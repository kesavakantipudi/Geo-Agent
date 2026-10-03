# GeoAgent — Scientific Methodology

> This document records the exact, reproducible definitions behind every computed
> value the system returns. Nothing here is aspirational: each metric that ships
> in an API response is defined below, together with its inputs, thresholds, and
> documented limits. It is a living document the implementation must stay in sync
> with.

Reference: [`PRD.md`](../PRD.md) §28; [`api-spec.md`](api-spec.md) §10.

## 1. Principles

1. **Deterministic indices first.** The only computed spectral indices shipped are
   the Normalized Difference Vegetation Index (NDVI, Phase 6A) and the Normalized
   Difference Water Index (NDWI, Phase 6B), both from Sentinel-2 Level-2A surface
   reflectance (NDVI: B04 red, B08 NIR; NDWI: B03 green, B08 NIR). No machine-learning or
   provider-side "product" values are embedded.
2. **Never fabricate data.** Missing bands, unsupported providers, out-of-AOI
   scenes, or essentially fully-masked AOIs produce an explicit `unavailable`
   result with a machine-readable `code` and `reason`. Missing values are `None`,
   never `0`.
3. **No resampling of reflectance.** If band grids do not align on the window,
   the analysis is reported `unavailable` (`band_grid_mismatch`) rather than
   silently interpolated. Raster reads are **windowed** — only the AOI overlap is
   read into memory.
4. **Provenance everywhere.** Every result carries the exact algorithm version,
   band asset keys + retrieval ids, acquisition date, cloud cover, scene
   provider/platform, window bounds, pixel area, and library versions.
5. **Heuristics are labeled.** Statistical tier labels are heuristic bands for
   user orientation, not a validated crop-health or yield model. Responses and
   charts carry this disclaimer.

## 2. NDVI (Sentinel-2 Level-2A)

- **Formula:** `NDVI = (NIR − RED) / (NIR + RED + ε)`, with a tiny `ε` to avoid
  division by zero. RED = surface reflectance band **B04**, NIR = band **B08**.
- **Domain:** nominally `[-1, 1]`; valid (non-masked) pixels are those where the
  expression is finite. `zero_as_nodata = false` for this index.
- **Band roles per provider** (see `backend/app/services/agri/bands.py`):
  - `planetary-computer` and `cdse`: `red → B04`, `nir → B08`, `cloud_mask → SCL`.
  - Any other provider → `provider_unsupported` unavailable.
- **Input handling:** reflectance is used as-is from the local GeoTIFF; no scale
  factors applied (B04/B08 in the S2 L2A product are already reflectance). The
  AOI is projected (pyproj transform of the AOI polygon into the scene CRS), the
  scene window overlapping the AOI bbox is computed and clamped, that window is
  read, and the AOI mask (shapely within-raster) selects pixels. Reads are size
  capped (`GEOAGENT_AGRI_MAX_WINDOW_PIXELS`, default 20 000 000); larger windows →
  `aoi_window_too_large`.

## 2. NDWI (Sentinel-2 Level-2A, Phase 6B)

- **Formula:** `NDWI = (GREEN − NIR) / (GREEN + NIR + ε)`, with a tiny `ε` to avoid
  division by zero. GREEN = surface reflectance band **B03**, NIR = band **B08**
  (the classic open-water index; also reported as the McFeeters 1996 formulation).
- **Domain:** nominally `[-1, 1]`; valid (non-masked) pixels are those where the
  expression is finite. `zero_as_nodata = true` for this index. `ε` is clamped so
  that a zero-green, zero-nir pixel is marked invalid (not forced to 0).
- **Band roles per provider** (see `backend/app/services/geospatial/bands.py`):
  - `planetary-computer` and `cdse`: `green → B03`, `nir → B08`, `cloud_mask → SCL`.
  - Any other provider → `provider_unsupported` unavailable.
