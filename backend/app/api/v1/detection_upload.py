"""
Upload detection router — image and video upload endpoints.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_app_settings, get_current_user_id, get_db
from app.core.config import Settings
from app.repositories.detection_repository import DetectionRepository
from app.schemas.detection import ImageDetectionResponse, VideoDetectionResponse
from app.services.inference_service import InferenceService
from app.services.media_service import MediaService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detect", tags=["detection"])

# Allowed file types (by extension)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _get_inference_service(settings: Settings) -> InferenceService:
    from app.ml.model_loader import load_model
    model = load_model(settings.MODEL_PATH, settings.DEVICE)
    return InferenceService(model, settings.CONFIDENCE_THRESHOLD, settings.IOU_THRESHOLD)


@router.post("/image", response_model=ImageDetectionResponse)
async def detect_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    user_id: int = Depends(get_current_user_id),
):
    """Upload an image for fire/smoke detection. Returns annotated result."""
    # Validate file
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image format. Allowed: {', '.join(IMAGE_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Decode image
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    # Run inference
    t0 = time.perf_counter()
    svc = _get_inference_service(settings)
    detections = await svc.predict(frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Save annotated image
    media = MediaService(settings.STORAGE_DIR)
    annotated_url = media.save_annotated_image(frame, detections, prefix="upload")

    # Persist to DB
    repo = DetectionRepository(db)
    await repo.create(
        detections=detections,
        source=f"upload:{file.filename}",
        image_path=annotated_url,
    )

    fire_count = sum(1 for d in detections if d.class_name == "fire")
    smoke_count = sum(1 for d in detections if d.class_name == "smoke")

    return ImageDetectionResponse(
        detections=detections,
        annotated_image_url=annotated_url,
        total_fire=fire_count,
        total_smoke=smoke_count,
        processing_time_ms=round(elapsed_ms, 2),
    )


@router.post("/video", response_model=VideoDetectionResponse)
async def detect_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    user_id: int = Depends(get_current_user_id),
):
    """Upload a video for fire/smoke detection. Returns annotated output."""
    if file.filename is None:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid video format. Allowed: {', '.join(VIDEO_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Save upload temporarily
    media = MediaService(settings.STORAGE_DIR)
    upload_path = media.save_upload(contents, file.filename)

    # Process video
    t0 = time.perf_counter()
    svc = _get_inference_service(settings)

    import asyncio
    loop = asyncio.get_running_loop()
    out_path, all_detections = await loop.run_in_executor(
        None, media.annotate_video, upload_path, svc, "upload_video"
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # Build URL
    rel_path = str(out_path).replace("\\", "/")
    # Extract the date/filename part for the static URL
    parts = rel_path.split("detections/")
    annotated_url = f"/static/detections/{parts[-1]}" if len(parts) > 1 else rel_path

    # Count frames
    cap = cv2.VideoCapture(str(upload_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    fire_count = sum(1 for d in all_detections if d.class_name == "fire")
    smoke_count = sum(1 for d in all_detections if d.class_name == "smoke")
    frames_with_dets = len(set(
        d.timestamp for d in all_detections if d.timestamp
    )) if all_detections else (1 if all_detections else 0)

    # Persist summary to DB
    repo = DetectionRepository(db)
    if all_detections:
        # Take top detections as representative
        top_dets = sorted(all_detections, key=lambda d: d.confidence, reverse=True)[:10]
        await repo.create(
            detections=top_dets,
            source=f"upload:{file.filename}",
            video_path=annotated_url,
        )

    return VideoDetectionResponse(
        total_frames=total_frames,
        frames_with_detections=min(fire_count + smoke_count, total_frames),
        detections_summary=sorted(all_detections, key=lambda d: d.confidence, reverse=True)[:20],
        annotated_video_url=annotated_url,
        total_fire=fire_count,
        total_smoke=smoke_count,
        processing_time_ms=round(elapsed_ms, 2),
    )
