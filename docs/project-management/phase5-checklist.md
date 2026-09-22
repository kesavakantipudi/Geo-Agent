# Phase 5 — Weather and Environmental Infrastructure: Checklist and Acceptance Criteria

**Goal:** provider-backed weather observation retrieval — current conditions, forecast, and historical/archive (reanalysis) data served over a pluggable provider abstraction, persisted session-scoped with full provenance (provider, model, data type, grid cell, timezone, attribution), and surfaced through a dashboard panel for any analysis session AOI + date range.

> Items marked `[x]` were completed during Phase 5 work and have been verified (commands run, checks green). Items marked `[ ]` remain for manual/team or later-phase action. Nothing is marked complete without a check to back it up.

## Backend — weather provider abstraction

- [x] `app/services/weather/base.py`: `WeatherProvider` ABC (`fetch_weather`, `name`, `attribution`, `user_agent`, `noncommercial`, `close`), `WeatherError`, `DisabledProvider`, `RateLimiter` (from settings), `optional_float` helper; documented BBox contract `(min_lat, min_lon, max_lat, max_lon)`.
- [x] `app/services/weather/openmeteo.py`: Open-Meteo provider with three config-driven endpoint kinds — forecast/current (`openmeteo_forecast_url`), reanalysis archive (`openmeteo_archive_url`), and the seamless historical-forecast product; `OPENMETEO_VARIABLES` registry; `_normalize` keeps **real provider values only** (missing → `None`, never `0`), attaches `latitude`/`longitude`/`model`/`timezone`/`units`/`provenance`/`attribution` per point, and drops variables the caller did not request.
- [x] `app/services/weather/__init__.py`: exports `OpenMeteoProvider`, `WeatherError`, `get_enabled_weather_provider_names`, `get_weather_providers`.
- [x] Settings: `GEOAGENT_WEATHER_ENABLED_PROVIDERS`, `_MAX_POINTS_PER_AOI`, `_MAX_VARIABLES`, `_TIMEOUT_SECONDS`, `_RATE_PER_SECOND`, `_CACHE_TTL_SECONDS`, `_ATTRIBUTION`, `_USER_AGENT`, `_NONCOMMERCIAL`, plus `GEOAGENT_OPENMETEO_*` URL/timeout/rate vars (in `app/core/config.py`, root `.env.example`, `backend/.env.example`).

## Backend — persistence and migration

- [x] Model (`app/models/weather_observation.py`): `WeatherObservation` rewritten to **per-variable rows** (`provider`, `observed_at`, `latitude`, `longitude`, `variable`, `value`, `units`, `units_doc`, `model`, `data_type`, `timezone`, `provenance`, `attribution`) with unique `uq_weather_obs_point_variable` and index on the point tuple; legacy Phase 2 scalar columns retained nullable so no data is erased and the ORM stays in sync with migrated databases.
- [x] New `WeatherObservationDiscovery` model: FKs observation → `weather_observations` (CASCADE), session → `analysis_sessions` (CASCADE), `discovered_by` → `users` (SET NULL); unique `(observation_id, analysis_session_id)`, indices on both FK columns.
- [x] Migration `0004_weather_observations` (down_revision `0003_satellite_scene_assets`): adds 9 columns, the point-variable unique constraint + index, and the discovery table + 2 indices; symmetric downgrade. Verified `upgrade head → downgrade 0003 → upgrade head` on a disposable PostGIS DB (`MIGRATION CHAIN OK`, `alembic current` reports `0004_weather_observations (head)`).
- [x] `alembic check` against a migrated head DB reports **no weather diffs** (only pre-existing PostGIS quirk diffs: `spatial_ref_sys` table, the geometry GIST index, and the token-hash unique index which predate Phase 5).

## Backend — service and endpoints

- [x] `app/services/weather_service.py`: `fetch_weather_endpoint` resolves a session AOI/date range or inline AOI + dates, validates date ranges, requires dates for `history`/`archive`/`reanalysis`/`historical_forecast`, validates geometry (`require_area=True`), converts bbox `[min_lon,min_lat,max_lon,max_lat]` → provider order, validates variables/providers, per-provider fetch with `WeatherError` → per-provider status (never a request failure), per-variable expansion with `None` skipped, `GEOAGENT_WEATHER_MAX_POINTS_PER_AOI` cap → `truncated`, upsert + session discovery splice, commit.
- [x] `list_observations_for_session` (owner/workspace-member only) and `get_observation` (`weather_observation_not_found` 404 for cross-user access).
- [x] Endpoints (`app/api/v1/endpoints/weather.py`): `POST /weather/search`, `GET /weather/sessions/{id}/observations`, `GET /weather/observations/{id}`; registered in the v1 router.
- [x] Error codes: `aoi_required`, `date_range_required`, `weather_variable_unknown`, `weather_too_many_variables`, `weather_provider_not_enabled`, `weather_disabled`, `weather_observation_not_found` (`WeatherError` → `503 unavailable`).

