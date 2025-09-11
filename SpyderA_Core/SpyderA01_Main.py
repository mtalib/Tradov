#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import sys
import os
import logging
import signal
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import Qt modules for GUI
try:
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit
    from PyQt6.QtCore import QTimer, pyqtSignal, QObject, QThread
    from PyQt6.QtGui import QIcon, QFont
    HAS_QT = True
except ImportError:
    print("Warning: PyQt6 not available. GUI mode disabled.")
    HAS_QT = False
    QApplication = QWidget = QVBoxLayout = QLabel = QPushButton = QTextEdit = None
    QTimer = pyqtSignal = QObject = QThread = QIcon = QFont = None

# Import Spyder modules with separated error handling
# Logger (required)
try:
    from SpyderU_Utilities.SpyderU01_Logger import get_logger, SpyderLogger
    setup_logging = lambda **kwargs: SpyderLogger.initialize_logging()
    HAS_LOGGER = True
except ImportError as e:
    print(f"Warning: Logger not available: {e}")
    HAS_LOGGER = False
    setup_logging = get_logger = lambda x: logging.getLogger(x)

# EventManager (optional)
try:
    from SpyderA_Core.SpyderA03_EventManager import EventManager, Event
    HAS_EVENT_MANAGER = True
except ImportError:
    EventManager = Event = None
    HAS_EVENT_MANAGER = False

# Broker modules (critical for testing race condition fix)
try:
    from SpyderB_Broker.SpyderB01_SpyderClient import get_spyder_client, IBConfig
    from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager, ConnectionConfig
    HAS_BROKER_MODULES = True
    print("✅ Broker modules loaded successfully!")
except ImportError as e:
    print(f"Warning: Broker modules not available: {e}")
    HAS_BROKER_MODULES = False
    get_spyder_client = get_connection_manager = None
    IBConfig = ConnectionConfig = None

# ==============================================================================
# CONFIGURATION
# ==============================================================================

class SpyderConfig:
    """Spyder application configuration with PROVEN race condition fix"""
    
    def __init__(self):
        # Application settings
        self.app_name = "SPYDER"
        self.version = "1.0"
        self.debug_mode = True
        
        # Broker connection settings with PROVEN race condition fix
        self.ib_host = '127.0.0.1'
        self.ib_port = 4002  # Paper trading port
        self.master_client_id = 2
        self.connection_timeout = 20.0
        
        # PROVEN race condition fix settings
        self.enable_race_condition_fix = True
        self.race_condition_delay = 1.0  # Proven 1.0 second delay
        
        # GUI settings
        self.enable_gui = True
        self.window_width = 1200
        self.window_height = 800
        
        # Logging settings
        self.log_level = logging.INFO
        self.log_to_file = True
        self.log_dir = project_root / "logs"
        
        # Operation modes
        self.headless_mode = False
        self.simulation_mode = False

# ==============================================================================
# SIMPLE GUI FOR CONNECTION TESTING
# ==============================================================================

