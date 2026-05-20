#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG62_ReadinessWorkerCleanupHelper.py
Purpose: Pure helper for readiness worker cleanup planning
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadinessWorkerCleanupPlan:
    """Plan describing the non-owning cleanup actions for readiness workers."""

    enable_button: bool
    delete_targets: tuple[Any, ...]


def build_readiness_worker_cleanup_plan(
    *,
    readiness_button: Any | None,
    readiness_worker: Any | None,
    readiness_worker_thread: Any | None,
) -> ReadinessWorkerCleanupPlan:
    """Build the readiness worker cleanup plan without mutating Qt objects."""
    delete_targets = tuple(
        target
        for target in (readiness_worker, readiness_worker_thread)
        if target is not None
    )
    return ReadinessWorkerCleanupPlan(
        enable_button=(readiness_button is not None),
        delete_targets=delete_targets,
    )
