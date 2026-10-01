from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession, OwnedVehicle
from app.models import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleStatus, VehicleUpdate
from app.services.telemetry import latest_reading

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleRead])
def list_vehicles(user: CurrentUser, db: DbSession) -> list[Vehicle]:
    statement = (
        select(Vehicle).where(Vehicle.owner_id == user.id, Vehicle.is_active).order_by(Vehicle.created_at)
    )
    return list(db.scalars(statement))


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, user: CurrentUser, db: DbSession) -> Vehicle:
    if db.scalar(select(Vehicle.id).where(Vehicle.vin == payload.vin)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A vehicle with this VIN is already registered")

    vehicle = Vehicle(owner_id=user.id, **payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle: OwnedVehicle) -> Vehicle:
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(payload: VehicleUpdate, vehicle: OwnedVehicle, db: DbSession) -> Vehicle:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_vehicle(vehicle: OwnedVehicle, db: DbSession) -> None:
    # Soft delete: keep the telemetry history for fleet-level analytics.
    vehicle.is_active = False
    db.commit()


@router.get("/{vehicle_id}/status", response_model=VehicleStatus)
def vehicle_status(vehicle: OwnedVehicle, db: DbSession) -> VehicleStatus:
    reading = latest_reading(db, vehicle.id)
    return VehicleStatus(
        vehicle_id=vehicle.id,
        last_seen_at=reading.recorded_at if reading else None,
        odometer_km=reading.odometer_km if reading else None,
        soc_pct=reading.soc_pct if reading else None,
        soh_pct=reading.soh_pct if reading else None,
        battery_temp_c=reading.battery_temp_c if reading else None,
    )
