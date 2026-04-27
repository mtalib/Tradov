#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA05_EventManager.py
Purpose: Centralized event management and message passing system
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-22 Time: 20:30:00

Module Description:
    This module provides a comprehensive event management system for the Spyder
    trading platform. It handles event publishing, subscription, routing, and
    persistence with support for priority queues, filtering, and asynchronous
    processing. The system ensures reliable communication between all components
    with proper error handling and metrics tracking.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import atexit
import json
import logging
import os
import queue
import sqlite3
import threading
import time
import traceback
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any
from collections.abc import Callable

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Queue settings
DEFAULT_QUEUE_SIZE = 10000
PRIORITY_QUEUE_SIZE = 1000
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 1  # seconds

# Persistence settings
EVENT_LOG_RETENTION_DAYS = 30
PERSIST_BATCH_SIZE = 100
PERSIST_INTERVAL = 5  # seconds

# Threading settings
MAX_WORKER_THREADS = 10
WORKER_THREAD_COUNT = 3
HANDLER_TIMEOUT = 30  # seconds

# ==============================================================================
# P2-4: Per-thread event loop for ASYNC handlers
# ==============================================================================
_thread_local = threading.local()


def _get_thread_loop() -> asyncio.AbstractEventLoop:
    """Return a persistent event loop for the calling thread.

    Creates a new loop on first access (or after the previous loop was closed).
    This avoids the overhead and GIL contention of ``asyncio.run()``
    (which creates *and tears down* a loop on every call) and is safe to call
    from worker threads that do not themselves host a running loop.
    """
    loop = getattr(_thread_local, 'loop', None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _thread_local.loop = loop
    return loop


# ==============================================================================
# ENUMS
# ==============================================================================
class EventType(Enum):
    """Event types for the trading system"""
    # System events
    SYSTEM = "system"
    SYSTEM_START = "system_start"
    SYSTEM_ERROR = "system_error"
    SYSTEM_METRICS = "system_metrics"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    CONFIG_CHANGE = "config_change"

    # Market data events
    MARKET_DATA = "market_data"
    MARKET_DATA_TICK = "market_data_tick"
    QUOTE_UPDATE = "quote_update"
    OPTION_CHAIN_UPDATE = "option_chain_update"
    GREEKS_UPDATE = "greeks_update"
    VOLUME_UPDATE = "volume_update"
    DATA_STALE = "data_stale"
    DATA_FRESH = "data_fresh"
    CUSTOM_METRIC_UPDATE = "custom_metric_update"

    # Trading events
    TRADING = "trading"
    TRADE = "trade"
    ORDER_PLACED = "order_placed"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_EXPIRED = "order_expired"
    ORDER_REJECTED = "order_rejected"
    ORDER_ORPHANED = "order_orphaned"
    ORDER_UN_ORPHANED = "order_un_orphaned"  # A9 (v14): recovered after orphan
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"

    # Risk events
    RISK = "risk"
    RISK_LIMIT_BREACH = "risk_limit_breach"
    RISK_VIOLATION = "risk_violation"
    MARGIN_CALL = "margin_call"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    FLATTEN_REQUEST = "flatten_request"  # P2-2: flatten all positions (e.g. prolonged data stale)

    # Connection events
    CONNECTION = "connection"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_LOST = "connection_lost"
    CONNECTION_RESTORED = "connection_restored"

    # Error events
    ERROR = "error"
    ERROR_OCCURRED = "error_occurred"
    CRITICAL_ERROR = "critical_error"
    WARNING = "warning"

    # Strategy events
    STRATEGY = "strategy"
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    STRATEGY_ERROR = "strategy_error"
    SIGNAL_GENERATED = "signal_generated"  # Strategy signal generated
    PERFORMANCE_UPDATE = "performance_update"  # Performance metrics updated

    # Account events
    ACCOUNT = "account"
    ACCOUNT_UPDATE = "account_update"
    BALANCE_UPDATE = "balance_update"
    MARGIN_UPDATE = "margin_update"

    # General events
    NOTIFICATION = "notification"
    ALERT = "alert"
    INFO = "info"
    DEBUG = "debug"

    # System control events
    KILL_SWITCH = "kill_switch"  # O-4: hard stop — halt all new order submission
    EMERGENCY = "emergency"      # P0-2: catastrophic-loss breach (emitted by E11/E13)

class EventPriority(Enum):
    """Event priorities with numeric values"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    EMERGENCY = 5

class HandlerType(Enum):
    """Types of event handlers"""
    SYNC = auto()
    ASYNC = auto()
    THREADED = auto()

# ==============================================================================
# CUSTOM JSON ENCODER FOR DATETIME
# ==============================================================================
class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Event:
    """Enhanced event data structure"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.SYSTEM
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: EventPriority = EventPriority.NORMAL
    source: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    ttl: int | None = None  # Time to live in seconds

    @classmethod
    def create(cls, event_type: "EventType", source: str, data: dict) -> "Event":
        """Factory classmethod: Event.create(EventType.X, source, data) → Event."""
        return cls(event_type=event_type, source=source, data=data)

    def __post_init__(self):
        # Normalize event_type to this module's EventType even when callers pass
        # enum members from another loaded copy of the module.
        if isinstance(self.event_type, str):
            try:
                self.event_type = EventType(str(self.event_type).lower())
            except Exception:
                self.event_type = EventType.SYSTEM
        elif not isinstance(self.event_type, Enum):
            try:
                self.event_type = EventType(str(self.event_type).lower())
            except Exception:
                self.event_type = EventType.SYSTEM

        # Normalize priority similarly for cross-module enum identity mismatches.
        if isinstance(self.priority, str):
            raw_priority = self.priority.name if isinstance(self.priority, Enum) else self.priority
            try:
                self.priority = EventPriority[raw_priority.upper()] if isinstance(raw_priority, str) else EventPriority.NORMAL  # noqa: E501
            except KeyError:
                self.priority = EventPriority.NORMAL
        elif not isinstance(self.priority, Enum):
            try:
                self.priority = EventPriority[str(self.priority).upper()]
            except KeyError:
                self.priority = EventPriority.NORMAL

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary with proper serialization"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.name,
            'source': self.source,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata,
            'ttl': self.ttl
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        return cls(
            event_id=data.get('event_id', str(uuid.uuid4())),
            event_type=EventType(data.get('event_type', 'system')),
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),  # noqa: E501
            priority=EventPriority[data.get('priority', 'NORMAL')],
            source=data.get('source'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {}),
            ttl=data.get('ttl')
        )


