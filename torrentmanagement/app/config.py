import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_torrent_bytes: int
    max_torrent_content_bytes: int
    range_chunk_bytes: int
    range_wait_seconds: float
    stream_workers: int
    subdl_api_key: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        settings = cls(
            data_dir=Path(os.environ.get("TM_DATA_DIR", "./data")).resolve(),
            max_torrent_bytes=int(os.environ.get("TM_MAX_TORRENT_BYTES", "10485760")),
            max_torrent_content_bytes=int(
                os.environ.get("TM_MAX_TORRENT_CONTENT_BYTES", str(200 * 1024**3))
            ),
            range_chunk_bytes=int(os.environ.get("TM_RANGE_CHUNK_BYTES", "1048576")),
            range_wait_seconds=float(os.environ.get("TM_RANGE_WAIT_SECONDS", "120")),
            stream_workers=int(os.environ.get("TM_STREAM_WORKERS", "2")),
            subdl_api_key=os.environ.get("SUBDL_API_KEY") or None,
        )
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
        for directory in ("torrents", "media", "converted", "subtitles", "tmp"):
            (self.data_dir / directory).mkdir(parents=True, exist_ok=True)
