"""ORM models for the tables owned by authentication.

The schema is defined by the Alembic migrations in alembic/versions/; these
models mirror it. Feature tasks add their own models next to these.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, LargeBinary, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _id() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


def _timestamp() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _user_fk() -> Mapped[int]:
    return mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = _id()
    email: Mapped[str] = mapped_column(String(254))
    username: Mapped[str] = mapped_column(String(30))
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    # argon2id hash; None for OAuth-only accounts that never set a password.
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _timestamp()
    # Kept current by the set_updated_at() trigger.
    updated_at: Mapped[datetime] = _timestamp()


Index("users_email_lower_key", func.lower(User.email), unique=True)
Index("users_username_lower_key", func.lower(User.username), unique=True)


class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = _id()
    user_id: Mapped[int] = _user_fk()
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    created_at: Mapped[datetime] = _timestamp()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = _id()
    user_id: Mapped[int] = _user_fk()
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    created_at: Mapped[datetime] = _timestamp()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[int] = _id()
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = _timestamp()
