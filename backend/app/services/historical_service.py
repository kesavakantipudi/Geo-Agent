"""Historical intelligence service (Phase 6E).

Session-scoped, provider-independent **timeline** over the analysis session's
discovered scenes, derived on demand (nothing is persisted):

1. The session (its AOI, access rules, and date range) is authoritative;
   an optional per-request date override must stay inside the session range.
2. Observations are ordered by acquisition date (oldest → newest) — never by
   ingestion/retrieval order — deduplicated by scene, and filtered to the date
   range; the resulting ``coverage`` (count, span, gaps) is always explicit,
   including zero/one/sparse scenes.
3. Each observation is analyzed per requested type by reusing the **shared
   geospatial index core** (the same functions behind Agri and Aqua): NDVI for
   vegetation and NDWI for water (with the documented water boundary). A scene
   that cannot be analyzed is reported as an explicit unavailable node — a
   missing value is never coerced to zero.
4. Consecutive observations are compared per type by reusing the **Phase 6D
   change-detection engine**, yielding deterministic, evidence-based events
   (dominant vegetation change; new/lost/persistent water extent). Weather is
   attached purely as descriptive context (never causal).
5. Trends are descriptive (first/latest/min/max + change) with the observation
   count that actually supports them.

Every reason for a gap in the timeline is preserved in the response rather than
fabricated away.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import numpy
import rasterio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models import SatelliteScene
from app.schemas import historical as historical_schemas
from app.services import (
    analysis_session_service,
    satellite_scene_service,
    weather_context_service,
)
from app.services.aqua.classification import water_summary as aqua_water_summary
from app.services.change_detection import (
    ChangeDetectionUnavailable,
    compute_change_index,
)
from app.services.geometry import validate_geometry
from app.services.geospatial.analysis import IndexAnalysisUnavailable, analyze_index_ratio
from app.services.geospatial.bands import resolve_band_keys
from app.services.geospatial.indices import INDEX_REGISTRY, WATER_INDEX_REGISTRY

# history type -> (index spec, required band roles); mirrors change detection.
_TYPE_INDEX: dict[str, tuple[Any, tuple[str, str]]] = {
    "vegetation": (INDEX_REGISTRY["ndvi"], ("red", "nir")),
    "water": (WATER_INDEX_REGISTRY["ndwi"], ("green", "nir")),
}

_SCENE_METADATA_KEYS = ("constellation", "instrument", "processing_level", "title")

_ORDERING_SEMANTICS = (
    "Observations are ordered by acquisition date (oldest → newest); the date is "
    "parsed from each scene's STAC datetime, never from ingestion or retrieval "
    "order. Irregular temporal gaps are reported, never interpolated."
)

_CHANGE_REUSE = (
    "Per-observation indices reuse the shared geospatial index core (agri/aqua "
    "semantics); events between consecutive observations reuse the Phase 6D "
    "change-detection engine."
)

_TREND_NOTE = (
    "Descriptive statistics over measured observations only; missing observations "
    "are never estimated, irregular intervals are never interpolated, and no "
    "seasonal or causal claims are made."
)


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


def _unavailable(code: str, reason: str, details: list[str] | None = None) -> dict[str, Any]:
    return {"code": code, "reason": reason, "details": list(details or [])}


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def order_observations(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by scene id and order oldest → newest by acquisition date.

    Discovery is already unique per session, but the ordering is defense-in-depth:
    ties on acquisition date are broken by scene id for determinism.
    """
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for scene in scenes:
        if scene["id"] in seen:
            continue
        seen.add(scene["id"])
        unique.append(scene)
    return sorted(unique, key=lambda scene: (scene["acquisition_date"], scene["id"]))


