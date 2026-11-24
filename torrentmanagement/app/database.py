import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_UNSET = object()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    infohash TEXT NOT NULL UNIQUE,
                    torrent_path TEXT NOT NULL,
                    download_dir TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    selected_file_index INTEGER,
                    selected_file_path TEXT,
                    selected_file_size INTEGER,
                    selected_file_offset INTEGER,
                    state TEXT NOT NULL,
                    progress REAL NOT NULL DEFAULT 0,
                    playback_mode TEXT NOT NULL DEFAULT 'unknown',
                    conversion_state TEXT NOT NULL DEFAULT 'not_required',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS subtitles (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    language TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    release_name TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _job_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        job = dict(row)
        job["files"] = json.loads(job.pop("files_json"))
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row)

    def get_by_infohash(self, infohash: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE infohash = ?", (infohash,)
            ).fetchone()
        return self._job_from_row(row)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._job_from_row(row) for row in rows if row is not None]

    def create_job(self, job: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM jobs WHERE infohash = ?", (job["infohash"],)
            ).fetchone()
            if existing is not None:
                return self._job_from_row(existing) or {}
            connection.execute(
                """
                INSERT INTO jobs (
                    id, infohash, torrent_path, download_dir, files_json,
                    selected_file_index, selected_file_path, selected_file_size,
                    selected_file_offset, state, progress, playback_mode,
                    conversion_state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
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
            )
        return self.get_job(job["id"]) or {}

    def update_status(
        self,
        job_id: str,
        *,
        state: str | None = None,
        progress: float | None = None,
        error: str | None | object = _UNSET,
    ) -> None:
        values: list[Any] = []
        assignments: list[str] = []
        for column, value in (("state", state), ("progress", progress)):
            if value is not None:
                assignments.append(f"{column} = ?")
                values.append(value)
        if error is not _UNSET:
            assignments.append("error = ?")
            values.append(error)
        if not assignments:
            return
        assignments.append("updated_at = ?")
        values.extend((_now(), job_id))
        with self._connect() as connection:
            connection.execute(
                f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", values
            )

    def select_file(self, job_id: str, file_info: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET selected_file_index = ?, selected_file_path = ?,
                    selected_file_size = ?, selected_file_offset = ?, progress = 0,
                    playback_mode = ?, conversion_state = 'not_required',
                    state = 'downloading', error = NULL, updated_at = ?
                WHERE id = ?
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
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET playback_mode = ?, updated_at = ? WHERE id = ?",
                (mode, _now(), job_id),
            )

    def set_conversion_state(self, job_id: str, state: str, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET conversion_state = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (state, error, _now(), job_id),
            )

    def add_subtitle(self, subtitle: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO subtitles (
                    id, job_id, language, filename, path, provider,
                    release_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM subtitles WHERE job_id = ? ORDER BY created_at, id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_subtitle(self, subtitle_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM subtitles WHERE id = ?", (subtitle_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def clear_all(self) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM subtitles")
            connection.execute("DELETE FROM jobs")
