#!/usr/bin/env python3
"""Focused regression coverage for desktop-launcher paper autostart defaults."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPO_ROOT / "Spyder" / "SpyderQ_Scripts" / "launch_spyder_desktop.sh"


def test_desktop_launcher_defaults_enable_paper_session_supervisor_autostart() -> None:
    launcher = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert (
        'export SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR="${SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR:-1}"'
        in launcher
    )
    assert (
        'export SPYDER_A01_ALLOW_GUI_AUTOSTART="${SPYDER_A01_ALLOW_GUI_AUTOSTART:-1}"'
        in launcher
    )
    assert (
        'export SPYDER_A01_AUTOSTART_MODE="${SPYDER_A01_AUTOSTART_MODE:-paper}"'
        in launcher
    )