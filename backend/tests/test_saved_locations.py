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
