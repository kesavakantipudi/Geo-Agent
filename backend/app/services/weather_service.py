"""Weather retrieval orchestration (Phase 5).

Mirrors the satellite scene service: retrieval is session-scoped, provider calls
go through the provider abstraction, results are merged and de-duplicated, and
each observation is persisted with full provenance. Values are *real* responses
from the provider; missing data stays ``None`` (never ``0``) and is not turned
into invented observations. Rate limiting and timeout bounds are enforced by each
provider from settings; an AOI point cap bounds the number of stored rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.models import (
    AnalysisSession,
    WeatherObservation,
    WeatherObservationDiscovery,
    Workspace,
)
from app.schemas import weather as weather_schemas
from app.services import analysis_session_service, workspace_service
from app.services.geometry import validate_geometry
from app.services.weather import (
    WeatherError,
    get_enabled_weather_provider_names,
    get_weather_providers,
)

# Data types that track a specific date range and therefore require dates.
DATE_RANGE_DATA_TYPES = frozenset({"history", "archive", "reanalysis", "historical_forecast"})


def _resolve_weather_providers(requested: list[str] | None) -> list[Any]:
    enabled = get_enabled_weather_provider_names()
    if not enabled:
        raise bad_request(
            "Weather retrieval is disabled or no provider is enabled.",
            code="weather_disabled",
        )
    wanted = [name.strip().lower() for name in requested] if requested else enabled
    if requested is not None:
        unknown = [name for name in wanted if name not in enabled]
        if unknown:
            raise bad_request(
                f"Unknown or disabled weather provider(s): {', '.join(unknown)}.",
                code="weather_provider_not_enabled",
            )
    providers = [p for p in get_weather_providers() if p.name in wanted]
    if not providers:
        raise bad_request("No weather provider is currently enabled.", code="weather_disabled")
    return providers


def _validate_variables(variables: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(variables))
    unknown = [name for name in normalized if name not in weather_schemas.VARIABLES]
    if unknown:
        raise bad_request(
            f"Unknown weather variable(s): {', '.join(unknown)}. "
            f"Supported variables: {', '.join(weather_schemas.VARIABLES)}.",
            code="weather_variable_unknown",
        )
    max_variables = max(1, get_settings().weather_max_variables)
    if len(normalized) > max_variables:
        raise bad_request(
            f"Too many variables requested: {len(normalized)} (max {max_variables}).",
            code="weather_too_many_variables",
        )
    return normalized


def _bbox_from_info(info: dict[str, Any]) -> tuple[float, float, float, float]:
    """Convert geometry ``[min_lon, min_lat, max_lon, max_lat]`` to provider order."""
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in info["bbox"])
    return (min_lat, min_lon, max_lat, max_lon)


def _point_cap(settings) -> int:
    return max(1, settings.weather_max_points_per_aoi)


def _default_variables() -> list[str]:
    return list(weather_schemas.DEFAULT_VARIABLES)


def _parse_observed_at(value: Any, timezone: str | None) -> datetime | None:
    """Parse a provider ISO timestamp into a timezone-aware datetime.

    Provider timestamps are recorded in the provider's configured timezone;
    the offset information is never invented, so an unparseable timestamp is
    dropped rather than guessed.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        observed_at = value
    else:
        try:
            observed_at = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if observed_at.tzinfo is None:
        try:
            tz = ZoneInfo(timezone or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")
        observed_at = observed_at.replace(tzinfo=tz)
    return observed_at


def fetch_weather_endpoint(
    db: Session, actor_id: int, payload: weather_schemas.WeatherSearchRequest
) -> dict[str, Any]:
    """Discover and persist weather observations for a session AOI or inline AOI."""
    settings = get_settings()
    point_cap = _point_cap(settings)

    session_obj: AnalysisSession | None = None
    aoi = payload.aoi
    start, end = payload.start_date, payload.end_date
    if payload.analysis_session_id is not None:
        session = analysis_session_service.get(db, actor_id, payload.analysis_session_id)
        aoi = payload.aoi if payload.aoi is not None else session.get("aoi")
        start = payload.start_date if payload.start_date is not None else session.get("start_date")
        end = payload.end_date if payload.end_date is not None else session.get("end_date")
        session_obj = db.get(AnalysisSession, session["id"])

    if aoi is None:
        raise bad_request("Provide an AOI or analysis_session_id.", code="aoi_required")

    start, end = analysis_session_service.validate_date_range(start, end)
    if payload.data_type in DATE_RANGE_DATA_TYPES and (start is None or end is None):
        raise bad_request(
            f"start_date and end_date are required for data type '{payload.data_type}'.",
            code="date_range_required",
        )

    info = validate_geometry(aoi, name="aoi", require_area=True)
    bbox = _bbox_from_info(info)

    variables = _validate_variables(payload.variables or _default_variables())
    providers = _resolve_weather_providers(payload.providers)

    observations: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    truncated = False

    for provider in providers:
        try:
            found = provider.fetch_weather(
                bbox=bbox,
                start=start.isoformat() if start else "",
                end=end.isoformat() if end else "",
                variables=variables,
                model=payload.model,
                timezone=payload.timezone,
                units=payload.units,
                data_type=payload.data_type,
            )
        except WeatherError as exc:
            statuses.append({"provider": provider.name, "observations": 0, "error": str(exc)})
            continue
        persisted = 0
        for point in found:
            observed_at = _parse_observed_at(
                point.get("observed_at"), point.get("timezone") or payload.timezone
            )
            latitude = point.get("latitude")
            longitude = point.get("longitude")
            if observed_at is None or latitude is None or longitude is None:
                continue
            for variable, value in (point.get("variables") or {}).items():
                if value is None:
                    continue  # missing stays missing; never stored as 0
                if persisted >= point_cap:
                    truncated = True
                    break
                row = _persist_observation(
                    db,
                    provider.name,
                    actor_id,
                    observed_at,
                    latitude,
                    longitude,
                    variable,
                    value,
                    point,
                    payload,
                    session_obj,
                )
                persisted += 1
                observations.append(_weather_summary(row))
            if truncated:
                break
        statuses.append({"provider": provider.name, "observations": persisted, "error": None})

    db.commit()
    return {
        "observations": observations,
        "providers": statuses,
        "truncated": truncated,
    }


def _persist_observation(
    db: Session,
    provider_name: str,
    actor_id: int,
    observed_at: datetime,
    latitude: float,
    longitude: float,
    variable: str,
    value: float,
    point: dict[str, Any],
    payload: weather_schemas.WeatherSearchRequest,
    session_obj: AnalysisSession | None,
) -> WeatherObservation:
    provenance = point.get("provenance") or {}
    attribution = point.get("attribution") or _attribution()
    units = (point.get("units") or {}).get(variable)
    model = point.get("model")
    data_type = point.get("data_type") or payload.data_type
    timezone = point.get("timezone") or payload.timezone

    row = db.execute(
        select(WeatherObservation).where(
            WeatherObservation.provider == provider_name,
            WeatherObservation.observed_at == observed_at,
            WeatherObservation.latitude == latitude,
            WeatherObservation.longitude == longitude,
            WeatherObservation.variable == variable,
        )
    ).scalar_one_or_none()
    if row is None:
        row = WeatherObservation(
            provider=provider_name,
            observed_at=observed_at,
            latitude=latitude,
            longitude=longitude,
            variable=variable,
            value=value,
            units=units,
            units_doc=point.get("units_doc"),
            model=model,
            data_type=data_type,
            timezone=timezone,
            provenance=provenance,
            attribution=attribution,
        )
        db.add(row)
        db.flush()
    else:
        row.value = value
        row.units = units
        row.units_doc = point.get("units_doc")
        row.model = model
        row.data_type = data_type
        row.timezone = timezone
        row.provenance = provenance
        row.attribution = attribution

    if session_obj is not None:
        discovery = db.execute(
            select(WeatherObservationDiscovery).where(
                WeatherObservationDiscovery.observation_id == row.id,
                WeatherObservationDiscovery.analysis_session_id == session_obj.id,
            )
        ).scalar_one_or_none()
        if discovery is None:
            db.add(
                WeatherObservationDiscovery(
                    observation_id=row.id,
                    analysis_session_id=session_obj.id,
                    discovered_by=actor_id,
                )
            )
    db.flush()
    db.refresh(row)
    return row


def _attribution() -> str:
    settings = get_settings()
    return getattr(settings, "weather_attribution", "Weather data by Open-Meteo.com")


def _weather_summary(row: WeatherObservation) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "model": row.model,
        "data_type": row.data_type,
        "variable": row.variable,
        "observed_at": row.observed_at,
        "timezone": row.timezone,
        "value": row.value,
        "units": row.units,
        "units_doc": row.units_doc,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "provenance": row.provenance or {},
        "attribution": row.attribution or _attribution(),
    }


