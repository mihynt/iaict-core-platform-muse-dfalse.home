"""Phase-review supplements (T-024).

Closes the residual gaps found when re-auditing phases 1-2 after
T-022/T-023: cross-store duplicate-link parity, audit entries for
auto-emitted CTE stages, GTIN format discipline, and the principal
fields the T-021 audit listed for zones / input lots / field events /
crop plans.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "Zone 1"})
    assert r.status_code == 201, r.text


def _chain(client):
    _setup(client)
    client.post("/api/v1/actors", headers=A,
                json={"code": "CS-01", "name": "Co so dong goi"})
    r = client.post("/api/v1/crop-plans", headers=A,
                    json={"code": "PLAN-1", "zone_code": "Z-01",
                          "target_yield_kg": 1000})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/lots", headers=A,
                    json={"code": "LOT-1", "plan_code": "PLAN-1",
                          "zone_code": "Z-01", "harvest_date": "2026-02-01",
                          "quantity": 500})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/packing-lots", headers=A,
                    json={"code": "PK-1", "facility_code": "CS-01",
                          "phc_code": "PHC-1", "product_name": "Buoi",
                          "output_weight_kg": 400, "yield_norm_ratio": 0.8,
                          "storage_type": "FRESH_AMBIENT",
                          "packed_at": "2026-02-03T08:00:00"})
    assert r.status_code == 201, r.text


def test_duplicate_links_rejected_on_every_store(client):
    _setup(client)
    r = client.post("/api/v1/spatial-units", headers=A,
                    json={"code": "TH-01", "name": "Thua 1"})
    assert r.status_code == 201, r.text
    body = {"zone_code": "Z-01", "parcel_code": "TH-01"}
    r = client.post("/api/v1/zone-parcel-links", headers=A, json=body)
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/zone-parcel-links", headers=A, json=body)
    assert r.status_code == 409, r.text


def test_duplicate_packing_input_rejected(client):
    _chain(client)
    body = {"packing_lot_code": "PK-1", "harvest_lot_code": "LOT-1",
            "allocated_weight_kg": 100}
    r = client.post("/api/v1/packing-inputs", headers=A, json=body)
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/packing-inputs", headers=A, json=body)
    assert r.status_code == 409, r.text


def test_cte_stages_are_audited(client):
    _chain(client)
    client.post("/api/v1/packing-inputs", headers=A,
                json={"packing_lot_code": "PK-1", "harvest_lot_code": "LOT-1",
                      "allocated_weight_kg": 500})
    r = client.post("/api/v1/packaging-units", headers=A,
                    json={"code": "SKU-1", "packing_lot_code": "PK-1",
                          "gtin_code": "08935049501237", "units_count": 10})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/traceability-records", headers=A,
                    json={"packaging_unit_code": "SKU-1"})
    assert r.status_code == 201, r.text
    audit = client.get("/api/v1/audit", headers=A).json()["items"]
    cte_rows = [row for row in audit if row["action"] == "CTE_CREATE"]
    assert len(cte_rows) >= 2  # harvest stage + packing stage


def test_gtin_format_validation(client):
    _chain(client)
    r = client.post("/api/v1/packaging-units", headers=A,
                    json={"code": "SKU-BAD", "packing_lot_code": "PK-1",
                          "gtin_code": "ABC-123"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "GTIN_INVALID"
    r = client.post("/api/v1/packaging-units", headers=A,
                    json={"code": "SKU-OK", "packing_lot_code": "PK-1",
                          "gtin_code": "08935049501237"})
    assert r.status_code == 201, r.text


def test_new_principal_fields_round_trip(client):
    _setup(client)
    r = client.patch("/api/v1/zones/Z-01", headers=A,
                     json={"vsic_code": "0141", "dist_to_residential_m": 120,
                           "bee_site_min_dist_km": 3})
    assert r.status_code == 200, r.text
    assert r.json()["vsic_code"] == "0141"
    assert r.json()["dist_to_residential_m"] == 120

    r = client.post("/api/v1/input-lots", headers=A,
                    json={"code": "VT-01", "name": "Thuoc A", "phi_days": 7,
                          "purchase_invoice_no": "HD-2026-001",
                          "qcvn_scheme_id": "QCVN-01"})
    assert r.status_code == 201, r.text
    assert r.json()["purchase_invoice_no"] == "HD-2026-001"

    r = client.post("/api/v1/crop-plans", headers=A,
                    json={"code": "PLAN-9", "zone_code": "Z-01",
                          "planting_density": 450,
                          "seed_origin_doc": "GCN-GIONG-88"})
    assert r.status_code == 201, r.text
    assert r.json()["planting_density"] == 450

    r = client.post("/api/v1/field-events", headers=A,
                    json={"plan_code": "PLAN-9", "zone_code": "Z-01",
                          "event_type": "PEST", "occurred_at": "2026-01-05",
                          "application_method": "Phun ap luc",
                          "fruit_bagging_count": 1200})
    assert r.status_code == 201, r.text
    assert r.json()["application_method"] == "Phun ap luc"
    assert r.json()["fruit_bagging_count"] == 1200
