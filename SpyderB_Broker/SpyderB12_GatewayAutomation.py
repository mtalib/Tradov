#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB12_GatewayAutomation.py
Group: B (Broker Integration)
Purpose: Automated IB Gateway management for headless operation

Description:
    This module provides automated management of IB Gateway for server-based
    deployments. It handles Gateway startup, login automation using IBController,
    health monitoring, and recovery procedures. Essential for running SPYDER
    on headless servers without manual intervention.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 20:30:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import subprocess
import socket
import signal
import threading
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import yaml

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Gateway configuration
DEFAULT_GATEWAY_PORT = 4002  # Paper trading
DEFAULT_LIVE_PORT = 4001     # Live trading
GATEWAY_STARTUP_TIMEOUT = 120  # seconds
GATEWAY_HEALTH_CHECK_INTERVAL = 30  # seconds
MAX_RESTART_ATTEMPTS = 3

# IBC configuration
IBC_VERSION = "3.15.0"
IBC_JAR_PATH = "/opt/ibc/IBC.jar"
GATEWAY_PATH = "/opt/ibgateway"
CONFIG_PATH = Path.home() / ".spyder" / "ibc" / "config.ini"

# File paths
LOG_DIR = Path("/var/log/spyder/gateway")
PID_FILE = Path("/var/run/spyder/gateway.pid")

# ==============================================================================
# ENUMS
# ==============================================================================
class GatewayState(Enum):
    """Gateway operational states"""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    RESTARTING = "RESTARTING"

class TradingMode(Enum):
    """Trading mode configuration"""
    PAPER = "paper"
    LIVE = "live"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GatewayConfig:
    """Gateway configuration parameters"""
    username: str
    password: str  # Should be encrypted in production
    trading_mode: TradingMode = TradingMode.PAPER
    gateway_port: int = DEFAULT_GATEWAY_PORT
    ibc_path: str = IBC_JAR_PATH
    gateway_path: str = GATEWAY_PATH
    auto_restart: bool = True
    min_heap_size: str = "512M"
    max_heap_size: str = "2048M"
    
