"""POST /auth/session and GET /auth/me."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.health import ReadinessRegistry
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def app(postgres_url: str, redis_url: str):  # type: ignore[no-untyped-def]
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.cache import build_client
    from app.identity import models as _identity  # noqa: F401
    from app.models import Base

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE sessions, magic_link_tokens, users CASCADE"))
    await engine.dispose()

    client = build_client(redis_url)
    await client.flushdb()
    await client.aclose()

    settings = Settings(
        environment="test",
        log_format="json",
        database_url=postgres_url,
        redis_url=redis_url,
        # Off here only because the test client speaks plain HTTP.
        session_cookie_secure=False,
        # The test app is mounted at the root; in production it sits under the
        # portfolio's path prefix. Leaving the production path here would mean
        # the client correctly refuses to send the cookie back, and every
        # authenticated test would fail for a reason unrelated to the code.
        session_cookie_path="/",
    )
    application = create_app(settings=settings, readiness=ReadinessRegistry())
    application.state.queue = None
    yield application
    await application.state.cache.aclose()
    await application.state.database.dispose()


async def _issue(app, email: str = "sam@example.com") -> str:  # type: ignore[no-untyped-def]
    from app.identity.service import IdentityService

    async with app.state.database.session() as session:
        raw, _ = await IdentityService(session).issue_token(email)
    return raw


async def test_a_valid_link_creates_a_session(app) -> None:  # type: ignore[no-untyped-def]
    token = await _issue(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/auth/session", json={"token": token})

    assert response.status_code == 200
    assert "cmc_session" in response.cookies


async def test_the_cookie_is_httponly_secure_and_samesite(app) -> None:  # type: ignore[no-untyped-def]
    """Three flags, each closing a different hole.

    HttpOnly keeps it away from JavaScript, so an XSS bug cannot read it.
    SameSite=Lax stops another site's form from acting as the user. Secure
    keeps it off plain HTTP.
    """
    app.state.settings.session_cookie_secure = True
    app.state.settings.session_cookie_path = "/apps/car-maintenance-companion"
    token = await _issue(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/auth/session", json={"token": token})

    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "secure" in header
    assert "path=/apps/car-maintenance-companion" in header


async def test_the_response_body_never_contains_the_session_token(app) -> None:  # type: ignore[no-untyped-def]
    """The cookie is the only place it belongs.

    A token in the body is readable by JavaScript, which is precisely what
    HttpOnly exists to prevent.
    """
    token = await _issue(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        response = await client.post("/auth/session", json={"token": token})

    assert response.cookies["cmc_session"] not in response.text


async def test_a_link_works_only_once(app) -> None:  # type: ignore[no-untyped-def]
    token = await _issue(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        first = await client.post("/auth/session", json={"token": token})
        second = await client.post("/auth/session", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 401


async def test_every_failure_looks_the_same(app) -> None:  # type: ignore[no-untyped-def]
    """Unknown, already used, malformed -- one response.

    Distinguishing them tells an attacker which tokens once existed.
    """
    used = await _issue(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/auth/session", json={"token": used})
        replayed = await client.post("/auth/session", json={"token": used})
        unknown = await client.post("/auth/session", json={"token": "a" * 43})

    assert replayed.status_code == unknown.status_code == 401
    assert replayed.json() == unknown.json()


async def test_signing_in_creates_the_user(app) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.identity.models import User

    token = await _issue(app, "brand-new@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/auth/session", json={"token": token})

    async with app.state.database.session() as session:
        users = (await session.execute(select(User))).scalars().all()
    assert [u.email for u in users] == ["brand-new@example.com"]


async def test_me_returns_the_signed_in_user(app) -> None:  # type: ignore[no-untyped-def]
    token = await _issue(app)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/auth/session", json={"token": token})
        me = await client.get("/auth/me")

    assert me.status_code == 200
    assert me.json()["email"] == "sam@example.com"


async def test_me_without_a_cookie_is_401(app) -> None:  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        me = await client.get("/auth/me")

    assert me.status_code == 401


async def test_me_with_a_revoked_session_is_401(app) -> None:  # type: ignore[no-untyped-def]
    """The point of storing sessions as rows."""
    from app.identity.service import SessionService

    token = await _issue(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/auth/session", json={"token": token})
        raw_session = client.cookies["cmc_session"]
        async with app.state.database.session() as session:
            await SessionService(session).revoke(raw_session)

        me = await client.get("/auth/me")

    assert me.status_code == 401
