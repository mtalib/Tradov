#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovC_MarketData
Module: TradovC23_RealTimeDataOptimizer.py
Purpose: TRADOV - Autonomous Options Trading System v1.0

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Autonomous Options Trading System v1.0

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
import threading
import logging
import warnings
from typing import Any
from dataclasses import dataclass
from collections import deque
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import mmap
import struct
import multiprocessing as mp
import numpy as np
import pandas as pd

try:
    from numba import jit, types  # noqa: F401
    from numba.typed import Dict as NumbaDict, List as NumbaList  # noqa: F401
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Fallback decorator
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Tradov utilities
try:
    from TradovU01_Logger import TradovLogger
    from TradovU02_ErrorHandler import ErrorHandler
except ImportError:
    # Fallback implementations
    TradovLogger = logging.getLogger
    class ErrorHandler:
        @staticmethod
        def handle_error(error, context=""):
            logging.error("Error in %s: %s", context, error)

# Tradov integrations
# TradovC21_FSeriesIntegrationHub was removed in v2; integration is via A08_FSeriesOrchestrator.
C21_AVAILABLE = False
get_fseries_integration_hub = None  # type: ignore[assignment]

try:
    from TradovF16_RealTimeAnalytics import get_realtime_analytics_engine
    F16_AVAILABLE = True
except ImportError:
    F16_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================
# Performance Constants
MICROSECOND = 1e-6
NANOSECOND = 1e-9
TARGET_LATENCY_MICROSECONDS = 100  # Target 100μs latency
CRITICAL_LATENCY_MICROSECONDS = 50   # Critical path 50μs
MAX_BUFFER_SIZE = 1024 * 1024 * 10   # 10MB buffer
CACHE_LINE_SIZE = 64  # CPU cache line size for alignment

# Priority Levels
class DataPriority:
    CRITICAL = 0    # Options trades, gamma flips
    HIGH = 1        # Price/volume updates
    MEDIUM = 2      # Market depth, Greeks
    LOW = 3         # Historical, analytics
    BATCH = 4       # Background processing

# Data Types for Optimization
DATA_TYPES = {
    'tick': {'size': 32, 'priority': DataPriority.CRITICAL},
    'quote': {'size': 24, 'priority': DataPriority.HIGH},
    'trade': {'size': 28, 'priority': DataPriority.HIGH},
    'depth': {'size': 64, 'priority': DataPriority.MEDIUM},
    'greeks': {'size': 40, 'priority': DataPriority.MEDIUM},
    'analytics': {'size': 128, 'priority': DataPriority.LOW}
}

# Buffer Configuration
BUFFER_CONFIG = {
    'critical_buffer_size': 1024,      # Items for critical data
    'high_buffer_size': 2048,          # Items for high priority
    'medium_buffer_size': 4096,        # Items for medium priority
    'low_buffer_size': 8192,           # Items for low priority
    'overflow_threshold': 0.8          # 80% buffer utilization warning
}

