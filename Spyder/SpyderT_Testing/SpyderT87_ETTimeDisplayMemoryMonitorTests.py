#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT87_ETTimeDisplayMemoryMonitorTests.py
Purpose: Comprehensive tests for U22 ETTimeDisplay and U23 MemoryMonitor

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-06 Time: 10:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


import pytz

_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

# U01 Logger
_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# U02 ErrorHandler
_u02 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# U03 DateTimeUtils (needed by U22)
_u03 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU03_DateTimeUtils.py")
_u03.pytz = pytz
_u03.SpyderLogger = _u01.SpyderLogger
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03
sys.modules["Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils"] = _u03

# U22 ETTimeDisplay
_u22 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU22_ETTimeDisplay.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay"] = _u22

# U23 MemoryMonitor
_u23 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU23_MemoryMonitor.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU23_MemoryMonitor"] = _u23


# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
import gc
import time as time_module
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
import psutil


# ==============================================================================
# U22 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay import (
    # Constants
    DASHBOARD_TIME_FORMAT,
    SIMPLE_TIME_FORMAT,
    EASTERN_TZ,
    # Functions
    get_et_time_string,
    get_et_time_for_dashboard,
    get_current_et_datetime,
    get_et_display,
    # Class
    SimpleETDisplay,
)


# ==============================================================================
# U23 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU23_MemoryMonitor import (
    # Constants
    MEMORY_WARNING_THRESHOLD,
    MEMORY_CRITICAL_THRESHOLD,
    MEMORY_EMERGENCY_THRESHOLD,
    MEMORY_CHECK_INTERVAL,
    GC_INTERVAL,
    MAX_MEMORY_HISTORY,
    PSUTIL_AVAILABLE,
    # Dataclasses
    MemorySnapshot,
    ProcessInfo,
    MemoryAlert,
    MemoryStats,
    # Class
    SpyderMemoryMonitor,
    # Module functions
    get_memory_monitor,
    start_global_monitoring,
    stop_global_monitoring,
)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U22 — ET TIME DISPLAY
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestU22Constants:
    """Tests for U22 module constants."""

    def test_dashboard_time_format_has_timezone(self):
        # "%H:%M:%S %Z" should produce HH:MM:SS TZ
        assert "%Z" in DASHBOARD_TIME_FORMAT
        assert "%H" in DASHBOARD_TIME_FORMAT

    def test_simple_time_format_no_timezone(self):
        assert "%Z" not in SIMPLE_TIME_FORMAT
        assert "%H" in SIMPLE_TIME_FORMAT

    def test_eastern_tz_is_pytz_timezone(self):
        # Should be a pytz timezone for US/Eastern
        assert EASTERN_TZ is not None
        import pytz
        # Should be convertible to a timezone string
        assert "Eastern" in str(EASTERN_TZ) or "US" in str(EASTERN_TZ)


class TestGetETTimeString:
    """Tests for get_et_time_string()."""

    def test_returns_string(self):
        result = get_et_time_string()
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        result = get_et_time_string()
        assert len(result) > 0

    def test_includes_timezone_by_default(self):
        result = get_et_time_string(include_timezone=True)
        # Should contain ET timezone abbreviation
        assert "ET" in result or "EST" in result or "EDT" in result

    def test_excludes_timezone_when_false(self):
        result = get_et_time_string(include_timezone=False)
        # Should NOT contain timezone abbreviation
        assert "EDT" not in result and "EST" not in result and "ET" not in result

    def test_simple_format_has_colons(self):
        result = get_et_time_string(include_timezone=False)
        assert ":" in result  # HH:MM:SS format

    def test_format_length_without_tz(self):
        result = get_et_time_string(include_timezone=False)
        # "HH:MM:SS" = 8 characters
        assert len(result) == 8

    def test_format_length_with_tz(self):
        result = get_et_time_string(include_timezone=True)
        # "HH:MM:SS EDT" = 12 characters (or "HH:MM:SS EST")
        assert len(result) >= 12


class TestGetETTimeForDashboard:
    """Tests for get_et_time_for_dashboard()."""

    def test_returns_string(self):
        result = get_et_time_for_dashboard()
        assert isinstance(result, str)

    def test_includes_timezone(self):
        result = get_et_time_for_dashboard()
        # Dashboard version should include timezone
        assert "ET" in result or "EST" in result or "EDT" in result

    def test_same_format_as_get_et_time_string_with_tz(self):
        result1 = get_et_time_for_dashboard()
        result2 = get_et_time_string(include_timezone=True)
        # Both should have the same format (may differ by a second)
        assert len(result1) == len(result2)

    def test_returns_non_empty(self):
        result = get_et_time_for_dashboard()
        assert len(result) > 0


