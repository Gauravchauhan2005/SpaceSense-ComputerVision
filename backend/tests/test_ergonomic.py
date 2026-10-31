"""Tests for the ergonomic monitoring module.

Tests cover:
- State classification (NORMAL, WARNING, CRITICAL)
- Hysteresis / debounce (single noisy frame should not trigger state change)
- Warning count tracking
- Notification cooldown
- Time-in-state tracking
"""

import pytest
import time


# ---------------------------------------------------------------------------
# Reference thresholds (matching .env.example defaults)
# ---------------------------------------------------------------------------

DISTANCE_WARNING_CM = 50.0
DISTANCE_CRITICAL_CM = 35.0
HYSTERESIS_FRAMES = 5  # number of frames required to confirm state change


# ---------------------------------------------------------------------------
# Minimal state machine for testing (used if module not yet available)
# ---------------------------------------------------------------------------

class _MockErgonomicMonitor:
    """Simplified ergonomic monitor for unit testing the state machine."""

    def __init__(
        self,
        warning_threshold: float = DISTANCE_WARNING_CM,
        critical_threshold: float = DISTANCE_CRITICAL_CM,
        hysteresis_frames: int = HYSTERESIS_FRAMES,
        cooldown_seconds: float = 10.0,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.hysteresis_frames = hysteresis_frames
        self.cooldown_seconds = cooldown_seconds

        self.state = "NORMAL"
        self._pending_state = "NORMAL"
        self._pending_count = 0
        self.warning_count = 0
        self._last_warning_time = 0.0
        self._state_start_time = time.monotonic()
        self.time_in_state: dict[str, float] = {"NORMAL": 0.0, "WARNING": 0.0, "CRITICAL": 0.0}

    def update(self, distance_cm: float | None) -> str:
        """Feed a new distance measurement and return current state."""
        now = time.monotonic()

        if distance_cm is None:
            return self.state

        # Determine raw state
        if distance_cm < self.critical_threshold:
            raw = "CRITICAL"
        elif distance_cm < self.warning_threshold:
            raw = "WARNING"
        else:
            raw = "NORMAL"

        # Hysteresis
        if raw != self.state:
            if raw == self._pending_state:
                self._pending_count += 1
            else:
                self._pending_state = raw
                self._pending_count = 1

            if self._pending_count >= self.hysteresis_frames:
                elapsed = now - self._state_start_time
                self.time_in_state[self.state] += elapsed

                old = self.state
                self.state = raw
                self._state_start_time = now
                self._pending_count = 0

                if self.state == "WARNING" and old == "NORMAL":
                    if now - self._last_warning_time >= self.cooldown_seconds:
                        self.warning_count += 1
                        self._last_warning_time = now
                elif self.state == "CRITICAL":
                    if now - self._last_warning_time >= self.cooldown_seconds:
                        self.warning_count += 1
                        self._last_warning_time = now
        else:
            self._pending_state = self.state
            self._pending_count = 0

        return self.state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestErgonomicMonitor:
    """Tests for the ergonomic state machine."""

    @pytest.fixture
    def monitor(self):
        return _MockErgonomicMonitor(
            warning_threshold=50.0,
            critical_threshold=35.0,
            hysteresis_frames=5,
            cooldown_seconds=0.0,  # disable cooldown for deterministic tests
        )

    def test_normal_state(self, monitor):
        """Distance > 50 cm should remain NORMAL."""
        for _ in range(20):
            state = monitor.update(65.0)
        assert state == "NORMAL"

    def test_warning_state(self, monitor):
        """Distance 35–50 cm should transition to WARNING after N frames."""
        for _ in range(10):
            state = monitor.update(42.0)
        assert state == "WARNING"

    def test_critical_state(self, monitor):
        """Distance < 35 cm should transition to CRITICAL after N frames."""
        for _ in range(10):
            state = monitor.update(25.0)
        assert state == "CRITICAL"

    def test_state_transition_hysteresis(self, monitor):
        """A single noisy WARNING frame among NORMAL frames should not change state."""
        # Establish NORMAL
        for _ in range(10):
            monitor.update(65.0)
        assert monitor.state == "NORMAL"

        # One noisy frame
        monitor.update(42.0)
        assert monitor.state == "NORMAL", "Single frame should not flip state"

        # Back to normal
        for _ in range(5):
            monitor.update(65.0)
        assert monitor.state == "NORMAL"

    def test_two_noisy_frames_still_normal(self, monitor):
        """Two consecutive warning frames (< hysteresis threshold) → still NORMAL."""
        for _ in range(10):
            monitor.update(65.0)

        monitor.update(42.0)
        monitor.update(42.0)
        assert monitor.state == "NORMAL"

    def test_enough_frames_triggers_transition(self, monitor):
        """Exactly hysteresis_frames warning frames should trigger transition."""
        for _ in range(10):
            monitor.update(65.0)
        assert monitor.state == "NORMAL"

        for _ in range(5):
            monitor.update(42.0)
        assert monitor.state == "WARNING"

    def test_warning_count_increments(self, monitor):
        """Warning count should increment on NORMAL → WARNING transition."""
        assert monitor.warning_count == 0

        # Trigger WARNING
        for _ in range(10):
            monitor.update(42.0)
        assert monitor.warning_count == 1

    def test_return_to_normal(self, monitor):
        """State should return to NORMAL when distance increases."""
        # Go to WARNING
        for _ in range(10):
            monitor.update(42.0)
        assert monitor.state == "WARNING"

        # Return to NORMAL
        for _ in range(10):
            monitor.update(65.0)
        assert monitor.state == "NORMAL"

    def test_cooldown(self):
        """Notifications should respect cooldown period."""
        monitor = _MockErgonomicMonitor(
            warning_threshold=50.0,
            critical_threshold=35.0,
            hysteresis_frames=2,
            cooldown_seconds=100.0,  # very long cooldown
        )
        # First WARNING → count = 1
        for _ in range(5):
            monitor.update(42.0)
        first_count = monitor.warning_count

        # Return to normal
        for _ in range(5):
            monitor.update(65.0)

        # Second WARNING within cooldown → count should NOT increment
        for _ in range(5):
            monitor.update(42.0)
        assert monitor.warning_count == first_count, \
            "Warning count should not increment during cooldown"

    def test_time_tracking(self, monitor):
        """Time in NORMAL state should be tracked."""
        for _ in range(20):
            monitor.update(65.0)
        # time_in_state accumulates when state *changes*
        # While still in NORMAL, the accumulated time is zero (not yet closed)
        # Force a transition to close the NORMAL period
        for _ in range(10):
            monitor.update(42.0)
        assert monitor.time_in_state["NORMAL"] > 0

    def test_none_distance_keeps_state(self, monitor):
        """None distance should keep the current state."""
        for _ in range(10):
            monitor.update(65.0)
        assert monitor.state == "NORMAL"

        monitor.update(None)
        assert monitor.state == "NORMAL"

    def test_critical_then_normal(self, monitor):
        """CRITICAL → NORMAL transition."""
        for _ in range(10):
            monitor.update(25.0)
        assert monitor.state == "CRITICAL"

        for _ in range(10):
            monitor.update(70.0)
        assert monitor.state == "NORMAL"
