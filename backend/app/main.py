"""FastAPI application factory and middleware setup."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from app._build_info import __git_sha__, __version__
from app.config import settings
from app.logging_config import configure_logging
from app.routers import dashboard, health, stats, telemetry

logger = logging.getLogger(__name__)

configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: create the data directory."""
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    yield


if __git_sha__ != "unknown" and __version__.find(__git_sha__[:7]) == -1:
    _display_version = f"{__version__} ({__git_sha__[:7]})"
else:
    _display_version = __version__

app = FastAPI(
    title="LibrisLog Telemetry API",
    description="Anonymous, aggregate telemetry API for LibrisLog.",
    version=_display_version,
    lifespan=lifespan,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting for the (intentionally public) ingestion endpoint.
app.state.limiter = telemetry.limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})


def _parse_forwarded_allow_ips(value: str) -> set[str]:
    """Parse the comma/space-separated ``forwarded_allow_ips`` setting."""
    if value.strip() == "*":
        return {"*"}
    return {ip.strip() for ip in value.replace(",", " ").split() if ip.strip()}


_TRUSTED_PROXY_IPS = _parse_forwarded_allow_ips(settings.forwarded_allow_ips)


@app.middleware("http")
async def proxy_headers_middleware(request: Request, call_next):
    """Respect ``X-Forwarded-For`` from trusted proxies so rate limiting uses
    the real client IP behind a reverse proxy (e.g. Traefik on Hetzner)."""
    if "*" in _TRUSTED_PROXY_IPS or (request.client and request.client.host in _TRUSTED_PROXY_IPS):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            request.scope["client"] = (forwarded_for.split(",")[0].strip(), request.scope.get("client", (None,))[1])
    return await call_next(request)


app.include_router(health.router)
app.include_router(stats.router)
app.include_router(telemetry.router)
app.include_router(dashboard.router)
