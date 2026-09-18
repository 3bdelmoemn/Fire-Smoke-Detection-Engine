"""
Inference Service — wraps the YOLO model behind a clean interface.

Routes and services call ``InferenceService.predict(frame)`` and receive
a list of ``Detection`` objects.  Nothing downstream imports ultralytics
directly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import numpy as np

from app.schemas.detection import BBox, Detection

logger = logging.getLogger(__name__)

# Dedicated thread pool for CPU/GPU-bound inference so we never block
# the FastAPI event loop.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="inference")


class InferenceService:
    """
    Thin wrapper around a YOLO model.

    Responsibilities:
    - Accept a raw frame (numpy array).
    - Run prediction through the model.
    - Normalise raw YOLO results into ``Detection`` dataclasses.
    - Track last inference latency for health reporting.
    """

    # Classes we care about for alerting (ignore the 'default' class from Roboflow)
    ALERT_CLASSES = {"fire", "smoke"}

    def __init__(self, model, conf_threshold: float = 0.6, iou_threshold: float = 0.45):
        self._model = model
        self._conf = conf_threshold
        self._iou = iou_threshold
        self.last_latency_ms: float = 0.0

    # ── Synchronous predict (runs inside thread pool) ────────────────
    def _predict_sync(self, frame: np.ndarray) -> List[Detection]:
        t0 = time.perf_counter()
        results = self._model.predict(
            source=frame,
            conf=self._conf,
            iou=self._iou,
            verbose=False,
        )
        self.last_latency_ms = (time.perf_counter() - t0) * 1000

        detections: List[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                cls_name = self._model.names.get(cls_id, "unknown").lower()

                # Skip the 'default' / background class
                if cls_name not in self.ALERT_CLASSES:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detections.append(
                    Detection(
                        class_name=cls_name,
                        confidence=round(conf, 4),
                        bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    )
                )
        return detections

    # ── Async predict (safe for FastAPI handlers) ────────────────────
    async def predict(self, frame: np.ndarray) -> List[Detection]:
        """Run inference in a background thread so the event loop stays free."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, self._predict_sync, frame)

    def predict_sync(self, frame: np.ndarray) -> List[Detection]:
        """Synchronous variant for use inside workers / tests."""
        return self._predict_sync(frame)

    # ── Annotated frame ──────────────────────────────────────────────
    def annotate_frame(self, frame: np.ndarray) -> tuple[np.ndarray, List[Detection]]:
        """
        Run prediction and draw bounding boxes on a *copy* of the frame.
        Returns ``(annotated_frame, detections)``.
        """
        detections = self._predict_sync(frame)
        annotated = frame.copy()

        import cv2

        for det in detections:
            colour = (0, 0, 255) if det.class_name == "fire" else (0, 165, 255)
            label = f"{det.class_name} {det.confidence:.0%}"
            x1, y1 = int(det.bbox.x1), int(det.bbox.y1)
            x2, y2 = int(det.bbox.x2), int(det.bbox.y2)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), colour, 2)

            # Label background
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), colour, -1)
            cv2.putText(
                annotated, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
            )

        return annotated, detections
