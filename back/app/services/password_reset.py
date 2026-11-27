"""Single-use, expiring password reset tokens. Only their hash is stored."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PasswordResetToken
from app.security import hash_token, new_token


async def create_reset_token(db: AsyncSession, user_id: int) -> str:
    """Issue a new token; any earlier unused token for this user stops working."""
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    token, token_hash = new_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_ttl_minutes)
    db.add(PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
    await db.commit()
    return token


async def get_valid_reset_token(db: AsyncSession, token: str) -> PasswordResetToken | None:
    """Unused, unexpired token row, locked so two concurrent resets can't both use it."""
    return await db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > func.now(),
        )
        .with_for_update()
    )
