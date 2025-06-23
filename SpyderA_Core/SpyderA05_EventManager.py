#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Event Manager (Complete EventType Implementation)
"""

from enum import Enum
from typing import Any, Dict, Callable, List
from dataclasses import dataclass
from datetime import datetime
import logging
import threading
from collections import defaultdict

class EventType(Enum):
    """Complete event types for Spyder system."""
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    
    # Trading events
    TRADE_EXECUTED = "trade_executed"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    
    # Position events
    POSITION_UPDATE = "position_update"
    POSITION_UPDATED = "position_updated"
    
    # Market data events
    MARKET_DATA_UPDATE = "market_data_update"
    MARKET_DATA_RECEIVED = "market_data_received"
    
    # Risk events
    RISK_VIOLATION = "risk_violation"
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    
    # Connection events
    CONNECTION_STATUS = "connection_status"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_LOST = "connection_lost"
    
    # Error events
    ERROR_OCCURRED = "error_occurred"
    CRITICAL_ERROR = "critical_error"
    
    # Strategy events
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"
    
    # Account events
    ACCOUNT_UPDATE = "account_update"
    
    # General events
    NOTIFICATION = "notification"
    ALERT = "alert"

class EventPriority(Enum):
    """Event priorities."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Event:
    """Event data structure."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None
    priority: EventPriority = EventPriority.NORMAL
    source: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EventManager:
    """
    Complete event manager for Spyder system.
    
    Provides event-driven architecture with publish/subscribe pattern,
    event filtering, and thread-safe operation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handlers = defaultdict(list)  # event_type -> list of handlers
        self.global_handlers = []  # handlers that receive all events
        self.event_queue = []
        self.is_running = False
        self.lock = threading.Lock()
        
        self.logger.info("EventManager initialized")
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """
        Subscribe to specific event type.
        
        Args:
            event_type: Type of event to subscribe to
            handler: Function to call when event occurs
        """
        with self.lock:
            self.handlers[event_type].append(handler)
            self.logger.debug(f"Handler subscribed to {event_type.value}")
    
    def register_handler(self, event_type: EventType, handler: Callable[[Event], None]):
        """
        Register handler for specific event type (alias for subscribe).
        
        Args:
            event_type: Type of event to handle
            handler: Function to call when event occurs
        """
        self.subscribe(event_type, handler)
    
    def subscribe_all(self, handler: Callable[[Event], None]):
        """
        Subscribe to all events.
        
        Args:
            handler: Function to call for any event
        """
        with self.lock:
            self.global_handlers.append(handler)
            self.logger.debug("Global event handler registered")
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """
        Unsubscribe from event type.
        
        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler function to remove
        """
        with self.lock:
            if handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)
                self.logger.debug(f"Handler unsubscribed from {event_type.value}")
    
    def publish(self, event: Event):
        """
        Publish event to all subscribers.
        
        Args:
            event: Event to publish
        """
        self.logger.debug(f"Publishing event: {event.event_type.value}")
        
        # Get handlers for this event type
        handlers_to_call = []
        
        with self.lock:
            # Add specific handlers
            handlers_to_call.extend(self.handlers.get(event.event_type, []))
            # Add global handlers
            handlers_to_call.extend(self.global_handlers)
        
        # Call handlers (outside lock to prevent deadlock)
        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Event handler error: {e}")
    
    def emit(self, event_type: EventType, data: Dict[str, Any], 
             priority: EventPriority = EventPriority.NORMAL, source: str = None):
        """
        Create and publish event.
        
        Args:
            event_type: Type of event
            data: Event data
            priority: Event priority
            source: Event source identifier
        """
        event = Event(
            event_type=event_type,
            data=data,
            priority=priority,
            source=source
        )
        self.publish(event)
    
    def get_handler_count(self, event_type: EventType = None) -> int:
        """
        Get number of handlers registered.
        
        Args:
            event_type: Specific event type, or None for total
            
        Returns:
            Number of handlers
        """
        with self.lock:
            if event_type:
                return len(self.handlers.get(event_type, []))
            else:
                total = sum(len(handlers) for handlers in self.handlers.values())
                total += len(self.global_handlers)
                return total
    
    def clear_handlers(self, event_type: EventType = None):
        """
        Clear handlers.
        
        Args:
            event_type: Specific event type to clear, or None for all
        """
        with self.lock:
            if event_type:
                self.handlers[event_type].clear()
                self.logger.debug(f"Cleared handlers for {event_type.value}")
            else:
                self.handlers.clear()
                self.global_handlers.clear()
                self.logger.debug("Cleared all event handlers")
    
    def start(self):
        """Start the event manager."""
        self.is_running = True
        self.logger.info("EventManager started")
    
    def stop(self):
        """Stop the event manager."""
        self.is_running = False
        self.logger.info("EventManager stopped")

# Factory function
def get_event_manager() -> EventManager:
    """Get EventManager instance."""
    return EventManager()

__all__ = [
    'EventManager', 
    'Event', 
    'EventType', 
    'EventPriority', 
    'get_event_manager'
]
