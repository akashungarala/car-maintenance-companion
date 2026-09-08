"""initial empty schema

Deliberately creates nothing. It establishes the migration chain and the
alembic_version table so the deployment pipeline has something to run and
verify before any product table exists. Tables arrive with the stories that
need them (E2 onwards).

Revision ID: 604ca14ec7b7
Revises:
Created: 2026-09-08 08:16:28.002510
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "604ca14ec7b7"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
