-- IAICT Core Platform — PostgreSQL schema (M2, task T-004).
-- Standard SQL + core PostgreSQL types only (DEC-006 portability rules).
-- Every tenant-owned row carries tenant_id; object references use composite
-- foreign keys (tenant_id, ref_id) so a row can never reference another
-- tenant's object. Entity definitions: docs/DATA_MODEL.md (SRS v2.0 groups
-- ZON / MPL / FLD / LOT plus the M1 foundation entities).

CREATE TABLE IF NOT EXISTS tenants (
    slug       TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE | SUSPENDED
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    tenant_id    TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    username     TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role         TEXT NOT NULL,  -- TENANT_ADMIN | OPERATOR | VIEWER
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, username)
);

CREATE TABLE IF NOT EXISTS workspaces (
    tenant_id  TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS audit_log (
    seq       BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
    scope     TEXT NOT NULL,  -- platform | tenant
    tenant_id TEXT,
    actor     TEXT NOT NULL,
    action    TEXT NOT NULL,
    target    TEXT NOT NULL,
    outcome   TEXT NOT NULL
);

-- ---- ZON: material zones / sites / plots (SRS ZON-01..04) ------------------
CREATE TABLE IF NOT EXISTS zones (
    id              BIGSERIAL,
    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    area_ha         NUMERIC,
    address         TEXT,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    geom            JSONB,  -- GeoJSON polygon, WGS84 / RFC 7946 (ZON-02)
    crop_group      TEXT,
    season          TEXT,
    water_source    TEXT,
    managing_entity TEXT,
    puc_code            TEXT,  -- national production-unit code (D-STD-01)
    puc_status          TEXT,  -- PENDING_POST_INSPECTION | ACTIVE_COMPLIANT | SUSPENDED_TEMPORARILY | RESTORED | REVOKED_PERMANENTLY
    sector_category     TEXT,  -- CROP_FARMING | FORESTRY_PLANTATION | LIVESTOCK_FARMING | AQUACULTURE
    market_scope        TEXT,  -- DOMESTIC_ONLY | EXPORT_ELIGIBLE | BOTH_MARKETS
    primary_species     TEXT,
    scientific_name     TEXT,
    issue_date          DATE,
    issuing_authority   TEXT,
    post_inspect_due_date DATE,
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    data            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code)
);

-- Boundary version history (ZON-04).
CREATE TABLE IF NOT EXISTS zone_boundary_versions (
    id         BIGSERIAL PRIMARY KEY,
    tenant_id  TEXT NOT NULL,
    zone_id    BIGINT NOT NULL,
    version    INTEGER NOT NULL,
    geom       JSONB,
    changed_by TEXT,
    reason     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, zone_id, version),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id) ON DELETE CASCADE
);

-- ---- MPL: mother plants / elite trees (SRS MPL-01..04) ---------------------
CREATE TABLE IF NOT EXISTS mother_plants (
    id               BIGSERIAL,
    tenant_id        TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code             TEXT NOT NULL,  -- unique plant code, QR payload (MPL-01)
    species          TEXT,
    variety          TEXT,
    scientific_name  TEXT,
    origin           TEXT,
    planting_year    INTEGER,
    lat              DOUBLE PRECISION,
    lon              DOUBLE PRECISION,
    zone_id          BIGINT,
    zone_code        TEXT,
    owner_manager    TEXT,
    recognition_no   TEXT,
    issuing_authority TEXT,
    valid_from       DATE,
    valid_to         DATE,
    status           TEXT NOT NULL DEFAULT 'ALIVE',
    data             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id)
);

-- Health / conservation status history (MPL-04).
CREATE TABLE IF NOT EXISTS mother_plant_status_history (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    plant_id    BIGINT NOT NULL,
    status      TEXT,
    health      TEXT,
    pest_risk   TEXT,
    note        TEXT,
    recorded_by TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id) ON DELETE CASCADE
);

-- ---- Traceability data standard, phase 1 (D-STD-01) -----------------------
-- Actors / households (ENT_ACTOR_HOUSEHOLD subset).
CREATE TABLE IF NOT EXISTS actors (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    actor_type    TEXT,
    gln_code      TEXT,
    parent_id     BIGINT,
    parent_code   TEXT,
    province_code TEXT,
    district_code TEXT,
    commune_code  TEXT,
    address       TEXT,
    phone         TEXT,
    email         TEXT,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, parent_id) REFERENCES actors (tenant_id, id)
);

