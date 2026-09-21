# GeoAgent backend

Python 3.12 / FastAPI application (Phases 2–3). See [`../README.md`](../README.md) and [`../docs/`](../docs/) for project context, and [`../DEVELOPMENT.md`](../DEVELOPMENT.md) for conventions.

## What is implemented

- **FastAPI app** (`app/main.py`, `create_app()`) with CORS, unified error handling (`{"error": {"code","message","details"}}`), `GET /` → `/docs`.
- **Versioned API** under `/api/v1` (`app/api/v1/`):
  - `auth` — register, login, refresh (rotation), logout, me.
  - `users` — `GET/PATCH /users/me`.
  - `organizations` — list/create/get/update + member CRUD with RBAC (owner/admin/member).
  - `workspaces` — list/create/patch under an organization.
  - `saved-locations` — create/list/get/update/delete with GeoJSON/WKT geometry stored as PostGIS `geometry(Geometry,4326)`; response now includes geometry type/GeoJSON, bbox, centroid, and approximate area (Phase 3).
  - `geometries` — `POST /geometries/validate`: strict GeoJSON/EWKT parsing, SRID-4326 enforcement, vertex cap, validity, and planimetric area via shapely/pyproj (Phase 3).
  - `places` — `GET /places/search`: provider-based geocoding (Photon by default, no key), rate-limited, with a disabled fallback (Phase 3).
  - `analysis-sessions` — CRUD for analysis draft sessions: AOI, date range, agent selection, workspace scoping (Phase 3).
  - `health` — app and DB/PostGIS checks.
- **Auth** — access JWT (15 min) + rotating refresh token (30 days), HTTP-only cookies (`geoagent_access` / `geoagent_refresh`), bearer-token support.
- **Migrations** — Alembic + GeoAlchemy2; `0001_initial.py` (tables + PostGIS) and `0002_analysis_session_config.py` (AOI geometry, dates, agents on analysis sessions).
- **Tests** — pytest suite that provisions a disposable PostGIS database per test and runs the suite against it (**66 tests**).

## Layout

```
app/
  api/           Routers, dependencies, v1 endpoints
  core/          Settings, exceptions
  db/            Session, base models
  models/        SQLAlchemy/GeoAlchemy2 ORM models
  schemas/       Pydantic request/response models
  services/      Business logic (auth, users, orgs, workspaces, saved
                 locations, geometry, geocoding/, analysis sessions)
alembic/         Migrations (env.py reads settings)
tests/           pytest suite (conftest provisions a throwaway DB per test)
```

Conventions: route handlers stay thin; business logic lives in `app/services/`; request/response validation uses Pydantic schemas in `app/schemas/`.

The legacy placeholder folders `agents/`, `services/`, and `utils/` remain reserved for their Phase-1 stated purposes; the live application package is `app/`.

## Local development

From the `backend/` directory (uses the PostGIS container on host port `54932`):

```bash
cp .env.example .env          # then fill in real values (see below)
uv sync                       # installs deps from uv.lock
uv run alembic upgrade head   # migrate the database (docker compose up -d db first)
uv run uvicorn app.main:app --reload
uv run pytest -q              # 66 tests against a fresh PostGIS DB
uv run ruff check .
uv run ruff format .
```

### Quick smoke test

```bash
curl http://localhost:8000/api/v1/health       # {"status":"ok",...}
curl http://localhost:8000/api/v1/health/db    # database + PostGIS version
```

Register → login → the API sets `geoagent_access` / `geoagent_refresh` cookies; keep them in your HTTP client (`--cookie-jar`).

## Environment

Required: `GEOAGENT_AUTH_SECRET_KEY` (>= 32 chars) and a reachable PostGIS database.
Defaults come from `app/core/config.py`; override via `backend/.env` (git-ignored).
See [`backend/.env.example`](./.env.example) for the full list.

A sample `.env` pointing at the dockerized database:

```dotenv
GEOAGENT_DATABASE_URL=postgresql+psycopg://geoagent:geoagent@localhost:54932/geoagent
GEOAGENT_AUTH_SECRET_KEY=<generated token>
GEOAGENT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Phase 3 settings (all optional with defaults): `GEOAGENT_GEOCODER_PROVIDER=photon|disabled`,
`GEOAGENT_GEOCODER_PHOTON_URL`, timeout/rate/user-agent/max-results, `GEOAGENT_MAX_GEOMETRY_POINTS`,
and `GEOAGENT_ANALYSIS_MAX_FUTURE_YEARS`. The default Photon geocoder needs no API key.

## Container

`backend/Dockerfile` builds the API image with `uv` (frozen, no dev deps) and starts uvicorn on port 8000. `docker-compose.yml` runs it next to PostGIS; on start it runs `alembic upgrade head` automatically. Validated with `docker compose config` and a live container smoke test (health + PostGIS both report ok).