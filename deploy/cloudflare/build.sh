#!/usr/bin/env bash
# Assemble the Worker source tree in the layout of Cloudflare's official
# Python/FastAPI guide: entrypoint at src/entry.py with the application
# package beside it at src/app/. Dependency vendoring (Pyodide-compatible
# wheels) is done by pywrangler at deploy time — NOT by hand.
# The src/app copy is a build artifact (git-ignored); the single source of
# truth for application code stays in backend/app.
set -euo pipefail
cd "$(dirname "$0")"
rm -rf src/app
mkdir -p src
cp -r ../../backend/app src/app
find src/app -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
echo "Worker source assembled: src/entry.py + src/app/"
echo "Deploy with: uv run pywrangler deploy"
