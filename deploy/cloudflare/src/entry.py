"""Cloudflare Python Workers entrypoint — a thin adapter (DEC-006).

The application itself (the `app` package, copied next to this file by
build.sh) is a standard ASGI FastAPI application. It runs unchanged under
uvicorn on any VPS or cloud (AWS/Azure/GCP). Only this file knows that
Cloudflare exists; nothing in `app` imports Cloudflare APIs.
"""
from workers import asgi

from app.main import app

Default = asgi.entrypoint(app)
