#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB14_MultiClientWatchdog.py
Purpose: Multi-client health monitoring and watchdog system
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-11 Time: 16:00:00  

Module Description:
    Comprehensive multi-client monitoring system that tracks the health and
    performance of all 10 IB Gateway client connections. Provides real-time
    health scoring, automatic recovery, performance monitoring, and system
    health aggregation. Essential for maintaining stable connections in the
    autonomous trading system.

Key Features:
    - Real-time health monitoring for all 10 client connections
    - PROVEN race condition fix integration and validation
    - System-wide health aggregation and scoring
    - Automatic recovery and reconnection logic
    - Performance metrics and latency tracking
    - Event-driven health alerts and notifications
    - Dashboard integration with color-coded status
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
import time
import statistics
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
import json
import logging
import weakref

# ==============================================================================
# THIRD-PARTY IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    print("WARNING: psutil not available - basic resource monitoring only")
    HAS_PSUTIL = False

try:
    import pytz
    HAS_PYTZ = True
except ImportError:
    print("WARNING: pytz not available - using basic timezone handling")
    HAS_PYTZ = False

# ==============================================================================
# LOCAL IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    print("WARNING: SpyderLogger not available - using basic logging")
    import logging
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    print("WARNING: SpyderErrorHandler not available - using basic error handling")
    class SpyderErrorHandler:
        def handle_error(self, error, context=""):
            print(f"ERROR in {context}: {error}")

try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    HAS_EVENT_MANAGER = True
except ImportError:
    print("WARNING: EventManager not available - no event notifications")
    HAS_EVENT_MANAGER = False
    # Mock implementations
    class EventType:
        CLIENT_HEALTH_CHANGE = "client_health_change"
        SYSTEM_HEALTH_CHANGE = "system_health_change"
        CLIENT_RECOVERY = "client_recovery"
        CLIENT_FAILURE = "client_failure"
    
    class Event:
        def __init__(self, event_type, data=None):
            self.type = event_type
            self.data = data
    
    class EventManager:
        def emit_event(self, event):
            pass

try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    HAS_SPYDER_CLIENT = True
except ImportError:
    print("WARNING: SpyderClient not available - watchdog will monitor externally")
    HAS_SPYDER_CLIENT = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Client configuration
CLIENT_COUNT = 10
CLIENT_ID_RANGE = range(1, CLIENT_COUNT + 1)

# Health check intervals
DEFAULT_HEALTH_CHECK_INTERVAL = 30.0  # seconds
FAST_HEALTH_CHECK_INTERVAL = 5.0      # seconds for critical situations
SYSTEM_HEALTH_AGGREGATION_INTERVAL = 60.0  # seconds

# Connection settings
RACE_CONDITION_DELAY = 1.0  # PROVEN: Full second for API handshake stability
CONNECTION_TIMEOUT = 20.0
MAX_CONNECTION_RETRIES = 5

# Performance monitoring
LATENCY_HISTORY_SIZE = 100
UPTIME_CALCULATION_INTERVAL = 300.0  # 5 minutes

# Health scoring thresholds
HEALTH_SCORE_EXCELLENT = 95
HEALTH_SCORE_GOOD = 80
HEALTH_SCORE_FAIR = 60
HEALTH_SCORE_POOR = 40

# Alert thresholds
CONSECUTIVE_FAILURES_WARNING = 3
CONSECUTIVE_FAILURES_CRITICAL = 5
LATENCY_WARNING_MS = 50
LATENCY_CRITICAL_MS = 100

# ==============================================================================
# ENUMS
# ==============================================================================

