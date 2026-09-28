"""Phase 6A API tests: analysis auth, access control, unavailable states.

The satellite download mock serves opaque bytes, so these tests seed real
synthetic GeoTIFF band files (see ``agri_mocks``) and completed retrieval rows
before calling the analysis endpoint — exactly the state a real completed
download would produce.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from agri_mocks import (
    clear_scl,
    cloudy_scl,
    dense_vegetation_scene,
    seed_retrieval,
    write_scene_bands,
)
from conftest import register_user
from satellite_mocks import (
    BLOB_HOST,
    create_session,
    install_client_mock,
    register,
    route_handler,
    stac_item,
)

AGRI_ASSETS = [
    ("visual", f"https://{BLOB_HOST}/container/agri-visual.tif", "image/tiff"),
    ("B04", f"https://{BLOB_HOST}/container/agri-B04.tif", "image/tiff"),
    ("B08", f"https://{BLOB_HOST}/container/agri-B08.tif", "image/tiff"),
    ("SCL", f"https://{BLOB_HOST}/container/agri-SCL.tif", "image/tiff"),
]


def _discover(client, monkeypatch) -> tuple[int, int]:
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler(mpc_items=[stac_item(assets=AGRI_ASSETS)]))
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    return session_id, search.json()["scenes"][0]["id"]


def _seed_bands(scene_id: int, red, nir, scl=None) -> None:
    directory = Path(tempfile.mkdtemp(prefix="agri_api_"))
    paths = write_scene_bands(directory, red, nir, scl=scl)
    for key, path in paths.items():
        seed_retrieval(scene_id, key, path)


def _analyze(client, session_id: int, scene_id: int, **overrides) -> dict:
    payload = {"analysis_session_id": session_id, "scene_id": scene_id}
    payload.update(overrides)
    return client.post("/api/v1/agri/analyze", json=payload)


# ---------------------------------------------------------------------------
# Auth & validation
# ---------------------------------------------------------------------------


def test_analyze_requires_authentication(client):
    response = _analyze(client, 1, 1)
    assert response.status_code == 401


def test_analyze_unknown_session(client, monkeypatch):
    scene_id = _seed_bare_scene(client, monkeypatch)
    response = _analyze(client, 999_999, scene_id)
    assert response.status_code == 404


def test_analyze_unknown_scene(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    response = _analyze(client, session_id, 999_999)
    assert response.status_code == 404


def test_analyze_requires_scene_access(client, monkeypatch):
    _, scene_id = _discover(client, monkeypatch)
    register_user(client, "rival@example.com", "rival")
    rival_session = create_session(client)
    response = _analyze(client, rival_session, scene_id)
    assert response.status_code == 404


def test_analyze_rejects_unsupported_index(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())
    response = _analyze(client, session_id, scene_id, indices=["evi"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "agri_index_unsupported"


def test_analyze_rejects_empty_indices(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _analyze(client, session_id, scene_id, indices=[])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "agri_index_required"


# ---------------------------------------------------------------------------
# Unavailable states (explicit, never fabricated)
# ---------------------------------------------------------------------------


def test_analyze_unavailable_when_bands_not_retrieved(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "unavailable"
    assert result["unavailable"]["code"] == "bands_not_retrieved"
    assert "missing" in result["unavailable"]["details"][0]
    assert result["scene"]["id"] == scene_id


def test_analyze_unavailable_when_insufficient_valid_pixels(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    red = np.zeros((16, 16), dtype=np.uint16)
    nir = np.zeros((16, 16), dtype=np.uint16)
    _seed_bands(scene_id, red, nir)
    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "unavailable"
    assert result["unavailable"]["code"] == "insufficient_valid_pixels"


# ---------------------------------------------------------------------------
# Happy path: completed analysis, persistence, listing
# ---------------------------------------------------------------------------


def test_completed_analysis_and_provenance(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())

    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["id"] is not None
    assert result["acquisition_date"] == "2024-07-05"
    assert result["scene"]["provider"] == "planetary-computer"
    assert result["index"]["name"] == "ndvi"
    assert result["index"]["formula"].startswith("NDVI")
    assert result["statistics"]["valid_pixel_pct"] == 100.0
    assert result["statistics"]["mean"] == np.round(3700 / 5300, 6)
    assert result["classification"]["overall"]["tier"] == "very_high"
    assert result["classification"]["dominant_tier"]["tier"] == "very_high"
    assert result["cloud"]["cloud_mask_available"] is True
    assert result["cloud"]["masked_classes"] == [0, 1, 3, 8, 9, 10, 11]
    assert {band["role"] for band in result["bands"]} == {"red", "nir", "cloud_mask"}
    assert all(band["retrieval_id"] > 0 for band in result["bands"])
    assert result["processing"]["provider"] == "planetary-computer"
    assert result["processing"]["algorithm"].endswith("-v1")
    assert result["processing"]["zero_as_nodata"] is True
    # No measured value may leak signed URLs.
    assert "sig=" not in response.text
    assert result["warnings"] == []


def test_analysis_replayable_via_get(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())
    created = _analyze(client, session_id, scene_id).json()["results"][0]
    analysis_id = created["id"]

    fetched = client.get(f"/api/v1/agri/analyses/{analysis_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["id"] == analysis_id
    assert body["statistics"] == created["statistics"]
    assert body["classification"] == created["classification"]
    assert body["index"] == created["index"]
    assert body["processing"] == created["processing"]


def test_get_analysis_requires_access(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())
    analysis_id = _analyze(client, session_id, scene_id).json()["results"][0]["id"]

    register_user(client, "other@example.com", "other")
    response = client.get(f"/api/v1/agri/analyses/{analysis_id}")
    assert response.status_code == 404


def test_list_session_analyses(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())
    _analyze(client, session_id, scene_id)

    response = client.get(f"/api/v1/agri/sessions/{session_id}/analyses")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    listed = rows[0]
    assert listed["index_name"] == "ndvi"
    assert listed["scene_id"] == scene_id
    assert listed["overall_tier"] == "very_high"
    assert listed["mean_value"] == np.round(3700 / 5300, 6)


def test_list_session_analyses_requires_access(client, monkeypatch):
    session_id, _ = _discover(client, monkeypatch)
    register_user(client, "other@example.com", "other")
    response = client.get(f"/api/v1/agri/sessions/{session_id}/analyses")
    assert response.status_code == 404


def test_missing_scl_falls_back_to_unmasked_with_warning(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=None)
    response = _analyze(client, session_id, scene_id)  # mask_clouds defaults True
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["cloud"]["cloud_mask_available"] is False
    assert any("unmasked" in item for item in result["warnings"])


def test_mask_clouds_disabled_ignores_clouds(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    red, nir = dense_vegetation_scene()
    _seed_bands(scene_id, red, nir, scl=cloudy_scl())
    response = _analyze(client, session_id, scene_id, mask_clouds=False)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["cloud"]["mask_clouds"] is False
    assert result["statistics"]["valid_pixel_pct"] == 100.0


def _seed_bare_scene(client, monkeypatch) -> int:
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *dense_vegetation_scene(), scl=clear_scl())
    return scene_id
