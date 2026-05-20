#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG69_LiveDataStatusHelper.py
Purpose: Pure helper for live-equivalent data-status evaluation
"""

from __future__ import annotations


LIVE_EQUIVALENT_DATA_STATUSES = frozenset(
    {
        "LIVE",
        "LIVE DATA",
        "LIVE - REAL",
        "REAL",
        "REAL-TIME",
        "REAL TIME",
        "PAPER",
    }
)


def is_live_equivalent_data_status(value: object) -> bool:
    """Return whether a data-status label is treated as live-equivalent."""
    normalized = str(value or "").strip().upper()
    return normalized in LIVE_EQUIVALENT_DATA_STATUSES
