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

## Phase 6B — Aqua Agent: water intelligence via NDWI

### Shared core (extracted for 6A + 6B)

- [x] `app/services/geospatial/` now owns the whole windowed index pipeline: `bands.py`
  (provider band-role maps incl. NDWI `{green: B03, nir: B08, cloud_mask: SCL}`,
  `resolve_band_keys`), `indices.py` (`IndexSpec` with band roles, `INDEX_REGISTRY`,
  `WATER_INDEX_REGISTRY={ndwi}`, `compute_ndvi`/`compute_ndwi`), `analysis.py`
  (`normalized_difference`, `index_info`, `window_for`, `window_pixel_count`,
  `analyze_index_ratio`, `IndexAnalysisUnavailable`), `statistics.py`, `raster.py`.
- [x] `app/services/agri/` reduced to an adapter: `__init__.py` re-exports the core API and
  `compute_agri_index` keeps the exact 6A output shape; `bands.py`/`indices.py`/`statistics.py`
  are compatibility shims; `classification.py` imports `SCL_CLOUD_MASK_CLASSES` from the core.
- [x] `satellite_scene_service.completed_retrieval_paths(db, scene_id, asset_keys)` made public
  so both Agri and Aqua resolve retrieved band paths; `agri_service` rewired to it.
- [x] 6A regression-proof: **41/41 agri tests** still pass after extraction (byte-identical NDVI).

### Aqua index computation (`app/services/aqua/`)

- [x] `indices` via `WATER_INDEX_REGISTRY`: NDWI `(B03−B08)/(B03+B08+ε)` (McFeeters 1996).
- [x] `classification.py`: `DEFAULT_THRESHOLD = 0.0`, `BOUNDARY =
  "water = NDWI >= threshold (inclusive)"`, `classify`, `water_summary`
  (water area/`pct_of_aoi_area`/`pixel_pct`; non-water pixel count/share only),
  `LIMITATIONS_NOTE` surfaced as `threshold_source`.
- [x] `__init__.py`: `AquaError`, `AquaUnavailable`, `compute_aqua_index` (thin adapter over
  `analyze_index_ratio`; unavailable codes mirror Agri).

### Persistence and API

- [x] **No persistence by design (derived on demand).** There is no migration and no
  `aqua_analyses` table; every call recomputes from the retrieved bands, so stored results can
  never go stale. `POST /aqua/analyze` returns completed or `unavailable` (HTTP 200) results;
  there are no `GET /aqua/...` endpoints.
- [x] Schemas `app/schemas/aqua.py`: `AquaAnalyzeRequest` (incl. `threshold` override),
  `AquaIndexInfo`, `AquaBandOutput`, `AquaCloudInfo`, `AquaStatistics`, `AquaWaterSummary`,
  `AquaNonWaterSummary`, `AquaClassification`, `AquaSceneReference`, `AquaProcessingInfo`,
  `AquaUnavailableInfo`, `AquaAnalysisResult`, `AquaAnalyzeResponse`;
  `SUPPORTED_INDICES = ("ndwi",)`.
- [x] Service `app/services/aqua_service.py`: `analyze` (session AOI or `aoi` override,
  scene ownership/access via Phase 6A changes, threshold default from settings + `[-1,1]`
  validation, SCL optional-but-warned, per-index computation, nothing persisted).
- [x] Endpoint `app/api/v1/endpoints/aqua.py`: `POST /aqua/analyze`; registered in v1 router.
- [x] Error codes: `aqua_index_unsupported`, `aqua_index_required`, `session_has_no_aoi`,
  `invalid_aqua_threshold` (400); per-result unavailable codes mirror Agri.
- [x] Settings `GEOAGENT_AQUA_WATER_THRESHOLD` (0.0), `GEOAGENT_AQUA_MIN_VALID_FRACTION`
  (0.01), `GEOAGENT_AQUA_MAX_WINDOW_PIXELS` (20 000 000) in `app/core/config.py`.

### Tests

- [x] `tests/aqua_mocks.py`: synthetic NDWI-ready scenes (pure water `NDWI ≈ +0.55`,
  pure land `NDWI = −0.2`, split water/land), clear/cloudy SCL, `write_aqua_bands` reusing
  the agri band writer on the same UTM grid.
- [x] `tests/test_aqua_unit.py` — **23 passing**: NDWI math incl. zero-denominator/NaN/inf,
  VNIR-negative, inclusive threshold boundary (0.0 is water), grid-structure stats, water
  area math, threshold overrides on known scenes, SCL masking, missing-SCL warning, zeros
  as nodata, scale invariance, and all unavailable codes.
