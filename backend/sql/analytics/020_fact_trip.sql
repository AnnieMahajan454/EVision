-- Trips reconstructed from raw telemetry (gaps-and-islands).
--
-- A new trip starts whenever a vehicle has been silent for more than 5 minutes. Energy is
-- derived from the SoC drop scaled by the pack's current usable capacity (capacity x SoH),
-- which is how most telematics platforms estimate consumption without a dedicated energy meter.

CREATE OR REPLACE VIEW analytics.fact_trip AS
WITH flagged AS (
    SELECT
        t.*,
        CASE
            WHEN t.recorded_at - lag(t.recorded_at) OVER w <= interval '5 minutes' THEN 0
            ELSE 1
        END AS is_new_trip
    FROM public.telemetry t
    WINDOW w AS (PARTITION BY t.vehicle_id ORDER BY t.recorded_at)
),
sequenced AS (
    SELECT
        f.*,
        sum(f.is_new_trip) OVER (PARTITION BY f.vehicle_id ORDER BY f.recorded_at) AS trip_seq
    FROM flagged f
),
trips AS (
    SELECT
        vehicle_id,
        trip_seq,
        min(recorded_at) AS started_at,
        max(recorded_at) AS ended_at,
        count(*) AS reading_count,
        max(odometer_km) - min(odometer_km) AS distance_km,
        (array_agg(soc_pct ORDER BY recorded_at))[1] AS start_soc_pct,
        (array_agg(soc_pct ORDER BY recorded_at DESC))[1] AS end_soc_pct,
        avg(speed_kph) AS avg_speed_kph,
        max(speed_kph) AS max_speed_kph,
        avg(ambient_temp_c) AS avg_ambient_temp_c,
        avg(battery_temp_c) AS avg_battery_temp_c,
        max(battery_temp_c) AS max_battery_temp_c,
        max(motor_temp_c) AS max_motor_temp_c,
        avg(soh_pct) AS soh_pct
    FROM sequenced
    GROUP BY vehicle_id, trip_seq
),
measured AS (
    SELECT
        tr.*,
        v.battery_capacity_kwh,
        (tr.start_soc_pct - tr.end_soc_pct) / 100.0
            * v.battery_capacity_kwh * coalesce(tr.soh_pct, 100) / 100.0 AS energy_used_kwh
    FROM trips tr
    JOIN public.vehicles v ON v.id = tr.vehicle_id
    -- Very short hops are dominated by SoC rounding, so they are left out of efficiency analysis.
    WHERE tr.distance_km >= 2
      AND tr.start_soc_pct > tr.end_soc_pct
),
with_efficiency AS (
    SELECT m.*, m.energy_used_kwh * 1000 / m.distance_km AS efficiency_wh_per_km
    FROM measured m
)
SELECT
    e.vehicle_id::text || '-' || e.trip_seq AS trip_id,
    e.vehicle_id,
    (e.started_at AT TIME ZONE 'Asia/Kolkata')::date AS trip_date,
    e.started_at,
    e.ended_at,
    e.started_at AT TIME ZONE 'Asia/Kolkata' AS started_at_local,
    extract(hour FROM e.started_at AT TIME ZONE 'Asia/Kolkata')::int AS start_hour,
    extract(epoch FROM e.ended_at - e.started_at) / 60 AS duration_min,
    e.reading_count,
    e.distance_km,
    e.start_soc_pct,
    e.end_soc_pct,
    e.energy_used_kwh,
    e.efficiency_wh_per_km,
    e.avg_speed_kph,
    e.max_speed_kph,
    e.avg_ambient_temp_c,
    e.avg_battery_temp_c,
    e.max_battery_temp_c,
    e.max_motor_temp_c,
    e.soh_pct,
    e.battery_capacity_kwh,
    -- Mean consumption of this vehicle's previous 20 trips: the baseline a driver would use.
    avg(e.efficiency_wh_per_km) OVER (
        PARTITION BY e.vehicle_id ORDER BY e.started_at ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
    ) AS trailing_efficiency_wh_per_km,
    e.battery_capacity_kwh * coalesce(e.soh_pct, 100) / 100 * 1000 / e.efficiency_wh_per_km
        AS full_charge_range_km,
    CASE
        WHEN e.avg_speed_kph < 30 THEN '1 City (<30 km/h)'
        WHEN e.avg_speed_kph < 55 THEN '2 Suburban (30-55)'
        WHEN e.avg_speed_kph < 80 THEN '3 Highway (55-80)'
        ELSE '4 Fast highway (80+)'
    END AS speed_band,
    CASE
        WHEN e.avg_ambient_temp_c < 25 THEN '1 Mild (<25 C)'
        WHEN e.avg_ambient_temp_c < 32 THEN '2 Warm (25-32 C)'
        WHEN e.avg_ambient_temp_c < 38 THEN '3 Hot (32-38 C)'
        ELSE '4 Very hot (38 C+)'
    END AS temperature_band
FROM with_efficiency e;
