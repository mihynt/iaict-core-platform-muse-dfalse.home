"""Bang 13 status history + Bang 12 withdraw lifecycle (T-031)."""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")


def test_zone_status_history_logged(client):
    _setup(client)
    r = client.post("/api/v1/zones", headers=A, json={
        "code": "Z-01", "name": "Zone 1", "puc_status": "PENDING_POST_INSPECTION"})
    assert r.status_code == 201, r.text
    hist = client.get("/api/v1/zone-status-history", headers=A).json()["items"]
    assert len(hist) == 1
    assert hist[0]["previous_status"] is None
    assert hist[0]["new_status"] == "PENDING_POST_INSPECTION"
    # a non-status edit logs nothing
    r = client.patch("/api/v1/zones/Z-01", headers=A, json={"season": "2026"})
    assert r.status_code == 200
    assert len(client.get("/api/v1/zone-status-history", headers=A).json()["items"]) == 1
    # a status change with metadata logs the full Bang-13 row
    r = client.patch("/api/v1/zones/Z-01", headers=A, json={
        "puc_status": "ACTIVE_COMPLIANT",
        "status_change_reason": "POST_INSPECTION_PASSED",
        "status_decision_doc": "QD-123/UBND"})
    assert r.status_code == 200, r.text
    hist = client.get("/api/v1/zone-status-history", headers=A).json()["items"]
    assert len(hist) == 2
    last = hist[-1]
    assert last["previous_status"] == "PENDING_POST_INSPECTION"
    assert last["new_status"] == "ACTIVE_COMPLIANT"
    assert last["trigger_reason_code"] == "POST_INSPECTION_PASSED"
    assert last["decision_doc_number"] == "QD-123/UBND"
    assert last["changed_by"] == "admin"
    # the metadata must not pollute the zone record itself
    zone = client.get("/api/v1/zones/Z-01", headers=A).json()
    assert "status_change_reason" not in zone


def test_withdraw_link_sets_left_date(client):
    _setup(client)
    client.post("/api/v1/zones", headers=A, json={"code": "Z-01", "name": "Z"})
    client.post("/api/v1/spatial-units", headers=A,
                json={"code": "TH-01", "name": "Thua 1"})
    r = client.post("/api/v1/zone-parcel-links", headers=A,
                    json={"zone_code": "Z-01", "parcel_code": "TH-01"})
    assert r.status_code == 201, r.text
    link_id = r.json()["id"]
    r = client.post(f"/api/v1/zone-parcel-links/{link_id}/withdraw", headers=A)
    assert r.status_code == 200, r.text
    assert r.json()["membership_status"] == "WITHDRAWN_FROM_ZONE"
    assert r.json()["left_date"]
    r = client.post(f"/api/v1/zone-parcel-links/{link_id}/withdraw", headers=A)
    assert r.status_code == 409
