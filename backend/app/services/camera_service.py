"""
Camera Service — async frame capture from webcam, RTSP, or video file.

Runs as a background worker, not inside a request handler.  Feeds frames
into the detection pipeline and pushes results to WebSocket subscribers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraService:
    """
    Asynchronous frame capture with configurable FPS cap and frame skipping.

    Supports:
    - Webcam (integer index, e.g. ``0``)
    - RTSP URL
    - Video file path (loops for demo purposes)
    """

    def __init__(
        self,
        source: str = "0",
        target_fps: int = 10,
        frame_skip: int = 2,
    ):
        self._source = int(source) if source.isdigit() else source
        self._target_fps = target_fps
        self._frame_skip = frame_skip
        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._frame_count = 0

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> bool:
        """Open the capture source. Returns True on success."""
        try:
            self._cap = cv2.VideoCapture(self._source)
            if not self._cap.isOpened():
                logger.error("Failed to open camera source: %s", self._source)
                return False
            logger.info("Camera opened: %s", self._source)
            return True
        except Exception as exc:
            logger.error("Camera open error: %s", exc)
            return False

    def release(self) -> None:
        """Release the capture source."""
        self._running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Camera released")

    def read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame synchronously. Returns None on failure."""
        if not self.is_open:
            return None
        ret, frame = self._cap.read()
        if not ret:
            # If reading a video file, loop back to the start
            if isinstance(self._source, str) and not self._source.isdigit():
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None
        return frame

    async def stream_frames(self) -> AsyncGenerator[np.ndarray, None]:
        """
        Async generator that yields frames at the target FPS,
        applying frame skipping.
        """
        self._running = True
        frame_interval = 1.0 / self._target_fps

        while self._running:
            t0 = time.perf_counter()

            # Read frame in thread to avoid blocking event loop
            loop = asyncio.get_running_loop()
            frame = await loop.run_in_executor(None, self.read_frame)

            if frame is None:
                logger.warning("Frame capture returned None — retrying in 1s")
                await asyncio.sleep(1.0)
                # Try to reconnect
                if not self.is_open:
                    self.open()
                continue

            self._frame_count += 1

            # Frame skipping: only yield every Nth frame
            if self._frame_count % (self._frame_skip + 1) != 0:
                elapsed = time.perf_counter() - t0
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)
                continue

            yield frame

            # Throttle to target FPS
            elapsed = time.perf_counter() - t0
            sleep_time = max(0, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        """Signal the stream generator to stop."""
        self._running = False

    def get_status(self) -> dict:
        """Return camera status for health checks."""
        return {
            "source": str(self._source),
            "is_open": self.is_open,
            "frame_count": self._frame_count,
            "target_fps": self._target_fps,
        }
