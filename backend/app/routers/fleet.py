from datetime import date, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.deps import CurrentUser, DbSession

router = APIRouter(prefix="/fleet", tags=["fleet"])


class FleetSummary(BaseModel):
    period_start: date
    period_end: date
    vehicles: int
    distance_km: float
    energy_used_kwh: float
    avg_efficiency_wh_per_km: float | None
    charging_sessions: int
    charging_cost_inr: float
    potential_saving_inr: float
    avg_soh_pct: float | None


@router.get("/summary", response_model=FleetSummary)
def fleet_summary(user: CurrentUser, db: DbSession, days: int = Query(default=30, ge=1, le=365)) -> dict:
    """Headline KPIs for the signed-in operator's fleet over the last `days` days of data."""
    row = (
        db.execute(
            text(
                """
            WITH owned AS (
                SELECT id FROM vehicles WHERE owner_id = :owner_id AND is_active
            ),
            bounds AS (
                SELECT max(d.date) AS period_end, max(d.date) - (:days - 1) AS period_start
                FROM analytics.fact_vehicle_daily d JOIN owned o ON o.id = d.vehicle_id
            ),
            daily AS (
                SELECT d.* FROM analytics.fact_vehicle_daily d
                JOIN owned o ON o.id = d.vehicle_id, bounds b
                WHERE d.date BETWEEN b.period_start AND b.period_end
            ),
            latest_soh AS (
                SELECT DISTINCT ON (vehicle_id) soh_pct FROM daily
                WHERE soh_pct IS NOT NULL
                ORDER BY vehicle_id, date DESC
            )
            SELECT
                b.period_start,
                b.period_end,
                (SELECT count(*) FROM owned) AS vehicles,
                coalesce(sum(daily.distance_km), 0) AS distance_km,
                coalesce(sum(daily.energy_used_kwh), 0) AS energy_used_kwh,
                sum(daily.energy_used_kwh) * 1000 / nullif(sum(daily.distance_km), 0) AS avg_efficiency_wh_per_km,
                coalesce(sum(daily.charging_sessions), 0) AS charging_sessions,
                coalesce(sum(daily.charging_cost_inr), 0) AS charging_cost_inr,
                coalesce(sum(daily.potential_saving_inr), 0) AS potential_saving_inr,
                (SELECT avg(soh_pct) FROM latest_soh) AS avg_soh_pct
            FROM bounds b LEFT JOIN daily ON true
            GROUP BY b.period_start, b.period_end
            """
            ),
            {"owner_id": user.id, "days": days},
        )
        .mappings()
        .one()
    )

    result = {key: round(value, 2) if isinstance(value, float) else value for key, value in row.items()}
    if result["period_end"] is None:  # no data yet
        today = date.today()
        result.update(period_end=today, period_start=today - timedelta(days=days - 1))
    return result
