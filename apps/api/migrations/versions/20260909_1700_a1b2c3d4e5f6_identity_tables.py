"""identity: users and magic-link tokens

Expand-only, like every migration here: it adds tables and nothing else, so the
previous image runs against this schema unchanged and rolling code back never
requires rolling schema back.

Revision ID: a1b2c3d4e5f6
Revises: 604ca14ec7b7
Created: 2026-09-09 17:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "604ca14ec7b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        # 320 is the maximum length of an email address per RFC 3696: 64 for
        # the local part, 255 for the domain, one for the @.
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_signed_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # Addresses are stored lowercased, so a plain unique constraint is
        # enough; the normalisation happens in the service, in one place.
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "magic_link_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # sha256 hex digest, never the token itself.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_magic_link_tokens_token_hash"),
    )

    # Partial: every lookup is "the live token for this user", so the index
    # covers exactly those rows and ignores the accumulating history of spent
    # ones, which is the part that grows without bound.
    op.create_index(
        "ix_magic_link_tokens_live",
        "magic_link_tokens",
        ["user_id"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_magic_link_tokens_live", table_name="magic_link_tokens")
    op.drop_table("magic_link_tokens")
    op.drop_table("users")
