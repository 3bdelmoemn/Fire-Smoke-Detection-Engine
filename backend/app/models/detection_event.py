"""DetectionEvent ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Float, Boolean, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    detection_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # 'fire' | 'smoke'
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_json: Mapped[str] = mapped_column(Text, nullable=False)  # serialised [x1,y1,x2,y2]
    source: Mapped[str] = mapped_column(String(200), nullable=False)  # camera id or 'upload:<name>'
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    is_alert_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
