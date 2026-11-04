"""Traceability data standard, phase 2 (D-STD-01 / T-016): packing chain.

Packing lots at a PHC, N-N harvest-input links with the over-allocation
guard, packaging units (SKU), national traceability records with the
packing mass-balance gate, and the auto-built CTE stage chain.
Backend-agnostic: must pass identically on every store backend.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}
B = {"X-Tenant-Id": "farm-b", "X-Actor": "admin"}


def _farm(client, slug="farm-a"):
    register_tenant(client, slug)
    bootstrap_admin(client, slug)


def _chain(client):
    """Zone + packing facility + two harvest lots of 5000 kg each."""
    _farm(client)
    client.post("/api/v1/zones", headers=A, json={
        "code": "Z-01", "name": "Ea Tan block", "puc_code": "VN-66-650-24370-94-21"})
    client.post("/api/v1/actors", headers=A, json={
        "code": "PHC-01", "name": "Co so dong goi Kim Thanh",
        "actor_type": "PACKING_HOUSE_OPERATOR",
        "address": "Xa Ea Tan, Huyen Krong Nang, Tinh Dak Lak"})
    for code in ("LOT-H1", "LOT-H2"):
        r = client.post("/api/v1/lots", headers=A, json={
            "code": code, "zone_code": "Z-01", "harvest_date": "2026-10-14",
            "quantity": 5000})
        assert r.status_code == 201, r.text
    r = client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-1", "facility_code": "PHC-01", "phc_code": "VN-PHC-66-019",
        "product_name": "Buoi da xanh loai 1", "output_weight_kg": 8200,
        "yield_norm_ratio": 0.85, "storage_type": "FRESH_AMBIENT",
        "packed_at": "2026-10-15T08:30:00", "expiry_date": "2026-12-15"})
    assert r.status_code == 201, r.text


def _link(client, harvest, kg, packing="PK-1"):
    return client.post("/api/v1/packing-inputs", headers=A, json={
        "packing_lot_code": packing, "harvest_lot_code": harvest,
        "allocated_weight_kg": kg})


def test_packing_lot_and_links(client):
    _chain(client)
    assert _link(client, "LOT-H1", 5000).status_code == 201
    assert _link(client, "LOT-H2", 5000).status_code == 201
    links = client.get("/api/v1/packing-inputs", headers=A).json()["items"]
    assert len(links) == 2
    plot = client.get("/api/v1/packing-lots/PK-1", headers=A).json()
    assert plot["facility_code"] == "PHC-01" and plot["phc_code"] == "VN-PHC-66-019"
    assert plot["status"] == "PACKED"


def test_over_allocation_blocked(client):
    _chain(client)
    assert _link(client, "LOT-H1", 5000).status_code == 201
    client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-2", "facility_code": "PHC-01", "output_weight_kg": 10})
    over = _link(client, "LOT-H1", 1, packing="PK-2")
    assert over.status_code == 400
    assert over.json()["detail"]["code"] == "HARVEST_LOT_OVER_ALLOCATED"


def test_traceability_record_and_cte_chain(client):
    _chain(client)
    _link(client, "LOT-H1", 5000)
    _link(client, "LOT-H2", 5000)
    r = client.post("/api/v1/packaging-units", headers=A, json={
        "code": "SKU-1", "packing_lot_code": "PK-1",
        "level": "SHIPPING_CASE_CARTON", "gtin_code": "08935049501237",
        "package_spec": "Thung carton 10 kg", "units_count": 820})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/traceability-records", headers=A,
                    json={"packaging_unit_code": "SKU-1"})
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["traceability_code"].startswith(
        "08935049501237|VN-PHC-66-019|PK-1|2026-10-15")
    assert rec["product_name"] == "Buoi da xanh loai 1"
    assert rec["business_unit_name"] == "Co so dong goi Kim Thanh"
    assert rec["data_retention_until"] == "2027-12-15"
    assert rec["sync_status"] == "PENDING_SYNC"
    stages = client.get("/api/v1/cte-stages", headers=A).json()["items"]
    harvest_stages = [s for s in stages if s["stage_no"] == 1]
    packing_stages = [s for s in stages if s["stage_no"] == 2]
    assert {s["product_trace_code"] for s in harvest_stages} == {"LOT-H1", "LOT-H2"}
    assert all(s["location_trace_code"] == "VN-66-650-24370-94-21"
               for s in harvest_stages)
    assert len(packing_stages) == 1
    assert packing_stages[0]["batch_lot_number"] == "PK-1"
    assert all(s["traceability_code"] == rec["traceability_code"] for s in stages)


def test_packing_mass_balance_gate(client):
    _chain(client)
    client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-BAD", "facility_code": "PHC-01", "phc_code": "VN-PHC-66-019",
        "product_name": "Buoi da xanh loai 1", "output_weight_kg": 9000,
        "yield_norm_ratio": 0.85, "packed_at": "2026-10-15T08:30:00"})
    _link(client, "LOT-H1", 5000, packing="PK-BAD")
    _link(client, "LOT-H2", 5000, packing="PK-BAD")
    client.post("/api/v1/packaging-units", headers=A, json={
        "code": "SKU-BAD", "packing_lot_code": "PK-BAD",
        "gtin_code": "08935049509998", "units_count": 900})
    r = client.post("/api/v1/traceability-records", headers=A,
                    json={"packaging_unit_code": "SKU-BAD"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "PACKING_MASS_BALANCE_EXCEEDED"
    assert client.get("/api/v1/traceability-records", headers=A).json()["items"] == []


def test_cross_tenant_facility_refused(client):
    _farm(client, "farm-a")
    _farm(client, "farm-b")
    client.post("/api/v1/actors", headers=B, json={
        "code": "PHC-B", "name": "B packing", "actor_type": "PACKING_HOUSE_OPERATOR"})
    r = client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-X", "facility_code": "PHC-B", "output_weight_kg": 10})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"


# ---- T-017 regression tests (two-pass review of T-016) -----------------------
def test_packing_input_requires_both_refs(client):
    """S1: a dangling link (missing either end) used to be creatable and
    later crashed traceability issuance with a 500."""
    _chain(client)
    r = client.post("/api/v1/packing-inputs", headers=A, json={
        "packing_lot_code": "PK-1", "allocated_weight_kg": 100})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_REQUIRED"
    r = client.post("/api/v1/packing-inputs", headers=A, json={
        "harvest_lot_code": "LOT-H1", "allocated_weight_kg": 100})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_REQUIRED"


def test_traceability_record_requires_unit(client):
    """M2: no record may be issued without its packaging unit."""
    _chain(client)
    r = client.post("/api/v1/traceability-records", headers=A,
                    json={"product_name": "Orphan"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TRACEABILITY_UNIT_REQUIRED"


def test_gate_not_skippable_without_norm(client):
    """M1: a packing lot without a yield norm (or output) must block
    issuance instead of silently skipping the mass-balance gate."""
    _chain(client)
    client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-NONORM", "facility_code": "PHC-01",
        "output_weight_kg": 999999, "packed_at": "2026-10-15T08:00:00"})
    client.post("/api/v1/packaging-units", headers=A, json={
        "code": "SKU-NN", "packing_lot_code": "PK-NONORM", "gtin_code": "8935000000014"})
    r = client.post("/api/v1/traceability-records", headers=A,
                    json={"packaging_unit_code": "SKU-NN"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PACKING_DATA_INCOMPLETE"


def test_duplicate_traceability_code_rejected(client):
    """M3: re-issuing for the same unit must not duplicate the code or
    the CTE chain."""
    _chain(client)
    _link(client, "LOT-H1", 5000)
    _link(client, "LOT-H2", 5000)
    client.post("/api/v1/packaging-units", headers=A, json={
        "code": "SKU-DUP", "packing_lot_code": "PK-1", "gtin_code": "8935000000021"})
    first = client.post("/api/v1/traceability-records", headers=A,
                        json={"packaging_unit_code": "SKU-DUP"})
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/traceability-records", headers=A,
                         json={"packaging_unit_code": "SKU-DUP"})
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "TRACEABILITY_CODE_EXISTS"
    records = client.get("/api/v1/traceability-records", headers=A).json()["items"]
    assert len(records) == 1
    stages = client.get("/api/v1/cte-stages", headers=A).json()["items"]
    assert len(stages) == 3  # 2 harvest + 1 packing, not doubled


def test_fresh_retention_anchors_to_harvest(client):
    """M5 (fresh case): without an expiry date, retention is the latest
    input harvest date + 12 months, not the packing date + 12."""
    _chain(client)
    client.post("/api/v1/packing-lots", headers=A, json={
        "code": "PK-FRESH", "facility_code": "PHC-01", "phc_code": "VN-PHC-66-019",
        "product_name": "Fresh pomelo", "output_weight_kg": 4000,
        "yield_norm_ratio": 0.85, "storage_type": "FRESH_AMBIENT",
        "packed_at": "2026-11-01T08:00:00"})
    _link(client, "LOT-H1", 5000, packing="PK-FRESH")  # harvested 2026-10-14
    client.post("/api/v1/packaging-units", headers=A, json={
        "code": "SKU-FRESH", "packing_lot_code": "PK-FRESH", "gtin_code": "8935000000038"})
    r = client.post("/api/v1/traceability-records", headers=A, json={
        "packaging_unit_code": "SKU-FRESH",
        "product_image_url": "https://example.org/pomelo.jpg"})
    assert r.status_code == 201, r.text
    assert r.json()["data_retention_until"] == "2027-10-14"
    assert r.json()["product_image_url"] == "https://example.org/pomelo.jpg"