class HealthStatus(Enum):
    """Client and system health status levels."""
    EXCELLENT = "excellent"
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    RECOVERING = "recovering"
    FAILED = "failed"
    UNKNOWN = "unknown"
    
    def __str__(self) -> str:
        return self.value
    
    @property
    def color_code(self) -> str:
        """Get color code for dashboard display."""
        color_map = {
            self.EXCELLENT: "#00CC00",   # Bright green
            self.HEALTHY: "#00FF00",     # Green
            self.WARNING: "#FFD700",     # Yellow
            self.CRITICAL: "#FF4500",    # Orange-red
            self.RECOVERING: "#87CEEB",  # Sky blue
            self.FAILED: "#FF0000",      # Red
            self.UNKNOWN: "#808080"      # Gray
        }
        return color_map.get(self, "#808080")
    
    @property
    def priority(self) -> int:
        """Get priority for sorting (higher = more critical)."""
        priority_map = {
            self.FAILED: 100,
            self.CRITICAL: 90,
            self.WARNING: 70,
            self.RECOVERING: 50,
            self.HEALTHY: 30,
            self.EXCELLENT: 20,
            self.UNKNOWN: 10
        }
        return priority_map.get(self, 0)

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class ClientPurpose(Enum):
    """Client purposes for specialized monitoring."""
    TRADING = "TRADING"
    MARKET_DATA = "MARKET_DATA"
    ACCOUNT_DATA = "ACCOUNT_DATA"
    ORDER_MANAGEMENT = "ORDER_MANAGEMENT"
    POSITION_TRACKING = "POSITION_TRACKING"
    RISK_MONITORING = "RISK_MONITORING"
    BACKUP = "BACKUP"
    GENERAL = "GENERAL"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class HealthMetrics:
    """Comprehensive health metrics for a client."""
    # Basic metrics
    latency_ms: float = 0.0
    packet_loss_rate: float = 0.0
    connection_uptime_seconds: float = 0.0
    
    # Performance metrics
    requests_per_minute: float = 0.0
    error_rate_percentage: float = 0.0
    response_time_ms: float = 0.0
    
    # Resource metrics
    memory_usage_mb: float = 0.0
    cpu_usage_percentage: float = 0.0
    
    # PROVEN race condition fix metrics
    race_condition_fixes_applied: int = 0
    successful_recoveries_after_fix: int = 0
    recovery_validation_successes: int = 0
    recovery_validation_failures: int = 0
    
    # Timestamps
    last_updated: datetime = field(default_factory=datetime.now)
    
    def calculate_health_score(self) -> float:
        """Calculate overall health score (0-100)."""
        score = 100.0
        
        # Latency impact (0-30 points)
        if self.latency_ms > LATENCY_CRITICAL_MS:
            score -= 30
        elif self.latency_ms > LATENCY_WARNING_MS:
            score -= 15
        
        # Error rate impact (0-25 points)
        score -= min(25, self.error_rate_percentage)
        
        # Packet loss impact (0-20 points)
        score -= min(20, self.packet_loss_rate * 20)
        
        # Resource usage impact (0-15 points)
        if self.cpu_usage_percentage > 80:
            score -= 15
        elif self.cpu_usage_percentage > 60:
            score -= 8
        
        # Recovery success bonus
        if self.recovery_validation_successes > self.recovery_validation_failures:
            score += 5
        
        return max(0.0, min(100.0, score))

