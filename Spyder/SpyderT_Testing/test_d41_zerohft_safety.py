#!/usr/bin/env python3
"""Focused safety regressions for ZeroHFT gating and D31 allowlist strictness."""

from __future__ import annotations

import Spyder.SpyderD_Strategies.SpyderD41_ZeroHFT as d41_module
from collections import deque
from datetime import datetime, timedelta
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import MarketRegime, StrategyOrchestrator
from Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor import MicroTranchePlan
from Spyder.SpyderD_Strategies.SpyderD41_ZeroHFT import ZeroHFTStrategy
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import NY, OptionType, ShortLeg, et_time


def _new_zerohft_for_gate_tests() -> ZeroHFTStrategy:
    """Build a minimal ZeroHFT instance for direct method-level safety checks."""
    strategy = ZeroHFTStrategy.__new__(ZeroHFTStrategy)
    strategy.logger = SpyderLogger.get_logger("test.zerohft")
    strategy.name = "ZeroHFT"
    strategy.strategy_type = "zero_hft"
    strategy.runtime_config = {"alias": "ZeroHFT"}
    strategy.symbol = "SPX"
    strategy._tail_hedged_session_date = None
    strategy._tail_hedge_status = "UNKNOWN"
    strategy._tail_hedge_detail = ""
    strategy._tail_hedge_retry_attempts = 0
    strategy._tail_hedge_retry_not_before = None
    strategy._tail_hedge_retry_session_date = None
    strategy._pending_short_legs_by_tag = {}
    strategy._active_short_legs = {}
    strategy._short_leg_risk_status = "UNKNOWN"
    strategy._short_leg_risk_detail = ""
    return strategy


def _sample_tranche_plan() -> MicroTranchePlan:
    return MicroTranchePlan(
        underlying="SPX",
        expiration="2026-05-20",
        long_put_symbol="SPXW260520P05280000",
        long_put_strike=5280.0,
        long_put_price=0.55,
        short_put_symbol="SPXW260520P05285000",
        short_put_strike=5285.0,
        short_put_price=1.25,
        short_put_delta=-0.11,
        short_call_symbol="SPXW260520C05315000",
        short_call_strike=5315.0,
        short_call_price=1.35,
        short_call_delta=0.10,
        long_call_symbol="SPXW260520C05320000",
        long_call_strike=5320.0,
        long_call_price=0.60,
        net_credit=1.45,
        quantity=1,
        tag="microtranche-test",
    )


def _sample_short_legs() -> list[ShortLeg]:
    return [
        ShortLeg(
            symbol="SPXW260520C05315000",
            option_type=OptionType.CALL,
            strike=5315.0,
            entry_delta=0.10,
            quantity=1,
            order_tag="microtranche-test",
        ),
        ShortLeg(
            symbol="SPXW260520P05285000",
            option_type=OptionType.PUT,
            strike=5285.0,
            entry_delta=-0.11,
            quantity=1,
            order_tag="microtranche-test",
        ),
    ]


def _prime_zerohft_for_signal_generation(strategy: ZeroHFTStrategy) -> None:
    strategy.paper_only = True
    strategy.require_defined_risk_entry = True
    strategy.profile_name = "micro_tranche"
    strategy.short_delta_target = 0.10
    strategy.max_short_delta = 0.35
    strategy.market_open_time = et_time(9, 30)
    strategy.entry_delay_minutes = 2
    strategy.runtime_cadence_enabled = True
    strategy.runtime_cadence_seconds = 60
    strategy.stop_loss = 1.50
    strategy.profit_target = 0.30
    strategy.tranche_quantity = 1
    strategy.min_premium = 0.35
    strategy.max_daily_trades = 48
    strategy.max_positions = 4
    strategy.max_vix = 35.0
    strategy.min_iv_rank = 25.0
    strategy.min_probability_profit = 0.60
    strategy._daily_tranche_count = 0
    strategy._refresh_daily_counters = lambda: None
    strategy._ensure_tail_hedge_ready = lambda: True
    strategy._within_entry_window = lambda: True
    strategy._calendar_allows_entry = lambda: True
    strategy._gamma_allows_entry = lambda: True
    strategy.option_chain_fetcher = None


