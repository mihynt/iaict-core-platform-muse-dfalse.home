#!/usr/bin/env python3
"""Generate every artefact derived from the field registry.

Source of truth: backend/app/fields.py (Owner direction, T-032).
Outputs (all marked GENERATED - never edit by hand):
  backend/app/records_spec.py            SPECS + RECORD_REFS + REF_ID_COLUMN + conv
  deploy/cloudflare/public/fields.js     window.IAICT_META (labels, detailSpecs, enums)
  contracts/iaict.proto                  Protobuf contract (append-only field numbers)
  contracts/iaict.graphql                GraphQL SDL contract
  contracts/field_numbers.json           pinned proto field numbers

Usage: python3 tools/gen_fields.py [--check]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.fields import ENUMS, EXTRA_LABELS, KINDS  # noqa: E402

GEN_NOTE = "GENERATED from backend/app/fields.py by tools/gen_fields.py - do not edit by hand."

CONV_BLOCK = '''

def conv(value, kind: str):
    """Normalize a database value into the API record shape."""
    if value is None:
        return None
    if kind == "num" and isinstance(value, Decimal):
        return float(value)
    if kind in ("date", "ts") and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
'''


def _specs():
    out = {}
    for kind, meta in KINDS.items():
        cols = {f["name"]: f["col"] for f in meta["fields"] if "col" in f}
        out[kind] = (meta["table"], cols)
    return out


def _refs():
    out = {}
    for kind, meta in KINDS.items():
        refs = {f["name"]: f["ref"] for f in meta["fields"] if "ref" in f}
        out[kind] = refs
    return out


def _ref_ids():
    out = {}
    for meta in KINDS.values():
        for f in meta["fields"]:
            if "ref_id" in f:
                prev = out.setdefault(f["name"], f["ref_id"])
                assert prev == f["ref_id"], f"ref_id conflict for {f['name']}"
    return out


def render_records_spec() -> str:
    import pprint
    head = f'''"""{GEN_NOTE}

Principal-column specifications for the production record kinds.
Fields not listed as columns are stored in the `data` payload
(see docs/DATA_MODEL.md). Reference resolution uses RECORD_REFS;
the SQL stores write the matching FK column from REF_ID_COLUMN.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

'''
    body = "SPECS = " + pprint.pformat(_specs(), width=100, sort_dicts=False) + "\n\n"
    body += "RECORD_REFS = " + pprint.pformat(_refs(), width=100, sort_dicts=False) + "\n\n"
    body += "REF_ID_COLUMN = " + pprint.pformat(_ref_ids(), width=100, sort_dicts=False) + "\n"
    return head + body + CONV_BLOCK


def render_fields_js() -> str:
    labels = {}
    for meta in KINDS.values():
        for f in meta["fields"]:
            if "label" in f:
                labels[f["name"]] = f["label"]
    labels.update(EXTRA_LABELS)
    detail = {k: m["detail"] for k, m in KINDS.items() if m.get("detail")}
    meta = {"labels": labels, "detailSpecs": detail, "enums": ENUMS}
    return ("// " + GEN_NOTE + "\n"
            "window.IAICT_META = " + json.dumps(meta, ensure_ascii=False, indent=1) + ";\n")


NUMBERS_PATH = ROOT / "contracts" / "field_numbers.json"


def load_numbers() -> dict:
    if NUMBERS_PATH.exists():
        return json.loads(NUMBERS_PATH.read_text(encoding="utf-8"))
    return {}


def assign_numbers() -> tuple[dict, bool]:
    numbers = load_numbers()
    changed = False
    for kind, meta in KINDS.items():
        book = numbers.setdefault(kind, {})
        used = set(book.values())
        nxt = max(used, default=0) + 1
        for f in meta["fields"]:
            if f["name"] not in book:
                while nxt in used:
                    nxt += 1
                book[f["name"]] = nxt
                used.add(nxt)
                changed = True
    return numbers, changed


def _proto_type(f) -> str:
    col = f.get("col")
    if col == "num":
        return "double"
    if col == "bool":
        return "bool"
    api = f.get("api", "")
    if "int" in api and "str" not in api:
        return "int64"
    if "float" in api:
        return "double"
    if api.startswith("bool"):
        return "bool"
    return "string"


def _pascal(kind: str) -> str:
    singular = kind[:-1] if kind.endswith("s") else kind
    return "".join(part.capitalize() for part in singular.split("_"))


def render_proto(numbers: dict) -> str:
    lines = ["// " + GEN_NOTE, 'syntax = "proto3";', "",
             "package iaict.core.v1;", "",
             "// Field numbers are append-only and never reused",
             "// (pinned in contracts/field_numbers.json).", ""]
    for kind, meta in KINDS.items():
        lines.append(f"message {_pascal(kind)} {{")
        for f in meta["fields"]:
            n = numbers[kind][f["name"]]
            comment = f"  // {f['label']}" if "label" in f else ""
            lines.append(f"  {_proto_type(f)} {f['name']} = {n};{comment}")
        lines += ["}", ""]
    return "\n".join(lines)


def _gql_type(f) -> str:
    t = _proto_type(f)
    return {"double": "Float", "int64": "Int", "bool": "Boolean"}.get(t, "String")


def render_graphql() -> str:
    lines = ["# " + GEN_NOTE, "",
             "# Generated contract surface. A future GraphQL gateway or",
             "# service split consumes this SDL; it is not served yet.", ""]
    for kind, meta in KINDS.items():
        lines.append(f"type {_pascal(kind)} {{")
        lines.append("  id: ID")
        for f in meta["fields"]:
            if f["name"] == "id":
                continue
            lines.append(f"  {f['name']}: {_gql_type(f)}")
        lines += ["}", ""]
    lines.append("type Query {")
    for kind in KINDS:
        lines.append(f"  {kind}: [{_pascal(kind)}!]!")
    lines.append("}")
    return "\n".join(lines) + "\n"


def outputs(numbers: dict) -> dict[Path, str]:
    return {
        ROOT / "backend/app/records_spec.py": render_records_spec(),
        ROOT / "deploy/cloudflare/public/fields.js": render_fields_js(),
        ROOT / "contracts/iaict.proto": render_proto(numbers),
        ROOT / "contracts/iaict.graphql": render_graphql(),
        NUMBERS_PATH: json.dumps(numbers, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
    }


def main() -> int:
    check = "--check" in sys.argv
    numbers, numbers_changed = assign_numbers()
    drift = []
    for path, content in outputs(numbers).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            drift.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(content, encoding="utf-8")
    if check and drift:
        print("DRIFT in:", ", ".join(drift))
        return 1
    print(("checked, no drift" if check else "generated:") ,
          ", ".join(str(p.relative_to(ROOT)) for p in outputs(numbers)))
    if numbers_changed and not check:
        print("note: new proto field numbers were assigned (append-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
