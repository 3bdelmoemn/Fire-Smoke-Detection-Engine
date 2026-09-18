"""
Media Service — save, annotate, and manage detection media files.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.schemas.detection import Detection

logger = logging.getLogger(__name__)


class MediaService:
    """Handles saving annotated images/videos and detection screenshots."""

    # Colour map for bounding box drawing
    COLOURS = {
        "fire": (0, 0, 255),     # Red in BGR
        "smoke": (0, 165, 255),  # Orange in BGR
    }

    STATIC_URL_PREFIX = "/static"

    def __init__(self, storage_dir: str):
        self._storage = Path(storage_dir)
        self._detections_dir = self._storage / "detections"
        self._uploads_dir = self._storage / "uploads"
        self._detections_dir.mkdir(parents=True, exist_ok=True)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, url_path: str) -> Path:
        """
        Translate a '/static/...' URL path (as returned by
        save_annotated_image / save_screenshot, and as stored on
        DetectionEvent.image_path / Alert.screenshot_path) back into
        the real filesystem path on disk.

        Already-filesystem paths are passed through unchanged, so this
        is safe to call even if the input isn't a '/static/...' URL.
        """
        if url_path.startswith(self.STATIC_URL_PREFIX):
            relative = url_path[len(self.STATIC_URL_PREFIX):].lstrip("/\\")
            return self._storage / relative
        return Path(url_path)

    def annotate_frame(
        self, frame: np.ndarray, detections: List[Detection]
    ) -> np.ndarray:
        """Draw bounding boxes and labels on a copy of the frame."""
        annotated = frame.copy()
        for det in detections:
            colour = self.COLOURS.get(det.class_name, (255, 255, 0))
            label = f"{det.class_name} {det.confidence:.0%}"
            x1, y1 = int(det.bbox.x1), int(det.bbox.y1)
            x2, y2 = int(det.bbox.x2), int(det.bbox.y2)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)

            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), colour, -1)
            cv2.putText(
                annotated, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
            )
        return annotated

    def save_annotated_image(
        self, frame: np.ndarray, detections: List[Detection], prefix: str = "det"
    ) -> str:
        """Annotate frame, save to detections dir, return relative URL path."""
        annotated = self.annotate_frame(frame, detections)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dir_path = self._detections_dir / date_str
        dir_path.mkdir(parents=True, exist_ok=True)

        filename = f"{prefix}_{uuid.uuid4().hex[:12]}.jpg"
        filepath = dir_path / filename
        cv2.imwrite(str(filepath), annotated)
        logger.info("Saved annotated image: %s", filepath)
        return f"/static/detections/{date_str}/{filename}"

    def save_upload(self, file_bytes: bytes, original_name: str) -> Path:
        """Save an uploaded file and return the filesystem path."""
        ext = Path(original_name).suffix.lower()
        filename = f"{uuid.uuid4().hex[:16]}{ext}"
        filepath = self._uploads_dir / filename
        filepath.write_bytes(file_bytes)
        logger.info("Saved upload: %s → %s", original_name, filepath)
        return filepath

    def save_screenshot(self, frame: np.ndarray, detections: List[Detection]) -> str:
        """Save an alert screenshot. Returns the relative URL path."""
        return self.save_annotated_image(frame, detections, prefix="alert")

    def annotate_video(
        self, input_path: Path, inference_service, output_prefix: str = "annotated"
    ) -> Tuple[Path, list]:
        """
        Process a video file frame-by-frame, annotate each frame, and
        write to an output video. Returns (output_path, all_detections).
        """
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {input_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = self._detections_dir / date_str
        out_dir.mkdir(parents=True, exist_ok=True)
        out_filename = f"{output_prefix}_{uuid.uuid4().hex[:12]}.mp4"
        out_path = out_dir / out_filename

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

        all_detections = []
        frame_count = 0
        frames_with_dets = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            dets = inference_service.predict_sync(frame)
            if dets:
                frames_with_dets += 1
                all_detections.extend(dets)

            annotated = self.annotate_frame(frame, dets)
            writer.write(annotated)
            frame_count += 1

        cap.release()
        writer.release()

        logger.info(
            "Video processed: %d frames, %d with detections → %s",
            frame_count, frames_with_dets, out_path,
        )
        return out_path, all_detections