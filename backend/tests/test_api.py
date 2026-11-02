"""Foundation tests: health, tenant context enforcement, tenant isolation."""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "tenant-a"}
B = {"X-Tenant-Id": "tenant-b"}
A_ADMIN = {"X-Tenant-Id": "tenant-a", "X-Actor": "admin"}
B_ADMIN = {"X-Tenant-Id": "tenant-b", "X-Actor": "admin"}


@pytest.fixture()
def two_tenants(client: TestClient):
    register_tenant(client, "tenant-a")
    register_tenant(client, "tenant-b")
    bootstrap_admin(client, "tenant-a")
    bootstrap_admin(client, "tenant-b")
    return client


def test_health_is_open(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_context_requires_tenant_header(client):
    r = client.get("/api/v1/context")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TENANT_REQUIRED"


def test_context_rejects_invalid_tenant_format(client):
    r = client.get("/api/v1/context", headers={"X-Tenant-Id": "Bad Tenant!"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TENANT_INVALID"


def test_context_rejects_unregistered_tenant(client):
    r = client.get("/api/v1/context", headers={"X-Tenant-Id": "ghost-tenant"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "TENANT_UNKNOWN"


def test_context_echoes_registered_tenant(two_tenants):
    r = two_tenants.get("/api/v1/context", headers=A)
    assert r.status_code == 200
    assert r.json()["tenant_id"] == "tenant-a"


def test_workspace_create_and_list_own_tenant(two_tenants):
    r = two_tenants.post("/api/v1/workspaces", headers=A_ADMIN, json={"name": "alpha-yard"})
    assert r.status_code == 201
    assert r.json()["created"] is True
    r = two_tenants.get("/api/v1/workspaces", headers=A)
    assert "alpha-yard" in r.json()["items"]


def test_tenant_isolation_other_tenant_cannot_see_workspace(two_tenants):
    two_tenants.post("/api/v1/workspaces", headers=A_ADMIN, json={"name": "shared-name"})
    r = two_tenants.get("/api/v1/workspaces", headers=B)
    assert "shared-name" not in r.json()["items"]
    assert "alpha-yard" not in r.json()["items"]


def test_same_workspace_name_allowed_in_different_tenants(two_tenants):
    r1 = two_tenants.post("/api/v1/workspaces", headers=A_ADMIN, json={"name": "yard-01"})
    r2 = two_tenants.post("/api/v1/workspaces", headers=B_ADMIN, json={"name": "yard-01"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r2.json()["created"] is True
