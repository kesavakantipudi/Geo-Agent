# GeoAgent — Development Guide

This document is the engineering reference for the GeoAgent team. It covers the development environment, coding conventions, and the practical standards we follow. Contribution process details (branching, commits, reviews) are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

> **Status:** GeoAgent is in **Phase 2 (Application Foundation)**. The FastAPI backend, Alembic/PostGIS setup, pytest suite, and Next.js frontend are implemented and configured in this repository. The conventions below are now enforced by real tooling (ruff, pytest, ESLint, `tsc`), not just recommendations. Planned agent/provider layers still follow the "recommended" wording where noted.

- [Team setup checklist](#team-setup-checklist)
- [Environment variables](#environment-variables)
- [Python conventions](#python-conventions)
- [TypeScript / frontend conventions](#typescript--frontend-conventions)
- [General engineering standards](#general-engineering-standards)
- [Documentation standards](#documentation-standards)
- [What remains to be configured](#what-remains-to-be-configured)

---

## Team setup checklist

Each team member should complete this checklist on their own machine and confirm it on the phase checklists.

- [ ] Git installed and authenticated (SSH or HTTPS) with access to `kesavakantipudi/Geo-Agent`.
- [ ] Repository cloned and `git status` is clean.
- [ ] Read `README.md`, `PRD.md`, and `docs/project-management/roadmap.md`.
- [ ] Python 3.12 installed and [uv](https://docs.astral.sh/uv/) available (`uv --version`).
- [ ] Node.js 20+ and npm installed (`node --version`, `npm --version`).
- [ ] Docker Desktop installed and running.
- [ ] `docker compose up -d db` brings up PostGIS (host port `54932`).
- [ ] Backend boots: `cd backend && cp .env.example .env && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app` → open `http://localhost:8000/docs`.
- [ ] Backend tests pass: `cd backend && uv run pytest -q`.
- [ ] Frontend boots: `cd frontend && npm install && npm run dev` → open `http://localhost:3000`.
- [ ] Frontend checks pass: `cd frontend && npm run typecheck && npm run lint && npm run build`.

---

## Environment variables

- All configuration must come from environment variables (`.env` locally), never hard-coded.
- Create local config with `cp .env.example .env`; fill in your own values.
- `.env` is git-ignored; never commit it.
- `.env.example` contains placeholders only — update it when new variables are introduced.
- Prefix variables with `GEOAGENT_` to keep them namespaced and grep-able.
- At startup, the application should fail fast with a clear message when a **required** variable is missing.
- API keys for satellite, weather, geocoding, or LLM providers are supplied via local environment or a secure secret store in later phases — never committed.

---

## Python conventions

**Implemented in Phase 2.** Backend conventions are enforced by configuration in `backend/pyproject.toml` and `backend/.env.example`.

- **Project/dependency management:** `uv` with `pyproject.toml` + `uv.lock`. Dev tools (pytest, ruff, httpx) live in `[dependency-groups] dev`. Install with `uv sync`.
- **Formatting & linting:** Ruff. Config: `line-length = 100`, ignores `B008` (FastAPI `Depends` defaults) and `E501`. Run `uv run ruff check .` and `uv run ruff format .`. Lint must stay clean before pushing.
- **Type hints:** Required on all function signatures. Pydantic models for schemas, SQLAlchemy 2 typed mappings for ORM models.
- **Error handling:** `app/core/exceptions.py` defines `ApiError` (code/message/details) → `{"error": {...}}`; services raise domain exceptions; global handlers translate validation and HTTP errors. Never swallow errors.
- **Logging:** `logging` with structured messages and context; never `print`.
- **Testing:** `pytest` (`backend/tests/`). `tests/conftest.py` sets test env before importing the app, provisions a fresh PostGIS database per test, runs `alembic upgrade head`, and drops the DB after — full isolation. Add `test_<module>.py` for new endpoints/services.
- **Migrations:** Alembic; initial migration creates `postgis` and all tables (`backend/alembic/versions/0001_initial.py`). After model changes, generate a new revision; verify `upgrade` and `downgrade`.

## TypeScript / frontend conventions

**Implemented in Phase 2.** Frontend conventions are enforced by `frontend/eslint.config.mjs`, `frontend/tsconfig.json`, and `frontend/tailwind.config.ts`.

- **Formatting:** Prettier is optional; the ESLint config keeps object/import formatting consistent. Keep `npm run lint` clean.
- **Linting:** ESLint 9 flat config built on `eslint-config-next` (`core-web-vitals`, `typescript`) via `FlatCompat`.
- **Component naming:** PascalCase components; camelCase functions/variables. One component per file by default.
- **Type safety:** `strict: true`; explicit interfaces/types in `src/lib/api/types.ts` mirroring backend schemas; avoid `any`.
- **Error handling:** API failures surface in UI states (loading / error / empty). A typed fetch wrapper (`src/lib/api/client.ts`) maps the backend error contract and retries once on 401 via refresh.
- **API service organization:** all backend calls go through `src/lib/api/client.ts`; components never call raw endpoints.
- **Environment usage:** only `NEXT_PUBLIC_*` variables reach the browser. `BACKEND_URL` (server-side rewrite target) and `GEOAGENT_*` stay server-side.
- **Auth:** HTTP-only cookies `geoagent_access` / `geoagent_refresh`; `src/middleware.ts` guards `/dashboard`; `src/lib/auth.tsx` provides `AuthProvider`/`useAuth`.

---

## General engineering standards

- **Small, reviewable pull requests** — one concern per PR (see `CONTRIBUTING.md`).
- **No committed secrets** — see the no-secrets policy in `CONTRIBUTING.md`.
- **Clear documentation for new modules** — a short README or docstring explaining purpose and usage.
- **Tests for meaningful functionality** — added alongside implementation once testing is introduced.
- **No fabricated data presented as real analysis** — mock data is acceptable for UI development when explicitly labeled, but the final system must use genuine data (see `PRD.md` §49).
- **Distinguish data, model results, and AI interpretation** in outputs and UI.
- **Provider abstraction** — satellite, weather, and geocoding services must be provider-independent and gracefully report when no suitable data is available.
- **Failure handling** — external providers fail; design for fallbacks and clear reporting.

---

## Documentation standards

- Keep consistent terminology: **GeoAgent**, **Agri Agent**, **Aqua Agent**, **Weather Agent**, **Change Agent**.
- Label everything honestly: *implemented* vs. *planned*.
- New modules get documentation at the same time as the code.
- Markdown only; keep files focused; cross-link rather than duplicate.

---

## What remains to be configured

The following are intentionally deferred and will be set up as their phases begin:

- Agent/provider tooling (ML/CV, geospatial processing libraries) — Phase 3+.
- CI pipeline — TBD, once the team agrees on a provider; suggested: lint + typecheck + backend tests on PRs (keep the test `GEOAGENT_AUTH_SECRET_KEY` in CI secrets, never the repo).
- Redis caching/queues — later phases if needed.
- Deployment (container registry, hosting, object storage) — Phase 4.
- License selection — owner decision (see `README.md` → License).