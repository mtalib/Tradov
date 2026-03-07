#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT110_VSeries.py
Purpose: Coverage tests for SpyderV_QuantModels — all 8 modules (V01-V08)

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-07 Time: 07:00:00
"""

# ==============================================================================
# BOOTSTRAP — install stubs before any V-series module is imported
# ==============================================================================
import os
import sys
import types
import logging
import threading
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
import importlib.util as _ilu

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_V_PKG_PATH = os.path.join(_ROOT, "Spyder", "SpyderV_QuantModels")


def _ensure_mod(key):
    """Create stub module + all ancestor package stubs."""
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            sys.modules[ancestor] = types.ModuleType(ancestor)
    return sys.modules[key]


# ---------------------------------------------------------------------------
# U01/U02 stubs  (V07 hard-imports SpyderLogger / SpyderErrorHandler)
# ---------------------------------------------------------------------------
_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
if not hasattr(_u01, "SpyderLogger"):
    _u01.SpyderLogger = type(
        "SpyderLogger",
        (),
        {"get_logger": staticmethod(lambda name: logging.getLogger(name))},
    )

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
if not hasattr(_u02, "SpyderErrorHandler"):
    _u02.SpyderErrorHandler = type("SpyderErrorHandler", (), {"__init__": lambda self, *a, **k: None})

# ---------------------------------------------------------------------------
# gym stub  (V08 does: import gym; from gym import spaces)
# ---------------------------------------------------------------------------
if "gym" not in sys.modules:
    _gym_mod = types.ModuleType("gym")

    class _GymEnv:
        """Minimal gym.Env stub."""
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

    # gym.spaces stub
    _spaces_mod = types.ModuleType("gym.spaces")

    class _Discrete:
        def __init__(self, n, **kw):
            self.n = n

    class _Box:
        def __init__(self, low, high, shape=None, dtype=None, **kw):
            self.low = low
            self.high = high
            self.shape = shape or ()

    class _Space:
        pass

    _spaces_mod.Discrete = _Discrete
    _spaces_mod.Box = _Box
    _spaces_mod.Space = _Space
    _gym_mod.spaces = _spaces_mod
    sys.modules["gym"] = _gym_mod
    sys.modules["gym.spaces"] = _spaces_mod

# ---------------------------------------------------------------------------
# V-package pre-stub (prevent __init__.py from executing before our modules
# are individually loaded — __init__.py tries wrong class names)
# ---------------------------------------------------------------------------
_v_pkg = sys.modules.setdefault(
    "Spyder.SpyderV_QuantModels",
    types.ModuleType("Spyder.SpyderV_QuantModels"),
)
_v_pkg.__path__ = [_V_PKG_PATH]
_v_pkg.__package__ = "Spyder.SpyderV_QuantModels"
_v_pkg.__file__ = os.path.join(_V_PKG_PATH, "__init__.py")


def _load_v_module(filename, fq_key):
    """Load a V-series module by filename and register under fq_key."""
    path = os.path.join(_V_PKG_PATH, filename)
    spec = _ilu.spec_from_file_location(fq_key, path)
    mod = _ilu.module_from_spec(spec)
    mod.__package__ = "Spyder.SpyderV_QuantModels"
    sys.modules[fq_key] = mod
    spec.loader.exec_module(mod)
    return mod


# Load V04 and V05 first (V01 imports them by bare name at module level)
_v04_key = "Spyder.SpyderV_QuantModels.SpyderV04_RiskManager"
if _v04_key not in sys.modules:
    _v04_mod = _load_v_module("SpyderV04_RiskManager.py", _v04_key)
else:
    _v04_mod = sys.modules[_v04_key]
# Register under bare name so V01 can find it
sys.modules.setdefault("SpyderV04_RiskManager", _v04_mod)

_v05_key = "Spyder.SpyderV_QuantModels.SpyderV05_PricingEngine"
if _v05_key not in sys.modules:
    _v05_mod = _load_v_module("SpyderV05_PricingEngine.py", _v05_key)
else:
    _v05_mod = sys.modules[_v05_key]
sys.modules.setdefault("SpyderV05_PricingEngine", _v05_mod)

# Load V06
_v06_key = "Spyder.SpyderV_QuantModels.SpyderV06_VolatilityEngine"
if _v06_key not in sys.modules:
    _v06_mod = _load_v_module("SpyderV06_VolatilityEngine.py", _v06_key)
else:
    _v06_mod = sys.modules[_v06_key]
sys.modules.setdefault("SpyderV06_VolatilityEngine", _v06_mod)

# Also register under SpyderV_QuantModels prefix (V07 imports with this prefix)
_v06_short_key = "SpyderV_QuantModels.SpyderV06_VolatilityEngine"
sys.modules.setdefault(_v06_short_key, _v06_mod)
_v06_parent = sys.modules.setdefault("SpyderV_QuantModels", types.ModuleType("SpyderV_QuantModels"))
_v06_parent.__path__ = [_V_PKG_PATH]

# Load V07 (hard U01/U02 imports satisfied by stubs above)
_v07_key = "Spyder.SpyderV_QuantModels.SpyderV07_AdvancedModels"
if _v07_key not in sys.modules:
    _v07_mod = _load_v_module("SpyderV07_AdvancedModels.py", _v07_key)
else:
    _v07_mod = sys.modules[_v07_key]
sys.modules.setdefault("SpyderV07_AdvancedModels", _v07_mod)

# Load V08 (gym stub satisfies hard gym import; torch is available in venv)
_v08_key = "Spyder.SpyderV_QuantModels.SpyderV08_AIModels"
if _v08_key not in sys.modules:
    _v08_mod = _load_v_module("SpyderV08_AIModels.py", _v08_key)
else:
    _v08_mod = sys.modules[_v08_key]
sys.modules.setdefault("SpyderV08_AIModels", _v08_mod)

# ==============================================================================
# IMPORTS from each V-series module
# ==============================================================================
# --- V01 ---
from Spyder.SpyderV_QuantModels.SpyderV01_QuantEngine import (
    RequestType,
    DataSource as V01DataSource,
    Priority,
    QuantRequest,
    QuantResponse,
    OrchestrationMetrics,
    SpyderQuantEngine,
)
import Spyder.SpyderV_QuantModels.SpyderV01_QuantEngine as _v01_mod

# --- V02 ---
from Spyder.SpyderV_QuantModels.SpyderV02_ModelManager import (
    EngineType,
    EngineStatus,
    ModelSelectionStrategy,
    MarketRegime,
    EngineConfig,
    EnginePerformance,
    ModelSelectionContext,
    EngineRecommendation,
    ConsolidatedRequest,
    ConsolidatedResponse,
    SpyderModelManager,
)

# --- V03 ---
from Spyder.SpyderV_QuantModels.SpyderV03_DataInterface import (
    DataSource as V03DataSource,
    MarketDataPoint,
    OptionData,
    MarketSentiment,
    InternationalData,
    SpyderDataInterface,
)

# --- V04 ---
from Spyder.SpyderV_QuantModels.SpyderV04_RiskManager import (
    RiskMethod,
    ConfidenceLevel,
    TimeHorizon,
    RiskMetricType,
    RiskParameters,
    SpyderRiskManager,
)

# --- V05 ---
from Spyder.SpyderV_QuantModels.SpyderV05_PricingEngine import (
    PricingModel,
    OptionType,
    ExerciseStyle,
    GreeksType,
    OptionContract,
    PricingParameters,
    SpyderPricingEngine,
)

# --- V06 ---
from Spyder.SpyderV_QuantModels.SpyderV06_VolatilityEngine import (
    VolatilityModel,
    VolatilityHorizon,
    VolatilityRegime,
    HestonParameters,
    GARCHParameters,
    RoughVolParameters,
    SpyderVolatilityEngine,
)

# --- V07 ---
from Spyder.SpyderV_QuantModels.SpyderV07_AdvancedModels import (
    CrisisLevel,
    JumpType,
    ModelValidationStatus,
    MertonParameters,
    JumpEvent,
    CrisisAssessment,
    SpyderAdvancedModelsEngine,
)

# --- V08 ---
from Spyder.SpyderV_QuantModels.SpyderV08_AIModels import (
    AIModelType,
    ModelMode,
    ActionType,
    TransformerConfig,
    RLConfig,
    TradingEnvironmentConfig,
    AIModelsConfig,
    SpyderAIModels,
)


# ==============================================================================
# V01 — QuantEngine
# ==============================================================================
class TestV01QuantEngine(unittest.TestCase):
    """Tests for SpyderV01_QuantEngine enums, dataclasses, and main class."""

    def test_request_type_enum_members(self):
        """RequestType has expected string values."""
        self.assertEqual(RequestType.PRICE_SINGLE.value, "price_single")
        self.assertEqual(RequestType.PRICE_PORTFOLIO.value, "price_portfolio")
        self.assertEqual(RequestType.CALCULATE_GREEKS.value, "calculate_greeks")
        self.assertEqual(RequestType.ASSESS_RISK.value, "assess_risk")
        self.assertEqual(RequestType.STRESS_TEST.value, "stress_test")
        self.assertEqual(RequestType.MODEL_VALIDATION.value, "model_validation")
        self.assertEqual(len(RequestType), 6)

    def test_data_source_enum_members(self):
        """DataSource (V01) has correct integer values."""
        self.assertEqual(V01DataSource.CORE_DATA.value, 3)
        self.assertEqual(V01DataSource.SPY_OPTIONS.value, 4)
        self.assertEqual(V01DataSource.MARKET_INTERNALS.value, 6)
        self.assertEqual(V01DataSource.INTERNATIONAL.value, 10)

    def test_priority_enum_members(self):
        """Priority enum has correct ordering structure."""
        self.assertEqual(Priority.CRITICAL.value, 1)
        self.assertEqual(Priority.HIGH.value, 2)
        self.assertEqual(Priority.MEDIUM.value, 3)
        self.assertEqual(Priority.LOW.value, 4)

    def test_quant_request_dataclass_defaults(self):
        """QuantRequest dataclass can be constructed with required fields."""
        req = QuantRequest(
            request_id="req-001",
            request_type=RequestType.PRICE_SINGLE,
            priority=Priority.HIGH,
            data={"symbol": "SPY"},
        )
        self.assertEqual(req.request_id, "req-001")
        self.assertEqual(req.request_type, RequestType.PRICE_SINGLE)
        self.assertEqual(req.priority, Priority.HIGH)
        self.assertEqual(req.timeout_seconds, 30.0)
        self.assertEqual(req.retry_count, 0)
        self.assertEqual(req.max_retries, 3)

    def test_quant_response_dataclass(self):
        """QuantResponse dataclass stores all fields."""
        resp = QuantResponse(
            request_id="req-001",
            success=True,
            data={"price": 450.0},
            execution_time_ms=12.5,
        )
        self.assertTrue(resp.success)
        self.assertEqual(resp.data["price"], 450.0)
        self.assertEqual(resp.execution_time_ms, 12.5)
        self.assertIsNone(resp.model_used)
        self.assertIsInstance(resp.warnings, list)

    def test_orchestration_metrics_defaults(self):
        """OrchestrationMetrics initialises with zeros."""
        m = OrchestrationMetrics()
        self.assertEqual(m.total_requests, 0)
        self.assertEqual(m.successful_requests, 0)
        self.assertEqual(m.failed_requests, 0)
        self.assertEqual(m.avg_response_time_ms, 0.0)
        self.assertIsInstance(m.requests_by_type, dict)

    def test_spyder_quant_engine_init(self):
        """SpyderQuantEngine initialises with mocked engine dependencies."""
        with patch.object(SpyderQuantEngine, "_initialize_engines", return_value=None):
            with patch.object(_v01_mod, "CONSOLIDATED_MODULES_AVAILABLE", True):
                eng = SpyderQuantEngine()
        self.assertIsNotNone(eng)
        self.assertFalse(eng.is_running)
        self.assertFalse(eng.shutdown_requested)
        self.assertIsInstance(eng.metrics, OrchestrationMetrics)
        self.assertIsInstance(eng.active_requests, dict)

    def test_spyder_quant_engine_config(self):
        """SpyderQuantEngine stores provided config."""
        cfg = {"max_workers": 4, "max_history_size": 500}
        with patch.object(SpyderQuantEngine, "_initialize_engines", return_value=None):
            with patch.object(_v01_mod, "CONSOLIDATED_MODULES_AVAILABLE", True):
                eng = SpyderQuantEngine(config=cfg)
        self.assertEqual(eng.config["max_workers"], 4)
        self.assertEqual(eng.max_history_size, 500)


# ==============================================================================
# V02 — ModelManager
# ==============================================================================
class TestV02ModelManager(unittest.TestCase):
    """Tests for SpyderV02_ModelManager enums, dataclasses, and main class."""

    def test_engine_type_enum(self):
        """EngineType has all expected entries."""
        self.assertEqual(EngineType.RISK_MANAGER.value, "risk_manager")
        self.assertEqual(EngineType.PRICING_ENGINE.value, "pricing_engine")
        self.assertEqual(EngineType.VOLATILITY_ENGINE.value, "volatility_engine")
        self.assertEqual(EngineType.ADVANCED_MODELS.value, "advanced_models")
        self.assertEqual(EngineType.AI_MODELS.value, "ai_models")

    def test_engine_status_enum(self):
        """EngineStatus covers lifecycle states."""
        self.assertEqual(EngineStatus.INITIALIZING.value, "initializing")
        self.assertEqual(EngineStatus.READY.value, "ready")
        self.assertEqual(EngineStatus.ERROR.value, "error")
        self.assertEqual(EngineStatus.DISABLED.value, "disabled")
        self.assertIn(EngineStatus.DEGRADED, EngineStatus)

    def test_model_selection_strategy_enum(self):
        """ModelSelectionStrategy values are correct."""
        self.assertEqual(ModelSelectionStrategy.PERFORMANCE_BASED.value, "performance_based")
        self.assertEqual(ModelSelectionStrategy.ENSEMBLE.value, "ensemble")
        self.assertEqual(ModelSelectionStrategy.FAIL_SAFE.value, "fail_safe")

    def test_market_regime_enum(self):
        """MarketRegime covers expected regimes."""
        self.assertEqual(MarketRegime.NORMAL.value, "normal")
        self.assertEqual(MarketRegime.HIGH_VOLATILITY.value, "high_volatility")
        self.assertEqual(MarketRegime.CRISIS.value, "crisis")
        self.assertEqual(MarketRegime.LOW_VOLATILITY.value, "low_volatility")
        self.assertIn(MarketRegime.TRENDING, MarketRegime)

    def test_engine_config_defaults(self):
        """EngineConfig has correct default values."""
        cfg = EngineConfig(engine_type=EngineType.RISK_MANAGER)
        self.assertEqual(cfg.engine_type, EngineType.RISK_MANAGER)
        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.priority, 1)
        self.assertEqual(cfg.performance_threshold, 0.85)
        self.assertIsInstance(cfg.initialization_params, dict)

    def test_model_selection_context(self):
        """ModelSelectionContext stores market context."""
        ctx = ModelSelectionContext(
            market_regime=MarketRegime.HIGH_VOLATILITY,
            volatility_level=0.35,
            time_to_expiry=0.25,
            option_type="call",
        )
        self.assertEqual(ctx.market_regime, MarketRegime.HIGH_VOLATILITY)
        self.assertEqual(ctx.volatility_level, 0.35)
        self.assertEqual(ctx.urgency, "normal")
        self.assertEqual(ctx.accuracy_requirement, "standard")

    def test_consolidated_request_dataclass(self):
        """ConsolidatedRequest stores all required fields."""
        ctx = ModelSelectionContext(
            market_regime=MarketRegime.NORMAL,
            volatility_level=0.2,
            time_to_expiry=None,
            option_type=None,
        )
        req = ConsolidatedRequest(
            request_id="cr-001",
            engine_type=EngineType.PRICING_ENGINE,
            operation="price_option",
            parameters={"strike": 450},
            context=ctx,
            timestamp=datetime.now(),
        )
        self.assertEqual(req.request_id, "cr-001")
        self.assertEqual(req.engine_type, EngineType.PRICING_ENGINE)
        self.assertEqual(req.priority, 1)

    def test_spyder_model_manager_init(self):
        """SpyderModelManager initialises without external engines."""
        mgr = SpyderModelManager()
        self.assertIsNotNone(mgr)
        self.assertIsInstance(mgr.engines, dict)
        self.assertIsInstance(mgr.engine_status, dict)
        self.assertIsInstance(mgr.performance_history, dict)


# ==============================================================================
# V03 — DataInterface
# ==============================================================================
class TestV03DataInterface(unittest.TestCase):
    """Tests for SpyderV03_DataInterface enums, dataclasses, and main class."""

    def test_data_source_enum(self):
        """DataSource (V03) maps to correct B08 client integers."""
        self.assertEqual(V03DataSource.CORE_DATA.value, 3)
        self.assertEqual(V03DataSource.SPY_OPTIONS.value, 4)
        self.assertEqual(V03DataSource.MARKET_INTERNALS.value, 6)
        self.assertEqual(V03DataSource.INTERNATIONAL.value, 10)

    def test_market_data_point_dataclass(self):
        """MarketDataPoint stores per-tick data correctly."""
        now = datetime.now()
        dp = MarketDataPoint(
            symbol="SPY",
            price=450.0,
            volume=1000,
            timestamp=now,
            bid=449.95,
            ask=450.05,
        )
        self.assertEqual(dp.symbol, "SPY")
        self.assertEqual(dp.price, 450.0)
        self.assertEqual(dp.bid, 449.95)
        self.assertIsInstance(dp.metadata, dict)

    def test_option_data_dataclass(self):
        """OptionData stores complete options chain fields."""
        expiry = datetime(2026, 1, 16)
        od = OptionData(
            underlying="SPY",
            strike=450.0,
            expiry=expiry,
            option_type="call",
            bid=5.10,
            ask=5.30,
            mid=5.20,
            volume=500,
            open_interest=10000,
            implied_vol=0.18,
            delta=0.50,
        )
        self.assertEqual(od.underlying, "SPY")
        self.assertEqual(od.strike, 450.0)
        self.assertEqual(od.delta, 0.50)
        self.assertIsNone(od.gamma)

    def test_market_sentiment_dataclass(self):
        """MarketSentiment stores VIX and put/call ratio."""
        ms = MarketSentiment(
            symbol="SPY",
            put_call_ratio=1.2,
            vix_level=18.5,
            skew_indicator=-0.05,
            fear_greed_index=35.0,
        )
        self.assertEqual(ms.symbol, "SPY")
        self.assertEqual(ms.vix_level, 18.5)
        self.assertEqual(ms.put_call_ratio, 1.2)

    def test_spyder_data_interface_init(self):
        """SpyderDataInterface initialises with default parameters."""
        iface = SpyderDataInterface()
        self.assertEqual(iface.cache_size, 10000)
        self.assertEqual(iface.update_frequency, 1.0)
        self.assertIsNone(iface.b08_manager)
        self.assertFalse(iface.is_running)
        self.assertIsInstance(iface.spot_prices, dict)
        self.assertIsInstance(iface.options_chains, dict)

    def test_spyder_data_interface_custom_params(self):
        """SpyderDataInterface stores custom cache_size and update_frequency."""
        iface = SpyderDataInterface(cache_size=500, update_frequency=0.5)
        self.assertEqual(iface.cache_size, 500)
        self.assertEqual(iface.update_frequency, 0.5)


# ==============================================================================
# V04 — RiskManager
# ==============================================================================
class TestV04RiskManager(unittest.TestCase):
    """Tests for SpyderV04_RiskManager enums, dataclasses, and main class."""

    def test_risk_method_enum(self):
        """RiskMethod has all expected calculation methods."""
        self.assertEqual(RiskMethod.HISTORICAL.value, "historical")
        self.assertEqual(RiskMethod.PARAMETRIC.value, "parametric")
        self.assertEqual(RiskMethod.MONTE_CARLO.value, "monte_carlo")
        self.assertEqual(RiskMethod.CORNISH_FISHER.value, "cornish_fisher")
        self.assertEqual(RiskMethod.EXTREME_VALUE.value, "extreme_value")

    def test_confidence_level_enum(self):
        """ConfidenceLevel has expected float values."""
        self.assertAlmostEqual(ConfidenceLevel.STANDARD.value, 0.95)
        self.assertAlmostEqual(ConfidenceLevel.REGULATORY.value, 0.99)
        self.assertAlmostEqual(ConfidenceLevel.CONSERVATIVE.value, 0.975)
        self.assertAlmostEqual(ConfidenceLevel.STRESS.value, 0.999)

    def test_time_horizon_enum(self):
        """TimeHorizon has expected day-fraction values."""
        self.assertAlmostEqual(TimeHorizon.INTRADAY.value, 0.25)
        self.assertEqual(TimeHorizon.DAILY.value, 1)
        self.assertEqual(TimeHorizon.WEEKLY.value, 5)
        self.assertEqual(TimeHorizon.MONTHLY.value, 21)

    def test_risk_metric_type_enum(self):
        """RiskMetricType covers expected risk categories."""
        self.assertEqual(RiskMetricType.VAR.value, "var")
        self.assertEqual(RiskMetricType.CVAR.value, "cvar")
        self.assertEqual(RiskMetricType.MAXIMUM_DRAWDOWN.value, "mdd")
        self.assertEqual(RiskMetricType.CONCENTRATION.value, "concentration")

    def test_risk_parameters_defaults(self):
        """RiskParameters has sensible defaults."""
        rp = RiskParameters()
        self.assertAlmostEqual(rp.confidence_level, 0.95)
        self.assertEqual(rp.time_horizon, 1)
        self.assertEqual(rp.method, RiskMethod.HISTORICAL)
        self.assertEqual(rp.lookback_days, 252)
        self.assertEqual(rp.monte_carlo_sims, 10000)

    def test_risk_parameters_validate(self):
        """RiskParameters.validate() returns True for valid defaults."""
        rp = RiskParameters()
        self.assertTrue(rp.validate())

    def test_risk_parameters_validate_invalid(self):
        """RiskParameters.validate() returns False for invalid confidence."""
        rp = RiskParameters(confidence_level=0.1)
        self.assertFalse(rp.validate())

    def test_spyder_risk_manager_init(self):
        """SpyderRiskManager initialises with no arguments."""
        rm = SpyderRiskManager()
        self.assertIsNotNone(rm)
        self.assertIsInstance(rm.positions, dict)
        self.assertIsInstance(rm.portfolio_returns, list)
        self.assertIsInstance(rm.risk_cache, dict)
        self.assertIsNone(rm.data_manager)


# ==============================================================================
# V05 — PricingEngine
# ==============================================================================
class TestV05PricingEngine(unittest.TestCase):
    """Tests for SpyderV05_PricingEngine enums, dataclasses, and main class."""

    def test_pricing_model_enum(self):
        """PricingModel has expected model names."""
        self.assertEqual(PricingModel.BLACK_SCHOLES.value, "black_scholes")
        self.assertEqual(PricingModel.BARONE_ADESI_WHALEY.value, "barone_adesi")
        self.assertEqual(PricingModel.BINOMIAL_TREE.value, "binomial_tree")
        self.assertEqual(PricingModel.MONTE_CARLO_LSM.value, "monte_carlo_lsm")
        self.assertEqual(PricingModel.AUTO.value, "auto")

    def test_option_type_enum(self):
        """OptionType has CALL and PUT."""
        self.assertEqual(OptionType.CALL.value, "call")
        self.assertEqual(OptionType.PUT.value, "put")
        self.assertEqual(len(OptionType), 2)

    def test_exercise_style_enum(self):
        """ExerciseStyle has EUROPEAN and AMERICAN."""
        self.assertEqual(ExerciseStyle.EUROPEAN.value, "european")
        self.assertEqual(ExerciseStyle.AMERICAN.value, "american")

    def test_greeks_type_enum(self):
        """GreeksType is importable."""
        self.assertIsNotNone(GreeksType)
        self.assertTrue(len(GreeksType) > 0)

    def test_option_contract_dataclass(self):
        """OptionContract stores all fields with defaults."""
        oc = OptionContract(
            underlying_price=450.0,
            strike_price=455.0,
            time_to_expiry=0.25,
            risk_free_rate=0.05,
        )
        self.assertEqual(oc.underlying_price, 450.0)
        self.assertEqual(oc.strike_price, 455.0)
        self.assertEqual(oc.dividend_yield, 0.0)
        self.assertAlmostEqual(oc.volatility, 0.2)
        self.assertEqual(oc.option_type, OptionType.CALL)
        self.assertEqual(oc.exercise_style, ExerciseStyle.AMERICAN)

    def test_option_contract_validate_valid(self):
        """OptionContract.validate() returns True for realistic inputs."""
        oc = OptionContract(
            underlying_price=450.0,
            strike_price=450.0,
            time_to_expiry=0.1,
            risk_free_rate=0.05,
        )
        self.assertTrue(oc.validate())

    def test_pricing_parameters_defaults(self):
        """PricingParameters has sensible defaults."""
        pp = PricingParameters()
        self.assertEqual(pp.model, PricingModel.AUTO)
        self.assertEqual(pp.binomial_steps, 100)
        self.assertEqual(pp.monte_carlo_sims, 10000)
        self.assertTrue(pp.use_cache)

    def test_spyder_pricing_engine_init(self):
        """SpyderPricingEngine initialises without external data manager."""
        pe = SpyderPricingEngine()
        self.assertIsNotNone(pe)
        self.assertIsInstance(pe.model_performance, dict)
        self.assertIsInstance(pe.price_cache, dict)
        self.assertEqual(pe.total_calculations, 0)
        self.assertIsNone(pe.data_manager)


# ==============================================================================
# V06 — VolatilityEngine
# ==============================================================================
class TestV06VolatilityEngine(unittest.TestCase):
    """Tests for SpyderV06_VolatilityEngine enums, dataclasses, and main class."""

    def test_volatility_model_enum(self):
        """VolatilityModel has all expected entries."""
        self.assertEqual(VolatilityModel.HESTON.value, "heston")
        self.assertEqual(VolatilityModel.GARCH.value, "garch")
        self.assertEqual(VolatilityModel.ROUGH_VOLATILITY.value, "rough_vol")
        self.assertEqual(VolatilityModel.HISTORICAL.value, "historical")
        self.assertEqual(VolatilityModel.AUTO.value, "auto")

    def test_volatility_horizon_enum(self):
        """VolatilityHorizon has expected time-frame entries."""
        self.assertEqual(VolatilityHorizon.INTRADAY.value, "intraday")
        self.assertEqual(VolatilityHorizon.SHORT_TERM.value, "short_term")
        self.assertEqual(VolatilityHorizon.MEDIUM_TERM.value, "medium_term")
        self.assertEqual(VolatilityHorizon.LONG_TERM.value, "long_term")

    def test_volatility_regime_enum(self):
        """VolatilityRegime covers all market conditions."""
        self.assertEqual(VolatilityRegime.LOW_VOL.value, "low_vol")
        self.assertEqual(VolatilityRegime.NORMAL_VOL.value, "normal_vol")
        self.assertEqual(VolatilityRegime.HIGH_VOL.value, "high_vol")
        self.assertEqual(VolatilityRegime.CRISIS_VOL.value, "crisis_vol")

    def test_heston_parameters_dataclass(self):
        """HestonParameters stores model calibration data."""
        params = HestonParameters(
            v0=0.04,
            theta=0.04,
            kappa=1.5,
            sigma=0.3,
            rho=-0.7,
        )
        self.assertAlmostEqual(params.v0, 0.04)
        self.assertAlmostEqual(params.kappa, 1.5)
        self.assertAlmostEqual(params.rho, -0.7)

    def test_heston_parameters_validate_feller(self):
        """HestonParameters.validate() checks Feller condition."""
        # kappa=1.5, theta=0.04, sigma=0.3 → 2*1.5*0.04=0.12 > 0.09 → valid
        params = HestonParameters(v0=0.04, theta=0.04, kappa=1.5, sigma=0.3, rho=-0.7)
        self.assertTrue(params.validate())

    def test_garch_parameters_dataclass(self):
        """GARCHParameters stores and validates GARCH(1,1) params."""
        g = GARCHParameters(omega=1e-6, alpha=0.1, beta=0.85)
        self.assertEqual(g.alpha, 0.1)
        self.assertEqual(g.beta, 0.85)
        self.assertTrue(g.validate())  # 0.1+0.85 < 1
        self.assertAlmostEqual(g.persistence, 0.95)

    def test_rough_vol_parameters_dataclass(self):
        """RoughVolParameters validates Hurst parameter constraint."""
        rv = RoughVolParameters(hurst=0.1, xi=0.3, theta=0.2)
        self.assertEqual(rv.hurst, 0.1)
        self.assertTrue(rv.validate())

    def test_spyder_volatility_engine_init(self):
        """SpyderVolatilityEngine initialises with empty state."""
        ve = SpyderVolatilityEngine()
        self.assertIsNotNone(ve)
        self.assertIsNone(ve.data_manager)
        self.assertIsNone(ve.heston_params)
        self.assertIsNone(ve.garch_params)
        self.assertEqual(ve.current_volatility, 0.0)
        self.assertEqual(ve.volatility_regime, VolatilityRegime.NORMAL_VOL)
        self.assertIsInstance(ve.price_history, list)
        self.assertIsInstance(ve.surface_cache, dict)


# ==============================================================================
# V07 — AdvancedModels
# ==============================================================================
class TestV07AdvancedModels(unittest.TestCase):
    """Tests for SpyderV07_AdvancedModels enums, dataclasses, and main class."""

    def test_crisis_level_enum(self):
        """CrisisLevel covers all severity tiers."""
        self.assertEqual(CrisisLevel.NORMAL.value, "normal")
        self.assertEqual(CrisisLevel.ELEVATED.value, "elevated")
        self.assertEqual(CrisisLevel.HIGH.value, "high")
        self.assertEqual(CrisisLevel.CRISIS.value, "crisis")
        self.assertEqual(CrisisLevel.EXTREME.value, "extreme")

    def test_jump_type_enum(self):
        """JumpType defines directional jump categories."""
        self.assertEqual(JumpType.UPWARD_JUMP.value, "upward_jump")
        self.assertEqual(JumpType.DOWNWARD_JUMP.value, "downward_jump")
        self.assertEqual(JumpType.VOLATILITY_JUMP.value, "volatility_jump")
        self.assertEqual(JumpType.NO_JUMP.value, "no_jump")

    def test_model_validation_status_enum(self):
        """ModelValidationStatus covers calibration lifecycle."""
        self.assertEqual(ModelValidationStatus.NOT_CALIBRATED.value, "not_calibrated")
        self.assertEqual(ModelValidationStatus.CALIBRATING.value, "calibrating")
        self.assertEqual(ModelValidationStatus.CALIBRATED.value, "calibrated")
        self.assertEqual(ModelValidationStatus.VALIDATION_FAILED.value, "validation_failed")
        self.assertEqual(ModelValidationStatus.OUTDATED.value, "outdated")

    def test_merton_parameters_defaults(self):
        """MertonParameters has expected default values for SPY dynamics."""
        mp = MertonParameters()
        self.assertAlmostEqual(mp.mu, 0.08)
        self.assertAlmostEqual(mp.sigma, 0.15)
        self.assertAlmostEqual(mp.lambda_jump, 0.2)
        self.assertAlmostEqual(mp.mu_jump, -0.05)
        self.assertAlmostEqual(mp.sigma_jump, 0.10)

    def test_jump_event_dataclass(self):
        """JumpEvent stores detection results."""
        now = datetime.now()
        je = JumpEvent(
            timestamp=now,
            price_before=450.0,
            price_after=440.0,
            jump_size=-0.022,
            jump_type=JumpType.DOWNWARD_JUMP,
            significance_level=0.01,
            market_impact="HIGH",
            confidence=0.95,
        )
        self.assertEqual(je.jump_type, JumpType.DOWNWARD_JUMP)
        self.assertAlmostEqual(je.jump_size, -0.022)
        self.assertAlmostEqual(je.confidence, 0.95)

    def test_crisis_assessment_dataclass(self):
        """CrisisAssessment stores market stress data."""
        ca = CrisisAssessment(
            crisis_level=CrisisLevel.ELEVATED,
            crisis_probability=0.15,
            stress_indicators={"vix": 28.0},
            jump_frequency=0.3,
            volatility_regime="HIGH_VOL",
            recommendations=["reduce_delta_exposure"],
        )
        self.assertEqual(ca.crisis_level, CrisisLevel.ELEVATED)
        self.assertAlmostEqual(ca.crisis_probability, 0.15)
        self.assertIsInstance(ca.timestamp, datetime)

    def test_spyder_advanced_models_engine_init(self):
        """SpyderAdvancedModelsEngine initialises with stub U01/U02."""
        eng = SpyderAdvancedModelsEngine()
        self.assertIsNotNone(eng)
        self.assertIsNone(eng.data_manager)
        self.assertIsNone(eng.volatility_engine)
        self.assertIsNone(eng.merton_params)
        self.assertEqual(eng.validation_status, ModelValidationStatus.NOT_CALIBRATED)
        self.assertIsInstance(eng.price_history, list)
        self.assertIsInstance(eng.jump_history, list)


# ==============================================================================
# V08 — AIModels
# ==============================================================================
class TestV08AIModels(unittest.TestCase):
    """Tests for SpyderV08_AIModels enums, config dataclasses, and main class."""

    def test_ai_model_type_enum(self):
        """AIModelType has Transformer, RL, and Ensemble entries."""
        self.assertEqual(AIModelType.TRANSFORMER_PRICING.value, "transformer_pricing")
        self.assertEqual(AIModelType.REINFORCEMENT_LEARNING.value, "reinforcement_learning")
        self.assertEqual(AIModelType.HYBRID_ENSEMBLE.value, "hybrid_ensemble")
        self.assertEqual(len(AIModelType), 3)

    def test_model_mode_enum(self):
        """ModelMode matches expected operating modes."""
        self.assertEqual(ModelMode.TRAINING.value, "training")
        self.assertEqual(ModelMode.INFERENCE.value, "inference")
        self.assertEqual(ModelMode.EVALUATION.value, "evaluation")
        self.assertEqual(ModelMode.CALIBRATION.value, "calibration")

    def test_action_type_enum(self):
        """ActionType covers expected RL trading actions."""
        self.assertEqual(ActionType.HOLD.value, 0)
        self.assertEqual(ActionType.BUY_CALL.value, 1)
        self.assertEqual(ActionType.SELL_CALL.value, 2)
        self.assertEqual(ActionType.BUY_PUT.value, 3)
        self.assertEqual(ActionType.SELL_PUT.value, 4)
        self.assertEqual(ActionType.CLOSE_POSITION.value, 5)

    def test_transformer_config_defaults(self):
        """TransformerConfig has expected architecture defaults."""
        cfg = TransformerConfig()
        self.assertEqual(cfg.d_model, 128)
        self.assertEqual(cfg.nhead, 8)
        self.assertEqual(cfg.num_layers, 6)
        self.assertEqual(cfg.dim_feedforward, 512)
        self.assertAlmostEqual(cfg.dropout, 0.1)
        self.assertEqual(cfg.max_seq_length, 60)

    def test_rl_config_defaults(self):
        """RLConfig has sensible RL hyperparameter defaults."""
        cfg = RLConfig()
        self.assertEqual(cfg.state_dim, 50)
        self.assertEqual(cfg.action_dim, 6)
        self.assertEqual(cfg.hidden_dim, 256)
        self.assertAlmostEqual(cfg.gamma, 0.99)
        self.assertEqual(cfg.buffer_size, 100000)

    def test_trading_environment_config_defaults(self):
        """TradingEnvironmentConfig stores paper-trading defaults."""
        cfg = TradingEnvironmentConfig()
        self.assertAlmostEqual(cfg.initial_capital, 100000.0)
        self.assertAlmostEqual(cfg.max_position_size, 0.2)
        self.assertEqual(cfg.max_steps, 252)
        self.assertEqual(cfg.lookback_window, 20)

    def test_ai_models_config_defaults(self):
        """AIModelsConfig nests sub-configs correctly."""
        cfg = AIModelsConfig()
        self.assertIsInstance(cfg.transformer_config, TransformerConfig)
        self.assertIsInstance(cfg.rl_config, RLConfig)
        self.assertIsInstance(cfg.trading_env_config, TradingEnvironmentConfig)
        self.assertEqual(cfg.model_cache_size, 10)
        self.assertIn("transformer", cfg.ensemble_weights)

    def test_spyder_ai_models_init(self):
        """SpyderAIModels initialises without external data."""
        ai = SpyderAIModels()
        self.assertIsNotNone(ai)
        self.assertIsInstance(ai.config, AIModelsConfig)
        self.assertIsNone(ai.transformer_model)
        self.assertIsNone(ai.rl_agent)
        self.assertFalse(ai.is_fitted)
        self.assertIsInstance(ai.performance_history, dict)
        self.assertIn("transformer", ai.performance_history)
        self.assertIsInstance(ai.model_cache, dict)
        self.assertIsInstance(ai.training_state, dict)
        self.assertFalse(ai.training_state["transformer_trained"])


# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
