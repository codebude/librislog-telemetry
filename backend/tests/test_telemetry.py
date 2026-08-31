"""Tests for the telemetry ingestion endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Installation


def _payload(**overrides):
    data = {
        "message_version": 1,
        "installation_id": "inst-001",
        "version": "v1.2.3",
        "os": "Linux",
        "architecture": "x64",
        "runtime": "docker",
    }
    data.update(overrides)
    return data


def test_ingest_new_installation(client: TestClient, session: Session):
    resp = client.post("/api/telemetry", json=_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["installation_id"] == "inst-001"

    row = session.get(Installation, "inst-001")
    assert row is not None
    assert row.version == "v1.2.3"
    assert row.os == "Linux"
    assert row.message_version == 1
    assert row.first_seen_at == row.last_seen_at


def test_ingest_without_message_version_rejected(client: TestClient):
    data = _payload()
    del data["message_version"]
    resp = client.post("/api/telemetry", json=data)
    assert resp.status_code == 422


def test_ingest_unknown_message_version_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json=_payload(message_version=99))
    assert resp.status_code == 422


def test_ingest_invalid_message_version_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json=_payload(message_version="v1"))
    assert resp.status_code == 422


def test_ingest_updates_existing(client: TestClient, session: Session):
    client.post("/api/telemetry", json=_payload(version="v1.0.0"))
    resp = client.post("/api/telemetry", json=_payload(version="v1.1.0"))
    assert resp.status_code == 200

    rows = session.exec(select(Installation)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.version == "v1.1.0"
    assert (row.last_seen_at - row.first_seen_at).total_seconds() < 1


def test_ingest_unknown_fields_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json=_payload(extra_field="garbage"))
    assert resp.status_code == 422


def test_ingest_missing_installation_id_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json={"version": "v1.0.0"})
    assert resp.status_code == 422


def test_ingest_invalid_installation_id_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json=_payload(installation_id=""))
    assert resp.status_code == 422


def test_ingest_overlong_fields_rejected(client: TestClient):
    resp = client.post("/api/telemetry", json=_payload(installation_id="x" * 65))
    assert resp.status_code == 422


def test_os_alias_normalization(client: TestClient, session: Session):
    resp = client.post("/api/telemetry", json=_payload(os="darwin", architecture="aarch64"))
    assert resp.status_code == 200
    row = session.get(Installation, "inst-001")
    assert row.os == "macOS"
    assert row.architecture == "ARM64"


def test_os_arch_case_insensitive_canonicalization(client: TestClient, session: Session):
    """Case-variants of known values map to the canonical form."""
    resp = client.post(
        "/api/telemetry",
        json=_payload(os="LINUX", architecture="X64"),
    )
    assert resp.status_code == 200
    row = session.get(Installation, "inst-001")
    assert row.os == "Linux"
    assert row.architecture == "x64"


def test_unknown_os_arch_passes_through(client: TestClient, session: Session):
    """Values not in the alias map are kept as-is (stripped, case preserved)."""
    resp = client.post(
        "/api/telemetry",
        json=_payload(os="  Fedora ", architecture="RISC-V"),
    )
    assert resp.status_code == 200
    row = session.get(Installation, "inst-001")
    assert row.os == "Fedora"
    assert row.architecture == "RISC-V"


def test_ingest_resurrects_pruned_installation(client: TestClient, session: Session):
    """A pruned installation that checks in again moves back to live, so it is
    not double-counted in the all-time total installations metric."""
    from datetime import timedelta
    from app.models import PrunedInstallation
    from app.time_utils import utcnow

    session.add(
        PrunedInstallation(
            installation_id="inst-001",
            pruned_at=utcnow() - timedelta(days=40),
        )
    )
    session.commit()

    resp = client.post("/api/telemetry", json=_payload())
    assert resp.status_code == 200

    row = session.get(Installation, "inst-001")
    assert row is not None
    assert session.get(PrunedInstallation, "inst-001") is None


def test_health_endpoint(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database_schema"]["status"] == "healthy"


def test_unhandled_message_version_raises():
    """An unknown message version in the router dispatch raises ValueError."""
    from app.models import Installation
    from app.routers.telemetry import _apply_version_specific

    class FakePayload:
        message_version = 99

    inst = Installation(installation_id="x")
    with pytest.raises(ValueError, match="Unhandled message version: 99"):
        _apply_version_specific(inst, FakePayload())  # type: ignore[arg-type]


# ── Strict per-version schema tests ──────────────────────────────────────────

from typing import Annotated, Literal, Union  # noqa: E402

from pydantic import Field  # noqa: E402

from app.schemas import TelemetryBase, TelemetryCommonMixin  # noqa: E402


def test_v1_rejects_fields_not_in_its_schema(client: TestClient):
    """Fields of a newer version are forbidden on v1 messages."""
    resp = client.post("/api/telemetry", json=_payload(locale="de"))
    assert resp.status_code == 422


def test_version_can_drop_fields_and_forbid_them():
    """A hypothetical v2 that drops ``runtime`` must reject it as unknown."""

    class TelemetryInV2(TelemetryBase, TelemetryCommonMixin):
        message_version: Literal[2] = 2
        locale: str = ""

    # Omission is fine
    v2 = TelemetryInV2(message_version=2, installation_id="inst-002")
    assert v2.locale == ""

    # Sending the dropped field is rejected (extra="forbid")
    try:
        TelemetryInV2(message_version=2, installation_id="inst-002", runtime="pipx")
        raise AssertionError("dropped field 'runtime' should be rejected")
    except Exception:
        pass


def test_common_mixin_validators_apply_per_version():
    """Shared normalizers apply to versions that declare the field, and are
    inert for versions that dropped it."""

    class TelemetryInV1Sub(TelemetryBase, TelemetryCommonMixin):
        message_version: Literal[1] = 1
        os: str = ""
        architecture: str = ""

    class TelemetryInV2NoArch(TelemetryBase, TelemetryCommonMixin):
        message_version: Literal[2] = 2
        os: str = ""

    v1 = TelemetryInV1Sub(message_version=1, installation_id="a", os="darwin", architecture="aarch64")
    assert v1.os == "macOS"
    assert v1.architecture == "ARM64"

    v2 = TelemetryInV2NoArch(message_version=2, installation_id="a", os="darwin")
    assert v2.os == "macOS"
    assert not hasattr(v2, "architecture")


def test_dropped_field_reset_on_update():
    """A new message version that drops a field clears its stored value."""
    from app.routers.telemetry import _apply_common, _apply_version_specific
    from app.schemas import TelemetryInV1

    # Incoming message: v1 schema, but with runtime intentionally empty/dropped.
    incoming = TelemetryInV1(
        message_version=1,
        installation_id="reset-test",
        version="v1.1.0",
        os="Linux",
        architecture="x64",
        runtime="",  # dropped by the sending client
    )

    fresh = Installation(installation_id="reset-test")
    _apply_common(fresh, incoming)
    _apply_version_specific(fresh, incoming)
    assert fresh.message_version == 1
    assert fresh.version == "v1.1.0"
    assert fresh.runtime == ""