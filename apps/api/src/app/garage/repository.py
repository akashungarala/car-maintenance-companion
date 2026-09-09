"""Vehicle queries, scoped to their owner by construction.

The scoping is not a filter somebody remembers to apply -- it is the only way
to build a query here. A repository cannot be constructed without a user, and
every statement it builds carries that user's id.

This matters more than it looks. Ad-hoc `WHERE user_id = ...` filters are how
IDOR bugs ship: the safe version and the unsafe version differ by one line,
the unsafe one works perfectly for anybody testing with their own data, and it
is found by a stranger. Making the scoped path the only path means the mistake
cannot be made by omission -- only by deliberately writing a second query
somewhere else, which is a thing a reviewer can see.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.garage.models import Vehicle


class VehicleRepository:
    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        self._session = session
        self._user_id = user_id

    def _scoped(self):  # type: ignore[no-untyped-def]
        """Every query starts here. There is no unscoped variant."""
        return select(Vehicle).where(Vehicle.user_id == self._user_id)

    async def list(self) -> list[Vehicle]:
        result = await self._session.execute(
            # Newest first: the most recently added vehicle is the one the user
            # is currently thinking about.
            self._scoped().order_by(Vehicle.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        """None for both "not yours" and "does not exist".

        The caller turns either into a 404, so the endpoint cannot be used to
        discover which ids are real.
        """
        result = await self._session.execute(self._scoped().where(Vehicle.id == vehicle_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        year: int,
        make: str,
        model: str,
        odometer: int,
        annual_mileage: int,
        nickname: str | None = None,
    ) -> Vehicle:
        vehicle = Vehicle(
            user_id=self._user_id,
            year=year,
            make=make.strip(),
            model=model.strip(),
            nickname=(nickname or "").strip() or None,
            odometer=odometer,
            annual_mileage=annual_mileage,
        )
        self._session.add(vehicle)
        await self._session.commit()
        await self._session.refresh(vehicle)
        return vehicle