@dataclass
class GatewayStatus:
    """Gateway status information"""
    state: GatewayState
    pid: Optional[int] = None
    port: int = DEFAULT_GATEWAY_PORT
    uptime: Optional[timedelta] = None
    last_error: Optional[str] = None
    restart_count: int = 0
    last_health_check: Optional[datetime] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class GatewayAutomation:
    """
    Automated IB Gateway management for headless operation.
    
    This class provides comprehensive Gateway lifecycle management including
    automated startup, login via IBController, health monitoring, and
    recovery procedures. Essential for server deployments.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Gateway configuration
        status: Current Gateway status
        
    Example:
        >>> gateway = GatewayAutomation(config)
        >>> gateway.start()
        >>> if gateway.is_healthy():
        >>>     print("Gateway ready for connections")
    """
    
    def __init__(self, config: GatewayConfig):
        """Initialize Gateway automation."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config
        
        # Status tracking
        self.status = GatewayStatus(
            state=GatewayState.STOPPED,
            port=config.gateway_port
        )
        
        # Process management
        self.gateway_process: Optional[subprocess.Popen] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Ensure directories exist
        self._ensure_directories()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start IB Gateway with automated login.
        
        Returns:
            bool: True if Gateway started successfully
        """
        if self.status.state == GatewayState.RUNNING:
            self.logger.warning("Gateway already running")
            return True
            
        try:
            self.status.state = GatewayState.STARTING
            self.logger.info(f"Starting IB Gateway in {self.config.trading_mode.value} mode...")
            
            # Generate IBC configuration
            self._generate_ibc_config()
            
            # Build command
            cmd = self._build_gateway_command()
            
            # Start Gateway process
            self.gateway_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Save PID
            self.status.pid = self.gateway_process.pid
            self._save_pid()
            
            # Wait for Gateway to be ready
            if self._wait_for_gateway():
                self.status.state = GatewayState.RUNNING
                self.status.uptime = timedelta(seconds=0)
                
                # Start monitoring thread
                self._start_monitoring()
                
                self.logger.info("IB Gateway started successfully")
                return True
            else:
                self.logger.error("Gateway failed to start within timeout")
                self.stop()
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start Gateway: {e}")
            self.status.state = GatewayState.ERROR
            self.status.last_error = str(e)
            return False
            
    def stop(self) -> None:
        """Stop IB Gateway gracefully."""
        if self.status.state == GatewayState.STOPPED:
            return
            
        self.logger.info("Stopping IB Gateway...")
        self.running = False
        
        # Stop monitoring
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            
        # Terminate Gateway process
        if self.gateway_process:
            try:
                # Send SIGTERM to process group
                os.killpg(os.getpgid(self.gateway_process.pid), signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    self.gateway_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if needed
                    os.killpg(os.getpgid(self.gateway_process.pid), signal.SIGKILL)
                    
            except Exception as e:
                self.logger.error(f"Error stopping Gateway: {e}")
                
        # Clean up
        self.gateway_process = None
        self.status.state = GatewayState.STOPPED
        self.status.pid = None
        self._remove_pid()
        
        self.logger.info("IB Gateway stopped")
        
    def restart(self) -> bool:
        """
        Restart IB Gateway.
        
        Returns:
            bool: True if restart successful
        """
        self.logger.info("Restarting IB Gateway...")
        self.status.state = GatewayState.RESTARTING
        self.status.restart_count += 1
        
        # Stop existing instance
        self.stop()
        
        # Wait a bit
        time.sleep(5)
        
        # Start new instance
        return self.start()
        
    # ==========================================================================
    # PUBLIC METHODS - HEALTH CHECKS
    # ==========================================================================
    def is_healthy(self) -> bool:
        """
        Check if Gateway is healthy and responsive.
        
        Returns:
            bool: True if Gateway is healthy
        """
        if self.status.state != GatewayState.RUNNING:
            return False
            
        # Check process
        if not self._is_process_running():
            return False
            
        # Check port
        if not self._is_port_listening():
            return False
            
        # Update last health check
        self.status.last_health_check = datetime.now()
        return True
        
    def get_status(self) -> GatewayStatus:
        """
        Get current Gateway status.
        
        Returns:
            GatewayStatus object
        """
        # Update uptime if running
        if self.status.state == GatewayState.RUNNING and self.status.pid:
            try:
                process = psutil.Process(self.status.pid)
                create_time = datetime.fromtimestamp(process.create_time())
                self.status.uptime = datetime.now() - create_time
            except:
                pass
                
        return self.status
        
    # ==========================================================================
    # PRIVATE METHODS - CONFIGURATION
    # ==========================================================================
    def _generate_ibc_config(self) -> None:
        """Generate IBC configuration file."""
        config_content = f"""
# IBC Configuration File
# Generated by SPYDER Gateway Automation

IbLoginId={self.config.username}
IbPassword={self.config.password}
TradingMode={self.config.trading_mode.value}
IbDir={self.config.gateway_path}

# Gateway settings
OverrideTwsApiPort={self.config.gateway_port}
AcceptIncomingConnectionAction=accept
ShowAllTrades=no
ExistingSessionDetectedAction=primary
ReadOnlyLogin=no

# Automation settings
AcceptNonBrokerageAccountWarning=yes
AllowBlindTrading=yes
DismissPasswordExpiryWarning=yes
DismissNSEComplianceNotice=yes
SaveTwsSettingsAt=EveryConfirmation

# Window settings
MinimizeMainWindow=yes
ConfirmOrdersAPI=no
LogLevel=INFO

# Fix settings
FIX=no
"""
        
        # Ensure config directory exists
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Write config
        with open(CONFIG_PATH, 'w') as f:
            f.write(config_content)
            
        # Set permissions (read-only for owner)
        os.chmod(CONFIG_PATH, 0o600)
        
        self.logger.debug(f"Generated IBC config at {CONFIG_PATH}")
        
    def _build_gateway_command(self) -> str:
        """Build Gateway startup command."""
        java_opts = [
            f"-Xms{self.config.min_heap_size}",
            f"-Xmx{self.config.max_heap_size}",
            "-XX:+UseG1GC",
            "-XX:MaxGCPauseMillis=200",
            "-Dtwslaunch.autoupdate.serviceImpl=com.ib.tws.twslaunch.install4j.Install4jAutoUpdateService",
            "-Dinstall4j.versionLine=IB Gateway"
        ]
        
        java_opts_str = " ".join(java_opts)
        
        cmd = f"""
        java {java_opts_str} \\
            -cp "{self.config.ibc_path}:{self.config.gateway_path}/jars/*" \\
            ibcalpha.ibc.IbcGateway \\
            "{CONFIG_PATH}" \\
            --mode={self.config.trading_mode.value} \\
            --gateway \\
            --user={self.config.username} \\
            --pw={self.config.password} \\
            >> {LOG_DIR}/gateway.log 2>&1
        """
        
        return cmd.strip()
        
    # ==========================================================================
    # PRIVATE METHODS - PROCESS MANAGEMENT
    # ==========================================================================
    def _wait_for_gateway(self) -> bool:
        """Wait for Gateway to be ready."""
        start_time = time.time()
        
        while time.time() - start_time < GATEWAY_STARTUP_TIMEOUT:
            # Check if process is still running
            if self.gateway_process and self.gateway_process.poll() is not None:
                self.logger.error("Gateway process terminated unexpectedly")
                return False
                
            # Check if port is listening
            if self._is_port_listening():
                # Give it a bit more time to fully initialize
                time.sleep(5)
                return True
                
            time.sleep(2)
            
        return False
        
    def _is_process_running(self) -> bool:
        """Check if Gateway process is running."""
        if not self.status.pid:
            return False
            
        try:
            process = psutil.Process(self.status.pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False
            
    def _is_port_listening(self) -> bool:
        """Check if Gateway port is listening."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', self.config.gateway_port))
            sock.close()
            return result == 0
        except:
            return False
            
    def _save_pid(self) -> None:
        """Save process PID to file."""
        if self.status.pid:
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PID_FILE, 'w') as f:
                f.write(str(self.status.pid))
                
    def _remove_pid(self) -> None:
        """Remove PID file."""
        if PID_FILE.exists():
            PID_FILE.unlink()
            
    def _ensure_directories(self) -> None:
        """Ensure required directories exist."""
        for directory in [LOG_DIR, PID_FILE.parent, CONFIG_PATH.parent]:
            directory.mkdir(parents=True, exist_ok=True)
            
    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _start_monitoring(self) -> None:
        """Start Gateway monitoring thread."""
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="GatewayMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
    def _monitor_loop(self) -> None:
        """Gateway monitoring loop."""
        while self.running:
            try:
                # Health check
                if not self.is_healthy():
                    self.logger.error("Gateway health check failed")
                    
                    if self.config.auto_restart and self.status.restart_count < MAX_RESTART_ATTEMPTS:
                        self.logger.info("Attempting automatic restart...")
                        if self.restart():
                            self.logger.info("Gateway restarted successfully")
                        else:
                            self.logger.error("Gateway restart failed")
                            self.status.state = GatewayState.ERROR
                    else:
                        self.logger.error("Maximum restart attempts reached or auto-restart disabled")
                        self.status.state = GatewayState.ERROR
                        
                time.sleep(GATEWAY_HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                
    # ==========================================================================
    # PUBLIC METHODS - UTILITIES
    # ==========================================================================
    def get_logs(self, lines: int = 100) -> List[str]:
        """
        Get recent Gateway logs.
        
        Args:
            lines: Number of log lines to retrieve
            
        Returns:
            List of log lines
        """
        log_file = LOG_DIR / "gateway.log"
        
        if not log_file.exists():
            return []
            
        try:
            with open(log_file, 'r') as f:
                return f.readlines()[-lines:]
        except Exception as e:
            self.logger.error(f"Failed to read logs: {e}")
            return []
            
    def create_systemd_service(self) -> str:
        """
        Generate systemd service configuration.
        
        Returns:
            Service configuration content
        """
        service_content = f"""[Unit]
Description=SPYDER IB Gateway Service
After=network.target

[Service]
Type=forking
User={os.getenv('USER', 'trader')}
WorkingDirectory={Path.home()}
ExecStart=/usr/bin/python3 -m SpyderB_Broker.SpyderB12_GatewayAutomation start
ExecStop=/usr/bin/python3 -m SpyderB_Broker.SpyderB12_GatewayAutomation stop
PIDFile={PID_FILE}
Restart=always
RestartSec=30
StandardOutput=append:{LOG_DIR}/gateway.log
StandardError=append:{LOG_DIR}/gateway_error.log

[Install]
WantedBy=multi-user.target
"""
        return service_content
        
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up Gateway resources."""
        self.stop()
        self.logger.info("Gateway automation cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_default_config() -> GatewayConfig:
    """
    Create default Gateway configuration.
    
    Returns:
        GatewayConfig with default values
    """
    return GatewayConfig(
        username=os.getenv("IB_USERNAME", ""),
        password=os.getenv("IB_PASSWORD", ""),
        trading_mode=TradingMode.PAPER,
        gateway_port=DEFAULT_GATEWAY_PORT
    )

def load_config_from_file(config_path: Path) -> GatewayConfig:
    """
    Load Gateway configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        GatewayConfig object
    """
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
        
    return GatewayConfig(
        username=config_data['username'],
        password=config_data['password'],
        trading_mode=TradingMode(config_data.get('trading_mode', 'paper')),
        gateway_port=config_data.get('gateway_port', DEFAULT_GATEWAY_PORT),
        auto_restart=config_data.get('auto_restart', True)
    )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
pass

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code / CLI interface
    import argparse
    
    parser = argparse.ArgumentParser(description="SPYDER IB Gateway Automation")
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'status', 'install-service'],
                       help='Command to execute')
    parser.add_argument('--config', type=Path, help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Load configuration
    if args.config and args.config.exists():
        config = load_config_from_file(args.config)
    else:
        config = create_default_config()
        
    # Create automation instance
    gateway = GatewayAutomation(config)
    
    # Execute command
    if args.command == 'start':
        if gateway.start():
            print("✅ IB Gateway started successfully")
        else:
            print("❌ Failed to start IB Gateway")
            sys.exit(1)
            
    elif args.command == 'stop':
        gateway.stop()
        print("✅ IB Gateway stopped")
        
    elif args.command == 'restart':
        if gateway.restart():
            print("✅ IB Gateway restarted successfully")
        else:
            print("❌ Failed to restart IB Gateway")
            sys.exit(1)
            
    elif args.command == 'status':
        status = gateway.get_status()
        print(f"Gateway Status: {status.state.value}")
        print(f"Port: {status.port}")
        if status.pid:
            print(f"PID: {status.pid}")
        if status.uptime:
            print(f"Uptime: {status.uptime}")
        if status.last_health_check:
            print(f"Last Health Check: {status.last_health_check}")
            
    elif args.command == 'install-service':
        service_content = gateway.create_systemd_service()
        service_path = Path("/etc/systemd/system/spyder-gateway.service")
        
        print("Systemd service configuration:")
        print("-" * 60)
        print(service_content)
        print("-" * 60)
        print(f"\nTo install, run:")
        print(f"sudo tee {service_path} << EOF")
        print(service_content)
        print("EOF")
        print("sudo systemctl daemon-reload")
        print("sudo systemctl enable spyder-gateway")
        print("sudo systemctl start spyder-gateway")
        
    # Cleanup
    gateway.cleanup()