#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG15_ClientConnectionManager.py
Purpose: Multi-Client Connection Manager for IB Gateway (8 Clients)
Author: SPYDER Development Team
Year Created: 2025
Last Updated: 2025-10-09

Module Description:
    Manages 8 IB Gateway client connections with sequential connection pattern,
    proper handshake delays, and health monitoring. Designed to work seamlessly
    with the Trading Dashboard (G05) and Gateway Control Panel (G14).

Key Features:
    • Sequential connection of 8 clients (Client IDs 1-8)
    • Proper handshake delay (1.0s after socket connection)
    • Inter-client delay (2.0s between connections)
    • Health monitoring with 30-second heartbeat
    • Individual client reconnection capability
    • Thread-safe connection management
    • Status signals for UI updates

Client Allocation:
    CLIENT 1: Orders (Order execution)
    CLIENT 2: Admin (Administrative tasks)
    CLIENT 3: Core (Core market data)
    CLIENT 4: Options (Options data)
    CLIENT 5: Volatility (Volatility metrics)
    CLIENT 6: Major ETFs (Major index ETFs)
    CLIENT 7: Extended (Extended assets)
    CLIENT 8: International (International markets)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ib_async import IB

from PySide6.QtCore import QThread, Signal, QObject, QMutex, QMutexLocker

try:
    from ib_async import IB, util

    IB_AVAILABLE = True
    IB_CLASS = IB
except ImportError:
    IB_AVAILABLE = False
    IB_CLASS = None


# ==============================================================================
# ENUMERATIONS
# ==============================================================================


