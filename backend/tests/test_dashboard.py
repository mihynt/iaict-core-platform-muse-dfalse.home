"""Dashboard summary endpoint (audit T-021, performance pack P1).

One call returns the counts the UI home screen used to assemble from a
health call + one full list per stat card, plus the latest audit rows.
Counts must be tenant-scoped and must track creates.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}
B = {"X-Tenant-Id": "farm-b", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    register_tenant(client, "farm-b")
    bootstrap_admin(client, "farm-a")
    bootstrap_admin(client, "farm-b")


def test_dashboard_counts_and_isolation(client):
    _setup(client)
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "Zone 1", "area_ha": 3})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-02", "name": "Zone 2"})
    assert r.status_code == 201, r.text

    d = client.get("/api/v1/dashboard", headers=A)
    assert d.status_code == 200, d.text
    body = d.json()
    assert body["tenant"] == "farm-a"
    assert body["counts"]["zones"] == 2
    assert body["counts"]["lots"] == 0
    assert body["counts"]["users"] == 1
    assert body["storage"]
    assert body["version"]
    actions = [row["action"] for row in body["recent_audit"]]
    assert "ZON_CREATE" in actions

    d_b = client.get("/api/v1/dashboard", headers=B).json()
    assert d_b["counts"]["zones"] == 0
    assert d_b["counts"]["users"] == 1


def test_dashboard_requires_tenant(client):
    r = client.get("/api/v1/dashboard")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TENANT_REQUIRED"
