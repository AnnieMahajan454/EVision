from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import PredictionType


class RangePredictionRequest(BaseModel):
    soc_pct: float | None = Field(default=None, ge=0, le=100, description="Defaults to the latest reading")
    ambient_temp_c: float = Field(ge=-20, le=55)
    expected_avg_speed_kph: float = Field(gt=0, le=150)


class RangePredictionResponse(BaseModel):
    soc_pct: float
    soh_pct: float
    usable_energy_kwh: float
    predicted_efficiency_wh_per_km: float
    estimated_range_km: float
    full_charge_range_km: float
    model_version: str


class BatteryHealthPredictionRequest(BaseModel):
    horizon_days: int = Field(default=365, ge=0, le=1095)


class BatteryHealthPredictionResponse(BaseModel):
    current_soh_pct: float
    predicted_soh_pct: float
    horizon_days: int
    target_date: datetime
    assumed_daily_km: float
    model_version: str


class PredictionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prediction_type: PredictionType
    reference_time: datetime
    horizon_days: int
    predicted_value: float
    unit: str
    model_version: str
    features: dict
    created_at: datetime
