#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovA_Core
Module: TradovA01_Main.py
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
import threading
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, TYPE_CHECKING
from zoneinfo import ZoneInfo

# Install uvloop as the asyncio event loop (2-4x faster on Linux/macOS)
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass  # Falls back to default asyncio event loop

# Add project root to path (now need to go up 3 levels: TradovA01_Main.py -> TradovA_Core -> Tradov -> project_root)  # noqa: E501
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

_A01_EASTERN_TZ = ZoneInfo("America/New_York")
_A01_PAPER_LOAD_START_ET = dt_time(9, 0)
_A01_MARKET_OPEN_ET = dt_time(9, 30)
_A01_PAPER_AUTOSTART_WARMUP_END_ET = dt_time(9, 0)


def _next_et_session_time(target_time: dt_time, now_et: datetime | None = None) -> datetime:
    """Return the next weekday occurrence of *target_time* in Eastern Time."""
    current_et = now_et or datetime.now(_A01_EASTERN_TZ)
    candidate = current_et.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )
    if current_et.weekday() < 5 and current_et.time() <= target_time:
        return candidate

    next_day = current_et + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0,
    )


def _resolve_gui_paper_autostart_delay_ms(mode: str, now_et: datetime | None = None) -> int:
    """Return the GUI autostart delay for paper launches."""
    if mode != "paper":
        return 250

    current_et = now_et or datetime.now(_A01_EASTERN_TZ)
    if current_et.weekday() < 5 and _A01_MARKET_OPEN_ET <= current_et.time() < dt_time(16, 0):
        return 250

    if current_et.weekday() < 5 and _A01_PAPER_LOAD_START_ET <= current_et.time() < _A01_MARKET_OPEN_ET:
        target = current_et.replace(
            hour=_A01_PAPER_AUTOSTART_WARMUP_END_ET.hour,
            minute=_A01_PAPER_AUTOSTART_WARMUP_END_ET.minute,
            second=0,
            microsecond=0,
        )
        return max(250, int((target - current_et).total_seconds() * 1000))

    if current_et.weekday() < 5 and current_et.time() < _A01_PAPER_LOAD_START_ET:
        target = _next_et_session_time(_A01_PAPER_AUTOSTART_WARMUP_END_ET, current_et)
        return max(250, int((target - current_et).total_seconds() * 1000))

    return 250

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
        logging.getLogger("TradovA01_Main").warning("PySide6 not available. GUI mode disabled.")

# Import Tradov modules with separated error handling
# Logger (required)
has_logger = False
setup_logging_func: Any = None
get_logger_func: Any = None

try:
    from Tradov.TradovU_Utilities.TradovU44_ShutdownCoordinator import get_shutdown_coordinator as _get_coordinator  # noqa: E501
    _HAS_COORDINATOR = True
except ImportError:
    _get_coordinator = None
    _HAS_COORDINATOR = False

try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import get_logger, TradovLogger

    def setup_logging(**_kwargs: Any) -> None:
        TradovLogger.initialize_logging()

    setup_logging_func = setup_logging
    get_logger_func = get_logger
    has_logger = True
except ImportError as e:
    logging.getLogger("TradovA01_Main").warning("Logger not available: %s", e)

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
    from Tradov.TradovA_Core.TradovA05_EventManager import EventManager, Event, get_event_manager  # noqa: F401

    has_event_manager = True
except ImportError:
    pass

# Broker modules — legacy broker connection modules removed
# Tradier API integration is handled by TradovB40_TradierClient
has_broker_modules = False
get_tradov_client = None
get_connection_manager = None

# NOTE: GUI imports (TradovG05_TradingDashboard, etc.) are intentionally deferred.
# They are loaded lazily inside start_gui() to avoid importing matplotlib/plotly/PySide6
# at module level, which would add 2+ seconds to any code that imports A01_Main.

# ==============================================================================
# CONFIGURATION
# ==============================================================================


class TradovConfig:
    """Tradov application configuration with PROVEN race condition fix"""

    def __init__(self) -> None:
        # Application settings
        self.app_name: str = "TRADOV"
        self.version: str = "1.0"
        self.debug_mode: bool = False  # PRODUCTION MODE

        # Broker connection settings (Tradier API via TradovB40_TradierClient)
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


class StartupInterrupted(RuntimeError):
    """Raised when shutdown interrupts the A01 startup path."""


if TYPE_CHECKING or has_qt:
    class _SessionSupervisorAutostartWorker(QObject):  # type: ignore[misc, valid-type]
        """Run deferred SessionSupervisor startup off the GUI thread."""

        finished = Signal(object, object)

        def __init__(self, tradov_app: "TradovApplication", supervisor: Any) -> None:
            super().__init__()
            self._tradov_app = tradov_app
            self._supervisor = supervisor

        def run(self) -> None:
            self._tradov_app._run_session_supervisor_autostart(self._supervisor)
            self.finished.emit(
                self._tradov_app._session_supervisor_autostart_result,
                self._tradov_app._session_supervisor_autostart_exception,
            )
