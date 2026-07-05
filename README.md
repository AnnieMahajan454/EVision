# EVision - Connected Electric Vehicle Analytics Platform

EVision is a demo production-quality portfolio project showcasing a FastAPI backend, SQL database, telemetry ingestion, and ML-powered predictions for electric vehicles (battery health, driving range, charging recommendations). The project demonstrates clean architecture, training pipelines, and a simple frontend-ready API surface.

This README covers local development and deployment notes.

## Key Features
- User authentication (JWT)
- Vehicle management (CRUD)
- Telemetry ingestion (batched)
- ML models: battery health and driving range prediction (scikit-learn)
- Prediction persistence and history

## Repo structure (top-level)
- `backend/` — FastAPI app, routers, services, models, and database code
- `ml/` — datasets, training scripts, prediction wrappers, saved model artifacts
- `frontend/` — (UI placeholder)

## Quick start — Local development (recommended)

1. Copy `.env.example` to `.env` and edit as needed.

2. Install Python dependencies (recommended in a venv):

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # or .\.venv\Scripts\activate on Windows
pip install -r requirements.txt
```

3. (Optional) Train the example ML model(s):

```bash
# from repo root
python -m ml.training.battery_health_train
python -m ml.training.range_train
```

4. Start the FastAPI app for development (sets PYTHONPATH so `ml` is importable):

```bash
# from repo root
$Env:PYTHONPATH = '.'; cd backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

5. Open docs at `http://127.0.0.1:8000/docs`.

## Quick start — Docker (local production-like)

```bash
docker-compose up --build
```

This brings up Postgres + backend. The compose file configures `CREATE_TABLES_ON_START=True` for convenience (creates tables automatically). In production you should use migrations instead of this flag.

## Environment
- Edit `.env` or set environment variables. See `.env.example` for keys: `DATABASE_URL`, `JWT_SECRET_KEY`, `CREATE_TABLES_ON_START`, `MODELS_DIR`, etc.

## Models
- Model artifacts live by default in `ml/models`. Set `MODELS_DIR` environment variable to change the path.

## Production notes
- Use Alembic for DB migrations (not included yet) and disable `CREATE_TABLES_ON_START` in production.
- Run with Gunicorn + Uvicorn workers behind a reverse proxy (NGINX).
- Store model artifacts in a model registry or object storage and load them at startup.

## Tests & CI
- Add unit tests to `backend/tests/` and a CI workflow to run linters, mypy/ruff, and tests.
