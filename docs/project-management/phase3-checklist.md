# Phase 3 — Location Intelligence: Checklist and Acceptance Criteria

**Goal:** interactive location and area-of-interest (AOI) selection — search a place, draw or import a polygon/rectangle AOI on a Leaflet map, validate it server-side, choose agents, a date range, and a workspace, and save draft analysis sessions that later phases execute. Persist AOI geometry and session configuration in PostGIS.

> Items marked `[x]` were completed during Phase 3 work and have been verified (commands run, checks green). Items marked `[ ]` remain for manual/team or later-phase action. Nothing is marked complete without a check to back it up.

## Backend — geocoding

- [x] Provider abstraction (`app/services/geocoding/base.py`): `PlacesProvider` ABC, `GeocodingError`, `DisabledProvider`, rate limiter, cached singleton resolver (`get_provider`).
- [x] Photon provider (`app/services/geocoding/photon.py`): `httpx.AsyncClient`, User-Agent header, bounding-box hint, label building; reached over the network in tests.
- [x] `GET /api/v1/places/search` (`q`, optional `limit`/`bbox`): 400 `invalid_bbox` on malformed bbox, 503 `service_unavailable` on provider failure/disabled provider.
- [x] Settings: `GEOAGENT_GEOCODER_PROVIDER`, `_PHOTON_URL`, `_TIMEOUT_SECONDS`, `_RATE_PER_SECOND`, `_USER_AGENT`, `_MAX_RESULTS` (env-driven, `.env.example` updated).

## Backend — geometry service

- [x] shapely 2 + pyproj 3 dependencies added (`backend/pyproject.toml`, `uv sync`).
- [x] `app/services/geometry.py`: strict GeoJSON parsing (Point/LineString/Polygon/Multi*/GeometryCollection, Feature/FeatureCollection unwrap), SRID pinned to 4326, coordinate-range checks, closed rings required for polygons, vertex cap from `GEOAGENT_MAX_GEOMETRY_POINTS` (default 2000).
- [x] Validity via shapely `is_valid` + `explain_validity`; area (m²) via LAEA projection at centroid with planar fallback.
- [x] `POST /api/v1/geometries/validate` returns `geometry_type`, `is_valid`, `point_count`, `bbox`, `centroid`, `area_m2_approx`, `srid`, `warnings`; field-scoped errors (`geometry_not_valid`, `geometry_too_complex`, `aoi_not_polygon`, `aoi_empty`).
- [x] `approximate_area_m2` unit-tested for point/line/polygon/multi-polygon and pathological inputs.

## Backend — analysis sessions

