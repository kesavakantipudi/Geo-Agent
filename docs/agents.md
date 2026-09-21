# GeoAgent — Planned Agents

> **Status: PLANNED.** Agent implementations begin in Q2/Q3. This documents design intent and responsibilities.

Reference: [`PRD.md`](../PRD.md) §9–§13, §31; [`docs/PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) §9.

## 1. Agent team

| Agent | Primary question it answers | Responsibility |
| --- | --- | --- |
| **GeoAgent** | "What is happening here and what should I investigate?" | Orchestration, coordination, synthesis, conversation, recommendations. |
| **Agri Agent** | "What does this mean for vegetation and agriculture?" | Vegetation and crop analysis. |
| **Aqua Agent** | "What changed in and around the water?" | Water-body detection and water analysis. |
| **Weather Agent** | "What environmental conditions are relevant?" | Weather and environmental context. |
| **Change Agent** | "What changed, where, and when?" | Temporal change analysis. |

## 2. GeoAgent (orchestrator)

Responsibilities:

- Understand user requests, selected boundaries, and selected analysis types.
- Coordinate specialized agents and manage agent communication.
- Combine structured outputs into an evidence-grounded response.
- Answer natural-language questions bound to the selected location, time range, active agents, and retrieved data.
- Recommend additional investigations (**the user stays in control** of activating them).
- Maintain analysis context and generate final summaries/reports.

GeoAgent does not perform every specialized computation itself; it delegates to specialists.

## 3. Agri Agent

Capabilities (where data permits):

- Agricultural land detection, vegetation analysis (NDVI), crop identification.
- Crop health/stress estimation, drought indicators, irrigation indicators, bare-soil detection.
- Crop-area estimation, vegetation change, historical agricultural analysis.
- Disease-related and yield analysis only where imagery/data sufficiently supports it.

Suggestions must be evidence-based, clearly separating observations from possible explanations.

## 4. Aqua Agent

Capabilities (where data supports):

- Water-body detection (lakes, ponds, reservoirs, rivers/water regions).
- Water-spread estimation and seasonal variation.
- Historical water-spread comparison, shrinkage/expansion detection, flooded-area detection, encroachment indicators.
- Water-quality indicators only where suitable remote-sensing data exists.

Example output shape:

```text
2023 → 15.2 km² | 2024 → 13.8 km² | 2025 → 11.4 km² | 2026 → 9.7 km²
```

The system visualizes the change and lets the user investigate it conversationally.

## 5. Weather Agent

- Current conditions, historical weather, forecasts (configurable duration), weather alerts.
- Environmental indicators: temperature, humidity, rainfall, wind, pressure, cloud cover, UV.
- Provides context for cross-agent correlation (e.g., low rainfall + high temperature + declining vegetation = potential stress) — presented as correlation, not proven causation.

## 6. Change Agent

- Compares observations over time: imagery, vegetation, agriculture, water bodies, land-use indicators, and weather/environmental conditions.
- Supports timeline selection: specific dates, weeks, months, years, custom ranges.
- Uses ML/CV methods where appropriate (differencing, spectral change, segmentation comparison, feature comparison, classification, deep models where feasible) rather than percentage thresholds alone.
- Classifies significance with **configurable thresholds**: no significant change / minor / moderate / significant.

## 7. Cross-agent reasoning

Example interaction:

```text
Agri Agent   → vegetation decline
Weather Agent → rainfall decline
Change Agent → decline began in June
GeoAgent → "Vegetation indicators declined after the identified period.
           Rainfall was also lower during the same period. This temporal
           association may be relevant, but the data alone does not
           establish the cause."
```

Answers always distinguish measured observations, model outputs, and AI interpretation.

## 8. Structured output (planned shape)

```json
{
  "agent": "AgriAgent",
  "location": "AOI / geometry reference",
  "time_range": ["date_1", "date_2"],
  "finding": "Observed change in vegetation condition",
  "measurements": { "index_before": "", "index_after": "", "change": "" },
  "evidence": ["imagery", "index", "segmentation"],
  "confidence": 0.0,
  "limitations": []
}
```

Schemas will be validated with Pydantic models before evidence fusion.