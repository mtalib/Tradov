# SPYDER — Switchable Market Data Layer Specification

**Document:** SPYDER-MKT-SWITCH-001  
**Version:** 1.0  
**Date:** 2026-03-16  
**Author:** Claude (Maestro)  
**Modules affected:** C00, C26, B40 (enhancement), B30 (deprecation)  
**New modules:** None — all changes within existing modules  
**Priority:** High — Prerequisite for live trading  
**Status:** Draft — Pending review  

> This document specifies the switchable market data architecture that allows Spyder to use Tradier market data during testing and Databento during live trading, controlled by a single environment variable. A companion document (B40-ENHANCE-SPEC-001) covers the B40 TradierClient enhancements that are a prerequisite for this work.

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Module spec: SpyderC00_MarketDataProtocol.py (revision)](#2-module-spec-spyderc00_marketdataprotocolpy-revision)
3. [Module spec: SpyderC26_DatabentoClient.py (revision)](#3-module-spec-spyderc26_databentoclientpy-revision)
4. [Module spec: SpyderB40_TradierClient.py (integration point)](#4-module-spec-spyderb40_tradierclientpy-integration-point)
5. [Module spec: SpyderB30_SPYOptionsChainManager.py (deprecation)](#5-module-spec-spyderb30_spyoptionschainmanagerpy-deprecation)
6. [Implementation order](#6-implementation-order)
7. [Configuration reference](#7-configuration-reference)
8. [Coding standards reminder](#8-coding-standards-reminder)
9. [Testing requirements](#9-testing-requirements)

---

## 1. Architecture overview

The switchable market data layer uses two complementary patterns:

- **REST queries (snapshots):** Option chains, expirations, quotes-on-demand. Governed by the `OptionsDataProvider` protocol in C00.
- **Streaming (real-time):** Live quote/trade feeds. Governed by the `MarketDataStreamProvider` protocol (to be added to C00).

Both patterns are controlled by a single environment variable:

```bash
# .env
MARKET_DATA_PROVIDER=tradier    # Testing mode
MARKET_DATA_PROVIDER=databento   # Production mode
```

The factory in C00 reads this variable and returns the correct provider. All downstream consumers (strategies in D series, analytics in C series, risk in E series) call the factory and **never import Tradier or Databento directly**.

### 1.1 What changes, what doesn't

| Layer | Testing (Tradier) | Production (Databento) | Consumers see |
|-------|-------------------|----------------------|---------------|
| REST quotes | B40 `TradierClient.get_quotes()` | C26 `DatabentoClient` snapshot via historical API | `dict` with bid/ask/last/volume |
| Option chain + Greeks | B40 `get_option_chain_with_greeks()` | C26 historical definitions + Spyder Greeks calc | `list[GreekData]` (identical format) |
| Option expirations | B40 `get_option_expirations()` | C26 `get_instrument_definitions()` parsed | `dict` with expiration date list |
| Live quote stream | B40 `TradierMarketStream` (ENH-01) | C26 `DatabentoClient.start_live()` | Callback: `on_quote(NormalizedQuote)` |
| Live trade stream | B40 `TradierMarketStream` (ENH-01) | C26 `DatabentoClient.start_live()` | Callback: `on_trade(NormalizedTrade)` |
| Order execution | B40 `TradierClient` (always) | B40 `TradierClient` (always) | No change — Tradier is always the broker |

**Critical point:** Order execution always goes through Tradier (B40) regardless of the market data provider. The switch only affects where quotes and option chains come from.

---

## 2. Module spec: SpyderC00_MarketDataProtocol.py (revision)

| Field | Specification |
|-------|--------------|
| Module | `SpyderC00_MarketDataProtocol.py` |
| Current size | 128 lines |
| Action | Revise — expand protocol, add streaming protocol, implement Databento adapter, enhance factory |
| Target size | ~350-450 lines |
| Dependencies | `SpyderB40_TradierClient`, `SpyderC26_DatabentoClient` |

### 2.1 Current state assessment

C00 currently defines:

- `OptionsDataProvider` protocol with 3 methods (`get_quotes`, `get_option_chain_with_greeks`, `get_option_expirations`)
- `create_options_data_provider()` factory reading `MARKET_DATA_PROVIDER` env var
- Tradier path works; Databento path raises `NotImplementedError`

What's missing:

- No streaming protocol — strategies also need real-time data, not just REST snapshots
- No `DatabentoMarketDataAdapter` class — the Databento path is a stub
- No Greeks computation bridge — Databento doesn't provide Greeks, so the adapter must compute them
- No normalized data types — Tradier returns different structures than Databento

### 2.2 New protocol: MarketDataStreamProvider

Add a second protocol alongside `OptionsDataProvider` for streaming data:

```python
@runtime_checkable
class MarketDataStreamProvider(Protocol):
    """Protocol for real-time streaming market data."""

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """Start real-time data stream for given symbols."""
        ...

    def stop_stream(self) -> None:
        """Stop the real-time data stream."""
        ...

    def update_symbols(self, symbols: list[str]) -> None:
        """Update symbol subscription without reconnecting."""
        ...

    @property
    def is_streaming(self) -> bool:
        """Whether the stream is currently active."""
        ...
```

### 2.3 Normalized data types

Add these dataclasses to C00 so both providers emit identical structures.

#### 2.3.1 NormalizedQuote

```python
@dataclass
class NormalizedQuote:
    """
    Provider-agnostic quote representation.

    Identical structure regardless of whether data comes from Tradier or Databento.
    All downstream consumers (strategies, risk, analytics) use this type exclusively.
    """
    symbol: str             # Ticker symbol (equity or OCC option format)
    bid: float              # Best bid price
    ask: float              # Best ask price
    last: float             # Last trade price
    bid_size: int           # Bid size
    ask_size: int           # Ask size
    volume: int             # Cumulative session volume
    timestamp: datetime     # Quote timestamp (converted to ET)
    source: str             # "tradier" or "databento"

    @property
    def mid(self) -> float:
        """Midpoint of bid/ask."""
        return round((self.bid + self.ask) / 2, 4) if (self.bid + self.ask) > 0 else 0.0

    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        return round(self.ask - self.bid, 4)

    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as percentage of mid."""
        if self.mid <= 0:
            return 0.0
        return round((self.spread / self.mid) * 100, 2)
```

#### 2.3.2 NormalizedTrade

```python
@dataclass
class NormalizedTrade:
    """Provider-agnostic trade representation."""
    symbol: str             # Ticker symbol
    price: float            # Trade price
    size: int               # Trade size
    timestamp: datetime     # Trade timestamp
    source: str             # "tradier" or "databento"
```

### 2.4 DatabentoMarketDataAdapter class

This is the key new class. It wraps `SpyderC26_DatabentoClient` and implements **both** `OptionsDataProvider` and `MarketDataStreamProvider`.

**The adapter solves three translation problems:**

#### 2.4.1 REST quotes translation

Databento doesn't have a simple `get_quotes()` REST endpoint like Tradier. Instead, the adapter should:

- Use C26's `get_latest_quotes()` (new method — see section 3) to read from the live stream buffer
- If no live stream is active, fall back to C26's `get_historical_bars()` with schema `"tbbo"` and a 1-second window ending "now"
- Return data in the same dict format as Tradier: `{"quotes": {"quote": {"symbol": ..., "bid": ..., "ask": ..., "last": ...}}}`

```python
class DatabentoMarketDataAdapter:
    """
    Adapts SpyderC26_DatabentoClient to satisfy OptionsDataProvider
    and MarketDataStreamProvider protocols.
    """

    def __init__(self, client: DatabentoClient):
        self._client = client
        self._greeks_engine = None  # Lazy-init pricing engine

    # --- OptionsDataProvider methods ---

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """
        Get current quotes via Databento.

        Reads from live stream buffer if streaming, otherwise makes
        a short historical request.

        Returns:
            Dict matching Tradier's quote response structure for compatibility.
        """
        raw = self._client.get_latest_quotes(symbols)
        # Normalize to Tradier-compatible dict structure
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
```

#### 2.4.2 Option chain + Greeks translation

This is the most complex translation. Databento provides raw option chain data **without Greeks**.

1. Call C26's `get_instrument_definitions()` to get the chain structure (strikes, expirations)
2. Call C26's `get_historical_quotes()` with schema `"mbp-1"` for the latest bid/ask on each contract
3. Compute Greeks internally using Black-Scholes (for equity options) from the raw bid/ask data and underlying price
4. Return `list[GreekData]` using the same dataclass from B40 — strategies see no difference

**Greeks computation:** Use Spyder's existing `SpyderV05_PricingEngine` or `SpyderN_OptionsAnalytics` for Black-Scholes. The adapter calls the pricing engine with: underlying price, strike, expiration, risk-free rate, and mid-price of the option to back-solve implied volatility, then computes delta/gamma/theta/vega/rho.

```python
    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list:
        """
        Get option chain with computed Greeks from Databento data.

        Unlike Tradier which returns Greeks inline, this method:
        1. Fetches instrument definitions for the chain structure
        2. Fetches latest bid/ask for each contract
        3. Computes Greeks using Black-Scholes via SpyderV05_PricingEngine

        Returns:
            list[GreekData] — identical format to TradierClient's method.
        """
        # 1. Get chain structure
        defs_df = self._client.get_instrument_definitions(symbol, expiration)
        if defs_df is None or defs_df.empty:
            return []

        # 2. Get current underlying price
        underlying_quotes = self._client.get_latest_quotes([symbol])
        underlying_mid = underlying_quotes.get(symbol, {}).get("mid", 0.0)
        if underlying_mid <= 0:
            logger.warning(f"Cannot get underlying price for {symbol}")
            return []

        # 3. Get latest quotes for all option contracts
        # (filter by expiration and option_type if specified)
        option_symbols = self._extract_option_symbols(defs_df, expiration, option_type)
        option_quotes = self._client.get_latest_quotes(option_symbols)

        # 4. Compute Greeks for each contract
        results = []
        for occ_symbol in option_symbols:
            quote = option_quotes.get(occ_symbol, {})
            defn = self._lookup_definition(defs_df, occ_symbol)
            if not defn or not quote:
                continue

            greeks = self._compute_greeks(
                underlying_price=underlying_mid,
                strike=defn["strike"],
                expiration_date=defn["expiration"],
                option_type=defn["option_type"],
                bid=quote.get("bid", 0.0),
                ask=quote.get("ask", 0.0),
            )
            results.append(greeks)

        return results
```

#### 2.4.3 Streaming translation

The adapter maps C26's callback structure to the normalized types:

- Set C26's `on_quote` callback to convert `MarketDataUpdate` → `NormalizedQuote` and forward
- Set C26's `on_trade` callback to convert `MarketDataUpdate` → `NormalizedTrade` and forward
- C26's `start_live(underlyings=["SPY"])` maps to `start_stream(symbols=["SPY"])`
- C26's `stop_live()` maps to `stop_stream()`
- Databento's subscription model (subscribe by underlying parent) naturally returns all SPY options

```python
    # --- MarketDataStreamProvider methods ---

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """Start Databento live stream, normalizing output."""
        self._user_on_quote = on_quote
        self._user_on_trade = on_trade

        # Wire C26 callbacks to normalization layer
        self._client.on_quote = self._handle_databento_quote
        self._client.on_trade = self._handle_databento_trade

        # Databento subscribes by underlying "parent" to get all options
        self._client.start_live(underlyings=symbols, schema="mbp-1")

    def stop_stream(self) -> None:
        """Stop Databento live stream."""
        self._client.stop_live()

    def update_symbols(self, symbols: list[str]) -> None:
        """
        Update subscription.
        Note: Databento requires reconnecting to change symbols.
        This stops and restarts the stream.
        """
        was_streaming = self.is_streaming
        if was_streaming:
            self.stop_stream()
            self.start_stream(
                symbols,
                on_quote=self._user_on_quote,
                on_trade=self._user_on_trade,
            )

    @property
    def is_streaming(self) -> bool:
        return self._client.is_connected

    def _handle_databento_quote(self, update: "MarketDataUpdate") -> None:
        """Convert Databento MarketDataUpdate to NormalizedQuote."""
        if self._user_on_quote is None:
            return
        try:
            nq = NormalizedQuote(
                symbol=update.symbol,
                bid=update.data.get("bid", 0.0),
                ask=update.data.get("ask", 0.0),
                last=update.data.get("price", 0.0),
                bid_size=update.data.get("bid_size", 0),
                ask_size=update.data.get("ask_size", 0),
                volume=update.data.get("volume", 0),
                timestamp=update.datetime,
                source="databento",
            )
            self._user_on_quote(nq)
        except Exception as e:
            logger.error(f"Error normalizing Databento quote: {e}")

    def _handle_databento_trade(self, update: "MarketDataUpdate") -> None:
        """Convert Databento MarketDataUpdate to NormalizedTrade."""
        if self._user_on_trade is None:
            return
        try:
            nt = NormalizedTrade(
                symbol=update.symbol,
                price=update.data.get("price", 0.0),
                size=update.data.get("size", 0),
                timestamp=update.datetime,
                source="databento",
            )
            self._user_on_trade(nt)
        except Exception as e:
            logger.error(f"Error normalizing Databento trade: {e}")
```

### 2.5 TradierMarketDataAdapter class

For symmetry, wrap the Tradier side too. This is simpler since B40 already matches `OptionsDataProvider`:

- For `OptionsDataProvider`: delegate directly to B40 `TradierClient` (it already satisfies the protocol)
- For `MarketDataStreamProvider`: wrap B40's `TradierMarketStream` (from ENH-01)
- Convert Tradier WebSocket messages to `NormalizedQuote`/`NormalizedTrade`

```python
class TradierMarketDataAdapter:
    """
    Adapts SpyderB40_TradierClient to satisfy OptionsDataProvider
    and MarketDataStreamProvider protocols.

    Since TradierClient already implements OptionsDataProvider methods,
    this adapter mostly delegates directly. The streaming adapter wraps
    TradierMarketStream (ENH-01) to normalize output.
    """

    def __init__(self, client: "TradierClient"):
        self._client = client
        self._stream: "TradierMarketStream | None" = None

    # --- OptionsDataProvider (direct delegation) ---

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        return self._client.get_quotes(symbols)

    def get_option_chain_with_greeks(
        self, symbol: str, expiration: str, option_type: str | None = None
    ) -> list:
        return self._client.get_option_chain_with_greeks(symbol, expiration, option_type)

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        return self._client.get_option_expirations(symbol)

    # --- MarketDataStreamProvider ---

    def start_stream(
        self,
        symbols: list[str],
        on_quote: Callable[[NormalizedQuote], None] | None = None,
        on_trade: Callable[[NormalizedTrade], None] | None = None,
    ) -> None:
        """Start Tradier WebSocket stream with normalized output."""
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierMarketStream

        self._user_on_quote = on_quote
        self._user_on_trade = on_trade

        self._stream = TradierMarketStream(
            client=self._client,
            symbols=symbols,
            filters=["trade", "quote"],
        )
        self._stream.on_quote = self._handle_tradier_quote
        self._stream.on_trade = self._handle_tradier_trade
        self._stream.start()

    def stop_stream(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream = None

    def update_symbols(self, symbols: list[str]) -> None:
        if self._stream:
            self._stream.update_symbols(symbols)

    @property
    def is_streaming(self) -> bool:
        return self._stream is not None and self._stream.is_running

    def _handle_tradier_quote(self, msg: dict) -> None:
        """Convert Tradier WebSocket quote to NormalizedQuote."""
        if self._user_on_quote is None:
            return
        try:
            nq = NormalizedQuote(
                symbol=msg.get("symbol", ""),
                bid=msg.get("bid", 0.0),
                ask=msg.get("ask", 0.0),
                last=msg.get("last", 0.0),
                bid_size=msg.get("bidsz", 0),
                ask_size=msg.get("asksz", 0),
                volume=msg.get("volume", 0),
                timestamp=datetime.now(),
                source="tradier",
            )
            self._user_on_quote(nq)
        except Exception as e:
            logger.error(f"Error normalizing Tradier quote: {e}")

    def _handle_tradier_trade(self, msg: dict) -> None:
        """Convert Tradier WebSocket trade to NormalizedTrade."""
        if self._user_on_trade is None:
            return
        try:
            nt = NormalizedTrade(
                symbol=msg.get("symbol", ""),
                price=msg.get("last", 0.0),
                size=msg.get("size", 0),
                timestamp=datetime.now(),
                source="tradier",
            )
            self._user_on_trade(nt)
        except Exception as e:
            logger.error(f"Error normalizing Tradier trade: {e}")
```

### 2.6 Enhanced factory

Replace the current `create_options_data_provider()` with two factories:

```python
def create_options_data_provider() -> OptionsDataProvider:
    """
    REST query provider. Reads MARKET_DATA_PROVIDER from env.

    Returns:
        TradierMarketDataAdapter when MARKET_DATA_PROVIDER=tradier (or unset).
        DatabentoMarketDataAdapter when MARKET_DATA_PROVIDER=databento.

    Raises:
        RuntimeError: If the selected provider cannot be instantiated.
    """
    provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()

    if provider == "databento":
        from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import (
            create_databento_client_from_env,
        )
        return DatabentoMarketDataAdapter(create_databento_client_from_env())

    # Default: Tradier
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        create_tradier_client_from_env,
    )
    return TradierMarketDataAdapter(create_tradier_client_from_env())


def create_stream_provider() -> MarketDataStreamProvider:
    """
    Streaming provider. Reads same MARKET_DATA_PROVIDER env var.

    Returns:
        TradierMarketDataAdapter or DatabentoMarketDataAdapter.
    """
    provider = os.getenv("MARKET_DATA_PROVIDER", "tradier").lower().strip()

    if provider == "databento":
        from Spyder.SpyderC_MarketData.SpyderC26_DatabentoClient import (
            create_databento_client_from_env,
        )
        return DatabentoMarketDataAdapter(create_databento_client_from_env())

    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        create_tradier_client_from_env,
    )
    return TradierMarketDataAdapter(create_tradier_client_from_env())
```

Both adapters implement both protocols, so either factory can return either adapter. The two factories exist for type clarity — callers that only need REST queries use the first, callers that need streaming use the second.

### 2.7 Acceptance criteria

- Setting `MARKET_DATA_PROVIDER=tradier` returns `TradierMarketDataAdapter` from both factories
- Setting `MARKET_DATA_PROVIDER=databento` returns `DatabentoMarketDataAdapter` from both factories
- `NormalizedQuote` and `NormalizedTrade` have identical fields regardless of provider
- `GreekData` returned by Databento adapter matches Tradier's format (same dataclass)
- Streaming works for both providers with the same callback signature
- Switching providers requires zero code changes — only the `.env` variable

---

## 3. Module spec: SpyderC26_DatabentoClient.py (revision)

| Field | Specification |
|-------|--------------|
| Module | `SpyderC26_DatabentoClient.py` |
| Current size | 1,389 lines |
| Action | Revise — SDK version bump, API fixes, add missing features |
| SDK current | `databento >= 0.44.0` (written against) |
| SDK target | `databento >= 0.70.0` (v0.73 is current as of March 2026) |

### 3.1 SDK version gap analysis

The C26 module was written against databento SDK v0.44+. Between v0.44 and v0.73, several significant changes occurred.

#### 3.1.1 Breaking changes to address

- **`CBBOMsg`/`BBOMsg` removed:** Removed from root package exports in favor of aliased versions from `databento-dbn`. Update any direct references.
- **`from_dbn()` removed:** Replaced by `read_dbn()`. C26 doesn't use this directly, but verify no transitive usage.
- **`batch.submit_job` packaging param removed:** Deprecated then removed. C26 doesn't use batch, so no impact.
- **`Live.stop()` behavior changed:** Now properly closes connection within reasonable time. C26's `stop_live()` should work better with this fix.

#### 3.1.2 New features to leverage

- **Auto-reconnect:** Live client now supports automatic reconnection on unexpected disconnection. C26 has custom reconnection logic — evaluate whether to use SDK's built-in reconnect or keep custom logic.
- **`ts_out` support:** Fixed in recent versions. Live records now have `ts_out` populated. Update `_normalize_record()` to capture this.
- **Python 3.13 support:** Added in v0.63+. C26 should bump minimum to Python >= 3.10 (Databento's requirement).
- **Reference client:** New client for corporate actions, security master, adjustment factors. Useful for dividend-adjusted pricing.
- **Multi-thread safety:** Fixed issue where creating Live clients in multiple threads caused RuntimeError. Good for Spyder's threaded architecture.

### 3.2 Specific code changes

#### 3.2.1 Update dependency declaration

```python
# BEFORE (line 39)
# Dependencies: databento>=0.44.0

# AFTER
# Dependencies: databento>=0.70.0
```

#### 3.2.2 Price normalization fix

C26 line 443 uses a fragile heuristic to detect fixed-point prices:

```python
# CURRENT (fragile heuristic — breaks for penny stocks)
data["price"] = record.price / 1e9 if record.price > 1e6 else record.price

# RECOMMENDED: Use consistent FIXED_PRICE_SCALE constant
FIXED_PRICE_SCALE = 1_000_000_000  # Databento fixed-point scaling factor

# Then throughout _normalize_record():
data["price"] = record.price / FIXED_PRICE_SCALE
```

Databento **always** uses fixed-point integers with a 1e9 scale factor for prices. The `> 1e6` heuristic will break for penny stocks or deeply out-of-the-money options. Replace **all** price normalization with consistent division by `FIXED_PRICE_SCALE`. This applies to:

- `record.price` (line 443)
- `level.bid_px` and `level.ask_px` (lines 456-457)
- `record.strike_price` (line 487)
- `record.min_price_increment` (line 498)
- OHLCV fields `open/high/low/close` (lines 473-476)

#### 3.2.3 Add auto-reconnect evaluation

C26's `_live_stream_loop` has custom exponential backoff reconnection. The SDK now offers built-in reconnection. The coding agent should:

1. Test whether `db.Live()` with auto-reconnect handles the same failure scenarios
2. If SDK reconnect is sufficient, simplify `_live_stream_loop` by delegating to it
3. If not, keep custom logic but add a comment explaining why

#### 3.2.4 Add snapshot method for REST-style quote access

C26 currently only has streaming and historical methods. Add a convenience method the adapter needs:

```python
def get_latest_quotes(self, symbols: list[str]) -> dict[str, dict]:
    """
    Get latest quotes by reading from the live stream buffer,
    or by making a short historical request if no stream is active.

    This method is used by DatabentoMarketDataAdapter to satisfy
    the OptionsDataProvider.get_quotes() protocol.

    Args:
        symbols: List of symbols to get quotes for.

    Returns:
        Dict mapping symbol -> {"bid": float, "ask": float, "last": float,
                                "volume": int, "mid": float, "timestamp": datetime}
    """
    results = {}

    # Strategy 1: Read from live stream buffer (preferred — zero latency)
    if self._running and self.message_buffer:
        # Scan buffer in reverse for most recent quote per symbol
        seen = set()
        for update in reversed(self.message_buffer):
            if update.symbol in symbols and update.symbol not in seen:
                results[update.symbol] = {
                    "bid": update.data.get("bid", 0.0),
                    "ask": update.data.get("ask", 0.0),
                    "last": update.data.get("price", update.data.get("close", 0.0)),
                    "volume": update.data.get("volume", 0),
                    "mid": (update.data.get("bid", 0.0) + update.data.get("ask", 0.0)) / 2,
                    "timestamp": update.datetime,
                }
                seen.add(update.symbol)
            if seen == set(symbols):
                break

    # Strategy 2: Fall back to short historical request
    missing = [s for s in symbols if s not in results]
    if missing:
        for sym in missing:
            try:
                df = self.get_historical_bars(
                    symbol=sym,
                    start=(datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                    end=datetime.utcnow().isoformat(),
                    schema="tbbo",
                )
                if df is not None and not df.empty:
                    last_row = df.iloc[-1]
                    results[sym] = {
                        "bid": float(last_row.get("bid_px_00", 0)),
                        "ask": float(last_row.get("ask_px_00", 0)),
                        "last": float(last_row.get("price", 0)),
                        "volume": int(last_row.get("size", 0)),
                        "mid": (float(last_row.get("bid_px_00", 0)) + float(last_row.get("ask_px_00", 0))) / 2,
                        "timestamp": datetime.utcnow(),
                    }
            except Exception as e:
                logger.warning(f"Could not get historical fallback for {sym}: {e}")

    return results
```

#### 3.2.5 Capture ts_out in _normalize_record

Add to the `_normalize_record()` function:

```python
# Capture ts_out (time record was sent to client) — available since SDK v0.63
if hasattr(record, "ts_out"):
    data["ts_out"] = record.ts_out
```

### 3.3 Acceptance criteria

- Module imports and runs against databento SDK v0.73 without deprecation warnings
- All price normalization uses consistent `FIXED_PRICE_SCALE` constant
- `get_latest_quotes()` returns current data from live buffer or historical fallback
- Existing live streaming and historical methods continue to work unchanged
- Change log updated with v1.1.0 entry

---

## 4. Module spec: SpyderB40_TradierClient.py (integration point)

B40 has its own enhancement spec (document B40-ENHANCE-SPEC-001). This section covers only the additional requirement for the switchable data layer.

### 4.1 No structural changes needed

B40's `TradierClient` already satisfies the `OptionsDataProvider` protocol because it implements:

- `get_quotes(symbols: list[str]) -> dict[str, Any]`
- `get_option_chain_with_greeks(symbol, expiration, option_type) -> list[GreekData]`
- `get_option_expirations(symbol) -> dict[str, Any]`

Once ENH-01 (WebSocket market data streaming) is implemented, `TradierMarketStream` will satisfy the streaming side. The `TradierMarketDataAdapter` in C00 wraps both.

### 4.2 One addition: normalize WebSocket output

The `TradierMarketStream` from ENH-01 emits raw Tradier WebSocket JSON. The adapter needs a conversion function. This can live in the adapter (C00) rather than in B40:

```python
def _tradier_ws_to_normalized_quote(msg: dict) -> NormalizedQuote:
    """Convert Tradier WebSocket quote message to NormalizedQuote."""
    return NormalizedQuote(
        symbol=msg.get("symbol", ""),
        bid=msg.get("bid", 0.0),
        ask=msg.get("ask", 0.0),
        last=msg.get("last", 0.0),
        bid_size=msg.get("bidsz", 0),
        ask_size=msg.get("asksz", 0),
        volume=msg.get("volume", 0),
        timestamp=datetime.now(),
        source="tradier",
    )
```

---

## 5. Module spec: SpyderB30_SPYOptionsChainManager.py (deprecation)

B30 is a 919-line module that manages SPY option chains. Its header explicitly states:

> *"⚠️ MIGRATION STATUS: Future: Full migration to Tradier + Databento APIs. Recommended: Use SpyderB40_TradierClient + SpyderC26_DatabentoClient for new options chain functionality."*

With the switchable data layer in place, B30's functionality is fully replaced by:

- `C00.create_options_data_provider()` for option chain queries
- B40 `get_option_chain_with_greeks()` (Tradier mode) or C26 + Greeks computation (Databento mode)
- The adapter handles strike selection, expiration lookups, and Greeks — everything B30 does

**Recommended action:** Do not delete B30 yet. Instead:

1. Add a deprecation warning to B30's `__init__` method that logs: `"SpyderB30 is deprecated. Use C00.create_options_data_provider() instead."`
2. Add a comment at the top of the module: `# DEPRECATED — use SpyderC00_MarketDataProtocol`
3. Do not add new features to B30
4. Migrate any consumers of B30 to use the C00 factory instead

---

## 6. Implementation order

The coding agent should implement these changes in this exact order.

### Phase 1: Foundation (no external dependencies)

1. **Step 1 — C00 data types:** Add `NormalizedQuote`, `NormalizedTrade`, `MarketDataStreamProvider` protocol to C00. No functional changes yet.

2. **Step 2 — C00 TradierMarketDataAdapter:** Implement the Tradier adapter wrapping B40. This should work immediately with the existing `TradierClient`. Note: the streaming part requires ENH-01 from B40-ENHANCE-SPEC-001 to be completed first; if not ready, implement the REST portion only and add a `# TODO: wire TradierMarketStream once ENH-01 is complete` comment for streaming.

3. **Step 3 — C00 factory update:** Update `create_options_data_provider()` to return `TradierMarketDataAdapter`. Add `create_stream_provider()`. Verify all existing consumers still work.

### Phase 2: Databento side

4. **Step 4 — C26 SDK update:** Bump databento dependency to >= 0.70.0, fix price normalization, add `get_latest_quotes()`, capture `ts_out`.

5. **Step 5 — C00 DatabentoMarketDataAdapter:** Implement the Databento adapter wrapping C26. Include Greeks computation bridge.

6. **Step 6 — C00 factory Databento path:** Wire the Databento path in the factory. Test with `MARKET_DATA_PROVIDER=databento`.

### Phase 3: Validation

7. **Step 7 — Switch test:** Write a test that starts with `MARKET_DATA_PROVIDER=tradier`, runs a strategy for 30 seconds, stops, switches to `databento`, runs the same strategy for 30 seconds. Both runs should produce valid signals.

8. **Step 8 — B30 deprecation:** Add deprecation warnings to B30. Migrate known consumers.

---

## 7. Configuration reference

### 7.1 Environment variables

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| `MARKET_DATA_PROVIDER` | `tradier` \| `databento` | `tradier` | Which market data source to use |
| `TRADIER_API_KEY` | Bearer token string | (none) | Tradier API authentication |
| `TRADIER_ACCOUNT_ID` | Account ID string | (none) | Tradier account identifier |
| `DATABENTO_API_KEY` | `db-*` API key string | (none) | Databento API authentication |
| `DATABENTO_DATASET` | `OPRA.PILLAR` \| `XNAS.ITCH` | `OPRA.PILLAR` | Databento dataset for options |
| `DATABENTO_MAX_DAILY_GB` | Float (GB) | `5.0` | Cost control bandwidth cap |

### 7.2 Switching between providers

To switch from Tradier (testing) to Databento (production):

```bash
# 1. Ensure Databento credentials are set
export DATABENTO_API_KEY=db-your-key-here

# 2. Switch the provider
export MARKET_DATA_PROVIDER=databento

# 3. Restart Spyder
# All market data will now flow from Databento OPRA feed
# Order execution continues through Tradier unchanged
```

To switch back:

```bash
export MARKET_DATA_PROVIDER=tradier
# Restart Spyder — back to Tradier market data
```

---

## 8. Coding standards reminder

All code must follow Spyder's GLM-Specs coding standards (see `ClaudeFeed_ModuleFormatExample.md` in project knowledge). Key points for this work:

- C00 revision must update the module header (Author, Last Updated, Change Log)
- New dataclasses go in a `DATA STRUCTURES` section with banner comments
- New protocols go in the `PROTOCOL DEFINITION` section
- Adapter classes go in a new `ADAPTER IMPLEMENTATIONS` section
- Factory functions stay in the `FACTORY` section
- All public methods have Google-style docstrings with `Args`, `Returns`, `Raises`, `Example`
- Modern typing: `X | None`, `dict[str, Any]`, `list[str]`
- Log levels: `INFO` for connection events, `DEBUG` for data events, `WARNING` for fallbacks, `ERROR` for failures
- Section banners use the exact format:

```python
# ==========================================================================
# SECTION NAME IN CAPS
# ==========================================================================
```

---

## 9. Testing requirements

### 9.1 Unit tests

- Test `NormalizedQuote` and `NormalizedTrade` dataclass creation and properties (mid, spread, spread_pct)
- Test `TradierMarketDataAdapter` satisfies both protocols (`isinstance` checks)
- Test `DatabentoMarketDataAdapter` satisfies both protocols
- Test `create_options_data_provider()` returns correct adapter based on env var
- Test `create_stream_provider()` returns correct adapter based on env var
- Mock both Tradier and Databento to verify normalization produces identical `NormalizedQuote` for same underlying data

### 9.2 Integration tests

- With `MARKET_DATA_PROVIDER=tradier`: verify `get_quotes(["SPY"])` returns valid data from Tradier sandbox
- With `MARKET_DATA_PROVIDER=databento`: verify `get_quotes(["SPY"])` returns valid data from Databento (requires API key)
- Verify `GreekData` from both providers has delta/gamma/theta/vega populated for ATM SPY options
- Verify streaming works for both providers (receive at least 1 `NormalizedQuote` within 30 seconds)

### 9.3 Switch test

Create a dedicated test: `SpyderT_Testing/SpyderT_MarketDataSwitch_Test.py`

- Start with Tradier, fetch SPY option chain, verify `GreekData` list is non-empty
- Switch to Databento, fetch same option chain, verify `GreekData` list is non-empty
- Compare: both should have the same strikes and expirations (Greeks values will differ slightly due to different model inputs)
- Verify `NormalizedQuote.source` field correctly reflects the active provider

---

*End of specification*
