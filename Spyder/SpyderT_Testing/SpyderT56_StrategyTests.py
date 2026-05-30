#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT56_StrategyTests.py
Purpose: Unit tests for D-series strategy framework (item A)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Covers the core D-series strategy modules with no broker or GUI
    dependencies:
      - SpyderD00_StrategyConstants  — enums, constants, validate_constant
      - SpyderD01_BaseStrategy       — TradingSignal, StrategyPosition,
                                       RiskProfile, PerformanceMetrics
      - SpyderD03_CreditSpread       — CreditSpread dataclass properties
      - SpyderD04_ZeroDTE            — ZeroDTEPosition, MarketConditions
      - SpyderD05_Straddle           — StraddlePosition properties

Change Log:
    2026-03-03:
        - Created (item A: strategy test suite)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import importlib.util
import sys
import unittest
import uuid
from datetime import datetime, timedelta, date, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

# ==============================================================================
# PATH SETUP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(rel_path: str):
    """Load a module from a repo-relative path via importlib."""
    full = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_d00 = _load("Spyder/SpyderD_Strategies/SpyderD00_StrategyConstants.py")
_d01 = _load("Spyder/SpyderD_Strategies/SpyderD01_BaseStrategy.py")
_d03 = _load("Spyder/SpyderD_Strategies/SpyderD03_CreditSpread.py")
_d04 = _load("Spyder/SpyderD_Strategies/SpyderD04_ZeroDTE.py")
_d05 = _load("Spyder/SpyderD_Strategies/SpyderD05_Straddle.py")

# Pull names from D00
StrategyType = _d00.StrategyType
MarketRegime = _d00.MarketRegime
get_strategy_constants = _d00.get_strategy_constants
validate_constant = _d00.validate_constant

# Pull names from D01
SignalType = _d01.SignalType
SignalStrength = _d01.SignalStrength
PositionType = _d01.PositionType
PositionState = _d01.PositionState
RiskLevel = _d01.RiskLevel
TradingSignal = _d01.TradingSignal
StrategyPosition = _d01.StrategyPosition
RiskProfile = _d01.RiskProfile
PerformanceMetrics = _d01.PerformanceMetrics

# Pull names from D03
CreditSpread = _d03.CreditSpread
SpreadType = _d03.SpreadType
SpreadState = _d03.SpreadState
D03OptionLeg = _d03.OptionLeg

# Pull names from D04
ZeroDTEPosition = _d04.ZeroDTEPosition
D04ZeroDTEStrategy = getattr(_d04, "ZeroDTEStrategy", None)
D04ZeroDTEState = _d04.ZeroDTEState
MarketConditions = _d04.MarketConditions
build_zero_dte_runtime_config = _d04.build_zero_dte_runtime_config

# Pull names from D05
StraddlePosition = _d05.StraddlePosition
D05StrategyType = _d05.StrategyType
D05OptionLeg = _d05.OptionLeg


# ==============================================================================
# HELPERS
# ==============================================================================

def _make_signal(
    signal_type=None,
    strength=None,
    confidence: float = 0.8,
    expires_in_seconds: int = 60,
) -> TradingSignal:
    signal_type = signal_type or SignalType.BUY
    strength = strength or SignalStrength.STRONG
    now = datetime.now()
    return TradingSignal(
        signal_id=str(uuid.uuid4()),
        signal_type=signal_type,
        symbol="SPY",
        strength=strength,
        confidence=confidence,
        entry_price=500.0,
        stop_loss=495.0,
        take_profit=510.0,
        position_size=10,
        timestamp=now,
        expires_at=now + timedelta(seconds=expires_in_seconds),
    )


def _make_position(
    position_type=None,
    entry_price: float = 500.0,
    size: int = 10,
    state=None,
) -> StrategyPosition:
    position_type = position_type or PositionType.LONG
    state = state or PositionState.OPEN
    return StrategyPosition(
        position_id=str(uuid.uuid4()),
        strategy_name="TestStrategy",
        symbol="SPY",
        position_type=position_type,
        state=state,
        entry_time=datetime.now() - timedelta(hours=1),
        entry_price=entry_price,
        position_size=size,
        stop_loss=490.0,
        take_profit=520.0,
    )


