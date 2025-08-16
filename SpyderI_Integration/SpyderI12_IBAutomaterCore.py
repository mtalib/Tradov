#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI12_IBAutomaterCore.py
Group: I (Integration)
Purpose: Core IB Gateway automation bridge integrating with B-series modules
Author: Mohamed Talib
Date Created: 2025-08-16
Last Updated: 2025-08-16 Time: 00:00:00

Description:
    This module serves as the integration bridge between I-series and B-series
    broker modules. It provides a unified interface for IB Gateway automation,
    coordinating with SpyderB12_GatewayAutomation for gateway management and
    SpyderB05_ConnectionManager for connection handling. Essential for seamless
    integration of new features with existing broker infrastructure.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to path for imports
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import existing B-series modules
try:
    from SpyderB_Broker.SpyderB12_GatewayAutomation import (
        GatewayAutomation,
        GatewayConfig,
        GatewayState,
        GatewayStatus,
        TradingMode
    )
    from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager
    B_SERIES_AVAILABLE = True
except ImportError as e:
    B_SERIES_AVAILABLE = False
    print(f"⚠️ B-series modules not available: {e}")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# IB Gateway settings
IB_GATEWAY_VERSION = "10.39.1c"
IB_GATEWAY_PATH = Path.home() / "Jts"
IB_GATEWAY_EXECUTABLE = "ibgateway"

# Process management
MAX_STARTUP_RETRIES = 3
STARTUP_TIMEOUT_SECONDS = 60
HEALTH_CHECK_INTERVAL = 30
PROCESS_CHECK_INTERVAL = 5

# Connection settings
DEFAULT_PAPER_PORT = 4002
DEFAULT_LIVE_PORT = 4001
CLIENT_ID_RANGE = range(1, 10)

# ==============================================================================
# ENUMS
# ==============================================================================
class AutomationMode(Enum):
    """IB Gateway automation modes"""
    MANUAL = "manual"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"
    HEADLESS = "headless"

class IntegrationStatus(Enum):
    """Integration status with B-series modules"""
    NOT_INITIALIZED = auto()
    INITIALIZING = auto()
    CONNECTED = auto()
    DISCONNECTED = auto()
    ERROR = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class IBProcessInfo:
    """Information about IB Gateway process"""
    pid: Optional[int] = None
    name: str = ""
    status: str = "stopped"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    uptime_seconds: int = 0
    port: int = 0
    
    def is_running(self) -> bool:
        """Check if process is running"""
        return self.pid is not None and self.status == "running"

