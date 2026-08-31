"""SQLModel ORM models for librislog-telemetry database tables."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, TypeDecorator
from sqlmodel import Field, SQLModel

from app.time_utils import utcnow


class UtcDateTime(TypeDecorator):
    """SQLAlchemy type decorator that stores aware datetimes as naive UTC.

    On bind: converts aware datetime to UTC and strips tzinfo.
    On result: attaches UTC tzinfo to the returned value.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        """Convert aware datetime to naive UTC before storing."""
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        """Attach UTC tzinfo to the value returned from the database."""
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Installation(SQLModel, table=True):
    """A single librislog installation, upserted on every telemetry heartbeat.

    One row per unique ``installation_id`` — the dataset stays bounded even if
    bots post garbage: a flood of fake IDs only creates one (mostly empty) row
    per unique ID instead of one row per request.
    """

    __tablename__: str = "installation"

    installation_id: str = Field(primary_key=True, max_length=64)
    message_version: int = Field(default=1)
    version: str = Field(default="", max_length=32, index=True)
    os: str = Field(default="", max_length=32, index=True)
    architecture: str = Field(default="", max_length=32, index=True)
    runtime: str = Field(default="", max_length=64)
    first_seen_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow, index=True),
    )
    last_seen_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow, index=True),
    )


class PrunedInstallation(SQLModel, table=True):
    """A tombstone row for an installation that was pruned for inactivity.

    Keeps the ``installation_id`` so the all-time "total installations" metric
    stays exact after pruning (``total_installations`` = count(installation) +
    count(pruned_installation)).

    If a pruned installation checks in again, the row is moved back to the
    live ``installation`` table, so it is never counted twice.
    """

    __tablename__: str = "pruned_installation"

    installation_id: str = Field(primary_key=True, max_length=64)
    pruned_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(UtcDateTime, default=utcnow, index=True),
    )