def _make_credit_spread(
    short_strike: float = 495.0,
    long_strike: float = 490.0,
    credit_received: float = 1.50,
    max_profit: float = 150.0,
    unrealized_pnl: float = 0.0,
) -> CreditSpread:
    expiry = datetime.now() + timedelta(days=30)
    short_leg = D03OptionLeg(
        symbol="SPY240315P495",
        strike=short_strike,
        expiry=expiry,
        option_type="put",
        position="short",
        quantity=1,
        entry_price=1.50,
        current_price=0.80,
        delta=-0.20,
        gamma=0.02,
        theta=0.10,
        vega=0.15,
        iv=0.22,
    )
    long_leg = D03OptionLeg(
        symbol="SPY240315P490",
        strike=long_strike,
        expiry=expiry,
        option_type="put",
        position="long",
        quantity=1,
        entry_price=0.75,
        current_price=0.40,
        delta=-0.10,
        gamma=0.01,
        theta=0.05,
        vega=0.08,
        iv=0.23,
    )
    return CreditSpread(
        spread_id=str(uuid.uuid4()),
        spread_type=SpreadType.BULL_PUT,
        short_leg=short_leg,
        long_leg=long_leg,
        entry_time=datetime.now() - timedelta(days=5),
        expiry=expiry,
        quantity=1,
        state=SpreadState.ACTIVE,
        credit_received=credit_received,
        max_profit=max_profit,
        unrealized_pnl=unrealized_pnl,
    )


def _make_straddle_position(
    strategy_type=None,
    call_strike: float = 500.0,
    put_strike: float = 500.0,
    total_debit: float = 10.0,
    total_credit: float = 0.0,
) -> StraddlePosition:
    strategy_type = strategy_type or D05StrategyType.LONG_STRADDLE
    expiry = datetime.now() + timedelta(days=20)
    call_leg = D05OptionLeg(
        symbol="SPY240315C500",
        strike=call_strike,
        expiry=expiry,
        option_type="call",
        position="long",
        quantity=1,
        entry_price=5.0,
        current_price=5.5,
        delta=0.50,
        gamma=0.02,
        theta=-0.10,
        vega=0.25,
        iv=0.20,
    )
    put_leg = D05OptionLeg(
        symbol="SPY240315P500",
        strike=put_strike,
        expiry=expiry,
        option_type="put",
        position="long",
        quantity=1,
        entry_price=5.0,
        current_price=4.8,
        delta=-0.50,
        gamma=0.02,
        theta=-0.10,
        vega=0.25,
        iv=0.20,
    )
    return StraddlePosition(
        position_id=str(uuid.uuid4()),
        strategy_type=strategy_type,
        call_leg=call_leg,
        put_leg=put_leg,
        entry_time=datetime.now() - timedelta(hours=2),
        expiry=expiry,
        quantity=1,
        total_debit=total_debit,
        total_credit=total_credit,
    )


# ==============================================================================
# 1. STRATEGY CONSTANTS (D00)
# ==============================================================================


