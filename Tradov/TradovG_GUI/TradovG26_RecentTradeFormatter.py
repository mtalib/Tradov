#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG26_RecentTradeFormatter.py
Purpose: Pure helpers for recent trade display formatting
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo


_EASTERN_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RecentTradeDisplay:
    """Preformatted recent-trade values for dashboard rendering."""

    timestamp_text: str
    symbol: str
    action: str
    quantity_text: str
    price_text: str
    cost_text: str
    realized_pnl_text: str
    realized_pnl_value: float

    def as_table_values(self) -> list[str]:
        """Return the ordered values used by the recent-trades dialog table."""
        return [
            self.timestamp_text,
            self.symbol,
            self.action,
            self.quantity_text,
            self.price_text,
            self.cost_text,
            self.realized_pnl_text,
        ]


def build_recent_trade_display(
    trade: dict[str, Any],
    *,
    symbol_placeholder: str = "-",
) -> RecentTradeDisplay:
    """Normalize a raw trade dict into preformatted dashboard display values."""
    raw_ts = str(trade.get("timestamp", "") or "")
    trade_type = str(trade.get("trade_type", "") or "").upper()
    side = str(trade.get("side", "") or "").upper()
    realized_pnl = _coerce_float(trade.get("realized_pnl", 0.0), 0.0)
    has_cost_basis = trade.get("cost_basis") not in (None, "")
    cost_basis = _coerce_float(trade.get("cost_basis", 0.0), 0.0)

    return RecentTradeDisplay(
        timestamp_text=_format_recent_trade_timestamp(raw_ts),
        symbol=str(trade.get("symbol", symbol_placeholder) or symbol_placeholder),
        action=trade_type or side or "TRADE",
        quantity_text=str(int(_coerce_float(trade.get("quantity", 0), 0.0))),
        price_text=f"${_coerce_float(trade.get('price', 0.0), 0.0):,.2f}",
        cost_text=(f"${cost_basis:+,.2f}" if has_cost_basis else "—"),
        realized_pnl_text=f"${realized_pnl:+,.2f}",
        realized_pnl_value=realized_pnl,
    )


def build_recent_trade_banner_text(display: RecentTradeDisplay) -> str:
    """Build the single-line recent-trade banner used in the positions tree."""
    return (
        f"RECENT TRADE | {display.timestamp_text} | {display.symbol} | {display.action} | "
        f"QTY: {display.quantity_text} | PRICE: {display.price_text} | "
        f"P&L: {display.realized_pnl_text}"
    )


def _format_recent_trade_timestamp(raw_timestamp: str) -> str:
    normalized = str(raw_timestamp or "").strip()
    if not normalized:
        return "--"

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            # H05 stores UTC trade timestamps; older rows may be missing the offset.
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(_EASTERN_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return normalized[:19].replace("T", " ") if normalized else "--"


def _coerce_float(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
