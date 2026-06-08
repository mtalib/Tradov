# SPEC-TRADOV-03 — Tradier Broker Integration Module

| Field | Value |
|---|---|
| Spec ID | SPEC-TRADOV-03 |
| Module | `tradov/broker/tradier/` (package) |
| Version | 1.0.0 |
| Status | Ready for implementation |
| Depends on | (none — this is the lowest layer) |
| Target | Production-grade Tradier REST + WebSocket client for SPY options |

---

## 1. Purpose

A reliable, well-tested Tradier client used by every Tradov strategy. The module:
1. Provides a typed Python interface over Tradier's REST and streaming endpoints.
2. Handles authentication, rate limiting, retries, and error classification.
3. Implements a `BrokerProtocol` matching the one used by the backtest simulator (SPEC-TRADOV-02), so live and backtest are interchangeable behind the strategy layer.
4. Persists every raw API response for audit and debugging.

---

## 2. Endpoints Used

### 2.1 REST endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/v1/user/profile` | GET | Bootstrap account ID at startup |
| `/v1/accounts/{id}/balances` | GET | NAV, buying power, day trades |
| `/v1/accounts/{id}/positions` | GET | Open positions for reconciliation |
| `/v1/accounts/{id}/orders` | GET | Open and historical orders |
| `/v1/accounts/{id}/orders` | POST | Place order (multileg, equity, option, OCO, OTOCO) |
| `/v1/accounts/{id}/orders/{id}` | DELETE | Cancel order |
| `/v1/accounts/{id}/orders/{id}` | PUT | Modify order |
| `/v1/markets/options/chains` | GET | Full chain with greeks (ORATS-sourced) |
| `/v1/markets/options/expirations` | GET | Available expirations |
| `/v1/markets/options/strikes` | GET | Available strikes per expiration |
| `/v1/markets/quotes` | GET / POST | Live quotes — POST for >50 symbols |
| `/v1/markets/clock` | GET | Market open/closed state |
| `/v1/markets/calendar` | GET | Trading days |
| `/v1/markets/history` | GET | Historical OHLCV |

### 2.2 Streaming endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/markets/events/session` | Create market data session token |
| `POST /v1/accounts/events/session` | Create account event session token |
| `wss://ws.tradier.com/v1/markets/events` | Real-time quotes, trades, summaries |
| `wss://ws.tradier.com/v1/accounts/events` | Order fills, status changes |

---

## 3. Authentication and Configuration

Two environments, never mixed at runtime:

```python
from enum import Enum
from dataclasses import dataclass

class TradierEnv(Enum):
    PRODUCTION = "production"
    SANDBOX    = "sandbox"

ENDPOINTS = {
    TradierEnv.PRODUCTION: {
        "rest":   "https://api.tradier.com/v1",
        "stream": "wss://ws.tradier.com/v1",
    },
    TradierEnv.SANDBOX: {
        "rest":   "https://sandbox.tradier.com/v1",
        "stream": "wss://sandbox-ws.tradier.com/v1",
    },
}

@dataclass(frozen=True)
class TradierConfig:
    env:        TradierEnv
    api_token:  str          # never log or persist
    account_id: str
    timeout_seconds:    float = 10.0
    rate_limit_per_sec: float = 4.0    # well below the 60/min docs limit
    retry_max_attempts: int   = 3
    retry_backoff_base: float = 0.5    # exponential
```

The token is loaded from `~/.tradov/secrets.toml` (`chmod 600`), never from environment variables in production (env vars leak into child processes and crash dumps).

---

## 4. Client Class Hierarchy

```
TradierClient                 # Composition root
├── TradierAuth               # Token + headers
├── TradierRateLimiter        # Token bucket
├── TradierRetryPolicy        # Exponential backoff with jitter
├── MarketDataClient          # /markets/* endpoints
├── TradingClient             # /accounts/{id}/orders, balances, positions
└── StreamingClient           # WebSocket subscriptions
```

Each sub-client is independently testable. `TradierClient` is the only thing strategies see.

---

## 5. The OCC Symbol

Tradier (and all U.S. brokers) use the standard OCC option symbol format:

