"""Vehicles, and the ownership boundary around them.

The ownership tests here are the template for every resource added from now on.
They are not about this feature working; they are about it failing correctly
for somebody who is not supposed to see it.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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


async def _two_users(session):  # type: ignore[no-untyped-def]
    identity = IdentityService(session)
    return (
        await identity.upsert_user("owner@example.com"),
        await identity.upsert_user("stranger@example.com"),
    )


async def test_a_vehicle_belongs_to_the_user_who_created_it(session) -> None:  # type: ignore[no-untyped-def]
    owner, _ = await _two_users(session)
    repo = VehicleRepository(session, owner.id)

    vehicle = await repo.create(
        year=2019, make="Honda", model="Civic", odometer=48200, annual_mileage=12000
    )

    assert vehicle.user_id == owner.id
    assert vehicle.odometer_recorded_at is not None


async def test_a_stranger_cannot_list_another_users_vehicles(session) -> None:  # type: ignore[no-untyped-def]
    """The IDOR test. Expected to exist for every resource from here on."""
    owner, stranger = await _two_users(session)
    await VehicleRepository(session, owner.id).create(
        year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000
    )

    theirs = await VehicleRepository(session, stranger.id).list()

    assert theirs == []


async def test_a_stranger_cannot_fetch_another_users_vehicle_by_id(session) -> None:  # type: ignore[no-untyped-def]
    """Guessing an id must not be enough.

    Returning None rather than raising means the caller produces a 404, which
    is indistinguishable from an id that never existed -- so the endpoint
    cannot be used to discover which ids are real.
    """
    owner, stranger = await _two_users(session)
    vehicle = await VehicleRepository(session, owner.id).create(
        year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000
    )

    found = await VehicleRepository(session, stranger.id).get(vehicle.id)

    assert found is None


async def test_the_owner_can_fetch_their_own_vehicle(session) -> None:  # type: ignore[no-untyped-def]
    owner, _ = await _two_users(session)
    repo = VehicleRepository(session, owner.id)
    created = await repo.create(
        year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000
    )

    assert (await repo.get(created.id)) is not None


async def test_an_unknown_id_returns_nothing(session) -> None:  # type: ignore[no-untyped-def]
    owner, _ = await _two_users(session)

    assert await VehicleRepository(session, owner.id).get(uuid.uuid4()) is None


async def test_vehicles_come_back_newest_first(session) -> None:  # type: ignore[no-untyped-def]
    """The most recently added vehicle is the one being thought about."""
    owner, _ = await _two_users(session)
    repo = VehicleRepository(session, owner.id)
    await repo.create(year=2014, make="Subaru", model="Outback", odometer=1, annual_mileage=6000)
    await repo.create(year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000)

    listed = await repo.list()

    assert [v.model for v in listed] == ["Civic", "Outback"]


async def test_the_nickname_defaults_to_year_make_model(session) -> None:  # type: ignore[no-untyped-def]
    """Most people have one car and do not name it.

    Requiring a name for something they think of as "the car" is a question
    with no right answer, so the obvious answer is filled in.
    """
    owner, _ = await _two_users(session)

    vehicle = await VehicleRepository(session, owner.id).create(
        year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000
    )

    assert vehicle.display_name == "2019 Honda Civic"


async def test_a_given_nickname_is_kept(session) -> None:  # type: ignore[no-untyped-def]
    owner, _ = await _two_users(session)

    vehicle = await VehicleRepository(session, owner.id).create(
        year=2019,
        make="Honda",
        model="Civic",
        odometer=1,
        annual_mileage=12000,
        nickname="The Civic",
    )

    assert vehicle.display_name == "The Civic"


async def test_deleting_a_user_removes_their_vehicles(session) -> None:  # type: ignore[no-untyped-def]
    """Nobody should have to remember to clean this up by hand."""
    from sqlalchemy import delete, select

    from app.garage.models import Vehicle
    from app.identity.models import User

    owner, _ = await _two_users(session)
    await VehicleRepository(session, owner.id).create(
        year=2019, make="Honda", model="Civic", odometer=1, annual_mileage=12000
    )

    await session.execute(delete(User).where(User.id == owner.id))
    await session.commit()

    remaining = (await session.execute(select(Vehicle))).scalars().all()
    assert remaining == []


@pytest.mark.parametrize(
    ("field", "value"),
    [("year", 219), ("year", 3000), ("odometer", -1), ("annual_mileage", -1)],
)
async def test_the_database_rejects_impossible_values(session, field: str, value: int) -> None:  # type: ignore[no-untyped-def]
    """Constraints, not just Pydantic.

    Validation at one entry point protects that entry point. A constraint
    protects the data from every future one -- another endpoint, a migration,
    a psql session at 2am -- and those are exactly the paths nobody writes
    tests for.
    """
    from sqlalchemy.exc import IntegrityError

    from app.garage.models import Vehicle

    owner, _ = await _two_users(session)
    valid = {
        "user_id": owner.id,
        "year": 2019,
        "make": "Honda",
        "model": "Civic",
        "odometer": 1,
        "annual_mileage": 12000,
    }

    session.add(Vehicle(**{**valid, field: value}))

    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()
