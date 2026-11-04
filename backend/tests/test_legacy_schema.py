"""Regression: retired NOT NULL columns from earlier schema eras must not
block record creation (production incident 2026-11-04: zones.name, cut from
the field model in T-034, still had NOT NULL with no default on the live D1
zones table, so every zone create returned 500 while PATCH/GET stayed fine).
"""
import os
from pathlib import Path

from tests.conftest import bootstrap_admin, register_tenant

A = {"X-Tenant-Id": "acme", "X-Actor": "admin"}


def test_create_zone_with_code_only(client):
    register_tenant(client, "acme")
    bootstrap_admin(client, "acme")
    r = client.post("/api/v1/zones", headers=A, json={"code": "Z-MIN"})
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "Z-MIN"


def test_d1_store_guard_under_legacy_notnull_schema():
    """Store-level, fully isolated: a private D1Store over a database whose
    zones table carries the production-era `name TEXT NOT NULL` (no default).
    Zone creation must succeed via the legacy-schema guard."""
    if os.environ.get("TEST_BACKEND") != "d1":
        import pytest
        pytest.skip("legacy D1 schema simulation only runs in D1 mode")
    import asyncio

    from app.d1store import D1Store
    from tests.conftest import _LocalD1

    schema = Path(__file__).with_name("..").joinpath(
        "app", "schema_d1.sql").resolve().read_text()
    start = schema.index("CREATE TABLE IF NOT EXISTS zones")
    end = schema.index(");", start)
    block = schema[start:end]
    legacy_block = block.replace("name            TEXT,", "name            TEXT NOT NULL,")
    assert legacy_block != block, "schema drift: zones name line not found"
    legacy_schema = schema[:start] + legacy_block + schema[end:]

    db = _LocalD1()
    db._conn.executescript(legacy_schema)
    impl = D1Store(db)

    async def run():
        await impl.create_tenant("acme", "Acme")
        rec = await impl.create_record("acme", "zones", {"code": "Z-LEGACY"})
        assert rec is not None and rec["code"] == "Z-LEGACY"

    asyncio.run(run())
