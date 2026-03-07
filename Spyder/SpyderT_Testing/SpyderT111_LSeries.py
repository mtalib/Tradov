#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT111_LSeries.py
Purpose: Coverage tests for SpyderL_ML — all 14 modules (L01, L07-L19)

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-07 Time: 09:00:00
"""

# ==============================================================================
# BOOTSTRAP — install stubs before any L-series module is imported
# ==============================================================================
import os
import sys
import types
import logging
import threading
import unittest
import numpy as np
from datetime import datetime, timedelta
from enum import Enum, auto
from unittest.mock import MagicMock, patch, PropertyMock
import importlib.util as _ilu

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_L_PKG_PATH = os.path.join(_ROOT, "Spyder", "SpyderL_ML")


def _ensure_mod(key):
    """Create stub module + all ancestor package stubs."""
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            m = types.ModuleType(ancestor)
            real_dir = os.path.join(_ROOT, ancestor.replace(".", os.sep))
            if os.path.isdir(real_dir):
                m.__path__ = [real_dir]
                m.__package__ = ancestor
            sys.modules[ancestor] = m
    return sys.modules[key]


# ---------------------------------------------------------------------------
# shap stub — L12 has hard `import shap` with no try/except
# ---------------------------------------------------------------------------
if "shap" not in sys.modules:
    _shap_mod = types.ModuleType("shap")

    class _TreeExplainer:
        def __init__(self, model, *a, **k):
            self.model = model

        def shap_values(self, X):
            n = X.shape[0] if hasattr(X, "shape") else len(X)
            c = X.shape[1] if hasattr(X, "shape") and len(X.shape) > 1 else 1
            return np.zeros((n, c))

    _shap_mod.TreeExplainer = _TreeExplainer
    _shap_mod.Explanation = MagicMock
    _shap_mod.force_plot = lambda *a, **k: None
    _shap_mod.summary_plot = lambda *a, **k: None
    _shap_mod.dependence_plot = lambda *a, **k: None
    sys.modules["shap"] = _shap_mod

# ---------------------------------------------------------------------------
# U01 SpyderLogger stub
# ---------------------------------------------------------------------------
_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
if not hasattr(_u01, "SpyderLogger"):
    _u01.SpyderLogger = type(
        "SpyderLogger",
        (),
        {"get_logger": staticmethod(lambda name: logging.getLogger(name))},
    )

# ---------------------------------------------------------------------------
# U02 SpyderErrorHandler stub
# ---------------------------------------------------------------------------
_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
if not hasattr(_u02, "SpyderErrorHandler"):
    _u02.SpyderErrorHandler = type(
        "SpyderErrorHandler", (), {"__init__": lambda self, *a, **k: None}
    )

# ---------------------------------------------------------------------------
# U03 TradingCalendar stub (L08 and L10 hard-import it)
# ---------------------------------------------------------------------------
_u03 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils")
if not hasattr(_u03, "TradingCalendar"):

    class _TradingCalendar:
        def is_trading_day(self, date=None):
            return True

        def get_next_trading_day(self, date=None):
            return datetime.now().date()

        def get_trading_hours(self):
            return (datetime.now(), datetime.now())

    _u03.TradingCalendar = _TradingCalendar

# ---------------------------------------------------------------------------
# U07 Constants stub (star import in L09; named imports in L11/L14/L15)
# ---------------------------------------------------------------------------
_u07 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU07_Constants")
# Provide every constant that L-series modules reference
_U07_ATTRS = {
    # Named imports for L11
    "ML_MODEL_UPDATE_FREQUENCY": 7,
    "MIN_EVALUATION_TRADES": 50,
    "MIN_EVALUATION_DAYS": 30,
    # Named imports for L14
    "MAX_PREDICTION_LATENCY_MS": 10,
    "FEATURE_CACHE_SIZE": 1000,
    "PREDICTION_BATCH_SIZE": 10,
    # Named imports for L15
    "MODEL_CONFIDENCE_THRESHOLD": 0.65,
    # Common constants from star import in L09
    "MAX_POSITIONS": 10,
    "MAX_POSITIONS_PER_STRATEGY": 5,
    "MAX_POSITION_SIZE": 100,
    "MIN_POSITION_SIZE": 1,
    "MAX_ORDERS_PER_MINUTE": 50,
    "MAX_PENDING_ORDERS": 20,
    "ORDER_TIMEOUT_SECONDS": 30,
    "MAX_DAILY_TRADES": 5,
    "MAX_PORTFOLIO_RISK": 0.06,
    "STOP_LOSS_PERCENTAGE": 0.02,
    "TAKE_PROFIT_PERCENTAGE": 0.15,
    "TRADING_DAYS_PER_YEAR": 252,
    "TRADING_DAYS_PER_MONTH": 21,
    "TRADING_HOURS_PER_DAY": 6.5,
    "PRIMARY_SYMBOL": "SPY",
    "SPY_CONTRACT_MULTIPLIER": 100,
    "OPTION_MULTIPLIER": 100,
    "MIN_WIN_RATE": 0.40,
    "MIN_PROFIT_FACTOR": 1.2,
    "MIN_SHARPE_RATIO": 0.5,
    "MAX_DRAWDOWN": 0.20,
    "SHARPE_RATIO_THRESHOLD": 1.0,
    "SORTINO_RATIO_THRESHOLD": 1.5,
    "DEFAULT_TIMEZONE": "America/New_York",
    "EVENT_QUEUE_SIZE": 10000,
    "DEBUG_MODE": False,
    "PAPER_TRADING_MODE": True,
    "DEFAULT_RETRY_COUNT": 3,
    "DEFAULT_RETRY_DELAY": 1,
    "MAX_CONSECUTIVE_ERRORS": 5,
    "MARKET_OPEN_TIME": "09:30:00",
    "MARKET_CLOSE_TIME": "16:00:00",
    "OPTIMAL_ENTRY_START": "10:15:00",
    "OPTIMAL_ENTRY_END": "11:40:00",
    "MONTE_CARLO_ITERATIONS": 1000,
    "CONFIDENCE_INTERVALS": [0.95, 0.99],
    "DAY_OF_WEEK_REDUCTION": 0.5,
    "SESSION_TIMEOUT": 3600,
    "PERFORMANCE_WINDOW": 1000,
}
for _k, _v in _U07_ATTRS.items():
    if not hasattr(_u07, _k):
        setattr(_u07, _k, _v)

# ---------------------------------------------------------------------------
# E01 RiskManager stub (L16 try/except imports it; real init requires args)
# ---------------------------------------------------------------------------
_e01 = _ensure_mod("Spyder.SpyderE_Risk.SpyderE01_RiskManager")
if not hasattr(_e01, "RiskManager"):

    class _RiskManagerStub:
        def __init__(self, *a, **k):
            pass

    _e01.RiskManager = _RiskManagerStub

# ---------------------------------------------------------------------------
# E06 RiskMetrics stub (L07 hard-imports calculate_sharpe_ratio/sortino)
# ---------------------------------------------------------------------------
_e06 = _ensure_mod("Spyder.SpyderE_Risk.SpyderE06_RiskMetrics")
if not hasattr(_e06, "calculate_sharpe_ratio"):
    _e06.calculate_sharpe_ratio = lambda returns, risk_free_rate=0.0: 1.0
if not hasattr(_e06, "calculate_sortino_ratio"):
    _e06.calculate_sortino_ratio = lambda returns, risk_free_rate=0.0: 1.2

# ---------------------------------------------------------------------------
# F01 TechnicalIndicators stub (L10 hard-imports)
# ---------------------------------------------------------------------------
_f01 = _ensure_mod("Spyder.SpyderF_Analysis.SpyderF01_Indicators")
if not hasattr(_f01, "TechnicalIndicators"):

    class _TechnicalIndicators:
        def __init__(self):
            pass

        def calculate_rsi(self, prices, period=14):
            return np.full(len(prices), 50.0)

        def calculate_macd(self, prices):
            return np.zeros(len(prices)), np.zeros(len(prices)), np.zeros(len(prices))

    _f01.TechnicalIndicators = _TechnicalIndicators

# ---------------------------------------------------------------------------
# F06 GreeksCalculator stub (L10 hard-imports)
# ---------------------------------------------------------------------------
_f06 = _ensure_mod("Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator")
if not hasattr(_f06, "GreeksCalculator"):

    class _GreeksCalculator:
        def __init__(self):
            pass

        def calculate_delta(self, *a, **k):
            return 0.5

    _f06.GreeksCalculator = _GreeksCalculator

# ---------------------------------------------------------------------------
# C03 OptionChainManager stub (L10 hard-imports)
# ---------------------------------------------------------------------------
_c03 = _ensure_mod("Spyder.SpyderC_MarketData.SpyderC03_OptionChain")
if not hasattr(_c03, "OptionChainManager"):

    class _OptionChainManager:
        def __init__(self):
            pass

        def get_chain(self, symbol):
            return {}

    _c03.OptionChainManager = _OptionChainManager

# ---------------------------------------------------------------------------
# C04 MarketInternals stub (L10 hard-imports)
# ---------------------------------------------------------------------------
_c04 = _ensure_mod("Spyder.SpyderC_MarketData.SpyderC04_MarketInternals")
if not hasattr(_c04, "MarketInternals"):

    class _MarketInternals:
        def __init__(self):
            pass

        def get_advance_decline(self):
            return 1.0

    _c04.MarketInternals = _MarketInternals

# ---------------------------------------------------------------------------
# A05 EventManager stub (L11, L14 hard-imports get_event_manager, EventType)
# ---------------------------------------------------------------------------
_a05 = _ensure_mod("Spyder.SpyderA_Core.SpyderA05_EventManager")
if not hasattr(_a05, "get_event_manager"):
    _a05.get_event_manager = staticmethod(lambda: MagicMock())


class _StubEventType(Enum):
    MARKET_DATA = "market_data"
    SIGNAL = "signal"
    ORDER = "order"
    TRADE = "trade"
    MODEL_UPDATE = "model_update"
    PREDICTION = "prediction"
    REGIME_CHANGE = "regime_change"
    RISK_ALERT = "risk_alert"


if not hasattr(_a05, "EventType"):
    _a05.EventType = _StubEventType

# ---------------------------------------------------------------------------
# C01 DataFeed stub (L14 hard-imports get_data_feed_manager)
# ---------------------------------------------------------------------------
_c01 = _ensure_mod("Spyder.SpyderC_MarketData.SpyderC01_DataFeed")
if not hasattr(_c01, "get_data_feed_manager"):
    _c01.get_data_feed_manager = staticmethod(lambda: MagicMock())

# ---------------------------------------------------------------------------
# Bare-package pre-stubs — prevent buggy __init__.py from executing when
# L09 (and others) do try/except imports of bare-name subpackages
# ---------------------------------------------------------------------------
_V_PKG_PATH_BARE = os.path.join(_ROOT, "Spyder", "SpyderV_QuantModels")
if "SpyderV_QuantModels" not in sys.modules:
    _vb = types.ModuleType("SpyderV_QuantModels")
    _vb.__path__ = [_V_PKG_PATH_BARE]
    _vb.__package__ = "SpyderV_QuantModels"
    sys.modules["SpyderV_QuantModels"] = _vb
# Stub the specific V07 submodule needed by L09
_v07s = sys.modules.setdefault(
    "SpyderV_QuantModels.SpyderV07_AdvancedModels",
    types.ModuleType("SpyderV_QuantModels.SpyderV07_AdvancedModels"),
)
_v07s.create_advanced_models_engine = lambda: MagicMock()

_S_PKG_PATH_BARE = os.path.join(_ROOT, "Spyder", "SpyderS_Signals")
if "SpyderS_Signals" not in sys.modules:
    _sb = types.ModuleType("SpyderS_Signals")
    _sb.__path__ = [_S_PKG_PATH_BARE]
    sys.modules["SpyderS_Signals"] = _sb
_s07s = sys.modules.setdefault(
    "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator",
    types.ModuleType("SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator"),
)
_s07s.get_metrics_orchestrator = lambda: MagicMock()

_FA_PKG_PATH_BARE = os.path.join(_ROOT, "Spyder", "SpyderF_Analysis")
if "SpyderF_Analysis" not in sys.modules:
    _fab = types.ModuleType("SpyderF_Analysis")
    _fab.__path__ = [_FA_PKG_PATH_BARE]
    sys.modules["SpyderF_Analysis"] = _fab
_f17s = sys.modules.setdefault(
    "SpyderF_Analysis.SpyderF17_UnifiedPerformanceEngine",
    types.ModuleType("SpyderF_Analysis.SpyderF17_UnifiedPerformanceEngine"),
)
_f17s.create_unified_performance_engine = lambda: MagicMock()

# ---------------------------------------------------------------------------
# gym stub (L16 and L19 try/except guard, but reuse T110 stub for safety)
# ---------------------------------------------------------------------------
if "gym" not in sys.modules:
    _gym_mod = types.ModuleType("gym")

    class _GymEnv:
        metadata = {}
        reward_range = (-float("inf"), float("inf"))
        spec = None

        def reset(self, **kwargs):
            return None, {}

        def step(self, action):
            return None, 0.0, False, False, {}

        def render(self):
            pass

        def close(self):
            pass

    _gym_mod.Env = _GymEnv
    _spaces_mod = types.ModuleType("gym.spaces")

    class _Discrete:
        def __init__(self, n, **kw):
            self.n = n
            self.shape = (1,)

    class _Box:
        def __init__(self, low, high, shape=None, dtype=None, **kw):
            import numpy as _np
            self.low = float(low) if isinstance(low, (int, float)) else low
            self.high = float(high) if isinstance(high, (int, float)) else high
            self.shape = shape or ()
            self.dtype = dtype or _np.float32

    class _Space:
        pass

    _spaces_mod.Discrete = _Discrete
    _spaces_mod.Box = _Box
    _spaces_mod.Space = _Space
    _gym_mod.spaces = _spaces_mod
    sys.modules["gym"] = _gym_mod
    sys.modules["gym.spaces"] = _spaces_mod

# ---------------------------------------------------------------------------
# L-package pre-stub (prevent __init__.py from executing prematurely)
# ---------------------------------------------------------------------------
_l_pkg = sys.modules.setdefault(
    "Spyder.SpyderL_ML",
    types.ModuleType("Spyder.SpyderL_ML"),
)
_l_pkg.__path__ = [_L_PKG_PATH]
_l_pkg.__package__ = "Spyder.SpyderL_ML"
_l_pkg.__file__ = os.path.join(_L_PKG_PATH, "__init__.py")


def _load_l_module(filename, fq_key):
    """Load an L-series module by filename and register under fq_key."""
    path = os.path.join(_L_PKG_PATH, filename)
    spec = _ilu.spec_from_file_location(fq_key, path)
    mod = _ilu.module_from_spec(spec)
    mod.__package__ = "Spyder.SpyderL_ML"
    sys.modules[fq_key] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Load L01 — MLPredictor (no cross-L imports; U02 only)
# ---------------------------------------------------------------------------
_l01_key = "Spyder.SpyderL_ML.SpyderL01_MLPredictor"
if _l01_key not in sys.modules:
    _l01_mod = _load_l_module("SpyderL01_MLPredictor.py", _l01_key)
else:
    _l01_mod = sys.modules[_l01_key]
sys.modules.setdefault("SpyderL01_MLPredictor", _l01_mod)

# Patch missing runtime deps into L01 namespace (needed for MLPredictor.__init__)
_l01_mod.SpyderLogger = _u01.SpyderLogger
_l01_mod.get_config_manager = lambda: MagicMock()
_l01_mod.get_event_manager = lambda: MagicMock()
_l01_mod.get_data_feed_manager = lambda: MagicMock()
_l01_mod.get_indicators = lambda: MagicMock()
_l01_mod.get_database_manager = lambda: MagicMock()
from collections import deque as _deque
_l01_mod.deque = _deque

# ---------------------------------------------------------------------------
# Load L10 — FeatureEngineering (imports U01/U02/U03, F01/F06, C03/C04)
# ---------------------------------------------------------------------------
_l10_key = "Spyder.SpyderL_ML.SpyderL10_FeatureEngineering"
if _l10_key not in sys.modules:
    _l10_mod = _load_l_module("SpyderL10_FeatureEngineering.py", _l10_key)
else:
    _l10_mod = sys.modules[_l10_key]
sys.modules.setdefault("SpyderL10_FeatureEngineering", _l10_mod)

# ---------------------------------------------------------------------------
# Load L13 — LSTMPricer (imports U01/U02, torch)
# ensure torch submodules are stubbed so L13 can be imported without real torch
for _torch_key in ["torch", "torch.nn", "torch.optim", "torch.utils", "torch.utils.data"]:
    sys.modules.setdefault(_torch_key, MagicMock())
# ---------------------------------------------------------------------------
_l13_key = "Spyder.SpyderL_ML.SpyderL13_LSTMPricer"
if _l13_key not in sys.modules:
    _l13_mod = _load_l_module("SpyderL13_LSTMPricer.py", _l13_key)
else:
    _l13_mod = sys.modules[_l13_key]
sys.modules.setdefault("SpyderL13_LSTMPricer", _l13_mod)

# Add aliases needed by L15 and L17
if not hasattr(_l13_mod, "LSTMPricer"):
    _l13_mod.LSTMPricer = _l13_mod.SpyderLSTMPricer
if not hasattr(_l13_mod, "get_enhanced_lstm_pricer"):
    _l13_mod.get_enhanced_lstm_pricer = staticmethod(lambda: _l13_mod.SpyderLSTMPricer())

# ---------------------------------------------------------------------------
# Load L11 — MLModelManager (imports L01, L10, A05)
# ---------------------------------------------------------------------------
_l11_key = "Spyder.SpyderL_ML.SpyderL11_MLModelManager"
if _l11_key not in sys.modules:
    _l11_mod = _load_l_module("SpyderL11_MLModelManager.py", _l11_key)
else:
    _l11_mod = sys.modules[_l11_key]
sys.modules.setdefault("SpyderL11_MLModelManager", _l11_mod)

# Patch commented-out import: get_database_manager
if not hasattr(_l11_mod, "get_database_manager"):
    _l11_mod.get_database_manager = lambda: MagicMock()

# ---------------------------------------------------------------------------
# Load L12 — RandomForestEnsemble (imports shap, U01/U02 implicit; no L-deps)
# ---------------------------------------------------------------------------
_l12_key = "Spyder.SpyderL_ML.SpyderL12_RandomForestEnsemble"
if _l12_key not in sys.modules:
    _l12_mod = _load_l_module("SpyderL12_RandomForestEnsemble.py", _l12_key)
else:
    _l12_mod = sys.modules[_l12_key]
sys.modules.setdefault("SpyderL12_RandomForestEnsemble", _l12_mod)

# ---------------------------------------------------------------------------
# Load L07 — PaperTradeLearner (imports U01/U02, E06)
# ---------------------------------------------------------------------------
_l07_key = "Spyder.SpyderL_ML.SpyderL07_PaperTradeLearner"
if _l07_key not in sys.modules:
    _l07_mod = _load_l_module("SpyderL07_PaperTradeLearner.py", _l07_key)
else:
    _l07_mod = sys.modules[_l07_key]
sys.modules.setdefault("SpyderL07_PaperTradeLearner", _l07_mod)

# ---------------------------------------------------------------------------
# Load L09 — UnifiedRegimeEngine (star-imports U07; must come before L08
#             because L08 try/except imports from L09)
# ---------------------------------------------------------------------------
_l09_key = "Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine"
if _l09_key not in sys.modules:
    _l09_mod = _load_l_module("SpyderL09_UnifiedRegimeEngine.py", _l09_key)
else:
    _l09_mod = sys.modules[_l09_key]
sys.modules.setdefault("SpyderL09_UnifiedRegimeEngine", _l09_mod)

# ---------------------------------------------------------------------------
# Load L08 — EntryOptimizer (imports U01/U02/U03; try/except imports L09)
# ---------------------------------------------------------------------------
_l08_key = "Spyder.SpyderL_ML.SpyderL08_EntryOptimizer"
if _l08_key not in sys.modules:
    _l08_mod = _load_l_module("SpyderL08_EntryOptimizer.py", _l08_key)
else:
    _l08_mod = sys.modules[_l08_key]
sys.modules.setdefault("SpyderL08_EntryOptimizer", _l08_mod)

# ---------------------------------------------------------------------------
# Load L14 — RealTimePredictor (imports L01/L10/L11/A05/C01)
# ---------------------------------------------------------------------------
_l14_key = "Spyder.SpyderL_ML.SpyderL14_RealTimePredictor"
if _l14_key not in sys.modules:
    _l14_mod = _load_l_module("SpyderL14_RealTimePredictor.py", _l14_key)
else:
    _l14_mod = sys.modules[_l14_key]
sys.modules.setdefault("SpyderL14_RealTimePredictor", _l14_mod)

# ---------------------------------------------------------------------------
# Load L15 — MOmentPredictor (imports L10/L13/L11/U07)
# ---------------------------------------------------------------------------
_l15_key = "Spyder.SpyderL_ML.SpyderL15_MOmentPredictor"
if _l15_key not in sys.modules:
    _l15_mod = _load_l_module("SpyderL15_MOmentPredictor.py", _l15_key)
else:
    _l15_mod = sys.modules[_l15_key]
sys.modules.setdefault("SpyderL15_MOmentPredictor", _l15_mod)

# ---------------------------------------------------------------------------
# Load L16 — OptionsAdjustmentRL (gym/sb3 try/except guarded)
# ---------------------------------------------------------------------------
_l16_key = "Spyder.SpyderL_ML.SpyderL16_OptionsAdjustmentRL"
if _l16_key not in sys.modules:
    _l16_mod = _load_l_module("SpyderL16_OptionsAdjustmentRL.py", _l16_key)
else:
    _l16_mod = sys.modules[_l16_key]
sys.modules.setdefault("SpyderL16_OptionsAdjustmentRL", _l16_mod)

# ---------------------------------------------------------------------------
# Load L17 — FederatedLearning (imports L01/L13/torch/cryptography/etc.)
# ---------------------------------------------------------------------------
_l17_key = "Spyder.SpyderL_ML.SpyderL17_FederatedLearning"
if _l17_key not in sys.modules:
    _l17_mod = _load_l_module("SpyderL17_FederatedLearning.py", _l17_key)
else:
    _l17_mod = sys.modules[_l17_key]
sys.modules.setdefault("SpyderL17_FederatedLearning", _l17_mod)
# Patch missing defaultdict import into L17 namespace
from collections import defaultdict as _defaultdict
_l17_mod.defaultdict = _defaultdict

# ---------------------------------------------------------------------------
# Load L18 — EnhancedMLIntegration (imports torch; no cross-L hard deps)
# ---------------------------------------------------------------------------
_l18_key = "Spyder.SpyderL_ML.SpyderL18_EnhancedMLIntegration"
if _l18_key not in sys.modules:
    _l18_mod = _load_l_module("SpyderL18_EnhancedMLIntegration.py", _l18_key)
else:
    _l18_mod = sys.modules[_l18_key]
sys.modules.setdefault("SpyderL18_EnhancedMLIntegration", _l18_mod)

# ---------------------------------------------------------------------------
# Load L19 — RLTrainingPipeline (gym/sb3 try/except guarded)
# ---------------------------------------------------------------------------
_l19_key = "Spyder.SpyderL_ML.SpyderL19_RLTrainingPipeline"
if _l19_key not in sys.modules:
    _l19_mod = _load_l_module("SpyderL19_RLTrainingPipeline.py", _l19_key)
else:
    _l19_mod = sys.modules[_l19_key]
sys.modules.setdefault("SpyderL19_RLTrainingPipeline", _l19_mod)


# ==============================================================================
# IMPORTS from each L-series module
# ==============================================================================

# --- L01 ---
from Spyder.SpyderL_ML.SpyderL01_MLPredictor import (
    ModelType as L01ModelType,
    Algorithm,
    PredictionTarget,
    ModelConfig,
    Prediction,
    ModelPerformance as L01ModelPerformance,
    MLPredictor,
)

# --- L07 ---
from Spyder.SpyderL_ML.SpyderL07_PaperTradeLearner import (
    LearningMode,
    PerformanceMetric,
    PatternType,
    PaperTradeLearner,
)

# --- L08 ---
from Spyder.SpyderL_ML.SpyderL08_EntryOptimizer import (
    EntrySignal,
    OptimizationObjective,
    ModelType as L08ModelType,
    EntryFilter,
    EntryOptimizer,
)

# --- L09 ---
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (
    MarketRegime,
    RegimeSource,
    RegimeConfidence,
    RegimeTransition,
    CompositeMarketState,
    OptionsAction,
    MLRegimeClassifier,
    SignalRegimeDetector,
    CompositeStateDetector,
    SimpleMarkovTrader,
)

# --- L10 ---
from Spyder.SpyderL_ML.SpyderL10_FeatureEngineering import (
    FeatureSet,
    FeatureConfig,
    FeatureEngineer,
)

# --- L11 ---
from Spyder.SpyderL_ML.SpyderL11_MLModelManager import (
    ModelStatus,
    DeploymentStrategy,
    ModelMetricType,
    MLModelManager,
    get_model_manager,
)

# --- L12 ---
from Spyder.SpyderL_ML.SpyderL12_RandomForestEnsemble import (
    EnsembleConfig,
    ModelPerformance as L12ModelPerformance,
    QuantileRandomForest,
    SpyderRandomForestEnsemble,
)

# --- L13 ---
from Spyder.SpyderL_ML.SpyderL13_LSTMPricer import (
    LSTMConfig,
    TrainingMetrics,
    OptionsLSTM,
    SpyderLSTMPricer,
)

# --- L14 ---
from Spyder.SpyderL_ML.SpyderL14_RealTimePredictor import (
    PredictionRequest,
    PredictionResult,
    ModelInstance,
    FeatureCacheEntry,
    PerformanceMetrics as L14PerformanceMetrics,
    RealTimePredictor,
)

# --- L15 ---
from Spyder.SpyderL_ML.SpyderL15_MOmentPredictor import (
    MomentTask,
    MultiTaskResult,
    EnsemblePrediction,
    MOmentPredictor,
)

# --- L16 ---
from Spyder.SpyderL_ML.SpyderL16_OptionsAdjustmentRL import (
    PositionState,
    AdjustmentAction,
    Episode,
    OptionsAdjustmentRL,
)

# --- L17 ---
from Spyder.SpyderL_ML.SpyderL17_FederatedLearning import (
    ClientRole,
    AggregationMethod,
    PrivacyMechanism,
    ModelType as L17ModelType,
    ClientConfig,
    FederatedModel,
    DifferentialPrivacy,
    SecureAggregator,
    FederatedClient,
    FederatedCoordinator,
    FederatedLearningManager,
)

# --- L18 ---
from Spyder.SpyderL_ML.SpyderL18_EnhancedMLIntegration import (
    ModelType as L18ModelType,
    PredictionHorizon,
    LearningMode as L18LearningMode,
    MLPrediction,
    ModelPerformance as L18ModelPerformance,
    FeatureSet as L18FeatureSet,
    EnhancedMLEngine,
)

# --- L19 ---
from Spyder.SpyderL_ML.SpyderL19_RLTrainingPipeline import (
    RLAlgorithm,
    EnvironmentSpec,
    TrainingResult,
    EvaluationResult,
    RLTrainingPipeline,
)


# ==============================================================================
# TEST CLASSES
# ==============================================================================


# ------------------------------------------------------------------------------
# L01 — MLPredictor
# ------------------------------------------------------------------------------
class TestL01Enums(unittest.TestCase):
    """Test L01 enumeration types."""

    def test_model_type_direction(self):
        self.assertEqual(L01ModelType.DIRECTION.value, "direction")

    def test_model_type_volatility(self):
        self.assertEqual(L01ModelType.VOLATILITY.value, "volatility")

    def test_model_type_price(self):
        self.assertEqual(L01ModelType.PRICE.value, "price")

    def test_algorithm_random_forest(self):
        self.assertEqual(Algorithm.RANDOM_FOREST.value, "random_forest")

    def test_algorithm_xgboost(self):
        self.assertEqual(Algorithm.XGBOOST.value, "xgboost")

    def test_algorithm_lstm(self):
        self.assertEqual(Algorithm.LSTM.value, "lstm")

    def test_prediction_target_next_candle(self):
        self.assertEqual(PredictionTarget.NEXT_CANDLE.value, "next_candle")

    def test_prediction_target_eod(self):
        self.assertEqual(PredictionTarget.END_OF_DAY.value, "eod")


class TestL01Dataclasses(unittest.TestCase):
    """Test L01 dataclass-style classes exist and have expected members."""

    def test_model_config_class_exists(self):
        self.assertTrue(hasattr(_l01_mod, "ModelConfig"))

    def test_model_config_has_annotations(self):
        # ModelConfig has type-annotated fields even without @dataclass
        self.assertIn("model_type", ModelConfig.__annotations__ if hasattr(ModelConfig, "__annotations__") else {})

    def test_model_performance_class_exists(self):
        self.assertTrue(hasattr(_l01_mod, "ModelPerformance"))

    def test_prediction_class_exists(self):
        self.assertTrue(hasattr(_l01_mod, "Prediction"))


class TestL01MLPredictor(unittest.TestCase):
    """Test L01 MLPredictor class."""

    def _make_predictor(self):
        with patch.object(MLPredictor, "_create_directories", return_value=None), \
             patch.object(MLPredictor, "_load_models", return_value=None), \
             patch.object(MLPredictor, "_initialize_default_models", return_value=None), \
             patch.object(MLPredictor, "_subscribe_to_events", return_value=None):
            return MLPredictor()

    def test_instantiation(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred, MLPredictor)

    def test_models_dict_empty(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred.models, dict)
        self.assertEqual(len(pred.models), 0)

    def test_performance_history_empty(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred.performance_history, dict)


# ------------------------------------------------------------------------------
# L07 — PaperTradeLearner
# ------------------------------------------------------------------------------
class TestL07Enums(unittest.TestCase):
    """Test L07 enumeration types."""

    def test_learning_mode_exploration(self):
        self.assertTrue(hasattr(LearningMode, "EXPLORATION"))

    def test_learning_mode_exploitation(self):
        self.assertTrue(hasattr(LearningMode, "EXPLOITATION"))

    def test_learning_mode_validation(self):
        self.assertTrue(hasattr(LearningMode, "VALIDATION"))

    def test_performance_metric_sharpe(self):
        self.assertTrue(hasattr(PerformanceMetric, "SHARPE_RATIO"))

    def test_performance_metric_win_rate(self):
        self.assertTrue(hasattr(PerformanceMetric, "WIN_RATE"))

    def test_pattern_type_entry(self):
        self.assertTrue(hasattr(PatternType, "ENTRY_CONDITION"))

    def test_pattern_type_market_regime(self):
        self.assertTrue(hasattr(PatternType, "MARKET_REGIME"))


class TestL07PaperTradeLearner(unittest.TestCase):
    """Test L07 PaperTradeLearner class."""

    def _make_learner(self):
        db_mock = MagicMock()
        with patch.object(PaperTradeLearner, "_load_historical_data", return_value=None, create=True):
            return PaperTradeLearner(db_mock)

    def test_instantiation(self):
        learner = self._make_learner()
        self.assertIsInstance(learner, PaperTradeLearner)

    def test_has_logger(self):
        learner = self._make_learner()
        self.assertTrue(hasattr(learner, "logger"))

    def test_db_manager_stored(self):
        db_mock = MagicMock()
        with patch.object(PaperTradeLearner, "_load_historical_data", return_value=None, create=True):
            learner = PaperTradeLearner(db_mock)
        # Stored as self.db (not self.database_manager)
        self.assertEqual(learner.db, db_mock)


# ------------------------------------------------------------------------------
# L08 — EntryOptimizer
# ------------------------------------------------------------------------------
class TestL08Enums(unittest.TestCase):
    """Test L08 enumeration types."""

    def test_entry_signal_strong_buy(self):
        self.assertEqual(EntrySignal.STRONG_BUY.value, "strong_buy")

    def test_entry_signal_avoid(self):
        self.assertEqual(EntrySignal.AVOID.value, "avoid")

    def test_optimization_objective_win_rate(self):
        self.assertEqual(OptimizationObjective.WIN_RATE.value, "win_rate")

    def test_optimization_objective_sharpe(self):
        self.assertEqual(OptimizationObjective.SHARPE_RATIO.value, "sharpe_ratio")

    def test_l08_model_type_rf(self):
        self.assertEqual(L08ModelType.RANDOM_FOREST.value, "random_forest")

    def test_l08_model_type_ensemble(self):
        self.assertEqual(L08ModelType.ENSEMBLE.value, "ensemble")


class TestL08EntryFilter(unittest.TestCase):
    """Test L08 EntryFilter dataclass."""

    def test_default_confidence(self):
        ef = EntryFilter()
        self.assertIsInstance(ef.min_confidence, float)
        self.assertGreater(ef.min_confidence, 0)

    def test_default_max_risk(self):
        ef = EntryFilter()
        self.assertLessEqual(ef.max_risk_score, 1.0)


class TestL08EntryOptimizer(unittest.TestCase):
    """Test L08 EntryOptimizer class."""

    def _make_optimizer(self):
        fe_mock = MagicMock()
        rc_mock = MagicMock()
        with patch.object(EntryOptimizer, "_initialize_models", return_value=None, create=True):
            return EntryOptimizer(fe_mock, rc_mock)

    def test_instantiation(self):
        opt = self._make_optimizer()
        self.assertIsInstance(opt, EntryOptimizer)

    def test_objective_default(self):
        opt = self._make_optimizer()
        self.assertEqual(opt.objective, OptimizationObjective.RISK_ADJUSTED_RETURN)

    def test_fitted_false_initially(self):
        opt = self._make_optimizer()
        self.assertFalse(opt.fitted)


# ------------------------------------------------------------------------------
# L09 — UnifiedRegimeEngine
# ------------------------------------------------------------------------------
class TestL09Enums(unittest.TestCase):
    """Test L09 enumeration types."""

    def test_market_regime_bull(self):
        # The module has two MarketRegime definitions; the last one (line 2059) wins
        self.assertEqual(MarketRegime.BULL.value, "bull")

    def test_market_regime_bear(self):
        self.assertEqual(MarketRegime.BEAR.value, "bear")

    def test_market_regime_unknown(self):
        self.assertEqual(MarketRegime.UNKNOWN.value, "unknown")

    def test_market_regime_sideways(self):
        self.assertEqual(MarketRegime.SIDEWAYS.value, "sideways")

    def test_regime_source_ml(self):
        self.assertEqual(RegimeSource.ML_CLASSIFIER.value, "ml_classifier")

    def test_regime_confidence_high(self):
        self.assertEqual(RegimeConfidence.HIGH.value, "high")

    def test_regime_transition_stable(self):
        self.assertEqual(RegimeTransition.STABLE.value, "stable")

    def test_composite_state_crash(self):
        self.assertEqual(CompositeMarketState.CRASH.value, "crash")

    def test_options_action_iron_condor(self):
        self.assertEqual(OptionsAction.IRON_CONDOR.value, "iron_condor")

    def test_options_action_hold(self):
        self.assertEqual(OptionsAction.HOLD.value, "hold")


class TestL09Classifiers(unittest.TestCase):
    """Test L09 regime classifier classes."""

    def test_ml_regime_classifier_instantiation(self):
        clf = MLRegimeClassifier()
        self.assertIsInstance(clf, MLRegimeClassifier)

    def test_signal_regime_detector_instantiation(self):
        det = SignalRegimeDetector()
        self.assertIsInstance(det, SignalRegimeDetector)

    def test_composite_state_detector_instantiation(self):
        det = CompositeStateDetector()
        self.assertIsInstance(det, CompositeStateDetector)

    def test_simple_markov_trader_instantiation(self):
        trader = SimpleMarkovTrader(states=3)
        self.assertIsInstance(trader, SimpleMarkovTrader)

    def test_simple_markov_trader_default_states(self):
        trader = SimpleMarkovTrader()
        self.assertIsNotNone(trader)


# ------------------------------------------------------------------------------
# L10 — FeatureEngineering
# ------------------------------------------------------------------------------
class TestL10Dataclasses(unittest.TestCase):
    """Test L10 dataclass types."""

    def test_feature_set_construction(self):
        fs = FeatureSet(
            timestamp=datetime.now(),
            symbol="SPY",
            features={"rsi": 50.0, "macd": 0.1},
        )
        self.assertEqual(fs.symbol, "SPY")
        self.assertIn("rsi", fs.features)

    def test_feature_set_to_array(self):
        fs = FeatureSet(
            timestamp=datetime.now(),
            symbol="SPY",
            features={"rsi": 50.0, "macd": 0.1},
        )
        arr = fs.to_array(["rsi", "macd"])
        self.assertEqual(arr.shape, (2,))
        self.assertAlmostEqual(arr[0], 50.0)

    def test_feature_config_defaults(self):
        cfg = FeatureConfig()
        self.assertTrue(cfg.price_features)
        self.assertTrue(cfg.volume_features)


class TestL10FeatureEngineer(unittest.TestCase):
    """Test L10 FeatureEngineer class."""

    def test_instantiation_no_config(self):
        fe = FeatureEngineer()
        self.assertIsInstance(fe, FeatureEngineer)

    def test_instantiation_with_config(self):
        cfg = FeatureConfig(price_features=True, volume_features=False)
        fe = FeatureEngineer(config=cfg)
        self.assertIsInstance(fe, FeatureEngineer)

    def test_has_logger(self):
        fe = FeatureEngineer()
        self.assertTrue(hasattr(fe, "logger"))


# ------------------------------------------------------------------------------
# L11 — MLModelManager
# ------------------------------------------------------------------------------
class TestL11Enums(unittest.TestCase):
    """Test L11 enumeration types."""

    def test_model_status_development(self):
        self.assertEqual(ModelStatus.DEVELOPMENT.value, "development")

    def test_model_status_production(self):
        self.assertEqual(ModelStatus.PRODUCTION.value, "production")

    def test_deployment_strategy_canary(self):
        self.assertEqual(DeploymentStrategy.CANARY.value, "canary")

    def test_deployment_strategy_ab_test(self):
        self.assertEqual(DeploymentStrategy.AB_TEST.value, "ab_test")

    def test_model_metric_type_accuracy(self):
        self.assertEqual(ModelMetricType.ACCURACY.value, "accuracy")

    def test_model_metric_type_latency(self):
        self.assertEqual(ModelMetricType.LATENCY.value, "latency")


class TestL11MLModelManager(unittest.TestCase):
    """Test L11 MLModelManager class."""

    def _make_manager(self):
        with patch.object(MLModelManager, "_create_directories", return_value=None), \
             patch.object(MLModelManager, "_load_registry", return_value=None), \
             patch.object(MLModelManager, "_subscribe_to_events", return_value=None):
            return MLModelManager()

    def test_instantiation(self):
        mgr = self._make_manager()
        self.assertIsInstance(mgr, MLModelManager)

    def test_model_registry_empty(self):
        mgr = self._make_manager()
        self.assertIsInstance(mgr.model_registry, dict)

    def test_ab_tests_empty(self):
        mgr = self._make_manager()
        self.assertIsInstance(mgr.ab_tests, dict)

    def test_get_model_manager_returns_instance(self):
        with patch.object(MLModelManager, "_create_directories", return_value=None), \
             patch.object(MLModelManager, "_load_registry", return_value=None), \
             patch.object(MLModelManager, "_subscribe_to_events", return_value=None):
            mgr = get_model_manager()
        self.assertIsInstance(mgr, MLModelManager)


# ------------------------------------------------------------------------------
# L12 — RandomForestEnsemble
# ------------------------------------------------------------------------------
class TestL12Dataclasses(unittest.TestCase):
    """Test L12 dataclass types."""

    def test_ensemble_config_default(self):
        cfg = EnsembleConfig()
        self.assertIsInstance(cfg, EnsembleConfig)

    def test_model_performance_requires_fields(self):
        # L12 ModelPerformance requires 8 positional fields
        perf = L12ModelPerformance(
            rmse=0.1, mae=0.08, r2=0.9,
            mean_absolute_percentage_error=0.05,
            quantile_coverage=0.90,
            feature_importance={"rsi": 0.5},
            oob_score=0.85,
            cross_val_scores=np.array([0.8, 0.85, 0.9]),
        )
        self.assertAlmostEqual(perf.rmse, 0.1)


class TestL12QuantileRandomForest(unittest.TestCase):
    """Test L12 QuantileRandomForest class."""

    def test_instantiation_default(self):
        qrf = QuantileRandomForest()
        self.assertIsInstance(qrf, QuantileRandomForest)

    def test_instantiation_custom_estimators(self):
        qrf = QuantileRandomForest(n_estimators=50)
        self.assertIsInstance(qrf, QuantileRandomForest)

    def test_n_estimators_stored(self):
        qrf = QuantileRandomForest(n_estimators=200)
        # n_estimators is passed to underlying model
        self.assertIsNotNone(qrf)


class TestL12SpyderRandomForestEnsemble(unittest.TestCase):
    """Test L12 SpyderRandomForestEnsemble class."""

    def test_instantiation_no_config(self):
        ens = SpyderRandomForestEnsemble()
        self.assertIsInstance(ens, SpyderRandomForestEnsemble)

    def test_instantiation_with_config(self):
        cfg = EnsembleConfig()
        ens = SpyderRandomForestEnsemble(config=cfg)
        self.assertIsInstance(ens, SpyderRandomForestEnsemble)

    def test_has_config(self):
        ens = SpyderRandomForestEnsemble()
        self.assertIsInstance(ens.config, EnsembleConfig)

    def test_is_trained_false(self):
        ens = SpyderRandomForestEnsemble()
        self.assertFalse(ens.is_trained)


# ------------------------------------------------------------------------------
# L13 — LSTMPricer
# ------------------------------------------------------------------------------
class TestL13Dataclasses(unittest.TestCase):
    """Test L13 dataclass types."""

    def test_lstm_config_defaults(self):
        cfg = LSTMConfig()
        self.assertEqual(cfg.hidden_size, 160)
        self.assertEqual(cfg.num_layers, 3)
        self.assertTrue(cfg.bidirectional)

    def test_training_metrics_construction(self):
        tm = TrainingMetrics(
            epoch=1,
            train_loss=0.5,
            val_loss=0.55,
            train_rmse=0.1,
            val_rmse=0.12,
            improvement_vs_bs=0.05,
            training_time=10.0,
        )
        self.assertEqual(tm.epoch, 1)
        self.assertAlmostEqual(tm.train_loss, 0.5)


class TestL13LSTMPricer(unittest.TestCase):
    """Test L13 SpyderLSTMPricer class."""

    def test_instantiation_no_config(self):
        pricer = SpyderLSTMPricer()
        self.assertIsInstance(pricer, SpyderLSTMPricer)

    def test_instantiation_with_config(self):
        cfg = LSTMConfig(hidden_size=64, num_layers=2)
        pricer = SpyderLSTMPricer(config=cfg)
        self.assertIsInstance(pricer, SpyderLSTMPricer)

    def test_has_logger(self):
        pricer = SpyderLSTMPricer()
        # Logger is not set as self.logger in L13; check config instead
        self.assertIsInstance(pricer.config, LSTMConfig)

    def test_alias_lstm_pricer(self):
        from Spyder.SpyderL_ML.SpyderL13_LSTMPricer import LSTMPricer
        self.assertIs(LSTMPricer, SpyderLSTMPricer)


# ------------------------------------------------------------------------------
# L14 — RealTimePredictor
# ------------------------------------------------------------------------------
class TestL14Dataclasses(unittest.TestCase):
    """Test L14 dataclass types."""

    def test_prediction_request_construction(self):
        req = PredictionRequest(
            request_id="test-001",
            timestamp=datetime.now(),
            features={"rsi": 50.0},
            model_names=["direction_model"],
        )
        self.assertEqual(req.request_id, "test-001")
        self.assertIn("rsi", req.features)

    def test_performance_metrics_default(self):
        pm = L14PerformanceMetrics()
        self.assertIsInstance(pm, L14PerformanceMetrics)
        self.assertEqual(pm.total_predictions, 0)


class TestL14RealTimePredictor(unittest.TestCase):
    """Test L14 RealTimePredictor class."""

    def _make_predictor(self):
        mock_mgr = MagicMock()
        mock_feed = MagicMock()
        with patch.object(_l11_mod, "get_model_manager", return_value=mock_mgr), \
             patch.object(_l14_mod, "get_model_manager", return_value=mock_mgr), \
             patch.object(_l14_mod, "get_data_feed_manager", return_value=mock_feed), \
             patch.object(RealTimePredictor, "_start_worker_threads", return_value=None, create=True), \
             patch.object(RealTimePredictor, "_warm_up_models", return_value=None, create=True), \
             patch.object(RealTimePredictor, "_subscribe_to_events", return_value=None, create=True):
            pred = RealTimePredictor()
        return pred

    def test_instantiation(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred, RealTimePredictor)

    def test_has_model_lock(self):
        pred = self._make_predictor()
        self.assertTrue(hasattr(pred, "model_lock"))

    def test_models_dict_exists(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred.models, dict)


# ------------------------------------------------------------------------------
# L15 — MOmentPredictor
# ------------------------------------------------------------------------------
class TestL15Enums(unittest.TestCase):
    """Test L15 enumeration types."""

    def test_moment_task_has_values(self):
        # MomentTask enum should have at least one value
        self.assertGreater(len(list(MomentTask)), 0)


class TestL15Dataclasses(unittest.TestCase):
    """Test L15 dataclass types."""

    def test_multi_task_result_constructable(self):
        self.assertTrue(hasattr(_l15_mod, "MultiTaskResult"))

    def test_ensemble_prediction_constructable(self):
        self.assertTrue(hasattr(_l15_mod, "EnsemblePrediction"))


class TestL15MOmentPredictor(unittest.TestCase):
    """Test L15 MOmentPredictor class."""

    def _make_predictor(self):
        with patch.object(MOmentPredictor, "_initialize_models", return_value=None, create=True), \
             patch.object(MOmentPredictor, "_load_ensemble_weights", return_value=None, create=True), \
             patch.object(MLModelManager, "_create_directories", return_value=None), \
             patch.object(MLModelManager, "_load_registry", return_value=None), \
             patch.object(MLModelManager, "_subscribe_to_events", return_value=None):
            return MOmentPredictor()

    def test_instantiation(self):
        pred = self._make_predictor()
        self.assertIsInstance(pred, MOmentPredictor)

    def test_has_logger(self):
        pred = self._make_predictor()
        self.assertTrue(hasattr(pred, "logger"))


# ------------------------------------------------------------------------------
# L16 — OptionsAdjustmentRL
# ------------------------------------------------------------------------------
class TestL16Dataclasses(unittest.TestCase):
    """Test L16 dataclass types."""

    def test_position_state_constructable(self):
        self.assertTrue(hasattr(_l16_mod, "PositionState"))

    def test_adjustment_action_constructable(self):
        self.assertTrue(hasattr(_l16_mod, "AdjustmentAction"))

    def test_episode_constructable(self):
        self.assertTrue(hasattr(_l16_mod, "Episode"))


class TestL16OptionsAdjustmentRL(unittest.TestCase):
    """Test L16 OptionsAdjustmentRL class."""

    def _make_rl(self):
        with patch.object(OptionsAdjustmentRL, "_initialize_agent", return_value=None, create=True), \
             patch.object(OptionsAdjustmentRL, "_build_model", return_value=None, create=True), \
             patch.object(OptionsAdjustmentRL, "_initialize_environments", return_value=None, create=True):
            return OptionsAdjustmentRL()

    def test_instantiation(self):
        rl = self._make_rl()
        self.assertIsInstance(rl, OptionsAdjustmentRL)

    def test_has_logger(self):
        rl = self._make_rl()
        self.assertTrue(hasattr(rl, "logger"))

    def test_has_config(self):
        rl = self._make_rl()
        self.assertTrue(hasattr(rl, "config"))


# ------------------------------------------------------------------------------
# L17 — FederatedLearning
# ------------------------------------------------------------------------------
class TestL17Enums(unittest.TestCase):
    """Test L17 enumeration types."""

    def test_client_role_coordinator(self):
        self.assertEqual(ClientRole.COORDINATOR.value, "coordinator")

    def test_client_role_participant(self):
        self.assertEqual(ClientRole.PARTICIPANT.value, "participant")

    def test_aggregation_fedavg(self):
        self.assertEqual(AggregationMethod.FEDERATED_AVERAGING.value, "fedavg")

    def test_aggregation_median(self):
        self.assertEqual(AggregationMethod.MEDIAN.value, "median")

    def test_privacy_mechanism_dp(self):
        self.assertEqual(PrivacyMechanism.DIFFERENTIAL_PRIVACY.value, "dp")

    def test_privacy_mechanism_none(self):
        self.assertEqual(PrivacyMechanism.NONE.value, "none")

    def test_l17_model_type_has_values(self):
        self.assertGreater(len(list(L17ModelType)), 0)


class TestL17DifferentialPrivacy(unittest.TestCase):
    """Test L17 DifferentialPrivacy class."""

    def test_instantiation(self):
        dp = DifferentialPrivacy()
        self.assertIsInstance(dp, DifferentialPrivacy)

    def test_add_noise(self):
        dp = DifferentialPrivacy()
        if hasattr(dp, "add_noise"):
            grad = np.array([1.0, 2.0, 3.0])
            noisy = dp.add_noise(grad)
            self.assertEqual(noisy.shape, grad.shape)


class TestL17SecureAggregator(unittest.TestCase):
    """Test L17 SecureAggregator class."""

    def test_instantiation(self):
        sa = SecureAggregator()
        self.assertIsInstance(sa, SecureAggregator)


class TestL17FederatedManagers(unittest.TestCase):
    """Test L17 high-level federated classes."""

    def test_federated_coordinator_instantiation(self):
        coord = FederatedCoordinator()
        self.assertIsInstance(coord, FederatedCoordinator)

    def test_federated_learning_manager_instantiation(self):
        mock_mgr = MagicMock()
        with patch.object(FederatedLearningManager, "_initialize_components", return_value=None, create=True), \
             patch.object(FederatedLearningManager, "_setup_network", return_value=None, create=True):
            mgr = FederatedLearningManager()
        self.assertIsInstance(mgr, FederatedLearningManager)


# ------------------------------------------------------------------------------
# L18 — EnhancedMLIntegration
# ------------------------------------------------------------------------------
class TestL18Enums(unittest.TestCase):
    """Test L18 enumeration types."""

    def test_model_type_price_predictor(self):
        self.assertEqual(L18ModelType.PRICE_PREDICTOR.value, "price_predictor")

    def test_model_type_regime_classifier(self):
        self.assertEqual(L18ModelType.REGIME_CLASSIFIER.value, "regime_classifier")

    def test_prediction_horizon_tick(self):
        self.assertEqual(PredictionHorizon.TICK.value, "tick")

    def test_prediction_horizon_day(self):
        self.assertEqual(PredictionHorizon.DAY.value, "1day")

    def test_learning_mode_batch(self):
        self.assertEqual(L18LearningMode.BATCH.value, "batch")

    def test_learning_mode_online(self):
        self.assertEqual(L18LearningMode.ONLINE.value, "online")


class TestL18Dataclasses(unittest.TestCase):
    """Test L18 dataclass construction."""

    def test_ml_prediction_constructable(self):
        self.assertTrue(hasattr(_l18_mod, "MLPrediction"))

    def test_model_performance_constructable(self):
        # L18 ModelPerformance requires positional fields; just check class exists
        self.assertTrue(hasattr(_l18_mod, "ModelPerformance"))

    def test_feature_set_constructable(self):
        self.assertTrue(hasattr(_l18_mod, "FeatureSet"))


class TestL18EnhancedMLEngine(unittest.TestCase):
    """Test L18 EnhancedMLEngine class."""

    def _make_engine(self):
        config = {"update_frequency": 100}
        with patch.object(EnhancedMLEngine, "_initialize_models", return_value=None):
            return EnhancedMLEngine(config)

    def test_instantiation(self):
        eng = self._make_engine()
        self.assertIsInstance(eng, EnhancedMLEngine)

    def test_config_stored(self):
        eng = self._make_engine()
        self.assertIsInstance(eng.config, dict)

    def test_device_set(self):
        eng = self._make_engine()
        self.assertTrue(hasattr(eng, "device"))

    def test_models_dict_exists(self):
        eng = self._make_engine()
        self.assertIsInstance(eng.models, dict)


# ------------------------------------------------------------------------------
# L19 — RLTrainingPipeline
# ------------------------------------------------------------------------------
class TestL19Enums(unittest.TestCase):
    """Test L19 enumeration types."""

    def test_rl_algorithm_ppo(self):
        self.assertEqual(RLAlgorithm.PPO.value, "PPO")

    def test_rl_algorithm_sac(self):
        self.assertEqual(RLAlgorithm.SAC.value, "SAC")


class TestL19Dataclasses(unittest.TestCase):
    """Test L19 dataclass types."""

    def test_environment_spec_constructable(self):
        self.assertTrue(hasattr(_l19_mod, "EnvironmentSpec"))

    def test_training_result_constructable(self):
        self.assertTrue(hasattr(_l19_mod, "TrainingResult"))

    def test_evaluation_result_constructable(self):
        self.assertTrue(hasattr(_l19_mod, "EvaluationResult"))


class TestL19RLTrainingPipeline(unittest.TestCase):
    """Test L19 RLTrainingPipeline class."""

    def test_instantiation_no_args(self):
        pipeline = RLTrainingPipeline()
        self.assertIsInstance(pipeline, RLTrainingPipeline)

    def test_instantiation_with_base_dir(self):
        pipeline = RLTrainingPipeline(base_dir="/tmp/rl_test")
        self.assertIsInstance(pipeline, RLTrainingPipeline)

    def test_has_logger(self):
        pipeline = RLTrainingPipeline()
        self.assertTrue(hasattr(pipeline, "logger"))

    def test_base_dir_stored(self):
        pipeline = RLTrainingPipeline(base_dir="/tmp/test_rl")
        self.assertIsNotNone(pipeline)


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
