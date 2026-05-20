#!/usr/bin/env python3
"""Focused tests for G64 readiness connection refresh helper."""

from Spyder.SpyderG_GUI.SpyderG64_ReadinessConnectionRefreshHelper import (
    build_readiness_connection_refresh_plan,
)


def test_build_readiness_connection_refresh_plan_preserves_cached_connected_state() -> None:
    plan = build_readiness_connection_refresh_plan(
        cached_api=True,
        cached_mkt=False,
        fresh_connected=True,
        fresh_mode="PAPER",
    )

    assert plan.api_connected is True
    assert plan.mkt_data_connected is False
    assert plan.connection_status is None
    assert plan.market_data_status is None


def test_build_readiness_connection_refresh_plan_promotes_connected_paper_probe() -> None:
    plan = build_readiness_connection_refresh_plan(
        cached_api=False,
        cached_mkt=False,
        fresh_connected=True,
        fresh_mode="PAPER",
    )

    assert plan.api_connected is True
    assert plan.mkt_data_connected is True
    assert plan.connection_status == "API CONNECTED (PAPER)"
    assert plan.market_data_status == "PAPER"


def test_build_readiness_connection_refresh_plan_ignores_failed_probe() -> None:
    plan = build_readiness_connection_refresh_plan(
        cached_api=False,
        cached_mkt=True,
        fresh_connected=False,
        fresh_mode="Tradier API not configured",
    )

    assert plan.api_connected is False
    assert plan.mkt_data_connected is True
    assert plan.connection_status is None
    assert plan.market_data_status is None
