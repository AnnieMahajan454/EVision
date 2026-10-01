import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleBase(BaseModel):
    nickname: str | None = Field(default=None, max_length=100)
    make: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=50)
    model_year: int = Field(ge=2010, le=2100)
    battery_capacity_kwh: float = Field(gt=0, le=250, description="Usable pack capacity when new")
    rated_range_km: float = Field(gt=0, le=1500, description="Manufacturer-certified range (ARAI/MIDC)")
    registered_on: date


class VehicleCreate(VehicleBase):
    vin: str = Field(min_length=17, max_length=17, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")

    @field_validator("vin", mode="before")
    @classmethod
    def normalise_vin(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value


class VehicleUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=100)
    battery_capacity_kwh: float | None = Field(default=None, gt=0, le=250)
    rated_range_km: float | None = Field(default=None, gt=0, le=1500)


class VehicleRead(VehicleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vin: str
    created_at: datetime


class VehicleStatus(BaseModel):
    """Latest known state of a vehicle, derived from its most recent telemetry."""

    vehicle_id: uuid.UUID
    last_seen_at: datetime | None
    odometer_km: float | None
    soc_pct: float | None
    soh_pct: float | None
    battery_temp_c: float | None
