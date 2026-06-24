#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG36_StripMetricsPresenter.py
Purpose: Pure presentation helpers for IV and portfolio Greek strip labels
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class StripLabelPresentation:
    """Preformatted text and style for a strip label."""

    text: str
    style: str


@dataclass(frozen=True)
class PortfolioGreekStripPresentations:
    """Preformatted text and styles for portfolio Greek strip labels."""

    delta: StripLabelPresentation
    gamma: StripLabelPresentation
    theta: StripLabelPresentation
    vega: StripLabelPresentation
    charm_text: str
    vanna_text: str


def _build_style(color: str) -> str:
    return f"color: {color}; font-size: 11px;"


def build_atm_iv_label_presentation(atm_iv: Any, colors: Mapping[str, str]) -> StripLabelPresentation:
    """Build the ATM IV strip label presentation."""
    neutral = colors["text"]
    warning = colors.get("warning", neutral)
    if isinstance(atm_iv, (int, float)):
        iv_pct = atm_iv * 100
        color = colors["negative"] if iv_pct >= 50 else (warning if iv_pct >= 30 else neutral)
        return StripLabelPresentation(
            text=f"ATM IV  {iv_pct:.1f}%",
            style=_build_style(color),
        )
    return StripLabelPresentation(text="ATM IV  —", style=_build_style(neutral))


def build_iv_rank_label_presentation(iv_rank: Any, colors: Mapping[str, str]) -> StripLabelPresentation:
    """Build the IV Rank strip label presentation."""
    neutral = colors["text"]
    warning = colors.get("warning", neutral)
    if isinstance(iv_rank, (int, float)):
        color = colors["negative"] if iv_rank >= 75 else (warning if iv_rank >= 25 else colors["positive"])
        return StripLabelPresentation(
            text=f"IVR  {iv_rank:.0f}",
            style=_build_style(color),
        )
    return StripLabelPresentation(text="IVR  —", style=_build_style(neutral))


def build_portfolio_greek_strip_presentations(
    greeks: Mapping[str, Any] | None,
    colors: Mapping[str, str],
) -> PortfolioGreekStripPresentations:
    """Build the portfolio Greek strip presentations."""
    greeks = greeks or {}
    neutral = colors["text"]
    warning = colors.get("warning", neutral)
    positive = colors["positive"]
    negative = colors["negative"]

    delta = greeks.get("delta")
    if isinstance(delta, (int, float)):
        delta_color = negative if abs(delta) >= 60 else (warning if abs(delta) >= 30 else neutral)
        delta_presentation = StripLabelPresentation(f"Δ  {delta:+,.1f}", _build_style(delta_color))
    else:
        delta_presentation = StripLabelPresentation("Δ  —", _build_style(neutral))

    gamma = greeks.get("gamma")
    if isinstance(gamma, (int, float)):
        gamma_color = negative if abs(gamma) >= 0.30 else (warning if abs(gamma) >= 0.15 else neutral)
        gamma_presentation = StripLabelPresentation(f"Γ  {gamma:+,.2f}", _build_style(gamma_color))
    else:
        gamma_presentation = StripLabelPresentation("Γ  —", _build_style(neutral))

    theta = greeks.get("theta")
    if isinstance(theta, (int, float)):
        theta_color = positive if theta > 0 else negative
        theta_presentation = StripLabelPresentation(f"Θ  ${theta:+,.2f}/day", _build_style(theta_color))
    else:
        theta_presentation = StripLabelPresentation("Θ  —", _build_style(neutral))

    vega = greeks.get("vega")
    if isinstance(vega, (int, float)):
        vega_color = negative if vega <= -800 else (warning if vega <= -300 else neutral)
        vega_presentation = StripLabelPresentation(f"V  {vega:+,.1f}", _build_style(vega_color))
    else:
        vega_presentation = StripLabelPresentation("V  —", _build_style(neutral))

    charm = greeks.get("charm")
    vanna = greeks.get("vanna")

    return PortfolioGreekStripPresentations(
        delta=delta_presentation,
        gamma=gamma_presentation,
        theta=theta_presentation,
        vega=vega_presentation,
        charm_text=(f"Chr: {charm:+.3f}" if isinstance(charm, (int, float)) else "Chr: —"),
        vanna_text=(f"Van: {vanna:+.3f}" if isinstance(vanna, (int, float)) else "Van: —"),
    )
