#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderZ_Communication
Module: SpyderZ07_MultiProcessManager.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import signal
import psutil
import multiprocessing as mp
from multiprocessing import shared_memory
import struct
import zmq
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderZ03_TradingCoordinator import (
    EngineType, COORDINATOR_MONITOR_PORT, create_engine_client
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Process configuration
MAX_RESTART_ATTEMPTS = 3
RESTART_DELAY = 5.0  # seconds
PROCESS_STARTUP_TIMEOUT = 30.0  # seconds
HEALTH_CHECK_INTERVAL = 2.0  # seconds
MEMORY_CHECK_INTERVAL = 10.0  # seconds

# Shared memory configuration
TICK_BUFFER_SIZE = 1024 * 1024 * 10  # 10MB for tick data
TICK_BUFFER_NAME = "spyder_tick_buffer"
MAX_TICKS_PER_SYMBOL = 1000

# Resource limits
MAX_CPU_PERCENT = 80.0  # Max CPU usage per process
MAX_MEMORY_MB = 2048    # Max memory per process (2GB)
MIN_FREE_MEMORY_MB = 1024  # Min system free memory

# Process priorities (nice values)
PROCESS_PRIORITIES = {
    EngineType.VOLATILITY: -5,     # Higher priority
    EngineType.ANOMALY: 0,         # Normal priority
    EngineType.HEDGER: -3,         # Medium-high priority
    EngineType.EXECUTION: -10      # Highest priority
}

# ==============================================================================
# ENUMS
# ==============================================================================
class ProcessState(Enum):
    """Process lifecycle states."""
    INITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()
    RESTARTING = auto()

class ResourceAction(Enum):
    """Resource management actions."""
    NONE = auto()
    THROTTLE = auto()
    RESTART = auto()
    KILL = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ProcessInfo:
    """Information about a managed process."""
    engine_type: EngineType
    process_class: type
    process: mp.Process | None = None
    pid: int | None = None
    state: ProcessState = ProcessState.INITIALIZED
    start_time: float | None = None
    restart_count: int = 0
    last_heartbeat: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    error_count: int = 0

    def is_alive(self) -> bool:
        """Check if process is alive."""
        return self.process is not None and self.process.is_alive()

    def get_uptime(self) -> float:
        """Get process uptime in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

@dataclass
class SharedTickData:
    """Structure for tick data in shared memory."""
    symbol: str
    timestamp: float
    bid: float
    ask: float
    last: float
    volume: int
    bid_size: int
    ask_size: int

    @classmethod
    def size(cls) -> int:
        """Get size of structure in bytes."""
        # 16 chars for symbol + 6 floats + 2 ints
        return 16 + (6 * 8) + (2 * 4)

    def to_bytes(self) -> bytes:
        """Convert to bytes for shared memory."""
        # Pack: 16s = 16 char string, d = double, i = int
        return struct.pack(
            '16sdddddii',
            self.symbol.encode('utf-8')[:16],
            self.timestamp,
            self.bid,
            self.ask,
            self.last,
            float(self.volume),
            self.bid_size,
            self.ask_size
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> 'SharedTickData':
        """Create from bytes."""
        unpacked = struct.unpack('16sdddddii', data)
        return cls(
            symbol=unpacked[0].decode('utf-8').strip('\x00'),
            timestamp=unpacked[1],
            bid=unpacked[2],
            ask=unpacked[3],
            last=unpacked[4],
            volume=int(unpacked[5]),
            bid_size=unpacked[6],
            ask_size=unpacked[7]
        )

@dataclass
class SystemResources:
    """System resource snapshot."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_percent: float
    process_count: int
    timestamp: float = field(default_factory=time.time)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MultiProcessManager:
    """
    Manages lifecycle of all SPYDER trading processes.

    This class spawns, monitors, and manages all trading engine processes.
    It provides automatic restart on failure, resource monitoring, and
    shared memory management for high-performance data sharing.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        processes: Dictionary of managed processes
        shared_memory: Shared memory for tick data

    Example:
        >>> manager = MultiProcessManager()
        >>> manager.initialize()
        >>> manager.start_all_processes()
    """

    def __init__(self):
        """Initialize the multi-process manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Process management
        self.processes: dict[EngineType, ProcessInfo] = {}
        self.process_lock = threading.Lock()

        # Shared memory
        self.shared_mem: shared_memory.SharedMemory | None = None
        self.tick_buffer: np.ndarray | None = None
        self.tick_index = mp.Value('i', 0)  # Shared counter

        # ZeroMQ communication
        self.context = zmq.Context()
        self.monitor_socket = None

        # Resource monitoring
        self.resource_history: list[SystemResources] = []
        self.max_history_size = 100

        # Control flags
        self.running = mp.Event()
        self.shutdown_event = mp.Event()

        # Monitoring threads
        self.health_thread = None
        self.resource_thread = None

        self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize manager components.

        Returns:
            bool: True if initialization successful
        """
        try:
            # Initialize shared memory
            self._init_shared_memory()

            # Set up signal handlers
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)

            # Connect to coordinator for monitoring
            self.monitor_socket = self.context.socket(zmq.REQ)
            self.monitor_socket.connect(f"tcp://localhost:{COORDINATOR_MONITOR_PORT}")

            self.logger.info("MultiProcessManager initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            return False

    def register_process(self, engine_type: EngineType, process_class: type) -> None:
        """
        Register a process class for an engine type.

        Args:
            engine_type: Type of engine
            process_class: Class to instantiate for this engine
        """
        with self.process_lock:
            self.processes[engine_type] = ProcessInfo(
                engine_type=engine_type,
                process_class=process_class
            )

        self.logger.info("Registered process for %s", engine_type.value)

    def start_all_processes(self) -> None:
        """Start all registered processes."""
        self.running.set()

        # Start monitoring threads
        self.health_thread = threading.Thread(
            target=self._health_monitor_loop,
            name="HealthMonitor",
            daemon=True
        )
        self.health_thread.start()

        self.resource_thread = threading.Thread(
            target=self._resource_monitor_loop,
            name="ResourceMonitor",
            daemon=True
        )
        self.resource_thread.start()

        # Start processes
        with self.process_lock:
            for _engine_type, proc_info in self.processes.items():
                self._start_process(proc_info)

        self.logger.info("All processes started")

    def stop_all_processes(self, timeout: float = 10.0) -> None:
        """
        Stop all processes gracefully.

        Args:
            timeout: Maximum time to wait for process shutdown
        """
        self.running.clear()
        self.shutdown_event.set()

        # Stop processes
        with self.process_lock:
            for proc_info in self.processes.values():
                self._stop_process(proc_info, timeout)

        # Wait for monitoring threads
        if self.health_thread:
            self.health_thread.join(timeout=2.0)
        if self.resource_thread:
            self.resource_thread.join(timeout=2.0)

        self.logger.info("All processes stopped")

    def restart_process(self, engine_type: EngineType) -> bool:
        """
        Restart a specific process.

        Args:
            engine_type: Engine type to restart

        Returns:
            bool: True if restart successful
        """
        with self.process_lock:
            if engine_type in self.processes:
                proc_info = self.processes[engine_type]
                return self._restart_process(proc_info)
        return False

    def get_process_status(self) -> dict[str, Any]:
        """
        Get status of all managed processes.

        Returns:
            Dictionary of process statuses
        """
        with self.process_lock:
            status = {}

            for engine_type, proc_info in self.processes.items():
                status[engine_type.value] = {
                    'state': proc_info.state.name,
                    'pid': proc_info.pid,
                    'alive': proc_info.is_alive(),
                    'uptime': proc_info.get_uptime(),
                    'restart_count': proc_info.restart_count,
                    'cpu_percent': proc_info.cpu_percent,
                    'memory_mb': proc_info.memory_mb,
                    'error_count': proc_info.error_count
                }

        return status

    def write_tick_data(self, tick: SharedTickData) -> bool:
        """
        Write tick data to shared memory.

        Args:
            tick: Tick data to write

        Returns:
            bool: True if written successfully
        """
        if not self.tick_buffer:
            return False

        try:
            # Get current index
            index = self.tick_index.value

            # Calculate position in buffer
            tick_size = SharedTickData.size()
            max_ticks = TICK_BUFFER_SIZE // tick_size

            # Circular buffer - wrap around
            position = index % max_ticks
            offset = position * tick_size

            # Write tick data
            tick_bytes = tick.to_bytes()
            self.tick_buffer[offset:offset + tick_size] = np.frombuffer(
                tick_bytes, dtype=np.uint8
            )

            # Increment index
            with self.tick_index.get_lock():
                self.tick_index.value = index + 1

            return True

        except Exception as e:
            self.logger.error("Failed to write tick data: %s", e)
            return False

    def read_tick_data(self, count: int = 100) -> list[SharedTickData]:
        """
        Read recent tick data from shared memory.

        Args:
            count: Number of recent ticks to read

        Returns:
            List of tick data
        """
        if not self.tick_buffer:
            return []

        try:
            ticks = []
            current_index = self.tick_index.value
            tick_size = SharedTickData.size()
            max_ticks = TICK_BUFFER_SIZE // tick_size

            # Read backwards from current position
            for i in range(min(count, current_index, max_ticks)):
                position = ((current_index - i - 1) % max_ticks)
                offset = position * tick_size

                # Read tick bytes
                tick_bytes = bytes(self.tick_buffer[offset:offset + tick_size])
                tick = SharedTickData.from_bytes(tick_bytes)

                # Skip empty entries
                if tick.timestamp > 0:
                    ticks.append(tick)

            return list(reversed(ticks))

        except Exception as e:
            self.logger.error("Failed to read tick data: %s", e)
            return []

    # ==========================================================================
    # PRIVATE METHODS - PROCESS MANAGEMENT
    # ==========================================================================
    def _start_process(self, proc_info: ProcessInfo) -> bool:
        """Start a single process."""
        try:
            if proc_info.is_alive():
                self.logger.warning("%s already running", proc_info.engine_type.value)
                return True

            proc_info.state = ProcessState.STARTING

            # Create process arguments
            args = (
                proc_info.engine_type,
                self.shutdown_event,
                TICK_BUFFER_NAME  # Pass shared memory name
            )

            # Create and start process
            proc_info.process = mp.Process(
                target=self._process_wrapper,
                args=(proc_info.process_class, args),
                name=f"Spyder_{proc_info.engine_type.value}"
            )

            proc_info.process.start()
            proc_info.pid = proc_info.process.pid
            proc_info.start_time = time.time()

            # Set process priority
            if proc_info.pid and proc_info.engine_type in PROCESS_PRIORITIES:
                try:
                    p = psutil.Process(proc_info.pid)
                    p.nice(PROCESS_PRIORITIES[proc_info.engine_type])
                except Exception as e:
                    self.logger.warning("Failed to set priority: %s", e)

            # Wait for startup
            startup_timeout = time.time() + PROCESS_STARTUP_TIMEOUT
            while time.time() < startup_timeout:
                if not proc_info.is_alive():
                    raise Exception("Process died during startup")

                # Check if process registered with coordinator
                if self._check_process_registered(proc_info.engine_type):
                    proc_info.state = ProcessState.RUNNING
                    self.logger.info("%s started successfully", proc_info.engine_type.value)
                    return True

                time.sleep(0.5)  # thread-safe: time.sleep() intentional

            raise Exception("Process startup timeout")

        except Exception as e:
            self.logger.error("Failed to start %s: %s", proc_info.engine_type.value, e)
            proc_info.state = ProcessState.FAILED
            proc_info.error_count += 1
            return False

    def _stop_process(self, proc_info: ProcessInfo, timeout: float) -> None:
        """Stop a single process gracefully."""
        if not proc_info.is_alive():
            proc_info.state = ProcessState.STOPPED
            return

        try:
            proc_info.state = ProcessState.STOPPING

            # Try graceful shutdown first
            if proc_info.process:
                proc_info.process.terminate()
                proc_info.process.join(timeout=timeout)

                # Force kill if still alive
                if proc_info.process.is_alive():
                    self.logger.warning("Force killing %s", proc_info.engine_type.value)
                    proc_info.process.kill()
                    proc_info.process.join(timeout=2.0)

            proc_info.state = ProcessState.STOPPED
            proc_info.process = None
            proc_info.pid = None

        except Exception as e:
            self.logger.error("Error stopping %s: %s", proc_info.engine_type.value, e)

    def _restart_process(self, proc_info: ProcessInfo) -> bool:
        """Restart a process."""
        proc_info.state = ProcessState.RESTARTING
        proc_info.restart_count += 1

        # Stop if running
        self._stop_process(proc_info, timeout=5.0)

        # Wait before restart
        time.sleep(RESTART_DELAY)  # thread-safe: time.sleep() intentional

        # Start again
        return self._start_process(proc_info)

    @staticmethod
    def _process_wrapper(process_class: type, args: tuple) -> None:
        """Wrapper to run process class."""
        try:
            # Create and run process instance
            instance = process_class(*args)
            instance.run()
        except Exception as e:
            logging.error("Process crashed: %s", e)
            raise

    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _health_monitor_loop(self) -> None:
        """Monitor health of all processes."""
        next_check = time.time()

        while self.running.is_set():
            try:
                now = time.time()

                if now >= next_check:
                    self._check_process_health()
                    next_check = now + HEALTH_CHECK_INTERVAL

                time.sleep(0.1)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Health monitor error: %s", e)

    def _check_process_health(self) -> None:
        """Check health of all processes."""
        with self.process_lock:
            for proc_info in self.processes.values():
                if proc_info.state != ProcessState.RUNNING:
                    continue

                # Check if process is alive
                if not proc_info.is_alive():
                    self.logger.error("%s died unexpectedly", proc_info.engine_type.value)
                    proc_info.state = ProcessState.FAILED

                    # Attempt restart if under limit
                    if proc_info.restart_count < MAX_RESTART_ATTEMPTS:
                        self.logger.info("Attempting restart of %s", proc_info.engine_type.value)
                        self._restart_process(proc_info)
                    else:
                        self.logger.error("%s exceeded restart limit", proc_info.engine_type.value)

                # Check resource usage
                if proc_info.pid:
                    try:
                        p = psutil.Process(proc_info.pid)
                        proc_info.cpu_percent = p.cpu_percent(interval=0.1)
                        proc_info.memory_mb = p.memory_info().rss / 1024 / 1024

                        # Check limits
                        action = self._check_resource_limits(proc_info)
                        if action != ResourceAction.NONE:
                            self._handle_resource_action(proc_info, action)

                    except psutil.NoSuchProcess:
                        pass

    def _resource_monitor_loop(self) -> None:
        """Monitor system resources."""
        next_check = time.time()

        while self.running.is_set():
            try:
                now = time.time()

                if now >= next_check:
                    self._update_system_resources()
                    next_check = now + MEMORY_CHECK_INTERVAL

                time.sleep(0.5)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Resource monitor error: %s", e)

    def _update_system_resources(self) -> None:
        """Update system resource snapshot."""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Create snapshot
            snapshot = SystemResources(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_percent=disk.percent,
                process_count=len(psutil.pids())
            )

            # Store in history
            self.resource_history.append(snapshot)
            if len(self.resource_history) > self.max_history_size:
                self.resource_history.pop(0)

            # Check for system-wide issues
            if memory.available / 1024 / 1024 < MIN_FREE_MEMORY_MB:
                self.logger.warning(f"Low system memory: {memory.available / 1024 / 1024:.1f}MB")

            if cpu_percent > 90:
                self.logger.warning("High system CPU usage: %s%%", cpu_percent)

        except Exception as e:
            self.logger.error("Resource update error: %s", e)

    def _check_resource_limits(self, proc_info: ProcessInfo) -> ResourceAction:
        """Check if process exceeds resource limits."""
        # CPU check
        if proc_info.cpu_percent > MAX_CPU_PERCENT:
            self.logger.warning(
                f"{proc_info.engine_type.value} high CPU: {proc_info.cpu_percent:.1f}%"
            )
            return ResourceAction.THROTTLE

        # Memory check
        if proc_info.memory_mb > MAX_MEMORY_MB:
            self.logger.warning(
                f"{proc_info.engine_type.value} high memory: {proc_info.memory_mb:.1f}MB"
            )
            return ResourceAction.RESTART

        return ResourceAction.NONE

    def _handle_resource_action(self, proc_info: ProcessInfo, action: ResourceAction) -> None:
        """Handle resource limit violation."""
        if action == ResourceAction.THROTTLE:
            # Send throttle command
            self._send_engine_command(proc_info.engine_type, "THROTTLE")

        elif action == ResourceAction.RESTART:
            # Schedule restart
            self.logger.info("Scheduling restart of %s due to resource limits", proc_info.engine_type.value)
            threading.Thread(
                target=lambda: self._restart_process(proc_info),
                daemon=True
            ).start()

    def _check_process_registered(self, engine_type: EngineType) -> bool:
        """Check if process registered with coordinator."""
        try:
            # Query coordinator status
            self.monitor_socket.send_json({'type': 'STATUS'})

            # Wait for response with timeout
            if self.monitor_socket.poll(1000):  # 1 second timeout
                response = self.monitor_socket.recv_json()
                engines = response.get('engines', {})

                # Check if engine type is registered
                for engine_info in engines.values():
                    if engine_info['type'] == engine_type.value:
                        return engine_info['alive']

        except Exception as e:
            self.logger.error("Failed to check registration: %s", e)

        return False

    def _send_engine_command(self, engine_type: EngineType, command: str) -> None:
        """Send command to engine via coordinator."""
        try:
            request = {
                'type': 'ENGINE_COMMAND',
                'engine_type': engine_type.value,
                'command_type': command,
                'data': {}
            }

            self.monitor_socket.send_json(request)

            # Wait for response
            if self.monitor_socket.poll(1000):
                response = self.monitor_socket.recv_json()
                if response['status'] != 'SUCCESS':
                    self.logger.error("Command failed: %s", response)

        except Exception as e:
            self.logger.error("Failed to send command: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - SHARED MEMORY
    # ==========================================================================
    def _init_shared_memory(self) -> None:
        """Initialize shared memory for tick data."""
        try:
            # Try to connect to existing shared memory
            try:
                self.shared_mem = shared_memory.SharedMemory(name=TICK_BUFFER_NAME)
                self.logger.info("Connected to existing shared memory")
            except FileNotFoundError:
                # Create new shared memory
                self.shared_mem = shared_memory.SharedMemory(
                    create=True,
                    size=TICK_BUFFER_SIZE,
                    name=TICK_BUFFER_NAME
                )
                self.logger.info("Created new shared memory")

            # Create numpy array view
            self.tick_buffer = np.ndarray(
                TICK_BUFFER_SIZE,
                dtype=np.uint8,
                buffer=self.shared_mem.buf
            )

            # Initialize to zero
            self.tick_buffer[:] = 0

        except Exception as e:
            self.logger.error("Shared memory initialization failed: %s", e)
            raise

    def _cleanup_shared_memory(self) -> None:
        """Clean up shared memory."""
        try:
            if self.shared_mem:
                self.shared_mem.close()

                # Unlink only if we created it
                if hasattr(self, '_created_shared_memory'):
                    self.shared_mem.unlink()

        except Exception as e:
            self.logger.error("Shared memory cleanup error: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle system signals."""
        self.logger.info("Received signal %s", signum)
        self.stop_all_processes()
        sys.exit(0)

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up manager resources."""
        self.stop_all_processes()
        self._cleanup_shared_memory()

        if self.monitor_socket:
            self.monitor_socket.close()
        self.context.term()

        self.logger.info("MultiProcessManager cleanup completed")

# ==============================================================================
# BASE PROCESS CLASS
# ==============================================================================
class SpyderEngineProcess:
    """
    Base class for all SPYDER engine processes.

    Inherit from this class to create engine processes that integrate
    with the MultiProcessManager.
    """

    def __init__(self, engine_type: EngineType, shutdown_event: mp.Event,
                 shared_memory_name: str):
        """Initialize base process."""
        self.engine_type = engine_type
        self.engine_id = f"{engine_type.value}_{os.getpid()}"
        self.shutdown_event = shutdown_event
        self.shared_memory_name = shared_memory_name

        # Logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # ZeroMQ
        self.context = zmq.Context()
        self.dealer_socket = None

        # Shared memory
        self.shared_mem = None
        self.tick_buffer = None

        # Heartbeat
        self.last_heartbeat = time.time()

    def setup(self) -> None:
        """Set up process resources."""
        # Connect to coordinator
        self.dealer_socket = create_engine_client(self.engine_type, self.engine_id)

        # Connect to shared memory
        try:
            self.shared_mem = shared_memory.SharedMemory(name=self.shared_memory_name)
            self.tick_buffer = np.ndarray(
                self.shared_mem.size,
                dtype=np.uint8,
                buffer=self.shared_mem.buf
            )
            self.logger.info("Connected to shared memory")
        except Exception as e:
            self.logger.error("Failed to connect to shared memory: %s", e)

    def run(self) -> None:
        """Main process loop - override in subclasses."""
        self.setup()

        while not self.shutdown_event.is_set():
            try:
                # Send heartbeat
                if time.time() - self.last_heartbeat > 1.0:
                    self.send_heartbeat()

                # Process work - implement in subclass
                self.process_work()

                time.sleep(0.01)  # Prevent busy loop  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Process error: %s", e)

        self.cleanup()

    def process_work(self) -> None:
        """Override this method to implement engine logic."""
        pass

    def send_heartbeat(self) -> None:
        """Send heartbeat to coordinator."""
        heartbeat = {
            'type': 'HEARTBEAT',
            'engine_id': self.engine_id,
            'status': 'HEALTHY',
            'timestamp': time.time(),
            'metrics': self.get_metrics()
        }

        self.dealer_socket.send_json(heartbeat)
        self.last_heartbeat = time.time()

    def get_metrics(self) -> dict[str, Any]:
        """Get process metrics - override to add custom metrics."""
        return {
            'uptime': time.time() - self.last_heartbeat,
            'pid': os.getpid()
        }

    def cleanup(self) -> None:
        """Clean up process resources."""
        if self.dealer_socket:
            self.dealer_socket.close()
        if self.shared_mem:
            self.shared_mem.close()
        self.context.term()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_manager_instance: MultiProcessManager | None = None

def get_manager_instance() -> MultiProcessManager:
    """
    Get singleton instance of the multi-process manager.

    Returns:
        MultiProcessManager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = MultiProcessManager()
    return _manager_instance

# ==============================================================================
# EXAMPLE ENGINE IMPLEMENTATION
# ==============================================================================
class ExampleVolatilityEngine(SpyderEngineProcess):
    """Example volatility engine implementation."""

    def process_work(self) -> None:
        """Process volatility calculations."""
        # Read recent ticks from shared memory
        # This is just an example - real implementation would be more complex

        # Check for commands
        if self.dealer_socket.poll(0):
            message = self.dealer_socket.recv_json()
            self.logger.info("Received command: %s", message)

            # Send response
            response = {
                'type': 'RESPONSE',
                'command_id': message.get('command_id'),
                'result': {'status': 'processed'}
            }
            self.dealer_socket.send_json(response)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    manager = MultiProcessManager()

    if manager.initialize():

        # Register example process
        manager.register_process(EngineType.VOLATILITY, ExampleVolatilityEngine)

        # Start processes
        try:
            manager.start_all_processes()

            # Monitor for a while
            for _i in range(10):
                time.sleep(2)
                status = manager.get_process_status()
                for _engine, _info in status.items():
                    pass

                # Test tick writing
                tick = SharedTickData(
                    symbol="SPY",
                    timestamp=time.time(),
                    bid=450.25,
                    ask=450.30,
                    last=450.28,
                    volume=1000000,
                    bid_size=100,
                    ask_size=150
                )

                if manager.write_tick_data(tick):
                    pass

        except KeyboardInterrupt:
            pass

        finally:
            manager.cleanup()

    else:
        pass
