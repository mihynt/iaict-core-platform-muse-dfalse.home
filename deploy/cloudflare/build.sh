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
# --- Web UI assets (audit T-021, pack P1) ---
# Stamp JS/CSS with a content hash so the edge can cache them immutably;
# index.html is rewritten to reference the stamped names. wrangler serves
# public_dist directly (the Worker only runs first for API routes).
STAMP=$(cat public/app.js public/styles.css | sha256sum | cut -c1-10)
rm -rf public_dist
mkdir -p public_dist
sed -e "s|/styles\.css|/styles.$STAMP.css|" -e "s|/app\.js|/app.$STAMP.js|" \
  public/index.html > public_dist/index.html
cp public/app.js "public_dist/app.$STAMP.js"
cp public/styles.css "public_dist/styles.$STAMP.css"
{
  echo "/app.$STAMP.js"
  echo "  Cache-Control: public, max-age=31536000, immutable"
  echo "/styles.$STAMP.css"
  echo "  Cache-Control: public, max-age=31536000, immutable"
} > public_dist/_headers
echo "UI assets assembled: public_dist/ (stamp $STAMP)"

echo "Deploy with: uv run pywrangler deploy"
