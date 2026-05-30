#!/usr/bin/env python3
"""Focused signal-contract tests for legacy D-series strategies."""

import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from Spyder.SpyderD_Strategies.SpyderD12_RSIMeanReversion import (
    RSIMeanReversionStrategy,
    RSIState,
)
from Spyder.SpyderD_Strategies.SpyderD13_MACrossover import (
    MACrossoverStrategy,
    CrossoverSignal,
    CrossoverType,
    TrendPhase,
)
from Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread import (
    CalendarLeg,
    CalendarSetup,
    CalendarSpreadStrategy,
    CalendarType,
    TermStructure,
)
from Spyder.SpyderD_Strategies.SpyderD19_JadeLizard import JadeLizardStrategy, JadeLizardState
from Spyder.SpyderD_Strategies.SpyderD38_JadeLizardZero import (
    JadeLizardZeroStrategy,
    ZeroJadeLeg,
    ZeroJadeLizardSetup,
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import OptionType


@pytest.fixture(autouse=True)
def _isolate_decision_audit(tmp_path, monkeypatch):
    """Redirect D31 decision-audit log to a temp dir for the duration of each test."""
    monkeypatch.setenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", str(tmp_path))


def _get_strategy_orchestrator_class():
    """Lazily import D31 to avoid heavy GUI/native import at collection time."""
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    return mod.StrategyOrchestrator


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None


class _ApprovedRiskManager:
    def __init__(self):
        self.requests = []

    def validate_signal(self, request):
        self.requests.append(request)
        return SimpleNamespace(approved=True)


def _risk_profile():
    return SimpleNamespace(account_size=100000)


def test_rsi_signal_builder_emits_complete_trading_signal():
    strategy = RSIMeanReversionStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )
    strategy.current_rsi = 25.0
    strategy.rsi_state = RSIState.OVERSOLD

    market_data = pd.DataFrame(
        {
            "high": [601.0, 602.0, 603.0, 604.0],
            "low": [598.0, 599.0, 600.0, 601.0],
            "close": [599.0, 600.0, 601.0, 602.0],
            "volume": [1000, 1100, 1200, 1300],
        }
    )

    signal = strategy._create_oversold_signal(market_data, divergence=None)

    assert signal is not None
    payload = signal.to_dict()
    assert payload["symbol"] == "SPY"
    assert payload["quantity"] >= 1
    assert payload["action"] == "buy"
    assert payload["strategy_id"] == "RSIMeanReversion"
    assert payload["entry_price"] > 0.0


def test_ma_signal_builder_emits_dispatchable_aliases():
    strategy = MACrossoverStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )

    crossover_signal = CrossoverSignal(
        crossover_type=CrossoverType.BULLISH_CROSS,
        fast_ma=603.0,
        slow_ma=601.0,
        distance=2.0,
        angle=35.0,
        volume_surge=True,
        volume_ratio=1.8,
        trend_strength=0.8,
        trend_phase=TrendPhase.EARLY_TREND,
        confirmation_bars=2,
        whipsaw_risk=0.1,
    )
    market_data = pd.DataFrame({"close": [600.0, 601.5, 603.0]})

    signal = strategy._convert_to_trading_signal(crossover_signal, market_data)

    assert signal is not None
    payload = signal.to_dict()
    assert payload["symbol"] == "SPY"
    assert payload["quantity"] >= 1
    assert payload["action"] == "sell"
    assert payload["strategy_id"] == "MACrossover"
    assert payload["price"] == payload["entry_price"]


