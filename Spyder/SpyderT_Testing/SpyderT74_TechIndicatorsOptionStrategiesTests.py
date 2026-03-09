#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT74_TechIndicatorsOptionStrategiesTests.py
Purpose: Tests for U13 TechnicalIndicators and U14 OptionStrategies

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 22:00:00
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

# U01 and U02 needed by both U13 and U14
_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

_u13 = _load("Spyder/SpyderU_Utilities/SpyderU13_TechnicalIndicators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators"] = _u13

_u14 = _load("Spyder/SpyderU_Utilities/SpyderU14_OptionStrategies.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies"] = _u14

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================================
# U13 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import (
    MAType,
    SignalType,
    TrendDirection,
    IndicatorResult,
    TrendAnalysis,
    TechnicalIndicators,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    get_technical_indicators,
    DEFAULT_RSI_PERIOD,
    DEFAULT_MACD_FAST,
    DEFAULT_MACD_SLOW,
    DEFAULT_MACD_SIGNAL,
    DEFAULT_BB_PERIOD,
    DEFAULT_BB_STDDEV,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
)

# ==============================================================================
# U14 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies import (
    OptionType,
    PositionType,
    StrategyType,
    OptionLeg,
    OptionStrategy,
    PayoffResult,
    OptionStrategies,
    get_option_strategies,
    calculate_option_payoff,
    CONTRACT_MULTIPLIER,
    RISK_FREE_RATE,
)


# ==============================================================================
# OHLCV FIXTURE
# ==============================================================================

def _make_prices(n: int = 100, base: float = 450.0, trend: float = 0.001,
                  noise: float = 1.0, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = rng.normal(trend, noise / base, n)
    prices = base * np.cumprod(1 + returns)
    return pd.Series(prices)


def _make_ohlcv(n: int = 100, seed: int = 42):
    rng = np.random.default_rng(seed)
    close = _make_prices(n=n, seed=seed)
    high = close + rng.uniform(0.2, 2.0, n)
    low = close - rng.uniform(0.2, 2.0, n)
    high = pd.Series(np.maximum(high, close.values))
    low = pd.Series(np.minimum(low, close.values))
    volume = pd.Series(rng.integers(100_000, 5_000_000, n).astype(float))
    return close, high, low, volume


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U13 — TechnicalIndicators TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestMATypeEnum:
    def test_sma(self):
        assert MAType.SMA.value == "SMA"

    def test_ema(self):
        assert MAType.EMA.value == "EMA"

    def test_wma(self):
        assert MAType.WMA.value == "WMA"

    def test_hull(self):
        assert MAType.HULL.value == "HULL"

    def test_vwma(self):
        assert MAType.VWMA.value == "VWMA"

    def test_five_members(self):
        assert len(list(MAType)) == 5


class TestSignalTypeEnum:
    def test_buy(self):
        assert SignalType.BUY.value == "buy"

    def test_sell(self):
        assert SignalType.SELL.value == "sell"

    def test_neutral(self):
        assert SignalType.NEUTRAL.value == "neutral"

    def test_strong_buy(self):
        assert SignalType.STRONG_BUY.value == "strong_buy"

    def test_strong_sell(self):
        assert SignalType.STRONG_SELL.value == "strong_sell"

    def test_five_members(self):
        assert len(list(SignalType)) == 5


class TestTrendDirectionEnum:
    def test_up(self):
        assert TrendDirection.UP.value == "up"

    def test_down(self):
        assert TrendDirection.DOWN.value == "down"

    def test_sideways(self):
        assert TrendDirection.SIDEWAYS.value == "sideways"

    def test_unknown(self):
        assert TrendDirection.UNKNOWN.value == "unknown"


class TestIndicatorResultDataclass:
    def _make(self):
        return IndicatorResult(
            name="RSI",
            value=55.0,
            signal=SignalType.NEUTRAL,
            timestamp=pd.Timestamp.now(),
            parameters={"period": 14},
        )

    def test_creation(self):
        ir = self._make()
        assert ir.name == "RSI"
        assert ir.value == 55.0

    def test_to_dict_has_name(self):
        d = self._make().to_dict()
        assert "name" in d

    def test_to_dict_has_signal_value(self):
        d = self._make().to_dict()
        assert d["signal"] == "neutral"

    def test_to_dict_has_timestamp(self):
        d = self._make().to_dict()
        assert "timestamp" in d

    def test_to_dict_has_parameters(self):
        d = self._make().to_dict()
        assert "parameters" in d


class TestTechIndicatorsInit:
    def test_instantiation(self):
        ti = TechnicalIndicators()
        assert ti is not None

    def test_has_logger(self):
        ti = TechnicalIndicators()
        assert ti.logger is not None


class TestCalculateRsi:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=100)

    def test_returns_series(self):
        result = self.ti.calculate_rsi(self.prices)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_rsi(self.prices)
        assert len(result) == len(self.prices)

    def test_values_0_to_100(self):
        result = self.ti.calculate_rsi(self.prices, period=14)
        assert (result >= 0).all() and (result <= 100).all()

    def test_custom_period(self):
        result = self.ti.calculate_rsi(self.prices, period=9)
        assert isinstance(result, pd.Series)
        assert (result >= 0).all() and (result <= 100).all()

    def test_insufficient_data_returns_nan_filled(self):
        # With only 3 points and period=14, RSI returns NaN-filled Series
        short = pd.Series([1.0, 2.0, 3.0])
        result = self.ti.calculate_rsi(short, period=14)
        assert isinstance(result, pd.Series)
        assert result.isna().all()

    def test_declining_price_rsi_below_50(self):
        prices = pd.Series([500.0 - i * 2 for i in range(60)])
        result = self.ti.calculate_rsi(prices, period=14)
        last_rsi = result.iloc[-1]
        assert last_rsi < 50


