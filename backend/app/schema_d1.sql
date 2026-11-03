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
    puc_code            TEXT,
    puc_status          TEXT,
    sector_category     TEXT,
    market_scope        TEXT,
    primary_species     TEXT,
    scientific_name     TEXT,
    issue_date          TEXT,
    issuing_authority   TEXT,
    post_inspect_due_date TEXT,
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
    parcel_id       INTEGER,
    parcel_code     TEXT,
    crop_name       TEXT,
    variety_name    TEXT,
    seed_origin     TEXT,
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
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
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
    input_lot_id INTEGER,
    input_lot_code TEXT,
    growth_stage TEXT,
    target_pest  TEXT,
    dosage       TEXT,
    quantity_applied REAL,
    phi_days         INTEGER,
    safe_harvest_date TEXT,
    data        TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, input_lot_id) REFERENCES input_lots (tenant_id, id)
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
    farmer_id     INTEGER,
    farmer_code   TEXT,
    parcel_id     INTEGER,
    parcel_code   TEXT,
    weigh_slip_number TEXT,
    traceability_code TEXT,
    data_retention_until TEXT,
    status        TEXT NOT NULL DEFAULT 'IN_STOCK',
    expiry_date   TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, farmer_id) REFERENCES actors (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
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

-- Traceability data standard (D-STD-01, phase 1) — see docs/DATA_MODEL.md.

CREATE TABLE IF NOT EXISTS actors (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    actor_type    TEXT,
    gln_code      TEXT,
    parent_id     INTEGER,
    parent_code   TEXT,
    province_code TEXT,
    district_code TEXT,
    commune_code  TEXT,
    address       TEXT,
    phone         TEXT,
    email         TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, parent_id) REFERENCES actors (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS spatial_units (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT,
    unit_type     TEXT,
    operator_id   INTEGER,
    operator_code TEXT,
    national_land_parcel_id TEXT,
    map_sheet_number TEXT,
    parcel_number    TEXT,
    land_tenure_doc_type TEXT,
    land_cert_serial     TEXT,
    land_legal_owner_name TEXT,
    forest_subzone_code    TEXT,
    forest_compartment_code TEXT,
    forest_plot_code       TEXT,
    area_m2       REAL,
    slope_degree  REAL,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, operator_id) REFERENCES actors (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS zone_parcel_links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    zone_id       INTEGER,
    zone_code     TEXT,
    parcel_id     INTEGER,
    parcel_code   TEXT,
    registered_area_m2 REAL,
    membership_status  TEXT,
    joined_date   TEXT,
    left_date     TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, zone_id, parcel_id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS input_lots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT,
    category      TEXT,
    substance_code TEXT,
    supplier_id   INTEGER,
    supplier_code TEXT,
    vn_registration_number TEXT,
    batch_no      TEXT,
    purchase_date TEXT,
    quantity      REAL,
    unit          TEXT,
    phi_days      INTEGER,
    expiry_date   TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, supplier_id) REFERENCES actors (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS phi_validations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    lot_code      TEXT,
    plan_code     TEXT,
    max_safe_harvest_date TEXT,
    actual_harvest_date   TEXT,
    outcome       TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id)
);

-- Traceability data standard, phase 2 (D-STD-01): packing chain and
-- national traceability records.

CREATE TABLE IF NOT EXISTS packing_lots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    facility_id   INTEGER,
    facility_code TEXT,
    phc_code      TEXT,
    product_name  TEXT,
    output_weight_kg REAL,
    yield_norm_ratio REAL,
    storage_type  TEXT,
    packed_at     TEXT,
    expiry_date   TEXT,
    status        TEXT NOT NULL DEFAULT 'PACKED',
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, facility_id) REFERENCES actors (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS packaging_units (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    packing_lot_id   INTEGER,
    packing_lot_code TEXT,
    level         TEXT,
    gtin_code     TEXT,
    sscc_code     TEXT,
    package_spec  TEXT,
    units_count   INTEGER,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, packing_lot_id) REFERENCES packing_lots (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS packing_inputs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    packing_lot_id   INTEGER,
    packing_lot_code TEXT,
    harvest_lot_id   INTEGER,
    harvest_lot_code TEXT,
    allocated_weight_kg REAL,
    linked_at     TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, packing_lot_id, harvest_lot_id),
    FOREIGN KEY (tenant_id, packing_lot_id) REFERENCES packing_lots (tenant_id, id),
    FOREIGN KEY (tenant_id, harvest_lot_id) REFERENCES lots (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS traceability_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    packaging_unit_id   INTEGER,
    packaging_unit_code TEXT,
    traceability_code   TEXT,
    product_name  TEXT,
    product_image_url TEXT,
    business_unit_name    TEXT,
    business_unit_address TEXT,
    production_event_time TEXT,
    brand_trademark_serial TEXT,
    expiration_date   TEXT,
    data_carrier_type TEXT,
    data_retention_until TEXT,
    sync_status   TEXT NOT NULL DEFAULT 'PENDING_SYNC',
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, packaging_unit_id) REFERENCES packaging_units (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS cte_stages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    traceability_code TEXT,
    stage_no      INTEGER,
    stage_name    TEXT,
    product_trace_code  TEXT,
    location_trace_code TEXT,
    batch_lot_number    TEXT,
    event_time    TEXT,
    scheme_code   TEXT,
    data          TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    UNIQUE (tenant_id, id)
);
