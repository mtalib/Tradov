#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderA05_EventManager.py
Group: A (Core Trading Engine)
Purpose: Event management and pub/sub system

Description:
    This module provides a comprehensive event management system for the Spyder
    trading platform. It implements a thread-safe publish/subscribe pattern with
    event filtering, priority handling, asynchronous processing, and persistence.
    The system supports event replay, metrics collection, and dead letter queue
    for failed events.

Spyder Version: 2.0
Author: Mohamed Talib
Created: 2025-01-27
Last Updated: 2025-07-06 - Production Ready
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
import queue
import time
import json
import pickle
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, Callable, List, Optional, Set, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from collections import defaultdict, deque
import logging
import traceback
import weakref
import inspect
import uuid
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
EVENT_QUEUE_SIZE = 10000
PRIORITY_QUEUE_SIZE = 1000
EVENT_HISTORY_SIZE = 1000
WORKER_THREAD_COUNT = 4
EVENT_PERSISTENCE_INTERVAL = 60  # seconds
METRIC_COLLECTION_INTERVAL = 30  # seconds
MAX_HANDLER_EXECUTION_TIME = 5  # seconds
DEAD_LETTER_RETENTION_DAYS = 7

# Database schema
EVENT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    priority INTEGER NOT NULL,
    source TEXT,
    timestamp TIMESTAMP NOT NULL,
    data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_type ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON event_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_source ON event_log(source);

CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    handler_name TEXT NOT NULL,
    error_message TEXT NOT NULL,
    error_count INTEGER DEFAULT 1,
    last_attempt TIMESTAMP NOT NULL,
    event_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dlq_event_type ON dead_letter_queue(event_type);
