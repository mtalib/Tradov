#!/usr/bin/env python3
"""Focused unit tests for the D37 Bullish Strangle strategy."""

from datetime import datetime, UTC

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    PositionState,
    PositionType,
    RiskProfile,
    StrategyPosition,
)
from Spyder.SpyderD_Strategies.SpyderD37_BullishStrangle import BullishStrangleStrategy
from Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies import StrategyType, get_option_strategies


pytestmark = pytest.mark.unit


class _StubEventManager:
    def __init__(self) -> None:
        self.handlers: dict[str, list] = {}

    def subscribe(self, event_type, handler) -> None:
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


def _make_strategy(config: dict | None = None) -> BullishStrangleStrategy:
    return BullishStrangleStrategy(
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000),
        config=config or {},
    )


def test_u14_create_strangle_builder_sets_expected_metrics() -> None:
    options = get_option_strategies()
    expiry = datetime.now(UTC)
    structure = options.create_strangle(
        call_strike=410.0,
        put_strike=390.0,
        expiry=expiry,
        call_premium=5.0,
        put_premium=4.0,
        underlying_price=400.0,
        position_type="LONG",
    )

    breakevens = options.calculate_breakeven_points(structure)

    assert structure.strategy_type == StrategyType.STRANGLE
    assert structure.is_debit_strategy is True
    assert structure.max_loss == pytest.approx(9.0, abs=1e-6)
    assert len(structure.legs) == 2
    assert breakevens == pytest.approx([381.0, 419.0], abs=0.15)


def test_bullish_strangle_generates_bullish_signal() -> None:
    strategy = _make_strategy(
        {
            "call_otm_pct": 0.01,
            "put_otm_pct": 0.025,
            "target_debit": 9.0,
        }
    )
    market_data = pd.DataFrame(
        {
            "close": [398.0, 401.0, 404.0],
            "rsi": [55.0, 58.0, 61.0],
        }
    )

    signals = strategy.generate_signals(market_data)

    assert len(signals) == 1
    signal = signals[0]
    assert strategy.validate_signal(signal) is True
    assert signal.metadata["strategy_type"] == "bullish_strangle"
    assert signal.metadata["call_strike"] > signal.metadata["underlying_spot"] > signal.metadata["put_strike"]
    assert signal.metadata["call_otm_pct"] < signal.metadata["put_otm_pct"]
    assert signal.metadata["upper_breakeven"] > signal.metadata["call_strike"]
    assert signal.metadata["lower_breakeven"] < signal.metadata["put_strike"]
    assert strategy.calculate_position_size(signal) == 1


def test_bullish_strangle_rejects_non_bullish_tape() -> None:
    strategy = _make_strategy()
    market_data = pd.DataFrame(
        {
            "close": [404.0, 402.0, 400.0],
            "rsi": [52.0, 49.0, 45.0],
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_bullish_strangle_exits_on_upper_breakeven_breakout() -> None:
    strategy = _make_strategy(
        {
            "call_otm_pct": 0.01,
            "put_otm_pct": 0.025,
            "target_debit": 9.0,
        }
    )
    entry_market_data = pd.DataFrame(
        {
            "close": [398.0, 401.0, 404.0],
            "rsi": [55.0, 58.0, 61.0],
        }
    )
    signal = strategy.generate_signals(entry_market_data)[0]

    position = StrategyPosition(
        position_id="bullish-strangle-1",
        strategy_name="BullishStrangle",
        symbol="SPY",
        position_type=PositionType.LONG,
        state=PositionState.OPEN,
        entry_time=datetime.now(UTC),
        entry_price=signal.entry_price,
        position_size=1,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        metadata=signal.metadata,
    )

    exit_market_data = pd.DataFrame(
        {
            "close": [signal.metadata["upper_breakeven"] + 1.0],
        }
    )

    should_exit, reason = strategy.should_exit_position(position, exit_market_data)

    assert should_exit is True
    assert reason == "upper_breakeven_reached"
