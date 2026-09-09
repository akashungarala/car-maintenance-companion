"""Resolving the signed-in user for a request."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.identity.models import User
from app.identity.service import SessionService


async def require_user(request: Request) -> User:
    """The signed-in user, or 401.

    A dependency rather than middleware: middleware would have to know which
    routes are public, and that list is exactly the thing people forget to
    update. Here, a route is protected because it says so in its signature.
    """
    settings = request.app.state.settings
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise HTTPException(status_code=401, detail="Not signed in")

    async with request.app.state.database.session() as session:
        user = await SessionService(session).resolve(raw)

    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
