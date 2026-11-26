"""HTTP routes and FastAPI lifecycle for the local Torrentmanagement POC."""

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Iterator
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings
from app.database import Repository
from app.domain import (
    InvalidTorrent,
    RangeNotSatisfiable,
    RangeUnavailable,
    UnknownJob,
    parse_byte_range,
    subtitle_languages,
)
from app.media import MediaProcessingError, MediaService
from app.subtitles import SubDLProvider, SubtitleProviderError
from app.torrent import TorrentManager


settings = Settings.from_environment()
settings.initialize_directories()
repository = Repository(settings)
torrents = TorrentManager(settings, repository)
media = MediaService(settings, repository, torrents)
subtitles = SubDLProvider(settings, repository)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start torrent workers only after PostgreSQL is healthy."""
    torrents.start()
    yield
    torrents.stop()


app = FastAPI(
    title="Hypertube Torrentmanagement POC",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SelectionRequest(BaseModel):
    """Validate a torrent-relative video file index from the UI."""

    file_index: int = Field(ge=0)


class SubtitleSearchRequest(BaseModel):
    """Constrain subtitle search inputs to the POC's supported languages."""

    title: str = Field(min_length=1, max_length=200)
    languages: list[str] = Field(
        default_factory=lambda: ["en", "fr", "de", "it"],
        min_length=1,
        max_length=4,
    )


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    """Build the API-safe job representation without exposing storage paths."""
    files = [
        {
            "index": item["index"],
            "path": item["path"],
            "size": item["size"],
            "selected": item["index"] == job["selected_file_index"],
            "playback_mode": "direct" if item.get("direct") else "transcode",
        }
        for item in job["files"]
    ]
    return {
        "id": job["id"],
        "infohash": job["infohash"],
        "state": job["state"],
        "progress": job["progress"],
        "selected_file_index": job["selected_file_index"],
        "selected_file_path": job["selected_file_path"],
        "selected_file_size": job["selected_file_size"],
        "playback_mode": job["playback_mode"],
        "conversion_state": job["conversion_state"],
        "error": job["error"],
        "files": files,
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


def _get_job(job_id: str) -> dict[str, Any]:
    """Resolve a known job or translate the domain error to HTTP 404."""
    try:
        return torrents.get_job(job_id)
    except UnknownJob as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _disk_chunks(path: Path, start: int, end_inclusive: int) -> Iterator[bytes]:
    """Yield a stored media interval without loading it into memory at once."""
    remaining = end_inclusive - start + 1
    with path.open("rb") as media_file:
        media_file.seek(start)
        while remaining:
            chunk = media_file.read(min(64 * 1024, remaining))
            if not chunk:
                raise RangeUnavailable("Stored media file is incomplete")
            remaining -= len(chunk)
            yield chunk


def _range_headers(
    start: int, end_inclusive: int, total_size: int, *, partial: bool
) -> dict[str, str]:
    """Set exact byte-range headers for the requested interval."""
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(end_inclusive - start + 1),
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }
    if partial:
        headers["Content-Range"] = f"bytes {start}-{end_inclusive}/{total_size}"
    return headers


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page local demo."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Expose a lightweight process health check."""
    return {"status": "ok"}


@app.get("/api/torrents")
def list_torrents() -> dict[str, list[dict[str, Any]]]:
    """List current download jobs and refresh their torrent progress."""
    return {
        "items": [
            _public_job(torrents.get_job(job["id"]))
            for job in repository.list_jobs()
        ]
    }


@app.post("/api/torrents")
async def upload_torrent(
    request: Request,
    content_length: str | None = Header(default=None),
) -> JSONResponse:
    """Stream a bounded raw torrent upload to disk and create/reuse its job."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if content_type not in {"application/x-bittorrent", "application/octet-stream"}:
        raise HTTPException(
            status_code=415,
            detail="Upload the .torrent file as application/x-bittorrent",
        )
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from error
        if declared_size <= 0 or declared_size > settings.max_torrent_bytes:
            raise HTTPException(status_code=413, detail="Torrent upload exceeds the size limit")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix="upload-", suffix=".torrent", dir=settings.data_dir / "tmp"
    )
    temporary_path = Path(temporary_name)
    uploaded_bytes = 0
    try:
        with os.fdopen(descriptor, "wb") as target:
            async for chunk in request.stream():
                uploaded_bytes += len(chunk)
                if uploaded_bytes > settings.max_torrent_bytes:
                    raise HTTPException(
                        status_code=413, detail="Torrent upload exceeds the size limit"
                    )
                target.write(chunk)
        if uploaded_bytes == 0:
            raise HTTPException(status_code=400, detail="Torrent upload is empty")
        try:
            job, reused = await asyncio.to_thread(torrents.add_torrent, temporary_path)
        except InvalidTorrent as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return JSONResponse(
            status_code=200 if reused else 202,
            content={"reused": reused, "job": _public_job(job)},
        )
    finally:
        temporary_path.unlink(missing_ok=True)


@app.get("/api/torrents/{job_id}")
def get_torrent(job_id: str) -> dict[str, Any]:
    """Return one job's current download and playback state."""
    return _public_job(_get_job(job_id))


