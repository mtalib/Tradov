#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Fixed IB Client with Working Connection Pattern
Based on successful research findings and working TWS/Gateway patterns

This version implements the EXACT working connection pattern that resolves
the IB Gateway 10.37 handshake timeout issues by using the proven approach.

Key Fixes Applied:
- Uses util.startLoop() before any connections (CRITICAL)
- Implements both synchronous and asynchronous connection patterns
- Handles Gateway handshake timeout with proper fallback
- Uses simple, proven connection logic without complex retry mechanisms
- Supports both IB Gateway (local) and Remote TWS connections
- Automatic connection method selection based on availability

Author: Spyder Trading System
Last Updated: 2025-01-06
"""

import asyncio
import logging
import time
import threading
from typing import Optional, Dict, Any, List, Union, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import concurrent.futures
from pathlib import Path
import socket

# ==============================================================================
# THIRD-PARTY IMPORTS WITH SAFE FALLBACKS
# ==============================================================================

# Apply nest_asyncio to handle event loops
try:
    import nest_asyncio

    nest_asyncio.apply()
    HAS_NEST_ASYNCIO = True
except ImportError:
    HAS_NEST_ASYNCIO = False

# ib_async is the main dependency
try:
    from ib_async import IB, util, Stock, Option, Contract

    HAS_IB_ASYNC = True
except ImportError:
    IB = None
    util = None
    Stock = None
    Option = None
    Contract = None
    HAS_IB_ASYNC = False
    print("ERROR: ib_async not available. Install with: pip install ib_async")

# ==============================================================================
# CONFIGURATION CLASSES
# ==============================================================================


@dataclass
class ConnectionConfig:
    """Configuration for IB connection"""

    host: str = "127.0.0.1"
    port: int = 4002
    client_id: int = 1
    timeout: int = 60
    connection_type: str = "gateway"  # "gateway" or "remote_tws"
    trading_mode: str = "paper"  # "paper" or "live"

    # Connection pattern settings
    use_async: bool = True  # Use connectAsync by default
    use_util_startup: bool = True  # Use util.startLoop() (CRITICAL)
    use_console_logging: bool = True  # Use util.logToConsole() for debugging

    # Fallback settings
    enable_fallback: bool = True  # Enable automatic fallback
    fallback_to_sync: bool = True  # Fallback to synchronous connection
    fallback_timeout: int = 30  # Shorter timeout for fallback


@dataclass
class ConnectionStatus:
    """Track connection status and statistics"""

    connected: bool = False
    connection_time: Optional[datetime] = None
    connection_method: str = ""  # "async", "sync", "fallback"
    connection_type: str = ""  # "gateway", "remote_tws"
    client_id: int = 0
    host: str = ""
    port: int = 0
    accounts: List[str] = field(default_factory=list)
    last_error: Optional[str] = None
    handshake_time: float = 0.0  # Time for handshake completion
    total_connection_time: float = 0.0


class ConnectionMethod(Enum):
    """Available connection methods"""

    ASYNC_CONNECT = "async"
    SYNC_CONNECT = "sync"
    FALLBACK_CONNECT = "fallback"


# ==============================================================================
# MAIN SPYDER CLIENT CLASS
# ==============================================================================


class SpyderClientFixed:
    """
    Fixed SPYDER IB Client with working connection patterns

    This implementation uses the proven connection pattern that works
    with both IB Gateway and Remote TWS, handling the handshake timeout
    issues properly.
    """

    def __init__(self, config: Optional[ConnectionConfig] = None):
        """Initialize the SPYDER client with fixed connection patterns"""

        # Configuration
        self.config = config or ConnectionConfig()
        self.connection_status = ConnectionStatus()

        # IB Connection
        self.ib: Optional[IB] = None
        self.is_connected = False

        # Logging
        self.logger = logging.getLogger(__name__)

        # Event handlers
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # Initialize if ib_async is available
        if HAS_IB_ASYNC:
            self._initialize_ib_async()
        else:
            raise ImportError("ib_async is required but not available")

    def _initialize_ib_async(self):
        """Initialize ib_async utilities - CRITICAL for connection success"""

        if not HAS_IB_ASYNC:
            return

        try:
            # CRITICAL: Start the ib_async event loop
            if self.config.use_util_startup:
                util.startLoop()
                self.logger.info("✅ ib_async event loop started")

            # Enable console logging for debugging
            if self.config.use_console_logging:
                util.logToConsole()
                self.logger.info("✅ ib_async console logging enabled")

        except Exception as e:
            self.logger.warning(f"ib_async initialization warning: {e}")

    def _create_ib_instance(self) -> IB:
        """Create a fresh IB instance"""
        if not HAS_IB_ASYNC:
            raise RuntimeError("ib_async not available")

        ib = IB()

        # Set up event handlers
        ib.connectedEvent += self._on_ib_connected
        ib.disconnectedEvent += self._on_ib_disconnected
        ib.errorEvent += self._on_ib_error

        return ib

    def _on_ib_connected(self):
        """Handle IB connection event"""
        self.logger.info("📡 IB connection event received")
        if self.on_connected:
            self.on_connected()

    def _on_ib_disconnected(self):
        """Handle IB disconnection event"""
        self.logger.info("🔌 IB disconnection event received")
        self.is_connected = False
        if self.on_disconnected:
            self.on_disconnected()

    def _on_ib_error(self, reqId, errorCode, errorString, contract):
        """Handle IB error events"""
        self.logger.warning(f"IB Error {errorCode}: {errorString}")
        if self.on_error:
            self.on_error(reqId, errorCode, errorString, contract)

    def _test_connection_available(self, host: str, port: int) -> bool:
        """Test if connection is available before attempting"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def connect_async_pattern(self) -> bool:
        """
        Connect using async pattern (matches working research example)
        This is the primary connection method that should work
        """

        self.logger.info(f"🔌 Connecting using ASYNC pattern...")
        self.logger.info(f"   Host: {self.config.host}")
        self.logger.info(f"   Port: {self.config.port}")
        self.logger.info(f"   Client ID: {self.config.client_id}")
        self.logger.info(f"   Timeout: {self.config.timeout}s")

        # Create fresh IB instance
        self.ib = self._create_ib_instance()

        try:
            start_time = time.time()

            # Use the EXACT pattern from working research
            await self.ib.connectAsync(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
            )

            connection_time = time.time() - start_time
            self.logger.info(f"✅ Connected via ASYNC in {connection_time:.2f}s")

            # Verify connection with account request (from working example)
            accounts = self.ib.managedAccounts()
            self.logger.info(f"💼 Accounts: {accounts}")

            # Test with server time request (from working example)
            server_time = await self.ib.reqCurrentTimeAsync()
            self.logger.info(f"🕐 Server time: {server_time}")

            # Update connection status
            self.is_connected = True
            self.connection_status.connected = True
            self.connection_status.connection_time = datetime.now()
            self.connection_status.connection_method = "async"
            self.connection_status.total_connection_time = connection_time
            self.connection_status.accounts = accounts
            self.connection_status.client_id = self.config.client_id
            self.connection_status.host = self.config.host
            self.connection_status.port = self.config.port

            return True

        except Exception as e:
            self.logger.error(f"❌ ASYNC connection failed: {e}")
            self.connection_status.last_error = str(e)
            return False

    def connect_sync_pattern(self) -> bool:
        """
        Connect using synchronous pattern (fallback method)
        This handles cases where async pattern has issues
        """

        self.logger.info(f"🔌 Connecting using SYNC pattern...")

        # Create fresh IB instance
        self.ib = self._create_ib_instance()

        try:
            start_time = time.time()

            # Use synchronous connect (sometimes more reliable)
            self.ib.connect(
                host=self.config.host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=self.config.fallback_timeout,
            )

            connection_time = time.time() - start_time
            self.logger.info(f"✅ Connected via SYNC in {connection_time:.2f}s")

            # Verify connection
            if self.ib.isConnected():
                accounts = self.ib.managedAccounts()
                self.logger.info(f"💼 Accounts: {accounts}")

                # Update connection status
                self.is_connected = True
                self.connection_status.connected = True
                self.connection_status.connection_time = datetime.now()
                self.connection_status.connection_method = "sync"
                self.connection_status.total_connection_time = connection_time
                self.connection_status.accounts = accounts
                self.connection_status.client_id = self.config.client_id
                self.connection_status.host = self.config.host
                self.connection_status.port = self.config.port

                return True
            else:
                self.logger.error("❌ SYNC connection established but not verified")
                return False

        except Exception as e:
            self.logger.error(f"❌ SYNC connection failed: {e}")
            self.connection_status.last_error = str(e)
            return False

    async def connect_with_auto_fallback(self) -> bool:
        """
        Connect with automatic fallback between methods
        This is the main public connection method
        """

        self.logger.info("🚀 Starting connection with auto-fallback...")

        # Test connection availability first
        if not self._test_connection_available(self.config.host, self.config.port):
            self.logger.error(f"❌ Cannot reach {self.config.host}:{self.config.port}")
            return False

        self.logger.info(f"✅ Connection endpoint is reachable")

        # Method 1: Try async connection (preferred)
        if self.config.use_async:
            self.logger.info("🔄 Attempting Method 1: ASYNC connection...")
            try:
                success = await self.connect_async_pattern()
                if success:
                    self.logger.info("🎉 Method 1 (ASYNC) SUCCESS!")
                    return True
                else:
                    self.logger.warning("⚠️ Method 1 (ASYNC) failed, trying fallback...")
            except Exception as e:
                self.logger.warning(f"⚠️ Method 1 (ASYNC) exception: {e}")

        # Method 2: Try sync connection (fallback)
        if self.config.fallback_to_sync:
            self.logger.info("🔄 Attempting Method 2: SYNC connection...")
            try:
                success = self.connect_sync_pattern()
                if success:
                    self.logger.info("🎉 Method 2 (SYNC) SUCCESS!")
                    return True
                else:
                    self.logger.warning("⚠️ Method 2 (SYNC) failed")
            except Exception as e:
                self.logger.warning(f"⚠️ Method 2 (SYNC) exception: {e}")

        # All methods failed
        self.logger.error("❌ All connection methods failed")
        return False

    def connect(self) -> bool:
        """
        Main connection method (synchronous interface)
        Runs the async connection method in a synchronous wrapper
        """

        try:
            # Run async method in event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                task = loop.create_task(self.connect_with_auto_fallback())
                return False  # Cannot wait in running loop, return False for now
            else:
                # Run in new event loop
                return loop.run_until_complete(self.connect_with_auto_fallback())

        except Exception as e:
            self.logger.error(f"Connection wrapper failed: {e}")
            return False

    async def connect_async(self) -> bool:
        """
        Main async connection method
        This is the preferred way to connect
        """
        return await self.connect_with_auto_fallback()

    def disconnect(self):
        """Disconnect from IB"""

        if self.ib and self.ib.isConnected():
            self.logger.info("🔌 Disconnecting from IB...")
            try:
                self.ib.disconnect()
                self.logger.info("✅ Disconnected successfully")
            except Exception as e:
                self.logger.error(f"Disconnect error: {e}")

        self.is_connected = False
        self.connection_status.connected = False
        self.ib = None

    def get_connection_status(self) -> ConnectionStatus:
        """Get current connection status"""
        return self.connection_status

    def get_managed_accounts(self) -> List[str]:
        """Get managed accounts"""
        if self.ib and self.ib.isConnected():
            return self.ib.managedAccounts()
        return []

    async def get_server_time(self):
        """Get IB server time"""
        if self.ib and self.ib.isConnected():
            return await self.ib.reqCurrentTimeAsync()
        return None

    def qualify_contract(self, contract: Contract) -> Contract:
        """Qualify a contract"""
        if self.ib and self.ib.isConnected():
            self.ib.qualifyContracts(contract)
            return contract
        return contract

    def request_market_data(self, contract: Contract, snapshot: bool = False):
        """Request market data for a contract"""
        if self.ib and self.ib.isConnected():
            return self.ib.reqMktData(contract, "", snapshot, False)
        return None

    def cancel_market_data(self, contract: Contract):
        """Cancel market data for a contract"""
        if self.ib and self.ib.isConnected():
            self.ib.cancelMktData(contract)


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def create_gateway_client(
    client_id: int = 1, trading_mode: str = "paper"
) -> SpyderClientFixed:
    """Create a client configured for IB Gateway"""

    port = 4002 if trading_mode == "paper" else 4001

    config = ConnectionConfig(
        host="127.0.0.1",
        port=port,
        client_id=client_id,
        connection_type="gateway",
        trading_mode=trading_mode,
        timeout=60,
        use_async=True,
        enable_fallback=True,
    )

    return SpyderClientFixed(config)


