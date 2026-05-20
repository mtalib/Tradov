#!/usr/bin/env python3
"""Pure snapshot-probe helpers for the custom metrics orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MetricsSnapshotProbeResult:
    """Captured metrics snapshot plus formatter callable, if hydration is possible."""

    snapshot: dict[str, object] | None
    formatter: Callable[[dict[str, object]], dict[str, object]] | None


def inspect_metrics_orchestrator_snapshot(
    orchestrator: object,
) -> MetricsSnapshotProbeResult:
    """Return the captured snapshot and formatter when S07 can hydrate cached metrics."""
    if orchestrator is None:
        return MetricsSnapshotProbeResult(snapshot=None, formatter=None)

    has_snapshot = getattr(orchestrator, "has_published_metrics_snapshot", None)
    if callable(has_snapshot):
        if not has_snapshot():
            return MetricsSnapshotProbeResult(snapshot=None, formatter=None)
    elif not bool(getattr(orchestrator, "_has_published_metrics", False)):
        return MetricsSnapshotProbeResult(snapshot=None, formatter=None)

    metrics_lock = getattr(orchestrator, "_metrics_lock", None)
    if metrics_lock is None:
        snapshot = dict(getattr(orchestrator, "current_metrics", {}) or {})
    else:
        with metrics_lock:
            snapshot = dict(getattr(orchestrator, "current_metrics", {}) or {})

    formatter = getattr(orchestrator, "_format_metrics", None)
    if not snapshot or not callable(formatter):
        return MetricsSnapshotProbeResult(snapshot=None, formatter=None)

    return MetricsSnapshotProbeResult(snapshot=snapshot, formatter=formatter)
