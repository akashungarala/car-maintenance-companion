"""Issuing and consuming magic-link tokens."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import MagicLinkToken, User

logger = structlog.get_logger()

#: 256 bits. A guessable token is a password with none of the protections, and
#: this is not brute-forceable inside the fifteen minutes it is valid.
TOKEN_BYTES = 32

#: ADR-0009. Long enough to switch to a phone and find the email; short enough
#: that a link left in an inbox for a week is not a standing key.
TOKEN_LIFETIME = timedelta(minutes=15)


def hash_token(raw: str) -> str:
    """sha256 of the token.

    Not a password hash, deliberately: bcrypt and friends are slow on purpose
    to resist offline guessing of low-entropy secrets. This secret has 256 bits
    of entropy, so there is nothing to guess, and a slow hash on the callback
    path would only add latency to every sign-in.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def normalise_email(email: str) -> str:
        return email.strip().lower()

    async def upsert_user(self, email: str) -> User:
        """Find or create the user for an address.

        Sign-in and sign-up are the same action: there is no separate
        registration step to complete, and nothing to confirm beyond proving
        control of the address, which the link itself does.
        """
        normalised = self.normalise_email(email)
        # ON CONFLICT rather than select-then-insert: two requests for the same
        # new address arriving together would otherwise both see "no user" and
        # both insert.
        stmt = (
            insert(User)
            .values(email=normalised)
            .on_conflict_do_nothing(index_elements=[User.email])
            .returning(User.id)
        )
        await self._session.execute(stmt)
        user = (
            await self._session.execute(select(User).where(User.email == normalised))
        ).scalar_one()
        await self._session.commit()
        return user

    async def issue_token(self, email: str) -> tuple[str, MagicLinkToken]:
        """Create a link for this address, invalidating any earlier one.

        Returns the raw token, which exists only in memory and in the email.
        It is never stored, logged or returned again.
        """
        user = await self.upsert_user(email)

        # Any previously issued link stops working. Two live links double the
        # window in which an intercepted email is useful, and the user is only
        # ever looking at the most recent one.
        await self._session.execute(
            update(MagicLinkToken)
            .where(MagicLinkToken.user_id == user.id, MagicLinkToken.consumed_at.is_(None))
            .values(consumed_at=datetime.now(UTC))
        )

        raw = secrets.token_urlsafe(TOKEN_BYTES)
        token = MagicLinkToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + TOKEN_LIFETIME,
        )
        self._session.add(token)
        await self._session.commit()

        # The address is not logged: it is a personal identifier, and this line
        # would scatter it across log storage with its own retention rules.
        logger.info("magic_link_issued", user_id=str(user.id), expires_at=token.expires_at)
        return raw, token

    async def consume_token(self, raw: str) -> User | None:
        """Spend a token, or return None.

        None covers every failure identically -- unknown, expired, already
        used. The caller must not be able to tell them apart, or the callback
        becomes an oracle for which links once existed.
        """
        now = datetime.now(UTC)
        # The UPDATE is the check: marking it consumed and requiring it to be
        # unconsumed in the same statement means two simultaneous uses of one
        # link cannot both succeed. A select-then-update would let both pass
        # the check before either wrote.
        result = await self._session.execute(
            update(MagicLinkToken)
            .where(
                MagicLinkToken.token_hash == hash_token(raw),
                MagicLinkToken.consumed_at.is_(None),
                MagicLinkToken.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(MagicLinkToken.user_id)
        )
        row = result.first()
        if row is None:
            await self._session.rollback()
            return None

        user = (
            await self._session.execute(select(User).where(User.id == row.user_id))
        ).scalar_one()
        user.last_signed_in_at = now
        await self._session.commit()
        logger.info("magic_link_consumed", user_id=str(user.id))
        return user
