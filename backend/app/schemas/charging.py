from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.models import ChargerType


class ChargingSessionCreate(BaseModel):
    started_at: AwareDatetime
    ended_at: AwareDatetime
    charger_type: ChargerType
    start_soc_pct: float = Field(ge=0, le=100)
    end_soc_pct: float = Field(ge=0, le=100)
    energy_delivered_kwh: float = Field(ge=0, le=300)
    max_power_kw: float | None = Field(default=None, gt=0, le=400)
    cost_inr: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_consistency(self) -> "ChargingSessionCreate":
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        if self.end_soc_pct < self.start_soc_pct:
            raise ValueError("end_soc_pct cannot be lower than start_soc_pct")
        return self


class ChargingSessionBatch(BaseModel):
    sessions: list[ChargingSessionCreate] = Field(min_length=1, max_length=500)


class ChargingSessionRead(ChargingSessionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    ended_at: datetime


class ChargingRecommendation(BaseModel):
    current_soc_pct: float
    target_soc_pct: float
    energy_needed_kwh: float
    avg_daily_energy_kwh: float = Field(description="Average over the last 14 days of driving")
    typical_departure: str = Field(description="Local time the vehicle usually leaves, HH:MM")
    recommended_start: datetime
    expected_finish: datetime
    estimated_cost_inr: float
    cost_if_started_now_inr: float
    saving_inr: float
    notes: list[str]
