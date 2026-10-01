# EVision: Connected Vehicle Analytics Platform

[![CI](https://github.com/AnnieMahajan454/EVision/actions/workflows/ci.yml/badge.svg)](https://github.com/AnnieMahajan454/EVision/actions/workflows/ci.yml)

EVision collects telemetry from a fleet of connected electric vehicles, stores it in **PostgreSQL** through a **FastAPI** ingestion service, and turns it into **Power BI** dashboards for battery health monitoring, range prediction and charging cost optimisation.

The demo fleet is 20 Indian EVs (Tata Nexon/Tiago/Punch, Mahindra XUV400, MG ZS EV, Hyundai Ioniq 5, BYD Atto 3). It covers commuters, field-sales cars and ride-hailing cabs across six cities, with 180 days of minute-level telemetry (560k readings) and 2,633 charging sessions.

```mermaid
flowchart LR
    SIM["Fleet simulator<br/>(telematics units)"] -- "REST / JSON batches" --> API
    subgraph Backend
        API["FastAPI<br/>auth · ingestion · predictions<br/>charging recommendations"]
        DB[("PostgreSQL<br/>raw tables")]
        VIEWS[["analytics schema<br/>star-schema SQL views"]]
        API --> DB --> VIEWS
    end
    VIEWS --> ML["ML pipeline<br/>scikit-learn"]
    ML -- "batch predictions" --> DB
    ML -- "model artifacts" --> API
    VIEWS --> PBI["Power BI<br/>4-page report"]
```

## What it does

| Area | Implementation |
|---|---|
| **Telemetry ingestion** | `POST /vehicles/{id}/telemetry` accepts batches of up to 2,000 readings. These go in with a single `INSERT … ON CONFLICT DO NOTHING`, so device retries and replayed buffers are idempotent. |
| **Storage** | PostgreSQL schema managed with Alembic. Natural keys on `(vehicle_id, recorded_at)`, check constraints, JWT-scoped multi-tenant access. |
| **Analytics layer** | Nine SQL views in an `analytics` schema. They reconstruct trips from raw telemetry (gaps-and-islands), derive energy use from SoC × capacity × SoH, price charging sessions hour by hour against a time-of-day tariff, and build expanding-window battery stress features. |
| **Battery health** | Ridge regression on physically motivated ageing terms (√age, heat, cycles × DC-fast share, cycles × 100%-charge share), plus a 12-month SoH forecast per vehicle anchored on its current BMS reading. |
| **Range prediction** | Gradient boosting predicts Wh/km from speed, temperature, SoH and the vehicle's recent consumption. Range = usable energy ÷ predicted consumption. |
| **Charging optimisation** | Session costing by tariff band, potential off-peak savings, DC sessions charged past the taper point, and an API endpoint that schedules the cheapest charging window before the vehicle's usual departure time. |
| **Power BI** | Star schema (3 dimensions, 6 facts), ~40 DAX measures, 4 report pages: Fleet Overview, Battery Health, Range, Charging Optimisation. |

## Results on the demo fleet

| Metric | Value |
|---|---|
| Range prediction error (MAPE, 2,230 held-out trips from the last 28 days) | **3.6%** vs 4.5% for the trailing-average baseline (21% lower) |
| SoH estimate error on vehicles not seen in training (MAE) | 0.44 percentage points |
| 45-day SoH forecast backtest (MAE) | 0.037 pp; 4× better than "no change" (0.155), on par with a per-vehicle linear trend (0.032) |
| Home/depot charging drawn at peak tariff | 52% of energy; shifting it off-peak saves **₹80,900 per 180 days** (27% of home charging cost) |
| Battery fade over the 180 days | Cabs 1.9 pp, commuters 0.8 pp. Per 10,000 km commuters fade *faster* (1.2 vs 0.8 pp), because calendar ageing dominates for low-mileage cars |

These numbers come from simulated data; see [Data](#data).

## Power BI report

| Fleet Overview | Battery Health |
|---|---|
| ![](powerbi/screenshots/01-fleet-overview.png) | ![](powerbi/screenshots/02-battery-health.png) |
| **Range** | **Charging Optimisation** |
| ![](powerbi/screenshots/03-range.png) | ![](powerbi/screenshots/04-charging.png) |

The data model, relationships, DAX measures and page-by-page layout are documented in [`powerbi/README.md`](powerbi/README.md).

## Quick start

Requirements: Python 3.11+, PostgreSQL 14+ (or Docker), Power BI Desktop (Windows).

```bash
# 1. Database + API
docker compose up -d --build          # Postgres on :5432, API on :8000 (runs migrations on start)
#    or, without Docker:
python -m venv .venv && .venv/Scripts/activate      # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
cp .env.example .env                                # set DATABASE_URL
alembic -c backend/alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir backend --reload

# 2. Load 180 days of fleet telemetry through the API (~5-10 min)
python -m simulator.run --api http://localhost:8000

# 3. Train models and write predictions back to Postgres
python -m ml.train_battery_health
python -m ml.train_range
python -m ml.score_fleet

# 4. Open Power BI Desktop -> Get data -> PostgreSQL -> localhost:5432 / evision -> analytics.*
```

Interactive API docs are at http://localhost:8000/docs.

## API

All endpoints except `/health` and `/auth/*` need a bearer token. Vehicles are scoped to the signed-in user.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/register`, `/auth/login` | Get a JWT |
| `GET/POST` | `/api/v1/vehicles` | List / register vehicles (VIN-validated) |
| `GET/PATCH/DELETE` | `/api/v1/vehicles/{id}` | Vehicle details; soft delete keeps history |
| `GET` | `/api/v1/vehicles/{id}/status` | Latest SoC, SoH, odometer, battery temperature |
| `POST/GET` | `/api/v1/vehicles/{id}/telemetry` | Bulk idempotent ingest / time-filtered read |
| `POST/GET` | `/api/v1/vehicles/{id}/charging/sessions` | Charging session ingest / history |
| `GET` | `/api/v1/vehicles/{id}/charging/recommendation` | Cheapest charging window to reach a target SoC before departure |
| `POST` | `/api/v1/vehicles/{id}/predictions/range` | Range for given SoC, temperature and speed |
| `POST` | `/api/v1/vehicles/{id}/predictions/battery-health` | SoH forecast N days ahead |
| `GET` | `/api/v1/fleet/summary` | Fleet KPIs for the last N days |

Example: ride-hailing cab *Cab 16*, a Nexon EV back at the depot at 19:30 with 31% SoC.

```http
GET /api/v1/vehicles/{id}/charging/recommendation?target_soc_pct=80&at=2026-09-30T19:30:00%2B05:30
```
```json
{
  "current_soc_pct": 30.9,
  "target_soc_pct": 80.0,
  "energy_needed_kwh": 19.38,
  "avg_daily_energy_kwh": 21.01,
  "typical_departure": "07:28",
  "recommended_start": "2026-10-01T03:15:00+05:30",
  "expected_finish": "2026-10-01T05:56:00+05:30",
  "estimated_cost_inr": 112.39,
  "cost_if_started_now_inr": 174.49,
  "saving_inr": 62.1,
  "notes": ["A typical day uses about 59% of the battery, so you would finish the day at around 21%."]
}
```

The planner reads the vehicle's state as of `at`, works out its usual departure time from trip history, and searches 15-minute start slots for the cheapest window that still finishes before departure. On a tie it picks the latest slot, so the pack sits at high SoC for less time.

## Repository layout

```
backend/
  app/            FastAPI app: models, schemas, routers, services
  alembic/        migrations (schema, tariff seed, analytics views)
  sql/analytics/  SQL views that feed Power BI and the ML pipeline
  tests/          pytest suite against a real PostgreSQL database
ml/               feature definitions, training, forecasting, batch scoring, model registry
simulator/        fleet telemetry generator (vehicle catalog, climate, driving and charging behaviour)
powerbi/          DAX measures, theme, Power Query source, report build guide
```

## Data

The telemetry is **simulated**, because no public dataset combines minute-level telematics, charging sessions and BMS state of health for one fleet. The simulator is built to produce realistic structure, not random noise:

- **Vehicles:** real pack sizes, certified ranges, AC/DC charging limits and pack voltages for the seven models.
- **Consumption:** a speed curve (stop-go losses in the city, aerodynamic drag on the highway), air-conditioning load from city- and hour-specific temperatures, plus driver and trip variability.
- **Charging behaviour by owner type:** scheduled off-peak, plug in on arrival, public-only, and cab depot charging with midday DC top-ups. DC charging tapers above 50/80/90% SoC.
- **Battery degradation:** calendar fade (√time, accelerated by heat) plus cycle fade (accelerated by DC fast charging and frequent 100% charges). It is reported through a BMS with per-vehicle bias.

Everything goes through the same public API a real telematics gateway would use, so swapping in real data only means pointing devices at `/telemetry` and `/charging/sessions`.

## Development

```bash
export TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/evision_test   # throwaway DB
pytest            # API, ingestion, SQL views, tariff costing, charging planner, predictions
ruff check . && ruff format --check .
```

CI (GitHub Actions) runs lint and the test suite against a PostgreSQL 16 service container, then builds the Docker image.

## Tech stack

FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · PostgreSQL · psycopg 3 · scikit-learn · pandas · Power BI (DAX, Power Query) · Docker · GitHub Actions
