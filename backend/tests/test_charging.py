from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.database import engine
from app.services.charging import cheapest_plan, next_departure, window_cost

IST = ZoneInfo("Asia/Kolkata")
RATES = {h: 5.80 if (h >= 22 or h < 6) else 9.25 if 18 <= h < 22 else 7.40 for h in range(24)}


def session(start_local: datetime, hours: float, kwh: float, charger="home_ac", **extra) -> dict:
    return {
        "started_at": start_local.isoformat(),
        "ended_at": (start_local + timedelta(hours=hours)).isoformat(),
        "charger_type": charger,
        "start_soc_pct": 30,
        "end_soc_pct": 80,
        "energy_delivered_kwh": kwh,
        **extra,
    }


def test_window_cost_spans_tariff_bands():
    # 7.2 kW for 1 h starting 21:30 -> half at peak (9.25), half at off-peak (5.80)
    start = datetime(2026, 9, 1, 21, 30, tzinfo=IST)
    assert window_cost(start, 7.2, 7.2, RATES) == pytest.approx(3.6 * 9.25 + 3.6 * 5.80)


def test_cheapest_plan_moves_charging_off_peak():
    now = datetime(2026, 9, 1, 19, 0, tzinfo=IST)
    departure = next_departure(now, datetime.strptime("08:00", "%H:%M").time())
    plan = cheapest_plan(now, departure, grid_kwh=21.6, power_kw=7.2, rates=RATES)  # 3 h

    assert plan.cost_inr == pytest.approx(21.6 * 5.80)
    assert plan.finish <= departure
    # Ties go to the latest start so the pack does not sit full overnight.
    assert plan.start.astimezone(IST).hour == 3 and plan.finish.astimezone(IST).hour == 6


def test_plan_starts_now_when_there_is_no_time():
    now = datetime(2026, 9, 1, 7, 0, tzinfo=IST)
    departure = datetime(2026, 9, 1, 8, 0, tzinfo=IST)
    plan = cheapest_plan(now, departure, grid_kwh=21.6, power_kw=7.2, rates=RATES)
    assert plan.start == now and plan.finish > departure


def test_session_ingest_validation_and_costing(client, auth_headers, vehicle):
    url = f"/api/v1/vehicles/{vehicle['id']}/charging/sessions"
    peak = session(datetime(2026, 9, 1, 19, 0, tzinfo=IST), 2, 14.4)
    dc = session(datetime(2026, 9, 2, 13, 0, tzinfo=IST), 0.5, 20, "dc_fast", end_soc_pct=92, cost_inr=430)

    result = client.post(url, json={"sessions": [peak, dc]}, headers=auth_headers).json()
    assert result["inserted"] == 2
    assert client.post(url, json={"sessions": [peak]}, headers=auth_headers).json()["duplicates"] == 1

    backwards = {**peak, "ended_at": peak["started_at"]}
    assert client.post(url, json={"sessions": [backwards]}, headers=auth_headers).status_code == 422

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT charger_type, tariff_band, cost_inr, potential_saving_inr, dc_fast_past_taper "
                "FROM analytics.fact_charging_session ORDER BY started_at"
            )
        ).all()

    home, fast = rows
    assert home.tariff_band == "peak"
    assert home.cost_inr == pytest.approx(14.4 * 9.25)
    assert home.potential_saving_inr == pytest.approx(14.4 * (9.25 - 5.80))
    assert fast.cost_inr == 430 and fast.potential_saving_inr == 0 and fast.dc_fast_past_taper


def test_recommendation_endpoint(client, auth_headers, vehicle):
    base = f"/api/v1/vehicles/{vehicle['id']}"
    # Last drive ended at 40% SoC, 18:00 IST.
    reading = {
        "recorded_at": datetime(2026, 9, 1, 18, 0, tzinfo=IST).isoformat(),
        "odometer_km": 1000,
        "speed_kph": 0,
        "soc_pct": 40,
        "soh_pct": 100,
        "battery_voltage_v": 350,
        "battery_current_a": 0,
        "battery_temp_c": 30,
    }
    client.post(f"{base}/telemetry", json={"readings": [reading]}, headers=auth_headers)

    response = client.get(
        f"{base}/charging/recommendation",
        params={"target_soc_pct": 80, "at": datetime(2026, 9, 1, 19, 0, tzinfo=IST).isoformat()},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    rec = response.json()
    expected_kwh = 0.40 * 40.5 / 0.90
    assert rec["energy_needed_kwh"] == pytest.approx(expected_kwh, abs=0.01)
    assert rec["typical_departure"] == "08:00"  # no trip history -> default
    assert rec["estimated_cost_inr"] == pytest.approx(expected_kwh * 5.80, abs=0.01)
    assert rec["saving_inr"] > 0
    assert datetime.fromisoformat(rec["recommended_start"]).astimezone(IST).hour in (22, 23, 0, 1, 2, 3, 4)


def test_recommendation_after_full_charge_needs_nothing(client, auth_headers, vehicle):
    url = f"/api/v1/vehicles/{vehicle['id']}/charging"
    client.post(
        f"{url}/sessions",
        json={"sessions": [session(datetime(2026, 9, 1, 0, 0, tzinfo=IST), 4, 25, end_soc_pct=90)]},
        headers=auth_headers,
    )
    rec = client.get(
        f"{url}/recommendation",
        params={"at": datetime(2026, 9, 1, 7, 0, tzinfo=IST).isoformat()},
        headers=auth_headers,
    ).json()
    assert rec["current_soc_pct"] == 90 and rec["energy_needed_kwh"] == 0


def test_recommendation_ignores_data_after_the_as_of_time(client, auth_headers, vehicle):
    base = f"/api/v1/vehicles/{vehicle['id']}"
    reading = {
        "recorded_at": datetime(2026, 9, 1, 18, 0, tzinfo=IST).isoformat(),
        "odometer_km": 1000,
        "speed_kph": 0,
        "soc_pct": 40,
        "soh_pct": 100,
        "battery_voltage_v": 350,
        "battery_current_a": 0,
        "battery_temp_c": 30,
    }
    client.post(f"{base}/telemetry", json={"readings": [reading]}, headers=auth_headers)
    # That night's scheduled charge has not happened yet at 19:00.
    later = session(datetime(2026, 9, 1, 23, 0, tzinfo=IST), 4, 25, start_soc_pct=40, end_soc_pct=90)
    client.post(f"{base}/charging/sessions", json={"sessions": [later]}, headers=auth_headers)

    rec = client.get(
        f"{base}/charging/recommendation",
        params={"at": datetime(2026, 9, 1, 19, 0, tzinfo=IST).isoformat()},
        headers=auth_headers,
    ).json()
    assert rec["current_soc_pct"] == 40
