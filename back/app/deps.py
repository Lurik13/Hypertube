"""Authentication dependencies.

- load_user: resolves the session cookie to a User, or None (LoadUser).
- require_auth: same, but answers 401 when nobody is logged in (RequireAuth).

Protect a single route with a `user: CurrentUser` parameter, or a whole router
with `APIRouter(dependencies=[Depends(require_auth)])`.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.config import get_settings
from app.db import DbSession
from app.models import User
from app.services.sessions import get_session_user


async def load_user(request: Request, db: DbSession) -> User | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    return await get_session_user(db, token)


OptionalUser = Annotated[User | None, Depends(load_user)]


async def require_auth(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Cookie realm="hypertube"'},
        )
    return user


CurrentUser = Annotated[User, Depends(require_auth)]
