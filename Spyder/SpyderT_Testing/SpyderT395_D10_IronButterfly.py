from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies import SpyderD10_IronButterfly as d10


pytestmark = pytest.mark.unit


def _market_frame() -> pd.DataFrame:
    close = [598.4, 598.6, 598.8, 598.9, 599.0, 599.1, 599.2, 599.0, 598.9, 599.1, 599.0, 599.2]
    iv = [0.22, 0.21, 0.22, 0.23, 0.22, 0.21, 0.22, 0.23, 0.22, 0.21, 0.22, 0.23]
    return pd.DataFrame(
        {
            "close": close,
            "high": [value + 0.35 for value in close],
            "low": [value - 0.35 for value in close],
            "iv": iv,
        }
    )


def _strategy(monkeypatch, **config_overrides) -> d10.IronButterflyStrategy:
    monkeypatch.setattr(d10, "get_multileg_coordinator", lambda config=None: SimpleNamespace())

    event_manager = SimpleNamespace(
        subscribe=lambda *args, **kwargs: None,
        publish=lambda *args, **kwargs: None,
        emit=lambda *args, **kwargs: None,
        unsubscribe=lambda *args, **kwargs: None,
    )
    return d10.IronButterflyStrategy(
        event_manager=event_manager,
        config={
            "symbol": "SPY",
            "wing_width": 5.0,
            "target_dte": 25,
            **config_overrides,
        },
    )


def _analysis() -> d10.IronButterflyAnalysis:
    return d10.IronButterflyAnalysis(
        market_suitable=True,
        neutral_outlook_confirmed=True,
        atm_analysis={"current_price": 599.2},
        iv_analysis={"current_iv": 0.22, "iv_rank": 55.0, "iv_data_available": True},
        time_decay_analysis={"estimated_daily_theta": 0.03},
        expected_move_analysis={"expected_move_dollars": 4.5},
        optimal_wing_width=5.0,
        atm_strike_recommendation=600.0,
        setup_recommendation="High-vol fallback regime — Iron Butterfly",
        confidence_score=0.78,
        risk_warnings=[],
    )


def test_build_iron_butterfly_setup_returns_dispatchable_credit_profile(monkeypatch):
    strategy = _strategy(monkeypatch)
    monkeypatch.setattr(
        strategy,
        "analyze_iron_butterfly_opportunity",
        lambda market_data, option_chain=None: _analysis(),
    )

    setup = strategy.build_iron_butterfly_setup(_market_frame())

    assert setup is not None
    assert setup.atm_strike == 600.0
    assert setup.long_put_strike == 595.0
    assert setup.long_call_strike == 605.0
    assert setup.days_to_expiry == 25
    assert 0.0 < setup.expected_credit < setup.wing_width
    assert setup.max_profit == setup.expected_credit
    assert setup.max_loss == round(setup.wing_width - setup.expected_credit, 2)


def test_generate_signals_emits_dispatchable_iron_butterfly_metadata(monkeypatch):
    strategy = _strategy(monkeypatch)
    monkeypatch.setattr(
        strategy,
        "analyze_iron_butterfly_opportunity",
        lambda market_data, option_chain=None: _analysis(),
    )

    signals = strategy.generate_signals(_market_frame())

    assert len(signals) == 1
    signal = signals[0]
    payload = signal.to_dict()
    metadata = signal.metadata

    assert payload["strategy_id"] == "IronButterfly"
    assert payload["strategy_type"] == "iron_butterfly"
    assert payload["side"] == "sell"
    assert metadata["short_put_strike"] == 600.0
    assert metadata["short_call_strike"] == 600.0
    assert metadata["long_put_strike"] == 595.0
    assert metadata["long_call_strike"] == 605.0
    assert metadata["target_dte"] == 25
    assert metadata["expiration_date"] >= datetime.now(UTC).date().isoformat()
    assert metadata["setup"]["strikes"] == {
        "put_long": 595.0,
        "put_short": 600.0,
        "call_short": 600.0,
        "call_long": 605.0,
    }