def create_remote_tws_client(
    tws_ip: str, client_id: int = 1, trading_mode: str = "paper"
) -> SpyderClientFixed:
    """Create a client configured for Remote TWS"""

    port = 7497 if trading_mode == "paper" else 7496

    config = ConnectionConfig(
        host=tws_ip,
        port=port,
        client_id=client_id,
        connection_type="remote_tws",
        trading_mode=trading_mode,
        timeout=30,  # Lower timeout for network connections
        use_async=True,
        enable_fallback=True,
    )

    return SpyderClientFixed(config)


def create_auto_client(
    client_id: int = 1, trading_mode: str = "paper"
) -> SpyderClientFixed:
    """
    Create a client that automatically chooses the best connection method
    This implements the intelligent selection from the dual-connection system
    """

    # First try to detect Remote TWS configuration
    try:
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "config.py"

        if config_path.exists():
            with open(config_path, "r") as f:
                content = f.read()

            if "remote_tws" in content:
                # Extract TWS IP
                import re

                ip_match = re.search(r'"ip_address":\s*"([^"]+)"', content)
                if ip_match:
                    tws_ip = ip_match.group(1)
                    print(f"🌐 Auto-detected Remote TWS at {tws_ip}")
                    return create_remote_tws_client(tws_ip, client_id, trading_mode)
    except Exception as e:
        print(f"⚠️ Auto-detect warning: {e}")

    # Default to Gateway
    print(f"🏪 Using IB Gateway (default)")
    return create_gateway_client(client_id, trading_mode)