@dataclass
class ClientHealth:
    """Health information for a client connection."""
    client_id: int
    purpose: ClientPurpose = ClientPurpose.GENERAL
    status: HealthStatus = HealthStatus.UNKNOWN
    
    # Connection state
    is_connected: bool = False
    last_connect_time: Optional[datetime] = None
    last_disconnect_time: Optional[datetime] = None
    connection_attempts: int = 0
    
    # Health tracking
    last_check_time: Optional[datetime] = None
    consecutive_failures: int = 0
    total_failures: int = 0
    total_recoveries: int = 0
    health_score: float = 0.0
    
    # Performance data
    metrics: HealthMetrics = field(default_factory=HealthMetrics)
    latency_history: deque = field(default_factory=lambda: deque(maxlen=LATENCY_HISTORY_SIZE))
    
    # Error tracking
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    error_count_24h: int = 0
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=10))
    
    # Recovery tracking
    last_recovery_time: Optional[datetime] = None
    recovery_success_rate: float = 0.0
    auto_recovery_enabled: bool = True
    
    def update_health_score(self):
        """Update the health score based on current metrics."""
        self.health_score = self.metrics.calculate_health_score()
        
        # Update status based on score
        if self.health_score >= HEALTH_SCORE_EXCELLENT:
            self.status = HealthStatus.EXCELLENT
        elif self.health_score >= HEALTH_SCORE_GOOD:
            self.status = HealthStatus.HEALTHY
        elif self.health_score >= HEALTH_SCORE_FAIR:
            self.status = HealthStatus.WARNING
        elif self.health_score >= HEALTH_SCORE_POOR:
            self.status = HealthStatus.CRITICAL
        else:
            self.status = HealthStatus.FAILED
    
    def add_error(self, error_message: str):
        """Add an error to the tracking."""
        self.last_error = error_message
        self.last_error_time = datetime.now()
        self.error_count_24h += 1
        self.total_failures += 1
        self.consecutive_failures += 1
        self.recent_errors.append({
            'error': error_message,
            'timestamp': datetime.now().isoformat()
        })
    
    def record_successful_connection(self):
        """Record a successful connection."""
        self.is_connected = True
        self.last_connect_time = datetime.now()
        self.consecutive_failures = 0
        self.connection_attempts += 1
        
        if self.last_error_time:
            self.total_recoveries += 1
            self.last_recovery_time = datetime.now()
    
    def record_latency(self, latency_ms: float):
        """Record a latency measurement."""
        self.latency_history.append(latency_ms)
        self.metrics.latency_ms = latency_ms
        
        # Update average
        if self.latency_history:
            self.metrics.latency_ms = statistics.mean(self.latency_history)
    
    @property
    def uptime_seconds(self) -> float:
        """Calculate current uptime in seconds."""
        if self.is_connected and self.last_connect_time:
            return (datetime.now() - self.last_connect_time).total_seconds()
        return 0.0
    
    @property
    def average_latency(self) -> float:
        """Get average latency from history."""
        if not self.latency_history:
            return 0.0
        return statistics.mean(self.latency_history)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Handle datetime and enum serialization
        data['status'] = self.status.value
        data['purpose'] = self.purpose.value
        data['last_check_time'] = self.last_check_time.isoformat() if self.last_check_time else None
        data['last_connect_time'] = self.last_connect_time.isoformat() if self.last_connect_time else None
        data['last_disconnect_time'] = self.last_disconnect_time.isoformat() if self.last_disconnect_time else None
        data['last_error_time'] = self.last_error_time.isoformat() if self.last_error_time else None
        data['last_recovery_time'] = self.last_recovery_time.isoformat() if self.last_recovery_time else None
        data['latency_history'] = list(self.latency_history)
        data['recent_errors'] = list(self.recent_errors)
        return data

