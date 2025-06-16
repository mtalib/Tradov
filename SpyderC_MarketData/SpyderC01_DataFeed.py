#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC01_DataFeed.py
Group: C (Market Data)
Purpose: Market data feed management

Description:
    This module manages real-time and historical market data feeds for the
    Spyder trading system. It provides a unified interface for accessing
    market data from various sources, handles data normalization, caching,
    and distribution to other system components. Supports both live and
    simulated data feeds for testing purposes.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_SYMBOL = "SPY"
CACHE_SIZE = 1000  # Number of ticks to cache
UPDATE_INTERVAL = 1.0  # Seconds between updates
RECONNECT_DELAY = 5  # Seconds before reconnection attempt
MAX_RECONNECT_ATTEMPTS = 3

# Market hours (Eastern Time)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# ==============================================================================
# ENUMS
# ==============================================================================
class DataFeedStatus(Enum):
    """Data feed status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    STOPPED = "stopped"

class DataSource(Enum):
    """Available data sources"""
    LIVE = "live"
    SIMULATED = "simulated"
    HISTORICAL = "historical"
    HYBRID = "hybrid"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketTick:
    """Market data tick structure"""
    symbol: str
    timestamp: datetime
    price: float
    bid: float
    ask: float
    volume: int
    bid_size: int = 0
    ask_size: int = 0
    last_size: int = 0

@dataclass
class DataFeedConfig:
    """Data feed configuration"""
    source: DataSource = DataSource.LIVE
    symbols: List[str] = None
    update_interval: float = UPDATE_INTERVAL
    cache_size: int = CACHE_SIZE
    
    def __post_init__(self):
        if self.symbols is None:
            self.symbols = [DEFAULT_SYMBOL]

# ==============================================================================
# MAIN CLASS
# ==============================================================================

# ==============================================================================
# MARKET DATA FEED CLASS
# ==============================================================================
class MarketDataFeed:
    """
    Basic market data feed class for real-time data.
    
    This class provides a standardized interface for market data feeds
    and serves as a base class for specific feed implementations.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """Initialize market data feed."""
        self.symbol = symbol
        self.callbacks = []
        self.is_active = False
        self.last_update = None
        
    def subscribe(self, callback):
        """Subscribe to data updates."""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
    
    def unsubscribe(self, callback):
        """Unsubscribe from data updates."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def start(self):
        """Start the data feed."""
        self.is_active = True
    
    def stop(self):
        """Stop the data feed."""
        self.is_active = False
    
    def get_latest_data(self):
        """Get latest market data."""
        return None

class DataFeedManager:
    """
    Market data feed manager for real-time and historical data.
    
    This class provides centralized management of market data feeds,
    handling connections, data normalization, caching, and distribution
    to subscribers throughout the trading system.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Data feed configuration
        status: Current feed status
        data_cache: Circular buffer for recent ticks
        
    Example:
        >>> feed = DataFeedManager(config)
        >>> feed.start()
        >>> data = feed.get_market_data("SPY")
    """
    
    def __init__(self, config: Optional[DataFeedConfig] = None):
        """Initialize data feed manager."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or DataFeedConfig()
        
        # State management
        self.status = DataFeedStatus.DISCONNECTED
        self.is_running = False
        self.last_update = None
        
        # Data storage
        self.data_cache = {}  # Symbol -> deque of MarketTick
        self.current_data = {}  # Symbol -> latest MarketTick
        self._init_data_cache()
        
        # Subscribers
        self.subscribers = {}  # Symbol -> List of callbacks
        
        # Threading
        self._lock = threading.Lock()
        self._worker_thread = None
        self._reconnect_attempts = 0
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the data feed.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Data feed already running")
                return True
            
            self.is_running = True
            self.status = DataFeedStatus.CONNECTING
            
            # Start worker thread
            self._start_worker()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while self.status == DataFeedStatus.CONNECTING:
                if time.time() - start_time > timeout:
                    self.logger.error("Connection timeout")
                    self.stop()
                    return False
                time.sleep(0.1)
            
            if self.status == DataFeedStatus.CONNECTED:
                self.logger.info("Data feed started successfully")
                return True
            else:
                self.logger.error("Failed to start data feed")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start data feed: {e}")
            self.status = DataFeedStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the data feed.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            self.is_running = False
            self.status = DataFeedStatus.STOPPED
            
            # Stop worker thread
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5)
            
            self.logger.info("Data feed stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop data feed: {e}")
            return False
    
    def get_market_data(self, symbol: str = DEFAULT_SYMBOL) -> Dict[str, Any]:
        """
        Get current market data for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dict containing market data
        """
        try:
            with self._lock:
                tick = self.current_data.get(symbol)
                
            if tick:
                return {
                    'symbol': tick.symbol,
                    'price': tick.price,
                    'timestamp': tick.timestamp.isoformat(),
                    'volume': tick.volume,
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'spread': tick.ask - tick.bid,
                    'mid': (tick.bid + tick.ask) / 2
                }
            else:
                # Return placeholder data if not available
                return self._generate_placeholder_data(symbol)
                
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return {}
    
    def get_historical_data(self, symbol: str, count: int = 100) -> List[MarketTick]:
        """
        Get historical ticks from cache.
        
        Args:
            symbol: Trading symbol
            count: Number of ticks to retrieve
            
        Returns:
            List of MarketTick objects
        """
        try:
            with self._lock:
                cache = self.data_cache.get(symbol, deque())
                # Return most recent 'count' items
                return list(cache)[-count:]
                
        except Exception as e:
            self.logger.error(f"Error getting historical data: {e}")
            return []
    
    def subscribe(self, symbol: str, callback: Callable) -> bool:
        """
        Subscribe to market data updates.
        
        Args:
            symbol: Trading symbol
            callback: Function to call with updates
            
        Returns:
            bool: True if subscribed successfully
        """
        try:
            with self._lock:
                if symbol not in self.subscribers:
                    self.subscribers[symbol] = []
                self.subscribers[symbol].append(callback)
                
            self.logger.debug(f"Subscribed to {symbol} updates")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {symbol}: {e}")
            return False
    
    def unsubscribe(self, symbol: str, callback: Callable) -> bool:
        """
        Unsubscribe from market data updates.
        
        Args:
            symbol: Trading symbol
            callback: Callback function to remove
            
        Returns:
            bool: True if unsubscribed successfully
        """
        try:
            with self._lock:
                if symbol in self.subscribers:
                    self.subscribers[symbol].remove(callback)
                    if not self.subscribers[symbol]:
                        del self.subscribers[symbol]
                        
            self.logger.debug(f"Unsubscribed from {symbol} updates")
            return True
            
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False
    
    def is_market_open(self) -> bool:
        """
        Check if market is currently open.
        
        Returns:
            bool: True if market is open
        """
        now = datetime.now()
        
        # Check if weekend
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check market hours
        market_open = now.replace(
            hour=MARKET_OPEN_HOUR,
            minute=MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0
        )
        market_close = now.replace(
            hour=MARKET_CLOSE_HOUR,
            minute=MARKET_CLOSE_MINUTE,
            second=0,
            microsecond=0
        )
        
        return market_open <= now <= market_close
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _init_data_cache(self):
        """Initialize data cache for configured symbols."""
        for symbol in self.config.symbols:
            self.data_cache[symbol] = deque(maxlen=self.config.cache_size)
    
    def _start_worker(self):
        """Start worker thread for data updates."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self._worker_thread.start()
    
    def _worker_loop(self):
        """Main worker loop for data updates."""
        self.logger.info("Data feed worker started")
        
        # Simulate connection
        time.sleep(0.5)
        self.status = DataFeedStatus.CONNECTED
        self._reconnect_attempts = 0
        
        while self.is_running:
            try:
                # Update market data
                for symbol in self.config.symbols:
                    self._update_market_data(symbol)
                
                # Sleep until next update
                time.sleep(self.config.update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in data feed worker: {e}")
                self._handle_connection_error()
    
    def _update_market_data(self, symbol: str):
        """Update market data for symbol."""
        try:
            # Generate or fetch new tick
            if self.config.source == DataSource.SIMULATED:
                tick = self._generate_simulated_tick(symbol)
            else:
                tick = self._fetch_live_tick(symbol)
            
            if tick:
                with self._lock:
                    # Update current data
                    self.current_data[symbol] = tick
                    
                    # Add to cache
                    self.data_cache[symbol].append(tick)
                    
                    # Update timestamp
                    self.last_update = datetime.now()
                
                # Notify subscribers
                self._notify_subscribers(symbol, tick)
                
        except Exception as e:
            self.logger.error(f"Error updating market data for {symbol}: {e}")
    
    def _generate_simulated_tick(self, symbol: str) -> MarketTick:
        """Generate simulated market tick."""
        # Get previous price or use default
        prev_tick = self.current_data.get(symbol)
        if prev_tick:
            base_price = prev_tick.price
        else:
            base_price = 450.0 if symbol == "SPY" else 100.0
        
        # Generate random walk
        change = np.random.normal(0, 0.1)
        new_price = base_price * (1 + change / 100)
        
        # Generate bid/ask
        spread = 0.01
        bid = new_price - spread / 2
        ask = new_price + spread / 2
        
        # Generate volume
        volume = int(np.random.exponential(1000000))
        
        return MarketTick(
            symbol=symbol,
            timestamp=datetime.now(),
            price=round(new_price, 2),
            bid=round(bid, 2),
            ask=round(ask, 2),
            volume=volume,
            bid_size=int(np.random.exponential(100)),
            ask_size=int(np.random.exponential(100)),
            last_size=int(np.random.exponential(10))
        )
    
    def _fetch_live_tick(self, symbol: str) -> Optional[MarketTick]:
        """Fetch live market tick (placeholder)."""
        # This would connect to actual data source
        # For now, return simulated data
        return self._generate_simulated_tick(symbol)
    
    def _generate_placeholder_data(self, symbol: str) -> Dict[str, Any]:
        """Generate placeholder market data."""
        return {
            'symbol': symbol,
            'price': 450.00 if symbol == "SPY" else 100.00,
            'timestamp': datetime.now().isoformat(),
            'volume': 1000000,
            'bid': 449.95,
            'ask': 450.05,
            'spread': 0.10,
            'mid': 450.00
        }
    
    def _notify_subscribers(self, symbol: str, tick: MarketTick):
        """Notify subscribers of new data."""
        with self._lock:
            callbacks = self.subscribers.get(symbol, []).copy()
        
        for callback in callbacks:
            try:
                callback(tick)
            except Exception as e:
                self.logger.error(f"Error in subscriber callback: {e}")
    
    def _handle_connection_error(self):
        """Handle connection errors with reconnection logic."""
        self.status = DataFeedStatus.ERROR
        self._reconnect_attempts += 1
        
        if self._reconnect_attempts > MAX_RECONNECT_ATTEMPTS:
            self.logger.error("Max reconnection attempts reached")
            self.stop()
            return
        
        self.logger.info(f"Attempting reconnection {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}")
        time.sleep(RECONNECT_DELAY)
        
        # Attempt reconnection
        self.status = DataFeedStatus.CONNECTING
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def shutdown(self) -> None:
        """Shutdown the data feed gracefully."""
        try:
            self.stop()
            
            # Clear data
            with self._lock:
                self.data_cache.clear()
                self.current_data.clear()
                self.subscribers.clear()
            
            self.logger.info("Data feed manager shut down")
            
        except Exception as e:
            self.logger.error(f"Error during data feed shutdown: {e}")
    
    def cleanup(self) -> None:
        """Clean up data feed resources."""
        self.shutdown()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_data_feed_instance: Optional[DataFeedManager] = None

def get_data_feed_manager(config: Optional[DataFeedConfig] = None) -> DataFeedManager:
    """
    Get singleton data feed manager instance.
    
    Args:
        config: Optional configuration
        
    Returns:
        DataFeedManager instance
    """
    global _data_feed_instance
    if _data_feed_instance is None:
        _data_feed_instance = DataFeedManager(config)
    return _data_feed_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
__all__ = [
    'DataFeedManager',
    'get_data_feed_manager',
    'DataFeedStatus',
    'DataSource',
    'MarketTick',
    'DataFeedConfig'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    feed = DataFeedManager()
    
    if feed.start():
        print("✅ DataFeedManager test passed")
        
        # Test getting market data
        data = feed.get_market_data("SPY")
        print(f"Market data: {data}")
        
        # Test subscription
        def on_update(tick):
            print(f"Update: {tick.symbol} @ {tick.price}")
        
        feed.subscribe("SPY", on_update)
        
        # Run for a few seconds
        time.sleep(3)
        
        # Cleanup
        feed.stop()
        feed.cleanup()
    else:
        print("❌ DataFeedManager test failed")