class TestStrategyConstants(unittest.TestCase):

    def test_strategy_type_enum_members(self):
        names = {e.name for e in StrategyType}
        # Core strategies must be present
        for required in ("IRON_CONDOR", "CREDIT_SPREAD", "STRADDLE", "CONDOR"):
            self.assertIn(required, names)

    def test_market_regime_enum_members(self):
        names = {e.name for e in MarketRegime}
        self.assertGreaterEqual(len(names), 3)  # LOW_VOL, NORMAL, HIGH_VOL, etc.

    def test_get_strategy_constants_returns_dict(self):
        result = get_strategy_constants()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_get_strategy_constants_contains_risk_keys(self):
        result = get_strategy_constants()
        for key in ("MAX_PORTFOLIO_RISK", "MAX_POSITIONS"):
            self.assertIn(key, result)

    def test_validate_constant_returns_bool(self):
        result = validate_constant("MAX_PORTFOLIO_RISK", 0.02)
        self.assertIsInstance(result, bool)

    def test_validate_constant_valid_value(self):
        # 0.02 is valid for a float constant (non-negative, < 1)
        result = validate_constant("MAX_PORTFOLIO_RISK", 0.02)
        # Implementation returns True for valid constants
        self.assertTrue(result)

    def test_validate_constant_invalid_value(self):
        # 'delta' range is (-1.0, 1.0) — 1.5 is outside and should be invalid
        result = validate_constant("delta", 1.5)
        self.assertFalse(result)

    def test_module_constants_are_positive(self):
        self.assertGreater(_d00.MAX_PORTFOLIO_RISK, 0)
        self.assertGreater(_d00.MAX_POSITIONS, 0)
        self.assertGreater(_d00.MAX_POSITION_SIZE, 0)


# ==============================================================================
# 2. TRADING SIGNAL (D01)
# ==============================================================================


class TestTradingSignal(unittest.TestCase):

    def test_construction(self):
        sig = _make_signal()
        self.assertEqual(sig.symbol, "SPY")
        self.assertAlmostEqual(sig.confidence, 0.8)

    def test_is_valid_for_unexpired_signal(self):
        sig = _make_signal(expires_in_seconds=3600)
        self.assertTrue(sig.is_valid())

    def test_is_invalid_for_expired_signal(self):
        sig = _make_signal(expires_in_seconds=-1)
        self.assertFalse(sig.is_valid())

    def test_to_dict_keys(self):
        sig = _make_signal()
        d = sig.to_dict()
        for key in (
            "signal_id", "signal_type", "symbol", "strength", "confidence",
            "entry_price", "stop_loss", "take_profit", "position_size",
            "timestamp", "expires_at",
        ):
            self.assertIn(key, d)

    def test_to_dict_signal_type_is_string(self):
        sig = _make_signal(signal_type=SignalType.BUY)
        self.assertEqual(sig.to_dict()["signal_type"], "buy")

    def test_to_dict_strength_is_string(self):
        sig = _make_signal(strength=SignalStrength.STRONG)
        self.assertEqual(sig.to_dict()["strength"], "strong")

    def test_metadata_defaults_to_empty_dict(self):
        sig = _make_signal()
        self.assertEqual(sig.metadata, {})

    def test_all_signal_types_valid(self):
        for sig_type in SignalType:
            s = _make_signal(signal_type=sig_type)
            self.assertEqual(s.signal_type, sig_type)

    def test_all_signal_strengths_valid(self):
        for strength in SignalStrength:
            s = _make_signal(strength=strength)
            self.assertEqual(s.strength, strength)


# ==============================================================================
# 3. STRATEGY POSITION (D01)
# ==============================================================================


class TestStrategyPositionUpdatePnL(unittest.TestCase):

    def test_long_position_profit(self):
        pos = _make_position(position_type=PositionType.LONG, entry_price=500.0, size=10)
        pos.update_pnl(510.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 100.0)
        self.assertAlmostEqual(pos.current_price, 510.0)

    def test_long_position_loss(self):
        pos = _make_position(position_type=PositionType.LONG, entry_price=500.0, size=10)
        pos.update_pnl(490.0)
        self.assertAlmostEqual(pos.unrealized_pnl, -100.0)

    def test_short_position_profit(self):
        pos = _make_position(position_type=PositionType.SHORT, entry_price=500.0, size=10)
        pos.update_pnl(490.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 100.0)

    def test_short_position_loss(self):
        pos = _make_position(position_type=PositionType.SHORT, entry_price=500.0, size=10)
        pos.update_pnl(510.0)
        self.assertAlmostEqual(pos.unrealized_pnl, -100.0)

    def test_breakeven_gives_zero_pnl(self):
        pos = _make_position(position_type=PositionType.LONG, entry_price=500.0, size=5)
        pos.update_pnl(500.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 0.0)


