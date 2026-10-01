import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("battery_capacity_kwh > 0", name="battery_capacity_positive"),
        CheckConstraint("rated_range_km > 0", name="rated_range_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    vin: Mapped[str] = mapped_column(String(17), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(100))
    make: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    model_year: Mapped[int]
    battery_capacity_kwh: Mapped[float]
    rated_range_km: Mapped[float]
    # First registration date; battery calendar ageing is measured from here.
    registered_on: Mapped[date]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
