# MOMENT — IAICT Core Platform

- **Revision:** 40 · **Updated:** 2026-11-03T16:30:22Z · **Phase:** DISCOVERY
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

- **Full-project audit (2026-11-03, T-021 TECH_DONE):**
  tables/fields vs the standard (concept-level), backend, UI and
  measured performance. Sound core (suite 47 green, tenant
  isolation intact); genuine gaps: `synced_at` missing on
  traceability records, no last-treatment link on PHI validations,
  no update/delete endpoints, no list pagination, and 5 API
  resources with no UI (spatial units, parcel links, input lots,
  PHI validations, CTE stages). Slow loads are architectural:
  every request — static assets included — runs the Python
  Worker (assets served max-age=0), and the dashboard costs 7
  invocations. Fix plan P1/P2/P3 recorded in the audit minutes.
- **Five-round review loop over SRS v2.1.1 (2026-11-03, T-020
  TECH_DONE):** dossier-as-root, baseline SRS, implementation,
  internal consistency, fresh-eyes — 4 findings (1 medium:
  DATA_MODEL phase labels; 3 minor in the SRS), all fixed and
  re-verified. Final v2.1.1 hash `16fdbdf8…`, 156 pages.
- **SRS v2.1.1 errata — tables follow the dossier as root
  (2026-11-03, T-019 TECH_DONE, DEC-012):** the Owner caught that
  TX-01/TX-03 duplicated pre-existing requirements (ZON-09/CMP-10
  and FLD-16/FLD-17). Appendix F was corrected the same day: F.2
  now reproduces the dossier's own 33 tables + 3 views with
  cross-references to pre-existing SRS requirements; F.3 cites
  each rule's source dossier table; TX-01/TX-03 are narrowed to
  the dossier's true additions. Recorded gap: phase-1 PHI checks
  run at plan scope and do not yet meet FLD-17's per-parcel /
  multi-parcel semantics — phase-3 completion scope.
- **Dossier designated the foundation (2026-11-03, DEC-011):**
  the traceability-standard dossier is now the foundational
  baseline for the platform's data standard, with an explicit
  precedence stack — the dossier itself (hash-pinned, reference
  copy kept outside the public repo) → SRS v2.1 Appendix F as its
  consolidated normative form → implementation. Any deviation must
  be recorded as a delta with rationale (D-STD-03); Q-TX-01..03
  are the only sanctioned open points.
- **Standard consolidated into the SRS (2026-11-03, T-018
  TECH_DONE, DEC-010):** SRS v2.1 is built — the traceability data
  standard now lives inside the SRS as **Appendix F** (full entity
  mapping with live phase statuses, rule requirements TX-01..TX-12,
  the TT 02/2024 mandatory fields, the retention fallback, open
  decisions Q-TX-01..03) with a §1.4 precedence clause. No existing
  requirement changed (385/385 IDs machine-verified); the document
  was rendered and its TOC page numbers re-measured (150 pages).
  SRS v2.1 stays a draft pending IAICT approval (INT-01..06).
- **Phase-2 hardening — live (2026-11-03, T-017 TECH_DONE):** the
  five fix groups from the two-pass review of T-016 are deployed
  (Worker `75f69cfb`): both-ends-required packing links, an
  unskippable mass-balance gate, unit-required issuance, unique
  traceability codes (409 + D1 unique index), product-image capture
  in the issue form, and harvest-anchored retention for fresh
  produce. The first T-017 build briefly took the beta's write
  paths down (a self-recursion in D1 schema setup); live write
  probes caught it before any checkpoint, it was root-caused,
  fixed, and covered by a new schema-guard regression test. Suite
  green in all four store modes (47+2 / 48+1 / 48 / 48); browser
  test passed. The frozen-retention interpretation remains an
  open Owner decision.
- **Traceability standard phase 2 — live (2026-11-03, D-STD-01 /
  T-016 TECH_DONE):** the packing chain lands on the beta: packing
  lots at PHC facilities, N-N harvest-input links with an
  over-allocation guard, SKU packaging units, and national
  traceability records whose issuance is gated by the packing
  mass-balance rule (output ≤ inputs × yield norm) and which
  auto-build their CTE stage chain back to each source harvest lot
  and zone PUC. New **Đóng gói** UI view with a one-flow
  "Cấp mã truy xuất" action. Suite green in all four store modes
  (42+1 / 42+1 / 43 / 43); D1 upgraded in place (5 new tables,
  beta-pilot intact), Worker `146e24f2`, browser test passed
  (dashboard 2/1/1/1, packing view + form verified, reload clean).
  Records wait as `PENDING_SYNC`; the national-portal push is a
  later integration slice.
