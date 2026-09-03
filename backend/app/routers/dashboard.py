"""Serves the public dashboard HTML page and its favicon."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["dashboard"])

_STATIC = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD = _STATIC / "dashboard.html"
_FAVICON = _STATIC / "favicon.svg"


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Return the public dashboard page."""
    html = _DASHBOARD.read_text(encoding="utf-8")
    return HTMLResponse(content=html, media_type="text/html; charset=utf-8")


@router.get("/favicon.ico", response_class=Response, include_in_schema=False)
async def favicon() -> Response:
    """Return the dashboard favicon."""
    svg = _FAVICON.read_bytes()
    return Response(content=svg, media_type="image/svg+xml")