class TestGetCurrentETDateTime:
    """Tests for get_current_et_datetime()."""

    def test_returns_datetime(self):
        result = get_current_et_datetime()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self):
        result = get_current_et_datetime()
        assert result.tzinfo is not None

    def test_is_in_eastern_timezone(self):
        result = get_current_et_datetime()
        # The tzinfo should be Eastern Time
        tz_name = str(result.tzinfo)
        assert "Eastern" in tz_name or "US" in tz_name or "ET" in tz_name

    def test_is_recent(self):
        result = get_current_et_datetime()
        now = datetime.now(EASTERN_TZ)
        diff = abs((result - now).total_seconds())
        assert diff < 5  # Within 5 seconds


class TestSimpleETDisplay:
    """Tests for SimpleETDisplay class."""

    def test_init(self):
        display = SimpleETDisplay()
        assert display is not None

    def test_eastern_tz_set(self):
        display = SimpleETDisplay()
        assert display.eastern_tz is not None

    def test_get_time_string_with_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string(include_tz=True)
        assert isinstance(result, str)
        assert "ET" in result or "EST" in result or "EDT" in result

    def test_get_time_string_without_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string(include_tz=False)
        assert isinstance(result, str)
        assert len(result) == 8  # HH:MM:SS

    def test_get_time_string_default_includes_tz(self):
        display = SimpleETDisplay()
        result = display.get_time_string()
        # Default is include_tz=True
        assert "ET" in result or "EST" in result or "EDT" in result

    def test_logger_set(self):
        display = SimpleETDisplay()
        assert display.logger is not None


class TestGetETDisplay:
    """Tests for get_et_display() singleton."""

    def test_returns_instance(self):
        display = get_et_display()
        assert isinstance(display, SimpleETDisplay)

    def test_singleton_behavior(self):
        display1 = get_et_display()
        display2 = get_et_display()
        assert display1 is display2

    def test_singleton_works(self):
        display = get_et_display()
        result = display.get_time_string()
        assert isinstance(result, str)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════
#  U23 — MEMORY MONITOR
# ═══════════════════════════════════════════════════════════════════════════
# ==============================================================================


class TestU23Constants:
    """Tests for U23 module constants and configuration."""

    def test_memory_thresholds_ordered(self):
        assert MEMORY_WARNING_THRESHOLD < MEMORY_CRITICAL_THRESHOLD
        assert MEMORY_CRITICAL_THRESHOLD < MEMORY_EMERGENCY_THRESHOLD

    def test_memory_warning_threshold_is_1gb(self):
        assert MEMORY_WARNING_THRESHOLD == 1e9

    def test_memory_critical_threshold_is_2gb(self):
        assert MEMORY_CRITICAL_THRESHOLD == 2e9

    def test_memory_emergency_threshold_is_4gb(self):
        assert MEMORY_EMERGENCY_THRESHOLD == 4e9

    def test_check_interval_positive(self):
        assert MEMORY_CHECK_INTERVAL > 0

    def test_gc_interval_positive(self):
        assert GC_INTERVAL > 0

    def test_max_history_positive(self):
        assert MAX_MEMORY_HISTORY > 0

    def test_psutil_available_is_bool(self):
        assert isinstance(PSUTIL_AVAILABLE, bool)


class TestMemorySnapshotDataclass:
    """Tests for MemorySnapshot dataclass."""

    def _make_snapshot(self):
        return MemorySnapshot(
            timestamp=datetime.now(),
            rss=500_000_000,   # 500 MB
            vms=1_000_000_000,  # 1 GB
            percent=5.0,
            available=8_000_000_000,
            process_count=10,
            gc_count=3,
        )

    def test_create_snapshot(self):
        snap = self._make_snapshot()
        assert snap is not None

    def test_rss_set(self):
        snap = self._make_snapshot()
        assert snap.rss == 500_000_000

    def test_percent_set(self):
        snap = self._make_snapshot()
        assert snap.percent == 5.0

    def test_process_count_set(self):
        snap = self._make_snapshot()
        assert snap.process_count == 10


