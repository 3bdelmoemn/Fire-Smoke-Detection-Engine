"""
Alert repository — DB access for Alert entities.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert


class AlertRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        detection_event_id: int,
        user_id: int,
        alert_uid: str,
        screenshot_path: Optional[str] = None,
    ) -> Alert:
        alert = Alert(
            alert_uid=alert_uid,
            user_id=user_id,
            detection_event_id=detection_event_id,
            screenshot_path=screenshot_path,
            notification_status="pending",
        )
        self._db.add(alert)
        await self._db.flush()
        await self._db.refresh(alert)
        return alert

    async def exists_by_uid(self, alert_uid: str) -> bool:
        """Check whether an alert with this UID already exists (idempotency)."""
        result = await self._db.execute(
            select(func.count(Alert.id)).where(Alert.alert_uid == alert_uid)
        )
        return (result.scalar() or 0) > 0

    async def update_status(
        self,
        alert_id: int,
        status: str,
        message_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        result = await self._db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert:
            alert.notification_status = status
            alert.whatsapp_message_id = message_id
            alert.error_message = error

    async def list_alerts(
        self,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> tuple[List[Alert], int]:
        query = select(Alert).order_by(Alert.triggered_at.desc())
        count_query = select(func.count(Alert.id))

        if status_filter:
            query = query.where(Alert.notification_status == status_filter)
            count_query = count_query.where(Alert.notification_status == status_filter)

        if user_id is not None:
            query = query.where(Alert.user_id == user_id)
            count_query = count_query.where(Alert.user_id == user_id)

        total = (await self._db.execute(count_query)).scalar() or 0
        result = await self._db.execute(
            query.offset((page - 1) * per_page).limit(per_page)
        )
        return list(result.scalars().all()), total

    async def get_alert_kpis(self, user_id: Optional[int] = None) -> dict:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        base_filter = (Alert.user_id == user_id) if user_id is not None else True

        total = (await self._db.execute(
            select(func.count(Alert.id)).where(base_filter)
        )).scalar() or 0

        sent = (await self._db.execute(
            select(func.count(Alert.id)).where(
                base_filter, Alert.notification_status == "sent"
            )
        )).scalar() or 0

        failed = (await self._db.execute(
            select(func.count(Alert.id)).where(
                base_filter, Alert.notification_status == "failed"
            )
        )).scalar() or 0

        today = (await self._db.execute(
            select(func.count(Alert.id)).where(
                base_filter, Alert.triggered_at >= today_start
            )
        )).scalar() or 0

        return {
            "total_alerts": total,
            "alerts_sent": sent,
            "alerts_failed": failed,
            "alerts_today": today,
        }
