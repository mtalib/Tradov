#!/usr/bin/env python3
"""Pure planning for dashboard system-log verbosity state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SystemLogVerbosityPlan:
    """Pure plan for applying a system-log verbosity mode."""

    selected_mode: str
    logger_level: int
    normal_button_checked: bool
    debug_button_checked: bool
    announcement_message: str | None


def build_system_log_verbosity_plan(
    *,
    mode: str,
    announce: bool,
    debug_level: int,
    normal_level: int,
) -> SystemLogVerbosityPlan:
    """Normalize the requested verbosity mode into a full application plan."""
    selected_mode = "DEBUG" if str(mode).upper() == "DEBUG" else "NORMAL"
    announcement_message = None
    if announce:
        announcement_message = f"ℹ️ System log mode → {selected_mode}"

    return SystemLogVerbosityPlan(
        selected_mode=selected_mode,
        logger_level=debug_level if selected_mode == "DEBUG" else normal_level,
        normal_button_checked=selected_mode == "NORMAL",
        debug_button_checked=selected_mode == "DEBUG",
        announcement_message=announcement_message,
    )
