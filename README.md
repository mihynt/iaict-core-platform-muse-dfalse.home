# IAICT Core Platform

Multi-tenant SaaS core platform for production, resource and value-chain management
across agriculture, forestry and aquaculture. One shared Core with per-sector
**Vertical Packs** (configuration and rule packs, no core forks).

## Status

- Phase: foundation (milestone M1 in progress)
- Requirements baseline: SRS v2.0 (document ID `IAICT/SRS-CORE/2026/V2.0`),
  maintained by the project Owner. The full requirements documents are **not**
  published in this repository; only code, project state (`pcs/`) and
  public-safe summaries are.
- Project continuity follows **PCS Chat Solo**: the canonical project state is
  [`pcs/STATE.json`](pcs/STATE.json); [`pcs/MOMENT.md`](pcs/MOMENT.md) is its
  human-readable checkpoint summary.

## Layout

| Path | Content |
|---|---|
| `backend/` | API service (Python 3.12, FastAPI) — modular monolith, tenant-isolated |
| `pcs/` | PCS project state and checkpoint moments |
| `docs/` | Public-safe design and baseline summaries |

## Quick start (backend)

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
# health: GET http://127.0.0.1:8000/health
# tenant-scoped API: send header  X-Tenant-Id: <tenant-slug>
.venv/bin/pytest
```

## Principles

- Strict tenant isolation on every tenant-scoped resource (deny by default).
- API-first: versioned OpenAPI under `/api/v1`.
- No secrets in the repository — configuration via environment only.
- Requirements change only through the delta log (`pcs/SRS_CHANGES.md`),
  never by editing the baseline.
