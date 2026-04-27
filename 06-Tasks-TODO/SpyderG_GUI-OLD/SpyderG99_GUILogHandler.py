#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG99_GUILogHandler.py
Purpose: SPYDER - GUI Log Handler

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - GUI Log Handler

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QObject, Signal, Qt

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
                     exclude_modules: list | None = None) -> GUILogHandler:
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
    """
    # Create handler
    if include_modules or exclude_modules:
        handler = FilteredGUILogHandler(dashboard, include_modules, exclude_modules)
    else:
        handler = GUILogHandler(dashboard)

    # Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler.setLevel(level)

    # Set formatter
    formatter = logging.Formatter('%(name)s - %(message)s')
    handler.setFormatter(formatter)

    # Add to root logger
    logging.getLogger().addHandler(handler)

    return handler


__all__ = ['GUILogHandler', 'FilteredGUILogHandler', 'setup_gui_logging']
