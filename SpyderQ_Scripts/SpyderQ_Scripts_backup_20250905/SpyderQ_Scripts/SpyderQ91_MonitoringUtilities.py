#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ91_MonitoringUtilities.py
Purpose: Consolidated system monitoring and status utilities
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-05 Time: 16:30:00

Module Description:
    This module consolidates system monitoring functionality including real-time
    status monitoring, IB Gateway connectivity checks, process monitoring, and
    system health tracking. Provides both CLI and programmatic interfaces for
    monitoring all Spyder components, tracking resource usage, and alerting on
    issues. Replaces multiple shell scripts with unified Python implementation.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import psutil
import socket
import subprocess
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import threading
import signal

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
    import ib_async
    from ib_async import IB, util
except ImportError as e:
    print(f"Warning: Some imports failed: {e}")
    ib_async = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add Spyder home to path if not already present
SPYDER_HOME = os.environ.get("SPYDER_HOME", "/home/adam/Projects/Spyder")
if SPYDER_HOME not in sys.path:
    sys.path.insert(0, SPYDER_HOME)

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import utilities: {e}")
    import logging
    SpyderLogger = logging
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# System paths
LOGS_DIR = Path(SPYDER_HOME) / "logs"
DATA_DIR = Path(SPYDER_HOME) / "data"
CONFIG_DIR = Path(SPYDER_HOME) / "config"
PID_DIR = Path(SPYDER_HOME) / "pids"

# IB Gateway Configuration
IB_GATEWAY_PORTS = {
    "paper": 7497,
    "live": 7496,
    "gateway": 4001,
    "tws": 4002
}

# Multi-client configuration (9 clients)
MULTI_CLIENT_PORTS = list(range(7497, 7506))  # 7497-7505 for 9 clients
CLIENT_NAMES = [f"Client_{i}" for i in range(1, 10)]

# Monitoring intervals (seconds)
DEFAULT_MONITOR_INTERVAL = 5
HEALTH_CHECK_INTERVAL = 30
RESOURCE_CHECK_INTERVAL = 10

# Resource thresholds
CPU_WARNING_THRESHOLD = 80.0
MEMORY_WARNING_THRESHOLD = 85.0
DISK_WARNING_THRESHOLD = 90.0

# Process names to monitor
MONITORED_PROCESSES = [
    "python3",
    "ib_gateway",
    "java",  # IB Gateway runs on Java
    "prometheus",
    "node_exporter"
]

# ==============================================================================
# ENUMS
# ==============================================================================
class ServiceStatus(Enum):
    """Service status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    WARNING = "warning"
    UNKNOWN = "unknown"

class HealthStatus(Enum):
    """System health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ProcessInfo:
    """Information about a running process"""
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str
    create_time: float
    cmdline: List[str]

@dataclass
class ServiceInfo:
    """Information about a Spyder service"""
    name: str
    status: ServiceStatus
    pid: Optional[int]
    uptime: Optional[timedelta]
    cpu_usage: float
    memory_usage: float
    port: Optional[int]
    last_check: datetime

@dataclass
class IBConnectionStatus:
    """IB Gateway connection status"""
    gateway_running: bool
    port_open: bool
    api_connected: bool
    account: Optional[str]
    connection_time: Optional[datetime]
    last_order_time: Optional[datetime]
    positions_count: int
    error_messages: List[str]

