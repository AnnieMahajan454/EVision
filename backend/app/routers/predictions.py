from fastapi import APIRouter, HTTPException, Query, status

from app.deps import DbSession, OwnedVehicle
from app.models import Prediction, PredictionType
from app.schemas.prediction import (
    BatteryHealthPredictionRequest,
    BatteryHealthPredictionResponse,
    PredictionRead,
    RangePredictionRequest,
    RangePredictionResponse,
)
from app.services import predictions as prediction_service
from app.services.predictions import InsufficientDataError
from ml.registry import ModelUnavailableError

router = APIRouter(prefix="/vehicles/{vehicle_id}/predictions", tags=["predictions"])


@router.post("/range", response_model=RangePredictionResponse, status_code=status.HTTP_201_CREATED)
def predict_range(payload: RangePredictionRequest, vehicle: OwnedVehicle, db: DbSession) -> dict:
    try:
        _, details = prediction_service.predict_range(
            db, vehicle, payload.ambient_temp_c, payload.expected_avg_speed_kph, payload.soc_pct
        )
    except ModelUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except InsufficientDataError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return details


@router.post(
    "/battery-health", response_model=BatteryHealthPredictionResponse, status_code=status.HTTP_201_CREATED
)
def predict_battery_health(
    payload: BatteryHealthPredictionRequest, vehicle: OwnedVehicle, db: DbSession
) -> dict:
    try:
        _, details = prediction_service.predict_battery_health(db, vehicle, payload.horizon_days)
    except ModelUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except InsufficientDataError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return details


@router.get("", response_model=list[PredictionRead])
def read_predictions(
    vehicle: OwnedVehicle,
    db: DbSession,
    prediction_type: PredictionType | None = None,
    limit: int = Query(default=50, ge=1, le=500),
) -> list[Prediction]:
    return prediction_service.list_predictions(db, vehicle, prediction_type, limit)
