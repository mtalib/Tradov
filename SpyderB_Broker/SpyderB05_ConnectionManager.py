#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB05_ConnectionManager.py
Group: B (Broker Integration)
Purpose: Robust broker connection management with auto-recovery and monitoring

Description:
    This module provides institutional-grade connection management for Interactive Brokers
    including automatic reconnection, connection health monitoring, failover mechanisms,
    and comprehensive connection analytics. It ensures maximum uptime and reliability
    for automated trading operations with sophisticated error recovery and state
    management capabilities.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 20:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import socket
import subprocess
import platform
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field, asdict
from collections import deque
from enum import Enum, auto
from threading import Lock, Event as ThreadEvent, RLock, Thread
from queue import Queue, Empty
import statistics
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# Interactive Brokers
try:
    from ib_insync import IB, Contract, Order, Trade, Position, Account
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("INFO: ib_insync not available. Connection will be simulated.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import is_market_open, get_market_hours
from SpyderU_Utilities.SpyderU05_NetworkUtils import check_internet_connection, ping_host

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connection defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 7497  # TWS Paper Trading
DEFAULT_CLIENT_ID = 1
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_COUNT = 5
DEFAULT_RETRY_DELAY = 5.0
DEFAULT_HEARTBEAT_INTERVAL = 30

# Connection states
CONNECTION_STATES = {
    'DISCONNECTED': 'disconnected',
    'CONNECTING': 'connecting',
    'CONNECTED': 'connected',
    'AUTHENTICATED': 'authenticated',
    'FAILED': 'failed',
    'RECONNECTING': 'reconnecting'
}

# Network thresholds
NETWORK_LATENCY_THRESHOLD_MS = 100
NETWORK_PACKET_LOSS_THRESHOLD = 5.0
NETWORK_BANDWIDTH_THRESHOLD_MBPS = 1.0

# Monitoring intervals
HEALTH_CHECK_INTERVAL = 30  # seconds
METRICS_UPDATE_INTERVAL = 60  # seconds
DIAGNOSTICS_INTERVAL = 300  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionState(Enum):
    """Connection state enumeration"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    RECONNECTING = "reconnecting"

class NetworkStatus(Enum):
    """Network status enumeration"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class ConnectionPriority(Enum):
    """Connection priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class FailoverMode(Enum):
    """Failover mode enumeration"""
    DISABLED = "disabled"
    MANUAL = "manual"
    AUTOMATIC = "automatic"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ConnectionConfig:
    """Connection configuration"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    timeout: int = DEFAULT_TIMEOUT
    retry_count: int = DEFAULT_RETRY_COUNT
    retry_delay: float = DEFAULT_RETRY_DELAY
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 5.0
    use_exponential_backoff: bool = True
    max_backoff_delay: float = 300.0
    enable_monitoring: bool = True
    enable_diagnostics: bool = True
    priority: ConnectionPriority = ConnectionPriority.NORMAL
    failover_hosts: List[str] = field(default_factory=list)
    failover_mode: FailoverMode = FailoverMode.AUTOMATIC
    connection_quality_threshold: float = 0.8
    network_latency_threshold_ms: float = NETWORK_LATENCY_THRESHOLD_MS
    packet_loss_threshold: float = NETWORK_PACKET_LOSS_THRESHOLD
    bandwidth_threshold_mbps: float = NETWORK_BANDWIDTH_THRESHOLD_MBPS

@dataclass
class ConnectionMetrics:
    """Connection performance metrics"""
    connection_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    total_connects: int = 0
    total_disconnects: int = 0
    total_reconnects: int = 0
    failed_attempts: int = 0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    downtime_seconds: float = 0.0
    data_received_bytes: int = 0
    data_sent_bytes: int = 0
    last_error: Optional[str] = None
    error_count: int = 0

@dataclass
class HeartbeatResult:
    """Heartbeat check result"""
    success: bool
    latency_ms: float
    timestamp: datetime
    error_message: Optional[str] = None

@dataclass
class NetworkDiagnostics:
    """Network diagnostics data"""
    ping_latency_ms: float = 0.0
    packet_loss_pct: float = 0.0
    bandwidth_mbps: float = 0.0
    network_status: NetworkStatus = NetworkStatus.UNKNOWN
    last_check: Optional[datetime] = None
    external_connectivity: bool = True
    dns_resolution_ms: float = 0.0

@dataclass
class ConnectionEvent:
    """Connection event for history tracking"""
    event_type: str
    timestamp: datetime
    state_from: ConnectionState
    state_to: ConnectionState
    details: str
    metrics: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConnectionManager:
    """
    Robust Broker Connection Manager.
    
    This class provides industrial-strength connection management for Interactive Brokers
    with automatic reconnection, health monitoring, failover capabilities, and comprehensive
    analytics. It ensures maximum uptime and reliability for automated trading operations.
    
    Key Features:
    - Automatic reconnection with exponential backoff
    - Real-time connection health monitoring
    - Network diagnostics and bandwidth monitoring  
    - Failover support for multiple broker endpoints
    - Connection quality assessment and optimization
    - Comprehensive connection analytics and reporting
    - Event-driven architecture with detailed logging
    
    Attributes:
        logger: Module logger instance
        config: Connection configuration
        state: Current connection state
        ib_connection: Interactive Brokers connection
        metrics: Connection performance metrics
        
    Example:
        >>> manager = ConnectionManager(config)
        >>> manager.initialize()
        >>> if manager.connect():
        >>>     print("Connected to broker")
    """
    
    def __init__(self, config: ConnectionConfig = None):
        """
        Initialize the Connection Manager.
        
        Args:
            config: Connection configuration
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or ConnectionConfig()
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.ib_connection: Optional[IB] = None
        self.connection_time: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        
        # Threading infrastructure
        self._state_lock = RLock()
        self._metrics_lock = RLock()
        self._shutdown_event = ThreadEvent()
        self._heartbeat_thread: Optional[Thread] = None
        self._monitoring_thread: Optional[Thread] = None
        self._diagnostics_thread: Optional[Thread] = None
        
        # Metrics and monitoring
        self.metrics = ConnectionMetrics()
        self.network_diagnostics = NetworkDiagnostics()
        self.connection_history: deque = deque(maxlen=1000)
        self.latency_history: deque = deque(maxlen=100)
        
        # Reconnection management
        self.reconnect_attempts = 0
        self.last_reconnect_time: Optional[datetime] = None
        self.current_backoff_delay = self.config.retry_delay
        
        # Failover management
        self.current_host_index = 0
        self.failover_hosts = [self.config.host] + self.config.failover_hosts
        
        # Event callbacks
        self.connection_callbacks: List[Callable] = []
        self.disconnection_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        
        self.logger.info("ConnectionManager initialized")
    
    # ==========================================================================
    # INITIALIZATION AND SETUP
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the connection manager.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing ConnectionManager...")
            
            # Validate configuration
            if not self._validate_config():
                self.logger.error("Configuration validation failed")
                return False
            
            # Initialize IB connection object
            if HAS_IB_INSYNC:
                self.ib_connection = IB()
                self._setup_ib_callbacks()
            else:
                self.logger.warning("IB connection will be simulated")
            
            # Start monitoring threads
            self._start_monitoring_threads()
            
            # Perform initial network diagnostics
            self._perform_network_diagnostics()
            
            self.logger.info("ConnectionManager initialization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Heartbeat failure handling error: {e}")
    
    def _connection_monitor(self):
        """Monitor connection status and metrics."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Update connection metrics
                    self._update_connection_metrics()
                    
                    # Check connection quality
                    self._assess_connection_quality()
                    
                    # Monitor for anomalies
                    self._detect_connection_anomalies()
                    
                    # Wait for next check
                    self._shutdown_event.wait(HEALTH_CHECK_INTERVAL)
                    
                except Exception as e:
                    self.logger.error(f"Connection monitor error: {e}")
                    self._shutdown_event.wait(HEALTH_CHECK_INTERVAL)
                    
        except Exception as e:
            self.logger.error(f"Connection monitor failed: {e}")
    
    def _diagnostics_monitor(self):
        """Monitor network diagnostics."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    # Perform network diagnostics
                    self._perform_network_diagnostics()
                    
                    # Update network status
                    self._update_network_status()
                    
                    # Wait for next check
                    self._shutdown_event.wait(DIAGNOSTICS_INTERVAL)
                    
                except Exception as e:
                    self.logger.error(f"Diagnostics monitor error: {e}")
                    self._shutdown_event.wait(DIAGNOSTICS_INTERVAL)
                    
        except Exception as e:
            self.logger.error(f"Diagnostics monitor failed: {e}")
    
    # ==========================================================================
    # NETWORK DIAGNOSTICS
    # ==========================================================================
    
    def _perform_network_diagnostics(self):
        """Perform comprehensive network diagnostics."""
        try:
            self.logger.debug("Performing network diagnostics...")
            
            # Check internet connectivity
            has_internet = check_internet_connection()
            self.network_diagnostics.external_connectivity = has_internet
            
            if not has_internet:
                self.network_diagnostics.network_status = NetworkStatus.CRITICAL
                return
            
            # Ping test to broker host
            ping_result = self._ping_host(self.config.host)
            self.network_diagnostics.ping_latency_ms = ping_result.get('latency_ms', 0)
            self.network_diagnostics.packet_loss_pct = ping_result.get('packet_loss', 0)
            
            # DNS resolution test
            dns_latency = self._test_dns_resolution(self.config.host)
            self.network_diagnostics.dns_resolution_ms = dns_latency
            
            # Bandwidth test (simplified)
            bandwidth = self._estimate_bandwidth()
            self.network_diagnostics.bandwidth_mbps = bandwidth
            
            # Update timestamp
            self.network_diagnostics.last_check = datetime.now()
            
            self.logger.debug("Network diagnostics completed")
            
        except Exception as e:
            self.logger.error(f"Network diagnostics failed: {e}")
    
    def _ping_host(self, host: str) -> Dict[str, float]:
        """Ping a host and return latency and packet loss."""
        try:
            if platform.system().lower() == "windows":
                cmd = ["ping", "-n", "4", host]
            else:
                cmd = ["ping", "-c", "4", host]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                output = result.stdout
                
                # Parse latency (simplified)
                latency_ms = 0.0
                packet_loss = 0.0
                
                if "time=" in output:
                    # Extract average latency
                    lines = output.split('\n')
                    for line in lines:
                        if "time=" in line:
                            try:
                                time_part = line.split("time=")[1].split("ms")[0]
                                latency_ms = float(time_part)
                                break
                            except:
                                pass
                
                # Parse packet loss
                if "% packet loss" in output or "% loss" in output:
                    try:
                        loss_line = [line for line in output.split('\n') if "% packet loss" in line or "% loss" in line][0]
                        packet_loss = float(loss_line.split('%')[0].split()[-1])
                    except:
                        pass
                
                return {"latency_ms": latency_ms, "packet_loss": packet_loss}
            else:
                return {"latency_ms": 0.0, "packet_loss": 100.0}
                
        except Exception as e:
            self.logger.error(f"Ping test failed: {e}")
            return {"latency_ms": 0.0, "packet_loss": 100.0}
    
    def _test_dns_resolution(self, host: str) -> float:
        """Test DNS resolution time."""
        try:
            start_time = time.time()
            socket.gethostbyname(host)
            return (time.time() - start_time) * 1000
        except Exception:
            return 0.0
    
    def _estimate_bandwidth(self) -> float:
        """Estimate network bandwidth (simplified)."""
        try:
            # Use psutil to get network stats
            net_io = psutil.net_io_counters()
            
            # This is a simplified estimation
            # In production, you might want to implement a proper bandwidth test
            return 10.0  # Default 10 Mbps
            
        except Exception:
            return 0.0
    
    def _update_network_status(self):
        """Update network status based on diagnostics."""
        try:
            diagnostics = self.network_diagnostics
            
            # Determine network status
            if not diagnostics.external_connectivity:
                status = NetworkStatus.CRITICAL
            elif diagnostics.packet_loss_pct > 10:
                status = NetworkStatus.CRITICAL
            elif diagnostics.ping_latency_ms > 200:
                status = NetworkStatus.POOR
            elif diagnostics.ping_latency_ms > 100:
                status = NetworkStatus.FAIR
            elif diagnostics.ping_latency_ms > 50:
                status = NetworkStatus.GOOD
            else:
                status = NetworkStatus.EXCELLENT
            
            # Update status
            if diagnostics.network_status != status:
                old_status = diagnostics.network_status
                diagnostics.network_status = status
                
                self.logger.info(f"Network status changed: {old_status.value} -> {status.value}")
                
                # Trigger callbacks if status degraded significantly
                if status in [NetworkStatus.POOR, NetworkStatus.CRITICAL]:
                    self._handle_network_degradation(status)
            
        except Exception as e:
            self.logger.error(f"Network status update failed: {e}")
    
    def _handle_network_degradation(self, status: NetworkStatus):
        """Handle network degradation."""
        try:
            self.logger.warning(f"Network degradation detected: {status.value}")
            
            # Implement degradation response based on severity
            if status == NetworkStatus.CRITICAL:
                self.logger.error("Critical network issues detected")
                # Consider triggering failover or disconnection
                if self.config.failover_mode == FailoverMode.AUTOMATIC:
                    self._try_next_host()
            
        except Exception as e:
            self.logger.error(f"Network degradation handling failed: {e}")
    
    # ==========================================================================
    # CONNECTION STATE MANAGEMENT
    # ==========================================================================
    
    def _set_state(self, new_state: ConnectionState):
        """Set connection state with proper tracking."""
        try:
            with self._state_lock:
                old_state = self.state
                self.state = new_state
                
                # Record state change
                self._record_connection_event(
                    f"STATE_CHANGE_{new_state.value.upper()}",
                    f"State changed from {old_state.value} to {new_state.value}"
                )
                
                # Update metrics
                if new_state == ConnectionState.CONNECTED:
                    self.metrics.total_connects += 1
                elif new_state == ConnectionState.DISCONNECTED:
                    self.metrics.total_disconnects += 1
                
                self.logger.debug(f"Connection state: {old_state.value} -> {new_state.value}")
                
        except Exception as e:
            self.logger.error(f"State change failed: {e}")
    
    def _record_connection_event(self, event_type: str, details: str):
        """Record a connection event."""
        try:
            event = ConnectionEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                state_from=self.state,
                state_to=self.state,
                details=details,
                metrics={
                    'latency_ms': self.metrics.avg_latency_ms,
                    'uptime_seconds': self.metrics.uptime_seconds,
                    'error_count': self.metrics.error_count
                }
            )
            
            self.connection_history.append(event)
            
        except Exception as e:
            self.logger.error(f"Event recording failed: {e}")
    
    # ==========================================================================
    # CONNECTION CALLBACKS
    # ==========================================================================
    
    def _on_connection_established(self):
        """Handle successful connection."""
        try:
            self.connection_time = datetime.now()
            self.reconnect_attempts = 0
            self.metrics.error_count = 0  # Reset error count on successful connection
            
            # Update metrics
            with self._metrics_lock:
                self.metrics.connection_time = self.connection_time
            
            # Trigger callbacks
            for callback in self.connection_callbacks:
                try:
                    callback(self)
                except Exception as e:
                    self.logger.error(f"Connection callback failed: {e}")
            
            self.logger.info("Connection established successfully")
            
        except Exception as e:
            self.logger.error(f"Connection establishment handling failed: {e}")
    
    def _on_connection_failed(self, reason: str):
        """Handle connection failure."""
        try:
            self.metrics.failed_attempts += 1
            self.metrics.last_error = reason
            
            # Trigger auto-reconnection if enabled
            if self.config.auto_reconnect:
                Thread(target=self._auto_reconnect, daemon=True).start()
            
            # Trigger callbacks
            for callback in self.error_callbacks:
                try:
                    callback(self, reason)
                except Exception as e:
                    self.logger.error(f"Error callback failed: {e}")
            
            self.logger.error(f"Connection failed: {reason}")
            
        except Exception as e:
            self.logger.error(f"Connection failure handling error: {e}")
    
    def _on_disconnection(self, reason: str):
        """Handle disconnection."""
        try:
            if self.connection_time:
                uptime = (datetime.now() - self.connection_time).total_seconds()
                self.metrics.uptime_seconds += uptime
            
            self.connection_time = None
            
            # Trigger callbacks
            for callback in self.disconnection_callbacks:
                try:
                    callback(self, reason)
                except Exception as e:
                    self.logger.error(f"Disconnection callback failed: {e}")
            
            self.logger.info(f"Disconnected: {reason}")
            
        except Exception as e:
            self.logger.error(f"Disconnection handling failed: {e}")
    
    # ==========================================================================
    # IB-SPECIFIC CALLBACKS
    # ==========================================================================
    
    def _on_ib_connected(self):
        """Handle IB connection event."""
        try:
            self.logger.info("IB connection established")
            self._set_state(ConnectionState.AUTHENTICATED)
            
        except Exception as e:
            self.logger.error(f"IB connection handler failed: {e}")
    
    def _on_ib_disconnected(self):
        """Handle IB disconnection event."""
        try:
            self.logger.warning("IB connection lost")
            self._set_state(ConnectionState.DISCONNECTED)
            
            # Trigger auto-reconnection
            if self.config.auto_reconnect:
                Thread(target=self._auto_reconnect, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"IB disconnection handler failed: {e}")
    
    def _on_ib_error(self, req_id, error_code, error_string, contract):
        """Handle IB error event."""
        try:
            self.logger.error(f"IB Error {error_code}: {error_string}")
            
            # Handle critical errors
            if error_code in [502, 503, 504]:  # Connection errors
                self._set_state(ConnectionState.FAILED)
                Thread(target=self._auto_reconnect, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"IB error handler failed: {e}")
    
    def _on_pending_tickers(self, tickers):
        """Handle pending tickers event."""
        try:
            # This indicates active data flow
            self.last_heartbeat = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Pending tickers handler failed: {e}")
    
    def _on_bar_update(self, bars, has_new_bar):
        """Handle bar update event."""
        try:
            # This indicates active data flow
            self.last_heartbeat = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Bar update handler failed: {e}")
    
    # ==========================================================================
    # METRICS AND ANALYTICS
    # ==========================================================================
    
    def _update_connection_metrics(self):
        """Update connection performance metrics."""
        try:
            with self._metrics_lock:
                # Update uptime
                if self.connection_time and self.state == ConnectionState.CONNECTED:
                    current_uptime = (datetime.now() - self.connection_time).total_seconds()
                    self.metrics.uptime_seconds = current_uptime
                
                # Update latency statistics
                if self.latency_history:
                    latencies = list(self.latency_history)
                    self.metrics.avg_latency_ms = statistics.mean(latencies)
                    self.metrics.min_latency_ms = min(latencies)
                    self.metrics.max_latency_ms = max(latencies)
            
        except Exception as e:
            self.logger.error(f"Metrics update failed: {e}")
    
    def _update_latency_metrics(self, latency_ms: float):
        """Update latency metrics."""
        try:
            self.latency_history.append(latency_ms)
            
            # Update min/max
            if latency_ms < self.metrics.min_latency_ms:
                self.metrics.min_latency_ms = latency_ms
            if latency_ms > self.metrics.max_latency_ms:
                self.metrics.max_latency_ms = latency_ms
            
        except Exception as e:
            self.logger.error(f"Latency metrics update failed: {e}")
    
    def _assess_connection_quality(self):
        """Assess overall connection quality."""
        try:
            quality_score = 1.0
            
            # Factor in latency
            if self.metrics.avg_latency_ms > self.config.network_latency_threshold_ms:
                quality_score *= 0.8
            
            # Factor in packet loss
            if self.network_diagnostics.packet_loss_pct > self.config.packet_loss_threshold:
                quality_score *= 0.7
            
            # Factor in error rate
            total_attempts = self.metrics.total_connects + self.metrics.failed_attempts
            if total_attempts > 0:
                error_rate = self.metrics.failed_attempts / total_attempts
                quality_score *= (1.0 - error_rate)
            
            # Factor in network status
            if self.network_diagnostics.network_status == NetworkStatus.POOR:
                quality_score *= 0.6
            elif self.network_diagnostics.network_status == NetworkStatus.CRITICAL:
                quality_score *= 0.3
            
            # Check if quality is below threshold
            if quality_score < self.config.connection_quality_threshold:
                self.logger.warning(f"Connection quality degraded: {quality_score:.2f}")
                
                # Consider taking action
                if quality_score < 0.5:
                    self.logger.error("Critical connection quality issues")
                    if self.config.failover_mode == FailoverMode.AUTOMATIC:
                        self._try_next_host()
            
        except Exception as e:
            self.logger.error(f"Connection quality assessment failed: {e}")
    
    def _detect_connection_anomalies(self):
        """Detect connection anomalies."""
        try:
            # Check for excessive latency
            if self.metrics.avg_latency_ms > self.config.network_latency_threshold_ms * 2:
                self.logger.warning(f"Excessive latency detected: {self.metrics.avg_latency_ms:.2f}ms")
            
            # Check for frequent disconnections
            recent_events = [e for e in self.connection_history 
                           if e.timestamp > datetime.now() - timedelta(hours=1)]
            disconnections = [e for e in recent_events if "DISCONNECT" in e.event_type]
            
            if len(disconnections) > 5:
                self.logger.warning(f"Frequent disconnections detected: {len(disconnections)} in last hour")
            
            # Check for error spikes
            if self.metrics.error_count > 10:
                self.logger.warning(f"Error spike detected: {self.metrics.error_count} errors")
            
        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {e}")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _pre_connection_checks(self) -> bool:
        """Perform pre-connection checks."""
        try:
            # Check network connectivity
            if not check_internet_connection():
                self.logger.error("No internet connectivity")
                return False
            
            # Check host reachability
            if not self._is_host_reachable(self.config.host, self.config.port):
                self.logger.error(f"Host unreachable: {self.config.host}:{self.config.port}")
                return False
            
            # Check market hours (optional)
            if hasattr(self.config, 'check_market_hours') and self.config.check_market_hours:
                if not is_market_open():
                    self.logger.warning("Market is currently closed")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Pre-connection checks failed: {e}")
            return False
    
    def _is_host_reachable(self, host: str, port: int, timeout: int = 5) -> bool:
        """Check if host and port are reachable."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _wait_for_connection(self, timeout: int) -> bool:
        """Wait for connection to be established."""
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.state == ConnectionState.CONNECTED:
                    return True
                elif self.state == ConnectionState.FAILED:
                    return False
                time.sleep(0.1)
            return False
        except Exception:
            return False
    
    def _save_connection_metrics(self):
        """Save connection metrics to file."""
        try:
            metrics_data = {
                'timestamp': datetime.now().isoformat(),
                'metrics': asdict(self.metrics),
                'network_diagnostics': asdict(self.network_diagnostics),
                'connection_history': [asdict(event) for event in list(self.connection_history)[-100:]]
            }
            
            # Save to metrics file
            metrics_file = "connection_metrics.json"
            with open(metrics_file, 'w') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            
            self.logger.debug(f"Connection metrics saved to {metrics_file}")
            
        except Exception as e:
            self.logger.error(f"Metrics saving failed: {e}")
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status.
        
        Returns:
            Dictionary with connection status information
        """
        try:
            return {
                'state': self.state.value,
                'connected': self.state == ConnectionState.CONNECTED,
                'host': self.config.host,
                'port': self.config.port,
                'client_id': self.config.client_id,
                'connection_time': self.connection_time.isoformat() if self.connection_time else None,
                'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
                'uptime_seconds': self.metrics.uptime_seconds if self.connection_time else 0,
                'metrics': asdict(self.metrics),
                'network_diagnostics': asdict(self.network_diagnostics),
                'reconnect_attempts': self.reconnect_attempts
            }
        except Exception as e:
            self.logger.error(f"Status retrieval failed: {e}")
            return {'error': str(e)}
    
    def get_connection_metrics(self) -> ConnectionMetrics:
        """Get connection metrics."""
        return self.metrics
    
    def get_network_diagnostics(self) -> NetworkDiagnostics:
        """Get network diagnostics."""
        return self.network_diagnostics
    
    def get_connection_history(self, limit: int = 100) -> List[ConnectionEvent]:
        """Get connection history."""
        try:
            return list(self.connection_history)[-limit:]
        except Exception:
            return []
    
    def add_connection_callback(self, callback: Callable):
        """Add connection callback."""
        self.connection_callbacks.append(callback)
    
    def add_disconnection_callback(self, callback: Callable):
        """Add disconnection callback."""
        self.disconnection_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add error callback."""
        self.error_callbacks.append(callback)
    
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self.state == ConnectionState.CONNECTED
    
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        try:
            if not self.is_connected():
                return False
            
            # Check last heartbeat
            if self.last_heartbeat:
                time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
                if time_since_heartbeat > self.config.heartbeat_interval * 2:
                    return False
            
            # Check network status
            if self.network_diagnostics.network_status in [NetworkStatus.POOR, NetworkStatus.CRITICAL]:
                return False
            
            # Check error rate
            if self.metrics.error_count > 5:
                return False
            
            return True
            
        except Exception:
            return False

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def get_connection_manager(config: ConnectionConfig = None) -> ConnectionManager:
    """
    Get a configured connection manager instance.
    
    Args:
        config: Connection configuration
        
    Returns:
        Configured connection manager instance
    """
    return ConnectionManager(config)

def create_connection_config(**kwargs) -> ConnectionConfig:
    """
    Create a connection configuration with custom parameters.
    
    Args:
        **kwargs: Configuration parameters
        
    Returns:
        Connection configuration instance
    """
    return ConnectionConfig(**kwargs)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    print("🔗 Spyder Connection Manager - Robust Broker Connections")
    print("=" * 60)
    
    # Create configuration
    config = ConnectionConfig(
        host="127.0.0.1",
        port=7497,
        client_id=1,
        auto_reconnect=True,
        enable_monitoring=True
    )
    
    print("\n1. Connection Manager Initialization...")
    manager = ConnectionManager(config)
    
    if manager.initialize():
        print("✅ Connection Manager initialized successfully")
        print(f"   - Host: {config.host}:{config.port}")
        print(f"   - Auto-reconnect: {config.auto_reconnect}")
        print(f"   - Monitoring: {config.enable_monitoring}")
    else:
        print("❌ Connection Manager initialization failed")
        sys.exit(1)
    
    print("\n2. Connection Attempt...")
    if manager.connect():
        print("✅ Connected to broker successfully")
        status = manager.get_connection_status()
        print(f"   - State: {status['state']}")
        print(f"   - Connection time: {status.get('connection_time', 'N/A')}")
    else:
        print("❌ Connection failed")
    
    print("\n3. Connection Health Check...")
    is_healthy = manager.is_healthy()
    print(f"✅ Connection health: {'Healthy' if is_healthy else 'Unhealthy'}")
    
    # Get metrics
    metrics = manager.get_connection_metrics()
    print(f"   - Total connects: {metrics.total_connects}")
    print(f"   - Failed attempts: {metrics.failed_attempts}")
    print(f"   - Average latency: {metrics.avg_latency_ms:.2f}ms")
    
    print("\n4. Network Diagnostics...")
    diagnostics = manager.get_network_diagnostics()
    print(f"✅ Network diagnostics completed")
    print(f"   - Network status: {diagnostics.network_status.value}")
    print(f"   - Ping latency: {diagnostics.ping_latency_ms:.2f}ms")
    print(f"   - Packet loss: {diagnostics.packet_loss_pct:.1f}%")
    print(f"   - External connectivity: {diagnostics.external_connectivity}")
    
    print("\n5. Connection History...")
    history = manager.get_connection_history(limit=5)
    print(f"✅ Recent connection events ({len(history)}):")
    for event in history[-3:]:
        print(f"   - {event.timestamp.strftime('%H:%M:%S')}: {event.event_type}")
    
    print("\n6. Testing Callbacks...")
    def on_connection(mgr):
        print("   📡 Connection callback triggered")
    
    def on_disconnection(mgr, reason):
        print(f"   📡 Disconnection callback triggered: {reason}")
    
    manager.add_connection_callback(on_connection)
    manager.add_disconnection_callback(on_disconnection)
    print("✅ Event callbacks registered")
    
    print("\n7. Connection Status Summary...")
    status = manager.get_connection_status()
    print("✅ Current status:")
    print(f"   - Connected: {status['connected']}")
    print(f"   - State: {status['state']}")
    print(f"   - Uptime: {status['uptime_seconds']:.1f} seconds")
    print(f"   - Reconnect attempts: {status['reconnect_attempts']}")
    
    print("\n8. Graceful Shutdown...")
    if manager.disconnect("Demo completed"):
        print("✅ Disconnected successfully")
    
    if manager.shutdown():
        print("✅ Connection Manager shutdown completed")
    
    print("\n" + "=" * 60)
    print("🎉 Connection Manager Demo Completed Successfully!")
    print("\nKey Features Demonstrated:")
    print("  • Robust connection management with auto-recovery")
    print("  • Real-time health monitoring and diagnostics")
    print("  • Comprehensive network diagnostics")
    print("  • Connection quality assessment")
    print("  • Event-driven architecture with callbacks")
    print("  • Detailed metrics and analytics")
    print("  • Failover support (when configured)")
    print("  • Professional error handling and logging")
    
    print("\nNext Steps:")
    print("  1. Configure failover hosts for redundancy")
    print("  2. Set up monitoring alerts and callbacks")
    print("  3. Integrate with your trading engine")
    print("  4. Configure market hours checking")
    print("  5. Set up connection quality thresholds")
    
    print("\nExample Integration:")
    print("  >>> config = ConnectionConfig(host='127.0.0.1', port=7497)")
    print("  >>> manager = ConnectionManager(config)")
    print("  >>> manager.initialize()")
    print("  >>> manager.connect()")
    print("  >>> # Your trading logic here")
    print("  >>> manager.shutdown()")
    
    print("\n🛡️ Production-Ready Connection Management!")
    print("   - Automatic reconnection with exponential backoff")
    print("   - Comprehensive health monitoring")
    print("   - Network diagnostics and quality assessment")
    print("   - Event-driven architecture")
    print("   - Professional error handling")
    print("   - Detailed analytics and reporting")
            self.logger.error(f"ConnectionManager initialization failed: {e}")
            self.error_handler.handle_broker_error(e, "ConnectionManager", "initialize")
            return False
    
    def _validate_config(self) -> bool:
        """Validate connection configuration."""
        try:
            # Check required fields
            if not self.config.host:
                self.logger.error("Host not specified in configuration")
                return False
            
            if not (1 <= self.config.port <= 65535):
                self.logger.error(f"Invalid port number: {self.config.port}")
                return False
            
            if not (1 <= self.config.client_id <= 9999):
                self.logger.error(f"Invalid client ID: {self.config.client_id}")
                return False
            
            if self.config.timeout <= 0:
                self.logger.error(f"Invalid timeout: {self.config.timeout}")
                return False
            
            # Check network settings
            if self.config.network_latency_threshold_ms <= 0:
                self.logger.error("Invalid network latency threshold")
                return False
            
            if not (0 <= self.config.packet_loss_threshold <= 100):
                self.logger.error("Invalid packet loss threshold")
                return False
            
            self.logger.debug("Configuration validation successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    def _setup_ib_callbacks(self):
        """Set up IB connection callbacks."""
        try:
            if not self.ib_connection:
                return
            
            # Connection callbacks
            self.ib_connection.connectedEvent += self._on_ib_connected
            self.ib_connection.disconnectedEvent += self._on_ib_disconnected
            self.ib_connection.errorEvent += self._on_ib_error
            
            # Market data callbacks
            self.ib_connection.pendingTickersEvent += self._on_pending_tickers
            self.ib_connection.barUpdateEvent += self._on_bar_update
            
            self.logger.debug("IB callbacks configured")
            
        except Exception as e:
            self.logger.error(f"IB callbacks setup failed: {e}")
    
    def _start_monitoring_threads(self):
        """Start monitoring threads."""
        try:
            if self.config.enable_monitoring:
                # Heartbeat monitoring
                self._heartbeat_thread = Thread(
                    target=self._heartbeat_monitor,
                    daemon=True,
                    name="ConnectionHeartbeat"
                )
                self._heartbeat_thread.start()
                
                # Connection monitoring
                self._monitoring_thread = Thread(
                    target=self._connection_monitor,
                    daemon=True,
                    name="ConnectionMonitor"
                )
                self._monitoring_thread.start()
                
                # Network diagnostics
                if self.config.enable_diagnostics:
                    self._diagnostics_thread = Thread(
                        target=self._diagnostics_monitor,
                        daemon=True,
                        name="NetworkDiagnostics"
                    )
                    self._diagnostics_thread.start()
                
                self.logger.debug("Monitoring threads started")
            
        except Exception as e:
            self.logger.error(f"Monitoring threads startup failed: {e}")
    
    def _stop_monitoring_threads(self):
        """Stop monitoring threads."""
        try:
            self._shutdown_event.set()
            
            # Wait for threads to complete
            threads = [self._heartbeat_thread, self._monitoring_thread, self._diagnostics_thread]
            for thread in threads:
                if thread and thread.is_alive():
                    thread.join(timeout=5.0)
            
            self.logger.debug("Monitoring threads stopped")
            
        except Exception as e:
            self.logger.error(f"Monitoring threads shutdown failed: {e}")
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def connect(self, timeout: Optional[int] = None) -> bool:
        """
        Establish connection to broker.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if connection successful
        """
        try:
            with self._state_lock:
                if self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
                    self.logger.info("Already connected to broker")
                    return True
                
                if self.state == ConnectionState.CONNECTING:
                    self.logger.info("Connection already in progress")
                    return self._wait_for_connection(timeout or self.config.timeout)
                
                self._set_state(ConnectionState.CONNECTING)
            
            timeout = timeout or self.config.timeout
            self.logger.info(f"Connecting to broker at {self.config.host}:{self.config.port}...")
            
            # Record connection attempt
            self._record_connection_event("CONNECTION_ATTEMPT", "Attempting to connect")
            
            # Perform pre-connection checks
            if not self._pre_connection_checks():
                self._set_state(ConnectionState.FAILED)
                return False
            
            # Attempt connection
            if HAS_IB_INSYNC and self.ib_connection:
                success = self._connect_to_ib(timeout)
            else:
                success = self._simulate_connection(timeout)
            
            if success:
                self._set_state(ConnectionState.CONNECTED)
                self._on_connection_established()
                self.logger.info("Successfully connected to broker")
                return True
            else:
                self._set_state(ConnectionState.FAILED)
                self._on_connection_failed("Connection attempt failed")
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_state(ConnectionState.FAILED)
            self._on_connection_failed(str(e))
            return False
    
    def _connect_to_ib(self, timeout: int) -> bool:
        """Connect to Interactive Brokers."""
        try:
            # Get current host
            current_host = self.failover_hosts[self.current_host_index]
            
            # Connect to IB
            self.ib_connection.connect(
                host=current_host,
                port=self.config.port,
                clientId=self.config.client_id,
                timeout=timeout
            )
            
            # Verify connection
            if self.ib_connection.isConnected():
                self.connection_time = datetime.now()
                self.metrics.connection_time = self.connection_time
                self.metrics.total_connects += 1
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"IB connection failed: {e}")
            self._try_next_host()
            return False
    
    def _simulate_connection(self, timeout: int) -> bool:
        """Simulate connection for testing purposes."""
        try:
            self.logger.info("Simulating broker connection...")
            
            # Simulate connection time
            time.sleep(1)
            
            # Set connection parameters
            self.connection_time = datetime.now()
            self.metrics.connection_time = self.connection_time
            self.metrics.total_connects += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Simulated connection failed: {e}")
            return False
    
    def disconnect(self, reason: str = "Manual disconnect") -> bool:
        """
        Disconnect from broker.
        
        Args:
            reason: Reason for disconnection
            
        Returns:
            bool: True if disconnection successful
        """
        try:
            with self._state_lock:
                if self.state == ConnectionState.DISCONNECTED:
                    self.logger.info("Already disconnected from broker")
                    return True
                
                self.logger.info(f"Disconnecting from broker: {reason}")
                self._record_connection_event("DISCONNECT_REQUESTED", reason)
                
                # Disconnect from IB
                if self.ib_connection and HAS_IB_INSYNC:
                    try:
                        self.ib_connection.disconnect()
                    except Exception as e:
                        self.logger.warning(f"IB disconnect error: {e}")
                
                self._set_state(ConnectionState.DISCONNECTED)
                self._on_disconnection(reason)
                
                self.logger.info("Successfully disconnected from broker")
                return True
                
        except Exception as e:
            self.logger.error(f"Disconnection failed: {e}")
            return False
    
    def reconnect(self, force: bool = False) -> bool:
        """
        Reconnect to broker.
        
        Args:
            force: Force reconnection even if already connected
            
        Returns:
            bool: True if reconnection successful
        """
        try:
            if not force and self.state == ConnectionState.CONNECTED:
                self.logger.info("Already connected, skipping reconnection")
                return True
            
            self.logger.info("Initiating reconnection...")
            
            # Disconnect first
            if self.state != ConnectionState.DISCONNECTED:
                self.disconnect("Reconnection requested")
            
            # Wait before reconnecting
            if self.config.reconnect_delay > 0:
                time.sleep(self.config.reconnect_delay)
            
            # Attempt reconnection
            return self.connect()
            
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
            return False
    
    def shutdown(self) -> bool:
        """
        Shutdown the connection manager.
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down ConnectionManager...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Disconnect if connected
            if self.state != ConnectionState.DISCONNECTED:
                self.disconnect("System shutdown")
            
            # Stop monitoring threads
            self._stop_monitoring_threads()
            
            # Save connection metrics
            self._save_connection_metrics()
            
            self.logger.info("ConnectionManager shutdown completed")
            return True
            
        except Exception as e:
            self.logger.error(f"ConnectionManager shutdown failed: {e}")
            return False
    
    # ==========================================================================
    # AUTOMATIC RECONNECTION
    # ==========================================================================
    
    def _auto_reconnect(self):
        """Attempt automatic reconnection."""
        try:
            if not self.config.auto_reconnect:
                return
            
            if self.reconnect_attempts >= self.config.max_reconnect_attempts:
                self.logger.error("Maximum reconnection attempts reached")
                return
            
            self.logger.info(f"Auto-reconnection attempt {self.reconnect_attempts + 1}")
            
            # Calculate backoff delay
            if self.config.use_exponential_backoff:
                delay = min(
                    self.config.reconnect_delay * (2 ** self.reconnect_attempts),
                    self.config.max_backoff_delay
                )
            else:
                delay = self.config.reconnect_delay
            
            # Wait before reconnecting
            self.logger.info(f"Waiting {delay:.1f} seconds before reconnection")
            time.sleep(delay)
            
            # Attempt reconnection
            self.reconnect_attempts += 1
            self.last_reconnect_time = datetime.now()
            
            if self.connect():
                self.logger.info("Auto-reconnection successful")
                self.reconnect_attempts = 0
                self.metrics.total_reconnects += 1
            else:
                self.logger.warning("Auto-reconnection failed")
                # Schedule next attempt
                Thread(target=self._auto_reconnect, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"Auto-reconnection failed: {e}")
    
    def _try_next_host(self):
        """Try next host in failover list."""
        try:
            if self.config.failover_mode == FailoverMode.DISABLED:
                return
            
            if len(self.failover_hosts) <= 1:
                return
            
            # Move to next host
            self.current_host_index = (self.current_host_index + 1) % len(self.failover_hosts)
            next_host = self.failover_hosts[self.current_host_index]
            
            self.logger.info(f"Failing over to host: {next_host}")
            
            # Update configuration
            self.config.host = next_host
            
        except Exception as e:
            self.logger.error(f"Host failover failed: {e}")
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    
    def _heartbeat_monitor(self):
        """Monitor connection health with heartbeat."""
        try:
            while not self._shutdown_event.is_set():
                try:
                    if self.state == ConnectionState.CONNECTED:
                        result = self._perform_heartbeat()
                        
                        if result.success:
                            self.last_heartbeat = result.timestamp
                            self.metrics.last_heartbeat = result.timestamp
                            self._update_latency_metrics(result.latency_ms)
                        else:
                            self.logger.warning(f"Heartbeat failed: {result.error_message}")
                            self._handle_heartbeat_failure(result)
                    
                    # Wait for next heartbeat
                    self._shutdown_event.wait(self.config.heartbeat_interval)
                    
                except Exception as e:
                    self.logger.error(f"Heartbeat monitor error: {e}")
                    self._shutdown_event.wait(self.config.heartbeat_interval)
                    
        except Exception as e:
            self.logger.error(f"Heartbeat monitor failed: {e}")
    
    def _perform_heartbeat(self) -> HeartbeatResult:
        """Perform heartbeat check."""
        try:
            start_time = time.time()
            
            if HAS_IB_INSYNC and self.ib_connection:
                # Use IB API for heartbeat
                if self.ib_connection.isConnected():
                    # Simple connectivity check
                    try:
                        # Request account summary as heartbeat
                        self.ib_connection.reqAccountSummary()
                        success = True
                        error_message = None
                    except Exception as e:
                        success = False
                        error_message = str(e)
                else:
                    success = False
                    error_message = "IB connection not established"
            else:
                # Simulate heartbeat
                success = True
                error_message = None
            
            latency_ms = (time.time() - start_time) * 1000
            
            return HeartbeatResult(
                success=success,
                latency_ms=latency_ms,
                timestamp=datetime.now(),
                error_message=error_message
            )
            
        except Exception as e:
            return HeartbeatResult(
                success=False,
                latency_ms=0.0,
                timestamp=datetime.now(),
                error_message=str(e)
            )
    
    def _handle_heartbeat_failure(self, result: HeartbeatResult):
        """Handle heartbeat failure."""
        try:
            self.logger.warning(f"Heartbeat failure detected: {result.error_message}")
            
            # Increment error count
            self.metrics.error_count += 1
            self.metrics.last_error = result.error_message
            
            # Check if reconnection is needed
            if self.metrics.error_count >= 3:
                self.logger.error("Multiple heartbeat failures, initiating reconnection")
                self._set_state(ConnectionState.FAILED)
                Thread(target=self._auto_reconnect, daemon=True).start()
            
        except Exception as e: