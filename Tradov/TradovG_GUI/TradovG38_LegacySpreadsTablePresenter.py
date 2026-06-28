#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG38_LegacySpreadsTablePresenter.py
Purpose: Pure presentation helpers for the legacy spreads table rows
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class LegacySpreadsTableRow:
    """Preformatted row values and MTM color for the legacy spreads table."""

    cells: tuple[str, ...]
    mtm_color: str


def build_legacy_spreads_table_rows(
    spreads_detail: Sequence[Mapping[str, Any]] | None,
    colors: Mapping[str, str],
) -> Sequence[LegacySpreadsTableRow]:
    """Build legacy spreads-table row values from paper spread details."""
    rows: list[LegacySpreadsTableRow] = []
    for spread in spreads_detail or []:
        if not isinstance(spread, Mapping):
            continue
        try:
            mtm_pnl = float(spread.get("mtm_pnl", 0.0) or 0.0)
        except (TypeError, ValueError):
            mtm_pnl = 0.0

        rows.append(
            LegacySpreadsTableRow(
                cells=(
                    str(spread.get("id", "")),
                    str(spread.get("expiration", "")),
                    f"{spread.get('short_strike', 0):.0f}/{spread.get('long_strike', 0):.0f}",
                    str(spread.get("qty", 0)),
                    f"${spread.get('credit', 0.0):.2f}",
                    f"${spread.get('debit', 0.0):.2f}",
                    f"${mtm_pnl:+,.2f}",
                ),
                mtm_color=colors["positive"] if mtm_pnl >= 0 else colors["negative"],
            )
        )
    return rows
