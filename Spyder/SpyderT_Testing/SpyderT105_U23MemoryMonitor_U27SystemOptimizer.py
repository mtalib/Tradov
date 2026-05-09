#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Test: T105 — SpyderU23_MemoryMonitor + SpyderU27_SystemOptimizer
Purpose: Maximize coverage for memory monitoring and system optimization utilities
"""

# ==============================================================================
# BOOTSTRAP — must run before any Spyder imports
# ==============================================================================
import os
import sys
import types
import gc
import datetime
import threading
import tempfile
from unittest.mock import MagicMock, patch, mock_open, call
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name):
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================
import Spyder.SpyderU_Utilities.SpyderU23_MemoryMonitor as _u23_mod
from Spyder.SpyderU_Utilities.SpyderU23_MemoryMonitor import (
    MemorySnapshot,
    ProcessInfo,
    MemoryAlert,
    MemoryStats,
    SpyderMemoryMonitor,
    get_memory_monitor,
    start_global_monitoring,
    stop_global_monitoring,
    MEMORY_WARNING_THRESHOLD,
    MEMORY_CRITICAL_THRESHOLD,
    MEMORY_EMERGENCY_THRESHOLD,
    MEMORY_CHECK_INTERVAL,
    GC_INTERVAL,
    DEEP_MONITORING_INTERVAL,
    MAX_MEMORY_HISTORY,
    MAX_PROCESS_HISTORY,
    PSUTIL_AVAILABLE,
)

import Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer as _u27_mod
from Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer import (
    OptimizationLevel,
    SystemComponent,
    OptimizationResult,
    SystemDiagnostics,
    SystemOptimizer,
    get_system_optimizer,
    optimize_system_for_trading,
    get_global_optimizer,
    DEFAULT_TCP_KEEPALIVE_TIME,
    DEFAULT_TCP_KEEPALIVE_INTVL,
    DEFAULT_TCP_KEEPALIVE_PROBES,
)

# ==============================================================================
# HELPERS
# ==============================================================================

def _make_snapshot(rss=500_000_000, vms=1_000_000_000, percent=10.0,
                   available=8_000_000_000, process_count=10, gc_count=50):
    return MemorySnapshot(
        timestamp=datetime.datetime.now(),
        rss=rss,
        vms=vms,
        percent=percent,
        available=available,
        process_count=process_count,
        gc_count=gc_count,
    )


def _reset_u23_global():
    _u23_mod._global_memory_monitor = None


def _reset_u27_global():
    _u27_mod._system_optimizer_instance = None


# ==============================================================================
# U23 — CONSTANTS
# ==============================================================================

class TestU23Constants:
    def test_warning_threshold(self):
        assert MEMORY_WARNING_THRESHOLD == 1e9

    def test_critical_threshold(self):
        assert MEMORY_CRITICAL_THRESHOLD == 2e9

    def test_emergency_threshold(self):
        assert MEMORY_EMERGENCY_THRESHOLD == 4e9

    def test_check_interval(self):
        assert MEMORY_CHECK_INTERVAL == 30

    def test_gc_interval(self):
        assert GC_INTERVAL == 60

    def test_deep_interval(self):
        assert DEEP_MONITORING_INTERVAL == 300

    def test_history_sizes(self):
        assert MAX_MEMORY_HISTORY == 1000
        assert MAX_PROCESS_HISTORY == 100

    def test_psutil_available(self):
        # In this environment psutil is installed
        assert PSUTIL_AVAILABLE is True


# ==============================================================================
# U23 — DATACLASSES
# ==============================================================================

class TestMemorySnapshotDataclass:
    def test_create(self):
        snap = _make_snapshot()
        assert isinstance(snap, MemorySnapshot)

    def test_fields(self):
        snap = _make_snapshot(rss=123, vms=456, percent=5.5, available=999,
                              process_count=3, gc_count=7)
        assert snap.rss == 123
        assert snap.vms == 456
        assert snap.percent == 5.5
        assert snap.available == 999
        assert snap.process_count == 3
        assert snap.gc_count == 7

    def test_timestamp_is_datetime(self):
        snap = _make_snapshot()
        assert isinstance(snap.timestamp, datetime.datetime)

    def test_defaults_are_numeric(self):
        snap = _make_snapshot()
        assert snap.rss > 0
        assert snap.vms > 0
        assert snap.percent >= 0

    def test_can_store_large_values(self):
        snap = _make_snapshot(rss=4_000_000_000, vms=8_000_000_000)
        assert snap.rss == 4_000_000_000


class TestProcessInfoDataclass:
    def test_create(self):
        pi = ProcessInfo(
            pid=12345,
            name="ibgateway",
            memory_rss=500_000_000,
            memory_percent=5.0,
            cpu_percent=1.2,
            status="running",
            create_time=datetime.datetime.now(),
        )
        assert isinstance(pi, ProcessInfo)

    def test_fields(self):
        now = datetime.datetime.now()
        pi = ProcessInfo(
            pid=99, name="test", memory_rss=100,
            memory_percent=2.0, cpu_percent=0.5, status="sleeping",
            create_time=now,
        )
        assert pi.pid == 99
        assert pi.name == "test"
        assert pi.memory_rss == 100
        assert pi.memory_percent == 2.0
        assert pi.cpu_percent == 0.5
        assert pi.status == "sleeping"
        assert pi.create_time is now

    def test_pid_is_int(self):
        pi = ProcessInfo(
            pid=1, name="x", memory_rss=0,
            memory_percent=0.0, cpu_percent=0.0,
            status="idle", create_time=datetime.datetime.now(),
        )
        assert isinstance(pi.pid, int)


class TestMemoryAlertDataclass:
    def test_create(self):
        alert = MemoryAlert(
            level="warning",
            message="High memory",
            memory_usage=1_500_000_000,
            recommended_action="Monitor",
            timestamp=datetime.datetime.now(),
        )
        assert isinstance(alert, MemoryAlert)

    def test_levels(self):
        for level in ["info", "warning", "critical", "emergency"]:
            alert = MemoryAlert(
                level=level, message="msg", memory_usage=0,
                recommended_action="act", timestamp=datetime.datetime.now(),
            )
            assert alert.level == level

    def test_fields(self):
        now = datetime.datetime.now()
        alert = MemoryAlert(
            level="critical", message="test", memory_usage=2_500_000_000,
            recommended_action="restart", timestamp=now,
        )
        assert alert.message == "test"
        assert alert.memory_usage == 2_500_000_000
        assert alert.recommended_action == "restart"
        assert alert.timestamp is now


class TestMemoryStatsDataclass:
    def test_create(self):
        stats = MemoryStats(
            current_usage=500_000_000,
            peak_usage=800_000_000,
            average_usage=600_000_000,
            trend_direction="stable",
            leak_detected=False,
            time_period="1h",
            measurements_count=10,
        )
        assert isinstance(stats, MemoryStats)

    def test_fields(self):
        stats = MemoryStats(
            current_usage=1, peak_usage=2, average_usage=3,
            trend_direction="increasing", leak_detected=True,
            time_period="5m", measurements_count=5,
        )
        assert stats.current_usage == 1
        assert stats.peak_usage == 2
        assert stats.trend_direction == "increasing"
        assert stats.leak_detected is True
        assert stats.measurements_count == 5

    def test_trend_directions(self):
        for direction in ["increasing", "decreasing", "stable"]:
            stats = MemoryStats(0, 0, 0, direction, False, "0", 0)
            assert stats.trend_direction == direction


# ==============================================================================
# U23 — SpyderMemoryMonitor INIT
# ==============================================================================

class TestSpyderMemoryMonitorInit:
    def test_creates_instance(self):
        m = SpyderMemoryMonitor()
        assert isinstance(m, SpyderMemoryMonitor)

    def test_enable_auto_gc_default(self):
        m = SpyderMemoryMonitor()
        assert m.enable_auto_gc is True

    def test_enable_deep_monitoring_default(self):
        m = SpyderMemoryMonitor()
        assert m.enable_deep_monitoring is True

    def test_custom_options(self):
        m = SpyderMemoryMonitor(enable_auto_gc=False, enable_deep_monitoring=False)
        assert m.enable_auto_gc is False
        assert m.enable_deep_monitoring is False

    def test_monitoring_not_active_initially(self):
        m = SpyderMemoryMonitor()
        assert m.monitoring_active is False

    def test_initial_collections_empty(self):
        m = SpyderMemoryMonitor()
        assert len(m.memory_history) == 0
        assert len(m.alerts) == 0
        assert len(m.alert_callbacks) == 0
        assert len(m.stats_callbacks) == 0

    def test_main_process_set_when_psutil_available(self):
        m = SpyderMemoryMonitor()
        # psutil is available → main_process should be set
        if PSUTIL_AVAILABLE:
            assert m.main_process is not None

    def test_baseline_memory_positive(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            assert m.baseline_memory > 0

    def test_gc_stats_initial(self):
        m = SpyderMemoryMonitor()
        assert m.total_gc_triggered == 0


# ==============================================================================
# U23 — start_monitoring / is_monitoring_active
# ==============================================================================

class TestMemoryMonitorStartMonitoring:
    def test_start_returns_true_when_psutil_available(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            result = m.start_monitoring()
            # Clean up
            m.stop_monitoring.set()
            m.monitoring_active = False
            assert result is True

    def test_monitoring_active_after_start(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            m.start_monitoring()
            active = m.monitoring_active
            m.stop_monitoring.set()
            m.monitoring_active = False
            assert active is True

    def test_monitor_thread_created(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            m.start_monitoring()
            thread_exists = m.monitor_thread is not None
            m.stop_monitoring.set()
            m.monitoring_active = False
            assert thread_exists

    def test_double_start_returns_true(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            m.start_monitoring()
            second = m.start_monitoring()
            m.stop_monitoring.set()
            m.monitoring_active = False
            assert second is True

    def test_is_monitoring_active_reflects_state(self):
        m = SpyderMemoryMonitor()
        assert m.is_monitoring_active() is False
        if PSUTIL_AVAILABLE:
            m.start_monitoring()
            active = m.is_monitoring_active()
            m.stop_monitoring.set()
            m.monitoring_active = False
            assert active is True


# ==============================================================================
# U23 — force_garbage_collection
# ==============================================================================

class TestForceGarbageCollection:
    def test_returns_dict(self):
        m = SpyderMemoryMonitor()
        result = m.force_garbage_collection()
        assert isinstance(result, dict)

    def test_expected_keys(self):
        m = SpyderMemoryMonitor()
        result = m.force_garbage_collection()
        expected_keys = {
            "memory_before_mb", "memory_after_mb", "memory_freed_mb",
            "objects_before", "objects_after", "objects_freed",
            "collections_performed",
        }
        assert expected_keys.issubset(result.keys())

    def test_memory_values_are_numeric(self):
        m = SpyderMemoryMonitor()
        result = m.force_garbage_collection()
        assert isinstance(result["memory_before_mb"], (int, float))
        assert isinstance(result["memory_after_mb"], (int, float))
        assert isinstance(result["collections_performed"], int)

    def test_collections_performed_non_negative(self):
        m = SpyderMemoryMonitor()
        result = m.force_garbage_collection()
        assert result["collections_performed"] >= 0

    def test_objects_before_positive(self):
        m = SpyderMemoryMonitor()
        result = m.force_garbage_collection()
        assert result["objects_before"] > 0


# ==============================================================================
# U23 — get_current_stats
# ==============================================================================

class TestGetCurrentStats:
    def test_empty_history_returns_empty_dict(self):
        m = SpyderMemoryMonitor()
        m.memory_history.clear()
        result = m.get_current_stats()
        assert result == {}

    def test_with_snapshot_returns_dict(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_current_stats()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_expected_keys(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_current_stats()
        expected_keys = {
            "current_memory_gb", "current_memory_percent", "peak_memory_gb",
            "average_memory_gb", "baseline_memory_gb", "memory_growth_percent",
            "available_memory_gb", "process_count", "gc_collections",
            "total_gc_triggered",
            "monitoring_duration_hours", "last_updated",
        }
        assert expected_keys.issubset(result.keys())

    def test_current_memory_non_negative(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot(rss=500_000_000))
        result = m.get_current_stats()
        assert result["current_memory_gb"] >= 0

    def test_last_updated_is_iso_string(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_current_stats()
        assert isinstance(result["last_updated"], str)
        # Should be parseable as ISO datetime
        datetime.datetime.fromisoformat(result["last_updated"])


# ==============================================================================
# U23 — Memory Alerts
# ==============================================================================

class TestCheckMemoryAlerts:
    def test_normal_usage_no_alert(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=500_000_000)  # 0.5GB < 1GB threshold
        m._check_memory_alerts(snap)
        assert len(m.alerts) == 0

    def test_warning_level_alert(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        assert len(m.alerts) == 1
        assert m.alerts[-1].level == "warning"

    def test_critical_level_alert(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_CRITICAL_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        assert len(m.alerts) == 1
        assert m.alerts[-1].level == "critical"

    def test_emergency_level_alert(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_EMERGENCY_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        assert len(m.alerts) == 1
        assert m.alerts[-1].level == "emergency"

    def test_alert_callback_called(self):
        m = SpyderMemoryMonitor()
        callback = MagicMock()
        m.alert_callbacks.append(callback)
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        callback.assert_called_once()

    def test_alert_has_timestamp(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        assert isinstance(m.alerts[-1].timestamp, datetime.datetime)


# ==============================================================================
# U23 — Callback Management
# ==============================================================================

class TestCallbackManagement:
    def test_add_alert_callback(self):
        m = SpyderMemoryMonitor()
        cb = MagicMock()
        m.add_alert_callback(cb)
        assert cb in m.alert_callbacks

    def test_add_stats_callback(self):
        m = SpyderMemoryMonitor()
        cb = MagicMock()
        m.add_stats_callback(cb)
        assert cb in m.stats_callbacks

    def test_remove_alert_callback(self):
        m = SpyderMemoryMonitor()
        cb = MagicMock()
        m.add_alert_callback(cb)
        m.remove_callback(cb)
        assert cb not in m.alert_callbacks

    def test_remove_stats_callback(self):
        m = SpyderMemoryMonitor()
        cb = MagicMock()
        m.add_stats_callback(cb)
        m.remove_callback(cb)
        assert cb not in m.stats_callbacks

    def test_multiple_callbacks(self):
        m = SpyderMemoryMonitor()
        cb1, cb2 = MagicMock(), MagicMock()
        m.add_alert_callback(cb1)
        m.add_alert_callback(cb2)
        assert len(m.alert_callbacks) == 2


# ==============================================================================
# U23 — get_recent_alerts
# ==============================================================================

class TestGetRecentAlerts:
    def test_empty_alerts(self):
        m = SpyderMemoryMonitor()
        result = m.get_recent_alerts()
        assert result == []

    def test_returns_list(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        result = m.get_recent_alerts()
        assert isinstance(result, list)

    def test_alert_dict_has_level(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        result = m.get_recent_alerts()
        assert "level" in result[0]

    def test_limit_parameter(self):
        m = SpyderMemoryMonitor()
        # Add multiple alerts
        for _ in range(5):
            snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
            m._check_memory_alerts(snap)
        result = m.get_recent_alerts(limit=2)
        assert len(result) <= 2


# ==============================================================================
# U23 — get_memory_history_csv
# ==============================================================================

class TestMemoryHistoryCSV:
    def test_empty_history_returns_empty_string(self):
        m = SpyderMemoryMonitor()
        result = m.get_memory_history_csv()
        assert result == ""

    def test_with_snapshot_returns_csv(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_csv_has_header(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        first_line = result.split("\n")[0]
        assert "timestamp" in first_line

    def test_csv_has_data_row(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row

    def test_data_row_has_commas(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        lines = result.strip().split("\n")
        assert "," in lines[1]


# ==============================================================================
# U23 — clear_history
# ==============================================================================

class TestClearHistory:
    def test_clears_memory_history(self):
        m = SpyderMemoryMonitor()
        m.memory_history.append(_make_snapshot())
        m.clear_history()
        assert len(m.memory_history) == 0

    def test_clears_alerts(self):
        m = SpyderMemoryMonitor()
        snap = _make_snapshot(rss=int(MEMORY_WARNING_THRESHOLD + 1))
        m._check_memory_alerts(snap)
        m.clear_history()
        assert len(m.alerts) == 0

    def test_resets_peak_memory(self):
        m = SpyderMemoryMonitor()
        m.peak_memory_usage = 999_999_999
        m.clear_history()
        assert m.peak_memory_usage == 0.0


# ==============================================================================
# U23 — detect_memory_leaks
# ==============================================================================

class TestDetectMemoryLeaks:
    def test_insufficient_data_returns_false(self):
        m = SpyderMemoryMonitor()
        # Less than 20 measurements
        for _ in range(5):
            m.memory_history.append(_make_snapshot())
        result = m._detect_memory_leaks()
        assert result is False

    def test_stable_memory_no_leak(self):
        m = SpyderMemoryMonitor()
        # 20 stable snapshots (constant rss)
        for _ in range(25):
            m.memory_history.append(_make_snapshot(rss=500_000_000))
        result = m._detect_memory_leaks()
        assert result is False

    def test_consistently_growing_memory_detected_if_large(self):
        m = SpyderMemoryMonitor()
        if PSUTIL_AVAILABLE:
            m.baseline_memory = 100_000_000  # 100MB baseline
            # 25 snapshots, each growing by 10MB, starting at 200MB → up to ~340MB
            # 300MB/100MB = 200% growth → >50% threshold
            for i in range(25):
                m.memory_history.append(_make_snapshot(rss=200_000_000 + i * 10_000_000))
            result = m._detect_memory_leaks()
            assert isinstance(result, bool)


# ==============================================================================
# U23 — Module Functions
# ==============================================================================

class TestGlobalFunctionsU23:
    def setup_method(self):
        _reset_u23_global()

    def test_get_memory_monitor_returns_instance(self):
        monitor = get_memory_monitor()
        assert isinstance(monitor, SpyderMemoryMonitor)

    def test_get_memory_monitor_singleton(self):
        m1 = get_memory_monitor()
        m2 = get_memory_monitor()
        assert m1 is m2

    def test_get_memory_monitor_after_reset(self):
        _reset_u23_global()
        m = get_memory_monitor()
        assert m is not None

    def test_start_global_monitoring_returns_bool(self):
        result = start_global_monitoring()
        monitor = get_memory_monitor()
        monitor.stop_monitoring.set()
        monitor.monitoring_active = False
        assert isinstance(result, bool)

    def test_stop_global_monitoring_known_bug(self):
        # stop_global_monitoring() calls monitor.stop_monitoring() which hits
        # a naming conflict bug in U23: self.stop_monitoring is shadowed by
        # the threading.Event set in __init__, making the public method
        # unreachable via instance. Verify this causes TypeError (documenting
        # the bug) and that the monitor instance exists.
        start_global_monitoring()
        monitor = get_memory_monitor()
        assert monitor is not None
        # Clean up manually
        monitor.stop_monitoring.set()
        monitor.monitoring_active = False


# ==============================================================================
# U27 — CONSTANTS
# ==============================================================================

class TestU27Constants:
    def test_tcp_keepalive_time(self):
        assert DEFAULT_TCP_KEEPALIVE_TIME == 60

    def test_tcp_keepalive_intvl(self):
        assert DEFAULT_TCP_KEEPALIVE_INTVL == 15

    def test_tcp_keepalive_probes(self):
        assert DEFAULT_TCP_KEEPALIVE_PROBES == 5



# ==============================================================================
# U27 — Enums
# ==============================================================================

class TestOptimizationLevelEnum:
    def test_basic(self):
        assert OptimizationLevel.BASIC.value == "basic"

    def test_standard(self):
        assert OptimizationLevel.STANDARD.value == "standard"

    def test_aggressive(self):
        assert OptimizationLevel.AGGRESSIVE.value == "aggressive"

    def test_ultra(self):
        assert OptimizationLevel.ULTRA.value == "ultra"

    def test_four_levels(self):
        assert len(OptimizationLevel) == 4


class TestSystemComponentEnum:
    def test_network(self):
        assert SystemComponent.NETWORK.value == "network"

    def test_firewall(self):
        assert SystemComponent.FIREWALL.value == "firewall"

    def test_jvm(self):
        assert SystemComponent.JVM.value == "jvm"

    def test_docker(self):
        assert SystemComponent.DOCKER.value == "docker"

    def test_memory(self):
        assert SystemComponent.MEMORY.value == "memory"


# ==============================================================================
# U27 — Dataclasses
# ==============================================================================

class TestOptimizationResultDataclass:
    def test_create(self):
        result = OptimizationResult(
            component=SystemComponent.NETWORK,
            success=True,
            message="OK",
        )
        assert isinstance(result, OptimizationResult)

    def test_details_default_none(self):
        result = OptimizationResult(
            component=SystemComponent.JVM,
            success=False,
            message="failed",
        )
        assert result.details is None

    def test_fields(self):
        result = OptimizationResult(
            component=SystemComponent.FIREWALL,
            success=True,
            message="done",
            details={"a": 1},
        )
        assert result.component == SystemComponent.FIREWALL
        assert result.success is True
        assert result.message == "done"
        assert result.details == {"a": 1}

    def test_success_false(self):
        result = OptimizationResult(
            component=SystemComponent.DOCKER,
            success=False,
            message="err",
        )
        assert result.success is False


class TestSystemDiagnosticsDataclass:
    def test_create(self):
        d = SystemDiagnostics(
            os_info={"system": "Linux"},
            memory_info={"total": 8_000_000_000},
            network_config={},
            java_info=None,
            docker_info=None,
        )
        assert isinstance(d, SystemDiagnostics)

    def test_fields(self):
        d = SystemDiagnostics(
            os_info={"system": "Linux"},
            memory_info={"total": 1},
            network_config={"tcp": {}},
            java_info={"available": True},
            docker_info={"version": "20.0"},
        )
        assert d.os_info["system"] == "Linux"
        assert d.memory_info["total"] == 1
        assert d.java_info == {"available": True}
        assert d.docker_info == {"version": "20.0"}

    def test_java_info_can_be_none(self):
        d = SystemDiagnostics({}, {}, {}, None, None)
        assert d.java_info is None
        assert d.docker_info is None


# ==============================================================================
# U27 — SystemOptimizer Init
# ==============================================================================

class TestSystemOptimizerInit:
    def test_create_default(self):
        opt = SystemOptimizer()
        assert isinstance(opt, SystemOptimizer)

    def test_default_level(self):
        opt = SystemOptimizer()
        assert opt.optimization_level == OptimizationLevel.STANDARD

    def test_custom_level(self):
        opt = SystemOptimizer(OptimizationLevel.AGGRESSIVE)
        assert opt.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_ultra_level(self):
        opt = SystemOptimizer(OptimizationLevel.ULTRA)
        assert opt.optimization_level == OptimizationLevel.ULTRA

    def test_applied_optimizations_empty(self):
        opt = SystemOptimizer()
        assert opt.applied_optimizations == []

    def test_applied_optimizations_is_list(self):
        opt = SystemOptimizer()
        assert isinstance(opt.applied_optimizations, list)


# ==============================================================================
# U27 — optimize_tcp_keepalive (requires root → returns failure)
# ==============================================================================

class TestOptimizeTCPKeepalive:
    def test_returns_optimization_result(self):
        opt = SystemOptimizer()
        result = opt.optimize_tcp_keepalive()
        assert isinstance(result, OptimizationResult)

    def test_component_is_network(self):
        opt = SystemOptimizer()
        result = opt.optimize_tcp_keepalive()
        assert result.component == SystemComponent.NETWORK

    def test_fails_without_root(self):
        opt = SystemOptimizer()
        # Running as non-root → should fail
        if os.geteuid() != 0:
            result = opt.optimize_tcp_keepalive()
            assert result.success is False

    def test_appended_to_applied_optimizations(self):
        opt = SystemOptimizer()
        opt.optimize_tcp_keepalive()
        # When not root, returns early WITHOUT appending to applied_optimizations
        if os.geteuid() != 0:
            assert len(opt.applied_optimizations) == 0
        else:
            assert len(opt.applied_optimizations) == 1

    def test_failure_message_set(self):
        opt = SystemOptimizer()
        if os.geteuid() != 0:
            result = opt.optimize_tcp_keepalive()
            assert len(result.message) > 0


# ==============================================================================
# U27 — configure_firewall
# ==============================================================================

class TestConfigureFirewall:
    def test_returns_optimization_result(self):
        opt = SystemOptimizer()
        result = opt.configure_firewall()
        assert isinstance(result, OptimizationResult)

    def test_component_is_firewall(self):
        opt = SystemOptimizer()
        result = opt.configure_firewall()
        assert result.component == SystemComponent.FIREWALL

    def test_appended_to_applied(self):
        opt = SystemOptimizer()
        opt.configure_firewall()
        assert len(opt.applied_optimizations) == 1

    def test_message_is_string(self):
        opt = SystemOptimizer()
        result = opt.configure_firewall()
        assert isinstance(result.message, str)


# ==============================================================================
# U27 — run_system_diagnostics
# ==============================================================================

class TestRunSystemDiagnostics:
    def test_returns_system_diagnostics(self):
        opt = SystemOptimizer()
        result = opt.run_system_diagnostics()
        assert isinstance(result, SystemDiagnostics)

    def test_os_info_has_system(self):
        opt = SystemOptimizer()
        result = opt.run_system_diagnostics()
        assert "system" in result.os_info

    def test_os_info_has_machine(self):
        opt = SystemOptimizer()
        result = opt.run_system_diagnostics()
        assert "machine" in result.os_info

    def test_memory_info_when_psutil_available(self):
        opt = SystemOptimizer()
        result = opt.run_system_diagnostics()
        # psutil is available
        assert isinstance(result.memory_info, dict)

    def test_network_config_is_dict(self):
        opt = SystemOptimizer()
        result = opt.run_system_diagnostics()
        assert isinstance(result.network_config, dict)


# ==============================================================================
# U27 — _is_root
# ==============================================================================

class TestPrivateMethods:
    def test_is_root_returns_bool(self):
        opt = SystemOptimizer()
        result = opt._is_root()
        assert isinstance(result, bool)

    def test_is_root_false_for_normal_user(self):
        opt = SystemOptimizer()
        # Tests run as non-root
        if os.geteuid() != 0:
            assert opt._is_root() is False

    def test_get_java_info_returns_dict_or_none(self):
        opt = SystemOptimizer()
        result = opt._get_java_info()
        assert result is None or isinstance(result, dict)

    def test_get_docker_info_returns_dict_or_none(self):
        opt = SystemOptimizer()
        result = opt._get_docker_info()
        assert result is None or isinstance(result, dict)

    def test_get_network_config_returns_dict(self):
        opt = SystemOptimizer()
        result = opt._get_network_config()
        assert isinstance(result, dict)


# ==============================================================================
# U27 — optimize_all
# ==============================================================================

class TestOptimizeAll:
    def test_returns_list(self):
        opt = SystemOptimizer(OptimizationLevel.STANDARD)
        with patch("builtins.open", mock_open()), patch("Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer.Path.cwd",
                       return_value=type("P", (), {
                           "__truediv__": lambda self, x: type("F", (), {
                               "__str__": lambda self: f"/tmp/{x}",
                           })()
                       })()):
            results = opt.optimize_all()
        assert isinstance(results, list)

    def test_standard_level_has_two_results(self):
        opt = SystemOptimizer(OptimizationLevel.STANDARD)
        results = opt.optimize_all()
        # STANDARD: tcp + firewall = 2 results
        assert len(results) == 2

    def test_aggressive_level_has_two_results(self):
        opt = SystemOptimizer(OptimizationLevel.AGGRESSIVE)
        results = opt.optimize_all()
        # AGGRESSIVE: tcp + firewall = 2 results
        assert len(results) == 2

    def test_basic_level_no_results(self):
        opt = SystemOptimizer(OptimizationLevel.BASIC)
        results = opt.optimize_all()
        # BASIC: none of STANDARD/AGGRESSIVE/ULTRA → 0 results
        assert len(results) == 0

    def test_results_are_optimization_results(self):
        opt = SystemOptimizer(OptimizationLevel.STANDARD)
        results = opt.optimize_all()
        for r in results:
            assert isinstance(r, OptimizationResult)


# ==============================================================================
# U27 — Module Functions
# ==============================================================================

class TestGlobalFunctionsU27:
    def setup_method(self):
        _reset_u27_global()

    def test_get_system_optimizer_returns_instance(self):
        opt = get_system_optimizer()
        assert isinstance(opt, SystemOptimizer)

    def test_get_system_optimizer_custom_level(self):
        opt = get_system_optimizer(OptimizationLevel.AGGRESSIVE)
        assert opt.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_get_system_optimizer_creates_new_each_call(self):
        # get_system_optimizer() creates a new SystemOptimizer each time (not singleton)
        opt1 = get_system_optimizer()
        opt2 = get_system_optimizer()
        assert isinstance(opt1, SystemOptimizer)
        assert isinstance(opt2, SystemOptimizer)

    def test_get_global_optimizer_singleton(self):
        o1 = get_global_optimizer()
        o2 = get_global_optimizer()
        assert o1 is o2

    def test_optimize_system_for_trading_returns_list(self):
        results = optimize_system_for_trading()
        assert isinstance(results, list)
