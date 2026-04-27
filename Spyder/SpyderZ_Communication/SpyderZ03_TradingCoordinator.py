#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderZ_Communication
Module: SpyderZ03_TradingCoordinator.py
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
import time
import json
import threading
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import uuid
import logging
from collections import defaultdict, OrderedDict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import heapq
import sqlite3
import hashlib
import zmq

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from .SpyderZ01_ZeroMQIntegration import CircuitBreaker
from .SpyderZ02_MessageProtocol import (
    MessageCategory, ProtocolManager,
    ProtocolMessage, SerializationFormat, ValidationLevel,
    PRIORITY_HIGH, PRIORITY_NORMAL,
)

# Import from utilities (these would be actual imports in production)
# from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
# from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Router ports
COORDINATOR_ROUTER_PORT = 6000
COORDINATOR_PUB_PORT = 6001
COORDINATOR_MONITOR_PORT = 6002
COORDINATOR_BACKUP_PORT = 6003

# Engine ports (DEALER clients will connect to these)
ENGINE_PORT_BASE = 6010
ENGINE_PORT_RANGE = 100  # Support up to 100 engines

# Timing constants
HEARTBEAT_INTERVAL = 1.0  # seconds
HEARTBEAT_TIMEOUT = 5.0   # seconds
COMMAND_TIMEOUT = 3.0     # seconds
HEALTH_CHECK_INTERVAL = 2.0
STATE_SAVE_INTERVAL = 10.0  # seconds
BACKUP_SYNC_INTERVAL = 5.0  # seconds

# System limits
MAX_PENDING_COMMANDS = 1000
MAX_MESSAGE_QUEUE_SIZE = 10000
MAX_ENGINE_INSTANCES = 10  # Per engine type
MAX_MESSAGE_AGE = 300  # seconds (5 minutes)

# Load balancing
LOAD_BALANCE_THRESHOLD = 0.8  # 80% capacity
LOAD_CHECK_INTERVAL = 1.0  # seconds

# State persistence
STATE_DB_PATH = "coordinator_state.db"
STATE_BACKUP_PATH = "coordinator_state_backup.db"
MAX_STATE_HISTORY = 1000

# ==============================================================================
# ENUMS
# ==============================================================================
class EngineType(Enum):
    """Types of trading engines managed by coordinator."""
    VOLATILITY = "VOLATILITY_ENGINE"
    ANOMALY = "ANOMALY_DETECTOR"
    HEDGER = "AUTO_HEDGER"
    EXECUTION = "EXECUTION_ENGINE"
    DATA_FEED = "DATA_FEED"
    RISK_MONITOR = "RISK_MONITOR"
    ML_PREDICTOR = "ML_PREDICTOR"

class CommandType(Enum):
    """Command types for engine control."""
    START = "START"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CONFIGURE = "CONFIGURE"
    EXECUTE = "EXECUTE"
    QUERY = "QUERY"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"

class CoordinatorState(Enum):
    """Coordinator operational states."""
    INITIALIZING = auto()
    RUNNING = auto()
    DEGRADED = auto()
    RECOVERING = auto()
    SHUTTING_DOWN = auto()
    STOPPED = auto()

