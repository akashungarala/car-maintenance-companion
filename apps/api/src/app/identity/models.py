"""Identity tables."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Stored lowercased, and unique. Addresses are case-insensitive in practice,
    # so storing them as typed would let Sam@example.com and sam@example.com
    # become two accounts for one person -- with two garages, and no way for
    # either to see the other's vehicles.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_signed_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tokens: Mapped[list["MagicLinkToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The sha256 of the token, never the token. A leaked database then shows
    # that a link exists and when it expires, but cannot be used to construct
    # one -- which is the difference between an embarrassment and a breach.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set on use. Single-use is enforced here rather than by deleting the row,
    # so a replayed link is distinguishable from one that never existed -- which
    # matters when investigating whether an email was intercepted.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="tokens")

    __table_args__ = (
        # Every lookup is "find the live token for this user", so the partial
        # index covers exactly the rows that query touches and skips the
        # accumulating history of spent ones.
        Index(
            "ix_magic_link_tokens_live",
            "user_id",
            postgresql_where=consumed_at.is_(None),
        ),
    )
