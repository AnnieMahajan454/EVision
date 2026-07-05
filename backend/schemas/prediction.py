from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.telemetry import TelemetryRecordCreate


class BatteryHealthPredictionRequest(BaseModel):
    telemetry: TelemetryRecordCreate
    model_version: str = Field(default="battery-health-v1", max_length=50)


class BatteryHealthPredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prediction_id: str
    vehicle_id: str
    prediction_type: str
    predicted_battery_health: float
    model_version: str
    created_at: datetime


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    vehicle_id: str
    prediction_type: str
    predicted_value: float
    model_version: str
    input_payload: dict
    notes: str | None
    created_at: datetime
