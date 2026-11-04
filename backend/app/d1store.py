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
    "audit_log", "water_quality_tests", "residue_test_details",
    "livestock_decl_items", "pre_harvest_supervisions",
    "monitoring_declarations", "livestock_units",
    "foreign_warnings", "entity_certifications",
    "zone_market_approvals", "ref_active_substance_mrls",
    "packing_inputs", "lot_relations", "field_events", "lots",
    "crop_plans", "cte_stages", "traceability_records", "packaging_units",
    "packing_lots",
    "phi_validations", "zone_parcel_links", "zone_status_history",
    "input_lots", "spatial_units",
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


# T-039 (T-032 slice 3): versioned migrations. Every statement is
# idempotent (IF NOT EXISTS / tolerated duplicate-column), so a migration
# can run safely against a database that already carries its effect;
# schema_migrations records what has been applied. New schema changes
# land BOTH here (as the next version, for existing databases) and in
# schema_d1.sql (for fresh installs, which are stamped current).
_MIGRATIONS: list[tuple[int, list[str]]] = [
    (1, [
        # T-017/M3: unique traceability code per tenant.
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_traceability_records_code"
        " ON traceability_records (tenant_id, traceability_code)"
        " WHERE traceability_code IS NOT NULL",
    ]),
    (2, [
        # T-031: zone status history (Bang 13).
        "CREATE TABLE IF NOT EXISTS zone_status_history ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " tenant_id TEXT NOT NULL REFERENCES tenants (slug)"
        " ON DELETE CASCADE, zone_id INTEGER, zone_code TEXT,"
        " previous_status TEXT, new_status TEXT,"
        " trigger_reason_code TEXT, decision_doc_number TEXT,"
        " remediation_measures TEXT, changed_by TEXT,"
        " data TEXT NOT NULL DEFAULT '{}',"
        " created_at TEXT NOT NULL, updated_at TEXT NOT NULL,"
        " UNIQUE (tenant_id, id),"
        " FOREIGN KEY (tenant_id, zone_id)"
        " REFERENCES zones (tenant_id, id))",
    ]),
    (3, [
        # T-023/T-024/T-031 column upgrades.
        "ALTER TABLE traceability_records ADD COLUMN synced_at TEXT",
        "ALTER TABLE phi_validations ADD COLUMN last_treatment_ref TEXT",
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
        "ALTER TABLE audit_log ADD COLUMN old_value TEXT",
        "ALTER TABLE audit_log ADD COLUMN new_value TEXT",
        "ALTER TABLE audit_log ADD COLUMN client_ip TEXT",
        "ALTER TABLE audit_log ADD COLUMN user_agent TEXT",
        "ALTER TABLE users ADD COLUMN linked_actor_code TEXT",
        "ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'ACTIVE'",
        "ALTER TABLE users ADD COLUMN jurisdiction_admin_code TEXT",
        "ALTER TABLE users ADD COLUMN auth_provider_type TEXT",
    ]),
    (4, [
        # T-039/GD3: REF catalogue tables (Bang 1-5).
        "CREATE TABLE IF NOT EXISTS ref_admin_units (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    parent_unit_id  INTEGER,\n    parent_unit_code TEXT,\n    admin_level     TEXT,\n    official_name   TEXT,\n    puc_prefix_code TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, parent_unit_id) REFERENCES ref_admin_units (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS ref_market_regulations (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    market_name     TEXT,\n    competent_authority_name TEXT,\n    protocol_reference_doc   TEXT,\n    quarantine_special_rules TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS ref_active_substance_mrls (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    substance_code  TEXT,\n    substance_name  TEXT,\n    substance_category TEXT,\n    market_id       INTEGER,\n    market_code     TEXT,\n    commodity_group_code TEXT,\n    approval_status TEXT,\n    mrl_threshold_value REAL,\n    mrl_measurement_unit TEXT,\n    default_phi_days INTEGER,\n    legal_circular_ref TEXT,\n    effective_from  TEXT,\n    effective_to    TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, market_id) REFERENCES ref_market_regulations (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS ref_certification_schemes (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    scheme_name     TEXT,\n    scheme_level    TEXT,\n    applicable_sector TEXT,\n    cb_accreditation_req TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS ref_transport_modes (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    mode_name       TEXT,\n    vehicle_id_format_rule TEXT,\n    customs_circular_ref TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id)\n)",
    ]),
    (5, [
        # T-039/GD3: zone jurisdiction link (Bang 7 via Bang 1).
        "ALTER TABLE zones ADD COLUMN jurisdiction_admin_unit_id INTEGER",
        "ALTER TABLE zones ADD COLUMN jurisdiction_commune_code TEXT",
    ]),
    (6, [
        # T-041/GD3: market approvals, foreign warnings, certifications (Bang 8-10).
        "CREATE TABLE IF NOT EXISTS zone_market_approvals (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    zone_id         INTEGER,\n    zone_code       TEXT,\n    market_id       INTEGER,\n    market_code     TEXT,\n    foreign_approval_code TEXT,\n    submitted_to_foreign_date TEXT,\n    foreign_approved_date TEXT,\n    foreign_market_status TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    UNIQUE (tenant_id, zone_code, market_code),\n    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),\n    FOREIGN KEY (tenant_id, market_id) REFERENCES ref_market_regulations (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS foreign_warnings (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    zone_id         INTEGER,\n    zone_code       TEXT,\n    market_id       INTEGER,\n    market_code     TEXT,\n    violated_facility_actor_id INTEGER,\n    violated_facility_actor_code TEXT,\n    violated_packing_lot_id INTEGER,\n    violated_packing_lot_code TEXT,\n    official_notice_number TEXT,\n    notification_date TEXT,\n    violation_type  TEXT,\n    detected_pest_or_substance TEXT,\n    foreign_sanction_action TEXT,\n    remediation_report_sent_at TEXT,\n    sanction_lifted_date TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),\n    FOREIGN KEY (tenant_id, market_id) REFERENCES ref_market_regulations (tenant_id, id),\n    FOREIGN KEY (tenant_id, violated_facility_actor_id) REFERENCES actors (tenant_id, id),\n    FOREIGN KEY (tenant_id, violated_packing_lot_id) REFERENCES packing_lots (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS entity_certifications (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    certified_entity_type TEXT,\n    zone_id         INTEGER,\n    zone_code       TEXT,\n    facility_actor_id INTEGER,\n    facility_actor_code TEXT,\n    scheme_id       INTEGER,\n    scheme_code     TEXT,\n    certificate_number TEXT,\n    cert_body_name  TEXT,\n    issue_date      TEXT,\n    expiry_date     TEXT,\n    cert_status     TEXT,\n    cert_scan_url   TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),\n    FOREIGN KEY (tenant_id, facility_actor_id) REFERENCES actors (tenant_id, id),\n    FOREIGN KEY (tenant_id, scheme_id) REFERENCES ref_certification_schemes (tenant_id, id)\n)",
    ]),
    (7, [
        # T-042/GD3: livestock units + monitoring logs (Bang 14, 16, 19-22).
        "CREATE TABLE IF NOT EXISTS livestock_units (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    code            TEXT NOT NULL,\n    facility_actor_id INTEGER,\n    facility_actor_code TEXT,\n    management_granularity TEXT,\n    species_code    TEXT,\n    breed_variety_name TEXT,\n    birth_or_import_date TEXT,\n    initial_head_count INTEGER,\n    current_head_count INTEGER,\n    lifecycle_status TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, code),\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, facility_actor_id) REFERENCES actors (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS pre_harvest_supervisions (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    plan_id         INTEGER,\n    plan_code       TEXT,\n    zone_id         INTEGER,\n    zone_code       TEXT,\n    registration_date TEXT,\n    expected_harvest_start TEXT,\n    supervising_agency_name TEXT,\n    supervision_date TEXT,\n    supervision_outcome TEXT,\n    report_minutes_no TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),\n    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS monitoring_declarations (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    zone_id         INTEGER,\n    zone_code       TEXT,\n    plan_id         INTEGER,\n    plan_code       TEXT,\n    declarant_actor_id INTEGER,\n    declarant_actor_code TEXT,\n    monitoring_type TEXT,\n    inspection_timestamp TEXT,\n    pest_species_detected TEXT,\n    pest_density_index TEXT,\n    quarantine_cert_no TEXT,\n    compliance_conclusion TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),\n    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),\n    FOREIGN KEY (tenant_id, declarant_actor_id) REFERENCES actors (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS water_quality_tests (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    monitoring_id   INTEGER,\n    parcel_id       INTEGER,\n    parcel_code     TEXT,\n    measured_timestamp TEXT,\n    water_salinity_permille REAL,\n    ph_value        REAL,\n    dissolved_oxygen_mg_l REAL,\n    water_temp_celsius REAL,\n    nh3_unionized_mg_l REAL,\n    no2_nitrite_mg_l REAL,\n    alkalinity_mg_l REAL,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS residue_test_details (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    monitoring_id   INTEGER,\n    sampling_standard_code TEXT,\n    mrl_rule_id     INTEGER,\n    mrl_rule_code   TEXT,\n    measured_value  REAL,\n    measurement_unit TEXT,\n    applied_mrl_limit REAL,\n    testing_lab_name TEXT,\n    lab_test_report_no TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id),\n    FOREIGN KEY (tenant_id, mrl_rule_id) REFERENCES ref_active_substance_mrls (tenant_id, id)\n)",
        "CREATE TABLE IF NOT EXISTS livestock_decl_items (\n    id              INTEGER PRIMARY KEY AUTOINCREMENT,\n    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,\n    monitoring_id   INTEGER,\n    species_category_code TEXT,\n    declared_quantity REAL,\n    quantity_unit   TEXT,\n    farming_purpose TEXT,\n    data            TEXT NOT NULL DEFAULT '{}',\n    created_at      TEXT NOT NULL,\n    updated_at      TEXT NOT NULL,\n    UNIQUE (tenant_id, id)\n)",
    ]),
]


