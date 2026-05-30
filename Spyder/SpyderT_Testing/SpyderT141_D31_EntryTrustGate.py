#!/usr/bin/env python3
"""Focused tests for D31 entry trust gating via F09 market-structure controls."""

import importlib
import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters


@pytest.fixture(autouse=True)
def _isolate_decision_audit(tmp_path, monkeypatch):
    """Redirect D31 decision-audit log to a temp dir for the duration of each test.

    Prevents tests from polluting the production ``logs/decisions/`` JSONL files.
    """
    monkeypatch.setenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", str(tmp_path))


def _get_strategy_orchestrator_class():
    """Lazily import D31 to avoid heavy GUI/native import at collection time."""
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    return mod.StrategyOrchestrator


class _MockConfigManager:
    def get_config(self, key, default=None):
        if key == 'entry_filters':
            return {}
        return default

    def is_feature_enabled(self, key):
        if key == 'adaptive_entry_filters':
            return False
        return False

    def get(self, key, default=None):
        values = {
            'autonomous_readiness.data_quality': {
                'enforce_hard_slo': True,
                'min_bucket_quality': 0.7,
                'required_buckets': ['VOL_SURFACE', 'DEALER_FLOW'],
            },
            'autonomous_readiness.market_structure': {
                'min_surface_confidence': 0.6,
                'max_surface_age_ms': 120000,
                'min_term_slope_0_7': -0.05,
                'max_abs_rr_25d': 0.25,
                'max_abs_fly_25d': 0.35,
                'min_wall_confidence': 0.55,
                'zero_gamma_buffer_pct': 0.01,
                'max_flow_imbalance': 0.85,
            },
        }
        return values.get(key, default)


class _StubEventManager:
    def __init__(self):
        self.handlers = {}
        self.emit = MagicMock()
        self.publish = MagicMock()

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

class _StubMetricsOrchestrator:
    def __init__(self, conditions):
        self._conditions = conditions

    def get_current_market_conditions(self):
        return self._conditions


class _ApprovedRiskManager:
    def __init__(self):
        self.validate_signal = MagicMock(return_value=SimpleNamespace(approved=True))
        self.validate_overlay_slot = MagicMock(
            return_value=SimpleNamespace(allow=True, reason_code='admitted')
        )


def _healthy_conditions():
    return {
        'spy_change_pct': 0.65,
        'qqq_change_pct': 0.92,
        'iwm_change_pct': 0.88,
        'xlk_change_pct': 1.10,
        'xlf_change_pct': 0.82,
        'surface_confidence': 0.88,
        'surface_age_ms': 15000.0,
        'term_slope_0_7': 0.03,
        'rr_25d': 0.05,
        'fly_25d': 0.04,
        'wall_confidence': 0.82,
        'flow_imbalance': 0.25,
        'dealer_flow': {
            'wall_confidence': 0.82,
            'flow_imbalance_score': 0.25,
            'spot_to_zero_gamma_pct': 0.03,
            'dealer_position': 'long_gamma',
        },
        'data_quality_feed': {
            'data': {
                'overall_quality': 0.94,
                'slo_status': {
                    'all_ok': True,
                    'freshness_ok': True,
                },
                'quality_buckets': {
                    'VOL_SURFACE': {'quality_score': 0.91, 'stale': False, 'source_available': True},
                    'DEALER_FLOW': {'quality_score': 0.9, 'stale': False, 'source_available': True},
                },
            }
        },
    }


def _make_orchestrator(conditions, tmp_path=None):
    StrategyOrchestrator = _get_strategy_orchestrator_class()
    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator.lean_mode = False
    orchestrator._entry_filter_gate = EntryFilters(_MockConfigManager())
    orchestrator._metrics_orchestrator = _StubMetricsOrchestrator(conditions)
    orchestrator.risk_manager = _ApprovedRiskManager()
    orchestrator._dispatch_approved_signal = MagicMock()
    # Bypass the time-of-day / calendar session gate so tests run at any time.
    orchestrator._passes_session_window_gate = lambda _sig: (True, "")
    # Run dispatch synchronously so assertions don't race the ThreadPoolExecutor.
    orchestrator._dispatch_executor = SimpleNamespace(submit=lambda fn, *args: fn(*args))
    # Redirect decision audit log to an isolated temp directory so tests do
    # not pollute the production logs/decisions/ JSONL files.
    if tmp_path is not None:
        orchestrator._signal_drop_audit_dir = str(tmp_path)
    return orchestrator


