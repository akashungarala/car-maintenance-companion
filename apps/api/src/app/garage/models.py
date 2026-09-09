"""Vehicle tables."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
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
