#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG00_ApplicationManager.py
Purpose: Qt Application lifecycle management and initialization
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-14 Time: 00:45:00

Module Description:
    This module manages Qt application initialization and lifecycle for the Spyder
    trading system GUI components. It ensures proper QApplication creation before
    any widgets are instantiated, handles headless operation modes, and provides
    centralized application management for all GUI components. Essential for
    preventing Qt widget creation errors and managing GUI resources.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from typing import Any
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtWidgets import QApplication, QWidget
    from PySide6.QtCore import QTimer, QObject, Signal
    from PySide6.QtGui import QGuiApplication
    PYSIDE6_AVAILABLE = True
except ImportError:
    try:
        from PySide6.QtWidgets import QApplication, QWidget
        from PySide6.QtCore import QTimer, QObject, Signal as Signal
        from PySide6.QtGui import QGuiApplication
        PYSIDE6_AVAILABLE = False
    except ImportError:
        QApplication = None
        QWidget = None
        QTimer = None
        QObject = None
        Signal = None
        QGuiApplication = None
        PYSIDE6_AVAILABLE = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
APP_NAME = "Spyder Trading System"
APP_VERSION = "1.0"
APP_ORGANIZATION = "Spyder Trading"

# ==============================================================================
# ENUMS
# ==============================================================================
class DisplayMode(Enum):
    """Display mode enumeration"""
    GUI = "gui"
    HEADLESS = "headless"
    OFFSCREEN = "offscreen"

class AppState(Enum):
    """Application state enumeration"""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    SHUTDOWN = "shutdown"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AppConfig:
    """Application configuration"""
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    organization: str = APP_ORGANIZATION
    display_mode: DisplayMode = DisplayMode.GUI
    enable_high_dpi: bool = True
    style_sheet: str | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ApplicationManager(QObject):
    """
    Qt Application lifecycle manager.

    This class manages the Qt application lifecycle for Spyder GUI components.
    It handles proper QApplication initialization, display mode management,
    and provides centralized control over GUI resources. Prevents common
    Qt initialization errors and enables headless operation when needed.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        app: Qt application instance
        state: Current application state
        config: Application configuration
    """

    # Signals
    app_initialized = Signal()
    app_shutdown = Signal()

    def __init__(self, config: AppConfig | None = None):
        """Initialize the application manager."""
        # Initialize QObject only if Qt is available
        if QObject is not None:
            super().__init__()

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or AppConfig()
        self.app: QApplication | None = None
        self.state = AppState.NOT_INITIALIZED
        self._widgets = []

        self.logger.info("ApplicationManager initialized for %s mode", self.config.display_mode.value)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize_application(self) -> bool:
        """
        Initialize Qt application.

        Returns:
            bool: True if initialization successful
        """
        if self.state != AppState.NOT_INITIALIZED:
            self.logger.warning("Application already in state: %s", self.state)
            return self.app is not None

        self.state = AppState.INITIALIZING

        try:
            # Check if Qt is available
            if QApplication is None:
                self.logger.error("Qt libraries not available")
                self.state = AppState.NOT_INITIALIZED
                return False

            # Configure display mode
            self._configure_display_mode()

            # Check if QApplication already exists
            existing_app = QApplication.instance()
            if existing_app is not None:
                self.app = existing_app
                self.logger.info("Using existing QApplication instance")
            else:
                # Create new QApplication
                self.app = QApplication(sys.argv)
                self._configure_application()
                self.logger.info("Created new QApplication instance")

            self.state = AppState.RUNNING

            # Emit signal if QObject is available
            if hasattr(self, 'app_initialized'):
                self.app_initialized.emit()

            self.logger.info("Qt application initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to initialize Qt application: %s", e)
            self.error_handler.handle_error(e, {"method": "initialize_application"})
            self.state = AppState.NOT_INITIALIZED
            return False

    def create_widget(self, widget_class, *args, **kwargs):
        """
        Create a widget with proper application initialization.

        Args:
            widget_class: Widget class to instantiate
            *args: Positional arguments for widget
            **kwargs: Keyword arguments for widget

        Returns:
            Widget instance or None if creation fails
        """
        try:
            # Ensure application is initialized
            if not self.ensure_application():
                return None

            # Create widget
            widget = widget_class(*args, **kwargs)
            self._widgets.append(widget)

            self.logger.debug("Created widget: %s", widget_class.__name__)
            return widget

        except Exception as e:
            self.logger.error("Failed to create widget %s: %s", widget_class.__name__, e)
            self.error_handler.handle_error(e, {"widget_class": widget_class.__name__})
            return None

    def ensure_application(self) -> bool:
        """
        Ensure Qt application is initialized.

        Returns:
            bool: True if application is ready
        """
        if self.state == AppState.RUNNING and self.app is not None:
            return True

        if self.state == AppState.NOT_INITIALIZED:
            return self.initialize_application()

        return False

    def run_application(self) -> int:
        """
        Run the Qt application event loop.

        Returns:
            int: Application exit code
        """
        if not self.ensure_application():
            self.logger.error("Cannot run application - initialization failed")
            return 1

        try:
            self.logger.info("Starting Qt application event loop")
            exit_code = self.app.exec()
            self.logger.info("Qt application exited with code: %s", exit_code)
            return exit_code

        except Exception as e:
            self.logger.error("Application event loop error: %s", e)
            self.error_handler.handle_error(e, {"method": "run_application"})
            return 1
        finally:
            self.shutdown_application()

    def shutdown_application(self) -> None:
        """Shutdown the Qt application."""
        if self.state == AppState.SHUTDOWN:
            return

        self.state = AppState.SHUTTING_DOWN

        try:
            # Close all widgets
            for widget in self._widgets:
                try:
                    if hasattr(widget, 'close'):
                        widget.close()
                except Exception as e:
                    # Log widget closure failure but continue cleanup
                    self.logger.warning("Failed to close widget %s: %s", widget.__class__.__name__, e)

            self._widgets.clear()

            # Emit shutdown signal
            if hasattr(self, 'app_shutdown'):
                self.app_shutdown.emit()

            # Process pending events
            if self.app is not None:
                self.app.processEvents()

            self.state = AppState.SHUTDOWN
            self.logger.info("Application shutdown completed")

        except Exception as e:
            self.logger.error("Error during application shutdown: %s", e)

    def is_headless(self) -> bool:
        """
        Check if running in headless mode.

        Returns:
            bool: True if headless
        """
        return self.config.display_mode in [DisplayMode.HEADLESS, DisplayMode.OFFSCREEN]

    def get_application_info(self) -> dict[str, Any]:
        """
        Get application information.

        Returns:
            Dict with application details
        """
        return {
            "name": self.config.app_name,
            "version": self.config.app_version,
            "organization": self.config.organization,
            "display_mode": self.config.display_mode.value,
            "state": self.state.value,
            "qt_available": QApplication is not None,
            "pyside6_available": PYSIDE6_AVAILABLE,
            "widget_count": len(self._widgets),
            "headless": self.is_headless()
        }

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _configure_display_mode(self) -> None:
        """Configure display mode settings."""
        if self.config.display_mode == DisplayMode.HEADLESS:
            os.environ['QT_QPA_PLATFORM'] = 'minimal'
        elif self.config.display_mode == DisplayMode.OFFSCREEN:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        else:
            # Force the native Wayland backend when running under a Wayland compositor.
            # Without this Qt falls back to XWayland which causes rendering glitches and
            # clipboard issues on Ubuntu 25+ / GNOME Wayland.
            # Only set if the caller has not already overridden QT_QPA_PLATFORM.
            if "QT_QPA_PLATFORM" not in os.environ and os.environ.get("WAYLAND_DISPLAY"):
                os.environ["QT_QPA_PLATFORM"] = "wayland"

        # Enable high DPI support
        if self.config.enable_high_dpi:
            os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
            os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

    def _configure_application(self) -> None:
        """Configure the QApplication instance."""
        if self.app is None:
            return

        # Set application properties
        self.app.setApplicationName(self.config.app_name)
        self.app.setApplicationVersion(self.config.app_version)
        self.app.setOrganizationName(self.config.organization)

        # Apply style sheet if provided
        if self.config.style_sheet:
            self.app.setStyleSheet(self.config.style_sheet)

        # Set application attributes
        if hasattr(self.app, 'setAttribute'):
            # Enable high DPI scaling
            if self.config.enable_high_dpi:
                try:
                    from PySide6.QtCore import Qt
                    self.app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
                    self.app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
                except (ImportError, AttributeError) as e:
                    # High DPI settings not available or not supported
                    self.logger.debug("High DPI scaling not available: %s", e)

