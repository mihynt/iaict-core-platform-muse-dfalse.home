-- IAICT Core Platform — D1 (SQLite) schema (T-014, DEC-008).
-- A dialect port of app/schema.sql (PostgreSQL): same tables, same
-- columns, same tenant-isolation structure. Composite foreign keys
-- (tenant_id, ref_id) keep references inside one tenant; D1 enforces
-- them (verified 2026-11-03: a cross-tenant INSERT is rejected with
-- SQLITE_CONSTRAINT_FOREIGNKEY). Differences from the PG original are
-- type-level only: TIMESTAMPTZ/DATE -> TEXT (ISO-8601, written by the
-- store), NUMERIC -> REAL, JSONB -> TEXT (JSON), BIGSERIAL ->
-- INTEGER PRIMARY KEY AUTOINCREMENT.

CREATE TABLE IF NOT EXISTS tenants (
    slug       TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    tenant_id    TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    username     TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role         TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (tenant_id, username)
);

CREATE TABLE IF NOT EXISTS workspaces (
    tenant_id  TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    scope     TEXT NOT NULL,
    tenant_id TEXT,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    target    TEXT NOT NULL,
    outcome   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS zones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    area_ha         REAL,
    address         TEXT,
    lat             REAL,
    lon             REAL,
    geom            TEXT,
    crop_group      TEXT,
    season          TEXT,
    water_source    TEXT,
    managing_entity TEXT,
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    data            TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS zone_boundary_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id  TEXT NOT NULL,
    zone_id    INTEGER NOT NULL,
    version    INTEGER NOT NULL,
    geom       TEXT,
    changed_by TEXT,
    reason     TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, zone_id, version),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mother_plants (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code              TEXT NOT NULL,
    species           TEXT,
    variety           TEXT,
    scientific_name   TEXT,
    origin            TEXT,
    planting_year     INTEGER,
    lat               REAL,
    lon               REAL,
    zone_id           INTEGER,
    zone_code         TEXT,
    owner_manager     TEXT,
    recognition_no    TEXT,
    issuing_authority TEXT,
    valid_from        TEXT,
    valid_to          TEXT,
    status            TEXT NOT NULL DEFAULT 'ALIVE',
    data              TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS mother_plant_status_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    plant_id    INTEGER NOT NULL,
    status      TEXT,
    health      TEXT,
    pest_risk   TEXT,
    note        TEXT,
    recorded_by TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crop_plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    name            TEXT,
    zone_id         INTEGER,
    zone_code       TEXT,
    plant_id        INTEGER,
    plant_code      TEXT,
    crop_name       TEXT,
    start_date      TEXT,
    end_date        TEXT,
    target_yield_kg REAL,
    status          TEXT NOT NULL DEFAULT 'DRAFT',
    data            TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS field_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    plan_id     INTEGER,
    plan_code   TEXT,
    zone_id     INTEGER,
    zone_code   TEXT,
    event_type  TEXT NOT NULL,
    occurred_at TEXT,
    lat         REAL,
    lon         REAL,
    actor       TEXT,
    device      TEXT,
    notes       TEXT,
    materials   TEXT,
    data        TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS lots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    zone_id       INTEGER,
    zone_code     TEXT,
    plan_id       INTEGER,
    plan_code     TEXT,
    harvest_date  TEXT,
    quantity      REAL,
    unit          TEXT NOT NULL DEFAULT 'kg',
    harvested_by  TEXT,
    quality_grade TEXT,
    status        TEXT NOT NULL DEFAULT 'IN_STOCK',
    expiry_date   TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS lot_relations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL,
    parent_lot_id INTEGER NOT NULL,
    child_lot_id  INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    quantity      REAL,
    unit          TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (tenant_id, parent_lot_id) REFERENCES lots (tenant_id, id),
    FOREIGN KEY (tenant_id, child_lot_id) REFERENCES lots (tenant_id, id)
);
