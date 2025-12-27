#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI06_AgentMessageBus.py
Group: I (Integration)
Purpose: Message bus for inter-agent communication
Author: Mohamed Talib
Date Created: 2025-01-27  
Last Updated: 2025-01-27 Time: 15:00:00

Description:
    This module provides a high-performance message bus for communication between
    all AI agents (X01-X15) and other system components. It implements pub/sub
    messaging, priority queuing, topic-based routing, and ensures reliable
    message delivery across the distributed agent ecosystem.

Key Features:
    - Publish/Subscribe messaging pattern
    - Topic-based message routing
    - Priority message queuing
    - Request/Reply patterns
    - Message persistence and replay
    - Dead letter queue for failed messages
    - Performance monitoring and metrics
    - Circuit breaker for fault tolerance
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import uuid
import pickle
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import heapq
import weakref

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_QUEUE_SIZE = 10000
MAX_MESSAGE_SIZE = 1024 * 1024  # 1MB
DEFAULT_TTL = 60  # 60 seconds
MAX_RETRIES = 3
DEAD_LETTER_THRESHOLD = 5
CIRCUIT_BREAKER_THRESHOLD = 10
CIRCUIT_BREAKER_TIMEOUT = 30  # seconds

# Topic definitions
TOPICS = {
    'market': 'market.*',
    'signals': 'signals.*',
    'risk': 'risk.*',
    'execution': 'execution.*',
    'performance': 'performance.*',
    'system': 'system.*',
    'alerts': 'alerts.*',
    'strategy': 'strategy.*',
    'research': 'research.*'
}

