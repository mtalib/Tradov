#!/usr/bin/env python3
"""Focused tests for D31 entry trust gating via F09 market-structure controls."""

import importlib
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
    def validate_signal(self, request):
        return SimpleNamespace(approved=True)


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