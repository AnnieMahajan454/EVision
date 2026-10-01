-- Dimension views for the Power BI star schema.

CREATE OR REPLACE VIEW analytics.dim_vehicle AS
SELECT
    v.id AS vehicle_id,
    v.vin,
    coalesce(v.nickname, v.make || ' ' || v.model) AS vehicle_name,
    v.make,
    v.model,
    v.make || ' ' || v.model AS make_model,
    v.model_year,
    v.battery_capacity_kwh,
    v.rated_range_km,
    v.battery_capacity_kwh * 1000 / v.rated_range_km AS rated_efficiency_wh_per_km,
    v.registered_on,
    u.email AS owner_email,
    v.is_active
FROM public.vehicles v
JOIN public.users u ON u.id = v.owner_id;


-- Continuous calendar covering all telemetry plus a year ahead for battery-health forecasts.
CREATE OR REPLACE VIEW analytics.dim_date AS
WITH bounds AS (
    SELECT
        coalesce(min((recorded_at AT TIME ZONE 'Asia/Kolkata')::date), current_date) AS first_day,
        greatest(coalesce(max((recorded_at AT TIME ZONE 'Asia/Kolkata')::date), current_date), current_date)
            + 400 AS last_day
    FROM public.telemetry
)
SELECT
    d::date AS date,
    extract(year FROM d)::int AS year,
    extract(quarter FROM d)::int AS quarter,
    extract(month FROM d)::int AS month,
    to_char(d, 'Mon YYYY') AS month_label,
    to_char(d, 'YYYY-MM') AS year_month,
    extract(isodow FROM d)::int AS day_of_week,
    to_char(d, 'Dy') AS day_name,
    extract(isodow FROM d) IN (6, 7) AS is_weekend,
    date_trunc('week', d)::date AS week_start
FROM bounds
CROSS JOIN LATERAL generate_series(bounds.first_day, bounds.last_day, interval '1 day') AS d;


-- Local clock hours with their time-of-day tariff; used for charging heatmaps.
CREATE OR REPLACE VIEW analytics.dim_hour AS
SELECT
    hour,
    lpad(hour::text, 2, '0') || ':00' AS hour_label,
    band AS tariff_band,
    rate_inr_per_kwh
FROM public.tariff_hours;
