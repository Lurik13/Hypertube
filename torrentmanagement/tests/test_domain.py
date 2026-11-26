"""Focused tests for torrent metadata, video selection, and byte ranges."""

import unittest

from app.domain import (
    InvalidTorrent,
    RangeNotSatisfiable,
    choose_preferred_video,
    parse_byte_range,
    pieces_for_range,
    subtitle_languages,
    validate_torrent_paths,
    validate_torrent_content_size,
)


class TorrentPathTests(unittest.TestCase):
    """Keep uploaded torrent paths inside the managed media directory."""

    def test_accepts_nested_relative_paths(self) -> None:
        """Allow normal torrent folder structures."""
        validate_torrent_paths(["Feature Film/feature.mkv", "Feature Film/readme.txt"])

    def test_rejects_path_traversal_and_absolute_paths(self) -> None:
        """Reject absolute and parent-relative torrent entries."""
        for path in ("../escape.mkv", "/absolute.mkv", "folder\\escape.mkv", "C:/escape.mkv"):
            with self.subTest(path=path):
                with self.assertRaises(InvalidTorrent):
                    validate_torrent_paths([path])


class FileSelectionTests(unittest.TestCase):
    """Select a stream-friendly container before optimizing for size."""

    def test_prefers_direct_play_video_over_a_larger_conversion_candidate(self) -> None:
        """Prefer the no-conversion container tier over a larger MPEG source."""
        files = [
            {"index": 0, "path": "small.mp4", "size": 20},
            {"index": 1, "path": "notes.txt", "size": 1000},
            {"index": 2, "path": "feature.mkv", "size": 200},
        ]
        self.assertEqual(choose_preferred_video(files), 0)

    def test_largest_direct_play_file_wins_and_ties_prefer_lower_index(self) -> None:
        """Use size within the preferred tier and stable index for ties."""
        files = [
            {"index": 4, "path": "a.mp4", "size": 50},
            {"index": 1, "path": "b.webm", "size": 50},
        ]
        self.assertEqual(choose_preferred_video(files), 1)

    def test_returns_none_without_supported_video(self) -> None:
        """Return no candidate when the torrent contains only non-video files."""
        self.assertIsNone(
            choose_preferred_video([{"index": 0, "path": "readme.txt", "size": 10}])
        )

    def test_rejects_torrent_content_over_storage_limit(self) -> None:
        """Reject metadata that advertises more bytes than the configured cap."""
        with self.assertRaises(InvalidTorrent):
            validate_torrent_content_size(
                [{"index": 0, "path": "feature.mkv", "size": 101}], 100
            )


class RangeTests(unittest.TestCase):
    """Cover inclusive HTTP range parsing and torrent-piece mapping."""

    def test_maps_file_range_to_all_overlapping_torrent_pieces(self) -> None:
        """Account for both file offset and inclusive end byte."""
        self.assertEqual(
            list(pieces_for_range(file_offset=98, start=0, end_inclusive=4, piece_size=100)),
            [0, 1],
        )

    def test_parses_open_and_suffix_ranges(self) -> None:
        """Support closed-open and suffix byte-range request forms."""
        self.assertEqual(parse_byte_range("bytes=10-", 100), (10, 99))
        self.assertEqual(parse_byte_range("bytes=-12", 100), (88, 99))
        self.assertEqual(parse_byte_range(None, 100), (0, 99))

    def test_rejects_unsatisfiable_and_multiple_ranges(self) -> None:
        """Reject ranges the stream endpoint cannot safely serve."""
        for header in ("bytes=100-101", "bytes=4-2", "bytes=0-1,4-5", "bytes=-0"):
            with self.subTest(header=header):
                with self.assertRaises(RangeNotSatisfiable):
                    parse_byte_range(header, 100)


class SubtitleLanguageTests(unittest.TestCase):
    """Restrict subtitle searches to supported POC languages."""

    def test_normalizes_and_deduplicates_supported_languages(self) -> None:
        """Normalize language codes without returning duplicates."""
        self.assertEqual(subtitle_languages(["EN", "fr", "en"]), ["en", "fr"])

    def test_rejects_unavailable_language(self) -> None:
        """Reject a language outside the configured four-language set."""
        with self.assertRaises(ValueError):
            subtitle_languages(["es"])


if __name__ == "__main__":
    unittest.main()
