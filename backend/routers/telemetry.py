from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_user
from database.session import get_db
from models.user import User
from schemas.telemetry import (
    TelemetryBatchIngestRequest,
    TelemetryBatchIngestResponse,
    TelemetryRead,
)
from services.telemetry_service import get_recent_telemetry, ingest_telemetry_records
from services.vehicle_service import get_vehicle_by_id

router = APIRouter(prefix=f"{settings.api_v1_prefix}/vehicles/{{vehicle_id}}/telemetry", tags=["Telemetry"])


@router.post("", response_model=TelemetryBatchIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_vehicle_telemetry(
    vehicle_id: str,
    payload: TelemetryBatchIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TelemetryBatchIngestResponse:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    records = ingest_telemetry_records(db, current_user.id, vehicle_id, payload.records)
    return TelemetryBatchIngestResponse(
        vehicle_id=vehicle_id,
        ingested_count=len(records),
        records=[TelemetryRead.model_validate(record) for record in records],
    )


@router.get("", response_model=list[TelemetryRead])
def list_vehicle_telemetry(
    vehicle_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TelemetryRead]:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    records = get_recent_telemetry(db, current_user.id, vehicle_id, limit)
    return [TelemetryRead.model_validate(record) for record in records]
