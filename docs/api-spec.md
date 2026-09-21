# GeoAgent — API Specification

> **Status:** Phase 3 (Location Intelligence) is implemented on top of Phase 2: `GET /places/search` (provider-based geocoding), `POST /geometries/validate` (strict GeoJSON parsing + shapely/pyproj validation and area estimation), full `analysis-sessions` CRUD (AOI, date range, agent selection), and an enriched saved-locations response (geometry type/GeoJSON, bbox, centroid, area). The suite has 66 passing integration tests. Endpoints below not yet implemented remain planned; planned modules stay as recorded design intent.

Reference: [`PRD.md`](../PRD.md) §28.

## 8. Phase 3 — implemented endpoints

All under the Phase 2 base path `/api/v1`, same cookie/bearer auth and error contract. Error codes added in Phase 3: `invalid_bbox`, `geometry_not_valid`, `geometry_too_complex`, `aoi_not_polygon`, `aoi_empty`, `invalid_date_range`, `invalid_agents`, `session_not_draft`, `analysis_session_not_found`, `saved_location_not_found`, `saved_location_no_geometry`, `service_unavailable`.

| Method | Path | Summary |
| --- | --- | --- |
| `GET` | `/places/search` | Geocode a free-text `q` (2+ chars) via the configured provider (default Photon). Optional `limit` (default from `GEOAGENT_GEOCODER_MAX_RESULTS`, max 10) and `bbox` (`minLon,minLat,maxLon,maxLat`). Returns `[{id, provider, label, display_name, bbox, center}]`. Provider errors → `503 service_unavailable`. |
| `POST` | `/geometries/validate` | Body `{geometry, require_area?}`. Accepts any GeoJSON geometry (Feature/FeatureCollection unwrapped, single geometry) or EWKT/`SRID=4326;...` text. Enforces SRID 4326, coordinate ranges, closed rings, and the `GEOAGENT_MAX_GEOMETRY_POINTS` vertex cap. Returns `{geometry_type, is_valid, point_count, bbox, centroid, area_m2_approx, srid, warnings}` with validation errors named by field. |
| `GET/POST` | `/analysis-sessions` | List sessions for the current user (optional `?workspace_id=` restricts to one workspace; members of the workspace see its sessions) / create a draft. Create body: `{title?, workspace_id?, aoi?, saved_location_id?, start_date?, end_date?, agents?}` — exactly one of `aoi` (GeoJSON Polygon/MultiPolygon with area) or `saved_location_id`; dates optional but must come as both-or-neither with `end >= start` and `end` no more than `GEOAGENT_ANALYSIS_MAX_FUTURE_YEARS` ahead; `agents` is a deduped non-empty list from `agri, aqua, weather, change`. |
| `GET/PATCH/DELETE` | `/analysis-sessions/{id}` | Read (owner or workspace member) / update (owner, while `status=draft`) / delete (owner). PATCH accepts the same fields as create and returns the updated session. |
| `GET/POST` | `/saved-locations`, `GET/PATCH/DELETE` `/saved-locations/{id}` | Phase 2 surface extended: create now requires membership for a linked workspace (404 when absent), derives `location_type`/`center_lat`/`center_lon` from geometry when a custom geometry is given, returns `geometry_type`, `geometry_geojson`, `bbox`, `centroid`, and `area_m2_approx`. |

Session and saved-location responses include `aoi` / `geometry_geojson` as GeoJSON objects and `area_m2_approx` computed with a Lambert Azimuthal Equal-Area projection at the centroid (shapely + pyproj).

## 6. Phase 2 — implemented endpoints

Base path `/api/v1`. Authentication: HTTP-only cookies `geoagent_access` (JWT, 15 min) and `geoagent_refresh` (rotated, 30 days) plus optional `Authorization: Bearer <access>`; the refresh endpoint also accepts a `refresh_token` body field.

Errors: `{"error": {"code", "message", "details": []}}`.

