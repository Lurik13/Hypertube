"""PostgreSQL persistence for torrent jobs and subtitle records.

The repository owns SQL details while returning ordinary Python dictionaries to
the application layer. This keeps API and torrent-engine code independent of
the PostgreSQL driver's row and connection types.
"""

import json
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from app.config import Settings


_UNSET = object()


def _now() -> str:
    """Return a sortable UTC timestamp used for job and subtitle updates."""
    return datetime.now(timezone.utc).isoformat()


class Repository:
    """Persist torrent state using short-lived PostgreSQL connections."""

    def __init__(self, settings: Settings, *, schema: str = "public") -> None:
        """Bind the repository to configured credentials and initialize tables.

        ``schema`` is an internal option used by tests to isolate each test
        suite's tables. Application instances use PostgreSQL's public schema.
        """
        self.settings = settings
        self.schema = schema
        self.initialize()

    def _connect(self) -> psycopg.Connection[dict[str, Any]]:
        """Create a configured connection and select the repository schema."""
        connection = psycopg.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            dbname=self.settings.db_name,
            user=self.settings.db_user,
            password=self.settings.db_password,
            connect_timeout=self.settings.db_connect_timeout,
            row_factory=dict_row,
        )
        if self.schema != "public":
            connection.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema))
            )
        return connection

    def initialize(self) -> None:
        """Create the POC's job and subtitle tables when they are absent."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    infohash TEXT NOT NULL UNIQUE,
                    torrent_path TEXT NOT NULL,
                    download_dir TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    selected_file_index INTEGER,
                    selected_file_path TEXT,
                    selected_file_size BIGINT,
                    selected_file_offset BIGINT,
                    state TEXT NOT NULL,
                    progress DOUBLE PRECISION NOT NULL DEFAULT 0,
                    playback_mode TEXT NOT NULL DEFAULT 'unknown',
                    conversion_state TEXT NOT NULL DEFAULT 'not_required',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS subtitles (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    language TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    release_name TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _job_from_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        """Decode stored file metadata while preserving the database fields."""
        if row is None:
            return None
        job = dict(row)
        job["files"] = json.loads(job.pop("files_json"))
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return one job by its public identifier, if it exists."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = %s", (job_id,)
            ).fetchone()
        return self._job_from_row(row)

    def get_by_infohash(self, infohash: str) -> dict[str, Any] | None:
        """Find an existing download so repeated uploads remain idempotent."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE infohash = %s", (infohash,)
            ).fetchone()
        return self._job_from_row(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return jobs newest first for the library view and monitor."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._job_from_row(row) for row in rows if row is not None]

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        """Insert a job or return the concurrent request's infohash match."""
        now = _now()
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO jobs (
                    id, infohash, torrent_path, download_dir, files_json,
                    selected_file_index, selected_file_path, selected_file_size,
                    selected_file_offset, state, progress, playback_mode,
                    conversion_state, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s)
                ON CONFLICT (infohash) DO NOTHING
                RETURNING *
                """,
                (
                    job["id"],
                    job["infohash"],
                    job["torrent_path"],
                    job["download_dir"],
                    json.dumps(job["files"]),
                    job["selected_file_index"],
                    job["selected_file_path"],
                    job["selected_file_size"],
                    job["selected_file_offset"],
                    job["state"],
                    job["playback_mode"],
                    job["conversion_state"],
                    now,
                    now,
                ),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT * FROM jobs WHERE infohash = %s", (job["infohash"],)
                ).fetchone()
        return self._job_from_row(row) or {}

    def update_status(
        self,
        job_id: str,
        *,
        state: str | None = None,
        progress: float | None = None,
        error: str | None | object = _UNSET,
    ) -> None:
        """Update supplied status fields; explicit ``None`` clears an error."""
        values: list[Any] = []
        assignments: list[str] = []
        for column, value in (("state", state), ("progress", progress)):
            if value is not None:
                assignments.append(f"{column} = %s")
                values.append(value)
        if error is not _UNSET:
            assignments.append("error = %s")
            values.append(error)
        if not assignments:
            return
        assignments.append("updated_at = %s")
        values.extend((_now(), job_id))
        with self._connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = %s", values
            )

    def select_file(self, job_id: str, file_info: dict[str, Any]) -> None:
        """Reset per-file progress and set the requested playable candidate."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET selected_file_index = %s, selected_file_path = %s,
                    selected_file_size = %s, selected_file_offset = %s, progress = 0,
                    playback_mode = %s, conversion_state = 'not_required',
                    state = 'downloading', error = NULL, updated_at = %s
                WHERE id = %s
                """,
                (
                    file_info["index"],
                    file_info["path"],
                    file_info["size"],
                    file_info["offset"],
                    "direct" if file_info["direct"] else "transcode",
                    _now(),
                    job_id,
                ),
            )

    def set_playback_mode(self, job_id: str, mode: str) -> None:
        """Persist the media mode selected by codec and readiness inspection."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET playback_mode = %s, updated_at = %s WHERE id = %s",
                (mode, _now(), job_id),
            )

    def set_conversion_state(
        self, job_id: str, state: str, error: str | None = None
    ) -> None:
        """Record conversion status independently from torrent completion."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET conversion_state = %s, error = %s, updated_at = %s
                WHERE id = %s
                """,
                (state, error, _now(), job_id),
            )

    def add_subtitle(self, subtitle: dict[str, Any]) -> None:
        """Store a downloaded subtitle's path and provider metadata."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subtitles (
                    id, job_id, language, filename, path, provider,
                    release_name, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    subtitle["id"],
                    subtitle["job_id"],
                    subtitle["language"],
                    subtitle["filename"],
                    subtitle["path"],
                    subtitle["provider"],
                    subtitle.get("release_name"),
                    _now(),
                ),
            )

    def list_subtitles(self, job_id: str) -> list[dict[str, Any]]:
        """Return subtitle records in stable order for API and player use."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM subtitles
                WHERE job_id = %s
                ORDER BY created_at, id
                """,
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows if row is not None]

    def get_subtitle(self, subtitle_id: str) -> dict[str, Any] | None:
        """Look up a subtitle record before returning its stored asset."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM subtitles WHERE id = %s", (subtitle_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def clear_all(self) -> None:
        """Delete all job metadata and cascade to related subtitle records."""
        with self._connect() as connection:
            connection.execute("DELETE FROM subtitles")
            connection.execute("DELETE FROM jobs")
