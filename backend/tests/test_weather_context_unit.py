"""Phase 6C unit tests (no database): weather-context alignment rules.

Covers the pure deterministic layer in ``app.services.weather.context``:
UTC alignment windows, per-variable aggregation (mean/sum/min/max/none),
the units-mismatch guard, and completeness accounting. Missing data must stay
``None`` (never fabricated as ``0``); a context must never invent observations.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.services.weather import context as ctx

UTC = UTC
DAY = date(2024, 7, 15)


def _row(variable, value, observed_at, units="°C", units_doc="Temperature", **extra):
    row = {
        "variable": variable,
        "value": value,
        "units": units,
        "units_doc": units_doc,
        "observed_at": observed_at,
        "provider": "openmeteo",
        "model": "gfs_seamless",
        "data_type": "historical_forecast",
    }
    row.update(extra)
    return row


def _at(hour: int, day_offset: int = 0):
    return datetime(2024, 7, 15 + day_offset, hour, tzinfo=UTC)


# --- Temporal alignment -----------------------------------------------------


def test_alignment_window_default_plus_minus_one_utc_days():
    start, end = ctx.alignment_window(DAY, 1, 1)
    assert start == datetime(2024, 7, 14, tzinfo=UTC)
    assert end == datetime(2024, 7, 16, 23, 59, 59, 999999, tzinfo=UTC)


def test_alignment_window_same_day_only():
    start, end = ctx.alignment_window(DAY, 0, 0)
    assert start == datetime(2024, 7, 15, tzinfo=UTC)
    assert end == datetime(2024, 7, 15, 23, 59, 59, 999999, tzinfo=UTC)


def test_alignment_window_crosses_month_boundary():
    start, end = ctx.alignment_window(date(2024, 6, 1), 1, 1)
    assert start == datetime(2024, 5, 31, tzinfo=UTC)
    assert end == datetime(2024, 6, 2, 23, 59, 59, 999999, tzinfo=UTC)


def test_window_dates_echoes_actual_days_used():
    assert ctx.window_dates(DAY, 1, 2) == (date(2024, 7, 14), date(2024, 7, 17))


def test_alignment_window_timezone_deterministic():
    # Unaware/local rows are compared against explicit UTC bounds, so the window
    # never depends on the observation row's recorded timezone.
    _, end = ctx.alignment_window(DAY, 0, 0)
    assert end.tzinfo is UTC


# --- Aggregation ------------------------------------------------------------


def test_mean_aggregation_of_temperature():
    rows = [_row("temperature_2m", 15.5, _at(0)), _row("temperature_2m", 21.0, _at(6))]
    variables, warnings = ctx.aggregate_observations(rows, ["temperature_2m"], 2)
    assert warnings == []
    assert variables[0]["value"] == pytest.approx(18.25)
    assert variables[0]["units"] == "°C"
    assert variables[0]["aggregator"] == "mean"
    assert variables[0]["available"] is True
    assert variables[0]["sample_count"] == 2
    assert variables[0]["coverage_pct"] == 100.0


def test_max_and_min_aggregation():
    rows = [
        _row("temperature_2m_max", 24.0, _at(0)),
        _row("temperature_2m_max", 28.5, _at(6)),
        _row("temperature_2m_min", 9.0, _at(0)),
        _row("temperature_2m_min", 11.5, _at(6)),
    ]
    variables, _ = ctx.aggregate_observations(rows, ["temperature_2m_max", "temperature_2m_min"], 2)
    assert variables[0]["value"] == 28.5
    assert variables[0]["aggregator"] == "max"
    assert variables[1]["value"] == 9.0
    assert variables[1]["aggregator"] == "min"


def test_precipitation_is_summed_including_recorded_zeros():
    rows = [
        _row("precipitation", 0.0, _at(0), units="mm", units_doc="Precipitation"),
        _row("precipitation", 2.5, _at(1), units="mm", units_doc="Precipitation"),
        _row("precipitation", 1.1, _at(2), units="mm", units_doc="Precipitation"),
    ]
    variables, _ = ctx.aggregate_observations(rows, ["precipitation"], 3)
    assert variables[0]["value"] == pytest.approx(3.6)
    assert variables[0]["aggregator"] == "sum"


def test_summed_variables_are_explicitly_listed():
    for name in ("precipitation", "rain", "showers", "snowfall", "et0_fao_evapotranspiration"):
        assert ctx.AGGREGATORS[name] == "sum"
        assert name in ctx.SUMMED_VARIABLES


def test_weather_code_is_not_aggregated():
    rows = [
        _row("weather_code", 1.0, _at(0), units=None, units_doc=None),
        _row("weather_code", 3.0, _at(1), units=None, units_doc=None),
    ]
    variables, _ = ctx.aggregate_observations(rows, ["weather_code"], 2)
    assert variables[0]["available"] is False
    assert variables[0]["value"] is None
    assert "not aggregated" in variables[0]["note"]


def test_units_mismatch_disables_variable_aggregation():
    rows = [
        _row("temperature_2m", 15.0, _at(0), units="°C"),
        _row("temperature_2m", 60.0, _at(1), units="°F"),
    ]
    variables, _ = ctx.aggregate_observations(rows, ["temperature_2m"], 2)
    assert variables[0]["available"] is False
    assert variables[0]["value"] is None
    assert "units mismatch" in variables[0]["note"]


def test_variable_with_no_rows_stays_none_not_zero():
    rows = [_row("precipitation", 2.0, _at(0), units="mm", units_doc="Precipitation")]
    variables, _ = ctx.aggregate_observations(rows, ["precipitation", "rain"], 1)
    rain = variables[1]
    assert rain["value"] is None  # never fabricated as 0
    assert rain["available"] is True
    assert rain["coverage_pct"] == 0.0
    assert "no observations" in rain["note"]


def test_non_finite_values_are_skipped_not_aggregated():
    rows = [
        _row("temperature_2m", float("nan"), _at(0)),
        _row("temperature_2m", 20.0, _at(1)),
    ]
    variables, _ = ctx.aggregate_observations(rows, ["temperature_2m"], 1)
    assert variables[0]["value"] == pytest.approx(20.0)


def test_partial_window_sum_raises_honesty_warning():
    # Coverage 2 of 4 expected timestamps -> sum is explicitly partial.
    rows = [
        _row("precipitation", 1.0, _at(0), units="mm", units_doc="Precipitation"),
        _row("precipitation", 2.0, _at(1), units="mm", units_doc="Precipitation"),
    ]
    variables, warnings = ctx.aggregate_observations(rows, ["precipitation"], 4)
    assert variables[0]["coverage_pct"] == 50.0
    assert variables[0]["value"] == pytest.approx(3.0)
    assert any("partial-window sum" in w for w in warnings)


# --- Completeness -----------------------------------------------------------


def test_expected_timestamp_count_counts_distinct_timestamps():
    rows = [
        _row("temperature_2m", 1.0, _at(0)),
        _row("precipitation", 0.0, _at(0), units="mm", units_doc="Precipitation"),
        _row("precipitation", 2.0, _at(1), units="mm", units_doc="Precipitation"),
    ]
    assert ctx.expected_timestamp_count(rows) == 2


def test_coverage_is_scaled_to_widest_observed_axis():
    axis = [_at(h) for h in (0, 6, 12, 18)]
    rows = []
    for observed_at in axis:
        rows.append(_row("temperature_2m", 20.0, observed_at))
    # humidity only recorded for half the timestamps
    for observed_at in axis[:2]:
        rows.append(
            _row("relative_humidity_2m", 50.0, observed_at, units="%", units_doc="Humidity")
        )
    variables, _ = ctx.aggregate_observations(
        rows, ["temperature_2m", "relative_humidity_2m"], ctx.expected_timestamp_count(rows)
    )
    temp, humidity = variables
    assert temp["sample_count"] == temp["expected_count"] == 4
    assert temp["coverage_pct"] == 100.0
    assert humidity["sample_count"] == 2
    assert humidity["coverage_pct"] == 50.0
