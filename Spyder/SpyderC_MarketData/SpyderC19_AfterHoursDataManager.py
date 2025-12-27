#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC19_AfterHoursDataManager.py
Purpose: After-hours market data management and closing price snapshots
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 16:45:00  

Module Description:
    Specialized manager for after-hours market data handling. Provides closing price
    snapshots, after-hours trading data, and proper data management when markets are
    closed. Ensures portfolio valuations and risk calculations have access to last
    known good prices. Integrates with enhanced SpyderClient for optimal data types.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import time
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, time as dt_time, timedelta
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU22_ETTimeDisplay import ETTimeDisplay, MarketStatus

# Import broker components if available
try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, MarketDataType
    from SpyderB_Broker.SpyderB07_MarketDataManager import MarketDataSnapshot
    BROKER_AVAILABLE = True
except ImportError:
    BROKER_AVAILABLE = False
    # Mock classes for testing
    class SpyderClient: pass
    class MarketDataSnapshot: pass

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Data freshness limits
MAX_CLOSING_DATA_AGE_HOURS = 72  # Consider closing data stale after 3 days
MAX_SNAPSHOT_CACHE_MINUTES = 15  # Cache snapshots for 15 minutes
DEFAULT_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2

# After-hours trading sessions
AFTER_HOURS_START = dt_time(16, 0, 0)   # 4:00 PM ET
AFTER_HOURS_END = dt_time(20, 0, 0)     # 8:00 PM ET
PRE_MARKET_START = dt_time(4, 0, 0)     # 4:00 AM ET
PRE_MARKET_END = dt_time(9, 30, 0)      # 9:30 AM ET

# File paths for persistence
CLOSING_PRICES_FILE = "/tmp/spyder_closing_prices.json"
AFTER_HOURS_CACHE_FILE = "/tmp/spyder_after_hours_cache.json"

# Data quality thresholds
MIN_PRICE_THRESHOLD = 0.01  # Minimum valid price
MAX_SPREAD_PERCENTAGE = 10.0  # Maximum spread as % of mid price

# ==============================================================================
# ENUMS
# ==============================================================================
class AfterHoursSession(Enum):
    """After-hours trading session types"""
    PRE_MARKET = "pre_market"
    REGULAR_HOURS = "regular_hours"
    AFTER_HOURS = "after_hours"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"
    CLOSED = "closed"

class DataSource(Enum):
    """Source of market data"""
    LIVE_FEED = "live_feed"
    CACHED_SNAPSHOT = "cached_snapshot"
    CLOSING_PRICES = "closing_prices"
    FALLBACK_DATA = "fallback_data"

class DataFreshness(Enum):
    """Data freshness indicators"""
    FRESH = "fresh"          # Real-time or very recent
    RECENT = "recent"        # Within acceptable limits
    STALE = "stale"          # Old but usable
    EXPIRED = "expired"      # Too old to be reliable

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ClosingSnapshot:
    """Snapshot of closing market data"""
    symbol: str
    closing_price: float
    closing_bid: float
    closing_ask: float
    closing_volume: int
    closing_time: datetime
    previous_close: float
    trading_date: str  # YYYY-MM-DD format
    source: DataSource
    data_freshness: DataFreshness
    
    # Additional closing data
    day_high: float = 0.0
    day_low: float = 0.0
    day_change: float = 0.0
    day_change_percent: float = 0.0
    
    def __post_init__(self):
        """Calculate derived fields"""
        if self.closing_price > 0 and self.previous_close > 0:
            self.day_change = self.closing_price - self.previous_close
            self.day_change_percent = (self.day_change / self.previous_close) * 100

@dataclass
class AfterHoursData:
    """After-hours trading data"""
    symbol: str
    last_price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    session: AfterHoursSession
    
    # Reference to closing data
    closing_reference: Optional[ClosingSnapshot] = None
    
    # Calculated fields
    change_from_close: float = 0.0
    change_percent_from_close: float = 0.0
    
    def __post_init__(self):
        """Calculate after-hours changes"""
        if self.closing_reference and self.last_price > 0:
            self.change_from_close = self.last_price - self.closing_reference.closing_price
            if self.closing_reference.closing_price > 0:
                self.change_percent_from_close = (self.change_from_close / 
                                                self.closing_reference.closing_price) * 100

