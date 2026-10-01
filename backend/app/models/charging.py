import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChargerType(enum.StrEnum):
    HOME_AC = "home_ac"
    PUBLIC_AC = "public_ac"
    DC_FAST = "dc_fast"


class ChargingSession(Base):
    __tablename__ = "charging_sessions"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "started_at", name="uq_charging_vehicle_start"),
        CheckConstraint("ended_at > started_at", name="ends_after_start"),
        CheckConstraint("end_soc_pct >= start_soc_pct", name="soc_does_not_drop"),
        CheckConstraint("energy_delivered_kwh >= 0", name="energy_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    charger_type: Mapped[ChargerType] = mapped_column(
        Enum(ChargerType, name="charger_type", values_callable=lambda e: [m.value for m in e])
    )
    start_soc_pct: Mapped[float]
    end_soc_pct: Mapped[float]
    energy_delivered_kwh: Mapped[float]  # measured at the charger (grid side)
    max_power_kw: Mapped[float | None]
    # Billed amount for public chargers. Home sessions are costed from tariff_hours instead.
    cost_inr: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TariffHour(Base):
    """Time-of-day electricity tariff for home/depot charging, one row per local hour."""

    __tablename__ = "tariff_hours"
    __table_args__ = (CheckConstraint("hour BETWEEN 0 AND 23", name="valid_hour"),)

    hour: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    band: Mapped[str] = mapped_column(String(20))
    rate_inr_per_kwh: Mapped[float]
