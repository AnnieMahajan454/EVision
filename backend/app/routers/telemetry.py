from datetime import datetime

from fastapi import APIRouter, Query, status

from app.deps import DbSession, OwnedVehicle
from app.models import Telemetry
from app.schemas.telemetry import IngestResult, TelemetryBatch, TelemetryRead
from app.services import telemetry as telemetry_service

router = APIRouter(prefix="/vehicles/{vehicle_id}/telemetry", tags=["telemetry"])


@router.post("", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest_telemetry(batch: TelemetryBatch, vehicle: OwnedVehicle, db: DbSession) -> IngestResult:
    """Bulk-ingest readings. Readings already stored for the same timestamp are skipped."""
    return telemetry_service.ingest_readings(db, vehicle.id, batch.readings)


@router.get("", response_model=list[TelemetryRead])
def read_telemetry(
    vehicle: OwnedVehicle,
    db: DbSession,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[Telemetry]:
    return telemetry_service.list_readings(db, vehicle.id, start, end, limit)
