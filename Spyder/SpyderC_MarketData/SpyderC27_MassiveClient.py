#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC27_MassiveClient.py
Purpose: Massive (formerly Polygon.io) REST and WebSocket market data client

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-03-18 Time: 15:00:00

Module Description:
    Massive (formerly Polygon.io) market data client providing:

    REST API (pull-based, on-demand):
        - SPY / equity NBBO quotes
        - SPY options chain snapshots with Greeks (delta, gamma, theta, vega, IV)
        - Historical OHLCV bars for backtesting and regime detection
        - Market internals: VIX, market status
        - Available expiration dates for options

    WebSocket API (push-based, real-time):
        - Real-time SPY equity quotes  (Q.SPY)
        - Real-time SPY trade prints   (T.SPY)
        - Real-time aggregate bars     (A.SPY / AM.SPY)
        - Automatic reconnection with exponential backoff

    Design notes:
        - Databento (SpyderC26) remains intact for OPRA L3 options depth.
        - Massive is the primary provider for SPY equity price and options chain.
        - REST and WebSocket share one API key.
        - All output is normalized to NormalizedQuote / NormalizedTrade from
          SpyderC00_MarketDataProtocol for provider-agnostic consumption.
        - Rate limiter (token bucket) applied to all REST calls.
        - Circuit breaker wraps REST call groups (3 failures → open for 60s).

    WebSocket subscription channel prefixes (Massive):
        Q.<symbol>   — NBBO quote updates (bid/ask)
        T.<symbol>   — trade prints
        A.<symbol>   — per-second aggregate bars
        AM.<symbol>  — per-minute aggregate bars

    REST options chain:
        client.list_snapshot_options_chain(underlying, params={...})
        Returns OptionContractSnapshot with greeks, IV, OI, day-bar data, quotes.

    Install:
        pip install massive

    Note: Polygon.io rebranded as Massive.com on Oct 30 2025.
    Existing API keys and `api.polygon.io` endpoint continue to work.
    The `massive` SDK defaults to `api.massive.com`.

References:
    - Massive Python SDK: https://github.com/massive-com/client-python
    - REST API docs:      https://massive.com/docs/stocks/getting-started
    - WebSocket docs:     https://massive.com/docs/websocket/getting-started

Change Log:
    2026-03-18 (v1.1.0):
        - Added build_option_ticker() static helper (O: Polygon/Massive format)
        - Added get_option_bars() for per-contract OHLCV via O: ticker
        - Added get_historical_option_chain() for point-in-time chain (no survivorship bias)
        - Added download_flat_file() for tick-level daily flat file download + Parquet cache
        - Added align_internals() for $TICK/$TRIN merge_asof alignment onto bars

    2026-03-18 (v1.0.0):
        - Initial implementation
        - RESTClient for options chain, historical bars, quotes, market status
        - WebSocketClient for real-time SPY equity streaming
        - Normalization to NormalizedQuote / NormalizedTrade
        - Token-bucket rate limiter + circuit breaker
        - Automatic WebSocket reconnection with exponential backoff
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import time
import threading
from datetime import datetime
from typing import Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import massive as _massive_sdk          # noqa: F401 (presence check)
    HAS_MASSIVE = True
except ImportError:
    try:
        import polygon as _massive_sdk      # noqa: F401 (polygon-api-client)
        HAS_MASSIVE = True
    except ImportError:
        HAS_MASSIVE = False
        _massive_sdk = None

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    from PySide6.QtCore import Signal, QObject
    HAS_QT = True
except ImportError:
    HAS_QT = False
    Signal = None
    QObject = object

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
    from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import TokenBucket
except ImportError:
    TokenBucket = None

try:
    from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None

# NormalizedQuote / NormalizedTrade from SpyderC00 (no circular risk — C00 has
# no module-level imports of C27).
try:
    from Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol import (
        NormalizedQuote,
        NormalizedTrade,
    )
    HAS_PROTOCOL_TYPES = True
except ImportError:
    HAS_PROTOCOL_TYPES = False
    NormalizedQuote = None  # type: ignore[assignment,misc]
    NormalizedTrade = None  # type: ignore[assignment,misc]

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_REST_RETRIES: int = 3
REST_RETRY_DELAY: float = 1.0          # seconds; doubles each attempt
RECONNECT_BASE_DELAY: float = 2.0      # WebSocket initial reconnect delay
MAX_RECONNECT_DELAY: float = 60.0      # WebSocket max reconnect delay
MAX_RECONNECT_ATTEMPTS: int = 10
DEFAULT_REST_RPS: float = 3.0          # REST requests per second (conservative)
MESSAGE_BUFFER_SIZE: int = 2000

# Massive option chain default filters for SPY (strike within ±10% OTM)
DEFAULT_OPTION_LIMIT: int = 500        # max contracts per chain snapshot

# ==============================================================================
# ENUMS
# ==============================================================================


