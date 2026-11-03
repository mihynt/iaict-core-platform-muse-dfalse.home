"""Cloudflare D1 backend for the store boundary (T-014, DEC-008).

Selected on Workers via IAICT_BACKEND=d1 (see store.make_store and the
LazyD1Store binding shim in store.py). D1 is Cloudflare's SQLite
database, local to the Worker: queries are awaited promises on the
binding object (prepare/bind/first/all/run/batch), so this backend is
async-native — the reason the whole store interface became async.

The SQL is the SQLite dialect port in app/schema_d1.sql: same tables
and composite (tenant_id, ref_id) foreign keys as the PostgreSQL
schema. D1 enforces those FKs (verified live 2026-11-03), so the
cross-tenant reference rejection proven on PostgreSQL holds here too.

The PostgreSQL backends (pgstore / workerstore) remain the documented
exit path: swap the backend, keep the API contract.
"""
from __future__ import annotations

import json
import pathlib

from .records_spec import REF_ID_COLUMN, SPECS
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User, utcnow

_SCHEMA = pathlib.Path(__file__).with_name("schema_d1.sql").read_text(encoding="utf-8")
_DDL = [stmt.strip() for stmt in _SCHEMA.split(";\n") if stmt.strip()]

_TABLES_CHILD_FIRST = [
    "audit_log", "packing_inputs", "lot_relations", "field_events", "lots",
    "crop_plans", "cte_stages", "traceability_records", "packaging_units",
    "packing_lots",
    "phi_validations", "zone_parcel_links", "input_lots", "spatial_units",
    "actors",
    "mother_plant_status_history", "mother_plants", "zone_boundary_versions",
    "zones", "workspaces", "users", "tenants",
]

_NEW_TABLES = ["actors", "spatial_units", "zone_parcel_links", "input_lots",
               "phi_validations"]

_PHASE2_TABLES = ["packing_lots", "packaging_units", "packing_inputs",
                  "traceability_records", "cte_stages"]

# D-STD-01 in-place upgrade for databases created before the traceability
# standard landed: new tables come from schema_d1.sql; new columns on the
# pre-existing tables are added as plain columns (SQLite cannot add a
# foreign key via ALTER TABLE — reference resolution is also enforced at
# the store layer, and fresh databases get the full composite FKs).
_UPGRADE_COLUMNS = {
    "zones": [("puc_code", "TEXT"), ("puc_status", "TEXT"),
              ("sector_category", "TEXT"), ("market_scope", "TEXT"),
              ("primary_species", "TEXT"), ("scientific_name", "TEXT"),
              ("issue_date", "TEXT"), ("issuing_authority", "TEXT"),
              ("post_inspect_due_date", "TEXT")],
    "crop_plans": [("parcel_id", "INTEGER"), ("parcel_code", "TEXT"),
                   ("variety_name", "TEXT"), ("seed_origin", "TEXT")],
    "field_events": [("input_lot_id", "INTEGER"), ("input_lot_code", "TEXT"),
                     ("growth_stage", "TEXT"), ("target_pest", "TEXT"),
                     ("dosage", "TEXT"), ("quantity_applied", "REAL"),
                     ("phi_days", "INTEGER"), ("safe_harvest_date", "TEXT")],
    "lots": [("farmer_id", "INTEGER"), ("farmer_code", "TEXT"),
             ("parcel_id", "INTEGER"), ("parcel_code", "TEXT"),
             ("weigh_slip_number", "TEXT"), ("traceability_code", "TEXT"),
             ("data_retention_until", "TEXT")],
}


def _plain(obj):
    """Workers results arrive as JS proxies; tests use plain dicts."""
    if obj is None or isinstance(obj, (dict, list, str, int, float, bool)):
        return obj
    try:
        return obj.to_py()
    except Exception:
        return obj


def _is_unique_violation(exc: BaseException) -> bool:
    msg = str(exc)
    return "UNIQUE constraint failed" in msg or "SQLITE_CONSTRAINT_UNIQUE" in msg


def _conv_out(value, ckind: str):
    if value is None:
        return None
    if ckind == "json" and isinstance(value, str):
        return json.loads(value)
    if ckind == "num" and isinstance(value, (int, float)):
        return float(value)
    return value


def _conv_in(value, ckind: str):
    if value is None:
        return None
    if ckind == "json":
        return json.dumps(value)
    return value