else:
    _SessionSupervisorAutostartWorker = None


# ==============================================================================
# SIMPLE GUI FOR CONNECTION TESTING
# ==============================================================================

if TYPE_CHECKING or has_qt:
    _BaseWidget = QWidget  # type: ignore[misc, name-defined]
else:
    _BaseWidget = object


class TradovMainWindow(_BaseWidget):  # type: ignore[misc]
    """
    Simple main window for testing PROVEN race condition fix.

    This window will only appear after successful broker connection,
    proving that the race condition fix is working.
    """

    def __init__(self, tradov_app: "TradovApplication") -> None:
        super().__init__()
        self.tradov_app: TradovApplication = tradov_app
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
            f"TRADOV v{self.tradov_app.config.version} - PROVEN Race Condition Fix"
        )
        self.setGeometry(
            100,
            100,
            self.tradov_app.config.window_width,
            self.tradov_app.config.window_height,
        )

        # Create layout
        if QVBoxLayout is None:
            return
        layout = QVBoxLayout()

        # Title
        if QLabel is None:
            return
        title = QLabel("TRADOV - Autonomous Options Trading System")
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
            if self.tradov_app.client and self.tradov_app.client.is_connected():
                status = self.tradov_app.client.get_connection_status()

                # Safely get account info
                account_info: dict[str, Any] = {}
                if hasattr(self.tradov_app.client, "get_account_info"):
                    try:
                        account_info = self.tradov_app.client.get_account_info()
                    except Exception as e:
                        self.tradov_app.logger.warning(
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
- Client ID: {self.tradov_app.config.master_client_id}
- Broker: Tradier API (TradovB40_TradierClient)

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
            if hasattr(self.tradov_app, "logger"):
                self.tradov_app.logger.error("Status update error: %s", e, exc_info=True)
            else:
                logging.getLogger("TradovA01_Main").error("Status update error: %s", e)

    def test_connection_fix(self) -> None:
        """Test the PROVEN race condition fix."""
        if self.tradov_app.client:
            self.connection_info.append("\n🧪 Testing PROVEN race condition fix...")

            # Check if the test method exists
            if hasattr(self.tradov_app.client, "test_connection_with_proven_fix"):
                result = self.tradov_app.client.test_connection_with_proven_fix()

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
                if self.tradov_app.client.is_connected():
                    self.connection_info.append("✅ Basic connection test SUCCESSFUL!")
                else:
                    self.connection_info.append("❌ Basic connection test FAILED!")

    def disconnect_broker(self) -> None:
        """Disconnect from broker."""
        if self.tradov_app.client:
            self.tradov_app.client.disconnect()
            self.connection_info.append("\n🔌 Disconnected from broker")


# ==============================================================================
# MAIN TRADOV APPLICATION CLASS
# ==============================================================================


class TradovApplication:
    """
    Main TRADOV application with PROVEN race condition fix integration.

    This class manages the complete application lifecycle and demonstrates
    that the GUI will only appear after successful broker connection using
    the proven race condition fix.
    """

    def __init__(self, config: TradovConfig | None = None) -> None:
        """Initialize TRADOV application with PROVEN race condition fix."""

        # Configuration
        self.config: TradovConfig = config or TradovConfig()

        # Setup logging first
        self._setup_logging()
        self.logger: Any = get_logger_func("TradovApplication")

        # Core components
        self.event_manager: Any = None
        self.connection_manager: Any = None
        self.client: Any = None
        self.telegram_bot: Any = None
        self.session_supervisor: Any = None
        self._session_supervisor_autostart_pending: bool = False
        self._session_supervisor_autostart_mode: str | None = None
        self._session_supervisor_autostart_thread: Any = None
        self._session_supervisor_autostart_worker: Any = None
        self._session_supervisor_autostart_active: bool = False
        self._session_supervisor_autostart_result: bool | None = None
        self._session_supervisor_autostart_exception: Exception | None = None
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
        self.logger.info("TRADOV v%s - PROVEN Race Condition Fix", self.config.version)
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
        title_text = "TRADOV CAPABILITY REPORT"
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
        """Setup application logging.

        Two log destinations are configured:
        - **Internal file** (``~/.tradov/logs/tradov_YYYYMMDD.log``): DEBUG+,
          rotates at 50 MB, keeps 10 backups.  Every record goes here so that
          nothing is lost during post-session analysis.
        - **Console / GUI**: INFO+ only; noisy INFO records are further
          suppressed in the GUI panel by ``GUIMinimalFilter`` in G99.
        """
        try:
            if has_logger:
                _log_file = (
                    Path.home()
                    / ".tradov"
                    / "logs"
                    / f"tradov_{datetime.now().strftime('%Y%m%d')}.log"
                )
                TradovLogger.initialize_logging(
                    log_level=self.config.log_level,
                    log_file=_log_file,
                    file_log_level="DEBUG",
                )
            else:
                # Fallback: attach a handler to the Tradov package logger only,
                # leaving the root logger untouched.
                _tradov_root = logging.getLogger("Tradov")
                if not _tradov_root.handlers:
                    _handler = logging.StreamHandler()
                    _handler.setFormatter(
                        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                    )
                    _tradov_root.addHandler(_handler)
                _tradov_root.setLevel(self.config.log_level)

            # Reduce dashboard worker logging (unconditional — applies on both paths)
            logging.getLogger("TradovG_GUI.TradovG05_TradingDashboard").setLevel(logging.INFO)

        except Exception as e:
            logging.getLogger("TradovA01_Main").warning("Could not setup advanced logging: %s", e)
            _tradov_root = logging.getLogger("Tradov")
            if not _tradov_root.handlers:
                _tradov_root.addHandler(logging.StreamHandler())

    def _raise_if_shutdown_requested(self, phase: str) -> None:
        """Abort startup work once a shutdown request has already been received."""
        if self.shutdown_requested:
            self.logger.info(
                "Shutdown requested during %s; aborting startup path",
                phase,
            )
            raise StartupInterrupted(phase)

    def _should_defer_session_supervisor_autostart(self) -> bool:
        """Return True when SessionSupervisor startup should wait for first paint."""
        return bool(
            self.config.enable_gui
            and not self.config.headless_mode
            and has_qt
            and QTimer is not None
        )

    def _clear_injected_session_supervisor_reference(self, supervisor: Any) -> None:
        """Drop the injected dashboard supervisor reference when it matches."""
        if (
            self.main_window is not None
            and getattr(self.main_window, "_session_supervisor", None) is supervisor
        ):
            self.main_window._session_supervisor = None

    def _prepare_session_supervisor_autostart(self, mode: str) -> bool:
        """Create the SessionSupervisor and either start or defer it."""
        from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import (
            authorize_paper_session_start,
            create_session_supervisor,
        )

        self._session_supervisor_autostart_pending = False
        self._session_supervisor_autostart_mode = None
        self._session_supervisor_autostart_thread = None
        self._session_supervisor_autostart_worker = None
        self._session_supervisor_autostart_active = False
        self._session_supervisor_autostart_delegated_to_dashboard = False
        self._session_supervisor_autostart_result = None
        self._session_supervisor_autostart_exception = None
        self.session_supervisor = create_session_supervisor(mode=mode)
        if mode == "paper":
            authorize_paper_session_start(self.session_supervisor)
        self.session_supervisor._tradov_autostart_in_progress = False
        if self._should_defer_session_supervisor_autostart():
            self._session_supervisor_autostart_pending = True
            self._session_supervisor_autostart_mode = mode
            self.logger.info(
                "⏳ SessionSupervisor autostart deferred until after GUI launch (mode=%s)",
                mode,
            )
            return True

        if self.session_supervisor.start():
            self._session_supervisor_autostart_mode = None
            self.logger.info(
                "✅ SessionSupervisor autostarted from A01 (mode=%s)",
                mode,
            )
            return True

        self._session_supervisor_autostart_mode = None
        self.logger.warning(
            "SessionSupervisor autostart failed from A01 (mode=%s)",
            mode,
        )
        self.session_supervisor = None
        return False

    def _run_session_supervisor_autostart(self, supervisor: Any) -> None:
        """Run SessionSupervisor autostart in a background thread."""
        self._session_supervisor_autostart_result = None
        self._session_supervisor_autostart_exception = None
        try:
            if getattr(supervisor, "mode", "paper") == "paper":
                from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import (
                    authorize_paper_session_start,
                )

                authorize_paper_session_start(supervisor)
            self._session_supervisor_autostart_result = bool(supervisor.start())
        except Exception as exc:  # noqa: BLE001
            self._session_supervisor_autostart_exception = exc

        if self.shutdown_requested and self._session_supervisor_autostart_result:
            try:
                supervisor.stop(flatten=False)
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(
                    "SessionSupervisor background shutdown stop error: %s",
                    exc,
                    exc_info=True,
                )

    def _is_session_supervisor_autostart_thread_running(self) -> bool:
        """Return True while the deferred autostart worker is still running."""
        thread = self._session_supervisor_autostart_thread
        if thread is None:
            return False
        if hasattr(thread, "isRunning"):
            try:
                return bool(thread.isRunning())
            except RuntimeError:
                self._session_supervisor_autostart_thread = None
                self._session_supervisor_autostart_worker = None
                return False
        if hasattr(thread, "is_alive"):
            return bool(thread.is_alive())
        return False

    def _wait_for_session_supervisor_autostart_thread(self, timeout_seconds: float) -> bool:
        """Wait briefly for the deferred autostart worker to finish."""
        thread = self._session_supervisor_autostart_thread
        if thread is None:
            return True
        if hasattr(thread, "wait"):
            try:
                return bool(thread.wait(int(timeout_seconds * 1000)))
            except RuntimeError:
                self._session_supervisor_autostart_thread = None
                self._session_supervisor_autostart_worker = None
                return True
        if hasattr(thread, "join"):
            thread.join(timeout=timeout_seconds)
            return not bool(thread.is_alive())
        return True

    def _on_session_supervisor_autostart_finished(self, started: object, exc: object) -> None:
        """Capture deferred autostart completion back on the GUI thread."""
        self._session_supervisor_autostart_result = bool(started)
        self._session_supervisor_autostart_exception = (
            exc if isinstance(exc, Exception) else None
        )
        self._finalize_session_supervisor_autostart()

    def _finalize_session_supervisor_autostart(self) -> None:
        """Finalize deferred SessionSupervisor startup on the GUI thread."""
        if self._is_session_supervisor_autostart_thread_running():
            return

        if getattr(self, "_session_supervisor_autostart_delegated_to_dashboard", False):
            self._session_supervisor_autostart_thread = None
            self._session_supervisor_autostart_worker = None
            self._session_supervisor_autostart_active = False
            self._session_supervisor_autostart_mode = None
            self._session_supervisor_autostart_result = None
            self._session_supervisor_autostart_exception = None
            self._session_supervisor_autostart_delegated_to_dashboard = False
            return

        supervisor = self.session_supervisor
        if supervisor is not None:
            supervisor._tradov_autostart_in_progress = False

        mode = self._session_supervisor_autostart_mode or "paper"
        started = bool(self._session_supervisor_autostart_result)
        exc = self._session_supervisor_autostart_exception

        self._session_supervisor_autostart_thread = None
        self._session_supervisor_autostart_worker = None
        self._session_supervisor_autostart_active = False
        self._session_supervisor_autostart_mode = None
        self._session_supervisor_autostart_delegated_to_dashboard = False
        self._session_supervisor_autostart_result = None
        self._session_supervisor_autostart_exception = None

        if self.shutdown_requested:
            return

        if started:
            self.logger.info(
                "✅ SessionSupervisor autostarted from A01 (mode=%s)",
                mode,
            )
            adopt_running_ui = getattr(self.main_window, "_adopt_running_session_supervisor_ui_state", None)
            begin_loading_transition = getattr(self.main_window, "_begin_start_button_loading_transition", None)
            if callable(adopt_running_ui):
                try:
                    adopt_running_ui()
                    if mode == "paper" and callable(begin_loading_transition):
                        begin_loading_transition()
                except Exception as ui_exc:
                    self.logger.warning(
                        "SessionSupervisor autostart UI adoption failed: %s",
                        ui_exc,
                    )
            return

        if exc is not None:
            self.logger.warning(
                "SessionSupervisor autostart exception in A01: %s",
                exc,
            )
        else:
            self.logger.warning(
                "SessionSupervisor autostart failed from A01 (mode=%s)",
                mode,
            )

        if supervisor is not None:
            self._clear_injected_session_supervisor_reference(supervisor)
        if self.session_supervisor is supervisor:
            self.session_supervisor = None

    def _poll_pending_session_supervisor_autostart_completion(self) -> None:
        """Poll for completion of the deferred SessionSupervisor startup."""
        if not self._session_supervisor_autostart_active:
            return

        if self._is_session_supervisor_autostart_thread_running():
            if QTimer is not None:
                QTimer.singleShot(100, self._poll_pending_session_supervisor_autostart_completion)
            return

        self._finalize_session_supervisor_autostart()

    def _start_pending_session_supervisor_autostart(self) -> None:
        """Start a previously prepared SessionSupervisor after first paint."""
        if not self._session_supervisor_autostart_pending:
            return

        mode = self._session_supervisor_autostart_mode or "paper"
        self._session_supervisor_autostart_pending = False

        if self.shutdown_requested:
            self._session_supervisor_autostart_mode = None
            self.logger.info(
                "Shutdown requested before deferred SessionSupervisor autostart; skipping"
            )
            return

        supervisor = self.session_supervisor
        if supervisor is None:
            self._session_supervisor_autostart_mode = None
            return

        if mode == "paper":
            from Tradov.TradovR_Runtime.TradovR12_SessionSupervisor import (
                authorize_paper_session_start,
            )

            authorize_paper_session_start(supervisor)

        if mode == "paper":
            queue_paper_session_start = getattr(self.main_window, "_queue_paper_session_start", None)
            if callable(queue_paper_session_start):
                self._session_supervisor_autostart_mode = None
                try:
                    self._session_supervisor_autostart_delegated_to_dashboard = True
                    queue_paper_session_start(show_failure_dialog=False)
                    self.logger.debug(
                        "⏳ SessionSupervisor autostart handed off to dashboard loading window (mode=%s)",
                        mode,
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    self._session_supervisor_autostart_delegated_to_dashboard = False
                    self.logger.warning(
                        "SessionSupervisor delayed autostart handoff failed; falling back to background start: %s",
                        exc,
                    )

        if getattr(supervisor, "is_running", False):
            self._session_supervisor_autostart_mode = None
            self.logger.info(
                "ℹ️ SessionSupervisor already running before deferred A01 autostart callback"
            )
            return

        if self._session_supervisor_autostart_active:
            self.logger.info(
                "ℹ️ Deferred SessionSupervisor autostart already in progress (mode=%s)",
                mode,
            )
            return

        self._session_supervisor_autostart_active = True
        self._session_supervisor_autostart_result = None
        self._session_supervisor_autostart_exception = None
        supervisor._tradov_autostart_in_progress = True

        if QThread is not None and _SessionSupervisorAutostartWorker is not None:
            thread = QThread()
            worker = _SessionSupervisorAutostartWorker(self, supervisor)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_session_supervisor_autostart_finished)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(self._finalize_session_supervisor_autostart)
            thread.finished.connect(thread.deleteLater)
            self._session_supervisor_autostart_thread = thread
            self._session_supervisor_autostart_worker = worker
            thread.start()
            self.logger.info(
                "🚀 SessionSupervisor autostart running in background QThread (mode=%s)",
                mode,
            )
            return

        thread = threading.Thread(
            target=lambda: self._run_session_supervisor_autostart(supervisor),
            name="A01-session-supervisor-autostart",
            daemon=True,
        )
        self._session_supervisor_autostart_thread = thread
        thread.start()
        self.logger.info(
            "🚀 SessionSupervisor autostart running in background thread (mode=%s)",
            mode,
        )
        self._poll_pending_session_supervisor_autostart_completion()

    def _schedule_session_supervisor_autostart_after_gui_launch(self) -> None:
        """Schedule any deferred SessionSupervisor startup after the window shows."""
        if not self._session_supervisor_autostart_pending or QTimer is None:
            return

        mode = self._session_supervisor_autostart_mode or "paper"
        delay_ms = _resolve_gui_paper_autostart_delay_ms(mode)
        QTimer.singleShot(delay_ms, self._start_pending_session_supervisor_autostart)
        if delay_ms <= 250:
            self.logger.info(
                "⏳ SessionSupervisor autostart scheduled after first paint (mode=%s)",
                mode,
            )

    def _stop_loaded_metrics_orchestrators(self) -> None:
        """Stop any already-loaded S07 singleton instances without creating new ones."""
        seen: set[int] = set()
        for module_name in (
            "Tradov.TradovS_Signals.TradovS07_CustomMetricsOrchestrator",
            "TradovS_Signals.TradovS07_CustomMetricsOrchestrator",
        ):
            module = sys.modules.get(module_name)
            if module is None:
                continue

            orchestrator = getattr(module, "_orchestrator_instance", None)
            if orchestrator is None:
                continue

            orchestrator_id = id(orchestrator)
            if orchestrator_id in seen:
                continue
            seen.add(orchestrator_id)

            try:
                orchestrator.stop()
                self.logger.info("📉 Metrics orchestrator stopped from A01 cleanup")
            except Exception as e:
                self.logger.warning(
                    "Metrics orchestrator cleanup stop error: %s",
                    e,
                    exc_info=True,
                )

            try:
                module._orchestrator_instance = None
            except Exception:
                pass

    def initialize_core_systems(self) -> bool:
        """
        Initialize core systems with PROVEN race condition fix.

        The GUI will only appear if this succeeds, proving the fix works.
        """
        try:
            self.logger.info(
                "🔧 Initializing core systems with PROVEN race condition fix..."
            )
            self._raise_if_shutdown_requested("core system initialization")

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
            self._raise_if_shutdown_requested("event manager initialization")

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
                    from Tradov.TradovJ_Alerts.TradovJ05_TelegramBot import TelegramBot

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
            self._raise_if_shutdown_requested("Telegram bot initialization")

            # Optionally autostart SessionSupervisor from A01. This is useful
            # for icon-launch workflows that rely on Telegram /status and
            # /resume gates checking session_supervisor state. Autostart is
            # paper-only by policy; live must always be armed and started
            # manually by the operator.
            autostart_raw = os.environ.get(
                "TRADOV_A01_AUTOSTART_SESSION_SUPERVISOR", "0"
            ).strip().lower()
            should_autostart = autostart_raw in ("1", "true", "yes", "on")
            if should_autostart and self.config.enable_gui and not self.config.headless_mode:
                allow_gui_autostart = os.environ.get(
                    "TRADOV_A01_ALLOW_GUI_AUTOSTART", "0"
                ).strip().lower() in ("1", "true", "yes", "on")
                if not allow_gui_autostart:
                    self.logger.warning(
                        "SessionSupervisor autostart requested, but blocked for GUI launches. "
                        "Use TRADOV_A01_ALLOW_GUI_AUTOSTART=1 to re-enable deferred GUI autostart."
                    )
                    should_autostart = False
            if should_autostart:
                mode = os.environ.get("TRADOV_A01_AUTOSTART_MODE", "paper").strip().lower()
                if mode not in ("paper", "live"):
                    self.logger.warning(
                        "Invalid TRADOV_A01_AUTOSTART_MODE=%s, falling back to paper",
                        mode,
                    )
                    mode = "paper"

                if mode == "live":
                    self.logger.warning(
                        "Live autostart requested but permanently disallowed. "
                        "Falling back to paper mode."
                    )
                    mode = "paper"

                try:
                    if not self._prepare_session_supervisor_autostart(mode):
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
            self._raise_if_shutdown_requested("SessionSupervisor autostart")

            self.logger.info("✅ Core systems initialized successfully!")

            # Log which optional capabilities are available before the event loop starts
            self._log_capability_report()

            return True

        except StartupInterrupted:
            raise

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
            self._raise_if_shutdown_requested("GUI startup")

            # Create Qt application
            if QApplication is None:
                raise RuntimeError("QApplication is not available")
            existing_app = None
            if hasattr(QApplication, "instance"):
                try:
                    existing_app = QApplication.instance()
                except Exception:
                    existing_app = None

            self.gui_app = existing_app if existing_app is not None else QApplication(sys.argv)

            # CRITICAL: Set desktop file name for Wayland/GNOME integration
            # This ensures the window appears under the launcher icon
            self.gui_app.setDesktopFileName("tradov-trading-system")

            self.gui_app.setApplicationName(self.config.app_name)
            self.gui_app.setApplicationVersion(self.config.version)
            self._raise_if_shutdown_requested("Qt application initialization")

            # Create main window - lazy-load GUI modules (deferred to avoid slow startup)
            # Try real TradovG05 Trading Dashboard first
            has_trading_dashboard = False
            TradovTradingDashboard = None
            try:
                from Tradov.TradovG_GUI.TradovG05_TradingDashboard import TradovTradingDashboard  # type: ignore[assignment]
                has_trading_dashboard = True
                self.logger.info("Real Trading Dashboard (G05) loaded successfully.")
            except ImportError as e:
                self.logger.warning("Trading Dashboard not available: %s", e)

            # Lazy-load GUI log handler
            setup_gui_logging = None
            try:
                from Tradov.TradovG_GUI.TradovG99_GUILogHandler import setup_gui_logging  # type: ignore[assignment]
            except ImportError:
                pass

            # Lazy-load fallback Working Trading Dashboard
            has_working_dashboard = False
            WorkingTradovDashboard = None
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    "launch_tradov_working_dashboard",
                    project_root / "launch_tradov_working_dashboard.py"
                )
                if _spec and _spec.loader:
                    _wmod = _ilu.module_from_spec(_spec)
                    _spec.loader.exec_module(_wmod)  # type: ignore[union-attr]
                    WorkingTradovDashboard = _wmod.WorkingTradovDashboard
                    has_working_dashboard = True
                    self.logger.info("Working Trading Dashboard loaded.")
            except Exception:
                pass

            self._raise_if_shutdown_requested("GUI module loading")

            if has_trading_dashboard and TradovTradingDashboard:
                self.logger.info("🚀 Starting REAL TradovG05 Trading Dashboard...")

                try:
                    self.main_window = TradovTradingDashboard()
                except Exception as e:
                    self.logger.error("❌ Failed to create dashboard: %s", e, exc_info=True)
                    import traceback

                    self.logger.debug(traceback.format_exc())
                    raise

                self._raise_if_shutdown_requested("Trading Dashboard construction")

                # The dashboard now manages its own connection via its polling timer.
                # No client needs to be passed from the main application.
                self.logger.info(
                    "ℹ️ Dashboard will manage its own connection."
                )

                # If A01 pre-started a SessionSupervisor (TRADOV_A01_AUTOSTART_SESSION_SUPERVISOR=1),
                # inject it into the dashboard so G05 reuses it instead of creating a second
                # instance (which would fail to bind the healthz port).
                if self.session_supervisor is not None:
                    self.main_window._session_supervisor = self.session_supervisor
                    self.logger.info(
                        "✅ A01 SessionSupervisor injected into dashboard — reusing existing session"
                    )
                    if (
                        getattr(self, "_session_supervisor_autostart_pending", False)
                        and getattr(self, "_session_supervisor_autostart_mode", "paper") == "paper"
                    ):
                        current_et = datetime.now(_A01_EASTERN_TZ)
                        if _A01_PAPER_LOAD_START_ET <= current_et.time() < dt_time(16, 0):
                            set_loading_state = getattr(
                                self.main_window,
                                "_set_start_button_loading_live_data_state",
                                None,
                            )
                            if callable(set_loading_state):
                                try:
                                    set_loading_state()
                                except Exception:
                                    pass

                self._raise_if_shutdown_requested("Trading Dashboard display")
                self.main_window.show()
                self.logger.info("✅ Real Trading Dashboard launched successfully!")
                self._schedule_session_supervisor_autostart_after_gui_launch()

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
            elif has_working_dashboard and WorkingTradovDashboard:
                self.logger.info("🚀 Starting Working Trading Dashboard (fallback)...")

                try:
                    self.main_window = WorkingTradovDashboard()
                except Exception as e:
                    self.logger.error("❌ Failed to create working dashboard: %s", e, exc_info=True)
                    import traceback

                    self.logger.debug(traceback.format_exc())
                    raise

                self._raise_if_shutdown_requested("Working Dashboard display")
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
                self.main_window = TradovMainWindow(self)
                self._raise_if_shutdown_requested("fallback window display")
                self.main_window.show()

            self.logger.debug("✅ GUI started successfully")

            return True

        except StartupInterrupted:
            raise

        except Exception as e:
            self.logger.error("❌ GUI startup failed: %s", e, exc_info=True)
            import traceback

            self.logger.debug(traceback.format_exc())
            return False

    def run(self) -> int:
        """
        Run the complete TRADOV application with PROVEN race condition fix.

        Returns:
            int: Exit code (0 = success, 1 = failure)
        """
        try:
            self.logger.info("🚀 Starting TRADOV with PROVEN race condition fix...")
            self.running = True
            self._raise_if_shutdown_requested("application startup")

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
            self._raise_if_shutdown_requested("startup configuration validation")

            # Initialize core systems (includes broker connection with race condition fix)
            if not self.initialize_core_systems():
                self.logger.error("❌ Core system initialization failed")
                return 1
            self._raise_if_shutdown_requested("post-core initialization")

            # Start GUI (only appears if broker connection succeeded)
            if self.config.enable_gui and not self.config.headless_mode:
                self._raise_if_shutdown_requested("pre-GUI startup")
                if not self.start_gui():
                    self.logger.error("❌ GUI startup failed")
                    return 1
                self._raise_if_shutdown_requested("GUI event loop startup")

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

        except StartupInterrupted:
            self.logger.info("Startup interrupted by shutdown request")
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
            self.logger.info("🔄 Shutting down TRADOV...")
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

            # Close the dashboard before stopping the injected SessionSupervisor.
            # G05's closeEvent stops its Qt worker/timer threads; if we stop the
            # backend first, those GUI-owned threads can keep the process alive
            # during bounded SIGTERM-based launcher validations.
            if self.main_window and hasattr(self.main_window, "close"):
                try:
                    self.main_window.close()
                    if self.gui_app and hasattr(self.gui_app, "processEvents"):
                        self.gui_app.processEvents()
                except Exception as e:
                    self.logger.warning("Main window close error: %s", e, exc_info=True)

            if getattr(self, "_session_supervisor_autostart_pending", False):
                self._session_supervisor_autostart_pending = False
                self._session_supervisor_autostart_mode = None

            autostart_thread = getattr(self, "_session_supervisor_autostart_thread", None)
            if autostart_thread is not None:
                try:
                    finished = self._wait_for_session_supervisor_autostart_thread(1.0)
                except Exception as e:
                    self.logger.warning(
                        "SessionSupervisor autostart thread join error: %s",
                        e,
                        exc_info=True,
                    )
                    finished = False
                if not finished:
                    self.logger.warning(
                        "SessionSupervisor autostart thread still running during shutdown"
                    )
                else:
                    self._finalize_session_supervisor_autostart()

            # Stop unified session supervisor if A01 started it.
            if self.session_supervisor:
                try:
                    self.session_supervisor.stop(flatten=False)
                    self.logger.info("🧭 SessionSupervisor stopped")
                except Exception as e:
                    self.logger.warning("SessionSupervisor stop error: %s", e, exc_info=True)
                finally:
                    self.session_supervisor = None

            self._stop_loaded_metrics_orchestrators()

            # Stop the EventManager while the application is still in an
            # explicit shutdown path instead of leaving it to atexit cleanup.
            if self.event_manager:
                try:
                    self.event_manager.stop()
                    self.logger.info("🧵 EventManager stopped")
                except Exception as e:
                    self.logger.warning("EventManager stop error: %s", e, exc_info=True)
                finally:
                    self.event_manager = None

            # Stop the shared A03 ConfigManager singleton so its watchdog
            # observer threads do not outlive the bounded launcher shutdown.
            try:
                from Tradov.TradovA_Core.TradovA03_Configuration import reset_config_manager

                reset_config_manager()
                self.logger.info("⚙️ ConfigManager reset")
            except Exception as e:
                self.logger.warning("ConfigManager reset error: %s", e, exc_info=True)

            # Signal and join any remaining background workers registered with
            # the process-wide shutdown coordinator before the main thread exits.
            if _HAS_COORDINATOR and _get_coordinator is not None:
                try:
                    _get_coordinator().shutdown(timeout=1.0)
                    self.logger.info("🧹 ShutdownCoordinator drained background workers")
                except Exception as e:
                    self.logger.warning(
                        "ShutdownCoordinator drain error: %s",
                        e,
                        exc_info=True,
                    )

            # Cleanup GUI
            if self.gui_app:
                try:
                    self.gui_app.quit()
                    if hasattr(self.gui_app, "processEvents"):
                        self.gui_app.processEvents()
                except Exception as e:
                    self.logger.warning("GUI cleanup error: %s", e, exc_info=True)

            live_threads = [
                f"{thread.name}(daemon={thread.daemon})"
                for thread in threading.enumerate()
                if thread is not threading.current_thread()
            ]
            if live_threads:
                self.logger.warning(
                    "Live non-main threads remain after shutdown: %s",
                    ", ".join(live_threads),
                )

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
    """Main entry point for TRADOV application with PROVEN race condition fix."""
    _startup_log = logging.getLogger("TradovA01_Main")

    _load_runtime_dotenv(_startup_log)

    _startup_log.info("=" * 70)
    _startup_log.info("TRADOV - Autonomous Options Trading System v1.0")
    _startup_log.info("PROVEN Race Condition Fix Integration Test")
    _startup_log.info("=" * 70)
    _startup_log.info(
        "System: Logger=%s | EventManager=%s | Broker=%s | PySide6=%s",
        "OK" if has_logger else "MISSING",
        "OK" if has_event_manager else "MISSING",
        "OK" if has_broker_modules else "MISSING",
        "OK" if has_qt else "MISSING",
    )

    # Broker: Tradier API (TradovB40_TradierClient) — legacy broker removed

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(
        description="TRADOV - Autonomous Options Trading System"
    )
    _ = parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    _ = parser.add_argument(
        "--headless", action="store_true", help="Run in headless mode"
    )
    _ = parser.add_argument("--no-gui", action="store_true", help="Disable GUI")
    args = parser.parse_args()

    # Create configuration
    config = TradovConfig()
    config.debug_mode = args.debug
    config.headless_mode = args.headless
    config.enable_gui = not args.no_gui and not args.headless

    if args.debug:
        config.log_level = logging.DEBUG
        _startup_log.debug("Debug mode enabled")

    if args.headless:
        _startup_log.info("Headless mode enabled")

    # Create and run application
    app = TradovApplication(config)

    # Setup signal handlers
    def signal_handler(signum: int, _frame: Any) -> None:
        _startup_log.info("Received signal %s, shutting down...", signum)
        app.shutdown()

    _ = signal.signal(signal.SIGINT, signal_handler)
    _ = signal.signal(signal.SIGTERM, signal_handler)

    # Run the application
    _startup_log.info("Starting TRADOV with PROVEN race condition fix...")
    exit_code = app.run()

    _startup_log.info("TRADOV exited with code: %s (%s)", exit_code, 'success' if exit_code == 0 else 'failure')  # noqa: E501
    return exit_code


def _finalize_process_exit(exit_code: int) -> None:
    """Flush logs and terminate the A01 entrypoint process immediately."""
    logging.shutdown()
    os._exit(exit_code)


if __name__ == "__main__":
    _finalize_process_exit(main())