@dataclass
class AutomationConfig:
    """Configuration for IB automation"""
    mode: AutomationMode = AutomationMode.SEMI_AUTO
    gateway_path: Path = field(default_factory=lambda: IB_GATEWAY_PATH)
    trading_mode: str = "paper"
    port: int = DEFAULT_PAPER_PORT
    client_id: int = 1
    username: str = ""
    password: str = ""  # Encrypted in production
    auto_restart: bool = True
    health_check_enabled: bool = True
    max_retries: int = MAX_STARTUP_RETRIES
    startup_timeout: int = STARTUP_TIMEOUT_SECONDS
    timezone: str = "US/Eastern"

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBAutomaterCore:
    """
    Core IB Gateway automation integrator.
    
    This class provides the integration layer between I-series modules and
    existing B-series broker infrastructure. It coordinates gateway automation,
    connection management, and process monitoring while maintaining compatibility
    with the established Spyder architecture.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Automation configuration
        gateway_automation: B-series gateway automation instance
        connection_manager: B-series connection manager instance
        integration_status: Current integration status
        
    Example:
        >>> config = AutomationConfig(mode=AutomationMode.SEMI_AUTO)
        >>> automater = IBAutomaterCore(config)
        >>> automater.initialize()
        >>> automater.start_gateway()
    """
    
    def __init__(self, config: Optional[AutomationConfig] = None):
        """
        Initialize the IB Automater Core
        
        Args:
            config: Automation configuration
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or AutomationConfig()
        
        # Integration with B-series modules
        self.gateway_automation: Optional[GatewayAutomation] = None
        self.connection_manager: Optional[ConnectionManager] = None
        self.integration_status = IntegrationStatus.NOT_INITIALIZED
        
        # Process tracking
        self.process_info = IBProcessInfo()
        self.process_monitor_thread: Optional[threading.Thread] = None
        self._monitoring_active = False
        self._monitor_lock = threading.Lock()
        
        # Health monitoring
        self.health_check_thread: Optional[threading.Thread] = None
        self._health_check_active = False
        self.last_health_check = datetime.now()
        self.health_status: Dict[str, Any] = {}
        
        # Event tracking
        self.events: List[Dict[str, Any]] = []
        self.callbacks: Dict[str, List] = {
            'on_gateway_start': [],
            'on_gateway_stop': [],
            'on_connection_established': [],
            'on_connection_lost': [],
            'on_error': []
        }
        
        self.logger.info(f"IBAutomaterCore initialized with mode: {config.mode.value if config else 'default'}")
    
    # ==========================================================================
    # INITIALIZATION AND SETUP
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize integration with B-series modules
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.integration_status = IntegrationStatus.INITIALIZING
            
            if not B_SERIES_AVAILABLE:
                self.logger.warning("B-series modules not available - running in standalone mode")
                self.integration_status = IntegrationStatus.ERROR
                return False
            
            # Create gateway configuration for B-series
            gateway_config = self._create_gateway_config()
            
            # Initialize connection manager
            self.connection_manager = ConnectionManager()
            
            # Initialize gateway automation
            self.gateway_automation = GatewayAutomation(
                config=gateway_config,
                connection_manager=self.connection_manager,
                event_manager=None  # We'll handle events internally
            )
            
            self.integration_status = IntegrationStatus.CONNECTED
            self.logger.info("Successfully integrated with B-series modules")
            
            # Start monitoring if enabled
            if self.config.health_check_enabled:
                self.start_monitoring()
            
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, "IBAutomaterCore.initialize")
            self.integration_status = IntegrationStatus.ERROR
            return False
    
    def _create_gateway_config(self) -> 'GatewayConfig':
        """
        Create gateway configuration for B-series integration
        
        Returns:
            GatewayConfig: Configuration for gateway automation
        """
        mode = TradingMode.PAPER if self.config.trading_mode == "paper" else TradingMode.LIVE
        
        return GatewayConfig(
            mode=mode,
            gateway_path=str(self.config.gateway_path),
            api_port=self.config.port,
            client_id=self.config.client_id,
            auto_restart=self.config.auto_restart,
            username=self.config.username,
            password=self.config.password,
            timezone=self.config.timezone
        )
    
    # ==========================================================================
    # GATEWAY MANAGEMENT
    # ==========================================================================
    
    def start_gateway(self, wait_for_ready: bool = True) -> bool:
        """
        Start IB Gateway
        
        Args:
            wait_for_ready: Wait for gateway to be ready
            
        Returns:
            bool: True if gateway started successfully
        """
        try:
            if self.integration_status != IntegrationStatus.CONNECTED:
                if not self.initialize():
                    return False
            
            self.logger.info("Starting IB Gateway...")
            self._fire_event('on_gateway_start', {'timestamp': datetime.now()})
            
            # Use B-series gateway automation if available
            if self.gateway_automation:
                success = self.gateway_automation.start_gateway()
                if success:
                    self.process_info = self._get_process_info()
                    if wait_for_ready:
                        success = self.wait_for_ready()
                return success
            else:
                # Fallback to direct process management
                return self._start_gateway_direct()
                
        except Exception as e:
            self.error_handler.handle_error(e, "IBAutomaterCore.start_gateway")
            self._fire_event('on_error', {'error': str(e)})
            return False
    
    def stop_gateway(self) -> bool:
        """
        Stop IB Gateway
        
        Returns:
            bool: True if gateway stopped successfully
        """
        try:
            self.logger.info("Stopping IB Gateway...")
            self._fire_event('on_gateway_stop', {'timestamp': datetime.now()})
            
            if self.gateway_automation:
                return self.gateway_automation.stop_gateway()
            else:
                return self._stop_gateway_direct()
                
        except Exception as e:
            self.error_handler.handle_error(e, "IBAutomaterCore.stop_gateway")
            return False
    
    def restart_gateway(self) -> bool:
        """
        Restart IB Gateway
        
        Returns:
            bool: True if restart successful
        """
        self.logger.info("Restarting IB Gateway...")
        
        if self.stop_gateway():
            time.sleep(5)  # Wait for clean shutdown
            return self.start_gateway()
        return False
    
    # ==========================================================================
    # PROCESS MANAGEMENT
    # ==========================================================================
    
    def _start_gateway_direct(self) -> bool:
        """
        Start gateway directly (fallback method)
        
        Returns:
            bool: True if started successfully
        """
        try:
            # Kill any existing gateway processes
            self._kill_existing_gateways()
            
            # Build command
            cmd = self._build_gateway_command()
            
            # Start process
            env = os.environ.copy()
            env['TWS_PORT'] = str(self.config.port)
            env['IB_USER'] = self.config.username
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.config.gateway_path)
            )
            
            # Wait for startup
            time.sleep(10)
            
            # Check if running
            if process.poll() is None:
                self.process_info.pid = process.pid
                self.process_info.status = "running"
                self.logger.info(f"Gateway started with PID: {process.pid}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to start gateway directly: {e}")
            return False
    
    def _stop_gateway_direct(self) -> bool:
        """
        Stop gateway directly (fallback method)
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            if self.process_info.pid:
                process = psutil.Process(self.process_info.pid)
                process.terminate()
                process.wait(timeout=10)
                self.process_info = IBProcessInfo()
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to stop gateway directly: {e}")
            return False
    
    def _kill_existing_gateways(self):
        """Kill any existing gateway processes"""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if 'ibgateway' in proc.info['name'].lower():
                    self.logger.info(f"Killing existing gateway process: {proc.info['pid']}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    
    def _build_gateway_command(self) -> List[str]:
        """
        Build gateway startup command
        
        Returns:
            List[str]: Command arguments
        """
        gateway_jar = self.config.gateway_path / f"{IB_GATEWAY_VERSION}" / "jars" / "ibgateway.jar"
        
        cmd = [
            "java",
            "-cp", str(gateway_jar),
            "-Xmx1024m",
            f"-Dib.port={self.config.port}",
            f"-Dib.mode={self.config.trading_mode}",
            "ibgateway.GWClient"
        ]
        
        return cmd
    
    # ==========================================================================
    # MONITORING
    # ==========================================================================
    
    def start_monitoring(self):
        """Start process and health monitoring"""
        if not self._monitoring_active:
            self._monitoring_active = True
            
            # Start process monitor
            self.process_monitor_thread = threading.Thread(
                target=self._process_monitor_loop,
                daemon=True
            )
            self.process_monitor_thread.start()
            
            # Start health check
            if self.config.health_check_enabled:
                self._health_check_active = True
                self.health_check_thread = threading.Thread(
                    target=self._health_check_loop,
                    daemon=True
                )
                self.health_check_thread.start()
            
            self.logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop all monitoring threads"""
        self._monitoring_active = False
        self._health_check_active = False
        
        if self.process_monitor_thread:
            self.process_monitor_thread.join(timeout=5)
        
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
        
        self.logger.info("Monitoring stopped")
    
    def _process_monitor_loop(self):
        """Monitor gateway process"""
        while self._monitoring_active:
            try:
                with self._monitor_lock:
                    self.process_info = self._get_process_info()
                    
                    # Check for unexpected termination
                    if not self.process_info.is_running() and self.config.auto_restart:
                        self.logger.warning("Gateway process terminated - attempting restart")
                        self.start_gateway()
                
                time.sleep(PROCESS_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Process monitor error: {e}")
    
    def _health_check_loop(self):
        """Perform periodic health checks"""
        while self._health_check_active:
            try:
                self.perform_health_check()
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
    
    def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check
        
        Returns:
            Dict[str, Any]: Health status information
        """
        health = {
            'timestamp': datetime.now(),
            'process_running': False,
            'connection_active': False,
            'memory_usage_mb': 0,
            'cpu_percent': 0,
            'uptime_seconds': 0,
            'errors': []
        }
        
        try:
            # Check process
            process_info = self._get_process_info()
            health['process_running'] = process_info.is_running()
            health['memory_usage_mb'] = process_info.memory_mb
            health['cpu_percent'] = process_info.cpu_percent
            health['uptime_seconds'] = process_info.uptime_seconds
            
            # Check connection
            if self.connection_manager:
                health['connection_active'] = self.connection_manager.is_connected()
            
            self.health_status = health
            self.last_health_check = datetime.now()
            
        except Exception as e:
            health['errors'].append(str(e))
        
        return health
    
    def _get_process_info(self) -> IBProcessInfo:
        """
        Get current process information
        
        Returns:
            IBProcessInfo: Process information
        """
        info = IBProcessInfo()
        
        try:
            # Find IB Gateway process
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                if 'ibgateway' in proc.info['name'].lower():
                    info.pid = proc.info['pid']
                    info.name = proc.info['name']
                    info.status = "running"
                    
                    process = psutil.Process(info.pid)
                    info.cpu_percent = process.cpu_percent()
                    info.memory_mb = process.memory_info().rss / 1024 / 1024
                    info.uptime_seconds = int(time.time() - proc.info['create_time'])
                    info.port = self.config.port
                    
                    break
                    
        except Exception as e:
            self.logger.error(f"Error getting process info: {e}")
        
        return info
    
    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    
    def wait_for_ready(self, timeout: Optional[int] = None) -> bool:
        """
        Wait for gateway to be ready for connections
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            bool: True if ready
        """
        timeout = timeout or self.config.startup_timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_ready():
                self._fire_event('on_connection_established', {'timestamp': datetime.now()})
                return True
            time.sleep(2)
        
        return False
    
    def is_ready(self) -> bool:
        """
        Check if gateway is ready for connections
        
        Returns:
            bool: True if ready
        """
        # Check process is running
        if not self.process_info.is_running():
            return False
        
        # Check connection manager
        if self.connection_manager:
            return self.connection_manager.is_connected()
        
        # Fallback to port check
        return self._check_port_open()
    
    def _check_port_open(self) -> bool:
        """
        Check if API port is open
        
        Returns:
            bool: True if port is open
        """
        import socket
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', self.config.port))
            sock.close()
            return result == 0
        except:
            return False
    
    # ==========================================================================
    # EVENT MANAGEMENT
    # ==========================================================================
    
    def register_callback(self, event: str, callback):
        """
        Register event callback
        
        Args:
            event: Event name
            callback: Callback function
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def _fire_event(self, event: str, data: Dict[str, Any]):
        """
        Fire event to registered callbacks
        
        Args:
            event: Event name
            data: Event data
        """
        # Log event
        self.events.append({
            'event': event,
            'data': data,
            'timestamp': datetime.now()
        })
        
        # Call callbacks
        for callback in self.callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"Callback error for {event}: {e}")
    
    # ==========================================================================
    # STATUS AND REPORTING
    # ==========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status information
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            'integration_status': self.integration_status.name,
            'process_info': {
                'pid': self.process_info.pid,
                'status': self.process_info.status,
                'cpu_percent': self.process_info.cpu_percent,
                'memory_mb': self.process_info.memory_mb,
                'uptime_seconds': self.process_info.uptime_seconds
            },
            'health_status': self.health_status,
            'config': {
                'mode': self.config.mode.value,
                'trading_mode': self.config.trading_mode,
                'port': self.config.port,
                'client_id': self.config.client_id
            },
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'events_count': len(self.events)
        }
    
    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent events
        
        Args:
            limit: Maximum number of events
            
        Returns:
            List[Dict[str, Any]]: Recent events
        """
        return self.events[-limit:]
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.stop_monitoring()
            
            if self.gateway_automation:
                self.stop_gateway()
            
            self.logger.info("IBAutomaterCore cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_automater(config: Optional[AutomationConfig] = None) -> IBAutomaterCore:
    """
    Factory function to create IB Automater
    
    Args:
        config: Optional automation configuration
        
    Returns:
        IBAutomaterCore: Configured automater instance
    """
    return IBAutomaterCore(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing
    print("=" * 80)
    print("SPYDER I12 - IB Automater Core Test")
    print("=" * 80)
    
    # Create configuration
    config = AutomationConfig(
        mode=AutomationMode.SEMI_AUTO,
        trading_mode="paper",
        port=4002,
        client_id=1
    )
    
    # Create automater
    automater = IBAutomaterCore(config)
    
    print("\n1. Initializing integration with B-series...")
    if automater.initialize():
        print("✅ Integration successful")
        
        print("\n2. Getting status...")
        status = automater.get_status()
        print(f"Integration Status: {status['integration_status']}")
        print(f"Configuration: {status['config']}")
        
        print("\n3. Checking gateway readiness...")
        if automater.is_ready():
            print("✅ Gateway is ready")
        else:
            print("⚠️ Gateway not ready (expected if not running)")
    else:
        print("❌ Integration failed - B-series modules may not be available")
    
    # Cleanup
    automater.cleanup()
    
    print("\n" + "=" * 80)
    print("Test completed!")
