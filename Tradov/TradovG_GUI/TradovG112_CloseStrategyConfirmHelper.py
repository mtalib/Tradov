#!/usr/bin/env python3
"""Pure confirmation dialog planning for close-strategy UX."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloseStrategyConfirmPlan:
    """Static dialog copy and styling for strategy-close confirmation."""

    title: str
    text: str
    yes_button_text: str
    yes_button_style: str
    cancel_button_style: str
    dialog_style: str


def build_close_strategy_confirm_plan(
    *,
    strategy_data: dict[str, object],
    colors: dict[str, str],
) -> CloseStrategyConfirmPlan:
    """Return the confirmation dialog copy and styles for closing a strategy."""
    leg_count = len(strategy_data["legs"])
    return CloseStrategyConfirmPlan(
        title="Close Strategy",
        text=(
            "⚠️  CLOSE ENTIRE STRATEGY?\n\n"
            f"Strategy:     {strategy_data['strategy']}\n"
            f"Entry Time:   {strategy_data['timestamp']}\n"
            f"DTE:          {strategy_data['dte']} days\n"
            f"Legs:         {leg_count} positions\n"
            f"Net P&L:      {strategy_data['net_pnl']} ({strategy_data['pct_return']})\n"
            f"Status:       {strategy_data['status']}\n\n"
            f"This will close ALL {leg_count} legs with MARKET ORDERS."
        ),
        yes_button_text="CLOSE ALL POSITIONS",
        yes_button_style=(
            f"background-color: {colors['negative']}; color: white; padding: 5px 15px;"
        ),
        cancel_button_style=(
            f"background-color: {colors['panel']}; color: white; padding: 5px 15px;"
        ),
        dialog_style=(
            "\n            QMessageBox {\n"
            f"                background-color: {colors['panel']};\n"
            f"                color: {colors['text']};\n"
            "            }\n"
            "            QLabel {\n"
            f"                color: {colors['text']};\n"
            "                font-family: monospace;\n"
            "                font-size: 12px;\n"
            "            }\n"
            "        "
        ),
    )