# ==============================================================================
# ENUMS
# ==============================================================================
class MessagePriority(Enum):
    """Message priority levels"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BULK = 4  # Lowest priority

class MessageType(Enum):
    """Types of messages"""
    PUBLISH = "publish"
    REQUEST = "request"
    REPLY = "reply"
    BROADCAST = "broadcast"
    COMMAND = "command"
    EVENT = "event"
    HEARTBEAT = "heartbeat"

class DeliveryMode(Enum):
    """Message delivery modes"""
    AT_MOST_ONCE = "at_most_once"  # Fire and forget
    AT_LEAST_ONCE = "at_least_once"  # Retry until ack
    EXACTLY_ONCE = "exactly_once"  # Guaranteed single delivery

class SubscriberState(Enum):
    """Subscriber connection states"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISCONNECTED = "disconnected"
    CIRCUIT_OPEN = "circuit_open"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Message:
    """Message structure for the bus"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    sender: str = ""
    message_type: MessageType = MessageType.PUBLISH
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Any = None
    headers: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    ttl: int = DEFAULT_TTL
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE
    retry_count: int = 0
    
    def __lt__(self, other):
        """For priority queue comparison"""
        return self.priority.value < other.priority.value
    
    def is_expired(self) -> bool:
        """Check if message has expired"""
        return (datetime.now() - self.timestamp).total_seconds() > self.ttl
    
    def to_json(self) -> str:
        """Convert to JSON"""
        return json.dumps(asdict(self), default=str)

@dataclass
class Subscriber:
    """Subscriber information"""
    id: str
    name: str
    topics: List[str]
    callback: Callable
    filter_func: Optional[Callable] = None
    state: SubscriberState = SubscriberState.ACTIVE
    message_count: int = 0
    error_count: int = 0
    last_message: Optional[datetime] = None
    circuit_breaker_opens: int = 0

@dataclass
class TopicStats:
    """Statistics for a topic"""
    topic: str
    message_count: int = 0
    subscriber_count: int = 0
    avg_processing_time: float = 0.0
    error_rate: float = 0.0
    last_message: Optional[datetime] = None

@dataclass
class BusMetrics:
    """Message bus metrics"""
    total_messages: int = 0
    delivered_messages: int = 0
    failed_messages: int = 0
    active_subscribers: int = 0
    topics_count: int = 0
    queue_size: int = 0
    dead_letter_count: int = 0
    avg_latency: float = 0.0
    throughput: float = 0.0

# ==============================================================================
# MAIN MESSAGE BUS CLASS
# ==============================================================================
class AgentMessageBus:
    """
    High-performance message bus for agent communication.
    
    Provides reliable pub/sub messaging with priority queuing,
    topic-based routing, and fault tolerance.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the message bus"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        
        # Threading
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        self._worker_thread = None
        
        # Message queues
        self.priority_queue = queue.PriorityQueue(maxsize=MAX_QUEUE_SIZE)
        self.dead_letter_queue = deque(maxlen=1000)
        self.pending_replies = {}  # correlation_id -> future
        
        # Subscriptions
        self.subscribers = {}  # subscriber_id -> Subscriber
        self.topic_subscribers = defaultdict(set)  # topic -> set of subscriber_ids
        
        # Topic management
        self.topic_stats = {}  # topic -> TopicStats
        self.topic_patterns = {}  # pattern -> compiled regex
        
        # Message history
        self.message_history = deque(maxlen=10000)
        self.reply_timeout = self.config.get('reply_timeout', 30)
        
        # Metrics
        self.metrics = BusMetrics()
        self.latency_history = deque(maxlen=1000)
        
        # Persistence
        self.persist_messages = self.config.get('persist', False)
        self.persistence_path = Path(self.config.get('persistence_path', 'data/messages'))
        
        # Start worker
        self._start_worker()
        
        self.logger.info("Agent Message Bus initialized")
    
    def _start_worker(self):
        """Start the message processing worker"""
        self._worker_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._worker_thread.start()
        self.logger.debug("Message processing worker started")
    
    def _process_messages(self):
        """Main message processing loop"""
        while not self._shutdown.is_set():
            try:
                # Get message with timeout
                try:
                    priority, message = self.priority_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Process message
                self._deliver_message(message)
                
                # Update metrics
                self.metrics.queue_size = self.priority_queue.qsize()
                
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
    
    def subscribe(
        self,
        subscriber_id: str,
        topics: List[str],
        callback: Callable,
        filter_func: Optional[Callable] = None,
        name: str = None
    ) -> bool:
        """
        Subscribe to topics.
        
        Args:
            subscriber_id: Unique subscriber identifier
            topics: List of topics or patterns to subscribe to
            callback: Function to call with messages
            filter_func: Optional filter function
            name: Human-readable name
            
        Returns:
            Success status
        """
        with self._lock:
            try:
                # Create subscriber
                subscriber = Subscriber(
                    id=subscriber_id,
                    name=name or subscriber_id,
                    topics=topics,
                    callback=callback,
                    filter_func=filter_func
                )
                
                # Register subscriber
                self.subscribers[subscriber_id] = subscriber
                
                # Update topic mappings
                for topic in topics:
                    self.topic_subscribers[topic].add(subscriber_id)
                    
                    # Initialize topic stats
                    if topic not in self.topic_stats:
                        self.topic_stats[topic] = TopicStats(topic=topic)
                    self.topic_stats[topic].subscriber_count += 1
                
                self.metrics.active_subscribers = len(self.subscribers)
                self.metrics.topics_count = len(self.topic_stats)
                
                self.logger.info(f"Subscriber {name} registered for topics: {topics}")
                return True
                
            except Exception as e:
                self.logger.error(f"Subscription failed: {e}")
                return False
    
    def unsubscribe(self, subscriber_id: str) -> bool:
        """Unsubscribe from all topics"""
        with self._lock:
            try:
                if subscriber_id not in self.subscribers:
                    return False
                
                subscriber = self.subscribers[subscriber_id]
                
                # Remove from topic mappings
                for topic in subscriber.topics:
                    self.topic_subscribers[topic].discard(subscriber_id)
                    if topic in self.topic_stats:
                        self.topic_stats[topic].subscriber_count -= 1
                
                # Remove subscriber
                del self.subscribers[subscriber_id]
                
                self.metrics.active_subscribers = len(self.subscribers)
                
                self.logger.info(f"Subscriber {subscriber.name} unsubscribed")
                return True
                
            except Exception as e:
                self.logger.error(f"Unsubscribe failed: {e}")
                return False
    
    async def publish(
        self,
        topic: str,
        payload: Any,
        sender: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        headers: Optional[Dict[str, Any]] = None,
        ttl: int = DEFAULT_TTL
    ) -> str:
        """
        Publish a message to a topic.
        
        Args:
            topic: Topic to publish to
            payload: Message payload
            sender: Sender identifier
            priority: Message priority
            headers: Optional headers
            ttl: Time to live in seconds
            
        Returns:
            Message ID
        """
        # Create message
        message = Message(
            topic=topic,
            sender=sender,
            message_type=MessageType.PUBLISH,
            priority=priority,
            payload=payload,
            headers=headers or {},
            ttl=ttl
        )
        
        # Add to queue
        self._enqueue_message(message)
        
        # Update metrics
        self.metrics.total_messages += 1
        if topic in self.topic_stats:
            self.topic_stats[topic].message_count += 1
            self.topic_stats[topic].last_message = datetime.now()
        
        return message.id
    
    async def request(
        self,
        topic: str,
        payload: Any,
        sender: str,
        timeout: Optional[float] = None
    ) -> Any:
        """
        Send request and wait for reply.
        
        Args:
            topic: Topic to send request to
            payload: Request payload
            sender: Sender identifier
            timeout: Reply timeout in seconds
            
        Returns:
            Reply payload
        """
        # Create request message
        correlation_id = str(uuid.uuid4())
        message = Message(
            topic=topic,
            sender=sender,
            message_type=MessageType.REQUEST,
            priority=MessagePriority.HIGH,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=f"{sender}.reply"
        )
        
        # Create future for reply
        future = asyncio.Future()
        self.pending_replies[correlation_id] = future
        
        # Send request
        self._enqueue_message(message)
        
        # Wait for reply
        try:
            reply = await asyncio.wait_for(
                future,
                timeout=timeout or self.reply_timeout
            )
            return reply
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Request timeout for {topic}")
            del self.pending_replies[correlation_id]
            return None
        
        except Exception as e:
            self.logger.error(f"Request failed: {e}")
            if correlation_id in self.pending_replies:
                del self.pending_replies[correlation_id]
            return None
    
    def reply(
        self,
        original_message: Message,
        payload: Any,
        sender: str
    ):
        """Send reply to a request"""
        if not original_message.correlation_id:
            self.logger.warning("Cannot reply to message without correlation_id")
            return
        
        # Create reply message
        reply_message = Message(
            topic=original_message.reply_to or f"{original_message.sender}.reply",
            sender=sender,
            message_type=MessageType.REPLY,
            priority=MessagePriority.HIGH,
            payload=payload,
            correlation_id=original_message.correlation_id
        )
        
        # Send reply
        self._enqueue_message(reply_message)
    
    def broadcast(
        self,
        payload: Any,
        sender: str,
        priority: MessagePriority = MessagePriority.NORMAL
    ):
        """Broadcast message to all subscribers"""
        message = Message(
            topic="*",  # Special broadcast topic
            sender=sender,
            message_type=MessageType.BROADCAST,
            priority=priority,
            payload=payload
        )
        
        self._enqueue_message(message)
    
    def _enqueue_message(self, message: Message):
        """Add message to priority queue"""
        try:
            # Check message size
            message_size = len(pickle.dumps(message))
            if message_size > MAX_MESSAGE_SIZE:
                self.logger.error(f"Message too large: {message_size} bytes")
                return
            
            # Add to queue with priority
            self.priority_queue.put((message.priority.value, message))
            
            # Persist if enabled
            if self.persist_messages:
                self._persist_message(message)
            
            # Record in history
            self.message_history.append(message)
            
        except queue.Full:
            self.logger.error("Message queue full, message dropped")
            self.metrics.failed_messages += 1
            self._add_to_dead_letter(message, "Queue full")
        
        except Exception as e:
            self.logger.error(f"Failed to enqueue message: {e}")
            self.metrics.failed_messages += 1
    
    def _deliver_message(self, message: Message):
        """Deliver message to subscribers"""
        delivered = False
        start_time = datetime.now()
        
        try:
            # Check if message expired
            if message.is_expired():
                self.logger.debug(f"Message {message.id} expired")
                self._add_to_dead_letter(message, "Expired")
                return
            
            # Handle reply messages
            if message.message_type == MessageType.REPLY:
                self._handle_reply(message)
                return
            
            # Find matching subscribers
            subscribers = self._find_subscribers(message.topic)
            
            # Deliver to each subscriber
            for subscriber_id in subscribers:
                subscriber = self.subscribers.get(subscriber_id)
                if not subscriber:
                    continue
                
                # Check subscriber state
                if subscriber.state != SubscriberState.ACTIVE:
                    continue
                
                # Apply filter if exists
                if subscriber.filter_func:
                    try:
                        if not subscriber.filter_func(message):
                            continue
                    except Exception as e:
                        self.logger.error(f"Filter function error: {e}")
                        continue
                
                # Deliver message
                try:
                    subscriber.callback(message)
                    subscriber.message_count += 1
                    subscriber.last_message = datetime.now()
                    delivered = True
                    
                except Exception as e:
                    self.logger.error(f"Delivery to {subscriber.name} failed: {e}")
                    self._handle_delivery_failure(subscriber, message, e)
            
            # Update metrics
            if delivered:
                self.metrics.delivered_messages += 1
                latency = (datetime.now() - start_time).total_seconds()
                self.latency_history.append(latency)
                self.metrics.avg_latency = np.mean(list(self.latency_history))
            else:
                # No subscribers or all failed
                if message.delivery_mode == DeliveryMode.AT_LEAST_ONCE:
                    self._retry_message(message)
                    
        except Exception as e:
            self.logger.error(f"Message delivery error: {e}")
            self.metrics.failed_messages += 1
            self._add_to_dead_letter(message, str(e))
    
    def _find_subscribers(self, topic: str) -> Set[str]:
        """Find subscribers for a topic"""
        subscribers = set()
        
        # Direct topic match
        if topic in self.topic_subscribers:
            subscribers.update(self.topic_subscribers[topic])
        
        # Wildcard matching
        if topic == "*":
            # Broadcast to all
            subscribers.update(self.subscribers.keys())
        else:
            # Pattern matching for wildcards
            for pattern, subs in self.topic_subscribers.items():
                if self._match_topic(topic, pattern):
                    subscribers.update(subs)
        
        return subscribers
    
    def _match_topic(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern"""
        if pattern == "*":
            return True
        
        if "*" in pattern:
            # Simple wildcard matching
            pattern_parts = pattern.split(".")
            topic_parts = topic.split(".")
            
            if len(pattern_parts) != len(topic_parts):
                return False
            
            for p, t in zip(pattern_parts, topic_parts):
                if p != "*" and p != t:
                    return False
            
            return True
        
        return topic == pattern
    
    def _handle_reply(self, message: Message):
        """Handle reply message"""
        correlation_id = message.correlation_id
        
        if correlation_id in self.pending_replies:
            future = self.pending_replies[correlation_id]
            if not future.done():
                future.set_result(message.payload)
            del self.pending_replies[correlation_id]
    
    def _handle_delivery_failure(self, subscriber: Subscriber, message: Message, error: Exception):
        """Handle failed delivery to subscriber"""
        subscriber.error_count += 1
        
        # Check for circuit breaker
        if subscriber.error_count >= CIRCUIT_BREAKER_THRESHOLD:
            self.logger.warning(f"Circuit breaker opened for {subscriber.name}")
            subscriber.state = SubscriberState.CIRCUIT_OPEN
            subscriber.circuit_breaker_opens += 1
            
            # Schedule circuit breaker reset
            threading.Timer(
                CIRCUIT_BREAKER_TIMEOUT,
                self._reset_circuit_breaker,
                args=[subscriber.id]
            ).start()
        
        # Retry if needed
        if message.delivery_mode == DeliveryMode.AT_LEAST_ONCE:
            self._retry_message(message)
    
    def _reset_circuit_breaker(self, subscriber_id: str):
        """Reset circuit breaker for subscriber"""
        with self._lock:
            if subscriber_id in self.subscribers:
                subscriber = self.subscribers[subscriber_id]
                subscriber.state = SubscriberState.ACTIVE
                subscriber.error_count = 0
                self.logger.info(f"Circuit breaker reset for {subscriber.name}")
    
    def _retry_message(self, message: Message):
        """Retry failed message"""
        message.retry_count += 1
        
        if message.retry_count <= MAX_RETRIES:
            # Re-enqueue with lower priority
            message.priority = MessagePriority.LOW
            self._enqueue_message(message)
        else:
            # Max retries exceeded
            self._add_to_dead_letter(message, "Max retries exceeded")
    
    def _add_to_dead_letter(self, message: Message, reason: str):
        """Add message to dead letter queue"""
        self.dead_letter_queue.append({
            'message': message,
            'reason': reason,
            'timestamp': datetime.now()
        })
        
        self.metrics.dead_letter_count = len(self.dead_letter_queue)
        self.metrics.failed_messages += 1
        
        self.logger.warning(f"Message {message.id} sent to dead letter: {reason}")
    
    def _persist_message(self, message: Message):
        """Persist message to disk"""
        try:
            self.persistence_path.mkdir(parents=True, exist_ok=True)
            
            filename = self.persistence_path / f"{message.id}.pkl"
            with open(filename, 'wb') as f:
                pickle.dump(message, f)
                
        except Exception as e:
            self.logger.error(f"Failed to persist message: {e}")
    
    def get_metrics(self) -> BusMetrics:
        """Get current metrics"""
        with self._lock:
            # Calculate throughput
            if self.latency_history:
                time_window = 60  # 1 minute
                recent_messages = [
                    m for m in self.message_history
                    if (datetime.now() - m.timestamp).total_seconds() <= time_window
                ]
                self.metrics.throughput = len(recent_messages) / time_window
            
            return self.metrics
    
    def get_topic_stats(self, topic: str = None) -> Dict[str, TopicStats]:
        """Get statistics for topics"""
        with self._lock:
            if topic:
                return {topic: self.topic_stats.get(topic)}
            return dict(self.topic_stats)
    
    def get_dead_letters(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent dead letter messages"""
        return list(self.dead_letter_queue)[-limit:]
    
    def clear_dead_letters(self):
        """Clear dead letter queue"""
        with self._lock:
            self.dead_letter_queue.clear()
            self.metrics.dead_letter_count = 0
            self.logger.info("Dead letter queue cleared")
    
    def shutdown(self):
        """Shutdown message bus"""
        self.logger.info("Shutting down message bus...")
        
        # Signal shutdown
        self._shutdown.set()
        
        # Wait for worker to finish
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        
        # Process remaining messages
        while not self.priority_queue.empty():
            try:
                _, message = self.priority_queue.get_nowait()
                self.logger.debug(f"Dropping message {message.id} during shutdown")
            except:
                break
        
        self.logger.info("Message bus shutdown complete")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_message_bus(config: Optional[Dict[str, Any]] = None) -> AgentMessageBus:
    """Create and initialize message bus instance"""
    return AgentMessageBus(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    import asyncio
    
    async def test_message_bus():
        # Create message bus
        bus = create_message_bus()
        
        print("\n" + "="*60)
        print("AGENT MESSAGE BUS TEST")
        print("="*60)
        
        # Test subscriber
        def test_callback(message: Message):
            print(f"Received: {message.topic} - {message.payload}")
        
        # Subscribe to topics
        bus.subscribe(
            "test_agent",
            ["market.*", "signals.*"],
            test_callback,
            name="Test Agent"
        )
        
        # Publish messages
        print("\nPublishing messages...")
        
        await bus.publish(
            "market.update",
            {"SPY": 450.0, "VIX": 18.5},
            "market_agent",
            priority=MessagePriority.HIGH
        )
        
        await bus.publish(
            "signals.entry",
            {"action": "BUY", "strategy": "IronCondor"},
            "strategy_agent",
            priority=MessagePriority.NORMAL
        )
        
        # Test request/reply
        print("\nTesting request/reply...")
        
        async def reply_handler(message: Message):
            if message.message_type == MessageType.REQUEST:
                bus.reply(message, {"status": "OK"}, "responder")
        
        bus.subscribe("responder", ["test.request"], reply_handler)
        
        reply = await bus.request(
            "test.request",
            {"query": "status"},
            "requester"
        )
        print(f"Reply received: {reply}")
        
        # Wait for processing
        await asyncio.sleep(1)
        
        # Get metrics
        metrics = bus.get_metrics()
        print(f"\nMetrics:")
        print(f"  Total Messages: {metrics.total_messages}")
        print(f"  Delivered: {metrics.delivered_messages}")
        print(f"  Failed: {metrics.failed_messages}")
        print(f"  Avg Latency: {metrics.avg_latency:.4f}s")
        print(f"  Active Subscribers: {metrics.active_subscribers}")
        
        # Shutdown
        bus.shutdown()
    
    # Run test
    asyncio.run(test_message_bus())
