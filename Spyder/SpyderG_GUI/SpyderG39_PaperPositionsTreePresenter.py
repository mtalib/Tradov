#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG39_PaperPositionsTreePresenter.py
Purpose: Pure presentation helpers for paper positions tree rows
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as dt_date, datetime, tzinfo
from typing import Any
from collections.abc import Mapping, Sequence


@dataclass(frozen=True)
class RestoredPaperPositionPresentation:
    """Preformatted texts and colors for a restored paper position row pair."""

    summary_text: str
    action_text: str
    action_color: str
    leg_text: str
    strike_text: str
    quantity_text: str
    expiry_text: str
    entry_price_text: str
    cost_text: str
    pnl_text: str
    tooltip_text: str
    quantity_color: str
    cost_color: str
    pnl_color: str


@dataclass(frozen=True)
class RestoredPaperPositionGroupPresentation:
    """Grouped restored-position rows shown under one summary header."""

    summary_text: str
    detail_rows: Sequence[RestoredPaperPositionPresentation]


@dataclass(frozen=True)
class PaperSpreadHeaderPresentation:
    """Preformatted summary header values for a paper spread tree row."""

    timestamp_text: str
    summary_text: str
    pnl_text: str
    pnl_color: str


@dataclass(frozen=True)
class PaperSpreadLegPresentation:
    """Preformatted detail values for a paper spread leg tree row."""

    action_text: str
    action_color: str | None
    leg_text: str
    strike_text: str
    quantity_text: str
    price_text: str
    expiry_text: str
    cost_text: str
    cost_color: str | None
    pnl_text: str
    pnl_color: str | None


def coerce_float(value: Any, default: float | None = None) -> float | None:
    """Convert value to float while treating empty inputs as missing."""
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_int(value: Any, default: int = 0) -> int:
    """Convert value to int while treating empty inputs as missing."""
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def coerce_timestamp(value: Any) -> float | None:
    """Convert a numeric or ISO timestamp into epoch seconds."""
    if value in (None, ""):
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = None

    if numeric_value is not None:
        return numeric_value if numeric_value > 0 else None

    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def format_days_to_expiration(expiration: str, today: dt_date) -> str:
    """Format DTE as a zero-padded day count."""
    if not expiration:
        return "--"

    try:
        yyyy, mm, dd = str(expiration)[:10].split("-")
        return f"{(dt_date(int(yyyy), int(mm), int(dd)) - today).days:02d}"
    except (TypeError, ValueError):
        return "--"


def format_expiration_short(expiration: str) -> str:
    """Format an ISO expiration date as MM/DD when possible."""
    if not expiration:
        return "--"

    parts = str(expiration)[:10].split("-")
    if len(parts) == 3:
        return f"{parts[1]}/{parts[2]}"
    return str(expiration)[:10]


def format_signed_dollars(value: float, decimals: int | None = None) -> str:
    """Format a signed dollar amount with dynamic decimals by default."""
    abs_value = abs(float(value))
    resolved_decimals = decimals
    if resolved_decimals is None:
        resolved_decimals = 0 if abs_value.is_integer() else 2
    return f"{'+' if value >= 0 else '-'}${abs_value:,.{resolved_decimals}f}"


def _occ_option_flag(symbol: str) -> str:
    """Return OCC option flag (C/P) when the symbol looks like an OCC contract."""
    normalized = str(symbol or "").strip().upper()
    if len(normalized) < 16 or not normalized[-15:-9].isdigit():
        return ""
    flag = normalized[-9:-8]
    return flag if flag in {"C", "P"} else ""


def _action_prefix_from_side(raw_side: str) -> str:
    """Normalize persisted side labels into BUY/SELL when possible."""
    normalized = str(raw_side or "").strip().lower()
    if normalized in {"sell", "sell_to_open", "sell_to_close", "sto", "stc", "short"}:
        return "SELL"
    if normalized in {"buy", "buy_to_open", "buy_to_close", "bto", "btc", "long"}:
        return "BUY"
    return ""


