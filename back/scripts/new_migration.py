"""Render a new, empty Alembic revision and print it to stdout.

Used by `make migration`: the file is written on the host by the shell, so it
belongs to the developer whatever the container's user mapping is.
Usage: python scripts/new_migration.py <rev_id> <message>
"""

import contextlib
import shutil
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def main(rev_id: str, message: str) -> None:
    # The image is read-only: render into a copy of the migrations folder.
    workdir = Path("/tmp/alembic")
    shutil.rmtree(workdir, ignore_errors=True)
    shutil.copytree("alembic", workdir)
    config = Config("alembic.ini")
    config.set_main_option("script_location", str(workdir))
    with contextlib.redirect_stdout(sys.stderr):
        script = command.revision(config, message=message, rev_id=rev_id)
    sys.stdout.write(Path(script.path).read_text())


if __name__ == "__main__":
    main(*sys.argv[1:3])