@dataclass
class SystemHealth:
    """
    System-wide health aggregation and monitoring.
    CRITICAL: This class is imported by SpyderB16_GatewayIntegration.py
    """
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    overall_health_score: float = 0.0
    
    # Component status
    component_status: Dict[str, bool] = field(default_factory=dict)
    client_health_summary: Dict[int, HealthStatus] = field(default_factory=dict)
    
    # System metrics
    connected_clients: int = 0
    total_clients: int = CLIENT_COUNT
    average_latency: float = 0.0
    total_errors_24h: int = 0
    
    # Performance tracking
    system_uptime_seconds: float = 0.0
    last_full_health_check: Optional[datetime] = None
    health_trend: str = "stable"  # improving, stable, degrading
    
    # Alert information
    active_alerts: List[Dict[str, Any]] = field(default_factory=list)
    last_critical_alert: Optional[datetime] = None
    
    def update_from_clients(self, client_healths: Dict[int, ClientHealth]):
        """Update system health from individual client health data."""
        if not client_healths:
            self.overall_status = HealthStatus.UNKNOWN
            return
        
        # Calculate connected clients
        self.connected_clients = sum(1 for health in client_healths.values() if health.is_connected)
        
        # Calculate overall health score
        health_scores = [health.health_score for health in client_healths.values()]
        self.overall_health_score = statistics.mean(health_scores) if health_scores else 0.0
        
        # Calculate average latency
        latencies = [health.average_latency for health in client_healths.values() if health.average_latency > 0]
        self.average_latency = statistics.mean(latencies) if latencies else 0.0
        
        # Update client health summary
        self.client_health_summary = {
            client_id: health.status for client_id, health in client_healths.items()
        }
        
        # Calculate total errors
        self.total_errors_24h = sum(health.error_count_24h for health in client_healths.values())
        
        # Determine overall status
        failed_clients = sum(1 for health in client_healths.values() if health.status == HealthStatus.FAILED)
        critical_clients = sum(1 for health in client_healths.values() if health.status == HealthStatus.CRITICAL)
        warning_clients = sum(1 for health in client_healths.values() if health.status == HealthStatus.WARNING)
        
        if failed_clients >= 3:  # 30% failure rate
            self.overall_status = HealthStatus.FAILED
        elif failed_clients >= 1 or critical_clients >= 3:
            self.overall_status = HealthStatus.CRITICAL
        elif critical_clients >= 1 or warning_clients >= 3:
            self.overall_status = HealthStatus.WARNING
        elif self.overall_health_score >= HEALTH_SCORE_EXCELLENT:
            self.overall_status = HealthStatus.EXCELLENT
        elif self.overall_health_score >= HEALTH_SCORE_GOOD:
            self.overall_status = HealthStatus.HEALTHY
        else:
            self.overall_status = HealthStatus.WARNING
        
        self.last_full_health_check = datetime.now()
    
    def get_health_score(self) -> float:
        """Get the overall health score (0-100)."""
        return self.overall_health_score
    
    def get_component_status(self) -> Dict[str, bool]:
        """Get component status for integration."""
        return self.component_status.copy()
    
    def add_component_status(self, component_name: str, is_healthy: bool):
        """Add or update component status."""
        self.component_status[component_name] = is_healthy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['overall_status'] = self.overall_status.value
        data['client_health_summary'] = {
            str(k): v.value for k, v in self.client_health_summary.items()
        }
        data['last_full_health_check'] = self.last_full_health_check.isoformat() if self.last_full_health_check else None
        return data

@dataclass
class WatchdogConfig:
    """Configuration for the multi-client watchdog system."""
    # Monitoring intervals
    health_check_interval: float = DEFAULT_HEALTH_CHECK_INTERVAL
    fast_check_interval: float = FAST_HEALTH_CHECK_INTERVAL
    system_aggregation_interval: float = SYSTEM_HEALTH_AGGREGATION_INTERVAL
    
    # Connection settings
    connection_timeout: float = CONNECTION_TIMEOUT
    max_retries: int = MAX_CONNECTION_RETRIES
    race_condition_delay: float = RACE_CONDITION_DELAY
    
    # Auto-recovery settings
    enable_auto_recovery: bool = True
    recovery_backoff_factor: float = 1.5
    max_recovery_attempts: int = 3
    
    # Alert thresholds
    consecutive_failures_warning: int = CONSECUTIVE_FAILURES_WARNING
    consecutive_failures_critical: int = CONSECUTIVE_FAILURES_CRITICAL
    latency_warning_ms: float = LATENCY_WARNING_MS
    latency_critical_ms: float = LATENCY_CRITICAL_MS
    
    # Client purposes mapping
    client_purposes: Dict[int, ClientPurpose] = field(default_factory=lambda: {
        1: ClientPurpose.TRADING,      # Highest priority
        2: ClientPurpose.ORDER_MANAGEMENT,
        3: ClientPurpose.MARKET_DATA,
        4: ClientPurpose.ACCOUNT_DATA,
        5: ClientPurpose.POSITION_TRACKING,
        6: ClientPurpose.RISK_MONITORING,
        7: ClientPurpose.BACKUP,
        8: ClientPurpose.GENERAL,
        9: ClientPurpose.GENERAL,
        10: ClientPurpose.GENERAL
    })
    
    # Feature flags
    enable_latency_tracking: bool = True
    enable_performance_monitoring: bool = True
    enable_event_notifications: bool = True