class TestStrategyPositionClose(unittest.TestCase):

    def test_close_long_position_profit(self):
        pos = _make_position(position_type=PositionType.LONG, entry_price=500.0, size=10)
        pos.close_position(510.0, "take_profit")
        self.assertEqual(pos.state, PositionState.CLOSED)
        self.assertAlmostEqual(pos.realized_pnl, 100.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 0.0)
        self.assertEqual(pos.exit_reason, "take_profit")
        self.assertIsNotNone(pos.exit_time)

    def test_close_short_position_profit(self):
        pos = _make_position(position_type=PositionType.SHORT, entry_price=500.0, size=10)
        pos.close_position(490.0, "take_profit")
        self.assertAlmostEqual(pos.realized_pnl, 100.0)
        self.assertEqual(pos.state, PositionState.CLOSED)

    def test_close_long_position_loss(self):
        pos = _make_position(position_type=PositionType.LONG, entry_price=500.0, size=10)
        pos.close_position(490.0, "stop_loss")
        self.assertAlmostEqual(pos.realized_pnl, -100.0)

    def test_exit_price_set_on_close(self):
        pos = _make_position()
        pos.close_position(505.0, "manual")
        self.assertAlmostEqual(pos.exit_price, 505.0)


# ==============================================================================
# 4. RISK PROFILE (D01)
# ==============================================================================


class TestRiskProfile(unittest.TestCase):

    def setUp(self):
        self.profile = RiskProfile(account_size=100_000.0, max_position_size=0.10)

    def test_weak_signal_half_base(self):
        size = self.profile.calculate_position_size(SignalStrength.WEAK)
        self.assertAlmostEqual(size, 5_000.0)   # 100k * 0.10 * 0.5

    def test_moderate_signal(self):
        size = self.profile.calculate_position_size(SignalStrength.MODERATE)
        self.assertAlmostEqual(size, 7_500.0)   # 100k * 0.10 * 0.75

    def test_strong_signal_full_base(self):
        size = self.profile.calculate_position_size(SignalStrength.STRONG)
        self.assertAlmostEqual(size, 10_000.0)  # 100k * 0.10 * 1.0

    def test_very_strong_signal_exceeds_base(self):
        size = self.profile.calculate_position_size(SignalStrength.VERY_STRONG)
        self.assertAlmostEqual(size, 12_500.0)  # 100k * 0.10 * 1.25

    def test_monotonic_sizing(self):
        sizes = [
            self.profile.calculate_position_size(s) for s in SignalStrength
        ]
        self.assertEqual(sizes, sorted(sizes))

    def test_position_size_always_positive(self):
        for strength in SignalStrength:
            self.assertGreater(self.profile.calculate_position_size(strength), 0)


# ==============================================================================
# 5. PERFORMANCE METRICS (D01)
# ==============================================================================


