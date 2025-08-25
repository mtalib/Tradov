#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC02_HistoricalData.py
Purpose: Historical data retrieval and storage (ib_async compatible)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-22 Time: 14:35:00

Module Description:
    This module handles the retrieval, storage, and management of historical market data
    for the Spyder trading system. It interfaces with Interactive Brokers to fetch
    historical price data, option data, and market statistics. The module includes
    caching mechanisms to minimize API calls and provides data preprocessing utilities.
    Updated to use ib_async for IB Gateway 10.37 compatibility.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from datetime import datetime
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
from ib_async import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderH_Storage.SpyderH03_MarketDataCache import MarketDataCache
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_HISTORICAL_REQUESTS_PER_SECOND = 6
CACHE_DIR = Path.home() / ".spyder" / "cache" / "historical"
CACHE_EXPIRY_HOURS = 24

# Historical data durations available from IB
IB_DURATIONS = ["1 D", "2 D", "1 W", "2 W", "1 M", "2 M", "3 M", "6 M", "1 Y", "2 Y"]

# Bar sizes available from IB
IB_BAR_SIZES = [
    "1 sec",
    "5 secs",
    "10 secs",
    "15 secs",
    "30 secs",
    "1 min",
    "2 mins",
    "3 mins",
    "5 mins",
    "10 mins",
    "15 mins",
    "20 mins",
    "30 mins",
    "1 hour",
    "2 hours",
    "3 hours",
    "4 hours",
    "8 hours",
    "1 day",
    "1 week",
    "1 month",
]

# What to show options for historical data
WHAT_TO_SHOW_OPTIONS = [
    "TRADES",
    "MIDPOINT",
    "BID",
    "ASK",
    "BID_ASK",
    "HISTORICAL_VOLATILITY",
    "OPTION_IMPLIED_VOLATILITY",
    "REBATE_RATE",
    "FEE_RATE",
    "YIELD_BID",
    "YIELD_ASK",
]


# ==============================================================================
# ENUMS
# ==============================================================================
class DataType(Enum):
    """Types of market data that can be requested"""

    TRADES = "TRADES"
    MIDPOINT = "MIDPOINT"
    BID = "BID"
    ASK = "ASK"
    BID_ASK = "BID_ASK"
    HISTORICAL_VOLATILITY = "HISTORICAL_VOLATILITY"
    OPTION_IMPLIED_VOLATILITY = "OPTION_IMPLIED_VOLATILITY"


class BarSize(Enum):
    """Bar size enumeration for historical data"""

    SEC_1 = "1 sec"
    SEC_5 = "5 secs"
    SEC_10 = "10 secs"
    SEC_15 = "15 secs"
    SEC_30 = "30 secs"
    MIN_1 = "1 min"
    MIN_2 = "2 mins"
    MIN_3 = "3 mins"
    MIN_5 = "5 mins"
    MIN_10 = "10 mins"
    MIN_15 = "15 mins"
    MIN_20 = "20 mins"
    MIN_30 = "30 mins"
    HOUR_1 = "1 hour"
    HOUR_2 = "2 hours"
    HOUR_3 = "3 hours"
    HOUR_4 = "4 hours"
    HOUR_8 = "8 hours"
    DAY_1 = "1 day"
    WEEK_1 = "1 week"
    MONTH_1 = "1 month"


class Duration(Enum):
    """Duration enumeration for historical data requests"""

    DAY_1 = "1 D"
    DAY_2 = "2 D"
    WEEK_1 = "1 W"
    WEEK_2 = "2 W"
    MONTH_1 = "1 M"
    MONTH_2 = "2 M"
    MONTH_3 = "3 M"
    MONTH_6 = "6 M"
    YEAR_1 = "1 Y"
    YEAR_2 = "2 Y"


