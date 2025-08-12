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
Last Updated: 2025-08-12 Time: 17:15:00

Description:
    Implements the advanced watchdog system from the stability plan with
    health monitoring, automatic recovery, and performance metrics for all
    9 client connections. Includes Eastern time scheduling and maintenance
    window awareness.
    
    UPDATED: Client IDs now range from 1-9 instead of 0-8 to match dashboard display.
    Order execution moved to Client 2 for highest priority trading operations.
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
    # Fallback classes
    SpyderLogger = None
    SpyderErrorHandler = None
    GatewayConfig = None
    MultiClientDataManager = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# UPDATED: Client monitoring constants for 1-9 range
MIN_CLIENT_ID = 1
MAX_CLIENT_ID = 9
TOTAL_CLIENTS = 9

# Health check intervals (seconds)
HEALTH_CHECK_INTERVAL = 30
RECOVERY_ATTEMPT_INTERVAL = 120
SYSTEM_METRICS_INTERVAL = 60

# Thresholds
MAX_RECONNECT_ATTEMPTS = 5
MAX_CONSECUTIVE_FAILURES = 3
MIN_HEALTHY_CLIENTS = 6
CRITICAL_CLIENT_THRESHOLD = 4

# Eastern timezone
EASTERN_TZ = pytz.timezone('US/Eastern')

# ==============================================================================
# ENUMS
# ==============================================================================
class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"

class ClientState(Enum):
    """Client connection state"""
    CONNECTING = auto()
    CONNECTED = auto()
    DISCONNECTED = auto()
    RECONNECTING = auto()
    FAILED = auto()

class SystemState(Enum):
    """Overall system state"""
    STARTING = auto()
    HEALTHY = auto()
    DEGRADED = auto()
    CRITICAL = auto()
    MAINTENANCE = auto()
    SHUTDOWN = auto()

# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class ClientHealth:
    """Health information for a single client"""
    client_id: int
    state: ClientState = ClientState.DISCONNECTED
    status: HealthStatus = HealthStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    consecutive_failures: int = 0
    reconnect_attempts: int = 0
    total_connections: int = 0
    total_disconnections: int = 0
    total_errors: int = 0
    data_messages_received: int = 0
    last_error: Optional[str] = None
    connection_time: Optional[datetime] = None
    is_critical: bool = False

@dataclass
class SystemHealth:
    """Overall system health information"""
    state: SystemState = SystemState.STARTING
    status: HealthStatus = HealthStatus.OFFLINE
    total_clients: int = TOTAL_CLIENTS
    connected_clients: int = 0
    healthy_clients: int = 0
    critical_clients_connected: int = 0
    critical_clients_required: int = 4  # UPDATED: 1,2,3,4 are critical (was 0,1,2,3)
    uptime: timedelta = field(default_factory=lambda: timedelta())
    last_health_check: Optional[datetime] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    network_latency: float = 0.0

@dataclass  
class RateLimiter:
    """Simple rate limiter for client requests"""
    max_requests: int
    window_seconds: float = 1.0
    requests: deque = field(default_factory=deque)
    
    def can_proceed(self) -> bool:
        """Check if request can proceed within rate limit"""
        now = time.time()
        
        # Remove old requests outside window
        while self.requests and self.requests[0] <= now - self.window_seconds:
            self.requests.popleft()
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        
        return False

