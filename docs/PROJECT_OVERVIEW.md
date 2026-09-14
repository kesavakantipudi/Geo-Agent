# GeoAgent
## Autonomous Multimodal Satellite Intelligence System

> Final-Year AI/ML Project  
> Version 1.0 | September 2026

---

# Project Specification and Team Reference

## Executive Summary

GeoAgent is an autonomous multimodal satellite intelligence system for temporal geospatial reasoning. It goes beyond conventional satellite image change detection and image captioning by identifying what changed, where it changed, why it may matter, and which domain-specific factors support the interpretation. The system combines satellite observations, environmental context, specialist agents, and evidence-grounded reasoning to produce map-aware recommendations.

The main analytical pipeline is coordinated by a Change Agent, supported by Agri, Aqua, and Weather Agents. These agents operate as a team around a shared geospatial evidence base and work together through an inference and recommendation layer that prioritizes explainability, confidence, and responsible decision support.

---

## 1. Project Identity

| Attribute | Description |
| --- | --- |
| Project Name | GeoAgent |
| Project Type | Final-year AI/ML research and application project |
| Main Domain | Remote sensing, satellite imagery, geospatial AI, multimodal AI, and multi-agent systems |
| Core Problem | Understanding meaningful changes observed in satellite imagery |
| Primary Inputs | Multitemporal satellite imagery, AOI, date range, and optional contextual data |
| Primary Output | Evidence-backed change analysis, explanations, domain insights, and recommendations |
| Core Agents | Change Agent, Agri Agent, Aqua Agent, Weather Agent |
| Design Principle | Detect → Understand → Validate → Explain → Recommend |

---

## 2. Motivation and Background

The growing availability of multitemporal satellite imagery enables continuous Earth observation. Satellite data can reveal changes across agriculture, vegetation, water bodies, urban growth, settlements, roads, and other land-use patterns without repeated physical inspection.

However, most existing remote-sensing pipelines focus on one narrow task: classification, segmentation, change detection, or captioning. These systems can perform well in isolation, but they rarely provide a complete reasoning chain for a user who needs to know what changed, why it changed, what evidence supports the finding, and what should be done next.

GeoAgent addresses this gap by modeling geospatial intelligence as a coordinated multi-agent system that fuses specialized environmental and domain evidence.

---

## 3. Problem Statement

Conventional satellite change-detection systems mostly detect differences between images acquired at different times. Change-captioning systems extend this by providing natural language descriptions. However, a practical geospatial intelligence system needs more than a detected change or caption. It needs contextual validation, temporal reasoning, uncertainty awareness, domain interpretation, and recommendations.

The project therefore aims to design a multimodal, multi-agent satellite intelligence framework that can analyze temporal geospatial data, identify meaningful land-surface changes, coordinate specialized agricultural, aquatic, and weather analyses, explain the observed situation in natural language, and generate location-aware recommendations supported by evidence.

---

## 4. Existing Systems and Gaps

| Approach | Strength | Limitation |
| --- | --- | --- |
| Pixel-level change detection | Finds changed pixels or regions | Rarely explains the broader context or recommends action |
| Image classification | Assigns labels to images or areas | Does not model temporal change directly |
| Semantic segmentation | Provides masks for regions | Needs an additional reasoning layer |
| Change captioning | Describes changes in language | Usually limited to visual changes |
| Single-purpose model | High performance for one domain | Ignores cross-domain evidence |
| Generic multimodal LLM | Strong reasoning ability | May hallucinate or produce unsupported geospatial claims |

### Key Gap

The major project gap is the transition from a simple question such as “What changed?” to a richer intelligence workflow:

- What changed?
- Where did it change?
- Why might the change matter?
- What evidence supports the interpretation?
- What should be done next?

---

## 5. Proposed System: GeoAgent

GeoAgent is designed as a modular multi-agent system. A central orchestrator receives a user request and determines which analyses are required. The system can retrieve or accept satellite imagery, perform preprocessing and geospatial alignment, run change analysis, and invoke specialist agents when their domain expertise is relevant.

