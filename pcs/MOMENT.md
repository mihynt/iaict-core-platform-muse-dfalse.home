# MOMENT — IAICT Core Platform

- **Revision:** 2 · **Updated:** 2026-11-02T05:20:21Z · **Phase:** DISCOVERY
- **Canonical state:** `pcs/STATE.json` (this file is a derived summary)
- **Target repository:** `mihynt/iaict-core-platform` (PUBLIC, Owner-selected 2026-11-02) — creation in progress

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

- GitHub is now connected; identity verified as **mihynt** (the account is
  `mihynt`, not `dungnt-mhy` — corrected at STATE revision 2, DEC-004).

## Next action

Create the public repository `mihynt/iaict-core-platform`, push this
checkpoint in one snapshot commit, re-read HEAD and STATE revision to
verify, then start T-003 (M1 foundation).
