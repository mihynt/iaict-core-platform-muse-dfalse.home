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

from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User

_SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

# kind -> (table, {column: kind}) where column kinds: text | int | float |
# num (Decimal) | date | ts (timestamp) | json. Reference code fields are
# declared in store.RECORD_REFS and map to <stem>_id FK columns.
SPECS: dict[str, tuple[str, dict[str, str]]] = {
    "zones": ("zones", {
        "name": "text", "area_ha": "num", "address": "text", "lat": "float",
        "lon": "float", "geom": "json", "crop_group": "text", "season": "text",
        "water_source": "text", "managing_entity": "text", "status": "text",
    }),
    "mother_plants": ("mother_plants", {
        "species": "text", "variety": "text", "scientific_name": "text",
        "origin": "text", "planting_year": "int", "lat": "float", "lon": "float",
        "owner_manager": "text", "recognition_no": "text",
        "issuing_authority": "text", "valid_from": "date", "valid_to": "date",
        "status": "text",
    }),
    "crop_plans": ("crop_plans", {
        "name": "text", "crop_name": "text", "start_date": "date",
        "end_date": "date", "target_yield_kg": "num", "status": "text",
    }),
    "field_events": ("field_events", {
        "event_type": "text", "occurred_at": "ts", "lat": "float", "lon": "float",
        "actor": "text", "device": "text", "notes": "text", "materials": "json",
    }),
    "lots": ("lots", {
        "harvest_date": "date", "quantity": "num", "unit": "text",
        "harvested_by": "text", "quality_grade": "text", "status": "text",
        "expiry_date": "date",
    }),
}
REF_ID_COLUMN = {"zone_code": "zone_id", "plant_code": "plant_id", "plan_code": "plan_id"}


def _conv(value, kind: str):
    if value is None:
        return None
    if kind == "num" and isinstance(value, Decimal):
        return float(value)
    if kind in ("date", "ts") and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class PgStore:
    def __init__(self, dsn: str) -> None:
        self._lock = threading.Lock()
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        with self._lock, self._conn.cursor() as cur:
            cur.execute(_SCHEMA)

    def reset(self) -> None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "TRUNCATE audit_log, lot_relations, field_events, lots, crop_plans,"
                " mother_plant_status_history, mother_plants, zone_boundary_versions,"
                " zones, workspaces, users, tenants RESTART IDENTITY CASCADE"
            )

    # ---- audit ---------------------------------------------------------
    def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
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

    def list_audit(self) -> list[dict]:
        return self._audit_rows("", ())

    def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return self._audit_rows("WHERE tenant_id = %s", (tenant_id,))

    # ---- tenants -------------------------------------------------------
    def create_tenant(self, slug: str, name: str) -> Tenant | None:
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

    def get_tenant(self, slug: str) -> Tenant | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM tenants WHERE slug = %s", (slug,))
            row = cur.fetchone()
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"].isoformat())

    def list_tenants(self) -> list[Tenant]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM tenants ORDER BY slug")
            rows = cur.fetchall()
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=r["created_at"].isoformat()) for r in rows]

    def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
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
    def create_user(self, tenant: str, username: str, display_name: str, role: str) -> User | None:
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

    def get_user(self, tenant: str, username: str) -> User | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s AND username = %s",
                        (tenant, username))
            row = cur.fetchone()
        if row is None:
            return None
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=row["created_at"].isoformat())

    def list_users(self, tenant: str) -> list[User]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s ORDER BY username", (tenant,))
            rows = cur.fetchall()
        return [User(username=r["username"], display_name=r["display_name"], role=r["role"],
                     created_at=r["created_at"].isoformat()) for r in rows]

    def tenant_user_count(self, tenant: str) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,))
            return cur.fetchone()["n"]

    # ---- workspaces ------------------------------------------------------
    def create_workspace(self, tenant: str, name: str) -> bool:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workspaces (tenant_id, name) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (tenant, name),
            )
            return cur.rowcount == 1

    def list_workspace_names(self, tenant: str) -> list[str]:
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

    def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
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

    def list_records(self, tenant: str, kind: str) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s ORDER BY {order}",
                        (tenant,))
            return [self._row_to_record(r, kind) for r in cur.fetchall()]

    def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        with self._lock, self._conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                        (tenant, code))
            row = cur.fetchone()
        return None if row is None else self._row_to_record(row, kind)
