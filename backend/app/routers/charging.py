from datetime import UTC, datetime

from fastapi import APIRouter, Query, status

from app.deps import DbSession, OwnedVehicle
from app.models import ChargingSession
from app.schemas.charging import ChargingRecommendation, ChargingSessionBatch, ChargingSessionRead
from app.schemas.telemetry import IngestResult
from app.services import charging as charging_service

router = APIRouter(prefix="/vehicles/{vehicle_id}/charging", tags=["charging"])


@router.post("/sessions", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest_sessions(batch: ChargingSessionBatch, vehicle: OwnedVehicle, db: DbSession) -> IngestResult:
    return charging_service.ingest_sessions(db, vehicle.id, batch.sessions)


@router.get("/sessions", response_model=list[ChargingSessionRead])
def read_sessions(
    vehicle: OwnedVehicle,
    db: DbSession,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ChargingSession]:
    return charging_service.list_sessions(db, vehicle.id, start, end, limit)


@router.get("/recommendation", response_model=ChargingRecommendation)
def charging_recommendation(
    vehicle: OwnedVehicle,
    db: DbSession,
    target_soc_pct: float = Query(default=80, ge=20, le=100),
    charger_kw: float = Query(default=charging_service.HOME_CHARGER_KW, gt=0, le=22),
    at: datetime | None = Query(default=None, description="Plan as of this time (defaults to now)"),
) -> ChargingRecommendation:
    """Cheapest home-charging window that reaches the target SoC before the usual departure."""
    now = at or datetime.now(UTC)
    return charging_service.recommend_charging(db, vehicle, now, target_soc_pct, charger_kw)
