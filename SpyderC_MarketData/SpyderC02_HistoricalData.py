#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC02_HistoricalData.py
Group: C (Market Data)
Purpose: Historical data retrieval and storage

Description:
    This module handles the retrieval, storage, and management of historical market data
    for the Spyder trading system. It interfaces with Interactive Brokers to fetch
    historical price data, option data, and market statistics. The module includes
    caching mechanisms to minimize API calls and provides data preprocessing utilities.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import datetime
import queue
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from ibapi.contract import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderH_Storage.SpyderH03_MarketDataCache import MarketDataCache
from SpyderB_Broker.SpyderB01_IBClient import IBClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_HISTORICAL_REQUESTS_PER_SECOND = 6
CACHE_DIR = Path.home() / '.spyder' / 'cache' / 'historical'
CACHE_EXPIRY_HOURS = 24
# ==============================================================================
# ENUMS
# ==============================================================================
class DataType(Enum):
    """Historical data types"""
    TRADES = "TRADES"
    MIDPOINT = "MIDPOINT"
    BID = "BID"
    ASK = "ASK"
    BID_ASK = "BID_ASK"
    ADJUSTED_LAST = "ADJUSTED_LAST"
    HISTORICAL_VOLATILITY = "HISTORICAL_VOLATILITY"
    OPTION_IMPLIED_VOLATILITY = "OPTION_IMPLIED_VOLATILITY"

class BarSize(Enum):
    """Bar size options"""
    ONE_SEC = "1 sec"
    FIVE_SECS = "5 secs"
    TEN_SECS = "10 secs"
    FIFTEEN_SECS = "15 secs"
    THIRTY_SECS = "30 secs"
    ONE_MIN = "1 min"
    TWO_MINS = "2 mins"
    THREE_MINS = "3 mins"
    FIVE_MINS = "5 mins"
    TEN_MINS = "10 mins"
    FIFTEEN_MINS = "15 mins"
    TWENTY_MINS = "20 mins"
    THIRTY_MINS = "30 mins"
    ONE_HOUR = "1 hour"
    TWO_HOURS = "2 hours"
    THREE_HOURS = "3 hours"
    FOUR_HOURS = "4 hours"
    EIGHT_HOURS = "8 hours"
    ONE_DAY = "1 day"
    ONE_WEEK = "1 week"
    ONE_MONTH = "1 month"

class Duration(Enum):
    """Duration units"""
    SECONDS = "S"
    DAYS = "D"
    WEEKS = "W"
    MONTHS = "M"
    YEARS = "Y"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class HistoricalDataRequest:
    """Historical data request specification"""
    request_id: int
    contract: Contract
    end_datetime: datetime.datetime
    duration: str  # e.g., "1 D", "1 W", "1 M"
    bar_size: BarSize
    data_type: DataType
    use_rth: bool = True  # Regular Trading Hours only
    format_date: int = 1  # 1=yyyyMMdd HH:mm:ss, 2=Unix timestamp
    keep_up_to_date: bool = False
    callback: Optional[Any] = None
    
class HistoricalBar:
    """Historical price bar"""
    timestamp: datetime.datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float  # Weighted Average Price
    count: int  # Number of trades
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'wap': self.wap,
            'count': self.count
        }

