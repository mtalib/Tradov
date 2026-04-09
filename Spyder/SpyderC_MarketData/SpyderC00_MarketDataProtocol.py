#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC00_MarketDataProtocol.py
Purpose: Provider-agnostic Protocols for market data access (REST + streaming)

Defines:
    OptionsDataProvider     — structural Protocol for REST options queries
    MarketDataStreamProvider — Protocol for real-time symbol streaming
    NormalizedQuote         — canonical quote representation
    NormalizedTrade         — canonical trade/print representation
    TradierMarketDataAdapter — adapter implementing both Protocols via B40
    DatabentoMarketDataAdapter — adapter implementing both Protocols via C26

Any object that implements the methods in OptionsDataProvider / MarketDataStreamProvider
satisfies the respective Protocol without inheritance (structural subtyping).
TradierClient (SpyderB40) already satisfies OptionsDataProvider directly.
TradierMarketDataAdapter wraps TradierClient + TradierMarketStream so callers
only deal with the Protocol surface.

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-03-16 Time: 20:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import logging
from dataclasses import dataclass, field
from typing import Any
from collections.abc import Callable

try:
    from typing import Protocol, runtime_checkable
except ImportError:                                     # Python < 3.8 fallback
    from typing import Protocol, runtime_checkable  # type: ignore[assignment]

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# CANONICAL DATA TYPES
# ==============================================================================


@dataclass
class NormalizedQuote:
    """
    Provider-agnostic quote snapshot.

    Downstream code (F-Series, D-Series, E-Series) should consume this
    dataclass instead of provider-specific dicts.

    Attributes:
        symbol: Ticker symbol (e.g., "SPY").
        bid:    Best bid price.
        ask:    Best ask price.
        last:   Last trade price.
        volume: Cumulative volume.
        timestamp: ISO-8601 or Unix epoch string from the provider.
        raw:    Original provider payload for fields not yet normalised.
    """

    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    timestamp: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def mid(self) -> float:
        """Mid-market price."""
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        """Absolute bid-ask spread."""
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        """Spread as a percentage of the mid price (0 when mid == 0)."""
        m = self.mid
        return (self.spread / m * 100.0) if m else 0.0


@dataclass
class NormalizedTrade:
    """
    Provider-agnostic trade / time-and-sales print.

    Attributes:
        symbol:    Ticker symbol.
        price:     Execution price.
        size:      Number of shares / contracts.
        timestamp: ISO-8601 or Unix epoch string from the provider.
        exchange:  Reporting exchange code (e.g., "Q", "N").
        raw:       Original provider payload.
    """

    symbol: str = ""
    price: float = 0.0
    size: int = 0
    timestamp: str = ""
    exchange: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# PROTOCOL DEFINITIONS
# ==============================================================================


@runtime_checkable
class OptionsDataProvider(Protocol):
    """
    Structural typing Protocol for REST-style options query providers.

    Any object implementing all three methods satisfies this Protocol without
    needing to inherit from it.  TradierClient (SpyderB40) already satisfies it.

    Methods:
        get_quotes: Retrieve current market quotes for one or more symbols.
        get_option_chain_with_greeks: Retrieve full options chain with Greeks.
        get_option_expirations: Retrieve available expiration dates for a symbol.
    """

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """Return current quote data for one or more symbols."""
        ...

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list:
        """Return options chain (calls and/or puts) with Greeks for a given expiry."""
        ...

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        """Return available option expiration dates for a symbol."""
        ...


@runtime_checkable
class MarketDataStreamProvider(Protocol):
    """
    Structural typing Protocol for real-time market data streaming.

    Satisfied by TradierMarketDataAdapter (and any future streaming adapter).

    Methods:
        start_stream:    Start streaming for the given symbol list.
        stop_stream:     Stop the active stream gracefully.
        update_symbols:  Replace the symbol subscription without reconnecting.
        is_streaming:    Return True when the stream is actively running.
    """

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """Start streaming for the given symbols and attach optional callbacks."""
        ...

    def stop_stream(self) -> None:
        """Stop the active stream."""
        ...

    def update_symbols(self, symbols: list[str]) -> None:
        """Replace the symbol subscription on the live connection."""
        ...

    @property
    def is_streaming(self) -> bool:
        """Return True when the stream is actively running."""
        ...


# ==============================================================================
# ADAPTER
# ==============================================================================


