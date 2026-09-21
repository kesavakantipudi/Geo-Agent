"""Saved-location CRUD tests (including PostGIS geometry round-trips)."""

from conftest import register_user


def _secret(client):
    register_user(client, "loc-owner@example.com", "locowner")
    return client


def test_create_list_get_update_delete(client):
    client = _secret(client)
    point = {
        "name": "HQ",
        "center_lat": 12.9716,
        "center_lon": 77.5946,
        "location_type": "point",
        "geometry": {"type": "Point", "coordinates": [77.5946, 12.9716]},
    }
    created = client.post("/api/v1/saved-locations", json=point)
    assert created.status_code == 201
    body = created.json()
    assert body["geometry"] is not None
    location_id = body["id"]

    listed = client.get("/api/v1/saved-locations")
    assert any(loc["id"] == location_id for loc in listed.json())

    fetched = client.get(f"/api/v1/saved-locations/{location_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "HQ"
    assert "POINT" in fetched.json()["geometry"]

    updated = client.patch(f"/api/v1/saved-locations/{location_id}", json={"name": "Regional HQ"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Regional HQ"

    deleted = client.delete(f"/api/v1/saved-locations/{location_id}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/saved-locations/{location_id}")
    assert gone.status_code == 404


def test_locations_are_private_to_owner(client):
    owner = _secret(client)
    created = owner.post(
        "/api/v1/saved-locations",
        json={"name": "Spot", "center_lat": 0.0, "center_lon": 0.0},
    ).json()

    from fastapi.testclient import TestClient

    other = TestClient(owner.app)
    register_user(other, "loc-other@example.com", "locother")
    response = other.get(f"/api/v1/saved-locations/{created['id']}")
    assert response.status_code == 404


def test_polygon_autofills_type_center_and_info(client):
    client = _secret(client)
    polygon = {
        "type": "Polygon",
        "coordinates": [[[80.0, 12.0], [81.0, 12.0], [81.0, 13.0], [80.0, 13.0], [80.0, 12.0]]],
    }
    created = client.post("/api/v1/saved-locations", json={"name": "Field", "geometry": polygon})
    assert created.status_code == 201
    body = created.json()
    assert body["location_type"] == "polygon"
    assert body["geometry_type"] == "Polygon"
    assert body["bbox"] == [80.0, 12.0, 81.0, 13.0]
    assert body["centroid"]["lon"] == 80.5
    assert body["area_m2_approx"] > 1e9
    assert body["center_lat"] is not None
    assert body["center_lon"] is not None


def test_invalid_geometry_rejected(client):
    client = _secret(client)
    open_ring = {
        "type": "Polygon",
        "coordinates": [[[80.0, 12.0], [81.0, 12.0], [81.0, 13.0], [80.0, 13.0]]],
    }
    response = client.post("/api/v1/saved-locations", json={"name": "Bad", "geometry": open_ring})
    assert response.status_code == 400
    assert "closed ring" in response.json()["error"]["message"]


def test_workspace_membership_enforced_on_create(client):
    owner = _secret(client)
    org = owner.post("/api/v1/organizations", json={"name": "Map Org", "slug": "maporg"}).json()
    ws = owner.post(
        f"/api/v1/organizations/{org['id']}/workspaces",
        json={"name": "Map WS", "slug": "mapws"},
    ).json()

    from fastapi.testclient import TestClient

    other = TestClient(owner.app)
    register_user(other, "loc-ws@example.com", "locws")
    response = other.post(
        "/api/v1/saved-locations",
        json={"name": "Snoop", "workspace_id": ws["id"], "center_lat": 0.0, "center_lon": 0.0},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "workspace_not_found"

    ok = owner.post(
        "/api/v1/saved-locations",
        json={"name": "Mine", "workspace_id": ws["id"], "center_lat": 0.0, "center_lon": 0.0},
    )
    assert ok.status_code == 201
