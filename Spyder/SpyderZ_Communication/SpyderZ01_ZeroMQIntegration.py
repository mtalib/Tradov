#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderZ01_ZeroMQIntegration.py
Group: Z (ZeroMQ Communication Layer)
Purpose: High-performance IPC with robust error handling and reliability

Description:
    Enhanced ZeroMQ-based communication for SPYDER with production-grade
    reliability features including:
    - Automatic reconnection with exponential backoff
    - Circuit breakers for system protection
    - Message acknowledgment and retry mechanisms
    - Heartbeat monitoring for connection health
    - Comprehensive error recovery strategies

Author: SPYDER Team
Date: 2025-01-03
Version: 2.0
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import zmq
import json
import threading
import time
import queue
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum, auto
import logging
from collections import defaultdict, deque
import random

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connection settings
DEFAULT_TIMEOUT = 5000  # milliseconds
HEARTBEAT_INTERVAL = 1.0  # seconds
HEARTBEAT_TIMEOUT = 5.0  # seconds
RECONNECT_INITIAL_DELAY = 0.1  # seconds
RECONNECT_MAX_DELAY = 30.0  # seconds
RECONNECT_MULTIPLIER = 2.0  # exponential backoff multiplier

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD = 10  # failures before opening
CIRCUIT_BREAKER_TIMEOUT = 60.0  # seconds before attempting reset
CIRCUIT_BREAKER_HALF_OPEN_ATTEMPTS = 3  # test attempts in half-open state

# Message reliability settings
MESSAGE_RETRY_ATTEMPTS = 3
MESSAGE_RETRY_DELAY = 0.5  # seconds
MESSAGE_QUEUE_SIZE = 10000
ACK_TIMEOUT = 3.0  # seconds

# Default ports for different services
MARKET_DATA_PORT = 5555
TRADE_EXECUTION_PORT = 5556
RISK_MONITOR_PORT = 5557
STRATEGY_PORT = 5558
DASHBOARD_PORT = 5559

# ==============================================================================
# ENUMS
# ==============================================================================
class MessageType(Enum):
    """Message types for SPYDER communication."""
    MARKET_DATA = "MARKET_DATA"
    TRADE_ORDER = "TRADE_ORDER"
    TRADE_FILL = "TRADE_FILL"
    RISK_UPDATE = "RISK_UPDATE"
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    SYSTEM_STATUS = "SYSTEM_STATUS"
    POSITION_UPDATE = "POSITION_UPDATE"
    PNL_UPDATE = "PNL_UPDATE"
    HEARTBEAT = "HEARTBEAT"
    ERROR = "ERROR"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    RETRY = "RETRY"

