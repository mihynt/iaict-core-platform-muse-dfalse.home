"""T-047 cleanup: pagination (P2-b), full GS1 (L1), per-SKU gate (L4)."""
from tests.conftest import bootstrap_admin, register_tenant


def _setup(client, slug="t-clean"):
    register_tenant(client, slug)
    bootstrap_admin(client, slug)
    return {"X-Tenant-Id": slug, "X-Actor": "admin"}


def test_list_pagination(client):
    h = _setup(client)
    for i in range(5):
        r = client.post("/api/v1/zones", headers=h, json={"code": f"Z-{i}"})
        assert r.status_code == 201
    full = client.get("/api/v1/zones", headers=h).json()
    assert full["total"] == 5 and len(full["items"]) == 5
    page = client.get("/api/v1/zones?limit=2&offset=2", headers=h).json()
    assert page["total"] == 5 and page["limit"] == 2 and page["offset"] == 2
    assert [z["code"] for z in page["items"]] == ["Z-2", "Z-3"]
    tail = client.get("/api/v1/zones?limit=2&offset=4", headers=h).json()
    assert [z["code"] for z in tail["items"]] == ["Z-4"]


def test_gs1_check_digit_enforced(client):
    h = _setup(client)
    client.post("/api/v1/actors", headers=h, json={"code": "CS-1"})
    client.post("/api/v1/packing-lots", headers=h,
                json={"code": "PK-1", "facility_code": "CS-1"})
    bad = client.post("/api/v1/packaging-units", headers=h, json={
        "code": "SKU-BAD", "packing_lot_code": "PK-1",
        "gtin_code": "08935049501234"})  # the old sample: check digit off by one
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "GTIN_CHECK_DIGIT_INVALID"
    short = client.post("/api/v1/packaging-units", headers=h, json={
        "code": "SKU-SHORT", "packing_lot_code": "PK-1", "gtin_code": "111"})
    assert short.status_code == 400
    assert short.json()["detail"]["code"] == "GTIN_INVALID"
    ok = client.post("/api/v1/packaging-units", headers=h, json={
        "code": "SKU-OK", "packing_lot_code": "PK-1",
        "gtin_code": "08935049501237"})
    assert ok.status_code == 201, ok.text


def _packing_chain(client, h, output=100.0):
    client.post("/api/v1/zones", headers=h, json={"code": "Z-01"})
    client.post("/api/v1/actors", headers=h, json={"code": "CS-1"})
    client.post("/api/v1/lots", headers=h, json={
        "code": "L-1", "zone_code": "Z-01", "harvest_date": "2026-10-01",
        "quantity_kg": 500})
    client.post("/api/v1/packing-lots", headers=h, json={
        "code": "PK-1", "facility_code": "CS-1",
        "output_weight_kg": output, "yield_norm_ratio": 0.5,
        "storage_type": "FRESH_AMBIENT", "packed_at": "2026-10-15T08:00:00"})
    client.post("/api/v1/packing-inputs", headers=h, json={
        "packing_lot_code": "PK-1", "harvest_lot_code": "L-1",
        "allocated_weight_kg": 500})


_GTINS = {"SKU-A": "8935000000014", "SKU-B": "8935000000021",
          "SKU-C": "8935000000038", "SKU-NW": "8935000000014"}


def _unit(client, h, code, units, weight):
    r = client.post("/api/v1/packaging-units", headers=h, json={
        "code": code, "packing_lot_code": "PK-1",
        "gtin_code": _GTINS[code], "units_count": units,
        "unit_weight_kg": weight})
    assert r.status_code == 201, r.text


def _issue(client, h, unit_code):
    return client.post("/api/v1/traceability-records", headers=h, json={
        "packaging_unit_code": unit_code, "product_name": "Ca phe",
        "product_image_url": "https://example.org/a.jpg",
        "production_event_time": "2026-10-15T08:00:00"})


def test_sku_cumulative_gate(client):
    h = _setup(client)
    _packing_chain(client, h, output=100.0)
    _unit(client, h, "SKU-A", 10, 6.0)    # 60 kg
    _unit(client, h, "SKU-B", 10, 5.0)    # 50 kg -> 110 > 100 blocked
    _unit(client, h, "SKU-C", 10, 4.0)    # 40 kg -> exactly 100 allowed
    assert _issue(client, h, "SKU-A").status_code == 201
    r = _issue(client, h, "SKU-B")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PACKING_OUTPUT_EXCEEDED"
    assert _issue(client, h, "SKU-C").status_code == 201


def test_sku_gate_skipped_without_declared_weight(client):
    h = _setup(client)
    _packing_chain(client, h, output=100.0)
    r = client.post("/api/v1/packaging-units", headers=h, json={
        "code": "SKU-NW", "packing_lot_code": "PK-1",
        "gtin_code": "8935000000014", "units_count": 99999})
    assert r.status_code == 201
    assert _issue(client, h, "SKU-NW").status_code == 201