class DataSeries:
    """Time series data container"""
    symbol: str
    bar_size: BarSize
    data_type: DataType
    bars: List[HistoricalBar]
    start_time: datetime.datetime
    end_time: datetime.datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame"""
        if not self.bars:
            return pd.DataFrame()
        
        data = [bar.to_dict() for bar in self.bars]
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)
        return df
    
    def get_stats(self) -> Dict[str, float]:
        """Calculate basic statistics"""
        if not self.bars:
            return {}
        
        closes = [bar.close for bar in self.bars]
        volumes = [bar.volume for bar in self.bars]
        
        return {
            'count': len(self.bars),
            'mean_close': np.mean(closes),
            'std_close': np.std(closes),
            'min_close': np.min(closes),
            'max_close': np.max(closes),
            'total_volume': np.sum(volumes),
            'mean_volume': np.mean(volumes)
        }

# ==============================================================================
# HISTORICAL DATA MANAGER CLASS
# ==============================================================================
class HistoricalDataManager:
    """
    Manages historical data retrieval and storage.
    
    Features:
    - Historical data fetching from IB
    - Data caching and persistence
    - Rate limiting for API calls
    - Data preprocessing and validation
    - Multiple timeframe support
    - Continuous data updates
    """
    
    def __init__(self, ib_client: IBClient, event_manager: EventManager):
        """
        Initialize historical data manager.
        
        Args:
            ib_client: IB client instance
            event_manager: Event manager instance
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data storage
        self.data_series: Dict[str, DataSeries] = {}
        self.pending_requests: Dict[int, HistoricalDataRequest] = {}
        self.completed_requests: Dict[int, DataSeries] = {}
        
        # Request management
        self._next_request_id = 20000
        self._request_queue = queue.Queue()
        self._response_queue = queue.Queue()
        self._request_lock = threading.RLock()
        
        # Rate limiting
        self._request_timestamps: List[float] = []
        self._rate_limit_lock = threading.Lock()
        
        # Cache
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.cache = MarketDataCache(CACHE_DIR)
        
        # Trading calendar
        self.calendar = TradingCalendar()
        
        # Processing thread
        self._processor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # IB callbacks
        self._register_ib_callbacks()
        
        self.logger.info("HistoricalDataManager initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start historical data manager"""
        if self._running:
            return
        
        self._running = True
        
        # Start processor thread
        self._processor_thread = threading.Thread(
            target=self._process_requests,
            daemon=True,
            name="HistoricalDataProcessor"
        )
        self._processor_thread.start()
        
        self.logger.info("Historical data manager started")
    
    def stop(self) -> None:
        """Stop historical data manager"""
        self._running = False
        
        if self._processor_thread:
            self._processor_thread.join(timeout=5.0)
        
        # Cancel pending requests
        self._cancel_all_requests()
        
        self.logger.info("Historical data manager stopped")
    
    # ==========================================================================
    # DATA REQUESTS
    # ==========================================================================
    def request_historical_data(
        self,
        contract: Contract,
        end_datetime: Optional[datetime.datetime] = None,
        duration: str = "1 D",
        bar_size: BarSize = BarSize.FIVE_MINS,
        data_type: DataType = DataType.TRADES,
        use_rth: bool = True,
        callback: Optional[Any] = None
    ) -> int:
        """
        Request historical data.
        
        Args:
            contract: Contract to fetch data for
            end_datetime: End time for data (default: now)
            duration: Duration string (e.g., "1 D", "1 W")
            bar_size: Bar size
            data_type: Type of data
            use_rth: Use regular trading hours only
            callback: Optional callback function
            
        Returns:
            Request ID
        """
        # Check cache first
        cache_key = self._get_cache_key(contract, bar_size, data_type)
        cached_data = self.cache.get(cache_key)
        
        if cached_data and self._is_cache_valid(cached_data, end_datetime):
            self.logger.info(f"Using cached data for {contract.symbol}")
            if callback:
                callback(cached_data)
            return -1  # Indicate cache hit
        
        # Create request
        request_id = self._get_next_request_id()
        
        if end_datetime is None:
            end_datetime = datetime.datetime.now()
        
        request = HistoricalDataRequest(
            request_id=request_id,
            contract=contract,
            end_datetime=end_datetime,
            duration=duration,
            bar_size=bar_size,
            data_type=data_type,
            use_rth=use_rth,
            callback=callback
        )
        
        # Queue request
        self._request_queue.put(request)
        
        self.logger.info(f"Queued historical data request {request_id} for {contract.symbol}")
        
        return request_id
    
    def request_intraday_bars(
        self,
        contract: Contract,
        date: datetime.date,
        bar_size: BarSize = BarSize.ONE_MIN,
        data_type: DataType = DataType.TRADES,
        callback: Optional[Any] = None
    ) -> int:
        """
        Request intraday bars for a specific date.
        
        Args:
            contract: Contract
            date: Date to fetch
            bar_size: Bar size
            data_type: Data type
            callback: Optional callback
            
        Returns:
            Request ID
        """
        # Set end time to end of trading day
        end_datetime = datetime.datetime.combine(
            date,
            datetime.time(16, 0)  # 4 PM ET
        )
        
        return self.request_historical_data(
            contract=contract,
            end_datetime=end_datetime,
            duration="1 D",
            bar_size=bar_size,
            data_type=data_type,
            use_rth=True,
            callback=callback
        )
    
    def request_daily_bars(
        self,
        contract: Contract,
        days: int = 30,
        data_type: DataType = DataType.TRADES,
        callback: Optional[Any] = None
    ) -> int:
        """
        Request daily bars.
        
        Args:
            contract: Contract
            days: Number of days
            data_type: Data type
            callback: Optional callback
            
        Returns:
            Request ID
        """
        duration = f"{days} D"
        
        return self.request_historical_data(
            contract=contract,
            duration=duration,
            bar_size=BarSize.ONE_DAY,
            data_type=data_type,
            callback=callback
        )
    
    def request_option_history(
        self,
        option_contract: Contract,
        days: int = 5,
        callback: Optional[Any] = None
    ) -> int:
        """
        Request option price history.
        
        Args:
            option_contract: Option contract
            days: Number of days
            callback: Optional callback
            
        Returns:
            Request ID
        """
        # Options typically have less liquidity, use larger bars
        return self.request_historical_data(
            contract=option_contract,
            duration=f"{days} D",
            bar_size=BarSize.THIRTY_MINS,
            data_type=DataType.TRADES,
            use_rth=True,
            callback=callback
        )
    
    # ==========================================================================
    # DATA PROCESSING
    # ==========================================================================
    def _process_requests(self) -> None:
        """Process queued requests with rate limiting"""
        while self._running:
            try:
                # Get next request
                request = self._request_queue.get(timeout=1.0)
                
                # Apply rate limiting
                self._wait_for_rate_limit()
                
                # Store pending request
                with self._request_lock:
                    self.pending_requests[request.request_id] = request
                
                # Format end time
                end_time_str = request.end_datetime.strftime("%Y%m%d %H:%M:%S")
                
                # Make IB request
                self.ib_client.reqHistoricalData(
                    request.request_id,
                    request.contract,
                    end_time_str,
                    request.duration,
                    request.bar_size.value,
                    request.data_type.value,
                    1 if request.use_rth else 0,
                    request.format_date,
                    request.keep_up_to_date,
                    []
                )
                
                # Record request time
                with self._rate_limit_lock:
                    self._request_timestamps.append(time.time())
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing request: {e}")
    
    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits"""
        with self._rate_limit_lock:
            # Remove old timestamps
            current_time = time.time()
            self._request_timestamps = [
                ts for ts in self._request_timestamps 
                if current_time - ts < 1.0
            ]
            
            # Check if at limit
            if len(self._request_timestamps) >= MAX_HISTORICAL_REQUESTS_PER_SECOND:
                # Calculate wait time
                oldest_request = self._request_timestamps[0]
                wait_time = 1.0 - (current_time - oldest_request) + 0.1
                
                if wait_time > 0:
                    self.logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
    
    def _process_bar_data(
        self,
        request_id: int,
        bars: List[HistoricalBar]
    ) -> Optional[DataSeries]:
        """Process received bar data"""
        request = self.pending_requests.get(request_id)
        if not request:
            self.logger.warning(f"No pending request for ID {request_id}")
            return None
        
        if not bars:
            self.logger.warning(f"No data received for request {request_id}")
            return None
        
        # Create data series
        data_series = DataSeries(
            symbol=request.contract.symbol,
            bar_size=request.bar_size,
            data_type=request.data_type,
            bars=bars,
            start_time=bars[0].timestamp,
            end_time=bars[-1].timestamp,
            metadata={
                'contract': request.contract,
                'use_rth': request.use_rth,
                'request_time': datetime.datetime.now()
            }
        )
        
        # Validate data
        if self._validate_data(data_series):
            # Store in cache
            cache_key = self._get_cache_key(
                request.contract,
                request.bar_size,
                request.data_type
            )
            self.cache.put(cache_key, data_series)
            
            # Store in memory
            self.data_series[cache_key] = data_series
            
            # Execute callback
            if request.callback:
                request.callback(data_series)
            
            return data_series
        else:
            self.logger.error(f"Data validation failed for request {request_id}")
            return None
    
    def _validate_data(self, data_series: DataSeries) -> bool:
        """Validate historical data"""
        if not data_series.bars:
            return False
        
        # Check for gaps
        prev_timestamp = None
        for bar in data_series.bars:
            # Validate bar data
            if bar.high < bar.low:
                self.logger.error("High < Low in bar data")
                return False
            
            if bar.open < bar.low or bar.open > bar.high:
                self.logger.error("Open outside of high/low range")
                return False
            
            if bar.close < bar.low or bar.close > bar.high:
                self.logger.error("Close outside of high/low range")
                return False
            
            # Check timestamp ordering
            if prev_timestamp and bar.timestamp <= prev_timestamp:
                self.logger.error("Timestamps not in ascending order")
                return False
            
            prev_timestamp = bar.timestamp
        
        return True
    
    # ==========================================================================
    # IB CALLBACKS
    # ==========================================================================
    def _register_ib_callbacks(self) -> None:
        """Register IB API callbacks"""
        self.ib_client.register_callback('historicalData', self._on_historical_data)
        self.ib_client.register_callback('historicalDataEnd', self._on_historical_data_end)
        self.ib_client.register_callback('historicalDataUpdate', self._on_historical_data_update)
        self.ib_client.register_callback('error', self._on_error)
    
    def _on_historical_data(self, reqId: int, bar) -> None:
        """Handle historical data from IB"""
        # Convert IB bar to our format
        historical_bar = HistoricalBar(
            timestamp=datetime.datetime.strptime(bar.date, "%Y%m%d %H:%M:%S"),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            wap=bar.average,
            count=bar.barCount
        )
        
        # Add to temporary storage
        if reqId not in self.completed_requests:
            self.completed_requests[reqId] = []
        
        self.completed_requests[reqId].append(historical_bar)
    
    def _on_historical_data_end(self, reqId: int, start: str, end: str) -> None:
        """Handle end of historical data from IB"""
        self.logger.info(f"Historical data complete for request {reqId}")
        
        # Get bars
        bars = self.completed_requests.get(reqId, [])
        
        # Process data
        data_series = self._process_bar_data(reqId, bars)
        
        # Clean up
        with self._request_lock:
            self.pending_requests.pop(reqId, None)
            self.completed_requests.pop(reqId, None)
        
        # Emit event
        if data_series:
            self.event_manager.emit(Event(
                EventType.MARKET_DATA,
                {
                    'type': 'historical_data_received',
                    'request_id': reqId,
                    'symbol': data_series.symbol,
                    'bar_count': len(data_series.bars),
                    'start_time': data_series.start_time,
                    'end_time': data_series.end_time
                }
            ))
    
    def _on_historical_data_update(self, reqId: int, bar) -> None:
        """Handle historical data update (for keep_up_to_date requests)"""
        # Convert and process update
        historical_bar = HistoricalBar(
            timestamp=datetime.datetime.strptime(bar.date, "%Y%m%d %H:%M:%S"),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            wap=bar.average,
            count=bar.barCount
        )
        
        # Update data series
        request = self.pending_requests.get(reqId)
        if request:
            cache_key = self._get_cache_key(
                request.contract,
                request.bar_size,
                request.data_type
            )
            
            data_series = self.data_series.get(cache_key)
            if data_series:
                # Add or update bar
                data_series.bars.append(historical_bar)
                data_series.end_time = historical_bar.timestamp
                
                # Trigger callback if specified
                if request.callback:
                    request.callback(data_series)
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str) -> None:
        """Handle errors from IB"""
        if reqId in self.pending_requests:
            self.logger.error(f"Historical data error for request {reqId}: {errorCode} - {errorString}")
            
            # Clean up
            with self._request_lock:
                request = self.pending_requests.pop(reqId, None)
                self.completed_requests.pop(reqId, None)
            
            # Notify callback of error
            if request and request.callback:
                request.callback(None)
    
    # ==========================================================================
    # DATA ACCESS
    # ==========================================================================
    def get_latest_data(
        self,
        symbol: str,
        bar_size: BarSize = BarSize.FIVE_MINS,
        data_type: DataType = DataType.TRADES
    ) -> Optional[DataSeries]:
        """
        Get latest cached data for a symbol.
        
        Args:
            symbol: Symbol
            bar_size: Bar size
            data_type: Data type
            
        Returns:
            Data series or None
        """
        # Create dummy contract for cache key
        contract = Contract()
        contract.symbol = symbol
        
        cache_key = self._get_cache_key(contract, bar_size, data_type)
        return self.data_series.get(cache_key)
    
    def get_dataframe(
        self,
        symbol: str,
        bar_size: BarSize = BarSize.FIVE_MINS,
        data_type: DataType = DataType.TRADES
    ) -> Optional[pd.DataFrame]:
        """
        Get data as pandas DataFrame.
        
        Args:
            symbol: Symbol
            bar_size: Bar size
            data_type: Data type
            
        Returns:
            DataFrame or None
        """
        data_series = self.get_latest_data(symbol, bar_size, data_type)
        if data_series:
            return data_series.to_dataframe()
        return None
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _get_next_request_id(self) -> int:
        """Get next request ID"""
        with self._request_lock:
            self._next_request_id += 1
            return self._next_request_id
    
    def _get_cache_key(
        self,
        contract: Contract,
        bar_size: BarSize,
        data_type: DataType
    ) -> str:
        """Generate cache key for data"""
        return f"{contract.symbol}_{bar_size.value}_{data_type.value}"
    
    def _is_cache_valid(
        self,
        cached_data: DataSeries,
        end_datetime: Optional[datetime.datetime]
    ) -> bool:
        """Check if cached data is still valid"""
        if not cached_data or not cached_data.bars:
            return False
        
        # Check age
        request_time = cached_data.metadata.get('request_time')
        if request_time:
            age_hours = (datetime.datetime.now() - request_time).total_seconds() / 3600
            if age_hours > CACHE_EXPIRY_HOURS:
                return False
        
        # Check if covers requested period
        if end_datetime:
            if cached_data.end_time < end_datetime:
                return False
        
        return True
    
    def _cancel_all_requests(self) -> None:
        """Cancel all pending requests"""
        with self._request_lock:
            for request_id in list(self.pending_requests.keys()):
                self.ib_client.cancelHistoricalData(request_id)
            
            self.pending_requests.clear()
            self.completed_requests.clear()
    
    def clear_cache(self) -> None:
        """Clear all cached data"""
        self.cache.clear()
        self.data_series.clear()
        self.logger.info("Historical data cache cleared")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test historical data manager
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from ibapi.contract import Contract
    
    # Mock IB client
    class MockIBClient:
        def __init__(self):
            self.callbacks = {}
        
        def register_callback(self, event, callback):
            self.callbacks[event] = callback
        
        def reqHistoricalData(self, reqId, contract, endDateTime, durationStr,
                             barSizeSetting, whatToShow, useRTH, formatDate,
                             keepUpToDate, chartOptions):
            print(f"Requesting historical data: {contract.symbol} {barSizeSetting}")
            
            # Simulate response
            import time
            time.sleep(0.5)
            
            # Create mock bars
            from collections import namedtuple
            Bar = namedtuple('Bar', ['date', 'open', 'high', 'low', 'close', 
                                    'volume', 'average', 'barCount'])
            
            # Send some bars
            for i in range(5):
                bar = Bar(
                    date="20250529 09:30:00",
                    open=450.0 + i,
                    high=451.0 + i,
                    low=449.0 + i,
                    close=450.5 + i,
                    volume=1000000,
                    average=450.25 + i,
                    barCount=1000
                )
                self.callbacks['historicalData'](reqId, bar)
            
            # Send end signal
            self.callbacks['historicalDataEnd'](reqId, "", "")
    
    # Initialize
    event_manager = EventManager()
    ib_client = MockIBClient()
    historical_manager = HistoricalDataManager(ib_client, event_manager)
    
    # Start manager
    historical_manager.start()
    
    # Create SPY contract
    spy_contract = Contract()
    spy_contract.symbol = "SPY"
    spy_contract.secType = "STK"
    spy_contract.exchange = "SMART"
    spy_contract.currency = "USD"
    
    # Define callback
    def on_data_received(data_series):
        if data_series:
            print(f"\nReceived {len(data_series.bars)} bars for {data_series.symbol}")
            print(f"Time range: {data_series.start_time} to {data_series.end_time}")
            
            # Get DataFrame
            df = data_series.to_dataframe()
            print(f"\nDataFrame shape: {df.shape}")
            print(df.head())
            
            # Get stats
            stats = data_series.get_stats()
            print(f"\nStatistics:")
            for key, value in stats.items():
                print(f"  {key}: {value:.2f}")
        else:
            print("No data received")
    
    # Request data
    request_id = historical_manager.request_historical_data(
        contract=spy_contract,
        duration="1 D",
        bar_size=BarSize.FIVE_MINS,
        data_type=DataType.TRADES,
        callback=on_data_received
    )
    
    print(f"Request ID: {request_id}")
    
    # Wait for data
    time.sleep(2)
    
    # Request daily bars
    print("\nRequesting daily bars...")
    request_id2 = historical_manager.request_daily_bars(
        contract=spy_contract,
        days=30,
        callback=on_data_received
    )
    
    # Wait
    time.sleep(2)
    
    # Stop manager
    historical_manager.stop()