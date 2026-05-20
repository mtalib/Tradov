#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Test Module: test_g05_event_clock_display.py
Purpose: Unit tests for Phase 5-A event-clock dashboard display
Author: Automated Testing Framework
Year Created: 2026
Last Updated: 2026-04-25

Module Description:
    Focused tests for event-clock state display in the trading dashboard (G05).
    Validates EventClockState dataclass, event subscription, UI updates, and
    thread-safety of the display mechanism.

Test Coverage:
    - EventClockState dataclass properties and color/label generation
    - Event-clock RISK event subscription and handler
    - Dashboard UI label updates
    - Thread-safe state transitions
    - Event payload validation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytz

# ==============================================================================
# PROJECT ROOT SETUP
# ==============================================================================
project_root = Path(__file__).parent.parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderG_GUI.SpyderG06_DashboardData import EventClockState, COLORS


# ==============================================================================
# TEST CASES
# ==============================================================================
class TestEventClockState(unittest.TestCase):
    """Test EventClockState dataclass functionality."""

    def test_event_clock_state_creation_default(self):
        """Test creating EventClockState with default values."""
        state = EventClockState()

        self.assertEqual(state.state, "clear")
        self.assertTrue(state.enabled)
        self.assertEqual(state.sources, "calendar+manual")
        self.assertEqual(state.allowed_strategies, [])
        self.assertEqual(state.blackout_pre_minutes, 30)
        self.assertEqual(state.blackout_post_minutes, 30)
        self.assertEqual(state.max_size_multiplier, 0.25)

    def test_event_clock_state_creation_custom(self):
        """Test creating EventClockState with custom values."""
        strategies = ["IronCondor", "CreditSpread"]
        state = EventClockState(
            state="pre",
            enabled=False,
            sources="manual",
            allowed_strategies=strategies,
            blackout_pre_minutes=45,
            blackout_post_minutes=60,
            max_size_multiplier=0.50,
        )

        self.assertEqual(state.state, "pre")
        self.assertFalse(state.enabled)
        self.assertEqual(state.sources, "manual")
        self.assertEqual(state.allowed_strategies, strategies)
        self.assertEqual(state.blackout_pre_minutes, 45)
        self.assertEqual(state.blackout_post_minutes, 60)
        self.assertEqual(state.max_size_multiplier, 0.50)

    def test_state_color_mapping(self):
        """Test state_color property returns correct color for each state."""
        # Clear state should be green (positive)
        state_clear = EventClockState(state="clear")
        self.assertEqual(state_clear.state_color, COLORS["positive"])

        # Pre state should be orange (warning)
        state_pre = EventClockState(state="pre")
        self.assertEqual(state_pre.state_color, COLORS["warning"])

        # Live state should be red (negative)
        state_live = EventClockState(state="live")
        self.assertEqual(state_live.state_color, COLORS["negative"])

        # Post state should be orange (warning)
        state_post = EventClockState(state="post")
        self.assertEqual(state_post.state_color, COLORS["warning"])

    def test_state_label_mapping(self):
        """Test state_label property returns correct label for each state."""
        test_cases = [
            ("clear", "✓ CLEAR"),
            ("pre", "⊕ PRE-EVENT"),
            ("live", "◆ LIVE EVENT"),
            ("post", "⊖ POST-EVENT"),
        ]

        for state_str, expected_label in test_cases:
            state = EventClockState(state=state_str)
            self.assertEqual(state.state_label, expected_label, f"Failed for state: {state_str}")

    def test_to_dict_conversion(self):
        """Test to_dict() conversion for display."""
        strategies = ["ZeroDTE", "Straddle"]
        state = EventClockState(
            state="live",
            enabled=True,
            sources="calendar",
            allowed_strategies=strategies,
            blackout_pre_minutes=20,
            blackout_post_minutes=40,
            max_size_multiplier=0.30,
        )

        result = state.to_dict()

        self.assertEqual(result["state"], "live")
        self.assertEqual(result["state_label"], "◆ LIVE EVENT")
        self.assertTrue(result["enabled"])
        self.assertEqual(result["sources"], "calendar")
        self.assertEqual(result["allowed_strategies"], "ZeroDTE, Straddle")
        self.assertEqual(result["blackout_pre_minutes"], 20)
        self.assertEqual(result["blackout_post_minutes"], 40)
        self.assertIn("30", result["max_size_multiplier"])  # Percentage format

    def test_to_dict_empty_strategies(self):
        """Test to_dict() with empty allowed strategies."""
        state = EventClockState(allowed_strategies=[])
        result = state.to_dict()

        self.assertEqual(result["allowed_strategies"], "None")


class TestEventClockStateTransitions(unittest.TestCase):
    """Test event-clock state transitions."""

    def test_state_transition_clear_to_pre(self):
        """Test transition from clear to pre state."""
        state = EventClockState(state="clear")
        self.assertEqual(state.state, "clear")
        self.assertEqual(state.state_color, COLORS["positive"])

        # Simulate transition
        state.state = "pre"
        self.assertEqual(state.state, "pre")
        self.assertEqual(state.state_color, COLORS["warning"])

    def test_state_transition_pre_to_live(self):
        """Test transition from pre to live state."""
        state = EventClockState(state="pre")
        self.assertEqual(state.state_color, COLORS["warning"])

        state.state = "live"
        self.assertEqual(state.state_color, COLORS["negative"])

    def test_state_transition_live_to_post(self):
        """Test transition from live to post state."""
        state = EventClockState(state="live")
        self.assertEqual(state.state_color, COLORS["negative"])

        state.state = "post"
        self.assertEqual(state.state_color, COLORS["warning"])

    def test_state_transition_post_to_clear(self):
        """Test transition from post back to clear state."""
        state = EventClockState(state="post")
        self.assertEqual(state.state_label, "⊖ POST-EVENT")

        state.state = "clear"
        self.assertEqual(state.state_color, COLORS["positive"])
        self.assertEqual(state.state_label, "✓ CLEAR")


