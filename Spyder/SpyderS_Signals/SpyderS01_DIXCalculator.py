#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderS_Signals
Module: SpyderS01_DIXCalculator.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
try:
    import fcntl  # POSIX-only; Windows falls back to best-effort coordination
    _HAS_FCNTL = True
except ImportError:
    fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False
import json
import os
import time
import warnings
import logging
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from io import StringIO
import pandas as pd
import yfinance as yf
import requests

try:
    from Spyder.SpyderC_MarketData.SpyderC29_DataProviderRouter import get_data_provider as _get_c29_provider
    _C29_AVAILABLE = True
except ImportError:
    _get_c29_provider = None  # type: ignore[assignment]
    _C29_AVAILABLE = False

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback for standalone operation
    SpyderLogger = logging

    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error("%s: %s", code, error)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# FINRA Data Constants
FINRA_BASE_URL = "https://cdn.finra.org/equity/regsho/daily/"
FINRA_FILE_PREFIX = "CNMSshvol"
FINRA_DATE_FORMAT = "%Y%m%d"

# S&P 500 Data Source
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# API Rate Limiting
YFINANCE_DELAY = 0.1  # seconds between requests
BATCH_SIZE = 10  # symbols per batch
BATCH_DELAY = 1.0  # seconds between batches

# Calculation Constants
MIN_VOLUME_THRESHOLD = 0  # minimum volume to include in calculation
# Cover up to a 7-day gap (long weekends + holidays): Sun→Thu needs 4 steps;
# Good Friday long weekends (Fri + Sun)→Mon needs 6. 10 is a safe ceiling.
MAX_RETRY_ATTEMPTS = 10

# Disk cache for market caps (avoids yfinance re-fetch on every startup)
_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
_MARKET_CAPS_CACHE_FILE = os.path.join(_CACHE_DIR, "market_caps_cache.json")
# Advisory lock file: prevents S02 and S07 from running concurrent yfinance fetches
_MARKET_CAPS_LOCK_FILE = os.path.join(_CACHE_DIR, "market_caps_fetch.lock")

class DataUnavailableError(RuntimeError):
    """Raised when required market data cannot be obtained from real sources."""
    pass


# ==============================================================================
# ENUMS
# ==============================================================================
class DataSource(Enum):
    """Data source types"""
    FINRA = "finra"
    YFINANCE = "yfinance"
    WIKIPEDIA = "wikipedia"
    SIMULATED = "simulated"

