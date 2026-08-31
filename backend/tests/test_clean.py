"""Tests for the database clean script helpers."""

from sqlmodel import Session

from app.models import Installation
from app.time_utils import utcnow
from scripts.clean import _counts


def _add(session: Session, installation_id: str) -> None:
    session.add(
        Installation(
            installation_id=installation_id,
            version="v1.0.0",
            first_seen_at=utcnow(),
            last_seen_at=utcnow(),
        )
    )


def test_counts_empty(session: Session):
    assert _counts(session) == (0, 0)


def test_counts_mixed(session: Session):
    _add(session, "seed-0000")
    _add(session, "seed-0001")
    _add(session, "real-install")
    session.commit()
    assert _counts(session) == (2, 3)


def test_counts_seed_prefix_only(session: Session):
    _add(session, "seed-0042")
    session.commit()
    assert _counts(session) == (1, 1)


def test_counts_missing_table_treated_as_empty():
    """A database without the installation table (never migrated) is empty."""
    from sqlmodel import Session as SModelSession, create_engine
    from sqlmodel.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with SModelSession(engine) as session:
        assert _counts(session) == (0, 0)
    engine.dispose()