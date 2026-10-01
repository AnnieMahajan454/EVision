-- Model output for Power BI, written back by ml/score_fleet.py.

-- Range predictions made at the start of each out-of-sample trip, compared with what happened.
CREATE OR REPLACE VIEW analytics.fact_range_prediction AS
SELECT
    p.id AS prediction_id,
    t.trip_id,
    p.vehicle_id,
    t.trip_date,
    t.started_at,
    p.model_version,
    t.speed_band,
    t.temperature_band,
    t.distance_km,
    (p.features ->> 'predicted_efficiency_wh_per_km')::float AS predicted_efficiency_wh_per_km,
    t.trailing_efficiency_wh_per_km AS baseline_efficiency_wh_per_km,
    t.efficiency_wh_per_km AS actual_efficiency_wh_per_km,
    p.predicted_value AS predicted_range_km,
    p.predicted_value * (p.features ->> 'predicted_efficiency_wh_per_km')::float
        / t.trailing_efficiency_wh_per_km AS baseline_range_km,
    p.predicted_value * (p.features ->> 'predicted_efficiency_wh_per_km')::float
        / t.efficiency_wh_per_km AS actual_range_km
FROM public.predictions p
JOIN analytics.fact_trip t ON t.vehicle_id = p.vehicle_id AND t.started_at = p.reference_time
WHERE p.prediction_type = 'range'
  AND p.features ->> 'source' = 'batch';


-- Latest batch SoH forecast curve per vehicle (horizon 0 = today's model estimate).
CREATE OR REPLACE VIEW analytics.fact_battery_health_forecast AS
SELECT
    p.id AS prediction_id,
    p.vehicle_id,
    (p.reference_time AT TIME ZONE 'UTC')::date AS as_of_date,
    p.horizon_days,
    (p.reference_time AT TIME ZONE 'UTC')::date + p.horizon_days AS target_date,
    p.predicted_value AS predicted_soh_pct,
    (p.features ->> 'assumed_daily_km')::float AS assumed_daily_km,
    p.model_version,
    p.created_at
FROM public.predictions p
WHERE p.prediction_type = 'battery_health'
  AND p.features ->> 'source' = 'batch';
