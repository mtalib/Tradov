#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG17_PaperPositionResolver.py
Purpose: Pure data helpers for paper-position dashboard rendering

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Keeps paper-position loading and condor reconstruction out of the PySide6
    dashboard class so the UI stays focused on rendering.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any


def _normalize_position_rows(
    rows: Any,
    *,
    origin: str | None = None,
) -> list[dict[str, Any]]:
    """Return shallow-copied position rows with an optional origin annotation."""
    if not isinstance(rows, list):
        return []

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized_row = dict(row)
        if origin and not str(normalized_row.get("_paper_open_origin") or "").strip():
            normalized_row["_paper_open_origin"] = origin
        normalized_rows.append(normalized_row)
    return normalized_rows


def _position_row_key(row: dict[str, Any]) -> str:
    """Return a stable dedupe key for one persisted paper position row."""
    position_id = str(row.get("position_id") or "").strip()
    if position_id:
        return position_id
    return f"{row.get('symbol', '')}:{row.get('opened_at', '')}:{row.get('quantity', '')}"


def _merge_position_rows(*row_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge position rows without duplicating the same persisted position."""
    merged_rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for row_group in row_groups:
        if not isinstance(row_group, list):
            continue
        for row in row_group:
            if not isinstance(row, dict):
                continue
            row_key = _position_row_key(row)
            if row_key in seen_keys:
                continue
            seen_keys.add(row_key)
            merged_rows.append(row)
    return merged_rows


def load_paper_open_positions(
    session_db: Any,
    *,
    trading_active: bool,
) -> list[dict[str, Any]]:
    """Load persisted paper positions from the session DB carryover boundary."""
    if session_db is None:
        return []

    get_active_open_positions = getattr(session_db, "get_active_paper_open_positions", None)
    get_display_eligible = getattr(session_db, "get_display_eligible_paper_open_positions", None)
    get_resume_eligible = getattr(session_db, "get_resume_eligible_open_positions", None)
    get_open_positions = getattr(session_db, "get_open_positions", None)

    if trading_active:
        display_rows = (
            _normalize_position_rows(get_display_eligible(), origin="carryover")
            if callable(get_display_eligible)
            else []
        )
        if callable(get_active_open_positions):
            active_rows = _normalize_position_rows(get_active_open_positions())
            merged_rows = _merge_position_rows(display_rows, active_rows)
            if merged_rows:
                return merged_rows
        if callable(get_open_positions):
            active_rows = _normalize_position_rows(get_open_positions(), origin="active_session")
            merged_rows = _merge_position_rows(display_rows, active_rows)
            if merged_rows:
                return merged_rows
        if callable(get_resume_eligible):
            return _normalize_position_rows(get_resume_eligible(), origin="carryover")
        return display_rows

    if callable(get_display_eligible):
        display_rows = _normalize_position_rows(get_display_eligible(), origin="carryover")
        if display_rows:
            return display_rows
    if callable(get_resume_eligible):
        return _normalize_position_rows(get_resume_eligible(), origin="carryover")
    if callable(get_open_positions):
        return _normalize_position_rows(get_open_positions())
    return []


def parse_occ_option_contract(symbol: str) -> dict[str, Any]:
    """Parse an OCC option symbol into underlying, expiration, strike, and type."""
    normalized = str(symbol or "").strip().upper()
    if len(normalized) < 16:
        return {}

    underlying = normalized[:-15]
    suffix = normalized[-15:]
    date_part = suffix[:6]
    option_flag = suffix[6:7]
    strike_part = suffix[7:]
    if not underlying or not date_part.isdigit() or option_flag not in {"C", "P"} or not strike_part.isdigit():
        return {}

    try:
        expiration = datetime.strptime(date_part, "%y%m%d").date().isoformat()
    except ValueError:
        expiration = ""

    return {
        "underlying": underlying,
        "expiration": expiration,
        "strike": int(strike_part) / 1000.0,
        "option_type": "call" if option_flag == "C" else "put",
    }


def _normalize_strategy_token(value: Any) -> str:
    """Normalize strategy identifiers for carryover grouping and labeling."""
    text = str(value or "").strip()
    if not text:
        return ""

    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def restore_paper_spreads_from_positions(
    positions: list[dict[str, Any]],
    *,
    default_lifecycle_state: str = "CARRIED OVER",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild spread-like paper positions from persisted single-leg option rows."""

    def _coerce_float(value: Any, default: float | None = None) -> float | None:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _coerce_int(value: Any, default: int = 0) -> int:
        try:
            if value in (None, ""):
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _opened_at_ts(value: str) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _position_key(position: dict[str, Any]) -> str:
        return str(
            position.get("position_id")
            or f"{position.get('symbol', '')}:{position.get('opened_at', '')}:{position.get('quantity', '')}"
        )

    def _normalized_signed_quantity(position: dict[str, Any], quantity: int) -> int:
        side = str(
            position.get("side")
            or position.get("position_side")
            or position.get("direction")
            or ""
        ).strip().lower()
        if side in {"sell", "sell_to_open", "sell_to_close", "sto", "stc", "short"}:
            return -abs(quantity)
        if side in {"buy", "buy_to_open", "buy_to_close", "bto", "btc", "long"}:
            return abs(quantity)
        return quantity

    def _resolve_group_lifecycle_state(candidate: list[dict[str, Any]]) -> str:
        lifecycle_state = default_lifecycle_state
        explicit_lifecycle_states = {
            str(row.get("lifecycle_state") or "").strip()
            for row in candidate
            if str(row.get("lifecycle_state") or "").strip()
        }
        if len(explicit_lifecycle_states) == 1:
            return explicit_lifecycle_states.pop()

        origins = {
            str(row.get("_paper_open_origin") or "").strip()
            for row in candidate
            if str(row.get("_paper_open_origin") or "").strip()
        }
        if origins == {"carryover"}:
            return "CARRIED OVER"
        return lifecycle_state

    def _build_restored_multileg_snapshot(
        candidate: list[dict[str, Any]],
        ordered_legs: list[dict[str, Any]],
        *,
        qty: int,
        structure: str,
        expiration: str,
        short_strike: float,
        long_strike: float,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if qty <= 0:
            return None

        legs: list[dict[str, Any]] = []
        credit = 0.0
        mtm_pnl = 0.0
        opened_at = min(_opened_at_ts(str(row.get("opened_at") or "")) for row in candidate)

        for row in ordered_legs:
            signed_qty = _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), qty))
            leg_qty = abs(signed_qty)
            if leg_qty <= 0:
                return None

            leg_price = _coerce_float(row.get("entry_price"), 0.0) or 0.0
            option_type = str(row.get("option_type") or "").lower()
            if option_type not in {"call", "put"}:
                return None

            unrealized_pnl = _coerce_float(row.get("unrealized_pnl"), 0.0) or 0.0
            cost = leg_price * 100.0 * leg_qty
            if signed_qty < 0:
                credit += leg_price * leg_qty
                side = "Sell Put" if option_type == "put" else "Sell Call"
                cost = -cost
            else:
                credit -= leg_price * leg_qty
                side = "Buy Put" if option_type == "put" else "Buy Call"

            mtm_pnl += unrealized_pnl
            legs.append(
                {
                    "symbol": str(row.get("symbol") or ""),
                    "side": side,
                    "strike": _coerce_float(row.get("strike"), 0.0) or 0.0,
                    "qty": leg_qty,
                    "type": "P" if option_type == "put" else "C",
                    "cost": cost,
                    "pnl": unrealized_pnl,
                }
            )

        spread_id = "|".join(
            sorted(leg["symbol"] for leg in legs if leg.get("symbol"))
        )
        snapshot: dict[str, Any] = {
            "id": spread_id,
            "structure": structure,
            "lifecycle_state": _resolve_group_lifecycle_state(candidate),
            "qty": qty,
            "credit": credit,
            "mtm_pnl": mtm_pnl,
            "expiration": expiration,
            "opened_at": opened_at,
            "short_strike": short_strike,
            "long_strike": long_strike,
            "legs": legs,
        }
        if extra_fields:
            snapshot.update(extra_fields)
        return snapshot

    def _build_condor(candidate: list[dict[str, Any]]) -> dict[str, Any] | None:
        if len(candidate) != 4:
            return None

        grouped: dict[str, list[dict[str, Any]]] = {"call": [], "put": []}
        unique_symbols = {
            str(row.get("symbol") or "")
            for row in candidate
            if str(row.get("symbol") or "")
        }
        if len(unique_symbols) != 4:
            return None

        for row in candidate:
            option_type = str(row.get("option_type") or "").lower()
            if option_type not in grouped:
                return None
            grouped[option_type].append(row)

        for option_type in ("call", "put"):
            if len(grouped[option_type]) != 2:
                return None
            positive = [
                row for row in grouped[option_type]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
            ]
            negative = [
                row for row in grouped[option_type]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
            ]
            if len(positive) != 1 or len(negative) != 1:
                return None

        long_put = next(
            row for row in grouped["put"]
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
        )
        short_put = next(
            row for row in grouped["put"]
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
        )
        short_call = next(
            row for row in grouped["call"]
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
        )
        long_call = next(
            row for row in grouped["call"]
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
        )

        if not (
            _coerce_float(long_put.get("strike"), 0.0) < _coerce_float(short_put.get("strike"), 0.0)
            < _coerce_float(short_call.get("strike"), 0.0) < _coerce_float(long_call.get("strike"), 0.0)
        ):
            return None

        qty = abs(_normalized_signed_quantity(short_put, _coerce_int(short_put.get("quantity"), 0)))
        if qty <= 0:
            return None

        return _build_restored_multileg_snapshot(
            candidate,
            [short_put, long_put, short_call, long_call],
            qty=qty,
            structure="IRON_CONDOR",
            expiration=str(short_put.get("expiration") or ""),
            short_strike=_coerce_float(short_put.get("strike"), 0.0) or 0.0,
            long_strike=_coerce_float(long_put.get("strike"), 0.0) or 0.0,
        )

    def _build_iron_butterfly(candidate: list[dict[str, Any]]) -> dict[str, Any] | None:
        if len(candidate) != 4:
            return None

        grouped: dict[str, list[dict[str, Any]]] = {"call": [], "put": []}
        unique_symbols = {
            str(row.get("symbol") or "")
            for row in candidate
            if str(row.get("symbol") or "")
        }
        if len(unique_symbols) != 4:
            return None

        for row in candidate:
            option_type = str(row.get("option_type") or "").lower()
            if option_type not in grouped:
                return None
            grouped[option_type].append(row)

        for option_type in ("call", "put"):
            if len(grouped[option_type]) != 2:
                return None

        long_put = next(
            (
                row for row in grouped["put"]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
            ),
            None,
        )
        short_put = next(
            (
                row for row in grouped["put"]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
            ),
            None,
        )
        short_call = next(
            (
                row for row in grouped["call"]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
            ),
            None,
        )
        long_call = next(
            (
                row for row in grouped["call"]
                if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
            ),
            None,
        )
        if any(row is None for row in (long_put, short_put, short_call, long_call)):
            return None

        short_put_strike = _coerce_float(short_put.get("strike"), 0.0) or 0.0
        short_call_strike = _coerce_float(short_call.get("strike"), 0.0) or 0.0
        long_put_strike = _coerce_float(long_put.get("strike"), 0.0) or 0.0
        long_call_strike = _coerce_float(long_call.get("strike"), 0.0) or 0.0
        if not (long_put_strike < short_put_strike == short_call_strike < long_call_strike):
            return None

        qty = abs(_normalized_signed_quantity(short_put, _coerce_int(short_put.get("quantity"), 0)))
        if qty <= 0:
            return None
        quantities = [
            abs(_normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)))
            for row in candidate
        ]
        if any(quantity != qty for quantity in quantities):
            return None

        return _build_restored_multileg_snapshot(
            candidate,
            [long_put, short_put, short_call, long_call],
            qty=qty,
            structure="IRON_BUTTERFLY",
            expiration=str(short_put.get("expiration") or short_call.get("expiration") or ""),
            short_strike=short_put_strike,
            long_strike=long_put_strike,
            extra_fields={
                "body_strike": short_put_strike,
                "long_call_strike": long_call_strike,
            },
        )

    def _build_option_butterfly(candidate: list[dict[str, Any]]) -> dict[str, Any] | None:
        if len(candidate) != 3:
            return None

        unique_symbols = {
            str(row.get("symbol") or "")
            for row in candidate
            if str(row.get("symbol") or "")
        }
        if len(unique_symbols) != 3:
            return None

        option_types = {
            str(row.get("option_type") or "").lower()
            for row in candidate
            if str(row.get("option_type") or "").lower() in {"call", "put"}
        }
        if len(option_types) != 1:
            return None
        option_type = option_types.pop()

        long_rows = [
            row for row in candidate
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) > 0
        ]
        short_rows = [
            row for row in candidate
            if _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0)) < 0
        ]
        if len(long_rows) != 2 or len(short_rows) != 1:
            return None

        body_row = short_rows[0]
        body_qty = abs(_normalized_signed_quantity(body_row, _coerce_int(body_row.get("quantity"), 0)))
        if body_qty <= 0 or body_qty % 2 != 0:
            return None

        qty = body_qty // 2
        if qty <= 0:
            return None
        if any(
            abs(_normalized_signed_quantity(row, _coerce_int(row.get("quantity"), 0))) != qty
            for row in long_rows
        ):
            return None

        ascending = sorted(
            candidate,
            key=lambda row: _coerce_float(row.get("strike"), 0.0) or 0.0,
        )
        strikes = [_coerce_float(row.get("strike"), None) for row in ascending]
        if len({strike for strike in strikes if strike is not None}) != 3:
            return None

        lower_row, middle_row, upper_row = ascending
        if middle_row is not body_row:
            return None
        if lower_row not in long_rows or upper_row not in long_rows:
            return None

        lower_strike = _coerce_float(lower_row.get("strike"), 0.0) or 0.0
        body_strike = _coerce_float(middle_row.get("strike"), 0.0) or 0.0
        upper_strike = _coerce_float(upper_row.get("strike"), 0.0) or 0.0
        lower_wing_width = body_strike - lower_strike
        upper_wing_width = upper_strike - body_strike

        strategy_token = str(body_row.get("strategy") or "")
        structure = (
            "BROKEN_WING_BUTTERFLY"
            if "broken_wing_butterfly" in strategy_token
            or abs(lower_wing_width - upper_wing_width) > 1e-9
            else "BUTTERFLY"
        )
        ordered_legs = ascending if option_type == "call" else [upper_row, middle_row, lower_row]

        return _build_restored_multileg_snapshot(
            candidate,
            ordered_legs,
            qty=qty,
            structure=structure,
            expiration=str(middle_row.get("expiration") or ""),
            short_strike=body_strike,
            long_strike=lower_strike,
            extra_fields={
                "body_strike": body_strike,
                "lower_strike": lower_strike,
                "upper_strike": upper_strike,
            },
        )

    eligible: list[dict[str, Any]] = []
    leftovers: list[dict[str, Any]] = []
    for raw_position in positions:
        if not isinstance(raw_position, dict):
            continue

        position = dict(raw_position)
        raw_strategy = (
            position.get("strategy_id")
            or position.get("strategy_name")
            or position.get("strategy")
            or ""
        )
        strategy = _normalize_strategy_token(raw_strategy)
        parsed = parse_occ_option_contract(str(position.get("symbol") or ""))
        expiration = str(position.get("expiration") or parsed.get("expiration") or "")
        strike = _coerce_float(position.get("strike"), parsed.get("strike"))
        option_type = str(position.get("option_type") or parsed.get("option_type") or "").lower()
        quantity = _normalized_signed_quantity(position, _coerce_int(position.get("quantity"), 0))
        underlying = str(parsed.get("underlying") or position.get("symbol") or "")

        if (
            ("condor" not in strategy and "butterfly" not in strategy)
            or not parsed
            or not expiration
            or strike is None
            or option_type not in {"call", "put"}
            or quantity == 0
        ):
            leftovers.append(position)
            continue

        position.update(
            {
                "strategy": strategy,
                "expiration": expiration,
                "strike": strike,
                "option_type": option_type,
                "underlying": underlying,
                "quantity": quantity,
                "_opened_at_ts": _opened_at_ts(str(position.get("opened_at") or "")),
                "_position_key": _position_key(position),
            }
        )
        eligible.append(position)

    buckets: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
    for position in eligible:
        bucket_quantity = abs(_coerce_int(position.get("quantity"), 0))
        if "butterfly" in str(position.get("strategy") or ""):
            bucket_quantity = 0
        key = (
            str(position.get("strategy") or ""),
            str(position.get("underlying") or ""),
            str(position.get("expiration") or ""),
            bucket_quantity,
        )
        buckets.setdefault(key, []).append(position)

    grouped_keys: set[str] = set()
    restored_spreads: list[dict[str, Any]] = []
    for bucket_positions in buckets.values():
        ordered = sorted(
            bucket_positions,
            key=lambda row: (row.get("_opened_at_ts", 0.0), str(row.get("symbol") or "")),
        )
        index = 0
        while index < len(ordered):
            restored = None
            consumed = 0

            if index <= len(ordered) - 4:
                candidate = ordered[index:index + 4]
                restored = _build_iron_butterfly(candidate) or _build_condor(candidate)
                if restored is not None:
                    consumed = 4

            if restored is None and index <= len(ordered) - 3:
                candidate = ordered[index:index + 3]
                restored = _build_option_butterfly(candidate)
                if restored is not None:
                    consumed = 3

            if restored is not None and consumed > 0:
                restored_spreads.append(restored)
                grouped_keys.update(
                    str(row.get("_position_key") or "")
                    for row in ordered[index:index + consumed]
                )
                index += consumed
                continue
            index += 1

    leftover_positions = leftovers + [
        position for position in eligible if str(position.get("_position_key") or "") not in grouped_keys
    ]
    leftover_positions.sort(key=lambda row: str(row.get("opened_at") or ""))
    restored_spreads.sort(key=lambda row: float(row.get("opened_at") or 0.0))
    return restored_spreads, leftover_positions
