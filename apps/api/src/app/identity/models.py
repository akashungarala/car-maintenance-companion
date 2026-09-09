"""Identity tables."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

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


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The address, not a user id. A link can be requested for any address --
    # that is what makes the endpoint enumeration-safe -- so tying tokens to
    # user rows would let anyone create accounts for addresses they do not
    # control simply by asking. The user is created when a link is *consumed*,
    # which is the point at which control of the address has been proven.
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
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

    __table_args__ = (
        # Every lookup is "find the live token for this user", so the partial
        # index covers exactly the rows that query touches and skips the
        # accumulating history of spent ones.
        Index(
            "ix_magic_link_tokens_live",
            "email",
            postgresql_where=consumed_at.is_(None),
        ),
    )


class Session(Base):
    """A signed-in browser.

    A row rather than a signed token, so it can be revoked. A stateless token
    stays valid until it expires no matter what happens in between, which means
    a sign-out that does not sign you out and no way to end a session on a
    device you no longer have.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Hashed for the same reason as the sign-in token, with higher stakes: this
    # one is valid for thirty days rather than fifteen minutes.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
