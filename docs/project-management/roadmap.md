# GeoAgent — Roadmap (Q1–Q4)

> **Status: PLANNED.** This roadmap is subject to refinement based on implementation progress. Quarter boundaries are indicative; a 4-member team should re-plan after each quarter review. Target completion: **January 2027**.

## Q1 — Foundation

| Phase | Deliverable focus |
| --- | --- |
| **Phase 1 — Engineering Foundation** | Repository organization, docs, standards, env config, project-management readiness. *(Completed — see phase1-checklist.)* |
| **Phase 2 — Application Foundation** | Backend (FastAPI) and frontend (Next.js) skeletons, PostgreSQL/PostGIS setup, API structure, environment wiring. |
| **Phase 3 — Location Intelligence** | Location search/selection, AOI geometry, geocoding provider abstraction. *(Implemented — see phase3-checklist.)* |
| **Phase 4 — Satellite Intelligence Infrastructure** | Satellite data retrieval, provider abstraction, imagery handling, caching. |
| **Phase 5 — Weather and Environmental Infrastructure** | Weather provider abstraction, historical/forecast retrieval. |

## Q2 — Geospatial Intelligence

| Phase | Deliverable focus |
| --- | --- |
| **Phase 6 — Agri Agent** | Vegetation/agriculture analysis (NDVI, crop health, stress, historical comparison). |
| **Phase 7 — Aqua Agent** | Water-body detection, spread estimation, historical water analysis. |
| **Phase 8 — Weather Agent** | Weather/environmental intelligence and correlation support. |
| **Phase 9 — Change Detection Engine** | Temporal comparison, ML/CV change detection, localization, significance thresholds. |
| **Phase 10 — Historical Intelligence** | Historical date-range workflows, comparison capabilities, provenance of observations. |

## Q3 — Multi-Agent GeoAgent

| Phase | Deliverable focus |
| --- | --- |
| **Phase 11 — Agent Framework** | Shared agent interface, structured schemas, evidence format. |
| **Phase 12 — GeoAgent Orchestrator** | Workflow planning, agent coordination, result synthesis. |
| **Phase 13 — Conversational GeoAgent** | Natural-language interface grounded in location/analysis context. |
| **Phase 14 — Multi-Agent Reasoning** | Cross-agent correlation, evidence fusion, uncertainty handling. |
| **Phase 15 — Suggestions Engine** | Evidence- and location-aware recommendations with user control. |

## Q4 — Productization and Delivery

| Phase | Deliverable focus |
| --- | --- |
| **Phase 16 — Advanced Dashboard** | Interactive maps, layers, timelines, charts, agent chat UI. |
| **Phase 17 — 3D Experience** | Three.js-based 3D globe/transitions; after functional MVP. |
| **Phase 18 — Analysis History** | Persisted sessions, restoration of past analysis context. |
| **Phase 19 — Reporting** | Downloadable PDF reports with clear attribution. |
| **Phase 20 — Testing and Evaluation** | Unit, API, agent, ML evaluation; documented metrics. |
| **Phase 21 — Deployment** | Provider selection, hosting, environment configuration, monitoring. |
| **Phase 22 — Final Submission** | Final report, paper/presentation, demo package. |

## Guiding priority (from PRD §49 / Appendix C)

Data first → analysis second → agents third → orchestration fourth → UI enhancement fifth.

The MVP must demonstrate genuine data retrieval and genuine analysis; dashboards and visuals are polish, not the core deliverable. The final project must show the complete loop: real location → real data → real analysis → change detection → specialized agents → multi-agent reasoning → map → conversation → suggestions → report.