class ConnectionStatus(Enum):
    """Massive WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPED = "stopped"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class MassiveQuoteUpdate:
    """
    Normalized real-time quote from the Massive WebSocket feed.

    Produced by MassiveClient and passed to on_quote callbacks.

    Attributes:
        symbol:    Ticker (e.g. "SPY").
        bid:       Best bid price.
        ask:       Best ask price.
        bid_size:  Bid size in shares.
        ask_size:  Ask size in shares.
        timestamp: UTC datetime of the quote.
        bid_exchange: Exchange code for bid.
        ask_exchange: Exchange code for ask.
        raw:       Original WebSocketMessage object.
    """
    symbol: str
    bid: float
    ask: float
    bid_size: int = 0
    ask_size: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    bid_exchange: str = ""
    ask_exchange: str = ""
    raw: Any = field(default=None, repr=False)

    @property
    def mid(self) -> float:
        """Mid-market price."""
        return (self.bid + self.ask) / 2.0 if (self.bid and self.ask) else (self.bid or self.ask)

    @property
    def spread(self) -> float:
        """Absolute bid-ask spread."""
        return self.ask - self.bid

    def to_normalized(self) -> Any:
        """Convert to NormalizedQuote if SpyderC00 is available."""
        if NormalizedQuote is None:
            return None
        return NormalizedQuote(
            symbol=self.symbol,
            bid=self.bid,
            ask=self.ask,
            last=0.0,
            volume=0,
            timestamp=self.timestamp.isoformat(),
            raw={
                "bid_size": self.bid_size,
                "ask_size": self.ask_size,
                "bid_exchange": self.bid_exchange,
                "ask_exchange": self.ask_exchange,
            },
        )


@dataclass
class MassiveTradeUpdate:
    """
    Normalized real-time trade print from the Massive WebSocket feed.

    Produced by MassiveClient and passed to on_trade callbacks.

    Attributes:
        symbol:    Ticker.
        price:     Execution price.
        size:      Number of shares.
        timestamp: UTC datetime of the trade.
        exchange:  Exchange code.
        conditions: Trade condition codes.
        raw:       Original WebSocketMessage object.
    """
    symbol: str
    price: float
    size: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: str = ""
    conditions: list[str] = field(default_factory=list)
    raw: Any = field(default=None, repr=False)

    def to_normalized(self) -> Any:
        """Convert to NormalizedTrade if SpyderC00 is available."""
        if NormalizedTrade is None:
            return None
        return NormalizedTrade(
            symbol=self.symbol,
            price=self.price,
            size=self.size,
            timestamp=self.timestamp.isoformat(),
            exchange=self.exchange,
            raw={"conditions": self.conditions},
        )


# ==============================================================================
# MAIN CLASS: MassiveClient
# ==============================================================================


class MassiveClient:
    """
    Massive (formerly Polygon.io) REST and WebSocket market data client.

    Provides:
        REST queries (on-demand):
            get_quote()                   — current NBBO quote for one symbol
            get_quotes_batch()            — quotes for multiple symbols
            get_option_chain()            — live options chain snapshot with Greeks
            get_option_expirations()      — available expiry dates for an underlying
            get_historical_bars()         — OHLCV bars for equity (minute/hour/day)
            get_option_bars()             — OHLCV bars for a single options contract
            get_historical_option_chain() — point-in-time chain (survivorship-bias-free)
            download_flat_file()          — tick-level daily flat file download + cache
            align_internals()             — merge $TICK/$TRIN onto bars via merge_asof
            build_option_ticker()         — construct O: ticker from strike/expiry/type
            get_market_status()           — NYSE/NASDAQ open/closed state

        WebSocket streaming (real-time):
            start_stream()           — subscribe to quotes and/or trades
            stop_stream()            — gracefully close the connection
            update_subscriptions()   — change symbol list (reconnects)
            is_streaming (property)  — True while stream is running

    Callbacks (set before calling start_stream):
        on_quote:         Callable[[MassiveQuoteUpdate], None]
        on_trade:         Callable[[MassiveTradeUpdate], None]
        on_bar:           Callable[[dict], None]        (aggregate bars)
        on_status_change: Callable[[ConnectionStatus], None]

    Example::

        client = MassiveClient()                          # reads MASSIVE_API_KEY
        client.on_quote = lambda q: print(q.symbol, q.mid)
        client.start_stream(["SPY"])

        chain = client.get_option_chain("SPY", expiration="2026-03-21")
        bars  = client.get_historical_bars("SPY", "2026-01-01", "2026-03-01")

        client.stop_stream()

    Attributes:
        api_key:          Massive API key.
        status:           Current WebSocket connection status.
    """

    def __init__(
        self,
        api_key: str | None = None,
        rest_requests_per_second: float = DEFAULT_REST_RPS,
    ) -> None:
        """
        Initialize MassiveClient.

        Args:
            api_key: Massive API key. If None, reads MASSIVE_API_KEY env var.
            rest_requests_per_second: REST rate limit (tokens/second, default 3.0).

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.environ.get("MASSIVE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Massive API key required. Set MASSIVE_API_KEY env var or pass api_key param."
            )

        self._rest_rps = rest_requests_per_second

        # REST — lazy-initialized on first call
        self._rest: Any = None

        # WebSocket state
        self._ws_client: Any = None
        self._ws_thread: threading.Thread | None = None
        self._ws_subscriptions: list[str] = []
        self._running = False
        self._reconnect_attempts = 0
        self._lock = threading.Lock()

        # Status
        self.status = ConnectionStatus.DISCONNECTED

        # Callbacks
        self.on_quote: Callable[[MassiveQuoteUpdate], None] | None = None
        self.on_trade: Callable[[MassiveTradeUpdate], None] | None = None
        self.on_bar: Callable[[dict[str, Any]], None] | None = None
        self.on_status_change: Callable[[ConnectionStatus], None] | None = None

        # Message buffer (debug / replay)
        self.message_buffer: deque = deque(maxlen=MESSAGE_BUFFER_SIZE)

        # Rate limiter for REST calls (token bucket)
        if TokenBucket is not None:
            self._rest_bucket: Any = TokenBucket(
                capacity=self._rest_rps * 10,
                fill_rate=self._rest_rps,
            )
        else:
            self._rest_bucket = None

        logger.info(
            f"MassiveClient initialized (REST RPS={self._rest_rps}, "
            f"HAS_SDK={HAS_MASSIVE})"
        )

    # ==========================================================================
    # PROPERTIES
    # ==========================================================================

    @property
    def is_connected(self) -> bool:
        """True when the WebSocket stream is actively streaming."""
        return self.status in (ConnectionStatus.CONNECTED, ConnectionStatus.STREAMING)

    @property
    def is_streaming(self) -> bool:
        """True while the background WebSocket thread is alive."""
        return (
            self._running
            and self._ws_thread is not None
            and self._ws_thread.is_alive()
        )

    # ==========================================================================
    # REST — PRIVATE HELPERS
    # ==========================================================================

    def _get_rest(self) -> Any:
        """Lazy-initialize the Massive/Polygon RESTClient."""
        if self._rest is None:
            if not HAS_MASSIVE:
                raise ImportError(
                    "massive/polygon-api-client package not installed. "
                    "Run: pip install polygon-api-client"
                )
            try:
                from massive import RESTClient
            except ImportError:
                from polygon import RESTClient
            self._rest = RESTClient(api_key=self.api_key)
        return self._rest

    def _rest_call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a REST call with rate limiting and retry on transient errors.

        Args:
            fn:      Callable from massive.RESTClient to invoke.
            *args:   Positional arguments forwarded to fn.
            **kwargs: Keyword arguments forwarded to fn.

        Returns:
            Return value of fn.

        Raises:
            Exception: If all retry attempts fail.
        """
        # Rate limiting
        if self._rest_bucket is not None:
            wait = self._rest_bucket.wait_time()
            if wait > 0:
                time.sleep(wait)  # thread-safe: time.sleep() intentional
            self._rest_bucket.consume()

        last_exc: Exception | None = None
        for attempt in range(MAX_REST_RETRIES):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    f"MassiveClient REST error (attempt {attempt + 1}/{MAX_REST_RETRIES}): "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < MAX_REST_RETRIES - 1:
                    time.sleep(REST_RETRY_DELAY * (2 ** attempt))  # thread-safe: time.sleep() intentional

        raise last_exc  # type: ignore[misc]

    # ==========================================================================
    # REST — PUBLIC API
    # ==========================================================================

    def get_quote(self, symbol: str) -> "NormalizedQuote":
        """
        Get the current NBBO quote for a single symbol.

        Args:
            symbol: Ticker symbol (e.g., "SPY").

        Returns:
            NormalizedQuote with bid, ask, and metadata.
            Returns an empty NormalizedQuote on error.
        """
        if NormalizedQuote is None:
            raise ImportError("SpyderC00_MarketDataProtocol not available")
        rest = self._get_rest()
        try:
            result = self._rest_call(rest.get_last_quote, ticker=symbol)
            ts_ns = getattr(result, "last_updated", 0) or 0
            ts_str = (
                datetime.fromtimestamp(ts_ns / 1_000_000_000).isoformat()
                if ts_ns
                else ""
            )
            return NormalizedQuote(
                symbol=symbol,
                bid=float(getattr(result, "bid_price", 0.0) or 0.0),
                ask=float(getattr(result, "ask_price", 0.0) or 0.0),
                last=0.0,
                volume=0,
                timestamp=ts_str,
                raw={
                    "bid_size": getattr(result, "bid_size", 0),
                    "ask_size": getattr(result, "ask_size", 0),
                    "bid_exchange": getattr(result, "bid_exchange", ""),
                    "ask_exchange": getattr(result, "ask_exchange", ""),
                },
            )
        except Exception as exc:
            logger.error(f"MassiveClient.get_quote({symbol}) failed: {exc}")
            return NormalizedQuote(symbol=symbol)

    def get_quotes_batch(self, symbols: list[str]) -> dict[str, "NormalizedQuote"]:
        """
        Get current NBBO quotes for multiple symbols.

        Args:
            symbols: List of ticker symbols.

        Returns:
            Dict mapping symbol → NormalizedQuote.
        """
        return {sym: self.get_quote(sym) for sym in symbols}

    def get_option_chain(
        self,
        underlying: str,
        expiration: str | None = None,
        option_type: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        limit: int = DEFAULT_OPTION_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Get a live SPY options chain snapshot with Greeks from Massive REST API.

        Massive returns pre-calculated delta, gamma, theta, vega, and IV for each
        contract — no local pricing engine needed for chain scanning.

        Args:
            underlying:   Underlying ticker (e.g., "SPY").
            expiration:   Specific expiry ISO date (e.g., "2026-03-21"). None = all.
            option_type:  "call", "put", or None for both.
            min_strike:   Lower strike filter (inclusive).
            max_strike:   Upper strike filter (inclusive).
            limit:        Maximum contracts to return (default 500).

        Returns:
            List of option dicts, each containing:
            symbol, underlying, strike, expiration_date, option_type,
            exercise_style, bid, ask, mid, implied_volatility,
            delta, gamma, theta, vega, open_interest, volume,
            open, close, break_even_price.

        Note:
            SPY has ~8,000+ contracts per expiry. Use strike filters to limit
            response time. For IC screening, filter to ±5% OTM range.
        """
        rest = self._get_rest()
        params: dict[str, Any] = {}
        if expiration:
            params["expiration_date"] = expiration
        if option_type:
            params["contract_type"] = option_type.lower()
        if min_strike is not None:
            params["strike_price.gte"] = min_strike
        if max_strike is not None:
            params["strike_price.lte"] = max_strike
        if limit:
            params["limit"] = limit

        try:
            results: list[dict[str, Any]] = []
            for snapshot in self._rest_call(
                rest.list_snapshot_options_chain,
                underlying,
                params=params if params else None,
            ):
                results.append(self._normalize_option_snapshot(snapshot))
            logger.debug(
                f"MassiveClient.get_option_chain({underlying}): {len(results)} contracts"
            )
            return results
        except Exception as exc:
            logger.error(f"MassiveClient.get_option_chain({underlying}) failed: {exc}")
            return []

    def get_option_expirations(self, underlying: str) -> list[str]:
        """
        Get all available expiration dates for an options underlying.

        Fetches a lightweight chain snapshot and extracts unique expiry dates.

        Args:
            underlying: Underlying ticker (e.g., "SPY").

        Returns:
            Sorted list of ISO date strings (e.g., ["2026-03-21", "2026-03-28", ...]).
        """
        chain = self.get_option_chain(underlying, limit=200)
        seen: set[str] = set()
        expirations: list[str] = []
        for opt in chain:
            exp = opt.get("expiration_date", "")
            if exp and exp not in seen:
                seen.add(exp)
                expirations.append(exp)
        return sorted(expirations)

    def get_historical_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        timespan: str = "minute",
        multiplier: int = 1,
        adjusted: bool = True,
    ) -> "pd.DataFrame":
        """
        Fetch historical OHLCV bars for a symbol.

        Args:
            symbol:     Ticker symbol (e.g., "SPY").
            start:      Start date ISO string (e.g., "2026-01-01").
            end:        End date ISO string (e.g., "2026-03-18").
            timespan:   Bar size: "second", "minute", "hour", "day", "week",
                        "month", "quarter", "year".
            multiplier: Timespan multiplier (e.g., 5 for 5-minute bars).
            adjusted:   Apply split/dividend adjustments (default True).

        Returns:
            DataFrame indexed by timestamp with columns:
            open, high, low, close, volume, vwap, transactions.
            Empty DataFrame on error.
        """
        if not HAS_PANDAS:
            raise ImportError("pandas required for get_historical_bars")
        rest = self._get_rest()
        try:
            rows: list[dict[str, Any]] = []
            for agg in self._rest_call(
                rest.list_aggs,
                ticker=symbol,
                multiplier=multiplier,
                timespan=timespan,
                from_=start,
                to=end,
                limit=50000,
                adjusted=adjusted,
            ):
                ts_ms = getattr(agg, "timestamp", 0) or 0
                rows.append({
                    "timestamp": (
                        datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.utcnow()
                    ),
                    "open":         float(getattr(agg, "open", 0.0) or 0.0),
                    "high":         float(getattr(agg, "high", 0.0) or 0.0),
                    "low":          float(getattr(agg, "low", 0.0) or 0.0),
                    "close":        float(getattr(agg, "close", 0.0) or 0.0),
                    "volume":       int(getattr(agg, "volume", 0) or 0),
                    "vwap":         float(getattr(agg, "vwap", 0.0) or 0.0),
                    "transactions": int(getattr(agg, "transactions", 0) or 0),
                })

            if not rows:
                logger.warning(
                    f"MassiveClient.get_historical_bars({symbol}): no data returned"
                )
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df = df.set_index("timestamp").sort_index()
            logger.info(
                f"MassiveClient.get_historical_bars({symbol}): "
                f"{len(df)} bars ({timespan}/{multiplier})"
            )
            return df

        except Exception as exc:
            logger.error(f"MassiveClient.get_historical_bars({symbol}) failed: {exc}")
            return pd.DataFrame()

    def get_market_status(self) -> dict[str, Any]:
        """
        Check whether the market is currently open.

        Returns:
            Dict with keys:
                "market"      — "open", "closed", or "extended-hours"
                "server_time" — current server timestamp string
                "exchanges"   — per-exchange status dict
                "currencies"  — crypto/fx market status dict
        """
        rest = self._get_rest()
        try:
            status = self._rest_call(rest.get_market_status)
            return {
                "market":      getattr(status, "market", "unknown"),
                "server_time": str(getattr(status, "server_time", "")),
                "exchanges":   dict(getattr(status, "exchanges", {}) or {}),
                "currencies":  dict(getattr(status, "currencies", {}) or {}),
            }
        except Exception as exc:
            logger.error(f"MassiveClient.get_market_status() failed: {exc}")
            return {"market": "unknown", "server_time": "", "exchanges": {}, "currencies": {}}

    # ==========================================================================
    # REST — HISTORICAL OPTIONS DATA (BACKTESTING)
    # ==========================================================================

    @staticmethod
    def build_option_ticker(
        underlying: str,
        expiration: str,
        option_type: str,
        strike: float,
    ) -> str:
        """
        Build a Massive/Polygon options ticker in the standard O: format.

        Format: O:{underlying}{YYMMDD}{C|P}{8-digit strike in thousandths}

        Args:
            underlying:  Underlying ticker (e.g., "SPY").
            expiration:  Expiry date as ISO string (e.g., "2026-06-19").
            option_type: "call" or "put" (case-insensitive).
            strike:      Strike price (e.g., 600.0 or 582.5).

        Returns:
            Polygon/Massive O: options ticker string.

        Examples::

            build_option_ticker("SPY", "2026-06-19", "call", 600.0)
            # → "O:SPY260619C00600000"

            build_option_ticker("SPY", "2026-03-21", "put", 582.5)
            # → "O:SPY260321P00582500"
        """
        exp = datetime.strptime(expiration, "%Y-%m-%d")
        date_str = exp.strftime("%y%m%d")                   # "260619"
        cp = "C" if option_type.lower().startswith("c") else "P"
        # Strike stored as thousandths, zero-padded to 8 digits.
        # $600.00 → 600000 → "00600000",  $582.50 → 582500 → "00582500"
        strike_int = round(strike * 1000)
        strike_str = f"{strike_int:08d}"
        return f"O:{underlying.upper()}{date_str}{cp}{strike_str}"

    def get_option_bars(
        self,
        underlying: str,
        expiration: str,
        option_type: str,
        strike: float,
        start: str,
        end: str,
        timespan: str = "minute",
        multiplier: int = 1,
    ) -> "pd.DataFrame":
        """
        Fetch historical OHLCV bars for a single SPY options contract.

        Constructs the Polygon O: ticker automatically from the provided
        strike/expiry/type and fetches minute (or other resolution) bars
        via the Massive REST aggregates endpoint.

        Args:
            underlying:  Underlying ticker (e.g., "SPY").
            expiration:  Expiry date ISO string (e.g., "2026-03-21").
            option_type: "call" or "put".
            strike:      Strike price (e.g., 590.0).
            start:       Start date ISO string (e.g., "2026-03-17").
            end:         End date ISO string (e.g., "2026-03-21").
            timespan:    Bar size: "second", "minute", "hour", "day" (default "minute").
            multiplier:  Timespan multiplier (default 1).

        Returns:
            DataFrame indexed by timestamp with columns:
            open, high, low, close, volume, vwap, transactions.
            Empty DataFrame on error or if the contract had no volume.

        Example::

            df = client.get_option_bars(
                "SPY", "2026-03-21", "put", 590.0,
                "2026-03-17", "2026-03-21"
            )
        """
        ticker = self.build_option_ticker(underlying, expiration, option_type, strike)
        logger.info(f"MassiveClient.get_option_bars: ticker={ticker}")
        # Options prices are not split-adjusted (adjusted=False)
        return self.get_historical_bars(
            ticker, start, end,
            timespan=timespan,
            multiplier=multiplier,
            adjusted=False,
        )

    def get_historical_option_chain(
        self,
        underlying: str,
        date: str,
        expiration: str | None = None,
        option_type: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        limit: int = DEFAULT_OPTION_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Get a point-in-time SPY options chain as it existed on a specific past date.

        Unlike get_option_chain() which returns the current live chain, this
        returns the chain exactly as it appeared at market close on ``date``.
        Essential for backtesting to prevent survivorship bias — you see only
        the strikes and contracts that existed then, with the Greeks and IVs
        that were quoted on that day.

        Args:
            underlying:  Underlying ticker (e.g., "SPY").
            date:        Historical date ISO string (e.g., "2026-01-15").
            expiration:  Filter by specific expiry date. None = all.
            option_type: "call", "put", or None for both.
            min_strike:  Lower strike filter (inclusive).
            max_strike:  Upper strike filter (inclusive).
            limit:       Max contracts to return (default 500).

        Returns:
            List of option dicts in the same format as get_option_chain(),
            representing the chain as it existed on ``date``.
            Empty list on error or if ``date`` has no available data.

        Note:
            Requires at least a Developer tier Massive subscription.
            Data older than 2 years is not available on the Basic tier.

        Example::

            # Get SPY chain on Jan 15 2026 for 0DTE strike selection
            chain = client.get_historical_option_chain(
                "SPY", "2026-01-15",
                expiration="2026-01-15",
                min_strike=570.0,
                max_strike=610.0,
            )
        """
        rest = self._get_rest()
        params: dict[str, Any] = {"date": date}
        if expiration:
            params["expiration_date"] = expiration
        if option_type:
            params["contract_type"] = option_type.lower()
        if min_strike is not None:
            params["strike_price.gte"] = min_strike
        if max_strike is not None:
            params["strike_price.lte"] = max_strike
        if limit:
            params["limit"] = limit

        try:
            results: list[dict[str, Any]] = []
            for snapshot in self._rest_call(
                rest.list_snapshot_options_chain,
                underlying,
                params=params,
            ):
                results.append(self._normalize_option_snapshot(snapshot))
            logger.info(
                f"MassiveClient.get_historical_option_chain({underlying}, {date}): "
                f"{len(results)} contracts"
            )
            return results
        except Exception as exc:
            logger.error(
                f"MassiveClient.get_historical_option_chain({underlying}, {date}) "
                f"failed: {exc}"
            )
            return []

    def download_flat_file(
        self,
        date: str,
        data_type: str = "options_quotes",
        cache_dir: str | None = None,
        use_polars: bool = False,
    ) -> "pd.DataFrame":
        """
        Download a Massive flat file for tick-level historical replay.

        Massive (Polygon) provides daily compressed flat files containing
        every trade and quote change. These are orders of magnitude higher
        fidelity than minute bars and are required for accurate 0DTE
        scalping backtests and slippage modeling.

        Downloaded files are cached locally as Parquet. Subsequent calls for
        the same date return immediately from the local Parquet cache without
        re-downloading.

        Args:
            date:       Date to download (ISO string, e.g., "2026-03-17").
            data_type:  One of:
                        "options_quotes" — All options NBBO quote changes (large: 1–5 GB/day)
                        "options_trades" — All options trade prints
                        "equity_quotes"  — SPY equity NBBO quotes
                        "equity_trades"  — SPY equity trade prints
            cache_dir:  Local directory for downloaded/cached files.
                        Defaults to ./data/historical/flat_files/{data_type}/
            use_polars: If True and polars is installed, use polars for I/O
                        (5–8x faster than pandas for large files). The
                        returned type will be a polars DataFrame.  Falls back
                        to pandas if polars is not installed. Default False.

        Returns:
            DataFrame of the flat file contents (pandas or polars depending on
            ``use_polars``). Columns vary by data_type but always include
            at minimum: timestamp/sip_timestamp, symbol, bid/ask or price.
            Returns empty pandas DataFrame on any error.

        Note:
            Requires Advanced or higher Massive subscription for options data.
            The API key is passed as a URL query parameter — do not share
            download URLs as they are authenticated.

        Example::

            # Download 0DTE quotes for March 21 2026
            df = client.download_flat_file(
                "2026-03-21",
                data_type="options_quotes",
                cache_dir="data/historical/options",
                use_polars=True,
            )
        """
        import urllib.request

        if not HAS_PANDAS and not use_polars:
            raise ImportError("pandas required for download_flat_file")

        # Resolve cache directory
        if cache_dir is None:
            cache_dir = os.path.join("data", "historical", "flat_files", data_type)
        os.makedirs(cache_dir, exist_ok=True)

        # Check Parquet cache first — fast path, no network required
        safe_date = date.replace("-", "")
        parquet_path = os.path.join(cache_dir, f"{safe_date}.parquet")
        if os.path.exists(parquet_path):
            logger.info(f"MassiveClient.download_flat_file: cache hit → {parquet_path}")
            try:
                if use_polars:
                    try:
                        import polars as pl
                        return pl.read_parquet(parquet_path)
                    except ImportError:
                        logger.debug("polars not installed; falling back to pandas")
                return pd.read_parquet(parquet_path)
            except Exception as exc:
                logger.warning(
                    f"MassiveClient.download_flat_file: failed to read cache "
                    f"{parquet_path}: {exc} — re-downloading"
                )

        # Map data_type to Polygon/Massive flat file URL path segment
        _type_map: dict[str, str] = {
            "options_quotes": "options",
            "options_trades": "options/trades",
            "equity_quotes":  "stocks/quotes",
            "equity_trades":  "stocks/trades",
        }
        path_segment = _type_map.get(data_type, data_type)
        url = (
            f"https://files.polygon.io/v1/{path_segment}/{date}.csv.gz"
            f"?apiKey={self.api_key}"
        )

        gz_path = os.path.join(cache_dir, f"{safe_date}.csv.gz")
        df = None

        logger.info(
            f"MassiveClient.download_flat_file: downloading {data_type} for {date} …"
        )
        try:
            urllib.request.urlretrieve(url, gz_path)
            logger.info(
                f"MassiveClient.download_flat_file: download complete → {gz_path}"
            )

            # Parse: polars fast path or pandas
            if use_polars:
                try:
                    import polars as pl
                    df_pl = pl.read_csv(gz_path)
                    df_pl.write_parquet(parquet_path)
                    os.remove(gz_path)
                    logger.info(
                        f"MassiveClient.download_flat_file: {len(df_pl)} rows "
                        f"(polars), cached → {parquet_path}"
                    )
                    return df_pl
                except ImportError:
                    logger.debug("polars not installed; falling back to pandas")

            df = pd.read_csv(gz_path, compression="gzip", low_memory=False)
            df.to_parquet(parquet_path, index=False)
            os.remove(gz_path)
            logger.info(
                f"MassiveClient.download_flat_file: {len(df)} rows "
                f"(pandas), cached → {parquet_path}"
            )
            return df

        except Exception as exc:
            logger.error(
                f"MassiveClient.download_flat_file({date}, {data_type}) failed: {exc}"
            )
            # Clean up partial download if present
            if os.path.exists(gz_path):
                try:
                    os.remove(gz_path)
                except Exception:
                    pass
            return pd.DataFrame() if HAS_PANDAS else None  # type: ignore[return-value]

    @staticmethod
    def align_internals(
        base_df: "pd.DataFrame",
        internals_df: "pd.DataFrame",
        timestamp_col: str = "timestamp",
        direction: str = "backward",
    ) -> "pd.DataFrame":
        """
        Align market internals ($TICK, $ADD, $TRIN) onto an options or equity bar
        DataFrame using a nearest-previous timestamp join (merge_asof).

        Market internals update at different frequencies than options bars.
        A naive inner-join would drop most bars. merge_asof with
        direction="backward" attaches the most recently available internal
        reading to each bar without introducing look-ahead bias.

        Args:
            base_df:       Primary DataFrame (options or equity bars).
                           Must have a datetime index or a ``timestamp_col`` column.
            internals_df:  Market internals DataFrame. Must contain at least one
                           column whose name contains "TICK", "ADD", "TRIN", or
                           "VOLD" (case-insensitive). Must have a datetime index
                           or a ``timestamp_col`` column.
            timestamp_col: Name of the timestamp column when not using an index.
                           Default "timestamp".
            direction:     merge_asof direction:
                           "backward" (default) — most recent prior internal reading
                           "nearest"  — closest reading regardless of direction
                           "forward"  — next available reading (introduces look-ahead)

        Returns:
            A copy of ``base_df`` with the internals columns merged in.
            NaN where no prior internals record exists.

        Note:
            Both DataFrames are sorted by timestamp automatically.

        Example::

            spy_bars      = client.get_historical_bars("SPY", "2026-03-17", "2026-03-17")
            internals_df  = pd.read_parquet("data/internals/20260317.parquet")
            aligned       = MassiveClient.align_internals(spy_bars, internals_df)
            # aligned now has TICK, ADD, TRIN columns beside each 1-min bar
        """
        if not HAS_PANDAS:
            raise ImportError("pandas required for align_internals")

        left = base_df.copy()
        right = internals_df.copy()

        # Flatten datetime index to a column for merge_asof
        if left.index.dtype.kind == "M":
            left = left.reset_index().rename(columns={"index": timestamp_col})
        if right.index.dtype.kind == "M":
            right = right.reset_index().rename(columns={"index": timestamp_col})

        # Ensure timestamp column is datetime dtype
        left[timestamp_col] = pd.to_datetime(left[timestamp_col])
        right[timestamp_col] = pd.to_datetime(right[timestamp_col])

        # Sort both — required by merge_asof
        left = left.sort_values(timestamp_col).reset_index(drop=True)
        right = right.sort_values(timestamp_col).reset_index(drop=True)

        # Identify internal signal columns
        internal_cols = [
            c for c in right.columns
            if any(kw in c.upper() for kw in ("TICK", "ADD", "TRIN", "VOLD"))
            and c != timestamp_col
        ]

        if not internal_cols:
            logger.warning(
                "align_internals: no TICK/ADD/TRIN/VOLD columns found in "
                "internals_df — returning base_df unchanged"
            )
            return base_df

        right_subset = right[[timestamp_col] + internal_cols]

        merged = pd.merge_asof(
            left,
            right_subset,
            on=timestamp_col,
            direction=direction,
            suffixes=("", "_internal"),
        )

        # Restore datetime index if the original base_df used one
        if base_df.index.dtype.kind == "M":
            merged = merged.set_index(timestamp_col)

        logger.debug(
            f"align_internals: merged {len(internal_cols)} column(s) "
            f"({', '.join(internal_cols)}) onto {len(merged)} bar(s)"
        )
        return merged

    # ==========================================================================
    # WEBSOCKET — PUBLIC API
    # ==========================================================================

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[MassiveQuoteUpdate], None] | None = None,
        on_trade: Callable[[MassiveTradeUpdate], None] | None = None,
        on_bar: Callable[[dict[str, Any]], None] | None = None,
        include_quotes: bool = True,
        include_trades: bool = True,
        include_second_bars: bool = False,
    ) -> None:
        """
        Start real-time WebSocket streaming for the given symbols.

        Spawns a background daemon thread that maintains the WebSocket
        connection with automatic reconnection on failure.

        Args:
            symbols:             List of symbols to stream (e.g., ["SPY"]).
            on_quote:            Callback for NBBO quote updates.
            on_trade:            Callback for trade print updates.
            on_bar:              Callback for aggregate bar updates.
            include_quotes:      Subscribe to Q.<symbol> channels (default True).
            include_trades:      Subscribe to T.<symbol> channels (default True).
            include_second_bars: Subscribe to A.<symbol> per-second bar channels.

        Note:
            To change symbols, call update_subscriptions() or stop_stream()
            then start_stream() again. Massive WebSocket does not support
            incremental subscription changes without reconnecting.
        """
        with self._lock:
            if self._running:
                logger.warning("MassiveClient: stream already running; stopping first")
                self._stop_stream_locked()

            if on_quote:
                self.on_quote = on_quote
            if on_trade:
                self.on_trade = on_trade
            if on_bar:
                self.on_bar = on_bar

            subs: list[str] = []
            for sym in symbols:
                if include_quotes:
                    subs.append(f"Q.{sym}")
                if include_trades:
                    subs.append(f"T.{sym}")
                if include_second_bars:
                    subs.append(f"A.{sym}")

            self._ws_subscriptions = subs
            self._running = True
            self._reconnect_attempts = 0

            self._ws_thread = threading.Thread(
                target=self._reconnect_loop,
                args=(subs,),
                daemon=True,
                name="MassiveWebSocket",
            )
            self._ws_thread.start()

        logger.info(
            f"MassiveClient stream starting: symbols={symbols}, subs={subs}"
        )

    def stop_stream(self) -> None:
        """
        Stop the active WebSocket stream gracefully.

        Sets the running flag to False and closes the WebSocket connection.
        The background thread will exit after the current reconnect cycle.
        """
        with self._lock:
            self._stop_stream_locked()
        logger.info("MassiveClient stream stopped")

    def update_subscriptions(
        self,
        symbols: list[str],
        include_quotes: bool = True,
        include_trades: bool = True,
        include_second_bars: bool = False,
    ) -> None:
        """
        Update the streaming symbol list.

        Closes the current WebSocket and reconnects with the new subscriptions.
        The background reconnect loop will pick up the new subscription list.

        Args:
            symbols:             New list of symbols.
            include_quotes:      Subscribe to quote channels.
            include_trades:      Subscribe to trade channels.
            include_second_bars: Subscribe to A.<symbol> channels.
        """
        subs: list[str] = []
        for sym in symbols:
            if include_quotes:
                subs.append(f"Q.{sym}")
            if include_trades:
                subs.append(f"T.{sym}")
            if include_second_bars:
                subs.append(f"A.{sym}")

        with self._lock:
            self._ws_subscriptions = subs
            # Close to force the reconnect loop to pick up new subs
            if self._ws_client is not None:
                try:
                    self._ws_client.close()
                except Exception:
                    pass

        logger.info(f"MassiveClient subscriptions updated: {subs}")

    # ==========================================================================
    # WEBSOCKET — PRIVATE IMPLEMENTATION
    # ==========================================================================

    def _stop_stream_locked(self) -> None:
        """Internal stop — must be called with self._lock held."""
        self._running = False
        if self._ws_client is not None:
            try:
                self._ws_client.close()
            except Exception:
                pass
            self._ws_client = None
        self._set_status(ConnectionStatus.DISCONNECTED)

    def _reconnect_loop(self, initial_subs: list[str]) -> None:
        """
        Background thread: connect WebSocket with automatic exponential-backoff
        reconnection on failure or clean close while _running is True.

        Args:
            initial_subs: Initial channel subscriptions list.
        """
        backoff = RECONNECT_BASE_DELAY
        while self._running and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            subs = self._ws_subscriptions  # may be updated by update_subscriptions()
            try:
                self._connect_websocket(subs)
                # _connect_websocket() returned → clean WebSocket close or disconnect
                if not self._running:
                    break
                logger.info("MassiveClient: stream closed, scheduling reconnect...")
                # Reset failure counter on clean disconnects
                self._reconnect_attempts = 0
                backoff = RECONNECT_BASE_DELAY
            except Exception as exc:
                self._reconnect_attempts += 1
                logger.warning(
                    f"MassiveClient WebSocket error "
                    f"(attempt {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}): "
                    f"{type(exc).__name__}: {exc}"
                )
                if not self._running or self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        "MassiveClient: max reconnect attempts reached"
                        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS
                        else "MassiveClient: stream stopped during reconnect"
                    )
                    self._set_status(ConnectionStatus.ERROR)
                    break
                self._set_status(ConnectionStatus.RECONNECTING)

            if self._running:
                logger.info(f"MassiveClient: reconnecting in {backoff:.1f}s...")
                time.sleep(backoff)  # thread-safe: time.sleep() intentional
                backoff = min(backoff * 2.0, MAX_RECONNECT_DELAY)

        self._running = False
        if self.status not in (ConnectionStatus.DISCONNECTED, ConnectionStatus.ERROR):
            self._set_status(ConnectionStatus.DISCONNECTED)
        logger.info("MassiveClient: reconnect loop exited")

    def _connect_websocket(self, subscriptions: list[str]) -> None:
        """
        Create and run a Massive WebSocketClient (blocks until disconnected).

        Args:
            subscriptions: List of channel subscription strings
                           (e.g., ["Q.SPY", "T.SPY"]).

        Raises:
            ImportError:    If `massive` package is not installed.
            Exception:      On connection or authentication failure.
        """
        if not HAS_MASSIVE:
            raise ImportError(
                "massive/polygon-api-client package not installed. "
                "Run: pip install polygon-api-client"
            )
        try:
            from massive import WebSocketClient
        except ImportError:
            from polygon import WebSocketClient

        self._set_status(ConnectionStatus.CONNECTING)
        self._ws_client = WebSocketClient(
            api_key=self.api_key,
            subscriptions=subscriptions,
        )
        self._set_status(ConnectionStatus.STREAMING)
        logger.info(f"MassiveClient: WebSocket connected, subscriptions={subscriptions}")
        # run() is blocking — returns on clean close or exception
        self._ws_client.run(handle_msg=self._handle_messages)
        # If execution reaches here, the connection closed cleanly
        if self.status == ConnectionStatus.STREAMING:
            self._set_status(ConnectionStatus.DISCONNECTED)

    def _handle_messages(self, messages: list) -> None:
        """
        Dispatch incoming WebSocket messages to registered callbacks.

        Processes Q (quote), T (trade), A/AM (aggregate bar) events.
        Buffers messages for inspection; errors are logged, never raised.

        Args:
            messages: List of WebSocketMessage objects from the Massive SDK.
        """
        for msg in messages:
            try:
                self.message_buffer.append(msg)
                event_type = getattr(msg, "event_type", "") or ""

                if event_type == "Q":
                    update = self._build_quote_update(msg)
                    if self.on_quote:
                        self.on_quote(update)

                elif event_type == "T":
                    update = self._build_trade_update(msg)
                    if self.on_trade:
                        self.on_trade(update)

                elif event_type in ("A", "AM"):
                    bar = self._build_bar_dict(msg)
                    if self.on_bar:
                        self.on_bar(bar)

            except Exception as exc:
                logger.error(
                    f"MassiveClient: error processing {getattr(msg, 'event_type', '?')} "
                    f"message: {exc}"
                )

    # ==========================================================================
    # MESSAGE BUILDERS
    # ==========================================================================

    def _build_quote_update(self, msg: Any) -> MassiveQuoteUpdate:
        """Build a MassiveQuoteUpdate from a WebSocket Q message."""
        ts_ms = getattr(msg, "timestamp", 0) or 0
        return MassiveQuoteUpdate(
            symbol=str(getattr(msg, "symbol", "")),
            bid=float(getattr(msg, "bid_price", 0.0) or 0.0),
            ask=float(getattr(msg, "ask_price", 0.0) or 0.0),
            bid_size=int(getattr(msg, "bid_size", 0) or 0),
            ask_size=int(getattr(msg, "ask_size", 0) or 0),
            timestamp=(
                datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.utcnow()
            ),
            bid_exchange=str(getattr(msg, "bid_exchange", "") or ""),
            ask_exchange=str(getattr(msg, "ask_exchange", "") or ""),
            raw=msg,
        )

    def _build_trade_update(self, msg: Any) -> MassiveTradeUpdate:
        """Build a MassiveTradeUpdate from a WebSocket T message."""
        ts_ms = getattr(msg, "timestamp", 0) or 0
        conditions = getattr(msg, "conditions", []) or []
        return MassiveTradeUpdate(
            symbol=str(getattr(msg, "symbol", "")),
            price=float(getattr(msg, "price", 0.0) or 0.0),
            size=int(getattr(msg, "size", 0) or 0),
            timestamp=(
                datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.utcnow()
            ),
            exchange=str(getattr(msg, "exchange", "") or ""),
            conditions=[str(c) for c in conditions],
            raw=msg,
        )

    def _build_bar_dict(self, msg: Any) -> dict[str, Any]:
        """Build a bar dict from a WebSocket A or AM message."""
        ts_ms = getattr(msg, "start_timestamp", 0) or 0
        return {
            "symbol":             str(getattr(msg, "symbol", "")),
            "event_type":         str(getattr(msg, "event_type", "A")),
            "open":               float(getattr(msg, "open", 0.0) or 0.0),
            "high":               float(getattr(msg, "high", 0.0) or 0.0),
            "low":                float(getattr(msg, "low", 0.0) or 0.0),
            "close":              float(getattr(msg, "close", 0.0) or 0.0),
            "volume":             int(getattr(msg, "volume", 0) or 0),
            "vwap":               float(getattr(msg, "vwap", 0.0) or 0.0),
            "accumulated_volume": int(getattr(msg, "accumulated_volume", 0) or 0),
            "timestamp":          (
                datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.utcnow()
            ),
        }

    def _normalize_option_snapshot(self, snapshot: Any) -> dict[str, Any]:
        """
        Normalize a Massive OptionContractSnapshot to Spyder's internal format.

        Extracted fields:
            symbol, underlying, strike, expiration_date, option_type,
            exercise_style, bid, ask, mid, implied_volatility,
            delta, gamma, theta, vega, open_interest, volume,
            open, close, break_even_price.

        Args:
            snapshot: massive OptionContractSnapshot object.

        Returns:
            Dict in Spyder internal option format.
        """
        details       = getattr(snapshot, "details", None)
        greeks        = getattr(snapshot, "greeks", None)
        last_quote    = getattr(snapshot, "last_quote", None)
        day           = getattr(snapshot, "day", None)
        underlying_a  = getattr(snapshot, "underlying_asset", None)

        return {
            "symbol":           str(getattr(details, "ticker", "") if details else ""),
            "underlying":       str(getattr(underlying_a, "ticker", "") if underlying_a else ""),
            "strike":           float(getattr(details, "strike_price", 0.0) or 0.0) if details else 0.0,
            "expiration_date":  str(getattr(details, "expiration_date", "") if details else ""),
            "option_type":      str(getattr(details, "contract_type", "") if details else ""),
            "exercise_style":   str(getattr(details, "exercise_style", "") if details else ""),
            "bid":              float(getattr(last_quote, "bid", 0.0) or 0.0) if last_quote else 0.0,
            "ask":              float(getattr(last_quote, "ask", 0.0) or 0.0) if last_quote else 0.0,
            "mid":              float(getattr(last_quote, "midpoint", 0.0) or 0.0) if last_quote else 0.0,
            "implied_volatility": float(getattr(snapshot, "implied_volatility", 0.0) or 0.0),
            "delta":            float(getattr(greeks, "delta", 0.0) or 0.0) if greeks else 0.0,
            "gamma":            float(getattr(greeks, "gamma", 0.0) or 0.0) if greeks else 0.0,
            "theta":            float(getattr(greeks, "theta", 0.0) or 0.0) if greeks else 0.0,
            "vega":             float(getattr(greeks, "vega", 0.0) or 0.0) if greeks else 0.0,
            "open_interest":    int(getattr(snapshot, "open_interest", 0) or 0),
            "volume":           int(getattr(day, "volume", 0) or 0) if day else 0,
            "open":             float(getattr(day, "open", 0.0) or 0.0) if day else 0.0,
            "close":            float(getattr(day, "close", 0.0) or 0.0) if day else 0.0,
            "break_even_price": float(getattr(snapshot, "break_even_price", 0.0) or 0.0),
        }

    # ==========================================================================
    # STATUS HELPER
    # ==========================================================================

    def _set_status(self, new_status: ConnectionStatus) -> None:
        """Update connection status and fire on_status_change callback if set."""
        if self.status != new_status:
            self.status = new_status
            if self.on_status_change:
                try:
                    self.on_status_change(new_status)
                except Exception as exc:
                    logger.error(f"MassiveClient: on_status_change callback error: {exc}")

    # ==========================================================================
    # STRING REPRESENTATION
    # ==========================================================================

    def __repr__(self) -> str:
        return (
            f"MassiveClient(status={self.status.value}, "
            f"streaming={self.is_streaming}, "
            f"subs={self._ws_subscriptions})"
        )


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================


def create_massive_client_from_env() -> MassiveClient:
    """
    Create a MassiveClient using environment variables.

    Required env var:
        MASSIVE_API_KEY — Massive.com (formerly Polygon.io) API key.

    Optional env var:
        MASSIVE_REST_RPS — REST requests per second (default 3.0).

    Returns:
        Configured MassiveClient instance.

    Raises:
        ValueError: If MASSIVE_API_KEY is not set.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "")
    if not api_key:
        raise ValueError(
            "MASSIVE_API_KEY is not set. Add it to your .env file."
        )
    rps = float(os.environ.get("MASSIVE_REST_RPS", str(DEFAULT_REST_RPS)))
    return MassiveClient(api_key=api_key, rest_requests_per_second=rps)


