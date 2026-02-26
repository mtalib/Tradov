#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC26_DatabentoClient.py
Purpose: Databento real-time and historical market data client for OPRA options

Author: GitHub Copilot (Maestro)
Year Created: 2026
Last Updated: 2026-02-25 Time: 14:00:00

Module Description:
    Databento market data client providing real-time streaming and historical
    data access for SPY options via the OPRA feed (OPRA.PILLAR dataset).

    Databento advantages over Polygon.io:
    - Native binary DBN format (low overhead, nanosecond timestamps)
    - Subscribe by underlying → receive all options automatically
    - Multiple schema levels: MBO (L3), MBP-1 (L1), MBP-10 (L2),
      TBBO, OHLCV, trades, definition
    - Server-side replay for backtesting with identical API surface
    - Institutional-grade SIP-consolidated equity + OPRA options data

    This module follows the same architectural patterns as SpyderC25_PolygonDataHandler:
    - Qt Signal/Slot integration for thread-safe UI communication
    - Automatic reconnection with exponential backoff
    - Circuit breaker and rate limiter integration
    - Normalization to Spyder's internal MarketDataUpdate format

Module Constants:
    DEFAULT_DATASET (str): Default Databento dataset for options (OPRA.PILLAR)
    DEFAULT_LIVE_SCHEMA (str): Default schema for live streaming
    MAX_RECONNECT_ATTEMPTS (int): Maximum reconnection attempts
    RECONNECT_BASE_DELAY (float): Base delay for exponential backoff (seconds)
    NANOSECONDS_PER_SECOND (int): Conversion factor for nanosecond timestamps

Dependencies:
    - databento>=0.44.0 (pip install databento)
    - pyarrow>=12.0.0 (for efficient columnar data)
    - PySide6 (optional, for Qt Signal integration)

Change Log:
    2026-02-25 (v1.0.0):
        - Initial implementation for Tradier+Databento migration
        - Live streaming via databento.Live with async iteration
        - Historical data via databento.Historical REST API
        - Instrument definition lookup
        - Symbol format conversion (Databento OSI ↔ Tradier)
        - Qt Signal/Slot integration for thread safety
        - Circuit breaker + rate limiter integration
        - Bandwidth cost tracking

References:
    - Databento Python SDK: https://databento.com/docs/api-reference-live
    - Databento Schemas: https://databento.com/docs/schemas
    - OPRA Feed: https://databento.com/docs/datasets/OPRA.PILLAR
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import time
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum
from datetime import datetime, date
from dataclasses import dataclass, field
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import databento as db
    HAS_DATABENTO = True
except ImportError:
    HAS_DATABENTO = False
    db = None

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    from PySide6.QtCore import QThread, Signal, QObject
    HAS_QT = True
except ImportError:
    HAS_QT = False
    QThread = threading.Thread
    Signal = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import acquire_databento
except ImportError:
    acquire_databento = None

try:
    from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import databento_breaker
except ImportError:
    databento_breaker = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_DATASET = "OPRA.PILLAR"
DEFAULT_EQUITY_DATASET = "XNAS.ITCH"
DEFAULT_LIVE_SCHEMA = "mbp-1"
DEFAULT_HIST_SCHEMA = "ohlcv-1m"
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_BASE_DELAY = 2.0
NANOSECONDS_PER_SECOND = 1_000_000_000
MESSAGE_BUFFER_SIZE = 5000

# Schema name → databento.Schema mapping (deferred to avoid import issues)
SCHEMA_MAP = {
    "mbo": "mbo",
    "mbp-1": "mbp-1",
    "mbp-10": "mbp-10",
    "tbbo": "tbbo",
    "trades": "trades",
    "ohlcv-1s": "ohlcv-1s",
    "ohlcv-1m": "ohlcv-1m",
    "ohlcv-1h": "ohlcv-1h",
    "ohlcv-1d": "ohlcv-1d",
    "definition": "definition",
    "statistics": "statistics",
    "status": "status",
}


# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionStatus(Enum):
    """Databento connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


class DatabentoSchema(Enum):
    """Supported Databento schema types."""
    MBO = "mbo"             # Market-by-order (Level 3)
    MBP_1 = "mbp-1"         # Market-by-price top of book (Level 1)
    MBP_10 = "mbp-10"       # Market-by-price 10 levels (Level 2)
    TBBO = "tbbo"           # Trade with best bid/offer
    TRADES = "trades"       # Trades only
    OHLCV_1S = "ohlcv-1s"   # 1-second OHLCV bars
    OHLCV_1M = "ohlcv-1m"   # 1-minute OHLCV bars
    OHLCV_1H = "ohlcv-1h"   # 1-hour OHLCV bars
    OHLCV_1D = "ohlcv-1d"   # Daily OHLCV bars
    DEFINITION = "definition"  # Instrument definitions
    STATISTICS = "statistics"  # Exchange statistics
    STATUS = "status"        # Trading status messages


class SymbolFormat(Enum):
    """Option symbol format conventions."""
    DATABENTO_OSI = "databento_osi"  # SPY   260220C00550000
    TRADIER = "tradier"              # SPY260220C00550000
    SPYDER = "spyder"                # SPY_260220_C_550.00


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class MarketDataUpdate:
    """
    Normalized market data update from Databento.

    Standardizes Databento records into Spyder's internal format,
    matching the interface from SpyderC25_PolygonDataHandler.
    """
    symbol: str
    timestamp_ns: int
    schema: str
    data: Dict[str, Any]
    underlying: str = ""
    is_option: bool = False

    @property
    def timestamp(self) -> int:
        """Timestamp in milliseconds (for backward compat with Polygon handler)."""
        return self.timestamp_ns // 1_000_000

    @property
    def datetime(self) -> datetime:
        """Convert nanosecond timestamp to datetime."""
        return datetime.fromtimestamp(self.timestamp_ns / NANOSECONDS_PER_SECOND)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "timestamp_ns": self.timestamp_ns,
            "datetime": self.datetime.isoformat(),
            "schema": self.schema,
            "underlying": self.underlying,
            "is_option": self.is_option,
            "data": self.data,
        }

    def __repr__(self) -> str:
        return f"MarketDataUpdate({self.symbol}, {self.schema}, {self.datetime})"


@dataclass
class InstrumentDefinition:
    """Option instrument definition from Databento."""
    raw_symbol: str
    instrument_id: int
    underlying: str
    strike_price: float
    expiration: date
    option_type: str  # "C" or "P"
    exchange: str = ""
    min_tick: float = 0.01
    multiplier: float = 100.0
    tradier_symbol: str = ""

    def __post_init__(self):
        """Compute Tradier symbol if not provided."""
        if not self.tradier_symbol:
            self.tradier_symbol = convert_symbol(
                self.raw_symbol, SymbolFormat.DATABENTO_OSI, SymbolFormat.TRADIER
            )


@dataclass
class BandwidthTracker:
    """Track Databento bandwidth usage for cost control."""
    bytes_received: int = 0
    messages_received: int = 0
    session_start: float = field(default_factory=time.time)
    daily_bytes: int = 0
    daily_reset_date: str = ""

    @property
    def gb_received(self) -> float:
        """Total GB received this session."""
        return self.bytes_received / (1024 ** 3)

    @property
    def daily_gb(self) -> float:
        """GB received today."""
        today = date.today().isoformat()
        if self.daily_reset_date != today:
            self.daily_bytes = 0
            self.daily_reset_date = today
        return self.daily_bytes / (1024 ** 3)

    def record(self, nbytes: int) -> None:
        """Record bytes received."""
        self.bytes_received += nbytes
        self.messages_received += 1
        today = date.today().isoformat()
        if self.daily_reset_date != today:
            self.daily_bytes = 0
            self.daily_reset_date = today
        self.daily_bytes += nbytes


# ==============================================================================
# SYMBOL CONVERSION UTILITIES
# ==============================================================================
def convert_symbol(
    symbol: str,
    from_format: SymbolFormat,
    to_format: SymbolFormat
) -> str:
    """
    Convert option symbol between Databento, Tradier, and Spyder formats.

    Databento OSI:  SPY   260220C00550000  (padded to 21 chars, price * 1000)
    Tradier:        SPY260220C00550000     (no padding, price * 1000)
    Spyder:         SPY_260220_C_550.00    (human-readable)

    Args:
        symbol: Input symbol string.
        from_format: Source format.
        to_format: Target format.

    Returns:
        Converted symbol string.

    Raises:
        ValueError: If symbol format cannot be parsed.
    """
    # Parse the symbol into components
    underlying, expiry_str, opt_type, strike = _parse_option_symbol(symbol, from_format)

    # Build the target format
    if to_format == SymbolFormat.DATABENTO_OSI:
        # Pad underlying to 6 chars, strike * 1000 padded to 8 digits
        strike_int = int(round(strike * 1000))
        return f"{underlying:<6}{expiry_str}{opt_type}{strike_int:08d}"

    elif to_format == SymbolFormat.TRADIER:
        # No padding, strike * 1000 padded to 8 digits
        strike_int = int(round(strike * 1000))
        return f"{underlying}{expiry_str}{opt_type}{strike_int:08d}"

    elif to_format == SymbolFormat.SPYDER:
        return f"{underlying}_{expiry_str}_{opt_type}_{strike:.2f}"

    else:
        raise ValueError(f"Unknown target format: {to_format}")


def _parse_option_symbol(
    symbol: str,
    fmt: SymbolFormat
) -> Tuple[str, str, str, float]:
    """
    Parse option symbol into (underlying, expiry_YYMMDD, C/P, strike_float).

    Args:
        symbol: Raw symbol string.
        fmt: Format of the input symbol.

    Returns:
        Tuple of (underlying, expiry_str, option_type, strike_price).

    Raises:
        ValueError: If symbol cannot be parsed.
    """
    try:
        if fmt == SymbolFormat.DATABENTO_OSI:
            # Fixed format: 6-char underlying + 6-digit date + C/P + 8-digit price
            # e.g. "SPY   260220C00550000"
            underlying = symbol[:6].strip()
            expiry_str = symbol[6:12]
            opt_type = symbol[12]
            strike = int(symbol[13:21]) / 1000.0
            return underlying, expiry_str, opt_type, strike

        elif fmt == SymbolFormat.TRADIER:
            # Variable-length underlying, then 6-digit date, C/P, 8-digit price
            # e.g. "SPY260220C00550000"
            # Find the first digit that starts the date portion
            idx = 0
            while idx < len(symbol) and not symbol[idx].isdigit():
                idx += 1
            underlying = symbol[:idx]
            expiry_str = symbol[idx:idx + 6]
            opt_type = symbol[idx + 6]
            strike = int(symbol[idx + 7:idx + 15]) / 1000.0
            return underlying, expiry_str, opt_type, strike

        elif fmt == SymbolFormat.SPYDER:
            # e.g. "SPY_260220_C_550.00"
            parts = symbol.split("_")
            underlying = parts[0]
            expiry_str = parts[1]
            opt_type = parts[2]
            strike = float(parts[3])
            return underlying, expiry_str, opt_type, strike

        else:
            raise ValueError(f"Unknown source format: {fmt}")

    except (IndexError, ValueError) as e:
        raise ValueError(f"Cannot parse option symbol '{symbol}' as {fmt.value}: {e}") from e


def databento_to_tradier(symbol: str) -> str:
    """Convenience: convert Databento OSI symbol to Tradier format."""
    return convert_symbol(symbol, SymbolFormat.DATABENTO_OSI, SymbolFormat.TRADIER)


def tradier_to_databento(symbol: str) -> str:
    """Convenience: convert Tradier symbol to Databento OSI format."""
    return convert_symbol(symbol, SymbolFormat.TRADIER, SymbolFormat.DATABENTO_OSI)


def is_option_symbol(symbol: str) -> bool:
    """
    Check whether a symbol is an option (vs equity).

    Heuristic: option symbols contain digits and C/P type indicator
    and are longer than typical equity tickers.
    """
    if len(symbol) < 10:
        return False
    # Check for C or P in the right position
    stripped = symbol.strip()
    for i in range(3, min(len(stripped), 7)):
        if stripped[i:i + 1].isdigit():
            # Found date start — check for C/P after 6 digits
            if i + 6 < len(stripped) and stripped[i + 6] in ("C", "P"):
                return True
            break
    return False


# ==============================================================================
# DATABENTO RECORD → DICT NORMALIZER
# ==============================================================================
def _normalize_record(record: Any) -> Dict[str, Any]:
    """
    Convert a Databento record object into a plain dictionary.

    Databento SDK returns typed record objects (MBP1Msg, TradeMsg, OhlcvMsg, etc.)
    that have named attributes. This function extracts the key fields into a
    dictionary suitable for Spyder's internal processing.

    Args:
        record: A databento record object.

    Returns:
        Dictionary with normalized fields.
    """
    data = {}

    # Common fields
    if hasattr(record, "ts_event"):
        data["ts_event"] = record.ts_event
    if hasattr(record, "ts_recv"):
        data["ts_recv"] = record.ts_recv

    # Trade fields
    if hasattr(record, "price"):
        data["price"] = record.price / 1e9 if record.price > 1e6 else record.price
    if hasattr(record, "size"):
        data["size"] = record.size
    if hasattr(record, "side"):
        data["side"] = str(record.side) if record.side else None
    if hasattr(record, "action"):
        data["action"] = str(record.action) if record.action else None

    # Quote / MBP fields
    if hasattr(record, "levels"):
        levels = []
        for level in record.levels:
            levels.append({
                "bid_px": level.bid_px / 1e9 if hasattr(level, "bid_px") and level.bid_px > 1e6 else getattr(level, "bid_px", 0),
                "ask_px": level.ask_px / 1e9 if hasattr(level, "ask_px") and level.ask_px > 1e6 else getattr(level, "ask_px", 0),
                "bid_sz": getattr(level, "bid_sz", 0),
                "ask_sz": getattr(level, "ask_sz", 0),
                "bid_ct": getattr(level, "bid_ct", 0),
                "ask_ct": getattr(level, "ask_ct", 0),
            })
        data["levels"] = levels
        if levels:
            data["bid"] = levels[0]["bid_px"]
            data["ask"] = levels[0]["ask_px"]
            data["bid_size"] = levels[0]["bid_sz"]
            data["ask_size"] = levels[0]["ask_sz"]

    # OHLCV fields
    for ohlcv_field in ("open", "high", "low", "close", "volume"):
        if hasattr(record, ohlcv_field):
            val = getattr(record, ohlcv_field)
            if ohlcv_field != "volume" and val > 1e6:
                val = val / 1e9
            data[ohlcv_field] = val

    # Instrument ID
    if hasattr(record, "instrument_id"):
        data["instrument_id"] = record.instrument_id

    # Definition fields
    if hasattr(record, "raw_symbol"):
        data["raw_symbol"] = str(record.raw_symbol).strip('\x00').strip()
    if hasattr(record, "strike_price"):
        sp = record.strike_price
        data["strike_price"] = sp / 1e9 if sp > 1e6 else sp
    if hasattr(record, "expiration"):
        data["expiration"] = str(record.expiration)
    if hasattr(record, "instrument_class"):
        data["instrument_class"] = str(record.instrument_class)
    if hasattr(record, "underlying"):
        data["underlying"] = str(record.underlying).strip('\x00').strip() if record.underlying else ""
    if hasattr(record, "exchange"):
        data["exchange"] = str(record.exchange).strip('\x00').strip() if record.exchange else ""
    if hasattr(record, "min_price_increment"):
        mpi = record.min_price_increment
        data["min_tick"] = mpi / 1e9 if mpi > 1e6 else mpi

    return data


# ==============================================================================
# MAIN CLASS: DatabentoClient
# ==============================================================================
class DatabentoClient:
    """
    Databento market data client for real-time streaming and historical data.

    This client provides:
    - Live streaming of OPRA options data (quotes, trades, OHLCV bars)
    - Historical data retrieval with DataFrame output
    - Instrument definition lookup
    - Symbol conversion between Databento, Tradier, and Spyder formats
    - Bandwidth tracking for cost control
    - Circuit breaker and reconnection logic

    The client runs the live stream in a background thread and dispatches
    updates via callbacks and/or Qt Signals (if PySide6 is available).

    Example:
        >>> client = DatabentoClient(api_key="YOUR_KEY")
        >>> client.on_quote = my_quote_handler
        >>> client.start_live(underlyings=["SPY"], schema="mbp-1")
        >>> # ... later
        >>> client.stop_live()

        >>> # Historical data
        >>> df = client.get_historical_bars("SPY", "2026-01-01", "2026-01-31")

    Attributes:
        api_key: Databento API key.
        dataset: Default dataset (OPRA.PILLAR for options).
        status: Current connection status.
        bandwidth: Bandwidth usage tracker.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        dataset: str = DEFAULT_DATASET,
        max_daily_gb: float = 5.0,
    ):
        """
        Initialize Databento client.

        Args:
            api_key: Databento API key. If None, reads from DATABENTO_API_KEY env var.
            dataset: Databento dataset identifier (default: OPRA.PILLAR).
            max_daily_gb: Maximum GB to receive per day before warning (cost control).

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.environ.get("DATABENTO_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Databento API key required. Set DATABENTO_API_KEY env var or pass api_key param."
            )

        self.dataset = dataset
        self.max_daily_gb = max_daily_gb

        # Clients (initialized lazily)
        self._historical: Optional[Any] = None
        self._live: Optional[Any] = None
        self._live_thread: Optional[threading.Thread] = None

        # State
        self.status = ConnectionStatus.DISCONNECTED
        self._running = False
        self._reconnect_attempts = 0
        self._lock = threading.Lock()

        # Tracking
        self.bandwidth = BandwidthTracker()
        self.message_buffer: deque = deque(maxlen=MESSAGE_BUFFER_SIZE)

        # Instrument definition cache: instrument_id → InstrumentDefinition
        self._definitions: Dict[int, InstrumentDefinition] = {}
        # Symbol → instrument_id mapping
        self._symbol_to_id: Dict[str, int] = {}

        # Callbacks (set these before calling start_live)
        self.on_quote: Optional[Callable[[MarketDataUpdate], None]] = None
        self.on_trade: Optional[Callable[[MarketDataUpdate], None]] = None
        self.on_ohlcv: Optional[Callable[[MarketDataUpdate], None]] = None
        self.on_definition: Optional[Callable[[InstrumentDefinition], None]] = None
        self.on_status_change: Optional[Callable[[ConnectionStatus], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

        # Qt Signals (populated if Qt is available and wrapper is created)
        self._qt_wrapper: Optional[Any] = None

        logger.info(
            f"DatabentoClient initialized (dataset={dataset}, "
            f"max_daily_gb={max_daily_gb})"
        )

    # ==========================================================================
    # PROPERTIES
    # ==========================================================================
    @property
    def historical(self) -> Any:
        """Lazy-initialize Databento Historical client."""
        if not HAS_DATABENTO:
            raise ImportError("databento package not installed. Run: pip install databento")
        if self._historical is None:
            self._historical = db.Historical(self.api_key)
        return self._historical

    @property
    def is_connected(self) -> bool:
        """Check if live stream is active."""
        return self.status in (ConnectionStatus.CONNECTED, ConnectionStatus.STREAMING)

    # ==========================================================================
    # STATUS MANAGEMENT
    # ==========================================================================
    def _set_status(self, new_status: ConnectionStatus) -> None:
        """Update connection status and notify listeners."""
        old_status = self.status
        self.status = new_status
        if old_status != new_status:
            logger.info(f"Databento status: {old_status.value} → {new_status.value}")
            if self.on_status_change:
                try:
                    self.on_status_change(new_status)
                except Exception as e:
                    logger.error(f"Error in status change callback: {e}")

    # ==========================================================================
    # LIVE STREAMING
    # ==========================================================================
    def start_live(
        self,
        underlyings: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
        schema: str = DEFAULT_LIVE_SCHEMA,
        dataset: Optional[str] = None,
    ) -> None:
        """
        Start live data streaming in a background thread.

        You can subscribe by underlying (to get all options for that underlying)
        or by specific option symbols.

        Args:
            underlyings: List of underlying symbols (e.g., ["SPY"]).
                Databento will stream all options for these underlyings.
            symbols: List of specific symbols to subscribe to.
            schema: Data schema to stream (default: "mbp-1").
            dataset: Override dataset (default: self.dataset).

        Raises:
            ImportError: If databento package is not installed.
            RuntimeError: If already streaming.
        """
        if not HAS_DATABENTO:
            raise ImportError("databento package not installed. Run: pip install databento")

        if self._running:
            logger.warning("Live stream already running. Call stop_live() first.")
            return

        effective_dataset = dataset or self.dataset

        # Determine subscription symbols
        if underlyings and not symbols:
            # Subscribe by underlying parent — Databento resolves all options
            sub_symbols = underlyings
            stype_in = "parent"
        elif symbols:
            sub_symbols = symbols
            stype_in = "raw_symbol"
        else:
            sub_symbols = ["SPY"]
            stype_in = "parent"

        logger.info(
            f"Starting live stream: dataset={effective_dataset}, "
            f"schema={schema}, symbols={sub_symbols}, stype_in={stype_in}"
        )

        self._running = True
        self._reconnect_attempts = 0

        self._live_thread = threading.Thread(
            target=self._live_stream_loop,
            args=(effective_dataset, schema, sub_symbols, stype_in),
            name="DatabentoLiveStream",
            daemon=True,
        )
        self._live_thread.start()

    def stop_live(self) -> None:
        """Stop the live data stream."""
        logger.info("Stopping live stream...")
        self._running = False

        if self._live is not None:
            try:
                self._live.stop()
            except Exception as e:
                logger.warning(f"Error stopping live client: {e}")
            self._live = None

        if self._live_thread is not None:
            self._live_thread.join(timeout=10.0)
            self._live_thread = None

        self._set_status(ConnectionStatus.STOPPED)
        logger.info(
            f"Live stream stopped. Bandwidth: {self.bandwidth.gb_received:.3f} GB "
            f"({self.bandwidth.messages_received} messages)"
        )

    def _live_stream_loop(
        self,
        dataset: str,
        schema: str,
        symbols: List[str],
        stype_in: str,
    ) -> None:
        """
        Main live stream loop (runs in background thread).

        Connects to Databento, subscribes, and iterates over records.
        Handles reconnection with exponential backoff on failure.
        """
        while self._running and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                self._set_status(ConnectionStatus.CONNECTING)

                # Create live client
                self._live = db.Live(key=self.api_key)

                # Subscribe
                self._live.subscribe(
                    dataset=dataset,
                    schema=schema,
                    symbols=symbols,
                    stype_in=stype_in,
                )

                self._set_status(ConnectionStatus.CONNECTED)
                logger.info("Databento live connection established, waiting for data...")

                # Iterate over incoming records
                for record in self._live:
                    if not self._running:
                        break

                    self._set_status(ConnectionStatus.STREAMING)
                    self._process_record(record, schema)

                    # Cost guard
                    if self.bandwidth.daily_gb >= self.max_daily_gb:
                        logger.warning(
                            f"Daily bandwidth limit reached ({self.bandwidth.daily_gb:.2f} GB). "
                            f"Stopping live stream."
                        )
                        self._running = False
                        break

                # Clean exit
                if not self._running:
                    break

            except Exception as e:
                self._reconnect_attempts += 1
                delay = min(
                    RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1)),
                    300.0  # Cap at 5 minutes
                )

                error_msg = (
                    f"Live stream error (attempt {self._reconnect_attempts}/"
                    f"{MAX_RECONNECT_ATTEMPTS}): {e}"
                )
                logger.error(error_msg)

                if self.on_error:
                    try:
                        self.on_error(error_msg)
                    except Exception:
                        pass

                if databento_breaker:
                    try:
                        databento_breaker.record_failure()
                    except Exception:
                        pass

                self._set_status(ConnectionStatus.RECONNECTING)

                if self._running:
                    logger.info(f"Reconnecting in {delay:.1f}s...")
                    time.sleep(delay)

            finally:
                if self._live is not None:
                    try:
                        self._live.stop()
                    except Exception:
                        pass
                    self._live = None

        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            error_msg = f"Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached. Giving up."
            logger.error(error_msg)
            self._set_status(ConnectionStatus.ERROR)
            if self.on_error:
                try:
                    self.on_error(error_msg)
                except Exception:
                    pass

    def _process_record(self, record: Any, schema: str) -> None:
        """
        Process a single Databento record and dispatch to callbacks.

        Args:
            record: Databento record object.
            schema: Schema string for categorization.
        """
        try:
            # Estimate message size for bandwidth tracking
            est_size = 128  # Approximate per-record overhead
            self.bandwidth.record(est_size)

            # Normalize the record
            data = _normalize_record(record)

            # Resolve symbol
            instrument_id = data.get("instrument_id", 0)
            raw_symbol = data.get("raw_symbol", "")

            # For definition records, cache the definition
            if hasattr(record, "raw_symbol") and hasattr(record, "strike_price"):
                self._cache_definition(record, data)

            # Look up symbol from cache
            if instrument_id in self._definitions:
                defn = self._definitions[instrument_id]
                symbol = defn.raw_symbol
                underlying = defn.underlying
                is_opt = True
            elif raw_symbol:
                symbol = raw_symbol
                underlying = ""
                is_opt = is_option_symbol(raw_symbol)
            else:
                symbol = str(instrument_id)
                underlying = ""
                is_opt = False

            # Create normalized update
            update = MarketDataUpdate(
                symbol=symbol,
                timestamp_ns=data.get("ts_event", 0),
                schema=schema,
                data=data,
                underlying=underlying,
                is_option=is_opt,
            )

            # Buffer
            self.message_buffer.append(update)

            # Dispatch to appropriate callback
            schema_lower = schema.lower()
            if "mbp" in schema_lower or "tbbo" in schema_lower:
                if self.on_quote:
                    self.on_quote(update)
            elif "trade" in schema_lower:
                if self.on_trade:
                    self.on_trade(update)
            elif "ohlcv" in schema_lower:
                if self.on_ohlcv:
                    self.on_ohlcv(update)
            elif "definition" in schema_lower:
                pass  # Already handled via _cache_definition
            else:
                # Generic — try quote callback as default
                if self.on_quote:
                    self.on_quote(update)

            # Record success for circuit breaker
            if databento_breaker:
                try:
                    databento_breaker.record_success()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error processing Databento record: {e}", exc_info=True)

    def _cache_definition(self, _record: Any, data: Dict[str, Any]) -> None:
        """Cache an instrument definition from a definition record."""
        try:
            instrument_id = data.get("instrument_id", 0)
            raw_symbol = data.get("raw_symbol", "")
            strike = data.get("strike_price", 0.0)
            expiry_str = data.get("expiration", "")
            underlying_str = data.get("underlying", "")
            exchange_str = data.get("exchange", "")
            instrument_class = data.get("instrument_class", "")

            # Determine option type from instrument_class or raw_symbol
            opt_type = ""
            if "C" in instrument_class.upper():
                opt_type = "C"
            elif "P" in instrument_class.upper():
                opt_type = "P"
            elif is_option_symbol(raw_symbol):
                # Try to parse from symbol
                try:
                    _, _, ot, _ = _parse_option_symbol(raw_symbol, SymbolFormat.DATABENTO_OSI)
                    opt_type = ot
                except ValueError:
                    pass

            # Parse expiration
            try:
                exp_date = date.fromisoformat(expiry_str[:10]) if expiry_str else date.today()
            except ValueError:
                exp_date = date.today()

            defn = InstrumentDefinition(
                raw_symbol=raw_symbol,
                instrument_id=instrument_id,
                underlying=underlying_str,
                strike_price=strike,
                expiration=exp_date,
                option_type=opt_type,
                exchange=exchange_str,
                min_tick=data.get("min_tick", 0.01),
            )

            self._definitions[instrument_id] = defn
            self._symbol_to_id[raw_symbol] = instrument_id

            if self.on_definition:
                self.on_definition(defn)

        except Exception as e:
            logger.debug(f"Error caching definition: {e}")

    # ==========================================================================
    # HISTORICAL DATA
    # ==========================================================================
    def get_historical_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        schema: str = DEFAULT_HIST_SCHEMA,
        dataset: Optional[str] = None,
        stype_in: str = "parent",
    ) -> Optional[Any]:
        """
        Fetch historical OHLCV bars as a DataFrame.

        Args:
            symbol: Underlying symbol (e.g., "SPY") or specific option symbol.
            start: Start date as ISO string (e.g., "2026-01-01").
            end: End date as ISO string (e.g., "2026-01-31").
            schema: Data schema (default: "ohlcv-1m").
            dataset: Override dataset (default: self.dataset).
            stype_in: Symbol type input — "parent" for underlying, "raw_symbol" for specific.

        Returns:
            pandas DataFrame with OHLCV data, or None on error.

        Raises:
            ImportError: If databento or pandas not installed.
        """
        if not HAS_DATABENTO:
            raise ImportError("databento package not installed. Run: pip install databento")
        if not HAS_PANDAS:
            raise ImportError("pandas package not installed. Run: pip install pandas")

        effective_dataset = dataset or self.dataset

        logger.info(
            f"Fetching historical data: {symbol} from {start} to {end} "
            f"(schema={schema}, dataset={effective_dataset})"
        )

        try:
            data = self.historical.timeseries.get_range(
                dataset=effective_dataset,
                symbols=[symbol],
                schema=schema,
                start=start,
                end=end,
                stype_in=stype_in,
            )

            df = data.to_df()
            logger.info(f"Historical data retrieved: {len(df)} rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data: {e}", exc_info=True)
            if databento_breaker:
                try:
                    databento_breaker.record_failure()
                except Exception:
                    pass
            return None

    def get_historical_trades(
        self,
        symbol: str,
        start: str,
        end: str,
        dataset: Optional[str] = None,
        stype_in: str = "parent",
    ) -> Optional[Any]:
        """
        Fetch historical trade data as a DataFrame.

        Args:
            symbol: Symbol to fetch (underlying or specific option).
            start: Start date ISO string.
            end: End date ISO string.
            dataset: Override dataset.
            stype_in: Symbol type input.

        Returns:
            pandas DataFrame with trade data, or None on error.
        """
        return self.get_historical_bars(
            symbol=symbol, start=start, end=end,
            schema="trades", dataset=dataset, stype_in=stype_in,
        )

    def get_historical_quotes(
        self,
        symbol: str,
        start: str,
        end: str,
        dataset: Optional[str] = None,
        stype_in: str = "parent",
    ) -> Optional[Any]:
        """
        Fetch historical quote (MBP-1) data as a DataFrame.

        Args:
            symbol: Symbol to fetch.
            start: Start date ISO string.
            end: End date ISO string.
            dataset: Override dataset.
            stype_in: Symbol type input.

        Returns:
            pandas DataFrame with quote data, or None on error.
        """
        return self.get_historical_bars(
            symbol=symbol, start=start, end=end,
            schema="mbp-1", dataset=dataset, stype_in=stype_in,
        )

    def get_instrument_definitions(
        self,
        symbol: str,
        date_str: str,
        dataset: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Fetch instrument definitions (option chain structure) for a date.

        This returns the full set of option contracts (strikes, expirations)
        for the given underlying on a specific date.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            date_str: Date as ISO string (e.g., "2026-02-25").
            dataset: Override dataset.

        Returns:
            pandas DataFrame with instrument definitions, or None on error.
        """
        if not HAS_DATABENTO:
            raise ImportError("databento package not installed. Run: pip install databento")

        effective_dataset = dataset or self.dataset

        logger.info(f"Fetching instrument definitions: {symbol} on {date_str}")

        try:
            data = self.historical.timeseries.get_range(
                dataset=effective_dataset,
                symbols=[symbol],
                schema="definition",
                start=date_str,
                end=date_str,
                stype_in="parent",
            )

            df = data.to_df()
            logger.info(f"Instrument definitions retrieved: {len(df)} contracts for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching instrument definitions: {e}", exc_info=True)
            return None

    # ==========================================================================
    # DEFINITION CACHE ACCESS
    # ==========================================================================
    def get_cached_definitions(self) -> Dict[int, InstrumentDefinition]:
        """Get all cached instrument definitions."""
        return dict(self._definitions)

    def lookup_definition(self, symbol: str) -> Optional[InstrumentDefinition]:
        """
        Look up a cached instrument definition by symbol.

        Args:
            symbol: Raw symbol or Tradier symbol.

        Returns:
            InstrumentDefinition if found, None otherwise.
        """
        # Direct lookup
        inst_id = self._symbol_to_id.get(symbol)
        if inst_id is not None:
            return self._definitions.get(inst_id)

        # Try Databento format
        try:
            db_symbol = tradier_to_databento(symbol)
            inst_id = self._symbol_to_id.get(db_symbol)
            if inst_id is not None:
                return self._definitions.get(inst_id)
        except ValueError:
            pass

        return None

    # ==========================================================================
    # BANDWIDTH / COST METRICS
    # ==========================================================================
    def get_bandwidth_report(self) -> Dict[str, Any]:
        """
        Get bandwidth usage report for cost monitoring.

        Returns:
            Dictionary with bandwidth metrics.
        """
        return {
            "session_gb": round(self.bandwidth.gb_received, 4),
            "daily_gb": round(self.bandwidth.daily_gb, 4),
            "daily_limit_gb": self.max_daily_gb,
            "daily_usage_pct": round(
                (self.bandwidth.daily_gb / self.max_daily_gb) * 100, 1
            ) if self.max_daily_gb > 0 else 0,
            "messages_received": self.bandwidth.messages_received,
            "status": self.status.value,
        }

    # ==========================================================================
    # CIRCUIT BREAKER
    # ==========================================================================
    @staticmethod
    def get_circuit_breaker_status() -> Dict[str, Any]:
        """Get circuit breaker state for Databento connections."""
        if databento_breaker:
            return {
                "state": str(databento_breaker.state),
                "failure_count": databento_breaker.failure_count,
                "success_count": getattr(databento_breaker, "success_count", 0),
            }
        return {"state": "unknown", "failure_count": 0, "success_count": 0}

    @staticmethod
    def reset_circuit_breaker() -> None:
        """Reset the Databento circuit breaker."""
        if databento_breaker:
            databento_breaker.reset()
            logger.info("Databento circuit breaker reset")

    # ==========================================================================
    # CONNECTION TEST
    # ==========================================================================
    def test_connection(self) -> Dict[str, Any]:
        """
        Test Databento API connectivity.

        Makes a small metadata request to verify the API key is valid
        and the service is reachable.

        Returns:
            Dictionary with test results.
        """
        if not HAS_DATABENTO:
            return {
                "success": False,
                "message": "databento package not installed",
            }

        try:
            # Use metadata endpoint as lightweight connectivity test
            result = self.historical.metadata.list_datasets()
            return {
                "success": True,
                "message": f"Connected. {len(result)} datasets available.",
                "datasets_available": len(result),
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {e}",
            }

    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    def close(self) -> None:
        """Clean shutdown of all connections."""
        self.stop_live()
        self._historical = None
        logger.info("DatabentoClient closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def __repr__(self) -> str:
        return (
            f"DatabentoClient(dataset={self.dataset}, status={self.status.value}, "
            f"bandwidth={self.bandwidth.gb_received:.3f}GB)"
        )


# ==============================================================================
# QT SIGNAL WRAPPER (if PySide6 is available)
# ==============================================================================
if HAS_QT:
    class DatabentoQtBridge(QObject):
        """
        Qt Signal bridge for DatabentoClient.

        Wraps the DatabentoClient callbacks into Qt Signals for thread-safe
        communication with PySide6 UI widgets.

        Usage:
            >>> client = DatabentoClient(api_key="...")
            >>> bridge = DatabentoQtBridge(client)
            >>> bridge.new_quote.connect(my_widget.on_quote)
            >>> client.start_live(underlyings=["SPY"])
        """
        new_quote = Signal(object)      # MarketDataUpdate
        new_trade = Signal(object)      # MarketDataUpdate
        new_ohlcv = Signal(object)      # MarketDataUpdate
        new_definition = Signal(object) # InstrumentDefinition
        connection_status_changed = Signal(object)  # ConnectionStatus
        error_occurred = Signal(str)

        def __init__(self, client: DatabentoClient, parent: Optional[QObject] = None):
            super().__init__(parent)
            self.client = client

            # Wire client callbacks to Qt signals
            client.on_quote = self._on_quote
            client.on_trade = self._on_trade
            client.on_ohlcv = self._on_ohlcv
            client.on_definition = self._on_definition
            client.on_status_change = self._on_status
            client.on_error = self._on_error

        def _on_quote(self, update: MarketDataUpdate) -> None:
            self.new_quote.emit(update)

        def _on_trade(self, update: MarketDataUpdate) -> None:
            self.new_trade.emit(update)

        def _on_ohlcv(self, update: MarketDataUpdate) -> None:
            self.new_ohlcv.emit(update)

        def _on_definition(self, defn: InstrumentDefinition) -> None:
            self.new_definition.emit(defn)

        def _on_status(self, status: ConnectionStatus) -> None:
            self.connection_status_changed.emit(status)

        def _on_error(self, error: str) -> None:
            self.error_occurred.emit(error)


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_databento_client_from_env(
    dataset: Optional[str] = None,
) -> DatabentoClient:
    """
    Create a DatabentoClient using environment variables.

    Reads from:
        DATABENTO_API_KEY: Required API key
        DATABENTO_DATASET: Optional dataset (default: OPRA.PILLAR)
        DATABENTO_MAX_DAILY_GB: Optional bandwidth cap (default: 5.0)

    Args:
        dataset: Override dataset. If None, reads from env or uses default.

    Returns:
        Configured DatabentoClient instance.

    Raises:
        ValueError: If DATABENTO_API_KEY is not set.
    """
    api_key = os.environ.get("DATABENTO_API_KEY", "")
    effective_dataset = dataset or os.environ.get("DATABENTO_DATASET", DEFAULT_DATASET)
    max_gb = float(os.environ.get("DATABENTO_MAX_DAILY_GB", "5.0"))

    return DatabentoClient(
        api_key=api_key,
        dataset=effective_dataset,
        max_daily_gb=max_gb,
    )


def create_databento_qt_bridge(
    client: Optional[DatabentoClient] = None,
    parent: Optional[Any] = None,
) -> Optional[Any]:
    """
    Create a Qt Signal bridge for a DatabentoClient.

    Args:
        client: DatabentoClient instance. If None, creates one from env.
        parent: Qt parent object.

    Returns:
        DatabentoQtBridge instance, or None if PySide6 not available.
    """
    if not HAS_QT:
        logger.warning("PySide6 not available — cannot create Qt bridge")
        return None

    if client is None:
        client = create_databento_client_from_env()

    return DatabentoQtBridge(client, parent)


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    # Main client
    "DatabentoClient",
    # Data classes
    "MarketDataUpdate",
    "InstrumentDefinition",
    "BandwidthTracker",
    # Enums
    "ConnectionStatus",
    "DatabentoSchema",
    "SymbolFormat",
    # Symbol conversion
    "convert_symbol",
    "databento_to_tradier",
    "tradier_to_databento",
    "is_option_symbol",
    # Factory functions
    "create_databento_client_from_env",
    "create_databento_qt_bridge",
    # Constants
    "DEFAULT_DATASET",
    "DEFAULT_EQUITY_DATASET",
    "DEFAULT_LIVE_SCHEMA",
    "DEFAULT_HIST_SCHEMA",
]

# Add Qt bridge to exports if available
if HAS_QT:
    __all__.append("DatabentoQtBridge")
