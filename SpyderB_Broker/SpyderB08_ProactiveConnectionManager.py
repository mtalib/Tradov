#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Proactive Connection Manager with Dashboard Integration

Author: SPYDER AI System
Created: 2025-10-07
Module: SpyderB08_ProactiveConnectionManager.py

PROACTIVE CONNECTION MANAGEMENT:
==============================
- Aggressive connection establishment and retry logic
- Built-in connection triggering for trading dashboard
- Self-healing connection recovery
- Real-time connection monitoring and diagnostics
- Dashboard-integrated connection controls

This manager can be embedded directly in the trading dashboard
and provides manual connection triggering capabilities.
"""

import asyncio
import logging
import threading
import time
import queue
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Union, Tuple, Set
import json
from pathlib import Path

# Third-party imports
try:
    from ib_async import IB, util, Contract, Order, Ticker

    IB_ASYNC_AVAILABLE = True
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("⚠️  ib_async not available - running in simulation mode")

# GUI imports for dashboard integration
try:
    from PySide6.QtCore import QObject, Signal, QTimer, QThread
    from PySide6.QtWidgets import (
        QWidget,
        QPushButton,
        QLabel,
        QProgressBar,
        QVBoxLayout,
    )

    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False
    print("⚠️  PySide6 not available - GUI integration disabled")

# SPYDER imports
try:
    import sys
    from pathlib import Path

    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    from config.config import get_active_config, ENHANCED_CONNECTION_CONFIG

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    print("⚠️  SPYDER config not available - using defaults")


class ConnectionState(Enum):
    """Connection states for tracking"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    SUSPENDED = "suspended"


class ClientPurpose(Enum):
    """Client purposes for the Universal 8-Client system"""

    ORDER_EXECUTION = "order_execution"
    ADMIN_NEWS = "admin_news"
    CORE_DATA = "core_data"
    SPY_OPTIONS = "spy_options"
    VOLATILITY_INTERNALS = "volatility_internals"
    MAJOR_INDICES = "major_indices"
    EXTENDED_SECTORS = "extended_sectors"
    INTERNATIONAL = "international"


@dataclass
class ConnectionInfo:
    """Information about a client connection"""

    client_id: int
    purpose: ClientPurpose
    symbols: List[str]
    description: str
    state: ConnectionState = ConnectionState.DISCONNECTED
    ib_instance: Optional[Any] = None
    last_connected: Optional[datetime] = None
    connection_attempts: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    is_critical: bool = False
    retry_count: int = 0
    max_retries: int = 10


