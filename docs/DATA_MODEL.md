# Data model (ERD) — M2 foundation + traceability standard (D-STD-01)

Baseline: SRS v2.0 (groups ZON, MPL, FLD, LOT) + M1 foundation entities.
Physical schemas: `backend/app/schema.sql` (PostgreSQL) and
`backend/app/schema_d1.sql` (SQLite port for Cloudflare D1, the live beta
backend since DEC-008); the store boundary (`backend/app/store.py`) keeps
every backend behind one contract.

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

## Traceability data standard (D-STD-01, adopted 2026-11-03)

Reference: the Owner-supplied research dossier on the Vietnamese
agri-forestry-fishery traceability data standard (33 tables + 3
materialized views; NĐ 38/2026/NĐ-CP, NQ 36/2026/NQ-CP, TCVN
11892-1:2026, TT 02/2024/TT-BKHCN, TCVN 12850:2019, GS1). Recorded as
delta **D-STD-01** in `pcs/SRS_CHANGES.md`. The standard is the platform's
data-model north star; adoption is phased so each phase lands inside the
SRS scope of a milestone. **Consolidated into the SRS baseline on
2026-11-03 (D-STD-02, DEC-010): SRS v2.1, Appendix F** (file
`IAICT_SRS_MUSE_v2.1_03-11-2026.docx`, SHA-256
`eb33a23d84e1283ee3f22ec0d502954ad45332bf6d499ec461d56c7891d6f6f1`) —
Appendix F prevails over conflicting data descriptions elsewhere in
the SRS; this file remains the implementation-level mapping.
**Foundation (DEC-011, 2026-11-03):** the dossier itself is the
ultimate source for traceability data definitions — Appendix F is
its consolidated form, and any deviation from the dossier must be
recorded as a delta in `pcs/SRS_CHANGES.md` with rationale.

### Mapping: standard → platform

| Standard table | Platform status |
|---|---|
| ENT_PRODUCTION_ZONE | **Phase 1** — `zones` extended with the PUC block (`puc_code`, `puc_status`, `sector_category`, `market_scope`, `primary_species`, `scientific_name`, `issue_date`, `issuing_authority`, `post_inspect_due_date`) |
| ENT_ACTOR_HOUSEHOLD | **Phase 1** — `actors` (subset: type, GLN, parent org, admin codes, contacts; PII encryption is a later hardening slice) |
| ENT_SPATIAL_UNIT | **Phase 1** — `spatial_units` (subset: parcel/forest identifiers, tenure, area, slope; geometry stays with the zone `geom` for now) |
| REL_ZONE_SPATIAL_UNIT | **Phase 1** — `zone_parcel_links` (`UNIQUE (tenant, zone, parcel)`, membership status, joined/left dates) |
| ENT_INPUT_INVENTORY | **Phase 1** — `input_lots` (category, substance code, VN registration, batch, PHI days, supplier → `actors`) |
| ENT_PRODUCTION_CYCLE | **Phase 1** — `crop_plans` extended (`parcel_code`, `variety_name`, `seed_origin`); `target_yield_kg` is the mass-balance ceiling |
| LOG_CULTIVATION_TREATMENT | **Phase 1** — `field_events` extended (`input_lot_code`, growth stage, target pest, dosage, quantity applied, `phi_days`, computed `safe_harvest_date`) |
| ENT_HARVEST_CATCH_LOT | **Phase 1** — `lots` extended (`farmer_code`, `parcel_code`, `weigh_slip_number`, generated `traceability_code`, `data_retention_until`); timber/VMS/eCDT specializations deferred |
| LOG_PHI_VALIDATION | **Phase 1** — `phi_validations` (system-written on every lot creation attempt) |
| SYS_USER_ACCOUNT / SYS_AUDIT_LOG | Already present — `users` / `audit_log` (M1) |
| REF_ADMIN_UNIT, REF_MARKET_REGULATION, REF_ACTIVE_SUBSTANCE_MRL, REF_CERTIFICATION_SCHEME, REF_TRANSPORT_MODE | Phase 2 — reference catalogues (substance/MRL lookups power the banned-substance cross-check) |
| REL_ZONE_MARKET_APPROVAL, LOG_FOREIGN_WARNING, LOG_ZONE_STATUS_HISTORY, REL_ENTITY_CERTIFICATION | Phase 2 — market approvals, warnings, code status history, certifications |
| LOG_PRE_HARVEST_SUPERVISION, LOG_MONITORING_DECLARATION, LOG_WATER_QUALITY_TEST, LOG_RESIDUE_TEST_DETAIL, LOG_LIVESTOCK_DECL_ITEM | Phase 2 — supervision & monitoring logs |
| ENT_LIVESTOCK_UNIT | Phase 2 — livestock sector (pilot is crop-first) |
| ENT_PACKING_PROCESSING, ENT_PACKING_INPUT_LINK, ENT_PACKAGING_UNIT_SKU | **Phase 2 — live (T-016, hardened T-017)** — `packing_lots` (facility → `actors`, PHC code, output weight, yield norm, storage type), `packing_inputs` (N-N link, `UNIQUE (tenant, packing lot, harvest lot)`), `packaging_units` (level, GTIN, SSCC, spec, count) |
| ENT_TRANSPORT_TRIP | Phase 3 |
| SYS_TRACEABILITY_RECORD, LOG_CTE_SUPPLY_CHAIN_STAGE | **Phase 2 — live (T-016, hardened T-017)** — `traceability_records` (the 10 mandatory TT 02/2024 fields, sync status) + `cte_stages` (auto-built harvest + packing stages; further stages appendable) |
| SYS_RECALL_COMPLIANCE | Phase 3 |
| VW_PRODUCTION_ZONE_METRICS, VW_CYCLE_MASS_BALANCE, VW_PACKING_MASS_BALANCE | Phase 1 partial — the cycle mass-balance rule is enforced at lot creation (below); the packing mass-balance rule is enforced at traceability-record issuance (phase 2); reporting views land later |

