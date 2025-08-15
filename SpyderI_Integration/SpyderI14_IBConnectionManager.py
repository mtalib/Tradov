#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI14_IBConnectionManager.py
Group: I (Integration)
Purpose: High-level IB connection manager integrating IBAutomater with Spyder system
Author: Mohamed Talib
Date Created: 2025-08-15
Last Updated: 2025-08-15 Time: 15:15:00

Description:
    High-level connection manager that orchestrates IB Gateway connections using
    IBAutomater for process management. Provides unified interface for Spyder
    system with connection state management, health monitoring, reconnection logic,
    and integration with Spyder's event and configuration systems. Abstracts
    IBAutomater complexity while providing robust connection management.
"""

import logging
import threading
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from enum import Enum
import queue

# Import IBAutomater
try:
    from SpyderI12_IBAutomaterCore import IBAutomater, IBEvent as IBAutomaterEvent, TradingMode
    IBAUTOMATER_AVAILABLE = True
except ImportError:
    IBAUTOMATER_AVAILABLE = False

# Import IB API (optional)
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    IB_API_AVAILABLE = True
except ImportError:
    IB_API_AVAILABLE = False

# ================================================================================================
# CONNECTION STATE MANAGEMENT
# ================================================================================================

class ConnectionState(Enum):
    """Connection states for IB Gateway"""
    DISCONNECTED = "disconnected"
    STARTING = "starting"
    GATEWAY_READY = "gateway_ready"
    WAITING_LOGIN = "waiting_login"
    CONNECTING_API = "connecting_api"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPING = "stopping"

class ConnectionEvent(Enum):
    """Connection events for Spyder integration"""
    STATE_CHANGED = "connection_state_changed"
    CONNECTION_READY = "connection_ready"
    CONNECTION_LOST = "connection_lost"
    RECONNECTION_STARTED = "reconnection_started"
    RECONNECTION_FAILED = "reconnection_failed"
    GATEWAY_RESTARTED = "gateway_restarted"
    ERROR_OCCURRED = "error_occurred"
    HEALTH_CHECK_FAILED = "health_check_failed"

@dataclass
class ConnectionConfig:
    """Configuration for IB connection management"""
    # IBAutomater settings
    ib_directory: str
    ib_version: str
    trading_mode: str
    port: int
    
    # Connection settings
    client_id: int = 1
    connection_timeout: float = 60.0
    reconnect_attempts: int = 5
    reconnect_delay: float = 10.0
    health_check_interval: float = 30.0
    
    # Monitoring settings
    enable_health_monitoring: bool = True
    log_level: str = "INFO"
    save_state: bool = True
    state_file: str = "ib_connection_state.json"

@dataclass
class ConnectionStatus:
    """Current connection status information"""
    state: ConnectionState
    gateway_running: bool
    api_connected: bool
    client_id: int
    port: int
    trading_mode: str
    last_heartbeat: Optional[datetime] = None
    uptime_seconds: Optional[float] = None
    reconnect_count: int = 0
    error_message: Optional[str] = None
    process_id: Optional[int] = None
    memory_mb: Optional[float] = None
    cpu_percent: Optional[float] = None

# ================================================================================================
# EVENT INTEGRATION SYSTEM
# ================================================================================================

class SpyderEventEmitter:
    """Event emitter for Spyder system integration"""
    
    def __init__(self):
        self._handlers: Dict[ConnectionEvent, List[Callable]] = {}
        self.logger = logging.getLogger(f"{__name__}.SpyderEventEmitter")
    
    def on(self, event: ConnectionEvent, handler: Callable):
        """Register event handler"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        self.logger.debug(f"Registered handler for {event.value}")
    
    def emit(self, event: ConnectionEvent, data: Any = None):
        """Emit event to all handlers"""
        if event in self._handlers:
            event_data = {
                "event": event.value,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            for handler in self._handlers[event]:
                try:
                    handler(event_data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event.value}: {e}")
    
    def clear(self, event: Optional[ConnectionEvent] = None):
        """Clear event handlers"""
        if event is None:
            self._handlers.clear()
        elif event in self._handlers:
            self._handlers[event].clear()

# ================================================================================================
# HEALTH MONITORING SYSTEM
# ================================================================================================

class HealthMonitor:
    """Monitor IB connection health"""
    
    def __init__(self, connection_manager: 'IBConnectionManager'):
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(f"{__name__}.HealthMonitor")
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        self.last_check_time: Optional[datetime] = None
        self.health_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
    
    def start_monitoring(self):
        """Start health monitoring"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.stop_monitoring.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        self.logger.info("Health monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while not self.stop_monitoring.is_set():
            try:
                self._perform_health_check()
                time.sleep(self.connection_manager.config.health_check_interval)
            except Exception as e:
                self.logger.error(f"Error in health monitoring: {e}")
                time.sleep(5)  # Short delay on error
    
    def _perform_health_check(self):
        """Perform comprehensive health check"""
        check_time = datetime.now()
        health_data = {
            "timestamp": check_time.isoformat(),
            "gateway_running": False,
            "api_connected": False,
            "process_health": {},
            "connection_quality": "unknown",
            "issues": []
        }
        
        try:
            # Check gateway process
            if self.connection_manager.ibautomater and self.connection_manager.ibautomater.is_running():
                health_data["gateway_running"] = True
                
                # Get process metrics
                health_data["process_health"] = {
                    "pid": self.connection_manager.ibautomater.get_status().get("process_id"),
                    "memory_mb": self.connection_manager.ibautomater.get_status().get("memory_mb"),
                    "cpu_percent": self.connection_manager.ibautomater.get_status().get("cpu_percent")
                }
            else:
                health_data["issues"].append("Gateway process not running")
            
            # Check API connection
            if self.connection_manager.ibautomater and self.connection_manager.ibautomater.is_connected():
                health_data["api_connected"] = True
                health_data["connection_quality"] = "good"
            else:
                health_data["issues"].append("API connection not responding")
                health_data["connection_quality"] = "poor"
            
            # Check for stale connections
            if self.last_check_time:
                time_since_last = (check_time - self.last_check_time).total_seconds()
                if time_since_last > self.connection_manager.config.health_check_interval * 2:
                    health_data["issues"].append(f"Health check delayed by {time_since_last:.1f}s")
            
            # Store health data
            self.health_history.append(health_data)
            if len(self.health_history) > self.max_history_size:
                self.health_history.pop(0)
            
            # Emit health events
            if health_data["issues"]:
                self.connection_manager.event_emitter.emit(
                    ConnectionEvent.HEALTH_CHECK_FAILED,
                    health_data
                )
            
            self.last_check_time = check_time
            
        except Exception as e:
            health_data["issues"].append(f"Health check error: {e}")
            self.logger.error(f"Health check failed: {e}")
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary"""
        if not self.health_history:
            return {"status": "no_data", "message": "No health data available"}
        
        recent = self.health_history[-5:]  # Last 5 checks
        issues_count = sum(len(check.get("issues", [])) for check in recent)
        
        if issues_count == 0:
            status = "healthy"
        elif issues_count <= 2:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "issues_count": issues_count,
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
            "recent_issues": recent[-1].get("issues", []) if recent else []
        }

