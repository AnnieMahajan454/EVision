-- Daily state of health with the cumulative stress factors that drive degradation.
-- The ML battery-health model trains on this view (see ml/features.py).

CREATE OR REPLACE VIEW analytics.fact_battery_health AS
WITH cumulative AS (
    SELECT
        d.vehicle_id,
        d.date,
        d.soh_pct,
        d.odometer_km,
        d.date - v.registered_on AS age_days,
        v.rated_range_km,
        -- Expanding windows: everything observed for this vehicle up to and including the day.
        avg(d.avg_battery_temp_c) OVER w AS lifetime_avg_battery_temp_c,
        sum(d.dc_fast_energy_kwh) OVER w AS cum_dc_fast_energy_kwh,
        sum(d.energy_charged_kwh) OVER w AS cum_energy_charged_kwh,
        sum(d.full_charge_sessions) OVER w AS cum_full_charge_sessions,
        sum(d.charging_sessions) OVER w AS cum_charging_sessions,
        first_value(d.soh_pct) OVER (
            PARTITION BY d.vehicle_id ORDER BY (d.soh_pct IS NULL), d.date
        ) AS first_observed_soh_pct
    FROM analytics.fact_vehicle_daily d
    JOIN public.vehicles v ON v.id = d.vehicle_id
    WINDOW w AS (PARTITION BY d.vehicle_id ORDER BY d.date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT
    vehicle_id,
    date,
    soh_pct,
    100 - soh_pct AS capacity_fade_pct,
    first_observed_soh_pct - soh_pct AS fade_since_first_observed_pct,
    odometer_km,
    age_days,
    -- Approximation: one equivalent full cycle per rated range driven.
    odometer_km / rated_range_km AS equivalent_full_cycles,
    lifetime_avg_battery_temp_c,
    coalesce(cum_dc_fast_energy_kwh / nullif(cum_energy_charged_kwh, 0), 0) AS dc_fast_share,
    coalesce(cum_full_charge_sessions::float / nullif(cum_charging_sessions, 0), 0) AS high_soc_share
FROM cumulative
WHERE soh_pct IS NOT NULL;
