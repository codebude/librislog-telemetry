"""Tests for the ENABLE_DOCS setting that toggles /api/docs and the OpenAPI schema."""

import importlib
import os

import app.main as main_module


def _reload_app() -> None:
    """Re-import config (fresh Settings) then main, so env changes take effect."""
    import app.config
    importlib.reload(app.config)
    importlib.reload(main_module)


def _docs_route_paths() -> set[str]:
    return {
        path
        for r in main_module.app.routes
        if (path := getattr(r, "path", None))
        in {"/api/docs", "/api/openapi.json"}
    }


def test_docs_enabled_by_default():
    os.environ.pop("ENABLE_DOCS", None)
    _reload_app()
    assert _docs_route_paths() == {"/api/docs", "/api/openapi.json"}


def test_docs_disabled_via_env():
    os.environ["ENABLE_DOCS"] = "false"
    _reload_app()
    assert _docs_route_paths() == set()

    os.environ.pop("ENABLE_DOCS", None)
    _reload_app()
    assert _docs_route_paths() == {"/api/docs", "/api/openapi.json"}