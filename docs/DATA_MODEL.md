# Data model (ERD) — M2 foundation

Baseline: SRS v2.0 (groups ZON, MPL, FLD, LOT) + M1 foundation entities.
Physical schema: `backend/app/schema.sql` (PostgreSQL, standard SQL per
DEC-006). The same model is served by the in-memory backend for local runs;
the store boundary (`backend/app/store.py`) keeps both behind one contract.

## Tenancy rule (applies to every table)

Every tenant-owned row carries `tenant_id`. Object references use
**composite foreign keys** `(tenant_id, ref_id) → (tenant_id, id)`, so the
database itself makes it impossible to reference another tenant's object.
Coded objects are unique per tenant: `UNIQUE (tenant_id, code)`.

## Foundation entities (M1)

| Table | Key | Notes |
|---|---|---|
| `tenants` | `slug` PK | Lifecycle `status`: ACTIVE / SUSPENDED. Registry is platform-scoped. |
| `users` | PK `(tenant_id, username)` | Roles: TENANT_ADMIN / OPERATOR / VIEWER. First user of a tenant is bootstrapped as TENANT_ADMIN. |
| `workspaces` | PK `(tenant_id, name)` | Tenant-isolated named workspaces. |
| `audit_log` | `seq` BIGSERIAL PK | Append-only. `scope` = platform / tenant; records actor, action, target, outcome. |

## ZON — material zones (SRS ZON-01..04)

`zones`: `code`, `name`, `area_ha`, `address`, `lat`/`lon`, `geom`
(GeoJSON polygon, WGS84 / RFC 7946 — ZON-02), `crop_group`, `season`,
`water_source`, `managing_entity`, `status`. Long-tail SRS fields live in
`data` (JSONB) until promoted to columns.

`zone_boundary_versions`: `(tenant_id, zone_id, version)` unique, `geom`,
`changed_by`, `reason` — boundary history per ZON-04 (schema ready; the
versioning write path lands with the map-editing slice).

## MPL — mother plants (SRS MPL-01..04)

`mother_plants`: `code` (unique plant code; QR payload — MPL-01), `species`,
`variety`, `scientific_name`, `origin`, `planting_year`, `lat`/`lon`,
→ `zones` (optional), `owner_manager`, recognition block (`recognition_no`,
`issuing_authority`, `valid_from`, `valid_to` — MPL-03), `status`.

`mother_plant_status_history`: status / health / pest-risk snapshots over
time (MPL-04; schema ready).

## FLD — crop plans & field events (SRS FLD-01..04)

`crop_plans`: `code`, `name`, → `zones`, → `mother_plants` (optional),
`crop_name`, `start_date`, `end_date`, `target_yield_kg`,
`status` DRAFT / RUNNING / ENDED (FLD-01).

`field_events` (append-style, no code): → `crop_plans`, → `zones`,
`event_type` (IRRIGATION / FERTILIZING / SOIL / PRUNING / PEST / INSPECTION /
HARVEST / OTHER — FLD-02), `occurred_at`, `lat`/`lon`, `actor`, `device`,
`notes` (FLD-04), `materials` JSONB — `[{name, supplier, material_lot,
quantity, unit, used_by}]` for input-lot traceability (FLD-03).

## LOT — harvest lots (SRS LOT-01..04)

`lots`: `code`, → `zones`, → `crop_plans`, `harvest_date`, `quantity`,
`unit`, `harvested_by`, `quality_grade`, `status`, `expiry_date` (LOT-01).

`lot_relations`: `(parent_lot_id, child_lot_id, relation_type SPLIT / MERGE /
TRANSFORM, quantity, unit)` — the lineage graph of LOT-02 (schema ready;
acyclicity is enforced at the application layer when the split/merge API
lands). Warehouse movements (LOT-03) and storage telemetry links (LOT-04)
are later slices on top of this graph.

## API surface (M2 slice delivered with this model)

`POST/GET /api/v1/zones`, `/mother-plants`, `/crop-plans`, `/lots`
(+ `GET /{code}`), `POST/GET /api/v1/field-events`. Writes require role
OPERATOR+; references are given as codes (`zone_code`, `plant_code`,
`plan_code`) and resolve only inside the caller's tenant
(unknown reference → `400 REF_UNKNOWN`; duplicate code → `409 CODE_EXISTS`).
Fields beyond the principal columns are accepted and stored in `data`.

## Backends

- `DATABASE_URL` unset → in-memory (local dev default; Workers beta until
  Hyperdrive is wired).
- `DATABASE_URL` set → PostgreSQL (`app/pgstore.py`); the schema is applied
  idempotently at startup. Production target per DEC-006: Neon via
  Hyperdrive, same SQL.
