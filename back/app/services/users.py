"""User lookups and creation, including accounts coming from OAuth providers."""

import re
import secrets
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthAccount, User
from app.schemas import NAME_EXTRA_CHARS


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    return await db.scalar(select(User).where(func.lower(User.username) == username.lower()))


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(func.lower(User.email) == email.lower()))


async def find_conflicts(db: AsyncSession, email: str, username: str) -> dict[str, str]:
    """Field errors for an email or username already in use (case-insensitive)."""
    errors = {}
    if await get_by_email(db, email):
        errors["email"] = "This email is already in use"
    if await get_by_username(db, username):
        errors["username"] = "This username is already taken"
    return errors


@dataclass(frozen=True)
class OAuthProfile:
    provider: str
    subject: str
    email: str
    email_verified: bool
    username_hint: str
    first_name: str
    last_name: str


class EmailAlreadyUsed(Exception):
    """The provider email belongs to another account and can't be safely linked."""


def _clean_name(value: str) -> str:
    return "".join(c for c in value if c.isalpha() or c in NAME_EXTRA_CHARS).strip()[:50]


async def _available_username(db: AsyncSession, hint: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]", "", hint)[:23]
    if len(base) < 3:
        base = f"user{base}"
    candidate = base
    while await get_by_username(db, candidate):
        candidate = f"{base}{secrets.randbelow(10**6):06d}"
    return candidate


async def get_or_create_oauth_user(db: AsyncSession, profile: OAuthProfile) -> User:
    """Return the user linked to this provider identity, linking or creating one.

    An existing account is linked by email only when the provider vouches for
    the address; otherwise anyone could take over an account by registering
    its email at the provider.
    """
    user = await db.scalar(
        select(User)
        .join(OAuthAccount, OAuthAccount.user_id == User.id)
        .where(OAuthAccount.provider == profile.provider, OAuthAccount.provider_user_id == profile.subject)
    )
    if user:
        return user

    user = await get_by_email(db, profile.email)
    if user and not profile.email_verified:
        raise EmailAlreadyUsed
    if user is None:
        user = User(
            email=profile.email,
            username=await _available_username(db, profile.username_hint),
            first_name=_clean_name(profile.first_name),
            last_name=_clean_name(profile.last_name),
            password_hash=None,
        )
        db.add(user)
        await db.flush()
    db.add(OAuthAccount(user_id=user.id, provider=profile.provider, provider_user_id=profile.subject))
    await db.commit()
    return user
