#!/usr/bin/env python3
"""Focused D40 regressions for SPXW-only option entry policy."""

from __future__ import annotations

from datetime import datetime

from Spyder.SpyderA_Core.SpyderA09_EventCalendarService import EventCalendarService
from Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor import MicroTrancheExecutor
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import GammaRegime, NY


class _GammaPositive:
    def current_regime(self) -> GammaRegime:
        return GammaRegime.POSITIVE


class _BrokerStub:
    trading_mode = "paper"

    def __init__(self, *, session_date: str, chain: list[dict]):
        self._session_date = session_date
        self._chain = list(chain)
        self.place_calls: list[dict] = []

    def get_option_expirations(self, underlying: str) -> dict:
        _ = underlying
        return {"expirations": {"date": [self._session_date]}}

    def get_option_chain_with_greeks(self, underlying: str, expiration: str) -> list[dict]:
        _ = (underlying, expiration)
        return list(self._chain)

    def place_multileg_order(self, **kwargs):
        self.place_calls.append(dict(kwargs))
        return {"order": {"id": "101"}}


def _build_chain(root: str) -> list[dict]:
    return [
        {
            "symbol": f"{root}260618C05315000",
            "option_type": "call",
            "strike": 5315.0,
            "bid": 1.40,
            "ask": 1.50,
            "greeks": {"delta": 0.10},
        },
        {
            "symbol": f"{root}260618C05320000",
            "option_type": "call",
            "strike": 5320.0,
            "bid": 0.60,
            "ask": 0.70,
            "greeks": {"delta": 0.05},
        },
        {
            "symbol": f"{root}260618P05285000",
            "option_type": "put",
            "strike": 5285.0,
            "bid": 1.30,
            "ask": 1.40,
            "greeks": {"delta": -0.10},
        },
        {
            "symbol": f"{root}260618P05280000",
            "option_type": "put",
            "strike": 5280.0,
            "bid": 0.50,
            "ask": 0.60,
            "greeks": {"delta": -0.05},
        },
    ]


def test_plan_once_rejects_non_spxw_option_entry_symbols(monkeypatch) -> None:
    fixed_now = datetime(2026, 6, 18, 11, 0, tzinfo=NY)
    monkeypatch.setattr(
        "Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor.now_et",
        lambda: fixed_now,
    )

    broker = _BrokerStub(session_date=fixed_now.date().isoformat(), chain=_build_chain("SPY"))
    executor = MicroTrancheExecutor(
        broker_client=broker,
        gamma_engine=_GammaPositive(),
        calendar_service=EventCalendarService(),
        underlying_symbol="SPX",
        option_root="SPXW",
        min_net_credit=0.05,
    )

    plan, short_legs = executor.plan_once()

    assert plan is None
    assert short_legs == []


def test_evaluate_once_accepts_spxw_option_entry_symbols(monkeypatch) -> None:
    fixed_now = datetime(2026, 6, 18, 11, 0, tzinfo=NY)
    monkeypatch.setattr(
        "Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor.now_et",
        lambda: fixed_now,
    )

    broker = _BrokerStub(session_date=fixed_now.date().isoformat(), chain=_build_chain("SPXW"))
    executor = MicroTrancheExecutor(
        broker_client=broker,
        gamma_engine=_GammaPositive(),
        calendar_service=EventCalendarService(),
        underlying_symbol="SPX",
        option_root="SPXW",
        min_net_credit=0.05,
    )

    result, short_legs = executor.evaluate_once()

    assert result is not None
    assert result.filled is True
    assert len(short_legs) == 2
    assert all(leg.symbol.startswith("SPXW") for leg in short_legs)
    assert len(broker.place_calls) == 1
    submitted = broker.place_calls[0]
    assert submitted["symbol"] == "SPX"
    assert submitted["order_type"] == "credit"
    assert all(leg.option_symbol.startswith("SPXW") for leg in submitted["legs"])