# ==============================================================================
# MAIN WATCHDOG CLASS - UPDATED FOR 1-9 RANGE
# ==============================================================================
class MultiClientWatchdog:
    """
    Advanced multi-client health monitoring and recovery system.
    
    UPDATED: Monitors clients 1-9 instead of 0-8, with Order Execution
    priority moved to Client 2 for optimal trading performance.
    """
    
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
        
        # Client connections - UPDATED for 1-9 range
        self.clients: Dict[int, IB] = {}
        self.client_configs = get_client_allocation()
        
        # Health tracking - UPDATED for 1-9 range
        self.client_health: Dict[int, ClientHealth] = {}
        self.last_successful_health_check: Dict[int, datetime] = {}
        self.health_check_failures: Dict[int, int] = {}
        self.reconnect_attempts: Dict[int, int] = {}
        
        # Initialize health tracking for clients 1-9
        for client_id in range(MIN_CLIENT_ID, MAX_CLIENT_ID + 1):
            self.client_health[client_id] = ClientHealth(
                client_id=client_id,
                is_critical=client_id in self.get_critical_client_ids()
            )
            self.last_successful_health_check[client_id] = datetime.now()
            self.health_check_failures[client_id] = 0
            self.reconnect_attempts[client_id] = 0
        
        # Rate limiters for each client (1-9)
        self.rate_limiters: Dict[int, RateLimiter] = {}
        for client_id, client_config in self.client_configs.items():
            self.rate_limiters[client_id] = RateLimiter(client_config.rate_limit)
        
        # System health
        self.system_health = SystemHealth()
        self.start_time = datetime.now()
        
        # Monitoring
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Eastern timezone
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        self.logger.info("MultiClientWatchdog initialized with %d clients (1-9)", 
                        len(self.client_configs))

    def get_critical_client_ids(self) -> List[int]:
        """Get list of critical client IDs that must be connected"""
        # UPDATED: Critical clients are now 1, 2, 3, 4 (was 0, 1, 2, 3)
        return [1, 2, 3, 4]

    def get_order_execution_client_id(self) -> int:
        """Get the client ID used for order execution"""
        return 2  # UPDATED: Order execution is now Client 2 (was Client 1)

    def get_administrative_client_id(self) -> int:
        """Get the client ID used for administrative tasks"""
        return 1  # UPDATED: Administrative is now Client 1 (was Client 0)

    # ==========================================================================
    # CONNECTION MANAGEMENT - UPDATED FOR 1-9 RANGE
    # ==========================================================================
    async def initialize_all_clients(self) -> bool:
        """
        Initialize all 9 client connections in priority order (1-9).
        
        Returns:
            True if all critical clients connected successfully
        """
        # UPDATED: Priority order with Order execution first, then admin, then core data
        priority_order = [2, 1, 3, 4, 5, 6, 7, 8, 9]  # UPDATED from [1, 0, 2, 3, 4, 5, 6, 7, 8]
        critical_clients = [1, 2, 3, 4]  # UPDATED from [0, 1, 2, 3]
        
        success_count = 0
        critical_success = True
        
        self.logger.info("🚀 Initializing clients in priority order: %s", priority_order)
        
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
        
        # Update system health
        self.system_health.connected_clients = success_count
        self.system_health.critical_clients_connected = len([
            c for c in critical_clients if c in [
                cid for cid, health in self.client_health.items() 
                if health.state == ClientState.CONNECTED
            ]
        ])
        
        return critical_success
    
    async def connect_client(self, client_id: int) -> bool:
        """
        Connect a specific client with health verification.
        
        Args:
            client_id: Client ID to connect (1-9 range)
            
        Returns:
            True if connection successful
        """
        try:
            # Validate client ID is in 1-9 range
            if client_id < MIN_CLIENT_ID or client_id > MAX_CLIENT_ID:
                self.logger.error("Invalid client ID %d. Valid range: %d-%d", 
                                client_id, MIN_CLIENT_ID, MAX_CLIENT_ID)
                return False
            
            client_config = self.client_configs.get(client_id)
            if not client_config:
                self.logger.error("No configuration for client %d", client_id)
                return False
            
            self.logger.info("Connecting client %d: %s", 
                           client_id, client_config.description)
            
            # Update client state
            self.client_health[client_id].state = ClientState.CONNECTING
            
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
                    # Connection successful
                    self.clients[client_id] = ib
                    health = self.client_health[client_id]
                    health.state = ClientState.CONNECTED
                    health.status = HealthStatus.HEALTHY
                    health.connection_time = datetime.now()
                    health.total_connections += 1
                    health.consecutive_failures = 0
                    health.reconnect_attempts = 0
                    health.last_heartbeat = datetime.now()
                    
                    self.logger.info("✅ Client %d connected and verified", client_id)
                    return True
                else:
                    self.logger.error("❌ Client %d connected but verification failed", client_id)
                    await self._handle_connection_failure(client_id, "Verification failed")
                    return False
            else:
                self.logger.error("❌ Client %d connection failed", client_id)
                await self._handle_connection_failure(client_id, "Connection failed")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error("❌ Client %d connection timeout", client_id)
            await self._handle_connection_failure(client_id, "Connection timeout")
            return False
        except Exception as e:
            self.logger.error("❌ Client %d connection error: %s", client_id, e)
            await self._handle_connection_failure(client_id, str(e))
            return False

    async def disconnect_client(self, client_id: int) -> bool:
        """
        Disconnect a specific client.
        
        Args:
            client_id: Client ID to disconnect (1-9 range)
            
        Returns:
            True if disconnection successful
        """
        try:
            if client_id not in self.clients:
                self.logger.warning("Client %d not found for disconnection", client_id)
                return True
            
            ib = self.clients[client_id]
            if ib.isConnected():
                ib.disconnect()
                self.logger.info("🔌 Client %d disconnected", client_id)
            
            # Clean up
            del self.clients[client_id]
            
            # Update health
            health = self.client_health[client_id]
            health.state = ClientState.DISCONNECTED
            health.status = HealthStatus.OFFLINE
            health.total_disconnections += 1
            
            return True
            
        except Exception as e:
            self.logger.error("❌ Error disconnecting client %d: %s", client_id, e)
            return False

    async def _handle_connection_failure(self, client_id: int, error_msg: str):
        """Handle connection failure for a client"""
        health = self.client_health[client_id]
        health.state = ClientState.FAILED
        health.status = HealthStatus.CRITICAL
        health.consecutive_failures += 1
        health.total_errors += 1
        health.last_error = error_msg
        
        # Clean up failed connection
        if client_id in self.clients:
            try:
                self.clients[client_id].disconnect()
            except:
                pass
            del self.clients[client_id]

    # ==========================================================================
    # HEALTH MONITORING - UPDATED FOR 1-9 RANGE
    # ==========================================================================
    async def start_monitoring(self):
        """Start the health monitoring system"""
        try:
            self.running = True
            self.system_health.state = SystemState.STARTING
            
            self.logger.info("🔍 Starting health monitoring for clients 1-9...")
            
            # Initialize all clients
            critical_success = await self.initialize_all_clients()
            
            if critical_success:
                self.system_health.state = SystemState.HEALTHY
                self.logger.info("✅ All critical clients connected - system healthy")
            else:
                self.system_health.state = SystemState.DEGRADED
                self.logger.warning("⚠️ Some critical clients failed - system degraded")
            
            # Start monitoring loop
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            await self.monitoring_task
            
        except Exception as e:
            self.logger.error("❌ Error starting monitoring: %s", e)
            self.system_health.state = SystemState.CRITICAL

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("🔄 Starting monitoring loop")
        
        while self.running:
            try:
                # Check if in maintenance window
                if self.gateway_manager.is_maintenance_window():
                    if self.system_health.state != SystemState.MAINTENANCE:
                        self.logger.info("🛠️ Entering maintenance window")
                        self.system_health.state = SystemState.MAINTENANCE
                    
                    # Reduced monitoring during maintenance
                    await asyncio.sleep(300)  # 5 minutes
                    continue
                else:
                    # Exit maintenance mode if needed
                    if self.system_health.state == SystemState.MAINTENANCE:
                        self.logger.info("✅ Exiting maintenance window")
                        await self._assess_system_health()
                
                # Perform health checks
                await self._perform_health_checks()
                
                # Update system metrics
                await self._update_system_metrics()
                
                # Assess overall health
                await self._assess_system_health()
                
                # Auto-recovery if needed
                await self._perform_recovery_actions()
                
                # Wait before next cycle
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error("❌ Error in monitoring loop: %s", e)
                await asyncio.sleep(10)
        
        self.logger.info("🛑 Monitoring loop stopped")

    async def _perform_health_checks(self):
        """Perform health checks on all clients (1-9)"""
        current_time = datetime.now()
        
        for client_id in range(MIN_CLIENT_ID, MAX_CLIENT_ID + 1):
            try:
                await self._check_client_health(client_id, current_time)
            except Exception as e:
                self.logger.error("❌ Error checking client %d health: %s", client_id, e)

    async def _check_client_health(self, client_id: int, current_time: datetime):
        """Check health of a specific client"""
        health = self.client_health[client_id]
        
        if client_id not in self.clients:
            # Client not connected
            health.state = ClientState.DISCONNECTED
            health.status = HealthStatus.OFFLINE
            return
        
        ib = self.clients[client_id]
        
        try:
            if not ib.isConnected():
                # Lost connection
                health.state = ClientState.DISCONNECTED
                health.status = HealthStatus.CRITICAL
                health.consecutive_failures += 1
                self.logger.warning("⚠️ Client %d lost connection", client_id)
                return
            
            # Test connection with heartbeat
            server_time = await asyncio.wait_for(
                ib.reqCurrentTimeAsync(),
                timeout=5.0
            )
            
            if server_time:
                # Healthy
                health.state = ClientState.CONNECTED
                health.status = HealthStatus.HEALTHY
                health.last_heartbeat = current_time
                health.consecutive_failures = 0
                self.last_successful_health_check[client_id] = current_time
            else:
                # Heartbeat failed
                health.consecutive_failures += 1
                health.status = HealthStatus.DEGRADED
                self.logger.warning("⚠️ Client %d heartbeat failed", client_id)
                
        except asyncio.TimeoutError:
            health.consecutive_failures += 1
            health.status = HealthStatus.DEGRADED
            self.logger.warning("⚠️ Client %d heartbeat timeout", client_id)
        except Exception as e:
            health.consecutive_failures += 1
            health.status = HealthStatus.CRITICAL
            health.last_error = str(e)
            self.logger.error("❌ Client %d health check error: %s", client_id, e)

    async def _update_system_metrics(self):
        """Update system-wide metrics"""
        try:
            # CPU and memory usage
            self.system_health.cpu_usage = psutil.cpu_percent(interval=1)
            self.system_health.memory_usage = psutil.virtual_memory().percent
            
            # Count healthy clients
            connected_count = 0
            healthy_count = 0
            critical_connected = 0
            
            critical_clients = self.get_critical_client_ids()
            
            for client_id, health in self.client_health.items():
                if health.state == ClientState.CONNECTED:
                    connected_count += 1
                    if health.status == HealthStatus.HEALTHY:
                        healthy_count += 1
                    if client_id in critical_clients:
                        critical_connected += 1
            
            # Update system health
            self.system_health.connected_clients = connected_count
            self.system_health.healthy_clients = healthy_count
            self.system_health.critical_clients_connected = critical_connected
            self.system_health.uptime = datetime.now() - self.start_time
            self.system_health.last_health_check = datetime.now()
            
        except Exception as e:
            self.logger.error("❌ Error updating system metrics: %s", e)

    async def _assess_system_health(self):
        """Assess overall system health"""
        try:
            critical_clients = self.get_critical_client_ids()
            critical_connected = self.system_health.critical_clients_connected
            total_connected = self.system_health.connected_clients
            
            # Determine system state
            if critical_connected == len(critical_clients) and total_connected >= MIN_HEALTHY_CLIENTS:
                self.system_health.state = SystemState.HEALTHY
                self.system_health.status = HealthStatus.HEALTHY
            elif critical_connected >= CRITICAL_CLIENT_THRESHOLD:
                self.system_health.state = SystemState.DEGRADED
                self.system_health.status = HealthStatus.DEGRADED
            else:
                self.system_health.state = SystemState.CRITICAL
                self.system_health.status = HealthStatus.CRITICAL
            
            # Log significant state changes
            # (This could be enhanced to track previous state)
            
        except Exception as e:
            self.logger.error("❌ Error assessing system health: %s", e)

    async def _perform_recovery_actions(self):
        """Perform automatic recovery actions"""
        try:
            critical_clients = self.get_critical_client_ids()
            
            for client_id in critical_clients:
                health = self.client_health[client_id]
                
                # Auto-reconnect failed critical clients
                if (health.state == ClientState.FAILED or 
                    health.consecutive_failures >= MAX_CONSECUTIVE_FAILURES):
                    
                    if health.reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                        self.logger.info("🔄 Attempting to recover client %d (attempt %d/%d)", 
                                       client_id, health.reconnect_attempts + 1, MAX_RECONNECT_ATTEMPTS)
                        
                        health.reconnect_attempts += 1
                        health.state = ClientState.RECONNECTING
                        
                        # Disconnect if needed
                        if client_id in self.clients:
                            await self.disconnect_client(client_id)
                        
                        # Reconnect
                        success = await self.connect_client(client_id)
                        if success:
                            self.logger.info("✅ Client %d recovery successful", client_id)
                        else:
                            self.logger.error("❌ Client %d recovery failed", client_id)
                    
        except Exception as e:
            self.logger.error("❌ Error in recovery actions: %s", e)

    # ==========================================================================
    # STATUS AND REPORTING - UPDATED FOR 1-9 RANGE
    # ==========================================================================
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            critical_clients = self.get_critical_client_ids()
            
            # Client status summary
            client_status = {}
            for client_id in range(MIN_CLIENT_ID, MAX_CLIENT_ID + 1):
                health = self.client_health[client_id]
                client_config = self.client_configs.get(client_id)
                
                client_status[client_id] = {
                    'state': health.state.name,
                    'status': health.status.value,
                    'purpose': client_config.description if client_config else 'Unknown',
                    'is_critical': health.is_critical,
                    'consecutive_failures': health.consecutive_failures,
                    'reconnect_attempts': health.reconnect_attempts,
                    'total_connections': health.total_connections,
                    'total_errors': health.total_errors,
                    'last_heartbeat': health.last_heartbeat.isoformat() if health.last_heartbeat else None,
                    'connection_time': health.connection_time.isoformat() if health.connection_time else None
                }
            
            return {
                'system': {
                    'state': self.system_health.state.name,
                    'status': self.system_health.status.value,
                    'uptime_seconds': self.system_health.uptime.total_seconds(),
                    'last_health_check': self.system_health.last_health_check.isoformat() if self.system_health.last_health_check else None
                },
                'clients': {
                    'total': self.system_health.total_clients,
                    'connected': self.system_health.connected_clients,
                    'healthy': self.system_health.healthy_clients,
                    'critical_connected': self.system_health.critical_clients_connected,
                    'critical_required': self.system_health.critical_clients_required,
                    'client_id_range': f"{MIN_CLIENT_ID}-{MAX_CLIENT_ID}",
                    'order_execution_client': self.get_order_execution_client_id(),
                    'administrative_client': self.get_administrative_client_id(),
                    'critical_client_ids': critical_clients
                },
                'performance': {
                    'cpu_usage': self.system_health.cpu_usage,
                    'memory_usage': self.system_health.memory_usage,
                    'network_latency': self.system_health.network_latency
                },
                'client_details': client_status
            }
            
        except Exception as e:
            self.logger.error("❌ Error getting system status: %s", e)
            return {'error': str(e)}

    def get_client_status(self, client_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific client"""
        try:
            if client_id not in self.client_health:
                return None
            
            health = self.client_health[client_id]
            client_config = self.client_configs.get(client_id)
            
            return {
                'client_id': client_id,
                'state': health.state.name,
                'status': health.status.value,
                'purpose': client_config.description if client_config else 'Unknown',
                'symbols': client_config.symbols if client_config else [],
                'is_critical': health.is_critical,
                'is_connected': client_id in self.clients and self.clients[client_id].isConnected(),
                'consecutive_failures': health.consecutive_failures,
                'reconnect_attempts': health.reconnect_attempts,
                'total_connections': health.total_connections,
                'total_disconnections': health.total_disconnections,
                'total_errors': health.total_errors,
                'data_messages_received': health.data_messages_received,
                'last_heartbeat': health.last_heartbeat.isoformat() if health.last_heartbeat else None,
                'connection_time': health.connection_time.isoformat() if health.connection_time else None,
                'last_error': health.last_error
            }
            
        except Exception as e:
            self.logger.error("❌ Error getting client %d status: %s", client_id, e)
            return None

    def get_health_summary(self) -> Dict[str, Any]:
        """Get simplified health summary for dashboard"""
        try:
            return {
                'overall_status': self.system_health.status.value,
                'system_state': self.system_health.state.name,
                'clients_connected': self.system_health.connected_clients,
                'clients_total': self.system_health.total_clients,
                'critical_clients_ok': self.system_health.critical_clients_connected >= CRITICAL_CLIENT_THRESHOLD,
                'order_execution_ok': self.get_order_execution_client_id() in [
                    cid for cid, health in self.client_health.items() 
                    if health.state == ClientState.CONNECTED
                ],
                'administrative_ok': self.get_administrative_client_id() in [
                    cid for cid, health in self.client_health.items() 
                    if health.state == ClientState.CONNECTED
                ],
                'uptime_minutes': int(self.system_health.uptime.total_seconds() / 60),
                'cpu_usage': self.system_health.cpu_usage,
                'memory_usage': self.system_health.memory_usage
            }
            
        except Exception as e:
            self.logger.error("❌ Error getting health summary: %s", e)
            return {'error': str(e)}

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    async def stop_monitoring(self):
        """Stop the monitoring system"""
        try:
            self.logger.info("🛑 Stopping multi-client watchdog...")
            
            self.running = False
            self.system_health.state = SystemState.SHUTDOWN
            
            # Cancel monitoring task
            if self.monitoring_task and not self.monitoring_task.done():
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Disconnect all clients
            for client_id in list(self.clients.keys()):
                await self.disconnect_client(client_id)
            
            self.logger.info("✅ Multi-client watchdog stopped")
            
        except Exception as e:
            self.logger.error("❌ Error stopping watchdog: %s", e)

    def __del__(self):
        """Cleanup on destruction"""
        if self.running:
            # Can't run async in destructor, just log
            self.logger.warning("⚠️ Watchdog destroyed while running - cleanup incomplete")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_watchdog(config: Optional[GatewayConfig] = None) -> MultiClientWatchdog:
    """
    Create a MultiClientWatchdog instance.
    
    Args:
        config: Optional gateway configuration
        
    Returns:
        MultiClientWatchdog instance
    """
    return MultiClientWatchdog(config)

async def start_monitoring_system(config: Optional[GatewayConfig] = None) -> MultiClientWatchdog:
    """
    Start the complete monitoring system.
    
    Args:
        config: Optional gateway configuration
        
    Returns:
        Running MultiClientWatchdog instance
    """
    watchdog = create_watchdog(config)
    await watchdog.start_monitoring()
    return watchdog

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution for testing and demonstration"""
    print("🚀 SPYDER B14 - Multi-Client Watchdog (UPDATED: CLIENTS 1-9)")
    print("=" * 70)
    
    try:
        # Create configuration
        if GatewayConfig:
            config = GatewayConfig()
            print(f"✅ Configuration created for clients 1-9")
        else:
            config = None
            print("⚠️ Using fallback configuration")
        
        # Create watchdog
        watchdog = create_watchdog(config)
        print(f"✅ Watchdog created")
        
        # Print configuration summary
        print(f"\n📊 Client Configuration:")
        print(f"   Client ID Range: {MIN_CLIENT_ID}-{MAX_CLIENT_ID}")
        print(f"   Total Clients: {TOTAL_CLIENTS}")
        print(f"   Critical Clients: {watchdog.get_critical_client_ids()}")
        print(f"   Order Execution: Client {watchdog.get_order_execution_client_id()}")
        print(f"   Administrative: Client {watchdog.get_administrative_client_id()}")
        
        # Test status methods
        print(f"\n🔍 Testing status methods:")
        health_summary = watchdog.get_health_summary()
        print(f"   Overall Status: {health_summary.get('overall_status', 'unknown')}")
        print(f"   System State: {health_summary.get('system_state', 'unknown')}")
        print(f"   Clients Connected: {health_summary.get('clients_connected', 0)}/{health_summary.get('clients_total', 0)}")
        
        # Test individual client status
        print(f"\n👥 Client Health Status:")
        for client_id in [1, 2, 3, 9]:  # Test a few clients
            status = watchdog.get_client_status(client_id)
            if status:
                print(f"   Client {client_id}: {status['status']} - {status['purpose']}")
            else:
                print(f"   Client {client_id}: Configuration not found")
        
        print(f"\n🎯 Watchdog test completed successfully!")
        print(f"✅ Ready for production monitoring of clients 1-9")
        
        # Note: In production, you would call:
        # await watchdog.start_monitoring()
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())