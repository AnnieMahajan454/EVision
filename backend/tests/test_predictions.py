from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LinearRegression

from app.config import settings
from app.services import predictions as prediction_service
from ml.features import RANGE_INPUTS, battery_health_design_matrix, range_design_matrix
from ml.registry import ModelArtifact, save_artifact
from tests.test_telemetry_and_analytics import START, drive, post_readings


class ConstantModel:
    def __init__(self, value: float):
        self.value = value

    def predict(self, frame):
        return np.full(len(frame), self.value)


@pytest.fixture
def trained_models(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", tmp_path)
    prediction_service.get_model.cache_clear()

    range_x = range_design_matrix(pd.DataFrame([dict.fromkeys(RANGE_INPUTS, 1.0)]))
    save_artifact(
        ModelArtifact(
            "range",
            "range-test",
            ConstantModel(150.0),
            list(range_x.columns),
            {},
            datetime.now(UTC),
            date.today(),
        ),
        tmp_path,
    )

    # SoH falls 2 points per sqrt(year) and 1 point per 100 cycles.
    history = pd.DataFrame(
        {
            "age_days": [0, 365, 730, 1460],
            "equivalent_full_cycles": [0, 100, 200, 400],
            "lifetime_avg_battery_temp_c": 25,
            "dc_fast_share": 0,
            "high_soc_share": 0,
        }
    )
    x = battery_health_design_matrix(history)
    y = 100 - 2 * x["sqrt_age"] - x["cycles"]
    save_artifact(
        ModelArtifact(
            "battery_health",
            "soh-test",
            LinearRegression().fit(x, y),
            list(x.columns),
            {},
            datetime.now(UTC),
            date.today(),
        ),
        tmp_path,
    )
    yield
    prediction_service.get_model.cache_clear()


def test_models_missing_returns_503(client, auth_headers, vehicle, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "models_dir", tmp_path / "empty")
    prediction_service.get_model.cache_clear()
    response = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/predictions/range",
        json={"soc_pct": 80, "ambient_temp_c": 30, "expected_avg_speed_kph": 40},
        headers=auth_headers,
    )
    assert response.status_code == 503


def test_range_prediction(client, auth_headers, vehicle, trained_models):
    post_readings(client, auth_headers, vehicle["id"], drive(START, 30, 80, 1000))  # SoH 97 %
    base = f"/api/v1/vehicles/{vehicle['id']}/predictions"

    response = client.post(
        f"{base}/range", json={"ambient_temp_c": 30, "expected_avg_speed_kph": 40}, headers=auth_headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    energy = 0.725 * 40.5 * 0.97  # latest SoC 72.5 %
    assert body["usable_energy_kwh"] == pytest.approx(energy, abs=0.01)
    assert body["estimated_range_km"] == pytest.approx(energy * 1000 / 150, abs=0.1)

    logged = client.get(base, params={"prediction_type": "range"}, headers=auth_headers).json()
    assert len(logged) == 1 and logged[0]["model_version"] == "range-test"


def test_battery_health_forecast(client, auth_headers, vehicle, trained_models):
    post_readings(client, auth_headers, vehicle["id"], drive(START, 30, 80, 1000))

    response = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/predictions/battery-health",
        json={"horizon_days": 365},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["current_soh_pct"] == pytest.approx(97.0)
    # Older battery + more cycles one year out -> lower predicted SoH than today's model estimate.
    today = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/predictions/battery-health",
        json={"horizon_days": 0},
        headers=auth_headers,
    ).json()
    assert body["predicted_soh_pct"] < today["predicted_soh_pct"] <= 100


def test_battery_health_without_history_is_422(client, auth_headers, vehicle, trained_models):
    response = client.post(
        f"/api/v1/vehicles/{vehicle['id']}/predictions/battery-health",
        json={"horizon_days": 30},
        headers=auth_headers,
    )
    assert response.status_code == 422
