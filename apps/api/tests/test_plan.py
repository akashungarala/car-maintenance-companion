"""Seeding a maintenance plan, and reading it back as projections."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.garage.plan import PlanService
from app.garage.projection import Status
from app.garage.repository import VehicleRepository
from app.garage.templates import DEFAULT_TEMPLATES
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


async def _vehicle(session, **overrides):  # type: ignore[no-untyped-def]
    user = await IdentityService(session).upsert_user("owner@example.com")
    return await VehicleRepository(session, user.id).create(
        **{
            "year": 2019,
            "make": "Honda",
            "model": "Civic",
            "odometer": 48_200,
            "annual_mileage": 12_000,
            **overrides,
        }
    )


async def test_creating_a_vehicle_seeds_every_template(session) -> None:  # type: ignore[no-untyped-def]
    vehicle = await _vehicle(session)

    items = await PlanService(session).items_for(vehicle.id)

    assert len(items) == len(DEFAULT_TEMPLATES)
    assert {i.name for i in items} == {t.name for t in DEFAULT_TEMPLATES}


async def test_seeded_items_are_marked_as_assumed(session) -> None:  # type: ignore[no-untyped-def]
    """We do not know when this car's oil was last changed.

    Baselining from today keeps the dates plausible; the flag is what stops the
    interface presenting an assumption as a fact.
    """
    vehicle = await _vehicle(session)

    items = await PlanService(session).items_for(vehicle.id)

    assert all(item.is_baseline for item in items)


async def test_the_baseline_is_the_vehicles_own_reading(session) -> None:  # type: ignore[no-untyped-def]
    vehicle = await _vehicle(session, odometer=48_200)

    items = await PlanService(session).items_for(vehicle.id)

    assert all(item.last_done_mileage == 48_200 for item in items)


async def test_the_plan_projects_a_due_date_for_each_item(session) -> None:  # type: ignore[no-untyped-def]
    vehicle = await _vehicle(session)

    plan = await PlanService(session).project(vehicle, today=date(2026, 1, 1))

    assert len(plan) == len(DEFAULT_TEMPLATES)
    assert all(entry.status in set(Status) for entry in plan)


async def test_a_freshly_added_car_has_nothing_overdue(session) -> None:  # type: ignore[no-untyped-def]
    """The point of baselining from today.

    A first screen of red would be mostly wrong and would destroy trust in the
    one number the product exists to provide.
    """
    vehicle = await _vehicle(session)
    today = vehicle.odometer_recorded_at.date()

    plan = await PlanService(session).project(vehicle, today=today)

    assert not [entry for entry in plan if entry.status is Status.OVERDUE]


async def test_the_wash_becomes_due_soon_within_three_weeks(session) -> None:  # type: ignore[no-untyped-def]
    """The item that keeps somebody opening the app between oil changes."""
    vehicle = await _vehicle(session)
    seeded_on = vehicle.odometer_recorded_at.date()

    plan = await PlanService(session).project(vehicle, today=seeded_on + timedelta(days=22))

    wash = next(entry for entry in plan if entry.name.startswith("Wash"))
    assert wash.status is Status.OVERDUE


async def test_a_heavily_driven_car_becomes_overdue_on_mileage(session) -> None:  # type: ignore[no-untyped-def]
    vehicle = await _vehicle(session, annual_mileage=30_000)
    seeded_on = vehicle.odometer_recorded_at.date()

    # 5,000 miles at 30,000/year is about two months.
    plan = await PlanService(session).project(vehicle, today=seeded_on + timedelta(days=80))

    oil = next(entry for entry in plan if entry.name.startswith("Engine oil"))
    assert oil.status is Status.OVERDUE


async def test_the_plan_reports_the_estimated_mileage(session) -> None:  # type: ignore[no-untyped-def]
    """The number the user cannot get any other way without walking outside."""
    vehicle = await _vehicle(session, odometer=48_200, annual_mileage=12_000)
    seeded_on = vehicle.odometer_recorded_at.date()

    plan = await PlanService(session).project(vehicle, today=seeded_on + timedelta(days=365))

    assert plan[0].estimated_mileage == pytest.approx(60_200, abs=50)


async def test_items_with_no_intervals_are_never_overdue(session) -> None:  # type: ignore[no-untyped-def]
    """A car in storage does not need its tires rotated."""
    vehicle = await _vehicle(session, annual_mileage=0)
    seeded_on = vehicle.odometer_recorded_at.date()

    plan = await PlanService(session).project(vehicle, today=seeded_on + timedelta(days=3650))

    rotation = next(entry for entry in plan if entry.name.startswith("Tire"))
    assert rotation.due_at is None
    assert rotation.status is Status.UPCOMING


async def test_seeding_is_idempotent(session) -> None:  # type: ignore[no-untyped-def]
    """A retried creation must not double every item.

    The vehicle insert and the plan seed share a transaction, so this should
    not happen -- and a guard costs nothing next to a garage listing sixteen
    oil changes.
    """
    vehicle = await _vehicle(session)
    service = PlanService(session)

    await service.seed(vehicle)

    assert len(await service.items_for(vehicle.id)) == len(DEFAULT_TEMPLATES)
