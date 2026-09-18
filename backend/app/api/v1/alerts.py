"""
Alerts router — alert history and detail endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id, get_db
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertListResponse, AlertResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by notification status"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get paginated alert history for the current user."""
    repo = AlertRepository(db)
    items, total = await repo.list_alerts(page, per_page, status, user_id=user_id)
    return AlertListResponse(items=items, total=total, page=page, per_page=per_page)
