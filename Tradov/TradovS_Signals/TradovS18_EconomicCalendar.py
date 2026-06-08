#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovS_Signals
Module: TradovS18_EconomicCalendar.py
Purpose: Track tier-1 macro-economic events and expose a stand-down gate that
         suppresses NEW entry signals within a configurable window around each
         event.  Closing trades always bypass this gate.

The event list is seeded from two sources (first wins per event):
  1. ``config/economic_calendar.json`` — user-maintained explicit date/time list
  2. Hardcoded FOMC announcement dates for 2025–2026 plus monthly heuristics
     for CPI, NFP, PCE, PPI.

Env vars:
  TRADOV_ECO_STAND_DOWN_BEFORE_MIN   – minutes before event to start stand-down
                                       (default 30)
  TRADOV_ECO_STAND_DOWN_AFTER_MIN    – minutes after event to end stand-down
                                       (default 30)
  TRADOV_ECO_CALENDAR_GATE_ENABLED   – set to "0" to disable the gate
                                       (default "1" — enabled)

Outputs (keys returned by :meth:`EconomicCalendar.get_snapshot`):
  ECO_STAND_DOWN          – bool, True when inside a stand-down window
  ECO_NEXT_EVENT_NAME     – str, name of the upcoming tier-1 event
  ECO_NEXT_EVENT_MINUTES  – float, minutes until that event (negative = past)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger

logger = TradovLogger.get_logger(__name__)

# ---------------------------------------------------------------------------
# Public snapshot keys
# ---------------------------------------------------------------------------
ECO_STAND_DOWN = "ECO_STAND_DOWN"
ECO_NEXT_EVENT_NAME = "ECO_NEXT_EVENT_NAME"
ECO_NEXT_EVENT_MINUTES = "ECO_NEXT_EVENT_MINUTES"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_BEFORE_MIN = int(os.getenv("TRADOV_ECO_STAND_DOWN_BEFORE_MIN", "30"))
_AFTER_MIN = int(os.getenv("TRADOV_ECO_STAND_DOWN_AFTER_MIN", "30"))
_GATE_ENABLED = os.getenv("TRADOV_ECO_CALENDAR_GATE_ENABLED", "1") != "0"

# Config override path relative to workspace root
_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "economic_calendar.json"

# ---------------------------------------------------------------------------
# Eastern Time helpers
# ---------------------------------------------------------------------------
try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:
    # Fallback: US/Eastern UTC offset (approximate; no DST correction)
    _ET = timezone(timedelta(hours=-5))  # type: ignore[assignment]


def _now_et() -> datetime:
    """Return the current wall-clock time in US/Eastern."""
    return datetime.now(tz=_ET)


