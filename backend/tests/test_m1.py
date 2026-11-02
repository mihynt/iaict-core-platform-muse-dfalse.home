"""M1 foundation tests: tenant registry/lifecycle, identity & roles, audit."""
import pytest
from fastapi.testclient import TestClient

from tests.conftest import PK, bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "tenant-a"}
A_ADMIN = {"X-Tenant-Id": "tenant-a", "X-Actor": "admin"}


# ---- platform key & registry -------------------------------------------

def test_platform_endpoints_reject_missing_key(client):
    r = client.get("/api/v1/platform/tenants")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "PLATFORM_KEY_INVALID"


def test_platform_endpoints_reject_wrong_key(client):
    r = client.get("/api/v1/platform/tenants", headers={"X-Platform-Key": "nope"})
    assert r.status_code == 401


def test_platform_disabled_when_key_not_configured(client, monkeypatch):
    monkeypatch.delenv("PLATFORM_ADMIN_KEY", raising=False)
    r = client.get("/api/v1/platform/tenants", headers=PK)
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "PLATFORM_DISABLED"


def test_tenant_create_get_list(client):
    register_tenant(client, "tenant-a", "Tenant A")
    r = client.get("/api/v1/platform/tenants/tenant-a", headers=PK)
    assert r.status_code == 200
    assert r.json()["status"] == "ACTIVE"
    r = client.get("/api/v1/platform/tenants", headers=PK)
    assert [t["slug"] for t in r.json()["items"]] == ["tenant-a"]


def test_tenant_create_duplicate_conflict(client):
    register_tenant(client, "tenant-a")
    r = client.post("/api/v1/platform/tenants", headers=PK,
                    json={"slug": "tenant-a", "name": "Again"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "TENANT_EXISTS"


def test_tenant_create_invalid_slug(client):
    r = client.post("/api/v1/platform/tenants", headers=PK,
                    json={"slug": "Bad Slug", "name": "X"})
    assert r.status_code in (400, 422)


def test_tenant_get_missing_404(client):
    r = client.get("/api/v1/platform/tenants/nope", headers=PK)
    assert r.status_code == 404


def test_suspended_tenant_is_blocked_and_reactivation_restores(client):
    register_tenant(client, "tenant-a")
    r = client.patch("/api/v1/platform/tenants/tenant-a/status", headers=PK,
                     json={"status": "SUSPENDED"})
    assert r.status_code == 200
    r = client.get("/api/v1/context", headers=A)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "TENANT_SUSPENDED"
    client.patch("/api/v1/platform/tenants/tenant-a/status", headers=PK,
                 json={"status": "ACTIVE"})
    r = client.get("/api/v1/context", headers=A)
    assert r.status_code == 200


# ---- identity ------------------------------------------------------------

def test_bootstrap_first_user_forced_admin(client):
    register_tenant(client, "tenant-a")
    r = client.post("/api/v1/users", headers=A,
                    json={"username": "founder", "display_name": "Founder", "role": "VIEWER"})
    assert r.status_code == 201
    assert r.json()["role"] == "TENANT_ADMIN"


def test_second_user_requires_admin_actor(client):
    register_tenant(client, "tenant-a")
    bootstrap_admin(client, "tenant-a")
    r = client.post("/api/v1/users", headers=A,
                    json={"username": "second", "display_name": "Second"})
    assert r.status_code == 401  # no actor after bootstrap
    r = client.post("/api/v1/users", headers=A_ADMIN,
                    json={"username": "second", "display_name": "Second", "role": "OPERATOR"})
    assert r.status_code == 201
    assert r.json()["role"] == "OPERATOR"


def test_non_admin_actor_cannot_create_user(client):
    register_tenant(client, "tenant-a")
    bootstrap_admin(client, "tenant-a")
    client.post("/api/v1/users", headers=A_ADMIN,
                json={"username": "op", "display_name": "Op", "role": "OPERATOR"})
    r = client.post("/api/v1/users",
                    headers={"X-Tenant-Id": "tenant-a", "X-Actor": "op"},
                    json={"username": "third", "display_name": "Third"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ROLE_FORBIDDEN"


def test_duplicate_username_same_tenant_conflict_cross_tenant_ok(client):
    register_tenant(client, "tenant-a")
    register_tenant(client, "tenant-b")
    bootstrap_admin(client, "tenant-a", "sam")
    r = client.post("/api/v1/users", headers={"X-Tenant-Id": "tenant-a", "X-Actor": "sam"},
                    json={"username": "sam", "display_name": "Duplicate"})
    assert r.status_code == 409
    r = client.post("/api/v1/users", headers={"X-Tenant-Id": "tenant-b"},
                    json={"username": "sam", "display_name": "Sam of B"})
    assert r.status_code == 201  # bootstrap of tenant-b, same username is fine


def test_users_list_is_tenant_scoped(client):
    register_tenant(client, "tenant-a")
    register_tenant(client, "tenant-b")
    bootstrap_admin(client, "tenant-a", "anna")
    bootstrap_admin(client, "tenant-b", "bob")
    r = client.get("/api/v1/users", headers=A)
    names = [u["username"] for u in r.json()["items"]]
    assert names == ["anna"]


def test_viewer_cannot_create_workspace(client):
    register_tenant(client, "tenant-a")
    bootstrap_admin(client, "tenant-a")
    client.post("/api/v1/users", headers=A_ADMIN,
                json={"username": "vic", "display_name": "Viewer", "role": "VIEWER"})
    r = client.post("/api/v1/workspaces",
                    headers={"X-Tenant-Id": "tenant-a", "X-Actor": "vic"},
                    json={"name": "nope"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ROLE_FORBIDDEN"


# ---- audit ---------------------------------------------------------------

def test_audit_records_platform_and_tenant_events(client):
    register_tenant(client, "tenant-a")
    bootstrap_admin(client, "tenant-a")
    client.post("/api/v1/workspaces", headers=A_ADMIN, json={"name": "yard"})
    r = client.get("/api/v1/platform/audit", headers=PK)
    actions = [(e["action"], e["tenant_id"]) for e in r.json()["items"]]
    assert ("TENANT_CREATE", "tenant-a") in actions
    assert ("USER_BOOTSTRAP", "tenant-a") in actions
    assert ("WORKSPACE_CREATE", "tenant-a") in actions
    seqs = [e["seq"] for e in r.json()["items"]]
    assert seqs == sorted(seqs)  # append-only order


def test_tenant_audit_does_not_leak_other_tenants(client):
    register_tenant(client, "tenant-a")
    register_tenant(client, "tenant-b")
    bootstrap_admin(client, "tenant-a", "anna")
    bootstrap_admin(client, "tenant-b", "bob")
    r = client.get("/api/v1/audit", headers=A)
    items = r.json()["items"]
    assert items and all(e["tenant_id"] == "tenant-a" for e in items)
    assert not any(e["actor"] == "bob" for e in items)
