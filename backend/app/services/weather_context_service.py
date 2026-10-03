"""Weather-context orchestration (Phase 6C).

Aligns *already-stored* weather observations (Phase 5) with a satellite
observation. The session is the access boundary (only observations discovered
for the session are considered) and both the session and the scene must be
accessible to the actor. The service never calls a provider: it only reads
whatever weather data was persisted earlier, so missing data is reported as an
explicit unavailable / incomplete state rather than fabricated.

The dedicated endpoint additionally enforces that the scene is *discovered by*
the given session (``require_associated=True``). Embedding into an intelligence
result (agri/aqua) uses ``default_context``, which intentionally skips that
association check because the scene was already authorized for the analysis.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request
from app.models import (
    SatelliteScene,
    SatelliteSceneDiscovery,
    WeatherObservation,
    WeatherObservationDiscovery,
)
from app.schemas import weather as weather_schemas
from app.services import analysis_session_service, satellite_scene_service
from app.services.weather import context as weather_context
from app.services.weather import get_enabled_weather_provider_names
from app.services.weather_service import _validate_variables

CONTEXT_NOTE = (
    "Weather context describes observed conditions around this satellite "
    "observation; it does not attribute cause to the imagery."
)


def _default_variables() -> list[str]:
    settings = get_settings()
    raw = getattr(settings, "weather_context_variables", "") or ""
    return [name.strip() for name in raw.split(",") if name.strip()]


def _resolve_context_providers(requested: list[str] | None) -> list[str] | None:
    """Validate an optional provider filter against the enabled providers."""
    if requested is None:
        return None
    enabled = set(get_enabled_weather_provider_names())
    wanted = [name.strip().lower() for name in requested if name.strip()]
    unknown = [name for name in wanted if name not in enabled]
    if unknown:
        raise bad_request(
            f"Unknown or disabled weather provider(s): {', '.join(unknown)}.",
            code="weather_provider_not_enabled",
        )
    return wanted


def _resolve_window(settings, days_before: int | None, days_after: int | None) -> tuple[int, int]:
    max_days = settings.weather_context_max_window_days
    before = days_before if days_before is not None else settings.weather_context_window_days
    after = days_after if days_after is not None else settings.weather_context_window_days
    for name, days in (("days_before", before), ("days_after", after)):
        if days < 0 or days > max_days:
            raise bad_request(
                f"{name} must be between 0 and {max_days} (config: "
                "weather_context_max_window_days).",
                code="weather_context_window_out_of_range",
            )
    return before, after


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


def build_context(
    db: Session,
    actor_id: int,
    request: weather_schemas.WeatherContextRequest,
    require_associated: bool = False,
) -> dict[str, Any]:
    session = analysis_session_service.get(db, actor_id, request.analysis_session_id)
    scene = satellite_scene_service.get_scene_orm(db, actor_id, request.scene_id)
    if require_associated:
        _check_scene_associated(db, session["id"], scene.id)

    settings = get_settings()
    days_before, days_after = _resolve_window(settings, request.days_before, request.days_after)
    variables = _validate_variables(
        list(request.variables) if request.variables is not None else _default_variables()
    )
    providers = _resolve_context_providers(request.providers)

    return _build_context(
        db,
        session["id"],
        scene,
        days_before=days_before,
        days_after=days_after,
        variables=variables,
        providers=providers,
    )


def default_context(db: Session, actor_id: int, session_id: int, scene_id: int) -> dict[str, Any]:
    """Convenience wrapper for embedding context into intelligence results.

    Uses configured default window/variable settings and no provider filter;
    the scene association is not re-checked (the analysis already authorized it).
    """
    session = analysis_session_service.get(db, actor_id, session_id)
    scene = satellite_scene_service.get_scene_orm(db, actor_id, scene_id)
    return _build_context(
        db,
        session["id"],
        scene,
        days_before=None,
        days_after=None,
        variables=None,
        providers=None,
    )


def _build_context(
    db: Session,
    session_id: int,
    scene: SatelliteScene,
    days_before: int | None,
    days_after: int | None,
    variables: list[str] | None,
    providers: list[str] | None,
) -> dict[str, Any]:
    settings = get_settings()
    days_before = days_before if days_before is not None else settings.weather_context_window_days
    days_after = days_after if days_after is not None else settings.weather_context_window_days
    variables = variables if variables is not None else _default_variables()

    start, end = weather_context.alignment_window(scene.acquisition_date, days_before, days_after)
    start_day, end_day = weather_context.window_dates(
        scene.acquisition_date, days_before, days_after
    )

    query = (
        select(WeatherObservation)
        .join(
            WeatherObservationDiscovery,
            WeatherObservationDiscovery.observation_id == WeatherObservation.id,
        )
        .where(WeatherObservationDiscovery.analysis_session_id == session_id)
        .where(WeatherObservation.observed_at >= start)
        .where(WeatherObservation.observed_at <= end)
        .where(WeatherObservation.variable.in_(variables))
        .order_by(WeatherObservation.observed_at, WeatherObservation.variable)
    )
    if providers:
        query = query.where(WeatherObservation.provider.in_(providers))
    rows = db.execute(query).scalars().all()

    normalized = [_normalize_row(row, settings) for row in rows]
    expected_count = weather_context.expected_timestamp_count(normalized)
    variables_meta, warnings = weather_context.aggregate_observations(
        normalized, variables, expected_count
    )

    providers_present = sorted({row["provider"] for row in normalized})
    models = sorted({row["model"] for row in normalized if row.get("model")})
    data_types = sorted({row["data_type"] for row in normalized if row.get("data_type")})
    attributions = {row["attribution"] for row in normalized if row.get("attribution")}
    attribution = next(iter(attributions), None) or settings.weather_attribution
    observation_count = len(normalized)
    completeness_pct = (
        round(sum(float(item["coverage_pct"]) for item in variables_meta) / len(variables_meta), 1)
        if variables_meta
        else 0.0
    )

    context: dict[str, Any] = {
        "status": "available" if observation_count else "unavailable",
        "scene": {
            "id": scene.id,
            "scene_id": scene.scene_id,
            "provider": scene.provider,
            "acquisition_date": scene.acquisition_date,
        },
        "satellite_observation": scene.acquisition_date,
        "period": {
            "start": start_day,
            "end": end_day,
            "days_before": days_before,
            "days_after": days_after,
        },
        "variables_requested": variables,
        "variables": variables_meta if observation_count else [],
        "observation_count": observation_count,
        "completeness_pct": completeness_pct,
        "partial": bool(observation_count)
        and (completeness_pct < 100.0 or any(not item["available"] for item in variables_meta)),
        "providers": providers_present,
        "models": models,
        "data_types": data_types,
        "attribution": attribution,
        "warnings": warnings,
        "unavailable": None,
        "note": CONTEXT_NOTE,
    }
    if not observation_count:
        context["unavailable"] = {
            "code": "no_weather_observations",
            "reason": (
                "No stored weather observations are available for the alignment "
                "window around this satellite observation."
            ),
            "details": [
                f"window={start_day.isoformat()}..{end_day.isoformat()}",
                f"requested_variables={','.join(variables)}",
            ],
        }
    return context


def _normalize_row(row: WeatherObservation, settings) -> dict[str, Any]:
    return {
        "variable": row.variable,
        "value": row.value,
        "units": row.units,
        "units_doc": row.units_doc,
        "observed_at": row.observed_at,
        "provider": row.provider,
        "model": row.model,
        "data_type": row.data_type,
        "attribution": row.attribution or settings.weather_attribution,
    }