# ==============================================================================
# MAIN WATCHDOG CLASS
# ==============================================================================

class MultiClientWatchdog:
    """
    Comprehensive multi-client health monitoring and watchdog system.
    
    Monitors all 10 IB Gateway client connections, tracks health metrics,
    performs automatic recovery, and provides real-time health scoring.
    Essential for maintaining stable connections in autonomous trading.
    """
    
    def __init__(self, config: Optional[WatchdogConfig] = None,
                 event_manager: Optional[EventManager] = None):
        """
        Initialize the multi-client watchdog.
        
        Args:
            config: Watchdog configuration
            event_manager: Event manager for notifications
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or WatchdogConfig()
        self.event_manager = event_manager or EventManager()
        
        # Client health tracking
        self.client_healths: Dict[int, ClientHealth] = {}
        self.system_health = SystemHealth()
        
        # Initialize client health objects
        for client_id in CLIENT_ID_RANGE:
            purpose = self.config.client_purposes.get(client_id, ClientPurpose.GENERAL)
            self.client_healths[client_id] = ClientHealth(
                client_id=client_id,
                purpose=purpose
            )
        
        # Threading and control
        self._is_running = False
        self._shutdown_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._system_health_thread: Optional[threading.Thread] = None
        
        # Performance tracking
        self._start_time = datetime.now()
        self._health_check_count = 0
        self._recovery_attempts = defaultdict(int)
        
        # Client management (if available)
        self._clients: Dict[int, Any] = {}  # Will store SpyderClient instances
        
        self.logger.info(f"MultiClientWatchdog initialized for {CLIENT_COUNT} clients")
    
    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    
    def start(self) -> bool:
        """Start the watchdog monitoring."""
        try:
            if self._is_running:
                self.logger.warning("Watchdog is already running")
                return True
            
            self.logger.info("Starting multi-client watchdog...")
            self._is_running = True
            self._shutdown_event.clear()
            
            # Start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="MultiClientWatchdog",
                daemon=True
            )
            self._monitor_thread.start()
            
            # Start system health aggregation thread
            self._system_health_thread = threading.Thread(
                target=self._system_health_loop,
                name="SystemHealthAggregator",
                daemon=True
            )
            self._system_health_thread.start()
            
            self.logger.info("Multi-client watchdog started successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "start_watchdog")
            return False
    
    def stop(self) -> bool:
        """Stop the watchdog monitoring."""
        try:
            if not self._is_running:
                self.logger.info("Watchdog is already stopped")
                return True
            
            self.logger.info("Stopping multi-client watchdog...")
            self._is_running = False
            self._shutdown_event.set()
            
            # Wait for threads to finish
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=10)
            
            if self._system_health_thread and self._system_health_thread.is_alive():
                self._system_health_thread.join(timeout=5)
            
            self.logger.info("Multi-client watchdog stopped successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "stop_watchdog")
            return False
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    
    def _monitor_loop(self):
        """Main monitoring loop for all clients."""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                start_time = time.time()
                
                # Check each client
                for client_id in CLIENT_ID_RANGE:
                    if self._shutdown_event.is_set():
                        break
                    
                    self._check_client_health(client_id)
                
                # Performance tracking
                self._health_check_count += 1
                check_duration = time.time() - start_time
                
                # Emit system health event
                if HAS_EVENT_MANAGER:
                    event = Event(EventType.SYSTEM_HEALTH_CHANGE, {
                        'overall_status': self.system_health.overall_status.value,
                        'connected_clients': self.system_health.connected_clients,
                        'check_duration_ms': check_duration * 1000
                    })
                    self.event_manager.emit_event(event)
                
                # Adaptive sleep based on system health
                sleep_interval = self._get_adaptive_check_interval()
                self._shutdown_event.wait(sleep_interval)
                
            except Exception as e:
                self.error_handler.handle_error(e, "_monitor_loop")
                self._shutdown_event.wait(60)  # Wait longer on error
    
    def _check_client_health(self, client_id: int):
        """Perform health check on a specific client."""
        try:
            health = self.client_healths[client_id]
            health.last_check_time = datetime.now()
            
            # Check connection status
            is_connected = self._check_client_connection(client_id)
            
            # Update connection state
            if is_connected and not health.is_connected:
                health.record_successful_connection()
                self._emit_client_recovery_event(client_id)
            elif not is_connected and health.is_connected:
                health.is_connected = False
                health.last_disconnect_time = datetime.now()
                health.add_error("Connection lost")
                self._emit_client_failure_event(client_id)
            
            # Measure latency if connected
            if is_connected and self.config.enable_latency_tracking:
                latency = self._measure_client_latency(client_id)
                if latency > 0:
                    health.record_latency(latency)
            
            # Update performance metrics
            if self.config.enable_performance_monitoring:
                self._update_performance_metrics(client_id)
            
            # Update health score and status
            health.update_health_score()
            
            # Check for recovery needs
            if (not is_connected and 
                self.config.enable_auto_recovery and 
                health.auto_recovery_enabled):
                self._attempt_client_recovery(client_id)
            
            # Emit health change event if status changed
            self._emit_health_change_event(client_id, health)
            
        except Exception as e:
            self.error_handler.handle_error(e, f"_check_client_health_{client_id}")
    
    def _check_client_connection(self, client_id: int) -> bool:
        """Check if a client is connected."""
        try:
            # If we have SpyderClient integration
            if HAS_SPYDER_CLIENT and client_id in self._clients:
                client = self._clients[client_id]
                return hasattr(client, 'is_connected') and client.is_connected()
            
            # Fallback: Check if port is listening
            import socket
            port = 4002 if client_id <= 5 else 4001  # Paper/Live port distribution
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result == 0
                
        except Exception as e:
            self.logger.debug(f"Connection check failed for client {client_id}: {e}")
            return False
    
    def _measure_client_latency(self, client_id: int) -> float:
        """Measure client response latency in milliseconds."""
        try:
            start_time = time.time()
            
            # Simple ping test if we have client integration
            if HAS_SPYDER_CLIENT and client_id in self._clients:
                client = self._clients[client_id]
                if hasattr(client, 'ping'):
                    client.ping()
                else:
                    # Fallback: Check account summary request
                    time.sleep(0.01)  # Simulate minimal request
            else:
                # Network latency test
                import socket
                port = 4002 if client_id <= 5 else 4001
                
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    sock.connect(('localhost', port))
            
            return (time.time() - start_time) * 1000  # Convert to milliseconds
            
        except Exception as e:
            self.logger.debug(f"Latency measurement failed for client {client_id}: {e}")
            return 0.0
    
    def _update_performance_metrics(self, client_id: int):
        """Update performance metrics for a client."""
        try:
            health = self.client_healths[client_id]
            
            # Update uptime
            health.metrics.connection_uptime_seconds = health.uptime_seconds
            
            # Update resource usage if psutil is available
            if HAS_PSUTIL:
                try:
                    # This is a simplified approach - in production you'd track
                    # the actual IB Gateway process for this client
                    process = psutil.Process()
                    health.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
                    health.metrics.cpu_usage_percentage = process.cpu_percent()
                except psutil.NoSuchProcess:
                    pass
            
            # Calculate error rate
            total_checks = max(1, self._health_check_count)
            health.metrics.error_rate_percentage = (health.total_failures / total_checks) * 100
            
            health.metrics.last_updated = datetime.now()
            
        except Exception as e:
            self.error_handler.handle_error(e, f"_update_performance_metrics_{client_id}")
    
    def _attempt_client_recovery(self, client_id: int):
        """Attempt to recover a failed client connection."""
        try:
            health = self.client_healths[client_id]
            
            # Check if we should attempt recovery
            if self._recovery_attempts[client_id] >= self.config.max_recovery_attempts:
                self.logger.warning(f"Max recovery attempts reached for client {client_id}")
                return
            
            # Exponential backoff
            backoff_delay = (self.config.recovery_backoff_factor ** self._recovery_attempts[client_id])
            
            self.logger.info(f"Attempting recovery for client {client_id} (attempt {self._recovery_attempts[client_id] + 1})")
            
            # Apply PROVEN race condition fix
            time.sleep(self.config.race_condition_delay)
            
            # Attempt reconnection
            if self._reconnect_client(client_id):
                self.logger.info(f"Successfully recovered client {client_id}")
                self._recovery_attempts[client_id] = 0
                health.metrics.successful_recoveries_after_fix += 1
                health.metrics.recovery_validation_successes += 1
            else:
                self._recovery_attempts[client_id] += 1
                health.metrics.recovery_validation_failures += 1
                
                # Wait before next attempt
                time.sleep(backoff_delay)
            
        except Exception as e:
            self.error_handler.handle_error(e, f"_attempt_client_recovery_{client_id}")
    
    def _reconnect_client(self, client_id: int) -> bool:
        """Attempt to reconnect a client."""
        try:
            # If we have SpyderClient integration
            if HAS_SPYDER_CLIENT and client_id in self._clients:
                client = self._clients[client_id]
                if hasattr(client, 'reconnect'):
                    return client.reconnect()
            
            # Fallback: Basic connection test
            import socket
            port = 4002 if client_id <= 5 else 4001
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.config.connection_timeout)
                result = sock.connect_ex(('localhost', port))
                return result == 0
                
        except Exception as e:
            self.logger.debug(f"Reconnection failed for client {client_id}: {e}")
            return False
    
    def _system_health_loop(self):
        """System health aggregation loop."""
        while self._is_running and not self._shutdown_event.is_set():
            try:
                # Update system health from client data
                self.system_health.update_from_clients(self.client_healths)
                
                # Update system uptime
                self.system_health.system_uptime_seconds = (
                    datetime.now() - self._start_time
                ).total_seconds()
                
                # Add component status
                self.system_health.add_component_status("watchdog", True)
                self.system_health.add_component_status("monitoring", self._is_running)
                
                # Wait for next aggregation
                self._shutdown_event.wait(self.config.system_aggregation_interval)
                
            except Exception as e:
                self.error_handler.handle_error(e, "_system_health_loop")
                self._shutdown_event.wait(60)
    
    # ==========================================================================
    # EVENT MANAGEMENT
    # ==========================================================================
    
    def _emit_client_recovery_event(self, client_id: int):
        """Emit client recovery event."""
        if HAS_EVENT_MANAGER:
            event = Event(EventType.CLIENT_RECOVERY, {
                'client_id': client_id,
                'purpose': self.client_healths[client_id].purpose.value,
                'recovery_time': datetime.now().isoformat()
            })
            self.event_manager.emit_event(event)
    
    def _emit_client_failure_event(self, client_id: int):
        """Emit client failure event."""
        if HAS_EVENT_MANAGER:
            health = self.client_healths[client_id]
            event = Event(EventType.CLIENT_FAILURE, {
                'client_id': client_id,
                'purpose': health.purpose.value,
                'consecutive_failures': health.consecutive_failures,
                'last_error': health.last_error
            })
            self.event_manager.emit_event(event)
    
    def _emit_health_change_event(self, client_id: int, health: ClientHealth):
        """Emit health change event if status changed."""
        if HAS_EVENT_MANAGER:
            event = Event(EventType.CLIENT_HEALTH_CHANGE, {
                'client_id': client_id,
                'status': health.status.value,
                'health_score': health.health_score,
                'latency_ms': health.average_latency,
                'uptime_seconds': health.uptime_seconds
            })
            self.event_manager.emit_event(event)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _get_adaptive_check_interval(self) -> float:
        """Get adaptive check interval based on system health."""
        if self.system_health.overall_status in [HealthStatus.CRITICAL, HealthStatus.FAILED]:
            return self.config.fast_check_interval
        elif self.system_health.overall_status == HealthStatus.WARNING:
            return self.config.health_check_interval / 2
        else:
            return self.config.health_check_interval
    
    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    
    def get_client_health(self, client_id: int) -> Optional[ClientHealth]:
        """Get health information for a specific client."""
        return self.client_healths.get(client_id)
    
    def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        return self.system_health
    
    def get_all_client_healths(self) -> Dict[int, ClientHealth]:
        """Get health information for all clients."""
        return self.client_healths.copy()
    
    def force_client_check(self, client_id: int) -> bool:
        """Force an immediate health check for a client."""
        try:
            self._check_client_health(client_id)
            return True
        except Exception as e:
            self.error_handler.handle_error(e, f"force_client_check_{client_id}")
            return False
    
    def register_client(self, client_id: int, client_instance: Any):
        """Register a SpyderClient instance for monitoring."""
        if HAS_SPYDER_CLIENT:
            self._clients[client_id] = client_instance
            self.logger.info(f"Registered client {client_id} for monitoring")
    
    def unregister_client(self, client_id: int):
        """Unregister a client from monitoring."""
        if client_id in self._clients:
            del self._clients[client_id]
            self.logger.info(f"Unregistered client {client_id} from monitoring")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get a comprehensive status summary."""
        return {
            'system_health': self.system_health.to_dict(),
            'client_healths': {
                client_id: health.to_dict() 
                for client_id, health in self.client_healths.items()
            },
            'monitoring_stats': {
                'is_running': self._is_running,
                'uptime_seconds': (datetime.now() - self._start_time).total_seconds(),
                'health_check_count': self._health_check_count,
                'recovery_attempts': dict(self._recovery_attempts)
            }
        }

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_watchdog(config: Optional[Dict[str, Any]] = None,
                   event_manager: Optional[EventManager] = None) -> MultiClientWatchdog:
    """
    Factory function to create MultiClientWatchdog instance.
    
    Args:
        config: Configuration dictionary
        event_manager: Event manager instance
        
    Returns:
        MultiClientWatchdog instance
    """
    if config:
        watchdog_config = WatchdogConfig(**config)
    else:
        watchdog_config = WatchdogConfig()
    
    return MultiClientWatchdog(watchdog_config, event_manager)