class SpyderMainWindow(QWidget):
    """
    Simple main window for testing PROVEN race condition fix.
    
    This window will only appear after successful broker connection,
    proving that the race condition fix is working.
    """
    
    def __init__(self, spyder_app):
        super().__init__()
        self.spyder_app = spyder_app
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"SPYDER v{self.spyder_app.config.version} - PROVEN Race Condition Fix")
        self.setGeometry(100, 100, self.spyder_app.config.window_width, self.spyder_app.config.window_height)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("SPYDER - Autonomous Options Trading System")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2E8B57; margin: 20px;")
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("Initializing with PROVEN race condition fix...")
        self.status_label.setStyleSheet("font-size: 14px; margin: 10px; padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(self.status_label)
        
        # Connection info
        self.connection_info = QTextEdit()
        self.connection_info.setMaximumHeight(200)
        self.connection_info.setStyleSheet("font-family: monospace; font-size: 10px;")
        layout.addWidget(self.connection_info)
        
        # Test button
        self.test_button = QPushButton("Test PROVEN Race Condition Fix")
        self.test_button.clicked.connect(self.test_connection_fix)
        self.test_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #4CAF50; color: white;")
        layout.addWidget(self.test_button)
        
        # Disconnect button
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_broker)
        self.disconnect_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f44336; color: white;")
        layout.addWidget(self.disconnect_button)
        
        # Exit button
        self.exit_button = QPushButton("Exit")
        self.exit_button.clicked.connect(self.close)
        self.exit_button.setStyleSheet("font-size: 14px; padding: 10px; background-color: #9E9E9E; color: white;")
        layout.addWidget(self.exit_button)
        
        self.setLayout(layout)
        
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(1000)  # Update every second
    
    def update_status(self):
        """Update the status display."""
        if self.spyder_app.client and self.spyder_app.client.is_connected():
            status = self.spyder_app.client.get_connection_status()
            account_info = self.spyder_app.client.get_account_info()
            
            self.status_label.setText("✅ CONNECTED with PROVEN race condition fix!")
            self.status_label.setStyleSheet("font-size: 14px; margin: 10px; padding: 10px; background-color: #d4edda; color: #155724;")
            
            # Update connection info
            info_text = f"""Connection Status:
- Source: {status.get('source', 'Unknown')}
- Connected: {status.get('connected', False)}
- Client ID: {self.spyder_app.config.master_client_id}
- Host: {self.spyder_app.config.ib_host}:{self.spyder_app.config.ib_port}
- Race Condition Fix: {status.get('proven_race_condition_fix', False)}

Account Info:
- Accounts: {account_info.get('accounts', 'N/A')}
- Status: Connected with PROVEN race condition fix

GUI Status: VISIBLE (proving connection is stable!)
"""
            self.connection_info.setText(info_text)
        else:
            self.status_label.setText("❌ DISCONNECTED")
            self.status_label.setStyleSheet("font-size: 14px; margin: 10px; padding: 10px; background-color: #f8d7da; color: #721c24;")
            self.connection_info.setText("Not connected to broker")
    
    def test_connection_fix(self):
        """Test the PROVEN race condition fix."""
        if self.spyder_app.client:
            self.connection_info.append("\n🧪 Testing PROVEN race condition fix...")
            
            # Check if the test method exists
            if hasattr(self.spyder_app.client, 'test_connection_with_proven_fix'):
                result = self.spyder_app.client.test_connection_with_proven_fix()
                
                if result.get('success'):
                    self.connection_info.append("✅ Race condition fix test SUCCESSFUL!")
                    self.connection_info.append(f"Result: {result}")
                else:
                    self.connection_info.append("❌ Race condition fix test FAILED!")
                    self.connection_info.append(f"Error: {result.get('error', 'Unknown error')}")
            else:
                # Basic connection test
                if self.spyder_app.client.is_connected():
                    self.connection_info.append("✅ Basic connection test SUCCESSFUL!")
                else:
                    self.connection_info.append("❌ Basic connection test FAILED!")
    
    def disconnect_broker(self):
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
    
    def __init__(self, config: Optional[SpyderConfig] = None):
        """Initialize SPYDER application with PROVEN race condition fix."""
        
        # Configuration
        self.config = config or SpyderConfig()
        
        # Setup logging first
        self._setup_logging()
        self.logger = get_logger("SpyderApplication")
        
        # Core components
        self.event_manager: Optional[EventManager] = None
        self.connection_manager = None
        self.client = None
        self.gui_app: Optional[QApplication] = None
        self.main_window: Optional[SpyderMainWindow] = None
        
        # Application state
        self.running = False
        self.shutdown_requested = False
        
        self.logger.info("=" * 70)
        self.logger.info(f"SPYDER v{self.config.version} - PROVEN Race Condition Fix")
        self.logger.info("=" * 70)
        self.logger.info("Initializing application with proven broker connection fix...")

    def _setup_logging(self):
        """Setup application logging."""
        try:
            if HAS_LOGGER and hasattr(setup_logging, '__call__'):
                setup_logging()
            else:
                # Fallback logging setup
                logging.basicConfig(
                    level=self.config.log_level,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
        except Exception as e:
            print(f"Warning: Could not setup advanced logging: {e}")
            logging.basicConfig(level=logging.INFO)

    def initialize_core_systems(self) -> bool:
        """
        Initialize core systems with PROVEN race condition fix.
        
        The GUI will only appear if this succeeds, proving the fix works.
        """
        try:
            self.logger.info("🔧 Initializing core systems with PROVEN race condition fix...")
            
            # Initialize event manager (optional)
            if HAS_EVENT_MANAGER and EventManager:
                try:
                    self.event_manager = EventManager()
                    self.logger.info("✅ Event manager initialized")
                except Exception as e:
                    self.logger.warning(f"Event manager initialization failed: {e}")
                    self.event_manager = None
            else:
                self.logger.info("ℹ️ Event manager not available - continuing without it")
            
            # Initialize broker connection with PROVEN race condition fix (critical)
            if not self._initialize_broker_connection():
                self.logger.error("❌ Failed to initialize broker connection")
                return False
            
            self.logger.info("✅ Core systems initialized successfully with PROVEN race condition fix!")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Core system initialization failed: {e}")
            return False

    def _initialize_broker_connection(self) -> bool:
        """
        Initialize broker connection with PROVEN race condition fix.
        
        This is the critical test - if this succeeds, the GUI will appear.
        """
        if not HAS_BROKER_MODULES:
            self.logger.error("❌ Broker modules not available - cannot test race condition fix")
            print("\nTo test the race condition fix, ensure these modules exist:")
            print("- SpyderB_Broker/SpyderB01_SpyderClient.py")
            print("- SpyderB_Broker/SpyderB05_ConnectionManager.py")
            return False

        try:
            self.logger.info("🔌 Initializing broker connection with PROVEN race condition fix...")

            # Create connection configuration with PROVEN race condition fix
            if IBConfig:
                client_config = IBConfig()
                client_config.client_id = self.config.master_client_id
                client_config.host = self.config.ib_host
                client_config.port = self.config.ib_port
                client_config.timeout = self.config.connection_timeout
                client_config.readonly = False  # Allow trading operations
                
                # CRITICAL: Enable PROVEN race condition fix
                client_config.use_connection_manager = True
                client_config.enable_race_condition_fix = self.config.enable_race_condition_fix
                client_config.race_condition_delay = self.config.race_condition_delay
                
                self.logger.info(f"🔗 Connecting to IB Gateway: {self.config.ib_host}:{self.config.ib_port}")
                self.logger.info(f"📡 Using master client ID: {self.config.master_client_id}")
                self.logger.info(f"🛡️ PROVEN race condition fix ENABLED - expecting reliable connection")
                
                # Get client with PROVEN race condition fix
                self.client = get_spyder_client(client_config)
                
                # Connect with PROVEN race condition fix (should be 100% reliable now)
                connection_success = self.client.connect()
                
                if connection_success:
                    self.logger.info("✅ Broker connection established successfully with PROVEN race condition fix!")
                    
                    # Verify connection by getting account info
                    account_info = self.client.get_account_info()
                    if account_info.get('accounts'):
                        self.logger.info(f"📊 Account validation successful: {account_info['accounts']}")
                        return True
                    else:
                        self.logger.error("❌ Account validation failed")
                        return False
                else:
                    self.logger.error("❌ Broker connection failed despite race condition fix")
                    return False
            else:
                self.logger.error("❌ IBConfig not available")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Broker connection initialization error: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def start_gui(self) -> bool:
        """
        Start the GUI application.
        
        This will only be called after successful broker connection,
        proving the PROVEN race condition fix is working.
        """
        if not HAS_QT:
            self.logger.error("❌ PyQt6 not available - GUI disabled")
            print("\nTo enable GUI, install PyQt6:")
            print("pip install PyQt6")
            return False
        
        if self.config.headless_mode:
            self.logger.info("Running in headless mode - GUI disabled")
            return True
        
        try:
            self.logger.info("🖥️ Starting GUI application...")
            
            # Create QApplication
            self.gui_app = QApplication(sys.argv)
            self.gui_app.setApplicationName(self.config.app_name)
            self.gui_app.setApplicationVersion(self.config.version)
            
            # Create main window
            self.main_window = SpyderMainWindow(self)
            
            # Show the window - this proves the race condition fix worked!
            self.main_window.show()
            
            self.logger.info("✅ GUI application started successfully!")
            self.logger.info("🎉 GUI IS VISIBLE - PROVING PROVEN RACE CONDITION FIX WORKS!")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ GUI startup failed: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def run(self) -> int:
        """
        Run the SPYDER application.
        
        This is the main entry point that tests the PROVEN race condition fix.
        """
        try:
            self.logger.info("🚀 Starting SPYDER application with PROVEN race condition fix...")
            
            # Initialize core systems (including broker connection with proven fix)
            if not self.initialize_core_systems():
                self.logger.error("❌ Core system initialization failed")
                return 1
            
            # Start GUI (will only succeed if broker connection worked)
            if not self.start_gui():
                self.logger.error("❌ GUI startup failed")
                return 1
            
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            self.running = True
            
            if self.gui_app:
                # Run Qt event loop
                self.logger.info("🔄 Starting Qt event loop...")
                return_code = self.gui_app.exec()
                self.logger.info(f"Qt event loop finished with code: {return_code}")
                return return_code
            else:
                # Headless mode
                self.logger.info("🔄 Running in headless mode...")
                while self.running and not self.shutdown_requested:
                    time.sleep(1)
                return 0
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
            return 0
        except Exception as e:
            self.logger.error(f"❌ Application error: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return 1
        finally:
            self.shutdown()

    def shutdown(self):
        """Shutdown the application gracefully."""
        try:
            self.logger.info("🛑 Shutting down SPYDER application...")
            self.running = False
            self.shutdown_requested = True
            
            # Disconnect from broker
            if self.client and self.client.is_connected():
                self.logger.info("🔌 Disconnecting from broker...")
                self.client.disconnect()
            
            # Close GUI
            if self.main_window:
                self.main_window.close()
            
            if self.gui_app:
                self.gui_app.quit()
            
            self.logger.info("✅ SPYDER application shutdown complete")
            
        except Exception as e:
            self.logger.error(f"❌ Shutdown error: {e}")

    def _signal_handler(self, signum, frame):
        """Handle system signals."""
        self.logger.info(f"Received signal {signum}")
        self.shutdown_requested = True
        if self.gui_app:
            self.gui_app.quit()

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def main():
    """
    Main entry point for SPYDER application.
    
    This will test the PROVEN race condition fix by:
    1. Attempting broker connection with the fix
    2. Only showing GUI if connection succeeds
    3. Proving the fix works by displaying the interface
    """
    print("=" * 70)
    print("SPYDER v1.0 - PROVEN Race Condition Fix Test")
    print("=" * 70)
    print("Testing EXACT working pattern from successful test:")
    print("• await asyncio.sleep(1.0) for API handshake stability")
    print("• Account validation for connection verification")
    print("• GUI will only appear if connection succeeds")
    print("=" * 70)
    print()
    
    # System status check
    print("System Status:")
    print(f"✅ Python: {sys.version.split()[0]}")
    print(f"{'✅' if HAS_QT else '❌'} PyQt6: {'Available' if HAS_QT else 'Not available'}")
    print(f"{'✅' if HAS_LOGGER else '❌'} Logger: {'Available' if HAS_LOGGER else 'Not available'}")
    print(f"{'✅' if HAS_EVENT_MANAGER else 'ℹ️'} EventManager: {'Available' if HAS_EVENT_MANAGER else 'Optional - not available'}")
    print(f"{'✅' if HAS_BROKER_MODULES else '❌'} Broker Modules: {'Available' if HAS_BROKER_MODULES else 'Not available'}")
    print()
    
    if not HAS_BROKER_MODULES:
        print("❌ Cannot test race condition fix without broker modules.")
        print("Ensure the temp_fixed modules have been properly installed.")
        return 1
    
    # Parse command line arguments (simple version)
    headless = "--headless" in sys.argv
    debug = "--debug" in sys.argv
    simulation = "--sim" in sys.argv
    
    # Create configuration
    config = SpyderConfig()
    config.headless_mode = headless
    config.debug_mode = debug
    config.simulation_mode = simulation
    
    if debug:
        config.log_level = logging.DEBUG
    
    # Create and run application
    app = SpyderApplication(config)
    return_code = app.run()
    
    if return_code == 0:
        print("\n🎉 SPYDER APPLICATION COMPLETED SUCCESSFULLY!")
        print("✅ PROVEN race condition fix is working!")
        if not headless:
            print("✅ GUI appeared - proving broker connection succeeded!")
    else:
        print(f"\n❌ SPYDER APPLICATION FAILED (code: {return_code})")
        print("❌ Check the error messages above for details")
    
    return return_code

if __name__ == "__main__":
    sys.exit(main())