@dataclass
class AfterHoursMetrics:
    """Metrics for after-hours data management"""
    total_symbols_tracked: int = 0
    closing_snapshots_available: int = 0
    live_after_hours_feeds: int = 0
    cached_data_age_minutes: float = 0.0
    data_quality_score: float = 0.0
    last_update: Optional[datetime] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AfterHoursDataManager:
    """
    After-hours market data manager.
    
    This class specializes in handling market data when regular trading hours
    are closed. It provides access to closing price snapshots, manages after-hours
    trading data, and ensures portfolio valuations have access to the most recent
    reliable price data. Works with the enhanced SpyderClient to use optimal
    data types for after-hours scenarios.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        client: Enhanced SpyderClient instance
        et_display: ET time display helper
        closing_snapshots: Dictionary of closing price snapshots
        after_hours_data: Dictionary of after-hours trading data
        
    Example:
        >>> manager = AfterHoursDataManager(spyder_client)
        >>> closing_data = manager.get_closing_snapshot('SPY')
        >>> after_hours = manager.get_after_hours_data('SPY')
        >>> is_available = manager.is_closing_data_available('SPY')
    """
    
    def __init__(self, client: Optional[SpyderClient] = None):
        """
        Initialize after-hours data manager.
        
        Args:
            client: Optional SpyderClient instance
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Core components
        self.client = client
        self.et_display = ETTimeDisplay()
        
        # Data storage
        self.closing_snapshots: Dict[str, ClosingSnapshot] = {}
        self.after_hours_data: Dict[str, AfterHoursData] = {}
        self.symbol_configs: Dict[str, Dict[str, Any]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # State management
        self.is_running = False
        self.last_market_check: Optional[datetime] = None
        self.current_session: Optional[AfterHoursSession] = None
        
        # Load persistent data
        self._load_closing_prices()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the after-hours data manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            with self._lock:
                if self.is_running:
                    self.logger.warning("After-hours manager already running")
                    return True
                
                # Determine current session
                self.current_session = self._get_current_session()
                self.logger.info(f"Current session: {self.current_session.value}")
                
                # Initialize data based on session
                if self.current_session in [AfterHoursSession.AFTER_HOURS, 
                                          AfterHoursSession.PRE_MARKET]:
                    self._setup_after_hours_feeds()
                elif self.current_session in [AfterHoursSession.WEEKEND, 
                                            AfterHoursSession.HOLIDAY, 
                                            AfterHoursSession.CLOSED]:
                    self._prepare_closing_data()
                
                self.is_running = True
                self.logger.info("After-hours data manager started")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to start after-hours manager: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the after-hours data manager."""
        try:
            with self._lock:
                if not self.is_running:
                    return
                
                # Save closing prices
                self._save_closing_prices()
                
                # Stop any active feeds
                self._stop_after_hours_feeds()
                
                self.is_running = False
                self.logger.info("After-hours data manager stopped")
                
        except Exception as e:
            self.logger.error(f"Error stopping after-hours manager: {e}")
    
    # ==========================================================================
    # PUBLIC METHODS - CLOSING DATA ACCESS
    # ==========================================================================
    def get_closing_snapshot(self, symbol: str) -> Optional[ClosingSnapshot]:
        """
        Get closing price snapshot for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            ClosingSnapshot or None if not available
        """
        with self._lock:
            snapshot = self.closing_snapshots.get(symbol)
            
            if snapshot:
                # Check data freshness
                age_hours = (datetime.now() - snapshot.closing_time).total_seconds() / 3600
                
                if age_hours > MAX_CLOSING_DATA_AGE_HOURS:
                    snapshot.data_freshness = DataFreshness.EXPIRED
                elif age_hours > 24:
                    snapshot.data_freshness = DataFreshness.STALE
                elif age_hours > 1:
                    snapshot.data_freshness = DataFreshness.RECENT
                else:
                    snapshot.data_freshness = DataFreshness.FRESH
            
            return snapshot
    
    def get_after_hours_data(self, symbol: str) -> Optional[AfterHoursData]:
        """
        Get after-hours trading data for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            AfterHoursData or None if not available
        """
        with self._lock:
            return self.after_hours_data.get(symbol)
    
    def is_closing_data_available(self, symbol: str) -> bool:
        """
        Check if closing data is available and fresh for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            bool: True if usable closing data is available
        """
        snapshot = self.get_closing_snapshot(symbol)
        if not snapshot:
            return False
        
        return snapshot.data_freshness in [DataFreshness.FRESH, 
                                         DataFreshness.RECENT, 
                                         DataFreshness.STALE]
    
    def request_closing_snapshot(self, symbol: str, force_refresh: bool = False) -> bool:
        """
        Request closing snapshot data for a symbol.
        
        Args:
            symbol: Trading symbol
            force_refresh: Force refresh even if cached data exists
            
        Returns:
            bool: True if request successful
        """
        try:
            # Check if we already have fresh data
            if not force_refresh and self.is_closing_data_available(symbol):
                return True
            
            if not self.client or not self.client.is_connected():
                self.logger.warning("No connected client for closing data request")
                return False
            
            # Use FROZEN data type for best closing data
            original_type = self.client.current_data_type
            if original_type != MarketDataType.FROZEN:
                self.client.set_market_data_type(MarketDataType.FROZEN)
            
            # Request market data snapshot
            contract = self.client.create_stock_contract(symbol)
            req_id = self.client.request_market_data(contract)
            
            if req_id > 0:
                # Wait for data
                time.sleep(3)
                
                # Get ticker data
                ticker = self.client.get_market_data(req_id)
                if ticker and ticker.last and ticker.last > MIN_PRICE_THRESHOLD:
                    
                    # Create closing snapshot
                    snapshot = ClosingSnapshot(
                        symbol=symbol,
                        closing_price=ticker.last,
                        closing_bid=ticker.bid if ticker.bid else 0.0,
                        closing_ask=ticker.ask if ticker.ask else 0.0,
                        closing_volume=int(ticker.volume) if ticker.volume else 0,
                        closing_time=datetime.now(),
                        previous_close=ticker.close if ticker.close else ticker.last,
                        trading_date=datetime.now().strftime('%Y-%m-%d'),
                        source=DataSource.LIVE_FEED,
                        data_freshness=DataFreshness.FRESH,
                        day_high=ticker.high if ticker.high else 0.0,
                        day_low=ticker.low if ticker.low else 0.0
                    )
                    
                    with self._lock:
                        self.closing_snapshots[symbol] = snapshot
                    
                    self.logger.info(f"✅ Closing snapshot for {symbol}: ${snapshot.closing_price:.2f}")
                    
                    # Cancel market data
                    self.client.cancel_market_data(req_id)
                    
                    # Restore original data type
                    if original_type != MarketDataType.FROZEN:
                        self.client.set_market_data_type(original_type)
                    
                    return True
                else:
                    self.logger.warning(f"No valid closing data received for {symbol}")
                
                # Cancel market data
                self.client.cancel_market_data(req_id)
            
            # Restore original data type
            if original_type != MarketDataType.FROZEN:
                self.client.set_market_data_type(original_type)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error requesting closing snapshot for {symbol}: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - BULK OPERATIONS
    # ==========================================================================
    def request_closing_snapshots(self, symbols: List[str], 
                                max_concurrent: int = 5) -> Dict[str, bool]:
        """
        Request closing snapshots for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dict[str, bool]: Success status per symbol
        """
        results = {}
        
        # Process in batches
        for i in range(0, len(symbols), max_concurrent):
            batch = symbols[i:i + max_concurrent]
            
            for symbol in batch:
                try:
                    results[symbol] = self.request_closing_snapshot(symbol)
                    time.sleep(0.5)  # Small delay between requests
                except Exception as e:
                    self.logger.error(f"Error requesting {symbol}: {e}")
                    results[symbol] = False
        
        return results
    
    def get_portfolio_closing_values(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get closing values for a portfolio of symbols.
        
        Args:
            symbols: List of symbols in portfolio
            
        Returns:
            Dict[str, float]: Symbol to closing price mapping
        """
        values = {}
        
        for symbol in symbols:
            snapshot = self.get_closing_snapshot(symbol)
            if snapshot and snapshot.data_freshness != DataFreshness.EXPIRED:
                values[symbol] = snapshot.closing_price
            else:
                self.logger.warning(f"No valid closing price for {symbol}")
                values[symbol] = 0.0
        
        return values
    
    # ==========================================================================
    # PUBLIC METHODS - SESSION MANAGEMENT
    # ==========================================================================
    def get_current_session(self) -> AfterHoursSession:
        """
        Get current trading session.
        
        Returns:
            AfterHoursSession: Current session type
        """
        return self._get_current_session()
    
    def is_after_hours_active(self) -> bool:
        """
        Check if after-hours trading is currently active.
        
        Returns:
            bool: True if after-hours trading is active
        """
        session = self.get_current_session()
        return session in [AfterHoursSession.PRE_MARKET, AfterHoursSession.AFTER_HOURS]
    
    def is_market_closed(self) -> bool:
        """
        Check if market is completely closed.
        
        Returns:
            bool: True if market is closed (no trading)
        """
        session = self.get_current_session()
        return session in [AfterHoursSession.WEEKEND, AfterHoursSession.HOLIDAY, 
                          AfterHoursSession.CLOSED]
    
    # ==========================================================================
    # PUBLIC METHODS - METRICS AND STATUS
    # ==========================================================================
    def get_metrics(self) -> AfterHoursMetrics:
        """
        Get comprehensive metrics for after-hours data management.
        
        Returns:
            AfterHoursMetrics: Current metrics
        """
        with self._lock:
            # Calculate data quality score
            total_symbols = len(self.closing_snapshots)
            fresh_data = sum(1 for s in self.closing_snapshots.values() 
                           if s.data_freshness in [DataFreshness.FRESH, DataFreshness.RECENT])
            
            quality_score = (fresh_data / total_symbols * 100) if total_symbols > 0 else 0
            
            # Calculate average cache age
            if self.closing_snapshots:
                ages = [(datetime.now() - s.closing_time).total_seconds() / 60 
                       for s in self.closing_snapshots.values()]
                avg_age = sum(ages) / len(ages)
            else:
                avg_age = 0.0
            
            return AfterHoursMetrics(
                total_symbols_tracked=total_symbols,
                closing_snapshots_available=len(self.closing_snapshots),
                live_after_hours_feeds=len(self.after_hours_data),
                cached_data_age_minutes=avg_age,
                data_quality_score=quality_score,
                last_update=datetime.now()
            )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of after-hours data manager.
        
        Returns:
            Dict[str, Any]: Status information
        """
        metrics = self.get_metrics()
        session = self.get_current_session()
        
        return {
            'is_running': self.is_running,
            'current_session': session.value,
            'symbols_tracked': metrics.total_symbols_tracked,
            'closing_snapshots': metrics.closing_snapshots_available,
            'after_hours_feeds': metrics.live_after_hours_feeds,
            'data_quality_score': metrics.data_quality_score,
            'cache_age_minutes': metrics.cached_data_age_minutes,
            'client_connected': self.client.is_connected() if self.client else False,
            'last_update': metrics.last_update.isoformat() if metrics.last_update else None
        }
    
    # ==========================================================================
    # PRIVATE METHODS - SESSION DETECTION
    # ==========================================================================
    def _get_current_session(self) -> AfterHoursSession:
        """Determine current trading session based on ET time."""
        try:
            et_time = self.et_display.get_et_time()
            current_time = et_time.time()
            weekday = et_time.weekday()  # 0=Monday, 6=Sunday
            
            # Weekend check
            if weekday >= 5:  # Saturday or Sunday
                return AfterHoursSession.WEEKEND
            
            # Holiday check (simplified - could be enhanced with holiday calendar)
            # if self._is_market_holiday(et_time.date()):
            #     return AfterHoursSession.HOLIDAY
            
            # Weekday session detection
            if PRE_MARKET_START <= current_time < PRE_MARKET_END:
                return AfterHoursSession.PRE_MARKET
            elif PRE_MARKET_END <= current_time < AFTER_HOURS_START:
                return AfterHoursSession.REGULAR_HOURS
            elif AFTER_HOURS_START <= current_time < AFTER_HOURS_END:
                return AfterHoursSession.AFTER_HOURS
            else:
                return AfterHoursSession.CLOSED
                
        except Exception as e:
            self.logger.error(f"Error determining session: {e}")
            return AfterHoursSession.CLOSED
    
    # ==========================================================================
    # PRIVATE METHODS - DATA MANAGEMENT
    # ==========================================================================
    def _setup_after_hours_feeds(self) -> None:
        """Setup data feeds for after-hours trading."""
        try:
            self.logger.info("Setting up after-hours data feeds")
            
            # For after-hours, we want to track symbols that might be actively trading
            # This could be enhanced to include symbols from active positions
            
        except Exception as e:
            self.logger.error(f"Error setting up after-hours feeds: {e}")
    
    def _prepare_closing_data(self) -> None:
        """Prepare closing data for non-trading periods."""
        try:
            self.logger.info("Preparing closing data for market closed period")
            
            # Load any cached closing prices
            self._load_closing_prices()
            
            # Validate data freshness
            expired_symbols = []
            for symbol, snapshot in self.closing_snapshots.items():
                age_hours = (datetime.now() - snapshot.closing_time).total_seconds() / 3600
                if age_hours > MAX_CLOSING_DATA_AGE_HOURS:
                    expired_symbols.append(symbol)
            
            if expired_symbols:
                self.logger.warning(f"Expired closing data for symbols: {expired_symbols}")
            
        except Exception as e:
            self.logger.error(f"Error preparing closing data: {e}")
    
    def _stop_after_hours_feeds(self) -> None:
        """Stop any active after-hours feeds."""
        try:
            with self._lock:
                self.after_hours_data.clear()
                
        except Exception as e:
            self.logger.error(f"Error stopping after-hours feeds: {e}")
    
    # ==========================================================================
    # PRIVATE METHODS - PERSISTENCE
    # ==========================================================================
    def _load_closing_prices(self) -> None:
        """Load closing prices from persistent storage."""
        try:
            if os.path.exists(CLOSING_PRICES_FILE):
                with open(CLOSING_PRICES_FILE, 'r') as f:
                    data = json.load(f)
                
                with self._lock:
                    for symbol, snapshot_data in data.items():
                        try:
                            # Convert back to ClosingSnapshot
                            snapshot = ClosingSnapshot(
                                symbol=snapshot_data['symbol'],
                                closing_price=snapshot_data['closing_price'],
                                closing_bid=snapshot_data['closing_bid'],
                                closing_ask=snapshot_data['closing_ask'],
                                closing_volume=snapshot_data['closing_volume'],
                                closing_time=datetime.fromisoformat(snapshot_data['closing_time']),
                                previous_close=snapshot_data['previous_close'],
                                trading_date=snapshot_data['trading_date'],
                                source=DataSource[snapshot_data['source']],
                                data_freshness=DataFreshness.STALE,  # Mark as stale initially
                                day_high=snapshot_data.get('day_high', 0.0),
                                day_low=snapshot_data.get('day_low', 0.0)
                            )
                            
                            self.closing_snapshots[symbol] = snapshot
                            
                        except Exception as e:
                            self.logger.warning(f"Error loading snapshot for {symbol}: {e}")
                
                self.logger.info(f"Loaded {len(self.closing_snapshots)} closing price snapshots")
            
        except Exception as e:
            self.logger.error(f"Error loading closing prices: {e}")
    
    def _save_closing_prices(self) -> None:
        """Save closing prices to persistent storage."""
        try:
            with self._lock:
                data = {}
                for symbol, snapshot in self.closing_snapshots.items():
                    data[symbol] = {
                        'symbol': snapshot.symbol,
                        'closing_price': snapshot.closing_price,
                        'closing_bid': snapshot.closing_bid,
                        'closing_ask': snapshot.closing_ask,
                        'closing_volume': snapshot.closing_volume,
                        'closing_time': snapshot.closing_time.isoformat(),
                        'previous_close': snapshot.previous_close,
                        'trading_date': snapshot.trading_date,
                        'source': snapshot.source.name,
                        'day_high': snapshot.day_high,
                        'day_low': snapshot.day_low
                    }
            
            with open(CLOSING_PRICES_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(data)} closing price snapshots")
            
        except Exception as e:
            self.logger.error(f"Error saving closing prices: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_after_hours_manager(client: Optional[SpyderClient] = None) -> AfterHoursDataManager:
    """
    Factory function to create after-hours data manager.
    
    Args:
        client: Optional SpyderClient instance
        
    Returns:
        AfterHoursDataManager: Configured instance
    """
    return AfterHoursDataManager(client)

def is_market_closed_now() -> bool:
    """
    Quick function to check if market is currently closed.
    
    Returns:
        bool: True if market is closed
    """
    manager = AfterHoursDataManager()
    return manager.is_market_closed()

def get_current_trading_session() -> str:
    """
    Quick function to get current trading session.
    
    Returns:
        str: Current session name
    """
    manager = AfterHoursDataManager()
    return manager.get_current_session().value

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance for singleton pattern
_after_hours_manager_instance: Optional[AfterHoursDataManager] = None
_instance_lock = threading.Lock()

def get_shared_after_hours_manager(client: Optional[SpyderClient] = None) -> AfterHoursDataManager:
    """
    Get shared after-hours manager instance (singleton).
    
    Args:
        client: Optional SpyderClient instance
        
    Returns:
        AfterHoursDataManager: Shared instance
    """
    global _after_hours_manager_instance
    
    if _after_hours_manager_instance is None:
        with _instance_lock:
            if _after_hours_manager_instance is None:
                _after_hours_manager_instance = AfterHoursDataManager(client)
    
    return _after_hours_manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER C19 - After-Hours Data Manager Test")
    print("=" * 80)
    
    # Create manager
    manager = AfterHoursDataManager()
    
    print("\n1. Session Detection:")
    session = manager.get_current_session()
    print(f"   Current Session: {session.value}")
    print(f"   Is After-Hours Active: {manager.is_after_hours_active()}")
    print(f"   Is Market Closed: {manager.is_market_closed()}")
    
    print("\n2. Quick Functions:")
    print(f"   Market Closed Now: {is_market_closed_now()}")
    print(f"   Current Session: {get_current_trading_session()}")
    
    print("\n3. Manager Status:")
    if manager.start():
        status = manager.get_status()
        for key, value in status.items():
            print(f"   {key}: {value}")
        
        metrics = manager.get_metrics()
        print(f"\n4. Metrics:")
        print(f"   Data Quality Score: {metrics.data_quality_score:.1f}%")
        print(f"   Cache Age: {metrics.cached_data_age_minutes:.1f} minutes")
        
        manager.stop()
    
    print("\n5. Simulated Closing Data Test:")
    # Test closing snapshot creation (without actual client)
    test_snapshot = ClosingSnapshot(
        symbol="SPY",
        closing_price=450.25,
        closing_bid=450.20,
        closing_ask=450.30,
        closing_volume=1000000,
        closing_time=datetime.now(),
        previous_close=449.50,
        trading_date=datetime.now().strftime('%Y-%m-%d'),
        source=DataSource.CACHED_SNAPSHOT,
        data_freshness=DataFreshness.FRESH,
        day_high=451.00,
        day_low=448.75
    )
    
    print(f"   Test Snapshot: {test_snapshot.symbol} @ ${test_snapshot.closing_price:.2f}")
    print(f"   Day Change: ${test_snapshot.day_change:.2f} ({test_snapshot.day_change_percent:+.2f}%)")
    
    print("\n" + "=" * 80)
    print("✅ After-Hours Data Manager test completed!")
    print("🌙 Ready to provide closing data when markets are closed!")