The Change Agent provides the main analytical signal. The Agri Agent analyzes crop and vegetation conditions, the Aqua Agent validates water-related patterns, and the Weather Agent supplies environmental context. A recommendation layer combines these findings into evidence-grounded suggestions and monitoring actions.

The architecture is intentionally modular. Agents can be developed and evaluated independently, then connected through a shared evidence and communication format.

---

## 6. Objectives

The objective of GeoAgent is to:

- Detect meaningful changes across multitemporal satellite imagery.
- Localize changes to specific geographic regions or objects.
- Classify or describe the nature of detected changes.
- Generate natural-language explanations grounded in observed evidence.
- Use Agri, Aqua, and Weather agents for domain-specific analysis.
- Combine multiple sources of evidence to improve spatial and temporal understanding.
- Produce practical, location-specific recommendations.
- Represent uncertainty openly where evidence is incomplete.
- Create a modular architecture that can support future domain agents.

---

## 7. System Features

| Feature | Description |
| --- | --- |
| Temporal Change Detection | Compare imagery from different dates and identify significant changes. |
| Change Localization | Produce a mask, region, or bounding area showing where a change occurred. |
| Change Classification | Categorize the observed transformation. |
| Change Captioning | Convert geospatial evidence into a descriptive natural-language summary. |
| Temporal Tracking | Compare multi-date trends to identify persistence or progression. |
| Agri Agent | Analyze agricultural and vegetation evidence. |
| Aqua Agent | Analyze water-body expansion, shrinkage, and related context. |
| Weather Agent | Supply environmental evidence for explanation and validation. |
| Evidence Fusion | Integrate agent outputs and identify agreement or conflict. |
| Recommendation Layer | Generate site-specific suggestions and monitoring actions. |
| User-Friendly Reporting | Present results through a dashboard or reporting UI. |

---

## 8. Multi-Agent Architecture

The GeoAgent architecture follows a coordinator-and-specialists model. The orchestrator identifies the appropriate agents, passes them the relevant evidence, receives structured findings, checks consistency, and produces the final response.

| Layer | Component | Responsibility |
| --- | --- | --- |
| 1 | User Interface | Accept AOI, dates, imagery, and analysis requests. |
| 2 | Orchestrator | Understand the request and manage the workflow. |
| 3 | Geo/Data Layer | Ingest, preprocess, align, tile, and index data. |
| 4 | Change Agent | Detect and describe temporal surface changes. |
| 4 | Agri Agent | Analyze vegetation and agriculture evidence. |
| 4 | Aqua Agent | Analyze water and aquatic surface changes. |
| 4 | Weather Agent | Provide environmental context. |
| 5 | Evidence Fusion | Combine specialist findings and confidence signals. |
| 6 | Recommendation Layer | Convert validated evidence into recommendations. |
| 7 | Report/UI | Present visual outputs and explanations clearly. |

---

## 9. Agent Responsibilities

### Change Agent

The Change Agent is the main component of GeoAgent. It compares observations across time and identifies meaningful changes. It produces masks, change categories, confidence estimates, and temporal summaries. It may also recommend monitoring or intervention actions when supported by strong evidence.

### Agri Agent

The Agri Agent analyzes vegetation and field-level patterns. It uses spectral indices such as NDVI where appropriate and flags possible stress, crop growth, harvesting, or land-use transition patterns. It should avoid over-claiming specific crop disease or causal mechanisms without enough evidence.

### Aqua Agent

The Aqua Agent specializes in water-body detection and water-area change validation. It helps examine expansion, shrinkage, and land-water transition evidence while maintaining traceable confidence and avoiding unsupported water-quality claims.

### Weather Agent

The Weather Agent adds environmental context such as rainfall, temperature, humidity, and wind conditions. It supports interpretation but should not be treated as proof of causality.

### Recommendation Layer

