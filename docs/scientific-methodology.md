# GeoAgent — Scientific Methodology

> This document records the exact, reproducible definitions behind every computed
> value the system returns. Nothing here is aspirational: each metric that ships
> in an API response is defined below, together with its inputs, thresholds, and
> documented limits. It is a living document the implementation must stay in sync
> with.

Reference: [`PRD.md`](../PRD.md) §28; [`api-spec.md`](api-spec.md) §10.

## 1. Principles

1. **Deterministic indices first.** The only computed spectral index shipped in
   Phase 6A is the Normalized Difference Vegetation Index (NDVI) from Sentinel-2
   Level-2A surface reflectance (B04 red, B08 NIR). No machine-learning or
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

## 3. Cloud/quality masking

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

## 4. Statistics

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

## 5. Vegetation-condition tiers (heuristic)

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

## 6. Unavailable reasons (honesty contract)

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

## 7. Algorithm and provenance

- `processing.algorithm = "geoagent-ndvi-v1"`.
- `processing.libraries` records `rasterio`, `affine`, `numpy`, `shapely`,
  `pyproj` versions used for the computation.
- `processing.window` records the `(col_off, row_off, width, height)` window in
  the scene raster grid actually read; `acquisition_date`, `cloud_cover`,
  `provider`, `platform`, `provider_scene_id` identify the source scene.

## 8. Verification

- Unit tests (`backend/tests/test_agri_unit.py`) verify index math for known
  synthetic scenes (pure vegetation, mixed field/water), tier thresholds,
  histogram/tie-break, statistics, and the unavailable codes.
- API tests (`backend/tests/test_agri.py`) verify auth/access, unavailable
  responses, persistence of completed results only, and 422 validation codes.