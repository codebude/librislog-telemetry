# librislog-telemetry

<p align="center">
  <a href="#what-it-does">📚 What it does</a>
  &nbsp;·&nbsp;
  <a href="#quick-start-local">Quick Start</a>
  &nbsp;·&nbsp;
  <a href="#api">API Reference</a>
  &nbsp;·&nbsp;
  <a href="#docker-compose-setup--configuration">Configuration</a>
  &nbsp;·&nbsp;
  <a href="https://metrics.librislog.app/">📈 Live Dashboard</a>
</p>

<p align="center">
  <a href="https://github.com/codebude/librislog-telemetry/actions/workflows/tests.yml"><img src="https://github.com/codebude/librislog-telemetry/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/codebude/librislog-telemetry/actions/workflows/docker.yml"><img src="https://github.com/codebude/librislog-telemetry/actions/workflows/docker.yml/badge.svg" alt="Docker Build"></a>
  <img src="https://img.shields.io/badge/python-3.14-%233776AB?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.141-%23009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

Minimal, open source and transparent telemetry server for [LibrisLog](https://github.com/codebude/librislog).

> 🚀 **Live instance:** [metrics.librislog.app](https://metrics.librislog.app/) — see the public dashboard in action.

> `docker compose up -d` → anonymous, aggregate usage statistics for your
> open-source app, with a clean public dashboard. No vendor lock-in.

---

## What it does

LibrisLog installations send a tiny anonymous heartbeat once per day:

```json
{
  "message_version": 1,
  "installation_id": "random-anonymous-id",
  "version": "v1.2.0",
  "os": "Linux",
  "architecture": "x64",
  "runtime": "docker"
}
```

The `message_version` field is the message-schema version. Every version is a
fully self-contained model declaring exactly its own fields — so a future
version can **add** new fields *or* **drop** existing ones (a dropped field is
rejected with a 422 if still sent). Shared normalizers live in
`TelemetryCommonMixin` and apply to whatever version declares the field.
Adding version 2 means subclassing the base with `message_version = 2`,
extending the union in `schemas.py`, and adding a dispatch branch in
`routers/telemetry.py`. Unknown versions are rejected.

The server:

- **Stores one row per installation** (upsert on each check-in), so the dataset
  stays small and bounded — it never grows unboundedly. Per-day activity is
  tracked in a separate table (one row per installation per day it reports),
  which keeps the daily-activity chart accurate even for installations that
  ping every day.
- **Prunes stale installations** — a background retention job (every
  `PRUNE_INTERVAL_HOURS`) moves installations not seen for `PRUNE_AFTER_DAYS`
  (default 365, i.e. abandoned for a year) to a pruned table. Their IDs are
  kept, so the all-time total remains exact — and if a pruned installation
  checks in again, it moves back to the live table without being counted twice.
- **Rejects invalid payloads** with strict schema validation (422), and
  **rate-limits per IP** to keep bots out.
- **Never stores personal data** — no IPs, no paths, no library contents. Just
  an anonymous ID and basic environment info. IPs are used transiently for rate
  limiting but are never stored, and the server logs no access log — rate-limit
  warnings appear with the trailing octets masked (`192.168.1.x` by default,
  configurable via `LOG_IP_MASK_OCTETS`).
- **Serves a public dashboard** at `/` with daily activity, new installs per
  day/month, install longevity, a version-mix stack, and version/OS/architecture/
  runtime breakdowns. The activity-based charts only cover installations that
  checked in during the last 30 days.

## Quick Start (local)

Prefer to look before you run? The public instance is at
[**metrics.librislog.app**](https://metrics.librislog.app/).

```bash
uv sync
uv run ltel migrate        # create the SQLite schema
uv run ltel seed --count 25  # optional: fake data for dashboard development
uv run ltel clean          # remove seeded data (asks before deleting)
uv run ltel prune --days 365  # move stale installations to the pruned table
uv run ltel run            # http://127.0.0.1:8001
```

Or with Docker:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Send a test heartbeat:

```bash
curl -X POST http://localhost:8001/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{"message_version":1,"installation_id":"example-1","version":"v1.0.0","os":"Linux","architecture":"x64","runtime":"docker"}'
```

Open **http://127.0.0.1:8001** to view the dashboard.

## Docker Compose Setup & Configuration

The project ships two compose files:

| File | Purpose |
|---|---|
| `docker-compose.dev.yml` | Local development — builds the image from source (`docker compose -f docker-compose.dev.yml up --build`) |
| `docker-compose.yml` | Production — pulls the published image from GHCR (`docker compose up -d`) |

Both mount the host directory `./data` into the container at `/app/data`. The
SQLite database (`telemetry.db`) lives there, so your data survives container
restarts and is easy to back up. That volume is the only thing you need to
persist.

### Passing configuration

All settings are read from environment variables by the backend
([pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)).
In Docker, the simplest way is `env_file: .env`:

```yaml
services:
  backend:
    image: ghcr.io/codebude/librislog-telemetry/librislog-telemetry-api:latest
    env_file: .env
    ports:
      - "8001:8001"
    volumes:
      - ./data:/app/data
```

Start by copying the example file:

```bash
cp .env.example .env
# edit .env to your liking
docker compose up -d
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/telemetry.db` | SQLAlchemy database URL. In the container this resolves to `/app/data/telemetry.db` because the image's working directory is `/app`. |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `RATE_LIMIT_PER_MINUTE` | `4` | Max telemetry requests per IP per minute before the endpoint returns `429`. The `.env.example` ships with `60`. |
| `LOG_IP_MASK_OCTETS` | `1` | How many trailing IPv4 octets are masked in log output (`1` → `192.168.1.x`, `2` → `192.168.x.x`). The prefix stays visible so repeat offenders can still be spotted. |
| `ENABLE_DOCS` | `true` | Whether to expose `/api/docs` (Swagger UI) and `/api/openapi.json`. Set to `false` in production to reduce the public attack surface — the endpoints then return `404`. |
| `PRUNE_AFTER_DAYS` | `365` | Installations not seen for this many days are moved to the pruned table by the retention job. Their IDs are kept, so the all-time total stays exact. |
| `PRUNE_INTERVAL_HOURS` | `24` | How often the background retention job runs. |
| `CORS_ORIGINS` | `["http://localhost:8001"]` | Allowed CORS origins, JSON array. |
| `FORWARDED_ALLOW_IPS` | `*` | IPs (or `*`) trusted to send `X-Forwarded-For`/`X-Forwarded-Proto`. Set to your reverse-proxy IP or CIDR in production. |

> The reference file is `.env.example`. Copy it to `.env` before starting —
> this project works with zero configuration out of the box, but the example
> documents every knob you can turn.

## API

| Endpoint | Description |
|---|---|
| `POST /api/telemetry` | Ingests a telemetry heartbeat (unauthenticated, rate-limited). |
| `GET /api/stats` | Aggregate statistics for the dashboard. |
| `GET /api/health` | Health check (db connectivity + schema). |
| `GET /api/docs` | Interactive OpenAPI docs. |
| `GET /` | Public dashboard. |

## Why no API key?

The sending client (librislog) is open source — an API key bundled with it
would be public anyway. Spam protection instead relies on:

1. **Strict schema validation** — only well-formed heartbeats are stored.
2. **Per-IP rate limiting** — configurable via `RATE_LIMIT_PER_MINUTE`.
3. **Bounded dataset** — one row per installation (upserted per check-in), so
   even a flood of fake installation IDs only creates one mostly-empty row per
   unique ID instead of one row per request. The dashboard only counts
   non-empty fields.


## Development

- **Backend** (`backend/`): FastAPI + SQLModel + SQLite, Alembic migrations,
  pytest. Port `8001`.
- **Devtools CLI** (`cli/`, `ltel`): run server, migrate, seed, run tests,
  manage Docker.

```bash
uv run ltel test all   # run all test suites
```

## License

[MIT](LICENSE)