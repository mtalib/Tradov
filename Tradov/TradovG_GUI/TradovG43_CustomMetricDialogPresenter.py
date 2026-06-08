#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG43_CustomMetricDialogPresenter.py
Purpose: Pure presentation helpers for WRS, PSR, and PMR detail dialogs
"""

from __future__ import annotations

import html as _html
from typing import Any

from Tradov.TradovG_GUI.TradovG42_PCADetailPresenter import format_metric_dialog_value


LEVEL_COLORS: dict[str, str] = {
    "NORMAL": "#5cffa0",
    "CAUTION": "#f2b134",
    "WARNING": "#ff9800",
    "CRITICAL": "#FF073A",
}

DUAL_REGIME_COLORS: dict[str, str] = {
    "HEALTHY": "#5cffa0",
    "MIDDLE_CLASS_PULLBACK": "#a0c4ff",
    "WORKING_CLASS_STRESS": "#f2b134",
    "EARLY_DETERIORATION": "#f2b134",
    "BROAD_STRESS": "#ff9800",
    "SYSTEMIC_CRISIS": "#FF073A",
}


def _escape_text(value: Any, fallback: str = "—") -> str:
    text = fallback if value in (None, "") else str(value)
    return _html.escape(text)


def _join_escaped(values: Any, fallback: str) -> str:
    if not isinstance(values, list):
        return fallback
    rendered = ", ".join(_html.escape(str(value)) for value in values if value not in (None, ""))
    return rendered or fallback


def _build_signal_status_html(level: Any, error: Any) -> tuple[str, str, str]:
    normalized_level = str(level or "NORMAL")
    level_color = LEVEL_COLORS.get(normalized_level, "#9bb")
    if error:
        return (
            f"<b style='color:#FF073A'>Error:</b> {_html.escape(str(error))}",
            normalized_level,
            level_color,
        )
    return (
        f"<b style='color:{level_color}'>{_html.escape(normalized_level)}</b>",
        normalized_level,
        level_color,
    )


def build_wrs_details_html(signal: dict) -> str:
    """Build the WRS details dialog HTML from the latest signal payload."""
    basket_available = signal.get("basket_available") or []
    basket_missing = signal.get("basket_missing") or []
    raw = format_metric_dialog_value(signal.get("wrs"), ".4f")
    pct_rank = format_metric_dialog_value(signal.get("wrs_pct_rank"), ".1f")
    zscore = format_metric_dialog_value(signal.get("wrs_zscore"), "+.2f")
    ma_30 = format_metric_dialog_value(signal.get("wrs_30d_ma"), ".4f")
    ma_90 = format_metric_dialog_value(signal.get("wrs_90d_ma"), ".4f")
    yoy = format_metric_dialog_value(signal.get("yoy_change"), "+.2f")
    guidance = _escape_text(
        signal.get("strategy_guidance"),
        "Insufficient data — using neutral stance.",
    )
    available = _join_escaped(basket_available, "—")
    missing = _join_escaped(basket_missing, "none")
    data_start = _escape_text(signal.get("data_start"))
    data_end = _escape_text(signal.get("data_end"))
    crossover_date = _escape_text(signal.get("last_crossover_date"))
    crossover_dir = _escape_text(signal.get("last_crossover_dir"))
    status_html, _, _ = _build_signal_status_html(
        signal.get("wrs_signal_level", "NORMAL"),
        signal.get("error") or "",
    )

    return f"""
    <h2 style='margin-bottom:4px;'>WRS — Walmart Recession Signal</h2>
    <p style='color:#9bb;'>Producer: <code>TradovS12_WRSSignal</code> &nbsp;·&nbsp;
    Consumer: strategy regime gate via <code>TradovS07_CustomMetricsOrchestrator</code></p>

    <h3>Live state</h3>
    <p>Signal level: {status_html}</p>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>WMT / Luxury ratio</b></td><td>{raw}</td></tr>
      <tr><td><b>Percentile rank (expanding)</b></td><td>{pct_rank}%</td></tr>
      <tr><td><b>Z-score (252d rolling)</b></td><td>{zscore}</td></tr>
      <tr><td><b>30-day MA</b></td><td>{ma_30}</td></tr>
      <tr><td><b>90-day MA</b></td><td>{ma_90}</td></tr>
      <tr><td><b>YoY change</b></td><td>{yoy}%</td></tr>
      <tr><td><b>Last MA crossover</b></td><td>{crossover_date} ({crossover_dir})</td></tr>
      <tr><td><b>Data range</b></td><td>{data_start} → {data_end}</td></tr>
    </table>

    <h3>Strategy guidance</h3>
    <p style='font-style:italic;'>{guidance}</p>

    <h3>Signal levels</h3>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b style='color:#5cffa0'>NORMAL</b></td><td>Pct-rank &lt; 60% — full strategy palette</td></tr>
      <tr><td><b style='color:#f2b134'>CAUTION</b></td><td>60–75% — reduce allocation 20%, avoid longs</td></tr>
      <tr><td><b style='color:#ff9800'>WARNING</b></td><td>75–90% — reduce 40%, defensive only</td></tr>
      <tr><td><b style='color:#FF073A'>CRITICAL</b></td><td>&gt;90% — reduce 60%, iron condors only</td></tr>
    </table>

    <h3>Luxury basket</h3>
    <p style='font-size:11px;'><b>Available ({len(basket_available)}):</b> {available}</p>
    <p style='font-size:11px;'><b>Missing:</b> {missing}</p>

    <hr/>
    <h3>How it works</h3>
    <ol>
      <li><b>Formula</b> — <code>WRS = Price(WMT) / mean(rebased luxury basket)</code>.
          Rising ratio signals consumer rotation from luxury to discount → recession risk.</li>
      <li><b>Luxury basket</b> — LVMUY, CFRUY, HESAY, PPRUY, BURBY, SWGAY, RACE, TPR, CPRI.
          Each ticker is rebased to 100 at its own first print; equal-weight mean.</li>
      <li><b>Data source</b> — Tradier <code>/markets/history</code> endpoint (primary);
          yfinance fallback when API key is absent.</li>
      <li><b>Refresh cadence</b> — 4-hour disk cache; computed once per session then
          served from cache. S07 reads the cache on every orchestrator cycle.</li>
      <li><b>Signal classification</b> — expanding percentile rank of the raw ratio
          against its full history. Crossovers of 30d/90d MAs trigger early alerts.</li>
    </ol>
    """


def build_psr_details_html(signal: dict, wrs_level: str, dual_signal: dict) -> str:
    """Build the PSR details dialog HTML from the latest signal payload."""
    raw = format_metric_dialog_value(signal.get("psr"), ".4f")
    pct_rank = format_metric_dialog_value(signal.get("psr_pct_rank"), ".1f")
    zscore = format_metric_dialog_value(signal.get("psr_zscore"), "+.2f")
    ma_30 = format_metric_dialog_value(signal.get("psr_30d_ma"), ".4f")
    ma_90 = format_metric_dialog_value(signal.get("psr_90d_ma"), ".4f")
    yoy = format_metric_dialog_value(signal.get("psr_yoy_change"), "+.4f")
    fcfs_px = format_metric_dialog_value(signal.get("psr_fcfs_price"), ".2f")
    ezpw_px = format_metric_dialog_value(signal.get("psr_ezpw_price"), ".2f")
    xlf_px = format_metric_dialog_value(signal.get("psr_xlf_price"), ".2f")
    guidance = _escape_text(
        signal.get("psr_strategy_guidance"),
        "Insufficient data — using neutral stance.",
    )
    data_start = _escape_text(signal.get("psr_data_start"))
    data_end = _escape_text(signal.get("psr_data_end"))
    crossover_date = _escape_text(signal.get("psr_crossover_date"))
    crossover_dir = _escape_text(signal.get("psr_crossover_dir"))
    status_html, normalized_level, level_color = _build_signal_status_html(
        signal.get("psr_signal_level", "NORMAL"),
        signal.get("psr_error") or "",
    )
    normalized_wrs_level = _escape_text(wrs_level, "NORMAL")
    dual_regime = _escape_text(dual_signal.get("regime"), "—")
    dual_color = DUAL_REGIME_COLORS.get(dual_signal.get("regime", ""), "#9bb")
    dual_description = _escape_text(dual_signal.get("description"), "")
    dual_trading_bias = _escape_text(dual_signal.get("trading_bias"), "—")
    dual_size_multiplier = _escape_text(dual_signal.get("size_multiplier"), "1.00")

    return f"""
    <h2 style='margin-bottom:4px;'>PSR — Pawn Shop Ratio</h2>
    <p style='color:#9bb;'>Producer: <code>TradovS13_PSRSignal</code> &nbsp;·&nbsp;
    Consumer: strategy regime gate via <code>TradovS07_CustomMetricsOrchestrator</code></p>
    <p style='color:#9bb; font-size:11px;'>Formula: <code>PSR = (FCFS + EZPW) / XLF</code>
    &nbsp;·&nbsp; FCFS = FirstCash Holdings &nbsp;·&nbsp; EZPW = EZCORP &nbsp;·&nbsp;
    XLF = Financial Select Sector SPDR</p>

    <h3>Live state</h3>
    <p>PSR signal level: {status_html}</p>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>(FCFS+EZPW) / XLF ratio</b></td><td>{raw}</td></tr>
      <tr><td><b>Percentile rank (expanding)</b></td><td>{pct_rank}%</td></tr>
      <tr><td><b>Z-score (252d rolling)</b></td><td>{zscore}</td></tr>
      <tr><td><b>30-day MA</b></td><td>{ma_30}</td></tr>
      <tr><td><b>90-day MA</b></td><td>{ma_90}</td></tr>
      <tr><td><b>YoY change</b></td><td>{yoy}</td></tr>
      <tr><td><b>Last MA crossover</b></td><td>{crossover_date} ({crossover_dir})</td></tr>
      <tr><td><b>Data range</b></td><td>{data_start} → {data_end}</td></tr>
    </table>

    <h3>Component prices</h3>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>FCFS (FirstCash Holdings)</b></td><td>${fcfs_px}</td></tr>
      <tr><td><b>EZPW (EZCORP)</b></td><td>${ezpw_px}</td></tr>
      <tr><td><b>XLF (Financial Select Sector SPDR)</b></td><td>${xlf_px}</td></tr>
    </table>

    <h3>Strategy guidance</h3>
    <p style='font-style:italic;'>{guidance}</p>

    <h3>PSR signal levels</h3>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b style='color:#5cffa0'>NORMAL</b></td>
          <td>Pct-rank &lt; 60% — banks healthy, credit flowing freely</td></tr>
      <tr><td><b style='color:#f2b134'>CAUTION</b></td>
          <td>60–75% — pawn sector outperforming; early credit tightening</td></tr>
      <tr><td><b style='color:#ff9800'>WARNING</b></td>
          <td>75–90% — significant working-class liquidity stress</td></tr>
      <tr><td><b style='color:#FF073A'>CRITICAL</b></td>
          <td>&gt;90% — systemic credit crunch; liquidity exhaustion</td></tr>
    </table>

    <hr/>
    <h3>Dual-Signal Assessment (PSR × WRS)</h3>
    <p>WRS level: <b>{normalized_wrs_level}</b> &nbsp;·&nbsp; PSR level: <b style='color:{level_color}'>{_html.escape(normalized_level)}</b></p>
    <p>Macro regime: <b style='color:{dual_color}'>{dual_regime}</b></p>
    <p>{dual_description}</p>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>Trading bias</b></td><td>{dual_trading_bias}</td></tr>
      <tr><td><b>Size multiplier</b></td><td>{dual_size_multiplier}×</td></tr>
    </table>

    <hr/>
    <h3>How it works</h3>
    <ol>
      <li><b>Thesis</b> — When traditional credit tightens, working-class households
          resort to pawn collateral loans (the “bank of last resort”). Pawn equities
          outperform bank stocks precisely when the credit cycle rolls over.</li>
      <li><b>Formula</b> — <code>PSR = (FCFS + EZPW) / XLF</code>.
          Rising PSR = Wall Street pricing in credit crunch: banks face defaults
          while pawn shops see surging demand.</li>
      <li><b>Leading vs lagging</b> — PSR leads credit card write-offs, CPI, and
          unemployment by several months. Borrowers pawn assets before they default
          on primary debts or face eviction.</li>
      <li><b>Data source</b> — Tradier <code>/markets/history</code> endpoint (primary);
          yfinance fallback when API key is absent.</li>
      <li><b>Refresh cadence</b> — 4-hour disk cache; PSR moves on weekly/monthly
          timescales. S07 reads the cache on every orchestrator cycle.</li>
      <li><b>Signal classification</b> — expanding percentile rank of the raw ratio
          against its full history since 2000. Crossovers of 30d/90d MAs trigger early alerts.</li>
    </ol>
    """


def build_pmr_details_html(state: dict) -> str:
    """Build the PMR details dialog HTML from the last pivot-signal state."""
    enabled = bool(state.get("enabled"))
    available = bool(state.get("available"))
    fired = bool(state.get("fired"))
    raw_direction = state.get("direction") or "—"
    direction = _escape_text(raw_direction)
    score_str = format_metric_dialog_value(state.get("score"), ".1f")
    level_name = _escape_text(state.get("level_name"))
    level_price_str = format_metric_dialog_value(state.get("level_price"), ".2f")
    atr_str = format_metric_dialog_value(state.get("atr_distance"), ".2f")
    reasons = state.get("reasons") or []
    penalties = state.get("penalties") or []

    if not available:
        status_line = "<b style='color:#FF073A'>N/A</b> — S08 module not importable"
    elif not enabled:
        status_line = (
            "<b style='color:#FF073A'>DISABLED</b> "
            "(set <code>TRADOV_PIVOT_MR_ENABLED=1</code> to enable)"
        )
    elif not fired:
        status_line = "<b style='color:#f2b134'>ARMED</b> — watching for setup"
    else:
        arrow = "▼" if raw_direction == "fade_resistance" else "▲"
        status_line = (
            f"<b style='color:#5cffa0'>FIRED</b> {arrow} {direction} @ "
            f"{level_name} {level_price_str} (score {score_str})"
        )

    reasons_html = (
        "<ul>" + "".join(f"<li>{_html.escape(str(reason))}</li>" for reason in reasons) + "</ul>"
        if reasons else "<i>none</i>"
    )
    penalties_html = (
        "<ul>" + "".join(f"<li>{_html.escape(str(penalty))}</li>" for penalty in penalties) + "</ul>"
        if penalties else "<i>none</i>"
    )

    return f"""
    <h2 style='margin-bottom:4px;'>PMR — Pivot Mean-Reversion Signal</h2>
    <p style='color:#9bb;'>Producer: <code>TradovS08_PivotMeanReversionSignal</code> &nbsp;·&nbsp;
    Consumer: <code>TradovD25_UnifiedCreditSpreadEngine</code> (via R08 paper worker)</p>

    <h3>Live state</h3>
    <p>{status_line}</p>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>Direction</b></td><td>{direction}</td></tr>
      <tr><td><b>Score</b></td><td>{score_str}</td></tr>
      <tr><td><b>Nearest level</b></td><td>{level_name} @ {level_price_str}</td></tr>
      <tr><td><b>ATR distance</b></td><td>{atr_str}</td></tr>
    </table>

    <h3>Reasons</h3>
    {reasons_html}

    <h3>Penalties</h3>
    {penalties_html}

    <hr/>
    <h3>How it works</h3>
    <ol>
      <li><b>Pivots</b> — classical daily floor pivots (P, R1/R2/R3, S1/S2/S3)
          are computed at the open from the prior session's H/L/C.</li>
      <li><b>Proximity filter</b> — current TRAD price must be within an ATR-based
          distance to a resistance (fade-resistance) or support (fade-support) level.</li>
      <li><b>Core inputs</b> — S08 scores the setup using regime label,
          ATR-normalised distance, RSI confirmation and net dealer GEX context.</li>
      <li><b>Penalties / vetoes</b> — score is reduced during event-window or
          edge-of-day periods, and when VIX is elevated/backwardated.</li>
      <li><b>Score</b> — final confidence score (0–100) with fire threshold at
          <code>MIN_FIRE_SCORE=60</code>.</li>
      <li><b>Downstream</b> — D25 reads the signal each tick; if <code>fired</code>
          and score exceeds the threshold, it biases credit-spread selection toward
          the fade side (bear-call on fade-resistance, bull-put on fade-support).</li>
    </ol>

    <h3>Display legend</h3>
    <ul>
      <li><b>DIS</b> — producer disabled (env flag off)</li>
      <li><b>N/A</b> — S08 module not importable</li>
      <li><b>ARMED</b> — enabled, watching, not yet fired</li>
      <li><b>▼ &lt;score&gt;</b> — fade-resistance fired (bearish bias)</li>
      <li><b>▲ &lt;score&gt;</b> — fade-support fired (bullish bias)</li>
    </ul>
    """