-- Spatial units: land parcels, forest plots, ponds/cages, barns, vessels
-- (ENT_SPATIAL_UNIT subset).
CREATE TABLE IF NOT EXISTS spatial_units (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT,
    unit_type     TEXT,
    operator_id   BIGINT,
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
    area_m2       NUMERIC,
    slope_degree  NUMERIC,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, operator_id) REFERENCES actors (tenant_id, id)
);

-- N-N membership of spatial units in production zones (REL_ZONE_SPATIAL_UNIT).
CREATE TABLE IF NOT EXISTS zone_parcel_links (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    zone_id       BIGINT,
    zone_code     TEXT,
    parcel_id     BIGINT,
    parcel_code   TEXT,
    registered_area_m2 NUMERIC,
    membership_status  TEXT,
    joined_date   DATE,
    left_date     DATE,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, zone_id, parcel_id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
);

-- Input material lots (ENT_INPUT_INVENTORY subset).
CREATE TABLE IF NOT EXISTS input_lots (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT,
    category      TEXT,
    substance_code TEXT,
    supplier_id   BIGINT,
    supplier_code TEXT,
    vn_registration_number TEXT,
    batch_no      TEXT,
    purchase_date DATE,
    quantity      NUMERIC,
    unit          TEXT,
    phi_days      INTEGER,
    expiry_date   DATE,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, supplier_id) REFERENCES actors (tenant_id, id)
);

-- Pre-harvest interval validation log (LOG_PHI_VALIDATION).
CREATE TABLE IF NOT EXISTS phi_validations (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    lot_code      TEXT,
    plan_code     TEXT,
    max_safe_harvest_date DATE,
    actual_harvest_date   DATE,
    outcome       TEXT,  -- PASSED_SAFE | BLOCKED_VIOLATION_PHI
    last_treatment_ref TEXT,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id)
);

-- ---- FLD: crop plans and field events (SRS FLD-01..04) ---------------------
CREATE TABLE IF NOT EXISTS crop_plans (
    id              BIGSERIAL,
    tenant_id       TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    name            TEXT,
    zone_id         BIGINT,
    zone_code       TEXT,
    plant_id        BIGINT,
    plant_code      TEXT,
    parcel_id       BIGINT,
    parcel_code     TEXT,
    crop_name       TEXT,
    variety_name    TEXT,
    seed_origin     TEXT,
    start_date      DATE,
    end_date        DATE,
    target_yield_kg NUMERIC,
    status          TEXT NOT NULL DEFAULT 'DRAFT',  -- DRAFT | RUNNING | ENDED
    data            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
);

CREATE TABLE IF NOT EXISTS field_events (
    id          BIGSERIAL,
    tenant_id   TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    plan_id     BIGINT,
    plan_code   TEXT,
    zone_id     BIGINT,
    zone_code   TEXT,
    event_type  TEXT NOT NULL,  -- IRRIGATION | FERTILIZING | SOIL | PRUNING | PEST | INSPECTION | HARVEST | OTHER
    occurred_at TIMESTAMPTZ,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    actor       TEXT,
    device      TEXT,
    notes       TEXT,
    materials   JSONB,  -- [{name, supplier, material_lot, quantity, unit, used_by}] (FLD-03)
    input_lot_id   BIGINT,
    input_lot_code TEXT,
    growth_stage   TEXT,
    target_pest    TEXT,
    dosage         TEXT,
    quantity_applied NUMERIC,
    phi_days         INTEGER,
    safe_harvest_date DATE,  -- occurred_at date + phi_days (LOG_CULTIVATION_TREATMENT, D-STD-01)
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, input_lot_id) REFERENCES input_lots (tenant_id, id)
);

-- ---- LOT: harvest lots and traceability (SRS LOT-01..04) -------------------
CREATE TABLE IF NOT EXISTS lots (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    zone_id       BIGINT,
    zone_code     TEXT,
    plan_id       BIGINT,
    plan_code     TEXT,
    harvest_date  DATE,
    quantity      NUMERIC,
    unit          TEXT NOT NULL DEFAULT 'kg',
    harvested_by  TEXT,
    quality_grade TEXT,
    farmer_id     BIGINT,
    farmer_code   TEXT,
    parcel_id     BIGINT,
    parcel_code   TEXT,
    weigh_slip_number TEXT,
    traceability_code TEXT,  -- product || location || lot || event time (TT 02/2024, D-STD-01)
    data_retention_until DATE,  -- expiry/harvest + 12 months (TT 17/2021)
    status        TEXT NOT NULL DEFAULT 'IN_STOCK',
    expiry_date   DATE,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, farmer_id) REFERENCES actors (tenant_id, id),
    FOREIGN KEY (tenant_id, parcel_id) REFERENCES spatial_units (tenant_id, id)
);

