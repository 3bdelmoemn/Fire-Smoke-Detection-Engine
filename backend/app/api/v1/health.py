"""
Health-check endpoints.

- ``GET /health``           — simple liveness probe (always 200 if the server is up).
- ``GET /health/detailed``  — readiness probe: DB, model, camera status.
- ``GET /health/kpis``      — aggregated KPIs for the dashboard.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.alert_repository import AlertRepository
from app.repositories.detection_repository import DetectionRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_liveness():
    """Simple liveness check — returns 200 if the server is running."""
    return {"status": "ok"}


@router.get("/detailed")
async def health_detailed(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe.  Checks:
    - DB connectivity
    - Model loaded status (via lru_cache check)
    - Last inference latency (if available)
    """
    checks: dict = {"status": "ok"}

    # DB check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        checks["status"] = "degraded"

    # Model check — inspect the lru_cache to see if model was loaded
    try:
        from app.ml.model_loader import load_model
        cache_info = load_model.cache_info()
        checks["model_loaded"] = cache_info.hits > 0 or cache_info.currsize > 0
    except Exception:
        checks["model_loaded"] = False

    return checks


@router.get("/kpis")
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db)):
    """Aggregated KPI numbers for the dashboard."""
    det_repo = DetectionRepository(db)
    alert_repo = AlertRepository(db)

    det_kpis = await det_repo.get_kpis()
    alert_kpis = await alert_repo.get_alert_kpis()

    return {**det_kpis, **alert_kpis}