class TestPerformanceMetrics(unittest.TestCase):

    def _closed_position(self, pnl: float) -> StrategyPosition:
        pos = _make_position(entry_price=500.0, size=10)
        pos.state = PositionState.CLOSED
        pos.realized_pnl = pnl
        return pos

    def test_update_with_winning_trade(self):
        metrics = PerformanceMetrics()
        pos = self._closed_position(pnl=200.0)
        metrics.update(pos)
        self.assertEqual(metrics.total_trades, 1)
        self.assertEqual(metrics.winning_trades, 1)
        self.assertEqual(metrics.losing_trades, 0)
        self.assertAlmostEqual(metrics.total_pnl, 200.0)

    def test_update_with_losing_trade(self):
        metrics = PerformanceMetrics()
        pos = self._closed_position(pnl=-100.0)
        metrics.update(pos)
        self.assertEqual(metrics.total_trades, 1)
        self.assertEqual(metrics.winning_trades, 0)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertAlmostEqual(metrics.total_pnl, -100.0)

    def test_update_ignores_open_position(self):
        metrics = PerformanceMetrics()
        pos = _make_position()  # state = OPEN
        pos.realized_pnl = 999.0
        metrics.update(pos)
        self.assertEqual(metrics.total_trades, 0)

    def test_multiple_updates(self):
        metrics = PerformanceMetrics()
        metrics.update(self._closed_position(pnl=100.0))
        metrics.update(self._closed_position(pnl=200.0))
        metrics.update(self._closed_position(pnl=-50.0))
        self.assertEqual(metrics.total_trades, 3)
        self.assertEqual(metrics.winning_trades, 2)
        self.assertEqual(metrics.losing_trades, 1)
        self.assertAlmostEqual(metrics.total_pnl, 250.0)

    def test_avg_win_computed(self):
        metrics = PerformanceMetrics()
        metrics.update(self._closed_position(pnl=100.0))
        metrics.update(self._closed_position(pnl=300.0))
        self.assertAlmostEqual(metrics.average_win, 200.0)

    def test_initial_state_zeros(self):
        metrics = PerformanceMetrics()
        self.assertEqual(metrics.total_trades, 0)
        self.assertAlmostEqual(metrics.total_pnl, 0.0)


# ==============================================================================
# 6. CREDIT SPREAD DATACLASS (D03)
# ==============================================================================


class TestCreditSpreadProperties(unittest.TestCase):

    def test_spread_width(self):
        cs = _make_credit_spread(short_strike=495.0, long_strike=490.0)
        self.assertAlmostEqual(cs.spread_width, 5.0)

    def test_spread_width_always_positive(self):
        # Even if legs reversed
        cs = _make_credit_spread(short_strike=490.0, long_strike=495.0)
        self.assertGreater(cs.spread_width, 0)

    def test_credit_to_width_ratio(self):
        cs = _make_credit_spread(short_strike=495.0, long_strike=490.0, credit_received=1.50)
        # 1.50 / 5.00 = 0.30
        self.assertAlmostEqual(cs.credit_to_width_ratio, 0.30)

    def test_credit_to_width_zero_width(self):
        cs = _make_credit_spread(short_strike=495.0, long_strike=495.0, credit_received=1.0)
        self.assertEqual(cs.credit_to_width_ratio, 0)

    def test_profit_percentage_with_max_profit(self):
        cs = _make_credit_spread(max_profit=150.0, unrealized_pnl=75.0)
        self.assertAlmostEqual(cs.profit_percentage, 0.50)

    def test_profit_percentage_zero_max_profit(self):
        cs = _make_credit_spread(max_profit=0.0, unrealized_pnl=50.0)
        self.assertEqual(cs.profit_percentage, 0)

    def test_update_greeks_combines_legs(self):
        cs = _make_credit_spread()
        # short_leg: delta=-0.20, theta=0.10
        # long_leg:  delta=-0.10, theta=0.05
        cs.update_greeks()
        self.assertAlmostEqual(cs.net_delta, -0.30, places=5)
        self.assertAlmostEqual(cs.net_theta, 0.15, places=5)

    def test_update_greeks_vega(self):
        cs = _make_credit_spread()
        cs.update_greeks()
        self.assertAlmostEqual(cs.net_vega, 0.23, places=5)


# ==============================================================================
# 7. ZERO-DTE POSITION (D04)
# ==============================================================================


class TestZeroDTEPositionProperties(unittest.TestCase):

    def _make_zdp(self, max_profit: float = 150.0, unrealized_pnl: float = 0.0):
        entry_time = datetime.now() - timedelta(hours=2)
        return ZeroDTEPosition(
            position_id=str(uuid.uuid4()),
            strategy_type=None,  # ZeroDTEStrategy is abstract; unused in profit_percentage
            entry_time=entry_time,
            expiry_date=date.today(),
            strikes={"short_put": 490.0, "long_put": 485.0},
            contracts=1,
            entry_premium=2.50,
            max_profit=max_profit,
            unrealized_pnl=unrealized_pnl,
        )

    def test_profit_percentage_positive(self):
        pos = self._make_zdp(max_profit=150.0, unrealized_pnl=75.0)
        self.assertAlmostEqual(pos.profit_percentage, 0.5)

    def test_profit_percentage_zero_max(self):
        pos = self._make_zdp(max_profit=0.0)
        self.assertEqual(pos.profit_percentage, 0)

    def test_profit_percentage_full(self):
        pos = self._make_zdp(max_profit=100.0, unrealized_pnl=100.0)
        self.assertAlmostEqual(pos.profit_percentage, 1.0)


