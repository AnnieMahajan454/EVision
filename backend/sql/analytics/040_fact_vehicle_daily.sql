-- One row per vehicle per local day with driving, battery and charging activity.

CREATE OR REPLACE VIEW analytics.fact_vehicle_daily AS
WITH reading_days AS (
    SELECT
        vehicle_id,
        (recorded_at AT TIME ZONE 'Asia/Kolkata')::date AS date,
        percentile_cont(0.5) WITHIN GROUP (ORDER BY soh_pct) AS soh_pct,
        max(odometer_km) AS odometer_km,
        avg(battery_temp_c) AS avg_battery_temp_c,
        max(battery_temp_c) AS max_battery_temp_c
    FROM public.telemetry
    GROUP BY 1, 2
),
trip_days AS (
    SELECT
        vehicle_id,
        trip_date AS date,
        count(*) AS trips,
        sum(distance_km) AS distance_km,
        sum(energy_used_kwh) AS energy_used_kwh,
        sum(duration_min) AS driving_min,
        avg(avg_ambient_temp_c) AS avg_ambient_temp_c
    FROM analytics.fact_trip
    GROUP BY 1, 2
),
charge_days AS (
    SELECT
        vehicle_id,
        session_date AS date,
        count(*) AS charging_sessions,
        count(*) FILTER (WHERE is_dc_fast) AS dc_fast_sessions,
        count(*) FILTER (WHERE charged_to_full) AS full_charge_sessions,
        sum(energy_delivered_kwh) AS energy_charged_kwh,
        coalesce(sum(energy_delivered_kwh) FILTER (WHERE is_dc_fast), 0) AS dc_fast_energy_kwh,
        sum(cost_inr) AS charging_cost_inr,
        sum(potential_saving_inr) AS potential_saving_inr
    FROM analytics.fact_charging_session
    GROUP BY 1, 2
),
activity AS (
    SELECT
        coalesce(r.vehicle_id, c.vehicle_id) AS vehicle_id,
        coalesce(r.date, c.date) AS date,
        r.soh_pct,
        r.odometer_km,
        r.avg_battery_temp_c,
        r.max_battery_temp_c,
        c.charging_sessions,
        c.dc_fast_sessions,
        c.full_charge_sessions,
        c.energy_charged_kwh,
        c.dc_fast_energy_kwh,
        c.charging_cost_inr,
        c.potential_saving_inr
    FROM reading_days r
    FULL JOIN charge_days c ON c.vehicle_id = r.vehicle_id AND c.date = r.date
)
SELECT
    a.vehicle_id,
    a.date,
    coalesce(t.trips, 0) AS trips,
    coalesce(t.distance_km, 0) AS distance_km,
    coalesce(t.energy_used_kwh, 0) AS energy_used_kwh,
    t.energy_used_kwh * 1000 / nullif(t.distance_km, 0) AS efficiency_wh_per_km,
    coalesce(t.driving_min, 0) AS driving_min,
    t.avg_ambient_temp_c,
    a.soh_pct,
    a.odometer_km,
    a.avg_battery_temp_c,
    a.max_battery_temp_c,
    coalesce(a.charging_sessions, 0) AS charging_sessions,
    coalesce(a.dc_fast_sessions, 0) AS dc_fast_sessions,
    coalesce(a.full_charge_sessions, 0) AS full_charge_sessions,
    coalesce(a.energy_charged_kwh, 0) AS energy_charged_kwh,
    coalesce(a.dc_fast_energy_kwh, 0) AS dc_fast_energy_kwh,
    coalesce(a.charging_cost_inr, 0) AS charging_cost_inr,
    coalesce(a.potential_saving_inr, 0) AS potential_saving_inr
FROM activity a
LEFT JOIN trip_days t ON t.vehicle_id = a.vehicle_id AND t.date = a.date;
