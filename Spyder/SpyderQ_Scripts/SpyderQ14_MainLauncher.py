#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ14_MainLauncher.py
Purpose: Fixed main system launcher that works with available modules
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-23 Time: 13:00:00

Module Description:
    Fixed version of the main system launcher that doesn't depend on the
    non-existent SpyderI05_SystemOrchestrator. This launcher uses available
    modules like SpyderA06_MasterController for system orchestration and
    provides graceful fallbacks when modules are not available.

Usage:
    python SpyderQ14_MainLauncher.py [options]

Options:
    --mode          : Trading mode (live/paper) [default: paper]
    --config        : Path to configuration file
    --gui           : Launch with GUI [default: True]
    --headless      : Run in headless mode (no GUI)
    --debug         : Enable debug logging
    --safe-mode     : Start with minimal modules (critical only)
    --module        : Start specific module only
    --status        : Check system status and exit
    --shutdown      : Shutdown running system

Examples:
    python SpyderQ14_MainLauncher.py --mode paper --gui
    python SpyderQ14_MainLauncher.py --mode live --headless
    python SpyderQ14_MainLauncher.py --status
    python SpyderQ14_MainLauncher.py --module SpyderG05_TradingDashboard
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ==============================================================================
# SYSTEM PATH SETUP
# ==============================================================================
# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# ==============================================================================
# LOCAL IMPORTS WITH FALLBACKS
# ==============================================================================
logger = None
error_handler = None
master_controller = None
CORE_AVAILABLE = False
GUI_AVAILABLE = False

# Try to import core utilities first
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger(__name__)
    print("✅ Logger available")
except ImportError as e:
    print(f"⚠️ Logger not available: {e}")

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    error_handler = SpyderErrorHandler()
    print("✅ Error handler available")
except ImportError as e:
    print(f"⚠️ Error handler not available: {e}")

# Try to import system controller (use MasterController instead of missing SystemOrchestrator)
try:
    from SpyderA_Core.SpyderA06_MasterController import MasterController, SystemStatus  # noqa: F401
    master_controller = MasterController
    CORE_AVAILABLE = True
    print("✅ MasterController available")
except ImportError as e:
    print(f"⚠️ MasterController not available: {e}")

    # Try alternative controllers
    try:
        from SpyderI_Integration.SpyderI01_IntegrationHub import IntegrationHub
        master_controller = IntegrationHub
        CORE_AVAILABLE = True
        print("✅ IntegrationHub available as fallback")
    except ImportError as e2:
        print(f"⚠️ IntegrationHub also not available: {e2}")

# Try to import GUI modules
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard  # noqa: F401
    GUI_AVAILABLE = True
    print("✅ Trading Dashboard available")
except ImportError:
    try:
        from SpyderG_GUI.SpyderG01_MainWindow import MainWindow  # noqa: F401
        GUI_AVAILABLE = True
        print("✅ Main Window available")
    except ImportError:
        try:
            from SpyderG_GUI.SpyderG02_GUIEntry import run_gui  # noqa: F401
            GUI_AVAILABLE = True
            print("✅ GUI Entry available")
        except ImportError as e:
            print(f"⚠️ GUI modules not available: {e}")

print(f"Core Available: {CORE_AVAILABLE}, GUI Available: {GUI_AVAILABLE}")

