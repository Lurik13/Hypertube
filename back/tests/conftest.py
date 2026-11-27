"""Tests run against the real PostgreSQL test database (`make test`)."""

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db import async_engine, get_sync_engine
from app.main import app

STRONG_PASSWORD = "Sup3r-secret!"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config("alembic.ini")
    config.attributes["configure_logger"] = False
    # Up, down, up: every migration's downgrade must undo its upgrade.
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def clean_database():
    yield
    await async_engine.dispose()
    with get_sync_engine().begin() as conn:
        conn.execute(text("TRUNCATE users, sessions, password_reset_tokens, oauth_accounts RESTART IDENTITY CASCADE"))


@pytest.fixture
async def client():
    # https so the client sends back Secure cookies.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as client:
        yield client


@pytest.fixture
def outbox(monkeypatch):
    """Captures password reset emails instead of sending them."""
    sent = []

    async def fake_send(to: str, first_name: str, link: str) -> None:
        sent.append({"to": to, "first_name": first_name, "link": link})

    monkeypatch.setattr("app.routers.auth.send_password_reset_email", fake_send)
    return sent


def registration(**overrides) -> dict:
    body = {
        "email": "jane@example.com",
        "username": "jane",
        "first_name": "Jane",
        "last_name": "Doe",
        "password": STRONG_PASSWORD,
    }
    return body | overrides