- **Water classification:** `water = NDWI >= threshold (inclusive)`. Default
  threshold `GEOAGENT_AQUA_WATER_THRESHOLD` (= **0.0**), overridable per call via
  `threshold` (must stay within `[-1, 1]`). The applied threshold is echoed in the
  response with `threshold_source` noting it is heuristic and not a validated
  flooded-area model. Only `ndwi` is registered for Aqua
  (`aqua_index_unsupported` for anything else).
- **Area semantics:** `water.area_m2 = water_pixels × pixel_area_m2`;
  `water.pct_of_aoi_area = water_area / aoi_area_m2 × 100`; `water.pixel_pct` is
  the share of *valid* pixels. `non_water.area` is never reported — only pixel
  counts/shares — because land area is not a water-model output.
- **No persistence:** results are derived on demand from the retrieved bands and
  are never stored, so there is no stale-watermark risk.

## 2. Weather context (satellite–weather alignment, Phase 6C)

Weather context summarizes the observed atmospheric conditions **around** a
satellite observation from weather data that GeoAgent already retrieved and
stored in Phase 5. It is a *context*, not a model: it answers "what did the
weather actually do around this scene?", and it never claims that weather
*caused* an index value. Every response states this explicitly
(`note: "…does not attribute cause to the imagery."`).

- **Reads stored data only.** Context is derived on demand from
  `weather_observations` already persisted via `POST /weather/search` and linked
  to the analysis session through `WeatherObservationDiscovery`. Providers are
  **never called** during context derivation, so there is no user-facing latency
  from a live fetch and no new data can be invented at context time. Because
  context is recomputed on every request, it can never go stale.
- **Temporal alignment.** A scene acquired on date `D` draws an inclusive window
  `[D − days_before, D + days_after]` over **whole UTC days**: from `00:00:00`
  of the first day to `23:59:59.999` of the last day, compared in UTC. This makes
  the window independent of the timezone each observation happened to be recorded
  in (a row at local midnight on D±1 is always assigned to the correct day). The
  default is `days_before = days_after = GEOAGENT_WEATHER_CONTEXT_WINDOW_DAYS`
  (default `1`); `0,0` means *same-day only*. The window actually used is echoed
  in the response (`period`). Window sizes are per-request overridable (capped at
  `GEOAGENT_WEATHER_CONTEXT_MAX_WINDOW_DAYS`).
- **Aggregation rules** (deterministic; see `backend/app/services/weather/context.py`):
  - `temperature_2m`, `apparent_temperature`, `dewpoint_2m`, `relative_humidity_2m`,
    `cloud_cover`, `pressure_msl`, `surface_pressure`, `soil_*`, `wind_speed_10m` →
    **mean** over the window.
  - `temperature_2m_max` → **max**; `temperature_2m_min` → **min**;
    `wind_gusts_10m` → max.
  - `precipitation`, `rain`, `showers`, `snowfall`, `et0_fao_evapotranspiration` →
    **sum** over the window. A stored `0.0` is a genuine provider measurement
    ("no measurable precipitation in that interval") and is summed like any value;
    an interval with no record contributes nothing. Partial-window sums are
    explicitly flagged ("sum over N of M recorded samples").
  - `weather_code` and `wind_direction_10m` are **not aggregated** (categorical /
    circular-vector quantities; a "mean vector" or "average weather-code" would be
    meaningless).
  - **Units guard:** a variable is aggregated only when every stored row for it in
    the window shares the same `units`; a mixed-units case is reported
    `available=false` with an explicit `units_mismatch` note rather than a
    silently wrong number.
- **Missing data contract.** A variable with no rows in the window, or whose value
  is absent, keeps `value = None` — **never `0`**. Zero is only ever a real stored
  measurement. This mirrors the Phase 5 fetch contract (missing stays missing).
- **Completeness accounting.** For provider fetches, every variable shares one
  time axis, so the context uses an explicit, self-consistent denominator:
  - `sample_count` = number of distinct stored timestamps for the variable in the
    window;
  - `expected_count` = the largest number of distinct timestamps seen for *any*
    context row in the window — the shape a "complete" set for that provider would
    have, without us assuming any particular temporal resolution;
  - `coverage_pct = sample_count / expected_count × 100`; overall
    `completeness_pct` = mean coverage across requested variables;
  - `partial = true` when coverage < 100 % or any requested variable is
    unconvertible — shown in the UI as "Weather coverage is incomplete for the
    selected period."
  - Zero observations in the window → status `unavailable`, code
    `no_weather_observations`, and an explicit reason (not empty numbers).
