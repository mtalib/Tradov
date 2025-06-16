#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderC08_SPYFeed.py
Group: C (Market Data)
Purpose: AMEX/ARCA (Network B) real-time SPY ETF data feed

Description:
This module provides high-quality real-time market data for the SPY ETF from
AMEX/ARCA (Network B). It handles Level 2 market data, tick-by-tick price updates,
volume analysis, and market internals for precise options trading entries. The
module integrates with the OPRA options feed to provide comprehensive underlying
and derivatives data for the Spyder trading system.

Author: Mohamed Talib
Created: 2025-06-09
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics

# =============================================================================
# Third-Party Imports
# =============================================================================
import pandas as pd
import numpy as np
from ib_insync import *
import pytz

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError
from SpyderU_Utilities.SpyderU03_DateTimeUtils import MarketTimeUtils
from SpyderU_Utilities.SpyderU07_Constants import TRADING_CONSTANTS
from SpyderC_MarketData.SpyderC06_DataValidator import DataValidator

# =============================================================================
# Constants
# =============================================================================
SPY_SYMBOL = "SPY"
DEFAULT_EXCHANGE = "ARCA"  # AMEX/ARCA Network B
BACKUP_EXCHANGES = ["SMART", "AMEX", "NYSE"]
DEFAULT_UPDATE_INTERVAL = 50  # milliseconds for tick data
TICK_BUFFER_SIZE = 10000
VOLUME_ANALYSIS_WINDOW = 100  # ticks
PRICE_LEVEL_DEPTH = 10  # Level 2 depth
SPY_FEED_ID = "SPY_FEED"

# Market microstructure constants
MIN_TICK_SIZE = 0.01
LARGE_TRADE_THRESHOLD = 10000  # shares
BLOCK_TRADE_THRESHOLD = 50000  # shares
VWAP_WINDOW = 20  # minutes

# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class SPYTick:
    """Individual SPY tick data structure."""
    
    price: float
    size: int
    timestamp: datetime
    tick_type: str  # 'BID', 'ASK', 'TRADE'
    exchange: str
    conditions: List[str] = field(default_factory=list)
    
    @property
    def value(self) -> float:
        """Calculate tick value (price * size)."""
        return self.price * self.size


