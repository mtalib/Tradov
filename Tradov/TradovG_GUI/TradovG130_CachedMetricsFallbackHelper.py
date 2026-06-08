#!/usr/bin/env python3
"""Pure fallback payload normalization for cached Market Overview metrics."""

from __future__ import annotations

import math
from typing import Any

from Tradov.TradovG_GUI.TradovG129_MetricsPayloadMergeHelper import (
    merge_metrics_payload,
)


def _build_metric_entry(value: object, **extra: object) -> dict[str, Any] | None:
    """Return a normalized metric entry when the numeric value is usable."""
    if not isinstance(value, (int, float)):
        return None

    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None

    entry: dict[str, Any] = {"value": numeric_value}
    entry.update(extra)
    return entry


def build_cached_metrics_fallback_payload_from_sources(
    *,
    persisted_metrics: dict | None,
    pca_iv_snapshot: object | None,
    dix_payload: dict | None,
    swan_payload: dict | None,
    nymo_payload: dict | None,
    iv_history_payload: list[object] | None,
) -> dict[str, dict[str, Any]]:
    """Build the cached metrics fallback payload from already-loaded sources."""
    fallback = merge_metrics_payload({}, persisted_metrics)

    pca_entry = _build_metric_entry(
        getattr(pca_iv_snapshot, "signal_value", float("nan")),
        change=getattr(pca_iv_snapshot, "change", float("nan")),
        status=getattr(pca_iv_snapshot, "status", None),
        details=getattr(pca_iv_snapshot, "details", {}) or {},
    )
    if pca_entry is not None:
        fallback["PCA-IV"] = pca_entry

    if isinstance(dix_payload, dict):
        dix_entry = _build_metric_entry(
            dix_payload.get("dix_percentage"),
            status=dix_payload.get("sentiment"),
        )
        if dix_entry is not None:
            fallback["DIX"] = dix_entry

    if isinstance(swan_payload, dict):
        last_result: dict[str, Any] = {}
        results = swan_payload.get("results", [])
        if isinstance(results, list) and results:
            tail = results[-1]
            if isinstance(tail, dict):
                last_result = tail

        swan_value = last_result.get("score")
        if swan_value is None:
            summary = swan_payload.get("summary", {})
            if isinstance(summary, dict):
                swan_value = summary.get("average_score")

        swan_entry = _build_metric_entry(
            swan_value,
            status=last_result.get("status"),
        )
        if swan_entry is not None:
            fallback["SWAN"] = swan_entry

    if isinstance(nymo_payload, dict):
        ema_fast = nymo_payload.get("ema_fast")
        ema_slow = nymo_payload.get("ema_slow")
        if isinstance(ema_fast, (int, float)) and isinstance(ema_slow, (int, float)):
            nymo_entry = _build_metric_entry(round(float(ema_fast) - float(ema_slow), 1))
            if nymo_entry is not None:
                fallback["NYMO"] = nymo_entry

    if isinstance(iv_history_payload, list):
        iv_values = [
            float(entry.get("iv"))
            for entry in iv_history_payload
            if isinstance(entry, dict) and isinstance(entry.get("iv"), (int, float))
        ]
        if iv_values:
            current_iv = iv_values[-1]
            low_iv = min(iv_values)
            high_iv = max(iv_values)
            ivr_value = float("nan")
            if len(iv_values) >= 5:
                if math.isclose(high_iv, low_iv):
                    ivr_value = 100.0 if math.isclose(current_iv, high_iv) else float("nan")
                else:
                    ivr_value = max(
                        0.0,
                        min(100.0, ((current_iv - low_iv) / (high_iv - low_iv)) * 100.0),
                    )

            atm_iv_entry = _build_metric_entry(current_iv)
            if atm_iv_entry is not None:
                fallback["ATM_IV"] = atm_iv_entry
            ivr_entry = _build_metric_entry(ivr_value)
            if ivr_entry is not None:
                fallback["IVR"] = ivr_entry

    return fallback