- **Traceability data standard, phase 1 — live (2026-11-03,
  DEC-009 / D-STD-01 / T-015 TECH_DONE):** the Owner supplied the
  national traceability data-standard research (33 tables + 3 views)
  and directed its adoption. Phase 1 lands the crop-chain core: PUC
  identity block on zones; new entities `actors`, `spatial_units`,
  `zone_parcel_links`, `input_lots`, `phi_validations`; field events
  compute a safe-harvest date from the input lot's PHI; harvest lots
  link farmer + parcel + weigh slip and are gated by the PHI check
  (blocked attempts logged) and the cycle mass-balance ceiling, and
  carry a generated traceability code + data-retention date. Suite
  green in all four store modes (37+1 / 37+1 / 38 / 38). The live D1
  database was upgraded in place (all 5 new tables present,
  beta-pilot data intact), Worker `871beb1e`, browser test passed
  (dashboard 2/1/1/1, new form fields present, reload clean). The
  full 33-table mapping incl. phase 2 lives in `docs/DATA_MODEL.md`;
  the SRS delta is D-STD-01 in `pcs/SRS_CHANGES.md`.
- **D1 adopted — the intermittency is resolved (2026-11-03,
  DEC-008 / T-014 TECH_DONE):** the Owner chose D1 after the spike.
  The store interface went async; a new D1Store runs the SQLite port
  of the 12-table schema (composite FKs verified enforced by D1
  itself). Suite green in all four modes (memory / D1-shim /
  psycopg / pg8000). Live on production D1 `iaict-core`: probes
  **20/20 + 48/48** (Postgres path: 8/20, 19/48), tail cpuTime
  median **42ms** (was ~1,241ms). Browser test: dashboard loads
  completely on the FIRST try — 2/1/1/0, no warnings, reload clean.
  T-013 cancelled as superseded; its Docker/Fly/Render packaging
  stays in the repo as the exit path, next to the PostgreSQL stores.

- **D1 spike measured — the failure classes disappear (2026-11-02,
  T-014 candidate):** a throwaway Python Worker on the same account
  serving the real read pattern (tenant lookup + list query) from D1
  scored sequential **20/20** and parallel **48/48** (Postgres path:
  8/20 and 19/48); tail showed 68/68 ok, cpuTime median **26ms** vs
  ~1,241ms, no hang-cancellations, no exceededCpu. D1 is therefore
  evidence-backed as a fix on Cloudflare free — at the price of an
  async store refactor, a SQLite schema port and a DEC-006 amendment
  (PostgreSQL stores + Supabase stay as the exit). Owner decision
  pending between T-014 (D1) and T-013 (plain host).

- **Database exonerated; runtime relocation prepared (2026-11-02,
  DEC-007 / T-013):** the beta now runs on Supabase (Singapore) via a
  new Hyperdrive config; beta-pilot was rebuilt from an API snapshot
  with a temporary platform secret (deleted right after — the Owner
  had forgotten their key; platform admin is disabled until they set
  a fresh one). Same-probe re-measurement: sequential 8/20, parallel
  19/48 — the failure rate did NOT improve with the database switch;
  latency did (5-6s vs 7-10s). `wrangler tail` shows why: 4 of 14
  sampled requests were canceled by the runtime's hang detector and 1
  exceeded CPU; successful requests burn ~1.2-1.9s CPU each — the
  Python Workers runtime (Pyodide + synchronous pg8000) is the
  bottleneck, not the DB. T-012 closed TECH_DONE with that partial
  outcome recorded. Plain-host packaging is ready (Dockerfile,
  fly.toml, render.yaml; the app serves the UI itself off-Workers)
  and smoke-proven locally: list calls ~2ms under uvicorn + psycopg
  with identical code. Waiting on the Owner's host choice.


- **Intermittency investigated, fix built (2026-11-02, T-012):** the
  Owner chose investigation over switching to Supabase. Controlled live
  measurement: sequential success only 8/20, dashboard-parallel 15/48,
  successful DB calls 7-10s warm or cold — Neon scale-to-zero ruled out
  as the main cause; the cost sits in per-request protocol chatter
  (2 store sessions per list, ping + COMMIT each, full schema DDL
  replayed by every fresh isolate) plus a UI bug: the GET retry never
  fired for network-level failures. Fixes: UI retry 3 attempts with
  backoff covering network errors; WorkerPgStore tenant/user cache
  (30s, per isolate), optimistic reads with one self-healing retry,
  one-query schema probe. Suite green in all three store modes
  (30+1 skip / 31/31 / 31/31). **Deploy pending** the Owner's
  Cloudflare API token; live re-measurement + browser test follow.


- **Dashboard load failures fixed (2026-11-02):** the first mandated
  browser test caught the dashboard failing under parallel load
  (Cloudflare 1102 + a Hyperdrive prepared-statement bug, SQLSTATE
  26000, found in wrangler tail). Fixes: per-isolate connection reuse
  with health-check, one explicit transaction per store operation,
  conflict handling moved outside the session, UI GET-retry + per-section
  loading. Post-fix browser re-test PASSED (stats 2/1/1/0, no error
  states). T-011 TECH_DONE. A labeled test zone Z-TMP remains in
  beta-pilot (no delete endpoint yet).


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

Owner reviews the hardened packing/traceability slice and decides
the frozen-retention interpretation, then chooses: D-STD-01 phase 3
(reference catalogues, market approvals, monitoring logs, transport
+ recall) and the national-portal sync integration, with T-006 — or
T-005 (M3a day-90 IoT gate).
