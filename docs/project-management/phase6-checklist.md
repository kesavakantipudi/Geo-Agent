# Phase 6 — Geospatial Intelligence: Checklist and Acceptance Criteria

**Goal:** compute genuine geospatial intelligence over locally retrieved satellite data —
**6A** vegetation/agriculture (Agri Agent), **6B** water (Aqua Agent), **6C** weather
integration, **6D** change detection (Change Agent), **6E** historical intelligence — each
sub-phase sharing the Phase 6 honesty contract: measured values only, explicit
`unavailable` states (never fabricated numbers), documented-and-exposed thresholds,
provenance-rich results, and full verification before commit/push.

> Items marked `[x]` were completed during Phase 6 work and have been verified
> (commands run, checks green). Items marked `[ ]` remain for manual/team or later-phase
> action. Nothing is marked complete without a check to back it up.

## Phase 6A — Agri Agent: agricultural geospatial intelligence

### Method: a shared raster core

- [x] `app/services/geospatial/raster.py`: windowed raster primitives — `RasterWindow`,
  `raster_info`, `project_bounds` (Geometry→scene CRS via pyproj), `window_from_bounds`
  (clamped), `read_window`, `reproject_nearest` (labels only, never reflectance),
  `inside_aoi_mask`, `pixel_area_m2`; dedicated `geospatial` package `__init__`.
- [x] Settings `GEOAGENT_AGRI_MAX_WINDOW_PIXELS` (20 000 000) and
  `GEOAGENT_AGRI_MIN_VALID_FRACTION` (0.01) in `app/core/config.py`.

### Agri index computation (`app/services/agri/`)

- [x] `indices.py`: `IndexSpec` + `INDEX_REGISTRY`; NDVI `(B08−B04)/(B08+B04+ε)`.
- [x] `bands.py`: provider band-role map — `planetary-computer` and `cdse` →
  `{red: B04, nir: B08, cloud_mask: SCL}`; unknown provider → `provider_unsupported`.
- [x] `classification.py`: SCL cloud mask classes `(0,1,3,8,9,10,11)`; NDVI heuristic tiers
  (`very_low <0.10 … very_high ≥0.60`), `tier_histogram`, `dominant_tier` (tie → lower-NDVI
  tier wins), `threshold_source` string.
- [x] `statistics.py`: min/max/mean/median/stddev/counts/pct/area over finite pixels only.
- [x] `__init__.py`: `AgriError`, `AgriUnavailable`, `compute_agri_index` (unavailable codes:
  `band_read_failed`, `crs_transform_failed`, `no_overlap`, `aoi_window_too_large`,
  `band_grid_mismatch`, `insufficient_valid_pixels`).

### Persistence and API

- [x] Model `app/models/agri_analysis.py` (FK scene, session, user snapshot, statistics
  JSONB, index/status/tier fields) exported from `app/models/__init__.py`.
- [x] Migration `0005_agri_analyses` (down_revision 0004); chain verified
  `upgrade head → downgrade 0003 → upgrade head` on a disposable PostGIS DB; dev DB at
  head; `alembic check` shows no agri drift (only pre-existing PostGIS/geometry/token quirks).
- [x] Schemas `app/schemas/agri.py`: request/result/summary models;
  `SUPPORTED_INDICES = ("ndvi",)`.
- [x] Service `app/services/agri_service.py`: `analyze` (session AOI or `aoi` override,
  scene ownership/access, band-role resolution, SCL optional-but-warned, per-index
  computation, persist completed only), `get_analysis`, `list_analyses_for_session`;
  `get_scene_orm` made public on `satellite_scene_service`.
- [x] Endpoints `app/api/v1/endpoints/agri.py`: `POST /agri/analyze`,
  `GET /agri/analyses/{id}`, `GET /agri/sessions/{id}/analyses`; registered in v1 router.
- [x] Error codes: `agri_index_unsupported`, `agri_index_required`, `session_has_no_aoi`,
  `agri_service_unavailable` (503); per-result unavailable codes (see methodology doc).

### Tests

- [x] `tests/agri_mocks.py`: synthetic Level-2A-like GeoTIFFs in UTM zone 43 N
  (pure vegetation, mixed field/water), clear/cloudy SCL, empty band handling,
  `seed_retrieval` helper reuse.
- [x] `tests/test_agri_unit.py` — **26 passing**: NDVI math on known scenes, stats
  definitions, tier thresholds + tie-break, unavailable codes, window clamping.
