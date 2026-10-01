import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Identity, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PredictionType(enum.StrEnum):
    BATTERY_HEALTH = "battery_health"
    RANGE = "range"


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_lookup", "vehicle_id", "prediction_type", "reference_time"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    prediction_type: Mapped[PredictionType] = mapped_column(
        Enum(PredictionType, name="prediction_type", values_callable=lambda e: [m.value for m in e])
    )
    # The moment the prediction is made from (e.g. a trip start). Target = reference + horizon.
    reference_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horizon_days: Mapped[int] = mapped_column(default=0)
    predicted_value: Mapped[float]
    unit: Mapped[str] = mapped_column(String(20))
    model_version: Mapped[str] = mapped_column(String(50))
    features: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
