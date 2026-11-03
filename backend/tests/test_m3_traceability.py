"""Traceability data standard, phase 1 (D-STD-01 / T-015).

Actors, spatial units, zone-parcel links, input lots, the field-event PHI
bookkeeping, the harvest-lot PHI gate + mass-balance ceiling, and the
generated traceability code / retention date. Backend-agnostic like the
M2 suite: must pass identically on every store backend.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}
B = {"X-Tenant-Id": "farm-b", "X-Actor": "admin"}


def _farm(client, slug="farm-a"):
    register_tenant(client, slug)
    bootstrap_admin(client, slug)


def _base(client):
    """Zone with a PUC code, a farmer, a parcel, linked membership."""
    _farm(client)
    r = client.post("/api/v1/zones", headers=A, json={
        "code": "Z-01", "name": "Ea Tan block",
        "puc_code": "VN-66-650-24370-94-21", "puc_status": "ACTIVE_COMPLIANT",
        "sector_category": "CROP_FARMING", "market_scope": "BOTH_MARKETS",
        "primary_species": "Pomelo", "issue_date": "2021-05-01",
        "issuing_authority": "UBND xa Ea Tan"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/actors", headers=A, json={
        "code": "H05", "name": "Nguyen Van B",
        "actor_type": "MEMBER_FARMER_HOUSEHOLD", "commune_code": "24370"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/spatial-units", headers=A, json={
        "code": "T42", "name": "Thua 42", "unit_type": "AGRICULTURAL_LAND_PARCEL",
        "operator_code": "H05", "national_land_parcel_id": "6665024370-18-42",
        "map_sheet_number": "18", "parcel_number": "42", "area_m2": 15000})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/zone-parcel-links", headers=A, json={
        "zone_code": "Z-01", "parcel_code": "T42",
        "registered_area_m2": 15000, "membership_status": "ACTIVE_MEMBER",
        "joined_date": "2021-05-01"})
    assert r.status_code == 201, r.text


def test_zone_puc_block_roundtrip(client):
    _base(client)
    zone = client.get("/api/v1/zones/Z-01", headers=A).json()
    assert zone["puc_code"] == "VN-66-650-24370-94-21"
    assert zone["puc_status"] == "ACTIVE_COMPLIANT"
    assert zone["sector_category"] == "CROP_FARMING"
    assert zone["issue_date"] == "2021-05-01"


def test_actor_parcel_link_listing(client):
    _base(client)
    links = client.get("/api/v1/zone-parcel-links", headers=A).json()["items"]
    assert len(links) == 1
    assert links[0]["zone_code"] == "Z-01" and links[0]["parcel_code"] == "T42"
    assert links[0]["registered_area_m2"] == 15000
    parcel = client.get("/api/v1/spatial-units/T42", headers=A).json()
    assert parcel["operator_code"] == "H05"
    assert parcel["national_land_parcel_id"] == "6665024370-18-42"
    bad = client.post("/api/v1/zone-parcel-links", headers=A,
                      json={"zone_code": "Z-01", "parcel_code": "NOPE"})
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "REF_UNKNOWN"


def test_actor_parent_and_cross_tenant_refs(client):
    _farm(client, "farm-a")
    _farm(client, "farm-b")
    client.post("/api/v1/actors", headers=B,
                json={"code": "COOP-B", "name": "B coop",
                      "actor_type": "PUC_REPRESENTATIVE_ORG"})
    ok = client.post("/api/v1/actors", headers=A,
                     json={"code": "COOP-A", "name": "A coop",
                           "actor_type": "PUC_REPRESENTATIVE_ORG"})
    assert ok.status_code == 201
    child = client.post("/api/v1/actors", headers=A,
                        json={"code": "H01", "name": "Farmer One",
                              "parent_code": "COOP-A"})
    assert child.status_code == 201 and child.json()["parent_code"] == "COOP-A"
    cross = client.post("/api/v1/actors", headers=A,
                        json={"code": "H02", "name": "Farmer Two",
                              "parent_code": "COOP-B"})
    assert cross.status_code == 400
    assert cross.json()["detail"]["code"] == "REF_UNKNOWN"


def test_input_lot_and_event_safe_harvest_date(client):
    _base(client)
    r = client.post("/api/v1/input-lots", headers=A, json={
        "code": "INP-1", "name": "Abamectin 3.6EC", "category": "PESTICIDE_PLANT_PROTECTION",
        "substance_code": "ABAMECTIN", "supplier_code": "H05",
        "vn_registration_number": "1234-56", "batch_no": "B-2026-01",
        "phi_days": 14, "expiry_date": "2027-01-01"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/crop-plans", headers=A, json={
        "code": "PLAN-1", "name": "Vu Thu Dong", "zone_code": "Z-01",
        "parcel_code": "T42", "crop_name": "Pomelo", "variety_name": "Da Xanh"})
    assert r.status_code == 201, r.text
    assert r.json()["parcel_code"] == "T42"
    r = client.post("/api/v1/field-events", headers=A, json={
        "plan_code": "PLAN-1", "event_type": "PEST",
        "occurred_at": "2026-09-10T07:00:00", "input_lot_code": "INP-1",
        "target_pest": "Sau ve bua", "dosage": "0.5 ml/l"})
    assert r.status_code == 201, r.text
    event = r.json()
    assert event["phi_days"] == 14
    assert event["safe_harvest_date"] == "2026-09-24"


def _plan_with_spray(client):
    _base(client)
    client.post("/api/v1/input-lots", headers=A, json={
        "code": "INP-1", "name": "Abamectin", "phi_days": 14})
    client.post("/api/v1/crop-plans", headers=A, json={
        "code": "PLAN-1", "name": "Vu Thu Dong", "zone_code": "Z-01"})
    client.post("/api/v1/field-events", headers=A, json={
        "plan_code": "PLAN-1", "event_type": "PEST",
        "occurred_at": "2026-09-10T07:00:00", "input_lot_code": "INP-1"})


def test_lot_blocked_by_phi_and_logged(client):
    _plan_with_spray(client)
    r = client.post("/api/v1/lots", headers=A, json={
        "code": "LOT-EARLY", "zone_code": "Z-01", "plan_code": "PLAN-1",
        "farmer_code": "H05", "parcel_code": "T42",
        "harvest_date": "2026-09-20", "quantity": 100,
        "weigh_slip_number": "WS-2026-0001"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "PHI_VIOLATION"
    assert client.get("/api/v1/lots", headers=A).json()["items"] == []
    vals = client.get("/api/v1/phi-validations", headers=A).json()["items"]
    assert len(vals) == 1
    assert vals[0]["outcome"] == "BLOCKED_VIOLATION_PHI"
    assert vals[0]["max_safe_harvest_date"] == "2026-09-24"
    assert vals[0]["lot_code"] == "LOT-EARLY"


def test_lot_passes_phi_traceability_and_retention(client):
    _plan_with_spray(client)
    r = client.post("/api/v1/lots", headers=A, json={
        "code": "HARV-20261014-H05-T42", "zone_code": "Z-01", "plan_code": "PLAN-1",
        "farmer_code": "H05", "parcel_code": "T42",
        "harvest_date": "2026-10-14", "quantity": 5000,
        "weigh_slip_number": "WS-2026-0051"})
    assert r.status_code == 201, r.text
    lot = r.json()
    assert lot["farmer_code"] == "H05" and lot["parcel_code"] == "T42"
    assert lot["traceability_code"] == \
        "PLAN-1|VN-66-650-24370-94-21|HARV-20261014-H05-T42|2026-10-14"
    assert lot["data_retention_until"] == "2027-10-14"
    vals = client.get("/api/v1/phi-validations", headers=A).json()["items"]
    assert [v["outcome"] for v in vals] == ["PASSED_SAFE"]


def test_mass_balance_ceiling(client):
    _base(client)
    client.post("/api/v1/crop-plans", headers=A, json={
        "code": "PLAN-MB", "name": "Ceiling plan", "zone_code": "Z-01",
        "target_yield_kg": 1000})
    ok = client.post("/api/v1/lots", headers=A, json={
        "code": "LOT-1", "zone_code": "Z-01", "plan_code": "PLAN-MB",
        "harvest_date": "2026-10-01", "quantity": 600})
    assert ok.status_code == 201, ok.text
    over = client.post("/api/v1/lots", headers=A, json={
        "code": "LOT-2", "zone_code": "Z-01", "plan_code": "PLAN-MB",
        "harvest_date": "2026-10-02", "quantity": 500})
    assert over.status_code == 400
    assert over.json()["detail"]["code"] == "MASS_BALANCE_EXCEEDED"
