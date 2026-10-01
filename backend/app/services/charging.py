"""Charging session storage and the off-peak charging recommendation."""

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import LOCAL_TIMEZONE
from app.models import ChargingSession, TariffHour, Vehicle
from app.schemas.charging import ChargingRecommendation, ChargingSessionCreate
from app.schemas.telemetry import IngestResult
from app.services.telemetry import latest_reading

IST = ZoneInfo(LOCAL_TIMEZONE)
HOME_CHARGER_KW = 7.2
AC_CHARGING_EFFICIENCY = 0.90  # grid kWh -> battery kWh
DEFAULT_DEPARTURE = time(8, 0)
SLOT = timedelta(minutes=15)


def ingest_sessions(
    db: Session, vehicle_id: uuid.UUID, sessions: list[ChargingSessionCreate]
) -> IngestResult:
    rows = [{"vehicle_id": vehicle_id, **session.model_dump()} for session in sessions]
    statement = (
        insert(ChargingSession)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_charging_vehicle_start")
        .returning(ChargingSession.id)
    )
    inserted = len(db.execute(statement).all())
    db.commit()
    return IngestResult(
        vehicle_id=vehicle_id, received=len(rows), inserted=inserted, duplicates=len(rows) - inserted
    )


def list_sessions(
    db: Session, vehicle_id: uuid.UUID, start: datetime | None, end: datetime | None, limit: int
) -> list[ChargingSession]:
    statement = select(ChargingSession).where(ChargingSession.vehicle_id == vehicle_id)
    if start is not None:
        statement = statement.where(ChargingSession.started_at >= start)
    if end is not None:
        statement = statement.where(ChargingSession.started_at < end)
    statement = statement.order_by(ChargingSession.started_at.desc()).limit(limit)
    return list(db.scalars(statement))


# --- Recommendation --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChargePlan:
    start: datetime
    finish: datetime
    cost_inr: float


def window_cost(start: datetime, grid_kwh: float, power_kw: float, rates: dict[int, float]) -> float:
    """Cost of drawing `grid_kwh` at a constant `power_kw` from `start`, priced per local hour."""
    remaining = grid_kwh
    cursor = start.astimezone(IST)
    cost = 0.0
    while remaining > 1e-9:
        slot_kwh = min(remaining, power_kw * SLOT.total_seconds() / 3600)
        cost += slot_kwh * rates[cursor.hour]
        remaining -= slot_kwh
        cursor += SLOT
    return cost


def cheapest_plan(
    now: datetime, departure: datetime, grid_kwh: float, power_kw: float, rates: dict[int, float]
) -> ChargePlan:
    """Pick the cheapest 15-minute-aligned start that still finishes before departure.

    Ties go to the latest start, so the pack spends as little time as possible sitting at a
    high state of charge.
    """
    duration = timedelta(hours=grid_kwh / power_kw)
    earliest = now.astimezone(IST)
    minutes_past_slot = (earliest.minute % 15) * 60 + earliest.second + earliest.microsecond / 1e6
    if minutes_past_slot:
        earliest += timedelta(seconds=15 * 60 - minutes_past_slot)
    latest = departure - duration

    best: ChargePlan | None = None
    candidate = earliest
    while candidate <= latest:
        cost = window_cost(candidate, grid_kwh, power_kw, rates)
        if best is None or cost <= best.cost_inr + 1e-9:
            best = ChargePlan(candidate, candidate + duration, cost)
        candidate += SLOT

    if best is None:  # not enough time before departure: start straight away
        best = ChargePlan(now, now + duration, window_cost(now, grid_kwh, power_kw, rates))
    return best


def next_departure(now: datetime, departure_time: time) -> datetime:
    local_now = now.astimezone(IST)
    candidate = datetime.combine(local_now.date(), departure_time, tzinfo=IST)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate


def _typical_departure(db: Session, vehicle_id: uuid.UUID, now: datetime) -> time:
    """Median local time of the first trip of each day over the last 30 days."""
    row = db.execute(
        text(
            """
            SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY first_start_s) AS median_start_s
            FROM (
                SELECT extract(epoch FROM min(started_at_local::time)) AS first_start_s
                FROM analytics.fact_trip
                WHERE vehicle_id = :vehicle_id AND started_at >= :since AND started_at < :now
                GROUP BY trip_date
            ) daily
            """
        ),
        {"vehicle_id": vehicle_id, "since": now - timedelta(days=30), "now": now},
    ).one()
    if row.median_start_s is None:
        return DEFAULT_DEPARTURE
    seconds = int(row.median_start_s)
    return time(seconds // 3600, (seconds % 3600) // 60)


def _avg_daily_energy_kwh(db: Session, vehicle_id: uuid.UUID, now: datetime) -> float:
    total = db.execute(
        text(
            """
            SELECT coalesce(sum(energy_used_kwh), 0)
            FROM analytics.fact_trip
            WHERE vehicle_id = :vehicle_id AND started_at >= :since AND started_at < :now
            """
        ),
        {"vehicle_id": vehicle_id, "since": now - timedelta(days=14), "now": now},
    ).scalar_one()
    return float(total) / 14


def _current_soc(db: Session, vehicle_id: uuid.UUID, now: datetime) -> tuple[float, float]:
    """SoC and SoH as of `now`, taking a charge that finished after the last drive into account."""
    reading = latest_reading(db, vehicle_id, before=now)
    soc = reading.soc_pct if reading else 50.0
    soh = (reading.soh_pct if reading and reading.soh_pct else None) or 100.0
    last_charge = db.scalars(
        select(ChargingSession)
        .where(ChargingSession.vehicle_id == vehicle_id, ChargingSession.ended_at <= now)
        .order_by(ChargingSession.ended_at.desc())
        .limit(1)
    ).first()
    if last_charge and (reading is None or last_charge.ended_at > reading.recorded_at):
        soc = last_charge.end_soc_pct
    return soc, soh


def recommend_charging(
    db: Session,
    vehicle: Vehicle,
    now: datetime,
    target_soc_pct: float,
    charger_kw: float = HOME_CHARGER_KW,
) -> ChargingRecommendation:
    rates = {row.hour: row.rate_inr_per_kwh for row in db.scalars(select(TariffHour))}
    current_soc, soh = _current_soc(db, vehicle.id, now)
    usable_capacity = vehicle.battery_capacity_kwh * soh / 100
    daily_kwh = _avg_daily_energy_kwh(db, vehicle.id, now)
    departure_time = _typical_departure(db, vehicle.id, now)
    departure = next_departure(now, departure_time)

    notes: list[str] = []
    battery_kwh = max(target_soc_pct - current_soc, 0) / 100 * usable_capacity
    grid_kwh = battery_kwh / AC_CHARGING_EFFICIENCY

    if grid_kwh < 0.1:
        notes.append(f"Battery is already at {current_soc:.0f}%, so no charge is needed before departure.")
        plan = ChargePlan(now, now, 0.0)
        cost_now = 0.0
    else:
        plan = cheapest_plan(now, departure, grid_kwh, charger_kw, rates)
        cost_now = window_cost(now, grid_kwh, charger_kw, rates)
        if plan.finish > departure:
            notes.append("There is not enough time to reach the target before the usual departure.")

    if target_soc_pct > 90:
        notes.append("Charging above 90% every day speeds up battery wear. Keep 100% for long trips.")
    if daily_kwh > 0:
        share = daily_kwh / usable_capacity * 100
        after_day = target_soc_pct - share
        notes.append(
            f"A typical day uses about {share:.0f}% of the battery, so you would finish the day "
            f"at around {after_day:.0f}%."
        )
        if after_day < 15:
            notes.append("That leaves under 15% in reserve. Consider a higher target or a midday top-up.")

    return ChargingRecommendation(
        current_soc_pct=round(current_soc, 1),
        target_soc_pct=target_soc_pct,
        energy_needed_kwh=round(grid_kwh, 2),
        avg_daily_energy_kwh=round(daily_kwh, 2),
        typical_departure=departure_time.strftime("%H:%M"),
        recommended_start=plan.start.astimezone(IST),
        expected_finish=plan.finish.astimezone(IST).replace(second=0, microsecond=0),
        estimated_cost_inr=round(plan.cost_inr, 2),
        cost_if_started_now_inr=round(cost_now, 2),
        saving_inr=round(cost_now - plan.cost_inr, 2),
        notes=notes,
    )
