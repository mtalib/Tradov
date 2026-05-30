#!/usr/bin/env python3
"""Focused regressions for the Q93 paper-launcher trading-mode gate."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_q93_main_rejects_sandbox_trading_mode(monkeypatch) -> None:
    from Spyder.SpyderQ_Scripts import SpyderQ93_RunPaper as q93

    monkeypatch.setenv("TRADING_MODE", "sandbox")
    monkeypatch.setattr(sys, "argv", ["SpyderQ93_RunPaper", "--once", "--no-market-check"])

    build_harness = MagicMock(side_effect=AssertionError("harness should not be built"))
    market_loop = MagicMock()
    monkeypatch.setattr(q93, "create_paper_trading_harness_from_env", build_harness)
    monkeypatch.setattr(q93, "market_hours_loop", market_loop)

    with pytest.raises(SystemExit) as excinfo:
        q93.main()

    assert str(excinfo.value).startswith(
        "[ERROR] SpyderQ93_RunPaper requires TRADING_MODE=paper"
    )
    build_harness.assert_not_called()
    market_loop.assert_not_called()


def test_run_session_logs_per_adapter_no_entry_details(monkeypatch) -> None:
    from Spyder.SpyderQ_Scripts import SpyderQ93_RunPaper as q93

    harness = MagicMock()
    harness._store.count_snapshots.return_value = 0
    harness.days_remaining.return_value = 30
    harness.start_session.return_value = True
    harness.get_current_metrics.side_effect = [
        {"starting_equity": 100000.0},
        {"current_equity": 100000.0, "trades_filled": 0, "wins": 0, "losses": 0},
    ]
    harness.check_drawdown.return_value = None
    harness.trading_halted = False
    harness.end_session.return_value = SimpleNamespace(
        session_date="2026-05-27",
        daily_pnl=0.0,
        daily_pnl_pct=0.0,
        trades_filled=0,
        trades_placed=0,
        win_rate=0.0,
    )

    strategy_runner = MagicMock()
    strategy_runner.tick.return_value = {
        "spy_price": 600.0,
        "open_positions": 0,
        "opens_this_tick": 0,
        "closes_this_tick": 0,
        "sim_pnl": 0.0,
        "top_no_entry_reason": "BullPutCreditSpread:outside_entry_window",
        "no_entry_reasons_by_adapter": {
            "BullPutCreditSpread": "outside_entry_window",
            "ZeroDTE_IronCondor": "daily_entry_cap",
        },
    }
    strategy_runner.close_all_positions.return_value = 0
    strategy_runner.flush_deferred_sandbox_replay.return_value = None

    log_info = MagicMock()
    monkeypatch.setattr(q93._logger, "info", log_info)
    monkeypatch.setattr(q93._logger, "warning", MagicMock())
    monkeypatch.setattr(q93._logger, "critical", MagicMock())
    monkeypatch.setattr(q93._logger, "exception", MagicMock())

    def stop_after_first_sleep(_seconds: int, stop_flag: list) -> None:
        stop_flag[0] = True

    monkeypatch.setattr(q93, "_interruptible_sleep", stop_after_first_sleep)

    q93.run_session(
        harness=harness,
        heartbeat=1,
        no_market_check=True,
        verbose=True,
        stop_flag=[False],
        strategy_runner=strategy_runner,
    )

    strategy_tick_logs = [
        call for call in log_info.call_args_list if call.args and call.args[0].startswith("Strategy tick —")
    ]
    assert strategy_tick_logs
    strategy_tick_log = strategy_tick_logs[0]
    assert "no_entry=%s details=%s" in strategy_tick_log.args[0]
    assert strategy_tick_log.args[-2] == "BullPutCreditSpread:outside_entry_window"
    assert (
        strategy_tick_log.args[-1]
        == "BullPutCreditSpread:outside_entry_window, ZeroDTE_IronCondor:daily_entry_cap"
    )