- **Honesty on intelligence results.** Agri and Aqua responses attach
  `weather_context` (default window/variables) even to `unavailable` analyses.
  The companion text always describes the *corresponding period* and reports
  precipitation/humidity/temperature as observations; it never states or implies
  e.g. "NDVI dropped because rainfall decreased" — correlation of timing is
  recorded, causation is not inferred.

## 3. Change detection (two-scene comparison, Phase 6D)

A comparison is anchored to an analysis session (its AOI and access rules) and
**two** scenes the caller can access: `before_scene_id` (earlier) and
`after_scene_id` (later). The temporal ordering rule is
`before.acquisition_date < after.acquisition_date`; the same scene twice or two
same-day scenes is rejected (`same_scene` / `before_after_order`). Results are
**derived on demand** — nothing is persisted.

### Aligned comparison grid

- The comparison grid is the **before scene's AOI-window grid**.
- If the after scene's window grid is geometrically identical (same CRS, north-up,
  resolution within `1e-3 m`), the grids are used as-is (`alignment.mode = "none"`).
- Otherwise the after bands are **nearest-neighbour resampled** onto the before
  window grid (`alignment.mode = "nearest"`, `resampled_with` recorded). Nearest
  resampling is used for integer-labelled data only — it is never used to invent
  reflectance values. Grids whose CRS is incompatible or whose resolution differs
  beyond tolerance → `incompatible_raster_alignment` (explicit, not silently warped).

### Comparison mask ("pixels valid in both observations")

Change is only defined where both observations are valid:

| Field | Definition |
| --- | --- |
| `total_pixels` | AOI-window pixels before masking. |
| `before_valid_pixels` / `after_valid_pixels` | Valid pixels per observation (cloud-masked). |
| `comparison_valid_pixels` | Valid in **both** (the pixels change is computed over). |
| `invalid_pixels` | `total − comparison_valid`. |
| `comparison_valid_pct` | `comparison_valid / total × 100`. |

A cloud-masked invalid pixel is **never** counted as change; it simply drops out of
the comparison (255 in the mask). If fewer than
`GEOAGENT_CHANGE_MIN_VALID_FRACTION` (0.01) of pixels are comparable →
`insufficient_valid_pixels`; if exactly zero overlap the scenes still share →
`no_valid_comparison_pixels`.

### Vegetation change (NDVI delta)

- `delta = NDVI(after) − NDVI(before)` pixelwise over the comparison mask.
- **Inclusive, documented heuristic boundary** (default
  `change_vegetation_threshold = 0.10`, validated `(0, 2]`):
  - `delta >= +threshold` → **increase**
  - `delta <= −threshold` → **decrease**
  - otherwise → **stable**
- Mask codes: `0` stable, `1` increase, `2` decrease, `255` invalid. The boundary
  is surfaced as `classification.boundary` and in the UI; the note states this is a
  **documented threshold, not a validated change assertion**.

### Water change (NDWI membership by date)

- Water is classified per observation with the shared Aqua boundary
  `water = NDWI >= threshold` (inclusive; default `0.0`, validated `[−1, 1]`).
- The per-pixel transition between the two dates yields the classes:
  `0` unchanged (non-water both), `1` new water (gained), `2` lost water,
  `3` persistent water, `255` invalid.
- `water_extent` reports `before_pixels`, `after_pixels`, `delta_pixels` and the
  share of the comparison mask each date was water. Water is reported as a
  transition count, so **no delta statistics block** is emitted
  (`statistics.delta == null`).

### Statistics

`statistics.before` / `statistics.after` (and vegetation `statistics.delta`) are
mean/median/stddev/min/max computed **over the comparison mask only** — never over
per-observation validity alone — so before/after/change numbers cover the same
pixels. Canopy-change and water area percentages are shares of
`comparison_valid_pixels`, not the unmasked AOI.

