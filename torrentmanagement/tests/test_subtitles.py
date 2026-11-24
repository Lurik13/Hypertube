import unittest

from app.subtitles import SubtitleProviderError, SubDLProvider


class SubtitlePayloadTests(unittest.TestCase):
    def test_rejects_html_instead_of_saving_it_as_a_subtitle(self) -> None:
        with self.assertRaises(SubtitleProviderError):
            SubDLProvider._payload_file(
                b"<html>not a subtitle</html>",
                "text/html",
                {"filename": "movie.srt"},
            )


if __name__ == "__main__":
    unittest.main()
