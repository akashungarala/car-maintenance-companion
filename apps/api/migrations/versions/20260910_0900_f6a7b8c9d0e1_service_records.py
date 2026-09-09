"""garage: service records

Expand-only: a new table.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Created: 2026-09-10 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("maintenance_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Denormalised on purpose: history should say what was done at the
        # time, not what the item happens to be called now.
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("performed_at", sa.Date(), nullable=False),
        sa.Column("odometer", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["maintenance_item_id"], ["maintenance_items.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("odometer >= 0", name="ck_service_records_odometer_non_negative"),
    )
    op.create_index("ix_service_records_vehicle_id", "service_records", ["vehicle_id"])
    op.create_index(
        "ix_service_records_maintenance_item_id", "service_records", ["maintenance_item_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_service_records_maintenance_item_id", table_name="service_records")
    op.drop_index("ix_service_records_vehicle_id", table_name="service_records")
    op.drop_table("service_records")
