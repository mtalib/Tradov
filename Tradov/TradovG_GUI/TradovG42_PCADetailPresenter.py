#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG42_PCADetailPresenter.py
Purpose: Pure presentation helpers for PCA custom-metric detail dialogs
"""

from __future__ import annotations

import html as _html
import math
from typing import Any


def format_metric_dialog_value(value: Any, fmt: str, fallback: str = "—") -> str:
    """Format numeric values for details dialogs."""
    try:
        coerced = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(coerced):
        return fallback
    return format(coerced, fmt)


def build_metric_sparkline(values: list[float]) -> str:
    """Convert a recent numeric series into a compact sparkline string."""
    blocks = "▁▂▃▄▅▆▇█"
    finite_values: list[float] = []
    for value in values if isinstance(values, list) else []:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric):
            finite_values.append(numeric)

    if not finite_values:
        return "Unavailable"

    low = min(finite_values)
    high = max(finite_values)
    if math.isclose(low, high):
        return blocks[3] * len(finite_values)

    span = high - low
    scaled = []
    for value in finite_values:
        position = (value - low) / span
        index = int(round(position * (len(blocks) - 1)))
        index = min(len(blocks) - 1, max(0, index))
        scaled.append(blocks[index])
    return "".join(scaled)


def coerce_metric_float(value: Any) -> float | None:
    """Return a finite float when a metric value can be parsed."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric):
        return None
    return numeric


def build_pca_proxy_operator_takeaway(
    entry: dict,
    details: dict,
    decomposition: dict,
) -> str:
    """Build a one-line operator takeaway for the PCA-Proxy dialog."""
    value = coerce_metric_float(entry.get("value"))
    pc2_abs = coerce_metric_float(decomposition.get("pc2_abs"))
    status = str(details.get("status") or "unknown").lower()
    regime_band = str(decomposition.get("regime_band") or "").lower()

    if status != "live":
        if status == "fallback":
            return "Fallback breadth context only; confirm direction with other market internals."
        return "Breadth factor is not fully live; use this row as supplemental context only."

    rotation_active = (
        (pc2_abs is not None and pc2_abs >= 1.0)
        or "rotation" in regime_band
        or "dispersion" in regime_band
    )
    if rotation_active:
        if value is not None and value >= 0.35:
            return "Positive breadth lean, but internal sector rotation is still elevated."
        if value is not None and value <= -0.35:
            return "Negative breadth lean with elevated internal sector rotation."
        return "Mixed breadth with elevated internal sector rotation."

    if value is None:
        return "Breadth factor is available, but the latest directional lean is unclear."
    if value >= 0.75:
        return "Broad upside impulse with sectors moving in sync."
    if value >= 0.35:
        return "Moderate positive breadth lean across sectors."
    if value <= -0.75:
        return "Broad downside impulse with sectors moving in sync."
    if value <= -0.35:
        return "Moderate negative breadth lean across sectors."
    return "Mixed breadth with no strong one-sided sector factor."


def build_pca_iv_operator_takeaway(
    entry: dict,
    details: dict,
    nested_details: dict,
) -> str:
    """Build a one-line operator takeaway for the PCA-IV dialog."""
    value = coerce_metric_float(entry.get("value"))
    pc2_abs = coerce_metric_float(nested_details.get("pc2_abs"))
    status = str(details.get("status") or "placeholder").lower()
    phase = str(nested_details.get("phase") or status).lower()
    regime_band = str(nested_details.get("regime_band") or "").lower()

    if status != "live":
        if "seed" in phase or "history" in phase:
            return "Seeding in progress; use this row as readiness context, not a live IV factor read."
        if status == "fallback":
            return "Live IV factor unavailable this cycle; confirm with ATM IV, skew, and term structure."
        return "IV surface factor is staged but not yet producing a live read."

    structure_active = (
        (pc2_abs is not None and pc2_abs >= 1.0)
        or "twist" in regime_band
        or "skew" in regime_band
        or "curve" in regime_band
    )
    if value is None:
        return "Live IV factor is available, but the latest directional lean is unclear."
    if value <= -0.75:
        if structure_active:
            return "Compression bias with skew and curve structure still active."
        return "Clear compression bias across the IV surface."
    if value <= -0.35:
        if structure_active:
            return "Mild compression bias with skew and curve structure still active."
        return "Mild compression bias across the IV surface."
    if value >= 0.75:
        if structure_active:
            return "Stress-expansion bias with skew and curve structure still active."
        return "Stress-expansion bias across the IV surface."
    if value >= 0.35:
        if structure_active:
            return "Mild stress-expansion bias with skew and curve structure still active."
        return "Mild stress-expansion bias across the IV surface."
    if structure_active:
        return "Flat IV-factor bias; skew and curve details matter more than direction."
    return "Flat IV-factor bias with no strong expansion or compression lean."


