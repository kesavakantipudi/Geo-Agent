"""Shared builders and fake providers for the Phase 4 satellite tests.

No live network access: every provider/service ``httpx.Client`` is routed
through an ``httpx.MockTransport`` handler.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[77.5, 12.9], [77.6, 12.9], [77.6, 13.0], [77.5, 13.0], [77.5, 12.9]]],
}

BLOB_HOST = "blob.example.test"


def stac_item(
    scene_id: str = "S2A_T43PFJ_20240705T040000",
    datetime: str = "2024-07-05T04:00:00Z",
    cloud_cover: float = 5.0,
    assets: list[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    assets = assets or [
        ("visual", f"https://{BLOB_HOST}/container/{scene_id}-visual.tif", "image/tiff"),
        ("B08", f"https://{BLOB_HOST}/container/{scene_id}-B08.tif", "image/tiff"),
    ]
    return {
        "type": "Feature",
        "id": scene_id,
        "geometry": POLYGON,
        "bbox": [77.5, 12.9, 77.6, 13.0],
        "properties": {
            "datetime": datetime,
            "eo:cloud_cover": cloud_cover,
            "platform": "sentinel-2a",
            "gsd": 10,
            "constellation": "sentinel-2",
            "instrument": "msi",
            "processing:level": "L2A",
            "title": f"Scene {scene_id}",
        },
        "assets": {
            key: {"href": href, "type": media_type, "file:size": 1000}
            for key, href, media_type in assets
        },
    }


def scene_collection(*items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(items)}


def route_handler(
    mpc_items: list[dict[str, Any]] | None = None,
    cdse_items: list[dict[str, Any]] | None = None,
    *,
    downloaded_content: bytes = b"asset-bytes",
    captured: list[dict[str, Any]] | None = None,
):
    """Build an ``httpx.MockTransport`` handler covering search/sign/download."""
    mpc_items = mpc_items if mpc_items is not None else [stac_item()]
    cdse_items = cdse_items if cdse_items is not None else []

    def handler(request) -> Any:
        url = str(request.url)
        if captured is not None:
            captured.append({"url": url, "body": request.content})
        path = urlsplit(url).path
        if path.endswith("/search"):
            if "stac.dataspace" in url:
                return ok_json(scene_collection(*cdse_items))
            return ok_json(scene_collection(*mpc_items))
        if "sas/v1/sign" in url:
            query = request.url.params.get("href", "")
            return ok_json({"href": f"{query}?se=2024-12-31T00%3A00%3A00Z&sig=TESTTOKEN"})
        if BLOB_HOST in url:
            import httpx

            return httpx.Response(
                200,
                content=downloaded_content,
                headers={"content-length": str(len(downloaded_content))},
            )
        return ok_json({"detail": "not found"}, status=404)

    return handler


def ok_json(payload: Any, *, status: int = 200, headers: dict | None = None) -> Any:
    import httpx

    return httpx.Response(status, json=payload, headers=headers or {})


def install_client_mock(monkeypatch, handler) -> None:
    """Route all provider/service ``httpx.Client`` calls through ``MockTransport``."""
    import httpx as httpx_module

    real_client = httpx_module.Client

    def client_factory(*args, **kwargs):
        if "transport" in kwargs:
            return real_client(*args, **kwargs)
        return real_client(*args, **kwargs, transport=httpx_module.MockTransport(handler))

    monkeypatch.setattr(httpx_module, "Client", client_factory)


def register(client, email: str) -> None:
    from conftest import register_user

    register_user(client, email, email.split("@")[0])


def create_session(client, start: str = "2024-07-01", end: str = "2024-07-31") -> int:
    response = client.post(
        "/api/v1/analysis-sessions",
        json={
            "title": "Satellite test session",
            "aoi": POLYGON,
            "start_date": start,
            "end_date": end,
            "agents": ["agri"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]