class TestProcessInfoDataclass:
    """Tests for ProcessInfo dataclass."""

    def _make_proc(self):
        return ProcessInfo(
            pid=12345,
            name="test_process",
            memory_rss=100_000_000,
            memory_percent=1.5,
            cpu_percent=2.3,
            status="running",
            create_time=datetime.now(),
        )

    def test_create_process_info(self):
        proc = self._make_proc()
        assert proc.pid == 12345

    def test_name_set(self):
        proc = self._make_proc()
        assert proc.name == "test_process"

    def test_memory_rss_set(self):
        proc = self._make_proc()
        assert proc.memory_rss == 100_000_000


class TestMemoryAlertDataclass:
    """Tests for MemoryAlert dataclass."""

    def _make_alert(self, level="warning"):
        return MemoryAlert(
            level=level,
            message=f"Test {level} alert",
            memory_usage=1_200_000_000,
            recommended_action="Monitor closely",
            timestamp=datetime.now(),
        )

    def test_create_alert(self):
        alert = self._make_alert()
        assert alert is not None

    def test_level_set(self):
        alert = self._make_alert("critical")
        assert alert.level == "critical"

    def test_message_set(self):
        alert = self._make_alert()
        assert "warning" in alert.message

    def test_memory_usage_set(self):
        alert = self._make_alert()
        assert alert.memory_usage == 1_200_000_000

    def test_action_set(self):
        alert = self._make_alert()
        assert alert.recommended_action == "Monitor closely"


class TestMemoryStatsDataclass:
    """Tests for MemoryStats dataclass."""

    def test_create_memory_stats(self):
        stats = MemoryStats(
            current_usage=500_000_000,
            peak_usage=800_000_000,
            average_usage=600_000_000,
            trend_direction="stable",
            leak_detected=False,
            time_period="1h",
            measurements_count=10,
        )
        assert stats.current_usage == 500_000_000
        assert stats.trend_direction == "stable"
        assert stats.leak_detected is False


