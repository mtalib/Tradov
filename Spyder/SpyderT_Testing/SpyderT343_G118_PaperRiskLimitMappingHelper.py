#!/usr/bin/env python3
"""Focused tests for G118 paper risk-limit mapping helper."""

from Spyder.SpyderG_GUI.SpyderG118_PaperRiskLimitMappingHelper import (
    build_paper_risk_limit_mapping_plan,
)


def test_build_paper_risk_limit_mapping_plan_maps_percentages_and_contracts() -> None:
    plan = build_paper_risk_limit_mapping_plan(
        default_risk_limits={"baseline": 1},
        current_risk_params={
            "global": {
                "max_buying_power": 50,
                "max_daily_loss": 5,
                "max_contracts": 12,
            }
        },
        initial_capital=100_000.0,
    )

    assert plan.warning_message is None
    assert plan.risk_limits == {
        "baseline": 1,
        "max_total_exposure": 50_000.0,
        "max_daily_loss": 5_000.0,
        "max_position_size": 12,
        "max_single_order_size": 12,
    }


def test_build_paper_risk_limit_mapping_plan_preserves_defaults_on_bad_value() -> None:
    plan = build_paper_risk_limit_mapping_plan(
        default_risk_limits={"baseline": 1, "max_daily_loss": 100.0},
        current_risk_params={"global": {"max_daily_loss": "oops"}},
        initial_capital=100_000.0,
    )

    assert plan.risk_limits == {"baseline": 1, "max_daily_loss": 100.0}
    assert plan.warning_message is not None
    assert "Could not map G09 params to E01 limits:" in plan.warning_message
