#!/usr/bin/env python3
"""Focused tests for G05 paper risk-limit mapping integration."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _RiskConfig:
    def __init__(self, *, risk_limits, enable_real_time_monitoring):
        self.risk_limits = risk_limits
        self.enable_real_time_monitoring = enable_real_time_monitoring


def test_build_paper_risk_manager_uses_helper_mapping(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.current_risk_params = {"global": {"max_buying_power": 50}}
    dash.tradier_client = object()
    dash.logger = SimpleNamespace(warning=MagicMock())

    helper_calls: list[dict[str, object]] = []
    config_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_paper_risk_limit_mapping_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            risk_limits={"max_total_exposure": 50_000.0},
            warning_message=None,
        ),
    )

    def _risk_config(*, risk_limits, enable_real_time_monitoring):
        config_calls.append(
            {
                "risk_limits": risk_limits,
                "enable_real_time_monitoring": enable_real_time_monitoring,
            }
        )
        return _RiskConfig(
            risk_limits=risk_limits,
            enable_real_time_monitoring=enable_real_time_monitoring,
        )

    created_manager = SimpleNamespace()

    def _risk_manager(*, config, connect_api, order_manager, tradier_client):
        created_manager.config = config
        created_manager.connect_api = connect_api
        created_manager.order_manager = order_manager
        created_manager.tradier_client = tradier_client
        return created_manager

    monkeypatch.setitem(
        g05.sys.modules,
        "Spyder.SpyderE_Risk.SpyderE01_RiskManager",
        SimpleNamespace(
            DEFAULT_RISK_LIMITS={"baseline": 1},
            RiskConfig=_risk_config,
            RiskManager=_risk_manager,
        ),
    )

    manager = SpyderTradingDashboard._build_paper_risk_manager(dash, initial_capital=100_000.0)

    assert helper_calls == [
        {
            "default_risk_limits": {"baseline": 1},
            "current_risk_params": {"global": {"max_buying_power": 50}},
            "initial_capital": 100_000.0,
        }
    ]
    assert config_calls == [
        {
            "risk_limits": {"max_total_exposure": 50_000.0},
            "enable_real_time_monitoring": False,
        }
    ]
    assert manager is created_manager
    assert manager.tradier_client is dash.tradier_client
    dash.logger.warning.assert_not_called()


def test_build_paper_risk_manager_logs_helper_warning(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.current_risk_params = {"global": {"max_daily_loss": "oops"}}
    dash.tradier_client = object()
    dash.logger = SimpleNamespace(warning=MagicMock())

    monkeypatch.setattr(
        g05,
        "build_paper_risk_limit_mapping_plan",
        lambda **_kwargs: SimpleNamespace(
            risk_limits={"baseline": 1},
            warning_message="Could not map G09 params to E01 limits: bad value",
        ),
    )
    monkeypatch.setitem(
        g05.sys.modules,
        "Spyder.SpyderE_Risk.SpyderE01_RiskManager",
        SimpleNamespace(
            DEFAULT_RISK_LIMITS={"baseline": 1},
            RiskConfig=lambda **kwargs: SimpleNamespace(**kwargs),
            RiskManager=lambda **kwargs: SimpleNamespace(**kwargs),
        ),
    )

    SpyderTradingDashboard._build_paper_risk_manager(dash, initial_capital=100_000.0)

    dash.logger.warning.assert_any_call("Could not map G09 params to E01 limits: bad value")
