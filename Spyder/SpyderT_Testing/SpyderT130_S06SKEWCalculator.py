#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT130_S06SKEWCalculator.py
Purpose: Comprehensive unit and integration tests for
         SpyderS06_SKEWCalculator — CBOE SKEW Index Calculator.

         All network and filesystem I/O is mocked.
         Tests run fully offline with no broker credentials required.

Test Coverage:
    - Data classes (OptionData, SKEWCalculation, SKEWComponents)
    - Initialization & configuration
    - Black-Scholes pricing (call, put, vega, put-call parity)
    - Delta & implied-volatility (Newton-Raphson round-trip)
    - Forward price via put-call parity
    - ATM volatility weighted average
    - Volatility smile interpolation (cubic / linear / SABR)
    - SKEW component assembly
    - SKEW index formula & bounds
    - Third / fourth moment numerical integration
    - Variance (CBOE-style)
    - Confidence scoring
    - Interpolation quality assessment
    - Caching (store, retrieve, TTL expiry, LRU eviction)
    - History tracking & statistics
    - Performance metrics
    - End-to-end calculate_skew() with injected synthetic chain
    - DataUnavailableError when no real data
    - Factory function & singleton pattern
    - Thread-safety (concurrent lock access)

Author: GitHub Copilot (Spyder Dev)
Year Created: 2026
Last Updated: 2026-04-23 Time: 00:00:00
"""

# ==============================================================================
# BOOTSTRAP — stubs injected before any project import
# ==============================================================================
import os
import sys
import json
import math
import logging
import threading
import tempfile
import time
import types
import hashlib
import importlib.util as _ilu
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

logging.disable(logging.CRITICAL)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Heavy optional deps — stub anything that may be absent
# ---------------------------------------------------------------------------
for _pkg in ["hmmlearn", "hmmlearn.hmm", "plotly", "plotly.graph_objects",
             "plotly.subplots", "pytz"]:
    if _pkg not in sys.modules:
        _m = types.ModuleType(_pkg)
        _m.__getattr__ = lambda self, n: MagicMock()  # type: ignore[method-assign]
        sys.modules[_pkg] = _m

# ---------------------------------------------------------------------------
# Stub C29 DataProviderRouter so S06 can import without live data connections
# ---------------------------------------------------------------------------
def _ensure_mod(key: str):
    parts = key.split(".")
    for i in range(1, len(parts) + 1):
        anc = ".".join(parts[:i])
        if anc not in sys.modules:
            sys.modules[anc] = types.ModuleType(anc)
    return sys.modules[key]

for _key in [
    "Spyder", "Spyder.SpyderC_MarketData",
    "Spyder.SpyderC_MarketData.SpyderC29_DataProviderRouter",
    "SpyderC_MarketData", "SpyderC_MarketData.SpyderC29_DataProviderRouter",
]:
    _ensure_mod(_key)

# ==============================================================================
# LOAD THE MODULE UNDER TEST
# ==============================================================================
import pytest
import numpy as np
from scipy import stats as scipy_stats

_S06_PATH = os.path.join(
    _ROOT, "Spyder", "SpyderS_Signals", "SpyderS06_SKEWCalculator.py"
)
_spec = _ilu.spec_from_file_location("_s06_module", _S06_PATH)
_s06_mod = _ilu.module_from_spec(_spec)   # type: ignore[arg-type]
_spec.loader.exec_module(_s06_mod)         # type: ignore[union-attr]

# Pull names we need for tests
OptionData            = _s06_mod.OptionData
SKEWCalculation       = _s06_mod.SKEWCalculation
SKEWComponents        = _s06_mod.SKEWComponents
SpyderS06_SKEWCalculator = _s06_mod.SpyderS06_SKEWCalculator
DataUnavailableError  = _s06_mod.DataUnavailableError
create_skew_calculator = _s06_mod.create_skew_calculator
get_skew_calculator   = _s06_mod.get_skew_calculator

# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================

def _make_calc(skew=120.0, spot=550.0, strikes=20, confidence=0.95) -> SKEWCalculation:
    return SKEWCalculation(
        skew_index=skew,
        timestamp=datetime.now(),
        spot_price=spot,
        risk_free_rate=0.05,
        expiry_used=datetime.now() + timedelta(days=30),
        strikes_used=strikes,
        put_skew=0.03,
        call_skew=-0.01,
        third_moment=-0.25,
        confidence=confidence,
        calculation_time=12.5,
    )


def _make_option(
    strike: float = 550.0,
    option_type: str = "call",
    moneyness: float = 1.0,
    iv: float = 0.20,
    delta: float = 0.50,
    volume: int = 1000,
    oi: int = 5000,
    bid: float = 1.90,
    ask: float = 2.10,
    dte_years: float = 30 / 365,
) -> OptionData:
    mid = (bid + ask) / 2
    return OptionData(
        strike=strike,
        expiry=datetime.now() + timedelta(days=int(dte_years * 365)),
        option_type=option_type,
        bid=bid,
        ask=ask,
        mid=mid,
        last=mid,
        volume=volume,
        open_interest=oi,
        implied_volatility=iv,
        delta=delta,
        gamma=0.01,
        theta=-0.05,
        vega=0.30,
        moneyness=moneyness,
        time_to_expiry=dte_years,
    )


def _make_synthetic_chain(spot=550.0, atm_iv=0.20, n_strikes=7, dte_years=30 / 365):
    """Return a list of OptionData objects forming a full smile around spot."""
    offsets = [-15, -10, -5, 0, 5, 10, 15][:n_strikes]
    options = []
    for offset in offsets:
        k = spot + offset
        moneyness = k / spot
        iv_smile = atm_iv + 0.003 * (offset / 5) ** 2  # simple smile
        # calls
        d1 = (math.log(spot / k) + (0.05 + 0.5 * iv_smile ** 2) * dte_years) / (
            iv_smile * math.sqrt(dte_years)
        )
        delta_c = scipy_stats.norm.cdf(d1)
        options.append(_make_option(
            strike=k, option_type="call", moneyness=moneyness, iv=iv_smile,
            delta=delta_c, dte_years=dte_years,
        ))
        # puts
        options.append(_make_option(
            strike=k, option_type="put", moneyness=moneyness, iv=iv_smile,
            delta=delta_c - 1, dte_years=dte_years,
        ))
    return options


@pytest.fixture()
def calc() -> SpyderS06_SKEWCalculator:
    """Fresh SKEW Calculator with no external connections."""
    c = SpyderS06_SKEWCalculator()
    c.spot_price = 550.0
    return c


# ==============================================================================
# 1. DATA CLASSES
# ==============================================================================

class TestOptionData:
    def test_creation_all_fields(self):
        od = _make_option(strike=450.0, option_type="put", moneyness=0.95)
        assert od.strike == 450.0
        assert od.option_type == "put"
        assert od.moneyness == 0.95
        assert od.mid == pytest.approx((od.bid + od.ask) / 2)

    def test_time_to_expiry_positive(self):
        od = _make_option(dte_years=45 / 365)
        assert od.time_to_expiry > 0

    def test_call_and_put_types_accepted(self):
        c = _make_option(option_type="call")
        p = _make_option(option_type="put")
        assert c.option_type == "call"
        assert p.option_type == "put"


class TestSKEWCalculation:
    def test_metadata_defaults_to_empty_dict(self):
        sc = _make_calc()
        assert isinstance(sc.metadata, dict)
        assert len(sc.metadata) == 0

    def test_metadata_custom_values_preserved(self):
        sc = _make_calc()
        sc.metadata["source"] = "synthetic"
        assert sc.metadata["source"] == "synthetic"

    def test_skew_index_value(self):
        sc = _make_calc(skew=132.5)
        assert sc.skew_index == pytest.approx(132.5)

    def test_confidence_range(self):
        sc = _make_calc(confidence=0.87)
        assert 0.0 <= sc.confidence <= 1.0

    def test_calculation_time_positive(self):
        sc = _make_calc()
        assert sc.calculation_time > 0

    def test_strikes_used_integer(self):
        sc = _make_calc(strikes=18)
        assert isinstance(sc.strikes_used, int)
        assert sc.strikes_used == 18


class TestSKEWComponents:
    def test_creation_and_wing_lengths(self):
        sc = SKEWComponents(
            spot=550.0, forward=552.0, atm_volatility=0.20,
            risk_neutral_skew=-0.30, risk_neutral_kurtosis=4.1,
            put_wing=[(535.0, 0.23), (520.0, 0.27)],
            call_wing=[(565.0, 0.17), (580.0, 0.15)],
            interpolation_quality=0.96,
        )
        assert sc.spot == pytest.approx(550.0)
        assert len(sc.put_wing) == 2
        assert len(sc.call_wing) == 2

    def test_empty_wings_allowed(self):
        sc = SKEWComponents(
            spot=500.0, forward=501.0, atm_volatility=0.18,
            risk_neutral_skew=0.0, risk_neutral_kurtosis=3.0,
            put_wing=[], call_wing=[],
            interpolation_quality=0.5,
        )
        assert sc.put_wing == []
        assert sc.call_wing == []

    def test_interpolation_quality_range(self):
        sc = SKEWComponents(
            spot=550.0, forward=552.0, atm_volatility=0.20,
            risk_neutral_skew=-0.1, risk_neutral_kurtosis=3.2,
            put_wing=[(540.0, 0.21)], call_wing=[(560.0, 0.19)],
            interpolation_quality=0.88,
        )
        assert 0.0 <= sc.interpolation_quality <= 1.0


# ==============================================================================
# 2. INITIALISATION & CONFIGURATION
# ==============================================================================

class TestInitialisation:
    def test_no_args_creates_instance(self):
        c = SpyderS06_SKEWCalculator()
        assert c is not None

    def test_config_merges_with_defaults(self):
        c = SpyderS06_SKEWCalculator(config={"target_days": 45})
        assert c.config["target_days"] == 45
        # Defaults still present
        assert c.config["min_days"] == _s06_mod.MIN_DAYS

    def test_default_risk_free_rate(self):
        c = SpyderS06_SKEWCalculator()
        assert c.risk_free_rate == pytest.approx(_s06_mod.RISK_FREE_RATE)

    def test_initial_state_is_none(self):
        c = SpyderS06_SKEWCalculator()
        assert c.current_skew is None
        assert c.last_calculation is None
        assert c.spot_price is None

    def test_history_deque_empty_initially(self):
        c = SpyderS06_SKEWCalculator()
        assert len(c.skew_history) == 0

    def test_metrics_initialised(self):
        c = SpyderS06_SKEWCalculator()
        assert c.metrics["calculations"] == 0
        assert c.metrics["cache_hits"] == 0
        assert c.metrics["errors"] == 0

    def test_executor_created(self):
        c = SpyderS06_SKEWCalculator()
        assert c.executor is not None

    def test_lock_is_rlock(self):
        c = SpyderS06_SKEWCalculator()
        assert c.lock is not None

    def test_custom_interpolation_method_stored(self):
        c = SpyderS06_SKEWCalculator(config={"interpolation_method": "linear"})
        assert c.config["interpolation_method"] == "linear"

    def test_cache_ttl_override(self):
        c = SpyderS06_SKEWCalculator(config={"cache_ttl": 300})
        assert c.config["cache_ttl"] == 300


# ==============================================================================
# 3. BLACK-SCHOLES MATH
# ==============================================================================

class TestBlackScholesPricing:
    """Black-Scholes prices must satisfy known analytical identities."""

    def test_call_price_positive(self, calc):
        p = calc._black_scholes_price(550.0, 540.0, 0.05, 0.20, 30 / 365, "call")
        assert p > 0

    def test_put_price_positive(self, calc):
        p = calc._black_scholes_price(550.0, 560.0, 0.05, 0.20, 30 / 365, "put")
        assert p > 0

    def test_deep_itm_call_near_intrinsic(self, calc):
        """Deep ITM call ≈ max(S − K*exp(−rT), 0)."""
        S, K, r, T = 550.0, 400.0, 0.05, 30 / 365
        intrinsic = S - K * math.exp(-r * T)
        p = calc._black_scholes_price(S, K, r, 0.20, T, "call")
        assert p == pytest.approx(intrinsic, abs=2.0)

    def test_deep_otm_call_near_zero(self, calc):
        p = calc._black_scholes_price(550.0, 700.0, 0.05, 0.20, 30 / 365, "call")
        assert p < 0.10

    def test_put_call_parity(self, calc):
        """C − P = S − K * exp(−rT)  (no dividends)."""
        S, K, r, vol, T = 550.0, 550.0, 0.05, 0.20, 30 / 365
        C = calc._black_scholes_price(S, K, r, vol, T, "call")
        P = calc._black_scholes_price(S, K, r, vol, T, "put")
        lhs = C - P
        rhs = S - K * math.exp(-r * T)
        assert lhs == pytest.approx(rhs, abs=0.01)

    def test_zero_vol_call_intrinsic(self, calc):
        """With zero vol, call ≈ max(S − K*exp(−rT), 0)."""
        S, K, r, T = 570.0, 550.0, 0.05, 0.25
        intrinsic = max(S - K * math.exp(-r * T), 0.0)
        p = calc._black_scholes_price(S, K, r, 0.001, T, "call")
        assert p == pytest.approx(intrinsic, abs=0.05)

    def test_returns_zero_floor_not_negative(self, calc):
        """Price must never be negative."""
        p = calc._black_scholes_price(550.0, 700.0, 0.05, 0.001, 0.001, "call")
        assert p >= 0.0


class TestBlackScholesVega:
    def test_vega_positive(self, calc):
        v = calc._black_scholes_vega(550.0, 550.0, 0.05, 0.20, 30 / 365)
        assert v > 0

    def test_vega_decreases_far_otm(self, calc):
        v_atm = calc._black_scholes_vega(550.0, 550.0, 0.05, 0.20, 30 / 365)
        v_otm = calc._black_scholes_vega(550.0, 700.0, 0.05, 0.20, 30 / 365)
        assert v_atm > v_otm

    def test_vega_matches_analytical(self, calc):
        """Vega = S * N'(d1) * sqrt(T)."""
        S, K, r, vol, T = 550.0, 550.0, 0.05, 0.20, 30 / 365
        d1 = (math.log(S / K) + (r + 0.5 * vol ** 2) * T) / (vol * math.sqrt(T))
        expected = S * scipy_stats.norm.pdf(d1) * math.sqrt(T)
        v = calc._black_scholes_vega(S, K, r, vol, T)
        assert v == pytest.approx(expected, rel=1e-6)


