"""Health check endpoint — database connectivity and schema."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlmodel import Session

from app._build_info import __git_sha__, __version__
from app.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
async def health(
    db_session: Annotated[Session, Depends(get_session)],
) -> dict:
    """Return the health status of the application and its dependencies."""
    checks: dict[str, dict] = {}
    overall_healthy = True

    def _result(*, healthy: bool, detail: str | None = None) -> dict:
        return {
            "status": "healthy" if healthy else "unhealthy",
            **( {"detail": detail} if detail else {} ),
        }

    # Database connectivity
    db_ok = True
    db_detail = None
    try:
        db_session.connection().execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_detail = str(exc)
        logger.warning("Health check failed — database connectivity: %s", exc)
    checks["database_connectivity"] = _result(healthy=db_ok, detail=db_detail)
    overall_healthy = overall_healthy and db_ok

    # Database schema
    schema_ok = True
    schema_detail = None
    try:
        inspector = inspect(db_session.bind)
        if inspector is None:
            raise RuntimeError("Engine binding returned no inspector")
        existing = set(inspector.get_table_names())
        missing = {"installation"} - existing
        if missing:
            schema_ok = False
            schema_detail = f"Missing tables: {', '.join(sorted(missing))}"
    except Exception as exc:
        schema_ok = False
        schema_detail = str(exc)
        logger.warning("Health check failed — database schema: %s", exc)
    checks["database_schema"] = _result(healthy=schema_ok, detail=schema_detail)
    overall_healthy = overall_healthy and schema_ok

    checks["app_version"] = {
        "version": __version__,
        "git_sha": __git_sha__,
    }

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "checks": checks,
    }
