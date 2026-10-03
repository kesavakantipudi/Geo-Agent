"""Change-detection service (Phase 6D).

Session-scoped, provider-independent comparison of **two** satellite scenes the
actor can access over an analysis session's AOI. Both scenes must be discovered
by the analysis session and must be temporally ordered (before strictly earlier
than after). Required band assets must be present as completed retrievals;
otherwise the affected change type is reported as an explicit unavailable state.
Results are **derived on demand** — nothing is persisted — with per-type class
masks, area statistics, and full provenance.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import numpy
import rasterio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models import SatelliteScene, SatelliteSceneDiscovery
from app.schemas import change_detection as change_schemas
from app.services import (
    analysis_session_service,
    satellite_scene_service,
    weather_context_service,
)
from app.services.change_detection import (
    ChangeDetectionUnavailable,
    compute_change_index,
    unavailable_block,
)
from app.services.geometry import validate_geometry
from app.services.geospatial.bands import resolve_band_keys
from app.services.geospatial.indices import INDEX_REGISTRY, WATER_INDEX_REGISTRY

# change_type -> (index spec, required band roles)
_TYPE_INDEX: dict[str, tuple[Any, tuple[str, str]]] = {
    "vegetation": (INDEX_REGISTRY["ndvi"], ("red", "nir")),
    "water": (WATER_INDEX_REGISTRY["ndwi"], ("green", "nir")),
}

_SCENE_METADATA_KEYS = ("constellation", "instrument", "processing_level", "title")


def _scene_reference(scene: SatelliteScene) -> dict[str, Any]:
    metadata = scene.metadata_ or {}
    return {
        "id": scene.id,
        "scene_id": scene.scene_id,
        "provider": scene.provider,
        "platform": scene.platform,
        "acquisition_date": scene.acquisition_date,
        "cloud_cover": scene.cloud_cover,
        "metadata": {
            key: metadata[key] for key in _SCENE_METADATA_KEYS if metadata.get(key) is not None
        },
    }


def _check_scene_associated(db: Session, session_id: int, scene_id: int) -> None:
    discovery = db.execute(
        select(SatelliteSceneDiscovery).where(
            SatelliteSceneDiscovery.scene_id == scene_id,
            SatelliteSceneDiscovery.analysis_session_id == session_id,
        )
    ).scalar_one_or_none()
    if discovery is None:
        raise bad_request(
            "The scene is not associated with the analysis session.",
            code="scene_not_associated",
        )


def _provenance(settings) -> dict[str, Any]:
    return {
        "engine_version": settings.change_detection_engine_version,
        "derived_on_demand": True,
        "comparison_semantics": (
            "Pixel-by-pixel delta of a normalized-difference index between two "
            "observations over the comparison mask (pixels valid in both); "
            "invalid pixels are never classed as change."
        ),
        "invalid_is_change": False,
        "resampling": (
            "nearest-neighbour resampling of index values onto the before-grid; "
            "never between spectral bands"
        ),
        "area_method": "pixel count x projected pixel area (north-up grid)",
        "libraries": {"numpy": numpy.__version__, "rasterio": rasterio.__version__},
        "analyzed_at": datetime.now(UTC).isoformat(),
    }


def analyze(
    db: Session,
    actor_id: int,
    data: change_schemas.ChangeDetectionRequest,
) -> dict[str, Any]:
    """Compute change classifications for two scenes over a session AOI."""
    session = analysis_session_service.get(db, actor_id, data.analysis_session_id)
    before = satellite_scene_service.get_scene_orm(db, actor_id, data.before_scene_id)
    after = satellite_scene_service.get_scene_orm(db, actor_id, data.after_scene_id)
    session_id = session["id"]

    if before.id == after.id:
        raise bad_request(
            "Change detection requires two different scenes, one per observation.",
            code="same_scene",
        )
    _check_scene_associated(db, session_id, before.id)
    _check_scene_associated(db, session_id, after.id)
    if before.acquisition_date >= after.acquisition_date:
        raise bad_request(
            "The 'before' scene must be acquired strictly earlier than the "
            "'after' scene (temporal order cannot be established on the same day).",
            code="before_after_order",
        )

    aoi = data.aoi if data.aoi is not None else session.get("aoi")
    if aoi is None:
        raise bad_request("The analysis session has no AOI to analyze.", code="session_has_no_aoi")
    validate_geometry(aoi, name="aoi", require_area=True)

    if not data.types:
        raise bad_request(
            "Select at least one change type to analyze.", code="change_type_required"
        )
    unknown = [name for name in data.types if name not in change_schemas.SUPPORTED_CHANGE_TYPES]
    if unknown:
        raise bad_request(
            f"Unsupported change type(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(change_schemas.SUPPORTED_CHANGE_TYPES)}.",
            code="change_type_unsupported",
        )

    settings = get_settings()
    veg_threshold = data.vegetation_threshold
    if veg_threshold is None:
        veg_threshold = settings.change_vegetation_threshold
    if not (0.0 < veg_threshold <= 2.0):
        raise bad_request(
            f"Vegetation threshold must be within (0, 2], got {veg_threshold}.",
            code="invalid_vegetation_threshold",
        )
    water_threshold = data.water_threshold
    if water_threshold is None:
        water_threshold = settings.aqua_water_threshold
    if not (-1.0 <= water_threshold <= 1.0):
        raise bad_request(
            f"Water threshold must be within [-1, 1], got {water_threshold}.",
            code="invalid_water_threshold",
        )

    blocks: dict[str, dict[str, Any | None]] = {}
    for change_type in dict.fromkeys(data.types):
        blocks[change_type] = _compute_type(
            db,
            session_id,
            before,
            after,
            change_type=change_type,
            aoi_geojson=aoi,
            mask_clouds=data.mask_clouds,
            settings=settings,
            veg_threshold=veg_threshold,
            water_threshold=water_threshold,
        )

    weather_contexts = None
    if data.include_weather:
        weather_contexts = [
            weather_context_service.default_context(db, actor_id, session_id, before.id),
            weather_context_service.default_context(db, actor_id, session_id, after.id),
        ]

    completed_types = [
        change_type for change_type, block in blocks.items() if block["status"] == "completed"
    ]
    status = "completed" if completed_types else "unavailable"
    unavailable = None
    if not completed_types:
        unavailable = {
            "code": "all_requested_analyses_unavailable",
            "reason": "None of the requested change analyses could be completed.",
            "details": [
                f"{change_type}={block['unavailable']['code']}"
                for change_type, block in blocks.items()
                if block["status"] == "unavailable"
            ],
        }

    warnings: list[str] = []
    for block in blocks.values():
        for item in block.get("warnings") or []:
            if item not in warnings:
                warnings.append(item)

    db.commit()
    return {
        "status": status,
        "before": _scene_reference(before),
        "after": _scene_reference(after),
        "types_requested": list(dict.fromkeys(data.types)),
        "vegetation": blocks.get("vegetation"),
        "water": blocks.get("water"),
        "weather_contexts": weather_contexts,
        "provenance": _provenance(settings),
        "warnings": warnings,
        "unavailable": unavailable,
    }


def _compute_type(
    db: Session,
    session_id: int,
    before: SatelliteScene,
    after: SatelliteScene,
    *,
    change_type: str,
    aoi_geojson: dict,
    mask_clouds: bool,
    settings,
    veg_threshold: float,
    water_threshold: float,
) -> dict[str, Any]:
    index, required = _TYPE_INDEX[change_type]
    threshold = veg_threshold if change_type == "vegetation" else water_threshold

    role_keys_before = resolve_band_keys(before.provider, index.name)
    role_keys_after = resolve_band_keys(after.provider, index.name)
    if role_keys_before is None or role_keys_after is None:
        return unavailable_block(
            change_type,
            ChangeDetectionUnavailable(
                "provider_unsupported",
                "No band mapping is registered for one of the scenes' providers.",
                details=[
                    f"before_provider={before.provider}",
                    f"after_provider={after.provider}",
                    f"index={index.name}",
                ],
            ),
        )

    before_paths, before_ids, before_missing = satellite_scene_service.completed_retrieval_paths(
        db, before.id, [role_keys_before[role] for role in required]
    )
    after_paths, after_ids, after_missing = satellite_scene_service.completed_retrieval_paths(
        db, after.id, [role_keys_after[role] for role in required]
    )
    missing_scenes: list[str] = []
    for scene_label, missing in (
        ("before", before_missing),
        ("after", after_missing),
    ):
        if missing:
            missing_scenes.append(f"{scene_label}={','.join(sorted(missing))}")
    if missing_scenes:
        return unavailable_block(
            change_type,
            ChangeDetectionUnavailable(
                "bands_not_retrieved",
                "Band assets required for this change analysis have not been "
                "downloaded for one or both scenes.",
                details=missing_scenes + [f"index={index.name}"],
            ),
        )

    band_paths_before: dict[str, str] = {
        role: before_paths[role_keys_before[role]] for role in required
    }
    band_retrievals_before: dict[str, int] = {
        role: before_ids[role_keys_before[role]] for role in required
    }
    band_paths_after: dict[str, str] = {
        role: after_paths[role_keys_after[role]] for role in required
    }
    band_retrievals_after: dict[str, int] = {
        role: after_ids[role_keys_after[role]] for role in required
    }
    if mask_clouds:
        if "cloud_mask" in role_keys_before:
            scl_paths, scl_ids, scl_missing = satellite_scene_service.completed_retrieval_paths(
                db, before.id, [role_keys_before["cloud_mask"]]
            )
            if not scl_missing:
                band_paths_before["cloud_mask"] = scl_paths[role_keys_before["cloud_mask"]]
                band_retrievals_before["cloud_mask"] = scl_ids[role_keys_before["cloud_mask"]]
        if "cloud_mask" in role_keys_after:
            scl_paths, scl_ids, scl_missing = satellite_scene_service.completed_retrieval_paths(
                db, after.id, [role_keys_after["cloud_mask"]]
            )
            if not scl_missing:
                band_paths_after["cloud_mask"] = scl_paths[role_keys_after["cloud_mask"]]
                band_retrievals_after["cloud_mask"] = scl_ids[role_keys_after["cloud_mask"]]

    try:
        return compute_change_index(
            aoi_geojson=aoi_geojson,
            index=index,
            change_type=change_type,
            scene_before={
                "role_keys": role_keys_before,
                "band_paths": band_paths_before,
                "band_retrievals": band_retrievals_before,
                "acquisition_date": before.acquisition_date,
                "cloud_cover": before.cloud_cover,
                "provider": before.provider,
                "platform": before.platform,
                "provider_scene_id": before.scene_id,
            },
            scene_after={
                "role_keys": role_keys_after,
                "band_paths": band_paths_after,
                "band_retrievals": band_retrievals_after,
                "acquisition_date": after.acquisition_date,
                "cloud_cover": after.cloud_cover,
                "provider": after.provider,
                "platform": after.platform,
                "provider_scene_id": after.scene_id,
            },
            mask_clouds=mask_clouds,
            settings=settings,
            change_threshold=threshold,
        )
    except ChangeDetectionUnavailable as exc:
        return unavailable_block(change_type, exc)