def list_observations_for_session(
    db: Session, actor_id: int, analysis_session_id: int
) -> list[dict[str, Any]]:
    """Return weather observations previously persisted for a session."""
    analysis_session_service.get(db, actor_id, analysis_session_id)
    rows = (
        db.execute(
            select(WeatherObservation)
            .join(
                WeatherObservationDiscovery,
                WeatherObservationDiscovery.observation_id == WeatherObservation.id,
            )
            .where(WeatherObservationDiscovery.analysis_session_id == analysis_session_id)
            .order_by(WeatherObservation.observed_at.desc(), WeatherObservation.variable)
        )
        .scalars()
        .all()
    )
    return [_weather_summary(row) for row in rows]


def get_observation(db: Session, actor_id: int, observation_id: int) -> dict[str, Any]:
    """Authorized observation summary (must belong to one of the actor's sessions)."""
    row = db.execute(
        select(WeatherObservation).where(WeatherObservation.id == observation_id)
    ).scalar_one_or_none()
    if row is None or not _can_access_observation(db, actor_id, observation_id):
        raise not_found("Weather observation not found.", code="weather_observation_not_found")
    return _weather_summary(row)


def _can_access_observation(db: Session, actor_id: int, observation_id: int) -> bool:
    discoveries = (
        db.execute(
            select(WeatherObservationDiscovery).where(
                WeatherObservationDiscovery.observation_id == observation_id
            )
        )
        .scalars()
        .all()
    )
    if not discoveries:
        return False
    for discovery in discoveries:
        session = db.get(AnalysisSession, discovery.analysis_session_id)
        if session is None:
            continue
        if session.user_id == actor_id:
            return True
        if session.workspace_id is None:
            continue
        workspace = db.get(Workspace, session.workspace_id)
        if workspace is not None and workspace_service.is_accesible(db, workspace, actor_id):
            return True
    return False