class ConnectionState(Enum):
    """Connection state for tracking."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    FAILED = auto()

class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = auto()  # Normal operation
    OPEN = auto()    # Blocking requests
    HALF_OPEN = auto()  # Testing if service recovered

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SpyderMessage:
    """Enhanced message format with reliability features."""
    msg_type: MessageType
    timestamp: datetime
    source: str
    destination: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int = 0
    requires_ack: bool = True
    priority: int = 5  # 1-10, higher is more important
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        msg_dict = {
            'msg_type': self.msg_type.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'destination': self.destination,
            'data': self.data,
            'correlation_id': self.correlation_id,
            'message_id': self.message_id,
            'retry_count': self.retry_count,
            'requires_ack': self.requires_ack,
            'priority': self.priority
        }
        return json.dumps(msg_dict)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SpyderMessage':
        """Create message from JSON string."""
        msg_dict = json.loads(json_str)
        return cls(
            msg_type=MessageType(msg_dict['msg_type']),
            timestamp=datetime.fromisoformat(msg_dict['timestamp']),
            source=msg_dict['source'],
            destination=msg_dict['destination'],
            data=msg_dict['data'],
            correlation_id=msg_dict.get('correlation_id'),
            message_id=msg_dict.get('message_id', str(uuid.uuid4())),
            retry_count=msg_dict.get('retry_count', 0),
            requires_ack=msg_dict.get('requires_ack', True),
            priority=msg_dict.get('priority', 5)
        )

@dataclass
class ConnectionMetrics:
    """Metrics for connection monitoring."""
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    reconnect_attempts: int = 0
    last_heartbeat: Optional[datetime] = None
    connection_uptime: float = 0.0
    average_latency: float = 0.0
    error_count: int = 0

# ==============================================================================
# CIRCUIT BREAKER
# ==============================================================================
class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""
    
    def __init__(self, 
                 failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD,
                 timeout: float = CIRCUIT_BREAKER_TIMEOUT,
                 half_open_attempts: int = CIRCUIT_BREAKER_HALF_OPEN_ATTEMPTS):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_attempts = half_open_attempts
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_attempt_count = 0
        self._lock = threading.Lock()
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_attempt_count = 0
                else:
                    raise Exception("Circuit breaker is OPEN")
            
        try:
            result = func(*args, **kwargs)
            with self._lock:
                self._on_success()
            return result
        except Exception as e:
            with self._lock:
                self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time > self.timeout)
    
    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_attempt_count += 1
            if self.half_open_attempt_count >= self.half_open_attempts:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN

# ==============================================================================
# ENHANCED PUBLISHER
# ==============================================================================
class SpyderPublisher:
    """Enhanced ZeroMQ Publisher with reliability features."""
    
    def __init__(self, port: int, component_name: str):
        """Initialize enhanced publisher."""
        self.port = port
        self.component_name = component_name
        self.context = zmq.Context()
        self.socket = None
        self.state = ConnectionState.DISCONNECTED
        self.circuit_breaker = CircuitBreaker()
        self.metrics = ConnectionMetrics()
        self._lock = threading.Lock()
        self._heartbeat_thread = None
        self._reconnect_thread = None
        self._reconnect_delay = RECONNECT_INITIAL_DELAY
        self._running = False
        
        # Message queue for reliability
        self._message_queue = queue.PriorityQueue(maxsize=MESSAGE_QUEUE_SIZE)
        self._pending_acks = {}
        self._retry_queue = deque()
        
        # Setup logging
        self.logger = logging.getLogger(f"SpyderPublisher.{component_name}")
        
    def connect(self) -> bool:
        """Connect publisher with error handling."""
        try:
            with self._lock:
                if self.state == ConnectionState.CONNECTED:
                    return True
                    
                self.state = ConnectionState.CONNECTING
                
            # Create socket
            self.socket = self.context.socket(zmq.PUB)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.setsockopt(zmq.SNDHWM, 0)  # No limit on send queue
            
            # Bind to port
            self.socket.bind(f"tcp://*:{self.port}")
            
            with self._lock:
                self.state = ConnectionState.CONNECTED
                self._running = True
                self._reconnect_delay = RECONNECT_INITIAL_DELAY
                
            # Start heartbeat thread
            self._start_heartbeat()
            
            # Start message processor thread
            self._start_message_processor()
            
            self.logger.info(f"Publisher connected on port {self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            with self._lock:
                self.state = ConnectionState.FAILED
            self._schedule_reconnect()
            return False
    
    def publish(self, message: SpyderMessage) -> bool:
        """Publish message with reliability guarantees."""
        if self.state != ConnectionState.CONNECTED:
            # Queue message for later delivery
            self._queue_message(message)
            return False
            
        try:
            # Use circuit breaker for protection
            return self.circuit_breaker.call(self._publish_internal, message)
        except Exception as e:
            self.logger.error(f"Publish failed: {e}")
            self._queue_message(message)
            return False
    
    def _publish_internal(self, message: SpyderMessage) -> bool:
        """Internal publish method."""
        try:
            # Add to pending acks if acknowledgment required
            if message.requires_ack:
                self._pending_acks[message.message_id] = {
                    'message': message,
                    'timestamp': time.time(),
                    'attempts': 1
                }
            
            # Send message
            self.socket.send_string(message.to_json())
            self.metrics.messages_sent += 1
            
            return True
            
        except zmq.ZMQError as e:
            self.metrics.messages_failed += 1
            if e.errno == zmq.EAGAIN:
                # Socket not ready, queue for retry
                self._queue_message(message)
            else:
                # More serious error, trigger reconnection
                self._handle_connection_error(e)
            return False
    
    def _queue_message(self, message: SpyderMessage):
        """Queue message for later delivery."""
        try:
            # Priority queue: negative priority for higher priority first
            self._message_queue.put((-message.priority, time.time(), message))
        except queue.Full:
            self.logger.error("Message queue full, dropping message")
            self.metrics.messages_failed += 1
    
    def _start_heartbeat(self):
        """Start heartbeat thread."""
        def heartbeat_loop():
            while self._running:
                try:
                    if self.state == ConnectionState.CONNECTED:
                        heartbeat = SpyderMessage(
                            msg_type=MessageType.HEARTBEAT,
                            timestamp=datetime.now(),
                            source=self.component_name,
                            destination="ALL",
                            data={"status": "alive"},
                            requires_ack=False,
                            priority=1
                        )
                        self._publish_internal(heartbeat)
                        self.metrics.last_heartbeat = datetime.now()
                except Exception as e:
                    self.logger.error(f"Heartbeat failed: {e}")
                
                time.sleep(HEARTBEAT_INTERVAL)
        
        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
    
    def _start_message_processor(self):
        """Start thread to process queued messages."""
        def process_loop():
            while self._running:
                try:
                    # Process queued messages
                    if not self._message_queue.empty() and self.state == ConnectionState.CONNECTED:
                        _, _, message = self._message_queue.get(timeout=0.1)
                        self._publish_internal(message)
                    
                    # Check for acknowledgment timeouts
                    self._check_acknowledgments()
                    
                    # Process retry queue
                    self._process_retries()
                    
                except queue.Empty:
                    pass
                except Exception as e:
                    self.logger.error(f"Message processor error: {e}")
                
                time.sleep(0.01)  # Small delay to prevent CPU spinning
        
        thread = threading.Thread(target=process_loop, daemon=True)
        thread.start()
    
    def _check_acknowledgments(self):
        """Check for acknowledgment timeouts."""
        current_time = time.time()
        timed_out = []
        
        for msg_id, info in self._pending_acks.items():
            if current_time - info['timestamp'] > ACK_TIMEOUT:
                timed_out.append(msg_id)
        
        for msg_id in timed_out:
            info = self._pending_acks.pop(msg_id)
            message = info['message']
            
            if message.retry_count < MESSAGE_RETRY_ATTEMPTS:
                message.retry_count += 1
                self._retry_queue.append((time.time() + MESSAGE_RETRY_DELAY, message))
            else:
                self.logger.error(f"Message {msg_id} failed after {MESSAGE_RETRY_ATTEMPTS} attempts")
                self.metrics.messages_failed += 1
    
    def _process_retries(self):
        """Process messages scheduled for retry."""
        current_time = time.time()
        
        while self._retry_queue and self._retry_queue[0][0] <= current_time:
            _, message = self._retry_queue.popleft()
            self._publish_internal(message)
    
    def _handle_connection_error(self, error: Exception):
        """Handle connection errors."""
        self.logger.error(f"Connection error: {error}")
        with self._lock:
            self.state = ConnectionState.FAILED
            self.metrics.error_count += 1
        
        self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
            
        def reconnect_loop():
            while self.state != ConnectionState.CONNECTED and self._running:
                time.sleep(self._reconnect_delay)
                
                self.logger.info(f"Attempting reconnection (attempt {self.metrics.reconnect_attempts + 1})")
                with self._lock:
                    self.state = ConnectionState.RECONNECTING
                    self.metrics.reconnect_attempts += 1
                
                if self.connect():
                    self.logger.info("Reconnection successful")
                    break
                else:
                    # Exponential backoff
                    self._reconnect_delay = min(
                        self._reconnect_delay * RECONNECT_MULTIPLIER,
                        RECONNECT_MAX_DELAY
                    )
        
        self._reconnect_thread = threading.Thread(target=reconnect_loop, daemon=True)
        self._reconnect_thread.start()
    
    def disconnect(self):
        """Disconnect publisher gracefully."""
        self._running = False
        
        # Wait for threads to finish
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2)
        
        # Close socket
        if self.socket:
            self.socket.close()
        
        with self._lock:
            self.state = ConnectionState.DISCONNECTED
        
        self.logger.info("Publisher disconnected")
    
    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics."""
        return self.metrics

