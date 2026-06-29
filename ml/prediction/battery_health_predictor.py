from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib

from ml.utils.feature_engineering import FEATURE_COLUMNS, build_feature_frame


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "ml" / "models" / "battery_health_model.joblib"


class BatteryHealthPredictor:
    def __init__(self, model_path: Path | str = MODEL_PATH) -> None:
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_columns = artifact.get("feature_columns", FEATURE_COLUMNS)
        self.metrics: dict[str, Any] = artifact.get("metrics", {})

    def predict_single(self, telemetry: dict[str, float]) -> float:
        feature_frame = build_feature_frame([telemetry])
        prediction = self.model.predict(feature_frame)[0]
        return float(prediction)

    def predict_batch(self, telemetry_records: list[dict[str, float]]) -> list[float]:
        feature_frame = build_feature_frame(telemetry_records)
        predictions = self.model.predict(feature_frame)
        return [float(value) for value in predictions]
