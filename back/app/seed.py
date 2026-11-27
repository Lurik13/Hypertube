"""Fill the local database with fake data for testing: `make seed`.

Idempotent (existing rows are skipped). Development only. Each feature task
adds its own seeder (movies, comments, ...) to SEEDERS.
"""

from collections.abc import Callable

from sqlalchemy import Connection
from sqlalchemy.dialects.postgresql import insert

from app.db import get_sync_engine
from app.models import User
from app.security import hash_password

SEED_PASSWORD = "Hypertube42!"

SEED_USERS = [
    ("alice", "Alice", "Martin"),
    ("bob", "Bob", "Durand"),
    ("chloe", "Chloé", "Bernard"),
    ("david", "David", "Petit"),
    ("emma", "Emma", "Leroy"),
]


def seed_users(conn: Connection) -> int:
    rows = [
        {
            "email": f"{username}@example.com",
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "password_hash": hash_password(SEED_PASSWORD),
        }
        for username, first_name, last_name in SEED_USERS
    ]
    return len(conn.execute(insert(User).values(rows).on_conflict_do_nothing().returning(User.id)).all())


SEEDERS: list[Callable[[Connection], int]] = [seed_users]


def main() -> None:
    with get_sync_engine().begin() as conn:
        for seeder in SEEDERS:
            print(f"{seeder.__name__}: {seeder(conn)} rows inserted")
    print(f"Seed users log in with password {SEED_PASSWORD!r}")


if __name__ == "__main__":
    main()
