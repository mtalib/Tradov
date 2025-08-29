#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB21_GatewayStartupAutomation.py
Purpose: Automated IB Gateway Docker Container Management with Connectivity Integration
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-28 Time: 17:00:00  

Module Description:
    Advanced Docker-based IB Gateway startup automation that integrates seamlessly
    with the SpyderB20_IntegratedConnectivityManager. Manages the complete lifecycle
    of the gnzsnz/ib-gateway-docker container including credential management,
    health monitoring, automatic restarts, and coordination with connectivity
    management for optimal startup timing and VPN integration.

Key Features:
    - Docker container lifecycle management for IB Gateway v10.39
    - Integration with SpyderB20 connectivity management
    - Secure credential management and environment configuration  
    - Health monitoring with automatic recovery
    - Coordinated startup with connectivity optimization
    - VPN-aware gateway startup sequences
    - PyQt6 dashboard integration with real-time monitoring
    - Trading session scheduling and automation
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import base64
import json
import logging
import os
import subprocess
import sys
import time
import threading
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import signal
import shutil
import tempfile
import yaml
import platform

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import docker
import psutil
import pytz
from cryptography.fernet import Fernet
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTextEdit, QProgressBar, QGroupBox,
                            QCheckBox, QMessageBox, QTabWidget, QListWidget,
                            QListWidgetItem, QLineEdit, QComboBox, QSpinBox,
                            QTimeEdit, QFrame, QSplitter, QScrollArea)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt, QTime, QProcess
from PyQt6.QtGui import QFont, QColor, QIcon, QPalette

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
    
    # Import our connectivity manager
    from SpyderB_Broker.SpyderB20_IntegratedConnectivityManager import (
        IntegratedConnectivityManager, ConnectivityState, ConnectivityReport
    )
    
    SPYDER_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Some Spyder modules not available: {e}")
    SPYDER_MODULES_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Docker image configuration
IB_GATEWAY_DOCKER_IMAGE = "gnzsnz/ib-gateway-docker:latest"
DEFAULT_CONTAINER_NAME = "ib_gateway"
CONTAINER_STARTUP_TIMEOUT = 120  # seconds
CONTAINER_HEALTH_CHECK_INTERVAL = 30  # seconds

# IB Gateway configuration
TWS_MAJOR_VERSION = "1039"
GATEWAY_VERSION = "10.39"

# Port mappings
GATEWAY_API_PORTS = {
    "paper": 4002,  # Paper trading port
    "live": 4001    # Live trading port
}

VNC_PORT = 5900  # For debugging
JTS_LOG_LEVEL = "WARNING"

# Trading session timing
MARKET_OPEN_TIME = dt_time(9, 30)  # 9:30 AM ET
MARKET_CLOSE_TIME = dt_time(16, 0)  # 4:00 PM ET
PRE_MARKET_BUFFER = timedelta(minutes=30)  # Start 30min before market
POST_MARKET_BUFFER = timedelta(minutes=30)  # Keep alive 30min after market

# Container resource limits
CONTAINER_MEMORY_LIMIT = "2g"
CONTAINER_CPU_LIMIT = "1.0"

# Credential encryption
CREDENTIAL_ENCRYPTION_KEY = "SPYDER_GATEWAY_ENCRYPTION_KEY"

# ==============================================================================
# ENUMS
# ==============================================================================

