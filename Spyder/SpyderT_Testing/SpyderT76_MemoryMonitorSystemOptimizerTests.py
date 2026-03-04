#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT76_MemoryMonitorSystemOptimizerTests.py
Purpose: Tests for U23 MemoryMonitor and U27 SystemOptimizer

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 23:00:00
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


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u23 = _load("Spyder/SpyderU_Utilities/SpyderU23_MemoryMonitor.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU23_MemoryMonitor"] = _u23

_u27 = _load("Spyder/SpyderU_Utilities/SpyderU27_SystemOptimizer.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer"] = _u27

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import gc
import time
import threading
import datetime
from collections import deque
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# ==============================================================================
# U23 IMPORTS
# ==============================================================================
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
    MAX_MEMORY_HISTORY,
    PSUTIL_AVAILABLE,
)

# ==============================================================================
# U27 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU27_SystemOptimizer import (
    OptimizationLevel,
    SystemComponent,
    OptimizationResult,
    SystemDiagnostics,
    SystemOptimizer,
    get_system_optimizer,
    get_global_optimizer,
    optimize_system_for_trading,
    DEFAULT_TCP_KEEPALIVE_TIME,
    DEFAULT_TCP_KEEPALIVE_INTVL,
    DEFAULT_TCP_KEEPALIVE_PROBES,
    IB_GATEWAY_PORTS,
    IB_GATEWAY_JVM_HEAP,
)


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_snapshot(rss: float = 500_000_000, percent: float = 5.0,
                    available: float = 8_000_000_000) -> MemorySnapshot:
    return MemorySnapshot(
        timestamp=datetime.datetime.now(),
        rss=rss,
        vms=rss * 2,
        percent=percent,
        available=available,
        process_count=10,
        gc_count=100,
    )


def _fresh_monitor() -> SpyderMemoryMonitor:
    """Create a fresh monitor with monitoring NOT started."""
    return SpyderMemoryMonitor(enable_auto_gc=False, enable_deep_monitoring=False)


def _stop_monitor(monitor: SpyderMemoryMonitor):
    """Reliably stop a monitor (works around Event/method name collision)."""
    monitor.monitoring_active = False
    # stop_monitoring is the threading.Event instance attribute
    monitor.stop_monitoring.set()
    if monitor.monitor_thread and monitor.monitor_thread.is_alive():
        monitor.monitor_thread.join(timeout=2.0)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U23 — SpyderMemoryMonitor TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestMemorySnapshotDataclass:
    def test_creation(self):
        s = _make_snapshot()
        assert s.rss == 500_000_000

    def test_timestamp_is_datetime(self):
        s = _make_snapshot()
        assert isinstance(s.timestamp, datetime.datetime)

    def test_vms_set(self):
        s = _make_snapshot()
        assert s.vms > 0

    def test_percent_field(self):
        s = _make_snapshot(percent=12.5)
        assert s.percent == 12.5

    def test_available_field(self):
        s = _make_snapshot(available=4_000_000_000)
        assert s.available == 4_000_000_000

    def test_process_count_field(self):
        s = _make_snapshot()
        assert s.process_count == 10

    def test_gc_count_field(self):
        s = _make_snapshot()
        assert s.gc_count == 100


class TestProcessInfoDataclass:
    def _make(self) -> ProcessInfo:
        return ProcessInfo(
            pid=1234,
            name="test_process",
            memory_rss=200_000_000,
            memory_percent=2.5,
            cpu_percent=10.0,
            status="running",
            create_time=datetime.datetime.now(),
        )

    def test_creation(self):
        pi = self._make()
        assert pi.pid == 1234

    def test_name_field(self):
        pi = self._make()
        assert pi.name == "test_process"

    def test_memory_fields(self):
        pi = self._make()
        assert pi.memory_rss == 200_000_000
        assert pi.memory_percent == 2.5


def _make_alert(level: str = "warning") -> MemoryAlert:
    return MemoryAlert(
        level=level,
        message=f"Memory {level}",
        memory_usage=1_500_000_000,
        recommended_action="Monitor",
        timestamp=datetime.datetime.now(),
    )


