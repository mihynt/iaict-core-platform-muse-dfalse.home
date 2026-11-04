"""GD3 logistics: transport trips (Bang 28), recall cases (Bang 31),
dossier views as reports, and the FLD-17 per-parcel PHI completion."""
from tests.conftest import bootstrap_admin, register_tenant


def _setup(client):
    register_tenant(client, "t-log")
    bootstrap_admin(client, "t-log")
    h = {"X-Tenant-Id": "t-log", "X-Actor": "admin"}
    client.post("/api/v1/zones", headers=h, json={"code": "Z-01"})
    client.post("/api/v1/actors", headers=h, json={"code": "A-01", "name": "Co so 1"})
    client.post("/api/v1/ref-transport-modes", headers=h,
                json={"code": "ROAD_TRUCK", "mode_name": "Xe tai"})
    return h


def test_transport_trip_lifecycle(client):
    h = _setup(client)
    r = client.post("/api/v1/transport-trips", headers=h,
                    json={"carrier_actor_code": "A-01", "transport_mode_code": "ROAD_TRUCK",
                          "vehicle_vessel_identifier": "51C-12345",
                          "origin_actor_code": "A-01", "destination_actor_code": "A-01",
                          "departure_timestamp": "2026-10-02T06:00:00"})
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    r = client.patch(f"/api/v1/transport-trips/{rec_id}", headers=h,
                     json={"arrival_timestamp": "2026-10-02T18:30:00",
                           "storage_temp_celsius": 4.5})
    assert r.status_code == 200
    assert r.json()["storage_temp_celsius"] == 4.5


def test_recall_generated_unrecovered_and_trace_validation(client):
    h = _setup(client)
    # unknown traceability code is rejected
    r = client.post("/api/v1/recall-cases", headers=h,
                    json={"traceability_code": "NOPE|CODE", "recall_reason": "test"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"
    # unrecovered quantity is generated: consumed - recovered
    r = client.post("/api/v1/recall-cases", headers=h,
                    json={"recall_initiation_type": "VOLUNTARY_RECALL",
                          "risk_classification": "HIGH_RISK",
                          "qty_consumed_sold": 100, "qty_recovered": 30,
                          "qty_unrecovered": 999})
    assert r.status_code == 201, r.text
    assert r.json()["qty_unrecovered"] == 70


def test_reports_compute_balances(client):
    h = _setup(client)
    client.post("/api/v1/crop-plans", headers=h,
                json={"code": "P-01", "zone_code": "Z-01", "target_yield_kg": 1000})
    client.post("/api/v1/lots", headers=h,
                json={"code": "L-01", "plan_code": "P-01", "zone_code": "Z-01",
                      "harvest_date": "2026-10-01", "quantity": 250})
    items = client.get("/api/v1/reports/cycle-mass-balance", headers=h).json()["items"]
    row = next(i for i in items if i["plan_code"] == "P-01")
    assert row["harvested_kg"] == 250 and row["remaining_kg"] == 750
    assert row["harvested_pct"] == 25.0 and row["over_ceiling"] is False
    items = client.get("/api/v1/reports/zone-metrics", headers=h).json()["items"]
    row = next(i for i in items if i["zone_code"] == "Z-01")
    assert row["plans"] == 1 and row["lots"] == 1 and row["harvested_kg"] == 250


def test_fld17_phi_scoped_per_parcel(client):
    h = _setup(client)
    # two plans on two different parcels of the same zone
    client.post("/api/v1/spatial-units", headers=h, json={"code": "TH-01"})
    client.post("/api/v1/spatial-units", headers=h, json={"code": "TH-02"})
    client.post("/api/v1/crop-plans", headers=h,
                json={"code": "P-A", "zone_code": "Z-01", "parcel_code": "TH-01"})
    client.post("/api/v1/crop-plans", headers=h,
                json={"code": "P-B", "zone_code": "Z-01", "parcel_code": "TH-02"})
    client.post("/api/v1/input-lots", headers=h,
                json={"code": "VT-01", "name": "Thuoc", "phi_days": 14})
    # treatment on parcel TH-02 only: applied 2026-10-01, safe from 2026-10-15
    r = client.post("/api/v1/field-events", headers=h,
                    json={"plan_code": "P-B", "zone_code": "Z-01",
                          "input_lot_code": "VT-01", "occurred_at": "2026-10-01"})
    assert r.status_code == 201, r.text
    # a lot on parcel TH-01 (plan P-A) is NOT blocked by TH-02's treatment
    r = client.post("/api/v1/lots", headers=h,
                    json={"code": "L-A", "plan_code": "P-A", "zone_code": "Z-01",
                          "parcel_code": "TH-01", "harvest_date": "2026-10-05",
                          "quantity": 10})
    assert r.status_code == 201, r.text
    # a lot on parcel TH-02 before the safe date IS blocked
    r = client.post("/api/v1/lots", headers=h,
                    json={"code": "L-B", "plan_code": "P-B", "zone_code": "Z-01",
                          "parcel_code": "TH-02", "harvest_date": "2026-10-05",
                          "quantity": 10})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PHI_VIOLATION"
    # after the safe date it passes
    r = client.post("/api/v1/lots", headers=h,
                    json={"code": "L-B", "plan_code": "P-B", "zone_code": "Z-01",
                          "parcel_code": "TH-02", "harvest_date": "2026-10-20",
                          "quantity": 10})
    assert r.status_code == 201, r.text


def test_fld17_missing_phi_is_not_zero(client):
    h = _setup(client)
    client.post("/api/v1/spatial-units", headers=h, json={"code": "TH-01"})
    client.post("/api/v1/crop-plans", headers=h,
                json={"code": "P-A", "zone_code": "Z-01", "parcel_code": "TH-01"})
    # input lot WITHOUT any PHI declaration
    client.post("/api/v1/input-lots", headers=h,
                json={"code": "VT-X", "name": "Phan bon"})
    r = client.post("/api/v1/field-events", headers=h,
                    json={"plan_code": "P-A", "zone_code": "Z-01",
                          "input_lot_code": "VT-X", "occurred_at": "2026-10-01"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/lots", headers=h,
                    json={"code": "L-X", "plan_code": "P-A", "zone_code": "Z-01",
                          "parcel_code": "TH-01", "harvest_date": "2026-12-01",
                          "quantity": 5})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PHI_DATA_MISSING"
    phis = client.get("/api/v1/phi-validations", headers=h).json()["items"]
    assert phis[-1]["validation_outcome"] == "CONDITIONAL_LAB_TEST_REQUIRED"
