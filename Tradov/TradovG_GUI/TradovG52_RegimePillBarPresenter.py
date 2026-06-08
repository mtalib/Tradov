#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG52_RegimePillBarPresenter.py
Purpose: Pure presenter for regime pill bar text, styles, and tooltips
"""

from __future__ import annotations

from dataclasses import dataclass

from Tradov.TradovG_GUI.TradovG41_RegimeLiquidityPresenter import build_pill_stylesheet


_REGIME_TIPS: dict[str, str] = {
    "BULL": (
        "<b>BULL REGIME</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD &gt; TRAD EMA50<br>"
        "&bull; VIX &lt; VIX EMA50<br>"
        "&bull; Not EVENT and not CRISIS<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = BULL<br>"
        "&bull; Strategy = TradovD06_BullPutSpread"
    ),
    "BEAR": (
        "<b>BEAR REGIME</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD &lt; TRAD EMA50<br>"
        "&bull; VIX &gt; VIX EMA50<br>"
        "&bull; Not EVENT and not CRISIS<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = BEAR<br>"
        "&bull; Strategy = TradovD07_BearCallSpread"
    ),
    "RANGE": (
        "<b>RANGE REGIME</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD within 1.0 ATR of EMA50<br>"
        "&bull; Term structure not stressed (VIX9D &le; VIX or VIX &le; VXV)<br>"
        "&bull; Not EVENT and not CRISIS<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = RANGE<br>"
        "&bull; Strategy = TradovD02_IronCondor"
    ),
    "VOLATILE": (
        "<b>VOLATILE REGIME</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD ATR% &ge; 1.5%<br>"
        "&bull; VIX Percentile &ge; 80th OR VIX &ge; 25<br>"
        "&bull; Not EVENT and not CRISIS<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = VOLATILE<br>"
        "&bull; Strategy = TradovD10_IronButterfly"
    ),
    "CRISIS": (
        "<b>CRISIS REGIME &mdash; HARD HALT</b><br><br>"
        "<b>Trigger (any one):</b><br>"
        "&bull; VIX9D &gt; VIX (front-vol inversion)<br>"
        "&bull; VIX &ge; 35<br>"
        "&bull; TRAD drop &le; &minus;1.25% AND VIX change &ge; +4 pts<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = CRISIS<br>"
        "&bull; Hard halt / kill-switch &mdash; no new entries"
    ),
    "EVENT": (
        "<b>EVENT REGIME &mdash; NO TRADE</b><br><br>"
        "<b>Trigger:</b><br>"
        "&bull; Event clock state in {pre, live, post}<br>"
        "&bull; OR &le; 30 min to high-impact macro event<br><br>"
        "<b>Action:</b><br>"
        "&bull; Regime = EVENT<br>"
        "&bull; Hard halt &mdash; no new strategy entries"
    ),
}

_DISPATCH_TIPS: dict[str, str] = {
    "FLOWING": (
        "<b>DISPATCH: FLOWING</b><br><br>"
        "D31 has approved and dispatched a signal in the last 120s.<br>"
        "The execution pipeline is healthy &mdash; new entries are permitted "
        "under the active Strategy Gate."
    ),
    "IDLE": (
        "<b>DISPATCH: IDLE</b><br><br>"
        "No signal events in the last 120s &mdash; no drops, no dispatches.<br>"
        "Expected outside RTH or between strategy cadences. "
        "Entries are permitted under the active Strategy Gate."
    ),
    "BLOCKED": (
        "<b>DISPATCH: BLOCKED</b><br><br>"
        "A guardrail dropped the latest signal in the last 120s.<br>"
        "See reason below; full context in "
        "<code>logs/decisions/YYYY-MM-DD.jsonl</code>."
    ),
    "ERROR": (
        "<b>DISPATCH: ERROR</b><br><br>"
        "A <code>dispatch_exception</code> occurred in the last 120s.<br>"
        "This is a system error, not a guardrail. "
        "Investigate via <code>logs/decisions/YYYY-MM-DD.jsonl</code>."
    ),
    "HALT": (
        "<b>DISPATCH: HALT &mdash; NO NEW ENTRIES</b><br><br>"
        "CRISIS or EVENT regime is active &mdash; all entry pipelines blocked "
        "by hard halt / kill-switch policy."
    ),
}

_STANCE_TIPS: dict[str, str] = {
    "BULLISH": (
        "<b>BULLISH STANCE</b><br><br>"
        "D31 maps BULL regime &rarr; BULLISH stance<br><br>"
        "<b>Execution note:</b> final strategy remains controlled by the active "
        "Strategy Gate and feature flags."
    ),
    "CHOPPY": (
        "<b>CHOPPY STANCE</b><br><br>"
        "D31 maps BEAR / RANGE / VOLATILE &rarr; CHOPPY stance<br>"
        "Specific strategy is determined by the active Strategy Gate and "
        "feature flags. See the DISPATCH tooltip for the flag-resolved map."
    ),
    "CRISIS": (
        "<b>CRISIS STANCE</b><br><br>"
        "D31 maps CRISIS / EVENT &rarr; CRISIS stance<br><br>"
        "<i>Hard halt &mdash; no new entries permitted</i>"
    ),
}

_STRESS_TIPS: dict[str, str] = {
    "LOW": (
        "<b>STRESS: LOW</b><br><br>"
        "S07 SWAN is in calm band (&lt; 1.5).<br>"
        "Lower urgency backdrop; slower metric cadence may apply."
    ),
    "MEDIUM": (
        "<b>STRESS: MEDIUM</b><br><br>"
        "S07 SWAN is in elevated band (&ge; 1.5 and &lt; 2.0).<br>"
        "Watch for transitions; baseline cadence maintained."
    ),
    "HIGH": (
        "<b>STRESS: HIGH</b><br><br>"
        "S07 SWAN is in high-stress band (&ge; 2.0 and &lt; 3.0).<br>"
        "Faster metric cadence and tighter operator attention advised."
    ),
    "CRISIS": (
        "<b>STRESS: CRISIS</b><br><br>"
        "S07 SWAN is in crisis band (&ge; 3.0).<br>"
        "Extreme stress backdrop; expect defensive behavior."
    ),
    "UNKNOWN": (
        "<b>STRESS: UNKNOWN</b><br><br>"
        "S07 stress feed not confirmed yet; fallback state displayed."
    ),
}

_GATE_TIPS: dict[str, str] = {
    "BULL TREND": (
        "<b>BULL TREND GATE</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD &gt; TRAD EMA50<br>"
        "&bull; VIX &lt; VIX EMA50<br><br>"
        "<b>Active strategy:</b> TradovD06_BullPutSpread<br>"
        "Max 2 concurrent strategies"
    ),
    "BEAR TREND": (
        "<b>BEAR TREND GATE</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD &lt; TRAD EMA50<br>"
        "&bull; VIX &gt; VIX EMA50<br><br>"
        "<b>Active strategy:</b> TradovD07_BearCallSpread<br>"
        "Max 2 concurrent strategies"
    ),
    "RANGE CALM": (
        "<b>RANGE CALM GATE</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD within 1.0 ATR of EMA50<br>"
        "&bull; Term structure not stressed (VIX9D &le; VIX)<br><br>"
        "<b>Active strategy:</b> TradovD02_IronCondor<br>"
        "Max 2 concurrent strategies"
    ),
    "HIGH VOL": (
        "<b>HIGH VOLATILITY GATE</b><br><br>"
        "<b>Trigger (all):</b><br>"
        "&bull; TRAD ATR% &ge; 1.5%<br>"
        "&bull; VIX Percentile &ge; 80th OR VIX &ge; 25<br><br>"
        "<b>Active strategy:</b> TradovD10_IronButterfly<br>"
        "Max 2 concurrent strategies"
    ),
    "CRISIS": (
        "<b>CRISIS GATE &mdash; HARD HALT</b><br><br>"
        "VIX9D &gt; VIX or VIX &ge; 35 or joint price-vol shock<br><br>"
        "<i>All entry strategies deactivated &mdash; kill-switch posture</i>"
    ),
    "EVENT": (
        "<b>EVENT GATE &mdash; NO TRADE</b><br><br>"
        "Calendar proximity to high-impact macro event (&le; 30 min window)<br><br>"
        "<i>All entry strategies deactivated &mdash; no new entries</i>"
    ),
}


@dataclass(frozen=True)
class PillPresentation:
    """Rendered text, style, and tooltip for one regime bar pill."""

    text: str
    stylesheet: str
    tooltip: str


@dataclass(frozen=True)
class RegimePillBarPresentation:
    """Full presentation payload for the regime pill bar."""

    regime_pill: PillPresentation
    stress_pill: PillPresentation
    stance_pill: PillPresentation
    gate_pill: PillPresentation
    dispatch_pill: PillPresentation
    bar_stylesheet: str


def _build_pill_presentation(
    label: str,
    value: str,
    tooltip_map: dict[str, str],
    fallback_label: str,
) -> PillPresentation:
    stylesheet, foreground = build_pill_stylesheet(value)
    return PillPresentation(
        text=f'{label}: <span style="color: {foreground};">{value}</span>',
        stylesheet=stylesheet,
        tooltip=tooltip_map.get(value, f"<b>{fallback_label}:</b> {value}"),
    )


def _build_strategy_list(
    bull_call_enabled: bool,
    bear_put_enabled: bool,
    butterfly_enabled: bool,
    pivot_enabled: bool,
    overlay_enabled: bool,
) -> str:
    bull_strategy = (
        "TradovD15_BullCallSpread"
        if bull_call_enabled else
        "TradovD06_BullPutSpread"
    )
    bear_strategy = (
        "TradovD16_BearPutSpread"
        if bear_put_enabled else
        "TradovD07_BearCallSpread"
    )
    range_strategy = "TradovD02_IronCondor"
    if pivot_enabled and butterfly_enabled:
        range_strategy = (
            "TradovD02_IronCondor "
            "(or TradovD34_PivotMeanReversion when "
            "TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true and S08 pivot_signal.fired=true; "
            "otherwise TradovD24_Butterfly when TRADOV_ENABLE_BUTTERFLY=true)"
        )
    elif pivot_enabled:
        range_strategy = (
            "TradovD02_IronCondor "
            "(or TradovD34_PivotMeanReversion when "
            "TRADOV_ENABLE_PIVOT_MEAN_REVERSION=true and S08 pivot_signal.fired=true)"
        )
    elif butterfly_enabled:
        range_strategy = (
            "TradovD02_IronCondor "
            "(or TradovD24_Butterfly when TRADOV_ENABLE_BUTTERFLY=true)"
        )
    volatile_strategy = (
        "TradovD10_IronButterfly "
        "(or TradovD23_BrokenWingButterfly for recovery / bullish-pivot entries)"
    )
    return (
        "<b>Permitted strategies:</b><br>"
        f"&bull; <b>BULL:</b> {bull_strategy}<br>"
        f"&bull; <b>BEAR:</b> {bear_strategy}<br>"
        f"&bull; <b>RANGE:</b> {range_strategy}<br>"
        f"&bull; <b>VOLATILE:</b> {volatile_strategy}"
        + "<br><br>"
        "<b>Concurrency limit:</b> D31 allows up to 3 strategy slots total. "
        "Baseline admission still uses two horizon buckets "
        "(one short/swing + one ultra_short)."
        + "<br><b>Duplicate handling:</b> Same symbol/strategy duplicates are skipped silently "
        "and do not flip DISPATCH to BLOCKED."
        + (
            "<br><b>Overlay path:</b> "
            "TRADOV_ENABLE_ODTE_PIVOT_OVERLAY_SLOT=true enables only the narrow "
            "third-slot ultra_short PivotMeanReversion overlay admission path."
            if overlay_enabled else ""
        )
    )


def build_regime_pill_bar_presentation(
    *,
    regime: str,
    stress: str,
    stance: str,
    gate: str,
    dispatch_label: str,
    dispatch_reason: str,
    execution_regime: str,
    execution_gate_key: str,
    s07_live: bool,
    swan: float,
    bull_call_enabled: bool,
    bear_put_enabled: bool,
    butterfly_enabled: bool,
    pivot_enabled: bool,
    overlay_enabled: bool,
    panel_color: str,
    border_color: str,
) -> RegimePillBarPresentation:
    """Build the full regime pill bar presentation from computed state."""
    regime_pill = _build_pill_presentation("REGIME", regime, _REGIME_TIPS, "Regime")
    stress_pill = _build_pill_presentation("STRESS", stress, _STRESS_TIPS, "Stress")
    stance_pill = _build_pill_presentation("STANCE", stance, _STANCE_TIPS, "Strategy stance")
    gate_pill = _build_pill_presentation("GATE", gate, _GATE_TIPS, "Strategy gate")

    dispatch_stylesheet, dispatch_foreground = build_pill_stylesheet(dispatch_label)
    dispatch_tooltip_parts = [_DISPATCH_TIPS.get(dispatch_label, f"<b>Dispatch:</b> {dispatch_label}")]
    dispatch_reason_compact = str(dispatch_reason).strip()
    if dispatch_reason_compact:
        dispatch_tooltip_parts.append(f"<b>Reason:</b> {dispatch_reason_compact}")

    regime_source = (
        "S07 composite (SWAN, DIX, SKEW, GEX)"
        if s07_live else
        "VIX fallback with debounce / sticky last-good S07"
    )
    dispatch_tooltip_parts.append(
        "<b>State reconciliation:</b><br>"
        f"&bull; <b>REGIME</b>: {regime} (source: {regime_source})<br>"
        f"&bull; <b>STRESS</b>: {stress} (source: S07 SWAN bands; now={swan:.2f}; "
        "LOW &lt; 1.5, MEDIUM &ge; 1.5, HIGH &ge; 2.0, CRISIS &ge; 3.0)<br>"
        f"&bull; <b>STANCE</b>: {stance} (source: D31 execution regime={execution_regime or 'n/a'})<br>"
        f"&bull; <b>GATE</b>: {gate} (source: D31 policy bucket={execution_gate_key or 'n/a'})<br>"
        f"&bull; <b>DISPATCH</b>: {dispatch_label} (source: D31 execution state, 120s recency window)"
    )
    dispatch_tooltip_parts.append(
        _build_strategy_list(
            bull_call_enabled=bull_call_enabled,
            bear_put_enabled=bear_put_enabled,
            butterfly_enabled=butterfly_enabled,
            pivot_enabled=pivot_enabled,
            overlay_enabled=overlay_enabled,
        )
    )
    dispatch_pill = PillPresentation(
        text=f'DISPATCH: <span style="color: {dispatch_foreground};">{dispatch_label}</span>',
        stylesheet=dispatch_stylesheet,
        tooltip="<br><br>".join(dispatch_tooltip_parts),
    )

    bar_stylesheet = (
        "background-color: #2a0a3a; border: 1px solid #6a2a9a;"
        if regime in ("CRISIS", "EVENT") else
        f"background-color: {panel_color}; border: 1px solid {border_color};"
    )

    return RegimePillBarPresentation(
        regime_pill=regime_pill,
        stress_pill=stress_pill,
        stance_pill=stance_pill,
        gate_pill=gate_pill,
        dispatch_pill=dispatch_pill,
        bar_stylesheet=bar_stylesheet,
    )
