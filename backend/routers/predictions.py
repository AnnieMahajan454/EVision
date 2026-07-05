from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_user
from database.session import get_db
from models.user import User
from schemas.prediction import BatteryHealthPredictionRequest, BatteryHealthPredictionResponse, PredictionRead
from services.prediction_service import create_battery_health_prediction, list_vehicle_predictions
from services.vehicle_service import get_vehicle_by_id

router = APIRouter(prefix=f"{settings.api_v1_prefix}/vehicles/{{vehicle_id}}/predictions", tags=["Predictions"])


@router.post("/battery-health", response_model=BatteryHealthPredictionResponse, status_code=status.HTTP_201_CREATED)
def predict_battery_health(
    vehicle_id: str,
    payload: BatteryHealthPredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatteryHealthPredictionResponse:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    return create_battery_health_prediction(db, current_user.id, vehicle_id, payload)


@router.get("", response_model=list[PredictionRead])
def read_vehicle_predictions(
    vehicle_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PredictionRead]:
    vehicle = get_vehicle_by_id(db, vehicle_id, current_user.id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    predictions = list_vehicle_predictions(db, current_user.id, vehicle_id, limit)
    return [PredictionRead.model_validate(prediction) for prediction in predictions]
