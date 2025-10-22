#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB32_IBKRSessionManager.py
Purpose: IBKR Client Portal Web API session management and authentication

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-01-24 Time: 12:00:00

Module Description:
    This module handles session management and authentication for the IBKR Client Portal Web API.
    It manages the connection to the local gateway, tracks authentication status, and handles
    session maintenance including tickle requests to keep the session alive. The module provides
    a robust interface for monitoring gateway availability, tracking authentication state,
    and handling automatic reconnection scenarios.

Module Constants:
    DEFAULT_BASE_URL (str): Default IBKR Client Portal gateway URL (default: "https://localhost:5000")
    DEFAULT_API_VERSION (str): Default API version (default: "v1")
    DEFAULT_TIMEOUT (int): Default request timeout in seconds (default: 30)
    DEFAULT_AUTH_CHECK_INTERVAL (int): Default authentication check interval in seconds (default: 5)
    DEFAULT_TICKLE_INTERVAL (int): Default tickle interval in seconds (default: 60)
    MAX_RETRY_ATTEMPTS (int): Maximum number of retry attempts for failed requests (default: 3)
    DEFAULT_RETRY_DELAY (float): Default delay between retry attempts in seconds (default: 1.0)

Change Log:
    2025-01-24 (v1.0.0):
        - Initial module creation following Spyder template standards
        - Implemented comprehensive session management
        - Added authentication status monitoring
        - Implemented gateway availability checking
        - Added tickle mechanism for session maintenance
        - Implemented proper error handling and recovery
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import threading
import asyncio
import uuid
import warnings
import logging
import urllib3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Safe imports with fallbacks
try:
    from SpyderU_Utilities.SpyderU07_Constants import BaseConstants
except ImportError:
    BaseConstants = None

# Disable SSL warnings for self-signed certificate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_BASE_URL = "https://localhost:5000"
DEFAULT_API_VERSION = "v1"
DEFAULT_TIMEOUT = 30
DEFAULT_AUTH_CHECK_INTERVAL = 5  # seconds
DEFAULT_TICKLE_INTERVAL = 60  # seconds
MAX_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0

