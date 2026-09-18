"""
Real-time detection router — WebSocket streaming + start/stop control.

The detection pipeline runs as a background asyncio task:
Camera → InferenceService → TemporalValidator → AlertDecisionEngine
  → WebSocket push + DB persist + Notification trigger

All alert-related work (DB save, WhatsApp, alarm broadcast) runs in
background tasks so the detection loop never blocks.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from typing import Set

import cv2
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user, get_current_user_id, get_db
from app.core.config import Settings
from app.models.user import User
from app.repositories.alert_repository import AlertRepository
from app.repositories.detection_repository import DetectionRepository
from app.services.alert_decision_engine import AlertDecisionEngine
from app.services.camera_service import CameraService
from app.services.inference_service import InferenceService
from app.services.media_service import MediaService
from app.services.notification_service import (
    ConsoleNotificationService,
    NotificationService,
    WhatsAppCloudAPINotificationService,
)
from app.services.temporal_validator import TemporalValidator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stream", tags=["realtime"])

# ── Global state for the streaming pipeline ──────────────────────────
_ws_clients: Set[WebSocket] = set()
_stream_task: asyncio.Task | None = None
_camera_service: CameraService | None = None
_notifier: NotificationService | None = None
# Track alert UIDs that have been processed (prevents duplicate handling)
_processed_alert_uids: set[str] = set()


async def _broadcast(message: dict) -> None:
    """Push a JSON message to all connected WebSocket clients."""
    data = json.dumps(message)
    disconnected = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    _ws_clients.difference_update(disconnected)


async def _handle_alert_background(
    alert_uid: str,
    alert_event,
    detections,
    frame,
    settings: Settings,
    media: MediaService,
    notifier: NotificationService,
    user_id: int,
    user_phone: str,
) -> None:
    """
    Background task: save screenshot → persist alert to DB → send WhatsApp.

    Runs independently so the detection loop continues immediately.
    Failures here are logged but never crash the detection pipeline.
    """
    from app.db.session import async_session_factory

    screenshot_url: str | None = None
    try:
        # Save screenshot
        screenshot_url = media.save_screenshot(frame, detections)
    except Exception as exc:
        logger.error("Alert screenshot save failed: %s", exc)

    # Persist to DB
    db_alert = None
    try:
        async with async_session_factory() as db:
            det_repo = DetectionRepository(db)
            events = await det_repo.create(
                detections=detections,
                source=settings.CAMERA_SOURCE,
                image_path=screenshot_url,
                duration_seconds=alert_event.duration_seconds,
                is_alert=True,
            )

            alert_repo = AlertRepository(db)
            # Idempotency check
            if await alert_repo.exists_by_uid(alert_uid):
                logger.warning("Duplicate alert_uid %s — skipping", alert_uid)
                await db.commit()
                return

            if events:
                db_alert = await alert_repo.create(
                    detection_event_id=events[0].id,
                    user_id=user_id,
                    alert_uid=alert_uid,
                    screenshot_path=screenshot_url,
                )

            await db.commit()
    except Exception as exc:
        logger.error("Alert DB persist error (uid=%s): %s", alert_uid, exc)

    # Send WhatsApp notification (non-blocking, does not affect detection)
    if db_alert and user_phone:
        try:
            # Resolve the /static/... URL path to the actual filesystem path
            image_fs_path: str | None = None
            if screenshot_url:
                try:
                    image_fs_path = str(media.resolve_path(screenshot_url))
                except Exception:
                    image_fs_path = None
            
            
            result = await notifier.send_alert(
                phone=user_phone,
                message=(
                    f"🔥 *ALERT: {alert_event.class_name.upper()} DETECTED!*\n\n"
                    f"• Confidence: {alert_event.confidence:.0%}\n"
                    f"• Duration: {alert_event.duration_seconds:.1f}s\n"
                    f"• Source: {settings.CAMERA_SOURCE}\n"
                    f"• Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"Alert ID: {alert_uid[:8]}"
                ),
                image_path=str(media.resolve_path(image_fs_path))
            )

            # Update alert status in DB
            try:
                async with async_session_factory() as db:
                    alert_repo = AlertRepository(db)
                    await alert_repo.update_status(
                        alert_id=db_alert.id,
                        status="sent" if result.success else "failed",
                        message_id=result.message_id,
                        error=result.error,
                    )
                    await db.commit()
            except Exception as exc:
                logger.error("Alert status update error: %s", exc)

        except Exception as exc:
            logger.error("WhatsApp notification error (uid=%s): %s", alert_uid, exc)
            # Mark as failed in DB
            try:
                async with async_session_factory() as db:
                    alert_repo = AlertRepository(db)
                    await alert_repo.update_status(
                        alert_id=db_alert.id,
                        status="failed",
                        error=str(exc),
                    )
                    await db.commit()
            except Exception:
                pass
    elif db_alert and not user_phone:
        logger.warning("User %d has no WhatsApp phone — skipping notification", user_id)
        try:
            async with async_session_factory() as db:
                alert_repo = AlertRepository(db)
                await alert_repo.update_status(
                    alert_id=db_alert.id,
                    status="failed",
                    error="No WhatsApp phone number configured for user",
                )
                await db.commit()
        except Exception:
            pass


async def _run_pipeline(settings: Settings, user_id: int, user_phone: str) -> None:
    """
    Core detection loop — runs as a background task.

    Camera → Inference → Temporal Validation → Alert Decision
      → broadcast to WebSocket clients
      → fire background tasks for alert persistence + notification
    """
    global _camera_service, _notifier

    from app.ml.model_loader import load_model

    model = load_model(settings.MODEL_PATH, settings.DEVICE)
    inference = InferenceService(model, settings.CONFIDENCE_THRESHOLD, settings.IOU_THRESHOLD)
    validator = TemporalValidator(
        window_seconds=settings.MIN_DETECTION_DURATION_SEC * 2,
        min_consecutive_frames=settings.MIN_CONSECUTIVE_FRAMES,
        min_detection_duration=settings.MIN_DETECTION_DURATION_SEC,
        detection_ratio_threshold=settings.DETECTION_RATIO_THRESHOLD,
        confidence_threshold=settings.CONFIDENCE_THRESHOLD,
    )
    alert_engine = AlertDecisionEngine(cooldown_seconds=settings.ALERT_COOLDOWN_SEC)
    media = MediaService(settings.STORAGE_DIR)
    

    # Initialize notification service
    if settings.WHATSAPP_API_KEY and settings.WHATSAPP_API_BASE:
        _notifier = WhatsAppCloudAPINotificationService(
            api_base=settings.WHATSAPP_API_BASE,
            api_key=settings.WHATSAPP_API_KEY,
            min_interval=60
        )
    else:
        _notifier = ConsoleNotificationService()

    _camera_service = CameraService(
        source=settings.CAMERA_SOURCE,
        target_fps=settings.CAMERA_FPS,
        frame_skip=settings.FRAME_SKIP,
    )

    if not _camera_service.open():
        await _broadcast({"type": "error", "message": "Failed to open camera"})
        return

    await _broadcast({"type": "status", "message": "Stream started", "camera": _camera_service.get_status()})

    frame_count = 0
    try:
        async for frame in _camera_service.stream_frames():
            frame_count += 1

            # Run inference
            detections = await inference.predict(frame)

            now = time.time()
            sustained = validator.update(detections, now)

            # Build confidence and duration maps for alert engine
            confidences = {}
            durations = {}
            for cls, is_sustained in sustained.items():
                state = validator.get_state(cls)
                if state:
                    confidences[cls] = state.max_confidence
                    durations[cls] = (now - state.first_seen) if state.first_seen else 0.0

            alerts = alert_engine.evaluate(sustained, confidences, durations, now)

            # Determine current status
            if any(d.class_name == "fire" for d in detections):
                status_text = "[!] FIRE DETECTED"
            elif any(d.class_name == "smoke" for d in detections):
                status_text = "[~] SMOKE DETECTED"
            else:
                status_text = "[OK] CLEAR"

            # Encode frame as JPEG for WebSocket transmission
            annotated = media.annotate_frame(frame, detections)
            _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_b64 = base64.b64encode(buffer.tobytes()).decode("utf-8")

            # Broadcast detection data
            det_payload = {
                "type": "detection",
                "frame": frame_b64,
                "status": status_text,
                "detections": [
                    {
                        "class_name": d.class_name,
                        "confidence": d.confidence,
                        "bbox": {"x1": d.bbox.x1, "y1": d.bbox.y1, "x2": d.bbox.x2, "y2": d.bbox.y2},
                    }
                    for d in detections
                ],
                "frame_number": frame_count,
                "latency_ms": round(inference.last_latency_ms, 1),
                "timestamp": now,
            }
            await _broadcast(det_payload)

            # Handle alerts — each one spawns a background task
            for alert_event in alerts:
                alert_uid = str(uuid.uuid4())

                # Skip if we somehow generated a duplicate in-memory
                if alert_uid in _processed_alert_uids:
                    continue
                _processed_alert_uids.add(alert_uid)

                logger.warning(
                    "[ALERT] %s (confidence=%.2f, duration=%.1fs, uid=%s)",
                    alert_event.class_name, alert_event.confidence,
                    alert_event.duration_seconds, alert_uid[:8],
                )

                # Broadcast alert event (triggers frontend alarm + UI update)
                await _broadcast({
                    "type": "alert",
                    "alert_uid": alert_uid,
                    "class_name": alert_event.class_name,
                    "confidence": alert_event.confidence,
                    "duration_seconds": alert_event.duration_seconds,
                    "timestamp": alert_event.timestamp,
                })

                # Fire background task for DB + WhatsApp (non-blocking)
                asyncio.create_task(
                    _handle_alert_background(
                        alert_uid=alert_uid,
                        alert_event=alert_event,
                        detections=detections,
                        frame=frame.copy(),  # copy frame as it may be overwritten
                        settings=settings,
                        media=media,
                        notifier=_notifier,
                        user_id=user_id,
                        user_phone=user_phone,
                    )
                )

                # Reset validator for this class after alert
                validator.reset_class(alert_event.class_name)

    except asyncio.CancelledError:
        logger.info("Stream pipeline cancelled")
    except Exception as exc:
        logger.error("Stream pipeline error: %s", exc, exc_info=True)
        await _broadcast({"type": "error", "message": str(exc)})
    finally:
        if _camera_service:
            _camera_service.release()
        if _notifier:
            await _notifier.close()
            _notifier = None
        _processed_alert_uids.clear()
        await _broadcast({"type": "status", "message": "Stream stopped"})


@router.websocket("/ws")
async def websocket_stream(ws: WebSocket):
    """WebSocket endpoint for live detection feed."""
    await ws.accept()
    _ws_clients.add(ws)
    logger.info("WebSocket client connected (%d total)", len(_ws_clients))

    try:
        # Send current status
        await ws.send_json({
            "type": "status",
            "message": "connected",
            "streaming": _stream_task is not None and not _stream_task.done(),
        })

        # Keep connection alive — just listen for close
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(_ws_clients))


@router.post("/start")
async def start_stream(
    settings: Settings = Depends(get_app_settings),
    user: User = Depends(get_current_user),
):
    """Start the real-time detection pipeline."""
    global _stream_task

    if _stream_task is not None and not _stream_task.done():
        return {"status": "already_running"}

    _stream_task = asyncio.create_task(
        _run_pipeline(settings, user_id=user.id, user_phone=user.mobile_phone)
    )
    return {"status": "started"}


@router.post("/stop")
async def stop_stream(
    user_id: int = Depends(get_current_user_id),
):
    """Stop the real-time detection pipeline."""
    global _stream_task, _camera_service

    if _stream_task is None or _stream_task.done():
        return {"status": "not_running"}

    if _camera_service:
        _camera_service.stop()
    _stream_task.cancel()

    try:
        await _stream_task
    except asyncio.CancelledError:
        pass

    _stream_task = None
    return {"status": "stopped"}


@router.get("/status")
async def stream_status():
    """Get current stream status."""
    running = _stream_task is not None and not _stream_task.done()
    camera_status = _camera_service.get_status() if _camera_service else None
    return {
        "streaming": running,
        "clients_connected": len(_ws_clients),
        "camera": camera_status,
    }
