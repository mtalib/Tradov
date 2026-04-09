#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC30_OrderFlowAnalyzer.py
Purpose: Real-time options order flow analysis, gamma exposure, and dark pool tracking

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-12-27

Module Description:
    This module provides institutional-grade order flow analysis capabilities:
    - Gamma Exposure (GEX) calculation and tracking
    - Unusual Options Activity (UOA) detection
    - Dark pool print analysis for support/resistance levels
    - Net flow analysis (call vs put flow)
    - Put/Call ratio tracking
    - Max Pain calculation

    These signals are leading indicators that can predict price movement
    before it occurs, giving the trading system an edge.

References:
    - SpotGamma methodology for GEX calculations
    - CBOE options data specifications
    - Dark pool reporting requirements (Rule 606)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
from typing import Optional, Any
from collections.abc import Callable
from enum import Enum
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# stumpy: Matrix Profile for pattern discovery in order flow time series
try:
    import stumpy
    _STUMPY_AVAILABLE = True
except ImportError:
    _STUMPY_AVAILABLE = False

# Databento (optional — real-time and historical tick data)
try:
    import databento as db
    HAS_DATABENTO = True
except ImportError:
    db = None  # type: ignore[assignment]
    HAS_DATABENTO = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        TradierClient,
        GreekData,
        create_tradier_client_from_env,
    )
    HAS_TRADIER = True
except ImportError:
    TradierClient = None  # type: ignore[assignment,misc]
    GreekData = None  # type: ignore[assignment,misc]
    create_tradier_client_from_env = None  # type: ignore[assignment]
    HAS_TRADIER = False
try:
    from Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol import (
        OptionsDataProvider,
        create_options_data_provider,
    )
except ImportError:
    OptionsDataProvider = None  # type: ignore[assignment,misc]
    create_options_data_provider = None  # type: ignore[assignment]

# ==============================================================================
# CONSTANTS
# ==============================================================================
UNUSUAL_VOLUME_MULTIPLIER = 3.0  # 3x average volume = unusual
LARGE_TRADE_THRESHOLD = 100  # contracts
DARK_POOL_MIN_SIZE = 10000  # shares for significance
GEX_CALCULATION_INTERVAL = 60  # seconds
MAX_FLOW_HISTORY = 1000  # max flow entries to keep

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)


from abc import ABC, abstractmethod

