# SPYDER — SpyderB40_TradierClient Enhancement Specification

**Document:** B40-ENHANCE-SPEC-001  
**Version:** 1.0  
**Date:** 2026-03-16  
**Author:** Claude (Maestro)  
**Series:** SpyderB_Broker  
**Module:** SpyderB40_TradierClient.py  
**Priority:** High — Production-critical broker interface  
**Status:** Draft — Pending review  

> This document provides complete implementation specifications for enhancing the SpyderB40_TradierClient module. Each specification is self-contained with acceptance criteria, integration points, and code-level guidance.

---

## Table of contents

1. [Overview and context](#1-overview-and-context)
2. [ENH-01: WebSocket market data streaming](#2-enh-01-websocket-market-data-streaming)
3. [ENH-02: WebSocket account event streaming](#3-enh-02-websocket-account-event-streaming)
4. [ENH-03: Dynamic rate limit header parsing](#4-enh-03-dynamic-rate-limit-header-parsing)
5. [ENH-04: Advanced order types (OCO/OTO/OTOCO)](#5-enh-04-advanced-order-types-ocootootoco)
6. [ENH-05: Missing REST endpoints](#6-enh-05-missing-rest-endpoints)
7. [ENH-06: Order preview (dry-run)](#7-enh-06-order-preview-dry-run)
8. [ENH-07: Async migration from deprecated API](#8-enh-07-async-migration-from-deprecated-api)
9. [Integration map and dependency summary](#9-integration-map-and-dependency-summary)
10. [Coding standards and conventions](#10-coding-standards-and-conventions)
11. [Testing requirements](#11-testing-requirements)

---

## 1. Overview and context

The SpyderB40_TradierClient module is Spyder's primary REST API client for the Tradier Brokerage. The current implementation (v2.0.0) provides synchronous REST calls with async wrappers, SSE-based account streaming, multileg order support, Greeks parsing, and OCC symbol utilities. This specification defines seven enhancements that bring the module to production grade.

### 1.1 Current module inventory

The following capabilities exist and must not be broken by any enhancement:

- **REST client:** `_make_request()` with retry, connection pooling, error classification
- **Account endpoints:** profile, balances, positions, history
- **Order endpoints:** place (single-leg), place multileg, modify, cancel, get order(s)
- **Market data:** quotes, option chain, option chain with Greeks, expirations, strikes
- **Convenience methods:** `place_iron_condor()`, `place_credit_spread()`, `find_options_by_delta()`
- **Streaming:** `TradierAccountStream` class (SSE via sseclient-py, threaded)
- **Async wrappers:** All major methods wrapped with `@rate_limit` and `tradier_breaker`
- **Utilities:** `build_option_symbol()`, `parse_option_symbol()`, `create_tradier_client_from_env()`

### 1.2 Architecture constraints

- All enhancements must remain within the single `SpyderB40_TradierClient.py` file
- Must use Spyder's existing `SpyderLogger`, `rate_limit` decorator, and `tradier_breaker`
- Sync methods are the primary API; async wrappers use `run_in_executor` pattern
- Thread safety required — streaming classes run in daemon threads
- Python 3.13.3 compatibility required; use modern typing (`X | None`, not `Optional[X]`)
- Environment: Ubuntu 25.04, virtual environment (.venv)

### 1.3 Tradier API rate limits (reference)

| Category | Production | Sandbox | Scope |
|----------|-----------|---------|-------|
| Standard (accounts, users, orders) | 120 req/min | 60 req/min | Per access token |
| Market data (/markets) | 120 req/min | 60 req/min | Per access token |
| Trading (order placement) | 60 req/min | 60 req/min | Per access token |

Response headers: `X-Ratelimit-Allowed`, `X-Ratelimit-Used`, `X-Ratelimit-Available`, `X-Ratelimit-Expiry`

---

## 2. ENH-01: WebSocket market data streaming

| Field | Specification |
|-------|--------------|
| Priority | P0 — Critical |
| Effort | Large (new class, ~250-350 lines) |
| Dependency | `websocket-client >= 1.7.0` (`pip install websocket-client`) |
| Replaces | Polling via `get_quotes()` for real-time data |
| API endpoint | `wss://ws.tradier.com/v1/markets/events` |
| Sandbox | `wss://sandbox-ws.tradier.com/v1/markets/events` |

### 2.1 Purpose

Add a `TradierMarketStream` class that provides real-time market data (trades, quotes, summaries) via Tradier's WebSocket API. This replaces the current polling pattern for SPY quotes and enables sub-second market data processing — a core Spyder requirement.

### 2.2 Protocol flow

The Tradier WebSocket streaming protocol requires a two-step connection:

1. **Step 1 — Create session:** `POST /v1/markets/events/session` (uses existing `create_streaming_session()` method). Returns a `sessionid` valid for 5 minutes.
2. **Step 2 — Connect WebSocket:** Open WSS connection, send JSON payload with sessionid, symbols list, and event filter. Server begins streaming immediately.

The key advantage over SSE: symbols can be added/removed by resending the subscription payload on the existing connection without disconnecting.

### 2.3 New class: TradierMarketStream

Add this class after the existing `TradierAccountStream` class.

#### 2.3.1 Constructor

Parameters:

- **`client: TradierClient`** — Parent client instance (provides API key and `create_streaming_session()`)
- **`symbols: list[str]`** — Initial symbol list, e.g., `["SPY", "QQQ", "VIX"]`
- **`filters: list[str]`** — Event type filter. Valid values: `"trade"`, `"quote"`, `"summary"`, `"timesale"`, `"tradex"`. Default: `["trade", "quote"]`

Internal state:

- `_running: bool = False`
- `_thread: threading.Thread | None = None`
- `_ws: websocket.WebSocketApp | None = None`
- `_session_id: str | None = None`
- `_reconnect_attempts: int = 0`
- `_max_reconnect: int = 10`
- `_reconnect_delay: float = 2.0` (exponential backoff, capped at 120s)
- `_symbols: list[str]` (mutable — can be updated at runtime)
- `_filters: list[str]`

#### 2.3.2 Callbacks (public attributes)

- **`on_quote: Callable[[dict], None] | None`** — Fired on quote events (bid/ask/last for a symbol)
- **`on_trade: Callable[[dict], None] | None`** — Fired on trade events (last price, size, exchange)
- **`on_summary: Callable[[dict], None] | None`** — Fired on summary events (open/high/low/close)
- **`on_error: Callable[[str], None] | None`** — Fired on connection errors
- **`on_connected: Callable[[], None] | None`** — Fired when WebSocket opens successfully
- **`on_disconnected: Callable[[], None] | None`** — Fired on clean or unclean disconnect

#### 2.3.3 Public methods

**`start() -> None`**

- Validate `websocket-client` is importable (raise `ImportError` with pip install hint if not)
- Validate `_running` is False (log warning and return if already running)
- Create streaming session via `client.create_streaming_session()`
- Set `_running = True`, `_reconnect_attempts = 0`
- Start daemon thread targeting `_stream_loop()`, name=`"TradierMarketStream"`

**`stop() -> None`**

- Set `_running = False`
- Call `_ws.close()` if `_ws` is not None
- Join thread with `timeout=10.0`, set `_thread = None`

**`update_symbols(symbols: list[str]) -> None`**

- Update `_symbols` in place
- If `_ws` is connected, resend subscription payload via `_ws.send()` (JSON)
- This is the key WebSocket advantage: no reconnection needed

**`is_running: bool` (property)**

- Return `_running and _thread is not None and _thread.is_alive()`

#### 2.3.4 Internal methods

**`_stream_loop() -> None`**

Main loop with reconnection logic (mirror `TradierAccountStream._stream_loop` pattern):

- While `_running` and `_reconnect_attempts < _max_reconnect`:
  - Create session if `_session_id` is None or expired
  - Determine WebSocket URL based on `client.environment`
  - Create `WebSocketApp` with `on_open`, `on_message`, `on_error`, `on_close` handlers
  - Call `_ws.run_forever(ping_interval=30, ping_timeout=10)`
  - On exception: increment `_reconnect_attempts`, exponential backoff, log error
  - On successful connect: reset `_reconnect_attempts = 0`

**`_on_ws_open(ws) -> None`**

- Build subscription payload: `{"symbols": _symbols, "sessionid": _session_id, "filter": _filters}`
- `ws.send(json.dumps(payload))`
- Fire `on_connected` callback if set
- Log: `"Market stream connected: {len(_symbols)} symbols"`

**`_on_ws_message(ws, message) -> None`**

- Parse JSON. Ignore empty/heartbeat messages.
- Extract event type from message (`"type"` field)
- Dispatch: `"quote"` → `on_quote`, `"trade"` → `on_trade`, `"summary"` → `on_summary`
- Log at DEBUG level: symbol, event type, key fields

**`_on_ws_error(ws, error) -> None`**

- Log error, fire `on_error` callback

**`_on_ws_close(ws, close_status_code, close_msg) -> None`**

- Fire `on_disconnected` callback
- Log with status code and message

### 2.4 Data class: MarketEvent

Add a dataclass for structured market event data:

```python
@dataclass
class MarketEvent:
    """Structured market event from Tradier WebSocket stream."""
    event_type: str         # "trade", "quote", or "summary"
    symbol: str             # Ticker symbol
    timestamp: str          # Event timestamp from Tradier
    bid: float = 0.0       # Best bid (quote events)
    ask: float = 0.0       # Best ask (quote events)
    last: float = 0.0      # Last trade price
    size: int = 0           # Trade size
    volume: int = 0         # Cumulative volume
    data: dict[str, Any] = field(default_factory=dict)  # Raw event payload
```

### 2.5 Acceptance criteria

- `TradierMarketStream` connects to Tradier WebSocket and receives SPY quote/trade events
- Reconnects automatically with exponential backoff on disconnect
- `update_symbols()` modifies subscription without reconnecting
- All callbacks fire correctly and exceptions in callbacks do not crash the stream
- Graceful `stop()` within 10 seconds
- Works in both LIVE and SANDBOX environments
- Thread-safe: can be started/stopped from any thread

---

## 3. ENH-02: WebSocket account event streaming

| Field | Specification |
|-------|--------------|
| Priority | P1 — High |
| Effort | Medium (~100-150 lines, refactor of existing class) |
| Dependency | `websocket-client` (same as ENH-01) |
| Replaces | `TradierAccountStream` (SSE-based, sseclient-py) |
| API endpoint | `wss://ws.tradier.com/v1/accounts/events` |
| Sandbox | `wss://sandbox-ws.tradier.com/v1/accounts/events` |

### 3.1 Purpose

Refactor the existing `TradierAccountStream` from SSE (Server-Sent Events) to WebSocket transport. This aligns both streaming classes on the same transport, removes the `sseclient-py` dependency, and gains the ability to modify subscriptions without reconnecting.

### 3.2 Implementation approach

Do **NOT** delete the existing `TradierAccountStream` class. Instead:

- Rename the existing class to `TradierAccountStreamSSE` (preserve as fallback)
- Create new `TradierAccountStream` class using WebSocket transport
- Mirror the same callback interface: `on_event`, `on_order`, `on_trade`, `on_error`
- Keep the same `AccountEvent` dataclass unchanged
- Use the same reconnection pattern as `TradierMarketStream` (ENH-01)

### 3.3 WebSocket subscription payload

On connection open, send:

```json
{
    "events": ["order", "account"],
    "sessionid": "<session_id>",
    "excludeAccounts": []
}
```

Valid event types: `"order"`, `"account"`. Subscribe to both for complete coverage.

### 3.4 Key differences from SSE implementation

- Use `websocket.WebSocketApp` instead of `requests.post` + `sseclient.SSEClient`
- WebSocket URL: `wss://ws.tradier.com/v1/accounts/events` (not `stream.tradier.com`)
- Message format: JSON objects (same structure as SSE data payloads)
- Heartbeats handled by WebSocket ping/pong (`ping_interval=30`)

### 3.5 Acceptance criteria

- New class receives order fill/cancel/reject events identically to SSE version
- Existing `on_event`, `on_order`, `on_trade` callback signatures unchanged
- `AccountEvent` dataclass populated identically
- Reconnection logic works correctly with exponential backoff
- SSE fallback class preserved as `TradierAccountStreamSSE`

---

## 4. ENH-03: Dynamic rate limit header parsing

| Field | Specification |
|-------|--------------|
| Priority | P1 — High |
| Effort | Small (~40-60 lines, modification to existing method) |
| Dependency | None (uses existing requests response headers) |
| Modifies | `_make_request()` method and adds `RateLimitInfo` dataclass |

### 4.1 Purpose

Tradier returns rate limit metadata in every response header. Currently ignored. Parse these headers and expose them so Spyder's rate limiter (`SpyderU40_RateLimiter`) can adapt dynamically instead of using a static estimate.

### 4.2 New dataclass: RateLimitInfo

```python
@dataclass
class RateLimitInfo:
    """Rate limit state from Tradier response headers."""
    allowed: int        # From X-Ratelimit-Allowed header
    used: int           # From X-Ratelimit-Used header
    available: int      # From X-Ratelimit-Available header
    expiry: int         # From X-Ratelimit-Expiry header (epoch millis)
    timestamp: float    # time.time() when captured

    @property
    def remaining_pct(self) -> float:
        """Percentage of rate limit remaining."""
        if self.allowed <= 0:
            return 0.0
        return round((self.available / self.allowed) * 100, 1)
```

### 4.3 Modifications to _make_request()

After receiving a successful response (status 200), before returning the JSON body:

1. Extract all four `X-Ratelimit-*` headers from `response.headers`
2. Create `RateLimitInfo` instance, store as `self._last_rate_limit`
3. If `available <= 10`: log WARNING with remaining count and expiry time
4. If `available <= 3`: log ERROR — approaching hard limit
5. Store on instance: `self._last_rate_limit: RateLimitInfo | None = None`

### 4.4 New public method

**`get_rate_limit_info() -> RateLimitInfo | None`**

- Return `self._last_rate_limit`
- Allows Spyder's rate limiter or monitoring GUI to query current state

### 4.5 Acceptance criteria

- Every successful API call updates `_last_rate_limit`
- Warning logged when fewer than 10 requests remain in window
- `get_rate_limit_info()` returns most recent rate limit snapshot
- No performance impact on `_make_request()` hot path (header extraction is O(1))

---

## 5. ENH-04: Advanced order types (OCO / OTO / OTOCO)

| Field | Specification |
|-------|--------------|
| Priority | P2 — Medium |
| Effort | Medium (~150-200 lines, three new methods + async wrappers) |
| Dependency | None |
| API reference | Tradier Brokerage API — Trading section |

### 5.1 Purpose

Add support for contingent order types that Tradier supports but our client currently does not. These are essential for automated bracket orders and protective stop management in Spyder's strategy modules.

### 5.2 New methods

#### 5.2.1 place_oco_order()

One-Cancels-Other: two orders where execution of either cancels the other. Used for take-profit + stop-loss brackets.

Parameters:

- **`symbol: str`** — Underlying symbol
- **`legs: list[dict]`** — Two order leg definitions, each containing: `side`, `quantity`, `type`, `duration`, `price`, `stop`, `option_symbol` (optional)
- **`duration: OrderDuration`** — Time-in-force for the OCO pair

Tradier payload structure: `class="oco"`, with `leg[0]` and `leg[1]` indexed parameters.

#### 5.2.2 place_oto_order()

One-Triggers-Other: first order must fill before second order is submitted. Used for entry + automatic stop placement.

Parameters: same structure as OCO but `class="oto"`.

#### 5.2.3 place_otoco_order()

One-Triggers-OCO: first order triggers an OCO pair. Used for entry + take-profit + stop-loss as a single atomic order group.

Parameters: three legs — trigger leg + two OCO legs. `class="otoco"`.

### 5.3 Async wrappers

Each method gets a corresponding `_async` version following the existing pattern:

- `@rate_limit(service="tradier")` decorator
- `async with tradier_breaker` context
- `loop.run_in_executor(None, lambda: self.place_xxx_order(...))`

### 5.4 Acceptance criteria

- All three order types accepted by Tradier sandbox API (no validation errors)
- Error raised if wrong number of legs provided (OCO=2, OTO=2, OTOCO=3)
- Async wrappers follow existing pattern exactly
- Proper logging at INFO level for order placement

---

## 6. ENH-05: Missing REST endpoints

| Field | Specification |
|-------|--------------|
| Priority | P2 — Medium |
| Effort | Medium (~120-180 lines, straightforward REST wrappers) |
| Dependency | None |

### 6.1 Purpose

Add coverage for Tradier API endpoints not currently implemented in the client.

### 6.2 Endpoints to add

| Method name | HTTP | Endpoint | Purpose |
|-------------|------|----------|---------|
| `get_market_calendar(month, year)` | GET | `/markets/calendar` | Trading days/holidays for scheduling |
| `get_market_clock()` | GET | `/markets/clock` | Current market state (pre/open/post/closed) |
| `get_gainloss()` | GET | `/accounts/{id}/gainloss` | Realized P&L for tax/performance reporting |
| `get_watchlists()` | GET | `/watchlists` | User's watchlists |
| `add_to_watchlist(id, symbols)` | POST | `/watchlists/{id}/symbols` | Add symbols to watchlist |
| `get_time_sales(symbol, ...)` | GET | `/markets/timesales` | Tick-level time and sales data |
| `search_symbols(query)` | GET | `/markets/search` | Symbol search/lookup |
| `get_historical_quotes(symbol, ...)` | GET | `/markets/history` | Historical OHLCV bars |

### 6.3 Implementation pattern

Each method follows the exact same pattern as existing methods like `get_quotes()`:

- Log at INFO or DEBUG level (DEBUG for market data, INFO for account operations)
- Call `self._make_request(method, endpoint, params=...)`
- Return raw dict response
- Add corresponding `_async` wrapper with `rate_limit` + `tradier_breaker`

### 6.4 Acceptance criteria

- All eight methods return valid responses from Tradier sandbox
- All eight have corresponding async wrappers
- Docstrings include `Args`, `Returns`, and `Example` sections

---

## 7. ENH-06: Order preview (dry-run)

| Field | Specification |
|-------|--------------|
| Priority | P2 — Medium |
| Effort | Small (~40-60 lines) |
| Dependency | None |
| API endpoint | `POST /accounts/{id}/orders` (with `preview=true` parameter) |

### 7.1 Purpose

Tradier supports an order preview mode that validates an order and returns estimated cost, commission, and margin impact without actually placing it. This is critical for Spyder's risk management layer (SpyderE_Risk) to pre-validate orders before execution.

### 7.2 New method: preview_order()

Parameters: identical to `place_order()`, plus the same for multileg.

Implementation: build the same payload as `place_order()` / `place_multileg_order()`, but add `"preview": "true"` to the payload.

Return the Tradier preview response which includes:

- Estimated cost / proceeds
- Commission / fees
- Margin impact
- Order validation status

### 7.3 Convenience methods

- **`preview_multileg_order()`** — Preview for multileg orders
- **`preview_iron_condor()`** — Preview for iron condor (wraps `preview_multileg_order`)
- **`preview_credit_spread()`** — Preview for credit spread

### 7.4 Acceptance criteria

- Preview returns validation result without placing an order
- Invalid orders return error details (not exceptions) from the preview response
- Works for single-leg equity, single-leg option, and multileg orders

---

## 8. ENH-07: Async migration from deprecated API

| Field | Specification |
|-------|--------------|
| Priority | P3 — Low (housekeeping) |
| Effort | Small (~20 lines changed across multiple methods) |
| Dependency | None |

### 8.1 Purpose

All async wrappers currently use `asyncio.get_event_loop()` which is deprecated in Python 3.10+. Replace with `asyncio.get_running_loop()` for forward compatibility.

### 8.2 Change specification

In every async method (there are currently 9), replace:

```python
# BEFORE (deprecated)
loop = asyncio.get_event_loop()

# AFTER
loop = asyncio.get_running_loop()
```

This is a one-line change per method. No behavioral difference when called from within an active async context (which is always the case in Spyder).

### 8.3 Affected methods

- `place_order_async`
- `get_quotes_async`
- `get_account_balances_async`
- `get_positions_async`
- `cancel_order_async`
- `get_option_chain_async`
- `place_multileg_order_async`
- `get_option_chain_with_greeks_async`
- `get_option_strikes_async`
- `modify_order_async`
- Plus any new async methods added by ENH-04 and ENH-05.

### 8.4 Acceptance criteria

- All async methods use `asyncio.get_running_loop()`
- No `DeprecationWarning` on Python 3.13.3
- All async methods still function identically when called via `await`

---

## 9. Integration map and dependency summary

### 9.1 New dependencies

| Package | Version | Purpose | Install |
|---------|---------|---------|---------|
| `websocket-client` | `>= 1.7.0` | WebSocket transport for ENH-01/02 | `pip install websocket-client` |

The `sseclient-py` dependency is retained (`TradierAccountStreamSSE` fallback) but moves to optional.

### 9.2 Dependency on Spyder internals

| Import | Used by | Purpose |
|--------|---------|---------|
| `SpyderU01_Logger.SpyderLogger` | All code | Centralized logging |
| `SpyderU40_RateLimiter.rate_limit` | All async methods | Async rate limiting decorator |
| `SpyderU41_CircuitBreaker.tradier_breaker` | All async methods | Circuit breaker context manager |

### 9.3 Enhancement dependency order

The following implementation order respects dependencies:

1. **ENH-07** (async fix) — Zero dependencies, apply first
2. **ENH-03** (rate limit headers) — Modifies `_make_request`, apply before new methods use it
3. **ENH-01** (market stream) — Requires `websocket-client` installed
4. **ENH-02** (account stream) — Reuses patterns from ENH-01
5. **ENH-05** (REST endpoints) — Independent, can be done in parallel
6. **ENH-04** (advanced orders) — Independent, can be done in parallel
7. **ENH-06** (order preview) — Depends on ENH-04 patterns for multileg preview

### 9.4 New constants

Add to the `CONSTANTS` section:

```python
TRADIER_WS_URL = "wss://ws.tradier.com/v1"
TRADIER_SANDBOX_WS_URL = "wss://sandbox-ws.tradier.com/v1"
WS_PING_INTERVAL = 30   # seconds
WS_PING_TIMEOUT = 10    # seconds
```

### 9.5 Change log entry

Update the module header change log:

```
2026-XX-XX (v3.0.0):
    - Added TradierMarketStream (WebSocket market data streaming)
    - Added TradierAccountStream WebSocket variant
    - Added dynamic rate limit header parsing (RateLimitInfo)
    - Added OCO/OTO/OTOCO advanced order types
    - Added missing REST endpoints (calendar, clock, gainloss, etc.)
    - Added order preview (dry-run) support
    - Fixed: async methods use get_running_loop() (Python 3.10+)
    - Added MarketEvent, RateLimitInfo dataclasses
    - Added websocket-client dependency for WebSocket transport
```

---

## 10. Coding standards and conventions

All code must follow Spyder's established GLM-Specs coding standards. Key requirements:

### 10.1 File structure

The module file is organized with banner-separated sections. New code must be placed in the correct section:

- New dataclasses (`MarketEvent`, `RateLimitInfo`): in the `DATA CLASSES` section after `AccountEvent`
- New streaming classes: after the existing `TradierAccountStream` section
- New REST methods on `TradierClient`: grouped with related existing methods
- New async wrappers: in the `ASYNC WRAPPERS` section

### 10.2 Section banners

Use the exact banner format:

```python
# ==========================================================================
# SECTION NAME IN CAPS
# ==========================================================================
```

### 10.3 Docstrings

Every public method must have a Google-style docstring with:

- One-line summary
- Extended description (if behavior is non-obvious)
- `Args:` section with type and description for each parameter
- `Returns:` section describing the return value
- `Raises:` section listing possible exceptions
- `Example:` section with a concrete usage example

### 10.4 Type annotations

- Use modern union syntax: `X | None` (not `Optional[X]`)
- Use `dict[str, Any]` (not `Dict[str, Any]`)
- Use `list[str]` (not `List[str]`)
- All method signatures must be fully annotated

### 10.5 Logging

- Use the module-level `logger` (already defined as `logger = SpyderLogger.get_logger(__name__)`)
- `INFO` for business events (order placed, stream connected)
- `DEBUG` for data events (quote received, API call made)
- `WARNING` for recoverable issues (reconnection, rate limit low)
- `ERROR` for failures (connection lost, max retries exceeded)

### 10.6 Error handling

- Raise the appropriate `TradierAPIError` subclass for API failures
- Never swallow exceptions silently — always log before re-raising
- Callbacks must be wrapped in `try/except` to prevent stream crashes

---

## 11. Testing requirements

### 11.1 Unit tests

Each enhancement must include corresponding tests. Test file: `SpyderT_Testing/test_SpyderB40_TradierClient.py`

- Mock Tradier API responses using `unittest.mock.patch` on `requests.Session`
- Mock WebSocket connections using `unittest.mock` on `websocket.WebSocketApp`
- Test all error paths (auth failure, rate limit, server error, timeout)
- Test dataclass creation and property calculations

### 11.2 Integration tests (sandbox)

Require `TRADIER_API_KEY` and `TRADIER_ACCOUNT_ID` environment variables:

- Test real connection to Tradier sandbox
- Test WebSocket market stream receives at least one event within 30 seconds
- Test order preview returns valid response
- Test market calendar returns current month data

### 11.3 Performance requirements

Per Spyder project standards:

- Market data processing: < 100ms from WebSocket message receipt to callback completion
- REST API calls: < 2 seconds including network latency
- Stream reconnection: within 5 seconds of detecting disconnect
- Memory: stream threads must not leak memory over 24-hour runtime

### 11.4 Validation checklist

Before marking any enhancement as complete, verify:

- All new methods have complete docstrings with `Args`, `Returns`, `Raises`, `Example`
- All new methods have corresponding async wrappers where appropriate
- No Python deprecation warnings on 3.13.3
- Module imports cleanly: `python -c "from Spyder.SpyderB_Broker.SpyderB40_TradierClient import *"`
- Existing `__main__` test block still runs successfully
- `pylint` score >= 9.0 for the module

---

*End of specification*
