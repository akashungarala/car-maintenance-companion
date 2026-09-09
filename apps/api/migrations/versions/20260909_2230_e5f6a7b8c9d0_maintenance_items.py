"""garage: maintenance items

Expand-only: a new table.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Created: 2026-09-09 22:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        # All three intervals are nullable: registration is time-only, tire
        # rotation is mileage-only, and the wash is measured in days.
        sa.Column("interval_miles", sa.Integer(), nullable=True),
        sa.Column("interval_months", sa.Integer(), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=True),
        sa.Column("last_done_at", sa.Date(), nullable=False),
        sa.Column("last_done_mileage", sa.Integer(), nullable=False),
        # True while last_done_* is an assumption rather than something the
        # user told us.
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("last_done_mileage >= 0", name="ck_items_mileage_non_negative"),
    )
    op.create_index("ix_maintenance_items_vehicle_id", "maintenance_items", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_maintenance_items_vehicle_id", table_name="maintenance_items")
    op.drop_table("maintenance_items")
