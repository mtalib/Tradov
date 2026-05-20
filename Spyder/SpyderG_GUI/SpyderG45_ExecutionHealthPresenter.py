#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG45_ExecutionHealthPresenter.py
Purpose: Pure presentation helpers for execution-health diagnostics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class ExecutionHealthPresentation:
    """Dashboard-ready execution-health label text."""

    slippage_bps_text: str
    fill_latency_text: str
    reject_rate_text: str
    partial_fill_text: str


def build_execution_health_presentation(
    samples: Sequence[Mapping[str, Any]] | None,
) -> ExecutionHealthPresentation:
    """Build execution-health panel text from rolling telemetry samples."""
    records = [sample for sample in (samples or []) if isinstance(sample, Mapping)]
    if not records:
        return ExecutionHealthPresentation(
            slippage_bps_text="-",
            fill_latency_text="-",
            reject_rate_text="-",
            partial_fill_text="-",
        )

    latest_slippage = next(
        (
            sample.get("slippage_bps")
            for sample in reversed(records)
            if isinstance(sample.get("slippage_bps"), (int, float))
        ),
        None,
    )
    latest_latency = next(
        (
            sample.get("fill_latency_ms")
            for sample in reversed(records)
            if isinstance(sample.get("fill_latency_ms"), (int, float))
        ),
        None,
    )

    reject_count = sum(1 for sample in records if sample.get("reject_flag"))
    reject_rate = reject_count / len(records)

    partial_vals = [
        float(sample.get("partial_fill_ratio"))
        for sample in records
        if isinstance(sample.get("partial_fill_ratio"), (int, float))
    ]
    partial_ratio = float(np.mean(partial_vals)) if partial_vals else 0.0

    return ExecutionHealthPresentation(
        slippage_bps_text=(
            "-" if latest_slippage is None else f"{float(latest_slippage):.1f} bps"
        ),
        fill_latency_text=(
            "-" if latest_latency is None else f"{float(latest_latency):.0f} ms"
        ),
        reject_rate_text=f"{reject_rate * 100.0:.1f}%",
        partial_fill_text=f"{partial_ratio * 100.0:.1f}%",
    )
