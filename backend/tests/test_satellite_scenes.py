"""Phase 4 satellite scene discovery endpoint tests (fake STAC providers)."""

from __future__ import annotations

import httpx
from conftest import register_user  # noqa: E402
from satellite_mocks import (
    BLOB_HOST,
    create_session,
    install_client_mock,
    register,
    route_handler,
    scene_collection,
    stac_item,
)

from app.core.config import get_settings


def _provider_statuses(body):
    return {entry["provider"]: entry for entry in body["providers"]}


def test_search_requires_authentication(client):
    response = client.post("/api/v1/satellite/scenes/search", json={})
    assert response.status_code == 401


def test_search_requires_aoi_or_session(client):
    register(client, "aoi@example.com")
    response = client.post(
        "/api/v1/satellite/scenes/search",
        json={"start_date": "2024-07-01", "end_date": "2024-07-31"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aoi_required"


def test_search_requires_date_range(client):
    register(client, "dates@example.com")
    response = client.post(
        "/api/v1/satellite/scenes/search",
        json={
            "aoi": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            }
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "date_range_required"


def test_search_returns_scenes_for_session(client, monkeypatch):
    register(client, "alice@example.com")
    captured: list[dict] = []
    items = [
        stac_item("S2A_T43PFJ_20240705T040000", cloud_cover=5.0),
        stac_item("S2B_T43PFJ_20240707T040000", cloud_cover=15.0),
    ]
    install_client_mock(monkeypatch, route_handler(mpc_items=items, captured=captured))

    session_id = create_session(client)
    response = client.post(
        "/api/v1/satellite/scenes/search",
        json={"analysis_session_id": session_id, "max_cloud_cover": 20.0},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["truncated"] is False
    assert [s["scene_id"] for s in body["scenes"]] == [
        "S2A_T43PFJ_20240705T040000",
        "S2B_T43PFJ_20240707T040000",
    ]
    statuses = _provider_statuses(body)
    assert statuses["planetary-computer"]["scenes"] == 2
    assert statuses["planetary-computer"]["error"] is None

    scene = body["scenes"][0]
    assert scene["provider"] == "planetary-computer"
    assert scene["acquisition_date"] == "2024-07-05"
    assert scene["cloud_cover"] == 5.0
    assert scene["platform"] == "sentinel-2a"
    assert scene["bbox"] == [77.5, 12.9, 77.6, 13.0]
    assert len(scene["assets"]) == 2
    assert all("sig=" not in asset["href"] for asset in scene["assets"])
    assert scene["geometry"]["type"] == "Polygon"

    assert all(req["url"].startswith("https://planetarycomputer.microsoft.com") for req in captured)


def test_search_caches_scenes_and_discovers_once(client, monkeypatch):
    register(client, "bob@example.com")
    install_client_mock(monkeypatch, route_handler())

    session_id = create_session(client)
    payload = {"analysis_session_id": session_id}
    first = client.post("/api/v1/satellite/scenes/search", json=payload)
    second = client.post("/api/v1/satellite/scenes/search", json=payload)
    assert first.status_code == second.status_code == 200
    first_ids = {s["id"]: s["scene_id"] for s in first.json()["scenes"]}
    second_ids = {s["id"]: s["scene_id"] for s in second.json()["scenes"]}
    assert first_ids == second_ids

    listing = client.get(f"/api/v1/satellite/sessions/{session_id}/scenes")
    assert listing.status_code == 200
    assert {s["id"] for s in listing.json()} == set(first_ids.keys())


def test_search_partial_provider_failure(client, monkeypatch):
    register(client, "carol@example.com")
    items = [stac_item("S2A_T43PFJ_20240705T040000")]

    def handler(request):
        url = str(request.url)
        if "stac.dataspace" in url:
            return httpx.Response(503, json={"detail": "service unavailable"})
        if url.endswith("/search"):
            return httpx.Response(200, json=scene_collection(*items))
        if "sas/v1/sign" in url:
            query = request.url.params.get("href", "")
            return httpx.Response(200, json={"href": f"{query}?se=x&sig=T"})
        if BLOB_HOST in url:
            return httpx.Response(200, headers={"content-length": "3"}, content=b"abc")
        return httpx.Response(404, json={"detail": "not found"})

    install_client_mock(monkeypatch, handler)

    get_settings().satellite_enabled_providers = "planetary-computer,cdse"
    try:
        session_id = create_session(client)
        response = client.post(
            "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["scenes"]) == 1
        statuses = _provider_statuses(body)
        assert statuses["planetary-computer"]["scenes"] == 1
        assert statuses["cdse"]["scenes"] == 0
        assert "unexpected" in statuses["cdse"]["error"]
    finally:
        get_settings().satellite_enabled_providers = "planetary-computer"


def test_search_unknown_provider_rejected(client, monkeypatch):
    register(client, "dave@example.com")
    response = client.post(
        "/api/v1/satellite/scenes/search",
        json={"aoi": {"type": "Point", "coordinates": [77.5, 12.9]}, "providers": ["mars"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "satellite_provider_not_enabled"


def test_search_disabled_rejected(client, monkeypatch):
    register(client, "erin@example.com")
    get_settings().satellite_enabled_providers = "none"
    try:
        response = client.post(
            "/api/v1/satellite/scenes/search",
            json={"aoi": {"type": "Point", "coordinates": [77.5, 12.9]}},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "satellite_disabled"
    finally:
        get_settings().satellite_enabled_providers = "planetary-computer"


def test_cloud_cover_filter_removes_cdse_items(client, monkeypatch):
    register(client, "fran@example.com")
    cdse_items = [stac_item("S2A_CDSE_20240705T040000", cloud_cover=30.0)]
    install_client_mock(monkeypatch, route_handler(mpc_items=[], cdse_items=cdse_items))

    get_settings().satellite_enabled_providers = "cdse"
    try:
        response = client.post(
            "/api/v1/satellite/scenes/search",
            json={
                "analysis_session_id": create_session(client),
                "providers": ["cdse"],
                "max_cloud_cover": 20.0,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["scenes"] == []
        assert _provider_statuses(body)["cdse"]["scenes"] == 0
    finally:
        get_settings().satellite_enabled_providers = "planetary-computer"


def test_mpc_cloud_filter_sent_server_side(client, monkeypatch):
    register(client, "grey@example.com")
    captured: list[dict] = []
    install_client_mock(monkeypatch, route_handler(captured=captured))

    session_id = create_session(client)
    response = client.post(
        "/api/v1/satellite/scenes/search",
        json={"analysis_session_id": session_id, "max_cloud_cover": 10.0},
    )
    assert response.status_code == 200, response.text
    search_request = next(req for req in captured if req["url"].endswith("/search"))
    body = search_request["body"].decode("utf-8")
    assert '"filter-lang":"cql2-json"' in body
    assert '"property":"eo:cloud_cover"' in body


def test_scene_not_shared_across_users(client, monkeypatch):
    register(client, "heidi@example.com")
    install_client_mock(monkeypatch, route_handler())
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    scene_id = search.json()["scenes"][0]["id"]

    register_user(client, "intruder@example.com", "intruder")
    response = client.get(f"/api/v1/satellite/scenes/{scene_id}")
    assert response.status_code == 404


def test_blob_href_persisted_unsigned(client, monkeypatch):
    register(client, "lana@example.com")
    install_client_mock(monkeypatch, route_handler())
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    scene = search.json()["scenes"][0]
    assert all(BLOB_HOST in asset["href"] for asset in scene["assets"])
    assert all("sig=" not in asset["href"] for asset in scene["assets"])
