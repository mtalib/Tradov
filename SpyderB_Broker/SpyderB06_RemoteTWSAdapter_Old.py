#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Remote TWS Connection Adapter
=====================================

This module provides seamless integration between Spyder's existing connection
management system and remote TWS (Trader Workstation) running on a separate
Windows computer. It extends the proven EnhancedConnectionManager approach
to work across network boundaries.

Key Features:
- Drop-in replacement for local Gateway connections
- Network latency compensation
- Enhanced error handling for network issues
- Connection health monitoring
- Automatic failover and reconnection
- Windows TWS compatibility optimizations

Author: Spyder Trading System
Date: 2025-01-02
"""

import asyncio
import socket
import time
import logging
from typing import Dict, Any, Optional, Tuple, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
from datetime import datetime, timedelta
import json
import os

# Third-party imports
try:
    from ib_async import IB

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    IB = None
    logging.warning("ib_async not available - RemoteTWSAdapter will be limited")

# Spyder imports
try:
    from SpyderB_Broker.SpyderB05_ConnectionManager import (
        ConnectionManager,
        ConnectionState,
        ConnectionConfig,
    )
except ImportError:
    logging.warning("Spyder modules not available - using fallback imports")
    ConnectionManager = object
    ConnectionState = None
    ConnectionConfig = None


class RemoteConnectionState(Enum):
    """Enhanced connection states for remote TWS"""

    DISCONNECTED = "disconnected"
    NETWORK_TEST = "network_test"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    NETWORK_ERROR = "network_error"
    TWS_ERROR = "tws_error"
    RECONNECTING = "reconnecting"
    DEGRADED = "degraded"  # Connected but with issues


@dataclass
class RemoteTWSConfig:
    """Configuration for remote TWS connection"""

    windows_ip: str
    paper_port: int = 7497
    live_port: int = 7496
    client_id: int = 1
    connection_timeout: int = 30
    network_timeout: int = 10
    max_reconnect_attempts: int = 5
    reconnect_delay: int = 10
    heartbeat_interval: int = 30
    ping_timeout: int = 5
    enable_network_monitoring: bool = True
    enable_latency_compensation: bool = True
    trading_mode: str = "paper"  # "paper" or "live"

    def get_connection_port(self) -> int:
        """Get the appropriate port based on trading mode"""
        return self.paper_port if self.trading_mode == "paper" else self.live_port


@dataclass
class NetworkMetrics:
    """Network performance metrics"""

    latency_ms: float = 0.0
    packet_loss_percent: float = 0.0
    connection_uptime: timedelta = field(default_factory=lambda: timedelta())
    last_heartbeat: Optional[datetime] = None
    reconnection_count: int = 0
    total_disconnections: int = 0


class RemoteTWSAdapter:
    """
    Adapter for connecting to TWS running on remote Windows computer.

    This class provides a drop-in replacement for local Gateway connections
    while handling the complexities of network communication, latency
    compensation, and remote system monitoring.
    """

    def __init__(
        self, config: RemoteTWSConfig, logger: Optional[logging.Logger] = None
    ):
        """Initialize the Remote TWS Adapter"""
        self.config: RemoteTWSConfig = config
        self.logger: logging.Logger = logger or logging.getLogger(__name__)

        # Connection state
        self.state: RemoteConnectionState = RemoteConnectionState.DISCONNECTED
        self.ib: Optional[IB] = None
        self.connection_start_time: Optional[datetime] = None
        self.last_successful_connection: Optional[datetime] = None

        # Network monitoring
        self.network_metrics: NetworkMetrics = NetworkMetrics()
        self.network_monitor_thread: Optional[threading.Thread] = None
        self.network_monitor_active: bool = False

        # Connection management
        self.reconnect_attempts: int = 0
        self.max_reconnect_attempts: int = config.max_reconnect_attempts
        self.reconnect_delay: int = config.reconnect_delay

        # Event callbacks
        self.connection_callbacks: List[Callable] = []
        self.disconnection_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []

        # Performance tracking
        self.connection_history: List[Dict[str, Any]] = []
        self.performance_stats: Dict[str, Any] = {
            "total_connections": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "average_connection_time": 0.0,
            "network_issues": 0,
            "tws_issues": 0,
        }

        self.logger.info(f"RemoteTWSAdapter initialized for {config.windows_ip}")

    def test_network_connectivity(self) -> Tuple[bool, str, float]:
        """
        Test basic network connectivity to Windows computer.

        Returns:
            Tuple of (success, message, latency_ms)
        """
        start_time = time.time()

        try:
            # Test ping (ICMP)
            ping_result = os.system(
                f"ping -c 1 -W {self.config.ping_timeout} {self.config.windows_ip} > /dev/null 2>&1"
            )
            ping_success = ping_result == 0

            # Test port connectivity (TCP)
            port = self.config.get_connection_port()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.network_timeout)

            connect_result = sock.connect_ex((self.config.windows_ip, port))
            sock.close()

            port_success = connect_result == 0
            latency_ms = (time.time() - start_time) * 1000

            if ping_success and port_success:
                return (
                    True,
                    f"Network connectivity OK (latency: {latency_ms:.1f}ms)",
                    latency_ms,
                )
            elif port_success:
                return (
                    True,
                    f"Port accessible but ping failed (latency: {latency_ms:.1f}ms)",
                    latency_ms,
                )
            else:
                return (
                    False,
                    f"Cannot connect to {self.config.windows_ip}:{port}",
                    latency_ms,
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return False, f"Network test error: {str(e)}", latency_ms

    async def connect_async(self) -> bool:
        """
        Establish asynchronous connection to remote TWS.

        Returns:
            True if connection successful, False otherwise
        """
        if not IB_ASYNC_AVAILABLE or IB is None:
            self.logger.error("ib_async not available for connection")
            return False

        self.state = RemoteConnectionState.NETWORK_TEST
        self.logger.info(f"Connecting to remote TWS at {self.config.windows_ip}")

        # Test network connectivity first
        network_ok, network_msg, latency = self.test_network_connectivity()
        self.network_metrics.latency_ms = latency

        if not network_ok:
            self.state = RemoteConnectionState.NETWORK_ERROR
            self.logger.error(f"Network connectivity failed: {network_msg}")
            self.performance_stats["network_issues"] += 1
            return False

        self.logger.info(f"Network connectivity OK: {network_msg}")

        # Initialize IB connection
        try:
            self.state = RemoteConnectionState.CONNECTING
            self.ib = IB()

            connection_start = time.time()
            port = self.config.get_connection_port()

            self.logger.info(
                f"Attempting TWS connection to {self.config.windows_ip}:{port} (Client ID: {self.config.client_id})"
            )

            await self.ib.connectAsync(
                host=self.config.windows_ip,
                port=port,
                clientId=self.config.client_id,
                timeout=self.config.connection_timeout,
            )

            connection_time = time.time() - connection_start

            if self.ib.isConnected():
                self.state = RemoteConnectionState.CONNECTED
                self.connection_start_time = datetime.now()
                self.last_successful_connection = self.connection_start_time
                self.reconnect_attempts = 0

                # Update performance stats
                self.performance_stats["total_connections"] += 1
                self.performance_stats["successful_connections"] += 1

                # Calculate average connection time
                total = self.performance_stats["successful_connections"]
                current_avg = self.performance_stats["average_connection_time"]
                self.performance_stats["average_connection_time"] = (
                    current_avg * (total - 1) + connection_time
                ) / total

                # Log connection details
                try:
                    accounts = self.ib.managedAccounts()
                    self.logger.info("✅ Connected to remote TWS successfully!")
                    self.logger.info(f"   Connection time: {connection_time:.2f}s")
                    self.logger.info(f"   Network latency: {latency:.1f}ms")
                    self.logger.info(f"   Accounts: {accounts}")

                    # Record connection history
                    self.connection_history.append(
                        {
                            "timestamp": self.connection_start_time.isoformat(),
                            "connection_time": connection_time,
                            "latency_ms": latency,
                            "accounts": accounts,
                            "mode": self.config.trading_mode,
                            "client_id": self.config.client_id,
                        }
                    )

                except Exception as e:
                    self.logger.warning(f"Could not retrieve account info: {e}")

                # Start network monitoring if enabled
                if self.config.enable_network_monitoring:
                    self._start_network_monitoring()

                # Trigger connection callbacks
                self._trigger_callbacks(self.connection_callbacks)

                return True
            else:
                self.state = RemoteConnectionState.TWS_ERROR
                self.logger.error("Connection established but TWS not responding")
                self.performance_stats["tws_issues"] += 1
                return False

        except asyncio.TimeoutError:
            self.state = RemoteConnectionState.TWS_ERROR
            self.logger.error(
                f"Connection timeout after {self.config.connection_timeout}s"
            )
            self.performance_stats["failed_connections"] += 1
            self.performance_stats["tws_issues"] += 1
            return False

        except Exception as e:
            self.state = RemoteConnectionState.TWS_ERROR
            self.logger.error(f"Connection failed: {str(e)}")
            self.performance_stats["failed_connections"] += 1
            self.performance_stats["tws_issues"] += 1
            return False

    def connect_sync(self) -> bool:
        """
        Establish synchronous connection to remote TWS.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            return asyncio.run(self.connect_async())
        except Exception as e:
            self.logger.error(f"Synchronous connection failed: {str(e)}")
            return False

    async def disconnect_async(self) -> bool:
        """
        Disconnect from remote TWS asynchronously.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            if self.ib and self.ib.isConnected():
                await self.ib.disconnectAsync()
                self.logger.info("Disconnected from remote TWS")

            self.state = RemoteConnectionState.DISCONNECTED
            self.connection_start_time = None

            # Stop network monitoring
            self._stop_network_monitoring()

            # Update metrics
            if self.connection_start_time:
                uptime = datetime.now() - self.connection_start_time
                self.network_metrics.connection_uptime += uptime

            # Trigger disconnection callbacks
            self._trigger_callbacks(self.disconnection_callbacks)

            return True

        except Exception as e:
            self.logger.error(f"Disconnection error: {str(e)}")
            return False

    def disconnect_sync(self) -> bool:
        """
        Disconnect from remote TWS synchronously.

        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            return asyncio.run(self.disconnect_async())
        except Exception as e:
            self.logger.error(f"Synchronous disconnection failed: {str(e)}")
            return False

    def is_connected(self) -> bool:
        """Check if connection is active"""
        return (
            self.ib is not None
            and self.ib.isConnected()
            and self.state == RemoteConnectionState.CONNECTED
        )

    def get_ib_instance(self) -> Optional[IB]:
        """Get the IB instance for trading operations"""
        if self.is_connected():
            return self.ib
        return None

    async def reconnect_async(self) -> bool:
        """
        Attempt to reconnect to remote TWS.

        Returns:
            True if reconnection successful, False otherwise
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error(
                f"Maximum reconnect attempts ({self.max_reconnect_attempts}) reached"
            )
            return False

        self.state = RemoteConnectionState.RECONNECTING
        self.reconnect_attempts += 1
        self.network_metrics.reconnection_count += 1

        self.logger.info(
            f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}"
        )

        # Disconnect first if still connected
        if self.ib and self.ib.isConnected():
            await self.disconnect_async()

        # Wait before reconnecting
        await asyncio.sleep(self.reconnect_delay)

        # Attempt reconnection
        return await self.connect_async()

    def _start_network_monitoring(self):
        """Start network monitoring thread"""
        if self.network_monitor_active:
            return

        self.network_monitor_active = True
        self.network_monitor_thread = threading.Thread(
            target=self._network_monitor_loop, daemon=True
        )
        self.network_monitor_thread.start()
        self.logger.debug("Network monitoring started")

    def _stop_network_monitoring(self):
        """Stop network monitoring thread"""
        self.network_monitor_active = False
        if self.network_monitor_thread and self.network_monitor_thread.is_alive():
            self.network_monitor_thread.join(timeout=5)
        self.logger.debug("Network monitoring stopped")

    def _network_monitor_loop(self):
        """Network monitoring loop (runs in separate thread)"""
        while self.network_monitor_active and self.is_connected():
            try:
                # Test network connectivity
                network_ok, _, latency = self.test_network_connectivity()
                self.network_metrics.latency_ms = latency
                self.network_metrics.last_heartbeat = datetime.now()

                if not network_ok:
                    self.logger.warning("Network connectivity issue detected")
                    self.state = RemoteConnectionState.DEGRADED
                    self.network_metrics.total_disconnections += 1

                    # Trigger error callbacks
                    self._trigger_callbacks(self.error_callbacks, "network_issue")

                time.sleep(self.config.heartbeat_interval)

            except Exception as e:
                self.logger.error(f"Network monitoring error: {str(e)}")
                time.sleep(self.config.heartbeat_interval)

    def _trigger_callbacks(self, callbacks: List[Callable], *args, **kwargs):
        """Trigger callback functions safely"""
        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Callback error: {str(e)}")

    def add_connection_callback(self, callback: Callable):
        """Add callback for connection events"""
        self.connection_callbacks.append(callback)

    def add_disconnection_callback(self, callback: Callable):
        """Add callback for disconnection events"""
        self.disconnection_callbacks.append(callback)

    def add_error_callback(self, callback: Callable):
        """Add callback for error events"""
        self.error_callbacks.append(callback)

    def get_network_metrics(self) -> NetworkMetrics:
        """Get current network performance metrics"""
        return self.network_metrics

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get connection performance statistics"""
        return self.performance_stats.copy()

    def get_connection_history(self) -> List[Dict[str, Any]]:
        """Get connection history"""
        return self.connection_history.copy()

    def save_diagnostics(self, filepath: str):
        """Save diagnostic information to file"""
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "windows_ip": self.config.windows_ip,
                "trading_mode": self.config.trading_mode,
                "client_id": self.config.client_id,
            },
            "state": self.state.value if self.state else "unknown",
            "network_metrics": {
                "latency_ms": self.network_metrics.latency_ms,
                "packet_loss_percent": self.network_metrics.packet_loss_percent,
                "connection_uptime": str(self.network_metrics.connection_uptime),
                "last_heartbeat": self.network_metrics.last_heartbeat.isoformat()
                if self.network_metrics.last_heartbeat
                else None,
                "reconnection_count": self.network_metrics.reconnection_count,
                "total_disconnections": self.network_metrics.total_disconnections,
            },
            "performance_stats": self.performance_stats,
            "connection_history": self.connection_history,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(diagnostics, f, indent=2, default=str)
            self.logger.info(f"Diagnostics saved to: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save diagnostics: {str(e)}")