def build_restored_position_presentations(
    positions: Sequence[Mapping[str, Any]] | None,
    colors: Mapping[str, str],
) -> Sequence[RestoredPaperPositionPresentation]:
    """Build display-ready restored paper position rows."""
    presentations: list[RestoredPaperPositionPresentation] = []
    for position in positions or []:
        if not isinstance(position, Mapping):
            continue

        symbol = str(position.get("symbol", "—") or "—")
        quantity = coerce_int(position.get("quantity"), 0)
        display_quantity = abs(quantity)
        entry_price = coerce_float(position.get("entry_price"), 0.0) or 0.0
        current_price = coerce_float(position.get("current_price"), None)
        strategy = str(position.get("strategy", "") or "paper_fill")
        status = str(position.get("status", "OPEN") or "OPEN").upper()
        lifecycle_state = str(position.get("lifecycle_state") or "").strip()
        if not lifecycle_state:
            origin = str(position.get("_paper_open_origin") or "").strip()
            if origin == "carryover":
                lifecycle_state = "CARRIED OVER"
            elif origin == "active_session":
                lifecycle_state = "EXECUTING"
            else:
                lifecycle_state = "CARRIED OVER"
        opened_at = str(position.get("opened_at", "") or "")
        opened_text = opened_at[:19].replace("T", " ") if opened_at else "--"
        expiration = str(position.get("expiration", "") or "")
        strike = coerce_float(position.get("strike"), None)
        option_type = str(position.get("option_type", "") or "").upper()[:1] or _occ_option_flag(symbol)
        action_prefix = _action_prefix_from_side(
            str(position.get("side") or position.get("position_side") or "")
        )
        if not action_prefix:
            if quantity < 0:
                action_prefix = "SELL"
            elif quantity > 0:
                action_prefix = "BUY"
        action_suffix = " PUT" if option_type == "P" else " CALL" if option_type == "C" else ""
        action_text = f"{action_prefix}{action_suffix}".strip() or "—"
        action_color = (
            colors["negative"] if action_prefix == "SELL"
            else colors["positive"] if action_prefix == "BUY"
            else colors["text"]
        )
        unrealized_pnl = coerce_float(position.get("unrealized_pnl"), 0.0) or 0.0
        mark_price = current_price if current_price is not None else entry_price
        contract_multiplier = 100.0 if option_type in {"P", "C"} else 1.0
        total_cost = entry_price * quantity * contract_multiplier

        quantity_color = action_color

        presentations.append(
            RestoredPaperPositionPresentation(
                summary_text=(
                    (
                        "ACTIVE PAPER POSITION (CARRIED OVER)"
                        if lifecycle_state == "CARRIED OVER"
                        else f"ACTIVE PAPER POSITION ({lifecycle_state})"
                    )
                    + " : "
                    f"{strategy.replace('_', ' ').upper()}  |  "
                    f"STATUS: {status}  |  OPENED: {opened_text}  |  MARK: ${mark_price:,.2f}"
                ),
                action_text=action_text,
                action_color=action_color,
                leg_text=symbol,
                strike_text=(
                    f"${strike:.0f}{option_type}"
                    if strike is not None and strike > 0
                    else "--"
                ),
                quantity_text=str(display_quantity),
                expiry_text=format_expiration_short(expiration),
                entry_price_text=f"${entry_price:,.2f}",
                cost_text=format_signed_dollars(total_cost),
                pnl_text=f"{'+' if unrealized_pnl >= 0 else '-'}${abs(unrealized_pnl):,.2f}",
                tooltip_text=(
                    f"Symbol: {symbol}\n"
                    f"Action: {action_text}\n"
                    f"Strategy: {strategy}\n"
                    f"Status: {status}\n"
                    f"Opened: {opened_text}\n"
                    f"Average entry: ${entry_price:,.2f}\n"
                    f"Mark: ${mark_price:,.2f}"
                ),
                quantity_color=quantity_color,
                cost_color=colors["positive"] if total_cost >= 0 else colors["negative"],
                pnl_color=colors["positive"] if unrealized_pnl >= 0 else colors["negative"],
            )
        )

    return presentations