-- Split / merge / transform lineage (LOT-02). Acyclicity is enforced at the
-- application layer; the composite FKs keep lineage inside one tenant.
CREATE TABLE IF NOT EXISTS lot_relations (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    parent_lot_id BIGINT NOT NULL,
    child_lot_id  BIGINT NOT NULL,
    relation_type TEXT NOT NULL,  -- SPLIT | MERGE | TRANSFORM
    quantity      NUMERIC,
    unit          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, parent_lot_id) REFERENCES lots (tenant_id, id),
    FOREIGN KEY (tenant_id, child_lot_id) REFERENCES lots (tenant_id, id)
);

-- ---- Traceability standard, phase 2 (D-STD-01): packing chain -------------
-- Packed/processed lots at a packing house (ENT_PACKING_PROCESSING subset).
CREATE TABLE IF NOT EXISTS packing_lots (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    facility_id   BIGINT,
    facility_code TEXT,
    phc_code      TEXT,
    product_name  TEXT,
    output_weight_kg NUMERIC,
    yield_norm_ratio NUMERIC,  -- max technical recovery ratio (mass balance)
    storage_type  TEXT,  -- FRESH_AMBIENT | CHILLED_COOL | FROZEN_PROCESSED
    packed_at     TIMESTAMPTZ,
    expiry_date   DATE,
    status        TEXT NOT NULL DEFAULT 'PACKED',
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, facility_id) REFERENCES actors (tenant_id, id)
);

-- Packaging units / SKU (ENT_PACKAGING_UNIT_SKU subset).
CREATE TABLE IF NOT EXISTS packaging_units (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    packing_lot_id   BIGINT,
    packing_lot_code TEXT,
    level         TEXT,  -- CONSUMER_ITEM_SKU | INNER_PACK | SHIPPING_CASE_CARTON | LOGISTIC_PALLET_CONTAINER
    gtin_code     TEXT,
    sscc_code     TEXT,
    package_spec  TEXT,
    units_count   INTEGER,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, packing_lot_id) REFERENCES packing_lots (tenant_id, id)
);

-- N-N link: harvest lots consumed by a packing lot (ENT_PACKING_INPUT_LINK).
CREATE TABLE IF NOT EXISTS packing_inputs (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    packing_lot_id   BIGINT,
    packing_lot_code TEXT,
    harvest_lot_id   BIGINT,
    harvest_lot_code TEXT,
    allocated_weight_kg NUMERIC,
    linked_at     TIMESTAMPTZ,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, packing_lot_id, harvest_lot_id),
    FOREIGN KEY (tenant_id, packing_lot_id) REFERENCES packing_lots (tenant_id, id),
    FOREIGN KEY (tenant_id, harvest_lot_id) REFERENCES lots (tenant_id, id)
);

-- National traceability records (SYS_TRACEABILITY_RECORD subset).
CREATE TABLE IF NOT EXISTS traceability_records (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    packaging_unit_id   BIGINT,
    packaging_unit_code TEXT,
    traceability_code   TEXT,
    product_name  TEXT,
    product_image_url TEXT,
    business_unit_name    TEXT,
    business_unit_address TEXT,
    production_event_time TIMESTAMPTZ,
    brand_trademark_serial TEXT,
    expiration_date   DATE,
    data_carrier_type TEXT,  -- QR_CODE | GS1_128_BARCODE | DATAMATRIX | RFID_TAG | NFC_CHIP
    data_retention_until DATE,
    sync_status   TEXT NOT NULL DEFAULT 'PENDING_SYNC',
    synced_at TIMESTAMPTZ,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, packaging_unit_id) REFERENCES packaging_units (tenant_id, id)
);

-- Critical-tracking-event stages of a traceability record
-- (LOG_CTE_SUPPLY_CHAIN_STAGE subset; linked by traceability_code).
CREATE TABLE IF NOT EXISTS cte_stages (
    id            BIGSERIAL,
    tenant_id     TEXT NOT NULL REFERENCES tenants (slug) ON DELETE CASCADE,
    traceability_code TEXT,
    stage_no      INTEGER,
    stage_name    TEXT,
    product_trace_code  TEXT,
    location_trace_code TEXT,
    batch_lot_number    TEXT,
    event_time    TIMESTAMPTZ,
    scheme_code   TEXT,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id)
);

-- T-017/M3: traceability codes are unique per tenant (dossier: UNIQUE NOT NULL).
CREATE UNIQUE INDEX IF NOT EXISTS ux_traceability_records_code
    ON traceability_records (tenant_id, traceability_code)
    WHERE traceability_code IS NOT NULL;
