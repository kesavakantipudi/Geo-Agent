"""Organization endpoints and RBAC tests."""

from conftest import register_user
from fastapi.testclient import TestClient


def _owner_client(client: TestClient) -> TestClient:
    register_user(client, "org-owner@example.com", "orgowner")
    return client


def test_create_and_list_organizations(client):
    client = _owner_client(client)
    created = client.post("/api/v1/organizations", json={"name": "Acme Maps", "slug": "acme"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Acme Maps"
    assert body["slug"] == "acme"
    assert body["role"] == "owner"

    listed = client.get("/api/v1/organizations")
    assert listed.status_code == 200
    assert any(org["id"] == body["id"] for org in listed.json())


def test_only_members_can_view_organization(client):
    owner = _owner_client(client)
    member = TestClient(owner.app)
    register_user(member, "memberr@example.com", "memberr")

    org = owner.post("/api/v1/organizations", json={"name": "Ltd", "slug": "ltd"}).json()

    outsider = TestClient(owner.app)
    register_user(outsider, "outsider@example.com", "outsider")
    forbidden = outsider.get(f"/api/v1/organizations/{org['id']}")
    assert forbidden.status_code == 404

    added = owner.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"user_id": _user_id(member), "role": "admin"},
    )
    assert added.status_code == 201
    assert added.json()["role"] == "admin"

    detail = member.get(f"/api/v1/organizations/{org['id']}")
    assert detail.status_code == 200
    assert detail.json()["role"] == "admin"


def _user_id(c: TestClient) -> int:
    return c.get("/api/v1/auth/me").json()["id"]


def test_member_cannot_manage_organization(client):
    owner = _owner_client(client)
    member = TestClient(owner.app)
    register_user(member, "memberr@example.com", "memberr")
    member_id = _user_id(member)

    org = owner.post("/api/v1/organizations", json={"name": "Rights", "slug": "rights"}).json()
    owner.post(
        f"/api/v1/organizations/{org['id']}/members", json={"user_id": member_id, "role": "member"}
    )

    denied = member.patch(f"/api/v1/organizations/{org['id']}", json={"name": "Hacked"})
    assert denied.status_code == 403

    denied_add = member.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"user_id": member_id, "role": "admin"},
    )
    assert denied_add.status_code == 403


def test_owner_cannot_be_removed_or_changed_by_others(client):
    owner = _owner_client(client)
    admin = TestClient(owner.app)
    register_user(admin, "adm1n@example.com", "admin1")
    admin_id = _user_id(admin)

    org = owner.post("/api/v1/organizations", json={"name": "Ceo", "slug": "ceo"}).json()
    owner.post(
        f"/api/v1/organizations/{org['id']}/members", json={"user_id": admin_id, "role": "admin"}
    )

    owner_id = _user_id(owner)
    remove = admin.delete(f"/api/v1/organizations/{org['id']}/members/{owner_id}")
    assert remove.status_code == 403

    demote = admin.patch(
        f"/api/v1/organizations/{org['id']}/members/{owner_id}", json={"role": "member"}
    )
    assert demote.status_code == 403


def test_admin_updates_organization(client):
    owner = _owner_client(client)
    admin = TestClient(owner.app)
    register_user(admin, "admin2@example.com", "admin2")

    org = owner.post("/api/v1/organizations", json={"name": "Update", "slug": "update"}).json()
    owner.post(
        f"/api/v1/organizations/{org['id']}/members",
        json={"user_id": _user_id(admin), "role": "admin"},
    )

    updated = admin.patch(
        f"/api/v1/organizations/{org['id']}", json={"name": "Updated Co", "description": "changed"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Co"