```
SYMBOL    YYMMDD     C/P     STRIKE_x_1000
SPY       260117     C       00578000      = SPY 17-Jan-2026 $578.00 Call
```

Total length is always 21 characters: 6-char ticker (right-padded with spaces), 6-digit date, 1-char type, 8-digit strike (strike * 1000, zero-padded).

```python
import re
from dataclasses import dataclass
from datetime import date

OCC_RE = re.compile(r"^([A-Z]{1,6})\s*(\d{6})([CP])(\d{8})$")

@dataclass(frozen=True)
class OccSymbol:
    underlying:   str
    expiration:   date
    option_type:  str   # 'C' or 'P'
    strike:       float

    @classmethod
    def parse(cls, s: str) -> "OccSymbol":
        m = OCC_RE.match(s.strip())
        if not m:
            raise ValueError(f"Not a valid OCC symbol: {s!r}")
        ul, dt, otype, strike_int = m.groups()
        exp = date(2000 + int(dt[:2]), int(dt[2:4]), int(dt[4:6]))
        strike = int(strike_int) / 1000.0
        return cls(ul, exp, otype, strike)

    def encode(self) -> str:
        dt = self.expiration.strftime("%y%m%d")
        strike_int = int(round(self.strike * 1000))
        return f"{self.underlying}{dt}{self.option_type}{strike_int:08d}"
```

---

## 6. Reading Market Data

### 6.1 Get Options Chain (with greeks)

```python
def get_chain(self, underlying: str, expiration: date) -> OptionChain:
    """
    GET /v1/markets/options/chains?symbol={underlying}&expiration={YYYY-MM-DD}&greeks=true

    Returns full chain with delta, gamma, theta, vega, rho, phi, IV
    (computed by ORATS, refreshed periodically — not tick-perfect).
    """
    resp = self._get(
        "/markets/options/chains",
        params={
            "symbol":     underlying,
            "expiration": expiration.isoformat(),
            "greeks":     "true",
        },
    )
    return OptionChain.from_tradier_response(resp)
```

### 6.2 Get Today's Expiration

For 0DTE strategies, get the `expirations` list and find an entry where `expiration_type == "weeklys"` (or daily) matching today's date.

```python
def get_zero_dte_expiration(self, underlying: str) -> date | None:
    """
    SPY has Mon/Tue/Wed/Thu/Fri expirations since 2023.
    Returns today's expiration if one exists, else None.
    """
    today = self.market.today_et()
    resp = self._get(
        "/markets/options/expirations",
        params={"symbol": underlying, "includeAllRoots": "true"},
    )
    for exp_str in resp["expirations"]["date"]:
        if date.fromisoformat(exp_str) == today:
            return today
    return None
```

### 6.3 Streaming Quotes

For sub-second strike monitoring during ACTIVE state:

```python
async def stream_quotes(self, occ_symbols: list[str]) -> AsyncIterator[QuoteUpdate]:
    """
    1) POST /markets/events/session   -> session_id
    2) WS wss://.../markets/events     subscribe to session_id with symbols
    3) Yield decoded QuoteUpdate events
    """
    session = await self._create_market_session()
    ws = await websockets.connect(self._stream_url("/markets/events"))
    await ws.send(json.dumps({
        "symbols":    occ_symbols,
        "sessionid":  session.id,
        "linebreak":  True,
        "filter":     ["quote", "trade", "summary"],
    }))
    async for raw in ws:
        yield QuoteUpdate.from_json(raw)
```

---

## 7. Placing Orders

### 7.1 The Multileg Iron Condor (canonical example)

```python
async def place_iron_condor(
    self,
    legs: CondorLegs,
    quantity: int,
    limit_credit: float,
    duration: str = "day",
    preview: bool = True,
) -> OrderResponse:
    """
    POST /v1/accounts/{account_id}/orders
    class=multileg, type=credit
    """
    payload = {
        "class":    "multileg",
        "symbol":   "SPY",
        "type":     "credit",
        "duration": duration,
        "price":    f"{limit_credit:.2f}",
        # Leg 0: long put
        "option_symbol[0]": legs.long_put.encode(),
        "side[0]":          "buy_to_open",
        "quantity[0]":      str(quantity),
        # Leg 1: short put
        "option_symbol[1]": legs.short_put.encode(),
        "side[1]":          "sell_to_open",
        "quantity[1]":      str(quantity),
        # Leg 2: short call
        "option_symbol[2]": legs.short_call.encode(),
        "side[2]":          "sell_to_open",
        "quantity[2]":      str(quantity),
        # Leg 3: long call
        "option_symbol[3]": legs.long_call.encode(),
        "side[3]":          "buy_to_open",
        "quantity[3]":      str(quantity),
    }
    if preview:
        payload["preview"] = "true"

    return await self._post(f"/accounts/{self.account_id}/orders", data=payload)
```

