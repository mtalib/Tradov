#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderZ03_TradingCoordinator.py
Group: Z (Communication Infrastructure)
Purpose: DEALER/ROUTER pattern implementation for multi-strategy coordination

Description:
    This module implements a central trading coordinator using ZeroMQ's DEALER/ROUTER
    pattern. It manages communication between the GUI dashboard and multiple trading
    engines (volatility, anomaly detection, auto-hedging). The coordinator routes
    commands, aggregates responses, monitors process health, and enforces system-wide
    risk limits.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 15:45:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import threading
import multiprocessing as mp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import logging
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import zmq
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderZ01_ZeroMQIntegration import (
    SpyderMessage, MessageType, SpyderCommHub,
    TRADE_EXECUTION_PORT, RISK_MONITOR_PORT, STRATEGY_PORT
)
from SpyderZ02_MessageProtocol import (
    MessageCategory, MessageFactory, ProtocolManager,
    SystemStatusMessage, HeartbeatMessage, RiskLimitMessage,
    PortfolioGreeksMessage, SerializationFormat
)
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Router ports
COORDINATOR_ROUTER_PORT = 6000
COORDINATOR_PUB_PORT = 6001
COORDINATOR_MONITOR_PORT = 6002

# Engine ports (DEALER clients will connect to these)
VOL_ENGINE_PORT = 6010
ANOMALY_ENGINE_PORT = 6011
HEDGE_ENGINE_PORT = 6012

# Timing constants
HEARTBEAT_INTERVAL = 1.0  # seconds
HEARTBEAT_TIMEOUT = 5.0   # seconds
COMMAND_TIMEOUT = 3.0     # seconds
HEALTH_CHECK_INTERVAL = 2.0

# System limits
MAX_PENDING_COMMANDS = 1000
MAX_MESSAGE_QUEUE_SIZE = 10000

# ==============================================================================
# ENUMS
# ==============================================================================
class EngineType(Enum):
    """Types of trading engines managed by coordinator."""
    VOLATILITY = "VOLATILITY_ENGINE"
    ANOMALY = "ANOMALY_DETECTOR"
    HEDGER = "AUTO_HEDGER"
    EXECUTION = "EXECUTION_ENGINE"
    DATA_FEED = "DATA_FEED"

class CommandType(Enum):
    """Command types for engine control."""
    START = "START"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CONFIGURE = "CONFIGURE"
    STATUS = "STATUS"
    CALCULATE = "CALCULATE"
    SUBSCRIBE = "SUBSCRIBE"
    UNSUBSCRIBE = "UNSUBSCRIBE"

class CoordinatorState(Enum):
    """Coordinator operational states."""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()
    SHUTTING_DOWN = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class EngineInfo:
    """Information about a connected engine."""
    engine_type: EngineType
    engine_id: str
    identity: bytes  # ZMQ identity
    last_heartbeat: float = 0.0
    status: str = "UNKNOWN"
    capabilities: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def is_alive(self, timeout: float = HEARTBEAT_TIMEOUT) -> bool:
        """Check if engine is alive based on heartbeat."""
        return (time.time() - self.last_heartbeat) < timeout

