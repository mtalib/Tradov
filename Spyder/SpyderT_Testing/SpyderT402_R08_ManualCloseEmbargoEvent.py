#!/usr/bin/env python3
"""Focused regressions for R08 manual-close embargo event emission."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
from Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingQtWorker


pytestmark = pytest.mark.unit


def test_manual_close_emits_position_updated_for_reentry_embargo(monkeypatch) -> None:
    worker = PaperTradingQtWorker(initial_capital=100_000.0)
    worker._save_state = MagicMock()

    event_manager = MagicMock()
    monkeypatch.setattr(
        "Spyder.SpyderA_Core.SpyderA05_EventManager.get_event_manager",
        lambda: event_manager,
    )

    position = {
        "id": 17,
        "qty": 1,
        "credit": 0.55,
        "expiration": "2026-05-29",
        "short_strike": 599.0,
        "long_strike": 598.0,
        "option_type": "C",
        "max_loss_per_contract": 45.0,
        "structure": "BUTTERFLY",
        "underlying_symbol": "SPY",
        "opened_at": 1.0,
    }
    worker._open_spreads = [dict(position)]

    worker._close_paper_credit_spread(position, 0.20, reason="MANUAL_CLOSE", closer="USER")

    event_manager.emit.assert_called_once_with(
        EventType.POSITION_UPDATED,
        {
            "symbol": "SPY",
            "strategy_id": "butterfly",
            "strategy": "butterfly",
            "status": "CLOSED",
            "reason": "manual_close_dashboard",
        },
        source="SpyderR08",
    )
