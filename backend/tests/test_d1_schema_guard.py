"""Regression guard for the 2026-11-03 T-017 incident: creating the M3
unique index inside _ensure_schema via self._run recursed into
_ensure_schema itself (which _run awaits), burning the Workers CPU
budget — every write path on the beta failed with 1102/500 while the
test suite stayed green (the recursion self-masked behind a try/except
and still produced the index on unwind).

This test counts binding prepare() calls during a cold-start store
operation: schema setup must be a small bounded number, never
proportional to the Python recursion limit. D1 mode only.
"""
import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_BACKEND") != "d1",
    reason="D1 schema-guard regression test only runs in d1 mode")


def test_schema_setup_is_bounded():
    from app.d1store import D1Store
    from tests.conftest import _LocalD1

    class CountingD1(_LocalD1):
        def __init__(self):
            super().__init__()
            self.prepares = 0

        def prepare(self, sql):
            self.prepares += 1
            return super().prepare(sql)

    async def run():
        db = CountingD1()
        store = D1Store(db)
        await store.list_records("nobody", "zones")
        # Fresh-DB path: ~25 DDL statements in one batch + probes + the
        # index statement + the list query itself. The recursion bug made
        # this thousands.
        assert db.prepares < 60, f"schema setup used {db.prepares} prepares"
        # Second call on the warm store: schema must not be re-checked.
        before = db.prepares
        await store.list_records("nobody", "zones")
        assert db.prepares - before <= 1

    asyncio.run(run())


def test_migration_ledger_stamped_on_fresh_db():
    """T-039: a fresh D1 database records every migration as applied."""
    from app.d1store import _MIGRATIONS, D1Store
    from tests.conftest import _LocalD1

    async def _probe():
        store = D1Store(_LocalD1())
        await store._ensure_schema()
        rows = await store._all("SELECT version FROM schema_migrations")
        return sorted(r["version"] for r in rows)

    versions = asyncio.run(_probe())
    assert versions == sorted(v for v, _ in _MIGRATIONS)