The recommendation layer converts validated findings into practical and location-aware suggestions. It should identify the affected region, summarize the evidence, and deliver targeted suggestions with appropriate confidence and uncertainty statements.

---

## 10. End-to-End Workflow

1. User selects an AOI and defines a date range or observation period.
2. GeoAgent retrieves relevant imagery and contextual data.
3. The geospatial pipeline performs quality checks, preprocessing, normalization, and alignment.
4. The orchestrator determines the required agents.
5. The Change Agent performs change detection and localization.
6. The Agri Agent checks vegetation and agricultural evidence if relevant.
7. The Aqua Agent validates water-body patterns if relevant.
8. The Weather Agent adds environmental context.
9. Evidence fusion compares agent outputs and resolves disagreement.
10. The reasoning layer constructs an evidence-grounded explanation.
11. The recommendation layer creates actionable suggestions.
12. The final report is shown through the UI.

---

## 11. System Architecture

| Module | Responsibility |
| --- | --- |
| Frontend | Map UI, AOI selection, image viewer, report, and dashboard |
| API / Backend | Request handling, job management, orchestration, and result delivery |
| Orchestrator | Request planning, agent control, retries, and workflow state |
| Geospatial Pipeline | Data retrieval, preprocessing, CRS handling, masks, indices, and derived features |
| Model Service | Change detection, classification, segmentation, and captioning inference |
| Agent Services | Agri, Aqua, and Weather specialist services |
| Evidence Store | Visuals, masks, indices, metadata, and agent observations |
| Database | Analysis records, artifacts, results, and recommendations |
| Monitoring and Logging | Execution status, errors, latency, and reproducibility |

Conceptual flow:

User → UI/API → Orchestrator → Data Pipeline → Change Agent + Specialist Agents → Evidence Fusion → Recommendation Layer → Report/Dashboard

---

## 12. Inputs and Outputs

### Inputs

- Area of interest as a point, polygon, bounding box, or administrative boundary.
- Observation date or date range.
- Satellite imagery or an imagery-provider interface.
- Optional user questions and domain selection.
- Optional environmental or contextual data.

### Outputs

| Output | Example |
| --- | --- |
| Change map | Mask showing the detected regional transformation |
| Change summary | Natural-language interpretation of the change |
| Temporal comparison | Before/after or multi-date trend |
| Domain analysis | Status of agricultural, water, or weather evidence |
| Evidence | Index values, masks, imagery metadata, and agent observations |
| Confidence | High, medium, low, or calibrated score |
| Recommendation | Location-aware action, monitoring, or intervention suggestion |
| Report | Visual and textual analysis summary |

---

## 13. Data and Datasets

The dataset strategy should be task-specific and evidence-driven. Recommended sources include:

| Category | Example Sources |
| --- | --- |
| Optical multispectral imagery | Sentinel-2, Landsat |
| Radar imagery | Sentinel-1 |
| Change detection datasets | LEVIR-CD and related remote-sensing datasets |
| Change-captioning datasets | Research datasets selected during the literature review |
| Weather data | Public meteorological APIs and datasets |
| Boundary datasets | OpenStreetMap and authoritative geospatial boundaries |

The dataset plan should support the intended task, temporal structure, and evaluation methodology.

---

## 14. AI/ML Models and Algorithms

A model-agnostic approach is recommended. The final technical design should be selected after benchmarking accuracy, compute requirements, data availability, and licensing constraints.

| Task | Candidate Methods |
| --- | --- |
| Preprocessing | Cloud masking, normalization, resampling, and tiling |
| Change Detection | CNNs, U-Net variants, transformers, and Siamese networks |
| Segmentation | U-Net, SegFormer, DeepLab, and related models |
| Classification | CNN, ViT, or remote-sensing foundation models |
| Captioning | Vision-language model or change-captioning model |
| Geospatial Indexing | NDVI, NDWI, and related indicators |
| Reasoning | Structured LLM agent interface |
| Recommendation | Rule-based and model-supported evidence reasoning |

