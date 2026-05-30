#!/usr/bin/env python3
"""Regression tests for S07 startup behavior."""

import threading

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from Spyder.SpyderS_Signals import SpyderS07_CustomMetricsOrchestrator as s07


def test_s07_constructor_defers_calculator_initialization(monkeypatch):
    called = False

    def _unexpected_init(self):
        nonlocal called
        called = True
        raise AssertionError("_init_calculators should not run inside __init__")

    monkeypatch.setattr(s07.CustomMetricsOrchestrator, "_init_calculators", _unexpected_init)

    orchestrator = s07.CustomMetricsOrchestrator(config={"auto_start": False})

    assert called is False
    assert orchestrator._calculators_initialized is False
    assert orchestrator.dix_calculator is None
    orchestrator.update_timer.stop()


def test_s07_calculator_initialization_is_idempotent(monkeypatch):
    calls = 0

    def _fake_init(self):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(s07.CustomMetricsOrchestrator, "_init_calculators", _fake_init)

    orchestrator = s07.CustomMetricsOrchestrator(config={"auto_start": False})
    orchestrator._ensure_calculators_initialized()
    orchestrator._ensure_calculators_initialized()

    assert calls == 1
    assert orchestrator._calculators_initialized is True
    orchestrator.update_timer.stop()


def test_s07_adjust_frequency_queues_timer_change_from_worker_thread():
    QApplication.instance() or QApplication([])

    orchestrator = s07.CustomMetricsOrchestrator(config={"auto_start": False})

    try:
        assert orchestrator.update_timer.interval() == s07.UPDATE_INTERVAL * 1000

        worker = threading.Thread(
            target=orchestrator._analyze_and_adjust_frequency,
            args=({"SWAN": 1.0},),
            daemon=True,
        )
        worker.start()
        worker.join()

        loop = QEventLoop()
        QTimer.singleShot(0, loop.quit)
        loop.exec()

        assert orchestrator.current_update_interval == s07.SLOW_UPDATE
        assert orchestrator.update_timer.interval() == s07.SLOW_UPDATE * 1000
    finally:
        orchestrator.update_timer.stop()
