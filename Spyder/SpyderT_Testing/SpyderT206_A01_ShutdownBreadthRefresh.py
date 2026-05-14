#!/usr/bin/env python3
"""Launcher-backed regression for shutdown during a live breadth refresh."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest


@pytest.mark.timeout(90)
def test_a01_launcher_shutdown_during_breadth_refresh_exits_cleanly(tmp_path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    log_path = tmp_path / "a01_shutdown_breadth_refresh.log"

    child_script = textwrap.dedent(
        """
        import importlib
        import signal
        import sys
        import time

        a01_main = importlib.import_module("Spyder.SpyderA_Core.SpyderA01_Main")
        g05_mod = importlib.import_module("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard")
        a01_main._HAS_COORDINATOR = False
        g05_mod.is_market_hours = lambda *_args, **_kwargs: True

        def _mark_market_worker_started(self, quiet_startup=False, announce=True):
            self._market_worker_started = True

        g05_mod.SpyderTradingDashboard.start_market_worker = _mark_market_worker_started
        g05_mod.SpyderTradingDashboard._init_h07_performance_analytics = lambda self: None
        g05_mod.SpyderTradingDashboard._start_decision_flow_timer = lambda self: None
        g05_mod.SpyderTradingDashboard._start_optional_signal_refresh_timer = lambda self: None
        g05_mod.SpyderTradingDashboard._restore_snapshot = lambda self: None
        g05_mod.SpyderTradingDashboard._init_account_display = lambda self: None
        g05_mod.SpyderTradingDashboard._refresh_startup_readiness_state = lambda self: None

        def patched_schedule_runtime_followups(self):
            if getattr(self, "_startup_runtime_followups_scheduled", False):
                return
            self._startup_runtime_followups_scheduled = True
            g05_mod.QTimer.singleShot(0, self._start_metrics_orchestrator)

        g05_mod.SpyderTradingDashboard._schedule_runtime_followup_startup_tasks = patched_schedule_runtime_followups

        class _FakeMetricsOrchestrator:
            def __init__(self):
                self._closed = False

            def stop(self):
                self._closed = True

        def patched_start_metrics(self, *args, **kwargs):
            if getattr(self, "_metrics_orchestrator", None) is not None:
                return None

            orchestrator = _FakeMetricsOrchestrator()
            self._metrics_orchestrator = orchestrator

            def _dispatch_breadth_refresh():
                print("TEST: breadth refresh dispatched", flush=True)
                print("TEST: breadth snapshot entered", flush=True)
                while not orchestrator._closed:
                    time.sleep(0.05)

            g05_mod.QTimer.singleShot(0, _dispatch_breadth_refresh)
            return None

        g05_mod.SpyderTradingDashboard._start_metrics_orchestrator = patched_start_metrics

        app = a01_main.SpyderApplication()

        def _signal_handler(signum, frame):
            app.shutdown()

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        if not app.initialize_core_systems():
            raise SystemExit(1)
        if not app.start_gui():
            raise SystemExit(1)

        orchestrator = _FakeMetricsOrchestrator()
        app.main_window._metrics_orchestrator = orchestrator

        def _dispatch_breadth_refresh():
            print("TEST: breadth refresh dispatched", flush=True)
            print("TEST: breadth snapshot entered", flush=True)
            while not orchestrator._closed:
                time.sleep(0.05)

        g05_mod.QTimer.singleShot(0, _dispatch_breadth_refresh)
        exit_code = app.gui_app.exec()
        if exit_code == 0:
            print("SPYDER exited with code: 0 (success)", flush=True)
        else:
            print(f"SPYDER exited with code: {exit_code} (failure)", flush=True)
        raise SystemExit(exit_code)
        """
    )

    env = os.environ.copy()
    env.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "MPLBACKEND": "Agg",
            "SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR": "1",
            "SPYDER_A01_ALLOW_GUI_AUTOSTART": "1",
            "SPYDER_A01_AUTOSTART_MODE": "paper",
            "SPYDER_ENABLE_PIVOT_MEAN_REVERSION": "true",
            "SPYDER_PIVOT_MR_ENABLED": "1",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
            "TELEGRAM_ALLOWED_USER_IDS": "",
            "TELEGRAM_PL_REPORTING_ENABLED": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(repo_root), env.get("PYTHONPATH", "")) if part
    )

    with log_path.open("w", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            [sys.executable, "-c", child_script],
            cwd=repo_root,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            marker = "TEST: breadth snapshot entered"
            deadline = time.monotonic() + 45.0

            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    break
                output = log_path.read_text(encoding="utf-8", errors="replace")
                if marker in output:
                    break
                time.sleep(0.2)

            output = log_path.read_text(encoding="utf-8", errors="replace")
            assert proc.poll() is None, output
            assert marker in output, output

            shutdown_started = time.monotonic()
            proc.send_signal(signal.SIGTERM)
            exit_code = proc.wait(timeout=30.0)
            shutdown_elapsed = time.monotonic() - shutdown_started
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10.0)

    output = log_path.read_text(encoding="utf-8", errors="replace")
    assert exit_code == 0, output
    assert shutdown_elapsed < 10.0, output
    assert "Shutdown complete" in output, output
    assert "SPYDER exited with code: 0 (success)" in output, output
    assert "Live non-main threads remain after shutdown" not in output, output
