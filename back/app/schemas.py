"""Request and response bodies. Every field is validated server-side here."""

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, StringConstraints, ValidationInfo, field_validator

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
_USERNAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
NAME_EXTRA_CHARS = " '-"


def check_username(value: str) -> str:
    if not _USERNAME_RE.fullmatch(value):
        raise ValueError("Username may only contain letters, digits, '.', '_' and '-'")
    return value


def check_name(value: str) -> str:
    if not all(c.isalpha() or c in NAME_EXTRA_CHARS for c in value):
        raise ValueError("Name may only contain letters, spaces, apostrophes and hyphens")
    return value


def check_password_strength(value: str) -> str:
    missing = []
    if not any(c.islower() for c in value):
        missing.append("a lowercase letter")
    if not any(c.isupper() for c in value):
        missing.append("an uppercase letter")
    if not any(c.isdigit() for c in value):
        missing.append("a digit")
    if all(c.isalnum() for c in value):
        missing.append("a special character")
    if missing:
        raise ValueError("Password must contain " + ", ".join(missing))
    return value


def password_contains_username(password: str, username: str) -> bool:
    return username.lower() in password.lower()


Username = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=30), AfterValidator(check_username)
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50), AfterValidator(check_name)]
NewPassword = Annotated[
    str,
    StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
    AfterValidator(check_password_strength),
]


class _Form(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(_Form):
    email: EmailStr
    username: Username
    first_name: Name
    last_name: Name
    password: NewPassword

    @field_validator("password")
    @classmethod
    def _password_not_username(cls, value: str, info: ValidationInfo) -> str:
        username = info.data.get("username")
        if username and password_contains_username(value, username):
            raise ValueError("Password must not contain your username")
        return value


class LoginIn(_Form):
    # Only presence and size are checked: strength rules apply when a password is set.
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class ForgotPasswordIn(_Form):
    email: EmailStr


class ResetPasswordIn(_Form):
    token: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    password: NewPassword


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    created_at: datetime


class Message(BaseModel):
    detail: str
