#!/usr/bin/env sh
# Simple entrypoint to start the app in container
set -e

# Allow passing DATABASE_URL and CREATE_TABLES_ON_START via env
echo "Starting EVision API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
