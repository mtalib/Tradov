#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT83_ErrorHandlerNetworkUtilsTests.py
Purpose: Comprehensive tests for U02 ErrorHandler and U05 NetworkUtils

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 13:00:00
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

_u05 = _load("Spyder/SpyderU_Utilities/SpyderU05_NetworkUtils.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils"] = _u05

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pytest
from unittest.mock import patch, MagicMock

# ==============================================================================
# U02 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import (
    ErrorCategory,
    ErrorSeverity,
    RecoveryAction,
    ErrorContext,
    RecoveryStrategy,
    SpyderError,
    ConnectionError as SpyderConnectionError,
    DataError,
    ExecutionError,
    RiskError,
    TradingError,
    SpyderErrorHandler,
    get_error_handler,
    reset_error_handler,
)

# ==============================================================================
# U05 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils import (
    ConnectionStatus,
    NetworkType,
    NetworkStats,
    ConnectionTest,
    NetworkUtils,
    get_network_utils,
    DEFAULT_TIMEOUT,
)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U02 — ERROR HANDLER
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU02Enums:
    def test_error_category_values(self):
        assert ErrorCategory.CONNECTION.value == "connection"
        assert ErrorCategory.DATA.value == "data"
        assert ErrorCategory.EXECUTION.value == "execution"
        assert ErrorCategory.RISK.value == "risk"
        assert ErrorCategory.SYSTEM.value == "system"
        assert ErrorCategory.STRATEGY.value == "strategy"
        assert ErrorCategory.UNKNOWN.value == "unknown"

    def test_error_severity_ordering(self):
        assert ErrorSeverity.LOW.value < ErrorSeverity.MEDIUM.value
        assert ErrorSeverity.MEDIUM.value < ErrorSeverity.HIGH.value
        assert ErrorSeverity.HIGH.value < ErrorSeverity.CRITICAL.value

    def test_recovery_action_values(self):
        assert RecoveryAction.NONE.value == "none"
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.RECONNECT.value == "reconnect"
        assert RecoveryAction.EMERGENCY_SHUTDOWN.value == "emergency_shutdown"

    def test_all_recovery_actions_exist(self):
        expected = ["NONE", "RETRY", "RECONNECT", "RESTART_COMPONENT",
                    "DISABLE_FEATURE", "SHUTDOWN_STRATEGY", "EMERGENCY_SHUTDOWN"]
        names = [a.name for a in RecoveryAction]
        for n in expected:
            assert n in names


class TestU02ErrorContext:
    def test_default_creation(self):
        ctx = ErrorContext()
        assert ctx.category == ErrorCategory.UNKNOWN
        assert ctx.severity == ErrorSeverity.LOW
        assert ctx.resolved is False
        assert ctx.recovery_attempts == 0

    def test_custom_creation(self):
        ctx = ErrorContext(
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH,
            error_message="Test error",
            component_name="TestComp",
        )
        assert ctx.category == ErrorCategory.CONNECTION
        assert ctx.severity == ErrorSeverity.HIGH
        assert ctx.error_message == "Test error"

    def test_error_id_auto_generated(self):
        ctx = ErrorContext()
        assert ctx.error_id.startswith("ERR_")
        assert len(ctx.error_id) > 4

    def test_timestamp_set(self):
        ctx = ErrorContext()
        assert ctx.timestamp is not None


class TestU02RecoveryStrategy:
    def test_default_values(self):
        rs = RecoveryStrategy(action=RecoveryAction.RETRY)
        assert rs.action == RecoveryAction.RETRY
        assert rs.max_retries == 3
        assert rs.retry_delay == 1.0
        assert rs.backoff_multiplier == 2.0

    def test_custom_values(self):
        rs = RecoveryStrategy(
            action=RecoveryAction.RECONNECT,
            max_retries=5,
            retry_delay=2.0,
        )
        assert rs.max_retries == 5
        assert rs.retry_delay == 2.0