class TestMarketConditionsProperties(unittest.TestCase):

    def test_gap_percentage(self):
        # gap_percentage = overnight_gap / opening_price
        mc = MarketConditions(
            timestamp=datetime.now(),
            spot_price=500.0,
            opening_price=502.0,
            high_of_day=505.0,
            low_of_day=498.0,
            volume=50_000_000,
            vix=18.0,
            iv_rank=50.0,
            market_phase=_d04.MarketPhase.MORNING,
            trend_direction="up",
            momentum=0.5,
            overnight_gap=12.0,  # overnight_gap / opening_price = 12/502
        )
        expected_gap = 12.0 / 502.0
        self.assertAlmostEqual(mc.gap_percentage, expected_gap, places=6)

    def test_intraday_range(self):
        mc = MarketConditions(
            timestamp=datetime.now(),
            spot_price=500.0,
            opening_price=495.0,
            high_of_day=510.0,
            low_of_day=488.0,
            volume=50_000_000,
            vix=18.0,
            iv_rank=50.0,
            market_phase=_d04.MarketPhase.MORNING,
            trend_direction="sideways",
            momentum=0.0,
            overnight_gap=5.0,
        )
        self.assertAlmostEqual(mc.intraday_range, 22.0)  # 510 - 488


class TestZeroDTERuntimeConfig(unittest.TestCase):

    def test_default_runtime_config_preserves_classic_thresholds(self):
        runtime = build_zero_dte_runtime_config({})
        self.assertEqual(runtime['profile'], 'classic')
        self.assertEqual(runtime['symbol'], 'SPY')
        self.assertEqual(runtime['max_daily_trades'], _d04.ZERO_DTE_MAX_TRADES)
        self.assertEqual(runtime['entry_window_end'], _d04.time(12, 0))
        self.assertEqual(runtime['spread_width_points'], 5.0)
        self.assertEqual(runtime['min_premium'], _d04.MIN_PREMIUM)

    def test_mark_spy_paper_profile_resolves_expected_overrides(self):
        runtime = build_zero_dte_runtime_config({'profile': 'mark_spy_paper'})
        self.assertEqual(runtime['profile'], 'mark_spy_paper')
        self.assertEqual(runtime['symbol'], 'SPY')
        self.assertEqual(runtime['entry_delay_minutes'], 2)
        self.assertEqual(runtime['entry_window_end'], _d04.time(14, 30))
        self.assertEqual(runtime['time_stop'], _d04.time(15, 15))
        self.assertEqual(runtime['max_daily_trades'], 8)
        self.assertEqual(runtime['spread_width_points'], 1.0)
        self.assertAlmostEqual(runtime['short_delta_min'], 0.07)
        self.assertAlmostEqual(runtime['short_delta_max'], 0.20)
        self.assertAlmostEqual(runtime['short_delta_target'], 0.12)
        self.assertAlmostEqual(runtime['min_premium'], 0.20)


