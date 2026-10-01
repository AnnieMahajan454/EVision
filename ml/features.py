"""Feature definitions shared by training, batch scoring and the API.

Keeping these in one place means a model is always served with exactly the columns it was
trained on.
"""

import numpy as np
import pandas as pd

# --- Battery health (state of health, %) -------------------------------------------------
#
# Lithium-ion capacity fade has two main components:
#   * calendar ageing  ~ sqrt(time), accelerated by high battery temperature
#   * cycle ageing     ~ energy throughput (equivalent full cycles), accelerated by
#                        DC fast charging and by routinely charging to a high SoC
# The design matrix encodes those terms so a regularised linear model can learn the
# coefficients and still extrapolate sensibly when we forecast 6-12 months ahead.
# A tree model would plateau outside the training range.

BATTERY_HEALTH_INPUTS = [
    "age_days",
    "equivalent_full_cycles",
    "lifetime_avg_battery_temp_c",
    "dc_fast_share",
    "high_soc_share",
]
BATTERY_HEALTH_TARGET = "soh_pct"

REFERENCE_BATTERY_TEMP_C = 25.0


def battery_health_design_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    sqrt_age = np.sqrt(frame["age_days"].clip(lower=0) / 365.0)
    heat = (frame["lifetime_avg_battery_temp_c"] - REFERENCE_BATTERY_TEMP_C).clip(lower=0)
    cycles = frame["equivalent_full_cycles"] / 100.0
    return pd.DataFrame(
        {
            "sqrt_age": sqrt_age,
            "sqrt_age_x_heat": sqrt_age * heat,
            "cycles": cycles,
            "cycles_x_dc_fast": cycles * frame["dc_fast_share"],
            "cycles_x_high_soc": cycles * frame["high_soc_share"],
        },
        index=frame.index,
    )


# --- Range ---------------------------------------------------------------------------------
#
# Range is not predicted directly. The model predicts energy consumption (Wh/km) for the
# expected driving conditions. Range then follows from the energy left in the pack:
#     range_km = soc * capacity * soh / consumption
# This keeps the model valid at any state of charge. It also makes errors easy to read:
# a 5% consumption error is a 5% range error.

RANGE_INPUTS = [
    "avg_speed_kph",
    "avg_ambient_temp_c",
    "soh_pct",
    "battery_capacity_kwh",
    "trailing_efficiency_wh_per_km",
]
RANGE_TARGET = "efficiency_wh_per_km"


def range_design_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[RANGE_INPUTS].astype(float)


def usable_energy_kwh(soc_pct: float, capacity_kwh: float, soh_pct: float) -> float:
    return soc_pct / 100.0 * capacity_kwh * soh_pct / 100.0


def range_from_efficiency(energy_kwh: float, efficiency_wh_per_km: float) -> float:
    return energy_kwh * 1000.0 / efficiency_wh_per_km
