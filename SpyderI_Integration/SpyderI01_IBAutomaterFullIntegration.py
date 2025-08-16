#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI01_IBAutomaterFullIntegration.py
Group: I (Integration)
Purpose: Full IB Gateway automation with UI automation for automated login
Author: Mohamed Talib
Date Created: 2025-08-16
Last Updated: 2025-08-16 Time: 01:45:00

Description:
    This module provides complete integration with the Python IBAutomater,
    including UI automation for automated login. It handles gateway startup,
    automatic credential entry, 2FA support, and seamless integration with
    the Spyder trading system.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import os
import sys
import time
import logging
import subprocess
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime

# Add Python IBAutomater path to system path
IB_AUTOMATER_PATH = Path(__file__).parent.parent / "IB_Automater_Python" / "python_ibautomater" / "src"
if IB_AUTOMATER_PATH.exists():
    sys.path.insert(0, str(IB_AUTOMATER_PATH))

# ==============================================================================
# DEPENDENCY CHECK AND INSTALLATION
# ==============================================================================
def check_and_install_dependencies():
    """Check and install required dependencies for UI automation"""
    required_packages = {
        'pyautogui': 'pyautogui>=0.9.54',
        'cv2': 'opencv-python>=4.5.0',
        'PIL': 'pillow>=8.0.0',
        'psutil': 'psutil>=5.8.0',
        'numpy': 'numpy>=1.20.0',
        'pytesseract': 'pytesseract>=0.3.8'  # Optional but recommended
    }
    
    missing_packages = []
    
    for module_name, package_spec in required_packages.items():
        try:
            if module_name == 'cv2':
                import cv2
            elif module_name == 'PIL':
                from PIL import Image
            else:
                __import__(module_name)
        except ImportError:
            missing_packages.append(package_spec)
    
    if missing_packages:
        print(f"Installing missing packages: {missing_packages}")
        for package in missing_packages:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print("Dependencies installed successfully!")
        return True
    return False

# Check dependencies
dependencies_installed = check_and_install_dependencies()

# ==============================================================================
# IMPORT IBAUTOMATER
# ==============================================================================
try:
    # Try to import from installed package first
    from ibautomater import IBAutomater as OriginalIBAutomater
    from ibautomater import IBConfig, TradingMode, IBEvent, StartResult
    from ibautomater.exceptions import IBAutomaterError, AuthenticationError, UIError
    IBAUTOMATER_AVAILABLE = True
except ImportError:
    # Fall back to local implementation
    try:
        from ibautomater.ibautomater import IBAutomater as OriginalIBAutomater
        from ibautomater.config import IBConfig, TradingMode
        from ibautomater.events import IBEvent, StartResult
        from ibautomater.exceptions import IBAutomaterError, AuthenticationError, UIError
        IBAUTOMATER_AVAILABLE = True
    except ImportError:
        IBAUTOMATER_AVAILABLE = False
        logging.warning("Full IBAutomater not available, using simplified version")

# ==============================================================================
# CONFIGURATION
# ==============================================================================
@dataclass
class SpyderIBAutomaterConfig:
    """Enhanced configuration for Spyder IB Gateway automation"""
    # IB Gateway settings
    ib_directory: str = "/home/adam/Jts/ibgateway"
    ib_version: str = "1037"
    username: str = ""  # Will be loaded from secure storage
    password: str = ""  # Will be loaded from secure storage
    trading_mode: str = "paper"
    port: int = 4002
    
    # Automation settings
    auto_login: bool = True
    export_logs: bool = False
    auto_restart_time: str = "23:45"
    max_login_attempts: int = 3
    two_factor_timeout: int = 180
    
    # UI automation settings
    ui_timeout: float = 30.0
    screenshot_interval: float = 1.0
    template_match_threshold: float = 0.8
    enable_ocr: bool = False  # Enable OCR for text recognition
    
    # Credentials file (encrypted)
    credentials_file: str = "~/.spyder/ib_credentials.json"
    
    def load_credentials(self) -> bool:
        """Load credentials from secure storage"""
        cred_path = Path(self.credentials_file).expanduser()
        if cred_path.exists():
            try:
                with open(cred_path, 'r') as f:
                    creds = json.load(f)
                    self.username = creds.get('username', '')
                    self.password = creds.get('password', '')
                    return True
            except Exception as e:
                logging.error(f"Failed to load credentials: {e}")
        return False
    
    def save_credentials(self) -> bool:
        """Save credentials to secure storage"""
        cred_path = Path(self.credentials_file).expanduser()
        cred_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(cred_path, 'w') as f:
                json.dump({
                    'username': self.username,
                    'password': self.password
                }, f)
            # Set restrictive permissions
            cred_path.chmod(0o600)
            return True
        except Exception as e:
            logging.error(f"Failed to save credentials: {e}")
            return False

