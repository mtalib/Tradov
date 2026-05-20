#!/usr/bin/env python3
"""Focused tests for G05 readiness report and audit export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub(tmp_path: Path) -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._readiness_reports_dir = tmp_path / "readiness-reports"
    dash._last_readiness_result = None
    dash.logged_messages: list[str] = []
    dash.add_system_log = lambda message: dash.logged_messages.append(str(message))
    return dash


def test_g05_export_readiness_report_uses_presenter_filename(monkeypatch, tmp_path: Path) -> None:
    dash = _build_dashboard_stub(tmp_path)

    monkeypatch.setattr(
        g05,
        "build_readiness_report_filename",
        lambda result, *, stamp: "custom_readiness_report.json",
    )

    result = {"decision": "OK", "checked_at_et": "2026-05-15T09:45:00-04:00"}
    out_path = Path(dash._export_readiness_report(result))

    assert out_path.name == "custom_readiness_report.json"
    assert json.loads(out_path.read_text(encoding="utf-8")) == result


def test_g05_append_readiness_bypass_audit_writes_standalone_file_with_presenter_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)

    monkeypatch.setattr(
        g05,
        "build_readiness_bypass_audit_entry",
        lambda *, action, decision, reason, stamp: {
            "audit_type": "session_start_gate",
            "action": "override",
            "decision": "OK - CONDITIONAL",
            "bypass_reason": "operator confirmed",
            "operator_ts_et": "fixed-stamp",
        },
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_bypass_audit_filename",
        lambda *, action, stamp: "custom_audit.json",
    )

    dash._append_readiness_bypass_audit("override", "OK - CONDITIONAL", "operator confirmed")

    out_path = dash._readiness_reports_dir / "custom_audit.json"
    assert json.loads(out_path.read_text(encoding="utf-8")) == {
        "audit_type": "session_start_gate",
        "action": "override",
        "decision": "OK - CONDITIONAL",
        "bypass_reason": "operator confirmed",
        "operator_ts_et": "fixed-stamp",
    }


def test_g05_append_readiness_bypass_audit_uses_helper_to_export_cached_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dash = _build_dashboard_stub(tmp_path)
    dash._last_readiness_result = {"decision": "OK"}
    dash._export_readiness_report = MagicMock()

    helper_calls: list[dict[str, object]] = []
    expected_export = {
        "decision": "OK",
        "bypass_audit": [
            {
                "audit_type": "session_start_gate",
                "action": "override",
                "decision": "OK - CONDITIONAL",
                "bypass_reason": "operator confirmed",
                "operator_ts_et": "fixed-stamp",
            }
        ],
    }

    monkeypatch.setattr(
        g05,
        "build_readiness_bypass_audit_entry",
        lambda *, action, decision, reason, stamp: {
            "audit_type": "session_start_gate",
            "action": action,
            "decision": decision,
            "bypass_reason": reason,
            "operator_ts_et": "fixed-stamp",
        },
    )
    monkeypatch.setattr(
        g05,
        "build_readiness_bypass_audit_plan",
        lambda last_result, audit_entry: helper_calls.append(
            {
                "last_result": last_result,
                "audit_entry": audit_entry,
            }
        )
        or SimpleNamespace(
            export_result=expected_export,
            standalone_payload=None,
        ),
    )

    dash._append_readiness_bypass_audit("override", "OK - CONDITIONAL", "operator confirmed")

    assert helper_calls == [
        {
            "last_result": {"decision": "OK"},
            "audit_entry": {
                "audit_type": "session_start_gate",
                "action": "override",
                "decision": "OK - CONDITIONAL",
                "bypass_reason": "operator confirmed",
                "operator_ts_et": "fixed-stamp",
            },
        }
    ]
    assert dash._last_readiness_result == expected_export
    dash._export_readiness_report.assert_called_once_with(expected_export)