---

## 15. Technology Stack

| Layer | Recommended Technology |
| --- | --- |
| Language | Python |
| Deep Learning | PyTorch |
| Computer Vision | OpenCV, rasterio, GDAL, NumPy |
| Geospatial | GeoPandas, Shapely, pyproj |
| Data | Pandas, xarray |
| Backend | FastAPI |
| Frontend | React / Next.js or lightweight Python UI |
| Maps | Leaflet, MapLibre, or Mapbox-compatible tooling |
| Database | PostgreSQL + PostGIS |
| Experiment Tracking | MLflow |
| Containers | Docker |
| Version Control | Git and GitHub |

---

## 16. APIs and External Data Sources

GeoAgent may integrate external APIs for satellite imagery, weather, geocoding, map tiles, and cloud storage. Service adapters should isolate these dependencies so that agents remain modular and swappable.

---

## 17. Backend, Database, and Frontend

### Backend

- Accept AOI, dates, and analysis preferences.
- Create asynchronous analysis jobs.
- Track job lifecycle from queue to completion.
- Return structured JSON and artifact references.
- Store metadata and provenance.

### Database

| Entity | Example Fields |
| --- | --- |
| Analysis | analysis_id, AOI, dates, created_at, status, model_version |
| Observation | satellite, acquisition_time, resolution, quality metadata |
| Change | geometry, class, magnitude, confidence |
| AgentResult | agent_id, findings, evidence, confidence |
| Recommendation | location, rationale, priority, confidence |
| Artifact | storage URI, type, checksum, metadata |

### Frontend

- AOI selection map
- Before/after imagery viewer
- Change mask overlay
- Date timeline control
- Agent findings panel
- Confidence and evidence panel
- Recommendations panel
- Exportable report

---

## 18. Training and Inference Strategy

A staged delivery strategy is recommended:

1. Data ingestion and preprocessing
2. Baseline change detection
3. Localization, classification, and change captioning
4. Agri Agent
5. Aqua Agent
6. Weather Agent
7. Evidence fusion
8. Recommendations and UI integration
9. Evaluation and ablation study

The implementation should be designed for a practical local prototype while allowing heavier compute to shift to cloud or GPU services where needed.

---

## 19. Evaluation Plan

| Component | Evaluation Metrics |
| --- | --- |
| Change detection | Precision, recall, F1, IoU, Dice |
| Segmentation | IoU, Dice, boundary accuracy |
| Classification | Accuracy, macro-F1, confusion matrix |
| Captioning | BLEU, ROUGE, METEOR, factuality, relevance |
| Agent validation | Agreement with labels and expert review |
| Recommendation quality | Relevance, specificity, evidence support, and confidence |
| System | Latency, success rate, resource usage, and reproducibility |

A critical experiment compares three configurations:

A. Change detection only  
B. Change detection + language explanation  
C. GeoAgent with specialized agents, evidence fusion, and recommendations

---

## 20. Example Use Cases

| Scenario | GeoAgent Behavior |
| --- | --- |
| Agricultural field | Detect vegetation change, inspect crop signal, and combine weather evidence. |
| Water body | Detect water-area expansion or shrinkage and validate with Aqua evidence. |
| Urban expansion | Map built-up growth across multiple dates. |
| Flood-like event | Pair water-surface evidence with rainfall and weather context. |
| Long-term land transformation | Summarize land-use progression over time. |

---

## 21. Recommendation Engine

Recommendations should be tied directly to the detected region and validated agent evidence. The suggested recommendation process is:

1. Detect the changed region.
2. Contextualize the event.
3. Validate through specialist agents.
4. Prioritize by urgency and confidence.
5. Suggest an evidence-based action or monitoring step.
6. Qualify the recommendation with uncertainty and missing-data warnings.

---

## 22. Novelty and Research Contribution

GeoAgent’s research contribution is not simply a new change-detection model. The broader contribution is a modular architecture for autonomous geospatial reasoning where specialized agents cooperate around a shared satellite-analysis task.

