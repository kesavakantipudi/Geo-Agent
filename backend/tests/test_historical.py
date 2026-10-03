"""Phase 6E API tests: historical auth, access, ordering, coverage, events.

The satellite download mock serves opaque bytes, so the timeline tests seed real
synthetic GeoTIFF band files (see ``agri_mocks`` / ``aqua_mocks``) and completed
retrieval rows for the session's scenes before calling the analysis endpoint —
exactly the state real completed downloads would produce. Timeline assets are
coherent across B03/B04/B08 so a scene's vegetation (NDVI) and water (NDWI)
metrics share the same underlying scene.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from agri_mocks import (
    REF_NIR_VEGETATION,
    REF_VEGETATION,
    REF_WATER,
    clear_scl,
    seed_retrieval,
    write_band,
)
from aqua_mocks import LAND_GREEN, WATER_GREEN, WATER_NIR, write_aqua_bands
from conftest import register_user
from satellite_mocks import (
    BLOB_HOST,
    create_session,
    install_client_mock,
    register,
    route_handler,
    stac_item,
)
from sqlalchemy import text

HISTORY_ASSETS = [
    ("visual", f"https://{BLOB_HOST}/container/hist-visual.tif", "image/tiff"),
    ("B03", f"https://{BLOB_HOST}/container/hist-B03.tif", "image/tiff"),
    ("B04", f"https://{BLOB_HOST}/container/hist-B04.tif", "image/tiff"),
    ("B08", f"https://{BLOB_HOST}/container/hist-B08.tif", "image/tiff"),
    ("SCL", f"https://{BLOB_HOST}/container/hist-SCL.tif", "image/tiff"),
]

SCENE_A = stac_item(
    scene_id="S2A_T43PFJ_20240705T040000", datetime="2024-07-05T04:00:00Z", assets=HISTORY_ASSETS
)
SCENE_B = stac_item(
    scene_id="S2A_T43PFJ_20240712T040000", datetime="2024-07-12T04:00:00Z", assets=HISTORY_ASSETS
)
SCENE_C = stac_item(
    scene_id="S2A_T43PFJ_20240720T040000", datetime="2024-07-20T04:00:00Z", assets=HISTORY_ASSETS
)


def _discover(client, monkeypatch, items=None) -> tuple[int, list[dict]]:
    items = items or [SCENE_A, SCENE_B, SCENE_C]
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler(mpc_items=items))
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    scenes = sorted(search.json()["scenes"], key=lambda scene: scene["acquisition_date"])
    return session_id, scenes


def _coherent_bands(state: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (green, red, nir) arrays for one coherent synthetic scene state.

    - "green": dense vegetation (NDVI ~0.698, NDWI -0.2 -> no water)
    - "mixed": top half water / bottom half vegetation (NDVI lower, half water)
    """
    size = 40
    if state == "green":
        green = np.full((size, size), LAND_GREEN, dtype=np.uint16)
        red = np.full((size, size), REF_VEGETATION, dtype=np.uint16)
        nir = np.full((size, size), REF_NIR_VEGETATION, dtype=np.uint16)
    elif state == "mixed":
        green = np.full((size, size), LAND_GREEN, dtype=np.uint16)
        red = np.full((size, size), REF_VEGETATION, dtype=np.uint16)
        nir = np.full((size, size), REF_NIR_VEGETATION, dtype=np.uint16)
        half = size // 2
        green[:half, :] = WATER_GREEN
        red[:half, :] = REF_WATER
        nir[:half, :] = WATER_NIR
    else:
        raise ValueError(state)
    return green, red, nir


def _seed_timeline_scene(scene_id: int, state: str, *, scl=None) -> None:
    directory = Path(tempfile.mkdtemp(prefix="hist_api_"))
    green, red, nir = _coherent_bands(state)
    paths = write_aqua_bands(directory, green, nir, scl=scl)  # B03 + B08
    paths["B04"] = write_band(directory / "B04.tif", red)
    for key, path in paths.items():
        seed_retrieval(scene_id, key, path)


def _seed_timeline(scenes: list[dict], states: list[str], *, scl=None) -> None:
    for scene, state in zip(scenes, states, strict=False):
        _seed_timeline_scene(scene["id"], state, scl=scl)


