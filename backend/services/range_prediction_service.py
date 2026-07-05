from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from models.prediction import Prediction
from ml.prediction.range_predictor import RangePredictor
from schemas.prediction import RangePredictionRequest, RangePredictionResponse


PREDICTION_TYPE_RANGE = "driving_range"


def get_range_predictor() -> RangePredictor:
    return RangePredictor()


def create_range_prediction(db: Session, user_id: str, vehicle_id: str, payload: RangePredictionRequest) -> RangePredictionResponse:
    predictor = get_range_predictor()
    telemetry_payload = payload.telemetry.model_dump()
    predicted_value = predictor.predict(telemetry_payload)

    prediction = Prediction(
        user_id=user_id,
        vehicle_id=vehicle_id,
        prediction_type=PREDICTION_TYPE_RANGE,
        predicted_value=predicted_value,
        model_version=payload.model_version,
        input_payload=telemetry_payload,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)

    return RangePredictionResponse(
        prediction_id=prediction.id,
        vehicle_id=prediction.vehicle_id,
        prediction_type=prediction.prediction_type,
        predicted_range_km=prediction.predicted_value,
        model_version=prediction.model_version,
        created_at=prediction.created_at,
    )


def list_vehicle_predictions(db: Session, user_id: str, vehicle_id: str, limit: int = 50) -> list[Prediction]:
    statement: Select[tuple[Prediction]] = (
        select(Prediction)
        .where(Prediction.user_id == user_id, Prediction.vehicle_id == vehicle_id)
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