# Keep a stable local reference so external test bootstraps cannot clobber
# the global `Event` symbol used by EventManager methods.
_A05_EVENT_CLASS = Event

@dataclass
class HandlerInfo:
    """Event handler information"""
    handler_id: str
    name: str
    func: Callable[[Event], None]
    event_types: set[EventType]
    handler_type: HandlerType = HandlerType.SYNC
    filter_func: Callable[[Event], bool] | None = None
    priority: int = 0  # Higher priority handlers execute first
    weak_ref: bool = False
    execution_count: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    disabled: bool = False
    total_execution_time: float = 0.0
    last_execution: datetime | None = None
    last_error: str | None = None

@dataclass
class EventMetrics:
    """Event system metrics"""
    events_published: int = 0
    events_processed: int = 0
    events_failed: int = 0
    events_filtered: int = 0
    events_expired: int = 0
    handlers_registered: int = 0
    handlers_executed: int = 0
    avg_processing_time: float = 0.0
    queue_size: int = 0
    priority_queue_size: int = 0

# ==============================================================================
# EVENT FILTER CLASS
# ==============================================================================
class EventFilter:
    """Advanced event filtering system"""

    def __init__(self):
        """Initialize event filter"""
        self.filters: list[Callable[[Event], bool]] = []
        self.exclusions: set[EventType] = set()
        self.inclusions: set[EventType] = set()
        self.source_filters: set[str] = set()
        self.priority_threshold: EventPriority | None = None

    def add_filter(self, filter_func: Callable[[Event], bool]) -> None:
        """Add custom filter function"""
        self.filters.append(filter_func)

    def remove_filter(self, filter_func: Callable[[Event], bool]) -> None:
        """Remove custom filter function"""
        if filter_func in self.filters:
            self.filters.remove(filter_func)

    def exclude_type(self, event_type: EventType) -> None:
        """Exclude specific event type"""
        self.exclusions.add(event_type)

    def include_only_types(self, event_types: list[EventType]) -> None:
        """Include only specific event types"""
        self.inclusions = set(event_types)

    def filter_by_source(self, sources: list[str]) -> None:
        """Filter by event source"""
        self.source_filters = set(sources)

    def set_priority_threshold(self, priority: EventPriority) -> None:
        """Set minimum priority threshold"""
        self.priority_threshold = priority

    def apply(self, event: Event) -> bool:
        """Apply all filters to event"""
        # Check exclusions
        if event.event_type in self.exclusions:
            return False

        # Check inclusions
        if self.inclusions and event.event_type not in self.inclusions:
            return False

        # Check source filters
        if self.source_filters and event.source not in self.source_filters:
            return False

        # Check priority threshold
        if self.priority_threshold and event.priority.value < self.priority_threshold.value:
            return False

        # Apply custom filters
        return all(filter_func(event) for filter_func in self.filters)