@dataclass
class SystemHealth:
    """Overall system health status"""
    status: HealthStatus
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_services: int
    total_services: int
    ib_connected: bool
    alerts: List[Dict[str, Any]]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MonitoringUtilities:
    """
    Consolidated monitoring utilities for Spyder system.
    
    This class provides comprehensive monitoring capabilities including
    service status tracking, IB Gateway connectivity monitoring, resource
    usage tracking, and health checks. Supports both real-time monitoring
    and point-in-time status checks.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        monitoring: Whether continuous monitoring is active
        services: Dictionary of monitored services
        
    Example:
        >>> monitor = MonitoringUtilities()
        >>> status = monitor.get_system_status()
        >>> monitor.start_live_monitoring(interval=5)
    """
    
    def __init__(self):
        """Initialize monitoring utilities."""
        self.logger = SpyderLogger.get_logger(__name__) if SpyderLogger else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        self.monitoring = False
        self.monitor_thread = None
        self.services: Dict[str, ServiceInfo] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.ib_connection: Optional[IBConnectionStatus] = None
        
        # Create PID directory if needed
        PID_DIR.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("MonitoringUtilities initialized")
        
    # ==========================================================================
    # SYSTEM STATUS METHODS
    # ==========================================================================
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary containing full system status
        """
        self.logger.info("Getting system status")
        
        status = {
            "timestamp": datetime.now().isoformat(),
            "system": self._get_system_info(),
            "resources": self._get_resource_usage(),
            "services": self._get_services_status(),
            "ib_gateway": self._get_ib_status(),
            "processes": self._get_process_list(),
            "health": self._calculate_health_status(),
            "alerts": self.alerts[-10:] if self.alerts else []  # Last 10 alerts
        }
        
        return status
        
    def _get_system_info(self) -> Dict[str, Any]:
        """Get basic system information."""
        try:
            return {
                "hostname": socket.gethostname(),
                "platform": sys.platform,
                "python_version": sys.version,
                "spyder_home": SPYDER_HOME,
                "uptime": self._get_system_uptime()
            }
        except Exception as e:
            self.logger.error(f"Error getting system info: {e}")
            return {}
            
    def _get_resource_usage(self) -> Dict[str, Any]:
        """Get system resource usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(SPYDER_HOME)
            
            return {
                "cpu": {
                    "percent": cpu_percent,
                    "cores": psutil.cpu_count(),
                    "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                "memory": {
                    "percent": memory.percent,
                    "used_gb": memory.used / (1024**3),
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3)
                },
                "disk": {
                    "percent": disk.percent,
                    "used_gb": disk.used / (1024**3),
                    "total_gb": disk.total / (1024**3),
                    "free_gb": disk.free / (1024**3)
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting resource usage: {e}")
            return {}
            
    def _get_system_uptime(self) -> str:
        """Get system uptime."""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            return f"{days}d {hours}h {minutes}m"
        except Exception as e:
            return "unknown"
            
    # ==========================================================================
    # SERVICE MONITORING
    # ==========================================================================
    def _get_services_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all Spyder services."""
        services = {}
        
        # Check main Python services
        services["spyder_main"] = self._check_python_service("SpyderA01_Main.py")
        services["watchdog"] = self._check_python_service("SpyderQ24_ProductionWatchdog.py")
        services["system_monitor"] = self._check_python_service("SpyderQ25_SystemMonitor.py")
        
        # Check systemd services
        services["spyder_service"] = self._check_systemd_service("spyder")
        services["watchdog_service"] = self._check_systemd_service("spyder-watchdog")
        services["metrics_service"] = self._check_systemd_service("spyder-metrics")
        
        # Check Docker containers
        services["ib_gateway_docker"] = self._check_docker_container("ib_gateway")
        
        return services
        
    def _check_python_service(self, script_name: str) -> Dict[str, Any]:
        """Check if a Python script is running."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if script_name in cmdline:
                        uptime = datetime.now() - datetime.fromtimestamp(proc.info['create_time'])
                        return {
                            "status": ServiceStatus.RUNNING.value,
                            "pid": proc.info['pid'],
                            "uptime": str(uptime),
                            "cpu_percent": proc.cpu_percent(),
                            "memory_percent": proc.memory_percent()
                        }
            
            return {"status": ServiceStatus.STOPPED.value}
            
        except Exception as e:
            self.logger.error(f"Error checking Python service {script_name}: {e}")
            return {"status": ServiceStatus.ERROR.value, "error": str(e)}
            
    def _check_systemd_service(self, service_name: str) -> Dict[str, Any]:
        """Check systemd service status."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                status = ServiceStatus.RUNNING
            else:
                status = ServiceStatus.STOPPED
                
            # Get more details
            result = subprocess.run(
                ["systemctl", "status", service_name, "--no-pager"],
                capture_output=True,
                text=True
            )
            
            return {
                "status": status.value,
                "details": result.stdout[:500]  # First 500 chars
            }
            
        except Exception as e:
            return {"status": ServiceStatus.UNKNOWN.value, "error": str(e)}
            
    def _check_docker_container(self, container_name: str) -> Dict[str, Any]:
        """Check Docker container status."""
        try:
            result = subprocess.run(
                ["docker", "inspect", container_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                info = json.loads(result.stdout)[0]
                state = info.get("State", {})
                
                return {
                    "status": ServiceStatus.RUNNING.value if state.get("Running") else ServiceStatus.STOPPED.value,
                    "started_at": state.get("StartedAt"),
                    "health": state.get("Health", {}).get("Status", "unknown")
                }
            else:
                return {"status": ServiceStatus.STOPPED.value}
                
        except Exception as e:
            return {"status": ServiceStatus.UNKNOWN.value, "error": str(e)}
            
    # ==========================================================================
    # IB GATEWAY MONITORING
    # ==========================================================================
    def check_ib_connection(self) -> IBConnectionStatus:
        """
        Check IB Gateway connection status.
        
        Returns:
            IBConnectionStatus object with connection details
        """
        self.logger.info("Checking IB Gateway connection")
        
        status = IBConnectionStatus(
            gateway_running=False,
            port_open=False,
            api_connected=False,
            account=None,
            connection_time=None,
            last_order_time=None,
            positions_count=0,
            error_messages=[]
        )
        
        # Check if gateway process is running
        status.gateway_running = self._is_ib_gateway_running()
        
        # Check if port is open
        for port_name, port_num in IB_GATEWAY_PORTS.items():
            if self._is_port_open("localhost", port_num):
                status.port_open = True
                self.logger.info(f"IB Gateway port {port_num} ({port_name}) is open")
                break
                
        # Try to connect via API if ib_async is available
        if ib_async and status.port_open:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                status.api_connected = loop.run_until_complete(self._test_ib_api_connection())
                loop.close()
            except Exception as e:
                status.error_messages.append(f"API connection test failed: {e}")
                
        self.ib_connection = status
        return status
        
    def _is_ib_gateway_running(self) -> bool:
        """Check if IB Gateway process is running."""
        try:
            # Check for Java process with IB Gateway
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] in ['java', 'java.exe']:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'ibgateway' in cmdline.lower() or 'tws' in cmdline.lower():
                        return True
                        
            # Check Docker container
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=ib_gateway", "--format", "{{.Names}}"],
                capture_output=True,
                text=True
            )
            return "ib_gateway" in result.stdout
            
        except Exception as e:
            self.logger.error(f"Error checking IB Gateway process: {e}")
            return False
            
    def _is_port_open(self, host: str, port: int) -> bool:
        """Check if a port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
            
    async def _test_ib_api_connection(self) -> bool:
        """Test IB API connection."""
        if not ib_async:
            return False
            
        ib = IB()
        try:
            # Try common ports
            for port in [7497, 7496, 4001, 4002]:
                try:
                    await ib.connectAsync('127.0.0.1', port, clientId=999)
                    self.logger.info(f"Successfully connected to IB on port {port}")
                    ib.disconnect()
                    return True
                except Exception:
                    continue
                    
            return False
            
        except Exception as e:
            self.logger.error(f"IB API connection test failed: {e}")
            return False
        finally:
            if ib.isConnected():
                ib.disconnect()
                
    def _get_ib_status(self) -> Dict[str, Any]:
        """Get IB Gateway status summary."""
        if not self.ib_connection:
            self.ib_connection = self.check_ib_connection()
            
        return {
            "gateway_running": self.ib_connection.gateway_running,
            "port_open": self.ib_connection.port_open,
            "api_connected": self.ib_connection.api_connected,
            "account": self.ib_connection.account,
            "positions": self.ib_connection.positions_count,
            "errors": self.ib_connection.error_messages
        }
        
    # ==========================================================================
    # PROCESS MONITORING
    # ==========================================================================
    def _get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of relevant running processes."""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
                # Filter for relevant processes
                if proc.info['name'] in MONITORED_PROCESSES:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    
                    # Check if it's a Spyder-related process
                    if 'spyder' in cmdline.lower() or 'ib_gateway' in cmdline.lower():
                        processes.append({
                            "pid": proc.info['pid'],
                            "name": proc.info['name'],
                            "cpu_percent": proc.info['cpu_percent'],
                            "memory_percent": proc.info['memory_percent'],
                            "cmdline": cmdline[:100]  # First 100 chars
                        })
                        
        except Exception as e:
            self.logger.error(f"Error getting process list: {e}")
            
        return processes
        
    # ==========================================================================
    # HEALTH CHECKS
    # ==========================================================================
    def _calculate_health_status(self) -> Dict[str, Any]:
        """Calculate overall system health status."""
        issues = []
        status = HealthStatus.HEALTHY
        
        # Check resource usage
        resources = self._get_resource_usage()
        
        if resources.get('cpu', {}).get('percent', 0) > CPU_WARNING_THRESHOLD:
            issues.append(f"High CPU usage: {resources['cpu']['percent']:.1f}%")
            status = HealthStatus.DEGRADED
            
        if resources.get('memory', {}).get('percent', 0) > MEMORY_WARNING_THRESHOLD:
            issues.append(f"High memory usage: {resources['memory']['percent']:.1f}%")
            status = HealthStatus.DEGRADED
            
        if resources.get('disk', {}).get('percent', 0) > DISK_WARNING_THRESHOLD:
            issues.append(f"High disk usage: {resources['disk']['percent']:.1f}%")
            status = HealthStatus.WARNING
            
        # Check services
        services = self._get_services_status()
        stopped_services = [name for name, info in services.items() 
                          if info.get('status') == ServiceStatus.STOPPED.value]
        
        if len(stopped_services) > 2:
            issues.append(f"{len(stopped_services)} services are stopped")
            status = HealthStatus.CRITICAL
            
        # Check IB connection
        if self.ib_connection and not self.ib_connection.gateway_running:
            issues.append("IB Gateway is not running")
            status = HealthStatus.DEGRADED
            
        return {
            "status": status.value,
            "issues": issues,
            "checked_at": datetime.now().isoformat()
        }
        
    # ==========================================================================
    # LIVE MONITORING
    # ==========================================================================
    def start_live_monitoring(self, interval: int = DEFAULT_MONITOR_INTERVAL) -> None:
        """
        Start live system monitoring.
        
        Args:
            interval: Monitoring interval in seconds
        """
        if self.monitoring:
            self.logger.warning("Monitoring already active")
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info(f"Started live monitoring with {interval}s interval")
        
    def stop_monitoring(self) -> None:
        """Stop live monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Stopped monitoring")
        
    def _monitor_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        last_health_check = datetime.now()
        
        while self.monitoring:
            try:
                # Get current status
                status = self.get_system_status()
                
                # Check for alerts
                self._check_alerts(status)
                
                # Periodic health check
                if datetime.now() - last_health_check > timedelta(seconds=HEALTH_CHECK_INTERVAL):
                    health = self._calculate_health_status()
                    if health['status'] != HealthStatus.HEALTHY.value:
                        self._create_alert(
                            AlertLevel.WARNING,
                            f"System health: {health['status']}",
                            health['issues']
                        )
                    last_health_check = datetime.now()
                    
                # Display status (can be customized)
                self._display_status(status)
                
                # Wait for next iteration
                time.sleep(interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                time.sleep(interval)
                
    def _check_alerts(self, status: Dict[str, Any]) -> None:
        """Check for conditions that require alerts."""
        resources = status.get('resources', {})
        
        # CPU alert
        cpu_percent = resources.get('cpu', {}).get('percent', 0)
        if cpu_percent > CPU_WARNING_THRESHOLD:
            self._create_alert(
                AlertLevel.WARNING,
                f"High CPU usage: {cpu_percent:.1f}%",
                {"threshold": CPU_WARNING_THRESHOLD}
            )
            
        # Memory alert
        mem_percent = resources.get('memory', {}).get('percent', 0)
        if mem_percent > MEMORY_WARNING_THRESHOLD:
            self._create_alert(
                AlertLevel.WARNING,
                f"High memory usage: {mem_percent:.1f}%",
                {"threshold": MEMORY_WARNING_THRESHOLD}
            )
            
    def _create_alert(self, level: AlertLevel, message: str, details: Any = None) -> None:
        """Create an alert."""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "level": level.value,
            "message": message,
            "details": details
        }
        
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
            
        # Log based on level
        if level == AlertLevel.CRITICAL:
            self.logger.critical(message)
        elif level == AlertLevel.ERROR:
            self.logger.error(message)
        elif level == AlertLevel.WARNING:
            self.logger.warning(message)
        else:
            self.logger.info(message)
            
    def _display_status(self, status: Dict[str, Any]) -> None:
        """Display status in terminal."""
        # Clear screen for live update effect
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 60)
        print("SPYDER SYSTEM MONITOR")
        print("=" * 60)
        print(f"Time: {status['timestamp']}")
        print()
        
        # Resources
        resources = status.get('resources', {})
        print("RESOURCES:")
        print(f"  CPU: {resources.get('cpu', {}).get('percent', 0):.1f}%")
        print(f"  Memory: {resources.get('memory', {}).get('percent', 0):.1f}%")
        print(f"  Disk: {resources.get('disk', {}).get('percent', 0):.1f}%")
        print()
        
        # Services
        print("SERVICES:")
        for name, info in status.get('services', {}).items():
            status_str = info.get('status', 'unknown')
            symbol = "✓" if status_str == 'running' else "✗"
            print(f"  {symbol} {name}: {status_str}")
        print()
        
        # IB Gateway
        ib = status.get('ib_gateway', {})
        print("IB GATEWAY:")
        print(f"  Running: {ib.get('gateway_running', False)}")
        print(f"  Port Open: {ib.get('port_open', False)}")
        print(f"  API Connected: {ib.get('api_connected', False)}")
        print()
        
        # Health
        health = status.get('health', {})
        print(f"HEALTH: {health.get('status', 'unknown')}")
        if health.get('issues'):
            for issue in health['issues']:
                print(f"  ⚠ {issue}")
        
        print()
        print("Press Ctrl+C to stop monitoring")
        print("=" * 60)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def quick_status() -> Dict[str, Any]:
    """Get quick system status."""
    monitor = MonitoringUtilities()
    return monitor.get_system_status()

