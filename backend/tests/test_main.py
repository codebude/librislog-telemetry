"""Tests for app.main: the prune job, rate-limit handler, and proxy middleware."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import _parse_forwarded_allow_ips, _periodic_prune, proxy_headers_middleware


# ── Rate limit handler ───────────────────────────────────────────────────────

def test_rate_limit_handler_returns_429():
    """The rate-limit exception handler returns a 429 with a friendly message."""
    from unittest.mock import MagicMock

    from slowapi.errors import RateLimitExceeded

    from app.main import _rate_limit_handler

    request = MagicMock()
    exc = RateLimitExceeded.__new__(RateLimitExceeded)
    resp = asyncio.run(_rate_limit_handler(request, exc))
    assert resp.status_code == 429
    assert resp.body == b'{"detail":"Too many requests. Please slow down."}'


# ── _parse_forwarded_allow_ips ───────────────────────────────────────────────

def test_parse_forwarded_wildcard():
    assert _parse_forwarded_allow_ips("*") == {"*"}


def test_parse_forwarded_list():
    result = _parse_forwarded_allow_ips("1.2.3.4, 5.6.7.8 9.10.11.12")
    assert result == {"1.2.3.4", "5.6.7.8", "9.10.11.12"}


def test_parse_forwarded_empty():
    assert _parse_forwarded_allow_ips("") == set()


# ── proxy_headers_middleware ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_proxy_middleware_rewrites_forwarded_for(mocker):
    """X-Forwarded-For from a trusted proxy rewrites the client IP."""
    mocker.patch("app.main._TRUSTED_PROXY_IPS", {"10.0.0.1"})
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers.get.return_value = "203.0.113.5, 10.0.0.1"
    request.scope = {"client": ("10.0.0.1", 1234)}

    called = False
    async def call_next(req):
        nonlocal called
        called = True
        return "response"

    result = await proxy_headers_middleware(request, call_next)
    assert called
    assert request.scope["client"][0] == "203.0.113.5"
    assert result == "response"


@pytest.mark.anyio
async def test_proxy_middleware_no_forwarded_header(mocker):
    """Without X-Forwarded-For, the client IP is left untouched."""
    mocker.patch("app.main._TRUSTED_PROXY_IPS", {"10.0.0.1"})
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers.get.return_value = None
    request.scope = {"client": ("10.0.0.1", 1234)}

    async def call_next(req):
        return "response"

    await proxy_headers_middleware(request, call_next)
    assert request.scope["client"][0] == "10.0.0.1"


@pytest.mark.anyio
async def test_proxy_middleware_untrusted_proxy(mocker):
    """Requests from untrusted IPs do not get rewritten."""
    mocker.patch("app.main._TRUSTED_PROXY_IPS", {"10.0.0.1"})
    request = MagicMock()
    request.client.host = "10.0.0.99"
    request.headers.get.return_value = "203.0.113.5"
    request.scope = {"client": ("10.0.0.99", 1234)}

    async def call_next(req):
        return "response"

    await proxy_headers_middleware(request, call_next)
    assert request.scope["client"][0] == "10.0.0.99"


# ── Version display ──────────────────────────────────────────────────────────

def test_display_version_appends_git_sha(mocker):
    """When built with a real git SHA, the version includes it."""
    import importlib

    mocker.patch("app._build_info.__git_sha__", "0123456789abcdef")
    mocker.patch("app._build_info.__version__", "v1.2.3")
    main = importlib.reload(__import__("app.main", fromlist=["_display_version"]))
    assert main._display_version == "v1.2.3 (0123456)"
    # restore default to avoid leaking state
    mocker.patch("app._build_info.__git_sha__", "unknown")
    importlib.reload(main)


def test_display_version_plain_when_unknown(mocker):
    """With an unknown git SHA, the version is shown as-is."""
    import importlib

    mocker.patch("app._build_info.__git_sha__", "unknown")
    mocker.patch("app._build_info.__version__", "v1.2.3")
    main = importlib.reload(__import__("app.main", fromlist=["_display_version"]))
    assert main._display_version == "v1.2.3"


# ── _periodic_prune ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_periodic_prune_success(mocker):
    """The prune loop runs, prunes rows, and logs a summary."""
    mock_prune = mocker.patch(
        "app.services.retention.prune_stale_installations", return_value=3
    )
    # get_session() yields a fake session that supports `with`
    session = MagicMock()
    mocker.patch("app.database.get_session", return_value=iter([session]))
    logger_info = mocker.patch("app.main.logger.info")

    slept = 0
    async def fake_sleep(_seconds):
        nonlocal slept
        slept += 1
        if slept >= 2:
            raise asyncio.CancelledError

    mocker.patch("app.main.asyncio.sleep", side_effect=fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await _periodic_prune(interval_hours=0)

    assert mock_prune.called


@pytest.mark.anyio
async def test_periodic_prune_failure_escalates(mocker):
    """Repeated failures escalate from warning to error."""
    mocker.patch("app.database.get_session", side_effect=RuntimeError("db down"))
    logger_warning = mocker.patch("app.main.logger.warning")
    logger_error = mocker.patch("app.main.logger.error")

    calls = 0
    async def fake_sleep(_seconds):
        nonlocal calls
        calls += 1
        if calls >= 4:
            raise asyncio.CancelledError

    mocker.patch("app.main.asyncio.sleep", side_effect=fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await _periodic_prune(interval_hours=0)

    assert logger_warning.call_count >= 1
    assert logger_error.call_count == 1