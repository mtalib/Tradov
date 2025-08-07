#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB07_MarketDataManager.py
Group: B (Broker Integration)
Purpose: Centralized market data management for all trading symbols

Description:
    This module provides centralized market data management for all required
    trading symbols with different update frequencies. It handles SPY, ES 
    futures, and OPRA SPY options data at 1-second intervals, while other 
    symbols update every 5 seconds. The module includes automatic subscription
    management, data caching, and distribution to other system components.

Author: Mohamed Talib
Date: 2025-01-13
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from enum import Enum, auto
from dataclasses import dataclass, field
from collections import defaultdict, deque
import asyncio
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from threading import Lock, RLock, Event as ThreadEvent

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from SpyderB_Broker.SpyderB10_IBDataTypes import SecurityType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update frequencies (in seconds)
HIGH_FREQUENCY_INTERVAL = 1    # SPY, ES, OPRA options
LOW_FREQUENCY_INTERVAL = 5     # Other symbols

# Symbol categories
HIGH_FREQUENCY_SYMBOLS = {'SPY', 'ES', 'MES', '/ES', '/MES', '/SP'}
FUTURES_SYMBOLS = {'/SP', '/ES', '/MES', 'ES', 'MES'}
INDEX_SYMBOLS = {'SPX', 'XSP', 'NANOS', 'VIX', 'VIX9D', 'VIX3M', 'VIX6M', 'VIX1Y', 'CPC', 'DXY'}
ETF_SYMBOLS = {'SPY', 'DIA', 'QQQ', 'IWM', 'TLT', 'IEF', 'HYG', 'GLD', 'USO', 'DBC', 'UVXY'}
MARKET_INTERNALS = {'$TICK', '$TRIN', '$ADD', '$VOLD'}

# All trading symbols
TRADING_SYMBOLS = {
    # S&P ETF & Indices
    'SPY': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'SPX': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'XSP': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'NANOS': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    
    # S&P Futures
    '/SP': {'type': SecurityType.FUT, 'exchange': 'CME', 'currency': 'USD'},
    '/ES': {'type': SecurityType.FUT, 'exchange': 'CME', 'currency': 'USD'},
    'ES': {'type': SecurityType.FUT, 'exchange': 'CME', 'currency': 'USD'},
    '/MES': {'type': SecurityType.FUT, 'exchange': 'CME', 'currency': 'USD'},
    'MES': {'type': SecurityType.FUT, 'exchange': 'CME', 'currency': 'USD'},
    
    # Volatility
    'VIX': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'VIX9D': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'VIX3M': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'VIX6M': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'VIX1Y': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'UVXY': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    
    # Major ETFs
    'CPC': {'type': SecurityType.IND, 'exchange': 'CBOE', 'currency': 'USD'},
    'DIA': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'QQQ': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'IWM': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    
    # Treasury/Bonds
    'TLT': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'IEF': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'HYG': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'DXY': {'type': SecurityType.IND, 'exchange': 'ICE', 'currency': 'USD'},
    
    # Commodities
    'GLD': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'USO': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    'DBC': {'type': SecurityType.STOCK, 'exchange': 'SMART', 'currency': 'USD'},
    
    # Market Breadth
    '$TICK': {'type': SecurityType.IND, 'exchange': 'NYSE', 'currency': 'USD'},
    '$TRIN': {'type': SecurityType.IND, 'exchange': 'NYSE', 'currency': 'USD'},
    '$ADD': {'type': SecurityType.IND, 'exchange': 'NYSE', 'currency': 'USD'},
    '$VOLD': {'type': SecurityType.IND, 'exchange': 'NYSE', 'currency': 'USD'},
}

# Data quality thresholds
MAX_STALE_SECONDS = 10
MAX_SPREAD_PERCENT = 0.5
MIN_TICK_SIZE = 0.01

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketDataStatus(Enum):
    """Market data feed status"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    SUBSCRIBED = auto()
    ERROR = auto()
    STALE = auto()

class DataQuality(Enum):
    """Data quality indicators"""
    GOOD = auto()
    DELAYED = auto()
    STALE = auto()
    INVALID = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketDataSnapshot:
    """Complete market data snapshot for a symbol"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    bid_size: int
    ask_size: int
    last_size: int
    volume: int
    high: float
    low: float
    open: float
    close: float
    vwap: float = 0.0
    spread: float = 0.0
    mid_price: float = 0.0
    quality: DataQuality = DataQuality.GOOD
    
    def __post_init__(self):
        """Calculate derived fields"""
        if self.bid > 0 and self.ask > 0:
            self.spread = self.ask - self.bid
            self.mid_price = (self.bid + self.ask) / 2

@dataclass
class OptionDataSnapshot(MarketDataSnapshot):
    """Extended market data for options"""
    underlying_price: float = 0.0
    strike: float = 0.0
    expiry: str = ""
    option_type: str = ""  # 'C' or 'P'
    implied_volatility: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    open_interest: int = 0

@dataclass
class MarketDataMetrics:
    """Metrics for market data quality and performance"""
    subscriptions_active: int = 0
    subscriptions_stale: int = 0
    subscriptions_error: int = 0
    updates_per_second: float = 0.0
    average_latency_ms: float = 0.0
    data_gaps: int = 0
    last_update: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MARKET DATA MANAGER CLASS
