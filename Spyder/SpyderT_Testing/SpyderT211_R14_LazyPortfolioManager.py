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


def test_exit_monitor_uses_authoritative_positions_provider() -> None:
    event_manager = _EventManagerStub()
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"iron_condor": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1.0,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
    )

    monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    position_view = strategy.check_exit.call_args.args[0]
    assert position_view.strategy_id == "iron_condor"
    assert position_view.cost_basis == 3.50
    assert position_view.current_price == 3.60
    assert monitor.portfolio_manager is None


def test_exit_monitor_authoritative_positions_suppress_stale_portfolio_manager() -> None:
    event_manager = _EventManagerStub()
    strategy = MagicMock()

    fake_pm = SimpleNamespace(
        portfolio_positions={
            "SPY_STALE": {
                "symbol": "SPY_STALE",
                "quantity": 1.0,
                "cost_basis": 2.10,
                "current_price": 2.30,
                "strategy_id": "test_strategy",
            }
        }
    )

    monitor = create_exit_monitor(
        portfolio_manager=fake_pm,
        strategy_map={"test_strategy": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {},
    )

    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert event_manager.emitted == []


def test_exit_monitor_resolves_semantic_strategy_alias_from_runtime_id() -> None:
    event_manager = _EventManagerStub()
    strategy = MagicMock()
    strategy.check_exit.return_value = None
    strategy.strategy_type = "iron_condor"
    strategy.name = "Iron Condor Strategy"

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"IronCondorAdapter_deadbeef": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1.0,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy_id": "iron_condor",
            }
        },
    )

    monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    assert event_manager.emitted == []
