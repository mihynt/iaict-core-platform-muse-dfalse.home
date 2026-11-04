"""GD3 monitoring group: Bang 14, 16, 19, 20, 21, 22."""
from tests.conftest import bootstrap_admin, register_tenant


def _setup(client):
    register_tenant(client, "t-mon")
    bootstrap_admin(client, "t-mon")
    h = {"X-Tenant-Id": "t-mon", "X-Actor": "admin"}
    client.post("/api/v1/zones", headers=h, json={"code": "Z-01"})
    client.post("/api/v1/actors", headers=h, json={"code": "A-01", "name": "Co so 1"})
    client.post("/api/v1/crop-plans", headers=h, json={"code": "P-01", "zone_code": "Z-01"})
    client.post("/api/v1/ref-market-regulations", headers=h, json={"code": "CN"})
    client.post("/api/v1/ref-active-substance-mrls", headers=h,
                json={"code": "MRL-1", "market_code": "CN", "mrl_threshold_value": 0.05})
    return h


def test_livestock_units(client):
    h = _setup(client)
    r = client.post("/api/v1/livestock-units", headers=h,
                    json={"code": "TAG-001", "facility_actor_code": "A-01",
                          "management_granularity": "INDIVIDUAL_ANIMAL",
                          "species_code": "CATTLE", "initial_head_count": 1,
                          "current_head_count": 1, "lifecycle_status": "ACTIVE_REARING"})
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    r = client.patch(f"/api/v1/livestock-units/{rec_id}", headers=h,
                     json={"lifecycle_status": "EXPORTED_TO_SLAUGHTER"})
    assert r.status_code == 200
    r = client.post("/api/v1/livestock-units", headers=h,
                    json={"code": "TAG-001", "facility_actor_code": "A-01"})
    assert r.status_code == 409


def test_supervision_and_monitoring(client):
    h = _setup(client)
    r = client.post("/api/v1/pre-harvest-supervisions", headers=h,
                    json={"plan_code": "P-01", "zone_code": "Z-01",
                          "registration_date": "2026-09-01",
                          "expected_harvest_start": "2026-10-01",
                          "supervision_outcome": "APPROVED_FOR_HARVEST"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/monitoring-declarations", headers=h,
                    json={"zone_code": "Z-01", "plan_code": "P-01",
                          "declarant_actor_code": "A-01",
                          "monitoring_type": "PEST_DISEASE_SURVEY",
                          "compliance_conclusion": "COMPLIANT"})
    assert r.status_code == 201, r.text
    mon_id = r.json()["id"]
    # water test hangs off the monitoring record by id (plain reference)
    r = client.post("/api/v1/water-quality-tests", headers=h,
                    json={"monitoring_id": mon_id, "ph_value": 7.2,
                          "water_salinity_permille": 0.4, "is_within_safe_range": True})
    assert r.status_code == 201, r.text
    # livestock declaration item
    r = client.post("/api/v1/livestock-decl-items", headers=h,
                    json={"monitoring_id": mon_id,
                          "species_category_code": "BUFFALO_CATTLE_HORSE",
                          "declared_quantity": 12, "quantity_unit": "HEAD_COUNT"})
    assert r.status_code == 201, r.text


def test_residue_exceeded_flag_is_generated(client):
    h = _setup(client)
    r = client.post("/api/v1/residue-test-details", headers=h,
                    json={"mrl_rule_code": "MRL-1", "measured_value": 0.09,
                          "applied_mrl_limit": 0.05, "measurement_unit": "MG_PER_KG",
                          "is_mrl_exceeded": False})
    assert r.status_code == 201, r.text
    assert r.json()["is_mrl_exceeded"] is True  # server-generated, input ignored
    r = client.post("/api/v1/residue-test-details", headers=h,
                    json={"mrl_rule_code": "MRL-1", "measured_value": 0.01,
                          "applied_mrl_limit": 0.05})
    assert r.json()["is_mrl_exceeded"] is False
