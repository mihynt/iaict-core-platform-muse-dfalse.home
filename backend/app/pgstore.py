"""PostgreSQL backend for the store boundary (M2, task T-004).

Selected by make_store() when DATABASE_URL is set. Standard SQL against the
schema in app/schema.sql; psycopg 3 driver. All access is serialized through
one connection + lock, mirroring the in-memory backend's semantics at this
scale; pooling is a deployment concern, not a contract change.
"""
from __future__ import annotations

import pathlib
import threading
from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .records_spec import REF_ID_COLUMN, SPECS, conv as _conv
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User

_SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

class PgStore:
    kind = "postgresql"

    def __init__(self, dsn: str) -> None:
        self._lock = threading.Lock()
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        with self._lock, self._conn.cursor() as cur:
            cur.execute(_SCHEMA)

    async def reset(self) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "TRUNCATE audit_log, lot_relations, field_events, lots, crop_plans,"
                " mother_plant_status_history, mother_plants, zone_boundary_versions,"
                " zones, workspaces, users, tenants RESTART IDENTITY CASCADE"
            )

    # ---- audit ---------------------------------------------------------
    async def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                     action: str, target: str, outcome: str) -> dict:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (scope, tenant_id, actor, action, target, outcome)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING seq, ts",
                (scope, tenant_id, actor, action, target, outcome),
            )
            row = cur.fetchone()
        return {"seq": row["seq"], "ts": row["ts"].isoformat(), "scope": scope,
                "tenant_id": tenant_id, "actor": actor, "action": action,
                "target": target, "outcome": outcome}

    def _audit_rows(self, where: str, params: tuple) -> list[dict]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT * FROM audit_log {where} ORDER BY seq", params)
            rows = cur.fetchall()
        return [{**r, "ts": r["ts"].isoformat()} for r in rows]

    async def list_audit(self) -> list[dict]:
        return self._audit_rows("", ())

    async def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return self._audit_rows("WHERE tenant_id = %s", (tenant_id,))

    # ---- tenants -------------------------------------------------------
    async def create_tenant(self, slug: str, name: str) -> Tenant | None:
        with self._lock, self._conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO tenants (slug, name) VALUES (%s, %s) RETURNING created_at",
                    (slug, name),
                )
                created = cur.fetchone()["created_at"]
            except psycopg.errors.UniqueViolation:
                return None
        return Tenant(slug=slug, name=name, created_at=created.isoformat())

    async def get_tenant(self, slug: str) -> Tenant | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM tenants WHERE slug = %s", (slug,))
            row = cur.fetchone()
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"].isoformat())

    async def list_tenants(self) -> list[Tenant]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM tenants ORDER BY slug")
            rows = cur.fetchall()
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=r["created_at"].isoformat()) for r in rows]

    async def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "UPDATE tenants SET status = %s WHERE slug = %s RETURNING *", (status, slug)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"].isoformat())

    # ---- users ---------------------------------------------------------
    async def create_user(self, tenant: str, username: str, display_name: str, role: str) -> User | None:
        with self._lock, self._conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO users (tenant_id, username, display_name, role)"
                    " VALUES (%s, %s, %s, %s) RETURNING created_at",
                    (tenant, username, display_name, role),
                )
                created = cur.fetchone()["created_at"]
            except psycopg.errors.UniqueViolation:
                return None
        return User(username=username, display_name=display_name, role=role,
                    created_at=created.isoformat())

    async def get_user(self, tenant: str, username: str) -> User | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s AND username = %s",
                        (tenant, username))
            row = cur.fetchone()
        if row is None:
            return None
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=row["created_at"].isoformat())

    async def list_users(self, tenant: str) -> list[User]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s ORDER BY username", (tenant,))
            rows = cur.fetchall()
        return [User(username=r["username"], display_name=r["display_name"], role=r["role"],
                     created_at=r["created_at"].isoformat()) for r in rows]

    async def tenant_user_count(self, tenant: str) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,))
            return cur.fetchone()["n"]

    # ---- workspaces ------------------------------------------------------
    async def create_workspace(self, tenant: str, name: str) -> bool:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workspaces (tenant_id, name) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (tenant, name),
            )
            return cur.rowcount == 1

    async def list_workspace_names(self, tenant: str) -> list[str]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT name FROM workspaces WHERE tenant_id = %s ORDER BY name",
                        (tenant,))
            return [r["name"] for r in cur.fetchall()]

    # ---- production records ---------------------------------------------
    def _resolve_ref(self, cur, tenant: str, ref_kind: str, code: str) -> int | None:
        table = SPECS[ref_kind][0]
        cur.execute(f"SELECT id FROM {table} WHERE tenant_id = %s AND code = %s",
                    (tenant, code))
        row = cur.fetchone()
        return None if row is None else row["id"]

    async def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        with self._lock, self._conn.cursor() as cur:
            values: dict[str, object] = {}
            for ref_field, ref_kind in refs.items():
                code = fields.get(ref_field)
                if code is not None:
                    ref_id = self._resolve_ref(cur, tenant, ref_kind, code)
                    if ref_id is None:
                        raise RefUnknown(ref_field)
                    values[REF_ID_COLUMN[ref_field]] = ref_id
                    values[ref_field] = code
            known = set(columns) | set(refs)
            extra = {k: v for k, v in fields.items() if k not in known and k != "code"}
            for col, ckind in columns.items():
                if col in fields:
                    values[col] = Jsonb(fields[col]) if ckind == "json" else fields[col]
            names = ["tenant_id", "data", *values.keys()]
            params = [tenant, Jsonb(extra), *values.values()]
            if kind in CODED_KINDS:
                names.insert(1, "code")
                params.insert(1, fields.get("code"))
            placeholders = ", ".join(["%s"] * len(names))
            try:
                cur.execute(
                    f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})"
                    " RETURNING id",
                    params,
                )
                new_id = cur.fetchone()["id"]
            except psycopg.errors.UniqueViolation:
                return None
            cur.execute(f"SELECT * FROM {table} WHERE id = %s", (new_id,))
            return self._row_to_record(cur.fetchone(), kind)

    def _row_to_record(self, row: dict, kind: str) -> dict:
        _, columns = SPECS[kind]
        record: dict = {"id": row["id"], "tenant_id": row["tenant_id"]}
        if kind in CODED_KINDS:
            record["code"] = row["code"]
        for col, ckind in columns.items():
            if row.get(col) is not None:
                record[col] = _conv(row[col], ckind)
        for ref_field in RECORD_REFS[kind]:
            if row.get(ref_field) is not None:
                record[ref_field] = row[ref_field]
        record.update(row.get("data") or {})
        record["created_at"] = row["created_at"].isoformat()
        if "updated_at" in row and row["updated_at"] is not None:
            record["updated_at"] = row["updated_at"].isoformat()
        return record

    async def list_records(self, tenant: str, kind: str) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s ORDER BY {order}",
                        (tenant,))
            return [self._row_to_record(r, kind) for r in cur.fetchall()]

    async def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                        (tenant, code))
            row = cur.fetchone()
        return None if row is None else self._row_to_record(row, kind)