- [x] `tests/test_aqua.py` — **14 passing**: auth, unknown session/scene, cross-user access,
  unsupported/empty indices, invalid threshold, `bands_not_retrieved` /
  `insufficient_valid_pixels` unavailable, completed provenance, threshold echo, SCL-missing
  warning fallback, `mask_clouds: false`, and the derived-on-demand contract (no `aqua_%`
  table exists after analysis).
- [x] Full suite: `python -m pytest -q` (env `GEOAGENT_TEST_PG_HOST=127.0.0.1`
  `GEOAGENT_TEST_PG_PORT=55432`) → **184 passed** (147 pre-6B + 37 aqua);
  `python -m ruff check .` and `python -m ruff format --check` → clean.

### Frontend — Aqua panel

- [x] `src/lib/api/types.ts`: `AquaIndexName/Info`, `AquaStatistics`, `AquaWaterSummary`,
  `AquaNonWaterSummary`, `AquaClassification`, `AquaCloudInfo`, `AquaBandOutput`,
  `AquaSceneReference`, `AquaUnavailableInfo`, `AquaAnalysisResult`,
  `AquaAnalyzeRequest/Response`.
- [x] `src/lib/api/aqua.ts`: `analyzeAqua` (session id + scene id inside payload).
- [x] `src/components/analysis/AquaPanel.tsx`: scene selector, B03/B08/SCL retrieval chips,
  NDWI threshold input (default 0.0, bounded [−1,1]), mask-clouds toggle, Analyze button,
  statistics grid, open-water vs non-water share bar + legend, provenance footer (formula,
  applied threshold + boundary, bands, window area, heuristic disclaimer), unavailable card.
- [x] `AnalysisWorkspace.tsx`: new **Water intelligence** section gated on an active session.
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing Phase 4
  warnings); `npm run build` → green.

### Documentation

- [x] `docs/api-spec.md` §11 — Phase 6B endpoint, result shape, error/unavailable codes,
  derived-on-demand note + overall suite count 184.
- [x] `docs/scientific-methodology.md` — NDWI formula/bands, inclusive threshold boundary,
  area semantics, heuristic disclaimer, shared-core algorithm/provenance, verification.
- [x] `docs/project-management/roadmap.md` — 6B completed point.
- [x] `.env.example` + `backend/.env.example` — `GEOAGENT_AQUA_*` vars documented.

## Phase 6C — Weather integration: weather context (complete)

Correlate agri/aqua outputs with stored weather observations (Phase 5) for an AOI in
`correlation` terms only (never causation claims) — implemented as a deterministic
**weather-context** layer that aligns stored observations with a satellite observation.

### Context layer (`app/services/weather/context.py` — pure, deterministic)

