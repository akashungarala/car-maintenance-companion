"""Sessions: rows, not signed tokens.

A session that cannot be revoked is not a session, it is a bearer token with a
long expiry. Everything here follows from wanting sign-out to actually sign
someone out.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.identity.models import Session, User
from app.identity.service import IdentityService, SessionService
from app.models import Base

pytestmark = pytest.mark.integration


@pytest.fixture
async def session(postgres_url: str):  # type: ignore[no-untyped-def]
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _user(session: AsyncSession) -> User:
    return await IdentityService(session).upsert_user("sam@example.com")


async def test_the_raw_session_token_is_never_stored(session: AsyncSession) -> None:
    """Same reasoning as the magic-link token, and higher stakes: this one is
    valid for thirty days rather than fifteen minutes."""
    user = await _user(session)
    service = SessionService(session)

    raw, _ = await service.create(user.id)

    rows = (await session.execute(select(Session))).scalars().all()
    assert rows[0].token_hash != raw
    assert len(rows[0].token_hash) == 64


async def test_a_session_resolves_to_its_user(session: AsyncSession) -> None:
    user = await _user(session)
    service = SessionService(session)
    raw, _ = await service.create(user.id)

    resolved = await service.resolve(raw)

    assert resolved is not None
    assert resolved.id == user.id


async def test_an_unknown_token_resolves_to_nothing(session: AsyncSession) -> None:
    service = SessionService(session)

    assert await service.resolve("a" * 43) is None


async def test_an_expired_session_resolves_to_nothing(session: AsyncSession) -> None:
    user = await _user(session)
    service = SessionService(session)
    raw, record = await service.create(user.id)

    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    assert await service.resolve(raw) is None


async def test_a_revoked_session_resolves_to_nothing(session: AsyncSession) -> None:
    """The entire reason sessions are rows.

    A signed token would remain valid until it expired, no matter what happened
    in between -- which means a sign-out that does not sign you out.
    """
    user = await _user(session)
    service = SessionService(session)
    raw, _ = await service.create(user.id)

    await service.revoke(raw)

    assert await service.resolve(raw) is None


async def test_revoking_an_unknown_token_is_not_an_error(session: AsyncSession) -> None:
    """Signing out with a stale cookie is ordinary, not exceptional."""
    service = SessionService(session)

    await service.revoke("a" * 43)  # must not raise


async def test_sessions_last_thirty_days(session: AsyncSession) -> None:
    """This is a product people use when something needs doing, which may be six
    weeks apart. A session expiring between visits turns every visit into a
    sign-in, which is what this epic exists to avoid."""
    user = await _user(session)
    service = SessionService(session)

    _, record = await service.create(user.id)

    remaining = record.expires_at - datetime.now(UTC)
    assert timedelta(days=29) < remaining <= timedelta(days=30)


async def test_using_a_session_extends_it(session: AsyncSession) -> None:
    """Sliding, not fixed. Somebody who visits every week should never be
    signed out; somebody who disappears for a month should be."""
    user = await _user(session)
    service = SessionService(session)
    raw, record = await service.create(user.id)

    record.expires_at = datetime.now(UTC) + timedelta(days=2)
    await session.commit()
    await service.resolve(raw)
    await session.refresh(record)

    assert record.expires_at - datetime.now(UTC) > timedelta(days=29)
