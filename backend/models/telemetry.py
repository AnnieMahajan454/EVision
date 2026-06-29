from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    vehicle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    battery_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    voltage_v: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_a: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    speed_kph: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    motor_temperature_c: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    ambient_temperature_c: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
