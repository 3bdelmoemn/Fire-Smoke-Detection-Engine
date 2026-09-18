"""
Alert Decision Engine — cooldown and de-duplication layer.

Sits on top of the ``TemporalValidator``.  It receives the validator's
"sustained" boolean per class and applies a cooldown timer so that
a single continuous fire event does not spam notifications.

This is a **pure logic** component with no I/O — it only knows about
detection events going *in* and alert decisions coming *out*.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AlertEvent:
    """Payload emitted when an alert is triggered."""
    class_name: str
    confidence: float
    timestamp: float
    duration_seconds: float


class AlertDecisionEngine:
    """
    Determines whether a sustained detection should trigger an alert,
    respecting a per-class cooldown window.

    Parameters
    ----------
    cooldown_seconds : float
        After an alert fires for a class, suppress further alerts for
        this many seconds.
    """

    def __init__(self, cooldown_seconds: float = 60.0):
        self.cooldown_seconds = cooldown_seconds
        # class_name → timestamp of last alert
        self._last_alert: Dict[str, float] = {}

    def evaluate(
        self,
        sustained: Dict[str, bool],
        confidences: Dict[str, float],
        durations: Dict[str, float],
        now: Optional[float] = None,
    ) -> List[AlertEvent]:
        """
        Given the temporal validator's sustained status per class,
        return a list of ``AlertEvent`` objects for any class that
        should fire an alert right now.

        Parameters
        ----------
        sustained : dict
            ``{class_name: bool}`` — output of ``TemporalValidator.update()``.
        confidences : dict
            ``{class_name: float}`` — highest confidence in current window.
        durations : dict
            ``{class_name: float}`` — seconds of continuous detection.
        now : float, optional
            Current timestamp (for testing); defaults to ``time.time()``.
        """
        now = now if now is not None else time.time()
        alerts: List[AlertEvent] = []

        for cls, is_sustained in sustained.items():
            if not is_sustained:
                continue

            last = self._last_alert.get(cls)
            if last is not None and (now - last) < self.cooldown_seconds:
                # Still within cooldown — suppress
                continue

            # Fire alert
            self._last_alert[cls] = now
            alerts.append(
                AlertEvent(
                    class_name=cls,
                    confidence=confidences.get(cls, 0.0),
                    timestamp=now,
                    duration_seconds=durations.get(cls, 0.0),
                )
            )

        return alerts

    def reset(self) -> None:
        """Clear all cooldown state."""
        self._last_alert.clear()

    def reset_class(self, class_name: str) -> None:
        self._last_alert.pop(class_name, None)

    def time_until_next_alert(self, class_name: str, now: Optional[float] = None) -> float:
        """Seconds remaining before this class can alert again. 0 = ready."""
        now = now if now is not None else time.time()
        last = self._last_alert.get(class_name)
        if last is None:
            return 0.0
        remaining = self.cooldown_seconds - (now - last)
        return max(0.0, remaining)
