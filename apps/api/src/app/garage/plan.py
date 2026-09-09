"""A vehicle's maintenance plan: what it needs, and when."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.garage.models import MaintenanceItem, Vehicle
from app.garage.projection import Status, estimate_mileage, project_due, status_for
from app.garage.templates import DEFAULT_TEMPLATES, WASH_INTERVAL_DAYS


@dataclass(frozen=True)
class PlanEntry:
    id: uuid.UUID
    name: str
    due_at: date | None
    due_mileage: int | None
    status: Status
    estimated_mileage: int
    #: True while the last-done date is an assumption. The interface says so;
    #: presenting it as a fact would be the dishonest version of this feature.
    is_assumed: bool


class PlanService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def seed(self, vehicle: Vehicle) -> None:
        """Give a new vehicle its plan.

        Baselined from the vehicle's own reading and today's date, and flagged
        as assumed. We do not know when this car's oil was last changed:
        pretending it was just done is comfortable and untrue, and pretending
        everything is overdue is a first screen of red that is mostly wrong.
        """
        # Idempotent. The seed shares a transaction with the vehicle insert so
        # this should not happen -- and the guard costs nothing next to a
        # garage listing sixteen oil changes.
        existing = await self._session.execute(
            select(MaintenanceItem.id).where(MaintenanceItem.vehicle_id == vehicle.id).limit(1)
        )
        if existing.first() is not None:
            return

        baseline_date = vehicle.odometer_recorded_at.date()
        for order, template in enumerate(DEFAULT_TEMPLATES):
            self._session.add(
                MaintenanceItem(
                    vehicle_id=vehicle.id,
                    name=template.name,
                    interval_miles=template.interval_miles,
                    interval_months=template.interval_months,
                    interval_days=(
                        WASH_INTERVAL_DAYS if template.name.startswith("Wash") else None
                    ),
                    last_done_at=baseline_date,
                    last_done_mileage=vehicle.odometer,
                    is_baseline=True,
                    sort_order=order,
                )
            )
        await self._session.commit()

    async def items_for(self, vehicle_id: uuid.UUID) -> list[MaintenanceItem]:
        result = await self._session.execute(
            select(MaintenanceItem)
            .where(MaintenanceItem.vehicle_id == vehicle_id)
            .order_by(MaintenanceItem.sort_order)
        )
        return list(result.scalars().all())

    async def project(self, vehicle: Vehicle, *, today: date) -> list[PlanEntry]:
        """Turn stored items into dated, banded answers.

        `today` is a parameter rather than a call to the clock, so this can be
        tested at any point in a vehicle's life without waiting for one.
        """
        items = await self.items_for(vehicle.id)
        estimated = estimate_mileage(
            vehicle.odometer,
            vehicle.odometer_recorded_at.date(),
            vehicle.annual_mileage,
            on=today,
        )

        entries: list[PlanEntry] = []
        for item in items:
            if item.interval_days is not None:
                # The one item measured in days. Handled here rather than in
                # the engine, which would otherwise carry a third interval unit
                # for a single row.
                due_at: date | None = item.last_done_at + timedelta(days=item.interval_days)
            else:
                due_at = project_due(
                    last_done_at=item.last_done_at,
                    last_done_mileage=item.last_done_mileage,
                    interval_miles=item.interval_miles,
                    interval_months=item.interval_months,
                    annual_mileage=vehicle.annual_mileage,
                )

            entries.append(
                PlanEntry(
                    id=item.id,
                    name=item.name,
                    due_at=due_at,
                    due_mileage=(
                        item.last_done_mileage + item.interval_miles
                        if item.interval_miles is not None
                        else None
                    ),
                    status=status_for(due_at, today=today),
                    estimated_mileage=estimated,
                    is_assumed=item.is_baseline,
                )
            )
        return entries
