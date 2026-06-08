#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG40_ToolbarIndexPresenter.py
Purpose: Pure presentation helpers for toolbar index quotes
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime, time as dt_time
from typing import Any
from collections.abc import Mapping


_DELAYED_INDEX_SYMBOLS = frozenset({"SPX", "$DJI", "NDX", "RUT"})


@dataclass(frozen=True)
class ToolbarIndexPresentation:
    """Display-ready value/change texts and color for one toolbar index."""

    value_text: str
    change_text: str
    change_color: str


def _coerce_numeric(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _market_data_datetime_from_epoch_ms(value: Any, now_et: datetime) -> datetime | None:
    epoch_ms = _coerce_numeric(value)
    if epoch_ms is None or epoch_ms <= 0.0:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000.0, UTC).astimezone(now_et.tzinfo or UTC)


def _is_regular_session_open(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    open_et = dt_time(9, 30)
    close_et = dt_time(16, 0)
    return open_et <= now_et.time() <= close_et


def _build_proxy_entry(entry: Mapping[str, Any] | None, multiplier: float) -> dict[str, Any] | None:
    if not isinstance(entry, Mapping):
        return None

    last = _coerce_numeric(entry.get("last"))
    if last is None or last <= 0.0:
        return None

    proxy_multiplier = _coerce_numeric(multiplier)
    if proxy_multiplier is None or proxy_multiplier <= 0.0:
        return None

    change = _coerce_numeric(entry.get("change")) or 0.0
    change_pct = _coerce_numeric(entry.get("change_pct")) or 0.0

    return {
        "last": last * proxy_multiplier,
        "change": change * proxy_multiplier,
        "change_pct": change_pct,
        "change_available": bool(entry.get("change_available", True)),
        "timestamp_ms": entry.get("timestamp_ms"),
    }


def _entry_is_fresh(
    symbol: str,
    entry: Mapping[str, Any] | None,
    *,
    fetch_time: datetime | None,
    now_et: datetime,
    market_hours_open: bool,
    realtime_quote_max_age_seconds: float,
) -> bool:
    if not isinstance(entry, Mapping):
        return False

    last = _coerce_numeric(entry.get("last"))
    if last is None or last == 0.0:
        return False

    if not market_hours_open:
        return True

    if symbol in _DELAYED_INDEX_SYMBOLS and not _is_regular_session_open(now_et):
        return True

    if fetch_time is None:
        return True

    quote_time = _market_data_datetime_from_epoch_ms(entry.get("timestamp_ms"), now_et)
    if quote_time is None:
        return False

    max_age_seconds = realtime_quote_max_age_seconds
    if symbol in _DELAYED_INDEX_SYMBOLS:
        max_age_seconds = 1800.0

    age_seconds = abs((fetch_time - quote_time).total_seconds())
    return age_seconds <= max_age_seconds


def _build_index_presentation(
    entry: Mapping[str, Any],
    *,
    use_grouping: bool,
    positive_color: str,
    negative_color: str,
    neutral_color: str,
) -> ToolbarIndexPresentation:
    last = _coerce_numeric(entry.get("last"))
    if last is None or last <= 0.0:
        return ToolbarIndexPresentation("", "", neutral_color)

    change = _coerce_numeric(entry.get("change")) or 0.0
    change_pct = _coerce_numeric(entry.get("change_pct")) or 0.0
    sign = "+" if change >= 0 else ""
    value_text = f" {last:,.0f}" if use_grouping else f" {last:.0f}"

    if not bool(entry.get("change_available", True)):
        return ToolbarIndexPresentation(value_text, "  --", neutral_color)

    return ToolbarIndexPresentation(
        value_text=value_text,
        change_text=f"  {sign}{change:.0f}  {sign}{change_pct:.1f}%",
        change_color=positive_color if change >= 0 else negative_color,
    )


def build_toolbar_index_presentations(
    live_data: Mapping[str, Any] | None,
    *,
    now_et: datetime,
    market_hours_open: bool,
    realtime_quote_max_age_seconds: float,
    dji_from_dia_multiplier: float,
    positive_color: str,
    negative_color: str,
    neutral_color: str = "#888888",
) -> dict[str, ToolbarIndexPresentation]:
    """Build toolbar index label presentations from a live-data payload."""
    payload = live_data if isinstance(live_data, Mapping) else {}
    fetch_time = _market_data_datetime_from_epoch_ms(payload.get("_fetch_time_ms"), now_et)
    clear = ToolbarIndexPresentation("", "", neutral_color)

    presentations: dict[str, ToolbarIndexPresentation] = {
        "spx": clear,
        "ndx": clear,
        "dji": clear,
        "rut": clear,
    }

    spx_entry = payload.get("SPX")
    if _entry_is_fresh(
        "SPX",
        spx_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        presentations["spx"] = _build_index_presentation(
            spx_entry,
            use_grouping=False,
            positive_color=positive_color,
            negative_color=negative_color,
            neutral_color=neutral_color,
        )

    ndx_entry = payload.get("NDX") or payload.get("^NDX")
    if not _entry_is_fresh(
        "NDX",
        ndx_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        ndx_entry = _build_proxy_entry(payload.get("QQQ"), 37.5)
    if _entry_is_fresh(
        "NDX",
        ndx_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        presentations["ndx"] = _build_index_presentation(
            ndx_entry,
            use_grouping=True,
            positive_color=positive_color,
            negative_color=negative_color,
            neutral_color=neutral_color,
        )

    dji_entry = payload.get("$DJI")
    if not _entry_is_fresh(
        "$DJI",
        dji_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        dji_entry = _build_proxy_entry(payload.get("DIA"), dji_from_dia_multiplier)
    if _entry_is_fresh(
        "$DJI",
        dji_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        presentations["dji"] = _build_index_presentation(
            dji_entry,
            use_grouping=True,
            positive_color=positive_color,
            negative_color=negative_color,
            neutral_color=neutral_color,
        )

    rut_entry = payload.get("RUT") or payload.get("^RUT")
    if not _entry_is_fresh(
        "RUT",
        rut_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        rut_entry = _build_proxy_entry(payload.get("IWM"), 10.0)
    if _entry_is_fresh(
        "RUT",
        rut_entry,
        fetch_time=fetch_time,
        now_et=now_et,
        market_hours_open=market_hours_open,
        realtime_quote_max_age_seconds=realtime_quote_max_age_seconds,
    ):
        presentations["rut"] = _build_index_presentation(
            rut_entry,
            use_grouping=True,
            positive_color=positive_color,
            negative_color=negative_color,
            neutral_color=neutral_color,
        )

    return presentations
