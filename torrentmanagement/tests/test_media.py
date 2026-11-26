"""Focused tests for playback readiness on partial media files."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.media import MediaService


class PartialReadinessTests(unittest.TestCase):
    """Verify that one available opening frame is enough for readiness."""

    def test_decodes_first_frame_without_waiting_for_ten_seconds(self) -> None:
        """A valid sub-second prefix passes once its first frame is verified."""
        service = MediaService.__new__(MediaService)
        service.torrents = Mock()
        service.torrents.has_byte_range.return_value = True
        probe = {
            "streams": [{"index": 0, "codec_type": "video"}],
            "packets": [
                {
                    "stream_index": 0,
                    "pts_time": "0",
                    "pos": "1024",
                    "size": "4096",
                }
            ],
        }

        with (
            patch.object(MediaService, "_run_probe", return_value=probe),
            patch("app.media.subprocess.run") as decode,
        ):
            self.assertTrue(
                service._prefix_is_playable(
                    {"id": "job-id", "selected_file_index": 0},
                    Path("/data/media/sample.mp4"),
                )
            )

        decode_command = decode.call_args.args[0]
        self.assertIn("-frames:v", decode_command)
        self.assertIn("1", decode_command)
        service.torrents.has_byte_range.assert_called_once_with(
            "job-id", 0, 1024, 5119
        )


if __name__ == "__main__":
    unittest.main()
