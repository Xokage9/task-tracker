import os
import tempfile

import pytest

# CI may supply an isolated PostgreSQL database. Never use the development .env.
_temp = tempfile.TemporaryDirectory(prefix="tracker-tests-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_temp.name}/core.db")
os.environ["JWT_SECRET"] = "test-jwt-secret-only-" + "x" * 40
os.environ["SERVICE_TOKEN"] = "test-service-token-only-" + "y" * 40

from fastapi.testclient import TestClient
from core.database import Base, engine
from core.main import app


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def register(client, email="owner@example.com", name="Антон"):
    response = client.post("/users/register", json={"name": name, "email": email, "password": "StrongPass123!"})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["user"], {"Authorization": "Bearer " + data["access_token"]}


@pytest.fixture
def owner(client):
    return register(client)


@pytest.fixture
def project(client, owner):
    response = client.post("/projects", json={"name": "Таск-трекер", "description": "Небольшой проект"}, headers=owner[1])
    assert response.status_code == 201
    return response.json()