class TestU02Exceptions:
    def test_spyder_error_base(self):
        err = SpyderError("test error")
        assert str(err) == "test error"
        assert err.category == ErrorCategory.UNKNOWN
        assert err.severity == ErrorSeverity.MEDIUM

    def test_spyder_error_custom_severity(self):
        err = SpyderError("high severity", severity=ErrorSeverity.HIGH)
        assert err.severity == ErrorSeverity.HIGH

    def test_connection_error(self):
        err = SpyderConnectionError("timeout")
        assert err.category == ErrorCategory.CONNECTION
        assert err.severity == ErrorSeverity.HIGH
        assert isinstance(err, SpyderError)
        with pytest.raises(SpyderConnectionError):
            raise err

    def test_data_error(self):
        err = DataError("bad data")
        assert err.category == ErrorCategory.DATA
        assert err.severity == ErrorSeverity.MEDIUM
        assert isinstance(err, SpyderError)

    def test_execution_error(self):
        err = ExecutionError("order failed")
        assert err.category == ErrorCategory.EXECUTION
        assert err.severity == ErrorSeverity.HIGH

    def test_risk_error(self):
        err = RiskError("limit exceeded")
        assert err.category == ErrorCategory.RISK
        assert err.severity == ErrorSeverity.CRITICAL

    def test_trading_error(self):
        err = TradingError("strategy error")
        assert err.category == ErrorCategory.STRATEGY
        assert err.severity == ErrorSeverity.HIGH
        assert isinstance(err, SpyderError)

    def test_exception_inheritance(self):
        for ExcClass in [SpyderConnectionError, DataError, ExecutionError, RiskError, TradingError]:
            assert issubclass(ExcClass, SpyderError)
            assert issubclass(ExcClass, Exception)

    def test_context_kwargs_stored(self):
        err = SpyderError("test", order_id="123", symbol="SPY")
        assert err.context["order_id"] == "123"
        assert err.context["symbol"] == "SPY"


class TestU02SpyderErrorHandler:
    def setup_method(self):
        self.handler = SpyderErrorHandler()

    def test_init(self):
        assert self.handler is not None
        assert len(self.handler.error_history) == 0
        assert self.handler.critical_error_count == 0

    def test_recovery_strategies_initialized(self):
        assert "ConnectionError" in self.handler.recovery_strategies
        assert "DataError" in self.handler.recovery_strategies
        assert "RiskError" in self.handler.recovery_strategies

    def test_set_event_manager(self):
        mock_manager = MagicMock()
        self.handler.set_event_manager(mock_manager)
        assert self.handler.event_manager is mock_manager

    def test_handle_error_string(self):
        ctx = self.handler.handle_error("simple error message", "test_component")
        assert isinstance(ctx, ErrorContext)
        assert ctx.component_name == "test_component"
        assert ctx.error_message == "simple error message"

    def test_handle_error_exception(self):
        err = ValueError("bad value")
        ctx = self.handler.handle_error(err, "validation")
        assert ctx.error_type == "ValueError"
        assert "bad value" in ctx.error_message

    def test_handle_error_with_strategy_name(self):
        ctx = self.handler.handle_error("error", "comp", strategy_name="IronCondor")
        assert ctx.strategy_name == "IronCondor"
        assert "IronCondor" in self.handler.strategy_errors

    def test_handle_error_tracks_history(self):
        self.handler.handle_error("err1", "comp1")
        self.handler.handle_error("err2", "comp2")
        assert len(self.handler.error_history) == 2

    def test_handle_spyder_error_uses_category(self):
        err = SpyderConnectionError("Connection refused")
        ctx = self.handler.handle_error(err, "broker")
        assert ctx.category == ErrorCategory.CONNECTION

    def test_handle_error_with_additional_data(self):
        ctx = self.handler.handle_error("err", "comp", additional_data={"key": "val"})
        assert ctx.additional_data["key"] == "val"

    def test_get_error_rate_zero_initially(self):
        rate = self.handler.get_error_rate()
        assert rate == 0.0

    def test_get_error_rate_after_errors(self):
        self.handler.handle_error("e1", "c1")
        self.handler.handle_error("e2", "c2")
        rate = self.handler.get_error_rate()
        assert rate > 0

    def test_get_error_summary_structure(self):
        self.handler.handle_error("test error", "TestComp")
        summary = self.handler.get_error_summary()
        assert "total_errors" in summary
        assert "critical_errors" in summary
        assert "error_rate" in summary
        assert "error_types" in summary
        assert "recent_errors" in summary
        assert summary["total_errors"] == 1

    def test_get_error_summary_empty(self):
        summary = self.handler.get_error_summary()
        assert summary["total_errors"] == 0
        assert summary["critical_errors"] == 0

    def test_register_error_callback(self):
        callback_called = []
        self.handler.register_error_callback(lambda ctx: callback_called.append(ctx))
        self.handler.handle_error("test", "comp")
        assert len(callback_called) == 1

    def test_register_component(self):
        mock_comp = MagicMock()
        self.handler.register_component("test_comp", mock_comp)
        assert "test_comp" in self.handler.components

    def test_get_strategy_error_report_unknown(self):
        report = self.handler.get_strategy_error_report("NoSuchStrategy")
        assert report["error_count"] == 0
        assert report["errors"] == []

    def test_get_strategy_error_report_with_errors(self):
        self.handler.handle_error("err", "comp", strategy_name="TestStrat")
        report = self.handler.get_strategy_error_report("TestStrat")
        assert report["error_count"] == 1