class GatewayState(Enum):
    """Gateway container states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    ERROR = "error"
    UNHEALTHY = "unhealthy"

class StartupMode(Enum):
    """Gateway startup modes"""
    MANUAL = "manual"           # Manual startup only
    SCHEDULED = "scheduled"     # Start based on market hours
    CONNECTIVITY = "connectivity"  # Start when connectivity is optimal
    IMMEDIATE = "immediate"     # Start immediately

class TradingMode(Enum):
    """Trading modes"""
    PAPER = "paper"
    LIVE = "live"

class RestartReason(Enum):
    """Reasons for container restart"""
    SCHEDULED = "scheduled"
    UNHEALTHY = "unhealthy"
    CONNECTION_LOST = "connection_lost"
    RESOURCE_LIMIT = "resource_limit"
    USER_REQUEST = "user_request"
    CONNECTIVITY_OPTIMIZATION = "connectivity_optimization"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class GatewayCredentials:
    """Secure gateway credentials"""
    username: str
    password: str  # Will be encrypted
    trading_mode: TradingMode = TradingMode.PAPER
    
    def encrypt_password(self, key: bytes) -> str:
        """Encrypt the password"""
        f = Fernet(key)
        return f.encrypt(self.password.encode()).decode()
    
    def decrypt_password(self, encrypted_password: str, key: bytes) -> str:
        """Decrypt the password"""
        f = Fernet(key)
        return f.decrypt(encrypted_password.encode()).decode()

@dataclass
class ContainerConfig:
    """Docker container configuration"""
    container_name: str = DEFAULT_CONTAINER_NAME
    image: str = IB_GATEWAY_DOCKER_IMAGE
    trading_mode: TradingMode = TradingMode.PAPER
    api_port: Optional[int] = None
    vnc_port: int = VNC_PORT
    enable_vnc: bool = True
    memory_limit: str = CONTAINER_MEMORY_LIMIT
    cpu_limit: str = CONTAINER_CPU_LIMIT
    auto_remove: bool = False
    restart_policy: str = "unless-stopped"
    timezone: str = "America/New_York"
    jts_log_level: str = JTS_LOG_LEVEL
    
    def __post_init__(self):
        if self.api_port is None:
            self.api_port = GATEWAY_API_PORTS[self.trading_mode.value]

@dataclass
class GatewayStatus:
    """Current gateway status"""
    state: GatewayState = GatewayState.STOPPED
    container_id: Optional[str] = None
    start_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    restart_count: int = 0
    last_restart_reason: Optional[RestartReason] = None
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    memory_limit_mb: float = 0.0
    api_port: Optional[int] = None
    connectivity_state: Optional[ConnectivityState] = None

@dataclass
class StartupSequence:
    """Gateway startup sequence configuration"""
    mode: StartupMode = StartupMode.SCHEDULED
    scheduled_start_time: Optional[dt_time] = None
    scheduled_stop_time: Optional[dt_time] = None
    wait_for_connectivity: bool = True
    max_connectivity_wait: int = 300  # seconds
    enable_vpn_coordination: bool = True
    pre_market_buffer_minutes: int = 30
    post_market_buffer_minutes: int = 30

# ==============================================================================
# GATEWAY STARTUP AUTOMATION ENGINE
# ==============================================================================

class GatewayStartupAutomation:
    """
    Advanced Docker-based IB Gateway automation with connectivity integration.
    
    This class provides comprehensive automation of IB Gateway containers with:
    - Docker container lifecycle management
    - Integration with connectivity management
    - Secure credential management
    - Health monitoring and automatic recovery
    - Trading session scheduling
    - VPN coordination
    """
    
    def __init__(self, 
                 credentials: GatewayCredentials,
                 container_config: Optional[ContainerConfig] = None,
                 startup_sequence: Optional[StartupSequence] = None,
                 connectivity_manager: Optional[IntegratedConnectivityManager] = None):
        """
        Initialize Gateway Startup Automation.
        
        Args:
            credentials: Gateway login credentials
            container_config: Docker container configuration
            startup_sequence: Startup sequence settings
            connectivity_manager: Connectivity management integration
        """
        # Setup logging and error handling
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        # Configuration
        self.credentials = credentials
        self.container_config = container_config or ContainerConfig(trading_mode=credentials.trading_mode)
        self.startup_sequence = startup_sequence or StartupSequence()
        self.connectivity_manager = connectivity_manager
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.logger.info("✅ Docker client initialized")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Docker client: {e}")
            self.docker_client = None
            
        # State management
        self.status = GatewayStatus()
        self.container = None
        
        # Threading and monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        self.scheduler_thread = None
        self.shutdown_event = threading.Event()
        
        # Callbacks
        self.status_change_callbacks = []
        self.health_check_callbacks = []
        
        # Trading calendar
        try:
            self.trading_calendar = TradingCalendar() if TradingCalendar else None
        except:
            self.trading_calendar = None
            
        # Security
        self.encryption_key = self._get_or_create_encryption_key()
        
        self.logger.info(f"🚀 Gateway Startup Automation initialized - Mode: {credentials.trading_mode.value}")
    
    # ==========================================================================
    # PUBLIC INTERFACE - CONTAINER LIFECYCLE
    # ==========================================================================
    
    def start_gateway(self, wait_for_ready: bool = True, timeout: int = CONTAINER_STARTUP_TIMEOUT) -> bool:
        """
        Start the IB Gateway container with full automation.
        
        Args:
            wait_for_ready: Wait for gateway to be ready for connections
            timeout: Maximum time to wait for startup
            
        Returns:
            bool: True if startup successful
        """
        try:
            if self.status.state in [GatewayState.RUNNING, GatewayState.STARTING]:
                self.logger.warning("Gateway is already running or starting")
                return True
                
            self.logger.info("🚀 Starting IB Gateway container...")
            self._update_status(GatewayState.STARTING)
            
            # Step 1: Check connectivity if enabled
            if self.startup_sequence.wait_for_connectivity and self.connectivity_manager:
                if not self._wait_for_optimal_connectivity():
                    self.logger.warning("⚠️ Starting without optimal connectivity")
            
            # Step 2: Ensure container is stopped/removed
            self._cleanup_existing_container()
            
            # Step 3: Pull latest image if needed
            self._ensure_image_available()
            
            # Step 4: Create and start container
            if not self._create_container():
                self._update_status(GatewayState.ERROR)
                return False
                
            if not self._start_container():
                self._update_status(GatewayState.ERROR)
                return False
            
            # Step 5: Wait for gateway to be ready
            if wait_for_ready:
                if not self._wait_for_gateway_ready(timeout):
                    self.logger.error("❌ Gateway startup timeout")
                    self._update_status(GatewayState.ERROR)
                    return False
            
            # Step 6: Start monitoring
            self.start_monitoring()
            
            # Step 7: Update status
            self._update_status(GatewayState.RUNNING)
            self.status.start_time = datetime.now()
            
            self.logger.info("✅ IB Gateway container started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start gateway: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "GatewayStartupAutomation", symbol="SPY")
            self._update_status(GatewayState.ERROR)
            return False
    
    def stop_gateway(self, graceful: bool = True, timeout: int = 30) -> bool:
        """
        Stop the IB Gateway container.
        
        Args:
            graceful: Attempt graceful shutdown first
            timeout: Maximum time to wait for shutdown
            
        Returns:
            bool: True if stopped successfully
        """
        try:
            if self.status.state == GatewayState.STOPPED:
                self.logger.info("Gateway is already stopped")
                return True
                
            self.logger.info("🛑 Stopping IB Gateway container...")
            self._update_status(GatewayState.STOPPING)
            
            # Stop monitoring first
            self.stop_monitoring()
            
            # Stop container
            if self.container:
                try:
                    if graceful:
                        self.logger.info("Attempting graceful shutdown...")
                        self.container.stop(timeout=timeout)
                    else:
                        self.logger.info("Forcing container shutdown...")
                        self.container.kill()
                        
                    # Wait for container to stop
                    self.container.wait(timeout=timeout)
                    self.logger.info("✅ Container stopped successfully")
                    
                except Exception as e:
                    self.logger.warning(f"Container stop error (may be normal): {e}")
            
            # Update status
            self._update_status(GatewayState.STOPPED)
            self.container = None
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping gateway: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "GatewayStartupAutomation")
            return False
    
    def restart_gateway(self, reason: RestartReason = RestartReason.USER_REQUEST) -> bool:
        """
        Restart the IB Gateway container.
        
        Args:
            reason: Reason for restart
            
        Returns:
            bool: True if restarted successfully
        """
        self.logger.info(f"🔄 Restarting gateway - Reason: {reason.value}")
        self._update_status(GatewayState.RESTARTING)
        
        # Update restart tracking
        self.status.restart_count += 1
        self.status.last_restart_reason = reason
        
        # Stop and start
        if self.stop_gateway():
            time.sleep(5)  # Brief pause
            return self.start_gateway()
        
        return False
    
    def get_gateway_status(self) -> GatewayStatus:
        """Get current gateway status with latest information"""
        self._update_container_stats()
        return self.status
    
    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    
    def start_monitoring(self) -> bool:
        """Start gateway monitoring"""
        try:
            if self.monitoring_active:
                self.logger.warning("Monitoring already active")
                return True
                
            self.logger.info("📊 Starting gateway monitoring...")
            
            self.monitoring_active = True
            self.shutdown_event.clear()
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            # Start scheduler if configured
            if self.startup_sequence.mode == StartupMode.SCHEDULED:
                self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
                self.scheduler_thread.start()
            
            self.logger.info("✅ Gateway monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop gateway monitoring"""
        self.monitoring_active = False
        self.shutdown_event.set()
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
            
        self.logger.info("🛑 Gateway monitoring stopped")
    
    def perform_health_check(self) -> Tuple[bool, str]:
        """
        Perform comprehensive health check.
        
        Returns:
            Tuple of (healthy, status_message)
        """
        try:
            if not self.container:
                return False, "Container not found"
                
            # Refresh container info
            self.container.reload()
            
            # Check container status
            if self.container.status != 'running':
                return False, f"Container not running: {self.container.status}"
            
            # Check resource usage
            stats = self.container.stats(stream=False)
            
            # Calculate CPU usage
            cpu_usage = self._calculate_cpu_usage(stats)
            if cpu_usage > 95:
                return False, f"High CPU usage: {cpu_usage:.1f}%"
            
            # Calculate memory usage
            memory_stats = stats['memory_stats']
            if 'usage' in memory_stats and 'limit' in memory_stats:
                memory_usage = (memory_stats['usage'] / memory_stats['limit']) * 100
                if memory_usage > 90:
                    return False, f"High memory usage: {memory_usage:.1f}%"
            
            # Check API port connectivity
            if not self._check_api_connectivity():
                return False, "API port not responding"
            
            # Check if connectivity integration is healthy
            if self.connectivity_manager:
                report = self.connectivity_manager.get_connectivity_report()
                if report.overall_state == ConnectivityState.FAILED:
                    return False, "Connectivity management reports failure"
            
            return True, "All checks passed"
            
        except Exception as e:
            return False, f"Health check error: {str(e)}"
    
    # ==========================================================================
    # SCHEDULING AND AUTOMATION
    # ==========================================================================
    
    def enable_scheduled_operation(self, 
                                   start_time: Optional[dt_time] = None,
                                   stop_time: Optional[dt_time] = None):
        """
        Enable scheduled gateway operation based on market hours.
        
        Args:
            start_time: Custom start time (default: market open - buffer)
            stop_time: Custom stop time (default: market close + buffer)  
        """
        self.startup_sequence.mode = StartupMode.SCHEDULED
        
        if start_time:
            self.startup_sequence.scheduled_start_time = start_time
        else:
            # Default to market open minus buffer
            market_open = datetime.combine(datetime.today(), MARKET_OPEN_TIME)
            start_with_buffer = market_open - PRE_MARKET_BUFFER
            self.startup_sequence.scheduled_start_time = start_with_buffer.time()
        
        if stop_time:
            self.startup_sequence.scheduled_stop_time = stop_time
        else:
            # Default to market close plus buffer
            market_close = datetime.combine(datetime.today(), MARKET_CLOSE_TIME)
            stop_with_buffer = market_close + POST_MARKET_BUFFER
            self.startup_sequence.scheduled_stop_time = stop_with_buffer.time()
        
        self.logger.info(f"📅 Scheduled operation enabled: "
                        f"{self.startup_sequence.scheduled_start_time} - "
                        f"{self.startup_sequence.scheduled_stop_time}")
    
    def is_market_hours(self) -> bool:
        """Check if we're within market hours (including buffers)"""
        if not self.trading_calendar:
            # Fallback to simple time check
            now = datetime.now().time()
            return MARKET_OPEN_TIME <= now <= MARKET_CLOSE_TIME
        
        try:
            return self.trading_calendar.is_market_open()
        except:
            # Fallback
            now = datetime.now().time()
            return MARKET_OPEN_TIME <= now <= MARKET_CLOSE_TIME
    
    # ==========================================================================
    # CONNECTIVITY INTEGRATION
    # ==========================================================================
    
    def set_connectivity_manager(self, connectivity_manager: IntegratedConnectivityManager):
        """Set the connectivity manager for integration"""
        self.connectivity_manager = connectivity_manager
        
        # Add callback for connectivity state changes
        connectivity_manager.add_state_change_callback(self._on_connectivity_state_change)
        
        self.logger.info("🔗 Connectivity manager integration enabled")
    
    def optimize_for_connectivity(self) -> bool:
        """
        Optimize gateway startup based on current connectivity.
        
        Returns:
            bool: True if optimization successful
        """
        if not self.connectivity_manager:
            self.logger.warning("No connectivity manager available for optimization")
            return False
            
        try:
            self.logger.info("🎯 Optimizing gateway for connectivity...")
            
            # Get connectivity report
            report = self.connectivity_manager.get_connectivity_report()
            
            # If connectivity is poor, attempt improvements
            if report.overall_state in [ConnectivityState.DEGRADED, ConnectivityState.FAILED]:
                self.logger.info("Poor connectivity detected, attempting improvements...")
                
                # Trigger connectivity repair
                success, message = self.connectivity_manager.execute_automated_repair()
                if success:
                    self.logger.info(f"✅ Connectivity improved: {message}")
                    # Wait a bit for connectivity to stabilize
                    time.sleep(10)
                else:
                    self.logger.warning(f"⚠️ Connectivity repair failed: {message}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connectivity optimization failed: {e}")
            return False
    
    # ==========================================================================
    # PRIVATE METHODS - CONTAINER MANAGEMENT
    # ==========================================================================
    
    def _create_container(self) -> bool:
        """Create the IB Gateway container"""
        try:
            # Prepare environment variables
            env_vars = {
                'TWS_USERID': self.credentials.username,
                'TWS_PASSWORD': self.credentials.password,
                'TWS_MAJOR_VRSN': TWS_MAJOR_VERSION,
                'TRADING_MODE': self.credentials.trading_mode.value.upper(),
                'JTS_LOG_LEVEL': self.container_config.jts_log_level,
                'TZ': self.container_config.timezone
            }
            
            # Add VNC configuration if enabled
            if self.container_config.enable_vnc:
                env_vars['VNC_PASSWORD'] = 'spyder123'  # Should be configurable
            
            # Prepare port mappings
            ports = {
                f'{self.container_config.api_port}/tcp': self.container_config.api_port
            }
            
            if self.container_config.enable_vnc:
                ports[f'{self.container_config.vnc_port}/tcp'] = self.container_config.vnc_port
            
            # Create container
            self.container = self.docker_client.containers.create(
                image=self.container_config.image,
                name=self.container_config.container_name,
                environment=env_vars,
                ports=ports,
                mem_limit=self.container_config.memory_limit,
                cpu_quota=int(float(self.container_config.cpu_limit) * 100000),
                cpu_period=100000,
                auto_remove=self.container_config.auto_remove,
                restart_policy={"Name": self.container_config.restart_policy},
                detach=True
            )
            
            self.status.container_id = self.container.id
            self.logger.info(f"✅ Container created: {self.container.short_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create container: {e}")
            return False
    
    def _start_container(self) -> bool:
        """Start the container"""
        try:
            if not self.container:
                return False
                
            self.container.start()
            self.logger.info(f"✅ Container started: {self.container.short_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start container: {e}")
            return False
    
    def _cleanup_existing_container(self):
        """Clean up any existing container with the same name"""
        try:
            existing = self.docker_client.containers.get(self.container_config.container_name)
            
            if existing.status == 'running':
                self.logger.info("Stopping existing container...")
                existing.stop(timeout=30)
                
            self.logger.info("Removing existing container...")
            existing.remove()
            
        except docker.errors.NotFound:
            # No existing container, which is fine
            pass
        except Exception as e:
            self.logger.warning(f"Error cleaning up existing container: {e}")
    
    def _ensure_image_available(self) -> bool:
        """Ensure the Docker image is available"""
        try:
            # Try to get the image
            self.docker_client.images.get(self.container_config.image)
            self.logger.info(f"✅ Docker image available: {self.container_config.image}")
            return True
            
        except docker.errors.ImageNotFound:
            self.logger.info(f"📥 Pulling Docker image: {self.container_config.image}")
            try:
                self.docker_client.images.pull(self.container_config.image)
                self.logger.info("✅ Docker image pulled successfully")
                return True
            except Exception as e:
                self.logger.error(f"Failed to pull Docker image: {e}")
                return False
        except Exception as e:
            self.logger.error(f"Error checking Docker image: {e}")
            return False
    
    def _wait_for_gateway_ready(self, timeout: int) -> bool:
        """Wait for gateway to be ready for API connections"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._check_api_connectivity():
                self.logger.info("✅ Gateway API is ready")
                return True
                
            # Check if container is still running
            if self.container:
                self.container.reload()
                if self.container.status != 'running':
                    self.logger.error(f"Container stopped unexpectedly: {self.container.status}")
                    return False
            
            time.sleep(5)
        
        self.logger.error("⏱️ Timeout waiting for gateway to be ready")
        return False
    
    def _check_api_connectivity(self) -> bool:
        """Check if the gateway API is responding"""
        try:
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', self.container_config.api_port))
            sock.close()
            
            return result == 0
            
        except Exception as e:
            self.logger.debug(f"API connectivity check failed: {e}")
            return False
    
    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active and not self.shutdown_event.is_set():
            try:
                # Update container stats
                self._update_container_stats()
                
                # Perform health check
                healthy, health_message = self.perform_health_check()
                self.status.health_status = health_message
                self.status.last_health_check = datetime.now()
                
                # Handle unhealthy state
                if not healthy and self.status.state == GatewayState.RUNNING:
                    self.logger.warning(f"⚠️ Gateway unhealthy: {health_message}")
                    self._update_status(GatewayState.UNHEALTHY)
                    
                    # Attempt automatic recovery
                    self._attempt_recovery(health_message)
                
                # Update connectivity status
                if self.connectivity_manager:
                    report = self.connectivity_manager.get_connectivity_report()
                    self.status.connectivity_state = report.overall_state
                
                # Notify callbacks
                for callback in self.health_check_callbacks:
                    try:
                        callback(healthy, health_message)
                    except Exception as e:
                        self.logger.error(f"Health check callback error: {e}")
                
                # Sleep until next check
                self.shutdown_event.wait(CONTAINER_HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                self.shutdown_event.wait(10)  # Short sleep on error
    
    def _scheduler_loop(self):
        """Scheduling loop for automatic start/stop"""
        while self.monitoring_active and not self.shutdown_event.is_set():
            try:
                current_time = datetime.now().time()
                
                # Check if we should start
                if (self.startup_sequence.scheduled_start_time and 
                    current_time >= self.startup_sequence.scheduled_start_time and
                    self.status.state == GatewayState.STOPPED):
                    
                    if not self.trading_calendar or self.trading_calendar.is_trading_day():
                        self.logger.info("📅 Scheduled start time reached")
                        self.start_gateway()
                
                # Check if we should stop
                if (self.startup_sequence.scheduled_stop_time and 
                    current_time >= self.startup_sequence.scheduled_stop_time and
                    self.status.state == GatewayState.RUNNING):
                    
                    self.logger.info("📅 Scheduled stop time reached")
                    self.stop_gateway()
                
                # Sleep for 1 minute
                self.shutdown_event.wait(60)
                
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                self.shutdown_event.wait(60)
    
    def _update_container_stats(self):
        """Update container statistics"""
        try:
            if not self.container:
                return
                
            self.container.reload()
            
            # Update basic status
            if self.container.status == 'running' and self.status.state not in [GatewayState.UNHEALTHY]:
                if self.status.state != GatewayState.RUNNING:
                    self._update_status(GatewayState.RUNNING)
            elif self.container.status in ['exited', 'dead']:
                self._update_status(GatewayState.STOPPED)
            
            # Update uptime
            if self.status.start_time:
                self.status.uptime_seconds = (datetime.now() - self.status.start_time).total_seconds()
            
            # Get resource stats
            try:
                stats = self.container.stats(stream=False)
                
                # CPU usage
                self.status.cpu_usage = self._calculate_cpu_usage(stats)
                
                # Memory usage
                memory_stats = stats.get('memory_stats', {})
                if 'usage' in memory_stats:
                    self.status.memory_usage_mb = memory_stats['usage'] / (1024 * 1024)
                if 'limit' in memory_stats:
                    self.status.memory_limit_mb = memory_stats['limit'] / (1024 * 1024)
                    
            except Exception as e:
                self.logger.debug(f"Error getting container stats: {e}")
                
        except Exception as e:
            self.logger.debug(f"Error updating container stats: {e}")
    
    def _calculate_cpu_usage(self, stats: Dict) -> float:
        """Calculate CPU usage percentage from container stats"""
        try:
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_usage = cpu_stats.get('cpu_usage', {})
            precpu_usage = precpu_stats.get('cpu_usage', {})
            
            total_usage = cpu_usage.get('total_usage', 0)
            pre_total_usage = precpu_usage.get('total_usage', 0)
            
            system_usage = cpu_stats.get('system_cpu_usage', 0)
            pre_system_usage = precpu_stats.get('system_cpu_usage', 0)
            
            if (system_usage > pre_system_usage and 
                total_usage > pre_total_usage):
                
                cpu_delta = total_usage - pre_total_usage
                system_delta = system_usage - pre_system_usage
                
                num_cpus = len(cpu_usage.get('percpu_usage', [1]))
                
                return (cpu_delta / system_delta) * num_cpus * 100.0
            
            return 0.0
            
        except Exception:
            return 0.0
    
    def _attempt_recovery(self, health_issue: str):
        """Attempt automatic recovery from health issues"""
        try:
            self.logger.info(f"🔧 Attempting recovery for: {health_issue}")
            
            # Different recovery strategies based on issue type
            if "high cpu" in health_issue.lower():
                # High CPU - restart container
                self.restart_gateway(RestartReason.RESOURCE_LIMIT)
                
            elif "high memory" in health_issue.lower():
                # High memory - restart container
                self.restart_gateway(RestartReason.RESOURCE_LIMIT)
                
            elif "api port" in health_issue.lower():
                # API connectivity issues - check and restart
                self.restart_gateway(RestartReason.CONNECTION_LOST)
                
            elif "connectivity" in health_issue.lower():
                # Connectivity issues - coordinate with connectivity manager
                if self.connectivity_manager:
                    self.connectivity_manager.execute_automated_repair()
                self.restart_gateway(RestartReason.CONNECTIVITY_OPTIMIZATION)
                
            else:
                # Generic recovery - restart
                self.restart_gateway(RestartReason.UNHEALTHY)
                
        except Exception as e:
            self.logger.error(f"Recovery attempt failed: {e}")
    
    # ==========================================================================
    # PRIVATE METHODS - CONNECTIVITY INTEGRATION
    # ==========================================================================
    
    def _wait_for_optimal_connectivity(self) -> bool:
        """Wait for optimal connectivity before starting gateway"""
        if not self.connectivity_manager:
            return True  # No connectivity manager, proceed
            
        max_wait = self.startup_sequence.max_connectivity_wait
        start_time = time.time()
        
        self.logger.info(f"⏳ Waiting for optimal connectivity (max {max_wait}s)...")
        
        while time.time() - start_time < max_wait:
            report = self.connectivity_manager.get_connectivity_report()
            
            if report.overall_state in [ConnectivityState.OPTIMAL, ConnectivityState.GOOD]:
                self.logger.info("✅ Optimal connectivity achieved")
                return True
            
            time.sleep(10)
        
        self.logger.warning("⏱️ Connectivity wait timeout")
        return False
    
    def _on_connectivity_state_change(self, old_state: ConnectivityState, new_state: ConnectivityState):
        """Handle connectivity state changes"""
        self.logger.info(f"🔄 Connectivity state changed: {old_state.value} → {new_state.value}")
        
        # Update our status
        self.status.connectivity_state = new_state
        
        # React to connectivity changes if gateway is running
        if self.status.state == GatewayState.RUNNING:
            
            # If connectivity degraded significantly, consider restart
            if (old_state in [ConnectivityState.OPTIMAL, ConnectivityState.GOOD] and
                new_state == ConnectivityState.FAILED):
                
                self.logger.warning("Connectivity failed - considering gateway restart for optimization")
                # Could trigger restart here if configured
    
    # ==========================================================================
    # PRIVATE METHODS - SECURITY AND UTILITIES
    # ==========================================================================
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for credentials"""
        key_env = os.getenv(CREDENTIAL_ENCRYPTION_KEY)
        
        if key_env:
            return base64.b64decode(key_env.encode())
        
        # Generate new key
        key = Fernet.generate_key()
        
        # Save to environment (in production, use secure key management)
        encoded_key = base64.b64encode(key).decode()
        os.environ[CREDENTIAL_ENCRYPTION_KEY] = encoded_key
        
        self.logger.warning("Generated new encryption key - ensure this is saved securely")
        return key
    
    def _update_status(self, new_state: GatewayState):
        """Update gateway status and notify callbacks"""
        if new_state != self.status.state:
            old_state = self.status.state
            self.status.state = new_state
            
            self.logger.info(f"🔄 Gateway state: {old_state.value} → {new_state.value}")
            
            # Notify callbacks
            for callback in self.status_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"Status change callback error: {e}")
    
    def add_status_change_callback(self, callback: Callable):
        """Add callback for status changes"""
        self.status_change_callbacks.append(callback)
    
    def add_health_check_callback(self, callback: Callable):
        """Add callback for health checks"""
        self.health_check_callbacks.append(callback)

