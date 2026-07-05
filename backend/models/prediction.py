from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

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
    prediction_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
