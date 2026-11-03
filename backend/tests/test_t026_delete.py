"""Delete endpoints for master data (T-026, Owner UX pack).

TENANT_ADMIN only; a record still referenced by others is refused with
409 RECORD_IN_USE; evidence-like kinds have no DELETE route at all.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "Zone 1"})
    assert r.status_code == 201, r.text


def test_delete_unreferenced_zone(client):
    _setup(client)
    r = client.delete("/api/v1/zones/Z-01", headers=A)
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] is True
    assert client.get("/api/v1/zones/Z-01", headers=A).status_code == 404
    audit = client.get("/api/v1/audit", headers=A).json()["items"]
    assert any(row["action"] == "ZON_DELETE" for row in audit)


def test_delete_referenced_zone_refused(client):
    _setup(client)
    r = client.post("/api/v1/mother-plants", headers=A,
                    json={"code": "MP-1", "species": "Sau rieng",
                          "zone_code": "Z-01"})
    assert r.status_code == 201, r.text
    r = client.delete("/api/v1/zones/Z-01", headers=A)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "RECORD_IN_USE"
    # delete the child first, then the parent goes through
    assert client.delete("/api/v1/mother-plants/MP-1", headers=A).status_code == 200
    assert client.delete("/api/v1/zones/Z-01", headers=A).status_code == 200


def test_delete_guards(client):
    _setup(client)
    assert client.delete("/api/v1/zones/NOPE", headers=A).status_code == 404
    # harvest lots are evidence: no DELETE route
    assert client.delete("/api/v1/lots/L-01", headers=A).status_code == 405
    # OPERATOR may create/edit but not delete
    r = client.post("/api/v1/users", headers=A,
                    json={"username": "op1", "display_name": "Op",
                          "role": "OPERATOR"})
    assert r.status_code == 201, r.text
    r = client.delete("/api/v1/zones/Z-01",
                      headers={"X-Tenant-Id": "farm-a", "X-Actor": "op1"})
    assert r.status_code == 403
