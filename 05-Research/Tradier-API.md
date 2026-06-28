Coding Agent Instructions: Implement Tradier API for Stocks and ETFs
1. Objective

Implement a production-grade Tradier brokerage adapter in Python for the existing Ubuntu / Wayland / PySide6 trading stack.

This new app is for stocks and ETFs only.

The adapter must support:

1. Sandbox and live Tradier environments.
2. Token-based authentication.
3. User profile lookup.
4. Account discovery.
5. Balances.
6. Positions.
7. Orders.
8. Equity and ETF quotes.
9. Symbol lookup/search.
10. Historical market data.
11. Order preview.
12. Order placement after explicit safety validation.
13. Rate-limit-aware request handling.
14. Async-safe integration with the PySide6 GUI.

Tradier provides account, trading, market-data, and streaming APIs for brokerage applications, including stocks and ETFs. The official docs describe account endpoints for balances, positions, orders, history, and gain/loss data, and trading endpoints for equity orders as well as more complex order types.

2. Hard Scope

This implementation is stocks and ETFs only.

Do not implement:

- Options.
- Option chains.
- Option expirations.
- Option strikes.
- Greeks.
- Implied volatility.
- Multi-leg option orders.
- Spreads.
- Naked option checks.
- SPY-only assumptions.

Allowed instruments:

- Common stocks.
- ETFs.

Initial allowed symbols may include:

SPY
QQQ
IWM
DIA
AAPL
MSFT
NVDA
AMZN
GOOGL
META
TSLA

But the code must not be hard-coded to SPY.

3. Environment Variables

Use environment variables only. Do not hard-code Tradier tokens.

TRADIER_ENV=sandbox
TRADIER_SANDBOX_TOKEN=replace_me
TRADIER_LIVE_API_KEY=replace_me
TRADIER_ACCOUNT_ID=
TRADIER_TIMEOUT_SECONDS=10
TRADIER_MAX_RETRIES=3
TRADIER_ENABLE_LIVE_TRADING=false
TRADIER_ALLOWED_SYMBOLS=SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA
TRADIER_MAX_SHARES_PER_ORDER=100
TRADIER_MAX_NOTIONAL_PER_ORDER=10000

Rules:

If TRADIER_ENV=sandbox:
    base_url = https://sandbox.tradier.com/v1
    token = TRADIER_SANDBOX_TOKEN

If TRADIER_ENV=live:
    base_url = https://api.tradier.com/v1
    token = TRADIER_LIVE_API_KEY

If TRADIER_ENV=live and TRADIER_ENABLE_LIVE_TRADING != true:
    block all order placement
    allow read-only endpoints
4. Python Dependencies

Add:

httpx>=0.27
pydantic>=2.7
python-dotenv>=1.0
tenacity>=8.3
websockets>=12.0
pytest>=8.0
pytest-asyncio>=0.23

Optional for PySide6 async integration:

qasync>=0.27
PySide6>=6.7

Do not use blocking requests in GUI-facing code.

All network operations must be async.

5. Proposed Module Layout

Create:

stock_app/
  brokers/
    tradier/
      __init__.py
      config.py
      client.py
      models.py
      market_data.py
      account.py
      orders.py
      streaming.py
      errors.py
      rate_limit.py
      safety.py
  tests/
    test_tradier_config.py
    test_tradier_client.py
    test_tradier_profile.py
    test_tradier_market_data.py
    test_tradier_orders_safety.py

Responsibilities:

config.py       Load environment and select sandbox/live settings.
client.py       Shared async HTTP client, headers, retries, errors.
models.py       Pydantic request/response models.
market_data.py  Quotes, symbol search, historical data, market clock/calendar.
account.py      Profile, balances, positions, account orders.
orders.py       Preview, place, cancel, replace/change equity orders.
streaming.py    Market/account streaming support.
errors.py       Typed exceptions.
rate_limit.py   Parse X-Ratelimit-* headers and throttle.
safety.py       Trading guardrails for stocks and ETFs.
6. Authentication Headers

Every JSON request must include:

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
}

For trading POST requests, include:

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

Tradier trading endpoints use Bearer-token authorization, JSON accept headers, and form-encoded content for order actions.