def test_d31_dispatches_rsi_trading_signal_object_via_live_engine():
    StrategyOrchestrator = _get_strategy_orchestrator_class()
    strategy = RSIMeanReversionStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )
    strategy.current_rsi = 25.0
    strategy.rsi_state = RSIState.OVERSOLD
    market_data = pd.DataFrame(
        {
            "high": [601.0, 602.0, 603.0, 604.0],
            "low": [598.0, 599.0, 600.0, 601.0],
            "close": [599.0, 600.0, 601.0, 602.0],
            "volume": [1000, 1100, 1200, 1300],
        }
    )
    signal = strategy._create_oversold_signal(market_data, divergence=None)
    assert signal is not None

    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator.risk_manager = _ApprovedRiskManager()
    live_engine = MagicMock()
    live_engine.execute_order.return_value = {"status": "submitted"}
    orchestrator._live_engine = live_engine

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    assert len(orchestrator.risk_manager.requests) == 1
    request = orchestrator.risk_manager.requests[0]
    assert request.symbol == "SPY"
    assert request.quantity >= 1
    live_engine.execute_order.assert_called_once()
    order = live_engine.execute_order.call_args.args[0]
    assert order["symbol"] == "SPY"
    assert order["quantity"] >= 1
    assert order["side"] == "buy"


def test_d31_dispatches_ma_trading_signal_object_via_live_engine():
    StrategyOrchestrator = _get_strategy_orchestrator_class()
    strategy = MACrossoverStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )
    crossover_signal = CrossoverSignal(
        crossover_type=CrossoverType.BULLISH_CROSS,
        fast_ma=603.0,
        slow_ma=601.0,
        distance=2.0,
        angle=35.0,
        volume_surge=True,
        volume_ratio=1.8,
        trend_strength=0.8,
        trend_phase=TrendPhase.EARLY_TREND,
        confirmation_bars=2,
        whipsaw_risk=0.1,
    )
    market_data = pd.DataFrame({"close": [600.0, 601.5, 603.0]})
    signal = strategy._convert_to_trading_signal(crossover_signal, market_data)
    assert signal is not None

    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator.risk_manager = _ApprovedRiskManager()
    live_engine = MagicMock()
    live_engine.execute_order.return_value = {"status": "submitted"}
    orchestrator._live_engine = live_engine

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    assert len(orchestrator.risk_manager.requests) == 1
    request = orchestrator.risk_manager.requests[0]
    assert request.symbol == "SPY"
    assert request.quantity >= 1
    live_engine.execute_order.assert_called_once()
    order = live_engine.execute_order.call_args.args[0]
    assert order["symbol"] == "SPY"
    assert order["quantity"] >= 1
    assert order["side"] == "sell"


def test_calendar_spread_signal_builder_emits_dispatchable_aliases():
    strategy = CalendarSpreadStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )
    setup = CalendarSetup(
        probability_profit=0.62,
        iv_skew=0.06,
        calendar_type=CalendarType.CALL_CALENDAR,
        near_leg=CalendarLeg(
            option_type=OptionType.CALL,
            strike=600.0,
            expiry=datetime.now() + timedelta(days=14),
            position=-1,
            contracts=1,
            iv=0.20,
            premium=2.0,
            delta=0.0,
            gamma=0.0,
            vega=0.0,
            theta=0.0,
        ),
        far_leg=CalendarLeg(
            option_type=OptionType.CALL,
            strike=600.0,
            expiry=datetime.now() + timedelta(days=42),
            position=1,
            contracts=1,
            iv=0.25,
            premium=4.0,
            delta=0.0,
            gamma=0.0,
            vega=0.0,
            theta=0.0,
        ),
        time_spread=28,
        net_debit=145.0,
        max_profit=290.0,
        breakeven_points=[596.0, 606.0],
        term_structure=TermStructure.CONTANGO,
        entry_iv_rank=40.0,
    )
    market_data = pd.DataFrame({"close": [599.0, 601.0]})

    signal = strategy._create_trading_signal(setup, market_data)

    assert signal is not None
    payload = signal.to_dict()
    assert payload["symbol"] == "SPY"
    assert payload["quantity"] == 1
    assert payload["action"] == "buy"
    assert payload["strategy_id"] == "CalendarSpread"
    assert payload["entry_price"] > 0.0


