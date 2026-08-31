"""Seed the database with fake telemetry data for local dashboard development.

Usage: uv run python scripts/seed.py [count]
"""

import random
import sys
from datetime import timedelta

from sqlmodel import Session

from app.database import engine
from app.models import Installation
from app.time_utils import utcnow

_VERSIONS = ["v0.9.0", "v1.0.0", "v1.0.1", "v1.1.0", "v1.2.0"]
_OS = ["Linux", "macOS", "Windows"]
_ARCHS = ["x64", "ARM64", "ARM"]
_RUNTIMES = ["docker", "pipx", "source"]


def main(count: int) -> None:
    now = utcnow()
    with Session(engine) as session:
        for i in range(count):
            first_seen = now - timedelta(days=random.randint(0, 200), hours=random.randint(0, 23))
            last_seen = min(
                first_seen + timedelta(days=random.randint(0, 60), hours=random.randint(0, 23)),
                now,
            )
            session.add(
                Installation(
                    installation_id=f"seed-{i:04d}",
                    version=random.choice(_VERSIONS),
                    os=random.choice(_OS),
                    architecture=random.choice(_ARCHS),
                    runtime=random.choice(_RUNTIMES),
                    event_count=random.randint(1, 400),
                    first_seen_at=first_seen,
                    last_seen_at=last_seen,
                )
            )
        session.commit()
    print(f"Seeded {count} installations")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    main(count)