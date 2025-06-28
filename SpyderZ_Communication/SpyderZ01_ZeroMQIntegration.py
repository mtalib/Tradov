#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderZ01_ZeroMQIntegration.py
Group: Z (ZeroMQ Communication Layer)
Purpose: High-performance IPC for distributed SPYDER components

Description:
    This module implements ZeroMQ-based communication for SPYDER, enabling
    high-performance inter-process communication between different system
    components. It supports multiple messaging patterns for various use cases.

Author: SPYDER Team
Date: 2025-06-28
Version: 1.0
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import zmq
import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default ports for different services
MARKET_DATA_PORT = 5555
TRADE_EXECUTION_PORT = 5556
RISK_MONITOR_PORT = 5557
STRATEGY_PORT = 5558
DASHBOARD_PORT = 5559

# Message types
class MessageType(Enum):
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

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SpyderMessage:
    """Standard message format for SPYDER communication."""
    msg_type: MessageType
    timestamp: datetime
    source: str
    destination: str
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        msg_dict = {
            'msg_type': self.msg_type.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'destination': self.destination,
            'data': self.data,
            'correlation_id': self.correlation_id
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
            correlation_id=msg_dict.get('correlation_id')
        )

# ==============================================================================
# ZEROMQ PUBLISHER (For Market Data & Updates)
# ==============================================================================
class SpyderPublisher:
    """ZeroMQ Publisher for broadcasting data."""
    
    def __init__(self, port: int, component_name: str):
        """Initialize publisher."""
        self.port = port
        self.component_name = component_name
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{port}")
        self.logger = logging.getLogger(f"SpyderPublisher.{component_name}")
        
        # Allow subscribers time to connect
        time.sleep(0.5)
        
    def publish(self, topic: str, message: SpyderMessage):
        """Publish message to topic."""
        try:
            # Topic-based filtering
            topic_msg = f"{topic}|{message.to_json()}"
            self.socket.send_string(topic_msg)
            self.logger.debug(f"Published to {topic}: {message.msg_type.value}")
        except Exception as e:
            self.logger.error(f"Publish error: {e}")
            
    def publish_market_data(self, symbol: str, data: Dict):
        """Publish market data update."""
        msg = SpyderMessage(
            msg_type=MessageType.MARKET_DATA,
            timestamp=datetime.now(),
            source=self.component_name,
            destination="ALL",
            data={'symbol': symbol, **data}
        )
        self.publish(f"MARKET.{symbol}", msg)
        
    def close(self):
        """Clean up resources."""
        self.socket.close()
        self.context.term()

# ==============================================================================
# ZEROMQ SUBSCRIBER (For Receiving Updates)
# ==============================================================================
class SpyderSubscriber:
    """ZeroMQ Subscriber for receiving broadcasts."""
    
    def __init__(self, port: int, component_name: str, topics: List[str] = None):
        """Initialize subscriber."""
        self.port = port
        self.component_name = component_name
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(f"tcp://localhost:{port}")
        self.logger = logging.getLogger(f"SpyderSubscriber.{component_name}")
        
        # Subscribe to topics
        if topics:
            for topic in topics:
                self.socket.subscribe(topic.encode())
        else:
            # Subscribe to all
            self.socket.subscribe(b"")
            
        self.running = False
        self.handlers: Dict[MessageType, List[Callable]] = {}
        
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register message handler."""
        if msg_type not in self.handlers:
            self.handlers[msg_type] = []
        self.handlers[msg_type].append(handler)
        
    def start(self):
        """Start subscriber thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        
    def _run(self):
        """Main subscriber loop."""
        while self.running:
            try:
                # Check for messages with timeout
                if self.socket.poll(100):  # 100ms timeout
                    message = self.socket.recv_string()
                    
                    # Parse topic and message
                    if '|' in message:
                        topic, json_msg = message.split('|', 1)
                        msg = SpyderMessage.from_json(json_msg)
                        
                        # Call handlers
                        if msg.msg_type in self.handlers:
                            for handler in self.handlers[msg.msg_type]:
                                try:
                                    handler(msg)
                                except Exception as e:
                                    self.logger.error(f"Handler error: {e}")
                                    
            except Exception as e:
                self.logger.error(f"Subscriber error: {e}")
                
    def stop(self):
        """Stop subscriber."""
        self.running = False
        self.thread.join()
        self.socket.close()
        self.context.term()

