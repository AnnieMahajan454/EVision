import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Telemetry(Base):
    """One reading from a vehicle's telematics unit (every ~60 s while driving)."""

    __tablename__ = "telemetry"
    # Devices retry on flaky connections, so (vehicle, timestamp) is the natural key. It also
    # serves as the index for per-vehicle time-range scans.
    __table_args__ = (UniqueConstraint("vehicle_id", "recorded_at", name="uq_telemetry_vehicle_time"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    odometer_km: Mapped[float]
    speed_kph: Mapped[float]
    soc_pct: Mapped[float]
    soh_pct: Mapped[float | None]  # as reported by the BMS
    battery_voltage_v: Mapped[float]
    battery_current_a: Mapped[float]  # positive = discharging
    battery_temp_c: Mapped[float]
    motor_temp_c: Mapped[float | None]
    ambient_temp_c: Mapped[float | None]

    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
