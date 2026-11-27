"""Password hashing (argon2id) and opaque token generation.

argon2 is deliberately slow: call hash_password / verify_password through
starlette's run_in_threadpool from async code so the event loop never blocks.
"""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified against when the username doesn't exist, so a failed login takes the
# same time whether the username or the password was wrong.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def hash_token(token: str) -> bytes:
    """SHA-256 is enough here: tokens are 256-bit random values, not passwords."""
    return hashlib.sha256(token.encode()).digest()


def new_token() -> tuple[str, bytes]:
    """Return (raw token for the client, hash to store in the database)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)
