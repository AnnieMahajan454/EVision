from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_user
from database.session import get_db
from models.user import User
from schemas.vehicle import VehicleCreate, VehicleListResponse, VehicleRead, VehicleUpdate
from services.vehicle_service import create_vehicle, delete_vehicle, get_vehicle_by_id, list_vehicles, update_vehicle

router = APIRouter(prefix=f"{settings.api_v1_prefix}/vehicles", tags=["Vehicles"])


@router.get("", response_model=VehicleListResponse)
def read_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VehicleListResponse:
    vehicles = list_vehicles(db, current_user.id)
    return VehicleListResponse(items=[VehicleRead.model_validate(vehicle) for vehicle in vehicles], total=len(vehicles))


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def add_vehicle(
    payload: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VehicleRead:
    try:
        vehicle = create_vehicle(db, current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return VehicleRead.model_validate(vehicle)


@router.put("/{vehicle_id}", response_model=VehicleRead)
def modify_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VehicleRead:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    return VehicleRead.model_validate(update_vehicle(db, vehicle, payload))


@router.delete("/{vehicle_id}", response_model=VehicleRead)
def remove_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VehicleRead:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    return VehicleRead.model_validate(delete_vehicle(db, vehicle))
