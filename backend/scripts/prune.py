"""Prune stale installations into the pruned table.

Usage: uv run python scripts/prune.py [days]

Moves installations not seen for *days* (default PRUNE_AFTER_DAYS = 365) to
the pruned table, keeping their IDs so all-time totals stay exact.
"""

import sys

from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.services.retention import prune_stale_installations


def main(days: int) -> None:
    with Session(engine) as session:
        count = prune_stale_installations(session, older_than_days=days)
    print(f"Pruned {count} stale installation(s) (older than {days} days)")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else settings.prune_after_days
    main(days)