The system introduces:

- Multi-agent decomposition of geospatial intelligence.
- Temporal change reasoning with contextual specialists.
- Cross-domain evidence fusion.
- Location-aware recommendation generation.
- Separation between measurable geospatial analysis and language-based explanation.

---

## 23. Implementation Roadmap

| Phase | Work |
| --- | --- |
| Phase 1 | Requirements, literature review, architecture |
| Phase 2 | Data pipeline and preprocessing |
| Phase 3 | Baseline change detection |
| Phase 4 | Change interpretation and captioning |
| Phase 5 | Agri Agent |
| Phase 6 | Aqua Agent |
| Phase 7 | Weather Agent |
| Phase 8 | Evidence fusion |
| Phase 9 | Recommendation engine |
| Phase 10 | UI and backend integration |
| Phase 11 | Evaluation and ablation |
| Phase 12 | Documentation and demo |

---

## 24. Team Roles

| Role | Responsibility |
| --- | --- |
| Project / Architecture Lead | System design, orchestration, integration, and delivery |
| Remote Sensing / ML Lead | Datasets, preprocessing, change detection, segmentation, and evaluation |
| Agri Agent Lead | Agriculture and vegetation analytics |
| Aqua Agent Lead | Water-body detection and validation |
| Weather / Context Lead | Weather integration and environmental context |
| Backend / Agent Integration | APIs, job management, agent interfaces, database, and evidence storage |
| Frontend / Visualization | Map UI, overlays, timelines, reports, and UX |
| Research / Documentation | Literature review, experiments, report, and paper preparation |

---

## 25. Development Milestones

| Milestone | Description |
| --- | --- |
| M1 | Project specification frozen |
| M2 | Literature review and datasets selected |
| M3 | Satellite ingestion and preprocessing working |
| M4 | Baseline change detector working |
| M5 | Change visualization and captioning working |
| M6 | Agri Agent working |
| M7 | Aqua Agent working |
| M8 | Weather Agent working |
| M9 | Agent communication schema stable |
| M10 | Recommendation engine integrated |
| M11 | End-to-end dashboard or demo working |
| M12 | Evaluation, ablation, and error analysis completed |
| M13 | Final report, paper, presentation, and demo finalized |

---

## 26. Risks and Technical Challenges

| Challenge | Why It Matters | Mitigation |
| --- | --- | --- |
| Cloud or image quality | Affects reliable observation | Cloud masking and sensor fallback |
| Temporal misalignment | Creates false or inconsistent change detection | Co-registration and consistent metadata |
| False change | Seasonal shift or illumination can look like change | Multi-date confirmation and validation |
| Limited training data | Weakens model generalization | Transfer learning and weak supervision |
| LLM hallucination | Produces unsupported explanations | Evidence grounding and structured output |
| Agent disagreement | Creates inconsistent evidence | Evidence fusion and confidence calibration |
| Compute limitations | Constrain model deployment | Tiling, APIs, and cloud inference |
| API dependency | External changes may interrupt workflow | Service adapters and fallbacks |
| Scope creep | Reduces delivery focus | Prioritize core agents first |

---

## 27. Expected Results

- Working multitemporal satellite processing prototype
- Baseline change-detection metrics
- Multi-agent evidence workflow
- Visual maps and change summaries
- Recommendation layer with uncertainty handling
- Interactive dashboard or demo interface
- Documented comparison between base and multi-agent models

---

## 28. Limitations and Future Scope

### Limitations

- Spatial resolution may limit small-scale change detection.
- Cloud cover and acquisition gaps can affect comparison.
- Weather evidence supports interpretation but does not prove causality.
- On-ground diagnosis may require field data or sensors.
- Recommendations should not replace expert judgment.

### Future Scope

- Disaster Agent
- Urban Agent
- Forest Agent
- Infrastructure Agent
- Carbon / Climate Agent
- Edge deployment
- Continuous monitoring and alerts
- Human-in-the-loop feedback and knowledge graph integration