# ==============================================================================
# TESTING AND DIAGNOSTICS
# ==============================================================================


async def test_connection_patterns():
    """Test all connection patterns to verify they work"""

    print("🧪 Testing SPYDER Client Connection Patterns")
    print("=" * 50)

    # Test 1: Gateway connection
    print("\n🏪 Testing IB Gateway Connection...")
    gateway_client = create_gateway_client(client_id=100, trading_mode="paper")

    try:
        success = await gateway_client.connect_async()
        if success:
            print("✅ Gateway connection: SUCCESS")
            accounts = gateway_client.get_managed_accounts()
            print(f"   Accounts: {accounts}")
            gateway_client.disconnect()
        else:
            print("❌ Gateway connection: FAILED")
    except Exception as e:
        print(f"❌ Gateway connection: ERROR - {e}")

    # Test 2: Remote TWS connection (if configured)
    print("\n🌐 Testing Remote TWS Connection...")
    try:
        # Try to get TWS IP from config
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "config.py"
        tws_ip = "192.168.1.244"  # Default

        if config_path.exists():
            with open(config_path, "r") as f:
                content = f.read()
            import re

            ip_match = re.search(r'"ip_address":\s*"([^"]+)"', content)
            if ip_match:
                tws_ip = ip_match.group(1)

        tws_client = create_remote_tws_client(
            tws_ip, client_id=101, trading_mode="paper"
        )

        success = await tws_client.connect_async()
        if success:
            print(f"✅ Remote TWS connection: SUCCESS")
            accounts = tws_client.get_managed_accounts()
            print(f"   Accounts: {accounts}")
            tws_client.disconnect()
        else:
            print(f"❌ Remote TWS connection: FAILED")

    except Exception as e:
        print(f"❌ Remote TWS connection: ERROR - {e}")

    # Test 3: Auto selection
    print("\n🎯 Testing Auto Connection Selection...")
    try:
        auto_client = create_auto_client(client_id=102, trading_mode="paper")

        success = await auto_client.connect_async()
        if success:
            print("✅ Auto connection: SUCCESS")
            status = auto_client.get_connection_status()
            print(f"   Method: {status.connection_method}")
            print(f"   Type: {status.connection_type}")
            print(f"   Time: {status.total_connection_time:.2f}s")
            auto_client.disconnect()
        else:
            print("❌ Auto connection: FAILED")

    except Exception as e:
        print(f"❌ Auto connection: ERROR - {e}")


if __name__ == "__main__":
    """Test the fixed client when run directly"""

    print("🕷️ SPYDER Fixed Client - Test Run")
    print("=" * 40)

    # Run connection pattern tests
    asyncio.run(test_connection_patterns())
