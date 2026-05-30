#!/usr/bin/env python3
"""Focused regressions for D14 calendar-spread signal serialization and lifecycle."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pandas as pd

from Spyder.SpyderA_Core.SpyderA05_EventManager import DateTimeEncoder
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile
from Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread import (
    CalendarLeg,
    CalendarSetup,
    CalendarSpreadStrategy,
    CalendarType,
    OptionType,
    TermStructure,
)


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None


def _build_strategy() -> CalendarSpreadStrategy:
    return CalendarSpreadStrategy(
        event_manager=_StubEventManager(),
        risk_profile=RiskProfile(account_size=100000),
        config={"symbol": "SPY"},
    )


def _build_setup() -> CalendarSetup:
    return CalendarSetup(
        calendar_type=CalendarType.CALL_CALENDAR,
        near_leg=CalendarLeg(
            option_type=OptionType.CALL,
            strike=600.0,
            expiry=datetime.now(UTC) + timedelta(days=14),
            position=-1,
            contracts=1,
            iv=0.20,
            premium=2.0,
            delta=0.0,
            gamma=0.0,
            vega=0.0,
            theta=0.0,
        ),
        far_leg=CalendarLeg(
            option_type=OptionType.CALL,
            strike=600.0,
            expiry=datetime.now(UTC) + timedelta(days=42),
            position=1,
            contracts=1,
            iv=0.25,
            premium=4.0,
            delta=0.0,
            gamma=0.0,
            vega=0.0,
            theta=0.0,
        ),
        time_spread=28,
        net_debit=200.0,
        max_profit=350.0,
        breakeven_points=[596.0, 606.0],
        iv_skew=0.05,
        term_structure=TermStructure.CONTANGO,
        entry_iv_rank=40.0,
        probability_profit=0.62,
    )


def test_calendar_spread_signal_payload_is_json_serializable() -> None:
    strategy = _build_strategy()
    signal = strategy._create_trading_signal(
        _build_setup(),
        pd.DataFrame({"close": [599.0, 601.0]}),
    )

    assert signal is not None
    payload = signal.to_dict()
    json.dumps(payload, cls=DateTimeEncoder)

    setup_payload = payload["metadata"]["setup"]
    assert setup_payload["calendar_type"] == CalendarType.CALL_CALENDAR.value
    assert setup_payload["near_leg"]["option_type"] == OptionType.CALL.value
    assert setup_payload["far_leg"]["position"] == 1


def test_calendar_spread_add_position_rehydrates_setup_for_management() -> None:
    strategy = _build_strategy()
    signal = strategy._create_trading_signal(
        _build_setup(),
        pd.DataFrame({"close": [599.0, 601.0]}),
    )

    assert signal is not None
    position_id = strategy.add_position(signal)
    position = strategy.active_positions[position_id]

    assert position.setup.calendar_type == CalendarType.CALL_CALENDAR
    assert position.setup.near_leg.option_type == OptionType.CALL

    signals = strategy.manage_positions(pd.DataFrame({"close": [601.0, 602.0]}))

    assert isinstance(signals, list)


def test_calendar_spread_exit_signal_preserves_serialized_setup() -> None:
    strategy = _build_strategy()
    signal = strategy._create_trading_signal(
        _build_setup(),
        pd.DataFrame({"close": [599.0, 601.0]}),
    )

    assert signal is not None
    position_id = strategy.add_position(signal)
    exit_signal = strategy._create_exit_signal(strategy.active_positions[position_id], "near_expiry")

    payload = exit_signal.to_dict()
    json.dumps(payload, cls=DateTimeEncoder)

    assert payload["metadata"]["action"] == "close"
    assert payload["metadata"]["setup"]["near_leg"]["option_type"] == OptionType.CALL.value
    assert payload["metadata"]["setup"]["far_leg"]["position"] == 1
