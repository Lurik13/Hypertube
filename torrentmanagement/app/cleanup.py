"""Clear Torrentmanagement metadata and managed files for operator cleanup."""

import shutil

from app.config import Settings
from app.database import Repository


def main() -> None:
    """Delete managed media and PostgreSQL records without removing its volume."""
    settings = Settings.from_environment()
    settings.initialize_directories()
    repository = Repository(settings)
    repository.clear_all()
    for name in ("torrents", "media", "converted", "subtitles", "tmp"):
        directory = settings.data_dir / name
        for child in directory.iterdir():
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