def build_pca_proxy_details_html(entry: dict) -> str:
    """Build the PCA-Proxy details dialog HTML from the latest metric payload."""
    details = entry.get("details", {}) if isinstance(entry, dict) else {}
    if not isinstance(details, dict):
        details = {}
    decomposition = details.get("details", {}) if isinstance(details.get("details", {}), dict) else {}

    value = format_metric_dialog_value(entry.get("value"), "+.2f")
    change = format_metric_dialog_value(entry.get("change"), "+.2f")
    quality = format_metric_dialog_value(entry.get("quality"), ".0%")
    explained_variance = format_metric_dialog_value(details.get("explained_variance"), ".1%")
    spectral_gap = format_metric_dialog_value(details.get("spectral_gap"), ".3f")
    dispersion_score = format_metric_dialog_value(details.get("dispersion_score"), ".3f")
    confidence = format_metric_dialog_value(details.get("confidence"), ".0%")
    pc1_score = format_metric_dialog_value(decomposition.get("pc1_score"), "+.3f")
    pc2_abs = format_metric_dialog_value(decomposition.get("pc2_abs"), ".3f")
    universe_size = str(details.get("universe_size", "—"))
    timestamp = _html.escape(str(details.get("timestamp") or "—"))
    source = _html.escape(str(details.get("source") or "—"))
    status = str(details.get("status") or "unknown").lower()
    status_colors = {
        "live": "#5cffa0",
        "fallback": "#ff9800",
        "unknown": "#9bb",
    }
    status_label = _html.escape(status.upper())
    status_color = status_colors.get(status, "#9bb")
    error_text = _html.escape(str(details.get("details", {}).get("error") or "")) if isinstance(details.get("details", {}), dict) else ""

    symbols = decomposition.get("symbols") if isinstance(decomposition.get("symbols"), list) else []
    symbol_text = _html.escape(", ".join(str(symbol) for symbol in symbols) or "—")
    recent_values = (
        decomposition.get("recent_signal_history")
        if isinstance(decomposition.get("recent_signal_history"), list)
        else []
    )
    recent_window = decomposition.get("history_window") or len(recent_values) or "—"
    recent_drift = "—"
    if len(recent_values) >= 2:
        recent_drift = format_metric_dialog_value(
            recent_values[-1] - recent_values[0],
            "+.2f",
        )
    sparkline = _html.escape(build_metric_sparkline(recent_values))
    regime_band = _html.escape(str(decomposition.get("regime_band") or "Unknown"))
    regime_color = _html.escape(str(decomposition.get("regime_color") or "#9bb"))
    regime_note = _html.escape(str(decomposition.get("regime_note") or ""))
    takeaway = _html.escape(
        build_pca_proxy_operator_takeaway(entry, details, decomposition),
    )

    fallback_note = ""
    if error_text:
        fallback_note = (
            "<p><b style='color:#ff9800'>Fallback context:</b> "
            f"{error_text}</p>"
        )

    return f"""
    <h2 style='margin-bottom:4px;'>PCA-Proxy — Sector Eigenfactor Signal</h2>
    <p style='color:#9bb;'>Producer: <code>TradovS14_PCASignals</code> &nbsp;·&nbsp;
    Publisher: <code>TradovS07_CustomMetricsOrchestrator</code> &nbsp;·&nbsp;
    Panel: <code>Custom Metrics</code></p>
    <p style='margin:8px 0 14px 0; padding:8px 10px; background:#10171d; border-left:3px solid #4db6ff;'>
    <b>Operator takeaway</b>: {takeaway}</p>

            <h3>How to read the number</h3>
            <ul>
                <li><b>Positive</b> — sector moves align with the dominant common factor.</li>
                <li><b>Negative</b> — sector moves lean against that factor.</li>
                <li><b>Near zero</b> — breadth is mixed rather than strongly one-sided.</li>
                <li><b>Rough strength guide</b> — around <code>±0.35</code> is a mild lean; around <code>±0.75</code> is a stronger impulse.</li>
            </ul>

    <h3>Live state</h3>
    <p>Status: <b style='color:{status_color}'>{status_label}</b></p>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>Composite signal</b></td><td>{value}</td></tr>
      <tr><td><b>Day-over-day change</b></td><td>{change}</td></tr>
      <tr><td><b>Explained variance (PC1)</b></td><td>{explained_variance}</td></tr>
      <tr><td><b>Spectral gap</b></td><td>{spectral_gap}</td></tr>
      <tr><td><b>Dispersion score |PC2|</b></td><td>{dispersion_score}</td></tr>
      <tr><td><b>Confidence</b></td><td>{confidence}</td></tr>
      <tr><td><b>Widget quality</b></td><td>{quality}</td></tr>
      <tr><td><b>Universe size</b></td><td>{universe_size}</td></tr>
      <tr><td><b>Source</b></td><td>{source}</td></tr>
      <tr><td><b>Timestamp</b></td><td>{timestamp}</td></tr>
    </table>

    <h3>Decomposition</h3>
    <table cellpadding='4' style='font-size:12px;'>
      <tr><td><b>Raw PC1 score</b></td><td>{pc1_score}</td></tr>
      <tr><td><b>Absolute PC2 score</b></td><td>{pc2_abs}</td></tr>
      <tr><td><b>Sector proxies</b></td><td>{symbol_text}</td></tr>
    </table>

            <h3>Recent history</h3>
            <p><b>Regime band</b>: <span style='color:{regime_color}; font-weight:600;'>{regime_band}</span></p>
            <p style='font-family:monospace; font-size:24px; letter-spacing:1px; margin:6px 0 4px 0;'>{sparkline}</p>
            <p style='color:#9bb;'>Last {recent_window} trading sessions · Net drift {recent_drift}</p>
            <p>{regime_note}</p>
    {fallback_note}

    <hr/>
    <h3>How it works</h3>
    <ol>
      <li><b>Universe</b> — the signal uses the liquid SPDR sector ETF basket as a practical TRAD breadth proxy.</li>
      <li><b>Window</b> — rolling daily log returns are standardized over roughly one trading year.</li>
      <li><b>PCA step</b> — the first principal component measures the dominant common sector factor; the second component is used as a simple rotation / dispersion check.</li>
      <li><b>Displayed value</b> — the dashboard shows the latest PC1 score scaled by <code>(0.5 + explained variance)</code> so stronger common-factor regimes carry more weight.</li>
      <li><b>Reading</b> — positive values mean the latest sector move aligns with the dominant factor; negative values mean it moved against that factor; high absolute PC2 suggests more internal rotation under the headline move.</li>
      <li><b>Source policy</b> — Tradier daily history is preferred; <code>yfinance</code> is a fallback when Tradier history is unavailable.</li>
    </ol>
    """


