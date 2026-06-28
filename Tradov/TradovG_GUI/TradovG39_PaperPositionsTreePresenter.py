#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG39_PaperPositionsTreePresenter.py
Purpose: Pure presentation helpers for paper positions tree rows
"""

from __future__ import annotations

import re
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

    timestamp_text: str
    summary_text: str
    pnl_text: str
    pnl_color: str
    detail_rows: Sequence[RestoredPaperPositionPresentation]
    cash_held_text: str = ""
    close_symbols: Sequence[str] = ()


@dataclass(frozen=True)
class PaperSpreadHeaderPresentation:
    """Preformatted summary header values for a paper spread tree row."""

    timestamp_text: str
    summary_text: str
    pnl_text: str
    pnl_color: str
    cash_held_text: str = ""


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
    """Format a signed dollar amount with two decimals by default."""
    abs_value = abs(float(value))
    resolved_decimals = decimals
    if resolved_decimals is None:
        resolved_decimals = 2
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


def _normalize_strategy_display_token(value: Any) -> str:
    """Normalize strategy or structure identifiers for display mapping."""
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def format_strategy_display_name(value: Any) -> str:
    """Map strategy identifiers into concise dashboard labels."""
    normalized = _normalize_strategy_display_token(value)
    if not normalized:
        return "PAPER FILL"
    if "broken_wing_butterfly" in normalized:
        return "Broken-Butterfly"
    if normalized == "iron_butterfly":
        return "Iron-Butterfly"
    if "butterfly" in normalized:
        return "Reg-Butterfly"
    return str(value or "paper_fill").replace("_", " ").upper()


def _resolve_position_strategy_value(position: Mapping[str, Any]) -> Any:
    """Return the most specific persisted strategy identifier for a position."""
    return (
        position.get("strategy_id")
        or position.get("strategy_name")
        or position.get("strategy")
        or "paper_fill"
    )


def _position_supports_manual_close(position: Mapping[str, Any]) -> bool:
    """Return True when the restored position is a butterfly-family artifact."""
    return "butterfly" in _normalize_strategy_display_token(_resolve_position_strategy_value(position))


def _signed_position_quantity(position: Mapping[str, Any]) -> int:
    """Return signed quantity using explicit side metadata when available."""
    raw_quantity = position.get("quantity")
    if raw_quantity in (None, ""):
        raw_quantity = position.get("qty")
    quantity = coerce_int(raw_quantity, 0)
    side = str(
        position.get("side")
        or position.get("position_side")
        or position.get("action")
        or ""
    ).strip().lower()
    if side.startswith(("sell", "short")):
        return -abs(quantity)
    if side.startswith(("buy", "long")):
        return abs(quantity)
    return quantity


def _position_contract_multiplier(position: Mapping[str, Any]) -> float:
    """Return the option-equity multiplier for one restored position row."""
    option_type = (
        str(position.get("option_type") or "").upper()[:1]
        or _occ_option_flag(str(position.get("symbol") or ""))
    )
    return 100.0 if option_type in {"P", "C"} else 1.0


def _position_total_entry_cost_dollars(position: Mapping[str, Any]) -> float | None:
    """Return signed entry cost dollars for one restored position row."""
    entry_price = coerce_float(position.get("entry_price", position.get("price")), None)
    if entry_price is None:
        return None

    quantity = _signed_position_quantity(position)
    if quantity == 0:
        return None

    return entry_price * quantity * _position_contract_multiplier(position)


def _position_cash_held_candidate_dollars(position: Mapping[str, Any]) -> float | None:
    """Return one best-effort cash-held candidate from a restored position row."""
    direct_candidate = coerce_float(
        position.get("cash_held_dollars", position.get("buying_power_held")),
        None,
    )
    if direct_candidate is not None and direct_candidate != 0:
        return abs(direct_candidate)

    direct_candidate = coerce_float(position.get("max_loss_dollars"), None)
    if direct_candidate is not None and direct_candidate != 0:
        return abs(direct_candidate)

    quantity = max(abs(_signed_position_quantity(position)), 1)
    max_loss_per_contract = coerce_float(position.get("max_loss_per_contract"), None)
    if max_loss_per_contract is not None and max_loss_per_contract != 0:
        return abs(max_loss_per_contract) * quantity

    per_share_risk = coerce_float(position.get("max_loss"), None)
    if per_share_risk is None:
        per_share_risk = coerce_float(position.get("expected_debit"), None)
    if per_share_risk is None:
        per_share_risk = coerce_float(position.get("debit"), None)
    if per_share_risk is not None and per_share_risk != 0:
        return abs(per_share_risk) * 100.0 * quantity

    return None


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
        strategy = str(_resolve_position_strategy_value(position) or "paper_fill")
        strategy_label = format_strategy_display_name(strategy)
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
                    f"{strategy_label}  |  "
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
                    f"Strategy: {strategy_label}\n"
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
    today: dt_date | None = None,
    eastern_timezone: tzinfo = UTC,
    cluster_window_seconds: float = 10.0,
) -> Sequence[RestoredPaperPositionGroupPresentation]:
    """Group related restored positions under one summary header when practical."""
    normalized_positions = [position for position in positions or [] if isinstance(position, Mapping)]
    if not normalized_positions:
        return []

    reference_today = today or datetime.now(UTC).astimezone(eastern_timezone).date()

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

        first = group[0]
        lifecycle_state = _resolve_restored_position_lifecycle_state(first)
        strategy = format_strategy_display_name(_resolve_position_strategy_value(first))
        status = str(first.get("status") or "OPEN").strip().upper()
        expiration = str(first.get("expiration") or "").strip()
        opened_ts = coerce_timestamp(first.get("opened_at"))
        timestamp_text = ""
        reference_date = reference_today
        if opened_ts is not None:
            try:
                opened_dt = datetime.fromtimestamp(opened_ts, UTC).astimezone(eastern_timezone)
                timestamp_text = opened_dt.strftime("%Y-%m-%d %H:%M")
                reference_date = opened_dt.date()
            except (OSError, OverflowError, ValueError):
                timestamp_text = ""

        dte = format_days_to_expiration(expiration, reference_date)
        if lifecycle_state == "CARRIED OVER":
            summary_text = f"ACTIVE TRADE CARRIED OVER : {strategy}  |  DTE: {dte}  |  STATUS: {status}"
        else:
            summary_text = f"STRATEGY {lifecycle_state} : {strategy}  |  DTE: {dte}  |  STATUS: {status}"

        mtm_pnl = sum(coerce_float(position.get("unrealized_pnl"), 0.0) or 0.0 for position in group)

        cash_held_basis_dollars = None
        for position in group:
            candidate = _position_cash_held_candidate_dollars(position)
            if candidate is not None and candidate > 0:
                cash_held_basis_dollars = max(cash_held_basis_dollars or 0.0, candidate)

        net_entry_cost_dollars = 0.0
        saw_entry_cost = False
        for position in group:
            entry_cost = _position_total_entry_cost_dollars(position)
            if entry_cost is None:
                continue
            net_entry_cost_dollars += entry_cost
            saw_entry_cost = True

        credit_dollars = abs(net_entry_cost_dollars) if saw_entry_cost and net_entry_cost_dollars < 0 else 0.0
        if cash_held_basis_dollars is None and saw_entry_cost and net_entry_cost_dollars != 0:
            cash_held_basis_dollars = abs(net_entry_cost_dollars)

        pnl_basis_dollars = credit_dollars if credit_dollars > 0 else (cash_held_basis_dollars or 0.0)
        pnl_percent = (mtm_pnl / pnl_basis_dollars * 100.0) if pnl_basis_dollars > 0 else 0.0
        cash_held_text = f"CASH HELD: ${cash_held_basis_dollars or 0.0:,.2f}"
        pnl_text = f"NET P&L {format_signed_dollars(mtm_pnl)} ({pnl_percent:+.1f}%)"

        seen_symbols: set[str] = set()
        close_symbols: list[str] = []
        if any(_position_supports_manual_close(position) for position in group):
            for position in group:
                symbol = str(position.get("symbol") or "").strip()
                if symbol and symbol not in seen_symbols:
                    seen_symbols.add(symbol)
                    close_symbols.append(symbol)

        presentations.append(
            RestoredPaperPositionGroupPresentation(
                timestamp_text=timestamp_text,
                summary_text=summary_text,
                pnl_text=pnl_text,
                pnl_color=colors["positive"] if mtm_pnl >= 0 else colors["negative"],
                detail_rows=detail_rows,
                cash_held_text=cash_held_text,
                close_symbols=tuple(close_symbols),
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
    structure = format_strategy_display_name(spread.get("structure") or spread.get("type") or "SPREAD")
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
    raw_legs = spread.get("legs") or []

    credit_dollars = coerce_float(spread.get("credit_received"), None)
    if credit_dollars is None:
        credit_dollars = credit * 100.0 * max(quantity, 1)

    cash_held_basis_dollars = coerce_float(
        spread.get("cash_held_dollars", spread.get("buying_power_held")),
        None,
    )
    if cash_held_basis_dollars is None:
        cash_held_basis_dollars = coerce_float(spread.get("max_loss_dollars"), None)
    if cash_held_basis_dollars is None:
        max_loss_per_contract = coerce_float(spread.get("max_loss_per_contract"), None)
        if max_loss_per_contract is not None and max_loss_per_contract > 0:
            cash_held_basis_dollars = max_loss_per_contract * max(abs(quantity), 1)
    if cash_held_basis_dollars is None:
        per_share_risk = coerce_float(spread.get("max_loss"), None)
        if per_share_risk is None:
            per_share_risk = coerce_float(spread.get("expected_debit"), None)
        if per_share_risk is None:
            per_share_risk = coerce_float(spread.get("debit"), None)
        if per_share_risk is not None and per_share_risk > 0:
            cash_held_basis_dollars = per_share_risk * 100.0 * max(abs(quantity), 1)
    if cash_held_basis_dollars is None and isinstance(raw_legs, list):
        total_entry_cost = 0.0
        saw_leg_cost = False
        for raw_leg in raw_legs:
            if not isinstance(raw_leg, Mapping):
                continue
            leg_cost = coerce_float(raw_leg.get("cost"), None)
            if leg_cost is not None:
                total_entry_cost += leg_cost
                saw_leg_cost = True
                continue

            leg_price = coerce_float(
                raw_leg.get("price", raw_leg.get("entry_price", raw_leg.get("premium"))),
                None,
            )
            if leg_price is None:
                continue

            leg_qty = abs(coerce_int(raw_leg.get("qty", raw_leg.get("quantity", quantity)), quantity))
            leg_side = str(
                raw_leg.get("side")
                or raw_leg.get("action")
                or raw_leg.get("position")
                or raw_leg.get("name")
                or ""
            ).strip().lower()
            sign = -1.0 if leg_side.startswith(("sell", "short")) else 1.0
            total_entry_cost += leg_price * 100.0 * leg_qty * sign
            saw_leg_cost = True

        if saw_leg_cost and total_entry_cost != 0:
            cash_held_basis_dollars = abs(total_entry_cost)

    pnl_basis_dollars = credit_dollars if credit_dollars > 0 else (cash_held_basis_dollars or 0.0)
    pnl_percent = (mtm_pnl / pnl_basis_dollars * 100.0) if pnl_basis_dollars > 0 else 0.0

    cash_held_dollars = None if closed else cash_held_basis_dollars

    cash_held_text = f"CASH HELD: ${cash_held_dollars or 0.0:,.2f}"

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
        cash_held_text=cash_held_text,
        pnl_text=f"NET P&L {format_signed_dollars(mtm_pnl)} ({pnl_percent:+.1f}%)",
        pnl_color=colors["positive"] if mtm_pnl >= 0 else colors["negative"],
    )

    normalized_legs: list[dict[str, Any]] = []
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

        display_cost = None
        if cost is not None:
            if action_text.startswith(("SELL", "SHORT")):
                display_cost = abs(cost)
            elif action_text.startswith(("BUY", "LONG")):
                display_cost = -abs(cost)
            else:
                display_cost = cost

        leg_presentations.append(
            PaperSpreadLegPresentation(
                action_text=action_text,
                action_color=action_color,
                leg_text=leg_text,
                strike_text=f"${strike:.0f}{leg_type}",
                quantity_text=str(leg_qty),
                price_text=(f"${abs(price):,.2f}" if price is not None else ""),
                expiry_text=expiry_display,
                cost_text=(format_signed_dollars(display_cost) if display_cost is not None else ""),
                cost_color=(colors["positive"] if display_cost is not None and display_cost >= 0 else colors["negative"] if display_cost is not None else None),
                pnl_text=(format_signed_dollars(pnl) if pnl is not None else ""),
                pnl_color=(colors["positive"] if pnl is not None and pnl >= 0 else colors["negative"] if pnl is not None else None),
            )
        )

    return header, leg_presentations
