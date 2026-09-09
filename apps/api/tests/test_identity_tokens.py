"""Magic-link tokens: the security properties, asserted rather than assumed.

Every rule here is one an attacker would test. Writing them as tests is the
only thing that keeps them true after the fifth refactor.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.identity.models import MagicLinkToken, User
from app.identity.service import IdentityService
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


async def test_email_is_normalised_to_lowercase(session: AsyncSession) -> None:
    """Addresses are case-insensitive in practice; storing them as typed means
    Sam@example.com and sam@example.com become two accounts for one person."""
    service = IdentityService(session)

    user = await service.upsert_user("Sam@Example.COM")

    assert user.email == "sam@example.com"


async def test_the_same_address_in_any_case_is_one_user(session: AsyncSession) -> None:
    service = IdentityService(session)

    first = await service.upsert_user("sam@example.com")
    second = await service.upsert_user("SAM@EXAMPLE.COM")

    assert first.id == second.id
    users = (await session.execute(select(User))).scalars().all()
    assert len(users) == 1


async def test_requesting_a_link_creates_no_user(session: AsyncSession) -> None:
    """Anyone can request a link for any address -- that is what makes the
    endpoint enumeration-safe. Creating a user row at that point would let a
    stranger fill the table with accounts for addresses they do not control.
    """
    service = IdentityService(session)

    await service.issue_token("stranger@example.com")

    assert (await session.execute(select(User))).scalars().all() == []


async def test_consuming_a_link_creates_the_user(session: AsyncSession) -> None:
    """Control of the address is proven here, and not before."""
    service = IdentityService(session)
    raw, _ = await service.issue_token("sam@example.com")

    user = await service.consume_token(raw)

    assert user is not None
    assert user.email == "sam@example.com"
    assert user.last_signed_in_at is not None


async def test_the_raw_token_is_never_stored(session: AsyncSession) -> None:
    """A leaked database must not yield usable sign-in links.

    Storing the hash makes the table useless to anyone who reads it: they can
    see that a token exists and when it expires, but cannot construct the link.
    """
    service = IdentityService(session)

    raw, _ = await service.issue_token("sam@example.com")

    rows = (await session.execute(select(MagicLinkToken))).scalars().all()
    assert len(rows) == 1
    assert rows[0].token_hash != raw
    assert raw not in rows[0].token_hash
    assert len(rows[0].token_hash) == 64, "expected a sha256 hex digest"


async def test_issuing_a_token_invalidates_any_earlier_one(session: AsyncSession) -> None:
    """Two live links double the window in which an intercepted email is
    useful, and the user is only ever looking at the most recent one."""
    service = IdentityService(session)

    first_raw, _ = await service.issue_token("sam@example.com")
    await service.issue_token("sam@example.com")

    assert await service.consume_token(first_raw) is None


async def test_a_token_works_exactly_once(session: AsyncSession) -> None:
    service = IdentityService(session)
    raw, _ = await service.issue_token("sam@example.com")

    first = await service.consume_token(raw)
    second = await service.consume_token(raw)

    assert first is not None
    assert second is None, "a consumed link must not work again"


async def test_an_expired_token_is_rejected(session: AsyncSession) -> None:
    service = IdentityService(session)
    raw, token = await service.issue_token("sam@example.com")

    token.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()

    assert await service.consume_token(raw) is None


async def test_tokens_expire_in_fifteen_minutes(session: AsyncSession) -> None:
    """Long enough to switch to a phone and find the email; short enough that a
    link sitting in an inbox for a week is not a standing key (ADR-0009)."""
    service = IdentityService(session)

    _, token = await service.issue_token("sam@example.com")

    lifetime = token.expires_at - datetime.now(UTC)
    assert timedelta(minutes=14) < lifetime <= timedelta(minutes=15)


async def test_an_unknown_token_is_rejected_without_error(session: AsyncSession) -> None:
    """The callback must not distinguish 'never existed' from 'already used'."""
    service = IdentityService(session)

    assert await service.consume_token("a" * 43) is None


async def test_tokens_have_enough_entropy(session: AsyncSession) -> None:
    """A guessable token is a password with none of the protections.

    43 URL-safe characters is 256 bits, which is not brute-forceable within the
    fifteen minutes the token is valid.
    """
    service = IdentityService(session)

    raw_a, _ = await service.issue_token("a@example.com")
    raw_b, _ = await service.issue_token("b@example.com")

    assert len(raw_a) >= 43
    assert raw_a != raw_b
