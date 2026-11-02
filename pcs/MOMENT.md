# MOMENT — IAICT Core Platform

- **Revision:** 15 · **Updated:** 2026-11-02T05:20:21Z · **Phase:** DISCOVERY
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

- **Stuck-login root cause fixed (2026-11-02):** the sign-in overlay
  uses `display:flex`, which overrode the `hidden` attribute — after a
  successful sign-in the overlay never disappeared and the button sat on
  "connecting" forever. Global `[hidden]{display:none !important}` rule
  added; tenant picker added to the sign-in screen (platform key typed
  in the form); 20s request timeout so stalls surface as errors.
  Deployed + verified live. T-010 TECH_DONE.


- **Login fix LIVE (2026-11-02):** the new sign-in screen is deployed
  and verified at the canonical URL (page grew 3310 -> 3918 bytes with
  the account picker; the login page's own request returns beta-pilot's
  Pilot Admin account). T-009 TECH_DONE. Sign-in is now: type tenant,
  tap your account card, done — with remember-me on by default.


- **Login fix built (2026-11-02):** the Owner could not sign in, so the
  sign-in screen now lists the tenant's accounts as tappable cards
  (verified live: beta-pilot returns admin / Pilot Admin), validates
  before entering with inline errors, normalizes the tenant slug, adds a
  remember-me checkbox (localStorage vs sessionStorage) and defensive
  storage with an in-memory fallback. UI-only change; backend tests
  green. Deploy pending the Owner's API token.


- **Web UI LIVE (2026-11-02):** deployed with a fresh Owner-issued API
  token (transient use only). Verified at the canonical URL: `/` serves
  the UI (200 text/html), CSS/JS with correct content types, `/health`
  unchanged, beta-pilot data intact, unknown API paths still JSON 404.
  T-008 / F-005 TECH_DONE. First run: tenant `beta-pilot`, actor `admin`.


- **Web UI built (2026-11-02):** mobile-first SPA in
  `deploy/cloudflare/public/` (dashboard, zones, plants, plans + field
  journal, lots, users + audit, tenant admin, settings), served by the
  Worker via the assets binding + guarded catch-all. All backend tests
  green in the three store modes. **Deploy pending**: wrangler needs the
  Owner's Cloudflare API token again (tokens are never stored; the
  session copy was lost on an environment restart).


- **Beta address renamed (2026-11-02):** the Owner changed the account
  subdomain — canonical URL is now
  https://iaict-core-platform.mihy.workers.dev (old address no longer
  resolves; data in Neon untouched, beta-pilot records verified at the
  new address). The Owner also set their own `PLATFORM_ADMIN_KEY` secret
  (active: wrong key -> 401).


- **Beta is DURABLE (2026-11-02):** the Owner created the Hyperdrive
  config `iaict-neon` in the dashboard; the binding is live and `/health`
  reports `storage: postgresql-hyperdrive`. Verified end-to-end on the
  live URL with a temporary platform secret (deleted after): tenant
  `beta-pilot` created in one request, then admin bootstrap, zone Z-01,
  plant MPL-001 and plan PLAN-2026 in later requests — all persisted in
  Neon and readable back, audit trail complete. One transient 500 led to
  switching WorkerPgStore to a fresh connection per operation
  (Cloudflare's prescribed pattern); repeated checks are clean. The
  in-memory era of the beta is over; next product stage is T-005 (M3a
  day-90 IoT gate).


- **Neon wired, one dashboard step left (2026-11-02):** the Owner's Neon
  project (Singapore, PG 18.6) is verified — schema applied (12 tables),
  cross-tenant FK rejection reproduced on Neon itself. The Workers store
  backend is built on **pg8000** (Cloudflare-supported for Hyperdrive;
  asyncpg's wheel CDN is unreachable from this build VM, and direct TLS
  to Neon fails in the Python runtime — Hyperdrive's plaintext local leg
  is the sanctioned answer). Suite: 31/31 in all three store modes. The
  beta already runs the new build and reports `storage: memory` via
  `/health`; it flips to durable `postgresql-hyperdrive` as soon as the
  Hyperdrive config exists (Owner creates it in the dashboard — the API
  token lacks Hyperdrive permission) and the binding is uncommented.


- **T-004 TECH_DONE (2026-11-02):** real SQL. ERD (`docs/DATA_MODEL.md`)
  grounded in the SRS v2.0 group texts; 12-table PostgreSQL schema with
  composite tenant foreign keys — a cross-tenant reference is rejected by
  the database itself (verified by negative INSERT test). `PgStore` sits
  behind the same store boundary (`DATABASE_URL` selects it; in-memory
  remains the default; psycopg is lazy-imported so the Workers bundle is
  unaffected). CRUD APIs for zones / mother-plants / crop-plans /
  field-events / lots with tenant-scoped code references and audit.
  Evidence: 31/31 tests pass on a real PostgreSQL 18.6, 30+1 skip in
  in-memory mode. Next: Neon project (Owner) -> Hyperdrive -> beta redeploy
  with durable state.


- **Beta is LIVE (2026-11-02):** https://iaict-core-platform.iaict-coreplatform-mhy.workers.dev
  — the M1 API running as a Cloudflare Python Worker on the Owner's account.
  Verified live: `/health` 200 (`env: beta`), deny-by-default 400/403/503,
  tenant creation 201 with a temporary platform secret (deleted after the
  check; platform admin stays disabled until the Owner sets their own
  `PLATFORM_ADMIN_KEY` secret). Packaging lessons recorded in the runbook:
  deploy via `uv run pywrangler deploy`; Workers expose variables/secrets
  through the ASGI scope `env`, not `os.environ` (the app reads both).
  Known limit, verified live: in-memory state is per-isolate and not shared
  between requests — multi-request flows arrive with T-004 persistence.


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
