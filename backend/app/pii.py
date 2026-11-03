"""Actor PII protection (dossier Bang 6, Q-TX-03; DEC-013/T-031).

The dossier requires an actor's legal identifier (CCCD / tax code) to be
stored encrypted with an HMAC lookup hash, and the phone number
encrypted. This module implements that with the standard library only
(so it behaves identically under uvicorn and Python Workers):

- legal_id_hash: HMAC-SHA256, always computed (keyed with IAICT_PII_KEY
  when configured; otherwise a tenant-scoped deterministic hash so
  lookups/dedup still work - documented as lookup-grade, not secret).
- legal_id_encrypted / phone_encrypted: present only when a key is
  configured. Construction: HMAC-SHA256 counter-mode keystream XOR,
  encrypt-then-MAC with a truncated HMAC tag, random 16-byte nonce,
  stored as "enc1.<base64>". When encryption is active the plaintext
  fields are wiped from the stored record; the API layer restores them
  transparently on reads (see production.py).
"""
import base64
import hashlib
import hmac
import os

from . import auditctx

_PREFIX = "enc1."


def _key_bytes() -> bytes | None:
    key = auditctx.pii_key()
    if not key:
        return None
    return hashlib.sha256(key.encode("utf-8")).digest()


def hmac_hash(value: str, scope: str) -> str:
    kb = _key_bytes()
    if kb is None:
        kb = hashlib.sha256(f"iaict-nokey:{scope}".encode("utf-8")).digest()
    return hmac.new(kb, f"{scope}:{value}".encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _keystream(kb: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(kb, nonce + counter.to_bytes(4, "big"),
                        hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt(value: str) -> str | None:
    kb = _key_bytes()
    if kb is None:
        return None
    nonce = os.urandom(16)
    data = value.encode("utf-8")
    stream = _keystream(kb, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, stream))
    tag = hmac.new(kb, b"tag" + nonce + ct, hashlib.sha256).digest()[:16]
    return _PREFIX + base64.b64encode(nonce + ct + tag).decode("ascii")


def decrypt(token: str) -> str | None:
    kb = _key_bytes()
    if kb is None or not token.startswith(_PREFIX):
        return None
    try:
        raw = base64.b64decode(token[len(_PREFIX):])
        nonce, ct, tag = raw[:16], raw[16:-16], raw[-16:]
        expect = hmac.new(kb, b"tag" + nonce + ct, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(tag, expect):
            return None
        stream = _keystream(kb, nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, stream)).decode("utf-8")
    except Exception:
        return None


def protect(fields: dict, tenant: str) -> dict:
    """Return a storage-ready copy of actor fields (input not mutated)."""
    out = dict(fields)
    legal = out.get("legal_id")
    if legal:
        out["legal_id_hash"] = hmac_hash(str(legal), tenant)
        enc = encrypt(str(legal))
        if enc is not None:
            out["legal_id_encrypted"] = enc
            out["legal_id"] = None
    phone = out.get("phone")
    if phone:
        enc = encrypt(str(phone))
        if enc is not None:
            out["phone_encrypted"] = enc
            out["phone"] = None
    return out


def restore(record: dict) -> dict:
    """Return a response copy with PII decrypted and cipher blobs hidden."""
    out = dict(record)
    enc = out.pop("legal_id_encrypted", None)
    if enc and not out.get("legal_id"):
        plain = decrypt(enc)
        if plain is not None:
            out["legal_id"] = plain
    enc_p = out.pop("phone_encrypted", None)
    if enc_p and not out.get("phone"):
        plain = decrypt(enc_p)
        if plain is not None:
            out["phone"] = plain
    return out


def encryption_active() -> bool:
    return _key_bytes() is not None