## Backend — tests

- [x] `tests/weather_mocks.py`: `httpx.MockTransport` handler for forecast/archive/historical-forecast endpoints (no network), error/timeout modes, request capture.
- [x] `tests/test_weather.py` — **19 passing**: auth required; AOI-or-session required; date-range required for history; full search + persistence + provider status for a session; missing values never fabricated as `0`; provider `_normalize` missing stays `None`; unknown variable / too many variables / unknown provider / weather disabled; point-vs-polygon AOI; invalid units/data_type (422); provider HTTP error + timeout surface in per-provider status; archive data type routes to the archive URL with dates; imperial units route to `temperature_unit=fahrenheit`; idempotent re-search; list + get endpoints; cross-user observation 404.
- [x] `uv run ruff check .` and `uv run ruff format .` → pass; full suite `uv run pytest -q` → **106 passed** (87 baseline + 19 weather) against per-test disposable PostGIS databases.

## Frontend — weather panel

- [x] `src/lib/api/types.ts`: `WeatherDataTypes`, `WeatherUnits`, `WeatherProvenance`, `WeatherObservationPoint`, `WeatherProviderStatus`, `WeatherSearchRequest`, `WeatherSearchResponse`.
- [x] `src/lib/api/weather.ts`: `searchWeather` (uses the correct `analysis_session_id` key), `listSessionObservations`, `getObservation`.
- [x] `src/components/analysis/WeatherDiscoveryPanel.tsx`: data-type select (current/forecast/history/archive/reanalysis/historical-forecast), metric/imperial select, variable chips (default `temperature_2m` + `relative_humidity_2m`), fetch / load-saved, per-provider status chips (success count or error), per-variable tables (time, value+units, source lat/lon), provenance + attribution footer, truncated/empty/hint states.
- [x] `AnalysisWorkspace.tsx`: new **Weather observations** section gated on an active session (AOI + config dates propagated).
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing Phase 4 warnings); `npm run build` → production build green (9 routes + middleware).

## Documentation

- [x] `docs/api-spec.md` — Phase 5 weather endpoints documented as implemented (request/response shapes, data types, caps, error codes, bbox contract).
- [x] `docs/project-management/roadmap.md` — Phase 5 marked implemented.
- [x] `.env.example` + `backend/.env.example` — weather + Open-Meteo env vars documented.

## Acceptance / manual test procedure

1. `docker compose up -d db`, then `cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.
2. `cd frontend && npm run dev`.
3. Register/login at `/login`; open **Analysis**.
4. Draw/save an AOI draft (or reuse one) and reopen it so the **Weather observations** section is enabled.
5. Pick a data type (`Current conditions`, or a date-bounded type like `History` once dates are set) and variables; click **Fetch weather**.
6. Confirm observations render per variable with time, value, units, source coordinates, and the attribution line **"Weather data by Open-Meteo.com"**.
7. Confirm `/docs` shows `POST /api/v1/weather/search`, `GET /api/v1/weather/sessions/{id}/observations`, `GET /api/v1/weather/observations/{id}`.
8. Disable the provider (`GEOAGENT_WEATHER_ENABLED_PROVIDERS=none`), restart the backend → weather search returns `400 weather_disabled` gracefully.

## Known notes / remaining team actions

- [ ] Live Open-Meteo reachability was verified via mocked handlers in tests; run one real fetch against `api.open-meteo.com` on a fresh dev boot to confirm firewall-free egress.
- [ ] The in-process response cache setting (`GEOAGENT_WEATHER_CACHE_TTL_SECONDS`) is declared but the provider has no cache implementation yet — a Q2 optimization.
- [ ] `historical_forecast` and forecast-lag/skill comparison are provider-ready but not yet exercised by a dedicated UI filter (data type already selectable).
- [ ] Add CI (lint + typecheck + backend tests) with `GEOAGENT_AUTH_SECRET_KEY` in CI secrets only.

## When this is done

Proceed to **Phase 6 — Agri Agent** (see [`roadmap.md`](roadmap.md)).