- [x] `tests/test_agri.py` — **15 passing**: auth required, session access control,
  unavailable not persisted, completed persisted + listable, 422 validation,
  scene-not-found, JSON-schema shape checks.
- [x] Full suite `uv run pytest -q` → **147 passed** (87 baseline + 19 weather + 41 agri);
  `uv run ruff check .` and `uv run ruff format --check` → clean for new code.

### Frontend — Agri panel

- [x] `src/lib/api/types.ts`: `AgriIndexName`, `AgriIndexInfo`, `AgriStatistics`,
  `AgriTier`, `AgriClassification`, `AgriCloudInfo`, `AgriBandOutput`, `AgriSceneReference`,
  `AgriUnavailableInfo`, `AgriAnalysisResult`, `AgriAnalyzeRequest/Response`,
  `AgriAnalysisSummary`.
- [x] `src/lib/api/agri.ts`: `analyzeAgri`, `getAgriAnalysis`, `listSessionAgriAnalyses`.
- [x] `src/components/analysis/AgriPanel.tsx`: scene selector (listSessionScenes), per-band
  retrieval status chips (B04/B08/SCL + hint to the Scene panel), mask-clouds toggle,
  Analyze NDVI button, statistics grid, tier share bar + legend, overall/dominant tiers,
  provenance footer (formula, thresholds, bands, window area, disclaimer), unavailable
  state card, saved-analyses list (view).
- [x] `AnalysisWorkspace.tsx`: new **Agricultural intelligence** section gated on an active
  session.
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing Phase 4
  warnings in `SceneDiscoveryPanel.tsx` / `satellite.ts`); `npm run build` → green.

### Documentation

- [x] `docs/api-spec.md` §10 — Phase 6A endpoints, result shape, error/unavailable codes.
- [x] `docs/scientific-methodology.md` — NDVI formula/bands, masking classes, statistics,
  heuristic tier table, unavailable contract, verification.
- [x] `docs/project-management/roadmap.md` — Phase 6 note + this checklist linked.
- [x] `.env.example` + `backend/.env.example` — `GEOAGENT_AGRI_*` vars documented.

## Phase 6B — Aqua Agent (planned)

- [ ] Water index (NDWI from B03/B08) + a water classification/tier scheme following the
      Agri pattern (windowed reads, unavailable contract, provenance).
- [ ] Persistence (migration), service, endpoints (`/aqua/...`), tests, dashboard panel.
- [ ] Historical water-spread comparison hooks (shared with 6E).

## Phase 6C — Weather integration (planned)

- [ ] Correlate agri/aqua outputs with stored weather observations (Phase 5) for an AOI in
      `correlation` terms only (never causation claims).

## Phase 6D — Change Detection (planned)

- [ ] Multi-date index differencing (NDVI/NDWI) over two scenes; significance thresholds
      configurable and documented; ML/CV where feasible.

## Phase 6E — Historical intelligence (planned)

- [ ] Date-range workflows, per-period snapshots, comparison timelines, provenance across
      time.

## Acceptance / manual test procedure (6A)

1. `docker compose up -d db`, then `cd backend && uv run alembic upgrade head && uv run uvicorn app.main:app --reload`.
2. `cd frontend && npm run dev`.
3. Register/login and open **Analysis**; save an AOI session and reopen it.
4. In **Scene discovery**, search + download `B04`, `B08`, `SCL` for one Sentinel-2 scene.
5. In **Agricultural intelligence**, select the scene and **Analyze NDVI**; confirm stats,
   tier bar, and provenance render, and a saved row appears in the list.
6. Select a scene with no band assets → confirm the missing-band chips and that the analyze
   returns the explicit unavailable reason.
7. Confirm `/docs` lists the three `/agri` routes.

## Known notes / remaining team actions (6A)

- [ ] A production-quality scale value for B04/B08 is assumed already-reflectance; verify
      against a live Planetary Computer L2A scene end-to-end on the first real egress fetch.
- [ ] `proj` database init is exercised via reproject_nearest in unit tests only; confirm
      `init` is available in the deployment image if runtime reprojection is needed (labels).
- [ ] 6C/6D correlation + change-detection thresholds are intentionally deferred to their own
      sub-phases; the NDVI/NDWI computation core is shared.

## When this is done

After 6A is committed (message `feat(agri): add agricultural geospatial intelligence`) and
pushed to `origin/main`, proceed to **Phase 6B — Aqua Agent**.