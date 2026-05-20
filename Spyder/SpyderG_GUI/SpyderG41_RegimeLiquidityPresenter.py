#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG41_RegimeLiquidityPresenter.py
Purpose: Pure presentation helpers for liquidity diagnostics and regime pill styling
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class LiquidityDiagnosticsSummary:
    """Aggregated liquidity diagnostics values for the dashboard panel."""

    total: int
    pass_count: int
    fail_count: int
    top_failure: str
    median_freshness_ms: float


@dataclass(frozen=True)
class LiquidityDiagnosticsPanelPresentation:
    """Dashboard-ready liquidity diagnostics label text."""

    candidates_text: str
    pass_ratio_text: str
    freshness_text: str
    top_failure_text: str


def summarize_liquidity_diagnostics(payload: Mapping[str, Any] | None) -> LiquidityDiagnosticsSummary:
    """Summarize S07 liquidity diagnostics payload into dashboard-friendly scalars."""
    data = payload.get("data", {}) if isinstance(payload, Mapping) else {}
    candidates = data.get("candidates", []) if isinstance(data, Mapping) else []
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        candidates = []

    total = len(candidates)
    pass_count = 0
    reason_counts: dict[str, int] = {}
    freshness_samples: list[float] = []

    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        if candidate.get("pass") is True:
            pass_count += 1
        for reason in candidate.get("fail_reasons", []) or []:
            if isinstance(reason, str) and reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        snapshot = candidate.get("snapshot", {}) if isinstance(candidate.get("snapshot", {}), Mapping) else {}
        quote_age_ms = snapshot.get("quote_age_ms")
        if isinstance(quote_age_ms, (int, float)):
            freshness_samples.append(float(quote_age_ms))

    fail_count = max(0, total - pass_count)
    top_failure = max(reason_counts.items(), key=lambda item: item[1])[0] if reason_counts else "none"
    median_freshness_ms = float(median(freshness_samples)) if freshness_samples else float("nan")

    return LiquidityDiagnosticsSummary(
        total=total,
        pass_count=pass_count,
        fail_count=fail_count,
        top_failure=top_failure,
        median_freshness_ms=median_freshness_ms,
    )


def build_liquidity_diagnostics_panel_presentation(
    summary: LiquidityDiagnosticsSummary,
) -> LiquidityDiagnosticsPanelPresentation:
    """Build liquidity diagnostics panel label text from a summary."""
    freshness = summary.median_freshness_ms
    freshness_text = (
        "-"
        if isinstance(freshness, float) and freshness != freshness
        else f"{freshness:.0f} ms"
    )
    return LiquidityDiagnosticsPanelPresentation(
        candidates_text=str(summary.total),
        pass_ratio_text=f"{summary.pass_count}/{summary.total}" if summary.total else "0/0",
        freshness_text=freshness_text,
        top_failure_text="none" if summary.fail_count <= 0 else summary.top_failure,
    )


def build_pill_stylesheet(category: str) -> tuple[str, str]:
    """Return (stylesheet, semantic foreground color) for the given pill category."""
    normalized = str(category or "").lower()
    if normalized == "low":
        bg, border, fg = "#1a4a1a", "#2d8a2d", "#5ddb5d"
    elif normalized == "medium":
        bg, border, fg = "#3a2800", "#8a5a00", "#e09020"
    elif normalized == "high":
        bg, border, fg = "#4a1a1a", "#8a2d2d", "#e05555"
    elif normalized == "crisis":
        bg, border, fg = "#3a1055", "#9a30dd", "#cc88ff"
    elif any(token in normalized for token in ("bull", "bullish", "flowing")):
        bg, border, fg = "#1a4a1a", "#2d8a2d", "#5ddb5d"
    elif any(token in normalized for token in ("bear", "bearish", "error")):
        bg, border, fg = "#4a1a1a", "#8a2d2d", "#e05555"
    elif any(token in normalized for token in ("crisis", "event", "halt", "risk-off")):
        bg, border, fg = "#3a1055", "#9a30dd", "#cc88ff"
    elif normalized == "none" or normalized.endswith(": none") or normalized == "idle":
        bg, border, fg = "#3a3a3a", "#666666", "#aaaaaa"
    elif any(token in normalized for token in ("range", "neutral", "choppy", "volatile", "cautious", "blocked")):
        bg, border, fg = "#3a2800", "#8a5a00", "#e09020"
    else:
        bg, border, fg = "#1e1e1e", "#444444", "#aaaaaa"

    stylesheet = (
        f"color: white; background-color: {bg}; "
        f"border: 1px solid {border}; border-radius: 4px; "
        "padding: 2px 10px; font-size: 13px;"
    )
    return stylesheet, fg