# ==============================================================================
class MarketDataManager:
    """
    Centralized market data management for all trading symbols.
    
    This class handles:
    - Subscription management for all required symbols
    - Different update frequencies for different symbol groups
    - Data quality monitoring and validation
    - Distribution of market data to other system components
    - Automatic reconnection and recovery
    """
    
    def __init__(self, 
                 spyder_client: SpyderClient,
                 event_manager: Optional[EventManager] = None):
        """
        Initialize Market Data Manager.
        
        Args:
            spyder_client: SpyderClient instance for IB connection
            event_manager: Optional event manager for data distribution
        """
        # Core components
        self.client = spyder_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler(__name__)
        
        # Thread safety
        self._lock = RLock()
        self._data_lock = RLock()
        
        # Market data storage
        self.market_data: Dict[str, MarketDataSnapshot] = {}
        self.option_data: Dict[str, OptionDataSnapshot] = {}
        self.data_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Subscription tracking
        self.subscriptions: Dict[str, int] = {}  # symbol -> reqId
        self.req_id_to_symbol: Dict[int, str] = {}  # reqId -> symbol
        self.subscription_status: Dict[str, MarketDataStatus] = {}
        
        # Update scheduling
        self.high_freq_symbols: Set[str] = set()
        self.low_freq_symbols: Set[str] = set()
        self._categorize_symbols()
        
        # Callbacks
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Worker threads
        self.is_running = False
        self._high_freq_thread: Optional[threading.Thread] = None
        self._low_freq_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Metrics
        self.metrics = MarketDataMetrics()
        self._update_counts: Dict[str, int] = defaultdict(int)
        self._last_update_time = datetime.now()
        
        # Configuration
        self.max_subscription_retries = 3
        self.subscription_retry_delay = 2
        
        self.logger.info("Market Data Manager initialized")
    
    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    
    def _categorize_symbols(self) -> None:
        """Categorize symbols by update frequency."""
        for symbol in TRADING_SYMBOLS.keys():
            if symbol in HIGH_FREQUENCY_SYMBOLS:
                self.high_freq_symbols.add(symbol)
            else:
                self.low_freq_symbols.add(symbol)
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    
    def start(self) -> bool:
        """
        Start market data manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Market data manager already running")
                return True
            
            if not self.client.is_connected():
                self.logger.error("IB client not connected")
                return False
            
            self.is_running = True
            
            # Subscribe to all symbols
            self._subscribe_all_symbols()
            
            # Start worker threads
            self._high_freq_thread = threading.Thread(
                target=self._high_frequency_worker,
                name="MarketData-HighFreq"
            )
            self._high_freq_thread.daemon = True
            self._high_freq_thread.start()
            
            self._low_freq_thread = threading.Thread(
                target=self._low_frequency_worker,
                name="MarketData-LowFreq"
            )
            self._low_freq_thread.daemon = True
            self._low_freq_thread.start()
            
            self._monitor_thread = threading.Thread(
                target=self._monitor_worker,
                name="MarketData-Monitor"
            )
            self._monitor_thread.daemon = True
            self._monitor_thread.start()
            
            self.logger.info("Market data manager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start market data manager: {e}")
            self.error_handler.handle_error(e)
            return False
    
    def stop(self) -> None:
        """Stop market data manager."""
        try:
            self.is_running = False
            
            # Cancel all subscriptions
            self._cancel_all_subscriptions()
            
            # Wait for threads to finish
            threads = [self._high_freq_thread, self._low_freq_thread, self._monitor_thread]
            for thread in threads:
                if thread and thread.is_alive():
                    thread.join(timeout=5)
            
            self.logger.info("Market data manager stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping market data manager: {e}")
            self.error_handler.handle_error(e)
    
    # ==========================================================================
    # SUBSCRIPTION MANAGEMENT
    # ==========================================================================
    
    def _subscribe_all_symbols(self) -> None:
        """Subscribe to all configured symbols."""
        for symbol, config in TRADING_SYMBOLS.items():
            self._subscribe_symbol(symbol, config)
            time.sleep(0.1)  # Rate limiting
    
    def _subscribe_symbol(self, symbol: str, config: Dict[str, Any]) -> bool:
        """
        Subscribe to a single symbol.
        
        Args:
            symbol: Trading symbol
            config: Symbol configuration
            
        Returns:
            bool: True if subscribed successfully
        """
        try:
            # Skip if already subscribed
            if symbol in self.subscriptions:
                return True
            
            # Create contract based on security type
            contract = self._create_contract(symbol, config)
            if not contract:
                self.logger.error(f"Failed to create contract for {symbol}")
                return False
            
            # Request market data
            req_id = self.client.request_market_data(contract)
            if req_id < 0:
                self.logger.error(f"Failed to request market data for {symbol}")
                self.subscription_status[symbol] = MarketDataStatus.ERROR
                return False
            
            # Track subscription
            with self._lock:
                self.subscriptions[symbol] = req_id
                self.req_id_to_symbol[req_id] = symbol
                self.subscription_status[symbol] = MarketDataStatus.SUBSCRIBED
            
            self.logger.info(f"Subscribed to {symbol} (reqId: {req_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to {symbol}: {e}")
            self.error_handler.handle_error(e)
            return False
    
    def _create_contract(self, symbol: str, config: Dict[str, Any]) -> Optional[Any]:
        """
        Create IB contract for symbol.
        
        Args:
            symbol: Trading symbol
            config: Symbol configuration
            
        Returns:
            Contract object or None
        """
        try:
            sec_type = config['type']
            
            if sec_type == SecurityType.STOCK:
                return self.client.create_stock_contract(symbol)
            
            elif sec_type == SecurityType.FUT:
                # Handle futures - need to determine expiry
                clean_symbol = symbol.replace('/', '')
                # For continuous futures, use the front month
                # This is simplified - in production you'd determine the actual expiry
                return self.client.create_futures_contract(
                    clean_symbol,
                    exchange=config['exchange']
                )
            
            elif sec_type == SecurityType.IND:
                # Indices require special handling
                return self.client.create_index_contract(
                    symbol,
                    exchange=config['exchange']
                )
            
            else:
                self.logger.warning(f"Unsupported security type for {symbol}: {sec_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    def _cancel_all_subscriptions(self) -> None:
        """Cancel all active subscriptions."""
        with self._lock:
            for symbol, req_id in list(self.subscriptions.items()):
                try:
                    self.client.cancel_market_data(req_id)
                    del self.subscriptions[symbol]
                    del self.req_id_to_symbol[req_id]
                    self.subscription_status[symbol] = MarketDataStatus.DISCONNECTED
                except Exception as e:
                    self.logger.error(f"Error canceling subscription for {symbol}: {e}")
    
    # ==========================================================================
    # DATA UPDATE WORKERS
    # ==========================================================================
    
    def _high_frequency_worker(self) -> None:
        """Worker thread for high-frequency symbol updates."""
        while self.is_running:
            try:
                start_time = time.time()
                
                # Update high-frequency symbols
                for symbol in self.high_freq_symbols:
                    if symbol in self.subscriptions:
                        self._update_market_data(symbol)
                
                # Maintain 1-second interval
                elapsed = time.time() - start_time
                sleep_time = max(0, HIGH_FREQUENCY_INTERVAL - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in high-frequency worker: {e}")
                time.sleep(HIGH_FREQUENCY_INTERVAL)
    
    def _low_frequency_worker(self) -> None:
        """Worker thread for low-frequency symbol updates."""
        while self.is_running:
            try:
                start_time = time.time()
                
                # Update low-frequency symbols
                for symbol in self.low_freq_symbols:
                    if symbol in self.subscriptions:
                        self._update_market_data(symbol)
                
                # Maintain 5-second interval
                elapsed = time.time() - start_time
                sleep_time = max(0, LOW_FREQUENCY_INTERVAL - elapsed)
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in low-frequency worker: {e}")
                time.sleep(LOW_FREQUENCY_INTERVAL)
    
    def _monitor_worker(self) -> None:
        """Worker thread for monitoring data quality and metrics."""
        while self.is_running:
            try:
                self._update_metrics()
                self._check_data_quality()
                self._handle_stale_data()
                
                time.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in monitor worker: {e}")
                time.sleep(10)
    
    # ==========================================================================
    # DATA PROCESSING
    # ==========================================================================
    
    def _update_market_data(self, symbol: str) -> None:
        """
        Update market data for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        try:
            req_id = self.subscriptions.get(symbol)
            if not req_id:
                return
            
            # Get ticker from client
            ticker = self.client.get_market_data(req_id)
            if not ticker:
                return
            
            # Create snapshot
            snapshot = self._create_snapshot(symbol, ticker)
            if not snapshot:
                return
            
            # Store data
            with self._data_lock:
                self.market_data[symbol] = snapshot
                self.data_history[symbol].append(snapshot)
                self._update_counts[symbol] += 1
            
            # Trigger callbacks
            self._trigger_callbacks(symbol, snapshot)
            
            # Emit event if available
            if self.event_manager:
                self.event_manager.emit(Event(
                    EventType.MARKET_DATA,
                    {'symbol': symbol, 'data': snapshot}
                ))
                
        except Exception as e:
            self.logger.error(f"Error updating market data for {symbol}: {e}")
    
    def _create_snapshot(self, symbol: str, ticker: Any) -> Optional[MarketDataSnapshot]:
        """
        Create market data snapshot from ticker.
        
        Args:
            symbol: Trading symbol
            ticker: IB ticker object
            
        Returns:
            MarketDataSnapshot or None
        """
        try:
            # Basic validation
            if not ticker or ticker.bid < 0 or ticker.ask < 0:
                return None
            
            # Create snapshot
            snapshot = MarketDataSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                bid=float(ticker.bid) if ticker.bid else 0.0,
                ask=float(ticker.ask) if ticker.ask else 0.0,
                last=float(ticker.last) if ticker.last else 0.0,
                bid_size=int(ticker.bidSize) if ticker.bidSize else 0,
                ask_size=int(ticker.askSize) if ticker.askSize else 0,
                last_size=int(ticker.lastSize) if ticker.lastSize else 0,
                volume=int(ticker.volume) if ticker.volume else 0,
                high=float(ticker.high) if ticker.high else 0.0,
                low=float(ticker.low) if ticker.low else 0.0,
                open=float(ticker.open) if ticker.open else 0.0,
                close=float(ticker.close) if ticker.close else 0.0,
                vwap=float(ticker.vwap) if hasattr(ticker, 'vwap') and ticker.vwap else 0.0
            )
            
            # Check data quality
            snapshot.quality = self._assess_data_quality(snapshot)
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error creating snapshot for {symbol}: {e}")
            return None
    
    def _assess_data_quality(self, snapshot: MarketDataSnapshot) -> DataQuality:
        """
        Assess data quality of snapshot.
        
        Args:
            snapshot: Market data snapshot
            
        Returns:
            DataQuality enum
        """
        # Check for invalid data
        if snapshot.bid <= 0 or snapshot.ask <= 0:
            return DataQuality.INVALID
        
        # Check spread
        if snapshot.spread > snapshot.mid_price * MAX_SPREAD_PERCENT:
            return DataQuality.INVALID
        
        # Check staleness
        age = (datetime.now() - snapshot.timestamp).total_seconds()
        if age > MAX_STALE_SECONDS:
            return DataQuality.STALE
        
        # Check if delayed (would need additional info from IB)
        # For now, assume good if passes other checks
        return DataQuality.GOOD
    
    # ==========================================================================
    # DATA QUALITY MONITORING
    # ==========================================================================
    
    def _check_data_quality(self) -> None:
        """Check data quality for all symbols."""
        with self._data_lock:
            now = datetime.now()
            
            for symbol, snapshot in self.market_data.items():
                age = (now - snapshot.timestamp).total_seconds()
                
                if age > MAX_STALE_SECONDS:
                    self.subscription_status[symbol] = MarketDataStatus.STALE
                    self.logger.warning(f"Stale data detected for {symbol} (age: {age:.1f}s)")
    
    def _handle_stale_data(self) -> None:
        """Handle stale data by attempting to resubscribe."""
        stale_symbols = []
        
        with self._lock:
            for symbol, status in self.subscription_status.items():
                if status == MarketDataStatus.STALE:
                    stale_symbols.append(symbol)
        
        # Attempt to resubscribe to stale symbols
        for symbol in stale_symbols:
            self.logger.info(f"Attempting to resubscribe to {symbol}")
            req_id = self.subscriptions.get(symbol)
            if req_id:
                self.client.cancel_market_data(req_id)
                del self.subscriptions[symbol]
                del self.req_id_to_symbol[req_id]
            
            # Resubscribe
            config = TRADING_SYMBOLS.get(symbol)
            if config:
                self._subscribe_symbol(symbol, config)
    
    def _update_metrics(self) -> None:
        """Update performance metrics."""
        with self._lock:
            # Count active subscriptions
            self.metrics.subscriptions_active = len(self.subscriptions)
            
            # Count stale subscriptions
            self.metrics.subscriptions_stale = sum(
                1 for status in self.subscription_status.values()
                if status == MarketDataStatus.STALE
            )
            
            # Count error subscriptions
            self.metrics.subscriptions_error = sum(
                1 for status in self.subscription_status.values()
                if status == MarketDataStatus.ERROR
            )
            
            # Calculate updates per second
            elapsed = (datetime.now() - self._last_update_time).total_seconds()
            if elapsed > 0:
                total_updates = sum(self._update_counts.values())
                self.metrics.updates_per_second = total_updates / elapsed
                
                # Reset counters
                self._update_counts.clear()
                self._last_update_time = datetime.now()
            
            self.metrics.last_update = datetime.now()
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def get_market_data(self, symbol: str) -> Optional[MarketDataSnapshot]:
        """
        Get current market data for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            MarketDataSnapshot or None
        """
        with self._data_lock:
            return self.market_data.get(symbol)
    
    def get_multiple_market_data(self, symbols: List[str]) -> Dict[str, MarketDataSnapshot]:
        """
        Get market data for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dict of symbol -> MarketDataSnapshot
        """
        with self._data_lock:
            return {
                symbol: self.market_data.get(symbol)
                for symbol in symbols
                if symbol in self.market_data
            }
    
    def get_all_market_data(self) -> Dict[str, MarketDataSnapshot]:
        """
        Get all available market data.
        
        Returns:
            Dict of all market data
        """
        with self._data_lock:
            return self.market_data.copy()
    
    def get_history(self, symbol: str, count: int = 100) -> List[MarketDataSnapshot]:
        """
        Get historical snapshots for symbol.
        
        Args:
            symbol: Trading symbol
            count: Number of snapshots to retrieve
            
        Returns:
            List of MarketDataSnapshot objects
        """
        with self._data_lock:
            history = self.data_history.get(symbol, deque())
            return list(history)[-count:]
    
    def subscribe_callback(self, symbol: str, callback: Callable) -> None:
        """
        Subscribe to market data updates for a symbol.
        
        Args:
            symbol: Trading symbol
            callback: Function to call with MarketDataSnapshot
        """
        self.callbacks[symbol].append(callback)
    
    def unsubscribe_callback(self, symbol: str, callback: Callable) -> None:
        """
        Unsubscribe from market data updates.
        
        Args:
            symbol: Trading symbol
            callback: Function to remove
        """
        if symbol in self.callbacks and callback in self.callbacks[symbol]:
            self.callbacks[symbol].remove(callback)
    
    def _trigger_callbacks(self, symbol: str, snapshot: MarketDataSnapshot) -> None:
        """Trigger callbacks for symbol update."""
        for callback in self.callbacks.get(symbol, []):
            try:
                callback(snapshot)
            except Exception as e:
                self.logger.error(f"Error in callback for {symbol}: {e}")
    
    def get_metrics(self) -> MarketDataMetrics:
        """
        Get current metrics.
        
        Returns:
            MarketDataMetrics object
        """
        return self.metrics
    
    def is_symbol_active(self, symbol: str) -> bool:
        """
        Check if symbol has active market data.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            bool: True if active
        """
        if symbol not in self.market_data:
            return False
        
        snapshot = self.market_data[symbol]
        age = (datetime.now() - snapshot.timestamp).total_seconds()
        return age < MAX_STALE_SECONDS
    
    def request_option_chain(self, 
                           underlying: str,
                           expiry: str,
                           strikes: Optional[List[float]] = None) -> bool:
        """
        Request market data for option chain.
        
        Args:
            underlying: Underlying symbol (e.g., 'SPY')
            expiry: Expiration date (YYYYMMDD)
            strikes: Optional list of strikes to subscribe
            
        Returns:
            bool: True if requests submitted
        """
        # This would be implemented to handle option chain subscriptions
        # For now, it's a placeholder for the interface
        self.logger.info(f"Option chain request for {underlying} {expiry}")
        return True

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level instance
_manager_instance: Optional[MarketDataManager] = None
_manager_lock = threading.Lock()