# ==============================================================================
# SYSTEM STATE ENUMS (fallback definitions)
# ==============================================================================
class SystemState:
    """Simple system state class as fallback"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"

# ==============================================================================
# SPYDER LAUNCHER CLASS
# ==============================================================================
class SpyderLauncher:
    """
    Fixed Spyder system launcher that works with available modules.
    """

    def __init__(self, args):
        self.args = args
        self.project_root = project_root
        self.state = SystemState.STARTING
        self.running = False

        # Propagate --mode to TRADING_MODE so all config-based mode switches
        # (TradierClient URL, risk limits) pick up the correct environment.
        os.environ["TRADING_MODE"] = args.mode

        # Set TRADIER_ENVIRONMENT default only if not already explicitly
        # overridden by the user in the process environment.  This allows:
        #   --mode paper                       → sandbox.tradier.com (default)
        #   --mode paper TRADIER_ENVIRONMENT=live → api.tradier.com + paper fills
        #   --mode live                        → api.tradier.com + live fills
        if "TRADIER_ENVIRONMENT" not in os.environ:
            os.environ["TRADIER_ENVIRONMENT"] = "live" if args.mode == "live" else "sandbox"

        # Setup logging
        self.log_info = logger.info if logger else print
        self.log_error = logger.error if logger else print
        self.log_warning = logger.warning if logger else print

    def _log_startup_info(self):
        """Log startup information"""
        self.log_info("🚀 SPYDER SYSTEM LAUNCHER STARTING")
        self.log_info("=" * 50)
        self.log_info(f"Project Root: {self.project_root}")
        self.log_info(f"Trading Mode: {self.args.mode}")
        self.log_info(f"GUI Enabled: {self.args.gui and not self.args.headless}")
        self.log_info(f"Debug Mode: {self.args.debug}")
        self.log_info(f"Safe Mode: {self.args.safe_mode}")
        self.log_info("")

        # Show module availability
        self.log_info("📦 MODULE AVAILABILITY:")
        self.log_info(f"  Core System: {'✅ Available' if CORE_AVAILABLE else '❌ Limited'}")
        self.log_info(f"  GUI System: {'✅ Available' if GUI_AVAILABLE else '❌ Not Available'}")
        self.log_info(f"  Logger: {'✅ Available' if logger else '❌ Using Print'}")
        self.log_info("")

    def show_status(self):
        """Show system status"""
        self.log_info("📊 SPYDER SYSTEM STATUS")
        self.log_info("=" * 50)

        # Basic system info
        self.log_info(f"System State: {self.state}")
        self.log_info(f"Project Root: {self.project_root}")
        self.log_info(f"Python Version: {sys.version}")
        self.log_info("")

        # Module availability
        self.log_info("📦 MODULE STATUS:")
        modules_to_check = [
            ("SpyderA_Core", "Core functionality"),
            ("SpyderB_Broker", "Broker integration"),
            ("SpyderC_MarketData", "Market data"),
            ("SpyderD_Strategies", "Trading strategies"),
            ("SpyderE_Risk", "Risk management"),
            ("SpyderG_GUI", "User interface"),
            ("SpyderU_Utilities", "Utilities"),
            ("SpyderI_Integration", "System integration")
        ]

        for module_dir, description in modules_to_check:
            module_path = self.project_root / module_dir
            if module_path.exists():
                py_files = list(module_path.glob("*.py"))
                self.log_info(f"  ✅ {module_dir}: {len(py_files)} modules - {description}")
            else:
                self.log_info(f"  ❌ {module_dir}: Not found - {description}")

        return True

    def launch_gui(self):
        """Launch GUI if available"""
        if not GUI_AVAILABLE:
            self.log_error("❌ GUI modules not available")
            return False

        self.log_info("🖥️ Launching GUI...")

        try:
            # Try different GUI entry points
            gui_modules = [
                ("SpyderG_GUI.SpyderG05_TradingDashboard", "TradingDashboard"),
                ("SpyderG_GUI.SpyderG01_MainWindow", "MainWindow"),
                ("SpyderG_GUI.SpyderG02_GUIEntry", "run_gui")
            ]

            for module_name, class_or_func in gui_modules:
                try:
                    self.log_info(f"Trying to launch {module_name}...")

                    # Import the module
                    module = __import__(module_name, fromlist=[''])

                    # Try to get the class or function
                    if hasattr(module, class_or_func):
                        gui_obj = getattr(module, class_or_func)

                        if callable(gui_obj):
                            if class_or_func == "run_gui":
                                # It's a function
                                gui_obj()
                            else:
                                # It's probably a class
                                app = self._create_qt_app()
                                if app:
                                    window = gui_obj()
                                    if hasattr(window, 'showMaximized'):
                                        window.showMaximized()
                                    elif hasattr(window, 'show'):
                                        window.show()
                                    app.exec()

                        self.log_info(f"✅ Successfully launched {class_or_func}")
                        return True

                except ImportError as e:
                    self.log_warning(f"Cannot import {module_name}: {e}")
                    continue
                except Exception as e:
                    self.log_error(f"Error launching {module_name}: {e}")
                    continue

            self.log_error("❌ Could not launch any GUI module")
            return False

        except Exception as e:
            self.log_error(f"❌ GUI launch failed: {e}")
            return False

    def _create_qt_app(self):
        """Create Qt application if possible with dock icon fix"""
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QCoreApplication

            # DOCK ICON FIX: Set properties BEFORE creating QApplication
            QCoreApplication.setApplicationName("spyder-trading-system")
            QCoreApplication.setOrganizationName("SpyderTrading")
            QCoreApplication.setApplicationVersion("1.0.0")

            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)

            # Set additional properties for dock icon matching
            app.setApplicationName("spyder-trading-system")
            app.setApplicationDisplayName("Spyder Options Trading System")
            app.setDesktopFileName("spyder-trading-system")

            print("✅ Qt application created with dock icon fix")
            return app

        except ImportError:
            try:
                from PyQt5.QtWidgets import QApplication
                from PyQt5.QtCore import QCoreApplication

                QCoreApplication.setApplicationName("spyder-trading-system")

                app = QApplication.instance()
                if app is None:
                    app = QApplication(sys.argv)

                app.setApplicationName("spyder-trading-system")
                print("✅ Qt5 application created with dock icon fix")
                return app

            except ImportError:
                self.log_error("❌ No Qt libraries available")
                return None

    def run_specific_module(self, module_name: str):
        """Run a specific module"""
        self.log_info(f"🚀 Running specific module: {module_name}")

        # Handle special cases
        if module_name == "SpyderG05_TradingDashboard":
            return self.launch_gui()

        # Try to run the module as a script
        module_paths = [
            self.project_root / f"{module_name}.py",
            self.project_root / "SpyderG_GUI" / f"{module_name}.py",
            self.project_root / "SpyderA_Core" / f"{module_name}.py",
        ]

        for module_path in module_paths:
            if module_path.exists():
                self.log_info(f"Found module at: {module_path}")
                try:
                    subprocess.run([sys.executable, str(module_path)], check=True)
                    return True
                except subprocess.CalledProcessError as e:
                    self.log_error(f"Module execution failed: {e}")
                    return False

        self.log_error(f"Module not found: {module_name}")
        return False

    def _live_preflight_checks(self) -> bool:
        """P0-7: Gate that must pass before any live-mode session starts.

        Checks (in order):
        1. ``LIVE_TRADING_CONFIRMED=true`` env guard — requires explicit opt-in.
        2. Required credentials present (``TRADIER_API_KEY``, ``TRADIER_ACCOUNT_ID``).
        3. Kill-lock gate — blocks start if ~/.spyder_kill_lock exists (N1).
        4. Single-instance PID lock — prevents two launchers trading the same account.

        Returns True if all checks pass; logs the first failure and returns False.
        """
        # 1. Explicit opt-in guard.
        if os.environ.get("LIVE_TRADING_CONFIRMED") != "true":
            self.log_error(
                "❌ Live trading requires LIVE_TRADING_CONFIRMED=true in the environment. "
                "Set the variable and re-run."
            )
            return False

        # 2. Credentials check.
        missing = [
            var for var in ("TRADIER_API_KEY", "TRADIER_ACCOUNT_ID")
            if not os.environ.get(var)
        ]
        if missing:
            self.log_error("❌ Missing required env vars for live mode: %s", missing)
            return False

        # A12 (v14): Safety-config preflight for live mode.
        # Catch the operator error of launching live with emergency-close off,
        # risk limits unset, or the account profile pointing elsewhere.
        emergency_close = os.environ.get("CLOSE_POSITIONS_ON_EMERGENCY", "false").lower()
        if emergency_close != "true":
            self.log_error(
                "❌ Live mode requires CLOSE_POSITIONS_ON_EMERGENCY=true — "
                "emergency stop will NOT flatten positions as currently configured."
            )
            return False

        account_profile = os.environ.get("ACCOUNT_PROFILE", "").lower()
        if account_profile and account_profile not in ("live", "production", "real"):
            self.log_error(
                "❌ Mode is live but ACCOUNT_PROFILE=%s — refusing to start. "
                "Set ACCOUNT_PROFILE=live before running in live mode.",
                account_profile,
            )
            return False

        for var in ("MAX_DAILY_LOSS", "MAX_POSITION_SIZE"):
            raw = os.environ.get(var)
            if raw is None or raw == "":
                self.log_error(
                    "❌ Live mode requires %s to be set (got empty/unset).", var
                )
                return False
            try:
                value = float(raw)
            except (TypeError, ValueError):
                self.log_error(
                    "❌ Live mode env var %s must be numeric, got %r.", var, raw
                )
                return False
            if value <= 0:
                self.log_error(
                    "❌ Live mode env var %s must be > 0, got %s.", var, value
                )
                return False

        # 3. N1: Kill-lock gate — refuse start if a prior session triggered the kill-switch.
        _KILL_LOCK = Path.home() / ".spyder_kill_lock"
        if _KILL_LOCK.exists():
            clear_requested = getattr(self.args, "clear_kill_lock", False)
            try:
                lock_data = json.loads(_KILL_LOCK.read_text())
            except Exception:
                lock_data = {}
            reason = lock_data.get("reason", "unknown")
            ts = lock_data.get("ts", "unknown")
            account = lock_data.get("account_id", "unknown")
            if clear_requested:
                cleared_at = datetime.now().isoformat()
                self.log_info(
                    "🔓 Clearing kill-lock (reason=%s ts=%s account=%s cleared_at=%s)",
                    reason, ts, account, cleared_at,
                )
                try:
                    _KILL_LOCK.unlink()
                except Exception as exc:
                    self.log_error("❌ Failed to remove kill-lock: %s", exc)
                    return False
            else:
                self.log_error(
                    "❌ Kill-lock present — a prior session activated the kill-switch "
                    "(reason=%s ts=%s account=%s). "
                    "Investigate, then re-run with --clear-kill-lock to proceed.",
                    reason, ts, account,
                )
                return False

        # 4. PID lock — prevent duplicate launchers.
        import fcntl
        lock_path = "/tmp/spyder_trading.lock"
        try:
            self._pid_lock_fh = open(lock_path, "w")  # noqa: WPS515
            fcntl.flock(self._pid_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._pid_lock_fh.write(str(os.getpid()))
            self._pid_lock_fh.flush()
        except OSError:
            self.log_error(
                "❌ Another Spyder launcher is already running (lock: %s).", lock_path
            )
            return False

        # 5. Stage 4 — require a successful Go/No-Go today before live start.
        if not self._check_go_no_go_cleared_today():
            return False

        # 6. Stage 4 — warn if kill-switch drill is overdue (> 7 days).
        self._check_kill_switch_test_staleness()

        return True

    # ------------------------------------------------------------------
    # Stage 4 helpers
    # ------------------------------------------------------------------

    def _check_go_no_go_cleared_today(self) -> bool:
        """Stage 4 — P0: Block live start if no passed Go/No-Go report exists today.

        Looks for ``market_data/go_no_go_reports/go_no_go_{YYYY-MM-DD}*.json``
        with ``decision`` != ``"NO-GO"``.  If none is found the operator is
        instructed to run the Go/No-Go checklist first.

        Returns:
            True when at least one today-dated report with a passing decision
            exists; False (and logs the reason) otherwise.
        """
        from datetime import date as _date
        today_str = _date.today().isoformat()
        # Report files live relative to the workspace root (two levels above Q_Scripts).
        _root = Path(__file__).resolve().parents[2]
        reports_dir = _root / "market_data" / "go_no_go_reports"
        if not reports_dir.exists():
            self.log_error(
                "❌ Go/No-Go reports directory not found (%s). "
                "Run the pre-open Go/No-Go checklist in the dashboard before starting live.",
                reports_dir,
            )
            return False

        passing_files = []
        for p in reports_dir.glob(f"go_no_go_{today_str}*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                decision = str(data.get("decision", "")).upper()
                if decision in ("GO", "CONDITIONAL GO"):
                    passing_files.append(p.name)
            except Exception:
                pass  # malformed file — skip

        if not passing_files:
            self.log_error(
                "❌ No passed Go/No-Go report for today (%s) found in %s. "
                "Open the dashboard, run the pre-open checklist, and obtain "
                "GO or CONDITIONAL GO before starting a live session.",
                today_str,
                reports_dir,
            )
            return False

        self.log_info(
            "✅ Go/No-Go cleared for today — %d passing report(s): %s",
            len(passing_files),
            passing_files,
        )
        return True

    def _check_kill_switch_test_staleness(self) -> None:
        """Stage 4 — warn if the kill-switch / emergency-flatten drill is overdue.

        The drill records ``~/.spyder_kill_test.json`` with an ISO timestamp.
        If that file is absent or the recorded timestamp is > 7 calendar days
        ago, a WARNING is logged (but startup is NOT blocked — this is an
        advisory reminder).
        """
        import math as _math
        _KILL_TEST_PATH = Path.home() / ".spyder_kill_test.json"
        STALE_DAYS = 7
        try:
            if not _KILL_TEST_PATH.exists():
                self.log_warning(
                    "⚠️  Kill-switch drill has never been recorded (%s absent). "
                    "Run a controlled kill-switch drill and call "
                    "LiveEngine.record_kill_switch_drill() to clear this warning.",
                    _KILL_TEST_PATH,
                )
                return
            test_data = json.loads(_KILL_TEST_PATH.read_text(encoding="utf-8"))
            last_ts_str = test_data.get("last_test_ts", "")
            if not last_ts_str:
                self.log_warning(
                    "⚠️  Kill-switch drill record has no timestamp — run a drill.",
                )
                return
            from datetime import datetime as _dt, timezone as _tz
            last_ts = _dt.fromisoformat(last_ts_str)
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=_tz.utc)
            now = _dt.now(_tz.utc)
            days_ago = (now - last_ts).total_seconds() / 86400
            if days_ago > STALE_DAYS:
                self.log_warning(
                    "⚠️  Kill-switch drill last recorded %.0f day(s) ago "
                    "(last: %s). Weekly drill is overdue — schedule a controlled test.",
                    _math.floor(days_ago),
                    last_ts_str,
                )
            else:
                self.log_info(
                    "✅ Kill-switch drill is current (last: %s, %.0f day(s) ago).",
                    last_ts_str,
                    _math.floor(days_ago),
                )
        except Exception as exc:
            self.log_warning("⚠️  Could not check kill-switch drill staleness: %s", exc)

    def _broker_preflight_check(self) -> bool:
        """P0-7: Verify the broker is reachable and buying power > 0 after start."""
        supervisor = getattr(self, "_supervisor", None)
        if supervisor is None or not hasattr(supervisor, "broker"):
            return True  # nothing to check in non-live / no-broker scenarios
        try:
            acct = supervisor.broker.get_account()
            buying_power = float((acct or {}).get("buying_power", 0))
            if buying_power <= 0:
                self.log_error(
                    "❌ Broker reachable but buying_power=%.2f — aborting live session.",
                    buying_power,
                )
                return False
            self.log_info("✅ Broker preflight OK (buying_power=%.2f)", buying_power)
        except Exception as exc:
            self.log_error("❌ Broker preflight failed: %s", exc)
            return False
        return True

    def launch_system(self):
        """Launch the full system via SessionSupervisor (S-12)."""
        self.log_info("🚀 Launching Spyder system via SessionSupervisor...")
        try:
            # P0-7: Gate live mode before any session objects are created.
            if self.args.mode == "live" and not self._live_preflight_checks():
                return False

            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import create_session_supervisor
            self._supervisor = create_session_supervisor(
                mode=self.args.mode,
                dry_run=getattr(self.args, "dry_run", False),        # B11 (v15)
                skip_orphan_sweep=getattr(self.args, "skip_orphan_sweep", False),
            )
            if not self._supervisor.start():
                self.log_error("❌ SessionSupervisor failed to start — aborting")
                return False

            # P0-7: Post-start broker health check (live only).
            if self.args.mode == "live" and not self._broker_preflight_check():
                self._supervisor.stop(flatten=False)  # session failed pre-trade; nothing to flatten
                return False

            self.state = SystemState.RUNNING
            self.log_info("✅ Session started (%s mode)", self.args.mode)
            return True
        except Exception as exc:
            self.log_error(f"❌ SessionSupervisor launch failed: {exc}")
            # Fallback: just show status so the user knows something ran.
            return self.show_status()

    # ── S-01: restructured launch routing ─────────────────────────────────────

    def _start_backend(self, mode: str) -> bool:
        """Start the trading backend (SessionSupervisor) for the given mode."""
        return self.launch_system()

    def _run_headless_loop(self) -> bool:
        """Block until SIGTERM / SIGINT, then tear down cleanly."""
        supervisor = getattr(self, "_supervisor", None)
        if supervisor is None:
            self.log_error("❌ _run_headless_loop called with no supervisor — aborting")
            return False
        self.log_info("⏳ Running headless — waiting for SIGTERM / Ctrl-C …")
        try:
            supervisor.block_until_signal()
        finally:
            # P0-6: flatten positions on exit in live mode so SIGTERM / deploy
            # restarts do not leave open positions on the broker.
            flatten = getattr(self.args, "mode", "paper") == "live"
            supervisor.stop(flatten=flatten)
            self.state = SystemState.STOPPED
            self.log_info("🛑 Headless session stopped cleanly (flatten=%s).", flatten)
        return True

    def _run_gui_attached_to_backend(self) -> bool:
        """Attach the Qt dashboard to the already-running backend."""
        if not GUI_AVAILABLE:
            self.log_warning("⚠️ GUI modules not available — falling back to headless loop")
            return self._run_headless_loop()
        self.log_info("🖥️ Attaching GUI to running backend …")
        try:
            return self.launch_gui()
        except Exception as exc:
            self.log_error(f"❌ GUI attach failed: {exc} — falling back to headless loop")
            return self._run_headless_loop()

    def _request_shutdown(self) -> bool:
        """Handle a --shutdown request gracefully."""
        self.log_info("🛑 Shutdown requested via CLI flag.")
        supervisor = getattr(self, "_supervisor", None)
        if supervisor is not None:
            flatten = getattr(self.args, "mode", "paper") == "live"
            supervisor.stop(flatten=flatten)
        self.state = SystemState.STOPPED
        return True

    def launch(self) -> bool:
        """Main launch method (S-01)."""
        try:
            self._log_startup_info()

            if self.args.status:
                return self.show_status()

            if self.args.module:
                return self.run_specific_module(self.args.module)

            if self.args.shutdown:
                return self._request_shutdown()

            # 1. Always start the trading backend regardless of GUI flag.
            backend_ok = self._start_backend(self.args.mode)
            if not backend_ok:
                return False

            # 2. Optionally attach the dashboard on top of the running backend.
            if self.args.gui and not self.args.headless and GUI_AVAILABLE:
                return self._run_gui_attached_to_backend()

            # Headless: block until SIGTERM / KeyboardInterrupt then clean up.
            return self._run_headless_loop()

        except KeyboardInterrupt:
            self.log_info("🛑 Interrupted by user")
            self._safe_stop_supervisor()
            return True
        except Exception as exc:
            self.log_error(f"❌ Launch failed: {exc}")
            if self.args.debug:
                import traceback
                traceback.print_exc()
            self._safe_stop_supervisor()
            return False

    def _safe_stop_supervisor(self) -> None:
        """Stop the supervisor with flatten=True iff in live mode.

        Centralised so every exit path (SIGTERM, KeyboardInterrupt, uncaught
        exception) uses identical flatten logic.
        """
        supervisor = getattr(self, "_supervisor", None)
        if supervisor is None:
            return
        flatten = getattr(self.args, "mode", "paper") == "live"
        try:
            supervisor.stop(flatten=flatten)
        except Exception as exc:
            self.log_error(f"❌ Supervisor stop failed during shutdown: {exc}")

# ==============================================================================
# MAIN FUNCTION
# ==============================================================================
def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Spyder Autonomous Options Trading System Launcher (Fixed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python SpyderQ14_MainLauncher.py --status
  python SpyderQ14_MainLauncher.py --mode paper --gui
  python SpyderQ14_MainLauncher.py --module SpyderG05_TradingDashboard
  python SpyderQ14_MainLauncher.py --mode live --headless
        """
    )

    parser.add_argument("--mode", choices=["live", "paper"],
                       default="paper", help="Trading mode")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--gui", action="store_true", default=True, help="Launch with GUI")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--safe-mode", action="store_true", help="Start with minimal modules")
    parser.add_argument("--module", type=str, help="Start specific module only")
    parser.add_argument("--status", action="store_true", help="Check system status and exit")
    parser.add_argument("--shutdown", action="store_true", help="Shutdown running system")
    parser.add_argument(
        "--clear-kill-lock",
        action="store_true",
        help="Clear the ~/.spyder_kill_lock file and allow live trading to start. "
             "CAUTION: only use after confirming the triggering risk event is resolved.",
    )
    parser.add_argument(
        "--skip-orphan-sweep",
        action="store_true",
        dest="skip_orphan_sweep",
        help="Skip the boot-time orphan position sweep (P1-3). "
             "Use when restarting on an empty account to avoid misleading orphan alerts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Suppress broker order placement — log what would be sent instead. "
             "Safe for integration rehearsals without live/paper order submission.",
    )

    args = parser.parse_args()

    # Handle shutdown request
    if args.shutdown:
        print("🛑 Shutdown requested")
        # Add shutdown logic here if needed
        return 0

    # Create and run launcher
    launcher = SpyderLauncher(args)
    success = launcher.launch()

    return 0 if success else 1

# ==============================================================================
# SCRIPT ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    sys.exit(main())