CREATE INDEX IF NOT EXISTS idx_dlq_last_attempt ON dead_letter_queue(last_attempt);
"""

# ==============================================================================
# ENUMS
# ==============================================================================
class EventType(Enum):
    """Complete event types for Spyder system"""
    # System events
    SYSTEM = "system"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ALERT = "system_alert"
    
    # Trading events
    TRADING = "trading"
    TRADE_EXECUTED = "trade_executed"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    
    # Position events
    POSITION_UPDATE = "position_update"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_MODIFIED = "position_modified"
    
    # Market data events
    MARKET_DATA = "market_data"
    MARKET_DATA_UPDATE = "market_data_update"
    MARKET_DATA_RECEIVED = "market_data_received"
    PRICE_UPDATE = "price_update"
    QUOTE_UPDATE = "quote_update"
    
    # Risk events
    RISK = "risk"
    RISK_VIOLATION = "risk_violation"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    RISK_WARNING = "risk_warning"
    MARGIN_CALL = "margin_call"
    
    # Connection events
    CONNECTION_STATUS = "connection_status"
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
        """Convert event to dictionary"""
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
    total_processing_time: float = 0.0
    queue_size: int = 0
    dead_letter_count: int = 0
    last_reset: datetime = field(default_factory=datetime.now)

# ==============================================================================
# EVENT FILTER
# ==============================================================================
class EventFilter:
    """Advanced event filtering"""
    
    def __init__(self):
        self.filters: List[Callable[[Event], bool]] = []
        
    def add_filter(self, filter_func: Callable[[Event], bool]):
        """Add a filter function"""
        self.filters.append(filter_func)
        
    def remove_filter(self, filter_func: Callable[[Event], bool]):
        """Remove a filter function"""
        if filter_func in self.filters:
            self.filters.remove(filter_func)
            
    def apply(self, event: Event) -> bool:
        """Apply all filters to event"""
        return all(f(event) for f in self.filters)
    
    @staticmethod
    def create_type_filter(event_types: List[EventType]) -> Callable[[Event], bool]:
        """Create filter for specific event types"""
        def filter_func(event: Event) -> bool:
            return event.event_type in event_types
        return filter_func
    
    @staticmethod
    def create_source_filter(sources: List[str]) -> Callable[[Event], bool]:
        """Create filter for specific sources"""
        def filter_func(event: Event) -> bool:
            return event.source in sources
        return filter_func
    
    @staticmethod
    def create_priority_filter(min_priority: EventPriority) -> Callable[[Event], bool]:
        """Create filter for minimum priority"""
        def filter_func(event: Event) -> bool:
            return event.priority.value >= min_priority.value
        return filter_func

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class EventManager:
    """
    Comprehensive event management system for Spyder.
    
    This class provides:
    - Thread-safe publish/subscribe pattern
    - Event filtering and routing
    - Priority-based processing
    - Asynchronous and synchronous handlers
    - Event persistence and replay
    - Dead letter queue for failed events
    - Performance metrics and monitoring
    - Weak references for handler cleanup
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        handlers: Dictionary of event handlers by type
        global_handlers: Handlers that receive all events
        event_queue: Main event processing queue
        priority_queue: High-priority event queue
        metrics: Performance metrics
        is_running: System running state
    """
    
    def __init__(self, persist_events: bool = True, 
                 db_path: Optional[Path] = None):
        """
        Initialize event manager.
        
        Args:
            persist_events: Enable event persistence
            db_path: Path to event database
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Handler storage
        self.handlers: Dict[EventType, List[HandlerInfo]] = defaultdict(list)
        self.global_handlers: List[HandlerInfo] = []
        self._handler_lock = threading.RLock()
        
        # Event queues
        self.event_queue: queue.Queue = queue.Queue(maxsize=EVENT_QUEUE_SIZE)
        self.priority_queue: queue.PriorityQueue = queue.PriorityQueue(maxsize=PRIORITY_QUEUE_SIZE)
        
        # Event history
        self.event_history: deque = deque(maxlen=EVENT_HISTORY_SIZE)
        self._history_lock = threading.Lock()
        
        # Worker pool
        self.worker_pool = ThreadPoolExecutor(max_workers=WORKER_THREAD_COUNT)
        self.worker_threads: List[threading.Thread] = []
        
        # System state
        self.is_running = False
        self._shutdown_event = threading.Event()
        
        # Metrics
        self.metrics = EventMetrics()
        self._metrics_lock = threading.Lock()
        
        # Event persistence
        self.persist_events = persist_events
        self.db_path = db_path or (Path.home() / ".spyder" / "events.db")
        if self.persist_events:
            self._init_database()
        
        # Background threads
        self._persistence_thread = None
        self._metrics_thread = None
        
        # Event filters
        self.global_filter = EventFilter()
        
        # Dead letter queue
        self.dead_letter_handlers: Dict[str, Tuple[HandlerInfo, Event, str]] = {}
        
        self.logger.info("EventManager initialized")

    def _init_database(self):
        """Initialize event persistence database"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(EVENT_LOG_SCHEMA)
            
            self.logger.info("Event database initialized")
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            self.persist_events = False

    # ==========================================================================
    # HANDLER REGISTRATION
    # ==========================================================================
    def subscribe(self, event_type: Union[EventType, List[EventType]], 
                  handler: Callable[[Event], None],
                  name: Optional[str] = None,
                  handler_type: HandlerType = HandlerType.SYNC,
                  filter_func: Optional[Callable[[Event], bool]] = None,
                  priority: int = 0,
                  weak_ref: bool = False) -> str:
        """
        Subscribe to event type(s) with enhanced options.
        
        Args:
            event_type: Event type or list of event types
            handler: Handler function
            name: Handler name (for identification)
            handler_type: Type of handler execution
            filter_func: Additional filter function
            priority: Handler priority (higher executes first)
            weak_ref: Use weak reference for handler
            
        Returns:
            Handler ID for unsubscribing
        """
        # Normalize event types
        if isinstance(event_type, EventType):
            event_types = {event_type}
        else:
            event_types = set(event_type)
        
        # Create handler info
        handler_id = str(uuid.uuid4())
        handler_info = HandlerInfo(
            handler_id=handler_id,
            name=name or f"{handler.__name__}_{handler_id[:8]}",
            func=weakref.ref(handler) if weak_ref else handler,
            event_types=event_types,
            handler_type=handler_type,
            filter_func=filter_func,
            priority=priority,
            weak_ref=weak_ref
        )
        
        # Register handler
        with self._handler_lock:
            for evt_type in event_types:
                # Insert in priority order
                handlers = self.handlers[evt_type]
                insert_pos = 0
                for i, h in enumerate(handlers):
                    if h.priority < priority:
                        insert_pos = i
                        break
                    insert_pos = i + 1
                handlers.insert(insert_pos, handler_info)
            
            # Update metrics
            self.metrics.handlers_registered += 1
        
        self.logger.debug(f"Handler {handler_info.name} subscribed to {[t.value for t in event_types]}")
        
        return handler_id

    def subscribe_all(self, handler: Callable[[Event], None], **kwargs) -> str:
        """
        Subscribe to all events.
        
        Args:
            handler: Handler function
            **kwargs: Additional handler options
            
        Returns:
            Handler ID
        """
        handler_id = str(uuid.uuid4())
        handler_info = HandlerInfo(
            handler_id=handler_id,
            name=kwargs.get('name', f"{handler.__name__}_{handler_id[:8]}"),
            func=weakref.ref(handler) if kwargs.get('weak_ref', False) else handler,
            event_types=set(),  # Empty means all events
            handler_type=kwargs.get('handler_type', HandlerType.SYNC),
            filter_func=kwargs.get('filter_func'),
            priority=kwargs.get('priority', 0),
            weak_ref=kwargs.get('weak_ref', False)
        )
        
        with self._handler_lock:
            # Insert in priority order
            insert_pos = 0
            for i, h in enumerate(self.global_handlers):
                if h.priority < handler_info.priority:
                    insert_pos = i
                    break
                insert_pos = i + 1
            self.global_handlers.insert(insert_pos, handler_info)
            
            self.metrics.handlers_registered += 1
        
        self.logger.debug(f"Global handler {handler_info.name} registered")
        
        return handler_id

    def unsubscribe(self, handler_id: str) -> bool:
        """
        Unsubscribe handler by ID.
        
        Args:
            handler_id: Handler ID from subscribe
            
        Returns:
            bool: True if unsubscribed successfully
        """
        with self._handler_lock:
            # Check event-specific handlers
            for event_type, handlers in self.handlers.items():
                for i, handler_info in enumerate(handlers):
                    if handler_info.handler_id == handler_id:
                        handlers.pop(i)
                        self.metrics.handlers_registered -= 1
                        self.logger.debug(f"Handler {handler_id} unsubscribed")
                        return True
            
            # Check global handlers
            for i, handler_info in enumerate(self.global_handlers):
                if handler_info.handler_id == handler_id:
                    self.global_handlers.pop(i)
                    self.metrics.handlers_registered -= 1
                    self.logger.debug(f"Global handler {handler_id} unsubscribed")
                    return True
        
        return False

    def register_handler(self, event_type: EventType, 
                        handler: Callable[[Event], None], **kwargs) -> str:
        """Register handler (alias for subscribe)"""
        return self.subscribe(event_type, handler, **kwargs)

    # ==========================================================================
    # EVENT PUBLISHING
    # ==========================================================================
    def publish(self, event: Event) -> bool:
        """
        Publish event to all subscribers.
        
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
            
            # Add to history
            with self._history_lock:
                self.event_history.append(event)
            
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
            source: Event source identifier
            **kwargs: Additional event attributes
            
        Returns:
            bool: True if published successfully
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
                
                # Process regular queue
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
        start_time = time.time()
        
        try:
            # Get handlers for this event
            handlers_to_call = self._get_handlers_for_event(event)
            
            # Execute handlers
            for handler_info in handlers_to_call:
                self._execute_handler(handler_info, event)
            
            # Update metrics
            with self._metrics_lock:
                self.metrics.events_processed += 1
                self.metrics.total_processing_time += time.time() - start_time
            
            # Persist event if enabled
            if self.persist_events:
                self._persist_event(event)
                
        except Exception as e:
            self.logger.error(f"Error processing event {event.event_id}: {e}")
            with self._metrics_lock:
                self.metrics.events_failed += 1

    def _get_handlers_for_event(self, event: Event) -> List[HandlerInfo]:
        """Get all handlers that should process this event"""
        handlers = []
        
        with self._handler_lock:
            # Add specific handlers
            if event.event_type in self.handlers:
                handlers.extend(self.handlers[event.event_type])
            
            # Add global handlers
            handlers.extend(self.global_handlers)
        
        # Filter handlers
        filtered_handlers = []
        for handler_info in handlers:
            # Check if handler is still valid (for weak refs)
            if handler_info.weak_ref:
                handler_func = handler_info.func()
                if handler_func is None:
                    continue
            
            # Apply handler filter
            if handler_info.filter_func and not handler_info.filter_func(event):
                continue
            
            filtered_handlers.append(handler_info)
        
        return filtered_handlers

    def _execute_handler(self, handler_info: HandlerInfo, event: Event):
        """Execute a single handler"""
        start_time = time.time()
        
        try:
            # Get actual handler function
            if handler_info.weak_ref:
                handler_func = handler_info.func()
                if handler_func is None:
                    return
            else:
                handler_func = handler_info.func
            
            # Execute based on handler type
            if handler_info.handler_type == HandlerType.ASYNC:
                # Schedule async execution
                asyncio.create_task(self._execute_async_handler(handler_func, event))
            elif handler_info.handler_type == HandlerType.THREADED:
                # Execute in thread pool
                self.worker_pool.submit(handler_func, event)
            else:
                # Execute synchronously
                handler_func(event)
            
            # Update handler metrics
            handler_info.execution_count += 1
            handler_info.total_execution_time += time.time() - start_time
            handler_info.last_execution = datetime.now()
            
            with self._metrics_lock:
                self.metrics.handlers_executed += 1
            
            # Check execution time
            execution_time = time.time() - start_time
            if execution_time > MAX_HANDLER_EXECUTION_TIME:
                self.logger.warning(
                    f"Handler {handler_info.name} took {execution_time:.2f}s "
                    f"(max: {MAX_HANDLER_EXECUTION_TIME}s)"
                )
                
        except Exception as e:
            handler_info.error_count += 1
            handler_info.last_error = str(e)
            
            self.logger.error(
                f"Handler {handler_info.name} error processing "
                f"{event.event_type.value}: {e}"
            )
            
            # Add to dead letter queue
            self._add_to_dead_letter_queue(handler_info, event, str(e))

    async def _execute_async_handler(self, handler: Callable, event: Event):
        """Execute async handler"""
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                # Run sync handler in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, handler, event)
        except Exception as e:
            self.logger.error(f"Async handler error: {e}")

    # ==========================================================================
    # EVENT PERSISTENCE
    # ==========================================================================
    def _persist_event(self, event: Event):
        """Persist event to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO event_log 
                    (event_id, event_type, priority, source, timestamp, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type.value,
                    event.priority.value,
                    event.source,
                    event.timestamp,
                    json.dumps(event.to_dict())
                ))
        except Exception as e:
            self.logger.error(f"Event persistence error: {e}")

    def _persistence_loop(self):
        """Background event persistence"""
        while not self._shutdown_event.is_set():
            try:
                # Clean old events
                self._clean_old_events()
                
                # Clean dead letter queue
                self._clean_dead_letter_queue()
                
                # Wait
                self._shutdown_event.wait(EVENT_PERSISTENCE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Persistence loop error: {e}")

    def _clean_old_events(self, days_to_keep: int = 30):
        """Clean old events from database"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute("""
                    DELETE FROM event_log
                    WHERE timestamp < ?
                """, (cutoff_date,))
                
                if result.rowcount > 0:
                    self.logger.info(f"Cleaned {result.rowcount} old events")
                    
        except Exception as e:
            self.logger.error(f"Event cleanup error: {e}")

    # ==========================================================================
    # DEAD LETTER QUEUE
    # ==========================================================================
    def _add_to_dead_letter_queue(self, handler_info: HandlerInfo, 
                                 event: Event, error_message: str):
        """Add failed event to dead letter queue"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO dead_letter_queue 
                    (event_id, event_type, handler_name, error_message, 
                     last_attempt, event_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.event_type.value,
                    handler_info.name,
                    error_message,
                    datetime.now(),
                    json.dumps(event.to_dict())
                ))
            
            with self._metrics_lock:
                self.metrics.dead_letter_count += 1
                
        except Exception as e:
            self.logger.error(f"Dead letter queue error: {e}")

    def _clean_dead_letter_queue(self):
        """Clean old entries from dead letter queue"""
        try:
            cutoff_date = datetime.now() - timedelta(days=DEAD_LETTER_RETENTION_DAYS)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM dead_letter_queue
                    WHERE created_at < ?
                """, (cutoff_date,))
                
        except Exception as e:
            self.logger.error(f"Dead letter cleanup error: {e}")

    def get_dead_letter_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get events from dead letter queue"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT event_id, event_type, handler_name, error_message,
                           error_count, last_attempt, event_data
                    FROM dead_letter_queue
                    ORDER BY last_attempt DESC
                    LIMIT ?
                """, (limit,))
                
                events = []
                for row in cursor:
                    events.append({
                        'event_id': row[0],
                        'event_type': row[1],
                        'handler_name': row[2],
                        'error_message': row[3],
                        'error_count': row[4],
                        'last_attempt': row[5],
                        'event_data': json.loads(row[6])
                    })
                
                return events
                
        except Exception as e:
            self.logger.error(f"Failed to get dead letter events: {e}")
            return []

    # ==========================================================================
    # EVENT REPLAY
    # ==========================================================================
    def replay_events(self, start_time: datetime, end_time: datetime,
                     event_types: Optional[List[EventType]] = None,
                     source_filter: Optional[str] = None) -> int:
        """
        Replay historical events.
        
        Args:
            start_time: Start of replay period
            end_time: End of replay period
            event_types: Filter by event types
            source_filter: Filter by source
            
        Returns:
            Number of events replayed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT data FROM event_log
                    WHERE timestamp >= ? AND timestamp <= ?
                """
                params = [start_time, end_time]
                
                if event_types:
                    placeholders = ','.join('?' * len(event_types))
                    query += f" AND event_type IN ({placeholders})"
                    params.extend([et.value for et in event_types])
                
                if source_filter:
                    query += " AND source = ?"
                    params.append(source_filter)
                
                query += " ORDER BY timestamp"
                
                cursor = conn.execute(query, params)
                
                count = 0
                for row in cursor:
                    event_data = json.loads(row[0])
                    event = Event.from_dict(event_data)
                    
                    # Re-publish event
                    self.publish(event)
                    count += 1
                
                self.logger.info(f"Replayed {count} events")
                return count
                
        except Exception as e:
            self.logger.error(f"Event replay error: {e}")
            return 0

    # ==========================================================================
    # METRICS AND MONITORING
    # ==========================================================================
    def _metrics_loop(self):
        """Background metrics collection"""
        while not self._shutdown_event.is_set():
            try:
                # Log current metrics
                metrics = self.get_metrics()
                self.logger.debug(f"Event metrics: {metrics}")
                
                # Emit metrics event
                self.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'event_manager_metrics',
                        'metrics': metrics
                    },
                    priority=EventPriority.LOW
                )
                
                # Wait
                self._shutdown_event.wait(METRIC_COLLECTION_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Metrics loop error: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current event system metrics"""
        with self._metrics_lock:
            metrics_dict = asdict(self.metrics)
            
            # Add queue sizes
            metrics_dict['event_queue_size'] = self.event_queue.qsize()
            metrics_dict['priority_queue_size'] = self.priority_queue.qsize()
            
            # Calculate rates
            uptime = (datetime.now() - self.metrics.last_reset).total_seconds()
            if uptime > 0:
                metrics_dict['events_per_second'] = self.metrics.events_processed / uptime
                metrics_dict['avg_processing_time_ms'] = (
                    (self.metrics.total_processing_time / self.metrics.events_processed * 1000)
                    if self.metrics.events_processed > 0 else 0
                )
            
            return metrics_dict

    def reset_metrics(self):
        """Reset performance metrics"""
        with self._metrics_lock:
            self.metrics = EventMetrics()

    def get_handler_stats(self) -> List[Dict[str, Any]]:
        """Get handler execution statistics"""
        stats = []
        
        with self._handler_lock:
            all_handlers = []
            
            # Collect all handlers
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

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    def start(self) -> bool:
        """Start the event manager"""
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
                EventType.SYSTEM_STOP,
                {
                    'component': 'EventManager',
                    'timestamp': datetime.now()
                },
                priority=EventPriority.HIGH
            )
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Wait for worker threads
            for thread in self.worker_threads:
                thread.join(timeout=timeout)
            
            # Stop other threads
            if self._persistence_thread and self._persistence_thread.is_alive():
                self._persistence_thread.join(timeout=timeout)
            
            if self._metrics_thread and self._metrics_thread.is_alive():
                self._metrics_thread.join(timeout=timeout)
            
            # Shutdown worker pool
            self.worker_pool.shutdown(wait=True)
            
            # Clear queues
            while not self.event_queue.empty():
                try:
                    self.event_queue.get_nowait()
                except queue.Empty:
                    break
            
            while not self.priority_queue.empty():
                try:
                    self.priority_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.is_running = False
            self.logger.info("EventManager stopped successfully")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop EventManager: {e}")
            return False

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def get_handler_count(self, event_type: Optional[EventType] = None) -> int:
        """Get number of registered handlers"""
        with self._handler_lock:
            if event_type:
                return len(self.handlers.get(event_type, []))
            else:
                total = sum(len(handlers) for handlers in self.handlers.values())
                total += len(self.global_handlers)
                return total

    def clear_handlers(self, event_type: Optional[EventType] = None):
        """Clear handlers"""
        with self._handler_lock:
            if event_type:
                self.handlers[event_type].clear()
                self.logger.debug(f"Cleared handlers for {event_type.value}")
            else:
                self.handlers.clear()
                self.global_handlers.clear()
                self.metrics.handlers_registered = 0
                self.logger.debug("Cleared all event handlers")

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