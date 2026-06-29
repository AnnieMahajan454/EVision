from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    vin: str = Field(min_length=8, max_length=32)
    nickname: str | None = Field(default=None, max_length=100)
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1990, le=2100)
    battery_capacity_kwh: float = Field(gt=0)
    odometer_km: float = Field(default=0.0, ge=0)


class VehicleUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=100)
    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1990, le=2100)
    battery_capacity_kwh: float | None = Field(default=None, gt=0)
    odometer_km: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    vin: str
    nickname: str | None
    make: str
    model: str
    year: int
    battery_capacity_kwh: float
    odometer_km: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class VehicleListResponse(BaseModel):
    items: list[VehicleRead]
    total: int
