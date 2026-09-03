"""Retention: move stale installations to the pruned table and purge old daily activity."""

import logging
from datetime import timedelta

from sqlmodel import Session, col, delete, select

from app.models import DailyActivity, Installation, PrunedInstallation
from app.time_utils import utcnow

logger = logging.getLogger(__name__)


def prune_stale_installations(session: Session, *, older_than_days: int) -> int:
    """Move installations not seen for *older_than_days* to the pruned table.

    Each pruned row keeps its ``installation_id`` so the all-time
    "total installations" metric stays exact (see the ``PrunedInstallation``
    docstring).

    Returns the number of installations pruned.
    """
    cutoff = utcnow() - timedelta(days=older_than_days)
    stale = session.exec(
        select(Installation).where(Installation.last_seen_at < cutoff)
    ).all()

    now = utcnow()
    for installation in stale:
        session.add(
            PrunedInstallation(
                installation_id=installation.installation_id,
                pruned_at=now,
            )
        )
        session.delete(installation)
        logger.info(
            "Pruned stale installation %s (last seen %s)",
            installation.installation_id,
            installation.last_seen_at,
        )

    session.commit()
    return len(stale)


def prune_stale_daily_activity(session: Session, *, keep_days: int) -> int:
    """Delete daily activity rows older than *keep_days*.

    The dashboard only shows the last 30 days of daily activity, so older rows
    can be dropped to keep the table small. Returns the number of rows deleted.
    """
    cutoff = (utcnow() - timedelta(days=keep_days)).date().isoformat()
    result = session.exec(
        delete(DailyActivity).where(col(DailyActivity.activity_date) < cutoff)
    )
    session.commit()
    if result.rowcount:
        logger.info("Pruned %d stale daily-activity row(s)", result.rowcount)
    return int(result.rowcount)