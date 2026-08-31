"""Public statistics endpoints consumed by the dashboard."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from app._build_info import __version__
from app.database import get_session
from app.models import Installation, PrunedInstallation
from app.schemas import DailyStat, StatEntry, StatsOut
from app.time_utils import utcnow

router = APIRouter(prefix="/api", tags=["stats"])


def _count_group(session: Session, column, *, active_since) -> list[StatEntry]:
    """Group *column* counts for installations active since *active_since*.

    Only "active" installations (those that reported within the retention /
    dashboard window) count toward the breakdowns; stale ones are excluded.
    Drops empties, sorts by count descending.
    """
    rows = session.exec(
        select(column, func.count(col(Installation.installation_id)))
        .where(col(column) != "")
        .where(col(Installation.last_seen_at) >= active_since)
        .group_by(column)
        .order_by(func.count(col(Installation.installation_id)).desc())
    ).all()
    return [StatEntry(label=str(label), count=int(count)) for label, count in rows]


def _total_installations(session: Session) -> int:
    """All-time installation count: live rows plus pruned tombstones."""
    live = session.exec(
        select(func.count(col(Installation.installation_id)))
    ).one()
    pruned = session.exec(
        select(func.count(col(PrunedInstallation.installation_id)))
    ).one()
    return int(live + pruned)


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: Annotated[Session, Depends(get_session)],
) -> StatsOut:
    """Return aggregate statistics for the public dashboard."""
    now = utcnow()

    total_installations = _total_installations(session)

    def _active(hours: int) -> int:
        cutoff = now - timedelta(hours=hours)
        return session.exec(
            select(func.count(col(Installation.installation_id)))
            .where(col(Installation.last_seen_at) >= cutoff)
        ).one()

    # Active installations within 7d / 30d windows.
    active_7d = _active(24 * 7)
    active_30d = _active(24 * 30)

    # Daily distinct-installation counts over the last 30 days.
    cutoff = now - timedelta(days=30)
    rows = session.exec(
        select(
            func.date(col(Installation.last_seen_at)),
            func.count(col(Installation.installation_id)),
        )
        .where(col(Installation.last_seen_at) >= cutoff)
        .group_by(func.date(col(Installation.last_seen_at)))
        .order_by(func.date(col(Installation.last_seen_at)))
    ).all()
    daily = [DailyStat(date=str(date), count=int(count)) for date, count in rows]

    return StatsOut(
        total_installations=int(total_installations),
        active_7d=int(active_7d),
        active_30d=int(active_30d),
        versions=_count_group(session, Installation.version, active_since=cutoff),
        operating_systems=_count_group(session, Installation.os, active_since=cutoff),
        architectures=_count_group(session, Installation.architecture, active_since=cutoff),
        runtimes=_count_group(session, Installation.runtime, active_since=cutoff),
        daily=daily,
        server_version=__version__,
    )