class TestCalculateStochastic:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, _ = _make_ohlcv()

    def test_returns_dict(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert isinstance(result, dict)

    def test_has_k_and_d(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert "%K" in result and "%D" in result

    def test_k_in_0_100(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        valid_k = result["%K"].dropna()
        assert (valid_k >= 0).all() and (valid_k <= 100).all()

    def test_same_length(self):
        result = self.ti.calculate_stochastic(self.high, self.low, self.close)
        assert len(result["%K"]) == len(self.close)


class TestCalculateWilliamsR:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, _ = _make_ohlcv()

    def test_returns_series(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_values_minus100_to_0(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= -100).all() and (valid <= 0).all()

    def test_same_length(self):
        result = self.ti.calculate_williams_r(self.high, self.low, self.close)
        assert len(result) == len(self.close)


class TestCalculateMacd13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=100)

    def test_returns_dict(self):
        result = self.ti.calculate_macd(self.prices)
        assert isinstance(result, dict)

    def test_has_macd_signal_histogram(self):
        result = self.ti.calculate_macd(self.prices)
        for key in ("MACD", "Signal", "Histogram"):
            assert key in result

    def test_all_series(self):
        result = self.ti.calculate_macd(self.prices)
        for key in ("MACD", "Signal", "Histogram"):
            assert isinstance(result[key], pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_macd(self.prices)
        assert len(result["MACD"]) == len(self.prices)

    def test_custom_params(self):
        result = self.ti.calculate_macd(self.prices, fast=5, slow=13, signal=6)
        assert isinstance(result, dict)
        assert "MACD" in result


class TestCalculateAdx:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, _ = _make_ohlcv()

    def test_returns_dict(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        assert isinstance(result, dict)

    def test_has_adx_di_plus_di_minus(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        for key in ("ADX", "+DI", "-DI"):
            assert key in result

    def test_adx_non_negative(self):
        result = self.ti.calculate_adx(self.high, self.low, self.close)
        valid = result["ADX"].dropna()
        assert (valid >= 0).all()


class TestCalculateBollingerBands13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=100)

    def test_returns_dict(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        assert isinstance(result, dict)

    def test_has_upper_middle_lower(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        for key in ("Upper", "Middle", "Lower"):
            assert key in result

    def test_upper_above_lower(self):
        result = self.ti.calculate_bollinger_bands(self.prices)
        upper = result["Upper"].dropna()
        lower = result["Lower"].dropna()
        idx = upper.index.intersection(lower.index)
        assert (upper.loc[idx] >= lower.loc[idx]).all()

    def test_custom_std_dev(self):
        result = self.ti.calculate_bollinger_bands(self.prices, std_dev=1.5)
        assert isinstance(result, dict)


class TestCalculateAtr:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, _ = _make_ohlcv()

    def test_returns_series(self):
        result = self.ti.calculate_atr(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_non_negative(self):
        result = self.ti.calculate_atr(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_same_length(self):
        result = self.ti.calculate_atr(self.high, self.low, self.close)
        assert len(result) == len(self.close)


class TestCalculateTrueRange:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, _ = _make_ohlcv()

    def test_returns_series(self):
        result = self.ti.calculate_true_range(self.high, self.low, self.close)
        assert isinstance(result, pd.Series)

    def test_non_negative_after_first(self):
        result = self.ti.calculate_true_range(self.high, self.low, self.close)
        valid = result.dropna()
        assert (valid >= 0).all()


class TestCalculateSma13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=60)

    def test_returns_series(self):
        assert isinstance(self.ti.calculate_sma(self.prices, 20), pd.Series)

    def test_nan_at_start(self):
        result = self.ti.calculate_sma(self.prices, 20)
        assert result.iloc[:19].isna().all()

    def test_not_nan_at_end(self):
        result = self.ti.calculate_sma(self.prices, 20)
        assert not result.iloc[20:].isna().any()


class TestCalculateEma13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=60)

    def test_returns_series(self):
        assert isinstance(self.ti.calculate_ema(self.prices, 20), pd.Series)

    def test_no_nan_at_end(self):
        result = self.ti.calculate_ema(self.prices, 10)
        assert not result.iloc[-20:].isna().any()

    def test_same_length(self):
        result = self.ti.calculate_ema(self.prices, 10)
        assert len(result) == len(self.prices)


class TestCalculateWma:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=60)

    def test_returns_series(self):
        assert isinstance(self.ti.calculate_wma(self.prices, 10), pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_wma(self.prices, 10)
        assert len(result) == len(self.prices)

    def test_nan_before_period(self):
        result = self.ti.calculate_wma(self.prices, 10)
        assert result.iloc[:9].isna().all()


class TestCalculateHullMa:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.prices = _make_prices(n=80)

    def test_returns_series(self):
        result = self.ti.calculate_hull_ma(self.prices, 16)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_hull_ma(self.prices, 16)
        assert len(result) == len(self.prices)

    def test_has_valid_values_at_end(self):
        result = self.ti.calculate_hull_ma(self.prices, 16)
        valid = result.dropna()
        assert len(valid) > 0


class TestCalculateVwap13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, self.high, self.low, self.volume = _make_ohlcv()

    def test_returns_series(self):
        result = self.ti.calculate_vwap(self.high, self.low, self.close, self.volume)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_vwap(self.high, self.low, self.close, self.volume)
        assert len(result) == len(self.close)

    def test_vwap_in_price_range(self):
        result = self.ti.calculate_vwap(self.high, self.low, self.close, self.volume)
        valid = result.dropna()
        assert (valid > 300).all() and (valid < 700).all()


class TestCalculateObv13:
    def setup_method(self):
        self.ti = TechnicalIndicators()
        self.close, _, _, self.volume = _make_ohlcv()

    def test_returns_series(self):
        result = self.ti.calculate_obv(self.close, self.volume)
        assert isinstance(result, pd.Series)

    def test_same_length(self):
        result = self.ti.calculate_obv(self.close, self.volume)
        assert len(result) == len(self.close)

    def test_obv_changes(self):
        result = self.ti.calculate_obv(self.close, self.volume)
        # OBV should not be constant given varying price
        assert result.std() > 0


class TestGenerateRsiSignal:
    def setup_method(self):
        self.ti = TechnicalIndicators()

    def test_strong_sell_above_80(self):
        rsi = pd.Series([85.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.STRONG_SELL

    def test_sell_between_70_and_80(self):
        rsi = pd.Series([72.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.SELL

    def test_strong_buy_below_20(self):
        rsi = pd.Series([15.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.STRONG_BUY

    def test_buy_between_20_and_30(self):
        rsi = pd.Series([25.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.BUY

    def test_neutral_mid_range(self):
        rsi = pd.Series([50.0])
        assert self.ti.generate_rsi_signal(rsi) == SignalType.NEUTRAL

    def test_returns_signal_type(self):
        rsi = pd.Series([55.0])
        result = self.ti.generate_rsi_signal(rsi)
        assert isinstance(result, SignalType)


class TestGenerateMacdSignal:
    def setup_method(self):
        self.ti = TechnicalIndicators()

    def _make_macd_data(self, macd_val, signal_val, prev_hist, curr_hist):
        macd_line = pd.Series([0.0, macd_val])
        signal_line = pd.Series([0.0, signal_val])
        histogram = pd.Series([prev_hist, curr_hist])
        return {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram}

    def test_bullish_crossover_buy(self):
        # curr macd > signal, hist goes from -0.1 to +0.1
        data = self._make_macd_data(0.5, 0.3, -0.1, 0.2)
        assert self.ti.generate_macd_signal(data) == SignalType.BUY

    def test_bearish_crossover_sell(self):
        # curr macd < signal, hist goes from +0.1 to -0.1
        data = self._make_macd_data(-0.3, 0.2, 0.1, -0.5)
        assert self.ti.generate_macd_signal(data) == SignalType.SELL

    def test_neutral_when_no_crossover(self):
        # Both hist values positive → no crossover
        data = self._make_macd_data(0.5, 0.3, 0.1, 0.2)
        assert self.ti.generate_macd_signal(data) == SignalType.NEUTRAL

    def test_returns_signal_type(self):
        data = self._make_macd_data(0.1, 0.2, 0.05, 0.03)
        result = self.ti.generate_macd_signal(data)
        assert isinstance(result, SignalType)


class TestModuleFunctions13:
    def test_calculate_rsi_module_func(self):
        prices = _make_prices(n=60)
        result = calculate_rsi(prices)
        assert isinstance(result, pd.Series)

    def test_calculate_macd_module_func(self):
        prices = _make_prices(n=60)
        result = calculate_macd(prices)
        assert isinstance(result, dict)

    def test_calculate_bollinger_bands_module_func(self):
        prices = _make_prices(n=60)
        result = calculate_bollinger_bands(prices)
        assert isinstance(result, dict)

    def test_get_technical_indicators_singleton(self):
        _u13._technical_indicators_instance = None
        ti1 = get_technical_indicators()
        ti2 = get_technical_indicators()
        assert ti1 is ti2

    def test_get_technical_indicators_returns_instance(self):
        _u13._technical_indicators_instance = None
        ti = get_technical_indicators()
        assert isinstance(ti, TechnicalIndicators)


# ==============================================================================
# ═══════════════════════════════════════════════════════════════════════════════
#  U14 — OptionStrategies TESTS
# ═══════════════════════════════════════════════════════════════════════════════
# ==============================================================================

def _expiry(days: int = 30) -> datetime:
    return datetime(2026, 4, 1) + timedelta(days=days)


class TestOptionTypeEnum:
    def test_call(self):
        assert OptionType.CALL.value == "CALL"

    def test_put(self):
        assert OptionType.PUT.value == "PUT"

    def test_two_members(self):
        assert len(list(OptionType)) == 2


class TestPositionTypeEnum:
    def test_long(self):
        assert PositionType.LONG.value == "LONG"

    def test_short(self):
        assert PositionType.SHORT.value == "SHORT"


class TestStrategyTypeEnum:
    def test_iron_condor(self):
        assert StrategyType.IRON_CONDOR.value == "iron_condor"

    def test_straddle(self):
        assert StrategyType.STRADDLE.value == "straddle"

    def test_bull_call_spread(self):
        assert StrategyType.BULL_CALL_SPREAD.value == "bull_call_spread"


class TestOptionLeg:
    def _make_call_long(self):
        return OptionLeg(
            option_type=OptionType.CALL,
            position_type=PositionType.LONG,
            strike=460.0,
            expiry=_expiry(),
            premium=5.0,
            quantity=1,
        )

    def _make_put_short(self):
        return OptionLeg(
            option_type=OptionType.PUT,
            position_type=PositionType.SHORT,
            strike=440.0,
            expiry=_expiry(),
            premium=3.0,
            quantity=1,
        )

    def test_is_call_true(self):
        leg = self._make_call_long()
        assert leg.is_call is True
        assert leg.is_put is False

    def test_is_put_true(self):
        leg = self._make_put_short()
        assert leg.is_put is True
        assert leg.is_call is False

    def test_is_long(self):
        leg = self._make_call_long()
        assert leg.is_long is True
        assert leg.is_short is False

    def test_is_short(self):
        leg = self._make_put_short()
        assert leg.is_short is True
        assert leg.is_long is False

    def test_net_premium_long_negative(self):
        # Long pays premium → negative net
        leg = self._make_call_long()
        assert leg.net_premium == pytest.approx(-5.0, abs=1e-9)

    def test_net_premium_short_positive(self):
        # Short receives premium → positive net
        leg = self._make_put_short()
        assert leg.net_premium == pytest.approx(3.0, abs=1e-9)

    def test_net_premium_quantity(self):
        leg = OptionLeg(OptionType.CALL, PositionType.SHORT, 460, _expiry(), 5.0, quantity=2)
        assert leg.net_premium == pytest.approx(10.0, abs=1e-9)


class TestOptionStrategy:
    def _make_credit_strategy(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.SHORT, 460, _expiry(), 5.0),
        ]
        return OptionStrategy(
            name="Short Call",
            strategy_type=StrategyType.NAKED_CALL,
            legs=legs,
            underlying_price=455.0,
        )

    def _make_debit_strategy(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.LONG, 460, _expiry(), 5.0),
        ]
        return OptionStrategy(
            name="Long Call",
            strategy_type=StrategyType.NAKED_CALL,
            legs=legs,
            underlying_price=455.0,
        )

    def test_net_premium_credit(self):
        s = self._make_credit_strategy()
        assert s.net_premium == pytest.approx(5.0, abs=1e-9)

    def test_is_credit_strategy(self):
        s = self._make_credit_strategy()
        assert s.is_credit_strategy is True
        assert s.is_debit_strategy is False

    def test_is_debit_strategy(self):
        s = self._make_debit_strategy()
        assert s.is_debit_strategy is True
        assert s.is_credit_strategy is False


class TestOptionStrategiesInit:
    def test_instantiation(self):
        os_ = OptionStrategies()
        assert os_ is not None

    def test_has_logger(self):
        os_ = OptionStrategies()
        assert os_.logger is not None


class TestCalculateOptionPayoff:
    def setup_method(self):
        self.os = OptionStrategies()

    def test_long_call_atm_expiry(self):
        # Long 460 call with $5 premium, spot=470 → (10-5)*100 = 500
        payoff = self.os.calculate_option_payoff("CALL", "LONG", 460, 5.0, 470.0)
        assert payoff == pytest.approx(500.0, abs=1e-6)

    def test_long_call_otm_expiry(self):
        # Long 470 call with $5 premium, spot=460 → (0-5)*100 = -500
        payoff = self.os.calculate_option_payoff("CALL", "LONG", 470, 5.0, 460.0)
        assert payoff == pytest.approx(-500.0, abs=1e-6)

    def test_long_put_itm(self):
        # Long 460 put with $5 premium, spot=450 → (10-5)*100 = 500
        payoff = self.os.calculate_option_payoff("PUT", "LONG", 460, 5.0, 450.0)
        assert payoff == pytest.approx(500.0, abs=1e-6)

    def test_long_put_otm(self):
        # Long 460 put with $5 premium, spot=470 → (0-5)*100 = -500
        payoff = self.os.calculate_option_payoff("PUT", "LONG", 460, 5.0, 470.0)
        assert payoff == pytest.approx(-500.0, abs=1e-6)

    def test_short_call_otm(self):
        # Short 470 call with $5 premium, spot=460 → (5-0)*100 = 500
        payoff = self.os.calculate_option_payoff("CALL", "SHORT", 470, 5.0, 460.0)
        assert payoff == pytest.approx(500.0, abs=1e-6)

    def test_short_call_itm(self):
        # Short 460 call with $5 premium, spot=470 → (5-10)*100 = -500
        payoff = self.os.calculate_option_payoff("CALL", "SHORT", 460, 5.0, 470.0)
        assert payoff == pytest.approx(-500.0, abs=1e-6)

    def test_vectorized_with_array(self):
        spot = np.array([450.0, 460.0, 470.0, 480.0])
        payoffs = self.os.calculate_option_payoff("CALL", "LONG", 460, 5.0, spot)
        assert isinstance(payoffs, np.ndarray)
        assert len(payoffs) == 4

    def test_quantity_multiplies_payoff(self):
        p1 = self.os.calculate_option_payoff("CALL", "LONG", 460, 5.0, 470.0, quantity=1)
        p2 = self.os.calculate_option_payoff("CALL", "LONG", 460, 5.0, 470.0, quantity=2)
        assert p2 == pytest.approx(p1 * 2, abs=1e-6)

    def test_module_level_function(self):
        payoff = calculate_option_payoff("CALL", "LONG", 460, 5.0, 470.0)
        assert payoff == pytest.approx(500.0, abs=1e-6)


class TestCreateBullCallSpread:
    def setup_method(self):
        self.os = OptionStrategies()
        self.expiry = _expiry()
        self.spread = self.os.create_bull_call_spread(
            long_strike=450,
            short_strike=460,
            expiry=self.expiry,
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=455.0,
        )

    def test_returns_option_strategy(self):
        assert isinstance(self.spread, OptionStrategy)

    def test_strategy_type(self):
        assert self.spread.strategy_type == StrategyType.BULL_CALL_SPREAD

    def test_two_legs(self):
        assert len(self.spread.legs) == 2

    def test_is_debit_strategy(self):
        # Net premium = -8 + 3 = -5 (debit)
        assert self.spread.is_debit_strategy is True

    def test_max_profit_set(self):
        assert self.spread.max_profit is not None
        assert self.spread.max_profit > 0

    def test_max_loss_set(self):
        assert self.spread.max_loss is not None
        assert self.spread.max_loss > 0

    def test_max_profit_less_than_spread_width(self):
        spread_width = (460 - 450) * CONTRACT_MULTIPLIER
        assert self.spread.max_profit <= spread_width

    def test_name_contains_strikes(self):
        assert "450" in self.spread.name
        assert "460" in self.spread.name


class TestCreateBearPutSpread:
    def setup_method(self):
        self.os = OptionStrategies()
        self.spread = self.os.create_bear_put_spread(
            long_strike=460,
            short_strike=450,
            expiry=_expiry(),
            long_premium=7.0,
            short_premium=2.0,
            underlying_price=455.0,
        )

    def test_returns_option_strategy(self):
        assert isinstance(self.spread, OptionStrategy)

    def test_strategy_type(self):
        assert self.spread.strategy_type == StrategyType.BEAR_PUT_SPREAD

    def test_two_legs(self):
        assert len(self.spread.legs) == 2

    def test_debit_strategy(self):
        assert self.spread.is_debit_strategy is True

    def test_legs_are_puts(self):
        for leg in self.spread.legs:
            assert leg.option_type == OptionType.PUT


class TestCreateIronCondor:
    def setup_method(self):
        self.os = OptionStrategies()
        self.condor = self.os.create_iron_condor(
            put_long_strike=440,
            put_short_strike=450,
            call_short_strike=470,
            call_long_strike=480,
            expiry=_expiry(),
            premiums=[2.0, 6.0, 6.0, 2.0],
            underlying_price=460.0,
        )

    def test_returns_option_strategy(self):
        assert isinstance(self.condor, OptionStrategy)

    def test_strategy_type(self):
        assert self.condor.strategy_type == StrategyType.IRON_CONDOR

    def test_four_legs(self):
        assert len(self.condor.legs) == 4

    def test_is_credit_strategy(self):
        # Net premium = -2 + 6 + 6 - 2 = 8 (credit)
        assert self.condor.is_credit_strategy is True

    def test_max_profit_set(self):
        assert self.condor.max_profit is not None
        assert self.condor.max_profit > 0

    def test_max_loss_greater_than_max_profit(self):
        # Wing risk > net credit
        assert self.condor.max_loss > self.condor.max_profit

    def test_name_has_all_strikes(self):
        for strike in ("440", "450", "470", "480"):
            assert strike in self.condor.name


class TestCreateStraddle:
    def setup_method(self):
        self.os = OptionStrategies()
        self.long_straddle = self.os.create_straddle(
            strike=460,
            expiry=_expiry(),
            call_premium=8.0,
            put_premium=8.0,
            underlying_price=460.0,
            position_type="LONG",
        )
        self.short_straddle = self.os.create_straddle(
            strike=460,
            expiry=_expiry(),
            call_premium=8.0,
            put_premium=8.0,
            underlying_price=460.0,
            position_type="SHORT",
        )

    def test_long_straddle_type(self):
        assert self.long_straddle.strategy_type == StrategyType.STRADDLE

    def test_two_legs(self):
        assert len(self.long_straddle.legs) == 2

    def test_long_straddle_is_debit(self):
        assert self.long_straddle.is_debit_strategy is True

    def test_short_straddle_is_credit(self):
        assert self.short_straddle.is_credit_strategy is True

    def test_long_straddle_max_loss_finite(self):
        assert math.isfinite(self.long_straddle.max_loss)

    def test_long_straddle_max_profit_infinite(self):
        assert self.long_straddle.max_profit == float("inf")

    def test_short_straddle_max_profit_finite(self):
        assert math.isfinite(self.short_straddle.max_profit)

    def test_legs_are_call_and_put(self):
        option_types = {leg.option_type for leg in self.long_straddle.legs}
        assert OptionType.CALL in option_types
        assert OptionType.PUT in option_types


class TestGetPayoffDiagram:
    def setup_method(self):
        self.os = OptionStrategies()
        self.spread = self.os.create_bull_call_spread(
            long_strike=450,
            short_strike=460,
            expiry=_expiry(),
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=455.0,
        )

    def test_returns_payoff_result(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result, PayoffResult)

    def test_spot_prices_is_array(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result.spot_prices, np.ndarray)

    def test_payoffs_is_array(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result.payoffs, np.ndarray)

    def test_num_points(self):
        result = self.os.get_payoff_diagram(self.spread, num_points=50)
        assert len(result.spot_prices) == 50
        assert len(result.payoffs) == 50

    def test_max_profit_is_float(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result.max_profit, float)

    def test_max_loss_is_float(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result.max_loss, float)

    def test_breakeven_is_list(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert isinstance(result.breakeven_points, list)

    def test_custom_price_range(self):
        result = self.os.get_payoff_diagram(self.spread, price_range=(430, 490))
        assert result.spot_prices[0] == pytest.approx(430, abs=0.1)
        assert result.spot_prices[-1] == pytest.approx(490, abs=0.1)

    def test_max_profit_non_negative(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert result.max_profit >= 0

    def test_max_loss_non_positive(self):
        result = self.os.get_payoff_diagram(self.spread)
        assert result.max_loss <= 0


class TestCalculateStrategyPayoff:
    def setup_method(self):
        self.os = OptionStrategies()
        self.spread = self.os.create_bull_call_spread(
            long_strike=450,
            short_strike=460,
            expiry=_expiry(),
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=455.0,
        )

    def test_returns_scalar_for_scalar(self):
        result = self.os.calculate_strategy_payoff(self.spread, 465.0)
        assert isinstance(result, (float, int, np.floating))

    def test_returns_array_for_array(self):
        spots = np.array([450.0, 460.0, 470.0])
        result = self.os.calculate_strategy_payoff(self.spread, spots)
        assert len(result) == 3


class TestCalculateMaxProfit:
    def setup_method(self):
        self.os = OptionStrategies()

    def test_bull_call_spread_max_profit(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        max_p = self.os.calculate_max_profit(spread)
        assert max_p >= 0

    def test_returns_float(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        assert isinstance(self.os.calculate_max_profit(spread), float)


class TestCalculateMaxLoss:
    def setup_method(self):
        self.os = OptionStrategies()

    def test_bull_call_max_loss_negative(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        max_l = self.os.calculate_max_loss(spread)
        assert max_l <= 0


class TestCalculateBreakevenPoints:
    def setup_method(self):
        self.os = OptionStrategies()

    def test_returns_list(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        result = self.os.calculate_breakeven_points(spread)
        assert isinstance(result, list)

    def test_bull_call_has_one_breakeven(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        result = self.os.calculate_breakeven_points(spread)
        assert len(result) >= 1


class TestCalculateProfitProbability:
    def setup_method(self):
        self.os = OptionStrategies()

    def test_returns_float_in_0_1(self):
        spread = self.os.create_bull_call_spread(
            long_strike=450, short_strike=460, expiry=_expiry(),
            long_premium=8.0, short_premium=3.0, underlying_price=455.0,
        )
        result = self.os.calculate_profit_probability(spread, 0.15, 30)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_iron_condor_probability(self):
        condor = self.os.create_iron_condor(
            put_long_strike=440, put_short_strike=450,
            call_short_strike=470, call_long_strike=480,
            expiry=_expiry(), premiums=[2.0, 6.0, 6.0, 2.0],
            underlying_price=460.0,
        )
        result = self.os.calculate_profit_probability(condor, 0.15, 30)
        assert 0.0 <= result <= 1.0


class TestGetOptionStrategiesSingleton:
    def setup_method(self):
        _u14._option_strategies = None

    def test_returns_option_strategies(self):
        os_ = get_option_strategies()
        assert isinstance(os_, OptionStrategies)

    def test_returns_same_instance(self):
        os1 = get_option_strategies()
        os2 = get_option_strategies()
        assert os1 is os2