class RequestStatus(Enum):
    """Status of a historical data request"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class HistoricalDataRequest:
    """Represents a historical data request"""

    contract: Contract
    end_date: datetime
    duration: str
    bar_size: str
    what_to_show: str
    use_rth: bool = True
    format_date: int = 1
    keep_up_to_date: bool = False
    chart_options: List[str] = field(default_factory=list)

    # Request metadata
    request_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    status: RequestStatus = RequestStatus.PENDING
    priority: int = 5  # 1=highest, 10=lowest


@dataclass
class HistoricalBarData:
    """Historical bar data structure"""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float  # Weighted average price
    count: int  # Number of trades

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "wap": self.wap,
            "count": self.count,
        }


@dataclass
class HistoricalDataResponse:
    """Response structure for historical data"""

    request_id: int
    symbol: str
    bars: List[HistoricalBarData]
    status: RequestStatus
    error_message: Optional[str] = None
    total_bars: int = 0
    cache_hit: bool = False
    execution_time_ms: float = 0.0


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class HistoricalDataManager:
    """
    Historical data management with caching and rate limiting.

    Handles retrieval, storage, and management of historical market data
    from Interactive Brokers with intelligent caching and request optimization.
    """

    def __init__(self, ib_client: SpyderClient, event_manager: EventManager):
        """
        Initialize Historical Data Manager.

        Args:
            ib_client: Connected SpyderClient instance
            event_manager: Event manager for publishing updates
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Request management
        self.active_requests: Dict[int, HistoricalDataRequest] = {}
        self.request_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.next_request_id = 1000
        self.request_lock = threading.RLock()

        # Rate limiting
        self.last_request_time = 0.0
        self.request_count = 0
        self.rate_limit_window = 1.0  # 1 second

        # Caching
        self.cache_enabled = True
        self.cache_dir = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = MarketDataCache(str(self.cache_dir))

        # Worker thread
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None

        # Trading calendar for business day calculations
        self.trading_calendar = TradingCalendar()

        # Response storage
        self.responses: Dict[int, HistoricalDataResponse] = {}

        # Setup callbacks
        self._setup_callbacks()

        self.logger.info("Historical Data Manager initialized")

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def start(self) -> bool:
        """
        Start the historical data manager.

        Returns:
            True if started successfully
        """
        try:
            if self.running:
                self.logger.warning("Historical Data Manager already running")
                return True

            if not self.ib_client.is_connected():
                self.logger.error("IB client not connected")
                return False

            self.running = True

            # Start worker thread
            self.worker_thread = threading.Thread(
                target=self._worker_loop, name="HistoricalDataWorker", daemon=True
            )
            self.worker_thread.start()

            self.logger.info("Historical Data Manager started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Historical Data Manager: {e}")
            return False

    def stop(self):
        """Stop the historical data manager"""
        try:
            self.running = False

            # Cancel all active requests
            with self.request_lock:
                for req_id in list(self.active_requests.keys()):
                    self.ib_client.ib.cancelHistoricalData(req_id)

                self.active_requests.clear()

            # Stop worker thread
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5.0)

            self.logger.info("Historical Data Manager stopped")

        except Exception as e:
            self.logger.error(f"Error stopping Historical Data Manager: {e}")

    def request_historical_data(
        self,
        contract: Contract,
        end_date: Optional[datetime] = None,
        duration: str = "1 D",
        bar_size: str = "1 min",
        data_type: str = "TRADES",
        use_rth: bool = True,
        priority: int = 5,
    ) -> int:
        """
        Request historical data for a contract.

        Args:
            contract: IB contract object
            end_date: End date for data (defaults to now)
            duration: Data duration (e.g., "1 D", "1 W", "1 M")
            bar_size: Bar size (e.g., "1 min", "5 mins", "1 hour")
            data_type: Type of data to retrieve
            use_rth: Use regular trading hours only
            priority: Request priority (1=highest, 10=lowest)

        Returns:
            Request ID for tracking
        """
        try:
            # Validate inputs
            if duration not in IB_DURATIONS:
                raise ValueError(f"Invalid duration: {duration}")

            if bar_size not in IB_BAR_SIZES:
                raise ValueError(f"Invalid bar size: {bar_size}")

            if data_type not in WHAT_TO_SHOW_OPTIONS:
                raise ValueError(f"Invalid data type: {data_type}")

            # Default end date
            if end_date is None:
                end_date = datetime.now()

            # Check cache first
            cache_key = self._generate_cache_key(
                contract, end_date, duration, bar_size, data_type
            )
            if self.cache_enabled:
                cached_data = self._get_cached_data(cache_key)
                if cached_data is not None:
                    return self._create_cached_response(cached_data, cache_key)

            # Create request
            with self.request_lock:
                request_id = self._get_next_request_id()

                request = HistoricalDataRequest(
                    contract=contract,
                    end_date=end_date,
                    duration=duration,
                    bar_size=bar_size,
                    what_to_show=data_type,
                    use_rth=use_rth,
                    request_id=request_id,
                    priority=priority,
                )

                # Add to queue
                self.request_queue.put((priority, request_id, request))
                self.active_requests[request_id] = request

            self.logger.info(
                f"Queued historical data request {request_id} for {contract.symbol}"
            )
            return request_id

        except Exception as e:
            self.logger.error(f"Error requesting historical data: {e}")
            return -1

    def get_response(self, request_id: int) -> Optional[HistoricalDataResponse]:
        """
        Get response for a request ID.

        Args:
            request_id: Request ID to get response for

        Returns:
            Historical data response or None if not available
        """
        return self.responses.get(request_id)

    def cancel_request(self, request_id: int) -> bool:
        """
        Cancel a historical data request.

        Args:
            request_id: Request ID to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            with self.request_lock:
                if request_id in self.active_requests:
                    # Cancel with IB
                    self.ib_client.ib.cancelHistoricalData(request_id)

                    # Update status
                    request = self.active_requests[request_id]
                    request.status = RequestStatus.FAILED

                    # Create error response
                    response = HistoricalDataResponse(
                        request_id=request_id,
                        symbol=request.contract.symbol,
                        bars=[],
                        status=RequestStatus.FAILED,
                        error_message="Request cancelled by user",
                    )
                    self.responses[request_id] = response

                    # Clean up
                    del self.active_requests[request_id]

                    self.logger.info(f"Cancelled historical data request {request_id}")
                    return True
                else:
                    self.logger.warning(
                        f"Request {request_id} not found or already completed"
                    )
                    return False

        except Exception as e:
            self.logger.error(f"Error cancelling request {request_id}: {e}")
            return False

    def get_cached_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        bar_size: str = "1 min",
    ) -> Optional[pd.DataFrame]:
        """
        Get cached historical data as DataFrame.

        Args:
            symbol: Symbol to get data for
            start_date: Start date
            end_date: End date
            bar_size: Bar size

        Returns:
            DataFrame with historical data or None
        """
        try:
            if not self.cache_enabled:
                return None

            # Generate cache key pattern
            cache_pattern = f"{symbol}_{bar_size}_*"

            # Search cache for matching data
            cached_files = list(self.cache_dir.glob(f"{cache_pattern}.pkl"))

            if not cached_files:
                return None

            # Load and filter data
            all_data = []
            for cache_file in cached_files:
                try:
                    with open(cache_file, "rb") as f:
                        data = pickle.load(f)

                    # Filter by date range
                    df = pd.DataFrame([bar.to_dict() for bar in data])
                    if not df.empty:
                        df["timestamp"] = pd.to_datetime(df["timestamp"])
                        filtered_df = df[
                            (df["timestamp"] >= start_date)
                            & (df["timestamp"] <= end_date)
                        ]
                        if not filtered_df.empty:
                            all_data.append(filtered_df)

                except Exception as e:
                    self.logger.warning(f"Error loading cache file {cache_file}: {e}")
                    continue

            if all_data:
                # Combine and sort
                combined_df = pd.concat(all_data, ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=["timestamp"])
                combined_df = combined_df.sort_values("timestamp")
                return combined_df

            return None

        except Exception as e:
            self.logger.error(f"Error getting cached data: {e}")
            return None

    # ==========================================================================
    # PRIVATE METHODS - WORKER THREAD
    # ==========================================================================

    def _worker_loop(self):
        """Main worker thread loop"""
        self.logger.info("Historical data worker started")

        while self.running:
            try:
                # Check rate limiting
                if not self._check_rate_limit():
                    time.sleep(0.1)
                    continue

                # Get next request
                try:
                    priority, request_id, request = self.request_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Process request
                self._process_request(request)

            except Exception as e:
                self.logger.error(f"Worker loop error: {e}")
                time.sleep(1.0)

        self.logger.info("Historical data worker stopped")

    def _process_request(self, request: HistoricalDataRequest):
        """Process a historical data request"""
        try:
            request.status = RequestStatus.IN_PROGRESS

            # Submit to IB
            end_date_str = request.end_date.strftime("%Y%m%d %H:%M:%S")

            self.ib_client.ib.reqHistoricalData(
                request.request_id,
                request.contract,
                end_date_str,
                request.duration,
                request.bar_size,
                request.what_to_show,
                request.use_rth,
                request.format_date,
                request.keep_up_to_date,
                request.chart_options,
            )

            # Update rate limiting
            self.last_request_time = time.time()
            self.request_count += 1

            self.logger.debug(f"Submitted historical data request {request.request_id}")

        except Exception as e:
            self.logger.error(f"Error processing request {request.request_id}: {e}")

            # Create error response
            response = HistoricalDataResponse(
                request_id=request.request_id,
                symbol=request.contract.symbol,
                bars=[],
                status=RequestStatus.FAILED,
                error_message=str(e),
            )
            self.responses[request.request_id] = response

            # Clean up
            with self.request_lock:
                if request.request_id in self.active_requests:
                    del self.active_requests[request.request_id]

    def _check_rate_limit(self) -> bool:
        """Check if we can make another request based on rate limiting"""
        current_time = time.time()

        # Reset counter if window has passed
        if current_time - self.last_request_time > self.rate_limit_window:
            self.request_count = 0

        # Check if we can make another request
        return self.request_count < MAX_HISTORICAL_REQUESTS_PER_SECOND

    # ==========================================================================
    # PRIVATE METHODS - CACHING
    # ==========================================================================

    def _generate_cache_key(
        self,
        contract: Contract,
        end_date: datetime,
        duration: str,
        bar_size: str,
        data_type: str,
    ) -> str:
        """Generate cache key for request"""
        date_str = end_date.strftime("%Y%m%d")
        return f"{contract.symbol}_{bar_size}_{data_type}_{duration}_{date_str}"

    def _get_cached_data(self, cache_key: str) -> Optional[List[HistoricalBarData]]:
        """Get cached data for a key"""
        try:
            cache_file = self.cache_dir / f"{cache_key}.pkl"

            if not cache_file.exists():
                return None

            # Check if cache is still valid
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age > (CACHE_EXPIRY_HOURS * 3600):
                cache_file.unlink()  # Delete expired cache
                return None

            # Load cached data
            with open(cache_file, "rb") as f:
                data = pickle.load(f)

            return data

        except Exception as e:
            self.logger.warning(f"Error loading cached data for {cache_key}: {e}")
            return None

    def _cache_data(self, cache_key: str, data: List[HistoricalBarData]):
        """Cache historical data"""
        try:
            if not self.cache_enabled:
                return

            cache_file = self.cache_dir / f"{cache_key}.pkl"

            with open(cache_file, "wb") as f:
                pickle.dump(data, f)

            self.logger.debug(f"Cached data for {cache_key}")

        except Exception as e:
            self.logger.warning(f"Error caching data for {cache_key}: {e}")

    def _create_cached_response(
        self, data: List[HistoricalBarData], cache_key: str
    ) -> int:
        """Create response from cached data"""
        # Generate fake request ID
        request_id = self._get_next_request_id()

        # Extract symbol from cache key
        symbol = cache_key.split("_")[0]

        # Create response
        response = HistoricalDataResponse(
            request_id=request_id,
            symbol=symbol,
            bars=data,
            status=RequestStatus.COMPLETED,
            total_bars=len(data),
            cache_hit=True,
        )

        self.responses[request_id] = response

        self.logger.info(f"Served {len(data)} bars from cache for {symbol}")
        return request_id

    # ==========================================================================
    # PRIVATE METHODS - CALLBACKS
    # ==========================================================================

    def _setup_callbacks(self):
        """Setup IB callbacks for historical data"""
        self.ib_client.ib.historicalData = self._on_historical_data
        self.ib_client.ib.historicalDataEnd = self._on_historical_data_end
        self.ib_client.ib.error = self._on_error

    def _on_historical_data(self, req_id: int, bar):
        """Handle incoming historical data"""
        try:
            with self.request_lock:
                if req_id not in self.active_requests:
                    return

                request = self.active_requests[req_id]

                # Create bar data
                bar_data = HistoricalBarData(
                    timestamp=datetime.strptime(bar.date, "%Y%m%d %H:%M:%S"),
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                    wap=float(bar.wap),
                    count=int(bar.count),
                )

                # Add to response
                if req_id not in self.responses:
                    self.responses[req_id] = HistoricalDataResponse(
                        request_id=req_id,
                        symbol=request.contract.symbol,
                        bars=[],
                        status=RequestStatus.IN_PROGRESS,
                    )

                self.responses[req_id].bars.append(bar_data)

        except Exception as e:
            self.logger.error(f"Error processing historical data for {req_id}: {e}")

    def _on_historical_data_end(self, req_id: int, start: str, end: str):
        """Handle end of historical data"""
        try:
            with self.request_lock:
                if req_id not in self.active_requests:
                    return

                request = self.active_requests[req_id]

                if req_id in self.responses:
                    response = self.responses[req_id]
                    response.status = RequestStatus.COMPLETED
                    response.total_bars = len(response.bars)

                    # Cache the data
                    cache_key = self._generate_cache_key(
                        request.contract,
                        request.end_date,
                        request.duration,
                        request.bar_size,
                        request.what_to_show,
                    )
                    self._cache_data(cache_key, response.bars)

                    # Publish event
                    self._publish_completion_event(response)

                    self.logger.info(
                        f"Historical data completed for {req_id}: {response.total_bars} bars"
                    )

                # Clean up
                del self.active_requests[req_id]

        except Exception as e:
            self.logger.error(f"Error completing historical data for {req_id}: {e}")

    def _on_error(self, req_id: int, error_code: int, error_string: str, contract=None):
        """Handle IB errors"""
        if req_id in self.active_requests:
            self.logger.error(
                f"Historical data error [{req_id}]: {error_code} - {error_string}"
            )

            # Create error response
            request = self.active_requests[req_id]
            response = HistoricalDataResponse(
                request_id=req_id,
                symbol=request.contract.symbol,
                bars=[],
                status=RequestStatus.FAILED,
                error_message=f"{error_code}: {error_string}",
            )
            self.responses[req_id] = response

            # Clean up
            with self.request_lock:
                del self.active_requests[req_id]

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================

    def _get_next_request_id(self) -> int:
        """Get next available request ID"""
        req_id = self.next_request_id
        self.next_request_id += 1
        return req_id

    def _publish_completion_event(self, response: HistoricalDataResponse):
        """Publish completion event"""
        try:
            event = Event(
                EventType.MARKET_DATA_HISTORICAL,
                {
                    "request_id": response.request_id,
                    "symbol": response.symbol,
                    "bars_count": response.total_bars,
                    "status": response.status.value,
                    "cache_hit": response.cache_hit,
                },
            )
            self.event_manager.publish(event)

        except Exception as e:
            self.logger.error(f"Error publishing completion event: {e}")


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def create_spy_contract() -> Contract:
    """Create SPY stock contract"""
    from ib_async import Stock

    return Stock("SPY", "SMART", "USD")


def create_spy_option_contract(
    expiry: str, strike: float, option_type: str
) -> Contract:
    """Create SPY option contract"""
    from ib_async import Option

    return Option("SPY", expiry, strike, option_type, "SMART")


def bars_to_dataframe(bars: List[HistoricalBarData]) -> pd.DataFrame:
    """Convert historical bars to pandas DataFrame"""
    data = [bar.to_dict() for bar in bars]
    df = pd.DataFrame(data)
    if not df.empty:
        df.set_index("timestamp", inplace=True)
    return df


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the Historical Data Manager
    from SpyderB_Broker.SpyderB01_SpyderClient import IBConfig, SpyderClient

    # Initialize components
    event_manager = EventManager()
    ib_config = IBConfig(host="127.0.0.1", port=7497, client_id=1)
    ib_client = SpyderClient(ib_config, event_manager)

    # Connect to IBKR
    if ib_client.connect():
        # Create manager
        hist_manager = HistoricalDataManager(ib_client, event_manager)

        # Start manager
        if hist_manager.start():
            # Request SPY daily data
            spy_contract = create_spy_contract()
            request_id = hist_manager.request_historical_data(
                contract=spy_contract,
                duration="5 D",
                bar_size="1 hour",
                data_type="TRADES",
            )

            print(f"Submitted request {request_id} for SPY historical data")

            # Wait for completion
            time.sleep(10)

            # Get response
            response = hist_manager.get_response(request_id)
            if response:
                print(f"Received {response.total_bars} bars for SPY")
                if response.bars:
                    df = bars_to_dataframe(response.bars)
                    print(df.head())

            # Stop manager
            hist_manager.stop()

        ib_client.disconnect()
    else:
        print("Failed to connect to IBKR")
