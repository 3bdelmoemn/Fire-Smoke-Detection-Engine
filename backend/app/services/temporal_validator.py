"""
Temporal Validator — rolling-window false-positive prevention.

This is a pure, I/O-free state machine.  It maintains a sliding window
of recent detections per class and decides whether a *sustained* detection
condition is met.  The AlertDecisionEngine sits on top and applies the
cooldown / de-duplication layer.

Design:
- **Condition A**: at least ``min_consecutive_frames`` consecutive frames
  contain a detection of the target class above ``confidence_threshold``.
- **Condition B**: the ratio of frames with detections to total frames in
  the window is ≥ ``detection_ratio_threshold``.
- **Condition C**: the continuous detection duration ≥ ``min_detection_duration``.

All three must be satisfied for ``is_sustained()`` to return True.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

from app.schemas.detection import Detection


@dataclass
class ClassState:
    """Per-class tracking state."""
    consecutive_count: int = 0
    first_seen: Optional[float] = None
    total_detections: int = 0
    total_frames: int = 0
    max_confidence: float = 0.0


class TemporalValidator:
    """
    Sliding-window validator that distinguishes transient from sustained
    detections.

    Parameters
    ----------
    window_seconds : float
        How far back (in seconds) the sliding window looks.
    min_consecutive_frames : int
        Minimum consecutive frames that must contain a detection.
    min_detection_duration : float
        Minimum continuous duration (seconds) the detection must persist.
    detection_ratio_threshold : float
        Minimum ratio of detection-frames / total-frames in the window.
    confidence_threshold : float
        Only detections above this confidence are counted.
    """

    def __init__(
        self,
        window_seconds: float = 5.0,
        min_consecutive_frames: int = 30,
        min_detection_duration: float = 3.0,
        detection_ratio_threshold: float = 0.8,
        confidence_threshold: float = 0.6,
    ):
        self.window_seconds = window_seconds
        self.min_consecutive_frames = min_consecutive_frames
        self.min_detection_duration = min_detection_duration
        self.detection_ratio_threshold = detection_ratio_threshold
        self.confidence_threshold = confidence_threshold

        # window stores (timestamp, {class_name: max_confidence}) per frame
        self._window: Deque[tuple[float, Dict[str, float]]] = deque()
        self._class_states: Dict[str, ClassState] = {}
        self._total_frames: int = 0

    # ── Public API ───────────────────────────────────────────────────

    def update(
        self, detections: List[Detection], now: Optional[float] = None
    ) -> Dict[str, bool]:
        """
        Push a new frame's detections and return sustained status per class.

        Returns
        -------
        dict mapping class_name → bool (True = sustained, False = not yet).
        """
        now = now if now is not None else time.time()
        self._total_frames += 1

        # Build per-class max confidence for this frame
        frame_classes: Dict[str, float] = {}
        for det in detections:
            if det.confidence >= self.confidence_threshold:
                existing = frame_classes.get(det.class_name, 0.0)
                frame_classes[det.class_name] = max(existing, det.confidence)

        self._window.append((now, frame_classes))
        self._evict(now)
        self._update_class_states(frame_classes, now)

        return {cls: self._evaluate(cls) for cls in self._class_states}

    def reset(self) -> None:
        """Clear all state."""
        self._window.clear()
        self._class_states.clear()
        self._total_frames = 0

    def reset_class(self, class_name: str) -> None:
        """Reset state for a specific class (e.g. after an alert fires)."""
        self._class_states.pop(class_name, None)

    def get_state(self, class_name: str) -> Optional[ClassState]:
        return self._class_states.get(class_name)

    # ── Internal ─────────────────────────────────────────────────────

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def _update_class_states(self, frame_classes: Dict[str, float], now: float) -> None:
        # Update existing class states
        all_classes = set(self._class_states.keys()) | set(frame_classes.keys())

        for cls in all_classes:
            state = self._class_states.setdefault(cls, ClassState())
            state.total_frames += 1

            if cls in frame_classes:
                state.consecutive_count += 1
                state.total_detections += 1
                state.max_confidence = max(state.max_confidence, frame_classes[cls])
                if state.first_seen is None:
                    state.first_seen = now
            else:
                # Break in detection — reset consecutive count
                state.consecutive_count = 0
                state.first_seen = None

    def _evaluate(self, class_name: str) -> bool:
        state = self._class_states.get(class_name)
        if state is None:
            return False

        # Condition A: consecutive frames
        if state.consecutive_count < self.min_consecutive_frames:
            return False

        # Condition B: detection ratio in window
        window_total = len(self._window)
        if window_total == 0:
            return False
        window_detections = sum(
            1 for _, fc in self._window if class_name in fc
        )
        ratio = window_detections / window_total
        if ratio < self.detection_ratio_threshold:
            return False

        # Condition C: continuous duration
        if state.first_seen is None:
            return False
        now = self._window[-1][0] if self._window else 0
        duration = now - state.first_seen
        if duration < self.min_detection_duration:
            return False

        return True
