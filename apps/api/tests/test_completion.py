"""Marking maintenance done, and what it quietly changes."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.garage.completion import CompletionService
from app.garage.plan import PlanService
from app.garage.repository import VehicleRepository
from app.identity.service import IdentityService
from app.models import Base

pytestmark = pytest.mark.integration


@pytest.fixture
async def session(postgres_url: str):  # type: ignore[no-untyped-def]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _setup(session, annual_mileage: int = 12_000):  # type: ignore[no-untyped-def]
    user = await IdentityService(session).upsert_user("owner@example.com")
    vehicle = await VehicleRepository(session, user.id).create(
        year=2019, make="Honda", model="Civic", odometer=48_000, annual_mileage=annual_mileage
    )
    items = await PlanService(session).items_for(vehicle.id)
    oil = next(i for i in items if i.name.startswith("Engine oil"))
    return vehicle, oil


async def test_completing_records_the_service(session) -> None:  # type: ignore[no-untyped-def]
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()

    record = await CompletionService(session).complete(
        vehicle=vehicle,
        item_id=oil.id,
        odometer=53_000,
        performed_at=anchor + timedelta(days=180),
    )

    assert record.name == "Engine oil & filter"
    assert record.odometer == 53_000


async def test_completing_clears_the_assumption(session) -> None:  # type: ignore[no-untyped-def]
    """The dashboard stops saying "assumed" and starts telling the truth."""
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()

    await CompletionService(session).complete(
        vehicle=vehicle, item_id=oil.id, odometer=53_000, performed_at=anchor + timedelta(days=180)
    )

    await session.refresh(oil)
    assert oil.is_baseline is False
    assert oil.last_done_mileage == 53_000


async def test_completing_re_anchors_the_vehicle(session) -> None:  # type: ignore[no-untyped-def]
    """Every other item's projection improves too, which is why we ask for the
    odometer rather than just the date."""
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()

    await CompletionService(session).complete(
        vehicle=vehicle, item_id=oil.id, odometer=53_000, performed_at=anchor + timedelta(days=180)
    )

    await session.refresh(vehicle)
    assert vehicle.odometer == 53_000


async def test_completing_recalibrates_the_usage_rate(session) -> None:  # type: ignore[no-untyped-def]
    """The product's central bet.

    The user said "average" when they added the car. Six months later they have
    driven 5,000 miles, which is 10,000 a year -- and they never told us that.
    """
    vehicle, oil = await _setup(session, annual_mileage=12_000)
    anchor = vehicle.odometer_recorded_at.date()

    await CompletionService(session).complete(
        vehicle=vehicle, item_id=oil.id, odometer=53_000, performed_at=anchor + timedelta(days=182)
    )

    await session.refresh(vehicle)
    assert vehicle.annual_mileage == pytest.approx(10_027, abs=100)


async def test_a_backwards_reading_is_refused_and_changes_nothing(session) -> None:  # type: ignore[no-untyped-def]
    """A rejected reading must leave no trace.

    4820 for 48200 is a typo, and a half-applied completion would be worse than
    a refused one.
    """
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()

    with pytest.raises(ValueError):
        await CompletionService(session).complete(
            vehicle=vehicle,
            item_id=oil.id,
            odometer=4_820,
            performed_at=anchor + timedelta(days=60),
        )

    await session.refresh(vehicle)
    await session.refresh(oil)
    assert vehicle.odometer == 48_000
    assert oil.is_baseline is True
    assert await CompletionService(session).history(vehicle.id) == []


async def test_an_item_from_another_vehicle_is_refused(session) -> None:  # type: ignore[no-untyped-def]
    """Scoped through the vehicle, which is already scoped to its owner."""
    vehicle, _ = await _setup(session)
    other_user = await IdentityService(session).upsert_user("stranger@example.com")
    other = await VehicleRepository(session, other_user.id).create(
        year=2014, make="Subaru", model="Outback", odometer=1, annual_mileage=6_000
    )
    their_item = (await PlanService(session).items_for(other.id))[0]

    with pytest.raises(LookupError):
        await CompletionService(session).complete(
            vehicle=vehicle,
            item_id=their_item.id,
            odometer=49_000,
            performed_at=date(2026, 6, 1),
        )


async def test_history_comes_back_most_recent_first(session) -> None:  # type: ignore[no-untyped-def]
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()
    service = CompletionService(session)

    await service.complete(
        vehicle=vehicle, item_id=oil.id, odometer=53_000, performed_at=anchor + timedelta(days=180)
    )
    await service.complete(
        vehicle=vehicle, item_id=oil.id, odometer=58_000, performed_at=anchor + timedelta(days=365)
    )

    history = await service.history(vehicle.id)
    assert [r.odometer for r in history] == [58_000, 53_000]


async def test_a_completion_makes_the_dashboard_stop_assuming(session) -> None:  # type: ignore[no-untyped-def]
    """The end-to-end effect, from the user's point of view."""
    vehicle, oil = await _setup(session)
    anchor = vehicle.odometer_recorded_at.date()

    await CompletionService(session).complete(
        vehicle=vehicle, item_id=oil.id, odometer=53_000, performed_at=anchor + timedelta(days=180)
    )

    await session.refresh(vehicle)
    plan = await PlanService(session).project(vehicle, today=anchor + timedelta(days=180))
    entry = next(e for e in plan if e.name.startswith("Engine oil"))
    assert entry.is_assumed is False
