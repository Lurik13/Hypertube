"""Periodic data upkeep, scheduled by app/worker.py."""

import logging
import shutil
from pathlib import Path

from celery import shared_task
from sqlalchemy import Connection, delete, func, or_, text

from app.config import get_settings
from app.db import get_sync_engine
from app.models import PasswordResetToken, UserSession

logger = logging.getLogger(__name__)


@shared_task(name="cleanup.expired_auth_rows")
def delete_expired_auth_rows() -> dict[str, int]:
    """Delete expired sessions and expired or already-used reset tokens."""
    with get_sync_engine().begin() as conn:
        sessions = conn.execute(delete(UserSession).where(UserSession.expires_at <= func.now())).rowcount
        tokens = conn.execute(
            delete(PasswordResetToken).where(
                or_(PasswordResetToken.expires_at <= func.now(), PasswordResetToken.used_at.is_not(None))
            )
        ).rowcount
    if sessions or tokens:
        logger.info("Deleted %d expired sessions and %d password reset tokens", sessions, tokens)
    return {"sessions": sessions, "password_reset_tokens": tokens}


# Columns the movies table must provide for this job (agreed with the
# movies/streaming task): file_path is relative to MEDIA_ROOT and NULL when
# the movie isn't on the server; last_watched_at is updated on every play.
MOVIES_COLUMNS = ("file_path", "last_watched_at", "created_at")


def _movies_table_ready(conn: Connection) -> bool:
    found = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'movies' AND column_name = ANY(:columns)"
        ),
        {"columns": list(MOVIES_COLUMNS)},
    ).scalars()
    return set(found) == set(MOVIES_COLUMNS)


def _remove_media(media_root: Path, file_path: str) -> bool:
    target = (media_root / file_path).resolve()
    if media_root not in target.parents:
        logger.warning("Not deleting movie file outside MEDIA_ROOT: %s", file_path)
        return False
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink(missing_ok=True)
    return True


@shared_task(name="cleanup.unwatched_movies")
def delete_unwatched_movies() -> int:
    """Delete files of movies unwatched for MOVIE_RETENTION_DAYS and clear their file_path.

    The movie row itself stays (comments and watch history point to it); the
    movie is downloaded again the next time someone plays it.
    """
    settings = get_settings()
    media_root = settings.media_root.resolve()
    removed = 0
    with get_sync_engine().begin() as conn:
        if not _movies_table_ready(conn):
            return 0
        rows = conn.execute(
            text(
                "SELECT id, file_path FROM movies "
                "WHERE file_path IS NOT NULL "
                "AND COALESCE(last_watched_at, created_at) < now() - :days * interval '1 day' "
                "FOR UPDATE SKIP LOCKED"
            ),
            {"days": settings.movie_retention_days},
        ).all()
        for movie_id, file_path in rows:
            if _remove_media(media_root, file_path):
                conn.execute(text("UPDATE movies SET file_path = NULL WHERE id = :id"), {"id": movie_id})
                removed += 1
    if removed:
        logger.info("Deleted %d movies unwatched for %d days", removed, settings.movie_retention_days)
    return removed
