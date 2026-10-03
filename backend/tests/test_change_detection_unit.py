"""Phase 6D unit tests: change classification, alignment, masking, pipeline.

The satellite download mock serves opaque bytes, so the change-detection
pipeline tests write synthetic GeoTIFF band files (see ``agri_mocks`` /
``aqua_mocks``) and feed them straight into ``compute_change_index`` — the same
aligned-observation pipeline the API service uses. Everything here is
deterministic math over honestly computed per-scene index arrays.
"""

from __future__ import annotations

import base64
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from agri_mocks import (
    UTM_CRS,
    cloudy_scl,
    dense_vegetation_scene,
    mixed_field_water_scene,
    write_band,
)
from aqua_mocks import land_scene, water_scene, write_aqua_bands
from rasterio.crs import CRS

from app.core.config import get_settings
from app.services.change_detection import (
    ChangeDetectionUnavailable,
    alignment,
    classification,
    compute_change_index,
    encoding,
)
from app.services.geospatial.indices import NDVI, NDWI

NDVI_ROLES = {"red": "B04", "nir": "B08", "cloud_mask": "SCL"}
NDWI_ROLES = {"green": "B03", "nir": "B08", "cloud_mask": "SCL"}
AOI = {
    "type": "Polygon",
    "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
}


def _grid(
    crs: str = "EPSG:32643",
    a: float = 10.0,
    e: float = -10.0,
    c: float = 100.0,
    f: float = 100.0,
    width: int = 40,
    height: int = 40,
) -> dict:
    return {
        "crs": crs,
        "transform": {"a": a, "b": 0.0, "c": c, "d": 0.0, "e": e, "f": f},
        "width": width,
        "height": height,
        "pixel_size_m": [abs(a), abs(e)],
    }


def _bottom_cloudy_scl(size: int = 40) -> np.ndarray:
    scl = np.full((size, size), 4, dtype=np.uint8)
    scl[size // 2 :, :] = 9  # cloud over the bottom half
    return scl


def _write_vegetation(
    directory: Path, red: np.ndarray, nir: np.ndarray, scl=None
) -> dict[str, str]:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "B04": write_band(directory / "B04.tif", red),
        "B08": write_band(directory / "B08.tif", nir),
    }
    if scl is not None:
        paths["SCL"] = write_band(directory / "SCL.tif", scl)
    return paths


def _scene(
    paths: dict[str, str],
    acquisitions: date,
    *,
    cloud_cover: float | None = 5.0,
) -> dict:
    """Build a `compute_change_index` scene input from {asset_key: path} files."""
    role_keys = NDWI_ROLES if "B03" in paths else NDVI_ROLES
    band_paths = {role: paths[key] for role, key in role_keys.items() if key in paths}
    band_retrievals = {role: idx for idx, role in enumerate(band_paths, start=1)}
    return {
        "role_keys": role_keys,
        "band_paths": band_paths,
        "band_retrievals": band_retrievals,
        "acquisition_date": acquisitions,
        "cloud_cover": cloud_cover,
        "provider": "planetary-computer",
        "platform": "sentinel-2a",
        "provider_scene_id": f"scene-{acquisitions.isoformat()}",
    }


# ---------------------------------------------------------------------------
# Pure classification math
# ---------------------------------------------------------------------------


