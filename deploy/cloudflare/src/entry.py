"""Cloudflare Python Workers entrypoint — a thin adapter.

The application itself (the `app` package, copied next to this file by
build.sh) is a standard ASGI FastAPI application. It also runs unchanged
under uvicorn on any plain host (the PostgreSQL store backends are the
documented exit path, DEC-008).

Setting IAICT_BACKEND=d1 here selects the lazy D1 store backend
(T-014): on the first request, the app binds the D1 database from the
request env and serves durable state from Cloudflare's SQLite. Without
the binding it falls back to in-memory storage, which /health reports.
Set IAICT_BACKEND=hyperdrive instead to roll back to PostgreSQL via
Hyperdrive (binding must be restored in wrangler.jsonc).
"""
import os

os.environ.setdefault("IAICT_BACKEND", "d1")

from workers import asgi

from app.main import app

Default = asgi.entrypoint(app)
