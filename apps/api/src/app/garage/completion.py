"""Marking maintenance done."""

import uuid
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.garage.models import MaintenanceItem, ServiceRecord, Vehicle
from app.garage.recalibration import recalibrate

logger = structlog.get_logger()


class CompletionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def complete(
        self,
        *,
        vehicle: Vehicle,
        item_id: uuid.UUID,
        odometer: int,
        performed_at: date,
    ) -> ServiceRecord:
        """Record a service, and learn from the reading it came with.

        Three things happen together, in one transaction: the item stops being
        an assumption, the vehicle's odometer anchor moves forward so every
        other item's projection improves, and the usage rate is recalculated
        from what the car actually did.

        The user asked for the first of those. The other two are why we ask for
        the odometer at all.
        """
        item = (
            await self._session.execute(
                select(MaintenanceItem).where(
                    MaintenanceItem.id == item_id,
                    # Scoped to the vehicle, which is already scoped to its
                    # owner: an item id from another garage resolves to nothing.
                    MaintenanceItem.vehicle_id == vehicle.id,
                )
            )
        ).scalar_one_or_none()
        if item is None:
            raise LookupError("No such maintenance item for this vehicle")

        # Raises on a reading that cannot be true. Deliberately before anything
        # is written: a rejected reading must leave no trace.
        new_rate = recalibrate(
            previous_odometer=vehicle.odometer,
            previous_recorded_at=vehicle.odometer_recorded_at.date(),
            new_odometer=odometer,
            new_recorded_at=performed_at,
            current_annual_mileage=vehicle.annual_mileage,
        )

        record = ServiceRecord(
            vehicle_id=vehicle.id,
            maintenance_item_id=item.id,
            # Denormalised: history says what was done at the time, not what
            # the item is called now.
            name=item.name,
            performed_at=performed_at,
            odometer=odometer,
        )
        self._session.add(record)

        item.last_done_at = performed_at
        item.last_done_mileage = odometer
        # No longer an assumption. The dashboard stops saying "assumed" for
        # this item, and starts telling the truth about it.
        item.is_baseline = False

        vehicle.odometer = odometer
        vehicle.odometer_recorded_at = vehicle.odometer_recorded_at.replace(
            year=performed_at.year, month=performed_at.month, day=performed_at.day
        )
        vehicle.annual_mileage = new_rate

        await self._session.commit()
        await self._session.refresh(record)
        logger.info(
            "maintenance_completed",
            vehicle_id=str(vehicle.id),
            item=item.name,
            recalibrated_to=new_rate,
        )
        return record

    async def history(self, vehicle_id: uuid.UUID) -> list[ServiceRecord]:
        result = await self._session.execute(
            select(ServiceRecord)
            .where(ServiceRecord.vehicle_id == vehicle_id)
            # Most recent first: "when did I last do this" is the question, and
            # the answer is at the top.
            .order_by(ServiceRecord.performed_at.desc(), ServiceRecord.created_at.desc())
        )
        return list(result.scalars().all())
