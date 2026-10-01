"""Train the consumption (Wh/km) model behind range prediction.

    python -m ml.train_range [--holdout-days 28]

Trips before the cutoff are used for training; the most recent `holdout-days` are held out
(time-based split, no shuffling, so the model is never evaluated on trips older than its
training data). The baseline is what a typical dashboard shows: the vehicle's average
consumption over its last 20 trips.
"""

import argparse
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

from ml.data import get_engine, load_trips
from ml.features import RANGE_TARGET, range_design_matrix
from ml.registry import ModelArtifact, save_artifact
from ml.settings import MODELS_DIR


def make_model() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=400,
        learning_rate=0.05,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        random_state=42,
    )


def evaluate(y_true: pd.Series, y_pred: np.ndarray, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_mae_wh_per_km": float(mean_absolute_error(y_true, y_pred)),
        # Range error % equals consumption error % for the same energy in the pack.
        f"{prefix}_mape_pct": float(mean_absolute_percentage_error(y_true, y_pred) * 100),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout-days", type=int, default=28)
    args = parser.parse_args()

    trips = load_trips(get_engine())
    cutoff = trips["trip_date"].max() - pd.Timedelta(days=args.holdout_days)
    train, test = trips[trips["trip_date"] <= cutoff], trips[trips["trip_date"] > cutoff]
    print(f"{len(trips):,} trips; training on {len(train):,} up to {cutoff.date()}, testing on {len(test):,}")

    model = make_model().fit(range_design_matrix(train), train[RANGE_TARGET])
    metrics = {
        **evaluate(test[RANGE_TARGET], model.predict(range_design_matrix(test)), "model"),
        **evaluate(test[RANGE_TARGET], test["trailing_efficiency_wh_per_km"].to_numpy(), "baseline"),
        "n_train": float(len(train)),
        "n_test": float(len(test)),
    }

    artifact = ModelArtifact(
        name="range",
        version=f"range-hgb-{datetime.now(UTC):%Y%m%d}",
        estimator=model,
        feature_names=list(range_design_matrix(train).columns),
        metrics=metrics,
        trained_at=datetime.now(UTC),
        train_cutoff=cutoff.date(),
    )
    path = save_artifact(artifact, MODELS_DIR)

    print("Hold-out metrics:")
    for name, value in metrics.items():
        print(f"  {name:<28} {value:,.2f}")
    print(f"Saved {artifact.version} -> {path}")


if __name__ == "__main__":
    main()
