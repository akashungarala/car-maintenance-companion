"""Issuing and consuming magic-link tokens."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.models import MagicLinkToken, Session, User

logger = structlog.get_logger()

#: 256 bits. A guessable token is a password with none of the protections, and
#: this is not brute-forceable inside the fifteen minutes it is valid.
TOKEN_BYTES = 32

#: ADR-0009. Long enough to switch to a phone and find the email; short enough
#: that a link left in an inbox for a week is not a standing key.
TOKEN_LIFETIME = timedelta(minutes=15)

#: Sliding. This is a product people use when something needs doing, which may
#: be six weeks apart, so a session that expires between visits turns every
#: visit into a sign-in -- the thing this epic exists to avoid.
SESSION_LIFETIME = timedelta(days=30)


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

        No user row is created here. A link can be requested for any address --
        that is what makes the endpoint enumeration-safe -- so creating users on
        request would let anyone fill the table with accounts for addresses they
        do not control. The user appears when the link is consumed.

        Returns the raw token, which exists only in memory and in the email. It
        is never stored, logged, or returned again.
        """
        normalised = self.normalise_email(email)

        # Any previously issued link stops working. Two live links double the
        # window in which an intercepted email is useful, and the user is only
        # ever looking at the most recent one.
        await self._session.execute(
            update(MagicLinkToken)
            .where(MagicLinkToken.email == normalised, MagicLinkToken.consumed_at.is_(None))
            .values(consumed_at=datetime.now(UTC))
        )

        raw = secrets.token_urlsafe(TOKEN_BYTES)
        token = MagicLinkToken(
            email=normalised,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + TOKEN_LIFETIME,
        )
        self._session.add(token)
        await self._session.commit()

        # The address is not logged: it is a personal identifier, and this line
        # would scatter it across log storage with its own retention rules.
        logger.info("magic_link_issued", expires_at=token.expires_at)
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
            .returning(MagicLinkToken.email)
        )
        row = result.first()
        if row is None:
            await self._session.rollback()
            return None

        # Control of the address is now proven, so this is where the account
        # comes into existence. Sign-in and sign-up are the same action.
        user = await self.upsert_user(row.email)
        user.last_signed_in_at = now
        await self._session.commit()
        logger.info("magic_link_consumed", user_id=str(user.id))
        return user


class SessionService:
    """Creating, resolving and revoking signed-in browsers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID) -> tuple[str, Session]:
        raw = secrets.token_urlsafe(TOKEN_BYTES)
        record = Session(
            user_id=user_id,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + SESSION_LIFETIME,
        )
        self._session.add(record)
        await self._session.commit()
        logger.info("session_created", user_id=str(user_id))
        return raw, record

    async def resolve(self, raw: str) -> User | None:
        """Who this cookie belongs to, extending the session as a side effect.

        Sliding expiry: somebody who visits every week is never signed out,
        while somebody who disappears for a month is. The extension is written
        on every request, which is one small write per request and the reason
        last_seen_at is useful at all.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            update(Session)
            .where(
                Session.token_hash == hash_token(raw),
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
            .values(expires_at=now + SESSION_LIFETIME, last_seen_at=now)
            .returning(Session.user_id)
        )
        row = result.first()
        if row is None:
            await self._session.rollback()
            return None

        user = (
            await self._session.execute(select(User).where(User.id == row.user_id))
        ).scalar_one()
        await self._session.commit()
        return user

    async def revoke(self, raw: str) -> None:
        """End a session.

        Signing out with a cookie that is already stale is ordinary rather than
        exceptional, so an unknown token is not an error.
        """
        await self._session.execute(
            update(Session)
            .where(Session.token_hash == hash_token(raw), Session.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.commit()
