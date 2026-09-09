"""POST and GET /vehicles.

Every test here that matters is about somebody who should not get an answer.
"""

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
    from app.garage import models as _garage  # noqa: F401
    from app.identity import models as _identity  # noqa: F401
    from app.models import Base

    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("TRUNCATE vehicles, sessions, magic_link_tokens, users CASCADE"))
    await engine.dispose()

    client = build_client(redis_url)
    await client.flushdb()
    await client.aclose()

    settings = Settings(
        environment="test",
        log_format="json",
        database_url=postgres_url,
        redis_url=redis_url,
        session_cookie_secure=False,
        session_cookie_path="/",
    )
    application = create_app(settings=settings, readiness=ReadinessRegistry())
    application.state.queue = None
    yield application
    await application.state.cache.aclose()
    await application.state.database.dispose()


async def _signed_in(app, email: str) -> AsyncClient:  # type: ignore[no-untyped-def]
    """A client holding a real session cookie for this address."""
    from app.identity.service import IdentityService

    async with app.state.database.session() as session:
        raw, _ = await IdentityService(session).issue_token(email)

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://t")
    response = await client.post("/auth/session", json={"token": raw})
    assert response.status_code == 200
    return client


VALID = {
    "year": 2019,
    "make": "Honda",
    "model": "Civic",
    "odometer": 48200,
    "annual_mileage": 12000,
}


async def test_creating_a_vehicle_returns_it(app) -> None:  # type: ignore[no-untyped-def]
    client = await _signed_in(app, "owner@example.com")

    response = await client.post("/vehicles", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["make"] == "Honda"
    assert body["display_name"] == "2019 Honda Civic"
    await client.aclose()


async def test_listing_returns_only_your_own_vehicles(app) -> None:  # type: ignore[no-untyped-def]
    """The test this whole story exists to pass."""
    owner = await _signed_in(app, "owner@example.com")
    stranger = await _signed_in(app, "stranger@example.com")
    await owner.post("/vehicles", json=VALID)

    theirs = await stranger.get("/vehicles")

    assert theirs.status_code == 200
    assert theirs.json() == []
    await owner.aclose()
    await stranger.aclose()


async def test_a_stranger_cannot_fetch_your_vehicle_by_id(app) -> None:  # type: ignore[no-untyped-def]
    """404, not 403.

    "Forbidden" confirms the record exists, which is half of what an attacker
    guessing ids wants to know.
    """
    owner = await _signed_in(app, "owner@example.com")
    stranger = await _signed_in(app, "stranger@example.com")
    created = (await owner.post("/vehicles", json=VALID)).json()

    response = await stranger.get(f"/vehicles/{created['id']}")

    assert response.status_code == 404
    await owner.aclose()
    await stranger.aclose()


async def test_both_endpoints_require_a_session(app) -> None:  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as anon:
        assert (await anon.get("/vehicles")).status_code == 401
        assert (await anon.post("/vehicles", json=VALID)).status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("year", 219),
        ("year", 3000),
        ("odometer", -1),
        ("annual_mileage", -1),
        ("make", ""),
        ("model", ""),
    ],
)
async def test_invalid_input_is_rejected_naming_the_field(app, field: str, value) -> None:  # type: ignore[no-untyped-def]
    client = await _signed_in(app, "owner@example.com")

    response = await client.post("/vehicles", json={**VALID, field: value})

    assert response.status_code == 422
    assert field in response.text, "the response must say which field was wrong"
    await client.aclose()


async def test_the_recorded_time_cannot_be_supplied_by_the_client(app) -> None:  # type: ignore[no-untyped-def]
    """Rejected outright rather than quietly ignored.

    Every projected due date is computed from this timestamp, so a client able
    to set it could move its own maintenance schedule arbitrarily. Ignoring the
    field silently would be safe but dishonest: the caller would believe they
    had set it. A 422 tells them they did not.

    The same strictness catches ordinary typos -- "odomter" is rejected rather
    than dropped, which is the difference between a clear error and a vehicle
    saved with a mileage of zero.
    """
    client = await _signed_in(app, "owner@example.com")

    response = await client.post(
        "/vehicles", json={**VALID, "odometer_recorded_at": "1999-01-01T00:00:00Z"}
    )

    assert response.status_code == 422
    await client.aclose()


async def test_the_server_records_when_the_reading_was_taken(app) -> None:  # type: ignore[no-untyped-def]
    from datetime import UTC, datetime

    client = await _signed_in(app, "owner@example.com")

    created = (await client.post("/vehicles", json=VALID)).json()

    recorded = datetime.fromisoformat(created["odometer_recorded_at"])
    assert abs((datetime.now(UTC) - recorded).total_seconds()) < 60
    await client.aclose()


async def test_a_misspelled_field_is_rejected(app) -> None:  # type: ignore[no-untyped-def]
    """Otherwise the vehicle saves with a mileage of zero and nobody is told."""
    client = await _signed_in(app, "owner@example.com")
    payload = {k: v for k, v in VALID.items() if k != "odometer"}

    response = await client.post("/vehicles", json={**payload, "odomter": 48200})

    assert response.status_code == 422
    await client.aclose()


async def test_vehicles_are_listed_newest_first(app) -> None:  # type: ignore[no-untyped-def]
    client = await _signed_in(app, "owner@example.com")
    await client.post("/vehicles", json={**VALID, "model": "Outback"})
    await client.post("/vehicles", json={**VALID, "model": "Civic"})

    listed = (await client.get("/vehicles")).json()

    assert [v["model"] for v in listed] == ["Civic", "Outback"]
    await client.aclose()
