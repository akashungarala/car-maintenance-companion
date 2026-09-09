"""identity: key magic-link tokens on the address, not a user row

Requesting a link must work for any address -- that is what stops the endpoint
becoming a tool for discovering who has an account. Tying tokens to users
therefore meant a stranger could create an account for any address simply by
asking for a link, filling the table with rows nobody ever proved control of.

Tokens now carry the address. The user is created when a link is consumed,
which is the moment control of that address is demonstrated.

Dropping user_id in the same migration as adding email is safe here and would
not normally be: the previous image never writes this table, because the
endpoint that would do so does not exist in it. The table is empty in
production. A later change to a table with live readers must expand first and
contract in a separate release.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Created: 2026-09-09 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_magic_link_tokens_live", table_name="magic_link_tokens")
    op.add_column("magic_link_tokens", sa.Column("email", sa.String(length=320), nullable=False))
    op.drop_constraint("magic_link_tokens_user_id_fkey", "magic_link_tokens", type_="foreignkey")
    op.drop_column("magic_link_tokens", "user_id")
    op.create_index("ix_magic_link_tokens_email", "magic_link_tokens", ["email"], unique=False)
    op.create_index(
        "ix_magic_link_tokens_live",
        "magic_link_tokens",
        ["email"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_magic_link_tokens_live", table_name="magic_link_tokens")
    op.drop_index("ix_magic_link_tokens_email", table_name="magic_link_tokens")
    op.add_column(
        "magic_link_tokens",
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "magic_link_tokens_user_id_fkey",
        "magic_link_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("magic_link_tokens", "email")
    op.create_index(
        "ix_magic_link_tokens_live",
        "magic_link_tokens",
        ["user_id"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )
