"""OAuth login: /api/auth/oauth/{42|google}/login redirects to the provider,
which sends the browser back to .../callback; we then open a session and
redirect to the frontend (with ?error=... on the login page when it fails).
"""

import logging

import httpx2
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.db import DbSession
from app.services.oauth import callback_url, fetch_profile, get_client
from app.services.sessions import create_session, set_session_cookie
from app.services.users import EmailAlreadyUsed, get_or_create_oauth_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


def _client_or_404(provider: str):
    client = get_client(provider)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or disabled OAuth provider")
    return client


def _login_error(code: str) -> RedirectResponse:
    return RedirectResponse(f"{get_settings().frontend_url}/login?error={code}", status.HTTP_303_SEE_OTHER)


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request):
    client = _client_or_404(provider)
    return await client.authorize_redirect(request, callback_url(provider))


@router.get("/{provider}/callback")
async def oauth_callback(provider: str, request: Request, db: DbSession):
    client = _client_or_404(provider)
    try:
        token = await client.authorize_access_token(request)
        profile = await fetch_profile(provider, client, token)
    except (OAuthError, httpx2.HTTPError, KeyError, ValueError) as exc:
        # Includes the user pressing "deny" at the provider.
        logger.info("OAuth login with %s failed: %s", provider, type(exc).__name__)
        return _login_error("oauth_failed")

    try:
        user = await get_or_create_oauth_user(db, profile)
    except EmailAlreadyUsed:
        return _login_error("email_in_use")
    except IntegrityError:
        await db.rollback()
        return _login_error("oauth_failed")

    response = RedirectResponse(f"{get_settings().frontend_url}/", status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, await create_session(db, user.id))
    return response