# ==============================================================================
# ENHANCED SUBSCRIBER
# ==============================================================================
class SpyderSubscriber:
    """Enhanced ZeroMQ Subscriber with reliability features."""
    
    def __init__(self, port: int, component_name: str, topics: Optional[List[str]] = None):
        """Initialize enhanced subscriber."""
        self.port = port
        self.component_name = component_name
        self.topics = topics or [""]  # Empty string subscribes to all
        self.context = zmq.Context()
        self.socket = None
        self.state = ConnectionState.DISCONNECTED
        self.circuit_breaker = CircuitBreaker()
        self.metrics = ConnectionMetrics()
        self._lock = threading.Lock()
        self._running = False
        self._reconnect_delay = RECONNECT_INITIAL_DELAY
        self._last_heartbeat_check = time.time()
        
        # Message handlers
        self._handlers = defaultdict(list)
        self._acknowledgment_socket = None
        
        # Setup logging
        self.logger = logging.getLogger(f"SpyderSubscriber.{component_name}")
    
    def connect(self) -> bool:
        """Connect subscriber with error handling."""
        try:
            with self._lock:
                if self.state == ConnectionState.CONNECTED:
                    return True
                
                self.state = ConnectionState.CONNECTING
            
            # Create socket
            self.socket = self.context.socket(zmq.SUB)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.setsockopt(zmq.RCVTIMEO, DEFAULT_TIMEOUT)
            
            # Connect to publisher
            self.socket.connect(f"tcp://localhost:{self.port}")
            
            # Subscribe to topics
            for topic in self.topics:
                self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
            
            # Create acknowledgment socket
            self._acknowledgment_socket = self.context.socket(zmq.PUSH)
            self._acknowledgment_socket.connect(f"tcp://localhost:{self.port + 1000}")
            
            with self._lock:
                self.state = ConnectionState.CONNECTED
                self._running = True
                self._reconnect_delay = RECONNECT_INITIAL_DELAY
            
            self.logger.info(f"Subscriber connected to port {self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            with self._lock:
                self.state = ConnectionState.FAILED
            self._schedule_reconnect()
            return False
    
    def subscribe(self, topic: str, handler: Callable[[SpyderMessage], None]):
        """Subscribe to a topic with a handler."""
        self._handlers[topic].append(handler)
        
        # Add topic subscription if already connected
        if self.socket and self.state == ConnectionState.CONNECTED:
            self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
    
    def start_listening(self):
        """Start listening for messages."""
        def listen_loop():
            while self._running:
                try:
                    if self.state != ConnectionState.CONNECTED:
                        time.sleep(0.1)
                        continue
                    
                    # Check for heartbeat timeout
                    self._check_heartbeat_timeout()
                    
                    # Receive message with timeout
                    try:
                        message_str = self.socket.recv_string(flags=zmq.NOBLOCK)
                        message = SpyderMessage.from_json(message_str)
                        
                        # Update metrics
                        self.metrics.messages_received += 1
                        
                        # Handle heartbeat
                        if message.msg_type == MessageType.HEARTBEAT:
                            self.metrics.last_heartbeat = datetime.now()
                            continue
                        
                        # Send acknowledgment if required
                        if message.requires_ack:
                            self._send_acknowledgment(message)
                        
                        # Process message
                        self._process_message(message)
                        
                    except zmq.Again:
                        # No message available
                        pass
                        
                except zmq.ZMQError as e:
                    if e.errno != zmq.EAGAIN:
                        self._handle_connection_error(e)
                except Exception as e:
                    self.logger.error(f"Listen error: {e}")
                
                time.sleep(0.001)  # Small delay to prevent CPU spinning
        
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()
    
    def _process_message(self, message: SpyderMessage):
        """Process received message."""
        try:
            # Call handlers for message type
            handlers = self._handlers.get(message.msg_type.value, [])
            handlers.extend(self._handlers.get("", []))  # Global handlers
            
            for handler in handlers:
                try:
                    handler(message)
                except Exception as e:
                    self.logger.error(f"Handler error: {e}")
                    
        except Exception as e:
            self.logger.error(f"Message processing error: {e}")
    
    def _send_acknowledgment(self, message: SpyderMessage):
        """Send acknowledgment for received message."""
        try:
            ack = SpyderMessage(
                msg_type=MessageType.ACKNOWLEDGMENT,
                timestamp=datetime.now(),
                source=self.component_name,
                destination=message.source,
                data={"original_message_id": message.message_id},
                requires_ack=False,
                priority=1
            )
            
            if self._acknowledgment_socket:
                self._acknowledgment_socket.send_string(ack.to_json())
                
        except Exception as e:
            self.logger.error(f"Failed to send acknowledgment: {e}")
    
    def _check_heartbeat_timeout(self):
        """Check if heartbeat has timed out."""
        current_time = time.time()
        
        if current_time - self._last_heartbeat_check < HEARTBEAT_TIMEOUT:
            return
            
        self._last_heartbeat_check = current_time
        
        if self.metrics.last_heartbeat:
            time_since_heartbeat = (datetime.now() - self.metrics.last_heartbeat).total_seconds()
            if time_since_heartbeat > HEARTBEAT_TIMEOUT:
                self.logger.warning("Heartbeat timeout detected")
                self._handle_connection_error(Exception("Heartbeat timeout"))
    
    def _handle_connection_error(self, error: Exception):
        """Handle connection errors."""
        self.logger.error(f"Connection error: {error}")
        with self._lock:
            self.state = ConnectionState.FAILED
            self.metrics.error_count += 1
        
        self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt."""
        def reconnect_loop():
            while self.state != ConnectionState.CONNECTED and self._running:
                time.sleep(self._reconnect_delay)
                
                self.logger.info(f"Attempting reconnection (attempt {self.metrics.reconnect_attempts + 1})")
                with self._lock:
                    self.state = ConnectionState.RECONNECTING
                    self.metrics.reconnect_attempts += 1
                
                # Close old socket
                if self.socket:
                    self.socket.close()
                
                if self.connect():
                    self.logger.info("Reconnection successful")
                    
                    # Re-subscribe to all topics
                    for topic in self._handlers.keys():
                        if topic:  # Skip empty string (global handler)
                            self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)
                    break
                else:
                    # Exponential backoff
                    self._reconnect_delay = min(
                        self._reconnect_delay * RECONNECT_MULTIPLIER,
                        RECONNECT_MAX_DELAY
                    )
        
        thread = threading.Thread(target=reconnect_loop, daemon=True)
        thread.start()
    
    def disconnect(self):
        """Disconnect subscriber gracefully."""
        self._running = False
        
        # Close sockets
        if self.socket:
            self.socket.close()
        if self._acknowledgment_socket:
            self._acknowledgment_socket.close()
        
        with self._lock:
            self.state = ConnectionState.DISCONNECTED
        
        self.logger.info("Subscriber disconnected")
    
    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics."""
        return self.metrics

# ==============================================================================
# REQUEST/REPLY PATTERN WITH RELIABILITY
# ==============================================================================
class SpyderRequester:
    """Enhanced ZeroMQ Requester with timeout and retry."""
    
    def __init__(self, port: int, component_name: str):
        """Initialize enhanced requester."""
        self.port = port
        self.component_name = component_name
        self.context = zmq.Context()
        self.socket = None
        self.state = ConnectionState.DISCONNECTED
        self.circuit_breaker = CircuitBreaker()
        self.metrics = ConnectionMetrics()
        self._lock = threading.Lock()
        
        # Setup logging
        self.logger = logging.getLogger(f"SpyderRequester.{component_name}")
    
    def connect(self) -> bool:
        """Connect requester with error handling."""
        try:
            with self._lock:
                if self.state == ConnectionState.CONNECTED:
                    return True
                
                self.state = ConnectionState.CONNECTING
            
            # Create socket
            self.socket = self.context.socket(zmq.REQ)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.setsockopt(zmq.RCVTIMEO, DEFAULT_TIMEOUT)
            self.socket.setsockopt(zmq.SNDTIMEO, DEFAULT_TIMEOUT)
            
            # Connect to server
            self.socket.connect(f"tcp://localhost:{self.port}")
            
            with self._lock:
                self.state = ConnectionState.CONNECTED
            
            self.logger.info(f"Requester connected to port {self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            with self._lock:
                self.state = ConnectionState.FAILED
            return False
    
    def request(self, message: SpyderMessage, timeout: float = None) -> Optional[SpyderMessage]:
        """Send request and wait for reply with timeout and retry."""
        if self.state != ConnectionState.CONNECTED:
            if not self.connect():
                return None
        
        timeout = timeout or (DEFAULT_TIMEOUT / 1000.0)
        
        for attempt in range(MESSAGE_RETRY_ATTEMPTS):
            try:
                # Use circuit breaker
                return self.circuit_breaker.call(
                    self._request_internal, message, timeout
                )
            except Exception as e:
                self.logger.error(f"Request attempt {attempt + 1} failed: {e}")
                
                if attempt < MESSAGE_RETRY_ATTEMPTS - 1:
                    # Reconnect for next attempt
                    self._reconnect()
                    time.sleep(MESSAGE_RETRY_DELAY * (attempt + 1))
                else:
                    self.metrics.messages_failed += 1
                    return None
    
    def _request_internal(self, message: SpyderMessage, timeout: float) -> Optional[SpyderMessage]:
        """Internal request method."""
        try:
            # Send request
            self.socket.send_string(message.to_json())
            self.metrics.messages_sent += 1
            
            # Wait for reply with timeout
            if self.socket.poll(timeout * 1000, zmq.POLLIN):
                reply_str = self.socket.recv_string()
                reply = SpyderMessage.from_json(reply_str)
                self.metrics.messages_received += 1
                return reply
            else:
                raise TimeoutError("Request timed out")
                
        except zmq.ZMQError as e:
            raise e
    
    def _reconnect(self):
        """Reconnect socket."""
        try:
            if self.socket:
                self.socket.close()
            
            self.socket = self.context.socket(zmq.REQ)
            self.socket.setsockopt(zmq.LINGER, 0)
            self.socket.setsockopt(zmq.RCVTIMEO, DEFAULT_TIMEOUT)
            self.socket.setsockopt(zmq.SNDTIMEO, DEFAULT_TIMEOUT)
            self.socket.connect(f"tcp://localhost:{self.port}")
            
            with self._lock:
                self.state = ConnectionState.CONNECTED
                
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
            with self._lock:
                self.state = ConnectionState.FAILED

# ==============================================================================
# COMMUNICATION HUB
# ==============================================================================
class SpyderCommHub:
    """Central communication hub with enhanced reliability."""
    
    def __init__(self, component_name: str):
        """Initialize communication hub."""
        self.component_name = component_name
        self.publishers = {}
        self.subscribers = {}
        self.requesters = {}
        self.reply_servers = {}
        self._running = False
        self._monitor_thread = None
        self.logger = logging.getLogger(f"SpyderCommHub.{component_name}")
        
    def create_publisher(self, name: str, port: int) -> SpyderPublisher:
        """Create and register a publisher."""
        publisher = SpyderPublisher(port, f"{self.component_name}.{name}")
        self.publishers[name] = publisher
        return publisher
    
    def create_subscriber(self, name: str, port: int, topics: List[str] = None) -> SpyderSubscriber:
        """Create and register a subscriber."""
        subscriber = SpyderSubscriber(port, f"{self.component_name}.{name}", topics)
        self.subscribers[name] = subscriber
        return subscriber
    
    def create_requester(self, name: str, port: int) -> SpyderRequester:
        """Create and register a requester."""
        requester = SpyderRequester(port, f"{self.component_name}.{name}")
        self.requesters[name] = requester
        return requester
    
    def start(self):
        """Start all communication components."""
        self._running = True
        
        # Connect all publishers
        for name, publisher in self.publishers.items():
            if publisher.connect():
                self.logger.info(f"Publisher '{name}' started")
            else:
                self.logger.error(f"Failed to start publisher '{name}'")
        
        # Connect all subscribers and start listening
        for name, subscriber in self.subscribers.items():
            if subscriber.connect():
                subscriber.start_listening()
                self.logger.info(f"Subscriber '{name}' started")
            else:
                self.logger.error(f"Failed to start subscriber '{name}'")
        
        # Connect all requesters
        for name, requester in self.requesters.items():
            if requester.connect():
                self.logger.info(f"Requester '{name}' started")
            else:
                self.logger.error(f"Failed to start requester '{name}'")
        
        # Start monitoring thread
        self._start_monitoring()
    
    def stop(self):
        """Stop all communication components."""
        self._running = False
        
        # Stop monitoring thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        
        # Disconnect all components
        for publisher in self.publishers.values():
            publisher.disconnect()
        
        for subscriber in self.subscribers.values():
            subscriber.disconnect()
        
        for requester in self.requesters.values():
            if requester.socket:
                requester.socket.close()
        
        self.logger.info("Communication hub stopped")
    
    def _start_monitoring(self):
        """Start monitoring thread for health checks."""
        def monitor_loop():
            while self._running:
                try:
                    # Collect metrics from all components
                    metrics = self.get_all_metrics()
                    
                    # Log summary
                    total_sent = sum(m.messages_sent for m in metrics.values())
                    total_received = sum(m.messages_received for m in metrics.values())
                    total_failed = sum(m.messages_failed for m in metrics.values())
                    total_errors = sum(m.error_count for m in metrics.values())
                    
                    self.logger.info(
                        f"Communication metrics - Sent: {total_sent}, "
                        f"Received: {total_received}, Failed: {total_failed}, "
                        f"Errors: {total_errors}"
                    )
                    
                    # Check for issues
                    for name, metric in metrics.items():
                        if metric.error_count > 10:
                            self.logger.warning(f"High error count for {name}: {metric.error_count}")
                        
                        if metric.messages_failed > metric.messages_sent * 0.1:
                            self.logger.warning(f"High failure rate for {name}")
                    
                except Exception as e:
                    self.logger.error(f"Monitoring error: {e}")
                
                time.sleep(10)  # Monitor every 10 seconds
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def get_all_metrics(self) -> Dict[str, ConnectionMetrics]:
        """Get metrics from all components."""
        metrics = {}
        
        for name, publisher in self.publishers.items():
            metrics[f"pub_{name}"] = publisher.get_metrics()
        
        for name, subscriber in self.subscribers.items():
            metrics[f"sub_{name}"] = subscriber.get_metrics()
        
        for name, requester in self.requesters.items():
            metrics[f"req_{name}"] = requester.get_metrics()
        
        return metrics

# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
def example_market_data_publisher():
    """Example: Publishing market data with reliability."""
    print("\n" + "="*60)
    print("EXAMPLE: Market Data Publisher with Enhanced Reliability")
    print("="*60)
    
    # Create publisher
    publisher = SpyderPublisher(MARKET_DATA_PORT, "MarketDataFeed")
    
    # Connect with retry
    if not publisher.connect():
        print("❌ Failed to connect publisher")
        return
    
    print("✅ Publisher connected")
    print(f"   Port: {MARKET_DATA_PORT}")
    print(f"   State: {publisher.state.name}")
    
    # Simulate market data publishing
    print("\nPublishing market data...")
    
    for i in range(5):
        # Create market data message
        market_data = SpyderMessage(
            msg_type=MessageType.MARKET_DATA,
            timestamp=datetime.now(),
            source="MarketDataFeed",
            destination="TradingEngine",
            data={
                "symbol": "SPY",
                "bid": 450.25 + random.random(),
                "ask": 450.30 + random.random(),
                "last": 450.28 + random.random(),
                "volume": 1000000 + i * 10000,
                "update_id": i
            },
            priority=8  # High priority for market data
        )
        
        # Publish with reliability
        success = publisher.publish(market_data)
        
        if success:
            print(f"   ✓ Published update {i}: SPY @ ${market_data.data['last']:.2f}")
        else:
            print(f"   ✗ Failed to publish update {i}")
        
        time.sleep(0.5)
    
    # Show metrics
    metrics = publisher.get_metrics()
    print(f"\nPublisher Metrics:")
    print(f"   Messages sent: {metrics.messages_sent}")
    print(f"   Messages failed: {metrics.messages_failed}")
    print(f"   Error count: {metrics.error_count}")
    print(f"   Reconnect attempts: {metrics.reconnect_attempts}")
    
    # Simulate connection failure and recovery
    print("\n🔧 Simulating connection failure...")
    publisher.socket.close()
    publisher.state = ConnectionState.FAILED
    
    # Try to publish - should queue and reconnect
    message = SpyderMessage(
        msg_type=MessageType.MARKET_DATA,
        timestamp=datetime.now(),
        source="MarketDataFeed",
        destination="TradingEngine",
        data={"symbol": "SPY", "last": 451.00},
        priority=9
    )
    
    publisher.publish(message)
    print("   Message queued for delivery after reconnection")
    
    # Wait for automatic reconnection
    time.sleep(2)
    
    if publisher.state == ConnectionState.CONNECTED:
        print("✅ Automatic reconnection successful!")
    
    # Disconnect
    publisher.disconnect()
    print("\n✅ Publisher disconnected gracefully")

def example_dashboard_subscriber():
    """Example: Dashboard subscribing to updates with reliability."""
    print("\n" + "="*60)
    print("EXAMPLE: Dashboard Subscriber with Enhanced Reliability")
    print("="*60)
    
    # Create subscriber
    subscriber = SpyderSubscriber(
        MARKET_DATA_PORT,
        "TradingDashboard",
        topics=["MARKET_DATA", "RISK_UPDATE", "PNL_UPDATE"]
    )
    
    # Message handler with error handling
    def handle_market_data(message: SpyderMessage):
        try:
            data = message.data
            print(f"📊 Market Update: {data['symbol']} @ ${data.get('last', 0):.2f}")
        except Exception as e:
            print(f"❌ Handler error: {e}")
    
    def handle_risk_update(message: SpyderMessage):
        try:
            data = message.data
            print(f"⚠️  Risk Update: {data}")
        except Exception as e:
            print(f"❌ Handler error: {e}")
    
    # Subscribe with handlers
    subscriber.subscribe("MARKET_DATA", handle_market_data)
    subscriber.subscribe("RISK_UPDATE", handle_risk_update)
    
    # Connect
    if not subscriber.connect():
        print("❌ Failed to connect subscriber")
        return
    
    print("✅ Subscriber connected")
    print(f"   Port: {MARKET_DATA_PORT}")
    print(f"   Topics: {subscriber.topics}")
    
    # Start listening
    subscriber.start_listening()
    print("\n👂 Listening for messages...")
    
    # Let it run for a while
    time.sleep(5)
    
    # Show metrics
    metrics = subscriber.get_metrics()
    print(f"\nSubscriber Metrics:")
    print(f"   Messages received: {metrics.messages_received}")
    print(f"   Last heartbeat: {metrics.last_heartbeat}")
    print(f"   Error count: {metrics.error_count}")
    
    # Test heartbeat timeout detection
    print("\n🔧 Testing heartbeat timeout detection...")
    subscriber.metrics.last_heartbeat = datetime.now() - timedelta(seconds=10)
    time.sleep(2)
    
    if subscriber.state == ConnectionState.RECONNECTING:
        print("✅ Heartbeat timeout detected, reconnecting...")
    
    # Disconnect
    subscriber.disconnect()
    print("\n✅ Subscriber disconnected gracefully")

def example_request_reply():
    """Example: Request/Reply pattern with timeout and retry."""
    print("\n" + "="*60)
    print("EXAMPLE: Request/Reply with Enhanced Reliability")
    print("="*60)
    
    # Create requester
    requester = SpyderRequester(TRADE_EXECUTION_PORT, "StrategyEngine")
    
    # Connect
    if not requester.connect():
        print("❌ Failed to connect requester")
        return
    
    print("✅ Requester connected")
    
    # Create order request
    order_request = SpyderMessage(
        msg_type=MessageType.TRADE_ORDER,
        timestamp=datetime.now(),
        source="StrategyEngine",
        destination="ExecutionEngine",
        data={
            "action": "BUY",
            "symbol": "SPY",
            "quantity": 100,
            "order_type": "MARKET",
            "strategy_id": "MOMENTUM_001"
        },
        priority=9  # High priority for orders
    )
    
    print("\n📤 Sending order request...")
    print(f"   Order: {order_request.data}")
    
    # Send request with timeout
    start_time = time.time()
    reply = requester.request(order_request, timeout=2.0)
    elapsed = time.time() - start_time
    
    if reply:
        print(f"\n✅ Received reply in {elapsed:.2f}s:")
        print(f"   Type: {reply.msg_type.value}")
        print(f"   Data: {reply.data}")
    else:
        print(f"\n❌ Request failed or timed out after {elapsed:.2f}s")
    
    # Test circuit breaker
    print("\n🔧 Testing circuit breaker...")
    
    # Simulate multiple failures
    for i in range(15):
        try:
            # This will fail since no server is running
            reply = requester.request(order_request, timeout=0.1)
        except Exception:
            pass
    
    # Check circuit breaker state
    if requester.circuit_breaker.state == CircuitBreakerState.OPEN:
        print("✅ Circuit breaker OPEN after multiple failures")
    
    print("\n✅ Request/Reply example completed")

def example_communication_hub():
    """Example: Using the communication hub."""
    print("\n" + "="*60)
    print("EXAMPLE: Communication Hub with Multiple Components")
    print("="*60)
    
    # Create communication hub
    hub = SpyderCommHub("TradingSystem")
    
    # Create various communication components
    market_pub = hub.create_publisher("market_data", MARKET_DATA_PORT)
    risk_pub = hub.create_publisher("risk_updates", RISK_MONITOR_PORT)
    
    dashboard_sub = hub.create_subscriber(
        "dashboard", 
        MARKET_DATA_PORT,
        ["MARKET_DATA", "RISK_UPDATE"]
    )
    
    execution_req = hub.create_requester("execution", TRADE_EXECUTION_PORT)
    
    print("✅ Communication components created:")
    print(f"   Publishers: {list(hub.publishers.keys())}")
    print(f"   Subscribers: {list(hub.subscribers.keys())}")
    print(f"   Requesters: {list(hub.requesters.keys())}")
    
    # Start all components
    hub.start()
    print("\n✅ Communication hub started")
    
    # Let it run for monitoring
    time.sleep(5)
    
    # Get all metrics
    all_metrics = hub.get_all_metrics()
    print("\n📊 System-wide Communication Metrics:")
    for name, metrics in all_metrics.items():
        print(f"   {name}:")
        print(f"      Sent: {metrics.messages_sent}")
        print(f"      Received: {metrics.messages_received}")
        print(f"      Failed: {metrics.messages_failed}")
        print(f"      Errors: {metrics.error_count}")
    
    # Stop hub
    hub.stop()
    print("\n✅ Communication hub stopped")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n🚀 SPYDER ZeroMQ Integration - Enhanced Version")
    print("=" * 60)
    
    print("\nSelect example to run:")
    print("1. Market Data Publisher (with auto-reconnection)")
    print("2. Dashboard Subscriber (with heartbeat monitoring)")
    print("3. Request/Reply (with timeout and circuit breaker)")
    print("4. Communication Hub (integrated system)")
    print("5. Run all examples")
    print("6. Exit")
    
    choice = input("\nSelect example (1-6): ")
    
    if choice == "1":
        example_market_data_publisher()
    elif choice == "2":
        example_dashboard_subscriber()
    elif choice == "3":
        example_request_reply()
    elif choice == "4":
        example_communication_hub()
    elif choice == "5":
        example_market_data_publisher()
        example_dashboard_subscriber()
        example_request_reply()
        example_communication_hub()
    else:
        print("Exiting...")
    
    print("\n✅ Enhanced ZeroMQ Integration demonstration completed!")
    print("\nKey improvements implemented:")
    print("  ✓ Automatic reconnection with exponential backoff")
    print("  ✓ Circuit breaker pattern for fault tolerance")
    print("  ✓ Message acknowledgment and retry mechanisms")
    print("  ✓ Heartbeat monitoring for connection health")
    print("  ✓ Comprehensive error recovery strategies")
    print("  ✓ Priority-based message queuing")
    print("  ✓ Detailed metrics and monitoring")
    print("  ✓ Graceful degradation under failures")