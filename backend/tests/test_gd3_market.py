"""GD3 group B: market approvals (Bang 8), foreign warnings (Bang 9),
entity certifications (Bang 10)."""
from tests.conftest import bootstrap_admin, register_tenant


def _setup(client):
    register_tenant(client, "t-mkt")
    bootstrap_admin(client, "t-mkt")
    h = {"X-Tenant-Id": "t-mkt", "X-Actor": "admin"}
    client.post("/api/v1/zones", headers=h, json={"code": "Z-01"})
    client.post("/api/v1/actors", headers=h, json={"code": "A-01", "name": "Co so 1"})
    client.post("/api/v1/ref-market-regulations", headers=h,
                json={"code": "CN", "market_name": "Trung Quoc"})
    client.post("/api/v1/ref-certification-schemes", headers=h,
                json={"code": "VIETGAP", "scheme_name": "VietGAP"})
    return h


def test_zone_market_approval_lifecycle(client):
    h = _setup(client)
    r = client.post("/api/v1/zone-market-approvals", headers=h,
                    json={"zone_code": "Z-01", "market_code": "CN",
                          "foreign_market_status": "PENDING_FOREIGN_APPROVAL"})
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    # same zone+market pair cannot be linked twice
    r = client.post("/api/v1/zone-market-approvals", headers=h,
                    json={"zone_code": "Z-01", "market_code": "CN"})
    assert r.status_code == 409, r.text
    # unknown market rejected
    r = client.post("/api/v1/zone-market-approvals", headers=h,
                    json={"zone_code": "Z-01", "market_code": "ZZ"})
    assert r.status_code == 400
    # status evolves via by-id PATCH
    r = client.patch(f"/api/v1/zone-market-approvals/{rec_id}", headers=h,
                     json={"foreign_market_status": "APPROVED_FOR_EXPORT",
                           "foreign_approval_code": "GACC-Z01-CN",
                           "foreign_approved_date": "2026-10-01"})
    assert r.status_code == 200, r.text
    assert r.json()["foreign_market_status"] == "APPROVED_FOR_EXPORT"
    r = client.patch("/api/v1/zone-market-approvals/99999", headers=h,
                     json={"foreign_market_status": "APPROVED_FOR_EXPORT"})
    assert r.status_code == 404


def test_foreign_warning_record(client):
    h = _setup(client)
    r = client.post("/api/v1/foreign-warnings", headers=h,
                    json={"zone_code": "Z-01", "market_code": "CN",
                          "violated_facility_actor_code": "A-01",
                          "official_notice_number": "GACC-2026-118",
                          "notification_date": "2026-09-15",
                          "violation_type": "MRL_RESIDUE_EXCEEDED",
                          "detected_pest_or_substance": "Chlorpyrifos",
                          "foreign_sanction_action": "WARNING_INVESTIGATION_REQUIRED"})
    assert r.status_code == 201, r.text
    items = client.get("/api/v1/foreign-warnings", headers=h).json()["items"]
    assert len(items) == 1
    assert items[0]["official_notice_number"] == "GACC-2026-118"


def test_certification_target_rule(client):
    h = _setup(client)
    # zone-type certification without a zone is rejected
    r = client.post("/api/v1/entity-certifications", headers=h,
                    json={"certified_entity_type": "PRODUCTION_ZONE",
                          "scheme_code": "VIETGAP", "certificate_number": "VG-1"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "CERT_TARGET_REQUIRED"
    # facility-type without a facility is rejected
    r = client.post("/api/v1/entity-certifications", headers=h,
                    json={"certified_entity_type": "FACILITY_ACTOR",
                          "scheme_code": "VIETGAP", "certificate_number": "VG-2"})
    assert r.status_code == 400
    # valid zone certification
    r = client.post("/api/v1/entity-certifications", headers=h,
                    json={"certified_entity_type": "PRODUCTION_ZONE",
                          "zone_code": "Z-01", "scheme_code": "VIETGAP",
                          "certificate_number": "VG-1", "cert_status": "VALID",
                          "issue_date": "2026-01-01", "expiry_date": "2029-01-01"})
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    r = client.patch(f"/api/v1/entity-certifications/{rec_id}", headers=h,
                     json={"cert_status": "SUSPENDED"})
    assert r.status_code == 200
    assert r.json()["cert_status"] == "SUSPENDED"
