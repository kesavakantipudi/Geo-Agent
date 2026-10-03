"""Agricultural intelligence service (Phase 6A).

Session-scoped, provider-independent analysis: an authenticated user analyses a
scene they can access (same access rule as satellite scenes) over an analysis
session's AOI. Required band assets must be present as completed satellite
retrievals; otherwise the response is an explicit unavailable state. Completed
results are persisted to ``agri_analyses`` with full provenance for later
timeline (6E) and change-detection (6D) use.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.models import AgriAnalysis, SatelliteScene
from app.schemas import agri as agri_schemas
from app.services import analysis_session_service, satellite_scene_service, weather_context_service
from app.services.agri import AgriUnavailable, bands, compute_agri_index
from app.services.agri.classification import HEURISTIC_NOTE
from app.services.agri.indices import INDEX_REGISTRY
from app.services.geometry import validate_geometry


def _scene_reference(scene: SatelliteScene) -> dict[str, Any]:
    return {
        "id": scene.id,
        "provider": scene.provider,
        "scene_id": scene.scene_id,
        "platform": scene.platform,
        "acquisition_date": scene.acquisition_date,
        "cloud_cover": scene.cloud_cover,
    }


def analyze(
    db: Session,
    actor_id: int,
    data: agri_schemas.AgriAnalyzeRequest,
) -> dict[str, Any]:
    """Compute the requested indices for a scene over a session AOI."""
    session = analysis_session_service.get(db, actor_id, data.analysis_session_id)
    scene = satellite_scene_service.get_scene_orm(db, actor_id, data.scene_id)

    aoi = data.aoi if data.aoi is not None else session.get("aoi")
    if aoi is None:
        raise bad_request("The analysis session has no AOI to analyze.", code="session_has_no_aoi")
    validate_geometry(aoi, name="aoi", require_area=True)

    if not data.indices:
        raise bad_request("Select at least one index to analyze.", code="agri_index_required")

    unknown = [name for name in data.indices if name not in INDEX_REGISTRY]
    if unknown:
        raise bad_request(
            f"Unsupported index name(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(INDEX_REGISTRY))}.",
            code="agri_index_unsupported",
        )

    results: list[dict[str, Any]] = []
    weather = weather_context_service.default_context(db, actor_id, session["id"], scene.id)
    for index_name in dict.fromkeys(data.indices):
        index = INDEX_REGISTRY[index_name]
        role_keys = bands.resolve_band_keys(scene.provider, index_name)
        if role_keys is None:
            result = _unavailable_result(
                scene,
                AgriUnavailable(
                    "provider_unsupported",
                    f"No band mapping is registered for provider '{scene.provider}'.",
                    details=[f"index={index_name}"],
                ),
            )
            result["weather_context"] = weather
            results.append(result)
            continue
        required = {"red", "nir"}
        retrieval_paths, retrieval_ids, missing = satellite_scene_service.completed_retrieval_paths(
            db, scene.id, [role_keys[role] for role in required]
        )
        if missing:
            result = _unavailable_result(
                scene,
                AgriUnavailable(
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
        # The Scene Classification Layer is optional: it enables cloud masking,
        # but a missing SCL retrieval degrades to an unmasked analysis with a
        # warning instead of failing the whole request.
        if data.mask_clouds and "cloud_mask" in role_keys:
            scl_paths, scl_ids, scl_missing = satellite_scene_service.completed_retrieval_paths(
                db, scene.id, [role_keys["cloud_mask"]]
            )
            if not scl_missing:
                band_paths["cloud_mask"] = scl_paths[role_keys["cloud_mask"]]
                band_retrieval_ids["cloud_mask"] = scl_ids[role_keys["cloud_mask"]]

        try:
            settings = get_settings()
            payload = compute_agri_index(
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
                settings=settings,
            )
        except AgriUnavailable as exc:
            result = _unavailable_result(scene, exc)
            result["weather_context"] = weather
            results.append(result)
            continue
        row = _persist_result(
            db,
            actor_id=actor_id,
            session_id=session["id"],
            scene=scene,
            index_name=index_name,
            payload=payload,
        )
        db.flush()
        payload["id"] = row.id
        payload["created_at"] = row.created_at
        payload["scene"] = _scene_reference(scene)
        payload["acquisition_date"] = scene.acquisition_date
        payload["weather_context"] = weather
        results.append(payload)

    db.commit()
    return {"results": results}


def get_analysis(db: Session, actor_id: int, analysis_id: int) -> dict[str, Any]:
    """Authorized single completed analysis."""
    row = db.get(AgriAnalysis, analysis_id)
    if row is None:
        raise not_found("Agricultural analysis not found.", code="agri_analysis_not_found")
    analysis_session_service.get(db, actor_id, row.analysis_session_id)
    scene = db.get(SatelliteScene, row.scene_id)
    result = _result_from_row(row, _scene_reference(scene) if scene else None)
    if scene is not None:
        result["weather_context"] = weather_context_service.default_context(
            db, actor_id, row.analysis_session_id, scene.id
        )
    return result


def list_analyses_for_session(
    db: Session, actor_id: int, analysis_session_id: int
) -> list[dict[str, Any]]:
    """Authorized list of completed analyses for a session (newest first)."""
    analysis_session_service.get(db, actor_id, analysis_session_id)
    rows = (
        db.execute(
            select(AgriAnalysis)
            .where(AgriAnalysis.analysis_session_id == analysis_session_id)
            .order_by(AgriAnalysis.acquisition_date.desc(), AgriAnalysis.id.desc())
        )
        .scalars()
        .all()
    )
    scenes_by_id = {
        scene.id: scene
        for scene in db.execute(
            select(SatelliteScene).where(SatelliteScene.id.in_({row.scene_id for row in rows}))
        ).scalars()
    }
    return [_summary_from_row(row, scenes_by_id.get(row.scene_id)) for row in rows]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _persist_result(
    db: Session,
    actor_id: int,
    session_id: int,
    scene: SatelliteScene,
    index_name: str,
    payload: dict[str, Any],
) -> AgriAnalysis:
    statistics = payload["statistics"]
    classification = payload["classification"]
    row = AgriAnalysis(
        analysis_session_id=session_id,
        scene_id=scene.id,
        requested_by=actor_id,
        index_name=index_name,
        acquisition_date=scene.acquisition_date,
        cloud_cover=scene.cloud_cover,
        min_value=statistics["min"],
        max_value=statistics["max"],
        mean_value=statistics["mean"],
        median_value=statistics["median"],
        stddev_value=statistics["stddev"],
        valid_pixel_pct=statistics["valid_pixel_pct"],
        pixel_count=statistics["valid_pixel_count"],
        overall_tier=classification["overall"]["tier"],
        dominant_tier=classification["dominant_tier"]["tier"],
        statistics=statistics,
        band_assets={
            band["role"]: {
                "asset_key": band["asset_key"],
                "retrieval_id": band["retrieval_id"],
            }
            for band in payload["bands"]
        },
        thresholds=classification["tiers"],
        index_info=payload["index"],
        processing=payload["processing"],
        warnings=payload["warnings"] or None,
    )
    db.add(row)
    return row


def _result_from_row(row: AgriAnalysis, scene_ref: dict[str, Any] | None) -> dict[str, Any]:
    """Rebuild a POST-shaped result from a persisted row (JSONB snapshots)."""
    return {
        "id": row.id,
        "status": "completed",
        "scene": scene_ref if scene_ref else {"id": row.scene_id},
        "index": row.index_info,
        "acquisition_date": row.acquisition_date,
        "cloud": {
            "mask_clouds": bool(row.processing.get("mask_clouds")),
            "cloud_mask_available": bool(row.processing.get("cloud_mask_available")),
            "masked_classes": list(row.processing.get("scl_masked_classes", [])),
        },
        "statistics": row.statistics,
        "classification": {
            "overall": {
                "tier": row.overall_tier,
                "label": _tier_label(row.overall_tier),
                "basis": "Mean NDVI of valid pixels.",
            },
            "dominant_tier": {
                "tier": row.dominant_tier,
                "label": _tier_label(row.dominant_tier),
                "pixel_pct": _tier_share(row.thresholds, row.dominant_tier),
            },
            "tiers": row.thresholds,
            "threshold_source": HEURISTIC_NOTE,
        },
        "bands": [
            {
                "role": band_assets["role"],
                "asset_key": band_assets["asset_key"],
                "retrieval_id": band_assets["retrieval_id"],
            }
            for band_assets in _band_assets_list(row.band_assets)
        ]
        if row.band_assets
        else [],
        "processing": row.processing,
        "warnings": list(row.warnings or []),
        "unavailable": None,
        "created_at": row.created_at,
    }


def _band_assets_list(band_assets: dict) -> list[dict]:
    return [
        {"role": role, "asset_key": info["asset_key"], "retrieval_id": info["retrieval_id"]}
        for role, info in sorted(band_assets.items())
        if isinstance(info, dict)
    ]


def _tier_label(tier: str | None) -> str | None:
    if tier is None:
        return None
    for item in _tier_definitions_for_label():
        if item.get("tier") == tier:
            return item.get("label")
    return tier


def _tier_share(thresholds: list | None, tier: str | None) -> float:
    for item in thresholds or []:
        if item.get("tier") == tier:
            return float(item.get("pixel_pct") or 0.0)
    return 0.0


def _tier_definitions_for_label() -> list[dict]:
    from app.services.agri import classification

    return [dict(item) for item in classification.NDVI_TIER_DEFINITIONS]


def _unavailable_result(scene: SatelliteScene, exc: AgriUnavailable) -> dict[str, Any]:
    return {
        "id": None,
        "status": "unavailable",
        "scene": _scene_reference(scene),
        "index": None,
        "acquisition_date": scene.acquisition_date,
        "cloud": None,
        "statistics": None,
        "classification": None,
        "bands": None,
        "processing": None,
        "warnings": [],
        "unavailable": {
            "code": exc.code,
            "reason": exc.reason,
            "details": list(exc.details),
        },
        "created_at": None,
    }


def _summary_from_row(row: AgriAnalysis, scene: SatelliteScene | None) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": "completed",
        "index_name": row.index_name,
        "acquisition_date": row.acquisition_date,
        "scene_id": row.scene_id,
        "provider": scene.provider if scene else None,
        "platform": scene.platform if scene else None,
        "cloud_cover": row.cloud_cover,
        "overall_tier": row.overall_tier,
        "dominant_tier": row.dominant_tier,
        "mean_value": row.mean_value,
        "valid_pixel_pct": row.valid_pixel_pct,
        "created_at": row.created_at,
    }