# ==============================================================================
# 4. DELTA CALCULATION
# ==============================================================================

class TestDeltaCalculation:
    def test_atm_call_delta_near_half(self, calc):
        d = calc._calculate_delta(550.0, 30 / 365, 0.20, "call")
        assert 0.45 <= d <= 0.55

    def test_atm_put_delta_near_minus_half(self, calc):
        d = calc._calculate_delta(550.0, 30 / 365, 0.20, "put")
        assert -0.55 <= d <= -0.45

    def test_call_delta_bounds(self, calc):
        d = calc._calculate_delta(550.0, 30 / 365, 0.20, "call")
        assert 0.0 < d < 1.0

    def test_put_delta_bounds(self, calc):
        d = calc._calculate_delta(550.0, 30 / 365, 0.20, "put")
        assert -1.0 < d < 0.0

    def test_deep_itm_call_delta_near_one(self, calc):
        d = calc._calculate_delta(400.0, 30 / 365, 0.20, "call")
        assert d > 0.95

    def test_deep_itm_put_delta_near_minus_one(self, calc):
        d = calc._calculate_delta(700.0, 30 / 365, 0.20, "put")
        assert d < -0.95

    def test_call_minus_put_delta_near_one(self, calc):
        """BSM identity: call_delta − put_delta = 1 (European, no dividends).

        Derivation: Δc = N(d1), Δp = N(d1)−1  ⟹  Δc − Δp = 1.
        """
        dc = calc._calculate_delta(550.0, 30 / 365, 0.20, "call")
        dp = calc._calculate_delta(550.0, 30 / 365, 0.20, "put")
        assert dc - dp == pytest.approx(1.0, abs=0.01)


