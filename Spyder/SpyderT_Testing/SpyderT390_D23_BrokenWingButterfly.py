from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies import SpyderD23_BrokenWingButterfly as d23
from Spyder.SpyderD_Strategies import SpyderD32_MultiLegStrategyCoordinator as d32


pytestmark = pytest.mark.unit


def _market_frame() -> pd.DataFrame:
    close = [598.0, 598.2, 598.1, 598.4, 598.5, 598.7, 598.9, 599.0, 599.2, 599.1, 599.3, 599.4]
    iv = [0.20, 0.21, 0.19, 0.22, 0.23, 0.21, 0.24, 0.22, 0.23, 0.21, 0.24, 0.23]
    return pd.DataFrame(
        {
            "close": close,
            "high": [value + 0.5 for value in close],
            "low": [value - 0.5 for value in close],
            "iv": iv,
        }
    )


def _strategy(monkeypatch, **config_overrides) -> d23.BrokenWingButterflyStrategy:
    monkeypatch.setattr(d23, "get_multileg_coordinator", lambda config=None: SimpleNamespace())

    event_manager = SimpleNamespace(
        subscribe=lambda *args, **kwargs: None,
        publish=lambda *args, **kwargs: None,
        emit=lambda *args, **kwargs: None,
        unsubscribe=lambda *args, **kwargs: None,
    )
    return d23.BrokenWingButterflyStrategy(
        event_manager=event_manager,
        config={
            "symbol": "SPY",
            "upper_width": 1.0,
            "lower_width": 3.0,
            "body_strike_offset": 1.0,
            "min_credit": 0.15,
            "prefer_live_chain": False,
            **config_overrides,
        }
    )


def test_build_bwb_setup_returns_credit_profile(monkeypatch):
    strategy = _strategy(monkeypatch)

    setup = strategy.build_broken_wing_butterfly_setup(_market_frame())

    assert setup is not None
    assert setup.upper_wing_strike == setup.body_strike + 1.0
    assert setup.lower_wing_strike == setup.body_strike - 3.0
    assert setup.expected_credit >= 0.15
    assert setup.max_profit > setup.expected_credit
    assert setup.probability_of_profit >= 0.55


def test_build_multileg_structure_preserves_ratio_metadata(monkeypatch):
    strategy = _strategy(monkeypatch)
    setup = strategy.build_broken_wing_butterfly_setup(_market_frame())

    assert setup is not None

    structure = strategy._build_multileg_structure_from_setup(setup)

    assert structure.strategy_type == d32.MultiLegStrategyType.BROKEN_WING_BUTTERFLY
    assert [leg.quantity for leg in structure.legs] == [1, -2, 1]
    assert structure.underlying_symbol == "SPY"
    assert structure.contracts == 1


def test_d32_submit_combo_order_preserves_bwb_leg_ratio(monkeypatch):
    strategy = _strategy(monkeypatch)
    setup = strategy.build_broken_wing_butterfly_setup(_market_frame())

    assert setup is not None

    order_manager = SimpleNamespace(
        submit_multileg_order=MagicMock(
            return_value=SimpleNamespace(success=True, tradier_order_id=99001, message="ok")
        )
    )
    coordinator = d32.MultiLegStrategyCoordinator(config={"symbol": "SPY"}, order_manager=order_manager)

    structure = strategy._build_multileg_structure_from_setup(setup)

    order_id = coordinator._submit_combo_order(structure, "test-bwb")

    assert order_id == 99001
    submitted_legs = order_manager.submit_multileg_order.call_args.kwargs["legs"]
    assert [leg.quantity for leg in submitted_legs] == [1, 2, 1]
    assert [leg.side.value for leg in submitted_legs] == [
        "buy_to_open",
        "sell_to_open",
        "buy_to_open",
    ]


def test_build_bwb_setup_uses_live_chain_alignment_and_mids(monkeypatch):
    strategy = _strategy(monkeypatch, prefer_live_chain=True)
    listed_expiration = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    live_mids = {
        600.0: 1.60,
        599.0: 1.30,
        598.0: 0.95,
        597.0: 0.55,
        596.0: 0.35,
        595.0: 0.25,
    }
    fake_client = SimpleNamespace(
        get_option_expirations=lambda _symbol: {"expirations": {"date": [listed_expiration]}},
        get_option_chain_with_greeks=lambda _symbol, _expiration: [
            SimpleNamespace(symbol="SPY", strike=600.0, option_type="put", bid=1.55, ask=1.65, last=1.60, mid=1.60, iv=0.26, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=599.0, option_type="put", bid=1.25, ask=1.35, last=1.30, mid=1.30, iv=0.25, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=598.0, option_type="put", bid=0.90, ask=1.00, last=0.95, mid=0.95, iv=0.24, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=597.0, option_type="put", bid=0.50, ask=0.60, last=0.55, mid=0.55, iv=0.23, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=596.0, option_type="put", bid=0.30, ask=0.40, last=0.35, mid=0.35, iv=0.22, expiration=listed_expiration),
            SimpleNamespace(symbol="SPY", strike=595.0, option_type="put", bid=0.20, ask=0.30, last=0.25, mid=0.25, iv=0.21, expiration=listed_expiration),
        ],
    )
    monkeypatch.setattr(strategy, "_get_live_quote_client", lambda: fake_client)

    setup = strategy.build_broken_wing_butterfly_setup(_market_frame())

    assert setup is not None
    assert setup.expiration_date.date().isoformat() == listed_expiration
    assert setup.upper_wing_strike > setup.body_strike > setup.lower_wing_strike
    assert setup.lower_width > setup.upper_width
    assert setup.body_strike < float(_market_frame()["close"].iloc[-1])
    expected_credit = round(
        (live_mids[setup.body_strike] * 2.0)
        - live_mids[setup.upper_wing_strike]
        - live_mids[setup.lower_wing_strike],
        2,
    )
    assert setup.expected_credit == expected_credit
