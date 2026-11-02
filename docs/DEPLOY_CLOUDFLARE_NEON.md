# Runbook: beta deployment on Cloudflare Workers + Neon PostgreSQL

Decision: **DEC-006** (`pcs/STATE.json`). Beta hosting is Cloudflare Workers
(Free) with Neon PostgreSQL (Free) reached through Hyperdrive (Free). The
stack is deliberately portable: it can move to a VPS or AWS/Azure/GCP later
without application changes.

## Portability rules (binding for all code)

1. Only `deploy/cloudflare/src/entry.py` may know about Cloudflare. Core
   modules never import Cloudflare bindings (no D1/KV/Durable Objects in
   business logic).
2. Persistence goes through the store boundary with standard SQL and only
   widely-available PostgreSQL extensions. No Neon/Supabase platform extras
   (their Auth/Storage/Realtime, branching in production paths).
3. The application is stateless per request; all durable state lives in
   PostgreSQL. Daily development and automated tests run against a **local**
   database — Neon hours are spent only by the shared beta environment.

## Prerequisites (Owner accounts, both free, no card)

- Cloudflare account (sign up with GitHub is fine).
- Neon account (sign up with GitHub is fine).
- Local tools: Node.js + Wrangler (`npm install -g wrangler` or use `npx
  wrangler@latest`), and `uv` (Wrangler uses it to vendor Python packages).

## Step 1 — Neon project

1. Create a project (suggested name `iaict-beta`), PostgreSQL **17**, region
   **Singapore (ap-southeast-1)** for lowest latency from Vietnam.
2. Keep the free defaults: compute min **0.25 CU**, scale-to-zero after
   5 minutes (fixed on the Free plan). One project per environment
   (beta / staging / dev) — each gets its own 100 CU-hours/month.
3. From the project dashboard, copy the **direct** connection string. Treat
   it as a secret: it goes into Hyperdrive configuration (Step 2), never
   into this repository.

## Step 2 — Hyperdrive configuration

```bash
wrangler login
wrangler hyperdrive create iaict-beta-db --connection-string "<NEON DIRECT CONNECTION STRING>"
```

Note the returned configuration `id`, then uncomment the `hyperdrive`
block in `deploy/cloudflare/wrangler.jsonc` and fill in that id. (The
binding is consumed by the M2 persistence layer, T-004; the M1 API does not
read it yet.)

## Step 3 — Secrets

```bash
cd deploy/cloudflare
wrangler secret put PLATFORM_ADMIN_KEY   # choose a strong value; it guards /api/v1/platform/*
```

## Step 4 — Build and deploy

```bash
./build.sh
uv run pywrangler deploy
```

Use **pywrangler**, not plain `wrangler deploy`: pywrangler vendors
Pyodide-compatible wheels (a hand-rolled `uv pip install` produces native
wheels whose `pydantic_core` cannot load under Pyodide). The project
layout follows Cloudflare's official FastAPI guide — entrypoint at
`src/entry.py`, `workers-py`/`workers-runtime-sdk` in the pyproject
`dev` dependency group, `requires-python >= 3.13`.

First live deployment (2026-11-02):
`https://iaict-core-platform.iaict-coreplatform-mhy.workers.dev`
— verified: `/health` 200 (`env: beta`), deny-by-default responses
(400 TENANT_REQUIRED, 403 TENANT_UNKNOWN, 503 PLATFORM_DISABLED), and
tenant creation (201) with a platform key held as a Worker secret.
Note: on Workers, variables/secrets arrive through the ASGI scope `env`
binding, not `os.environ`; the app reads both (see `backend/app/deps.py`).

## Step 5 — Verify the deployment

```bash
curl https://iaict-core-platform.<your-subdomain>.workers.dev/health
# {"status":"ok",...}

curl -X POST https://iaict-core-platform.<your-subdomain>.workers.dev/api/v1/platform/tenants \
  -H "X-Platform-Key: <your key>" -H "Content-Type: application/json" \
  -d '{"slug":"beta-tenant","name":"Beta tenant"}'
# 201 with status ACTIVE
```

## Known limits at this stage

- Persistence status (2026-11-02): **durable**. The Hyperdrive config
  `iaict-neon` (id in `wrangler.jsonc`) points at the Neon project; the
  Worker store backend (`app/workerstore.py`, pg8000) binds it from the
  first request's env and `/health` reports `storage:
  postgresql-hyperdrive`. Multi-request flows were verified live end to
  end, and the seed records (tenant `beta-pilot`, zone Z-01, plant
  MPL-001, plan PLAN-2026) are stored in Neon. WorkerPgStore opens a
  fresh connection per operation — the pattern Cloudflare prescribes for
  Hyperdrive; a cached per-isolate connection produced one transient 500
  during verification. The in-memory fallback remains only for runs
  without the binding, and `/health` always says which mode is active.
- Workers Free allows 100,000 requests/day; Hyperdrive Free 100,000
  queries/day — ample for beta, monitored in the Cloudflare dashboard.
- Neon Free: 100 CU-hours/month per project. At the 0.25 CU minimum that is
  roughly 400 awake-hours; local development (rule 3) keeps the beta
  project far below the cap.

## Exit path (when moving to VPS / AWS / Azure / GCP)

1. Run the same `backend/app` under uvicorn or as a container — no code
   changes; the Cloudflare adapter file is simply not used.
2. Move data with `pg_dump` from Neon and `pg_restore` into the target
   PostgreSQL (same major version). Application user accounts live in
   application tables and move with the data.
3. Repoint DNS. Estimated effort at beta data volumes: hours, dominated by
   verification.