class TradierMarketDataAdapter:
    """
    Adapter implementing both OptionsDataProvider and MarketDataStreamProvider
    using :class:`~Spyder.SpyderB_Broker.SpyderB40_TradierClient.TradierClient`
    for REST queries and
    :class:`~Spyder.SpyderB_Broker.SpyderB40_TradierClient.TradierMarketStream`
    for WebSocket streaming.

    This is the recommended way for BrokerC/D/E/F modules to access market data
    when ``MARKET_DATA_PROVIDER=tradier``.

    Example::

        adapter = TradierMarketDataAdapter()
        quotes = adapter.get_quotes(["SPY", "QQQ"])
        adapter.start_stream(
            ["SPY"],
            on_quote=lambda q: print(q.symbol, q.mid),
        )
        # … later …
        adapter.stop_stream()
    """

    def __init__(self) -> None:
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
            TradierClient,
            TradierMarketStream,
            create_tradier_client_from_env,
        )
        self._TradierMarketStream = TradierMarketStream
        self._client: TradierClient = create_tradier_client_from_env()
        self._stream: Any = None  # TradierMarketStream instance

    # ---- OptionsDataProvider ------------------------------------------------

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """Delegate to TradierClient.get_quotes()."""
        return self._client.get_quotes(symbols)

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list:
        """Delegate to TradierClient.get_option_chain_with_greeks()."""
        return self._client.get_option_chain_with_greeks(symbol, expiration, option_type)

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        """Delegate to TradierClient.get_option_expirations()."""
        return self._client.get_option_expirations(symbol)

    # ---- MarketDataStreamProvider -------------------------------------------

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """
        Start a WebSocket market data stream.

        Normalises raw Tradier quote/trade dicts into :class:`NormalizedQuote`
        and :class:`NormalizedTrade` before calling the supplied callbacks.

        Args:
            symbols:  List of symbols to subscribe to.
            on_quote: Callback for normalised quote events.
            on_trade: Callback for normalised trade events.
        """
        if self._stream is not None and self._stream.is_running:
            logger.warning("TradierMarketDataAdapter: stream already running; stopping first")
            self.stop_stream()

        self._stream = self._TradierMarketStream(self._client, symbols)

        if on_quote:
            def _quote_cb(raw: dict[str, Any]) -> None:
                nq = NormalizedQuote(
                    symbol=raw.get("symbol", ""),
                    bid=float(raw.get("bid", 0.0) or 0.0),
                    ask=float(raw.get("ask", 0.0) or 0.0),
                    last=float(raw.get("last", 0.0) or 0.0),
                    volume=int(raw.get("volume", 0) or 0),
                    timestamp=str(raw.get("timestamp", "")),
                    raw=raw,
                )
                on_quote(nq)
            self._stream.on_quote = _quote_cb

        if on_trade:
            def _trade_cb(raw: dict[str, Any]) -> None:
                nt = NormalizedTrade(
                    symbol=raw.get("symbol", ""),
                    price=float(raw.get("price", 0.0) or 0.0),
                    size=int(raw.get("size", 0) or 0),
                    timestamp=str(raw.get("timestamp", "")),
                    exchange=str(raw.get("exch", "")),
                    raw=raw,
                )
                on_trade(nt)
            self._stream.on_trade = _trade_cb

        self._stream.start()
        logger.info("TradierMarketDataAdapter stream started for %s", symbols)

    def stop_stream(self) -> None:
        """Stop the active WebSocket stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream = None

    def update_symbols(self, symbols: list[str]) -> None:
        """Update symbol subscription on the live stream without reconnecting."""
        if self._stream is not None:
            self._stream.update_symbols(symbols)

    @property
    def is_streaming(self) -> bool:
        """Return True when the WebSocket stream is actively running."""
        return self._stream is not None and self._stream.is_running


# ==============================================================================
# DATABENTO ADAPTER
# ==============================================================================


class DatabentoMarketDataAdapter:
    """
    Adapter implementing both OptionsDataProvider and MarketDataStreamProvider
    using :class:`~Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient.DatabentoClient`
    for REST snapshots and live streaming.

    This is the recommended way for D/E/F-Series modules to access market data
    when ``MARKET_DATA_PROVIDER=databento``.

    Note:
        Option Greeks are not provided by Databento natively. In Phase 1,
        ``get_option_chain_with_greeks`` returns raw chain structure (strikes,
        bid/ask) without delta/gamma/theta/vega. Full Greeks computation via
        SpyderV05_PricingEngine is planned for Phase 2.

    Example::

        adapter = DatabentoMarketDataAdapter()
        quotes = adapter.get_quotes(["SPY"])
        adapter.start_stream(
            ["SPY"],
            on_quote=lambda q: print(q.symbol, q.mid),
        )
        # … later …
        adapter.stop_stream()
    """

    def __init__(self) -> None:
        # SpyderC26_DatabentoClient was removed in v2; use SpyderC27_MassiveClient instead.
        try:
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import (
                create_massive_client_from_env,
            )
            self._client = create_massive_client_from_env()
        except ImportError as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "DatabentoMarketDataAdapter: market data client unavailable (%s). "
                "Ensure SpyderC27_MassiveClient is installed.",
                exc,
            )
            self._client = None
        self._user_on_quote: Callable[[NormalizedQuote], None] | None = None
        self._user_on_trade: Callable[[NormalizedTrade], None] | None = None

    # ---- OptionsDataProvider ------------------------------------------------

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """
        Get current quotes via Databento live buffer or historical fallback.

        Args:
            symbols: List of symbols to quote (e.g., ``["SPY", "QQQ"]``).

        Returns:
            Dict matching Tradier's quote response structure for compatibility:
            ``{"quotes": {"quote": {...}}}`` for a single symbol, or
            ``{"quotes": {"quote": [...]}}`` for multiple symbols.
        """
        raw = self._client.get_latest_quotes(symbols)
        quotes = []
        for sym, data in raw.items():
            quotes.append({
                "symbol": sym,
                "bid": data.get("bid", 0.0),
                "ask": data.get("ask", 0.0),
                "last": data.get("last", 0.0),
                "volume": data.get("volume", 0),
            })
        if len(quotes) == 1:
            return {"quotes": {"quote": quotes[0]}}
        return {"quotes": {"quote": quotes}}

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list:
        """
        Get option chain structure from Databento instrument definitions.

        Note:
            Greeks are not provided by Databento in Phase 1. This returns raw
            chain structure (strikes, contract codes, bid/ask) without
            delta/gamma/theta/vega. Full Greeks via SpyderV05_PricingEngine
            are planned for Phase 2.

        Args:
            symbol:      Underlying symbol (e.g., ``"SPY"``).
            expiration:  Expiration date ISO string (e.g., ``"2026-04-18"``).
            option_type: ``"call"``, ``"put"``, or ``None`` for both.

        Returns:
            List of dicts with option chain data, or empty list on error.
        """
        defs_df = self._client.get_instrument_definitions(symbol, expiration)
        if defs_df is None or (hasattr(defs_df, "empty") and defs_df.empty):
            logger.warning("DatabentoAdapter: no definitions for %s %s", symbol, expiration)
            return []
        rows = list(defs_df.to_dict("records")) if hasattr(defs_df, "to_dict") else []
        if option_type:
            side = option_type[0].upper()  # "C" or "P"
            rows = [r for r in rows if str(r.get("instrument_class", "")).startswith(side)]
        return rows

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        """
        Get available option expiration dates from Databento instrument definitions.

        Args:
            symbol: Underlying symbol (e.g., ``"SPY"``).

        Returns:
            Dict matching Tradier's expirations format:
            ``{"expirations": {"date": ["2026-04-18", ...]}}``,
            or ``{"expirations": {"date": []}}`` on error.
        """
        from datetime import date as _date
        today_str = _date.today().isoformat()
        try:
            defs_df = self._client.get_instrument_definitions(symbol, today_str)
            if defs_df is None or (hasattr(defs_df, "empty") and defs_df.empty):
                return {"expirations": {"date": []}}
            dates: list[str] = []
            if hasattr(defs_df, "columns") and "expiration" in defs_df.columns:
                dates = sorted(str(d) for d in defs_df["expiration"].dropna().unique())
            return {"expirations": {"date": dates}}
        except Exception as exc:
            logger.error("DatabentoAdapter: error fetching expirations for %s: %s", symbol, exc)
            return {"expirations": {"date": []}}

    # ---- MarketDataStreamProvider -------------------------------------------

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """
        Start Databento live stream with normalized output.

        Subscribes by underlying parent — Databento automatically streams
        all option contracts for the given underlying(s).

        Args:
            symbols:  List of underlying symbols (e.g., ``["SPY"]``).
            on_quote: Callback for normalised quote events.
            on_trade: Callback for normalised trade events.
        """
        self._user_on_quote = on_quote
        self._user_on_trade = on_trade
        if on_quote:
            self._client.on_quote = self._handle_databento_quote
        if on_trade:
            self._client.on_trade = self._handle_databento_trade
        self._client.start_live(underlyings=symbols, schema="mbp-1")
        logger.info("DatabentoMarketDataAdapter stream started for %s", symbols)

    def stop_stream(self) -> None:
        """Stop the active Databento live stream."""
        self._client.stop_live()
        logger.info("DatabentoMarketDataAdapter stream stopped")

    def update_symbols(self, symbols: list[str]) -> None:
        """
        Restart stream with an updated symbol list.

        Note:
            Databento does not support adding symbols to a live session without
            reconnecting, so this stops and restarts the stream.

        Args:
            symbols: New symbol list.
        """
        if self.is_streaming:
            on_quote = self._user_on_quote
            on_trade = self._user_on_trade
            self.stop_stream()
            self.start_stream(symbols, on_quote=on_quote, on_trade=on_trade)

    @property
    def is_streaming(self) -> bool:
        """Return True when the Databento live stream is active."""
        return self._client.is_connected

    def _handle_databento_quote(self, update: Any) -> None:
        """Convert MarketDataUpdate → NormalizedQuote and forward to caller."""
        if self._user_on_quote is None:
            return
        try:
            nq = NormalizedQuote(
                symbol=update.symbol,
                bid=float(update.data.get("bid", 0.0) or 0.0),
                ask=float(update.data.get("ask", 0.0) or 0.0),
                last=float(
                    update.data.get("price", update.data.get("close", 0.0)) or 0.0
                ),
                volume=int(update.data.get("volume", 0) or 0),
                timestamp=str(getattr(update, "datetime", "")),
                raw=dict(update.data),
            )
            self._user_on_quote(nq)
        except Exception as exc:
            logger.error("DatabentoAdapter: error normalizing quote: %s", exc)

    def _handle_databento_trade(self, update: Any) -> None:
        """Convert MarketDataUpdate → NormalizedTrade and forward to caller."""
        if self._user_on_trade is None:
            return
        try:
            nt = NormalizedTrade(
                symbol=update.symbol,
                price=float(update.data.get("price", 0.0) or 0.0),
                size=int(update.data.get("size", 0) or 0),
                timestamp=str(getattr(update, "datetime", "")),
                raw=dict(update.data),
            )
            self._user_on_trade(nt)
        except Exception as exc:
            logger.error("DatabentoAdapter: error normalizing trade: %s", exc)


# ==============================================================================
# MASSIVE MARKET DATA ADAPTER
# ==============================================================================
class MassiveMarketDataAdapter:
    """
    Implements both ``OptionsDataProvider`` and ``MarketDataStreamProvider``
    using ``SpyderC27_MassiveClient`` (Massive).

    Advantages over Tradier for options scanning:
        - Pre-calculated Greeks (delta/gamma/theta/vega) on every contract —
          no local BSM engine needed for chain screening.
        - Full 8,000+ contract SPY options chain in a single REST call.
        - Real-time WebSocket equity price feed (Q.SPY / T.SPY).

    Typical usage::

        adapter = MassiveMarketDataAdapter()
        chain = adapter.get_option_chain_with_greeks("SPY", "2026-03-21")
        adapter.start_stream(["SPY"], on_quote=lambda q: print(q.mid))
        expirations = adapter.get_option_expirations("SPY")
        adapter.stop_stream()
    """

    def __init__(self) -> None:
        try:
            from Spyder.SpyderC_MarketData.SpyderC27_MassiveClient import (
                MassiveQuoteUpdate,
                MassiveTradeUpdate,
                create_massive_client_from_env as _create,
            )
            self._client: Any = _create()
            self._MassiveQuoteUpdate = MassiveQuoteUpdate
            self._MassiveTradeUpdate = MassiveTradeUpdate
        except ImportError as exc:
            raise ImportError(
                "SpyderC27_MassiveClient not found or massive SDK not installed. "
                "Run: pip install massive"
            ) from exc

        self._user_on_quote: Callable[[NormalizedQuote], None] | None = None
        self._user_on_trade: Callable[[NormalizedTrade], None] | None = None
        logger.info("MassiveMarketDataAdapter initialised")

    # ---- OptionsDataProvider ------------------------------------------------

    def get_quotes(self, symbols: list[str]) -> dict[str, NormalizedQuote]:
        """
        Fetch current NBBO quotes for a list of symbols via Massive REST.

        Args:
            symbols: List of ticker symbols (e.g., ["SPY", "QQQ"]).

        Returns:
            Mapping of symbol → NormalizedQuote.
        """
        return self._client.get_quotes_batch(symbols)

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str | None = None,
        option_type: str | None = None,
        min_strike: float | None = None,
        max_strike: float | None = None,
        limit: int = 500,
    ) -> dict:
        """
        Fetch a live SPY options chain snapshot with pre-calculated Greeks.

        Massive returns delta/gamma/theta/vega and IV for every contract in
        a single REST call — no local pricing engine required.

        Args:
            symbol:     Underlying symbol (e.g., ``"SPY"``).
            expiration: Specific expiry date ISO string, or ``None`` for all.
            option_type: ``"call"``, ``"put"``, or ``None`` for both.
            min_strike: Lower strike filter (inclusive).
            max_strike: Upper strike filter (inclusive).
            limit:      Max contracts to return (default 500).

        Returns:
            Dict with structure::

                {
                    "options": [
                        {
                            "symbol": str,
                            "underlying": str,
                            "strike": float,
                            "expiration_date": str,
                            "option_type": str,   # "call" or "put"
                            "bid": float,
                            "ask": float,
                            "mid": float,
                            "implied_volatility": float,
                            "delta": float,
                            "gamma": float,
                            "theta": float,
                            "vega": float,
                            "open_interest": int,
                            "volume": int,
                            "break_even_price": float,
                        },
                        ...
                    ]
                }
        """
        contracts = self._client.get_option_chain(
            underlying=symbol,
            expiration=expiration,
            option_type=option_type,
            min_strike=min_strike,
            max_strike=max_strike,
            limit=limit,
        )
        return {"options": contracts}

    def get_option_expirations(self, symbol: str) -> dict:
        """
        Get available options expiration dates for an underlying via Massive REST.

        Args:
            symbol: Underlying symbol (e.g., ``"SPY"``).

        Returns:
            Dict matching Tradier expiration format::

                {"expirations": {"date": ["2026-03-21", "2026-03-28", ...]}}
        """
        try:
            dates = self._client.get_option_expirations(symbol)
            return {"expirations": {"date": dates}}
        except Exception as exc:
            logger.error("MassiveAdapter: error fetching expirations for %s: %s", symbol, exc)
            return {"expirations": {"date": []}}

    # ---- MarketDataStreamProvider -------------------------------------------

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """
        Start Massive WebSocket stream with normalized output.

        Subscribes to Q.<symbol> (quotes) and T.<symbol> (trades) channels.

        Args:
            symbols:  Symbols to stream (e.g., ``["SPY"]``).
            on_quote: Callback receiving :class:`NormalizedQuote` objects.
            on_trade: Callback receiving :class:`NormalizedTrade` objects.
        """
        self._user_on_quote = on_quote
        self._user_on_trade = on_trade
        self._client.start_stream(
            symbols=symbols,
            on_quote=self._handle_massive_quote if on_quote else None,
            on_trade=self._handle_massive_trade if on_trade else None,
            include_quotes=on_quote is not None,
            include_trades=on_trade is not None,
        )
        logger.info("MassiveMarketDataAdapter stream started for %s", symbols)

    def stop_stream(self) -> None:
        """Stop the active Massive WebSocket stream."""
        self._client.stop_stream()
        logger.info("MassiveMarketDataAdapter stream stopped")

    def update_symbols(self, symbols: list[str]) -> None:
        """
        Update streaming symbol subscriptions without full reconnect.

        Args:
            symbols: New symbol list.
        """
        self._client.update_subscriptions(symbols)

    @property
    def is_streaming(self) -> bool:
        """Return True when the Massive WebSocket stream is active."""
        return self._client.is_streaming

    # ---- Internal callbacks -------------------------------------------------

    def _handle_massive_quote(self, update: Any) -> None:
        """Convert MassiveQuoteUpdate → NormalizedQuote and forward to caller."""
        if self._user_on_quote is None:
            return
        try:
            nq = NormalizedQuote(
                symbol=update.symbol,
                bid=update.bid,
                ask=update.ask,
                last=update.mid,
                volume=update.bid_size,
                timestamp=update.timestamp.isoformat(),
                raw={
                    "bid_size":    update.bid_size,
                    "ask_size":    update.ask_size,
                    "bid_exchange": update.bid_exchange,
                    "ask_exchange": update.ask_exchange,
                },
            )
            self._user_on_quote(nq)
        except Exception as exc:
            logger.error("MassiveAdapter: error normalizing quote: %s", exc)

    def _handle_massive_trade(self, update: Any) -> None:
        """Convert MassiveTradeUpdate → NormalizedTrade and forward to caller."""
        if self._user_on_trade is None:
            return
        try:
            nt = NormalizedTrade(
                symbol=update.symbol,
                price=update.price,
                size=update.size,
                timestamp=update.timestamp.isoformat(),
                exchange=update.exchange,
                raw={"conditions": update.conditions},
            )
            self._user_on_trade(nt)
        except Exception as exc:
            logger.error("MassiveAdapter: error normalizing trade: %s", exc)


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================


def create_options_data_provider() -> Any:
    """
    Factory that returns an OptionsDataProvider based on MARKET_DATA_PROVIDER.

    Environment Variables:
        MARKET_DATA_PROVIDER: ``"tradier"`` (default) or ``"databento"``

    Returns:
        :class:`TradierMarketDataAdapter` when provider is ``tradier`` (or unset).
        :class:`DatabentoMarketDataAdapter` when provider is ``databento``.

    Raises:
        RuntimeError: If the selected provider cannot be instantiated.

    Example::

        provider = create_options_data_provider()
        chain = provider.get_option_chain_with_greeks("SPY", "2026-04-18")
    """
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()

    if provider_name == "databento":
        try:
            return DatabentoMarketDataAdapter()
        except Exception as exc:
            raise RuntimeError(
                f"Could not create DatabentoMarketDataAdapter: {exc}"
            ) from exc

    if provider_name == "massive":
        try:
            return MassiveMarketDataAdapter()
        except Exception as exc:
            raise RuntimeError(
                f"Could not create MassiveMarketDataAdapter: {exc}"
            ) from exc

    # Default: Tradier
    try:
        return TradierMarketDataAdapter()
    except Exception as exc:
        raise RuntimeError(
            f"Could not create TradierMarketDataAdapter as OptionsDataProvider: {exc}"
        ) from exc


def create_stream_provider(symbols: list[str] | None = None) -> Any:
    """
    Factory that returns a MarketDataStreamProvider based on MARKET_DATA_PROVIDER.

    Reads the same ``MARKET_DATA_PROVIDER`` env var as
    :func:`create_options_data_provider`.

    Args:
        symbols: Optional initial symbol list; call :meth:`start_stream` to begin.

    Returns:
        :class:`TradierMarketDataAdapter` (Tradier) or
        :class:`DatabentoMarketDataAdapter` (Databento).

    Example::

        provider = create_stream_provider()
        provider.start_stream(["SPY"], on_quote=lambda q: print(q.mid))
    """
    _ = symbols  # reserved for future lazy-start
    provider_name = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()

    if provider_name == "databento":
        try:
            return DatabentoMarketDataAdapter()
        except Exception as exc:
            raise RuntimeError(
                f"Could not create DatabentoMarketDataAdapter as stream provider: {exc}"
            ) from exc

    if provider_name == "massive":
        try:
            return MassiveMarketDataAdapter()
        except Exception as exc:
            raise RuntimeError(
                f"Could not create MassiveMarketDataAdapter as stream provider: {exc}"
            ) from exc

    return TradierMarketDataAdapter()


def switch_market_data_provider(provider: str) -> None:
    """
    Switch ``MARKET_DATA_PROVIDER`` at runtime (session-level; not persisted to .env).

    After calling this, the next call to :func:`create_options_data_provider` or
    :func:`create_stream_provider` will return the new provider's adapter.

    Args:
        provider: ``"tradier"`` or ``"databento"``.

    Raises:
        ValueError: If *provider* is not recognised.

    Example::

        switch_market_data_provider("databento")
        stream = create_stream_provider()   # Now returns DatabentoMarketDataAdapter
    """
    provider = provider.lower().strip()
    if provider not in ("tradier", "databento", "massive"):
        raise ValueError(
            f"Unknown provider '{provider}'; supported values are "
            "'tradier', 'databento', and 'massive'."
        )
    os.environ["MARKET_DATA_PROVIDER"] = provider
    logger.info("MARKET_DATA_PROVIDER switched to '%s' (session-level).", provider)


# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = [
    "NormalizedQuote",
    "NormalizedTrade",
    "OptionsDataProvider",
    "MarketDataStreamProvider",
    "TradierMarketDataAdapter",
    "DatabentoMarketDataAdapter",
    "MassiveMarketDataAdapter",
    "create_options_data_provider",
    "create_stream_provider",
    "switch_market_data_provider",
]
