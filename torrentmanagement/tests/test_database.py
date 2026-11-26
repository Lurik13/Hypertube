"""PostgreSQL repository contract tests using isolated temporary schemas."""

import unittest
from uuid import uuid4

import psycopg
from psycopg import sql

from app.config import Settings
from app.database import Repository


class RepositoryTests(unittest.TestCase):
    """Verify repository behavior without touching application tables."""

    def setUp(self) -> None:
        """Create an isolated PostgreSQL schema for this test instance."""
        self.settings = Settings.from_environment()
        self.schema = f"test_{uuid4().hex}"
        with psycopg.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            dbname=self.settings.db_name,
            user=self.settings.db_user,
            password=self.settings.db_password,
            connect_timeout=self.settings.db_connect_timeout,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema))
            )
        self.repository = Repository(self.settings, schema=self.schema)

    def tearDown(self) -> None:
        """Drop only the schema created by this test instance."""
        with psycopg.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            dbname=self.settings.db_name,
            user=self.settings.db_user,
            password=self.settings.db_password,
            connect_timeout=self.settings.db_connect_timeout,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema))
            )

    @staticmethod
    def job(job_id: str, infohash: str) -> dict[str, object]:
        """Return the minimum complete record shape required for insertion."""
        return {
            "id": job_id,
            "infohash": infohash,
            "torrent_path": "/data/torrents/file.torrent",
            "download_dir": "/data/media/abcd",
            "files": [
                {"index": 0, "path": "film.mp4", "size": 123, "offset": 0, "direct": True}
            ],
            "selected_file_index": 0,
            "selected_file_path": "film.mp4",
            "selected_file_size": 123,
            "selected_file_offset": 0,
            "state": "queued",
            "playback_mode": "direct",
            "conversion_state": "not_required",
        }

    def test_infohash_is_unique_and_returns_existing_job(self) -> None:
        """A duplicate infohash resolves to its original job, not a second row."""
        first = self.repository.create_job(self.job("first", "hash"))
        duplicate = self.repository.create_job(self.job("second", "hash"))
        self.assertEqual(first["id"], "first")
        self.assertEqual(duplicate["id"], "first")
        self.assertEqual(len(self.repository.list_jobs()), 1)

    def test_cleanup_removes_job_and_dependent_subtitles(self) -> None:
        """Cleanup removes both jobs and subtitle records in the test schema."""
        self.repository.create_job(self.job("first", "hash"))
        self.repository.add_subtitle(
            {
                "id": "subtitle",
                "job_id": "first",
                "language": "en",
                "filename": "film.en.srt",
                "path": "/data/subtitles/film.en.srt",
                "provider": "SubDL",
            }
        )
        self.repository.clear_all()
        self.assertEqual(self.repository.list_jobs(), [])
        self.assertEqual(self.repository.list_subtitles("first"), [])

    def test_update_status_can_clear_error_without_overwriting_other_fields(self) -> None:
        """Passing error=None clears an old error while updating the state."""
        self.repository.create_job(self.job("first", "hash"))
        self.repository.update_status("first", state="failed", error="old_error")
        self.repository.update_status("first", state="downloading", error=None)
        job = self.repository.get_job("first")
        self.assertIsNotNone(job)
        self.assertEqual(job["state"], "downloading")
        self.assertIsNone(job["error"])


if __name__ == "__main__":
    unittest.main()