def test_zerohft_constructor_exposes_runtime_config() -> None:
    strategy = ZeroHFTStrategy(
        event_manager=MagicMock(),
        risk_profile=MagicMock(),
        config={},
    )

    assert strategy.runtime_config["alias"] == "ZeroHFT"
    assert strategy.symbol == "SPX"
    assert strategy.runtime_config["runtime_cadence_seconds"] == 60
    assert strategy.runtime_config["max_daily_trades"] == 48
    assert strategy.runtime_config["spread_width_points"] == 3.0


def test_zerohft_hard_tail_hedge_policy_blocks_entries(monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.tail_hedge_required = True
    strategy.tail_hedge_max_retries = 2
    strategy.tail_hedge_establisher = None

    monkeypatch.delenv("SPYDER_ZEROHFT_TAIL_HEDGE_STATUS", raising=False)
    monkeypatch.delenv("SPYDER_ZEROHFT_TAIL_HEDGE_DETAIL", raising=False)

    allowed = strategy._ensure_tail_hedge_ready()

    assert allowed is False
    assert strategy._tail_hedge_status == "HALTED"
    assert "HARD policy" in strategy._tail_hedge_detail


def test_zerohft_tail_hedge_retry_is_non_blocking(monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.tail_hedge_required = True
    strategy.tail_hedge_max_retries = 3
    strategy.tail_hedge_retry_seconds = 30

    calls: list[str] = []
    current_now = [datetime(2026, 6, 1, 9, 45, tzinfo=NY)]

    monkeypatch.setattr(d41_module, "now_et", lambda: current_now[0])
    strategy.tail_hedge_establisher = lambda symbol: calls.append(symbol) or False

    assert strategy._ensure_tail_hedge_ready() is False
    assert strategy._tail_hedge_status == "UNKNOWN"
    assert len(calls) == 1

    current_now[0] = current_now[0] + timedelta(seconds=10)
    assert strategy._ensure_tail_hedge_ready() is False
    assert len(calls) == 1
    assert "retry scheduled" in strategy._tail_hedge_detail.lower()

    current_now[0] = datetime(2026, 6, 1, 9, 45, 31, tzinfo=NY)
    assert strategy._ensure_tail_hedge_ready() is False
    assert len(calls) == 2


def test_zerohft_soft_tail_hedge_allows_after_retry_budget(monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.tail_hedge_required = False
    strategy.tail_hedge_max_retries = 2
    strategy.tail_hedge_retry_seconds = 30

    current_now = [datetime(2026, 6, 1, 10, 0, tzinfo=NY)]

    monkeypatch.setattr(d41_module, "now_et", lambda: current_now[0])
    strategy.tail_hedge_establisher = lambda symbol: False

    assert strategy._ensure_tail_hedge_ready() is False
    assert strategy._tail_hedge_status == "UNKNOWN"

    current_now[0] = datetime(2026, 6, 1, 10, 0, 31, tzinfo=NY)
    assert strategy._ensure_tail_hedge_ready() is True
    assert strategy._tail_hedge_status == "UNHEDGED"
    assert "soft mode" in strategy._tail_hedge_detail.lower()


def test_zerohft_tail_hedge_allocator_can_mark_session_hedged() -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.tail_hedge_required = True
    strategy.tail_hedge_allocator = lambda symbol: symbol == "SPX"

    assert strategy._ensure_tail_hedge_ready() is True
    assert strategy._tail_hedge_status == "HEDGED"
    assert "allocated" in strategy._tail_hedge_detail.lower()


def test_zerohft_paper_only_mode_blocks_signal_generation(monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.paper_only = True
    strategy._refresh_daily_counters = lambda: None

    monkeypatch.setattr(
        ZeroHFTStrategy,
        "_is_paper_mode",
        staticmethod(lambda: False),
    )

    signals = strategy.generate_signals(pd.DataFrame())

    assert signals == []


def test_zerohft_logs_paper_mode_block(caplog, monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    strategy.paper_only = True
    strategy._refresh_daily_counters = lambda: None

    monkeypatch.setattr(
        ZeroHFTStrategy,
        "_is_paper_mode",
        staticmethod(lambda: False),
    )

    with caplog.at_level("INFO"):
        signals = strategy.generate_signals(pd.DataFrame())

    assert signals == []
    assert "ZeroHFT entry blocked at paper_mode" in caplog.text


def test_zerohft_runtime_cadence_aligns_to_two_minute_boundaries() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.time_stop = et_time(15, 50)

    before_open = datetime(2026, 6, 1, 9, 31, 15, tzinfo=NY)
    mid_cycle = datetime(2026, 6, 1, 9, 33, 5, tzinfo=NY)

    assert strategy.next_runtime_evaluation_at(before_open) == datetime(
        2026,
        6,
        1,
        9,
        32,
        tzinfo=NY,
    )
    assert strategy.next_runtime_evaluation_at(mid_cycle) == datetime(
        2026,
        6,
        1,
        9,
        34,
        tzinfo=NY,
    )


def test_d31_normalize_allowed_strategy_token_keeps_zerohft_distinct() -> None:
    canonical_map = {
        "zerohft": "ZeroHFT",
        "zerodte": "ZeroDTE",
    }

    assert StrategyOrchestrator._normalize_allowed_strategy_token("ZeroHFT", canonical_map) == "ZeroHFT"
    assert StrategyOrchestrator._normalize_allowed_strategy_token("zerohft", canonical_map) == "ZeroHFT"
    assert StrategyOrchestrator._normalize_allowed_strategy_token("ZeroHFTStrategy", canonical_map) == "ZeroHFT"


def test_d31_env_allowlist_override_applies_zerohft_without_alias(monkeypatch) -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31")
    orchestrator.lean_strategy_allowlist = {
        "ZeroHFT",
        "ZeroHFTStrategy",
        "ZeroDTE",
        "ZeroDTEStrategy",
        "IronCondor",
        "IronCondorStrategy",
    }

    monkeypatch.setenv("SPYDER_ALLOWED_STRATEGIES", "ZeroHFT")

    orchestrator._apply_env_allowed_strategies_override()

    assert orchestrator.lean_strategy_allowlist == {"ZeroHFT", "ZeroHFTStrategy"}


def test_d31_lean_mode_falls_back_to_sole_allowlisted_zerohft() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.lean_fallback")
    orchestrator.lean_mode = True
    orchestrator.lean_strategy_allowlist = {"ZeroHFT", "ZeroHFTStrategy"}
    orchestrator.market_regime = SimpleNamespace(current_regime=MarketRegime.SIDEWAYS_LOW_VOL)
    orchestrator._last_selector_feature_flag = "test"
    orchestrator._record_selector_outcome_audit = lambda *args, **kwargs: None
    orchestrator._select_strategy_name_for_regime = lambda: ("IronCondor", "Range/calm fallback regime — Iron Condor")

    weights = orchestrator._get_regime_strategy_weights()

    assert weights == {"ZeroHFT": 1.0}


def test_zerohft_defined_risk_mode_skips_single_leg_fallback() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.micro_executor = None
    strategy.option_chain_fetcher = lambda symbol: [
        {"option_type": "call", "strike": 5315.0, "greeks": {"delta": 0.10}, "bid": 1.30, "ask": 1.40, "symbol": "CALL"},
        {"option_type": "put", "strike": 5285.0, "greeks": {"delta": -0.10}, "bid": 1.20, "ask": 1.30, "symbol": "PUT"},
    ]

    signals = strategy.generate_signals(pd.DataFrame())

    assert signals == []


def test_zerohft_delta_band_rejects_out_of_band_shorts() -> None:
    # Only out-of-band strikes exist (calls too deep, puts too cheap): skip entry.
    options = [
        {"option_type": "call", "strike": 5315.0, "greeks": {"delta": 0.40}, "symbol": "C1"},
        {"option_type": "put", "strike": 5285.0, "greeks": {"delta": -0.02}, "symbol": "P1"},
    ]

    short_call, short_put = ZeroHFTStrategy._select_delta_targets(
        options,
        0.10,
        delta_min=0.07,
        delta_max=0.18,
    )

    assert short_call is None
    assert short_put is None


def test_zerohft_delta_band_keeps_in_band_short() -> None:
    # In-band candidate must be preferred; out-of-band candidate must be ignored.
    options = [
        {"option_type": "call", "strike": 5315.0, "greeks": {"delta": 0.11}, "symbol": "C_IN"},
        {"option_type": "call", "strike": 5300.0, "greeks": {"delta": 0.45}, "symbol": "C_OUT"},
        {"option_type": "put", "strike": 5285.0, "greeks": {"delta": -0.12}, "symbol": "P_IN"},
        {"option_type": "put", "strike": 5295.0, "greeks": {"delta": -0.55}, "symbol": "P_OUT"},
    ]

    short_call, short_put = ZeroHFTStrategy._select_delta_targets(
        options,
        0.10,
        delta_min=0.07,
        delta_max=0.18,
    )

    assert short_call["symbol"] == "C_IN"
    assert short_put["symbol"] == "P_IN"


def test_micro_tranche_executor_delta_band_rejects_out_of_band_shorts() -> None:
    from Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor import MicroTrancheExecutor

    options = [
        {"option_type": "call", "strike": 5315.0, "greeks": {"delta": 0.40}, "symbol": "C1"},
        {"option_type": "put", "strike": 5285.0, "greeks": {"delta": -0.02}, "symbol": "P1"},
    ]

    short_call, short_put = MicroTrancheExecutor.select_delta_targets(
        options,
        0.10,
        delta_min=0.07,
        delta_max=0.18,
    )

    assert short_call is None
    assert short_put is None


def test_zerohft_max_positions_caps_concurrent_tranches() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.max_positions = 1
    strategy.micro_executor = SimpleNamespace(
        plan_once=lambda: (_sample_tranche_plan(), _sample_short_legs())
    )
    # One tranche already open (two legs share one order tag).
    strategy._active_short_legs = {leg.symbol: leg for leg in _sample_short_legs()}

    assert strategy._active_tranche_count() == 1
    assert strategy.generate_signals(pd.DataFrame()) == []


def test_zerohft_vix_gate_blocks_high_vol(monkeypatch) -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.max_vix = 35.0
    strategy.micro_executor = SimpleNamespace(
        plan_once=lambda: (_sample_tranche_plan(), _sample_short_legs())
    )

    high_vix = pd.DataFrame({"vix": [42.0]})
    assert strategy._market_data_allows_entry(high_vix) is False
    assert strategy.generate_signals(high_vix) == []

    calm_vix = pd.DataFrame({"vix": [18.0]})
    assert strategy._market_data_allows_entry(calm_vix) is True


def test_zerohft_iv_rank_gate_blocks_low_rank() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.min_iv_rank = 25.0

    # Percentage form below floor.
    assert strategy._market_data_allows_entry(pd.DataFrame({"iv_rank": [10.0]})) is False
    # Fraction form (0-1) is normalized to a percentage.
    assert strategy._market_data_allows_entry(pd.DataFrame({"iv_rank": [0.40]})) is True
    # Absent column fails open.
    assert strategy._market_data_allows_entry(pd.DataFrame({"close": [5300.0]})) is True


def test_zerohft_probability_profit_gate_blocks_low_pop() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.min_probability_profit = 0.60

    # POP ~= 1 - 0.10 - 0.11 = 0.79 → passes.
    assert strategy._plan_meets_probability_profit(_sample_tranche_plan()) is True

    risky_plan = _sample_tranche_plan()
    risky_plan.short_call_delta = 0.30
    risky_plan.short_put_delta = -0.30  # POP ~= 0.40 → blocked
    assert strategy._plan_meets_probability_profit(risky_plan) is False


def test_zerohft_multileg_plan_emits_single_serialized_signal() -> None:
    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.micro_executor = SimpleNamespace(plan_once=lambda: (_sample_tranche_plan(), _sample_short_legs()))

    signals = strategy.generate_signals(pd.DataFrame())

    assert len(signals) == 1
    signal = signals[0]
    payload = signal.to_dict()
    assert signal.option_symbol == ""
    assert strategy.validate_signal(signal) is True
    assert payload["strategy_id"] == "ZeroHFT"
    assert payload["strategy_type"] == "zero_hft"
    assert payload["metadata"]["expiration_date"] == "2026-05-20"
    assert [leg["role"] for leg in payload["metadata"]["legs"]] == [
        "long_put",
        "short_put",
        "short_call",
        "long_call",
    ]
    assert set(strategy._pending_short_legs_by_tag) == {"microtranche-test"}


def test_zerohft_registers_accepted_short_legs_from_dispatch(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_STATUS", raising=False)
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_DETAIL", raising=False)

    strategy = _new_zerohft_for_gate_tests()
    _prime_zerohft_for_signal_generation(strategy)
    strategy.micro_executor = SimpleNamespace(plan_once=lambda: (_sample_tranche_plan(), _sample_short_legs()))

    signal = strategy.generate_signals(pd.DataFrame())[0]
    raw_signal = signal.to_dict()

    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.shortlegs")
    accepted_leg_orders = orchestrator._build_paper_serialized_multileg_leg_orders(
        raw_signal,
        "SPX",
        1,
        "ZeroHFT",
    )

    strategy.register_dispatched_short_legs(raw_signal, accepted_leg_orders)

    active_short_legs = strategy.get_active_short_legs()
    expected_symbols = {
        leg_order["symbol"]
        for leg_order in accepted_leg_orders
        if leg_order["side"] == "sell_to_open"
    }
    assert {leg.symbol for leg in active_short_legs} == expected_symbols
    assert {leg.option_type for leg in active_short_legs} == {
        OptionType.CALL,
        OptionType.PUT,
    }
    assert all(leg.order_tag == "microtranche-test" for leg in active_short_legs)
    assert os.environ["SPYDER_ZEROHFT_SHORT_LEG_STATUS"] == "ACTIVE"
    assert "Monitoring 2 active short legs" in os.environ["SPYDER_ZEROHFT_SHORT_LEG_DETAIL"]


def test_zerohft_remove_active_short_legs_updates_manifest(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_STATUS", raising=False)
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_DETAIL", raising=False)

    strategy = _new_zerohft_for_gate_tests()
    strategy._active_short_legs = {
        leg.symbol: leg
        for leg in _sample_short_legs()
    }

    strategy.remove_active_short_legs(["SPXW260520C05315000"])

    remaining_symbols = {leg.symbol for leg in strategy.get_active_short_legs()}
    assert remaining_symbols == {"SPXW260520P05285000"}
    assert os.environ["SPYDER_ZEROHFT_SHORT_LEG_STATUS"] == "ACTIVE"
    assert "Monitoring 1 active short leg" in os.environ["SPYDER_ZEROHFT_SHORT_LEG_DETAIL"]


def test_d31_resolves_and_notifies_active_strategy_for_serialized_multileg_dispatch() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.notify")
    strategy = _new_zerohft_for_gate_tests()
    strategy.register_dispatched_short_legs = MagicMock()
    orchestrator.active_strategies = {"ZeroHFT_deadbeef": strategy}

    raw_signal = _new_zerohft_for_gate_tests()._build_multileg_signal(_sample_tranche_plan()).to_dict()
    accepted_leg_orders = [{"symbol": "SPXW260520C05315000", "side": "sell_to_open", "quantity": 1}]

    orchestrator._notify_strategy_serialized_multileg_dispatch(raw_signal, accepted_leg_orders)

    strategy.register_dispatched_short_legs.assert_called_once_with(raw_signal, accepted_leg_orders)


def test_d31_reconciles_short_leg_manifest_with_open_positions(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_STATUS", raising=False)
    monkeypatch.delenv("SPYDER_ZEROHFT_SHORT_LEG_DETAIL", raising=False)

    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.reconcile")
    strategy = _new_zerohft_for_gate_tests()

    call_leg = ShortLeg(
        symbol="SPX260520C05315000",
        option_type=OptionType.CALL,
        strike=5315.0,
        entry_delta=0.10,
        quantity=1,
        order_tag="microtranche-test",
    )
    put_leg = ShortLeg(
        symbol="SPX260520P05285000",
        option_type=OptionType.PUT,
        strike=5285.0,
        entry_delta=-0.11,
        quantity=1,
        order_tag="microtranche-test",
    )
    strategy._active_short_legs = {
        call_leg.symbol: call_leg,
        put_leg.symbol: put_leg,
    }

    supervisor = SimpleNamespace(
        _get_positions_for_flatten=lambda: [
            {"option_symbol": "SPX260520P05285000", "quantity": -1}
        ]
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor.get_session_supervisor",
        lambda: supervisor,
    )

    removed_symbols = orchestrator._reconcile_strategy_active_short_legs(strategy)

    assert removed_symbols == ["SPX260520C05315000"]
    assert [leg.symbol for leg in strategy.get_active_short_legs()] == ["SPX260520P05285000"]
    assert os.environ["SPYDER_ZEROHFT_SHORT_LEG_STATUS"] == "ACTIVE"
    assert "Reconciled 1 stale short leg" in os.environ["SPYDER_ZEROHFT_SHORT_LEG_DETAIL"]


def test_d31_evaluates_short_leg_risk_and_removes_breached_leg() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.shortleg_risk")
    captured_orders: list[dict[str, object]] = []
    quote_client = SimpleNamespace(
        get_option_chain_with_greeks=lambda underlying, expiration: [
            {
                "symbol": "SPX260520C05315000",
                "option_type": "call",
                "strike": 5315.0,
                "bid": 6.0,
                "ask": 6.2,
                "greeks": {"delta": 0.45},
            }
        ]
    )
    orchestrator._live_engine = SimpleNamespace(
        _get_paper_option_quote_client=lambda: quote_client,
        execute_order=lambda order: captured_orders.append(order) or {"status": "filled", "order_id": "close-1"},
    )

    strategy = _new_zerohft_for_gate_tests()
    strategy.max_short_delta = 0.35
    breached_leg = ShortLeg(
        symbol="SPX260520C05315000",
        option_type=OptionType.CALL,
        strike=5315.0,
        entry_delta=0.10,
        quantity=1,
        order_tag="microtranche-test",
    )
    strategy._active_short_legs = {breached_leg.symbol: breached_leg}

    closed_legs = orchestrator._evaluate_strategy_short_leg_risk("ZeroHFT", strategy)

    assert [leg.symbol for leg in closed_legs] == ["SPX260520C05315000"]
    assert strategy.get_active_short_legs() == []
    assert captured_orders == [
        {
            "symbol": "SPX260520C05315000",
            "side": "buy_to_close",
            "quantity": 1,
            "order_type": "market",
            "strategy_id": "ZeroHFT",
            "tag": "microtranche-test-delta-stop",
        }
    ]
    assert os.environ["SPYDER_ZEROHFT_SHORT_LEG_STATUS"] == "CLEAR"
    assert "Closed 1 short leg via risk pass" in os.environ["SPYDER_ZEROHFT_SHORT_LEG_DETAIL"]


def test_d31_short_leg_risk_leaves_leg_when_delta_below_threshold() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.shortleg_risk_safe")
    captured_orders: list[dict[str, object]] = []
    quote_client = SimpleNamespace(
        get_option_chain_with_greeks=lambda underlying, expiration: [
            {
                "symbol": "SPX260520P05285000",
                "option_type": "put",
                "strike": 5285.0,
                "bid": 1.5,
                "ask": 1.6,
                "greeks": {"delta": -0.20},
            }
        ]
    )
    orchestrator._live_engine = SimpleNamespace(
        _get_paper_option_quote_client=lambda: quote_client,
        execute_order=lambda order: captured_orders.append(order) or {"status": "filled", "order_id": "close-1"},
    )

    strategy = _new_zerohft_for_gate_tests()
    strategy.max_short_delta = 0.35
    safe_leg = ShortLeg(
        symbol="SPX260520P05285000",
        option_type=OptionType.PUT,
        strike=5285.0,
        entry_delta=-0.11,
        quantity=1,
        order_tag="microtranche-test",
    )
    strategy._active_short_legs = {safe_leg.symbol: safe_leg}

    closed_legs = orchestrator._evaluate_strategy_short_leg_risk("ZeroHFT", strategy)

    assert closed_legs == []
    assert [leg.symbol for leg in strategy.get_active_short_legs()] == ["SPX260520P05285000"]
    assert captured_orders == []


def test_d31_zero_hft_defaults_inject_quote_dependencies() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.defaults")
    orchestrator._audit_run_mode = "paper"
    quote_client = SimpleNamespace(
        get_option_expirations=lambda symbol: {"expirations": {"date": ["2026-05-20"]}},
        get_option_chain_with_greeks=lambda symbol, expiration: [],
    )
    orchestrator._live_engine = SimpleNamespace(
        _get_paper_option_quote_client=lambda: quote_client,
    )

    resolved = orchestrator._apply_strategy_runtime_config_defaults("ZeroHFT", {})

    assert resolved["target_dte"] == 0
    assert resolved["require_defined_risk_entry"] is True
    assert resolved["broker_client"].trading_mode == "paper"
    assert resolved["broker_client"].get_option_expirations("SPX") == {
        "expirations": {"date": ["2026-05-20"]}
    }
    assert resolved["gamma_engine"].underlying == "SPX"


def test_d31_live_engine_wiring_backfills_zero_hft_planner() -> None:
    orchestrator = StrategyOrchestrator(
        event_manager=SimpleNamespace(
            subscribe=lambda *args, **kwargs: None,
            emit=lambda *args, **kwargs: None,
            publish=lambda *args, **kwargs: None,
            unsubscribe=lambda *args, **kwargs: None,
        )
    )
    orchestrator.logger = SpyderLogger.get_logger("test.d31.zerohft_backfill")
    orchestrator._audit_run_mode = "paper"

    strategy = _new_zerohft_for_gate_tests()
    strategy.calendar_service = SimpleNamespace(
        entry_decision=lambda *_args, **_kwargs: SimpleNamespace(halt=False, reason=""),
    )
    strategy.entry_window_end = et_time(15, 35)
    strategy._entry_start_time = lambda session_date=None: et_time(9, 32)
    strategy.micro_executor = None
    strategy.broker_client = None
    strategy.gamma_engine = None
    orchestrator.active_strategies = {"ZeroHFT": strategy}

    quote_client = SimpleNamespace(
        get_option_expirations=lambda symbol: {"expirations": {"date": ["2026-05-20"]}},
        get_option_chain_with_greeks=lambda symbol, expiration: [],
    )

    orchestrator.set_live_engine(
        SimpleNamespace(_get_paper_option_quote_client=lambda: quote_client)
    )

    assert strategy.broker_client is not None
    assert strategy.gamma_engine is not None
    assert strategy.micro_executor is not None
    assert strategy.runtime_config["broker_client"] is strategy.broker_client


def test_d31_builds_zero_hft_serialized_multileg_leg_orders() -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.routing")

    signal = _new_zerohft_for_gate_tests()._build_multileg_signal(_sample_tranche_plan()).to_dict()
    leg_orders = orchestrator._build_paper_serialized_multileg_leg_orders(
        signal,
        "SPX",
        1,
        "ZeroHFT",
    )

    assert len(leg_orders) == 4
    assert [order["side"] for order in leg_orders] == [
        "buy_to_open",
        "sell_to_open",
        "sell_to_open",
        "buy_to_open",
    ]
    assert all(order["strategy_id"] == "ZeroHFT" for order in leg_orders)
    assert all(order["multileg_leg_execution"] is True for order in leg_orders)


def test_d31_market_data_fanout_skips_runtime_cadence_strategy() -> None:
    orchestrator = StrategyOrchestrator(
        event_manager=SimpleNamespace(
            subscribe=lambda *args, **kwargs: None,
            emit=lambda *args, **kwargs: None,
            publish=lambda *args, **kwargs: None,
            unsubscribe=lambda *args, **kwargs: None,
        )
    )
    strategy = SimpleNamespace(
        symbol="SPX",
        process_market_data=MagicMock(),
        uses_runtime_cadence=lambda: True,
        next_runtime_evaluation_at=lambda now: now,
    )
    orchestrator.active_strategies = {"ZeroHFT": strategy}

    orchestrator._on_market_data_event(
        SimpleNamespace(data={"symbol": "SPX", "tick": {"last": 5300.0}})
    )

    strategy.process_market_data.assert_not_called()
    assert "ZeroHFT" in orchestrator._scheduled_strategy_due_at


def test_d31_evaluate_strategy_from_cache_feeds_runtime_strategy() -> None:
    orchestrator = StrategyOrchestrator(
        event_manager=SimpleNamespace(
            subscribe=lambda *args, **kwargs: None,
            emit=lambda *args, **kwargs: None,
            publish=lambda *args, **kwargs: None,
            unsubscribe=lambda *args, **kwargs: None,
        )
    )
    strategy = SimpleNamespace(symbol="SPX", process_market_data=MagicMock())
    orchestrator.active_strategies = {"ZeroHFT": strategy}
    orchestrator.market_data_cache = {
        "SPX": deque(
            [{"symbol": "SPX", "last": 5300.0, "close": 5300.0}],
            maxlen=10,
        )
    }

    result = orchestrator._evaluate_strategy_from_cache("ZeroHFT", reason="test")

    assert result is True
    strategy.process_market_data.assert_called_once()
    market_df = strategy.process_market_data.call_args.args[0]
    assert list(market_df["symbol"])[-1] == "SPX"
    assert float(list(market_df["close"])[-1]) == 5300.0


def test_d31_dispatch_routes_wrapped_zero_hft_signal_to_serialized_multileg(monkeypatch) -> None:
    event_manager = SimpleNamespace(
        subscribe=lambda *args, **kwargs: None,
        emit=lambda *args, **kwargs: None,
        publish=lambda *args, **kwargs: None,
        unsubscribe=lambda *args, **kwargs: None,
    )
    orchestrator = StrategyOrchestrator(event_manager=event_manager)
    orchestrator.set_decision_audit_context(run_mode="paper", source_context="session_supervisor")
    orchestrator._live_engine = object()
    monkeypatch.setattr(orchestrator, "_get_duplicate_open_position_source", lambda *args, **kwargs: None)

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        orchestrator,
        "_dispatch_paper_serialized_multileg",
        lambda **kwargs: captured.update(kwargs),
    )

    signal = _new_zerohft_for_gate_tests()._build_multileg_signal(_sample_tranche_plan())

    orchestrator._dispatch_approved_signal({"signal": signal})

    assert captured
    raw_signal = captured["raw_signal"]
    assert isinstance(raw_signal, dict)
    assert raw_signal["strategy_id"] == "ZeroHFT"
    assert raw_signal["metadata"]["legs"][0]["role"] == "long_put"


def test_d31_dispatch_paper_serialized_multileg_notifies_strategy_callback(monkeypatch) -> None:
    orchestrator = StrategyOrchestrator.__new__(StrategyOrchestrator)
    orchestrator.logger = SpyderLogger.get_logger("test.d31.dispatch_notify")
    orchestrator._live_engine = SimpleNamespace(
        execute_order=lambda leg_order: {
            "status": "filled",
            "order_id": f"accepted-{leg_order['symbol']}",
        }
    )
    orchestrator._record_signal_dispatch_outcome_safe = lambda *args, **kwargs: None
    orchestrator._record_signal_drop = lambda *args, **kwargs: None
    orchestrator._clear_pending_entry_reservation = lambda *args, **kwargs: None
    orchestrator._clear_pending_exit_reservation = lambda *args, **kwargs: None

    captured: dict[str, object] = {}
    monkeypatch.setattr(
        orchestrator,
        "_notify_strategy_serialized_multileg_dispatch",
        lambda raw_signal, accepted_leg_orders: captured.update(
            {
                "raw_signal": raw_signal,
                "accepted_leg_orders": accepted_leg_orders,
            }
        ),
    )

    raw_signal = _new_zerohft_for_gate_tests()._build_multileg_signal(_sample_tranche_plan()).to_dict()

    orchestrator._dispatch_paper_serialized_multileg(
        signal=raw_signal,
        raw_signal=raw_signal,
        symbol="SPX",
        quantity=1,
        strategy_id="ZeroHFT",
        pivot_context="test",
    )

    assert captured["raw_signal"] == raw_signal
    accepted_leg_orders = captured["accepted_leg_orders"]
    assert isinstance(accepted_leg_orders, list)
    assert len(accepted_leg_orders) == 4