class TestZeroDTEStrikeSelection(unittest.TestCase):

    def _make_strategy(self):
        strategy = D04ZeroDTEStrategy.__new__(D04ZeroDTEStrategy)
        strategy.short_delta_min = 0.07
        strategy.short_delta_max = 0.20
        strategy.short_delta_target = 0.12
        strategy.spread_width_points = 1.0
        strategy.prefer_delta_selection = True
        return strategy

    def test_put_and_call_spread_strikes_use_delta_band_when_available(self):
        strategy = self._make_strategy()
        option_chain = pd.DataFrame(
            [
                {'option_type': 'put', 'strike': 596.0, 'delta': -0.18},
                {'option_type': 'put', 'strike': 597.0, 'delta': -0.11},
                {'option_type': 'put', 'strike': 598.0, 'delta': -0.05},
                {'option_type': 'call', 'strike': 603.0, 'delta': 0.11},
                {'option_type': 'call', 'strike': 604.0, 'delta': 0.18},
                {'option_type': 'call', 'strike': 605.0, 'delta': 0.24},
            ]
        )

        put_spread = strategy._find_put_spread_strikes(option_chain, 600.0)
        call_spread = strategy._find_call_spread_strikes(option_chain, 600.0)
        condor = strategy._find_iron_condor_strikes(option_chain, 600.0)

        self.assertEqual(put_spread, {'short_put': 597.0, 'long_put': 596.0})
        self.assertEqual(call_spread, {'short_call': 603.0, 'long_call': 604.0})
        self.assertEqual(
            condor,
            {
                'long_put': 596.0,
                'short_put': 597.0,
                'short_call': 603.0,
                'long_call': 604.0,
            },
        )


class TestZeroDTEMarketInputs(unittest.TestCase):

    def _make_strategy(self):
        strategy = D04ZeroDTEStrategy.__new__(D04ZeroDTEStrategy)
        strategy.symbol = 'SPY'
        strategy.logger = MagicMock()
        strategy.error_handler = MagicMock()
        strategy.current_conditions = None
        strategy.option_chain_cache = {}
        strategy.option_chain_cache_time = {}
        strategy._tradier_client = None
        strategy._intraday_iv_history = []
        strategy.eastern_tz = _d04.pytz.timezone('US/Eastern')
        return strategy

    def test_get_0dte_options_fetches_live_chain_and_caches(self):
        strategy = self._make_strategy()
        expiration = date.today().isoformat()
        strategy._tradier_client = MagicMock()
        strategy._tradier_client.get_option_chain_with_greeks.return_value = [
            SimpleNamespace(
                symbol='SPY250527P00597000',
                underlying='SPY',
                strike=597.0,
                expiration=expiration,
                option_type='put',
                bid=0.42,
                ask=0.46,
                last=0.44,
                mid=0.44,
                volume=120,
                open_interest=320,
                delta=-0.12,
                gamma=0.08,
                theta=-0.18,
                vega=0.02,
                iv=0.19,
            ),
            SimpleNamespace(
                symbol='SPY250528C00603000',
                underlying='SPY',
                strike=603.0,
                expiration='2099-12-31',
                option_type='call',
                bid=0.39,
                ask=0.43,
                last=0.41,
                mid=0.41,
                volume=90,
                open_interest=200,
                delta=0.11,
                gamma=0.07,
                theta=-0.16,
                vega=0.02,
                iv=0.18,
            ),
        ]

        first = strategy._get_0dte_options(pd.DataFrame())
        second = strategy._get_0dte_options(pd.DataFrame())

        self.assertEqual(len(first), 1)
        self.assertEqual(first.iloc[0]['option_type'], 'put')
        self.assertAlmostEqual(first.iloc[0]['iv'], 0.19)
        self.assertEqual(first.iloc[0]['expiration'], expiration)
        self.assertEqual(len(second), 1)
        strategy._tradier_client.get_option_chain_with_greeks.assert_called_once_with('SPY', expiration)

    def test_calculate_iv_rank_uses_rolling_atm_iv_history(self):
        strategy = self._make_strategy()
        now = datetime.now()
        strategy._intraday_iv_history = [
            (now - timedelta(days=2), 0.10),
            (now - timedelta(days=1), 0.30),
        ]

        iv_rank = strategy._calculate_iv_rank(0.20)

        self.assertAlmostEqual(iv_rank, 50.0)

    def test_update_market_conditions_prefers_supplied_volatility_inputs(self):
        strategy = self._make_strategy()
        today = date.today()
        yesterday = today - timedelta(days=1)
        timestamps = [datetime.combine(yesterday, time(15, 59))]
        timestamps.extend(
            datetime.combine(today, time(9, 30)) + timedelta(minutes=minute)
            for minute in range(25)
        )
        close_values = [598.0] + [600.0 + (minute * 0.1) for minute in range(25)]
        market_data = pd.DataFrame(
            {
                'open': [598.0] + [600.0] * 25,
                'high': [599.0] + [600.5 + (minute * 0.1) for minute in range(25)],
                'low': [597.5] + [599.5 + (minute * 0.1) for minute in range(25)],
                'close': close_values,
                'volume': [1_000_000] + [2_000_000] * 25,
                'vix': [17.5] * 26,
                'iv_rank': [42.0] * 26,
            },
            index=pd.DatetimeIndex(timestamps),
        )
        strategy._get_0dte_options = MagicMock(
            return_value=pd.DataFrame(
                [
                    {'strike': 602.0, 'iv': 0.20},
                    {'strike': 603.0, 'iv': 0.22},
                ]
            )
        )

        strategy._update_market_conditions(market_data)

        self.assertIsNotNone(strategy.current_conditions)
        self.assertAlmostEqual(strategy.current_conditions.vix, 17.5)
        self.assertAlmostEqual(strategy.current_conditions.iv_rank, 42.0)


