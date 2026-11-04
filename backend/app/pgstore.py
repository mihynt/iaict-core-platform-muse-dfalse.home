"""PostgreSQL backend for the store boundary (M2, task T-004).

Selected by make_store() when DATABASE_URL is set. Standard SQL against
the schema in app/schema.sql; psycopg 3 driver. All access is
serialized through one connection + lock, mirroring the in-memory
backend's semantics at this scale; pooling is a deployment concern,
not a contract change.

Since T-044 (T-032 slice 4) the store contract itself lives in
app.sqlcore.SqlStoreCore; this module is only the psycopg dialect
adapter (placeholders, Jsonb, RETURNING, unique-violation type).
"""
from __future__ import annotations

import pathlib
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .sqlcore import SqlStoreCore

_SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


class PgDialect:
    ph = "%s"

    def __init__(self, conn, lock) -> None:
        self._conn = conn
        self._lock = lock

    async def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    async def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    async def run(self, sql: str, params: tuple = ()) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    async def insert(self, sql: str, params: tuple = (),
                     returning: str = "id") -> int | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"{sql} RETURNING {returning}", params)
            row = cur.fetchone()
            return None if row is None else row[returning]

    @staticmethod
    def json_in(obj):
        return Jsonb(obj)

    @staticmethod
    def is_unique(exc: BaseException) -> bool:
        return isinstance(exc, psycopg.errors.UniqueViolation)

    async def legacy_columns(self, table: str) -> list:
        rows = await self.all(
            "SELECT column_name AS name, data_type AS type"
            " FROM information_schema.columns"
            " WHERE table_name = %s AND is_nullable = 'NO'"
            " AND column_default IS NULL",
            (table,))
        system = {"id", "tenant_id", "code", "data", "created_at", "updated_at"}
        found = []
        for r in rows:
            if r["name"] not in system:
                t = (r["type"] or "").upper()
                neutral = 0 if any(x in t for x in
                                   ("INT", "REAL", "NUM", "DEC", "DOUBLE")) else ""
                found.append((r["name"], neutral))
        return found


class PgStore(SqlStoreCore):
    kind = "postgresql"

    def __init__(self, dsn: str) -> None:
        self._lock = threading.Lock()
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        with self._lock, self._conn.cursor() as cur:
            cur.execute(_SCHEMA)
        super().__init__(PgDialect(self._conn, self._lock))

    async def reset(self) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "TRUNCATE audit_log, lot_relations, field_events, lots, crop_plans,"
                " mother_plant_status_history, mother_plants, zone_boundary_versions,"
                " zones, workspaces, users, tenants RESTART IDENTITY CASCADE"
            )
