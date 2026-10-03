"""Phase 6C API tests: /weather/context end-to-end (fake providers).

Context is derived from observations persisted through the real Phase 5
``/weather/search`` flow (fake Open-Meteo), so these tests exercise the actual
storage/discovery path. Covers authorization, the scene↔session association
rule, window handling, aggregation, explicit unavailable states, and the
embedded context on agri/aqua intelligence results.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from conftest import register_user
from satellite_mocks import (
    BLOB_HOST,
    create_session,
    install_client_mock,
    register,
    route_handler,
    stac_item,
)
from weather_mocks import openmeteo_payload, weather_handler

AGRI_ASSETS = [
    ("visual", f"https://{BLOB_HOST}/container/ctx-visual.tif", "image/tiff"),
    ("B04", f"https://{BLOB_HOST}/container/ctx-B04.tif", "image/tiff"),
    ("B08", f"https://{BLOB_HOST}/container/ctx-B08.tif", "image/tiff"),
    ("SCL", f"https://{BLOB_HOST}/container/ctx-SCL.tif", "image/tiff"),
]

DEFAULT_CONTEXT_VARIABLES = [
    "temperature_2m",
    "temperature_2m_max",
    "temperature_2m_min",
    "relative_humidity_2m",
    "precipitation",
]


def _discover(client, monkeypatch, items=None) -> tuple[int, int]:
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler(mpc_items=items or [stac_item()]))
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    return session_id, search.json()["scenes"][0]["id"]


def _seed_weather(client, monkeypatch, session_id, *, variables=None, payload=None) -> dict:
    install_client_mock(monkeypatch, weather_handler(payload))
    body = {
        "analysis_session_id": session_id,
        "variables": variables or ["temperature_2m", "relative_humidity_2m"],
    }
    response = client.post("/api/v1/weather/search", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _context(client, session_id: int, scene_id: int, **overrides) -> dict:
    payload = {"analysis_session_id": session_id, "scene_id": scene_id}
    payload.update(overrides)
    return client.post("/api/v1/weather/context", json=payload)


# ---------------------------------------------------------------------------
# Auth & access control
# ---------------------------------------------------------------------------


def test_context_requires_authentication(client):
    response = _context(client, 1, 1)
    assert response.status_code == 401


def test_context_unknown_session(client, monkeypatch):
    _, scene_id = _discover(client, monkeypatch)
    response = _context(client, 999_999, scene_id)
    assert response.status_code == 404


def test_context_unknown_scene(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    response = _context(client, session_id, 999_999)
    assert response.status_code == 404


def test_context_requires_scene_access(client, monkeypatch):
    _, scene_id = _discover(client, monkeypatch)
    register_user(client, "rival@example.com", "rival")
    rival_session = create_session(client)
    response = _context(client, rival_session, scene_id)
    assert response.status_code == 404


def test_context_scene_not_associated_with_session(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    other_session = create_session(client)
    response = _context(client, other_session, scene_id)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scene_not_associated"


# ---------------------------------------------------------------------------
# Context derivation
# ---------------------------------------------------------------------------


def test_context_returns_aggregated_weather(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_weather(client, monkeypatch, session_id)

    response = _context(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    context = response.json()["context"]

    assert context["status"] == "available"
    assert context["satellite_observation"] == "2024-07-05"
    assert context["scene"]["acquisition_date"] == "2024-07-05"
    assert context["period"] == {
        "start": "2024-07-04",
        "end": "2024-07-06",
        "days_before": 1,
        "days_after": 1,
    }
    assert context["variables_requested"] == DEFAULT_CONTEXT_VARIABLES
    assert context["observation_count"] == 6
    assert context["providers"] == ["openmeteo"]
    assert context["data_types"] == ["current"]
    assert context["attribution"] == "Weather data by Open-Meteo.com"
    assert context["note"]

    variables = {item["name"]: item for item in context["variables"]}
    temperature = variables["temperature_2m"]
    assert temperature["aggregator"] == "mean"
    assert temperature["value"] == pytest.approx((23.5 + 23.1 + 22.8) / 3)
    assert temperature["units"] == "°C"
    assert temperature["sample_count"] == temperature["expected_count"] == 3
    assert temperature["coverage_pct"] == 100.0

    humidity = variables["relative_humidity_2m"]
    assert humidity["value"] == pytest.approx((82 + 80 + 79) / 3)

    # Requested but not stored variables: explicit None, never 0.
    for name in ("temperature_2m_max", "temperature_2m_min", "precipitation"):
        missing = variables[name]
        assert missing["available"] is True
        assert missing["value"] is None
        assert missing["coverage_pct"] == 0.0

    # 2 of 5 variables carry data -> partial but explicit.
    assert context["completeness_pct"] == 40.0
    assert context["partial"] is True
    assert context["unavailable"] is None


def test_context_same_day_only_window_echoed(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_weather(client, monkeypatch, session_id)

    response = _context(client, session_id, scene_id, days_before=0, days_after=0)
    assert response.status_code == 200, response.text
    context = response.json()["context"]
    assert context["period"]["start"] == "2024-07-05"
    assert context["period"]["end"] == "2024-07-05"
    assert context["period"]["days_before"] == 0
    assert context["period"]["days_after"] == 0
    assert context["status"] == "available"


def test_context_window_out_of_range_rejected(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _context(client, session_id, scene_id, days_before=-1)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weather_context_window_out_of_range"


def test_context_unknown_variable_rejected(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _context(client, session_id, scene_id, variables=["temperature_2m", "bogus"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weather_variable_unknown"


def test_context_unknown_provider_rejected(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _context(client, session_id, scene_id, providers=["mars"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weather_provider_not_enabled"


def test_context_no_weather_observations_is_explicit(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    # No weather search performed -> nothing stored for the session.
    response = _context(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    context = response.json()["context"]
    assert context["status"] == "unavailable"
    assert context["unavailable"]["code"] == "no_weather_observations"
    assert context["observation_count"] == 0
    assert context["variables"] == []
    assert context["completeness_pct"] == 0.0
    assert context["partial"] is False


def test_context_ignores_observations_outside_window(client, monkeypatch):
    # Scene acquired well after the only stored weather data.
    session_id, scene_id = _discover(
        client, monkeypatch, items=[stac_item(datetime="2024-08-20T04:00:00Z")]
    )
    _seed_weather(client, monkeypatch, session_id)

    response = _context(client, session_id, scene_id, days_before=0, days_after=0)
    assert response.status_code == 200, response.text
    context = response.json()["context"]
    assert context["status"] == "unavailable"
    assert context["unavailable"]["code"] == "no_weather_observations"
    assert context["period"]["start"] == "2024-08-20"


def test_context_precipitation_sums_recorded_values_including_zeros(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    payload = openmeteo_payload(
        variables={"precipitation": [0.0, 2.5, 1.1], "temperature_2m": [20.0, 21.0, 22.0]},
        units={"precipitation": "mm"},
    )
    _seed_weather(client, monkeypatch, session_id, variables=["precipitation"], payload=payload)

    response = _context(client, session_id, scene_id, days_before=0, days_after=0)
    assert response.status_code == 200, response.text
    context = response.json()["context"]
    assert context["status"] == "available"
    precipitation = {item["name"]: item for item in context["variables"]}["precipitation"]
    assert precipitation["aggregator"] == "sum"
    assert precipitation["value"] == pytest.approx(3.6)  # 0.0 is a real measurement
    assert precipitation["units"] == "mm"
    assert precipitation["sample_count"] == 3
    assert precipitation["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Embedded context on intelligence results
# ---------------------------------------------------------------------------


def test_agri_unavailable_result_carries_weather_context(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch, items=[stac_item(assets=AGRI_ASSETS)])
    _seed_weather(client, monkeypatch, session_id)

    response = client.post(
        "/api/v1/agri/analyze",
        json={"analysis_session_id": session_id, "scene_id": scene_id},
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "unavailable"
    assert result["unavailable"]["code"] == "bands_not_retrieved"
    weather = result["weather_context"]
    assert weather["status"] == "available"
    assert weather["satellite_observation"] == "2024-07-05"


def test_agri_completed_result_carries_weather_context(client, monkeypatch):
    from agri_mocks import clear_scl, dense_vegetation_scene, seed_retrieval, write_scene_bands

    session_id, scene_id = _discover(client, monkeypatch, items=[stac_item(assets=AGRI_ASSETS)])
    _seed_weather(client, monkeypatch, session_id)

    directory = Path(tempfile.mkdtemp(prefix="ctx_api_"))
    band_paths = write_scene_bands(directory, *dense_vegetation_scene(), scl=clear_scl())
    for asset_key, path in band_paths.items():
        seed_retrieval(scene_id, asset_key, path)

    response = client.post(
        "/api/v1/agri/analyze",
        json={"analysis_session_id": session_id, "scene_id": scene_id},
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    weather = result["weather_context"]
    assert weather["status"] == "available"
    assert weather["completeness_pct"] > 0.0

    # get_analysis recomputes context on demand (never persisted).
    detail = client.get(f"/api/v1/agri/analyses/{result['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["weather_context"]["status"] == "available"


def test_aqua_unavailable_result_carries_weather_context(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch, items=[stac_item(assets=AGRI_ASSETS)])
    _seed_weather(client, monkeypatch, session_id)

    response = client.post(
        "/api/v1/aqua/analyze",
        json={"analysis_session_id": session_id, "scene_id": scene_id},
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "unavailable"
    assert result["unavailable"]["code"] == "bands_not_retrieved"
    assert result["weather_context"]["status"] == "available"
