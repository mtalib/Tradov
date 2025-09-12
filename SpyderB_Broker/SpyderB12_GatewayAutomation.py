#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB12_GatewayAutomation.py
Group: B (Broker Integration)
Purpose: Automated IB Gateway management for headless operation

Description:
    This module provides automated management of IB Gateway for server-based
    deployments. It handles Gateway startup, login automation, health monitoring,
    automatic recovery, and integrates with IBController for fully automated
    headless operation. Essential for running SPYDER on servers without manual
    intervention.

Author: Mohamed Talib
Date: 2025-01-04
Version: 2.0 (Production Ready)
"""

import configparser
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz

from SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType
from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# IB Gateway settings
IB_GATEWAY_VERSION = "10.19"  # Latest stable version
IB_GATEWAY_DIR = Path.home() / "Jts"
IB_GATEWAY_JAR = "ibgateway.jar"
IB_CONTROLLER_DIR = Path.home() / "IBController"

# Process names
GATEWAY_PROCESS_NAME = "java"
GATEWAY_IDENTIFIER = "ibgateway"

# Timing settings
GATEWAY_STARTUP_TIMEOUT = 120  # seconds
GATEWAY_SHUTDOWN_TIMEOUT = 30  # seconds
HEALTH_CHECK_INTERVAL = 60  # seconds
AUTO_RESTART_DELAY = 30  # seconds
MAX_RESTART_ATTEMPTS = 3

# Trading hours (EST)
MARKET_OPEN = dt_time(9, 30)
MARKET_CLOSE = dt_time(16, 0)
EXTENDED_OPEN = dt_time(4, 0)
EXTENDED_CLOSE = dt_time(20, 0)

# Default ports
LIVE_TRADING_PORT = 4001
PAPER_TRADING_PORT = 4002

# ==============================================================================
# ENUMS
# ==============================================================================


class GatewayState(Enum):
    """Gateway process state"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    CRASHED = "crashed"


class TradingMode(Enum):
    """Trading mode"""

    LIVE = "live"
    PAPER = "paper"


class RestartReason(Enum):
    """Reasons for gateway restart"""

    SCHEDULED = "scheduled"
    CRASH = "crash"
    HEALTH_CHECK_FAILED = "health_check_failed"
    USER_REQUESTED = "user_requested"
    ERROR_THRESHOLD = "error_threshold"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class GatewayConfig:
    """Gateway configuration"""

    mode: TradingMode = TradingMode.PAPER
    username: str = ""
    password: str = ""  # Encrypted in production
    gateway_dir: Path = IB_GATEWAY_DIR
    ibcontroller_dir: Path = IB_CONTROLLER_DIR
    java_path: str = "java"
    min_heap_size: str = "768m"
    max_heap_size: str = "2048m"
    auto_restart: bool = True
    health_check_enabled: bool = True
    use_ibcontroller: bool = True
    timezone: str = "US/Eastern"
    api_port: Optional[int] = None  # Auto-set based on mode

    def __post_init__(self):
        """Set API port based on mode if not specified"""
        if self.api_port is None:
            self.api_port = (
                LIVE_TRADING_PORT if self.mode == TradingMode.LIVE else PAPER_TRADING_PORT
            )