class EngineStatus(Enum):
    """Engine status states."""
    OFFLINE = auto()
    STARTING = auto()
    ONLINE = auto()
    BUSY = auto()
    ERROR = auto()
    UNRESPONSIVE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class EngineInfo:
    """Information about a registered engine."""
    engine_id: str
    engine_type: EngineType
    status: EngineStatus = EngineStatus.OFFLINE
    last_heartbeat: float = 0.0
    capabilities: list[str] = field(default_factory=list)
    current_load: float = 0.0
    processed_commands: int = 0
    error_count: int = 0
    start_time: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class CommandRequest:
    """Command request to be routed to engines."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_type: CommandType = CommandType.EXECUTE
    target_engine: str | None = None
    target_type: EngineType | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    timeout: float = COMMAND_TIMEOUT
    priority: int = PRIORITY_NORMAL
    requires_response: bool = True
    retries: int = 0
    max_retries: int = 3

@dataclass
class CommandResponse:
    """Response from engine for a command."""
    command_id: str
    engine_id: str
    success: bool
    result: Any
    error: str | None = None
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class CoordinatorMetrics:
    """Metrics for coordinator performance."""
    total_commands: int = 0
    successful_commands: int = 0
    failed_commands: int = 0
    avg_response_time: float = 0.0
    active_engines: int = 0
    total_engines: int = 0
    message_queue_size: int = 0
    uptime: float = 0.0
    last_state_save: float = 0.0
    memory_usage_mb: float = 0.0

# ==============================================================================
# STATE PERSISTENCE
# ==============================================================================
class StateManager:
    """Manages coordinator state persistence and recovery."""

    def __init__(self, db_path: str = STATE_DB_PATH):
        self.db_path = db_path
        self.backup_path = STATE_BACKUP_PATH
        self.logger = logging.getLogger("StateManager")
        self._initialize_db()

    def _initialize_db(self):
        """Initialize state database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Create tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS coordinator_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        state TEXT,
                        engines TEXT,
                        metrics TEXT,
                        checksum TEXT
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS command_history (
                        command_id TEXT PRIMARY KEY,
                        timestamp REAL,
                        command_type TEXT,
                        target TEXT,
                        payload TEXT,
                        response TEXT,
                        status TEXT
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS engine_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        engine_id TEXT,
                        timestamp REAL,
                        event_type TEXT,
                        details TEXT
                    )
                """)

                conn.commit()

        except Exception as e:
            self.logger.error("Failed to initialize database: %s", e)

    def save_state(self,
                   state: CoordinatorState,
                   engines: dict[str, EngineInfo],
                   metrics: CoordinatorMetrics) -> bool:
        """Save coordinator state to database."""
        try:
            # Prepare data
            state_data = {
                "state": state.name,
                "engines": {eid: asdict(info) for eid, info in engines.items()},
                "metrics": asdict(metrics)
            }

            # Calculate checksum
            state_json = json.dumps(state_data, sort_keys=True)
            checksum = hashlib.sha256(state_json.encode()).hexdigest()

            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO coordinator_state (timestamp, state, engines, metrics, checksum)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    time.time(),
                    state_data["state"],
                    json.dumps(state_data["engines"]),
                    json.dumps(state_data["metrics"]),
                    checksum
                ))

                # Clean old entries
                cursor.execute("""
                    DELETE FROM coordinator_state
                    WHERE id NOT IN (
                        SELECT id FROM coordinator_state
                        ORDER BY timestamp DESC
                        LIMIT ?
                    )
                """, (MAX_STATE_HISTORY,))

                conn.commit()

            # Create backup
            self._create_backup()

            return True

        except Exception as e:
            self.logger.error("Failed to save state: %s", e)
            return False

    def load_state(self) -> dict[str, Any] | None:
        """Load latest coordinator state from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT state, engines, metrics, checksum
                    FROM coordinator_state
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)

                row = cursor.fetchone()
                if not row:
                    return None

                # Verify checksum
                state_data = {
                    "state": row[0],
                    "engines": json.loads(row[1]),
                    "metrics": json.loads(row[2])
                }

                state_json = json.dumps(state_data, sort_keys=True)
                checksum = hashlib.sha256(state_json.encode()).hexdigest()

                if checksum != row[3]:
                    self.logger.warning("State checksum mismatch, attempting backup")
                    return self._load_from_backup()

                return state_data

        except Exception as e:
            self.logger.error("Failed to load state: %s", e)
            return self._load_from_backup()

    def _create_backup(self):
        """Create backup of state database."""
        try:
            import shutil
            shutil.copy2(self.db_path, self.backup_path)
        except Exception as e:
            self.logger.error("Failed to create backup: %s", e)

    def _load_from_backup(self) -> dict[str, Any] | None:
        """Load state from backup database."""
        if not os.path.exists(self.backup_path):
            return None

        # Swap paths temporarily
        self.db_path, self.backup_path = self.backup_path, self.db_path
        result = self.load_state()
        self.db_path, self.backup_path = self.backup_path, self.db_path

        return result

    def save_command(self, command: CommandRequest, response: CommandResponse | None = None):
        """Save command to history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO command_history
                    (command_id, timestamp, command_type, target, payload, response, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    command.command_id,
                    command.timestamp,
                    command.command_type.value,
                    command.target_engine or command.target_type.value if command.target_type else "",  # noqa: E501
                    json.dumps(command.payload),
                    json.dumps(asdict(response)) if response else None,
                    "SUCCESS" if response and response.success else "PENDING" if not response else "FAILED"  # noqa: E501
                ))
                conn.commit()

        except Exception as e:
            self.logger.error("Failed to save command: %s", e)

# ==============================================================================
# LOAD BALANCER
# ==============================================================================
class LoadBalancer:
    """Manages load distribution across engines."""

    def __init__(self):
        self.engine_loads = defaultdict(float)
        self.engine_queues = defaultdict(int)
        self.routing_history = defaultdict(list)
        self.logger = logging.getLogger("LoadBalancer")

    def select_engine(self,
                     engines: dict[str, EngineInfo],
                     engine_type: EngineType | None = None,
                     exclude: set[str] | None = None) -> str | None:
        """Select best engine based on load and availability."""
        exclude = exclude or set()

        # Filter available engines
        available = []
        for engine_id, info in engines.items():
            if engine_id in exclude:
                continue
            if engine_type and info.engine_type != engine_type:
                continue
            if info.status != EngineStatus.ONLINE:
                continue
            if info.current_load >= LOAD_BALANCE_THRESHOLD:
                continue

            available.append((engine_id, info))

        if not available:
            return None

        # Sort by load and error rate
        def score_engine(item):
            engine_id, info = item
            load_score = info.current_load
            error_rate = info.error_count / max(info.processed_commands, 1)
            queue_size = self.engine_queues.get(engine_id, 0)

            # Combined score (lower is better)
            return load_score + (error_rate * 0.3) + (queue_size * 0.1)

        available.sort(key=score_engine)
        selected = available[0][0]

        # Update routing history
        self.routing_history[selected].append(time.time())

        return selected

    def update_load(self, engine_id: str, load: float):
        """Update engine load."""
        self.engine_loads[engine_id] = load

    def update_queue_size(self, engine_id: str, size: int):
        """Update engine queue size."""
        self.engine_queues[engine_id] = size

    def get_load_distribution(self) -> dict[str, float]:
        """Get current load distribution."""
        return dict(self.engine_loads)

# ==============================================================================
# MESSAGE SEQUENCER
# ==============================================================================
class MessageSequencer:
    """Ensures message ordering guarantees."""

    def __init__(self):
        self.sequences = defaultdict(int)
        self.pending_messages = defaultdict(list)
        self.message_buffer = OrderedDict()
        self.max_buffer_size = 1000
        self.logger = logging.getLogger("MessageSequencer")

    def add_sequence(self, message: ProtocolMessage) -> int:
        """Add sequence number to message."""
        key = f"{message.source}:{message.category.value}"
        sequence = self.sequences[key]
        self.sequences[key] += 1

        # Add sequence to metadata
        message.metadata.tags.add(f"seq:{sequence}")

        return sequence

    def should_process(self, message: ProtocolMessage) -> bool:
        """Check if message should be processed based on ordering."""
        # Extract sequence if present
        sequence = None
        for tag in message.metadata.tags:
            if tag.startswith("seq:"):
                sequence = int(tag.split(":")[1])
                break

        if sequence is None:
            return True  # No sequencing required

        key = f"{message.source}:{message.category.value}"
        expected = self.get_expected_sequence(key)

        if sequence == expected:
            # Process any pending messages
            self._process_pending(key)
            return True
        elif sequence > expected:
            # Out of order, buffer it
            heapq.heappush(self.pending_messages[key], (sequence, message))
            return False
        else:
            # Old message, discard — sequence too old
            self.logger.debug("Discarding out-of-order message (stale sequence)")
            return False

    def promote_to_primary(self):
        """Promote backup coordinator to primary."""
        if self.is_primary:
            return

        self.logger.info("Promoting to primary coordinator")

        with self._lock:
            self.is_primary = True

            # Rebind sockets to primary ports
            self.router_socket.close()
            self.router_socket = self.context.socket(zmq.ROUTER)
            self.router_socket.bind(f"tcp://*:{COORDINATOR_ROUTER_PORT}")

            # Switch backup socket to publisher mode
            self.backup_socket.close()
            self.backup_socket = self.context.socket(zmq.PUB)
            self.backup_socket.bind(f"tcp://*:{COORDINATOR_BACKUP_PORT}")

        # Broadcast promotion
        self._broadcast_status("COORDINATOR_PROMOTED")

    # ==========================================================================
    # BROADCASTING AND MONITORING
    # ==========================================================================
    def _broadcast_status(self, status: str):
        """Broadcast status update to all subscribers."""
        try:
            status_msg = self.protocol_manager.create_message(
                category=MessageCategory.SYSTEM,
                message_type="STATUS_BROADCAST",
                source=self.coordinator_id,
                data={
                    "status": status,
                    "timestamp": time.time(),
                    "is_primary": self.is_primary,
                    "state": self.state.name
                },
                priority=PRIORITY_HIGH
            )

            data = self.protocol_manager.serialize_message(status_msg)
            self.pub_socket.send(data)

        except Exception as e:
            self.logger.error("Broadcast failed: %s", e)

    def get_system_status(self) -> dict[str, Any]:
        """Get comprehensive system status."""
        with self._lock:
            return {
                "coordinator_id": self.coordinator_id,
                "state": self.state.name,
                "is_primary": self.is_primary,
                "uptime": time.time() - self.start_time,
                "engines": {
                    engine_type.value: {
                        "total": len(engine_ids),
                        "online": sum(
                            1 for eid in engine_ids
                            if self.engines[eid].status == EngineStatus.ONLINE
                        ),
                        "engines": [
                            {
                                "id": eid,
                                "status": self.engines[eid].status.name,
                                "load": self.engines[eid].current_load,
                                "errors": self.engines[eid].error_count
                            }
                            for eid in engine_ids
                        ]
                    }
                    for engine_type, engine_ids in self.engine_types.items()
                },
                "metrics": asdict(self.metrics),
                "load_distribution": self.load_balancer.get_load_distribution(),
                "pending_commands": len(self.pending_commands),
                "circuit_breakers": {
                    name: breaker.state.name
                    for name, breaker in self.circuit_breakers.items()
                }
            }

# ==============================================================================
# ENGINE CLIENT HELPER
# ==============================================================================
def create_engine_client(engine_type: EngineType,
                        engine_id: str,
                        coordinator_host: str = "localhost",
                        coordinator_port: int = COORDINATOR_ROUTER_PORT) -> zmq.Socket:
    """
    Create a DEALER socket for engine to connect to coordinator.

    Args:
        engine_type: Type of engine
        engine_id: Unique engine identifier
        coordinator_host: Coordinator hostname
        coordinator_port: Coordinator port

    Returns:
        Configured DEALER socket
    """
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)

    # Set identity for routing
    socket.identity = f"{engine_type.value}:{engine_id}".encode()

    # Configure socket
    socket.setsockopt(zmq.LINGER, 0)
    socket.setsockopt(zmq.SNDHWM, 0)
    socket.setsockopt(zmq.RCVHWM, 0)

    # Connect to coordinator
    socket.connect(f"tcp://{coordinator_host}:{coordinator_port}")

    # Create protocol manager
    protocol_manager = ProtocolManager()

    # Send registration
    registration = protocol_manager.create_message(
        category=MessageCategory.SYSTEM,
        message_type="REGISTER",
        source=engine_id,
        data={
            "engine_id": engine_id,
            "engine_type": engine_type.value,
            "capabilities": [],
            "timestamp": time.time()
        },
        priority=PRIORITY_HIGH
    )

    # Send registration message
    data = protocol_manager.serialize_message(registration)
    socket.send(data)

    return socket

# ==============================================================================
# COORDINATOR CLUSTER MANAGER
# ==============================================================================
class CoordinatorCluster:
    """Manages multiple coordinator instances for high availability."""

    def __init__(self, num_instances: int = 2):
        self.num_instances = num_instances
        self.coordinators = []
        self.primary_index = 0
        self.logger = logging.getLogger("CoordinatorCluster")

    def start(self):
        """Start coordinator cluster."""
        for i in range(self.num_instances):
            is_primary = (i == self.primary_index)
            coordinator = TradingCoordinator(is_primary=is_primary)

            if coordinator.initialize():
                coordinator.start()
                self.coordinators.append(coordinator)
                self.logger.info("Started coordinator %s (Primary: %s)", i, is_primary)
            else:
                self.logger.error("Failed to start coordinator %s", i)

    def monitor_health(self):
        """Monitor coordinator health and handle failover."""
        while True:
            try:
                # Check primary health
                primary = self.coordinators[self.primary_index]

                # Simple health check - in production would be more sophisticated
                if primary.state != CoordinatorState.RUNNING:
                    self.logger.warning("Primary coordinator unhealthy, initiating failover")
                    self._perform_failover()

                time.sleep(5)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Health monitoring error: %s", e)

    def _perform_failover(self):
        """Perform failover to backup coordinator."""
        # Find healthy backup
        for i, coordinator in enumerate(self.coordinators):
            if i != self.primary_index and coordinator.state == CoordinatorState.RUNNING:
                # Promote backup to primary
                coordinator.promote_to_primary()
                self.primary_index = i
                self.logger.info("Failover completed to coordinator %s", i)
                break

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_coordinator_instance(is_primary: bool = True) -> "TradingCoordinator":
    """
    Get coordinator instance.

    Args:
        is_primary: Whether this is the primary coordinator

    Returns:
        TradingCoordinator instance
    """
    coordinator = TradingCoordinator(is_primary=is_primary)
    return coordinator

# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
def example_single_coordinator():
    """Example: Single coordinator with engines."""
    logging.info("\n" + "="*60)
    logging.info("Example: Single Coordinator")
    logging.info("="*60)

    # Create and start coordinator
    coordinator = TradingCoordinator(is_primary=True)

    if coordinator.initialize():
        logging.info("✅ Coordinator initialized")
        coordinator.start()
        logging.info("✅ Coordinator started")

        # Simulate engine connections
        logging.info("\nSimulating engine connections...")

        # Print status
        logging.info("\nCoordinator Status:")
        status = coordinator.get_system_status()
        logging.info("  ID: %s", status['coordinator_id'][:8])
        logging.info("  State: %s", status['state'])
        logging.info("  Primary: %s", status['is_primary'])
        logging.info(f"  Uptime: {status['uptime']:.1f}s")

        # Create and route a command
        command = CommandRequest(
            command_type=CommandType.EXECUTE,
            target_type=EngineType.VOLATILITY,
            payload={"action": "calculate_iv", "symbol": "SPY"},
            source="TestClient",
            priority=PRIORITY_HIGH
        )

        logging.info("\nRouting command: %s", command.command_id[:8])
        cmd_id = coordinator.route_command(command)

        if cmd_id:
            logging.info("✅ Command routed successfully")
        else:
            logging.info("❌ Command routing failed")

        # Let it run for a bit
        time.sleep(5)

        # Stop coordinator
        coordinator.stop()
        logging.info("\n✅ Coordinator stopped")

    else:
        logging.info("❌ Coordinator initialization failed")

def example_coordinator_cluster():
    """Example: High availability coordinator cluster."""
    logging.info("\n" + "="*60)
    logging.info("Example: Coordinator Cluster")
    logging.info("="*60)

    # Create cluster
    cluster = CoordinatorCluster(num_instances=2)

    logging.info("Starting coordinator cluster...")
    cluster.start()

    logging.info("\nCluster Status:")
    for i, coordinator in enumerate(cluster.coordinators):
        logging.info("  Coordinator %s:", i)
        logging.info("    State: %s", coordinator.state.name)
        logging.info("    Primary: %s", coordinator.is_primary)

    # Simulate failover
    logging.info("\nSimulating primary failure...")
    cluster.coordinators[0].state = CoordinatorState.STOPPED

    cluster._perform_failover()

    logging.info("\nCluster Status After Failover:")
    for i, coordinator in enumerate(cluster.coordinators):
        logging.info("  Coordinator %s:", i)
        logging.info("    State: %s", coordinator.state.name)
        logging.info("    Primary: %s", coordinator.is_primary)

    # Stop all coordinators
    for coordinator in cluster.coordinators:
        if coordinator.state == CoordinatorState.RUNNING:
            coordinator.stop()

    logging.info("\n✅ Cluster stopped")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )



    choice = input("\nSelect example (1-3): ")

    if choice == "1":
        example_single_coordinator()
    elif choice == "2":
        example_coordinator_cluster()
    else:
        pass


    def get_expected_sequence(self, key: str) -> int:
        """Get expected sequence number for a key."""
        # This would be tracked based on processed messages
        return 0  # Simplified for example

    def _process_pending(self, key: str):
        """Process pending messages that are now in order."""
        # Implementation would process buffered messages
        pass

# ==============================================================================
# ENHANCED TRADING COORDINATOR
# ==============================================================================
class TradingCoordinator:
    """
    Enhanced central trading coordinator with high availability.

    Features:
        - Redundancy and failover support
        - State persistence and recovery
        - Load balancing across engines
        - Message ordering guarantees
        - Comprehensive monitoring
        - Automatic backup and restore
    """

    def __init__(self, is_primary: bool = True):
        """Initialize enhanced trading coordinator."""
        self.is_primary = is_primary
        self.coordinator_id = str(uuid.uuid4())
        self.state = CoordinatorState.INITIALIZING

        # Communication
        self.context = zmq.Context()
        self.router_socket = None
        self.pub_socket = None
        self.monitor_socket = None
        self.backup_socket = None

        # Protocol management
        self.protocol_manager = ProtocolManager(
            validation_level=ValidationLevel.STRICT,
            default_format=SerializationFormat.COMPRESSED_JSON
        )

        # State management
        self.state_manager = StateManager()
        self.load_balancer = LoadBalancer()
        self.message_sequencer = MessageSequencer()

        # Engine tracking
        self.engines = {}  # engine_id -> EngineInfo
        self.engine_types = defaultdict(list)  # engine_type -> [engine_ids]
        self.pending_commands = {}  # command_id -> CommandRequest
        self.command_responses = {}  # command_id -> CommandResponse

        # Metrics
        self.metrics = CoordinatorMetrics()
        self.start_time = time.time()

        # Circuit breakers
        self.circuit_breakers = defaultdict(lambda: CircuitBreaker())

        # Thread control
        self._running = False
        self._stop_event = threading.Event()
        self._threads = []
        self._lock = threading.RLock()

        # Logging
        self.logger = logging.getLogger(f"TradingCoordinator.{self.coordinator_id[:8]}")

    # ==========================================================================
    # INITIALIZATION AND LIFECYCLE
    # ==========================================================================
    def initialize(self) -> bool:
        """Initialize coordinator with state recovery."""
        try:
            self.logger.info("Initializing coordinator (Primary: %s)", self.is_primary)

            # Load previous state if available
            saved_state = self.state_manager.load_state()
            if saved_state:
                self._restore_state(saved_state)
                self.logger.info("Restored previous coordinator state")

            # Setup sockets
            if not self._setup_sockets():
                return False

            # Initialize components
            self.state = CoordinatorState.RUNNING
            self._running = True

            self.logger.info("Coordinator initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            self.state = CoordinatorState.STOPPED
            return False

    def _setup_sockets(self) -> bool:
        """Setup ZMQ sockets."""
        try:
            # Router socket for engine communication
            self.router_socket = self.context.socket(zmq.ROUTER)
            self.router_socket.setsockopt(zmq.ROUTER_MANDATORY, 1)
            self.router_socket.setsockopt(zmq.SNDHWM, 0)
            self.router_socket.setsockopt(zmq.RCVHWM, 0)

            if self.is_primary:
                self.router_socket.bind(f"tcp://*:{COORDINATOR_ROUTER_PORT}")
            else:
                # Backup uses different port
                self.router_socket.bind(f"tcp://*:{COORDINATOR_ROUTER_PORT + 100}")

            # Publisher socket for broadcasts
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{COORDINATOR_PUB_PORT}")

            # Monitor socket for health checks
            self.monitor_socket = self.context.socket(zmq.REP)
            self.monitor_socket.bind(f"tcp://*:{COORDINATOR_MONITOR_PORT}")

            # Backup synchronization socket
            if self.is_primary:
                self.backup_socket = self.context.socket(zmq.PUB)
                self.backup_socket.bind(f"tcp://*:{COORDINATOR_BACKUP_PORT}")
            else:
                self.backup_socket = self.context.socket(zmq.SUB)
                self.backup_socket.connect(f"tcp://localhost:{COORDINATOR_BACKUP_PORT}")
                self.backup_socket.setsockopt_string(zmq.SUBSCRIBE, "")

            return True

        except Exception as e:
            self.logger.error("Socket setup failed: %s", e)
            return False

    def start(self):
        """Start coordinator threads."""
        try:
            # Start worker threads
            threads = [
                ("router", self._router_thread),
                ("monitor", self._monitor_thread),
                ("health", self._health_check_thread),
                ("state", self._state_persistence_thread),
                ("cleanup", self._cleanup_thread),
                ("backup", self._backup_sync_thread),
            ]

            for name, target in threads:
                thread = threading.Thread(target=target, name=name, daemon=True)
                thread.start()
                self._threads.append(thread)
                self.logger.info("Started %s thread", name)

            # Broadcast startup
            self._broadcast_status("COORDINATOR_STARTED")

        except Exception as e:
            self.logger.error("Failed to start threads: %s", e)
            self.stop()

    def stop(self):
        """Stop coordinator gracefully."""
        self.logger.info("Shutting down coordinator...")

        with self._lock:
            self.state = CoordinatorState.SHUTTING_DOWN
            self._running = False
            self._stop_event.set()

        # Save final state
        self._save_state()

        # Broadcast shutdown
        self._broadcast_status("COORDINATOR_SHUTDOWN")

        # Wait for threads
        for thread in self._threads:
            thread.join(timeout=2)

        # Close sockets
        for socket in [self.router_socket, self.pub_socket,
                      self.monitor_socket, self.backup_socket]:
            if socket:
                socket.close()

        self.context.term()

        with self._lock:
            self.state = CoordinatorState.STOPPED

        self.logger.info("Coordinator stopped")

    # ==========================================================================
    # THREAD WORKERS
    # ==========================================================================
    def _router_thread(self):
        """Handle engine communication."""
        poller = zmq.Poller()
        poller.register(self.router_socket, zmq.POLLIN)

        while self._running:
            try:
                # Poll with timeout
                socks = dict(poller.poll(100))

                if self.router_socket in socks:
                    # Receive message
                    frames = self.router_socket.recv_multipart()
                    if len(frames) < 2:
                        continue

                    identity = frames[0]
                    message_data = frames[1]

                    # Process message
                    self._process_engine_message(identity, message_data)

                # Process pending commands
                self._process_pending_commands()

            except zmq.ZMQError as e:
                if e.errno != zmq.EAGAIN:
                    self.logger.error("Router error: %s", e)
            except Exception as e:
                self.logger.error("Router thread error: %s", e)

    def _monitor_thread(self):
        """Handle monitoring requests."""
        while self._running:
            try:
                # Wait for monitoring request
                if self.monitor_socket.poll(100):
                    self.monitor_socket.recv_json()

                    # Prepare response
                    response = {
                        "coordinator_id": self.coordinator_id,
                        "state": self.state.name,
                        "is_primary": self.is_primary,
                        "metrics": asdict(self.metrics),
                        "engines": {
                            eid: {
                                "type": info.engine_type.value,
                                "status": info.status.name,
                                "load": info.current_load
                            }
                            for eid, info in self.engines.items()
                        },
                        "timestamp": time.time()
                    }

                    self.monitor_socket.send_json(response)

            except Exception as e:
                self.logger.error("Monitor thread error: %s", e)

    def _health_check_thread(self):
        """Monitor engine health."""
        while self._running:
            try:
                current_time = time.time()

                with self._lock:
                    for engine_id, info in list(self.engines.items()):
                        # Check heartbeat timeout
                        if current_time - info.last_heartbeat > HEARTBEAT_TIMEOUT:
                            if info.status == EngineStatus.ONLINE:
                                self.logger.warning("Engine %s heartbeat timeout", engine_id)
                                info.status = EngineStatus.UNRESPONSIVE
                                self._handle_engine_failure(engine_id)

                if self._stop_event.wait(timeout=HEALTH_CHECK_INTERVAL):
                    break

            except Exception as e:
                self.logger.error("Health check error: %s", e)

    def _state_persistence_thread(self):
        """Periodically save coordinator state."""
        while self._running:
            try:
                if self._stop_event.wait(timeout=STATE_SAVE_INTERVAL):
                    break

                if self.is_primary:
                    self._save_state()

            except Exception as e:
                self.logger.error("State persistence error: %s", e)

    def _cleanup_thread(self):
        """Clean up old messages and data."""
        while self._running:
            try:
                current_time = time.time()

                with self._lock:
                    # Clean old pending commands
                    old_commands = []
                    for cmd_id, cmd in self.pending_commands.items():
                        if current_time - cmd.timestamp > MAX_MESSAGE_AGE:
                            old_commands.append(cmd_id)

                    for cmd_id in old_commands:
                        self.logger.warning("Removing old command: %s", cmd_id)
                        del self.pending_commands[cmd_id]

                if self._stop_event.wait(timeout=60):
                    break

            except Exception as e:
                self.logger.error("Cleanup error: %s", e)

    def _backup_sync_thread(self):
        """Synchronize with backup coordinator."""
        while self._running:
            try:
                if self.is_primary:
                    # Send state updates to backup
                    state_update = {
                        "type": "STATE_SYNC",
                        "engines": {eid: asdict(info) for eid, info in self.engines.items()},
                        "metrics": asdict(self.metrics),
                        "timestamp": time.time()
                    }

                    self.backup_socket.send_json(state_update)

                else:
                    # Receive state updates from primary
                    if self.backup_socket.poll(100):
                        update = self.backup_socket.recv_json()
                        self._process_backup_update(update)

                if self._stop_event.wait(timeout=BACKUP_SYNC_INTERVAL):
                    break

            except Exception as e:
                self.logger.error("Backup sync error: %s", e)

    # ==========================================================================
    # MESSAGE PROCESSING
    # ==========================================================================
    def _process_engine_message(self, identity: bytes, message_data: bytes):
        """Process message from engine."""
        try:
            # Deserialize message
            message = self.protocol_manager.deserialize_message(message_data)

            # Check sequencing
            if not self.message_sequencer.should_process(message):
                return

            # Route based on message type
            if message.message_type == "REGISTER":
                self._handle_engine_registration(identity, message)
            elif message.message_type == "HEARTBEAT":
                self._handle_heartbeat(identity, message)
            elif message.message_type == "RESPONSE":
                self._handle_command_response(identity, message)
            elif message.message_type == "STATUS_UPDATE":
                self._handle_status_update(identity, message)
            else:
                self.logger.warning("Unknown message type: %s", message.message_type)

            # Update metrics
            self.metrics.total_commands += 1

        except Exception as e:
            self.logger.error("Message processing error: %s", e)
            self.metrics.failed_commands += 1

    def _handle_engine_registration(self, identity: bytes, message: ProtocolMessage):
        """Handle engine registration."""
        try:
            data = message.data
            engine_id = data.get("engine_id")
            engine_type = EngineType(data.get("engine_type"))

            with self._lock:
                # Create or update engine info
                if engine_id not in self.engines:
                    self.engines[engine_id] = EngineInfo(
                        engine_id=engine_id,
                        engine_type=engine_type,
                        capabilities=data.get("capabilities", [])
                    )
                    self.engine_types[engine_type].append(engine_id)
                    self.logger.info("Registered new engine: %s (%s)", engine_id, engine_type.value)

                # Update status
                info = self.engines[engine_id]
                info.status = EngineStatus.ONLINE
                info.last_heartbeat = time.time()

                # Store identity mapping
                info.metadata["identity"] = identity

            # Send acknowledgment
            ack = self.protocol_manager.factory.create_alert(
                alert_type="REGISTRATION_ACK",
                message=f"Engine {engine_id} registered successfully",
                source=self.coordinator_id,
                severity="INFO"
            )

            self._send_to_engine(identity, ack)

            # Update load balancer
            self.load_balancer.update_load(engine_id, 0.0)

            # Save state
            self._save_state()

        except Exception as e:
            self.logger.error("Registration error: %s", e)

    def _handle_heartbeat(self, identity: bytes, message: ProtocolMessage):
        """Handle engine heartbeat."""
        try:
            engine_id = message.source

            with self._lock:
                if engine_id in self.engines:
                    info = self.engines[engine_id]
                    info.last_heartbeat = time.time()
                    info.current_load = message.data.get("load", 0.0)
                    info.status = EngineStatus.ONLINE

                    # Update load balancer
                    self.load_balancer.update_load(engine_id, info.current_load)

        except Exception as e:
            self.logger.error("Heartbeat error: %s", e)

    def _handle_command_response(self, identity: bytes, message: ProtocolMessage):
        """Handle command response from engine."""
        try:
            command_id = message.data.get("command_id")

            with self._lock:
                if command_id in self.pending_commands:
                    # Create response
                    response = CommandResponse(
                        command_id=command_id,
                        engine_id=message.source,
                        success=message.data.get("success", False),
                        result=message.data.get("result"),
                        error=message.data.get("error"),
                        execution_time=message.data.get("execution_time", 0.0)
                    )

                    # Store response
                    self.command_responses[command_id] = response

                    # Save to history
                    command = self.pending_commands[command_id]
                    self.state_manager.save_command(command, response)

                    # Remove from pending
                    del self.pending_commands[command_id]

                    # Update metrics
                    if response.success:
                        self.metrics.successful_commands += 1
                    else:
                        self.metrics.failed_commands += 1

                    # Update engine info
                    if message.source in self.engines:
                        self.engines[message.source].processed_commands += 1
                        if not response.success:
                            self.engines[message.source].error_count += 1

        except Exception as e:
            self.logger.error("Response handling error: %s", e)

    # ==========================================================================
    # COMMAND ROUTING
    # ==========================================================================
    def route_command(self, command: CommandRequest) -> str | None:
        """
        Route command to appropriate engine.

        Returns command_id if routed successfully.
        """
        try:
            with self._lock:
                # Select target engine
                if command.target_engine:
                    # Specific engine requested
                    if command.target_engine not in self.engines:
                        raise ValueError(f"Unknown engine: {command.target_engine}")
                    target = command.target_engine
                else:
                    # Use load balancer
                    target = self.load_balancer.select_engine(
                        self.engines,
                        command.target_type
                    )

                    if not target:
                        raise ValueError("No available engines")

                # Add to pending
                self.pending_commands[command.command_id] = command

                # Create protocol message
                cmd_message = self.protocol_manager.create_message(
                    category=MessageCategory.SYSTEM,
                    message_type="COMMAND",
                    source=self.coordinator_id,
                    data=asdict(command),
                    priority=command.priority
                )

                # Add sequencing
                self.message_sequencer.add_sequence(cmd_message)

                # Send to engine
                engine_info = self.engines[target]
                identity = engine_info.metadata.get("identity")

                if identity:
                    self._send_to_engine(identity, cmd_message)

                    # Save command
                    self.state_manager.save_command(command)

                    return command.command_id
                else:
                    raise ValueError(f"No identity for engine {target}")

        except Exception as e:
            self.logger.error("Command routing failed: %s", e)
            self.metrics.failed_commands += 1
            return None

    def _send_to_engine(self, identity: bytes, message: ProtocolMessage):
        """Send message to specific engine."""
        try:
            # Serialize message
            data = self.protocol_manager.serialize_message(message)

            # Send via router
            self.router_socket.send_multipart([identity, data])

        except Exception as e:
            self.logger.error("Send to engine failed: %s", e)

    def _process_pending_commands(self):
        """Process commands that need retry."""
        current_time = time.time()
        retry_commands = []

        with self._lock:
            for cmd_id, command in self.pending_commands.items():
                if current_time - command.timestamp > command.timeout:
                    if command.retries < command.max_retries:
                        retry_commands.append(command)
                    else:
                        # Max retries exceeded
                        self.logger.error("Command %s failed after max retries", cmd_id)
                        del self.pending_commands[cmd_id]
                        self.metrics.failed_commands += 1

        # Retry commands
        for command in retry_commands:
            command.retries += 1
            command.timestamp = current_time
            self.route_command(command)

    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    def _save_state(self):
        """Save current coordinator state."""
        try:
            with self._lock:
                # Update metrics
                self.metrics.uptime = time.time() - self.start_time
                self.metrics.active_engines = sum(
                    1 for info in self.engines.values()
                    if info.status == EngineStatus.ONLINE
                )
                self.metrics.total_engines = len(self.engines)
                self.metrics.message_queue_size = len(self.pending_commands)

                # Save state
                self.state_manager.save_state(
                    self.state,
                    self.engines,
                    self.metrics
                )

                self.metrics.last_state_save = time.time()

        except Exception as e:
            self.logger.error("State save failed: %s", e)

    def _restore_state(self, saved_state: dict[str, Any]):
        """Restore coordinator state from saved data."""
        try:
            # Restore engines
            for engine_id, engine_data in saved_state.get("engines", {}).items():
                info = EngineInfo(**engine_data)
                info.status = EngineStatus.OFFLINE  # Reset status
                self.engines[engine_id] = info
                self.engine_types[info.engine_type].append(engine_id)

            # Restore metrics
            metrics_data = saved_state.get("metrics", {})
            for key, value in metrics_data.items():
                if hasattr(self.metrics, key):
                    setattr(self.metrics, key, value)

            self.logger.info("Restored %s engines from saved state", len(self.engines))

        except Exception as e:
            self.logger.error("State restore failed: %s", e)

    def _process_backup_update(self, update: dict[str, Any]):
        """Process state update from primary (backup mode)."""
        try:
            if update.get("type") == "STATE_SYNC":
                # Update engine information
                for engine_id, engine_data in update.get("engines", {}).items():
                    if engine_id not in self.engines:
                        self.engines[engine_id] = EngineInfo(**engine_data)
                    else:
                        # Update existing info
                        for key, value in engine_data.items():
                            if hasattr(self.engines[engine_id], key):
                                setattr(self.engines[engine_id], key, value)

                # Update metrics
                metrics_data = update.get("metrics", {})
                for key, value in metrics_data.items():
                    if hasattr(self.metrics, key):
                        setattr(self.metrics, key, value)

        except Exception as e:
            self.logger.error("Backup update processing failed: %s", e)

    # ==========================================================================
    # FAILOVER AND RECOVERY
    # ==========================================================================
    def _handle_engine_failure(self, engine_id: str):
        """Handle engine failure."""
        try:
            self.logger.warning("Handling engine failure for: %s", engine_id)

            # Handle the failure logic here
            with self._lock:
                if engine_id in self.engines:
                    del self.engines[engine_id]
                    self.logger.info("Removed failed engine: %s", engine_id)

        except Exception as e:
            self.logger.error("Error handling engine failure: %s", e)
