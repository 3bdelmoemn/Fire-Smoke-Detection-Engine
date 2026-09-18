"""
Detection schemas — Pydantic models for API request/response.

The ``Detection`` model is the normalized output of the inference service.
Nothing downstream should know about raw YOLO result objects.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box in xyxy format (top-left x, top-left y, bottom-right x, bottom-right y)."""
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    """Single detection result — model-agnostic representation."""
    class_name: str = Field(..., description="Detected class: 'fire' or 'smoke'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BBox
    timestamp: Optional[datetime] = None


class ImageDetectionRequest(BaseModel):
    """Metadata sent alongside an uploaded image (optional)."""
    source: str = Field(default="upload", description="Source identifier")


class ImageDetectionResponse(BaseModel):
    """Response for a single image detection."""
    detections: List[Detection]
    annotated_image_url: str
    total_fire: int = 0
    total_smoke: int = 0
    processing_time_ms: float


class VideoDetectionResponse(BaseModel):
    """Response for video detection."""
    total_frames: int
    frames_with_detections: int
    detections_summary: List[Detection]
    annotated_video_url: str
    total_fire: int = 0
    total_smoke: int = 0
    processing_time_ms: float


class DetectionEventResponse(BaseModel):
    """Serialised DetectionEvent for API responses."""
    id: int
    detection_type: str
    confidence: float
    bbox_json: str
    source: str
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    detected_at: datetime
    duration_seconds: Optional[float] = None
    is_alert_triggered: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectionListResponse(BaseModel):
    """Paginated list of detection events."""
    items: List[DetectionEventResponse]
    total: int
    page: int
    per_page: int


class KPIResponse(BaseModel):
    """Aggregated KPI data for the dashboard."""
    total_detections: int = 0
    total_fire: int = 0
    total_smoke: int = 0
    total_alerts: int = 0
    alerts_sent: int = 0
    alerts_failed: int = 0
    avg_confidence: float = 0.0
    detections_today: int = 0
    alerts_today: int = 0
