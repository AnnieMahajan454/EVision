"""Tests run against a real PostgreSQL database (the analytics layer is Postgres SQL).

Set TEST_DATABASE_URL to a throwaway database; it is migrated from scratch on every run.
"""

import os
import uuid
from datetime import date
from pathlib import Path

import pytest

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/evision_test"
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["configure_logger"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, vehicles, telemetry, charging_sessions, predictions RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def register(client: TestClient, email: str | None = None) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email or f"{uuid.uuid4().hex[:8]}@example.com", "password": "s3cure-pass"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return register(client)


VEHICLE_PAYLOAD = {
    "vin": "MAT612345NX000001",
    "nickname": "Cab 01",
    "make": "Tata",
    "model": "Nexon EV",
    "model_year": 2024,
    "battery_capacity_kwh": 40.5,
    "rated_range_km": 465,
    "registered_on": date(2024, 3, 1).isoformat(),
}


@pytest.fixture
def vehicle(client: TestClient, auth_headers: dict[str, str]) -> dict:
    response = client.post("/api/v1/vehicles", json=VEHICLE_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()
