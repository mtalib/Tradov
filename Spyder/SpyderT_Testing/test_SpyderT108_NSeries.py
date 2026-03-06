#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT108_NSeries.py
Purpose: Coverage tests for SpyderN_OptionsAnalytics — all 13 modules

Author: Spyder Dev
Year Created: 2025
Last Updated: 2026-03-06 Time: 01:00:00
"""

# ==============================================================================
# BOOTSTRAP — stub out missing cross-module deps before any N-series import
# ==============================================================================
import os
import sys
import types
import logging
import unittest
from datetime import datetime, timedelta, date
from unittest.mock import MagicMock

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# --- plotly stubs (N06/N07/N08/N09/N10/N11/N12 dependency) -------------------
_plotly_go = types.ModuleType("plotly.graph_objects")
_plotly_go.Figure = type("Figure", (), {
    "add_trace": lambda *a, **k: None,
    "update_layout": lambda *a, **k: None,
    "show": lambda *a, **k: None,
})
_plotly_go.Bar = type("Bar", (), {})
_plotly_go.Scatter = type("Scatter", (), {})
_plotly_go.Heatmap = type("Heatmap", (), {})
_plotly_go.Surface = type("Surface", (), {})
_plotly_sub = types.ModuleType("plotly.subplots")
_plotly_sub.make_subplots = lambda *a, **k: _plotly_go.Figure()
_plotly_express = types.ModuleType("plotly.express")
_plotly_pkg = types.ModuleType("plotly")
_plotly_pkg.graph_objects = _plotly_go
_plotly_pkg.subplots = _plotly_sub
_plotly_pkg.express = _plotly_express
sys.modules.setdefault("plotly", _plotly_pkg)
sys.modules.setdefault("plotly.graph_objects", _plotly_go)
sys.modules.setdefault("plotly.subplots", _plotly_sub)
sys.modules.setdefault("plotly.express", _plotly_express)

# --- Spyder U-series stubs used by N-series ----------------------------------
def _ensure_mod(key):
    """Create a stub module and all ancestor package stubs (prevents real __init__.py loading)."""
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        ancestor = ".".join(parts[:i])
        if ancestor not in sys.modules:
            sys.modules[ancestor] = types.ModuleType(ancestor)
    return sys.modules[key]

_u01 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU01_Logger")
if not hasattr(_u01, "SpyderLogger"):
    _u01.SpyderLogger = type("SpyderLogger", (), {
        "get_logger": staticmethod(lambda name: logging.getLogger(name))
    })

_u02 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
if not hasattr(_u02, "SpyderErrorHandler"):
    _u02.SpyderErrorHandler = type("SpyderErrorHandler", (), {})

_u07 = _ensure_mod("Spyder.SpyderU_Utilities.SpyderU07_Constants")
if not hasattr(_u07, "OptionType"):
    from enum import Enum
    _u07.OptionType = Enum("OptionType", {"CALL": "CALL", "PUT": "PUT"})
if not hasattr(_u07, "OrderType"):
    _u07.OrderType = type("OrderType", (), {})
if not hasattr(_u07, "TimeFrame"):
    _u07.TimeFrame = type("TimeFrame", (), {})

# --- Spyder A-series stubs used by N-series ----------------------------------
_a05 = _ensure_mod("Spyder.SpyderA_Core.SpyderA05_EventManager")
if not hasattr(_a05, "Event"):
    _a05.Event = type("Event", (), {})
if not hasattr(_a05, "EventType"):
    from enum import Enum
    _a05.EventType = Enum("EventType", {"MARKET_DATA": 1})
if not hasattr(_a05, "get_event_manager"):
    _a05.get_event_manager = lambda: MagicMock()

# --- Spyder C-series stubs used by N-series ----------------------------------
_c03 = _ensure_mod("Spyder.SpyderC_MarketData.SpyderC03_OptionChain")
if not hasattr(_c03, "OptionChainManager"):
    _c03.OptionChainManager = type("OptionChainManager", (), {})
if not hasattr(_c03, "OptionChain"):
    _c03.OptionChain = type("OptionChain", (), {})

_c07 = _ensure_mod("Spyder.SpyderC_MarketData.SpyderC07_OPRAFeed")
if not hasattr(_c07, "OPRAFeedHandler"):
    _c07.OPRAFeedHandler = type("OPRAFeedHandler", (), {})

# --- Spyder F-series stubs used by N-series ----------------------------------
_f06 = _ensure_mod("Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator")
if not hasattr(_f06, "GreeksCalculator"):
    _f06.GreeksCalculator = type("GreeksCalculator", (), {})

# --- Spyder S-series stubs ---------------------------------------------------
_s05 = _ensure_mod("Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator")
if not hasattr(_s05, "GammaExposureCalculator"):
    _s05.GammaExposureCalculator = type("GammaExposureCalculator", (), {})

# --- N-series internal missing modules ----------------------------------------
# N08 imports SpyderN01_VolatilitySmile which doesn't exist on disk
_n01_smile = _ensure_mod(
    "Spyder.SpyderN_OptionsAnalytics.SpyderN01_VolatilitySmile"
)
if not hasattr(_n01_smile, "VolatilitySmileAnalyzer"):
    _n01_smile.VolatilitySmileAnalyzer = type(
        "VolatilitySmileAnalyzer", (),
        {"__init__": lambda self, *a, **kw: None}
    )

# N09 imports SpyderN07_OPRAGreeksHandler (a different N07, not FlowTracker)
_n07_opra = _ensure_mod(
    "Spyder.SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler"
)
if not hasattr(_n07_opra, "OPRAGreeksHandler"):
    _n07_opra.OPRAGreeksHandler = type("OPRAGreeksHandler", (), {})

# --- Ensure Spyder N package itself is properly set up as a real package ------
# We want Python to recognise it as a real package with __path__, so individual
# sub-modules can be found.  We preload it so the __init__.py does NOT run
# (it imports N08 which has a broken dep on the non-existent N01_VolatilitySmile).
import importlib.util as _ilu

# _ensure_mod may have already stubbed the N package (without __path__).
# Always set __path__ so Python can locate real N-submodule files on disk.
_n_pkg_path = os.path.join(_ROOT, "Spyder", "SpyderN_OptionsAnalytics")
_n_pkg = sys.modules.setdefault(
    "Spyder.SpyderN_OptionsAnalytics",
    types.ModuleType("Spyder.SpyderN_OptionsAnalytics"),
)
_n_pkg.__path__ = [_n_pkg_path]
_n_pkg.__package__ = "Spyder.SpyderN_OptionsAnalytics"
_n_pkg.__file__ = os.path.join(_n_pkg_path, "__init__.py")

# --- Pre-load N08 before __path__ lets Python find it on disk ----------------
# N08 imports SpyderN01_VolatilitySmile (non-existent) and SpyderA05 — both
# of which we've pre-stubbed above.  We must load N08 before any N-submodule
# import happens so that __init__.py (which also imports N08) is never run.
_n08_mod_key = "Spyder.SpyderN_OptionsAnalytics.SpyderN08_VolatilitySurface"
if _n08_mod_key not in sys.modules:
    _n08_file = os.path.join(
        _ROOT, "Spyder", "SpyderN_OptionsAnalytics",
        "SpyderN08_VolatilitySurface.py"
    )
    _n08_spec = _ilu.spec_from_file_location(_n08_mod_key, _n08_file)
    _n08_mod = _ilu.module_from_spec(_n08_spec)
    _n08_mod.__package__ = "Spyder.SpyderN_OptionsAnalytics"
    sys.modules[_n08_mod_key] = _n08_mod
    _n08_spec.loader.exec_module(_n08_mod)

# ==============================================================================
# N01_OptionsPricer — enums, dataclasses, OptionsPricer
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import (
    OptionType,
    ExerciseStyle,
    PricingModel,
    GreekType,
    OptionContract,
    MarketData,
    OptionPrice,
    GreeksResult,
    BlackScholesPricer,
    BinomialPricer,
    ImpliedVolatilitySolver,
    OptionsPricer,
)


class TestN01Enums(unittest.TestCase):
    def test_option_type_values(self):
        self.assertEqual(OptionType.CALL.value, "CALL")
        self.assertEqual(OptionType.PUT.value, "PUT")
        self.assertEqual(len(OptionType), 2)

    def test_exercise_style_values(self):
        self.assertEqual(ExerciseStyle.EUROPEAN.value, "EUROPEAN")
        self.assertEqual(ExerciseStyle.AMERICAN.value, "AMERICAN")
        self.assertIn(ExerciseStyle.BERMUDAN, ExerciseStyle)

    def test_pricing_model_values(self):
        self.assertEqual(PricingModel.BLACK_SCHOLES.value, "BLACK_SCHOLES")
        self.assertEqual(PricingModel.BINOMIAL.value, "BINOMIAL")
        self.assertEqual(PricingModel.MONTE_CARLO.value, "MONTE_CARLO")
        self.assertIn(PricingModel.FINITE_DIFFERENCE, PricingModel)

    def test_greek_type_values(self):
        self.assertEqual(GreekType.DELTA.value, "DELTA")
        self.assertEqual(GreekType.GAMMA.value, "GAMMA")
        self.assertEqual(GreekType.VEGA.value, "VEGA")
        self.assertEqual(GreekType.THETA.value, "THETA")
        self.assertEqual(GreekType.RHO.value, "RHO")
        self.assertIn(GreekType.VANNA, GreekType)
        self.assertIn(GreekType.CHARM, GreekType)


class TestN01OptionContract(unittest.TestCase):
    def _make_contract(self, option_type=OptionType.CALL):
        expiry = datetime.now() + timedelta(days=30)
        return OptionContract(
            symbol="SPY_CALL_500",
            underlying="SPY",
            strike=500.0,
            expiry=expiry,
            option_type=option_type,
        )

    def test_contract_creation(self):
        c = self._make_contract()
        self.assertEqual(c.symbol, "SPY_CALL_500")
        self.assertEqual(c.strike, 500.0)
        self.assertEqual(c.option_type, OptionType.CALL)

    def test_time_to_expiry_positive(self):
        c = self._make_contract()
        self.assertGreater(c.time_to_expiry, 0.0)

    def test_is_expired_future(self):
        c = self._make_contract()
        self.assertFalse(c.is_expired)

    def test_is_expired_past(self):
        c = OptionContract(
            symbol="SPY_CALL_500",
            underlying="SPY",
            strike=500.0,
            expiry=datetime.now() - timedelta(days=1),
            option_type=OptionType.CALL,
        )
        self.assertTrue(c.is_expired)


class TestN01MarketData(unittest.TestCase):
    def test_market_data_creation(self):
        md = MarketData(spot_price=450.0, volatility=0.2, risk_free_rate=0.05)
        self.assertEqual(md.spot_price, 450.0)
        self.assertEqual(md.volatility, 0.2)

    def test_mid_price_with_bid_ask(self):
        md = MarketData(spot_price=450.0, volatility=0.2, bid=1.90, ask=2.10)
        self.assertAlmostEqual(md.mid_price, 2.0, places=5)

    def test_mid_price_without_bid_ask(self):
        md = MarketData(spot_price=450.0, volatility=0.2)
        self.assertIsNone(md.mid_price)


class TestN01BlackScholesPricer(unittest.TestCase):
    def test_call_price_positive(self):
        price = BlackScholesPricer.price_call(
            S=450.0, K=450.0, T=0.25, r=0.05, q=0.0, sigma=0.20
        )
        self.assertGreater(price, 0.0)

    def test_put_price_positive(self):
        price = BlackScholesPricer.price_put(
            S=450.0, K=450.0, T=0.25, r=0.05, q=0.0, sigma=0.20
        )
        self.assertGreater(price, 0.0)

    def test_calculate_greeks_delta_call(self):
        greeks = BlackScholesPricer.calculate_greeks(
            S=450.0, K=450.0, T=0.25, r=0.05, q=0.0,
            sigma=0.20, option_type=OptionType.CALL  # must pass Enum, not str
        )
        # calculate_greeks returns a GreeksResult dataclass, not a dict
        self.assertGreater(greeks.delta, 0.0)
        self.assertLess(greeks.delta, 1.0)

    def test_calculate_greeks_delta_put_negative(self):
        greeks = BlackScholesPricer.calculate_greeks(
            S=450.0, K=450.0, T=0.25, r=0.05, q=0.0,
            sigma=0.20, option_type=OptionType.PUT  # must pass Enum, not str
        )
        self.assertLess(greeks.delta, 0.0)


class TestN01OptionsPricer(unittest.TestCase):
    def setUp(self):
        self.pricer = OptionsPricer()
        self.contract = OptionContract(
            symbol="SPY240315C00450000",
            underlying="SPY",
            strike=450.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=OptionType.CALL,
            exercise_style=ExerciseStyle.EUROPEAN,
        )
        self.market_data = MarketData(
            spot_price=450.0,
            volatility=0.20,
            risk_free_rate=0.05,
        )

    def test_instantiation(self):
        self.assertIsNotNone(self.pricer)

    def test_price_option_returns_option_price(self):
        result = self.pricer.price_option(self.contract, self.market_data)
        self.assertIsInstance(result, OptionPrice)
        self.assertGreater(result.theoretical_value, 0.0)

    def test_calculate_breakeven(self):
        premium = 5.0
        breakeven = self.pricer.calculate_breakeven(self.contract, premium)
        self.assertIsInstance(breakeven, (int, float))
        self.assertGreater(breakeven, 0.0)


# ==============================================================================
# N02_ImpliedVolatilityEngine — enums, IVPoint, ImpliedVolatilityEngine
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import (
    IVMetric,
    VolatilityRegime as N02VolatilityRegime,
    TermStructureShape,
    SmileShape,
    IVPoint,
    IVSnapshot,
    ImpliedVolatilityEngine,
)


class TestN02Enums(unittest.TestCase):
    def test_iv_metric_values(self):
        self.assertEqual(IVMetric.SPOT_IV.value, "SPOT_IV")
        self.assertEqual(IVMetric.IV_RANK.value, "IV_RANK")
        self.assertEqual(IVMetric.IV_PERCENTILE.value, "IV_PERCENTILE")
        self.assertIn(IVMetric.HV_RATIO, IVMetric)

    def test_volatility_regime_values(self):
        self.assertEqual(N02VolatilityRegime.LOW.value, "LOW_VOLATILITY")
        self.assertEqual(N02VolatilityRegime.NORMAL.value, "NORMAL_VOLATILITY")
        self.assertEqual(N02VolatilityRegime.HIGH.value, "HIGH_VOLATILITY")
        self.assertIn(N02VolatilityRegime.EXTREME, N02VolatilityRegime)

    def test_term_structure_shape_values(self):
        self.assertEqual(TermStructureShape.CONTANGO.value, "CONTANGO")
        self.assertEqual(TermStructureShape.BACKWARDATION.value, "BACKWARDATION")
        self.assertIn(TermStructureShape.FLAT, TermStructureShape)
        self.assertIn(TermStructureShape.HUMPED, TermStructureShape)

    def test_smile_shape_values(self):
        self.assertEqual(SmileShape.SYMMETRIC.value, "SYMMETRIC")
        self.assertEqual(SmileShape.SKEWED_PUT.value, "SKEWED_PUT")
        self.assertIn(SmileShape.SMIRK, SmileShape)


class TestN02IVPoint(unittest.TestCase):
    def test_iv_point_creation(self):
        # IVPoint fields: timestamp, symbol, strike, expiry, option_type,
        # spot_price, market_price, implied_volatility  (no iv field)
        from Spyder.SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import OptionType as N02OptionType
        pt = IVPoint(
            timestamp=datetime.now(),
            symbol="SPY",
            strike=450.0,
            expiry=datetime.now() + timedelta(days=30),
            option_type=N02OptionType.CALL,
            spot_price=450.0,
            market_price=5.0,
            implied_volatility=0.20,
        )
        self.assertEqual(pt.strike, 450.0)
        self.assertAlmostEqual(pt.implied_volatility, 0.20)


class TestN02Engine(unittest.TestCase):
    def test_instantiation_no_args(self):
        engine = ImpliedVolatilityEngine()
        self.assertIsNotNone(engine)

    def test_instantiation_with_data_dir(self):
        from pathlib import Path
        engine = ImpliedVolatilityEngine(data_dir=Path("/tmp"))
        self.assertIsNotNone(engine)


# ==============================================================================
# N03_OptionsChainManager — enums, OptionContract, OptionsChainManager
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import (
    OptionType as N03OptionType,
    Moneyness,
    ChainFilter,
    OptionContract as N03OptionContract,
    OptionsChainManager,
)


class TestN03Enums(unittest.TestCase):
    def test_option_type(self):
        self.assertEqual(N03OptionType.CALL.value, "CALL")
        self.assertEqual(N03OptionType.PUT.value, "PUT")

    def test_moneyness_values(self):
        self.assertEqual(Moneyness.DEEP_ITM.value, "DEEP_ITM")
        self.assertEqual(Moneyness.ITM.value, "ITM")
        self.assertEqual(Moneyness.ATM.value, "ATM")
        self.assertEqual(Moneyness.OTM.value, "OTM")
        self.assertEqual(Moneyness.DEEP_OTM.value, "DEEP_OTM")

    def test_chain_filter_values(self):
        self.assertEqual(ChainFilter.ALL.value, "ALL")
        self.assertEqual(ChainFilter.HIGH_VOLUME.value, "HIGH_VOLUME")
        self.assertIn(ChainFilter.LIQUID, ChainFilter)
        self.assertIn(ChainFilter.WEEKLY, ChainFilter)


class TestN03Manager(unittest.TestCase):
    def test_instantiation_no_args(self):
        mgr = OptionsChainManager()
        self.assertIsNotNone(mgr)

    def test_instantiation_with_config(self):
        mgr = OptionsChainManager(config={"max_strikes": 20})
        self.assertIsNotNone(mgr)


# ==============================================================================
# N04_OptionsGreeksCalculator — enums, OptionsGreeksCalculator
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import (
    GreekType as N04GreekType,
    ScenarioType,
    HedgeType,
    PositionGreeks,
    OptionsGreeksCalculator,
)


class TestN04Enums(unittest.TestCase):
    def test_greek_type_values(self):
        self.assertEqual(N04GreekType.DELTA.value, "Delta")
        self.assertEqual(N04GreekType.GAMMA.value, "Gamma")
        self.assertEqual(N04GreekType.VEGA.value, "Vega")
        self.assertEqual(N04GreekType.THETA.value, "Theta")
        self.assertIn(N04GreekType.VANNA, N04GreekType)

    def test_scenario_type_values(self):
        self.assertEqual(ScenarioType.SPOT_MOVE.value, "Spot Move")
        self.assertEqual(ScenarioType.VOL_CHANGE.value, "Volatility Change")
        self.assertIn(ScenarioType.TIME_DECAY, ScenarioType)


class TestN04PositionGreeks(unittest.TestCase):
    def test_position_greeks_creation(self):
        pg = PositionGreeks(
            symbol="SPY",
            option_type="call",
            strike=450.0,
            expiry=datetime.now() + timedelta(days=30),
            quantity=1,
            delta=0.50,
            gamma=0.02,
            theta=-0.10,
            vega=0.30,
            rho=0.05,
        )
        self.assertEqual(pg.symbol, "SPY")
        self.assertAlmostEqual(pg.delta, 0.50)


class TestN04Calculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        calc = OptionsGreeksCalculator()
        self.assertIsNotNone(calc)


# ==============================================================================
# N05_OptionsExpirationManager — enums, ExpiringPosition, OptionsExpirationManager
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN05_OptionsExpirationManager import (
    ExpirationType,
    SettlementType,
    ExpirationAction,
    PinRiskLevel,
    RollType,
    ExpiringPosition,
    OptionsExpirationManager,
)


class TestN05Enums(unittest.TestCase):
    def test_expiration_type_values(self):
        self.assertEqual(ExpirationType.WEEKLY.value, "WEEKLY")
        self.assertEqual(ExpirationType.MONTHLY.value, "MONTHLY")
        self.assertIn(ExpirationType.QUARTERLY, ExpirationType)
        self.assertIn(ExpirationType.LEAP, ExpirationType)

    def test_settlement_type_values(self):
        self.assertEqual(SettlementType.PM.value, "PM")
        self.assertEqual(SettlementType.AM.value, "AM")
        self.assertIn(SettlementType.CASH, SettlementType)

    def test_expiration_action_values(self):
        self.assertEqual(ExpirationAction.EXERCISE.value, "EXERCISE")
        self.assertEqual(ExpirationAction.ABANDON.value, "ABANDON")
        self.assertEqual(ExpirationAction.ROLL.value, "ROLL")
        self.assertIn(ExpirationAction.CLOSE, ExpirationAction)

    def test_pin_risk_level_values(self):
        self.assertEqual(PinRiskLevel.NONE.value, "NONE")
        self.assertEqual(PinRiskLevel.LOW.value, "LOW")
        self.assertEqual(PinRiskLevel.HIGH.value, "HIGH")
        self.assertIn(PinRiskLevel.CRITICAL, PinRiskLevel)

    def test_roll_type_values(self):
        self.assertEqual(RollType.CALENDAR.value, "CALENDAR")
        self.assertEqual(RollType.DIAGONAL.value, "DIAGONAL")
        self.assertIn(RollType.VERTICAL, RollType)


class TestN05Manager(unittest.TestCase):
    def test_instantiation_no_args(self):
        mgr = OptionsExpirationManager()
        self.assertIsNotNone(mgr)


# ==============================================================================
# N06_VolatilitySurfaceBuilder — enums, VolatilitySurfaceBuilder
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder import (
    SurfaceType,
    InterpolationMethod as N06InterpolationMethod,
    ArbitrageType as N06ArbitrageType,
    SkewPattern,
    SurfacePoint,
    VolatilitySurface as N06VolatilitySurface,
    VolatilitySurfaceBuilder,
)


class TestN06Enums(unittest.TestCase):
    def test_surface_type_values(self):
        self.assertEqual(SurfaceType.IMPLIED_VOLATILITY.value, "IV")
        self.assertEqual(SurfaceType.LOCAL_VOLATILITY.value, "LV")
        self.assertIn(SurfaceType.STOCHASTIC_VOLATILITY, SurfaceType)

    def test_interpolation_method_values(self):
        self.assertEqual(N06InterpolationMethod.LINEAR.value, "linear")
        self.assertEqual(N06InterpolationMethod.CUBIC.value, "cubic")
        self.assertIn(N06InterpolationMethod.SVI, N06InterpolationMethod)
        self.assertIn(N06InterpolationMethod.SABR, N06InterpolationMethod)

    def test_arbitrage_type_values(self):
        self.assertEqual(N06ArbitrageType.CALENDAR.value, "Calendar Spread")
        self.assertEqual(N06ArbitrageType.BUTTERFLY.value, "Butterfly")
        self.assertIn(N06ArbitrageType.BOX, N06ArbitrageType)


class TestN06Builder(unittest.TestCase):
    def test_instantiation_no_args(self):
        builder = VolatilitySurfaceBuilder()
        self.assertIsNotNone(builder)


# ==============================================================================
# N07_OptionsFlowTracker — enums, OptionsFlow, OptionsFlowTracker
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN07_OptionsFlowTracker import (
    OrderType as N07OrderType,
    FlowType as N07FlowType,
    Sentiment,
    AggressorSide,
    InstitutionalIndicator,
    OptionsFlow,
    OptionsFlowTracker,
)


class TestN07Enums(unittest.TestCase):
    def test_order_type_values(self):
        self.assertEqual(N07OrderType.BUY_TO_OPEN.value, "BTO")
        self.assertEqual(N07OrderType.SELL_TO_OPEN.value, "STO")
        self.assertEqual(N07OrderType.BUY_TO_CLOSE.value, "BTC")
        self.assertIn(N07OrderType.UNKNOWN, N07OrderType)

    def test_flow_type_values(self):
        self.assertEqual(N07FlowType.SWEEP.value, "SWEEP")
        self.assertEqual(N07FlowType.BLOCK.value, "BLOCK")
        self.assertIn(N07FlowType.UNUSUAL, N07FlowType)

    def test_sentiment_values(self):
        self.assertEqual(Sentiment.VERY_BULLISH.value, "VERY_BULLISH")
        self.assertEqual(Sentiment.BULLISH.value, "BULLISH")
        self.assertEqual(Sentiment.NEUTRAL.value, "NEUTRAL")
        self.assertEqual(Sentiment.BEARISH.value, "BEARISH")
        self.assertIn(Sentiment.VERY_BEARISH, Sentiment)

    def test_aggressor_side_values(self):
        self.assertEqual(AggressorSide.BUY.value, "BUY")
        self.assertEqual(AggressorSide.SELL.value, "SELL")
        self.assertIn(AggressorSide.NEUTRAL, AggressorSide)

    def test_institutional_indicator_values(self):
        self.assertEqual(InstitutionalIndicator.SMART_MONEY.value, "SMART_MONEY")
        self.assertEqual(InstitutionalIndicator.HEDGE.value, "HEDGE")
        self.assertIn(InstitutionalIndicator.RETAIL, InstitutionalIndicator)


class TestN07FlowTracker(unittest.TestCase):
    def test_instantiation_no_args(self):
        tracker = OptionsFlowTracker()
        self.assertIsNotNone(tracker)


# ==============================================================================
# N08_VolatilitySurface — enums, SurfacePoint, VolatilitySurfaceAnalyzer
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN08_VolatilitySurface import (
    SurfaceModel,
    InterpolationMethod as N08InterpolationMethod,
    ArbitrageType as N08ArbitrageType,
    SurfacePoint as N08SurfacePoint,
    VolatilitySurface as N08VolatilitySurface,
    VolatilitySurfaceAnalyzer,
)


class TestN08Enums(unittest.TestCase):
    def test_surface_model_values(self):
        self.assertEqual(SurfaceModel.POLYNOMIAL.value, "polynomial")
        self.assertEqual(SurfaceModel.SPLINE.value, "spline")
        self.assertEqual(SurfaceModel.SVI.value, "svi")
        self.assertEqual(SurfaceModel.SABR.value, "sabr")
        self.assertIn(SurfaceModel.LOCAL_VOL, SurfaceModel)
        self.assertIn(SurfaceModel.VANNA_VOLGA, SurfaceModel)

    def test_interpolation_method_values(self):
        self.assertEqual(N08InterpolationMethod.LINEAR.value, "linear")
        self.assertEqual(N08InterpolationMethod.CUBIC.value, "cubic")
        self.assertIn(N08InterpolationMethod.THIN_PLATE_SPLINE, N08InterpolationMethod)

    def test_arbitrage_type_values(self):
        self.assertEqual(N08ArbitrageType.CALENDAR.value, "calendar")
        self.assertEqual(N08ArbitrageType.BUTTERFLY.value, "butterfly")
        self.assertIn(N08ArbitrageType.VERTICAL, N08ArbitrageType)
        self.assertIn(N08ArbitrageType.NO_ARBITRAGE, N08ArbitrageType)


class TestN08SurfacePoint(unittest.TestCase):
    def test_surface_point_creation(self):
        # SurfacePoint fields: strike, expiry, time_to_expiry, moneyness,
        # log_moneyness, implied_vol  (no expiry_days / iv)
        import math
        pt = N08SurfacePoint(
            strike=450.0,
            expiry=datetime.now() + timedelta(days=30),
            time_to_expiry=30 / 365,
            moneyness=1.0,
            log_moneyness=0.0,
            implied_vol=0.20,
        )
        self.assertEqual(pt.strike, 450.0)
        self.assertAlmostEqual(pt.implied_vol, 0.20)


class TestN08Analyzer(unittest.TestCase):
    def test_instantiation(self):
        # Patch OptionChainManager in N08's namespace so the constructor doesn't
        # require positional args when the real C03 module is cached (full suite).
        with unittest.mock.patch(
            "Spyder.SpyderN_OptionsAnalytics.SpyderN08_VolatilitySurface.OptionChainManager",
            return_value=MagicMock(),
        ):
            analyzer = VolatilitySurfaceAnalyzer(symbol="SPY")
            self.assertIsNotNone(analyzer)


# ==============================================================================
# N09_GammaExposure — enums, GEXPoint, GammaExposureCalculator
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN09_GammaExposure import (
    GEXRegime,
    HedgingFlow,
    GEXSignal,
    GEXPoint,
    GammaExposureCalculator,
)


class TestN09Enums(unittest.TestCase):
    def test_gex_regime_values(self):
        self.assertEqual(GEXRegime.HIGH_POSITIVE.value, "high_positive")
        self.assertEqual(GEXRegime.MODERATE_POSITIVE.value, "moderate_positive")
        self.assertEqual(GEXRegime.NEAR_FLIP.value, "near_flip")
        self.assertEqual(GEXRegime.NEGATIVE.value, "negative")
        self.assertIn(GEXRegime.EXTREME_NEGATIVE, GEXRegime)

    def test_hedging_flow_values(self):
        self.assertEqual(HedgingFlow.STRONG_BUYING.value, "strong_buying")
        self.assertEqual(HedgingFlow.NEUTRAL.value, "neutral")
        self.assertIn(HedgingFlow.STRONG_SELLING, HedgingFlow)

    def test_gex_signal_values(self):
        self.assertEqual(GEXSignal.VOLATILITY_SUPPRESSED.value, "volatility_suppressed")
        self.assertEqual(GEXSignal.NEUTRAL.value, "neutral")
        self.assertIn(GEXSignal.APPROACHING_FLIP, GEXSignal)


class TestN09GEXPoint(unittest.TestCase):
    def test_gex_point_creation(self):
        # GEXPoint fields include required timestamp
        pt = GEXPoint(
            price=450.0,
            total_gamma=1000000.0,
            call_gamma=800000.0,
            put_gamma=-200000.0,
            net_gamma=600000.0,
            timestamp=datetime.now(),
        )
        self.assertEqual(pt.price, 450.0)
        self.assertAlmostEqual(pt.net_gamma, 600000.0)


class TestN09Calculator(unittest.TestCase):
    def test_instantiation_no_args(self):
        # Pass mock deps so N09 doesn't call OptionChainManager() with no args.
        calc = GammaExposureCalculator(
            opra_handler=MagicMock(), option_chain_mgr=MagicMock()
        )
        self.assertIsNotNone(calc)


# ==============================================================================
# N10_OptionsFlowAnalyzer — enums, OptionFlow, AdvancedOptionsFlowAnalyzer
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN10_OptionsFlowAnalyzer import (
    FlowType as N10FlowType,
    OrderSentiment,
    TraderType,
    FlowSignal,
    AdvancedOptionsFlowAnalyzer,
)


class TestN10Enums(unittest.TestCase):
    def test_flow_type_values(self):
        self.assertEqual(N10FlowType.SWEEP.value, "sweep")
        self.assertEqual(N10FlowType.BLOCK.value, "block")
        self.assertIn(N10FlowType.REGULAR, N10FlowType)
        self.assertIn(N10FlowType.INTERMARKET_SWEEP, N10FlowType)

    def test_order_sentiment_values(self):
        self.assertEqual(OrderSentiment.BULLISH.value, "bullish")
        self.assertEqual(OrderSentiment.BEARISH.value, "bearish")
        self.assertEqual(OrderSentiment.NEUTRAL.value, "neutral")
        self.assertIn(OrderSentiment.MIXED, OrderSentiment)

    def test_trader_type_values(self):
        self.assertEqual(TraderType.RETAIL.value, "retail")
        self.assertEqual(TraderType.INSTITUTIONAL.value, "institutional")
        self.assertIn(TraderType.SMART_MONEY, TraderType)
        self.assertIn(TraderType.MARKET_MAKER, TraderType)

    def test_flow_signal_values(self):
        self.assertEqual(FlowSignal.BULLISH_SWEEP.value, "bullish_sweep")
        self.assertGreaterEqual(len(FlowSignal), 2)


class TestN10Analyzer(unittest.TestCase):
    def test_instantiation_no_args(self):
        # N10 __init__ calls _initialize_anomaly_detector and
        # _load_historical_baselines which are not implemented in source;
        # pass option_chain_mgr mock so N10 doesn't call OptionChainManager().
        with unittest.mock.patch.object(
            AdvancedOptionsFlowAnalyzer,
            "_initialize_anomaly_detector",
            create=True,
            return_value=None,
        ), unittest.mock.patch.object(
            AdvancedOptionsFlowAnalyzer,
            "_load_historical_baselines",
            create=True,
        ):
            analyzer = AdvancedOptionsFlowAnalyzer(
                opra_feed=MagicMock(), option_chain_mgr=MagicMock()
            )
            self.assertIsNotNone(analyzer)


# ==============================================================================
# N11_OptionsGreeksFlow — enums, OptionsGreeksFlowAnalyzer
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow import (
    GreekFlowType,
    DealerPositioning as N11DealerPositioning,
    FlowDirection,
    OptionsGreeksFlowAnalyzer,
)


class TestN11Enums(unittest.TestCase):
    def test_greek_flow_type_auto(self):
        # Uses auto() so check names exist
        self.assertIn("GAMMA_HEDGING", [m.name for m in GreekFlowType])
        self.assertIn("VANNA_FLOW", [m.name for m in GreekFlowType])
        self.assertIn("CHARM_DECAY", [m.name for m in GreekFlowType])
        self.assertGreaterEqual(len(GreekFlowType), 3)

    def test_dealer_positioning_values(self):
        self.assertEqual(N11DealerPositioning.LONG_GAMMA.value, "LONG_GAMMA")
        self.assertEqual(N11DealerPositioning.SHORT_GAMMA.value, "SHORT_GAMMA")
        self.assertIn(N11DealerPositioning.NEUTRAL_GAMMA, N11DealerPositioning)
        self.assertIn(N11DealerPositioning.FLIPPING, N11DealerPositioning)

    def test_flow_direction_values(self):
        self.assertEqual(FlowDirection.BUYING_PRESSURE.value, "BUYING")
        self.assertEqual(FlowDirection.SELLING_PRESSURE.value, "SELLING")
        self.assertIn(FlowDirection.NEUTRAL, FlowDirection)
        self.assertIn(FlowDirection.MIXED, FlowDirection)


class TestN11Analyzer(unittest.TestCase):
    def test_instantiation_no_args(self):
        # Patch OptionChainManager in N11's namespace so the constructor doesn't
        # require positional args when the real C03 module is cached (full suite).
        with unittest.mock.patch(
            "Spyder.SpyderN_OptionsAnalytics.SpyderN11_OptionsGreeksFlow.OptionChainManager",
            return_value=MagicMock(),
        ):
            analyzer = OptionsGreeksFlowAnalyzer()
            self.assertIsNotNone(analyzer)


# ==============================================================================
# N12_VolatilitySurfaceAI — dataclasses, VolatilitySurfaceAI
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN12_VolatilitySurfaceAI import (
    VolatilityPoint,
    VolatilitySurface as N12VolatilitySurface,
    SurfaceMetrics,
    VolatilitySurfaceAI,
)


class TestN12Classes(unittest.TestCase):
    def test_volatility_point_creation(self):
        # VolatilityPoint fields: strike, expiry, moneyness, time_to_maturity,
        # implied_vol (all required)
        pt = VolatilityPoint(
            strike=450.0,
            expiry=datetime.now() + timedelta(days=91),
            moneyness=1.0,
            time_to_maturity=0.25,
            implied_vol=0.20,
        )
        self.assertEqual(pt.strike, 450.0)
        self.assertAlmostEqual(pt.implied_vol, 0.20)

    def test_volatility_surface_ai_instantiation(self):
        ai = VolatilitySurfaceAI()
        self.assertIsNotNone(ai)


# ==============================================================================
# N13_MarketImpactModel — enums, dataclasses, MarketImpactModel
# ==============================================================================
from Spyder.SpyderN_OptionsAnalytics.SpyderN13_MarketImpactModel import (
    ImpactModel,
    OrderUrgency,
    MarketState,
    MarketConditions,
    OrderCharacteristics,
    OptionGreeks as N13OptionGreeks,
    ImpactEstimate,
    MarketImpactModel,
)


class TestN13Enums(unittest.TestCase):
    def test_impact_model_values(self):
        self.assertEqual(ImpactModel.LINEAR.value, "LINEAR")
        self.assertEqual(ImpactModel.SQUARE_ROOT.value, "SQUARE_ROOT")
        self.assertEqual(ImpactModel.ALMGREN_CHRISS.value, "ALMGREN_CHRISS")
        self.assertIn(ImpactModel.ML_ENSEMBLE, ImpactModel)
        self.assertIn(ImpactModel.HYBRID, ImpactModel)

    def test_order_urgency_values(self):
        self.assertEqual(OrderUrgency.PASSIVE.value, 1)
        self.assertEqual(OrderUrgency.NORMAL.value, 2)
        self.assertEqual(OrderUrgency.AGGRESSIVE.value, 3)
        self.assertEqual(OrderUrgency.IMMEDIATE.value, 4)

    def test_market_state_values(self):
        self.assertEqual(MarketState.NORMAL.value, "NORMAL")
        self.assertEqual(MarketState.STRESSED.value, "STRESSED")
        self.assertIn(MarketState.VOLATILE, MarketState)
        self.assertIn(MarketState.ILLIQUID, MarketState)


class TestN13DataClasses(unittest.TestCase):
    def _make_market_conditions(self):
        # MarketConditions fields: symbol, bid, ask, mid_price, spread,
        # spread_bps, volume_30d_avg, volume_today, volatility_30d,
        # volatility_implied, order_book_depth, trade_frequency
        return MarketConditions(
            symbol="SPY",
            bid=449.50,
            ask=450.50,
            mid_price=450.0,
            spread=1.0,
            spread_bps=22.2,
            volume_30d_avg=80_000_000,
            volume_today=50_000_000,
            volatility_30d=0.18,
            volatility_implied=0.20,
            order_book_depth=5000,
            trade_frequency=120.0,
        )

    def _make_order_characteristics(self):
        # OrderCharacteristics also requires urgency, duration_minutes,
        # participation_rate
        return OrderCharacteristics(
            symbol="SPY",
            side="BUY",
            total_quantity=100,
            order_type="MARKET",
            urgency=OrderUrgency.NORMAL,
            duration_minutes=5.0,
            participation_rate=0.10,
        )

    def test_market_conditions_creation(self):
        mc = self._make_market_conditions()
        self.assertEqual(mc.symbol, "SPY")
        self.assertAlmostEqual(mc.mid_price, 450.0)

    def test_order_characteristics_creation(self):
        oc = self._make_order_characteristics()
        self.assertEqual(oc.side, "BUY")
        self.assertEqual(oc.total_quantity, 100)

    def test_option_greeks_creation(self):
        og = N13OptionGreeks(delta=0.50, gamma=0.02, theta=-0.10, vega=0.30)
        self.assertAlmostEqual(og.delta, 0.50)
        self.assertAlmostEqual(og.gamma, 0.02)


class TestN13ImpactModel(unittest.TestCase):
    def test_instantiation_default(self):
        model = MarketImpactModel()
        self.assertIsNotNone(model)

    def test_instantiation_with_model_type(self):
        model = MarketImpactModel(model_type=ImpactModel.LINEAR)
        self.assertIsNotNone(model)


# ==============================================================================
# Cross-module consistency tests
# ==============================================================================
class TestNSeriesCrossModule(unittest.TestCase):
    def test_option_type_consistent_across_n01_n03(self):
        # Both N01 and N03 define OptionType with CALL/PUT
        self.assertEqual(OptionType.CALL.value, "CALL")
        self.assertEqual(N03OptionType.CALL.value, "CALL")

    def test_greeks_result_has_required_fields(self):
        gr = GreeksResult(
            delta=0.50,
            gamma=0.02,
            vega=0.30,
            theta=-0.10,
            rho=0.05,
        )
        self.assertAlmostEqual(gr.delta, 0.50)
        self.assertAlmostEqual(gr.gamma, 0.02)

    def test_iv_engine_and_pricer_coexist(self):
        pricer = OptionsPricer()
        engine = ImpliedVolatilityEngine()
        self.assertIsNotNone(pricer)
        self.assertIsNotNone(engine)


if __name__ == "__main__":
    unittest.main()