class D1Store:
    kind = "d1"

    def __init__(self, db) -> None:
        self._db = db
        self._schema_ready = False

    # ---- plumbing ------------------------------------------------------
    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        row = _plain(await self._db.prepare(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tenants'"
        ).first())
        if row is None:
            await self._db.batch([self._db.prepare(stmt) for stmt in _DDL])
            self._schema_ready = True
            return

        async def _table_exists(name: str) -> bool:
            probe = _plain(await self._db.prepare(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?"
            ).bind(name).first())
            return probe is not None

        def _create_stmts(names: list[str]) -> list[str]:
            return [stmt for stmt in _DDL
                    if any(f"CREATE TABLE IF NOT EXISTS {name} " in stmt or
                           f"CREATE TABLE IF NOT EXISTS {name}(" in stmt
                           for name in names)]

        if not await _table_exists("actors"):
            # D-STD-01 phase-1 upgrade: new tables + ALTER-added columns.
            stmts = _create_stmts(_NEW_TABLES)
            for table, cols in _UPGRADE_COLUMNS.items():
                for col, ctype in cols:
                    stmts.append(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
            await self._db.batch([self._db.prepare(stmt) for stmt in stmts])
        if not await _table_exists("packing_lots"):
            # D-STD-01 phase-2 upgrade: packing chain (new tables only).
            stmts = _create_stmts(_PHASE2_TABLES)
            await self._db.batch([self._db.prepare(stmt) for stmt in stmts])
        # T-017/M3 backstop: unique traceability code per tenant. The
        # statement goes through the raw binding, NOT self._run (which
        # itself awaits _ensure_schema — that recursion burned the
        # Workers CPU budget and took the beta's write paths down with
        # 1102/500s on 2026-11-03 until this fix). Guarded: a legacy
        # duplicate must not take the whole API down.
        self._schema_ready = True
        try:
            await self._db.prepare(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_traceability_records_code"
                " ON traceability_records (tenant_id, traceability_code)"
                " WHERE traceability_code IS NOT NULL").run()
        except Exception:
            pass
        # T-023 column upgrades (audit T-021 field gaps): portal sync
        # timestamp + PHI last-treatment reference. Raw binding only
        # (see the M3 note above); duplicate-column errors on already
        # upgraded databases are expected and ignored.
        for _stmt in (
            "ALTER TABLE traceability_records ADD COLUMN synced_at TEXT",
            "ALTER TABLE phi_validations ADD COLUMN last_treatment_ref TEXT",
            # T-024 field completion (phase review follow-up, 2026-11-03)
            "ALTER TABLE zones ADD COLUMN vsic_code TEXT",
            "ALTER TABLE zones ADD COLUMN dist_to_residential_m REAL",
            "ALTER TABLE zones ADD COLUMN dist_to_sensitive_zone_m REAL",
            "ALTER TABLE zones ADD COLUMN bee_site_min_dist_km REAL",
            "ALTER TABLE input_lots ADD COLUMN purchase_invoice_no TEXT",
            "ALTER TABLE input_lots ADD COLUMN qcvn_scheme_id TEXT",
            "ALTER TABLE field_events ADD COLUMN application_method TEXT",
            "ALTER TABLE field_events ADD COLUMN fruit_bagging_count INTEGER",
            "ALTER TABLE crop_plans ADD COLUMN planting_density REAL",
            "ALTER TABLE crop_plans ADD COLUMN seed_origin_doc TEXT",
            "ALTER TABLE zones ADD COLUMN owner_actor_id INTEGER",
            "ALTER TABLE zones ADD COLUMN owner_actor_code TEXT",
        ):
            try:
                await self._db.prepare(_stmt).run()
            except Exception:
                pass

    async def _first(self, sql: str, params: tuple = ()):
        await self._ensure_schema()
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        return _plain(await stmt.first())

    async def _all(self, sql: str, params: tuple = ()) -> list[dict]:
        await self._ensure_schema()
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = _plain(await stmt.all())
        return result["results"] if isinstance(result, dict) else []

    async def _run(self, sql: str, params: tuple = ()) -> dict:
        await self._ensure_schema()
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        result = _plain(await stmt.run())
        return result.get("meta", {}) if isinstance(result, dict) else {}

    async def reset(self) -> None:
        await self._ensure_schema()
        await self._db.batch(
            [self._db.prepare(f"DELETE FROM {t}") for t in _TABLES_CHILD_FIRST]
        )
        try:
            await self._run(
                "DELETE FROM sqlite_sequence WHERE name IN"
                " ('audit_log','zones','mother_plants','crop_plans','field_events','lots')"
            )
        except Exception:
            pass  # sqlite_sequence is an implementation detail; ignore if absent

    # ---- audit ---------------------------------------------------------
    async def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                           action: str, target: str, outcome: str) -> dict:
        ts = utcnow()
        meta = await self._run(
            "INSERT INTO audit_log (ts, scope, tenant_id, actor, action, target, outcome)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, scope, tenant_id, actor, action, target, outcome),
        )
        return {"seq": meta.get("last_row_id"), "ts": ts, "scope": scope,
                "tenant_id": tenant_id, "actor": actor, "action": action,
                "target": target, "outcome": outcome}

    async def list_audit(self) -> list[dict]:
        return await self._all("SELECT * FROM audit_log ORDER BY seq")

    async def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return await self._all(
            "SELECT * FROM audit_log WHERE tenant_id = ? ORDER BY seq", (tenant_id,)
        )

    # ---- tenants -------------------------------------------------------
    async def create_tenant(self, slug: str, name: str) -> Tenant | None:
        created = utcnow()
        try:
            await self._run(
                "INSERT INTO tenants (slug, name, status, created_at) VALUES (?, ?, 'ACTIVE', ?)",
                (slug, name, created),
            )
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        return Tenant(slug=slug, name=name, created_at=created)

    async def get_tenant(self, slug: str) -> Tenant | None:
        row = await self._first("SELECT * FROM tenants WHERE slug = ?", (slug,))
        if row is None:
            return None
        return Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                      created_at=row["created_at"])

    async def list_tenants(self) -> list[Tenant]:
        rows = await self._all("SELECT * FROM tenants ORDER BY slug")
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=r["created_at"]) for r in rows]

    async def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        meta = await self._run(
            "UPDATE tenants SET status = ? WHERE slug = ?", (status, slug)
        )
        if not meta.get("changes"):
            return None
        return await self.get_tenant(slug)

    # ---- users ---------------------------------------------------------
    async def create_user(self, tenant: str, username: str, display_name: str,
                          role: str) -> User | None:
        created = utcnow()
        try:
            await self._run(
                "INSERT INTO users (tenant_id, username, display_name, role, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (tenant, username, display_name, role, created),
            )
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        return User(username=username, display_name=display_name, role=role,
                    created_at=created)

    async def get_user(self, tenant: str, username: str) -> User | None:
        row = await self._first(
            "SELECT * FROM users WHERE tenant_id = ? AND username = ?", (tenant, username)
        )
        if row is None:
            return None
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=row["created_at"])

    async def list_users(self, tenant: str) -> list[User]:
        rows = await self._all(
            "SELECT * FROM users WHERE tenant_id = ? ORDER BY username", (tenant,)
        )
        return [User(username=r["username"], display_name=r["display_name"],
                     role=r["role"], created_at=r["created_at"]) for r in rows]

    async def tenant_user_count(self, tenant: str) -> int:
        row = await self._first(
            "SELECT count(*) AS n FROM users WHERE tenant_id = ?", (tenant,)
        )
        return int(row["n"]) if row else 0

    # ---- workspaces ------------------------------------------------------
    async def create_workspace(self, tenant: str, name: str) -> bool:
        meta = await self._run(
            "INSERT INTO workspaces (tenant_id, name, created_at) VALUES (?, ?, ?)"
            " ON CONFLICT DO NOTHING",
            (tenant, name, utcnow()),
        )
        return meta.get("changes") == 1

    async def list_workspace_names(self, tenant: str) -> list[str]:
        rows = await self._all(
            "SELECT name FROM workspaces WHERE tenant_id = ? ORDER BY name", (tenant,)
        )
        return [r["name"] for r in rows]

    # ---- production records ---------------------------------------------
    async def _resolve_ref(self, tenant: str, ref_kind: str, code: str) -> int | None:
        table = SPECS[ref_kind][0]
        row = await self._first(
            f"SELECT id FROM {table} WHERE tenant_id = ? AND code = ?", (tenant, code)
        )
        return None if row is None else row["id"]

    async def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        table, columns = SPECS[kind]
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
        known = set(columns) | set(refs)
        extra = {k: v for k, v in fields.items() if k not in known and k != "code"}
        for col, ckind in columns.items():
            if col in fields:
                values[col] = _conv_in(fields[col], ckind)
        now = utcnow()
        names = ["tenant_id", "data", "created_at"]
        params = [tenant, json.dumps(extra), now]
        if kind != "field_events":  # the one table without updated_at (as in PG)
            names.append("updated_at")
            params.append(now)
        names += list(values.keys())
        params += list(values.values())
        if kind in CODED_KINDS:
            names.insert(1, "code")
            params.insert(1, fields.get("code"))
        placeholders = ", ".join(["?"] * len(names))
        try:
            meta = await self._run(
                f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})",
                tuple(params),
            )
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        row = await self._first(
            f"SELECT * FROM {table} WHERE id = ?", (meta.get("last_row_id"),)
        )
        return self._row_to_record(row, kind)

    def _row_to_record(self, row: dict, kind: str) -> dict:
        _, columns = SPECS[kind]
        record: dict = {"id": row["id"], "tenant_id": row["tenant_id"]}
        if kind in CODED_KINDS:
            record["code"] = row["code"]
        for col, ckind in columns.items():
            if row.get(col) is not None:
                record[col] = _conv_out(row[col], ckind)
        for ref_field in RECORD_REFS[kind]:
            if row.get(ref_field) is not None:
                record[ref_field] = row[ref_field]
        data = row.get("data")
        if isinstance(data, str):
            data = json.loads(data) if data else {}
        record.update(data or {})
        record["created_at"] = row["created_at"]
        if row.get("updated_at") is not None:
            record["updated_at"] = row["updated_at"]
        return record

    async def update_record(self, tenant: str, kind: str, code: str,
                            fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        row = await self._first(
            f"SELECT * FROM {table} WHERE tenant_id = ? AND code = ?",
            (tenant, code))
        if row is None:
            return None
        values: dict[str, object] = {}
        for ref_field, ref_kind in refs.items():
            ref_code = fields.get(ref_field)
            if ref_code is not None:
                ref_id = await self._resolve_ref(tenant, ref_kind, ref_code)
                if ref_id is None:
                    raise RefUnknown(ref_field)
                values[REF_ID_COLUMN[ref_field]] = ref_id
                values[ref_field] = ref_code
        known = set(columns) | set(refs)
        extra = {k: v for k, v in fields.items()
                 if k not in known and k != "code"}
        if extra:
            current = row.get("data")
            data = json.loads(current) if isinstance(current, str) \
                and current else {}
            data.update(extra)
            values["data"] = json.dumps(data)
        for col, ckind in columns.items():
            if col in fields:
                values[col] = _conv_in(fields[col], ckind)
        if kind != "field_events":
            values["updated_at"] = utcnow()
        if values:
            assignments = ", ".join(f"{k} = ?" for k in values)
            await self._run(
                f"UPDATE {table} SET {assignments}"
                " WHERE tenant_id = ? AND code = ?",
                tuple(values.values()) + (tenant, code))
            row = await self._first(
                f"SELECT * FROM {table} WHERE tenant_id = ? AND code = ?",
                (tenant, code))
        return self._row_to_record(row, kind)

    async def delete_record(self, tenant: str, kind: str, code: str) -> dict | None:
        existing = await self.get_record_by_code(tenant, kind, code)
        if existing is None:
            return None
        table, _ = SPECS[kind]
        meta = await self._run(
            f"DELETE FROM {table} WHERE tenant_id = ? AND code = ?",
            (tenant, code))
        changes = (meta or {}).get("changes")
        if changes is not None and changes == 0:
            return None
        return existing

    async def list_records(self, tenant: str, kind: str) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"
        rows = await self._all(
            f"SELECT * FROM {table} WHERE tenant_id = ? ORDER BY {order}", (tenant,)
        )
        return [self._row_to_record(r, kind) for r in rows]

    async def count_records(self, tenant: str, kind: str) -> int:
        await self._ensure_schema()
        table, _ = SPECS[kind]
        row = await self._first(
            f"SELECT count(*) AS n FROM {table} WHERE tenant_id = ?", (tenant,)
        )
        return int(row["n"]) if row else 0

    async def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        row = await self._first(
            f"SELECT * FROM {table} WHERE tenant_id = ? AND code = ?", (tenant, code)
        )
        return None if row is None else self._row_to_record(row, kind)
