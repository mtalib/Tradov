#!/usr/bin/env python3
"""Focused tests for F09 decision-path market-structure and trust controls."""

from datetime import datetime

from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters, FilterResult, FilterType


class _MockConfigManager:
    def get_config(self, key, default=None):
        if key == 'autonomous_readiness.data_quality':
            return {
                'enforce_hard_slo': True,
                'min_bucket_quality': 0.60,
                'required_buckets': ['VOL_SURFACE', 'DEALER_FLOW', 'LEAD_LAG'],
            }
        if key == 'autonomous_readiness.market_structure':
            return {
                'min_surface_confidence': 0.65,
                'max_surface_age_ms': 180000,
                'min_term_slope_0_7': 0.0,
                'min_wall_confidence': 0.55,
                'zero_gamma_buffer_pct': 0.50,
                'fast_regime_lead_lag_ms': 3.0,
                'fast_regime_impulse_score': 0.40,
                'min_confirm_confidence': 0.55,
            }
        return default if default is not None else {}

    def is_feature_enabled(self, _key):
        return False


def _base_params():
    return {
        'current_price': 585.0,
        'volume': 1000,
        'rsi': 50.0,
        'implied_volatility': 0.22,
        'current_volatility': 0.20,
        'trend_strength': 0.40,
        'trend_direction': 'up',
        'volume_ratio': 1.2,
        'position_size_pct': 0.02,
        'portfolio_delta': 20.0,
        'iv_percentile': 55.0,
        'iv_skew': 0.04,
        'strategy_type': 'bull_put_spread',
        'position_type': 'long',
        'current_time': datetime(2026, 4, 27, 11, 0, 0),
        'market_conditions': {
            'surface_confidence': 0.88,
            'surface_age_ms': 1200,
            'term_slope_0_7': 1.50,
            'rr_25d': 0.012,
            'fly_25d': 0.008,
            'wall_confidence': 0.82,
            'flow_imbalance': 0.20,
            'dealer_flow': {
                'dealer_position': 'long_gamma',
                'spot_to_zero_gamma_pct': 0.90,
                'wall_confidence': 0.82,
                'flow_imbalance_score': 0.20,
            },
            'lead_lag_ms': 4.25,
            'es_impulse_score': 0.62,
            'confirm_direction': 'up',
            'confirm_confidence': 0.72,
            'data_quality_feed': {
                'feed': 'data_quality',
                'data': {
                    'overall_quality': 0.91,
                    'slo_status': {
                        'overall_quality_ok': True,
                        'freshness_ok': True,
                        'all_ok': True,
                    },
                    'quality_buckets': {
                        'VOL_SURFACE': {
                            'quality_score': 0.90,
                            'stale': False,
                            'source_available': True,
                        },
                        'DEALER_FLOW': {
                            'quality_score': 0.88,
                            'stale': False,
                            'source_available': True,
                        },
                        'LEAD_LAG': {
                            'quality_score': 0.87,
                            'stale': False,
                            'source_available': True,
                        },
                    },
                },
            },
        },
    }


def test_f09_passes_when_market_structure_controls_are_healthy():
    ef = EntryFilters(_MockConfigManager())

    result = ef.assess_entry(_base_params())

    assert result.overall_result == FilterResult.PASS
    assert not result.get_failed_filters()


def test_f09_data_quality_slo_failure_is_hard_block():
    ef = EntryFilters(_MockConfigManager())
    params = _base_params()
    params['market_conditions']['data_quality_feed']['data']['slo_status']['all_ok'] = False
    params['market_conditions']['data_quality_feed']['data']['slo_status']['freshness_ok'] = False

    result = ef.assess_entry(params)

    assert result.overall_result == FilterResult.FAIL
    failures = [c for c in result.checks if c.filter_type == FilterType.DATA_QUALITY]
    assert len(failures) == 1
    assert failures[0].result == FilterResult.FAIL


def test_f09_vol_surface_stale_blocks_entry():
    ef = EntryFilters(_MockConfigManager())
    params = _base_params()
    params['market_conditions']['surface_age_ms'] = 250000

    result = ef.assess_entry(params)

    failures = [c for c in result.checks if c.filter_type == FilterType.VOL_SURFACE]
    assert len(failures) == 1
    assert failures[0].result == FilterResult.FAIL
    assert result.overall_result == FilterResult.FAIL


def test_f09_dealer_short_gamma_near_flip_blocks_entry():
    ef = EntryFilters(_MockConfigManager())
    params = _base_params()
    params['market_conditions']['dealer_flow']['dealer_position'] = 'short_gamma'
    params['market_conditions']['dealer_flow']['spot_to_zero_gamma_pct'] = 0.20

    result = ef.assess_entry(params)

    failures = [c for c in result.checks if c.filter_type == FilterType.DEALER_FLOW]
    assert len(failures) == 1
    assert failures[0].result == FilterResult.FAIL
    assert result.overall_result == FilterResult.FAIL


def test_f09_fast_tape_direction_mismatch_blocks_entry():
    ef = EntryFilters(_MockConfigManager())
    params = _base_params()
    params['market_conditions']['confirm_direction'] = 'down'

    result = ef.assess_entry(params)

    failures = [c for c in result.checks if c.filter_type == FilterType.LEAD_LAG_CONFIRMATION]
    assert len(failures) == 1
    assert failures[0].result == FilterResult.FAIL
    assert result.overall_result == FilterResult.FAIL