def test_jade_lizard_signal_builders_emit_dispatchable_aliases():
    strategy = JadeLizardStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY"},
    )

    strategy._calculate_risk_metrics = MagicMock(
        return_value=SimpleNamespace(
            portfolio_delta=0.0,
            portfolio_gamma=0.0,
            portfolio_vega=0.0,
            portfolio_theta=0.0,
            pin_risk=False,
            early_assignment_risk=False,
            max_loss_percent=1.0,
            current_risk_level=SimpleNamespace(value="low"),
        )
    )
    setup = SimpleNamespace(
        probability_profit=0.7,
        no_upside_risk=True,
        short_put=SimpleNamespace(strike=590.0),
        short_call=SimpleNamespace(strike=610.0),
        long_call=SimpleNamespace(strike=615.0),
        total_credit=180.0,
        put_credit=120.0,
        call_spread_credit=60.0,
        breakeven=588.2,
        max_profit=180.0,
        max_loss=1200.0,
        iv_rank=55.0,
        market_sentiment=SimpleNamespace(value="neutral"),
    )
    market_data = pd.DataFrame({"close": [600.0, 602.0]})

    entry_signal = strategy._create_trading_signal(setup, market_data)

    assert entry_signal is not None
    entry_payload = entry_signal.to_dict()
    assert entry_payload["symbol"] == "SPY"
    assert entry_payload["quantity"] == 1
    assert entry_payload["action"] == "buy"
    assert entry_payload["strategy_id"] == "JadeLizard"

    strategy._update_performance_stats = MagicMock()
    position = SimpleNamespace(
        position_id="JL-1",
        current_value=75.0,
        days_held=3,
        unrealized_pnl=50.0,
        pnl_percent=27.7,
        dte=18,
        management_triggers=[],
        risk_metrics=SimpleNamespace(current_risk_level=SimpleNamespace(value="low")),
        state=JadeLizardState.MONITORING,
    )

    exit_signal = strategy._create_exit_signal(position, "profit_target")
    exit_payload = exit_signal.to_dict()
    assert exit_payload["symbol"] == "SPY"
    assert exit_payload["quantity"] == 1
    assert exit_payload["action"] == "close"
    assert exit_payload["strategy_id"] == "JadeLizard"


def test_jade_lizard_zero_signal_builder_serializes_multileg_contract():
    strategy = JadeLizardZeroStrategy(
        event_manager=_StubEventManager(),
        risk_profile=_risk_profile(),
        config={"symbol": "SPY", "target_dte": 0},
    )
    expiration = datetime.now(UTC) + timedelta(hours=4)
    setup = ZeroJadeLizardSetup(
        underlying_price=600.0,
        expiration_date=expiration,
        days_to_expiry=0,
        short_put=ZeroJadeLeg("put", 596.0, "short", 1, 0.95, -0.22, expiration),
        short_call=ZeroJadeLeg("call", 603.0, "short", 1, 0.62, 0.12, expiration),
        long_call=ZeroJadeLeg("call", 604.0, "long", 1, 0.24, 0.05, expiration),
        total_credit=1.33,
        put_credit=0.95,
        call_spread_credit=0.38,
        call_spread_width=1.0,
        max_profit=133.0,
        max_loss=59467.0,
        breakeven_lower=594.67,
        no_upside_risk=True,
        probability_profit=0.68,
        expected_move=4.1,
        entry_quality_score=0.74,
    )
    market_data = pd.DataFrame({"close": [599.5, 600.0]})

    signal = strategy._create_trading_signal(setup, market_data)

    assert signal is not None
    payload = signal.to_dict()
    assert payload["symbol"] == "SPY"
    assert payload["quantity"] == 1
    assert payload["action"] == "sell"
    assert payload["strategy_id"] == "JadeLizardZero"
    assert payload["metadata"]["target_dte"] == 0
    assert payload["metadata"]["expiration_date"] == expiration.date().isoformat()
    assert len(payload["metadata"]["legs"]) == 3
    assert payload["metadata"]["legs"][0]["position"] == "short"