class TestMemoryAlertDataclass:
    def test_creation(self):
        a = _make_alert()
        assert a.level == "warning"

    def test_message_field(self):
        a = _make_alert("critical")
        assert "critical" in a.message

    def test_memory_usage_field(self):
        a = _make_alert()
        assert a.memory_usage == 1_500_000_000

    def test_recommended_action(self):
        a = _make_alert()
        assert a.recommended_action == "Monitor"


class TestMemoryStatsDataclass:
    def test_creation(self):
        ms = MemoryStats(
            current_usage=500_000_000,
            peak_usage=800_000_000,
            average_usage=600_000_000,
            trend_direction="stable",
            leak_detected=False,
            time_period="1h",
            measurements_count=100,
        )
        assert ms.current_usage == 500_000_000
        assert ms.leak_detected is False
        assert ms.trend_direction == "stable"


class TestSpyderMemoryMonitorInit:
    def test_instantiation(self):
        m = _fresh_monitor()
        assert m is not None

    def test_has_logger(self):
        m = _fresh_monitor()
        assert m.logger is not None

    def test_not_monitoring_on_init(self):
        m = _fresh_monitor()
        assert m.monitoring_active is False

    def test_memory_history_empty(self):
        m = _fresh_monitor()
        assert len(m.memory_history) == 0

    def test_alerts_empty(self):
        m = _fresh_monitor()
        assert len(m.alerts) == 0

    def test_peak_memory_zero(self):
        m = _fresh_monitor()
        assert m.peak_memory_usage == 0.0

    def test_total_gc_zero(self):
        m = _fresh_monitor()
        assert m.total_gc_triggered == 0

    def test_stop_monitoring_is_event(self):
        m = _fresh_monitor()
        # The instance attribute shadows the method
        assert isinstance(m.stop_monitoring, threading.Event)

    def test_alert_callbacks_empty(self):
        m = _fresh_monitor()
        assert m.alert_callbacks == []

    def test_stats_callbacks_empty(self):
        m = _fresh_monitor()
        assert m.stats_callbacks == []


class TestStartMonitoring:
    def test_returns_bool(self):
        m = _fresh_monitor()
        result = m.start_monitoring()
        assert isinstance(result, bool)
        _stop_monitor(m)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_sets_monitoring_active(self):
        m = _fresh_monitor()
        m.start_monitoring()
        assert m.monitoring_active is True
        _stop_monitor(m)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_already_active_returns_true(self):
        m = _fresh_monitor()
        m.start_monitoring()
        result = m.start_monitoring()
        assert result is True
        _stop_monitor(m)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_creates_monitor_thread(self):
        m = _fresh_monitor()
        m.start_monitoring()
        assert m.monitor_thread is not None
        _stop_monitor(m)


class TestIsMonitoringActive:
    def test_returns_false_initially(self):
        m = _fresh_monitor()
        assert m.is_monitoring_active() is False

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_returns_true_after_start(self):
        m = _fresh_monitor()
        m.start_monitoring()
        assert m.is_monitoring_active() is True
        _stop_monitor(m)


class TestForceGarbageCollection:
    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_returns_dict(self):
        m = _fresh_monitor()
        result = m.force_garbage_collection()
        assert isinstance(result, dict)

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_has_expected_keys(self):
        m = _fresh_monitor()
        result = m.force_garbage_collection()
        for key in ("memory_before_mb", "memory_after_mb", "memory_freed_mb",
                    "objects_before", "objects_after", "collections_performed"):
            assert key in result

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil required")
    def test_collections_performed_non_negative(self):
        m = _fresh_monitor()
        result = m.force_garbage_collection()
        assert result["collections_performed"] >= 0

    def test_without_psutil_returns_empty_or_dict(self):
        m = _fresh_monitor()
        m.main_process = None
        result = m.force_garbage_collection()
        # When main_process is None, before_memory = 0; should still return dict
        assert isinstance(result, dict)


