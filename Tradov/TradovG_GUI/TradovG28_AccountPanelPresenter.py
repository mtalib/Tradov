#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG28_AccountPanelPresenter.py
Purpose: Pure helpers for account-panel money and P&L presentation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping


@dataclass(frozen=True)
class PnlLabelPresentation:
    """Formatted text and style for a signed P&L account label."""

    text: str
    style: str


@dataclass(frozen=True)
class AccountSnapshotPresentation:
    """Preformatted account snapshot values for dashboard labels."""

    settled_text: str
    buying_text: str
    realized: PnlLabelPresentation
    unrealized: PnlLabelPresentation


def parse_money_text(text: str) -> float:
    """Parse dashboard money labels like '$100,024.40' or '$+0.00'."""
    try:
        cleaned = str(text or "").strip().replace("$", "").replace(",", "")
        return float(cleaned) if cleaned not in {"", "—"} else 0.0
    except (TypeError, ValueError):
        return 0.0


def format_account_money_text(value: float) -> str:
    """Format an unsigned account money value."""
    return f"${float(value):,.2f}"


def build_account_pnl_presentation(
    value: float,
    colors: Mapping[str, str],
) -> PnlLabelPresentation:
    """Build the signed P&L text and stylesheet for an account label."""
    pnl_value = float(value)
    color = colors["positive"] if pnl_value >= 0 else colors["negative"]
    return PnlLabelPresentation(
        text=f"${pnl_value:+,.2f}",
        style=(
            f"padding: 2px 5px; background-color: {colors['background']}; "
            f"border: 1px solid {colors['border']}; font-size: 12px; color: {color}; text-align: right;"
        ),
    )


def capture_account_snapshot_from_texts(
    *,
    settled_text: str,
    buying_text: str,
    realized_text: str,
    unrealized_text: str,
) -> dict[str, float]:
    """Capture normalized numeric account snapshot values from label texts."""
    return {
        "settled_cash": parse_money_text(settled_text),
        "buying_power": parse_money_text(buying_text),
        "realized_pnl": parse_money_text(realized_text),
        "unrealized_pnl": parse_money_text(unrealized_text),
    }


def build_account_snapshot_presentation(
    snapshot: Mapping[str, Any],
    colors: Mapping[str, str],
) -> AccountSnapshotPresentation:
    """Build preformatted account-panel values from a numeric snapshot payload."""
    settled = float(snapshot.get("settled_cash", 0.0) or 0.0)
    buying = float(snapshot.get("buying_power", 0.0) or 0.0)
    realized = float(snapshot.get("realized_pnl", 0.0) or 0.0)
    unrealized = float(snapshot.get("unrealized_pnl", 0.0) or 0.0)

    return AccountSnapshotPresentation(
        settled_text=format_account_money_text(settled),
        buying_text=format_account_money_text(buying),
        realized=build_account_pnl_presentation(realized, colors),
        unrealized=build_account_pnl_presentation(unrealized, colors),
    )
