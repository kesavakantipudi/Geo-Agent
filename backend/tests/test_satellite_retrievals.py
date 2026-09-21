"""Phase 4 satellite asset retrieval tests (bounded, on-demand downloads)."""

from __future__ import annotations

from pathlib import Path

from conftest import register_user  # noqa: E402
from satellite_mocks import (
    BLOB_HOST,
    create_session,
    install_client_mock,
    register,
    route_handler,
    stac_item,
)

from app.core.config import get_settings


def _discover(client, monkeypatch) -> int:
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler())
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    return search.json()["scenes"][0]["id"]


def test_retrieval_requires_authentication(client):
    response = client.post("/api/v1/satellite/scenes/1/retrievals", json={"asset_keys": ["visual"]})
    assert response.status_code == 401


def test_retrieve_asset_downloads_file(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)

    response = client.post(
        f"/api/v1/satellite/scenes/{scene_id}/retrievals",
        json={"asset_keys": ["visual"], "analysis_session_id": None},
    )
    assert response.status_code == 200, response.text
    records = response.json()
    assert len(records) == 1
    record = records[0]
    assert record["asset_key"] == "visual"
    assert record["status"] == "completed"
    assert record["size_bytes"] == len(b"asset-bytes")
    assert record["error"] is None

    storage = Path(get_settings().retrieval_storage_dir)
    saved = list((storage / str(scene_id)).glob("*.download"))
    assert len(saved) == 1 and saved[0].read_bytes() == b"asset-bytes"

    # The download URL / token never leaks into responses.
    assert "sig=" not in response.text
    assert record.get("stored_path") is None


def test_retrieval_signed_url_not_persisted(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)
    client.post(
        f"/api/v1/satellite/scenes/{scene_id}/retrievals",
        json={"asset_keys": ["visual"]},
    )

    scene = client.get(f"/api/v1/satellite/scenes/{scene_id}").json()
    visual = next(a for a in scene["assets"] if a["key"] == "visual")
    assert BLOB_HOST in visual["href"]
    assert "sig=" not in visual["href"]


def test_retrieval_unknown_asset_rejected(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)
    response = client.post(
        f"/api/v1/satellite/scenes/{scene_id}/retrievals", json={"asset_keys": ["nope"]}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scene_asset_not_found"


def test_retrieval_exceeds_size_cap_fails(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)
    get_settings().retrieval_max_bytes = 4
    try:
        response = client.post(
            f"/api/v1/satellite/scenes/{scene_id}/retrievals",
            json={"asset_keys": ["visual"]},
        )
        assert response.status_code == 200, response.text
        record = response.json()[0]
        assert record["status"] == "failed"
        assert "maximum allowed download size" in record["error"]
        storage = Path(get_settings().retrieval_storage_dir)
        assert not list((storage / str(scene_id)).glob("*.download"))
    finally:
        get_settings().retrieval_max_bytes = 200 * 1024 * 1024


def test_retrieval_requires_scene_access(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)

    register_user(client, "rival@example.com", "rival")
    response = client.post(
        f"/api/v1/satellite/scenes/{scene_id}/retrievals", json={"asset_keys": ["visual"]}
    )
    assert response.status_code == 404


def test_retrieval_history_and_delete(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)
    client.post(f"/api/v1/satellite/scenes/{scene_id}/retrievals", json={"asset_keys": ["visual"]})

    history = client.get(f"/api/v1/satellite/scenes/{scene_id}/retrievals")
    assert history.status_code == 200
    assert len(history.json()) == 1
    history_id = history.json()[0]["id"]

    storage = Path(get_settings().retrieval_storage_dir)

    delete = client.delete(f"/api/v1/satellite/retrievals/{history_id}")
    assert delete.status_code == 204

    history_after = client.get(f"/api/v1/satellite/scenes/{scene_id}/retrievals")
    assert history_after.json() == []
    assert list((storage / str(scene_id)).glob("*.download")) == []


def test_delete_retrieval_only_owner(client, monkeypatch):
    scene_id = _discover(client, monkeypatch)
    client.post(f"/api/v1/satellite/scenes/{scene_id}/retrievals", json={"asset_keys": ["visual"]})
    history_id = client.get(f"/api/v1/satellite/scenes/{scene_id}/retrievals").json()[0]["id"]

    register_user(client, "other@example.com", "other")
    delete = client.delete(f"/api/v1/satellite/retrievals/{history_id}")
    assert delete.status_code == 404


def test_cdse_download_without_credentials_fails_gracefully(client, monkeypatch):
    register(client, "cdse@example.com")
    cdse_items = [stac_item("S2A_ODATA_20240705T040000")]
    install_client_mock(monkeypatch, route_handler(mpc_items=[], cdse_items=cdse_items))

    get_settings().satellite_enabled_providers = "cdse"
    try:
        session_id = create_session(client)
        search = client.post(
            "/api/v1/satellite/scenes/search",
            json={"analysis_session_id": session_id, "providers": ["cdse"]},
        )
        assert search.status_code == 200, search.text
        assert search.json()["scenes"], search.text

        scene_id = search.json()["scenes"][0]["id"]
        response = client.post(
            f"/api/v1/satellite/scenes/{scene_id}/retrievals",
            json={"asset_keys": [search.json()["scenes"][0]["assets"][0]["key"]]},
        )
        assert response.status_code == 200, response.text
        record = response.json()[0]
        assert "GEOAGENT_CDSE_USERNAME" in record["error"]
    finally:
        get_settings().satellite_enabled_providers = "planetary-computer"
