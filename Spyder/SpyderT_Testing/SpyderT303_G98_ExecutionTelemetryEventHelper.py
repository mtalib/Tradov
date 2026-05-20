#!/usr/bin/env python3
"""Focused tests for G98 execution-telemetry event helper."""

from __future__ import annotations

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
from Spyder.SpyderG_GUI.SpyderG98_ExecutionTelemetryEventHelper import (
    extract_execution_telemetry_sample,
)


def test_extract_execution_telemetry_sample_accepts_event_dataclass_payload() -> None:
    telemetry = {
        "feed": "execution",
        "published_ts": "2026-04-25T14:30:00",
        "data": {
            "order_id": "ORD-G98-001",
            "slippage_bps": 7.5,
            "fill_latency_ms": 240.0,
            "partial_fill_ratio": 0.5,
            "reject_flag": False,
        },
    }
    event = Event(
        event_type=EventType.TRADE,
        source="unit_test",
        data={"execution_telemetry": telemetry},
    )

    assert extract_execution_telemetry_sample(event) == {
        "published_ts": "2026-04-25T14:30:00",
        "order_id": "ORD-G98-001",
        "slippage_bps": 7.5,
        "fill_latency_ms": 240.0,
        "partial_fill_ratio": 0.5,
        "reject_flag": False,
    }


def test_extract_execution_telemetry_sample_returns_none_for_non_execution_feed() -> None:
    assert extract_execution_telemetry_sample(
        {
            "execution_telemetry": {
                "feed": "market_data",
                "data": {"order_id": "ORD-G98-002"},
            }
        }
    ) is None