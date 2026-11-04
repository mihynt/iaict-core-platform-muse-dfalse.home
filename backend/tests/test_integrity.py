"""T-050 (SOW D-10 / BLC): Data Integrity checkpoints + verifier.

Covers the JCS canonicalization vectors, the Merkle construction rules,
the seal -> verify flow, Merkle inclusion proofs, tamper evidence
(edit and delete a sealed audit row at the storage layer), and the
keyed (HMAC) mode with key rotation behaviour.
"""
import hashlib

import pytest

from app import integrity as ig
from app.store import store
from tests.conftest import bootstrap_admin, register_tenant

H = {"X-Tenant-Id": "t-int", "X-Actor": "admin"}


# ---------------------------------------------------------------------------
# Canonicalization + Merkle units (D-10 asks for published test vectors)
# ---------------------------------------------------------------------------

def test_jcs_rfc8785_number_vectors():
    assert ig.jcs(333333333.33333329) == "333333333.3333333"
    assert ig.jcs(1e30) == "1e+30"
    assert ig.jcs(4e-50) == "4e-50"
    assert ig.jcs(2e-3) == "0.002"
    assert ig.jcs(1e21) == "1e+21"
    assert ig.jcs(1e-7) == "1e-7"
    assert ig.jcs(0.000001) == "0.000001"
    assert ig.jcs(123456789012345680000.0) == "123456789012345680000"
    assert ig.jcs(-0.0) == "0"
    assert ig.jcs(10.5) == "10.5"
    assert ig.jcs(100.0) == "100"


