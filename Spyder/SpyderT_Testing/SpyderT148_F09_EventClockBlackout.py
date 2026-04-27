#!/usr/bin/env python3
"""Focused tests for F09 event-clock blackout behavior."""

from datetime import datetime

from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters, FilterResult, FilterType


class _MockConfigManager:
    def get_config(self, key, default=None):
        if key == "autonomous_readiness.event_clock":
            return {
                "enforce_blackout": True,
                "allowlist_strategies": ["D03"],
            }
        return default if default is not None else {}

    def is_feature_enabled(self, _key):
        return False


def test_time_filters_fail_during_event_clock_blackout():
    ef = EntryFilters(_MockConfigManager())

    checks = ef._check_time_filters(
        {
            "current_time": datetime(2026, 4, 27, 10, 0, 0),
            "event_clock_state": {
                "state": "pre",
                "event_type": "CPI",
                "allowed_strategies": [],
            },
            "strategy_id": "D99",
        }
    )

    econ_checks = [c for c in checks if c.filter_type == FilterType.ECONOMIC_EVENTS]
    assert len(econ_checks) == 1
    assert econ_checks[0].result == FilterResult.FAIL


def test_time_filters_warning_for_allowlisted_strategy():
    ef = EntryFilters(_MockConfigManager())

    checks = ef._check_time_filters(
        {
            "current_time": datetime(2026, 4, 27, 10, 0, 0),
            "event_clock_state": {
                "state": "post",
                "event_type": "FOMC",
                "allowed_strategies": ["D03"],
            },
            "strategy_id": "D03",
        }
    )

    econ_checks = [c for c in checks if c.filter_type == FilterType.ECONOMIC_EVENTS]
    assert len(econ_checks) == 1
    assert econ_checks[0].result == FilterResult.WARNING