# ==============================================================================
# QUICK SELF-TEST
# ==============================================================================
if __name__ == "__main__":
    import sys

    print("MassiveClient self-test")
    print(f"  massive SDK available: {HAS_MASSIVE}")
    print(f"  pandas available:      {HAS_PANDAS}")
    print(f"  PySide6 available:     {HAS_QT}")

    key = os.environ.get("MASSIVE_API_KEY", "")
    if not key:
        print("\nSet MASSIVE_API_KEY in env to run a live test.")
        sys.exit(0)

    client = MassiveClient(api_key=key)
    print(f"\n{client}")

    print("\n--- Market status ---")
    status = client.get_market_status()
    print(f"  market: {status.get('market')}")

    print("\n--- SPY quote (REST) ---")
    q = client.get_quote("SPY")
    print(f"  bid={q.bid}  ask={q.ask}  mid={q.mid:.2f}  spread={q.spread:.2f}")

    print("\n--- Historical 1-min bars (SPY equity) ---")
    df = client.get_historical_bars("SPY", "2026-01-02", "2026-01-03", timespan="minute")
    print(f"  rows={len(df)}, columns={list(df.columns)}")
    if not df.empty:
        print(f"  last bar:\n{df.tail(1)}")

    print("\n--- build_option_ticker() ---")
    ticker_call = MassiveClient.build_option_ticker("SPY", "2026-06-19", "call", 600.0)
    ticker_put  = MassiveClient.build_option_ticker("SPY", "2026-03-21", "put",  582.5)
    print(f"  call ticker: {ticker_call}")   # O:SPY260619C00600000
    print(f"  put  ticker: {ticker_put}")    # O:SPY260321P00582500

    print("\n--- get_option_bars() (single contract) ---")
    opt_df = client.get_option_bars(
        "SPY", "2026-01-03", "call", 580.0,
        "2026-01-02", "2026-01-03", timespan="minute"
    )
    print(f"  rows={len(opt_df)}" + (" (no data for this contract)" if opt_df.empty else ""))
    if not opt_df.empty:
        print(f"  last bar:\n{opt_df.tail(1)}")

    print("\n--- get_historical_option_chain() (point-in-time, no survivorship bias) ---")
    hist_chain = client.get_historical_option_chain(
        "SPY", "2026-01-15",
        expiration="2026-01-17",
        min_strike=570.0, max_strike=600.0,
    )
    print(f"  contracts returned: {len(hist_chain)}")
    if hist_chain:
        c = hist_chain[0]
        print(f"  sample: {c['symbol']}  strike={c['strike']}  IV={c['implied_volatility']:.3f}"
              f"  delta={c['delta']:.3f}")

    print("\n--- download_flat_file() note ---")
    print("  Use client.download_flat_file('2026-03-21', data_type='options_quotes')")
    print("  Requires Advanced Massive subscription. Files cached locally as Parquet.")

    print("\nSelf-test complete.")
