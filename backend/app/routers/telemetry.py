"""Telemetry ingestion endpoint.

Intentionally unauthenticated: librislog is open source, so any API key
bundled with it would be public anyway. Spam protection relies on strict
schema validation plus per-IP rate limiting (configured in app/config.py).
The dataset stays bounded because each ``installation_id`` upserts a single
row instead of appending a new event per request.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlmodel import Session

from app.config import settings
from app.database import get_session
from app.models import Installation, PrunedInstallation
from app.schemas import TelemetryIn, TelemetryInV1, TelemetryOut
from app.time_utils import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# Capacity guard: reject bursts over the configured per-minute limit from a
# single IP before they even reach the database. slowapi enforces this across
# all /api/telemetry paths.
from slowapi import Limiter  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

limiter = Limiter(key_func=get_remote_address)


def _apply_common(installation: Installation, payload: TelemetryIn) -> None:
    """Copy the fields shared by every message version onto an Installation row."""
    installation.message_version = payload.message_version


def _apply_version_specific(installation: Installation, payload: TelemetryIn) -> None:
    """Persist the fields declared by a specific message version.

    Each ``TelemetryInV{n}`` model dispatches here. Any payload column that the
    incoming version does not declare is reset to empty, so a version that
    drops a field also clears its stored value.
    """
    # Columns that can carry version-specific values. Fields absent from the
    # incoming message are reset to "" instead of keeping stale data.
    installation.version = ""
    installation.os = ""
    installation.architecture = ""
    installation.runtime = ""

    if isinstance(payload, TelemetryInV1):
        installation.version = payload.version
        installation.os = payload.os
        installation.architecture = payload.architecture
        installation.runtime = payload.runtime
        return

    raise ValueError(f"Unhandled message version: {payload.message_version}")


@router.post(
    "",
    response_model=TelemetryOut,
    status_code=status.HTTP_200_OK,
)
@limiter.limit(lambda: f"{settings.rate_limit_per_minute}/minute")
async def ingest_telemetry(
    request: Request,
    payload: TelemetryIn,
    session: Annotated[Session, Depends(get_session)],
) -> TelemetryOut:
    """Record (or update) one installation's telemetry heartbeat."""
    now = utcnow()
    existing = session.get(Installation, payload.installation_id)

    if existing is None:
        # If this installation was pruned for inactivity, resurrect it: move it
        # back to the live table so it is not double-counted in the all-time
        # "total installations" metric.
        pruned = session.get(PrunedInstallation, payload.installation_id)
        existing = Installation(
            installation_id=payload.installation_id,
            first_seen_at=now,
            last_seen_at=now,
        )
        _apply_common(existing, payload)
        _apply_version_specific(existing, payload)
        session.add(existing)
        if pruned is not None:
            session.delete(pruned)
        logger.info(
            "New installation registered (%s, message v%s): %s",
            payload.installation_id,
            payload.message_version,
            payload.installation_id,
        )
    else:
        _apply_common(existing, payload)
        _apply_version_specific(existing, payload)
        existing.last_seen_at = now

    session.commit()
    return TelemetryOut(installation_id=payload.installation_id)
