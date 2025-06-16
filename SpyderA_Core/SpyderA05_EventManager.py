#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderA05_EventManager.py
Group: A (Core Trading Engine)
Purpose: Event management and pub/sub system

Description:
    This module provides a robust event management system implementing the
    publisher-subscriber pattern for the Spyder trading system. It handles
    event creation, distribution, subscription management, and maintains event
    history for audit purposes. The system supports priority-based event
    handling and thread-safe operations for concurrent event processing.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import uuid
import queue
import threading
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# None required for this module

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_EVENT_HISTORY = 1000  # Maximum events to keep in history
DEFAULT_QUEUE_SIZE = 10000  # Default event queue size
WORKER_THREAD_TIMEOUT = 1.0  # Worker thread timeout in seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class EventType(Enum):
    """Event types for the trading system"""
    # System events
    SYSTEM = "system"
    ERROR = "error"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    CRITICAL_ERROR = "CRITICAL_ERROR"
    
    # Connection events
    CONNECTION = "CONNECTION"
    CONNECTION_LOST = "CONNECTION_LOST"
    CONNECTION_RESTORED = "CONNECTION_RESTORED"
    
    # Market events
    MARKET_DATA = "MARKET_DATA"
    MARKET_OPEN = "MARKET_OPEN"
    MARKET_CLOSE = "MARKET_CLOSE"
    MARKET_HOURS_CHANGED = "MARKET_HOURS_CHANGED"
    
    # Trading events
    TRADING = "trading"
    TRADE = "TRADE"
    TRADE_EXECUTED = "TRADE_EXECUTED"
    TRADE_CANCELLED = "TRADE_CANCELLED"
    
    # Order events
    ORDER = "order"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_UPDATED = "ORDER_UPDATED"
    
    # Position events
    POSITION = "position"
    POSITION_UPDATED = "POSITION_UPDATED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    
    # Portfolio events
    PORTFOLIO = "PORTFOLIO"
    PORTFOLIO_UPDATED = "PORTFOLIO_UPDATED"
    
    # Account events
    ACCOUNT = "ACCOUNT"
    ACCOUNT_UPDATE = "ACCOUNT_UPDATE"
    BALANCE_UPDATE = "BALANCE_UPDATE"
    
    # Risk events
    RISK = "risk"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    RISK_WARNING = "RISK_WARNING"
    
    # Data events
    DATA = "data"
    DATA_RECEIVED = "DATA_RECEIVED"
    DATA_ERROR = "DATA_ERROR"
    
    # Strategy events
    STRATEGY = "strategy"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    STRATEGY_ERROR = "STRATEGY_ERROR"
    
    # GUI events
    GUI = "GUI"
    GUI_UPDATE = "GUI_UPDATE"
    GUI_ERROR = "GUI_ERROR"
    
    # Execution events
    EXECUTION = "EXECUTION"
    EXECUTION_REPORT = "EXECUTION_REPORT"
    
    # Price events
    PRICE = "PRICE"
    PRICE_UPDATE = "PRICE_UPDATE"
    
    # Volume events
    VOLUME = "VOLUME"
    VOLUME_UPDATE = "VOLUME_UPDATE"
    
    # Notification events
    NOTIFICATION = "notification"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()
    URGENT = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Event:
    """Event data structure."""
    id: str
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime
    source: str
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None


