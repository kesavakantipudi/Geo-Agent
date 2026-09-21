"""Authentication flow tests: register, login, refresh rotation, logout."""

from conftest import register_user
from fastapi.testclient import TestClient


def test_register_sets_cookies_and_me(client):
    register_user(client, "alice@example.com", "alice")

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "alice@example.com"
    assert body["username"] == "alice"


def test_register_duplicate_email_conflicts(client):
    register_user(client, "bob@example.com", "bob1")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "bob@example.com", "username": "bob2", "password": "Password-123!"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


def test_login_with_email_and_username(client):
    register_user(client, "carol@example.com", "carol")
    for identifier in ("carol@example.com", "carol"):
        response = client.post(
            "/api/v1/auth/login", json={"identifier": identifier, "password": "Password-123!"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]


def test_login_wrong_password_rejected(client):
    register_user(client, "dave@example.com", "dave")
    response = client.post(
        "/api/v1/auth/login", json={"identifier": "dave", "password": "Wrong-pass-1"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_refresh_rotation_revokes_old_token(client):
    tokens = register_user(client, "erin@example.com", "erin")
    old_refresh = tokens["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new_refresh = rotated.json()["refresh_token"]
    assert new_refresh != old_refresh

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401

    valid = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert valid.status_code == 200


def test_access_token_cannot_be_used_as_refresh(client):
    tokens = register_user(client, "frank@example.com", "frank")
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["access_token"]})
    assert response.status_code == 401


def test_logout_revokes_refresh_token(client):
    tokens = register_user(client, "grace@example.com", "grace")
    response = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401


def test_me_requires_auth(client):
    anon = TestClient(client.app)
    response = anon.get("/api/v1/auth/me")
    assert response.status_code == 401
