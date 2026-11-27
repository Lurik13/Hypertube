"""Account endpoints: register, login, logout and password reset by email."""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import DbSession
from app.errors import FormError
from app.mail import send_password_reset_email
from app.models import User
from app.schemas import ForgotPasswordIn, LoginIn, Message, RegisterIn, ResetPasswordIn, UserOut, password_contains_username
from app.security import hash_password, password_needs_rehash, verify_password
from app.services.password_reset import create_reset_token, get_valid_reset_token
from app.services.sessions import (
    clear_session_cookie,
    create_session,
    delete_session,
    delete_user_sessions,
    set_session_cookie,
)
from app.services.users import find_conflicts, get_by_email, get_by_username

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def register(body: RegisterIn, response: Response, db: DbSession) -> User:
    """Create an account and log it in."""
    conflicts = await find_conflicts(db, body.email, body.username)
    if conflicts:
        raise FormError(status.HTTP_409_CONFLICT, "Account already exists", conflicts)

    user = User(
        email=body.email,
        username=body.username,
        first_name=body.first_name,
        last_name=body.last_name,
        password_hash=await run_in_threadpool(hash_password, body.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Lost a race with a concurrent registration of the same email/username.
        await db.rollback()
        raise FormError(status.HTTP_409_CONFLICT, "Account already exists") from None

    set_session_cookie(response, await create_session(db, user.id))
    return user


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response, db: DbSession) -> User:
    user = await get_by_username(db, body.username)
    password_hash = user.password_hash if user else None
    if user is None or not await run_in_threadpool(verify_password, password_hash, body.password):
        # Same answer (and timing) for an unknown username and a wrong password.
        raise FormError(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    if password_needs_rehash(user.password_hash):
        user.password_hash = await run_in_threadpool(hash_password, body.password)
    set_session_cookie(response, await create_session(db, user.id))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(request: Request, response: Response, db: DbSession) -> None:
    token = request.cookies.get(get_settings().session_cookie_name)
    if token:
        await delete_session(db, token)
    clear_session_cookie(response)


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED, response_model=Message)
async def forgot_password(body: ForgotPasswordIn, background_tasks: BackgroundTasks, db: DbSession) -> Message:
    """Email a reset link. The answer never says whether the email is registered."""
    user = await get_by_email(db, body.email)
    if user:
        token = await create_reset_token(db, user.id)
        link = f"{get_settings().frontend_url}/reset-password?token={token}"
        background_tasks.add_task(send_password_reset_email, user.email, user.first_name, link)
    return Message(detail="If an account exists for this email, a reset link has been sent.")


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def reset_password(body: ResetPasswordIn, db: DbSession) -> None:
    """Set a new password from an emailed token, then log out every session."""
    reset = await get_valid_reset_token(db, body.token)
    if reset is None:
        raise FormError(
            status.HTTP_400_BAD_REQUEST,
            "This reset link is invalid or has expired",
            {"token": "Ask for a new reset link"},
        )
    user = await db.get(User, reset.user_id)
    if password_contains_username(body.password, user.username):
        raise FormError(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Invalid input", {"password": "Password must not contain your username"}
        )

    user.password_hash = await run_in_threadpool(hash_password, body.password)
    reset.used_at = datetime.now(UTC)
    await delete_user_sessions(db, user.id)
    await db.commit()
