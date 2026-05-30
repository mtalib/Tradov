#!/usr/bin/env python3
"""Focused regressions for SKEW dialog close responsiveness."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from Spyder.SpyderG_GUI.SpyderG11_SkewMonitorDialog import SkewDataThread, SkewMonitorDialog


def test_skew_data_thread_stop_interrupts_long_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    thread = SkewDataThread()
    monkeypatch.setattr(thread, "fetch_skew_data", lambda: None)
    thread.update_interval = 5_000
    thread.start()

    deadline = time.monotonic() + 1.0
    while not thread.isRunning() and time.monotonic() < deadline:
        time.sleep(0.01)

    try:
        assert thread.isRunning()

        thread.stop()

        assert thread.wait(500)
    finally:
        if thread.isRunning():
            thread.stop()
            thread.wait(1000)


def test_skew_dialog_close_event_uses_bounded_wait() -> None:
    wait_calls: list[int] = []
    stop_calls: list[str] = []
    accepted: list[bool] = []

    class _ThreadStub:
        def isRunning(self) -> bool:
            return True

        def wait(self, timeout: int) -> bool:
            wait_calls.append(timeout)
            return True

    dialog = SimpleNamespace(
        stop_monitoring=lambda: stop_calls.append("stop"),
        data_thread=_ThreadStub(),
    )
    event = SimpleNamespace(accept=lambda: accepted.append(True))

    SkewMonitorDialog.closeEvent(dialog, event)

    assert stop_calls == ["stop"]
    assert wait_calls == [1000]
    assert accepted == [True]
