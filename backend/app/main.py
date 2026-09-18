"""
FastAPI application factory.

- Registers all v1 routers.
- Configures CORS, logging, and lifespan events.
- Creates storage directories and DB tables on startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.db.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle events."""
    settings = get_settings()

    # ── Startup ──────────────────────────────────────────────────────
    setup_logging(log_level=settings.LOG_LEVEL, log_dir=str(settings.storage_path / "logs"))
    logger.info("[FIRE] Fire & Smoke Detection System starting up...")

    # Create storage directories
    settings.ensure_directories()
    logger.info("Storage directories ensured at %s", settings.storage_path)

    # Initialise database tables
    await init_db()
    logger.info("Database tables initialised")

    # Pre-load YOLO model so it's cached and ready for inference
    try:
        from app.ml.model_loader import load_model
        load_model(settings.MODEL_PATH, settings.DEVICE)
        logger.info("YOLO model loaded successfully")
    except Exception as exc:
        logger.warning("Model pre-load failed (will retry on first request): %s", exc)

    # Mount static files for serving detection screenshots & uploads
    app.mount(
        "/static/detections",
        StaticFiles(directory=str(settings.detections_path), check_dir=False),
        name="detections",
    )
    app.mount(
        "/static/uploads",
        StaticFiles(directory=str(settings.uploads_path), check_dir=False),
        name="uploads",
    )

    logger.info("[OK] Startup complete")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("[STOP] Shutting down...")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Fire & Smoke Detection System",
        description="Production-grade YOLO-based fire and smoke detection API",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────
    from app.api.v1.health import router as health_router
    from app.api.v1.auth import router as auth_router
    from app.api.v1.detection_upload import router as upload_router
    from app.api.v1.detection_realtime import router as realtime_router
    from app.api.v1.evaluation import router as eval_router
    from app.api.v1.alerts import router as alerts_router

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(upload_router, prefix="/api/v1")
    app.include_router(realtime_router, prefix="/api/v1")
    app.include_router(eval_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")

    return app


# Module-level app instance for ``uvicorn app.main:app``
app = create_app()
