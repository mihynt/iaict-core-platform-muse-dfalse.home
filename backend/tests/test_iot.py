"""T-005 IoT simulation ingestion slice (T-045)."""
import pytest

from tests.conftest import bootstrap_admin, register_tenant


def _setup(client):
    register_tenant(client, "t-iot")
    bootstrap_admin(client, "t-iot")
    h = {"X-Tenant-Id": "t-iot", "X-Actor": "admin"}
    client.post("/api/v1/zones", headers=h, json={"code": "Z-01"})
    client.post("/api/v1/spatial-units", headers=h, json={"code": "AO-01"})
    r = client.post("/api/v1/iot-devices", headers=h,
                    json={"code": "WQ-01", "device_type": "WATER_QUALITY_SENSOR",
                          "zone_code": "Z-01", "parcel_code": "AO-01"})
    assert r.status_code == 201, r.text
    return h


def test_ingest_disabled_without_key(client, monkeypatch):
    h = _setup(client)
    monkeypatch.delenv("IAICT_IOT_KEY", raising=False)
    r = client.post("/api/v1/iot/readings", headers={"X-Tenant-Id": "t-iot"},
                    json={"device_code": "WQ-01", "water": {"ph_value": 7.0}})
    assert r.status_code == 503
    assert r.json()["detail"]["code"] == "IOT_DISABLED"


def test_ingest_rejects_wrong_key_and_unknown_device(client, monkeypatch):
    h = _setup(client)
    monkeypatch.setenv("IAICT_IOT_KEY", "test-key")
    r = client.post("/api/v1/iot/readings",
                    headers={"X-Tenant-Id": "t-iot", "X-Iot-Key": "nope"},
                    json={"device_code": "WQ-01", "water": {"ph_value": 7.0}})
    assert r.status_code == 401
    r = client.post("/api/v1/iot/readings",
                    headers={"X-Tenant-Id": "t-iot", "X-Iot-Key": "test-key"},
                    json={"device_code": "GHOST", "water": {"ph_value": 7.0}})
    assert r.status_code == 404


def test_ingest_lands_water_and_trap_records(client, monkeypatch):
    h = _setup(client)
    monkeypatch.setenv("IAICT_IOT_KEY", "test-key")
    r = client.post("/api/v1/iot/readings",
                    headers={"X-Tenant-Id": "t-iot", "X-Iot-Key": "test-key"},
                    json={"device_code": "WQ-01",
                          "measured_at": "2026-11-04T07:00:00",
                          "water": {"ph_value": 7.4, "water_temp_celsius": 28.5,
                                    "dissolved_oxygen_mg_l": 6.1},
                          "trap": {"pest_species_detected": "Sau cuon la",
                                   "pest_density_index": "3 con/bay"}})
    assert r.status_code == 201, r.text
    body = r.json()
    tests = client.get("/api/v1/water-quality-tests", headers=h).json()["items"]
    assert len(tests) == 1
    assert tests[0]["id"] == body["water_test_id"]
    assert tests[0]["parcel_code"] == "AO-01"
    assert tests[0]["ph_value"] == 7.4
    mons = client.get("/api/v1/monitoring-declarations", headers=h).json()["items"]
    assert len(mons) == 1
    assert mons[0]["monitoring_type"] == "AI_INSECT_TRAP_REALTIME"
    assert mons[0]["zone_code"] == "Z-01"
