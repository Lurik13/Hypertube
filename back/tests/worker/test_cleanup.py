import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db import get_sync_engine
from app.jobs.cleanup import delete_expired_auth_rows, delete_unwatched_movies
from app.seed import SEED_USERS, main as seed


def execute(sql: str, **params):
    with get_sync_engine().begin() as conn:
        return conn.execute(text(sql), params)


@pytest.fixture
def user_id() -> int:
    return execute(
        "INSERT INTO users (email, username, first_name, last_name) "
        "VALUES ('a@example.com', 'alice', 'Alice', 'A') RETURNING id"
    ).scalar_one()


def test_expired_sessions_and_reset_tokens_are_deleted(user_id):
    execute(
        "INSERT INTO sessions (user_id, token_hash, expires_at) VALUES "
        "(:u, 'expired', now() - interval '1 minute'), (:u, 'valid', now() + interval '1 hour')",
        u=user_id,
    )
    execute(
        "INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used_at) VALUES "
        "(:u, 'expired', now() - interval '1 minute', NULL), "
        "(:u, 'used', now() + interval '1 hour', now()), "
        "(:u, 'valid', now() + interval '1 hour', NULL)",
        u=user_id,
    )

    assert delete_expired_auth_rows() == {"sessions": 1, "password_reset_tokens": 2}
    assert execute("SELECT convert_from(token_hash, 'UTF8') FROM sessions").scalars().all() == ["valid"]
    assert execute("SELECT convert_from(token_hash, 'UTF8') FROM password_reset_tokens").scalars().all() == ["valid"]


def test_movie_cleanup_waits_for_the_movies_table():
    assert delete_unwatched_movies() == 0


@pytest.fixture
def movies_table(tmp_path, monkeypatch):
    """Stand-in for the movies table, with only the columns the job relies on."""
    monkeypatch.setattr(get_settings(), "media_root", tmp_path)
    execute(
        "CREATE TABLE movies (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, file_path TEXT, "
        "last_watched_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    yield tmp_path
    execute("DROP TABLE movies")


def test_unwatched_movies_lose_their_files(movies_table):
    media = movies_table
    (media / "old").mkdir()
    (media / "old" / "movie.mp4").write_bytes(b"x")
    (media / "recent.mp4").write_bytes(b"x")
    (media.parent / "outside.mp4").write_bytes(b"x")
    execute(
        "INSERT INTO movies (file_path, last_watched_at) VALUES "
        "('old', now() - interval '31 days'), "
        "('recent.mp4', now() - interval '2 days'), "
        "('../outside.mp4', now() - interval '31 days')"
    )

    assert delete_unwatched_movies() == 1
    assert not (media / "old").exists()
    assert (media / "recent.mp4").exists()
    assert (media.parent / "outside.mp4").exists()
    assert execute("SELECT file_path FROM movies ORDER BY id").scalars().all() == [
        None,
        "recent.mp4",
        "../outside.mp4",
    ]


def test_seed_is_idempotent():
    seed()
    seed()
    assert execute("SELECT count(*) FROM users").scalar_one() == len(SEED_USERS)
