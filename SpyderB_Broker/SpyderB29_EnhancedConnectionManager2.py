#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB29_EnhancedConnectionManager.py
Purpose: Enhanced IB Connection Manager with proper ib.sleep() usage
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-24 Time: 15:00:00

Module Description:
    Enhanced connection manager that uses ib.sleep() for non-blocking operations
    instead of blocking delays or timers. This ensures proper event loop management
    and prevents API timeouts, missed messages, and connection issues. Implements
    exponential backoff reconnection with event loop-friendly delays.
"""

import asyncio
import socket
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import traceback

try:
    from ib_async import IB, util
    IB_ASYNC_AVAILABLE = True
    print("✅ ib_async available for enhanced connection management")
except ImportError:
    IB_ASYNC_AVAILABLE = False
    print("⚠️ ib_async not available - using fallback connection management")

from PySide6.QtCore import QObject, Signal, QTimer, QThread
from PySide6.QtWidgets import QApplication


# ==============================================================================
# CONNECTION MANAGER CONFIGURATION
# ==============================================================================
@dataclass
class ConnectionConfig:
    """Configuration for IB connection management"""
    paper_port: int = 4002
    live_port: int = 4001
    host: str = "127.0.0.1"
    client_id: int = 2
    timeout_seconds: int = 10
    max_reconnect_attempts: int = 5
    reconnect_delays: list = None  # Will default to [5, 10, 20, 40, 60]
    heartbeat_interval: float = 30.0  # seconds
    connection_check_delay: float = 0.1  # Non-blocking delay between checks
    
    def __post_init__(self):
        if self.reconnect_delays is None:
            self.reconnect_delays = [5, 10, 20, 40, 60]


class ConnectionState(Enum):
    """Connection states for the manager"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    MARKET_CLOSED = "MARKET_CLOSED"


@dataclass
class ConnectionStatus:
    """Current connection status information"""
    state: ConnectionState = ConnectionState.DISCONNECTED
    port: Optional[int] = None
    mode: str = "UNKNOWN"
    last_connected: Optional[datetime] = None
    last_error: Optional[str] = None
    reconnect_attempts: int = 0
    next_reconnect_delay: float = 0
    is_market_hours: bool = False