class TestSpyderMemoryMonitorInit:
    """Tests for SpyderMemoryMonitor initialization."""

    def test_default_init(self):
        monitor = SpyderMemoryMonitor()
        assert monitor is not None

    def test_auto_gc_enabled_by_default(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.enable_auto_gc is True

    def test_deep_monitoring_enabled_by_default(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.enable_deep_monitoring is True

    def test_custom_auto_gc_disabled(self):
        monitor = SpyderMemoryMonitor(enable_auto_gc=False)
        assert monitor.enable_auto_gc is False

    def test_custom_deep_monitoring_disabled(self):
        monitor = SpyderMemoryMonitor(enable_deep_monitoring=False)
        assert monitor.enable_deep_monitoring is False

    def test_monitoring_inactive_initially(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.monitoring_active is False

    def test_memory_history_initially_empty(self):
        monitor = SpyderMemoryMonitor()
        assert len(monitor.memory_history) == 0

    def test_alerts_initially_empty(self):
        monitor = SpyderMemoryMonitor()
        assert len(monitor.alerts) == 0

    def test_alert_callbacks_initially_empty(self):
        monitor = SpyderMemoryMonitor()
        assert len(monitor.alert_callbacks) == 0

    def test_stats_callbacks_initially_empty(self):
        monitor = SpyderMemoryMonitor()
        assert len(monitor.stats_callbacks) == 0

    def test_peak_memory_usage_initially_zero(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.peak_memory_usage == 0.0

    def test_total_gc_triggered_initially_zero(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.total_gc_triggered == 0


class TestSpyderMemoryMonitorStartMonitoring:
    """Tests for SpyderMemoryMonitor.start_monitoring()."""

    def test_start_monitoring_returns_bool(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.start_monitoring()
        assert isinstance(result, bool)
        # Stop if started
        if monitor.monitoring_active:
            SpyderMemoryMonitor.stop_monitoring(monitor)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_start_monitoring_sets_active(self):
        monitor = SpyderMemoryMonitor()
        monitor.start_monitoring()
        assert monitor.monitoring_active is True
        SpyderMemoryMonitor.stop_monitoring(monitor)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_start_monitoring_creates_thread(self):
        monitor = SpyderMemoryMonitor()
        monitor.start_monitoring()
        assert monitor.monitor_thread is not None
        SpyderMemoryMonitor.stop_monitoring(monitor)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_double_start_returns_true(self):
        monitor = SpyderMemoryMonitor()
        monitor.start_monitoring()
        result = monitor.start_monitoring()
        assert result is True
        SpyderMemoryMonitor.stop_monitoring(monitor)

    def test_is_monitoring_active_false_initially(self):
        monitor = SpyderMemoryMonitor()
        assert monitor.is_monitoring_active() is False


class TestSpyderMemoryMonitorStopMonitoring:
    """Tests for SpyderMemoryMonitor stopping monitoring.

    Note: Due to a naming conflict (self.stop_monitoring = threading.Event()
    shadows the stop_monitoring() method), we access the method via the class
    directly: SpyderMemoryMonitor.stop_monitoring(monitor).
    """

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_stop_monitoring_deactivates(self):
        monitor = SpyderMemoryMonitor()
        monitor.start_monitoring()
        assert monitor.monitoring_active is True
        SpyderMemoryMonitor.stop_monitoring(monitor)
        assert monitor.monitoring_active is False

    def test_stop_when_not_started_is_safe(self):
        monitor = SpyderMemoryMonitor()
        # Should not raise when called with monitoring not active
        SpyderMemoryMonitor.stop_monitoring(monitor)  # No-op

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_threading_event_is_set_after_stop(self):
        monitor = SpyderMemoryMonitor()
        monitor.start_monitoring()
        SpyderMemoryMonitor.stop_monitoring(monitor)
        # The threading.Event should be set
        assert monitor.stop_monitoring.is_set()


class TestSpyderMemoryMonitorGarbageCollection:
    """Tests for SpyderMemoryMonitor.force_garbage_collection()."""

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_returns_dict(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.force_garbage_collection()
        assert isinstance(result, dict)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_result_has_memory_before(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.force_garbage_collection()
        assert "memory_before_mb" in result

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_result_has_memory_after(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.force_garbage_collection()
        assert "memory_after_mb" in result

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_result_has_collections_performed(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.force_garbage_collection()
        assert "collections_performed" in result

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_result_has_objects_counts(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.force_garbage_collection()
        assert "objects_before" in result
        assert "objects_after" in result

    def test_returns_empty_dict_without_psutil(self):
        monitor = SpyderMemoryMonitor()
        # Simulate no psutil by removing main_process
        monitor.main_process = None
        result = monitor.force_garbage_collection()
        # Should still work (returns partial result or empty dict)
        assert isinstance(result, dict)


class TestSpyderMemoryMonitorStats:
    """Tests for SpyderMemoryMonitor.get_current_stats()."""

    def test_empty_history_returns_empty_dict(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.get_current_stats()
        assert result == {}

    def _add_snapshot(self, monitor):
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss=500_000_000,
            vms=1_000_000_000,
            percent=5.0,
            available=8_000_000_000,
            process_count=10,
            gc_count=3,
        )
        monitor.memory_history.append(snapshot)
        monitor.peak_memory_usage = max(monitor.peak_memory_usage, snapshot.rss)
        return snapshot

    def test_with_history_returns_dict(self):
        monitor = SpyderMemoryMonitor()
        self._add_snapshot(monitor)
        result = monitor.get_current_stats()
        assert isinstance(result, dict)

    def test_stats_has_current_memory(self):
        monitor = SpyderMemoryMonitor()
        self._add_snapshot(monitor)
        result = monitor.get_current_stats()
        assert "current_memory_gb" in result

    def test_stats_has_peak_memory(self):
        monitor = SpyderMemoryMonitor()
        self._add_snapshot(monitor)
        result = monitor.get_current_stats()
        assert "peak_memory_gb" in result

    def test_stats_has_total_gc_triggered(self):
        monitor = SpyderMemoryMonitor()
        self._add_snapshot(monitor)
        result = monitor.get_current_stats()
        assert "total_gc_triggered" in result


class TestSpyderMemoryMonitorAlerts:
    """Tests for alert management."""

    def test_get_recent_alerts_empty(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.get_recent_alerts()
        assert result == []

    def _add_alert(self, monitor, level="warning"):
        alert = MemoryAlert(
            level=level,
            message=f"Test {level}",
            memory_usage=1_500_000_000,
            recommended_action="Monitor",
            timestamp=datetime.now(),
        )
        monitor.alerts.append(alert)

    def test_get_recent_alerts_with_alerts(self):
        monitor = SpyderMemoryMonitor()
        self._add_alert(monitor, "warning")
        self._add_alert(monitor, "critical")
        result = monitor.get_recent_alerts()
        assert len(result) == 2

    def test_alert_dict_has_level(self):
        monitor = SpyderMemoryMonitor()
        self._add_alert(monitor, "warning")
        alerts = monitor.get_recent_alerts()
        assert alerts[0]["level"] == "warning"

    def test_alert_dict_has_message(self):
        monitor = SpyderMemoryMonitor()
        self._add_alert(monitor, "critical")
        alerts = monitor.get_recent_alerts()
        assert "message" in alerts[0]

    def test_alert_dict_has_timestamp(self):
        monitor = SpyderMemoryMonitor()
        self._add_alert(monitor)
        alerts = monitor.get_recent_alerts()
        assert "timestamp" in alerts[0]

    def test_limit_parameter(self):
        monitor = SpyderMemoryMonitor()
        for _ in range(5):
            self._add_alert(monitor)
        result = monitor.get_recent_alerts(limit=3)
        assert len(result) == 3

    def test_check_memory_alerts_warning_threshold(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss=int(MEMORY_WARNING_THRESHOLD + 1),  # Just above warning
            vms=2_000_000_000,
            percent=10.0,
            available=5_000_000_000,
            process_count=5,
            gc_count=1,
        )
        monitor._check_memory_alerts(snapshot)
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0].level == "warning"

    def test_check_memory_alerts_critical_threshold(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss=int(MEMORY_CRITICAL_THRESHOLD + 1),  # Just above critical
            vms=4_000_000_000,
            percent=20.0,
            available=2_000_000_000,
            process_count=5,
            gc_count=1,
        )
        monitor._check_memory_alerts(snapshot)
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0].level == "critical"

    def test_check_memory_alerts_emergency_threshold(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss=int(MEMORY_EMERGENCY_THRESHOLD + 1),  # Just above emergency
            vms=8_000_000_000,
            percent=40.0,
            available=1_000_000_000,
            process_count=5,
            gc_count=1,
        )
        monitor._check_memory_alerts(snapshot)
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0].level == "emergency"

    def test_check_memory_alerts_below_warning_no_alert(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            rss=500_000_000,  # Well below warning
            vms=1_000_000_000,
            percent=5.0,
            available=10_000_000_000,
            process_count=5,
            gc_count=1,
        )
        monitor._check_memory_alerts(snapshot)
        assert len(monitor.alerts) == 0


class TestSpyderMemoryMonitorCallbacks:
    """Tests for callback management."""

    def test_add_alert_callback(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.add_alert_callback(callback)
        assert callback in monitor.alert_callbacks

    def test_add_stats_callback(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.add_stats_callback(callback)
        assert callback in monitor.stats_callbacks

    def test_remove_alert_callback(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.add_alert_callback(callback)
        monitor.remove_callback(callback)
        assert callback not in monitor.alert_callbacks

    def test_remove_stats_callback(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.add_stats_callback(callback)
        monitor.remove_callback(callback)
        assert callback not in monitor.stats_callbacks

    def test_remove_nonexistent_callback_no_error(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.remove_callback(callback)  # Should not raise

    def test_notify_alert_calls_callback(self):
        monitor = SpyderMemoryMonitor()
        callback = Mock()
        monitor.add_alert_callback(callback)
        alert = MemoryAlert(
            level="warning",
            message="Test",
            memory_usage=1_200_000_000,
            recommended_action="Check",
            timestamp=datetime.now(),
        )
        monitor._notify_alert(alert)
        callback.assert_called_once_with(alert)

    def test_multiple_alert_callbacks_all_called(self):
        monitor = SpyderMemoryMonitor()
        cb1 = Mock()
        cb2 = Mock()
        monitor.add_alert_callback(cb1)
        monitor.add_alert_callback(cb2)
        alert = MemoryAlert(
            level="critical",
            message="Multi-callback test",
            memory_usage=2_500_000_000,
            recommended_action="Restart",
            timestamp=datetime.now(),
        )
        monitor._notify_alert(alert)
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestSpyderMemoryMonitorHistory:
    """Tests for memory history management."""

    def test_clear_history_clears_memory_history(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(), rss=500_000_000, vms=1_000_000_000,
            percent=5.0, available=8_000_000_000, process_count=5, gc_count=1
        )
        monitor.memory_history.append(snapshot)
        monitor.clear_history()
        assert len(monitor.memory_history) == 0

    def test_clear_history_clears_alerts(self):
        monitor = SpyderMemoryMonitor()
        alert = MemoryAlert(
            level="warning", message="Test", memory_usage=1_200_000_000,
            recommended_action="Check", timestamp=datetime.now()
        )
        monitor.alerts.append(alert)
        monitor.clear_history()
        assert len(monitor.alerts) == 0

    def test_clear_history_resets_peak_usage(self):
        monitor = SpyderMemoryMonitor()
        monitor.peak_memory_usage = 2_000_000_000
        monitor.main_process = None  # Avoid psutil calls
        monitor.clear_history()
        assert monitor.peak_memory_usage == 0.0

    def test_get_memory_history_csv_empty(self):
        monitor = SpyderMemoryMonitor()
        result = monitor.get_memory_history_csv()
        assert result == ""

    def test_get_memory_history_csv_with_data(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(), rss=500_000_000, vms=1_000_000_000,
            percent=5.0, available=8_000_000_000, process_count=5, gc_count=1
        )
        monitor.memory_history.append(snapshot)
        result = monitor.get_memory_history_csv()
        assert isinstance(result, str)
        assert "timestamp" in result
        assert "rss_gb" in result

    def test_get_memory_history_csv_has_data_row(self):
        monitor = SpyderMemoryMonitor()
        snapshot = MemorySnapshot(
            timestamp=datetime.now(), rss=500_000_000, vms=1_000_000_000,
            percent=5.0, available=8_000_000_000, process_count=5, gc_count=1
        )
        monitor.memory_history.append(snapshot)
        result = monitor.get_memory_history_csv()
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row


class TestSpyderMemoryMonitorLeakDetection:
    """Tests for memory leak detection."""

    def test_detect_memory_leaks_insufficient_data(self):
        monitor = SpyderMemoryMonitor()
        # Less than 20 snapshots
        result = monitor._detect_memory_leaks()
        assert result is False

    def test_detect_memory_leaks_stable_memory(self):
        monitor = SpyderMemoryMonitor()
        # Add 20 snapshots with stable memory
        base_memory = 500_000_000
        for i in range(20):
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss=base_memory,
                vms=1_000_000_000,
                percent=5.0,
                available=8_000_000_000,
                process_count=5,
                gc_count=1,
            )
            monitor.memory_history.append(snapshot)
        monitor.baseline_memory = base_memory
        result = monitor._detect_memory_leaks()
        assert result is False  # Stable → no leak

    def test_detect_memory_leaks_rapidly_increasing_returns_true(self):
        monitor = SpyderMemoryMonitor()
        # Add 20 snapshots with rapidly increasing memory (>50% baseline growth)
        base_memory = 500_000_000
        monitor.baseline_memory = base_memory
        for i in range(20):
            # Memory increases each time → >80% increasing trend
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss=base_memory + (i + 1) * 50_000_000,  # Grows significantly
                vms=2_000_000_000,
                percent=10.0,
                available=8_000_000_000,
                process_count=5,
                gc_count=1,
            )
            monitor.memory_history.append(snapshot)
        result = monitor._detect_memory_leaks()
        # Final RSs is 500M + 20*50M = 1.5G → 200% growth from 500M → "leak"
        assert result is True


class TestMemoryMonitorModuleFunctions:
    """Tests for U23 module-level functions."""

    def test_get_memory_monitor_returns_instance(self):
        monitor = get_memory_monitor()
        assert isinstance(monitor, SpyderMemoryMonitor)

    def test_get_memory_monitor_singleton(self):
        m1 = get_memory_monitor()
        m2 = get_memory_monitor()
        assert m1 is m2

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_start_global_monitoring_returns_bool(self):
        result = start_global_monitoring()
        assert isinstance(result, bool)
        # Use unbound method call to avoid Event/method naming conflict
        SpyderMemoryMonitor.stop_monitoring(get_memory_monitor())

    @pytest.mark.xfail(reason="stop_global_monitoring calls monitor.stop_monitoring() which hits Event/method naming conflict in source")
    def test_stop_global_monitoring_no_error(self):
        # Module function is broken due to self.stop_monitoring = threading.Event()
        # shadowing the stop_monitoring() method in SpyderMemoryMonitor
        stop_global_monitoring()
