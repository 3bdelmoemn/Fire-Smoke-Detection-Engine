"""
Unit tests for TemporalValidator.

Tests the core false-positive prevention logic:
- Single-frame detections do NOT trigger sustained status
- Sustained detections over configured duration DO trigger
- Intermittent detections are handled correctly
- Class-specific reset works
- Confidence threshold filtering works
"""

from __future__ import annotations

import pytest

from app.schemas.detection import BBox, Detection
from app.services.temporal_validator import TemporalValidator


def _make_detection(cls: str = "fire", conf: float = 0.85) -> Detection:
    """Helper to create a Detection with reasonable defaults."""
    return Detection(
        class_name=cls,
        confidence=conf,
        bbox=BBox(x1=100, y1=100, x2=200, y2=200),
    )


class TestTemporalValidator:
    """Tests for the sliding-window temporal validator."""

    def _make_validator(self, **kwargs) -> TemporalValidator:
        defaults = {
            "window_seconds": 5.0,
            "min_consecutive_frames": 5,
            "min_detection_duration": 2.0,
            "detection_ratio_threshold": 0.8,
            "confidence_threshold": 0.6,
        }
        defaults.update(kwargs)
        return TemporalValidator(**defaults)

    # ── Test: Single frame does NOT trigger ──────────────────────────

    def test_single_frame_not_sustained(self):
        """A single detection frame should never trigger sustained status."""
        v = self._make_validator()
        result = v.update([_make_detection()], now=1.0)
        assert result.get("fire", False) is False

    # ── Test: Sustained detection DOES trigger ───────────────────────

    def test_sustained_detection_triggers(self):
        """
        Feeding fire detections for enough consecutive frames over the
        minimum duration should trigger sustained status.
        """
        v = self._make_validator(
            min_consecutive_frames=5,
            min_detection_duration=1.0,
            window_seconds=10.0,
        )
        dets = [_make_detection("fire", 0.9)]

        # Feed 10 frames over 2 seconds
        for i in range(10):
            result = v.update(dets, now=1.0 + i * 0.25)

        # After 10 frames at 0.25s intervals (2.5s total), should be sustained
        assert result["fire"] is True

    # ── Test: Below confidence threshold ─────────────────────────────

    def test_below_confidence_threshold_not_sustained(self):
        """Detections below the confidence threshold should be ignored."""
        v = self._make_validator(confidence_threshold=0.7)
        dets = [_make_detection("fire", 0.5)]  # below threshold

        for i in range(20):
            result = v.update(dets, now=1.0 + i * 0.25)

        # Should never trigger because confidence is too low
        assert result.get("fire", False) is False

    # ── Test: Intermittent detections ────────────────────────────────

    def test_intermittent_detections_not_sustained(self):
        """
        Detections that appear and disappear should NOT trigger sustained
        status because the consecutive frame count resets.
        """
        v = self._make_validator(min_consecutive_frames=5, min_detection_duration=1.0)

        # Alternate: detect, miss, detect, miss...
        for i in range(20):
            dets = [_make_detection()] if i % 2 == 0 else []
            result = v.update(dets, now=1.0 + i * 0.1)

        assert result.get("fire", False) is False

    # ── Test: Multiple classes independently ─────────────────────────

    def test_multiple_classes_independent(self):
        """Fire and smoke should be tracked independently."""
        v = self._make_validator(
            min_consecutive_frames=3,
            min_detection_duration=0.5,
            window_seconds=10.0,
        )

        # Feed fire only for 5 frames
        for i in range(5):
            result = v.update([_make_detection("fire")], now=1.0 + i * 0.25)

        assert result.get("fire") is True
        assert result.get("smoke", False) is False

    # ── Test: Reset clears state ─────────────────────────────────────

    def test_reset_clears_state(self):
        """After reset, no class should be sustained."""
        v = self._make_validator(min_consecutive_frames=3, min_detection_duration=0.5)

        for i in range(10):
            v.update([_make_detection()], now=1.0 + i * 0.25)

        v.reset()
        result = v.update([], now=10.0)
        assert not any(result.values())

    # ── Test: Class-specific reset ───────────────────────────────────

    def test_reset_class(self):
        """Resetting one class should not affect others."""
        v = self._make_validator(
            min_consecutive_frames=3,
            min_detection_duration=0.5,
            window_seconds=10.0,
        )

        dets = [_make_detection("fire"), _make_detection("smoke")]
        for i in range(10):
            result = v.update(dets, now=1.0 + i * 0.25)

        assert result.get("fire") is True
        assert result.get("smoke") is True

        v.reset_class("fire")
        result = v.update(dets, now=10.0)
        # Fire just restarted, shouldn't be sustained yet
        assert result.get("fire") is False

    # ── Test: Window eviction ────────────────────────────────────────

    def test_old_entries_evicted(self):
        """Entries older than window_seconds should be evicted."""
        v = self._make_validator(window_seconds=2.0, min_consecutive_frames=3, min_detection_duration=1.0)

        # Feed detections at time 0-1
        for i in range(5):
            v.update([_make_detection()], now=float(i) * 0.25)

        # Jump far into the future — old entries should be gone
        result = v.update([], now=100.0)
        assert result.get("fire", False) is False

    # ── Test: Empty detections ───────────────────────────────────────

    def test_empty_detections(self):
        """Passing an empty detection list should not crash."""
        v = self._make_validator()
        result = v.update([], now=1.0)
        assert isinstance(result, dict)
