"""Public statistics endpoints consumed by the dashboard."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session, col, func, select

from app._build_info import __version__
from app.database import get_session
from app.models import DailyActivity, Installation, PrunedInstallation
from app.schemas import (
    DailyStat,
    LongevityEntry,
    NewInstallDaily,
    NewInstallMonthly,
    StatEntry,
    StatsOut,
    VersionMixEntry,
)
from app.time_utils import utcnow

router = APIRouter(prefix="/api", tags=["stats"])

_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


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


def _active_counts(session: Session, now) -> tuple[int, int]:
    """Return ``(active_7d, active_30d)``."""
    def _active(hours: int) -> int:
        cutoff = now - timedelta(hours=hours)
        return session.exec(
            select(func.count(col(Installation.installation_id)))
            .where(col(Installation.last_seen_at) >= cutoff)
        ).one()

    return _active(24 * 7), _active(24 * 30)


def _daily_activity(session: Session, now) -> list[DailyStat]:
    """Distinct installations active per day over the last 30 days.

    Counts from the ``daily_activity`` table (one row per installation per day),
    so an installation that pings every day is counted on *every* day, not just
    its most recent ping.
    """
    cutoff = (now - timedelta(days=30)).date().isoformat()
    rows = session.exec(
        select(
            col(DailyActivity.activity_date),
            func.count(col(DailyActivity.installation_id)),
        )
        .where(col(DailyActivity.activity_date) >= cutoff)
        .group_by(col(DailyActivity.activity_date))
        .order_by(col(DailyActivity.activity_date))
    ).all()
    return [DailyStat(date=str(date), count=int(count)) for date, count in rows]


def _new_install_daily(session: Session, now) -> list[NewInstallDaily]:
    """Installations first seen per day over the last 30 days."""
    cutoff = now - timedelta(days=30)
    rows = session.exec(
        select(
            func.date(col(Installation.first_seen_at)),
            func.count(col(Installation.installation_id)),
        )
        .where(col(Installation.first_seen_at) >= cutoff)
        .group_by(func.date(col(Installation.first_seen_at)))
        .order_by(func.date(col(Installation.first_seen_at)))
    ).all()
    return [NewInstallDaily(date=str(date), count=int(count)) for date, count in rows]


def _new_install_monthly(session: Session, now) -> list[NewInstallMonthly]:
    """Installations first seen per month over the last 12 months."""
    cutoff = now - timedelta(days=365)
    month = func.strftime("%Y-%m", col(Installation.first_seen_at))
    rows = session.exec(
        select(month, func.count(col(Installation.installation_id)))
        .where(col(Installation.first_seen_at) >= cutoff)
        .group_by(month)
        .order_by(month)
    ).all()
    return [NewInstallMonthly(month=str(month_key), count=int(count)) for month_key, count in rows]


def _longevity(session: Session, now) -> list[LongevityEntry]:
    """Active installations bucketed by how long they've existed.

    Buckets mirror the dashboard's "active 30d" scope: only installations that
    checked in within the last 30 days are counted.
    """
    active_since = now - timedelta(days=30)
    week = now - timedelta(days=7)
    month = now - timedelta(days=30)
    three_months = now - timedelta(days=90)

    def _bucket(floor: datetime, *, upper: datetime | None = None) -> int:
        stmt = (
            select(func.count(col(Installation.installation_id)))
            .where(col(Installation.last_seen_at) >= active_since)
            .where(col(Installation.first_seen_at) >= floor)
        )
        if upper is not None:
            stmt = stmt.where(col(Installation.first_seen_at) < upper)
        return session.exec(stmt).one()

    return [
        LongevityEntry(label="< 1 week", count=int(_bucket(week))),
        LongevityEntry(label="1-4 weeks", count=int(_bucket(month, upper=week))),
        LongevityEntry(label="1-3 months", count=int(_bucket(three_months, upper=month))),
        LongevityEntry(label="3+ months", count=int(_bucket(_OLDEST, upper=three_months))),
    ]


def _version_mix(session: Session, now) -> list[VersionMixEntry]:
    """Version distribution of active installations per day, last 30 days."""
    cutoff = now - timedelta(days=30)
    rows = session.exec(
        select(
            func.date(col(Installation.last_seen_at)),
            col(Installation.version),
            func.count(col(Installation.installation_id)),
        )
        .where(col(Installation.last_seen_at) >= cutoff)
        .where(col(Installation.version) != "")
        .group_by(func.date(col(Installation.last_seen_at)), col(Installation.version))
        .order_by(func.date(col(Installation.last_seen_at)))
    ).all()

    by_date: dict[str, list[StatEntry]] = {}
    for date, version, count in rows:
        by_date.setdefault(str(date), []).append(StatEntry(label=str(version), count=int(count)))
    return [
        VersionMixEntry(date=str(date), versions=entries)
        for date, entries in sorted(by_date.items())
    ]


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: Annotated[Session, Depends(get_session)],
) -> StatsOut:
    """Return aggregate statistics for the public dashboard."""
    now = utcnow()

    total_installations = _total_installations(session)
    active_7d, active_30d = _active_counts(session, now)

    cutoff = now - timedelta(days=30)
    return StatsOut(
        total_installations=int(total_installations),
        active_7d=int(active_7d),
        active_30d=int(active_30d),
        versions=_count_group(session, Installation.version, active_since=cutoff),
        operating_systems=_count_group(session, Installation.os, active_since=cutoff),
        architectures=_count_group(session, Installation.architecture, active_since=cutoff),
        runtimes=_count_group(session, Installation.runtime, active_since=cutoff),
        daily=_daily_activity(session, now),
        new_daily=_new_install_daily(session, now),
        new_monthly=_new_install_monthly(session, now),
        longevity=_longevity(session, now),
        version_mix=_version_mix(session, now),
        server_version=__version__,
    )