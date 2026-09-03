"""Tests for the public stats endpoint."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import DailyActivity, Installation, PrunedInstallation
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
    # Mirror the ingest behaviour: one DailyActivity row per day the install pings.
    activity_date = data["last_seen_at"].date().isoformat()
    session.add(DailyActivity(installation_id=installation_id, activity_date=activity_date))


def test_empty_stats(client: TestClient):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_installations"] == 0
    assert body["active_7d"] == 0
    assert body["active_30d"] == 0


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
    assert 'href="/favicon.ico"' in resp.text


def test_favicon_served(client: TestClient):
    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert resp.content.startswith(b"<svg")


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
    assert body["active_7d"] == 1


def test_breakdowns_exclude_inactive_installations(client: TestClient, session: Session):
    """Breakdown charts only count installations active within the last 30 days."""
    now = utcnow()
    _seed(session, "active-a", version="v1.0.0", os="Linux", runtime="docker", last_seen_at=now)
    _seed(session, "active-b", version="v2.0.0", os="macOS", runtime="pipx", last_seen_at=now - timedelta(days=10))
    # Stale: reported 60 days ago — must not appear in breakdowns.
    _seed(session, "stale-c", version="v0.5.0", os="Windows", runtime="source", last_seen_at=now - timedelta(days=60))
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()

    # All-time + active counts include the stale row.
    assert body["total_installations"] == 3
    assert body["active_30d"] == 2

    # Breakdowns exclude the stale installation entirely.
    versions = {e["label"]: e["count"] for e in body["versions"]}
    assert versions == {"v1.0.0": 1, "v2.0.0": 1}
    assert "v0.5.0" not in versions

    oss = {e["label"]: e["count"] for e in body["operating_systems"]}
    assert oss == {"Linux": 1, "macOS": 1}
    assert "Windows" not in oss

    runtimes = {e["label"]: e["count"] for e in body["runtimes"]}
    assert runtimes == {"docker": 1, "pipx": 1}
    assert "source" not in runtimes


def test_new_install_and_longevity_stats(client: TestClient, session: Session):
    """New installs (daily/monthly) and longevity buckets are computed."""
    now = utcnow()
    # 2 new installs this month, one 2 months old, one 4 months old.
    _seed(session, "new-1", version="v1.0.0", os="Linux", runtime="docker",
          first_seen_at=now - timedelta(days=1), last_seen_at=now - timedelta(days=1))
    _seed(session, "new-2", version="v1.0.0", os="Linux", runtime="docker",
          first_seen_at=now - timedelta(days=2), last_seen_at=now - timedelta(days=2))
    _seed(session, "old-1", version="v1.0.0", os="Linux", runtime="docker",
          first_seen_at=now - timedelta(days=60), last_seen_at=now - timedelta(days=5))
    _seed(session, "old-2", version="v1.0.0", os="Linux", runtime="docker",
          first_seen_at=now - timedelta(days=120), last_seen_at=now - timedelta(days=6))
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()

    # new_daily: 2 days have entries
    new_daily_total = sum(e["count"] for e in body["new_daily"])
    assert new_daily_total == 2

    # new_monthly: current month has 2, plus older months
    months = {e["month"]: e["count"] for e in body["new_monthly"]}
    assert sum(months.values()) == 4

    # longevity: all 4 are active (last seen within 30d)
    longevity = {e["label"]: e["count"] for e in body["longevity"]}
    assert sum(longevity.values()) == 4
    assert longevity["< 1 week"] == 2

    # version_mix: only active installs appear
    assert body["version_mix"], "version mix should have entries"


def test_version_mix_has_entries(client: TestClient, session: Session):
    now = utcnow()
    _seed(session, "a", version="v1.2.0", os="Linux", runtime="docker", last_seen_at=now)
    _seed(session, "b", version="v1.1.0", os="macOS", runtime="pipx", last_seen_at=now)
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["version_mix"]) == 1
    day = body["version_mix"][0]
    versions = {e["label"]: e["count"] for e in day["versions"]}
    assert versions == {"v1.2.0": 1, "v1.1.0": 1}


def test_daily_activity_counts_each_ping_day(client: TestClient, session: Session):
    """An installation that pings on multiple days is counted on each day.

    This is the core regression test for the daily-active chart: it must count
    installations that were active *on* a day, not installations whose most
    recent ping was on that day.
    """
    from app.models import DailyActivity

    now = utcnow()
    today = now.date().isoformat()
    yesterday = (now - timedelta(days=1)).date().isoformat()
    _seed(session, "pinger", last_seen_at=now)
    session.add(DailyActivity(installation_id="pinger", activity_date=yesterday))
    # yesterday-only pinged just yesterday.
    _seed(session, "yesterday-only", last_seen_at=now - timedelta(days=1))
    session.commit()

    resp = client.get("/api/stats")
    assert resp.status_code == 200
    body = resp.json()

    by_date = {e["date"]: e["count"] for e in body["daily"]}
    assert by_date.get(yesterday) == 2  # pinger + yesterday-only
    assert by_date.get(today) == 1      # only pinger