"""Sending the sign-in email.

The link is the credential. Everything here is about making sure it reaches
exactly one inbox and appears nowhere else.
"""

import httpx
import pytest
import respx

from app.identity.email import LoggingSender, ResendSender, build_sender
from app.settings import Settings


def test_without_a_key_the_link_is_logged_not_sent() -> None:
    """Local development and CI must not need a credential.

    A flow that cannot be exercised without production secrets is a flow that
    stops being exercised.
    """
    sender = build_sender(Settings(environment="test"))

    assert isinstance(sender, LoggingSender)


def test_with_a_key_the_real_sender_is_used() -> None:
    sender = build_sender(Settings(environment="test", resend_api_key="re_test_key"))

    assert isinstance(sender, ResendSender)


@respx.mock
async def test_the_email_carries_the_link_and_nothing_else_identifying() -> None:
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(200, json={"id": "msg-1"})
    )
    sender = ResendSender(api_key="re_test_key", sender="CMC <garage@send.example.com>")

    await sender.send_magic_link(
        email="sam@example.com", link="https://example.test/auth/callback?token=abc123"
    )

    assert route.called
    body = route.calls[0].request.content.decode()
    assert "sam@example.com" in body
    assert "https://example.test/auth/callback?token=abc123" in body


@respx.mock
async def test_a_failure_raises_so_the_job_retries() -> None:
    """Swallowing the error would leave the user waiting for an email that is
    never coming, with nothing recorded anywhere to explain it.

    Raising hands the decision to ARQ, which retries and then dead-letters --
    and the dead-letter counter is alerted on.
    """
    respx.post("https://api.resend.com/emails").mock(return_value=httpx.Response(500, json={}))
    sender = ResendSender(api_key="re_test_key", sender="CMC <garage@send.example.com>")

    with pytest.raises(Exception, match="resend"):
        await sender.send_magic_link(email="sam@example.com", link="https://example.test/x")


@respx.mock
async def test_the_api_key_never_appears_in_an_error() -> None:
    """Exceptions end up in logs, in traces, and in the dead-letter list.

    An error message that quotes the request would put the sending credential
    in all three.
    """
    respx.post("https://api.resend.com/emails").mock(
        return_value=httpx.Response(401, json={"message": "invalid key"})
    )
    sender = ResendSender(api_key="re_super_secret_value", sender="CMC <x@y.com>")

    with pytest.raises(Exception) as caught:
        await sender.send_magic_link(email="sam@example.com", link="https://example.test/x")

    assert "re_super_secret_value" not in str(caught.value)


def test_the_logging_sender_prints_the_link() -> None:
    """In development the log *is* the inbox.

    Withholding the link here would mean nobody can sign in locally without a
    mail provider, and a flow that cannot be exercised stops being exercised.
    """
    import asyncio
    import io

    import structlog

    from app.logging import configure_logging

    buffer = io.StringIO()
    configure_logging(Settings(environment="test", log_format="json"), stream=buffer)
    sender = LoggingSender()

    asyncio.run(
        sender.send_magic_link(
            email="sam@example.com", link="https://example.test/auth/callback?token=DEVTOKEN"
        )
    )

    assert "DEVTOKEN" in buffer.getvalue()
    structlog.reset_defaults()


def test_production_without_a_key_refuses_to_build_a_sender() -> None:
    """The dangerous case is not logging links in development.

    It is *silently* logging them in production, where the user waits for an
    email that was never sent and a live sign-in link sits in log storage that
    is shipped to a third party and retained for weeks. A missing key in
    production is a configuration error and should read as one.
    """
    with pytest.raises(RuntimeError, match="CMC_RESEND_API_KEY"):
        build_sender(Settings(environment="prod", log_format="json"))
