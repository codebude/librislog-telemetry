"""Tests for the database seed script helpers."""

from sqlmodel import Session

from app.models import Installation
from app.time_utils import utcnow
from scripts.seed import _existing_ids


def _add_seed(session: Session, index: int) -> None:
    session.add(
        Installation(
            installation_id=f"seed-{index:04d}",
            version="v1.0.0",
            event_count=1,
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
        )
    )


def test_existing_ids_empty(session: Session):
    assert _existing_ids(session, 25) == set()


def test_existing_ids_partial(session: Session):
    _add_seed(session, 0)
    _add_seed(session, 4)
    session.commit()
    assert _existing_ids(session, 5) == {"seed-0000", "seed-0004"}


def test_existing_ids_does_not_include_non_seed(session: Session):
    session.add(
        Installation(
            installation_id="real-install",
            version="v1.0.0",
            event_count=1,
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
        )
    )
    session.commit()
    assert _existing_ids(session, 25) == set()