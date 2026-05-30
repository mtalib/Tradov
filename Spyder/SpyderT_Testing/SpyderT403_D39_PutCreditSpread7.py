#!/usr/bin/env python3
"""Focused unit tests for the D39 Put Credit Spread 7 strategy."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    PositionState,
    PositionType,
    RiskProfile,
    StrategyPosition,
)
from Spyder.SpyderD_Strategies.SpyderD39_PutCreditSpread7 import PutCreditSpread7Strategy


pytestmark = pytest.mark.unit


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None


def _make_strategy(config: dict | None = None) -> PutCreditSpread7Strategy:
    return PutCreditSpread7Strategy(
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=50000),
        config=config or {},
    )


def _put_row(
    expiration: str,
    strike: float,
    delta: float,
    bid: float,
    ask: float,
    *,
    open_interest: int = 1200,
    volume: int = 300,
) -> dict:
    return {
        "option_type": "put",
        "strike": strike,
        "delta": delta,
        "bid": bid,
        "ask": ask,
        "open_interest": open_interest,
        "volume": volume,
        "expiration_date": expiration,
    }


def _option_chain(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _default_option_chain(expiration: str) -> pd.DataFrame:
    return _option_chain(
        _put_row(expiration, 557.0, -0.10, 1.24, 1.28),
        _put_row(expiration, 552.0, -0.05, 0.89, 0.91),
    )


def _market_data(
    closes: list[float] | None = None,
    *,
    iv: float | None = 0.17,
    sma_200: float | None = None,
) -> pd.DataFrame:
    resolved_closes = closes or [520.0 + idx * 0.2 for idx in range(205)]
    data: dict[str, list[float | None]] = {"close": resolved_closes}
    if iv is not None:
        data["iv"] = [iv] * len(resolved_closes)
    if sma_200 is not None:
        data["sma_200"] = [sma_200] * len(resolved_closes)
    return pd.DataFrame(data)


def _make_position(signal, entry_time: datetime) -> StrategyPosition:
    return StrategyPosition(
        position_id="pcs7-1",
        strategy_name="PutCreditSpread7",
        symbol="SPY",
        position_type=PositionType.SHORT,
        state=PositionState.OPEN,
        entry_time=entry_time,
        entry_price=signal.entry_price,
        position_size=signal.position_size,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        metadata=signal.metadata,
    )


def test_put_credit_spread_7_generates_signal_from_option_chain() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    signals = strategy.generate_signals(market_data)

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type.value == "sell"
    assert signal.symbol == "SPY"
    assert strategy.validate_signal(signal) is True
    assert signal.position_size == 40
    assert signal.metadata["strategy_id"] == "PutCreditSpread7"
    assert signal.metadata["strategy_type"] == "bull_put_credit_spread"
    assert signal.metadata["short_put_strike"] > signal.metadata["long_put_strike"]
    assert signal.metadata["expiration_date"] == "2026-06-12"
    assert signal.metadata["credit_model"] == "option_chain"
    assert signal.metadata["selection_method"] == "delta_primary"
    assert signal.metadata["profit_target_enabled"] is False
    assert signal.metadata["stop_loss_bar_minutes"] == 5
    assert signal.metadata["expiration_exit_time_et"] == "15:55:00"
    assert len(signal.metadata["legs"]) == 2


def test_put_credit_spread_7_rejects_market_below_sma_200() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    closes = [620.0 - idx * 0.3 for idx in range(205)]
    market_data = _market_data(closes, iv=0.19)

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_fails_closed_without_option_chain() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data()

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_waits_until_entry_time() -> None:
    friday_morning = datetime(2026, 6, 5, 14, 30, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_morning,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_rejects_after_exact_entry_minute() -> None:
    friday_late = datetime(2026, 6, 5, 19, 46, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_late,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_requires_half_percent_sma_buffer() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data(
        closes=[100.0, 100.2, 100.4],
        iv=0.17,
        sma_200=100.0,
    )
    market_data.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", 95.0, -0.10, 1.20, 1.24),
        _put_row("2026-06-12T00:00:00+00:00", 90.0, -0.05, 0.70, 0.74),
    )

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_hybrid_exit_triggers_at_one_dte() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    entry_market = _market_data()
    entry_market.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )
    signal = strategy.generate_signals(entry_market)[0]

    position = _make_position(signal, friday_open)

    one_dte_time = datetime(2026, 6, 11, 19, 55, tzinfo=UTC)
    short_put = float(signal.metadata["short_put_strike"])
    spot_near_short = short_put * 1.002
    exit_market = pd.DataFrame({"close": [spot_near_short]})
    strategy._clock = lambda: one_dte_time

    should_exit, reason = strategy.should_exit_position(position, exit_market)

    assert should_exit is True
    assert reason == "hybrid_one_dte_exit"


def test_put_credit_spread_7_defers_one_dte_hybrid_check_until_close() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    entry_market = _market_data()
    entry_market.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )
    signal = strategy.generate_signals(entry_market)[0]
    position = _make_position(signal, friday_open)

    one_dte_afternoon = datetime(2026, 6, 11, 18, 0, tzinfo=UTC)
    short_put = float(signal.metadata["short_put_strike"])
    exit_market = pd.DataFrame({"close": [short_put * 1.002]})
    strategy._clock = lambda: one_dte_afternoon

    should_exit, reason = strategy.should_exit_position(position, exit_market)

    assert should_exit is False
    assert reason == ""


def test_put_credit_spread_7_selects_liquid_delta_within_search_window() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", 560.0, -0.10, 1.00, 1.40),
        _put_row("2026-06-12T00:00:00+00:00", 559.0, -0.12, 1.10, 1.18),
        _put_row("2026-06-12T00:00:00+00:00", 558.0, -0.08, 1.00, 1.08),
        _put_row("2026-06-12T00:00:00+00:00", 553.0, -0.04, 0.70, 0.74),
    )

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    signal = strategy.generate_signals(market_data)[0]

    assert signal.metadata["short_put_strike"] == 558.0
    assert signal.metadata["selection_method"] == "delta_search_liquid"


def test_put_credit_spread_7_uses_iv_fallback_when_no_liquid_strike_found() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", 560.0, -0.10, 1.00, 1.40),
        _put_row("2026-06-12T00:00:00+00:00", 559.0, -0.09, 0.96, 1.22),
        _put_row("2026-06-12T00:00:00+00:00", 558.0, -0.08, 0.90, 1.15),
        _put_row("2026-06-12T00:00:00+00:00", 554.0, -0.06, 0.72, 0.78),
        _put_row("2026-06-12T00:00:00+00:00", 549.0, -0.03, 0.40, 0.46),
    )

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    signal = strategy.generate_signals(market_data)[0]

    assert signal.metadata["short_put_strike"] == 554.0
    assert signal.metadata["selection_method"] == "iv_fallback"


def test_put_credit_spread_7_fails_closed_when_iv_fallback_has_no_iv() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data(iv=None)
    market_data.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", 560.0, -0.10, 1.00, 1.40),
        _put_row("2026-06-12T00:00:00+00:00", 559.0, -0.09, 0.96, 1.22),
        _put_row("2026-06-12T00:00:00+00:00", 558.0, -0.08, 0.90, 1.15),
        _put_row("2026-06-12T00:00:00+00:00", 549.0, -0.03, 0.40, 0.46),
    )

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    assert strategy.generate_signals(market_data) == []


def test_put_credit_spread_7_prefers_later_expiry_on_tie() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    market_data = _market_data()
    market_data.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-11T00:00:00+00:00", 557.0, -0.10, 1.24, 1.28),
        _put_row("2026-06-11T00:00:00+00:00", 552.0, -0.05, 0.89, 0.91),
        _put_row("2026-06-13T00:00:00+00:00", 557.0, -0.10, 1.24, 1.28),
        _put_row("2026-06-13T00:00:00+00:00", 552.0, -0.05, 0.89, 0.91),
    )

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )

    signal = strategy.generate_signals(market_data)[0]

    assert signal.metadata["expiration_date"] == "2026-06-13"


def test_put_credit_spread_7_forces_zero_dte_close_at_1555_et() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    entry_market = _market_data()
    entry_market.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
        }
    )
    signal = strategy.generate_signals(entry_market)[0]
    position = _make_position(signal, friday_open)

    expiration_close = datetime(2026, 6, 12, 19, 55, tzinfo=UTC)
    short_put = float(signal.metadata["short_put_strike"])
    exit_market = pd.DataFrame({"close": [short_put * 1.02]})
    strategy._clock = lambda: expiration_close

    should_exit, reason = strategy.should_exit_position(position, exit_market)

    assert should_exit is True
    assert reason == "expiration_close"


def test_put_credit_spread_7_profit_target_precedes_time_based_exit() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    entry_market = _market_data()
    entry_market.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
            "enable_profit_target": True,
        }
    )
    signal = strategy.generate_signals(entry_market)[0]
    position = _make_position(signal, friday_open)

    profit_time = datetime(2026, 6, 9, 18, 0, tzinfo=UTC)
    short_put = float(signal.metadata["short_put_strike"])
    long_put = float(signal.metadata["long_put_strike"])
    exit_market = pd.DataFrame({"close": [short_put * 1.02], "iv": [0.17]})
    exit_market.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", short_put, -0.10, 0.38, 0.42),
        _put_row("2026-06-12T00:00:00+00:00", long_put, -0.05, 0.25, 0.29),
    )
    strategy._clock = lambda: profit_time

    should_exit, reason = strategy.should_exit_position(position, exit_market)

    assert should_exit is True
    assert reason == "profit_target"


def test_put_credit_spread_7_stop_loss_precedes_profit_target() -> None:
    friday_open = datetime(2026, 6, 5, 19, 45, tzinfo=UTC)
    entry_market = _market_data()
    entry_market.attrs["option_chain"] = _default_option_chain("2026-06-12T00:00:00+00:00")

    strategy = _make_strategy(
        {
            "clock": lambda: friday_open,
            "spread_width": 5.0,
            "enable_profit_target": True,
        }
    )
    signal = strategy.generate_signals(entry_market)[0]
    position = _make_position(signal, friday_open)

    profit_time = datetime(2026, 6, 9, 18, 0, tzinfo=UTC)
    short_put = float(signal.metadata["short_put_strike"])
    long_put = float(signal.metadata["long_put_strike"])
    exit_market = pd.DataFrame({"close": [short_put - 0.5], "iv": [0.17]})
    exit_market.attrs["option_chain"] = _option_chain(
        _put_row("2026-06-12T00:00:00+00:00", short_put, -0.10, 0.38, 0.42),
        _put_row("2026-06-12T00:00:00+00:00", long_put, -0.05, 0.25, 0.29),
    )
    strategy._clock = lambda: profit_time

    should_exit, reason = strategy.should_exit_position(position, exit_market)

    assert should_exit is True
    assert reason == "stop_loss_bar_close"