@dataclass
class SPYQuote:
    """SPY bid/ask quote data."""
    
    symbol: str
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    last_size: int
    volume: int
    high: float
    low: float
    open: float
    close: float
    timestamp: datetime
    exchange: str
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points."""
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 10000
        return 0.0


@dataclass
class MarketDepth:
    """Level 2 market depth data."""
    
    symbol: str
    bids: List[Tuple[float, int]] = field(default_factory=list)  # (price, size) pairs
    asks: List[Tuple[float, int]] = field(default_factory=list)  # (price, size) pairs
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def best_bid(self) -> Optional[Tuple[float, int]]:
        """Get best bid price and size."""
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[Tuple[float, int]]:
        """Get best ask price and size."""
        return self.asks[0] if self.asks else None
    
    @property
    def total_bid_size(self) -> int:
        """Total size on bid side."""
        return sum(size for _, size in self.bids)
    
    @property
    def total_ask_size(self) -> int:
        """Total size on ask side."""
        return sum(size for _, size in self.asks)


@dataclass
class VolumeProfile:
    """Volume profile analysis."""
    
    symbol: str
    price_levels: Dict[float, int] = field(default_factory=dict)  # price -> volume
    vwap: float = 0.0
    total_volume: int = 0
    average_trade_size: float = 0.0
    large_trades_count: int = 0
    block_trades_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_volume_at_price(self, price: float) -> int:
        """Get volume traded at specific price level."""
        # Round to nearest cent for SPY
        rounded_price = round(price, 2)
        return self.price_levels.get(rounded_price, 0)
    
    def get_peak_volume_price(self) -> float:
        """Get price level with highest volume."""
        if not self.price_levels:
            return 0.0
        return max(self.price_levels.items(), key=lambda x: x[1])[0]


# =============================================================================
# Main SPY Feed Class
# =============================================================================
class SPYFeed:
    """
    AMEX/ARCA (Network B) real-time SPY ETF data feed handler.
    
    This class provides comprehensive real-time market data for SPY including:
    - Tick-by-tick price and volume data
    - Level 2 market depth (DOM)
    - Volume profile analysis
    - VWAP calculations
    - Market microstructure metrics
    - Trade classification and analysis
    
    Attributes:
        symbol (str): SPY symbol
        ib_client (IB): Interactive Brokers client connection
        is_running (bool): Feed running state
        data_callbacks (Dict): Registered data callbacks
        current_quote (SPYQuote): Latest quote data
        tick_buffer (deque): Historical tick data
        market_depth (MarketDepth): Current Level 2 data
        volume_profile (VolumeProfile): Volume analysis
        logger (SpyderLogger): Application logger
        error_handler (SpyderErrorHandler): Error handler
        data_validator (DataValidator): Data validation
        update_thread (threading.Thread): Data update thread
        market_time_utils (MarketTimeUtils): Market time utilities
    """
    
    def __init__(self, ib_client: IB, symbol: str = SPY_SYMBOL):
        """
        Initialize the SPY feed handler.
        
        Args:
            ib_client: Interactive Brokers client connection
            symbol: Symbol to track (default: SPY)
        """
        self.symbol = symbol.upper()
        self.ib_client = ib_client
        self.is_running = False
        
        # Data storage
        self.data_callbacks: Dict[str, Callable] = {}
        self.current_quote: Optional[SPYQuote] = None
        self.tick_buffer: deque = deque(maxlen=TICK_BUFFER_SIZE)
        self.market_depth: Optional[MarketDepth] = None
        self.volume_profile: Optional[VolumeProfile] = None
        
        # Market data subscriptions
        self.ticker: Optional[Ticker] = None
        self.depth_ticker: Optional[Ticker] = None
        
        # Analytics
        self.vwap_calculator = VWAPCalculator()
        self.trade_classifier = TradeClassifier()
        
        # Threading
        self.update_thread: Optional[threading.Thread] = None
        self.data_lock = threading.RLock()
        
        # Utilities
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.data_validator = DataValidator()
        self.market_time_utils = MarketTimeUtils()
        
        self.logger.info(f"SPY Feed initialized for {self.symbol}")
    
    def start(self) -> bool:
        """
        Start the SPY data feed.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            if self.is_running:
                self.logger.warning("SPY feed is already running")
                return True
            
            if not self.ib_client.isConnected():
                raise TradingError("IB client not connected - cannot start SPY feed")
            
            self.logger.info(f"🚀 Starting SPY feed for {self.symbol}")
            self.is_running = True
            
            # Initialize data structures
            self.volume_profile = VolumeProfile(symbol=self.symbol)
            self.market_depth = MarketDepth(symbol=self.symbol)
            
            # Subscribe to market data
            success = self._subscribe_to_market_data()
            if not success:
                self.is_running = False
                return False
            
            # Start data processing thread
            self.update_thread = threading.Thread(target=self._data_processing_loop, daemon=True)
            self.update_thread.start()
            
            self.logger.info(f"✅ SPY feed started successfully for {self.symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start SPY feed: {e}")
            self.error_handler.handle_error(e, context="SPY Feed Start")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop the SPY data feed."""
        try:
            if not self.is_running:
                self.logger.info("SPY feed is already stopped")
                return
            
            self.logger.info(f"🛑 Stopping SPY feed for {self.symbol}")
            self.is_running = False
            
            # Cancel subscriptions
            self._cancel_subscriptions()
            
            # Wait for processing thread to finish
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=5.0)
            
            self.logger.info(f"✅ SPY feed stopped for {self.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error stopping SPY feed: {e}")
            self.error_handler.handle_error(e, context="SPY Feed Stop")
    
    def register_callback(self, callback_name: str, callback_func: Callable):
        """
        Register a callback for data updates.
        
        Args:
            callback_name: Unique name for the callback
            callback_func: Function to call with data updates
        """
        with self.data_lock:
            self.data_callbacks[callback_name] = callback_func
            self.logger.info(f"Registered callback: {callback_name}")
    
    def unregister_callback(self, callback_name: str):
        """
        Unregister a data callback.
        
        Args:
            callback_name: Name of callback to remove
        """
        with self.data_lock:
            if callback_name in self.data_callbacks:
                del self.data_callbacks[callback_name]
                self.logger.info(f"Unregistered callback: {callback_name}")
    
    def get_current_price(self) -> float:
        """
        Get current SPY price.
        
        Returns:
            Current price or 0.0 if not available
        """
        with self.data_lock:
            if self.current_quote:
                return self.current_quote.last if self.current_quote.last > 0 else self.current_quote.mid_price
            return 0.0
    
    def get_current_quote(self) -> Optional[SPYQuote]:
        """
        Get current SPY quote.
        
        Returns:
            Current quote or None if not available
        """
        with self.data_lock:
            return self.current_quote
    
    def get_market_depth(self) -> Optional[MarketDepth]:
        """
        Get current Level 2 market depth.
        
        Returns:
            Market depth data or None if not available
        """
        with self.data_lock:
            return self.market_depth
    
    def get_volume_profile(self) -> Optional[VolumeProfile]:
        """
        Get current volume profile analysis.
        
        Returns:
            Volume profile or None if not available
        """
        with self.data_lock:
            return self.volume_profile
    
    def get_vwap(self) -> float:
        """
        Get current Volume Weighted Average Price.
        
        Returns:
            VWAP value or 0.0 if not available
        """
        return self.vwap_calculator.get_current_vwap()
    
    def get_recent_ticks(self, count: int = 100) -> List[SPYTick]:
        """
        Get recent tick data.
        
        Args:
            count: Number of recent ticks to return
            
        Returns:
            List of recent ticks
        """
        with self.data_lock:
            return list(self.tick_buffer)[-count:] if self.tick_buffer else []
    
    def _subscribe_to_market_data(self) -> bool:
        """Subscribe to SPY market data."""
        try:
            # Create SPY contract
            spy_contract = Stock(self.symbol, DEFAULT_EXCHANGE, 'USD')
            self.ib_client.qualifyContracts(spy_contract)
            
            # Subscribe to tick data
            self.ticker = self.ib_client.reqMktData(
                spy_contract,
                '100,101,104,105,106,165,221,225,233,236,258',  # Comprehensive tick types
                False,  # snapshot
                False   # regulatory snapshot
            )
            
            # Subscribe to Level 2 data
            self.depth_ticker = self.ib_client.reqMktDepth(
                spy_contract,
                PRICE_LEVEL_DEPTH,
                True  # isSmartDepth
            )
            
            # Set up event handlers
            self.ticker.updateEvent += self._on_tick_data
            self.depth_ticker.updateEvent += self._on_depth_data
            
            self.logger.info(f"Subscribed to {self.symbol} market data on {DEFAULT_EXCHANGE}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error subscribing to market data: {e}")
            return False
    
    def _on_tick_data(self, ticker):
        """Handle tick data updates."""
        try:
            if not self.is_running:
                return
            
            # Create SPY quote from ticker
            quote = self._create_spy_quote(ticker)
            if quote and self.data_validator.validate_spy_quote(quote):
                
                with self.data_lock:
                    self.current_quote = quote
                    
                    # Process trade ticks
                    if hasattr(ticker, 'last') and ticker.last > 0:
                        tick = SPYTick(
                            price=ticker.last,
                            size=getattr(ticker, 'lastSize', 0),
                            timestamp=datetime.now(),
                            tick_type='TRADE',
                            exchange=getattr(ticker, 'exchange', DEFAULT_EXCHANGE)
                        )
                        
                        self.tick_buffer.append(tick)
                        
                        # Update analytics
                        self._update_volume_profile(tick)
                        self.vwap_calculator.add_trade(tick.price, tick.size, tick.timestamp)
                        self.trade_classifier.classify_trade(tick)
                    
                    # Notify callbacks
                    self._notify_callbacks('quote_update', quote)
            
        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}")
            self.error_handler.handle_error(e, context="SPY Tick Data")
    
    def _on_depth_data(self, ticker):
        """Handle Level 2 depth data updates."""
        try:
            if not self.is_running:
                return
            
            depth = self._create_market_depth(ticker)
            if depth:
                with self.data_lock:
                    self.market_depth = depth
                    self._notify_callbacks('depth_update', depth)
            
        except Exception as e:
            self.logger.error(f"Error processing depth data: {e}")
            self.error_handler.handle_error(e, context="SPY Depth Data")
    
    def _create_spy_quote(self, ticker) -> Optional[SPYQuote]:
        """Create SPYQuote from ticker data."""
        try:
            # Extract data with defaults
            bid = getattr(ticker, 'bid', 0.0)
            ask = getattr(ticker, 'ask', 0.0)
            last = getattr(ticker, 'last', 0.0)
            
            # Check for valid data
            if bid <= 0 and ask <= 0 and last <= 0:
                return None
            
            quote = SPYQuote(
                symbol=self.symbol,
                bid=bid,
                ask=ask,
                bid_size=getattr(ticker, 'bidSize', 0),
                ask_size=getattr(ticker, 'askSize', 0),
                last=last,
                last_size=getattr(ticker, 'lastSize', 0),
                volume=getattr(ticker, 'volume', 0),
                high=getattr(ticker, 'high', 0.0),
                low=getattr(ticker, 'low', 0.0),
                open=getattr(ticker, 'open', 0.0),
                close=getattr(ticker, 'close', 0.0),
                timestamp=datetime.now(),
                exchange=getattr(ticker, 'exchange', DEFAULT_EXCHANGE)
            )
            
            return quote
            
        except Exception as e:
            self.logger.error(f"Error creating SPY quote: {e}")
            return None
    
    def _create_market_depth(self, ticker) -> Optional[MarketDepth]:
        """Create MarketDepth from ticker data."""
        try:
            depth = MarketDepth(symbol=self.symbol)
            
            # Extract bid/ask depth
            if hasattr(ticker, 'domBids') and ticker.domBids:
                depth.bids = [(level.price, level.size) for level in ticker.domBids[:PRICE_LEVEL_DEPTH]]
                depth.bids.sort(key=lambda x: x[0], reverse=True)  # Sort by price descending
            
            if hasattr(ticker, 'domAsks') and ticker.domAsks:
                depth.asks = [(level.price, level.size) for level in ticker.domAsks[:PRICE_LEVEL_DEPTH]]
                depth.asks.sort(key=lambda x: x[0])  # Sort by price ascending
            
            return depth if depth.bids or depth.asks else None
            
        except Exception as e:
            self.logger.error(f"Error creating market depth: {e}")
            return None
    
    def _update_volume_profile(self, tick: SPYTick):
        """Update volume profile with new tick."""
        try:
            if tick.tick_type != 'TRADE' or tick.size <= 0:
                return
            
            # Round price to nearest cent
            price_level = round(tick.price, 2)
            
            with self.data_lock:
                if self.volume_profile:
                    # Update price level volume
                    current_volume = self.volume_profile.price_levels.get(price_level, 0)
                    self.volume_profile.price_levels[price_level] = current_volume + tick.size
                    
                    # Update totals
                    self.volume_profile.total_volume += tick.size
                    
                    # Update trade size metrics
                    if tick.size >= LARGE_TRADE_THRESHOLD:
                        self.volume_profile.large_trades_count += 1
                    
                    if tick.size >= BLOCK_TRADE_THRESHOLD:
                        self.volume_profile.block_trades_count += 1
                    
                    # Calculate average trade size
                    total_trades = len([t for t in self.tick_buffer if t.tick_type == 'TRADE'])
                    if total_trades > 0:
                        self.volume_profile.average_trade_size = self.volume_profile.total_volume / total_trades
                    
                    self.volume_profile.timestamp = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating volume profile: {e}")
    
    def _notify_callbacks(self, event_type: str, data: Any):
        """Notify registered callbacks of data updates."""
        try:
            with self.data_lock:
                for callback_name, callback_func in self.data_callbacks.items():
                    try:
                        callback_func(event_type, data)
                    except Exception as e:
                        self.logger.error(f"Error in callback {callback_name}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error notifying callbacks: {e}")
    
    def _data_processing_loop(self):
        """Main data processing loop."""
        while self.is_running:
            try:
                # Update VWAP
                self.vwap_calculator.update()
                
                # Update volume profile VWAP
                if self.volume_profile:
                    self.volume_profile.vwap = self.vwap_calculator.get_current_vwap()
                
                # Periodic maintenance
                self._cleanup_old_data()
                
                time.sleep(1)  # Run every second
                
            except Exception as e:
                self.logger.error(f"Error in data processing loop: {e}")
                time.sleep(5)
    
    def _cleanup_old_data(self):
        """Clean up old data to manage memory."""
        try:
            # Clean up old ticks (keep last hour during market hours)
            cutoff_time = datetime.now() - timedelta(hours=1)
            
            with self.data_lock:
                while self.tick_buffer and self.tick_buffer[0].timestamp < cutoff_time:
                    self.tick_buffer.popleft()
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
    
    def _cancel_subscriptions(self):
        """Cancel all market data subscriptions."""
        try:
            if self.ticker:
                self.ib_client.cancelMktData(self.ticker.contract)
                self.ticker = None
            
            if self.depth_ticker:
                self.ib_client.cancelMktDepth(self.depth_ticker.contract)
                self.depth_ticker = None
                
        except Exception as e:
            self.logger.error(f"Error canceling subscriptions: {e}")
    
    def get_feed_status(self) -> Dict[str, Any]:
        """
        Get current feed status and statistics.
        
        Returns:
            dict: Feed status information
        """
        try:
            with self.data_lock:
                current_price = self.get_current_price()
                vwap = self.get_vwap()
                
                return {
                    "feed_id": SPY_FEED_ID,
                    "symbol": self.symbol,
                    "is_running": self.is_running,
                    "current_price": current_price,
                    "vwap": vwap,
                    "vwap_deviation": ((current_price - vwap) / vwap * 100) if vwap > 0 else 0.0,
                    "tick_buffer_size": len(self.tick_buffer),
                    "total_volume": self.volume_profile.total_volume if self.volume_profile else 0,
                    "large_trades": self.volume_profile.large_trades_count if self.volume_profile else 0,
                    "block_trades": self.volume_profile.block_trades_count if self.volume_profile else 0,
                    "spread_bps": self.current_quote.spread_bps if self.current_quote else 0.0,
                    "callbacks_registered": len(self.data_callbacks),
                    "last_update": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting feed status: {e}")
            return {"error": str(e)}


# =============================================================================
# Helper Classes
# =============================================================================
class VWAPCalculator:
    """Volume Weighted Average Price calculator."""
    
    def __init__(self, window_minutes: int = VWAP_WINDOW):
        self.window_minutes = window_minutes
        self.trades: deque = deque()
        self.current_vwap = 0.0
        
    def add_trade(self, price: float, volume: int, timestamp: datetime):
        """Add a trade to VWAP calculation."""
        self.trades.append((price, volume, timestamp))
        self._calculate_vwap()
        
    def _calculate_vwap(self):
        """Calculate current VWAP."""
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        
        # Remove old trades
        while self.trades and self.trades[0][2] < cutoff_time:
            self.trades.popleft()
        
        if not self.trades:
            self.current_vwap = 0.0
            return
        
        # Calculate VWAP
        total_value = sum(price * volume for price, volume, _ in self.trades)
        total_volume = sum(volume for _, volume, _ in self.trades)
        
        self.current_vwap = total_value / total_volume if total_volume > 0 else 0.0
    
    def get_current_vwap(self) -> float:
        """Get current VWAP value."""
        return self.current_vwap
    
    def update(self):
        """Update VWAP (remove old trades)."""
        self._calculate_vwap()


class TradeClassifier:
    """Trade classification for market microstructure analysis."""
    
    def __init__(self):
        self.aggressive_buys = 0
        self.aggressive_sells = 0
        self.passive_trades = 0
        
    def classify_trade(self, tick: SPYTick):
        """Classify trade as aggressive buy, sell, or passive."""
        # Simplified classification - in practice would use more sophisticated logic
        if tick.size >= LARGE_TRADE_THRESHOLD:
            if tick.price > tick.price * 1.001:  # Simplified logic
                self.aggressive_buys += 1
            else:
                self.aggressive_sells += 1
        else:
            self.passive_trades += 1


# =============================================================================
# Main Execution
# =============================================================================
if __name__ == "__main__":
    # Example usage
    from ib_insync import IB
    
    # Create IB connection
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    
    # Create SPY feed
    spy_feed = SPYFeed(ib, "SPY")
    
    # Register sample callback
    def on_quote_update(event_type, data):
        print(f"SPY Update: Price: {data.last}, Bid: {data.bid}, Ask: {data.ask}, Spread: {data.spread_bps:.1f} bps")
    
    spy_feed.register_callback("sample_callback", on_quote_update)
    
    try:
        # Start the feed
        spy_feed.start()
        
        # Keep running
        while True:
            time.sleep(30)
            status = spy_feed.get_feed_status()
            print(f"Feed Status: {status}")
            
    except KeyboardInterrupt:
        print("Shutting down SPY feed...")
        spy_feed.stop()
        ib.disconnect()
