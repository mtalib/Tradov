#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG26_RecentTradeFormatter.py
Purpose: Pure helpers for recent trade display formatting
"""

from __future__ import annotations

import html
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


@dataclass(frozen=True)
class PairTradeHistoryDisplay:
    """Preformatted pair-trade history values for dashboard rendering."""

    closed_text: str
    pair_text: str
    side_text: str
    qty_a_text: str
    qty_b_text: str
    entry_z_text: str
    close_z_text: str
    realized_pnl_text: str
    duration_text: str
    realized_pnl_value: float


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


def build_pair_trade_history_display(
    trade: dict[str, Any],
    *,
    pair_placeholder: str = "—",
) -> PairTradeHistoryDisplay:
    """Normalize a raw pair-trade record into display-ready table values."""
    closed_text = _format_recent_trade_timestamp(
        str(
            trade.get("closed_at")
            or trade.get("timestamp")
            or trade.get("exit_time")
            or ""
        )
    )
    pair_text = _build_pair_trade_label(trade, pair_placeholder=pair_placeholder)
    side_text = _build_pair_trade_side_label(trade)
    qty_a = abs(_coerce_int(trade.get("quantity_a", trade.get("qty_a", trade.get("quantity", 0))), 0))
    qty_b = abs(_coerce_int(trade.get("quantity_b", trade.get("qty_b", trade.get("quantity", 0))), 0))
    entry_z = _coerce_float(trade.get("entry_z"), None)
    close_z = _coerce_float(trade.get("close_z", trade.get("exit_z", trade.get("current_z"))), None)
    realized_pnl = _coerce_float(trade.get("realized_pnl", trade.get("pnl", 0.0)), 0.0)
    duration_seconds = _coerce_float(
        trade.get("duration_seconds", trade.get("hold_seconds", trade.get("duration"))),
        None,
    )
    if duration_seconds is None and trade.get("entry_time") and trade.get("exit_time"):
        try:
            opened = datetime.fromisoformat(str(trade["entry_time"]).replace("Z", "+00:00"))
            closed = datetime.fromisoformat(str(trade["exit_time"]).replace("Z", "+00:00"))
            duration_seconds = max(0.0, (closed - opened).total_seconds())
        except ValueError:
            duration_seconds = None

    return PairTradeHistoryDisplay(
        closed_text=closed_text,
        pair_text=pair_text,
        side_text=side_text,
        qty_a_text=str(qty_a) if qty_a else "—",
        qty_b_text=str(qty_b) if qty_b else "—",
        entry_z_text=f"{entry_z:.2f}" if entry_z is not None else "—",
        close_z_text=f"{close_z:.2f}" if close_z is not None else "—",
        realized_pnl_text=f"${realized_pnl:+,.2f}",
        duration_text=_format_duration_seconds(duration_seconds),
        realized_pnl_value=realized_pnl,
    )


def build_pair_trade_banner_html(
    display: PairTradeHistoryDisplay,
    *,
    colors: dict[str, str] | None = None,
    pair_placeholder: str = "—",
) -> str:
    """Build a rich-text banner for one pair-trade history row."""
    palette = colors or {}
    text_color = palette.get("text", "#ffffff")
    dim_color = palette.get("text_dim", "#a8a8a8")
    positive = palette.get("positive", "#00ff88")
    negative = palette.get("negative", "#ff4444")

    pair_html = build_recent_trade_symbol_html(
        display.pair_text,
        side=display.side_text,
        colors=palette,
        symbol_placeholder=pair_placeholder,
    )

    return (
        f"<span style='color:{dim_color};'>CLOSED | {html.escape(display.closed_text)} | </span>"
        f"{pair_html}"
        f"<span style='color:{dim_color};'> | </span>"
        f"<span style='color:{text_color};'>{html.escape(display.side_text)}</span>"
        f"<span style='color:{dim_color};'> | QTY: </span>"
        f"<span style='color:{text_color};'>A {html.escape(display.qty_a_text)} / B {html.escape(display.qty_b_text)}</span>"
        f"<span style='color:{dim_color};'> | Z: </span>"
        f"<span style='color:{text_color};'>{html.escape(display.entry_z_text)} -&gt; {html.escape(display.close_z_text)}</span>"
        f"<span style='color:{dim_color};'> | P&amp;L: </span>"
        f"<span style='color:{positive if display.realized_pnl_value >= 0 else negative};'>"
        f"{html.escape(display.realized_pnl_text)}</span>"
    )


def build_recent_trade_banner_text(display: RecentTradeDisplay) -> str:
    """Build the single-line recent-trade banner used in the positions tree."""
    return (
        f"RECENT TRADE | {display.timestamp_text} | {display.symbol} | {display.action} | "
        f"QTY: {display.quantity_text} | PRICE: {display.price_text} | "
        f"P&L: {display.realized_pnl_text}"
    )


def build_recent_trade_banner_html(
    display: RecentTradeDisplay,
    *,
    side: str = "",
    colors: dict[str, str] | None = None,
    symbol_placeholder: str = "-",
) -> str:
    """Build a rich-text recent-trade banner with paired-symbol coloring when possible."""
    palette = colors or {}
    text_color = palette.get("text", "#ffffff")
    dim_color = palette.get("text_dim", "#a8a8a8")
    positive = palette.get("positive", "#00ff88")
    negative = palette.get("negative", "#ff4444")

    symbol_html = build_recent_trade_symbol_html(
        display.symbol,
        side=side,
        colors=palette,
        symbol_placeholder=symbol_placeholder,
    )

    return (
        f"<span style='color:{dim_color};'>RECENT TRADE | {html.escape(display.timestamp_text)} | </span>"
        f"{symbol_html}"
        f"<span style='color:{dim_color};'> | </span>"
        f"<span style='color:{text_color};'>{html.escape(display.action)}</span>"
        f"<span style='color:{dim_color};'> | QTY: </span>"
        f"<span style='color:{text_color};'>{html.escape(display.quantity_text)}</span>"
        f"<span style='color:{dim_color};'> | PRICE: </span>"
        f"<span style='color:{text_color};'>{html.escape(display.price_text)}</span>"
        f"<span style='color:{dim_color};'> | P&amp;L: </span>"
        f"<span style='color:{positive if display.realized_pnl_value >= 0 else negative};'>"
        f"{html.escape(display.realized_pnl_text)}</span>"
    )


def build_recent_trade_symbol_html(
    symbol: str,
    *,
    side: str = "",
    colors: dict[str, str] | None = None,
    symbol_placeholder: str = "-",
) -> str:
    """Render a recent-trade symbol, colorizing paired symbols when a separator is present."""
    palette = colors or {}
    positive = palette.get("positive", "#00ff88")
    negative = palette.get("negative", "#ff4444")
    text = str(symbol or "").strip() or symbol_placeholder

    pair = _split_pair_symbol(text)
    if pair is None:
        return f"<span style='color:{palette.get('text', '#ffffff')};'>{html.escape(text)}</span>"

    is_negative_side = _is_negative_trade_side(side)
    first_color = negative if is_negative_side else positive
    second_color = positive if is_negative_side else negative

    first_symbol, second_symbol = pair
    return (
        f"<span style='color:{first_color}; font-weight:600;'>{html.escape(first_symbol)}</span>"
        f"<span style='color:{palette.get('text_dim', '#a8a8a8')};'> / </span>"
        f"<span style='color:{second_color}; font-weight:600;'>{html.escape(second_symbol)}</span>"
    )


def _build_pair_trade_label(trade: dict[str, Any], *, pair_placeholder: str) -> str:
    pair_key = str(trade.get("pair_key") or "").strip()
    if pair_key:
        return pair_key

    symbol_a = str(trade.get("symbol_a") or "").strip()
    symbol_b = str(trade.get("symbol_b") or "").strip()
    if symbol_a and symbol_b:
        return f"{symbol_a} / {symbol_b}"

    symbol = str(trade.get("symbol") or "").strip()
    if symbol:
        return symbol

    return pair_placeholder


def _build_pair_trade_side_label(trade: dict[str, Any]) -> str:
    pair_side = str(trade.get("pair_side") or "").strip().lower()
    if pair_side == "short_long":
        return "NEGATIVE"
    if pair_side == "long_short":
        return "POSITIVE"

    side = str(trade.get("side") or trade.get("action") or trade.get("direction") or "").strip().lower()
    if side.startswith(("sell", "short")):
        return "NEGATIVE"
    if side.startswith(("buy", "long")):
        return "POSITIVE"
    return "—"


def _format_duration_seconds(duration_seconds: float | None) -> str:
    if duration_seconds is None:
        return "—"

    total_seconds = max(0, int(duration_seconds))
    days, remainder = divmod(total_seconds, 24 * 3600)
    hours, remainder = divmod(remainder, 3600)
    minutes, _seconds = divmod(remainder, 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    if minutes > 0:
        return f"{minutes}m"
    return f"{total_seconds}s"


def _is_negative_trade_side(side: str) -> bool:
    normalized = str(side or "").strip().lower()
    return normalized in {"sell", "sell_short", "short", "sto", "stc"} or normalized.startswith(("sell", "short"))


def _split_pair_symbol(symbol: str) -> tuple[str, str] | None:
    text = str(symbol or "").strip()
    if not text:
        return None

    for separator in (" / ", "/", " | ", "|", " :: ", "::"):
        if separator in text:
            left, right = text.split(separator, 1)
            left = left.strip()
            right = right.strip()
            if left and right:
                return left, right
    return None


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
