#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG99_GUILogHandler.py
Purpose: TRADOV - GUI Log Handler

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - GUI Log Handler

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import re

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Allowlist: logger name prefixes whose INFO-level records are shown in the
# GUI log.  WARNING / ERROR / CRITICAL from *any* logger always pass through.
# Add a prefix here when a new series needs its milestones surfaced.
# ---------------------------------------------------------------------------
_GUI_INFO_ALLOWLIST: tuple[str, ...] = (
    "TradovA01",       # Application lifecycle (startup, shutdown)
    "TradovB40",       # TradierClient — connection events and fills
    "TradovD31",       # StrategyOrchestrator — strategy lifecycle
    "TradovE",         # Risk series — limit changes, halt events
    "TradovJ05",       # Telegram bot — trade executed / closed headlines
    "TradovG18",       # MarketDataWorker — connection status
    "TradovR_Runtime", # Runtime supervisor events
    "TradovR04",       # FillReconciler — confirmed fills
    "TradovR12",       # SessionSupervisor / paper start gate
    "TradovS07",       # Market conditions / regime transitions
)

# Human-readable labels shown in the ALLOWLIST dialog, keyed by prefix.
_GUI_INFO_ALLOWLIST_LABELS: dict[str, str] = {
    "TradovA01":       "Application lifecycle  (startup / shutdown)",
    "TradovB40":       "Tradier — connection events & fills",
    "TradovD31":       "Strategy Orchestrator  (add / pause / remove)",
    "TradovE":         "Risk series  (limit changes, halt events)",
    "TradovJ05":       "Telegram bot  (executed / closed headlines)",
    "TradovG18":       "Market data worker  (connection status)",
    "TradovR_Runtime": "Runtime supervisor events",
    "TradovR04":       "Fill Reconciler  (confirmed fills)",
    "TradovR12":       "Session Supervisor  (paper start gate)",
    "TradovS07":       "Market conditions  (regime transitions)",
}

# Tight allowlist used in MINIMAL mode — only the key trade-lifecycle headlines.
_GUI_MINIMAL_ALLOWLIST: tuple[str, ...] = (
    "TradovD31",  # Strategy Executed / Hunting / Supervising
    "TradovJ05",  # Trade executed / closed headlines
    "TradovR12",  # Session started
)


class GUIMinimalFilter(logging.Filter):
    """Reduce dashboard log noise while keeping all actionable records.

    Pass-through rules (evaluated in order):
    1. ``WARNING`` and above from **any** logger — always shown.
    2. ``INFO`` from loggers whose name starts with a prefix in *allowlist*
       — key operational milestones (session events, fills, regime changes).
    3. Everything else — suppressed from the GUI log but still written to
       the internal rotating file log.

    The allowlist can be customised at startup via
    ``setup_gui_logging(info_allowlist=...)``.  The module-level
    ``_GUI_INFO_ALLOWLIST`` tuple is the default.
    """

    def __init__(self, allowlist: tuple[str, ...] = _GUI_INFO_ALLOWLIST) -> None:
        super().__init__()
        self._allowlist = allowlist

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if record.levelno >= logging.WARNING:
            return True
        return any(record.name.startswith(prefix) for prefix in self._allowlist)


