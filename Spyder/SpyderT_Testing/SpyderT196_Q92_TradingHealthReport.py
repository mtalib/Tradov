#!/usr/bin/env python3
"""Focused tests for the Q92 trading-health diagnostics report."""

from __future__ import annotations

import json
from datetime import datetime, timezone, UTC

from Spyder.SpyderQ_Scripts.SpyderQ92_DiagnosticsUtilities import DiagnosticsUtilities


class _FakeSessionDB:
    """Minimal session DB double for trading-health diagnostics tests."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def get_trades_today(self) -> list[dict[str, str]]:
        return [
            {"timestamp": "2026-05-13T14:31:00+00:00"},
            {"timestamp": "2026-05-13T15:01:00+00:00"},
        ]

    def get_latest_snapshot(self) -> dict[str, int]:
        return {"total_trades": 2}


def test_collect_trading_health_surfaces_engine_dispatch_and_drop_artifacts(tmp_path):
    """Q92 trading-health should summarize persisted state from launcher and D31 logs."""
    decision_log = tmp_path / "2026-05-13.jsonl"
    launcher_log = tmp_path / "spyder-desktop-launch.log"
    paper_state = tmp_path / "paper_trading_state.json"

    decision_log.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:05:00+00:00",
                        "event": "dispatch_submitted",
                        "stage": "dispatch",
                        "reason": "dispatch_submitted",
                        "detail": "submitted",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:06:00+00:00",
                        "event": "signal_dropped",
                        "stage": "pre_dispatch",
                        "reason": "duplicate_open_position",
                        "detail": "symbol=SPY;strategy=iron_condor",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:10:00+00:00",
                        "event": "dispatch_submitted",
                        "stage": "dispatch",
                        "reason": "dispatch_submitted",
                        "detail": "submitted_again",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:15:00+00:00",
                        "event": "dispatch_rejected",
                        "stage": "dispatch",
                        "reason": "dispatch_rejected",
                        "detail": "Daily trade limit reached",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:18:00+00:00",
                        "event": "signal_dropped",
                        "stage": "pre_dispatch",
                        "reason": "duplicate_open_position",
                        "detail": "symbol=SPY;strategy=iron_condor",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
                json.dumps(
                    {
                        "ts_utc": "2026-05-13T00:20:00+00:00",
                        "event": "signal_dropped",
                        "stage": "pre_risk",
                        "reason": "session_window_gate",
                        "detail": "session_window:outside_primary_window",
                        "symbol": "SPY",
                        "strategy_id": "iron_condor",
                        "session_id": "paper-test-session",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    launcher_log.write_text(
        "\n".join(
            [
                "2026-05-13 00:10:00,000 - Spyder.SpyderR_Runtime.SpyderR04_LiveEngine - INFO - Market order rejected by live engine: symbol=SPY reason=Daily trade limit reached | pivot_signal=none",
                "2026-05-13 00:45:29,921 - Spyder.SpyderR_Runtime.SpyderR04_LiveEngine - INFO - Paper trading deferred until market open (market_closed)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paper_state.write_text(json.dumps({"_trades_executed": 0}), encoding="utf-8")

    diag = DiagnosticsUtilities()
    report = diag.collect_trading_health(
        run_mode="paper",
        now_utc=datetime(2026, 5, 13, 1, 59, 37, tzinfo=UTC),
        session_window={
            "primary_start_et": "09:20",
            "primary_end_et": "16:15",
            "first_entry_not_before_et": "10:15",
            "zero_dte_no_new_risk_cutoff_et": "14:30",
            "broker_cutoff_et": "16:00",
        },
        recent_event_limit=2,
        max_daily_trades=5,
        decision_log_path=decision_log,
        launcher_log_path=launcher_log,
        paper_state_path=paper_state,
        session_db=_FakeSessionDB(db_path=str(tmp_path / "spyder_paper.db")),
    )

    assert report["run_mode"] == "paper"
    assert report["market_window"]["gate_reason"] == "session_window:outside_primary_window"
    assert report["engine_state"]["state"] == "deferred_until_market_open"
    assert report["engine_state"]["detail"] == "market_closed"
    assert report["engine_state"]["last_rejection_reason"] == "Daily trade limit reached"
    assert report["daily_trades"]["count"] == 2
    assert report["daily_trades"]["max_daily_trades"] == 5
    assert report["daily_trades"]["account_snapshot_total_trades"] == 2
    assert report["last_dispatch_result"]["event"] == "dispatch_rejected"
    assert report["last_dispatch_result"]["detail"] == "Daily trade limit reached"
    assert report["last_drop_reason"]["reason"] == "session_window_gate"
    assert report["recent_decision_flow"]["limit"] == 2
    assert [event["event"] for event in report["recent_decision_flow"]["dispatch"]] == [
        "dispatch_rejected",
        "dispatch_submitted",
    ]
    assert [event["detail"] for event in report["recent_decision_flow"]["dispatch"]] == [
        "Daily trade limit reached",
        "submitted_again",
    ]
    assert [event["detail"] for event in report["recent_decision_flow"]["drops"]] == [
        "session_window:outside_primary_window",
        "symbol=SPY;strategy=iron_condor",
    ]
    assert report["artifacts"]["decision_log"] == str(decision_log)
