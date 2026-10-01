# ML pipeline

Both models train directly from the PostgreSQL `analytics` views. Their predictions are written back to the `predictions` table, where Power BI picks them up.

```bash
python -m ml.train_battery_health   # -> ml/artifacts/battery_health.joblib
python -m ml.train_range            # -> ml/artifacts/range.joblib
python -m ml.score_fleet            # writes batch predictions to Postgres
```

All three read `DATABASE_URL`. Artifacts go to `MODELS_DIR` (default `ml/artifacts`, git-ignored). The API loads them from the same place: `POST /vehicles/{id}/predictions/...` returns `503` until they exist.

## Battery state of health

**Source:** `analytics.fact_battery_health`, one row per vehicle per day. The target is the BMS-reported SoH.

**Features** (`ml/features.py`) mirror the two degradation mechanisms of lithium-ion cells:

| Term | Meaning |
|---|---|
| `sqrt_age` | calendar ageing grows with √time |
| `sqrt_age × heat` | ...faster when the pack runs above 25 °C |
| `cycles` | equivalent full cycles (odometer ÷ rated range) |
| `cycles × dc_fast_share` | extra wear from DC fast charging |
| `cycles × high_soc_share` | extra wear from routinely charging to 100% |

**Model:** standardised ridge regression. A linear model on physically motivated terms keeps forecasts sensible 12 months beyond the data, where a tree ensemble would just flatten out, and its coefficients are interpretable ("SoH lost per 100 cycles").

**Forecasting** (`ml/battery_forecast.py`): forecasts are *anchored*. The model's absolute estimate for any one vehicle carries about 0.4 pp of bias (BMS calibration, proxy features), which is more than several months of real fade. So a forecast starts from the vehicle's observed SoH (median of the last 7 days) and adds only the change the model expects as age and cycles accumulate:

```
forecast(h) = observed_soh + model(features at t+h) − model(features at t)
```

Without anchoring, the 45-day backtest MAE was 0.36 pp, worse than assuming no change. With anchoring it is 0.037 pp.

**Evaluation:**

| Check | MAE (pp) |
|---|---|
| Leave-vehicles-out CV (GroupKFold): absolute SoH estimate for unseen vehicles | 0.44 |
| 45-day forecast backtest: anchored model | **0.037** |
| ...baseline "SoH stays the same" | 0.155 |
| ...baseline per-vehicle linear trend | 0.032 |

Over 45 days, fade is close to linear, so a trend line does about as well. The model's value is at longer horizons, where √time calendar ageing slows down and a straight line overshoots. It also attributes fade to its causes, such as DC fast charging and routine 100% charges, which a trend line can't do.

## Range

Range isn't predicted directly. The model predicts consumption (Wh/km) for the expected conditions:

```
range_km = SoC × capacity × SoH × 1000 / predicted_Wh_per_km
```

so one model works at any state of charge, for any pack size and at any battery age.

**Source:** `analytics.fact_trip`, trips reconstructed from telemetry.

**Features:** average speed, ambient temperature, SoH, pack capacity, and the vehicle's average consumption over its previous 20 trips (which captures driver and vehicle effects).

**Model:** `HistGradientBoostingRegressor`. It captures the non-linear speed curve (stop-go losses below about 40 km/h, aerodynamic drag above about 70 km/h) and the air-conditioning load in heat.

**Evaluation:** time-based hold-out (last 28 days, 2,230 trips). The baseline is the trailing 20-trip average, which is what most in-car range estimates use.

| | MAE (Wh/km) | MAPE |
|---|---|---|
| Gradient boosting | 5.05 | **3.5%** |
| Trailing 20-trip average | 6.43 | 4.6% |

## Batch scoring → Power BI

`score_fleet.py` writes:

- a range prediction "at departure" for every trip after the training cutoff → `analytics.fact_range_prediction` (predicted vs actual vs baseline);
- a 0–360-day SoH forecast curve for every vehicle, in 15-day steps → `analytics.fact_battery_health_forecast`.

Re-running replaces the previous batch, so it is safe to schedule after each data load.
