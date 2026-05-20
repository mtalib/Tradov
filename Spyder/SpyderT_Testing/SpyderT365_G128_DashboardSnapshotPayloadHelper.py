#!/usr/bin/env python3
"""Focused tests for G128 dashboard snapshot payload helper."""

from Spyder.SpyderG_GUI.SpyderG128_DashboardSnapshotPayloadHelper import (
    build_dashboard_snapshot_payload,
)


class _Mode:
    def __init__(self, value: str) -> None:
        self.value = value


def test_build_dashboard_snapshot_payload_clears_paper_state_and_filters_data() -> None:
    live = _Mode("LIVE")
    paper = _Mode("PAPER")

    payload = build_dashboard_snapshot_payload(
        saved_at=123.4,
        trading_mode="LIVE",
        mode_keys=(live, paper),
        account_snapshot_by_mode={live: {"settled": 1000.0}, paper: {"settled": 999.0}},
        pnl_stats_by_mode={live: {"today_pnl": "$+5.00"}, paper: {"today_pnl": "$+7.00"}},
        market_data={
            "SPY": {"last": 530.5, "change": 1.2, "change_pct": 0.23},
            "QQQ": {"last": None, "change": 0.0, "change_pct": 0.0},
            "IWM": "invalid",
        },
    )

    assert payload == {
        "_saved_at": 123.4,
        "trading_mode": "LIVE",
        "account_by_mode": {"LIVE": {"settled": 1000.0}, "PAPER": {}},
        "pnl_stats_by_mode": {"LIVE": {"today_pnl": "$+5.00"}, "PAPER": {}},
        "data": {"SPY": {"last": 530.5, "change": 1.2, "change_pct": 0.23}},
    }


def test_build_dashboard_snapshot_payload_coerces_non_mapping_mode_values_to_empty_dicts() -> None:
    payload = build_dashboard_snapshot_payload(
        saved_at=1.0,
        trading_mode="PAPER",
        mode_keys=("LIVE", "PAPER"),
        account_snapshot_by_mode={"LIVE": [1, 2, 3]},
        pnl_stats_by_mode={"LIVE": None},
        market_data={"SPY": {"last": 530.5}},
    )

    assert payload["account_by_mode"] == {"LIVE": {}, "PAPER": {}}
    assert payload["pnl_stats_by_mode"] == {"LIVE": {}, "PAPER": {}}
    assert payload["data"] == {"SPY": {"last": 530.5, "change": 0.0, "change_pct": 0.0}}
