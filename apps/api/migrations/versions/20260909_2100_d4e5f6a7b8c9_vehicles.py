"""garage: vehicles

Expand-only: a new table, nothing altered.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Created: 2026-09-09 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=64), nullable=True),
        sa.Column("odometer", sa.Integer(), nullable=False),
        sa.Column(
            "odometer_recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("annual_mileage", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        # ON DELETE CASCADE: removing a user removes their garage, without
        # anybody having to remember to clean it up.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # In the database, not only in Pydantic. Validation at one entry point
        # protects that entry point; a constraint protects the data from every
        # future one, including a migration and a psql session at 2am.
        sa.CheckConstraint("year >= 1900 AND year <= 2100", name="ck_vehicles_year"),
        sa.CheckConstraint("odometer >= 0", name="ck_vehicles_odometer_non_negative"),
        sa.CheckConstraint("annual_mileage >= 0", name="ck_vehicles_annual_mileage_non_negative"),
    )
    op.create_index("ix_vehicles_user_id", "vehicles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_vehicles_user_id", table_name="vehicles")
    op.drop_table("vehicles")
