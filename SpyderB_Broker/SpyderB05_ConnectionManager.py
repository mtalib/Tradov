#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module: SpyderB05_ConnectionManager.py
Group: B (Broker Integration)
Purpose: Connection handling and reconnection logic

Description:
    This module manages the connection to Interactive Brokers, handles disconnections,
    implements automatic reconnection strategies, and monitors connection health.
    It provides a robust connection layer that ensures the trading system maintains
    connectivity even in unstable network conditions.

Author: Mohamed Talib
Date: 2024-01-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import threading
import socket
from typing import Dict, List, Optional, Any, Tuple, Set, Type, Callable
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
import json
import psutil

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# None for this module

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import *
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderB_Broker.SpyderB01_IBClient import IBClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connection timeouts and intervals
CONNECTION_TIMEOUT = 30  # seconds
HEARTBEAT_INTERVAL = 300  # seconds (5 minutes)
RECONNECT_DELAY_MIN = 5  # seconds
RECONNECT_DELAY_MAX = 60  # seconds
MAX_RECONNECT_ATTEMPTS = 10

# Connection health thresholds
MAX_LATENCY_MS = 1000  # 1 second
LATENCY_WARNING_MS = 500
MIN_HEARTBEAT_SUCCESS_RATE = 0.90  # 90%

# Process names for IB applications
IB_PROCESS_NAMES = ["tws", "java", "gateway", "ibgateway"]

# Default connection parameters
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497  # TWS paper trading
LIVE_PORT = 7496  # TWS live trading
GATEWAY_PORT = 4001  # IB Gateway paper
GATEWAY_LIVE_PORT = 4000  # IB Gateway live


# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionState(Enum):
    """Connection states"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    READY = "ready"
    ERROR = "error"
    RECONNECTING = "reconnecting"


class ConnectionType(Enum):
    """Connection types"""

    TWS_PAPER = "tws_paper"
    TWS_LIVE = "tws_live"
    GATEWAY_PAPER = "gateway_paper"
    GATEWAY_LIVE = "gateway_live"


class DisconnectReason(Enum):
    """Disconnection reasons"""

    USER_INITIATED = "user_initiated"
    CONNECTION_LOST = "connection_lost"
    AUTHENTICATION_FAILED = "auth_failed"
    API_ERROR = "api_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class ConnectionConfig:
    """Connection configuration"""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = 1
    connection_type: ConnectionType = ConnectionType.TWS_PAPER
    auto_reconnect: bool = True
    max_reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS
    use_ssl: bool = False

    def get_port(self) -> int:
        """Get port based on connection type"""
        port_map = {
            ConnectionType.TWS_PAPER: DEFAULT_PORT,
            ConnectionType.TWS_LIVE: LIVE_PORT,
            ConnectionType.GATEWAY_PAPER: GATEWAY_PORT,
            ConnectionType.GATEWAY_LIVE: GATEWAY_LIVE_PORT,
        }
        return port_map.get(self.connection_type, self.port)


class ConnectionStats:
    """Connection statistics"""

    connect_time: Optional[datetime.datetime] = None
    disconnect_time: Optional[datetime.datetime] = None
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    total_messages_sent: int = 0
    total_messages_received: int = 0
    average_latency_ms: float = 0.0
    heartbeat_success_rate: float = 1.0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "connect_time": (
                self.connect_time.isoformat() if self.connect_time else None
            ),
            "disconnect_time": (
                self.disconnect_time.isoformat() if self.disconnect_time else None
            ),
            "uptime_seconds": self.uptime_seconds,
            "reconnect_count": self.reconnect_count,
            "messages_sent": self.total_messages_sent,
            "messages_received": self.total_messages_received,
            "avg_latency_ms": self.average_latency_ms,
            "heartbeat_success_rate": self.heartbeat_success_rate,
            "last_error": self.last_error,
        }


# ==============================================================================
# CONNECTION MANAGER CLASS
# ==============================================================================
class ConnectionManager:
    """
    Manages IB API connection with automatic reconnection and health monitoring.

    Features:
    - Automatic connection establishment
    - Connection health monitoring
    - Automatic reconnection on failure
    - Latency tracking
    - Connection statistics
    - Process monitoring
    """

    def __init__(self, config: ConnectionConfig, event_manager: EventManager):
        """
        Initialize connection manager.

        Args:
            config: Connection configuration
            event_manager: Event manager instance
        """
        self.config = config
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # IB Client
        self.ib_client: Optional[IBClient] = None

        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.disconnect_reason = DisconnectReason.UNKNOWN
        self.is_reconnecting = False
        self.reconnect_attempts = 0

        # Statistics
        self.stats = ConnectionStats()
        self.latency_history: deque = deque(maxlen=100)
        self.heartbeat_history: deque = deque(maxlen=20)

        # Threads
        self._monitor_thread: Optional[threading.Thread] = None
        self._reconnect_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False

        # Callbacks
        self.connection_callbacks: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "ready": [],
            "error": [],
        }

        # Locks
        self._lock = threading.RLock()

        # Last heartbeat time
        self._last_heartbeat_time = 0
        self._heartbeat_timeout = HEARTBEAT_INTERVAL * 3

        self.logger.info(
            f"ConnectionManager initialized for {config.connection_type.value}"
        )

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> bool:
        """
        Start connection manager and establish connection.

        Returns:
            Success status
        """
        with self._lock:
            if self._running:
                self.logger.warning("Connection manager already running")
                return True

            self._running = True

            # Start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_connection, daemon=True
            )
            self._monitor_thread.start()

            # Establish initial connection
            return self.connect()

    def stop(self) -> None:
        """Stop connection manager and disconnect"""
        with self._lock:
            self._running = False
            self.disconnect(DisconnectReason.USER_INITIATED)

            # Wait for threads
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5.0)
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=5.0)

            self.logger.info("Connection manager stopped")

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    def connect(self) -> bool:
        """
        Establish connection to IB.

        Returns:
            Success status
        """
        with self._lock:
            if self.state in [ConnectionState.CONNECTED, ConnectionState.READY]:
                self.logger.info("Already connected")
                return True

            self.state = ConnectionState.CONNECTING
            self.stats.connect_time = datetime.datetime.now()

        try:
            # Check if IB Gateway/TWS is running
            if not self._check_ib_running():
                self.logger.error("IB Gateway/TWS not running")
                self._handle_connection_error("IB Gateway/TWS not running")
                return False

            # Create IB client
            self.ib_client = IBClient(self.event_manager)

            # Set up callbacks
            self._setup_ib_callbacks()

            # Connect
            self.logger.info(
                f"Connecting to {self.config.host}:{self.config.get_port()}"
            )

            connected = self.ib_client.connect(
                self.config.host, self.config.get_port(), self.config.client_id
            )

            if connected:
                # Start IB client thread
                ib_thread = threading.Thread(target=self.ib_client.run, daemon=True)
                ib_thread.start()

                # Wait for connection to be established
                timeout = time.time() + CONNECTION_TIMEOUT
                while time.time() < timeout:
                    if self.ib_client.isConnected():
                        self._on_connected()
                        return True
                    time.sleep(0.1)

                # Timeout
                self.logger.error("Connection timeout")
                self._handle_connection_error("Connection timeout")
                return False
            else:
                self.logger.error("Failed to connect")
                self._handle_connection_error("Connection failed")
                return False

        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self._handle_connection_error(str(e))
            return False

    def disconnect(
        self, reason: DisconnectReason = DisconnectReason.USER_INITIATED
    ) -> None:
        """
        Disconnect from IB.

        Args:
            reason: Reason for disconnection
        """
        with self._lock:
            if self.state == ConnectionState.DISCONNECTED:
                return

            self.disconnect_reason = reason
            self.state = ConnectionState.DISCONNECTED
            self.stats.disconnect_time = datetime.datetime.now()

            # Stop heartbeat
            if self._heartbeat_thread:
                self._heartbeat_thread = None

            # Disconnect IB client
            if self.ib_client and self.ib_client.isConnected():
                try:
                    self.ib_client.disconnect()
                except Exception as e:
                    self.logger.error(f"Error disconnecting: {e}")

            self.ib_client = None

        # Notify callbacks
        self._execute_callbacks("disconnected", reason)

        # Emit event
        self.event_manager.emit(
            Event(
                EventType.SYSTEM,
                {
                    "type": "connection_lost",
                    "reason": reason.value,
                    "timestamp": datetime.datetime.now(),
                },
            )
        )

        self.logger.info(f"Disconnected: {reason.value}")

        # Auto-reconnect if enabled
        if (
            self.config.auto_reconnect
            and reason != DisconnectReason.USER_INITIATED
            and self._running
        ):
            self._schedule_reconnect()

    def reconnect(self) -> bool:
        """
        Reconnect to IB.

        Returns:
            Success status
        """
        with self._lock:
            if self.is_reconnecting:
                self.logger.warning("Reconnection already in progress")
                return False

            self.is_reconnecting = True
            self.state = ConnectionState.RECONNECTING

        try:
            # Disconnect first
            self.disconnect(DisconnectReason.CONNECTION_LOST)

            # Wait before reconnecting
            delay = self._get_reconnect_delay()
            self.logger.info(f"Reconnecting in {delay} seconds...")
            time.sleep(delay)

            # Try to connect
            success = self.connect()

            with self._lock:
                if success:
                    self.reconnect_attempts = 0
                    self.stats.reconnect_count += 1
                else:
                    self.reconnect_attempts += 1

                self.is_reconnecting = False

            return success

        except Exception as e:
            self.logger.error(f"Reconnection error: {e}")
            with self._lock:
                self.is_reconnecting = False
            return False

    # ==========================================================================
    # CONNECTION MONITORING
    # ==========================================================================
    def _monitor_connection(self) -> None:
        """Monitor connection health"""
        while self._running:
            try:
                if self.state == ConnectionState.READY:
                    # Check connection health
                    if not self._check_connection_health():
                        self.logger.warning("Connection health check failed")
                        self.disconnect(DisconnectReason.CONNECTION_LOST)

                    # Update statistics
                    self._update_statistics()

                    # Check heartbeat timeout
                    if (
                        time.time() - self._last_heartbeat_time
                        > self._heartbeat_timeout
                    ):
                        self.logger.error("Heartbeat timeout")
                        self.disconnect(DisconnectReason.TIMEOUT)

                time.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Error in connection monitor: {e}")

    def _check_connection_health(self) -> bool:
        """
        Check if connection is healthy.

        Returns:
            Health status
        """
        if not self.ib_client or not self.ib_client.isConnected():
            return False

        # Check heartbeat success rate
        if self.heartbeat_history:
            success_rate = sum(1 for h in self.heartbeat_history if h) / len(
                self.heartbeat_history
            )
            if success_rate < MIN_HEARTBEAT_SUCCESS_RATE:
                self.logger.warning(f"Low heartbeat success rate: {success_rate:.2%}")
                return False

        # Check average latency
        if self.latency_history:
            avg_latency = sum(self.latency_history) / len(self.latency_history)
            if avg_latency > MAX_LATENCY_MS:
                self.logger.warning(f"High latency: {avg_latency:.0f}ms")
                return False

        return True

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to check connection"""
        while self._running and self.state == ConnectionState.READY:
            try:
                start_time = time.time()

                # Send heartbeat (request current time)
                self.ib_client.reqCurrentTime()

                # Wait for response
                time.sleep(0.5)

                # Check if we got a response
                latency = (time.time() - start_time) * 1000
                self.latency_history.append(latency)
                self.heartbeat_history.append(True)

                # Update last heartbeat time
                self._last_heartbeat_time = time.time()

                # Log if high latency
                if latency > LATENCY_WARNING_MS:
                    self.logger.warning(f"High latency detected: {latency:.0f}ms")

                time.sleep(HEARTBEAT_INTERVAL)

            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                self.heartbeat_history.append(False)

    def _update_statistics(self) -> None:
        """Update connection statistics"""
        if self.stats.connect_time:
            self.stats.uptime_seconds = (
                datetime.datetime.now() - self.stats.connect_time
            ).total_seconds()

        if self.latency_history:
            self.stats.average_latency_ms = sum(self.latency_history) / len(
                self.latency_history
            )

        if self.heartbeat_history:
            self.stats.heartbeat_success_rate = sum(
                1 for h in self.heartbeat_history if h
            ) / len(self.heartbeat_history)

    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _setup_ib_callbacks(self) -> None:
        """Set up IB client callbacks"""
        if not self.ib_client:
            return

        # Connection callbacks
        self.ib_client.register_callback("nextValidId", self._on_next_valid_id)
        self.ib_client.register_callback("error", self._on_error)
        self.ib_client.register_callback("connectionClosed", self._on_connection_closed)
        self.ib_client.register_callback("currentTime", self._on_current_time)

    def _on_connected(self) -> None:
        """Handle successful connection"""
        with self._lock:
            self.state = ConnectionState.CONNECTED
            self.stats.connect_time = datetime.datetime.now()

        self.logger.info("Connected to IB")

        # Start heartbeat
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()

        # Notify callbacks
        self._execute_callbacks("connected")

    def _on_next_valid_id(self, orderId: int) -> None:
        """Handle next valid order ID (indicates ready state)"""
        with self._lock:
            if self.state != ConnectionState.READY:
                self.state = ConnectionState.READY

                # Emit ready event
                self.event_manager.emit(
                    Event(
                        EventType.SYSTEM,
                        {
                            "type": "connection_ready",
                            "order_id": orderId,
                            "timestamp": datetime.datetime.now(),
                        },
                    )
                )

                # Notify callbacks
                self._execute_callbacks("ready")

                self.logger.info(f"Connection ready - Next order ID: {orderId}")

    def _on_error(self, reqId: int, errorCode: int, errorString: str) -> None:
        """Handle error from IB"""
        # Connection-related errors
        connection_errors = [502, 504, 1100, 1101, 1102]

        if errorCode in connection_errors:
            self.logger.error(f"Connection error {errorCode}: {errorString}")
            self.stats.last_error = f"{errorCode}: {errorString}"

            if errorCode in [1100, 1101, 1102]:  # Connectivity lost
                self.disconnect(DisconnectReason.CONNECTION_LOST)
            elif errorCode == 502:  # Cannot connect to TWS
                self.disconnect(DisconnectReason.CONNECTION_LOST)

    def _on_connection_closed(self) -> None:
        """Handle connection closed event"""
        self.logger.warning("Connection closed by IB")
        self.disconnect(DisconnectReason.CONNECTION_LOST)

    def _on_current_time(self, time: int) -> None:
        """Handle current time response (heartbeat)"""
        self._last_heartbeat_time = time
        self.stats.total_messages_received += 1

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _check_ib_running(self) -> bool:
        """
        Check if IB Gateway or TWS is running.

        Returns:
            True if running
        """
        try:
            for proc in psutil.process_iter(["name"]):
                if any(
                    ib_name in proc.info["name"].lower() for ib_name in IB_PROCESS_NAMES
                ):
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking IB process: {e}")
            # Try socket connection as fallback
            return self._check_port_open()

    def _check_port_open(self) -> bool:
        """
        Check if IB port is open.

        Returns:
            True if port is open
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((self.config.host, self.config.get_port()))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _get_reconnect_delay(self) -> int:
        """
        Get exponential backoff delay for reconnection.

        Returns:
            Delay in seconds
        """
        delay = min(
            RECONNECT_DELAY_MIN * (2**self.reconnect_attempts), RECONNECT_DELAY_MAX
        )
        return delay

    def _schedule_reconnect(self) -> None:
        """Schedule reconnection attempt"""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            self.logger.error("Maximum reconnection attempts reached")
            self._execute_callbacks("error", "Max reconnections reached")
            return

        self._reconnect_thread = threading.Thread(target=self.reconnect, daemon=True)
        self._reconnect_thread.start()

    def _handle_connection_error(self, error: str) -> None:
        """
        Handle connection error.

        Args:
            error: Error message
        """
        with self._lock:
            self.state = ConnectionState.ERROR
            self.stats.last_error = error

        self._execute_callbacks("error", error)

        # Attempt reconnection
        if self.config.auto_reconnect and self._running:
            self._schedule_reconnect()

    def _execute_callbacks(self, event_type: str, *args) -> None:
        """
        Execute registered callbacks.

        Args:
            event_type: Type of event
            args: Additional arguments
        """
        if event_type in self.connection_callbacks:
            for callback in self.connection_callbacks[event_type]:
                try:
                    callback(*args)
                except Exception as e:
                    self.logger.error(f"Error in callback: {e}")

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """
        Register callback for connection events.

        Args:
            event_type: Event type ('connected', 'disconnected', 'ready', 'error')
            callback: Callback function
        """
        if event_type in self.connection_callbacks:
            self.connection_callbacks[event_type].append(callback)

    def unregister_callback(self, event_type: str, callback: Callable) -> None:
        """
        Unregister callback.

        Args:
            event_type: Event type
            callback: Callback function
        """
        if event_type in self.connection_callbacks:
            if callback in self.connection_callbacks[event_type]:
                self.connection_callbacks[event_type].remove(callback)

    def get_connection_state(self) -> ConnectionState:
        """
        Get current connection state.

        Returns:
            Connection state
        """
        return self.state

    def is_connected(self) -> bool:
        """
        Check if connected.

        Returns:
            True if connected
        """
        return self.state in [ConnectionState.CONNECTED, ConnectionState.READY]

    def is_ready(self) -> bool:
        """
        Check if ready for trading.

        Returns:
            True if ready
        """
        return self.state == ConnectionState.READY

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.to_dict()

    def reset_statistics(self) -> None:
        """Reset connection statistics"""
        with self._lock:
            self.stats = ConnectionStats()
            self.latency_history.clear()
            self.heartbeat_history.clear()

    def force_reconnect(self) -> bool:
        """
        Force reconnection.

        Returns:
            Success status
        """
        self.logger.info("Forcing reconnection")
        self.disconnect(DisconnectReason.USER_INITIATED)
        time.sleep(2)
        return self.connect()

    def _connect_to_ib(self) -> bool:
        """
        Connect to Interactive Brokers Gateway.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Get configuration values
            host = self.config.get("ib.host", "127.0.0.1")
            port = self.config.get("ib.port", 4001)  # Gateway paper trading port
            client_id = self.config.get("ib.client_id", 1)

            self.logger.info(f"Connecting to IB Gateway at {host}:{port}")

            # Attempt connection with retries
            max_retries = 3
            for attempt in range(max_retries):
                if self.ib_client.connect(host, port, client_id):
                    self.logger.info("Successfully connected to IB Gateway")
                    return True

                if attempt < max_retries - 1:
                    self.logger.warning(
                        f"Connection attempt {attempt + 1} failed, retrying..."
                    )
                    time.sleep(2)

            self.logger.error("Failed to connect to IB Gateway")
            return False

        except Exception as e:
            self.logger.error(f"IB connection error: {str(e)}")
            return False


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test connection manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager

    event_manager = EventManager()
    config = ConnectionConfig(
        connection_type=ConnectionType.TWS_PAPER, auto_reconnect=True
    )

    manager = ConnectionManager(config, event_manager)

    # Register callbacks
    manager.register_callback("connected", lambda: print("Connected!"))
    manager.register_callback("ready", lambda: print("Ready to trade!"))
    manager.register_callback("disconnected", lambda r: print(f"Disconnected: {r}"))
    manager.register_callback("error", lambda e: print(f"Error: {e}"))

    # Start connection
    if manager.start():
        print("Connection manager started successfully")

        # Run for a while
        try:
            time.sleep(60)
        except KeyboardInterrupt:
            print("Stopping...")

        # Stop
        manager.stop()
        print("Connection manager stopped")
    else:
        print("Failed to start connection manager")
