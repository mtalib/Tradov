#!/usr/bin/env python3
"""
Pooled Multi-Client Data Manager using IB Connection Pool

⚠️ DEPRECATED - MIGRATION TO WEB API IN PROGRESS ⚠️

This module provided pooled multi-client management for IB Gateway/TWS via ib_async.
It is being DEPRECATED as part of the migration to IBKR Web API (OAuth 2.0).

The Web API does not require multi-client pools:
- Single session with OAuth 2.0 authentication
- Rate limiting handles request distribution
- WebSocket for streaming data
- REST API for operations

MIGRATION STATUS: This file should NOT be used in new code.
Use ClientPortalAPI session and rate limiting instead.

Legacy Purpose (IB Gateway/TWS):
This module provided a connection pool-based implementation of the multi-client
data manager, designed to solve IB Gateway connection issues by using a shared
pool of persistent connections instead of individual client connections.

Legacy Key Features:
- Uses IBConnectionPool for efficient connection management
- Thread-safe connection borrowing and returning
- Maintains existing MultiClientDataManager interface
- Automatic retry and error handling
- Health monitoring and statistics
- Graceful startup and shutdown

Author: Spyder Trading System
Version: 1.0.0 (DEPRECATED)
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import weakref

# DEPRECATED: ib_async import for multi-client pooling
# This module is being phased out in favor of Web API
try:
    from ib_async import IB, Contract, Stock, Option

    IB_ASYNC_AVAILABLE = True
    print("⚠️ WARNING: PooledMultiClientManager is DEPRECATED. Use ClientPortalAPI instead.")
except ImportError:
    IB_ASYNC_AVAILABLE = False
    IB = None

# Spyder imports
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU23_MemoryMonitor import SpyderMemoryMonitor
from .SpyderB30_IBConnectionPool import IBConnectionPool, ConnectionState


class ClientType(Enum):
    """Types of data clients"""

    ORDER_EXECUTION = "order_execution"
    ADMINISTRATIVE = "administrative"
    CORE_DATA = "core_data"
    OPTIONS_DATA = "options_data"
    VOLATILITY_DATA = "volatility_data"
    MARKET_INTERNALS = "market_internals"
    MAJOR_INDICES = "major_indices"
    EXTENDED_ASSETS = "extended_assets"
    SECTOR_ETFS = "sector_etfs"
    INTERNATIONAL = "international"


@dataclass
class PooledClientInfo:
    """Information about a pooled client"""

    client_id: int
    client_type: ClientType
    is_active: bool
    last_activity: float
    data_subscriptions: List[str]
    error_count: int
    total_requests: int


class PooledMultiClientManager:
    """
    Multi-client data manager using connection pooling.

    This manager uses a shared pool of IB Gateway connections to serve
    multiple data clients efficiently, avoiding the connection timeout
    and handshake issues seen with individual connections.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4002,
        pool_size: int = 8,
        client_types: Optional[List[ClientType]] = None,
        connection_timeout: float = 30.0,
        request_timeout: float = 10.0,
    ):
        """
        Initialize the pooled multi-client manager.

        Args:
            host: IB Gateway host
            port: IB Gateway port
            pool_size: Size of connection pool
            client_types: Types of clients to manage
            connection_timeout: Timeout for pool connections
            request_timeout: Timeout for individual requests
        """
        if not IB_ASYNC_AVAILABLE:
            raise ImportError("ib_async is required for PooledMultiClientManager")

        self.host = host
        self.port = port
        self.request_timeout = request_timeout

        # Default client types
        if client_types is None:
            client_types = [
                ClientType.ORDER_EXECUTION,
                ClientType.ADMINISTRATIVE,
                ClientType.CORE_DATA,
                ClientType.OPTIONS_DATA,
                ClientType.VOLATILITY_DATA,
                ClientType.MARKET_INTERNALS,
                ClientType.MAJOR_INDICES,
                ClientType.EXTENDED_ASSETS,
                ClientType.SECTOR_ETFS,
                ClientType.INTERNATIONAL,
            ]

        self.client_types = client_types

        # Connection pool
        self.connection_pool = IBConnectionPool(
            host=host,
            port=port,
            min_connections=min(3, pool_size // 2),
            max_connections=pool_size,
            connection_timeout=connection_timeout,
        )

        # Client management
        self._clients: Dict[int, PooledClientInfo] = {}
        self._client_lock = threading.RLock()
        self._is_started = False

        # Thread management
        self._executor = ThreadPoolExecutor(
            max_workers=pool_size + 2, thread_name_prefix="PooledClient"
        )

        # Error handling and logging
        self.error_handler = SpyderErrorHandler()
        self.memory_monitor = SpyderMemoryMonitor()
        self.logger = logging.getLogger(f"{__name__}.PooledMultiClient")

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "active_clients": 0,
            "pool_borrows": 0,
            "pool_returns": 0,
        }

        # Callbacks
        self._data_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        self._status_callbacks: List[Callable] = []

        self.logger.info(
            f"PooledMultiClientManager initialized with {len(client_types)} client types"
        )

    async def start(self) -> bool:
        """
        Start the pooled multi-client manager.

        Returns:
            True if successfully started
        """
        if self._is_started:
            self.logger.warning("Manager already started")
            return True

        self.logger.info("Starting pooled multi-client manager...")

        try:
            # Initialize connection pool
            if not await self.connection_pool.initialize():
                self.logger.error("Failed to initialize connection pool")
                return False

            # Initialize clients
            success_count = 0
            for i, client_type in enumerate(self.client_types, 1):
                if await self._initialize_client(i, client_type):
                    success_count += 1
                else:
                    self.logger.warning(
                        f"Failed to initialize client {i} ({client_type.value})"
                    )

            if success_count == 0:
                self.logger.error("Failed to initialize any clients")
                return False

            self._is_started = True
            self.logger.info(
                f"✅ Started {success_count}/{len(self.client_types)} clients"
            )

            # Update stats
            with self._client_lock:
                self._stats["active_clients"] = success_count

            return True

        except Exception as e:
            self.logger.error(f"Failed to start manager: {e}")
            self.error_handler.handle_error(e, "Manager startup failed")
            return False

    async def _initialize_client(self, client_id: int, client_type: ClientType) -> bool:
        """
        Initialize a single client.

        Args:
            client_id: Unique client identifier
            client_type: Type of client

        Returns:
            True if successfully initialized
        """
        try:
            self.logger.debug(f"Initializing client {client_id} ({client_type.value})")

            # Test connection by borrowing from pool
            with self.connection_pool.get_connection(f"InitClient{client_id}") as ib:
                if not ib.isConnected():
                    self.logger.error(f"Client {client_id}: Pool connection not active")
                    return False

            # Create client info
            client_info = PooledClientInfo(
                client_id=client_id,
                client_type=client_type,
                is_active=True,
                last_activity=time.time(),
                data_subscriptions=[],
                error_count=0,
                total_requests=0,
            )

            with self._client_lock:
                self._clients[client_id] = client_info

            self.logger.info(f"✅ Client {client_id} ({client_type.value}) initialized")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize client {client_id}: {e}")
            return False

    @contextmanager
    def get_client_connection(self, client_id: int):
        """
        Get a connection for a specific client.

        Args:
            client_id: Client identifier

        Yields:
            IB connection instance

        Raises:
            ValueError: If client not found
            TimeoutError: If no connection available
        """
        with self._client_lock:
            if client_id not in self._clients:
                raise ValueError(f"Client {client_id} not found")

            client_info = self._clients[client_id]
            if not client_info.is_active:
                raise ValueError(f"Client {client_id} is not active")

        # Borrow connection from pool
        borrower_info = f"Client{client_id}_{client_info.client_type.value}"

        try:
            with self.connection_pool.get_connection(
                borrower_info, timeout=self.request_timeout
            ) as ib:
                # Update client activity
                with self._client_lock:
                    client_info.last_activity = time.time()
                    client_info.total_requests += 1
                    self._stats["pool_borrows"] += 1

                yield ib

                # Update success stats
                with self._client_lock:
                    self._stats["pool_returns"] += 1
                    self._stats["successful_requests"] += 1

        except Exception as e:
            # Update error stats
            with self._client_lock:
                client_info.error_count += 1
                self._stats["failed_requests"] += 1

            self.logger.error(f"Client {client_id} connection error: {e}")
            raise

    async def request_market_data(
        self,
        client_id: int,
        contract: Any,
        generic_tick_list: str = "",
        snapshot: bool = False,
    ) -> Optional[Any]:
        """
        Request market data using pooled connection.

        Args:
            client_id: Client requesting data
            contract: IB contract object
            generic_tick_list: List of generic tick types
            snapshot: Whether to request snapshot

        Returns:
            Market data ticker or None if failed
        """
        try:
            with self.get_client_connection(client_id) as ib:
                self.logger.debug(
                    f"Client {client_id} requesting market data for {contract.symbol}"
                )

                # Request market data
                ticker = ib.reqMktData(
                    contract, genericTickList=generic_tick_list, snapshot=snapshot
                )

                # Wait for initial data if snapshot
                if snapshot:
                    await asyncio.sleep(0.5)  # Give time for data to arrive

                # Update subscriptions
                with self._client_lock:
                    client_info = self._clients[client_id]
                    subscription_key = f"{contract.symbol}_{contract.secType}"
                    if subscription_key not in client_info.data_subscriptions:
                        client_info.data_subscriptions.append(subscription_key)

                self._stats["total_requests"] += 1
                return ticker

        except Exception as e:
            self.logger.error(f"Market data request failed for client {client_id}: {e}")
            self.error_handler.handle_error(e, f"Market data request failed")
            return None

    async def request_historical_data(
        self,
        client_id: int,
        contract: Any,
        end_datetime: str = "",
        duration_str: str = "1 D",
        bar_size_setting: str = "1 min",
        what_to_show: str = "TRADES",
        use_rth: int = 1,
    ) -> Optional[List]:
        """
        Request historical data using pooled connection.

        Args:
            client_id: Client requesting data
            contract: IB contract object
            end_datetime: End date/time for data
            duration_str: Duration of data to retrieve
            bar_size_setting: Bar size
            what_to_show: Type of data to show
            use_rth: Use regular trading hours

        Returns:
            List of historical bars or None if failed
        """
        try:
            with self.get_client_connection(client_id) as ib:
                self.logger.debug(
                    f"Client {client_id} requesting historical data for {contract.symbol}"
                )

                # Request historical data
                bars = ib.reqHistoricalData(
                    contract,
                    endDateTime=end_datetime,
                    durationStr=duration_str,
                    barSizeSetting=bar_size_setting,
                    whatToShow=what_to_show,
                    useRTH=use_rth,
                    formatDate=1,
                )

                self._stats["total_requests"] += 1
                return bars

        except Exception as e:
            self.logger.error(
                f"Historical data request failed for client {client_id}: {e}"
            )
            self.error_handler.handle_error(e, f"Historical data request failed")
            return None

    async def get_positions(self, client_id: int) -> Optional[List]:
        """
        Get positions using pooled connection.

        Args:
            client_id: Client requesting positions

        Returns:
            List of positions or None if failed
        """
        try:
            with self.get_client_connection(client_id) as ib:
                self.logger.debug(f"Client {client_id} requesting positions")

                positions = ib.positions()
                self._stats["total_requests"] += 1
                return positions

        except Exception as e:
            self.logger.error(f"Positions request failed for client {client_id}: {e}")
            return None

    async def get_account_summary(
        self, client_id: int, tags: str = "TotalCashValue,NetLiquidation"
    ) -> Optional[List]:
        """
        Get account summary using pooled connection.

        Args:
            client_id: Client requesting account data
            tags: Account summary tags to request

        Returns:
            List of account values or None if failed
        """
        try:
            with self.get_client_connection(client_id) as ib:
                self.logger.debug(f"Client {client_id} requesting account summary")

                account_summary = ib.reqAccountSummary("All", tags)
                self._stats["total_requests"] += 1
                return account_summary

        except Exception as e:
            self.logger.error(
                f"Account summary request failed for client {client_id}: {e}"
            )
            return None

    def get_client_info(self, client_id: int) -> Optional[PooledClientInfo]:
        """Get information about a specific client."""
        with self._client_lock:
            return self._clients.get(client_id)

    def list_active_clients(self) -> List[int]:
        """Get list of active client IDs."""
        with self._client_lock:
            return [cid for cid, info in self._clients.items() if info.is_active]

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        with self._client_lock:
            stats = self._stats.copy()

        # Add pool stats
        pool_stats = self.connection_pool.get_stats()
        stats.update({f"pool_{k}": v for k, v in pool_stats.items()})

        # Add client stats
        with self._client_lock:
            stats["total_clients"] = len(self._clients)
            stats["active_clients"] = sum(
                1 for info in self._clients.values() if info.is_active
            )

            # Client type breakdown
            client_types = {}
            for info in self._clients.values():
                ctype = info.client_type.value
                client_types[ctype] = client_types.get(ctype, 0) + 1
            stats["clients_by_type"] = client_types

        return stats

    def add_data_callback(self, callback: Callable):
        """Add callback for data events."""
        self._data_callbacks.append(callback)

    def add_error_callback(self, callback: Callable):
        """Add callback for error events."""
        self._error_callbacks.append(callback)

    def add_status_callback(self, callback: Callable):
        """Add callback for status events."""
        self._status_callbacks.append(callback)

    async def stop(self):
        """Stop the pooled multi-client manager."""
        if not self._is_started:
            return

        self.logger.info("Stopping pooled multi-client manager...")

        # Deactivate all clients
        with self._client_lock:
            for client_info in self._clients.values():
                client_info.is_active = False

        # Shutdown connection pool
        await self.connection_pool.shutdown()

        # Shutdown executor
        self._executor.shutdown(wait=True)

        self._is_started = False
        self.logger.info("✅ Pooled multi-client manager stopped")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


