#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU51_OptionTypesAndTime.py
Purpose: Shared option datatypes and timezone-safe ET helpers for SPX/SPXW flows.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


class OptionType(str, Enum):
    """Canonical option type representation."""

    CALL = "call"
    PUT = "put"


class GammaRegime(str, Enum):
    """Dealer-gamma regime used for entry gating."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


def now_et() -> dt.datetime:
    """Return timezone-aware current time in America/New_York."""

    return dt.datetime.now(tz=NY)


def et_time(hour: int, minute: int) -> dt.time:
    """Build an ET-aware time object."""

    return dt.time(hour, minute, tzinfo=NY)


def within_window(start: dt.time, end: dt.time, when: dt.datetime | None = None) -> bool:
    """Return True when `when` falls within [start, end] in ET."""

    when = when or now_et()
    return start <= when.timetz() <= end


@dataclass
class OptionQuote:
    """Normalized options quote payload for strategy/risk consumers."""

    symbol: str
    option_type: OptionType
    strike: float
    bid: float
    ask: float
    delta: float | None
    gamma: float | None = None
    underlying_price: float | None = None

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2.0, 2)


@dataclass
class ShortLeg:
    """One active short option leg monitored by delta-based risk controls."""

    symbol: str
    option_type: OptionType
    strike: float
    entry_delta: float
    quantity: int
    order_tag: str
    opened_at: dt.datetime = field(default_factory=now_et)


@dataclass
class TrancheResult:
    """Summary of one micro-tranche execution attempt."""

    underlying: str
    call_symbol: str
    put_symbol: str
    call_strike: float
    put_strike: float
    net_credit: float
    order_id: int | None
    filled: bool
    tag: str
    timestamp: dt.datetime = field(default_factory=now_et)


def is_spxw_symbol(occ_symbol: str) -> bool:
    """Return True when the OCC option symbol uses the SPXW root."""

    return occ_symbol.upper().startswith("SPXW")


def build_occ_symbol(root: str, expiry: dt.date, option_type: OptionType, strike: float) -> str:
    """Build OCC symbol from root/date/type/strike."""

    cp = "C" if option_type is OptionType.CALL else "P"
    strike_int = int(round(strike * 1000))
    return f"{root.upper()}{expiry:%y%m%d}{cp}{strike_int:08d}"
