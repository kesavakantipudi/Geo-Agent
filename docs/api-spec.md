# GeoAgent — API Specification

> **Status:** Phase 2 delivered a working `/api/v1` (auth, users, organizations, workspaces, saved locations, health) with 21 passing integration tests. Endpoints below not yet implemented remain planned; planned modules stay as recorded design intent.

Reference: [`PRD.md`](../PRD.md) §28.

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

Originally planned module groups (`location`, `satellite`, `weather`, `agriculture`, `water`, `change`, `geoagent`, `chat`, `analysis`, `reports`) remain as design intent. Phase 2 seeded the persistence for several of them (analyses, satellite scenes, weather observations, chat sessions/messages, reports tables exist in the schema). API versioning practice is now fixed at `/api/v1`.

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