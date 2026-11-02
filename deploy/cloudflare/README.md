# Cloudflare deployment (beta)

Packaging for running the IAICT Core Platform API as a **Cloudflare Python
Worker** with **Neon PostgreSQL** via Hyperdrive — the beta hosting stack
chosen in DEC-006 (see `pcs/STATE.json`).

- `src/entry.py` — the only Cloudflare-specific file (thin ASGI adapter).
- `wrangler.jsonc` — Worker configuration (no secrets in this file).
- `pyproject.toml` — Python dependencies vendored at deploy time.
- `build.sh` — copies `backend/app` into `src/app` before deploy.

Full step-by-step runbook: `docs/DEPLOY_CLOUDFLARE_NEON.md`.

Portability rule (DEC-006): application code must never import Cloudflare or
Neon/Supabase platform APIs. The same `app` package runs under uvicorn on a
VPS/AWS/Azure/GCP unchanged; the database is standard PostgreSQL, movable
with `pg_dump`/`pg_restore`.