def test_jcs_structure_vectors():
    assert ig.jcs({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    # keys sort by UTF-16 code units: U+1F600 (surrogate pair) before U+FB00
    assert ig.jcs({"😀": 1, "ﬀ": 2}) == '{"😀":1,"ﬀ":2}'
    assert ig.jcs("a\"b\\c\nd") == '"a\\"b\\\\c\\nd"'
    assert ig.jcs([True, False, None]) == "[true,false,null]"
    assert ig.jcs({"x": [{"y": 2.5}]}) == '{"x":[{"y":2.5}]}'


def test_merkle_rules_and_proofs():
    h = [hashlib.sha256(f"leaf-{i}".encode()).digest() for i in range(5)]
    # odd node duplicated: root of 3 = H(H(h0|h1) | H(h2|h2)) with 0x02 domain
    p = lambda a, b: hashlib.sha256(b"\x02" + a + b).digest()
    assert ig.merkle_root(h[:3]) == p(p(h[0], h[1]), p(h[2], h[2]))
    assert ig.merkle_root(h[:1]) == h[0]
    root = ig.merkle_root(h)
    for i in range(5):
        proof = ig.merkle_proof(h, i)
        assert ig.proof_root(h[i], proof) == root


def test_published_demo_vector():
    """The exact values published in docs/INTEGRITY.md section 7 (D-10)."""
    rows = [
        {"seq": 1, "ts": "2026-11-04T01:00:00Z", "tenant_id": "demo",
         "actor": "admin", "action": "ZON_CREATE", "target": "zones/Z-01",
         "outcome": "OK", "old_value": None,
         "new_value": '{"code": "Z-01", "initial_declared_area_ha": 10.5}'},
        {"seq": 2, "ts": "2026-11-04T01:05:00Z", "tenant_id": "demo",
         "actor": "admin", "action": "PLAN_CREATE",
         "target": "crop_plans/PLAN-2026", "outcome": "OK", "old_value": None,
         "new_value": '{"code": "PLAN-2026", "target_yield_kg": 5000}'},
        {"seq": 3, "ts": "2026-11-04T02:00:00Z", "tenant_id": "demo",
         "actor": "op1", "action": "LOT_CREATE", "target": "lots/L-01",
         "outcome": "OK", "old_value": None,
         "new_value": '{"code": "L-01", "quantity": 120}'},
    ]
    events, head = ig.compute_batch(rows, ig.genesis("demo"), None)
    assert [e.hex() for e in events] == [
        "1568c700a9b86b722cecc45d527b91b81cdf1d1cb9b8dbf08e3bcc29e6c42e9d",
        "a781ec8aab86fd22b21cd32e39640b75205f34099ee8cbbdd2d14db3ae69e21f",
        "9ace13dee2cc6764ca8372b16b0219d0a19c0cc81668a0f94003f059de9dcdc2"]
    assert head.hex() == "ca2be75624a9a96d608301b021eb790d2a81828c6a1620ae6bffbb0652cb15a4"
    assert ig.merkle_root(events).hex() == \
        "d041bb003a0ad41e6da70ce297d8da6774f87a56dcaf0ff823e412d0664e12d3"


def test_envelope_normalizes_snapshots():
    row = {"seq": 7, "ts": "2026-11-04T00:00:00Z", "tenant_id": "t",
           "actor": "a", "action": "X", "target": "y", "outcome": "OK",
           "old_value": '{"kg": 10.5}', "new_value": None}
    env = ig.envelope(row)
    assert env["old"] == {"kg": 10.5} and env["new"] is None
    assert ig.jcs(env).startswith('{"action":"X","actor":"a"')


# ---------------------------------------------------------------------------
# API flow
# ---------------------------------------------------------------------------

def _setup(client):
    register_tenant(client, "t-int")
    bootstrap_admin(client, "t-int")
    r = client.post("/api/v1/zones", headers=H, json={"code": "Z-01"})
    assert r.status_code == 201, r.text


def test_seal_verify_and_proof_flow(client):
    _setup(client)
    r = client.get("/api/v1/integrity/checkpoints", headers=H)
    assert r.json()["items"] == [] and r.json()["unsealed_rows"] > 0
    assert client.get("/api/v1/integrity/verify", headers=H).json()["status"] == "EMPTY"

    r = client.post("/api/v1/integrity/checkpoints", headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created"]) >= 1
    cp = body["created"][0]
    assert cp["canon_id"] == "RFC8785-JCS" and cp["hash_alg"] == "SHA-256"
    assert cp["key_id"] == "none" and len(cp["merkle_root"]) == 64
    # the INTEGRITY_CHECKPOINT audit row itself is the one unsealed row
    assert body["unsealed_rows"] == 1

    v = client.get("/api/v1/integrity/verify", headers=H).json()
    assert v["status"] == "VALID" and v["first_break"] is None
    assert v["sealed_rows"] == cp["leaf_count"]

    seq = cp["from_seq"]
    p = client.get(f"/api/v1/integrity/proof/{seq}", headers=H)
    assert p.status_code == 200, p.text
    pj = p.json()
    assert pj["root_matches_checkpoint"] is True
    assert pj["merkle_root"] == cp["merkle_root"]
    rebuilt = ig.proof_root(bytes.fromhex(pj["event_hash"]), pj["proof"])
    assert rebuilt.hex() == pj["merkle_root"]
    assert pj["anchor"]["status"] == "NOT_ENABLED"

    r = client.get("/api/v1/integrity/proof/999999", headers=H)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "PROOF_NOT_SEALED"

    # sealing again seals the checkpoint audit row itself; chain stays valid
    r = client.post("/api/v1/integrity/checkpoints", headers=H)
    assert len(r.json()["created"]) >= 1
    v = client.get("/api/v1/integrity/verify", headers=H).json()
    assert v["status"] == "VALID" and len(v["checkpoints"]) >= 2


def test_checkpoint_requires_tenant_admin(client):
    _setup(client)
    r = client.post("/api/v1/users", headers=H,
                    json={"username": "op1", "display_name": "Op", "role": "OPERATOR"})
    assert r.status_code in (200, 201), r.text
    r = client.post("/api/v1/integrity/checkpoints",
                    headers={"X-Tenant-Id": "t-int", "X-Actor": "op1"})
    assert r.status_code == 403


def test_tenant_isolation(client):
    _setup(client)
    register_tenant(client, "t-other")
    bootstrap_admin(client, "t-other")
    ho = {"X-Tenant-Id": "t-other", "X-Actor": "admin"}
    client.post("/api/v1/integrity/checkpoints", headers=H)
    assert client.get("/api/v1/integrity/verify", headers=ho).json()["status"] == "EMPTY"
    assert client.get("/api/v1/integrity/checkpoints", headers=ho).json()["items"] == []


# ---------------------------------------------------------------------------
# Tamper evidence (storage-layer rewrite, bypassing the API)
# ---------------------------------------------------------------------------

def _tamper(sqlite_sql=None, memory_mutate=None):
    impl = getattr(store, "_impl", None) or store
    if hasattr(impl, "audit"):
        memory_mutate(impl.audit)
        return
    conn = getattr(getattr(impl, "_db", None), "_conn", None)
    if conn is not None and sqlite_sql:
        conn.execute(sqlite_sql)
        conn.commit()
        return
    pytest.skip("storage tamper drive unavailable for this backend")


def test_verify_detects_edited_history(client):
    _setup(client)
    client.post("/api/v1/integrity/checkpoints", headers=H)
    _tamper(
        sqlite_sql="UPDATE audit_log SET action='FORGED_ACTION'"
                   " WHERE seq=(SELECT MIN(seq) FROM audit_log)",
        memory_mutate=lambda rows: rows[0].__setitem__("action", "FORGED_ACTION"))
    v = client.get("/api/v1/integrity/verify", headers=H).json()
    assert v["status"] == "INVALID"
    assert v["first_break"]["reason"] in (
        "CHAIN_MISMATCH", "ROOT_MISMATCH", "ROW_COUNT_MISMATCH")


def test_verify_detects_deleted_history(client):
    _setup(client)
    client.post("/api/v1/integrity/checkpoints", headers=H)

    def _delete(rows):
        rows.pop(0)
    _tamper(
        sqlite_sql="DELETE FROM audit_log"
                   " WHERE seq=(SELECT MIN(seq) FROM audit_log)",
        memory_mutate=_delete)
    v = client.get("/api/v1/integrity/verify", headers=H).json()
    assert v["status"] == "INVALID"
    assert v["first_break"]["reason"] == "ROW_COUNT_MISMATCH"


# ---------------------------------------------------------------------------
# Keyed mode (BLC-07)
# ---------------------------------------------------------------------------

def test_keyed_checkpoints_and_rotation(client, monkeypatch):
    _setup(client)
    monkeypatch.setenv("IAICT_INTEGRITY_KEY", "test-integrity-key-1")
    r = client.post("/api/v1/integrity/checkpoints", headers=H)
    cp = r.json()["created"][0]
    assert cp["hash_alg"] == "HMAC-SHA-256"
    assert cp["key_id"] == ig.key_id("test-integrity-key-1") != "none"
    assert client.get("/api/v1/integrity/verify", headers=H).json()["status"] == "VALID"
    # after rotation the historical checkpoint is attributable but unverifiable
    monkeypatch.setenv("IAICT_INTEGRITY_KEY", "test-integrity-key-2")
    v = client.get("/api/v1/integrity/verify", headers=H).json()
    assert v["status"] == "UNVERIFIABLE"
    assert v["checkpoints"][0]["status"] == "KEY_UNAVAILABLE"
    p = client.get(f"/api/v1/integrity/proof/{cp['from_seq']}", headers=H)
    assert p.status_code == 409
    assert p.json()["detail"]["code"] == "KEY_UNAVAILABLE"