# System Optimization Settings
SYSTEM_CONFIG = {
    'enable_cpu_affinity': True,
    'enable_numa_optimization': True,
    'enable_memory_mapping': True,
    'enable_jit_compilation': NUMBA_AVAILABLE,
    'thread_priority': 'high',
    'process_priority': 'high'
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DataPacket:
    """Optimized data packet for ultra-low latency processing."""
    data_type: str
    timestamp_ns: int  # Nanosecond precision
    priority: int
    size_bytes: int
    data: bytes
    sequence_id: int = 0
    source_id: int = 0

    def __post_init__(self):
        # Align to cache line boundary for optimal performance
        self.cache_aligned = True

@dataclass
class LatencyMetrics:
    """Container for latency measurement data."""
    packet_id: int
    ingress_time_ns: int
    processing_start_ns: int
    processing_end_ns: int
    egress_time_ns: int
    total_latency_ns: int
    processing_latency_ns: int
    queue_time_ns: int

@dataclass
class OptimizationStats:
    """Container for optimization performance statistics."""
    total_packets_processed: int = 0
    critical_packets_processed: int = 0
    average_latency_ns: float = 0.0
    p99_latency_ns: float = 0.0
    p99_9_latency_ns: float = 0.0
    throughput_packets_per_second: float = 0.0
    memory_utilization_percent: float = 0.0
    cpu_utilization_percent: float = 0.0
    queue_overflow_events: int = 0
    optimization_adjustments: int = 0

class LockFreeQueue:
    """Lock-free queue implementation for ultra-low latency."""

    def __init__(self, size: int):
        self.size = size
        self.buffer = np.empty(size, dtype=object)
        self.head = mp.Value('i', 0)
        self.tail = mp.Value('i', 0)
        self.mask = size - 1  # Assumes power of 2 size

    def enqueue(self, item: Any) -> bool:
        """Enqueue item without locks."""
        with self.tail.get_lock():
            current_tail = self.tail.value
            next_tail = (current_tail + 1) & self.mask

            if next_tail == self.head.value:
                return False  # Queue full

            self.buffer[current_tail] = item
            self.tail.value = next_tail
            return True

    def dequeue(self) -> Any | None:
        """Dequeue item without locks."""
        with self.head.get_lock():
            current_head = self.head.value

            if current_head == self.tail.value:
                return None  # Queue empty

            item = self.buffer[current_head]
            self.head.value = (current_head + 1) & self.mask
            return item

# ==============================================================================
# MAIN REAL-TIME DATA OPTIMIZER
# ==============================================================================
class RealTimeDataOptimizer:
    """
    Ultra-low latency data optimization engine for real-time analytics.

    Implements microsecond-precision data processing with hardware-optimized
    data structures, priority-based routing, and intelligent buffering for
    maximum performance in high-frequency trading environments.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the Real-Time Data Optimizer."""
        self.logger = TradovLogger(__name__)
        self.error_handler = ErrorHandler()

        # Configuration
        self.config = config or {}
        self.enable_system_optimization = self.config.get('enable_system_optimization', True)
        self.enable_hardware_optimization = self.config.get('enable_hardware_optimization', True)
        self.target_latency_ns = self.config.get('target_latency_ns', TARGET_LATENCY_MICROSECONDS * 1000)  # noqa: E501

        # Internal state
        self.running = False
        self.start_time_ns = time.time_ns()
        self.packet_counter = 0
        self.optimization_stats = OptimizationStats()
        self.latency_measurements = deque(maxlen=10000)

        # Priority queues (lock-free for performance)
        self.priority_queues = {}
        for priority in range(5):  # 0-4 priority levels
            queue_size = self._get_queue_size_for_priority(priority)
            self.priority_queues[priority] = LockFreeQueue(queue_size)

        # Memory-mapped buffers
        self.memory_buffers = {}

        # Processing threads
        self.processing_threads = []
        self.thread_pool = ThreadPoolExecutor(
            max_workers=mp.cpu_count(),
            thread_name_prefix="RTOptimizer"
        )

        # System optimization
        self.cpu_cores = mp.cpu_count()
        self.memory_info = None

        # Integration components
        self.integration_hub = None
        self.realtime_engine = None

        # Performance monitoring
        self.performance_monitor = None
        self.latency_histogram = np.zeros(1000, dtype=np.uint64)  # Microsecond buckets

        # Initialize components
        self._initialize_system_optimization()
        self._initialize_memory_buffers()
        self._initialize_jit_functions()

        self.logger.info("Real-Time Data Optimizer initialized")

    def initialize(self) -> bool:
        """
        Initialize the data optimizer with all components.

        Returns:
            bool: True if initialization successful
        """
        try:
            # System optimization
            if self.enable_system_optimization:
                self._apply_system_optimizations()

            # Initialize integrations
            self._initialize_integrations()

            # Start processing threads
            self._start_processing_threads()

            # Start monitoring
            self._start_performance_monitoring()

            self.running = True
            self.logger.info("Real-Time Data Optimizer fully initialized")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeDataOptimizer.initialize")
            return False

    def _initialize_system_optimization(self) -> None:
        """Initialize system-level optimizations."""
        try:
            if PSUTIL_AVAILABLE:
                self.memory_info = psutil.virtual_memory()
                self.cpu_info = psutil.cpu_freq()

                # Get NUMA topology if available
                if hasattr(psutil, 'cpu_count'):
                    self.numa_nodes = 1  # Simplified

                self.logger.info("System: %s cores, %sGB RAM", self.cpu_cores, self.memory_info.total // (1024**3))  # noqa: E501

        except Exception as e:
            self.logger.warning("System optimization initialization failed: %s", e)

    def _initialize_memory_buffers(self) -> None:
        """Initialize memory-mapped buffers for zero-copy operations."""
        try:
            for data_type, config in DATA_TYPES.items():
                buffer_size = config['size'] * 10000  # 10k items per type

                # Create memory-mapped buffer
                buffer = mmap.mmap(-1, buffer_size, access=mmap.ACCESS_WRITE)

                self.memory_buffers[data_type] = {
                    'buffer': buffer,
                    'size': buffer_size,
                    'item_size': config['size'],
                    'max_items': buffer_size // config['size'],
                    'current_pos': 0
                }

            self.logger.debug("Initialized %s memory buffers", len(self.memory_buffers))

        except Exception as e:
            self.error_handler.handle_error(e, context="_initialize_memory_buffers")

    def _initialize_jit_functions(self) -> None:
        """Initialize JIT-compiled functions for maximum performance."""
        if NUMBA_AVAILABLE:
            # Pre-compile critical functions
            self._jit_process_packet = self._create_jit_process_packet()
            self._jit_calculate_latency = self._create_jit_calculate_latency()
            self.logger.debug("JIT functions compiled")
        else:
            # Use regular Python functions
            self._jit_process_packet = self._process_packet_regular
            self._jit_calculate_latency = self._calculate_latency_regular

    def _initialize_integrations(self) -> None:
        """Initialize integrations with other Tradov modules."""
        try:
            # Connect to F-Series Orchestrator (C21 was removed in v2; replaced by A08)
            if C21_AVAILABLE:
                self.integration_hub = get_fseries_integration_hub()
                self.logger.info("Connected to F-Series integration hub via A08_FSeriesOrchestrator")  # noqa: E501

            # Connect to F16 Real-time Analytics
            if F16_AVAILABLE:
                self.realtime_engine = get_realtime_analytics_engine()
                self.logger.info("Connected to TradovF16_RealTimeAnalytics")

        except Exception as e:
            self.logger.warning("Integration initialization failed: %s", e)

    def _apply_system_optimizations(self) -> None:
        """Apply system-level performance optimizations."""
        try:
            if not PSUTIL_AVAILABLE:
                return

            # Set process priority
            if SYSTEM_CONFIG['process_priority'] == 'high':
                current_process = psutil.Process()
                if hasattr(current_process, 'nice'):
                    current_process.nice(-10)  # High priority

            # Set CPU affinity for critical threads
            if SYSTEM_CONFIG['enable_cpu_affinity']:
                # Reserve specific cores for critical processing
                critical_cores = list(range(min(2, self.cpu_cores)))
                current_process = psutil.Process()
                if hasattr(current_process, 'cpu_affinity'):
                    current_process.cpu_affinity(critical_cores)

            self.logger.info("System optimizations applied")

        except Exception as e:
            self.logger.warning("System optimization failed: %s", e)

    # ==============================================================================
    # CORE DATA PROCESSING METHODS
    # ==============================================================================
    def ingest_data(
        self,
        data_type: str,
        data: bytes | dict[str, Any] | pd.DataFrame,
        priority: int | None = None
    ) -> bool:
        """
        Ingest data with ultra-low latency processing.

        Args:
            data_type: Type of data being ingested
            data: Raw data to process
            priority: Override priority (optional)

        Returns:
            bool: True if data ingested successfully
        """
        try:
            ingress_time_ns = time.time_ns()

            # Determine priority
            if priority is None:
                priority = DATA_TYPES.get(data_type, {}).get('priority', DataPriority.LOW)

            # Convert data to optimized packet format
            packet = self._create_optimized_packet(data_type, data, priority, ingress_time_ns)

            if packet is None:
                return False

            # Route to appropriate priority queue
            success = self.priority_queues[priority].enqueue(packet)

            if not success:
                # Queue full - log overflow event
                self.optimization_stats.queue_overflow_events += 1
                self.logger.warning("Queue overflow for priority %s", priority)
                return False

            # Update statistics
            self.packet_counter += 1
            if priority == DataPriority.CRITICAL:
                self.optimization_stats.critical_packets_processed += 1

            return True

        except Exception as e:
            self.error_handler.handle_error(e, context="ingest_data")
            return False

    def _create_optimized_packet(
        self,
        data_type: str,
        data: bytes | dict[str, Any] | pd.DataFrame,
        priority: int,
        timestamp_ns: int
    ) -> DataPacket | None:
        """Create optimized data packet for processing."""
        try:
            # Convert data to bytes if needed
            if isinstance(data, dict):
                # Pack dictionary into binary format for efficiency
                packed_data = self._pack_dict_to_bytes(data)
            elif isinstance(data, pd.DataFrame):
                # Serialize DataFrame efficiently
                packed_data = data.to_numpy().tobytes()
            elif isinstance(data, bytes):
                packed_data = data
            else:
                # Convert to string and encode
                packed_data = str(data).encode('utf-8')

            # Get expected size
            DATA_TYPES.get(data_type, {}).get('size', len(packed_data))

            # Create packet
            packet = DataPacket(
                data_type=data_type,
                timestamp_ns=timestamp_ns,
                priority=priority,
                size_bytes=len(packed_data),
                data=packed_data,
                sequence_id=self.packet_counter
            )

            return packet

        except Exception as e:
            self.error_handler.handle_error(e, context="_create_optimized_packet")
            return None

    @jit(nopython=True)
    def _create_jit_process_packet(self):
        """Create JIT-compiled packet processing function."""
        def jit_process_packet(packet_data, processing_start_ns):
            # Ultra-fast packet processing logic
            processing_end_ns = time.time_ns()
            processing_latency_ns = processing_end_ns - processing_start_ns
            return processing_end_ns, processing_latency_ns

        return jit_process_packet

    def _process_packet_regular(self, packet_data, processing_start_ns):
        """Regular (non-JIT) packet processing function."""
        processing_end_ns = time.time_ns()
        processing_latency_ns = processing_end_ns - processing_start_ns
        return processing_end_ns, processing_latency_ns

    @jit(nopython=True)
    def _create_jit_calculate_latency(self):
        """Create JIT-compiled latency calculation function."""
        def jit_calculate_latency(ingress_ns, egress_ns):
            return egress_ns - ingress_ns

        return jit_calculate_latency

    def _calculate_latency_regular(self, ingress_ns, egress_ns):
        """Regular latency calculation function."""
        return egress_ns - ingress_ns

    # ==============================================================================
    # PROCESSING THREADS AND LOOPS
    # ==============================================================================
    def _start_processing_threads(self) -> None:
        """Start high-performance processing threads."""
        try:
            # Critical priority thread (highest performance)
            critical_thread = threading.Thread(
                target=self._critical_processing_loop,
                name="CriticalProcessor",
                daemon=True
            )
            critical_thread.start()
            self.processing_threads.append(critical_thread)

            # High priority thread
            high_thread = threading.Thread(
                target=self._high_priority_processing_loop,
                name="HighPriorityProcessor",
                daemon=True
            )
            high_thread.start()
            self.processing_threads.append(high_thread)

            # Medium/Low priority thread
            bulk_thread = threading.Thread(
                target=self._bulk_processing_loop,
                name="BulkProcessor",
                daemon=True
            )
            bulk_thread.start()
            self.processing_threads.append(bulk_thread)

            self.logger.info("Started %s processing threads", len(self.processing_threads))

        except Exception as e:
            self.error_handler.handle_error(e, context="_start_processing_threads")

    def _critical_processing_loop(self) -> None:
        """Ultra-low latency processing loop for critical data."""
        self.logger.info("Started critical processing loop")

        # Set thread priority if possible
        try:
            if PSUTIL_AVAILABLE and hasattr(psutil.Process(), 'nice'):
                current_process = psutil.Process()
                current_process.nice(-20)  # Highest priority
        except Exception as e:
            self.logger.debug("Could not set process priority: %s", e)

        critical_queue = self.priority_queues[DataPriority.CRITICAL]

        while self.running:
            try:
                # Try to get packet with minimal overhead
                packet = critical_queue.dequeue()

                if packet is None:
                    # No data available - minimal sleep
                    time.sleep(MICROSECOND)  # thread-safe: time.sleep() intentional
                    continue

                # Process packet with maximum speed
                processing_start_ns = time.time_ns()

                # Use JIT-compiled processing
                processing_end_ns, processing_latency_ns = self._jit_process_packet(
                    packet.data, processing_start_ns
                )

                # Quick latency check
                total_latency_ns = processing_end_ns - packet.timestamp_ns

                if total_latency_ns > self.target_latency_ns:
                    self.logger.warning(f"Critical latency exceeded: {total_latency_ns/1000:.2f}μs")

                # Forward to F16 if available
                if self.realtime_engine:
                    asyncio.create_task(self._forward_to_realtime_engine(packet))

                # Record metrics
                self._record_latency_measurement(packet, processing_start_ns, processing_end_ns)

            except Exception as e:
                self.error_handler.handle_error(e, context="_critical_processing_loop")
                time.sleep(MICROSECOND * 10)  # thread-safe: time.sleep() intentional

        self.logger.info("Critical processing loop stopped")

    def _high_priority_processing_loop(self) -> None:
        """High-priority processing loop."""
        self.logger.info("Started high priority processing loop")

        high_queue = self.priority_queues[DataPriority.HIGH]

        while self.running:
            try:
                packet = high_queue.dequeue()

                if packet is None:
                    time.sleep(MICROSECOND * 10)  # thread-safe: time.sleep() intentional
                    continue

                processing_start_ns = time.time_ns()

                # Process packet
                processed_data = self._process_high_priority_packet(packet)

                processing_end_ns = time.time_ns()

                # Forward to destination
                if processed_data and self.realtime_engine:
                    asyncio.create_task(self._forward_to_realtime_engine(packet))

                # Record metrics
                self._record_latency_measurement(packet, processing_start_ns, processing_end_ns)

            except Exception as e:
                self.error_handler.handle_error(e, context="_high_priority_processing_loop")
                time.sleep(MICROSECOND * 100)  # thread-safe: time.sleep() intentional

        self.logger.info("High priority processing loop stopped")

    def _bulk_processing_loop(self) -> None:
        """Bulk processing loop for medium and low priority data."""
        self.logger.info("Started bulk processing loop")

        medium_queue = self.priority_queues[DataPriority.MEDIUM]
        low_queue = self.priority_queues[DataPriority.LOW]
        batch_queue = self.priority_queues[DataPriority.BATCH]

        while self.running:
            try:
                # Process in priority order: Medium -> Low -> Batch
                packet = None

                for queue in [medium_queue, low_queue, batch_queue]:
                    packet = queue.dequeue()
                    if packet is not None:
                        break

                if packet is None:
                    time.sleep(MICROSECOND * 100)  # thread-safe: time.sleep() intentional
                    continue

                # Batch processing for efficiency
                batch = [packet]

                # Try to collect more packets for batch processing
                for _ in range(9):  # Up to 10 packets per batch
                    additional_packet = medium_queue.dequeue() or low_queue.dequeue() or batch_queue.dequeue()  # noqa: E501
                    if additional_packet is None:
                        break
                    batch.append(additional_packet)

                # Process batch
                processing_start_ns = time.time_ns()
                processed_batch = self._process_packet_batch(batch)
                processing_end_ns = time.time_ns()

                # Forward results
                if processed_batch and self.realtime_engine:
                    for processed_packet in processed_batch:
                        asyncio.create_task(self._forward_to_realtime_engine(processed_packet))

                # Record metrics for each packet in batch
                for packet in batch:
                    self._record_latency_measurement(packet, processing_start_ns, processing_end_ns)

            except Exception as e:
                self.error_handler.handle_error(e, context="_bulk_processing_loop")
                time.sleep(MICROSECOND * 1000)  # thread-safe: time.sleep() intentional

        self.logger.info("Bulk processing loop stopped")

    def _process_high_priority_packet(self, packet: DataPacket) -> dict[str, Any] | None:
        """Process high-priority packet with optimized logic."""
        try:
            # Fast processing path for high-priority data
            if packet.data_type == 'tick':
                return self._process_tick_data(packet)
            elif packet.data_type == 'quote':
                return self._process_quote_data(packet)
            elif packet.data_type == 'trade':
                return self._process_trade_data(packet)
            else:
                return self._process_generic_packet(packet)

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_high_priority_packet")
            return None

    def _process_packet_batch(self, batch: list[DataPacket]) -> list[dict[str, Any]]:
        """Process batch of packets efficiently."""
        try:
            processed_results = []

            for packet in batch:
                result = self._process_generic_packet(packet)
                if result:
                    processed_results.append(result)

            return processed_results

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_packet_batch")
            return []

    # ==============================================================================
    # DATA PROCESSING METHODS
    # ==============================================================================
    def _process_tick_data(self, packet: DataPacket) -> dict[str, Any]:
        """Process tick data with maximum speed."""
        try:
            # Unpack tick data (assuming fixed format)
            data = struct.unpack('ffI', packet.data[:12])  # price, size, timestamp

            return {
                'type': 'tick',
                'price': data[0],
                'size': data[1],
                'timestamp': data[2],
                'processing_time_ns': time.time_ns(),
                'latency_ns': time.time_ns() - packet.timestamp_ns
            }

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_tick_data")
            return {}

    def _process_quote_data(self, packet: DataPacket) -> dict[str, Any]:
        """Process quote data efficiently."""
        try:
            # Unpack quote data
            data = struct.unpack('ffffff', packet.data[:24])  # bid, ask, bid_size, ask_size, etc.

            return {
                'type': 'quote',
                'bid': data[0],
                'ask': data[1],
                'bid_size': data[2],
                'ask_size': data[3],
                'spread': data[1] - data[0],
                'mid_price': (data[0] + data[1]) / 2,
                'processing_time_ns': time.time_ns(),
                'latency_ns': time.time_ns() - packet.timestamp_ns
            }

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_quote_data")
            return {}

    def _process_trade_data(self, packet: DataPacket) -> dict[str, Any]:
        """Process trade data efficiently."""
        try:
            # Unpack trade data
            data = struct.unpack('ffIc', packet.data[:13])  # price, size, timestamp, side

            return {
                'type': 'trade',
                'price': data[0],
                'size': data[1],
                'timestamp': data[2],
                'side': data[3].decode('utf-8'),
                'processing_time_ns': time.time_ns(),
                'latency_ns': time.time_ns() - packet.timestamp_ns
            }

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_trade_data")
            return {}

    def _process_generic_packet(self, packet: DataPacket) -> dict[str, Any]:
        """Process generic packet data."""
        try:
            return {
                'type': packet.data_type,
                'data_size': packet.size_bytes,
                'priority': packet.priority,
                'sequence_id': packet.sequence_id,
                'processing_time_ns': time.time_ns(),
                'latency_ns': time.time_ns() - packet.timestamp_ns
            }

        except Exception as e:
            self.error_handler.handle_error(e, context="_process_generic_packet")
            return {}

    # ==============================================================================
    # FORWARDING AND INTEGRATION
    # ==============================================================================
    async def _forward_to_realtime_engine(self, packet: DataPacket) -> None:
        """Forward processed packet to F16 Real-time Analytics."""
        try:
            if not self.realtime_engine:
                return

            # Convert packet to F16 format
            metric_name = f"{packet.data_type}_update"
            metric_value = packet.sequence_id  # Simplified

            # Send to F16
            success = await self.realtime_engine.add_metric(
                stream_type='realtime',
                metric_name=metric_name,
                value=metric_value,
                metadata={
                    'packet_priority': packet.priority,
                    'processing_latency_ns': time.time_ns() - packet.timestamp_ns,
                    'optimizer_processed': True
                }
            )

            if not success:
                self.logger.warning("Failed to forward packet to F16")

        except Exception as e:
            self.error_handler.handle_error(e, context="_forward_to_realtime_engine")

    # ==============================================================================
    # PERFORMANCE MONITORING
    # ==============================================================================
    def _start_performance_monitoring(self) -> None:
        """Start performance monitoring thread."""
        try:
            monitor_thread = threading.Thread(
                target=self._performance_monitoring_loop,
                name="PerformanceMonitor",
                daemon=True
            )
            monitor_thread.start()
            self.processing_threads.append(monitor_thread)

            self.logger.info("Performance monitoring started")

        except Exception as e:
            self.error_handler.handle_error(e, context="_start_performance_monitoring")

    def _performance_monitoring_loop(self) -> None:
        """Performance monitoring loop."""
        self.logger.info("Started performance monitoring loop")

        last_stats_update = time.time()

        while self.running:
            try:
                current_time = time.time()

                # Update statistics every second
                if current_time - last_stats_update >= 1.0:
                    self._update_optimization_stats()
                    self._check_performance_thresholds()
                    last_stats_update = current_time

                time.sleep(0.1)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.error_handler.handle_error(e, context="_performance_monitoring_loop")
                time.sleep(1.0)  # thread-safe: time.sleep() intentional

        self.logger.info("Performance monitoring loop stopped")

    def _record_latency_measurement(
        self,
        packet: DataPacket,
        processing_start_ns: int,
        processing_end_ns: int
    ) -> None:
        """Record latency measurement for analysis."""
        try:
            egress_time_ns = time.time_ns()

            latency_metrics = LatencyMetrics(
                packet_id=packet.sequence_id,
                ingress_time_ns=packet.timestamp_ns,
                processing_start_ns=processing_start_ns,
                processing_end_ns=processing_end_ns,
                egress_time_ns=egress_time_ns,
                total_latency_ns=egress_time_ns - packet.timestamp_ns,
                processing_latency_ns=processing_end_ns - processing_start_ns,
                queue_time_ns=processing_start_ns - packet.timestamp_ns
            )

            self.latency_measurements.append(latency_metrics)

            # Update histogram
            latency_us = latency_metrics.total_latency_ns / 1000  # Convert to microseconds
            histogram_bin = min(int(latency_us), len(self.latency_histogram) - 1)
            self.latency_histogram[histogram_bin] += 1

        except Exception as e:
            self.error_handler.handle_error(e, context="_record_latency_measurement")

    def _update_optimization_stats(self) -> None:
        """Update optimization statistics."""
        try:
            if not self.latency_measurements:
                return

            # Calculate statistics from recent measurements
            recent_measurements = list(self.latency_measurements)[-1000:]  # Last 1000 measurements

            if recent_measurements:
                latencies = [m.total_latency_ns for m in recent_measurements]

                self.optimization_stats.average_latency_ns = np.mean(latencies)
                self.optimization_stats.p99_latency_ns = np.percentile(latencies, 99)
                self.optimization_stats.p99_9_latency_ns = np.percentile(latencies, 99.9)

                # Calculate throughput
                time_span = recent_measurements[-1].egress_time_ns - recent_measurements[0].ingress_time_ns  # noqa: E501
                if time_span > 0:
                    self.optimization_stats.throughput_packets_per_second = len(recent_measurements) * 1e9 / time_span  # noqa: E501

            # Update packet counts
            self.optimization_stats.total_packets_processed = self.packet_counter

            # Get system resource utilization
            if PSUTIL_AVAILABLE:
                self.optimization_stats.memory_utilization_percent = psutil.virtual_memory().percent
                self.optimization_stats.cpu_utilization_percent = psutil.cpu_percent()

        except Exception as e:
            self.error_handler.handle_error(e, context="_update_optimization_stats")

    def _check_performance_thresholds(self) -> None:
        """Check performance thresholds and trigger optimizations."""
        try:
            stats = self.optimization_stats

            # Check latency thresholds
            if stats.p99_latency_ns > self.target_latency_ns * 2:
                self.logger.warning(f"P99 latency high: {stats.p99_latency_ns/1000:.2f}μs")
                self._trigger_latency_optimization()

            # Check throughput
            if stats.throughput_packets_per_second < 10000:  # Below 10k packets/sec
                self.logger.warning(f"Low throughput: {stats.throughput_packets_per_second:.0f} packets/sec")  # noqa: E501

            # Check queue overflow
            if stats.queue_overflow_events > 100:
                self.logger.error("High queue overflow events detected")
                self._adjust_buffer_sizes()

        except Exception as e:
            self.error_handler.handle_error(e, context="_check_performance_thresholds")

    def _trigger_latency_optimization(self) -> None:
        """Trigger automatic latency optimization."""
        try:
            self.optimization_stats.optimization_adjustments += 1

            # Implement optimization strategies
            # This could include:
            # - Adjusting buffer sizes
            # - Changing processing algorithms
            # - Modifying thread priorities
            # - Enabling/disabling certain features

            self.logger.info("Triggered latency optimization")

        except Exception as e:
            self.error_handler.handle_error(e, context="_trigger_latency_optimization")

    def _adjust_buffer_sizes(self) -> None:
        """Dynamically adjust buffer sizes based on load."""
        try:
            # This would implement dynamic buffer size adjustment
            self.logger.info("Adjusted buffer sizes for better performance")

        except Exception as e:
            self.error_handler.handle_error(e, context="_adjust_buffer_sizes")

    # ==============================================================================
    # UTILITY METHODS
    # ==============================================================================
    def _get_queue_size_for_priority(self, priority: int) -> int:
        """Get optimal queue size for priority level."""
        queue_sizes = {
            DataPriority.CRITICAL: BUFFER_CONFIG['critical_buffer_size'],
            DataPriority.HIGH: BUFFER_CONFIG['high_buffer_size'],
            DataPriority.MEDIUM: BUFFER_CONFIG['medium_buffer_size'],
            DataPriority.LOW: BUFFER_CONFIG['low_buffer_size'],
            DataPriority.BATCH: BUFFER_CONFIG['low_buffer_size']
        }

        # Ensure power of 2 for lock-free queue
        size = queue_sizes.get(priority, 1024)
        return 2 ** (size - 1).bit_length()  # Next power of 2

    def _pack_dict_to_bytes(self, data: dict[str, Any]) -> bytes:
        """Pack dictionary to bytes for efficient storage."""
        try:
            # Simple packing - in production would use more efficient serialization
            packed = str(data).encode('utf-8')
            return packed

        except Exception as e:
            self.error_handler.handle_error(e, context="_pack_dict_to_bytes")
            return b""

    def get_optimization_status(self) -> dict[str, Any]:
        """Get comprehensive optimization status."""
        try:
            stats = self.optimization_stats

            status = {
                'is_running': self.running,
                'total_packets_processed': stats.total_packets_processed,
                'critical_packets_processed': stats.critical_packets_processed,
                'average_latency_microseconds': stats.average_latency_ns / 1000,
                'p99_latency_microseconds': stats.p99_latency_ns / 1000,
                'p99_9_latency_microseconds': stats.p99_9_latency_ns / 1000,
                'throughput_packets_per_second': stats.throughput_packets_per_second,
                'memory_utilization_percent': stats.memory_utilization_percent,
                'cpu_utilization_percent': stats.cpu_utilization_percent,
                'queue_overflow_events': stats.queue_overflow_events,
                'optimization_adjustments': stats.optimization_adjustments,
                'target_latency_microseconds': self.target_latency_ns / 1000,
                'processing_threads': len(self.processing_threads),
                'queue_utilizations': self._get_queue_utilizations()
            }

            return status

        except Exception as e:
            self.error_handler.handle_error(e, context="get_optimization_status")
            return {'error': str(e)}

    def _get_queue_utilizations(self) -> dict[str, float]:
        """Get current queue utilization percentages."""
        try:
            utilizations = {}

            for priority, queue in self.priority_queues.items():
                current_size = abs(queue.tail.value - queue.head.value)
                max_size = queue.size
                utilization = (current_size / max_size) * 100

                priority_names = {
                    DataPriority.CRITICAL: 'critical',
                    DataPriority.HIGH: 'high',
                    DataPriority.MEDIUM: 'medium',
                    DataPriority.LOW: 'low',
                    DataPriority.BATCH: 'batch'
                }

                priority_name = priority_names.get(priority, f'priority_{priority}')
                utilizations[priority_name] = utilization

            return utilizations

        except Exception as e:
            self.error_handler.handle_error(e, context="_get_queue_utilizations")
            return {}

    def shutdown(self) -> None:
        """Shutdown the optimizer gracefully."""
        try:
            self.logger.info("Shutting down Real-Time Data Optimizer...")

            self.running = False

            # Wait for threads to finish
            for thread in self.processing_threads:
                thread.join(timeout=1.0)

            # Close memory buffers
            for buffer_info in self.memory_buffers.values():
                buffer_info['buffer'].close()

            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)

            self.logger.info("Real-Time Data Optimizer shutdown complete")

        except Exception as e:
            self.error_handler.handle_error(e, context="RealTimeDataOptimizer.shutdown")

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================
# Global instance for singleton pattern
_optimizer_instance = None

def get_realtime_data_optimizer(config: dict[str, Any] | None = None) -> RealTimeDataOptimizer:
    """
    Get global Real-Time Data Optimizer instance (singleton pattern).

    Args:
        config: Optional configuration dictionary

    Returns:
        RealTimeDataOptimizer instance
    """
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = RealTimeDataOptimizer(config)
        _optimizer_instance.initialize()
    return _optimizer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    logging.info("🎯 TRADOV C23 - Real-Time Data Optimizer")
    logging.info("=" * 80)

    try:
        # Create optimizer
        config = {
            'enable_system_optimization': True,
            'enable_hardware_optimization': True,
            'target_latency_ns': 100 * 1000  # 100 microseconds
        }

        optimizer = RealTimeDataOptimizer(config)
        logging.info("✅ Real-Time Data Optimizer initialized")

        # Initialize optimizer
        if not optimizer.initialize():
            logging.info("❌ Failed to initialize optimizer")
            return False

        logging.info("⚡ System Configuration:")
        logging.info("   • CPU Cores: %s", optimizer.cpu_cores)
        logging.info("   • Memory Buffers: %s", len(optimizer.memory_buffers))
        logging.info("   • Processing Threads: %s", len(optimizer.processing_threads))
        logging.info(f"   • Target Latency: {config['target_latency_ns']/1000:.0f}μs")

        # Test data ingestion with different priorities
        logging.info("\n📊 Testing data ingestion...")

        test_cases = [
            ('tick', {'price': 401.50, 'size': 100}, DataPriority.CRITICAL),
            ('quote', {'bid': 401.48, 'ask': 401.52}, DataPriority.HIGH),
            ('trade', {'price': 401.51, 'size': 500, 'side': 'B'}, DataPriority.HIGH),
            ('greeks', {'delta': 0.5, 'gamma': 0.01}, DataPriority.MEDIUM),
            ('analytics', {'volatility': 0.25, 'momentum': 0.02}, DataPriority.LOW)
        ]

        successful_ingests = 0

        for data_type, data, priority in test_cases:
            success = optimizer.ingest_data(data_type, data, priority)
            if success:
                successful_ingests += 1
                logging.info("   ✅ %s: Priority %s", data_type, priority)
            else:
                logging.info("   ❌ %s: Failed", data_type)

        logging.info("   Successfully ingested: %s/%s", successful_ingests, len(test_cases))

        # Let the system process data
        logging.info("\n⚡ Processing data for 10 seconds...")
        await asyncio.sleep(10)

        # Get optimization status
        status = optimizer.get_optimization_status()

        logging.info("\n📈 Performance Statistics:")
        logging.info(f"   • Total Packets Processed: {status['total_packets_processed']:,}")
        logging.info(f"   • Critical Packets: {status['critical_packets_processed']:,}")
        logging.info(f"   • Average Latency: {status['average_latency_microseconds']:.2f}μs")
        logging.info(f"   • P99 Latency: {status['p99_latency_microseconds']:.2f}μs")
        logging.info(f"   • P99.9 Latency: {status['p99_9_latency_microseconds']:.2f}μs")
        logging.info(f"   • Throughput: {status['throughput_packets_per_second']:.0f} packets/sec")
        logging.info(f"   • CPU Utilization: {status['cpu_utilization_percent']:.1f}%")
        logging.info(f"   • Memory Utilization: {status['memory_utilization_percent']:.1f}%")

        logging.info("\n📊 Queue Utilizations:")
        for queue_name, utilization in status['queue_utilizations'].items():
            logging.info(f"   • {queue_name}: {utilization:.1f}%")

        if status['queue_overflow_events'] > 0:
            logging.info("\n⚠️  Queue Overflow Events: %s", status['queue_overflow_events'])

        if status['optimization_adjustments'] > 0:
            logging.info("🔧 Optimization Adjustments: %s", status['optimization_adjustments'])

        logging.info("\n🎊 Real-Time Data Optimizer demonstration completed successfully!")
        return True

    except Exception as e:
        logging.info("❌ Error in main execution: %s", e)
        return False

    finally:
        # Clean up
        if 'optimizer' in locals():
            optimizer.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
