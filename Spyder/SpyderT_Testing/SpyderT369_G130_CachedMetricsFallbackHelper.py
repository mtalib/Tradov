#!/usr/bin/env python3
"""Focused tests for G130 cached metrics fallback helper."""

from __future__ import annotations

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG130_CachedMetricsFallbackHelper import (
    build_cached_metrics_fallback_payload_from_sources,
)


def test_build_cached_metrics_fallback_payload_from_sources_merges_loaded_sources() -> None:
    result = build_cached_metrics_fallback_payload_from_sources(
        persisted_metrics={"GEX": {"value": 1.25, "status": "cached"}},
        pca_iv_snapshot=SimpleNamespace(
            signal_value=2.5,
            change=0.1,
            status="live",
            details={"source": "pca"},
        ),
        dix_payload={"dix_percentage": 47.1, "sentiment": "bullish"},
        swan_payload={"results": [{"score": 8.5, "status": "watch"}]},
        nymo_payload={"ema_fast": 14.2, "ema_slow": 10.0},
        iv_history_payload=[
            {"iv": 0.20},
            {"iv": 0.24},
            {"iv": 0.28},
            {"iv": 0.32},
            {"iv": 0.36},
        ],
    )

    assert result == {
        "GEX": {"value": 1.25, "status": "cached"},
        "PCA-IV": {
            "value": 2.5,
            "change": 0.1,
            "status": "live",
            "details": {"source": "pca"},
        },
        "DIX": {"value": 47.1, "status": "bullish"},
        "SWAN": {"value": 8.5, "status": "watch"},
        "NYMO": {"value": 4.2},
        "ATM_IV": {"value": 0.36},
        "IVR": {"value": 100.0},
    }


def test_build_cached_metrics_fallback_payload_from_sources_ignores_invalid_sources() -> None:
    result = build_cached_metrics_fallback_payload_from_sources(
        persisted_metrics={"GEX": {"value": 1.25, "status": "cached"}},
        pca_iv_snapshot=SimpleNamespace(
            signal_value=float("nan"),
            change=0.1,
            status="live",
            details={"source": "pca"},
        ),
        dix_payload={"dix_percentage": "bad", "sentiment": "bullish"},
        swan_payload={"summary": {"average_score": "bad"}},
        nymo_payload={"ema_fast": "bad", "ema_slow": 10.0},
        iv_history_payload=[{"iv": "bad"}],
    )

    assert result == {"GEX": {"value": 1.25, "status": "cached"}}


def test_build_cached_metrics_fallback_payload_from_sources_uses_swan_summary_and_flat_ivr_rule() -> None:
    result = build_cached_metrics_fallback_payload_from_sources(
        persisted_metrics=None,
        pca_iv_snapshot=None,
        dix_payload=None,
        swan_payload={"summary": {"average_score": 7.5}},
        nymo_payload=None,
        iv_history_payload=[
            {"iv": 0.25},
            {"iv": 0.25},
            {"iv": 0.25},
            {"iv": 0.25},
            {"iv": 0.25},
        ],
    )

    assert result == {
        "SWAN": {"value": 7.5, "status": None},
        "ATM_IV": {"value": 0.25},
        "IVR": {"value": 100.0},
    }