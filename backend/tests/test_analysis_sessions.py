"""Phase 3 analysis-session tests (AOI, date range, agent selection, access)."""

from __future__ import annotations

from conftest import register_user
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as SASession

from app.db.session import engine
from app.models import AnalysisSession


def _polygon_aoi():
    return {
        "type": "Polygon",
        "coordinates": [[[80.0, 12.0], [81.0, 12.0], [81.0, 13.0], [80.0, 13.0], [80.0, 12.0]]],
    }


def _owner(client: TestClient) -> TestClient:
    register_user(client, "ses-owner@example.com", "sesowner")
    return client


def _org_and_workspace(client: TestClient, name: str = "Farm Org", slug: str = "farmorg") -> dict:
    org = client.post("/api/v1/organizations", json={"name": name, "slug": slug}).json()
    workspace = client.post(
        f"/api/v1/organizations/{org['id']}/workspaces",
        json={"name": f"{name} WS", "slug": f"{slug}-ws"},
    ).json()
    return {"org": org, "workspace": workspace}


def _create_session(client: TestClient, workspace_id: int, **overrides):
    payload = {
        "title": "Rice field analysis",
        "workspace_id": workspace_id,
        "aoi": _polygon_aoi(),
        "start_date": "2023-06-01",
        "end_date": "2023-09-30",
        "agents": ["agri", "aqua"],
    }
    payload.update(overrides)
    return client.post("/api/v1/analysis-sessions", json=payload)


def test_create_get_list_update_delete(client):
    client = _owner(client)
    ws_id = _org_and_workspace(client)["workspace"]["id"]

    created = _create_session(client, ws_id)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "draft"
    assert body["agents"] == ["agri", "aqua"]
    assert body["start_date"] == "2023-06-01"
    assert body["aoi"]["type"] == "Polygon"
    assert body["bbox"] == [80.0, 12.0, 81.0, 13.0]
    assert body["area_m2_approx"] > 1e9
    session_id = body["id"]

    listed = client.get("/api/v1/analysis-sessions")
    assert any(s["id"] == session_id for s in listed.json())

    fetched = client.get(f"/api/v1/analysis-sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Rice field analysis"

    updated = client.patch(
        f"/api/v1/analysis-sessions/{session_id}",
        json={"title": "Updated crop analysis", "agents": ["weather"]},
    )
    assert updated.status_code == 200
    assert updated.json()["agents"] == ["weather"]

    deleted = client.delete(f"/api/v1/analysis-sessions/{session_id}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/analysis-sessions/{session_id}")
    assert gone.status_code == 404


def test_create_requires_area_polygon(client):
    client = _owner(client)
    response = client.post(
        "/api/v1/analysis-sessions",
        json={"aoi": {"type": "Point", "coordinates": [80.0, 12.0]}, "agents": ["agri"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aoi_not_polygon"


def test_invalid_agent_rejected(client):
    client = _owner(client)
    response = _create_session(client, None, agents=["crops"])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_agents"


def test_empty_agents_rejected(client):
    client = _owner(client)
    response = _create_session(client, None, agents=[])
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_agents"


def test_end_before_start_rejected(client):
    client = _owner(client)
    response = _create_session(client, None, start_date="2023-09-30", end_date="2023-06-01")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_only_one_date_edge_rejected(client):
    client = _owner(client)
    response = _create_session(client, None, start_date="2023-06-01", end_date=None)
    assert response.status_code == 400


def test_excessively_future_date_rejected(client):
    client = _owner(client)
    response = _create_session(client, None, start_date="2124-01-01", end_date="2124-02-01")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"


def test_aoi_and_saved_location_conflict(client):
    client = _owner(client)
    location = client.post(
        "/api/v1/saved-locations",
        json={
            "name": "Coverage",
            "location_type": "polygon",
            "geometry": _polygon_aoi(),
        },
    ).json()
    response = _create_session(client, None, saved_location_id=location["id"])
    assert response.status_code == 400


def test_aoi_from_saved_location(client):
    client = _owner(client)
    location = client.post(
        "/api/v1/saved-locations",
        json={"name": "Coverage", "geometry": _polygon_aoi()},
    ).json()
    response = client.post(
        "/api/v1/analysis-sessions",
        json={
            "title": "From saved",
            "saved_location_id": location["id"],
            "agents": ["aqua"],
        },
    )
    assert response.status_code == 201
    assert response.json()["aoi"]["type"] == "Polygon"
    assert response.json()["area_m2_approx"] > 1e9


def test_foreign_workspace_rejected(client):
    owner = _owner(client)
    ws_id = _org_and_workspace(owner)["workspace"]["id"]

    other = TestClient(owner.app)
    register_user(other, "ses-other@example.com", "sesother")
    response = _create_session(other, ws_id)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workspace_not_found"


def test_sessions_are_private_without_workspace(client):
    owner = _owner(client)
    created = _create_session(owner, None).json()

    from fastapi.testclient import TestClient

    other = TestClient(owner.app)
    register_user(other, "ses-private@example.com", "sesprivate")
    response = other.get(f"/api/v1/analysis-sessions/{created['id']}")
    assert response.status_code == 404
    patch = other.patch(f"/api/v1/analysis-sessions/{created['id']}", json={"title": "Hijack"})
    assert patch.status_code == 404
    delete = other.delete(f"/api/v1/analysis-sessions/{created['id']}")
    assert delete.status_code == 404


def test_workspace_member_can_view_not_edit(client):
    owner = _owner(client)
    other = TestClient(owner.app)
    register_user(other, "ses-member@example.com", "sesmember")

    org = owner.post("/api/v1/organizations", json={"name": "Team Org", "slug": "teamorg"}).json()
    member_id = other.get("/api/v1/auth/me").json()["id"]
    owner.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"user_id": member_id, "role": "member"},
    )
    ws = owner.post(
        f"/api/v1/organizations/{org['id']}/workspaces",
        json={"name": "Team WS", "slug": "teamws"},
    ).json()

    created = _create_session(owner, ws["id"]).json()
    session_id = created["id"]

    view = other.get(f"/api/v1/analysis-sessions/{session_id}")
    assert view.status_code == 200

    patch = other.patch(f"/api/v1/analysis-sessions/{session_id}", json={"title": "Nope"})
    assert patch.status_code == 404


def test_list_filtered_by_workspace(client):
    owner = _owner(client)
    ws1 = _org_and_workspace(owner, "Org A", "orga")["workspace"]
    ws2 = _org_and_workspace(owner, "Org B", "orgb")["workspace"]

    _create_session(owner, ws1["id"]).json()
    _create_session(owner, ws2["id"]).json()

    filtered = client.get(f"/api/v1/analysis-sessions?workspace_id={ws1['id']}")
    ids = [s["id"] for s in filtered.json()]
    assert len(ids) == 1


def test_non_draft_cannot_be_edited(client):
    client = _owner(client)
    created = _create_session(client, None).json()
    session_id = created["id"]

    with SASession(engine) as session:
        row = session.get(AnalysisSession, session_id)
        row.status = "completed"
        session.commit()

    response = client.patch(f"/api/v1/analysis-sessions/{session_id}", json={"title": "Late"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "session_not_draft"


def test_unauthenticated_rejected(client):
    response = client.get("/api/v1/analysis-sessions")
    assert response.status_code == 401
