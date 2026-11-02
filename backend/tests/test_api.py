"""Foundation tests: health, tenant context enforcement, tenant isolation."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
A = {"X-Tenant-Id": "tenant-a"}
B = {"X-Tenant-Id": "tenant-b"}


def test_health_is_open():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_context_requires_tenant_header():
    r = client.get("/api/v1/context")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TENANT_REQUIRED"


def test_context_rejects_invalid_tenant():
    r = client.get("/api/v1/context", headers={"X-Tenant-Id": "Bad Tenant!"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TENANT_INVALID"


def test_context_echoes_tenant():
    r = client.get("/api/v1/context", headers=A)
    assert r.status_code == 200
    assert r.json()["tenant_id"] == "tenant-a"


def test_workspace_create_and_list_own_tenant():
    r = client.post("/api/v1/workspaces", headers=A, json={"name": "alpha-yard"})
    assert r.status_code == 201
    assert r.json()["created"] is True
    r = client.get("/api/v1/workspaces", headers=A)
    assert "alpha-yard" in r.json()["items"]


def test_tenant_isolation_other_tenant_cannot_see_workspace():
    client.post("/api/v1/workspaces", headers=A, json={"name": "shared-name"})
    r = client.get("/api/v1/workspaces", headers=B)
    assert "shared-name" not in r.json()["items"]
    assert "alpha-yard" not in r.json()["items"]


def test_same_workspace_name_allowed_in_different_tenants():
    r1 = client.post("/api/v1/workspaces", headers=A, json={"name": "yard-01"})
    r2 = client.post("/api/v1/workspaces", headers=B, json={"name": "yard-01"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r2.json()["created"] is True