- [x] `AGGREGATORS` map (mean for temperature/humidity-family, `max`=`temperature_2m_max`,
  `min`=`temperature_2m_min`, **sum** for `precipitation`/`rain`/`showers`/`snowfall`/`et0_...`,
  `none` for `weather_code`/`wind_direction_10m`.
- [x] `alignment_window`/`window_dates` — inclusive **UTC-day** window `[D − days_before, D + days_after]`
  (timezone-independent; `0,0` = same-day only); `expected_timestamp_count`,
  `aggregate_observations` (units-mismatch guard, missing stays `None` never `0`, partial-window
  sum warning), completeness `coverage_pct = sample_count / expected_count × 100`.

### Service + API

- [x] `app/services/weather_context_service.py`: `build_context` (session = access boundary,
  scene access via `get_scene_orm`, optional `require_associated` → `scene_not_associated`),
  `default_context` (embedded default window/variables), window/variable/provider validation
  reusing Phase 5 rules (`weather_context_window_out_of_range`, `weather_variable_unknown`,
  `weather_provider_not_enabled`).
- [x] Schemas `app/schemas/weather.py`: `WeatherContextRequest`, rich `WeatherContext`
  (status available/unavailable, scene, `satellite_observation`, echoed `period`,
  per-variable aggregation `WeatherContextVariable`, completeness, provenance, attribution,
  `partial`, `unavailable` `{code,reason,details}`, descriptive-not-causal `note`),
  `WeatherContextResponse`.
- [x] Endpoint `POST /weather/context` in `app/api/v1/endpoints/weather.py` — reads **stored**
  observations only, never calls a provider.
- [x] Settings `GEOAGENT_WEATHER_CONTEXT_WINDOW_DAYS` (1), `..._MAX_WINDOW_DAYS` (31),
  `..._VARIABLES` (5-variable default) in `app/core/config.py` + both `.env.example`s.
- [x] Integration: `weather_context` field on `AgriAnalysisResult` and `AquaAnalysisResult`;
  recomputed on demand in `agri_service.analyze`/`get_analysis` and `aqua_service.analyze`
  (never persisted — can't go stale; attached to completed **and** unavailable results).

### Tests

- [x] `tests/test_weather_context_unit.py` — **16 passing**: UTC alignment (default/same-day/
  month-boundary), timezone determinism, mean/min/max/sum, precipitation incl. recorded `0.0`,
  non-aggregatable variables, units mismatch, missing-stays-`None`, non-finite filtering,
  partial-window sum warning, expected-count/coverage scaling.
- [x] `tests/test_weather_context.py` — **16 passing**: auth 401, unknown session/scene 404,
  cross-user access 404, `scene_not_associated` 400, happy-path aggregation through the real
  Phase 5 storage path (mean/coverage/partial, window echo, attribution), same-day window,
  window-out-of-range, unknown variable/provider, explicit `no_weather_observations`,
  observations-outside-window, precipitation sum, and embedded context on completed/unavailable
  Agri + Aqua results.
- [x] Full suite `python -m pytest -q` (env `GEOAGENT_TEST_PG_HOST=127.0.0.1`
  `GEOAGENT_TEST_PG_PORT=55432`) → **216 passed** (184 pre-6C + 32 weather-context);
  `python -m ruff check .` and `python -m ruff format --check` → clean.

### Frontend — weather context

- [x] `src/lib/api/types.ts`: `WeatherContext`, `WeatherContextVariable`, `WeatherContextPeriod`,
  `WeatherContextSceneRef`, `WeatherContextUnavailable`, `WeatherContextRequest/Response`;
  `weather_context` field added to `AgriAnalysisResult` and `AquaAnalysisResult`.
- [x] `src/lib/api/weather.ts`: `getWeatherContext(sessionId, sceneId, payload?)`.
- [x] `src/components/analysis/WeatherContextCard.tsx`: reusable card — period echo,
  variable grid (label/value/units, "Unavailable" for missing never `0`, sample counts on
  partial coverage), incomplete-coverage note, warnings, attribution, explicit
  "No weather observations available for this period.", descriptive-not-causal note.
- [x] `AgriPanel.tsx` + `AquaPanel.tsx`: WeatherContextCard rendered for both **completed and
  unavailable** results.
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing Phase 4
  warnings); `npm run build` → green; `frontend/src/lib` tracking unaffected.

### Documentation

- [x] `docs/api-spec.md` §12 — weather-context endpoint, aggregation/completeness rules,
  `no_weather_observations`, embedded field on agri/aqua, suite count 216.
- [x] `docs/scientific-methodology.md` — temporal alignment, aggregation rules, missing-data
  contract, completeness accounting, honesty note (context, not causation).
- [x] `docs/project-management/roadmap.md` — 6C completed point.
- [x] `.env.example` + `backend/.env.example` — `GEOAGENT_WEATHER_CONTEXT_*` vars documented.

### Known notes / remaining team actions (6C)

- [ ] 6C correlation is implemented as *descriptive context* only; explicit correlation
      statistics and thresholded "correlated change" assertions are intentionally deferred to
      6D/6E, where the Change Agent can compare periods.

## Phase 6D — Change Detection (complete)

Multi-date NDVI/NDWI differencing over **two** satellite scenes anchored to an analysis
session (its AOI and access rules). Results are **derived on demand** — nothing is
persisted. Each requested type is reported as a `completed` block with per-pixel class
masks and area statistics, or an explicit `unavailable` block with a structured reason —
never fabricated numbers. Change is defined only over pixels valid in both observations.

### Alignment core (`app/services/change_detection/`) — pure, deterministic

- [x] `alignment.py`: `to_transform`, `verify_alignment` (CRS equality, north-up, resolution
  tolerance 1e-3; mismatches → `incompatible_raster_alignment`), `resample_nearest` (after →
  before window grid, nearest-neighbour on a reprojected grid — labels only, never
  reflectance), `window_bounds_ll`, `extract_grid`; identical grids → `mode == "none"`,
  otherwise `mode == "nearest"` with `resampled_with` recorded.
- [x] `classification.py`: vegetation `delta = NDVI_after − NDVI_before` with inclusive
  boundary (`>= +threshold` increase, `<= −threshold` decrease, default
  `change_vegetation_threshold = 0.10`, validated `(0, 2]`); water per-date
  `NDWI >= threshold` (`aqua_water_threshold` default 0.0, validated `[−1, 1]`,
  `boundary = "water = NDWI >= threshold (inclusive)"`); mask codes 0/1/2/3 per class,
  255 = invalid; `vegetation_summary`/`water_summary`/`class_summary`/`water_change`/
  `vegetation_change`; `vegetation_limitations_note` ("documented threshold, not a
  validated change assertion").
- [x] `encoding.py`: `encode_mask_png` → rasterio `MemoryFile` PNG (uint8, nodata 255) →
  base64 **data URI** (no Pillow dependency).
- [x] `__init__.py`: `ChangeDetectionError`, `ChangeDetectionUnavailable`,
  `compute_change_detection`/`compute_change_for_type`, `unavailable_block`, `_compare_payloads`
  — stats + percentages always over the comparison (both-valid) mask.

### Service, schemas, API

- [x] `app/services/change_detection_service.py`: session access boundary, scene
  ownership/association (`scene_not_associated`), ordering rule **before.acquisition_date
  strictly < after.acquisition_date** (same-day → 400), optional per-call AOI override,
  band-role resolution, per-type computation, two descriptive weather contexts
  (`weather_context_service.default_context`, `include_weather` opt-out) and provenance.
- [x] Schemas `app/schemas/change_detection.py`: request
  (`analysis_session_id`, `before_scene_id`, `after_scene_id`, `types`, `mask_clouds`,
  `vegetation_threshold`, `water_threshold`, `include_weather`), `ChangeSceneRef` (metadata
  incl. constellation), `ChangeIndexInfo`, `ChangeBandOutput`, `ChangeCloudInfo`,
  `ChangeGrid`, `ChangeAlignment`, `ChangeMasking`, `ChangeStatBlock`/`ChangeStatistics`
  (delta `None` for water — transitions, not a signed delta), `ChangeClassification`
  (with `water_extent` for water), `ChangeMask`, `ChangeUnavailableInfo`, `ChangeTypeBlock`,
  `ChangeProvenance`, `ChangeDetectionResponse`.
- [x] Endpoint `POST /change-detection/analyze` in `app/api/v1/endpoints/change_detection.py`;
  registered in v1 router.
- [x] 400 error codes: `same_scene`, `before_after_order`, `scene_not_associated`,
  `session_has_no_aoi`, `change_type_required`, `change_type_unsupported`,
  `invalid_vegetation_threshold`, `invalid_water_threshold`. Per-type unavailable codes:
  `bands_not_retrieved`, `insufficient_valid_pixels`, `incompatible_raster_alignment`,
  `no_valid_comparison_pixels`, `provider_unsupported`; top-level
  `all_requested_analyses_unavailable` when nothing completed.
- [x] Settings `GEOAGENT_CHANGE_VEGETATION_THRESHOLD` (0.10),
  `GEOAGENT_CHANGE_MIN_VALID_FRACTION` (0.01), `GEOAGENT_CHANGE_MAX_WINDOW_PIXELS`
  (20 000 000), `GEOAGENT_CHANGE_DETECTION_ENGINE_VERSION` (`geoagent-change-detection-v1`)
  in `app/core/config.py` + both `.env.example`s.

### Core integration

- [x] `app/services/geospatial/analysis.py`: `processing` now carries an additive `"grid"`
  (`crs`, `transform`, `width`, `height`, `pixel_size_m`) — backwards-safe; Pydantic drops
  it for agri/aqua response models; all pre-existing agri/aqua/weather tests unchanged green.

### Tests

- [x] `tests/test_change_detection_unit.py` — **20 passing**: inclusive vegetation boundary,
  bad thresholds, water transitions, invalid-never-changes, overrides, alignment identity /
  offset / CRS-mismatch / resolution-mismatch / window bounds, PNG encoding, and full
  pipeline cases for both types (decrease+stable, increase, lost/new water, no-comparison
  pixels, incompatible alignment, insufficient valid pixels, nearest resample).
- [x] `tests/test_change_detection.py` — **21 passing** (needs PG test DB at
  `127.0.0.1:55432`): auth, unknown session/scene, cross-user access, `scene_not_associated`,
  `same_scene`, same-day & reversed order, empty/unsupported types, invalid thresholds,
  `bands_not_retrieved` unavailable, partial-unavailable keeps top-level completed, completed
  vegetation + provenance + weather contexts, `include_weather:false`, water both-types,
  `mask_clouds:false`, missing-SCL warning fallback, and derived-on-demand contract (no
  `change%` table after analysis).
- [x] Full suite `python -m pytest -q` (env `GEOAGENT_TEST_PG_HOST=127.0.0.1`
  `GEOAGENT_TEST_PG_PORT=55432`) → **257 passed** (216 pre-6D + 41 change-detection);
  `python -m ruff check .` and `python -m ruff format --check` → clean.

### Frontend — Change detection panel

- [x] `src/lib/api/types.ts`: `ChangeType/ChangeStatus`, `ChangeSceneReference`,
  `ChangeIndexInfo`, `ChangeBandOutput`, `ChangeCloudInfo`, `ChangeGrid`, `ChangeAlignment`,
  `ChangeMasking`, `ChangeComparison`, `ChangeStatBlock/ChangeStatistics`, `ChangeClassSummary`,
  `ChangeWaterExtent`, `ChangeClassification`, `ChangeMask`, `ChangeUnavailableInfo`,
  `ChangeTypeBlock`, `ChangeProvenance`, `ChangeDetectionRequest/Response`.
- [x] `src/lib/api/change.ts`: `analyzeChange` (before/after scene ids inside payload).
- [x] `src/components/analysis/ChangeDetectionPanel.tsx`: before/after scene selects
  (sessions scenes sorted by acquisition date, same-day guard), vegetation/water toggles,
  mask-clouds + weather-context toggles, NDVI-delta & NDWI threshold inputs with inline
  validation, per-scene band retrieval chips (B03/B04/B08/SCL), Analyze button, per-type
  completed cards (legend, stat grid over compared pixels, class-area table, water extent,
  alignment/masking provenance, limitations note) and unavailable cards, map-overlay
  segmented toggle (mask data-URI on the map), weather context cards, top-level unavailable.
- [x] `src/components/map/LocationMap.tsx`: new `MaskOverlay` — `L.imageOverlay` from the
  mask data URI to `[[south, west],[north, east]]`, opacity 0.75, fit-bounds on change;
  new optional `maskOverlay` prop.
- [x] `AnalysisWorkspace.tsx`: lifted `changeOverlay` state; new **Change detection**
  section gated on an active session; overlay wiring map ↔ panel.
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing Phase 4
  warnings); `npm run build` → green; `frontend/src/lib` tracking unaffected.

### Documentation

- [x] `docs/api-spec.md` §13 — change-detection endpoint, request/response shape,
  ordering rule, error/unavailable codes, derived-on-demand note, suite count 257.
- [x] `docs/scientific-methodology.md` — comparison mask (before ∩ after valid),
  alignment grid + nearest resampling, inclusive classification boundaries, class codes,
  statistics semantics, weather as non-causal reference, limitations.
- [x] `docs/project-management/roadmap.md` — 6D completed point.
- [x] `.env.example` + `backend/.env.example` — `GEOAGENT_CHANGE_*` vars documented.

## Phase 6E - Historical intelligence (complete)

Session-scoped **timeline over discovered scenes**, derived on demand (no migration,
nothing persisted).

### Timeline core (`app/services/historical_service.py`)

- [x] Session is authoritative: AOI, access rules, base date range. No AOI override.
- [x] Observations ordered **oldest → newest by acquisition date** (STAC datetime, never
      ingestion/retrieval order), deduplicated by scene, ties broken by id.
- [x] `coverage` always explicit: count, first/last date, span, ordering, `compared_pairs`,
      `same_day_pairs_skipped`, `limited`, gaps (`gap_days`) and notes.
- [x] Same-day pairs are **never compared**; irregular gaps are reported, never
      interpolated.
- [x] Optional date override: both-or-none, `end >= start`, must stay inside the session
      range (`invalid_date_range`, `date_range_outside_session`).

### Reuse (no duplicated index math)

- [x] Per-observation metrics via the shared core `analyze_index_ratio` — agri settings for
      NDVI, aqua settings + `water_summary` for NDWI (identical §2/§4 semantics).
- [x] Consecutive-pair events via the Phase 6D engine `compute_change_index` (same alignment,
      comparison mask, inclusive boundaries, class areas, masks, statistics).
- [x] `resolve_band_keys` + `completed_retrieval_paths` for role→asset resolution;
      `analysis_session_service.get` / `validate_date_range` for access + ranges;
      `satellite_scene_service.list_scenes_for_session` for scene discovery;
      `weather_context_service.default_context` for descriptive weather.

### Deterministic labels and descriptive trends

- [x] Vegetation event = dominant class by pixel count over comparison-valid pixels
      (tie → `vegetation_stable`); water event = net new-vs-lost balance (tie →
      `water_stable`). Basis text shipped with every event.
- [x] Trends = first/latest/min/max + absolute (and relative) change + contributing
      observation count + evidence-capped `basis`; no extrapolation, no forecasting.

### Honesty contract

- [x] Missing stays missing: per-observation and per-event `status: "unavailable"` nodes with
      structured codes (`bands_not_retrieved`, `provider_unsupported`,
      `insufficient_valid_pixels`); top-level `no_historical_observations` /
      `all_requested_analyses_unavailable`.
- [x] Weather labelled "Weather context", never "Cause"; descriptive only.
- [x] Validation codes: `session_has_no_aoi`, `historical_type_required`,
      `historical_type_unsupported`, `invalid_vegetation_threshold`,
      `invalid_water_threshold`.
- [x] Provenance: `engine_version = "geoagent-historical-intelligence-v1"`,
      `derived_on_demand`, `ordering_semantics`, `change_reuse`, `area_method`, `libraries`.

### Service, schemas, API

- [x] `backend/app/schemas/historical.py` (`HistoricalRequest`, `HistoricalResponse` and
      block models, reusing the 6D index/mask/statistics/unavailable models).
- [x] `backend/app/api/v1/endpoints/historical.py` — `POST /api/v1/historical/analyze`
      (registered in `app/api/v1/router.py`); no GET endpoints (nothing persisted).
- [x] `GEOAGENT_HISTORICAL_ENGINE_VERSION` in `app/core/config.py` + both `.env.example`
      files (commented, optional — matches the documented-default pattern).
- [x] **No database migration required** — derived on demand.

### Tests

- [x] `backend/tests/test_historical_unit.py` — ordering/dedup/ties, gap vs same-day, trend
      basis, deterministic event labels (13 tests).
- [x] `backend/tests/test_historical.py` — auth/access, no-AOI, type/threshold validation,
      date-override rules, zero/one/many observations, oldest→newest ordering, gaps,
      same-day not compared, missing-band unavailable nodes, completed events for both
      types, weather contexts on/off, no `historical%` table, plus a cross-phase regression
      (historical + change detection + agri + aqua + weather on one session) (21 tests).
- [x] Full suite green: **291 passed**; `ruff check` / `ruff format --check` clean.

### Frontend - Historical intelligence panel

- [x] `frontend/src/lib/api/types.ts` — historical types; `frontend/src/lib/api/historical.ts`
      — `analyzeHistorical`.
- [x] `HistoricalIntelligencePanel.tsx` — coverage card, **observed-points-only** charts
      (categorical axis so irregular sampling is never drawn as regular; segments only
      between adjacent measured points), observation table (oldest → newest) with explicit
      `unavailable (…)` labels, event cards with threshold/basis/comparison evidence,
      trend cards, per-observation weather contexts.
- [x] Mask selection reuses the existing `ChangeOverlay` / `ChangeMaskOverlay` map wiring
      (no new map code); section gated on an active session.
- [x] `npm run typecheck` → clean; `npm run lint` → 0 errors (only pre-existing warnings);
      `npm run build` → green.

### Documentation

- [x] `docs/api-spec.md` §14 — historical endpoint, timeline/coverage/events/trends shape,
  ordering rules, error/unavailable codes, derived-on-demand + no-migration note,
  suite count 291.
- [x] `docs/scientific-methodology.md` §3A — ordering semantics, per-observation reuse of
  §2/§4 math, deterministic labels, coverage/gaps, descriptive-only trends, weather as
  non-causal reference, explicit non-goals (no forecasting/attribution).
- [x] `docs/project-management/roadmap.md` — 6E completed point.

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

6A was committed (`feat(agri): add agricultural geospatial intelligence`) and pushed to
`origin/main`. **6B is committed as `feat(aqua): add water intelligence`** and pushed. **6C is
committed as `feat(weather): integrate weather context with geospatial intelligence`** and
pushed. **6D is committed as `feat(change-detection): add satellite change detection engine`**
and pushed; after verifying a clean tree, proceed to **Phase 6E — Historical intelligence**.