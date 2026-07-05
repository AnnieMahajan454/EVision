Deployment & local production-like run
------------------------------------

Quick local run with docker-compose (Postgres + backend):

```bash
# from repo root
docker-compose up --build
```

This composes a Postgres DB and the backend. The compose file sets `CREATE_TABLES_ON_START=True` so tables are created for convenience. In production, use a proper migration tool (Alembic) and set `CREATE_TABLES_ON_START=False`.

Endpoints:
- Health: `GET /health`
- Register/Login: `/api/v1/auth`
- Vehicles: `/api/v1/vehicles`
- Predictions: `/api/v1/vehicles/{vehicle_id}/predictions`

Notes:
- Configure secrets via environment variables or a secure secrets store.
- Ensure `MODELS_DIR` points to the folder containing model artifacts (default `ml/models`).
- Prefer running with a process manager (Gunicorn + Uvicorn workers) behind a reverse proxy in production.
