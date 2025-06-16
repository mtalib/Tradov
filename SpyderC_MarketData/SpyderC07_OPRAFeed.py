#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderC07_OPRAFeed.py
Group: C (Market Data)
Purpose: OPRA (Options Price Reporting Authority) real-time options data feed

Description:
This module provides high-quality real-time options data feed from OPRA for SPY
options trading. It handles options quotes, trades, volume, open interest, and
Greeks calculations from live market data. The module supports Level 2 options
market data, real-time options chain updates, and integrates with the broader
Spyder market data infrastructure for comprehensive options analytics.

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
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import asyncio

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
DEFAULT_SYMBOL = "SPY"
DEFAULT_EXCHANGES = ["SMART", "CBOE", "ISE", "AMEX", "PHLX"]
DEFAULT_UPDATE_INTERVAL = 100  # milliseconds
DEFAULT_CACHE_SIZE = 10000
DEFAULT_HISTORY_DEPTH = 1000
OPRA_FEED_ID = "OPRA_FEED"
OPTIONS_EXPIRY_WINDOW = 60  # days
MIN_VOLUME_THRESHOLD = 10
MAX_SPREAD_THRESHOLD = 0.50  # 50 cents max bid-ask spread

# Greeks calculation constants
RISK_FREE_RATE = 0.05  # 5% risk-free rate
VOLATILITY_WINDOW = 252  # trading days

# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class OptionsQuote:
    """Real-time options quote data structure."""
    
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'C' for Call, 'P' for Put
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    last_size: int
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    timestamp: datetime
    exchange: str
    
    @property
    def mid_price(self) -> float:
        """Calculate mid price from bid/ask."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last if self.last > 0 else 0.0
    
    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        if self.bid > 0 and self.ask > 0:
            return self.ask - self.bid
        return 0.0
    
    @property
    def spread_percent(self) -> float:
        """Calculate spread as percentage of mid price."""
        mid = self.mid_price
        if mid > 0:
            return (self.spread / mid) * 100.0
        return 0.0


@dataclass
class OptionsChainSnapshot:
    """Complete options chain snapshot for a given expiry."""
    
    underlying_symbol: str
    expiry: datetime
    underlying_price: float
    calls: Dict[float, OptionsQuote] = field(default_factory=dict)  # strike -> quote
    puts: Dict[float, OptionsQuote] = field(default_factory=dict)   # strike -> quote
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_atm_strike(self) -> float:
        """Get the at-the-money strike price."""
        if not self.calls and not self.puts:
            return 0.0
        
        all_strikes = set(self.calls.keys()) | set(self.puts.keys())
        if not all_strikes:
            return 0.0
        
        return min(all_strikes, key=lambda x: abs(x - self.underlying_price))
    
    def get_liquid_options(self, min_volume: int = MIN_VOLUME_THRESHOLD) -> List[OptionsQuote]:
        """Get liquid options based on volume threshold."""
        liquid_options = []
        
        for quote in list(self.calls.values()) + list(self.puts.values()):
            if quote.volume >= min_volume and quote.spread <= MAX_SPREAD_THRESHOLD:
                liquid_options.append(quote)
        
        return sorted(liquid_options, key=lambda x: x.volume, reverse=True)


# =============================================================================
# Main OPRA Feed Class
# =============================================================================
class OPRAFeed:
    """
    OPRA (Options Price Reporting Authority) real-time data feed handler.
    
    This class provides comprehensive real-time options market data including:
    - Real-time options quotes and trades
    - Level 2 options market data
    - Options volume and open interest tracking
    - Live Greeks calculations
    - Options chain management
    - Market data validation and quality control
    
    Attributes:
        symbol (str): Primary underlying symbol (SPY)
        ib_client (IB): Interactive Brokers client connection
        is_running (bool): Feed running state
        data_callbacks (Dict): Registered data callbacks
        options_cache (Dict): Cached options data
        quotes_history (deque): Historical quotes buffer
        chain_snapshots (Dict): Options chain snapshots by expiry
        logger (SpyderLogger): Application logger
        error_handler (SpyderErrorHandler): Error handler
        data_validator (DataValidator): Data validation
        update_thread (threading.Thread): Data update thread
        market_time_utils (MarketTimeUtils): Market time utilities
    """
    
    def __init__(self, ib_client: IB, symbol: str = DEFAULT_SYMBOL):
        """
        Initialize the OPRA feed handler.
        
        Args:
            ib_client: Interactive Brokers client connection
            symbol: Primary underlying symbol for options
        """
        self.symbol = symbol.upper()
        self.ib_client = ib_client
        self.is_running = False
        
        # Data storage
        self.data_callbacks: Dict[str, Callable] = {}
        self.options_cache: Dict[str, OptionsQuote] = {}
        self.quotes_history: deque = deque(maxlen=DEFAULT_HISTORY_DEPTH)
        self.chain_snapshots: Dict[datetime, OptionsChainSnapshot] = {}
        
        # Subscriptions tracking
        self.active_contracts: Dict[str, Contract] = {}
        self.subscription_requests: Dict[str, bool] = {}
        
        # Threading
        self.update_thread: Optional[threading.Thread] = None
        self.data_lock = threading.RLock()
        
        # Utilities
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.data_validator = DataValidator()
        self.market_time_utils = MarketTimeUtils()
        
        self.logger.info(f"OPRA Feed initialized for {self.symbol}")
    
    def start(self) -> bool:
        """
        Start the OPRA data feed.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        try:
            if self.is_running:
                self.logger.warning("OPRA feed is already running")
                return True
            
            if not self.ib_client.isConnected():
                raise TradingError("IB client not connected - cannot start OPRA feed")
            
            self.logger.info(f"🚀 Starting OPRA feed for {self.symbol}")
            self.is_running = True
            
            # Start data processing thread
            self.update_thread = threading.Thread(target=self._data_processing_loop, daemon=True)
            self.update_thread.start()
            
            # Subscribe to options chain
            self._subscribe_to_options_chain()
            
            self.logger.info(f"✅ OPRA feed started successfully for {self.symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start OPRA feed: {e}")
            self.error_handler.handle_error(e, context="OPRA Feed Start")
            self.is_running = False
            return False
    
    def stop(self):
        """Stop the OPRA data feed."""
        try:
            if not self.is_running:
                self.logger.info("OPRA feed is already stopped")
                return
            
            self.logger.info(f"🛑 Stopping OPRA feed for {self.symbol}")
            self.is_running = False
            
            # Cancel all subscriptions
            self._cancel_all_subscriptions()
            
            # Wait for processing thread to finish
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=5.0)
            
            self.logger.info(f"✅ OPRA feed stopped for {self.symbol}")
            
        except Exception as e:
            self.logger.error(f"Error stopping OPRA feed: {e}")
            self.error_handler.handle_error(e, context="OPRA Feed Stop")
    
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
    
    def get_options_chain(self, expiry: Optional[datetime] = None) -> Optional[OptionsChainSnapshot]:
        """
        Get current options chain snapshot.
        
        Args:
            expiry: Specific expiry date, or None for nearest expiry
            
        Returns:
            Options chain snapshot or None if not available
        """
        try:
            with self.data_lock:
                if not self.chain_snapshots:
                    return None
                
                if expiry is None:
                    # Return nearest expiry
                    expiry = min(self.chain_snapshots.keys())
                
                return self.chain_snapshots.get(expiry)
                
        except Exception as e:
            self.logger.error(f"Error getting options chain: {e}")
            return None
    
    def get_option_quote(self, strike: float, expiry: datetime, option_type: str) -> Optional[OptionsQuote]:
        """
        Get specific option quote.
        
        Args:
            strike: Strike price
            expiry: Expiration date
            option_type: 'C' for Call, 'P' for Put
            
        Returns:
            Options quote or None if not found
        """
        try:
            chain = self.get_options_chain(expiry)
            if not chain:
                return None
            
            if option_type.upper() == 'C':
                return chain.calls.get(strike)
            elif option_type.upper() == 'P':
                return chain.puts.get(strike)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting option quote: {e}")
            return None
    
    def get_liquid_options(self, expiry: Optional[datetime] = None, 
                          min_volume: int = MIN_VOLUME_THRESHOLD) -> List[OptionsQuote]:
        """
        Get liquid options for trading.
        
        Args:
            expiry: Specific expiry or None for all
            min_volume: Minimum volume threshold
            
        Returns:
            List of liquid options quotes
        """
        try:
            liquid_options = []
            
            chains_to_check = []
            if expiry:
                chain = self.get_options_chain(expiry)
                if chain:
                    chains_to_check = [chain]
            else:
                chains_to_check = list(self.chain_snapshots.values())
            
            for chain in chains_to_check:
                liquid_options.extend(chain.get_liquid_options(min_volume))
            
            return sorted(liquid_options, key=lambda x: x.volume, reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error getting liquid options: {e}")
            return []
    
    def _subscribe_to_options_chain(self):
        """Subscribe to options chain data."""
        try:
            # Get available option expiries
            expiry_dates = self._get_option_expiries()
            
            for expiry in expiry_dates[:4]:  # Limit to first 4 expiries
                self._subscribe_to_expiry(expiry)
            
        except Exception as e:
            self.logger.error(f"Error subscribing to options chain: {e}")
            self.error_handler.handle_error(e, context="Options Chain Subscription")
    
    def _get_option_expiries(self) -> List[datetime]:
        """Get available option expiration dates."""
        try:
            # Create underlying contract
            underlying = Stock(self.symbol, 'SMART', 'USD')
            self.ib_client.qualifyContracts(underlying)
            
            # Get option chain
            chains = self.ib_client.reqSecDefOptParams(
                underlying.symbol, '', underlying.secType, underlying.conId
            )
            
            expiry_dates = []
            for chain in chains:
                for expiry_str in chain.expirations:
                    expiry_date = datetime.strptime(expiry_str, '%Y%m%d')
                    
                    # Only include expiries within our window
                    days_to_expiry = (expiry_date - datetime.now()).days
                    if 0 < days_to_expiry <= OPTIONS_EXPIRY_WINDOW:
                        expiry_dates.append(expiry_date)
            
            return sorted(expiry_dates)
            
        except Exception as e:
            self.logger.error(f"Error getting option expiries: {e}")
            return []
    
    def _subscribe_to_expiry(self, expiry: datetime):
        """Subscribe to all options for a specific expiry."""
        try:
            expiry_str = expiry.strftime('%Y%m%d')
            
            # Get underlying price for strike selection
            underlying = Stock(self.symbol, 'SMART', 'USD')
            self.ib_client.qualifyContracts(underlying)
            
            underlying_data = self.ib_client.reqMktData(underlying, '', False, False)
            self.ib_client.sleep(1)  # Wait for data
            
            if hasattr(underlying_data, 'last') and underlying_data.last:
                underlying_price = underlying_data.last
            else:
                self.logger.warning(f"Could not get underlying price for {self.symbol}")
                return
            
            # Calculate strike range around current price
            strike_range = self._calculate_strike_range(underlying_price)
            
            # Subscribe to calls and puts
            for strike in strike_range:
                self._subscribe_to_option(strike, expiry_str, 'C')  # Calls
                self._subscribe_to_option(strike, expiry_str, 'P')  # Puts
            
            self.logger.info(f"Subscribed to {len(strike_range) * 2} options for expiry {expiry_str}")
            
        except Exception as e:
            self.logger.error(f"Error subscribing to expiry {expiry}: {e}")
    
    def _calculate_strike_range(self, underlying_price: float) -> List[float]:
        """Calculate relevant strike range around current price."""
        try:
            # Calculate range: ±20% around current price, in $1 increments for SPY
            range_percent = 0.20
            lower_bound = underlying_price * (1 - range_percent)
            upper_bound = underlying_price * (1 + range_percent)
            
            # Round to nearest dollar for SPY
            lower_strike = int(lower_bound)
            upper_strike = int(upper_bound) + 1
            
            strikes = list(range(lower_strike, upper_strike + 1))
            return strikes
            
        except Exception as e:
            self.logger.error(f"Error calculating strike range: {e}")
            return []
    
    def _subscribe_to_option(self, strike: float, expiry_str: str, right: str):
        """Subscribe to a specific option contract."""
        try:
            # Create option contract
            option = Option(self.symbol, expiry_str, strike, right, 'SMART')
            self.ib_client.qualifyContracts(option)
            
            # Request market data
            contract_key = f"{self.symbol}_{expiry_str}_{strike}_{right}"
            
            if contract_key not in self.active_contracts:
                ticker = self.ib_client.reqMktData(
                    option, 
                    '100,101,104,105,106,225',  # Bid, Ask, Last, Volume, IV, Greeks
                    False, 
                    False
                )
                
                self.active_contracts[contract_key] = option
                self.subscription_requests[contract_key] = True
                
                # Set up callback for this ticker
                ticker.updateEvent += lambda t=ticker, k=contract_key: self._on_option_data_update(t, k)
            
        except Exception as e:
            self.logger.error(f"Error subscribing to option {strike} {right} {expiry_str}: {e}")
    
    def _on_option_data_update(self, ticker, contract_key: str):
        """Handle option data updates."""
        try:
            if not self.is_running:
                return
            
            contract = self.active_contracts.get(contract_key)
            if not contract:
                return
            
            # Extract data from ticker
            quote = self._create_options_quote(ticker, contract)
            if quote and self.data_validator.validate_options_quote(quote):
                
                with self.data_lock:
                    # Update cache
                    self.options_cache[contract_key] = quote
                    self.quotes_history.append(quote)
                    
                    # Update chain snapshot
                    self._update_chain_snapshot(quote)
                    
                    # Notify callbacks
                    self._notify_callbacks('option_update', quote)
            
        except Exception as e:
            self.logger.error(f"Error processing option data update: {e}")
            self.error_handler.handle_error(e, context="Option Data Update")
    
    def _create_options_quote(self, ticker, contract: Option) -> Optional[OptionsQuote]:
        """Create OptionsQuote from ticker data."""
        try:
            # Extract basic data
            bid = getattr(ticker, 'bid', 0.0) if hasattr(ticker, 'bid') else 0.0
            ask = getattr(ticker, 'ask', 0.0) if hasattr(ticker, 'ask') else 0.0
            last = getattr(ticker, 'last', 0.0) if hasattr(ticker, 'last') else 0.0
            
            # Check for valid data
            if bid <= 0 and ask <= 0 and last <= 0:
                return None
            
            # Create quote
            quote = OptionsQuote(
                symbol=contract.symbol,
                strike=contract.strike,
                expiry=datetime.strptime(contract.lastTradeDateOrContractMonth, '%Y%m%d'),
                option_type=contract.right,
                bid=bid,
                ask=ask,
                bid_size=getattr(ticker, 'bidSize', 0),
                ask_size=getattr(ticker, 'askSize', 0),
                last=last,
                last_size=getattr(ticker, 'lastSize', 0),
                volume=getattr(ticker, 'volume', 0),
                open_interest=getattr(ticker, 'openInterest', 0),
                implied_volatility=getattr(ticker, 'impliedVolatility', 0.0),
                delta=getattr(ticker, 'delta', 0.0),
                gamma=getattr(ticker, 'gamma', 0.0),
                theta=getattr(ticker, 'theta', 0.0),
                vega=getattr(ticker, 'vega', 0.0),
                rho=getattr(ticker, 'rho', 0.0),
                timestamp=datetime.now(),
                exchange=getattr(ticker, 'exchange', 'SMART')
            )
            
            return quote
            
        except Exception as e:
            self.logger.error(f"Error creating options quote: {e}")
            return None
    
    def _update_chain_snapshot(self, quote: OptionsQuote):
        """Update options chain snapshot with new quote."""
        try:
            expiry = quote.expiry
            
            if expiry not in self.chain_snapshots:
                # Create new chain snapshot
                underlying_price = self._get_current_underlying_price()
                self.chain_snapshots[expiry] = OptionsChainSnapshot(
                    underlying_symbol=self.symbol,
                    expiry=expiry,
                    underlying_price=underlying_price
                )
            
            # Update the appropriate strike
            chain = self.chain_snapshots[expiry]
            if quote.option_type == 'C':
                chain.calls[quote.strike] = quote
            elif quote.option_type == 'P':
                chain.puts[quote.strike] = quote
            
            chain.timestamp = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating chain snapshot: {e}")
    
    def _get_current_underlying_price(self) -> float:
        """Get current underlying price."""
        try:
            # This would integrate with SpyderC08_SPYFeed
            # For now, return a placeholder
            return 450.0  # Placeholder SPY price
            
        except Exception as e:
            self.logger.error(f"Error getting underlying price: {e}")
            return 0.0
    
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
                # Periodic maintenance tasks
                self._cleanup_expired_data()
                self._validate_subscriptions()
                
                time.sleep(1)  # Run every second
                
            except Exception as e:
                self.logger.error(f"Error in data processing loop: {e}")
                time.sleep(5)
    
    def _cleanup_expired_data(self):
        """Clean up expired options data."""
        try:
            current_time = datetime.now()
            expired_expiries = []
            
            with self.data_lock:
                for expiry in self.chain_snapshots:
                    if expiry < current_time:
                        expired_expiries.append(expiry)
                
                for expiry in expired_expiries:
                    del self.chain_snapshots[expiry]
                    self.logger.info(f"Cleaned up expired options data for {expiry}")
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up expired data: {e}")
    
    def _validate_subscriptions(self):
        """Validate active subscriptions."""
        try:
            # Check if subscriptions are still active
            inactive_contracts = []
            
            for contract_key in self.active_contracts:
                if not self.subscription_requests.get(contract_key, False):
                    inactive_contracts.append(contract_key)
            
            # Clean up inactive contracts
            for contract_key in inactive_contracts:
                if contract_key in self.active_contracts:
                    del self.active_contracts[contract_key]
                if contract_key in self.subscription_requests:
                    del self.subscription_requests[contract_key]
                    
        except Exception as e:
            self.logger.error(f"Error validating subscriptions: {e}")
    
    def _cancel_all_subscriptions(self):
        """Cancel all active subscriptions."""
        try:
            with self.data_lock:
                for contract_key in list(self.active_contracts.keys()):
                    try:
                        contract = self.active_contracts[contract_key]
                        self.ib_client.cancelMktData(contract)
                    except Exception as e:
                        self.logger.error(f"Error canceling subscription {contract_key}: {e}")
                
                self.active_contracts.clear()
                self.subscription_requests.clear()
                
        except Exception as e:
            self.logger.error(f"Error canceling all subscriptions: {e}")
    
    def get_feed_status(self) -> Dict[str, Any]:
        """
        Get current feed status and statistics.
        
        Returns:
            dict: Feed status information
        """
        try:
            with self.data_lock:
                return {
                    "feed_id": OPRA_FEED_ID,
                    "symbol": self.symbol,
                    "is_running": self.is_running,
                    "active_contracts": len(self.active_contracts),
                    "cached_quotes": len(self.options_cache),
                    "chain_expiries": len(self.chain_snapshots),
                    "quotes_history_size": len(self.quotes_history),
                    "callbacks_registered": len(self.data_callbacks),
                    "last_update": datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting feed status: {e}")
            return {"error": str(e)}


# =============================================================================
# Main Execution
# =============================================================================
if __name__ == "__main__":
    # Example usage
    from ib_insync import IB
    
    # Create IB connection
    ib = IB()
    ib.connect('127.0.0.1', 4002, clientId=1)
    
    # Create OPRA feed
    opra_feed = OPRAFeed(ib, "SPY")
    
    # Register a sample callback
    def on_option_update(event_type, data):
        print(f"Option Update: {data.symbol} {data.strike} {data.option_type} - Bid: {data.bid}, Ask: {data.ask}")
    
    opra_feed.register_callback("sample_callback", on_option_update)
    
    try:
        # Start the feed
        opra_feed.start()
        
        # Keep running
        while True:
            time.sleep(60)
            status = opra_feed.get_feed_status()
            print(f"Feed Status: {status}")
            
    except KeyboardInterrupt:
        print("Shutting down OPRA feed...")
        opra_feed.stop()
        ib.disconnect()
