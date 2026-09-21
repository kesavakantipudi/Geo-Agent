# GeoAgent — Project Scope

> **Status: PLANNED (scope summary).** Consolidates what GeoAgent aims to build, what is explicitly out of scope for the initial version, and the scope-management rules the team follows.

Reference: [`PRD.md`](../PRD.md) — the authoritative scope.

## 1. Vision

GeoAgent is an interactive multi-agent geospatial intelligence platform. Users select a location and geographic area, choose analysis modules, retrieve satellite and environmental data, investigate historical changes, and interact with specialized agents through natural-language conversations.

**Target completion: January 2027.** Initial geographic focus: **India**, extensible to global coverage.

## 2. In scope (planned)

- Location selection and AOI definition (search, coordinates, map click, polygon, rectangle, GeoJSON/KML upload).
- Explicit analysis-module selection: Agriculture, Water, Weather, Change Detection.
- Satellite data retrieval (Copernicus Sentinel-2, Sentinel-1, Landsat; Microsoft Planetary Computer candidate) with provider fallback.
- Specialized agents: Agri, Aqua, Weather, Change, coordinated by GeoAgent.
- Historical change detection with configurable timelines and thresholds.
- Interactive map with layers, overlays, and timeline controls.
- Conversational interface grounded in the selected location and analysis context.
- Analysis history, data-attribute tracing, and PDF reports.
- Authentication (Google / standard) and role-based permissions.
- Grounded recommendations and uncertainty-aware explanations.

## 3. Out of scope for the initial version

The following are out of scope for the initial MVP (from `PRD.md` §35):

- Mobile application.
- Payment gateway / billing.
- Real-time satellite streaming.
- IoT and drone integration.
- Social features.
- Excessively complex enterprise functionality.

Also explicitly *deferred to later phases* for **Phase 1** (this phase): application code, database models/migrations, PostGIS functionality, geocoding, satellite/weather API integration, agents, LLM orchestration, ML models, dashboards, 3D visuals, PDF reports, and production deployment.

## 4. Scope management rules

- The MVP scope in `PRD.md` is considered frozen once implementation starts.
- New feature ideas go to a separate backlog rather than changing the MVP architecture mid-flight.
- Data first → analysis second → agents third → orchestration fourth → UI enhancement fifth.
- Planned vs. implemented is always labeled honestly in docs and UI.
- No fabricated data may be presented as real analysis in the final system.

## 5. Team roles

| Role | Focus |
| --- | --- |
| Member 1 | GeoAgent orchestration, LLM, system integration |
| Member 2 | Agri Agent |
| Member 3 | Aqua Agent |
| Member 4 | Weather Agent |

All members contribute to testing, documentation, integration, and the final presentation.