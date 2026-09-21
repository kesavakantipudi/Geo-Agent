"""Satellite scene discovery, persistence, and bounded asset retrieval.

Discovery is session-centric: scenes are found for an authorized analysis
session's AOI and date range (or for an inline AOI + dates), fetched from every
enabled provider, deduplicated, and cached with their unsigned asset ``href``
values. Downloads are on-demand, size/time-bounded, restricted to allow-listed
hosts, and leave a persisted retrieval record per scene/key. Signed URLs are
generated at download time and are never stored or returned to clients.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from geoalchemy2.functions import ST_AsEWKT
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import bad_request, not_found
from app.models import (
    AnalysisSession,
    SatelliteRetrieval,
    SatelliteScene,
    SatelliteSceneAsset,
    SatelliteSceneDiscovery,
    Workspace,
)
from app.schemas import satellite as sat_schemas
from app.services import analysis_session_service, workspace_service
from app.services.geometry import geojson_from_ewkt, parse_geometry, validate_geometry
from app.services.satellite import (
    SatelliteError,
    SatelliteRetrievalUnsupported,
    get_enabled_provider_names,
    get_providers,
)

DOWNLOAD_CHUNK_SIZE = 131_072


def _parse_acquisition_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _safe_key(key: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (key or ""))[:80]


def search_scenes(
    db: Session, actor_id: int, data: sat_schemas.SceneSearchRequest
) -> dict[str, Any]:
    """Discover scenes for a session (or inline AOI + dates) across providers."""
    wanted = _resolve_providers(data.providers)

    session_obj: AnalysisSession | None = None
    if data.analysis_session_id is not None:
        session = analysis_session_service.get(db, actor_id, data.analysis_session_id)
        aoi = data.aoi if data.aoi is not None else session.get("aoi")
        if aoi is None:
            raise bad_request(
                "The analysis session has no AOI to search against.",
                code="session_has_no_aoi",
            )
        start = data.start_date if data.start_date is not None else session.get("start_date")
        end = data.end_date if data.end_date is not None else session.get("end_date")
        session_obj = db.get(AnalysisSession, session["id"])
    else:
        aoi = data.aoi
        start, end = data.start_date, data.end_date

    if aoi is None:
        raise bad_request("Provide an AOI or analysis_session_id.", code="aoi_required")
    start, end = analysis_session_service.validate_date_range(start, end)
    if start is None:
        raise bad_request(
            "start_date and end_date are required for scene discovery.",
            code="date_range_required",
        )

    info = validate_geometry(aoi, name="aoi", require_area=True)
    bbox = tuple(float(value) for value in info["bbox"])

    settings = get_settings()
    limit = max(1, min(data.limit, settings.satellite_max_scenes_per_provider))
    max_cloud_cover = min(data.max_cloud_cover, settings.satellite_max_cloud_cover)

    providers = [p for p in get_providers() if p.name in wanted]
    if not providers:
        raise bad_request("No satellite provider is currently enabled.", code="satellite_disabled")

    scenes: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    truncated = False
    for provider in providers:
        try:
            found = provider.search_scenes(
                bbox=bbox,
                start=start,
                end=end,
                limit=limit,
                max_cloud_cover=max_cloud_cover,
            )
        except SatelliteError as exc:
            statuses.append({"provider": provider.name, "scenes": 0, "error": str(exc)})
            continue
        persisted = 0
        for scene in found:
            row = _persist_scene(
                db, actor_id, session_obj.id if session_obj else None, scene, max_cloud_cover
            )
            if row is None:
                continue
            persisted += 1
            scenes.append(_scene_summary(row, scene.get("geometry")))
        truncated = truncated or len(found) >= limit
        statuses.append({"provider": provider.name, "scenes": persisted, "error": None})

    db.commit()
    return {
        "scenes": scenes,
        "providers": statuses,
        "truncated": truncated,
    }


def list_scenes_for_session(
    db: Session, actor_id: int, analysis_session_id: int
) -> list[dict[str, Any]]:
    """Return scenes previously discovered for a session (most recent first)."""
    analysis_session_service.get(db, actor_id, analysis_session_id)
    rows = db.execute(
        select(SatelliteScene, ST_AsEWKT(SatelliteScene.geometry))
        .join(SatelliteSceneDiscovery, SatelliteSceneDiscovery.scene_id == SatelliteScene.id)
        .where(SatelliteSceneDiscovery.analysis_session_id == analysis_session_id)
        .order_by(SatelliteScene.acquisition_date.desc(), SatelliteScene.id.desc())
    ).all()
    return [_scene_summary(scene, geojson_from_ewkt(ewkt)) for scene, ewkt in rows]


def get_scene(db: Session, actor_id: int, scene_id: int) -> dict[str, Any]:
    """Authorized scene summary (geometry as GeoJSON)."""
    scene, ewkt = _scene_for_user(db, actor_id, scene_id)
    geometry = geojson_from_ewkt(ewkt) if ewkt else None
    return _scene_summary(scene, geometry)


def retrieve_assets(
    db: Session,
    actor_id: int,
    scene_id: int,
    asset_keys: list[str],
    analysis_session_id: int | None,
) -> list[SatelliteRetrieval]:
    """Download up to ``retrieval_max_assets_per_scene`` assets, bounded."""
    scene, _ = _scene_for_user(db, actor_id, scene_id)

    settings = get_settings()
    max_assets = max(1, settings.retrieval_max_assets_per_scene)
    keys = list(dict.fromkeys(asset_keys))[:max_assets]
    if not keys:
        raise bad_request("Select at least one asset to download.", code="assets_required")

    assets_by_key = {asset.asset_key: asset for asset in scene.assets}
    missing = [key for key in keys if key not in assets_by_key]
    if missing:
        raise bad_request(
            f"Unknown asset key(s): {', '.join(missing)}.", code="scene_asset_not_found"
        )

    if analysis_session_id is not None:
        session = analysis_session_service.get(db, actor_id, analysis_session_id)
        session_id = session["id"]
    else:
        session_id = None

    provider = _provider_named(scene.provider)

    now = datetime.now(UTC)
    records: list[SatelliteRetrieval] = []
    for key in keys:
        record = SatelliteRetrieval(
            scene_id=scene.id,
            analysis_session_id=session_id,
            requested_by=actor_id,
            asset_key=key,
            status="queued",
            requested_at=now,
        )
        db.add(record)
        db.flush()
        try:
            url, headers = provider.download_url({"href": assets_by_key[key].href})
            if not _host_allowed(assets_by_key[key].href, url, settings):
                raise SatelliteError("The download URL is not on the allow-listed host.")
            stored_path, size_bytes = _download_asset(url, headers, record, settings)
            record.status = "completed"
            record.stored_path = stored_path
            record.size_bytes = size_bytes
            record.error = None
        except (SatelliteError, SatelliteRetrievalUnsupported) as exc:
            record.status = "failed"
            record.error = str(exc)
        record.completed_at = datetime.now(UTC)
        records.append(record)

    db.commit()
    return records


def list_retrievals(db: Session, actor_id: int, scene_id: int) -> list[SatelliteRetrieval]:
    _scene_for_user(db, actor_id, scene_id)
    return (
        db.execute(
            select(SatelliteRetrieval)
            .where(SatelliteRetrieval.scene_id == scene_id)
            .order_by(SatelliteRetrieval.requested_at.desc())
        )
        .scalars()
        .all()
    )


def delete_retrieval(db: Session, actor_id: int, retrieval_id: int) -> None:
    record = db.execute(
        select(SatelliteRetrieval).where(SatelliteRetrieval.id == retrieval_id)
    ).scalar_one_or_none()
    if record is None or record.requested_by != actor_id:
        raise not_found("Retrieval not found.", code="retrieval_not_found")
    if record.stored_path:
        (Path(get_settings().retrieval_storage_dir) / record.stored_path).unlink(missing_ok=True)
    db.delete(record)
    db.flush()
    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_providers(requested: list[str] | None) -> list[str]:
    enabled = get_enabled_provider_names()
    wanted = [name.strip().lower() for name in requested] if requested else enabled
    if not wanted:
        raise bad_request("Satellite scene discovery is disabled.", code="satellite_disabled")
    unknown = [name for name in wanted if name not in enabled]
    if unknown:
        raise bad_request(
            f"Unknown or disabled satellite provider(s): {', '.join(unknown)}.",
            code="satellite_provider_not_enabled",
        )
    return wanted


def _provider_named(name: str):
    for provider in get_providers():
        if provider.name == name:
            return provider
    raise SatelliteRetrievalUnsupported(
        f"Asset downloads require the '{name}' provider to be enabled."
    )


def _host_allowed(original_href: str, download_url: str, settings) -> bool:
    allowed_hosts = {
        host for host in (settings.retrieval_url_allowlist or "").split(",") if host.strip()
    }
    try:
        original_host = urlparse(original_href).hostname
    except ValueError:
        original_host = None
    if original_host:
        allowed_hosts.add(original_host)
    try:
        parsed = urlparse(download_url)
        return parsed.scheme == "https" and parsed.hostname in allowed_hosts
    except ValueError:
        return False


def _download_asset(
    url: str, headers: dict[str, str], record: SatelliteRetrieval, settings
) -> tuple[str, int]:
    storage_dir = Path(settings.retrieval_storage_dir)
    target_dir = storage_dir / str(record.scene_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{record.id}_{_safe_key(record.asset_key)}.download"
    max_bytes = max(1, settings.retrieval_max_bytes)
    timeout = settings.retrieval_timeout_seconds
    written = 0
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                content_length = int(response.headers.get("content-length") or 0)
                if content_length > max_bytes:
                    raise SatelliteError("The asset exceeds the maximum allowed download size.")
                with target.open("wb") as file_handle:
                    for chunk in response.iter_bytes(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        written += len(chunk)
                        if written > max_bytes:
                            raise SatelliteError(
                                "The asset exceeds the maximum allowed download size."
                            )
                        file_handle.write(chunk)
    except SatelliteError:
        target.unlink(missing_ok=True)
        raise
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        target.unlink(missing_ok=True)
        raise SatelliteError(f"The asset could not be downloaded: {exc}") from exc
    if written == 0:
        target.unlink(missing_ok=True)
        raise SatelliteError("The asset download returned no data.")
    return str(target.relative_to(storage_dir)), written


def _persist_scene(
    db: Session,
    actor_id: int,
    analysis_session_id: int | None,
    scene: dict[str, Any],
    max_cloud_cover: float,
) -> SatelliteScene | None:
    acquisition_date = _parse_acquisition_date(scene.get("acquisition_date"))
    if acquisition_date is None:
        return None
    cloud_cover = scene.get("cloud_cover")
    if cloud_cover is not None and float(cloud_cover) > max_cloud_cover:
        return None

    provider = scene.get("provider")
    scene_id = scene.get("scene_id")
    row = db.execute(
        select(SatelliteScene).where(
            SatelliteScene.provider == provider, SatelliteScene.scene_id == scene_id
        )
    ).scalar_one_or_none()
    geometry = scene.get("geometry")
    geometry_wkt = parse_geometry("geometry", geometry) if isinstance(geometry, dict) else None
    metadata: dict[str, Any] = dict(scene.get("metadata") or {})
    if scene.get("bbox"):
        metadata["_bbox"] = scene["bbox"]

    if row is None:
        row = SatelliteScene(
            provider=provider,
            scene_id=scene_id,
            platform=scene.get("platform"),
            acquisition_date=acquisition_date,
            cloud_cover=cloud_cover,
            resolution_m=scene.get("resolution_m"),
            geometry=geometry_wkt,
            metadata_=metadata,
        )
        db.add(row)
        db.flush()
    else:
        row.acquisition_date = acquisition_date
        row.cloud_cover = cloud_cover
        row.resolution_m = scene.get("resolution_m")
        if geometry_wkt is not None:
            row.geometry = geometry_wkt
        row.metadata_ = metadata

    assets_by_key = {asset.asset_key: asset for asset in row.assets}
    for asset in scene.get("assets") or []:
        key = asset.get("key")
        if not key:
            continue
        existing = assets_by_key.get(key)
        if existing is None:
            db.add(
                SatelliteSceneAsset(
                    scene_id=row.id,
                    asset_key=key,
                    href=asset.get("href"),
                    media_type=asset.get("media_type"),
                    size_bytes=asset.get("size_bytes"),
                )
            )
        else:
            existing.href = asset.get("href")
            existing.media_type = asset.get("media_type")
            existing.size_bytes = asset.get("size_bytes")

    if analysis_session_id is not None:
        discovery = db.execute(
            select(SatelliteSceneDiscovery).where(
                SatelliteSceneDiscovery.scene_id == row.id,
                SatelliteSceneDiscovery.analysis_session_id == analysis_session_id,
            )
        ).scalar_one_or_none()
        if discovery is None:
            db.add(
                SatelliteSceneDiscovery(
                    scene_id=row.id,
                    analysis_session_id=analysis_session_id,
                    discovered_by=actor_id,
                )
            )
    db.flush()
    db.refresh(row, ["assets"])
    return row


def _scene_summary(scene: SatelliteScene, geometry: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": scene.id,
        "provider": scene.provider,
        "scene_id": scene.scene_id,
        "platform": scene.platform,
        "acquisition_date": scene.acquisition_date,
        "cloud_cover": scene.cloud_cover,
        "resolution_m": scene.resolution_m,
        "geometry": geometry,
        "bbox": scene.metadata_.get("_bbox") if scene.metadata_ else None,
        "metadata": {k: v for k, v in (scene.metadata_ or {}).items() if k != "_bbox"},
        "created_at": scene.created_at,
        "assets": [
            {
                "key": asset.asset_key,
                "href": asset.href,
                "media_type": asset.media_type,
                "size_bytes": asset.size_bytes,
            }
            for asset in scene.assets
        ],
    }


def _can_access_scene(db: Session, actor_id: int, scene_id: int) -> bool:
    discoveries = (
        db.execute(
            select(SatelliteSceneDiscovery).where(SatelliteSceneDiscovery.scene_id == scene_id)
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


def _scene_for_user(db: Session, actor_id: int, scene_id: int) -> tuple[SatelliteScene, str | None]:
    row = db.execute(
        select(SatelliteScene, ST_AsEWKT(SatelliteScene.geometry)).where(
            SatelliteScene.id == scene_id
        )
    ).one_or_none()
    if row is None or not _can_access_scene(db, actor_id, scene_id):
        raise not_found("Satellite scene not found.", code="satellite_scene_not_found")
    return row[0], row[1]
