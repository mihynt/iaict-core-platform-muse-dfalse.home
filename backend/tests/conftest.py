import itertools

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store

PLATFORM_KEY = "test-platform-key"
PK = {"X-Platform-Key": PLATFORM_KEY}


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", PLATFORM_KEY)
    store.tenants.clear()
    store.users.clear()
    store.workspaces.clear()
    store.audit.clear()
    store._seq = itertools.count(1)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def register_tenant(client: TestClient, slug: str, name: str | None = None):
    r = client.post("/api/v1/platform/tenants", headers=PK,
                    json={"slug": slug, "name": name or slug})
    assert r.status_code == 201, r.text
    return r


def bootstrap_admin(client: TestClient, slug: str, username: str = "admin"):
    r = client.post("/api/v1/users", headers={"X-Tenant-Id": slug},
                    json={"username": username, "display_name": "Tenant Admin"})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "TENANT_ADMIN"
    return r