def build_pca_iv_details_html(entry: dict) -> str:
    """Build the PCA-IV details dialog HTML for live or seeded states."""
    details = entry.get("details", {}) if isinstance(entry, dict) else {}
    if not isinstance(details, dict):
        details = {}
    nested_details = details.get("details", {}) if isinstance(details.get("details", {}), dict) else {}

    value = format_metric_dialog_value(entry.get("value"), "+.2f")
    change = format_metric_dialog_value(entry.get("change"), "+.2f")
    quality = format_metric_dialog_value(entry.get("quality"), ".0%")
    explained_variance = format_metric_dialog_value(details.get("explained_variance"), ".1%")
    spectral_gap = format_metric_dialog_value(details.get("spectral_gap"), ".3f")
    dispersion_score = format_metric_dialog_value(details.get("dispersion_score"), ".3f")
    confidence = format_metric_dialog_value(details.get("confidence"), ".0%")
    timestamp = _html.escape(str(details.get("timestamp") or "—"))
    source = _html.escape(str(details.get("source") or "—"))
    status_value = str(details.get("status") or "placeholder").lower()
    status = _html.escape(status_value.upper())
    message = _html.escape(str(nested_details.get("message") or "Reserved for future IV-surface PCA work."))
    target_surface = _html.escape(str(nested_details.get("target_surface") or "moneyness x dte implied-vol grid"))
    phase = _html.escape(str(nested_details.get("phase") or "placeholder"))
    stored_snapshots = _html.escape(str(nested_details.get("stored_snapshots") or 0))
    min_live_snapshots = _html.escape(str(nested_details.get("min_live_snapshots") or "—"))
    target_snapshots = _html.escape(str(nested_details.get("target_snapshots") or "—"))
    readiness_progress = format_metric_dialog_value(
        nested_details.get("readiness_progress"),
        ".0%",
    )
    first_snapshot_ts = _html.escape(str(nested_details.get("first_snapshot_ts") or "—"))
    last_snapshot_ts = _html.escape(str(nested_details.get("last_snapshot_ts") or "—"))
    history_path = _html.escape(str(nested_details.get("history_path") or "—"))
    feature_columns = nested_details.get("feature_columns") if isinstance(nested_details.get("feature_columns"), list) else []
    feature_text = _html.escape(", ".join(str(column) for column in feature_columns) or "—")
    takeaway = _html.escape(
        build_pca_iv_operator_takeaway(entry, details, nested_details),
    )

    if status_value == "live":
        pc1_score = format_metric_dialog_value(nested_details.get("pc1_score"), "+.3f")
        pc2_abs = format_metric_dialog_value(nested_details.get("pc2_abs"), ".3f")
        feature_level = format_metric_dialog_value(nested_details.get("feature_level"), ".3f")
        feature_skew = format_metric_dialog_value(nested_details.get("feature_skew"), ".3f")
        feature_convexity = format_metric_dialog_value(nested_details.get("feature_convexity"), ".3f")
        row_count = _html.escape(str(nested_details.get("row_count") or "—"))
        recent_values = nested_details.get("recent_signal_history") if isinstance(nested_details.get("recent_signal_history"), list) else []
        sparkline = _html.escape(build_metric_sparkline(recent_values))
        recent_window = nested_details.get("history_window") or len(recent_values) or "—"
        recent_drift = "—"
        if len(recent_values) >= 2:
            recent_drift = format_metric_dialog_value(recent_values[-1] - recent_values[0], "+.2f")
        regime_band = _html.escape(str(nested_details.get("regime_band") or "Unknown"))
        regime_color = _html.escape(str(nested_details.get("regime_color") or "#9bb"))
        regime_note = _html.escape(str(nested_details.get("regime_note") or ""))
        loadings = nested_details.get("pc1_loadings") if isinstance(nested_details.get("pc1_loadings"), dict) else {}
        loading_rows = "".join(
            (
                "<tr>"
                f"<td><b>{_html.escape(str(name))}</b></td>"
                f"<td>{format_metric_dialog_value(val, '+.3f')}</td>"
                "</tr>"
            )
            for name, val in list(loadings.items())[:5]
        )

        return f"""
        <h2 style='margin-bottom:4px;'>PCA-IV — Surface Factor Signal</h2>
        <p style='color:#9bb;'>Producer: <code>TradovS14_PCASignals</code> &nbsp;·&nbsp;
        Publisher: <code>TradovS07_CustomMetricsOrchestrator</code> &nbsp;·&nbsp;
        Panel: <code>Custom Metrics</code></p>
        <p style='margin:8px 0 14px 0; padding:8px 10px; background:#10171d; border-left:3px solid #4db6ff;'>
        <b>Operator takeaway</b>: {takeaway}</p>

        <h3>How to read the number</h3>
        <ul>
            <li><b>Positive</b> — the dominant IV surface factor is leaning toward stress expansion.</li>
            <li><b>Negative</b> — the surface is leaning toward compression and normalization.</li>
            <li><b>Near zero</b> — the surface factor is active but not strongly directional.</li>
            <li><b>Rough strength guide</b> — around <code>±0.35</code> is a mild lean; around <code>±0.75</code> is a stronger expansion / compression regime.</li>
        </ul>

        <h3>Live state</h3>
        <table cellpadding='4' style='font-size:12px;'>
            <tr><td><b>Status</b></td><td>{status}</td></tr>
            <tr><td><b>Composite signal</b></td><td>{value}</td></tr>
            <tr><td><b>Day-over-day change</b></td><td>{change}</td></tr>
            <tr><td><b>Explained variance (PC1)</b></td><td>{explained_variance}</td></tr>
            <tr><td><b>Spectral gap</b></td><td>{spectral_gap}</td></tr>
            <tr><td><b>Dispersion score |PC2|</b></td><td>{dispersion_score}</td></tr>
            <tr><td><b>Confidence</b></td><td>{confidence}</td></tr>
            <tr><td><b>Widget quality</b></td><td>{quality}</td></tr>
            <tr><td><b>Surface rows used</b></td><td>{row_count}</td></tr>
            <tr><td><b>Phase</b></td><td>{phase}</td></tr>
            <tr><td><b>Source</b></td><td>{source}</td></tr>
            <tr><td><b>Timestamp</b></td><td>{timestamp}</td></tr>
        </table>

        <h3>Surface decomposition</h3>
        <table cellpadding='4' style='font-size:12px;'>
            <tr><td><b>Raw PC1 score</b></td><td>{pc1_score}</td></tr>
            <tr><td><b>Absolute PC2 score</b></td><td>{pc2_abs}</td></tr>
            <tr><td><b>Current IV level feature</b></td><td>{feature_level}</td></tr>
            <tr><td><b>Current skew feature</b></td><td>{feature_skew}</td></tr>
            <tr><td><b>Current convexity feature</b></td><td>{feature_convexity}</td></tr>
        </table>

        <h3>Dominant loadings</h3>
        <table cellpadding='4' style='font-size:12px;'>
            {loading_rows}
        </table>

        <h3>Recent history</h3>
        <p><b>Regime band</b>: <span style='color:{regime_color}; font-weight:600;'>{regime_band}</span></p>
        <p style='font-family:monospace; font-size:24px; letter-spacing:1px; margin:6px 0 4px 0;'>{sparkline}</p>
        <p style='color:#9bb;'>Last {recent_window} surface snapshots · Net drift {recent_drift}</p>
        <p>{regime_note}</p>

        <h3>History seeding</h3>
        <table cellpadding='4' style='font-size:12px;'>
            <tr><td><b>Stored snapshots</b></td><td>{stored_snapshots}</td></tr>
            <tr><td><b>Live threshold</b></td><td>{min_live_snapshots}</td></tr>
            <tr><td><b>Initial burn-in target</b></td><td>{target_snapshots}</td></tr>
            <tr><td><b>Readiness progress</b></td><td>{readiness_progress}</td></tr>
            <tr><td><b>First snapshot</b></td><td>{first_snapshot_ts}</td></tr>
            <tr><td><b>Latest snapshot</b></td><td>{last_snapshot_ts}</td></tr>
            <tr><td><b>Storage path</b></td><td>{history_path}</td></tr>
        </table>
        <p style='font-size:11px;'><b>PCA-ready feature set</b>: {feature_text}</p>

        <hr/>
        <h3>How it works</h3>
        <ol>
            <li><b>Input matrix</b> — each row is a persisted TRAD IV-surface feature snapshot derived from the live term-structure path in S07/N06.</li>
            <li><b>Feature family</b> — level, front/back curve, butterfly, term twist, skew, and convexity are standardized before PCA.</li>
            <li><b>Orientation</b> — PC1 is sign-anchored to the level feature, so positive readings align with higher-volatility surface stress and negative readings align with compression.</li>
            <li><b>Displayed value</b> — the dashboard shows the latest PC1 score scaled by <code>(0.5 + explained variance)</code>.</li>
        </ol>
        """

    return f"""
    <h2 style='margin-bottom:4px;'>PCA-IV — Placeholder Signal</h2>
    <p style='color:#9bb;'>Producer: <code>TradovS14_PCASignals</code> &nbsp;·&nbsp;
                    "🟡 Establishing live connections",
                    "⏳ ENTRY gate remains blocked until 09:35 ET",
    <p style='margin:8px 0 14px 0; padding:8px 10px; background:#10171d; border-left:3px solid #4db6ff;'>
    <b>Operator takeaway</b>: {takeaway}</p>

    <h3>How to read the states</h3>
    <ul>
        <li><b>PEND</b> — PCA-IV is staged but not live yet.</li>
        <li><b>SEED</b> — history is accumulating and the factor is warming up.</li>
        <li><b>HOLD</b> — live computation temporarily fell back for the current cycle.</li>
        <li><b>When live</b> — positive means stress expansion; negative means compression and normalization.</li>
    </ul>

    <h3>Current state</h3>
    <p><b style='color:#f2b134'>PEND</b> — this row is intentionally a placeholder while IV-surface PCA infrastructure is staged.</p>
    <table cellpadding='4' style='font-size:12px;'>
        <tr><td><b>Status</b></td><td>{status}</td></tr>
        <tr><td><b>Phase</b></td><td>{phase}</td></tr>
        <tr><td><b>Target surface</b></td><td>{target_surface}</td></tr>
        <tr><td><b>Source</b></td><td>{source}</td></tr>
        <tr><td><b>Confidence</b></td><td>{confidence}</td></tr>
        <tr><td><b>Widget quality</b></td><td>{quality}</td></tr>
        <tr><td><b>Timestamp</b></td><td>{timestamp}</td></tr>
    </table>

    <h3>Placeholder note</h3>
    <p>{message}</p>

    <h3>History seeding</h3>
    <table cellpadding='4' style='font-size:12px;'>
        <tr><td><b>Stored snapshots</b></td><td>{stored_snapshots}</td></tr>
        <tr><td><b>Live threshold</b></td><td>{min_live_snapshots}</td></tr>
        <tr><td><b>Initial burn-in target</b></td><td>{target_snapshots}</td></tr>
        <tr><td><b>Readiness progress</b></td><td>{readiness_progress}</td></tr>
        <tr><td><b>First snapshot</b></td><td>{first_snapshot_ts}</td></tr>
        <tr><td><b>Latest snapshot</b></td><td>{last_snapshot_ts}</td></tr>
        <tr><td><b>Storage path</b></td><td>{history_path}</td></tr>
    </table>
    <p style='font-size:11px;'><b>PCA-ready feature set</b>: {feature_text}</p>

    <hr/>
    <h3>Planned shape</h3>
    <ol>
        <li><b>Input matrix</b> — a rolling TRAD implied-volatility surface organized by moneyness and days-to-expiry.</li>
        <li><b>PCA factors</b> — expected factor families are level, skew, convexity, and term-structure deformation.</li>
        <li><b>Why deferred</b> — this needs reliable persisted surface history, not just a short in-memory snapshot window.</li>
        <li><b>Dashboard contract</b> — the row already exists so the eventual live signal can plug into the current Custom Metrics pipeline without another UI change.</li>
    </ol>
    """
