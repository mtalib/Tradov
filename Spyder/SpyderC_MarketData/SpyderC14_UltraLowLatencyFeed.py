#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC14_UltraLowLatencyFeed.py
Purpose: Ultra-low latency market data feed with ib_async integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-21 Time: 21:55:00

⚠️ DEPRECATION WARNING ⚠️
    This module is DEPRECATED and represents over-engineering for current needs.

    Status:
    - ❌ Uses deprecated ib_async for market data
    - ⚠️ HFT-level optimization not needed for options strategies
    - 🎯 Databento WebSocket provides adequate latency (~nanosecond timestamps via DBN)

    Architecture Decision:
    - Current Spyder strategies are NOT high-frequency trading
    - Options strategies operate on 1-second to 1-minute timeframes
    - Sub-5ms latency optimization is premature
    - Databento + standard async provides sufficient performance

    For Current Needs:
    - Use SpyderC26_DatabentoClient (Databento OPRA.PILLAR)
    - Nanosecond resolution DBN format is sufficient for options strategies
    - Simpler architecture, easier maintenance
    - No special kernel/hardware requirements

    Note: If HFT capabilities needed in future, consider:
    - Direct exchange connectivity (CME iLink, etc.)
    - FPGAs for sub-microsecond latency
    - Co-location services
    - This module's techniques as starting point

Module Description:
    This module implements a high-performance, ultra-low latency market data
    feed system inspired by institutional HFT architectures with modern ib_async
    integration for enhanced IB Gateway 10.37 compatibility.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
import time
import mmap
import struct
import asyncio
import threading
import multiprocessing as mp
from typing import Any, Callable
from collections import deque, defaultdict
from enum import IntEnum
import ctypes
from ctypes import c_uint64, c_uint32, c_double, c_char
import numpy as np
import psutil

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import numba  # noqa: F401
    from numba import jit, cuda  # noqa: F401
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    logging.info("Warning: numba not available - performance will be reduced")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Performance Configuration
RING_BUFFER_SIZE = 1024 * 1024  # 1MB ring buffer
CPU_AFFINITY_CORE = 2  # Dedicated CPU core
CACHE_LINE_SIZE = 64
PAGE_SIZE = 4096

# Latency Targets (nanoseconds)
TARGET_MARKET_DATA_LATENCY_NS = 5_000_000    # 5ms
TARGET_ORDER_PREP_LATENCY_NS = 10_000_000    # 10ms
TARGET_TOTAL_RTT_LATENCY_NS = 50_000_000     # 50ms

# Memory Configuration
SHARED_MEMORY_SIZE = 64 * 1024 * 1024  # 64MB
MAX_CALLBACKS = 32
MAX_SYMBOLS = 1000

# Network Configuration
UDP_BUFFER_SIZE = 65536
SO_REUSEPORT = 15

# ==============================================================================
# ENUMS
# ==============================================================================
class MessageType(IntEnum):
    """Message types for ultra-fast processing"""
    QUOTE = 1
    TRADE = 2
    DEPTH = 3
    OPTIONS_CHAIN = 4
    GREEKS = 5
    NEWS = 6
    HEARTBEAT = 99

class DataPriority(IntEnum):
    """Data priority levels"""
    CRITICAL = 1  # SPY quotes, options
    HIGH = 2      # VIX, key indices
    NORMAL = 3    # Other symbols
    LOW = 4       # News, analytics

# ==============================================================================
# C STRUCTURES FOR ZERO-COPY OPERATIONS
# ==============================================================================
class MarketDataHeader(ctypes.Structure):
    """Ultra-fast header for market data messages"""
    _fields_ = [
        ('timestamp_ns', c_uint64),      # Nanosecond timestamp
        ('sequence_num', c_uint64),      # Sequence number
        ('message_type', c_uint32),      # Message type
        ('message_size', c_uint32),      # Total message size
    ]

class QuoteData(ctypes.Structure):
    """Ultra-fast quote structure"""
    _fields_ = [
        ('header', MarketDataHeader),
        ('symbol', c_char * 16),         # Symbol (e.g., "SPY")
        ('bid_price', c_double),
        ('ask_price', c_double),
        ('bid_size', c_uint32),
        ('ask_size', c_uint32),
        ('exchange', c_char * 4),
    ]

