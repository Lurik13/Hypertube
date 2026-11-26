"""Validated environment configuration shared by the API and workers."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings for storage, PostgreSQL, and media limits."""

    data_dir: Path
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    db_connect_timeout: int
    max_torrent_bytes: int
    max_torrent_content_bytes: int
    range_chunk_bytes: int
    range_wait_seconds: float
    stream_workers: int
    subdl_api_key: str | None = field(repr=False)

    @classmethod
    def from_environment(cls) -> "Settings":
        """Read runtime values from environment variables and validate bounds."""
        settings = cls(
            data_dir=Path(os.environ.get("TM_DATA_DIR", "./data")).resolve(),
            db_host=os.environ.get("TM_DB_HOST", "127.0.0.1"),
            db_port=int(os.environ.get("TM_DB_PORT", "5432")),
            db_name=os.environ.get("TM_DB_NAME", ""),
            db_user=os.environ.get("TM_DB_USER", ""),
            db_password=os.environ.get("TM_DB_PASSWORD", ""),
            db_connect_timeout=int(os.environ.get("TM_DB_CONNECT_TIMEOUT", "5")),
            max_torrent_bytes=int(os.environ.get("TM_MAX_TORRENT_BYTES", "10485760")),
            max_torrent_content_bytes=int(
                os.environ.get("TM_MAX_TORRENT_CONTENT_BYTES", str(200 * 1024**3))
            ),
            range_chunk_bytes=int(os.environ.get("TM_RANGE_CHUNK_BYTES", "1048576")),
            range_wait_seconds=float(os.environ.get("TM_RANGE_WAIT_SECONDS", "120")),
            stream_workers=int(os.environ.get("TM_STREAM_WORKERS", "2")),
            subdl_api_key=os.environ.get("SUBDL_API_KEY") or None,
        )
        if not settings.db_host.strip():
            raise ValueError("TM_DB_HOST must not be empty")
        if not 1 <= settings.db_port <= 65535:
            raise ValueError("TM_DB_PORT must be between 1 and 65535")
        if not settings.db_name.strip():
            raise ValueError("TM_DB_NAME must not be empty")
        if not settings.db_user.strip():
            raise ValueError("TM_DB_USER must not be empty")
        if not settings.db_password:
            raise ValueError("TM_DB_PASSWORD must be configured")
        if settings.db_connect_timeout <= 0:
            raise ValueError("TM_DB_CONNECT_TIMEOUT must be positive")
        if settings.max_torrent_bytes <= 0:
            raise ValueError("TM_MAX_TORRENT_BYTES must be positive")
        if settings.max_torrent_content_bytes <= 0:
            raise ValueError("TM_MAX_TORRENT_CONTENT_BYTES must be positive")
        if settings.range_chunk_bytes <= 0:
            raise ValueError("TM_RANGE_CHUNK_BYTES must be positive")
        if settings.range_wait_seconds <= 0:
            raise ValueError("TM_RANGE_WAIT_SECONDS must be positive")
        if settings.stream_workers <= 0:
            raise ValueError("TM_STREAM_WORKERS must be positive")
        return settings

    def initialize_directories(self) -> None:
        """Create only the application's data subdirectories if missing."""
        for directory in ("torrents", "media", "converted", "subtitles", "tmp"):
            (self.data_dir / directory).mkdir(parents=True, exist_ok=True)