# ==============================================================================
# ENUMS
# ==============================================================================
class FlowDirection(Enum):
    """Options flow direction classification."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TradeType(Enum):
    """Trade type classification."""
    SWEEP = "sweep"  # Multi-exchange aggressive
    BLOCK = "block"  # Large single transaction
    SPLIT = "split"  # Broken into smaller pieces
    OPENING = "opening"
    CLOSING = "closing"
    UNKNOWN = "unknown"


class FlowSentiment(Enum):
    """Overall flow sentiment."""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionsFlow:
    """Single options flow entry."""
    symbol: str
    timestamp: datetime
    option_type: str  # 'call' or 'put'
    strike: float
    expiry: date
    premium: float  # Total premium in dollars
    size: int  # Number of contracts
    price: float  # Option price per contract
    underlying_price: float
    side: str  # 'bid', 'ask', 'mid'
    trade_type: TradeType = TradeType.UNKNOWN
    open_interest: int = 0
    volume: int = 0
    implied_volatility: float = 0.0
    delta: float = 0.0

    @property
    def is_unusual(self) -> bool:
        """Check if this is unusual activity."""
        if self.open_interest == 0:
            return self.size >= LARGE_TRADE_THRESHOLD
        return self.size > self.open_interest * 0.1  # >10% of OI

    @property
    def sentiment(self) -> FlowDirection:
        """Determine sentiment based on trade characteristics."""
        if self.option_type == 'call':
            if self.side == 'ask':  # Bought at ask = bullish
                return FlowDirection.BULLISH
            elif self.side == 'bid':  # Sold at bid = bearish
                return FlowDirection.BEARISH
        else:  # put
            if self.side == 'ask':  # Bought at ask = bearish
                return FlowDirection.BEARISH
            elif self.side == 'bid':  # Sold at bid = bullish
                return FlowDirection.BULLISH
        return FlowDirection.NEUTRAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "option_type": self.option_type,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "premium": self.premium,
            "size": self.size,
            "price": self.price,
            "underlying_price": self.underlying_price,
            "side": self.side,
            "trade_type": self.trade_type.value,
            "is_unusual": self.is_unusual,
            "sentiment": self.sentiment.value,
        }


@dataclass
class GammaExposure:
    """Gamma exposure calculation result."""
    symbol: str
    timestamp: datetime
    total_gex: float  # Net gamma exposure
    call_gex: float  # Call gamma exposure
    put_gex: float  # Put gamma exposure
    gex_by_strike: dict[float, float] = field(default_factory=dict)
    flip_level: float | None = None  # Price where GEX flips sign
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)

    @property
    def is_positive(self) -> bool:
        """Positive GEX = dealers short gamma = mean reversion."""
        return self.total_gex > 0

    @property
    def regime(self) -> str:
        """Get market regime based on GEX."""
        if self.total_gex > 1_000_000_000:  # $1B+
            return "high_positive"  # Strong mean reversion expected
        elif self.total_gex > 0:
            return "positive"  # Mild mean reversion
        elif self.total_gex > -1_000_000_000:
            return "negative"  # Mild trending
        else:
            return "high_negative"  # Strong trending expected

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "total_gex": self.total_gex,
            "call_gex": self.call_gex,
            "put_gex": self.put_gex,
            "flip_level": self.flip_level,
            "regime": self.regime,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
        }


@dataclass
class DarkPoolPrint:
    """Dark pool trade print."""
    symbol: str
    timestamp: datetime
    price: float
    size: int  # shares
    value: float  # dollar value
    exchange: str

    @property
    def is_significant(self) -> bool:
        """Check if this is a significant print."""
        return self.size >= DARK_POOL_MIN_SIZE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "size": self.size,
            "value": self.value,
            "exchange": self.exchange,
            "is_significant": self.is_significant,
        }


# ==============================================================================
# TICK DATA SOURCE PROVIDERS
# ==============================================================================
class BaseTickDataSource(ABC):
    """
    Abstract base class for real-time / historical tick data providers.

    Concrete implementations supply :class:`OptionsFlow` and
    :class:`DarkPoolPrint` objects to :class:`OrderFlowAnalyzer` without
    coupling the analyzer to a specific data vendor.

    All ``fetch_*`` methods **must never raise** — return an empty list on
    any error so the caller can degrade gracefully.

    Example (custom source)::

        class MyTickSource(BaseTickDataSource):
            @property
            def source_name(self) -> str:
                return "my_vendor"

            def fetch_options_trades(
                self, symbol: str, lookback_minutes: int
            ) -> List['OptionsFlow']:
                ...

            def fetch_dark_pool_prints(
                self, symbol: str, lookback_days: int
            ) -> List['DarkPoolPrint']:
                ...
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable vendor/source identifier."""

    @abstractmethod
    def fetch_options_trades(
        self, symbol: str, lookback_minutes: int
    ) -> list['OptionsFlow']:
        """
        Fetch recent options trade prints.

        Args:
            symbol:           Underlying ticker symbol (e.g. ``"SPY"``)
            lookback_minutes: How far back to query (in minutes).

        Returns:
            List of :class:`OptionsFlow` records, newest-first.
            Returns an empty list on any error — must not raise.
        """

    @abstractmethod
    def fetch_dark_pool_prints(
        self, symbol: str, lookback_days: int
    ) -> list['DarkPoolPrint']:
        """
        Fetch recent dark pool / block trade prints.

        Args:
            symbol:        Underlying ticker symbol.
            lookback_days: How many days back to search.

        Returns:
            List of :class:`DarkPoolPrint` records, largest-first.
            Returns an empty list on any error — must not raise.
        """


class DatabentoTickDataSource(BaseTickDataSource):
    """
    Tick data source backed by the Databento Historical API.

    Options Trades
    --------------
    Dataset  : ``OPRA.PILLAR``
    Schema   : ``trades``
    Encodes each OPRA print as an :class:`OptionsFlow` with:

    * ``premium``  = ``price * size * 100``  (100 shares/contract)
    * ``price``    = Databento fixed-point integer / 1 000 000 000
    * ``side``     = ``"ask"`` (aggressor = ``"A"``), ``"bid"``
                     (aggressor = ``"B"``), otherwise ``"mid"``
    * Strike, expiry and ``option_type`` are decoded from the
      OSI symbology embedded in the Databento *symbol* string
      (format: ``<ROOT><YYMMDD><C/P><STRIKE_x1000>``).

    Dark Pool / Block Trades
    ------------------------
    Dataset  : ``DBEQ.BASIC``
    Schema   : ``trades``
    Filters trades with ``size >= DARK_POOL_MIN_SIZE`` and maps
    them to :class:`DarkPoolPrint` objects.

    .. note::
        **This is a stub implementation.**  The Databento calls are
        structurally correct but have not been exercised against a live
        subscription.  Field names and fixed-point scaling were taken
        from the Databento Python client docs (v0.37+).  Verify against
        your actual subscription datasets before enabling in production.

    Requires::

        pip install databento

    Env var: ``DATABENTO_API_KEY``
    """

    # Databento fixed-point price divisor
    _PRICE_DIVISOR: float = 1_000_000_000.0

    # Aggressor-side codes → bid/ask labels
    _SIDE_MAP: dict[str, str] = {"A": "ask", "B": "bid"}

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: Databento API key (``DATABENTO_API_KEY``).

        Raises:
            ImportError: If the ``databento`` package is not installed.
        """
        if not HAS_DATABENTO:
            raise ImportError(
                "databento package is required: pip install databento"
            )
        self._api_key = api_key
        self._client = db.Historical(api_key=api_key)

    @property
    def source_name(self) -> str:
        return "databento"

    # ------------------------------------------------------------------
    # Options trades  (OPRA.PILLAR / trades)
    # ------------------------------------------------------------------

    def fetch_options_trades(
        self, symbol: str, lookback_minutes: int
    ) -> list['OptionsFlow']:
        """
        Fetch OPRA options trades from Databento.

        Maps ``OPRA.PILLAR`` trade records to :class:`OptionsFlow`.
        Strike / expiry / option_type are parsed from OSI-format symbols.
        """
        try:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(minutes=lookback_minutes)

            data = self._client.timeseries.get_range(
                dataset="OPRA.PILLAR",
                schema="trades",
                symbols=[symbol],
                stype_in="parent",   # map root symbol → all options
                start=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                end=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            )

            flows: list[OptionsFlow] = []
            for record in data:
                try:
                    flow = self._record_to_options_flow(record, symbol)
                    if flow is not None:
                        flows.append(flow)
                except Exception as parse_err:
                    logger.debug("Databento options trade parse error: %s", parse_err)

            logger.info(
                f"Databento: {len(flows)} options trades for {symbol} "
                f"(last {lookback_minutes} min)"
            )
            return flows

        except Exception as exc:
            logger.error("DatabentoTickDataSource.fetch_options_trades(%s): %s", symbol, exc, exc_info=True)
            return []

    def _record_to_options_flow(
        self, record: Any, underlying: str
    ) -> Optional['OptionsFlow']:
        """
        Convert a single Databento ``TradeMsg`` to :class:`OptionsFlow`.

        OSI symbol format: ``<ROOT><YYMMDD><C|P><STRIKE_x1000>``
        e.g. ``SPY   240119C00480000`` = SPY Jan-19-2024 Call @ $480.00
        """
        raw_symbol: str = getattr(record, "symbol", "") or ""
        raw_symbol = raw_symbol.strip()

        # --- Parse OSI fields from symbol string ---
        option_type = "call"
        strike: float = 0.0
        expiry = date.today()
        try:
            # Root is up to 6 chars, padded with spaces
            # YYMMDD = chars 6-11, C/P = char 12, Strike = chars 13-20 (/1000)
            if len(raw_symbol) >= 13:
                date_str = raw_symbol[6:12]          # e.g. "240119"
                cp_char = raw_symbol[12].upper()     # 'C' or 'P'
                strike_raw = raw_symbol[13:21]       # e.g. "00480000"
                option_type = "call" if cp_char == "C" else "put"
                strike = int(strike_raw) / 1000.0
                expiry = datetime.strptime(date_str, "%y%m%d").date()
        except Exception as e:
            self.logger.debug("OPRA symbol parse failed for '%s': %s", raw_symbol, e)

        # --- Map numeric fields ---
        price: float = getattr(record, "price", 0) / self._PRICE_DIVISOR
        size: int = int(getattr(record, "size", 0))
        if size == 0:
            return None  # Skip zero-size records

        side_code = str(getattr(record, "side", "")).upper()
        side: str = self._SIDE_MAP.get(side_code, "mid")

        ts_ns: int = int(getattr(record, "ts_event", 0))
        timestamp = datetime.utcfromtimestamp(ts_ns / 1e9) if ts_ns else datetime.utcnow()

        premium = price * size * 100  # 100 shares per contract

        return OptionsFlow(
            symbol=underlying,
            timestamp=timestamp,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            premium=premium,
            size=size,
            price=price,
            underlying_price=0.0,  # Not available from trade schema alone
            side=side,
            trade_type=TradeType.UNKNOWN,
        )

    # ------------------------------------------------------------------
    # Dark pool / block trades  (DBEQ.BASIC / trades)
    # ------------------------------------------------------------------

    def fetch_dark_pool_prints(
        self, symbol: str, lookback_days: int
    ) -> list['DarkPoolPrint']:
        """
        Fetch large equity block trades from Databento as dark-pool proxies.

        Queries ``DBEQ.BASIC`` trades schema and filters records with
        ``size >= DARK_POOL_MIN_SIZE``.  Publisher IDs are mapped to
        exchange names using the Databento publishers list.
        """
        try:
            end_dt = datetime.utcnow()
            start_dt = end_dt - timedelta(days=lookback_days)

            data = self._client.timeseries.get_range(
                dataset="DBEQ.BASIC",
                schema="trades",
                symbols=[symbol],
                start=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                end=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            )

            prints: list[DarkPoolPrint] = []
            for record in data:
                try:
                    dp = self._record_to_dark_pool_print(record, symbol)
                    if dp is not None and dp.size >= DARK_POOL_MIN_SIZE:
                        prints.append(dp)
                except Exception as parse_err:
                    logger.debug("Databento dark pool parse error: %s", parse_err)

            logger.info(
                f"Databento: {len(prints)} block prints for {symbol} "
                f"(last {lookback_days} day(s))"
            )
            return prints

        except Exception as exc:
            logger.error("DatabentoTickDataSource.fetch_dark_pool_prints(%s): %s", symbol, exc, exc_info=True)
            return []

    def _record_to_dark_pool_print(
        self, record: Any, symbol: str
    ) -> Optional['DarkPoolPrint']:
        """Convert a single Databento trade record to :class:`DarkPoolPrint`."""
        price: float = getattr(record, "price", 0) / self._PRICE_DIVISOR
        size: int = int(getattr(record, "size", 0))
        if price == 0.0 or size == 0:
            return None

        ts_ns: int = int(getattr(record, "ts_event", 0))
        timestamp = datetime.utcfromtimestamp(ts_ns / 1e9) if ts_ns else datetime.utcnow()

        # publisher_id → exchange name (approximate; full map in Databento docs)
        publisher_id: int = int(getattr(record, "publisher_id", 0))
        exchange = f"venue_{publisher_id}" if publisher_id else "unknown"

        return DarkPoolPrint(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            size=size,
            value=price * size,
            exchange=exchange,
        )