- [x] Migration `0002_analysis_session_config` (down_revision `0001_initial`): `aoi_geometry` (Geometry, 4326, GIST index), `start_date`, `end_date`, `agents` JSONB. Verified `upgrade head` on dev DB and via the test suite.
- [x] Model + Pydantic schemas (`app/schemas/analysis_session.py`) with `AGENT_CODES = agri/aqua/weather/change`.
- [x] Service (`app/services/analysis_session_service.py`): create/get/list/update/delete; both-or-neither date validation, `end >= start`, `end <= today + GEOAGENT_ANALYSIS_MAX_FUTURE_YEARS`; AOI from inline GeoJSON **or** `saved_location_id` (not both); deduped non-empty agents; RBAC — owner or workspace member may view, owner-only edit while `draft`, owner-only delete.
- [x] Endpoints `GET/POST /api/v1/analysis-sessions`, `GET/PATCH/DELETE /api/v1/analysis-sessions/{id}`, wired into the v1 router.
- [x] `list` honors optional `workspace_id` (owner-only list already restricts to the user's own sessions).

## Backend — saved locations (enriched)

- [x] Workspace membership enforced on create (`404` when the workspace is not the caller's).
- [x] `location_type` and center auto-derived from provided geometry; response adds `geometry_type`, `geometry_geojson`, `bbox`, `centroid`, `area_m2_approx`.

## Backend — quality gates

- [x] `uv run ruff check .` → passes; `uv run ruff format .` applied.
- [x] `uv run pytest -q` → **66 passed** (geometry validation, geocoding, analysis sessions, saved-locations enrichment + Phase 2 surface) against per-test disposable PostGIS databases.
- [x] Migration chain `0001_initial → 0002_analysis_session_config`; `alembic current` reports head after apply.

## Frontend — map and AOI

- [x] Dependencies installed and version-locked: `leaflet@1.9.4`, `react-leaflet@5.0.0`, `leaflet-draw@1.0.4`, `@types/leaflet`, `@types/leaflet-draw`.
- [x] `src/lib/map/config.ts`: env-configurable tile URL/attribution/max zoom (`NEXT_PUBLIC_MAP_*`), sensible OSM defaults.
- [x] `src/components/map/LocationMap.tsx`: MapContainer + TileLayer + AOI overlay (fit-to-bounds) + place pin (div icon, avoids default-marker asset issue) + **direct draw handlers** (polygon/rectangle start drawing on button click, `allowIntersection: false`, created layer converted to GeoJSON geometry) + draw-mode hint banner. Leaflet + leaflet-draw CSS imported.
- [x] `src/components/map/PlaceSearch.tsx`: debounced (300 ms) place search with in-flight cancellation, dropdown results, error/empty states.
- [x] `src/components/map/AoiPanel.tsx`: draw / cancel, GeoJSON file import, paste-and-validate, GeoJSON export download, clear, and live validation info (type, vertices, area, SRID).
- [x] `src/components/analysis/AnalysisConfigPanel.tsx`: title, workspace select, date range, saved-location reuse, agent checkboxes, save/new, save states.
- [x] `src/components/analysis/SessionsList.tsx`: lists sessions with status badges and agent tags, reopen (loads AOI + config back into the canvas).
- [x] `src/components/analysis/AnalysisWorkspace.tsx`: orchestrates map + panels; clientside validation via `/geometries/validate`; create/update drafts; `next/dynamic` map import (`ssr: false`).
- [x] `/dashboard/analysis` page renders the workspace; `.geo-pin__dot` styles in `globals.css`.

## Frontend — quality gates

- [x] `npm run typecheck` → clean (`tsc --noEmit`).
- [x] `npm run lint` → clean (ESLint 9 flat config, no warnings).
- [x] `npm run build` → production build green (9 routes + middleware).
- [x] Env example `frontend/.env.local.example` documents `NEXT_PUBLIC_MAP_*`.

## Documentation

- [x] `backend/README.md` — implemented endpoints, layout (geocoding), migration 0002, 66-test suite, env vars.
- [x] `frontend/README.md` — map stack, new lib/components, env vars.
- [x] `docs/api-spec.md` — Phase 3 endpoints documented as implemented.
- [x] `docs/architecture.md` — service layer, backend/frontend layers, Phase 3 as-built.
- [x] `docs/README.md` index + roadmap updated.
- [x] Root `README.md` status, core features, testing counts, and structure updated.

## Acceptance / manual test procedure

1. `docker compose up -d db`, then `cd backend && cp .env.example .env && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.
2. `cd frontend && cp .env.local.example .env.local && npm install && npm run dev`.
3. Register/login at `/login`; open **Analysis**.
4. **Place search:** type a city (≥2 chars), pick a result → map re-centers and drops a pin.
5. **Draw AOI:** click *Draw polygon*, click 3+ vertices on the map (Esc/right-click to finish via leaflet-draw) → the AOI highlights and the info card shows type, vertices, approximate area, valid. Repeat for *Draw rectangle*.
6. **Import/export:** export the AOI, edit/delete some coordinates → import the file back (or *Paste*) → server validation rejects invalid rings/out-of-range coordinates with a clear message.
7. **Config:** set a title, workspace (optional), dates (test `end < start` shows an inline error), tick agents, and save a draft.
8. **Sessions:** the new draft appears in *Your analysis sessions*; *Reopen* restores the AOI polygon and settings; opening the same account in a second tab shows the session persisted.
9. Confirm `/docs` shows `/api/v1/places/search`, `/api/v1/geometries/validate`, `/api/v1/analysis-sessions*` with request schemas.
10. Set `GEOAGENT_GEOCODER_PROVIDER=disabled` and restart the backend → place search returns `503 service_unavailable` gracefully.

## Known notes / remaining team actions

- [ ] npm `audit` reports 2 advisories via `next`'s bundled `postcss` (pre-existing); the suggested fix (bumping to `next@16`) is a breaking change and is deferred — re-evaluate when upgrading Next.
- [ ] Build the frontend Docker image once (`docker compose build frontend`) — image unchanged since Phase 2.
- [ ] Add CI (lint + typecheck + backend tests) with `GEOAGENT_AUTH_SECRET_KEY` in CI secrets only.
- [ ] Fresh-server boot smoke test of the Phase 3 backend on an unused port (pytest already covers app import, routes, and migrations via TestClient).

## When this is done

Proceed to **Phase 4 — Satellite Intelligence Infrastructure** (see [`roadmap.md`](roadmap.md)).