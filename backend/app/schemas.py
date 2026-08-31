"""Pydantic schemas for request and response payloads.

Each message version is a fully self-contained model: it declares exactly the
fields that version accepts. Shared normalizers live in ``TelemetryCommonMixin``
and apply to whatever version declares the relevant fields. ``message_version``
is the discriminator that lets FastAPI pick the matching model.
"""

from datetime import datetime
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

def _build_aliases(mapping: dict[str, str]) -> dict[str, str]:
    """Build a case-insensitive alias map, including canonical values.

    Every canonical value is also added (lowercased -> itself) so any casing of
    a known value resolves to the canonical form. Unknown values fall through
    the validator unchanged.
    """
    aliases = dict(mapping)
    for canonical in mapping.values():
        aliases.setdefault(canonical.lower(), canonical)
    return aliases


_OS_ALIASES = _build_aliases({
    "macos": "macOS",
    "osx": "macOS",
    "darwin": "macOS",
    "windows": "Windows",
    "win32": "Windows",
    "linux": "Linux",
    "linux-gnu": "Linux",
})

_ARCH_ALIASES = _build_aliases({
    "x86_64": "x64",
    "amd64": "x64",
    "arm64": "ARM64",
    "aarch64": "ARM64",
    "arm": "ARM",
})


class TelemetryCommonMixin:
    """Shared field validators.

    ``check_fields=False`` lets a version omit a field entirely without the
    validator raising; the validator simply never runs for that version.
    """

    @field_validator("installation_id", check_fields=False)
    @classmethod
    def _strip_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("os", check_fields=False)
    @classmethod
    def _normalize_os(cls, value: str) -> str:
        return _OS_ALIASES.get(value.strip().lower(), value.strip())

    @field_validator("architecture", check_fields=False)
    @classmethod
    def _normalize_arch(cls, value: str) -> str:
        return _ARCH_ALIASES.get(value.strip().lower(), value.strip())

    @field_validator("version", "runtime", check_fields=False)
    @classmethod
    def _strip_plain(cls, value: str) -> str:
        return value.strip()


class TelemetryBase(BaseModel):
    """Fields every message version shares.

    Everything else is declared per-version, so a version can add fields (e.g.
    ``locale``) or drop fields (making them 422 if still sent) freely.
    """

    model_config = ConfigDict(extra="forbid")

    message_version: int = Field(ge=1)
    installation_id: str = Field(min_length=1, max_length=64)


class TelemetryInV1(TelemetryBase, TelemetryCommonMixin):
    """Message version 1 — the original heartbeat schema."""

    message_version: Literal[1] = 1
    version: str = Field(default="", max_length=32)
    os: str = Field(default="", max_length=32)
    architecture: str = Field(default="", max_length=32)
    runtime: str = Field(default="", max_length=64)
    client_ts: Optional[datetime] = None


# Discriminated union: FastAPI validates the payload against the model whose
# ``message_version`` matches. New versions are added here as their own model.
TelemetryIn = Annotated[Union[TelemetryInV1], Field(discriminator="message_version")]


class TelemetryOut(BaseModel):
    """Acknowledgement returned on a successful telemetry ingestion."""

    ok: bool = True
    installation_id: str


class StatEntry(BaseModel):
    """A single (label, count) pair used by dashboard breakdowns."""

    label: str
    count: int


class DailyStat(BaseModel):
    """Number of distinct installations seen on a given day."""

    date: str
    count: int


class StatsOut(BaseModel):
    """Aggregate statistics consumed by the public dashboard."""

    total_installations: int
    active_7d: int
    active_30d: int
    versions: list[StatEntry]
    operating_systems: list[StatEntry]
    architectures: list[StatEntry]
    runtimes: list[StatEntry]
    daily: list[DailyStat]
    server_version: str