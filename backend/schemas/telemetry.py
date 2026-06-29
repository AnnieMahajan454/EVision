from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryRecordCreate(BaseModel):
    battery_percentage: float = Field(ge=0, le=100)
    voltage_v: float = Field(gt=0)
    current_a: float
    speed_kph: float = Field(ge=0)
    motor_temperature_c: float
    ambient_temperature_c: float
    distance_km: float = Field(ge=0)
    recorded_at: datetime | None = None


class TelemetryBatchIngestRequest(BaseModel):
    records: list[TelemetryRecordCreate] = Field(min_length=1, max_length=500)


class TelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    vehicle_id: str
    battery_percentage: float
    voltage_v: float
    current_a: float
    speed_kph: float
    motor_temperature_c: float
    ambient_temperature_c: float
    distance_km: float
    recorded_at: datetime
    ingested_at: datetime


class TelemetryBatchIngestResponse(BaseModel):
    vehicle_id: str
    ingested_count: int
    records: list[TelemetryRead]