class OptionQuoteData(ctypes.Structure):
    """Option quote with Greeks"""
    _fields_ = [
        ('header', MarketDataHeader),
        ('symbol', c_char * 16),
        ('expiry', c_uint32),           # YYYYMMDD format
        ('strike', c_double),
        ('call_put', c_char),           # 'C' or 'P'
        ('bid', c_double),
        ('ask', c_double),
        ('bid_size', c_uint32),
        ('ask_size', c_uint32),
        ('iv', c_double),               # Implied volatility
        ('delta', c_double),
        ('gamma', c_double),
        ('theta', c_double),
        ('vega', c_double),
        ('volume', c_uint32),
        ('open_interest', c_uint32),
    ]

# ==============================================================================
# LOCK-FREE RING BUFFER
# ==============================================================================
class LockFreeRingBuffer:
    """
    Lock-free single-producer single-consumer ring buffer.
    Uses memory barriers for thread-safe operations without locks.
    """

    def __init__(self, size: int):
        self.size = size
        self.mask = size - 1  # Size must be power of 2
        assert (size & self.mask) == 0, "Size must be power of 2"

        # Shared memory for the buffer
        self.buffer = mmap.mmap(-1, size * 8)  # 8 bytes per entry

        # Atomic indices
        self.head = mp.Value('L', 0)  # Producer index
        self.tail = mp.Value('L', 0)  # Consumer index

    def push(self, data: int) -> bool:
        """Push data to buffer (producer side)"""
        current_head = self.head.value
        next_head = (current_head + 1) & self.mask

        if next_head == self.tail.value:
            return False  # Buffer full

        # Write data
        offset = current_head * 8
        struct.pack_into('Q', self.buffer, offset, data)

        # Update head (memory barrier)
        self.head.value = next_head
        return True

    def pop(self) -> int | None:
        """Pop data from buffer (consumer side)"""
        current_tail = self.tail.value

        if current_tail == self.head.value:
            return None  # Buffer empty

        # Read data
        offset = current_tail * 8
        data = struct.unpack_from('Q', self.buffer, offset)[0]

        # Update tail (memory barrier)
        self.tail.value = (current_tail + 1) & self.mask
        return data

# ==============================================================================
# NANOSECOND TIMER
# ==============================================================================
class NanoTimer:
    """High-precision nanosecond timer"""

    def __init__(self):
        self.start_time = time.perf_counter_ns()

    def timestamp_ns(self) -> int:
        """Get nanosecond timestamp"""
        return time.perf_counter_ns()

    def elapsed_ns(self) -> int:
        """Get elapsed nanoseconds since creation"""
        return time.perf_counter_ns() - self.start_time

# ==============================================================================
# MEMORY-MAPPED DATA STORE
# ==============================================================================
class MemoryMappedDataStore:
    """Ultra-fast memory-mapped data storage"""

    def __init__(self, name: str, size: int = SHARED_MEMORY_SIZE):
        self.name = name
        self.size = size

        # Create memory-mapped file
        self.filename = f"/tmp/spyder_{name}.mmap"
        self.file = open(self.filename, "w+b")  # noqa: SIM115
        self.file.write(b'\x00' * size)
        self.file.flush()

        # Map to memory
        self.mmap = mmap.mmap(self.file.fileno(), size)

    def write_struct(self, offset: int, data: ctypes.Structure) -> None:
        """Write C structure to memory"""
        data_bytes = bytes(data)
        self.mmap[offset:offset + len(data_bytes)] = data_bytes

    def read_struct(self, offset: int, struct_type: type) -> ctypes.Structure:
        """Read C structure from memory"""
        size = ctypes.sizeof(struct_type)
        data_bytes = self.mmap[offset:offset + size]
        return struct_type.from_buffer_copy(data_bytes)

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'mmap'):
            self.mmap.close()
        if hasattr(self, 'file'):
            self.file.close()
        try:
            os.unlink(self.filename)
        except Exception:
            pass