# ==============================================================================
# ENUMS
# ==============================================================================
class ModuleState(Enum):
    """Module operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()

class AuthStatus(Enum):
    """Authentication status enumeration."""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATED = "authenticated"
    AUTHENTICATING = "authenticating"
    FAILED = "failed"
    EXPIRED = "expired"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"

class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class SessionConfig:
    """Configuration for session management."""
    base_url: str = "https://localhost:5000"
    api_version: str = "v1"
    timeout: int = 30
    verify_ssl: bool = False
    auth_check_interval: int = 5  # seconds
    tickle_interval: int = 60  # seconds
    max_auth_wait: int = 300  # 5 minutes
    session_refresh_interval: int = 3600  # 1 hour
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class SessionInfo:
    """Session information."""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    server_name: Optional[str] = None
    auth_time: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    expires_at: Optional[datetime] = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SessionManager:
    """
    Manages IBKR Client Portal sessions and authentication.

    This class handles all aspects of session management including:
    - Gateway connectivity
    - Authentication status monitoring
    - Session maintenance
    - Error handling and recovery

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        state: Current module state
        config: Module configuration
        _state_lock: Thread lock for state management
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, config: Optional[SessionConfig] = None):
        """
        Initialize Session Manager.

        Args:
            config: Session configuration
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or SessionConfig()

        # State management
        self.state = ModuleState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # API endpoints
        self.base_url = self.config.base_url.rstrip("/")
        self.api_base = f"{self.base_url}/{self.config.api_version}/api"

        # Session state
        self.auth_status = AuthStatus.NOT_AUTHENTICATED
        self.connection_state = ConnectionState.DISCONNECTED
        self.session_info = SessionInfo()

        # HTTP session
        self.session = requests.Session()
        self.session.verify = self.config.verify_ssl

        # Threading
        self._lock = threading.RLock()
        self._running = False
        self._auth_thread: Optional[threading.Thread] = None
        self._tickle_thread: Optional[threading.Thread] = None

        # Statistics
        self._stats = {
            'auth_checks': 0,
            'successful_auths': 0,
            'failed_auths': 0,
            'tickle_sent': 0,
            'tickle_failed': 0,
            'gateway_checks': 0,
            'gateway_available': 0,
            'last_auth_check': None,
            'last_tickle': None,
            'session_start': None,
            'total_uptime': 0
        }

        # Event callbacks
        self._auth_callbacks: List[Callable] = []
        self._connection_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []

        self.logger.info(f"SessionManager initialized for {self.base_url}")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the session manager with all necessary setup.

        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False

                self.logger.info(f"Initializing {self.__class__.__name__}...")

                # Perform initialization tasks
                if not self._validate_configuration():
                    return False

                if not self._setup_resources():
                    return False

                self.state = ModuleState.READY
                self.logger.info(f"{self.__class__.__name__} initialization completed")
                return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "initialize")
            self.state = ModuleState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the session manager.

        Returns:
            True if started successfully
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.READY:
                    self.logger.warning(f"Cannot start from state: {self.state}")
                    return False

                self.logger.info(f"Starting {self.__class__.__name__}...")

                # Clear shutdown event
                self._shutdown_event.clear()

                if self._running:
                    return True

                self._running = True

                # Start authentication monitoring thread
                self._auth_thread = threading.Thread(
                    target=self._auth_monitor_loop,
                    daemon=True,
                    name="IBKR-AuthMonitor"
                )
                self._auth_thread.start()

                # Start tickle thread
                self._tickle_thread = threading.Thread(
                    target=self._tickle_loop,
                    daemon=True,
                    name="IBKR-Tickle"
                )
                self._tickle_thread.start()

                self.state = ModuleState.RUNNING
                self.logger.info(f"{self.__class__.__name__} started successfully")
                return True

        except Exception as e:
            self.logger.error(f"Failed to start {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "start")
            self.state = ModuleState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the session manager gracefully.

        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [ModuleState.RUNNING, ModuleState.PAUSED]:
                    self.logger.warning(f"Cannot stop from state: {self.state}")
                    return False

                self.logger.info(f"Stopping {self.__class__.__name__}...")

                # Signal shutdown
                self._shutdown_event.set()
                self._running = False

                # Wait for threads to finish
                if self._auth_thread and self._auth_thread.is_alive():
                    self._auth_thread.join(timeout=5.0)

                if self._tickle_thread and self._tickle_thread.is_alive():
                    self._tickle_thread.join(timeout=5.0)

                # Close session
                self.session.close()

                # Clean up resources
                self._cleanup_resources()

                self.state = ModuleState.STOPPED
                self.logger.info(f"{self.__class__.__name__} stopped successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _validate_configuration(self) -> bool:
        """Validate module configuration."""
        try:
            if not self.config.base_url:
                self.logger.error("Base URL not provided")
                return False

            if self.config.timeout <= 0:
                self.logger.error("Invalid timeout value")
                return False

            if self.config.auth_check_interval <= 0:
                self.logger.error("Invalid auth check interval")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _setup_resources(self) -> bool:
        """Set up required resources."""
        try:
            # Setup HTTP session
            self.session = requests.Session()
            self.session.verify = self.config.verify_ssl

            self.logger.debug("Resources setup completed")
            return True

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            return False

    def _cleanup_resources(self):
        """Clean up allocated resources."""
        try:
            # Close HTTP session
            if hasattr(self, 'session'):
                self.session.close()

            # Clear callbacks
            self._auth_callbacks.clear()
            self._connection_callbacks.clear()
            self._error_callbacks.clear()

            self.logger.debug("Resources cleaned up")

        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")

    # ==========================================================================
    # CORE OPERATIONS
    # ==========================================================================

    def is_gateway_available(self) -> bool:
        """
        Check if the IBKR Client Portal Gateway is available.

        Returns:
            True if gateway is available
        """
        try:
            with self._lock:
                self._stats['gateway_checks'] += 1

            # Try to access the login page
            response = self.session.get(
                f"{self.base_url}/sso/Login",
                timeout=self.config.timeout
            )

            is_available = response.status_code in [200, 302]

            with self._lock:
                if is_available:
                    self._stats['gateway_available'] += 1
                    self.connection_state = ConnectionState.CONNECTED
                else:
                    self.connection_state = ConnectionState.ERROR

            return is_available

        except Exception as e:
            self.logger.debug(f"Gateway availability check failed: {e}")
            with self._lock:
                self.connection_state = ConnectionState.ERROR
            return False

    def check_auth_status(self) -> bool:
        """
        Check the current authentication status.

        Returns:
            True if authenticated
        """
        try:
            # Rate limit auth checks
            with self._lock:
                if (self._stats['last_auth_check'] and
                    time.time() - self._stats['last_auth_check'] < self.config.auth_check_interval):
                    return self.auth_status == AuthStatus.AUTHENTICATED

                self._stats['auth_checks'] += 1
                self._stats['last_auth_check'] = time.time()

            # Check gateway availability first
            if not self.is_gateway_available():
                self.auth_status = AuthStatus.GATEWAY_UNAVAILABLE
                self._notify_error("Gateway is not available")
                return False

            # Check authentication status
            response = self._make_request('GET', '/iserver/auth/status')
            if not response:
                self.auth_status = AuthStatus.FAILED
                return False

            auth_data = response.json()
            is_authenticated = (
                auth_data.get('authenticated', False) and
                auth_data.get('connected', False)
            )

            with self._lock:
                if is_authenticated:
                    if self.auth_status != AuthStatus.AUTHENTICATED:
                        # Just authenticated
                        self._stats['successful_auths'] += 1
                        self.session_info.auth_time = datetime.now()
                        self.session_info.server_name = auth_data.get('serverName')

                        # Get session details
                        self._update_session_info()

                    self.auth_status = AuthStatus.AUTHENTICATED

                    # Update last activity
                    self.session_info.last_activity = datetime.now()

                    if not self._stats['session_start']:
                        self._stats['session_start'] = datetime.now()

                    self._notify_auth_change(True)

                else:
                    if self.auth_status == AuthStatus.AUTHENTICATED:
                        # Session expired
                        self.auth_status = AuthStatus.EXPIRED
                        self._notify_auth_change(False)
                        self._notify_error("Session expired - manual login required")
                    else:
                        self.auth_status = AuthStatus.NOT_AUTHENTICATED

            return is_authenticated

        except Exception as e:
            self.logger.error(f"Error checking auth status: {e}")
            with self._lock:
                self.auth_status = AuthStatus.FAILED
                self._stats['failed_auths'] += 1
            return False

    def send_tickle(self) -> bool:
        """
        Send a tickle request to keep the session alive.

        Returns:
            True if tickle was successful
        """
        try:
            if not self.is_authenticated():
                return False

            response = self._make_request('GET', '/tickle')
            if response and response.status_code == 200:
                with self._lock:
                    self._stats['tickle_sent'] += 1
                    self._stats['last_tickle'] = time.time()
                    self.session_info.last_activity = datetime.now()

                self.logger.debug("Session tickle successful")
                return True
            else:
                with self._lock:
                    self._stats['tickle_failed'] += 1
                return False

        except Exception as e:
            self.logger.error(f"Error sending tickle: {e}")
            with self._lock:
                self._stats['tickle_failed'] += 1
            return False

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self.auth_status == AuthStatus.AUTHENTICATED

    def get_session_info(self) -> SessionInfo:
        """Get current session information."""
        with self._lock:
            return SessionInfo(
                session_id=self.session_info.session_id,
                user_id=self.session_info.user_id,
                account_id=self.session_info.account_id,
                server_name=self.session_info.server_name,
                auth_time=self.session_info.auth_time,
                last_activity=self.session_info.last_activity,
                expires_at=self.session_info.expires_at
            )

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status information."""
        with self._lock:
            uptime = 0
            if self._stats['session_start']:
                uptime = (datetime.now() - self._stats['session_start']).total_seconds()

            return {
                'auth_status': self.auth_status.value,
                'connection_state': self.connection_state.value,
                'authenticated': self.is_authenticated(),
                'gateway_available': self.connection_state == ConnectionState.CONNECTED,
                'session_info': {
                    'session_id': self.session_info.session_id,
                    'user_id': self.session_info.user_id,
                    'account_id': self.session_info.account_id,
                    'server_name': self.session_info.server_name,
                    'auth_time': self.session_info.auth_time.isoformat() if self.session_info.auth_time else None,
                    'last_activity': self.session_info.last_activity.isoformat() if self.session_info.last_activity else None,
                    'expires_at': self.session_info.expires_at.isoformat() if self.session_info.expires_at else None
                },
                'statistics': {
                    'auth_checks': self._stats['auth_checks'],
                    'successful_auths': self._stats['successful_auths'],
                    'failed_auths': self._stats['failed_auths'],
                    'tickle_sent': self._stats['tickle_sent'],
                    'tickle_failed': self._stats['tickle_failed'],
                    'gateway_checks': self._stats['gateway_checks'],
                    'gateway_available': self._stats['gateway_available'],
                    'uptime_seconds': uptime,
                    'last_auth_check': self._stats['last_auth_check'],
                    'last_tickle': self._stats['last_tickle']
                },
                'config': {
                    'base_url': self.base_url,
                    'auth_check_interval': self.config.auth_check_interval,
                    'tickle_interval': self.config.tickle_interval,
                    'timeout': self.config.timeout
                }
            }

    def add_auth_callback(self, callback: Callable[[bool], None]):
        """Add callback for authentication state changes."""
        self._auth_callbacks.append(callback)

    def add_connection_callback(self, callback: Callable[[bool], None]):
        """Add callback for connection state changes."""
        self._connection_callbacks.append(callback)

    def add_error_callback(self, callback: Callable[[str], None]):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make HTTP request to IBKR API.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters

        Returns:
            Response object or None
        """
        try:
            url = f"{self.api_base}{endpoint}"

            for attempt in range(self.config.retry_attempts):
                try:
                    if method.upper() == 'GET':
                        response = self.session.get(url, **kwargs)
                    elif method.upper() == 'POST':
                        response = self.session.post(url, **kwargs)
                    elif method.upper() == 'DELETE':
                        response = self.session.delete(url, **kwargs)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    if response.status_code == 200:
                        return response
                    elif response.status_code == 401:
                        self.auth_status = AuthStatus.NOT_AUTHENTICATED
                        return None
                    else:
                        self.logger.warning(f"Request failed: {response.status_code} - {response.text}")

                except requests.exceptions.RequestException as e:
                    self.logger.warning(f"Request attempt {attempt + 1} failed: {e}")
                    if attempt < self.config.retry_attempts - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise e

            return None

        except Exception as e:
            self.logger.error(f"Error making {method} request to {endpoint}: {e}")
            return None

    def _update_session_info(self):
        """Update session information from API."""
        try:
            # Get accounts to extract session info
            response = self._make_request('GET', '/iserver/accounts')
            if response:
                accounts = response.json()
                if accounts and len(accounts) > 0:
                    # Use first account for session info
                    account = accounts[0]
                    self.session_info.account_id = account.get('accountId')
                    self.session_info.user_id = account.get('userId')

            # Try to get session ID from other endpoints
            # Note: IBKR doesn't always expose session ID directly

        except Exception as e:
            self.logger.error(f"Error updating session info: {e}")

    def _auth_monitor_loop(self):
        """Background thread to monitor authentication status."""
        self.logger.info("Authentication monitor started")

        while self._running:
            try:
                self.check_auth_status()
                time.sleep(self.config.auth_check_interval)

            except Exception as e:
                self.logger.error(f"Error in auth monitor loop: {e}")
                time.sleep(10)  # Brief pause on error

        self.logger.info("Authentication monitor stopped")

    def _tickle_loop(self):
        """Background thread to send tickle requests."""
        self.logger.info("Tickle loop started")

        while self._running:
            try:
                if self.is_authenticated():
                    self.send_tickle()

                time.sleep(self.config.tickle_interval)

            except Exception as e:
                self.logger.error(f"Error in tickle loop: {e}")
                time.sleep(30)  # Brief pause on error

        self.logger.info("Tickle loop stopped")

    def _notify_auth_change(self, authenticated: bool):
        """Notify callbacks of authentication state change."""
        for callback in self._auth_callbacks:
            try:
                callback(authenticated)
            except Exception as e:
                self.logger.error(f"Error in auth callback: {e}")

    def _notify_connection_change(self, connected: bool):
        """Notify callbacks of connection state change."""
        for callback in self._connection_callbacks:
            try:
                callback(connected)
            except Exception as e:
                self.logger.error(f"Error in connection callback: {e}")

    def _notify_error(self, error_message: str):
        """Notify callbacks of error events."""
        for callback in self._error_callbacks:
            try:
                callback(error_message)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance (if needed)
_module_instance: Optional[SessionManager] = None
_module_lock = Lock()


def get_module_instance(config: Optional[SessionConfig] = None) -> SessionManager:
    """
    Get singleton module instance.

    Args:
        config: Module configuration (required for first call)

    Returns:
        SessionManager singleton instance
    """
    global _module_instance

    with _module_lock:
        if _module_instance is None:
            if config is None:
                raise ValueError("Configuration required for first module creation")
            _module_instance = SessionManager(config)

        return _module_instance


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_session_manager(**kwargs) -> SessionManager:
    """
    Create a SessionManager instance with configuration.

    Args:
        **kwargs: Configuration parameters

    Returns:
        SessionManager instance
    """
    config = SessionConfig(**kwargs)
    return SessionManager(config)


# Global instance for backward compatibility
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


if __name__ == "__main__":
    # Example usage
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def auth_changed(authenticated):
        print(f"Authentication changed: {authenticated}")

    def connection_changed(connected):
        print(f"Connection changed: {connected}")

    def error_occurred(error):
        print(f"Error: {error}")

    # Create and start session manager
    manager = SessionManager()
    manager.add_auth_callback(auth_changed)
    manager.add_connection_callback(connection_changed)
    manager.add_error_callback(error_occurred)

    try:
        manager.start()

        print("SessionManager started. Check authentication status...")

        # Check status
        if manager.check_auth_status():
            print("✅ Authenticated with IBKR")
            status = manager.get_status()
            print(f"Session info: {status['session_info']}")
        else:
            print("❌ Not authenticated. Please login via browser:")
            print(f"https://localhost:5000")

        # Keep running for demonstration
        time.sleep(60)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        manager.stop()