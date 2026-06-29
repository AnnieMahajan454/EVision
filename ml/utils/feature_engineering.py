from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


FEATURE_COLUMNS = [
    "battery_percentage",
    "voltage_v",
    "current_a",
    "speed_kph",
    "motor_temperature_c",
    "ambient_temperature_c",
    "distance_km",
]

TARGET_COLUMN = "battery_health"


@dataclass(frozen=True)
class TelemetryFeatures:
    battery_percentage: float
    voltage_v: float
    current_a: float
    speed_kph: float
    motor_temperature_c: float
    ambient_temperature_c: float
    distance_km: float


def load_training_frame(csv_path: str) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    missing_columns = [column for column in FEATURE_COLUMNS + [TARGET_COLUMN] if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    return frame


def build_feature_frame(features: list[TelemetryFeatures] | list[dict[str, float]]) -> pd.DataFrame:
    frame = pd.DataFrame(features)
    return frame[FEATURE_COLUMNS]
