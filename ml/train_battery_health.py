"""Train the battery state-of-health model and backtest its forecasts.

    python -m ml.train_battery_health [--holdout-days 45]

Evaluation:
  * leave-vehicles-out CV: how well SoH is estimated for vehicles the model never saw;
  * forecast backtest: fit on data up to a cutoff, then forecast each vehicle's SoH over the
    held-out period with the same anchored projection used in production
    (ml/battery_forecast.py). Compared against "SoH stays where it is" and a per-vehicle
    straight-line trend.
"""

import argparse
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ml.battery_forecast import forecast_soh
from ml.data import get_engine, load_battery_health
from ml.features import BATTERY_HEALTH_TARGET, battery_health_design_matrix
from ml.registry import ModelArtifact, save_artifact
from ml.settings import MODELS_DIR


def make_model():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 2, 20)))


def current_soh(history: pd.DataFrame) -> float:
    """Median of the last week: daily BMS readings jitter by about 0.1 pp."""
    return float(history[BATTERY_HEALTH_TARGET].tail(7).median())


def recent_km_per_day(history: pd.DataFrame, days: int = 30) -> float:
    recent = history.tail(days)
    span = max((recent["date"].iloc[-1] - recent["date"].iloc[0]).days, 1)
    return float(recent["odometer_km"].iloc[-1] - recent["odometer_km"].iloc[0]) / span


def forecast_backtest(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, float]:
    model = make_model().fit(battery_health_design_matrix(train), train[BATTERY_HEALTH_TARGET])
    errors = {"model": [], "persistence": [], "linear_trend": []}

    for vehicle_id, future in test.groupby("vehicle_id"):
        history = train[train["vehicle_id"] == vehicle_id]
        if len(history) < 30:
            continue
        last = history.iloc[-1]
        anchor = current_soh(history)
        days_ahead = (future["date"] - last["date"]).dt.days.tolist()
        actual = future[BATTERY_HEALTH_TARGET].to_numpy()

        forecast = forecast_soh(
            model, last.to_dict(), anchor, days_ahead, recent_km_per_day(history), last["rated_range_km"]
        )
        days_back = (history["date"] - last["date"]).dt.days
        slope, intercept = np.polyfit(days_back, history[BATTERY_HEALTH_TARGET], 1)
        trend = intercept + slope * np.array(days_ahead)

        errors["model"] += list(np.abs(np.array(forecast) - actual))
        errors["persistence"] += list(np.abs(anchor - actual))
        errors["linear_trend"] += list(np.abs(trend - actual))

    return {f"backtest_mae_{name}": float(np.mean(values)) for name, values in errors.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout-days", type=int, default=45)
    args = parser.parse_args()

    frame = load_battery_health(get_engine())
    cutoff = frame["date"].max() - pd.Timedelta(days=args.holdout_days)
    train, test = frame[frame["date"] <= cutoff], frame[frame["date"] > cutoff]
    print(
        f"{len(frame):,} vehicle-days from {frame['vehicle_id'].nunique()} vehicles; cutoff {cutoff.date()}"
    )

    x, y = battery_health_design_matrix(frame), frame[BATTERY_HEALTH_TARGET]
    cv_pred = cross_val_predict(make_model(), x, y, groups=frame["vehicle_id"], cv=GroupKFold(n_splits=5))
    metrics = {"cv_mae_unseen_vehicles": float(mean_absolute_error(y, cv_pred))}
    metrics.update(forecast_backtest(train, test))

    final = make_model().fit(x, y)  # production model uses all data
    coefficients = dict(zip(x.columns, final[-1].coef_ / final[0].scale_, strict=True))

    artifact = ModelArtifact(
        name="battery_health",
        version=f"soh-ridge-{datetime.now(UTC):%Y%m%d}",
        estimator=final,
        feature_names=list(x.columns),
        metrics=metrics,
        trained_at=datetime.now(UTC),
        train_cutoff=frame["date"].max().date(),
        extra={"coefficients_pct_per_unit": coefficients},
    )
    path = save_artifact(artifact, MODELS_DIR)

    print("Metrics (SoH percentage points):")
    for name, value in metrics.items():
        print(f"  {name:<32} {value:.3f}")
    print("Fade per unit of each term:", {k: round(v, 3) for k, v in coefficients.items()})
    print(f"Saved {artifact.version} -> {path}")


if __name__ == "__main__":
    main()