# ==============================================================================
# FLOW SUMMARY
# ==============================================================================
@dataclass
class FlowSummary:
    """Summary of options flow for a symbol."""
    symbol: str
    timestamp: datetime
    total_call_premium: float
    total_put_premium: float
    total_call_volume: int
    total_put_volume: int
    net_premium: float  # Call - Put premium
    put_call_ratio: float
    unusual_count: int
    bullish_flow_count: int
    bearish_flow_count: int
    largest_trade: OptionsFlow | None = None

    @property
    def sentiment(self) -> FlowSentiment:
        """Calculate overall sentiment."""
        # Calculate premium ratio
        if self.total_put_premium == 0:
            premium_ratio = float('inf') if self.total_call_premium > 0 else 1.0
        else:
            premium_ratio = self.total_call_premium / self.total_put_premium

        # Calculate flow direction ratio
        total_flow = self.bullish_flow_count + self.bearish_flow_count
        if total_flow == 0:
            flow_ratio = 0.5
        else:
            flow_ratio = self.bullish_flow_count / total_flow

        # Combined score (0-1, higher = more bullish)
        score = (premium_ratio / (1 + premium_ratio) + flow_ratio) / 2

        if score > 0.7:
            return FlowSentiment.VERY_BULLISH
        elif score > 0.55:
            return FlowSentiment.BULLISH
        elif score > 0.45:
            return FlowSentiment.NEUTRAL
        elif score > 0.3:
            return FlowSentiment.BEARISH
        else:
            return FlowSentiment.VERY_BEARISH

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "total_call_premium": self.total_call_premium,
            "total_put_premium": self.total_put_premium,
            "total_call_volume": self.total_call_volume,
            "total_put_volume": self.total_put_volume,
            "net_premium": self.net_premium,
            "put_call_ratio": self.put_call_ratio,
            "unusual_count": self.unusual_count,
            "sentiment": self.sentiment.value,
        }


