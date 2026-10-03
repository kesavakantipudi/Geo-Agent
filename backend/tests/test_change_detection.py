"""Phase 6D API tests: change-detection auth, access, order, unavailable states.

The satellite download mock serves opaque bytes, so these tests seed real
synthetic GeoTIFF band files (see ``agri_mocks`` / ``aqua_mocks``) and completed
retrieval rows for **two** scenes before calling the analysis endpoint — exactly
the state real completed downloads would produce.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from agri_mocks import (
    clear_scl,
    cloudy_scl,
    dense_vegetation_scene,
    mixed_field_water_scene,
    seed_retrieval,
    write_scene_bands,
)
from aqua_mocks import land_scene, water_scene, write_aqua_bands
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

CHANGE_ASSETS = [
    ("visual", f"https://{BLOB_HOST}/container/change-visual.tif", "image/tiff"),
    ("B03", f"https://{BLOB_HOST}/container/change-B03.tif", "image/tiff"),
    ("B04", f"https://{BLOB_HOST}/container/change-B04.tif", "image/tiff"),
    ("B08", f"https://{BLOB_HOST}/container/change-B08.tif", "image/tiff"),
    ("SCL", f"https://{BLOB_HOST}/container/change-SCL.tif", "image/tiff"),
]

BEFORE_ITEM = stac_item(
    scene_id="S2A_T43PFJ_20240705T040000", datetime="2024-07-05T04:00:00Z", assets=CHANGE_ASSETS
)
AFTER_ITEM = stac_item(
    scene_id="S2A_T43PFJ_20240720T040000", datetime="2024-07-20T04:00:00Z", assets=CHANGE_ASSETS
)


def _discover_pair(client, monkeypatch) -> tuple[int, dict[str, int]]:
    register(client, "owner@example.com")
    install_client_mock(monkeypatch, route_handler(mpc_items=[BEFORE_ITEM, AFTER_ITEM]))
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    assert search.status_code == 200, search.text
    scenes = search.json()["scenes"]
    ids = {}
    for scene in scenes:
        if "20240705" in scene["scene_id"]:
            ids["before"] = scene["id"]
        elif "20240720" in scene["scene_id"]:
            ids["after"] = scene["id"]
    assert {"before", "after"} <= set(ids), scenes
    return session_id, ids


def _seed_vegetation(scene_id: int, red, nir, scl=None) -> None:
    directory = Path(tempfile.mkdtemp(prefix="cd_api_veg_"))
    paths = write_scene_bands(directory, red, nir, scl=scl)
    for key, path in paths.items():
        seed_retrieval(scene_id, key, path)


def _seed_water(scene_id: int, green, nir, scl=None) -> None:
    directory = Path(tempfile.mkdtemp(prefix="cd_api_water_"))
    paths = write_aqua_bands(directory, green, nir, scl=scl)
    for key, path in paths.items():
        seed_retrieval(scene_id, key, path)


def _analyze(client, session_id: int, ids: dict[str, int], **overrides) -> dict:
    payload = {
        "analysis_session_id": session_id,
        "before_scene_id": ids["before"],
        "after_scene_id": ids["after"],
    }
    payload.update(overrides)
    return client.post("/api/v1/change-detection/analyze", json=payload)


# ---------------------------------------------------------------------------
# Auth & basic validation
# ---------------------------------------------------------------------------


def test_analyze_requires_authentication(client):
    response = _analyze(client, 1, {"before": 1, "after": 2})
    assert response.status_code == 401


def test_analyze_unknown_session(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene())
    _seed_vegetation(ids["after"], *dense_vegetation_scene())
    response = _analyze(client, 999_999, ids)
    assert response.status_code == 404


def test_analyze_unknown_before_scene(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, {"before": 999_999, "after": ids["after"]})
    assert response.status_code == 404


def test_analyze_unknown_after_scene(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, {"before": ids["before"], "after": 999_999})
    assert response.status_code == 404


def test_analyze_requires_cross_user_access(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    register_user(client, "rival@example.com", "rival")
    rival_session = create_session(client)
    response = _analyze(client, rival_session, ids)
    assert response.status_code == 404


def test_scene_not_associated_with_session(client, monkeypatch):
    _, ids = _discover_pair(client, monkeypatch)
    other_session = create_session(client)  # same user, different session
    response = _analyze(client, other_session, ids)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scene_not_associated"


# ---------------------------------------------------------------------------
# Scene selection & temporal order
# ---------------------------------------------------------------------------


def test_rejects_same_scene(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, {"before": ids["before"], "after": ids["before"]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "same_scene"


def test_rejects_same_day_scenes(client, monkeypatch):
    register(client, "owner@example.com")
    install_client_mock(
        monkeypatch,
        route_handler(
            mpc_items=[
                stac_item(
                    scene_id="S2A_T43PFJ_20240705T040000",
                    datetime="2024-07-05T04:00:00Z",
                    assets=CHANGE_ASSETS,
                ),
                stac_item(
                    scene_id="S2B_T43PFJ_20240705T044000",
                    datetime="2024-07-05T04:40:00Z",
                    assets=CHANGE_ASSETS,
                ),
            ]
        ),
    )
    session_id = create_session(client)
    search = client.post(
        "/api/v1/satellite/scenes/search", json={"analysis_session_id": session_id}
    )
    scenes = search.json()["scenes"]
    assert len(scenes) == 2
    response = _analyze(client, session_id, {"before": scenes[1]["id"], "after": scenes[0]["id"]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "before_after_order"


def test_rejects_reversed_order(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, {"before": ids["after"], "after": ids["before"]})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "before_after_order"


# ---------------------------------------------------------------------------
# Type & threshold validation
# ---------------------------------------------------------------------------


def test_rejects_empty_types(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, ids, types=[])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "change_type_required"


def test_rejects_unsupported_type(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, ids, types=["soil"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "change_type_unsupported"


def test_rejects_invalid_vegetation_threshold(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    for threshold in (0.0, 2.5):
        response = _analyze(
            client, session_id, ids, types=["vegetation"], vegetation_threshold=threshold
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_vegetation_threshold"


def test_rejects_invalid_water_threshold(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    for threshold in (-1.5, 1.5):
        response = _analyze(client, session_id, ids, types=["water"], water_threshold=threshold)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_water_threshold"


# ---------------------------------------------------------------------------
# Unavailable states (explicit, never fabricated)
# ---------------------------------------------------------------------------


def test_unavailable_when_bands_not_retrieved(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    response = _analyze(client, session_id, ids, types=["vegetation"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unavailable"
    block = body["vegetation"]
    assert block["status"] == "unavailable"
    assert block["unavailable"]["code"] == "bands_not_retrieved"
    assert "before=" in block["unavailable"]["details"][0]
    assert body["unavailable"]["code"] == "all_requested_analyses_unavailable"


def test_partial_unavailable_keeps_top_level_completed(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=clear_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, ids, types=["vegetation", "water"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["vegetation"]["status"] == "completed"
    assert body["water"]["status"] == "unavailable"
    assert body["water"]["unavailable"]["code"] == "bands_not_retrieved"
    assert body["unavailable"] is None


# ---------------------------------------------------------------------------
# Happy path: completed derived-on-demand change analysis
# ---------------------------------------------------------------------------


def test_completed_vegetation_change_and_provenance(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=clear_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=clear_scl())

    response = _analyze(client, session_id, ids, types=["vegetation"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert "id" not in body  # derived on demand; nothing persisted
    assert "created_at" not in body
    assert body["before"]["acquisition_date"] == "2024-07-05"
    assert body["after"]["acquisition_date"] == "2024-07-20"
    assert body["before"]["scene_id"].endswith("20240705T040000")
    assert body["before"]["metadata"]["constellation"] == "sentinel-2"
    block = body["vegetation"]
    assert block["status"] == "completed"
    assert block["index"]["name"] == "ndvi"
    assert block["index"]["formula"].startswith("NDVI")
    assert block["comparison"]["alignment"]["mode"] in {"none", "nearest"}
    assert block["comparison"]["masking"]["comparison_valid_pixels"] == 1600
    assert block["classification"]["classes"]["decrease"]["pixel_count"] == 800
    assert block["classification"]["classes"]["stable"]["pixel_count"] == 800
    assert block["classification"]["threshold"] == pytest.approx(0.10)
    assert block["mask"]["data_uri"].startswith("data:image/png;base64,")
    assert set(block["mask"]["bounds"]) == {"west", "south", "east", "north"}
    assert any(band["scene"] == "before" for band in block["bands"])
    assert any(band["role"] == "cloud_mask" for band in block["bands"])
    assert body["provenance"]["engine_version"].startswith("geoagent-change-detection")
    assert body["provenance"]["derived_on_demand"] is True
    assert body["provenance"]["invalid_is_change"] is False
    assert len(body["weather_contexts"]) == 2
    assert body["weather_contexts"][0]["scene"]["acquisition_date"] == "2024-07-05"
    assert "sig=" not in response.text


def test_include_weather_false_omits_contexts(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=clear_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, ids, types=["vegetation"], include_weather=False)
    assert response.status_code == 200, response.text
    assert response.json()["weather_contexts"] is None


def test_completed_water_change_both_types(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=clear_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=clear_scl())
    _seed_water(ids["before"], *water_scene())
    _seed_water(ids["after"], *land_scene())

    response = _analyze(client, session_id, ids, types=["vegetation", "water"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    water = body["water"]
    assert water["status"] == "completed"
    assert water["classification"]["boundary"] == "water = NDWI >= threshold (inclusive)"
    assert water["classification"]["classes"]["lost"]["pixel_count"] == 1600
    assert water["classification"]["water_extent"]["delta_pixels"] == -1600
    assert water["statistics"]["delta"] is None
    assert water["mask"]["classes"]["3"] == "persistent water"


def test_mask_clouds_false_ignores_clouds(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=cloudy_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=cloudy_scl())
    response = _analyze(client, session_id, ids, types=["vegetation"], mask_clouds=False)
    assert response.status_code == 200, response.text
    block = response.json()["vegetation"]
    assert block["status"] == "completed"
    assert block["cloud"]["mask_clouds"] is False
    assert block["comparison"]["masking"]["comparison_valid_pixels"] == 1600


def test_missing_scl_falls_back_with_warning(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene())
    _seed_vegetation(ids["after"], *mixed_field_water_scene())
    response = _analyze(client, session_id, ids, types=["vegetation"])
    assert response.status_code == 200, response.text
    block = response.json()["vegetation"]
    assert block["status"] == "completed"
    assert block["cloud"]["before"]["cloud_mask_available"] is False
    assert any("unmasked" in item for item in block["warnings"])


def test_derived_on_demand_creates_no_change_tables(client, monkeypatch):
    session_id, ids = _discover_pair(client, monkeypatch)
    _seed_vegetation(ids["before"], *dense_vegetation_scene(), scl=clear_scl())
    _seed_vegetation(ids["after"], *mixed_field_water_scene(), scl=clear_scl())
    response = _analyze(client, session_id, ids, types=["vegetation", "water"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"

    from app.db.session import SessionLocal

    with SessionLocal() as db:
        tables = (
            db.execute(text("select tablename from pg_tables where tablename like 'change%'"))
            .scalars()
            .all()
        )
    assert tables == []
