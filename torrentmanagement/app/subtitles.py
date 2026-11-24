import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from app.config import Settings
from app.database import Repository
from app.domain import SUBTITLE_LANGUAGES


_SUBTITLE_EXTENSIONS = {".ass", ".srt", ".ssa", ".sub", ".vtt"}
_MAX_SUBTITLE_BYTES = 10 * 1024 * 1024
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class SubtitleProviderError(RuntimeError):
    pass


class SubDLProvider:
    def __init__(self, settings: Settings, repository: Repository) -> None:
        self.settings = settings
        self.repository = repository

    def _request(
        self, url: str, *, data: bytes | None = None
    ) -> tuple[bytes, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.subdl_api_key}",
            "Accept": "application/json" if data is None else "*/*",
            "User-Agent": "Hypertube-Torrentmanagement-POC/1.0",
        }
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read(_MAX_SUBTITLE_BYTES + 1)
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            raise SubtitleProviderError(
                f"Subtitle provider returned HTTP {error.code}"
            ) from error
        except urllib.error.URLError as error:
            raise SubtitleProviderError("Subtitle provider could not be reached") from error
        except TimeoutError as error:
            raise SubtitleProviderError("Subtitle provider request timed out") from error
        if len(body) > _MAX_SUBTITLE_BYTES:
            raise SubtitleProviderError("Subtitle provider response exceeded the size limit")
        return body, content_type

    @staticmethod
    def _language(candidate: dict[str, Any]) -> str | None:
        raw_language = candidate.get("language") or candidate.get("lang")
        if isinstance(raw_language, dict):
            raw_language = raw_language.get("code") or raw_language.get("name")
        if not isinstance(raw_language, str):
            return None
        value = raw_language.strip().lower()
        aliases = {
            "english": "en",
            "french": "fr",
            "german": "de",
            "italian": "it",
            "en": "en",
            "fr": "fr",
            "de": "de",
            "it": "it",
        }
        return aliases.get(value)

    @staticmethod
    def _payload_file(body: bytes, content_type: str, candidate: dict[str, Any]) -> tuple[bytes, str]:
        if "text/html" in content_type.lower() or body.lstrip().lower().startswith(
            (b"<!doctype html", b"<html")
        ):
            raise SubtitleProviderError("Subtitle provider returned an HTML page")
        extension = PurePosixPath(
            str(candidate.get("filename") or candidate.get("name") or "")
        ).suffix.lower()
        if zipfile.is_zipfile(io.BytesIO(body)):
            try:
                with zipfile.ZipFile(io.BytesIO(body)) as archive:
                    members = [
                        member
                        for member in archive.infolist()
                        if not member.is_dir()
                        and PurePosixPath(member.filename).suffix.lower()
                        in _SUBTITLE_EXTENSIONS
                        and member.file_size <= _MAX_SUBTITLE_BYTES
                    ]
                    if not members:
                        raise SubtitleProviderError(
                            "Subtitle archive contained no supported subtitle file"
                        )
                    selected = members[0]
                    extension = PurePosixPath(selected.filename).suffix.lower()
                    body = archive.read(selected)
            except zipfile.BadZipFile as error:
                raise SubtitleProviderError("Subtitle provider returned an invalid archive") from error
        if len(body) > _MAX_SUBTITLE_BYTES:
            raise SubtitleProviderError("Subtitle file exceeded the size limit")
        if extension not in _SUBTITLE_EXTENSIONS:
            if "webvtt" in content_type.lower():
                extension = ".vtt"
            elif "subrip" in content_type.lower():
                extension = ".srt"
            else:
                extension = ".srt"
        return body, extension

    @staticmethod
    def _filename(title: str, language: str, extension: str) -> str:
        safe_title = _SAFE_FILENAME.sub("-", title).strip("-._")[:80] or "subtitle"
        return f"{safe_title}.{language}.{uuid.uuid4().hex[:8]}{extension}"

    def search_and_download(
        self,
        job_id: str,
        title: str,
        languages: list[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        if not self.settings.subdl_api_key:
            raise SubtitleProviderError("SUBDL_API_KEY is not configured")
        if not title.strip() or len(title) > 200:
            raise ValueError("Title must contain between 1 and 200 characters")
        if any(language not in SUBTITLE_LANGUAGES for language in languages):
            raise ValueError("Unsupported subtitle language")

        query = urllib.parse.urlencode(
            {
                "film_name": title.strip(),
                "languages": ",".join(languages),
            }
        )
        search_url = f"https://api.subdl.com/api/v2/subtitles/search?{query}"
        response_body, _ = self._request(search_url)
        try:
            response = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise SubtitleProviderError("Subtitle provider returned invalid JSON") from error
        if not isinstance(response, dict) or not isinstance(response.get("subtitles"), list):
            raise SubtitleProviderError("Subtitle provider returned an unexpected response")

        candidates = [
            item
            for item in response["subtitles"]
            if isinstance(item, dict)
            and isinstance(item.get("n_id"), str)
            and self._language(item) in languages
        ][:5]
        if not candidates:
            return [], []

        subtitle_dir = self.settings.data_dir / "subtitles" / job_id
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for candidate in candidates:
            language = self._language(candidate)
            subtitle_id = str(candidate["n_id"])
            download_url = (
                "https://api.subdl.com/api/v2/subtitles/"
                f"{urllib.parse.quote(subtitle_id, safe='')}/download?format=file"
            )
            try:
                body, content_type = self._request(download_url)
                body, extension = self._payload_file(body, content_type, candidate)
                filename = self._filename(title, language or "en", extension)
                path = subtitle_dir / filename
                path.write_bytes(body)
                subtitle = {
                    "id": str(uuid.uuid4()),
                    "job_id": job_id,
                    "language": language or "en",
                    "filename": filename,
                    "path": str(path),
                    "provider": "SubDL",
                    "release_name": str(candidate.get("release_name") or "")[:200],
                }
                self.repository.add_subtitle(subtitle)
                downloaded.append(
                    {
                        "id": subtitle["id"],
                        "language": subtitle["language"],
                        "filename": filename,
                        "provider": "SubDL",
                        "release_name": subtitle["release_name"],
                    }
                )
            except SubtitleProviderError as error:
                failures.append(
                    {
                        "release_name": str(candidate.get("release_name") or "")[:200],
                        "reason": str(error),
                    }
                )
        return downloaded, failures

    def asset_path(self, subtitle_id: str) -> Path | None:
        subtitle = self.repository.get_subtitle(subtitle_id)
        if subtitle is None:
            return None
        path = Path(subtitle["path"]).resolve()
        root = (self.settings.data_dir / "subtitles").resolve()
        return path if path.is_relative_to(root) else None