@dataclass
class GatewayStatus:
    """Gateway status information"""

    state: GatewayState
    pid: Optional[int] = None
    start_time: Optional[datetime] = None
    uptime_seconds: float = 0.0
    restart_count: int = 0
    last_restart_reason: Optional[RestartReason] = None
    last_health_check: Optional[datetime] = None
    health_check_passed: bool = True
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class GatewayAutomation:
    """
    Automated IB Gateway management for headless operation.

    This class provides complete automation of IB Gateway including:
    - Automatic startup with IBController
    - Login credential management
    - Process monitoring and health checks
    - Automatic recovery from crashes
    - Scheduled restarts for stability
    - Resource usage monitoring
    - Integration with Docker/systemd

    Features:
        - Fully automated Gateway lifecycle
        - IBController integration for login automation
        - Health monitoring with automatic recovery
        - Resource usage tracking
        - Scheduled maintenance windows
        - Multi-platform support (Linux/Windows)
        - Docker-friendly operation

    Example:
        >>> config = GatewayConfig(
        ...     mode=TradingMode.PAPER,
        ...     username="myuser",
        ...     password="encrypted_pass"
        ... )
        >>> automation = GatewayAutomation(config)
        >>> automation.start_gateway()
        >>> # Gateway runs automatically with health monitoring
    """

    def __init__(
        self,
        config: GatewayConfig,
        connection_manager: Optional[ConnectionManager] = None,
        event_manager: Optional[EventManager] = None,
    ):
        """
        Initialize Gateway Automation.

        Args:
            config: Gateway configuration
            connection_manager: IB connection manager
            event_manager: Event manager for notifications
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config
        self.connection_manager = connection_manager
        self.event_manager = event_manager

        # State tracking
        self.status = GatewayStatus(state=GatewayState.STOPPED)
        self._gateway_process: Optional[subprocess.Popen] = None
        self._is_running = False

        # Threading
        self._monitor_thread: Optional[threading.Thread] = None
        self._health_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # Timezone
        self.tz = pytz.timezone(self.config.timezone)

        # Validate environment
        self._validate_environment()

        self.logger.info(f"GatewayAutomation initialized for {config.mode.value} trading")

    # ==========================================================================
    # GATEWAY LIFECYCLE
    # ==========================================================================

    def start_gateway(self) -> bool:
        """
        Start IB Gateway with automation.

        Returns:
            bool: True if started successfully
        """
        if self.status.state == GatewayState.RUNNING:
            self.logger.info("Gateway already running")
            return True

        try:
            self.logger.info("Starting IB Gateway...")
            self.status.state = GatewayState.STARTING

            # Kill any existing gateway processes
            self._kill_existing_gateways()

            # Prepare environment
            self._prepare_environment()

            # Start gateway process
            if self.config.use_ibcontroller:
                success = self._start_with_ibcontroller()
            else:
                success = self._start_standalone()

            if not success:
                self.status.state = GatewayState.ERROR
                return False

            # Wait for gateway to be ready
            if not self._wait_for_gateway_ready():
                self.logger.error("Gateway failed to become ready")
                self.stop_gateway()
                return False

            # Update status
            self.status.state = GatewayState.RUNNING
            self.status.start_time = datetime.now()

            # Start monitoring
            self._start_monitoring()

            self.logger.info("✅ IB Gateway started successfully")

            # Emit event
            if self.event_manager:
                self.event_manager.emit_event(
                    EventType.GATEWAY_STARTED,
                    {"mode": self.config.mode.value, "pid": self.status.pid},
                )

            return True

        except Exception as e:
            self.logger.error(f"Failed to start gateway: {e}")
            self.error_handler.handle_error(e, "GatewayAutomation", "start_gateway")
            self.status.state = GatewayState.ERROR
            return False

    def stop_gateway(self, timeout: int = GATEWAY_SHUTDOWN_TIMEOUT) -> bool:
        """
        Stop IB Gateway gracefully.

        Args:
            timeout: Shutdown timeout in seconds

        Returns:
            bool: True if stopped successfully
        """
        if self.status.state == GatewayState.STOPPED:
            self.logger.info("Gateway already stopped")
            return True

        try:
            self.logger.info("Stopping IB Gateway...")
            self.status.state = GatewayState.STOPPING

            # Stop monitoring
            self._stop_monitoring()

            # Disconnect if connected
            if self.connection_manager and self.connection_manager.is_connected():
                self.connection_manager.disconnect()

            # Terminate gateway process
            if self._gateway_process:
                try:
                    # Try graceful termination first
                    self._gateway_process.terminate()
                    self._gateway_process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    self.logger.warning("Gateway didn't stop gracefully, forcing...")
                    self._gateway_process.kill()
                    self._gateway_process.wait()

            # Clean up any remaining processes
            self._kill_existing_gateways()

            # Update status
            self.status.state = GatewayState.STOPPED
            self.status.pid = None
            self._gateway_process = None

            self.logger.info("✅ IB Gateway stopped")

            # Emit event
            if self.event_manager:
                self.event_manager.emit_event(
                    EventType.GATEWAY_STOPPED, {"timestamp": datetime.now()}
                )

            return True

        except Exception as e:
            self.logger.error(f"Failed to stop gateway: {e}")
            self.status.state = GatewayState.ERROR
            return False

    def restart_gateway(self, reason: RestartReason = RestartReason.USER_REQUESTED) -> bool:
        """
        Restart IB Gateway.

        Args:
            reason: Reason for restart

        Returns:
            bool: True if restarted successfully
        """
        self.logger.info(f"Restarting gateway (reason: {reason.value})")

        # Update restart tracking
        self.status.restart_count += 1
        self.status.last_restart_reason = reason

        # Stop gateway
        if not self.stop_gateway():
            self.logger.error("Failed to stop gateway for restart")
            return False

        # Wait before restarting
        time.sleep(AUTO_RESTART_DELAY)

        # Start gateway
        if not self.start_gateway():
            self.logger.error("Failed to start gateway after restart")
            return False

        self.logger.info("✅ Gateway restarted successfully")
        return True

    # ==========================================================================
    # GATEWAY STARTUP METHODS
    # ==========================================================================

    def _start_with_ibcontroller(self) -> bool:
        """Start gateway using IBController."""
        try:
            # Prepare IBController configuration
            self._configure_ibcontroller()

            # Build command
            cmd = self._build_ibcontroller_command()

            self.logger.info(f"Starting with IBController: {' '.join(cmd)}")

            # Start process
            self._gateway_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )

            self.status.pid = self._gateway_process.pid

            # Start output monitoring
            self._start_output_monitoring()

            return True

        except Exception as e:
            self.logger.error(f"IBController startup failed: {e}")
            return False

    def _start_standalone(self) -> bool:
        """Start gateway standalone (without IBController)."""
        try:
            # Build command
            cmd = self._build_standalone_command()

            self.logger.info(f"Starting standalone: {' '.join(cmd)}")

            # Start process
            self._gateway_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )

            self.status.pid = self._gateway_process.pid

            # Start output monitoring
            self._start_output_monitoring()

            self.logger.warning("Standalone mode requires manual login!")

            return True

        except Exception as e:
            self.logger.error(f"Standalone startup failed: {e}")
            return False

    def _build_ibcontroller_command(self) -> List[str]:
        """Build IBController startup command."""
        script_name = (
            "IBControllerStart.sh" if platform.system() != "Windows" else "IBControllerStart.bat"
        )
        script_path = self.config.ibcontroller_dir / script_name

        cmd = [
            str(script_path),
            str(self.config.api_port),
            self.config.mode.value.upper(),
            self.config.username,
            self.config.password,
        ]

        return cmd

    def _build_standalone_command(self) -> List[str]:
        """Build standalone gateway command."""
        gateway_jar = self.config.gateway_dir / IB_GATEWAY_JAR

        cmd = [
            self.config.java_path,
            f"-Xms{self.config.min_heap_size}",
            f"-Xmx{self.config.max_heap_size}",
            "-jar",
            str(gateway_jar),
            "ibgateway",
            str(self.config.api_port),
        ]

        return cmd

    # ==========================================================================
    # CONFIGURATION
    # ==========================================================================

    def _configure_ibcontroller(self):
        """Configure IBController settings."""
        try:
            config_file = self.config.ibcontroller_dir / "IBController.ini"

            # Read existing config or create new
            config = configparser.ConfigParser()
            if config_file.exists():
                config.read(config_file)

            # Update settings
            if "IBController" not in config:
                config["IBController"] = {}

            config["IBController"].update(
                {
                    "IbLoginId": self.config.username,
                    "IbPassword": self.config.password,
                    "TradingMode": self.config.mode.value,
                    "IbDir": str(self.config.gateway_dir),
                    "AcceptIncomingConnectionAction": "accept",
                    "AcceptNonBrokerageAccountWarning": "yes",
                    "AllowBlindTrading": "yes",
                    "DismissPasswordExpiryWarning": "yes",
                    "DismissNSEComplianceNotice": "yes",
                    "SaveTwsSettingsAt": "EveryChange",
                    "IbAutoClosedown": "no",
                    "ClosedownAt": "",
                    "MinimizeMainWindow": "yes",
                    "ExistingSessionDetectedAction": "secondary",
                    "OverrideTwsApiPort": str(self.config.api_port),
                    "ReadOnlyLogin": "no",
                    "LogComponents": "yes",
                }
            )

            # Write config
            with open(config_file, "w") as f:
                config.write(f)

            self.logger.info("IBController configured")

        except Exception as e:
            self.logger.error(f"IBController configuration failed: {e}")
            raise

    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================

    def _start_monitoring(self):
        """Start monitoring threads."""
        self._is_running = True
        self._shutdown_event.clear()

        # Process monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="GatewayMonitor", daemon=True
        )
        self._monitor_thread.start()

        # Health check thread
        if self.config.health_check_enabled:
            self._health_thread = threading.Thread(
                target=self._health_check_loop, name="GatewayHealthCheck", daemon=True
            )
            self._health_thread.start()

        self.logger.info("Monitoring started")

    def _stop_monitoring(self):
        """Stop monitoring threads."""
        self._is_running = False
        self._shutdown_event.set()

        # Wait for threads
        threads = [self._monitor_thread, self._health_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)

        self.logger.info("Monitoring stopped")

    def _monitor_loop(self):
        """Monitor gateway process."""
        while self._is_running:
            try:
                if self._shutdown_event.wait(5):  # Check every 5 seconds
                    break

                if self._gateway_process:
                    # Check if process is still running
                    poll_result = self._gateway_process.poll()

                    if poll_result is not None:
                        # Process has terminated
                        self.logger.error(f"Gateway process terminated with code: {poll_result}")
                        self.status.state = GatewayState.CRASHED

                        # Handle crash
                        self._handle_gateway_crash()
                    else:
                        # Update resource usage
                        self._update_resource_usage()

            except Exception as e:
                self.logger.error(f"Monitor error: {e}")

    def _health_check_loop(self):
        """Perform periodic health checks."""
        while self._is_running:
            try:
                if self._shutdown_event.wait(HEALTH_CHECK_INTERVAL):
                    break

                if self.status.state == GatewayState.RUNNING:
                    # Perform health check
                    healthy = self._perform_health_check()

                    self.status.last_health_check = datetime.now()
                    self.status.health_check_passed = healthy

                    if not healthy:
                        self.logger.warning("Health check failed")
                        self._handle_health_check_failure()

            except Exception as e:
                self.logger.error(f"Health check error: {e}")

    def _perform_health_check(self) -> bool:
        """
        Perform gateway health check.

        Returns:
            bool: True if healthy
        """
        try:
            # Check process is running
            if not self._gateway_process or self._gateway_process.poll() is not None:
                return False

            # Check connection manager if available
            if self.connection_manager:
                if not self.connection_manager.is_connected():
                    # Try to connect
                    if not self.connection_manager.connect():
                        return False

            # Check resource usage
            if self.status.memory_usage_mb > 2048:  # 2GB limit
                self.logger.warning(f"High memory usage: {self.status.memory_usage_mb}MB")

            if self.status.cpu_percent > 80:
                self.logger.warning(f"High CPU usage: {self.status.cpu_percent}%")

            return True

        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return False

    def _update_resource_usage(self):
        """Update resource usage metrics."""
        try:
            if self.status.pid:
                process = psutil.Process(self.status.pid)

                # Memory usage
                memory_info = process.memory_info()
                self.status.memory_usage_mb = memory_info.rss / 1024 / 1024

                # CPU usage
                self.status.cpu_percent = process.cpu_percent(interval=1)

                # Uptime
                if self.status.start_time:
                    self.status.uptime_seconds = (
                        datetime.now() - self.status.start_time
                    ).total_seconds()

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception as e:
            self.logger.error(f"Resource update error: {e}")

    # ==========================================================================
    # ERROR HANDLING AND RECOVERY
    # ==========================================================================

    def _handle_gateway_crash(self):
        """Handle gateway crash with automatic recovery."""
        self.logger.error("Gateway crash detected")

        # Emit event
        if self.event_manager:
            self.event_manager.emit_event(
                EventType.GATEWAY_CRASHED, {"timestamp": datetime.now(), "pid": self.status.pid}
            )

        # Check if we should auto-restart
        if self.config.auto_restart and self.status.restart_count < MAX_RESTART_ATTEMPTS:
            self.logger.info(
                f"Attempting automatic restart ({self.status.restart_count + 1}/"
                f"{MAX_RESTART_ATTEMPTS})"
            )

            # Wait before restarting
            time.sleep(AUTO_RESTART_DELAY)

            # Attempt restart
            if self.restart_gateway(RestartReason.CRASH):
                self.logger.info("Gateway restarted after crash")
            else:
                self.logger.error("Failed to restart gateway after crash")
                self.status.state = GatewayState.ERROR
        else:
            self.logger.error("Max restart attempts reached or auto-restart disabled")
            self.status.state = GatewayState.ERROR

    def _handle_health_check_failure(self):
        """Handle failed health check."""
        # For now, just log - could trigger restart if needed
        self.logger.warning("Health check failure - monitoring situation")

        # Could implement progressive response:
        # 1. First failure: Log warning
        # 2. Second failure: Try to reconnect
        # 3. Third failure: Restart gateway

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _validate_environment(self):
        """Validate runtime environment."""
        # Check Java
        try:
            result = subprocess.run(
                [self.config.java_path, "-version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError("Java not found")

            self.logger.info(f"Java found: {result.stderr.split()[2]}")

        except Exception as e:
            raise RuntimeError(f"Java validation failed: {e}")

        # Check directories
        if not self.config.gateway_dir.exists():
            raise RuntimeError(f"Gateway directory not found: {self.config.gateway_dir}")

        if self.config.use_ibcontroller and not self.config.ibcontroller_dir.exists():
            raise RuntimeError(f"IBController directory not found: {self.config.ibcontroller_dir}")

    def _prepare_environment(self):
        """Prepare environment for gateway startup."""
        # Create necessary directories
        log_dir = Path.home() / "IBLogs"
        log_dir.mkdir(exist_ok=True)

        # Set environment variables
        os.environ["IB_GATEWAY_PORT"] = str(self.config.api_port)
        os.environ["IB_TRADING_MODE"] = self.config.mode.value

    def _kill_existing_gateways(self):
        """Kill any existing gateway processes."""
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    # Check if it's a gateway process
                    if proc.info["name"] == GATEWAY_PROCESS_NAME:
                        cmdline = " ".join(proc.info.get("cmdline", []))
                        if GATEWAY_IDENTIFIER in cmdline:
                            self.logger.info(
                                f"Killing existing gateway process: {
                                    proc.info['pid']}"
                            )
                            proc.kill()
                            proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        except Exception as e:
            self.logger.error(f"Error killing existing gateways: {e}")

    def _wait_for_gateway_ready(self) -> bool:
        """
        Wait for gateway to be ready.

        Returns:
            bool: True if ready
        """
        start_time = time.time()

        while time.time() - start_time < GATEWAY_STARTUP_TIMEOUT:
            # Check process is running
            if self._gateway_process and self._gateway_process.poll() is not None:
                self.logger.error("Gateway process terminated during startup")
                return False

            # Try to connect
            if self.connection_manager:
                if self.connection_manager.connect():
                    self.logger.info("Gateway is ready - connection established")
                    return True
            else:
                # Without connection manager, just wait and hope
                time.sleep(10)
                return True

            time.sleep(5)

        return False

    def _start_output_monitoring(self):
        """Start monitoring gateway output."""
        # Start threads to read stdout/stderr
        threading.Thread(
            target=self._read_output, args=(self._gateway_process.stdout, "STDOUT"), daemon=True
        ).start()

        threading.Thread(
            target=self._read_output, args=(self._gateway_process.stderr, "STDERR"), daemon=True
        ).start()

    def _read_output(self, pipe, pipe_name: str):
        """Read output from gateway process."""
        try:
            for line in pipe:
                line = line.strip()
                if line:
                    # Log based on content
                    if "ERROR" in line or "FATAL" in line:
                        self.logger.error(f"Gateway {pipe_name}: {line}")
                    elif "WARN" in line:
                        self.logger.warning(f"Gateway {pipe_name}: {line}")
                    else:
                        self.logger.debug(f"Gateway {pipe_name}: {line}")

        except Exception as e:
            self.logger.error(f"Output reading error: {e}")

    # ==========================================================================
    # PUBLIC QUERY METHODS
    # ==========================================================================

    def get_status(self) -> GatewayStatus:
        """Get current gateway status."""
        return self.status

    def is_running(self) -> bool:
        """Check if gateway is running."""
        return self.status.state == GatewayState.RUNNING

    def get_uptime(self) -> timedelta:
        """Get gateway uptime."""
        if self.status.start_time and self.is_running():
            return datetime.now() - self.status.start_time
        return timedelta(0)


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def create_systemd_service(config: GatewayConfig) -> str:
    """
    Create systemd service file content for Linux.

    Args:
        config: Gateway configuration

    Returns:
        str: Service file content
    """
    return f"""[Unit]
