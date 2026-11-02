import os

# Optional: run the whole suite against a real PostgreSQL backend.
#   TEST_DATABASE_URL=postgresql://user:pass@host/db pytest            (psycopg backend)
#   TEST_BACKEND=worker TEST_DATABASE_URL=postgresql://... pytest      (pg8000/Hyperdrive backend)
# The URL is bridged to DATABASE_URL before the app (and its store) imports.
if os.environ.get("TEST_BACKEND") == "worker":
    os.environ["IAICT_BACKEND"] = "hyperdrive"
elif os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store

PLATFORM_KEY = "test-platform-key"
PK = {"X-Platform-Key": PLATFORM_KEY}


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", PLATFORM_KEY)
    if os.environ.get("TEST_BACKEND") == "worker" and getattr(store, "_impl", None) is None:
        from urllib.parse import urlparse

        u = urlparse(os.environ["TEST_DATABASE_URL"])
        store.bind_params(host=u.hostname, port=u.port or 5432, user=u.username,
                          password=u.password or "", database=u.path.lstrip("/"))
    store.reset()
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