# ==============================================================================
# ENHANCED CONNECTION MANAGER WITH IB.SLEEP()
# ==============================================================================
class EnhancedIBConnectionManager(QObject):
    """
    Enhanced IB connection manager using ib.sleep() for non-blocking operations.
    
    This manager provides:
    - Non-blocking connection attempts with ib.sleep()
    - Exponential backoff reconnection with event loop preservation
    - Proper async/await patterns for IB API compatibility
    - Event loop-friendly heartbeat monitoring
    - Automatic market hours detection and management
    """
    
    # Qt Signals for UI integration
    connection_changed = Signal(bool, str)  # connected, status_message
    status_changed = Signal(ConnectionState)  # state
    heartbeat = Signal(str)  # heartbeat_message
    error_occurred = Signal(str)  # error_message
    log_message = Signal(str)  # log_message
    
    def __init__(self, config: Optional[ConnectionConfig] = None, logger=None):
        super().__init__()
        
        self.config = config or ConnectionConfig()
        self.logger = logger
        self.status = ConnectionStatus()
        
        # IB connection instance
        self.ib: Optional[IB] = None
        self.is_running = False
        self.reconnect_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Event loop management
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Callbacks for status changes
        self.status_callbacks: list = []
        
        self._log("Enhanced IB Connection Manager initialized with ib.sleep() support")
    
    def _log(self, message: str):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        
        if self.logger:
            self.logger.info(message)
        else:
            print(formatted_msg)
        
        self.log_message.emit(formatted_msg)
    
    def add_status_callback(self, callback: Callable[[ConnectionStatus], None]):
        """Add callback for status changes"""
        self.status_callbacks.append(callback)
    
    def _notify_status_change(self):
        """Notify all callbacks of status change"""
        for callback in self.status_callbacks:
            try:
                callback(self.status)
            except Exception as e:
                self._log(f"Error in status callback: {e}")
    
    # ==========================================================================
    # ASYNC CONNECTION METHODS WITH IB.SLEEP()
    # ==========================================================================
    async def start_async(self) -> bool:
        """
        Start the async connection manager.
        
        Returns:
            bool: True if started successfully
        """
        if self.is_running:
            self._log("Connection manager already running")
            return True
        
        try:
            if not IB_ASYNC_AVAILABLE:
                self._log("❌ ib_async not available - cannot start enhanced manager")
                return False
            
            self.is_running = True
            self.ib = IB()
            
            # Start initial connection attempt
            await self._attempt_connection()
            
            # Start heartbeat monitoring
            self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
            
            self._log("✅ Enhanced connection manager started with ib.sleep() support")
            return True
            
        except Exception as e:
            self._log(f"❌ Error starting connection manager: {e}")
            self.is_running = False
            return False
    
    async def stop_async(self):
        """Stop the async connection manager"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel running tasks
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
        
        # Disconnect IB
        if self.ib and self.ib.isConnected():
            await self._disconnect_with_delay()
        
        self._log("🛑 Enhanced connection manager stopped")
    
    async def _attempt_connection(self) -> bool:
        """
        Attempt to connect to IB Gateway using ib.sleep() for delays.
        
        Returns:
            bool: True if connection successful
        """
        if not self.ib:
            return False
        
        # Update status
        old_state = self.status.state
        self.status.state = ConnectionState.CONNECTING
        self._notify_status_change()
        
        if old_state != ConnectionState.CONNECTING:
            self._log("🔄 Attempting connection to IB Gateway...")
        
        # Check market hours first
        self.status.is_market_hours = self._is_market_hours()
        
        try:
            # Try paper trading port first
            if await self._try_connect_port(self.config.paper_port, "PAPER"):
                return True
            
            # Use ib.sleep() for non-blocking delay between attempts
            await self.ib.sleep(self.config.connection_check_delay)
            
            # Try live trading port
            if await self._try_connect_port(self.config.live_port, "LIVE"):
                return True
            
            # Connection failed
            await self._handle_connection_failure()
            return False
            
        except Exception as e:
            await self._handle_connection_error(e)
            return False
    
    async def _try_connect_port(self, port: int, mode: str) -> bool:
        """
        Try connecting to specific port with ib.sleep() delays.
        
        Args:
            port: Port number to connect to
            mode: Connection mode ("PAPER" or "LIVE")
            
        Returns:
            bool: True if connection successful
        """
        try:
            # Use ib.sleep() instead of blocking socket check
            await self.ib.sleep(0.05)  # Small delay to prevent overwhelming
            
            # Attempt connection with timeout
            await asyncio.wait_for(
                self.ib.connectAsync(
                    host=self.config.host,
                    port=port,
                    clientId=self.config.client_id
                ),
                timeout=self.config.timeout_seconds
            )
            
            if self.ib.isConnected():
                await self._handle_successful_connection(port, mode)
                return True
                
        except asyncio.TimeoutError:
            # Use ib.sleep() for timeout handling
            await self.ib.sleep(0.01)
            
        except Exception as e:
            # Use ib.sleep() for error handling delay
            await self.ib.sleep(0.01)
        
        return False
    
    async def _handle_successful_connection(self, port: int, mode: str):
        """Handle successful connection with ib.sleep() delay"""
        # Small delay to ensure connection is stable
        await self.ib.sleep(0.1)
        
        # Update status
        self.status.state = ConnectionState.CONNECTED
        self.status.port = port
        self.status.mode = mode
        self.status.last_connected = datetime.now()
        self.status.last_error = None
        self.status.reconnect_attempts = 0
        
        # Emit signals
        self.connection_changed.emit(True, f"IB CONNECTED ({mode})")
        self.status_changed.emit(ConnectionState.CONNECTED)
        
        self._log(f"✅ Connected to IB Gateway on port {port} ({mode})")
        self._notify_status_change()
        
        # Cancel any running reconnection task
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
    
    async def _handle_connection_failure(self):
        """Handle connection failure with market hours consideration"""
        if not self.status.is_market_hours:
            self.status.state = ConnectionState.MARKET_CLOSED
            self.status_changed.emit(ConnectionState.MARKET_CLOSED)
            # Don't start reconnection outside market hours
            return
        
        self.status.state = ConnectionState.DISCONNECTED
        self.status_changed.emit(ConnectionState.DISCONNECTED)
        self.connection_changed.emit(False, "IB DISCONNECTED")
        
        # Start reconnection during market hours
        if not self.reconnect_task or self.reconnect_task.done():
            self.reconnect_task = asyncio.create_task(self._reconnection_loop())
    
    async def _handle_connection_error(self, error: Exception):
        """Handle connection error with ib.sleep() delay"""
        # Use ib.sleep() for error handling delay
        await self.ib.sleep(0.1)
        
        error_msg = str(error)
        self.status.state = ConnectionState.ERROR
        self.status.last_error = error_msg
        
        self.error_occurred.emit(f"Connection error: {error_msg}")
        self.status_changed.emit(ConnectionState.ERROR)
        
        self._log(f"❌ Connection error: {error_msg}")
        self._notify_status_change()
    
    # ==========================================================================
    # EXPONENTIAL BACKOFF RECONNECTION WITH IB.SLEEP()
    # ==========================================================================
    async def _reconnection_loop(self):
        """
        Exponential backoff reconnection loop using ib.sleep().
        
        This prevents blocking the event loop during reconnection delays
        and ensures proper IB API event processing continues.
        """
        self._log("🔄 Starting auto-reconnection sequence...")
        self.status.state = ConnectionState.RECONNECTING
        self.status_changed.emit(ConnectionState.RECONNECTING)
        
        for attempt in range(self.config.max_reconnect_attempts):
            if not self.is_running:
                break
            
            # Check if already connected (manual connection)
            if self.ib and self.ib.isConnected():
                self._log("✅ Already connected - stopping reconnection")
                break
            
            # Check market hours
            if not self._is_market_hours():
                self._log("📊 Market closed - stopping reconnection")
                self.status.state = ConnectionState.MARKET_CLOSED
                self.status_changed.emit(ConnectionState.MARKET_CLOSED)
                break
            
            # Calculate delay using exponential backoff
            delay_index = min(attempt, len(self.config.reconnect_delays) - 1)
            delay = self.config.reconnect_delays[delay_index]
            
            self.status.reconnect_attempts = attempt + 1
            self.status.next_reconnect_delay = delay
            
            self._log(f"🔄 Reconnection attempt #{attempt + 1} in {delay}s")
            self._notify_status_change()
            
            # Use ib.sleep() for non-blocking delay - CRITICAL FOR EVENT LOOP
            await self.ib.sleep(delay) if self.ib else await asyncio.sleep(delay)
            
            # Check if stopped during delay
            if not self.is_running:
                break
            
            # Attempt reconnection
            if await self._attempt_connection():
                self._log("✅ Reconnection successful!")
                return
            
            self._log(f"⚠️ Reconnection attempt #{attempt + 1} failed")
        
        # Max attempts reached
        if self.is_running:
            self._log("❌ Max reconnection attempts reached - stopping auto-reconnect")
            self.status.state = ConnectionState.DISCONNECTED
            self.status_changed.emit(ConnectionState.DISCONNECTED)
            self._notify_status_change()
    
    # ==========================================================================
    # HEARTBEAT MONITORING WITH IB.SLEEP()
    # ==========================================================================
    async def _heartbeat_monitor(self):
        """
        Heartbeat monitoring loop using ib.sleep() for non-blocking delays.
        
        This monitors connection health without blocking the event loop
        and only logs status changes to prevent log clutter.
        """
        last_connection_state = None
        
        while self.is_running:
            try:
                # Use ib.sleep() for heartbeat interval - NON-BLOCKING
                await self.ib.sleep(self.config.heartbeat_interval) if self.ib else await asyncio.sleep(self.config.heartbeat_interval)
                
                if not self.is_running:
                    break
                
                # Check current connection status
                current_connected = self.ib and self.ib.isConnected()
                
                # Only log and emit signals on status CHANGES
                if current_connected != last_connection_state:
                    if current_connected:
                        # Connection established/restored
                        mode = self.status.mode or "UNKNOWN"
                        port = self.status.port or "UNKNOWN"
                        
                        if last_connection_state is False:
                            # Connection restored
                            self.heartbeat.emit(f"💚 Heartbeat: IB Gateway connection restored ({mode})")
                        # Don't log repetitive "healthy" messages
                        
                    else:
                        # Connection lost
                        if last_connection_state is True:
                            # Connection just lost
                            self.heartbeat.emit("💔 Heartbeat: IB Gateway connection lost")
                            
                            # Trigger reconnection if market is open
                            if self._is_market_hours() and not self.reconnect_task:
                                self.reconnect_task = asyncio.create_task(self._reconnection_loop())
                        # Don't log repetitive "still disconnected" messages
                
                last_connection_state = current_connected
                
                # Update market hours status
                self.status.is_market_hours = self._is_market_hours()
                
            except Exception as e:
                # Only log heartbeat errors (should be rare)
                self.heartbeat.emit(f"💔 Heartbeat error: {e}")
                # Use ib.sleep() for error recovery delay
                await self.ib.sleep(1.0) if self.ib else await asyncio.sleep(1.0)
    
    # ==========================================================================
    # MANUAL CONNECTION METHODS
    # ==========================================================================
    async def connect_manual(self) -> bool:
        """
        Manual connection request using ib.sleep().
        
        Returns:
            bool: True if connection successful
        """
        if not self._is_market_hours():
            self._log("📊 Cannot connect - market is closed")
            return False
        
        # Cancel any running reconnection
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        
        return await self._attempt_connection()
    
    async def disconnect_manual(self):
        """Manual disconnection request using ib.sleep()"""
        # Cancel reconnection
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
        
        await self._disconnect_with_delay()
    
    async def _disconnect_with_delay(self):
        """Disconnect with ib.sleep() delay for clean shutdown"""
        if self.ib and self.ib.isConnected():
            # Use small delay before disconnect for clean shutdown
            await self.ib.sleep(0.1)
            
            self.ib.disconnect()
            
            # Small delay after disconnect
            await self.ib.sleep(0.1)
            
            self.status.state = ConnectionState.DISCONNECTED
            self.status.port = None
            self.status.mode = "UNKNOWN"
            
            self.connection_changed.emit(False, "IB DISCONNECTED")
            self.status_changed.emit(ConnectionState.DISCONNECTED)
            
            self._log("🔌 Manually disconnected from IB Gateway")
            self._notify_status_change()
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _is_market_hours(self) -> bool:
        """Check if market is currently open"""
        import pytz
        from datetime import time as dt_time
        
        eastern = pytz.timezone("US/Eastern")
        now_et = datetime.now(eastern).time()
        market_open = dt_time(4, 0)  # 4:00 AM ET
        market_close = dt_time(16, 30)  # 4:30 PM ET
        
        return market_open <= now_et <= market_close
    
    def get_status(self) -> ConnectionStatus:
        """Get current connection status"""
        return self.status
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.ib and self.ib.isConnected()
    
    def get_ib_instance(self) -> Optional[IB]:
        """Get the IB instance for advanced operations"""
        return self.ib


# ==============================================================================
# QT INTEGRATION WRAPPER
# ==============================================================================
class QtIBConnectionManager(QObject):
    """
    Qt wrapper for the enhanced IB connection manager.
    
    This provides Qt signal integration while running the async manager
    in a separate thread to prevent blocking the GUI.
    """
    
    # Qt Signals matching the original dashboard expectations
    connection_status_changed = Signal(bool, str)
    heartbeat_status_changed = Signal(str)
    heartbeat_received = Signal(str)
    log_message = Signal(str)
    
    def __init__(self, config: Optional[ConnectionConfig] = None, logger=None):
        super().__init__()
        
        self.config = config or ConnectionConfig()
        self.logger = logger
        self.manager = EnhancedIBConnectionManager(config, logger)
        
        # Connect manager signals to Qt signals
        self.manager.connection_changed.connect(self.connection_status_changed)
        self.manager.heartbeat.connect(self.heartbeat_received)
        self.manager.log_message.connect(self.log_message)
        self.manager.status_changed.connect(self._handle_status_change)
        
        # Event loop for async operations
        self.loop = None
        self.loop_thread = None
        
        print("✅ Qt IB Connection Manager initialized with ib.sleep() support")
    
    def _handle_status_change(self, state: ConnectionState):
        """Convert connection state to heartbeat status for dashboard compatibility"""
        if state == ConnectionState.CONNECTED:
            self.heartbeat_status_changed.emit("connected")
        elif state in [ConnectionState.DISCONNECTED, ConnectionState.ERROR]:
            self.heartbeat_status_changed.emit("disconnected")
        elif state in [ConnectionState.CONNECTING, ConnectionState.RECONNECTING]:
            self.heartbeat_status_changed.emit("warning")
    
    def start(self):
        """Start the connection manager in a separate thread"""
        if self.loop_thread and self.loop_thread.is_alive():
            return
        
        def run_async_manager():
            """Run the async manager in its own event loop"""
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            try:
                self.loop.run_until_complete(self.manager.start_async())
                self.loop.run_forever()
            except Exception as e:
                print(f"Error in async manager: {e}")
            finally:
                self.loop.close()
        
        import threading
        self.loop_thread = threading.Thread(target=run_async_manager, daemon=True)
        self.loop_thread.start()
    
    def stop(self):
        """Stop the connection manager"""
        if self.loop and not self.loop.is_closed():
            # Schedule stop in the async loop
            future = asyncio.run_coroutine_threadsafe(self.manager.stop_async(), self.loop)
            future.result(timeout=5.0)
            
            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
    
    def force_connect(self) -> bool:
        """Force manual connection attempt"""
        if not self.loop or self.loop.is_closed():
            return False
        
        try:
            future = asyncio.run_coroutine_threadsafe(self.manager.connect_manual(), self.loop)
            return future.result(timeout=10.0)
        except Exception as e:
            print(f"Error in force connect: {e}")
            return False
    
    def force_disconnect(self):
        """Force manual disconnection"""
        if not self.loop or self.loop.is_closed():
            return
        
        try:
            future = asyncio.run_coroutine_threadsafe(self.manager.disconnect_manual(), self.loop)
            future.result(timeout=5.0)
        except Exception as e:
            print(f"Error in force disconnect: {e}")
    
    def is_connected(self) -> bool:
        """Check if currently connected"""
        return self.manager.is_connected()
    
    def get_status(self) -> ConnectionStatus:
        """Get current connection status"""
        return self.manager.get_status()


# ==============================================================================
# FACTORY FUNCTION FOR DASHBOARD INTEGRATION
# ==============================================================================
def create_enhanced_connection_manager(logger=None) -> QtIBConnectionManager:
    """
    Factory function to create enhanced connection manager for dashboard integration.
    
    Args:
        logger: Optional logger instance
        
    Returns:
        QtIBConnectionManager: Ready-to-use connection manager
    """
    config = ConnectionConfig(
        paper_port=4002,
        live_port=4001,
        client_id=2,
        timeout_seconds=10,
        max_reconnect_attempts=5,
        reconnect_delays=[5, 10, 20, 40, 60],
        heartbeat_interval=30.0,
        connection_check_delay=0.1
    )
    
    return QtIBConnectionManager(config, logger)


# ==============================================================================
# TESTING AND EXAMPLE USAGE
# ==============================================================================
async def test_enhanced_manager():
    """Test the enhanced connection manager"""
    print("🧪 Testing Enhanced IB Connection Manager with ib.sleep()")
    
    manager = EnhancedIBConnectionManager()
    
    # Add status callback
    def status_callback(status: ConnectionStatus):
        print(f"Status: {status.state.value} | Mode: {status.mode} | Attempts: {status.reconnect_attempts}")
    
    manager.add_status_callback(status_callback)
    
    try:
        # Start manager
        await manager.start_async()
        
        # Let it run for a bit
        await manager.ib.sleep(60) if manager.ib else await asyncio.sleep(60)
        
        # Test manual disconnect/connect
        await manager.disconnect_manual()
        await manager.ib.sleep(5) if manager.ib else await asyncio.sleep(5)
        await manager.connect_manual()
        
        # Let it run more
        await manager.ib.sleep(30) if manager.ib else await asyncio.sleep(30)
        
    finally:
        await manager.stop_async()


if __name__ == "__main__":
    if IB_ASYNC_AVAILABLE:
        asyncio.run(test_enhanced_manager())
    else:
        print("❌ ib_async not available - cannot run test")
