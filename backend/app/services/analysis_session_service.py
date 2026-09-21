"""Analysis-session business logic and access control (Phase 3).

Access model (backend-enforced):

- A session is visible to its owner and to members of its workspace.
- Only the owner (and only while the session is ``draft``) can edit or delete
  it, so one user cannot touch another user's sessions by changing an ID.
- AOI geometries and saved locations referenced by a session are validated
  through the shared geometry service.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_AsEWKT
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.models import AnalysisSession, SavedLocation, Workspace
from app.schemas import analysis_session as ses_schemas
from app.services import workspace_service
from app.services.geometry import (
    geojson_from_ewkt,
    geometry_info_from_ewkt,
    parse_geometry,
    validate_geometry,
)

DEFAULT_TITLE = "Untitled analysis"


def _today_utc() -> date:
    return datetime.now(UTC).date()


def validate_date_range(
    start_date: date | None, end_date: date | None
) -> tuple[date | None, date | None]:
    """Validate a start/end pair, returning the normalized pair."""
    if (start_date is None) != (end_date is None):
        raise bad_request("Both start_date and end_date must be provided together.")
    if start_date is None:
        return None, None
    if end_date < start_date:
        raise bad_request("end_date must be on or after start_date.", code="invalid_date_range")
    max_future_years = get_settings().analysis_max_future_years
    future_limit = _today_utc() + timedelta(days=max_future_years * 366)
    if end_date > future_limit:
        raise bad_request(
            f"end_date is more than {max_future_years} years in the future; "
            "analysis must target a realistic date range.",
            code="invalid_date_range",
        )
    return start_date, end_date


def validate_agents(agents: list[str] | None) -> list[str] | None:
    """Normalize and validate the agent selection (non-empty, unique, allowed)."""
    if agents is None:
        return None
    if not agents:
        raise bad_request("Select at least one agent.", code="invalid_agents")
    allowed = set(ses_schemas.AGENT_CODES)
    normalized: list[str] = []
    for code in agents:
        if not isinstance(code, str) or code not in allowed:
            raise bad_request(
                f"Unknown agent '{code}'. Allowed agents: {', '.join(ses_schemas.AGENT_CODES)}.",
                code="invalid_agents",
            )
        if code not in normalized:
            normalized.append(code)
    return normalized


def _resolve_workspace(db: Session, user_id: int, workspace_id: int | None) -> int | None:
    if workspace_id is None:
        return None
    if workspace_id <= 0:
        raise bad_request("Invalid workspace_id.")
    workspace_service.require_member(db, workspace_id, user_id)
    return workspace_id


def _resolve_aoi(
    db: Session, user_id: int, aoi: dict | None, saved_location_id: int | None
) -> tuple[WKTElement | None, dict | None]:
    """Resolve the AOI from inline GeoJSON or a saved location.

    Returns ``(WKTElement | None, info | None)``. The AOI must be a Polygon
    (or MultiPolygon) with a measurable area.
    """
    if aoi is not None and saved_location_id is not None:
        raise bad_request("Provide either 'aoi' or 'saved_location_id', not both.")
    if aoi is not None:
        info = validate_geometry(aoi, name="aoi", require_area=True)
        return parse_geometry("aoi", aoi), info
    if saved_location_id is not None:
        row = db.execute(
            select(SavedLocation, ST_AsEWKT(SavedLocation.geometry)).where(
                SavedLocation.id == saved_location_id,
                SavedLocation.user_id == user_id,
            )
        ).one_or_none()
        if row is None:
            raise not_found("Saved location not found.", code="saved_location_not_found")
        ewkt = row[1]
        if not ewkt:
            raise bad_request(
                "The saved location has no geometry.", code="saved_location_no_geometry"
            )
        info = validate_geometry(ewkt, name="aoi", require_area=True)
        return parse_geometry("aoi", ewkt), info
    return None, None


def _can_view(db: Session, actor_id: int, session: AnalysisSession) -> bool:
    if session.user_id == actor_id:
        return True
    if session.workspace_id is None:
        return False
    workspace = db.get(Workspace, session.workspace_id)
    if workspace is None:
        return False
    return workspace_service.is_accesible(db, workspace, actor_id)


def _fetch_session(
    db: Session, actor_id: int, session_id: int
) -> tuple[AnalysisSession, str | None]:
    row = db.execute(
        select(AnalysisSession, ST_AsEWKT(AnalysisSession.aoi_geometry)).where(
            AnalysisSession.id == session_id
        )
    ).one_or_none()
    if row is None or not _can_view(db, actor_id, row[0]):
        raise not_found("Analysis session not found.", code="analysis_session_not_found")
    return row[0], row[1]


def _require_owner(session: AnalysisSession, actor_id: int) -> None:
    if session.user_id != actor_id:
        raise not_found("Analysis session not found.", code="analysis_session_not_found")


def _row_dict(session: AnalysisSession, ewkt: str | None) -> dict:
    info = geometry_info_from_ewkt(ewkt)
    return {
        "id": session.id,
        "user_id": session.user_id,
        "workspace_id": session.workspace_id,
        "title": session.title,
        "status": session.status,
        "aoi": geojson_from_ewkt(ewkt),
        "start_date": session.start_date,
        "end_date": session.end_date,
        "agents": session.agents,
        "bbox": info["bbox"] if info else None,
        "centroid": info["centroid"] if info else None,
        "area_m2_approx": info["area_m2_approx"] if info else 0.0,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def create(db: Session, user_id: int, data: ses_schemas.AnalysisSessionCreate) -> dict:
    workspace_id = _resolve_workspace(db, user_id, data.workspace_id)
    aoi_geometry, _ = _resolve_aoi(db, user_id, data.aoi, data.saved_location_id)
    start_date, end_date = validate_date_range(data.start_date, data.end_date)
    agents = validate_agents(data.agents)
    session_obj = AnalysisSession(
        user_id=user_id,
        workspace_id=workspace_id,
        title=(data.title or DEFAULT_TITLE).strip() or DEFAULT_TITLE,
        status="draft",
        aoi_geometry=aoi_geometry,
        start_date=start_date,
        end_date=end_date,
        agents=agents,
    )
    db.add(session_obj)
    db.flush()
    _, ewkt = _fetch_session(db, user_id, session_obj.id)
    return _row_dict(session_obj, ewkt)


def list_for_user(db: Session, user_id: int, workspace_id: int | None = None) -> list[dict]:
    if workspace_id is not None:
        _resolve_workspace(db, user_id, workspace_id)
        condition = AnalysisSession.workspace_id == workspace_id
    else:
        accessible_ids = [w["id"] for w in workspace_service.list_for_user(db, user_id)]
        condition = or_(
            AnalysisSession.user_id == user_id,
            AnalysisSession.workspace_id.in_(accessible_ids),
        )
    query = (
        select(AnalysisSession, ST_AsEWKT(AnalysisSession.aoi_geometry))
        .where(condition)
        .order_by(AnalysisSession.created_at.desc())
    )
    rows = db.execute(query).all()
    return [_row_dict(session, ewkt) for session, ewkt in rows]


def get(db: Session, actor_id: int, session_id: int) -> dict:
    session_obj, ewkt = _fetch_session(db, actor_id, session_id)
    return _row_dict(session_obj, ewkt)


def update(
    db: Session, actor_id: int, session_id: int, data: ses_schemas.AnalysisSessionUpdate
) -> dict:
    session_obj, _ = _fetch_session(db, actor_id, session_id)
    _require_owner(session_obj, actor_id)
    if session_obj.status != "draft":
        raise bad_request("Only draft sessions can be edited.", code="session_not_draft")
    if data.aoi is not None or data.saved_location_id is not None:
        aoi_geometry, _ = _resolve_aoi(db, actor_id, data.aoi, data.saved_location_id)
        session_obj.aoi_geometry = aoi_geometry
    if data.workspace_id is not None:
        session_obj.workspace_id = _resolve_workspace(db, actor_id, data.workspace_id)
    if data.title is not None:
        session_obj.title = data.title.strip() or DEFAULT_TITLE
    if data.start_date is not None or data.end_date is not None:
        new_start = data.start_date if data.start_date is not None else session_obj.start_date
        new_end = data.end_date if data.end_date is not None else session_obj.end_date
        session_obj.start_date, session_obj.end_date = validate_date_range(new_start, new_end)
    if data.agents is not None:
        session_obj.agents = validate_agents(data.agents)
    db.flush()
    return get(db, actor_id, session_id)


def delete(db: Session, actor_id: int, session_id: int) -> dict:
    session_obj, ewkt = _fetch_session(db, actor_id, session_id)
    _require_owner(session_obj, actor_id)
    result = _row_dict(session_obj, ewkt)
    db.delete(session_obj)
    db.flush()
    return result