def temporal_gaps(dates: list[date]) -> tuple[list[dict[str, Any]], int]:
    """Gaps between consecutive observations and the number of same-day pairs.

    Only pairs with strictly increasing dates can be compared; pairs that share
    an acquisition date are counted separately (``same_day_pairs``) and are never
    reported as a temporal gap.
    """
    gaps: list[dict[str, Any]] = []
    same_day_pairs = 0
    for previous, current in zip(dates, dates[1:], strict=False):
        if current == previous:
            same_day_pairs += 1
            continue
        gap_days = (current - previous).days
        if gap_days > 1:
            gaps.append({"from_date": previous, "to_date": current, "gap_days": gap_days})
    return gaps, same_day_pairs


def trend_basis(count: int, same_date: bool) -> str:
    """Deterministic descriptive basis for a trend, capped to the evidence."""
    if count == 0:
        return "No completed observations are available for this history type."
    if count == 1:
        return "Single observation; no change computed."
    if same_date:
        return "All observations share a single acquisition date; no temporal change computed."
    if count == 2:
        return "Observed change between two observations."
    return f"Trend across {count} observations."


def classify_vegetation_event(classification: dict[str, Any]) -> tuple[str, str, str]:
    """Dominant vegetation change over pixels valid in both observations."""
    increase = classification["classes"]["increase"]["pixel_count"]
    decrease = classification["classes"]["decrease"]["pixel_count"]
    if decrease > increase:
        event = "vegetation_decrease"
        label = "Vegetation index decreased over most compared pixels"
    elif increase > decrease:
        event = "vegetation_increase"
        label = "Vegetation index increased over most compared pixels"
    else:
        event = "vegetation_stable"
        label = "No dominant vegetation index change between the observations"
    basis = (
        "Dominant class among pixels valid in both observations: increase if the "
        "increased area exceeds the decreased area, otherwise decrease if the "
        "decreased area exceeds the increased area, otherwise stable."
    )
    return event, label, basis


def classify_water_event(classification: dict[str, Any]) -> tuple[str, str, str]:
    """Net water-extent balance over pixels valid in both observations."""
    new = classification["classes"]["new"]["pixel_count"]
    lost = classification["classes"]["lost"]["pixel_count"]
    if new > lost:
        event = "water_expansion"
        label = "Water extent increased between the observations"
    elif lost > new:
        event = "water_reduction"
        label = "Water extent decreased between the observations"
    else:
        event = "water_stable"
        label = "No net water-extent change between the observations"
    basis = (
        "Net water-extent balance over pixels valid in both observations (water = "
        "NDWI >= threshold on each date, matching the Phase 6B Aqua boundary)."
    )
    return event, label, basis


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def analyze(
    db: Session,
    actor_id: int,
    data: historical_schemas.HistoricalRequest,
) -> dict[str, Any]:
    """Build a derived-on-demand historical timeline for a session's scenes."""
    session = analysis_session_service.get(db, actor_id, data.analysis_session_id)
    session_id = session["id"]

    aoi = session.get("aoi")
    if aoi is None:
        raise bad_request("The analysis session has no AOI to analyze.", code="session_has_no_aoi")
    validate_geometry(aoi, name="aoi", require_area=True)

    if not data.types:
        raise bad_request(
            "Select at least one history type to analyze.", code="historical_type_required"
        )
    unknown = [
        name for name in data.types if name not in historical_schemas.SUPPORTED_HISTORICAL_TYPES
    ]
    if unknown:
        raise bad_request(
            f"Unsupported history type(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(historical_schemas.SUPPORTED_HISTORICAL_TYPES)}.",
            code="historical_type_unsupported",
        )
    types = list(dict.fromkeys(data.types))

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

    effective_start, effective_end = _resolve_date_range(session, data)
    scene_rows, excluded = _session_observations(
        db, actor_id, session_id, effective_start, effective_end
    )

    observations = _build_observations(
        db,
        actor_id,
        session_id,
        scene_rows,
        types=types,
        aoi=aoi,
        mask_clouds=data.mask_clouds,
        include_weather=data.include_weather,
        settings=settings,
        veg_threshold=veg_threshold,
        water_threshold=water_threshold,
    )

    events = _build_events(
        db,
        scene_rows,
        types=types,
        aoi=aoi,
        mask_clouds=data.mask_clouds,
        settings=settings,
        veg_threshold=veg_threshold,
        water_threshold=water_threshold,
    )

    coverage = _coverage(scene_rows, excluded=excluded, effective=bool(effective_start))
    trends = {change_type: _build_trend(change_type, observations) for change_type in types}

    warnings = _gather_warnings(observations, events, coverage)
    summary = _summary(types, observations, events, coverage)

    if not observations:
        status = "unavailable"
        unavailable = _unavailable(
            "no_historical_observations",
            "No historical satellite observations are available for this analysis "
            "session within the requested date range.",
            details=[
                f"session_id={session_id}",
                f"date_range={_date_range_label(effective_start, effective_end)}",
            ],
        )
    else:
        completed_any = _any_completed(observations, events, types)
        status = "completed" if completed_any else "unavailable"
        unavailable = None if completed_any else _all_unavailable(observations, events, types)

    return {
        "status": status,
        "session": {
            "id": session["id"],
            "title": session.get("title"),
            "start_date": session.get("start_date"),
            "end_date": session.get("end_date"),
        },
        "types_requested": types,
        "coverage": coverage,
        "observations": observations,
        "events": events,
        "trends": trends,
        "weather_contexts": (
            [observation["weather_context"] for observation in observations]
            if data.include_weather
            else None
        ),
        "summary": summary,
        "provenance": _provenance(settings),
        "warnings": warnings,
        "unavailable": unavailable,
    }