# Example usage and testing
if __name__ == "__main__":

    async def test_pooled_manager():
        """Test the pooled multi-client manager."""
        manager = PooledMultiClientManager(
            host="127.0.0.1",
            port=4002,  # Paper trading
            pool_size=5,
            client_types=[
                ClientType.CORE_DATA,
                ClientType.OPTIONS_DATA,
                ClientType.MARKET_INTERNALS,
            ],
        )

        try:
            # Start manager
            if not await manager.start():
                print("❌ Failed to start manager")
                return

            print("✅ Manager started successfully")

            # Test market data requests
            spx_contract = Stock("SPY", "SMART", "USD")

            for client_id in [1, 2, 3]:
                ticker = await manager.request_market_data(
                    client_id, spx_contract, snapshot=True
                )
                if ticker:
                    print(
                        f"✅ Client {client_id} got market data: {ticker.contract.symbol}"
                    )
                else:
                    print(f"❌ Client {client_id} failed to get market data")

            # Test concurrent requests
            tasks = []
            for client_id in [1, 2, 3]:
                task = manager.get_positions(client_id)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            print(
                f"✅ Concurrent requests completed: {len([r for r in results if not isinstance(r, Exception)])} successful"
            )

            # Print stats
            stats = manager.get_stats()
            print(f"📊 Manager stats: {stats}")

        finally:
            await manager.stop()
            print("✅ Manager stopped")

    # Run test
    if IB_ASYNC_AVAILABLE:
        asyncio.run(test_pooled_manager())
    else:
        print("❌ ib_async not available for testing")
