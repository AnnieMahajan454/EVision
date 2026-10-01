"""time-of-day tariff and analytics views

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEWS_DIR = Path(__file__).resolve().parents[2] / "sql" / "analytics"

# Residential time-of-day tariff (INR/kWh, incl. duties) modelled on Indian state ToD schemes:
# cheapest overnight, most expensive in the evening demand peak.
OFF_PEAK, NORMAL, PEAK = ("off_peak", 5.80), ("normal", 7.40), ("peak", 9.25)


def band_for(hour: int) -> tuple[str, float]:
    if hour >= 22 or hour < 6:
        return OFF_PEAK
    if 18 <= hour < 22:
        return PEAK
    return NORMAL


def create_analytics_views() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    # Run on the raw psycopg cursor without parameters, so the files can hold several
    # statements and literal ':' / '%' characters without being parsed as bind placeholders.
    cursor = op.get_bind().connection.dbapi_connection.cursor()
    for sql_file in sorted(VIEWS_DIR.glob("*.sql")):
        cursor.execute(sql_file.read_text(encoding="utf-8"))


def upgrade() -> None:
    tariff_hours = sa.table(
        "tariff_hours",
        sa.column("hour", sa.SmallInteger),
        sa.column("band", sa.String),
        sa.column("rate_inr_per_kwh", sa.Float),
    )
    op.bulk_insert(
        tariff_hours,
        [{"hour": h, "band": band_for(h)[0], "rate_inr_per_kwh": band_for(h)[1]} for h in range(24)],
    )
    create_analytics_views()


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
    op.execute("DELETE FROM tariff_hours")
