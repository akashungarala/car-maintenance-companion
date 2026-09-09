"""The job that sends the sign-in email."""

from typing import Any

import pytest

from app.tasks import send_magic_link_email
from tests.conftest import points_for


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_magic_link(self, *, email: str, link: str) -> None:
        self.sent.append({"email": email, "link": link})


class FailingSender:
    async def send_magic_link(self, *, email: str, link: str) -> None:
        raise RuntimeError("resend is unavailable")


async def test_the_link_is_built_from_the_base_url_and_token() -> None:
    """The API cannot infer the browser's URL.

    It is reached through Cloudflare, Traefik and a path prefix, so a link
    built from the incoming request would point somewhere unreachable.
    """
    sender = RecordingSender()

    await send_magic_link_email(
        {"job_id": "j1"},
        email="sam@example.com",
        token="tok-123",
        base_url="https://example.test/apps/cmc",
        sender=sender,
    )

    assert sender.sent[0]["link"] == "https://example.test/apps/cmc/auth/callback?token=tok-123"
    assert sender.sent[0]["email"] == "sam@example.com"


async def test_a_trailing_slash_does_not_produce_a_double_slash() -> None:
    sender = RecordingSender()

    await send_magic_link_email(
        {"job_id": "j1"},
        email="sam@example.com",
        token="tok",
        base_url="https://example.test/",
        sender=sender,
    )

    assert sender.sent[0]["link"] == "https://example.test/auth/callback?token=tok"


async def test_a_send_failure_propagates(metric_reader: Any) -> None:
    """ARQ owns retry and dead-lettering. Swallowing the error here would leave
    the user waiting for an email that is never coming, with nothing recorded
    to explain it."""
    with pytest.raises(RuntimeError):
        await send_magic_link_email(
            {"job_id": "j1"},
            email="sam@example.com",
            token="tok",
            base_url="https://example.test",
            sender=FailingSender(),
        )


async def test_sent_emails_are_counted(metric_reader: Any) -> None:
    """Login mail and the weekly digests share one 100/day allowance.

    Without a count there is no way to know which is consuming it, and the
    first sign that it ran out is people being unable to sign in.
    """
    before = sum(p.value for p in points_for(metric_reader, "email.sent"))

    await send_magic_link_email(
        {"job_id": "j1"},
        email="sam@example.com",
        token="tok",
        base_url="https://example.test",
        sender=RecordingSender(),
    )

    after = sum(p.value for p in points_for(metric_reader, "email.sent"))
    assert after == before + 1


async def test_the_token_is_not_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """The job payload contains a live credential.

    A job that logs its own arguments -- which is a very ordinary thing to add
    while debugging -- would put working sign-in links in log storage.
    """
    await send_magic_link_email(
        {"job_id": "j1"},
        email="sam@example.com",
        token="SECRET-TOKEN-VALUE",
        base_url="https://example.test",
        sender=RecordingSender(),
    )

    assert "SECRET-TOKEN-VALUE" not in capsys.readouterr().out
