"""Serves the public dashboard HTML page."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

_DASHBOARD = Path(__file__).resolve().parent.parent / "static" / "dashboard.html"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Return the public dashboard page."""
    html = _DASHBOARD.read_text(encoding="utf-8")
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")
