# GeoAgent — Architecture

> **Status:** Phase 2 implemented the application foundation (FastAPI backend, PostgreSQL/PostGIS, Alembic migrations, RBAC, rotating-refresh auth, typed Next.js shell). Phase 3 (Location Intelligence) added map-based AOI capture, provider-based geocoding (Photon), a shapely/pyproj geometry service, and persisted analysis sessions with agent/date configuration. The agent, satellite-provider, weather-provider, and orchestrator layers remain planned (Q2/Q3).

Domain: Remote sensing, geospatial intelligence, multi-agent systems.
Reference: [`PRD.md`](../PRD.md) §28–§34; [`docs/PROJECT_OVERVIEW.md`](../docs/PROJECT_OVERVIEW.md) §11.

## 1. Architectural principles

- **Modularity** — agents and providers are independent, swappable modules.
- **Separation of concerns** — geoanalysis vs. language interpretation vs. presentation.
- **Provider abstraction** — satellite, weather, and geocoding services sit behind interfaces with fallbacks.
- **Grounding** — AI explanations must be tied to retrieved data and analysis outputs.
- **Honesty** — observed data, model results, and AI interpretation are always distinguishable.
- **Extensibility** — future agents (Forest, Flood, Urban, etc.) can be added without redesign.

## 2. High-level layers

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend  (Phases 2–3: Next.js 15 / React 19 / TS / Tailwind) │
│  App shell, login, dashboard · Leaflet map canvas with        │
│  polygon/rectangle AOI drawing, GeoJSON import/export,        │
│  place search, saved-location reuse, draft session config     │
│  /api/* proxied to backend via next.config rewrites           │
└──────────────────────────────────────────────────────────────┘
                             │  HTTPS / JSON
┌──────────────────────────────────────────────────────────────┐
│ Backend API  (Phases 2–3: Python 3.12 / FastAPI)              │
│  /api/v1: auth, users, organizations, workspaces,             │
│  saved-locations, health · geometries/validate ·              │
│  places/search · analysis-sessions · Pydantic validation      │
│  · RBAC · unified error contract {"error":{code,message,...}} │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ GeoAgent Orchestrator (LLM-powered planning & coordination)   │
│  PLANNED (Q3) — request planning, agent selection, output     │
│  synthesis, conversational answers, next-step recommendations │
└──────────────────────────────────────────────────────────────┘
        │           │            │             │
        ▼           ▼            ▼             ▼
┌────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐
│ Agri Agent │ │ Aqua     │ │ Weather   │ │ Change Agent │
│ vegetation │ │ Agent    │ │ Agent     │ │ temporal     │
│ & crop     │ │ water    │ │ env &     │ │ analysis     │
│ analysis   │ │ bodies   │ │ forecast  │ │              │
└────────────┘ └──────────┘ └───────────┘ └──────────────┘
        │           │            │             │
        └───────────┴────────────┴─────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ Service Layer (provider abstraction)                          │
│  Geocoding: IMPLEMENTED Phase 3 (PlacesProvider ABC,          │
│  Photon provider, rate limiting, disabled fallback)           │
│  Geometry: IMPLEMENTED Phase 3 (shapely validation,           │
│  pyproj equal-area measurement)                               │
│  PLANNED — Satellite · Weather · geospatial workloads         │
└──────────────────────────────────────────────────────────────┘
                             │
┌──────────────────────────────────────────────────────────────┐
│ Data Layer  (implemented Phase 2)                             │
│  PostgreSQL 16 + PostGIS 3.4 (Docker) · Alembic migrations   │
│  SQLAlchemy 2 / GeoAlchemy2 models · saved-location geometry │
│  SRID 4326 · Phase-3 tables (analysis, scenes, weather,      │
│  chat, reports) already present in the schema                 │
└──────────────────────────────────────────────────────────────┘
```

## 3. Component responsibilities

| Component | Responsibility |
| --- | --- |
| **Frontend** | Location and AOI selection, interactive map with layers/timeline, analysis module selection, dashboards, agent chat UI, reports, (later) 3D visuals. |
| **Backend API** | Validate requests, manage analysis jobs, orchestrate providers/agents, return structured JSON and artifact references, store metadata. |
| **GeoAgent Orchestrator** | Plan analysis workflows, coordinate agents, synthesize outputs, answer questions, recommend further investigation. Does *not* do every specialized calculation itself. |
| **Agri Agent** | Agriculture and vegetation analysis (NDVI, crop health, stress, drought indicators, historical comparison). |
| **Aqua Agent** | Water-body detection, spread estimation, shrinkage/expansion, flooded areas, seasonal variation. |
| **Weather Agent** | Current conditions, historical weather, forecasts, environmental indicators. |
| **Change Agent** | Temporal change detection across imagery, vegetation, water, and land-use indicators. |
| **Satellite service** | Retrieve, cache, and normalize imagery from providers (Sentinel-2, Sentinel-1, Landsat, Planetary Computer candidate) with fallback. |
| **Weather service** | Retrieve weather/environmental data with provider fallback. |
| **Geocoding service** | Convert place names to coordinates; provider-independent. **Implemented (Phase 3):** `app/services/geocoding/` with a Photon provider and disabled fallback. |
| **Geospatial processing** | Preprocessing, cloud masking, index computation (NDVI/NDWI), alignment, masking, derived features. Geometry handling/validation and area measurement are **implemented (Phase 3)** via shapely/pyproj. |
| **Data layer** | PostgreSQL/PostGIS for geographic and analysis data; object storage for imagery/files. |

## 4. Provider fallback design

All external dependencies are behind interfaces so failures or free-tier limits degrade gracefully:

```
SatelliteDataService
    ├── Primary provider
    ├── Secondary provider
    └── Fallback provider
```

When no suitable data is available, the system reports the situation clearly rather than fabricating results. Provider selection will be finalized during implementation based on coverage, resolution, licenses, and free-tier limits.

## 5. Job / request flow (planned)

1. User selects a location + AOI, chooses analysis modules, defines date range.
2. API creates an analysis job.
3. Orchestrator maps modules to agents and required services.
4. Services retrieve data (with fallbacks).
5. Geospatial processing prepares aligned inputs.
6. Agents produce structured findings (with confidence and limitations).
7. Change Agent compares selected historical periods.
8. Orchestrator fuses evidence, produces explanation + recommendations.
9. Results returned to the dashboard/map; conversation continues naturally.

## 6. Evolution path

- Phase 2: application skeleton, DB/PostGIS schema, API structure. **Implemented** (see Phase 2 checklist).
- Phase 3: location intelligence — geocoding, AOI geometry, interactive map capture, analysis session drafts. **Implemented** (see Phase 3 checklist).
- Phase 4 (Q1): satellite provider retrieval.
- Phase 5 (Q1): weather provider retrieval.
- Q2 Q3: agents + change engine + orchestrator/LLM reasoning + suggestions.
- Phase 4 (Q4): dashboards, 3D, reports, deployment.

Decisions remain flexible; architecture documentation is updated as the design firms up.

## 7. Phase 2 as-built

- **Backend:** `backend/app/` — FastAPI + SQLAlchemy 2 models, `app/services/*` business logic, Pydantic schemas. RBAC for organizations (owner/admin/member) enforced in `organizations` + `workspaces` endpoints; saved locations are private per user.
- **Auth:** access JWT + rotating refresh token stored hashed; cookies for the browser, bearer for API clients (see `app/api/deps.py`).
- **Data:** PostGIS 16/3.4 via Docker Compose (host port 54932), Alembic-managed schema, `geometry(Geometry,4326)` stored via GeoAlchemy2 with SRID-4326 GeoJSON/EWKT parsing in `app/services/geometry.py`.
- **Frontend:** `frontend/` — Next.js 15 App Router, typed API client in `src/lib/api/`, auth provider, cookie-guarded `/dashboard`, rewrites `/api/*` → backend.
- **Quality:** 66 backend tests (per-test disposable PostGIS DB), ruff lint/format clean, `tsc --noEmit` + eslint clean, `next build` green, backend Docker image built and smoke-tested.

## 8. Phase 3 as-built

- **Geocoding:** `app/services/geocoding/` — `PlacesProvider` ABC with `PhotonProvider` (httpx client, rate limiter, bounding-box hints) and a `disabled` fallback that degrades to `503 service_unavailable`; provider resolved once via `functools.lru_cache`. Default endpoint compares no keys.
- **Geometry service:** `app/services/geometry.py` rewritten on shapely 2 + pyproj 3 — strict GeoJSON parsing (single geometry from Feature/FeatureCollection), SRID-4326 pinning with range checks, closed-ring requirement, vertex cap, validity via `explain_validity`, and planimetric area in m² via a LAEA projection centered on the centroid (planar fallback for pathological inputs).
- **Analysis sessions:** new model + `0002_analysis_session_config` migration add AOI geometry (indexed), date range, and agent list; service enforces both-or-neither dates, future-year cap, one AOI source (inline GeoJSON or `saved_location_id`), and RBAC (owner/workspace-member read, owner-only draft mutation).
- **Saved locations:** workspace membership enforced, geometry-derived type/center, and response enrichments (geometry type, GeoJSON, bbox, centroid, area).
- **Frontend map:** Leaflet 1.9 + react-leaflet 5 + leaflet-draw on the analysis page — polygon/rectangle draw handlers start on button click, AOI overlay fit-to-bounds, div-icon place pin, debounced place search with cancellation, GeoJSON file/paste import, export download, validation feedback via `/geometries/validate`, and draft saving/reopening through `/analysis-sessions`.