from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models.telemetry import Telemetry
from schemas.telemetry import TelemetryRecordCreate


def ingest_telemetry_records(
    db: Session,
    user_id: str,
    vehicle_id: str,
    telemetry_records: list[TelemetryRecordCreate],
) -> list[Telemetry]:
    rows = [
        Telemetry(
            user_id=user_id,
            vehicle_id=vehicle_id,
            battery_percentage=record.battery_percentage,
            voltage_v=record.voltage_v,
            current_a=record.current_a,
            speed_kph=record.speed_kph,
            motor_temperature_c=record.motor_temperature_c,
            ambient_temperature_c=record.ambient_temperature_c,
            distance_km=record.distance_km,
            recorded_at=record.recorded_at or datetime.now(timezone.utc),
        )
        for record in telemetry_records
    ]

    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def get_recent_telemetry(db: Session, user_id: str, vehicle_id: str, limit: int) -> list[Telemetry]:
    statement: Select[tuple[Telemetry]] = (
        select(Telemetry)
        .where(Telemetry.user_id == user_id, Telemetry.vehicle_id == vehicle_id)
        .order_by(Telemetry.recorded_at.desc(), Telemetry.ingested_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
