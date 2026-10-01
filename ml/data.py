"""Read training data straight from the analytics views, so the ML features are the same
numbers that appear in the Power BI dashboards."""

import os

import pandas as pd
from sqlalchemy import Engine, create_engine, text

DEFAULT_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/evision"


def get_engine() -> Engine:
    return create_engine(os.environ.get("DATABASE_URL", DEFAULT_URL))


def read_sql(engine: Engine, query: str, **params) -> pd.DataFrame:
    with engine.connect() as connection:
        return pd.read_sql(text(query), connection, params=params)


def load_battery_health(engine: Engine) -> pd.DataFrame:
    frame = read_sql(
        engine,
        """
        SELECT b.*, v.rated_range_km
        FROM analytics.fact_battery_health b
        JOIN public.vehicles v ON v.id = b.vehicle_id
        ORDER BY b.vehicle_id, b.date
        """,
    )
    frame["date"] = pd.to_datetime(frame["date"])
    # Stress shares are expanding averages; give each vehicle two weeks before trusting them.
    frame["days_observed"] = frame.groupby("vehicle_id").cumcount()
    return frame[frame["days_observed"] >= 14].reset_index(drop=True)


def load_trips(engine: Engine) -> pd.DataFrame:
    frame = read_sql(
        engine,
        """
        SELECT * FROM analytics.fact_trip
        WHERE trailing_efficiency_wh_per_km IS NOT NULL
        ORDER BY started_at
        """,
    )
    frame["trip_date"] = pd.to_datetime(frame["trip_date"])
    return frame


def recent_daily_km(engine: Engine) -> pd.DataFrame:
    """Average km/day over each vehicle's last 30 days of data (used to project ageing)."""
    return read_sql(
        engine,
        """
        WITH last_day AS (
            SELECT vehicle_id, max(date) AS last_date FROM analytics.fact_vehicle_daily GROUP BY 1
        )
        SELECT d.vehicle_id, sum(d.distance_km) / 30.0 AS daily_km
        FROM analytics.fact_vehicle_daily d
        JOIN last_day l ON l.vehicle_id = d.vehicle_id AND d.date > l.last_date - 30
        GROUP BY d.vehicle_id
        """,
    )
