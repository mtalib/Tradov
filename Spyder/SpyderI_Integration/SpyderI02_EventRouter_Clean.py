#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderI02_EventRouter_Clean.py
Group: I (Integration)
Purpose: Clean version of Event Router with simplified event handling

Description:
    A simplified and cleaned version of the Event Router for lightweight
    event handling. This module provides basic event routing capabilities
    without the complex filtering and correlation features of the main
    EventRouter. Designed for scenarios requiring minimal overhead.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-09-04
Last Updated: 2025-09-28 Time: 14:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum, auto
from collections import defaultdict
import json
import uuid
import logging

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU07_Constants import LOG_CONFIG, TRADING_HOURS
    from SpyderU_Utilities.SpyderU08_Logger import setup_logger
except ImportError as e:
    print(f"Warning: Could not import Spyder utilities: {e}")
    LOG_CONFIG = {"level": "INFO"}

# ==============================================================================
# CONFIGURATION
# ==============================================================================
logger = (
    setup_logger(__name__)
    if "setup_logger" in globals()
    else logging.getLogger(__name__)
)


class EventType(Enum):
    """Simplified event types for clean router"""

    MARKET_DATA = auto()
    ORDER_UPDATE = auto()
    POSITION_CHANGE = auto()
    SYSTEM_STATUS = auto()
    ERROR = auto()
    HEARTBEAT = auto()


@dataclass
class CleanEvent:
    """Simplified event structure"""

    event_type: EventType
    source: str
    data: Dict[str, Any]
    timestamp: Optional[datetime] = None
    event_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.event_id is None:
            self.event_id = str(uuid.uuid4())


class CleanEventRouter:
    """
    Simplified Event Router for basic event handling

    This is a lightweight version that provides essential event routing
    functionality without the complexity of the full EventRouter.
    """

    def __init__(self):
        self.logger = logger
        self.subscribers = defaultdict(list)
        self.event_queue = queue.Queue(maxsize=1000)
        self.running = False
        self.worker_thread = None
        self.lock = threading.RLock()

        self.logger.info("CleanEventRouter initialized")

    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to events of specific type"""
        with self.lock:
            self.subscribers[event_type].append(callback)
            self.logger.debug(f"Subscribed to {event_type} events")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from events"""
        with self.lock:
            if callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
                self.logger.debug(f"Unsubscribed from {event_type} events")

    def publish(self, event: CleanEvent):
        """Publish an event"""
        try:
            self.event_queue.put_nowait(event)
        except queue.Full:
            self.logger.warning("Event queue full, dropping event")

    def start(self):
        """Start the event processing"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._process_events)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            self.logger.info("CleanEventRouter started")

    def stop(self):
        """Stop the event processing"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5.0)
        self.logger.info("CleanEventRouter stopped")

    def _process_events(self):
        """Process events from the queue"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1.0)
                self._handle_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")

    def _handle_event(self, event: CleanEvent):
        """Handle a single event"""
        subscribers = self.subscribers.get(event.event_type, [])

        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                self.logger.error(f"Error in event callback: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get basic router statistics"""
        return {
            "running": self.running,
            "queue_size": self.event_queue.qsize(),
            "subscriber_count": sum(len(subs) for subs in self.subscribers.values()),
            "event_types": list(self.subscribers.keys()),
        }


# ==============================================================================
# GLOBAL INSTANCE
# ==============================================================================
_clean_router_instance = None


def get_clean_router() -> CleanEventRouter:
    """Get the global clean router instance"""
    global _clean_router_instance
    if _clean_router_instance is None:
        _clean_router_instance = CleanEventRouter()
    return _clean_router_instance


# ==============================================================================
# TESTING
# ==============================================================================
if __name__ == "__main__":
    # Simple test
    router = CleanEventRouter()

    def test_callback(event):
        print(f"Received event: {event.event_type} from {event.source}")

    router.subscribe(EventType.HEARTBEAT, test_callback)
    router.start()

    # Send test event
    test_event = CleanEvent(
        event_type=EventType.HEARTBEAT,
        source="test",
        data={"message": "test heartbeat"},
    )
    router.publish(test_event)

    time.sleep(2)
    print(f"Router stats: {router.get_stats()}")

    router.stop()
