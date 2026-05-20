#!/usr/bin/env python3
"""Focused tests for R12 freshness-monitor threshold resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

from types import SimpleNamespace

from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


def test_r12_freshness_thresholds_default_to_spec(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_RTH_THRESHOLD_S", raising=False)
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_OOH_THRESHOLD_S", raising=False)

    supervisor = SessionSupervisor(mode="paper", dry_run=True)

    assert supervisor._resolve_freshness_monitor_thresholds() == (3.0, 30.0)


def test_r12_freshness_threshold_relaxes_for_degraded_quote_fallback(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_RTH_THRESHOLD_S", raising=False)
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_OOH_THRESHOLD_S", raising=False)

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    supervisor.feed = SimpleNamespace(
        status=SimpleNamespace(value="degraded"),
        _quote_poll_interval_s=1.0,
    )

    assert supervisor._resolve_freshness_monitor_thresholds() == (10.0, 30.0)


def test_r12_freshness_threshold_scales_with_slower_degraded_quote_poll(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_RTH_THRESHOLD_S", raising=False)
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_OOH_THRESHOLD_S", raising=False)

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    supervisor.feed = SimpleNamespace(
        status=SimpleNamespace(value="degraded"),
        _quote_poll_interval_s=5.0,
    )

    assert supervisor._resolve_freshness_monitor_thresholds() == (26.0, 30.0)


def test_r12_freshness_threshold_keeps_live_degraded_cadence_threshold(monkeypatch) -> None:
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_RTH_THRESHOLD_S", raising=False)
    monkeypatch.delenv("SPYDER_DATA_FRESHNESS_OOH_THRESHOLD_S", raising=False)

    supervisor = SessionSupervisor(mode="live", dry_run=True)
    supervisor.feed = SimpleNamespace(
        status=SimpleNamespace(value="degraded"),
        _quote_poll_interval_s=1.0,
    )

    assert supervisor._resolve_freshness_monitor_thresholds() == (6.0, 30.0)


def test_r12_freshness_threshold_keeps_larger_explicit_override(monkeypatch) -> None:
    monkeypatch.setenv("SPYDER_DATA_FRESHNESS_RTH_THRESHOLD_S", "8.0")
    monkeypatch.setenv("SPYDER_DATA_FRESHNESS_OOH_THRESHOLD_S", "45.0")

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    supervisor.feed = SimpleNamespace(
        status=SimpleNamespace(value="degraded"),
        _quote_poll_interval_s=1.0,
    )

    assert supervisor._resolve_freshness_monitor_thresholds() == (8.0, 45.0)


def test_r12_freshness_monitor_starts_without_startup_grace(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monitor = MagicMock()
    monitor.start.return_value = True

    def _fake_create_freshness_monitor(**kwargs):
        captured.update(kwargs)
        return monitor

    monkeypatch.setattr(
        "Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor.create_freshness_monitor",
        _fake_create_freshness_monitor,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True)

    assert supervisor._start_freshness_monitor() is True
    assert captured["startup_grace_s"] == 0.0
    monitor.start.assert_called_once_with()


def test_r12_start_freshness_monitor_uses_paper_degraded_floor(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monitor = MagicMock()
    monitor.start.return_value = True

    def _fake_create_freshness_monitor(**kwargs):
        captured.update(kwargs)
        return monitor

    monkeypatch.setattr(
        "Spyder.SpyderE_Risk.SpyderE24_DataFreshnessMonitor.create_freshness_monitor",
        _fake_create_freshness_monitor,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True)
    supervisor.feed = SimpleNamespace(
        status=SimpleNamespace(value="degraded"),
        _quote_poll_interval_s=1.0,
    )

    assert supervisor._start_freshness_monitor() is True
    assert captured["rth_threshold_s"] == 10.0
    assert captured["startup_grace_s"] == 0.0
    monitor.start.assert_called_once_with()