| Method | Path | Summary |
| --- | --- | --- |
| `POST` | `/auth/register` | Create account; sets cookies. |
| `POST` | `/auth/login` | Email/password login; sets cookies. |
| `POST` | `/auth/refresh` | Rotate refresh token (cookie or body); sets cookies. |
| `POST` | `/auth/logout` | Revoke refresh token; clears cookies. |
| `GET` | `/auth/me` | Current user. |
| `GET` / `PATCH` | `/users/me` | Read / update own profile. |
| `GET` | `/organizations` | Organizations the user belongs to. |
| `POST` | `/organizations` | Create (slugs: `[a-z0-9-]`, 3–63 chars). |
| `GET` / `PATCH` | `/organizations/{id}` | View (members) / update (owner/admin). |
| `GET` | `/organizations/{id}/members` | Members with roles. |
| `POST` | `/organizations/{id}/members` | Add member (owner/admin; `role` only `admin`/`member`). |
| `PATCH` | `/organizations/{id}/members/{user_id}` | Change role (owner/admin; owner role only by owners). |
| `DELETE` | `/organizations/{id}/members/{user_id}` | Remove member (owner/admin). |
| `GET` / `POST` | `/organizations/{id}/workspaces` | List / create workspace. |
| `PATCH` | `/workspaces/{id}` | Rename/describe (org member). |
| `GET` | `/saved-locations` | List current user's saved locations. |
| `POST` | `/saved-locations` | Create (GeoJSON geometry or EWKT string, SRID 4326). |
| `GET` / `PATCH` / `DELETE` | `/saved-locations/{id}` | Read / update / delete (owner only). |
| `GET` | `/health` | App status + version. |
| `GET` | `/health/db` | Database reachability + PostGIS version. |

Schemas and interactive docs: run the backend and open `/docs` (OpenAPI). Tests covering the surface: `backend/tests/`.

## 7. Planned (unchanged intent for later phases)

Originally planned module groups (`satellite`, `weather`, `agriculture`, `water`, `change`, `geoagent`, `chat`, `analysis`, `reports`) remain as design intent. Phase 2 seeded the persistence for several of them (analyses, satellite scenes, weather observations, chat sessions/messages, reports tables exist in the schema). API versioning practice is fixed at `/api/v1`. Phase 3 covered the `location` group (geocoding + geometry + persisted analysis sessions) end to end; agent execution, satellite retrieval, weather, and change detection remain future phases.

## 1. Design notes

- REST-style API over JSON, served by a planned Python/FastAPI backend.
- Async job handling for long-running analyses (satellite retrieval, ML inference).
- Provider abstraction: `/satellite`, `/weather`, and geocoding endpoints call service interfaces with fallback providers.
- All future endpoints will require authentication (planned Q2/Q3); exact auth scheme TBD.
- Requests must validate geometry (polygon/bbox) and date ranges server-side.

## 2. Planned module groups

The routing below is indicative and will evolve.

| Group | Planned responsibility | Example routes |
| --- | --- | --- |
| `location` | Geocoding, place search, AOI geometry, coordinates | `GET /api/location/search` `POST /api/location/geometry` |
| `satellite` | Imagery search/retrieval, metadata, bands | `POST /api/satellite/search` `GET /api/satellite/{id}` |
| `weather` | Current conditions, history, forecast | `GET /api/weather/current` `GET /api/weather/history` `GET /api/weather/forecast` |
| `agriculture` | Agri Agent analysis jobs and results | `POST /api/agriculture/analyze` `GET /api/agriculture/{job_id}` |
| `water` | Aqua Agent analysis jobs and results | `POST /api/water/analyze` `GET /api/water/{job_id}` |
| `change` | Change Agent analysis and comparison | `POST /api/change/compare` `GET /api/change/{job_id}` |
| `geoagent` | Orchestrated multi-agent analysis | `POST /api/geoagent/analyze` |
| `chat` | Agent conversation bound to an analysis context | `POST /api/chat` `GET /api/chat/{session_id}` |
| `analysis` | Persisted analyses, sessions, history | `GET /api/analysis` `GET /api/analysis/{id}` |
| `reports` | Report generation (planned Q4) | `POST /api/reports/{analysis_id}` |

## 3. Planned request example (satellite search)

```json
{
  "geometry": "POLYGON((...))",
  "start_date": "2026-08-01",
  "end_date": "2026-09-01",
  "max_cloud_cover": 20,
  "source": "SENTINEL_2"
}
```

## 4. Planned response conventions

- Structured JSON with `data` / `meta` separation where useful.
- Every analysis result distinguishes:
  - **Observations** (measured data)
  - **Model outputs** (ML/CV results with confidence where available)
  - **AI interpretation** (LLM explanation)
  - **Suggestions** (recommendations)
- Errors are returned with a stable machine-readable code and a human message.
- Provider limits/failures are reported explicitly rather than hidden.

## 5. Versioning and evolution

- API versioning practice is fixed (`/api/v1/...`); see §6 for what Phase 2 implemented.