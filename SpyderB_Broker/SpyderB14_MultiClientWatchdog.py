#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB14_MultiClientWatchdog.py
Group: B (Broker/Connection)
Purpose: Multi-client health monitoring and recovery system
Author: Mohamed Talib
Date Created: 2025-08-03
Last Updated: 2025-08-03 Time: 12:45:00

Description:
    Implements the advanced watchdog system from the stability plan with
    health monitoring, automatic recovery, and performance metrics for all
    9 client connections. Includes Eastern time scheduling and maintenance
    window awareness.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
import logging
import signal
import json
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
import threading
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz
import psutil
from ib_insync import IB, util, Contract

# ==============================================================================
# MONITORING IMPORTS (OPTIONAL)
# ==============================================================================
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    print("Warning: prometheus_client not available - metrics disabled")

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager, ClientInfo
    )
    from SpyderB_Broker.SpyderB13_GatewayConfig import (
        GatewayConfig, GatewayManager, ClientConfig, get_client_allocation
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder modules: {e}")
    # Create minimal fallbacks
    MultiClientDataManager = None
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_RECONNECT_ATTEMPTS = 10
HEALTH_CHECK_INTERVAL = 30  # seconds
CRITICAL_LATENCY_MS = 100
WARNING_LATENCY_MS = 50
MEMORY_WARNING_THRESHOLD = 0.80  # 80% memory usage
CPU_WARNING_THRESHOLD = 0.70  # 70% CPU usage

# ==============================================================================
# ENUMS
# ==============================================================================
class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = auto()
    WARNING = auto()
    CRITICAL = auto()
    DISCONNECTED = auto()

class RecoveryAction(Enum):
    """Recovery action types"""
    NONE = auto()
    RECONNECT = auto()
    RESTART_CLIENT = auto()
    RESTART_GATEWAY = auto()
    ALERT_OPERATOR = auto()

# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class ClientHealth:
    """Health status for a single client"""
    client_id: int
    timestamp: datetime
    status: HealthStatus
    connected: bool
    functional: bool
    latency_ms: Optional[float]
    error_count: int
    last_error: Optional[str]
    memory_usage_mb: Optional[float]
    cpu_percent: Optional[float]
    score: int  # 0-100 health score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'client_id': self.client_id,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.name,
            'connected': self.connected,
            'functional': self.functional,
            'latency_ms': self.latency_ms,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_percent': self.cpu_percent,
            'score': self.score
        }

@dataclass
class SystemHealth:
    """Overall system health status"""
    timestamp: datetime
    overall_status: HealthStatus
    client_health: Dict[int, ClientHealth]
    gateway_connected: bool
    memory_usage_percent: float
    cpu_usage_percent: float
    active_clients: int
    critical_clients: List[int]
    warnings: List[str]

# ==============================================================================
# METRICS SETUP (IF PROMETHEUS AVAILABLE)
# ==============================================================================
if HAS_PROMETHEUS:
    # Gateway metrics
    connection_status = Gauge('ib_gateway_connected', 'IB Gateway connection status')
    latency_histogram = Histogram('ib_gateway_latency_ms', 'IB Gateway latency',
                                 buckets=[10, 25, 50, 100, 200, 500, 1000])
    error_counter = Counter('ib_gateway_errors_total', 'Total IB Gateway errors', ['error_code'])
    restart_counter = Counter('ib_gateway_restarts_total', 'Total Gateway restarts')
    health_check_gauge = Gauge('ib_gateway_health_score', 'Overall health score (0-100)')
    
    # Client-specific metrics
    client_connected = Gauge('ib_client_connected', 'Client connection status', ['client_id'])
    client_latency = Histogram('ib_client_latency_ms', 'Client latency', ['client_id'],
                              buckets=[5, 10, 25, 50, 100, 200, 500])
    client_errors = Counter('ib_client_errors_total', 'Client errors', ['client_id', 'error_code'])
    client_health_score = Gauge('ib_client_health_score', 'Client health score', ['client_id'])

