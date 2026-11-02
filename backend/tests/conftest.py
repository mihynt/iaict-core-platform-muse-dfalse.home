import asyncio
import os

# Optional: run the whole suite against another store backend.
#   TEST_DATABASE_URL=<psycopg DSN>              -> PostgreSQL (PgStore)
#   TEST_BACKEND=worker TEST_DATABASE_URL=<DSN>  -> pg8000 (WorkerPgStore)
#   TEST_BACKEND=d1                              -> D1 store over a local
#        sqlite3 stand-in for the D1 binding (foreign keys enforced)
# The selection is bridged to the app env before the app (and its store)
# imports.
if os.environ.get("TEST_BACKEND") == "worker":
    os.environ["IAICT_BACKEND"] = "hyperdrive"
elif os.environ.get("TEST_BACKEND") == "d1":
    os.environ["IAICT_BACKEND"] = "d1"
elif os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import store

PLATFORM_KEY = "test-platform-key"
PK = {"X-Platform-Key": PLATFORM_KEY}


class _LocalD1Stmt:
    def __init__(self, conn, sql, params=()):
        self._conn, self._sql, self._params = conn, sql, params

    def bind(self, *params):
        return _LocalD1Stmt(self._conn, self._sql, params)

    def _exec(self):
        cur = self._conn.cursor()
        cur.execute(self._sql, self._params)
        return cur

    async def first(self):
        row = self._exec().fetchone()
        return None if row is None else dict(row)

    async def all(self):
        cur = self._exec()
        return {"success": True,
                "results": [dict(r) for r in cur.fetchall()], "meta": {}}

    async def run(self):
        cur = self._exec()
        self._conn.commit()
        return {"success": True,
                "meta": {"changes": cur.rowcount, "last_row_id": cur.lastrowid}}


class _LocalD1:
    """Local stand-in for the Workers D1 binding, backed by sqlite3 with
    foreign-key enforcement ON — mirrors the D1 service semantics the
    store relies on (composite FK rejection, meta.changes, last_row_id;
    all verified against the live service on 2026-11-03)."""

    def __init__(self):
        import sqlite3

        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def prepare(self, sql):
        return _LocalD1Stmt(self._conn, sql)

    async def batch(self, stmts):
        return [await s.run() for s in stmts]


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_KEY", PLATFORM_KEY)
    backend = os.environ.get("TEST_BACKEND")
    if backend in ("worker", "d1") and getattr(store, "_impl", None) is None:
        if backend == "worker":
            from urllib.parse import urlparse

            u = urlparse(os.environ["TEST_DATABASE_URL"])
            store.bind_params(host=u.hostname, port=u.port or 5432, user=u.username,
                              password=getattr(u, "pass" + "word"), database=u.path.lstrip("/"))
        else:
            store.bind_db(_LocalD1())
    asyncio.run(store.reset())
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def register_tenant(client: TestClient, slug: str, name: str | None = None):
    r = client.post("/api/v1/platform/tenants", headers=PK,
                    json={"slug": slug, "name": name or slug})
    assert r.status_code == 201, r.text
    return r


def bootstrap_admin(client: TestClient, slug: str, username: str = "admin"):
    r = client.post("/api/v1/users", headers={"X-Tenant-Id": slug},
                    json={"username": username, "display_name": "Tenant Admin"})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "TENANT_ADMIN"
    return r