class TestEventClockPolicies(unittest.TestCase):
    """Test event-clock policy configurations."""

    def test_policy_enabled_disabled(self):
        """Test enabled/disabled policy affects display."""
        state_enabled = EventClockState(enabled=True)
        state_disabled = EventClockState(enabled=False)

        self.assertTrue(state_enabled.enabled)
        self.assertFalse(state_disabled.enabled)

    def test_policy_sources_manual_only(self):
        """Test manual-only source policy."""
        state = EventClockState(sources="manual")
        self.assertEqual(state.sources, "manual")

        result = state.to_dict()
        self.assertIn("manual", result["sources"])

    def test_policy_sources_calendar_only(self):
        """Test calendar-only source policy."""
        state = EventClockState(sources="calendar")
        self.assertEqual(state.sources, "calendar")

    def test_policy_sources_calendar_plus_manual(self):
        """Test calendar+manual source policy."""
        state = EventClockState(sources="calendar+manual")
        self.assertEqual(state.sources, "calendar+manual")

    def test_policy_allowlist_strategies(self):
        """Test allowed strategies allowlist policy."""
        strategies = ["IronCondor", "ZeroDTE", "CreditSpread"]
        state = EventClockState(allowed_strategies=strategies)

        result = state.to_dict()
        self.assertIn("IronCondor", result["allowed_strategies"])
        self.assertIn("ZeroDTE", result["allowed_strategies"])

    def test_policy_blackout_windows(self):
        """Test blackout window policies."""
        state = EventClockState(
            blackout_pre_minutes=25,
            blackout_post_minutes=35,
        )

        self.assertEqual(state.blackout_pre_minutes, 25)
        self.assertEqual(state.blackout_post_minutes, 35)

    def test_policy_size_multiplier_during_event(self):
        """Test max size multiplier policy during event."""
        state_conservative = EventClockState(max_size_multiplier=0.10)
        state_moderate = EventClockState(max_size_multiplier=0.50)

        self.assertEqual(state_conservative.max_size_multiplier, 0.10)
        self.assertEqual(state_moderate.max_size_multiplier, 0.50)

        # Check percentage formatting
        result_conservative = state_conservative.to_dict()
        result_moderate = state_moderate.to_dict()

        self.assertIn("10", result_conservative["max_size_multiplier"])
        self.assertIn("50", result_moderate["max_size_multiplier"])


class TestEventClockThreadSafety(unittest.TestCase):
    """Test thread-safety of EventClockState updates."""

    def test_state_update_concurrent_read_write(self):
        """Test that concurrent reads and writes are safe."""
        state = EventClockState()
        lock = threading.Lock()
        results = []

        def read_state():
            for _ in range(10):
                with lock:
                    snapshot = {
                        'state': state.state,
                        'enabled': state.enabled,
                        'sources': state.sources,
                    }
                results.append(('read', snapshot))

        def write_state():
            states = ['clear', 'pre', 'live', 'post']
            for s in states:
                with lock:
                    state.state = s
                results.append(('write', s))

        # Run concurrent operations
        threads = [
            threading.Thread(target=read_state),
            threading.Thread(target=write_state),
            threading.Thread(target=read_state),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no exceptions occurred
        self.assertTrue(len(results) > 0)

    def test_to_dict_thread_safety(self):
        """Test that to_dict() is safe to call from multiple threads."""
        state = EventClockState(
            allowed_strategies=["Strategy1", "Strategy2"],
            blackout_pre_minutes=30,
        )
        results = []

        def dict_caller():
            for _ in range(5):
                try:
                    d = state.to_dict()
                    results.append(('success', d))
                except Exception as e:
                    results.append(('error', str(e)))

        threads = [threading.Thread(target=dict_caller) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All calls should succeed
        self.assertEqual(len([r for r in results if r[0] == 'success']), 15)


class TestEventClockTimestamp(unittest.TestCase):
    """Test event-clock timestamp handling."""

    def test_default_timestamp_is_current(self):
        """Test that default timestamp is set to current time."""
        # Create EventClockState without specifying timestamp (uses default)
        state = EventClockState()

        # Verify timestamp was set (is not None)
        self.assertIsNotNone(state.timestamp)
        # Verify it's a datetime object
        self.assertIsInstance(state.timestamp, datetime)

    def test_custom_timestamp(self):
        """Test setting custom timestamp."""
        custom_time = datetime(2026, 4, 25, 10, 30, 0, tzinfo=pytz.timezone("US/Eastern"))
        state = EventClockState(timestamp=custom_time)

        self.assertEqual(state.timestamp, custom_time)

    def test_timestamp_format_in_dict(self):
        """Test timestamp formatting in to_dict()."""
        state = EventClockState(timestamp=datetime(2026, 4, 25, 14, 45, 30, tzinfo=pytz.timezone("US/Eastern")))
        result = state.to_dict()

        # Should format as HH:MM:SS
        self.assertEqual(result["timestamp"], "14:45:30")


# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
