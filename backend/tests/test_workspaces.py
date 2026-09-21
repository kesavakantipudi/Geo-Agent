"""Workspace endpoints and access control tests."""

from conftest import register_user
from fastapi.testclient import TestClient


def _org_id(c: TestClient) -> int:
    return c.post("/api/v1/organizations", json={"name": "Map Co", "slug": "mapco"}).json()["id"]


def test_create_workspace_and_list(client):
    org_id = _org_id(_owner(client))
    created = client.post(
        f"/api/v1/organizations/{org_id}/workspaces", json={"name": "Field Survey", "slug": "field"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["role"] == "manager"

    listed = client.get(f"/api/v1/organizations/{org_id}/workspaces")
    assert listed.status_code == 200
    assert any(w["id"] == body["id"] for w in listed.json())

    all_workspaces = client.get("/api/v1/workspaces")
    assert any(w["id"] == body["id"] for w in all_workspaces.json())


def test_org_member_sees_workspace_but_cannot_manage(client):
    owner = _owner(client)
    member = TestClient(owner.app)
    register_user(member, "ws-member@example.com", "wsmember")
    org_id = owner.post("/api/v1/organizations", json={"name": "Perm", "slug": "perm"}).json()["id"]
    owner.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": member.get("/api/v1/auth/me").json()["id"], "role": "member"},
    )

    ws = owner.post(
        f"/api/v1/organizations/{org_id}/workspaces", json={"name": "Shared", "slug": "shared"}
    ).json()

    view = member.get(f"/api/v1/workspaces/{ws['id']}")
    assert view.status_code == 200
    assert view.json()["role"] == "member"

    denied = member.patch(f"/api/v1/workspaces/{ws['id']}", json={"name": "Touched"})
    assert denied.status_code == 403


def test_outsider_cannot_see_workspace(client):
    owner = _owner(client)
    org_id = _org_id(owner)
    ws = owner.post(
        f"/api/v1/organizations/{org_id}/workspaces", json={"name": "Private", "slug": "private"}
    ).json()

    outsider = TestClient(owner.app)
    register_user(outsider, "ws-outsider@example.com", "wsoutsider")
    response = outsider.get(f"/api/v1/workspaces/{ws['id']}")
    assert response.status_code == 404


def _owner(client: TestClient) -> TestClient:
    register_user(client, "ws-owner@example.com", "wsowner")
    return client