### 7.2 Closing the same condor

Build a separate order: flip every `_to_open` to `_to_close`, change `type` from `credit` to `debit`, and set the limit to your acceptable debit.

### 7.3 Order types reference

| `type` | Use case |
|---|---|
| `market` | Avoid for options — slippage on wide spreads can be brutal |
| `limit` | Single-leg options |
| `stop` / `stop_limit` | Stop orders on equity, sometimes options |
| `credit` | Multileg orders that must result in net credit |
| `debit` | Multileg orders that must result in net debit |
| `even` | Net-zero credit/debit (rare; for adjustments) |

For credit spreads and iron condors, **always use `type=credit`** for opening and **`type=debit`** for closing. Tradier enforces sign correctness — a positive `price` with `type=credit` means *minimum* credit required.

---

## 8. The `BrokerProtocol`

Live `TradierClient` and `SimulatedBroker` (SPEC-TRADOV-02) both implement:

```python
from typing import Protocol

class BrokerProtocol(Protocol):
    @property
    def account_id(self) -> str: ...
    def get_nav(self) -> float: ...
    def get_buying_power(self) -> float: ...
    def get_open_positions(self) -> list[Position]: ...

    def place_iron_condor(
        self,
        legs: CondorLegs,
        quantity: int,
        limit_credit: float,
        duration: str = "day",
        preview: bool = True,
    ) -> OrderResponse: ...

    def close_iron_condor(
        self,
        order_id: str,
        limit_debit: float,
    ) -> OrderResponse: ...

    def cancel_order(self, order_id: str) -> None: ...
    def get_order(self, order_id: str) -> Order: ...
    def get_position_mtm(self, order_id: str) -> float: ...
```

Strategies type-hint against this Protocol, not against `TradierClient`.

---

## 9. Rate Limiting

Tradier publishes rate limits per endpoint category. The client uses a token bucket:

```python
class TradierRateLimiter:
    """Token bucket per endpoint category. Refill rate set per docs:
       - Trading: 60 req/min
       - Market Data: 120 req/min
       - Streaming session creation: 1 req/sec
    """
    def __init__(self, capacity: int, refill_per_second: float): ...
    async def acquire(self) -> None: ...
```

The conservative defaults in `TradierConfig` (`rate_limit_per_sec=4`) leave significant headroom; the limiter is mostly a safety net.

---

## 10. Retry and Error Classification

```python
class TradierError(Exception):                  pass
class TradierAuthError(TradierError):           pass      # 401, 403 — never retry
class TradierClientError(TradierError):         pass      # 4xx — never retry except 429
class TradierRateLimitError(TradierError):      pass      # 429 — retry with backoff
class TradierServerError(TradierError):         pass      # 5xx — retry
class TradierTimeoutError(TradierError):        pass      # network — retry

def is_retryable(e: Exception) -> bool:
    return isinstance(e, (TradierRateLimitError, TradierServerError, TradierTimeoutError))
```

Retry policy: 3 attempts max, exponential backoff with full jitter:

```python
async def _retry(self, fn, *args, **kwargs):
    for attempt in range(self.cfg.retry_max_attempts):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if not is_retryable(e) or attempt == self.cfg.retry_max_attempts - 1:
                raise
            sleep_s = self.cfg.retry_backoff_base * (2 ** attempt) * random.random()
            await asyncio.sleep(sleep_s)
```

---

## 11. Persistence — Audit Log

Every API call's full request and response is persisted to a local SQLite DB for audit:

