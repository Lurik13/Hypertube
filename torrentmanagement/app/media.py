"""Probe, transcode, and serveability decisions for selected video files."""

import json
import os
import select
import subprocess
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from app.config import Settings
from app.database import Repository
from app.domain import RangeUnavailable
from app.torrent import TorrentManager


_VIDEO_CODECS = {"av1", "h264", "vp8", "vp9"}
_AUDIO_CODECS = {"aac", "mp3", "opus", "vorbis"}


class MediaProcessingError(RuntimeError):
    """Raised when FFmpeg cannot produce a valid media stream or output."""

    pass


class PartialTranscode:
    """Own an FFmpeg process streaming fragmented output from partial input."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        producer: threading.Thread,
        first_chunk: bytes,
        semaphore: threading.BoundedSemaphore,
    ) -> None:
        """Retain the process resources until streaming finishes or is cancelled."""
        self.process = process
        self.producer = producer
        self.first_chunk = first_chunk
        self.semaphore = semaphore
        self._closed = False

    def __iter__(self) -> Iterator[bytes]:
        """Yield FFmpeg output and surface non-zero process completion."""
        if self.first_chunk:
            yield self.first_chunk
        stream = self.process.stdout
        if stream is None:
            return
        while True:
            chunk = os.read(stream.fileno(), 64 * 1024)
            if not chunk:
                break
            yield chunk
        return_code = self.process.wait()
        self.producer.join(timeout=2)
        if return_code != 0:
            raise MediaProcessingError("Partial media conversion failed")
        self.close()

    def close(self) -> None:
        """Terminate remaining workers, close pipes, and free one stream slot."""
        if self._closed:
            return
        self._closed = True
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.producer.join(timeout=2)
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.stdout is not None:
            self.process.stdout.close()
        self.semaphore.release()


class MediaService:
    """Coordinate FFprobe checks, browser compatibility, and conversions."""

    def __init__(
        self,
        settings: Settings,
        repository: Repository,
        torrents: TorrentManager,
    ) -> None:
        """Bind media processing to runtime settings and torrent storage."""
        self.settings = settings
        self.repository = repository
        self.torrents = torrents
        self._conversion_lock = threading.Lock()
        self._conversions: set[str] = set()
        self._probe_lock = threading.Lock()
        self._last_probe: dict[str, float] = {}
        self._stream_slots = threading.BoundedSemaphore(settings.stream_workers)

    @staticmethod
    def converted_path(job_id: str, data_dir: Path) -> Path:
        """Return the deterministic MP4 destination for a completed job."""
        return data_dir / "converted" / f"{job_id}.mp4"

    @staticmethod
    def _run_probe(path: Path, *, packets: bool) -> dict[str, Any] | None:
        """Return bounded FFprobe metadata, or None when the source is unreadable."""
        entries = (
            "stream=index,codec_type,codec_name:"
            "packet=stream_index,pts_time,duration_time,pos,size:"
            "format=duration"
            if packets
            else "stream=index,codec_type,codec_name:format=format_name,duration"
        )
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            entries,
            "-of",
            "json",
        ]
        if packets:
            command.extend(["-read_intervals", "%+1"])
        command.append(str(path))
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _is_browser_compatible(path: Path, probe: dict[str, Any]) -> bool:
        """Check the container and every present audio/video codec."""
        extension = path.suffix.lower()
        streams = probe.get("streams", [])
        videos = [
            item.get("codec_name")
            for item in streams
            if item.get("codec_type") == "video"
        ]
        audios = [
            item.get("codec_name")
            for item in streams
            if item.get("codec_type") == "audio"
        ]
        if len(videos) != 1 or videos[0] not in _VIDEO_CODECS:
            return False
        if any(codec not in _AUDIO_CODECS for codec in audios):
            return False
        if extension == ".mp4":
            return videos[0] in {"h264", "av1"} and all(
                codec in {"aac", "mp3"} for codec in audios
            )
        if extension == ".webm":
            return videos[0] in {"av1", "vp8", "vp9"} and all(
                codec in {"opus", "vorbis"} for codec in audios
            )
        return False

    def _prefix_is_playable(self, job: dict[str, Any], path: Path) -> bool:
        """Require verified bytes for, and a successful decode of, one video frame."""
        piece_probe = self._run_probe(path, packets=True)
        if piece_probe is None:
            return False
        streams = piece_probe.get("streams", [])
        video_streams = {
            int(item["index"])
            for item in streams
            if item.get("codec_type") == "video" and "index" in item
        }
        video_packets = [
            packet
            for packet in piece_probe.get("packets", [])
            if int(packet.get("stream_index", -1)) in video_streams
        ]
        if not video_packets:
            return False
        positioned: list[tuple[float, int, int]] = []
        for packet in video_packets:
            try:
                start = float(packet["pts_time"])
                position = int(packet["pos"])
                size = int(packet["size"])
            except (KeyError, TypeError, ValueError):
                return False
            if position < 0 or size <= 0:
                return False
            positioned.append((start, position, size))
        first_video_packet = min(positioned, key=lambda item: item[0])
        if first_video_packet[0] > 0.1:
            return False
        file_index = int(job["selected_file_index"])
        _, position, size = first_video_packet
        if not self.torrents.has_byte_range(
            job["id"], file_index, position, position + size - 1
        ):
            return False
        decode_command = [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-map",
            "0:v:0",
            "-f",
            "null",
            "-",
        ]
        try:
            subprocess.run(
                decode_command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
        return True

    def readiness(self, job_id: str) -> dict[str, Any]:
        """Report direct, partial, or completed-conversion readiness."""
        job = self.torrents.get_job(job_id)
        if job["selected_file_index"] is None:
            return {"ready": False, "reason": "no_video_selected"}
        path = self.torrents.media_path(job_id)
        complete = job["state"] == "complete"
        if complete:
            probe = self._run_probe(path, packets=False)
            if probe is None:
                self.repository.update_status(
                    job_id, state="failed", error="media_probe_failed"
                )
                return {"ready": False, "reason": "media_probe_failed"}
            mode = "direct" if self._is_browser_compatible(path, probe) else "transcode"
            self.repository.set_playback_mode(job_id, mode)
            if mode == "direct":
                return {
                    "ready": True,
                    "mode": "direct",
                    "complete": True,
                    "duration_seconds": probe.get("format", {}).get("duration"),
                }
            output_path = self.converted_path(job_id, self.settings.data_dir)
            if output_path.is_file() and output_path.stat().st_size:
                self.repository.set_conversion_state(job_id, "ready")
                return {
                    "ready": True,
                    "mode": "converted",
                    "complete": True,
                    "duration_seconds": probe.get("format", {}).get("duration"),
                }
            self._queue_conversion(job_id, path, output_path)
            current = self.repository.get_job(job_id) or job
            return {
                "ready": False,
                "mode": "transcode",
                "complete": True,
                "conversion_state": current["conversion_state"],
                "reason": current.get("error") or "conversion_pending",
            }

        with self._probe_lock:
            now = time.monotonic()
            if now - self._last_probe.get(job_id, 0) < 2:
                return {
                    "ready": job["state"] == "streamable",
                    "mode": job["playback_mode"],
                    "complete": False,
                    "reason": None,
                }
            self._last_probe[job_id] = now
        if self._prefix_is_playable(job, path):
            probe = self._run_probe(path, packets=False)
            mode = (
                "direct"
                if probe is not None and self._is_browser_compatible(path, probe)
                else "transcode"
            )
            if mode == "transcode" and path.suffix.lower() not in {".mkv", ".webm"}:
                return {
                    "ready": False,
                    "mode": mode,
                    "complete": False,
                    "reason": "conversion_requires_complete_download",
                }
            self.torrents.mark_streamable(job_id)
            self.repository.set_playback_mode(job_id, mode)
            return {
                "ready": True,
                "mode": mode,
                "complete": False,
                "duration_seconds": (
                    probe.get("format", {}).get("duration") if probe is not None else None
                ),
            }
        return {
            "ready": False,
            "mode": job["playback_mode"],
            "complete": False,
            "reason": "waiting_for_playable_prefix",
        }

    def _queue_conversion(self, job_id: str, source: Path, destination: Path) -> None:
        """Start at most one background conversion worker per job."""
        with self._conversion_lock:
            if job_id in self._conversions:
                return
            self._conversions.add(job_id)
        self.repository.set_conversion_state(job_id, "queued")
        thread = threading.Thread(
            target=self._convert_completed,
            args=(job_id, source, destination),
            name=f"transcode-{job_id}",
            daemon=True,
        )
        thread.start()

    def _convert_completed(self, job_id: str, source: Path, destination: Path) -> None:
        """Remux or transcode a complete source, then atomically publish output."""
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        self.repository.set_conversion_state(job_id, "running")
        try:
            remux = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                "-f",
                "mp4",
                str(temporary),
            ]
            try:
                subprocess.run(
                    remux,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=6 * 60 * 60,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                )
            except subprocess.CalledProcessError:
                temporary.unlink(missing_ok=True)
                transcode = [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    "-f",
                    "mp4",
                    str(temporary),
                ]
                subprocess.run(
                    transcode,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=6 * 60 * 60,
                    env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
                )
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise MediaProcessingError("Transcoder produced no media output")
            os.replace(temporary, destination)
            self.repository.set_conversion_state(job_id, "ready")
        except FileNotFoundError:
            temporary.unlink(missing_ok=True)
            self.repository.set_conversion_state(job_id, "failed", "ffmpeg_unavailable")
        except subprocess.CalledProcessError:
            temporary.unlink(missing_ok=True)
            self.repository.set_conversion_state(job_id, "failed", "conversion_failed")
        except subprocess.TimeoutExpired:
            temporary.unlink(missing_ok=True)
            self.repository.set_conversion_state(job_id, "failed", "conversion_timeout")
        except MediaProcessingError:
            temporary.unlink(missing_ok=True)
            self.repository.set_conversion_state(job_id, "failed", "conversion_empty_output")
        finally:
            with self._conversion_lock:
                self._conversions.discard(job_id)

    def open_partial_transcode(self, job: dict[str, Any]) -> PartialTranscode:
        """Start the bounded sequential transcoder supported for partial MKV/WebM."""
        source = self.torrents.media_path(job["id"])
        if source.suffix.lower() not in {".mkv", ".webm"}:
            raise RangeUnavailable("This source requires complete download before conversion")
        if not self._stream_slots.acquire(blocking=False):
            raise RangeUnavailable("All partial transcode slots are in use")
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "matroska",
                    "-i",
                    "pipe:0",
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "ultrafast",
                    "-tune",
                    "zerolatency",
                    "-threads",
                    "2",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+empty_moov+frag_keyframe+default_base_moof",
                    "-f",
                    "mp4",
                    "pipe:1",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
                env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            )
        except FileNotFoundError as error:
            self._stream_slots.release()
            raise MediaProcessingError("FFmpeg is not installed") from error
        if process.stdin is None or process.stdout is None:
            process.kill()
            process.wait()
            self._stream_slots.release()
            raise MediaProcessingError("FFmpeg did not open its media pipes")

        def feed_source() -> None:
            """Feed verified source chunks to FFmpeg while respecting piece waits."""
            try:
                for block in self.torrents.iter_file_bytes(
                    job["id"],
                    int(job["selected_file_index"]),
                    0,
                    int(job["selected_file_size"]) - 1,
                ):
                    process.stdin.write(block)
                process.stdin.close()
            except (BrokenPipeError, OSError, RangeUnavailable):
                if process.poll() is None:
                    process.terminate()

        producer = threading.Thread(
            target=feed_source,
            name=f"transcode-input-{job['id']}",
            daemon=True,
        )
        producer.start()
        ready, _, _ = select.select(
            [process.stdout], [], [], self.settings.range_wait_seconds
        )
        if not ready:
            process.terminate()
            process.wait(timeout=3)
            producer.join(timeout=2)
            self._stream_slots.release()
            raise RangeUnavailable("Transcoder did not produce playable output in time")
        first_chunk = os.read(process.stdout.fileno(), 64 * 1024)
        if not first_chunk:
            return_code = process.poll()
            producer.join(timeout=2)
            process.stdout.close()
            process.stdin.close()
            self._stream_slots.release()
            raise MediaProcessingError(
                "Transcoder exited before producing playable output"
            ) from (None if return_code is None else RuntimeError(str(return_code)))
        return PartialTranscode(process, producer, first_chunk, self._stream_slots)