class CalculationStatus(Enum):
    """Calculation status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SUCCESS = "success"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StockDPI:
    """Data structure for individual stock DPI information"""
    symbol: str
    short_volume: int
    total_volume: int
    dpi: float
    market_cap: float
    weight: float
    contribution: float

@dataclass
class DIXResult:
    """Data structure for DIX calculation results"""
    date: str
    dix_value: float
    dix_percentage: float
    num_components: int
    total_market_cap: float
    breakdown: dict[str, StockDPI]
    calculation_time: datetime
    metadata: dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDIXCalculator:
    """
    Full S&P 500 DIX (Dark Index) Calculator.

    This class provides the complete implementation of DIX calculation using
    all S&P 500 components. It manages data fetching from FINRA, market cap
    retrieval from yfinance, and the dollar-weighted DIX calculation.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        sp500_symbols: List of S&P 500 symbols
        market_caps: Dictionary of symbol to market cap
        finra_data: FINRA short sale volume data

    Example:
        >>> calculator = SpyderDIXCalculator()
        >>> calculator.initialize()
        >>> results = calculator.calculate_dix()
    """

    def __init__(self):
        """Initialize the DIX Calculator."""
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler()

        self.sp500_symbols = []
        self.market_caps = {}
        self.finra_data = None
        self.status = CalculationStatus.PENDING

        # Suppress warnings
        warnings.filterwarnings('ignore')

        # Try to warm the in-memory cache from disk immediately
        self._load_market_caps_from_disk()

        self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize DIX calculator components.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing DIX Calculator...")

            # Fetch S&P 500 constituents
            if not self._fetch_sp500_constituents():
                raise Exception("Failed to fetch S&P 500 constituents")

            self.logger.info("Initialized with %s S&P 500 symbols", len(self.sp500_symbols))
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            self.error_handler.handle_error(e, "DIX_INIT_ERROR")
            return False


    def calculate_dix(self, date: str = None):
        """Calculate DIX using available data."""
        try:
            # Try to fetch S&P 500 symbols if not loaded
            if not self.sp500_symbols:
                self._fetch_sp500_constituents()

            # If still no symbols, use simulated data
            if not self.sp500_symbols or len(self.sp500_symbols) == 0:
                return self._calculate_dix_simulated()

            # Regular calculation
            result = self._calculate_dix_internal(date)
            if result:
                return result
            else:
                return self._calculate_dix_simulated()

        except Exception as e:
            self.logger.warning("DIX calculation failed: %s, using simulated data", e)
            return self._calculate_dix_simulated()

    def _calculate_dix_simulated(self):
        """Simulation removed — raise DataUnavailableError when real data is unavailable."""
        raise DataUnavailableError(
            "DIX data is unavailable: FINRA short volume data could not be fetched. "
            "Check network connectivity and FINRA data source availability. "
            "Simulated DIX values have been disabled to prevent fake signals."
        )

    def run_calculation(self, date: str | None = None) -> dict | None:
        """
        Run complete DIX calculation process (legacy interface).

        Args:
            date: Date in YYYYMMDD format (None for latest)

        Returns:
            Dictionary with results or None
        """
        result = self.calculate_dix(date)

        if result:
            # Convert to legacy format for compatibility
            return {
                'dix': result.dix_value,
                'dix_percentage': result.dix_percentage,
                'date': result.date,
                'num_symbols': result.num_components,
                'total_market_cap': result.total_market_cap,
                'breakdown': {
                    symbol: {
                        'dpi': comp.dpi,
                        'market_cap': comp.market_cap,
                        'weighted_dpi': comp.dpi * comp.market_cap,
                        'weight': comp.weight
                    }
                    for symbol, comp in result.breakdown.items()
                },
                'metadata': result.metadata
            }

        return None

    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    def _fetch_sp500_constituents(self) -> bool:
        """
        Fetch current S&P 500 constituents from Wikipedia.

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info("Fetching S&P 500 constituents from Wikipedia...")

            # Read S&P 500 list — Wikipedia blocks urllib's default UA with 403;
            # fetch via requests with a browser UA, then parse the HTML string.
            _wiki_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            }
            _resp = requests.get(SP500_WIKI_URL, headers=_wiki_headers, timeout=30)
            _resp.raise_for_status()
            from io import StringIO as _StringIO
            tables = pd.read_html(_StringIO(_resp.text))
            sp500_table = tables[0]

            # Extract and clean symbols
            symbols = sp500_table['Symbol'].tolist()
            self.sp500_symbols = [str(symbol).replace('.', '-') for symbol in symbols]

            self.logger.info("Fetched %s S&P 500 constituents", len(self.sp500_symbols))
            return True

        except Exception as e:
            self.logger.error("Error fetching S&P 500 constituents: %s", e)

            # Fallback list
            self.sp500_symbols = self._get_fallback_symbols()
            self.logger.warning("Using fallback list of %s symbols", len(self.sp500_symbols))
            return True

    def _load_market_caps_from_disk(self) -> bool:
        """Load market caps from the disk cache if today's data is present.

        Returns:
            True if today's cache was loaded, False otherwise.
        """
        today = datetime.now().strftime("%Y%m%d")
        if not os.path.exists(_MARKET_CAPS_CACHE_FILE):
            return False
        try:
            with open(_MARKET_CAPS_CACHE_FILE, "r") as fh:
                cached = json.load(fh)
            if cached.get("date") == today and cached.get("caps"):
                self.market_caps = cached["caps"]
                self._market_caps_date = today
                self.logger.info(
                    "Market caps loaded from disk cache (%s symbols, date=%s)",
                    len(self.market_caps), today,
                )
                return True
        except Exception as exc:
            self.logger.warning("Could not read market cap disk cache: %s", exc)
        return False

    def _save_market_caps_to_disk(self) -> None:
        """Persist the current market_caps dict to the disk cache."""
        today = datetime.now().strftime("%Y%m%d")
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            payload = {"date": today, "caps": self.market_caps}
            tmp = _MARKET_CAPS_CACHE_FILE + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(payload, fh)
            os.replace(tmp, _MARKET_CAPS_CACHE_FILE)  # atomic on Linux
            self.logger.info(
                "Market caps saved to disk cache (%s symbols)", len(self.market_caps)
            )
        except Exception as exc:
            self.logger.warning("Could not write market cap disk cache: %s", exc)

    def _fetch_market_caps(self) -> None:
        """Fetch market capitalization data for all symbols.

        Check order:
        1. In-memory cache valid for today → return immediately.
        2. Disk cache valid for today → load and return.
        3. Fetch from yfinance (slow, ~6 min) → save to disk when done.
        """
        today = datetime.now().strftime("%Y%m%d")
        # 1. In-memory hit
        if self.market_caps and getattr(self, "_market_caps_date", None) == today:
            self.logger.debug("Market caps in-memory cache hit for %s", today)
            return
        # 2. Disk cache hit (covers restarts within the same trading day)
        if self._load_market_caps_from_disk():
            return

        # 3. Full yfinance fetch — serialised with a file lock so that concurrent
        #    callers (S02 scheduler + S07 orchestrator both start at launch) don't
        #    race against each other and hit yfinance rate limits.
        os.makedirs(_CACHE_DIR, exist_ok=True)
        self.logger.debug("Waiting for market-cap fetch lock…")
        with open(_MARKET_CAPS_LOCK_FILE, "w") as _lock_fh:
            if _HAS_FCNTL:
                fcntl.flock(_lock_fh, fcntl.LOCK_EX)  # blocks until previous fetch done
            try:
                # Re-check: another process may have populated the cache while we waited
                if self._load_market_caps_from_disk():
                    self.logger.info("Market caps ready from peer fetch — skipping yfinance")
                    return

                self.logger.info(
                    "Fetching market cap data for %s symbols via yfinance (one-time per day) …",
                    len(self.sp500_symbols),
                )
                self.market_caps = {}
                failed_symbols = []
                total_batches = (len(self.sp500_symbols) - 1) // BATCH_SIZE + 1
                for i in range(0, len(self.sp500_symbols), BATCH_SIZE):
                    batch = self.sp500_symbols[i:i + BATCH_SIZE]
                    batch_num = i // BATCH_SIZE + 1
                    self.logger.debug("Market cap batch %s/%s", batch_num, total_batches)

                    for symbol in batch:
                        try:
                            ticker = yf.Ticker(symbol)
                            info = ticker.info
                            market_cap = self._extract_market_cap(info)
                            if market_cap and market_cap > 0:
                                self.market_caps[symbol] = float(market_cap)
                            else:
                                failed_symbols.append(symbol)
                        except Exception as e:
                            failed_symbols.append(symbol)
                            self.logger.warning("Error fetching %s: %s", symbol, e)
                        time.sleep(YFINANCE_DELAY)

                    time.sleep(BATCH_DELAY)

                self.logger.info("Fetched market cap for %s symbols", len(self.market_caps))
                if failed_symbols:
                    self.logger.warning("Failed: %s symbols", len(failed_symbols))
                self._market_caps_date = today
                # Persist so next startup is instant
                self._save_market_caps_to_disk()
            finally:
                if _HAS_FCNTL:
                    fcntl.flock(_lock_fh, fcntl.LOCK_UN)

    def _download_finra_data(self, date: str) -> None:
        """
        Download FINRA short sale volume data.

        Args:
            date: Date in YYYYMMDD format
        """
        self.logger.info("Downloading FINRA data for %s...", date)

        url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{date}.txt"

        # FINRA's CDN blocks the default Python-requests User-Agent with HTTP 403.
        # Presenting a realistic browser UA + Accept headers bypasses the block.
        _headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/plain,text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.finra.org/",
        }

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, headers=_headers, timeout=30)
                response.raise_for_status()

                # Parse data
                self.finra_data = pd.read_csv(StringIO(response.text), sep='|')
                self.logger.info("Downloaded FINRA data: %s records", len(self.finra_data))
                return

            except Exception as e:
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    # Try previous day
                    prev_date = (datetime.strptime(date, FINRA_DATE_FORMAT) -
                               timedelta(days=1)).strftime(FINRA_DATE_FORMAT)
                    date = prev_date
                    url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{date}.txt"
                    self.logger.warning("Retrying with %s", prev_date)
                else:
                    raise Exception(f"Failed to download FINRA data: {e}")

    # ==========================================================================
    # PRIVATE METHODS - CALCULATION
    # ==========================================================================
    def _calculate_all_dpi(self) -> dict[str, StockDPI]:
        """
        Calculate DPI for all S&P 500 symbols.

        Returns:
            Dictionary mapping symbols to StockDPI objects
        """
        self.logger.info("Calculating DPI for S&P 500 components...")

        dpi_data = {}

        # Filter FINRA data for S&P 500 symbols
        sp500_finra = self.finra_data[
            self.finra_data['Symbol'].isin(self.sp500_symbols)
        ].copy()

        self.logger.info("Found FINRA data for %s symbols", len(sp500_finra))

        for _, row in sp500_finra.iterrows():
            symbol = row['Symbol']
            short_volume = row['ShortVolume']
            total_volume = row['TotalVolume']

            if total_volume > MIN_VOLUME_THRESHOLD:
                dpi = short_volume / total_volume

                # Get market cap
                market_cap = self.market_caps.get(symbol, 0)

                if market_cap > 0:
                    dpi_data[symbol] = StockDPI(
                        symbol=symbol,
                        short_volume=short_volume,
                        total_volume=total_volume,
                        dpi=dpi,
                        market_cap=market_cap,
                        weight=0,  # Will be calculated later
                        contribution=0  # Will be calculated later
                    )

        self.logger.info("Calculated DPI for %s symbols", len(dpi_data))
        return dpi_data

    def _calculate_weighted_dix(self, dpi_data: dict[str, StockDPI]) -> tuple[float, dict[str, StockDPI]]:
        """
        Calculate dollar-weighted DIX.

        Args:
            dpi_data: Dictionary of StockDPI objects

        Returns:
            Tuple of (DIX value, updated breakdown)
        """
        if not dpi_data:
            raise ValueError("No DPI data available for calculation")

        # Calculate total market cap
        total_market_cap = sum(stock.market_cap for stock in dpi_data.values())

        if total_market_cap == 0:
            raise ValueError("Total market cap is zero")

        # Calculate weights and contributions
        weighted_dpi_sum = 0

        for _symbol, stock in dpi_data.items():
            stock.weight = stock.market_cap / total_market_cap
            stock.contribution = stock.dpi * stock.weight
            weighted_dpi_sum += stock.dpi * stock.market_cap

        # Calculate DIX
        dix = weighted_dpi_sum / total_market_cap

        self.logger.info(f"DIX calculated: {dix:.4f} ({dix*100:.2f}%)")
        self.logger.info(f"Based on {len(dpi_data)} components, "
                        f"total market cap: ${total_market_cap:,.0f}")

        return dix, dpi_data

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_latest_trading_date(self) -> str:
        """Get latest trading date in YYYYMMDD format."""
        today = datetime.now()

        # If weekend, go back to Friday
        if today.weekday() >= 5:
            days_back = today.weekday() - 4
            target_date = today - timedelta(days=days_back)
        else:
            target_date = today

        return target_date.strftime(FINRA_DATE_FORMAT)

    def _extract_market_cap(self, info: dict) -> float | None:
        """Extract market cap from yfinance info dict."""
        # Try different keys
        for key in ['marketCap', 'market_cap', 'sharesOutstanding']:
            if key in info and info[key] is not None:
                if key == 'sharesOutstanding':
                    # Calculate from shares and price
                    shares = info[key]
                    price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if shares and price:
                        return shares * price
                else:
                    return info[key]

        return None

    def _get_fallback_symbols(self) -> list[str]:
        """Get fallback list of major S&P 500 symbols."""
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
            'UNH', 'JNJ', 'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'BAC',
            'ABBV', 'PFE', 'AVGO', 'KO', 'MRK', 'TMO', 'COST', 'PEP', 'WMT',
            'CSCO', 'ABT', 'ACN', 'MCD', 'VZ', 'ADBE', 'NEE', 'DHR', 'TXN',
            'BMY', 'LIN', 'ORCL', 'PM', 'CRM', 'NFLX', 'WFC', 'DIS', 'CMCSA',
            'NKE', 'AMD', 'T', 'UPS', 'QCOM', 'RTX', 'LOW', 'SPGI', 'HON'
        ]

    def _calculate_dix_internal(self, date: str | None = None) -> "DIXResult | None":
        """
        Orchestrate the full DIX calculation pipeline.

        Down# Skip FINRA re-download when we already have data for this date
            if self.finra_data is None or getattr(self, "_finra_date", None) != date:
                self._download_finra_data(date)
                self._finra_date = date
            else:
                self.logger.debug("FINRA data for %s already cached — skipping download", date)
fetches market caps, computes
        DPI for each S&P 500 component, and returns a weighted DIXResult.

        Args:
            date: Date in YYYYMMDD format (None = latest trading day).

        Returns:
            DIXResult on success, or None if any step fails.
        """
        try:
            if date is None:
                date = self._get_latest_trading_date()

            # Skip FINRA re-download when we already have data for this date
            if self.finra_data is None or getattr(self, "_finra_date", None) != date:
                self._download_finra_data(date)
                self._finra_date = date
            else:
                self.logger.debug("FINRA data for %s already cached — skipping download", date)

            self._fetch_market_caps()

            dpi_data = self._calculate_all_dpi()
            if not dpi_data:
                self.logger.warning("No DPI data computed — FINRA/market-cap data insufficient")
                return None

            dix, breakdown = self._calculate_weighted_dix(dpi_data)
            total_market_cap = sum(s.market_cap for s in breakdown.values())

            return DIXResult(
                date=date,
                dix_value=dix,
                dix_percentage=dix * 100,
                num_components=len(breakdown),
                total_market_cap=total_market_cap,
                breakdown=breakdown,
                calculation_time=datetime.now(),
                metadata={"source": "FINRA", "method": "market_cap_weighted"},
            )
        except Exception as e:
            self.logger.warning("_calculate_dix_internal failed: %s", e)
            return None

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up module resources."""
        self.sp500_symbols = []
        self.market_caps = {}
        self.finra_data = None
        self.logger.info("DIX Calculator cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def calculate_dix_for_date(date: str) -> float | None:
    """
    Helper function to calculate DIX for a specific date.

    Args:
        date: Date in YYYYMMDD format

    Returns:
        DIX percentage or None
    """
    try:
        calculator = SpyderDIXCalculator()
        calculator.initialize()
        result = calculator.calculate_dix(date)
        return result.dix_percentage if result else None
    except Exception as e:
        logging.error("Error calculating DIX: %s", e)
        return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    calculator = SpyderDIXCalculator()

    if calculator.initialize():

        # Run calculation
        result = calculator.calculate_dix()

        if result:

            # Show top contributors
            sorted_breakdown = sorted(
                result.breakdown.items(),
                key=lambda x: x[1].contribution,
                reverse=True
            )

            for _symbol, _data in sorted_breakdown[:5]:
                pass

        # Cleanup
        calculator.cleanup()
    else:
        pass


# ==============================================================================
# MAIN CALCULATOR CLASS (Fixed for import compatibility)
# ==============================================================================
class DIXCalculator:
    """
    Main DIX Calculator class for compatibility
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Reuse one SpyderDIXCalculator instance across calls so that cached
        # S&P 500 constituents and FINRA data are retained between updates.
        self._inner = SpyderDIXCalculator()

    def calculate_dix_internal(self) -> DIXResult:
        """Internal DIX calculation — delegates to shared SpyderDIXCalculator."""
        return self._inner.calculate_dix()

    def calculate_dix(self):
        """Calculate DIX using available data — raises DataUnavailableError on failure."""
        result = self.calculate_dix_internal()
        if result is None:
            raise DataUnavailableError(
                "DIX calculation returned no result. "
                "Ensure FINRA short volume data is accessible."
            )
        return result

    def calculate_dix_simulated(self) -> dict:
        """Simulation removed — raises DataUnavailableError."""
        raise DataUnavailableError(
            "DIX simulation is disabled. Spyder requires real FINRA short volume "
            "data. Ensure network access to FINRA data sources is available."
        )

# Singleton instance
_calculator_instance = None
_calculator_instance_lock = threading.Lock()


def get_calculator_instance() -> DIXCalculator:
    """Get singleton DIX calculator instance"""
    global _calculator_instance
    if _calculator_instance is None:
        with _calculator_instance_lock:
            if _calculator_instance is None:
                _calculator_instance = DIXCalculator()
    return _calculator_instance
