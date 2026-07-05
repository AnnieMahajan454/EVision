import os
import joblib
import pandas as pd
from pathlib import Path
from ml.utils.range_feature_engineering import prepare_features


class RangePredictor:
    def __init__(self, model_path: str | None = None):
        repo_root = Path(__file__).resolve().parents[2]
        models_dir = Path(os.getenv("MODELS_DIR", repo_root / "ml" / "models"))
        if model_path is None:
            model_path = models_dir / "range_model.joblib"
        self.model_path = str(model_path)
        self._model = None

    def load(self):
        if self._model is None:
            self._model = joblib.load(self.model_path)
        return self._model

    def predict(self, telemetry: dict) -> float:
        # Accept telemetry dicts that may not include vehicle-level fields
        telemetry = telemetry.copy()
        telemetry.setdefault("battery_capacity_kwh", telemetry.get("battery_capacity_kwh", 75.0))
        telemetry.setdefault("odometer_km", telemetry.get("odometer_km", 0.0))

        df = pd.DataFrame([telemetry])
        X = prepare_features(df)
        model = self.load()
        pred = model.predict(X)
        return float(pred[0])
