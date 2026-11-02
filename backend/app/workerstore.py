"""PostgreSQL backend for serverless Workers, via Hyperdrive (M2, T-004).

Same store contract as app.pgstore, but with the pure-Python pg8000 driver:
it is the driver Cloudflare supports for PostgreSQL in Python Workers,
where the Hyperdrive binding provides the connection fields and Hyperdrive
itself terminates TLS and pools connections to the database (Neon).
Standard SQL only (app/schema.sql), so this backend and the psycopg one are
interchangeable; the entrypoint chooses (see app.store.make_store).

Connection policy: a fresh pg8000 connection per store operation, closed
when the operation ends — the pattern Cloudflare prescribes for Hyperdrive
(it maintains the real pool upstream). A cached per-isolate connection was
observed to fail transiently on the live beta after isolate reuse
(one 500 amid otherwise successful durable flows on 2026-11-02).
"""
from __future__ import annotations

import json
import pathlib
import threading
from contextlib import contextmanager

import pg8000

from .records_spec import REF_ID_COLUMN, SPECS, conv as _conv
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User

_SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def _is_unique_violation(exc: BaseException) -> bool:
    return bool(exc.args and isinstance(exc.args[0], dict)
                and exc.args[0].get("C") == "23505")


class WorkerPgStore:
    kind = "postgresql-hyperdrive"

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str) -> None:
        self._lock = threading.Lock()
        self._params = dict(host=host, port=int(port), user=user,
                            password=password, database=database)
        self._schema_done = False

    @contextmanager
    def _session(self):
        """One short-lived connection per operation (see module docstring).
        Applies the schema once per store instance, on first use."""
        conn = pg8000.connect(**self._params, timeout=30)
        conn.autocommit = True
        try:
            if not self._schema_done:
                cur = conn.cursor()
                for stmt in _SCHEMA.split(";\n"):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
                self._schema_done = True
            yield conn.cursor()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @classmethod
    def from_binding(cls, binding) -> "WorkerPgStore":
        """Build from a Hyperdrive binding object (host/port/user/password/
        database attributes), as exposed in the Workers request env."""
        return cls(host=binding.host, port=int(binding.port), user=binding.user,
                   password=binding.password, database=binding.database)

    @staticmethod
    def _rows(cur) -> list[dict]:
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

    def _one(self, cur) -> dict | None:
        rows = self._rows(cur)
        return rows[0] if rows else None

    def reset(self) -> None:
        with self._lock, self._session() as cur:
            cur.execute(
                "TRUNCATE audit_log, lot_relations, field_events, lots, crop_plans,"
                " mother_plant_status_history, mother_plants, zone_boundary_versions,"
                " zones, workspaces, users, tenants RESTART IDENTITY CASCADE"
            )

    # ---- audit ---------------------------------------------------------
    def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                     action: str, target: str, outcome: str) -> dict:
        with self._lock, self._session() as cur:
            cur.execute(
                "INSERT INTO audit_log (scope, tenant_id, actor, action, target, outcome)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING seq, ts",
                (scope, tenant_id, actor, action, target, outcome),
            )
            row = self._one(cur)
        return {"seq": row["seq"], "ts": row["ts"].isoformat(), "scope": scope,
                "tenant_id": tenant_id, "actor": actor, "action": action,
                "target": target, "outcome": outcome}

    def _audit_rows(self, where: str, params: tuple) -> list[dict]:
        with self._lock, self._session() as cur:
            cur.execute(f"SELECT * FROM audit_log {where} ORDER BY seq", params)
            rows = self._rows(cur)
        return [{**r, "ts": r["ts"].isoformat()} for r in rows]

    def list_audit(self) -> list[dict]:
        return self._audit_rows("", ())

    def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return self._audit_rows("WHERE tenant_id = %s", (tenant_id,))

    # ---- tenants -------------------------------------------------------
    def create_tenant(self, slug: str, name: str) -> Tenant | None:
        with self._lock, self._session() as cur:
            try:
                cur.execute(
                    "INSERT INTO tenants (slug, name) VALUES (%s, %s) RETURNING created_at",
                    (slug, name),
                )
                created = self._one(cur)["created_at"]
            except Exception as exc:
                if _is_unique_violation(exc):
                    return None
                raise
        return Tenant(slug=slug, name=name, created_at=created.isoformat())

    def get_tenant(self, slug: str) -> Tenant | None:
        with self._lock, self._session() as cur:
            cur.execute("SELECT * FROM tenants WHERE slug = %s", (slug,))
            row = self._one(cur)
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"].isoformat())

    def list_tenants(self) -> list[Tenant]:
        with self._lock, self._session() as cur:
            cur.execute("SELECT * FROM tenants ORDER BY slug")
            rows = self._rows(cur)
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=r["created_at"].isoformat()) for r in rows]

    def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        with self._lock, self._session() as cur:
            cur.execute(
                "UPDATE tenants SET status = %s WHERE slug = %s RETURNING *", (status, slug)
            )
            row = self._one(cur)
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"].isoformat())

    # ---- users ---------------------------------------------------------
    def create_user(self, tenant: str, username: str, display_name: str, role: str) -> User | None:
        with self._lock, self._session() as cur:
            try:
                cur.execute(
                    "INSERT INTO users (tenant_id, username, display_name, role)"
                    " VALUES (%s, %s, %s, %s) RETURNING created_at",
                    (tenant, username, display_name, role),
                )
                created = self._one(cur)["created_at"]
            except Exception as exc:
                if _is_unique_violation(exc):
                    return None
                raise
        return User(username=username, display_name=display_name, role=role,
                    created_at=created.isoformat())

    def get_user(self, tenant: str, username: str) -> User | None:
        with self._lock, self._session() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s AND username = %s",
                        (tenant, username))
            row = self._one(cur)
        if row is None:
            return None
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=row["created_at"].isoformat())

    def list_users(self, tenant: str) -> list[User]:
        with self._lock, self._session() as cur:
            cur.execute("SELECT * FROM users WHERE tenant_id = %s ORDER BY username", (tenant,))
            rows = self._rows(cur)
        return [User(username=r["username"], display_name=r["display_name"], role=r["role"],
                     created_at=r["created_at"].isoformat()) for r in rows]

    def tenant_user_count(self, tenant: str) -> int:
        with self._lock, self._session() as cur:
            cur.execute("SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,))
            return self._one(cur)["n"]

    # ---- workspaces ------------------------------------------------------
    def create_workspace(self, tenant: str, name: str) -> bool:
        with self._lock, self._session() as cur:
            cur.execute(
                "INSERT INTO workspaces (tenant_id, name) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (tenant, name),
            )
            return cur.rowcount == 1

    def list_workspace_names(self, tenant: str) -> list[str]:
        with self._lock, self._session() as cur:
            cur.execute("SELECT name FROM workspaces WHERE tenant_id = %s ORDER BY name",
                        (tenant,))
            return [r["name"] for r in self._rows(cur)]

    # ---- production records ---------------------------------------------
    def _resolve_ref(self, cur, tenant: str, ref_kind: str, code: str) -> int | None:
        table = SPECS[ref_kind][0]
        cur.execute(f"SELECT id FROM {table} WHERE tenant_id = %s AND code = %s",
                    (tenant, code))
        row = self._one(cur)
        return None if row is None else row["id"]

    def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        with self._lock, self._session() as cur:
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
                    values[col] = json.dumps(fields[col]) if ckind == "json" else fields[col]
            names = ["tenant_id", "data", *values.keys()]
            params = [tenant, json.dumps(extra), *values.values()]
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
                new_id = self._one(cur)["id"]
            except Exception as exc:
                if _is_unique_violation(exc):
                    return None
                raise
            cur.execute(f"SELECT * FROM {table} WHERE id = %s", (new_id,))
            return self._row_to_record(self._one(cur), kind)

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
        data = row.get("data") or {}
        record.update(data if isinstance(data, dict) else json.loads(data))
        record["created_at"] = row["created_at"].isoformat()
        if "updated_at" in row and row["updated_at"] is not None:
            record["updated_at"] = row["updated_at"].isoformat()
        return record

    def list_records(self, tenant: str, kind: str) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"
        with self._lock, self._session() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s ORDER BY {order}",
                        (tenant,))
            return [self._row_to_record(r, kind) for r in self._rows(cur)]

    def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        with self._lock, self._session() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                        (tenant, code))
            row = self._one(cur)
        return None if row is None else self._row_to_record(row, kind)
