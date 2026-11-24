import json
import shutil
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

import libtorrent as lt

from app.config import Settings
from app.database import Repository
from app.domain import (
    InvalidTorrent,
    RangeUnavailable,
    UnknownJob,
    choose_largest_video,
    pieces_for_range,
    validate_torrent_content_size,
    validate_torrent_paths,
)


class TorrentManager:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository
        self.session = lt.session()
        self.session.apply_settings(
            {
                "listen_interfaces": "0.0.0.0:6881",
                "enable_dht": True,
                "enable_lsd": True,
                "enable_upnp": False,
                "enable_natpmp": False,
            }
        )
        self._handles: dict[str, tuple[Any, Any]] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._monitor: threading.Thread | None = None

    @staticmethod
    def _infohash(info: Any) -> str:
        hashes = info.info_hashes()
        v1 = hashes.v1.to_string()
        if any(v1):
            return v1.hex()
        v2 = hashes.v2.to_string()
        if any(v2):
            return v2.hex()
        raise InvalidTorrent("Torrent has no usable infohash")

    @staticmethod
    def _file_records(info: Any) -> list[dict[str, Any]]:
        storage = info.files()
        paths = [storage.file_path(index) for index in range(storage.num_files())]
        validate_torrent_paths(paths)
        return [
            {
                "index": index,
                "path": paths[index],
                "size": storage.file_size(index),
                "offset": storage.file_offset(index),
            }
            for index in range(storage.num_files())
        ]

    def start(self) -> None:
        self.settings.initialize_directories()
        self._restore_active_jobs()
        self._monitor = threading.Thread(
            target=self._monitor_jobs,
            name="torrent-job-monitor",
            daemon=True,
        )
        self._monitor.start()

    def stop(self) -> None:
        self._stop.set()
        if self._monitor is not None:
            self._monitor.join(timeout=3)
        self.session.pause()

    def _restore_active_jobs(self) -> None:
        for job in self.repository.list_jobs():
            if job["state"] not in {"queued", "downloading", "streamable"}:
                continue
            torrent_path = Path(job["torrent_path"])
            if not torrent_path.is_file():
                self.repository.update_status(
                    job["id"], state="failed", error="torrent_metadata_missing"
                )
                continue
            info = lt.torrent_info(str(torrent_path))
            self._attach(job, info)
            if job["selected_file_index"] is not None:
                self._apply_selection(job, info, int(job["selected_file_index"]))

    def add_torrent(self, temporary_path: Path) -> tuple[dict[str, Any], bool]:
        try:
            info = lt.torrent_info(str(temporary_path))
        except RuntimeError as error:
            raise InvalidTorrent("The uploaded file is not valid torrent metadata") from error
        files = self._file_records(info)
        validate_torrent_content_size(files, self.settings.max_torrent_content_bytes)
        selected_index = choose_largest_video(files)
        if selected_index is None:
            raise InvalidTorrent("Torrent does not contain a supported video file")

        infohash = self._infohash(info)
        with self._lock:
            existing = self.repository.get_by_infohash(infohash)
            if existing is not None:
                temporary_path.unlink(missing_ok=True)
                return existing, True

            torrent_path = self.settings.data_dir / "torrents" / f"{infohash}.torrent"
            download_dir = self.settings.data_dir / "media" / infohash
            download_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temporary_path), torrent_path)
            video = files[selected_index]
            video["direct"] = PurePosixPath(video["path"]).suffix.lower() in {
                ".mp4",
                ".webm",
            }
            for item in files:
                item["direct"] = PurePosixPath(item["path"]).suffix.lower() in {
                    ".mp4",
                    ".webm",
                }
            job_id = str(uuid.uuid4())
            job = self.repository.create_job(
                {
                    "id": job_id,
                    "infohash": infohash,
                    "torrent_path": str(torrent_path),
                    "download_dir": str(download_dir),
                    "files": files,
                    "selected_file_index": selected_index,
                    "selected_file_path": video["path"],
                    "selected_file_size": video["size"],
                    "selected_file_offset": video["offset"],
                    "state": "queued",
                    "playback_mode": "direct" if video["direct"] else "transcode",
                    "conversion_state": "not_required",
                }
            )
            self._attach(job, info)
            self._apply_selection(job, info, selected_index)
            return self.repository.get_job(job["id"]) or job, False

    def _attach(self, job: dict[str, Any], info: Any) -> tuple[Any, Any]:
        params = lt.add_torrent_params()
        params.ti = info
        params.save_path = job["download_dir"]
        params.flags |= lt.torrent_flags.paused
        params.file_priorities = [0] * info.files().num_files()
        handle = self.session.add_torrent(params)
        with self._lock:
            self._handles[job["id"]] = (handle, info)
        return handle, info

    def _runtime(self, job_id: str) -> tuple[Any, Any]:
        with self._lock:
            runtime = self._handles.get(job_id)
        if runtime is None:
            job = self.repository.get_job(job_id)
            if job is None:
                raise UnknownJob("Torrent job was not found")
            info = lt.torrent_info(job["torrent_path"])
            runtime = self._attach(job, info)
        return runtime

    def select_file(self, job_id: str, file_index: int) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise UnknownJob("Torrent job was not found")
        selected = next(
            (item for item in job["files"] if item["index"] == file_index), None
        )
        if selected is None or choose_largest_video([selected]) is None:
            raise InvalidTorrent("Selected file is not a supported video")
        selected["direct"] = PurePosixPath(selected["path"]).suffix.lower() in {
            ".mp4",
            ".webm",
        }
        handle, info = self._runtime(job_id)
        self._apply_selection(job, info, file_index, handle=handle)
        return self.repository.get_job(job_id) or job

    def _apply_selection(
        self,
        job: dict[str, Any],
        info: Any,
        file_index: int,
        *,
        handle: Any | None = None,
    ) -> None:
        if handle is None:
            handle, _ = self._runtime(job["id"])
        files = job["files"]
        selected = next(item for item in files if item["index"] == file_index)
        if PurePosixPath(selected["path"]).suffix.lower() not in {
            ".avi",
            ".m4v",
            ".mkv",
            ".mov",
            ".mp4",
            ".mpeg",
            ".mpg",
            ".webm",
        }:
            raise InvalidTorrent("Selected file is not a supported video")
        priorities = [0] * info.files().num_files()
        priorities[file_index] = 4
        handle.prioritize_files(priorities)
        piece_length = info.piece_length()
        first_piece = selected["offset"] // piece_length
        last_piece = (selected["offset"] + selected["size"] - 1) // piece_length
        for piece in {first_piece, last_piece}:
            handle.piece_priority(piece, 7)
        handle.resume()
        self.repository.select_file(job["id"], selected)

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if job is None:
            raise UnknownJob("Torrent job was not found")
        if job["selected_file_index"] is None:
            return job
        try:
            handle, _ = self._runtime(job_id)
            progress = handle.file_progress()[int(job["selected_file_index"])]
        except (RuntimeError, IndexError):
            return job
        total_size = int(job["selected_file_size"] or 0)
        normalized_progress = min(1.0, progress / total_size) if total_size else 0.0
        if total_size and progress >= total_size:
            self.repository.update_status(job_id, state="complete", progress=1.0)
        else:
            current_state = "streamable" if job["state"] == "streamable" else "downloading"
            self.repository.update_status(
                job_id, state=current_state, progress=normalized_progress
            )
        return self.repository.get_job(job_id) or job

    def mark_streamable(self, job_id: str) -> None:
        self.repository.update_status(job_id, state="streamable")

    def _piece_available(self, handle: Any, piece: int) -> bool:
        return bool(handle.have_piece(piece))

    def has_byte_range(
        self, job_id: str, file_index: int, start: int, end_inclusive: int
    ) -> bool:
        job = self.repository.get_job(job_id)
        if job is None:
            raise UnknownJob("Torrent job was not found")
        if job["state"] == "complete":
            return True
        handle, info = self._runtime(job_id)
        file_info = next(item for item in job["files"] if item["index"] == file_index)
        pieces = pieces_for_range(
            int(file_info["offset"]),
            start,
            end_inclusive,
            info.piece_length(),
        )
        return all(self._piece_available(handle, piece) for piece in pieces)

    def wait_for_range(
        self,
        job_id: str,
        file_index: int,
        start: int,
        end_inclusive: int,
        timeout: float,
    ) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise UnknownJob("Torrent job was not found")
        if job["state"] == "complete":
            return
        handle, info = self._runtime(job_id)
        file_info = next(item for item in job["files"] if item["index"] == file_index)
        pieces = pieces_for_range(
            int(file_info["offset"]),
            start,
            end_inclusive,
            info.piece_length(),
        )
        for piece in pieces:
            if not self._piece_available(handle, piece):
                handle.piece_priority(piece, 7)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if all(self._piece_available(handle, piece) for piece in pieces):
                return
            time.sleep(0.1)
        raise RangeUnavailable("Requested media bytes are not available yet")

    def media_path(self, job_id: str, file_index: int | None = None) -> Path:
        job = self.repository.get_job(job_id)
        if job is None:
            raise UnknownJob("Torrent job was not found")
        selected_index = (
            int(job["selected_file_index"]) if file_index is None else file_index
        )
        file_info = next(
            (item for item in job["files"] if item["index"] == selected_index), None
        )
        if file_info is None:
            raise UnknownJob("Selected video was not found")
        destination = Path(job["download_dir"]).joinpath(
            *PurePosixPath(file_info["path"]).parts
        )
        resolved = destination.resolve()
        root = Path(job["download_dir"]).resolve()
        if not resolved.is_relative_to(root):
            raise InvalidTorrent("Selected file path escaped media storage")
        return resolved

    def iter_file_bytes(
        self, job_id: str, file_index: int, start: int, end_inclusive: int
    ) -> Iterator[bytes]:
        path = self.media_path(job_id, file_index)
        current = start
        while current <= end_inclusive:
            chunk_end = min(end_inclusive, current + 256 * 1024 - 1)
            self.wait_for_range(
                job_id,
                file_index,
                current,
                chunk_end,
                self.settings.range_wait_seconds,
            )
            remaining = chunk_end - current + 1
            with path.open("rb") as media_file:
                media_file.seek(current)
                while remaining:
                    chunk = media_file.read(min(64 * 1024, remaining))
                    if not chunk:
                        raise RangeUnavailable("Downloaded media file is incomplete")
                    remaining -= len(chunk)
                    yield chunk
            current = chunk_end + 1

    def _monitor_jobs(self) -> None:
        while not self._stop.wait(1):
            for job in self.repository.list_jobs():
                if job["state"] not in {"queued", "downloading", "streamable"}:
                    continue
                self.get_job(job["id"])