def check_ib_gateway() -> bool:
    """Quick IB Gateway check."""
    monitor = MonitoringUtilities()
    status = monitor.check_ib_connection()
    return status.gateway_running and status.port_open

def monitor_system(interval: int = 5) -> None:
    """Start system monitoring."""
    monitor = MonitoringUtilities()
    
    # Set up signal handler for clean exit
    def signal_handler(signum, frame):
        print("\nStopping monitor...")
        monitor.stop_monitoring()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start monitoring
    monitor.start_live_monitoring(interval)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop_monitoring()

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
def main():
    """Main entry point for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Spyder Monitoring Utilities - System Status and Monitoring"
    )
    
    parser.add_argument(
        "action",
        choices=["status", "monitor", "ib-check", "services", "health", "resources"],
        help="Action to perform"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Monitoring interval in seconds (for monitor action)"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Initialize monitor
    monitor = MonitoringUtilities()
    
    # Perform requested action
    if args.action == "status":
        status = monitor.get_system_status()
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            # Pretty print status
            print("\nSYSTEM STATUS")
            print("=" * 60)
            print(f"Timestamp: {status['timestamp']}")
            print(f"Host: {status['system']['hostname']}")
            print(f"Uptime: {status['system']['uptime']}")
            print()
            
            # Resources
            resources = status['resources']
            print("Resources:")
            print(f"  CPU: {resources['cpu']['percent']:.1f}%")
            print(f"  Memory: {resources['memory']['percent']:.1f}% ({resources['memory']['used_gb']:.1f}/{resources['memory']['total_gb']:.1f} GB)")
            print(f"  Disk: {resources['disk']['percent']:.1f}% ({resources['disk']['free_gb']:.1f} GB free)")
            print()
            
            # Services
            print("Services:")
            for name, info in status['services'].items():
                print(f"  {name}: {info.get('status', 'unknown')}")
                
    elif args.action == "monitor":
        print(f"Starting live monitoring (interval: {args.interval}s)")
        print("Press Ctrl+C to stop")
        monitor_system(args.interval)
        
    elif args.action == "ib-check":
        status = monitor.check_ib_connection()
        if args.json:
            print(json.dumps({
                "gateway_running": status.gateway_running,
                "port_open": status.port_open,
                "api_connected": status.api_connected,
                "errors": status.error_messages
            }, indent=2))
        else:
            print("\nIB GATEWAY STATUS")
            print("=" * 40)
            print(f"Gateway Running: {'✓' if status.gateway_running else '✗'}")
            print(f"Port Open: {'✓' if status.port_open else '✗'}")
            print(f"API Connected: {'✓' if status.api_connected else '✗'}")
            if status.error_messages:
                print("\nErrors:")
                for error in status.error_messages:
                    print(f"  - {error}")
                    
    elif args.action == "services":
        services = monitor._get_services_status()
        if args.json:
            print(json.dumps(services, indent=2, default=str))
        else:
            print("\nSERVICE STATUS")
            print("=" * 40)
            for name, info in services.items():
                status = info.get('status', 'unknown')
                symbol = "✓" if status == 'running' else "✗"
                print(f"{symbol} {name}: {status}")
                if args.verbose and 'pid' in info:
                    print(f"    PID: {info['pid']}")
                    if 'uptime' in info:
                        print(f"    Uptime: {info['uptime']}")
                        
    elif args.action == "health":
        health = monitor._calculate_health_status()
        if args.json:
            print(json.dumps(health, indent=2))
        else:
            print("\nSYSTEM HEALTH")
            print("=" * 40)
            print(f"Status: {health['status']}")
            print(f"Checked: {health['checked_at']}")
            if health['issues']:
                print("\nIssues:")
                for issue in health['issues']:
                    print(f"  ⚠ {issue}")
            else:
                print("\n✓ No issues detected")
                
    elif args.action == "resources":
        resources = monitor._get_resource_usage()
        if args.json:
            print(json.dumps(resources, indent=2))
        else:
            print("\nRESOURCE USAGE")
            print("=" * 40)
            print(f"CPU: {resources['cpu']['percent']:.1f}% ({resources['cpu']['cores']} cores)")
            if resources['cpu']['load_avg']:
                print(f"  Load Average: {', '.join(map(str, resources['cpu']['load_avg']))}")
            print(f"Memory: {resources['memory']['percent']:.1f}%")
            print(f"  Used: {resources['memory']['used_gb']:.2f} GB")
            print(f"  Total: {resources['memory']['total_gb']:.2f} GB")
            print(f"  Available: {resources['memory']['available_gb']:.2f} GB")
            print(f"Disk: {resources['disk']['percent']:.1f}%")
            print(f"  Used: {resources['disk']['used_gb']:.2f} GB")
            print(f"  Total: {resources['disk']['total_gb']:.2f} GB")
            print(f"  Free: {resources['disk']['free_gb']:.2f} GB")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    main()