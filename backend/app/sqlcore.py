"""Dialect-unified SQL store core (T-044, T-032 slice 4).

The store boundary used to carry three near-identical record engines
(PgStore, WorkerPgStore, D1Store). This module is now the ONE
implementation of the shared store contract — audit, tenants, users,
workspaces and all production-record operations — written once against
a small dialect interface:

    ph                  SQL placeholder ("?" for SQLite/D1, "%s" for PG)
    one(sql, params)    first row as dict, or None
    all(sql, params)    every row as dicts
    run(sql, params)    affected-row count
    insert(sql, params, returning)
                        new row id (RETURNING on PG, last_row_id on D1)
    json_in(obj)        bindable value for JSON payloads (Jsonb / text)
    is_unique(exc)      unique-violation detection for the driver
    legacy_columns(t)   NOT-NULL-without-default columns outside the
                        standard write set (the T-036 legacy guard)

PgStore (psycopg, the documented exit path) and D1Store (the live
beta backend) are thin dialect adapters over this core. Timestamps are
written explicitly (utcnow) on both dialects; PostgreSQL columns that
used to rely on DEFAULT now() accept the same values.

WorkerPgStore deliberately does NOT sit on this core: its operations
are transactional units (one explicit transaction per operation with
rollback-and-drop on failure, optimistic retry-once reads, per-isolate
lookup caches) because Hyperdrive pins upstream sessions at
transaction boundaries (see its module docstring, SQLSTATE 26000).
That execution model cannot be decomposed into per-statement dialect
calls without changing its failure semantics, so it remains a separate
implementation of the same contract on the legacy Hyperdrive path.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from .records_spec import REF_ID_COLUMN, SPECS
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User, utcnow


def _ts(value) -> str:
    """Normalize a timestamp-ish value to the API's string shape."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def conv_out(value, ckind: str):
    """Normalize a database value into the API record shape (one
    implementation for both dialects: JSON text on SQLite, native
    objects on PostgreSQL)."""
    if value is None:
        return None
    if ckind == "json" and isinstance(value, str):
        return json.loads(value)
    if ckind == "num" and isinstance(value, (int, float, Decimal)) \
            and not isinstance(value, bool):
        return float(value)
    if ckind in ("date", "ts") and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class SqlStoreCore:
    """The shared store contract over a dialect adapter (`self.d`)."""

    def __init__(self, dialect) -> None:
        self.d = dialect
        self._legacy_cache: dict[str, list] = {}

    # ---- dialect helpers -------------------------------------------------
    async def _legacy_required_columns(self, table: str) -> list:
        if table not in self._legacy_cache:
            self._legacy_cache[table] = await self.d.legacy_columns(table)
        return self._legacy_cache[table]

    def _conv_in(self, value, ckind: str):
        if value is None:
            return None
        if ckind == "json":
            return self.d.json_in(value)
        return value

    def _data_in(self, extra: dict):
        return self.d.json_in(extra)

    @staticmethod
    def _data_out(raw) -> dict:
        if raw is None:
            return {}
        if isinstance(raw, dict):
            return raw
        return json.loads(raw) if raw else {}

    # ---- audit -----------------------------------------------------------
    async def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                           action: str, target: str, outcome: str,
                           old_value: str | None = None,
                           new_value: str | None = None) -> dict:
        from . import auditctx
        ph = self.d.ph
        ts = utcnow()
        seq = await self.d.insert(
            "INSERT INTO audit_log (ts, scope, tenant_id, actor, action, target,"
            f" outcome, old_value, new_value, client_ip, user_agent)"
            f" VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (ts, scope, tenant_id, actor, action, target, outcome,
             old_value, new_value, auditctx.client_ip(), auditctx.user_agent()),
            returning="seq",
        )
        return {"seq": seq, "ts": ts, "scope": scope, "tenant_id": tenant_id,
                "actor": actor, "action": action, "target": target,
                "outcome": outcome, "old_value": old_value,
                "new_value": new_value, "client_ip": auditctx.client_ip(),
                "user_agent": auditctx.user_agent()}

    async def _audit_rows(self, where: str, params: tuple) -> list[dict]:
        rows = await self.d.all(f"SELECT * FROM audit_log {where} ORDER BY seq", params)
        return [{**r, "ts": _ts(r["ts"])} for r in rows]

    async def list_audit(self) -> list[dict]:
        return await self._audit_rows("", ())

    async def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return await self._audit_rows(f"WHERE tenant_id = {self.d.ph}", (tenant_id,))

    # ---- tenants -----------------------------------------------------------
    async def create_tenant(self, slug: str, name: str) -> Tenant | None:
        ph = self.d.ph
        created = utcnow()
        try:
            await self.d.run(
                f"INSERT INTO tenants (slug, name, status, created_at)"
                f" VALUES ({ph}, {ph}, 'ACTIVE', {ph})",
                (slug, name, created),
            )
        except Exception as exc:
            if self.d.is_unique(exc):
                return None
            raise
        return Tenant(slug=slug, name=name, created_at=created)

    async def get_tenant(self, slug: str) -> Tenant | None:
        row = await self.d.one(
            f"SELECT * FROM tenants WHERE slug = {self.d.ph}", (slug,))
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=_ts(row["created_at"]))

    async def list_tenants(self) -> list[Tenant]:
        rows = await self.d.all("SELECT * FROM tenants ORDER BY slug")
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=_ts(r["created_at"])) for r in rows]

    async def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        ph = self.d.ph
        changes = await self.d.run(
            f"UPDATE tenants SET status = {ph} WHERE slug = {ph}", (status, slug))
        if not changes:
            return None
        return await self.get_tenant(slug)

    # ---- users -------------------------------------------------------------
    async def create_user(self, tenant: str, username: str, display_name: str,
                          role: str, linked_actor_code: str | None = None,
                          jurisdiction_admin_code: str | None = None,
                          auth_provider_type: str | None = None) -> User | None:
        ph = self.d.ph
        created = utcnow()
        try:
            await self.d.run(
                "INSERT INTO users (tenant_id, username, display_name, role,"
                " created_at, linked_actor_code, account_status,"
                f" jurisdiction_admin_code, auth_provider_type)"
                f" VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'ACTIVE', {ph}, {ph})",
                (tenant, username, display_name, role, created,
                 linked_actor_code, jurisdiction_admin_code, auth_provider_type),
            )
        except Exception as exc:
            if self.d.is_unique(exc):
                return None
            raise
        return User(username=username, display_name=display_name, role=role,
                    created_at=created, linked_actor_code=linked_actor_code,
                    jurisdiction_admin_code=jurisdiction_admin_code,
                    auth_provider_type=auth_provider_type)

    @staticmethod
    def _to_user(row: dict) -> User:
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=_ts(row["created_at"]),
                    linked_actor_code=row.get("linked_actor_code"),
                    account_status=row.get("account_status") or "ACTIVE",
                    jurisdiction_admin_code=row.get("jurisdiction_admin_code"),
                    auth_provider_type=row.get("auth_provider_type"))

    async def update_user(self, tenant: str, username: str, fields: dict) -> User | None:
        allowed = ("display_name", "role", "linked_actor_code", "account_status",
                   "jurisdiction_admin_code", "auth_provider_type")
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if await self.get_user(tenant, username) is None:
            return None
        if sets:
            ph = self.d.ph
            assignments = ", ".join(f"{k} = {ph}" for k in sets)
            await self.d.run(
                f"UPDATE users SET {assignments}"
                f" WHERE tenant_id = {ph} AND username = {ph}",
                tuple(sets.values()) + (tenant, username))
        return await self.get_user(tenant, username)

    async def get_user(self, tenant: str, username: str) -> User | None:
        ph = self.d.ph
        row = await self.d.one(
            f"SELECT * FROM users WHERE tenant_id = {ph} AND username = {ph}",
            (tenant, username))
        return None if row is None else self._to_user(row)

    async def list_users(self, tenant: str) -> list[User]:
        rows = await self.d.all(
            f"SELECT * FROM users WHERE tenant_id = {self.d.ph} ORDER BY username",
            (tenant,))
        return [self._to_user(r) for r in rows]

    async def tenant_user_count(self, tenant: str) -> int:
        row = await self.d.one(
            f"SELECT count(*) AS n FROM users WHERE tenant_id = {self.d.ph}",
            (tenant,))
        return int(row["n"]) if row else 0

    # ---- workspaces ----------------------------------------------------------
    async def create_workspace(self, tenant: str, name: str) -> bool:
        ph = self.d.ph
        changes = await self.d.run(
            f"INSERT INTO workspaces (tenant_id, name, created_at)"
            f" VALUES ({ph}, {ph}, {ph}) ON CONFLICT DO NOTHING",
            (tenant, name, utcnow()))
        return changes == 1

    async def list_workspace_names(self, tenant: str) -> list[str]:
        rows = await self.d.all(
            f"SELECT name FROM workspaces WHERE tenant_id = {self.d.ph} ORDER BY name",
            (tenant,))
        return [r["name"] for r in rows]

    # ---- production records --------------------------------------------------
    async def _resolve_ref(self, tenant: str, ref_kind: str, code: str) -> int | None:
        table = SPECS[ref_kind][0]
        ph = self.d.ph
        row = await self.d.one(
            f"SELECT id FROM {table} WHERE tenant_id = {ph} AND code = {ph}",
            (tenant, code))
        return None if row is None else row["id"]

    async def _values_for(self, tenant: str, kind: str, fields: dict) -> dict:
        """Resolve references and split principal columns for a write."""
        _, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        values: dict[str, object] = {}
        for ref_field, ref_kind in refs.items():
            code = fields.get(ref_field)
            if code is not None:
                ref_id = await self._resolve_ref(tenant, ref_kind, code)
                if ref_id is None:
                    raise RefUnknown(ref_field)
                values[REF_ID_COLUMN[ref_field]] = ref_id
                values[ref_field] = code
        for col, ckind in columns.items():
            if col in fields:
                values[col] = self._conv_in(fields[col], ckind)
        return values

    @staticmethod
    def _extra_of(kind: str, fields: dict) -> dict:
        _, columns = SPECS[kind]
        known = set(columns) | set(RECORD_REFS[kind])
        return {k: v for k, v in fields.items() if k not in known and k != "code"}

    async def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        table, _ = SPECS[kind]
        ph = self.d.ph
        values = await self._values_for(tenant, kind, fields)
        extra = self._extra_of(kind, fields)
        now = utcnow()
        names = ["tenant_id", "data", "created_at"]
        params: list = [tenant, self._data_in(extra), now]
        if kind != "field_events":  # the one table without updated_at
            names.append("updated_at")
            params.append(now)
        names += list(values.keys())
        params += list(values.values())
        if kind in CODED_KINDS:
            names.insert(1, "code")
            params.insert(1, fields.get("code"))
        # Legacy-schema guard (T-036): a table from an earlier schema era
        # can carry NOT NULL columns with no default that the current
        # field model retired; satisfy them with a neutral value instead
        # of failing the insert (reads are SPECS-driven, never surface it).
        for col, neutral in await self._legacy_required_columns(table):
            if col not in names:
                names.append(col)
                params.append(neutral)
        placeholders = ", ".join([ph] * len(names))
        try:
            new_id = await self.d.insert(
                f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})",
                tuple(params), returning="id")
        except Exception as exc:
            if self.d.is_unique(exc):
                return None
            raise
        row = await self.d.one(f"SELECT * FROM {table} WHERE id = {ph}", (new_id,))
        return self._row_to_record(row, kind)

    def _row_to_record(self, row: dict, kind: str) -> dict:
        _, columns = SPECS[kind]
        record: dict = {"id": row["id"], "tenant_id": row["tenant_id"]}
        if kind in CODED_KINDS:
            record["code"] = row["code"]
        for col, ckind in columns.items():
            if row.get(col) is not None:
                record[col] = conv_out(row[col], ckind)
        for ref_field in RECORD_REFS[kind]:
            if row.get(ref_field) is not None:
                record[ref_field] = row[ref_field]
        record.update(self._data_out(row.get("data")))
        record["created_at"] = _ts(row["created_at"])
        if row.get("updated_at") is not None:
            record["updated_at"] = _ts(row["updated_at"])
        return record

    async def _update_where(self, tenant: str, kind: str, where: str,
                            key_params: tuple, fields: dict) -> dict | None:
        table, _ = SPECS[kind]
        ph = self.d.ph
        row = await self.d.one(
            f"SELECT * FROM {table} WHERE tenant_id = {ph} AND {where}", key_params)
        if row is None:
            return None
        values = await self._values_for(tenant, kind, fields)
        extra = self._extra_of(kind, fields)
        if extra:
            data = self._data_out(row.get("data"))
            data.update(extra)
            values["data"] = self._data_in(data)
        if kind != "field_events":
            values["updated_at"] = utcnow()
        if values:
            assignments = ", ".join(f"{k} = {ph}" for k in values)
            await self.d.run(
                f"UPDATE {table} SET {assignments} WHERE tenant_id = {ph} AND {where}",
                tuple(values.values()) + key_params)
            row = await self.d.one(
                f"SELECT * FROM {table} WHERE tenant_id = {ph} AND {where}",
                key_params)
        return self._row_to_record(row, kind)

    async def update_record(self, tenant: str, kind: str, code: str,
                            fields: dict) -> dict | None:
        return await self._update_where(
            tenant, kind, f"code = {self.d.ph}", (tenant, code), fields)

    async def update_record_by_id(self, tenant: str, kind: str, record_id: int,
                                  fields: dict) -> dict | None:
        return await self._update_where(
            tenant, kind, f"id = {self.d.ph}", (tenant, record_id), fields)

    async def delete_record(self, tenant: str, kind: str, code: str) -> dict | None:
        existing = await self.get_record_by_code(tenant, kind, code)
        if existing is None:
            return None
        table, _ = SPECS[kind]
        ph = self.d.ph
        changes = await self.d.run(
            f"DELETE FROM {table} WHERE tenant_id = {ph} AND code = {ph}",
            (tenant, code))
        if changes == 0:
            return None
        return existing

    async def list_records(self, tenant: str, kind: str,
                           limit: int | None = None, offset: int = 0) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"
        sql = (f"SELECT * FROM {table} WHERE tenant_id = {self.d.ph}"
               f" ORDER BY {order}")
        params: tuple = (tenant,)
        if limit is not None:
            sql += f" LIMIT {self.d.ph} OFFSET {self.d.ph}"
            params = (tenant, limit, offset)
        rows = await self.d.all(sql, params)
        return [self._row_to_record(r, kind) for r in rows]

    async def count_records(self, tenant: str, kind: str) -> int:
        table, _ = SPECS[kind]
        row = await self.d.one(
            f"SELECT count(*) AS n FROM {table} WHERE tenant_id = {self.d.ph}",
            (tenant,))
        return int(row["n"]) if row else 0

    async def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        ph = self.d.ph
        row = await self.d.one(
            f"SELECT * FROM {table} WHERE tenant_id = {ph} AND code = {ph}",
            (tenant, code))
        return None if row is None else self._row_to_record(row, kind)
