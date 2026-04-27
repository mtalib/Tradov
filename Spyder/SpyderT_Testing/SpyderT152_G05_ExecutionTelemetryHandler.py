#!/usr/bin/env python3
"""Focused tests for G05 execution telemetry handler wiring."""

from collections import deque
import threading
from unittest.mock import patch

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
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
