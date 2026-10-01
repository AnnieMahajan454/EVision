from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import auth, charging, fleet, predictions, telemetry, vehicles

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Ingests connected-vehicle telemetry and charging sessions into PostgreSQL and serves "
        "battery-health, range and charging-optimisation insights."
    ),
)

for router in (
    auth.router,
    vehicles.router,
    telemetry.router,
    charging.router,
    predictions.router,
    fleet.router,
):
    app.include_router(router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
