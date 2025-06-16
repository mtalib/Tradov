#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB07_IBConnectionManager.py
Group: B (Broker Integration)
Purpose: Enhanced Interactive Brokers Gateway connection management

Description:
This module provides sophisticated connection management for IB Gateway including
exponential backoff retry strategies, health monitoring, scheduled connections,
mobile 2FA handling, and graceful position management. It coordinates connection
lifecycle with market hours and provides comprehensive monitoring capabilities
for stable API access throughout trading sessions.

Author: Mohamed Talib
Created: 2025-06-09
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import time
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

# =============================================================================
# Third-Party Imports
# =============================================================================
import pytz
from ib_insync import *

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError

# =============================================================================
# Constants
# =============================================================================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4002
DEFAULT_CLIENT_ID = 1
DEFAULT_TIMEZONE = "US/Eastern"
DEFAULT_CONNECT_TIME = "13:00"  # 1:00 PM EST
DEFAULT_DISCONNECT_TIME = "16:30"  # 4:30 PM EST
DEFAULT_MAX_RETRIES = 10
DEFAULT_INITIAL_RETRY_DELAY = 5
DEFAULT_MAX_RETRY_DELAY = 120
DEFAULT_HEALTH_CHECK_INTERVAL = 30

# =============================================================================
# Configuration Classes
# =============================================================================
@dataclass
class ConnectionConfig:
    """Configuration parameters for IB Gateway connection management."""
    
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    client_id: int = DEFAULT_CLIENT_ID
    connect_time: str = DEFAULT_CONNECT_TIME
    disconnect_time: str = DEFAULT_DISCONNECT_TIME
    timezone: str = DEFAULT_TIMEZONE
    max_retries: int = DEFAULT_MAX_RETRIES
    initial_retry_delay: int = DEFAULT_INITIAL_RETRY_DELAY
    max_retry_delay: int = DEFAULT_MAX_RETRY_DELAY
    health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL


# =============================================================================
# Class Definitions
# =============================================================================
class IBConnectionManager:
    """
    Enhanced IB Gateway connection manager with advanced features.
    
    This class provides sophisticated connection management including:
    - Exponential backoff retry strategies
    - Scheduled connection/disconnection based on market hours
    - Health monitoring with periodic connection verification
    - Mobile 2FA authentication handling
    - Graceful position management during disconnection
    - Comprehensive logging and error handling
    
    Attributes:
        config (ConnectionConfig): Connection configuration parameters
        ib (IB): Interactive Brokers API client instance
        news_callback (Callable): Optional callback for news gathering
        is_running (bool): Manager running state
        scheduler_thread (threading.Thread): Scheduler thread
        monitor_thread (threading.Thread): Monitor thread
        tz (pytz.timezone): Trading timezone
        logger (SpyderLogger): Application logger
        error_handler (SpyderErrorHandler): Error handler
    """
    
    def __init__(self, config: ConnectionConfig = None, news_callback: Callable = None):
        """
        Initialize the IB Gateway connection manager.
        
        Args:
            config: Connection configuration parameters
            news_callback: Optional callback function for news gathering
        """
        self.config = config or ConnectionConfig()
        self.ib = IB()
        self.news_callback = news_callback
        self.is_running = False
        self.scheduler_thread = None
        self.monitor_thread = None
        self.tz = pytz.timezone(self.config.timezone)
        
        # Initialize logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info("IBConnectionManager initialized")

    def connect_with_backoff(self) -> bool:
        """
        Connect to IB Gateway with exponential backoff retry strategy.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        retry_count = 0
        retry_delay = self.config.initial_retry_delay
        
        while retry_count < self.config.max_retries:
            try:
                if self.ib.isConnected():
                    self.logger.info("Already connected to IB Gateway")
                    return True
                    
                self.logger.info(f"Attempting to connect to IB Gateway (attempt {retry_count + 1})")
                self.ib.connect(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id
                )
                
                # Verify connection with actual API call
                if self._verify_connection():
                    self.logger.info("✅ Successfully connected to IB Gateway")
                    self._on_connection_established()
                    return True
                    
            except Exception as e:
                self.logger.error(f"Connection attempt {retry_count + 1} failed: {e}")
                self.error_handler.handle_error(e, context="IB Connection")
                
            retry_count += 1
            if retry_count < self.config.max_retries:
                self.logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, self.config.max_retry_delay)
        
        self.logger.error(f"❌ Failed to connect after {self.config.max_retries} attempts")
        return False
    
    def connect_with_approval_wait(self) -> bool:
        """
        Connect and wait for mobile 2FA approval.
        
        Returns:
            bool: True if connection and approval successful, False otherwise
        """
        approval_timeout = 300  # 5 minutes
        self.logger.info("🔄 Initiating connection - please approve on your mobile device")
        
        start_time = time.time()
        while time.time() - start_time < approval_timeout:
            try:
                self.ib.connect(
                    host=self.config.host,
                    port=self.config.port,
                    clientId=self.config.client_id
                )
                
                if self._verify_connection():
                    self.logger.info("📱 Mobile approval received - connection established")
                    self._on_connection_established()
                    return True
                    
            except Exception as e:
                if "authentication" in str(e).lower():
                    self.logger.info("⏳ Waiting for mobile approval...")
                    time.sleep(10)
                else:
                    self.logger.error(f"Connection error: {e}")
                    time.sleep(5)
        
        self.logger.error("⏰ Mobile approval timeout - connection failed")
        return False
    
    def _verify_connection(self) -> bool:
        """
        Verify connection health with actual API call.
        
        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            # Test with a simple API call
            account_summary = self.ib.reqAccountSummary()
            return len(account_summary) > 0
        except Exception as e:
            self.logger.warning(f"Connection verification failed: {e}")
            return False
    
    def _on_connection_established(self):
        """Called when connection is successfully established."""
        self.logger.info("🎯 Connection established, initializing services...")
        
        # Start gathering news if callback provided
        if self.news_callback:
            try:
                self.news_callback()
                self.logger.info("📰 News gathering initiated")
            except Exception as e:
                self.logger.error(f"Failed to start news gathering: {e}")
                self.error_handler.handle_error(e, context="News Gathering")
    
    def disconnect_gracefully(self):
        """Gracefully disconnect with position checks."""
        try:
            if not self.ib.isConnected():
                self.logger.info("Already disconnected")
                return
                
            # Check for open positions before disconnecting
            positions = self.ib.positions()
            if positions:
                self.logger.warning(f"⚠️ Disconnecting with {len(positions)} open positions")
                for pos in positions:
                    self.logger.warning(f"   • Open position: {pos.contract.symbol} - {pos.position}")
            
            self.ib.disconnect()
            self.logger.info("✅ Gracefully disconnected from IB Gateway")
            
        except Exception as e:
            self.logger.error(f"Error during graceful disconnect: {e}")
            self.error_handler.handle_error(e, context="Disconnection")
    
    def _is_market_hours(self) -> bool:
        """
        Check if current time is within market hours.
        
        Returns:
            bool: True if within market hours, False otherwise
        """
        now = datetime.now(self.tz)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        # Skip weekends
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        return market_open <= now <= market_close
    
    def _should_be_connected(self) -> bool:
        """
        Check if we should be connected based on schedule.
        
        Returns:
            bool: True if should be connected, False otherwise
        """
        now = datetime.now(self.tz)
        
        # Skip weekends
        if now.weekday() >= 5:
            return False
            
        connect_time = datetime.strptime(self.config.connect_time, "%H:%M").time()
        disconnect_time = datetime.strptime(self.config.disconnect_time, "%H:%M").time()
        
        current_time = now.time()
        return connect_time <= current_time <= disconnect_time
    
    def _connection_monitor(self):
        """Monitor connection health and reconnect if needed."""
        while self.is_running:
            try:
                if self._should_be_connected():
                    if not self.ib.isConnected() or not self._verify_connection():
                        self.logger.warning("⚠️ Connection lost or unhealthy, attempting reconnection...")
                        self.connect_with_backoff()
                elif self.ib.isConnected():
                    self.logger.info("🕐 Outside connection hours, disconnecting...")
                    self.disconnect_gracefully()
                    
                time.sleep(self.config.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in connection monitor: {e}")
                self.error_handler.handle_error(e, context="Connection Monitor")
                time.sleep(self.config.health_check_interval)
    
    def _scheduler(self):
        """Schedule connections and disconnections."""
        while self.is_running:
            try:
                now = datetime.now(self.tz)
                
                # Parse scheduled times
                connect_time = datetime.strptime(self.config.connect_time, "%H:%M").time()
                disconnect_time = datetime.strptime(self.config.disconnect_time, "%H:%M").time()
                
                # Create datetime objects for today
                today_connect = datetime.combine(now.date(), connect_time)
                today_connect = self.tz.localize(today_connect)
                today_disconnect = datetime.combine(now.date(), disconnect_time)
                today_disconnect = self.tz.localize(today_disconnect)
                
                # Calculate next scheduled action
                if now < today_connect:
                    next_action = today_connect
                    action = "connect"
                elif now < today_disconnect:
                    next_action = today_disconnect
                    action = "disconnect"
                else:
                    # Schedule for next day
                    tomorrow = now + timedelta(days=1)
                    next_action = datetime.combine(tomorrow.date(), connect_time)
                    next_action = self.tz.localize(next_action)
                    action = "connect"
                
                # Wait until next scheduled action
                wait_seconds = (next_action - now).total_seconds()
                if wait_seconds > 0:
                    self.logger.info(f"📅 Next {action} scheduled for {next_action} (in {wait_seconds:.0f} seconds)")
                    time.sleep(min(wait_seconds, 300))  # Check every 5 minutes max
                else:
                    # Execute action
                    if action == "connect" and not self.ib.isConnected():
                        self.logger.info("⏰ Executing scheduled connection")
                        self.connect_with_backoff()
                    elif action == "disconnect" and self.ib.isConnected():
                        self.logger.info("⏰ Executing scheduled disconnection")
                        self.disconnect_gracefully()
                    
                    time.sleep(60)  # Wait a minute before next check
                    
            except Exception as e:
                self.logger.error(f"Error in scheduler: {e}")
                self.error_handler.handle_error(e, context="Scheduler")
                time.sleep(60)
    
    def start(self):
        """Start the connection manager."""
        self.logger.info("🚀 Starting IBConnectionManager")
        self.is_running = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._connection_monitor, daemon=True)
        self.monitor_thread.start()
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Initial connection if we're in the connection window
        if self._should_be_connected():
            self.connect_with_backoff()
    
    def stop(self):
        """Stop the connection manager."""
        self.logger.info("🛑 Stopping IBConnectionManager")
        self.is_running = False
        
        if self.ib.isConnected():
            self.disconnect_gracefully()
        
        # Wait for threads to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
    
    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get current connection status and metrics.
        
        Returns:
            dict: Connection status information
        """
        return {
            "connected": self.ib.isConnected(),
            "should_be_connected": self._should_be_connected(),
            "market_hours": self._is_market_hours(),
            "next_connect": self.config.connect_time,
            "next_disconnect": self.config.disconnect_time,
            "current_time": datetime.now(self.tz).strftime("%H:%M:%S"),
            "client_id": self.config.client_id
        }

    def manual_connection_request(self) -> Dict[str, Any]:
        """
        Handle manual connection request from dashboard.
        
        Returns:
            dict: Connection attempt result
        """
        self.logger.info("🖱️ Manual connection requested from dashboard")
        
        if self.ib.isConnected():
            self.logger.info("Already connected to IB Gateway")
            return {"success": False, "message": "Already connected"}
        
        # Override time restrictions for manual connections
        self.logger.info("Initiating manual connection (bypassing schedule)")
        success = self.connect_with_backoff()
        
        if success:
            return {"success": True, "message": "Connection established successfully"}
        else:
            return {"success": False, "message": "Connection failed - check logs for details"}

    def close_all_positions(self) -> bool:
        """
        Close all open positions before disconnecting.
        
        Returns:
            bool: True if all positions closed successfully, False otherwise
        """
        try:
            if not self.ib.isConnected():
                self.logger.error("Cannot close positions - not connected to IB Gateway")
                return False
            
            positions = self.ib.positions()
            if not positions:
                self.logger.info("No positions to close")
                return True
            
            self.logger.info(f"🔄 Closing {len(positions)} open positions...")
            
            close_orders = []
            for pos in positions:
                if pos.position != 0:  # Only close non-zero positions
                    # Create market order to close position
                    action = 'SELL' if pos.position > 0 else 'BUY'
                    quantity = abs(pos.position)
                    
                    order = MarketOrder(action, quantity)
                    trade = self.ib.placeOrder(pos.contract, order)
                    close_orders.append(trade)
                    
                    self.logger.info(f"   • Closing {pos.contract.symbol}: {action} {quantity} shares")
            
            # Wait for orders to fill (with timeout)
            timeout = 30  # 30 seconds timeout
            start_time = time.time()
            
            while close_orders and (time.time() - start_time) < timeout:
                self.ib.sleep(1)  # Wait 1 second
                
                # Check which orders are still pending
                pending_orders = []
                for trade in close_orders:
                    if trade.orderStatus.status in ['Submitted', 'PreSubmitted', 'PendingSubmit']:
                        pending_orders.append(trade)
                    elif trade.orderStatus.status == 'Filled':
                        self.logger.info(f"   ✅ {trade.contract.symbol} position closed")
                    elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled']:
                        self.logger.warning(f"   ⚠️ {trade.contract.symbol} order cancelled")
                
                close_orders = pending_orders
            
            # Check final results
            remaining_positions = self.ib.positions()
            if any(pos.position != 0 for pos in remaining_positions):
                self.logger.warning("⚠️ Some positions may not have closed completely")
                return False
            else:
                self.logger.info("✅ All positions successfully closed")
                return True
                
        except Exception as e:
            self.logger.error(f"Error closing positions: {e}")
            self.error_handler.handle_error(e, context="Position Closure")
            return False


# =============================================================================
# Function Definitions
# =============================================================================
def gather_trading_news():
    """
    Example news gathering function.
    
    This function serves as a placeholder for implementing
    trading news gathering logic.
    """
    logger = SpyderLogger.get_logger("news_gathering")
    logger.info("📰 Gathering trading news...")
    # Implement your news gathering logic here
    # This could fetch from news APIs, IB news feed, etc.


# =============================================================================
# Main Execution
# =============================================================================
if __name__ == "__main__":
    # Create configuration
    config = ConnectionConfig(
        connect_time="13:00",    # 1:00 PM EST
        disconnect_time="16:30", # 4:30 PM EST
        max_retries=5
    )
    
    # Create connection manager with news callback
    manager = IBConnectionManager(config=config, news_callback=gather_trading_news)
    
    try:
        # Start the manager
        manager.start()
        
        # Keep running (in production, this would be your main application loop)
        while True:
            status = manager.get_connection_status()
            print(f"Status: {status}")
            time.sleep(300)  # Check status every 5 minutes
            
    except KeyboardInterrupt:
        print("Shutting down...")
        manager.stop()
