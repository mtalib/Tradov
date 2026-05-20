#!/usr/bin/env python3
"""Focused regressions for D02 Iron Condor ExitMonitor integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from Spyder.SpyderD_Strategies.SpyderD02_IronCondor import IronCondorStrategy


class _StubEventManager:
    def subscribe(self, *_args, **_kwargs):
        return None

    def emit(self, *_args, **_kwargs):
        return None

    def publish(self, *_args, **_kwargs):
        return None


def _build_position(
    *,
    symbol: str,
    quantity: float,
    cost_basis: float,
    current_price: float,
    unrealized_pnl: float,
    days_to_expiry: int = 30,
    days_held: int = 3,
):
    opened_at = datetime.now(timezone.utc) - timedelta(days=days_held)
    expiration = (datetime.now(timezone.utc) + timedelta(days=days_to_expiry)).date().isoformat()
    return SimpleNamespace(
        symbol=symbol,
        strategy_id='iron_condor',
        quantity=quantity,
        cost_basis=cost_basis,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        raw={
            'opened_at': opened_at.isoformat(),
            'expiration': expiration,
        },
    )


def test_check_exit_closes_profitable_short_leg() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    position = _build_position(
        symbol='SPY260619C00580000',
        quantity=-1.0,
        cost_basis=2.0,
        current_price=1.2,
        unrealized_pnl=80.0,
    )

    assert strategy.check_exit(position) == 'close'


def test_check_exit_holds_short_leg_before_threshold() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    position = _build_position(
        symbol='SPY260619P00540000',
        quantity=-1.0,
        cost_basis=2.0,
        current_price=1.8,
        unrealized_pnl=20.0,
    )

    assert strategy.check_exit(position) is None


def test_check_exit_holds_long_wing_without_time_exit() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    position = _build_position(
        symbol='SPY260619P00530000',
        quantity=1.0,
        cost_basis=0.5,
        current_price=0.1,
        unrealized_pnl=-40.0,
    )

    assert strategy.check_exit(position) is None


def test_check_exit_closes_any_leg_near_expiry() -> None:
    strategy = IronCondorStrategy(event_manager=_StubEventManager(), config={})
    position = _build_position(
        symbol='SPY260521P00530000',
        quantity=1.0,
        cost_basis=0.5,
        current_price=0.05,
        unrealized_pnl=-45.0,
        days_to_expiry=5,
    )

    assert strategy.check_exit(position) == 'close'


def test_days_to_expiry_uses_et_date_source(monkeypatch) -> None:
    monkeypatch.setattr(
        IronCondorStrategy,
        '_now_et',
        staticmethod(lambda: datetime(2026, 5, 20, 10, 30, tzinfo=timezone.utc)),
    )

    assert IronCondorStrategy._days_to_expiry('2026-05-21', 'SPY260521P00530000') == 1