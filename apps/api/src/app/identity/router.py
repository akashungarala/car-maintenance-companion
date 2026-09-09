"""Authentication endpoints."""

import structlog
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app import metrics as app_metrics
from app.identity.service import IdentityService
from app.queue import enqueue_magic_link_email

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["authentication"])


class MagicLinkRequest(BaseModel):
    # EmailStr validates the shape and rejects the obvious nonsense before any
    # work happens. It does not confirm the address exists -- nothing can,
    # short of sending to it, which is the entire point of the flow.
    email: EmailStr


@router.post(
    "/magic-link",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a sign-in link",
    response_description="Always accepted, whether or not the address has an account",
)
async def request_magic_link(payload: MagicLinkRequest, request: Request) -> JSONResponse:
    """Send a sign-in link to an address.

    Returns 202 for every well-formed address, registered or not. Anything else
    turns this endpoint into a way to discover who has an account: an attacker
    submits a list of addresses and reads the answers off the status codes.

    202 rather than 200 is literal: the work has been accepted, not completed.
    The email is sent by the worker, so holding the request open until an
    external mail API answered would make sign-in latency -- and then sign-in
    availability -- a function of Resend's.
    """
    settings = request.app.state.settings
    database = request.app.state.database

    async with database.session() as session:
        raw_token, _ = await IdentityService(session).issue_token(payload.email)

    await enqueue_magic_link_email(
        request.app.state.queue,
        email=IdentityService.normalise_email(payload.email),
        token=raw_token,
        base_url=settings.app_base_url,
    )
    app_metrics.record_magic_link_requested()

    # No token, no user id, nothing that varies with whether the account
    # exists. The body is a constant.
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted"},
    )