---

## 29. Deliverables

| Deliverable | Description |
| --- | --- |
| Source code | Backend, agents, model logic, frontend, configuration |
| Dataset pipeline | Access instructions, preprocessing, and splits |
| Trained models | Weights, checkpoints, or reproducible training instructions |
| Application | Working end-to-end GeoAgent prototype |
| Evaluation report | Metrics, baselines, ablations, and error analysis |
| Project report | Literature, methodology, results, and recommendations |
| Research paper | Architecture contribution and experimental findings |
| Demo | Architecture, novelty, results, and demonstration package |

---

## 30. Demo and Presentation Strategy

A strong demo should combine visual and reasoning evidence into a complete story:

1. Select a geographic AOI with a known temporal change.
2. Show the earlier observation.
3. Show the later observation.
4. Display the change mask or region.
5. Ask GeoAgent to explain the change.
6. Trigger the relevant specialist agent or agents.
7. Display weather or contextual information.
8. Show the evidence-fused interpretation.
9. Present the recommendation generated from the evidence.
10. Reveal the traceable evidence panel for evaluation.

The key message is:

> GeoAgent does not stop at detecting change. It coordinates specialist geospatial agents to understand, validate, explain, and recommend action based on the same evidence.

---

## 31. Research Direction

A central research question is:

> Does a specialized multi-agent architecture improve contextual interpretation and decision-support quality when compared with conventional change detection and image captioning systems?

The paper can organize findings around methodology, experiments, baselines, ablations, error analysis, and the contribution of multi-agent evidence fusion.

---

## 32. One-Page Team Quick Reference

GeoAgent is an autonomous multimodal satellite intelligence system that detects and understands temporal land-surface changes, validates them using Agri, Aqua, and Weather agents, and produces evidence-grounded, location-specific recommendations.

### Core pipeline

Satellite Data → Preprocessing → Change Agent → Specialist Agents → Evidence Fusion → Reasoning → Recommendation → Visual Report

### Core agents

| Agent | Question It Answers |
| --- | --- |
| Change Agent | What changed, where, and over what period? |
| Agri Agent | What does the change imply for vegetation or agriculture? |
| Aqua Agent | What changed in or around water bodies? |
| Weather Agent | What environmental conditions explain the observation? |
| Recommendation Layer | What action or monitoring decision is supported by the evidence? |

### Minimum viable project

- Multitemporal satellite input
- Baseline change detection and localization
- Change explanation
- Agri, Aqua, and Weather capabilities
- Evidence fusion
- Location-specific recommendation
- Map-based demonstration

### Success criteria

- Strong change-detection metrics
- Useful and defensible specialty-agent outputs
- More informative output than simple before/after captioning
- Evidence-traceable recommendations with uncertainty
- Reproducible and demonstrable demonstration workflow

---

## Appendix A — Suggested Structured Agent Output

```json
{
  "agent": "AgriAgent",
  "location": "AOI / geometry reference",
  "time_range": ["date_1", "date_2"],
  "finding": "Observed change in vegetation condition",
  "measurements": {
    "index_before": "...",
    "index_after": "...",
    "change": "..."
  },
  "evidence": ["imagery", "index", "segmentation"],
  "confidence": 0.0,
  "limitations": ["..."]
}
```

This schema can be represented using Pydantic models or JSON Schema for validation before evidence fusion.

---

## Appendix B — Engineering Principles

- Modularity
- Observability
- Reproducibility
- Grounding
- Uncertainty handling
- Extensibility
- Separation of concerns
- Evaluation-first development

---

## Appendix C — Recommended Priority Order

For the final-year implementation, the priority should be:

1. Change Agent
2. Agri Agent
3. Aqua Agent
4. Weather Agent
5. Evidence fusion
6. Recommendation layer
7. Polished UI

Additional agents should remain future scope until the core pipeline is stable.
