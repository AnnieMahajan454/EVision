import pandas as pd

FEATURE_COLUMNS = [
    "battery_percentage",
    "voltage_v",
    "current_a",
    "speed_kph",
    "motor_temperature_c",
    "ambient_temperature_c",
    "battery_capacity_kwh",
    "odometer_km",
]

TARGET_COLUMN = "range_km"

def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Basic sanity: fillna
    df = df.fillna(method="ffill").fillna(0)

    # Derived features
    df["power_kw"] = (df["voltage_v"] * df["current_a"]).abs() / 1000.0
    df["speed_mps"] = df["speed_kph"] / 3.6
    df["consumption_kw_per_km"] = df["power_kw"] / (df["speed_kph"].replace(0, 0.1))

    features = FEATURE_COLUMNS + ["power_kw", "speed_mps", "consumption_kw_per_km"]
    return df[features]
