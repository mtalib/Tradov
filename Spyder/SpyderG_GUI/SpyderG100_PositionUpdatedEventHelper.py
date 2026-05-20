#!/usr/bin/env python3
"""Pure parsing for dashboard POSITION_UPDATED events."""

from __future__ import annotations


def extract_position_update_symbol(event: object) -> str | None:
    """Return the normalized symbol for a POSITION_UPDATED event, if present."""
    event_payload = event
    if hasattr(event, "data") and isinstance(getattr(event, "data", None), dict):
        event_payload = getattr(event, "data")  # noqa: B009

    if not isinstance(event_payload, dict):
        return None

    symbol = str(event_payload.get("symbol") or "").strip()
    if not symbol:
        return None
    return symbol
