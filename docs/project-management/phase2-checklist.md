# Phase 2 — Application Foundation: Checklist and Acceptance Criteria

**Goal:** a working application skeleton the rest of the project builds on — FastAPI backend with auth, organizations/workspaces RBAC, saved locations in PostGIS, a typed Next.js frontend, containerization, and updated documentation.

> Items marked `[x]` were completed during Phase 2 work and have been verified (commands run, checks green). Items marked `[ ]` remain for manual/team or later-phase action. Nothing is marked complete without a check to back it up.

## Backend — foundation

- [x] FastAPI application scaffold (`app/main.py`, `create_app()`, settings, CORS, exception handlers, `GET /` → `/docs`).
- [x] Unified error contract `{"error": {"code", "message", "details"}}` across API errors, validation, and HTTP exceptions.
- [x] Settings via pydantic-settings (`GEOAGENT_*`), fail-fast on missing `GEOAGENT_AUTH_SECRET_KEY` outside tests.
- [x] SQLAlchemy 2 models for users, refresh tokens, organizations, memberships, workspaces, saved locations, and Phase-3 tables (analysis, satellite scenes, weather, chat sessions/messages, reports) — all migrated by `0001_initial`.
- [x] Alembic + GeoAlchemy2: initial migration verified `upgrade head`, full `downgrade base → upgrade head` round-trip against PostGIS 16/3.4.
- [x] Engines/session wired to `GEOAGENT_DATABASE_URL`; DB health endpoint reports PostGIS presence + version.
- [x] Geometry handling (`app/services/geometry.py`): EWKT strings and GeoJSON Point/LineString/Polygon → `geometry(Geometry,4326)`; validated against PostGIS (SRID 4326).
- [x] Auth: register, login, refresh (rotation, single-use, expires after use), logout (revoke), `users/me`; access JWT (15 min) + rotating refresh (30 days).

## Backend — API surface (all exercised by tests)

- [x] `POST /api/v1/auth/register|login|refresh|logout`, `GET /api/v1/auth/me`.
- [x] `GET/PATCH /api/v1/users/me`.
- [x] Organizations: `GET /api/v1/organizations`, `POST ...` (201 + slug rules), `GET/PATCH /{id}` (member-scoped), members `GET/POST/PATCH/DELETE /{id}/members` with RBAC (owner can only be appointed by other owners; owner/admin manage members; members read-only).
- [x] Workspaces: `GET/POST /api/v1/organizations/{id}/workspaces`, `PATCH /api/v1/workspaces/{id}`; organization scoping enforced.
- [x] Saved locations: `POST /api/v1/saved-locations`, `GET .../saved-locations`, `GET/PATCH/DELETE /{id}`; private per user.
- [x] `GET /api/v1/health`, `GET /api/v1/health/db`.

## Backend — quality gates

- [x] `uv run ruff check .` → passes (lint + import sorting; B008/E501 configured).
- [x] `uv run ruff format .` → applied consistently (whole backend formatted).
- [x] `uv run pytest -q` → **21 passed** (health 3, auth 8, organizations 5, workspaces 4, saved locations 2) against per-test disposable PostGIS databases.
- [x] Live uvicorn smoke test: `/api/v1/health` and `/api/v1/health/db` return ok / `postgis: true`.
- [x] Type safety in app code (no dynamic/SQL string queries for user input).

## Frontend — scaffold

- [x] Next.js 15 (App Router) + React 19 + TypeScript strict + Tailwind 3 in `frontend/` with `src/` layout.
- [x] `next.config.ts` rewriting `/api/*` → backend (`http://localhost:8000` configurable via `BACKEND_URL`).
- [x] `src/middleware.ts` cookie guard: `/dashboard/*` redirects to `/login?next=...` when `geoagent_access` is missing; `/login` bounces authenticated users.
- [x] `src/lib/api/` typed client (JSON error contract, credentials include, 401 → one refresh retry) + types mirroring backend responses.
- [x] `AuthProvider`/`useAuth` — boots user from `/users/me`, exposes logout/reload.
- [x] App shell (`src/components/AppShell.tsx`) with sidebar nav, header, sign-out.
- [x] Pages: `/` (landing), `/login`, `/dashboard`, `/dashboard/analysis`, `/dashboard/history`, `/dashboard/settings`.
- [x] ESLint 9 flat config and `tsc --noEmit`.
- [x] Quality gates: `npm run typecheck` → clean, `npm run lint` → clean, `npm run build` → 9 routes + middleware built successfully.

## Containerization

- [x] `docker-compose.yml` extends to three services: `db` (PostGIS), `backend`, `frontend`; `docker compose config` validates.
- [x] `backend/Dockerfile` (uv, frozen, no dev deps) — **image built successfully** and smoke-tested live: health ok, PostGIS true against the dockerized database.
- [x] Frontend Dockerfile (two-stage, `next start`); compose wiring in place (image build not run in this pass).
- [x] `.dockerignore` keeps build contexts clean (no `.git`, node_modules, .venv, secrets).

## Documentation

- [x] `backend/README.md` rewritten for the implemented app (layout, dev commands, env, container).
- [x] `frontend/README.md` rewritten for the implemented app.
- [x] `docs/api-spec.md` updated to mark Phase 2 endpoints as implemented.
- [x] `docs/architecture.md` updated with the live Phase 2 component stack.
- [x] `docs/README.md` index updated.
- [x] Root `README.md` status, structure, setup, testing, and roadmap sections updated for Phase 2.
- [ ] `DEVELOPMENT.md` refreshed to describe the now-configured toolchains (see checklist below).

## Remaining / team actions

- [ ] Build the frontend Docker image once (`docker compose build frontend`) and run the full stack with `docker compose up`.
- [ ] Add CI (lint + typecheck + backend tests) when the team is ready; CI secret for `GEOAGENT_AUTH_SECRET_KEY` never committed.
- [ ] Phase 3 design: map canvas, AOI picker, satellite/weather layers, agent jobs (endpoints and reserved tables already prepared).
- [ ] License decision (still open from Phase 1).

## When this is done

Proceed to **Phase 3 — Location Intelligence / Satellites** (see [`roadmap.md`](roadmap.md)).