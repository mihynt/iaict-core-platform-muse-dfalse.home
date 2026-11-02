#!/usr/bin/env bash
# Assemble the Worker source tree: copy the backend `app` package next to the
# Cloudflare entrypoint so the deployed bundle contains the whole ASGI app.
# The copy is a build artifact (git-ignored); the single source of truth for
# application code stays in backend/app.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf src/app
cp -r ../../backend/app src/app
find src/app -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "Worker source assembled: src/entry.py + src/app/"
echo "Next: wrangler dev   (local smoke test)"
echo "  or: wrangler deploy (publish to your Cloudflare account)"