@dataclass
class EventSubscription:
    """Event subscription details."""
    subscriber_id: str
    event_types: List[EventType]
    callback: Callable[[Event], None]
    priority_filter: Optional[EventPriority] = None
    active: bool = True

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class EventManager:
    """
    Event management system with safe subscription handling.
    
    This class provides centralized event management for the trading system,
    implementing a thread-safe publisher-subscriber pattern with priority
    handling and event history tracking.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        subscribers: Dictionary of active subscriptions
        event_queue: Priority queue for event processing
        event_history: Historical event storage
        
    Example:
        >>> manager = EventManager()
        >>> manager.start()
        >>> manager.subscribe(EventType.TRADE_EXECUTED, callback_func)
    """
    
    def __init__(self):
        """Initialize the EventManager."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Subscription management
        self.subscribers: Dict[str, EventSubscription] = {}
        self._subscribers = defaultdict(list)
        
        # Event processing
        self.event_queue = queue.PriorityQueue(maxsize=DEFAULT_QUEUE_SIZE)
        self.event_history: List[Event] = []
        
        # Thread safety
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread = None
        
        # Event statistics
        self.stats = {
            "events_published": 0,
            "events_processed": 0,
            "subscribers_count": 0,
            "errors": 0,
        }
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def subscribe(self, *args, **kwargs) -> bool:
        """
        Subscribe to events with flexible parameter handling.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Callback function to invoke
            subscriber_id: Optional subscriber identifier
            
        Returns:
            bool: True if subscription successful
        """
        try:
            # Parse arguments
            event_type, callback, subscriber_id = self._parse_subscribe_args(args, kwargs)
            
            # Validate inputs
            if not self._validate_subscription(event_type, callback):
                return False
            
            # Create subscription
            event_type_str = str(event_type)
            
            with self._lock:
                if event_type_str not in self._subscribers:
                    self._subscribers[event_type_str] = []
                
                subscriber_info = {
                    "callback": callback,
                    "subscriber_id": subscriber_id or f"sub_{len(self._subscribers[event_type_str])}"
                }
                
                self._subscribers[event_type_str].append(subscriber_info)
                self.stats["subscribers_count"] = len(self._subscribers)
            
            self.logger.debug(f"Successfully subscribed to {event_type_str}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {event_type}: {str(e)}")
            self.stats["errors"] += 1
            return False
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """
        Unsubscribe from events.
        
        Args:
            subscriber_id: Subscriber identifier
            
        Returns:
            bool: True if unsubscription successful
        """
        try:
            with self._lock:
                removed = False
                for event_type, subscribers in self._subscribers.items():
                    self._subscribers[event_type] = [
                        sub for sub in subscribers 
                        if sub.get("subscriber_id") != subscriber_id
                    ]
                    if len(subscribers) != len(self._subscribers[event_type]):
                        removed = True
                
                if removed:
                    self.stats["subscribers_count"] = sum(
                        len(subs) for subs in self._subscribers.values()
                    )
                    self.logger.debug(f"Unsubscribed {subscriber_id}")
                    return True
                else:
                    self.logger.warning(f"Subscriber {subscriber_id} not found")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error in unsubscribe: {e}")
            self.stats["errors"] += 1
            return False
    
    def publish(self, event_type, data=None, source="unknown") -> bool:
        """
        Publish event to subscribers.
        
        Args:
            event_type: Type of event or Event object
            data: Event data dictionary
            source: Event source identifier
            
        Returns:
            bool: True if published successfully
        """
        try:
            # Extract event information
            actual_event_type, event_data, event_source = self._extract_event_info(
                event_type, data, source
            )
            
            if not actual_event_type:
                self.logger.warning(f"Invalid event type: {event_type}")
                return False
            
            # Create event info
            event_info = {
                "type": actual_event_type,
                "data": event_data,
                "timestamp": datetime.now(),
                "source": event_source,
            }
            
            # Process event
            with self._lock:
                self._add_to_history(event_info)
                self.stats["events_published"] += 1
                
                # Notify subscribers
                subscribers = self._subscribers.get(actual_event_type, [])
                
            # Notify outside lock to prevent deadlocks
            self._notify_subscribers(subscribers, event_info)
            self.stats["events_processed"] += 1
            
            self.logger.debug(
                f"Published {actual_event_type} to {len(subscribers)} subscribers"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error in publish: {e}")
            self.stats["errors"] += 1
            return False
    
    def create_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "unknown",
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> Event:
        """
        Create a new event.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Event source
            priority: Event priority
            correlation_id: Optional correlation ID
            
        Returns:
            Event object
        """
        return Event(
            id=f"evt_{uuid.uuid4().hex[:8]}",
            type=event_type,
            data=data,
            timestamp=datetime.now(),
            source=source,
            priority=priority,
            correlation_id=correlation_id,
        )
    
    def get_subscriber_count(self) -> int:
        """Get number of active subscribers."""
        with self._lock:
            return sum(len(subs) for subs in self._subscribers.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event manager statistics."""
        with self._lock:
            return dict(self.stats)
    
    def get_event_history(self, count: int = 100) -> List[Event]:
        """Get recent event history."""
        with self._lock:
            return self.event_history[-count:]
    
    def clear_history(self):
        """Clear event history."""
        with self._lock:
            self.event_history.clear()
            self.logger.debug("Event history cleared")
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _parse_subscribe_args(self, args: tuple, kwargs: dict) -> tuple:
        """Parse subscribe method arguments."""
        if len(args) >= 2:
            event_type = args[0]
            callback = args[1]
            subscriber_id = args[2] if len(args) > 2 else kwargs.get("subscriber_id")
        elif len(args) == 1 and "callback" in kwargs:
            event_type = args[0]
            callback = kwargs["callback"]
            subscriber_id = kwargs.get("subscriber_id")
        else:
            event_type = kwargs.get("event_type")
            callback = kwargs.get("callback")
            subscriber_id = kwargs.get("subscriber_id")
        
        return event_type, callback, subscriber_id
    
    def _validate_subscription(self, event_type, callback) -> bool:
        """Validate subscription parameters."""
        if not event_type:
            self.logger.warning("Subscribe called without event_type")
            return False
        
        if callback is None or not callable(callback):
            self.logger.warning(f"Invalid callback: {type(callback)}")
            return False
        
        return True
    
    def _extract_event_info(self, event_type, data, source) -> tuple:
        """Extract event information from various input types."""
        if hasattr(event_type, "__dict__") and hasattr(event_type, "type"):
            # Event object
            actual_event_type = str(getattr(event_type, "type", "UNKNOWN"))
            event_data = getattr(event_type, "data", data or {})
            event_source = getattr(event_type, "source", source)
        elif hasattr(event_type, "value"):
            # Enum with value
            actual_event_type = str(event_type.value)
            event_data = data or {}
            event_source = source
        else:
            # String
            actual_event_type = str(event_type)
            event_data = data or {}
            event_source = source
        
        return actual_event_type, event_data, event_source
    
    def _add_to_history(self, event_info: dict):
        """Add event to history with size limit."""
        self.event_history.append(event_info)
        if len(self.event_history) > MAX_EVENT_HISTORY:
            self.event_history = self.event_history[-MAX_EVENT_HISTORY:]
    
    def _notify_subscribers(self, subscribers: list, event_info: dict):
        """Notify subscribers of event."""
        for subscriber_info in subscribers:
            try:
                callback = subscriber_info["callback"]
                callback(event_info)
            except Exception as e:
                self.logger.error(f"Error notifying subscriber: {e}")
                self.stats["errors"] += 1
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self):
        """Start the event manager worker thread."""
        if not self._running:
            self._running = True
            self.logger.info("EventManager started")
    
    def stop(self):
        """Stop the event manager worker thread."""
        if self._running:
            self._running = False
            self.logger.info("EventManager stopped")
    
    def cleanup(self):
        """Clean up event manager resources."""
        self.stop()
        self.clear_history()
        self._subscribers.clear()
        self.logger.info("EventManager cleanup completed")
    
    def is_running(self) -> bool:
        """Check if event manager is running."""
        return self._running

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_event_manager_instance: Optional[EventManager] = None

def get_event_manager() -> EventManager:
    """
    Get singleton event manager instance.
    
    Returns:
        EventManager instance
    """
    global _event_manager_instance
    if _event_manager_instance is None:
        _event_manager_instance = EventManager()
    return _event_manager_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Export all public symbols
__all__ = [
    'EventManager',
    'Event', 
    'EventType',
    'EventPriority',
    'EventSubscription',
    'get_event_manager'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    manager = EventManager()
    
    if manager.start():
        print("✅ EventManager test passed")
        
        # Test subscription
        def test_callback(event):
            print(f"Received event: {event}")
        
        manager.subscribe(EventType.TRADE_EXECUTED, test_callback)
        
        # Test publishing
        manager.publish(EventType.TRADE_EXECUTED, {"symbol": "SPY", "price": 450.0})
        
        # Show statistics
        stats = manager.get_statistics()
        print(f"Statistics: {stats}")
        
        # Cleanup
        manager.stop()
        manager.cleanup()
    else:
        print("❌ EventManager test failed")