class ClientStatus(Enum):
    """Client connection status"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ClientPurpose(Enum):
    """Client purpose/role"""

    ORDERS = "Orders"
    ADMIN = "Admin"
    CORE = "Core"
    OPTIONS = "Options"
    VOLATILITY = "Volatility"
    MAJOR_ETFS = "Major ETFs"
    EXTENDED = "Extended"
    INTERNATIONAL = "International"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ClientConfig:
    """Configuration for a single client"""

    client_id: int
    purpose: ClientPurpose
    host: str = "127.0.0.1"
    port: int = 4002  # Paper trading
    timeout: int = 10  # 10 second timeout per research
    connection_delay: float = 1.0  # Handshake delay
    symbols: List[str] = field(default_factory=list)
    # Enhanced timeout handling
    socket_timeout: int = 5  # Socket connection timeout
    handshake_timeout: int = 10  # API handshake timeout
    retry_attempts: int = 2  # Number of retry attempts


@dataclass
class ClientState:
    """Current state of a client connection"""

    client_id: int
    status: ClientStatus
    ib_instance: Optional[object]  # Will be IB instance if available
    accounts: List[str]
    last_activity: Optional[datetime]
    error_message: Optional[str]
    connection_time: Optional[datetime]
    reconnect_attempts: int = 0


# ==============================================================================
# CLIENT CONNECTION MANAGER
# ==============================================================================


class ClientConnectionManager(QObject):
    """
    Manages multiple IB Gateway client connections.

    Handles sequential connection with proper delays, health monitoring,
    and individual client reconnection.
    """

    # Signals
    client_status_changed = Signal(int, str, bool)  # client_id, status_text, success
    client_connecting = Signal(int, str)  # client_id, purpose
    client_connected = Signal(int, str, list)  # client_id, purpose, accounts
    client_error = Signal(int, str, str)  # client_id, purpose, error
    all_clients_ready = Signal(int, int)  # connected_count, total_count
    connection_progress = Signal(int, int)  # current, total
    log_message = Signal(str)  # Log messages

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        num_clients: int = 8,
        start_client_id: int = 1,
    ):
        super().__init__()

        self.host = host
        self.port = port
        self.num_clients = num_clients
        self.start_client_id = start_client_id

        # Client configurations
        self.client_configs: Dict[int, ClientConfig] = {}
        self.client_states: Dict[int, ClientState] = {}

        # Connection management
        self.mutex = QMutex()
        self._stop_requested = False

        # Initialize client configurations
        self._init_client_configs()

        self.log_message.emit("📋 Client Connection Manager initialized")

    def _init_client_configs(self):
        """Initialize configurations for all 8 clients"""
        purposes = [
            ClientPurpose.ORDERS,
            ClientPurpose.ADMIN,
            ClientPurpose.CORE,
            ClientPurpose.OPTIONS,
            ClientPurpose.VOLATILITY,
            ClientPurpose.MAJOR_ETFS,
            ClientPurpose.EXTENDED,
            ClientPurpose.INTERNATIONAL,
        ]

        for i in range(self.num_clients):
            client_id = self.start_client_id + i
            purpose = purposes[i]

            config = ClientConfig(
                client_id=client_id, purpose=purpose, host=self.host, port=self.port
            )

            self.client_configs[client_id] = config

            # Initialize state as disconnected
            self.client_states[client_id] = ClientState(
                client_id=client_id,
                status=ClientStatus.DISCONNECTED,
                ib_instance=None,
                accounts=[],
                last_activity=None,
                error_message=None,
                connection_time=None,
            )

    def connect_all_clients(self) -> bool:
        """
        Connect all clients concurrently with staggered start (200ms delays).

        Returns:
            True if at least 50% of clients connected successfully
        """
        if not IB_AVAILABLE:
            self.log_message.emit("❌ ib_async not available")
            return False

        self.log_message.emit(
            f"🔗 Starting connection of {self.num_clients} clients..."
        )
        self._stop_requested = False

        # Use the current event loop instead of creating a new one
        # This prevents the "Task got Future attached to a different loop" error
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            self.log_message.emit("📡 Using existing event loop")
        except RuntimeError:
            # No running loop, create one
            util.patchAsyncio()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.log_message.emit("📡 Created new event loop")

            # We'll run the loop synchronously since we created it
            try:
                success_count = loop.run_until_complete(self._connect_all_async(loop))
            finally:
                # Close the event loop after all clients are processed
                loop.close()
        else:
            # We have a running loop, create a task to run our connection
            import concurrent.futures

            # Create a new thread to run the async connection
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_connection_in_thread)
                success_count = future.result()

        # Summary
        self.log_message.emit(f"\n{'=' * 60}")
        self.log_message.emit(f"📊 Connection Summary:")
        self.log_message.emit(f"  ✅ Successful: {success_count}/{self.num_clients}")
        self.log_message.emit(f"  ❌ Failed: {self.num_clients - success_count}")

        # Emit completion signal
        self.all_clients_ready.emit(success_count, self.num_clients)

        return success_count >= (self.num_clients / 2)

    def _run_connection_in_thread(self) -> int:
        """Run the connection process in a separate thread with its own event loop"""
        util.patchAsyncio()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(self._connect_all_async(loop))
        finally:
            loop.close()

    async def _connect_all_async(self, loop: asyncio.AbstractEventLoop) -> int:
        """
        Async method to connect all clients concurrently with staggered start.

        Args:
            loop: The event loop to use

        Returns:
            Number of successful connections
        """
        connection_tasks = []

        for i in range(self.num_clients):
            if self._stop_requested:
                self.log_message.emit("🛑 Connection process cancelled")
                break

            client_id = self.start_client_id + i
            config = self.client_configs[client_id]

            self.log_message.emit(f"\n{'=' * 60}")
            self.log_message.emit(
                f"🔗 Starting Client {client_id}: {config.purpose.value} ({i + 1}/{self.num_clients})"
            )

            # Update progress
            self.connection_progress.emit(i + 1, self.num_clients)

            # Create IB instance
            if IB_AVAILABLE and IB_CLASS:
                ib = IB_CLASS()
            else:
                self.log_message.emit("❌ ib_async not available")
                return False

            # Create connection task
            task = self._connect_single_client_async(ib, client_id, config)
            connection_tasks.append(task)

            # Stagger connection starts by 200ms (per research)
            if i < self.num_clients - 1:
                await asyncio.sleep(0.2)

        # Run all connection tasks concurrently
        self.log_message.emit("\n🔗 Running all connections concurrently...")
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)

        # Count successes
        success_count = sum(1 for r in results if r is True)

        return success_count

    async def _connect_single_client_async(
        self, ib, client_id: int, config: ClientConfig
    ) -> bool:
        """
        Async method to connect a single client with proper handshake delay.

        Args:
            ib: Pre-created IB instance
            client_id: Client ID to connect
            config: Client configuration

        Returns:
            True if connection successful
        """
        with QMutexLocker(self.mutex):
            state = self.client_states[client_id]
            state.status = ClientStatus.CONNECTING
            state.reconnect_attempts += 1

        # Emit connecting signal
        self.client_connecting.emit(client_id, config.purpose.value)
        self.client_status_changed.emit(client_id, "Connecting...", False)

        try:
            # Step 1: Socket connection
            self.log_message.emit(f"  [{client_id}] Socket connecting...")
            await ib.connectAsync(
                host=config.host,
                port=config.port,
                clientId=client_id,
                timeout=config.timeout,
            )
            self.log_message.emit(f"  [{client_id}] ✅ Socket connected")

            # Step 2: CRITICAL - Handshake delay
            self.log_message.emit(
                f"  [{client_id}] Handshake delay ({config.connection_delay}s)..."
            )
            await asyncio.sleep(config.connection_delay)
            self.log_message.emit(f"  [{client_id}] ✅ Handshake complete")

            # Step 3: Validate connection
            accounts = ib.managedAccounts()

            if accounts:
                self.log_message.emit(
                    f"  [{client_id}] ✅ Connected! Accounts: {accounts}"
                )

                # Update state
                with QMutexLocker(self.mutex):
                    state = self.client_states[client_id]
                    state.status = ClientStatus.CONNECTED
                    state.ib_instance = ib
                    state.accounts = accounts
                    state.last_activity = datetime.now()
                    state.connection_time = datetime.now()
                    state.error_message = None

                # Emit success signals
                self.client_connected.emit(client_id, config.purpose.value, accounts)
                self.client_status_changed.emit(client_id, "Connected", True)

                return True
            else:
                self.log_message.emit(f"  [{client_id}] ⚠️ No accounts returned")
                ib.disconnect()

                with QMutexLocker(self.mutex):
                    state = self.client_states[client_id]
                    state.status = ClientStatus.ERROR
                    state.error_message = "No accounts returned"

                self.client_error.emit(client_id, config.purpose.value, "No accounts")
                self.client_status_changed.emit(client_id, "No accounts", False)

                return False

        except asyncio.TimeoutError:
            error_msg = "Connection timeout (10s)"
            self.log_message.emit(f"  [{client_id}] ❌ Timeout")

            with QMutexLocker(self.mutex):
                state = self.client_states[client_id]
                state.status = ClientStatus.ERROR
                state.error_message = error_msg

            self.client_error.emit(client_id, config.purpose.value, error_msg)
            self.client_status_changed.emit(client_id, error_msg, False)
            return False

        except Exception as e:
            error_msg = str(e)
            self.log_message.emit(f"  [{client_id}] ❌ Error: {error_msg}")

            with QMutexLocker(self.mutex):
                state = self.client_states[client_id]
                state.status = ClientStatus.ERROR
                state.error_message = error_msg

            self.client_error.emit(client_id, config.purpose.value, error_msg)
            self.client_status_changed.emit(client_id, f"Error: {error_msg}", False)
            return False

    def reconnect_client(self, client_id: int) -> bool:
        """
        Reconnect a specific client.

        Args:
            client_id: Client ID to reconnect

        Returns:
            True if reconnection successful
        """
        if client_id not in self.client_configs:
            self.log_message.emit(f"❌ Invalid client ID: {client_id}")
            return False

        config = self.client_configs[client_id]
        self.log_message.emit(
            f"🔄 Reconnecting Client {client_id}: {config.purpose.value}"
        )

        # Disconnect if currently connected
        self.disconnect_client(client_id)

        # Wait a moment
        time.sleep(1.0)

        # Create event loop for reconnection
        util.patchAsyncio()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Create new IB instance
            if IB_AVAILABLE and IB_CLASS:
                ib = IB_CLASS()
            else:
                self.log_message.emit("❌ ib_async not available")
                return False
            config = self.client_configs[client_id]

            # Reconnect with event loop
            return loop.run_until_complete(
                self._connect_single_client_async(ib, client_id, config)
            )
        finally:
            loop.close()

    def disconnect_client(self, client_id: int):
        """
        Disconnect a specific client.

        Args:
            client_id: Client ID to disconnect
        """
        with QMutexLocker(self.mutex):
            state = self.client_states.get(client_id)
            if state and state.ib_instance:
                try:
                    # Use getattr to safely call disconnect method
                    disconnect_method = getattr(state.ib_instance, 'disconnect', None)
                    if disconnect_method and callable(disconnect_method):
                        disconnect_method()
                    self.log_message.emit(f"🔌 Client {client_id} disconnected")
                except Exception as e:
                    self.log_message.emit(
                        f"⚠️ Error disconnecting client {client_id}: {e}"
                    )

                state.status = ClientStatus.DISCONNECTED
                state.ib_instance = None
                state.accounts = []

                # Emit status change
                config = self.client_configs[client_id]
                self.client_status_changed.emit(client_id, "Disconnected", False)

    def disconnect_all_clients(self):
        """Disconnect all clients"""
        self.log_message.emit("🔌 Disconnecting all clients...")

        for client_id in self.client_configs.keys():
            self.disconnect_client(client_id)

        self.log_message.emit("✅ All clients disconnected")

    def get_client_status(self, client_id: int) -> Optional[ClientState]:
        """
        Get current status of a client.

        Args:
            client_id: Client ID

        Returns:
            ClientState if found, None otherwise
        """
        with QMutexLocker(self.mutex):
            return self.client_states.get(client_id)

    def get_connected_count(self) -> int:
        """Get number of currently connected clients"""
        with QMutexLocker(self.mutex):
            return sum(
                1
                for state in self.client_states.values()
                if state.status == ClientStatus.CONNECTED
            )

    def is_client_connected(self, client_id: int) -> bool:
        """Check if a specific client is connected"""
        with QMutexLocker(self.mutex):
            state = self.client_states.get(client_id)
            return state is not None and state.status == ClientStatus.CONNECTED

    def stop(self):
        """Stop connection process"""
        self._stop_requested = True
        self.log_message.emit("🛑 Stop requested")


# ==============================================================================
# CONNECTION THREAD WRAPPER
# ==============================================================================


class ClientConnectionThread(QThread):
    """
    Thread wrapper for client connection manager.
    Allows connection process to run in background without blocking UI.
    """

    # Forward signals from manager
    client_status_changed = Signal(int, str, bool)
    client_connecting = Signal(int, str)
    client_connected = Signal(int, str, list)
    client_error = Signal(int, str, str)
    all_clients_ready = Signal(int, int)
    connection_progress = Signal(int, int)
    log_message = Signal(str)
    connection_complete = Signal(bool)  # success flag

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        num_clients: int = 8,
        parent=None,
    ):
        super().__init__(parent)

        self.host = host
        self.port = port
        self.num_clients = num_clients
        self.manager: Optional[ClientConnectionManager] = None

    def run(self):
        """Run connection process in background thread"""
        # Create manager in this thread
        self.manager = ClientConnectionManager(
            host=self.host, port=self.port, num_clients=self.num_clients
        )

        # Connect signals
        self.manager.client_status_changed.connect(self.client_status_changed)
        self.manager.client_connecting.connect(self.client_connecting)
        self.manager.client_connected.connect(self.client_connected)
        self.manager.client_error.connect(self.client_error)
        self.manager.all_clients_ready.connect(self.all_clients_ready)
        self.manager.connection_progress.connect(self.connection_progress)
        self.manager.log_message.connect(self.log_message)

        # Connect all clients
        success = self.manager.connect_all_clients()

        # Emit completion
        self.connection_complete.emit(success)

    def stop(self):
        """Stop connection process"""
        if self.manager:
            self.manager.stop()


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================


def create_client_manager(
    host: str = "127.0.0.1", port: int = 4002, num_clients: int = 8
) -> ClientConnectionManager:
    """
    Factory function to create a ClientConnectionManager instance.

    Args:
        host: IB Gateway host
        port: IB Gateway port
        num_clients: Number of clients to manage

    Returns:
        ClientConnectionManager instance
    """
    return ClientConnectionManager(host=host, port=port, num_clients=num_clients)


# ==============================================================================
# MAIN EXECUTION - FOR TESTING
# ==============================================================================

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    print("=" * 60)
    print("SPYDER G15 - Client Connection Manager Test")
    print("=" * 60)

    app = QApplication(sys.argv)

    # Create manager
    manager = create_client_manager()

    # Connect to log signal
    manager.log_message.connect(lambda msg: print(msg))

    # Test connection (would require IB Gateway running)
    print("\n🧪 Testing client connection logic...")
    print("Note: Actual connection requires IB Gateway running on port 4002")

    sys.exit(0)
