#!/usr/bin/env python3
"""Pure parsing for dashboard execution-telemetry events."""

from __future__ import annotations


def extract_execution_telemetry_sample(event: object) -> dict[str, object] | None:
    """Normalize an execution-telemetry event and return the compact sample."""
    event_payload = event
    if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
        event_payload = getattr(event, "data")  # noqa: B009

    if not isinstance(event_payload, dict):
        return None

    telemetry = event_payload.get("execution_telemetry")
    if not isinstance(telemetry, dict):
        return None
    if telemetry.get("feed") != "execution":
        return None

    data = telemetry.get("data", {})
    if not isinstance(data, dict):
        return None

    return {
        "published_ts": telemetry.get("published_ts"),
        "order_id": data.get("order_id"),
        "slippage_bps": data.get("slippage_bps"),
        "fill_latency_ms": data.get("fill_latency_ms"),
        "partial_fill_ratio": data.get("partial_fill_ratio", 0.0),
        "reject_flag": bool(data.get("reject_flag", False)),
    }