# ==============================================================================
# RATE LIMITER CLASS
# ==============================================================================
class RateLimiter:
    """Rate limiter for IB API requests"""
    
    def __init__(self, requests_per_second: int):
        """Initialize rate limiter"""
        self.requests_per_second = requests_per_second
        self.requests = deque()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        async with self.lock:
            now = time.time()
            
            # Remove requests older than 1 second
            while self.requests and now - self.requests[0] >= 1.0:
                self.requests.popleft()
            
            # If at limit, wait
            if len(self.requests) >= self.requests_per_second:
                wait_time = 1.0 - (now - self.requests[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    # Remove old requests after waiting
                    now = time.time()
                    while self.requests and now - self.requests[0] >= 1.0:
                        self.requests.popleft()
            
            self.requests.append(now)

# ==============================================================================
# MULTI-CLIENT WATCHDOG CLASS
# ==============================================================================
class MultiClientWatchdog:
    """Advanced watchdog for multi-client IB Gateway stability"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        """
        Initialize Multi-Client Watchdog.
        
        Args:
            config: Gateway configuration (creates default if None)
        """
        self.config = config or GatewayConfig()
        self.gateway_manager = GatewayManager(self.config)
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
        
        # Setup error handler
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        # Initialize data manager if available
        self.data_manager = MultiClientDataManager() if MultiClientDataManager else None
        
        # Client connections
        self.clients: Dict[int, IB] = {}
        self.client_configs = get_client_allocation()
        
        # Health tracking
        self.client_health: Dict[int, ClientHealth] = {}
        self.last_successful_health_check: Dict[int, datetime] = {}
        self.health_check_failures: Dict[int, int] = {}
        self.reconnect_attempts: Dict[int, int] = {}
        
        # Rate limiters for each client
        self.rate_limiters: Dict[int, RateLimiter] = {}
        for client_id, client_config in self.client_configs.items():
            self.rate_limiters[client_id] = RateLimiter(client_config.rate_limit)
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Eastern timezone
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        self.logger.info("MultiClientWatchdog initialized with %d clients", 
                        len(self.client_configs))
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    async def initialize_all_clients(self) -> bool:
        """
        Initialize all 9 client connections in priority order.
        
        Returns:
            True if all critical clients connected successfully
        """
        # Priority order: Order execution first, then admin, then core data
        priority_order = [1, 0, 2, 3, 4, 5, 6, 7, 8]
        critical_clients = [0, 1, 2, 3]  # Must connect successfully
        
        success_count = 0
        critical_success = True
        
        for client_id in priority_order:
            try:
                success = await self.connect_client(client_id)
                if success:
                    success_count += 1
                    self.logger.info("✓ Client %d connected successfully", client_id)
                elif client_id in critical_clients:
                    critical_success = False
                    self.logger.error("✗ Critical client %d failed to connect", client_id)
                else:
                    self.logger.warning("⚠ Non-critical client %d failed to connect", client_id)
                
                # Prevent overwhelming Gateway
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.error("Failed to initialize client %d: %s", client_id, e)
                if client_id in critical_clients:
                    critical_success = False
        
        self.logger.info("Client initialization complete: %d/%d connected", 
                        success_count, len(priority_order))
        
        return critical_success
    
    async def connect_client(self, client_id: int) -> bool:
        """
        Connect a specific client with health verification.
        
        Args:
            client_id: Client ID to connect
            
        Returns:
            True if connection successful
        """
        try:
            client_config = self.client_configs.get(client_id)
            if not client_config:
                self.logger.error("No configuration for client %d", client_id)
                return False
            
            self.logger.info("Connecting client %d: %s", 
                           client_id, client_config.description)
            
            # Create IB client
            ib = IB()
            
            # Connect with timeout
            await asyncio.wait_for(
                ib.connectAsync(
                    host='127.0.0.1',
                    port=self.config.get_current_api_port(),
                    clientId=client_id,
                    timeout=30
                ),
                timeout=self.config.connection_timeout
            )
            
            if ib.isConnected():
                # Verify functional connection
                server_time = await asyncio.wait_for(
                    ib.reqCurrentTimeAsync(),
                    timeout=5.0
                )
                
                if server_time:
                    # Configure client based on purpose
                    await self._configure_client(client_id, ib, client_config)
                    
                    # Store client
                    self.clients[client_id] = ib
                    
                    # Update metrics
                    if HAS_PROMETHEUS:
                        client_connected.labels(client_id=str(client_id)).set(1)
                    
                    # Initialize health tracking
                    self.reconnect_attempts[client_id] = 0
                    self.health_check_failures[client_id] = 0
                    
                    return True
            
            return False
            
        except asyncio.TimeoutError:
            self.logger.error("Connection timeout for client %d", client_id)
            return False
        except Exception as e:
            self.logger.error("Failed to connect client %d: %s", client_id, e)
            if HAS_PROMETHEUS:
                client_connected.labels(client_id=str(client_id)).set(0)
                client_errors.labels(client_id=str(client_id), 
                                   error_code='CONNECTION').inc()
            return False
    
    async def _configure_client(self, client_id: int, ib: IB, config: ClientConfig):
        """Configure client based on its purpose"""
        # Client 1 (Order Execution) - NO market data subscriptions
        if client_id == 1:
            self.logger.info("Client 1 configured for order execution only - no market data")
            return
        
        # Client 0 (Administrative) - No market data needed
        if client_id == 0:
            self.logger.info("Client 0 configured for administrative tasks")
            return
        
        # Other clients - Configure market data if needed
        if config.symbols:
            self.logger.info("Client %d will subscribe to %d symbols", 
                           client_id, len(config.symbols))
            # Note: Actual subscription would be handled by data manager
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    async def comprehensive_health_check(self, client_id: int) -> ClientHealth:
        """
        Perform detailed health check for a client.
        
        Args:
            client_id: Client ID to check
            
        Returns:
            ClientHealth object with status
        """
        health = ClientHealth(
            client_id=client_id,
            timestamp=datetime.now(self.eastern_tz),
            status=HealthStatus.DISCONNECTED,
            connected=False,
            functional=False,
            latency_ms=None,
            error_count=self.health_check_failures.get(client_id, 0),
            last_error=None,
            memory_usage_mb=None,
            cpu_percent=None,
            score=0
        )
        
        try:
            # Check process resources
            if HAS_PSUTIL:
                process = psutil.Process()
                health.memory_usage_mb = process.memory_info().rss / 1024 / 1024
                health.cpu_percent = process.cpu_percent(interval=0.1)
            
            # Check client connection
            client = self.clients.get(client_id)
            if not client or not client.isConnected():
                health.status = HealthStatus.DISCONNECTED
                return health
            
            health.connected = True
            
            # Test latency
            start = time.time()
            server_time = await asyncio.wait_for(
                client.reqCurrentTimeAsync(),
                timeout=5.0
            )
            
            if server_time:
                latency = (time.time() - start) * 1000
                health.latency_ms = round(latency, 2)
                health.functional = True
                
                # Update metrics
                if HAS_PROMETHEUS:
                    client_latency.labels(client_id=str(client_id)).observe(latency)
                
                # Calculate health score and status
                health.score, health.status = self._calculate_health_score(
                    latency, health.error_count
                )
                
                # Update metrics
                if HAS_PROMETHEUS:
                    client_health_score.labels(client_id=str(client_id)).set(health.score)
                
                # Reset failure counter on success
                self.health_check_failures[client_id] = 0
                self.last_successful_health_check[client_id] = datetime.now(self.eastern_tz)
            
        except asyncio.TimeoutError:
            health.last_error = "Health check timeout"
            health.status = HealthStatus.CRITICAL
            self.health_check_failures[client_id] = self.health_check_failures.get(client_id, 0) + 1
        except Exception as e:
            health.last_error = str(e)
            health.status = HealthStatus.CRITICAL
            self.health_check_failures[client_id] = self.health_check_failures.get(client_id, 0) + 1
            self.logger.error("Health check failed for client %d: %s", client_id, e)
        
        # Store health status
        self.client_health[client_id] = health
        
        return health
    
    def _calculate_health_score(self, latency_ms: float, error_count: int) -> Tuple[int, HealthStatus]:
        """
        Calculate health score based on latency and errors.
        
        Returns:
            Tuple of (score, status)
        """
        score = 100
        
        # Deduct for latency
        if latency_ms < 10:
            pass  # Perfect
        elif latency_ms < 25:
            score -= 10
        elif latency_ms < WARNING_LATENCY_MS:
            score -= 20
        elif latency_ms < CRITICAL_LATENCY_MS:
            score -= 40
        else:
            score -= 60
        
        # Deduct for errors
        score -= min(error_count * 5, 30)
        
        # Determine status
        score = max(0, score)
        if score >= 80:
            status = HealthStatus.HEALTHY
        elif score >= 60:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL
        
        return score, status
    
    async def check_all_clients(self) -> SystemHealth:
        """
        Check health of all clients and return system status.
        
        Returns:
            SystemHealth object with overall status
        """
        client_health_results = {}
        critical_clients = []
        warnings = []
        
        # Check each client
        for client_id in self.client_configs.keys():
            health = await self.comprehensive_health_check(client_id)
            client_health_results[client_id] = health
            
            if health.status == HealthStatus.CRITICAL:
                critical_clients.append(client_id)
                warnings.append(f"Client {client_id} is in critical state")
            elif health.status == HealthStatus.WARNING:
                warnings.append(f"Client {client_id} has warnings")
        
        # Check system resources
        memory_percent = psutil.virtual_memory().percent if HAS_PSUTIL else 0
        cpu_percent = psutil.cpu_percent(interval=0.1) if HAS_PSUTIL else 0
        
        if memory_percent > MEMORY_WARNING_THRESHOLD * 100:
            warnings.append(f"High memory usage: {memory_percent:.1f}%")
        
        if cpu_percent > CPU_WARNING_THRESHOLD * 100:
            warnings.append(f"High CPU usage: {cpu_percent:.1f}%")
        
        # Determine overall status
        if critical_clients:
            overall_status = HealthStatus.CRITICAL
        elif warnings:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.HEALTHY
        
        # Count active clients
        active_clients = sum(1 for h in client_health_results.values() if h.connected)
        
        system_health = SystemHealth(
            timestamp=datetime.now(self.eastern_tz),
            overall_status=overall_status,
            client_health=client_health_results,
            gateway_connected=active_clients > 0,
            memory_usage_percent=memory_percent,
            cpu_usage_percent=cpu_percent,
            active_clients=active_clients,
            critical_clients=critical_clients,
            warnings=warnings
        )
        
        # Update overall health metric
        if HAS_PROMETHEUS:
            overall_score = sum(h.score for h in client_health_results.values()) // len(client_health_results)
            health_check_gauge.set(overall_score)
        
        return system_health
    
    # ==========================================================================
    # RECOVERY PROCEDURES
    # ==========================================================================
    async def attempt_recovery(self, client_id: int) -> bool:
        """
        Attempt to recover a failed client connection.
        
        Args:
            client_id: Client ID to recover
            
        Returns:
            True if recovery successful
        """
        self.reconnect_attempts[client_id] = self.reconnect_attempts.get(client_id, 0) + 1
        
        if self.reconnect_attempts[client_id] > MAX_RECONNECT_ATTEMPTS:
            self.logger.error("Max reconnection attempts reached for client %d", client_id)
            if HAS_PROMETHEUS:
                client_errors.labels(client_id=str(client_id), 
                                   error_code='MAX_RECONNECTS').inc()
            return False
        
        self.logger.info("Attempting recovery for client %d (attempt %d/%d)",
                        client_id, self.reconnect_attempts[client_id], MAX_RECONNECT_ATTEMPTS)
        
        # Disconnect existing client if present
        if client_id in self.clients:
            try:
                self.clients[client_id].disconnect()
            except:
                pass
            del self.clients[client_id]
        
        # Wait before reconnecting
        await asyncio.sleep(5)
        
        # Attempt reconnection
        success = await self.connect_client(client_id)
        
        if success:
            self.logger.info("✓ Successfully recovered client %d", client_id)
            self.reconnect_attempts[client_id] = 0
            if HAS_PROMETHEUS:
                restart_counter.inc()
        else:
            self.logger.error("✗ Failed to recover client %d", client_id)
        
        return success
    
    # ==========================================================================
    # MONITORING LOOP
    # ==========================================================================
    async def start_monitoring(self):
        """Start the monitoring loop"""
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Start Prometheus metrics server if available
        if HAS_PROMETHEUS:
            start_http_server(9090)
            self.logger.info("Prometheus metrics server started on port 9090")
        
        self.logger.info("Watchdog monitoring started")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check if in maintenance window
                if self.gateway_manager.is_maintenance_window():
                    self.logger.info("In IB maintenance window - skipping health checks")
                    await asyncio.sleep(60)
                    continue
                
                # Perform health checks
                system_health = await self.check_all_clients()
                
                # Log status
                self.logger.info("System Health: %s | Active Clients: %d/%d | Memory: %.1f%% | CPU: %.1f%%",
                               system_health.overall_status.name,
                               system_health.active_clients,
                               len(self.client_configs),
                               system_health.memory_usage_percent,
                               system_health.cpu_usage_percent)
                
                # Handle critical clients
                for client_id in system_health.critical_clients:
                    client_config = self.client_configs.get(client_id)
                    if client_config and client_config.priority == 'CRITICAL':
                        self.logger.warning("Critical client %d needs recovery", client_id)
                        asyncio.create_task(self.attempt_recovery(client_id))
                
                # Wait before next check
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", e)
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    
    async def stop_monitoring(self):
        """Stop the monitoring loop"""
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        for client_id, client in self.clients.items():
            try:
                client.disconnect()
                self.logger.info("Disconnected client %d", client_id)
            except:
                pass
        
        self.clients.clear()
        self.logger.info("Watchdog monitoring stopped")
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def get_client_health(self, client_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current health status for a client.
        
        Args:
            client_id: Client ID
            
        Returns:
            Health status dictionary or None
        """
        health = self.client_health.get(client_id)
        return health.to_dict() if health else None
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status summary.
        
        Returns:
            System status dictionary
        """
        active_clients = sum(1 for c in self.clients.values() if c.isConnected())
        
        return {
            'timestamp': datetime.now(self.eastern_tz).isoformat(),
            'active_clients': active_clients,
            'total_clients': len(self.client_configs),
            'is_trading_hours': self.gateway_manager.is_trading_hours(),
            'is_extended_hours': self.gateway_manager.is_extended_hours(),
            'is_maintenance_window': self.gateway_manager.is_maintenance_window(),
            'client_health': {
                client_id: self.get_client_health(client_id)
                for client_id in self.client_configs.keys()
            }
        }
    
    def save_health_report(self, filepath: Path):
        """Save health report to file"""
        report = self.get_system_status()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        self.logger.info("Health report saved to %s", filepath)

# ==============================================================================
# MODULE TEST
# ==============================================================================
async def test_watchdog():
    """Test the watchdog functionality"""
    print("Testing MultiClientWatchdog...")
    
    # Create watchdog
    watchdog = MultiClientWatchdog()
    
    # Initialize clients
    print("\nInitializing clients...")
    success = await watchdog.initialize_all_clients()
    print(f"  Critical clients connected: {success}")
    
    # Perform health check
    print("\nPerforming health checks...")
    system_health = await watchdog.check_all_clients()
    
    print(f"\nSystem Health Report:")
    print(f"  Status: {system_health.overall_status.name}")
    print(f"  Active Clients: {system_health.active_clients}/{len(watchdog.client_configs)}")
    print(f"  Memory Usage: {system_health.memory_usage_percent:.1f}%")
    print(f"  CPU Usage: {system_health.cpu_usage_percent:.1f}%")
    
    if system_health.warnings:
        print(f"\nWarnings:")
        for warning in system_health.warnings:
            print(f"  ⚠ {warning}")
    
    print(f"\nClient Status:")
    for client_id, health in system_health.client_health.items():
        status_symbol = "✓" if health.connected else "✗"
        print(f"  {status_symbol} Client {client_id}: {health.status.name} (Score: {health.score})")
        if health.latency_ms:
            print(f"    Latency: {health.latency_ms:.1f}ms")
    
    # Save report
    report_path = Path("health_report.json")
    watchdog.save_health_report(report_path)
    print(f"\nHealth report saved to {report_path}")
    
    # Stop watchdog
    await watchdog.stop_monitoring()
    print("\n✓ Watchdog test completed")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_watchdog())