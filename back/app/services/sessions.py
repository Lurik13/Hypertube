"""Server-side sessions: the cookie holds a random token, the DB only its hash."""

from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, UserSession
from app.security import hash_token, new_token

# token_urlsafe(32) is 43 characters; anything much longer is not ours.
_MAX_TOKEN_LENGTH = 128


async def create_session(db: AsyncSession, user_id: int) -> str:
    token, token_hash = new_token()
    expires_at = datetime.now(UTC) + timedelta(hours=get_settings().session_ttl_hours)
    db.add(UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()
    return token


async def get_session_user(db: AsyncSession, token: str) -> User | None:
    if len(token) > _MAX_TOKEN_LENGTH:
        return None
    return await db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(UserSession.token_hash == hash_token(token), UserSession.expires_at > func.now())
    )


async def delete_session(db: AsyncSession, token: str) -> None:
    await db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
    await db.commit()


async def delete_user_sessions(db: AsyncSession, user_id: int) -> None:
    """Log the user out everywhere. The caller commits."""
    await db.execute(delete(UserSession).where(UserSession.user_id == user_id))


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
