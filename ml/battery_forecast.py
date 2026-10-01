"""SoH forecasting shared by the backtest, batch scoring and the API.

The regression estimates SoH from ageing/usage features. Its absolute estimate for any one
vehicle carries a bias (BMS calibration, proxy features) that is larger than a few months of
real fade. So forecasts are *anchored*: start from the vehicle's observed SoH and add only
the change the model expects as age and cycles accumulate.

    forecast(h) = observed_soh + model(features at t+h) - model(features at t)
"""

from collections.abc import Sequence

import pandas as pd

from ml.features import battery_health_design_matrix
from ml.registry import ModelArtifact


def project_features(
    latest: dict, horizons: Sequence[int], daily_km: float, rated_range_km: float
) -> pd.DataFrame:
    """Age the vehicle by each horizon at its recent mileage; stress factors stay as observed."""
    return pd.DataFrame(
        {
            "age_days": [latest["age_days"] + h for h in horizons],
            "equivalent_full_cycles": [
                latest["equivalent_full_cycles"] + daily_km * h / rated_range_km for h in horizons
            ],
            "lifetime_avg_battery_temp_c": latest["lifetime_avg_battery_temp_c"],
            "dc_fast_share": latest["dc_fast_share"],
            "high_soc_share": latest["high_soc_share"],
        }
    )


def forecast_soh(
    model: ModelArtifact,
    latest: dict,
    observed_soh: float,
    horizons: Sequence[int],
    daily_km: float,
    rated_range_km: float,
) -> list[float]:
    projected = project_features(latest, [0, *horizons], daily_km, rated_range_km)
    estimates = model.predict(battery_health_design_matrix(projected))
    now, future = estimates[0], estimates[1:]
    return [min(observed_soh + (value - now), 100.0) for value in future]
