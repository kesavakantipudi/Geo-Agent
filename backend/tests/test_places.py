"""Phase 3 place-search (geocoding) endpoint tests with a fake provider."""

from __future__ import annotations

from conftest import register_user
from fastapi.testclient import TestClient

from app.services.geocoding.base import GeocodingError


def _register(client: TestClient) -> TestClient:
    register_user(client, "places@example.com", "placesuser")
    return client


def _fake_result(monkeypatch, results):
    from app.api.v1.endpoints import places as places_endpoint

    def fake_search(query, limit=8, *, bbox=None):
        return results

    monkeypatch.setattr(places_endpoint, "search_places", fake_search)


def test_place_search_returns_results(client, monkeypatch):
    _register(client)
    _fake_result(
        monkeypatch,
        [
            {
                "id": "place:143964",
                "provider": "photon",
                "label": "Bengaluru, Karnataka, India",
                "display_name": "Bengaluru, Karnataka, India",
                "bbox": [77.4, 12.8, 77.8, 13.1],
                "center": {"lon": 77.59, "lat": 12.97},
            }
        ],
    )
    response = client.get("/api/v1/places/search?q=bengaluru")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["label"] == "Bengaluru, Karnataka, India"
    assert body[0]["center"] == {"lon": 77.59, "lat": 12.97}


def test_place_search_passes_bbox(client, monkeypatch):
    _register(client)
    captured = {}

    from app.api.v1.endpoints import places as places_endpoint

    def fake_search(query, limit=8, *, bbox=None):
        captured["bbox"] = bbox
        return []

    monkeypatch.setattr(places_endpoint, "search_places", fake_search)
    client.get("/api/v1/places/search?q=river&bbox=77.0,12.0,78.0,13.0")
    assert captured["bbox"] == (77.0, 12.0, 78.0, 13.0)


def test_malformed_bbox_rejected(client, monkeypatch):
    _register(client)
    response = client.get("/api/v1/places/search?q=river&bbox=77.0,12.0")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_bbox"


def test_provider_error_returns_503(client, monkeypatch):
    _register(client)

    from app.api.v1.endpoints import places as places_endpoint

    def failing(query, limit=8, *, bbox=None):
        raise GeocodingError("The geocoding service is unavailable.")

    monkeypatch.setattr(places_endpoint, "search_places", failing)
    response = client.get("/api/v1/places/search?q=anywhere")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_search_requires_authentication(client):
    response = client.get("/api/v1/places/search?q=anywhere")
    assert response.status_code == 401


def test_short_query_rejected(client):
    _register(client)
    response = client.get("/api/v1/places/search?q=x")
    assert response.status_code == 422