def _read_today_audit_records(orchestrator):
    file_path = Path(
        orchestrator._resolve_signal_audit_file_path(datetime.now(UTC))
    )
    if not file_path.exists():
        return []

    records = []
    with file_path.open(encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def test_d31_dispatches_signal_when_entry_trust_gate_passes():
    orchestrator = _make_orchestrator(_healthy_conditions())
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once_with(signal)


def test_d31_calls_overlay_gate_only_for_baseline_full_pmr_candidate(monkeypatch):
    monkeypatch.setenv('SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT', 'true')
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator.active_strategies = {
        'base-1': object(),
        'base-2': object(),
    }
    orchestrator.max_concurrent_strategies = 2
    orchestrator.risk_manager = _ApprovedRiskManager()

    signal = {
        'strategy_id': 'D34_PivotMR',
        'strategy_type': 'PivotMeanReversion',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'daily_risk_used_fraction': 0.25,
        'projected_post_trade_greeks': {
            'delta': 0.05,
            'gamma': 0.01,
            'vega': 0.05,
            'theta': 0.05,
        },
        'execution_quality': {
            'bid_ask_width_ok': True,
            'expected_slippage_bps': 12.0,
        },
        'event_clock_state': {'state': 'clear'},
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator.risk_manager.validate_overlay_slot.assert_called_once()
    overlay_request = orchestrator.risk_manager.validate_overlay_slot.call_args.args[0]
    assert overlay_request.metadata['overlay_slot_requested'] is True
    assert overlay_request.metadata['active_strategy_count'] == 2
    assert overlay_request.metadata['strategy_type'] == 'pivot_mean_reversion'
    assert overlay_request.metadata['strategy_type_normalized'] == 'pivot_mean_reversion'
    assert overlay_request.metadata['event_window_blocked'] is False
    orchestrator.risk_manager.validate_signal.assert_called_once()
    orchestrator._dispatch_approved_signal.assert_called_once_with(signal)


def test_d31_skips_overlay_gate_before_baseline_cap_even_when_flag_enabled(monkeypatch):
    monkeypatch.setenv('SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT', 'true')
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator.active_strategies = {'base-1': object()}
    orchestrator.max_concurrent_strategies = 2
    orchestrator.risk_manager = _ApprovedRiskManager()

    signal = {
        'strategy_id': 'D34_PivotMR',
        'strategy_type': 'PivotMeanReversion',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator.risk_manager.validate_overlay_slot.assert_not_called()
    orchestrator.risk_manager.validate_signal.assert_called_once()
    orchestrator._dispatch_approved_signal.assert_called_once_with(signal)


def test_d31_blocks_signal_when_overlay_gate_rejects_candidate(monkeypatch):
    monkeypatch.setenv('SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT', 'true')
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator.active_strategies = {
        'base-1': object(),
        'base-2': object(),
    }
    orchestrator.max_concurrent_strategies = 2
    orchestrator.risk_manager = _ApprovedRiskManager()
    orchestrator.risk_manager.validate_overlay_slot.return_value = SimpleNamespace(
        allow=False,
        reason_code='daily_risk_limit',
        computed_values={},
    )

    signal = {
        'strategy_id': 'D34_PivotMR',
        'strategy_type': 'pivot_mean_reversion',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator.risk_manager.validate_overlay_slot.assert_called_once()
    orchestrator.risk_manager.validate_signal.assert_not_called()
    orchestrator._dispatch_approved_signal.assert_not_called()
    assert orchestrator._last_drop_event is not None
    assert orchestrator._last_drop_event['stage'] == 'pre_risk'
    assert orchestrator._last_drop_event['reason'] == 'overlay_gate:daily_risk_limit'


def test_d31_blocks_signal_when_data_quality_trust_gate_fails():
    conditions = _healthy_conditions()
    conditions['data_quality_feed']['data']['slo_status']['all_ok'] = False
    conditions['data_quality_feed']['data']['slo_status']['freshness_ok'] = False
    orchestrator = _make_orchestrator(conditions)
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()


def test_d31_blocks_signal_when_qqq_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['qqq_change_pct'] = -0.25
    orchestrator = _make_orchestrator(conditions)
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once()


def test_d31_blocks_signal_when_iwm_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['iwm_change_pct'] = -0.35
    orchestrator = _make_orchestrator(conditions)
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once()


def test_d31_blocks_signal_when_xlk_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['xlk_change_pct'] = -0.40
    orchestrator = _make_orchestrator(conditions)
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once()


def test_d31_blocks_signal_when_xlf_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['xlf_change_pct'] = -0.20
    orchestrator = _make_orchestrator(conditions)
    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once()


def test_d31_blocks_signal_when_strategy_not_allowlisted_for_regime():
    conditions = _healthy_conditions()
    conditions['regime'] = 'bull'
    orchestrator = _make_orchestrator(conditions)
    orchestrator._regime_policy = {
        'regimes': {
            'bull_trend': {
                'allowed_strategies': ['bull_put_credit_spread'],
                'blocked_strategies': [],
                'hard_blocks': {'no_trade': False},
            }
        }
    }
    signal = {
        'strategy_id': 'iron_condor_defined_risk',
        'strategy_type': 'iron_condor_defined_risk',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()


def test_d31_dispatches_signal_when_strategy_is_allowlisted_for_regime():
    conditions = _healthy_conditions()
    conditions['regime'] = 'bull'
    orchestrator = _make_orchestrator(conditions)
    orchestrator._regime_policy = {
        'regimes': {
            'bull_trend': {
                'allowed_strategies': ['bull_put_credit_spread'],
                'blocked_strategies': [],
                'hard_blocks': {'no_trade': False},
            }
        }
    }
    signal = {
        'strategy_id': 'bull_put_credit_spread_v2',
        'strategy_type': 'bull_put_credit_spread_v2',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once_with(signal)


def test_d31_on_strategy_signal_session_window_rejection_emits_risk_event_and_pre_risk_drop():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._passes_session_window_gate = MagicMock(return_value=(False, "zero_dte_short_cutoff"))
    orchestrator._passes_entry_trust_gate = MagicMock(return_value=(True, ""))

    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()
    assert orchestrator._last_drop_event is not None
    assert orchestrator._last_drop_event['stage'] == 'pre_risk'
    assert orchestrator._last_drop_event['reason'] == 'session_window_gate'
    orchestrator._passes_entry_trust_gate.assert_not_called()

    assert orchestrator.event_manager.emit.called
    emitted_payload = orchestrator.event_manager.emit.call_args.args[1]
    assert emitted_payload['type'] == 'session_window_gate_rejected'
    assert emitted_payload['reason'] == 'zero_dte_short_cutoff'
    assert emitted_payload['signal'] == signal


def test_d31_on_strategy_signal_entry_trust_rejection_emits_risk_alert_and_pre_risk_drop():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._passes_session_window_gate = MagicMock(return_value=(True, ""))
    orchestrator._passes_entry_trust_gate = MagicMock(return_value=(False, "market_structure_untrusted"))
    orchestrator.risk_manager = MagicMock()

    signal = {
        'strategy_id': 'bull_put_spread',
        'strategy_type': 'bull_put_spread',
        'symbol': 'SPY',
        'action': 'buy',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()
    assert orchestrator._last_drop_event is not None
    assert orchestrator._last_drop_event['stage'] == 'pre_risk'
    assert orchestrator._last_drop_event['reason'] == 'entry_trust_gate'
    orchestrator.risk_manager.validate_signal.assert_not_called()

    orchestrator.event_manager.publish.assert_called_once()
    publish_payload = orchestrator.event_manager.publish.call_args.args[1]
    assert publish_payload['reason'] == 'entry_trust_gate_rejected'
    assert publish_payload['message'] == 'market_structure_untrusted'
    assert publish_payload['signal'] == signal


def test_d31_session_window_blocks_short_premium_sell_before_first_entry(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._session_window_policy["first_entry_not_before_et"] = "09:40"
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator._passes_session_window_gate = mod.StrategyOrchestrator._passes_session_window_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    eastern = mod._d31_now_et().tzinfo
    monkeypatch.setattr(
        mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 14, 9, 33, tzinfo=eastern),
    )

    allowed, reason = orchestrator._passes_session_window_gate(
        {
            'strategy_id': 'iron_condor',
            'strategy_type': 'iron_condor',
            'symbol': 'SPY',
            'action': 'sell',
            'quantity': 1,
            'price': 2.15,
            'confidence': 0.8,
        }
    )

    assert allowed is False
    assert reason == 'session_window:first_entry_embargo'


def test_d31_session_window_does_not_treat_generic_sell_as_opening_trade(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._session_window_policy["first_entry_not_before_et"] = "09:40"
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator._passes_session_window_gate = mod.StrategyOrchestrator._passes_session_window_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    eastern = mod._d31_now_et().tzinfo
    monkeypatch.setattr(
        mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 14, 9, 33, tzinfo=eastern),
    )

    allowed, reason = orchestrator._passes_session_window_gate(
        {
            'strategy_id': 'MACrossover',
            'strategy_type': 'MACrossover',
            'symbol': 'SPY',
            'action': 'sell',
            'quantity': 1,
            'price': 603.0,
            'confidence': 0.8,
        }
    )

    assert allowed is True
    assert reason == ''


def test_d31_session_window_allows_explicit_close_signal_outside_primary_window(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator._passes_session_window_gate = mod.StrategyOrchestrator._passes_session_window_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    eastern = mod._d31_now_et().tzinfo
    monkeypatch.setattr(
        mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 14, 18, 14, tzinfo=eastern),
    )

    allowed, reason = orchestrator._passes_session_window_gate(
        {
            'strategy_id': 'iron_condor',
            'strategy_type': 'iron_condor',
            'symbol': 'SPY260618P00699000',
            'action': 'close',
            'side': 'buy',
            'quantity': 1,
        }
    )

    assert allowed is True
    assert reason == ''


def test_d31_session_window_rejects_zero_dte_butterfly_after_no_new_risk_cutoff(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator._passes_session_window_gate = mod.StrategyOrchestrator._passes_session_window_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    eastern = mod._d31_now_et().tzinfo
    monkeypatch.setattr(
        mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 14, 15, 25, tzinfo=eastern),
    )

    allowed, reason = orchestrator._passes_session_window_gate(
        {
            'strategy_id': 'butterfly',
            'strategy_type': 'butterfly',
            'symbol': 'SPY',
            'action': 'buy',
            'quantity': 1,
            'price': 0.35,
            'confidence': 0.8,
            'metadata': {
                'expiration_date': '2026-05-14',
            },
        }
    )

    assert allowed is False
    assert reason == 'session_window:zero_dte_no_new_risk_cutoff'


def test_d31_entry_trust_gate_skips_explicit_close_signal() -> None:
    orchestrator = _make_orchestrator(_healthy_conditions())

    allowed, reason = orchestrator._passes_entry_trust_gate(
        {
            'strategy_id': 'iron_condor',
            'strategy_type': 'iron_condor',
            'symbol': 'SPY260618P00699000',
            'action': 'close',
            'side': 'buy',
            'quantity': 1,
        }
    )

    assert allowed is True
    assert reason == ''


def test_d31_on_strategy_signal_dispatches_explicit_close_signal_outside_primary_window(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    orchestrator._passes_session_window_gate = mod.StrategyOrchestrator._passes_session_window_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    orchestrator._passes_entry_trust_gate = mod.StrategyOrchestrator._passes_entry_trust_gate.__get__(
        orchestrator,
        mod.StrategyOrchestrator,
    )
    eastern = mod._d31_now_et().tzinfo
    monkeypatch.setattr(
        mod,
        "_d31_now_et",
        lambda: datetime(2026, 5, 14, 18, 14, tzinfo=eastern),
    )

    signal = {
        'strategy_id': 'iron_condor',
        'strategy_type': 'iron_condor',
        'symbol': 'SPY260618P00699000',
        'action': 'close',
        'side': 'buy',
        'quantity': 1,
        'price': 4.21,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_called_once_with(signal)


def test_d31_low_confidence_l09_falls_back_to_contract_bull_classifier(monkeypatch):
    orchestrator = _make_orchestrator(_healthy_conditions())
    d31_mod = importlib.import_module("Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator")
    l09_mod = importlib.import_module("Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine")

    monkeypatch.setattr(orchestrator, "_recover_cache_if_cold", lambda: None)

    spy_ticks = []
    for idx in range(60):
        close = 700.0 + idx
        spy_ticks.append(
            {
                "close": close,
                "high": close + 1.0,
                "low": close - 1.0,
            }
        )

    vix_ticks = []
    for idx in range(60):
        close = 24.0 - (idx * 0.1)
        vix_ticks.append({"close": close})

    orchestrator.market_data_cache = {
        "SPY": spy_ticks,
        "VIX": vix_ticks,
        "VIX9D": [{"close": 17.0}],
        "VXV": [{"close": 20.0}],
        "event_clock_state": {"state": "clear"},
    }

    class _LowConfidenceL09:
        def get_current_regime(self, _conditions):
            return SimpleNamespace(
                regime=l09_mod.MarketRegime.SIDEWAYS_RANGE,
                confidence=0.60,
            )

    orchestrator._l09_engine = _LowConfidenceL09()

    result = orchestrator._classify_market_regime_unified(
        vix_level=18.0,
        vix_percentile=50.0,
        trend_strength=0.0,
    )

    assert result == d31_mod.MarketRegime.BULL_LOW_VOL


def test_d31_duplicate_open_position_is_silent_and_does_not_block_dispatch_state():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._get_duplicate_open_position_source = MagicMock(return_value='active_positions')
    orchestrator.logger.warning = MagicMock()

    signal = {
        'strategy_id': 'iron_condor',
        'strategy_type': 'iron_condor',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))
    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    assert orchestrator.logger.warning.call_count == 0
    assert orchestrator._signal_drop_reasons['pre_dispatch:duplicate_open_position'] == 2
    assert orchestrator.get_dispatch_state()['state'] == 'IDLE'


def test_d31_duplicate_open_position_remains_silent_after_cooldown():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._get_duplicate_open_position_source = MagicMock(return_value='active_positions')
    orchestrator.logger.warning = MagicMock()
    orchestrator._duplicate_entry_warning_interval_s = 60.0

    signal = {
        'strategy_id': 'iron_condor',
        'strategy_type': 'iron_condor',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))
    orchestrator._duplicate_entry_warning_last_monotonic[('SPY', 'iron_condor')] -= 61.0
    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    assert orchestrator.logger.warning.call_count == 0
    assert orchestrator.get_dispatch_state()['state'] == 'IDLE'


def test_d31_duplicate_open_position_remains_silent_after_block_clears():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._get_duplicate_open_position_source = MagicMock(
        side_effect=['active_positions', None, 'active_positions']
    )
    orchestrator._reserve_pending_entry = MagicMock(return_value=True)
    orchestrator._dispatch_approved_signal = MagicMock()
    orchestrator.logger.warning = MagicMock()
    orchestrator._duplicate_entry_warning_interval_s = 600.0

    signal = {
        'strategy_id': 'iron_condor',
        'strategy_type': 'iron_condor',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))
    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))
    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    assert orchestrator.logger.warning.call_count == 0
    assert orchestrator._dispatch_approved_signal.call_count == 1
    assert orchestrator.get_dispatch_state()['state'] == 'IDLE'


def test_d31_manual_close_dashboard_embargo_blocks_immediate_reentry():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._get_duplicate_open_position_source = MagicMock(return_value=None)
    orchestrator._reserve_pending_entry = MagicMock(return_value=True)
    orchestrator.logger.warning = MagicMock()

    orchestrator._on_position_updated(
        SimpleNamespace(
            data={
                'symbol': 'SPY260526C00750000',
                'strategy_id': 'butterfly',
                'status': 'CLOSED',
                'reason': 'manual_close_dashboard',
            }
        )
    )

    signal = {
        'strategy_id': 'butterfly',
        'strategy_type': 'butterfly',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()
    orchestrator._get_duplicate_open_position_source.assert_not_called()
    orchestrator._reserve_pending_entry.assert_not_called()
    assert orchestrator._signal_drop_reasons['pre_dispatch:manual_close_reentry_embargo'] == 1
    orchestrator.logger.warning.assert_called_once()
    assert 'manual close reentry embargo active' in orchestrator.logger.warning.call_args[0][0]


def test_d31_manual_close_request_embargo_blocks_immediate_reentry():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._get_duplicate_open_position_source = MagicMock(return_value=None)
    orchestrator._reserve_pending_entry = MagicMock(return_value=True)
    orchestrator.logger.warning = MagicMock()

    orchestrator._on_position_updated(
        SimpleNamespace(
            data={
                'symbol': 'SPY260526C00750000',
                'strategy_id': 'butterfly',
                'status': 'CLOSE_REQUESTED',
                'reason': 'manual_close_dashboard',
            }
        )
    )

    signal = {
        'strategy_id': 'butterfly',
        'strategy_type': 'butterfly',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    orchestrator._dispatch_approved_signal.assert_not_called()
    orchestrator._get_duplicate_open_position_source.assert_not_called()
    orchestrator._reserve_pending_entry.assert_not_called()
    assert orchestrator._signal_drop_reasons['pre_dispatch:manual_close_reentry_embargo'] == 1
    orchestrator.logger.warning.assert_called_once()
    assert 'manual close reentry embargo active' in orchestrator.logger.warning.call_args[0][0]


def test_d31_pre_dispatch_duplicate_pending_source_persisted_to_decision_audit(tmp_path):
    orchestrator = _make_orchestrator(_healthy_conditions(), tmp_path=tmp_path)

    signal = {
        'strategy_id': 'iron_condor',
        'strategy_type': 'iron_condor',
        'symbol': 'SPY',
        'action': 'sell',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
    }

    assert orchestrator._reserve_pending_entry('SPY', 'iron_condor') is True

    orchestrator._on_strategy_signal(SimpleNamespace(data=signal))

    records = _read_today_audit_records(orchestrator)
    dropped = [
        record for record in records
        if record.get('event') == 'signal_dropped'
        and record.get('stage') == 'pre_dispatch'
        and record.get('reason') == 'duplicate_open_position'
    ]
    rejected = [record for record in records if record.get('event') == 'dispatch_rejected']

    assert dropped
    assert rejected
    assert dropped[-1]['detail'] == (
        'symbol=SPY;strategy=iron_condor;duplicate_source=pending_entry_reservation'
    )
    assert rejected[-1]['detail'] == (
        'symbol=SPY;strategy=iron_condor;duplicate_source=pending_entry_reservation'
    )


def test_d31_duplicate_source_reports_live_active_positions():
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._live_engine = SimpleNamespace(
        get_active_positions_snapshot=lambda: {
            'SPY': {
                'symbol': 'SPY',
                'strategy': 'iron_condor',
                'quantity': -1,
            }
        }
    )

    assert (
        orchestrator._get_duplicate_open_position_source('SPY', 'iron_condor', 'sell')
        == 'active_positions'
    )


def test_d31_duplicate_source_prefers_active_paper_selector_over_raw_open_rows():
    class _ManifestAwarePaperDB:
        def __init__(self) -> None:
            self.active_calls = 0
            self.resume_calls = 0
            self.open_calls = 0

        def has_active_paper_session_marker(self):
            return True

        def get_active_paper_open_positions(self):
            self.active_calls += 1
            return [
                {
                    'symbol': 'SPY260526C00750000',
                    'strategy': 'iron_condor',
                    'quantity': -1,
                    '_paper_open_origin': 'carryover',
                }
            ]

        def get_resume_eligible_open_positions(self):
            self.resume_calls += 1
            return []

        def get_open_positions(self):
            self.open_calls += 1
            return [
                {
                    'symbol': 'SPY',
                    'strategy': 'iron_condor',
                    'quantity': -1,
                }
            ]

    session_db = _ManifestAwarePaperDB()
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._live_engine = SimpleNamespace(
        get_active_positions_snapshot=lambda: {},
        _session_db=session_db,
    )

    assert (
        orchestrator._get_duplicate_open_position_source('SPY', 'iron_condor', 'sell')
        == 'persisted_carryover'
    )
    assert session_db.active_calls == 1
    assert session_db.resume_calls == 0
    assert session_db.open_calls == 0


def test_d31_duplicate_source_uses_resume_selector_without_active_session_marker():
    class _ResumeOnlyPaperDB:
        def __init__(self) -> None:
            self.active_calls = 0
            self.resume_calls = 0
            self.open_calls = 0

        def has_active_paper_session_marker(self):
            return False

        def get_active_paper_open_positions(self):
            self.active_calls += 1
            return [
                {
                    'symbol': 'SPY',
                    'strategy': 'iron_condor',
                    'quantity': -1,
                }
            ]

        def get_resume_eligible_open_positions(self):
            self.resume_calls += 1
            return [
                {
                    'symbol': 'SPY260526C00750000',
                    'strategy': 'iron_condor',
                    'quantity': -1,
                }
            ]

        def get_open_positions(self):
            self.open_calls += 1
            return [
                {
                    'symbol': 'SPY',
                    'strategy': 'iron_condor',
                    'quantity': -1,
                }
            ]

    session_db = _ResumeOnlyPaperDB()
    orchestrator = _make_orchestrator(_healthy_conditions())
    orchestrator._live_engine = SimpleNamespace(
        get_active_positions_snapshot=lambda: {},
        _session_db=session_db,
    )

    assert (
        orchestrator._get_duplicate_open_position_source('SPY', 'iron_condor', 'sell')
        == 'persisted_carryover'
    )
    assert session_db.active_calls == 0
    assert session_db.resume_calls == 1
    assert session_db.open_calls == 0
