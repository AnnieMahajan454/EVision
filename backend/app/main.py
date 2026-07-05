from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routers.auth import router as auth_router
from routers.health import router as health_router
from routers.predictions import router as predictions_router
from routers.telemetry import router as telemetry_router
from routers.vehicles import router as vehicles_router
from database.session import engine
from database.base import Base


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create tables on startup only when explicitly enabled (dev convenience)
    try:
        from core.config import settings

        if settings.create_tables_on_start:
            Base.metadata.create_all(bind=engine)
    except Exception:
        # If config isn't available or creation fails, continue startup and
        # rely on the deployed DB migration process (Alembic) in production.
        pass
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(vehicles_router)
app.include_router(telemetry_router)
app.include_router(predictions_router)


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"message": "EVision API is running"}
