"""POST /auth/magic-link.

The endpoint's job is small and its constraints are unusual: it must be useful
to a legitimate user and useless to someone probing for accounts, and those two
requirements are in tension in every detail.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.health import ReadinessRegistry
from app.identity.models import MagicLinkToken, User
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def app_and_enqueued(postgres_url: str, redis_url: str, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """The app, plus a record of what it asked the queue to do."""
    from app.identity import router as auth_router

    enqueued: list[dict] = []

    async def fake_enqueue(pool, *, email: str, token: str, base_url: str) -> None:  # type: ignore[no-untyped-def]
        enqueued.append({"email": email, "token": token, "base_url": base_url})

    monkeypatch.setattr(auth_router, "enqueue_magic_link_email", fake_enqueue)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.cache import build_client
    from app.identity import models as _identity  # noqa: F401  (registers tables)
    from app.models import Base

    # The Postgres container is session-scoped and shared, and the migration
    # tests move it between base and head. Creating the tables here makes this
    # file independent of whatever ran before it.
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Truncated rather than dropped: dropping would pull the schema out
        # from under any test that runs after this one.
        await conn.execute(text("TRUNCATE magic_link_tokens, users CASCADE"))
    await engine.dispose()

    client = build_client(redis_url)
    await client.flushdb()
    await client.aclose()

    settings = Settings(
        environment="test",
        log_format="json",
        database_url=postgres_url,
        redis_url=redis_url,
        app_base_url="https://example.test",
    )
    app = create_app(settings=settings, readiness=ReadinessRegistry())
    # ASGITransport does not run the lifespan, which is where the real ARQ pool
    # is built. The enqueue call is monkeypatched above, so the pool is never
    # touched -- but the attribute must exist for the handler to reach it.
    app.state.queue = None
    yield app, enqueued
    await app.state.cache.aclose()
    await app.state.database.dispose()


async def _post(app, payload):  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        return await client.post("/auth/magic-link", json=payload)


async def test_a_valid_address_is_accepted(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    app, enqueued = app_and_enqueued

    response = await _post(app, {"email": "sam@example.com"})

    assert response.status_code == 202
    assert len(enqueued) == 1


async def test_an_unknown_address_is_indistinguishable_from_a_known_one(
    app_and_enqueued,  # type: ignore[no-untyped-def]
) -> None:
    """The single most important property of this endpoint.

    If the two differ in status, body, or anything else observable, the sign-in
    form becomes a tool for discovering who has an account.
    """
    app, _ = app_and_enqueued

    first = await _post(app, {"email": "brand-new@example.com"})
    # Consume it so the address becomes a real, known user.
    async with app.state.database.session() as session:
        from app.identity.service import IdentityService

        service = IdentityService(session)
        raw, _t = await service.issue_token("known@example.com")
        await service.consume_token(raw)

    second = await _post(app, {"email": "known@example.com"})

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


async def test_a_malformed_address_is_rejected(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    app, enqueued = app_and_enqueued

    response = await _post(app, {"email": "not-an-email"})

    assert response.status_code == 422
    assert enqueued == [], "a malformed address must not reach the queue"


async def test_requesting_a_link_creates_no_user(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    app, _ = app_and_enqueued

    await _post(app, {"email": "stranger@example.com"})

    async with app.state.database.session() as session:
        users = (await session.execute(select(User))).scalars().all()
    assert users == []


async def test_the_response_body_contains_no_token(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    """The link travels by email and nowhere else.

    Returning it would make the email pointless: anyone who could call the API
    could sign in as anyone.
    """
    app, enqueued = app_and_enqueued

    response = await _post(app, {"email": "sam@example.com"})

    body = response.text
    assert enqueued[0]["token"] not in body
    assert "token" not in response.json()


async def test_a_second_request_invalidates_the_first_link(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    app, enqueued = app_and_enqueued

    await _post(app, {"email": "sam@example.com"})
    await _post(app, {"email": "sam@example.com"})

    async with app.state.database.session() as session:
        from app.identity.service import IdentityService

        service = IdentityService(session)
        assert await service.consume_token(enqueued[0]["token"]) is None
        assert await service.consume_token(enqueued[1]["token"]) is not None


async def test_the_address_is_normalised_before_use(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    app, _enqueued = app_and_enqueued

    await _post(app, {"email": "  Sam@Example.COM  "})

    async with app.state.database.session() as session:
        tokens = (await session.execute(select(MagicLinkToken))).scalars().all()
    assert tokens[0].email == "sam@example.com"


async def test_the_sixth_request_in_a_minute_is_refused(app_and_enqueued) -> None:  # type: ignore[no-untyped-def]
    """Authentication gets the strict bucket: 5/min, not the general 100.

    This is the endpoint worth guessing against, and a legitimate person signs
    in once, not five times a minute.
    """
    app, _enqueued = app_and_enqueued

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        headers = {"CF-Connecting-IP": "203.0.113.99"}
        codes = []
        for _ in range(6):
            response = await client.post(
                "/auth/magic-link", json={"email": "sam@example.com"}, headers=headers
            )
            codes.append(response.status_code)

    assert codes[:5] == [202] * 5
    assert codes[5] == 429
