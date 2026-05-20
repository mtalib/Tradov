#!/usr/bin/env python3
"""Focused tests for R12 paper ExitMonitor authoritative-position wiring."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


def test_r12_start_exit_monitor_uses_engine_positions_for_paper(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: True,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    position_view = strategy.check_exit.call_args.args[0]
    assert position_view.strategy_id == "iron_condor"
    assert position_view.cost_basis == 3.50
    assert position_view.current_price == 3.60
    assert supervisor.exit_monitor.portfolio_manager is None


def test_r12_start_exit_monitor_suppresses_paper_positions_after_hours(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: False,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_not_called()
