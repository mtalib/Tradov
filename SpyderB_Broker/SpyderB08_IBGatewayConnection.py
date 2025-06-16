#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderB08_IBGatewayConnection.py
Group: B (Broker Integration)
Purpose: Core IB Gateway connection with news gathering and session management

Description:
This module provides the core Interactive Brokers Gateway connection functionality
with simplified connection management, news gathering upon connection, session
maintenance, and position management. It serves as a focused connection handler
for specific trading strategies and provides real-time position tracking with
selective closure capabilities.

Author: Mohamed Talib
Created: 2025-06-09
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable, Dict, Any, List

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
DEFAULT_CONNECT_TIME = "13:00"    # 1:00 PM EST
DEFAULT_DISCONNECT_TIME = "16:30" # 4:30 PM EST
DEFAULT_TIMEZONE = "US/Eastern"
CONNECTION_CHECK_INTERVAL = 30  # seconds
NEWS_GATHERING_INTERVAL = 300   # 5 minutes
SESSION_REFRESH_INTERVAL = 1800 # 30 minutes

# =============================================================================
# Class Definitions
# =============================================================================
class SpyderIBConnection:
    """
    Core IB Gateway connection handler for Spyder trading system.
    
    This class provides simplified connection management with essential features:
    - Scheduled connection/disconnection based on trading hours
    - News gathering upon successful connection
    - Session maintenance with periodic refresh
    - Position tracking and selective closure
    - Mobile 2FA authentication support
    - Real-time connection monitoring
    
    Attributes:
        ib (IB): Interactive Brokers API client instance
        is_running (bool): Connection manager running state
        scheduler_thread (threading.Thread): Scheduler thread
        monitor_thread (threading.Thread): Monitor thread
        news_thread (threading.Thread): News gathering thread
        est (pytz.timezone): Eastern timezone
        host (str): IB Gateway host address
        port (int): IB Gateway port number
        client_id (int): API client identifier
        connect_time (str): Scheduled connection time
        disconnect_time (str): Scheduled disconnection time
        logger (SpyderLogger): Application logger
        error_handler (SpyderErrorHandler): Error handler
    """
    
    def __init__(self):
        """Initialize the Spyder IB Gateway connection."""
        self.ib = IB()
        self.is_running = False
        self.scheduler_thread = None
        self.monitor_thread = None
        self.news_thread = None
        self.est = pytz.timezone(DEFAULT_TIMEZONE)
        
        # Connection settings
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.client_id = DEFAULT_CLIENT_ID
        
        # Schedule settings
        self.connect_time = DEFAULT_CONNECT_TIME
        self.disconnect_time = DEFAULT_DISCONNECT_TIME
        
        # Initialize logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.logger.info("SpyderIBConnection initialized")
    
    def connect_ib(self) -> bool:
        """
        Enhanced connection with mobile 2FA waiting.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        self.logger.info("🚀 SPYDER IB CONNECTION STARTING")
        self.logger.info("📱 Please approve the connection on your mobile device when prompted")
        
        retry_count = 0
        max_retries = 5
        
        while retry_count < max_retries:
            try:
                if self.ib.isConnected():
                    self.logger.info("Already connected to IB Gateway")
                    return True
                
                self.logger.info(f"Connecting to IB Gateway (attempt {retry_count + 1})")
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                
                # Verify connection with account summary
                account_summary = self.ib.reqAccountSummary()
                if account_summary:
                    self.logger.info("✅ Successfully connected to IB Gateway")
                    self.logger.info(f"Account details retrieved: {len(account_summary)} items")
                    
                    # Start news gathering upon successful connection
                    self.start_news_gathering()
                    return True
                
            except Exception as e:
                retry_count += 1
                if "authentication" in str(e).lower() or "login" in str(e).lower():
                    self.logger.warning(f"⏳ Waiting for mobile 2FA approval... (attempt {retry_count})")
                    time.sleep(30)  # Wait longer for mobile approval
                else:
                    self.logger.error(f"Connection failed: {e}")
                    self.error_handler.handle_error(e, context="IB Connection")
                    if retry_count < max_retries:
                        self.logger.info("Retrying in 10 seconds...")
                        time.sleep(10)
        
        self.logger.error(f"❌ Failed to connect after {max_retries} attempts")
        return False
    
    def disconnect_ib(self):
        """Graceful disconnection with position check."""
        if not self.ib.isConnected():
            self.logger.info("Already disconnected from IB Gateway")
            return
        
        try:
            # Check for open positions before disconnecting
            positions = self.ib.positions()
            if positions:
                self.logger.warning(f"⚠️ Disconnecting with {len(positions)} open positions:")
                for pos in positions:
                    self.logger.warning(f"   • {pos.contract.symbol}: {pos.position} shares")
            
            self.ib.disconnect()
            self.logger.info("✅ Gracefully disconnected from IB Gateway")
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            self.error_handler.handle_error(e, context="Disconnection")
    
    def start_news_gathering(self):
        """Start gathering trading news upon connection."""
        if self.news_thread and self.news_thread.is_alive():
            return
            
        self.news_thread = threading.Thread(target=self._gather_news, daemon=True)
        self.news_thread.start()
        self.logger.info("📰 Started trading news gathering")
    
    def _gather_news(self):
        """
        Gather trading news - implement your news logic here.
        
        This method runs in a separate thread and continuously gathers
        trading news while the connection is active.
        """
        while self.ib.isConnected() and self.is_running:
            try:
                # Example: Get market data for news-relevant stocks
                # You can implement your specific news gathering logic here
                
                # Placeholder for news gathering
                current_time = datetime.now(self.est).strftime("%H:%M:%S")
                self.logger.info(f"📊 Gathering trading news at {current_time}")
                
                # Your news gathering implementation goes here:
                # - Fetch from news APIs
                # - Get IB news headlines
                # - Process market-moving events
                # - Store news data for analysis
                
                time.sleep(NEWS_GATHERING_INTERVAL)  # Gather news every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error gathering news: {e}")
                self.error_handler.handle_error(e, context="News Gathering")
                time.sleep(60)
    
    def should_be_connected(self) -> bool:
        """
        Check if we should be connected based on schedule.
        
        Returns:
            bool: True if should be connected, False otherwise
        """
        now = datetime.now(self.est)
        
        # Skip weekends
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Parse connection times
        connect_hour, connect_min = map(int, self.connect_time.split(':'))
        disconnect_hour, disconnect_min = map(int, self.disconnect_time.split(':'))
        
        connect_time = now.replace(hour=connect_hour, minute=connect_min, second=0, microsecond=0)
        disconnect_time = now.replace(hour=disconnect_hour, minute=disconnect_min, second=0, microsecond=0)
        
        return connect_time <= now <= disconnect_time
    
    def _connection_monitor(self):
        """Monitor connection and reconnect if needed."""
        while self.is_running:
            try:
                current_time = datetime.now(self.est).strftime("%H:%M:%S EST")
                
                if self.should_be_connected():
                    if not self.ib.isConnected():
                        self.logger.warning(f"⚠️ Connection lost at {current_time}, attempting reconnect...")
                        self.connect_ib()
                    else:
                        # Keep session active with periodic account summary request
                        try:
                            account_summary = self.ib.reqAccountSummary()
                            self.logger.debug(f"Session refreshed at {current_time}")
                        except Exception as e:
                            self.logger.warning(f"Session refresh failed: {e}")
                            
                elif self.ib.isConnected():
                    self.logger.info(f"🕐 Outside trading hours ({current_time}), disconnecting...")
                    self.disconnect_ib()
                
                time.sleep(CONNECTION_CHECK_INTERVAL)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in connection monitor: {e}")
                self.error_handler.handle_error(e, context="Connection Monitor")
                time.sleep(CONNECTION_CHECK_INTERVAL)
    
    def _scheduler(self):
        """Handle scheduled connections and disconnections."""
        while self.is_running:
            try:
                now = datetime.now(self.est)
                current_time = now.strftime("%H:%M:%S EST")
                
                # Skip weekends
                if now.weekday() >= 5:
                    self.logger.info("🏖️ Weekend detected, skipping connection checks")
                    time.sleep(3600)  # Check again in 1 hour
                    continue
                
                if self.should_be_connected() and not self.ib.isConnected():
                    self.logger.info(f"⏰ Scheduled connection time reached ({current_time})")
                    self.connect_ib()
                
                time.sleep(60)  # Check every minute for scheduled actions
                
            except Exception as e:
                self.logger.error(f"Error in scheduler: {e}")
                self.error_handler.handle_error(e, context="Scheduler")
                time.sleep(60)
    
    def start(self):
        """Start Spyder IB connection manager."""
        self.logger.info("🚀 STARTING SPYDER IB CONNECTION MANAGER")
        self.logger.info(f"📅 Schedule: Connect at {self.connect_time} EST, Disconnect at {self.disconnect_time} EST")
        self.logger.info("📱 Mobile 2FA approval will be required at connection time")
        
        self.is_running = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._connection_monitor, daemon=True)
        self.monitor_thread.start()
        
        # Start scheduler thread  
        self.scheduler_thread = threading.Thread(target=self._scheduler, daemon=True)
        self.scheduler_thread.start()
        
        # Connect immediately if we're in the connection window
        if self.should_be_connected():
            self.logger.info("Currently in connection window, connecting now...")
            self.connect_ib()
        else:
            next_connect = datetime.now(self.est).replace(
                hour=int(self.connect_time.split(':')[0]), 
                minute=int(self.connect_time.split(':')[1]), 
                second=0, microsecond=0
            )
            if next_connect <= datetime.now(self.est):
                next_connect += timedelta(days=1)
            self.logger.info(f"⏰ Next connection scheduled for: {next_connect.strftime('%Y-%m-%d %H:%M EST')}")
    
    def stop(self):
        """Stop Spyder IB connection manager."""
        self.logger.info("🛑 STOPPING SPYDER IB CONNECTION MANAGER")
        self.is_running = False
        
        if self.ib.isConnected():
            self.disconnect_ib()
        
        # Wait for threads to finish
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("✅ Spyder IB connection manager stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current connection status.
        
        Returns:
            dict: Current connection status information
        """
        now = datetime.now(self.est)
        return {
            "connected": self.ib.isConnected(),
            "should_be_connected": self.should_be_connected(),
            "current_time": now.strftime("%H:%M:%S EST"),
            "current_date": now.strftime("%Y-%m-%d"),
            "is_weekend": now.weekday() >= 5,
            "next_connect": self.connect_time,
            "next_disconnect": self.disconnect_time,
            "news_gathering": self.news_thread.is_alive() if self.news_thread else False
        }

    def close_specific_position(self, symbol: str, contract_id: int = None) -> bool:
        """
        Close a specific position by symbol.
        
        Args:
            symbol: Stock symbol to close
            contract_id: Optional contract identifier
            
        Returns:
            bool: True if position closed successfully, False otherwise
        """
        try:
            if not self.ib.isConnected():
                self.logger.error("Cannot close position - not connected to IB Gateway")
                return False
            
            # Find the position
            positions = self.ib.positions()
            target_position = None
            
            for pos in positions:
                if pos.contract.symbol == symbol:
                    if contract_id is None or pos.contract.conId == contract_id:
                        target_position = pos
                        break
            
            if not target_position or target_position.position == 0:
                self.logger.warning(f"No position found for {symbol}")
                return False
            
            # Create market order to close the position
            action = 'SELL' if target_position.position > 0 else 'BUY'
            quantity = abs(target_position.position)
            
            order = MarketOrder(action, quantity)
            trade = self.ib.placeOrder(target_position.contract, order)
            
            self.logger.info(f"🔄 Closing {symbol}: {action} {quantity} shares")
            
            # Wait for order to fill (with timeout)
            timeout = 30  # 30 seconds
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                self.ib.sleep(1)
                
                if trade.orderStatus.status == 'Filled':
                    self.logger.info(f"   ✅ {symbol} position closed successfully")
                    return True
                elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled']:
                    self.logger.warning(f"   ⚠️ {symbol} order was cancelled")
                    return False
            
            # Timeout reached
            self.logger.warning(f"   ⏰ Timeout closing {symbol} position")
            return False
            
        except Exception as e:
            self.logger.error(f"Error closing {symbol} position: {e}")
            self.error_handler.handle_error(e, context=f"Position Closure - {symbol}")
            return False

    def get_detailed_positions(self) -> List[Dict[str, Any]]:
        """
        Get detailed position information for the dashboard.
        
        Returns:
            list: List of detailed position dictionaries
        """
        try:
            if not self.ib.isConnected():
                return []
            
            positions = self.ib.positions()
            detailed_positions = []
            
            for pos in positions:
                if pos.position != 0:  # Only include non-zero positions
                    detailed_positions.append({
                        'symbol': pos.contract.symbol,
                        'contract_id': pos.contract.conId,
                        'position': pos.position,
                        'market_price': pos.marketPrice,
                        'market_value': pos.marketValue,
                        'unrealized_pnl': pos.unrealizedPNL,
                        'avg_cost': pos.avgCost,
                        'contract_type': pos.contract.secType,
                        'exchange': pos.contract.exchange,
                        'currency': pos.contract.currency
                    })
            
            return detailed_positions
            
        except Exception as e:
            self.logger.error(f"Error getting detailed positions: {e}")
            self.error_handler.handle_error(e, context="Position Retrieval")
            return []


# =============================================================================
# Main Execution
# =============================================================================
if __name__ == "__main__":
    spyder = SpyderIBConnection()
    
    try:
        spyder.start()
        
        # Main loop - show status periodically
        while True:
            status = spyder.get_status()
            print(f"\n--- SPYDER STATUS ---")
            print(f"Connected: {'✅' if status['connected'] else '❌'}")
            print(f"Current Time: {status['current_time']}")
            print(f"Should Be Connected: {status['should_be_connected']}")
            print(f"News Gathering: {'✅' if status['news_gathering'] else '❌'}")
            print(f"Weekend: {status['is_weekend']}")
            
            time.sleep(300)  # Show status every 5 minutes
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down Spyder...")
        spyder.stop()
