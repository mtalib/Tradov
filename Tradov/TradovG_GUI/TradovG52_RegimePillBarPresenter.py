#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG52_RegimePillBarPresenter.py
Purpose: Pure presenter for regime pill bar text, styles, and tooltips
"""

from __future__ import annotations

from dataclasses import dataclass

from Tradov.TradovG_GUI.TradovG41_RegimeLiquidityPresenter import build_pill_stylesheet


# Regime is classified by the S07 composite stress model (SWAN/DIX/SKEW/GEX);
# when S07 is stale a VIX/term-structure fallback is used (committed after a few
# cycles, sticky otherwise). Strategy selection is operator-curated via the
# STRATEGIES selector and is independent of the regime — the regime sets the
# execution posture (Gate / Stance) and the halt policy, not the strategy.
_REGIME_TIPS: dict[str, str] = {
    "UNAVAILABLE": (
        "<b>REGIME UNAVAILABLE</b><br><br>"
        "S07 market conditions are unavailable or stale.<br>"
        "The dashboard is showing an explicit unavailable state instead of "
        "fabricating a neutral regime."
    ),
    "BULL": (
        "<b>BULL REGIME</b><br><br>"
        "<b>Trigger (S07 composite):</b><br>"
        "&bull; DIX &ge; 46, GEX &ge; 0, SWAN &lt; 1.9<br>"
        "&bull; or DIX &ge; 43 and SWAN &lt; 1.92<br>"
        "&bull; VIX fallback: SPX day change &ge; +0.3% and VIX &lt; 24<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = BULL TREND, Stance = BULLISH<br>"
        "&bull; New entries permitted; strategies operator-curated"
    ),
    "BEAR": (
        "<b>BEAR REGIME</b><br><br>"
        "<b>Trigger (S07 composite):</b><br>"
        "&bull; DIX &le; 40 and SWAN &ge; 1.85<br>"
        "&bull; VIX fallback: SPX day change &le; &minus;1.5%<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = BEAR TREND, Stance = CHOPPY<br>"
        "&bull; New entries permitted; strategies operator-curated"
    ),
    "RANGE": (
        "<b>RANGE REGIME</b><br><br>"
        "<b>Trigger (S07 composite):</b><br>"
        "&bull; SKEW &ge; 140 and DIX &lt; 42<br>"
        "&bull; or no stronger directional / stress signal (default)<br>"
        "&bull; VIX fallback: not BULL/BEAR/VOLATILE/CRISIS<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = RANGE CALM, Stance = CHOPPY<br>"
        "&bull; New entries permitted; strategies operator-curated"
    ),
    "VOLATILE": (
        "<b>VOLATILE REGIME</b><br><br>"
        "<b>Trigger (S07 composite):</b><br>"
        "&bull; SWAN &ge; 1.95 or SKEW &ge; 150<br>"
        "&bull; VIX fallback: VIX &ge; 25<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = HIGH VOL, Stance = CHOPPY<br>"
        "&bull; Entries permitted under elevated stress; strategies operator-curated"
    ),
    "CRISIS": (
        "<b>CRISIS REGIME &mdash; HARD HALT</b><br><br>"
        "<b>Trigger (any one):</b><br>"
        "&bull; SWAN &ge; 2.0 (S07 composite)<br>"
        "&bull; VIX fallback: VIX9D &gt; VIX (front-vol inversion) or VIX &ge; 35<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = CRISIS, Stance = CRISIS<br>"
        "&bull; Hard halt / kill-switch &mdash; no new entries (DISPATCH = HALT)"
    ),
    "EVENT": (
        "<b>EVENT REGIME &mdash; NO TRADE</b><br><br>"
        "<b>Trigger:</b><br>"
        "&bull; Event clock state in {pre, live, post}<br>"
        "&bull; or &le; 30 min to high-impact macro event<br><br>"
        "<b>Action:</b><br>"
        "&bull; Gate = EVENT<br>"
        "&bull; Hard halt &mdash; no new entries (DISPATCH = HALT)"
    ),
}

_DISPATCH_TIPS: dict[str, str] = {
    "UNAVAILABLE": (
        "<b>DISPATCH: UNAVAILABLE</b><br><br>"
        "S07 market conditions are unavailable or stale. "
        "Execution posture is being shown explicitly as unavailable."
    ),
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
    "UNAVAILABLE": (
        "<b>STANCE: UNAVAILABLE</b><br><br>"
        "The regime layer does not have fresh S07 market conditions."
    ),
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

# The GATE is the D31 execution-policy bucket derived from the regime. It sets
# the entry posture (permit vs halt); the specific strategies are operator-
# curated via the STRATEGIES selector, not fixed per gate.
_GATE_TIPS: dict[str, str] = {
    "UNAVAILABLE": (
        "<b>UNAVAILABLE GATE</b><br><br>"
        "The regime layer does not have fresh S07 market conditions."
    ),
    "BULL TREND": (
        "<b>BULL TREND GATE</b><br><br>"
        "Derived from a BULL regime (DIX/GEX strong, SWAN low).<br><br>"
        "<b>Posture:</b> new entries permitted; strategies operator-curated.<br>"
        "Max 3 concurrent strategy slots."
    ),
    "BEAR TREND": (
        "<b>BEAR TREND GATE</b><br><br>"
        "Derived from a BEAR regime (DIX weak, SWAN elevated).<br><br>"
        "<b>Posture:</b> new entries permitted; strategies operator-curated.<br>"
        "Max 3 concurrent strategy slots."
    ),
    "RANGE CALM": (
        "<b>RANGE CALM GATE</b><br><br>"
        "Derived from a RANGE regime (no strong directional / stress signal).<br><br>"
        "<b>Posture:</b> new entries permitted; strategies operator-curated.<br>"
        "Max 3 concurrent strategy slots."
    ),
    "HIGH VOL": (
        "<b>HIGH VOLATILITY GATE</b><br><br>"
        "Derived from a VOLATILE regime (SWAN &ge; 1.95 or SKEW &ge; 150; VIX &ge; 25).<br><br>"
        "<b>Posture:</b> entries permitted under elevated stress; strategies operator-curated.<br>"
        "Max 3 concurrent strategy slots."
    ),
    "CRISIS": (
        "<b>CRISIS GATE &mdash; HARD HALT</b><br><br>"
        "SWAN &ge; 2.0, or VIX9D &gt; VIX inversion, or VIX &ge; 35.<br><br>"
        "<i>All entries deactivated &mdash; kill-switch posture (DISPATCH = HALT)</i>"
    ),
    "EVENT": (
        "<b>EVENT GATE &mdash; NO TRADE</b><br><br>"
        "Calendar proximity to a high-impact macro event (&le; 30 min window).<br><br>"
        "<i>All entries deactivated &mdash; no new entries (DISPATCH = HALT)</i>"
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
    # Permitted strategies are operator-curated via the STRATEGIES selector on
    # the regime bar (not auto-mapped per regime). These are this system's
    # stat-arb stock/ETF strategies. The legacy options-strategy / regime-map
    # listing belonged to a different app. The boolean flags are retained for
    # caller compatibility but no longer affect this list.
    del bull_call_enabled, bear_put_enabled, butterfly_enabled, pivot_enabled, overlay_enabled
    return (
        "<b>Permitted strategies:</b> operator-curated via the STRATEGIES "
        "selector (right of DISPATCH).<br>"
        "&bull; <b>PairTrading</b> (D42) &mdash; cointegration / Kalman z-score<br>"
        "&bull; <b>DistanceApproach</b> (D43) &mdash; SSD normalized-price pairs<br>"
        "&bull; <b>PCAStatArb</b> (D44) &mdash; eigenportfolio residual s-score"
        + "<br><br>"
        "<b>Concurrency limit:</b> D31 admits up to 3 strategy slots total."
        + "<br><b>Duplicate handling:</b> Same symbol/strategy duplicates are skipped "
        "silently and do not flip DISPATCH to BLOCKED."
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
    swan_value_text = "n/a"
    if s07_live:
        try:
            swan_value_text = f"{float(swan):.2f}"
        except Exception:
            swan_value_text = "n/a"
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
    if regime == "UNAVAILABLE":
        regime_source = "S07 market conditions unavailable"
    dispatch_tooltip_parts.append(
        "<b>State reconciliation:</b><br>"
        f"&bull; <b>REGIME</b>: {regime} (source: {regime_source})<br>"
        f"&bull; <b>STRESS</b>: {stress} (source: S07 SWAN bands; now={swan_value_text}; "
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