# ==============================================================================
# 5. IMPLIED VOLATILITY (Newton-Raphson round-trip)
# ==============================================================================

class TestImpliedVolatility:
    def test_round_trip_atm(self, calc):
        """price → IV → BS price should recover original price."""
        target_iv = 0.22
        target_price = calc._black_scholes_price(550.0, 550.0, 0.05, target_iv, 30 / 365, "call")
        recovered_iv = calc._calculate_iv(target_price, 550.0, 30 / 365, "call")
        assert recovered_iv == pytest.approx(target_iv, abs=0.002)

    def test_round_trip_put_otm(self, calc):
        target_iv = 0.28
        target_price = calc._black_scholes_price(550.0, 530.0, 0.05, target_iv, 30 / 365, "put")
        recovered_iv = calc._calculate_iv(target_price, 530.0, 30 / 365, "put")
        assert recovered_iv == pytest.approx(target_iv, abs=0.003)

    def test_iv_above_floor(self, calc):
        iv = calc._calculate_iv(1.0, 550.0, 30 / 365, "call")
        assert iv >= _s06_mod.VOLATILITY_FLOOR

    def test_iv_below_ceiling(self, calc):
        iv = calc._calculate_iv(50.0, 550.0, 30 / 365, "call")
        assert iv <= _s06_mod.VOLATILITY_CEILING


