"""Shared pytest fixtures.

Each test gets a dedicated PostgreSQL database: it is created, migrated with
Alembic (``alembic upgrade head``), used by the whole test, and finally
dropped. Env vars below are set **before** importing the app so that
``app.main`` builds its engine against the test database.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent

ADMIN_URL = "postgresql://geoagent:geoagent@localhost:54932/geoagent"
TEST_DB = f"geoagent_test_{uuid.uuid4().hex[:10]}"
TEST_URL = f"postgresql+psycopg://geoagent:geoagent@localhost:54932/{TEST_DB}"

os.environ["GEOAGENT_APP_ENV"] = "test"
os.environ["GEOAGENT_AUTH_SECRET_KEY"] = "test-only-secret-key-that-is-at-least-32-chars!!"
os.environ["GEOAGENT_DATABASE_URL"] = TEST_URL
os.environ["GEOAGENT_CORS_ORIGINS"] = "http://localhost:3000"
os.environ["GEOAGENT_RETRIEVAL_STORAGE_DIR"] = str(
    Path(tempfile.gettempdir()) / "geoagent_test_satellite"
)

from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402  (env must be set before import)


def _admin_connection():
    return psycopg.connect(ADMIN_URL, autocommit=True)


@pytest.fixture()
def database() -> Generator[str, None, None]:
    with _admin_connection() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        conn.execute(f"CREATE DATABASE \"{TEST_DB}\" ENCODING 'UTF8'")

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "GEOAGENT_DATABASE_URL": TEST_URL},
        check=True,
        timeout=180,
    )

    yield TEST_URL

    engine.dispose()
    with _admin_connection() as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')


@pytest.fixture()
def client(database: str) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def register_user(
    c: TestClient, email: str, username: str, password: str = "Password-123!"
) -> dict:
    response = c.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password, "full_name": "Test User"},
    )
    assert response.status_code == 201
    return response.json()
