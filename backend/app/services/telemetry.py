import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Telemetry
from app.schemas.telemetry import IngestResult, TelemetryReading


def ingest_readings(db: Session, vehicle_id: uuid.UUID, readings: list[TelemetryReading]) -> IngestResult:
    rows = [{"vehicle_id": vehicle_id, **reading.model_dump()} for reading in readings]
    # Re-sent readings (device retries, replayed buffers) are skipped instead of failing the batch.
    statement = (
        insert(Telemetry)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_telemetry_vehicle_time")
        .returning(Telemetry.id)
    )
    inserted = len(db.execute(statement).all())
    db.commit()
    return IngestResult(
        vehicle_id=vehicle_id,
        received=len(rows),
        inserted=inserted,
        duplicates=len(rows) - inserted,
    )


def list_readings(
    db: Session,
    vehicle_id: uuid.UUID,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[Telemetry]:
    statement = select(Telemetry).where(Telemetry.vehicle_id == vehicle_id)
    if start is not None:
        statement = statement.where(Telemetry.recorded_at >= start)
    if end is not None:
        statement = statement.where(Telemetry.recorded_at < end)
    statement = statement.order_by(Telemetry.recorded_at.desc()).limit(limit)
    return list(db.scalars(statement))


def latest_reading(db: Session, vehicle_id: uuid.UUID, before: datetime | None = None) -> Telemetry | None:
    statement = select(Telemetry).where(Telemetry.vehicle_id == vehicle_id)
    if before is not None:
        statement = statement.where(Telemetry.recorded_at <= before)
    return db.scalars(statement.order_by(Telemetry.recorded_at.desc()).limit(1)).first()
