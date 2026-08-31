"""Tests for the health endpoint, including failure branches."""

import asyncio
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.routers.health import health


def _run_health(session: Mock) -> dict:
    """Run the async health handler with a mocked session."""
    return asyncio.run(health(db_session=session))


def test_health_ok(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database_connectivity"]["status"] == "healthy"
    assert body["checks"]["database_schema"]["status"] == "healthy"
    assert "version" in body["checks"]["app_version"]


def test_health_database_connectivity_failure(client: TestClient, mocker):
    """When SELECT 1 fails, connectivity reports unhealthy."""
    session = Mock()
    conn = Mock()
    conn.execute.side_effect = RuntimeError("connection refused")
    session.connection.return_value = conn

    result = _run_health(session)
    assert result["status"] == "unhealthy"
    assert result["checks"]["database_connectivity"]["status"] == "unhealthy"
    assert "connection refused" in result["checks"]["database_connectivity"]["detail"]


def test_health_schema_missing_tables(client: TestClient, mocker):
    """Missing tables make the schema check unhealthy."""
    session = Mock()
    conn = Mock()
    conn.execute.return_value = None
    session.connection.return_value = conn

    inspector = Mock()
    inspector.get_table_names.return_value = set()
    mocker.patch("app.routers.health.inspect", return_value=inspector)

    result = _run_health(session)
    assert result["status"] == "unhealthy"
    schema = result["checks"]["database_schema"]
    assert schema["status"] == "unhealthy"
    assert "installation" in schema["detail"]
    assert "pruned_installation" in schema["detail"]


def test_health_schema_inspector_none(client: TestClient, mocker):
    """A None inspector is treated as a schema failure."""
    session = Mock()
    conn = Mock()
    conn.execute.return_value = None
    session.connection.return_value = conn

    mocker.patch("app.routers.health.inspect", return_value=None)

    result = _run_health(session)
    schema = result["checks"]["database_schema"]
    assert schema["status"] == "unhealthy"
    assert "no inspector" in schema["detail"].lower()


def test_health_schema_exception(client: TestClient, mocker):
    """An unexpected schema-check exception is reported as unhealthy."""
    session = Mock()
    conn = Mock()
    conn.execute.return_value = None
    session.connection.return_value = conn

    def boom():
        raise RuntimeError("boom")
    mocker.patch("app.routers.health.inspect", side_effect=boom)

    result = _run_health(session)
    schema = result["checks"]["database_schema"]
    assert schema["status"] == "unhealthy"
    assert "boom" in schema["detail"]