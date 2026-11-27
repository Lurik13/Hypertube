import logging
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text

from app.config import get_settings
from app.db import get_sync_engine
from app.security import hash_token
from tests.conftest import STRONG_PASSWORD, registration

COOKIE = get_settings().session_cookie_name


def db_rows(sql: str, **params):
    with get_sync_engine().connect() as conn:
        return conn.execute(text(sql), params).all()


async def test_register_logs_in_and_me_returns_user(client):
    response = await client.post("/api/auth/register", json=registration())
    assert response.status_code == 201
    assert response.json()["username"] == "jane"
    assert "password" not in response.text

    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "jane@example.com"


async def test_session_cookie_is_secure_and_httponly(client):
    response = await client.post("/api/auth/register", json=registration())
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie


async def test_password_and_session_token_are_stored_hashed(client):
    await client.post("/api/auth/register", json=registration())
    [(password_hash,)] = db_rows("SELECT password_hash FROM users")
    assert password_hash.startswith("$argon2id$")
    assert STRONG_PASSWORD not in password_hash

    token = client.cookies[COOKIE]
    [(token_hash,)] = db_rows("SELECT token_hash FROM sessions")
    assert bytes(token_hash) == hash_token(token)
    assert token.encode() not in bytes(token_hash)


async def test_register_validates_every_field(client):
    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "username": "a!", "first_name": "", "password": "weakpass"},
    )
    assert response.status_code == 422
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"email", "username", "first_name", "last_name", "password"}
    # The submitted password is never echoed back.
    assert "weakpass" not in response.text


async def test_register_rejects_password_containing_username(client):
    response = await client.post("/api/auth/register", json=registration(password="Jane-1234!"))
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "password"


async def test_register_rejects_duplicate_email_and_username_case_insensitively(client):
    await client.post("/api/auth/register", json=registration())
    response = await client.post(
        "/api/auth/register", json=registration(email="JANE@example.com", username="JANE")
    )
    assert response.status_code == 409
    assert {error["field"] for error in response.json()["errors"]} == {"email", "username"}


async def test_login_and_logout(client):
    await client.post("/api/auth/register", json=registration())
    client.cookies.clear()

    response = await client.post("/api/auth/login", json={"username": "Jane", "password": STRONG_PASSWORD})
    assert response.status_code == 200
    token = client.cookies[COOKIE]
    assert (await client.get("/api/me")).status_code == 200

    response = await client.post("/api/auth/logout")
    assert response.status_code == 204
    assert (await client.get("/api/me")).status_code == 401
    # The session is deleted server-side: replaying the old cookie doesn't work.
    client.cookies.set(COOKIE, token)
    assert (await client.get("/api/me")).status_code == 401


async def test_wrong_credentials_do_not_reveal_which_part_was_wrong(client):
    await client.post("/api/auth/register", json=registration())
    client.cookies.clear()

    wrong_password = await client.post("/api/auth/login", json={"username": "jane", "password": "Wrong-pass1"})
    unknown_user = await client.post("/api/auth/login", json={"username": "nobody", "password": "Wrong-pass1"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json() == {"detail": "Invalid username or password", "errors": []}


async def test_login_requires_fields(client):
    response = await client.post("/api/auth/login", json={"username": ""})
    assert response.status_code == 422
    assert {error["field"] for error in response.json()["errors"]} == {"username", "password"}


async def test_protected_route_returns_401_when_logged_out(client):
    assert (await client.get("/api/me")).status_code == 401
    client.cookies.set(COOKIE, "forged-token")
    response = await client.get("/api/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"]


async def test_expired_session_is_rejected(client):
    await client.post("/api/auth/register", json=registration())
    with get_sync_engine().begin() as conn:
        conn.execute(text("UPDATE sessions SET expires_at = now() - interval '1 second'"))
    assert (await client.get("/api/me")).status_code == 401


async def test_forgot_password_does_not_reveal_unknown_email(client, outbox):
    await client.post("/api/auth/register", json=registration())
    known = await client.post("/api/auth/password/forgot", json={"email": "jane@example.com"})
    unknown = await client.post("/api/auth/password/forgot", json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [mail["to"] for mail in outbox] == ["jane@example.com"]


async def test_reset_password_flow(client, outbox):
    await client.post("/api/auth/register", json=registration())
    await client.post("/api/auth/password/forgot", json={"email": "jane@example.com"})
    link = outbox[0]["link"]
    assert link.startswith(f"{get_settings().frontend_url}/reset-password?token=")
    token = parse_qs(urlparse(link).query)["token"][0]
    [(stored,)] = db_rows("SELECT token_hash FROM password_reset_tokens")
    assert bytes(stored) == hash_token(token)

    new_password = "N3w-password!"
    response = await client.post("/api/auth/password/reset", json={"token": token, "password": new_password})
    assert response.status_code == 204
    # Every existing session was revoked.
    assert (await client.get("/api/me")).status_code == 401

    # Single use.
    again = await client.post("/api/auth/password/reset", json={"token": token, "password": "An0ther-pass!"})
    assert again.status_code == 400

    old = await client.post("/api/auth/login", json={"username": "jane", "password": STRONG_PASSWORD})
    new = await client.post("/api/auth/login", json={"username": "jane", "password": new_password})
    assert old.status_code == 401
    assert new.status_code == 200


async def test_new_reset_link_invalidates_the_previous_one(client, outbox):
    await client.post("/api/auth/register", json=registration())
    await client.post("/api/auth/password/forgot", json={"email": "jane@example.com"})
    await client.post("/api/auth/password/forgot", json={"email": "jane@example.com"})
    first, second = (parse_qs(urlparse(mail["link"]).query)["token"][0] for mail in outbox)

    stale = await client.post("/api/auth/password/reset", json={"token": first, "password": "N3w-password!"})
    fresh = await client.post("/api/auth/password/reset", json={"token": second, "password": "N3w-password!"})
    assert stale.status_code == 400
    assert fresh.status_code == 204


async def test_expired_reset_token_is_rejected(client, outbox):
    await client.post("/api/auth/register", json=registration())
    await client.post("/api/auth/password/forgot", json={"email": "jane@example.com"})
    token = parse_qs(urlparse(outbox[0]["link"]).query)["token"][0]
    with get_sync_engine().begin() as conn:
        conn.execute(text("UPDATE password_reset_tokens SET expires_at = now() - interval '1 second'"))

    response = await client.post("/api/auth/password/reset", json={"token": token, "password": "N3w-password!"})
    assert response.status_code == 400


async def test_reset_validates_password_strength(client):
    response = await client.post("/api/auth/password/reset", json={"token": "x", "password": "short"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "password"


async def test_passwords_never_reach_the_logs(client, outbox, caplog):
    caplog.set_level(logging.DEBUG)
    await client.post("/api/auth/register", json=registration())
    await client.post("/api/auth/login", json={"username": "jane", "password": "Wrong-pass1"})
    await client.post("/api/auth/login", json={"username": "jane", "password": STRONG_PASSWORD})
    await client.post("/api/auth/register", json=registration(password="weakpass"))
    for secret in (STRONG_PASSWORD, "Wrong-pass1", "weakpass"):
        assert secret not in caplog.text


async def test_unknown_route_returns_404(client):
    assert (await client.get("/api/does-not-exist")).status_code == 404
