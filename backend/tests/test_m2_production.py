"""M2 production objects (ZON/MPL/FLD/LOT): CRUD, references, isolation.

These tests are backend-agnostic: they must pass identically against the
in-memory store and against PostgreSQL (TEST_DATABASE_URL). One extra test
checks true persistence across store instances on PostgreSQL only.
"""
import os

import pytest

from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}
B = {"X-Tenant-Id": "farm-b", "X-Actor": "admin"}


def _farm(client, slug="farm-a"):
    register_tenant(client, slug)
    bootstrap_admin(client, slug)


def test_zone_create_get_list_and_duplicate(client):
    _farm(client)
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "North block", "area_ha": 12.5,
                          "crop_group": "durian", "lat": 11.94, "lon": 108.43})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "Z-01" and body["tenant_id"] == "farm-a"
    assert body["area_ha"] == 12.5 and body["status"] == "ACTIVE"
    dup = client.post("/api/v1/zones", headers=A, json={"code": "Z-01", "name": "again"})
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "CODE_EXISTS"
    got = client.get("/api/v1/zones/Z-01", headers=A)
    assert got.status_code == 200 and got.json()["name"] == "North block"
    items = client.get("/api/v1/zones", headers=A).json()["items"]
    assert [i["code"] for i in items] == ["Z-01"]
    missing = client.get("/api/v1/zones/NOPE", headers=A)
    assert missing.status_code == 404


def test_zone_requires_code_and_valid_pattern(client):
    _farm(client)
    r = client.post("/api/v1/zones", headers=A, json={"name": "no code"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "CODE_REQUIRED"
    bad = client.post("/api/v1/zones", headers=A, json={"code": "bad code!"})
    assert bad.status_code == 422


def test_tenant_isolation_for_objects(client):
    _farm(client, "farm-a")
    _farm(client, "farm-b")
    client.post("/api/v1/zones", headers=A, json={"code": "Z-01", "name": "A zone"})
    assert client.get("/api/v1/zones", headers=B).json()["items"] == []
    assert client.get("/api/v1/zones/Z-01", headers=B).status_code == 404
    # The same code may exist independently in another tenant.
    r = client.post("/api/v1/zones", headers=B, json={"code": "Z-01", "name": "B zone"})
    assert r.status_code == 201
    assert client.get("/api/v1/zones/Z-01", headers=B).json()["name"] == "B zone"


def test_references_resolve_within_tenant_only(client):
    _farm(client, "farm-a")
    _farm(client, "farm-b")
    client.post("/api/v1/zones", headers=A, json={"code": "Z-01", "name": "A zone"})
    ok = client.post("/api/v1/mother-plants", headers=A,
                     json={"code": "MPL-001", "species": "Durian", "zone_code": "Z-01"})
    assert ok.status_code == 201, ok.text
    assert ok.json()["zone_code"] == "Z-01"
    unknown = client.post("/api/v1/mother-plants", headers=A,
                          json={"code": "MPL-002", "zone_code": "GHOST"})
    assert unknown.status_code == 400
    assert unknown.json()["detail"]["code"] == "REF_UNKNOWN"
    # farm-b cannot reference farm-a's zone even though the code exists there.
    cross = client.post("/api/v1/mother-plants", headers=B,
                        json={"code": "MPL-001", "zone_code": "Z-01"})
    assert cross.status_code == 400
    assert cross.json()["detail"]["code"] == "REF_UNKNOWN"


def test_plan_event_lot_chain_and_audit(client):
    _farm(client)
    client.post("/api/v1/zones", headers=A, json={"code": "Z-01", "name": "A zone"})
    plan = client.post("/api/v1/crop-plans", headers=A,
                       json={"code": "PLAN-2027", "zone_code": "Z-01",
                             "crop_name": "Durian Ri6", "status": "RUNNING",
                             "target_yield_kg": 4000})
    assert plan.status_code == 201, plan.text
    ev = client.post("/api/v1/field-events", headers=A,
                     json={"plan_code": "PLAN-2027", "event_type": "IRRIGATION",
                           "notes": "Drip line check",
                           "materials": [{"name": "NPK 20-20-15", "material_lot": "IN-88",
                                          "quantity": 25, "unit": "kg"}]})
    assert ev.status_code == 201, ev.text
    lot = client.post("/api/v1/lots", headers=A,
                      json={"code": "LOT-001", "zone_code": "Z-01", "plan_code": "PLAN-2027",
                            "harvest_date": "2027-06-15", "quantity": 1250.5, "unit": "kg",
                            "quality_grade": "A"})
    assert lot.status_code == 201, lot.text
    assert lot.json()["quantity"] == 1250.5
    events = client.get("/api/v1/field-events", headers=A).json()["items"]
    assert len(events) == 1 and events[0]["materials"][0]["material_lot"] == "IN-88"
    actions = {(e["action"], e["outcome"]) for e in
               client.get("/api/v1/audit", headers=A).json()["items"]}
    assert ("ZON_CREATE", "OK") in actions
    assert ("FLD_CREATE", "OK") in actions
    assert ("LOT_CREATE", "OK") in actions


def test_viewer_cannot_write_objects(client):
    _farm(client)
    r = client.post("/api/v1/users", headers={"X-Tenant-Id": "farm-a", "X-Actor": "admin"},
                    json={"username": "guest", "display_name": "Guest", "role": "VIEWER"})
    assert r.status_code == 201, r.text
    denied = client.post("/api/v1/zones",
                         headers={"X-Tenant-Id": "farm-a", "X-Actor": "guest"},
                         json={"code": "Z-09", "name": "nope"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "ROLE_FORBIDDEN"
    # Reads stay open to any tenant member context.
    assert client.get("/api/v1/zones", headers={"X-Tenant-Id": "farm-a"}).status_code == 200


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"),
                    reason="PostgreSQL persistence check needs TEST_DATABASE_URL")
def test_data_survives_a_fresh_store_instance(client):
    """A second PgStore on the same database sees what the API wrote:
    state lives in PostgreSQL, not in the process."""
    from app.pgstore import PgStore

    _farm(client)
    client.post("/api/v1/zones", headers=A, json={"code": "Z-77", "name": "Persisted"})
    other = PgStore(os.environ["TEST_DATABASE_URL"])
    assert other.get_tenant("farm-a") is not None
    rec = other.get_record_by_code("farm-a", "zones", "Z-77")
    assert rec is not None and rec["name"] == "Persisted"
    assert any(e["action"] == "ZON_CREATE" for e in other.audit_for_tenant("farm-a"))
