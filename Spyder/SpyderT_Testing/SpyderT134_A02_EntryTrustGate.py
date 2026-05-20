#!/usr/bin/env python3
"""Focused tests for A02 direct signal trust gating via F09 controls."""

from Spyder.SpyderA_Core.SpyderA02_TradingEngine import (
    TradingEngine,
    StrategyInfo,
    StrategyState,
    EngineState,
)
from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters


class _StubEventManager:
    def emit(self, *args, **kwargs):
        return None


class _StubMetricsOrchestrator:
    def __init__(self, conditions):
        self._conditions = conditions

    def get_current_market_conditions(self):
        return self._conditions


class _MockConfigManager:
    def get_config(self, key, default=None):
        values = {
            'entry_filters': {},
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

    def is_feature_enabled(self, key):
        if key == 'adaptive_entry_filters':
            return False
        return False

    def get(self, key, default=None):
        return self.get_config(key, default)


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


def _make_engine(conditions):
    engine = TradingEngine(config={}, spyder_client=None, event_manager=_StubEventManager())
    engine.lean_mode = False
    engine.state = EngineState.RUNNING
    engine.strategies['bull_put_spread'] = StrategyInfo(
        strategy_id='bull_put_spread',
        name='Bull Put Spread',
        class_instance=object(),
        state=StrategyState.ACTIVE,
    )
    engine.has_risk_manager = False
    engine._entry_filter_gate = EntryFilters(_MockConfigManager())
    engine._metrics_orchestrator = _StubMetricsOrchestrator(conditions)
    return engine


def test_a02_process_signal_passes_when_trust_gate_is_healthy():
    engine = _make_engine(_healthy_conditions())
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_process_signal_blocks_when_data_quality_trust_gate_fails():
    conditions = _healthy_conditions()
    conditions['data_quality_feed']['data']['slo_status']['all_ok'] = False
    conditions['data_quality_feed']['data']['slo_status']['freshness_ok'] = False
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is False
    assert engine.order_queue.qsize() == 0


def test_a02_process_signal_blocks_when_qqq_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['qqq_change_pct'] = -0.25
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_process_signal_blocks_when_iwm_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['iwm_change_pct'] = -0.35
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_process_signal_blocks_when_xlk_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['xlk_change_pct'] = -0.40
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_process_signal_blocks_when_xlf_confirmation_fails():
    conditions = _healthy_conditions()
    conditions['spy_change_pct'] = 0.70
    conditions['xlf_change_pct'] = -0.20
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_process_signal_blocks_when_strategy_not_allowlisted_for_regime():
    conditions = _healthy_conditions()
    conditions['regime'] = 'bull'
    engine = _make_engine(conditions)
    engine._regime_policy = {
        'regimes': {
            'bull_trend': {
                'allowed_strategies': ['bull_put_credit_spread'],
                'blocked_strategies': [],
                'hard_blocks': {'no_trade': False},
            }
        }
    }
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'iron_condor_defined_risk',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is False
    assert engine.order_queue.qsize() == 0


def test_a02_process_signal_passes_when_strategy_is_allowlisted_for_regime():
    conditions = _healthy_conditions()
    conditions['regime'] = 'bull'
    engine = _make_engine(conditions)
    engine._regime_policy = {
        'regimes': {
            'bull_trend': {
                'allowed_strategies': ['bull_put_credit_spread'],
                'blocked_strategies': [],
                'hard_blocks': {'no_trade': False},
            }
        }
    }
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.15,
        'confidence': 0.8,
        'strategy_type': 'bull_put_credit_spread_v2',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is True
    assert engine.order_queue.qsize() == 1


def test_a02_decision_pipeline_runs_in_strict_order(monkeypatch):
    engine = _make_engine(_healthy_conditions())
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.10,
        'strategy_type': 'bull_put_spread',
    }

    calls = []

    monkeypatch.setattr(engine, '_passes_data_gate', lambda *a, **k: (calls.append('data') or (True, '')))
    monkeypatch.setattr(engine, '_passes_regime_gate', lambda *a, **k: (calls.append('regime') or (True, '')))
    monkeypatch.setattr(engine, '_passes_strategy_gate', lambda *a, **k: (calls.append('strategy') or (True, '')))
    monkeypatch.setattr(engine, '_passes_risk_gate', lambda *a, **k: (calls.append('risk') or (True, '')))
    monkeypatch.setattr(engine, '_queue_execution_from_signal', lambda *a, **k: (calls.append('execution') or (True, '')))

    ok, reason = engine._run_decision_flow_pipeline('bull_put_spread', signal)

    assert ok is True
    assert reason == ''
    assert calls == ['data', 'regime', 'strategy', 'risk', 'execution']


def test_a02_decision_pipeline_short_circuits_on_data_gate_failure(monkeypatch):
    engine = _make_engine(_healthy_conditions())
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.10,
        'strategy_type': 'bull_put_spread',
    }

    calls = []

    monkeypatch.setattr(engine, '_passes_data_gate', lambda *a, **k: (calls.append('data') or (False, 'stale_quote')))
    monkeypatch.setattr(engine, '_passes_regime_gate', lambda *a, **k: (calls.append('regime') or (True, '')))

    ok, reason = engine._run_decision_flow_pipeline('bull_put_spread', signal)

    assert ok is False
    assert 'data_gate:stale_quote' in reason
    assert calls == ['data']


def test_a02_decision_pipeline_halts_on_crisis_regime():
    conditions = _healthy_conditions()
    conditions['regime'] = 'crisis'
    engine = _make_engine(conditions)
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'price': 2.10,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is False
    assert engine.order_queue.qsize() == 0


def test_a02_decision_pipeline_requires_limit_price_for_execution():
    engine = _make_engine(_healthy_conditions())
    signal = {
        'symbol': 'SPY',
        'action': 'BUY',
        'quantity': 1,
        'strategy_type': 'bull_put_spread',
    }

    result = engine.process_signal('bull_put_spread', signal)

    assert result is False
    assert engine.order_queue.qsize() == 0
