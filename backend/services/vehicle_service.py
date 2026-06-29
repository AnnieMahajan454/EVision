from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models.vehicle import Vehicle
from schemas.vehicle import VehicleCreate, VehicleUpdate


def get_vehicle_by_id(db: Session, vehicle_id: str, user_id: str) -> Vehicle | None:
    statement: Select[tuple[Vehicle]] = select(Vehicle).where(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == user_id,
        Vehicle.is_active.is_(True),
    )
    return db.scalars(statement).first()


def list_vehicles(db: Session, user_id: str) -> list[Vehicle]:
    statement: Select[tuple[Vehicle]] = select(Vehicle).where(
        Vehicle.user_id == user_id,
        Vehicle.is_active.is_(True),
    ).order_by(Vehicle.created_at.desc())
    return list(db.scalars(statement).all())


def create_vehicle(db: Session, user_id: str, vehicle_in: VehicleCreate) -> Vehicle:
    statement: Select[tuple[Vehicle]] = select(Vehicle).where(Vehicle.vin == vehicle_in.vin.upper())
    existing_vehicle = db.scalars(statement).first()
    if existing_vehicle is not None:
        raise ValueError("VIN is already registered")

    vehicle = Vehicle(
        user_id=user_id,
        vin=vehicle_in.vin.upper(),
        nickname=vehicle_in.nickname,
        make=vehicle_in.make,
        model=vehicle_in.model,
        year=vehicle_in.year,
        battery_capacity_kwh=vehicle_in.battery_capacity_kwh,
        odometer_km=vehicle_in.odometer_km,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(db: Session, vehicle: Vehicle, vehicle_in: VehicleUpdate) -> Vehicle:
    updates = vehicle_in.model_dump(exclude_unset=True)
    if "nickname" in updates:
        vehicle.nickname = updates["nickname"]
    if "make" in updates:
        vehicle.make = updates["make"]
    if "model" in updates:
        vehicle.model = updates["model"]
    if "year" in updates:
        vehicle.year = updates["year"]
    if "battery_capacity_kwh" in updates:
        vehicle.battery_capacity_kwh = updates["battery_capacity_kwh"]
    if "odometer_km" in updates:
        vehicle.odometer_km = updates["odometer_km"]
    if "is_active" in updates:
        vehicle.is_active = updates["is_active"]

    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, vehicle: Vehicle) -> Vehicle:
    vehicle.is_active = False
    db.commit()
    db.refresh(vehicle)
    return vehicle