# ---------------------------------------------------------------------------
# Internal steps
# ---------------------------------------------------------------------------


def _resolve_date_range(
    session: dict[str, Any], data: historical_schemas.HistoricalRequest
) -> tuple[date | None, date | None]:
    """Session dates are authoritative; an optional override must stay inside."""
    if (data.start_date is None) != (data.end_date is None):
        raise bad_request(
            "Both start_date and end_date must be provided together.",
            code="invalid_date_range",
        )
    session_start, session_end = session.get("start_date"), session.get("end_date")
    if data.start_date is None:
        return session_start, session_end
    start, end = analysis_session_service.validate_date_range(data.start_date, data.end_date)
    if session_start is not None and (start < session_start or end > session_end):
        raise bad_request(
            "The requested date range must stay within the analysis session's date range.",
            code="date_range_outside_session",
        )
    return start, end


def _session_observations(
    db: Session,
    actor_id: int,
    session_id: int,
    start: date | None,
    end: date | None,
) -> tuple[list[SatelliteScene], int]:
    """Session-authorized scenes, ordered oldest → newest within the date range."""
    summaries = satellite_scene_service.list_scenes_for_session(db, actor_id, session_id)
    total = len(summaries)
    ordered = order_observations(summaries)
    if start is not None or end is not None:
        ordered = [
            scene
            for scene in ordered
            if (start is None or scene["acquisition_date"] >= start)
            and (end is None or scene["acquisition_date"] <= end)
        ]
    excluded = total - len(ordered) if (start is not None or end is not None) else 0

    if not ordered:
        return [], excluded
    orm_by_id = {
        row.id: row
        for row in db.execute(
            select(SatelliteScene).where(SatelliteScene.id.in_([s["id"] for s in ordered]))
        ).scalars()
    }
    return [orm_by_id[summary["id"]] for summary in ordered if summary["id"] in orm_by_id], excluded


