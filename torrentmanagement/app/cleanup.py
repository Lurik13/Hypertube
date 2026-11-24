import shutil

from app.config import Settings
from app.database import Repository


def main() -> None:
    settings = Settings.from_environment()
    settings.initialize_directories()
    repository = Repository(settings.data_dir / "torrentmanagement.sqlite3")
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
