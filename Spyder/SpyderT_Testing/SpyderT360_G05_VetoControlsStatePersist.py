#!/usr/bin/env python3
"""Focused tests for G05 veto controls persistence."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def test_persist_veto_controls_state_uses_helper_plan(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    profile_path = tmp_path / "development.json"
    profile_path.write_text('{"other": 7, "enable_x16_veto": true}\n', encoding="utf-8")
    helper_calls: list[dict[str, object]] = []
    fake_cfg = MagicMock()
    fake_plan = SimpleNamespace(
        payload={
            "enable_x16_veto": False,
            "enable_y03_trade_veto": False,
            "enable_y05_veto_consumption": False,
        },
        serialized_profile_text='{"saved": true}\n',
        env_updates={
            "ENABLE_X16_VETO": "false",
            "ENABLE_Y03_TRADE_VETO": "false",
            "ENABLE_Y05_VETO_CONSUMPTION": "false",
        },
    )

    monkeypatch.setattr(dash, "_resolve_veto_profile_path", lambda: profile_path)
    monkeypatch.setattr(
        g05,
        "build_veto_controls_persist_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or fake_plan,
    )
    monkeypatch.setitem(
        sys.modules,
        "Spyder.SpyderA_Core.SpyderA03_Configuration",
        SimpleNamespace(get_config_manager=lambda: fake_cfg),
    )
    monkeypatch.delenv("ENABLE_X16_VETO", raising=False)
    monkeypatch.delenv("ENABLE_Y03_TRADE_VETO", raising=False)
    monkeypatch.delenv("ENABLE_Y05_VETO_CONSUMPTION", raising=False)

    result = SpyderTradingDashboard._persist_veto_controls_state(dash, False)

    assert result == (True, str(profile_path))
    assert helper_calls == [{"existing_data": {"other": 7, "enable_x16_veto": True}, "enabled": False}]
    assert profile_path.read_text(encoding="utf-8") == '{"saved": true}\n'
    assert os.environ["ENABLE_X16_VETO"] == "false"
    assert os.environ["ENABLE_Y03_TRADE_VETO"] == "false"
    assert os.environ["ENABLE_Y05_VETO_CONSUMPTION"] == "false"
    fake_cfg.update.assert_called_once_with(fake_plan.payload, source="dashboard")


def test_persist_veto_controls_state_preserves_parse_failure_boundary(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    profile_path = tmp_path / "development.json"
    profile_path.write_text("{invalid json\n", encoding="utf-8")
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(dash, "_resolve_veto_profile_path", lambda: profile_path)
    monkeypatch.setattr(
        g05,
        "build_veto_controls_persist_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs)),
    )

    success, detail = SpyderTradingDashboard._persist_veto_controls_state(dash, True)

    assert success is False
    assert helper_calls == []
    assert detail
