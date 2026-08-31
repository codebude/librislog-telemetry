"""Tests for the public stats endpoint."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Installation, PrunedInstallation
from app.time_utils import utcnow


def _seed(session: Session, installation_id: str, **overrides) -> None:
    data = {
        "installation_id": installation_id,
        "version": "v1.0.0",
        "os": "Linux",
        "architecture": "x64",
        "runtime": "docker",
        "first_seen_at": utcnow(),
        "last_seen_at": utcnow(),
    }
    data.update(overrides)
    session.add(Installation(**data))


def test_empty_stats(client: TestClient):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_installations"] == 0
    assert body["active_24h"] == 0


def test_stats_aggregation(client: TestClient, session: Session):
    now = utcnow()
    _seed(session, "a", version="v1.0.0", os="Linux", runtime="docker", last_seen_at=now)
    _seed(session, "b", version="v1.0.0", os="macOS", runtime="pipx", last_seen_at=now)
    _seed(session, "c", version="v1.1.0", os="Linux", runtime="docker", last_seen_at=now - timedelta(days=3))
    _seed(session, "d", version="v1.1.0", os="Linux", runtime="docker", last_seen_at=now - timedelta(days=10))
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_installations"] == 4
    assert body["active_24h"] == 2
    assert body["active_7d"] == 3
    assert body["active_30d"] == 4

    versions = {e["label"]: e["count"] for e in body["versions"]}
    assert versions == {"v1.0.0": 2, "v1.1.0": 2}

    oss = {e["label"]: e["count"] for e in body["operating_systems"]}
    assert oss == {"Linux": 3, "macOS": 1}

    runtimes = {e["label"]: e["count"] for e in body["runtimes"]}
    assert runtimes == {"docker": 3, "pipx": 1}

    assert body["daily"], "daily should contain at least one entry"
    assert body["daily"][0]["date"].startswith("20")


def test_stats_dashboard_page(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "LibrisLog" in resp.text
    assert "chart-daily" in resp.text


def test_stats_include_pruned_in_all_time_totals(client: TestClient, session: Session):
    """Pruned rows still count toward the all-time installation total."""
    now = utcnow()
    _seed(session, "a", version="v1.0.0", os="Linux", runtime="docker", last_seen_at=now)
    session.add(
        PrunedInstallation(
            installation_id="old-b",
            pruned_at=now - timedelta(days=40),
        )
    )
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_installations"] == 2
    assert body["active_24h"] == 1