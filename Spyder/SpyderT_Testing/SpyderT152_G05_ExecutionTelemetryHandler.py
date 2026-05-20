#!/usr/bin/env python3
"""Focused tests for G05 execution telemetry handler wiring."""

from collections import deque
import threading
from unittest.mock import MagicMock, patch

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _Label:
    """Tiny QLabel stand-in for logic-only tests."""

    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:  # noqa: N802 - Qt-style method name
        self.text = value


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._execution_telemetry_lock = threading.Lock()
    dash._execution_telemetry_events = deque(maxlen=200)
    dash.execution_slippage_bps_value = _Label()
    dash.execution_fill_latency_value = _Label()
    dash.execution_reject_rate_value = _Label()
    dash.execution_partial_fill_value = _Label()
    return dash


def test_g05_handle_trade_event_accepts_event_dataclass_payload() -> None:
    """G05 handler should accept Event payload shape and update panel labels."""
    dash = _build_dashboard_stub()

    telemetry = {
        "feed": "execution",
        "version": "1.0",
        "mode": "paper",
        "session_id": "session-test",
        "published_ts": "2026-04-25T14:30:00",
        "data": {
            "order_id": "ORD-G05-001",
            "slippage_bps": 7.5,
            "fill_latency_ms": 240.0,
            "partial_fill_ratio": 0.5,
            "reject_flag": False,
        },
    }
    event = Event(
        event_type=EventType.TRADE,
        source="unit_test",
        data={"execution_telemetry": telemetry},
    )

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_trade_event(event)

    assert len(dash._execution_telemetry_events) == 1
    assert dash.execution_slippage_bps_value.text == "7.5 bps"
    assert dash.execution_fill_latency_value.text == "240 ms"
    assert dash.execution_reject_rate_value.text == "0.0%"
    assert dash.execution_partial_fill_value.text == "50.0%"


def test_g05_handle_trade_event_uses_helper_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    sample = {
        "published_ts": "2026-04-25T14:30:00",
        "order_id": "ORD-G05-HELPER",
        "slippage_bps": 3.5,
        "fill_latency_ms": 125.0,
        "partial_fill_ratio": 0.25,
        "reject_flag": True,
    }
    update_calls = MagicMock()
    dash._update_execution_health_display = update_calls
    helper_inputs: list[object] = []

    monkeypatch.setattr(
        g05,
        "extract_execution_telemetry_sample",
        lambda event: helper_inputs.append(event) or sample,
    )

    with patch("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot", side_effect=lambda _ms, cb: cb()):
        dash._handle_trade_event({"raw": "event"})

    assert helper_inputs == [{"raw": "event"}]
    assert list(dash._execution_telemetry_events) == [sample]
    update_calls.assert_called_once_with()


def test_g05_update_execution_health_display_uses_presenter_output(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash._execution_telemetry_events.extend(
        [{"slippage_bps": 1.0, "fill_latency_ms": 2.0, "partial_fill_ratio": 0.1, "reject_flag": False}]
    )

    class _Presentation:
        slippage_bps_text = "slippage"
        fill_latency_text = "latency"
        reject_rate_text = "reject-rate"
        partial_fill_text = "partial-fill"

    monkeypatch.setattr(g05, "build_execution_health_presentation", lambda samples: _Presentation())

    dash._update_execution_health_display()

    assert dash.execution_slippage_bps_value.text == "slippage"
    assert dash.execution_fill_latency_value.text == "latency"
    assert dash.execution_reject_rate_value.text == "reject-rate"
    assert dash.execution_partial_fill_value.text == "partial-fill"
