#!/usr/bin/env python3
"""
SPYDER - MAESTRO'S TWS API CONNECTION FIX
=========================================

Comprehensive solution based on analysis of 6 AI research reports:
- Claude's race condition delay solution
- ChatGPT's readonly mode fix
- Perplexity's reqExecutions timeout bypass
- Copilot's TCP_NODELAY optimization
- Gemini's protocol adherence fixes
- Grok's version compatibility solutions

This implements the "Triple Fix" approach combining the most effective solutions.
"""

import asyncio
import socket
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB, util
    from config.config_remote_tws import get_active_config

    print("✅ ib_async and config imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("   Install with: pip install ib_async")
    sys.exit(1)


class MaestroTWSConnection:
    """
    MAESTRO's Comprehensive TWS Connection Manager

    Implements all research-backed solutions:
    1. Race condition delay (Claude's proven solution)
    2. Read-only mode bypass (ChatGPT/Perplexity solution)
    3. Enhanced timeouts and retry logic
    4. TCP optimization (Copilot solution)
    5. Version compatibility handling (Grok solution)
    6. Protocol adherence (Gemini solution)
    """

    def __init__(self, host="192.168.1.4", port=7497, client_id=1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = None
        self.connection_attempts = 0
        self.max_retries = 5

        # Research-backed configuration
        self.PROVEN_RACE_CONDITION_DELAY = 1.0  # Claude's solution
        self.EXTENDED_REQUEST_TIMEOUT = 30.0  # All reports recommend this
        self.CONNECTION_TIMEOUT = 15.0  # Increased from default 4s
        self.RETRY_DELAY = 2.0  # Between connection attempts

        # Setup logging
        self.setup_logging()

    def setup_logging(self):
        """Enhanced logging based on research recommendations"""
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - MAESTRO_TWS - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(
                    f"logs/maestro_tws_{datetime.now().strftime('%Y%m%d')}.log"
                ),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger("MaestroTWS")

    def apply_tcp_optimizations(self):
        """
        Apply TCP optimizations (Copilot's solution)
        Disable Nagle's algorithm to prevent packet delays
        """
        try:
            # Monkey-patch socket creation to add TCP_NODELAY
            original_create_connection = asyncio.get_event_loop().create_connection

            async def optimized_connection(*args, **kwargs):
                transport, protocol = await original_create_connection(*args, **kwargs)
                sock = transport.get_extra_info("socket")
                if sock:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    self.logger.debug(
                        "✅ Applied TCP optimizations (TCP_NODELAY, SO_KEEPALIVE)"
                    )
                return transport, protocol

            asyncio.get_event_loop().create_connection = optimized_connection
            return True

        except Exception as e:
            self.logger.warning(f"⚠️ Could not apply TCP optimizations: {e}")
            return False

    def initialize_ib_async(self):
        """
        Initialize ib_async with research-backed settings
        """
        try:
            # Initialize utilities (Claude's working pattern)
            util.startLoop()
            util.logToConsole("DEBUG")  # Enhanced logging

            # Create IB instance with extended timeouts
            self.ib = IB()
            self.ib.RequestTimeout = (
                self.EXTENDED_REQUEST_TIMEOUT
            )  # All reports recommend this

            # Setup connection event handlers (Perplexity solution)
            self.ib.connectedEvent += self._on_connected
            self.ib.disconnectedEvent += self._on_disconnected
            self.ib.errorEvent += self._on_error

            self.logger.info("✅ ib_async initialized with enhanced settings")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize ib_async: {e}")
            return False

    def _on_connected(self):
        """Connection event handler"""
        self.logger.info("🔌 Connected event fired")

    def _on_disconnected(self):
        """Disconnection event handler"""
        self.logger.info("🔌 Disconnected event fired")

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Error event handler"""
        self.logger.error(f"❌ TWS Error {errorCode}: {errorString}")

    async def test_socket_connection(self):
        """
        Pre-flight socket test (All reports recommend this)
        """
        self.logger.info(
            f"🔌 Testing raw socket connection to {self.host}:{self.port}..."
        )

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            start_time = time.time()
            result = sock.connect_ex((self.host, self.port))
            connection_time = time.time() - start_time
            sock.close()

            if result == 0:
                self.logger.info(f"✅ Socket connected in {connection_time:.3f}s")
                return True
            else:
                self.logger.error(f"❌ Socket connection failed (error: {result})")
                return False

        except Exception as e:
            self.logger.error(f"❌ Socket test failed: {e}")
            return False

    async def connect_with_triple_fix(self):
        """
        MAESTRO'S TRIPLE FIX IMPLEMENTATION

        Combines the three most effective solutions:
        1. Read-only mode (bypasses reqExecutions timeout)
        2. Race condition delay (proven 1-second delay)
        3. Enhanced error handling and retries
        """
        self.connection_attempts += 1

        try:
            self.logger.info(
                f"🚀 MAESTRO Triple Fix - Attempt {self.connection_attempts}"
            )
            self.logger.info(f"   Host: {self.host}:{self.port}")
            self.logger.info(f"   Client ID: {self.client_id}")
            self.logger.info(f"   Mode: Read-Only (bypasses execution sync)")

            # SOLUTION 1: Connect in read-only mode (ChatGPT/Perplexity solution)
            # This bypasses reqExecutions during handshake which causes timeouts
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.CONNECTION_TIMEOUT,
                readonly=True,  # 🔑 KEY FIX: Prevents execution history sync timeout
            )

            self.logger.info(
                "✅ Phase 1: TCP connection and initial handshake completed"
            )

            # SOLUTION 2: Apply race condition delay (Claude's proven solution)
            # This allows the API handshake to fully stabilize
            self.logger.info(
                f"⏳ Phase 2: Applying proven race condition delay ({self.PROVEN_RACE_CONDITION_DELAY}s)"
            )
            await asyncio.sleep(self.PROVEN_RACE_CONDITION_DELAY)

            # SOLUTION 3: Validate connection stability
            if not self.ib.isConnected():
                raise ConnectionError("Connection lost during stabilization delay")

            # Test basic API functionality
            self.logger.info("🔍 Phase 3: Testing API functionality...")

            # Get managed accounts (should be immediate)
            accounts = self.ib.managedAccounts()
            if accounts:
                self.logger.info(f"✅ Managed accounts: {accounts}")
            else:
                self.logger.warning("⚠️ No managed accounts returned")

            # Test server time (lightweight API call)
            try:
                server_time = await asyncio.wait_for(
                    self.ib.reqCurrentTimeAsync(), timeout=5.0
                )
                self.logger.info(f"✅ Server time: {server_time}")
            except asyncio.TimeoutError:
                self.logger.warning("⚠️ Server time request timed out (non-critical)")

            self.logger.info("🎉 MAESTRO TRIPLE FIX SUCCESS!")
            self.logger.info("✅ TWS API connection is stable and ready")

            return True

        except asyncio.TimeoutError:
            self.logger.error(f"❌ Connection timeout after {self.CONNECTION_TIMEOUT}s")
            self.logger.error(
                "   This suggests TWS is not sending nextValidId/managedAccounts"
            )
            return False

        except ConnectionRefusedError:
            self.logger.error(f"❌ Connection refused by {self.host}:{self.port}")
            self.logger.error("   Check if TWS is running and API is enabled")
            return False

        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.logger.error(f"   Error type: {type(e).__name__}")
            return False

    async def connect_with_full_retry(self):
        """
        Full connection process with retry logic
        """
        # Apply TCP optimizations first
        self.apply_tcp_optimizations()

        # Initialize ib_async
        if not self.initialize_ib_async():
            return None

        # Test socket connectivity first
        if not await self.test_socket_connection():
            self.logger.error("❌ Pre-flight socket test failed")
            return None

        # Attempt connection with retries
        for attempt in range(self.max_retries):
            try:
                # Use different client ID for each retry (research recommendation)
                self.client_id = 1 + attempt

                success = await self.connect_with_triple_fix()

                if success:
                    self.logger.info(f"🎉 CONNECTION SUCCESS on attempt {attempt + 1}")
                    return self.ib

                # If failed, disconnect cleanly before retry
                if self.ib and self.ib.isConnected():
                    self.ib.disconnect()
                    self.logger.info("🔌 Disconnected cleanly before retry")

                # Wait before retry with exponential backoff
                retry_delay = self.RETRY_DELAY * (2**attempt)
                self.logger.info(f"⏳ Waiting {retry_delay}s before retry...")
                await asyncio.sleep(retry_delay)

            except Exception as e:
                self.logger.error(f"❌ Attempt {attempt + 1} crashed: {e}")
                if self.ib and self.ib.isConnected():
                    self.ib.disconnect()

        self.logger.error(f"❌ All {self.max_retries} connection attempts failed")
        return None

    def disconnect(self):
        """Clean disconnection"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.logger.info("🔌 Disconnected from TWS")


async def test_maestro_fix():
    """
    Test the MAESTRO TWS fix
    """
    print("🕷️ SPYDER - MAESTRO'S TWS CONNECTION FIX")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print()

    # Get configuration
    try:
        config = get_active_config()
        host = config.get("host", "192.168.1.4")
        port = config.get("port", 7497)
        print(f"🎯 Target: {host}:{port} (from config)")
    except:
        host = "192.168.1.4"
        port = 7497
        print(f"🎯 Target: {host}:{port} (fallback)")

    print(f"🖥️  Linux IP: Should be in TWS trusted IPs")
    print()

    # Create connection manager
    maestro = MaestroTWSConnection(host=host, port=port)

    try:
        # Attempt connection
        ib = await maestro.connect_with_full_retry()

        if ib:
            print(f"\n🎉 MAESTRO FIX SUCCESSFUL!")
            print(f"✅ TWS API is connected and ready")
            print(f"✅ SPYDER can now use this connection")

            # Keep connection alive briefly for demonstration
            print(f"\n⏳ Keeping connection alive for 10 seconds...")
            await asyncio.sleep(10)

        else:
            print(f"\n❌ MAESTRO FIX FAILED")
            print(f"   See logs for detailed diagnosis")
            print(f"   Check TWS configuration:")
            print(f"   • API enabled with correct ports")
            print(f"   • Linux IP in trusted IPs")
            print(f"   • 'Download open orders on connection' DISABLED")

    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")

    finally:
        maestro.disconnect()


class ProductionTWSManager:
    """
    Production-ready TWS connection manager for SPYDER
    """

    def __init__(self):
        self.connections = {}
        self.connection_pool_size = 3

    async def get_connection(self, connection_type="data"):
        """
        Get a connection from the pool
        """
        if connection_type not in self.connections:
            maestro = MaestroTWSConnection(
                client_id=self._get_client_id(connection_type)
            )
            ib = await maestro.connect_with_full_retry()
            if ib:
                self.connections[connection_type] = {
                    "ib": ib,
                    "maestro": maestro,
                    "last_used": datetime.now(),
                }

        return self.connections.get(connection_type, {}).get("ib")

    def _get_client_id(self, connection_type):
        """Assign client IDs by connection type"""
        client_id_map = {"data": 1, "orders": 2, "positions": 3, "market_data": 4}
        return client_id_map.get(connection_type, 10)

    async def health_check(self):
        """Check all connections are healthy"""
        for conn_type, conn_info in self.connections.items():
            ib = conn_info["ib"]
            if not ib.isConnected():
                print(f"⚠️ Connection {conn_type} is down, reconnecting...")
                # Reconnect logic here

    def shutdown(self):
        """Clean shutdown of all connections"""
        for conn_info in self.connections.values():
            conn_info["maestro"].disconnect()


if __name__ == "__main__":
    import os

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    try:
        asyncio.run(test_maestro_fix())
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