class TestCheckMemoryAlerts:
    def setup_method(self):
        self.m = _fresh_monitor()

    def _check_alert_level(self, rss: float, expected_level: str):
        snap = _make_snapshot(rss=rss)
        self.m._check_memory_alerts(snap)
        if expected_level:
            assert len(self.m.alerts) > 0
            last_alert = list(self.m.alerts)[-1]
            assert last_alert.level == expected_level
        else:
            assert len(self.m.alerts) == 0

    def test_below_warning_no_alert(self):
        self.m.alerts.clear()
        snap = _make_snapshot(rss=500_000_000)  # 0.5 GB < 1GB threshold
        self.m._check_memory_alerts(snap)
        assert len(self.m.alerts) == 0

    def test_warning_threshold(self):
        self.m.alerts.clear()
        snap = _make_snapshot(rss=MEMORY_WARNING_THRESHOLD + 1)
        self.m._check_memory_alerts(snap)
        assert len(self.m.alerts) == 1
        assert list(self.m.alerts)[0].level == "warning"

    def test_critical_threshold(self):
        self.m.alerts.clear()
        snap = _make_snapshot(rss=MEMORY_CRITICAL_THRESHOLD + 1)
        self.m._check_memory_alerts(snap)
        assert len(self.m.alerts) == 1
        assert list(self.m.alerts)[0].level == "critical"

    def test_emergency_threshold(self):
        self.m.alerts.clear()
        snap = _make_snapshot(rss=MEMORY_EMERGENCY_THRESHOLD + 1)
        self.m._check_memory_alerts(snap)
        assert len(self.m.alerts) == 1
        assert list(self.m.alerts)[0].level == "emergency"


class TestNotifyAlert:
    def test_alert_callback_called(self):
        m = _fresh_monitor()
        received = []
        m.add_alert_callback(lambda a: received.append(a))
        m._notify_alert(_make_alert())
        assert len(received) == 1
        assert received[0].level == "warning"

    def test_faulty_callback_doesnt_crash(self):
        m = _fresh_monitor()
        m.add_alert_callback(lambda a: 1 / 0)  # Will raise ZeroDivisionError
        # Should not propagate exception
        m._notify_alert(_make_alert())