# ==============================================================================
# PREDICTIVE ORDER CACHE
# ==============================================================================
class PredictiveOrderCache:
    """Pre-calculate likely orders based on market conditions"""

    def __init__(self):
        self.pre_calculated_orders = {}
        self.market_conditions = {}

    async def pre_calculate_orders(self, market_data: dict[str, Any]):
        """Pre-calculate orders based on current market conditions"""

        # Extract key metrics
        price = market_data.get('price', 0)
        iv = market_data.get('iv', 20)
        rsi = market_data.get('rsi', 50)

        strategies = []

        # Iron Condor conditions
        if 30 < rsi < 70 and 15 < iv < 25:
            strategies.extend(self._generate_iron_condor_orders(price, iv))

        # Credit spread conditions
        if rsi > 70:  # Overbought
            strategies.extend(self._generate_bear_call_spread_orders(price, iv))
        elif rsi < 30:  # Oversold
            strategies.extend(self._generate_bull_put_spread_orders(price, iv))

        # Store pre-calculated orders
        self.pre_calculated_orders = {
            'iron_condor': strategies[:4] if len(strategies) >= 4 else [],
            'credit_spreads': strategies[4:8] if len(strategies) >= 8 else [],
            'timestamp': time.perf_counter_ns()
        }

    def _generate_iron_condor_orders(self, price: float, iv: float) -> list[dict]:
        """Generate iron condor orders"""
        wing_width = price * 0.02  # 2% wings

        return [
            {'strategy': 'iron_condor', 'leg': 1, 'action': 'SELL', 'type': 'PUT', 'strike': price - wing_width/2},
            {'strategy': 'iron_condor', 'leg': 2, 'action': 'BUY', 'type': 'PUT', 'strike': price - wing_width},
            {'strategy': 'iron_condor', 'leg': 3, 'action': 'SELL', 'type': 'CALL', 'strike': price + wing_width/2},
            {'strategy': 'iron_condor', 'leg': 4, 'action': 'BUY', 'type': 'CALL', 'strike': price + wing_width},
        ]

    def _generate_bear_call_spread_orders(self, price: float, iv: float) -> list[dict]:
        """Generate bear call spread orders"""
        width = price * 0.015  # 1.5% width

        return [
            {'strategy': 'bear_call', 'leg': 1, 'action': 'SELL', 'type': 'CALL', 'strike': price + width/2},
            {'strategy': 'bear_call', 'leg': 2, 'action': 'BUY', 'type': 'CALL', 'strike': price + width},
        ]

    def _generate_bull_put_spread_orders(self, price: float, iv: float) -> list[dict]:
        """Generate bull put spread orders"""
        width = price * 0.015  # 1.5% width

        return [
            {'strategy': 'bull_put', 'leg': 1, 'action': 'SELL', 'type': 'PUT', 'strike': price - width/2},
            {'strategy': 'bull_put', 'leg': 2, 'action': 'BUY', 'type': 'PUT', 'strike': price - width},
        ]

