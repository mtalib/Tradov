from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies import SpyderD24_Butterfly as d24
from Spyder.SpyderD_Strategies import SpyderD32_MultiLegStrategyCoordinator as d32


pytestmark = pytest.mark.unit


def _market_frame() -> pd.DataFrame:
    close = [598.8, 598.9, 599.0, 599.1, 599.2, 599.1, 599.2, 599.3, 599.4, 599.3, 599.4, 599.5]
    iv = [0.19, 0.18, 0.19, 0.20, 0.19, 0.18, 0.19, 0.20, 0.19, 0.18, 0.19, 0.20]
    return pd.DataFrame(
        {
            "close": close,
            "high": [value + 0.35 for value in close],
            "low": [value - 0.35 for value in close],
            "iv": iv,
        }
    )


def _strategy(monkeypatch, **config_overrides) -> d24.ButterflyStrategy:
    monkeypatch.setattr(d24, "get_multileg_coordinator", lambda config=None: SimpleNamespace())

    event_manager = SimpleNamespace(
        subscribe=lambda *args, **kwargs: None,
        publish=lambda *args, **kwargs: None,
        emit=lambda *args, **kwargs: None,
        unsubscribe=lambda *args, **kwargs: None,
    )
    return d24.ButterflyStrategy(
        event_manager=event_manager,
        config={
            "symbol": "SPY",
            "wing_width": 1.0,
            "max_debit": 0.65,
            "prefer_live_chain": False,
            **config_overrides,
        },
    )


def test_build_butterfly_setup_returns_debit_profile(monkeypatch):
    strategy = _strategy(monkeypatch)

    setup = strategy.build_butterfly_setup(_market_frame())

    assert setup is not None
    assert setup.body_strike == 600.0
    assert setup.lower_strike == 599.0
    assert setup.upper_strike == 601.0
    assert 0.0 < setup.expected_debit < setup.wing_width
    assert setup.max_profit == round(setup.wing_width - setup.expected_debit, 2)
    assert setup.max_loss == setup.expected_debit


def test_build_multileg_structure_preserves_butterfly_ratio(monkeypatch):
    strategy = _strategy(monkeypatch)
    setup = strategy.build_butterfly_setup(_market_frame())

    assert setup is not None

    structure = strategy._build_multileg_structure_from_setup(setup)

    assert structure.strategy_type == d32.MultiLegStrategyType.BUTTERFLY
    assert structure.net_credit == -setup.expected_debit
    assert [leg.quantity for leg in structure.legs] == [1, -2, 1]
    assert structure.underlying_symbol == "SPY"
    assert structure.contracts == 1


def test_d32_submit_combo_order_routes_butterfly_as_debit(monkeypatch):
    strategy = _strategy(monkeypatch)
    setup = strategy.build_butterfly_setup(_market_frame())

    assert setup is not None

    order_manager = SimpleNamespace(
        submit_multileg_order=MagicMock(
            return_value=SimpleNamespace(success=True, tradier_order_id=88001, message="ok")
        )
    )
    coordinator = d32.MultiLegStrategyCoordinator(config={"symbol": "SPY"}, order_manager=order_manager)

    structure = strategy._build_multileg_structure_from_setup(setup)

    order_id = coordinator._submit_combo_order(structure, "test-bfly")

    assert order_id == 88001
    kwargs = order_manager.submit_multileg_order.call_args.kwargs
    assert kwargs["order_type"] == "debit"
    assert kwargs["price"] == setup.expected_debit
    submitted_legs = kwargs["legs"]
    assert [leg.quantity for leg in submitted_legs] == [1, 2, 1]
    assert [leg.side.value for leg in submitted_legs] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]


def test_build_butterfly_setup_uses_live_chain_alignment_and_mids(monkeypatch):
    strategy = _strategy(monkeypatch, prefer_live_chain=True)
    listed_expiration = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    live_mids = {
        598.0: 2.10,
        599.0: 1.55,
        600.0: 1.10,
    }
    fake_client = SimpleNamespace(
        get_option_expirations=lambda _symbol: {"expirations": {"date": [listed_expiration]}},
        get_option_chain_with_greeks=lambda _symbol, _expiration: [
            SimpleNamespace(symbol="SPY", strike=598.0, option_type="call", bid=2.05, ask=2.15, last=2.10, mid=2.10, iv=0.21, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=599.0, option_type="call", bid=1.50, ask=1.60, last=1.55, mid=1.55, iv=0.20, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=600.0, option_type="call", bid=1.05, ask=1.15, last=1.10, mid=1.10, iv=0.19, expiration=listed_expiration),
        ],
    )
    monkeypatch.setattr(strategy, "_get_live_quote_client", lambda: fake_client)

    setup = strategy.build_butterfly_setup(_market_frame())

    assert setup is not None
    assert setup.expiration_date.date().isoformat() == listed_expiration
    assert setup.lower_strike < setup.body_strike < setup.upper_strike
    assert setup.body_strike == 599.0
    expected_debit = round(
        live_mids[setup.lower_strike]
        + live_mids[setup.upper_strike]
        - (live_mids[setup.body_strike] * 2.0),
        2,
    )
    assert setup.expected_debit == expected_debit


def test_generate_signals_emits_expiration_date_metadata(monkeypatch):
    strategy = _strategy(monkeypatch)

    signals = strategy.generate_signals(_market_frame())

    assert len(signals) == 1
    signal = signals[0]
    metadata = signal.metadata
    assert metadata["strategy_type"] == "butterfly"
    assert metadata["expiration_date"] >= datetime.now(UTC).date().isoformat()


def test_should_close_butterfly_hits_profit_target(monkeypatch):
    strategy = _strategy(monkeypatch)

    should_close, reason = strategy.should_close_butterfly(
        {
            "pnl_percent": 0.81,
            "unrealized_pnl": 81.0,
            "days_to_expiry": 1,
        }
    )

    assert should_close is True
    assert reason == "profit_target"


def test_should_close_butterfly_hits_stop_loss_mark(monkeypatch):
    strategy = _strategy(monkeypatch)

    should_close, reason = strategy.should_close_butterfly(
        {
            "entry_notional": 100.0,
            "quantity": 2,
            "pnl_percent": -0.60,
            "unrealized_pnl": -60.0,
            "days_to_expiry": 0,
        }
    )

    assert should_close is True
    assert reason == "stop_loss_mark"


def test_should_close_butterfly_skips_precarryover_exit_for_active_zero_dte(monkeypatch):
    strategy = _strategy(monkeypatch)

    should_close, reason = strategy.should_close_butterfly(
        {
            "pnl_percent": 0.05,
            "unrealized_pnl": 12.0,
            "days_to_expiry": 0,
            "is_hydrated_carryover": False,
        }
    )

    assert should_close is False
    assert reason == "hold"


def test_should_close_butterfly_closes_profitable_hydrated_zero_dte_carryover(monkeypatch):
    strategy = _strategy(monkeypatch)

    should_close, reason = strategy.should_close_butterfly(
        {
            "pnl_percent": 0.05,
            "unrealized_pnl": 12.0,
            "days_to_expiry": 0,
            "is_hydrated_carryover": True,
        }
    )

    assert should_close is True
    assert reason == "pre_carryover_profit_take"
