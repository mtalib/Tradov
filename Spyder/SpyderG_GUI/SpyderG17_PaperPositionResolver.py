#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG17_PaperPositionResolver.py
Purpose: Pure data helpers for paper-position dashboard rendering

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-05-14 Time: 22:30:00

Module Description:
    Keeps paper-position loading and condor reconstruction out of the PySide6
    dashboard class so the UI stays focused on rendering.
"""

from __future__ import annotations

from datetime import datetime
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


def load_paper_open_positions(
    session_db: Any,
    *,
    trading_active: bool,
) -> list[dict[str, Any]]:
    """Load persisted paper positions from the session DB carryover boundary."""
    if session_db is None:
        return []

    get_active_open_positions = getattr(session_db, "get_active_paper_open_positions", None)
    get_resume_eligible = getattr(session_db, "get_resume_eligible_open_positions", None)
    get_open_positions = getattr(session_db, "get_open_positions", None)

    if trading_active:
        if callable(get_active_open_positions):
            return _normalize_position_rows(get_active_open_positions())
        if callable(get_open_positions):
            return _normalize_position_rows(get_open_positions(), origin="active_session")
        if callable(get_resume_eligible):
            return _normalize_position_rows(get_resume_eligible(), origin="carryover")
        return []

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

    def _build_condor(candidate: list[dict[str, Any]]) -> dict[str, Any] | None:
        if len(candidate) != 4:
            return None

        lifecycle_state = default_lifecycle_state
        explicit_lifecycle_states = {
            str(row.get("lifecycle_state") or "").strip()
            for row in candidate
            if str(row.get("lifecycle_state") or "").strip()
        }
        if len(explicit_lifecycle_states) == 1:
            lifecycle_state = explicit_lifecycle_states.pop()
        else:
            origins = {
                str(row.get("_paper_open_origin") or "").strip()
                for row in candidate
                if str(row.get("_paper_open_origin") or "").strip()
            }
            if origins == {"carryover"}:
                lifecycle_state = "CARRIED OVER"

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

        ordered_legs = [short_put, long_put, short_call, long_call]
        legs: list[dict[str, Any]] = []
        credit = 0.0
        mtm_pnl = 0.0
        opened_at = min(_opened_at_ts(str(row.get("opened_at") or "")) for row in candidate)
        expiration = str(short_put.get("expiration") or "")

        for row in ordered_legs:
            signed_qty = _normalized_signed_quantity(row, _coerce_int(row.get("quantity"), qty))
            leg_qty = abs(signed_qty) or qty
            leg_price = _coerce_float(row.get("entry_price"), 0.0) or 0.0
            option_type = str(row.get("option_type") or "").lower()
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

        # Build a unique, stable id from the sorted OCC symbols of the four
        # legs so the dashboard X-button can target exactly this condor group
        # via a FLATTEN_REQUEST without ambiguity when multiple condors are open.
        condor_id = "|".join(
            sorted(leg["symbol"] for leg in legs if leg.get("symbol"))
        )

        return {
            "id": condor_id,
            "structure": "IRON_CONDOR",
            "lifecycle_state": lifecycle_state,
            "qty": qty,
            "credit": credit,
            "mtm_pnl": mtm_pnl,
            "expiration": expiration,
            "opened_at": opened_at,
            "short_strike": _coerce_float(short_put.get("strike"), 0.0) or 0.0,
            "long_strike": _coerce_float(long_put.get("strike"), 0.0) or 0.0,
            "legs": legs,
        }

    eligible: list[dict[str, Any]] = []
    leftovers: list[dict[str, Any]] = []
    for raw_position in positions:
        if not isinstance(raw_position, dict):
            continue

        position = dict(raw_position)
        strategy = str(position.get("strategy") or "").lower()
        parsed = parse_occ_option_contract(str(position.get("symbol") or ""))
        expiration = str(position.get("expiration") or parsed.get("expiration") or "")
        strike = _coerce_float(position.get("strike"), parsed.get("strike"))
        option_type = str(position.get("option_type") or parsed.get("option_type") or "").lower()
        quantity = _normalized_signed_quantity(position, _coerce_int(position.get("quantity"), 0))
        underlying = str(parsed.get("underlying") or position.get("symbol") or "")

        if (
            "condor" not in strategy
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
        key = (
            str(position.get("strategy") or ""),
            str(position.get("underlying") or ""),
            str(position.get("expiration") or ""),
            abs(_coerce_int(position.get("quantity"), 0)),
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
        while index <= len(ordered) - 4:
            candidate = ordered[index:index + 4]
            restored = _build_condor(candidate)
            if restored is not None:
                restored_spreads.append(restored)
                grouped_keys.update(str(row.get("_position_key") or "") for row in candidate)
                index += 4
                continue
            index += 1

    leftover_positions = leftovers + [
        position for position in eligible if str(position.get("_position_key") or "") not in grouped_keys
    ]
    leftover_positions.sort(key=lambda row: str(row.get("opened_at") or ""))
    restored_spreads.sort(key=lambda row: float(row.get("opened_at") or 0.0))
    return restored_spreads, leftover_positions
