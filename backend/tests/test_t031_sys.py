"""SYS pack (T-031): Bang 32 user link/status, Bang 33 audit snapshots."""
import json

from tests.conftest import PK, bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")


def test_user_linked_actor_and_status(client):
    _setup(client)
    client.post("/api/v1/actors", headers=A,
                json={"code": "DN-01", "name": "Cong ty A"})
    r = client.post("/api/v1/users", headers=A, json={
        "username": "ops1", "display_name": "Van hanh 1", "role": "OPERATOR",
        "linked_actor_code": "DN-01", "jurisdiction_admin_code": "66"})
    assert r.status_code == 201, r.text
    assert r.json()["linked_actor_code"] == "DN-01"
    assert r.json()["account_status"] == "ACTIVE"
    # unknown linked actor rejected
    r = client.post("/api/v1/users", headers=A, json={
        "username": "ops2", "display_name": "X", "linked_actor_code": "GHOST"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"
    # lock the account: it can no longer act
    r = client.patch("/api/v1/users/ops1", headers=A,
                     json={"account_status": "LOCKED"})
    assert r.status_code == 200, r.text
    r = client.get("/api/v1/zones", headers={"X-Tenant-Id": "farm-a",
                                             "X-Actor": "ops1"})
    assert r.status_code == 200  # reads do not require an actor
    r = client.post("/api/v1/zones", headers={"X-Tenant-Id": "farm-a",
                                              "X-Actor": "ops1"},
                    json={"code": "Z-9", "name": "Nope"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "ACCOUNT_INACTIVE"
    # the last active TENANT_ADMIN cannot be locked
    r = client.patch("/api/v1/users/admin", headers=A,
                     json={"account_status": "LOCKED"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "LAST_ADMIN"


def test_audit_snapshots_and_client_info(client):
    _setup(client)
    client.post("/api/v1/zones", headers=A,
                json={"code": "Z-01", "name": "Zone 1", "season": "2025"})
    client.patch("/api/v1/zones/Z-01", headers=A, json={"season": "2026"})
    audit = client.get("/api/v1/audit", headers=A).json()["items"]
    upd = next(a for a in audit if a["action"] == "ZON_UPDATE")
    old = json.loads(upd["old_value"])
    new = json.loads(upd["new_value"])
    assert old["season"] == "2025" and new["season"] == "2026"
    cre = next(a for a in audit if a["action"] == "ZON_CREATE")
    assert json.loads(cre["new_value"])["code"] == "Z-01"
    assert "user_agent" in cre  # Bang 33 columns are carried on every row