class TestU02Categorization:
    def setup_method(self):
        self.handler = SpyderErrorHandler()

    def test_categorize_connection_error(self):
        err = Exception("connection timeout failed")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.CONNECTION

    def test_categorize_data_error(self):
        err = Exception("invalid data format")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.DATA

    def test_categorize_execution_error(self):
        err = Exception("order execution failed")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.EXECUTION

    def test_categorize_risk_error(self):
        err = Exception("risk limit exceeded")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.RISK

    def test_categorize_system_error(self):
        err = Exception("system memory error")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.SYSTEM

    def test_categorize_strategy_error(self):
        err = Exception("strategy signal failed")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.STRATEGY

    def test_categorize_unknown_error(self):
        err = Exception("some random error")
        cat = self.handler._categorize_error(err)
        assert cat == ErrorCategory.UNKNOWN

    def test_assess_severity_risk_critical(self):
        err = Exception("test")
        sev = self.handler._assess_severity(err, ErrorCategory.RISK)
        assert sev == ErrorSeverity.CRITICAL

    def test_assess_severity_connection_high(self):
        err = Exception("test")
        sev = self.handler._assess_severity(err, ErrorCategory.CONNECTION)
        assert sev == ErrorSeverity.HIGH

    def test_assess_severity_value_error_medium(self):
        err = ValueError("bad value")
        sev = self.handler._assess_severity(err, ErrorCategory.UNKNOWN)
        assert sev == ErrorSeverity.MEDIUM

    def test_assess_severity_memory_error_critical(self):
        err = MemoryError("out of memory")
        sev = self.handler._assess_severity(err, ErrorCategory.UNKNOWN)
        assert sev == ErrorSeverity.CRITICAL


class TestU02ErrorHandlerDecorator:
    def test_decorator_passes_on_success(self):
        _u02.reset_error_handler()

        class MyComp:
            @SpyderErrorHandler.error_handler("MyComp")
            def do_work(self):
                return 42

        comp = MyComp()
        result = comp.do_work()
        assert result == 42

    def test_decorator_handles_exception(self):
        _u02.reset_error_handler()

        class MyComp:
            @SpyderErrorHandler.error_handler("MyComp")
            def fail_work(self):
                raise ValueError("intentional error")

        comp = MyComp()
        # Should re-raise since error is not resolved
        with pytest.raises(ValueError):
            comp.fail_work()


class TestU02ModuleFunctions:
    def setup_method(self):
        _u02.reset_error_handler()

    def test_get_error_handler_returns_instance(self):
        handler = get_error_handler()
        assert isinstance(handler, SpyderErrorHandler)

    def test_get_error_handler_singleton(self):
        h1 = get_error_handler()
        h2 = get_error_handler()
        assert h1 is h2

    def test_reset_error_handler(self):
        h1 = get_error_handler()
        reset_error_handler()
        h2 = get_error_handler()
        assert h1 is not h2


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U05 — NETWORK UTILS
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU05Enums:
    def test_connection_status_values(self):
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.UNKNOWN.value == "unknown"
        assert ConnectionStatus.SLOW.value == "slow"
        assert ConnectionStatus.UNSTABLE.value == "unstable"

    def test_network_type_values(self):
        assert NetworkType.ETHERNET.value == "ethernet"
        assert NetworkType.WIFI.value == "wifi"
        assert NetworkType.UNKNOWN.value == "unknown"


class TestU05DataStructures:
    def test_network_stats_creation(self):
        import time
        ns = NetworkStats(
            latency_ms=10.5,
            packet_loss=0.0,
            bandwidth_mbps=100.0,
            connection_type=NetworkType.ETHERNET,
            status=ConnectionStatus.CONNECTED,
            timestamp=time.time(),
        )
        assert ns.latency_ms == 10.5
        assert ns.status == ConnectionStatus.CONNECTED

    def test_connection_test_creation(self):
        ct = ConnectionTest(host="8.8.8.8", port=53, success=True, latency_ms=15.0)
        assert ct.host == "8.8.8.8"
        assert ct.success is True
        assert ct.error_message is None

    def test_connection_test_with_error(self):
        ct = ConnectionTest(
            host="localhost", port=9999, success=False, latency_ms=-1.0,
            error_message="Connection refused"
        )
        assert ct.success is False
        assert ct.error_message is not None


