"""Phase 6B API tests: analysis auth, access control, unavailable states.

The satellite download mock serves opaque bytes, so these tests seed real
synthetic GeoTIFF band files (see ``aqua_mocks``) and completed retrieval rows
before calling the analysis endpoint — exactly the state a real completed
download would produce.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest
from agri_mocks import clear_scl, cloudy_scl, seed_retrieval
from aqua_mocks import water_scene, write_aqua_bands
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

AQUA_ASSETS = [
    ("visual", f"https://{BLOB_HOST}/container/aqua-visual.tif", "image/tiff"),
    ("B03", f"https://{BLOB_HOST}/container/aqua-B03.tif", "image/tiff"),
    ("B08", f"https://{BLOB_HOST}/container/aqua-B08.tif", "image/tiff"),
    ("SCL", f"https://{BLOB_HOST}/container/aqua-SCL.tif", "image/tiff"),
]


def _discover(client, monkeypatch) -> tuple[int, int]:
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler(mpc_items=[stac_item(assets=AQUA_ASSETS)]))
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    return session_id, search.json()["scenes"][0]["id"]


def _seed_bands(scene_id: int, green, nir, scl=None) -> None:
    directory = Path(tempfile.mkdtemp(prefix="aqua_api_"))
    paths = write_aqua_bands(directory, green, nir, scl=scl)
    for key, path in paths.items():
        seed_retrieval(scene_id, key, path)


def _analyze(client, session_id: int, scene_id: int, **overrides) -> dict:
    payload = {"analysis_session_id": session_id, "scene_id": scene_id}
    payload.update(overrides)
    return client.post("/api/v1/aqua/analyze", json=payload)


# ---------------------------------------------------------------------------
# Auth & validation
# ---------------------------------------------------------------------------


def test_analyze_requires_authentication(client):
    response = _analyze(client, 1, 1)
    assert response.status_code == 401


def test_analyze_unknown_session(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene(), scl=clear_scl())
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
    _seed_bands(scene_id, *water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, scene_id, indices=["ndvi"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aqua_index_unsupported"


def test_analyze_rejects_empty_indices(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    response = _analyze(client, session_id, scene_id, indices=[])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aqua_index_required"


def test_analyze_rejects_threshold_outside_range(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, scene_id, threshold=2.0)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_aqua_threshold"


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
    zeros = (np.zeros((16, 16), dtype=np.uint16), np.zeros((16, 16), dtype=np.uint16))
    _seed_bands(scene_id, *zeros)
    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "unavailable"
    assert result["unavailable"]["code"] == "insufficient_valid_pixels"


# ---------------------------------------------------------------------------
# Happy path: completed derived-on-demand analysis
# ---------------------------------------------------------------------------


def test_completed_analysis_and_provenance(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene(), scl=clear_scl())

    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert "id" not in result  # derived on demand; nothing persisted
    assert "created_at" not in result
    assert result["acquisition_date"] == "2024-07-05"
    assert result["scene"]["provider"] == "planetary-computer"
    assert result["index"]["name"] == "ndwi"
    assert result["index"]["formula"].startswith("NDWI")
    assert result["index"]["range"] == [-1.0, 1.0]
    assert result["statistics"]["valid_pixel_pct"] == 100.0
    assert result["statistics"]["mean"] == np.round(1700 / 3100, 6)
    assert result["classification"]["label"] == "Open water / non-water"
    assert result["classification"]["threshold"] == pytest.approx(0.0)
    assert result["classification"]["boundary"] == "water = NDWI >= threshold (inclusive)"
    assert "not a validated" in result["classification"]["threshold_source"]
    assert result["classification"]["water"]["pixel_pct"] == 100.0
    assert result["classification"]["water"]["pct_of_aoi_area"] == pytest.approx(100.0)
    assert result["classification"]["water"]["area_m2"] > 0
    assert (
        result["classification"]["water"]["pixel_count"] == result["statistics"]["aoi_pixel_count"]
    )
    assert result["classification"]["non_water"]["pixel_count"] == 0
    assert result["cloud"]["cloud_mask_available"] is True
    assert {band["role"] for band in result["bands"]} == {"green", "nir", "cloud_mask"}
    assert all(band["retrieval_id"] > 0 for band in result["bands"])
    assert result["processing"]["provider"] == "planetary-computer"
    assert result["processing"]["algorithm"].endswith("-v1")
    assert result["processing"]["zero_as_nodata"] is True
    assert "sig=" not in response.text
    assert result["warnings"] == []


def test_threshold_override_reflected_in_result(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene())  # NDWI ~0.548
    response = _analyze(client, session_id, scene_id, threshold=0.6)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["classification"]["threshold"] == 0.6
    assert result["classification"]["water"]["pixel_count"] == 0
    assert (
        result["classification"]["non_water"]["pixel_count"]
        == result["statistics"]["valid_pixel_count"]
    )


def test_missing_scl_falls_back_to_unmasked_with_warning(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene(), scl=None)
    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["cloud"]["cloud_mask_available"] is False
    assert any("unmasked" in item for item in result["warnings"])


def test_mask_clouds_disabled_ignores_clouds(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    green, nir = water_scene()
    _seed_bands(scene_id, green, nir, scl=cloudy_scl())
    response = _analyze(client, session_id, scene_id, mask_clouds=False)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "completed"
    assert result["cloud"]["mask_clouds"] is False
    assert result["statistics"]["valid_pixel_pct"] == 100.0


def test_derived_on_demand_creates_no_table(client, monkeypatch):
    session_id, scene_id = _discover(client, monkeypatch)
    _seed_bands(scene_id, *water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, scene_id)
    assert response.status_code == 200, response.text
    assert response.json()["results"][0]["status"] == "completed"

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        tables = (
            db.execute(text("select tablename from pg_tables where tablename like 'aqua_%'"))
            .scalars()
            .all()
        )
    assert tables == []
