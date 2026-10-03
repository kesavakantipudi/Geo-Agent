"""Water intelligence service (Phase 6B).

Session-scoped, provider-independent analysis that mirrors agricultural
intelligence: an authenticated user analyses a scene they can access (same access
rule as satellite scenes) over an analysis session's AOI. Required band assets
must be present as completed satellite retrievals; otherwise the response is an
explicit unavailable state. NDWI results are **derived on demand** — nothing is
persisted — with full provenance so the analysis is reproducible.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models import SatelliteScene
from app.schemas import aqua as aqua_schemas
from app.services import (
    analysis_session_service,
    satellite_scene_service,
    weather_context_service,
)
from app.services.aqua import AquaUnavailable, compute_aqua_index
from app.services.geometry import validate_geometry
from app.services.geospatial.bands import resolve_band_keys
from app.services.geospatial.indices import WATER_INDEX_REGISTRY


def _scene_reference(scene: SatelliteScene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "provider": scene.provider,
        "scene_id": scene.scene_id,
        "platform": scene.platform,
        "acquisition_date": scene.acquisition_date,
        "cloud_cover": scene.cloud_cover,
    }


def _unavailable_result(scene: SatelliteScene, exc: AquaUnavailable) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "scene": _scene_reference(scene),
        "unavailable": {
            "code": exc.code,
            "reason": exc.reason,
            "details": exc.details or [],
        },
        "warnings": [],
    }


def analyze(
    db: Session,
    actor_id: int,
    data: aqua_schemas.AquaAnalyzeRequest,
) -> dict[str, Any]:
    """Compute NDWI water analysis for a scene over a session AOI."""
    session = analysis_session_service.get(db, actor_id, data.analysis_session_id)
    scene = satellite_scene_service.get_scene_orm(db, actor_id, data.scene_id)

    aoi = data.aoi if data.aoi is not None else session.get("aoi")
    if aoi is None:
        raise bad_request("The analysis session has no AOI to analyze.", code="session_has_no_aoi")
    validate_geometry(aoi, name="aoi", require_area=True)

    if not data.indices:
        raise bad_request("Select at least one index to analyze.", code="aqua_index_required")

    unknown = [name for name in data.indices if name not in WATER_INDEX_REGISTRY]
    if unknown:
        raise bad_request(
            f"Unsupported index name(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(WATER_INDEX_REGISTRY))}.",
            code="aqua_index_unsupported",
        )

    threshold = data.threshold
    if threshold is None:
        threshold = get_settings().aqua_water_threshold
    if not (-1.0 <= threshold <= 1.0):
        raise bad_request(
            f"Water threshold must be within [-1, 1], got {threshold}.",
            code="invalid_aqua_threshold",
        )

    results: list[dict[str, Any]] = []
    weather = weather_context_service.default_context(db, actor_id, session["id"], scene.id)
    for index_name in dict.fromkeys(data.indices):
        index = WATER_INDEX_REGISTRY[index_name]
        role_keys = resolve_band_keys(scene.provider, index_name)
        if role_keys is None:
            result = _unavailable_result(
                scene,
                AquaUnavailable(
                    "provider_unsupported",
                    f"No band mapping is registered for provider '{scene.provider}'.",
                    details=[f"index={index_name}"],
                ),
            )
            result["weather_context"] = weather
            results.append(result)
            continue
        required = {"green", "nir"}
        retrieval_paths, retrieval_ids, missing = satellite_scene_service.completed_retrieval_paths(
            db, scene.id, [role_keys[role] for role in required]
        )
        if missing:
            result = _unavailable_result(
                scene,
                AquaUnavailable(
                    "bands_not_retrieved",
                    "The band assets required for this analysis have not been "
                    "downloaded for this scene.",
                    details=[f"missing_assets={','.join(sorted(missing))}"],
                ),
            )
            result["weather_context"] = weather
            results.append(result)
            continue

        band_paths = {role: retrieval_paths[role_keys[role]] for role in required}
        band_retrieval_ids = {role: retrieval_ids[role_keys[role]] for role in required}
        if data.mask_clouds and "cloud_mask" in role_keys:
            scl_paths, scl_ids, scl_missing = satellite_scene_service.completed_retrieval_paths(
                db, scene.id, [role_keys["cloud_mask"]]
            )
            if not scl_missing:
                band_paths["cloud_mask"] = scl_paths[role_keys["cloud_mask"]]
                band_retrieval_ids["cloud_mask"] = scl_ids[role_keys["cloud_mask"]]

        try:
            settings = get_settings()
            payload = compute_aqua_index(
                aoi_geojson=aoi,
                index=index,
                band_paths=band_paths,
                band_retrievals=band_retrieval_ids,
                acquisition_date=scene.acquisition_date,
                cloud_cover=scene.cloud_cover,
                provider=scene.provider,
                platform=scene.platform,
                provider_scene_id=scene.scene_id,
                mask_clouds=data.mask_clouds,
                threshold=threshold,
                settings=settings,
            )
        except AquaUnavailable as exc:
            result = _unavailable_result(scene, exc)
            result["weather_context"] = weather
            results.append(result)
            continue

        payload["scene"] = _scene_reference(scene)
        payload["acquisition_date"] = scene.acquisition_date
        payload["weather_context"] = weather
        results.append(payload)

    db.commit()
    return {"results": results}
