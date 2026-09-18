"""
Detection repository — DB access for DetectionEvent entities.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection_event import DetectionEvent
from app.schemas.detection import Detection


class DetectionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        detections: List[Detection],
        source: str,
        image_path: Optional[str] = None,
        video_path: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        is_alert: bool = False,
    ) -> List[DetectionEvent]:
        """Persist one DetectionEvent per detection."""
        events = []
        for det in detections:
            event = DetectionEvent(
                detection_type=det.class_name,
                confidence=det.confidence,
                bbox_json=json.dumps([det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2]),
                source=source,
                image_path=image_path,
                video_path=video_path,
                duration_seconds=duration_seconds,
                is_alert_triggered=is_alert,
            )
            self._db.add(event)
            events.append(event)
        await self._db.flush()
        return events

    async def list_events(
        self,
        page: int = 1,
        per_page: int = 20,
        detection_type: Optional[str] = None,
    ) -> tuple[List[DetectionEvent], int]:
        """Return paginated events and total count."""
        query = select(DetectionEvent).order_by(DetectionEvent.detected_at.desc())
        count_query = select(func.count(DetectionEvent.id))

        if detection_type:
            query = query.where(DetectionEvent.detection_type == detection_type)
            count_query = count_query.where(DetectionEvent.detection_type == detection_type)

        total = (await self._db.execute(count_query)).scalar() or 0
        result = await self._db.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def get_kpis(self) -> dict:
        """Aggregate KPI numbers for the dashboard."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total = (await self._db.execute(
            select(func.count(DetectionEvent.id))
        )).scalar() or 0

        total_fire = (await self._db.execute(
            select(func.count(DetectionEvent.id)).where(DetectionEvent.detection_type == "fire")
        )).scalar() or 0

        total_smoke = (await self._db.execute(
            select(func.count(DetectionEvent.id)).where(DetectionEvent.detection_type == "smoke")
        )).scalar() or 0

        avg_conf = (await self._db.execute(
            select(func.avg(DetectionEvent.confidence))
        )).scalar() or 0.0

        today_dets = (await self._db.execute(
            select(func.count(DetectionEvent.id)).where(
                DetectionEvent.detected_at >= today_start
            )
        )).scalar() or 0

        return {
            "total_detections": total,
            "total_fire": total_fire,
            "total_smoke": total_smoke,
            "avg_confidence": round(float(avg_conf), 4),
            "detections_today": today_dets,
        }