### Phase-1 enforcement rules (application layer, all backends)

- **PHI gate.** A field event with a PHI (its own `phi_days`, or inherited
  from its input lot) stores `safe_harvest_date = occurred date + phi_days`.
  Creating a harvest lot for a plan whose events set a later safe date is
  rejected `400 PHI_VIOLATION`; every attempt (passed or blocked) is
  written to `phi_validations` (`LOG_PHI_VALIDATION`).
- **Mass balance.** A lot that would push the plan's cumulative harvested
  quantity above `target_yield_kg` is rejected
  `400 MASS_BALANCE_EXCEEDED` (VW_CYCLE_MASS_BALANCE rule, TCVN
  11892-1:2026).
- **Traceability code.** On creation a lot is stamped
  `traceability_code = plan_code ∥ zone PUC (or zone code) ∥ lot code ∥
  harvest_date` — the TT 02/2024 concatenation of product trace code,
  location trace code, batch/lot number and event time.
- **Retention.** `data_retention_until = expiry_date + 12 months`, or
  `harvest_date + 12 months` for fresh produce without an expiry date
  (TT 17/2021 fallback; the 24-month frozen/processed branch lands with
  the packing chain).

API surface additions: `POST/GET /api/v1/actors`, `/spatial-units`,
`/zone-parcel-links` (create/list), `/input-lots`, `GET /phi-validations`,
under the same tenancy/role rules as the other production objects.

Phase-2 additions (T-016, prepared 2026-11-03, pending deploy):
`POST/GET /api/v1/packing-lots`, `/packing-inputs` (create/list),
`/packaging-units`, `/traceability-records`, `/cte-stages`. Rules:
a harvest lot cannot be allocated to packing beyond its harvested
quantity (`400 HARVEST_LOT_OVER_ALLOCATED`); issuing a traceability
record runs the packing mass-balance gate — packed output must not
exceed linked inputs × yield norm (`400 PACKING_MASS_BALANCE_EXCEEDED`,
the VW_PACKING_MASS_BALANCE rule) — then completes the record from the
chain (product, facility name/address, event time), stamps its
traceability code (GTIN ∥ PHC ∥ packing lot ∥ event time) and retention
date (expiry + 12 months; frozen/processed + 24 months from packing),
and auto-writes the CTE stages (one harvest stage per input lot,
located at the source zone's PUC, plus the packing stage). Records
start as `PENDING_SYNC` toward the national portal (TT 02/2024); the
portal push itself is an integration slice, not part of T-016.

T-017 hardening (2026-11-03, from the two-pass review of T-016):
packing-input links must name both ends (`400 REF_REQUIRED` — a
dangling link previously crashed issuance with a 500 after the record
was written); issuance requires a packaging unit
(`TRACEABILITY_UNIT_REQUIRED`) linked to a packing lot
(`PACKING_CHAIN_INCOMPLETE`) that declares output weight and yield
norm (`PACKING_DATA_INCOMPLETE` — the mass-balance gate can no longer
be skipped); traceability codes are unique per tenant (application
check `409 TRACEABILITY_CODE_EXISTS` + partial unique index
`ux_traceability_records_code`); fresh-produce retention now anchors
to the latest input harvest date + 12 months per the dossier's
fallback case (2). The issue form collects the product image URL
(mandatory field 2 of TT 02/2024) and warns on records missing it.

Note on the D1 upgrade path: databases created before phase 1 gain the
new tables from `schema_d1.sql` and the new columns via `ALTER TABLE`
(plain columns — SQLite cannot add FKs by ALTER; reference resolution is
enforced by the store layer, fresh databases carry the full composite
FKs).

## Backends

- `DATABASE_URL` unset → in-memory (local dev default).
- `DATABASE_URL` set → PostgreSQL (`app/pgstore.py`); the schema is applied
  idempotently at startup.
- Workers beta → Cloudflare D1 (`app/d1store.py`, DEC-008) with the
  PostgreSQL backends kept green as the exit path.
