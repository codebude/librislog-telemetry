"""Clean seeded (or all) telemetry data from the database.

Usage: uv run python scripts/clean.py --status
       uv run python scripts/clean.py --seed
       uv run python scripts/clean.py --all

This script only executes the requested operation; the interactive confirmation
is handled by the CLI (``ltel clean``) before invoking it.
"""

import argparse

from sqlalchemy import delete
from sqlmodel import Session, col, func, inspect, select

from app.database import engine
from app.models import Installation

SEED_PREFIX = "seed-"


def _counts(session: Session) -> tuple[int, int]:
    """Return ``(seed_row_count, total_row_count)``.

    If the ``installation`` table does not exist yet (e.g. migrations have
    never been run), the database is treated as empty.
    """
    inspector = inspect(session.bind)
    if inspector is None or "installation" not in inspector.get_table_names():
        return 0, 0
    total = session.exec(select(func.count(col(Installation.installation_id)))).one()
    seed = (
        session.exec(
            select(func.count(col(Installation.installation_id))).where(
                col(Installation.installation_id).like(f"{SEED_PREFIX}%")
            )
        ).one()
    )
    return seed, total


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean seeded telemetry data.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Print row counts and exit")
    group.add_argument("--seed", action="store_true", help="Delete seeded rows only")
    group.add_argument("--all", action="store_true", help="Delete every installation row")
    args = parser.parse_args()

    with Session(engine) as session:
        seed_count, total_count = _counts(session)

        if args.status:
            print(f"seed_rows={seed_count}")
            print(f"total_rows={total_count}")
            return

        if args.seed:
            result = session.exec(
                delete(Installation).where(
                    col(Installation.installation_id).like(f"{SEED_PREFIX}%")
                )
            )
            session.commit()
            print(f"Deleted {result.rowcount} seeded installation(s)")

        elif args.all:
            result = session.exec(delete(Installation))
            session.commit()
            print(f"Deleted {result.rowcount} installation(s)")


if __name__ == "__main__":
    main()