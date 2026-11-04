"""GD3 phase 3, REF catalogue group (Bang 1-5) + zone jurisdiction link."""
from tests.conftest import bootstrap_admin, register_tenant


def _setup(client):
    register_tenant(client, "t-ref")
    bootstrap_admin(client, "t-ref")
    return {"X-Tenant-Id": "t-ref", "X-Actor": "admin"}


def test_admin_units_tree_and_zone_link(client):
    admin = _setup(client)
    r = client.post("/api/v1/ref-admin-units", headers=admin,
                    json={"code": "66", "admin_level": "PROVINCE_CITY",
                          "official_name": "Dak Lak", "puc_prefix_code": "66"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/ref-admin-units", headers=admin,
                    json={"code": "24370", "parent_unit_code": "66",
                          "admin_level": "COMMUNE_WARD",
                          "official_name": "Ea Tan", "puc_prefix_code": "24370"})
    assert r.status_code == 201, r.text
    # unknown parent is rejected
    r = client.post("/api/v1/ref-admin-units", headers=admin,
                    json={"code": "99999", "parent_unit_code": "NOPE"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"
    # zone can now link its jurisdiction commune (Bang 7 via Bang 1)
    r = client.post("/api/v1/zones", headers=admin,
                    json={"code": "Z-REF", "jurisdiction_commune_code": "24370"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/zones", headers=admin,
                    json={"code": "Z-BAD", "jurisdiction_commune_code": "00000"})
    assert r.status_code == 400
    # an admin unit referenced by a zone cannot be deleted
    r = client.delete("/api/v1/ref-admin-units/24370", headers=admin)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "RECORD_IN_USE"


def test_market_mrl_chain(client):
    admin = _setup(client)
    r = client.post("/api/v1/ref-market-regulations", headers=admin,
                    json={"code": "CN", "market_name": "Trung Quoc",
                          "requires_bilateral_pre_approval": True,
                          "competent_authority_name": "GACC"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/ref-active-substance-mrls", headers=admin,
                    json={"code": "MRL-CLP-CN", "substance_code": "2921-88-2",
                          "substance_name": "Chlorpyrifos",
                          "substance_category": "PESTICIDE_ACTIVE",
                          "market_code": "CN", "commodity_group_code": "DURIAN",
                          "approval_status": "STRICTLY_BANNED",
                          "default_phi_days": 0,
                          "legal_circular_ref": "Danh muc BVTV Viet Nam",
                          "effective_from": "2026-01-01"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["market_code"] == "CN"
    assert body["approval_status"] == "STRICTLY_BANNED"
    # unknown market rejected
    r = client.post("/api/v1/ref-active-substance-mrls", headers=admin,
                    json={"code": "MRL-X", "market_code": "ZZ"})
    assert r.status_code == 400
    # patch + duplicate code guard
    r = client.patch("/api/v1/ref-market-regulations/CN", headers=admin,
                     json={"quarantine_special_rules": "Bao trai 60 ngay"})
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/ref-market-regulations", headers=admin,
                    json={"code": "CN", "market_name": "Dup"})
    assert r.status_code == 409


def test_schemes_and_transport_modes(client):
    admin = _setup(client)
    r = client.post("/api/v1/ref-certification-schemes", headers=admin,
                    json={"code": "GLOBALGAP_V6", "scheme_name": "GLOBALG.A.P. v6",
                          "scheme_level": "INTERNATIONAL_STANDARD",
                          "applicable_sector": "CROP_FARMING"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/ref-transport-modes", headers=admin,
                    json={"code": "ROAD_TRUCK", "mode_name": "Duong bo",
                          "vehicle_id_format_rule": "Bien kiem soat xe tai"})
    assert r.status_code == 201, r.text
    items = client.get("/api/v1/ref-transport-modes", headers=admin).json()["items"]
    assert [x["code"] for x in items] == ["ROAD_TRUCK"]