def _resolve_restored_position_lifecycle_state(position: Mapping[str, Any]) -> str:
    """Return the display lifecycle label for one restored paper position."""
    lifecycle_state = str(position.get("lifecycle_state") or "").strip()
    if lifecycle_state:
        return lifecycle_state

    origin = str(position.get("_paper_open_origin") or "").strip()
    if origin == "carryover":
        return "CARRIED OVER"
    if origin == "active_session":
        return "EXECUTING"
    return "CARRIED OVER"


def _restored_position_underlying(symbol: str) -> str:
    """Return the OCC underlying when the symbol looks like an option contract."""
    normalized = str(symbol or "").strip().upper()
    if len(normalized) >= 16 and normalized[-15:-9].isdigit():
        return normalized[:-15] or normalized
    return normalized


def build_restored_position_group_presentations(
    positions: Sequence[Mapping[str, Any]] | None,
    colors: Mapping[str, str],
    *,
    cluster_window_seconds: float = 10.0,
) -> Sequence[RestoredPaperPositionGroupPresentation]:
    """Group related restored positions under one summary header when practical."""
    normalized_positions = [position for position in positions or [] if isinstance(position, Mapping)]
    if not normalized_positions:
        return []

    def _cluster_identity(position: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
        symbol = str(position.get("symbol") or "")
        return (
            str(position.get("strategy") or "paper_fill").strip().lower(),
            _resolve_restored_position_lifecycle_state(position),
            str(position.get("status") or "OPEN").strip().upper(),
            str(position.get("expiration") or "").strip(),
            _restored_position_underlying(symbol),
        )

    ordered_positions = sorted(
        normalized_positions,
        key=lambda position: (
            _cluster_identity(position),
            coerce_timestamp(position.get("opened_at"))
            if coerce_timestamp(position.get("opened_at")) is not None
            else float("inf"),
            str(position.get("symbol") or ""),
        ),
    )

    grouped_positions: list[list[Mapping[str, Any]]] = []
    current_group: list[Mapping[str, Any]] = []
    current_identity: tuple[str, str, str, str, str] | None = None
    current_anchor_ts: float | None = None
    safe_window_seconds = max(0.0, float(cluster_window_seconds))

    for position in ordered_positions:
        identity = _cluster_identity(position)
        opened_ts = coerce_timestamp(position.get("opened_at"))
        within_window = (
            current_anchor_ts is not None
            and opened_ts is not None
            and abs(opened_ts - current_anchor_ts) <= safe_window_seconds
        )

        if current_group and identity == current_identity and within_window:
            current_group.append(position)
            continue

        if current_group:
            grouped_positions.append(current_group)

        current_group = [position]
        current_identity = identity
        current_anchor_ts = opened_ts

    if current_group:
        grouped_positions.append(current_group)

    presentations: list[RestoredPaperPositionGroupPresentation] = []
    for group in grouped_positions:
        detail_rows = list(build_restored_position_presentations(group, colors))
        if not detail_rows:
            continue

        if len(group) == 1:
            summary_text = detail_rows[0].summary_text
        else:
            first = group[0]
            lifecycle_state = _resolve_restored_position_lifecycle_state(first)
            strategy = str(first.get("strategy") or "paper_fill").replace("_", " ").upper()
            status = str(first.get("status") or "OPEN").strip().upper()
            opened_at = str(first.get("opened_at") or "").strip()
            opened_text = opened_at[:19].replace("T", " ") if opened_at else "--"
            summary_prefix = (
                "ACTIVE PAPER POSITION (CARRIED OVER)"
                if lifecycle_state == "CARRIED OVER"
                else f"ACTIVE PAPER POSITION ({lifecycle_state})"
            )
            summary_text = (
                f"{summary_prefix} : {strategy}  |  "
                f"STATUS: {status}  |  OPENED: {opened_text}  |  TRADES: {len(group)}"
            )

        presentations.append(
            RestoredPaperPositionGroupPresentation(
                summary_text=summary_text,
                detail_rows=detail_rows,
            )
        )

    return presentations


def build_paper_spread_tree_presentation(
    spread: Mapping[str, Any],
    today: dt_date,
    eastern_timezone: tzinfo,
    colors: Mapping[str, str],
    default_lifecycle_state: str,
    *,
    closed: bool = False,
) -> tuple[PaperSpreadHeaderPresentation, Sequence[PaperSpreadLegPresentation]]:
    """Build display-ready header and leg rows for one paper spread."""
    structure = str(spread.get("structure") or spread.get("type") or "SPREAD").replace("_", " ").upper()
    lifecycle_state = str(spread.get("lifecycle_state") or default_lifecycle_state)
    quantity = coerce_int(spread.get("qty"), 0)
    mtm_pnl = coerce_float(spread.get("mtm_pnl"), None)
    credit = coerce_float(spread.get("credit"), 0.0) or 0.0
    if mtm_pnl is None:
        debit_fallback = coerce_float(spread.get("debit"), None)
        if debit_fallback is None:
            debit_fallback = coerce_float(spread.get("last_debit"), None)
        if debit_fallback is not None:
            mtm_pnl = (credit - debit_fallback) * 100.0 * max(quantity, 1)
        else:
            mtm_pnl = 0.0

    if closed:
        mtm_pnl = coerce_float(spread.get("realized_pnl"), mtm_pnl)
        if mtm_pnl is None:
            mtm_pnl = 0.0

    short_strike = coerce_float(spread.get("short_strike"), 0.0) or 0.0
    long_strike = coerce_float(spread.get("long_strike"), 0.0) or 0.0
    expiration = str(spread.get("expiration", "") or "")
    opened_at = coerce_timestamp(spread.get("opened_at")) or 0.0
    closed_at = coerce_timestamp(spread.get("closed_at")) or 0.0
    reference_timestamp = closed_at if closed and closed_at > 0 else opened_at
    reference_date = today

    timestamp_text = ""
    if reference_timestamp > 0:
        try:
            reference_dt = datetime.fromtimestamp(reference_timestamp, UTC)
            reference_date = reference_dt.astimezone(eastern_timezone).date()
            timestamp_text = (
                reference_dt
                .astimezone(eastern_timezone)
                .strftime("%Y-%m-%d %H:%M")
            )
        except (OSError, OverflowError, ValueError):
            timestamp_text = ""

    dte = format_days_to_expiration(expiration, reference_date)

    credit_dollars = coerce_float(spread.get("credit_received"), None)
    if credit_dollars is None:
        credit_dollars = credit * 100.0 * max(quantity, 1)
    pnl_percent = (mtm_pnl / credit_dollars * 100.0) if credit_dollars > 0 else 0.0

    if closed:
        summary_text = (
            f"CLOSED TRADE : {structure}  |  "
            f"DTE: {dte}  |  STATUS: CLOSED"
        )
    elif lifecycle_state == "CARRIED OVER":
        summary_text = (
            f"ACTIVE TRADE CARRIED OVER : {structure}  |  "
            f"DTE: {dte}  |  STATUS: OPEN"
        )
    else:
        summary_text = (
            f"STRATEGY {lifecycle_state} : {structure}  |  "
            f"DTE: {dte}  |  STATUS: OPEN"
        )

    header = PaperSpreadHeaderPresentation(
        timestamp_text=timestamp_text,
        summary_text=summary_text,
        pnl_text=f"NET P&L {format_signed_dollars(mtm_pnl)} ({pnl_percent:+.1f}%)",
        pnl_color=colors["positive"] if mtm_pnl >= 0 else colors["negative"],
    )

    normalized_legs: list[dict[str, Any]] = []
    raw_legs = spread.get("legs") or []
    if isinstance(raw_legs, list):
        for raw_leg in raw_legs:
            if not isinstance(raw_leg, Mapping):
                continue
            normalized_legs.append(
                {
                    "side": str(
                        raw_leg.get("side")
                        or raw_leg.get("action")
                        or raw_leg.get("position")
                        or raw_leg.get("name")
                        or ""
                    ).strip(),
                    "symbol": str(
                        raw_leg.get("symbol")
                        or raw_leg.get("option_symbol")
                        or raw_leg.get("contract_symbol")
                        or ""
                    ).strip(),
                    "strike": coerce_float(raw_leg.get("strike", raw_leg.get("strike_price")), None),
                    "qty": coerce_int(raw_leg.get("qty", raw_leg.get("quantity", quantity)), quantity),
                    "price": coerce_float(
                        raw_leg.get("price", raw_leg.get("entry_price", raw_leg.get("premium"))),
                        None,
                    ),
                    "type": str(
                        raw_leg.get("type")
                        or raw_leg.get("option_type")
                        or raw_leg.get("right")
                        or ""
                    ),
                    "cost": coerce_float(raw_leg.get("cost"), None),
                    "pnl": coerce_float(raw_leg.get("pnl"), None),
                }
            )

    normalized_legs = [
        leg for leg in normalized_legs
        if leg.get("side") or leg.get("strike") is not None
    ]

    if len(normalized_legs) < 2:
        option_type = str(spread.get("option_type", "P") or "P").upper()[:1]
        option_word = "Put" if option_type == "P" else "Call"
        short_entry = coerce_float(spread.get("short_entry_mid"), None)
        long_entry = coerce_float(spread.get("long_entry_mid"), None)
        last_short = coerce_float(spread.get("last_short_mid"), None)
        last_long = coerce_float(spread.get("last_long_mid"), None)
        normalized_legs = [
            {
                "side": f"Sell {option_word}",
                "symbol": "",
                "strike": short_strike,
                "qty": quantity,
                "price": short_entry,
                "type": option_type,
                "cost": -(short_entry * 100.0 * quantity) if short_entry is not None else None,
                "pnl": (
                    (short_entry - last_short) * 100.0 * quantity
                    if short_entry is not None and last_short is not None
                    else None
                ),
            },
            {
                "side": f"Buy {option_word}",
                "symbol": "",
                "strike": long_strike,
                "qty": quantity,
                "price": long_entry,
                "type": option_type,
                "cost": (long_entry * 100.0 * quantity) if long_entry is not None else None,
                "pnl": (
                    (last_long - long_entry) * 100.0 * quantity
                    if long_entry is not None and last_long is not None
                    else None
                ),
            },
        ]

    expiry_display = format_expiration_short(expiration)
    leg_presentations: list[PaperSpreadLegPresentation] = []
    for leg in normalized_legs:
        side = str(leg.get("side") or "LEG")
        action_text = side.upper()
        action_color = (
            colors["negative"] if action_text.startswith("SELL") or action_text.startswith("SHORT")
            else colors["positive"] if action_text.startswith("BUY") or action_text.startswith("LONG")
            else None
        )
        strike = coerce_float(leg.get("strike"), 0.0) or 0.0
        leg_type = str(leg.get("type") or "").upper()[:1]
        leg_qty = abs(coerce_int(leg.get("qty"), quantity))
        leg_symbol = str(leg.get("symbol") or "").strip()
        leg_text = leg_symbol or ("PUT LEG" if leg_type == "P" else "CALL LEG" if leg_type == "C" else "LEG")
        price = coerce_float(leg.get("price"), None)
        cost = coerce_float(leg.get("cost"), None)
        pnl = coerce_float(leg.get("pnl"), None)
        if price is None and cost is not None and leg_qty > 0:
            price = abs(cost) / (leg_qty * 100.0)

        leg_presentations.append(
            PaperSpreadLegPresentation(
                action_text=action_text,
                action_color=action_color,
                leg_text=leg_text,
                strike_text=f"${strike:.0f}{leg_type}",
                quantity_text=str(leg_qty),
                price_text=(f"${abs(price):,.2f}" if price is not None else ""),
                expiry_text=expiry_display,
                cost_text=(format_signed_dollars(cost) if cost is not None else ""),
                cost_color=(colors["positive"] if cost is not None and cost >= 0 else colors["negative"] if cost is not None else None),
                pnl_text=(format_signed_dollars(pnl) if pnl is not None else ""),
                pnl_color=(colors["positive"] if pnl is not None and pnl >= 0 else colors["negative"] if pnl is not None else None),
            )
        )

    return header, leg_presentations
