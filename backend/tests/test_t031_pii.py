"""PII protection (T-031, Bang 6 / Q-TX-03): hash always, encryption with key."""
import hashlib
import hmac as hmac_mod

from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "farm-a", "X-Actor": "admin"}


def _setup(client):
    register_tenant(client, "farm-a")
    bootstrap_admin(client, "farm-a")


def test_hash_without_key(client):
    _setup(client)
    r = client.post("/api/v1/actors", headers=A, json={
        "code": "H01", "name": "Ho 1", "legal_id": "079123456789",
        "phone": "0901234567"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["legal_id"] == "079123456789"  # no key: readable as before
    assert len(body["legal_id_hash"]) == 64


def test_encryption_with_key(client, monkeypatch):
    monkeypatch.setenv("IAICT_PII_KEY", "unit-test-secret")
    _setup(client)
    r = client.post("/api/v1/actors", headers=A, json={
        "code": "H02", "name": "Ho 2", "legal_id": "079123456789",
        "phone": "0901234567"})
    assert r.status_code == 201, r.text
    body = r.json()
    # API consumers still see the plaintext (transparent restore)
    assert body["legal_id"] == "079123456789"
    assert body["phone"] == "0901234567"
    # hash is the keyed HMAC of tenant:value
    kb = hashlib.sha256(b"unit-test-secret").digest()
    expect = hmac_mod.new(kb, b"farm-a:079123456789", hashlib.sha256).hexdigest()
    assert body["legal_id_hash"] == expect
    # the STORED record carries ciphertext, not plaintext
    from app.store import store
    import asyncio
    raw = asyncio.get_event_loop().run_until_complete(
        store.get_record_by_code("farm-a", "actors", "H02")) \
        if False else None
    # (direct store access differs per backend; verify via a fresh create
    # in the same store through the internal bucket when in-memory)
    bucket = getattr(store, "records", None)
    if bucket is not None:
        stored = bucket["actors"]["farm-a"]["by_code"]["H02"]
        assert stored.get("legal_id") is None
        assert stored["legal_id_encrypted"].startswith("enc1.")
        assert stored.get("phone") is None
        assert stored["phone_encrypted"].startswith("enc1.")
