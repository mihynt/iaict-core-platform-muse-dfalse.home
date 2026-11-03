"""Field & relation consistency (T-029, Owner review 2026-11-03 23:10).

The dossier (Bang 7) models a production zone as OWNED BY an actor:
zones.owner_actor_code is a validated reference, and it protects the
actor from deletion while a zone points at it.
"""
from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")


def test_zone_owner_reference_roundtrip(client):
    _setup(client)
    r = client.post("/api/v1/actors", headers=A,
                    json={"code": "DN-01", "name": "Cong ty A",
                          "actor_type": "COMPANY"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-01", "name": "Zone 1",
                          "owner_actor_code": "DN-01"})
    assert r.status_code == 201, r.text
    assert r.json()["owner_actor_code"] == "DN-01"
    # the owner actor cannot be deleted while the zone references it
    r = client.delete("/api/v1/actors/DN-01", headers=A)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "RECORD_IN_USE"


def test_zone_owner_must_exist(client):
    _setup(client)
    r = client.post("/api/v1/zones", headers=A,
                    json={"code": "Z-02", "owner_actor_code": "GHOST"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "REF_UNKNOWN"


def test_actor_bool_fields_accepted(client):
    _setup(client)
    r = client.post("/api/v1/actors", headers=A,
                    json={"code": "H09", "name": "Ho 9",
                          "is_group_leader": True,
                          "ics_training_completed": False,
                          "gs1_role_ai": "(91)X"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["is_group_leader"] is True
    assert body["gs1_role_ai"] == "(91)X"
