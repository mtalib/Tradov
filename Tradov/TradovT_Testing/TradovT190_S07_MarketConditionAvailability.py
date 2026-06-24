from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest


def test_market_conditions_start_unavailable_not_plausibly_neutral():
    pytest.importorskip("PySide6")

    from Tradov.TradovS_Signals.TradovS07_CustomMetricsOrchestrator import (
        CustomMetricsOrchestrator,
    )

    orchestrator = CustomMetricsOrchestrator()

    conditions = orchestrator.get_current_market_conditions()

    assert conditions["market_conditions_available"] is False
    assert math.isnan(conditions["dix_score"])
    assert math.isnan(conditions["swan_score"])
    assert math.isnan(conditions["skew_level"])
    assert conditions["metric_health"]["DIX"]["available"] is False


def test_market_conditions_available_when_required_metrics_are_fresh():
    pytest.importorskip("PySide6")

    from Tradov.TradovS_Signals.TradovS07_CustomMetricsOrchestrator import (
        CustomMetricsOrchestrator,
        MetricQuality,
    )

    orchestrator = CustomMetricsOrchestrator()
    now = datetime.now(UTC)
    with orchestrator._metrics_lock:
        orchestrator.current_metrics["DIX"] = 44.0
        orchestrator.current_metrics["SWAN"] = 1.2
        orchestrator.current_metrics["SKEW"] = 121.0
        for name in ("DIX", "SWAN", "SKEW"):
            orchestrator.metric_quality[name] = MetricQuality(
                metric_name=name,
                quality_score=1.0,
                data_points=10,
                last_successful_update=now,
                source_available=True,
            )

    conditions = orchestrator.get_current_market_conditions()

    assert conditions["market_conditions_available"] is True
    assert conditions["dix_score"] == 44.0
    assert conditions["metric_health"]["SWAN"]["fresh"] is True
