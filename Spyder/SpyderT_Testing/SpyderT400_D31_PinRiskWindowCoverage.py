#!/usr/bin/env python3
"""Focused regressions for D31 post-close pin-risk coverage counting."""

from __future__ import annotations

import importlib
from datetime import datetime
from types import SimpleNamespace


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    orch = mod.StrategyOrchestrator.__new__(mod.StrategyOrchestrator)
    orch.market_data_cache = {}
    return orch


def test_count_at_risk_short_options_ignores_fully_covered_call_butterfly(
    monkeypatch,
) -> None:
    orch = _make_orchestrator()
    session_mod = importlib.import_module(
        "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor"
    )
    monkeypatch.setattr(orch, "_get_spy_last_price", lambda: 750.46)
    monkeypatch.setattr(
        session_mod,
        "get_session_supervisor",
        lambda: SimpleNamespace(
            position_tracker=SimpleNamespace(
                positions={
                    "SPY260527C00748000": {
                        "symbol": "SPY260527C00748000",
                        "quantity": 10,
                    },
                    "SPY260527C00749000": {
                        "symbol": "SPY260527C00749000",
                        "quantity": -20,
                    },
                    "SPY260527C00750000": {
                        "symbol": "SPY260527C00750000",
                        "quantity": 10,
                    },
                }
            )
        ),
    )

    count = orch._count_at_risk_short_options(datetime(2026, 5, 27, 16, 57, 59))

    assert count == 0


def test_count_at_risk_short_options_keeps_uncovered_call_spread_alert(
    monkeypatch,
) -> None:
    orch = _make_orchestrator()
    session_mod = importlib.import_module(
        "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor"
    )
    monkeypatch.setattr(orch, "_get_spy_last_price", lambda: 749.20)
    monkeypatch.setattr(
        session_mod,
        "get_session_supervisor",
        lambda: SimpleNamespace(
            position_tracker=SimpleNamespace(
                positions={
                    "SPY260527C00749000": {
                        "symbol": "SPY260527C00749000",
                        "quantity": -10,
                    },
                    "SPY260527C00750000": {
                        "symbol": "SPY260527C00750000",
                        "quantity": 10,
                    },
                }
            )
        ),
    )

    count = orch._count_at_risk_short_options(datetime(2026, 5, 27, 16, 57, 59))

    assert count == 1


def test_count_at_risk_short_options_ignores_stale_tracker_after_paper_flatten(
    monkeypatch,
) -> None:
    orch = _make_orchestrator()
    session_mod = importlib.import_module(
        "Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor"
    )
    monkeypatch.setattr(orch, "_get_spy_last_price", lambda: 754.60)
    monkeypatch.setattr(
        session_mod,
        "get_session_supervisor",
        lambda: SimpleNamespace(
            mode="paper",
            engine=SimpleNamespace(
                get_active_positions_snapshot=lambda: {},
                _session_db=SimpleNamespace(
                    get_resume_eligible_open_positions=lambda: [],
                ),
            ),
            position_tracker=SimpleNamespace(
                positions={
                    "SPY260528C00754000": {
                        "symbol": "SPY260528C00754000",
                        "quantity": -9,
                    },
                    "SPY260528C00756000": {
                        "symbol": "SPY260528C00756000",
                        "quantity": 3,
                    },
                }
            ),
        ),
    )

    count = orch._count_at_risk_short_options(datetime(2026, 5, 28, 16, 25, 50))

    assert count == 0