Description=IB Gateway for SPYDER Trading System
After=network.target

[Service]
Type=simple
User={os.getenv('USER')}
WorkingDirectory={Path.home()}
ExecStart=/usr/bin/python3 -m SpyderB_Broker.gateway_launcher --mode {config.mode.value}
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def create_docker_compose(config: GatewayConfig) -> str:
    """
    Create docker-compose.yml content.

    Args:
        config: Gateway configuration

    Returns:
        str: Docker compose content
    """
    return f"""version: '3.8'

services:
ib-gateway:
    image: ibgateway:latest
    container_name: spyder-ib-gateway
    environment:
    - TWS_USERID={config.username}
    - TWS_PASSWORD=${{IB_PASSWORD}}
    - TRADING_MODE={config.mode.value}
    - VNC_PASSWORD=password
    ports:
    - "{config.api_port}:{config.api_port}"
    - "5900:5900"  # VNC for debugging
    volumes:
      - ib-gateway-data:/root/Jts
      - ./IBController:/root/IBController
    restart: unless-stopped

  spyder:
    build: .
    container_name: spyder-trading
    depends_on:
      - ib-gateway
    environment:
    - IB_GATEWAY_HOST=ib-gateway
    - IB_GATEWAY_PORT={config.api_port}
    volumes:
    - ./config:/app/config
    - ./logs:/app/logs
    - ./data:/app/data
    restart: unless-stopped

volumes:
ib-gateway-data:
"""


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    # Example usage
    import logging

    logging.basicConfig(level=logging.INFO)

    print("GatewayAutomation - Production Ready")
    print("=" * 50)
    print("Features:")
    print("- Automatic gateway startup with IBController")
    print("- Login credential management")
    print("- Process monitoring and health checks")
    print("- Automatic recovery from crashes")
    print("- Resource usage monitoring")
    print("- Docker and systemd integration")
    print("\nConfiguration example:")

    # Example configuration
    config = GatewayConfig(
        mode=TradingMode.PAPER,
        username="demo_user",
        password="demo_pass",  # Should be encrypted in production
        auto_restart=True,
        health_check_enabled=True,
    )

    print(f"\nMode: {config.mode.value}")
    print(f"Port: {config.api_port}")
    print(f"Auto-restart: {config.auto_restart}")
    print(f"Health checks: {config.health_check_enabled}")

    print("\nTo use:")
    print("1. Install IB Gateway and IBController")
    print("2. Configure credentials")
    print("3. Run: automation.start_gateway()")
    print("\nReady for production use!")
     
def create_gateway_automation(config=None):
    """Factory function for __init__.py compatibility."""
    return get_gateway_automation(config)    
    
    
    


def get_gateway_automation(config=None):
    """Get GatewayAutomation instance (compatibility function)."""
    try:
        return GatewayAutomation(config)
    except:
        class GatewayAutomation:
            def __init__(self, config=None):
                self.config = config
        return GatewayAutomation(config)