# ==============================================================================
# 8. STRADDLE POSITION (D05)
# ==============================================================================


class TestStraddlePositionProperties(unittest.TestCase):

    def test_long_straddle_is_long(self):
        pos = _make_straddle_position(strategy_type=D05StrategyType.LONG_STRADDLE)
        self.assertTrue(pos.is_long)

    def test_short_straddle_not_long(self):
        pos = _make_straddle_position(strategy_type=D05StrategyType.SHORT_STRADDLE)
        self.assertFalse(pos.is_long)

    def test_long_strangle_is_long(self):
        pos = _make_straddle_position(strategy_type=D05StrategyType.LONG_STRANGLE)
        self.assertTrue(pos.is_long)

    def test_expected_move_long_straddle(self):
        # With same strike for call and put (500.0), debit=10
        # expected_move = 10 / ((500+500)/2) = 10/500 = 0.02
        pos = _make_straddle_position(
            strategy_type=D05StrategyType.LONG_STRADDLE,
            total_debit=10.0,
        )
        self.assertAlmostEqual(pos.expected_move, 0.02, places=6)

    def test_expected_move_positive(self):
        pos = _make_straddle_position(total_debit=15.0)
        self.assertGreater(pos.expected_move, 0)

    def test_update_greeks(self):
        pos = _make_straddle_position()
        pos.update_greeks()
        # delta = call_delta + put_delta = 0.50 + (-0.50) = 0.0
        self.assertAlmostEqual(pos.net_delta, 0.0, places=5)
        # vega: both legs long → 0.25 + 0.25 = 0.50
        self.assertAlmostEqual(pos.net_vega, 0.50, places=5)

    def test_update_breakevens_long_straddle(self):
        pos = _make_straddle_position(
            strategy_type=D05StrategyType.LONG_STRADDLE,
            call_strike=500.0,
            put_strike=500.0,
            total_debit=10.0,
        )
        pos.update_breakevens()
        self.assertAlmostEqual(pos.breakeven_up, 510.0)
        self.assertAlmostEqual(pos.breakeven_down, 490.0)

    def test_update_breakevens_long_strangle(self):
        pos = _make_straddle_position(
            strategy_type=D05StrategyType.LONG_STRANGLE,
            call_strike=505.0,
            put_strike=495.0,
            total_debit=8.0,
        )
        pos.update_breakevens()
        self.assertAlmostEqual(pos.breakeven_up, 513.0)   # 505 + 8
        self.assertAlmostEqual(pos.breakeven_down, 487.0) # 495 - 8

    def test_days_to_expiry_positive_for_future(self):
        pos = _make_straddle_position()
        self.assertGreater(pos.days_to_expiry, 0)


# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
