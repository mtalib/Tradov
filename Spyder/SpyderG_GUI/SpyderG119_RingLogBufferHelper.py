#!/usr/bin/env python3
"""Pure ring-log buffering and refresh planning for the dashboard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RingLogAppendPlan:
    """Pure append/truncate result for a ring log buffer."""

    next_buffer: list[str]


@dataclass(frozen=True)
class LogWidgetRefreshPlan:
    """Pure routing plan for a buffered log widget refresh."""

    action: str
    target: str | None = None
    set_system_pending: bool = False
    set_automation_pending: bool = False


def build_ring_log_append_plan(
    *,
    buffer: list[str],
    message: str,
    max_buffer: int,
    timestamp_text: str,
) -> RingLogAppendPlan:
    """Return the next ring-buffer contents after appending one message."""
    next_buffer = list(buffer)
    next_buffer.append(f"[{timestamp_text}] {message}")
    if len(next_buffer) > max_buffer:
        next_buffer = next_buffer[-max_buffer:]
    return RingLogAppendPlan(next_buffer=next_buffer)


def build_log_widget_refresh_plan(
    *,
    has_widget: bool,
    is_system_widget: bool,
    is_automation_widget: bool,
    system_pending: bool,
    automation_pending: bool,
) -> LogWidgetRefreshPlan:
    """Choose how a buffered log refresh should be applied."""
    if not has_widget:
        return LogWidgetRefreshPlan(action="skip")

    if is_system_widget:
        if system_pending:
            return LogWidgetRefreshPlan(action="skip")
        return LogWidgetRefreshPlan(
            action="schedule",
            target="system",
            set_system_pending=True,
        )

    if is_automation_widget:
        if automation_pending:
            return LogWidgetRefreshPlan(action="skip")
        return LogWidgetRefreshPlan(
            action="schedule",
            target="automation",
            set_automation_pending=True,
        )

    return LogWidgetRefreshPlan(action="flush", target="other")