class D1Store:
    kind = "d1"

    def __init__(self, db) -> None:
        self._db = db
        self._schema_ready = False
        self._legacy_cols: dict[str, list] = {}

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
            # Fresh installs carry the current schema already; stamp the
            # migration ledger current without re-running statements.
            await self._db.prepare(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            ).run()
            await self._db.batch([
                self._db.prepare(
                    "INSERT OR REPLACE INTO schema_migrations"
                    " (version, applied_at) VALUES (?, ?)"
                ).bind(version, utcnow())
                for version, _stmts in _MIGRATIONS
            ])
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
        # T-039: versioned migrations through the raw binding, NOT
        # self._run (which itself awaits _ensure_schema — that recursion
        # burned the Workers CPU budget on 2026-11-03, see T-017).
        # _schema_ready is set first for the same reason.
        self._schema_ready = True
        await self._db.prepare(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        ).run()
        applied_rows = _plain(await self._db.prepare(
            "SELECT version FROM schema_migrations").all())
        applied = {
            r["version"] for r in
            (applied_rows["results"] if isinstance(applied_rows, dict) else [])
        }
        for version, stmts in _MIGRATIONS:
            if version in applied:
                continue
            for stmt in stmts:
                try:
                    await self._db.prepare(stmt).run()
                except Exception:
                    pass
            await self._db.prepare(
                "INSERT OR REPLACE INTO schema_migrations"
                " (version, applied_at) VALUES (?, ?)"
            ).bind(version, utcnow()).run()

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
                           action: str, target: str, outcome: str,
                           old_value: str | None = None,
                           new_value: str | None = None) -> dict:
        from . import auditctx
        ts = utcnow()
        meta = await self._run(
            "INSERT INTO audit_log (ts, scope, tenant_id, actor, action, target, outcome,"
            " old_value, new_value, client_ip, user_agent)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, scope, tenant_id, actor, action, target, outcome,
             old_value, new_value, auditctx.client_ip(), auditctx.user_agent()),
        )
        return {"seq": meta.get("last_row_id"), "ts": ts, "scope": scope,
                "tenant_id": tenant_id, "actor": actor, "action": action,
                "target": target, "outcome": outcome, "old_value": old_value,
                "new_value": new_value, "client_ip": auditctx.client_ip(),
                "user_agent": auditctx.user_agent()}

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
                          role: str, linked_actor_code: str | None = None,
                          jurisdiction_admin_code: str | None = None,
                          auth_provider_type: str | None = None) -> User | None:
        created = utcnow()
        try:
            await self._run(
                "INSERT INTO users (tenant_id, username, display_name, role, created_at,"
                " linked_actor_code, account_status, jurisdiction_admin_code,"
                " auth_provider_type)"
                " VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)",
                (tenant, username, display_name, role, created,
                 linked_actor_code, jurisdiction_admin_code, auth_provider_type),
            )
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        return User(username=username, display_name=display_name, role=role,
                    created_at=created, linked_actor_code=linked_actor_code,
                    jurisdiction_admin_code=jurisdiction_admin_code,
                    auth_provider_type=auth_provider_type)

    async def update_user(self, tenant: str, username: str, fields: dict) -> User | None:
        allowed = ("display_name", "role", "linked_actor_code", "account_status",
                   "jurisdiction_admin_code", "auth_provider_type")
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if await self.get_user(tenant, username) is None:
            return None
        if sets:
            assignments = ", ".join(f"{k} = ?" for k in sets)
            await self._run(
                f"UPDATE users SET {assignments} WHERE tenant_id = ? AND username = ?",
                tuple(sets.values()) + (tenant, username))
        return await self.get_user(tenant, username)

    async def get_user(self, tenant: str, username: str) -> User | None:
        row = await self._first(
            "SELECT * FROM users WHERE tenant_id = ? AND username = ?", (tenant, username)
        )
        if row is None:
            return None
        return User(username=row["username"], display_name=row["display_name"],
                    role=row["role"], created_at=row["created_at"],
                    linked_actor_code=row.get("linked_actor_code"),
                    account_status=row.get("account_status") or "ACTIVE",
                    jurisdiction_admin_code=row.get("jurisdiction_admin_code"),
                    auth_provider_type=row.get("auth_provider_type"))

    async def list_users(self, tenant: str) -> list[User]:
        rows = await self._all(
            "SELECT * FROM users WHERE tenant_id = ? ORDER BY username", (tenant,)
        )
        return [User(username=r["username"], display_name=r["display_name"],
                     role=r["role"], created_at=r["created_at"],
                     linked_actor_code=r.get("linked_actor_code"),
                     account_status=r.get("account_status") or "ACTIVE",
                     jurisdiction_admin_code=r.get("jurisdiction_admin_code"),
                     auth_provider_type=r.get("auth_provider_type")) for r in rows]

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

    async def _legacy_required_columns(self, table: str) -> list:
        """(column, neutral value) for NOT NULL columns that have no default
        and are not part of the standard write set — see the guard in
        create_record. Cached per table for the isolate's lifetime."""
        if table in self._legacy_cols:
            return self._legacy_cols[table]
        rows = await self._all(f"PRAGMA table_info({table})")
        system = {"id", "tenant_id", "code", "data", "created_at", "updated_at"}
        found = []
        for r in rows:
            if r.get("notnull") == 1 and r.get("dflt_value") is None \
                    and r.get("name") not in system:
                ctype = (r.get("type") or "").upper()
                neutral = 0 if any(t in ctype for t in ("INT", "REAL", "NUM", "DEC")) else ""
                found.append((r["name"], neutral))
        self._legacy_cols[table] = found
        return found

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
        # Legacy-schema guard: a table created by an earlier schema era can
        # carry NOT NULL columns with no default that the current field model
        # has retired (production zones.name, cut in T-034, blocked every zone
        # create with a constraint 500). Reads are SPECS-driven, so such
        # columns are never surfaced; satisfy the constraint with a neutral
        # value instead of failing the insert.
        for col, neutral in await self._legacy_required_columns(table):
            if col not in names:
                names.append(col)
                params.append(neutral)
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

    async def update_record_by_id(self, tenant: str, kind: str, record_id: int,
                            fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        row = await self._first(
            f"SELECT * FROM {table} WHERE tenant_id = ? AND id = ?",
            (tenant, record_id))
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
                " WHERE tenant_id = ? AND id = ?",
                tuple(values.values()) + (tenant, record_id))
            row = await self._first(
                f"SELECT * FROM {table} WHERE tenant_id = ? AND id = ?",
                (tenant, record_id))
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
