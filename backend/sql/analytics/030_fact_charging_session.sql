-- Charging sessions enriched with time-of-day cost and optimisation flags.
--
-- Home/depot sessions are costed by splitting each session across the local clock hours it
-- overlaps and pricing each slice at that hour's tariff. Charging power is taken as constant,
-- which is a good approximation for AC charging. "Potential saving" is what the same energy
-- would have cost entirely at the off-peak rate. Public sessions use the billed amount and
-- cannot be shifted.

CREATE OR REPLACE VIEW analytics.fact_charging_session AS
WITH localised AS (
    SELECT
        c.*,
        c.started_at AT TIME ZONE 'Asia/Kolkata' AS started_at_local,
        c.ended_at AT TIME ZONE 'Asia/Kolkata' AS ended_at_local
    FROM public.charging_sessions c
),
hourly AS (
    SELECT
        l.id,
        extract(hour FROM h.hour_start)::int AS hour,
        extract(epoch FROM least(l.ended_at_local, h.hour_start + interval '1 hour')
                          - greatest(l.started_at_local, h.hour_start))
            / extract(epoch FROM l.ended_at_local - l.started_at_local) AS energy_share
    FROM localised l
    CROSS JOIN LATERAL generate_series(
        date_trunc('hour', l.started_at_local),
        l.ended_at_local - interval '1 microsecond',
        interval '1 hour'
    ) AS h(hour_start)
),
priced AS (
    SELECT
        hourly.id,
        sum(hourly.energy_share * t.rate_inr_per_kwh) AS blended_rate_inr_per_kwh,
        coalesce(sum(hourly.energy_share) FILTER (WHERE t.band = 'peak'), 0) AS peak_energy_share
    FROM hourly
    JOIN public.tariff_hours t ON t.hour = hourly.hour
    GROUP BY hourly.id
),
off_peak AS (
    SELECT min(rate_inr_per_kwh) AS rate_inr_per_kwh FROM public.tariff_hours
)
SELECT
    l.id AS session_id,
    l.vehicle_id,
    l.started_at_local::date AS session_date,
    l.started_at,
    l.ended_at,
    l.started_at_local,
    extract(hour FROM l.started_at_local)::int AS start_hour,
    l.charger_type::text AS charger_type,
    l.charger_type = 'dc_fast' AS is_dc_fast,
    extract(epoch FROM l.ended_at - l.started_at) / 60 AS duration_min,
    l.start_soc_pct,
    l.end_soc_pct,
    l.end_soc_pct - l.start_soc_pct AS soc_added_pct,
    l.energy_delivered_kwh,
    l.energy_delivered_kwh / (extract(epoch FROM l.ended_at - l.started_at) / 3600) AS avg_power_kw,
    l.max_power_kw,
    CASE WHEN l.charger_type = 'home_ac' THEN th.band ELSE 'public' END AS tariff_band,
    CASE WHEN l.charger_type = 'home_ac' THEN p.peak_energy_share ELSE 0 END AS peak_energy_share,
    coalesce(l.cost_inr, l.energy_delivered_kwh * p.blended_rate_inr_per_kwh) AS cost_inr,
    coalesce(l.cost_inr, l.energy_delivered_kwh * p.blended_rate_inr_per_kwh)
        / nullif(l.energy_delivered_kwh, 0) AS effective_rate_inr_per_kwh,
    CASE
        WHEN l.charger_type = 'home_ac'
            THEN l.energy_delivered_kwh * (p.blended_rate_inr_per_kwh - o.rate_inr_per_kwh)
        ELSE 0
    END AS potential_saving_inr,
    l.end_soc_pct >= 95 AS charged_to_full,
    -- DC power tapers sharply above ~80% SoC: slow, expensive, and hard on the cells.
    l.charger_type = 'dc_fast' AND l.end_soc_pct > 85 AS dc_fast_past_taper
FROM localised l
LEFT JOIN priced p ON p.id = l.id
LEFT JOIN public.tariff_hours th ON th.hour = extract(hour FROM l.started_at_local)
CROSS JOIN off_peak o;
