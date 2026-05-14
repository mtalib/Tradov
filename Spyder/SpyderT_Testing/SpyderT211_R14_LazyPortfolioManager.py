#!/usr/bin/env python3
"""Focused regressions for lazy ExitMonitor portfolio manager resolution."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor


class _EventManagerStub:
    def __init__(self) -> None:
        self.emitted: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:  # noqa: ANN003
        self.emitted.append(kwargs)


def test_exit_monitor_without_portfolio_manager_is_safe() -> None:
    event_manager = _EventManagerStub()

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
    )

    monitor._sweep_once()

    assert monitor.portfolio_manager is None
    assert event_manager.emitted == []


def test_exit_monitor_adopts_portfolio_manager_lazily() -> None:
    event_manager = _EventManagerStub()
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    fake_pm = SimpleNamespace(
        portfolio_positions={
            "SPY240620C00500000": {
                "symbol": "SPY240620C00500000",
                "quantity": 1.0,
                "cost_basis": 3.50,
                "current_price": 3.60,
                "unrealized_pnl": 10.0,
                "strategy_id": "test_strategy",
            }
        }
    )

    state = {"portfolio_manager": None}

    def _provider() -> object | None:
        return state["portfolio_manager"]

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"test_strategy": strategy},
        event_manager=event_manager,
        portfolio_manager_provider=_provider,
    )

    monitor._sweep_once()
    strategy.check_exit.assert_not_called()

    state["portfolio_manager"] = fake_pm
    monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    assert monitor.portfolio_manager is fake_pm
