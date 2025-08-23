#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import json
import queue
import sqlite3
import threading
import time
import uuid
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

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
# ENUMS
# ==============================================================================
class EventType(Enum):
    """Event types for the trading system"""
    # System events
    SYSTEM = "system"
    SYSTEM_START = "system_start"
    SYSTEM_ERROR = "system_error"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    HEARTBEAT = "heartbeat"
    CONFIG_CHANGE = "config_change"
    
    # Market data events
    MARKET_DATA = "market_data"
    QUOTE_UPDATE = "quote_update"
    OPTION_CHAIN_UPDATE = "option_chain_update"
    GREEKS_UPDATE = "greeks_update"
    VOLUME_UPDATE = "volume_update"
    
    # Trading events
    TRADING = "trading"
    TRADE = "trade"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    
    # Risk events
    RISK = "risk"
    RISK_LIMIT_BREACH = "risk_limit_breach"
    MARGIN_CALL = "margin_call"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    
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
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    priority: EventPriority = EventPriority.NORMAL
    source: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: Optional[int] = None  # Time to live in seconds
    
    def __post_init__(self):
        # Ensure event_type is EventType enum
        if isinstance(self.event_type, str):
            try:
                self.event_type = EventType(self.event_type)
            except ValueError:
                self.event_type = EventType.SYSTEM
        
        # Ensure priority is EventPriority enum
        if isinstance(self.priority, str):
            try:
                self.priority = EventPriority[self.priority.upper()]
            except KeyError:
                self.priority = EventPriority.NORMAL

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary"""
        return cls(
            event_id=data.get('event_id', str(uuid.uuid4())),
            event_type=EventType(data.get('event_type', 'system')),
            data=data.get('data', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            priority=EventPriority[data.get('priority', 'NORMAL')],
            source=data.get('source'),
            correlation_id=data.get('correlation_id'),
            metadata=data.get('metadata', {}),
            ttl=data.get('ttl')
        )

@dataclass
class HandlerInfo:
    """Event handler information"""
    handler_id: str
    name: str
    func: Callable[[Event], None]
    event_types: Set[EventType]
    handler_type: HandlerType = HandlerType.SYNC
    filter_func: Optional[Callable[[Event], bool]] = None
    priority: int = 0  # Higher priority handlers execute first
    weak_ref: bool = False
    execution_count: int = 0
    error_count: int = 0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    last_error: Optional[str] = None

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
        self.filters: List[Callable[[Event], bool]] = []
        self.exclusions: Set[EventType] = set()
        self.inclusions: Set[EventType] = set()
        self.source_filters: Set[str] = set()
        self.priority_threshold: Optional[EventPriority] = None
        
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
        
    def include_only_types(self, event_types: List[EventType]) -> None:
        """Include only specific event types"""
        self.inclusions = set(event_types)
        
    def filter_by_source(self, sources: List[str]) -> None:
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
        for filter_func in self.filters:
            if not filter_func(event):
                return False
                
        return True

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
    
    def __init__(self, persist_events: bool = True,
                 db_path: Optional[Path] = None):
        """
        Initialize event manager.
        
        Args:
            persist_events: Enable event persistence
            db_path: Optional database path
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # State management
        self.is_running = False
        self.persist_events = persist_events
        
        # Queues
        self.event_queue = queue.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        self.priority_queue = queue.PriorityQueue(maxsize=PRIORITY_QUEUE_SIZE)
        
        # Handler registry
        self.handlers: Dict[EventType, List[HandlerInfo]] = defaultdict(list)
        self.global_handlers: List[HandlerInfo] = []
        self.handler_lock = threading.RLock()
        
        # Filtering
        self.global_filter = EventFilter()
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self._shutdown_event = threading.Event()
        self.worker_threads: List[threading.Thread] = []
        self._persistence_thread: Optional[threading.Thread] = None
        self._metrics_thread: Optional[threading.Thread] = None
        
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
            self.logger.error(f"Database initialization error: {e}")
    
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
            self.logger.error(f"Failed to start EventManager: {e}")
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
            
            # Wait for queues to empty
            try:
                self.event_queue.join()
                self.priority_queue.join()
                if self.persist_events:
                    self._persist_queue.join()
            except:
                pass
            
            # Stop worker threads
            for thread in self.worker_threads:
                thread.join(timeout=timeout/len(self.worker_threads))
            
            # Stop persistence thread
            if self._persistence_thread:
                self._persistence_thread.join(timeout=1.0)
            
            # Stop metrics thread
            if self._metrics_thread:
                self._metrics_thread.join(timeout=1.0)
            
            # Shutdown executor
            self.executor.shutdown(wait=True, timeout=timeout)
            
            self.is_running = False
            self.logger.info("EventManager stopped successfully")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping EventManager: {e}")
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
                    self._process_single_event(event)
                    continue
                except queue.Empty:
                    pass
                
                # Check regular queue
                try:
                    event = self.event_queue.get(timeout=0.1)
                    self._process_single_event(event)
                except queue.Empty:
                    continue
                    
            except Exception as e:
                self.logger.error(f"Event processing error: {e}")
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
            self.logger.error(f"Event processing failed: {e}")
            self.dead_letter_queue.append(event)
    
    def _execute_handler(self, handler: HandlerInfo, event: Event):
        """Execute a single handler"""
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
                asyncio.run(handler.func(event))
            elif handler.handler_type == HandlerType.THREADED:
                self.executor.submit(handler.func, event)
            
            # Update metrics
            handler.execution_count += 1
            handler.total_execution_time += time.time() - start_time
            handler.last_execution = datetime.now()
            
            with self._metrics_lock:
                self.metrics.handlers_executed += 1
                
        except Exception as e:
            handler.error_count += 1
            handler.last_error = str(e)
            self.logger.error(f"Handler {handler.name} error: {e}")
    
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
                    
                    self._persist_batch(batch)
                    batch.clear()
                    last_persist = current_time
                    
            except Exception as e:
                self.logger.error(f"Persistence loop error: {e}")
    
    def _persist_batch(self, events: List[Event]):
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
                self.logger.debug(f"Persisted {len(events)} events")
                
        except Exception as e:
            self.logger.error(f"Batch persistence error: {e}")
    
    def _metrics_loop(self):
        """Metrics calculation loop"""
        while not self._shutdown_event.is_set():
            try:
                time.sleep(10)  # Update metrics every 10 seconds
                
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
                self.logger.error(f"Metrics loop error: {e}")
            
    # ==========================================================================
    # PUBLIC METHODS - SUBSCRIPTION
    # ==========================================================================
    def subscribe(self, event_type: EventType, handler: Callable,
                  name: Optional[str] = None,
                  handler_type: HandlerType = HandlerType.SYNC,
                  filter_func: Optional[Callable] = None,
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
            
        self.logger.info(f"Handler {handler_name} subscribed to {event_type.value}")
        return handler_id
    
    def subscribe_all(self, handler: Callable, name: Optional[str] = None,
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
            
        self.logger.info(f"Handler {handler_name} subscribed to all events")
        return handler_id
        
    def unsubscribe(self, handler_id: str) -> bool:
        """
        Unsubscribe handler.
        
        Args:
            handler_id: Handler ID from subscription
            
        Returns:
            True if handler was found and removed
        """
        with self.handler_lock:
            # Check type-specific handlers
            for event_type, handlers in self.handlers.items():
                for i, handler in enumerate(handlers):
                    if handler.handler_id == handler_id:
                        removed = handlers.pop(i)
                        self.logger.info(f"Handler {removed.name} unsubscribed")
                        
                        with self._metrics_lock:
                            self.metrics.handlers_registered -= 1
                            
                        return True
            
            # Check global handlers
            for i, handler in enumerate(self.global_handlers):
                if handler.handler_id == handler_id:
                    removed = self.global_handlers.pop(i)
                    self.logger.info(f"Global handler {removed.name} unsubscribed")
                    
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
            self.logger.error(f"Event publish error: {e}")
            return False
            
    def emit(self, event_type: EventType, data: Dict[str, Any],
             priority: EventPriority = EventPriority.NORMAL,
             source: Optional[str] = None, **kwargs) -> bool:
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
        event = Event(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source or self.__class__.__name__,
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {}),
            ttl=kwargs.get('ttl')
        )
        
        return self.publish(event)
    
    def create_event(self, event_type: EventType, data: Dict[str, Any], 
                    **kwargs) -> Event:
        """Create event without publishing"""
        return Event(
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
    def get_event_history(self, limit: Optional[int] = None,
                         event_type: Optional[EventType] = None) -> List[Event]:
        """Get recent event history"""
        with self._history_lock:
            events = list(self.event_history)
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if limit:
                events = events[-limit:]
            
            return events
    
    def get_handler_stats(self) -> List[Dict[str, Any]]:
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
        
    def get_metrics(self) -> Dict[str, Any]:
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
    
    def clear_handlers(self, event_type: Optional[EventType] = None):
        """Clear event handlers"""
        with self.handler_lock:
            if event_type:
                self.handlers[event_type].clear()
                self.logger.debug(f"Cleared handlers for {event_type.value}")
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

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_event_manager_instance: Optional[EventManager] = None
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
            _event_manager_instance = EventManager(persist_events=persist_events)
        
        return _event_manager_instance

def reset_event_manager():
    """Reset the singleton instance (for testing)"""
    global _event_manager_instance
    with _event_manager_lock:
        if _event_manager_instance and _event_manager_instance.is_running:
            _event_manager_instance.stop()
        _event_manager_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    import json
    
    print("Testing EventManager...")
    
    # Create event manager
    em = EventManager(persist_events=False)
    
    # Test handler registration
    print("\n1. Testing handler registration:")
    
    def test_handler(event: Event):
        print(f"Handler received: {event.event_type.value} - {event.data}")
    
    handler_id = em.subscribe(EventType.SYSTEM, test_handler, name="TestHandler")
    print(f"Handler registered with ID: {handler_id}")
    
    # Test global handler
    def global_handler(event: Event):
        print(f"Global handler: {event.event_type.value}")
    
    global_id = em.subscribe_all(global_handler, name="GlobalHandler")
    
    # Start event manager
    print("\n2. Starting EventManager:")
    if em.start():
        print("✅ EventManager started successfully")
        
        # Test event publishing
        print("\n3. Testing event publishing:")
        
        # Publish test events
        em.emit(EventType.SYSTEM, {'message': 'Test system event'})
        em.emit(EventType.TRADING, {'action': 'Test trade'})
        em.emit(EventType.RISK, {'warning': 'Test risk event'}, priority=EventPriority.HIGH)
        
        # Wait for processing
        import time
        time.sleep(1)
        
        # Get metrics
        print("\n4. Event metrics:")
        metrics = em.get_metrics()
        print(json.dumps(metrics, indent=2))
        
        # Test filtering
        print("\n5. Testing event filtering:")
        
        def priority_filter(event: Event) -> bool:
            return event.priority.value >= EventPriority.HIGH.value
        
        filtered_handler_id = em.subscribe(
            EventType.RISK,
            lambda e: print(f"High priority: {e.data}"),
            filter_func=priority_filter,
            name="FilteredHandler"
        )
        
        # Emit events with different priorities
        em.emit(EventType.RISK, {'level': 'low'}, priority=EventPriority.LOW)
        em.emit(EventType.RISK, {'level': 'high'}, priority=EventPriority.HIGH)
        
        time.sleep(1)
        
        # Test handler statistics
        print("\n6. Handler statistics:")
        stats = em.get_handler_stats()
        for stat in stats:
            print(f"  {stat['name']}: {stat['execution_count']} executions")
        
        # Test event history
        print("\n7. Event history:")
        history = em.get_event_history(limit=5)
        for event in history:
            print(f"  {event.timestamp}: {event.event_type.value} - {event.data}")
        
        # Test unsubscribe
        print("\n8. Testing unsubscribe:")
        if em.unsubscribe(handler_id):
            print("✅ Handler unsubscribed successfully")
        
        # Stop event manager
        print("\n9. Stopping EventManager:")
        if em.stop():
            print("✅ EventManager stopped successfully")
    else:
        print("❌ Failed to start EventManager")
    
    print("\n✅ EventManager test completed")
