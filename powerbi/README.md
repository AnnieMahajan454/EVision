# EVision Power BI report

The report connects to PostgreSQL in **Import** mode and reads only the `analytics` schema. All business logic lives in SQL views (`backend/sql/analytics/`), so the report stays thin and the API and ML pipeline use the same numbers.

| File | Purpose |
|---|---|
| `connection.pq` | Parameterised Power Query source (`PgServer`, `PgDatabase`) |
| `measures.dax` | All DAX measures, grouped by page |
| `EVision.theme.json` | Report theme (View → Themes → Browse for themes) |
| `EVision.pbix` | The report itself (add after building, see below) |
| `screenshots/` | Page exports used in the main README |

## 1. Connect

1. Run the pipeline once so the database has data and predictions (see the main README: migrate → simulate → train → score).
2. Power BI Desktop → **Get data → PostgreSQL database**. Server `localhost:5432`, database `evision`, Data Connectivity mode **Import**.
3. In the Navigator tick the nine views under `analytics` (listed in `connection.pq`).
4. Apply the theme `EVision.theme.json`.

> Power BI Desktop ships with the Npgsql provider since the Oct-2019 release. If you see "provider not found", install Npgsql 4.0.x with *GAC installation* enabled.

## 2. Model

Star schema with three shared dimensions. All relationships are one-to-many, single direction, from dimension to fact.

```
                 dim_vehicle[vehicle_id]
                          │
   ┌─────────────┬────────┼────────────────┬──────────────────┬──────────────────────┐
fact_trip   fact_vehicle_daily   fact_charging_session   fact_battery_health   fact_range_prediction
   │               │                     │                       │             fact_battery_health_forecast
   └───────────────┴──────────┬──────────┴───────────────────────┘
                     dim_date[date]
```

| From (one) | To (many) |
|---|---|
| `dim_vehicle[vehicle_id]` | `vehicle_id` on every fact view |
| `dim_date[date]` | `fact_trip[trip_date]`, `fact_vehicle_daily[date]`, `fact_charging_session[session_date]`, `fact_battery_health[date]`, `fact_range_prediction[trip_date]`, `fact_battery_health_forecast[target_date]` |
| `dim_hour[hour]` | `fact_charging_session[start_hour]`, `fact_trip[start_hour]` |

Model settings:

- Mark `dim_date` as the date table (Table tools → Mark as date table → `date`).
- Sort `dim_date[month_label]` by `year_month`, and `dim_hour[hour_label]` by `hour`.
- Hide all `vehicle_id`, `date` and `hour` keys on the fact tables, so users slice by dimensions only.
- Formats: `%` measures as percentage with 1 decimal place; `₹` measures as currency with 0 decimals.
- Create a `_Measures` table and paste in `measures.dax`. Use display folders *Fleet*, *Battery*, *Range* and *Charging*.

## 3. Pages

Canvas 1280 × 720. Every page has a left-hand slicer panel with **Date** (between), **Make/Model** and **Vehicle** (`dim_vehicle[vehicle_name]`), synced across pages.

### Page 1: Fleet Overview

| Visual | Fields |
|---|---|
| KPI cards | Vehicles · Distance (km) · Avg Efficiency (Wh/km) · Charging Cost (₹) · Latest SoH % |
| Line chart | X `dim_date[date]`, Y Distance (km); secondary Y Avg Efficiency (Wh/km) |
| Clustered bar | Y `dim_vehicle[make_model]`, X Avg Efficiency (Wh/km) and Rated Efficiency (Wh/km) |
| Table | vehicle_name, Distance (km), Avg Efficiency, Latest SoH %, Charging Cost per km (₹); conditional icons on SoH |

### Page 2: Battery Health

| Visual | Fields |
|---|---|
| KPI cards | Latest SoH % · Vehicles Below 90% SoH · Fade per 10,000 km (pp) · Forecast SoH in 12 Months % |
| Line chart (SoH trend) | X `dim_date[date]`, Y `fact_battery_health[soh_pct]` (average), Legend `vehicle_name`; filter the visual to top/bottom 5 by Latest SoH % |
| Line chart (forecast) | X `fact_battery_health_forecast[horizon_days]`, Y Predicted SoH %, Legend `vehicle_name`; constant line at 80% (typical warranty threshold) |
| Scatter (degradation drivers) | X DC Fast Energy Share %, Y SoH Fade in Period (pp), Size Distance (km), Details `vehicle_name` |
| Bar | Y `vehicle_name`, X Full-Charge Session Share % (shows the "always charge to 100%" habit) |

Narrative: cabs and DC-heavy vehicles fade fastest. Charging habits (DC share, routine 100% charges) separate vehicles more than mileage alone does.

### Page 3: Range

| Visual | Fields |
|---|---|
| KPI cards | Real-World Range (km) · Rated Range (km) · Range vs Rated % · Range Prediction Error % · Error Reduction vs Baseline % |
| Clustered column | X `fact_trip[speed_band]`, Y Trip Efficiency (Wh/km) |
| Clustered column | X `fact_trip[temperature_band]`, Y Real-World Range (km) |
| Matrix heatmap | Rows `speed_band`, Columns `temperature_band`, Values Real-World Range (km); background colour scale |
| Scatter (model accuracy) | X Actual Range (km), Y Predicted Range (km), Details `fact_range_prediction[trip_id]`; add a y = x reference line via the Analytics pane |
| Clustered bar | Y `make_model`, X Real-World Range (km) and Rated Range (km) |

### Page 4: Charging Optimisation

| Visual | Fields |
|---|---|
| KPI cards | Charging Cost (₹) · Avg Cost per kWh (₹) · Home Energy at Peak % · Potential Saving (₹) · Annualised Saving (₹) |
| Matrix heatmap | Rows `dim_date[day_name]`, Columns `dim_hour[hour_label]`, Values Charging Sessions; background colour scale |
| Stacked column | X `dim_hour[hour_label]`, Y Energy Charged (kWh), Legend `dim_hour[tariff_band]` |
| Donut | Legend `fact_charging_session[charger_type]`, Values Energy Charged (kWh) |
| Table (action list) | vehicle_name, Charging Sessions, Home Energy at Peak %, Potential Saving (₹), DC Past-Taper Share %, sorted by saving |
| Card + text | Link to `GET /api/v1/vehicles/{id}/charging/recommendation` for per-vehicle schedules |

## 4. Refresh

The views are always current, so a refresh is just **Home → Refresh**. After new telemetry arrives, re-run `python -m ml.score_fleet` first so predictions are up to date.

For scheduled refresh in the Power BI Service, install the on-premises data gateway (or point `PgServer` at a cloud Postgres such as Neon, Supabase or Render).

## 5. Publishing artefacts

Save the report as `powerbi/EVision.pbix`. Export each page (File → Export → PDF, or a screenshot) to `powerbi/screenshots/01-fleet-overview.png` … `04-charging.png`. The main README links to them.
