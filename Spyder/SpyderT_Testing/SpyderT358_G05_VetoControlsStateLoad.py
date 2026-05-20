#!/usr/bin/env python3
"""Focused tests for G05 veto controls state loading."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def test_load_veto_controls_state_uses_helper_with_profile_data(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    profile_path = tmp_path / "development.json"
    profile_path.write_text(
        json.dumps(
            {
                "enable_x16_veto": True,
                "enable_y03_trade_veto": False,
                "enable_y05_veto_consumption": True,
            }
        ),
        encoding="utf-8",
    )
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(dash, "_resolve_veto_profile_path", lambda: profile_path)
    monkeypatch.setenv("ENABLE_X16_VETO", "true")
    monkeypatch.setenv("ENABLE_Y03_TRADE_VETO", "true")
    monkeypatch.setenv("ENABLE_Y05_VETO_CONSUMPTION", "true")
    monkeypatch.setattr(
        g05,
        "resolve_veto_controls_enabled_state",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or False,
    )

    result = SpyderTradingDashboard._load_veto_controls_state(dash)

    assert result is False
    assert helper_calls == [
        {
            "profile_data": {
                "enable_x16_veto": True,
                "enable_y03_trade_veto": False,
                "enable_y05_veto_consumption": True,
            },
            "default_enabled": True,
            "env_values": {
                "ENABLE_X16_VETO": "true",
                "ENABLE_Y03_TRADE_VETO": "true",
                "ENABLE_Y05_VETO_CONSUMPTION": "true",
            },
        }
    ]


def test_load_veto_controls_state_uses_helper_with_env_fallback(monkeypatch, tmp_path: Path) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    profile_path = tmp_path / "missing.json"
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(dash, "_resolve_veto_profile_path", lambda: profile_path)
    monkeypatch.setenv("ENABLE_X16_VETO", "false")
    monkeypatch.setenv("ENABLE_Y03_TRADE_VETO", "yes")
    monkeypatch.delenv("ENABLE_Y05_VETO_CONSUMPTION", raising=False)
    monkeypatch.setattr(
        g05,
        "resolve_veto_controls_enabled_state",
        lambda **kwargs: helper_calls.append(dict(kwargs)) or True,
    )

    result = SpyderTradingDashboard._load_veto_controls_state(dash)

    assert result is True
    assert helper_calls == [
        {
            "profile_data": None,
            "default_enabled": True,
            "env_values": {
                "ENABLE_X16_VETO": "false",
                "ENABLE_Y03_TRADE_VETO": "yes",
                "ENABLE_Y05_VETO_CONSUMPTION": None,
            },
        }
    ]
