
# =============================================================================
# Event Priority Enum
# =============================================================================
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set
from threading import Lock
import queue
import traceback

class EventPriority(Enum):
    """Priority levels for event processing."""
    CRITICAL = 0  # Highest priority - system critical events
    HIGH = 1      # High priority - important events
    NORMAL = 5    # Normal priority - standard events
    LOW = 8       # Low priority - background events
    TRIVIAL = 10  # Lowest priority - informational events

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderA05_EventManager.py
Group: A (Core Trading Engine)
Purpose: Event-driven architecture implementation

Description:
This module implements the event management system that coordinates communication
between different components of the trading system. It provides a publish-subscribe
pattern for handling system events, market data updates, trading signals, and
risk management notifications.

Author: [Your Name]
Created: 2025-01-27
Version: 1.0
"""

# =============================================================================
# Standard Library Imports
# =============================================================================

# =============================================================================
# Event Type Definitions
# =============================================================================
class EventType(Enum):
    """Enumeration of all system event types."""
    
    # System Events
    SYSTEM_START = auto()
    SYSTEM_STOP = auto()
    SYSTEM_ERROR = auto()
    SYSTEM_WARNING = auto()
    SYSTEM_INFO = auto()
    
    # Market Data Events
    MARKET_DATA_RECEIVED = auto()
    MARKET_DATA_ERROR = auto()
    QUOTE_UPDATE = auto()
    TICK_DATA = auto()
    ORDERBOOK_UPDATE = auto()
    
    # Trading Events
    SIGNAL_GENERATED = auto()
    ORDER_PLACED = auto()
    ORDER_FILLED = auto()
    ORDER_CANCELLED = auto()
    ORDER_REJECTED = auto()
    TRADE_EXECUTED = auto()
    TRADE_CLOSED = auto()
    
    # Position Events
    POSITION_OPENED = auto()
    POSITION_UPDATED = auto()
    POSITION_CLOSED = auto()
    
    # Risk Management Events
    RISK_LIMIT_EXCEEDED = auto()
    RISK_WARNING = auto()
    MARGIN_CALL = auto()
    STOP_LOSS_TRIGGERED = auto()
    
    # Strategy Events
    STRATEGY_START = auto()
    STRATEGY_STOP = auto()
    STRATEGY_UPDATE = auto()
    
    # Account Events
    ACCOUNT_UPDATE = auto()
    BALANCE_UPDATE = auto()
    BUYING_POWER_UPDATE = auto()

# =============================================================================
# Event Data Structure
# =============================================================================
@dataclass
class Event:
    """
    Represents a system event with metadata.
    
    Attributes:
        type: The type of event
        data: Event payload data
        timestamp: When the event occurred
        source: Component that generated the event
        priority: Event priority (0=highest)
        id: Unique event identifier
    """
    type: EventType
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "Unknown"
    priority: int = 5
    id: Optional[str] = None
    
    def __post_init__(self):
        """Generate unique ID if not provided."""
        if self.id is None:
            self.id = f"{self.type.name}_{self.timestamp.timestamp()}"

# =============================================================================
# Event Manager Implementation
# =============================================================================
class EventManager:
    """
    Central event management system for the trading application.
    
    Handles event publishing, subscription, and distribution using
    the publish-subscribe pattern. Thread-safe for concurrent access.
    
    Attributes:
        handlers: Dictionary mapping event types to handler functions
        event_queue: Priority queue for event processing
        logger: Logger instance
        is_running: Flag indicating if event processing is active
        event_history: Recent event history for debugging
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the EventManager.
        
        Args:
            max_history: Maximum number of events to keep in history
        """
        self.handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self.event_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        self.event_history: List[Event] = []
        self.max_history = max_history
        self._lock = Lock()
        self._async_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
        self._processing_thread = None
        
        self.logger.info("EventManager initialized")
    
    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        Register a handler function for a specific event type.
        
        Args:
            event_type: The type of event to handle
            handler: Callback function to invoke when event occurs
        """
        with self._lock:
            if handler not in self.handlers[event_type]:
                self.handlers[event_type].append(handler)
                self.logger.debug(f"Registered handler {handler.__name__} for {event_type.name}")
    
    def register_async_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        Register an async handler function for a specific event type.
        
        Args:
            event_type: The type of event to handle
            handler: Async callback function to invoke when event occurs
        """
        with self._lock:
            if handler not in self._async_handlers[event_type]:
                self._async_handlers[event_type].append(handler)
                self.logger.debug(f"Registered async handler {handler.__name__} for {event_type.name}")
    
    def unregister_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        Unregister a handler function for a specific event type.
        
        Args:
            event_type: The type of event
            handler: Handler function to remove
        """
        with self._lock:
            if handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
                self.logger.debug(f"Unregistered handler {handler.__name__} for {event_type.name}")
            
            if handler in self._async_handlers[event_type]:
                self._async_handlers[event_type].remove(handler)
                self.logger.debug(f"Unregistered async handler {handler.__name__} for {event_type.name}")
    
    def publish(self, event: Event) -> None:
        """
        Publish an event to the system.
        
        Args:
            event: Event to publish
        """
        # Add to history
        with self._lock:
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history.pop(0)
        
        # Add to queue for processing
        self.event_queue.put((event.priority, event.timestamp, event))
        self.logger.debug(f"Published event: {event.type.name} from {event.source}")
    
    def publish_event(self, event_type: EventType, data: Any, 
                     source: str = "System", priority: int = 5) -> None:
        """
        Convenience method to publish an event.
        
        Args:
            event_type: Type of event to publish
            data: Event data payload
            source: Source component name
            priority: Event priority (0=highest)
        """
        event = Event(
            type=event_type,
            data=data,
            source=source,
            priority=priority
        )
        self.publish(event)
    
    def _process_event(self, event: Event) -> None:
        """
        Process a single event by calling all registered handlers.
        
        Args:
            event: Event to process
        """
        # Process synchronous handlers
        handlers = self.handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(
                    f"Error in handler {handler.__name__} for event {event.type.name}: {str(e)}"
                )
                self.logger.error(traceback.format_exc())
        
        # Process async handlers
        async_handlers = self._async_handlers.get(event.type, [])
        if async_handlers:
            asyncio.create_task(self._process_async_handlers(event, async_handlers))
    
    async def _process_async_handlers(self, event: Event, handlers: List[Callable]) -> None:
        """
        Process async handlers for an event.
        
        Args:
            event: Event to process
            handlers: List of async handlers
        """
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                self.logger.error(
                    f"Error in async handler {handler.__name__} for event {event.type.name}: {str(e)}"
                )
                self.logger.error(traceback.format_exc())
    
    def start(self) -> None:
        """Start the event processing system."""
        self.is_running = True
        self.logger.info("EventManager started")
    
    def stop(self) -> None:
        """Stop the event processing system."""
        self.is_running = False
        self.logger.info("EventManager stopped")
    
    def process_events(self, max_events: Optional[int] = None) -> int:
        """
        Process pending events in the queue.
        
        Args:
            max_events: Maximum number of events to process (None=all)
            
        Returns:
            Number of events processed
        """
        if not self.is_running:
            return 0
        
        processed = 0
        while not self.event_queue.empty() and (max_events is None or processed < max_events):
            try:
                _, _, event = self.event_queue.get(timeout=0.1)
                self._process_event(event)
                processed += 1
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing event: {str(e)}")
        
        return processed
    
    def get_handlers_count(self, event_type: Optional[EventType] = None) -> int:
        """
        Get the number of registered handlers.
        
        Args:
            event_type: Specific event type to check (None=all)
            
        Returns:
            Number of registered handlers
        """
        if event_type:
            return len(self.handlers.get(event_type, []))
        else:
            return sum(len(handlers) for handlers in self.handlers.values())
    
    def get_event_history(self, event_type: Optional[EventType] = None, 
                         limit: int = 100) -> List[Event]:
        """
        Get recent event history.
        
        Args:
            event_type: Filter by event type (None=all)
            limit: Maximum number of events to return
            
        Returns:
            List of recent events
        """
        with self._lock:
            if event_type:
                filtered = [e for e in self.event_history if e.type == event_type]
            else:
                filtered = self.event_history.copy()
        
        return filtered[-limit:]
    
    def clear_handlers(self, event_type: Optional[EventType] = None) -> None:
        """
        Clear registered handlers.
        
        Args:
            event_type: Clear handlers for specific type (None=all)
        """
        with self._lock:
            if event_type:
                self.handlers[event_type].clear()
                self._async_handlers[event_type].clear()
                self.logger.info(f"Cleared handlers for {event_type.name}")
            else:
                self.handlers.clear()
                self._async_handlers.clear()
                self.logger.info("Cleared all handlers")

# =============================================================================
# Singleton Instance
# =============================================================================
_event_manager_instance = None

def get_event_manager() -> EventManager:
    """
    Get the singleton EventManager instance.
    
    Returns:
        The global EventManager instance
    """
    global _event_manager_instance
    if _event_manager_instance is None:
        _event_manager_instance = EventManager()
    return _event_manager_instance

# =============================================================================
# Example Usage and Testing
# =============================================================================
if __name__ == "__main__":
    # Example usage
    em = get_event_manager()
    
    # Define a sample handler
    def handle_trade(event: Event):
        print(f"Trade executed: {event.data}")
    
    # Register handler
    em.register_handler(EventType.TRADE_EXECUTED, handle_trade)
    
    # Start event manager
    em.start()
    
    # Publish an event
    em.publish_event(
        EventType.TRADE_EXECUTED,
        {"symbol": "SPY", "quantity": 100, "price": 450.50},
        source="TradingEngine"
    )
    
    # Process events
    em.process_events()
    
    # Stop event manager
    em.stop()
