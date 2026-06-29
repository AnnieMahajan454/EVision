from __future__ import annotations

from pathlib import Path
import joblib

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.utils.feature_engineering import FEATURE_COLUMNS, TARGET_COLUMN, load_training_frame


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = PROJECT_ROOT / "ml" / "datasets" / "sample_battery_health_telemetry.csv"
MODEL_OUTPUT_PATH = PROJECT_ROOT / "ml" / "models" / "battery_health_model.joblib"
MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def train_battery_health_model() -> dict[str, float]:
    frame = load_training_frame(str(DATASET_PATH))
    features = frame[FEATURE_COLUMNS]
    target = frame[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=0.25, random_state=42)

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("regressor", RandomForestRegressor(n_estimators=200, random_state=42)),
        ]
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, predictions)),
        "r2": float(r2_score(y_test, predictions)),
    }

    joblib.dump(
        {
            "model": model,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "metrics": metrics,
        },
        MODEL_OUTPUT_PATH,
    )
    return metrics


if __name__ == "__main__":
    metrics = train_battery_health_model()
    print(metrics)