def test_vegetation_change_classes_and_inclusive_boundary():
    nd_before = np.array([[0.5, 0.5], [0.25, 0.25]], dtype=np.float32)
    nd_after = np.array([[0.75, 0.25], [0.0, 0.5]], dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    result = classification.vegetation_change(nd_before, nd_after, valid, valid, 0.25)
    # delta = [0.25, -0.25, -0.25, 0.25]; exact ±threshold (inclusive) -> increase
    # for +0.25, decrease for -0.25.
    assert result["mask"].tolist() == [[1, 2], [2, 1]]
    assert result["threshold"] == 0.25
    assert result["valid"].all()


def test_vegetation_change_rejects_bad_threshold():
    nd_before = np.array([[0.5]], dtype=np.float32)
    nd_after = np.array([[0.8]], dtype=np.float32)
    valid = np.ones((1, 1), dtype=bool)
    for threshold in (0.0, -0.1, 2.5):
        with pytest.raises(ValueError):
            classification.vegetation_change(nd_before, nd_after, valid, valid, threshold)


def test_water_change_transitions_inclusive_threshold():
    ndwi_before = np.array([[0.3, -0.1], [0.0, -0.2]], dtype=np.float32)
    ndwi_after = np.array([[-0.2, 0.4], [0.0, 0.1]], dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    result = classification.water_change(ndwi_before, ndwi_after, valid, valid, 0.0)
    # before water: [T, F, T(0.0 inclusive), F] -> after water: [F, T, T, T]
    # transitions: lost, new, persistent, new.
    assert result["mask"].tolist() == [
        [classification.WATER_LOST, classification.WATER_NEW],
        [classification.WATER_PERSISTENT, classification.WATER_NEW],
    ]


def test_classification_invalid_pixels_are_never_change():
    nd_before = np.array([[0.8, 0.8], [0.0, 0.8]], dtype=np.float32)
    nd_after = np.array([[0.5, 0.8], [0.8, 0.8]], dtype=np.float32)
    valid = np.array([[True, True], [False, True]])
    result = classification.vegetation_change(nd_before, nd_after, valid, valid, 0.2)
    summary = classification.vegetation_summary(result, area_m2=100.0)
    assert summary["comparison_pixels"] == 3
    assert result["mask"][1, 0] == classification.INVALID_CLASS
    counts = sum(summary["classes"][name]["pixel_count"] for name in summary["classes"]["order"])
    assert counts == 3  # percentages add up to comparison-valid pixels only


def test_vegetation_summary_limits_area():
    result = {
        "valid": np.array([True, True, True, False], dtype=bool),
        "increase": np.array([True, False, False, False], dtype=bool),
        "decrease": np.array([False, True, False, False], dtype=bool),
        "stable": np.array([False, False, True, False], dtype=bool),
        "threshold": 0.1,
    }
    summary = classification.vegetation_summary(result, area_m2=25.0)
    assert summary["comparison_pixels"] == 3
    assert summary["classes"]["increase"]["pixel_count"] == 1
    assert summary["classes"]["increase"]["area_m2"] == pytest.approx(25.0)
    assert summary["classes"]["increase"]["pixel_pct"] == pytest.approx(100 / 3, rel=1e-4)
    assert summary["invalid_pixel_count"] == 1
    assert "documented threshold" in summary["limitations_note"]


def test_water_summary_extent_deltas():
    result = {
        "valid": np.array([True, True, True, True], dtype=bool),
        "before_water": np.array([True, True, False, False], dtype=bool),
        "after_water": np.array([True, False, True, True], dtype=bool),
        "new_water": np.array([False, False, True, True], dtype=bool),
        "lost_water": np.array([False, True, False, False], dtype=bool),
        "persistent": np.array([True, False, False, False], dtype=bool),
        "unchanged": np.array([False, False, False, False], dtype=bool),
        "threshold": 0.0,
    }
    summary = classification.water_summary(result, area_m2=10.0)
    assert summary["water_extent"]["before_pixels"] == 2
    assert summary["water_extent"]["after_pixels"] == 3
    assert summary["water_extent"]["delta_pixels"] == 1
    assert summary["classes"]["new"]["pixel_count"] == 2


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


def test_verify_alignment_identical_grids_is_none():
    grid = _grid()
    compatible, info = alignment.verify_alignment(grid, _grid())
    assert compatible is True
    assert info["mode"] == "none"
    assert info["resampled_with"] is None


def test_verify_alignment_offset_grids_resample_nearest():
    before = _grid(c=100.0, f=100.0)
    after = _grid(c=95.0, f=98.0)  # same pixel size, shifted origin
    compatible, info = alignment.verify_alignment(before, after)
    assert compatible is True
    assert info["mode"] == "nearest"
    assert info["resampled_with"] == "nearest"


def test_verify_alignment_crs_mismatch_incompatible():
    compatible, info = alignment.verify_alignment(_grid(crs="EPSG:32643"), _grid(crs="EPSG:32644"))
    assert compatible is False
    assert info["grid_before"]["crs"] == "EPSG:32643"
    assert info["grid_after"]["crs"] == "EPSG:32644"


def test_verify_alignment_resolution_mismatch_incompatible():
    compatible, _ = alignment.verify_alignment(_grid(a=10.0, e=-10.0), _grid(a=20.0, e=-20.0))
    assert compatible is False


def test_window_bounds_ll_around_mock_aoi():
    from pyproj import Transformer

    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
    easting, northing = transformer.transform(77.5, 13.0)  # AOI north-west corner
    bounds = alignment.window_bounds_ll(_grid(c=easting, f=northing))
    assert bounds["west"] < bounds["east"]
    assert bounds["south"] < bounds["north"]
    assert abs(bounds["west"] - 77.5) < 0.01
    assert abs(bounds["north"] - 13.0) < 0.01
    assert -180.0 < bounds["west"] < 180.0
    assert -90.0 < bounds["north"] < 90.0


# ---------------------------------------------------------------------------
# Mask encoding
# ---------------------------------------------------------------------------


def test_encode_mask_png_is_data_uri():
    mask = np.array([[0, 0], [1, 255]], dtype=np.uint8)
    uri = encoding.encode_mask_png(mask)
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert len(raw) > 0


# ---------------------------------------------------------------------------
# Full pipeline over synthetic GeoTIFFs
# ---------------------------------------------------------------------------


def test_vegetation_change_pipeline_decrease_and_stable():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_before_veg_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_after_veg_"))
    b_red, b_nir = dense_vegetation_scene()  # NDVI 0.698 everywhere
    a_red, a_nir = mixed_field_water_scene()  # top half water NDVI -0.333
    before = _scene(
        _write_vegetation(before_dir, b_red, b_nir, scl=np.full((40, 40), 4, np.uint8)),
        date(2024, 7, 5),
    )
    after = _scene(
        _write_vegetation(after_dir, a_red, a_nir, scl=np.full((40, 40), 4, np.uint8)),
        date(2024, 7, 20),
    )

    payload = compute_change_index(
        aoi_geojson=AOI,
        index=NDVI,
        change_type="vegetation",
        scene_before=before,
        scene_after=after,
        mask_clouds=True,
        settings=settings,
        change_threshold=0.10,
    )
    assert payload["status"] == "completed"
    assert payload["type"] == "vegetation"
    assert payload["comparison"]["alignment"]["mode"] == "none"
    masking = payload["comparison"]["masking"]
    assert masking["comparison_valid_pixels"] == 1600
    assert masking["comparison_valid_pct"] == 100.0
    classes = payload["classification"]["classes"]
    assert classes["decrease"]["pixel_count"] == 800
    assert classes["stable"]["pixel_count"] == 800
    assert classes["increase"]["pixel_count"] == 0
    assert payload["classification"]["threshold"] == pytest.approx(0.10)
    assert payload["classification"]["boundary"].startswith("increase = delta")
    assert payload["statistics"]["delta"]["mean"] == pytest.approx(-0.5157, abs=1e-3)
    assert payload["statistics"]["before"]["mean"] == pytest.approx(3700 / 5300, abs=1e-3)
    assert payload["mask"]["data_uri"].startswith("data:image/png;base64,")
    assert payload["mask"]["pixel_area_m2"] > 0
    assert payload["mask"]["bounds"]["west"] < payload["mask"]["bounds"]["east"]
    assert payload["cloud"]["before"]["cloud_mask_available"] is True
    assert payload["bands"][0]["scene"] == "before"
    assert {len(payload["bands"])} == {6}  # 3 roles x (before + after)


def test_vegetation_change_pipeline_increase_all():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_before_inc_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_after_inc_"))
    low = (np.full((40, 40), 800, np.uint16), np.full((40, 40), 3000, np.uint16))
    high = dense_vegetation_scene()
    before = _scene(_write_vegetation(before_dir, *low), date(2024, 7, 5))
    after = _scene(_write_vegetation(after_dir, *high), date(2024, 7, 20))
    payload = compute_change_index(
        aoi_geojson=AOI,
        index=NDVI,
        change_type="vegetation",
        scene_before=before,
        scene_after=after,
        mask_clouds=True,
        settings=settings,
        change_threshold=0.05,
    )
    # NDVI 2200/3800=0.579 -> 3700/5300=0.698; delta +0.119 > 0.05 -> increase.
    assert payload["classification"]["classes"]["increase"]["pixel_count"] == 1600
    assert payload["classification"]["classes"]["decrease"]["pixel_count"] == 0


def test_water_change_pipeline_lost_water():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_before_water_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_after_water_"))
    before_paths = write_aqua_bands(before_dir, *water_scene())  # NDWI ~0.548
    after_paths = write_aqua_bands(after_dir, *land_scene())  # NDWI -0.2
    payload = compute_change_index(
        aoi_geojson=AOI,
        index=NDWI,
        change_type="water",
        scene_before=_scene(before_paths, date(2024, 7, 5)),
        scene_after=_scene(after_paths, date(2024, 7, 20)),
        mask_clouds=False,
        settings=settings,
        change_threshold=0.0,
    )
    assert payload["status"] == "completed"
    classes = payload["classification"]["classes"]
    assert classes["lost"]["pixel_count"] == 1600
    assert classes["new"]["pixel_count"] == 0
    extent = payload["classification"]["water_extent"]
    assert extent["before_pixels"] == 1600
    assert extent["after_pixels"] == 0
    assert extent["delta_pixels"] == -1600
    assert payload["classification"]["boundary"] == "water = NDWI >= threshold (inclusive)"


def test_water_change_pipeline_new_water():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_before_land_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_after_water_"))
    before_paths = write_aqua_bands(before_dir, *land_scene())
    after_paths = write_aqua_bands(after_dir, *water_scene())
    payload = compute_change_index(
        aoi_geojson=AOI,
        index=NDWI,
        change_type="water",
        scene_before=_scene(before_paths, date(2024, 7, 5)),
        scene_after=_scene(after_paths, date(2024, 7, 20)),
        mask_clouds=False,
        settings=settings,
        change_threshold=0.0,
    )
    assert payload["classification"]["classes"]["new"]["pixel_count"] == 1600


def test_no_comparison_pixels_when_valid_regions_disjoint():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_disjoint_before_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_disjoint_after_"))
    # Before valid only over the bottom half; after valid only over the top half.
    before_paths = _write_vegetation(before_dir, *mixed_field_water_scene(), scl=cloudy_scl())
    after_paths = _write_vegetation(after_dir, *mixed_field_water_scene(), scl=_bottom_cloudy_scl())
    with pytest.raises(ChangeDetectionUnavailable) as excinfo:
        compute_change_index(
            aoi_geojson=AOI,
            index=NDVI,
            change_type="vegetation",
            scene_before=_scene(before_paths, date(2024, 7, 5)),
            scene_after=_scene(after_paths, date(2024, 7, 20)),
            mask_clouds=True,
            settings=settings,
            change_threshold=0.10,
        )
    assert excinfo.value.code == "no_valid_comparison_pixels"


def test_incompatible_raster_alignment_when_crs_differs():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_crs_before_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_crs_after_"))

    def _write_crs(directory: Path, crs: CRS) -> dict[str, str]:
        directory.mkdir(parents=True, exist_ok=True)
        red, nir = dense_vegetation_scene()
        return {
            "B04": write_band(directory / "B04.tif", red, crs=crs),
            "B08": write_band(directory / "B08.tif", nir, crs=crs),
        }

    before_paths = _write_crs(before_dir, UTM_CRS)
    after_paths = _write_crs(after_dir, CRS.from_epsg(32644))
    with pytest.raises(ChangeDetectionUnavailable) as excinfo:
        compute_change_index(
            aoi_geojson=AOI,
            index=NDVI,
            change_type="vegetation",
            scene_before=_scene(before_paths, date(2024, 7, 5)),
            scene_after=_scene(after_paths, date(2024, 7, 20)),
            mask_clouds=False,
            settings=settings,
            change_threshold=0.10,
        )
    assert excinfo.value.code == "incompatible_raster_alignment"


def test_insufficient_valid_pixels_propagates():
    settings = get_settings()
    before_dir = Path(tempfile.mkdtemp(prefix="cd_zero_before_"))
    after_dir = Path(tempfile.mkdtemp(prefix="cd_zero_after_"))
    zeros = (np.zeros((16, 16), dtype=np.uint16), np.zeros((16, 16), dtype=np.uint16))
    before_paths = _write_vegetation(before_dir, *zeros)
    after_paths = _write_vegetation(after_dir, *dense_vegetation_scene(size=16))
    with pytest.raises(ChangeDetectionUnavailable) as excinfo:
        compute_change_index(
            aoi_geojson=AOI,
            index=NDVI,
            change_type="vegetation",
            scene_before=_scene(before_paths, date(2024, 7, 5)),
            scene_after=_scene(after_paths, date(2024, 7, 20)),
            mask_clouds=False,
            settings=settings,
            change_threshold=0.10,
        )
    assert excinfo.value.code == "insufficient_valid_pixels"


def test_resample_nearest_aligns_offset_grids():
    values = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    before = _grid(width=2, height=2)
    after = _grid(c=99.0, f=99.0, width=2, height=2)
    aligned = alignment.resample_nearest(values, before, after, (2, 2))
    assert aligned.shape == (2, 2)
    assert np.all(np.isfinite(aligned))
