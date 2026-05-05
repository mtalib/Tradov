#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA01_Main.py
Purpose: Main application entry point with PROVEN race condition fix
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-10 Time: 17:30:00

CRITICAL FIX: Now uses the EXACT working pattern from successful test:
await asyncio.sleep(1.0) immediately after connection for API handshake stability.
This ensures the GUI launches properly after establishing reliable broker connections.
"""

import importlib.util
import os
import sys
import logging
import signal
import time
import asyncio
from pathlib import Path
from typing import Any, TYPE_CHECKING

# Install uvloop as the asyncio event loop (2-4x faster on Linux/macOS)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass  # Falls back to default asyncio event loop

# Add project root to path (now need to go up 3 levels: SpyderA01_Main.py -> SpyderA_Core -> Spyder -> project_root)  # noqa: E501
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Try to import Qt modules for GUI
# Using lowercase to avoid constant redefinition warnings
has_qt = False

if TYPE_CHECKING:
    from PySide6.QtWidgets import (
        QApplication,
        QWidget,
        QVBoxLayout,
        QLabel,
        QPushButton,
        QTextEdit,
    )
    from PySide6.QtCore import QTimer, Signal, QObject, QThread
    from PySide6.QtGui import QIcon, QFont
else:
    QApplication: type | None = None
    QWidget: type | None = None
    QVBoxLayout: type | None = None
    QLabel: type | None = None
    QPushButton: type | None = None
    QTextEdit: type | None = None
    QTimer: type | None = None
    Signal: type | None = None
    QObject: type | None = None
    QThread: type | None = None
    QIcon: type | None = None
    QFont: type | None = None

    try:
        from PySide6.QtWidgets import (
            QApplication,
            QWidget,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QTextEdit,
        )
        from PySide6.QtCore import QTimer, Signal, QObject, QThread  # noqa: F401
        from PySide6.QtGui import QIcon, QFont  # noqa: F401

        has_qt = True
    except ImportError:
        logging.getLogger("SpyderA01_Main").warning("PySide6 not available. GUI mode disabled.")

# Import Spyder modules with separated error handling
# Logger (required)
has_logger = False
setup_logging_func: Any = None
get_logger_func: Any = None

try:
    from Spyder.SpyderU_Utilities.SpyderU44_ShutdownCoordinator import get_shutdown_coordinator as _get_coordinator  # noqa: E501
    _HAS_COORDINATOR = True
except ImportError:
    _get_coordinator = None
    _HAS_COORDINATOR = False

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import get_logger, SpyderLogger

    def setup_logging(**_kwargs: Any) -> None:
        SpyderLogger.initialize_logging()

    setup_logging_func = setup_logging
    get_logger_func = get_logger
    has_logger = True
except ImportError as e:
    logging.getLogger("SpyderA01_Main").warning("Logger not available: %s", e)

    def setup_logging(**_kwargs: Any) -> None:
        pass

    def get_logger(name: str) -> Any:
        return logging.getLogger(name)

    setup_logging_func = setup_logging
    get_logger_func = get_logger


# EventManager (optional)
has_event_manager = False
EventManager: type | None = None
Event: type | None = None

try:
    from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, get_event_manager  # noqa: F401

    has_event_manager = True
except ImportError:
    pass

# Broker modules — B01_SpyderClient and B05_ConnectionManager removed (legacy broker)
# Tradier API integration is handled by SpyderB40_TradierClient
has_broker_modules = False
get_spyder_client = None
get_connection_manager = None

# NOTE: GUI imports (SpyderG05_TradingDashboard, etc.) are intentionally deferred.
# They are loaded lazily inside start_gui() to avoid importing matplotlib/plotly/PySide6
# at module level, which would add 2+ seconds to any code that imports A01_Main.

# ==============================================================================
# CONFIGURATION
# ==============================================================================


class SpyderConfig:
    """Spyder application configuration with PROVEN race condition fix"""

    def __init__(self) -> None:
        # Application settings
        self.app_name: str = "SPYDER"
        self.version: str = "1.0"
        self.debug_mode: bool = False  # PRODUCTION MODE

        # Broker connection settings (Tradier API via SpyderB40_TradierClient)
        self.master_client_id: int = 2
        self.connection_timeout: float = 20.0

        # GUI settings
        self.enable_gui: bool = True
        self.window_width: int = 1200
        self.window_height: int = 800

        # Logging settings - PRODUCTION MODE (minimal output)
        self.log_level: int = logging.ERROR  # Only errors in production
        self.log_to_file: bool = True
        self.log_dir: Path = project_root / "logs"

        # Operation modes
        self.headless_mode: bool = False
        self.simulation_mode: bool = False


# ==============================================================================
# SIMPLE GUI FOR CONNECTION TESTING
# ==============================================================================

if TYPE_CHECKING or has_qt:
    _BaseWidget = QWidget  # type: ignore[misc, name-defined]
else:
    _BaseWidget = object


class SpyderMainWindow(_BaseWidget):  # type: ignore[misc]
    """
    Simple main window for testing PROVEN race condition fix.

    This window will only appear after successful broker connection,
    proving that the race condition fix is working.
    """

    def __init__(self, spyder_app: "SpyderApplication") -> None:
        super().__init__()
        self.spyder_app: SpyderApplication = spyder_app
        self.status_label: Any = None
        self.connection_info: Any = None
        self.test_button: Any = None
        self.disconnect_button: Any = None
        self.exit_button: Any = None
        self.timer: Any = None
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle(
            f"SPYDER v{self.spyder_app.config.version} - PROVEN Race Condition Fix"
        )
        self.setGeometry(
            100,
            100,
            self.spyder_app.config.window_width,
            self.spyder_app.config.window_height,
        )

        # Create layout
        if QVBoxLayout is None:
            return
        layout = QVBoxLayout()

        # Title
        if QLabel is None:
            return
        title = QLabel("SPYDER - Autonomous Options Trading System")
        title.setStyleSheet(
            "font-size: 24px; font-weight: normal; color: #2E8B57; margin: 20px;"
        )
        layout.addWidget(title)

        # Status label
        if QLabel is None:
            return
        self.status_label = QLabel("Initializing with PROVEN race condition fix...")
        self.status_label.setStyleSheet(
            "font-size: 14px; margin: 10px; padding: 10px; background-color: #f0f0f0;"
        )
        layout.addWidget(self.status_label)

        # Connection info
        if QTextEdit is None:
            return
        self.connection_info = QTextEdit()
        self.connection_info.setMaximumHeight(200)
        self.connection_info.setStyleSheet("font-family: monospace; font-size: 10px;")
        layout.addWidget(self.connection_info)

        # Test button
        if QPushButton is None:
            return
        self.test_button = QPushButton("Test PROVEN Race Condition Fix")
        _ = self.test_button.clicked.connect(self.test_connection_fix)
        self.test_button.setStyleSheet(
            "font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;"
        )
        layout.addWidget(self.test_button)

        # Disconnect button
        if QPushButton is None:
            return
        self.disconnect_button = QPushButton("Disconnect")
        _ = self.disconnect_button.clicked.connect(self.disconnect_broker)
        self.disconnect_button.setStyleSheet(
            "font-size: 14px; padding: 10px; background-color: #f44336; color: white;"
        )
        layout.addWidget(self.disconnect_button)

        # Exit button
        if QPushButton is None:
            return
        self.exit_button = QPushButton("Exit")
        _ = self.exit_button.clicked.connect(self.close)
        self.exit_button.setStyleSheet(
            "font-size: 14px; padding: 10px; background-color: #9E9E9E; color: white;"
        )
        layout.addWidget(self.exit_button)

        self.setLayout(layout)

        # Set up timer for status updates
        if QTimer is None:
            return
        self.timer = QTimer()
        _ = self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # Update every second

    def update_status(self) -> None:
        """Update the status display."""
        try:
            if self.spyder_app.client and self.spyder_app.client.is_connected():
                status = self.spyder_app.client.get_connection_status()

                # Safely get account info
                account_info: dict[str, Any] = {}
                if hasattr(self.spyder_app.client, "get_account_info"):
                    try:
                        account_info = self.spyder_app.client.get_account_info()
                    except Exception as e:
                        self.spyder_app.logger.warning(
                            "Failed to get account info: %s", e
                        )
                        account_info = {"accounts": [], "connection_status": "Error"}

                self.status_label.setText(
                    "✅ CONNECTED with PROVEN race condition fix!"
                )
                self.status_label.setStyleSheet(
                    "font-size: 14px; margin: 10px; padding: 10px; background-color: #d4edda; color: #155724;"  # noqa: E501
                )

                # Update connection info
                info_text = f"""Connection Status:
