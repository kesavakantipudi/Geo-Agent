"""Phase 5 weather observation endpoint tests (fake Open-Meteo provider)."""

from __future__ import annotations

from conftest import register_user  # noqa: E402
from satellite_mocks import create_session, install_client_mock, register
from weather_mocks import (
    ARCHIVE_HOST,
    FORECAST_HOST,
    openmeteo_payload,
    weather_handler,
)

from app.core.config import get_settings
from app.services.weather import OpenMeteoProvider

PLANAR_AOI = {
    "type": "Polygon",
    "coordinates": [
        [[77.45, 12.85], [77.75, 12.85], [77.75, 13.05], [77.45, 13.05], [77.45, 12.85]]
    ],
}


def _provider_statuses(body):
    return {entry["provider"]: entry for entry in body["providers"]}


def test_search_requires_authentication(client):
    response = client.post("/api/v1/weather/search", json={})
    assert response.status_code == 401


def test_search_requires_aoi_or_session(client):
    register(client, "aoi@example.com")
    response = client.post("/api/v1/weather/search", json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aoi_required"


def test_search_requires_date_range_for_history(client, monkeypatch):
    register(client, "dates@example.com")
    install_client_mock(monkeypatch, weather_handler())
    response = client.post(
        "/api/v1/weather/search",
        json={
            "aoi": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            },
            "data_type": "history",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "date_range_required"


def test_search_returns_observations_for_session(client, monkeypatch):
    register(client, "alice@example.com")
    captured: list[dict] = []
    install_client_mock(monkeypatch, weather_handler(captured=captured))

    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={"analysis_session_id": session_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["truncated"] is False
    statuses = _provider_statuses(body)
    assert statuses["openmeteo"]["observations"] == 6
    assert statuses["openmeteo"]["error"] is None

    obs = body["observations"]
    assert {o["variable"] for o in obs} == {"relative_humidity_2m", "temperature_2m"}
    samples = {
        v: sorted(
            (o for o in obs if o["variable"] == v),
            key=lambda o: o["observed_at"],
        )
        for v in ("relative_humidity_2m", "temperature_2m")
    }
    assert [o["value"] for o in samples["temperature_2m"]] == [23.5, 23.1, 22.8]
    temp = samples["temperature_2m"][0]
    assert temp["value"] == 23.5
    assert temp["units"] == "°C"
    assert temp["timezone"] == "UTC"
    assert temp["observed_at"] in (
        "2024-07-05T00:00:00Z",
        "2024-07-05T00:00:00+00:00",
    )
    assert temp["data_type"] == "current"
    assert temp["provenance"]["provider"] == "openmeteo"
    assert temp["attribution"] == "Weather data by Open-Meteo.com"

    assert len(captured) == 1
    assert FORECAST_HOST in captured[0]["url"]
    assert "temperature_2m" in captured[0]["url"]
    assert "relative_humidity_2m" in captured[0]["url"]
    assert "timezone=UTC" in captured[0]["url"]


def test_missing_values_are_not_fabricated(client, monkeypatch):
    register(client, "bob@example.com")
    payload = openmeteo_payload(
        variables={
            "temperature_2m": [25.0, 24.5, 24.0],
            "pressure_msl": [None, 1013.2, None],
        },
        units={"pressure_msl": "hPa"},
    )
    install_client_mock(monkeypatch, weather_handler(payload))
    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={
            "analysis_session_id": session_id,
            "variables": ["temperature_2m", "pressure_msl"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    pressures = [o for o in body["observations"] if o["variable"] == "pressure_msl"]
    # Only the single recorded sample is present; missing is never stored as 0.
    assert [p["value"] for p in pressures] == [1013.2]
    assert all(o["value"] is not None and o["value"] != 0 for o in body["observations"])


def test_provider_normalize_missing_stays_none():
    provider = OpenMeteoProvider(get_settings())
    payload = openmeteo_payload(
        times=["2024-07-05T00:00", "2024-07-05T01:00"],
        variables={
            "temperature_2m": [23.5],
            "relative_humidity_2m": [],
        },
    )
    points = provider._normalize(
        payload,
        lat=12.95,
        lon=77.55,
        timezone="UTC",
        variables=["temperature_2m", "relative_humidity_2m"],
        units="metric",
        data_type="current",
        model=None,
    )
    assert points[0]["variables"]["temperature_2m"] == 23.5
    assert points[1]["variables"]["temperature_2m"] is None
    assert points[0]["variables"]["relative_humidity_2m"] is None
    assert points[0]["latitude"] == 12.95
    assert points[0]["longitude"] == 77.55
    provider.close()


def test_unknown_variable_rejected(client, monkeypatch):
    register(client, "carol@example.com")
    install_client_mock(monkeypatch, weather_handler())
    response = client.post(
        "/api/v1/weather/search",
        json={
            "aoi": PLANAR_AOI,
            "variables": ["temperature_2m", "bogus"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weather_variable_unknown"


def test_too_many_variables_rejected(client, monkeypatch):
    register(client, "dave@example.com")
    install_client_mock(monkeypatch, weather_handler())
    get_settings().weather_max_variables = 2
    try:
        response = client.post(
            "/api/v1/weather/search",
            json={
                "aoi": PLANAR_AOI,
                "variables": ["temperature_2m", "relative_humidity_2m", "pressure_msl"],
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "weather_too_many_variables"
    finally:
        get_settings().weather_max_variables = 20


def test_unknown_provider_rejected(client, monkeypatch):
    register(client, "erin@example.com")
    install_client_mock(monkeypatch, weather_handler())
    response = client.post(
        "/api/v1/weather/search",
        json={
            "aoi": PLANAR_AOI,
            "providers": ["mars"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "weather_provider_not_enabled"


def test_weather_disabled_rejected(client, monkeypatch):
    register(client, "fran@example.com")
    get_settings().weather_enabled_providers = "none"
    try:
        response = client.post(
            "/api/v1/weather/search",
            json={"aoi": PLANAR_AOI},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "weather_disabled"
    finally:
        get_settings().weather_enabled_providers = "openmeteo"


def test_aoi_must_be_polygon(client, monkeypatch):
    register(client, "grey@example.com")
    install_client_mock(monkeypatch, weather_handler())
    response = client.post(
        "/api/v1/weather/search",
        json={"aoi": {"type": "Point", "coordinates": [77.5, 12.9]}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aoi_not_polygon"


def test_invalid_units_rejected(client):
    register(client, "heidi@example.com")
    response = client.post(
        "/api/v1/weather/search",
        json={
            "aoi": {"type": "Point", "coordinates": [77.5, 12.9]},
            "units": "bogus",
        },
    )
    assert response.status_code == 422


def test_invalid_data_type_rejected(client):
    register(client, "ivan@example.com")
    response = client.post(
        "/api/v1/weather/search",
        json={
            "aoi": {"type": "Point", "coordinates": [77.5, 12.9]},
            "data_type": "bogus",
        },
    )
    assert response.status_code == 422


def test_provider_http_error_surfaces_in_status(client, monkeypatch):
    register(client, "judy@example.com")
    install_client_mock(monkeypatch, weather_handler(error=(503, "unavailable")))
    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={"analysis_session_id": session_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["observations"] == []
    status = _provider_statuses(body)["openmeteo"]
    assert status["observations"] == 0
    assert "HTTP 503" in status["error"]


def test_provider_timeout_surfaces_in_status(client, monkeypatch):
    register(client, "kate@example.com")
    install_client_mock(monkeypatch, weather_handler(raise_timeout=True))
    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={"analysis_session_id": session_id},
    )
    assert response.status_code == 200, response.text
    status = _provider_statuses(response.json())["openmeteo"]
    assert status["observations"] == 0
    assert "timeout" in status["error"]


def test_archive_data_type_routes_to_archive_url(client, monkeypatch):
    register(client, "leo@example.com")
    captured: list[dict] = []
    install_client_mock(monkeypatch, weather_handler(captured=captured))
    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={
            "analysis_session_id": session_id,
            "data_type": "history",
            "variables": ["temperature_2m"],
        },
    )
    assert response.status_code == 200, response.text
    statuses = _provider_statuses(response.json())
    assert statuses["openmeteo"]["observations"] == 3
    assert len(captured) == 1
    assert ARCHIVE_HOST in captured[0]["url"]
    assert "start_date=2024-07-01" in captured[0]["url"]
    assert "end_date=2024-07-31" in captured[0]["url"]


def test_forecast_units_imperial(client, monkeypatch):
    register(client, "mia@example.com")
    captured: list[dict] = []
    payload = openmeteo_payload(
        variables={"temperature_2m": [74.3]},
        units={"temperature_2m": "°F"},
    )
    install_client_mock(monkeypatch, weather_handler(payload, captured=captured))
    session_id = create_session(client)
    response = client.post(
        "/api/v1/weather/search",
        json={
            "analysis_session_id": session_id,
            "variables": ["temperature_2m"],
            "units": "imperial",
        },
    )
    assert response.status_code == 200, response.text
    obs = response.json()["observations"][0]
    assert obs["value"] == 74.3
    assert obs["units"] == "°F"
    assert "temperature_unit=fahrenheit" in captured[0]["url"]


def test_observations_persisted_and_listable(client, monkeypatch):
    register(client, "nina@example.com")
    install_client_mock(monkeypatch, weather_handler())
    session_id = create_session(client)
    first = client.post("/api/v1/weather/search", json={"analysis_session_id": session_id})
    second = client.post("/api/v1/weather/search", json={"analysis_session_id": session_id})
    assert first.status_code == second.status_code == 200
    first_ids = {o["id"]: o["variable"] for o in first.json()["observations"]}
    second_ids = {o["id"]: o["variable"] for o in second.json()["observations"]}
    assert first_ids == second_ids

    listing = client.get(f"/api/v1/weather/sessions/{session_id}/observations")
    assert listing.status_code == 200
    listed = {o["id"]: o["variable"] for o in listing.json()}
    assert listed == first_ids

    single_id = next(iter(first_ids))
    single = client.get(f"/api/v1/weather/observations/{single_id}")
    assert single.status_code == 200
    assert single.json()["id"] == single_id


def test_observation_not_shared_across_users(client, monkeypatch):
    register(client, "oscar@example.com")
    install_client_mock(monkeypatch, weather_handler())
    session_id = create_session(client)
    search = client.post("/api/v1/weather/search", json={"analysis_session_id": session_id})
    observation_id = search.json()["observations"][0]["id"]

    register_user(client, "intruder@example.com", "intruder")
    response = client.get(f"/api/v1/weather/observations/{observation_id}")
    assert response.status_code == 404
