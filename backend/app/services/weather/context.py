"""Weather-context layer (Phase 6C): satellite-observation alignment (pure).

This module holds the *deterministic* rules for turning already-stored weather
observations (retrieved and persisted by Phase 5) into a compact context for a
satellite observation. It never calls a provider and never invents data.

Rules (all deterministic and documented in ``docs/scientific-methodology.md``):

- **Temporal alignment**: a satellite observation with acquisition date ``D``
  draws a window of ``[D - days_before, D + days_after]`` over **inclusive UTC
  days** (start of the first day to end of the last day, in UTC). ``0`` on both
  sides means *same-day only*. The window actually used is always echoed.
- **Aggregation**: only variables that exist in the stored data are aggregated.
  Missing values are ``None`` (never fabricated as ``0``). Precipitation-family
  variables (``precipitation``/``rain``/``showers``/``snowfall``/``et0_...``)
  are *summed* over the window; ``temperature_2m_max``/``min`` use max/min;
  everything else uses the mean. ``weather_code`` and ``wind_direction_10m`` are
  categorical/vector variables and are **not aggregated** (no fake means).
- **Units guard**: values from the same variable are only aggregated if every
  stored row reports the same ``units``; otherwise the variable is reported
  ``available=false`` with an explicit ``units_mismatch`` note.
- **Completeness**: each variable's ``sample_count`` is its number of distinct
  stored timestamps inside the window; ``expected_count`` is the largest number
  of distinct timestamps seen for *any* context row in the window (all variables
  of a single provider fetch share the same time axis, so this is the natural
  "what a full set would look like" denominator without assuming hourly data).
  ``coverage_pct = sample_count / expected_count * 100``. No observation in the
  window → the caller reports an explicit ``no_weather_observations`` state.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

#: Variable → deterministic aggregator.
#: ``mean`` | ``sum`` | ``min`` | ``max`` | ``none`` (categorical/vector).
AGGREGATORS: dict[str, str] = {
    "temperature_2m": "mean",
    "apparent_temperature": "mean",
    "dewpoint_2m": "mean",
    "relative_humidity_2m": "mean",
    "cloud_cover": "mean",
    "pressure_msl": "mean",
    "surface_pressure": "mean",
    "soil_temperature_0cm": "mean",
    "soil_moisture_0to10cm": "mean",
    "wind_speed_10m": "mean",
    "wind_gusts_10m": "max",
    "temperature_2m_max": "max",
    "temperature_2m_min": "min",
    "precipitation": "sum",
    "rain": "sum",
    "showers": "sum",
    "snowfall": "sum",
    "et0_fao_evapotranspiration": "sum",
    "weather_code": "none",
    "wind_direction_10m": "none",
}

#: Summed variables: totals accumulate recorded values over the window.
SUMMED_VARIABLES: frozenset[str] = frozenset(
    name for name, agg in AGGREGATORS.items() if agg == "sum"
)

#: Variable names that are never aggregated (categorical / circular vector).
NON_AGGREGATABLE: frozenset[str] = frozenset(
    name for name, agg in AGGREGATORS.items() if agg == "none"
)


def window_dates(acquisition_date: date, days_before: int, days_after: int) -> tuple[date, date]:
    """Inclusive calendar-day window around an acquisition date."""
    return (
        acquisition_date - timedelta(days=days_before),
        acquisition_date + timedelta(days=days_after),
    )


def alignment_window(
    acquisition_date: date, days_before: int, days_after: int
) -> tuple[datetime, datetime]:
    """UTC-bounded inclusive window: 00:00 of start day → 23:59:59.999 of end day.

    Comparing stored ``timestamptz`` values against this window is deterministic
    regardless of the timezone each observation was recorded in.
    """
    start_day, end_day = window_dates(acquisition_date, days_before, days_after)
    start = datetime.combine(start_day, time.min, tzinfo=UTC)
    end = datetime.combine(end_day, time.max, tzinfo=UTC)
    return start, end


def _finite(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)


def expected_timestamp_count(rows: list[dict[str, Any]]) -> int:
    """Largest number of distinct timestamps across the context rows."""
    timestamps: set[Any] = set()
    for row in rows:
        observed_at = row.get("observed_at")
        if observed_at is not None:
            timestamps.add(
                observed_at.isoformat() if hasattr(observed_at, "isoformat") else str(observed_at)
            )
    return len(timestamps)


def aggregate_observations(
    rows: list[dict[str, Any]], variables: list[str], expected_count: int
) -> tuple[list[dict[str, Any]], list[str]]:
    """Aggregate stored observation rows per requested variable (deterministic).

    ``rows`` are normalized dicts with (at least) ``variable``, ``value``,
    ``units``, ``units_doc`` and ``observed_at``. Returns ``(variables, warnings)``.

    - Missing/stale values are ``None``, never ``0``.
    - A variable with no rows in the window keeps ``value=None`` and
      ``coverage_pct=0`` (explicit, not fabricated).
    - ``sum`` aggregators report a warning when their own coverage is below the
      expected count ("partial-window sum" honesty note).
    """
    warnings: list[str] = []
    results: list[dict[str, Any]] = []

    for name in variables:
        matched = [row for row in rows if row.get("variable") == name]
        units_set = {row.get("units") for row in matched if row.get("units") is not None}
        units = next(iter(units_set)) if len(units_set) == 1 else None
        units_doc = next((row.get("units_doc") for row in matched if row.get("units_doc")), None)
        sample_count = len({row.get("observed_at") for row in matched})
        observation_count = len(matched)
        coverage_pct = round(sample_count / expected_count * 100.0, 1) if expected_count else 0.0

        aggregator = AGGREGATORS.get(name, "mean")
        value: float | None = None
        available = True
        note: str | None = None

        if len(units_set) > 1:
            available = False
            note = (
                f"units mismatch across stored observations "
                f"({', '.join(sorted(str(u) for u in units_set))}); not aggregated"
            )
        elif aggregator == "none":
            available = False
            note = f"{name} is categorical/vector and is not aggregated"
        else:
            values = [float(row["value"]) for row in matched if _finite(row.get("value"))]
            if not values:
                available = True
                note = "no observations for this variable in the window"
            elif aggregator == "sum":
                value = sum(values)
                if coverage_pct < 100.0:
                    note = (
                        f"partial-window sum over {sample_count} of {expected_count} "
                        "recorded samples"
                    )
            elif aggregator == "min":
                value = min(values)
            elif aggregator == "max":
                value = max(values)
            else:
                value = sum(values) / len(values)

        result: dict[str, Any] = {
            "name": name,
            "aggregator": aggregator,
            "value": value,
            "units": units,
            "units_doc": units_doc,
            "observation_count": observation_count,
            "sample_count": sample_count,
            "expected_count": expected_count,
            "coverage_pct": coverage_pct,
            "available": available,
            "note": note,
        }
        results.append(result)
        if value is not None and aggregator == "sum" and note:
            warnings.append(note)

    return results, warnings


__all__ = [
    "AGGREGATORS",
    "NON_AGGREGATABLE",
    "SUMMED_VARIABLES",
    "aggregate_observations",
    "alignment_window",
    "expected_timestamp_count",
    "window_dates",
]