class TestU05NetworkUtils:
    def setup_method(self):
        self.net = NetworkUtils()

    def test_init(self):
        assert self.net is not None
        assert isinstance(self.net.stats, NetworkStats)
        assert self.net.stats.status == ConnectionStatus.UNKNOWN

    def test_check_internet_true_when_host_reachable(self):
        with patch.object(self.net, "_test_host_connection", return_value=True):
            result = self.net.check_internet_connection()
            assert result is True

    def test_check_internet_false_when_all_fail(self):
        with patch.object(self.net, "_test_host_connection", return_value=False), \
             patch.object(self.net, "_test_http_connection", return_value=False):
            result = self.net.check_internet_connection()
            assert result is False

    def test_check_internet_falls_back_to_http(self):
        # All socket checks fail but http works
        with patch.object(self.net, "_test_host_connection", return_value=False), \
             patch.object(self.net, "_test_http_connection", return_value=True):
            result = self.net.check_internet_connection()
            assert result is True

    def test_check_internet_handles_exception(self):
        with patch.object(self.net, "_test_host_connection", side_effect=Exception("network error")):
            result = self.net.check_internet_connection()
            assert result is False

    def test_check_ib_connection_unknown_type(self):
        result = self.net.check_ib_connection("UNKNOWN_TYPE")
        assert result is False

    def test_check_ib_connection_mocked_success(self):
        with patch.object(self.net, "_test_host_connection", return_value=True):
            result = self.net.check_ib_connection("GATEWAY")
            assert result is True

    def test_check_ib_connection_mocked_fail(self):
        with patch.object(self.net, "_test_host_connection", return_value=False):
            result = self.net.check_ib_connection("GATEWAY")
            assert result is False

    def test_test_host_connection_success(self):
        import socket
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            result = self.net._test_host_connection("8.8.8.8", 53, 5)
            assert result is True

    def test_test_host_connection_failure(self):
        import socket
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = self.net._test_host_connection("badhost", 9999, 1)
            assert result is False

    def test_test_endpoint_success(self):
        import socket
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            ct = self.net._test_endpoint("8.8.8.8", 53)
            assert isinstance(ct, ConnectionTest)
            assert ct.success is True
            assert ct.host == "8.8.8.8"

    def test_test_endpoint_failure(self):
        import socket
        with patch("socket.create_connection", side_effect=OSError("refused")):
            ct = self.net._test_endpoint("badhost", 9999)
            assert ct.success is False
            assert ct.error_message is not None

    def test_test_dns_resolution_success(self):
        import socket
        with patch("socket.gethostbyname", return_value="142.250.80.46"):
            result = self.net._test_dns_resolution()
            assert result is True

    def test_test_dns_resolution_failure(self):
        import socket
        with patch("socket.gethostbyname", side_effect=socket.gaierror("not found")):
            result = self.net._test_dns_resolution()
            assert result is False

    def test_test_http_connection_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("requests.get", return_value=mock_response):
            result = self.net._test_http_connection()
            assert result is True

    def test_test_http_connection_failure(self):
        import requests as req
        with patch("requests.get", side_effect=req.RequestException("error")):
            result = self.net._test_http_connection()
            assert result is False

    def test_get_network_status_structure(self):
        with patch.object(self.net, "check_internet_connection", return_value=True), \
             patch.object(self.net, "check_ib_connection", return_value=False), \
             patch.object(self.net, "measure_latency", return_value=15.0), \
             patch.object(self.net, "_test_dns_resolution", return_value=True), \
             patch.object(self.net, "_test_http_connection", return_value=True):
            status = self.net.get_network_status()
            assert "internet_connected" in status
            assert "ib_gateway_connected" in status
            assert "latency_ms" in status
            assert status["internet_connected"] is True

    def test_get_network_status_updates_stats(self):
        with patch.object(self.net, "check_internet_connection", return_value=True), \
             patch.object(self.net, "check_ib_connection", return_value=False), \
             patch.object(self.net, "measure_latency", return_value=25.0), \
             patch.object(self.net, "_test_dns_resolution", return_value=True), \
             patch.object(self.net, "_test_http_connection", return_value=True):
            self.net.get_network_status()
            assert self.net.stats.latency_ms == 25.0
            assert self.net.stats.status == ConnectionStatus.CONNECTED

    def test_get_network_status_disconnected_updates_stats(self):
        with patch.object(self.net, "check_internet_connection", return_value=False), \
             patch.object(self.net, "check_ib_connection", return_value=False), \
             patch.object(self.net, "measure_latency", return_value=-1.0), \
             patch.object(self.net, "_test_dns_resolution", return_value=False), \
             patch.object(self.net, "_test_http_connection", return_value=False):
            self.net.get_network_status()
            assert self.net.stats.status == ConnectionStatus.DISCONNECTED


class TestU05ModuleFunctions:
    def setup_method(self):
        _u05._network_utils_instance = None

    def test_get_network_utils_returns_instance(self):
        inst = get_network_utils()
        assert isinstance(inst, NetworkUtils)

    def test_get_network_utils_singleton(self):
        inst1 = get_network_utils()
        inst2 = get_network_utils()
        assert inst1 is inst2

    def test_default_timeout_value(self):
        assert DEFAULT_TIMEOUT == 10