# ==============================================================================
# 6. FORWARD PRICE (put-call parity)
# ==============================================================================

class TestForwardPrice:
    def test_forward_near_spot_atm(self, calc):
        """With realistic BSM-priced puts and calls the forward from put-call
        parity should land close to spot * exp(r*T)."""
        # Build options with realistic BS prices so C − P encodes the carry.
        spot, r, vol, T = 550.0, 0.05, 0.20, 30 / 365
        calc.spot_price = spot
        options = []
        for offset in range(-15, 20, 5):
            k = spot + offset
            c_price = calc._black_scholes_price(spot, k, r, vol, T, "call")
            p_price = calc._black_scholes_price(spot, k, r, vol, T, "put")
            options.append(_make_option(
                strike=k, option_type="call", moneyness=k / spot,
                bid=c_price * 0.98, ask=c_price * 1.02, dte_years=T))
            options.append(_make_option(
                strike=k, option_type="put", moneyness=k / spot,
                bid=p_price * 0.98, ask=p_price * 1.02, dte_years=T))
        forward = calc._calculate_forward_price(options, T)
        expected = spot * math.exp(r * T)
        assert forward == pytest.approx(expected, abs=1.5)

    def test_forward_exceeds_spot(self, calc):
        """Forward > spot for positive interest rates."""
        options = _make_synthetic_chain(spot=550.0)
        calc.spot_price = 550.0
        forward = calc._calculate_forward_price(options, 90 / 365)
        assert forward >= 550.0

    def test_forward_no_pairs_falls_back_to_spot(self, calc):
        """If no call/put pairs, fallback: forward = spot * exp(r*T)."""
        calls_only = [_make_option(strike=550.0, option_type="call")]
        calc.spot_price = 550.0
        forward = calc._calculate_forward_price(calls_only, 30 / 365)
        expected = 550.0 * math.exp(0.05 * 30 / 365)
        assert forward == pytest.approx(expected, abs=0.1)


# ==============================================================================
# 7. ATM VOLATILITY
# ==============================================================================

class TestATMVolatility:
    def test_atm_vol_near_input_iv(self, calc):
        options = _make_synthetic_chain(spot=550.0, atm_iv=0.20)
        atm_vol = calc._calculate_atm_volatility(options, 550.0)
        assert atm_vol == pytest.approx(0.20, abs=0.02)

    def test_high_iv_environment(self, calc):
        options = _make_synthetic_chain(spot=550.0, atm_iv=0.40)
        atm_vol = calc._calculate_atm_volatility(options, 550.0)
        assert 0.30 <= atm_vol <= 0.50

    def test_returns_positive(self, calc):
        options = _make_synthetic_chain(spot=550.0)
        atm_vol = calc._calculate_atm_volatility(options, 550.0)
        assert atm_vol > 0

    def test_fallback_20pct_for_empty(self, calc):
        atm_vol = calc._calculate_atm_volatility([], forward=550.0)
        assert atm_vol == pytest.approx(0.20)


# ==============================================================================
# 8. VOLATILITY INTERPOLATORS
# ==============================================================================

class TestVolatilityInterpolators:
    def test_cubic_interpolator_callable(self, calc):
        put_wing = [(535.0, 0.23), (525.0, 0.27), (515.0, 0.31), (505.0, 0.35), (495.0, 0.40)]
        call_wing = [(565.0, 0.18), (575.0, 0.17), (585.0, 0.16), (595.0, 0.15), (605.0, 0.14)]
        calc._build_volatility_interpolators(put_wing, call_wing, 550.0, 0.20)
        iv = float(calc.interpolators["volatility"](550.0))
        assert iv > 0

    def test_linear_interpolator_callable(self, calc):
        calc.config["interpolation_method"] = "linear"
        put_wing = [(540.0, 0.22), (530.0, 0.25), (520.0, 0.28), (510.0, 0.32), (500.0, 0.36)]
        call_wing = [(560.0, 0.19), (570.0, 0.17), (580.0, 0.16), (590.0, 0.15), (600.0, 0.14)]
        calc._build_volatility_interpolators(put_wing, call_wing, 550.0, 0.20)
        iv = float(calc.interpolators["volatility"](550.0))
        assert iv > 0

    def test_sabr_fallback_callable(self, calc):
        calc.config["interpolation_method"] = "sabr"
        put_wing = [(540.0, 0.22), (530.0, 0.25)]
        call_wing = [(560.0, 0.19), (570.0, 0.17)]
        calc._build_volatility_interpolators(put_wing, call_wing, 550.0, 0.20)
        iv = float(calc.interpolators["volatility"](560.0))
        assert iv > 0

    def test_sparse_points_does_not_raise(self, calc):
        """Fewer than 3 points should fall back gracefully to ATM flat vol."""
        calc._build_volatility_interpolators([(540.0, 0.22)], [], 550.0, 0.20)
        iv = float(calc.interpolators["volatility"](550.0))
        assert iv > 0


# ==============================================================================
# 9. SKEW COMPONENTS
# ==============================================================================

