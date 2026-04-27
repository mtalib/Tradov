#!/usr/bin/env python3
"""Backward-compatible launcher shim.

Keeps old desktop/icon Exec targets working after Q-series renames.
"""

import sys

from Spyder.SpyderQ_Scripts.SpyderQ14_MainLauncher import main as main_launcher
from Spyder.SpyderQ_Scripts.SpyderQ05_LaunchDashboardProactive import main as proactive_launcher


def _qt_app_exists() -> bool:
    """Return True if a Qt application instance is already alive."""
    try:
        from PySide6.QtWidgets import QApplication

        return QApplication.instance() is not None
    except Exception:
        try:
            from PyQt5.QtWidgets import QApplication

            return QApplication.instance() is not None
        except Exception:
            return False


if __name__ == "__main__":
    # Prefer the main unified dashboard; keep proactive fallback.
    if len(sys.argv) == 1:
        sys.argv = [sys.argv[0], "--mode", "paper", "--gui"]
    exit_code = main_launcher()
    if exit_code != 0 and not _qt_app_exists():
        raise SystemExit(proactive_launcher())
    raise SystemExit(exit_code)
