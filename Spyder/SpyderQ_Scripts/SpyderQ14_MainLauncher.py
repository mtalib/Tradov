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
    --mode          : Trading mode (live/paper/backtest) [default: paper]
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
import os
import subprocess
import sys
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
                                    if hasattr(window, 'show'):
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

    def launch_system(self):
        """Launch the full system"""
        self.log_info("🚀 Launching Spyder system...")

        if CORE_AVAILABLE and master_controller:
            try:
                # Try to use the master controller
                controller = master_controller()
                if hasattr(controller, 'start'):
                    controller.start()
                    self.state = SystemState.RUNNING
                    self.log_info("✅ System started successfully")
                else:
                    self.log_warning("⚠️ Controller has no start method")
            except Exception as e:
                self.log_error(f"❌ System startup failed: {e}")

        if self.args.mode == "live":
            self._start_live_engine()
        elif self.args.mode == "paper":
            self.log_info("📄 Paper trading mode — using simulated execution")

        # Fallback: just show status
        if self.state != SystemState.RUNNING:
            self.log_warning("⚠️ Full system startup not available, showing status instead")
            return self.show_status()

        return True

    def _start_live_engine(self) -> None:
        """Import and start SpyderR04_LiveEngine for live trading."""
        self.log_info("🔴 LIVE TRADING MODE — initialising live engine...")
        try:
            from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import create_live_engine
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import create_tradier_client_from_env
            from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
        except ImportError as e:
            self.log_error(f"❌ Live engine prerequisites missing — cannot start live: {e}")
            return

        try:
            # create_tradier_client_from_env() reads TRADIER_ENVIRONMENT automatically.
            # In live mode this will be "live" (api.tradier.com) unless explicitly overridden.
            broker = create_tradier_client_from_env()
            risk_manager = get_risk_manager()
            config = {
                "account_id": os.environ.get("TRADIER_ACCOUNT_ID"),
                "max_daily_trades": int(os.environ.get("MAX_DAILY_TRADES", 100)),
                "max_daily_loss": float(os.environ.get("MAX_DAILY_LOSS_USD", 10000)),
                "require_confirmation": True,  # Always confirm live orders
            }
            live_engine = create_live_engine(broker, risk_manager, config)
            if live_engine.initialize():
                self.log_info("✅ Live engine initialised — safety guards active")
                live_engine.start()
                self.state = SystemState.RUNNING
            else:
                self.log_error("❌ Live engine initialisation failed — aborting live mode")
        except Exception as e:
            self.log_error(f"❌ Failed to start live engine: {e}")

    def launch(self):
        """Main launch method"""
        try:
            self._log_startup_info()

            if self.args.status:
                return self.show_status()

            if self.args.module:
                return self.run_specific_module(self.args.module)

            if self.args.gui and not self.args.headless:
                if GUI_AVAILABLE:
                    return self.launch_gui()
                else:
                    self.log_error("❌ GUI not available, showing status instead")
                    return self.show_status()

            # Default: try to launch full system
            return self.launch_system()

        except KeyboardInterrupt:
            self.log_info("🛑 Interrupted by user")
            return True
        except Exception as e:
            self.log_error(f"❌ Launch failed: {e}")
            if self.args.debug:
                import traceback
                traceback.print_exc()
            return False

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

    parser.add_argument("--mode", choices=["live", "paper", "backtest"],
                       default="paper", help="Trading mode")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--gui", action="store_true", default=True, help="Launch with GUI")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--safe-mode", action="store_true", help="Start with minimal modules")
    parser.add_argument("--module", type=str, help="Start specific module only")
    parser.add_argument("--status", action="store_true", help="Check system status and exit")
    parser.add_argument("--shutdown", action="store_true", help="Shutdown running system")

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
