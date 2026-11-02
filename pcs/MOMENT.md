# MOMENT — IAICT Core Platform

- **Revision:** 5 · **Updated:** 2026-11-02T05:20:21Z · **Phase:** DISCOVERY
- **Canonical state:** `pcs/STATE.json` (this file is a derived summary)
- **Repository:** [`mihynt/iaict-core-platform-muse-dfalse.home`](https://github.com/mihynt/iaict-core-platform-muse-dfalse.home) (PUBLIC) — live; initial checkpoint commit `2b354557` verified by read-back

## Where the project stands

- Requirements baseline locked for development: **SRS v2.0**
  (`IAICT/SRS-CORE/2026/V2.0`, SHA-256 `3a5d21e1…66fe1`), derived from SOW
  v2.2.0-R21. Full documents stay off-repo (internal); see
  `docs/REQUIREMENTS_BASELINE.md`.
- Foundation slice built and verified **locally**: FastAPI service with
  `/health`, deny-by-default tenant context (`X-Tenant-Id`) and tenant-isolated
  workspaces. Tests: **7/7 passed** (pytest, 2026-11-02).
- PCS validator (`tools/pcs_solo.py verify`): **verified revision 1** at the initial checkpoint.
  Local git checkpoint: initial commit on branch `main` (14 files).
- Milestone plan (from SRS): M1 tenancy/identity/audit foundation → M2 data
  model & core production objects → M3a day-90 IoT gate → M5 pilot go-live →
  M7 commercial readiness.

## Status note

- GitHub is connected; identity verified as **mihynt** (the account is
  `mihynt`, not `dungnt-mhy` — corrected at STATE revision 2, DEC-004).
- The Owner created the repository as
  `mihynt/iaict-core-platform-muse-dfalse.home` (the Muse app has no
  repository-creation permission). The initial checkpoint was pushed as
  commit `2b354557` and verified: HEAD and `pcs/STATE.json` revision 2 read
  back from GitHub match this project.

## Latest progress

- **DEC-006 (Owner, 2026-11-02): beta hosting = Cloudflare Workers Free +
  Neon PostgreSQL Free via Hyperdrive**, under binding portability rules
  (no platform-proprietary APIs in the core; standard SQL only; local DB
  for daily development). Packaging is ready in `deploy/cloudflare/` with
  the runbook `docs/DEPLOY_CLOUDFLARE_NEON.md`; the adapter wiring was
  verified locally end-to-end. Actual deployment waits for the Owner's
  Cloudflare and Neon accounts.


- **T-003 (M1 foundation) TECH_DONE:** platform tenant registry with
  lifecycle (ACTIVE/SUSPENDED), registry-aware tenant guard (unknown or
  suspended tenants denied), tenant users with a bootstrap-admin rule and
  role guards (VIEWER < OPERATOR < TENANT_ADMIN), and an append-only audit
  log with per-tenant views. Verified by **pytest 24/24** (2026-11-02).

## Next action

T-004 (M2): data model (ERD) for the core production objects
(ZON/MPL/FLD/LOT) and a persistence layer that replaces the in-memory
stores behind the same API contracts.
