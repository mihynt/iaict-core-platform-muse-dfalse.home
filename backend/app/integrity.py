"""Data Integrity verifier (SOW D-10 / group BLC) — T-050.

Tamper-evidence for the tenant audit ledger (Bang 33) built from three
documented, versioned constructions (see docs/INTEGRITY.md):

1. Canonicalization: RFC 8785 (JCS) of the audit event envelope
   (BLC-01). Envelope schema_version 1:
   {v, seq, ts, tenant, actor, action, target, outcome, old, new}
   where old/new are the parsed JSON snapshots (or null). Request
   metadata (client_ip, user_agent) is deliberately excluded.
2. Event hash: SHA-256 over the canonical bytes; when an integrity key
   is configured (IAICT_INTEGRITY_KEY, held in the platform secret
   store — BLC-07) HMAC-SHA-256 is used instead and the checkpoint
   records hash_alg + a key fingerprint (key_id) so historical
   checkpoints stay attributable after rotation.
3. Hash chain + Merkle checkpoints (BLC-02): event hashes are chained
   with a domain-separated link  chain_i = SHA-256(0x01 | chain_{i-1} |
   event_i)  starting from a per-tenant genesis, and grouped per UTC
   day into checkpoints whose Merkle root uses node hash
   SHA-256(0x02 | left | right), leaves ordered by seq ascending, an
   odd trailing node duplicated. tree_version 1.

Anchoring (BLC-03/04/05/08/09) is intentionally NOT built in: it is
conditional on an IAICT decision (SOW Q.2). Checkpoints expose their
root + metadata through an export shape an anchoring adapter can
consume without touching business logic.
"""
import hashlib
import hmac as _hmac
import json

SCHEMA_VERSION = 1
CANON_ID = "RFC8785-JCS"
TREE_VERSION = 1

# ---------------------------------------------------------------------------
# RFC 8785 (JCS) canonicalization
# ---------------------------------------------------------------------------

_ESCAPES = {
    0x22: '\\"', 0x5C: "\\\\", 0x08: "\\b", 0x09: "\\t",
    0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r",
}


def _jcs_string(s: str) -> str:
    out = ['"']
    for ch in s:
        code = ord(ch)
        esc = _ESCAPES.get(code)
        if esc is not None:
            out.append(esc)
        elif code < 0x20:
            out.append("\\u%04x" % code)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _jcs_number(x: float) -> str:
    """ECMAScript Number::toString (radix 10), as RFC 8785 requires."""
    if x == 0:
        return "0"
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError("JCS cannot serialize NaN/Infinity")
    sign = "-" if x < 0 else ""
    r = repr(abs(x))
    if "e" in r:
        mant, e = r.split("e")
        e = int(e)
    else:
        mant, e = r, 0
    if "." in mant:
        ip, fp = mant.split(".")
        digits = ip + fp
        e -= len(fp)
    else:
        digits = mant
    digits = digits.lstrip("0")
    stripped = digits.rstrip("0")
    e += len(digits) - len(stripped)
    digits = stripped
    k = len(digits)
    n = e + k  # value = 0.<digits> * 10^n
    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    exp = n - 1
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return sign + mantissa + "e" + ("+" if exp >= 0 else "-") + str(abs(exp))


def jcs(value) -> str:
    """Serialize a JSON value to its RFC 8785 canonical form."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _jcs_number(value)
    if isinstance(value, str):
        return _jcs_string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(jcs(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(),
                      key=lambda k: k.encode("utf-16-be", "surrogatepass"))
        return "{" + ",".join(
            _jcs_string(k) + ":" + jcs(value[k]) for k in keys) + "}"
    raise TypeError(f"not a JSON value: {type(value)!r}")


# ---------------------------------------------------------------------------
# Event envelope, hashes, chain, Merkle
# ---------------------------------------------------------------------------

def _json_value(raw):
    """Normalize a stored snapshot (JSON text, dict or None) to a JSON value."""
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return raw
    return raw


def envelope(row: dict) -> dict:
    """The canonical event envelope (schema v1) for one audit row."""
    return {
        "v": SCHEMA_VERSION,
        "seq": row["seq"],
        "ts": str(row["ts"]),
        "tenant": row.get("tenant_id"),
        "actor": row.get("actor"),
        "action": row.get("action"),
        "target": row.get("target"),
        "outcome": row.get("outcome"),
        "old": _json_value(row.get("old_value")),
        "new": _json_value(row.get("new_value")),
    }


def key_id(key: str | None) -> str:
    if not key:
        return "none"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def event_hash(row: dict, key: str | None) -> bytes:
    data = jcs(envelope(row)).encode("utf-8")
    if key:
        return _hmac.new(key.encode(), data, hashlib.sha256).digest()
    return hashlib.sha256(data).digest()


def genesis(tenant_id: str) -> bytes:
    return hashlib.sha256(
        b"IAICT-INTEGRITY-GENESIS-v1:" + tenant_id.encode()).digest()


def chain_link(prev_chain: bytes, ev_hash: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + prev_chain + ev_hash).digest()


def _merkle_parent(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x02" + left + right).digest()


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        raise ValueError("a checkpoint needs at least one leaf")
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [_merkle_parent(level[i], level[i + 1])
                 for i in range(0, len(level), 2)]
    return level[0]


def merkle_proof(leaves: list[bytes], index: int) -> list[dict]:
    """Inclusion proof: sibling hashes from the leaf up to the root."""
    proof = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        if idx % 2 == 0:
            proof.append({"side": "R", "hash": level[idx + 1].hex()})
        else:
            proof.append({"side": "L", "hash": level[idx - 1].hex()})
        level = [_merkle_parent(level[i], level[i + 1])
                 for i in range(0, len(level), 2)]
        idx //= 2
    return proof


def proof_root(leaf: bytes, proof: list[dict]) -> bytes:
    node = leaf
    for step in proof:
        sib = bytes.fromhex(step["hash"])
        node = (_merkle_parent(sib, node) if step["side"] == "L"
                else _merkle_parent(node, sib))
    return node


def compute_batch(rows: list[dict], prev_chain: bytes, key: str | None):
    """Return (event_hashes, head_chain) for rows in seq order."""
    events = []
    chain = prev_chain
    for row in rows:
        ev = event_hash(row, key)
        events.append(ev)
        chain = chain_link(chain, ev)
    return events, chain