# ==============================================================================
# SINGLETON PATTERN
# ==============================================================================
_global_app_manager: ApplicationManager | None = None

def get_application_manager(config: AppConfig | None = None) -> ApplicationManager:
    """
    Get global application manager instance.

    Args:
        config: Application configuration (only used on first call)

    Returns:
        ApplicationManager instance
    """
    global _global_app_manager

    if _global_app_manager is None:
        _global_app_manager = ApplicationManager(config)

    return _global_app_manager

def ensure_qt_application(display_mode: DisplayMode = DisplayMode.GUI) -> bool:
    """
    Ensure Qt application is initialized with specified display mode.

    Args:
        display_mode: Display mode to use

    Returns:
        bool: True if application is ready
    """
    config = AppConfig(display_mode=display_mode)
    app_manager = get_application_manager(config)
    return app_manager.ensure_application()

def create_safe_widget(widget_class, *args, **kwargs):
    """
    Create a widget safely with proper Qt application initialization.

    Args:
        widget_class: Widget class to create
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Widget instance or None
    """
    app_manager = get_application_manager()
    return app_manager.create_widget(widget_class, *args, **kwargs)

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def init_gui_application() -> bool:
    """Initialize GUI application with display."""
    return ensure_qt_application(DisplayMode.GUI)

def init_headless_application() -> bool:
    """Initialize headless application."""
    return ensure_qt_application(DisplayMode.HEADLESS)

def init_offscreen_application() -> bool:
    """Initialize offscreen application."""
    return ensure_qt_application(DisplayMode.OFFSCREEN)

def is_qt_available() -> bool:
    """Check if Qt libraries are available."""
    return QApplication is not None

def get_app_info() -> dict[str, Any]:
    """Get application information."""
    if _global_app_manager is not None:
        return _global_app_manager.get_application_info()
    return {"qt_available": is_qt_available(), "initialized": False}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    # Test application manager
    app_manager = get_application_manager()

    qt_available = is_qt_available()

    if qt_available:
        success = app_manager.initialize_application()

        info = app_manager.get_application_info()
        for _key, _value in info.items():
            pass

        if QWidget is not None:
            widget = app_manager.create_widget(QWidget)
            if widget:
                widget.setWindowTitle("Test Widget")

        app_manager.shutdown_application()