# ================================================================================================
# MAIN CONNECTION MANAGER
# ================================================================================================

class IBConnectionManager:
    """
    High-level IB connection manager for Spyder system
    
    Features:
    - IBAutomater integration for process management
    - Connection state management and monitoring
    - Automatic reconnection handling
    - Health monitoring and diagnostics
    - Event-driven integration with Spyder
    - Configuration management
    - State persistence
    """
    
    def __init__(self, config: ConnectionConfig):
        """
        Initialize connection manager
        
        Args:
            config: Connection configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.IBConnectionManager")
        
        # Validate dependencies
        if not IBAUTOMATER_AVAILABLE:
            raise RuntimeError("IBAutomater not available - check SpyderI12_IBAutomaterCore.py")
        
        # Initialize components
        self.event_emitter = SpyderEventEmitter()
        self.ibautomater: Optional[IBAutomater] = None
        self.health_monitor = HealthMonitor(self)
        
        # State management
        self._state = ConnectionState.DISCONNECTED
        self._state_lock = threading.Lock()
        self._connection_start_time: Optional[datetime] = None
        self._reconnect_count = 0
        self._last_error: Optional[str] = None
        
        # Threading
        self._connection_thread: Optional[threading.Thread] = None
        self._stop_requested = threading.Event()
        
        # State persistence
        self.state_file = Path(config.state_file)
        
        self.logger.info(f"IBConnectionManager initialized for {config.trading_mode} on port {config.port}")
    
    # ==============================================================================================
    # PUBLIC INTERFACE
    # ==============================================================================================
    
    def connect(self) -> bool:
        """
        Initiate connection to IB Gateway
        
        Returns:
            True if connection initiated successfully, False otherwise
        """
        with self._state_lock:
            if self._state not in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
                self.logger.warning(f"Cannot connect from state: {self._state.value}")
                return False
            
            self._set_state(ConnectionState.STARTING)
        
        try:
            # Create IBAutomater instance
            self.ibautomater = IBAutomater(
                ib_directory=self.config.ib_directory,
                ib_version=self.config.ib_version,
                trading_mode=self.config.trading_mode,
                port=self.config.port
            )
            
            # Setup IBAutomater event handlers
            self._setup_ibautomater_events()
            
            # Start connection in background thread
            self._stop_requested.clear()
            self._connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
            self._connection_thread.start()
            
            self.logger.info("Connection process initiated")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initiate connection: {e}")
            self._set_state(ConnectionState.ERROR, str(e))
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from IB Gateway
        
        Returns:
            True if disconnection successful, False otherwise
        """
        try:
            self.logger.info("Initiating disconnect...")
            self._set_state(ConnectionState.STOPPING)
            
            # Stop connection thread
            self._stop_requested.set()
            if self._connection_thread and self._connection_thread.is_alive():
                self._connection_thread.join(timeout=10)
            
            # Stop health monitoring
            self.health_monitor.stop_monitoring()
            
            # Stop IBAutomater
            if self.ibautomater:
                success = self.ibautomater.stop()
                self.ibautomater = None
                
                if success:
                    self.logger.info("Disconnected successfully")
                else:
                    self.logger.warning("IBAutomater stop returned False")
            
            self._set_state(ConnectionState.DISCONNECTED)
            self._save_state()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            self._set_state(ConnectionState.ERROR, str(e))
            return False
    
    def reconnect(self) -> bool:
        """
        Reconnect to IB Gateway
        
        Returns:
            True if reconnection initiated, False otherwise
        """
        self.logger.info("Initiating reconnection...")
        self.event_emitter.emit(ConnectionEvent.RECONNECTION_STARTED)
        
        # Disconnect first
        if not self.disconnect():
            self.logger.error("Failed to disconnect for reconnection")
            return False
        
        # Wait a moment
        time.sleep(self.config.reconnect_delay)
        
        # Reconnect
        self._reconnect_count += 1
        return self.connect()
    
    def get_status(self) -> ConnectionStatus:
        """
        Get current connection status
        
        Returns:
            Current connection status
        """
        status = ConnectionStatus(
            state=self._state,
            gateway_running=False,
            api_connected=False,
            client_id=self.config.client_id,
            port=self.config.port,
            trading_mode=self.config.trading_mode,
            reconnect_count=self._reconnect_count,
            error_message=self._last_error
        )
        
        # Add IBAutomater status if available
        if self.ibautomater:
            ib_status = self.ibautomater.get_status()
            status.gateway_running = ib_status.get("running", False)
            status.api_connected = ib_status.get("connected", False)
            status.process_id = ib_status.get("process_id")
            status.memory_mb = ib_status.get("memory_mb")
            status.cpu_percent = ib_status.get("cpu_percent")
        
        # Add uptime if connected
        if self._connection_start_time:
            uptime = datetime.now() - self._connection_start_time
            status.uptime_seconds = uptime.total_seconds()
        
        return status
    
    def is_connected(self) -> bool:
        """Check if fully connected to IB Gateway"""
        return self._state == ConnectionState.CONNECTED
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health monitoring summary"""
        return self.health_monitor.get_health_summary()
    
    def get_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive diagnostics information"""
        status = self.get_status()
        health = self.get_health_summary()
        
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "connection_status": asdict(status),
            "health_summary": health,
            "configuration": {
                "ib_directory": self.config.ib_directory,
                "ib_version": self.config.ib_version,
                "trading_mode": self.config.trading_mode,
                "port": self.config.port,
                "client_id": self.config.client_id
            },
            "runtime_info": {
                "ibautomater_available": IBAUTOMATER_AVAILABLE,
                "ib_api_available": IB_API_AVAILABLE,
                "health_monitoring": self.config.enable_health_monitoring
            }
        }
        
        return diagnostics
    
    # ==============================================================================================
    # EVENT HANDLERS
    # ==============================================================================================
    
    def on_state_changed(self, handler: Callable):
        """Register handler for state change events"""
        self.event_emitter.on(ConnectionEvent.STATE_CHANGED, handler)
    
    def on_connection_ready(self, handler: Callable):
        """Register handler for connection ready events"""
        self.event_emitter.on(ConnectionEvent.CONNECTION_READY, handler)
    
    def on_connection_lost(self, handler: Callable):
        """Register handler for connection lost events"""
        self.event_emitter.on(ConnectionEvent.CONNECTION_LOST, handler)
    
    def on_error(self, handler: Callable):
        """Register handler for error events"""
        self.event_emitter.on(ConnectionEvent.ERROR_OCCURRED, handler)
    
    # ==============================================================================================
    # PRIVATE METHODS
    # ==============================================================================================
    
    def _set_state(self, new_state: ConnectionState, error_message: Optional[str] = None):
        """Set connection state and emit events"""
        old_state = self._state
        self._state = new_state
        
        if error_message:
            self._last_error = error_message
        
        self.logger.info(f"State changed: {old_state.value} → {new_state.value}")
        
        # Emit state change event
        self.event_emitter.emit(ConnectionEvent.STATE_CHANGED, {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "error_message": error_message
        })
        
        # Emit specific events
        if new_state == ConnectionState.CONNECTED:
            self._connection_start_time = datetime.now()
            self.event_emitter.emit(ConnectionEvent.CONNECTION_READY, self.get_status())
        elif old_state == ConnectionState.CONNECTED and new_state != ConnectionState.STOPPING:
            self.event_emitter.emit(ConnectionEvent.CONNECTION_LOST, {"reason": error_message})
        
        # Save state
        self._save_state()
    
    def _setup_ibautomater_events(self):
        """Setup event handlers for IBAutomater"""
        if not self.ibautomater:
            return
        
        self.ibautomater.on_process_started(self._on_gateway_started)
        self.ibautomater.on_connection_ready(self._on_api_ready)
        self.ibautomater.on_gateway_exited(self._on_gateway_exited)
        self.ibautomater.on_restart_detected(self._on_gateway_restarted)
    
    def _on_gateway_started(self, event_data):
        """Handle gateway started event"""
        self.logger.info(f"Gateway started: PID {event_data['data']}")
        self._set_state(ConnectionState.GATEWAY_READY)
    
    def _on_api_ready(self, event_data):
        """Handle API ready event"""
        self.logger.info("API connection ready")
        self._set_state(ConnectionState.CONNECTED)
    
    def _on_gateway_exited(self, event_data):
        """Handle gateway exit event"""
        self.logger.warning(f"Gateway exited unexpectedly: {event_data['data']}")
        if self._state == ConnectionState.CONNECTED:
            self._set_state(ConnectionState.ERROR, "Gateway process exited")
            self._attempt_reconnection()
    
    def _on_gateway_restarted(self, event_data):
        """Handle gateway restart event"""
        self.logger.info("Gateway restart detected")
        self.event_emitter.emit(ConnectionEvent.GATEWAY_RESTARTED, event_data)
        self._set_state(ConnectionState.RECONNECTING)
    
    def _connection_loop(self):
        """Main connection loop"""
        try:
            # Start IBAutomater
            self.logger.info("Starting IBAutomater...")
            result = self.ibautomater.start(wait_for_manual_login=True)
            
            if not result.success:
                raise Exception(f"IBAutomater start failed: {result.error_message}")
            
            self.logger.info("IBAutomater started, waiting for manual login...")
            self._set_state(ConnectionState.WAITING_LOGIN)
            
            # Wait for API connection
            if self.ibautomater.wait_for_connection(self.config.connection_timeout):
                self._set_state(ConnectionState.CONNECTED)
                
                # Start health monitoring
                if self.config.enable_health_monitoring:
                    self.health_monitor.start_monitoring()
                
                self.logger.info("✅ Connection established successfully")
            else:
                raise Exception("API connection timeout")
            
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self._set_state(ConnectionState.ERROR, str(e))
            self._attempt_reconnection()
    
    def _attempt_reconnection(self):
        """Attempt automatic reconnection"""
        if self._reconnect_count >= self.config.reconnect_attempts:
            self.logger.error("Maximum reconnection attempts reached")
            self.event_emitter.emit(ConnectionEvent.RECONNECTION_FAILED, {
                "attempts": self._reconnect_count,
                "max_attempts": self.config.reconnect_attempts
            })
            return
        
        self.logger.info(f"Attempting reconnection ({self._reconnect_count + 1}/{self.config.reconnect_attempts})")
        
        # Schedule reconnection
        threading.Timer(self.config.reconnect_delay, self.reconnect).start()
    
    def _save_state(self):
        """Save connection state to file"""
        if not self.config.save_state:
            return
        
        try:
            state_data = {
                "timestamp": datetime.now().isoformat(),
                "state": self._state.value,
                "reconnect_count": self._reconnect_count,
                "last_error": self._last_error,
                "config": {
                    "trading_mode": self.config.trading_mode,
                    "port": self.config.port,
                    "client_id": self.config.client_id
                }
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def _load_state(self) -> Optional[Dict[str, Any]]:
        """Load connection state from file"""
        if not self.config.save_state or not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return None

# ================================================================================================
# CONVENIENCE FUNCTIONS
# ================================================================================================

def create_connection_manager(
    ib_directory: str,
    ib_version: str = "10.39",
    trading_mode: str = "paper",
    port: int = 4002,
    client_id: int = 1
) -> IBConnectionManager:
    """
    Create connection manager with common settings
    
    Args:
        ib_directory: Path to IB Gateway installation
        ib_version: IB Gateway version
        trading_mode: Trading mode ("paper" or "live")
        port: API port number
        client_id: IB API client ID
        
    Returns:
        Configured connection manager
    """
    config = ConnectionConfig(
        ib_directory=ib_directory,
        ib_version=ib_version,
        trading_mode=trading_mode,
        port=port,
        client_id=client_id
    )
    
    return IBConnectionManager(config)

def get_default_config() -> ConnectionConfig:
    """Get default connection configuration"""
    return ConnectionConfig(
        ib_directory="/opt/ibc",
        ib_version="10.39",
        trading_mode="paper",
        port=4002,
        client_id=1,
        connection_timeout=60.0,
        reconnect_attempts=5,
        reconnect_delay=10.0,
        health_check_interval=30.0,
        enable_health_monitoring=True
    )

# ================================================================================================
# MAIN EXECUTION
# ================================================================================================

if __name__ == "__main__":
    # Example usage and testing
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('spyder_connection_manager.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🎯 Testing Spyder IBConnectionManager...")
        
        # Create connection manager
        config = get_default_config()
        config.ib_directory = "/opt/ibc"  # Adjust for your system
        
        connection_manager = IBConnectionManager(config)
        
        # Setup event handlers
        connection_manager.on_state_changed(
            lambda e: logger.info(f"🔄 State: {e['data']['old_state']} → {e['data']['new_state']}")
        )
        connection_manager.on_connection_ready(
            lambda e: logger.info("🎉 Connection ready!")
        )
        connection_manager.on_connection_lost(
            lambda e: logger.warning(f"⚠️ Connection lost: {e['data']}")
        )
        connection_manager.on_error(
            lambda e: logger.error(f"❌ Error: {e['data']}")
        )
        
        # Test connection
        logger.info("Testing connection initialization...")
        if connection_manager.connect():
            logger.info("✅ Connection initiated successfully")
            
            # Show status
            status = connection_manager.get_status()
            logger.info(f"📊 Status: {status.state.value}")
            
            # Wait a bit for testing
            time.sleep(5)
            
            # Disconnect
            connection_manager.disconnect()
        else:
            logger.error("❌ Failed to initiate connection")
        
        logger.info("✅ IBConnectionManager test completed")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)
