"""T-005 IoT ingestion with per-device keys (T-045 slice + T-046 keys)."""
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
    return h, r.json()


def _reading(client, key=None, device="WQ-01", **kw):
    headers = {"X-Tenant-Id": "t-iot"}
    if key is not None:
        headers["X-Iot-Key"] = key
    body = {"device_code": device,
            "water": {"ph_value": 7.4, "water_temp_celsius": 28.5}}
    body.update(kw)
    return client.post("/api/v1/iot/readings", headers=headers, json=body)


def test_key_issued_once_and_never_listed(client):
    h, created = _setup(client)
    assert created["device_key"].startswith("iotk_")
    assert "key_hash" not in created
    items = client.get("/api/v1/iot-devices", headers=h).json()["items"]
    assert len(items) == 1
    assert "key_hash" not in items[0]
    assert "device_key" not in items[0]


def test_ingest_requires_the_device_key(client):
    h, created = _setup(client)
    key = created["device_key"]
    assert _reading(client).status_code == 401               # no header
    assert _reading(client, key="iotk_wrong").status_code == 401
    assert _reading(client, key=key, device="GHOST").status_code == 404
    r = _reading(client, key=key,
                 trap={"pest_species_detected": "Sau cuon la",
                       "pest_density_index": "3 con/bay"})
    assert r.status_code == 201, r.text
    tests = client.get("/api/v1/water-quality-tests", headers=h).json()["items"]
    assert len(tests) == 1 and tests[0]["parcel_code"] == "AO-01"
    mons = client.get("/api/v1/monitoring-declarations", headers=h).json()["items"]
    assert len(mons) == 1
    assert mons[0]["monitoring_type"] == "AI_INSECT_TRAP_REALTIME"


def test_rotate_and_revoke(client):
    h, created = _setup(client)
    old_key = created["device_key"]
    r = client.post("/api/v1/iot-devices/WQ-01/rotate-key", headers=h)
    assert r.status_code == 200, r.text
    new_key = r.json()["device_key"]
    assert new_key != old_key
    assert _reading(client, key=old_key).status_code == 401
    assert _reading(client, key=new_key).status_code == 201
    r = client.post("/api/v1/iot-devices/WQ-01/revoke-key", headers=h)
    assert r.status_code == 200 and r.json()["revoked"] is True
    r = _reading(client, key=new_key)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "DEVICE_KEY_INACTIVE"
    assert client.post("/api/v1/iot-devices/NOPE/rotate-key",
                       headers=h).status_code == 404