- Source: {status.get("source", "Unknown")}
- Connected: {status.get("connected", False)}
- Client ID: {self.spyder_app.config.master_client_id}
- Broker: Tradier API (SpyderB40_TradierClient)

Account Info:
- Accounts: {account_info.get("accounts", "N/A")}
- Status: {account_info.get("connection_status", "Unknown")}

GUI Status: VISIBLE (proving connection is stable!)
"""
                self.connection_info.setText(info_text)
            else:
                self.status_label.setText("❌ DISCONNECTED")
                self.status_label.setStyleSheet(
                    "font-size: 14px; margin: 10px; padding: 10px; background-color: #f8d7da; color: #721c24;"  # noqa: E501
                )
                self.connection_info.setText("Not connected to broker")
        except Exception as e:
            # Log the error but don't crash the GUI
            if hasattr(self.spyder_app, "logger"):
                self.spyder_app.logger.error("Status update error: %s", e, exc_info=True)
            else:
                logging.getLogger("SpyderA01_Main").error("Status update error: %s", e)

    def test_connection_fix(self) -> None:
        """Test the PROVEN race condition fix."""
        if self.spyder_app.client:
            self.connection_info.append("\n🧪 Testing PROVEN race condition fix...")

            # Check if the test method exists
            if hasattr(self.spyder_app.client, "test_connection_with_proven_fix"):
                result = self.spyder_app.client.test_connection_with_proven_fix()

                if result.get("success"):
                    self.connection_info.append(
                        "✅ Race condition fix test SUCCESSFUL!"
                    )
                    self.connection_info.append(f"Result: {result}")
                else:
                    self.connection_info.append("❌ Race condition fix test FAILED!")
                    self.connection_info.append(
                        f"Error: {result.get('error', 'Unknown error')}"
                    )
            else:
                # Basic connection test
                if self.spyder_app.client.is_connected():
                    self.connection_info.append("✅ Basic connection test SUCCESSFUL!")
                else:
                    self.connection_info.append("❌ Basic connection test FAILED!")

    def disconnect_broker(self) -> None:
        """Disconnect from broker."""
        if self.spyder_app.client:
            self.spyder_app.client.disconnect()
            self.connection_info.append("\n🔌 Disconnected from broker")


# ==============================================================================
# MAIN SPYDER APPLICATION CLASS
# ==============================================================================


class SpyderApplication:
    """
    Main SPYDER application with PROVEN race condition fix integration.

    This class manages the complete application lifecycle and demonstrates
    that the GUI will only appear after successful broker connection using
    the proven race condition fix.
    """

    def __init__(self, config: SpyderConfig | None = None) -> None:
        """Initialize SPYDER application with PROVEN race condition fix."""

        # Configuration
        self.config: SpyderConfig = config or SpyderConfig()

        # Setup logging first
        self._setup_logging()
        self.logger: Any = get_logger_func("SpyderApplication")

        # Core components
        self.event_manager: Any = None
        self.connection_manager: Any = None
        self.client: Any = None
        self.telegram_bot: Any = None
        self.session_supervisor: Any = None
        self.gui_app: Any = None
        self.main_window: Any = None

        # Application state
        self.running: bool = False
        self.shutdown_requested: bool = False

        # Register application shutdown with the process-wide coordinator so
        # that broker streams and data feed threads are stopped cleanly on exit.
        if _HAS_COORDINATOR:
            _get_coordinator().register_cleanup(self.shutdown)

        self.logger.info("=" * 70)
        self.logger.info("SPYDER v%s - PROVEN Race Condition Fix", self.config.version)
        self.logger.info("=" * 70)
        self.logger.info(
            "Initializing application with proven broker connection fix..."
        )

    # ------------------------------------------------------------------
    # Capability report
    # ------------------------------------------------------------------
    def _log_capability_report(self) -> None:
        """Log an ASCII capability table showing which optional modules loaded."""

        # ── package → (display_name, critical, notes_if_missing) ──────────────
        _CAPABILITIES: list[tuple[str, str, bool, str]] = [
            # package_name             display_name                       critical  note_if_missing
            ("PySide6",                "GUI Dashboard (PySide6)",          True,  "run: pip install PySide6"),  # noqa: E501
            ("sklearn",                "ML Regime Detection (scikit-learn)",False, "run: pip install scikit-learn"),  # noqa: E501
            ("hmmlearn",               "HMM Regime Models (hmmlearn)",     False, "run: pip install hmmlearn"),  # noqa: E501
            ("zmq",                    "ZeroMQ Messaging (pyzmq)",         False, "run: pip install pyzmq"),  # noqa: E501
            ("prometheus_client",      "Prometheus Metrics",               False, "run: pip install prometheus-client"),  # noqa: E501
            ("QuantLib",               "QuantLib Pricing Engine",          False, "run: pip install QuantLib"),  # noqa: E501
            ("uvloop",                 "uvloop Event Loop (2-4x faster)",  False, "run: pip install uvloop"),  # noqa: E501
            ("asyncio",                "asyncio (stdlib)",                 True,  "stdlib — should always be present"),  # noqa: E501
        ]

        # Build rows: check each package with importlib.util.find_spec()
        rows: list[tuple[str, str, str]] = []
        missing_critical: list[str] = []

        for pkg, display, critical, note in _CAPABILITIES:
            available = importlib.util.find_spec(pkg) is not None
            status = "\u2713 ACTIVE " if available else "\u2717 MISSING"
            notes = "" if available else note
            rows.append((display, status, notes))
            if not available and critical:
                missing_critical.append(f"{display} — {note}")

        # ── column widths ──────────────────────────────────────────────────────
        col1 = max(len(r[0]) for r in rows)
        col1 = max(col1, len("Capability"))
        col2 = max(len(r[1]) for r in rows)
        col2 = max(col2, len("Status"))
        col3 = max(len(r[2]) for r in rows) if any(r[2] for r in rows) else len("Notes")
        col3 = max(col3, len("Notes"))

        pad = 1  # one space padding on each side

        def rule(left: str, mid: str, right: str, fill: str) -> str:
            return (
                left
                + fill * (col1 + 2 * pad)
                + mid
                + fill * (col2 + 2 * pad)
                + mid
                + fill * (col3 + 2 * pad)
                + right
            )

        def row_line(c1: str, c2: str, c3: str) -> str:
            return (
                "\u2551"
                + f" {c1:<{col1}} "
                + "\u2551"
                + f" {c2:<{col2}} "
                + "\u2551"
                + f" {c3:<{col3}} "
                + "\u2551"
            )

        top    = rule("\u2554", "\u2566", "\u2557", "\u2550")
        header = row_line("Capability", "Status", "Notes")
        sep    = rule("\u2560", "\u256c", "\u2563", "\u2550")
        bottom = rule("\u255a", "\u2569", "\u255d", "\u2550")

        # Title banner
        title_inner = col1 + 2 * pad + 1 + col2 + 2 * pad + 1 + col3 + 2 * pad
        title_text = "SPYDER CAPABILITY REPORT"
        title_line = "\u2551" + title_text.center(title_inner) + "\u2551"
        banner_top    = "\u2554" + "\u2550" * title_inner + "\u2557"
        banner_bottom = "\u255a" + "\u2550" * title_inner + "\u255d"

        self.logger.info(banner_top)
        self.logger.info(title_line)
        self.logger.info(banner_bottom)
        self.logger.info(top)
        self.logger.info(header)
        self.logger.info(sep)
        for cap, status, notes in rows:
            self.logger.info(row_line(cap, status, notes))
        self.logger.info(bottom)
        self.logger.info("")

        # ── one-line warnings for each missing critical capability ─────────────
        for warning in missing_critical:
            self.logger.warning("MISSING CRITICAL CAPABILITY: %s", warning)

    def _setup_logging(self) -> None:
        """Setup application logging with reduced verbosity to prevent Gateway flooding."""
        try:
            if has_logger and setup_logging_func:
                setup_logging_func()
            else:
                # Fallback: attach a handler to the Spyder package logger only,
                # leaving the root logger untouched.
                _spyder_root = logging.getLogger("Spyder")
                if not _spyder_root.handlers:
                    _handler = logging.StreamHandler()
                    _handler.setFormatter(
                        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                    )
                    _spyder_root.addHandler(_handler)
                _spyder_root.setLevel(self.config.log_level)

            # Reduce dashboard worker logging (unconditional — applies on both paths)
            logging.getLogger("SpyderG_GUI.SpyderG05_TradingDashboard").setLevel(logging.INFO)

        except Exception as e:
            logging.getLogger("SpyderA01_Main").warning("Could not setup advanced logging: %s", e)
            _spyder_root = logging.getLogger("Spyder")
            if not _spyder_root.handlers:
                _spyder_root.addHandler(logging.StreamHandler())

    def initialize_core_systems(self) -> bool:
        """
        Initialize core systems with PROVEN race condition fix.

        The GUI will only appear if this succeeds, proving the fix works.
        """
        try:
            self.logger.info(
                "🔧 Initializing core systems with PROVEN race condition fix..."
            )

            # Initialize event manager (optional)
            if has_event_manager and EventManager:
                try:
                    self.event_manager = get_event_manager()
                    self.logger.info("✅ Event manager initialized")
                except Exception as e:
                    self.logger.warning("Event manager initialization failed: %s", e, exc_info=True)
                    self.event_manager = None
            else:
                self.logger.info(
                    "ℹ️ Event manager not available - continuing without it"
                )

            # Using standard connection approach
            self.logger.info(
                "⚡ Skipping blocking connection at startup for fast launch"
            )
            self.logger.info(
                "🔄 Dashboard will auto-connect via polling timer when available"
            )

            self.client = None  # Tradier client (set by dashboard connection)

            # Initialize Telegram bot (optional). This enables outbound alerts
            # and inbound operator commands when A01 is used as entrypoint.
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
            if bot_token and chat_id and self.event_manager is not None:
                try:
                    from Spyder.SpyderJ_Alerts.SpyderJ05_TelegramBot import TelegramBot

                    self.telegram_bot = TelegramBot(
                        bot_token=bot_token,
                        chat_id=chat_id,
                        event_manager=self.event_manager,
                    )
                    self.telegram_bot.start()
                    self.logger.info("✅ Telegram bot initialized from A01")
                except Exception as e:
                    self.logger.warning(
                        "Telegram bot initialization failed in A01: %s", e, exc_info=True
                    )
            elif bot_token and chat_id and self.event_manager is None:
                self.logger.warning(
                    "Telegram env present, but EventManager unavailable; "
                    "Telegram bot not initialized"
                )
            else:
                self.logger.info("ℹ️ Telegram bot not configured for A01 startup")

            # Optionally autostart SessionSupervisor from A01. This is useful
            # for icon-launch workflows that rely on Telegram /status and
            # /resume gates checking session_supervisor state.
            autostart_raw = os.environ.get(
                "SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", "0"
            ).strip().lower()
            should_autostart = autostart_raw in ("1", "true", "yes", "on")
            if should_autostart:
                mode = os.environ.get("SPYDER_A01_AUTOSTART_MODE", "paper").strip().lower()
                if mode not in ("paper", "live"):
                    self.logger.warning(
                        "Invalid SPYDER_A01_AUTOSTART_MODE=%s, falling back to paper",
                        mode,
                    )
                    mode = "paper"

                # Never autostart live mode unless explicitly allowed.
                if mode == "live":
                    allow_live = os.environ.get(
                        "SPYDER_A01_ALLOW_LIVE_AUTOSTART", "0"
                    ).strip().lower() in ("1", "true", "yes", "on")
                    if not allow_live:
                        self.logger.warning(
                            "Live autostart requested but blocked. "
                            "Set SPYDER_A01_ALLOW_LIVE_AUTOSTART=1 to enable. "
                            "Falling back to paper mode."
                        )
                        mode = "paper"

                try:
                    from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import (
                        create_session_supervisor,
                    )

                    self.session_supervisor = create_session_supervisor(mode=mode)
                    if self.session_supervisor.start():
                        self.logger.info(
                            "✅ SessionSupervisor autostarted from A01 (mode=%s)",
                            mode,
                        )
                    else:
                        self.logger.warning(
                            "SessionSupervisor autostart failed from A01 (mode=%s)",
                            mode,
                        )
                        self.session_supervisor = None
                except Exception as exc:
                    self.logger.warning(
                        "SessionSupervisor autostart exception in A01: %s",
                        exc,
                        exc_info=True,
                    )
                    self.session_supervisor = None
            else:
                self.logger.info("ℹ️ SessionSupervisor autostart disabled in A01")

            self.logger.info("✅ Core systems initialized successfully!")

            # Log which optional capabilities are available before the event loop starts
            self._log_capability_report()

            return True

        except Exception as e:
            self.logger.error("❌ Core system initialization failed: %s", e, exc_info=True)
            return False

    def _initialize_broker_connection(self) -> bool:
        """
        Initialize broker connection with race condition fix.
        This method is not used when skipping broker initialization.
        """
        self.logger.info("Broker initialization skipped for fast startup")
        return True

    def start_gui(self) -> bool:
        """
        Start the GUI application.

        This method will only succeed if broker connection was established,
        proving the race condition fix is working.
        """
        if not has_qt:
            self.logger.error("PySide6 not available - GUI disabled. Run: pip install PySide6")
            return False

        try:
            self.logger.info(
                "🎨 Starting GUI with PROVEN race condition fix validation..."
            )

            # Create Qt application
            if QApplication is None:
                raise RuntimeError("QApplication is not available")
            self.gui_app = QApplication(sys.argv)

            # CRITICAL: Set desktop file name for Wayland/GNOME integration
            # This ensures the window appears under the launcher icon
            self.gui_app.setDesktopFileName("spyder-trading-system")

            self.gui_app.setApplicationName(self.config.app_name)
            self.gui_app.setApplicationVersion(self.config.version)

            # Create main window - lazy-load GUI modules (deferred to avoid slow startup)
            # Try real SpyderG05 Trading Dashboard first
            has_trading_dashboard = False
            SpyderTradingDashboard = None
            try:
                from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard  # type: ignore[assignment]
                has_trading_dashboard = True
                self.logger.info("Real Trading Dashboard (G05) loaded successfully.")
            except ImportError as e:
                self.logger.warning("Trading Dashboard not available: %s", e)

            # Lazy-load GUI log handler
            setup_gui_logging = None
            try:
                from Spyder.SpyderG_GUI.SpyderG99_GUILogHandler import setup_gui_logging  # type: ignore[assignment]
            except ImportError:
                pass

            # Lazy-load fallback Working Trading Dashboard
            has_working_dashboard = False
            WorkingSpyderDashboard = None
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    "launch_spyder_working_dashboard",
                    project_root / "launch_spyder_working_dashboard.py"
                )
                if _spec and _spec.loader:
                    _wmod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_wmod)  # type: ignore[union-attr]
                    WorkingSpyderDashboard = _wmod.WorkingSpyderDashboard
                    has_working_dashboard = True
                    self.logger.info("Working Trading Dashboard loaded.")
            except Exception:
                pass

            if has_trading_dashboard and SpyderTradingDashboard:
                self.logger.info("🚀 Starting REAL SpyderG05 Trading Dashboard...")

                try:
                    self.main_window = SpyderTradingDashboard()
                except Exception as e:
                    self.logger.error("❌ Failed to create dashboard: %s", e, exc_info=True)
                    import traceback

                    self.logger.debug(traceback.format_exc())
                    raise

                # The dashboard now manages its own connection via its polling timer.
                # No client needs to be passed from the main application.
                self.logger.info(
                    "ℹ️ Dashboard will manage its own connection."
                )

                # If A01 pre-started a SessionSupervisor (SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR=1),
                # inject it into the dashboard so G05 reuses it instead of creating a second
                # instance (which would fail to bind the healthz port).
                if self.session_supervisor is not None:
                    self.main_window._session_supervisor = self.session_supervisor
                    self.logger.info(
                        "✅ A01 SessionSupervisor injected into dashboard — reusing existing session"
                    )

                self.main_window.show()
                self.logger.info("✅ Real Trading Dashboard launched successfully!")

                # Setup GUI logging to route logs to dashboard widgets
                try:
                    import os
                    gui_log_level = os.environ.get("GUI_LOG_LEVEL", "INFO")
                    if setup_gui_logging is not None:
                        self.gui_log_handler = setup_gui_logging(
                            self.main_window,
                            log_level=gui_log_level
                        )
                        self.logger.debug("✅ GUI logging handler connected (level: %s)", gui_log_level)  # noqa: E501
                except Exception as e:
                    self.logger.warning("⚠️ Could not setup GUI logging: %s", e, exc_info=True)
            elif has_working_dashboard and WorkingSpyderDashboard:
                self.logger.info("🚀 Starting Working Trading Dashboard (fallback)...")

                try:
                    self.main_window = WorkingSpyderDashboard()
                except Exception as e:
                    self.logger.error("❌ Failed to create working dashboard: %s", e, exc_info=True)
                    import traceback

                    self.logger.debug(traceback.format_exc())
                    raise

                self.main_window.show()
                self.logger.info("✅ Working Trading Dashboard launched successfully!")

                # Setup GUI logging to route logs to dashboard widgets
                try:
                    import os
                    gui_log_level = os.environ.get("GUI_LOG_LEVEL", "INFO")
                    if setup_gui_logging is not None:
                        self.gui_log_handler = setup_gui_logging(
                            self.main_window,
                            log_level=gui_log_level
                        )
                        self.logger.debug("✅ GUI logging handler connected (level: %s)", gui_log_level)  # noqa: E501
                except Exception as e:
                    self.logger.warning("⚠️ Could not setup GUI logging: %s", e, exc_info=True)
            else:
                self.logger.info(
                    "⚠️ Trading Dashboard not available, using test window..."
                )
                self.main_window = SpyderMainWindow(self)
                self.main_window.show()

            self.logger.debug("✅ GUI started successfully")

            return True

        except Exception as e:
            self.logger.error("❌ GUI startup failed: %s", e, exc_info=True)
            import traceback

            self.logger.debug(traceback.format_exc())
            return False

    def run(self) -> int:
        """
        Run the complete SPYDER application with PROVEN race condition fix.

        Returns:
            int: Exit code (0 = success, 1 = failure)
        """
        try:
            self.logger.info("🚀 Starting SPYDER with PROVEN race condition fix...")
            self.running = True

            # Fail-fast: validate all required environment variables before doing
            # anything else.  validate_startup_config() raises ConfigurationError
            # with a complete list of problems if anything is wrong.
            try:
                from config.config import validate_startup_config
                validate_startup_config()
                self.logger.info("✅ Startup configuration validated successfully")
            except ImportError:
                self.logger.warning("⚠️ config.config not importable — skipping startup config validation")  # noqa: E501
            except Exception as cfg_err:  # ConfigurationError or anything unexpected
                self.logger.error("❌ Startup configuration invalid:\n%s", cfg_err)
                return 1

            # Initialize core systems (includes broker connection with race condition fix)
            if not self.initialize_core_systems():
                self.logger.error("❌ Core system initialization failed")
                return 1

            # Start GUI (only appears if broker connection succeeded)
            if self.config.enable_gui and not self.config.headless_mode:
                if not self.start_gui():
                    self.logger.error("❌ GUI startup failed")
                    return 1

                # Run GUI event loop
                self.logger.debug("🔄 Running GUI event loop...")
                exit_code = self.gui_app.exec()
                self.logger.debug("GUI event loop ended with code: %s", exit_code)
                return exit_code
            else:
                # Headless mode
                self.logger.info("🖥️ Running in headless mode...")
                try:
                    while self.running and not self.shutdown_requested:
                        time.sleep(1.0)  # thread-safe: time.sleep() intentional
                except KeyboardInterrupt:
                    self.logger.info("Received keyboard interrupt")
                return 0

        except Exception as e:
            self.logger.error("❌ Application runtime error: %s", e, exc_info=True)
            import traceback

            self.logger.debug(traceback.format_exc())
            return 1
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        if not self.shutdown_requested:
            self.logger.info("🔄 Shutting down SPYDER...")
            self.shutdown_requested = True
            self.running = False

            # Disconnect broker
            if self.client:
                try:
                    self.client.disconnect()
                    self.logger.info("🔌 Broker disconnected")
                except Exception as e:
                    self.logger.warning("Broker disconnect error: %s", e, exc_info=True)

            # Stop Telegram bot worker/poller threads
            if self.telegram_bot:
                try:
                    self.telegram_bot.stop()
                    self.logger.info("📨 Telegram bot stopped")
                except Exception as e:
                    self.logger.warning("Telegram bot stop error: %s", e, exc_info=True)

            # Stop unified session supervisor if A01 started it.
            if self.session_supervisor:
                try:
                    self.session_supervisor.stop(flatten=False)
                    self.logger.info("🧭 SessionSupervisor stopped")
                except Exception as e:
                    self.logger.warning("SessionSupervisor stop error: %s", e, exc_info=True)
                finally:
                    self.session_supervisor = None

            # Cleanup GUI
            if self.gui_app:
                try:
                    self.gui_app.quit()
                except Exception as e:
                    self.logger.warning("GUI cleanup error: %s", e, exc_info=True)

            self.logger.info("✅ Shutdown complete")


def _load_runtime_dotenv(startup_log: logging.Logger) -> None:
    """Load runtime .env settings when running the A01 entrypoint directly."""
    try:
        from dotenv import load_dotenv

        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            startup_log.info("Loaded environment from %s", env_path)
        else:
            startup_log.info("No .env file found at %s", env_path)
    except ImportError:
        startup_log.warning(
            "python-dotenv not installed; relying on pre-exported environment variables"
        )
    except Exception as exc:
        startup_log.warning("Failed to load .env: %s", exc)


def main() -> int:
    """Main entry point for SPYDER application with PROVEN race condition fix."""
    _startup_log = logging.getLogger("SpyderA01_Main")

    _load_runtime_dotenv(_startup_log)

    _startup_log.info("=" * 70)
    _startup_log.info("SPYDER - Autonomous Options Trading System v1.0")
    _startup_log.info("PROVEN Race Condition Fix Integration Test")
    _startup_log.info("=" * 70)
    _startup_log.info(
        "System: Logger=%s | EventManager=%s | Broker=%s | PySide6=%s",
        "OK" if has_logger else "MISSING",
        "OK" if has_event_manager else "MISSING",
        "OK" if has_broker_modules else "MISSING",
        "OK" if has_qt else "MISSING",
    )

    # Broker: Tradier API (SpyderB40_TradierClient) — legacy broker removed

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(
        description="SPYDER - Autonomous Options Trading System"
    )
    _ = parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    _ = parser.add_argument(
        "--headless", action="store_true", help="Run in headless mode"
    )
    _ = parser.add_argument("--no-gui", action="store_true", help="Disable GUI")
    args = parser.parse_args()

    # Create configuration
    config = SpyderConfig()
    config.debug_mode = args.debug
    config.headless_mode = args.headless
    config.enable_gui = not args.no_gui and not args.headless

    if args.debug:
        config.log_level = logging.DEBUG
        _startup_log.debug("Debug mode enabled")

    if args.headless:
        _startup_log.info("Headless mode enabled")

    # Create and run application
    app = SpyderApplication(config)

    # Setup signal handlers
    def signal_handler(signum: int, _frame: Any) -> None:
        _startup_log.info("Received signal %s, shutting down...", signum)
        app.shutdown()

    _ = signal.signal(signal.SIGINT, signal_handler)
    _ = signal.signal(signal.SIGTERM, signal_handler)

    # Run the application
    _startup_log.info("Starting SPYDER with PROVEN race condition fix...")
    exit_code = app.run()

    _startup_log.info("SPYDER exited with code: %s (%s)", exit_code, 'success' if exit_code == 0 else 'failure')  # noqa: E501
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
