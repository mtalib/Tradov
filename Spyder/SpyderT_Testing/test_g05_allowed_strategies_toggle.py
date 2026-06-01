#!/usr/bin/env python3
"""Focused regression for reversible in-session ALLOWED STRATEGIES filtering."""

from __future__ import annotations

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _FakeStrategy:
    pass


def test_g05_allowed_strategies_toggle_restores_reenabled_strategy_without_restart() -> None:
    orchestrator = SimpleNamespace(
        lean_strategy_allowlist={
            "ZeroHFT",
            "ZeroHFTStrategy",
            "IronCondor",
            "IronCondorStrategy",
        },
        available_strategies={
            "ZeroHFT": _FakeStrategy,
            "IronCondor": _FakeStrategy,
        },
    )
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._session_supervisor = SimpleNamespace(orchestrator=orchestrator)

    applied_narrow = dashboard._apply_allowed_strategies_to_active_orchestrator(("ZeroHFT",))

    assert applied_narrow is True
    assert orchestrator.available_strategies == {"ZeroHFT": _FakeStrategy}

    applied_reenable = dashboard._apply_allowed_strategies_to_active_orchestrator(
        ("ZeroHFT", "IronCondor")
    )

    assert applied_reenable is True
    assert set(orchestrator.available_strategies.keys()) == {"ZeroHFT", "IronCondor"}
