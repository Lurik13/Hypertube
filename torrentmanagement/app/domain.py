"""Transport-independent validation and selection rules for torrent media."""

import re
from pathlib import PurePosixPath
from typing import Any


VIDEO_EXTENSIONS = frozenset(
    {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
)
DIRECT_EXTENSIONS = frozenset({".mp4", ".webm"})
SUBTITLE_LANGUAGES = frozenset({"en", "fr", "de", "it"})
_RANGE_PATTERN = re.compile(r"bytes=(\d*)-(\d*)$")


class InvalidTorrent(ValueError):
    """Raised when torrent metadata violates a supported-media constraint."""

    pass


class UnknownJob(LookupError):
    """Raised when an operation references a missing torrent job."""

    pass


class RangeNotSatisfiable(ValueError):
    """Raised when an HTTP byte range cannot fit within the media file."""

    pass


class RangeUnavailable(TimeoutError):
    """Raised when requested torrent pieces fail to arrive before the deadline."""

    pass


def validate_torrent_paths(paths: list[str]) -> None:
    """Reject paths that could escape the per-torrent media directory."""
    for raw_path in paths:
        if not raw_path or "\\" in raw_path:
            raise InvalidTorrent("Torrent contains an invalid file path")
        path = PurePosixPath(raw_path)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise InvalidTorrent("Torrent contains an unsafe file path")
        if path.parts and ":" in path.parts[0]:
            raise InvalidTorrent("Torrent contains an unsafe file path")


def choose_preferred_video(files: list[dict[str, Any]]) -> int | None:
    """Prefer direct-play containers, then the largest file within that tier.

    The extension is only an inexpensive first-pass hint. The media service
    still inspects codecs and confirms that the available prefix is playable
    before enabling direct playback.
    """
    candidates = [
        item
        for item in files
        if item["size"] > 0
        and PurePosixPath(item["path"]).suffix.lower() in VIDEO_EXTENSIONS
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            PurePosixPath(item["path"]).suffix.lower() in DIRECT_EXTENSIONS,
            item["size"],
            -item["index"],
        ),
    )["index"]


def validate_torrent_content_size(files: list[dict[str, Any]], limit: int) -> None:
    """Enforce the configured aggregate payload-size ceiling."""
    if limit <= 0 or sum(int(item["size"]) for item in files) > limit:
        raise InvalidTorrent("Torrent content exceeds the configured storage limit")


def pieces_for_range(file_offset: int, start: int, end_inclusive: int, piece_size: int) -> range:
    """Map a file-relative inclusive byte range to overlapping torrent pieces."""
    if file_offset < 0 or start < 0 or end_inclusive < start or piece_size <= 0:
        raise ValueError("Invalid byte range")
    first_piece = (file_offset + start) // piece_size
    last_piece = (file_offset + end_inclusive) // piece_size
    return range(first_piece, last_piece + 1)


def parse_byte_range(header: str | None, file_size: int) -> tuple[int, int]:
    """Parse one RFC-style byte range, rejecting unsupported multi-ranges."""
    if file_size <= 0:
        raise RangeNotSatisfiable("Empty media file")
    if header is None:
        return 0, file_size - 1
    if "," in header:
        raise RangeNotSatisfiable("Multiple byte ranges are not supported")
    match = _RANGE_PATTERN.fullmatch(header.strip())
    if match is None:
        raise RangeNotSatisfiable("Invalid Range header")
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise RangeNotSatisfiable("Invalid Range header")
    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise RangeNotSatisfiable("Invalid suffix range")
        return max(0, file_size - suffix_length), file_size - 1
    start = int(start_text)
    if start >= file_size:
        raise RangeNotSatisfiable("Range starts beyond end of file")
    end = file_size - 1 if not end_text else min(int(end_text), file_size - 1)
    if end < start:
        raise RangeNotSatisfiable("Range end precedes start")
    return start, end


def subtitle_languages(values: list[str] | None) -> list[str]:
    """Normalize and validate a deduplicated set of supported subtitle languages."""
    selected = [value.lower() for value in (values or sorted(SUBTITLE_LANGUAGES))]
    if not selected or len(selected) > len(SUBTITLE_LANGUAGES):
        raise ValueError("Choose between one and four subtitle languages")
    if any(value not in SUBTITLE_LANGUAGES for value in selected):
        raise ValueError("Only English, French, German, and Italian are supported")
    return list(dict.fromkeys(selected))


def is_direct_extension(path: str) -> bool:
    """Return whether a filename is a candidate for browser-native delivery."""
    return PurePosixPath(path).suffix.lower() in DIRECT_EXTENSIONS
