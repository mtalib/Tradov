#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA09_EventCalendarService.py
Purpose: Entry halt/caution decisions for SPX/SPXW around macro events.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class EntryDecision:
    """Policy decision for whether a new entry is allowed."""

    halt: bool
    caution: bool = False
    reason: str = ""


@dataclass
class EventCalendarService:
    """Store and evaluate event-driven entry restrictions."""

    hard_halt_dates: set[dt.date] = field(default_factory=set)
    caution_dates: set[dt.date] = field(default_factory=set)
    skip_caution_days: bool = False

    def add_fomc(self, *dates: dt.date) -> None:
        self.hard_halt_dates.update(dates)

    def add_data_release(self, *dates: dt.date) -> None:
        self.caution_dates.update(dates)

    def entry_decision(self, day: dt.date) -> EntryDecision:
        if day in self.hard_halt_dates:
            return EntryDecision(halt=True, reason="FOMC or hard-halt event")
        if day in self.caution_dates:
            if self.skip_caution_days:
                return EntryDecision(halt=True, reason="Major data release (skip mode)")
            return EntryDecision(halt=False, caution=True, reason="Major data release")
        return EntryDecision(halt=False)

    def load_from_provider(self, events: list[dict]) -> None:
        """Ingest a simple provider payload: {'date': ISO_DATE, 'type': EVENT}."""

        hard_types = {"FOMC", "FOMC_RATE_DECISION"}
        for event in events:
            raw_date = event.get("date")
            if not raw_date:
                continue
            try:
                day = dt.date.fromisoformat(str(raw_date))
            except ValueError:
                continue
            event_type = str(event.get("type") or "").upper()
            if event_type in hard_types:
                self.hard_halt_dates.add(day)
            else:
                self.caution_dates.add(day)
