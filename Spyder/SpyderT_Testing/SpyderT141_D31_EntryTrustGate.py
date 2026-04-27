#!/usr/bin/env python3
"""Focused tests for D31 entry trust gating via F09 market-structure controls."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator import StrategyOrchestrator
from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters


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
                'required_buckets': ['VOL_SURFACE', 'DEALER_FLOW', 'LEAD_LAG'],
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
                'fast_regime_lead_lag_ms': 150.0,
                'fast_regime_impulse_score': 0.7,
                'min_confirm_confidence': 0.55,
            },
        }
        return values.get(key, default)


class _StubEventManager:
    def __init__(self):
        self.handlers = {}
        self.publish = MagicMock()

    def subscribe(self, event_type, handler):
        self.handlers.setdefault(event_type, []).append(handler)

    def emit(self, *args, **kwargs):
        return None


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
        'lead_lag_ms': 220.0,
        'es_impulse_score': 0.75,
        'confirm_direction': 'up',
        'confirm_confidence': 0.72,
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
                    'LEAD_LAG': {'quality_score': 0.89, 'stale': False, 'source_available': True},
                },
            }
        },
    }


def _make_orchestrator(conditions):
    orchestrator = StrategyOrchestrator(event_manager=_StubEventManager())
    orchestrator._entry_filter_gate = EntryFilters(_MockConfigManager())
    orchestrator._metrics_orchestrator = _StubMetricsOrchestrator(conditions)
    orchestrator.risk_manager = _ApprovedRiskManager()
    orchestrator._dispatch_approved_signal = MagicMock()
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