### Weather is reference, not cause

When `include_weather: true`, two descriptive weather contexts (before, after) are
attached via `weather_context_service.default_context`. They express correlation
context around the two observations only and are never used to assert causation.

### Change-detection unavailable codes

| Code | When |
| --- | --- |
| `bands_not_retrieved` | Required bands (vegetation B04/B08/(SCL); water B03/B08/(SCL)) not retrieved. |
| `insufficient_valid_pixels` | Comparable valid fraction below `GEOAGENT_CHANGE_MIN_VALID_FRACTION`. |
| `incompatible_raster_alignment` | Before/after grids cannot be aligned on a shared grid. |
| `no_valid_comparison_pixels` | Zero pixels valid in both observations. |
| `provider_unsupported` | No band-role map for the scene's provider. |

The top-level response is `completed` when at least one requested type completed;
per-type blocks carry their own `unavailable` and a partial invalid mask where
meaningful.

## 4. Cloud/quality masking

- SCL (Scene Classification Layer) values: `0` no-data, `1` saturated/defective,
  `2` dark-area pixels, `3` cloud shadows, `4` vegetation, `5` non-vegetated,
  `6` water, `7` unclassified, `8` cloud medium probability, `9` cloud high
  probability, `10` thin cirrus, `11` snow.
- **Masked classes when `mask_clouds: true`:** `[0, 1, 3, 8, 9, 10, 11]`
  (no-data / defective / shadows / cloud / cirrus / snow). This matches standard
  ESA SCL usage and Phase 4 scene filtering.
- SCL is optional: if masking is requested but the SCL band was not retrieved
  (and the provider exposes a `cloud_mask` role), the analysis completes unmasked
  **with a warning** — masking failure must never suppress a computable signal.
  If B04/B08 are missing entirely → `bands_not_retrieved`.
- `excluded_pixel_pct` = fraction of AOI-window pixels excluded by masking (or
  `0` when unmasked). `valid_pixel_pct` = valid ÷ `aoi_pixel_count`.

## 5. Statistics

Computed over the valid (masked) NDVI raster within the AOI mask:

| Field | Definition |
| --- | --- |
| `min` / `max` | Minimum / maximum finite NDVI. |
| `mean` | Arithmetic mean of valid NDVI. |
| `median` | 50th percentile of valid NDVI. |
| `stddev` | Population standard deviation of valid NDVI. |
| `valid_pixel_count` | Pixels inside the AOI that survived masking. |
| `aoi_pixel_count` | Pixels inside the AOI before masking. |
| `valid_pixel_pct` | `valid_pixel_count / aoi_pixel_count × 100`. |
| `excluded_pixel_pct` | `100 − valid_pixel_pct`. |
| `sampled_area_m2` | `valid_pixel_count × pixel_area_m2`. |
| `pixel_area_m2` | Pixel area from the affine transform map (per-band), in m². |

All calculations drop non-finite values (NaN/inf `!= value`). `None`/empty →
index not computed.

## 6. Vegetation-condition tiers (heuristic)

Tier bands are **orientation only**. They are surfaced in responses under
`classification.threshold_source` and labeled in the UI as heuristic, not a
validated crop-health/yield/drought model.

| Tier | NDVI range | Typical reading | Status color |
| --- | --- | --- | --- |
| `very_low` | `< 0.10` | Bare soil / water / sparse cover | stone/grey |
| `low` | `[0.10, 0.25)` | Sparse or stressed vegetation | orange |
| `moderate` | `[0.25, 0.40)` | Moderate green cover | yellow |
| `high` | `[0.40, 0.60)` | Dense healthy vegetation | lime |
| `very_high` | `>= 0.60` | Very dense vegetation | green |

- `overall` tier = the tier of the **mean NDVI**.
- `dominant_tier` = the tier covering the **largest `pixel_pct`**; ties are broken
  toward the *lower* NDVI tier (deliberate pessimism for decision support).
