"""
Alert schemas — request / response models for alert endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: int
    alert_uid: str
    detection_event_id: int
    triggered_at: datetime
    notification_status: str
    whatsapp_message_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    page: int
    per_page: int
