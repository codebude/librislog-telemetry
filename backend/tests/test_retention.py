"""Tests for the retention (prune) service."""

from datetime import timedelta

from sqlmodel import Session, select

from app.models import Installation, PrunedInstallation
from app.services.retention import prune_stale_installations
from app.time_utils import utcnow


def _add(session: Session, installation_id: str, *, days_ago: int) -> None:
    now = utcnow()
    session.add(
        Installation(
            installation_id=installation_id,
            version="v1.0.0",
            first_seen_at=now - timedelta(days=days_ago),
            last_seen_at=now - timedelta(days=days_ago),
        )
    )


def test_prune_moves_only_stale(session: Session):
    _add(session, "stale-1", days_ago=40)
    _add(session, "fresh-1", days_ago=5)
    session.commit()

    pruned = prune_stale_installations(session, older_than_days=30)
    assert pruned == 1

    live = {i.installation_id for i in session.exec(select(Installation)).all()}
    pruned_rows = session.exec(select(PrunedInstallation)).all()
    assert live == {"fresh-1"}
    assert {p.installation_id for p in pruned_rows} == {"stale-1"}


def test_prune_preserves_all_time_installations(session: Session):
    _add(session, "stale-1", days_ago=40)
    _add(session, "fresh-1", days_ago=5)
    session.commit()

    prune_stale_installations(session, older_than_days=30)

    live = session.exec(select(Installation)).all()
    pruned = session.exec(select(PrunedInstallation)).all()
    assert len(live) + len(pruned) == 2


def test_prune_no_stale_is_noop(session: Session):
    _add(session, "fresh-1", days_ago=5)
    session.commit()
    assert prune_stale_installations(session, older_than_days=30) == 0
    assert len(session.exec(select(PrunedInstallation)).all()) == 0