- `pixel_pct` sums are the share of *valid* AOI pixels in each tier.

## 7. Unavailable reasons (honesty contract)

| Code | When |
| --- | --- |
| `provider_unsupported` | No band-role map for the scene's provider. |
| `bands_not_retrieved` | Required B04/B08 (or explicitly-requested SCL) not retrieved. |
| `band_read_failed` | A band GeoTIFF could not be opened/read. |
| `crs_transform_failed` | AOI could not be transformed into the scene CRS. |
| `no_overlap` | AOI bbox does not overlap the scene footprint. |
| `aoi_window_too_large` | AOI window exceeds `GEOAGENT_AGRI_MAX_WINDOW_PIXELS`. |
| `band_grid_mismatch` | Band windows do not share the same grid (never resampled). |
| `insufficient_valid_pixels` | Valid pixel fraction below `GEOAGENT_AGRI_MIN_VALID_FRACTION` (0.01). |

Only **completed** analyses are persisted and listable; unavailable state is
returned (HTTP 200) but not stored.

## 8. Algorithm and provenance

- `processing.algorithm = "geoagent-ndvi-v1"` (Agri) or `"geoagent-ndwi-v1"`
  (Aqua). Both run on the shared windowed core in `backend/app/services/geospatial`
  (`normalized_difference`, `analyze_index_ratio`), where capital letters in the
  name denote the normalized-difference formula family (`ND**I`), not a sub-version.
- Change detection runs the same NDVI/NDWI computations per scene and compares on
  the before-grid through `backend/app/services/change_detection`
  (`alignment.verify_alignment`/`resample_nearest`, `classification`,
  `encoding.encode_mask_png`); `provenance.engine_version =
  "geoagent-change-detection-v1"`, `derived_on_demand = true`.
- `processing.libraries` records `rasterio`, `affine`, `numpy`, `shapely`,
  `pyproj` versions used for the computation.
- `processing.window` records the `(col_off, row_off, width, height)` window in
  the scene raster grid actually read; `acquisition_date`, `cloud_cover`,
  `provider`, `platform`, `provider_scene_id` identify the source scene.

## 9. Verification

- Unit tests verify index math for known synthetic scenes (pure vegetation, mixed
  field/water, pure water), tier/water thresholds, histogram/tie-break, statistics,
  and the unavailable codes — `backend/tests/test_agri_unit.py` (NDVI),
  `backend/tests/test_aqua_unit.py` (NDWI, inclusive threshold boundary, area math,
  masking).
- API tests verify auth/access, unavailable responses, persistence of completed
  Agri results only, and 422 validation codes — `backend/tests/test_agri.py`,
  `backend/tests/test_aqua.py`. The Aqua suite additionally asserts that the
  endpoint creates **no** `aqua_%` table (derived-on-demand contract).
- Weather-context tests: `backend/tests/test_weather_context_unit.py` verifies the
  pure layer (UTC alignment windows incl. month boundaries and same-day windows,
  mean/sum/min/max/no-aggregation, the units-mismatch guard, missing-stays-`None`,
  precipitation sums including recorded zeros, and coverage scaling);
  `backend/tests/test_weather_context.py` exercises the endpoint end to end
  (auth 401, unknown session/scene 404, `scene_not_associated`, window echo,
  variable/provider validation, the explicit `no_weather_observations` state,
  precipitation aggregation through the real Phase 5 storage path, and the
  embedded `weather_context` on completed/unavailable Agri and Aqua results).
- Change-detection tests: `backend/tests/test_change_detection_unit.py` verifies
  the pure alignment/classification layer (inclusive vegetation boundary, water
  transitions, offset-grid nearest resampling, CRS/resolution mismatch,
  invalid-never-changes) and the full two-scene pipeline for both types;
  `backend/tests/test_change_detection.py` exercises the endpoint end to end
  (auth/access, `same_scene`/`before_after_order`, per-type unavailable states,
  completed provenance + weather contexts, and the derived-on-demand contract —
  no `change%` table exists after analysis).