@dataclass
class MaxPainAnalysis:
    """Max pain calculation result."""
    symbol: str
    expiry: date
    timestamp: datetime
    max_pain_strike: float
    current_price: float
    distance_to_max_pain: float  # percentage
    call_pain_by_strike: dict[float, float] = field(default_factory=dict)
    put_pain_by_strike: dict[float, float] = field(default_factory=dict)
    total_open_interest: int = 0

    @property
    def gravity_strength(self) -> str:
        """Estimate strength of price gravity toward max pain."""
        abs_distance = abs(self.distance_to_max_pain)
        if abs_distance < 0.5:
            return "weak"  # Already close
        elif abs_distance < 1.5:
            return "moderate"
        else:
            return "strong"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "expiry": self.expiry.isoformat(),
            "timestamp": self.timestamp.isoformat(),
            "max_pain_strike": self.max_pain_strike,
            "current_price": self.current_price,
            "distance_percent": self.distance_to_max_pain,
            "gravity_strength": self.gravity_strength,
            "total_open_interest": self.total_open_interest,
        }


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OrderFlowAnalyzer:
    """
    Real-time options order flow analyzer.

    Provides institutional-grade order flow analysis including:
    - Gamma Exposure (GEX) tracking
    - Unusual Options Activity detection
    - Dark Pool analysis
    - Net flow and Put/Call ratio
    - Max Pain calculation

    Example:
        >>> analyzer = OrderFlowAnalyzer()
        >>> gex = analyzer.get_gamma_exposure("SPY")
        >>> print(f"GEX: ${gex.total_gex:,.0f}, Regime: {gex.regime}")
        >>>
        >>> unusual = analyzer.detect_unusual_activity("SPY")
        >>> for flow in unusual:
        ...     print(f"{flow.option_type} {flow.strike} - ${flow.premium:,.0f}")
    """

    def __init__(
        self,
        data_provider: Optional['OptionsDataProvider'] = None,
        symbols: list[str] | None = None,
        enable_realtime: bool = False,
        tick_data_source: BaseTickDataSource | None = None,
    ):
        """
        Initialize Order Flow Analyzer.

        Args:
            data_provider: OptionsDataProvider instance (e.g. TradierClient or
                DatabentoMarketDataAdapter). If None, auto-created via
                create_options_data_provider() using MARKET_DATA_PROVIDER env var.
            symbols: Symbols to track (default: ["SPY"])
            enable_realtime: Enable real-time flow tracking
            tick_data_source: :class:`BaseTickDataSource` used to fetch live
                options trades and dark pool prints.  When *None* the built-in
                stub behaviour (warning + empty list) is preserved.  Pass a
                :class:`DatabentoTickDataSource` to enable real Databento data.
        """
        self.symbols = symbols or ["SPY"]
        if data_provider is not None:
            self._data_provider: Any = data_provider
        elif create_options_data_provider is not None:
            try:
                self._data_provider = create_options_data_provider()
            except Exception as e:
                logger.warning("OptionsDataProvider unavailable: %s", e, exc_info=True)
                self._data_provider = None
        else:
            self._data_provider = None
        self.enable_realtime = enable_realtime
        self._tick_data_source: BaseTickDataSource | None = tick_data_source

        # Flow storage
        self._flow_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_FLOW_HISTORY)
        )
        self._dark_pool_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_FLOW_HISTORY)
        )

        # Cached calculations
        self._gex_cache: dict[str, GammaExposure] = {}
        self._gex_cache_time: dict[str, datetime] = {}
        self._max_pain_cache: dict[tuple[str, date], MaxPainAnalysis] = {}

        # Callbacks
        self._flow_callbacks: list[Callable[[OptionsFlow], None]] = []
        self._unusual_callbacks: list[Callable[[OptionsFlow], None]] = []

        # Threading
        self._running = False
        self._thread: threading.Thread | None = None

        logger.info("OrderFlowAnalyzer initialized for symbols: %s", self.symbols)

    # ==========================================================================
    # GAMMA EXPOSURE (GEX) METHODS
    # ==========================================================================

    def get_gamma_exposure(
        self,
        symbol: str,
        use_cache: bool = True,
        cache_ttl: int = GEX_CALCULATION_INTERVAL
    ) -> GammaExposure:
        """
        Calculate Gamma Exposure (GEX) for a symbol.

        GEX measures how much dealers need to hedge for each $1 move in the
        underlying. Positive GEX = dealers short gamma = mean reversion.
        Negative GEX = dealers long gamma = trending/volatile.

        Args:
            symbol: Stock symbol (e.g., "SPY")
            use_cache: Use cached value if available
            cache_ttl: Cache time-to-live in seconds

        Returns:
            GammaExposure object with calculations

        Example:
            >>> gex = analyzer.get_gamma_exposure("SPY")
            >>> if gex.is_positive:
            ...     print("Mean reversion expected - fade moves")
            >>> else:
            ...     print("Trending expected - follow momentum")
        """
        # Check cache
        if use_cache and symbol in self._gex_cache:
            cache_time = self._gex_cache_time.get(symbol, datetime.min)
            if (datetime.now() - cache_time).seconds < cache_ttl:
                return self._gex_cache[symbol]

        try:
            # Fetch option chain
            chain = self._fetch_option_chain(symbol)
            if not chain:
                logger.warning("Could not fetch option chain for %s", symbol)
                return GammaExposure(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    total_gex=0,
                    call_gex=0,
                    put_gex=0
                )

            # Get current underlying price
            underlying_price = self._get_underlying_price(symbol)

            # Calculate GEX
            gex_result = self._calculate_gex(symbol, chain, underlying_price)

            # Cache result
            self._gex_cache[symbol] = gex_result
            self._gex_cache_time[symbol] = datetime.now()

            logger.info(
                f"GEX calculated for {symbol}: "
                f"${gex_result.total_gex:,.0f} ({gex_result.regime})"
            )

            return gex_result

        except Exception as e:
            logger.error("GEX calculation failed for %s: %s", symbol, e, exc_info=True)
            return GammaExposure(
                symbol=symbol,
                timestamp=datetime.now(),
                total_gex=0,
                call_gex=0,
                put_gex=0
            )

    def _calculate_gex(
        self,
        symbol: str,
        chain: pd.DataFrame,
        underlying_price: float
    ) -> GammaExposure:
        """
        Internal GEX calculation.

        GEX = Gamma × Open Interest × Contract Multiplier × Spot Price²

        For dealers:
        - Calls: Dealers are typically short, so positive gamma exposure
        - Puts: Dealers are typically long, so negative gamma exposure
        """
        call_gex = 0.0
        put_gex = 0.0
        gex_by_strike: dict[float, float] = {}

        contract_multiplier = 100  # Standard options

        for _, row in chain.iterrows():
            strike = row.get('strike', 0)
            gamma = row.get('gamma', 0)
            oi = row.get('open_interest', 0)
            option_type = row.get('contract_type', '').lower()

            if gamma == 0 or oi == 0:
                continue

            # GEX formula
            gex = gamma * oi * contract_multiplier * (underlying_price ** 2) / 100

            if option_type == 'call':
                # Dealers short calls = positive GEX
                call_gex += gex
                gex_by_strike[strike] = gex_by_strike.get(strike, 0) + gex
            elif option_type == 'put':
                # Dealers long puts = negative GEX (we flip sign)
                put_gex -= gex
                gex_by_strike[strike] = gex_by_strike.get(strike, 0) - gex

        total_gex = call_gex + put_gex

        # Find GEX flip level (where gamma changes sign)
        flip_level = self._find_gex_flip_level(gex_by_strike, underlying_price)

        # Find support/resistance levels (high absolute GEX strikes)
        support_levels, resistance_levels = self._find_gex_levels(
            gex_by_strike, underlying_price
        )

        return GammaExposure(
            symbol=symbol,
            timestamp=datetime.now(),
            total_gex=total_gex,
            call_gex=call_gex,
            put_gex=put_gex,
            gex_by_strike=gex_by_strike,
            flip_level=flip_level,
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )

    def _find_gex_flip_level(
        self,
        gex_by_strike: dict[float, float],
        current_price: float
    ) -> float | None:
        """Find the price level where GEX flips from positive to negative."""
        if not gex_by_strike:
            return None

        strikes = sorted(gex_by_strike.keys())
        for i in range(len(strikes) - 1):
            strike1, strike2 = strikes[i], strikes[i + 1]
            gex1, gex2 = gex_by_strike[strike1], gex_by_strike[strike2]

            # Check for sign change
            if gex1 * gex2 < 0:
                # Linear interpolation to find flip level
                flip = strike1 + (strike2 - strike1) * abs(gex1) / (abs(gex1) + abs(gex2))
                return flip

        return None

    def _find_gex_levels(
        self,
        gex_by_strike: dict[float, float],
        current_price: float,
        num_levels: int = 3
    ) -> tuple[list[float], list[float]]:
        """Find support and resistance levels based on GEX concentration."""
        if not gex_by_strike:
            return [], []

        # Sort by absolute GEX value
        sorted_strikes = sorted(
            gex_by_strike.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:num_levels * 2]

        support = []
        resistance = []

        for strike, _gex in sorted_strikes:
            if strike < current_price:
                support.append(strike)
            else:
                resistance.append(strike)

        return sorted(support)[:num_levels], sorted(resistance)[:num_levels]

    # ==========================================================================
    # UNUSUAL OPTIONS ACTIVITY
    # ==========================================================================

    def detect_unusual_activity(
        self,
        symbol: str,
        min_premium: float = 50000,
        min_size: int = 100,
        lookback_minutes: int = 60
    ) -> list[OptionsFlow]:
        """
        Detect unusual options activity for a symbol.

        Unusual activity is identified by:
        - Volume significantly higher than open interest
        - Large premium trades
        - Aggressive execution (buying at ask, selling at bid)
        - Sweep orders across multiple exchanges

        Args:
            symbol: Stock symbol
            min_premium: Minimum premium in dollars
            min_size: Minimum contract size
            lookback_minutes: Time window to analyze

        Returns:
            List of unusual OptionsFlow entries

        Example:
            >>> unusual = analyzer.detect_unusual_activity("SPY", min_premium=100000)
            >>> for flow in unusual:
            ...     print(f"{flow.option_type} {flow.strike} exp {flow.expiry}")
            ...     print(f"  Premium: ${flow.premium:,.0f}, Sentiment: {flow.sentiment.value}")
        """
        try:
            # Fetch recent options trades
            trades = self._fetch_options_trades(symbol, lookback_minutes)

            unusual = []
            for trade in trades:
                # Check if unusual
                if not trade.is_unusual:
                    continue
                if trade.premium < min_premium:
                    continue
                if trade.size < min_size:
                    continue

                unusual.append(trade)

                # Trigger callbacks
                for callback in self._unusual_callbacks:
                    try:
                        callback(trade)
                    except Exception as e:
                        logger.error("Unusual callback error: %s", e, exc_info=True)

            # Sort by premium (largest first)
            unusual.sort(key=lambda x: x.premium, reverse=True)

            logger.info("Found %s unusual options trades for %s", len(unusual), symbol)
            return unusual

        except Exception as e:
            logger.error("Unusual activity detection failed for %s: %s", symbol, e, exc_info=True)
            return []

    def get_flow_summary(
        self,
        symbol: str,
        lookback_minutes: int = 60
    ) -> FlowSummary:
        """
        Get a summary of options flow for a symbol.

        Args:
            symbol: Stock symbol
            lookback_minutes: Time window to analyze

        Returns:
            FlowSummary with aggregated statistics

        Example:
            >>> summary = analyzer.get_flow_summary("SPY")
            >>> print(f"Net Premium: ${summary.net_premium:,.0f}")
            >>> print(f"P/C Ratio: {summary.put_call_ratio:.2f}")
            >>> print(f"Sentiment: {summary.sentiment.value}")
        """
        try:
            trades = self._fetch_options_trades(symbol, lookback_minutes)

            if not trades:
                return FlowSummary(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    total_call_premium=0,
                    total_put_premium=0,
                    total_call_volume=0,
                    total_put_volume=0,
                    net_premium=0,
                    put_call_ratio=1.0,
                    unusual_count=0,
                    bullish_flow_count=0,
                    bearish_flow_count=0
                )

            call_premium = sum(t.premium for t in trades if t.option_type == 'call')
            put_premium = sum(t.premium for t in trades if t.option_type == 'put')
            call_volume = sum(t.size for t in trades if t.option_type == 'call')
            put_volume = sum(t.size for t in trades if t.option_type == 'put')
            unusual = sum(1 for t in trades if t.is_unusual)
            bullish = sum(1 for t in trades if t.sentiment == FlowDirection.BULLISH)
            bearish = sum(1 for t in trades if t.sentiment == FlowDirection.BEARISH)

            # Calculate P/C ratio
            pcr = put_volume / call_volume if call_volume > 0 else 1.0

            # Find largest trade
            largest = max(trades, key=lambda x: x.premium) if trades else None

            return FlowSummary(
                symbol=symbol,
                timestamp=datetime.now(),
                total_call_premium=call_premium,
                total_put_premium=put_premium,
                total_call_volume=call_volume,
                total_put_volume=put_volume,
                net_premium=call_premium - put_premium,
                put_call_ratio=pcr,
                unusual_count=unusual,
                bullish_flow_count=bullish,
                bearish_flow_count=bearish,
                largest_trade=largest
            )

        except Exception as e:
            logger.error("Flow summary failed for %s: %s", symbol, e, exc_info=True)
            return FlowSummary(
                symbol=symbol,
                timestamp=datetime.now(),
                total_call_premium=0,
                total_put_premium=0,
                total_call_volume=0,
                total_put_volume=0,
                net_premium=0,
                put_call_ratio=1.0,
                unusual_count=0,
                bullish_flow_count=0,
                bearish_flow_count=0
            )

    # ==========================================================================
    # DARK POOL ANALYSIS
    # ==========================================================================

    def get_dark_pool_levels(
        self,
        symbol: str,
        lookback_days: int = 5,
        min_value: float = 1_000_000
    ) -> list[DarkPoolPrint]:
        """
        Get significant dark pool prints that serve as support/resistance.

        Dark pool prints represent large institutional trades that can
        indicate significant price levels.

        Args:
            symbol: Stock symbol
            lookback_days: Days to look back
            min_value: Minimum dollar value for significance

        Returns:
            List of significant DarkPoolPrint entries

        Example:
            >>> levels = analyzer.get_dark_pool_levels("SPY")
            >>> for level in levels:
            ...     print(f"${level.price:.2f} - {level.size:,} shares (${level.value:,.0f})")
        """
        try:
            # Fetch trades from dark pool exchanges
            prints = self._fetch_dark_pool_prints(symbol, lookback_days)

            # Filter by significance
            significant = [p for p in prints if p.value >= min_value]

            # Sort by value
            significant.sort(key=lambda x: x.value, reverse=True)

            logger.info("Found %s significant dark pool prints for %s", len(significant), symbol)
            return significant

        except Exception as e:
            logger.error("Dark pool analysis failed for %s: %s", symbol, e, exc_info=True)
            return []

    def get_dark_pool_support_resistance(
        self,
        symbol: str,
        current_price: float,
        lookback_days: int = 5
    ) -> tuple[list[float], list[float]]:
        """
        Get support and resistance levels from dark pool prints.

        Args:
            symbol: Stock symbol
            current_price: Current underlying price
            lookback_days: Days to analyze

        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        prints = self.get_dark_pool_levels(symbol, lookback_days)

        if not prints:
            return [], []

        # Group prints by price level (within $0.50)
        price_clusters: dict[float, float] = defaultdict(float)
        for p in prints:
            rounded_price = round(p.price * 2) / 2  # Round to nearest $0.50
            price_clusters[rounded_price] += p.value

        # Sort by total value
        sorted_levels = sorted(
            price_clusters.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        support = [price for price, _ in sorted_levels if price < current_price]
        resistance = [price for price, _ in sorted_levels if price >= current_price]

        return sorted(support, reverse=True)[:5], sorted(resistance)[:5]

    # ==========================================================================
    # MAX PAIN CALCULATION
    # ==========================================================================

    def calculate_max_pain(
        self,
        symbol: str,
        expiry: date | None = None
    ) -> MaxPainAnalysis:
        """
        Calculate max pain strike for an expiration.

        Max pain is the strike price where option holders collectively
        experience maximum losses (and market makers have minimum payout).

        Args:
            symbol: Stock symbol
            expiry: Expiration date (default: nearest expiry)

        Returns:
            MaxPainAnalysis with calculation results

        Example:
            >>> max_pain = analyzer.calculate_max_pain("SPY")
            >>> print(f"Max Pain: ${max_pain.max_pain_strike}")
            >>> print(f"Current distance: {max_pain.distance_to_max_pain:.2f}%")
        """
        try:
            # Get expiry if not specified
            if expiry is None:
                expiry = self._get_nearest_expiry(symbol)

            # Check cache
            cache_key = (symbol, expiry)
            if cache_key in self._max_pain_cache:
                cached = self._max_pain_cache[cache_key]
                if (datetime.now() - cached.timestamp).seconds < 300:  # 5 min cache
                    return cached

            # Fetch option chain for expiry
            chain = self._fetch_option_chain(symbol, expiry)
            if chain.empty:
                logger.warning("No option chain for %s %s", symbol, expiry)
                return MaxPainAnalysis(
                    symbol=symbol,
                    expiry=expiry,
                    timestamp=datetime.now(),
                    max_pain_strike=0,
                    current_price=0,
                    distance_to_max_pain=0
                )

            current_price = self._get_underlying_price(symbol)

            # Calculate pain at each strike
            strikes = chain['strike'].unique()
            call_oi = chain[chain['contract_type'].str.lower() == 'call'].set_index('strike')['open_interest']
            put_oi = chain[chain['contract_type'].str.lower() == 'put'].set_index('strike')['open_interest']

            call_pain: dict[float, float] = {}
            put_pain: dict[float, float] = {}
            total_pain: dict[float, float] = {}

            for test_price in strikes:
                # Call pain: For each strike below test price, calls are ITM
                cp = 0
                for strike in strikes:
                    if strike < test_price:
                        oi = call_oi.get(strike, 0)
                        cp += (test_price - strike) * oi * 100
                call_pain[test_price] = cp

                # Put pain: For each strike above test price, puts are ITM
                pp = 0
                for strike in strikes:
                    if strike > test_price:
                        oi = put_oi.get(strike, 0)
                        pp += (strike - test_price) * oi * 100
                put_pain[test_price] = pp

                total_pain[test_price] = cp + pp

            # Find minimum pain (max pain strike)
            max_pain_strike = min(total_pain.keys(), key=lambda x: total_pain[x])

            # Calculate total OI
            total_oi = int(call_oi.sum() + put_oi.sum())

            # Distance from current price
            distance = ((max_pain_strike - current_price) / current_price) * 100

            result = MaxPainAnalysis(
                symbol=symbol,
                expiry=expiry,
                timestamp=datetime.now(),
                max_pain_strike=max_pain_strike,
                current_price=current_price,
                distance_to_max_pain=distance,
                call_pain_by_strike=call_pain,
                put_pain_by_strike=put_pain,
                total_open_interest=total_oi
            )

            # Cache result
            self._max_pain_cache[cache_key] = result

            logger.info(
                f"Max pain for {symbol} {expiry}: ${max_pain_strike} "
                f"(current: ${current_price:.2f}, distance: {distance:.2f}%)"
            )

            return result

        except Exception as e:
            logger.error("Max pain calculation failed for %s: %s", symbol, e, exc_info=True)
            return MaxPainAnalysis(
                symbol=symbol,
                expiry=expiry or date.today(),
                timestamp=datetime.now(),
                max_pain_strike=0,
                current_price=0,
                distance_to_max_pain=0
            )

    # ==========================================================================
    # PUT/CALL RATIO
    # ==========================================================================

    def get_put_call_ratio(
        self,
        symbol: str,
        lookback_minutes: int = 60,
        use_volume: bool = True
    ) -> dict[str, float]:
        """
        Calculate put/call ratio.

        Args:
            symbol: Stock symbol
            lookback_minutes: Time window
            use_volume: Use volume (True) or open interest (False)

        Returns:
            Dictionary with ratio metrics

        Example:
            >>> pcr = analyzer.get_put_call_ratio("SPY")
            >>> if pcr["ratio"] > 1.3:
            ...     print("Extreme bearish positioning - contrarian bullish")
            >>> elif pcr["ratio"] < 0.5:
            ...     print("Extreme bullish positioning - contrarian bearish")
        """
        summary = self.get_flow_summary(symbol, lookback_minutes)

        volume_ratio = summary.put_call_ratio
        premium_ratio = (
            summary.total_put_premium / summary.total_call_premium
            if summary.total_call_premium > 0 else 1.0
        )

        return {
            "volume_ratio": volume_ratio,
            "premium_ratio": premium_ratio,
            "ratio": volume_ratio if use_volume else premium_ratio,
            "interpretation": self._interpret_pcr(volume_ratio),
            "contrarian_signal": self._get_contrarian_signal(volume_ratio)
        }

    def _interpret_pcr(self, ratio: float) -> str:
        """Interpret put/call ratio."""
        if ratio > 1.3:
            return "extreme_fear"
        elif ratio > 1.0:
            return "bearish"
        elif ratio > 0.7:
            return "neutral"
        elif ratio > 0.5:
            return "bullish"
        else:
            return "extreme_greed"

    def _get_contrarian_signal(self, ratio: float) -> str:
        """Get contrarian signal from put/call ratio."""
        if ratio > 1.3:
            return "bullish"  # Extreme fear = contrarian buy
        elif ratio < 0.5:
            return "bearish"  # Extreme greed = contrarian sell
        else:
            return "neutral"

    # ==========================================================================
    # COMPOSITE ANALYSIS
    # ==========================================================================

    def get_comprehensive_analysis(
        self,
        symbol: str
    ) -> dict[str, Any]:
        """
        Get comprehensive order flow analysis combining all metrics.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with complete analysis

        Example:
            >>> analysis = analyzer.get_comprehensive_analysis("SPY")
            >>> print(f"GEX: {analysis['gex']['regime']}")
            >>> print(f"Flow: {analysis['flow']['sentiment']}")
            >>> print(f"Max Pain: ${analysis['max_pain']['strike']}")
            >>> print(f"Overall Bias: {analysis['overall_bias']}")
        """
        # Get all components
        gex = self.get_gamma_exposure(symbol)
        flow = self.get_flow_summary(symbol)
        max_pain = self.calculate_max_pain(symbol)
        pcr = self.get_put_call_ratio(symbol)
        unusual = self.detect_unusual_activity(symbol)[:5]  # Top 5

        # Calculate overall bias
        bias_score = 0

        # GEX contribution
        if gex.regime == "high_positive":
            bias_score += 1  # Mean reversion to support
        elif gex.regime == "high_negative":
            bias_score -= 1  # Trending

        # Flow contribution
        if flow.sentiment == FlowSentiment.VERY_BULLISH:
            bias_score += 2
        elif flow.sentiment == FlowSentiment.BULLISH:
            bias_score += 1
        elif flow.sentiment == FlowSentiment.BEARISH:
            bias_score -= 1
        elif flow.sentiment == FlowSentiment.VERY_BEARISH:
            bias_score -= 2

        # Max pain contribution
        if max_pain.distance_to_max_pain > 1:  # Price above max pain
            bias_score -= 0.5  # Gravity pulling down
        elif max_pain.distance_to_max_pain < -1:  # Price below max pain
            bias_score += 0.5  # Gravity pulling up

        # Determine overall bias
        if bias_score >= 2:
            overall_bias = "strong_bullish"
        elif bias_score >= 1:
            overall_bias = "bullish"
        elif bias_score <= -2:
            overall_bias = "strong_bearish"
        elif bias_score <= -1:
            overall_bias = "bearish"
        else:
            overall_bias = "neutral"

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "gex": {
                "total": gex.total_gex,
                "regime": gex.regime,
                "flip_level": gex.flip_level,
                "support": gex.support_levels,
                "resistance": gex.resistance_levels,
            },
            "flow": {
                "sentiment": flow.sentiment.value,
                "net_premium": flow.net_premium,
                "unusual_count": flow.unusual_count,
                "bullish_count": flow.bullish_flow_count,
                "bearish_count": flow.bearish_flow_count,
            },
            "max_pain": {
                "strike": max_pain.max_pain_strike,
                "current_price": max_pain.current_price,
                "distance_percent": max_pain.distance_to_max_pain,
                "gravity": max_pain.gravity_strength,
            },
            "put_call_ratio": pcr,
            "unusual_activity": [u.to_dict() for u in unusual],
            "overall_bias": overall_bias,
            "bias_score": bias_score,
        }

    # ==========================================================================
    # DATA FETCHING (Tradier for chains/prices; Databento stubs for tick data)
    # ==========================================================================

    @staticmethod
    def _greek_data_to_df(greek_data: list) -> pd.DataFrame:
        """
        Normalize List[GreekData] from TradierClient into a standard options chain DataFrame.

        Columns: strike, contract_type, open_interest, volume, bid, ask,
                 last_price, mid, implied_volatility, delta, gamma, theta, vega, rho, symbol.
        """
        if not greek_data:
            return pd.DataFrame()
        return pd.DataFrame([{
            'symbol': g.symbol,
            'strike': g.strike,
            'contract_type': g.option_type,
            'open_interest': g.open_interest,
            'volume': g.volume,
            'bid': g.bid,
            'ask': g.ask,
            'last_price': g.last,
            'mid': g.mid,
            'implied_volatility': g.iv,
            'delta': g.delta,
            'gamma': g.gamma,
            'theta': g.theta,
            'vega': g.vega,
            'rho': g.rho,
        } for g in greek_data])

    def _fetch_option_chain(
        self,
        symbol: str,
        expiry=None
    ) -> pd.DataFrame:
        """Fetch option chain from market data provider."""
        if self._data_provider is None:
            logger.warning("_fetch_option_chain(%s): OptionsDataProvider not available.", symbol)
            return pd.DataFrame()
        try:
            exp = expiry or self._get_nearest_expiry(symbol)
            expiry_str = exp.strftime('%Y-%m-%d') if hasattr(exp, 'strftime') else str(exp)
            greek_data = self._data_provider.get_option_chain_with_greeks(symbol, expiry_str)
            df = self._greek_data_to_df(greek_data)
            if df.empty:
                logger.warning("Empty option chain from Tradier for %s %s", symbol, expiry_str)
            return df
        except Exception as e:
            logger.error("_fetch_option_chain(%s): Tradier error: %s", symbol, e, exc_info=True)
            return pd.DataFrame()

    def _fetch_options_trades(
        self,
        symbol: str,
        lookback_minutes: int
    ) -> list['OptionsFlow']:
        """
        Fetch recent options trades via the configured tick data source.

        Delegates to :attr:`_tick_data_source` when one is set, otherwise
        logs a warning and returns an empty list (stub behaviour).

        Data source: Databento ``OPRA.PILLAR / trades`` schema via
        :class:`DatabentoTickDataSource`.
        """
        if self._tick_data_source is None:
            logger.warning(
                f"_fetch_options_trades({symbol}): No tick data source configured. "
                "Pass a DatabentoTickDataSource via the tick_data_source= argument "
                "or set DATABENTO_API_KEY to enable real data."
            )
            return []
        return self._tick_data_source.fetch_options_trades(symbol, lookback_minutes)

    def _fetch_dark_pool_prints(
        self,
        symbol: str,
        lookback_days: int
    ) -> list['DarkPoolPrint']:
        """
        Fetch dark pool / block trade prints via the configured tick data source.

        Delegates to :attr:`_tick_data_source` when one is set, otherwise
        logs a warning and returns an empty list (stub behaviour).

        Data source: Databento ``DBEQ.BASIC / trades`` schema via
        :class:`DatabentoTickDataSource`.
        """
        if self._tick_data_source is None:
            logger.warning(
                f"_fetch_dark_pool_prints({symbol}): No tick data source configured. "
                "Pass a DatabentoTickDataSource via the tick_data_source= argument "
                "or set DATABENTO_API_KEY to enable real data."
            )
            return []
        return self._tick_data_source.fetch_dark_pool_prints(symbol, lookback_days)

    def _get_underlying_price(self, symbol: str) -> float:
        """Get current underlying price from market data provider."""
        if self._data_provider is None:
            logger.warning("_get_underlying_price(%s): OptionsDataProvider not available.", symbol)
            return 0.0
        try:
            response = self._data_provider.get_quotes([symbol])
            quote = response.get('quotes', {}).get('quote', {})
            if isinstance(quote, list):
                quote = quote[0]
            return float(quote.get('last', 0.0) or 0.0)
        except Exception as e:
            logger.error("_get_underlying_price(%s): Tradier error: %s", symbol, e, exc_info=True)
            return 0.0

    def _get_nearest_expiry(self, symbol: str) -> date:
        """Get nearest options expiration from Tradier."""
        if self._data_provider is not None:
            try:
                response = self._data_provider.get_option_expirations(symbol)
                dates = response.get('expirations', {}).get('date', [])
                if isinstance(dates, str):
                    dates = [dates]
                today = date.today()
                future = sorted(date.fromisoformat(d) for d in dates if date.fromisoformat(d) >= today)
                if future:
                    return future[0]
            except Exception as e:
                logger.warning("_get_nearest_expiry(%s): Tradier error: %s", symbol, e, exc_info=True)
        today = date.today()
        days = (4 - today.weekday()) % 7 or 7
        return today + timedelta(days=days)

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================

    def register_flow_callback(self, callback: Callable[[OptionsFlow], None]):
        """Register callback for all flow updates."""
        self._flow_callbacks.append(callback)

    def register_unusual_callback(self, callback: Callable[[OptionsFlow], None]):
        """Register callback for unusual activity alerts."""
        self._unusual_callbacks.append(callback)

    # ==========================================================================
    # LIFECYCLE
    # ==========================================================================

    def start(self):
        """Start real-time flow tracking."""
        if not self.enable_realtime:
            logger.warning("Real-time tracking not enabled")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_realtime, daemon=True)
        self._thread.start()
        logger.info("OrderFlowAnalyzer real-time tracking started")

    def stop(self):
        """Stop real-time tracking."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("OrderFlowAnalyzer stopped")

    def detect_order_flow_anomalies(
        self,
        symbol: str,
        window: int = 20,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Use the stumpy Matrix Profile to find anomalous (discord) patterns in
        net delta order flow.  Discords have the highest 1-nearest-neighbour
        distance in Matrix-Profile space — i.e., they are the most unusual
        sub-sequences seen in the time series.

        Args:
            symbol: Trading symbol to analyse.
            window: Sub-sequence length for the Matrix Profile (default 20 ticks).
            top_k: Number of top discords to return.

        Returns:
            List of dicts with keys ``index``, ``mp_distance``, ``start_time``.
            Empty list when stumpy is unavailable or data is insufficient.
        """
        if not _STUMPY_AVAILABLE:
            logger.debug("stumpy not available — skipping matrix-profile anomaly detection")
            return []

        with self._lock:
            trades = list(self.flow_history.get(symbol, []))

        if len(trades) < window * 2:
            return []

        try:
            net_delta = np.array(
                [t.size if t.sentiment == FlowDirection.BULLISH else -t.size for t in trades],
                dtype=float,
            )
            mp = stumpy.stump(net_delta, m=window)
            profile = mp[:, 0].astype(float)  # column 0 = Matrix Profile distances

            # Discords = indices with highest MP distance
            discord_indices = np.argsort(profile)[::-1][:top_k]
            results = []
            for idx in discord_indices:
                ts = trades[int(idx)].timestamp if int(idx) < len(trades) else None
                results.append({
                    "index": int(idx),
                    "mp_distance": float(profile[idx]),
                    "start_time": ts,
                })
            return results
        except Exception as exc:
            logger.warning("Order flow matrix-profile anomaly detection failed: %s", exc, exc_info=True)
            return []

    def _run_realtime(self):
        """Real-time tracking loop."""
        while self._running:
            try:
                for symbol in self.symbols:
                    # Update GEX
                    self.get_gamma_exposure(symbol, use_cache=False)

                    # Check for unusual activity
                    self.detect_unusual_activity(symbol)

                time.sleep(GEX_CALCULATION_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                logger.error("Real-time tracking error: %s", e, exc_info=True)
                time.sleep(5)  # thread-safe: time.sleep() intentional


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_order_flow_analyzer_from_env() -> 'OrderFlowAnalyzer':
    """
    Create :class:`OrderFlowAnalyzer` from environment variables.

    Reads:

    * ``MARKET_DATA_PROVIDER`` — options chain provider (``tradier`` / ``databento``)
    * ``DATABENTO_API_KEY``    — enables :class:`DatabentoTickDataSource` for live
      options trades and dark pool block prints
    * ``FLOW_SYMBOLS``         — comma-separated symbols (default: ``SPY,QQQ``)
    * ``ENABLE_REALTIME_FLOW`` — ``true`` / ``false`` (default ``false``)
    """
    import os
    data_provider = None
    if create_options_data_provider is not None:
        try:
            data_provider = create_options_data_provider()
        except Exception as e:
            logger.warning("Could not create OptionsDataProvider: %s", e, exc_info=True)

    # Wire Databento tick data source when key is present
    tick_source: BaseTickDataSource | None = None
    databento_key = os.getenv("DATABENTO_API_KEY")
    if databento_key:
        if HAS_DATABENTO:
            try:
                tick_source = DatabentoTickDataSource(api_key=databento_key)
                logger.info("DatabentoTickDataSource enabled for options trades and dark pool prints")
            except Exception as exc:
                logger.warning("Could not create DatabentoTickDataSource: %s", exc, exc_info=True)
        else:
            logger.warning(
                "DATABENTO_API_KEY is set but the 'databento' package is not installed. "
                "Run: pip install databento"
            , exc_info=True)

    symbols = os.getenv("FLOW_SYMBOLS", "SPY,QQQ").split(",")
    return OrderFlowAnalyzer(
        data_provider=data_provider,
        symbols=symbols,
        enable_realtime=os.getenv("ENABLE_REALTIME_FLOW", "false").lower() == "true",
        tick_data_source=tick_source,
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":


    analyzer = OrderFlowAnalyzer(symbols=["SPY"])

    # Test GEX
    gex = analyzer.get_gamma_exposure("SPY")

    # Test Flow Summary
    flow = analyzer.get_flow_summary("SPY")

    # Test Max Pain
    max_pain = analyzer.calculate_max_pain("SPY")

    # Test Comprehensive
    analysis = analyzer.get_comprehensive_analysis("SPY")
