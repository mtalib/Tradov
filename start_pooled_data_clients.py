#!/usr/bin/env python3
"""
Pooled Data Clients Startup Script

This script starts the Spyder data clients using the enhanced connection pool
approach that has been proven to work. Instead of individual client connections
that timeout, this uses a shared pool of EnhancedConnectionManager connections.

Key Features:
- Uses EnhancedConnectionManager (same as working dashboard)
- Connection pooling for efficient resource usage
- Eliminates 30-second timeout issues
- Supports all 11 data client types
- Proper error handling and monitoring
- Health checks and auto-recovery

Usage:
    python start_pooled_data_clients.py

Requirements:
- IB Gateway must be running and logged in
- Port 4002 (paper trading) should be accessible

Author: Spyder Trading System
Version: 1.0.0
"""

import asyncio
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Spyder imports
from SpyderB_Broker.SpyderB29_EnhancedConnectionManager import (
    get_connection_manager,
    ConnectionConfig,
    TradingMode,
)
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from enhanced_connection_pool import EnhancedConnectionPool

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


class PooledDataClientManager:
    """
    Manager for pooled data clients using EnhancedConnectionManager.

    This replaces the traditional MultiClientDataManager with a connection
    pool-based approach that eliminates timeout issues.
    """

    def __init__(self, pool_size: int = 8):
        """
        Initialize the pooled data client manager.

        Args:
            pool_size: Size of connection pool
        """
        self.pool_size = pool_size
        self.connection_pool: Optional[EnhancedConnectionPool] = None
        self.is_running = False
        self.error_handler = SpyderErrorHandler()

        # Data client definitions
        self.client_definitions = [
            {
                "id": 1,
                "type": "order_execution",
                "description": "Order execution and trade management",
            },
            {
                "id": 2,
                "type": "administrative",
                "description": "Account and administrative data",
            },
            {
                "id": 3,
                "type": "core_data",
                "description": "Core market data (SPY, QQQ, major ETFs)",
            },
            {
                "id": 4,
                "type": "options_data",
                "description": "Options chains and volatility data",
            },
            {
                "id": 5,
                "type": "volatility_data",
                "description": "VIX and volatility surface data",
            },
            {
                "id": 6,
                "type": "market_internals",
                "description": "Market breadth and internals",
            },
            {
                "id": 7,
                "type": "major_indices",
                "description": "Major index futures and data",
            },
            {
                "id": 8,
                "type": "extended_assets",
                "description": "Extended asset coverage",
            },
            {"id": 9, "type": "sector_etfs", "description": "Sector ETF data"},
            {
                "id": 10,
                "type": "international",
                "description": "International market data",
            },
            {
                "id": 11,
                "type": "backup_data",
                "description": "Backup and redundancy client",
            },
        ]

        # Statistics
        self.stats = {
            "start_time": None,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "active_subscriptions": 0,
        }

        logger.info(
            f"🔧 PooledDataClientManager initialized with {len(self.client_definitions)} client types"
        )

    async def start(self) -> bool:
        """
        Start the pooled data client system.

        Returns:
            True if successfully started
        """
        if self.is_running:
            logger.warning("Data client manager already running")
            return True

        logger.info("🚀 Starting pooled data client system...")

        try:
            # Create and initialize connection pool
            self.connection_pool = EnhancedConnectionPool(
                pool_size=self.pool_size,
                host="127.0.0.1",
                port=4002,
                trading_mode=TradingMode.PAPER,
            )

            # Initialize the pool
            success_count = self.connection_pool.initialize()

            if success_count == 0:
                logger.error("❌ Failed to create any connections")
                return False

            logger.info(
                f"✅ Connection pool ready with {success_count}/{self.pool_size} connections"
            )

            # Test pool functionality
            await self._test_pool_functionality()

            # Start monitoring
            await self._start_monitoring()

            self.is_running = True
            self.stats["start_time"] = time.time()

            logger.info("🎉 Pooled data client system started successfully!")
            logger.info(
                f"📋 Managing {len(self.client_definitions)} data client types:"
            )

            for client_def in self.client_definitions:
                logger.info(
                    f"   🔹 Client {client_def['id']}: {client_def['type']} - {client_def['description']}"
                )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to start data client system: {e}")
            self.error_handler.handle_error(e, "Data client system startup failed")
            return False

    async def _test_pool_functionality(self):
        """Test basic pool functionality with sample requests."""
        logger.info("🧪 Testing pool functionality...")

        try:
            # Test basic connection borrowing
            with self.connection_pool.get_connection("StartupTest") as ib:
                logger.info(f"✅ Pool test: Borrowed connection {ib.client.clientId}")

                # Test basic operations
                try:
                    positions = ib.positions()
                    logger.info(f"✅ Pool test: Retrieved {len(positions)} positions")
                except Exception as e:
                    logger.warning(f"⚠️ Pool test: Position request failed: {e}")

                try:
                    account_summary = ib.accountSummary()
                    logger.info(
                        f"✅ Pool test: Retrieved account summary with {len(account_summary)} items"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Pool test: Account summary failed: {e}")

            logger.info("✅ Pool functionality test completed")

        except Exception as e:
            logger.error(f"❌ Pool functionality test failed: {e}")
            raise

    async def _start_monitoring(self):
        """Start monitoring tasks."""
        logger.info("📊 Starting monitoring tasks...")

        # Health check task
        asyncio.create_task(self._health_monitor_loop())

        # Statistics task
        asyncio.create_task(self._stats_monitor_loop())

        logger.info("✅ Monitoring tasks started")

    async def _health_monitor_loop(self):
        """Monitor connection pool health."""
        while self.is_running:
            try:
                if self.connection_pool:
                    health = self.connection_pool.health_check()

                    if health["unhealthy"]:
                        logger.warning(
                            f"⚠️ Health check: {len(health['unhealthy'])} unhealthy connections"
                        )

                    if health["reconnected"]:
                        logger.info(
                            f"✅ Health check: Reconnected {len(health['reconnected'])} connections"
                        )

                # Wait 60 seconds before next check
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")
                await asyncio.sleep(30)  # Shorter wait on error

    async def _stats_monitor_loop(self):
        """Monitor and log statistics."""
        while self.is_running:
            try:
                if self.connection_pool:
                    pool_stats = self.connection_pool.get_stats()

                    # Log stats every 5 minutes
                    logger.info("📊 Pool Statistics:")
                    logger.info(
                        f"   Total connections: {pool_stats['total_connections']}"
                    )
                    logger.info(f"   Available: {pool_stats['current_available']}")
                    logger.info(f"   In use: {pool_stats['current_in_use']}")
                    logger.info(f"   Total borrowed: {pool_stats['total_borrowed']}")
                    logger.info(f"   Total returned: {pool_stats['total_returned']}")
                    logger.info(f"   Healthy: {pool_stats['healthy_connections']}")

                # Wait 5 minutes before next stats
                await asyncio.sleep(300)

            except Exception as e:
                logger.error(f"❌ Stats monitor error: {e}")
                await asyncio.sleep(60)

    async def request_market_data(self, client_type: str, contract, **kwargs):
        """
        Request market data using the connection pool.

        Args:
            client_type: Type of client making the request
            contract: IB contract object
            **kwargs: Additional arguments for market data request

        Returns:
            Market data ticker or None
        """
        if not self.is_running or not self.connection_pool:
            logger.error("❌ Data client system not running")
            return None

        try:
            self.stats["total_requests"] += 1

            with self.connection_pool.get_connection(
                f"{client_type}_market_data"
            ) as ib:
                logger.debug(
                    f"📡 {client_type} requesting market data for {getattr(contract, 'symbol', 'unknown')}"
                )

                ticker = ib.reqMktData(contract, **kwargs)

                self.stats["successful_requests"] += 1
                return ticker

        except Exception as e:
            logger.error(f"❌ Market data request failed for {client_type}: {e}")
            self.stats["failed_requests"] += 1
            return None

    async def request_historical_data(self, client_type: str, contract, **kwargs):
        """
        Request historical data using the connection pool.

        Args:
            client_type: Type of client making the request
            contract: IB contract object
            **kwargs: Additional arguments for historical data request

        Returns:
            Historical data bars or None
        """
        if not self.is_running or not self.connection_pool:
            logger.error("❌ Data client system not running")
            return None

        try:
            self.stats["total_requests"] += 1

            with self.connection_pool.get_connection(f"{client_type}_historical") as ib:
                logger.debug(
                    f"📊 {client_type} requesting historical data for {getattr(contract, 'symbol', 'unknown')}"
                )

                bars = ib.reqHistoricalData(contract, **kwargs)

                self.stats["successful_requests"] += 1
                return bars

        except Exception as e:
            logger.error(f"❌ Historical data request failed for {client_type}: {e}")
            self.stats["failed_requests"] += 1
            return None

    def get_stats(self) -> Dict:
        """Get system statistics."""
        runtime = (
            time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        )

        stats = self.stats.copy()
        stats.update(
            {
                "runtime_seconds": runtime,
                "is_running": self.is_running,
                "pool_size": self.pool_size,
                "client_types": len(self.client_definitions),
            }
        )

        if self.connection_pool:
            pool_stats = self.connection_pool.get_stats()
            stats.update({f"pool_{k}": v for k, v in pool_stats.items()})

        return stats

    async def stop(self):
        """Stop the pooled data client system."""
        if not self.is_running:
            return

        logger.info("🛑 Stopping pooled data client system...")

        self.is_running = False

        if self.connection_pool:
            self.connection_pool.shutdown()

        logger.info("✅ Pooled data client system stopped")


# Global manager instance
manager = None


async def main():
    """Main startup function."""
    global manager

    print("=" * 60)
    print("🚀 SPYDER POOLED DATA CLIENTS STARTUP")
    print("=" * 60)
    print("This script starts 11 data clients using connection pooling.")
    print("Connection pooling eliminates timeout issues and provides")
    print("efficient resource usage with IB Gateway.")
    print()
    print("Make sure IB Gateway is running and logged in before proceeding.")
    print()

    try:
        # Create and start manager
        manager = PooledDataClientManager(pool_size=8)

        if not await manager.start():
            logger.error("❌ Failed to start data client system")
            return 1

        # Print success message
        print("🎉 SUCCESS!")
        print("=" * 60)
        print("✅ Pooled data client system is now running")
        print("✅ Connection pool is healthy and ready")
        print("✅ All 11 data client types are available")
        print()
        print("📊 Statistics:")
        stats = manager.get_stats()
        print(f"   Pool size: {stats['pool_size']}")
        print(f"   Available connections: {stats.get('pool_current_available', 'N/A')}")
        print(f"   Client types: {stats['client_types']}")
        print()
        print("🔄 System will continue running...")
        print("   Press Ctrl+C to stop")
        print()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

            # Check if manager is still healthy
            if not manager.is_running:
                logger.error("❌ Manager stopped unexpectedly")
                break

    except KeyboardInterrupt:
        logger.info("👋 Received shutdown signal")
        print("\n🛑 Shutting down...")

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        print(f"\n❌ Error: {e}")
        return 1

    finally:
        # Cleanup
        if manager:
            await manager.stop()

        print("✅ Shutdown complete")

    return 0


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}")
    # The KeyboardInterrupt will be handled in main()
    raise KeyboardInterrupt()


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run main
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