```sql
CREATE TABLE IF NOT EXISTS tradier_calls (
    call_id          TEXT PRIMARY KEY,
    timestamp_utc    TEXT NOT NULL,
    method           TEXT NOT NULL,           -- GET | POST | PUT | DELETE
    endpoint         TEXT NOT NULL,
    request_params   TEXT,                    -- JSON, with token redacted
    response_status  INTEGER NOT NULL,
    response_body    TEXT,                    -- JSON
    duration_ms      INTEGER NOT NULL,
    error_class      TEXT,
    correlation_id   TEXT                     -- ties to strategy trade_id
);

CREATE INDEX idx_tradier_calls_endpoint ON tradier_calls(endpoint);
CREATE INDEX idx_tradier_calls_correlation ON tradier_calls(correlation_id);
```

Tokens are scrubbed before persistence. Persistence is asynchronous (queue + background writer) so it never adds latency to the critical path.

---

## 12. Reconciliation on Startup

After a crash or restart, the strategy layer can't trust its own DB about what's open. The client provides a reconciliation routine:

```python
async def reconcile(self) -> ReconciliationReport:
    """
    Compare the local trades DB against Tradier's source of truth.
    Returns:
      - orders_open_at_broker_not_local
      - orders_open_local_not_at_broker
      - positions_open_at_broker_not_local
      - positions_open_local_not_at_broker
    """
```

A startup hook calls reconcile and refuses to start trading if any discrepancy exists, escalating to HUMAN_REVIEW.

---

## 13. Sandbox vs Production Guards

Three guard rails to prevent the catastrophic "I thought I was on sandbox" mistake:

1. **At config load:** if `env=PRODUCTION` and the file path is under `~/.tradov/dev/`, refuse to load.
2. **At startup:** print a 5-line banner with the environment in red and require a `TRADOV_PROD_CONFIRMED=1` env var.
3. **At order submission:** if `env=PRODUCTION` and `quantity > config.production_max_qty`, refuse and log.

```python
def assert_production_safe(cfg: TradierConfig) -> None:
    if cfg.env == TradierEnv.PRODUCTION:
        if os.environ.get("TRADOV_PROD_CONFIRMED") != "1":
            raise RuntimeError(
                "Production trading requires TRADOV_PROD_CONFIRMED=1 in environment. "
                "Set it deliberately and never in shell rc files."
            )
```

---

## 14. Test Plan

### 14.1 Unit tests
- OCC symbol round-trip (`parse(encode(x)) == x` for 1000 random symbols)
- Rate limiter releases tokens at the correct rate under load
- Retry policy retries the right errors and gives up at the limit
- Multileg payload encoding matches the canonical Tradier example byte-for-byte
- Auth header is present and token-redacted in logs

### 14.2 Integration tests (sandbox)
- Place a 1-contract iron condor → fills → close → verify P/L
- Cancel an unfilled order
- Modify an unfilled order (price change)
- Stream quotes for 4 OCC symbols for 30 seconds, verify >0 updates
- Account event stream emits `fill` event after a sandbox order fills
- Reconcile finds zero discrepancies in a clean state
- Reconcile finds the seeded discrepancy when one is intentionally introduced

### 14.3 Resilience tests (mocked)
- 429 rate limit response → backs off, eventually succeeds
- Network timeout → retries, eventually succeeds
- 401 auth error → does not retry, raises `TradierAuthError`
- WebSocket disconnect → reconnects, resubscribes

---

## 15. Acceptance Criteria

- [ ] All endpoints in §2.1 and §2.2 have a typed wrapper
- [ ] `BrokerProtocol` matches the simulator's signatures exactly
- [ ] Sandbox integration test suite passes for 5 consecutive days unattended
- [ ] Audit DB grows correctly under load and never blocks the critical path (<1ms p99 enqueue)
- [ ] Reconciliation is correct on a corrupted-local-state test
- [ ] No token ever appears in logs, exception messages, or audit DB
- [ ] Production-safe guards block accidental live trades in unit tests

---

## 16. Out of Scope

- IB / TWS support — separate spec if needed (`SPEC-TRADOV-03B_IB_Integration.md`)
- Equities trading — strategies are options-only for now
- FIX protocol — REST + WS is sufficient for SPY 0DTE volume
- OAuth flow — Tradier API uses long-lived bearer tokens; no rotation logic needed