class ProactiveConnectionManager(QObject if GUI_AVAILABLE else object):
    """
    Proactive connection manager with dashboard integration
    Provides aggressive connection establishment and monitoring
    """

    # Qt signals for dashboard integration
    if GUI_AVAILABLE:
        connection_state_changed = Signal(int, str)  # client_id, state
        connection_progress = Signal(int, int)  # current, total
        error_occurred = Signal(str)  # error message
        all_connected = Signal()  # all clients connected

    def __init__(self, dashboard_widget=None):
        if GUI_AVAILABLE:
            super().__init__()

        # Configuration
        self.dashboard_widget = dashboard_widget
        self.setup_configuration()
        self.setup_logging()

        # Connection tracking
        self.connections: Dict[int, ConnectionInfo] = {}
        self.connection_lock = threading.Lock()
        self.is_running = False
        self.stop_requested = False

        # Proactive features
        self.auto_retry_enabled = True
        self.connection_monitor_enabled = True
        self.aggressive_mode = True

        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=16, thread_name_prefix="SPYDER-Conn"
        )
        self.monitor_thread = None

        # Performance tracking
        self.connection_stats = {
            "total_attempts": 0,
            "successful_connections": 0,
            "failed_connections": 0,
            "recovery_count": 0,
            "start_time": None,
            "last_full_connection": None,
        }

        self.setup_client_configurations()
        self.logger.info("🚀 Proactive Connection Manager initialized")

    def setup_configuration(self):
        """Setup configuration from SPYDER config or defaults"""
        if CONFIG_AVAILABLE:
            config = get_active_config()
            self.host = config.get("host", "127.0.0.1")
            self.port = config.get("port", 4002)
            self.base_client_id = 100
        else:
            # Default configuration
            self.host = "127.0.0.1"
            self.port = 4002
            self.base_client_id = 100

        # Connection settings
        self.connection_timeout = 15.0
        self.retry_delay = 2.0
        self.max_retries = 10
        self.heartbeat_interval = 30.0
        self.race_condition_delay = 1.0

    def setup_logging(self):
        """Setup logging"""
        self.logger = logging.getLogger("SPYDER.ProactiveConnections")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def setup_client_configurations(self):
        """Setup the Universal 8-Client configuration"""
        client_configs = {
            1: {
                "purpose": ClientPurpose.ORDER_EXECUTION,
                "symbols": ["SPY", "QQQ", "IWM", "VXX", "UVXY"],
                "description": "Order Execution & Primary Trading",
                "is_critical": True,
            },
            2: {
                "purpose": ClientPurpose.ADMIN_NEWS,
                "symbols": ["SPY", "QQQ", "IWM", "VIX", "TNX"],
                "description": "Administrative & News Feeds",
                "is_critical": True,
            },
            3: {
                "purpose": ClientPurpose.CORE_DATA,
                "symbols": ["SPY", "SPX", "/ES", "VIX", "/VX"],
                "description": "Core Market Data - 1s updates",
                "is_critical": True,
            },
            4: {
                "purpose": ClientPurpose.SPY_OPTIONS,
                "symbols": [
                    "SPY_OPTIONS_0DTE",
                    "SPY_OPTIONS_1DTE",
                    "SPY_OPTIONS_WEEKLY",
                ],
                "description": "SPY Options Chains - 1s updates",
                "is_critical": False,
            },
            5: {
                "purpose": ClientPurpose.VOLATILITY_INTERNALS,
                "symbols": ["UVXY", "SVXY", "TICK", "TRIN", "ADD", "SKEW"],
                "description": "Volatility + Market Internals - 5s updates",
                "is_critical": False,
            },
            6: {
                "purpose": ClientPurpose.MAJOR_INDICES,
                "symbols": [
                    "DIA",
                    "QQQ",
                    "IWM",
                    "DIA_OPTIONS_1DTE",
                    "QQQ_OPTIONS_1DTE",
                ],
                "description": "Major Indices - 5s updates",
                "is_critical": False,
            },
            7: {
                "purpose": ClientPurpose.EXTENDED_SECTORS,
                "symbols": ["XLF", "XLK", "XLE", "XLV", "TLT", "GLD"],
                "description": "Extended Assets + Sectors - 30s updates",
                "is_critical": False,
            },
            8: {
                "purpose": ClientPurpose.INTERNATIONAL,
                "symbols": ["EFA", "EEM", "FXI", "DAX", "HSI"],
                "description": "International Markets - 60s updates",
                "is_critical": False,
            },
        }

        # Create connection info objects
        for client_num, config in client_configs.items():
            client_id = self.base_client_id + client_num - 1  # 100, 101, 102, etc.

            connection_info = ConnectionInfo(
                client_id=client_id,
                purpose=config["purpose"],
                symbols=config["symbols"],
                description=config["description"],
                is_critical=config["is_critical"],
                max_retries=self.max_retries * 2
                if config["is_critical"]
                else self.max_retries,
            )

            self.connections[client_id] = connection_info

        self.logger.info(
            f"📋 Configured {len(self.connections)} clients for Universal 8-Client system"
        )

    # ================================================================================
    # DASHBOARD INTEGRATION METHODS
    # ================================================================================

    def create_dashboard_widget(self, parent=None):
        """Create a widget for dashboard integration"""
        if not GUI_AVAILABLE:
            return None

        widget = QWidget(parent)
        layout = QVBoxLayout(widget)

        # Status label
        self.status_label = QLabel("Connection Status: Not Started")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(self.connections))
        layout.addWidget(self.progress_bar)

        # Control buttons
        self.connect_button = QPushButton("🚀 Connect All Clients")
        self.connect_button.clicked.connect(self.trigger_connections_from_dashboard)
        layout.addWidget(self.connect_button)

        self.reconnect_button = QPushButton("🔄 Reconnect Failed")
        self.reconnect_button.clicked.connect(self.trigger_reconnect_failed)
        layout.addWidget(self.reconnect_button)

        self.status_button = QPushButton("📊 Show Status")
        self.status_button.clicked.connect(self.show_connection_status)
        layout.addWidget(self.status_button)

        # Connect signals
        if hasattr(self, "connection_progress"):
            self.connection_progress.connect(self.progress_bar.setValue)
            self.connection_state_changed.connect(self.update_status_display)

        return widget

    def trigger_connections_from_dashboard(self):
        """Trigger connection establishment from dashboard button"""
        self.logger.info("🎯 Dashboard triggered connection establishment")

        if self.connect_button:
            self.connect_button.setText("🔄 Connecting...")
            self.connect_button.setEnabled(False)

        # Start connections in background thread
        def run_connections():
            try:
                if IB_ASYNC_AVAILABLE:
                    # Run async connection in thread
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.establish_all_connections())
                else:
                    self.simulate_connections()
            except Exception as e:
                self.logger.error(f"❌ Connection error: {e}")
                if hasattr(self, "error_occurred"):
                    self.error_occurred.emit(str(e))
            finally:
                if self.connect_button:
                    self.connect_button.setText("🚀 Connect All Clients")
                    self.connect_button.setEnabled(True)

        self.executor.submit(run_connections)

    def trigger_reconnect_failed(self):
        """Reconnect only failed connections"""
        failed_clients = [
            client_id
            for client_id, info in self.connections.items()
            if info.state in [ConnectionState.FAILED, ConnectionState.DISCONNECTED]
        ]

        if not failed_clients:
            self.logger.info("✅ No failed connections to reconnect")
            return

        self.logger.info(f"🔄 Reconnecting {len(failed_clients)} failed clients")

        def run_reconnections():
            try:
                if IB_ASYNC_AVAILABLE:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.reconnect_clients(failed_clients))
                else:
                    for client_id in failed_clients:
                        self.connections[client_id].state = ConnectionState.CONNECTED
                        self.logger.info(f"✅ [SIM] Client {client_id} reconnected")
            except Exception as e:
                self.logger.error(f"❌ Reconnection error: {e}")

        self.executor.submit(run_reconnections)

    def update_status_display(self, client_id, state):
        """Update status display when connection state changes"""
        if hasattr(self, "status_label"):
            connected_count = sum(
                1
                for info in self.connections.values()
                if info.state == ConnectionState.CONNECTED
            )
            total_count = len(self.connections)
            self.status_label.setText(
                f"Connected: {connected_count}/{total_count} clients"
            )

    def show_connection_status(self):
        """Show detailed connection status"""
        status_lines = ["📊 Connection Status Report:", "=" * 50]

        for client_id, info in self.connections.items():
            status_icon = {
                ConnectionState.CONNECTED: "✅",
                ConnectionState.CONNECTING: "🔄",
                ConnectionState.DISCONNECTED: "❌",
                ConnectionState.FAILED: "💥",
                ConnectionState.RECONNECTING: "🔁",
            }.get(info.state, "❓")

            status_lines.append(
                f"{status_icon} Client {client_id}: {info.state.value} - {info.description}"
            )
            if info.last_error:
                status_lines.append(f"   Last error: {info.last_error}")

        status_text = "\n".join(status_lines)
        self.logger.info(status_text)
        print(status_text)  # Also print to console

    # ================================================================================
    # CONNECTION ESTABLISHMENT METHODS
    # ================================================================================

    async def establish_all_connections(self):
        """Establish all connections with aggressive retry logic"""
        self.logger.info("🚀 Starting aggressive connection establishment")
        self.connection_stats["start_time"] = datetime.now()

        # Pre-flight checks
        if not await self.pre_flight_checks():
            self.logger.error("❌ Pre-flight checks failed")
            return False

        # Start connections in priority order (critical clients first)
        critical_clients = [
            cid for cid, info in self.connections.items() if info.is_critical
        ]
        normal_clients = [
            cid for cid, info in self.connections.items() if not info.is_critical
        ]

        all_clients = critical_clients + normal_clients

        successful_connections = 0

        for i, client_id in enumerate(all_clients):
            try:
                self.logger.info(
                    f"🔌 Connecting client {client_id} ({i + 1}/{len(all_clients)})"
                )

                if hasattr(self, "connection_progress"):
                    self.connection_progress.emit(i + 1)

                success = await self.establish_single_connection(client_id)
                if success:
                    successful_connections += 1

                # Race condition delay
                await asyncio.sleep(self.race_condition_delay)

            except Exception as e:
                self.logger.error(f"❌ Error connecting client {client_id}: {e}")
                self.connections[client_id].state = ConnectionState.FAILED
                self.connections[client_id].last_error = str(e)

        # Summary
        self.logger.info(
            f"📊 Connection summary: {successful_connections}/{len(all_clients)} successful"
        )

        if successful_connections == len(all_clients):
            self.connection_stats["last_full_connection"] = datetime.now()
            if hasattr(self, "all_connected"):
                self.all_connected.emit()

        return successful_connections > 0

    async def establish_single_connection(self, client_id: int) -> bool:
        """Establish a single client connection with retry logic"""
        connection_info = self.connections[client_id]
        connection_info.state = ConnectionState.CONNECTING

        if hasattr(self, "connection_state_changed"):
            self.connection_state_changed.emit(client_id, connection_info.state.value)

        max_attempts = connection_info.max_retries

        for attempt in range(1, max_attempts + 1):
            try:
                self.logger.info(
                    f"🔌 Client {client_id} connection attempt {attempt}/{max_attempts}"
                )
                connection_info.connection_attempts += 1
                self.connection_stats["total_attempts"] += 1

                # Create IB instance
                ib = IB()
                ib.RequestTimeout = self.connection_timeout

                # Attempt connection
                await ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=client_id,
                    timeout=self.connection_timeout,
                    readonly=False,  # We need full access for trading
                )

                # Success!
                connection_info.ib_instance = ib
                connection_info.state = ConnectionState.CONNECTED
                connection_info.last_connected = datetime.now()
                connection_info.error_count = 0
                connection_info.last_error = None

                self.connection_stats["successful_connections"] += 1

                self.logger.info(f"✅ Client {client_id} connected successfully")

                if hasattr(self, "connection_state_changed"):
                    self.connection_state_changed.emit(
                        client_id, connection_info.state.value
                    )

                return True

            except Exception as e:
                connection_info.error_count += 1
                connection_info.last_error = str(e)

                self.logger.warning(
                    f"⚠️  Client {client_id} attempt {attempt} failed: {e}"
                )

                if attempt < max_attempts:
                    delay = self.retry_delay * attempt  # Exponential backoff
                    self.logger.info(f"⏳ Retrying client {client_id} in {delay}s...")
                    await asyncio.sleep(delay)

        # All attempts failed
        connection_info.state = ConnectionState.FAILED
        self.connection_stats["failed_connections"] += 1

        self.logger.error(f"❌ Client {client_id} failed after {max_attempts} attempts")

        if hasattr(self, "connection_state_changed"):
            self.connection_state_changed.emit(client_id, connection_info.state.value)

        return False

    async def reconnect_clients(self, client_ids: List[int]):
        """Reconnect specific clients"""
        for client_id in client_ids:
            connection_info = self.connections[client_id]

            # Disconnect existing connection if any
            if connection_info.ib_instance:
                try:
                    connection_info.ib_instance.disconnect()
                except:
                    pass
                connection_info.ib_instance = None

            # Reset state
            connection_info.state = ConnectionState.RECONNECTING
            connection_info.retry_count += 1

            # Attempt reconnection
            success = await self.establish_single_connection(client_id)
            if success:
                self.connection_stats["recovery_count"] += 1

    async def pre_flight_checks(self) -> bool:
        """Perform pre-flight checks before connecting"""
        self.logger.info("🔍 Performing pre-flight checks...")

        # Check if IB Gateway port is accessible
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()

            if result != 0:
                self.logger.error(f"❌ Cannot connect to {self.host}:{self.port}")
                return False

            self.logger.info(f"✅ Port {self.port} is accessible")
            return True

        except Exception as e:
            self.logger.error(f"❌ Port check failed: {e}")
            return False

    def simulate_connections(self):
        """Simulate connections when IB API is not available"""
        self.logger.info("🎭 Simulating connections for testing")

        for client_id, connection_info in self.connections.items():
            connection_info.state = ConnectionState.CONNECTED
            connection_info.last_connected = datetime.now()

            if hasattr(self, "connection_state_changed"):
                self.connection_state_changed.emit(
                    client_id, connection_info.state.value
                )

            time.sleep(0.1)  # Simulate connection time

        self.logger.info("✅ All connections simulated successfully")

        if hasattr(self, "all_connected"):
            self.all_connected.emit()

    # ================================================================================
    # MONITORING AND MAINTENANCE
    # ================================================================================

    def start_connection_monitor(self):
        """Start background connection monitoring"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return

        self.monitor_thread = threading.Thread(
            target=self._monitor_connections, daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("👁️  Connection monitor started")

    def _monitor_connections(self):
        """Monitor connections in background thread"""
        while not self.stop_requested:
            try:
                disconnected_clients = []

                for client_id, connection_info in self.connections.items():
                    if (
                        connection_info.state == ConnectionState.CONNECTED
                        and connection_info.ib_instance
                        and not connection_info.ib_instance.isConnected()
                    ):
                        self.logger.warning(
                            f"⚠️  Client {client_id} disconnected - queuing for reconnect"
                        )
                        connection_info.state = ConnectionState.DISCONNECTED
                        disconnected_clients.append(client_id)

                # Trigger reconnection for disconnected clients
                if disconnected_clients and self.auto_retry_enabled:
                    self.executor.submit(
                        self._reconnect_in_thread, disconnected_clients
                    )

                time.sleep(self.heartbeat_interval)

            except Exception as e:
                self.logger.error(f"❌ Monitor error: {e}")
                time.sleep(5)

    def _reconnect_in_thread(self, client_ids):
        """Reconnect clients in separate thread"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.reconnect_clients(client_ids))
        except Exception as e:
            self.logger.error(f"❌ Background reconnection failed: {e}")

    # ================================================================================
    # UTILITY METHODS
    # ================================================================================

    def get_connection_summary(self) -> Dict:
        """Get summary of all connections"""
        summary = {
            "total_clients": len(self.connections),
            "connected": 0,
            "connecting": 0,
            "failed": 0,
            "disconnected": 0,
            "critical_connected": 0,
            "critical_total": 0,
        }

        for connection_info in self.connections.values():
            if connection_info.is_critical:
                summary["critical_total"] += 1
                if connection_info.state == ConnectionState.CONNECTED:
                    summary["critical_connected"] += 1

            if connection_info.state == ConnectionState.CONNECTED:
                summary["connected"] += 1
            elif connection_info.state == ConnectionState.CONNECTING:
                summary["connecting"] += 1
            elif connection_info.state == ConnectionState.FAILED:
                summary["failed"] += 1
            else:
                summary["disconnected"] += 1

        return summary

    def is_fully_connected(self) -> bool:
        """Check if all clients are connected"""
        return all(
            info.state == ConnectionState.CONNECTED
            for info in self.connections.values()
        )

    def is_critically_connected(self) -> bool:
        """Check if all critical clients are connected"""
        return all(
            info.state == ConnectionState.CONNECTED
            for info in self.connections.values()
            if info.is_critical
        )

    def shutdown(self):
        """Shutdown the connection manager"""
        self.logger.info("🛑 Shutting down Proactive Connection Manager")

        self.stop_requested = True

        # Disconnect all clients
        for connection_info in self.connections.values():
            if connection_info.ib_instance:
                try:
                    connection_info.ib_instance.disconnect()
                except:
                    pass

        # Shutdown executor
        self.executor.shutdown(wait=True)

        self.logger.info("✅ Proactive Connection Manager shutdown complete")


# ================================================================================
# STANDALONE TESTING
# ================================================================================


def main():
    """Test the proactive connection manager"""
    print("🕷️  SPYDER - Proactive Connection Manager Test")
    print("=" * 60)

    # Create manager
    manager = ProactiveConnectionManager()

    # Test connection establishment
    if IB_ASYNC_AVAILABLE:
        print("🚀 Testing real IB API connections...")

        async def test_connections():
            success = await manager.establish_all_connections()
            print(f"Connection test result: {'✅ SUCCESS' if success else '❌ FAILED'}")

            # Show summary
            summary = manager.get_connection_summary()
            print(f"\n📊 Connection Summary:")
            print(f"   Connected: {summary['connected']}/{summary['total_clients']}")
            print(
                f"   Critical: {summary['critical_connected']}/{summary['critical_total']}"
            )

            return success

        # Run test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(test_connections())

    else:
        print("🎭 Testing simulation mode...")
        manager.simulate_connections()

        summary = manager.get_connection_summary()
        print(f"📊 Simulation Summary:")
        print(f"   Connected: {summary['connected']}/{summary['total_clients']}")
        result = True

    # Cleanup
    manager.shutdown()

    return 0 if result else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