def _analyze(client, session_id: int, **overrides) -> dict:
    payload = {"analysis_session_id": session_id}
    payload.update(overrides)
    return client.post("/api/v1/historical/analyze", json=payload)


def _create_no_aoi_session(client) -> int:
    response = client.post(
        "/api/v1/analysis-sessions", json={"title": "No AOI session", "agents": ["agri"]}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ---------------------------------------------------------------------------
# Auth & basic validation
# ---------------------------------------------------------------------------


def test_analyze_requires_authentication(client):
    response = _analyze(client, 1)
    assert response.status_code == 401


def test_analyze_unknown_session(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    response = _analyze(client, 999_999)
    assert response.status_code == 404


def test_analyze_unknown_or_rival_session_is_404(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    register_user(client, "rival@example.com", "rival")
    response = _analyze(client, session_id)
    assert response.status_code == 404


def test_analyze_requires_session_aoi(client):
    register(client, "owner@example.com")
    session_id = _create_no_aoi_session(client)
    response = _analyze(client, session_id)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "session_has_no_aoi"


# ---------------------------------------------------------------------------
# Type & threshold validation
# ---------------------------------------------------------------------------


def test_rejects_empty_types(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    response = _analyze(client, session_id, types=[])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "historical_type_required"


def test_rejects_unsupported_type(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    response = _analyze(client, session_id, types=["soil"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "historical_type_unsupported"


def test_rejects_invalid_vegetation_threshold(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    for threshold in (0.0, 2.5):
        response = _analyze(
            client, session_id, types=["vegetation"], vegetation_threshold=threshold
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_vegetation_threshold"


def test_rejects_invalid_water_threshold(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    for threshold in (-1.5, 1.5):
        response = _analyze(client, session_id, types=["water"], water_threshold=threshold)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_water_threshold"


# ---------------------------------------------------------------------------
# Date-range override (session range is authoritative)
# ---------------------------------------------------------------------------


def test_date_override_requires_both_dates(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    response = _analyze(client, session_id, start_date="2024-07-01")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    response = _analyze(client, session_id, end_date="2024-07-31")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_date_override_must_stay_within_session(client):
    register(client, "owner@example.com")
    session_id = create_session(client)  # 2024-07-01 .. 2024-07-31
    response = _analyze(client, session_id, start_date="2024-06-01", end_date="2024-06-30")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "date_range_outside_session"


def test_date_override_filters_the_timeline(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    response = _analyze(client, session_id, start_date="2024-07-10", end_date="2024-07-31")
    assert response.status_code == 200, response.text
    body = response.json()
    dates = [observation["date"] for observation in body["observations"]]
    assert dates == ["2024-07-12", "2024-07-20"]
    assert body["coverage"]["observation_count"] == 2
    assert body["coverage"]["compared_pairs"] == 1
    assert any("excluded" in note for note in body["coverage"]["notes"])


# ---------------------------------------------------------------------------
# Coverage & ordering (missing data stays missing, never zero)
# ---------------------------------------------------------------------------


def test_no_observations_is_explicit_unavailable(client):
    register(client, "owner@example.com")
    session_id = create_session(client)
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["unavailable"]["code"] == "no_historical_observations"
    assert body["coverage"]["observation_count"] == 0
    assert body["observations"] == []
    assert body["events"] == []
    assert body["summary"].startswith("No historical satellite observations")
    assert body["provenance"]["derived_on_demand"] is True


def test_single_observation_has_no_events(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch, items=[SCENE_A])
    _seed_timeline(scenes, ["green"], scl=clear_scl())
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert len(body["observations"]) == 1
    assert body["events"] == []
    assert body["coverage"]["compared_pairs"] == 0
    assert body["trends"]["vegetation"]["basis"] == "Single observation; no change computed."
    assert body["trends"]["vegetation"]["observations"] == 1
    assert any("Only one observation" in note for note in body["coverage"]["notes"])


def test_observations_ordered_oldest_to_newest(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    dates = [observation["date"] for observation in body["observations"]]
    assert dates == ["2024-07-05", "2024-07-12", "2024-07-20"]
    assert [observation["index"] for observation in body["observations"]] == [0, 1, 2]
    assert [observation["scene"]["id"] for observation in body["observations"]] == [
        scenes[0]["id"],
        scenes[1]["id"],
        scenes[2]["id"],
    ]
    assert body["coverage"]["ordered_by"] == "acquisition_date (oldest → newest)"


def test_same_day_scenes_are_not_compared(client, monkeypatch):
    same_day = [
        stac_item(
            scene_id="S2A_T43PFJ_20240705T040000",
            datetime="2024-07-05T04:00:00Z",
            assets=HISTORY_ASSETS,
        ),
        stac_item(
            scene_id="S2B_T43PFJ_20240705T044000",
            datetime="2024-07-05T04:40:00Z",
            assets=HISTORY_ASSETS,
        ),
    ]
    session_id, scenes = _discover(client, monkeypatch, items=same_day)
    _seed_timeline(scenes, ["green", "mixed"], scl=clear_scl())
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["observations"]) == 2
    assert body["events"] == []
    assert body["coverage"]["same_day_pairs_skipped"] == 1
    assert body["coverage"]["compared_pairs"] == 0
    assert any("same acquisition date" in note for note in body["coverage"]["notes"])
    assert "No changes between consecutive observations could be computed." in body["summary"]


# ---------------------------------------------------------------------------
# Unavailable states (explicit, never fabricated)
# ---------------------------------------------------------------------------


def test_all_unavailable_when_bands_missing(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["unavailable"]["code"] == "all_requested_analyses_unavailable"
    for observation in body["observations"]:
        assert observation["vegetation"]["status"] == "unavailable"
        assert observation["vegetation"]["unavailable"]["code"] == "bands_not_retrieved"
        assert observation["water"]["status"] == "unavailable"
    for event in body["events"]:
        assert event["status"] == "unavailable"
        assert event["unavailable"]["code"] == "bands_not_retrieved"
    # Missing observations are never coerced to zero.
    assert all(trend["observations"] == 0 for trend in body["trends"].values())


def test_partial_unavailable_keeps_top_level_completed(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline_scene(scenes[0]["id"], "green", scl=clear_scl())
    response = _analyze(client, session_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["observations"][0]["vegetation"]["status"] == "completed"
    assert body["observations"][1]["vegetation"]["status"] == "unavailable"
    assert body["observations"][1]["vegetation"]["unavailable"]["code"] == "bands_not_retrieved"
    for event in body["events"]:
        assert event["status"] == "unavailable"
    assert body["trends"]["vegetation"]["observations"] == 1
    assert "measured on 1 of 3 observations" in body["summary"]


# ---------------------------------------------------------------------------
# Happy path: completed evidence-based timeline
# ---------------------------------------------------------------------------


def test_completed_timeline_events_and_trends(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())

    response = _analyze(client, session_id, types=["vegetation", "water"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert "id" not in body
    assert "created_at" not in body
    assert body["types_requested"] == ["vegetation", "water"]
    assert body["coverage"]["observation_count"] == 3
    assert body["coverage"]["compared_pairs"] == 2
    assert body["coverage"]["same_day_pairs_skipped"] == 0
    assert body["session"]["id"] == session_id
    assert body["provenance"]["engine_version"].startswith("geoagent-historical")
    assert "sig=" not in response.text

    # Per-observation metrics (vegetation mean NDVI, water pixel count).
    veg_means = [
        observation["vegetation"]["statistics"]["mean"] for observation in body["observations"]
    ]
    assert veg_means[0] == pytest.approx(veg_means[2], abs=1e-4)
    assert veg_means[1] < veg_means[0]
    water_pixels = [
        observation["water"]["water"]["pixel_count"] for observation in body["observations"]
    ]
    assert water_pixels == [0, 800, 0]
    assert body["observations"][1]["scene"]["metadata"]["constellation"] == "sentinel-2"
    assert len(body["weather_contexts"]) == 3
    assert body["weather_contexts"][0]["scene"]["acquisition_date"] == "2024-07-05"

    # Events: 2 comparisons x 2 types, all completed with deterministic labels.
    assert len(body["events"]) == 4
    by_type = {}
    for event in body["events"]:
        assert event["status"] == "completed"
        assert event["mask"]["data_uri"].startswith("data:image/png;base64,")
        assert event["classification"]["comparison_pixels"] == 1600
        by_type.setdefault(event["type"], []).append(event["classification"])
    assert by_type["vegetation"][0]["event"] == "vegetation_decrease"
    assert by_type["vegetation"][1]["event"] == "vegetation_increase"
    assert by_type["vegetation"][0]["region"]["decreased"]["pixel_count"] == 800
    assert by_type["water"][0]["event"] == "water_expansion"
    assert by_type["water"][1]["event"] == "water_reduction"
    assert by_type["water"][0]["water_extent"]["delta_pixels"] == 800
    assert by_type["water"][0]["water_extent"]["lost"]["pixel_count"] == 0

    # Descriptive trends cover the observations.
    vegetation = body["trends"]["vegetation"]
    assert vegetation["observations"] == 3
    assert vegetation["basis"] == "Trend across 3 observations."
    assert vegetation["period"]["start"] == "2024-07-05"
    assert vegetation["period"]["end"] == "2024-07-20"
    assert vegetation["absolute_change"] == pytest.approx(0.0, abs=1e-4)
    water = body["trends"]["water"]
    assert water["observations"] == 3
    assert water["minimum"]["date"] == "2024-07-05"
    assert water["maximum"]["date"] == "2024-07-12"


def test_include_weather_false_omits_contexts(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    response = _analyze(client, session_id, include_weather=False)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weather_contexts"] is None
    assert all(observation["weather_context"] is None for observation in body["observations"])


def test_derived_on_demand_creates_no_tables(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch)
    _seed_timeline(scenes, ["green", "mixed", "green"], scl=clear_scl())
    response = _analyze(client, session_id, types=["vegetation", "water"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        tables = (
            db.execute(
                text(
                    "select tablename from pg_tables "
                    "where tablename like 'historical%' or tablename like 'change%'"
                )
            )
            .scalars()
            .all()
        )
    assert tables == []


# ---------------------------------------------------------------------------
# Regression: historical + change detection + agri + aqua + weather, one session
# ---------------------------------------------------------------------------


def test_regression_all_engines_share_one_session(client, monkeypatch):
    session_id, scenes = _discover(client, monkeypatch, items=[SCENE_A, SCENE_B])
    _seed_timeline(scenes, ["green", "mixed"], scl=clear_scl())
    before_id, after_id = scenes[0]["id"], scenes[1]["id"]

    historical = _analyze(client, session_id, types=["vegetation", "water"])
    assert historical.status_code == 200, historical.text
    history = historical.json()
    assert history["status"] == "completed"
    assert len(history["observations"]) == 2
    assert history["observations"][0]["vegetation"]["status"] == "completed"
    assert len(history["events"]) == 2  # one gap, both types

    change = client.post(
        "/api/v1/change-detection/analyze",
        json={
            "analysis_session_id": session_id,
            "before_scene_id": before_id,
            "after_scene_id": after_id,
            "types": ["vegetation", "water"],
        },
    )
    assert change.status_code == 200, change.text
    assert change.json()["status"] == "completed"
    assert (
        change.json()["vegetation"]["classification"]["classes"]["decrease"]["pixel_count"] == 800
    )

    agri = client.post(
        "/api/v1/agri/analyze",
        json={"analysis_session_id": session_id, "scene_id": before_id},
    )
    assert agri.status_code == 200, agri.text
    agri_result = agri.json()["results"][0]
    assert agri_result["status"] == "completed"
    assert agri_result["index"]["name"] == "ndvi"

    aqua = client.post(
        "/api/v1/aqua/analyze",
        json={"analysis_session_id": session_id, "scene_id": scenes[1]["id"]},
    )
    assert aqua.status_code == 200, aqua.text
    aqua_result = aqua.json()["results"][0]
    assert aqua_result["status"] == "completed"
    assert aqua_result["classification"]["water"]["pixel_count"] == 800

    weather = client.post(
        "/api/v1/weather/context",
        json={"analysis_session_id": session_id, "scene_id": before_id},
    )
    assert weather.status_code == 200, weather.text
    context = weather.json()["context"]
    # No weather search ran for this session, so the descriptive context is an
    # explicit unavailable state — consistent with missing-data-stays-missing.
    assert context["status"] == "unavailable"
    assert context["unavailable"]["code"] == "no_weather_observations"