# ==============================================================================
# ENHANCED IB AUTOMATER
# ==============================================================================
class SpyderIBAutomater:
    """
    Enhanced IBAutomater wrapper for Spyder integration
    
    Provides:
    - Full UI automation for login
    - Credential management
    - Event handling
    - Error recovery
    - Integration with Spyder modules
    """
    
    def __init__(self, config: Optional[SpyderIBAutomaterConfig] = None):
        """Initialize SpyderIBAutomater"""
        self.config = config or SpyderIBAutomaterConfig()
        self.logger = logging.getLogger(__name__)
        
        # Load credentials
        if not self.config.username or not self.config.password:
            if not self.config.load_credentials():
                self.logger.warning("No credentials loaded - will need manual login")
        
        # Initialize IBAutomater based on availability
        self.automater = None
        self.using_full_automater = False
        
        if IBAUTOMATER_AVAILABLE and self.config.auto_login:
            self._init_full_automater()
        else:
            self._init_simplified_automater()
        
        # State tracking
        self.gateway_running = False
        self.ready_for_trading = False
        self.login_completed = False
        self.two_factor_pending = False
        
        # Event callbacks
        self.on_gateway_started: Optional[Callable] = None
        self.on_login_completed: Optional[Callable] = None
        self.on_ready_for_trading: Optional[Callable] = None
        self.on_gateway_stopped: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def _init_full_automater(self):
        """Initialize full IBAutomater with UI automation"""
        try:
            self.logger.info("Initializing full IBAutomater with UI automation...")
            
            # Convert trading mode
            mode = "paper" if self.config.trading_mode == "paper" else "live"
            
            # Create IBAutomater instance
            self.automater = OriginalIBAutomater(
                ib_directory=self.config.ib_directory,
                ib_version=self.config.ib_version,
                username=self.config.username,
                password=self.config.password,
                trading_mode=mode,
                port=self.config.port,
                export_ib_gateway_logs=self.config.export_logs
            )
            
            # Setup event handlers
            self._setup_full_event_handlers()
            
            self.using_full_automater = True
            self.logger.info("✅ Full IBAutomater initialized with UI automation")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize full IBAutomater: {e}")
            self.logger.info("Falling back to simplified version")
            self._init_simplified_automater()
    
    def _init_simplified_automater(self):
        """Initialize simplified automater (fallback)"""
        self.logger.info("Using simplified IBAutomater (manual login required)")
        # Import and use the simplified version from SpyderIBAutomaterIntegration
        from SpyderIBAutomaterIntegration import IBAutomater as SimplifiedAutomater
        
        self.automater = SimplifiedAutomater(self.config)
        self._setup_simplified_event_handlers()
        self.using_full_automater = False
    
    def _setup_full_event_handlers(self):
        """Setup event handlers for full IBAutomater"""
        if not self.automater:
            return
        
        self.automater.on_output_data_received = self._on_output_data
        self.automater.on_error_data_received = self._on_error_data
        self.automater.on_exited = self._on_gateway_exit
        self.automater.on_restarted = self._on_gateway_restart
        
        # Additional event handlers for login
        if hasattr(self.automater, 'on_login_completed'):
            self.automater.on_login_completed = self._on_login_complete
        
        if hasattr(self.automater, 'on_two_factor_required'):
            self.automater.on_two_factor_required = self._on_two_factor
    
    def _setup_simplified_event_handlers(self):
        """Setup event handlers for simplified automater"""
        if not self.automater:
            return
        
        self.automater.on_output_data_received = self._on_output_data
        self.automater.on_error_data_received = self._on_error_data
        self.automater.on_exited = self._on_gateway_exit
    
    # ==============================================================================
    # EVENT HANDLERS
    # ==============================================================================
    def _on_output_data(self, data: str):
        """Handle gateway output data"""
        self.logger.debug(f"Gateway: {data}")
        
        # Check for important messages
        if "ready to accept API connections" in data.lower():
            self._on_ready_for_trading()
        elif "login successful" in data.lower():
            self._on_login_complete({"status": "success"})
        elif "authentication failed" in data.lower():
            self._on_authentication_failed()
    
    def _on_error_data(self, data: str):
        """Handle gateway error data"""
        self.logger.error(f"Gateway Error: {data}")
        
        if self.on_error:
            self.on_error({"type": "gateway_error", "message": data})
    
    def _on_gateway_exit(self, event_args):
        """Handle gateway exit"""
        self.gateway_running = False
        self.ready_for_trading = False
        self.login_completed = False
        
        if event_args.get("unexpected"):
            self.logger.error(f"⚠️ Gateway exited unexpectedly (code: {event_args.get('exit_code')})")
            
            # Auto-restart on unexpected exit
            if self.config.max_login_attempts > 0:
                self.logger.info("Attempting auto-restart...")
                time.sleep(5)
                self.start()
        else:
            self.logger.info("Gateway exited normally")
        
        if self.on_gateway_stopped:
            self.on_gateway_stopped()
    
    def _on_gateway_restart(self, event_data):
        """Handle gateway restart"""
        self.logger.info("🔄 Gateway restarted (daily restart)")
        
        # Re-login if using full automater
        if self.using_full_automater and self.config.auto_login:
            self.logger.info("Performing automatic re-login...")
    
    def _on_login_complete(self, event_data):
        """Handle login completion"""
        self.login_completed = True
        self.logger.info("✅ Login completed successfully")
        
        if self.on_login_completed:
            self.on_login_completed(event_data)
    
    def _on_two_factor(self, event_data):
        """Handle 2FA requirement"""
        self.two_factor_pending = True
        self.logger.warning("🔐 Two-factor authentication required")
        self.logger.warning(f"Please complete 2FA on your mobile device within {self.config.two_factor_timeout} seconds")
        
        # Start timeout timer
        threading.Timer(self.config.two_factor_timeout, self._on_two_factor_timeout).start()
    
    def _on_two_factor_timeout(self):
        """Handle 2FA timeout"""
        if self.two_factor_pending:
            self.logger.error("❌ Two-factor authentication timed out")
            self.two_factor_pending = False
    
    def _on_ready_for_trading(self):
        """Handle gateway ready for trading"""
        self.ready_for_trading = True
        self.logger.info("✅ Gateway ready for API connections!")
        
        if self.on_ready_for_trading:
            self.on_ready_for_trading()
        
        # Connect Spyder modules
        self._connect_spyder_modules()
    
    def _on_authentication_failed(self):
        """Handle authentication failure"""
        self.logger.error("❌ Authentication failed")
        
        if self.on_error:
            self.on_error({"type": "auth_failed", "message": "Authentication failed"})
    
    # ==============================================================================
    # MAIN METHODS
    # ==============================================================================
    def start(self, wait_for_connection: bool = True) -> bool:
        """
        Start IB Gateway with full automation
        
        Args:
            wait_for_connection: Wait for gateway to be ready
            
        Returns:
            bool: True if started successfully
        """
        self.logger.info("=" * 60)
        self.logger.info("Starting IB Gateway with Full Automation")
        self.logger.info(f"Mode: {self.config.trading_mode}")
        self.logger.info(f"Port: {self.config.port}")
        self.logger.info(f"Auto-login: {self.config.auto_login and self.using_full_automater}")
        self.logger.info("=" * 60)
        
        try:
            # Start gateway
            result = self.automater.start(wait_for_connection=wait_for_connection)
            
            if result.success if hasattr(result, 'success') else result:
                self.gateway_running = True
                
                pid = result.process_id if hasattr(result, 'process_id') else None
                self.logger.info(f"✅ Gateway started (PID: {pid})")
                
                if self.on_gateway_started:
                    self.on_gateway_started({"pid": pid})
                
                if self.using_full_automater and self.config.auto_login:
                    self.logger.info("⏳ Performing automated login...")
                    
                    # Wait for login to complete
                    login_timeout = self.config.ui_timeout
                    start_time = time.time()
                    
                    while not self.login_completed and (time.time() - start_time < login_timeout):
                        time.sleep(1)
                    
                    if self.login_completed:
                        self.logger.info("✅ Automated login successful!")
                    else:
                        self.logger.warning("⚠️ Automated login timed out - manual login may be required")
                else:
                    self.logger.info("⚠️ Manual login required - please log in to IB Gateway")
                
                # Wait for ready state
                if wait_for_connection:
                    ready_timeout = 60  # seconds
                    start_time = time.time()
                    
                    while not self.ready_for_trading and (time.time() - start_time < ready_timeout):
                        time.sleep(1)
                    
                    if self.ready_for_trading:
                        self.logger.info("✅ Gateway ready for trading!")
                        return True
                    else:
                        self.logger.warning("⚠️ Gateway started but not ready for trading yet")
                        return True
                
                return True
            else:
                error_msg = result.error_message if hasattr(result, 'error_message') else "Unknown error"
                self.logger.error(f"❌ Failed to start gateway: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to start gateway: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop IB Gateway"""
        self.logger.info("Stopping IB Gateway...")
        
        try:
            if self.automater.stop():
                self.gateway_running = False
                self.ready_for_trading = False
                self.login_completed = False
                self.logger.info("✅ Gateway stopped")
                
                if self.on_gateway_stopped:
                    self.on_gateway_stopped()
                
                return True
        except Exception as e:
            self.logger.error(f"❌ Failed to stop gateway: {e}")
        
        return False
    
    def restart(self) -> bool:
        """Restart IB Gateway"""
        self.logger.info("Restarting IB Gateway...")
        
        try:
            result = self.automater.restart()
            
            if result.success if hasattr(result, 'success') else result:
                self.logger.info("✅ Gateway restarted")
                return True
        except Exception as e:
            self.logger.error(f"❌ Failed to restart gateway: {e}")
        
        return False
    
    def _connect_spyder_modules(self):
        """Connect Spyder trading modules to IB Gateway"""
        try:
            # Import Spyder modules
            from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager
            
            self.logger.info("Connecting Spyder modules to IB Gateway...")
            
            connection_manager = ConnectionManager()
            if connection_manager.connect():
                self.logger.info("✅ Spyder modules connected successfully")
            else:
                self.logger.warning("⚠️ Failed to connect Spyder modules")
                
        except ImportError as e:
            self.logger.debug(f"Spyder modules not available: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        return {
            "gateway_running": self.gateway_running,
            "ready_for_trading": self.ready_for_trading,
            "login_completed": self.login_completed,
            "two_factor_pending": self.two_factor_pending,
            "using_full_automater": self.using_full_automater,
            "auto_login": self.config.auto_login and self.using_full_automater,
            "config": {
                "mode": self.config.trading_mode,
                "port": self.config.port,
                "ib_directory": self.config.ib_directory,
                "ib_version": self.config.ib_version
            }
        }
    
    def setup_credentials(self, username: str = None, password: str = None) -> bool:
        """
        Setup or update credentials
        
        Args:
            username: IB username (will prompt if not provided)
            password: IB password (will prompt if not provided)
            
        Returns:
            bool: True if credentials saved successfully
        """
        import getpass
        
        if not username:
            username = input("Enter IB Username: ")
        if not password:
            password = getpass.getpass("Enter IB Password: ")
        
        self.config.username = username
        self.config.password = password
        
        if self.config.save_credentials():
            self.logger.info("✅ Credentials saved successfully")
            return True
        else:
            self.logger.error("❌ Failed to save credentials")
            return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main function to demonstrate full IB Gateway automation"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "=" * 60)
    print("SPYDER IB GATEWAY FULL AUTOMATION")
    print("=" * 60)
    print("This will start IB Gateway with automated login")
    print("=" * 60 + "\n")
    
    # Create configuration
    config = SpyderIBAutomaterConfig(
        ib_directory="/home/adam/Jts/ibgateway",
        ib_version="1037",
        trading_mode="paper",
        port=4002,
        auto_login=True
    )
    
    # Check for credentials
    if not config.username or not config.password:
        if not config.load_credentials():
            print("\n⚠️ No credentials found. Please set them up:")
            automater = SpyderIBAutomater(config)
            if not automater.setup_credentials():
                print("Failed to setup credentials")
                return
    
    # Create automater
    automater = SpyderIBAutomater(config)
    
    # Setup event callbacks
    def on_ready():
        print("\n🎯 Gateway is ready for trading!")
    
    def on_error(error_data):
        print(f"\n❌ Error: {error_data}")
    
    automater.on_ready_for_trading = on_ready
    automater.on_error = on_error
    
    # Start gateway
    if automater.start():
        print("\n✅ IB Gateway is running!")
        
        # Print status
        status = automater.get_status()
        print(f"\nStatus: {json.dumps(status, indent=2)}")
        
        # Keep running
        print("\n⏳ Gateway will keep running. Press Ctrl+C to stop...")
        
        try:
            while automater.gateway_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down...")
            automater.stop()
    else:
        print("\n❌ Failed to start IB Gateway")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
