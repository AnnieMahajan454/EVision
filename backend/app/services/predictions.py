"""Serve the trained ML models for a single vehicle and log each prediction."""

import statistics
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Prediction, PredictionType, Vehicle
from app.services.telemetry import latest_reading
from ml.battery_forecast import forecast_soh
from ml.features import (
    BATTERY_HEALTH_INPUTS,
    range_design_matrix,
    range_from_efficiency,
    usable_energy_kwh,
)
from ml.registry import ModelArtifact, load_artifact


class InsufficientDataError(RuntimeError):
    pass


@lru_cache
def get_model(name: str) -> ModelArtifact:
    return load_artifact(settings.models_path, name)


def _trailing_efficiency(db: Session, vehicle: Vehicle) -> float:
    value = db.execute(
        text(
            """
            SELECT avg(efficiency_wh_per_km) FROM (
                SELECT efficiency_wh_per_km FROM analytics.fact_trip
                WHERE vehicle_id = :vehicle_id
                ORDER BY started_at DESC
                LIMIT 20
            ) recent
            """
        ),
        {"vehicle_id": vehicle.id},
    ).scalar_one()
    if value is None:
        # No trip history yet: fall back to the certified figure.
        return vehicle.battery_capacity_kwh * 1000 / vehicle.rated_range_km
    return float(value)


def predict_range(
    db: Session,
    vehicle: Vehicle,
    ambient_temp_c: float,
    expected_avg_speed_kph: float,
    soc_pct: float | None,
) -> tuple[Prediction, dict]:
    model = get_model("range")
    reading = latest_reading(db, vehicle.id)
    if soc_pct is None:
        if reading is None:
            raise InsufficientDataError("No telemetry yet. Pass soc_pct explicitly.")
        soc_pct = reading.soc_pct
    soh_pct = (reading.soh_pct if reading and reading.soh_pct else None) or 100.0

    features = {
        "avg_speed_kph": expected_avg_speed_kph,
        "avg_ambient_temp_c": ambient_temp_c,
        "soh_pct": soh_pct,
        "battery_capacity_kwh": vehicle.battery_capacity_kwh,
        "trailing_efficiency_wh_per_km": _trailing_efficiency(db, vehicle),
    }
    efficiency = model.predict(range_design_matrix(pd.DataFrame([features])))[0]
    energy = usable_energy_kwh(soc_pct, vehicle.battery_capacity_kwh, soh_pct)
    estimated_range = range_from_efficiency(energy, efficiency)

    prediction = Prediction(
        vehicle_id=vehicle.id,
        prediction_type=PredictionType.RANGE,
        reference_time=datetime.now(UTC),
        predicted_value=round(estimated_range, 1),
        unit="km",
        model_version=model.version,
        features={**features, "soc_pct": soc_pct, "predicted_efficiency_wh_per_km": efficiency},
    )
    db.add(prediction)
    db.commit()

    details = {
        "soc_pct": soc_pct,
        "soh_pct": soh_pct,
        "usable_energy_kwh": round(energy, 2),
        "predicted_efficiency_wh_per_km": round(efficiency, 1),
        "estimated_range_km": round(estimated_range, 1),
        "full_charge_range_km": round(
            range_from_efficiency(usable_energy_kwh(100, vehicle.battery_capacity_kwh, soh_pct), efficiency),
            1,
        ),
        "model_version": model.version,
    }
    return prediction, details


def predict_battery_health(db: Session, vehicle: Vehicle, horizon_days: int) -> tuple[Prediction, dict]:
    model = get_model("battery_health")
    recent = (
        db.execute(
            text(
                """
            SELECT * FROM analytics.fact_battery_health
            WHERE vehicle_id = :vehicle_id
            ORDER BY date DESC
            LIMIT 7
            """
            ),
            {"vehicle_id": vehicle.id},
        )
        .mappings()
        .all()
    )
    if not recent:
        raise InsufficientDataError("No battery history for this vehicle yet.")
    latest = recent[0]
    # Last week's median smooths day-to-day BMS jitter; the forecast is anchored on it.
    current_soh = float(statistics.median(row["soh_pct"] for row in recent))

    daily_km = db.execute(
        text(
            """
            SELECT coalesce(sum(distance_km), 0) / 30.0 FROM analytics.fact_vehicle_daily
            WHERE vehicle_id = :vehicle_id AND date > CAST(:as_of AS date) - 30
            """
        ),
        {"vehicle_id": vehicle.id, "as_of": latest["date"]},
    ).scalar_one()
    daily_km = float(daily_km)

    features = {name: float(latest[name]) for name in BATTERY_HEALTH_INPUTS}
    predicted = forecast_soh(model, features, current_soh, [horizon_days], daily_km, vehicle.rated_range_km)[
        0
    ]

    reference = datetime.combine(latest["date"], datetime.min.time(), tzinfo=UTC)
    prediction = Prediction(
        vehicle_id=vehicle.id,
        prediction_type=PredictionType.BATTERY_HEALTH,
        reference_time=reference,
        horizon_days=horizon_days,
        predicted_value=round(predicted, 2),
        unit="pct",
        model_version=model.version,
        features={**features, "assumed_daily_km": daily_km},
    )
    db.add(prediction)
    db.commit()

    details = {
        "current_soh_pct": round(current_soh, 2),
        "predicted_soh_pct": round(predicted, 2),
        "horizon_days": horizon_days,
        "target_date": reference + timedelta(days=horizon_days),
        "assumed_daily_km": round(daily_km, 1),
        "model_version": model.version,
    }
    return prediction, details


def list_predictions(db: Session, vehicle: Vehicle, prediction_type: PredictionType | None, limit: int):
    statement = select(Prediction).where(Prediction.vehicle_id == vehicle.id)
    if prediction_type is not None:
        statement = statement.where(Prediction.prediction_type == prediction_type)
    return list(db.scalars(statement.order_by(Prediction.created_at.desc()).limit(limit)))
