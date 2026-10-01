"""Batch-score the fleet and write predictions back to PostgreSQL for Power BI.

    python -m ml.score_fleet

* Range: every trip after the range model's training cutoff gets a prediction made "at
  departure" (start SoC, SoH, conditions). analytics.fact_range_prediction compares it with
  what actually happened.
* Battery health: a SoH forecast curve, 0-365 days ahead in 15-day steps, for every vehicle.
  The previous batch forecast is replaced.
"""

import json

import pandas as pd
from sqlalchemy import text

from ml.battery_forecast import forecast_soh
from ml.data import get_engine, load_battery_health, load_trips, recent_daily_km
from ml.features import (
    range_design_matrix,
    range_from_efficiency,
    usable_energy_kwh,
)
from ml.registry import load_artifact
from ml.settings import MODELS_DIR

INSERT = text(
    """
    INSERT INTO predictions
        (vehicle_id, prediction_type, reference_time, horizon_days, predicted_value, unit, model_version, features)
    VALUES
        (:vehicle_id, :prediction_type, :reference_time, :horizon_days, :predicted_value, :unit, :model_version,
         CAST(:features AS jsonb))
    """
)


def score_range(engine) -> int:
    model = load_artifact(MODELS_DIR, "range")
    trips = load_trips(engine)
    trips = trips[trips["trip_date"].dt.date > model.train_cutoff].copy()

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM predictions WHERE prediction_type = 'range' AND features->>'source' = 'batch'")
        )
        if trips.empty:
            return 0
        trips["predicted_efficiency"] = model.predict(range_design_matrix(trips))
        rows = []
        for trip in trips.itertuples():
            soh = trip.soh_pct if pd.notna(trip.soh_pct) else 100.0
            energy = usable_energy_kwh(trip.start_soc_pct, trip.battery_capacity_kwh, soh)
            features = {name: float(getattr(trip, name)) for name in model.feature_names}
            features.update(
                source="batch",
                soc_pct=float(trip.start_soc_pct),
                predicted_efficiency_wh_per_km=float(trip.predicted_efficiency),
            )
            rows.append(
                {
                    "vehicle_id": trip.vehicle_id,
                    "prediction_type": "range",
                    "reference_time": trip.started_at,
                    "horizon_days": 0,
                    "predicted_value": round(range_from_efficiency(energy, trip.predicted_efficiency), 2),
                    "unit": "km",
                    "model_version": model.version,
                    "features": json.dumps(features),
                }
            )
        connection.execute(INSERT, rows)
    return len(rows)


def score_battery_health(engine, horizons=range(0, 366, 15)) -> int:
    model = load_artifact(MODELS_DIR, "battery_health")
    history = load_battery_health(engine)
    latest = (
        history.sort_values("date")
        .groupby("vehicle_id")
        .tail(1)
        .merge(recent_daily_km(engine), on="vehicle_id")
    )

    # Anchor each forecast on the vehicle's last week of BMS readings (see ml/battery_forecast.py).
    observed = (
        history.sort_values("date").groupby("vehicle_id")["soh_pct"].apply(lambda s: s.tail(7).median())
    )

    rows = []
    for vehicle in latest.itertuples():
        forecast = forecast_soh(
            model,
            vehicle._asdict(),
            float(observed[vehicle.vehicle_id]),
            list(horizons),
            vehicle.daily_km,
            vehicle.rated_range_km,
        )
        for h, value in zip(horizons, forecast, strict=True):
            rows.append(
                {
                    "vehicle_id": vehicle.vehicle_id,
                    "prediction_type": "battery_health",
                    "reference_time": pd.Timestamp(vehicle.date).tz_localize("UTC"),
                    "horizon_days": h,
                    "predicted_value": round(value, 3),
                    "unit": "pct",
                    "model_version": model.version,
                    "features": json.dumps({"source": "batch", "assumed_daily_km": float(vehicle.daily_km)}),
                }
            )

    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM predictions WHERE prediction_type = 'battery_health' AND features->>'source' = 'batch'"
            )
        )
        if rows:
            connection.execute(INSERT, rows)
    return len(rows)


def main() -> None:
    engine = get_engine()
    print(f"Range predictions written:          {score_range(engine):,}")
    print(f"Battery-health forecasts written:   {score_battery_health(engine):,}")


if __name__ == "__main__":
    main()
