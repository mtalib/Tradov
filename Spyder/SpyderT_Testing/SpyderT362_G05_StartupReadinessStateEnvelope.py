#!/usr/bin/env python3
"""Focused tests for G05 startup-readiness state envelope shaping."""

from __future__ import annotations

import sys
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


def test_collect_startup_readiness_state_uses_envelope_helpers(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    fake_cfg = MagicMock()
    fake_cfg.get.side_effect = lambda key, default=None: {
        "trading.mode": "live",
        "automation.enabled": True,
        "runtime.paper_mode": None,
    }.get(key, default)
    fake_cfg.config_data = {}
    fake_cfg.validate_autonomous_readiness_config.return_value = {
        "warnings": ["warn-a"],
        "errors": ["err-a"],
    }
    base_calls: list[bool] = []
    payload_calls: list[dict[str, object]] = []

    def _base_state() -> dict[str, object]:
        base_calls.append(True)
        return {
            "checked": False,
            "pending": False,
            "mode": "paper",
            "automation_enabled": True,
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
        }

    def _state_plan(**kwargs):
        if kwargs["market_hours_open"] and kwargs["preconnect_idle"]:
            return SimpleNamespace(
                mode="paper",
                automation_enabled=True,
                warnings=(),
                errors=(),
                safe_fallback_applied=False,
                live_blocking=False,
            )
        return SimpleNamespace(
            mode="live",
            automation_enabled=False,
            warnings=("warn-a",),
            errors=("err-a",),
            safe_fallback_applied=False,
            live_blocking=True,
        )

    def _payload(**kwargs) -> dict[str, object]:
        payload_calls.append(dict(kwargs))
        return {
            "checked": True,
            "mode": kwargs["mode"],
            "automation_enabled": kwargs["automation_enabled"],
            "warnings": list(kwargs["warnings"]),
            "errors": list(kwargs["errors"]),
            "safe_fallback_applied": kwargs["safe_fallback_applied"],
            "live_blocking": kwargs["live_blocking"],
        }

    monkeypatch.setitem(
        sys.modules,
        "Spyder.SpyderA_Core.SpyderA03_Configuration",
        SimpleNamespace(get_config_manager=lambda: fake_cfg),
    )
    monkeypatch.setattr(g05, "build_startup_readiness_base_state", _base_state)
    monkeypatch.setattr(g05, "build_startup_readiness_state_plan", _state_plan)
    monkeypatch.setattr(g05, "build_startup_readiness_success_state_payload", _payload)
    monkeypatch.setattr(g05, "_get_eastern_timezone", lambda: timezone.utc)
    monkeypatch.setattr(g05, "is_market_hours", lambda current_et: False)
    monkeypatch.setattr(g05, "_is_preconnect_idle_window", lambda current_et=None: False)

    state = SpyderTradingDashboard._collect_startup_readiness_state(dash)

    assert base_calls == [True]
    assert payload_calls == [
        {
            "mode": "live",
            "automation_enabled": False,
            "warnings": ("warn-a",),
            "errors": ("err-a",),
            "safe_fallback_applied": False,
            "live_blocking": True,
        }
    ]
    assert state == {
        "checked": True,
        "pending": False,
        "mode": "live",
        "automation_enabled": False,
        "warnings": ["warn-a"],
        "errors": ["err-a"],
        "safe_fallback_applied": False,
        "live_blocking": True,
        "source": "A03.ConfigManager",
    }


def test_collect_startup_readiness_state_preserves_exception_source_boundary(monkeypatch) -> None:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    payload_calls: list[dict[str, object]] = []

    monkeypatch.setitem(
        sys.modules,
        "Spyder.SpyderA_Core.SpyderA03_Configuration",
        SimpleNamespace(
            get_config_manager=lambda: (_ for _ in ()).throw(RuntimeError("cfg down"))
        ),
    )
    monkeypatch.setattr(
        g05,
        "build_startup_readiness_base_state",
        lambda: {
            "checked": False,
            "pending": False,
            "mode": "paper",
            "automation_enabled": True,
            "warnings": [],
            "errors": [],
            "safe_fallback_applied": False,
            "live_blocking": False,
        },
    )
    monkeypatch.setattr(
        g05,
        "build_startup_readiness_success_state_payload",
        lambda **kwargs: payload_calls.append(dict(kwargs)) or {},
    )

    state = SpyderTradingDashboard._collect_startup_readiness_state(dash)

    assert payload_calls == []
    assert state == {
        "checked": False,
        "pending": False,
        "mode": "paper",
        "automation_enabled": True,
        "warnings": [],
        "errors": [],
        "safe_fallback_applied": False,
        "live_blocking": False,
        "source": "unavailable: cfg down",
    }
