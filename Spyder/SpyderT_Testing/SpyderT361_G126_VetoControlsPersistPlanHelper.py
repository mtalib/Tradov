#!/usr/bin/env python3
"""Focused tests for G126 veto controls persistence planning."""

import json

from Spyder.SpyderG_GUI.SpyderG126_VetoControlsPersistPlanHelper import (
    build_veto_controls_persist_plan,
)


def test_build_veto_controls_persist_plan_merges_existing_data() -> None:
    plan = build_veto_controls_persist_plan(
        existing_data={"other": 7, "enable_x16_veto": True},
        enabled=False,
    )

    assert plan.payload == {
        "enable_x16_veto": False,
        "enable_y03_trade_veto": False,
        "enable_y05_veto_consumption": False,
    }
    assert json.loads(plan.serialized_profile_text) == {
        "other": 7,
        "enable_x16_veto": False,
        "enable_y03_trade_veto": False,
        "enable_y05_veto_consumption": False,
    }
    assert plan.serialized_profile_text.endswith("\n")


def test_build_veto_controls_persist_plan_sets_all_env_updates() -> None:
    plan = build_veto_controls_persist_plan(
        existing_data=None,
        enabled=True,
    )

    assert plan.env_updates == {
        "ENABLE_X16_VETO": "true",
        "ENABLE_Y03_TRADE_VETO": "true",
        "ENABLE_Y05_VETO_CONSUMPTION": "true",
    }


def test_build_veto_controls_persist_plan_handles_missing_existing_data() -> None:
    plan = build_veto_controls_persist_plan(
        existing_data=None,
        enabled=False,
    )

    assert json.loads(plan.serialized_profile_text) == {
        "enable_x16_veto": False,
        "enable_y03_trade_veto": False,
        "enable_y05_veto_consumption": False,
    }