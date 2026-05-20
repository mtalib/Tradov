#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG35_PaperSummaryPresenter.py
Purpose: Pure presentation helpers for paper summary badges and portfolio rows
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from Spyder.SpyderG_GUI.SpyderG34_AccountCapitalMath import BuyingPowerUsage


@dataclass(frozen=True)
class SummaryBadgePresentation:
    """Preformatted text and style for a small summary badge label."""

    text: str
    style: str


@dataclass(frozen=True)
class PortfolioSummaryRow:
    """A preformatted row for the portfolio summary dialog."""

    text: str
    color: str
    explanation: str
    legend: str


def _warning_color(colors: Mapping[str, str]) -> str:
    return colors.get("warning", colors["text"])


def _signed_color(value: float, colors: Mapping[str, str]) -> str:
    return colors["positive"] if value >= 0 else colors["negative"]


def _bp_color(percent: float, colors: Mapping[str, str]) -> str:
    if percent >= 80:
        return colors["negative"]
    if percent >= 50:
        return _warning_color(colors)
    return colors["positive"]


def _build_style(color: str) -> str:
    return f"color: {color}; font-size: 11px;"


def build_spreads_summary_badge_presentation(
    open_count: int,
    spreads_mtm: float,
    colors: Mapping[str, str],
) -> SummaryBadgePresentation:
    """Build the spreads summary badge shown in the paper summary strip."""
    return SummaryBadgePresentation(
        text=f"OPEN  {open_count}   MTM  ${float(spreads_mtm):+,.2f}",
        style=_build_style(_signed_color(float(spreads_mtm), colors)),
    )


def build_realized_today_badge_presentation(
    realized: float,
    colors: Mapping[str, str],
) -> SummaryBadgePresentation:
    """Build the realized-today badge for the paper summary strip."""
    realized_value = float(realized)
    return SummaryBadgePresentation(
        text=f"REALIZED  ${realized_value:+,.2f}",
        style=_build_style(_signed_color(realized_value, colors)),
    )


def build_buying_power_badge_presentation(
    bp_usage: BuyingPowerUsage,
    colors: Mapping[str, str],
) -> SummaryBadgePresentation:
    """Build the buying-power badge for the paper summary strip."""
    return SummaryBadgePresentation(
        text=(
            f"BP  ${bp_usage.used:,.0f} / ${bp_usage.capital:,.0f}  ({bp_usage.percent:.0f}%)"
        ),
        style=_build_style(_bp_color(bp_usage.percent, colors)),
    )


def build_portfolio_summary_rows(
    *,
    open_count: int,
    spreads_mtm: float,
    realized: float,
    atm_iv_raw: Any,
    iv_rank: Any,
    greeks: Mapping[str, Any] | None,
    bp_usage: BuyingPowerUsage,
    colors: Mapping[str, str],
) -> Sequence[PortfolioSummaryRow]:
    """Build the text, color, and descriptions for the portfolio summary dialog."""
    greeks = greeks or {}
    delta = greeks.get("delta")
    gamma = greeks.get("gamma")
    theta = greeks.get("theta")
    vega = greeks.get("vega")
    neutral = colors["text"]
    warning = _warning_color(colors)
    atm_iv_pct = atm_iv_raw * 100 if isinstance(atm_iv_raw, (int, float)) else None

    def iv_color(value: float) -> str:
        return colors["negative"] if value >= 50 else (warning if value >= 30 else neutral)

    def ivr_color(value: float) -> str:
        return colors["negative"] if value >= 75 else (warning if value >= 25 else colors["positive"])

    def delta_color(value: float) -> str:
        return colors["negative"] if abs(value) >= 60 else (warning if abs(value) >= 30 else neutral)

    def gamma_color(value: float) -> str:
        return colors["negative"] if abs(value) >= 0.30 else (warning if abs(value) >= 0.15 else neutral)

    def theta_color(value: float) -> str:
        return colors["positive"] if value > 0 else colors["negative"]

    def vega_color(value: float) -> str:
        return colors["negative"] if value <= -800 else (warning if value <= -300 else neutral)

    return [
        PortfolioSummaryRow(
            text=f"OPEN  {open_count}",
            color=neutral,
            explanation="Number of active open positions",
            legend="—",
        ),
        PortfolioSummaryRow(
            text=f"MTM  ${float(spreads_mtm):+,.2f}",
            color=_signed_color(float(spreads_mtm), colors),
            explanation="Mark-to-market unrealised P&L across all open legs",
            legend="Green +ve / Red -ve",
        ),
        PortfolioSummaryRow(
            text=f"REALIZED  ${float(realized):+,.2f}",
            color=_signed_color(float(realized), colors),
            explanation="Closed trade P&L for today's session",
            legend="Green +ve / Red -ve",
        ),
        PortfolioSummaryRow(
            text=f"ATM IV  {atm_iv_pct:.1f}%" if atm_iv_pct is not None else "ATM IV  —",
            color=iv_color(atm_iv_pct) if atm_iv_pct is not None else neutral,
            explanation="At-the-money implied volatility of SPY options",
            legend="White <30%  │  Amber ≥30%  │  Red ≥50%",
        ),
        PortfolioSummaryRow(
            text=f"IVR  {iv_rank:.0f}" if isinstance(iv_rank, (int, float)) else "IVR  —",
            color=ivr_color(iv_rank) if isinstance(iv_rank, (int, float)) else neutral,
            explanation="IV Rank — where current IV sits vs. the past year (0–100)",
            legend="Green <25  │  Amber 25–74  │  Red ≥75",
        ),
        PortfolioSummaryRow(
            text=f"Δ DELTA  {delta:+,.1f}" if isinstance(delta, (int, float)) else "Δ DELTA  —",
            color=delta_color(delta) if isinstance(delta, (int, float)) else neutral,
            explanation="Portfolio net delta: directional exposure per $1 SPY move",
            legend="White |Δ|<30  │  Amber |Δ|≥30  │  Red |Δ|≥60",
        ),
        PortfolioSummaryRow(
            text=f"Γ GAMMA  {gamma:+,.3f}" if isinstance(gamma, (int, float)) else "Γ GAMMA  —",
            color=gamma_color(gamma) if isinstance(gamma, (int, float)) else neutral,
            explanation="Portfolio net gamma: rate of delta change per $1 move",
            legend="White <0.15  │  Amber ≥0.15  │  Red ≥0.30",
        ),
        PortfolioSummaryRow(
            text=f"Θ THETA  ${theta:+,.2f}/day" if isinstance(theta, (int, float)) else "Θ THETA  —",
            color=theta_color(theta) if isinstance(theta, (int, float)) else neutral,
            explanation="Daily time decay earned (premium sellers receive positive theta)",
            legend="Green >0 (earning)  │  Red <0 (paying)",
        ),
        PortfolioSummaryRow(
            text=f"V VEGA  {vega:+,.1f}" if isinstance(vega, (int, float)) else "V VEGA  —",
            color=vega_color(vega) if isinstance(vega, (int, float)) else neutral,
            explanation="Portfolio vega: P&L impact per 1-point rise in implied volatility",
            legend="White ≥−300  │  Amber ≤−300  │  Red ≤−800",
        ),
        PortfolioSummaryRow(
            text=(
                f"BP USED  {bp_usage.percent:.0f}%  (${bp_usage.used:,.0f} / ${bp_usage.capital:,.0f})"
            ),
            color=_bp_color(bp_usage.percent, colors),
            explanation="Buying power consumed as a % of total paper capital",
            legend="Green <50%  │  Amber 50–80%  │  Red ≥80%",
        ),
    ]
