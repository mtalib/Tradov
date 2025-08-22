#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderA_Core
Module: SpyderA05_EventManager.py
Purpose: Centralized event management and message passing system
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-22 Time: 18:45:00

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
HANDLER_TIMEOUT = 30  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class EventType(Enum):
    """Event types for the trading system"""
    # System events
    SYSTEM = "system"
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
        executor: Thread pool for async handlers
        
    Example:
        >>> manager = EventManager()
        >>> manager.subscribe(EventType.TRADE, my_handler)
        >>> manager.emit(EventType.TRADE, {"symbol": "SPY", "action": "BUY"})
    """
    
    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE,
                 db_path: Optional[str] = None):
        """Initialize event manager"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Queues
        self.event_queue = queue.Queue(maxsize=queue_size)
        self.priority_queue = queue.PriorityQueue(maxsize=PRIORITY_QUEUE_SIZE)
        
        # Handler registry
        self.handlers: Dict[EventType, List[HandlerInfo]] = defaultdict(list)
        self.handler_lock = threading.RLock()
        
        # Filtering
        self.global_filter = EventFilter()
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self._shutdown_event = threading.Event()
        self._worker_thread = None
        self._priority_worker_thread = None
        
        # Persistence
        self.db_path = db_path or "events.db"
        self._init_database()
        self._persist_queue = queue.Queue()
        self._persist_thread = None
        
        # Metrics
        self.metrics = EventMetrics()
        self._metrics_lock = threading.Lock()
        
        # Event history
        self.event_history = deque(maxlen=1000)
        self._history_lock = threading.Lock()
        
        # Start workers
        self._start_workers()
        
        self.logger.info("EventManager initialized")
        
    # ==========================================================================
    # DATABASE INITIALIZATION
    # ==========================================================================
    def _init_database(self):
        """Initialize event persistence database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
    # WORKER THREADS
    # ==========================================================================
    def _start_workers(self):
        """Start background worker threads"""
        # Start event processing workers
        self._worker_thread = threading.Thread(
            target=self._event_worker,
            name="EventWorker",
            daemon=True
        )
        self._worker_thread.start()
        
        self._priority_worker_thread = threading.Thread(
            target=self._priority_worker,
            name="PriorityEventWorker",
            daemon=True
        )
        self._priority_worker_thread.start()
        
        # Start persistence worker
        self._persist_thread = threading.Thread(
            target=self._persist_worker,
            name="EventPersistWorker",
            daemon=True
        )
        self._persist_thread.start()
        
        self.logger.info("Worker threads started")
        
    def _event_worker(self):
        """Process events from main queue"""
        while not self._shutdown_event.is_set():
            try:
                event = self.event_queue.get(timeout=1)
                self._process_event(event)
                self.event_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Event worker error: {e}")
                
    def _priority_worker(self):
        """Process high-priority events"""
        while not self._shutdown_event.is_set():
            try:
                _, _, event = self.priority_queue.get(timeout=1)
                self._process_event(event)
                self.priority_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Priority worker error: {e}")
                
    def _persist_worker(self):
        """Persist events to database"""
        batch = []
        last_persist = time.time()
        
        while not self._shutdown_event.is_set():
            try:
                # Get event from persist queue
                try:
                    event = self._persist_queue.get(timeout=1)
                    batch.append(event)
                    self._persist_queue.task_done()
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
                self.logger.error(f"Persist worker error: {e}")
                
    def _persist_batch(self, events: List[Event]):
        """Persist batch of events to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for event in events:
                    # Use custom encoder for proper datetime serialization
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
            self.logger.error(f"Event batch persistence error: {e}")
            
    # ==========================================================================
    # EVENT PROCESSING
    # ==========================================================================
    def _process_event(self, event: Event):
        """Process single event"""
        try:
            # Update metrics
            with self._metrics_lock:
                self.metrics.events_processed += 1
                
            # Get handlers for this event type
            with self.handler_lock:
                handlers = self.handlers.get(event.event_type, [])
                
            # Sort handlers by priority
            handlers = sorted(handlers, key=lambda h: h.priority, reverse=True)
            
            # Execute handlers
            for handler in handlers:
                try:
                    # Apply handler filter
                    if handler.filter_func and not handler.filter_func(event):
                        continue
                        
                    # Execute based on handler type
                    start_time = time.time()
                    
                    if handler.handler_type == HandlerType.SYNC:
                        handler.func(event)
                    elif handler.handler_type == HandlerType.ASYNC:
                        asyncio.run(handler.func(event))
                    elif handler.handler_type == HandlerType.THREADED:
                        self.executor.submit(handler.func, event)
                        
                    # Update handler metrics
                    handler.execution_count += 1
                    handler.total_execution_time += time.time() - start_time
                    handler.last_execution = datetime.now()
                    
                    with self._metrics_lock:
                        self.metrics.handlers_executed += 1
                        
                except Exception as e:
                    handler.error_count += 1
                    handler.last_error = str(e)
                    self.logger.error(f"Handler {handler.name} error: {e}")
                    
            # Persist event if needed
            if event.priority.value >= EventPriority.HIGH.value:
                self.persist_event(event)
                
        except Exception as e:
            with self._metrics_lock:
                self.metrics.events_failed += 1
            self.logger.error(f"Event processing error: {e}")
            
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
        
    def unsubscribe(self, handler_id: str) -> bool:
        """
        Unsubscribe handler.
        
        Args:
            handler_id: Handler ID from subscription
            
        Returns:
            True if handler was found and removed
        """
        with self.handler_lock:
            for event_type, handlers in self.handlers.items():
                for i, handler in enumerate(handlers):
                    if handler.handler_id == handler_id:
                        removed = handlers.pop(i)
                        self.logger.info(f"Handler {removed.name} unsubscribed")
                        
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
            source: Event source
            **kwargs: Additional event attributes
            
        Returns:
            bool: True if event published successfully
        """
        event = Event(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source,
            **kwargs
        )
        
        return self.publish(event)
        
    # ==========================================================================
    # PERSISTENCE METHODS
    # ==========================================================================
    def persist_event(self, event: Event):
        """Queue event for persistence"""
        try:
            self._persist_queue.put(event)
        except Exception as e:
            self.logger.error(f"Event persistence error: {e}")
            
    # ==========================================================================
    # QUERY METHODS
    # ==========================================================================
    def get_event_history(self, event_type: Optional[EventType] = None,
                          limit: int = 100) -> List[Event]:
        """Get recent event history"""
        with self._history_lock:
            history = list(self.event_history)
            
        if event_type:
            history = [e for e in history if e.event_type == event_type]
            
        return history[-limit:]
        
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
                'queue_size': self.event_queue.qsize(),
                'priority_queue_size': self.priority_queue.qsize()
            }
            
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def shutdown(self):
        """Shutdown event manager"""
        self.logger.info("Shutting down EventManager")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for queues to empty
        self.event_queue.join()
        self.priority_queue.join()
        self._persist_queue.join()
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Wait for threads
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        if self._priority_worker_thread:
            self._priority_worker_thread.join(timeout=5)
        if self._persist_thread:
            self._persist_thread.join(timeout=5)
            
        self.logger.info("EventManager shutdown complete")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_event_manager_instance: Optional[EventManager] = None

def get_event_manager() -> EventManager:
    """Get singleton instance of EventManager"""
    global _event_manager_instance
    if _event_manager_instance is None:
        _event_manager_instance = EventManager()
    return _event_manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the event manager
    manager = EventManager()
    
    # Test handler
    def test_handler(event: Event):
        print(f"Received event: {event.event_type.value} - {event.data}")
        
    # Subscribe to events
    handler_id = manager.subscribe(EventType.TRADE, test_handler)
    
    # Emit test events
    manager.emit(EventType.TRADE, {"symbol": "SPY", "action": "BUY", "quantity": 100})
    manager.emit(EventType.SYSTEM, {"message": "System test"})
    
    # Wait for processing
    time.sleep(2)
    
    # Print metrics
    print("\nEvent Metrics:")
    for key, value in manager.get_metrics().items():
        print(f"  {key}: {value}")
        
    # Cleanup
    manager.shutdown()
    print("\n✅ EventManager test completed")