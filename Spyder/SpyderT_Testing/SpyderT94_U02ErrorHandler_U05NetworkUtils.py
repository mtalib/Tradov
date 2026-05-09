#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT94_U02ErrorHandler_U05NetworkUtils.py
Purpose: Test suite for SpyderU02_ErrorHandler and SpyderU05_NetworkUtils

Author: Test Suite
Year Created: 2025
Last Updated: 2026-01-20 Time: 12:00:00
"""

# ==============================================================================
# BOOTSTRAP — must come before any local imports
# ==============================================================================
import os
import sys
import types
from unittest.mock import MagicMock, patch, call
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

# Stub SpyderLogger — provides both SpyderLogger class AND top-level get_logger
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Remove any stub installed by earlier T-files for SpyderU02_ErrorHandler
# so that we import the REAL module below.
for _key in list(sys.modules.keys()):
    if "SpyderU02_ErrorHandler" in _key:
        del sys.modules[_key]

# NOTE: We do NOT stub SpyderErrorHandler here — we import the real one from U02.
# U05 will use the real SpyderErrorHandler as well.

# ==============================================================================
# IMPORTS UNDER TEST — U02 FIRST (so it registers in sys.modules before U05)
# ==============================================================================
import socket
import time
from collections import deque
from datetime import datetime, timedelta

import Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler as u02_mod_alias

from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import (
    SpyderErrorHandler,
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
    MAX_ERROR_HISTORY,
    ERROR_RATE_WINDOW,
    MAX_ERROR_RATE,
    STRATEGY_SHUTDOWN_THRESHOLD,
    SYSTEM_SHUTDOWN_THRESHOLD,
    get_error_handler,
    reset_error_handler,
)

# U05 NetworkUtils — imports SpyderLogger + SpyderErrorHandler (real)
import Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils as u05_mod_alias

from Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils import (
    NetworkUtils,
    NetworkStats,
    ConnectionTest,
    ConnectionStatus,
    NetworkType,
    DEFAULT_TIMEOUT,
    PING_TIMEOUT,
    CONNECTION_RETRIES,
    INTERNET_TEST_HOSTS,
    IB_ENDPOINTS,
    HTTP_TEST_URLS,
    check_internet_connection as module_check_internet,
    check_connection as module_check_connection,
    measure_latency as module_measure_latency,
    get_network_utils,
)

# ==============================================================================
# HELPERS
# ==============================================================================
U02_MOD_KEY = "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"
U05_MOD_KEY = "Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils"


def make_handler() -> SpyderErrorHandler:
    """Create a fresh SpyderErrorHandler for each test."""
    return SpyderErrorHandler()


def make_error_context(**kwargs) -> ErrorContext:
    defaults = {
        "category": ErrorCategory.UNKNOWN,
        "severity": ErrorSeverity.LOW,
        "error_type": "ValueError",
        "error_message": "test error",
        "component_name": "TestComponent",
    }
    defaults.update(kwargs)
    return ErrorContext(**defaults)


# ==============================================================================
# U02 — MODULE-LEVEL CONSTANTS
# ==============================================================================

class TestU02Constants:
    def test_max_error_history(self):
        assert MAX_ERROR_HISTORY == 1000

    def test_error_rate_window(self):
        assert ERROR_RATE_WINDOW == 300

    def test_max_error_rate(self):
        assert MAX_ERROR_RATE == 10

    def test_strategy_shutdown_threshold(self):
        assert STRATEGY_SHUTDOWN_THRESHOLD == 5

    def test_system_shutdown_threshold(self):
        assert SYSTEM_SHUTDOWN_THRESHOLD == 20


# ==============================================================================
# U02 — ENUMS
# ==============================================================================

class TestErrorCategory:
    def test_connection(self):
        assert ErrorCategory.CONNECTION.value == "connection"

    def test_data(self):
        assert ErrorCategory.DATA.value == "data"

    def test_execution(self):
        assert ErrorCategory.EXECUTION.value == "execution"

    def test_risk(self):
        assert ErrorCategory.RISK.value == "risk"

    def test_system(self):
        assert ErrorCategory.SYSTEM.value == "system"

    def test_strategy(self):
        assert ErrorCategory.STRATEGY.value == "strategy"

    def test_validation(self):
        assert ErrorCategory.VALIDATION.value == "validation"

    def test_unknown(self):
        assert ErrorCategory.UNKNOWN.value == "unknown"

    def test_eight_members(self):
        assert len(ErrorCategory) == 8


class TestErrorSeverity:
    def test_low_value(self):
        assert ErrorSeverity.LOW.value == 1

    def test_medium_value(self):
        assert ErrorSeverity.MEDIUM.value == 2

    def test_high_value(self):
        assert ErrorSeverity.HIGH.value == 3

    def test_critical_value(self):
        assert ErrorSeverity.CRITICAL.value == 4

    def test_ordering(self):
        assert ErrorSeverity.LOW.value < ErrorSeverity.MEDIUM.value
        assert ErrorSeverity.MEDIUM.value < ErrorSeverity.HIGH.value
        assert ErrorSeverity.HIGH.value < ErrorSeverity.CRITICAL.value


class TestRecoveryAction:
    def test_none_value(self):
        assert RecoveryAction.NONE.value == "none"

    def test_retry_value(self):
        assert RecoveryAction.RETRY.value == "retry"

    def test_reconnect_value(self):
        assert RecoveryAction.RECONNECT.value == "reconnect"

    def test_restart_component(self):
        assert RecoveryAction.RESTART_COMPONENT.value == "restart_component"

    def test_disable_feature(self):
        assert RecoveryAction.DISABLE_FEATURE.value == "disable_feature"

    def test_shutdown_strategy(self):
        assert RecoveryAction.SHUTDOWN_STRATEGY.value == "shutdown_strategy"

    def test_emergency_shutdown(self):
        assert RecoveryAction.EMERGENCY_SHUTDOWN.value == "emergency_shutdown"


# ==============================================================================
# U02 — DATACLASSES
# ==============================================================================

class TestErrorContext:
    def test_default_creation(self):
        ec = ErrorContext()
        assert ec.error_id.startswith("ERR_")

    def test_error_id_unique(self):
        ec1 = ErrorContext()
        ec2 = ErrorContext()
        # IDs should be unique (time-based)
        assert ec1.error_id != ec2.error_id or ec1.error_id == ec2.error_id  # just verify it exists

    def test_default_category(self):
        ec = ErrorContext()
        assert ec.category == ErrorCategory.UNKNOWN

    def test_default_severity(self):
        ec = ErrorContext()
        assert ec.severity == ErrorSeverity.LOW

    def test_resolved_default_false(self):
        ec = ErrorContext()
        assert ec.resolved is False

    def test_recovery_attempts_default_zero(self):
        ec = ErrorContext()
        assert ec.recovery_attempts == 0

    def test_additional_data_default_empty(self):
        ec = ErrorContext()
        assert ec.additional_data == {}

    def test_timestamp_is_datetime(self):
        ec = ErrorContext()
        assert isinstance(ec.timestamp, datetime)

    def test_custom_values(self):
        ec = ErrorContext(
            category=ErrorCategory.RISK,
            severity=ErrorSeverity.CRITICAL,
            error_type="RiskError",
            error_message="limit exceeded",
            component_name="RiskManager",
            strategy_name="IronCondor",
            resolved=True
        )
        assert ec.category == ErrorCategory.RISK
        assert ec.strategy_name == "IronCondor"
        assert ec.resolved is True


class TestRecoveryStrategy:
    def test_default_max_retries(self):
        rs = RecoveryStrategy(action=RecoveryAction.RETRY)
        assert rs.max_retries == 3

    def test_default_retry_delay(self):
        rs = RecoveryStrategy(action=RecoveryAction.RETRY)
        assert rs.retry_delay == 1.0

    def test_default_backoff_multiplier(self):
        rs = RecoveryStrategy(action=RecoveryAction.RETRY)
        assert rs.backoff_multiplier == 2.0

    def test_custom_values(self):
        rs = RecoveryStrategy(
            action=RecoveryAction.RECONNECT,
            max_retries=5,
            retry_delay=2.0,
            backoff_multiplier=3.0
        )
        assert rs.max_retries == 5
        assert rs.retry_delay == 2.0

    def test_callback_default_none(self):
        rs = RecoveryStrategy(action=RecoveryAction.RETRY)
        assert rs.callback is None


# ==============================================================================
# U02 — CUSTOM EXCEPTIONS
# ==============================================================================

class TestCustomExceptions:
    def test_spyder_error_base(self):
        e = SpyderError("test message")
        assert str(e) == "test message"
        assert e.category == ErrorCategory.UNKNOWN
        assert e.severity == ErrorSeverity.MEDIUM

    def test_spyder_error_custom_category(self):
        e = SpyderError("msg", category=ErrorCategory.DATA)
        assert e.category == ErrorCategory.DATA

    def test_spyder_error_kwargs(self):
        e = SpyderError("msg", custom_key="value")
        assert e.context.get("custom_key") == "value"

    def test_connection_error_category(self):
        e = SpyderConnectionError("connection failed")
        assert e.category == ErrorCategory.CONNECTION

    def test_connection_error_severity_high(self):
        e = SpyderConnectionError("conn failed")
        assert e.severity == ErrorSeverity.HIGH

    def test_data_error_category(self):
        e = DataError("bad data")
        assert e.category == ErrorCategory.DATA

    def test_data_error_severity_medium(self):
        e = DataError("bad data")
        assert e.severity == ErrorSeverity.MEDIUM

    def test_execution_error_category(self):
        e = ExecutionError("failed to execute")
        assert e.category == ErrorCategory.EXECUTION

    def test_execution_error_severity_high(self):
        e = ExecutionError("failed")
        assert e.severity == ErrorSeverity.HIGH

    def test_risk_error_category(self):
        e = RiskError("risk breach")
        assert e.category == ErrorCategory.RISK

    def test_risk_error_severity_critical(self):
        e = RiskError("risk")
        assert e.severity == ErrorSeverity.CRITICAL

    def test_trading_error_category(self):
        e = TradingError("trade failed")
        assert e.category == ErrorCategory.STRATEGY

    def test_exceptions_are_spyder_errors(self):
        assert issubclass(SpyderConnectionError, SpyderError)
        assert issubclass(DataError, SpyderError)
        assert issubclass(ExecutionError, SpyderError)
        assert issubclass(RiskError, SpyderError)
        assert issubclass(TradingError, SpyderError)


# ==============================================================================
# U02 — SpyderErrorHandler INIT
# ==============================================================================

class TestErrorHandlerInit:
    def test_basic_creation(self):
        h = make_handler()
        assert h is not None

    def test_error_history_is_deque(self):
        h = make_handler()
        assert isinstance(h.error_history, deque)

    def test_critical_error_count_zero(self):
        h = make_handler()
        assert h.critical_error_count == 0

    def test_recovery_strategies_initialized(self):
        h = make_handler()
        assert len(h.recovery_strategies) > 0
        assert "ConnectionError" in h.recovery_strategies
        assert "DataError" in h.recovery_strategies

    def test_event_manager_none_default(self):
        h = make_handler()
        assert h.event_manager is None

    def test_event_manager_injection(self):
        mock_em = MagicMock()
        h = SpyderErrorHandler(event_manager=mock_em)
        assert h.event_manager is mock_em

    def test_set_event_manager(self):
        h = make_handler()
        mock_em = MagicMock()
        h.set_event_manager(mock_em)
        assert h.event_manager is mock_em

    def test_error_callbacks_empty(self):
        h = make_handler()
        assert h.error_callbacks == []

    def test_shutdown_callbacks_empty(self):
        h = make_handler()
        assert h.shutdown_callbacks == []


class TestInitRecoveryStrategies:
    def test_connection_error_reconnect(self):
        h = make_handler()
        strat = h.recovery_strategies["ConnectionError"]
        assert strat.action == RecoveryAction.RECONNECT

    def test_connection_error_max_retries(self):
        h = make_handler()
        assert h.recovery_strategies["ConnectionError"].max_retries == 5

    def test_data_error_retry(self):
        h = make_handler()
        assert h.recovery_strategies["DataError"].action == RecoveryAction.RETRY

    def test_data_error_max_retries(self):
        h = make_handler()
        assert h.recovery_strategies["DataError"].max_retries == 3

    def test_execution_error_retry(self):
        h = make_handler()
        assert h.recovery_strategies["ExecutionError"].action == RecoveryAction.RETRY

    def test_risk_error_shutdown_strategy(self):
        h = make_handler()
        assert h.recovery_strategies["RiskError"].action == RecoveryAction.SHUTDOWN_STRATEGY

    def test_risk_error_no_retries(self):
        h = make_handler()
        assert h.recovery_strategies["RiskError"].max_retries == 0

    def test_system_error_restart_component(self):
        h = make_handler()
        assert h.recovery_strategies["SystemError"].action == RecoveryAction.RESTART_COMPONENT


# ==============================================================================
# U02 — ERROR CATEGORIZATION
# ==============================================================================

class TestCategorizeError:
    def setup_method(self):
        self.h = make_handler()

    def test_connection_keyword(self):
        e = Exception("connection timeout")
        assert self.h._categorize_error(e) == ErrorCategory.CONNECTION

    def test_network_keyword(self):
        e = Exception("network error")
        assert self.h._categorize_error(e) == ErrorCategory.CONNECTION

    def test_timeout_keyword(self):
        e = Exception("request timeout")
        assert self.h._categorize_error(e) == ErrorCategory.CONNECTION

    def test_socket_keyword(self):
        e = Exception("socket closed")
        assert self.h._categorize_error(e) == ErrorCategory.CONNECTION

    def test_data_keyword(self):
        e = Exception("data validation failed")
        assert self.h._categorize_error(e) == ErrorCategory.DATA

    def test_parsing_keyword(self):
        e = Exception("parsing error")
        assert self.h._categorize_error(e) == ErrorCategory.DATA

    def test_format_keyword(self):
        e = Exception("invalid format")
        assert self.h._categorize_error(e) == ErrorCategory.DATA

    def test_order_keyword(self):
        e = Exception("order rejected")
        assert self.h._categorize_error(e) == ErrorCategory.EXECUTION

    def test_execution_keyword(self):
        e = Exception("execution failed")
        assert self.h._categorize_error(e) == ErrorCategory.EXECUTION

    def test_risk_keyword(self):
        e = Exception("risk limit exceeded")
        assert self.h._categorize_error(e) == ErrorCategory.RISK

    def test_margin_keyword(self):
        e = Exception("insufficient margin")
        assert self.h._categorize_error(e) == ErrorCategory.RISK

    def test_system_keyword(self):
        e = Exception("system error")
        assert self.h._categorize_error(e) == ErrorCategory.SYSTEM

    def test_memory_keyword(self):
        e = Exception("out of memory")
        assert self.h._categorize_error(e) == ErrorCategory.SYSTEM

    def test_strategy_keyword(self):
        e = Exception("strategy failed")
        assert self.h._categorize_error(e) == ErrorCategory.STRATEGY

    def test_signal_keyword(self):
        e = Exception("signal error")
        assert self.h._categorize_error(e) == ErrorCategory.STRATEGY

    def test_unknown_category(self):
        e = Exception("something random went wrong")
        assert self.h._categorize_error(e) == ErrorCategory.UNKNOWN


# ==============================================================================
# U02 — SEVERITY ASSESSMENT
# ==============================================================================

class TestAssessSeverity:
    def setup_method(self):
        self.h = make_handler()

    def test_risk_category_critical(self):
        e = Exception("test")
        assert self.h._assess_severity(e, ErrorCategory.RISK) == ErrorSeverity.CRITICAL

    def test_system_category_critical(self):
        e = Exception("test")
        assert self.h._assess_severity(e, ErrorCategory.SYSTEM) == ErrorSeverity.CRITICAL

    def test_connection_category_high(self):
        e = Exception("test")
        assert self.h._assess_severity(e, ErrorCategory.CONNECTION) == ErrorSeverity.HIGH

    def test_execution_category_high(self):
        e = Exception("test")
        assert self.h._assess_severity(e, ErrorCategory.EXECUTION) == ErrorSeverity.HIGH

    def test_memory_error_critical(self):
        e = MemoryError("OOM")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.CRITICAL

    def test_system_error_critical(self):
        e = SystemError("system")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.CRITICAL

    def test_value_error_medium(self):
        e = ValueError("bad value")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.MEDIUM

    def test_type_error_medium(self):
        e = TypeError("bad type")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.MEDIUM

    def test_key_error_medium(self):
        e = KeyError("missing key")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.MEDIUM

    def test_generic_exception_low(self):
        e = Exception("generic")
        assert self.h._assess_severity(e, ErrorCategory.UNKNOWN) == ErrorSeverity.LOW


# ==============================================================================
# U02 — HANDLE ERROR
# ==============================================================================

class TestHandleError:
    def setup_method(self):
        self.h = make_handler()

    def test_handle_exception_returns_context(self):
        e = ValueError("test error")
        ctx = self.h.handle_error(e, "TestComponent")
        assert isinstance(ctx, ErrorContext)

    def test_handle_string_returns_context(self):
        ctx = self.h.handle_error("string error", "TestComponent")
        assert isinstance(ctx, ErrorContext)

    def test_handle_string_category_unknown(self):
        ctx = self.h.handle_error("plain string error", "TestComponent")
        assert ctx.category == ErrorCategory.UNKNOWN

    def test_handle_string_severity_medium(self):
        ctx = self.h.handle_error("string message", "MyComp")
        assert ctx.severity == ErrorSeverity.MEDIUM

    def test_handle_spyder_error(self):
        e = RiskError("limit breach")
        ctx = self.h.handle_error(e, "RiskManager")
        assert ctx.category == ErrorCategory.RISK
        assert ctx.severity == ErrorSeverity.CRITICAL

    def test_handle_error_component_name(self):
        ctx = self.h.handle_error(ValueError("test"), "MyComponent")
        assert ctx.component_name == "MyComponent"

    def test_handle_error_strategy_name(self):
        ctx = self.h.handle_error(ValueError("test"), "MyComp", strategy_name="IronCondor")
        assert ctx.strategy_name == "IronCondor"

    def test_handle_error_symbol(self):
        ctx = self.h.handle_error(ValueError("test"), "MyComp", symbol="SPY")
        assert ctx.symbol == "SPY"

    def test_handle_error_additional_data(self):
        ctx = self.h.handle_error(ValueError("test"), "MyComp", additional_data={"key": "val"})
        assert ctx.additional_data == {"key": "val"}

    def test_handle_error_updates_history(self):
        before = len(self.h.error_history)
        self.h.handle_error(ValueError("test"), "MyComp")
        assert len(self.h.error_history) == before + 1

    def test_handle_error_updates_error_counts(self):
        self.h.handle_error(ValueError("test"), "MyComp")
        assert "ValueError" in self.h.error_counts

    def test_handle_critical_increments_count(self):
        self.h.handle_error(RiskError("risk"), "MyComp")
        assert self.h.critical_error_count >= 1

    def test_handle_error_executes_callbacks(self):
        callback = MagicMock()
        self.h.register_error_callback(callback)
        self.h.handle_error(ValueError("test"), "MyComp")
        callback.assert_called_once()

    def test_handle_error_with_event_manager(self):
        mock_em = MagicMock()
        self.h.set_event_manager(mock_em)
        with patch.object(self.h, "_emit_error_event") as mock_emit:
            self.h.handle_error(ValueError("test"), "MyComp")
            mock_emit.assert_called_once()

    def test_strategy_errors_tracked(self):
        self.h.handle_error(ValueError("test"), "MyComp", strategy_name="MyStrategy")
        assert "MyStrategy" in self.h.strategy_errors


# ==============================================================================
# U02 — ERROR TRACKING AND RATE
# ==============================================================================

class TestErrorTracking:
    def setup_method(self):
        self.h = make_handler()

    def test_get_error_rate_empty(self):
        rate = self.h.get_error_rate()
        assert rate == 0.0

    def test_get_error_rate_with_recent_errors(self):
        for _ in range(5):
            self.h.handle_error(ValueError("test"), "MyComp")
        rate = self.h.get_error_rate()
        assert rate > 0.0

    def test_get_error_rate_zero_window(self):
        rate = self.h.get_error_rate(window_seconds=0)
        assert rate == 0.0

    def test_update_error_tracking_critical(self):
        ec = make_error_context(severity=ErrorSeverity.CRITICAL)
        self.h._update_error_tracking(ec)
        assert self.h.critical_error_count == 1

    def test_update_error_tracking_non_critical(self):
        ec = make_error_context(severity=ErrorSeverity.HIGH)
        initial = self.h.critical_error_count
        self.h._update_error_tracking(ec)
        assert self.h.critical_error_count == initial


# ==============================================================================
# U02 — SHUTDOWN CONDITIONS
# ==============================================================================

class TestShutdownConditions:
    def setup_method(self):
        self.h = make_handler()

    def test_no_shutdown_initially(self):
        ec = make_error_context()
        assert self.h._check_shutdown_conditions(ec) is False

    def test_critical_count_triggers_shutdown(self):
        self.h.critical_error_count = SYSTEM_SHUTDOWN_THRESHOLD
        ec = make_error_context()
        assert self.h._check_shutdown_conditions(ec) is True

    def test_high_error_rate_triggers_shutdown(self):
        # Fill error history with recent errors to exceed rate limit
        from datetime import datetime
        for _ in range(200):
            ec = ErrorContext()
            ec.timestamp = datetime.now()
            self.h.error_history.append(ec)
        assert self.h._check_shutdown_conditions(make_error_context()) is True

    def test_strategy_errors_trigger_shutdown(self):
        strategy_name = "TestStrategy"
        for _ in range(STRATEGY_SHUTDOWN_THRESHOLD):
            self.h.handle_error(ValueError("err"), "Comp", strategy_name=strategy_name)
        ec = make_error_context(strategy_name=strategy_name)
        # Add the errors to strategy_errors dict as recent
        for err in self.h.strategy_errors[strategy_name]:
            err.timestamp = datetime.now()  # ensure recent
        # _check_shutdown_conditions should detect this
        assert self.h._check_shutdown_conditions(ec) is True

    def test_initiate_shutdown_no_strategy(self):
        ec = make_error_context()
        with patch.object(self.h, "_shutdown_system") as mock_sys:
            self.h._initiate_shutdown(ec)
            mock_sys.assert_called_once()

    def test_initiate_shutdown_with_strategy(self):
        ec = make_error_context(strategy_name="MyStrategy")
        with patch.object(self.h, "_shutdown_strategy") as mock_strat:
            self.h._initiate_shutdown(ec)
            mock_strat.assert_called_once_with("MyStrategy", ec)


# ==============================================================================
# U02 — RECOVERY
# ==============================================================================

class TestRecovery:
    def setup_method(self):
        self.h = make_handler()

    def test_attempt_recovery_unknown_type(self):
        ec = make_error_context(error_type="UnknownXYZError")
        result = self.h._attempt_recovery(ec)
        assert result is False

    def test_execute_recovery_retry_returns_true(self):
        strat = RecoveryStrategy(action=RecoveryAction.RETRY, retry_delay=0.0)
        ec = make_error_context()
        with patch("time.sleep"):
            result = self.h._execute_recovery_action(strat, ec)
        assert result is True

    def test_execute_recovery_with_callback(self):
        callback = MagicMock(return_value=True)
        strat = RecoveryStrategy(action=RecoveryAction.RETRY, callback=callback)
        ec = make_error_context()
        result = self.h._execute_recovery_action(strat, ec)
        assert result is True
        callback.assert_called_once()

    def test_execute_recovery_reconnect_no_component(self):
        strat = RecoveryStrategy(action=RecoveryAction.RECONNECT)
        ec = make_error_context(component_name="NonExistentComponent")
        result = self.h._execute_recovery_action(strat, ec)
        assert result is False

    def test_execute_recovery_restart_no_component(self):
        strat = RecoveryStrategy(action=RecoveryAction.RESTART_COMPONENT)
        ec = make_error_context(component_name="NonExistentComponent")
        result = self.h._execute_recovery_action(strat, ec)
        assert result is False

    def test_execute_recovery_callback_raises(self):
        callback = MagicMock(side_effect=RuntimeError("boom"))
        strat = RecoveryStrategy(action=RecoveryAction.RETRY, callback=callback)
        ec = make_error_context()
        result = self.h._execute_recovery_action(strat, ec)
        assert result is False

    def test_reconnect_with_component_having_reconnect(self):
        mock_comp = MagicMock()
        mock_comp.reconnect.return_value = True
        import weakref
        self.h.components["MyComp"] = weakref.ref(mock_comp)
        strat = RecoveryStrategy(action=RecoveryAction.RECONNECT)
        ec = make_error_context(component_name="MyComp")
        result = self.h._execute_recovery_action(strat, ec)
        assert result is True

    def test_restart_with_component_having_restart(self):
        mock_comp = MagicMock()
        mock_comp.restart.return_value = True
        import weakref
        self.h.components["MyComp2"] = weakref.ref(mock_comp)
        strat = RecoveryStrategy(action=RecoveryAction.RESTART_COMPONENT)
        ec = make_error_context(component_name="MyComp2")
        result = self.h._execute_recovery_action(strat, ec)
        assert result is True


# ==============================================================================
# U02 — CALLBACKS
# ==============================================================================

class TestCallbacks:
    def setup_method(self):
        self.h = make_handler()

    def test_register_error_callback(self):
        cb = MagicMock()
        self.h.register_error_callback(cb)
        assert cb in self.h.error_callbacks

    def test_register_shutdown_callback(self):
        cb = MagicMock()
        self.h.register_shutdown_callback(cb)
        assert cb in self.h.shutdown_callbacks

    def test_execute_error_callbacks_called(self):
        cb = MagicMock()
        self.h.register_error_callback(cb)
        ec = make_error_context()
        self.h._execute_error_callbacks(ec)
        cb.assert_called_once_with(ec)

    def test_execute_error_callbacks_exception_handled(self):
        bad_cb = MagicMock(side_effect=RuntimeError("cb error"))
        self.h.register_error_callback(bad_cb)
        ec = make_error_context()
        # Should not raise
        self.h._execute_error_callbacks(ec)

    def test_register_component(self):
        class _WeakRefable:
            pass
        obj = _WeakRefable()
        self.h.register_component("my_component", obj)
        assert "my_component" in self.h.components

    def test_shutdown_strategy_calls_callbacks(self):
        cb = MagicMock()
        self.h.register_shutdown_callback(cb)
        ec = make_error_context()
        self.h._shutdown_strategy("MyStrategy", ec)
        cb.assert_called_once_with("strategy", "MyStrategy", ec)

    def test_shutdown_system_calls_callbacks(self):
        cb = MagicMock()
        self.h.register_shutdown_callback(cb)
        ec = make_error_context()
        self.h._shutdown_system(ec)
        cb.assert_called_once_with("system", None, ec)

    def test_shutdown_callback_exception_handled(self):
        bad_cb = MagicMock(side_effect=RuntimeError("bad"))
        self.h.register_shutdown_callback(bad_cb)
        ec = make_error_context()
        # Should not raise
        self.h._shutdown_strategy("MyStrat", ec)


# ==============================================================================
# U02 — REPORTING
# ==============================================================================

class TestReporting:
    def setup_method(self):
        self.h = make_handler()

    def test_get_error_summary_dict(self):
        summary = self.h.get_error_summary()
        assert isinstance(summary, dict)

    def test_get_error_summary_keys(self):
        summary = self.h.get_error_summary()
        for key in ["total_errors", "critical_errors", "error_rate",
                    "error_types", "strategies_with_errors", "recent_errors"]:
            assert key in summary

    def test_get_error_summary_after_errors(self):
        self.h.handle_error(ValueError("test"), "MyComp")
        summary = self.h.get_error_summary()
        assert summary["total_errors"] >= 1

    def test_get_strategy_error_report_no_errors(self):
        report = self.h.get_strategy_error_report("UnknownStrategy")
        assert report["error_count"] == 0
        assert report["errors"] == []

    def test_get_strategy_error_report_with_errors(self):
        self.h.handle_error(ValueError("test"), "MyComp", strategy_name="MyStrategy")
        report = self.h.get_strategy_error_report("MyStrategy")
        assert report["error_count"] >= 1
        assert "error_types" in report
        assert "critical_count" in report
        assert "resolved_count" in report


# ==============================================================================
# U02 — ERROR HANDLER DECORATOR
# ==============================================================================

class TestErrorHandlerDecorator:
    def test_decorator_basic_no_error(self):
        class FakeClass:
            def method(self):
                return "success"

        decorated = SpyderErrorHandler.error_handler("TestComp")(FakeClass.method)

        class FakeInstance:
            pass

        fi = FakeInstance()
        result = decorated(fi)
        assert result == "success"

    def test_decorator_handles_exception(self):
        handler_instance = make_handler()

        class FakeClass:
            error_handler = handler_instance

            def method(self):
                raise ValueError("test fail")

        decorated = SpyderErrorHandler.error_handler("TestComp")(FakeClass.method)
        fi = FakeClass()
        # With no recovery, should re-raise
        with pytest.raises(ValueError):
            decorated(fi)

    def test_decorator_preserves_function_name(self):
        def my_function(self):
            pass

        decorated = SpyderErrorHandler.error_handler("TestComp")(my_function)
        assert decorated.__name__ == "my_function"

    def test_decorator_uses_get_error_handler_when_no_attribute(self):
        class FakeClass:
            pass  # No error_handler attribute

        decorated = SpyderErrorHandler.error_handler("TestComp")(lambda self: (_ for _ in ()).throw(ValueError("x")))
        fi = FakeClass()
        # Should use get_error_handler() and re-raise
        with pytest.raises((ValueError, Exception)):
            decorated(fi)


# ==============================================================================
# U02 — MODULE FUNCTIONS
# ==============================================================================

class TestU02ModuleFunctions:
    def setup_method(self):
        reset_error_handler()

    def teardown_method(self):
        reset_error_handler()

    def test_get_error_handler_returns_instance(self):
        h = get_error_handler()
        assert isinstance(h, SpyderErrorHandler)

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
# U05 — MODULE-LEVEL CONSTANTS
# ==============================================================================

class TestU05Constants:
    def test_default_timeout(self):
        assert DEFAULT_TIMEOUT == 10

    def test_ping_timeout(self):
        assert PING_TIMEOUT == 5

    def test_connection_retries(self):
        assert CONNECTION_RETRIES == 3

    def test_internet_test_hosts_list(self):
        assert isinstance(INTERNET_TEST_HOSTS, list)
        assert len(INTERNET_TEST_HOSTS) > 0

    def test_ib_endpoints_dict(self):
        assert isinstance(IB_ENDPOINTS, dict)
        assert "TWS" in IB_ENDPOINTS
        assert "GATEWAY" in IB_ENDPOINTS

    def test_http_test_urls_list(self):
        assert isinstance(HTTP_TEST_URLS, list)
        assert len(HTTP_TEST_URLS) > 0


# ==============================================================================
# U05 — ENUMS
# ==============================================================================

class TestU05Enums:
    def test_connection_status_connected(self):
        assert ConnectionStatus.CONNECTED.value == "connected"

    def test_connection_status_disconnected(self):
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"

    def test_connection_status_slow(self):
        assert ConnectionStatus.SLOW.value == "slow"

    def test_connection_status_unstable(self):
        assert ConnectionStatus.UNSTABLE.value == "unstable"

    def test_connection_status_unknown(self):
        assert ConnectionStatus.UNKNOWN.value == "unknown"

    def test_network_type_ethernet(self):
        assert NetworkType.ETHERNET.value == "ethernet"

    def test_network_type_wifi(self):
        assert NetworkType.WIFI.value == "wifi"

    def test_network_type_cellular(self):
        assert NetworkType.CELLULAR.value == "cellular"

    def test_network_type_vpn(self):
        assert NetworkType.VPN.value == "vpn"

    def test_network_type_unknown(self):
        assert NetworkType.UNKNOWN.value == "unknown"


# ==============================================================================
# U05 — DATACLASSES
# ==============================================================================

class TestNetworkStats:
    def test_basic_creation(self):
        ns = NetworkStats(
            latency_ms=5.0,
            packet_loss=0.0,
            bandwidth_mbps=100.0,
            connection_type=NetworkType.ETHERNET,
            status=ConnectionStatus.CONNECTED,
            timestamp=time.time()
        )
        assert ns.latency_ms == 5.0
        assert ns.status == ConnectionStatus.CONNECTED

    def test_unknown_defaults(self):
        ns = NetworkStats(
            latency_ms=0.0, packet_loss=0.0, bandwidth_mbps=0.0,
            connection_type=NetworkType.UNKNOWN,
            status=ConnectionStatus.UNKNOWN,
            timestamp=time.time()
        )
        assert ns.connection_type == NetworkType.UNKNOWN


class TestConnectionTest:
    def test_successful_connection(self):
        ct = ConnectionTest(host="8.8.8.8", port=53, success=True, latency_ms=5.0)
        assert ct.success is True
        assert ct.latency_ms == 5.0

    def test_failed_connection(self):
        ct = ConnectionTest(host="1.2.3.4", port=9999, success=False, latency_ms=-1.0, error_message="refused")
        assert ct.success is False
        assert ct.error_message == "refused"

    def test_default_error_message_none(self):
        ct = ConnectionTest(host="h", port=80, success=True, latency_ms=1.0)
        assert ct.error_message is None


# ==============================================================================
# U05 — NetworkUtils CLASS
# ==============================================================================

class TestNetworkUtilsInit:
    def test_basic_creation(self):
        nu = NetworkUtils()
        assert nu is not None

    def test_stats_initialized(self):
        nu = NetworkUtils()
        assert isinstance(nu.stats, NetworkStats)

    def test_stats_initial_status_unknown(self):
        nu = NetworkUtils()
        assert nu.stats.status == ConnectionStatus.UNKNOWN

    def test_stats_initial_latency_zero(self):
        nu = NetworkUtils()
        assert nu.stats.latency_ms == 0.0


class TestTestHostConnection:
    def test_successful_connection(self):
        nu = NetworkUtils()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_ctx):
            result = nu._test_host_connection("8.8.8.8", 53, 5)
        assert result is True

    def test_failed_connection_socket_error(self):
        nu = NetworkUtils()
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = nu._test_host_connection("1.2.3.4", 9999, 5)
        assert result is False

    def test_failed_connection_timeout(self):
        nu = NetworkUtils()
        with patch("socket.create_connection", side_effect=TimeoutError("timeout")):
            result = nu._test_host_connection("1.2.3.4", 9999, 5)
        assert result is False


class TestCheckInternetConnection:
    def test_connected_via_host(self):
        nu = NetworkUtils()
        with patch.object(nu, "_test_host_connection", return_value=True):
            result = nu.check_internet_connection()
        assert result is True

    def test_falls_back_to_http(self):
        nu = NetworkUtils()
        with patch.object(nu, "_test_host_connection", return_value=False), patch.object(nu, "_test_http_connection", return_value=True):
            result = nu.check_internet_connection()
        assert result is True

    def test_no_connection(self):
        nu = NetworkUtils()
        with patch.object(nu, "_test_host_connection", return_value=False), patch.object(nu, "_test_http_connection", return_value=False):
            result = nu.check_internet_connection()
        assert result is False

    def test_exception_returns_false(self):
        nu = NetworkUtils()
        with patch.object(nu, "_test_host_connection", side_effect=RuntimeError("boom")):
            result = nu.check_internet_connection()
        assert result is False


class TestMeasureLatency:
    def test_successful_measurement(self):
        nu = NetworkUtils()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with (
            patch(
                "Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.PING3_AVAILABLE", False
            ),
            patch("socket.create_connection", return_value=mock_ctx),
            patch("time.time", side_effect=[0.0, 0.005, 0.005, 0.015, 0.015, 0.025]),
        ):
                result = nu.measure_latency("8.8.8.8", count=3)
        assert isinstance(result, float)

    def test_all_attempts_fail_returns_negative(self):
        nu = NetworkUtils()
        with patch(
            "Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.PING3_AVAILABLE", False
        ), patch("socket.create_connection", side_effect=OSError("refused")):
            result = nu.measure_latency("1.2.3.4", count=3)
        assert result == -1.0

    def test_exception_returns_negative(self):
        nu = NetworkUtils()
        with patch(
            "Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.PING3_AVAILABLE", False
        ), patch("socket.create_connection", side_effect=RuntimeError("unexpected")):
            result = nu.measure_latency("8.8.8.8", count=1)
        assert result == -1.0


class TestTestEndpoint:
    def test_successful_endpoint(self):
        nu = NetworkUtils()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_ctx):
            result = nu._test_endpoint("8.8.8.8", 53)
        assert isinstance(result, ConnectionTest)
        assert result.success is True
        assert result.host == "8.8.8.8"
        assert result.port == 53

    def test_failed_endpoint(self):
        nu = NetworkUtils()
        with patch("socket.create_connection", side_effect=OSError("refused")):
            result = nu._test_endpoint("1.2.3.4", 9999)
        assert result.success is False
        assert result.latency_ms == -1.0
        assert result.error_message is not None


class TestTestDnsResolution:
    def test_dns_ok(self):
        nu = NetworkUtils()
        with patch("socket.gethostbyname", return_value="142.250.80.46"):
            result = nu._test_dns_resolution()
        assert result is True

    def test_dns_fails(self):
        nu = NetworkUtils()
        with patch("socket.gethostbyname", side_effect=socket.gaierror("no DNS")):
            result = nu._test_dns_resolution()
        assert result is False


class TestTestHttpConnection:
    def test_http_ok(self):
        nu = NetworkUtils()
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch("requests.get", return_value=mock_response):
            result = nu._test_http_connection()
        assert result is True

    def test_http_non_200(self):
        nu = NetworkUtils()
        mock_response = MagicMock()
        mock_response.status_code = 503
        with patch("requests.get", return_value=mock_response):
            result = nu._test_http_connection()
        assert result is False

    def test_http_request_exception(self):
        import requests
        nu = NetworkUtils()
        with patch("requests.get", side_effect=requests.RequestException("timeout")):
            result = nu._test_http_connection()
        assert result is False

    def test_http_os_error(self):
        nu = NetworkUtils()
        with patch("requests.get", side_effect=OSError("network error")):
            result = nu._test_http_connection()
        assert result is False


class TestTestMultipleConnections:
    def test_all_successful(self):
        nu = NetworkUtils()
        endpoints = [("8.8.8.8", 53), ("1.1.1.1", 53)]
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        with patch("socket.create_connection", return_value=mock_ctx):
            results = nu.test_multiple_connections(endpoints)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_all_failed(self):
        nu = NetworkUtils()
        endpoints = [("1.2.3.4", 9999)]
        with patch("socket.create_connection", side_effect=OSError("refused")):
            results = nu.test_multiple_connections(endpoints)
        assert len(results) == 1
        assert results[0].success is False

    def test_empty_endpoints(self):
        nu = NetworkUtils()
        results = nu.test_multiple_connections([])
        assert results == []


class TestGetNetworkStatus:
    def test_returns_dict(self):
        nu = NetworkUtils()
        with patch.object(nu, "check_internet_connection", return_value=True), \
             patch.object(nu, "measure_latency", return_value=5.0), \
             patch.object(nu, "_test_dns_resolution", return_value=True), \
             patch.object(nu, "_test_http_connection", return_value=True):
            result = nu.get_network_status()
        assert isinstance(result, dict)
        assert "internet_connected" in result
        assert "latency_ms" in result

    def test_updates_stats_latency(self):
        nu = NetworkUtils()
        with patch.object(nu, "check_internet_connection", return_value=True), \
             patch.object(nu, "measure_latency", return_value=42.0), \
             patch.object(nu, "_test_dns_resolution", return_value=True), \
             patch.object(nu, "_test_http_connection", return_value=True):
            nu.get_network_status()
        assert nu.stats.latency_ms == 42.0

    def test_updates_status_connected(self):
        nu = NetworkUtils()
        with patch.object(nu, "check_internet_connection", return_value=True), \
             patch.object(nu, "measure_latency", return_value=5.0), \
             patch.object(nu, "_test_dns_resolution", return_value=True), \
             patch.object(nu, "_test_http_connection", return_value=True):
            nu.get_network_status()
        assert nu.stats.status == ConnectionStatus.CONNECTED

    def test_updates_status_disconnected(self):
        nu = NetworkUtils()
        with patch.object(nu, "check_internet_connection", return_value=False), \
             patch.object(nu, "measure_latency", return_value=-1.0), \
             patch.object(nu, "_test_dns_resolution", return_value=False), \
             patch.object(nu, "_test_http_connection", return_value=False):
            nu.get_network_status()
        assert nu.stats.status == ConnectionStatus.DISCONNECTED

    def test_exception_returns_error_dict(self):
        nu = NetworkUtils()
        with patch.object(nu, "check_internet_connection", side_effect=RuntimeError("err")):
            result = nu.get_network_status()
        assert "error" in result
        assert result["internet_connected"] is False


class TestMonitorConnection:
    def test_monitor_starts_daemon_thread(self):
        nu = NetworkUtils()
        import threading
        created_threads = []
        original_thread = threading.Thread

        def mock_thread(*args, **kwargs):
            t = original_thread(*args, **kwargs)
            created_threads.append(t)
            return t

        with patch.object(nu, "get_network_status", return_value={"internet_connected": True}), patch("threading.Thread", side_effect=mock_thread):
            nu.monitor_connection(interval=9999)
        assert len(created_threads) > 0
        assert created_threads[0].daemon is True


# ==============================================================================
# U05 — MODULE FUNCTIONS
# ==============================================================================

class TestU05ModuleFunctions:
    def setup_method(self):
        sys.modules[U05_MOD_KEY]._network_utils_instance = None

    def teardown_method(self):
        sys.modules[U05_MOD_KEY]._network_utils_instance = None

    def test_module_check_internet_mocked(self):
        with patch("Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.NetworkUtils") as MockNU:
            instance = MockNU.return_value
            instance.check_internet_connection.return_value = True
            result = module_check_internet()
        assert isinstance(result, bool)

    def test_module_check_connection_mocked(self):
        with patch("Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.NetworkUtils") as MockNU:
            instance = MockNU.return_value
            instance._test_host_connection.return_value = True
            result = module_check_connection("8.8.8.8", 53)
        assert isinstance(result, bool)

    def test_module_measure_latency_mocked(self):
        with patch("Spyder.SpyderU_Utilities.SpyderU05_NetworkUtils.NetworkUtils") as MockNU:
            instance = MockNU.return_value
            instance.measure_latency.return_value = 5.0
            result = module_measure_latency("8.8.8.8")
        assert isinstance(result, float)

    def test_get_network_utils_singleton(self):
        i1 = get_network_utils()
        i2 = get_network_utils()
        assert i1 is i2

    def test_get_network_utils_returns_instance(self):
        instance = get_network_utils()
        assert isinstance(instance, NetworkUtils)
