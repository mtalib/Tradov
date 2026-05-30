#!/usr/bin/env python3
"""Focused regressions for after-hours spread MTM freezing in R08."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from Spyder.SpyderD_Strategies.SpyderD00_StrategyConstants import StrategyLifecycleState
from Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker import PaperTradingQtWorker


def test_is_spy_mtm_marking_hours_freezes_at_regular_close_on_friday() -> None:
    worker = PaperTradingQtWorker(initial_capital=100_000.0)
    et_tz = ZoneInfo("America/New_York")

    assert worker._is_spy_mtm_marking_hours(
        datetime(2026, 5, 29, 15, 59, tzinfo=et_tz)
    )
    assert not worker._is_spy_mtm_marking_hours(
        datetime(2026, 5, 29, 16, 0, tzinfo=et_tz)
    )
    assert not worker._is_spy_mtm_marking_hours(
        datetime(2026, 5, 29, 16, 5, tzinfo=et_tz)
    )


def test_mark_spreads_mtm_preserves_last_mark_outside_spy_mtm_marking_hours(
    monkeypatch,
) -> None:
    worker = PaperTradingQtWorker(initial_capital=100_000.0)
    worker._open_spreads = [
        {
            "id": 1,
            "expiration": "2099-01-01",
            "short_strike": 605.0,
            "long_strike": 600.0,
            "option_type": "C",
            "credit": 1.50,
            "qty": 1,
            "last_debit": 0.75,
            "last_short_mid": 1.10,
            "last_long_mid": 0.35,
            "lifecycle_state": StrategyLifecycleState.ENTERED_BY_AI.value,
        }
    ]

    fetch_leg_mids = MagicMock(return_value=(1.15, 0.25))
    close_spread = MagicMock()
    monkeypatch.setattr(worker, "_is_spy_mtm_marking_hours", lambda: False)
    monkeypatch.setattr(worker, "_fetch_leg_mids", fetch_leg_mids)
    monkeypatch.setattr(worker, "_close_paper_credit_spread", close_spread)

    worker._mark_spreads_mtm()

    fetch_leg_mids.assert_not_called()
    close_spread.assert_not_called()
    assert worker._open_spreads[0]["last_debit"] == 0.75
    assert worker._open_spreads[0]["last_short_mid"] == 1.10
    assert worker._open_spreads[0]["last_long_mid"] == 0.35
    assert (
        worker._open_spreads[0]["lifecycle_state"]
        == StrategyLifecycleState.ENTERED_BY_AI.value
    )


def test_mark_spreads_mtm_updates_last_mark_during_spy_mtm_marking_hours(
    monkeypatch,
) -> None:
    worker = PaperTradingQtWorker(initial_capital=100_000.0)
    worker._open_spreads = [
        {
            "id": 1,
            "expiration": "2099-01-01",
            "short_strike": 605.0,
            "long_strike": 600.0,
            "option_type": "C",
            "credit": 1.50,
            "qty": 1,
            "lifecycle_state": StrategyLifecycleState.ENTERED_BY_AI.value,
        }
    ]

    fetch_leg_mids = MagicMock(return_value=(1.15, 0.25))
    close_spread = MagicMock()
    monkeypatch.setattr(worker, "_is_spy_mtm_marking_hours", lambda: True)
    monkeypatch.setattr(worker, "_fetch_leg_mids", fetch_leg_mids)
    monkeypatch.setattr(worker, "_close_paper_credit_spread", close_spread)

    worker._mark_spreads_mtm()

    fetch_leg_mids.assert_called_once_with("2099-01-01", "call", 605.0, 600.0)
    close_spread.assert_not_called()
    assert worker._open_spreads[0]["last_debit"] == pytest.approx(0.9)
    assert worker._open_spreads[0]["last_short_mid"] == 1.15
    assert worker._open_spreads[0]["last_long_mid"] == 0.25
    assert (
        worker._open_spreads[0]["lifecycle_state"]
        == StrategyLifecycleState.MANAGED_BY_AI.value
    )
