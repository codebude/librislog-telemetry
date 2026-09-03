"""Seed the database with fake telemetry data for local dashboard development.

Usage: uv run python scripts/seed.py [count]

The script is idempotent: rows whose ``seed-`` installation id already exists
are skipped, so re-running it never crashes on a UNIQUE constraint.
"""

import random
import sys
from datetime import timedelta

from sqlmodel import Session, col, select

from app.database import engine
from app.models import DailyActivity, Installation
from app.time_utils import utcnow

_VERSIONS = ["v0.9.0", "v1.0.0", "v1.0.1", "v1.1.0", "v1.2.0"]
_OS = ["Linux", "macOS", "Windows"]
_ARCHS = ["x64", "ARM64", "ARM"]
_RUNTIMES = ["docker", "pipx", "source"]


def _existing_ids(session: Session, count: int) -> set[str]:
    """Return the seed installation ids already present for ids 0..count-1."""
    ids = [f"seed-{i:04d}" for i in range(count)]
    rows = session.exec(
        select(col(Installation.installation_id)).where(
            col(Installation.installation_id).in_(ids)
        )
    ).all()
    return set(rows)


def main(count: int) -> None:
    now = utcnow()
    added = 0
    with Session(engine) as session:
        existing = _existing_ids(session, count)
        for i in range(count):
            if f"seed-{i:04d}" in existing:
                continue
            first_seen = now - timedelta(days=random.randint(0, 200), hours=random.randint(0, 23))
            last_seen = min(
                first_seen + timedelta(days=random.randint(0, 60), hours=random.randint(0, 23)),
                now,
            )
            install_id = f"seed-{i:04d}"
            session.add(
                Installation(
                    installation_id=install_id,
                    version=random.choice(_VERSIONS),
                    os=random.choice(_OS),
                    architecture=random.choice(_ARCHS),
                    runtime=random.choice(_RUNTIMES),
                    first_seen_at=first_seen,
                    last_seen_at=last_seen,
                )
            )
            # Mirror ingest: add daily-activity rows for each day this install pings.
            day = last_seen.date()
            for offset in range(0, random.randint(1, min(14, (now.date() - day).days + 1))):
                activity_date = (now - timedelta(days=offset)).date().isoformat()
                session.add(
                    DailyActivity(
                        installation_id=install_id,
                        activity_date=activity_date,
                    )
                )
            added += 1
        session.commit()
    print(f"Seeded {added} new installation(s) ({count - added} already present)")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    main(count)