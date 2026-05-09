#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT113_BSeries.py
Purpose: Coverage tests for SpyderB_Broker — all 8 modules

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-06 Time: 09:00:00
"""

# ==============================================================================
# BOOTSTRAP — install stubs BEFORE any B-series module is imported
# ==============================================================================
import os
import sys
import types
import logging
import threading
import importlib.util as _ilu
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_B_PKG_PATH = os.path.join(_ROOT, "Spyder", "SpyderB_Broker")


def _ensure_mod(key):
    """Create stub module + all ancestor package stubs.

    Returns (module, is_new) where is_new=True when the leaf was just created.
    """
    is_new = key not in sys.modules
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            sys.modules[ancestor] = types.ModuleType(ancestor)
    return sys.modules[key], is_new


# ==============================================================================
# Third-party stubs
# ==============================================================================

# ---- requests/urllib3 — use real packages (installed in .venv) ---------------
# No stub needed; B40 imports the real requests at module level (no HTTP at import)

# ---- prometheus_client stub --------------------------------------------------
if "prometheus_client" not in sys.modules:
    _prom = types.ModuleType("prometheus_client")
    _prom.Counter = MagicMock
    _prom.Gauge = MagicMock
    _prom.Histogram = MagicMock
    _prom.Summary = MagicMock
    _prom.Info = MagicMock
    _prom.CollectorRegistry = MagicMock
    _prom.start_http_server = MagicMock()
    sys.modules["prometheus_client"] = _prom

# ---- psutil stub (complete — later tests need Process, PROCFS_PATH, etc.) ----
if "psutil" not in sys.modules:
    _psutil = types.ModuleType("psutil")
    _psutil.PROCFS_PATH = "/proc"
    _psutil.LINUX = True
    _psutil.POSIX = True
    _psutil.cpu_percent = MagicMock(return_value=10.0)
    _psutil.cpu_count = MagicMock(return_value=4)
    _psutil.getloadavg = MagicMock(return_value=(1.0, 1.0, 1.0))
    _psutil.pids = MagicMock(return_value=[])
    _psutil.disk_usage = MagicMock(return_value=MagicMock(percent=50.0, total=100, used=50, free=50))
    _psutil.net_io_counters = MagicMock(return_value=MagicMock(bytes_sent=0, bytes_recv=0))
    _psutil.virtual_memory = MagicMock(return_value=MagicMock(
        percent=50.0, total=8*1024**3, available=4*1024**3, used=4*1024**3,
    ))
    _psutil.swap_memory = MagicMock(return_value=MagicMock(percent=0.0, total=2*1024**3, used=0))
    _psutil_proc = MagicMock()
    _psutil_proc.memory_info.return_value = MagicMock(rss=100*1024**2, vms=200*1024**2)
    _psutil_proc.cpu_percent.return_value = 5.0
    _psutil_proc.status.return_value = "running"
    _psutil.Process = MagicMock(return_value=_psutil_proc)
    _psutil.NoSuchProcess = type("NoSuchProcess", (Exception,), {})
    _psutil.AccessDenied = type("AccessDenied", (Exception,), {})
    _psutil.process_iter = MagicMock(return_value=iter([]))
    sys.modules["psutil"] = _psutil
else:
    _psutil = sys.modules["psutil"]

# ---- sseclient stub (optional) -----------------------------------------------
if "sseclient" not in sys.modules:
    _sseclient = types.ModuleType("sseclient")
    _sseclient.SSEClient = MagicMock
    sys.modules["sseclient"] = _sseclient

# ---- PySide6 stubs -----------------------------------------------------------
class _AnyAttrModule(types.ModuleType):
    def __getattr__(self, name):
        val = MagicMock()
        setattr(self, name, val)
        return val

for _pyside_key in [
    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui",
    "PySide6.QtCharts", "PySide6.QtAsyncio",
]:
    if _pyside_key not in sys.modules:
        sys.modules[_pyside_key] = _AnyAttrModule(_pyside_key)

# Ensure QObject exists in QtCore
sys.modules["PySide6.QtCore"].QObject = MagicMock

# ==============================================================================
# Spyder utility stubs (prefixed and bare-name forms)
# ==============================================================================

# SpyderLogger
class _SpyderLoggerCls:
    @staticmethod
    def get_logger(name=""):
        return logging.getLogger(name)

for _key in [
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "SpyderLogger"):
        _m.SpyderLogger = _SpyderLoggerCls
    if _new or not hasattr(_m, "get_logger"):
        _m.get_logger = _SpyderLoggerCls.get_logger

# SpyderErrorHandler
class _SpyderErrorHandlerCls:
    def __init__(self, logger=None): pass
    def log_error(self, *a, **kw): pass
    def handle_exception(self, *a, **kw): pass

for _key in [
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
]:
    _m, _new = _ensure_mod(_key)
    # Always override SpyderErrorHandler — other test files set it to MagicMock
    # at collection time, but B04 needs a real constructor-callable class here.
    _m.SpyderErrorHandler = _SpyderErrorHandlerCls
    if _new or not hasattr(_m, "TradingError"):
        _m.TradingError = type("TradingError", (Exception,), {})

# DateTimeUtils
for _key in [
    "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
    "Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "DateTimeUtils"):
        _m.DateTimeUtils = MagicMock()

# MathUtils
for _key in [
    "Spyder.SpyderU_Utilities.SpyderU06_MathUtils",
    "Spyder.SpyderU_Utilities.SpyderU06_MathUtils",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "MathUtils"):
        _m.MathUtils = MagicMock()

# U40 RateLimiter (B40 imports `rate_limit` and `acquire_tradier`)
def _rate_limit_decorator(func=None, *args, **kwargs):
    if func is not None:
        return func
    def decorator(f):
        return f
    return decorator

for _key in [
    "Spyder.SpyderU_Utilities.SpyderU40_RateLimiter",
    "Spyder.SpyderU_Utilities.SpyderU40_RateLimiter",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "rate_limit"):
        _m.rate_limit = _rate_limit_decorator
    if _new or not hasattr(_m, "acquire_tradier"):
        _m.acquire_tradier = MagicMock(return_value=True)

# U41 CircuitBreaker (B40 imports `tradier_breaker` as decorator)
def _tradier_breaker_decorator(func=None, *args, **kwargs):
    if func is not None:
        return func
    def decorator(f):
        return f
    return decorator

for _key in [
    "Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker",
    "Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "tradier_breaker"):
        _m.tradier_breaker = _tradier_breaker_decorator
    if _new or not hasattr(_m, "CircuitBreaker"):
        _m.CircuitBreaker = MagicMock

# A05 EventManager stub
class _A05EventType(Enum):
    SYSTEM = "system"
    MARKET = "market"
    TRADE = "trade"
    RISK = "risk"

@dataclass
class _A05Event:
    event_type: _A05EventType
    data: dict = field(default_factory=dict)

class _A05EventManagerCls:
    def subscribe(self, *a, **kw): pass
    def publish(self, *a, **kw): pass
    def register_handler(self, *a, **kw): pass

def _get_event_manager():
    return _A05EventManagerCls()

for _key in [
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
    "SpyderA_Core.SpyderA05_EventManager",
]:
    _m, _new = _ensure_mod(_key)
    if _new or not hasattr(_m, "EventManager"):
        _m.EventType = _A05EventType
        _m.Event = _A05Event
        _m.EventManager = _A05EventManagerCls
        _m.get_event_manager = staticmethod(_get_event_manager)

# ==============================================================================
# SpyderB_Broker package pre-stubs
# ==============================================================================
_b_pkg = sys.modules.setdefault("Spyder.SpyderB_Broker", types.ModuleType("Spyder.SpyderB_Broker"))
_b_pkg.__path__ = [_B_PKG_PATH]
_b_pkg.__package__ = "Spyder.SpyderB_Broker"
_b_pkg.__file__ = os.path.join(_B_PKG_PATH, "__init__.py")

_b_pkg_bare = sys.modules.setdefault("SpyderB_Broker", types.ModuleType("SpyderB_Broker"))
_b_pkg_bare.__path__ = [_B_PKG_PATH]
_b_pkg_bare.__package__ = "SpyderB_Broker"

# Stub SpyderB_Utilities bare parent
_u_pkg_bare = sys.modules.setdefault("Spyder.SpyderU_Utilities", types.ModuleType("Spyder.SpyderU_Utilities"))
_u_pkg_bare.__path__ = [os.path.join(_ROOT, "Spyder", "Spyder.SpyderU_Utilities")]

# ==============================================================================
# MODULE LOADER HELPER
# ==============================================================================

def _load_b_module(filename: str, module_name: str):
    """Load a B-series module by filename, registering it in sys.modules."""
    filepath = os.path.join(_B_PKG_PATH, filename)
    spec = _ilu.spec_from_file_location(module_name, filepath)
    mod = _ilu.module_from_spec(spec)
    mod.__package__ = "Spyder.SpyderB_Broker"
    sys.modules[module_name] = mod
    # Also register under the bare package key
    bare_key = module_name.replace("Spyder.", "", 1)
    sys.modules.setdefault(bare_key, mod)
    spec.loader.exec_module(mod)
    return mod


# ==============================================================================
# LOAD B-SERIES MODULES
# ==============================================================================

# B00 — pure stdlib, no Spyder imports → load first
_b00 = _load_b_module("SpyderB00_OrderTypes.py", "Spyder.SpyderB_Broker.SpyderB00_OrderTypes")

# B40 — TradierClient (B02 imports from it; load before B02)
# B40 uses requests + U01/U02/U40/U41 (all stubbed above)
_b40 = _load_b_module("SpyderB40_TradierClient.py", "Spyder.SpyderB_Broker.SpyderB40_TradierClient")

# B02 — OrderManager (imports from B40)
_b02 = _load_b_module("SpyderB02_OrderManager.py", "Spyder.SpyderB_Broker.SpyderB02_OrderManager")

# B03 — PositionTracker (no heavy cross-deps)
_b03 = _load_b_module("SpyderB03_PositionTracker.py", "Spyder.SpyderB_Broker.SpyderB03_PositionTracker")

# B04 — AccountManager
_b04 = _load_b_module("SpyderB04_AccountManager.py", "Spyder.SpyderB_Broker.SpyderB04_AccountManager")

# B15 — PrometheusMetrics
_b15 = _load_b_module("SpyderB15_PrometheusMetrics.py", "Spyder.SpyderB_Broker.SpyderB15_PrometheusMetrics")

# B26 — PySideAsyncBridge (REMOVED — file no longer exists after broker migration)
_b26 = None

# B30 — SPYOptionsChainManager (lazy data type imports + B08 stubs)
# B30 has internal fallback when B08 is absent — just load
_b30 = _load_b_module("SpyderB30_SPYOptionsChainManager.py", "Spyder.SpyderB_Broker.SpyderB30_SPYOptionsChainManager")

# ==============================================================================
# CLEANUP: Remove Spyder-internal stubs that should not persist to later tests.
# B-series modules are now fully loaded; their decorators have been applied.
# Other test files (T91, T46, T45 etc.) need the real U40/U41 implementations.
# ==============================================================================
_STUBS_TO_REMOVE = [
    "Spyder.SpyderU_Utilities.SpyderU40_RateLimiter",
    "Spyder.SpyderU_Utilities.SpyderU40_RateLimiter",
    "Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker",
    "Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker",
]
for _stub_key in _STUBS_TO_REMOVE:
    sys.modules.pop(_stub_key, None)


import pytest
from unittest.mock import MagicMock


# ===========================================================================
# B00 — OrderTypes
# ===========================================================================
class TestB00OrderTypes:
    def test_order_action_members(self):
        OA = _b00.OrderAction
        assert OA.BUY
        assert OA.SELL

    def test_order_type_members(self):
        OT = _b00.OrderType
        assert OT.MARKET
        assert OT.LIMIT
        assert OT.STOP
        assert OT.STOP_LIMIT

    def test_order_status_members(self):
        OS = _b00.OrderStatus
        assert OS.PENDING
        assert OS.SUBMITTED
        assert OS.PARTIALLY_FILLED

    def test_time_in_force_members(self):
        TIF = _b00.TimeInForce
        assert hasattr(TIF, "__members__") or len(list(TIF)) >= 2

    def test_option_right_members(self):
        OR = _b00.OptionRight
        assert hasattr(OR, "__members__") or len(list(OR)) >= 2

    def test_sec_type_members(self):
        ST = _b00.SecType
        assert hasattr(ST, "__members__") or len(list(ST)) >= 2

    def test_contract_details_dataclass(self):
        assert hasattr(_b00, "ContractDetails")

    def test_order_request_dataclass(self):
        assert hasattr(_b00, "OrderRequest")

    def test_bracket_order_dataclass(self):
        assert hasattr(_b00, "BracketOrder")

    def test_fill_dataclass(self):
        assert hasattr(_b00, "Fill")

    def test_order_action_is_enum(self):
        from enum import Enum
        assert issubclass(_b00.OrderAction, Enum)

    def test_order_request_instantiation(self):
        contract = _b00.ContractDetails(
            symbol="SPY",
            sec_type=_b00.SecType.STOCK,
        )
        req = _b00.OrderRequest(
            contract=contract,
            action=_b00.OrderAction.BUY,
            total_quantity=1,
            order_type=_b00.OrderType.MARKET,
        )
        assert req.contract.symbol == "SPY"
        assert req.action == _b00.OrderAction.BUY


# ===========================================================================
# B02 — OrderManager
# ===========================================================================
class TestB02OrderManager:
    def test_order_state_members(self):
        OS = _b02.OrderState
        assert OS.PENDING
        assert OS.SUBMITTED
        assert OS.OPEN
        assert OS.PARTIALLY_FILLED
        assert OS.FILLED
        assert OS.CANCELLED
        assert OS.REJECTED

    def test_security_type_members(self):
        ST = _b02.SecurityType
        assert ST.EQUITY
        assert ST.OPTION
        assert ST.MULTILEG

    def test_order_dataclass(self):
        assert hasattr(_b02, "Order")

    def test_order_result_dataclass(self):
        assert hasattr(_b02, "OrderResult")

    def test_execution_report_dataclass(self):
        assert hasattr(_b02, "ExecutionReport")

    def test_order_manager_class_exists(self):
        assert hasattr(_b02, "OrderManager")

    def test_order_manager_instantiation_with_mock_client(self):
        mock_tradier = MagicMock()
        om = _b02.OrderManager(tradier_client=mock_tradier)
        assert om is not None
        assert om.tradier is mock_tradier

    def test_order_manager_streaming_off_by_default(self):
        mock_tradier = MagicMock()
        om = _b02.OrderManager(tradier_client=mock_tradier)
        assert om._streaming_enabled is False

    def test_order_manager_order_store_empty(self):
        mock_tradier = MagicMock()
        om = _b02.OrderManager(tradier_client=mock_tradier)
        assert isinstance(om._orders, dict)
        assert len(om._orders) == 0

    def test_order_state_is_enum(self):
        from enum import Enum
        assert issubclass(_b02.OrderState, Enum)


# ===========================================================================
# B03 — PositionTracker
# ===========================================================================
class TestB03PositionTracker:
    def test_position_tracker_class_exists(self):
        assert hasattr(_b03, "PositionTracker")

    def test_position_tracker_instantiation(self):
        client = MagicMock()
        pt = _b03.PositionTracker(client)
        assert pt is not None
        assert pt.spyder_client is client

    def test_position_tracker_with_event_manager(self):
        client = MagicMock()
        em = MagicMock()
        pt = _b03.PositionTracker(client, event_manager=em)
        assert pt.event_manager is em

    def test_position_tracker_update_interval(self):
        client = MagicMock()
        pt = _b03.PositionTracker(client, update_interval=2.0)
        assert pt.update_interval == 2.0

    def test_position_tracker_initially_not_running(self):
        client = MagicMock()
        pt = _b03.PositionTracker(client)
        assert pt._running is False

    def test_position_tracker_callbacks_initialized(self):
        client = MagicMock()
        pt = _b03.PositionTracker(client)
        assert isinstance(pt._position_callbacks, list)
        assert isinstance(pt._pnl_callbacks, list)
        assert isinstance(pt._risk_callbacks, list)


# ===========================================================================
# B04 — AccountManager
# ===========================================================================
class TestB04AccountManager:
    def test_account_type_members(self):
        AT = _b04.AccountType
        assert AT.CASH
        assert AT.MARGIN
        assert AT.PORTFOLIO_MARGIN

    def test_account_status_members(self):
        AS = _b04.AccountStatus
        assert AS.ACTIVE
        assert AS.RESTRICTED
        assert AS.CLOSED
        assert AS.SUSPENDED

    def test_risk_level_members(self):
        RL = _b04.RiskLevel
        assert RL.LOW
        assert RL.MEDIUM
        assert RL.HIGH

    def test_restriction_type_members(self):
        RT = _b04.RestrictionType
        assert RT.PDT
        assert RT.MARGIN_CALL
        assert RT.BUYING_POWER

    def test_account_info_dataclass(self):
        assert hasattr(_b04, "AccountInfo")

    def test_balance_snapshot_dataclass(self):
        assert hasattr(_b04, "BalanceSnapshot")

    def test_risk_metrics_dataclass(self):
        assert hasattr(_b04, "RiskMetrics")

    def test_performance_metrics_dataclass(self):
        assert hasattr(_b04, "PerformanceMetrics")

    def test_account_manager_class_exists(self):
        assert hasattr(_b04, "AccountManager")

    def test_account_manager_instantiation_no_args(self):
        am = _b04.AccountManager()
        assert am is not None

    def test_account_manager_has_logger(self):
        am = _b04.AccountManager()
        assert hasattr(am, "logger")

    def test_spyder_client_class_exists(self):
        assert hasattr(_b04, "SpyderClient")

    def test_account_type_is_enum(self):
        from enum import Enum
        assert issubclass(_b04.AccountType, Enum)


# ===========================================================================
# B15 — PrometheusMetrics
# ===========================================================================
class TestB15PrometheusMetrics:
    def test_metric_type_members(self):
        MT = _b15.MetricType
        assert MT.COUNTER
        assert MT.GAUGE
        assert MT.HISTOGRAM
        assert MT.SUMMARY

    def test_metric_period_members(self):
        MP = _b15.MetricPeriod
        assert MP.REAL_TIME
        assert MP.MINUTE
        assert MP.HOUR
        assert MP.DAY

    def test_performance_status_members(self):
        PS = _b15.PerformanceStatus
        assert PS.EXCELLENT
        assert PS.GOOD
        assert PS.POOR
        assert PS.CRITICAL

    def test_trade_status_members(self):
        TS = _b15.TradeStatus
        assert TS.PENDING
        assert TS.EXECUTED

    def test_component_health_members(self):
        CH = _b15.ComponentHealth
        assert CH.HEALTHY
        assert CH.WARNING
        assert CH.CRITICAL
        assert CH.DOWN
        assert CH.UNKNOWN

    def test_trade_metrics_dataclass(self):
        assert hasattr(_b15, "TradeMetrics")

    def test_strategy_metrics_dataclass(self):
        assert hasattr(_b15, "StrategyMetrics")

    def test_portfolio_metrics_dataclass(self):
        assert hasattr(_b15, "PortfolioMetrics")

    def test_metrics_config_dataclass(self):
        assert hasattr(_b15, "MetricsConfig")

    def test_trading_metrics_class(self):
        assert hasattr(_b15, "TradingMetrics")

    def test_trading_metrics_instantiation(self):
        tm = _b15.TradingMetrics()
        assert tm is not None

    def test_prometheus_collector_class_exists(self):
        assert hasattr(_b15, "PrometheusMetricsCollector")

    def test_prometheus_collector_instantiation(self):
        collector = _b15.PrometheusMetricsCollector()
        assert collector is not None

    def test_prometheus_collector_config(self):
        cfg = _b15.MetricsConfig()
        collector = _b15.PrometheusMetricsCollector(config=cfg)
        assert collector.config is cfg

    def test_metric_type_is_enum(self):
        from enum import Enum
        assert issubclass(_b15.MetricType, Enum)


# ===========================================================================
# B26 — PySideAsyncBridge (REMOVED — file deleted during broker migration)
# ===========================================================================


# ===========================================================================
# B30 — SPYOptionsChainManager
# ===========================================================================
class TestB30SPYOptionsChainManager:
    def test_options_chain_type_members(self):
        OCT = _b30.OptionsChainType
        assert OCT.ZERO_DTE
        assert OCT.ONE_DTE
        assert OCT.WEEKLY
        assert OCT.MONTHLY

    def test_option_type_members(self):
        OT = _b30.OptionType
        assert OT.CALL
        assert OT.PUT

    def test_chain_status_members(self):
        CS = _b30.ChainStatus
        assert CS.ACTIVE
        assert CS.EXPIRED
        assert CS.PENDING
        assert CS.ERROR

    def test_options_contract_dataclass(self):
        assert hasattr(_b30, "OptionsContract")

    def test_options_chain_dataclass(self):
        assert hasattr(_b30, "OptionsChain")

    def test_chain_selection_criteria_dataclass(self):
        assert hasattr(_b30, "ChainSelectionCriteria")

    def test_spy_chain_manager_class_exists(self):
        assert hasattr(_b30, "SPYOptionsChainManager")

    def test_spy_chain_manager_instantiation(self):
        mgr = _b30.SPYOptionsChainManager()
        assert mgr is not None

    def test_manager_default_spy_price(self):
        mgr = _b30.SPYOptionsChainManager()
        assert mgr.current_spy_price > 0

    def test_manager_active_chains_empty(self):
        mgr = _b30.SPYOptionsChainManager()
        assert isinstance(mgr.active_chains, dict)

    def test_options_chain_type_is_enum(self):
        from enum import Enum
        assert issubclass(_b30.OptionsChainType, Enum)


# ===========================================================================
# B40 — TradierClient
# ===========================================================================
class TestB40TradierClient:
    def test_trading_environment_members(self):
        TE = _b40.TradingEnvironment
        assert TE.LIVE
        assert TE.SANDBOX
        assert TE.PAPER

    def test_order_side_members(self):
        OS = _b40.OrderSide
        assert OS.BUY
        assert OS.SELL
        assert OS.BUY_TO_OPEN
        assert OS.BUY_TO_CLOSE
        assert OS.SELL_TO_OPEN
        assert OS.SELL_TO_CLOSE

    def test_order_type_members(self):
        OT = _b40.OrderType
        assert OT.MARKET
        assert OT.LIMIT
        assert OT.STOP
        assert OT.STOP_LIMIT

    def test_order_duration_members(self):
        OD = _b40.OrderDuration
        assert OD.DAY
        assert OD.GTC

    def test_order_class_members(self):
        OC = _b40.OrderClass
        assert OC.EQUITY
        assert OC.OPTION
        assert OC.MULTILEG
        assert OC.COMBO

    def test_tradier_api_error_hierarchy(self):
        assert issubclass(_b40.TradierAPIError, Exception)
        assert issubclass(_b40.TradierAuthenticationError, _b40.TradierAPIError)
        assert issubclass(_b40.TradierValidationError, _b40.TradierAPIError)
        assert issubclass(_b40.TradierServerError, _b40.TradierAPIError)
        assert issubclass(_b40.TradierRateLimitError, _b40.TradierAPIError)

    def test_option_leg_dataclass(self):
        assert hasattr(_b40, "OptionLeg")

    def test_greek_data_dataclass(self):
        assert hasattr(_b40, "GreekData")

    def test_greek_data_default_values(self):
        gd = _b40.GreekData()
        assert gd.delta == 0.0
        assert gd.gamma == 0.0
        assert gd.theta == 0.0
        assert gd.vega == 0.0
        assert gd.iv == 0.0

    def test_greek_data_spread_property(self):
        gd = _b40.GreekData(bid=1.00, ask=1.10)
        assert abs(gd.spread - 0.10) < 1e-6

    def test_tradier_client_class_exists(self):
        assert hasattr(_b40, "TradierClient")

    def test_tradier_client_instantiation(self):
        client = _b40.TradierClient(
            api_key="test_key",
            account_id="test_account",
            environment=_b40.TradingEnvironment.SANDBOX,
        )
        assert client is not None
        assert client.api_key == "test_key"
        assert client.account_id == "test_account"
        assert client.environment == _b40.TradingEnvironment.SANDBOX

    def test_tradier_client_sandbox_url(self):
        client = _b40.TradierClient("k", "a", _b40.TradingEnvironment.SANDBOX)
        assert "sandbox" in client.base_url or "tradier" in client.base_url

    def test_tradier_client_paper_uses_sandbox_url(self):
        sandbox_client = _b40.TradierClient("k", "a", _b40.TradingEnvironment.SANDBOX)
        paper_client = _b40.TradierClient("k", "a", _b40.TradingEnvironment.PAPER)
        assert sandbox_client.base_url == paper_client.base_url

    def test_tradier_client_live_url_different_from_sandbox(self):
        sandbox_client = _b40.TradierClient("k", "a", _b40.TradingEnvironment.SANDBOX)
        live_client = _b40.TradierClient("k", "a", _b40.TradingEnvironment.LIVE)
        assert sandbox_client.base_url != live_client.base_url

    def test_account_event_dataclass(self):
        assert hasattr(_b40, "AccountEvent")

    def test_tradier_account_stream_class_exists(self):
        assert hasattr(_b40, "TradierAccountStream")

    def test_trading_environment_is_enum(self):
        from enum import Enum
        assert issubclass(_b40.TradingEnvironment, Enum)

    def test_tradier_client_timeout_default(self):
        client = _b40.TradierClient("k", "a")
        assert client.timeout > 0