7. First Endpoint to Implement: User Profile

Implement:

GET /user/profile

Purpose:

Fetch profile information for the authenticated user.
Use this endpoint to discover available account IDs.

Implementation:

# stock_app/brokers/tradier/account.py

from .client import TradierClient


class TradierAccountService:
    def __init__(self, client: TradierClient):
        self.client = client

    async def get_profile(self) -> dict:
        return await self.client.get("/user/profile")

Acceptance test:

@pytest.mark.asyncio
async def test_get_profile_returns_user_and_accounts(tradier_account_service):
    profile = await tradier_account_service.get_profile()
    assert "profile" in profile

Do not assume a fixed account ID. Parse the profile response defensively.

8. Core Async HTTP Client
# stock_app/brokers/tradier/client.py

import httpx

from .config import TradierConfig
from .errors import TradierAPIError, TradierAuthError, TradierRateLimitError


class TradierClient:
    def __init__(self, config: TradierConfig):
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.token}",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict | None = None) -> dict:
        response = await self._client.get(path, params=params)
        return await self._handle_response(response)

    async def post_form(self, path: str, data: dict) -> dict:
        response = await self._client.post(
            path,
            data=data,
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        return await self._handle_response(response)

    async def delete(self, path: str) -> dict:
        response = await self._client.delete(path)
        return await self._handle_response(response)

    async def _handle_response(self, response: httpx.Response) -> dict:
        self._record_rate_limit_headers(response)

        if response.status_code == 401:
            raise TradierAuthError("Tradier authentication failed. Check token/environment.")

        if response.status_code == 429:
            raise TradierRateLimitError("Tradier rate limit exceeded.")

        if response.status_code >= 400:
            raise TradierAPIError(
                f"Tradier API error {response.status_code}: {response.text}"
            )

        if not response.content:
            return {}

        return response.json()

    def _record_rate_limit_headers(self, response: httpx.Response) -> None:
        # Persist/log these for diagnostics:
        # X-Ratelimit-Allowed
        # X-Ratelimit-Used
        # X-Ratelimit-Available
        # X-Ratelimit-Expiry
        pass

Tradier documents rate-limit headers including X-Ratelimit-Allowed, X-Ratelimit-Used, X-Ratelimit-Available, and X-Ratelimit-Expiry; these should be parsed and exposed to the dashboard.

9. Configuration Class
# stock_app/brokers/tradier/config.py

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TradierConfig:
    env: str
    base_url: str
    token: str
    account_id: str | None
    timeout_seconds: float
    max_retries: int
    enable_live_trading: bool
    allowed_symbols: set[str]
    max_shares_per_order: int
    max_notional_per_order: float

    @staticmethod
    def from_env() -> "TradierConfig":
        env = os.getenv("TRADIER_ENV", "sandbox").lower().strip()

        if env not in {"sandbox", "live"}:
            raise ValueError("TRADIER_ENV must be 'sandbox' or 'live'.")

        if env == "sandbox":
            base_url = "https://sandbox.tradier.com/v1"
            token = os.getenv("TRADIER_SANDBOX_TOKEN")
        else:
            base_url = "https://api.tradier.com/v1"
            token = os.getenv("TRADIER_LIVE_API_KEY")

        if not token:
            raise ValueError(f"Missing Tradier token for environment: {env}")

        allowed_symbols_raw = os.getenv(
            "TRADIER_ALLOWED_SYMBOLS",
            "SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA",
        )

        allowed_symbols = {
            symbol.strip().upper()
            for symbol in allowed_symbols_raw.split(",")
            if symbol.strip()
        }

        return TradierConfig(
            env=env,
            base_url=base_url,
            token=token,
            account_id=os.getenv("TRADIER_ACCOUNT_ID") or None,
            timeout_seconds=float(os.getenv("TRADIER_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.getenv("TRADIER_MAX_RETRIES", "3")),
            enable_live_trading=os.getenv(
                "TRADIER_ENABLE_LIVE_TRADING",
                "false",
            ).lower() == "true",
            allowed_symbols=allowed_symbols,
            max_shares_per_order=int(os.getenv("TRADIER_MAX_SHARES_PER_ORDER", "100")),
            max_notional_per_order=float(os.getenv("TRADIER_MAX_NOTIONAL_PER_ORDER", "10000")),
        )
10. Market Data Service: Stocks and ETFs Only

Implement:

GET /markets/quotes
GET /markets/search
GET /markets/lookup
GET /markets/history
GET /markets/clock
GET /markets/calendar

Do not implement option endpoints.

Minimum implementation:

# stock_app/brokers/tradier/market_data.py

from .client import TradierClient


class TradierMarketDataService:
    def __init__(self, client: TradierClient):
        self.client = client

    async def get_quotes(self, symbols: list[str]) -> dict:
        clean_symbols = [symbol.upper().strip() for symbol in symbols if symbol.strip()]

        return await self.client.get(
            "/markets/quotes",
            params={
                "symbols": ",".join(clean_symbols),
            },
        )

    async def get_quote(self, symbol: str) -> dict:
        return await self.get_quotes([symbol])

    async def search_symbols(self, query: str) -> dict:
        return await self.client.get(
            "/markets/search",
            params={"q": query},
        )

    async def lookup_symbol(self, symbol: str) -> dict:
        return await self.client.get(
            "/markets/lookup",
            params={"q": symbol},
        )

    async def get_history(
        self,
        symbol: str,
        interval: str = "daily",
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        params = {
            "symbol": symbol.upper().strip(),
            "interval": interval,
        }

        if start:
            params["start"] = start

        if end:
            params["end"] = end

        return await self.client.get("/markets/history", params=params)

    async def get_clock(self) -> dict:
        return await self.client.get("/markets/clock")

    async def get_calendar(self, month: int | None = None, year: int | None = None) -> dict:
        params = {}

        if month:
            params["month"] = month

        if year:
            params["year"] = year

        return await self.client.get("/markets/calendar", params=params)

Tradier’s market-data docs cover U.S. stocks and options, and the quote endpoint is the relevant quote source for stock and ETF symbols in this app.

Normalize quote data internally:

# stock_app/brokers/tradier/models.py

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedEquityQuote:
    symbol: str
    description: str | None
    bid: float | None
    ask: float | None
    last: float | None
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None
    average_volume: int | None
    change: float | None
    change_percentage: float | None
    timestamp_utc: datetime
11. Account Service

Implement:

GET /user/profile
GET /accounts/{account_id}/balances
GET /accounts/{account_id}/positions
GET /accounts/{account_id}/orders
GET /accounts/{account_id}/orders/{order_id}
GET /accounts/{account_id}/history
GET /accounts/{account_id}/gainloss

Skeleton:

# stock_app/brokers/tradier/account.py

from .client import TradierClient


class TradierAccountService:
    def __init__(self, client: TradierClient, account_id: str | None = None):
        self.client = client
        self.account_id = account_id

    async def get_profile(self) -> dict:
        return await self.client.get("/user/profile")

    async def resolve_account_id(self) -> str:
        if self.account_id:
            return self.account_id

        profile = await self.get_profile()
        account_id = extract_first_account_id(profile)

        if not account_id:
            raise RuntimeError("No Tradier account ID found in profile response.")

        return account_id

    async def get_balances(self) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/balances")

    async def get_positions(self) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/positions")

    async def get_orders(self) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/orders")

    async def get_order(self, order_id: str) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/orders/{order_id}")

    async def get_history(self) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/history")

    async def get_gainloss(self) -> dict:
        account_id = await self.resolve_account_id()
        return await self.client.get(f"/accounts/{account_id}/gainloss")

Tradier’s account guide explicitly covers balances, positions, orders, history, and gain/loss endpoints.

Implement robust account extraction:

def extract_first_account_id(profile_response: dict) -> str | None:
    profile = profile_response.get("profile") or {}
    account = profile.get("account")

    if isinstance(account, dict):
        return str(account.get("account_number") or account.get("id") or "")

    if isinstance(account, list) and account:
        first = account[0]
        if isinstance(first, dict):
            return str(first.get("account_number") or first.get("id") or "")

    return None
12. Order Service: Stocks and ETFs

Implement support for simple equity/ETF orders only.

Supported actions:

buy
sell
buy_to_cover
sell_short

Initial allowed order types:

market
limit
stop
stop_limit

Recommended default for automation:

Use limit orders by default.
Block market orders unless explicitly enabled.

Tradier’s trading guide covers equity orders and order placement via the trading endpoints.

Implementation:

# stock_app/brokers/tradier/orders.py

from .account import TradierAccountService
from .client import TradierClient
from .safety import validate_equity_order_safety


class TradierOrderService:
    def __init__(self, client: TradierClient, account_service: TradierAccountService):
        self.client = client
        self.account_service = account_service
        self._previewed_order_fingerprints: set[str] = set()

    async def preview_order(self, payload: dict) -> dict:
        account_id = await self.account_service.resolve_account_id()

        validate_equity_order_safety(
            payload=payload,
            config=self.client.config,
            preview=True,
        )

        data = dict(payload)
        data["preview"] = "true"

        response = await self.client.post_form(
            f"/accounts/{account_id}/orders",
            data=data,
        )

        self._previewed_order_fingerprints.add(fingerprint_order(payload))

        return response

    async def place_order(self, payload: dict) -> dict:
        account_id = await self.account_service.resolve_account_id()

        validate_equity_order_safety(
            payload=payload,
            config=self.client.config,
            preview=False,
        )

        if self.client.config.env == "live" and not self.client.config.enable_live_trading:
            raise PermissionError(
                "Live order placement blocked. Set TRADIER_ENABLE_LIVE_TRADING=true."
            )

        fingerprint = fingerprint_order(payload)

        if fingerprint not in self._previewed_order_fingerprints:
            raise PermissionError("Order placement blocked. Preview this exact order first.")

        response = await self.client.post_form(
            f"/accounts/{account_id}/orders",
            data=payload,
        )

        order_id = extract_order_id(response)
        if order_id:
            return await self.account_service.get_order(order_id)

        return response

Example stock/ETF limit order payload:

payload = {
    "class": "equity",
    "symbol": "AAPL",
    "side": "buy",
    "quantity": "10",
    "type": "limit",
    "duration": "day",
    "price": "185.50",
}

Example market order payload, if explicitly allowed:

payload = {
    "class": "equity",
    "symbol": "QQQ",
    "side": "buy",
    "quantity": "5",
    "type": "market",
    "duration": "day",
}
13. Safety Rules for Stocks and ETFs

Implement these hard rules in safety.py:

1. Default environment must be sandbox.
2. Live trading disabled unless TRADIER_ENABLE_LIVE_TRADING=true.
3. Stocks and ETFs only.
4. Reject all option-class orders.
5. Reject all multi-leg orders.
6. Reject symbols outside TRADIER_ALLOWED_SYMBOLS unless whitelist is disabled intentionally.
7. Reject order quantity > TRADIER_MAX_SHARES_PER_ORDER.
8. Reject estimated notional > TRADIER_MAX_NOTIONAL_PER_ORDER.
9. Require order preview before live order placement.
10. Require buying-power check before placement.
11. Use limit orders by default.
12. Reject market orders unless explicitly enabled.
13. Reject fractional quantities unless explicitly enabled.
14. Immediately fetch order status after submission.

Safety validator:

# stock_app/brokers/tradier/safety.py

from decimal import Decimal


ALLOWED_SIDES = {"buy", "sell", "buy_to_cover", "sell_short"}
ALLOWED_ORDER_TYPES = {"market", "limit", "stop", "stop_limit"}
ALLOWED_DURATIONS = {"day", "gtc", "pre", "post"}


def validate_equity_order_safety(payload: dict, config, preview: bool) -> None:
    order_class = str(payload.get("class", "")).lower()
    symbol = str(payload.get("symbol", "")).upper().strip()
    side = str(payload.get("side", "")).lower()
    order_type = str(payload.get("type", "")).lower()
    duration = str(payload.get("duration", "")).lower()

    if order_class != "equity":
        raise ValueError("Only equity-class orders are allowed for stocks and ETFs.")

    if not symbol:
        raise ValueError("Missing symbol.")

    if config.allowed_symbols and symbol not in config.allowed_symbols:
        raise ValueError(f"Symbol {symbol} is not in TRADIER_ALLOWED_SYMBOLS.")

    if side not in ALLOWED_SIDES:
        raise ValueError(f"Unsupported equity order side: {side}")

    if order_type not in ALLOWED_ORDER_TYPES:
        raise ValueError(f"Unsupported equity order type: {order_type}")

    if duration not in ALLOWED_DURATIONS:
        raise ValueError(f"Unsupported order duration: {duration}")

    quantity = Decimal(str(payload.get("quantity", "0")))

    if quantity <= 0:
        raise ValueError("Order quantity must be positive.")

    if quantity != quantity.to_integral_value():
        raise ValueError("Fractional shares are disabled by default.")

    if int(quantity) > config.max_shares_per_order:
        raise ValueError(
            f"Order quantity exceeds max shares per order: {config.max_shares_per_order}"
        )

    if order_type in {"limit", "stop_limit"}:
        price = Decimal(str(payload.get("price", "0")))
        if price <= 0:
            raise ValueError("Limit and stop-limit orders require a positive price.")

        estimated_notional = quantity * price

        if estimated_notional > Decimal(str(config.max_notional_per_order)):
            raise ValueError(
                f"Estimated notional exceeds max order notional: {config.max_notional_per_order}"
            )

    if order_type == "market":
        raise ValueError("Market orders are disabled by default. Use limit orders.")
14. Market Data Normalization

Normalize all quote responses into a broker-neutral model so the GUI is not coupled to Tradier response shape.

def normalize_equity_quote(raw_quote: dict) -> NormalizedEquityQuote:
    return NormalizedEquityQuote(
        symbol=raw_quote.get("symbol"),
        description=raw_quote.get("description"),
        bid=raw_quote.get("bid"),
        ask=raw_quote.get("ask"),
        last=raw_quote.get("last"),
        open=raw_quote.get("open"),
        high=raw_quote.get("high"),
        low=raw_quote.get("low"),
        close=raw_quote.get("close"),
        volume=raw_quote.get("volume"),
        average_volume=raw_quote.get("average_volume"),
        change=raw_quote.get("change"),
        change_percentage=raw_quote.get("change_percentage"),
        timestamp_utc=parse_tradier_timestamp(raw_quote),
    )

Internal normalized watchlist object:

@dataclass
class WatchlistQuote:
    symbol: str
    name: str | None
    asset_type: str
    last: float | None
    bid: float | None
    ask: float | None
    spread: float | None
    spread_pct: float | None
    day_change: float | None
    day_change_pct: float | None
    volume: int | None
    timestamp_utc: datetime
15. Streaming Support

Implement streaming separately from REST.

Do not put websocket logic inside the base REST client.

Initial streaming goals:

1. Create market streaming session.
2. Subscribe to stock/ETF symbols.
3. Emit quote/trade updates to controller.
4. Reconnect on disconnect.
5. Fall back to REST polling if streaming unavailable.

The market-data guide notes real-time data availability for U.S.-based stocks and options for Tradier Brokerage account holders. For this app, only subscribe to stock and ETF symbols.

Skeleton:

# stock_app/brokers/tradier/streaming.py

class TradierStreamingService:
    def __init__(self, client: TradierClient):
        self.client = client

    async def create_market_session(self) -> dict:
        return await self.client.post_form("/markets/events/session", data={})

    async def stream_symbols(self, symbols: list[str]):
        clean_symbols = [symbol.upper().strip() for symbol in symbols]
        # Implement websocket connection separately.
        # Emit normalized quote/trade events.
        raise NotImplementedError

Sandbox caveat:

If sandbox streaming is unavailable or delayed data cannot stream:
    use REST polling for development.
16. Rate-Limit Strategy

Tradier rate limits are token-based and documented with rate-limit response headers. The implementation must parse and expose these headers.

Implement:

- Central async request limiter.
- Parse X-Ratelimit-Allowed.
- Parse X-Ratelimit-Used.
- Parse X-Ratelimit-Available.
- Parse X-Ratelimit-Expiry.
- If available quota < 5, throttle.
- If HTTP 429, back off until reset/expiry if provided.
- Prefer streaming over aggressive REST polling.

Suggested polling defaults:

Watchlist quotes: every 1–3 seconds while market is open.
Account balances: every 30–60 seconds.
Positions: every 5–15 seconds.
Orders: every 2–5 seconds while active orders exist.
Historical data: on demand only.
Market clock: every 60 seconds.
17. PySide6 / Ubuntu / Wayland Integration

Rules:

1. Do not block the Qt UI thread.
2. Use async services behind a controller layer.
3. Use qasync or a worker event loop.
4. Emit Qt signals with normalized data.
5. Keep broker adapter independent of GUI.
6. No Tkinter.
7. No Streamlit.
8. No network polling inside widget classes.

Recommended architecture:

TradierClient
   ↓
TradierMarketDataService / TradierAccountService / TradierOrderService
   ↓
BrokerController
   ↓
Qt Signals
   ↓
PySide6 GUI widgets

Example controller:

from PySide6.QtCore import QObject, Signal


class BrokerController(QObject):
    quote_updated = Signal(dict)
    watchlist_updated = Signal(list)
    balances_updated = Signal(dict)
    positions_updated = Signal(list)
    order_status_updated = Signal(dict)
    broker_error = Signal(str)

    def __init__(self, market_data_service, account_service, order_service):
        super().__init__()
        self.market_data_service = market_data_service
        self.account_service = account_service
        self.order_service = order_service

    async def refresh_watchlist(self, symbols: list[str]) -> None:
        try:
            raw = await self.market_data_service.get_quotes(symbols)
            normalized = normalize_watchlist_quotes(raw)
            self.watchlist_updated.emit(normalized)
        except Exception as exc:
            self.broker_error.emit(str(exc))
18. CLI Smoke Test

Create:

scripts/tradier_stocks_smoke_test.py

It must test:

1. Load config.
2. Print selected environment.
3. Call /user/profile.
4. Resolve account ID.
5. Call balances.
6. Call positions.
7. Fetch quotes for SPY, QQQ, AAPL.
8. Fetch historical data for one stock or ETF.
9. Preview a tiny sandbox equity order.
10. Confirm live trading is disabled by default.

Example command:

TRADIER_ENV=sandbox python scripts/tradier_stocks_smoke_test.py

Expected output:

Tradier environment: sandbox
Profile: OK
Account ID: detected
Balances: OK
Positions: OK
Quotes: OK
Historical data: OK
Sandbox equity preview: OK
Live trading: disabled
Options endpoints: disabled
19. Testing Requirements

Use mocked HTTP responses first.

Minimum tests:

test_config_uses_sandbox_by_default
test_config_rejects_missing_token
test_client_sends_bearer_token
test_profile_401_raises_auth_error
test_profile_success_parses_account_id
test_quotes_supports_multiple_equity_symbols
test_market_data_rejects_empty_symbols
test_history_passes_symbol_interval_start_end
test_live_order_blocked_when_flag_false
test_option_order_class_rejected
test_multileg_order_rejected
test_quantity_over_max_rejected
test_market_order_rejected_by_default
test_limit_order_requires_price
test_order_preview_required_before_place
test_rate_limit_headers_are_recorded

Do not write tests that place real live orders.

20. README_TRADIER.md Must Include
- How to get Tradier API tokens.
- Sandbox vs live setup.
- Environment variable setup.
- Stocks/ETFs-only scope.
- Explicit note that options are not implemented.
- How to run the smoke test.
- Safety restrictions.
- How to enable live trading intentionally.
- Rate-limit behavior.
- PySide6 integration notes.
21. Deliverables

The coding agent must produce:

1. Tradier adapter package under stock_app/brokers/tradier/
2. Async HTTP client
3. Account/profile service
4. Stock/ETF market-data service
5. Stock/ETF order preview/place service
6. Safety gate for equity orders
7. Rate-limit handling
8. Sandbox smoke-test script
9. PySide6 controller integration stub
10. Unit tests
11. README_TRADIER.md
22. Implementation Order

Use this order:

Phase 1:
    config.py
    errors.py
    client.py
    account.py
    /user/profile smoke test

Phase 2:
    market_data.py
    stock/ETF quotes
    symbol search/lookup
    historical data

Phase 3:
    balances
    positions
    orders read-only

Phase 4:
    order preview
    safety.py
    sandbox-only stock/ETF order simulation

Phase 5:
    live-trading gates
    PySide6 controller
    dashboard status panel

Phase 6:
    streaming session prototype
    REST polling fallback
Prompt to Paste Directly Into Your Coding Agent
Implement a Tradier brokerage adapter for our new Python/Ubuntu/Wayland/PySide6 trading app.

This app is for STOCKS and ETFs only.

Use async Python only. Do not block the GUI thread. Do not use Tkinter, Streamlit, or blocking requests.

Create package:
stock_app/brokers/tradier/

Implement:
- config.py
- client.py
- errors.py
- rate_limit.py
- account.py
- market_data.py
- orders.py
- streaming.py
- safety.py
- models.py

Use environment variables:
TRADIER_ENV=sandbox|live
TRADIER_SANDBOX_TOKEN
TRADIER_LIVE_API_KEY
TRADIER_ACCOUNT_ID
TRADIER_ENABLE_LIVE_TRADING=false
TRADIER_ALLOWED_SYMBOLS=SPY,QQQ,IWM,DIA,AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA
TRADIER_MAX_SHARES_PER_ORDER=100
TRADIER_MAX_NOTIONAL_PER_ORDER=10000

Default to sandbox.

Base URLs:
sandbox REST: https://sandbox.tradier.com/v1
live REST: https://api.tradier.com/v1
live streaming: https://stream.tradier.com/v1

Authentication:
Authorization: Bearer <token>
Accept: application/json

Trading POST requests:
Content-Type: application/x-www-form-urlencoded

First implement and test:
GET /user/profile

Then implement:
GET /accounts/{account_id}/balances
GET /accounts/{account_id}/positions
GET /accounts/{account_id}/orders
GET /accounts/{account_id}/orders/{order_id}
GET /accounts/{account_id}/history
GET /accounts/{account_id}/gainloss
GET /markets/quotes
GET /markets/search
GET /markets/lookup
GET /markets/history
GET /markets/clock
GET /markets/calendar

Do NOT implement:
- options
- option chains
- expirations
- strikes
- Greeks
- implied volatility
- multileg option orders
- spreads
- naked option checks
- SPY-only assumptions

Order support:
- class=equity only
- buy
- sell
- buy_to_cover
- sell_short
- market
- limit
- stop
- stop_limit

Hard safety rules:
- Stocks and ETFs only.
- Reject all option-class orders.
- Reject all multi-leg orders.
- Reject unsupported symbols outside TRADIER_ALLOWED_SYMBOLS.
- Max shares per order from TRADIER_MAX_SHARES_PER_ORDER.
- Max notional per order from TRADIER_MAX_NOTIONAL_PER_ORDER.
- Require order preview before placement.
- Block live order placement unless TRADIER_ENABLE_LIVE_TRADING=true.
- Prefer limit orders.
- Reject market orders by default unless explicitly enabled later.
- Check balances/buying power before order placement.
- Immediately fetch order status after submission.

Implement rate-limit handling using:
X-Ratelimit-Allowed
X-Ratelimit-Used
X-Ratelimit-Available
X-Ratelimit-Expiry

Create:
scripts/tradier_stocks_smoke_test.py

Smoke test must verify:
- config loads
- profile works
- account ID resolves
- balances work
- positions work
- stock/ETF quotes work
- historical data works
- sandbox equity preview works
- live trading is disabled by default
- options endpoints are not implemented

Add pytest coverage for:
- config
- auth headers
- profile
- account ID resolution
- equity/ETF quotes
- historical data
- live-order blocking
- option-order rejection
- multileg-order rejection
- market-order rejection by default
- max quantity
- max notional
- preview-before-place
- rate-limit header parsing

Add README_TRADIER.md with setup, environment variables, stocks/ETFs-only scope, sandbox/live usage, smoke test, safety restrictions, and PySide6 integration notes.
