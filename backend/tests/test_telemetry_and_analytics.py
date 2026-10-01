from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import engine

START = datetime(2026, 9, 1, 3, 0, tzinfo=UTC)  # 08:30 IST


def drive(start: datetime, minutes: int, start_soc: float, start_odo: float, speed: float = 36.0):
    """Readings for a steady drive: 0.6 km and 0.25% SoC per minute."""
    return [
        {
            "recorded_at": (start + timedelta(minutes=i)).isoformat(),
            "odometer_km": start_odo + 0.6 * i,
            "speed_kph": speed,
            "soc_pct": start_soc - 0.25 * i,
            "soh_pct": 97.0,
            "battery_voltage_v": 350.0,
            "battery_current_a": 40.0,
            "battery_temp_c": 31.0,
            "motor_temp_c": 55.0,
            "ambient_temp_c": 30.0,
        }
        for i in range(minutes + 1)
    ]


def post_readings(client, headers, vehicle_id, readings):
    return client.post(
        f"/api/v1/vehicles/{vehicle_id}/telemetry", json={"readings": readings}, headers=headers
    )


def test_ingest_is_idempotent(client, auth_headers, vehicle):
    readings = drive(START, 10, 80, 1000)

    first = post_readings(client, auth_headers, vehicle["id"], readings).json()
    assert first["inserted"] == 11 and first["duplicates"] == 0

    # A device replaying a buffer that overlaps what was already sent.
    replay = readings[5:] + drive(START + timedelta(minutes=11), 4, 77.25, 1006.6)
    second = post_readings(client, auth_headers, vehicle["id"], replay).json()
    assert second == {**second, "received": 11, "inserted": 5, "duplicates": 6}


def test_ingest_rejects_invalid_readings(client, auth_headers, vehicle):
    reading = drive(START, 0, 80, 1000)[0]
    for field, value in [("soc_pct", 120), ("speed_kph", -5), ("recorded_at", "2026-09-01T03:00:00")]:
        response = post_readings(client, auth_headers, vehicle["id"], [{**reading, field: value}])
        assert response.status_code == 422, field


def test_status_and_time_filtered_reads(client, auth_headers, vehicle):
    post_readings(client, auth_headers, vehicle["id"], drive(START, 20, 80, 1000))
    base = f"/api/v1/vehicles/{vehicle['id']}"

    status = client.get(f"{base}/status", headers=auth_headers).json()
    assert status["soc_pct"] == pytest.approx(75.0)
    assert status["odometer_km"] == pytest.approx(1012.0)

    window = client.get(
        f"{base}/telemetry",
        params={
            "start": (START + timedelta(minutes=5)).isoformat(),
            "end": (START + timedelta(minutes=10)).isoformat(),
        },
        headers=auth_headers,
    ).json()
    assert len(window) == 5


def test_trips_are_reconstructed_from_telemetry(client, auth_headers, vehicle):
    morning = drive(START, 30, 80, 1000)  # 18 km, 7.5% SoC
    evening = drive(START + timedelta(hours=9), 20, 72.5, 1018, speed=24)  # 12 km, 5% SoC
    post_readings(client, auth_headers, vehicle["id"], morning + evening)

    with engine.connect() as connection:
        trips = connection.execute(
            text(
                "SELECT distance_km, energy_used_kwh, efficiency_wh_per_km, speed_band, start_hour "
                "FROM analytics.fact_trip WHERE vehicle_id = :v ORDER BY started_at"
            ),
            {"v": vehicle["id"]},
        ).all()

    assert len(trips) == 2
    distance, energy, efficiency, band, hour = trips[0]
    assert distance == pytest.approx(18.0)
    assert energy == pytest.approx(0.075 * 40.5 * 0.97)  # SoC drop x capacity x SoH
    assert efficiency == pytest.approx(energy * 1000 / 18)
    assert band.startswith("2 Suburban")
    assert hour == 8  # local (IST) hour
    assert trips[1].speed_band.startswith("1 City")


def test_fleet_summary(client, auth_headers, vehicle):
    post_readings(client, auth_headers, vehicle["id"], drive(START, 30, 80, 1000))
    summary = client.get("/api/v1/fleet/summary", headers=auth_headers).json()
    assert summary["vehicles"] == 1
    assert summary["distance_km"] == pytest.approx(18.0)
    assert summary["avg_soh_pct"] == pytest.approx(97.0)
