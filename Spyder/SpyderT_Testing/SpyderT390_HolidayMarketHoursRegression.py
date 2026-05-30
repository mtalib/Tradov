#!/usr/bin/env python3
"""Regression tests for holiday-aware market-hours helpers across GUI/runtime layers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytz

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI import SpyderG18_MarketDataWorker as g18
from Spyder.SpyderR_Runtime import SpyderR04_LiveEngine as r04
from Spyder.SpyderR_Runtime import SpyderR05_LivenessMonitor as r05
from Spyder.SpyderU_Utilities import SpyderU03_DateTimeUtils as u03


ET = pytz.timezone("US/Eastern")
HOLIDAY_TS = ET.localize(datetime(2026, 5, 25, 10, 21))


class _FixedHolidayDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return HOLIDAY_TS.replace(tzinfo=None)
        return HOLIDAY_TS.astimezone(tz)


class _StubEventManager:
    def subscribe(self, *_args, **_kwargs):
        return None

    def emit(self, *_args, **_kwargs):
        return None


def test_g05_is_market_hours_false_on_holiday() -> None:
    assert g05.is_market_hours(HOLIDAY_TS) is False


def test_g18_is_market_hours_false_on_holiday() -> None:
    assert g18.is_market_hours(HOLIDAY_TS) is False


def test_u03_is_market_open_false_on_holiday() -> None:
    assert u03.is_market_open(HOLIDAY_TS) is False


def test_u03_trading_time_utils_false_on_holiday() -> None:
    assert u03.TradingTimeUtils.is_market_hours(HOLIDAY_TS) is False


def test_r04_is_market_open_false_on_holiday(monkeypatch) -> None:
    monkeypatch.setattr(r04, "datetime", _FixedHolidayDateTime)
    engine = r04.LiveEngine.__new__(r04.LiveEngine)
    assert engine._is_market_open() is False


def test_r05_is_market_hours_false_on_holiday(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(r05, "datetime", _FixedHolidayDateTime)
    monitor = r05.LivenessMonitor(
        event_manager=_StubEventManager(),
        engine=SimpleNamespace(),
        heartbeat_path=str(tmp_path / "heartbeat.json"),
        healthz_port=0,
    )
    assert monitor._is_market_hours() is False