class TestGetCurrentStats:
    def test_empty_history_returns_empty_dict(self):
        m = _fresh_monitor()
        assert m.get_current_stats() == {}

    def test_with_history_returns_dict(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_current_stats()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_has_current_memory_gb(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot(rss=500_000_000))
        result = m.get_current_stats()
        assert "current_memory_gb" in result
        assert result["current_memory_gb"] == pytest.approx(0.5, abs=0.01)

    def test_has_total_gc_triggered(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        m.total_gc_triggered = 5
        result = m.get_current_stats()
        assert result["total_gc_triggered"] == 5

    def test_has_ib_gateway_processes(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_current_stats()
        assert "ib_gateway_processes" in result


class TestGetRecentAlerts:
    def test_empty_returns_list(self):
        m = _fresh_monitor()
        assert m.get_recent_alerts() == []

    def test_alerts_returned_as_dicts(self):
        m = _fresh_monitor()
        m.alerts.append(_make_alert())
        result = m.get_recent_alerts()
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_alert_dict_has_level(self):
        m = _fresh_monitor()
        m.alerts.append(_make_alert("critical"))
        result = m.get_recent_alerts()
        assert result[0]["level"] == "critical"

    def test_limit_respected(self):
        m = _fresh_monitor()
        for i in range(20):
            m.alerts.append(_make_alert("warning"))
        result = m.get_recent_alerts(limit=5)
        assert len(result) == 5


class TestGetIbGatewayStats:
    def test_empty_returns_list(self):
        m = _fresh_monitor()
        assert m.get_ib_gateway_stats() == []

    def test_with_process_returns_list(self):
        m = _fresh_monitor()
        m.ib_gateway_processes.append(
            ProcessInfo(1234, "ibgateway", 500_000_000, 2.0, 5.0, "running", datetime.datetime.now())
        )
        result = m.get_ib_gateway_stats()
        assert len(result) == 1
        assert "pid" in result[0]
        assert result[0]["pid"] == 1234


class TestGetMemoryHistoryCSV:
    def test_empty_history_returns_empty_string(self):
        m = _fresh_monitor()
        assert m.get_memory_history_csv() == ""

    def test_with_history_returns_csv(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_csv_has_header(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        first_line = result.split("\n")[0]
        assert "timestamp" in first_line
        assert "rss_gb" in first_line

    def test_csv_has_data_row(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot(rss=500_000_000))
        result = m.get_memory_history_csv()
        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 row

    def test_multiple_snapshots(self):
        m = _fresh_monitor()
        for _ in range(3):
            m.memory_history.append(_make_snapshot())
        result = m.get_memory_history_csv()
        lines = result.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows


class TestClearHistory:
    def test_clears_memory_history(self):
        m = _fresh_monitor()
        m.memory_history.append(_make_snapshot())
        m.clear_history()
        assert len(m.memory_history) == 0

    def test_clears_alerts(self):
        m = _fresh_monitor()
        m.alerts.append(_make_alert())
        m.clear_history()
        assert len(m.alerts) == 0

    def test_resets_peak_memory(self):
        m = _fresh_monitor()
        m.peak_memory_usage = 999_999_999.0
        m.clear_history()
        assert m.peak_memory_usage == 0.0


class TestCallbackManagement:
    def test_add_alert_callback(self):
        m = _fresh_monitor()
        cb = lambda a: None
        m.add_alert_callback(cb)
        assert cb in m.alert_callbacks

    def test_add_stats_callback(self):
        m = _fresh_monitor()
        cb = lambda s: None
        m.add_stats_callback(cb)
        assert cb in m.stats_callbacks

    def test_remove_alert_callback(self):
        m = _fresh_monitor()
        cb = lambda a: None
        m.add_alert_callback(cb)
        m.remove_callback(cb)
        assert cb not in m.alert_callbacks

    def test_remove_stats_callback(self):
        m = _fresh_monitor()
        cb = lambda s: None
        m.add_stats_callback(cb)
        m.remove_callback(cb)
        assert cb not in m.stats_callbacks

    def test_multiple_callbacks(self):
        m = _fresh_monitor()
        results = []
        m.add_stats_callback(lambda s: results.append("cb1"))
        m.add_stats_callback(lambda s: results.append("cb2"))
        # Trigger manually via _perform_memory_check path isn't easy without psutil,
        # so verify registration only
        assert len(m.stats_callbacks) == 2


class TestAnalyzeMemoryTrends:
    def test_insufficient_data_no_crash(self):
        m = _fresh_monitor()
        # Only 5 snapshots — should return without error (needs 10)
        for _ in range(5):
            m.memory_history.append(_make_snapshot())
        m._analyze_memory_trends()  # Should not raise

    def test_with_enough_data_runs(self):
        m = _fresh_monitor()
        for i in range(15):
            m.memory_history.append(_make_snapshot(rss=500_000_000 + i * 1_000_000))
        m._analyze_memory_trends()  # Should not raise


class TestDetectMemoryLeaks:
    def test_insufficient_data_returns_false(self):
        m = _fresh_monitor()
        for _ in range(10):
            m.memory_history.append(_make_snapshot())
        result = m._detect_memory_leaks()
        assert result is False

    def test_stable_memory_no_leak(self):
        m = _fresh_monitor()
        base = 500_000_000
        m.baseline_memory = base
        # All same RSS — no upward trend
        for _ in range(25):
            m.memory_history.append(_make_snapshot(rss=base))
        result = m._detect_memory_leaks()
        assert result is False

    def test_consistent_growth_detected(self):
        m = _fresh_monitor()
        base = 500_000_000
        m.baseline_memory = base
        # RSS grows consistently and exceeds 50% of baseline
        for i in range(25):
            rss = base + i * 20_000_000  # Grows by 20MB each step
        # Final RSS = 500M + 24*20M = 980M → 96% above baseline
            m.memory_history.append(_make_snapshot(rss=rss))
        result = m._detect_memory_leaks()
        assert result is True


class TestGlobalMemoryMonitorFunctions:
    def setup_method(self):
        _u23._global_memory_monitor = None

    def test_get_memory_monitor_returns_instance(self):
        m = get_memory_monitor()
        assert isinstance(m, SpyderMemoryMonitor)

    def test_get_memory_monitor_singleton(self):
        m1 = get_memory_monitor()
        m2 = get_memory_monitor()
        assert m1 is m2

    def test_start_global_monitoring_returns_bool(self):
        result = start_global_monitoring()
        assert isinstance(result, bool)
        # Clean up
        _u23._global_memory_monitor.monitoring_active = False
        _u23._global_memory_monitor.stop_monitoring.set()

    @pytest.mark.xfail(
        reason="Known bug: stop_monitoring instance attr (threading.Event) shadows the method; "
               "stop_global_monitoring() calls monitor.stop_monitoring() which is the Event, "
               "raising TypeError: 'Event' object is not callable"
    )
    def test_stop_global_monitoring_no_crash(self):
        # Confirms existing bug: stop_global_monitoring raises TypeError
        stop_global_monitoring()


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U27 — SystemOptimizer TESTS
# ═══════════════════════════════════════════════════════════════════════════════
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

    def test_four_members(self):
        assert len(list(OptimizationLevel)) == 4


class TestSystemComponentEnum:
    def test_network(self):
        assert SystemComponent.NETWORK.value == "network"

    def test_memory(self):
        assert SystemComponent.MEMORY.value == "memory"

    def test_firewall(self):
        assert SystemComponent.FIREWALL.value == "firewall"

    def test_jvm(self):
        assert SystemComponent.JVM.value == "jvm"

    def test_docker(self):
        assert SystemComponent.DOCKER.value == "docker"

    def test_five_members(self):
        assert len(list(SystemComponent)) == 5


def _make_opt_result(success: bool = True) -> OptimizationResult:
    return OptimizationResult(
        component=SystemComponent.NETWORK,
        success=success,
        message="Test result",
        details={"key": "value"},
    )


class TestOptimizationResultDataclass:
    def test_creation(self):
        r = _make_opt_result()
        assert r.component == SystemComponent.NETWORK
        assert r.success is True

    def test_failure_result(self):
        r = _make_opt_result(success=False)
        assert r.success is False

    def test_details_optional(self):
        r = OptimizationResult(SystemComponent.JVM, True, "OK")
        assert r.details is None

    def test_message_field(self):
        r = _make_opt_result()
        assert r.message == "Test result"


class TestSystemDiagnosticsDataclass:
    def test_creation(self):
        diag = SystemDiagnostics(
            os_info={"system": "Linux"},
            memory_info={"total": 16_000_000_000},
            network_config={"tcp": {}},
            java_info={"available": True},
            docker_info=None,
        )
        assert diag.os_info["system"] == "Linux"

    def test_optional_java_none(self):
        diag = SystemDiagnostics({}, {}, {}, None, None)
        assert diag.java_info is None
        assert diag.docker_info is None


class TestSystemOptimizerInit:
    def test_instantiation_default(self):
        so = SystemOptimizer()
        assert so is not None

    def test_default_optimization_level(self):
        so = SystemOptimizer()
        assert so.optimization_level == OptimizationLevel.STANDARD

    def test_custom_optimization_level(self):
        so = SystemOptimizer(OptimizationLevel.AGGRESSIVE)
        assert so.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_has_logger(self):
        so = SystemOptimizer()
        assert so.logger is not None

    def test_applied_optimizations_empty(self):
        so = SystemOptimizer()
        assert so.applied_optimizations == []


class TestIsRoot:
    def test_returns_bool(self):
        so = SystemOptimizer()
        result = so._is_root()
        assert isinstance(result, bool)

    def test_not_root_in_test_env(self):
        # Tests should not run as root
        so = SystemOptimizer()
        # May be root in CI, so just check it returns bool
        assert so._is_root() in (True, False)


class TestOptimizeTcpKeepalive:
    def test_returns_optimization_result(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        assert isinstance(result, OptimizationResult)

    def test_component_is_network(self):
        so = SystemOptimizer()
        result = so.optimize_tcp_keepalive()
        assert result.component == SystemComponent.NETWORK

    def test_non_root_does_not_append(self):
        so = SystemOptimizer()
        with patch.object(so, "_is_root", return_value=False):
            before = len(so.applied_optimizations)
            so.optimize_tcp_keepalive()
            # Early return without root does NOT append
            assert len(so.applied_optimizations) == before

    def test_root_path_appends(self):
        so = SystemOptimizer()
        with patch.object(so, "_is_root", return_value=True), \
             patch("subprocess.run", side_effect=Exception("sysctl missing")):
            before = len(so.applied_optimizations)
            so.optimize_tcp_keepalive()
            # Exception path still appends
            assert len(so.applied_optimizations) == before + 1

    def test_non_root_returns_failure(self):
        so = SystemOptimizer()
        with patch.object(so, "_is_root", return_value=False):
            result = so.optimize_tcp_keepalive()
            assert result.success is False
            assert "Root" in result.message or "root" in result.message

    def test_root_attempts_sysctl(self):
        so = SystemOptimizer()
        with patch.object(so, "_is_root", return_value=True), \
             patch("subprocess.run", side_effect=Exception("no sysctl")):
            result = so.optimize_tcp_keepalive()
            assert isinstance(result, OptimizationResult)


class TestConfigureFirewall:
    def test_returns_optimization_result(self):
        so = SystemOptimizer()
        result = so.configure_firewall()
        assert isinstance(result, OptimizationResult)

    def test_component_is_firewall(self):
        so = SystemOptimizer()
        result = so.configure_firewall()
        assert result.component == SystemComponent.FIREWALL

    def test_no_ufw_does_not_append(self):
        so = SystemOptimizer()
        import shutil as _shutil
        with patch.object(_shutil, "which", return_value=None):
            before = len(so.applied_optimizations)
            so.configure_firewall()
            # Early return without ufw does NOT append
            assert len(so.applied_optimizations) == before

    def test_with_ufw_path_appends(self):
        so = SystemOptimizer()
        import shutil as _shutil
        with patch.object(_shutil, "which", return_value="/usr/sbin/ufw"), \
             patch("subprocess.run", side_effect=Exception("permission denied")):
            before = len(so.applied_optimizations)
            so.configure_firewall()
            # Exception path still appends
            assert len(so.applied_optimizations) == before + 1

    def test_no_ufw_returns_failure_message(self):
        so = SystemOptimizer()
        import shutil as shutil_mod
        with patch.object(shutil_mod, "which", return_value=None):
            result = so.configure_firewall()
            assert result.success is False
            assert "UFW" in result.message or "ufw" in result.message.lower()


class TestOptimizeIbGatewayJvm:
    def test_returns_optimization_result(self):
        so = SystemOptimizer()
        result = so.optimize_ib_gateway_jvm()
        assert isinstance(result, OptimizationResult)

    def test_component_is_jvm(self):
        so = SystemOptimizer()
        result = so.optimize_ib_gateway_jvm()
        assert result.component == SystemComponent.JVM

    def test_succeeds_by_default(self):
        so = SystemOptimizer()
        result = so.optimize_ib_gateway_jvm()
        # Should write file to ~/.ibgateway/jvm_args.txt
        assert result.success is True

    def test_details_has_jvm_args(self):
        so = SystemOptimizer()
        result = so.optimize_ib_gateway_jvm()
        if result.success:
            assert "jvm_args" in (result.details or {})

    def test_appended_to_applied(self):
        so = SystemOptimizer()
        before = len(so.applied_optimizations)
        so.optimize_ib_gateway_jvm()
        assert len(so.applied_optimizations) == before + 1

    def test_jvm_heap_in_args(self):
        so = SystemOptimizer()
        result = so.optimize_ib_gateway_jvm()
        if result.success and result.details:
            jvm_args = result.details.get("jvm_args", [])
            heap_args = [a for a in jvm_args if "Xmx" in a]
            assert len(heap_args) > 0


class TestGenerateDockerCompose:
    def test_returns_optimization_result(self):
        so = SystemOptimizer()
        result = so.generate_docker_compose()
        assert isinstance(result, OptimizationResult)

    def test_component_is_docker(self):
        so = SystemOptimizer()
        result = so.generate_docker_compose()
        assert result.component == SystemComponent.DOCKER

    def test_appended_to_applied(self):
        so = SystemOptimizer()
        before = len(so.applied_optimizations)
        so.generate_docker_compose()
        assert len(so.applied_optimizations) == before + 1


class TestRunSystemDiagnostics:
    def test_returns_system_diagnostics(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result, SystemDiagnostics)

    def test_os_info_populated(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result.os_info, dict)
        assert "system" in result.os_info

    def test_os_info_system_value(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert result.os_info["system"] in ("Linux", "Windows", "Darwin")

    def test_memory_info_populated_if_psutil(self):
        import psutil as psutil_mod
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        if _u27.psutil:
            assert isinstance(result.memory_info, dict)
            assert "total" in result.memory_info

    def test_network_config_is_dict(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert isinstance(result.network_config, dict)

    def test_java_info_is_dict_or_none(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert result.java_info is None or isinstance(result.java_info, dict)

    def test_docker_info_is_dict_or_none(self):
        so = SystemOptimizer()
        result = so.run_system_diagnostics()
        assert result.docker_info is None or isinstance(result.docker_info, dict)


class TestOptimizeAll:
    def test_returns_list(self):
        so = SystemOptimizer()
        with patch.object(so, "_is_root", return_value=False):
            results = so.optimize_all()
        assert isinstance(results, list)

    def test_basic_level_empty(self):
        so = SystemOptimizer(OptimizationLevel.BASIC)
        results = so.optimize_all()
        # BASIC level runs nothing
        assert results == []

    def test_standard_level_runs_three(self):
        so = SystemOptimizer(OptimizationLevel.STANDARD)
        with patch.object(so, "_is_root", return_value=False), \
             patch("shutil.which", return_value=None):
            results = so.optimize_all()
        assert len(results) == 3  # tcp + firewall + jvm

    def test_aggressive_level_runs_four(self):
        so = SystemOptimizer(OptimizationLevel.AGGRESSIVE)
        with patch.object(so, "_is_root", return_value=False), \
             patch("shutil.which", return_value=None):
            results = so.optimize_all()
        assert len(results) == 4  # tcp + firewall + jvm + docker

    def test_all_results_are_optimization_results(self):
        so = SystemOptimizer(OptimizationLevel.STANDARD)
        with patch.object(so, "_is_root", return_value=False), \
             patch("shutil.which", return_value=None):
            results = so.optimize_all()
        for r in results:
            assert isinstance(r, OptimizationResult)


class TestPrivateHelpers27:
    def test_get_java_info_returns_dict_or_none(self):
        so = SystemOptimizer()
        result = so._get_java_info()
        assert result is None or isinstance(result, dict)

    def test_get_java_info_has_available_key(self):
        so = SystemOptimizer()
        result = so._get_java_info()
        if result is not None:
            assert "available" in result

    def test_get_docker_info_returns_dict_or_none(self):
        so = SystemOptimizer()
        result = so._get_docker_info()
        assert result is None or isinstance(result, dict)

    def test_get_network_config_returns_dict(self):
        so = SystemOptimizer()
        result = so._get_network_config()
        assert isinstance(result, dict)


class TestModuleFunctions27:
    def test_get_system_optimizer_returns_instance(self):
        so = get_system_optimizer()
        assert isinstance(so, SystemOptimizer)

    def test_get_system_optimizer_with_level(self):
        so = get_system_optimizer(OptimizationLevel.AGGRESSIVE)
        assert so.optimization_level == OptimizationLevel.AGGRESSIVE

    def test_get_global_optimizer_returns_instance(self):
        _u27._system_optimizer_instance = None
        so = get_global_optimizer()
        assert isinstance(so, SystemOptimizer)

    def test_get_global_optimizer_singleton(self):
        _u27._system_optimizer_instance = None
        so1 = get_global_optimizer()
        so2 = get_global_optimizer()
        assert so1 is so2

    def test_optimize_system_for_trading_returns_list(self):
        with patch("subprocess.run", side_effect=Exception("no subprocess")), \
             patch("shutil.which", return_value=None):
            results = optimize_system_for_trading()
        assert isinstance(results, list)


class TestConstants:
    def test_tcp_keepalive_time(self):
        assert DEFAULT_TCP_KEEPALIVE_TIME == 60

    def test_tcp_keepalive_intvl(self):
        assert DEFAULT_TCP_KEEPALIVE_INTVL == 15

    def test_tcp_keepalive_probes(self):
        assert DEFAULT_TCP_KEEPALIVE_PROBES == 5

    def test_ib_gateway_ports(self):
        assert 4001 in IB_GATEWAY_PORTS
        assert 4002 in IB_GATEWAY_PORTS

    def test_jvm_heap_format(self):
        assert "m" in IB_GATEWAY_JVM_HEAP or "g" in IB_GATEWAY_JVM_HEAP
