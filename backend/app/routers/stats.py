"""Public statistics endpoints consumed by the dashboard."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlmodel import Session

from app.database import get_session
from app.models import Installation, PrunedInstallation
from app.schemas import DailyStat, StatEntry, StatsOut
from app.time_utils import utcnow

router = APIRouter(prefix="/api", tags=["stats"])


def _count_group(session: Session, column) -> list[StatEntry]:
    """Group by *column*, drop empties, sort by count descending."""
    rows = session.exec(
        select(column, func.count(Installation.installation_id))
        .where(column != "")
        .group_by(column)
        .order_by(func.count(Installation.installation_id).desc())
    ).all()
    return [StatEntry(label=str(label), count=int(count)) for label, count in rows]


def _total_installations(session: Session) -> int:
    """All-time installation count: live rows plus pruned tombstones."""
    live = session.exec(select(func.count(Installation.installation_id))).scalar() or 0
    pruned = session.exec(select(func.count(PrunedInstallation.installation_id))).scalar() or 0
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
            select(func.count(Installation.installation_id))
            .where(Installation.last_seen_at >= cutoff)
        ).scalar() or 0

    # Active installations within 24h / 7d / 30d windows.
    active_24h = _active(24)
    active_7d = _active(24 * 7)
    active_30d = _active(24 * 30)

    # Daily distinct-installation counts over the last 30 days.
    cutoff = now - timedelta(days=30)
    rows = session.exec(
        select(
            func.date(Installation.last_seen_at),
            func.count(Installation.installation_id),
        )
        .where(Installation.last_seen_at >= cutoff)
        .group_by(func.date(Installation.last_seen_at))
        .order_by(func.date(Installation.last_seen_at))
    ).all()
    daily = [DailyStat(date=str(date), count=int(count)) for date, count in rows]

    return StatsOut(
        total_installations=int(total_installations),
        active_24h=int(active_24h),
        active_7d=int(active_7d),
        active_30d=int(active_30d),
        versions=_count_group(session, Installation.version),
        operating_systems=_count_group(session, Installation.os),
        architectures=_count_group(session, Installation.architecture),
        runtimes=_count_group(session, Installation.runtime),
        daily=daily,
    )