def _build_observations(
    db: Session,
    actor_id: int,
    session_id: int,
    scenes: list[SatelliteScene],
    *,
    types: list[str],
    aoi: dict[str, Any],
    mask_clouds: bool,
    include_weather: bool,
    settings,
    veg_threshold: float,
    water_threshold: float,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        observation: dict[str, Any] = {
            "date": scene.acquisition_date,
            "index": index,
            "scene": _scene_reference(scene),
            "weather_context": None,
        }
        for change_type in types:
            index_spec, required = _TYPE_INDEX[change_type]
            threshold = veg_threshold if change_type == "vegetation" else water_threshold
            observation[change_type] = _observation_metric(
                db,
                scene,
                index_spec,
                required,
                aoi=aoi,
                mask_clouds=mask_clouds,
                settings=settings,
                threshold=threshold,
            )
        if include_weather:
            observation["weather_context"] = weather_context_service.default_context(
                db, actor_id, session_id, scene.id
            )
        observations.append(observation)
    return observations


def _observation_metric(
    db: Session,
    scene: SatelliteScene,
    index: Any,
    required: tuple[str, str],
    *,
    aoi: dict[str, Any],
    mask_clouds: bool,
    settings,
    threshold: float,
) -> dict[str, Any]:
    inputs, unavailable = _resolve_bands(db, scene, index.name, required, mask_clouds)
    if inputs is None:
        return {
            "status": "unavailable",
            "index": None,
            "statistics": None,
            "water": None,
            "warnings": [],
            "unavailable": unavailable,
        }
    if index.name == "ndwi":
        max_window_pixels = settings.aqua_max_window_pixels
        min_valid_fraction = settings.aqua_min_valid_fraction
    else:
        max_window_pixels = settings.agri_max_window_pixels
        min_valid_fraction = settings.agri_min_valid_fraction
    try:
        payload = analyze_index_ratio(
            aoi_geojson=aoi,
            index=index,
            band_role_keys=inputs["role_keys"],
            band_paths=inputs["band_paths"],
            band_retrievals=inputs["band_retrievals"],
            acquisition_date=scene.acquisition_date,
            cloud_cover=scene.cloud_cover,
            provider=scene.provider,
            platform=scene.platform,
            provider_scene_id=scene.scene_id,
            mask_clouds=mask_clouds,
            max_window_pixels=max_window_pixels,
            min_valid_fraction=min_valid_fraction,
        )
    except IndexAnalysisUnavailable as exc:
        return {
            "status": "unavailable",
            "index": None,
            "statistics": None,
            "water": None,
            "warnings": [],
            "unavailable": _unavailable(exc.code, exc.reason, exc.details),
        }

    statistics = {
        "min": payload["statistics"]["min"],
        "max": payload["statistics"]["max"],
        "mean": payload["statistics"]["mean"],
        "median": payload["statistics"]["median"],
        "stddev": payload["statistics"]["stddev"],
        "valid_pixel_count": payload["statistics"]["valid_pixel_count"],
        "aoi_pixel_count": payload["statistics"]["aoi_pixel_count"],
        "valid_pixel_pct": payload["statistics"]["valid_pixel_pct"],
        "excluded_pixel_pct": payload["statistics"]["excluded_pixel_pct"],
        "sampled_area_m2": payload["statistics"]["sampled_area_m2"],
        "units": payload["statistics"]["units"],
        "range": payload["statistics"]["range"],
    }
    result: dict[str, Any] = {
        "status": "completed",
        "index": payload["index"],
        "statistics": statistics,
        "warnings": list(payload["warnings"]),
        "unavailable": None,
    }
    if index.name == "ndwi":
        water = aqua_water_summary(
            payload["nd"],
            payload["nd_valid"],
            threshold=threshold,
            valid_pixel_count=payload["statistics"]["valid_pixel_count"],
            aoi_pixel_count=payload["statistics"]["aoi_pixel_count"],
            pixel_area_m2=payload["processing"]["pixel_area_m2"],
        )
        result["water"] = {
            "pixel_count": water["water"]["pixel_count"],
            "pixel_pct": water["water"]["pixel_pct"],
            "area_m2": water["water"]["area_m2"],
            "pct_of_aoi_area": water["water"]["pct_of_aoi_area"],
            "aoi_area_m2": water["aoi_area_m2"],
        }
    return result


def _build_events(
    db: Session,
    scenes: list[SatelliteScene],
    *,
    types: list[str],
    aoi: dict[str, Any],
    mask_clouds: bool,
    settings,
    veg_threshold: float,
    water_threshold: float,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for before, after in zip(scenes, scenes[1:], strict=False):
        if after.acquisition_date == before.acquisition_date:
            continue  # same-day observations cannot be temporally ordered
        for change_type in types:
            index_spec, required = _TYPE_INDEX[change_type]
            threshold = veg_threshold if change_type == "vegetation" else water_threshold
            events.append(
                _pair_event(
                    db,
                    before,
                    after,
                    index_spec,
                    required,
                    change_type=change_type,
                    aoi=aoi,
                    mask_clouds=mask_clouds,
                    settings=settings,
                    threshold=threshold,
                )
            )
    return events


def _pair_event(
    db: Session,
    before: SatelliteScene,
    after: SatelliteScene,
    index: Any,
    required: tuple[str, str],
    *,
    change_type: str,
    aoi: dict[str, Any],
    mask_clouds: bool,
    settings,
    threshold: float,
) -> dict[str, Any]:
    before_inputs, before_unavailable = _resolve_bands(
        db, before, index.name, required, mask_clouds
    )
    after_inputs, after_unavailable = _resolve_bands(db, after, index.name, required, mask_clouds)
    unresolved = before_unavailable or after_unavailable
    if unresolved is not None:
        event = {
            "type": change_type,
            "status": "unavailable",
            "start_date": before.acquisition_date,
            "end_date": after.acquisition_date,
            "gap_days": (after.acquisition_date - before.acquisition_date).days,
            "before": _scene_reference(before),
            "after": _scene_reference(after),
            "statistics": None,
            "classification": None,
            "mask": None,
            "warnings": [],
            "unavailable": unresolved,
        }
    else:
        try:
            payload = compute_change_index(
                aoi_geojson=aoi,
                index=index,
                change_type=change_type,
                scene_before=before_inputs,
                scene_after=after_inputs,
                mask_clouds=mask_clouds,
                settings=settings,
                change_threshold=threshold,
            )
            event = _event_from_payload(payload, before, after)
        except ChangeDetectionUnavailable as exc:
            event = {
                "type": change_type,
                "status": "unavailable",
                "start_date": before.acquisition_date,
                "end_date": after.acquisition_date,
                "gap_days": (after.acquisition_date - before.acquisition_date).days,
                "before": _scene_reference(before),
                "after": _scene_reference(after),
                "statistics": None,
                "classification": None,
                "mask": None,
                "warnings": [],
                "unavailable": _unavailable(exc.code, exc.reason, exc.details),
            }
    return event


def _event_from_payload(
    payload: dict[str, Any], before: SatelliteScene, after: SatelliteScene
) -> dict[str, Any]:
    classification_block = payload["classification"]
    if payload["type"] == "water":
        event, label, basis = classify_water_event(classification_block)
        classes = classification_block["classes"]
        extent = classification_block["water_extent"]
        water_extent = {
            "before_pixels": extent["before_pixels"],
            "after_pixels": extent["after_pixels"],
            "delta_pixels": extent["delta_pixels"],
            "before_pct": extent["before_pct"],
            "after_pct": extent["after_pct"],
            "added": classes["new"],
            "lost": classes["lost"],
            "persistent": classes["persistent"],
            "unchanged": classes["unchanged"],
        }
        changed_region = None
    else:
        event, label, basis = classify_vegetation_event(classification_block)
        classes = classification_block["classes"]
        increased = classes["increase"]
        decreased = classes["decrease"]
        stable = classes["stable"]
        changed_total_pixels = increased["pixel_count"] + decreased["pixel_count"]
        changed_total_pct = round(increased["pixel_pct"] + decreased["pixel_pct"], 4)
        changed_total_area = (
            round(increased["area_m2"] + decreased["area_m2"], 2)
            if increased["area_m2"] is not None and decreased["area_m2"] is not None
            else None
        )
        changed_region = {
            "increased": increased,
            "decreased": decreased,
            "stable": stable,
            "changed_total": {
                "pixel_count": changed_total_pixels,
                "pixel_pct": changed_total_pct,
                "area_m2": changed_total_area,
            },
        }
        water_extent = None

    masking = payload["comparison"]["masking"]
    return {
        "type": payload["type"],
        "status": "completed",
        "start_date": before.acquisition_date,
        "end_date": after.acquisition_date,
        "gap_days": (after.acquisition_date - before.acquisition_date).days,
        "before": _scene_reference(before),
        "after": _scene_reference(after),
        "statistics": payload["statistics"],
        "classification": {
            "event": event,
            "label": label,
            "basis": basis,
            "threshold": classification_block["threshold"],
            "boundary": classification_block["boundary"],
            "comparison_pixels": classification_block["comparison_pixels"],
            "comparison_valid_pct": masking["comparison_valid_pct"],
            "limitations_note": classification_block["limitations_note"],
            "region": changed_region,
            "water_extent": water_extent,
        },
        "mask": payload["mask"],
        "warnings": list(payload["warnings"]),
        "unavailable": None,
    }


def _resolve_bands(
    db: Session,
    scene: SatelliteScene,
    index_name: str,
    required: tuple[str, str],
    mask_clouds: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve role -> asset keys, band paths, and retrieval ids.

    Returns ``(inputs, None)`` when the scene can be analyzed, or
    ``(None, unavailable_info)`` otherwise (provider unsupported / bands missing).
    """
    role_keys = resolve_band_keys(scene.provider, index_name)
    if role_keys is None:
        return None, _unavailable(
            "provider_unsupported",
            f"No band mapping is registered for provider '{scene.provider}'.",
            details=[f"index={index_name}", f"scene_id={scene.scene_id}"],
        )

    key_paths, key_ids, missing = satellite_scene_service.completed_retrieval_paths(
        db, scene.id, [role_keys[role] for role in required]
    )
    if missing:
        return None, _unavailable(
            "bands_not_retrieved",
            "The band assets required for this history analysis have not been "
            "downloaded for this scene.",
            details=[
                f"missing_assets={','.join(sorted(missing))}",
                f"scene_id={scene.id}",
                f"date={scene.acquisition_date.isoformat()}",
                f"index={index_name}",
            ],
        )

    band_paths = {role: key_paths[role_keys[role]] for role in required}
    band_retrievals = {role: key_ids[role_keys[role]] for role in required}
    if mask_clouds and "cloud_mask" in role_keys:
        scl_paths, scl_ids, scl_missing = satellite_scene_service.completed_retrieval_paths(
            db, scene.id, [role_keys["cloud_mask"]]
        )
        if not scl_missing:
            band_paths["cloud_mask"] = scl_paths[role_keys["cloud_mask"]]
            band_retrievals["cloud_mask"] = scl_ids[role_keys["cloud_mask"]]

    return {
        "role_keys": role_keys,
        "band_paths": band_paths,
        "band_retrievals": band_retrievals,
        "acquisition_date": scene.acquisition_date,
        "cloud_cover": scene.cloud_cover,
        "provider": scene.provider,
        "platform": scene.platform,
        "provider_scene_id": scene.scene_id,
    }, None


def _coverage(
    scenes: list[SatelliteScene],
    *,
    excluded: int,
    effective: bool,
) -> dict[str, Any]:
    count = len(scenes)
    start_date = scenes[0].acquisition_date if scenes else None
    end_date = scenes[-1].acquisition_date if scenes else None
    span = (
        (end_date - start_date).days
        if start_date is not None and end_date is not None and end_date >= start_date
        else None
    )
    gaps, same_day_pairs = temporal_gaps([scene.acquisition_date for scene in scenes])

    notes: list[str] = []
    if count == 0:
        notes.append(
            "No historical satellite observations are available for this analysis "
            "session within the requested date range."
        )
    if count == 1:
        notes.append("Only one observation is available; no change events can be computed.")
    if effective and excluded:
        notes.append(f"{excluded} observation(s) outside the requested date range were excluded.")
    for gap in gaps:
        notes.append(
            f"Temporal gap of {gap['gap_days']} days between {gap['from_date'].isoformat()} "
            f"and {gap['to_date'].isoformat()} is reported and never interpolated."
        )
    if same_day_pairs:
        notes.append(
            "Observations sharing the same acquisition date cannot be temporally "
            "ordered; change events were not computed between them."
        )
    if not notes:
        notes.append("No temporal gaps or ordering issues were found in the timeline.")

    compared_pairs = max(count - 1 - same_day_pairs, 0)
    limited = count < 2 or bool(gaps) or same_day_pairs > 0
    return {
        "observation_count": count,
        "start_date": start_date,
        "end_date": end_date,
        "temporal_span_days": span,
        "ordered_by": "acquisition_date (oldest → newest)",
        "gaps": gaps,
        "compared_pairs": compared_pairs,
        "same_day_pairs_skipped": same_day_pairs,
        "limited": limited,
        "notes": notes,
    }


def _build_trend(change_type: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    completed = []
    for observation in observations:
        metric = observation.get(change_type)
        if metric is None or metric["status"] != "completed":
            continue
        if change_type == "water":
            value = metric["water"]["area_m2"] if metric.get("water") else None
            valid_pixel_pct = metric["statistics"]["valid_pixel_pct"]
        else:
            value = metric["statistics"]["mean"]
            valid_pixel_pct = metric["statistics"]["valid_pixel_pct"]
        completed.append(
            {
                "date": observation["date"],
                "value": value,
                "valid_pixel_pct": valid_pixel_pct,
            }
        )

    if not completed:
        return {
            "type": change_type,
            "observations": 0,
            "period": {"start": None, "end": None},
            "first": None,
            "latest": None,
            "minimum": None,
            "maximum": None,
            "absolute_change": None,
            "relative_change_pct": None,
            "basis": trend_basis(0, False),
            "note": _TREND_NOTE,
        }

    usable = [point for point in completed if point["value"] is not None]
    first = completed[0]
    latest = completed[-1]
    if usable:
        minimum = min(usable, key=lambda point: point["value"])
        maximum = max(usable, key=lambda point: point["value"])
    else:
        minimum = None
        maximum = None
    absolute_change = (
        round(latest["value"] - first["value"], 6)
        if latest["value"] is not None and first["value"] is not None
        else None
    )
    relative_change_pct = (
        round((absolute_change / abs(first["value"])) * 100.0, 4)
        if absolute_change is not None and first["value"] not in (None, 0)
        else None
    )
    same_date = first["date"] == latest["date"]
    return {
        "type": change_type,
        "observations": len(completed),
        "period": {"start": first["date"], "end": latest["date"]},
        "first": {
            "date": first["date"],
            "value": first["value"],
            "valid_pixel_pct": first["valid_pixel_pct"],
        },
        "latest": {
            "date": latest["date"],
            "value": latest["value"],
            "valid_pixel_pct": latest["valid_pixel_pct"],
        },
        "minimum": {
            "date": minimum["date"],
            "value": minimum["value"],
            "valid_pixel_pct": minimum["valid_pixel_pct"],
        }
        if minimum
        else None,
        "maximum": {
            "date": maximum["date"],
            "value": maximum["value"],
            "valid_pixel_pct": maximum["valid_pixel_pct"],
        }
        if maximum
        else None,
        "absolute_change": absolute_change,
        "relative_change_pct": relative_change_pct,
        "basis": trend_basis(len(completed), same_date),
        "note": _TREND_NOTE,
    }


def _gather_warnings(
    observations: list[dict[str, Any]],
    events: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for observation in observations:
        for metric in (
            observation[change_type]
            for change_type in ("vegetation", "water")
            if change_type in observation
        ):
            for item in metric.get("warnings") or []:
                if item not in warnings:
                    warnings.append(item)
    for event in events:
        for item in event.get("warnings") or []:
            if item not in warnings:
                warnings.append(item)
    for note in coverage.get("notes") or []:
        # The "no temporal gaps or ordering issues" line is reassurance, not a warning.
        if "no temporal gaps" in note.lower() or note in warnings:
            continue
        warnings.append(note)
    return warnings


def _any_completed(
    observations: list[dict[str, Any]],
    events: list[dict[str, Any]],
    types: list[str],
) -> bool:
    for observation in observations:
        for change_type in types:
            metric = observation.get(change_type)
            if metric and metric["status"] == "completed":
                return True
    for event in events:
        if event["status"] == "completed" and event["type"] in types:
            return True
    return False


def _all_unavailable(
    observations: list[dict[str, Any]],
    events: list[dict[str, Any]],
    types: list[str],
) -> dict[str, Any]:
    codes: dict[str, list[str]] = {}
    for observation in observations:
        for change_type in types:
            metric = observation.get(change_type)
            if metric and metric["status"] == "unavailable":
                code = metric["unavailable"]["code"]
                codes.setdefault(change_type, []).append(code)
    for event in events:
        if event["status"] == "unavailable":
            code = event["unavailable"]["code"]
            codes.setdefault(event["type"], []).append(code)
    return _unavailable(
        "all_requested_analyses_unavailable",
        "None of the requested historical analyses could be completed.",
        details=[
            f"{change_type}={','.join(sorted(set(item for item in values)))}"
            for change_type, values in codes.items()
        ],
    )


def _summary(
    types: list[str],
    observations: list[dict[str, Any]],
    events: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> str:
    count = coverage["observation_count"]
    if count == 0:
        return (
            "No historical satellite observations are available for this analysis "
            "session within the requested date range."
        )
    start = coverage["start_date"].isoformat()
    end = coverage["end_date"].isoformat()
    parts = [f"{count} satellite observations between {start} and {end}."]
    for change_type in types:
        completed = sum(
            1
            for observation in observations
            if observation.get(change_type) and observation[change_type]["status"] == "completed"
        )
        label = "Vegetation (NDVI)" if change_type == "vegetation" else "Water extent (NDWI)"
        parts.append(f"{label} was measured on {completed} of {count} observations.")
    completed_events = [event for event in events if event["status"] == "completed"]
    if completed_events:
        latest_event = completed_events[-1]
        label = latest_event["classification"]["label"]
        parts.append(
            f"{len(completed_events)} observed change(s) between consecutive observations; "
            f"the most recent is '{label}' between "
            f"{latest_event['start_date'].isoformat()} and {latest_event['end_date'].isoformat()}."
        )
    else:
        parts.append("No changes between consecutive observations could be computed.")
    parts.append(
        "Weather is shown as descriptive context only and does not attribute cause to the imagery."
    )
    return " ".join(parts)


def _date_range_label(start: date | None, end: date | None) -> str:
    if start is None and end is None:
        return "session default"
    return f"{start.isoformat() if start else 'open'}..{end.isoformat() if end else 'open'}"


def _provenance(settings) -> dict[str, Any]:
    return {
        "engine_version": settings.historical_engine_version,
        "derived_on_demand": True,
        "ordering_semantics": _ORDERING_SEMANTICS,
        "change_reuse": _CHANGE_REUSE,
        "area_method": "pixel count x projected pixel area (north-up grid)",
        "libraries": {"numpy": numpy.__version__, "rasterio": rasterio.__version__},
        "analyzed_at": datetime.now(UTC).isoformat(),
    }