def get_market_data_manager(client: Optional[SpyderClient] = None,
                          event_manager: Optional[EventManager] = None) -> MarketDataManager:
    """
    Get or create the market data manager instance.
    
    Args:
        client: SpyderClient instance (required on first call)
        event_manager: Optional event manager
        
    Returns:
        MarketDataManager instance
    """
    global _manager_instance
    
    with _manager_lock:
        if _manager_instance is None:
            if client is None:
                raise ValueError("SpyderClient required for first initialization")
            _manager_instance = MarketDataManager(client, event_manager)
        return _manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage
    import logging
    from SpyderB_Broker.SpyderB01_SpyderClient import IBConfig
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create IB client
    config = IBConfig(
        host='127.0.0.1',
        port=4002,  # Paper trading
        client_id=1
    )
    
    client = SpyderClient(config)
    
    if client.connect():
        print("✅ Connected to Interactive Brokers")
        
        # Create market data manager
        manager = MarketDataManager(client)
        
        # Example callback
        def on_spy_update(snapshot: MarketDataSnapshot):
            print(f"SPY Update: Bid={snapshot.bid:.2f}, Ask={snapshot.ask:.2f}, "
                  f"Last={snapshot.last:.2f}, Volume={snapshot.volume:,}")
        
        # Subscribe to SPY updates
        manager.subscribe_callback('SPY', on_spy_update)
        
        # Start manager
        if manager.start():
            print("✅ Market Data Manager started")
            
            # Let it run for a bit
            time.sleep(30)
            
            # Get current data
            spy_data = manager.get_market_data('SPY')
            if spy_data:
                print(f"\nCurrent SPY: {spy_data.last:.2f} "
                      f"({spy_data.bid:.2f} x {spy_data.ask:.2f})")
            
            # Get metrics
            metrics = manager.get_metrics()
            print(f"\nMetrics:")
            print(f"  Active subscriptions: {metrics.subscriptions_active}")
            print(f"  Updates/second: {metrics.updates_per_second:.1f}")
            
            # Stop manager
            manager.stop()
            print("\n✅ Market Data Manager stopped")
        
        # Disconnect
        client.disconnect()
        print("✅ Disconnected from Interactive Brokers")
    else:
        print("❌ Failed to connect to Interactive Brokers")