# ==============================================================================
# MAIN EVENT MANAGER CLASS
# ==============================================================================
class EventManager:
    """
    Centralized event management system for Spyder.

    This class provides comprehensive event handling with support for
    priority queues, asynchronous processing, filtering, persistence,
    and metrics tracking. It serves as the central nervous system for
    all inter-component communication within the trading platform.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_queue: Main event queue
        priority_queue: High-priority event queue
        handlers: Registry of event handlers
        global_handlers: Handlers that receive all events
        executor: Thread pool for async handlers
        is_running: System running state
        persist_events: Whether to persist events to database

    Example:
        >>> manager = EventManager()
        >>> manager.start()
        >>> manager.subscribe(EventType.TRADE, my_handler)
        >>> manager.emit(EventType.TRADE, {"symbol": "SPY", "action": "BUY"})
        >>> manager.stop()
    """

    # Tracks how many instances have been created.  More than one outside of
    # ``get_event_manager()`` is almost certainly a bug (fragmented bus).
    _constructed_count: int = 0
    _construction_lock = threading.Lock()

    @staticmethod
    def _allow_multiple() -> bool:
        """Return True when multiple instances are explicitly permitted.

        Set the environment variable ``SPYDER_ALLOW_MULTIPLE_EM=1`` in unit
        tests that deliberately construct isolated EventManager instances.
        """
        return os.environ.get("SPYDER_ALLOW_MULTIPLE_EM", "0") == "1"

    def __init__(self, persist_events: bool = True,
                 db_path: Path | None = None):
        """
        Initialize event manager.

        Args:
            persist_events: Enable event persistence
            db_path: Optional database path
        """
        with EventManager._construction_lock:
            EventManager._constructed_count += 1
            if EventManager._constructed_count > 1 and not EventManager._allow_multiple():
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "EventManager: multiple instances detected (count=%d). "
                    "Use get_event_manager() to share a single instance. "
                    "Set SPYDER_ALLOW_MULTIPLE_EM=1 to suppress this warning in tests.",
                    EventManager._constructed_count,
                )

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # State management
        self.is_running = False
        self.persist_events = persist_events

        # Queues
        self.event_queue = queue.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        self.priority_queue = queue.PriorityQueue(maxsize=PRIORITY_QUEUE_SIZE)

        # Handler registry
        self.handlers: dict[EventType, list[HandlerInfo]] = defaultdict(list)
        self.global_handlers: list[HandlerInfo] = []
        self.handler_lock = threading.RLock()

        # Filtering
        self.global_filter = EventFilter()

        # Threading
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self._shutdown_event = threading.Event()
        self.worker_threads: list[threading.Thread] = []
        self._persistence_thread: threading.Thread | None = None
        self._metrics_thread: threading.Thread | None = None

        # Persistence
        self.db_path = db_path or Path.home() / ".spyder" / "events.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.persist_events:
            self._init_database()
        self._persist_queue = queue.Queue()

        # Metrics
        self.metrics = EventMetrics()
        self._metrics_lock = threading.Lock()

        # Event history
        self.event_history = deque(maxlen=1000)
        self._history_lock = threading.Lock()

        # Dead letter queue
        self.dead_letter_queue = deque(maxlen=100)

        # Per-handler error ring (P1-12)
        self._handler_errors: deque = deque(maxlen=100)
        self._handler_errors_lock = threading.Lock()

        self.logger.info("EventManager initialized")

    def get(self, key: str, default: Any = None) -> Any:
        """Get method for compatibility."""
        config_defaults = {
            'max_queue_size': DEFAULT_QUEUE_SIZE,
            'priority_queue_size': PRIORITY_QUEUE_SIZE,
            'worker_threads': WORKER_THREAD_COUNT,
            'persist_events': self.persist_events,
            'database_path': str(self.db_path) if hasattr(self, 'db_path') else None
        }
        return config_defaults.get(key, default)

    # ==========================================================================
    # DATABASE INITIALIZATION
    # ==========================================================================
    def _init_database(self):
        """Initialize event persistence database"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_log (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT,
                        timestamp TEXT,
                        priority TEXT,
                        source TEXT,
                        data TEXT,
                        metadata TEXT
                    )
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON event_log(timestamp)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_event_type
                    ON event_log(event_type)
                """)

                self.logger.info("Event database initialized")

        except Exception as e:
            self.logger.error("Database initialization error: %s", e)

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the event manager.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("EventManager already running")
                return True

            self.logger.info("Starting EventManager...")

            # Clear shutdown event
            self._shutdown_event.clear()

            # Start worker threads
            for i in range(WORKER_THREAD_COUNT):
                thread = threading.Thread(
                    target=self._process_events,
                    name=f"EventWorker-{i}",
                    daemon=True
                )
                thread.start()
                self.worker_threads.append(thread)

            # Start persistence thread
            if self.persist_events:
                self._persistence_thread = threading.Thread(
                    target=self._persistence_loop,
                    name="EventPersistence",
                    daemon=True
                )
                self._persistence_thread.start()

            # Start metrics thread
            self._metrics_thread = threading.Thread(
                target=self._metrics_loop,
                name="EventMetrics",
                daemon=True
            )
            self._metrics_thread.start()

            self.is_running = True
            self.logger.info("EventManager started successfully")

            # Emit startup event
            self.emit(
                EventType.SYSTEM_START,
                {
                    'component': 'EventManager',
                    'timestamp': datetime.now()
                }
            )

            return True

        except Exception as e:
            self.logger.error("Failed to start EventManager: %s", e)
            self.error_handler.handle_error(e, "event_manager_start")
            return False

    def stop(self, timeout: float = 5.0) -> bool:
        """
        Stop the event manager.

        Args:
            timeout: Maximum time to wait for shutdown

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.is_running:
                self.logger.warning("EventManager not running")
                return True

            self.logger.info("Stopping EventManager...")

            # Emit shutdown event
            self.emit(
                EventType.SHUTDOWN,
                {
                    'component': 'EventManager',
                    'timestamp': datetime.now()
                }
            )

            # Signal shutdown
            self._shutdown_event.set()

            # A10 (v14): after shutdown is signaled, workers stop pulling new
            # items; drain any queued-but-unprocessed items so unfinished_tasks
            # reflects explicit shutdown drops instead of leaking.
            def _drain_unprocessed(q, name: str) -> None:
                dropped = 0
                while True:
                    try:
                        q.get_nowait()
                        dropped += 1
                        q.task_done()
                    except queue.Empty:
                        break
                    except ValueError:
                        # task_done called too many times; stop draining safely
                        break
                if dropped:
                    self.logger.info(
                        "A10: dropped %s unprocessed %s events during shutdown",
                        dropped,
                        name,
                    )

            _drain_unprocessed(self.priority_queue, "priority")
            _drain_unprocessed(self.event_queue, "regular")
            if self.persist_events:
                _drain_unprocessed(self._persist_queue, "persist")

            # A10 (v14): bounded drain — unconditional join() can block forever
            # when a handler holds a task_done(). Cap drain time at half the
            # stop() timeout so the rest of the shutdown sequence can still run.
            drain_deadline = time.time() + max(0.1, timeout / 2.0)

            def _bounded_join(q) -> bool:
                """Wait on queue.unfinished_tasks up to drain_deadline."""
                while time.time() < drain_deadline:
                    if getattr(q, "unfinished_tasks", 0) == 0:
                        return True
                    time.sleep(0.02)
                return getattr(q, "unfinished_tasks", 0) == 0

            try:
                if not _bounded_join(self.event_queue):
                    self.logger.warning(
                        "A10: event_queue drain timed out; %s tasks left unfinished",
                        getattr(self.event_queue, "unfinished_tasks", "?"),
                    )
                if not _bounded_join(self.priority_queue):
                    self.logger.warning(
                        "A10: priority_queue drain timed out; %s tasks left unfinished",
                        getattr(self.priority_queue, "unfinished_tasks", "?"),
                    )
                if self.persist_events and not _bounded_join(self._persist_queue):
                    self.logger.warning(
                        "A10: persist_queue drain timed out; %s tasks left unfinished",
                        getattr(self._persist_queue, "unfinished_tasks", "?"),
                    )
            except (RuntimeError, AttributeError) as e:
                # Queue join may fail if queue already closed or in invalid state
                self.logger.warning("Error waiting for queues during shutdown: %s", e)

            # Stop worker threads
            for thread in self.worker_threads:
                thread.join(timeout=timeout/len(self.worker_threads))

            # Stop persistence thread
            if self._persistence_thread:
                self._persistence_thread.join(timeout=1.0)

            # Stop metrics thread
            if self._metrics_thread:
                self._metrics_thread.join(timeout=1.0)

            # Shutdown executor — `timeout` kwarg was added in Python 3.9;
            # guard for environments where it may not be accepted.
            try:
                self.executor.shutdown(wait=True, timeout=timeout)
            except TypeError:
                self.executor.shutdown(wait=True)

            self.is_running = False
            self.logger.info("EventManager stopped successfully")

            return True

        except Exception as e:
            self.logger.error("Error stopping EventManager: %s", e)
            self.error_handler.handle_error(e, "event_manager_stop")
            return False

    def shutdown(self):
        """Shutdown event manager (alias for stop)"""
        return self.stop()

    # ==========================================================================
    # EVENT PROCESSING
    # ==========================================================================
    def _process_events(self):
        """Main event processing loop"""
        self.logger.info("Event processor started")

        while not self._shutdown_event.is_set():
            try:
                # Check priority queue first
                try:
                    _, _, event = self.priority_queue.get_nowait()
                    try:
                        self._process_single_event(event)
                    finally:
                        self.priority_queue.task_done()
                    continue
                except queue.Empty:
                    pass

                # Check regular queue
                try:
                    event = self.event_queue.get(timeout=0.1)
                    try:
                        self._process_single_event(event)
                    finally:
                        self.event_queue.task_done()
                except queue.Empty:
                    continue

            except Exception as e:
                self.logger.error("Event processing error: %s", e)
                self.error_handler.handle_error(e, "event_processing")

    def _process_single_event(self, event: Event):
        """Process a single event"""
        try:
            # Update metrics
            with self._metrics_lock:
                self.metrics.events_processed += 1

            # Add to history
            with self._history_lock:
                self.event_history.append(event)

            # Get handlers
            with self.handler_lock:
                type_handlers = self.handlers.get(event.event_type, []).copy()
                global_handlers = self.global_handlers.copy()

            # Execute type-specific handlers
            for handler in sorted(type_handlers, key=lambda h: -h.priority):
                self._execute_handler(handler, event)

            # Execute global handlers
            for handler in sorted(global_handlers, key=lambda h: -h.priority):
                self._execute_handler(handler, event)

            # Persist if needed
            if self.persist_events and event.priority.value >= EventPriority.HIGH.value:
                self._persist_queue.put(event)

        except Exception as e:
            with self._metrics_lock:
                self.metrics.events_failed += 1
            self.logger.error("Event processing failed: %s", e)
            self.dead_letter_queue.append(event)

    def _execute_handler(self, handler: HandlerInfo, event: Event):
        """Execute a single handler"""
        # P1-12: skip disabled handlers
        if handler.disabled:
            return

        try:
            # Apply filter
            if handler.filter_func and not handler.filter_func(event):
                return

            # Record start time
            start_time = time.time()

            # Execute based on type
            if handler.handler_type == HandlerType.SYNC:
                handler.func(event)
            elif handler.handler_type == HandlerType.ASYNC:
                # P2-4: reuse a per-thread loop instead of creating a new one per call
                _get_thread_loop().run_until_complete(handler.func(event))
            elif handler.handler_type == HandlerType.THREADED:
                self.executor.submit(handler.func, event)

            # Update metrics
            handler.execution_count += 1
            handler.consecutive_errors = 0  # reset on success
            handler.total_execution_time += time.time() - start_time
            handler.last_execution = datetime.now()

            with self._metrics_lock:
                self.metrics.handlers_executed += 1

        except Exception as e:
            handler.error_count += 1
            handler.consecutive_errors += 1
            handler.last_error = str(e)
            tb = traceback.format_exc()
            self.logger.error("Handler %s error: %s", handler.name, e)

            # P1-12: record to error ring
            error_record = {
                "handler_name": handler.name,
                "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),  # noqa: E501
                "error": str(e),
                "traceback": tb,
                "consecutive": handler.consecutive_errors,
                "ts": datetime.now().isoformat(),
            }
            with self._handler_errors_lock:
                self._handler_errors.append(error_record)

            # P1-12: circuit-break after 3 consecutive failures
            if handler.consecutive_errors >= 3:
                handler.disabled = True
                self.logger.critical(
                    "Handler %s disabled after %d consecutive errors; last: %s",
                    handler.name, handler.consecutive_errors, e,
                )
                self._emit_system_error(handler.name, event, tb)

    def _emit_system_error(self, handler_name: str, event: Event, tb: str) -> None:
        """Emit SYSTEM_ERROR for a disabled handler (best-effort; never raises)."""
        try:
            err_event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.SYSTEM_ERROR,
                data={
                    "handler_name": handler_name,
                    "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),  # noqa: E501
                    "traceback": tb,
                    "reason": "handler_circuit_open",
                },
                source="EventManager",
                priority=EventPriority.HIGH,
            )
            # Place directly on the high-priority queue to avoid recursion
            try:
                self.priority_queue.put_nowait((
                    -EventPriority.HIGH.value,
                    err_event.timestamp,
                    err_event,
                ))
            except Exception:
                self.dead_letter_queue.append(err_event)
        except Exception as inner:
            self.logger.error("_emit_system_error failed: %s", inner)

    def get_handler_errors(self) -> list:
        """Return a copy of the per-handler error ring (newest last).

        Returns:
            List of dicts with keys: handler_name, event_type, error,
            traceback, consecutive, ts.
        """
        with self._handler_errors_lock:
            return list(self._handler_errors)

    # ==========================================================================
    # BACKGROUND LOOPS
    # ==========================================================================
    def _persistence_loop(self):
        """Persistence background loop"""
        batch = []
        last_persist = time.time()

        while not self._shutdown_event.is_set():
            try:
                # Get events from queue
                try:
                    event = self._persist_queue.get(timeout=1)
                    batch.append(event)
                except queue.Empty:
                    pass

                # Persist batch if needed
                current_time = time.time()
                if (len(batch) >= PERSIST_BATCH_SIZE or
                    current_time - last_persist >= PERSIST_INTERVAL) and batch:

                    to_persist = list(batch)
                    self._persist_batch(to_persist)
                    for _ in to_persist:
                        try:
                            self._persist_queue.task_done()
                        except ValueError:
                            break
                    batch.clear()
                    last_persist = current_time

            except Exception as e:
                self.logger.error("Persistence loop error: %s", e)

        # Best-effort final flush before thread exits.
        if batch:
            try:
                to_persist = list(batch)
                self._persist_batch(to_persist)
                for _ in to_persist:
                    try:
                        self._persist_queue.task_done()
                    except ValueError:
                        break
            except Exception as e:
                self.logger.error("Final persistence flush error: %s", e)

    def _persist_batch(self, events: list[Event]):
        """Persist batch of events to database"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                for event in events:
                    data_json = json.dumps(event.data, cls=DateTimeEncoder)
                    metadata_json = json.dumps(event.metadata, cls=DateTimeEncoder)

                    conn.execute("""
                        INSERT OR REPLACE INTO event_log
                        (event_id, event_type, timestamp, priority, source, data, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.event_id,
                        event.event_type.value,
                        event.timestamp.isoformat(),
                        event.priority.name,
                        event.source or '',
                        data_json,
                        metadata_json
                    ))

                conn.commit()
                self.logger.debug("Persisted %s events", len(events))

        except Exception as e:
            self.logger.error("Batch persistence error: %s", e)

    def _metrics_loop(self):
        """Metrics calculation loop"""
        while not self._shutdown_event.is_set():
            try:
                self._shutdown_event.wait(timeout=10)  # Update metrics every 10 seconds
                if self._shutdown_event.is_set():
                    break

                with self._metrics_lock:
                    self.metrics.queue_size = self.event_queue.qsize()
                    self.metrics.priority_queue_size = self.priority_queue.qsize()

                    if self.metrics.events_processed > 0:
                        total_time = sum(
                            h.total_execution_time
                            for handlers in self.handlers.values()
                            for h in handlers
                        )
                        self.metrics.avg_processing_time = (
                            total_time / self.metrics.events_processed
                        )

            except Exception as e:
                self.logger.error("Metrics loop error: %s", e)

    # ==========================================================================
    # PUBLIC METHODS - SUBSCRIPTION
    # ==========================================================================
    def subscribe(self, event_type: EventType, handler: Callable,
                  name: str | None = None,
                  handler_type: HandlerType = HandlerType.SYNC,
                  filter_func: Callable | None = None,
                  priority: int = 0) -> str:
        """
        Subscribe to events.

        Args:
            event_type: Type of event to subscribe to
            handler: Handler function
            name: Optional handler name
            handler_type: Type of handler execution
            filter_func: Optional filter function
            priority: Handler priority (higher executes first)

        Returns:
            Handler ID for unsubscription
        """
        handler_id = str(uuid.uuid4())
        handler_name = name or f"{handler.__name__}_{handler_id[:8]}"

        handler_info = HandlerInfo(
            handler_id=handler_id,
            name=handler_name,
            func=handler,
            event_types={event_type},
            handler_type=handler_type,
            filter_func=filter_func,
            priority=priority
        )

        with self.handler_lock:
            self.handlers[event_type].append(handler_info)

        with self._metrics_lock:
            self.metrics.handlers_registered += 1

        self.logger.info("Handler %s subscribed to %s", handler_name, event_type.value)
        return handler_id

    def subscribe_all(self, handler: Callable, name: str | None = None,
                      **kwargs) -> str:
        """Subscribe to all events"""
        handler_id = str(uuid.uuid4())
        handler_name = name or f"{handler.__name__}_{handler_id[:8]}"

        handler_info = HandlerInfo(
            handler_id=handler_id,
            name=handler_name,
            func=handler,
            event_types=set(EventType),
            **kwargs
        )

        with self.handler_lock:
            self.global_handlers.append(handler_info)

        with self._metrics_lock:
            self.metrics.handlers_registered += 1

        self.logger.info("Handler %s subscribed to all events", handler_name)
        return handler_id

    def unsubscribe(self, handler_id_or_type, callback=None) -> bool:
        """
        Unsubscribe handler.

        Accepts two call signatures:
        - ``unsubscribe(handler_id: str)`` — original form using the ID returned by subscribe()
        - ``unsubscribe(event_type: EventType, callback: Callable)`` — convenience form for tests

        Returns:
            True if handler was found and removed
        """
        # Convenience overload: unsubscribe(event_type, callable)
        if callback is not None:
            with self.handler_lock:
                handlers = self.handlers.get(handler_id_or_type, [])
                for i, h in enumerate(handlers):
                    if h.func is callback or h.func == callback:
                        handlers.pop(i)
                        with self._metrics_lock:
                            self.metrics.handlers_registered -= 1
                        return True
            return False

        handler_id = handler_id_or_type
        with self.handler_lock:
            # Check type-specific handlers
            for _event_type, handlers in self.handlers.items():
                for i, handler in enumerate(handlers):
                    if handler.handler_id == handler_id:
                        removed = handlers.pop(i)
                        self.logger.info("Handler %s unsubscribed", removed.name)

                        with self._metrics_lock:
                            self.metrics.handlers_registered -= 1

                        return True

            # Check global handlers
            for i, handler in enumerate(self.global_handlers):
                if handler.handler_id == handler_id:
                    removed = self.global_handlers.pop(i)
                    self.logger.info("Global handler %s unsubscribed", removed.name)

                    with self._metrics_lock:
                        self.metrics.handlers_registered -= 1

                    return True

        return False

    # ==========================================================================
    # PUBLIC METHODS - PUBLISHING
    # ==========================================================================
    def publish(self, event: Event) -> bool:
        """
        Publish event to queue.

        Args:
            event: Event to publish

        Returns:
            bool: True if event queued successfully
        """
        try:
            # Apply global filter
            if not self.global_filter.apply(event):
                with self._metrics_lock:
                    self.metrics.events_filtered += 1
                return False

            # Check TTL
            if event.ttl and (datetime.now() - event.timestamp).total_seconds() > event.ttl:
                with self._metrics_lock:
                    self.metrics.events_expired += 1
                return False

            # Update metrics
            with self._metrics_lock:
                self.metrics.events_published += 1

            # Synchronous dispatch when not yet started (e.g., unit tests)
            if not self.is_running:
                self._process_single_event(event)
                return True

            # Add to appropriate queue
            if event.priority.value >= EventPriority.HIGH.value:
                self.priority_queue.put((
                    -event.priority.value,  # Negative for correct priority order
                    event.timestamp,
                    event
                ))
            else:
                self.event_queue.put(event)

            return True

        except queue.Full:
            self.logger.error("Event queue full")
            return False
        except Exception as e:
            self.logger.error("Event publish error: %s", e)
            return False

    def emit(self, event_type: EventType, data: dict[str, Any],
             priority: EventPriority = EventPriority.NORMAL,
             source: str | None = None, **kwargs) -> bool:
        """
        Create and publish event.

        Args:
            event_type: Type of event
            data: Event data
            priority: Event priority
            source: Event source
            **kwargs: Additional event attributes

        Returns:
            bool: True if event published successfully
        """
        event = _A05_EVENT_CLASS(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source or self.__class__.__name__,
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {}),
            ttl=kwargs.get('ttl')
        )

        return self.publish(event)

    def create_event(self, event_type: EventType, data: dict[str, Any],
                    **kwargs) -> Event:
        """Create event without publishing"""
        return _A05_EVENT_CLASS(
            event_type=event_type,
            data=data,
            priority=kwargs.get('priority', EventPriority.NORMAL),
            source=kwargs.get('source', self.__class__.__name__),
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {}),
            ttl=kwargs.get('ttl')
        )

    # ==========================================================================
    # QUERY METHODS
    # ==========================================================================
    def get_event_history(self, limit: int | None = None,
                         event_type: EventType | None = None) -> list[Event]:
        """Get recent event history"""
        with self._history_lock:
            events = list(self.event_history)

            if event_type:
                events = [e for e in events if e.event_type == event_type]

            if limit:
                events = events[-limit:]

            return events

    def get_recent_events(self, event_type: EventType | None = None,
                          limit: int | None = None) -> list[Event]:
        """Alias for get_event_history with swapped arg order for test convenience."""
        return self.get_event_history(limit=limit, event_type=event_type)

    def get_handler_stats(self) -> list[dict[str, Any]]:
        """Get handler statistics"""
        stats = []

        with self.handler_lock:
            all_handlers = []

            for handlers in self.handlers.values():
                all_handlers.extend(handlers)
            all_handlers.extend(self.global_handlers)

            # Generate stats
            for handler in all_handlers:
                avg_time = (
                    handler.total_execution_time / handler.execution_count
                    if handler.execution_count > 0 else 0
                )

                stats.append({
                    'name': handler.name,
                    'event_types': [et.value for et in handler.event_types],
                    'execution_count': handler.execution_count,
                    'error_count': handler.error_count,
                    'avg_execution_time_ms': avg_time * 1000,
                    'last_execution': handler.last_execution,
                    'last_error': handler.last_error
                })

        return stats

    def get_metrics(self) -> dict[str, Any]:
        """Get event system metrics"""
        with self._metrics_lock:
            return {
                'events_published': self.metrics.events_published,
                'events_processed': self.metrics.events_processed,
                'events_failed': self.metrics.events_failed,
                'events_filtered': self.metrics.events_filtered,
                'events_expired': self.metrics.events_expired,
                'handlers_registered': self.metrics.handlers_registered,
                'handlers_executed': self.metrics.handlers_executed,
                'avg_processing_time': self.metrics.avg_processing_time,
                'queue_size': self.metrics.queue_size,
                'priority_queue_size': self.metrics.priority_queue_size,
                'dead_letter_queue_size': len(self.dead_letter_queue)
            }

    def clear_handlers(self, event_type: EventType | None = None):
        """Clear event handlers"""
        with self.handler_lock:
            if event_type:
                self.handlers[event_type].clear()
                self.logger.debug("Cleared handlers for %s", event_type.value)
            else:
                self.handlers.clear()
                self.global_handlers.clear()
                self.metrics.handlers_registered = 0
                self.logger.debug("Cleared all event handlers")

    def add_global_filter(self, filter_func: Callable[[Event], bool]):
        """Add global event filter"""
        self.global_filter.add_filter(filter_func)

    def remove_global_filter(self, filter_func: Callable[[Event], bool]):
        """Remove global event filter"""
        self.global_filter.remove_filter(filter_func)


# Keep a stable local reference so external test bootstraps cannot clobber
# the global `EventManager` symbol used by singleton helpers.
_A05_EVENT_MANAGER_CLASS = EventManager

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_event_manager_instance: EventManager | None = None
_event_manager_lock = threading.Lock()

def get_event_manager(persist_events: bool = True) -> EventManager:
    """
    Get singleton EventManager instance.

    Args:
        persist_events: Enable event persistence

    Returns:
        EventManager instance
    """
    global _event_manager_instance

    with _event_manager_lock:
        if _event_manager_instance is None:
            _event_manager_instance = _A05_EVENT_MANAGER_CLASS(persist_events=persist_events)
            # Register atexit cleanup so the executor shuts down before Python's
            # own ThreadPoolExecutor._python_exit atexit fires.  atexit runs in
            # LIFO order, so this handler executes first and stops all worker
            # threads cleanly, eliminating the
            # "cannot schedule new futures after interpreter shutdown" warning.
            atexit.register(_event_manager_atexit_cleanup)

        return _event_manager_instance

def _event_manager_atexit_cleanup() -> None:
    """Stop the EventManager singleton at interpreter exit.

    Registered via ``atexit`` (LIFO) so this fires *before* the
    ``ThreadPoolExecutor._python_exit`` atexit handler.  This ensures all
    worker threads are joined and the executor is shut down cleanly, which
    prevents the ``cannot schedule new futures after interpreter shutdown``
    RuntimeWarning.
    """
    global _event_manager_instance
    with _event_manager_lock:
        inst = _event_manager_instance
    if inst is not None and getattr(inst, "is_running", False):
        try:
            inst.stop()
        except Exception:
            pass


def reset_event_manager():
    """Reset the singleton instance (for testing)"""
    global _event_manager_instance
    with _event_manager_lock:
        if _event_manager_instance and _event_manager_instance.is_running:
            _event_manager_instance.stop()
        _event_manager_instance = None
    with EventManager._construction_lock:
        EventManager._constructed_count = 0

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    import json


    # Create event manager
    em = EventManager(persist_events=False)

    # Test handler registration

    def test_handler(event: Event):
        pass

    handler_id = em.subscribe(EventType.SYSTEM, test_handler, name="TestHandler")

    # Test global handler
    def global_handler(event: Event):
        pass

    global_id = em.subscribe_all(global_handler, name="GlobalHandler")

    # Start event manager
    if em.start():

        # Test event publishing

        # Publish test events
        em.emit(EventType.SYSTEM, {'message': 'Test system event'})
        em.emit(EventType.TRADING, {'action': 'Test trade'})
        em.emit(EventType.RISK, {'warning': 'Test risk event'}, priority=EventPriority.HIGH)

        # Wait for processing
        import time
        time.sleep(1)

        # Get metrics
        metrics = em.get_metrics()

        # Test filtering

        def priority_filter(event: Event) -> bool:
            return event.priority.value >= EventPriority.HIGH.value

        filtered_handler_id = em.subscribe(
            EventType.RISK,
            lambda e: logging.debug("High priority: %s", e.data),
            filter_func=priority_filter,
            name="FilteredHandler"
        )

        # Emit events with different priorities
        em.emit(EventType.RISK, {'level': 'low'}, priority=EventPriority.LOW)
        em.emit(EventType.RISK, {'level': 'high'}, priority=EventPriority.HIGH)

        time.sleep(1)

        # Test handler statistics
        stats = em.get_handler_stats()
        for _stat in stats:
            pass

        # Test event history
        history = em.get_event_history(limit=5)
        for _event in history:
            pass

        # Test unsubscribe
        if em.unsubscribe(handler_id):
            pass

        # Stop event manager
        if em.stop():
            pass
    else:
        pass



class EventBus:
    """Event bus for managing event distribution"""

    def __init__(self):
        self.subscribers = {}

    def subscribe(self, event_type, callback):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, event_type, data=None):
        """Publish an event"""
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logging.getLogger(__name__).warning(
                        "EventBus subscriber callback for '%s' failed: %s", event_type, e
                    )

    def unsubscribe(self, event_type, callback=None):
        """Unsubscribe from an event type"""
        if event_type in self.subscribers:
            if callback:
                self.subscribers[event_type].remove(callback)
            else:
                self.subscribers[event_type].clear()

def get_event_bus():
    """Factory function to get EventBus instance"""
    return EventBus()