@dataclass
class PendingCommand:
    """Track pending commands sent to engines."""
    command_id: str
    command_type: CommandType
    target_engine: str
    timestamp: float
    timeout: float
    callback: Optional[Callable] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class SystemMetrics:
    """System-wide performance metrics."""
    total_messages: int = 0
    messages_per_second: float = 0.0
    active_engines: int = 0
    pending_commands: int = 0
    error_count: int = 0
    last_update: float = field(default_factory=time.time)
    
    def update_rate(self, new_messages: int):
        """Update message rate calculation."""
        now = time.time()
        elapsed = now - self.last_update
        if elapsed > 0:
            self.messages_per_second = new_messages / elapsed
        self.total_messages += new_messages
        self.last_update = now

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradingCoordinator:
    """
    Central trading coordinator using DEALER/ROUTER pattern.
    
    This class manages all trading engines, routes commands, aggregates
    responses, and monitors system health. It acts as the central nervous
    system for the SPYDER trading platform.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        state: Current coordinator state
        engines: Dictionary of connected engines
        pending_commands: Queue of commands awaiting responses
        
    Example:
        >>> coordinator = TradingCoordinator()
        >>> coordinator.initialize()
        >>> coordinator.start()
    """
    
    def __init__(self):
        """Initialize the trading coordinator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.state = CoordinatorState.INITIALIZING
        
        # ZeroMQ context and sockets
        self.context = zmq.Context()
        self.router_socket = None  # ROUTER for command routing
        self.pub_socket = None     # PUB for broadcasting updates
        self.monitor_socket = None # REP for monitoring/control
        
        # Protocol manager
        self.protocol = ProtocolManager(SerializationFormat.MSGPACK)
        
        # Engine management
        self.engines: Dict[str, EngineInfo] = {}
        self.engine_lock = threading.Lock()
        
        # Command tracking
        self.pending_commands: Dict[str, PendingCommand] = {}
        self.command_results: Dict[str, Any] = {}
        
        # Metrics and monitoring
        self.metrics = SystemMetrics()
        self.message_history = deque(maxlen=1000)
        
        # Risk limits
        self.risk_limits = {
            'max_position_delta': 1000.0,
            'max_portfolio_vega': 5000.0,
            'max_daily_loss': 10000.0,
            'max_order_size': 100
        }
        
        # Threads
        self.router_thread = None
        self.monitor_thread = None
        self.health_thread = None
        self.running = False
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize coordinator components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Create ROUTER socket for engine communication
            self.router_socket = self.context.socket(zmq.ROUTER)
            self.router_socket.bind(f"tcp://*:{COORDINATOR_ROUTER_PORT}")
            
            # Create PUB socket for broadcasting
            self.pub_socket = self.context.socket(zmq.PUB)
            self.pub_socket.bind(f"tcp://*:{COORDINATOR_PUB_PORT}")
            
            # Create REP socket for monitoring
            self.monitor_socket = self.context.socket(zmq.REP)
            self.monitor_socket.bind(f"tcp://*:{COORDINATOR_MONITOR_PORT}")
            
            # Allow time for bindings
            time.sleep(0.5)
            
            self.state = CoordinatorState.READY
            self.logger.info("Coordinator initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.state = CoordinatorState.ERROR
            return False
    
    def start(self) -> None:
        """Start the coordinator threads."""
        if self.state != CoordinatorState.READY:
            self.logger.warning(f"Cannot start from state: {self.state}")
            return
            
        self.running = True
        self.state = CoordinatorState.RUNNING
        
        # Start router thread
        self.router_thread = threading.Thread(
            target=self._router_loop,
            name="RouterThread",
            daemon=True
        )
        self.router_thread.start()
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="MonitorThread",
            daemon=True
        )
        self.monitor_thread.start()
        
        # Start health check thread
        self.health_thread = threading.Thread(
            target=self._health_check_loop,
            name="HealthThread",
            daemon=True
        )
        self.health_thread.start()
        
        self.logger.info("Coordinator started")
        
    def stop(self) -> None:
        """Stop the coordinator."""
        if self.state != CoordinatorState.RUNNING:
            self.logger.warning(f"Cannot stop from state: {self.state}")
            return
            
        self.state = CoordinatorState.SHUTTING_DOWN
        self.running = False
        
        # Send shutdown commands to all engines
        self._broadcast_shutdown()
        
        # Wait for threads to finish
        if self.router_thread:
            self.router_thread.join(timeout=2.0)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        if self.health_thread:
            self.health_thread.join(timeout=2.0)
            
        # Close sockets
        if self.router_socket:
            self.router_socket.close()
        if self.pub_socket:
            self.pub_socket.close()
        if self.monitor_socket:
            self.monitor_socket.close()
            
        self.context.term()
        
        self.logger.info("Coordinator stopped")
        
    def send_command(self, engine_type: EngineType, command_type: CommandType,
                    data: Dict[str, Any], callback: Optional[Callable] = None) -> str:
        """
        Send command to a specific engine type.
        
        Args:
            engine_type: Type of engine to target
            command_type: Command to send
            data: Command data
            callback: Optional callback for response
            
        Returns:
            Command ID for tracking
        """
        command_id = str(uuid.uuid4())
        
        # Find available engine of the requested type
        target_engine = self._find_engine(engine_type)
        if not target_engine:
            self.logger.error(f"No available engine of type {engine_type}")
            return ""
            
        # Create command message
        command_msg = {
            'command_id': command_id,
            'command_type': command_type.value,
            'data': data,
            'timestamp': time.time()
        }
        
        # Track pending command
        pending = PendingCommand(
            command_id=command_id,
            command_type=command_type,
            target_engine=target_engine.engine_id,
            timestamp=time.time(),
            timeout=COMMAND_TIMEOUT,
            callback=callback
        )
        self.pending_commands[command_id] = pending
        
        # Send via router
        self._route_command(target_engine.identity, command_msg)
        
        return command_id
        
    def broadcast_market_update(self, data: Dict[str, Any]) -> None:
        """
        Broadcast market data update to all engines.
        
        Args:
            data: Market data to broadcast
        """
        msg = self.protocol.create_message(
            MessageCategory.MARKET,
            "MARKET_UPDATE",
            data,
            source="COORDINATOR"
        )
        
        serialized = self.protocol.serialize_message(msg)
        self.pub_socket.send(b"MARKET|" + serialized)
        
        self.metrics.total_messages += 1
        
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            System status dictionary
        """
        with self.engine_lock:
            engine_status = {
                engine_id: {
                    'type': info.engine_type.value,
                    'status': info.status,
                    'alive': info.is_alive(),
                    'last_heartbeat': datetime.fromtimestamp(info.last_heartbeat).isoformat(),
                    'metrics': info.metrics
                }
                for engine_id, info in self.engines.items()
            }
            
        return {
            'state': self.state.name,
            'engines': engine_status,
            'metrics': {
                'total_messages': self.metrics.total_messages,
                'messages_per_second': self.metrics.messages_per_second,
                'active_engines': self.metrics.active_engines,
                'pending_commands': len(self.pending_commands),
                'error_count': self.metrics.error_count
            },
            'risk_limits': self.risk_limits,
            'timestamp': datetime.now().isoformat()
        }
        
    # ==========================================================================
    # PRIVATE METHODS - MAIN LOOPS
    # ==========================================================================
    def _router_loop(self) -> None:
        """Main ROUTER socket processing loop."""
        poller = zmq.Poller()
        poller.register(self.router_socket, zmq.POLLIN)
        
        while self.running:
            try:
                # Poll with timeout
                socks = dict(poller.poll(100))
                
                if self.router_socket in socks:
                    # Receive multipart message
                    frames = self.router_socket.recv_multipart()
                    
                    if len(frames) >= 3:
                        identity = frames[0]
                        empty = frames[1]  # Empty delimiter frame
                        message = frames[2]
                        
                        # Process the message
                        self._process_router_message(identity, message)
                        
            except Exception as e:
                self.logger.error(f"Router loop error: {e}")
                self.error_handler.handle_error(e, {"context": "router_loop"})
                
    def _monitor_loop(self) -> None:
        """Monitor socket processing loop for external queries."""
        poller = zmq.Poller()
        poller.register(self.monitor_socket, zmq.POLLIN)
        
        while self.running:
            try:
                socks = dict(poller.poll(100))
                
                if self.monitor_socket in socks:
                    request = self.monitor_socket.recv_json()
                    
                    # Process monitoring request
                    response = self._process_monitor_request(request)
                    
                    # Send response
                    self.monitor_socket.send_json(response)
                    
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                
    def _health_check_loop(self) -> None:
        """Periodic health check of all engines."""
        next_check = time.time()
        
        while self.running:
            try:
                now = time.time()
                
                if now >= next_check:
                    self._check_engine_health()
                    self._check_pending_commands()
                    self._update_metrics()
                    
                    next_check = now + HEALTH_CHECK_INTERVAL
                    
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                
    # ==========================================================================
    # PRIVATE METHODS - MESSAGE PROCESSING
    # ==========================================================================
    def _process_router_message(self, identity: bytes, message: bytes) -> None:
        """Process message received on ROUTER socket."""
        try:
            # Deserialize message
            msg_dict = json.loads(message.decode('utf-8'))
            msg_type = msg_dict.get('type', '')
            
            # Handle different message types
            if msg_type == 'REGISTER':
                self._handle_registration(identity, msg_dict)
                
            elif msg_type == 'HEARTBEAT':
                self._handle_heartbeat(identity, msg_dict)
                
            elif msg_type == 'RESPONSE':
                self._handle_command_response(identity, msg_dict)
                
            elif msg_type == 'EVENT':
                self._handle_engine_event(identity, msg_dict)
                
            else:
                self.logger.warning(f"Unknown message type: {msg_type}")
                
            # Update metrics
            self.metrics.total_messages += 1
            
        except Exception as e:
            self.logger.error(f"Message processing error: {e}")
            
    def _handle_registration(self, identity: bytes, data: Dict) -> None:
        """Handle engine registration."""
        engine_type = EngineType(data['engine_type'])
        engine_id = data['engine_id']
        
        # Create engine info
        engine_info = EngineInfo(
            engine_type=engine_type,
            engine_id=engine_id,
            identity=identity,
            last_heartbeat=time.time(),
            status='REGISTERED',
            capabilities=data.get('capabilities', [])
        )
        
        # Store engine
        with self.engine_lock:
            self.engines[engine_id] = engine_info
            self.metrics.active_engines = len(self.engines)
            
        self.logger.info(f"Engine registered: {engine_id} ({engine_type.value})")
        
        # Send acknowledgment
        ack = {
            'type': 'REGISTRATION_ACK',
            'status': 'SUCCESS',
            'coordinator_time': time.time()
        }
        self.router_socket.send_multipart([identity, b'', json.dumps(ack).encode()])
        
        # Broadcast registration event
        self._broadcast_engine_status(engine_id, 'REGISTERED')
        
    def _handle_heartbeat(self, identity: bytes, data: Dict) -> None:
        """Handle engine heartbeat."""
        engine_id = data.get('engine_id')
        
        with self.engine_lock:
            if engine_id in self.engines:
                engine = self.engines[engine_id]
                engine.last_heartbeat = time.time()
                engine.status = data.get('status', 'HEALTHY')
                engine.metrics = data.get('metrics', {})
                
    def _handle_command_response(self, identity: bytes, data: Dict) -> None:
        """Handle response to a command."""
        command_id = data.get('command_id')
        
        if command_id in self.pending_commands:
            pending = self.pending_commands[command_id]
            
            # Store result
            self.command_results[command_id] = data.get('result')
            
            # Execute callback if provided
            if pending.callback:
                try:
                    pending.callback(data.get('result'))
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
                    
            # Remove from pending
            del self.pending_commands[command_id]
            
            self.logger.debug(f"Command {command_id} completed")
            
    def _handle_engine_event(self, identity: bytes, data: Dict) -> None:
        """Handle event from engine (alerts, updates, etc)."""
        event_type = data.get('event_type')
        
        # Map to appropriate message category
        if event_type == 'RISK_ALERT':
            self._process_risk_alert(data)
        elif event_type == 'GREEK_UPDATE':
            self._process_greek_update(data)
        elif event_type == 'ANOMALY_DETECTED':
            self._process_anomaly(data)
        else:
            # Forward as generic event
            self._broadcast_engine_event(data)
            
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _find_engine(self, engine_type: EngineType) -> Optional[EngineInfo]:
        """Find an available engine of the specified type."""
        with self.engine_lock:
            for engine in self.engines.values():
                if engine.engine_type == engine_type and engine.is_alive():
                    return engine
        return None
        
    def _route_command(self, identity: bytes, command: Dict) -> None:
        """Route command to specific engine."""
        message = json.dumps(command).encode('utf-8')
        self.router_socket.send_multipart([identity, b'', message])
        
    def _check_engine_health(self) -> None:
        """Check health of all registered engines."""
        with self.engine_lock:
            dead_engines = []
            
            for engine_id, engine in self.engines.items():
                if not engine.is_alive():
                    dead_engines.append(engine_id)
                    self.logger.warning(f"Engine {engine_id} appears dead")
                    
            # Remove dead engines
            for engine_id in dead_engines:
                del self.engines[engine_id]
                self._broadcast_engine_status(engine_id, 'DISCONNECTED')
                
            self.metrics.active_engines = len(self.engines)
            
    def _check_pending_commands(self) -> None:
        """Check for timed out commands."""
        now = time.time()
        timed_out = []
        
        for cmd_id, pending in self.pending_commands.items():
            if now - pending.timestamp > pending.timeout:
                timed_out.append(cmd_id)
                
        # Handle timeouts
        for cmd_id in timed_out:
            pending = self.pending_commands[cmd_id]
            
            if pending.retry_count < pending.max_retries:
                # Retry command
                pending.retry_count += 1
                pending.timestamp = now
                self.logger.warning(f"Retrying command {cmd_id} (attempt {pending.retry_count})")
                
                # Re-route command
                engine = self._find_engine_by_id(pending.target_engine)
                if engine:
                    command_msg = {
                        'command_id': cmd_id,
                        'command_type': pending.command_type.value,
                        'timestamp': now,
                        'retry': pending.retry_count
                    }
                    self._route_command(engine.identity, command_msg)
            else:
                # Max retries exceeded
                self.logger.error(f"Command {cmd_id} failed after {pending.max_retries} retries")
                
                if pending.callback:
                    pending.callback({'error': 'Command timeout'})
                    
                del self.pending_commands[cmd_id]
                self.metrics.error_count += 1
                
    def _find_engine_by_id(self, engine_id: str) -> Optional[EngineInfo]:
        """Find engine by ID."""
        with self.engine_lock:
            return self.engines.get(engine_id)
            
    def _update_metrics(self) -> None:
        """Update system metrics."""
        # Calculate message rate
        current_messages = self.metrics.total_messages
        self.metrics.update_rate(0)  # Just update timestamp
        
        # Broadcast metrics
        metrics_msg = SystemStatusMessage(
            component="COORDINATOR",
            status="HEALTHY" if self.state == CoordinatorState.RUNNING else "DEGRADED",
            message=f"Active engines: {self.metrics.active_engines}",
            timestamp=time.time()
        )
        
        msg = self.protocol.factory.create_message(
            MessageCategory.SYSTEM,
            "METRICS_UPDATE",
            asdict(metrics_msg),
            source="COORDINATOR"
        )
        
        self.pub_socket.send(b"SYSTEM|" + self.protocol.serialize_message(msg))
        
    def _broadcast_shutdown(self) -> None:
        """Broadcast shutdown command to all engines."""
        shutdown_msg = {
            'type': 'COMMAND',
            'command_type': CommandType.STOP.value,
            'timestamp': time.time()
        }
        
        with self.engine_lock:
            for engine in self.engines.values():
                self._route_command(engine.identity, shutdown_msg)
                
    def _broadcast_engine_status(self, engine_id: str, status: str) -> None:
        """Broadcast engine status change."""
        status_msg = {
            'engine_id': engine_id,
            'status': status,
            'timestamp': time.time()
        }
        
        msg = self.protocol.create_message(
            MessageCategory.SYSTEM,
            "ENGINE_STATUS",
            status_msg,
            source="COORDINATOR"
        )
        
        self.pub_socket.send(b"SYSTEM|" + self.protocol.serialize_message(msg))
        
    def _broadcast_engine_event(self, event_data: Dict) -> None:
        """Broadcast generic engine event."""
        msg = self.protocol.create_message(
            MessageCategory.SYSTEM,
            "ENGINE_EVENT",
            event_data,
            source="COORDINATOR"
        )
        
        self.pub_socket.send(b"EVENT|" + self.protocol.serialize_message(msg))
        
    def _process_risk_alert(self, data: Dict) -> None:
        """Process risk alert from engine."""
        # Create risk limit message
        risk_msg = RiskLimitMessage(
            limit_type=data.get('limit_type', 'UNKNOWN'),
            current_value=data.get('current_value', 0),
            limit_value=data.get('limit_value', 0),
            severity=data.get('severity', 'WARNING'),
            action_required=data.get('action', 'Review position')
        )
        
        # Check against coordinator's risk limits
        if self._validate_risk_limit(risk_msg):
            # Broadcast validated alert
            msg = self.protocol.factory.create_message(
                MessageCategory.RISK,
                "RISK_ALERT",
                asdict(risk_msg),
                source="COORDINATOR"
            )
            
            self.pub_socket.send(b"RISK|" + self.protocol.serialize_message(msg))
            
            # Log critical alerts
            if risk_msg.severity == "CRITICAL":
                self.logger.error(f"CRITICAL RISK ALERT: {risk_msg.limit_type} = {risk_msg.current_value}")
                
    def _process_greek_update(self, data: Dict) -> None:
        """Process Greek update from volatility engine."""
        # Forward to subscribers
        msg = self.protocol.create_message(
            MessageCategory.RISK,
            "GREEK_UPDATE",
            data,
            source="COORDINATOR"
        )
        
        self.pub_socket.send(b"RISK|" + self.protocol.serialize_message(msg))
        
    def _process_anomaly(self, data: Dict) -> None:
        """Process anomaly detection event."""
        # Evaluate severity and take action
        severity = data.get('severity', 'LOW')
        
        if severity in ['HIGH', 'CRITICAL']:
            # May need to pause trading
            self.logger.warning(f"High severity anomaly detected: {data.get('description')}")
            
            # Notify all engines
            alert_cmd = {
                'command_type': CommandType.PAUSE.value,
                'reason': 'Anomaly detected',
                'data': data
            }
            
            with self.engine_lock:
                for engine in self.engines.values():
                    if engine.engine_type == EngineType.EXECUTION:
                        self._route_command(engine.identity, alert_cmd)
                        
        # Broadcast anomaly event
        msg = self.protocol.create_message(
            MessageCategory.ALERT,
            "ANOMALY_DETECTED",
            data,
            source="COORDINATOR"
        )
        
        self.pub_socket.send(b"ALERT|" + self.protocol.serialize_message(msg))
        
    def _validate_risk_limit(self, risk_msg: RiskLimitMessage) -> bool:
        """Validate risk limit against coordinator limits."""
        limit_type = risk_msg.limit_type
        
        # Map to internal limits
        if limit_type == "MAX_DELTA":
            return abs(risk_msg.current_value) <= self.risk_limits['max_position_delta']
        elif limit_type == "MAX_VEGA":
            return abs(risk_msg.current_value) <= self.risk_limits['max_portfolio_vega']
        elif limit_type == "DAILY_LOSS":
            return abs(risk_msg.current_value) <= self.risk_limits['max_daily_loss']
            
        return True  # Unknown limits pass through
        
    def _process_monitor_request(self, request: Dict) -> Dict:
        """Process monitoring/control request."""
        request_type = request.get('type', '')
        
        if request_type == 'STATUS':
            return self.get_system_status()
            
        elif request_type == 'SET_LIMIT':
            # Update risk limit
            limit_name = request.get('limit_name')
            limit_value = request.get('limit_value')
            
            if limit_name in self.risk_limits:
                old_value = self.risk_limits[limit_name]
                self.risk_limits[limit_name] = limit_value
                
                return {
                    'status': 'SUCCESS',
                    'old_value': old_value,
                    'new_value': limit_value
                }
            else:
                return {'status': 'ERROR', 'message': 'Unknown limit'}
                
        elif request_type == 'ENGINE_COMMAND':
            # Forward command to engine
            engine_type = EngineType(request.get('engine_type'))
            command_type = CommandType(request.get('command_type'))
            
            cmd_id = self.send_command(
                engine_type,
                command_type,
                request.get('data', {})
            )
            
            return {'status': 'SUCCESS', 'command_id': cmd_id}
            
        else:
            return {'status': 'ERROR', 'message': 'Unknown request type'}
            
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up coordinator resources."""
        self.stop()
        self.logger.info("Coordinator cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_engine_client(engine_type: EngineType, engine_id: str) -> zmq.Socket:
    """
    Create a DEALER socket for engine to connect to coordinator.
    
    Args:
        engine_type: Type of engine
        engine_id: Unique engine identifier
        
    Returns:
        Configured DEALER socket
    """
    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    
    # Set identity for routing
    socket.identity = f"{engine_type.value}:{engine_id}".encode('utf-8')
    
    # Connect to coordinator
    socket.connect(f"tcp://localhost:{COORDINATOR_ROUTER_PORT}")
    
    # Send registration
    registration = {
        'type': 'REGISTER',
        'engine_type': engine_type.value,
        'engine_id': engine_id,
        'capabilities': [],
        'timestamp': time.time()
    }
    
    socket.send_json(registration)
    
    return socket

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_coordinator_instance: Optional[TradingCoordinator] = None

def get_coordinator_instance() -> TradingCoordinator:
    """
    Get singleton instance of the trading coordinator.
    
    Returns:
        TradingCoordinator instance
    """
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = TradingCoordinator()
    return _coordinator_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    import signal
    
    coordinator = TradingCoordinator()
    
    # Handle shutdown gracefully
    def signal_handler(sig, frame):
        print("\nShutting down coordinator...")
        coordinator.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    if coordinator.initialize():
        print("✅ Trading Coordinator initialized")
        
        # Start coordinator
        coordinator.start()
        print("✅ Trading Coordinator started")
        print(f"   ROUTER port: {COORDINATOR_ROUTER_PORT}")
        print(f"   PUB port: {COORDINATOR_PUB_PORT}")
        print(f"   Monitor port: {COORDINATOR_MONITOR_PORT}")
        
        # Print status periodically
        try:
            while True:
                time.sleep(5)
                status = coordinator.get_system_status()
                print(f"\nStatus: {status['state']}")
                print(f"Active engines: {status['metrics']['active_engines']}")
                print(f"Total messages: {status['metrics']['total_messages']}")
                print(f"Pending commands: {status['metrics']['pending_commands']}")
                
        except KeyboardInterrupt:
            pass
            
    else:
        print("❌ Coordinator initialization failed")
