import unittest

from app.domain import (
    InvalidTorrent,
    RangeNotSatisfiable,
    choose_largest_video,
    parse_byte_range,
    pieces_for_range,
    subtitle_languages,
    validate_torrent_paths,
    validate_torrent_content_size,
)


class TorrentPathTests(unittest.TestCase):
    def test_accepts_nested_relative_paths(self) -> None:
        validate_torrent_paths(["Feature Film/feature.mkv", "Feature Film/readme.txt"])

    def test_rejects_path_traversal_and_absolute_paths(self) -> None:
        for path in ("../escape.mkv", "/absolute.mkv", "folder\\escape.mkv", "C:/escape.mkv"):
            with self.subTest(path=path):
                with self.assertRaises(InvalidTorrent):
                    validate_torrent_paths([path])


class FileSelectionTests(unittest.TestCase):
    def test_selects_largest_supported_video(self) -> None:
        files = [
            {"index": 0, "path": "small.mp4", "size": 20},
            {"index": 1, "path": "notes.txt", "size": 1000},
            {"index": 2, "path": "feature.mkv", "size": 200},
        ]
        self.assertEqual(choose_largest_video(files), 2)

    def test_ties_prefer_lower_file_index(self) -> None:
        files = [
            {"index": 4, "path": "a.mp4", "size": 50},
            {"index": 1, "path": "b.webm", "size": 50},
        ]
        self.assertEqual(choose_largest_video(files), 1)

    def test_returns_none_without_supported_video(self) -> None:
        self.assertIsNone(
            choose_largest_video([{"index": 0, "path": "readme.txt", "size": 10}])
        )

    def test_rejects_torrent_content_over_storage_limit(self) -> None:
        with self.assertRaises(InvalidTorrent):
            validate_torrent_content_size(
                [{"index": 0, "path": "feature.mkv", "size": 101}], 100
            )


class RangeTests(unittest.TestCase):
    def test_maps_file_range_to_all_overlapping_torrent_pieces(self) -> None:
        self.assertEqual(
            list(pieces_for_range(file_offset=98, start=0, end_inclusive=4, piece_size=100)),
            [0, 1],
        )

    def test_parses_open_and_suffix_ranges(self) -> None:
        self.assertEqual(parse_byte_range("bytes=10-", 100), (10, 99))
        self.assertEqual(parse_byte_range("bytes=-12", 100), (88, 99))
        self.assertEqual(parse_byte_range(None, 100), (0, 99))

    def test_rejects_unsatisfiable_and_multiple_ranges(self) -> None:
        for header in ("bytes=100-101", "bytes=4-2", "bytes=0-1,4-5", "bytes=-0"):
            with self.subTest(header=header):
                with self.assertRaises(RangeNotSatisfiable):
                    parse_byte_range(header, 100)


class SubtitleLanguageTests(unittest.TestCase):
    def test_normalizes_and_deduplicates_supported_languages(self) -> None:
        self.assertEqual(subtitle_languages(["EN", "fr", "en"]), ["en", "fr"])

    def test_rejects_unavailable_language(self) -> None:
        with self.assertRaises(ValueError):
            subtitle_languages(["es"])


if __name__ == "__main__":
    unittest.main()