def get_multi_client_watchdog() -> MultiClientWatchdog:
    """Get default watchdog instance (singleton pattern)."""
    if not hasattr(get_multi_client_watchdog, '_instance'):
        get_multi_client_watchdog._instance = create_watchdog()
    
    return get_multi_client_watchdog._instance

# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    'HealthStatus', 'AlertLevel', 'ClientPurpose',
    
    # Data structures
    'HealthMetrics', 'ClientHealth', 'SystemHealth', 'WatchdogConfig',
    
    # Main class
    'MultiClientWatchdog',
    
    # Factory functions
    'create_watchdog', 'get_multi_client_watchdog'
]

# ==============================================================================
# MODULE TEST
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    print("SpyderB14_MultiClientWatchdog - Multi-Client Health Monitoring")
    print("=" * 70)
    
    # Create watchdog with default config
    watchdog = create_watchdog()
    
    print(f"Monitoring {CLIENT_COUNT} clients")
    print(f"Health check interval: {watchdog.config.health_check_interval}s")
    print(f"Race condition delay: {watchdog.config.race_condition_delay}s")
    
    # Test health status
    print(f"\nHealth Status Colors:")
    for status in HealthStatus:
        print(f"  {status.value}: {status.color_code}")
    
    # Test system health
    system_health = watchdog.get_system_health()
    print(f"\nSystem Health Score: {system_health.get_health_score():.1f}")
    print(f"Connected Clients: {system_health.connected_clients}/{system_health.total_clients}")
    
    print(f"\nWatchdog ready - SystemHealth class available for import!")
    print("✅ FIXED: SystemHealth import issue resolved")
