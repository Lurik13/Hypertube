from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import SecretStr

from app.config import get_settings
from app.db import SessionLocal
from app.services.oauth import register_providers
from app.services.users import EmailAlreadyUsed, OAuthProfile, get_or_create_oauth_user
from tests.conftest import registration


def profile(**overrides) -> OAuthProfile:
    values = {
        "provider": "42",
        "subject": "12345",
        "email": "jdoe@student.42.fr",
        "email_verified": True,
        "username_hint": "jdoe",
        "first_name": "John",
        "last_name": "Doe",
    }
    return OAuthProfile(**(values | overrides))


async def test_unknown_provider_returns_404(client):
    assert (await client.get("/api/auth/oauth/github/login")).status_code == 404


async def test_login_redirects_to_the_42_authorize_page(client):
    settings = get_settings().model_copy(
        update={"fortytwo_client_id": "test-client", "fortytwo_client_secret": SecretStr("test-secret")}
    )
    register_providers(settings)

    response = await client.get("/api/auth/oauth/42/login")
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert location.netloc == "api.intra.42.fr"
    assert query["client_id"] == ["test-client"]
    assert query["redirect_uri"] == [f"{settings.public_api_url}/api/auth/oauth/42/callback"]
    assert query["state"]


async def test_callback_without_valid_state_redirects_to_login_error(client):
    register_providers(
        get_settings().model_copy(update={"fortytwo_client_id": "test-client", "fortytwo_client_secret": SecretStr("s")})
    )
    response = await client.get("/api/auth/oauth/42/callback?code=abc&state=forged")
    assert response.status_code == 303
    assert response.headers["location"].endswith("/login?error=oauth_failed")


async def test_oauth_user_is_created_once_then_found_again():
    async with SessionLocal() as db:
        first = await get_or_create_oauth_user(db, profile())
        again = await get_or_create_oauth_user(db, profile(email="changed@student.42.fr"))
    assert first.id == again.id
    assert first.username == "jdoe"
    assert first.password_hash is None


async def test_oauth_username_is_made_unique(client):
    await client.post("/api/auth/register", json=registration(username="jdoe", email="other@example.com"))
    async with SessionLocal() as db:
        user = await get_or_create_oauth_user(db, profile())
    assert user.username.startswith("jdoe")
    assert user.username != "jdoe"


async def test_verified_email_links_to_the_existing_account(client):
    created = (await client.post("/api/auth/register", json=registration(email="jdoe@student.42.fr"))).json()
    async with SessionLocal() as db:
        user = await get_or_create_oauth_user(db, profile(provider="google", subject="g-1"))
    assert user.id == created["id"]


async def test_unverified_email_never_takes_over_an_existing_account(client):
    await client.post("/api/auth/register", json=registration(email="jdoe@gmail.com"))
    async with SessionLocal() as db:
        with pytest.raises(EmailAlreadyUsed):
            await get_or_create_oauth_user(
                db, profile(provider="google", subject="g-2", email="jdoe@gmail.com", email_verified=False)
            )
