# IAICT Core Platform — plain-host image (T-013).
# Runs the SAME FastAPI app that ships to Cloudflare Workers, but under
# uvicorn on a normal host with the psycopg PostgreSQL backend
# (DATABASE_URL selects it; see backend/app/store.py). The web UI files
# are served by the app itself from IAICT_PUBLIC_DIR.
FROM python:3.12-slim

WORKDIR /srv
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY deploy/cloudflare/public ./public

ENV IAICT_PUBLIC_DIR=/srv/public \
    APP_ENV=beta \
    PYTHONUNBUFFERED=1

# DATABASE_URL and PLATFORM_ADMIN_KEY are provided by the host at runtime
# (never baked into the image). PORT is injected by most hosts.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
