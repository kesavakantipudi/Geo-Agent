"""Health endpoint tests."""


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_database_health(client):
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["postgis"] is True
    assert "3.4" in body["postgis_version"]


def test_health_error_shape_is_standard(client):
    response = client.get("/api/v1/no-such-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
