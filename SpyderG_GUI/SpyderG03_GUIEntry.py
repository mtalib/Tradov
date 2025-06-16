#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG03_GUIEntry.py
Group: G (User Interface)
Purpose: Main GUI entry point and system integration

Description:
    This module serves as the main entry point for the Spyder GUI application.
    It initializes the trading system, creates the GUI components, and manages
    the integration between the frontend dashboard and backend trading system.

Author: Mohamed Talib
Date: 2025-06-05
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import threading
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QPixmap, QFont

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Core modules
from SpyderA_Core.SpyderA01_Main import SpyderApplication
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderA_Core.SpyderA03_Configuration import get_config_manager

# GUI modules
from SpyderG_GUI.SpyderG02_Dashboard import TradingDashboard

# Utilities
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
APP_NAME = "Spyder Trading System"
APP_VERSION = "1.0.0"
CONFIG_FILE = Path.home() / ".spyder" / "config.json"
LOG_FILE = Path.home() / ".spyder" / "logs" / "spyder_gui.log"

# ==============================================================================
# GUI BRIDGE CLASS
# ==============================================================================
class GUISystemBridge(QObject):
    """
    Bridge between GUI and trading system.
    Handles communication between frontend and backend components.
    """
    
    # Signals for GUI updates
    connection_status_changed = pyqtSignal(bool, str)
    trading_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str, str)  # severity, message
    
    def __init__(self, event_manager: EventManager):
        super().__init__()
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Core application reference
        self.spyder_app: Optional[SpyderApplication] = None
        
        # State tracking
        self.is_connected = False
        self.is_trading = False
        self.current_mode = None
        
        # Subscribe to system events
        self._subscribe_to_events()
        
    def _subscribe_to_events(self):
        """Subscribe to relevant system events"""
        # System events
        self.event_manager.subscribe(
            self._handle_system_event,
            event_type=EventType.SYSTEM,
            subscriber_id="gui_bridge_system"
        )
        
        # Connection events
        self.event_manager.subscribe(
            self._handle_connection_event,
            event_type=EventType.CONNECTION,
            subscriber_id="gui_bridge_connection"
        )
        
        # Error events
        self.event_manager.subscribe(
            self._handle_error_event,
            event_type=EventType.ERROR,
            subscriber_id="gui_bridge_error"
        )
        
    def initialize_trading_system(self, mode: str) -> bool:
        """
        Initialize the trading system for the specified mode.
        
        Args:
            mode: Trading mode (BACKTEST, PAPER, LIVE)
            
        Returns:
            bool: Success status
        """
        try:
            self.logger.info(f"Initializing trading system for {mode} mode")
            self.current_mode = mode
            
            # Create Spyder application if not exists
            if not self.spyder_app:
                self.spyder_app = SpyderApplication()
                
            # Configure for specific mode
            config = get_config_manager()
            
            if mode == "BACKTEST":
                config.set("trading.mode", "backtest")
                config.set("ib.use_gateway", False)
            elif mode == "PAPER":
                config.set("trading.mode", "paper")
                config.set("ib.port", 7497)  # TWS paper trading port
            elif mode == "LIVE":
                config.set("trading.mode", "live")
                config.set("ib.port", 7496)  # TWS live trading port
                
            # Setup the application
            if not self.spyder_app.setup():
                raise Exception("Failed to setup trading system")
                
            self.logger.info("Trading system initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading system: {e}")
            self.error_occurred.emit("critical", str(e))
            return False
            
    def connect_to_ib(self) -> bool:
        """Connect to Interactive Brokers"""
        try:
            if not self.spyder_app:
                self.error_occurred.emit("error", "Trading system not initialized")
                return False
                
            # Emit connecting status
            self.connection_status_changed.emit(False, "Connecting to IB...")
            
            # Connect through the application
            if self.spyder_app.connect_to_ib():
                self.is_connected = True
                self.connection_status_changed.emit(True, "Connected to IB")
                return True
            else:
                self.connection_status_changed.emit(False, "Failed to connect")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self.connection_status_changed.emit(False, str(e))
            return False
            
    def disconnect_from_ib(self):
        """Disconnect from Interactive Brokers"""
        try:
            if self.spyder_app:
                self.spyder_app.disconnect()
                
            self.is_connected = False
            self.connection_status_changed.emit(False, "Disconnected")
            
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
            
    def start_trading(self):
        """Start automated trading"""
        if not self.is_connected:
            self.error_occurred.emit("warning", "Not connected to IB")
            return
            
        try:
            # Send start trading event
            self.event_manager.emit(Event(
                EventType.SYSTEM,
                {
                    'type': 'trading_start',
                    'mode': self.current_mode
                }
            ))
            
            self.is_trading = True
            self.trading_status_changed.emit(True)
            
        except Exception as e:
            self.logger.error(f"Failed to start trading: {e}")
            self.error_occurred.emit("error", str(e))
            
    def stop_trading(self):
        """Stop automated trading"""
        try:
            # Send stop trading event
            self.event_manager.emit(Event(
                EventType.SYSTEM,
                {
                    'type': 'trading_stop',
                    'mode': self.current_mode
                }
            ))
            
            self.is_trading = False
            self.trading_status_changed.emit(False)
            
        except Exception as e:
            self.logger.error(f"Failed to stop trading: {e}")
            
    def emergency_stop(self):
        """Emergency stop all trading activities"""
        try:
            self.logger.critical("EMERGENCY STOP initiated")
            
            # Send emergency stop event
            self.event_manager.emit(Event(
                EventType.SYSTEM,
                {
                    'type': 'emergency_stop',
                    'mode': self.current_mode
                }
            ))
            
            # Force stop trading
            self.is_trading = False
            self.trading_status_changed.emit(False)
            
        except Exception as e:
            self.logger.error(f"Emergency stop error: {e}")
            
    def _handle_system_event(self, event: Event):
        """Handle system events"""
        event_type = event.data.get('type')
        
        if event_type == 'trading_started':
            self.is_trading = True
            self.trading_status_changed.emit(True)
        elif event_type == 'trading_stopped':
            self.is_trading = False
            self.trading_status_changed.emit(False)
            
    def _handle_connection_event(self, event: Event):
        """Handle connection events"""
        status = event.data.get('status')
        message = event.data.get('message', '')
        
        if status == 'connected':
            self.is_connected = True
            self.connection_status_changed.emit(True, message)
        elif status == 'disconnected':
            self.is_connected = False
            self.connection_status_changed.emit(False, message)
            
    def _handle_error_event(self, event: Event):
        """Handle error events"""
        severity = event.data.get('severity', 'error')
        message = event.data.get('message', 'Unknown error')
        self.error_occurred.emit(severity, message)