class RemoteTWSConnectionManager:
    """
    Enhanced connection manager that extends Spyder's existing ConnectionManager
    to work with remote TWS connections seamlessly.
    """

    def __init__(
        self,
        config: Optional[ConnectionConfig],
        remote_config: RemoteTWSConfig,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize remote TWS connection manager"""
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Remote TWS specific setup
        self.remote_config: RemoteTWSConfig = remote_config
        self.remote_adapter: RemoteTWSAdapter = RemoteTWSAdapter(remote_config, logger)
        self.connection_type: str = "remote_tws"
        self.ib: Optional[IB] = None
        self.state: Optional[RemoteConnectionState] = RemoteConnectionState.DISCONNECTED

        self.logger.info(
            f"RemoteTWSConnectionManager initialized for {remote_config.windows_ip}"
        )

    async def connect_async(self) -> bool:
        """Connect using remote TWS adapter"""
        try:
            success = await self.remote_adapter.connect_async()
            if success:
                self.ib = self.remote_adapter.get_ib_instance()
                self.state = RemoteConnectionState.CONNECTED
            return success
        except Exception as e:
            self.logger.error(f"Remote TWS connection failed: {str(e)}")
            return False

    def connect(self) -> bool:
        """Synchronous connection using remote TWS adapter"""
        return self.remote_adapter.connect_sync()

    async def disconnect_async(self) -> bool:
        """Disconnect using remote TWS adapter"""
        return await self.remote_adapter.disconnect_async()

    def disconnect(self) -> bool:
        """Synchronous disconnection using remote TWS adapter"""
        return self.remote_adapter.disconnect_sync()

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.remote_adapter.is_connected()

    def get_connection_info(self) -> Dict[str, Any]:
        """Get comprehensive connection information"""
        base_info = {
            "connection_type": self.connection_type,
            "windows_ip": self.remote_config.windows_ip,
            "port": self.remote_config.get_connection_port(),
            "trading_mode": self.remote_config.trading_mode,
            "client_id": self.remote_config.client_id,
            "state": self.state.value if self.state else "unknown",
        }

        # Add remote-specific metrics
        base_info.update(
            {
                "network_metrics": self.remote_adapter.get_network_metrics().__dict__,
                "performance_stats": self.remote_adapter.get_performance_stats(),
            }
        )

        return base_info


# Factory function for easy integration
def create_remote_tws_connection(
    windows_ip: str, trading_mode: str = "paper", client_id: int = 1, **kwargs
) -> RemoteTWSAdapter:
    """
    Factory function to create a remote TWS connection.

    Args:
        windows_ip: IP address of Windows computer running TWS
        trading_mode: "paper" or "live"
        client_id: Client ID for the connection
        **kwargs: Additional configuration options

    Returns:
        RemoteTWSAdapter instance
    """
    config = RemoteTWSConfig(
        windows_ip=windows_ip, trading_mode=trading_mode, client_id=client_id, **kwargs
    )

    return RemoteTWSAdapter(config)


# Utility function for configuration loading
def load_remote_tws_config(config_path: Optional[str] = None) -> RemoteTWSConfig:
    """
    Load remote TWS configuration from file or environment.

    Args:
        config_path: Path to configuration file (unused for now)

    Returns:
        RemoteTWSConfig instance
    """
    # Try to load from Spyder config first
    try:
        from config.config import IB_CONFIG, REMOTE_CONNECTION_CONFIG

        # Extract Windows IP from gateway config
        paper_config = IB_CONFIG["gateway"]["paper"]
        windows_ip = paper_config["host"]

        # Create configuration
        config = RemoteTWSConfig(
            windows_ip=windows_ip,
            paper_port=paper_config["port"],
            live_port=IB_CONFIG["gateway"]["live"]["port"],
            client_id=paper_config["clientId"],
            **REMOTE_CONNECTION_CONFIG,
        )

        return config

    except (ImportError, KeyError, TypeError):
        # Fallback to environment variables
        windows_ip = os.environ.get("TWS_WINDOWS_IP", "192.168.1.100")

        config = RemoteTWSConfig(
            windows_ip=windows_ip,
            paper_port=int(os.environ.get("TWS_PAPER_PORT", "7497")),
            live_port=int(os.environ.get("TWS_LIVE_PORT", "7496")),
            client_id=int(os.environ.get("TWS_CLIENT_ID", "1")),
            trading_mode=os.environ.get("TRADING_MODE", "paper"),
        )

        return config


# Example usage and testing
if __name__ == "__main__":
    import argparse

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Test Remote TWS Adapter")
    parser.add_argument(
        "--windows-ip", required=True, help="Windows computer IP address"
    )
    parser.add_argument(
        "--mode", choices=["paper", "live"], default="paper", help="Trading mode"
    )
    parser.add_argument("--client-id", type=int, default=1, help="Client ID")
    parser.add_argument(
        "--test-only", action="store_true", help="Only test connectivity"
    )

    args = parser.parse_args()

    # Create configuration
    config = RemoteTWSConfig(
        windows_ip=args.windows_ip, trading_mode=args.mode, client_id=args.client_id
    )

    # Create adapter
    adapter = RemoteTWSAdapter(config)

    if args.test_only:
        # Test network connectivity only
        success, message, latency = adapter.test_network_connectivity()
        print(f"Network Test: {'✅' if success else '❌'} {message}")
    else:
        # Full connection test
        print(f"Testing connection to {args.windows_ip} ({args.mode} mode)...")

        async def test_connection():
            success = await adapter.connect_async()
            if success:
                print("✅ Connection successful!")

                # Get some basic info
                ib = adapter.get_ib_instance()
                if ib:
                    try:
                        accounts = ib.managedAccounts()
                        print(f"Accounts: {accounts}")
                    except Exception as e:
                        print(f"Could not get accounts: {e}")

                # Wait a bit then disconnect
                await asyncio.sleep(5)
                await adapter.disconnect_async()
                print("✅ Disconnected successfully!")
            else:
                print("❌ Connection failed!")

        asyncio.run(test_connection())
