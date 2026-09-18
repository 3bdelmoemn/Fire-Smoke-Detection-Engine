"""
Unit tests for AlertDecisionEngine.

Tests the cooldown / de-duplication logic:
- Alert fires when sustained and cooldown is not active
- Alert is suppressed within cooldown window
- Cooldown resets correctly
- Multiple classes handled independently
"""

from __future__ import annotations

import pytest

from app.services.alert_decision_engine import AlertDecisionEngine


class TestAlertDecisionEngine:
    """Tests for the alert cooldown engine."""

    def test_first_alert_fires(self):
        """The very first sustained detection should trigger an alert."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        alerts = engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.92},
            durations={"fire": 3.5},
            now=100.0,
        )

        assert len(alerts) == 1
        assert alerts[0].class_name == "fire"
        assert alerts[0].confidence == 0.92
        assert alerts[0].duration_seconds == 3.5

    def test_cooldown_suppresses_duplicate(self):
        """A second sustained detection within cooldown should NOT alert."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        # First alert at t=100
        engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.9},
            durations={"fire": 3.0},
            now=100.0,
        )

        # Second evaluation at t=130 (30s later, still in cooldown)
        alerts = engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.95},
            durations={"fire": 6.0},
            now=130.0,
        )

        assert len(alerts) == 0

    def test_alert_fires_after_cooldown(self):
        """After cooldown expires, a new sustained detection should alert."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        # First alert at t=100
        engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.9},
            durations={"fire": 3.0},
            now=100.0,
        )

        # After cooldown at t=161
        alerts = engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.88},
            durations={"fire": 4.0},
            now=161.0,
        )

        assert len(alerts) == 1
        assert alerts[0].class_name == "fire"

    def test_not_sustained_no_alert(self):
        """If no class is sustained, no alert should fire."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        alerts = engine.evaluate(
            sustained={"fire": False, "smoke": False},
            confidences={"fire": 0.3, "smoke": 0.2},
            durations={"fire": 1.0, "smoke": 0.5},
            now=100.0,
        )

        assert len(alerts) == 0

    def test_multiple_classes_independent_cooldown(self):
        """Cooldown for fire should not affect smoke alerts."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        # Fire alert at t=100
        alerts1 = engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.9},
            durations={"fire": 3.0},
            now=100.0,
        )
        assert len(alerts1) == 1

        # Smoke alert at t=110 (fire in cooldown, but smoke is independent)
        alerts2 = engine.evaluate(
            sustained={"fire": True, "smoke": True},
            confidences={"fire": 0.9, "smoke": 0.85},
            durations={"fire": 5.0, "smoke": 4.0},
            now=110.0,
        )

        # Fire suppressed (cooldown), smoke fires
        assert len(alerts2) == 1
        assert alerts2[0].class_name == "smoke"

    def test_both_classes_alert_simultaneously(self):
        """Both fire and smoke can alert at the same time if neither is in cooldown."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        alerts = engine.evaluate(
            sustained={"fire": True, "smoke": True},
            confidences={"fire": 0.9, "smoke": 0.8},
            durations={"fire": 3.0, "smoke": 3.0},
            now=100.0,
        )

        assert len(alerts) == 2
        names = {a.class_name for a in alerts}
        assert names == {"fire", "smoke"}

    def test_reset_clears_cooldown(self):
        """After reset, alert should fire immediately."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.9},
            durations={"fire": 3.0},
            now=100.0,
        )

        engine.reset()

        alerts = engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.88},
            durations={"fire": 2.0},
            now=105.0,
        )
        assert len(alerts) == 1

    def test_time_until_next_alert(self):
        """Should correctly report remaining cooldown time."""
        engine = AlertDecisionEngine(cooldown_seconds=60.0)

        engine.evaluate(
            sustained={"fire": True},
            confidences={"fire": 0.9},
            durations={"fire": 3.0},
            now=100.0,
        )

        remaining = engine.time_until_next_alert("fire", now=130.0)
        assert remaining == pytest.approx(30.0)

        remaining = engine.time_until_next_alert("fire", now=161.0)
        assert remaining == 0.0

        # Unknown class has no cooldown
        remaining = engine.time_until_next_alert("smoke", now=130.0)
        assert remaining == 0.0
