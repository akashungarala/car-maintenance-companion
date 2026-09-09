"""Vehicle tables."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

#: A car built before 1900 is a typo, and one more than a year ahead is too.
#: The upper bound is generous rather than exact: model years run ahead of
#: calendar years, and rejecting a car somebody actually owns to enforce a
#: definition of "year" is the wrong trade.
MIN_YEAR = 1900
MAX_YEAR = 2100


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    make: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Optional. Most people have one car and do not name it, so the year, make
    #: and model stand in and no vehicle is ever untitled.
    nickname: Mapped[str | None] = mapped_column(String(64))

    #: The single reading every projection is anchored to.
    odometer: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Set server-side, always. Accepting it from the client would let a caller
    #: backdate a reading and shift every projected due date.
    odometer_recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    #: The other half of the projection. Captured as one of three plausible
    #: choices, because almost nobody knows this number.
    annual_mileage: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Enforced in the database, not only in Pydantic. Validation in one
        # layer protects one entry point; a constraint protects the data from
        # every future one, including a migration and a psql session at 2am.
        CheckConstraint(f"year >= {MIN_YEAR} AND year <= {MAX_YEAR}", name="ck_vehicles_year"),
        CheckConstraint("odometer >= 0", name="ck_vehicles_odometer_non_negative"),
        CheckConstraint("annual_mileage >= 0", name="ck_vehicles_annual_mileage_non_negative"),
    )

    @property
    def display_name(self) -> str:
        return self.nickname or f"{self.year} {self.make} {self.model}"


class MaintenanceItem(Base):
    """One thing a vehicle needs, and when it was last done.

    A per-vehicle row rather than a reference to a shared template. The
    intervals are copied at creation so they can be edited for one car without
    touching another's -- a shared table would need the copy anyway the first
    time somebody changed an interval, and would add a join to every plan
    query until then.
    """

    __tablename__ = "maintenance_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Either may be null. Registration is time-only; tire rotation is
    #: mileage-only; a car in storage never needs the latter, which is correct.
    interval_miles: Mapped[int | None] = mapped_column(Integer)
    interval_months: Mapped[int | None] = mapped_column(Integer)
    #: Days, for the one item measured in weeks rather than months. Cheaper
    #: than a third interval unit used by a single row.
    interval_days: Mapped[int | None] = mapped_column(Integer)

    last_done_at: Mapped[date] = mapped_column(Date, nullable=False)
    last_done_mileage: Mapped[int] = mapped_column(Integer, nullable=False)
    #: True while last_done_* is an assumption rather than something the user
    #: told us. The interface must not present an assumption as a fact, and the
    #: first time somebody marks this item done the flag clears.
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("last_done_mileage >= 0", name="ck_items_mileage_non_negative"),
    )


class ServiceRecord(Base):
    """Something that was actually done, and when.

    History rather than only the latest state. "When did I last do this?" is a
    question people ask standing on a garage forecourt, and the answer is worth
    more than the storage it costs.
    """

    __tablename__ = "service_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    maintenance_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("maintenance_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Denormalised on purpose: an item can be renamed or its intervals
    #: changed, and history should say what was done at the time rather than
    #: what the item happens to be called now.
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    performed_at: Mapped[date] = mapped_column(Date, nullable=False)
    odometer: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("odometer >= 0", name="ck_service_records_odometer_non_negative"),
    )
