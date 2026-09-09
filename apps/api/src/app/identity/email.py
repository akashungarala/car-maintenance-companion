"""Delivering the sign-in link.

Two senders. The real one talks to Resend; the other writes the link to the log
so development and CI need no credential. Which one is used is decided by
configuration, and getting that decision wrong in production is made loud
rather than silent.
"""

from typing import Protocol

import httpx
import structlog

from app.settings import Settings

logger = structlog.get_logger()

RESEND_ENDPOINT = "https://api.resend.com/emails"

SUBJECT = "Your sign-in link"

TEXT_BODY = """Sign in to your garage

Click the link below. It works once and expires in 15 minutes.

{link}

If you did not ask to sign in, ignore this email -- the link cannot be used
without it, and nobody has access to your account.
"""


class EmailSender(Protocol):
    async def send_magic_link(self, *, email: str, link: str) -> None: ...


class LoggingSender:
    """Writes the link to the log instead of sending it.

    The log *is* the inbox in development. Withholding the link would mean
    nobody can sign in locally without a mail provider, and a flow that cannot
    be exercised stops being exercised.
    """

    async def send_magic_link(self, *, email: str, link: str) -> None:
        logger.info("magic_link_not_sent_logged_instead", link=link)


class ResendSender:
    def __init__(self, *, api_key: str, sender: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._sender = sender
        self._timeout = timeout

    async def send_magic_link(self, *, email: str, link: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._sender,
                    "to": [email],
                    "subject": SUBJECT,
                    "text": TEXT_BODY.format(link=link),
                },
            )

        if response.status_code >= 400:
            # Deliberately narrow: the status code and Resend's own message,
            # never the request. Exceptions reach logs, traces and the
            # dead-letter list, and quoting the request would put the sending
            # credential -- and the sign-in link -- in all three.
            detail = ""
            try:
                detail = str(response.json().get("message", ""))[:200]
            except Exception:  # a non-JSON error body is still an error
                detail = ""
            raise RuntimeError(f"resend rejected the message: HTTP {response.status_code} {detail}")


def build_sender(settings: Settings) -> EmailSender:
    if settings.resend_api_key:
        return ResendSender(api_key=settings.resend_api_key, sender=settings.email_from)

    if settings.environment == "prod":
        # Not a fallback. Silently logging links in production means the user
        # waits for an email that was never sent, while a live sign-in link
        # sits in log storage that is shipped to a third party and kept for
        # weeks. A missing key is a configuration error and should read as one.
        raise RuntimeError(
            "CMC_RESEND_API_KEY is not set. Refusing to fall back to logging "
            "sign-in links in production."
        )

    logger.warning("email_sender_is_logging_only", environment=settings.environment)
    return LoggingSender()