def _make_et(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Build a timezone-aware datetime in US/Eastern."""
    return datetime(year, month, day, hour, minute, tzinfo=_ET)


# ---------------------------------------------------------------------------
# Hardcoded tier-1 event schedule
# ---------------------------------------------------------------------------
# Each entry: (year, month, day, hour_et, minute_et, event_name)
# All times are US Eastern.

_FOMC_EVENTS: list[tuple[int, int, int, int, int, str]] = [
    # 2025 FOMC announcement dates — announcement at 14:00 ET
    (2025, 1, 29, 14, 0, "FOMC"),
    (2025, 3, 19, 14, 0, "FOMC"),
    (2025, 5,  7, 14, 0, "FOMC"),
    (2025, 6, 18, 14, 0, "FOMC"),
    (2025, 7, 30, 14, 0, "FOMC"),
    (2025, 9, 17, 14, 0, "FOMC"),
    (2025, 10, 29, 14, 0, "FOMC"),
    (2025, 12, 10, 14, 0, "FOMC"),
    # 2026 FOMC announcement dates (projected; update when Fed publishes)
    (2026, 1, 28, 14, 0, "FOMC"),
    (2026, 3, 18, 14, 0, "FOMC"),
    (2026, 4, 29, 14, 0, "FOMC"),
    (2026, 6, 17, 14, 0, "FOMC"),
    (2026, 7, 29, 14, 0, "FOMC"),
    (2026, 9, 16, 14, 0, "FOMC"),
    (2026, 10, 28, 14, 0, "FOMC"),
    (2026, 12,  9, 14, 0, "FOMC"),
]


def _first_friday(year: int, month: int) -> date:
    """Return the first Friday of the given year/month."""
    d = date(year, month, 1)
    delta = (4 - d.weekday()) % 7   # 4 == Friday
    return d + timedelta(days=delta)


def _last_friday(year: int, month: int) -> date:
    """Return the last Friday of the given year/month."""
    # start from the 28th (always in the month) and walk forward to end of month
    # then find the last Friday
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    delta = (last_day.weekday() - 4) % 7   # days past the last Friday
    return last_day - timedelta(days=delta)


def _monthly_heuristic_events(year: int, month: int) -> list[tuple[int, int, int, int, int, str]]:
    """Generate approximate event dates for CPI, NFP, PCE, PPI for year/month.

    These are approximations.  For exact dates load ``config/economic_calendar.json``.
    """
    events: list[tuple[int, int, int, int, int, str]] = []

    # NFP — typically first Friday at 08:30 ET
    nfp = _first_friday(year, month)
    events.append((nfp.year, nfp.month, nfp.day, 8, 30, "NFP"))

    # CPI — typically 2nd or 3rd Wednesday; heuristic: 10th–15th, nearest Wednesday
    # Approximate as the Wednesday of the week containing the 13th
    cpi_anchor = date(year, month, 13)
    days_to_wed = (2 - cpi_anchor.weekday()) % 7
    cpi = cpi_anchor + timedelta(days=days_to_wed)
    events.append((cpi.year, cpi.month, cpi.day, 8, 30, "CPI"))

    # PPI — typically one day before CPI (Tuesday of the same week)
    ppi = cpi - timedelta(days=1)
    events.append((ppi.year, ppi.month, ppi.day, 8, 30, "PPI"))

    # PCE — typically last Friday at 08:30 ET
    pce = _last_friday(year, month)
    events.append((pce.year, pce.month, pce.day, 8, 30, "PCE"))

    return events


def _build_event_list(horizon_months: int = 3) -> list[datetime]:
    """Build sorted list of tier-1 event datetimes covering the next N months."""
    now = _now_et()
    events: list[datetime] = []

    # FOMC
    for (yr, mo, dy, hr, mn, _nm) in _FOMC_EVENTS:
        events.append(_make_et(yr, mo, dy, hr, mn))

    # Monthly heuristics for the rolling window
    for offset in range(-1, horizon_months + 1):
        mo = now.month + offset
        yr = now.year
        while mo > 12:
            mo -= 12
            yr += 1
        while mo < 1:
            mo += 12
            yr -= 1
        for (ey, em, ed, eh, emn, _en) in _monthly_heuristic_events(yr, mo):
            events.append(_make_et(ey, em, ed, eh, emn))

    events.sort()
    return events


def _load_config_events() -> list[datetime]:
    """Load explicit event datetimes from the config file if it exists.

    Expected JSON schema::

        [
          {"name": "CPI", "datetime_et": "2025-06-11T08:30:00"},
          ...
        ]

    Returns an empty list if the file is absent or malformed.
    """
    if not _CONFIG_FILE.exists():
        return []

    try:
        raw: list[dict] = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        parsed: list[datetime] = []
        for entry in raw:
            dt_str = entry.get("datetime_et", "")
            if not dt_str:
                continue
            naive = datetime.fromisoformat(dt_str)
            aware = naive.replace(tzinfo=_ET)
            parsed.append(aware)
        parsed.sort()
        logger.debug("S18: loaded %d events from config file", len(parsed))
        return parsed
    except Exception as exc:
        logger.warning("S18: failed to parse economic_calendar.json: %s", exc)
        return []


# ---------------------------------------------------------------------------
# EconomicCalendar
# ---------------------------------------------------------------------------

class EconomicCalendar:
    """Track tier-1 economic events and expose a stand-down gate for D31.

    The event list is rebuilt lazily once per calendar day so it stays
    current without requiring a restart.  All public methods are thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[datetime] = []
        self._event_labels: list[str] = []
        self._built_date: date | None = None
        self.gate_enabled: bool = _GATE_ENABLED
        self.before_min: int = _BEFORE_MIN
        self.after_min: int = _AFTER_MIN

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict[str, Any]:
        """Return a snapshot dict for S07 metric emission.

        Returns:
            dict with ECO_STAND_DOWN, ECO_NEXT_EVENT_NAME,
            ECO_NEXT_EVENT_MINUTES.
        """
        self._ensure_events_built()
        now = _now_et()
        stand_down, next_name, next_minutes = self._evaluate(now)

        return {
            ECO_STAND_DOWN: stand_down,
            ECO_NEXT_EVENT_NAME: next_name,
            ECO_NEXT_EVENT_MINUTES: next_minutes,
        }

    def is_stand_down_active(self) -> tuple[bool, str]:
        """Check whether entries should be suppressed right now.

        Returns:
            ``(True, reason_str)`` if inside a stand-down window, else
            ``(False, "")``.
        """
        if not self.gate_enabled:
            return False, ""

        self._ensure_events_built()
        now = _now_et()
        stand_down, next_name, next_minutes = self._evaluate(now)

        if stand_down:
            if next_minutes < 0:
                # We are inside the post-event window
                reason = f"eco_standdown:{next_name}_T{int(abs(next_minutes))}m_ago"
            else:
                reason = f"eco_standdown:{next_name}_in_{int(next_minutes)}m"
            return True, reason

        return False, ""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_events_built(self) -> None:
        """Rebuild event list once per calendar day."""
        today = _now_et().date()
        with self._lock:
            if self._built_date == today:
                return
            self._rebuild_events()
            self._built_date = today

    def _rebuild_events(self) -> None:
        """Build the combined event list from config + hardcoded schedule."""
        config_events = _load_config_events()

        # Build heuristic list and label each event
        heuristic_raw: list[tuple[int, int, int, int, int, str]] = list(_FOMC_EVENTS)
        now = _now_et()
        for offset in range(-1, 4):
            mo = now.month + offset
            yr = now.year
            while mo > 12:
                mo -= 12
                yr += 1
            while mo < 1:
                mo += 12
                yr -= 1
            heuristic_raw.extend(_monthly_heuristic_events(yr, mo))

        heuristic_dts: list[datetime] = [
            _make_et(yr, mo, dy, hr, mn) for (yr, mo, dy, hr, mn, _) in heuristic_raw
        ]
        heuristic_labels: list[str] = [nm for (*_, nm) in heuristic_raw]

        # Config events take precedence; remove heuristic events on days that
        # appear in the config (avoid duplicates around the same event).
        config_dates = {e.date() for e in config_events}
        filtered_heuristic: list[tuple[datetime, str]] = [
            (dt, lbl)
            for dt, lbl in zip(heuristic_dts, heuristic_labels, strict=False)
            if dt.date() not in config_dates
        ]

        combined: list[tuple[datetime, str]] = (
            [(e, "event") for e in config_events]
            + filtered_heuristic
        )
        combined.sort(key=lambda x: x[0])

        # Keep only events within a rolling ±60-day window
        now_ts = _now_et()
        cutoff_past = now_ts - timedelta(days=1)
        cutoff_future = now_ts + timedelta(days=60)
        combined = [
            (dt, lbl) for dt, lbl in combined
            if cutoff_past <= dt <= cutoff_future
        ]

        self._events = [dt for dt, _ in combined]
        self._event_labels = [lbl for _, lbl in combined]
        logger.debug("S18: rebuilt event list — %d events", len(self._events))

    def _evaluate(self, now: datetime) -> tuple[bool, str, float]:
        """Check stand-down status against the event list.

        Args:
            now: Current time (timezone-aware ET).

        Returns:
            ``(is_stand_down, next_event_name, minutes_to_next_event)``.
            *minutes_to_next_event* is negative if the most recent event
            already passed but we are still inside the post-event window.
        """
        events = self._events
        labels = self._event_labels

        if not events:
            return False, "", float("nan")

        after_td = timedelta(minutes=self.after_min)

        # Find the first upcoming event (or most recently past event)
        upcoming_dt: datetime | None = None
        upcoming_lbl: str = ""
        past_dt: datetime | None = None
        past_lbl: str = ""

        for dt, lbl in zip(events, labels, strict=False):
            if dt >= now:
                if upcoming_dt is None:
                    upcoming_dt = dt
                    upcoming_lbl = lbl
            else:
                # Most recent past event
                past_dt = dt
                past_lbl = lbl

        # Check post-event stand-down window
        if past_dt is not None:
            elapsed = now - past_dt
            if elapsed <= after_td:
                elapsed_min = elapsed.total_seconds() / 60.0
                return True, past_lbl, -elapsed_min

        # Check pre-event stand-down window
        if upcoming_dt is not None:
            time_to = upcoming_dt - now
            time_to_min = time_to.total_seconds() / 60.0
            if time_to_min <= self.before_min:
                return True, upcoming_lbl, time_to_min
            return False, upcoming_lbl, time_to_min

        return False, "", float("nan")


# ---------------------------------------------------------------------------
# Module-level singleton factory
# ---------------------------------------------------------------------------

_calendar_instance: EconomicCalendar | None = None
_calendar_lock = threading.Lock()


def get_economic_calendar() -> EconomicCalendar:
    """Return the module-level singleton :class:`EconomicCalendar`.

    Thread-safe double-checked locking; safe to call from any thread.
    """
    global _calendar_instance
    if _calendar_instance is not None:
        return _calendar_instance

    with _calendar_lock:
        if _calendar_instance is None:
            _calendar_instance = EconomicCalendar()
    return _calendar_instance
