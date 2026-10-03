"""Phase 6E unit tests: timeline ordering, gaps, trend basis, event classification.

The historical service's pure helpers are deterministic math over scene
summaries and change-classification payloads, so they are tested directly
(no database or rasters involved).
"""

from __future__ import annotations

from datetime import date

from app.services.historical_service import (
    classify_vegetation_event,
    classify_water_event,
    order_observations,
    temporal_gaps,
    trend_basis,
)

# ---------------------------------------------------------------------------
# Timeline ordering
# ---------------------------------------------------------------------------


def test_order_observations_dedupes_and_sorts_oldest_first():
    scenes = [
        {"id": 3, "acquisition_date": date(2024, 7, 20)},
        {"id": 1, "acquisition_date": date(2024, 7, 5)},
        {"id": 2, "acquisition_date": date(2024, 7, 12)},
        {"id": 1, "acquisition_date": date(2024, 7, 5)},
    ]
    ordered = order_observations(scenes)
    assert [scene["id"] for scene in ordered] == [1, 2, 3]


def test_order_observations_breaks_acquisition_ties_by_id():
    scenes = [
        {"id": 10, "acquisition_date": date(2024, 7, 5)},
        {"id": 2, "acquisition_date": date(2024, 7, 5)},
    ]
    ordered = order_observations(scenes)
    assert [scene["id"] for scene in ordered] == [2, 10]
    # Deterministic even though the ordering logic must never rely on it alone.
    assert isinstance(ordered[0]["id"], int)


# ---------------------------------------------------------------------------
# Temporal gaps
# ---------------------------------------------------------------------------


def test_temporal_gaps_reports_only_irregular_spans():
    dates = [date(2024, 7, 5), date(2024, 7, 6), date(2024, 7, 20)]
    gaps, same_day_pairs = temporal_gaps(dates)
    assert same_day_pairs == 0
    assert gaps == [{"from_date": date(2024, 7, 6), "to_date": date(2024, 7, 20), "gap_days": 14}]


def test_temporal_gaps_never_treats_same_day_as_a_gap():
    dates = [date(2024, 7, 5), date(2024, 7, 5), date(2024, 7, 20)]
    gaps, same_day_pairs = temporal_gaps(dates)
    assert same_day_pairs == 1
    assert gaps == [{"from_date": date(2024, 7, 5), "to_date": date(2024, 7, 20), "gap_days": 15}]


def test_temporal_gaps_no_gaps_for_consecutive_days():
    gaps, same_day_pairs = temporal_gaps([date(2024, 7, 5), date(2024, 7, 6), date(2024, 7, 7)])
    assert gaps == []
    assert same_day_pairs == 0


# ---------------------------------------------------------------------------
# Trend basis (descriptive, capped to evidence)
# ---------------------------------------------------------------------------


def test_trend_basis_covers_the_evidence():
    assert trend_basis(0, False) == "No completed observations are available for this history type."
    assert trend_basis(1, False) == "Single observation; no change computed."
    assert trend_basis(2, False) == "Observed change between two observations."
    assert trend_basis(3, False) == "Trend across 3 observations."


def test_trend_basis_single_date_never_claims_change():
    assert (
        trend_basis(2, True)
        == "All observations share a single acquisition date; no temporal change computed."
    )
    assert (
        trend_basis(4, True)
        == "All observations share a single acquisition date; no temporal change computed."
    )


# ---------------------------------------------------------------------------
# Event classification (deterministic, measurable)
# ---------------------------------------------------------------------------


def _vegetation_classification(increase: int, decrease: int) -> dict:
    return {
        "classes": {
            "increase": {"pixel_count": increase},
            "decrease": {"pixel_count": decrease},
        }
    }


def _water_classification(new: int, lost: int) -> dict:
    return {"classes": {"new": {"pixel_count": new}, "lost": {"pixel_count": lost}}}


def test_vegetation_event_dominant_decrease():
    event, label, basis = classify_vegetation_event(_vegetation_classification(300, 700))
    assert event == "vegetation_decrease"
    assert "decreased" in label
    assert basis.startswith("Dominant class")


def test_vegetation_event_dominant_increase():
    event, label, _ = classify_vegetation_event(_vegetation_classification(900, 100))
    assert event == "vegetation_increase"
    assert "increased" in label


def test_vegetation_event_tie_is_stable():
    event, label, _ = classify_vegetation_event(_vegetation_classification(500, 500))
    assert event == "vegetation_stable"
    assert "No dominant" in label


def test_water_event_expansion():
    event, label, basis = classify_water_event(_water_classification(800, 0))
    assert event == "water_expansion"
    assert "increased" in label
    assert "NDWI >= threshold" in basis


def test_water_event_reduction():
    event, label, _ = classify_water_event(_water_classification(0, 800))
    assert event == "water_reduction"
    assert "decreased" in label


def test_water_event_tie_is_stable():
    event, label, _ = classify_water_event(_water_classification(400, 400))
    assert event == "water_stable"
    assert "net water-extent change" in label
