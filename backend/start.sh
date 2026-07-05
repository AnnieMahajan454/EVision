#!/usr/bin/env sh
# Simple entrypoint to start the app in container
set -e

# Allow passing DATABASE_URL and CREATE_TABLES_ON_START via env
echo "Starting EVision API..."

# If gunicorn is installed (production image), use it with Uvicorn workers.
if command -v gunicorn >/dev/null 2>&1; then
	echo "Starting with gunicorn"
	exec gunicorn -k uvicorn.workers.UvicornWorker -w ${GUNICORN_WORKERS:-4} -b 0.0.0.0:8000 app.main:app
else
	exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
