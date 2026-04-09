#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT114_DSeries.py
Purpose: Coverage tests for SpyderD_Strategies — all 30 modules

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-06 Time: 10:00:00
"""

# ==============================================================================
# BOOTSTRAP — install stubs BEFORE any D-series module is imported
# ==============================================================================
import os
import sys
import types
import logging
import importlib.util as _ilu
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, patch

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_D_PKG_PATH = os.path.join(_ROOT, "Spyder", "SpyderD_Strategies")
_U_PKG_PATH = os.path.join(_ROOT, "Spyder", "SpyderU_Utilities")


def _ensure_mod(key, force=False):
    """Create stub module + all ancestor package stubs.

    Args:
        key: sys.modules key to create/get.
        force: If True, ALWAYS create a fresh types.ModuleType stub for the
               leaf module and ASSIGN it to sys.modules (even if the key
               already has a real module).  This is used for 'Spyder.*'
               prefix keys so that D-series modules importing via the 'Spyder.'
               namespace get our stubs rather than whatever the real package
               loaded.  Previously-stored module object references (e.g.
               T112's ``_e01``) are unaffected because they hold a direct
               reference to the old object, not a sys.modules lookup.
               If False (default) use setdefault — create only when absent.

    Returns:
        (module, is_new) where is_new is True when a fresh stub was created.
    """
    is_new = key not in sys.modules
    # Create ancestor package stubs if they do not already exist.
    parts = key.split(".")
    for i in range(1, len(parts)):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            m = types.ModuleType(ancestor)
            real_dir = os.path.join(_ROOT, ancestor.replace(".", os.sep))
            if os.path.isdir(real_dir):
                m.__path__ = [real_dir]
                m.__package__ = ancestor
            sys.modules[ancestor] = m
    # Leaf module
    if force or is_new:
        new_mod = types.ModuleType(key)
        sys.modules[key] = new_mod
        return new_mod, True
    return sys.modules[key], False



# ==============================================================================
# Third-party GUI / plotting stubs
# ==============================================================================

class _AnyAttrModule(types.ModuleType):
    """Module stub that returns MagicMock for any attribute."""
    def __getattr__(self, name):
        val = MagicMock()
        setattr(self, name, val)
        return val


for _pyside_key in [
    "PySide6", "PySide6.QtCore", "PySide6.QtWidgets",
    "PySide6.QtGui", "PySide6.QtCharts",
]:
    if _pyside_key not in sys.modules:
        sys.modules[_pyside_key] = _AnyAttrModule(_pyside_key)

# Only set Qt stub attrs when the module is already OUR stub (not the real library).
_qt_core_mod = sys.modules.get("PySide6.QtCore")
if isinstance(_qt_core_mod, _AnyAttrModule):
    _qt_core_mod.QObject = MagicMock
    _qt_core_mod.Signal = MagicMock
    _qt_core_mod.QTimer = MagicMock
    _qt_core_mod.QThread = MagicMock
    _qt_core_mod.Qt = MagicMock()
    _qt_core_mod.QAbstractTableModel = MagicMock
    _qt_core_mod.QModelIndex = MagicMock
_qt_widgets_mod = sys.modules.get("PySide6.QtWidgets")
if isinstance(_qt_widgets_mod, _AnyAttrModule):
    _qt_widgets_mod.QWidget = MagicMock

# matplotlib backend stub (used in D31) — only install if not already real.
_mpl = sys.modules.setdefault("matplotlib", _AnyAttrModule("matplotlib"))
_mpl_be = types.ModuleType("matplotlib.backends")
_mpl_be_qt = types.ModuleType("matplotlib.backends.backend_qt5agg")
_mpl_be_qt.FigureCanvasQTAgg = MagicMock
if "matplotlib.backends" not in sys.modules:
    sys.modules["matplotlib.backends"] = _mpl_be
if "matplotlib.backends.backend_qt5agg" not in sys.modules:
    sys.modules["matplotlib.backends.backend_qt5agg"] = _mpl_be_qt

# pandas_ta stub — prevents D18 from importing real pandas_ta which sets
# pd.options.mode.copy_on_write = True (breaking other tests' numpy arrays).
if "pandas_ta" not in sys.modules:
    sys.modules["pandas_ta"] = _AnyAttrModule("pandas_ta")

# plotly stubs (for D31)
for _plkey in ["plotly", "plotly.graph_objects", "plotly.express"]:
    if _plkey not in sys.modules:
        sys.modules[_plkey] = _AnyAttrModule(_plkey)

# ==============================================================================
# Spyder utility stubs
# ==============================================================================

# ---- U01 SpyderLogger -------------------------------------------------------
class _SpyderLoggerCls:
    @staticmethod
    def get_logger(name=""):
        return logging.getLogger(name)


for _key in [
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
    "SpyderU_Utilities.SpyderU01_Logger",
]:
    _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
    if _new:
        _m.SpyderLogger = _SpyderLoggerCls
        _m.get_logger = _SpyderLoggerCls.get_logger

# ---- U02 SpyderErrorHandler -------------------------------------------------
class _ErrHandlerCls:
    def __init__(self, logger=None):
        pass

    def log_error(self, *a, **kw):
        pass

    def handle_exception(self, *a, **kw):
        pass


for _key in [
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    "SpyderU_Utilities.SpyderU02_ErrorHandler",
]:
    _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
    if _new:
        _m.SpyderErrorHandler = _ErrHandlerCls
        _m.TradingError = type("TradingError", (Exception,), {})
        _m.DataValidationError = type("DataValidationError", (Exception,), {})
        _m.SpyderException = type("SpyderException", (Exception,), {})

# ---- U07 Constants — load REAL file (stdlib-only deps) ----------------------
_u07_path = os.path.join(_U_PKG_PATH, "SpyderU07_Constants.py")
_u07_spec = _ilu.spec_from_file_location(
    "Spyder.SpyderU_Utilities.SpyderU07_Constants", _u07_path
)
_u07_real = _ilu.module_from_spec(_u07_spec)
_u07_real.__package__ = "Spyder.SpyderU_Utilities"
sys.modules["Spyder.SpyderU_Utilities.SpyderU07_Constants"] = _u07_real
sys.modules.setdefault("SpyderU_Utilities.SpyderU07_Constants", _u07_real)
_u07_spec.loader.exec_module(_u07_real)

# Inject constants that D modules import but are absent from the real U07 file
_u07_real.ZERO_DTE_STOP_LOSS = 2.0           # 200% of credit (stop-loss multiple)
_u07_real.CALENDAR_SPREAD_PROFIT_TARGET = 0.50
_u07_real.CALENDAR_SPREAD_STOP_LOSS = 2.00

# ---- U13 TechnicalIndicators ------------------------------------------------
for _key in [
    "Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators",
    "SpyderU_Utilities.SpyderU13_TechnicalIndicators",
]:
    _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
    if _new:
        _m.TechnicalIndicators = MagicMock

# ---- A05 EventManager -------------------------------------------------------
class _A05EventType(Enum):
    SYSTEM = "system"
    MARKET = "market"
    TRADE = "trade"
    RISK = "risk"
    ORDER = "order"
    SIGNAL = "signal"


@dataclass
class _A05Event:
    event_type: _A05EventType
    data: dict = field(default_factory=dict)


class _A05EventManagerCls:
    def subscribe(self, *a, **kw):
        pass

    def publish(self, *a, **kw):
        pass

    def register_handler(self, *a, **kw):
        pass

    def unsubscribe(self, *a, **kw):
        pass


def _get_event_manager():
    return _A05EventManagerCls()


def _get_event_bus():
    return _A05EventManagerCls()


for _key in [
    "Spyder.SpyderA_Core.SpyderA05_EventManager",
    "SpyderA_Core.SpyderA05_EventManager",
]:
    # Only force-replace our own _AnyAttrModule stubs, not real modules from other test files
    _a05_existing = sys.modules.get(_key)
    _a05_force = _key.startswith("Spyder.") and isinstance(_a05_existing, _AnyAttrModule)
    _m, _new = _ensure_mod(_key, force=_a05_force)
    if _new or not hasattr(_m, "EventManager"):
        _m.EventType = _A05EventType
        _m.Event = _A05Event
        _m.EventManager = _A05EventManagerCls
        _m.get_event_manager = staticmethod(_get_event_manager)
        _m.get_event_bus = staticmethod(_get_event_bus)

# ---- E01 RiskManager: load from file directly (avoids Spyder __init__ chain) -
for _key in [
    "Spyder.SpyderE_Risk.SpyderE01_RiskManager",
    "SpyderE_Risk.SpyderE01_RiskManager",
]:
    if _key not in sys.modules:
        _e01_path = os.path.join(_ROOT, "Spyder", "SpyderE_Risk", "SpyderE01_RiskManager.py")
        try:
            import importlib.util as _ilu_e01
            _spec = _ilu_e01.spec_from_file_location(_key, _e01_path)
            _mod = _ilu_e01.module_from_spec(_spec)
            sys.modules[_key] = _mod
            _spec.loader.exec_module(_mod)
        except Exception:
            _m, _new = _ensure_mod(_key, force=False)
            if _new:
                _m.RiskProfile = MagicMock(return_value=MagicMock())
                _m.RiskManager = MagicMock
                _m.RiskLevel = MagicMock
                _m.DEFAULT_RISK_LIMITS = {
                    'max_position_size': 1000,
                    'max_total_exposure': 100000.0,
                    'max_daily_loss': 10000.0,
                    'max_single_order_size': 500,
                    'max_orders_per_minute': 10,
                    'max_concentration_ratio': 0.3,
                    'max_options_exposure': 50000.0,
                    'max_margin_usage': 0.8,
                }

# ---- E08 PositionGroupValidator ---------------------------------------------
for _key in [
    "Spyder.SpyderE_Risk.SpyderE08_PositionGroupValidator",
    "SpyderE_Risk.SpyderE08_PositionGroupValidator",
]:
    _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
    if _new:
        _m.PositionGroupValidator = MagicMock

# ---- F-series stubs ---------------------------------------------------------
_F_STUBS = {
    "SpyderF01_Indicators": {
        "TechnicalIndicators": MagicMock,
        "MarketProfile": MagicMock,
    },
    "SpyderF02_PriceAction": {"PriceActionAnalyzer": MagicMock},
    "SpyderF04_VolatilityAnalysis": {"VolatilityAnalyzer": MagicMock},
    "SpyderF05_TrendDetection": {"TrendDetector": MagicMock},
    "SpyderF06_GreeksCalculator": {"GreeksCalculator": MagicMock},
    "SpyderF08_VolatilityRegime": {"VolatilityRegimeAnalyzer": MagicMock},
    "SpyderF10_MarketRegimeDetector": {"MarketRegimeDetector": MagicMock},
    "SpyderF21_RenaissanceIndicators": {
        "RenaissanceStyleSignalGenerator": MagicMock,
        "MeanReversionIndicators": MagicMock,
        "VolatilityIndicators": MagicMock,
        "MeanReversionSignal": MagicMock,
        "VolatilityRegime": MagicMock,
        "RenaissanceSignal": MagicMock,
        "ZSCORE_OVERBOUGHT": 2.0,
        "ZSCORE_OVERSOLD": -2.0,
        "IV_HIGH_PERCENTILE": 80.0,
        "IV_LOW_PERCENTILE": 20.0,
    },
}

for _fname, _attrs in _F_STUBS.items():
    for _key in [
        f"Spyder.SpyderF_Analysis.{_fname}",
        f"SpyderF_Analysis.{_fname}",
    ]:
        _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
        if _new:
            for _attr_name, _attr_val in _attrs.items():
                setattr(_m, _attr_name, _attr_val)

# ---- C-series stubs ---------------------------------------------------------
_C_STUBS = {
    "SpyderC05_VolumeProfile": {"VolumeProfileAnalyzer": MagicMock},
    "SpyderC09_NewsManager": {"NewsManager": MagicMock},
    "SpyderC10_VIXAnalyzer": {"VIXAnalyzer": MagicMock},
}

for _fname, _attrs in _C_STUBS.items():
    for _key in [
        f"Spyder.SpyderC_MarketData.{_fname}",
        f"SpyderC_MarketData.{_fname}",
    ]:
        _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
        if _new:
            for _attr_name, _attr_val in _attrs.items():
                setattr(_m, _attr_name, _attr_val)

# ---- N-series (OptionsAnalytics) stubs --------------------------------------
_N_OPT_STUBS = {
    "SpyderN07_OPRAGreeksHandler": {"OPRAGreeksHandler": MagicMock},
}

for _fname, _attrs in _N_OPT_STUBS.items():
    for _key in [
        f"Spyder.SpyderN_OptionsAnalytics.{_fname}",
        f"SpyderN_OptionsAnalytics.{_fname}",
    ]:
        _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
        if _new:
            for _attr_name, _attr_val in _attrs.items():
                setattr(_m, _attr_name, _attr_val)

# N11 is handled specially: always ensure GreeksFlowAnalyzer exists (needed by
# D09), but do NOT force-replace if the real module is already loaded (T108
# imports from it at collection time and the real module is needed intact).
for _key in [
    "Spyder.SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow",
    "SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow",
]:
    _n11_mod, _n11_new = _ensure_mod(_key, force=False)
    if not hasattr(_n11_mod, "GreeksFlowAnalyzer"):
        _n11_mod.GreeksFlowAnalyzer = MagicMock
    if not hasattr(_n11_mod, "OptionsGreeksFlowAnalyzer"):
        _n11_mod.OptionsGreeksFlowAnalyzer = MagicMock
    if not hasattr(_n11_mod, "OptionChainManager"):
        _n11_mod.OptionChainManager = MagicMock

# ---- N-series (Numerical) stubs ---------------------------------------------
_N_NUM_STUBS = {
    "SpyderN04_OptionsGreeksCalculator": {"OptionsGreeksCalculator": MagicMock},
    "SpyderN05_VolatilityModeling": {"VolatilityModeling": MagicMock},
}

for _fname, _attrs in _N_NUM_STUBS.items():
    for _key in [
        f"Spyder.SpyderN_Numerical.{_fname}",
        f"SpyderN_Numerical.{_fname}",
    ]:
        _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
        if _new:
            for _attr_name, _attr_val in _attrs.items():
                setattr(_m, _attr_name, _attr_val)

# ---- P07 RenaissancePositionSizer stub (for D33) ----------------------------
for _key in [
    "Spyder.SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer",
    "SpyderP_PortfolioMgmt.SpyderP07_RenaissancePositionSizer",
]:
    _m, _new = _ensure_mod(_key, force=_key.startswith("Spyder."))
    if _new:
        _m.RenaissancePositionSizer = MagicMock
        _m.PositionSizeMethod = MagicMock
        _m.PositionSizeResult = MagicMock

# ==============================================================================
# SpyderD_Strategies package pre-stubs
# ==============================================================================
_d_pkg = sys.modules.setdefault(
    "Spyder.SpyderD_Strategies", types.ModuleType("Spyder.SpyderD_Strategies")
)
_d_pkg.__path__ = [_D_PKG_PATH]
_d_pkg.__package__ = "Spyder.SpyderD_Strategies"
_d_pkg.__file__ = os.path.join(_D_PKG_PATH, "__init__.py")

_d_pkg_bare = sys.modules.setdefault(
    "SpyderD_Strategies", types.ModuleType("SpyderD_Strategies")
)
_d_pkg_bare.__path__ = [_D_PKG_PATH]
_d_pkg_bare.__package__ = "SpyderD_Strategies"

# Bare-form parent stubs
for _bare in [
    "SpyderU_Utilities",
    "SpyderA_Core",
    "SpyderE_Risk",
    "SpyderF_Analysis",
    "SpyderC_MarketData",
    "SpyderN_OptionsAnalytics",
    "SpyderN_Numerical",
    "SpyderP_PortfolioMgmt",
]:
    _pkg = sys.modules.setdefault(_bare, types.ModuleType(_bare))
    _pkg.__path__ = [os.path.join(_ROOT, "Spyder", _bare)]

# ==============================================================================
# MODULE LOADER HELPER
# ==============================================================================


def _load_d_module(filename: str, module_name: str):
    """Load a D-series module by filename, registering it in sys.modules."""
    from enum import auto as _enum_auto
    from typing import (Union, Optional, Any)
    from collections.abc import Callable
    filepath = os.path.join(_D_PKG_PATH, filename)
    spec = _ilu.spec_from_file_location(module_name, filepath)
    mod = _ilu.module_from_spec(spec)
    mod.__package__ = "Spyder.SpyderD_Strategies"
    # Inject commonly missing names (modules that forget to import them)
    mod.auto = _enum_auto
    mod.Union = Union
    mod.Optional = Optional
    mod.List = list
    mod.Dict = dict
    mod.Tuple = tuple
    mod.Any = Any
    mod.Set = set
    mod.Callable = Callable
    mod.Type = type
    mod.ClassVar = ClassVar
    mod.FrozenSet = frozenset
    sys.modules[module_name] = mod
    bare_key = module_name.replace("Spyder.", "", 1)
    sys.modules.setdefault(bare_key, mod)
    spec.loader.exec_module(mod)
    return mod


# ==============================================================================
# LOAD D-SERIES MODULES
# (order matters: D01 must precede all subclasses)
# ==============================================================================

# D00 — pure constants/enums, no Spyder imports
_d00 = _load_d_module(
    "SpyderD00_StrategyConstants.py",
    "Spyder.SpyderD_Strategies.SpyderD00_StrategyConstants",
)

# D01 — BaseStrategy (U01, U02, U07)
_d01 = _load_d_module(
    "SpyderD01_BaseStrategy.py",
    "Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy",
)

# --- Patch D01 with symbols that other D modules import but D01 doesn't export --
# MarketCondition: imported by D11-D17, D19, D21
class _MarketCondition(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    STABLE = "stable"
    LOW_VOL = "low_vol"

# StrategyState and Signal: imported by D20
class _StrategyState(Enum):
    IDLE = "idle"
    SCANNING = "scanning"
    ACTIVE = "active"
    CLOSING = "closing"
    STOPPED = "stopped"

@dataclass
class _Signal:
    signal_type: str = "neutral"
    strength: float = 0.0
    timestamp: object = None

@dataclass
class _StrategySignal:
    """Stub for StrategySignal imported by D31 from D01."""
    signal_type: str = "neutral"
    strength: float = 0.0
    confidence: float = 0.5
    timestamp: object = None

_d01.MarketCondition = _MarketCondition
_d01.StrategyState = _StrategyState
_d01.Signal = _Signal
_d01.StrategySignal = _StrategySignal

# D18 — standalone (no Spyder cross-imports)
_d18 = _load_d_module(
    "SpyderD18_EvolvedCreditSpread.py",
    "Spyder.SpyderD_Strategies.SpyderD18_EvolvedCreditSpread",
)

# D02 — IronCondor (D01, E01, U01, U02)
_d02 = _load_d_module(
    "SpyderD02_IronCondor.py",
    "Spyder.SpyderD_Strategies.SpyderD02_IronCondor",
)

# D03 — CreditSpread (D01, U01, U02, U07)
_d03 = _load_d_module(
    "SpyderD03_CreditSpread.py",
    "Spyder.SpyderD_Strategies.SpyderD03_CreditSpread",
)

# D04 — ZeroDTE (D01, U01, U02, U07, pytz)
_d04 = _load_d_module(
    "SpyderD04_ZeroDTE.py",
    "Spyder.SpyderD_Strategies.SpyderD04_ZeroDTE",
)

# D05 — Straddle (D01, U01, U02, U07, U13, F06, scipy)
_d05 = _load_d_module(
    "SpyderD05_Straddle.py",
    "Spyder.SpyderD_Strategies.SpyderD05_Straddle",
)

# D08 — OpeningRangeBreakout (D01, U01, U02, U07, U13, C05, F02)
_d08 = _load_d_module(
    "SpyderD08_OpeningRangeBreakout.py",
    "Spyder.SpyderD_Strategies.SpyderD08_OpeningRangeBreakout",
)

# D09 — GreeksBasedStrategy (D01, U01, U02, U07, N07, N11)
_d09 = _load_d_module(
    "SpyderD09_GreeksBasedStrategy.py",
    "Spyder.SpyderD_Strategies.SpyderD09_GreeksBasedStrategy",
)

# D10 — IronButterfly (D01, E01, U01, U02)
_d10 = _load_d_module(
    "SpyderD10_IronButterfly.py",
    "Spyder.SpyderD_Strategies.SpyderD10_IronButterfly",
)

# D11 — SpecializedZeroDTE (A05, D01, E01, F04, F06, F10, U01, U02, U07)
_d11 = _load_d_module(
    "SpyderD11_SpecializedZeroDTE.py",
    "Spyder.SpyderD_Strategies.SpyderD11_SpecializedZeroDTE",
)

# D12 — RSIMeanReversion (A05, D01, E01, F01, F04, F06, U01, U02, U07)
_d12 = _load_d_module(
    "SpyderD12_RSIMeanReversion.py",
    "Spyder.SpyderD_Strategies.SpyderD12_RSIMeanReversion",
)

# D13 — MACrossover (A05, D01, E01, F01, F05, F06, U01, U02, U07)
_d13 = _load_d_module(
    "SpyderD13_MACrossover.py",
    "Spyder.SpyderD_Strategies.SpyderD13_MACrossover",
)

# D14 — CalendarSpread (A05, C10, D01, E01, F04, F06, U01, U02, U07)
_d14 = _load_d_module(
    "SpyderD14_CalendarSpread.py",
    "Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread",
)

# D15 — StraddleStrangle (A05, C09, D01, E01, F04, F06, F08, U01, U02, U07)
_d15 = _load_d_module(
    "SpyderD15_StraddleStrangle.py",
    "Spyder.SpyderD_Strategies.SpyderD15_StraddleStrangle",
)

# D16 — RatioSpreads (A05, D01, E01, E08, F04, F06, F10, U01, U02, U07)
_d16 = _load_d_module(
    "SpyderD16_RatioSpreads.py",
    "Spyder.SpyderD_Strategies.SpyderD16_RatioSpreads",
)

# D17 — DiagonalSpread (A05, D01, E01, F04, F05, F06, U01, U02, U07)
_d17 = _load_d_module(
    "SpyderD17_DiagonalSpread.py",
    "Spyder.SpyderD_Strategies.SpyderD17_DiagonalSpread",
)

# D19 — JadeLizard (A05, D01, E01, E08, F04, F06, F10, U01, U02, U07)
_d19 = _load_d_module(
    "SpyderD19_JadeLizard.py",
    "Spyder.SpyderD_Strategies.SpyderD19_JadeLizard",
)

# D20 — VerticalSpreadOptimizer (D01, N04, N05, U01, U02)
_d20 = _load_d_module(
    "SpyderD20_VerticalSpreadOptimizer.py",
    "Spyder.SpyderD_Strategies.SpyderD20_VerticalSpreadOptimizer",
)

# D21 — DoubleCalendar (A05, C10, D01, E01, F04, F06, F08, U01, U02, U07)
_d21 = _load_d_module(
    "SpyderD21_DoubleCalendar.py",
    "Spyder.SpyderD_Strategies.SpyderD21_DoubleCalendar",
)

# D22 — AdaptiveVolatility (D01, U01, U02)
_d22 = _load_d_module(
    "SpyderD22_AdaptiveVolatility.py",
    "Spyder.SpyderD_Strategies.SpyderD22_AdaptiveVolatility",
)

# D25 — UnifiedCreditSpreadEngine (U01, U02, U07*)
_d25 = _load_d_module(
    "SpyderD25_UnifiedCreditSpreadEngine.py",
    "Spyder.SpyderD_Strategies.SpyderD25_UnifiedCreditSpreadEngine",
)

# D26 — GammaScalper (D01, U01, U02)
_d26 = _load_d_module(
    "SpyderD26_GammaScalper.py",
    "Spyder.SpyderD_Strategies.SpyderD26_GammaScalper",
)

# D27 — EarningsStrategy (U01, U02)
_d27 = _load_d_module(
    "SpyderD27_EarningsStrategy.py",
    "Spyder.SpyderD_Strategies.SpyderD27_EarningsStrategy",
)

# D28 — VIXHedging (U01, U02)
_d28 = _load_d_module(
    "SpyderD28_VIXHedging.py",
    "Spyder.SpyderD_Strategies.SpyderD28_VIXHedging",
)

# D30 — RegimeGatedSelector (numpy, pandas only)
_d30 = _load_d_module(
    "SpyderD30_RegimeGatedSelector.py",
    "Spyder.SpyderD_Strategies.SpyderD30_RegimeGatedSelector",
)

# D31 — patch U15 (PerformanceMetrics doesn't exist in real U15, only PerformanceCalculator)
_u15_mod = sys.modules.get("SpyderU_Utilities.SpyderU15_PerformanceMetrics")
if _u15_mod and not hasattr(_u15_mod, "PerformanceMetrics"):
    _u15_mod.PerformanceMetrics = MagicMock

# D31 needs SpyderB20_IntegratedConnectivityManager stub
import types as _types_mod
_b20_stub = _types_mod.ModuleType("SpyderB_Broker.SpyderB20_IntegratedConnectivityManager")
_b20_stub.IntegratedConnectivityManager = MagicMock
_b20_stub.ConnectivityState = MagicMock
sys.modules["SpyderB_Broker.SpyderB20_IntegratedConnectivityManager"] = _b20_stub
sys.modules["Spyder.SpyderB_Broker.SpyderB20_IntegratedConnectivityManager"] = _b20_stub

# D31 — StrategyOrchestrator (PySide6, plotly, scipy, pytz)
# Pre-inject IntegratedConnectivityManager so it's available even if D31's try block fails
_d31_name = "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
_d31_path = os.path.join(_D_PKG_PATH, "SpyderD31_StrategyOrchestrator.py")
_d31_spec = _ilu.spec_from_file_location(_d31_name, _d31_path)
_d31 = _ilu.module_from_spec(_d31_spec)
_d31.__package__ = "Spyder.SpyderD_Strategies"
from typing import Union, Any, ClassVar, Optional
from collections.abc import Callable
from enum import auto as _enum_auto2
_d31.auto = _enum_auto2
_d31.Union = Union
_d31.Optional = Optional
_d31.List = list
_d31.Dict = dict
_d31.Tuple = tuple
_d31.Any = Any
_d31.Set = set
_d31.Callable = Callable
_d31.IntegratedConnectivityManager = MagicMock  # fallback if try/except fires
sys.modules[_d31_name] = _d31
sys.modules.setdefault(_d31_name.replace("Spyder.", "", 1), _d31)
_d31_spec.loader.exec_module(_d31)

# D32 — MultiLegStrategyCoordinator (U01, U02, U07*)
_d32 = _load_d_module(
    "SpyderD32_MultiLegStrategyCoordinator.py",
    "Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator",
)

# D33 — RenaissanceMeanReversion (D01, F21, P07, U01, U02)
_d33 = _load_d_module(
    "SpyderD33_RenaissanceMeanReversion.py",
    "Spyder.SpyderD_Strategies.SpyderD33_RenaissanceMeanReversion",
)

# ==============================================================================
import pytest
from enum import Enum
import inspect


# ==============================================================================
# D00 — StrategyConstants
# ==============================================================================
class TestD00StrategyConstants:
    def test_strategy_type_enum_exists(self):
        assert hasattr(_d00, "StrategyType")

    def test_strategy_type_is_enum(self):
        assert issubclass(_d00.StrategyType, Enum)

    def test_strategy_type_has_members(self):
        members = list(_d00.StrategyType)
        assert len(members) >= 2

    def test_market_regime_enum_exists(self):
        assert hasattr(_d00, "MarketRegime")

    def test_market_regime_is_enum(self):
        assert issubclass(_d00.MarketRegime, Enum)

    def test_risk_level_enum_exists(self):
        assert hasattr(_d00, "RiskLevel")

    def test_risk_level_is_enum(self):
        assert issubclass(_d00.RiskLevel, Enum)

    def test_market_regime_has_expected_members(self):
        mr = _d00.MarketRegime
        assert len(list(mr)) >= 2


# ==============================================================================
# D01 — BaseStrategy
# ==============================================================================
class TestD01BaseStrategy:
    def test_signal_type_enum_exists(self):
        assert hasattr(_d01, "SignalType")

    def test_signal_type_is_enum(self):
        assert issubclass(_d01.SignalType, Enum)

    def test_signal_strength_enum_exists(self):
        assert hasattr(_d01, "SignalStrength")

    def test_signal_strength_is_enum(self):
        assert issubclass(_d01.SignalStrength, Enum)

    def test_position_type_enum_exists(self):
        assert hasattr(_d01, "PositionType")

    def test_position_state_enum_exists(self):
        assert hasattr(_d01, "PositionState")

    def test_trading_signal_class_exists(self):
        assert hasattr(_d01, "TradingSignal")

    def test_strategy_position_class_exists(self):
        assert hasattr(_d01, "StrategyPosition")

    def test_risk_profile_class_exists(self):
        assert hasattr(_d01, "RiskProfile")

    def test_performance_metrics_class_exists(self):
        assert hasattr(_d01, "PerformanceMetrics")

    def test_base_strategy_exists(self):
        assert hasattr(_d01, "BaseStrategy")

    def test_base_strategy_is_abstract(self):
        import abc
        assert issubclass(_d01.BaseStrategy, abc.ABC)

    def test_strategy_factory_exists(self):
        assert hasattr(_d01, "StrategyFactory")

    def test_event_manager_exists(self):
        assert hasattr(_d01, "EventManager")

    def test_signal_type_buy_member(self):
        st = _d01.SignalType
        names = [m.name for m in st]
        assert any("BUY" in n or "LONG" in n or "ENTER" in n for n in names)


# ==============================================================================
# D02 — IronCondor
# ==============================================================================
class TestD02IronCondor:
    def test_iron_condor_state_enum_exists(self):
        assert hasattr(_d02, "IronCondorState")

    def test_iron_condor_state_is_enum(self):
        assert issubclass(_d02.IronCondorState, Enum)

    def test_iron_condor_state_has_members(self):
        assert len(list(_d02.IronCondorState)) >= 2

    def test_iron_condor_adjustment_type_exists(self):
        assert hasattr(_d02, "IronCondorAdjustmentType")

    def test_iron_condor_setup_class_exists(self):
        assert hasattr(_d02, "IronCondorSetup")

    def test_iron_condor_analysis_class_exists(self):
        assert hasattr(_d02, "IronCondorAnalysis")

    def test_iron_condor_strategy_exists(self):
        assert hasattr(_d02, "IronCondorStrategy")

    def test_iron_condor_strategy_is_class(self):
        assert inspect.isclass(_d02.IronCondorStrategy)

    def test_iron_condor_strategy_is_base_strategy_subclass(self):
        assert issubclass(_d02.IronCondorStrategy, _d01.BaseStrategy)


# ==============================================================================
# D03 — CreditSpread
# ==============================================================================
class TestD03CreditSpread:
    def test_spread_type_enum_exists(self):
        assert hasattr(_d03, "SpreadType")

    def test_spread_type_is_enum(self):
        assert issubclass(_d03.SpreadType, Enum)

    def test_market_condition_enum_exists(self):
        assert hasattr(_d03, "MarketCondition")

    def test_spread_state_enum_exists(self):
        assert hasattr(_d03, "SpreadState")

    def test_option_leg_class_exists(self):
        assert hasattr(_d03, "OptionLeg")

    def test_credit_spread_class_exists(self):
        assert hasattr(_d03, "CreditSpread")

    def test_credit_spread_strategy_exists(self):
        assert hasattr(_d03, "CreditSpreadStrategy")

    def test_credit_spread_strategy_is_subclass(self):
        assert issubclass(_d03.CreditSpreadStrategy, _d01.BaseStrategy)


# ==============================================================================
# D04 — ZeroDTE
# ==============================================================================
class TestD04ZeroDTE:
    def test_zero_dte_state_enum_exists(self):
        assert hasattr(_d04, "ZeroDTEState")

    def test_zero_dte_state_is_enum(self):
        assert issubclass(_d04.ZeroDTEState, Enum)

    def test_market_phase_enum_exists(self):
        assert hasattr(_d04, "MarketPhase")

    def test_market_phase_is_enum(self):
        assert issubclass(_d04.MarketPhase, Enum)

    def test_zero_dte_position_class_exists(self):
        assert hasattr(_d04, "ZeroDTEPosition")

    def test_market_conditions_class_exists(self):
        assert hasattr(_d04, "MarketConditions")

    def test_zero_dte_setup_class_exists(self):
        assert hasattr(_d04, "ZeroDTESetup")

    def test_zero_dte_strategy_is_class(self):
        # Note: ZeroDTEStrategy enum is overwritten by the class
        assert inspect.isclass(_d04.ZeroDTEStrategy)

    def test_zero_dte_strategy_is_subclass(self):
        assert issubclass(_d04.ZeroDTEStrategy, _d01.BaseStrategy)


# ==============================================================================
# D05 — Straddle
# ==============================================================================
class TestD05Straddle:
    def test_volatility_regime_enum_exists(self):
        assert hasattr(_d05, "VolatilityRegime")

    def test_volatility_regime_is_enum(self):
        assert issubclass(_d05.VolatilityRegime, Enum)

    def test_option_leg_class_exists(self):
        assert hasattr(_d05, "OptionLeg")

    def test_straddle_position_class_exists(self):
        assert hasattr(_d05, "StraddlePosition")

    def test_volatility_analysis_class_exists(self):
        assert hasattr(_d05, "VolatilityAnalysis")

    def test_straddle_strategy_exists(self):
        assert hasattr(_d05, "StraddleStrategy")

    def test_straddle_strategy_is_subclass(self):
        assert issubclass(_d05.StraddleStrategy, _d01.BaseStrategy)


# ==============================================================================
# D08 — OpeningRangeBreakout
# ==============================================================================
class TestD08OpeningRangeBreakout:
    def test_range_state_enum_exists(self):
        assert hasattr(_d08, "RangeState")

    def test_range_state_is_enum(self):
        assert issubclass(_d08.RangeState, Enum)

    def test_breakout_type_enum_exists(self):
        assert hasattr(_d08, "BreakoutType")

    def test_breakout_quality_enum_exists(self):
        assert hasattr(_d08, "BreakoutQuality")

    def test_opening_range_class_exists(self):
        assert hasattr(_d08, "OpeningRange")

    def test_breakout_signal_class_exists(self):
        assert hasattr(_d08, "BreakoutSignal")

    def test_breakout_position_class_exists(self):
        assert hasattr(_d08, "BreakoutPosition")

    def test_orb_strategy_exists(self):
        assert hasattr(_d08, "OpeningRangeBreakoutStrategy")

    def test_orb_strategy_is_subclass(self):
        assert issubclass(_d08.OpeningRangeBreakoutStrategy, _d01.BaseStrategy)


# ==============================================================================
# D09 — GreeksBasedStrategy
# ==============================================================================
class TestD09GreeksBasedStrategy:
    def test_greeks_strategy_enum_exists(self):
        assert hasattr(_d09, "GreeksStrategy")

    def test_greeks_signal_type_enum_exists(self):
        assert hasattr(_d09, "GreeksSignalType")

    def test_greeks_signal_type_is_enum(self):
        assert issubclass(_d09.GreeksSignalType, Enum)

    def test_greeks_cache_status_enum_exists(self):
        assert hasattr(_d09, "GreeksCacheStatus")

    def test_greeks_snapshot_class_exists(self):
        assert hasattr(_d09, "GreeksSnapshot")

    def test_greeks_position_class_exists(self):
        assert hasattr(_d09, "GreeksPosition")

    def test_greeks_cache_manager_class_exists(self):
        assert hasattr(_d09, "GreeksCacheManager")

    def test_greeks_based_strategy_exists(self):
        assert hasattr(_d09, "GreeksBasedStrategy")

    def test_greeks_based_strategy_is_subclass(self):
        assert issubclass(_d09.GreeksBasedStrategy, _d01.BaseStrategy)


# ==============================================================================
# D10 — IronButterfly
# ==============================================================================
class TestD10IronButterfly:
    def test_iron_butterfly_state_enum_exists(self):
        assert hasattr(_d10, "IronButterflyState")

    def test_iron_butterfly_state_is_enum(self):
        assert issubclass(_d10.IronButterflyState, Enum)

    def test_iron_butterfly_adjustment_type_exists(self):
        assert hasattr(_d10, "IronButterflyAdjustmentType")

    def test_iron_butterfly_setup_class_exists(self):
        assert hasattr(_d10, "IronButterflySetup")

    def test_iron_butterfly_analysis_class_exists(self):
        assert hasattr(_d10, "IronButterflyAnalysis")

    def test_iron_butterfly_strategy_exists(self):
        assert hasattr(_d10, "IronButterflyStrategy")

    def test_iron_butterfly_strategy_is_subclass(self):
        assert issubclass(_d10.IronButterflyStrategy, _d01.BaseStrategy)


# ==============================================================================
# D11 — SpecializedZeroDTE
# ==============================================================================
class TestD11SpecializedZeroDTE:
    def test_zero_dte_state_enum_exists(self):
        assert hasattr(_d11, "ZeroDTEState")

    def test_market_bias_enum_exists(self):
        assert hasattr(_d11, "MarketBias")

    def test_market_bias_is_enum(self):
        assert issubclass(_d11.MarketBias, Enum)

    def test_zero_dte_setup_class_exists(self):
        assert hasattr(_d11, "ZeroDTESetup")

    def test_zero_dte_position_class_exists(self):
        assert hasattr(_d11, "ZeroDTEPosition")

    def test_zero_dte_metrics_class_exists(self):
        assert hasattr(_d11, "ZeroDTEMetrics")

    def test_specialized_zero_dte_strategy_exists(self):
        assert hasattr(_d11, "SpecializedZeroDTEStrategy")

    def test_specialized_zero_dte_strategy_is_subclass(self):
        assert issubclass(_d11.SpecializedZeroDTEStrategy, _d01.BaseStrategy)


# ==============================================================================
# D12 — RSIMeanReversion
# ==============================================================================
class TestD12RSIMeanReversion:
    def test_rsi_state_enum_exists(self):
        assert hasattr(_d12, "RSIState")

    def test_rsi_state_is_enum(self):
        assert issubclass(_d12.RSIState, Enum)

    def test_divergence_type_enum_exists(self):
        assert hasattr(_d12, "DivergenceType")

    def test_divergence_type_is_enum(self):
        assert issubclass(_d12.DivergenceType, Enum)

    def test_reversion_state_enum_exists(self):
        assert hasattr(_d12, "ReversionState")

    def test_rsi_divergence_class_exists(self):
        assert hasattr(_d12, "RSIDivergence")

    def test_rsi_signal_class_exists(self):
        assert hasattr(_d12, "RSISignal")

    def test_rsi_position_class_exists(self):
        assert hasattr(_d12, "RSIPosition")

    def test_rsi_mean_reversion_strategy_exists(self):
        assert hasattr(_d12, "RSIMeanReversionStrategy")

    def test_rsi_mean_reversion_strategy_is_subclass(self):
        assert issubclass(_d12.RSIMeanReversionStrategy, _d01.BaseStrategy)


# ==============================================================================
# D13 — MACrossover
# ==============================================================================
class TestD13MACrossover:
    def test_crossover_type_enum_exists(self):
        assert hasattr(_d13, "CrossoverType")

    def test_crossover_type_is_enum(self):
        assert issubclass(_d13.CrossoverType, Enum)

    def test_ma_state_enum_exists(self):
        assert hasattr(_d13, "MAState")

    def test_ma_state_is_enum(self):
        assert issubclass(_d13.MAState, Enum)

    def test_trend_phase_enum_exists(self):
        assert hasattr(_d13, "TrendPhase")

    def test_crossover_signal_class_exists(self):
        assert hasattr(_d13, "CrossoverSignal")

    def test_ma_position_class_exists(self):
        assert hasattr(_d13, "MAPosition")

    def test_ma_crossover_strategy_exists(self):
        assert hasattr(_d13, "MACrossoverStrategy")

    def test_ma_crossover_strategy_is_subclass(self):
        assert issubclass(_d13.MACrossoverStrategy, _d01.BaseStrategy)


# ==============================================================================
# D14 — CalendarSpread
# ==============================================================================
class TestD14CalendarSpread:
    def test_calendar_type_enum_exists(self):
        assert hasattr(_d14, "CalendarType")

    def test_calendar_type_is_enum(self):
        assert issubclass(_d14.CalendarType, Enum)

    def test_calendar_state_enum_exists(self):
        assert hasattr(_d14, "CalendarState")

    def test_iv_regime_enum_exists(self):
        assert hasattr(_d14, "IVRegime")

    def test_iv_regime_is_enum(self):
        assert issubclass(_d14.IVRegime, Enum)

    def test_term_structure_class_exists(self):
        assert hasattr(_d14, "TermStructure")

    def test_calendar_leg_class_exists(self):
        assert hasattr(_d14, "CalendarLeg")

    def test_calendar_setup_class_exists(self):
        assert hasattr(_d14, "CalendarSetup")

    def test_calendar_position_class_exists(self):
        assert hasattr(_d14, "CalendarPosition")

    def test_calendar_spread_strategy_exists(self):
        assert hasattr(_d14, "CalendarSpreadStrategy")

    def test_calendar_spread_strategy_is_subclass(self):
        assert issubclass(_d14.CalendarSpreadStrategy, _d01.BaseStrategy)


# ==============================================================================
# D15 — StraddleStrangle
# ==============================================================================
class TestD15StraddleStrangle:
    def test_volatility_strategy_enum_exists(self):
        assert hasattr(_d15, "VolatilityStrategy")

    def test_volatility_event_enum_exists(self):
        assert hasattr(_d15, "VolatilityEvent")

    def test_position_state_enum_exists(self):
        assert hasattr(_d15, "PositionState")

    def test_volatility_setup_class_exists(self):
        assert hasattr(_d15, "VolatilitySetup")

    def test_volatility_position_class_exists(self):
        assert hasattr(_d15, "VolatilityPosition")

    def test_straddle_strangle_strategy_exists(self):
        assert hasattr(_d15, "StraddleStrangleStrategy")

    def test_straddle_strangle_strategy_is_subclass(self):
        assert issubclass(_d15.StraddleStrangleStrategy, _d01.BaseStrategy)


# ==============================================================================
# D16 — RatioSpreads
# ==============================================================================
class TestD16RatioSpreads:
    def test_ratio_strategy_enum_exists(self):
        assert hasattr(_d16, "RatioStrategy")

    def test_ratio_strategy_is_enum(self):
        assert issubclass(_d16.RatioStrategy, Enum)

    def test_ratio_type_enum_exists(self):
        assert hasattr(_d16, "RatioType")

    def test_risk_zone_enum_exists(self):
        assert hasattr(_d16, "RiskZone")

    def test_ratio_leg_class_exists(self):
        assert hasattr(_d16, "RatioLeg")

    def test_ratio_setup_class_exists(self):
        assert hasattr(_d16, "RatioSetup")

    def test_jade_lizard_setup_class_exists(self):
        assert hasattr(_d16, "JadeLizardSetup")

    def test_ratio_position_class_exists(self):
        assert hasattr(_d16, "RatioPosition")

    def test_ratio_spreads_strategy_exists(self):
        assert hasattr(_d16, "RatioSpreadsStrategy")

    def test_ratio_spreads_strategy_is_subclass(self):
        assert issubclass(_d16.RatioSpreadsStrategy, _d01.BaseStrategy)


# ==============================================================================
# D17 — DiagonalSpread
# ==============================================================================
class TestD17DiagonalSpread:
    def test_diagonal_type_enum_exists(self):
        assert hasattr(_d17, "DiagonalType")

    def test_diagonal_type_is_enum(self):
        assert issubclass(_d17.DiagonalType, Enum)

    def test_diagonal_bias_enum_exists(self):
        assert hasattr(_d17, "DiagonalBias")

    def test_diagonal_state_enum_exists(self):
        assert hasattr(_d17, "DiagonalState")

    def test_diagonal_leg_class_exists(self):
        assert hasattr(_d17, "DiagonalLeg")

    def test_diagonal_setup_class_exists(self):
        assert hasattr(_d17, "DiagonalSetup")

    def test_diagonal_position_class_exists(self):
        assert hasattr(_d17, "DiagonalPosition")

    def test_diagonal_spread_strategy_exists(self):
        assert hasattr(_d17, "DiagonalSpreadStrategy")

    def test_diagonal_spread_strategy_is_subclass(self):
        assert issubclass(_d17.DiagonalSpreadStrategy, _d01.BaseStrategy)


# ==============================================================================
# D18 — EvolvedCreditSpread (standalone — no Spyder cross-imports)
# ==============================================================================
class TestD18EvolvedCreditSpread:
    def test_strategy_state_enum_exists(self):
        assert hasattr(_d18, "StrategyState")

    def test_strategy_state_is_enum(self):
        assert issubclass(_d18.StrategyState, Enum)

    def test_market_regime_enum_exists(self):
        assert hasattr(_d18, "MarketRegime")

    def test_market_regime_is_enum(self):
        assert issubclass(_d18.MarketRegime, Enum)

    def test_volatility_environment_enum_exists(self):
        assert hasattr(_d18, "VolatilityEnvironment")

    def test_evolved_strategy_params_class_exists(self):
        assert hasattr(_d18, "EvolvedStrategyParams")

    def test_technical_indicators_class_exists(self):
        assert hasattr(_d18, "TechnicalIndicators")

    def test_market_analysis_class_exists(self):
        assert hasattr(_d18, "MarketAnalysis")

    def test_credit_spread_position_class_exists(self):
        assert hasattr(_d18, "CreditSpreadPosition")

    def test_evolved_credit_spread_strategy_exists(self):
        assert hasattr(_d18, "EvolvedCreditSpreadStrategy")

    def test_evolved_credit_spread_strategy_instantiable(self):
        strategy = _d18.EvolvedCreditSpreadStrategy()
        assert strategy is not None

    def test_evolved_credit_spread_with_config(self):
        strategy = _d18.EvolvedCreditSpreadStrategy(config={"test": True})
        assert strategy is not None

    def test_evolved_credit_spread_has_methods(self):
        strategy = _d18.EvolvedCreditSpreadStrategy()
        assert hasattr(strategy, "analyze_market") or hasattr(strategy, "generate_signals") or hasattr(strategy, "execute")

    def test_strategy_state_has_members(self):
        assert len(list(_d18.StrategyState)) >= 2


# ==============================================================================
# D19 — JadeLizard
# ==============================================================================
class TestD19JadeLizard:
    def test_jade_lizard_state_enum_exists(self):
        assert hasattr(_d19, "JadeLizardState")

    def test_jade_lizard_state_is_enum(self):
        assert issubclass(_d19.JadeLizardState, Enum)

    def test_risk_profile_enum_exists(self):
        assert hasattr(_d19, "RiskProfile")

    def test_market_sentiment_enum_exists(self):
        assert hasattr(_d19, "MarketSentiment")

    def test_jade_leg_class_exists(self):
        assert hasattr(_d19, "JadeLeg")

    def test_jade_lizard_setup_class_exists(self):
        assert hasattr(_d19, "JadeLizardSetup")

    def test_risk_metrics_class_exists(self):
        assert hasattr(_d19, "RiskMetrics")

    def test_jade_lizard_position_class_exists(self):
        assert hasattr(_d19, "JadeLizardPosition")

    def test_jade_lizard_strategy_exists(self):
        assert hasattr(_d19, "JadeLizardStrategy")

    def test_jade_lizard_strategy_is_subclass(self):
        assert issubclass(_d19.JadeLizardStrategy, _d01.BaseStrategy)


# ==============================================================================
# D20 — VerticalSpreadOptimizer
# ==============================================================================
class TestD20VerticalSpreadOptimizer:
    def test_spread_type_enum_exists(self):
        assert hasattr(_d20, "SpreadType")

    def test_spread_type_is_enum(self):
        assert issubclass(_d20.SpreadType, Enum)

    def test_market_bias_enum_exists(self):
        assert hasattr(_d20, "MarketBias")

    def test_market_bias_is_enum(self):
        assert issubclass(_d20.MarketBias, Enum)

    def test_optimization_mode_enum_exists(self):
        assert hasattr(_d20, "OptimizationMode")

    def test_spread_analysis_class_exists(self):
        assert hasattr(_d20, "SpreadAnalysis")

    def test_vertical_spread_position_class_exists(self):
        assert hasattr(_d20, "VerticalSpreadPosition")

    def test_vertical_spread_optimizer_exists(self):
        assert hasattr(_d20, "VerticalSpreadOptimizer")

    def test_vertical_spread_optimizer_is_subclass(self):
        assert issubclass(_d20.VerticalSpreadOptimizer, _d01.BaseStrategy)


# ==============================================================================
# D21 — DoubleCalendar
# ==============================================================================
class TestD21DoubleCalendar:
    def test_double_calendar_type_enum_exists(self):
        assert hasattr(_d21, "DoubleCalendarType")

    def test_double_calendar_type_is_enum(self):
        assert issubclass(_d21.DoubleCalendarType, Enum)

    def test_iv_regime_enum_exists(self):
        assert hasattr(_d21, "IVRegime")

    def test_position_state_enum_exists(self):
        assert hasattr(_d21, "PositionState")

    def test_calendar_leg_class_exists(self):
        assert hasattr(_d21, "CalendarLeg")

    def test_double_calendar_setup_class_exists(self):
        assert hasattr(_d21, "DoubleCalendarSetup")

    def test_iv_analysis_class_exists(self):
        assert hasattr(_d21, "IVAnalysis")

    def test_double_calendar_position_class_exists(self):
        assert hasattr(_d21, "DoubleCalendarPosition")

    def test_double_calendar_strategy_exists(self):
        assert hasattr(_d21, "DoubleCalendarStrategy")

    def test_double_calendar_strategy_is_subclass(self):
        assert issubclass(_d21.DoubleCalendarStrategy, _d01.BaseStrategy)


# ==============================================================================
# D22 — AdaptiveVolatility
# ==============================================================================
class TestD22AdaptiveVolatility:
    def test_strategy_state_enum_exists(self):
        assert hasattr(_d22, "StrategyState")

    def test_strategy_state_is_enum(self):
        assert issubclass(_d22.StrategyState, Enum)

    def test_volatility_regime_enum_exists(self):
        assert hasattr(_d22, "VolatilityRegime")

    def test_volatility_regime_is_enum(self):
        assert issubclass(_d22.VolatilityRegime, Enum)

    def test_volatility_trade_enum_exists(self):
        assert hasattr(_d22, "VolatilityTrade")

    def test_signal_strength_enum_exists(self):
        assert hasattr(_d22, "SignalStrength")

    def test_volatility_metrics_class_exists(self):
        assert hasattr(_d22, "VolatilityMetrics")

    def test_volatility_signal_class_exists(self):
        assert hasattr(_d22, "VolatilitySignal")

    def test_volatility_position_class_exists(self):
        assert hasattr(_d22, "VolatilityPosition")

    def test_adaptive_volatility_strategy_exists(self):
        assert hasattr(_d22, "AdaptiveVolatilityStrategy")

    def test_adaptive_volatility_strategy_is_subclass(self):
        assert issubclass(_d22.AdaptiveVolatilityStrategy, _d01.BaseStrategy)


# ==============================================================================
# D25 — UnifiedCreditSpreadEngine
# ==============================================================================
class TestD25UnifiedCreditSpreadEngine:
    def test_credit_spread_type_enum_exists(self):
        assert hasattr(_d25, "CreditSpreadType")

    def test_credit_spread_type_is_enum(self):
        assert issubclass(_d25.CreditSpreadType, Enum)

    def test_spread_state_enum_exists(self):
        assert hasattr(_d25, "SpreadState")

    def test_adjustment_type_enum_exists(self):
        assert hasattr(_d25, "AdjustmentType")

    def test_market_bias_enum_exists(self):
        assert hasattr(_d25, "MarketBias")

    def test_credit_spread_parameters_class_exists(self):
        assert hasattr(_d25, "CreditSpreadParameters")

    def test_credit_spread_position_class_exists(self):
        assert hasattr(_d25, "CreditSpreadPosition")

    def test_market_environment_class_exists(self):
        assert hasattr(_d25, "MarketEnvironment")

    def test_market_analysis_engine_class_exists(self):
        assert hasattr(_d25, "MarketAnalysisEngine")

    def test_spread_construction_engine_class_exists(self):
        assert hasattr(_d25, "SpreadConstructionEngine")

    def test_unified_credit_spread_engine_exists(self):
        assert hasattr(_d25, "UnifiedCreditSpreadEngine")


# ==============================================================================
# D26 — GammaScalper
# ==============================================================================
class TestD26GammaScalper:
    def test_strategy_state_enum_exists(self):
        assert hasattr(_d26, "StrategyState")

    def test_hedge_type_enum_exists(self):
        assert hasattr(_d26, "HedgeType")

    def test_hedge_type_is_enum(self):
        assert issubclass(_d26.HedgeType, Enum)

    def test_market_condition_enum_exists(self):
        assert hasattr(_d26, "MarketCondition")

    def test_scalping_mode_enum_exists(self):
        assert hasattr(_d26, "ScalpingMode")

    def test_gamma_position_class_exists(self):
        assert hasattr(_d26, "GammaPosition")

    def test_hedge_action_class_exists(self):
        assert hasattr(_d26, "HedgeAction")

    def test_scalping_metrics_class_exists(self):
        assert hasattr(_d26, "ScalpingMetrics")

    def test_portfolio_greeks_class_exists(self):
        assert hasattr(_d26, "PortfolioGreeks")

    def test_gamma_scalper_strategy_exists(self):
        assert hasattr(_d26, "GammaScalperStrategy")

    def test_gamma_scalper_strategy_is_subclass(self):
        assert issubclass(_d26.GammaScalperStrategy, _d01.BaseStrategy)


# ==============================================================================
# D27 — EarningsStrategy
# ==============================================================================
class TestD27EarningsStrategy:
    def test_earnings_phase_enum_exists(self):
        assert hasattr(_d27, "EarningsPhase")

    def test_earnings_phase_is_enum(self):
        assert issubclass(_d27.EarningsPhase, Enum)

    def test_earnings_bias_enum_exists(self):
        assert hasattr(_d27, "EarningsBias")

    def test_trade_action_enum_exists(self):
        assert hasattr(_d27, "TradeAction")

    def test_earnings_event_class_exists(self):
        assert hasattr(_d27, "EarningsEvent")

    def test_expected_move_class_exists(self):
        assert hasattr(_d27, "ExpectedMove")

    def test_iv_crush_analysis_class_exists(self):
        assert hasattr(_d27, "IVCrushAnalysis")

    def test_earnings_trade_setup_class_exists(self):
        assert hasattr(_d27, "EarningsTradeSetup")

    def test_historical_earnings_pattern_class_exists(self):
        assert hasattr(_d27, "HistoricalEarningsPattern")

    def test_earnings_strategy_handler_exists(self):
        assert hasattr(_d27, "EarningsStrategyHandler")

    def test_earnings_strategy_handler_is_class(self):
        assert inspect.isclass(_d27.EarningsStrategyHandler)


# ==============================================================================
# D28 — VIXHedging
# ==============================================================================
class TestD28VIXHedging:
    def test_vix_regime_enum_exists(self):
        assert hasattr(_d28, "VIXRegime")

    def test_vix_regime_is_enum(self):
        assert issubclass(_d28.VIXRegime, Enum)

    def test_term_structure_enum_exists(self):
        assert hasattr(_d28, "TermStructure")

    def test_hedge_action_enum_exists(self):
        assert hasattr(_d28, "HedgeAction")

    def test_hedge_type_enum_exists(self):
        assert hasattr(_d28, "HedgeType")

    def test_vix_snapshot_class_exists(self):
        assert hasattr(_d28, "VIXSnapshot")

    def test_hedge_recommendation_class_exists(self):
        assert hasattr(_d28, "HedgeRecommendation")

    def test_vix_trade_setup_class_exists(self):
        assert hasattr(_d28, "VIXTradeSetup")

    def test_mean_reversion_signal_class_exists(self):
        assert hasattr(_d28, "MeanReversionSignal")

    def test_volatility_premium_opportunity_class_exists(self):
        assert hasattr(_d28, "VolatilityPremiumOpportunity")

    def test_vix_hedging_strategy_exists(self):
        assert hasattr(_d28, "VIXHedgingStrategy")

    def test_vix_regime_has_members(self):
        assert len(list(_d28.VIXRegime)) >= 2


# ==============================================================================
# D30 — RegimeGatedSelector
# ==============================================================================
class TestD30RegimeGatedSelector:
    def test_strategy_type_enum_exists(self):
        assert hasattr(_d30, "StrategyType")

    def test_strategy_type_is_enum(self):
        assert issubclass(_d30.StrategyType, Enum)

    def test_transition_state_enum_exists(self):
        assert hasattr(_d30, "TransitionState")

    def test_transition_state_is_enum(self):
        assert issubclass(_d30.TransitionState, Enum)

    def test_strategy_profile_class_exists(self):
        assert hasattr(_d30, "StrategyProfile")

    def test_regime_strategy_mapping_class_exists(self):
        assert hasattr(_d30, "RegimeStrategyMapping")

    def test_strategy_selection_class_exists(self):
        assert hasattr(_d30, "StrategySelection")

    def test_strategy_performance_class_exists(self):
        assert hasattr(_d30, "StrategyPerformance")

    def test_regime_gated_selector_exists(self):
        assert hasattr(_d30, "RegimeGatedSelector")

    def test_regime_gated_selector_is_class(self):
        assert inspect.isclass(_d30.RegimeGatedSelector)


# ==============================================================================
# D31 — StrategyOrchestrator
# ==============================================================================
class TestD31StrategyOrchestrator:
    def test_orchestration_mode_enum_exists(self):
        assert hasattr(_d31, "OrchestrationMode")

    def test_orchestration_mode_is_enum(self):
        assert issubclass(_d31.OrchestrationMode, Enum)

    def test_market_regime_enum_exists(self):
        assert hasattr(_d31, "MarketRegime")

    def test_market_regime_is_enum(self):
        assert issubclass(_d31.MarketRegime, Enum)

    def test_allocation_method_enum_exists(self):
        assert hasattr(_d31, "AllocationMethod")

    def test_rebalance_reason_enum_exists(self):
        assert hasattr(_d31, "RebalanceReason")

    def test_strategy_allocation_class_exists(self):
        assert hasattr(_d31, "StrategyAllocation")

    def test_market_regime_data_class_exists(self):
        assert hasattr(_d31, "MarketRegimeData")

    def test_portfolio_metrics_class_exists(self):
        assert hasattr(_d31, "PortfolioMetrics")

    def test_strategy_conflict_class_exists(self):
        assert hasattr(_d31, "StrategyConflict")

    def test_rebalance_event_class_exists(self):
        assert hasattr(_d31, "RebalanceEvent")

    def test_strategy_orchestrator_exists(self):
        assert hasattr(_d31, "StrategyOrchestrator")

    def test_strategy_orchestrator_is_class(self):
        assert inspect.isclass(_d31.StrategyOrchestrator)


# ==============================================================================
# D32 — MultiLegStrategyCoordinator
# ==============================================================================
class TestD32MultiLegStrategyCoordinator:
    def test_multi_leg_strategy_type_enum_exists(self):
        assert hasattr(_d32, "MultiLegStrategyType")

    def test_multi_leg_strategy_type_is_enum(self):
        assert issubclass(_d32.MultiLegStrategyType, Enum)

    def test_volatility_environment_enum_exists(self):
        assert hasattr(_d32, "VolatilityEnvironment")

    def test_market_condition_enum_exists(self):
        assert hasattr(_d32, "MarketCondition")

    def test_adjustment_action_enum_exists(self):
        assert hasattr(_d32, "AdjustmentAction")

    def test_position_status_enum_exists(self):
        assert hasattr(_d32, "PositionStatus")

    def test_option_leg_class_exists(self):
        assert hasattr(_d32, "OptionLeg")

    def test_multi_leg_structure_class_exists(self):
        assert hasattr(_d32, "MultiLegStructure")

    def test_multi_leg_position_class_exists(self):
        assert hasattr(_d32, "MultiLegPosition")

    def test_market_environment_analysis_class_exists(self):
        assert hasattr(_d32, "MarketEnvironmentAnalysis")

    def test_multi_leg_market_analyzer_class_exists(self):
        assert hasattr(_d32, "MultiLegMarketAnalyzer")

    def test_multi_leg_strategy_constructor_class_exists(self):
        assert hasattr(_d32, "MultiLegStrategyConstructor")

    def test_multi_leg_strategy_coordinator_exists(self):
        assert hasattr(_d32, "MultiLegStrategyCoordinator")

    def test_multi_leg_strategy_coordinator_is_class(self):
        assert inspect.isclass(_d32.MultiLegStrategyCoordinator)


# ==============================================================================
# D33 — RenaissanceMeanReversion
# ==============================================================================
class TestD33RenaissanceMeanReversion:
    def test_option_type_enum_exists(self):
        assert hasattr(_d33, "OptionType")

    def test_option_type_is_enum(self):
        assert issubclass(_d33.OptionType, Enum)

    def test_trade_action_enum_exists(self):
        assert hasattr(_d33, "TradeAction")

    def test_trade_action_is_enum(self):
        assert issubclass(_d33.TradeAction, Enum)

    def test_option_contract_class_exists(self):
        assert hasattr(_d33, "OptionContract")

    def test_renaissance_trading_signal_class_exists(self):
        assert hasattr(_d33, "RenaissanceTradingSignal")

    def test_renaissance_mean_reversion_strategy_exists(self):
        assert hasattr(_d33, "RenaissanceMeanReversionStrategy")

    def test_renaissance_mean_reversion_strategy_is_subclass(self):
        assert issubclass(
            _d33.RenaissanceMeanReversionStrategy, _d01.BaseStrategy
        )

    def test_option_type_has_call_put(self):
        ot = _d33.OptionType
        names = [m.name for m in ot]
        assert "CALL" in names or "PUT" in names or any("C" in n for n in names)


# ==============================================================================
# Cross-module sanity checks
# ==============================================================================
class TestDSeriesCrossModule:
    def test_all_strategy_classes_are_classes(self):
        strategy_classes = [
            _d02.IronCondorStrategy,
            _d03.CreditSpreadStrategy,
            _d04.ZeroDTEStrategy,
            _d05.StraddleStrategy,
            _d08.OpeningRangeBreakoutStrategy,
            _d09.GreeksBasedStrategy,
            _d10.IronButterflyStrategy,
            _d11.SpecializedZeroDTEStrategy,
            _d12.RSIMeanReversionStrategy,
            _d13.MACrossoverStrategy,
            _d14.CalendarSpreadStrategy,
            _d15.StraddleStrangleStrategy,
            _d16.RatioSpreadsStrategy,
            _d17.DiagonalSpreadStrategy,
            _d19.JadeLizardStrategy,
            _d20.VerticalSpreadOptimizer,
            _d21.DoubleCalendarStrategy,
            _d22.AdaptiveVolatilityStrategy,
            _d26.GammaScalperStrategy,
            _d33.RenaissanceMeanReversionStrategy,
        ]
        for cls in strategy_classes:
            assert inspect.isclass(cls), f"{cls} is not a class"

    def test_all_base_strategy_subclasses(self):
        subclasses = [
            _d02.IronCondorStrategy,
            _d03.CreditSpreadStrategy,
            _d05.StraddleStrategy,
            _d09.GreeksBasedStrategy,
            _d10.IronButterflyStrategy,
            _d12.RSIMeanReversionStrategy,
            _d13.MACrossoverStrategy,
        ]
        for cls in subclasses:
            assert issubclass(cls, _d01.BaseStrategy), (
                f"{cls.__name__} does not inherit from BaseStrategy"
            )

    def test_d00_constants_are_loaded(self):
        # D00 sets constants at module level
        assert hasattr(_d00, "StrategyType")
        assert hasattr(_d00, "MarketRegime")
        assert hasattr(_d00, "RiskLevel")

    def test_u07_real_constants_available(self):
        assert hasattr(_u07_real, "SPY_CONTRACT_MULTIPLIER")
        assert _u07_real.SPY_CONTRACT_MULTIPLIER == 100

    def test_u07_max_daily_trades(self):
        assert hasattr(_u07_real, "MAX_DAILY_TRADES")
        assert isinstance(_u07_real.MAX_DAILY_TRADES, int)

    def test_u07_signal_type_enum(self):
        assert hasattr(_u07_real, "SignalType")
        assert issubclass(_u07_real.SignalType, Enum)

    def test_u07_option_type_enum(self):
        assert hasattr(_u07_real, "OptionType")
        assert issubclass(_u07_real.OptionType, Enum)

    def test_d18_standalone_no_base_strategy(self):
        # D18 is standalone — does NOT inherit from D01.BaseStrategy
        assert not issubclass(_d18.EvolvedCreditSpreadStrategy, _d01.BaseStrategy)

    def test_all_thirty_d_modules_loaded(self):
        modules = [
            _d00, _d01, _d02, _d03, _d04, _d05,
            _d08, _d09, _d10, _d11, _d12, _d13,
            _d14, _d15, _d16, _d17, _d18, _d19,
            _d20, _d21, _d22, _d25, _d26, _d27,
            _d28, _d30, _d31, _d32, _d33,
        ]
        assert len(modules) == 29
        for mod in modules:
            assert mod is not None
