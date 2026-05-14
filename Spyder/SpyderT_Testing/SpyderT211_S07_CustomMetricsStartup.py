#!/usr/bin/env python3
"""Regression tests for S07 startup behavior."""

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
