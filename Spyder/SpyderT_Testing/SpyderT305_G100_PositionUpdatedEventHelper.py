#!/usr/bin/env python3
"""Focused tests for G100 POSITION_UPDATED event helper."""

from __future__ import annotations

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
from Spyder.SpyderG_GUI.SpyderG100_PositionUpdatedEventHelper import (
    extract_position_update_symbol,
)


def test_extract_position_update_symbol_accepts_event_dataclass_payload() -> None:
    event = Event(
        event_type=EventType.POSITION_UPDATED,
        source="PositionTracker",
        data={"symbol": "SPY", "quantity": -1, "fill_price": 733.8771},
    )

    assert extract_position_update_symbol(event) == "SPY"


def test_extract_position_update_symbol_rejects_blank_or_missing_symbol() -> None:
    assert extract_position_update_symbol({"symbol": "   "}) is None
    assert extract_position_update_symbol({"quantity": 1}) is None