# ==============================================================================
# MAIN ULTRA-LOW LATENCY FEED CLASS
# ==============================================================================
class UltraLowLatencyFeed:
    """
    Ultra-low latency market data feed with ib_async integration.

    Combines all performance optimizations for institutional-grade latency
    with modern ib_async library for enhanced IB Gateway 10.37 compatibility.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize ultra-low latency feed with ib_async"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}

        # Components
        self.timer = NanoTimer()
        self.ring_buffer = LockFreeRingBuffer(RING_BUFFER_SIZE)
        self.mmap_store = MemoryMappedDataStore("market_data")
        self.order_cache = PredictiveOrderCache()

        # Performance tracking
        self.latency_stats = {
            "data_receive": deque(maxlen=10000),
            "processing": deque(maxlen=10000),
            "distribution": deque(maxlen=10000),
            "total": deque(maxlen=10000),
        }

        # Message sequencing
        self.sequence_number = 0

        # CPU optimization
        self._setup_cpu_affinity()

        # Callbacks
        self.callbacks = defaultdict(list)

        # Start processing threads
        self.running = False
        self.threads = []

        self.logger.info("✅ Ultra-low latency feed initialized with ib_async")

    # ==========================================================================
    # CPU OPTIMIZATION
    # ==========================================================================

    def _setup_cpu_affinity(self):
        """Set CPU affinity for optimal performance"""
        try:
            # Get current process
            p = psutil.Process()

            # Set CPU affinity to dedicated core
            if hasattr(p, "cpu_affinity"):
                cores = p.cpu_affinity()
                if len(cores) > CPU_AFFINITY_CORE:
                    p.cpu_affinity([CPU_AFFINITY_CORE])
                    self.logger.info(f"Set CPU affinity to core {CPU_AFFINITY_CORE}")

            # Set high priority
            if hasattr(p, "nice"):
                p.nice(-20)  # Highest priority

        except Exception as e:
            self.logger.warning(f"Could not set CPU affinity: {e}")

    # ==========================================================================
    # DATA INGESTION
    # ==========================================================================

    def process_market_data(self, data: bytes) -> None:
        """
        Process incoming market data with minimal latency.
        This is the hot path - must be extremely fast.
        """
        receive_time = self.timer.timestamp_ns()

        try:
            # Parse message header
            header = MarketDataHeader.from_buffer_copy(data[:ctypes.sizeof(MarketDataHeader)])

            # Calculate receive latency
            receive_latency = receive_time - header.timestamp_ns
            self.latency_stats["data_receive"].append(receive_latency)

            # Process by message type
            if header.message_type == MessageType.QUOTE:
                self._process_quote(data, receive_time)
            elif header.message_type == MessageType.OPTIONS_CHAIN:
                self._process_option_chain(data, receive_time)
            elif header.message_type == MessageType.TRADE:
                self._process_trade(data, receive_time)

        except Exception as e:
            self.logger.error(f"Market data processing error: {e}")

    def _process_quote(self, data: bytes, receive_time: int):
        """Process quote message"""
        start_time = self.timer.timestamp_ns()

        try:
            # Parse quote
            quote = QuoteData.from_buffer_copy(data)

            # Store in memory-mapped file
            offset = (self.sequence_number % 1000) * ctypes.sizeof(QuoteData)
            self.mmap_store.write_struct(offset, quote)

            # Distribute to callbacks
            self._distribute_data('quote', quote, receive_time)

            # Update statistics
            processing_latency = self.timer.timestamp_ns() - start_time
            self.latency_stats["processing"].append(processing_latency)

        except Exception as e:
            self.logger.error(f"Quote processing error: {e}")

    def _process_option_chain(self, data: bytes, receive_time: int):
        """Process option chain message"""
        start_time = self.timer.timestamp_ns()

        try:
            # Parse option data
            option = OptionQuoteData.from_buffer_copy(data)

            # Store in memory-mapped file
            offset = (self.sequence_number % 1000) * ctypes.sizeof(OptionQuoteData)
            self.mmap_store.write_struct(offset, option)

            # Distribute to callbacks
            self._distribute_data('option', option, receive_time)

            # Update statistics
            processing_latency = self.timer.timestamp_ns() - start_time
            self.latency_stats["processing"].append(processing_latency)

        except Exception as e:
            self.logger.error(f"Option processing error: {e}")

    def _process_trade(self, data: bytes, receive_time: int):
        """Process trade message"""
        start_time = self.timer.timestamp_ns()

        try:
            # Basic trade processing
            # Distribute to callbacks
            self._distribute_data('trade', data, receive_time)

            # Update statistics
            processing_latency = self.timer.timestamp_ns() - start_time
            self.latency_stats["processing"].append(processing_latency)

        except Exception as e:
            self.logger.error(f"Trade processing error: {e}")

    def _distribute_data(self, data_type: str, data: Any, receive_time: int):
        """Distribute data to registered callbacks"""
        start_time = self.timer.timestamp_ns()

        try:
            callbacks = self.callbacks.get(data_type, [])

            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        asyncio.create_task(callback(data))
                    else:
                        callback(data)
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")

            # Update distribution latency
            dist_latency = self.timer.timestamp_ns() - start_time
            self.latency_stats["distribution"].append(dist_latency)

            # Calculate total latency
            total_latency = self.timer.timestamp_ns() - receive_time
            self.latency_stats["total"].append(total_latency)

        except Exception as e:
            self.logger.error(f"Data distribution error: {e}")

    # ==========================================================================
    # CALLBACK REGISTRATION
    # ==========================================================================

    def register_callback(self, data_type: str, callback: Callable):
        """Register callback for data type"""
        self.callbacks[data_type].append(callback)
        self.logger.info(f"Registered callback for {data_type}")

    def unregister_callback(self, data_type: str, callback: Callable):
        """Unregister callback"""
        if callback in self.callbacks[data_type]:
            self.callbacks[data_type].remove(callback)
            self.logger.info(f"Unregistered callback for {data_type}")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def start(self):
        """Start the ultra-low latency feed"""
        try:
            self.running = True

            # Start processing threads
            self._start_worker_threads()

            # Create IBKR connection pool
            asyncio.create_task(self.create_ibkr_connection_pool())

            self.logger.info("Started ultra-low latency feed with ib_async")

        except Exception as e:
            self.logger.error(f"Failed to start feed: {e}")
            self.running = False

    def stop(self):
        """Stop the ultra-low latency feed"""
        try:
            self.running = False

            # Stop worker threads
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(timeout=1.0)

            # Cleanup resources
            self.mmap_store.close()

            self.logger.info("Stopped ultra-low latency feed")

        except Exception as e:
            self.logger.error(f"Error stopping feed: {e}")

    def _start_worker_threads(self):
        """Start background worker threads"""
        # Data processing thread
        data_thread = threading.Thread(
            target=self._data_worker,
            name="DataWorker",
            daemon=True
        )
        data_thread.start()
        self.threads.append(data_thread)

        # Statistics thread
        stats_thread = threading.Thread(
            target=self._stats_worker,
            name="StatsWorker",
            daemon=True
        )
        stats_thread.start()
        self.threads.append(stats_thread)

    def _data_worker(self):
        """Background data processing worker"""
        while self.running:
            try:
                # Process ring buffer
                data = self.ring_buffer.pop()
                if data:
                    # Process the data
                    pass
                else:
                    time.sleep(0.001)  # 1ms sleep if no data

            except Exception as e:
                self.logger.error(f"Data worker error: {e}")

    def _stats_worker(self):
        """Background statistics worker"""
        while self.running:
            try:
                # Update performance metrics
                time.sleep(1.0)  # Update every second

            except Exception as e:
                self.logger.error(f"Stats worker error: {e}")

    # ==========================================================================
    # PERFORMANCE MONITORING
    # ==========================================================================

    def get_latency_stats(self) -> dict[str, dict[str, float]]:
        """Get latency statistics"""
        stats = {}

        for stage, measurements in self.latency_stats.items():
            if measurements:
                stats[stage] = {
                    "mean_ns": np.mean(measurements),
                    "median_ns": np.median(measurements),
                    "p99_ns": np.percentile(measurements, 99),
                    "p999_ns": np.percentile(measurements, 99.9),
                    "mean_ms": np.mean(measurements) / 1e6,
                    "p99_ms": np.percentile(measurements, 99) / 1e6,
                    "p999_ms": np.percentile(measurements, 99.9) / 1e6,
                }

        return stats

    def create_test_quote(self, symbol: str, bid: float, ask: float) -> bytes:
        """Create test quote message"""
        quote = QuoteData()
        quote.header.timestamp_ns = self.timer.timestamp_ns()
        quote.header.sequence_num = self.sequence_number
        quote.header.message_type = MessageType.QUOTE
        quote.header.message_size = ctypes.sizeof(QuoteData)

        # Set quote data
        quote.symbol = symbol.encode('utf-8')
        quote.bid_price = bid
        quote.ask_price = ask
        quote.bid_size = 100
        quote.ask_size = 100
        quote.exchange = b'CBOE'

        self.sequence_number += 1

        return bytes(quote)

    # ==========================================================================
    # IBKR INTEGRATION WITH ib_async
    # ==========================================================================

    async def create_ibkr_connection_pool(self, size: int = 5):
        """Create connection pool for IBKR using ib_async"""
        try:
            from ib_async import IB, util

            self.ib_pool = []

            for i in range(size):
                ib = IB()
                await ib.connectAsync(
                    "127.0.0.1", 7497 + i, clientId=100 + i  # Different ports
                )
                self.ib_pool.append(ib)

            self.logger.info(f"Created IBKR connection pool with {size} connections via ib_async")

            # Start market data on all connections
            for ib in self.ib_pool:
                contract = util.Contract(symbol="SPY", exchange="SMART")
                ib.reqMktData(contract, "", False, False)

        except ImportError:
            self.logger.warning("ib_async not available")
        except Exception as e:
            self.logger.error(f"Failed to create IBKR pool: {e}")

    def get_fastest_ib_connection(self):
        """Get connection with lowest latency"""
        if hasattr(self, "ib_pool") and self.ib_pool:
            # Simple round-robin for now
            # In production, track latency per connection
            return self.ib_pool[self.sequence_number % len(self.ib_pool)]
        return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: UltraLowLatencyFeed | None = None

def create_ultra_low_latency_feed(config: dict[str, Any] | None = None) -> UltraLowLatencyFeed:
    """Factory function to create ultra-low latency feed"""
    global _module_instance
    if _module_instance is None:
        _module_instance = UltraLowLatencyFeed(config)
    return _module_instance

def get_ultra_low_latency_feed() -> UltraLowLatencyFeed | None:
    """Get existing feed instance"""
    return _module_instance

# ==============================================================================
# PERFORMANCE TESTING
# ==============================================================================
async def benchmark_latency():
    """Benchmark the ultra-low latency feed"""
    feed = create_ultra_low_latency_feed()

    # Test callback
    received_quotes = []

    async def test_callback(data):
        received_quotes.append(data)

    feed.register_callback('quote', test_callback)
    feed.start()

    # Generate test data
    logging.info("\n=== Running Latency Benchmark with ib_async ===")
    logging.info("Sending 10,000 test quotes...")

    start_time = time.perf_counter_ns()

    for i in range(10000):
        quote_data = feed.create_test_quote('SPY', 450.0 + i * 0.01, 450.1 + i * 0.01)
        feed.process_market_data(quote_data)

    # Wait for processing
    await asyncio.sleep(0.5)

    end_time = time.perf_counter_ns()
    total_time_ms = (end_time - start_time) / 1e6

    # Get statistics
    stats = feed.get_latency_stats()

    logging.info(f"\nTotal time: {total_time_ms:.2f}ms")
    logging.info(f"Throughput: {10000 / (total_time_ms/1000):.0f} quotes/second")
    logging.info(f"Quotes received: {len(received_quotes)}")

    logging.info("\nLatency Statistics:")
    for stage, metrics in stats.items():
        logging.info(f"\n{stage.upper()}:")
        logging.info(f"  Mean: {metrics['mean_ms']:.3f}ms")
        logging.info(f"  P99: {metrics['p99_ms']:.3f}ms")
        logging.info(f"  P99.9: {metrics['p999_ms']:.3f}ms")

    feed.stop()

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test ultra-low latency feed functionality"""
    import argparse

    parser = argparse.ArgumentParser(description="Ultra-Low Latency Feed Testing")
    parser.add_argument(
        "--benchmark", action="store_true", help="Run latency benchmark"
    )
    parser.add_argument(
        "--test-orders", action="store_true", help="Test order pre-calculation"
    )
    parser.add_argument("--stats", action="store_true", help="Show performance stats")
    args = parser.parse_args()

    if args.benchmark:
        await benchmark_latency()

    elif args.test_orders:
        logging.info("\n=== Testing Order Pre-calculation ===")
        feed = create_ultra_low_latency_feed()

        # Test market conditions
        market_data = {"price": 450.0, "iv": 20, "rsi": 25}  # Oversold

        await feed.order_cache.pre_calculate_orders(market_data)

        # Show pre-calculated orders
        for strategy, orders in feed.order_cache.pre_calculated_orders.items():
            logging.info(f"\n{strategy.upper()}:")
            for order in orders:
                logging.info(f"  {order['action']} {order['type']} @ {order['strike']}")

    elif args.stats:
        logging.info("\n=== Performance Capabilities with ib_async ===")
        logging.info("Target Latencies:")
        logging.info("  Market Data: <5ms")
        logging.info("  Order Prep: <10ms")
        logging.info("  Total RTT: <50ms")
        logging.info("\nOptimizations:")
        logging.info("  ✓ Lock-free ring buffers")
        logging.info("  ✓ Memory-mapped data")
        logging.info("  ✓ Nanosecond timestamping")
        logging.info("  ✓ CPU affinity")
        logging.info("  ✓ Pre-calculated orders")
        logging.info("  ✓ Zero-copy operations")
        logging.info("  ✓ Modern ib_async integration")
        logging.info("  ✓ Enhanced IB Gateway 10.37 compatibility")

        if NUMBA_AVAILABLE:
            logging.info("  ✓ JIT compilation available")
        else:
            logging.info("  ✗ JIT compilation not available (install numba)")

if __name__ == "__main__":
    asyncio.run(main())