class TestSKEWComponents:
    def test_returns_components_with_synthetic_chain(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        calc.spot_price = 550.0
        comps = calc._calculate_skew_components(options, 30 / 365)
        assert comps is not None
        assert isinstance(comps, SKEWComponents)

    def test_atm_vol_positive(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        calc.spot_price = 550.0
        comps = calc._calculate_skew_components(options, 30 / 365)
        assert comps is not None
        assert comps.atm_volatility > 0

    def test_forward_reasonable(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        calc.spot_price = 550.0
        comps = calc._calculate_skew_components(options, 30 / 365)
        assert comps is not None
        assert 500.0 < comps.forward < 600.0

    def test_insufficient_puts_returns_none(self, calc):
        calls_only = [_make_option(strike=550.0 + i, option_type="call") for i in range(5)]
        comps = calc._calculate_skew_components(calls_only, 30 / 365)
        assert comps is None

    def test_wings_populated(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        calc.spot_price = 550.0
        comps = calc._calculate_skew_components(options, 30 / 365)
        assert comps is not None
        # At minimum some wings should be present
        assert len(comps.put_wing) + len(comps.call_wing) > 0

    def test_interpolation_quality_between_0_and_1(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        calc.spot_price = 550.0
        comps = calc._calculate_skew_components(options, 30 / 365)
        assert comps is not None
        assert 0.0 <= comps.interpolation_quality <= 1.0


# ==============================================================================
# 10. SKEW INDEX COMPUTATION
# ==============================================================================

class TestSKEWIndex:
    def _make_comps(self, skew=-0.3, atm_vol=0.20) -> SKEWComponents:
        return SKEWComponents(
            spot=550.0, forward=552.0, atm_volatility=atm_vol,
            risk_neutral_skew=skew, risk_neutral_kurtosis=3.5,
            put_wing=[(540.0, 0.22), (530.0, 0.25), (520.0, 0.28),
                      (510.0, 0.31), (500.0, 0.35)],
            call_wing=[(560.0, 0.18), (570.0, 0.16), (580.0, 0.15),
                       (590.0, 0.14), (600.0, 0.13)],
            interpolation_quality=0.95,
        )

    def test_result_is_float(self, calc):
        comps = self._make_comps()
        s = calc._compute_skew_index(comps)
        assert isinstance(s, float)

    def test_typical_skew_in_100_150(self, calc):
        comps = self._make_comps(skew=-0.30)  # −10 * (−0.30) = +3 → 103
        s = calc._compute_skew_index(comps)
        assert 100.0 <= s <= 150.0

    def test_positive_skew_value_below_base(self, calc):
        """Positive risk-neutral skew → SKEW_BASE − 10*(pos) < 100, clamped to 100."""
        comps = self._make_comps(skew=5.0)
        s = calc._compute_skew_index(comps)
        assert s >= 100.0  # floor applied

    def test_very_negative_skew_near_150(self, calc):
        """Very negative skew → formula pushes toward 150, then clamped."""
        comps = self._make_comps(skew=-5.0)  # − 10 * (−5) = +50 → 150
        s = calc._compute_skew_index(comps)
        assert s <= 150.0

    def test_high_vol_environment_increases_skew(self, calc):
        comps_normal = self._make_comps(skew=-0.30, atm_vol=0.20)
        comps_high_vol = self._make_comps(skew=-0.30, atm_vol=0.35)
        s_normal = calc._compute_skew_index(comps_normal)
        s_high_vol = calc._compute_skew_index(comps_high_vol)
        assert s_high_vol > s_normal

    def test_low_vol_environment_slightly_decreases_skew(self, calc):
        comps_normal = self._make_comps(skew=-0.30, atm_vol=0.20)
        comps_low_vol = self._make_comps(skew=-0.30, atm_vol=0.12)
        s_normal = calc._compute_skew_index(comps_normal)
        s_low_vol = calc._compute_skew_index(comps_low_vol)
        assert s_low_vol < s_normal


# ==============================================================================
# 11. THIRD & FOURTH MOMENT INTEGRATION
# ==============================================================================

class TestMomentIntegration:
    def _setup_interpolators(self, calc, atm_vol=0.20, forward=550.0):
        put_wing = [(forward - 5 * i, atm_vol + 0.005 * i) for i in range(1, 8)]
        call_wing = [(forward + 5 * i, atm_vol - 0.003 * i) for i in range(1, 8)]
        calc._build_volatility_interpolators(put_wing, call_wing, forward, atm_vol)

    def test_third_moment_returns_float(self, calc):
        self._setup_interpolators(calc)
        v = calc._calculate_third_moment(550.0, 30 / 365)
        assert isinstance(v, float)

    def test_fourth_moment_returns_float(self, calc):
        self._setup_interpolators(calc)
        v = calc._calculate_fourth_moment(550.0, 30 / 365)
        assert isinstance(v, float)

    def test_variance_positive(self, calc):
        self._setup_interpolators(calc)
        v = calc._calculate_variance(550.0, 30 / 365)
        assert v > 0

    def test_variance_floor_enforced(self, calc):
        """Variance must be ≥ 0.01 (the floor in the implementation)."""
        # Tiny vol smile
        calc._build_volatility_interpolators(
            [(540.0, 0.001)], [(560.0, 0.001)], 550.0, 0.001
        )
        v = calc._calculate_variance(550.0, 30 / 365)
        assert v >= 0.01

    def test_no_interpolator_gives_defaults(self, calc):
        # Clear interpolators
        calc.interpolators.clear()
        third = calc._calculate_third_moment(550.0, 30 / 365)
        fourth = calc._calculate_fourth_moment(550.0, 30 / 365)
        variance = calc._calculate_variance(550.0, 30 / 365)
        assert third == pytest.approx(0.0)
        assert fourth == pytest.approx(3.0)
        assert variance > 0


# ==============================================================================
# 12. CONFIDENCE SCORING
# ==============================================================================

class TestConfidenceScoring:
    def _make_comps_for_confidence(self) -> SKEWComponents:
        return SKEWComponents(
            spot=550.0, forward=552.0, atm_volatility=0.20,
            risk_neutral_skew=-0.3, risk_neutral_kurtosis=3.5,
            put_wing=[(k, 0.20 + (550 - k) * 0.001) for k in range(520, 550, 5)],
            call_wing=[(k, 0.20 - (k - 550) * 0.001) for k in range(555, 585, 5)],
            interpolation_quality=0.96,
        )

    def test_confidence_range(self, calc):
        options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        comps = self._make_comps_for_confidence()
        conf = calc._calculate_confidence(options, comps)
        assert 0.0 <= conf <= 1.0

    def test_more_strikes_higher_confidence(self, calc):
        comps = self._make_comps_for_confidence()
        few_options = _make_synthetic_chain(spot=550.0, n_strikes=3)
        many_options = _make_synthetic_chain(spot=550.0, n_strikes=7)
        c_few = calc._calculate_confidence(few_options, comps)
        c_many = calc._calculate_confidence(many_options, comps)
        assert c_many >= c_few

    def test_tight_spreads_higher_confidence(self, calc):
        comps = self._make_comps_for_confidence()
        tight = [_make_option(bid=2.0, ask=2.02) for _ in range(10)]
        wide  = [_make_option(bid=1.0, ask=3.00) for _ in range(10)]
        c_tight = calc._calculate_confidence(tight, comps)
        c_wide  = calc._calculate_confidence(wide, comps)
        assert c_tight >= c_wide


# ==============================================================================
# 13. INTERPOLATION QUALITY
# ==============================================================================

class TestInterpolationQuality:
    def test_rich_wings_near_1(self, calc):
        put_wing  = [(550 - 5 * i, 0.20 + 0.01 * i) for i in range(1, 8)]
        call_wing = [(550 + 5 * i, 0.20 - 0.005 * i) for i in range(1, 8)]
        q = calc._assess_interpolation_quality(put_wing, call_wing)
        assert q >= 0.85

    def test_sparse_wings_lower_quality(self, calc):
        q = calc._assess_interpolation_quality([(540.0, 0.22)], [(560.0, 0.18)])
        assert q < 0.95

    def test_large_vol_jump_reduces_quality(self, calc):
        """Consecutive vols differing by > 0.10 should reduce quality."""
        jagged_put = [(540.0, 0.20), (535.0, 0.35), (530.0, 0.21)]
        flat_call  = [(560.0, 0.18), (565.0, 0.17), (570.0, 0.16)]
        q_jagged = calc._assess_interpolation_quality(jagged_put, flat_call)
        flat_put = [(540.0, 0.20), (535.0, 0.22), (530.0, 0.24)]
        q_flat   = calc._assess_interpolation_quality(flat_put, flat_call)
        assert q_jagged <= q_flat

    def test_empty_wings_handled(self, calc):
        q = calc._assess_interpolation_quality([], [])
        assert 0.0 <= q <= 1.0


# ==============================================================================
# 14. CACHING
# ==============================================================================

class TestCaching:
    def test_cache_and_retrieve(self, calc):
        calc.spot_price = 550.0
        c = _make_calc()
        calc._cache_calculation(c)
        result = calc._get_cached_calculation()
        assert result is not None
        assert result.skew_index == pytest.approx(c.skew_index)

    def test_cache_miss_after_ttl(self, calc):
        calc.spot_price = 550.0
        calc.config["cache_ttl"] = 0  # Expire immediately
        c = _make_calc()
        calc._cache_calculation(c)
        time.sleep(0.01)
        result = calc._get_cached_calculation()
        assert result is None

    def test_cache_key_changes_with_spot(self, calc):
        calc.spot_price = 550.0
        key1 = calc._generate_cache_key()
        calc.spot_price = 560.0
        key2 = calc._generate_cache_key()
        assert key1 != key2

    def test_cache_eviction_at_100_entries(self, calc):
        """Cache should not grow beyond 100 entries."""
        for i in range(105):
            calc.spot_price = 500.0 + i
            calc._cache_calculation(_make_calc(skew=100.0 + i))
        assert len(calc.calculation_cache) <= 100

    def test_cache_key_is_hex_string(self, calc):
        calc.spot_price = 550.0
        key = calc._generate_cache_key()
        # MD5 hex = 32 lowercase hex characters
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


# ==============================================================================
# 15. HISTORY & STATISTICS
# ==============================================================================

class TestHistoryAndStatistics:
    def _populate_history(self, calc, n=10):
        for i in range(n):
            calc.skew_history.append(_make_calc(skew=110.0 + i))

    def test_get_history_default_100(self, calc):
        self._populate_history(calc, 5)
        h = calc.get_history()
        assert len(h) == 5

    def test_get_history_limited_by_periods(self, calc):
        self._populate_history(calc, 10)
        h = calc.get_history(periods=3)
        assert len(h) == 3

    def test_get_history_returns_most_recent(self, calc):
        self._populate_history(calc, 10)
        h = calc.get_history(periods=1)
        assert h[0].skew_index == pytest.approx(119.0)  # last value 110+9

    def test_get_statistics_mean_correct(self, calc):
        self._populate_history(calc, 10)
        calc.current_skew = 115.0
        stats = calc.get_statistics()
        assert stats["mean"] == pytest.approx(114.5, abs=0.1)  # mean of 110..119

    def test_get_statistics_empty_returns_empty_dict(self, calc):
        stats = calc.get_statistics()
        assert stats == {}

    def test_get_statistics_one_entry_returns_empty(self, calc):
        calc.skew_history.append(_make_calc(skew=115.0))
        stats = calc.get_statistics()
        assert stats == {}

    def test_statistics_min_max_correct(self, calc):
        self._populate_history(calc, 10)
        calc.current_skew = 115.0
        stats = calc.get_statistics()
        assert stats["min"] == pytest.approx(110.0)
        assert stats["max"] == pytest.approx(119.0)


# ==============================================================================
# 16. PERFORMANCE METRICS
# ==============================================================================

class TestPerformanceMetrics:
    def test_metrics_structure(self, calc):
        m = calc.get_performance_metrics()
        assert "calculations" in m
        assert "cache_hits" in m
        assert "errors" in m

    def test_cache_hit_rate_zero_initially(self, calc):
        m = calc.get_performance_metrics()
        # No calculations yet → no cache_hit_rate key
        assert m["calculations"] == 0

    def test_cache_hit_rate_after_hits(self, calc):
        calc.metrics["calculations"] = 10
        calc.metrics["cache_hits"] = 4
        m = calc.get_performance_metrics()
        assert m["cache_hit_rate"] == pytest.approx(0.40)

    def test_error_rate_after_errors(self, calc):
        calc.metrics["calculations"] = 10
        calc.metrics["errors"] = 2
        m = calc.get_performance_metrics()
        assert m["error_rate"] == pytest.approx(0.20)

    def test_avg_calc_time_calculated(self, calc):
        calc.metrics["calculations"] = 5
        calc.metrics["calculation_times"].extend([10.0, 20.0, 30.0])
        m = calc.get_performance_metrics()
        assert m["avg_calc_time"] == pytest.approx(20.0)


# ==============================================================================
# 17. PUBLIC INTERFACE GETTERS
# ==============================================================================

class TestPublicInterface:
    def test_get_current_skew_none_initially(self, calc):
        assert calc.get_current_skew() is None

    def test_get_current_skew_after_set(self, calc):
        calc.current_skew = 125.5
        assert calc.get_current_skew() == pytest.approx(125.5)

    def test_get_last_calculation_none_initially(self, calc):
        assert calc.get_last_calculation() is None

    def test_get_components_none_initially(self, calc):
        assert calc.get_components() is None


# ==============================================================================
# 18. DATA UNAVAILABLE ERROR
# ==============================================================================

class TestDataUnavailableError:
    def test_simulated_raises_error(self, calc):
        """_calculate_skew_simulated must raise DataUnavailableError, not return fake values."""
        with pytest.raises(DataUnavailableError):
            calc._calculate_skew_simulated()

    def test_calculate_skew_no_data_raises(self, calc):
        """calculate_skew() with no data and no provider raises DataUnavailableError."""
        with patch.object(calc, "_fetch_spot_price", return_value=None), \
             patch.object(calc, "_fetch_option_chain", return_value=None):
            with pytest.raises(DataUnavailableError):
                calc.calculate_skew()

    def test_error_message_contains_context(self, calc):
        try:
            calc._calculate_skew_simulated()
        except DataUnavailableError as exc:
            assert "options chain" in str(exc).lower() or "unavailable" in str(exc).lower()

    def test_is_runtime_error_subclass(self):
        assert issubclass(DataUnavailableError, RuntimeError)


# ==============================================================================
# 19. FULL END-TO-END calculate_skew() WITH INJECTED DATA
# ==============================================================================

class TestEndToEndCalculateSkew:
    """Inject a synthetic options chain; verify the full pipeline produces a
    valid SKEWCalculation without touching any network or filesystem."""

    def _build_chain_df(self, spot=550.0, n=12):
        """Build a synthetic option chain DataFrame with ≥10 calls and ≥10 puts.

        Uses realistic Black-Scholes mid-prices so put-call parity is respected.
        """
        import pandas as pd
        # Ensure at least 12 rows per side regardless of caller's n
        n = max(n, 12)
        calc_tmp = SpyderS06_SKEWCalculator()
        calc_tmp.spot_price = spot
        r, vol, T = 0.05, 0.20, 30 / 365
        today = datetime.now()
        expiry_str = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        offsets = [i * 5 - (n // 2) * 5 for i in range(n)]
        rows_c, rows_p = [], []
        for offset in offsets:
            k = spot + offset
            iv = 0.20 + 0.003 * (offset / 5) ** 2
            cp = calc_tmp._black_scholes_price(spot, k, r, vol, T, "call")
            pp = calc_tmp._black_scholes_price(spot, k, r, vol, T, "put")
            rows_c.append({"strike": k, "bid": round(cp * 0.98, 3),
                           "ask": round(cp * 1.02, 3), "lastPrice": round(cp, 3),
                           "impliedVolatility": iv, "openInterest": 5000,
                           "volume": 1500, "expiry": expiry_str})
            rows_p.append({"strike": k, "bid": round(pp * 0.98, 3),
                           "ask": round(pp * 1.02, 3), "lastPrice": round(pp, 3),
                           "impliedVolatility": iv, "openInterest": 5000,
                           "volume": 1500, "expiry": expiry_str})
        calls = pd.DataFrame(rows_c)
        puts  = pd.DataFrame(rows_p)
        return {"calls": calls, "puts": puts}

    def test_returns_skew_calculation(self, calc):
        chain = self._build_chain_df()
        result = calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert isinstance(result, SKEWCalculation)

    def test_skew_index_in_valid_range(self, calc):
        chain = self._build_chain_df()
        result = calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert 100.0 <= result.skew_index <= 155.0

    def test_calculation_time_recorded(self, calc):
        chain = self._build_chain_df()
        result = calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert result.calculation_time > 0

    def test_spot_price_stored(self, calc):
        chain = self._build_chain_df(spot=560.0)
        result = calc.calculate_skew(option_chain=chain, spot_price=560.0)
        assert result.spot_price == pytest.approx(560.0)

    def test_result_cached(self, calc):
        chain = self._build_chain_df()
        calc.calculate_skew(option_chain=chain, spot_price=550.0)
        cached = calc._get_cached_calculation()
        assert cached is not None

    def test_result_appended_to_history(self, calc):
        chain = self._build_chain_df()
        calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert len(calc.skew_history) == 1

    def test_strikes_used_positive(self, calc):
        chain = self._build_chain_df()
        result = calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert result.strikes_used > 0

    def test_confidence_in_valid_range(self, calc):
        chain = self._build_chain_df()
        result = calc.calculate_skew(option_chain=chain, spot_price=550.0)
        assert 0.0 <= result.confidence <= 1.0

    def test_multiple_calls_grow_history(self, calc):
        chain = self._build_chain_df()
        for s in [548.0, 550.0, 552.0]:
            calc.calculate_skew(option_chain=chain, spot_price=s)
        assert len(calc.skew_history) >= 2

    def test_high_vol_scenario(self, calc):
        """High IV environment should produce valid SKEW in range."""
        chain = self._build_chain_df(spot=480.0, n=12)
        # Simulate high vol by inflating IVs
        chain["calls"] = chain["calls"].copy()
        chain["puts"]  = chain["puts"].copy()
        chain["calls"]["impliedVolatility"] *= 2.5
        chain["puts"]["impliedVolatility"]  *= 2.5
        result = calc.calculate_skew(option_chain=chain, spot_price=480.0)
        assert 100.0 <= result.skew_index <= 155.0


# ==============================================================================
# 20. FACTORY & SINGLETON
# ==============================================================================

class TestFactoryAndSingleton:
    def test_create_skew_calculator_returns_instance(self):
        c = create_skew_calculator()
        assert isinstance(c, SpyderS06_SKEWCalculator)

    def test_create_with_config(self):
        c = create_skew_calculator(config={"target_days": 45})
        assert c.config["target_days"] == 45

    def test_get_skew_calculator_same_instance(self):
        # Reset singleton
        _s06_mod._module_instance = None
        a = get_skew_calculator()
        b = get_skew_calculator()
        assert a is b

    def test_singleton_is_correct_type(self):
        _s06_mod._module_instance = None
        c = get_skew_calculator()
        assert isinstance(c, SpyderS06_SKEWCalculator)


# ==============================================================================
# 21. THREAD SAFETY
# ==============================================================================

class TestThreadSafety:
    def test_concurrent_cache_writes_no_exception(self, calc):
        """Multiple threads caching simultaneously must not raise."""
        errors = []

        def _worker(i):
            try:
                calc.spot_price = 550.0 + i
                calc._cache_calculation(_make_calc(skew=110.0 + i))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []

    def test_concurrent_reads_no_exception(self, calc):
        calc.spot_price = 550.0
        calc._cache_calculation(_make_calc())
        errors = []

        def _reader():
            try:
                calc._get_cached_calculation()
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


# ==============================================================================
# 22. EDGE CASES & ROBUSTNESS
# ==============================================================================

class TestEdgeCases:
    def test_bs_price_handles_zero_vol(self, calc):
        """Near-zero vol must not raise (division guard)."""
        p = calc._black_scholes_price(550.0, 550.0, 0.05, 1e-9, 30 / 365, "call")
        assert p >= 0

    def test_bs_price_very_long_dated(self, calc):
        p = calc._black_scholes_price(550.0, 550.0, 0.05, 0.20, 5.0, "call")
        assert p > 0

    def test_delta_zero_time_returns_float(self, calc):
        """DTE very close to zero should return without raising."""
        d = calc._calculate_delta(550.0, 1e-6, 0.20, "call")
        assert isinstance(d, float)

    def test_forward_empty_options_list(self, calc):
        """No options → fallback to spot * exp(r*T)."""
        calc.spot_price = 550.0
        f = calc._calculate_forward_price([], 30 / 365)
        expected = 550.0 * math.exp(0.05 * 30 / 365)
        assert f == pytest.approx(expected, abs=0.1)

    def test_calculate_skew_insufficient_puts_raises(self, calc):
        """Fewer than 10 puts in the chain → DataUnavailableError (simulated fallback)."""
        import pandas as pd
        small_chain = {
            "calls": pd.DataFrame([{"strike": 550 + i, "bid": 1.9, "ask": 2.1,
                                     "lastPrice": 2.0, "impliedVolatility": 0.20,
                                     "openInterest": 100, "volume": 50,
                                     "expiry": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")} for i in range(15)]),
            "puts": pd.DataFrame([{"strike": 550 - i, "bid": 1.9, "ask": 2.1,
                                    "lastPrice": 2.0, "impliedVolatility": 0.20,
                                    "openInterest": 100, "volume": 50,
                                    "expiry": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")} for i in range(5)]),
        }
        with pytest.raises(DataUnavailableError):
            calc.calculate_skew(option_chain=small_chain, spot_price=550.0)

    def test_sabr_vol_returns_float(self, calc):
        v = calc._sabr_volatility(560.0, 550.0, 0.20)
        assert isinstance(v, float)
        assert v > 0


# ==============================================================================
# 23. SAVE HISTORY (filesystem — use temp dir)
# ==============================================================================

class TestSaveHistory:
    def test_save_does_not_raise(self, calc):
        """save_history() with populated deque should complete without error."""
        for i in range(3):
            calc.skew_history.append(_make_calc(skew=110.0 + i))
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_file = _s06_mod.HISTORY_FILE
            _s06_mod.HISTORY_FILE = type(orig_file)(tmpdir) / "skew_history.csv"
            try:
                calc.save_history()
            finally:
                _s06_mod.HISTORY_FILE = orig_file

    def test_save_empty_history_does_not_raise(self, calc):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_file = _s06_mod.HISTORY_FILE
            _s06_mod.HISTORY_FILE = type(orig_file)(tmpdir) / "skew_history.csv"
            try:
                calc.save_history()  # empty deque
            finally:
                _s06_mod.HISTORY_FILE = orig_file