# ==============================================================================
# PYQT6 DASHBOARD WIDGET
# ==============================================================================

class GatewayAutomationDashboard(QWidget):
    """
    PyQt6 dashboard widget for gateway startup automation.
    
    Provides real-time monitoring, control, and configuration of the
    IB Gateway container with integrated connectivity management.
    """
    
    # Qt signals
    gatewayStateChanged = pyqtSignal(str)  # GatewayState
    healthStatusChanged = pyqtSignal(bool, str)  # healthy, message
    
    def __init__(self, 
                 gateway_automation: Optional[GatewayStartupAutomation] = None,
                 config: Optional[GatewayConfig] = None):
        super().__init__()
        
        self.gateway_automation = gateway_automation
        self.config = config or GatewayConfig()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
        
        # Setup UI
        self.setup_ui()
        self.setup_monitoring()
        
        # Connect callbacks if gateway automation is available
        if self.gateway_automation:
            self.setup_callbacks()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()
        
        # Header
        self.create_header_section(main_layout)
        
        # Main content with tabs
        self.create_main_content(main_layout)
        
        # Control buttons
        self.create_control_section(main_layout)
        
        # Status bar
        self.create_status_bar(main_layout)
        
        self.setLayout(main_layout)
        self.setMinimumSize(900, 700)
        self.setWindowTitle("SPYDER - Gateway Startup Automation")
    
    def create_header_section(self, layout):
        """Create header with title and main status"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel("🚀 SPYDER Gateway Startup Automation")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        
        # Main status
        self.main_status_label = QLabel("🔄 Initializing...")
        status_font = QFont()
        status_font.setPointSize(14)
        self.main_status_label.setFont(status_font)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.main_status_label)
        
        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)
    
    def create_main_content(self, layout):
        """Create main content with tabs"""
        self.tab_widget = QTabWidget()
        
        # Status tab
        self.create_status_tab()
        
        # Configuration tab
        self.create_configuration_tab()
        
        # Logs tab
        self.create_logs_tab()
        
        # Advanced tab
        self.create_advanced_tab()
        
        layout.addWidget(self.tab_widget)
    
    def create_status_tab(self):
        """Create gateway status tab"""
        status_widget = QWidget()
        layout = QVBoxLayout()
        
        # Container status
        container_group = QGroupBox("🐳 Container Status")
        container_layout = QVBoxLayout()
        
        self.container_id_label = QLabel("Container ID: Unknown")
        self.container_status_label = QLabel("Status: Unknown")
        self.uptime_label = QLabel("Uptime: Unknown")
        self.restart_count_label = QLabel("Restarts: 0")
        
        container_layout.addWidget(self.container_id_label)
        container_layout.addWidget(self.container_status_label)
        container_layout.addWidget(self.uptime_label)
        container_layout.addWidget(self.restart_count_label)
        
        container_group.setLayout(container_layout)
        layout.addWidget(container_group)
        
        # Resource usage
        resources_group = QGroupBox("📊 Resource Usage")
        resources_layout = QVBoxLayout()
        
        self.cpu_usage_label = QLabel("CPU: Unknown")
        self.memory_usage_label = QLabel("Memory: Unknown")
        self.api_port_label = QLabel("API Port: Unknown")
        
        resources_layout.addWidget(self.cpu_usage_label)
        resources_layout.addWidget(self.memory_usage_label)
        resources_layout.addWidget(self.api_port_label)
        
        resources_group.setLayout(resources_layout)
        layout.addWidget(resources_group)
        
        # Health status
        health_group = QGroupBox("🏥 Health Status")
        health_layout = QVBoxLayout()
        
        self.health_status_label = QLabel("Health: Unknown")
        self.last_health_check_label = QLabel("Last Check: Unknown")
        self.connectivity_status_label = QLabel("Connectivity: Unknown")
        
        health_layout.addWidget(self.health_status_label)
        health_layout.addWidget(self.last_health_check_label)
        health_layout.addWidget(self.connectivity_status_label)
        
        health_group.setLayout(health_layout)
        layout.addWidget(health_group)
        
        status_widget.setLayout(layout)
        self.tab_widget.addTab(status_widget, "Status")
    
    def create_configuration_tab(self):
        """Create configuration tab"""
        config_widget = QWidget()
        layout = QVBoxLayout()
        
        # Trading mode
        trading_group = QGroupBox("📈 Trading Configuration")
        trading_layout = QVBoxLayout()
        
        self.trading_mode_combo = QComboBox()
        self.trading_mode_combo.addItems(["paper", "live"])
        trading_layout.addWidget(QLabel("Trading Mode:"))
        trading_layout.addWidget(self.trading_mode_combo)
        
        trading_group.setLayout(trading_layout)
        layout.addWidget(trading_group)
        
        # Scheduling
        schedule_group = QGroupBox("📅 Scheduling")
        schedule_layout = QVBoxLayout()
        
        self.enable_scheduling_cb = QCheckBox("Enable scheduled operation")
        self.start_time_edit = QTimeEdit()
        self.stop_time_edit = QTimeEdit()
        
        schedule_layout.addWidget(self.enable_scheduling_cb)
        schedule_layout.addWidget(QLabel("Start Time:"))
        schedule_layout.addWidget(self.start_time_edit)
        schedule_layout.addWidget(QLabel("Stop Time:"))
        schedule_layout.addWidget(self.stop_time_edit)
        
        schedule_group.setLayout(schedule_layout)
        layout.addWidget(schedule_group)
        
        # Connectivity integration
        connectivity_group = QGroupBox("🌐 Connectivity Integration")
        connectivity_layout = QVBoxLayout()
        
        self.wait_connectivity_cb = QCheckBox("Wait for optimal connectivity")
        self.enable_vpn_cb = QCheckBox("Enable VPN coordination")
        self.max_wait_spin = QSpinBox()
        self.max_wait_spin.setRange(30, 600)
        self.max_wait_spin.setValue(300)
        self.max_wait_spin.setSuffix(" seconds")
        
        connectivity_layout.addWidget(self.wait_connectivity_cb)
        connectivity_layout.addWidget(self.enable_vpn_cb)
        connectivity_layout.addWidget(QLabel("Max connectivity wait:"))
        connectivity_layout.addWidget(self.max_wait_spin)
        
        connectivity_group.setLayout(connectivity_layout)
        layout.addWidget(connectivity_group)
        
        config_widget.setLayout(layout)
        self.tab_widget.addTab(config_widget, "Configuration")
    
    def create_logs_tab(self):
        """Create logs tab"""
        logs_widget = QWidget()
        layout = QVBoxLayout()
        
        # Log display
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Courier", 9))
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Log controls
        log_controls = QHBoxLayout()
        
        self.clear_logs_btn = QPushButton("Clear Logs")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        log_controls.addWidget(self.clear_logs_btn)
        
        self.export_logs_btn = QPushButton("Export Logs")
        self.export_logs_btn.clicked.connect(self.export_logs)
        log_controls.addWidget(self.export_logs_btn)
        
        log_controls.addStretch()
        
        layout.addLayout(log_controls)
        logs_widget.setLayout(layout)
        self.tab_widget.addTab(logs_widget, "Logs")
    
    def create_advanced_tab(self):
        """Create advanced settings tab"""
        advanced_widget = QWidget()
        layout = QVBoxLayout()
        
        # Container settings
        container_group = QGroupBox("🐳 Container Settings")
        container_layout = QVBoxLayout()
        
        self.memory_limit_edit = QLineEdit("2g")
        self.cpu_limit_edit = QLineEdit("1.0")
        self.vnc_enable_cb = QCheckBox("Enable VNC (port 5900)")
        
        container_layout.addWidget(QLabel("Memory Limit:"))
        container_layout.addWidget(self.memory_limit_edit)
        container_layout.addWidget(QLabel("CPU Limit:"))
        container_layout.addWidget(self.cpu_limit_edit)
        container_layout.addWidget(self.vnc_enable_cb)
        
        container_group.setLayout(container_layout)
        layout.addWidget(container_group)
        
        # Monitoring settings
        monitoring_group = QGroupBox("📊 Monitoring")
        monitoring_layout = QVBoxLayout()
        
        self.auto_restart_cb = QCheckBox("Enable automatic restart on failure")
        self.health_check_interval_spin = QSpinBox()
        self.health_check_interval_spin.setRange(10, 300)
        self.health_check_interval_spin.setValue(30)
        self.health_check_interval_spin.setSuffix(" seconds")
        
        monitoring_layout.addWidget(self.auto_restart_cb)
        monitoring_layout.addWidget(QLabel("Health check interval:"))
        monitoring_layout.addWidget(self.health_check_interval_spin)
        
        monitoring_group.setLayout(monitoring_layout)
        layout.addWidget(monitoring_group)
        
        advanced_widget.setLayout(layout)
        self.tab_widget.addTab(advanced_widget, "Advanced")
    
    def create_control_section(self, layout):
        """Create control buttons section"""
        controls_frame = QFrame()
        controls_layout = QHBoxLayout()
        
        # Main control buttons
        self.start_btn = QPushButton("🚀 Start Gateway")
        self.start_btn.clicked.connect(self.start_gateway)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        controls_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("🛑 Stop Gateway")
        self.stop_btn.clicked.connect(self.stop_gateway)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        controls_layout.addWidget(self.stop_btn)
        
        self.restart_btn = QPushButton("🔄 Restart Gateway")
        self.restart_btn.clicked.connect(self.restart_gateway)
        controls_layout.addWidget(self.restart_btn)
        
        # Utility buttons
        controls_layout.addWidget(QFrame())  # Separator
        
        self.health_check_btn = QPushButton("🏥 Health Check")
        self.health_check_btn.clicked.connect(self.perform_health_check)
        controls_layout.addWidget(self.health_check_btn)
        
        self.optimize_btn = QPushButton("🎯 Optimize")
        self.optimize_btn.clicked.connect(self.optimize_connectivity)
        controls_layout.addWidget(self.optimize_btn)
        
        controls_frame.setLayout(controls_layout)
        layout.addWidget(controls_frame)
    
    def create_status_bar(self, layout):
        """Create status bar"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout()
        
        self.status_bar_label = QLabel("Ready")
        self.last_update_label = QLabel("")
        
        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_bar_label)
        status_layout.addStretch()
        status_layout.addWidget(self.last_update_label)
        
        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)
    
    def setup_monitoring(self):
        """Setup monitoring timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        # Initial update
        self.update_display()
    
    def setup_callbacks(self):
        """Setup callbacks with gateway automation"""
        if self.gateway_automation:
            self.gateway_automation.add_status_change_callback(self.on_status_change)
            self.gateway_automation.add_health_check_callback(self.on_health_check)
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def update_display(self):
        """Update all display elements"""
        try:
            if not self.gateway_automation:
                return
                
            status = self.gateway_automation.get_gateway_status()
            
            # Update main status
            state_colors = {
                GatewayState.RUNNING: "#4CAF50",
                GatewayState.STARTING: "#2196F3",
                GatewayState.STOPPING: "#FF9800",
                GatewayState.STOPPED: "#757575",
                GatewayState.ERROR: "#F44336",
                GatewayState.UNHEALTHY: "#FF5722"
            }
            
            color = state_colors.get(status.state, "#666666")
            self.main_status_label.setText(f"Status: {status.state.value.title()}")
            self.main_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
            # Update status tab
            self.update_status_tab(status)
            
            # Update status bar
            self.status_bar_label.setText(status.state.value.title())
            self.last_update_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")
    
    def update_status_tab(self, status: GatewayStatus):
        """Update status tab with current information"""
        try:
            # Container info
            self.container_id_label.setText(f"Container ID: {status.container_id or 'None'}")
            self.container_status_label.setText(f"Status: {status.state.value}")
            
            if status.uptime_seconds > 0:
                hours = int(status.uptime_seconds // 3600)
                minutes = int((status.uptime_seconds % 3600) // 60)
                self.uptime_label.setText(f"Uptime: {hours:02d}:{minutes:02d}")
            else:
                self.uptime_label.setText("Uptime: Not running")
            
            self.restart_count_label.setText(f"Restarts: {status.restart_count}")
            
            # Resource usage
            self.cpu_usage_label.setText(f"CPU: {status.cpu_usage:.1f}%")
            
            if status.memory_usage_mb > 0:
                memory_text = f"Memory: {status.memory_usage_mb:.1f} MB"
                if status.memory_limit_mb > 0:
                    memory_pct = (status.memory_usage_mb / status.memory_limit_mb) * 100
                    memory_text += f" ({memory_pct:.1f}%)"
                self.memory_usage_label.setText(memory_text)
            else:
                self.memory_usage_label.setText("Memory: Unknown")
            
            self.api_port_label.setText(f"API Port: {status.api_port or 'Unknown'}")
            
            # Health status
            self.health_status_label.setText(f"Health: {status.health_status}")
            
            if status.last_health_check:
                check_time = status.last_health_check.strftime('%H:%M:%S')
                self.last_health_check_label.setText(f"Last Check: {check_time}")
            
            if status.connectivity_state:
                conn_text = status.connectivity_state.value.title()
                self.connectivity_status_label.setText(f"Connectivity: {conn_text}")
            
        except Exception as e:
            self.logger.error(f"Error updating status tab: {e}")
    
    def on_status_change(self, old_state: GatewayState, new_state: GatewayState):
        """Handle gateway status changes"""
        self.gatewayStateChanged.emit(new_state.value)
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{timestamp}] Status: {old_state.value} → {new_state.value}")
        self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def on_health_check(self, healthy: bool, message: str):
        """Handle health check results"""
        self.healthStatusChanged.emit(healthy, message)
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_emoji = "✅" if healthy else "❌"
        self.log_text.append(f"[{timestamp}] Health Check: {status_emoji} {message}")
        self.log_text.moveCursor(self.log_text.textCursor().End)
    
    # ==========================================================================
    # BUTTON HANDLERS
    # ==========================================================================
    
    def start_gateway(self):
        """Start gateway"""
        if not self.gateway_automation:
            QMessageBox.warning(self, "Warning", "Gateway automation not available")
            return
            
        self.start_btn.setEnabled(False)
        self.start_btn.setText("🔄 Starting...")
        
        try:
            success = self.gateway_automation.start_gateway()
            if success:
                self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Gateway started successfully")
            else:
                self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Gateway start failed")
            
        finally:
            self.start_btn.setEnabled(True)
            self.start_btn.setText("🚀 Start Gateway")
            self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def stop_gateway(self):
        """Stop gateway"""
        if not self.gateway_automation:
            QMessageBox.warning(self, "Warning", "Gateway automation not available")
            return
            
        reply = QMessageBox.question(self, "Confirm Stop", 
                                   "Are you sure you want to stop the gateway?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.stop_btn.setEnabled(False)
            self.stop_btn.setText("🔄 Stopping...")
            
            try:
                success = self.gateway_automation.stop_gateway()
                if success:
                    self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Gateway stopped successfully")
                else:
                    self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Gateway stop failed")
                
            finally:
                self.stop_btn.setEnabled(True)
                self.stop_btn.setText("🛑 Stop Gateway")
                self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def restart_gateway(self):
        """Restart gateway"""
        if not self.gateway_automation:
            QMessageBox.warning(self, "Warning", "Gateway automation not available")
            return
            
        self.restart_btn.setEnabled(False)
        self.restart_btn.setText("🔄 Restarting...")
        
        try:
            success = self.gateway_automation.restart_gateway()
            if success:
                self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Gateway restarted successfully")
            else:
                self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Gateway restart failed")
            
        finally:
            self.restart_btn.setEnabled(True)
            self.restart_btn.setText("🔄 Restart Gateway")
            self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def perform_health_check(self):
        """Perform manual health check"""
        if not self.gateway_automation:
            QMessageBox.warning(self, "Warning", "Gateway automation not available")
            return
            
        self.health_check_btn.setEnabled(False)
        self.health_check_btn.setText("🔄 Checking...")
        
        try:
            healthy, message = self.gateway_automation.perform_health_check()
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            status_emoji = "✅" if healthy else "❌"
            self.log_text.append(f"[{timestamp}] Manual Health Check: {status_emoji} {message}")
            
            # Show message box with result
            if healthy:
                QMessageBox.information(self, "Health Check", f"✅ {message}")
            else:
                QMessageBox.warning(self, "Health Check", f"❌ {message}")
            
        finally:
            self.health_check_btn.setEnabled(True)
            self.health_check_btn.setText("🏥 Health Check")
            self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def optimize_connectivity(self):
        """Optimize connectivity"""
        if not self.gateway_automation:
            QMessageBox.warning(self, "Warning", "Gateway automation not available")
            return
            
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.setText("🔄 Optimizing...")
        
        try:
            success = self.gateway_automation.optimize_for_connectivity()
            
            timestamp = datetime.now().strftime('%H:%M:%S')
            if success:
                self.log_text.append(f"[{timestamp}] ✅ Connectivity optimization completed")
            else:
                self.log_text.append(f"[{timestamp}] ⚠️ Connectivity optimization had issues")
                
        finally:
            self.optimize_btn.setEnabled(True)
            self.optimize_btn.setText("🎯 Optimize")
            self.log_text.moveCursor(self.log_text.textCursor().End)
    
    def clear_logs(self):
        """Clear the log display"""
        self.log_text.clear()
    
    def export_logs(self):
        """Export logs to file"""
        QMessageBox.information(self, "Export", "Log export functionality not implemented yet")
    
    def closeEvent(self, event):
        """Handle widget close"""
        try:
            # Stop monitoring if we started it
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            event.accept()
        except Exception as e:
            self.logger.error(f"Error during close: {e}")
            event.accept()

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_gateway_automation(credentials: GatewayCredentials,
                             container_config: Optional[ContainerConfig] = None,
                             startup_sequence: Optional[StartupSequence] = None,
                             connectivity_manager: Optional[IntegratedConnectivityManager] = None) -> GatewayStartupAutomation:
    """Factory function to create gateway automation"""
    return GatewayStartupAutomation(credentials, container_config, startup_sequence, connectivity_manager)

def create_gateway_dashboard(gateway_automation: Optional[GatewayStartupAutomation] = None,
                           config: Optional[GatewayConfig] = None) -> GatewayAutomationDashboard:
    """Factory function to create gateway dashboard"""
    return GatewayAutomationDashboard(gateway_automation, config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    print("🚀 SPYDER B21 - Gateway Startup Automation")
    print("=" * 60)
    
    try:
        # Test credentials (use secure storage in production)
        credentials = GatewayCredentials(
            username="demo_user", 
            password="demo_password",
            trading_mode=TradingMode.PAPER
        )
        
        # Test container configuration
        container_config = ContainerConfig(
            trading_mode=TradingMode.PAPER,
            enable_vnc=True
        )
        
        # Test startup automation
        automation = GatewayStartupAutomation(
            credentials=credentials,
            container_config=container_config
        )
        
        print("✅ Gateway Startup Automation initialized")
        print(f"📊 Configuration:")
        print(f"  Trading Mode: {credentials.trading_mode.value}")
        print(f"  Container Name: {container_config.container_name}")
        print(f"  API Port: {container_config.api_port}")
        print(f"  VNC Enabled: {container_config.enable_vnc}")
        
        # Test status check
        status = automation.get_gateway_status()
        print(f"\n🔍 Current Status:")
        print(f"  State: {status.state.value}")
        print(f"  Container ID: {status.container_id or 'None'}")
        print(f"  Health Status: {status.health_status}")
        
        print(f"\n✅ Gateway Startup Automation test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    return True

if __name__ == "__main__":
    main()
