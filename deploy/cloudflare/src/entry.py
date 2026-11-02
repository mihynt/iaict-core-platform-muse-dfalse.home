"""Cloudflare Python Workers entrypoint — a thin adapter (DEC-006).

The application itself (the `app` package, copied next to this file by
build.sh) is a standard ASGI FastAPI application. It runs unchanged under
uvicorn on any VPS or cloud (AWS/Azure/GCP). Only this file knows that
Cloudflare exists; nothing in `app` imports Cloudflare APIs.

Setting IAICT_BACKEND=hyperdrive here selects the lazy Hyperdrive store
backend: on the first request, the app binds the Hyperdrive configuration
from the request env and serves durable PostgreSQL state (Neon). Without
the binding it falls back to in-memory storage, which /health reports.
"""
import os

os.environ.setdefault("IAICT_BACKEND", "hyperdrive")

from workers import asgi

from app.main import app

Default = asgi.entrypoint(app)