@app.put("/api/torrents/{job_id}/selection")
def select_video(job_id: str, selection: SelectionRequest) -> dict[str, Any]:
    """Apply a validated user-selected media file to the torrent job."""
    _get_job(job_id)
    try:
        job = torrents.select_file(job_id, selection.file_index)
    except InvalidTorrent as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _public_job(job)


@app.get("/api/torrents/{job_id}/readiness")
def get_readiness(job_id: str) -> dict[str, Any]:
    """Report readiness independently from download completion."""
    _get_job(job_id)
    try:
        result = media.readiness(job_id)
    except UnknownJob as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return result


@app.get("/api/torrents/{job_id}/stream")
async def stream_media(job_id: str, request: Request) -> StreamingResponse:
    """Stream direct ranges, sequential partial output, or completed conversion."""
    job = _get_job(job_id)
    readiness = media.readiness(job_id)
    if not readiness.get("ready"):
        raise HTTPException(
            status_code=425,
            detail={
                "message": "Media is not ready to play yet",
                "reason": readiness.get("reason"),
                "state": job["state"],
            },
            headers={"Retry-After": "3"},
        )
    job = _get_job(job_id)

    selected_index = int(job["selected_file_index"])
    if readiness["mode"] == "transcode" and job["state"] != "complete":
        try:
            partial = media.open_partial_transcode(job)
        except (RangeUnavailable, MediaProcessingError) as error:
            raise HTTPException(
                status_code=503, detail=str(error), headers={"Retry-After": "3"}
            ) from error

        def partial_chunks() -> Iterator[bytes]:
            """Release the transcoder process even if the client disconnects."""
            try:
                yield from partial
            finally:
                partial.close()

        return StreamingResponse(
            partial_chunks(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "none",
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    if readiness["mode"] == "converted":
        path = media.converted_path(job_id, settings.data_dir)
        media_type = "video/mp4"
    else:
        path = torrents.media_path(job_id, selected_index)
        media_type = {
            ".mp4": "video/mp4",
            ".webm": "video/webm",
        }.get(path.suffix.lower(), "application/octet-stream")
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Media file is not available")

    total_size = (
        path.stat().st_size
        if readiness["mode"] == "converted"
        else int(job["selected_file_size"])
    )
    range_header = request.headers.get("range")
    try:
        start, end_inclusive = parse_byte_range(range_header, total_size)
    except RangeNotSatisfiable as error:
        raise HTTPException(
            status_code=416,
            detail=str(error),
            headers={"Content-Range": f"bytes */{total_size}"},
        ) from error
    if range_header is not None:
        end_inclusive = min(end_inclusive, start + settings.range_chunk_bytes - 1)
    is_complete = job["state"] == "complete" and readiness["complete"]
    if not is_complete and range_header is not None:
        try:
            await asyncio.to_thread(
                torrents.wait_for_range,
                job_id,
                selected_index,
                start,
                end_inclusive,
                settings.range_wait_seconds,
            )
        except RangeUnavailable as error:
            raise HTTPException(
                status_code=503, detail=str(error), headers={"Retry-After": "3"}
            ) from error
    partial_response = range_header is not None
    response_headers = _range_headers(
        start, end_inclusive, total_size, partial=partial_response
    )
    response_headers["Cache-Control"] = "no-store"
    response_headers["Content-Disposition"] = (
        "inline; filename*=UTF-8''" + quote(Path(job["selected_file_path"]).name)
    )
    chunks = (
        _disk_chunks(path, start, end_inclusive)
        if readiness["mode"] == "converted" or is_complete
        else torrents.iter_file_bytes(
            job_id, selected_index, start, end_inclusive
        )
    )
    return StreamingResponse(
        chunks,
        status_code=206 if partial_response else 200,
        media_type=media_type,
        headers=response_headers,
    )


@app.post("/api/torrents/{job_id}/subtitles")
def download_subtitles(
    job_id: str, payload: SubtitleSearchRequest
) -> dict[str, Any]:
    """Search and store up to five subtitles for the selected languages."""
    _get_job(job_id)
    try:
        languages = subtitle_languages(payload.languages)
        downloaded, failures = subtitles.search_and_download(
            job_id, payload.title, languages
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SubtitleProviderError as error:
        status_code = 503 if "not configured" in str(error) else 502
        raise HTTPException(status_code=status_code, detail=str(error)) from error
    return {
        "downloaded": downloaded,
        "failures": failures,
        "requested": 5,
    }


@app.get("/api/torrents/{job_id}/subtitles")
def list_subtitles(job_id: str) -> dict[str, list[dict[str, Any]]]:
    """List subtitle records available to the job's player."""
    _get_job(job_id)
    return {
        "items": [
            {
                "id": item["id"],
                "language": item["language"],
                "filename": item["filename"],
                "provider": item["provider"],
                "release_name": item["release_name"],
            }
            for item in repository.list_subtitles(job_id)
        ]
    }


@app.get("/api/subtitles/{subtitle_id}")
def get_subtitle(subtitle_id: str) -> FileResponse:
    """Serve one validated subtitle asset from the managed storage tree."""
    path = subtitles.asset_path(subtitle_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Subtitle file was not found")
    return FileResponse(
        path,
        media_type="text/vtt" if path.suffix.lower() == ".vtt" else "text/plain",
        filename=path.name,
    )
