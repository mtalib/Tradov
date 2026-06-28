#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovC_MarketData
Module: TradovC00_MarketDataProtocol.py
Purpose: Provider-agnostic Protocols for market data access (REST + streaming)

Defines:
    OptionsDataProvider     — structural Protocol for REST options queries
    MarketDataStreamProvider — Protocol for real-time symbol streaming
    NormalizedQuote         — canonical quote representation
    NormalizedTrade         — canonical trade/print representation
    TradierMarketDataAdapter — adapter implementing both Protocols via B40
    MassiveMarketDataAdapter — adapter implementing both Protocols via C27

Any object that implements the methods in OptionsDataProvider / MarketDataStreamProvider
satisfies the respective Protocol without inheritance (structural subtyping).
TradierClient (TradovB40) already satisfies OptionsDataProvider directly.
TradierMarketDataAdapter wraps TradierClient + TradierMarketStream so callers
only deal with the Protocol surface.

Author: Tradov Dev
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07
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
        symbol: Ticker symbol (e.g., "TRAD").
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
    needing to inherit from it.  TradierClient (TradovB40) already satisfies it.

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

    Satisfied by TradierMarketDataAdapter and MassiveMarketDataAdapter.

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
    using :class:`~Tradov.TradovB_Broker.TradovB40_TradierClient.TradierClient`
    for REST queries and
    :class:`~Tradov.TradovB_Broker.TradovB40_TradierClient.TradierMarketStream`
    for WebSocket streaming.

    This is the recommended way for BrokerC/D/E/F modules to access market data
    when ``MARKET_DATA_PROVIDER=tradier``.

    Example::

        adapter = TradierMarketDataAdapter()
        quotes = adapter.get_quotes(["TRAD", "QQQ"])
        adapter.start_stream(
            ["TRAD"],
            on_quote=lambda q: print(q.symbol, q.mid),
        )
        # … later …
        adapter.stop_stream()
    """

    def __init__(self) -> None:
        from Tradov.TradovB_Broker.TradovB40_TradierClient import (
            TradierClient,
            TradierMarketStream,
            TradingEnvironment,
            create_tradier_client_from_env,
        )
        self._TradierMarketStream = TradierMarketStream

        allow_sandbox = str(
            os.environ.get("TRADOV_ALLOW_SANDBOX_MARKET_DATA", "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        market_data_env = (
            os.environ.get("TRADIER_MARKET_DATA_ENVIRONMENT")
            or os.environ.get("TRADIER_ENVIRONMENT")
            or "live"
        ).strip().lower()
        is_live_env = market_data_env in {"live", "production"}
        if not is_live_env and not allow_sandbox:
            logger.warning(
                "TradierMarketDataAdapter forcing LIVE market-data endpoint "
                "(TRADIER_MARKET_DATA_ENVIRONMENT=%s ignored).",
                market_data_env or "<empty>",
            )
            is_live_env = True

        env_enum = TradingEnvironment.LIVE if is_live_env else TradingEnvironment.SANDBOX
        self._client: TradierClient = create_tradier_client_from_env(environment=env_enum)
        self._stream: Any = None

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
# FACTORY FUNCTIONS
# ==============================================================================


# FACTORY FUNCTIONS
# ==============================================================================


def create_options_data_provider() -> Any:
    """
    Factory that returns a :class:`TradierMarketDataAdapter`.

    Tradier is the sole supported data provider.

    Returns:
        :class:`TradierMarketDataAdapter` instance.

    Raises:
        RuntimeError: If the adapter cannot be instantiated.

    Example::

        provider = create_options_data_provider()
        chain = provider.get_option_chain_with_greeks("TRAD", "2026-04-18")
    """
    try:
        return TradierMarketDataAdapter()
    except Exception as exc:
        raise RuntimeError(
            f"Could not create TradierMarketDataAdapter as OptionsDataProvider: {exc}"
        ) from exc


def create_stream_provider(symbols: list[str] | None = None) -> Any:
    """
    Factory that returns a :class:`TradierMarketDataAdapter` as a stream provider.

    Args:
        symbols: Optional initial symbol list; call :meth:`start_stream` to begin.

    Returns:
        :class:`TradierMarketDataAdapter` instance.

    Example::

        provider = create_stream_provider()
        provider.start_stream(["TRAD"], on_quote=lambda q: print(q.mid))
    """
    _ = symbols  # reserved for future lazy-start
    return TradierMarketDataAdapter()


def switch_market_data_provider(provider: str) -> None:
    """
    No-op compatibility shim — Tradier is the only supported provider.

    Args:
        provider: Must be ``"tradier"``.

    Raises:
        ValueError: If *provider* is not ``"tradier"``.
    """
    if provider.lower().strip() != "tradier":
        raise ValueError(
            f"Unknown provider '{provider}'; only 'tradier' is supported."
        )
    logger.info("Market data provider confirmed as 'tradier'.")


# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = [
    "NormalizedQuote",
    "NormalizedTrade",
    "OptionsDataProvider",
    "MarketDataStreamProvider",
    "TradierMarketDataAdapter",
    "create_options_data_provider",
    "create_stream_provider",
    "switch_market_data_provider",
]
