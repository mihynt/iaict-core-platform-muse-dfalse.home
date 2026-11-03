"""Drift guard for the field registry (T-032, slice 2).

The registry in app/fields.py is the single source of truth; every
generated artefact must match a fresh render byte-for-byte, every
principal field must exist as a column in BOTH store schemas, and
every registry field declared for the API must exist on RecordIn.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "backend"))

import gen_fields  # noqa: E402
from app.fields import KINDS  # noqa: E402


def test_no_codegen_drift():
    numbers, changed = gen_fields.assign_numbers()
    assert not changed, "new fields lack pinned proto numbers - run tools/gen_fields.py"
    for path, content in gen_fields.outputs(numbers).items():
        assert path.exists(), f"missing generated file: {path}"
        assert path.read_text(encoding="utf-8") == content, \
            f"drift in {path.relative_to(ROOT)} - run tools/gen_fields.py"


def test_registry_columns_exist_in_both_schemas():
    ddl = (ROOT / "backend/app/schema_d1.sql").read_text()
    pg = (ROOT / "backend/app/schema.sql").read_text()
    for kind, meta in KINDS.items():
        table = meta["table"]
        for schema, name in ((ddl, "d1"), (pg, "pg")):
            m = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);",
                          schema, re.S)
            assert m, f"{name}: table {table} missing"
            body = m.group(1)
            for f in meta["fields"]:
                if "col" in f:
                    assert re.search(rf"^\s*{f['name']}\s", body, re.M), \
                        f"{name}: {table}.{f['name']} not a column"


def test_registry_api_fields_declared_on_recordin():
    tree = ast.parse((ROOT / "backend/app/production.py").read_text())
    declared = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "RecordIn":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    declared.add(stmt.target.id)
    for kind, meta in KINDS.items():
        for f in meta["fields"]:
            if "api" in f:
                assert f["name"] in declared, \
                    f"{kind}.{f['name']} declared in registry but not on RecordIn"
