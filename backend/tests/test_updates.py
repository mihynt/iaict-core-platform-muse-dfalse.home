"""Master-data updates + T-023 field additions (audit T-021 follow-up).

PATCH exists for non-gated master kinds only; evidence-like kinds stay
append-only. PHI validations must reference the treatment whose PHI ends
last (Bang 24 LOG_PHI_VALIDATION.last_treatment_log_id).
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "Zone 1", "area_ha": 3})
    assert r.status_code == 201, r.text


def test_patch_zone_and_audit(client):
    _setup(client)
    r = client.patch("/api/v1/zones/Z-01", headers=A,
                     json={"name": "Zone One", "area_ha": 4.5,
                           "puc_code": "VN-66-650-24370-94-21"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Zone One"
    assert body["area_ha"] == 4.5
    assert body["code"] == "Z-01"
    got = client.get("/api/v1/zones/Z-01", headers=A).json()
    assert got["puc_code"] == "VN-66-650-24370-94-21"
    audit = client.get("/api/v1/audit", headers=A).json()["items"]
    assert any(row["action"] == "ZON_UPDATE" and row["target"] == "Z-01"
               for row in audit)


def test_patch_guards(client):
    _setup(client)
    r = client.patch("/api/v1/zones/NOPE", headers=A, json={"name": "x"})
    assert r.status_code == 404
    r = client.patch("/api/v1/zones/Z-01", headers=A, json={"code": "Z-99"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "CODE_IMMUTABLE"
    # harvest lots are evidence: no PATCH route
    r = client.patch("/api/v1/lots/L-01", headers=A, json={"quantity": 5})
    assert r.status_code == 405


def test_patch_unknown_ref_rejected(client):
    _setup(client)
    r = client.post("/api/v1/mother-plants", headers=A,
                    json={"code": "MP-1", "species": "Sau rieng",
                          "zone_code": "Z-01"})
    assert r.status_code == 201, r.text
    r = client.patch("/api/v1/mother-plants/MP-1", headers=A,
                     json={"zone_code": "GHOST"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"


def test_patch_requires_operator(client):
    _setup(client)
    r = client.post("/api/v1/users", headers=A,
                    json={"username": "viewer1", "display_name": "Viewer",
                          "role": "VIEWER"})
    assert r.status_code == 201, r.text
    r = client.patch("/api/v1/zones/Z-01",
                     headers={"X-Tenant-Id": "farm-a", "X-Actor": "viewer1"},
                     json={"name": "Nope"})
    assert r.status_code == 403


def test_phi_validation_records_last_treatment(client):
    _setup(client)
    r = client.post("/api/v1/input-lots", headers=A,
                    json={"code": "VT-01", "name": "Thuoc A", "phi_days": 10})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/crop-plans", headers=A,
                    json={"code": "PLAN-1", "name": "Vu 1",
                          "zone_code": "Z-01", "target_yield_kg": 1000})
    assert r.status_code == 201, r.text
    ev = client.post("/api/v1/field-events", headers=A,
                     json={"plan_code": "PLAN-1", "zone_code": "Z-01",
                           "event_type": "SPRAY", "occurred_at": "2026-01-01",
                           "input_lot_code": "VT-01"})
    assert ev.status_code == 201, ev.text
    event_id = str(ev.json()["id"])
    r = client.post("/api/v1/lots", headers=A,
                    json={"code": "LOT-1", "plan_code": "PLAN-1",
                          "zone_code": "Z-01", "harvest_date": "2026-01-20",
                          "quantity": 100})
    assert r.status_code == 201, r.text
    vals = client.get("/api/v1/phi-validations", headers=A).json()["items"]
    assert len(vals) == 1
    assert vals[0]["outcome"] == "PASSED_SAFE"
    assert vals[0]["last_treatment_ref"] == event_id
