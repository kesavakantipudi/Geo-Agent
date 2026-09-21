# GeoAgent — Satellite Intelligence Agent

> An interactive multi-agent geospatial intelligence platform that turns satellite and environmental data into understandable analysis, historical insights, and conversational intelligence for any selected location.

**Project status: Q1 — Phase 3: Location Intelligence implemented (backend + frontend verified).** The FastAPI backend (auth, organizations/workspaces RBAC, saved locations in PostGIS, provider-based geocoding, geometry validation, analysis-session drafts), its 66-test suite, and a Next.js frontend with an interactive Leaflet map canvas are implemented; satellite/weather retrieval and agent execution are still **planned**. Everything in this README that is not explicitly marked as *implemented* is **planned**.

*Project inaugurated on September 14, 2026.*

---

## Table of Contents

- [Overview](#overview)
- [Problem statement](#problem-statement)
- [Proposed solution](#proposed-solution)
- [Core features](#core-features)
- [Planned agents](#planned-agents)
- [Planned technology stack](#planned-technology-stack)
- [High-level architecture](#high-level-architecture)
- [Repository structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Environment configuration](#environment-configuration)
- [Development workflow](#development-workflow)
- [Testing](#testing)
- [Project status and roadmap](#project-status-and-roadmap)
- [Contribution](#contribution)
- [License](#license)

---

## Overview

GeoAgent is a multi-agent geospatial intelligence platform. A user selects a location and a geographic area, chooses the analysis modules they need, and GeoAgent retrieves satellite and environmental data, runs specialized analyses, investigates historical changes, and lets the user continue the investigation through natural-language conversations.

The initial geographic focus is **India**, with an architecture designed to be extensible to global coverage.

The platform is a **B.Tech final-year project** (target completion: January 2027) with the potential to evolve into a real product.

*The full product specification is in [`PRD.md`](PRD.md). The research-oriented overview is in [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md).*

---

## Problem statement

Users who need geographic, agricultural, environmental, or water-related information typically have to:

1. Manually collect data from multiple platforms.
2. Interpret complex satellite imagery, weather data, maps, and historical observations.
3. Combine and explain the results themselves.

Existing conversational AI systems can explain information, but they do not provide an integrated workflow for selecting a geographic region, retrieving relevant geospatial data, running satellite-based analysis, comparing historical observations, and interacting with specialized analytical agents.

GeoAgent addresses this gap by providing an integrated, conversational, multi-agent geospatial intelligence platform.

---

## Proposed solution

GeoAgent combines geospatial data sources, satellite imagery, weather APIs, machine-learning models, geospatial processing, and large language models into one unified platform.

The core experience follows this flow:

```
Location → Data → Specialized Analysis → Change Detection → AI Reasoning → Visualization → Conversation → Suggestions
```

A user selects a location and explicitly chooses the analyses they need (for example, Agriculture + Weather + Change Detection). Specialized agents perform the requested analyses, a central GeoAgent layer combines the outputs, and the user investigates the results on an interactive map and through natural-language questions grounded in the retrieved data and analysis.

---

## Core features

> **Partially implemented (Phase 3).** Items marked *(implemented)* are working end to end; the rest remain **planned**.

- Location and geographic-area selection (search, coordinates, map click, polygon, rectangle, GeoJSON upload/paste) — **place search, polygon/rectangle drawing, GeoJSON import/export, and saved-location reuse implemented**.
- Explicit selection of analysis modules (Agriculture, Water, Weather, Change Detection) — selection UI and persisted draft sessions **implemented**; agent execution planned.
- Satellite imagery retrieval from free/open providers (Copernicus Sentinel-2, Sentinel-1, Landsat, and Microsoft Planetary Computer as a candidate).
- Specialized agent analyses (Agri, Aqua, Weather, Change).
- Historical change detection over selectable date ranges.
- Interactive map with imagery, overlays, layers, and timeline controls — **map canvas with AOI overlay implemented**; imagery/layer/timeline controls planned.
- Conversational interface with the agents, grounded in the selected location and analysis.
- Cross-agent reasoning that clearly distinguishes observations from possible explanations.
- Analysis history and downloadable PDF reports.

---

## Planned agents

| Agent | Responsibility |
| --- | --- |
| **GeoAgent** | Central intelligence/orchestration layer. Understands requests, coordinates specialized agents, combines outputs, answers natural-language questions, and recommends further investigation. |
| **Agri Agent** | Agricultural and vegetation analysis (NDVI, crop health, vegetation stress, drought indicators, historical comparison). |
| **Aqua Agent** | Water-body analysis (water detection, spread estimation, shrinkage/expansion, flooded-area detection, seasonal variation). |
| **Weather Agent** | Environmental and weather intelligence (temperature, rainfall, humidity, wind, forecast, historical weather, weather alerts). |
| **Change Agent** | Temporal change analysis across imagery, vegetation, agriculture, water, and land-use indicators. |

Detailed planned responsibilities are in [`docs/agents.md`](docs/agents.md).

---

## Planned technology stack

> **Planned — tooling and configuration are not set up yet.** See [`DEVELOPMENT.md`](DEVELOPMENT.md) for what remains to be configured.

| Layer | Technology | Status |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, shapely, pyproj, httpx | **Implemented (Phases 2–3)** |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, React 19 | **Implemented (Phases 2–3)** |
| Geospatial database | PostgreSQL 16 + PostGIS 3.4 (Docker) | **Implemented (Phases 2–3)** |
| Satellite data | Copernicus Sentinel-2, Sentinel-1, Landsat, Microsoft Planetary Computer (candidate) | Planned |
| Maps | Leaflet + react-leaflet + leaflet-draw | **Implemented (Phase 3)** |
| ML/CV | PyTorch, rasterio, GDAL, OpenCV, NumPy, GeoPandas | Planned |
| LLM orchestration | TBD (Phase 3, Q3) | Planned |
| Caching / queues | Redis (where useful) | Planned |
| Storage | Object storage for imagery and files (TBD) | Planned |

The stack will be finalized during implementation phases.

---

## High-level architecture

> **Status: partially implemented.** The segments below that say *implemented* are real working code; the rest of the diagram shows the planned target.

```
Frontend (implemented: Next.js 15 / React 19 / Tailwind, Leaflet map canvas)
        │  /api/* proxied to the backend
        ▼
FastAPI backend (implemented: auth, users, orgs, workspaces, saved locations,
                places/search, geometries/validate, analysis-sessions, health)
        │
        ▼
GeoAgent Orchestrator (planned)
        │
        ├── Agri Agent (planned)
        ├── Aqua Agent (planned)
        ├── Weather Agent (planned)
        └── Change Agent (planned)
        │
        ▼
Service layer — provider abstraction (implemented: geocoding; planned: satellite, weather)
        │
        ├── Satellite providers (planned)
        ├── Weather providers (planned)
        ├── Geocoding provider (implemented: Photon)
        └── Geospatial processing (implemented: geometry validation/area via shapely/pyproj)
        │
        ▼
Data layer (implemented: PostgreSQL 16 + PostGIS 3.4, Alembic-managed schema)
```

Detailed planned architecture and component responsibilities are in [`docs/architecture.md`](docs/architecture.md).

---

## Repository structure

The current repository layout (Phases 2–3):

```
GeoAgent/
├── README.md                     # This file
├── PRD.md                        # Full product requirement document
├── CONTRIBUTING.md               # Contribution process and git workflow
├── CODE_OF_CONDUCT.md            # Community standards
├── DEVELOPMENT.md                # Development conventions and standards
├── .gitignore                    # Ignore rules for generated files and secrets
├── .dockerignore                 # Build-context exclusions for Docker
├── .env.example                  # Example environment variables (placeholders only)
├── LICENSE                       # License decision pending (see License section)
├── requirements.txt              # Reserved for Python dependencies (Phase 2+)
├── docker-compose.yml            # PostGIS + backend + frontend services
├── docs/                         # Project documentation
│   ├── README.md                 # Documentation index
│   ├── PROJECT_OVERVIEW.md       # Research-oriented overview
│   ├── architecture.md           # Architecture (Phases 2–3 layers implemented)
│   ├── agents.md                 # Planned agent responsibilities
│   ├── api-spec.md               # API spec (Phase 2 + 3 endpoints implemented)
│   ├── project-scpoe.md          # Scope summary
│   └── project-management/
│       ├── roadmap.md            # Q1–Q4 roadmap with all planned phases
│       ├── phase1-checklist.md   # Phase 1 checklist and acceptance criteria
│       ├── phase2-checklist.md   # Phase 2 checklist and verified checks
│       └── phase3-checklist.md   # Phase 3 checklist and verified checks
├── .github/                      # GitHub issue and PR templates
├── backend/                      # FastAPI backend (implemented — see backend/README.md)
│   ├── README.md
│   ├── Dockerfile
│   ├── pyproject.toml / uv.lock  # uv-managed Python project
│   ├── alembic.ini + alembic/    # DB migrations (PostGIS, initial + session config)
│   ├── app/                      # API, models, schemas, services, core, db
│   ├── tests/                    # pytest suite (66 tests, per-test PostGIS DB)
│   ├── agents/                    # Reserved for agent implementations
│   ├── services/                  # Reserved for service/provider layer
│   └── utils/                     # Reserved for shared utilities
├── frontend/                     # Next.js frontend (implemented — see frontend/README.md)
│   ├── README.md
│   ├── Dockerfile
│   ├── package.json
│   └── src/                      # App Router pages, middleware, lib, components (map/analysis UI)
├── data/                         # Reserved for datasets (never committed)
│   ├── README.md
│   ├── raw/
│   ├── processed/
│   └── sample/
├── models/                       # Reserved for model artifacts and evaluation
│   └── README.md
├── notebooks/                    # Reserved for research/experiments
│   └── README.md
├── src/                          # Reserved for shared/shared-pipeline code
│   └── README.md
└── tests/                        # Reserved for automated tests (none yet)
    └── README.md
```

Empty directories are kept trackable with small placeholder files so the structure survives commits and clones.

---

## Prerequisites

For the implemented Phase 2 stack:

- Git (required).
- A GitHub account with access to the `kesavakantipudi/Geo-Agent` repository.
- Docker Desktop (running) for the PostGIS database and optional app containers.
- Python 3.12 and [uv](https://docs.astral.sh/uv/) for the backend.
- Node.js 20+ and npm for the frontend.

Recommendations for later phases: PostgreSQL with PostGIS knowledge, GPU/ML tooling, and cloud accounts — not required yet.

## Setup

### Backend (implemented)

```bash
docker compose up -d db        # PostGIS on localhost:54932
cd backend
cp .env.example .env           # fill GEOAGENT_AUTH_SECRET_KEY + DB URL
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload   # http://localhost:8000/docs
```

### Frontend (implemented)

```bash
cd frontend
npm install
npm run dev                    # http://localhost:3000 (proxies /api/* to the backend)
```

### Full stack (implemented)

```bash
docker compose up --build      # PostGIS + backend (migrates on start) + frontend
```

See [`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md), and [`DEVELOPMENT.md`](DEVELOPMENT.md) for details.

Team action item: each member should complete the setup and confirm their machine is ready (see [`DEVELOPMENT.md`](DEVELOPMENT.md#team-setup-checklist)).

---

## Environment configuration

Environment variables are read by the application **from Phases 2 onward**. In Phase 1, no environment variables are required.

- `.env.example` contains **placeholder values only** — never real credentials.
- To create a local environment file: `cp .env.example .env` and fill in your own values as development proceeds.
- `.env` must never be committed. It is covered by `.gitignore`.
- Real API keys (satellite, weather, LLM) will be supplied via local `.env` files or a secure secret store in later phases — never committed and never hard-coded.

See [`.env.example`](.env.example) and the *Environment variables* section of [`DEVELOPMENT.md`](DEVELOPMENT.md#environment-variables) for details.

---

## Development workflow

- **Branching and commits:** Conventional Commits; feature branches merged to `main` (or an optional `develop`). Guidelines in [`CONTRIBUTING.md`](CONTRIBUTING.md).
- **Dev conventions (Python, TypeScript, general):** [`DEVELOPMENT.md`](DEVELOPMENT.md).
- **Issue and PR templates:** provided under `.github/` (bug report, feature request, engineering task, pull request).

---

## Testing

**Implemented for the backend.** `cd backend && uv run pytest -q` runs the suite (currently **66 tests**: health, auth with refresh rotation, organizations/workspaces RBAC, saved locations, geometry validation, place search/geocoding, and analysis sessions) against a disposable PostGIS database provisioned per test; `uv run ruff check .` and `uv run ruff format --check .` keep the code formatted. Frontend checks: `cd frontend && npm run typecheck && npm run lint && npm run build`.

Automated tests for the satellite/weather/agent modules, plus ML/evaluation checks, will be added as those modules are built. Evaluation metrics for analytical components are defined in [`PRD.md`](PRD.md) section 40 and [`docs/PROJECT_OVERVIEW.md`](docs/PROJECT_OVERVIEW.md) section 19.

---

## Project status and roadmap

| Quarter | Focus | Phases |
| --- | --- | --- |
| **Q1** | Engineering and data foundation | 1–5 |
| **Q2** | Geospatial intelligence agents | 6–10 |
| **Q3** | Multi-agent GeoAgent platform | 11–15 |
| **Q4** | Productization and delivery | 16–22 |

The roadmap is **planned** and subject to refinement based on implementation progress. Full detail: [`docs/project-management/roadmap.md`](docs/project-management/roadmap.md).

Phase 1–3 progress is tracked in the phase checklists under [`docs/project-management/`](docs/project-management/).

**Phase 3 status:** location intelligence implemented — debounced place search (Photon), shapely/pyproj geometry validation and area measurement, polygon/rectangle AOI drawing + GeoJSON import/export on a Leaflet canvas, analysis-session drafts with date range, agents, and workspace scoping. Backend verified: migrations at head, **66 tests green**, ruff clean. Frontend verified: typecheck, lint, and production build green. Remaining Phase 3 niceties listed in the phase-3 checklist (CI, frontend Docker image, fresh-server boot smoke test).

---

## Contribution

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first. By participating in this project, you agree to abide by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## License

**No license has been chosen for this repository yet.** The project owner must select a license before public distribution or reuse; until then, no rights are granted for reuse. See the note in [`LICENSE`](LICENSE). This is a team/owner decision for an upcoming phase.