# ==============================================================================
# SPLASH SCREEN
# ==============================================================================
class SpyderSplashScreen(QSplashScreen):
    """Custom splash screen for application startup"""
    
    def __init__(self):
        super().__init__()
        
        # Create splash pixmap (you can replace with actual logo)
        pixmap = QPixmap(400, 300)
        pixmap.fill(Qt.darkGray)
        self.setPixmap(pixmap)
        
        # Set text properties
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        
        # Add text
        font = QFont("Arial", 16, QFont.Bold)
        self.setFont(font)
        
        self.showMessage(
            "SPYDER Trading System\nAutomated SPY Options Trading",
            Qt.AlignCenter | Qt.AlignBottom,
            Qt.white
        )
        
    def update_message(self, message: str):
        """Update splash screen message"""
        self.showMessage(
            f"SPYDER Trading System\n{message}",
            Qt.AlignCenter | Qt.AlignBottom,
            Qt.white
        )

# ==============================================================================
# MAIN APPLICATION CLASS
# ==============================================================================
class SpyderGUIApplication:
    """Main GUI application controller"""
    
    def __init__(self):
        self.logger = SpyderLogger.get_logger(__name__)
        self.app: Optional[QApplication] = None
        self.splash: Optional[SpyderSplashScreen] = None
        self.dashboard: Optional[TradingDashboard] = None
        self.bridge: Optional[GUISystemBridge] = None
        self.event_manager: Optional[EventManager] = None
        
    def run(self, args):
        """Run the GUI application"""
        try:
            # Create Qt application
            self.app = QApplication(sys.argv)
            self.app.setApplicationName(APP_NAME)
            self.app.setApplicationDisplayName(APP_NAME)
            self.app.setStyle('Fusion')  # Modern look
            
            # Show splash screen
            self.splash = SpyderSplashScreen()
            self.splash.show()
            self.app.processEvents()
            
            # Initialize components
            self.splash.update_message("Initializing components...")
            self._initialize_components()
            
            # Create main window
            self.splash.update_message("Creating interface...")
            self._create_main_window()
            
            # Setup connections
            self.splash.update_message("Setting up connections...")
            self._setup_connections()
            
            # Hide splash and show main window
            QTimer.singleShot(1000, self._show_main_window)
            
            # Start application
            return self.app.exec_()
            
        except Exception as e:
            self.logger.critical(f"Application startup failed: {e}")
            if self.app:
                QMessageBox.critical(None, "Startup Error", str(e))
            return 1
            
    def _initialize_components(self):
        """Initialize application components"""
        # Create event manager
        self.event_manager = EventManager()
        
        # Create GUI-system bridge
        self.bridge = GUISystemBridge(self.event_manager)
        
        # Setup logging
        self._setup_logging()
        
    def _create_main_window(self):
        """Create the main dashboard window"""
        self.dashboard = TradingDashboard(self.event_manager)
        
        # Connect mode change to bridge
        self.dashboard.mode_changed.connect(self._handle_mode_change)
        
    def _setup_connections(self):
        """Setup signal/slot connections"""
        # Bridge to GUI connections
        self.bridge.connection_status_changed.connect(self._update_connection_status)
        self.bridge.trading_status_changed.connect(self._update_trading_status)
        self.bridge.error_occurred.connect(self._show_error)
        
        # Override dashboard methods to use bridge
        self._override_dashboard_methods()
        
    def _override_dashboard_methods(self):
        """Override dashboard methods to integrate with bridge"""
        # Store original methods
        self.dashboard._original_start_trading = self.dashboard.start_trading
        self.dashboard._original_stop_trading = self.dashboard.stop_trading
        self.dashboard._original_emergency_stop = self.dashboard.emergency_stop
        
        # Override with bridge methods
        self.dashboard.start_trading = self._start_trading_with_bridge
        self.dashboard.stop_trading = self._stop_trading_with_bridge
        self.dashboard.emergency_stop = self._emergency_stop_with_bridge
        
    def _show_main_window(self):
        """Hide splash and show main window"""
        if self.splash:
            self.splash.hide()
            self.splash = None
            
        if self.dashboard:
            self.dashboard.show()
            
    def _handle_mode_change(self, mode: str):
        """Handle trading mode change"""
        self.logger.info(f"Trading mode changed to: {mode}")
        
        # Initialize trading system for new mode
        if self.bridge:
            self.bridge.initialize_trading_system(mode)
            
            # Auto-connect for paper/live modes
            if mode in ["PAPER", "LIVE"]:
                QTimer.singleShot(500, lambda: self.bridge.connect_to_ib())
                
    def _start_trading_with_bridge(self):
        """Start trading through bridge"""
        if self.bridge:
            if not self.bridge.is_connected:
                # Try to connect first
                if self.bridge.connect_to_ib():
                    QTimer.singleShot(1000, self.bridge.start_trading)
            else:
                self.bridge.start_trading()
                
        # Call original method for UI updates
        self.dashboard._original_start_trading()
        
    def _stop_trading_with_bridge(self):
        """Stop trading through bridge"""
        if self.bridge:
            self.bridge.stop_trading()
            
        # Call original method for UI updates
        self.dashboard._original_stop_trading()
        
    def _emergency_stop_with_bridge(self):
        """Emergency stop through bridge"""
        if self.bridge:
            self.bridge.emergency_stop()
            
        # Call original method for UI updates
        self.dashboard._original_emergency_stop()
        
    def _update_connection_status(self, connected: bool, message: str):
        """Update connection status in GUI"""
        if self.dashboard:
            # Update status bar or connection indicator
            self.dashboard.status_bar.showMessage(f"IB: {message}")
            
    def _update_trading_status(self, trading: bool):
        """Update trading status in GUI"""
        if self.dashboard:
            status = "Active" if trading else "Inactive"
            self.dashboard.status_bar.showMessage(f"Trading: {status}")
            
    def _show_error(self, severity: str, message: str):
        """Show error message to user"""
        if severity == "critical":
            QMessageBox.critical(self.dashboard, "Critical Error", message)
        elif severity == "error":
            QMessageBox.warning(self.dashboard, "Error", message)
        else:
            if self.dashboard:
                self.dashboard.log_message(f"{severity.upper()}: {message}")
                
    def _setup_logging(self):
        """Setup application logging"""
        # Ensure log directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler()
            ]
        )

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for Spyder GUI application"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Spyder Trading System GUI')
    parser.add_argument(
        '--mode',
        choices=['backtest', 'paper', 'live'],
        default='paper',
        help='Initial trading mode'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=str(CONFIG_FILE),
        help='Configuration file path'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run application
    app = SpyderGUIApplication()
    return app.run(args)

if __name__ == '__main__':
    sys.exit(main())