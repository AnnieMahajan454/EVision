import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

# Each reading becomes 11 bind parameters in the bulk INSERT; 2000 rows keeps a batch well
# under PostgreSQL's 65,535-parameter limit.
MAX_BATCH_SIZE = 2000


class TelemetryReading(BaseModel):
    recorded_at: AwareDatetime
    odometer_km: float = Field(ge=0)
    speed_kph: float = Field(ge=0, le=250)
    soc_pct: float = Field(ge=0, le=100)
    soh_pct: float | None = Field(default=None, ge=0, le=100)
    battery_voltage_v: float = Field(gt=0, le=1000)
    battery_current_a: float = Field(ge=-1000, le=1000)
    battery_temp_c: float = Field(ge=-40, le=90)
    motor_temp_c: float | None = Field(default=None, ge=-40, le=200)
    ambient_temp_c: float | None = Field(default=None, ge=-50, le=60)


class TelemetryBatch(BaseModel):
    readings: list[TelemetryReading] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class IngestResult(BaseModel):
    vehicle_id: uuid.UUID
    received: int
    inserted: int
    duplicates: int


class TelemetryRead(TelemetryReading):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