class GUILogHandler(QObject, logging.Handler):
    """
    Custom logging handler that sends log messages to GUI dashboard.

    Uses Qt signals for thread-safe communication between logging thread
    and GUI thread. Routes messages to appropriate log widgets based on
    log name and level.

    Attributes:
        log_signal: Qt signal for emitting log messages to GUI thread
        dashboard: Reference to TradingDashboard instance
        last_messages: Set of recent messages to prevent duplicates
        max_cache_size: Maximum number of messages to cache for duplicate detection
    """

    # Signal: (level, message, logger_name)
    log_signal = Signal(str, str, str)

    # Keywords that route to automation log instead of system log
    AUTOMATION_KEYWORDS = {
        'automation', 'strategy', 'signal', 'trade', 'order',
        'execution', 'position', 'risk', 'alert'
    }

    _EVENT_MANAGER_HANDLER_CHURN = re.compile(
        r"^Handler\s+.+\s+(subscribed to|unsubscribed)\s+.+$"
    )

    def __init__(self, dashboard=None):
        """
        Initialize GUI log handler.

        Args:
            dashboard: TradingDashboard instance (optional, can be set later)
        """
        QObject.__init__(self)
        logging.Handler.__init__(self)

        self.dashboard = dashboard
        self.last_messages: set[str] = set()
        self.max_cache_size = 50

        # Connect signal to slot
        self.log_signal.connect(self._handle_log_message, Qt.ConnectionType.QueuedConnection)

        # Set default formatter
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)

        # Suppress noisy INFO records; WARNING+ always passes through.
        self.addFilter(GUIMinimalFilter())

    def set_allowlist(self, active_prefixes: tuple[str, ...]) -> None:
        """Replace the active INFO allowlist on the attached GUIMinimalFilter.

        Called from the dashboard whenever the user confirms a new selection
        in the ALLOWLIST dialog.  Safe to call from the GUI thread.
        """
        self.filters = [f for f in self.filters if not isinstance(f, GUIMinimalFilter)]
        self.addFilter(GUIMinimalFilter(active_prefixes))

    def set_dashboard(self, dashboard):
        """
        Set or update the dashboard reference.

        Args:
            dashboard: TradingDashboard instance
        """
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record to the GUI.

        This method is called automatically by Python's logging system.
        It emits a Qt signal that will be handled in the GUI thread.

        Args:
            record: LogRecord instance containing log information
        """
        try:
            if self._should_suppress_record(record):
                return

            # Format the message
            msg = self.format(record)
            level = record.levelname
            logger_name = record.name

            # Create a message key for duplicate detection
            message_key = f"{level}:{logger_name}:{record.getMessage()}"

            # Skip duplicate messages (within recent history)
            if message_key in self.last_messages:
                return

            # Add to cache and trim if needed
            self.last_messages.add(message_key)
            if len(self.last_messages) > self.max_cache_size:
                # Remove oldest messages (convert to list, remove first half, convert back)
                messages_list = list(self.last_messages)
                self.last_messages = set(messages_list[self.max_cache_size // 2:])

            # Emit signal to GUI thread
            self.log_signal.emit(level, msg, logger_name)

        except Exception:
            # Don't let logging errors crash the application
            # Use standard error handler
            self.handleError(record)

    def _should_suppress_record(self, record: logging.LogRecord) -> bool:
        """Return True for low-value repetitive records that should not hit GUI logs."""
        logger_name = (record.name or "").strip()
        message = (record.getMessage() or "").strip()

        # News has its own Breaking News panel. Feed fetch failures from public
        # RSS providers are noisy and not actionable in the operator SYSTEM LOG.
        if logger_name.endswith("TradovC09_NewsManager"):
            if message.startswith("Error fetching from ") or message.startswith("BREAKING NEWS:"):
                return True

        # Never suppress other warnings/errors/criticals.
        if record.levelno >= logging.WARNING:
            return False

        # EventManager handler subscribe/unsubscribe churn can flood startup logs.
        if logger_name.endswith("TradovA05_EventManager"):
            if self._EVENT_MANAGER_HANDLER_CHURN.match(message):
                return True

        return False

    def _handle_log_message(self, level: str, message: str, logger_name: str):
        """
        Handle log message in GUI thread (connected to log_signal).

        All Python logger messages go to the system log only.
        The AUTONOMOUS AI ACTIVITY panel is populated exclusively via
        direct add_automation_log() calls so only real trade-related
        events appear there — never infrastructure/scheduling noise.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Formatted log message
            logger_name: Name of the logger that emitted the message
        """
        if not self.dashboard:
            return

        try:
            formatted_message = self._format_message_for_gui(level, message)
            self.dashboard.add_system_log(formatted_message)

        except Exception as e:
            # Fail silently to prevent infinite logging loops
            logging.info("Error in GUI log handler: %s", e)

    def _is_automation_log(self, logger_name: str, message: str) -> bool:
        """
        Determine if log should go to automation log or system log.

        Args:
            logger_name: Name of the logger
            message: Log message

        Returns:
            True if should route to automation log, False for system log
        """
        # Check logger name for automation keywords
        logger_lower = logger_name.lower()
        message_lower = message.lower()

        for keyword in self.AUTOMATION_KEYWORDS:
            if keyword in logger_lower or keyword in message_lower:
                return True

        return False

    def _format_message_for_gui(self, level: str, message: str) -> str:
        """
        Format message with color coding for GUI display.

        Args:
            level: Log level
            message: Log message

        Returns:
            Formatted message (plain text, widget handles styling)
        """
        # Add level indicator prefix
        level_prefix = self._get_level_prefix(level)
        return f"{level_prefix} {message}"

    def _get_level_prefix(self, level: str) -> str:
        """
        Get prefix icon/indicator for log level.

        Args:
            level: Log level

        Returns:
            Prefix string
        """
        prefixes = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🔥'
        }
        return prefixes.get(level, '•')


class FilteredGUILogHandler(GUILogHandler):
    """
    GUI log handler with additional filtering capabilities.

    Extends GUILogHandler to add module-specific filtering,
    allowing fine-grained control over what appears in the GUI.
    """

    def __init__(self, dashboard=None, include_modules: list | None = None,
                 exclude_modules: list | None = None):
        """
        Initialize filtered GUI log handler.

        Args:
            dashboard: TradingDashboard instance
            include_modules: List of module names to include (None = all)
            exclude_modules: List of module names to exclude (None = none)
        """
        super().__init__(dashboard)
        self.include_modules = set(include_modules) if include_modules else None
        self.exclude_modules = set(exclude_modules) if exclude_modules else set()

    def emit(self, record: logging.LogRecord):
        """
        Emit with filtering based on module names.

        Args:
            record: LogRecord instance
        """
        # Check if module should be filtered out
        if self.include_modules and record.name not in self.include_modules:
            return

        if record.name in self.exclude_modules:
            return

        # Pass to parent emit
        super().emit(record)


def setup_gui_logging(dashboard, log_level: str = "INFO",
                     include_modules: list | None = None,
                     exclude_modules: list | None = None,
                     info_allowlist: tuple[str, ...] | None = None) -> GUILogHandler:
    """
    Convenience function to set up GUI logging.

    Args:
        dashboard: TradingDashboard instance
        log_level: Minimum log level to display in GUI (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        include_modules: Optional list of modules to include
        exclude_modules: Optional list of modules to exclude

    Returns:
        Configured GUILogHandler instance

    Example:
        >>> handler = setup_gui_logging(dashboard, log_level="INFO")
        >>> # Now all INFO and above logs will appear in dashboard

    Additional parameters
    ---------------------
    info_allowlist:
        Override the default set of logger-name prefixes whose INFO records
        are allowed through to the dashboard.  ``None`` keeps the module
        default (``_GUI_INFO_ALLOWLIST``).
    """
    # Create handler
    if include_modules or exclude_modules:
        handler = FilteredGUILogHandler(dashboard, include_modules, exclude_modules)
    else:
        handler = GUILogHandler(dashboard)

    # Replace the default GUIMinimalFilter if a custom allowlist was supplied.
    if info_allowlist is not None:
        handler.filters = [f for f in handler.filters if not isinstance(f, GUIMinimalFilter)]
        handler.addFilter(GUIMinimalFilter(info_allowlist))

    # Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler.setLevel(level)

    # Set formatter
    formatter = logging.Formatter('%(name)s - %(message)s')
    handler.setFormatter(formatter)

    # Add to root logger
    logging.getLogger().addHandler(handler)

    return handler


class AllowlistDialog(QDialog):
    """Modal dialog that lets the user toggle individual INFO-level prefixes.

    The dialog is driven entirely by ``_GUI_INFO_ALLOWLIST`` and
    ``_GUI_INFO_ALLOWLIST_LABELS`` so it stays in sync with the code
    automatically when new entries are added to those module-level constants.

    Usage::

        dlg = AllowlistDialog(parent=dashboard, active=current_active_tuple)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            handler.set_allowlist(dlg.selected_prefixes())
    """

    _DIALOG_STYLE = """
        QDialog {
            background-color: #1a1a1a;
        }
        QLabel#title {
            color: #e0e0e0;
            font-size: 13px;
            letter-spacing: 1px;
            font-weight: 600;
        }
        QLabel#subtitle {
            color: #909090;
            font-size: 11px;
        }
        QCheckBox {
            color: #d0d0d0;
            font-size: 12px;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 14px;
            height: 14px;
            border: 1px solid #555;
            border-radius: 2px;
            background-color: #2a2a2a;
        }
        QCheckBox::indicator:checked {
            background-color: #1E88E5;
            border-color: #1E88E5;
        }
        QCheckBox::indicator:hover {
            border-color: #1E88E5;
        }
        QDialogButtonBox QPushButton {
            background-color: #2a2a2a;
            color: #d0d0d0;
            border: 1px solid #444;
            border-radius: 3px;
            padding: 4px 16px;
            font-size: 12px;
            font-weight: 600;
            min-width: 72px;
        }
        QDialogButtonBox QPushButton:hover {
            background-color: #1E88E5;
            color: white;
            border-color: #1E88E5;
        }
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        active: tuple[str, ...] = _GUI_INFO_ALLOWLIST,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Log — INFO Allowlist")
        self.setMinimumWidth(420)
        self.setStyleSheet(self._DIALOG_STYLE)
        self._checkboxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 14)

        title = QLabel("INFO ALLOWLIST")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Checked modules show INFO messages in the dashboard log.\n"
            "WARNING / ERROR / CRITICAL always appear regardless."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Scrollable checkbox area (future-proof for a longer list)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        check_layout = QVBoxLayout(container)
        check_layout.setSpacing(8)
        check_layout.setContentsMargins(4, 4, 4, 4)

        active_set = set(active)
        for prefix in _GUI_INFO_ALLOWLIST:
            label = _GUI_INFO_ALLOWLIST_LABELS.get(prefix, prefix)
            cb = QCheckBox(label)
            cb.setChecked(prefix in active_set)
            self._checkboxes[prefix] = cb
            check_layout.addWidget(cb)

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_prefixes(self) -> tuple[str, ...]:
        """Return the prefixes whose checkboxes are currently checked."""
        return tuple(
            prefix for prefix, cb in self._checkboxes.items() if cb.isChecked()
        )


__all__ = ['GUILogHandler', 'FilteredGUILogHandler', 'GUIMinimalFilter',
           'AllowlistDialog', 'setup_gui_logging', '_GUI_INFO_ALLOWLIST',
           '_GUI_INFO_ALLOWLIST_LABELS']