# ==============================================================================
# ZEROMQ REQUEST-REPLY (For Synchronous Communication)
# ==============================================================================
class SpyderClient:
    """ZeroMQ Request client for synchronous calls."""
    
    def __init__(self, port: int, component_name: str, timeout: int = 5000):
        """Initialize client."""
        self.port = port
        self.component_name = component_name
        self.timeout = timeout
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{port}")
        self.socket.setsockopt(zmq.RCVTIMEO, timeout)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.logger = logging.getLogger(f"SpyderClient.{component_name}")
        
    def request(self, message: SpyderMessage) -> Optional[SpyderMessage]:
        """Send request and wait for reply."""
        try:
            self.socket.send_string(message.to_json())
            reply_json = self.socket.recv_string()
            return SpyderMessage.from_json(reply_json)
        except zmq.error.Again:
            self.logger.error(f"Request timeout after {self.timeout}ms")
            # Recreate socket after timeout
            self._recreate_socket()
            return None
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return None
            
    def _recreate_socket(self):
        """Recreate socket after error."""
        self.socket.close()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://localhost:{self.port}")
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout)
        self.socket.setsockopt(zmq.LINGER, 0)
        
    def close(self):
        """Clean up resources."""
        self.socket.close()
        self.context.term()

class SpyderServer:
    """ZeroMQ Reply server for handling requests."""
    
    def __init__(self, port: int, component_name: str):
        """Initialize server."""
        self.port = port
        self.component_name = component_name
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{port}")
        self.logger = logging.getLogger(f"SpyderServer.{component_name}")
        self.running = False
        self.handlers: Dict[MessageType, Callable] = {}
        
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """Register request handler."""
        self.handlers[msg_type] = handler
        
    def start(self):
        """Start server thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        
    def _run(self):
        """Main server loop."""
        while self.running:
            try:
                # Check for requests with timeout
                if self.socket.poll(100):  # 100ms timeout
                    request_json = self.socket.recv_string()
                    request = SpyderMessage.from_json(request_json)
                    
                    # Process request
                    if request.msg_type in self.handlers:
                        try:
                            response = self.handlers[request.msg_type](request)
                            if isinstance(response, SpyderMessage):
                                self.socket.send_string(response.to_json())
                            else:
                                # Create error response
                                error_msg = SpyderMessage(
                                    msg_type=MessageType.ERROR,
                                    timestamp=datetime.now(),
                                    source=self.component_name,
                                    destination=request.source,
                                    data={'error': 'Invalid handler response'},
                                    correlation_id=request.correlation_id
                                )
                                self.socket.send_string(error_msg.to_json())
                        except Exception as e:
                            self.logger.error(f"Handler error: {e}")
                            # Send error response
                            error_msg = SpyderMessage(
                                msg_type=MessageType.ERROR,
                                timestamp=datetime.now(),
                                source=self.component_name,
                                destination=request.source,
                                data={'error': str(e)},
                                correlation_id=request.correlation_id
                            )
                            self.socket.send_string(error_msg.to_json())
                    else:
                        # Unknown message type
                        error_msg = SpyderMessage(
                            msg_type=MessageType.ERROR,
                            timestamp=datetime.now(),
                            source=self.component_name,
                            destination=request.source,
                            data={'error': f'Unknown message type: {request.msg_type}'},
                            correlation_id=request.correlation_id
                        )
                        self.socket.send_string(error_msg.to_json())
                        
            except Exception as e:
                self.logger.error(f"Server error: {e}")
                
    def stop(self):
        """Stop server."""
        self.running = False
        self.thread.join()
        self.socket.close()
        self.context.term()

# ==============================================================================
# SPYDER COMMUNICATION HUB
# ==============================================================================
class SpyderCommHub:
    """Central communication hub for SPYDER components."""
    
    def __init__(self, component_name: str):
        """Initialize communication hub."""
        self.component_name = component_name
        self.logger = logging.getLogger(f"SpyderCommHub.{component_name}")
        
        # Publishers
        self.publishers: Dict[str, SpyderPublisher] = {}
        
        # Subscribers
        self.subscribers: Dict[str, SpyderSubscriber] = {}
        
        # Clients
        self.clients: Dict[str, SpyderClient] = {}
        
        # Servers
        self.servers: Dict[str, SpyderServer] = {}
        
    def create_publisher(self, name: str, port: int) -> SpyderPublisher:
        """Create and store publisher."""
        pub = SpyderPublisher(port, f"{self.component_name}.{name}")
        self.publishers[name] = pub
        return pub
        
    def create_subscriber(self, name: str, port: int, topics: List[str] = None) -> SpyderSubscriber:
        """Create and store subscriber."""
        sub = SpyderSubscriber(port, f"{self.component_name}.{name}", topics)
        self.subscribers[name] = sub
        return sub
        
    def create_client(self, name: str, port: int, timeout: int = 5000) -> SpyderClient:
        """Create and store client."""
        client = SpyderClient(port, f"{self.component_name}.{name}", timeout)
        self.clients[name] = client
        return client
        
    def create_server(self, name: str, port: int) -> SpyderServer:
        """Create and store server."""
        server = SpyderServer(port, f"{self.component_name}.{name}")
        self.servers[name] = server
        return server
        
    def start_all(self):
        """Start all subscribers and servers."""
        for sub in self.subscribers.values():
            sub.start()
        for server in self.servers.values():
            server.start()
            
    def stop_all(self):
        """Stop all components and clean up."""
        # Stop subscribers
        for sub in self.subscribers.values():
            sub.stop()
            
        # Stop servers
        for server in self.servers.values():
            server.stop()
            
        # Close publishers
        for pub in self.publishers.values():
            pub.close()
            
        # Close clients
        for client in self.clients.values():
            client.close()

# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
def example_market_data_publisher():
    """Example: Market data publisher."""
    # Create communication hub
    hub = SpyderCommHub("MarketDataService")
    
    # Create publisher
    publisher = hub.create_publisher("market_data", MARKET_DATA_PORT)
    
    # Simulate market data updates
    symbols = ["SPY", "VIX", "QQQ", "IWM"]
    
    try:
        while True:
            for symbol in symbols:
                # Generate fake market data
                import random
                data = {
                    'bid': round(random.uniform(100, 500), 2),
                    'ask': round(random.uniform(100, 500), 2),
                    'last': round(random.uniform(100, 500), 2),
                    'volume': random.randint(1000000, 10000000)
                }
                
                # Publish update
                publisher.publish_market_data(symbol, data)
                
            time.sleep(1)  # Update every second
            
    except KeyboardInterrupt:
        print("Stopping market data publisher...")
    finally:
        hub.stop_all()

def example_dashboard_subscriber():
    """Example: Dashboard subscriber."""
    # Create communication hub
    hub = SpyderCommHub("Dashboard")
    
    # Create subscriber for market data
    market_sub = hub.create_subscriber("market_data", MARKET_DATA_PORT, ["MARKET.SPY"])
    
    # Define handler
    def handle_market_data(msg: SpyderMessage):
        print(f"Dashboard received: {msg.data['symbol']} - "
              f"Bid: ${msg.data['bid']}, Ask: ${msg.data['ask']}")
    
    # Register handler
    market_sub.register_handler(MessageType.MARKET_DATA, handle_market_data)
    
    # Start subscriber
    hub.start_all()
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping dashboard...")
    finally:
        hub.stop_all()

def example_trade_server():
    """Example: Trade execution server."""
    # Create communication hub
    hub = SpyderCommHub("TradeExecutionService")
    
    # Create server
    server = hub.create_server("trade_execution", TRADE_EXECUTION_PORT)
    
    # Define handler
    def handle_trade_order(request: SpyderMessage) -> SpyderMessage:
        print(f"Processing trade order: {request.data}")
        
        # Simulate order processing
        time.sleep(0.1)
        
        # Return fill confirmation
        return SpyderMessage(
            msg_type=MessageType.TRADE_FILL,
            timestamp=datetime.now(),
            source="TradeExecutionService",
            destination=request.source,
            data={
                'order_id': request.data.get('order_id'),
                'symbol': request.data.get('symbol'),
                'quantity': request.data.get('quantity'),
                'fill_price': 425.50,
                'status': 'FILLED'
            },
            correlation_id=request.correlation_id
        )
    
    # Register handler
    server.register_handler(MessageType.TRADE_ORDER, handle_trade_order)
    
    # Start server
    hub.start_all()
    
    print("Trade execution server running...")
    
    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping trade server...")
    finally:
        hub.stop_all()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("SPYDER ZeroMQ Integration Examples")
    print("==================================")
    print("1. Market Data Publisher")
    print("2. Dashboard Subscriber")
    print("3. Trade Execution Server")
    print("4. Exit")
    
    choice = input("\nSelect example to run (1-4): ")
    
    if choice == "1":
        example_market_data_publisher()
    elif choice == "2":
        example_dashboard_subscriber()
    elif choice == "3":
        example_trade_server()
    else:
        print("Exiting...")