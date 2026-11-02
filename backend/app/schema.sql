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
    crop_name       TEXT,
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
    FOREIGN KEY (tenant_id, plant_id) REFERENCES mother_plants (tenant_id, id)
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
    data        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id)
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
    status        TEXT NOT NULL DEFAULT 'IN_STOCK',
    expiry_date   DATE,
    data          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, code),
    FOREIGN KEY (tenant_id, zone_id) REFERENCES zones (tenant_id, id),
    FOREIGN KEY (tenant_id, plan_id) REFERENCES crop_plans (tenant_id, id)
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
