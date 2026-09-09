"""Authentication endpoints."""

import structlog
from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from app import metrics as app_metrics
from app.identity.service import IdentityService, SessionService
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


class SessionRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


@router.post("/session", summary="Exchange a sign-in link for a session")
async def create_session(
    payload: SessionRequest, request: Request, response: Response
) -> dict[str, str]:
    """Spend the link and sign the browser in.

    A POST, not a GET on the link itself. Mail scanners prefetch URLs, and a
    GET that consumed the token would let a scanner spend it before the user
    ever clicked -- which presents as "this link has expired" seconds after it
    arrived.
    """
    settings = request.app.state.settings
    database = request.app.state.database

    async with database.session() as session:
        user = await IdentityService(session).consume_token(payload.token)
        if user is None:
            # One response for expired, already used, never existed and
            # tampered with. Distinguishing them tells an attacker which tokens
            # once existed, and none of the four changes what the user does.
            raise HTTPException(status_code=401, detail="This link cannot be used")
        raw_session, record = await SessionService(session).create(user.id)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_session,
        max_age=int((record.expires_at - record.created_at).total_seconds())
        if record.created_at
        else 30 * 24 * 3600,
        # HttpOnly keeps it away from JavaScript, so an XSS bug cannot read it.
        httponly=True,
        # Lax stops another site's form from acting as this user, while still
        # allowing the ordinary top-level navigation that arrives from email.
        samesite="lax",
        secure=settings.session_cookie_secure,
        path=settings.session_cookie_path,
    )
    # The token is in the cookie and nowhere else. Returning it in the body
    # would put it within reach of JavaScript, which is what HttpOnly exists
    # to prevent.
    return {"status": "signed_in"}


@router.get("/me", summary="The signed-in user")
async def me(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=401, detail="Not signed in")

    async with request.app.state.database.session() as session:
        user = await SessionService(session).resolve(raw)

    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return {"id": str(user.id), "email": user.email}


@router.delete("/session", status_code=204, summary="Sign out")
async def delete_session(request: Request, response: Response) -> Response:
    """End the session.

    Revokes server-side rather than only clearing the cookie: a cleared cookie
    leaves a valid session behind, usable by anyone who captured it and
    impossible to end from a device you no longer have. This is what sessions
    being rows is for.

    Always 204. Signing out twice, or with a cookie that already expired, is
    ordinary rather than exceptional -- and a sign-out that can fail is a
    sign-out people stop trusting.
    """
    settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie_name)

    if raw:
        async with request.app.state.database.session() as session:
            await SessionService(session).revoke(raw)

    # Cleared on the same path it was set on. A mismatch leaves the original
    # cookie in place and the browser still believes it is signed in.
    response.delete_cookie(
        key=settings.session_cookie_name,
        path=settings.session_cookie_path,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
    response.status_code = 204
    return response
