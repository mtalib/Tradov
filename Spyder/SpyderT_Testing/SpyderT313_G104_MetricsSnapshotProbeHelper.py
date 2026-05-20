#!/usr/bin/env python3
"""Focused tests for G104 metrics snapshot probe helper."""

from __future__ import annotations

from types import SimpleNamespace

from Spyder.SpyderG_GUI.SpyderG104_MetricsSnapshotProbeHelper import (
    inspect_metrics_orchestrator_snapshot,
)


class _Lock:
    def __init__(self) -> None:
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_inspect_metrics_orchestrator_snapshot_reads_locked_snapshot() -> None:
    metrics_lock = _Lock()
    formatter = lambda payload: payload  # noqa: E731
    orchestrator = SimpleNamespace(
        has_published_metrics_snapshot=lambda: True,
        _metrics_lock=metrics_lock,
        current_metrics={"PCA-PROXY": 0.84},
        _format_metrics=formatter,
    )

    probe = inspect_metrics_orchestrator_snapshot(orchestrator)

    assert metrics_lock.entered == 1
    assert probe.snapshot == {"PCA-PROXY": 0.84}
    assert probe.formatter is formatter


def test_inspect_metrics_orchestrator_snapshot_rejects_unpublished_or_empty_state() -> None:
    unpublished = SimpleNamespace(
        has_published_metrics_snapshot=lambda: False,
        current_metrics={"PCA-PROXY": 0.84},
        _format_metrics=lambda payload: payload,
    )
    empty_snapshot = SimpleNamespace(
        _has_published_metrics=True,
        current_metrics={},
        _format_metrics=lambda payload: payload,
    )

    unpublished_probe = inspect_metrics_orchestrator_snapshot(unpublished)
    empty_probe = inspect_metrics_orchestrator_snapshot(empty_snapshot)

    assert unpublished_probe.snapshot is None
    assert unpublished_probe.formatter is None
    assert empty_probe.snapshot is None
    assert empty_probe.formatter is None