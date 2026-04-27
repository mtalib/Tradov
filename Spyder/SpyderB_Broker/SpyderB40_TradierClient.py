#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB40_TradierClient.py
Purpose: Tradier Brokerage REST API Client for Order Execution

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2026-02-25 Time: 14:00:00

Module Description:
    REST API client for Tradier Brokerage providing order execution, account
    management, option chain analysis, and real-time event streaming.

    KEY FEATURES:
    - Simple Bearer token authentication (stateless)
    - Commission-free equity/ETF options trading
    - Single-leg and multileg order support (spreads, Iron Condors)
    - Option chain with parsed Greeks (delta, gamma, theta, vega, IV)
    - Option symbol builder (OCC format) and parser
    - SSE streaming for real-time order fills and account events
    - Delta-based strike selection for strategy construction
    - Sandbox and live environment support
    - Async wrappers with rate limiting and circuit breaker

    API ENDPOINTS COVERED:
    - User profile and account information
    - Account balances and positions
    - Market quotes (real-time for account holders)
    - Order placement (single-leg: market, limit, stop)
    - Multileg orders (credit/debit spreads, Iron Condors)
    - Order management (status, modification, cancellation)
    - Option chains with Greeks
    - Option expirations and strikes
    - Account event streaming (SSE)
    - Trade history

Module Constants:
    TRADIER_LIVE_URL (str): Production API base URL
    TRADIER_SANDBOX_URL (str): Sandbox API base URL
    TRADIER_STREAM_URL (str): SSE streaming base URL
    DEFAULT_TIMEOUT (int): HTTP request timeout in seconds (default: 10)
    MAX_RETRIES (int): Maximum retry attempts for failed requests (default: 3)
    RETRY_BACKOFF (float): Exponential backoff factor for retries (default: 2.0)

Change Log:
    2026-03-16 (v3.0.0):
        - Added TradierMarketStream: WebSocket real-time market data streaming (ENH-01)
        - Added dynamic rate limit header parsing — RateLimitInfo dataclass (ENH-03)
        - Added get_rate_limit_info() for real-time rate limit monitoring (ENH-03)
        - Added OCO/OTO/OTOCO contingent order types (ENH-04)
        - Added missing REST endpoints: calendar, clock, gainloss, watchlists,
          timesales, symbol search, historical quotes (ENH-05)
        - Added order preview (dry-run) support for single-leg and multileg (ENH-06)
        - Fixed: all async methods use get_running_loop() — Python 3.10+ (ENH-07)
        - Added MarketEvent and RateLimitInfo dataclasses
        - TradierAccountStream (SSE) preserved; aliased for backward compatibility
    2026-02-25 (v2.0.0):
        - Added multileg order support (spreads, Iron Condors)
        - Added option symbol builder and parser utilities
        - Added Greeks parsing from option chain responses
        - Added delta-based strike selection
        - Added SSE streaming for account events (TradierAccountStream)
        - Added order modification endpoint
        - Added option strikes lookup
        - Added async wrappers for all new endpoints
        - Added convenience methods: place_iron_condor(), place_credit_spread()
        - Added OptionLeg, GreekData, AccountEvent data classes
    2025-11-18 (v1.0.0):
        - Initial implementation for Tradier migration
        - Simple Bearer token authentication
        - Core endpoints: account, orders, positions
        - Error handling with custom exceptions
        - Sandbox and live environment support

References:
    - Tradier API Documentation: https://docs.tradier.com/
    - Tradier Brokerage API: https://docs.tradier.com/brokerage-api/
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import functools
import os
import time
try:
    import orjson as json  # 3-10x faster JSON; drop-in compatible for loads/dumps
except ImportError:
    import json
import asyncio
import threading
from typing import Any
from collections.abc import Callable
from enum import Enum
from dataclasses import dataclass, field

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import sseclient
    HAS_SSE = True
except ImportError:
    HAS_SSE = False
    sseclient = None

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False
    websocket = None  # type: ignore[assignment]

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit
from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import tradier_breaker
from Spyder.SpyderU_Utilities.SpyderU44_ShutdownCoordinator import get_shutdown_coordinator
from Spyder.SpyderU_Utilities.SpyderU45_RetryWithBackoff import retry_async

# ==============================================================================
# CONSTANTS
# ==============================================================================
TRADIER_LIVE_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
TRADIER_STREAM_URL = "https://stream.tradier.com/v1"
TRADIER_WS_URL = "wss://ws.tradier.com/v1"
TRADIER_SANDBOX_WS_URL = "wss://sandbox-ws.tradier.com/v1"
DEFAULT_TIMEOUT = 30  # seconds (sandbox can be slow; 10 s was too tight)
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # exponential backoff factor
WS_PING_INTERVAL = 30  # seconds between WebSocket pings
WS_PING_TIMEOUT = 10   # seconds to wait for pong response
SESSION_TTL = 270.0    # session token refresh threshold (4.5 min; Tradier TTL is 5 min)

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class TradingEnvironment(Enum):
    """Tradier trading environment."""
    LIVE = "live"
    SANDBOX = "sandbox"
    PAPER = "paper"  # Alias for sandbox

class OrderSide(Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_OPEN = "buy_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_OPEN = "sell_to_open"
    SELL_TO_CLOSE = "sell_to_close"

class OrderType(Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderDuration(Enum):
    """Order time-in-force."""
    DAY = "day"
    GTC = "gtc"  # Good 'til canceled
    PRE = "pre"  # Pre-market
    POST = "post"  # After-hours

class OrderClass(Enum):
    """Security class."""
    EQUITY = "equity"
    OPTION = "option"
    MULTILEG = "multileg"
    COMBO = "combo"

# ==============================================================================
# CUSTOM EXCEPTIONS
# ==============================================================================
class TradierAPIError(Exception):
    """Base exception for Tradier API errors."""
    pass

class TradierAuthenticationError(TradierAPIError):
    """Authentication failed (invalid API key)."""
    pass

class TradierValidationError(TradierAPIError):
    """Request validation failed (4xx errors)."""
    pass

class TradierServerError(TradierAPIError):
    """Tradier server error (5xx errors)."""
    pass

class TradierRateLimitError(TradierAPIError):
    """Rate limit exceeded."""
    pass


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class OptionLeg:
    """
    Represents a single leg of a multileg option order.

    Attributes:
        option_symbol: OCC-format option symbol (e.g., SPY260220C00550000).
        side: Order side for this leg.
        quantity: Number of contracts for this leg.
    """
    option_symbol: str
    side: OrderSide
    quantity: int


@dataclass
class GreekData:
    """
    Parsed Greeks for an option contract.

    Attributes:
        symbol: Option symbol.
        underlying: Underlying symbol.
        strike: Strike price.
        expiration: Expiration date string.
        option_type: 'call' or 'put'.
        bid: Best bid price.
        ask: Best ask price.
        last: Last trade price.
        mid: Midpoint of bid/ask.
        volume: Trading volume.
        open_interest: Open interest.
        delta: Delta value.
        gamma: Gamma value.
        theta: Theta value (daily decay).
        vega: Vega value (per 1% IV change).
        rho: Rho value.
        iv: Implied volatility.
        in_the_money: Whether the option is ITM.
    """
    symbol: str = ""
    underlying: str = ""
    strike: float = 0.0
    expiration: str = ""
    option_type: str = ""  # "call" or "put"
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    mid: float = 0.0
    volume: int = 0
    open_interest: int = 0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    iv: float = 0.0
    in_the_money: bool = False

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


@dataclass
class AccountEvent:
    """
    Represents a real-time account event from Tradier SSE stream.

    Attributes:
        event_type: Type of event (e.g., 'order', 'trade').
        timestamp: Event timestamp.
        data: Raw event data dictionary.
        order_id: Associated order ID (if applicable).
        symbol: Associated symbol (if applicable).
        status: Order/fill status (if applicable).
    """
    event_type: str = ""
    timestamp: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    order_id: int | None = None
    symbol: str = ""
    status: str = ""


@dataclass
class RateLimitInfo:
    """
    Rate limit state captured from Tradier response headers.

    Tradier includes X-Ratelimit-* headers in every response.  This dataclass
    surfaces that data so Spyder's rate limiter (SpyderU40) can adapt
    dynamically instead of relying on a static estimate.

    Attributes:
        allowed: Total calls allowed in the current window (X-Ratelimit-Allowed).
        used: Calls consumed so far (X-Ratelimit-Used).
        available: Remaining calls (X-Ratelimit-Available).
        expiry: Window expiry as Unix epoch milliseconds (X-Ratelimit-Expiry).
        timestamp: Local time.time() when this snapshot was captured.
    """
    allowed: int = 0
    used: int = 0
    available: int = 0
    expiry: int = 0
    timestamp: float = 0.0

    @property
    def remaining_pct(self) -> float:
        """Percentage of rate limit remaining (0.0–100.0)."""
        if self.allowed <= 0:
            return 0.0
        return round((self.available / self.allowed) * 100, 1)


@dataclass
class MarketEvent:
    """
    Structured market event from Tradier WebSocket stream.

    Populated by TradierMarketStream from incoming WebSocket JSON messages.

    Attributes:
        event_type: Event category: "trade", "quote", or "summary".
        symbol: Ticker symbol (equity or OCC option format).
        timestamp: Event timestamp string from Tradier.
        bid: Best bid price (quote events).
        ask: Best ask price (quote events).
        last: Last trade price.
        size: Trade size (trade events).
        volume: Cumulative session volume.
        data: Raw event payload for fields not captured above.
    """
    event_type: str = ""
    symbol: str = ""
    timestamp: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    size: int = 0
    volume: int = 0
    data: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# OPTION SYMBOL UTILITIES
# ==============================================================================
def build_option_symbol(
    underlying: str,
    expiration: str,
    option_type: str,
    strike: float,
) -> str:
    """
    Build a Tradier/OCC-format option symbol.

    The OCC (Options Clearing Corporation) standard format is:
        {underlying}{YYMMDD}{C|P}{strike*1000 zero-padded to 8 digits}

    Example:
        >>> build_option_symbol("SPY", "2026-02-20", "C", 550.00)
        'SPY260220C00550000'
        >>> build_option_symbol("SPY", "260220", "P", 545.50)
        'SPY260220P00545500'

    Args:
        underlying: Underlying ticker (e.g., "SPY").
        expiration: Expiration date as "YYYY-MM-DD" or "YYMMDD".
        option_type: "C" or "P" (or "call"/"put" — first char used).
        strike: Strike price as float.

    Returns:
        OCC-format option symbol string.

    Raises:
        ValueError: If option_type is not recognized.
    """
    # P1-6: enforce SPY options strike tick (0.05). Avoid generating symbols
    # that live exchange validation will reject.
    strike_steps = strike * 20.0
    if abs(round(strike_steps) - strike_steps) > 1e-9:
        raise ValueError(
            f"Invalid strike {strike:.4f}: must be in 0.05 increments"
        )

    # Normalize option type
    opt_char = option_type[0].upper()
    if opt_char not in ("C", "P"):
        raise ValueError(f"option_type must be 'C'/'call' or 'P'/'put', got '{option_type}'")

    # Normalize expiration to YYMMDD
    if "-" in expiration:
        # YYYY-MM-DD → YYMMDD
        parts = expiration.split("-")
        exp_str = parts[0][2:] + parts[1] + parts[2]
    elif len(expiration) == 6:
        exp_str = expiration
    else:
        raise ValueError(f"expiration must be 'YYYY-MM-DD' or 'YYMMDD', got '{expiration}'")

    # Strike price → 8-digit integer (price * 1000)
    strike_int = int(round(strike * 1000))

    return f"{underlying}{exp_str}{opt_char}{strike_int:08d}"


def parse_option_symbol(symbol: str) -> dict[str, Any]:
    """
    Parse a Tradier/OCC-format option symbol into components.

    Example:
        >>> parse_option_symbol("SPY260220C00550000")
        {'underlying': 'SPY', 'expiration': '260220', 'expiration_date': '2026-02-20',
         'option_type': 'C', 'strike': 550.0, 'symbol': 'SPY260220C00550000'}

    Args:
        symbol: OCC-format option symbol.

    Returns:
        Dictionary with parsed components.

    Raises:
        ValueError: If symbol cannot be parsed.
    """
    # Find where the date portion starts (first digit after ticker)
    idx = 0
    while idx < len(symbol) and not symbol[idx].isdigit():
        idx += 1

    if idx == 0 or idx + 15 > len(symbol):
        raise ValueError(f"Cannot parse option symbol: '{symbol}'")

    underlying = symbol[:idx]
    exp_str = symbol[idx:idx + 6]
    opt_type = symbol[idx + 6]
    strike = int(symbol[idx + 7:idx + 15]) / 1000.0

    # Convert YYMMDD → YYYY-MM-DD
    yy = int(exp_str[:2])
    mm = exp_str[2:4]
    dd = exp_str[4:6]
    yyyy = 2000 + yy if yy < 80 else 1900 + yy
    exp_date = f"{yyyy}-{mm}-{dd}"

    return {
        "underlying": underlying,
        "expiration": exp_str,
        "expiration_date": exp_date,
        "option_type": opt_type,
        "strike": strike,
        "symbol": symbol,
    }


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradierClient:
    """
    Tradier Brokerage REST API Client.

    This client provides simple, stateless access to Tradier's trading API.
    No OAuth, no session management, no complexity - just HTTP requests with
    a Bearer token.

    Attributes:
        api_key (str): Tradier API access token
        account_id (str): Tradier account ID
        environment (TradingEnvironment): Live or sandbox environment
        base_url (str): API base URL (determined by environment)
        timeout (int): HTTP request timeout in seconds

    Example:
        >>> client = TradierClient(
        ...     api_key="your_access_token",
        ...     account_id="your_account_id",
        ...     environment=TradingEnvironment.SANDBOX
        ... )
        >>> profile = client.get_user_profile()
        >>> print(profile["profile"]["account"]["account_number"])
    """

    def __init__(
        self,
        api_key: str,
        account_id: str,
        environment: TradingEnvironment = TradingEnvironment.SANDBOX,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize Tradier API client.

        Args:
            api_key: Tradier API access token (Bearer token)
            account_id: Tradier account ID
            environment: Trading environment (live or sandbox)
            timeout: HTTP request timeout in seconds
        """
        self.api_key = api_key
        self.account_id = account_id
        self.environment = environment
        self.timeout = timeout

        # Set base URL based on environment
        if environment in (TradingEnvironment.SANDBOX, TradingEnvironment.PAPER):
            self.base_url = TRADIER_SANDBOX_URL
        else:
            self.base_url = TRADIER_LIVE_URL

        # Create session with connection pooling and retry logic
        self.session = self._create_session()

        # Rate limit snapshot updated after every successful API call (ENH-03)
        self._last_rate_limit: RateLimitInfo | None = None

        logger.debug("TradierClient initialized for %s environment", environment.value)

    def _create_session(self) -> requests.Session:
        """
        Create requests session with connection pooling and retry logic.

        Returns:
            Configured requests.Session object
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"]
        )

        # Mount retry adapter
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set default headers
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        })

        return session

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make HTTP request to Tradier API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/user/profile")
            params: Query parameters
            data: Form data (for POST/PUT)
            json_data: JSON data (for POST/PUT)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            TradierAuthenticationError: Authentication failed
            TradierValidationError: Request validation failed
            TradierServerError: Server error
            TradierRateLimitError: Rate limit exceeded
            TradierAPIError: Other API errors
        """
        url = f"{self.base_url}{endpoint}"

        try:
            logger.debug("Making %s request to %s", method, endpoint)

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                timeout=self.timeout
            )

            # Handle different status codes
            if response.status_code == 200:
                # ENH-03: Parse rate limit headers on every successful response
                try:
                    h = response.headers
                    rl = RateLimitInfo(
                        allowed=int(h.get("X-Ratelimit-Allowed", 0)),
                        used=int(h.get("X-Ratelimit-Used", 0)),
                        available=int(h.get("X-Ratelimit-Available", 0)),
                        expiry=int(h.get("X-Ratelimit-Expiry", 0)),
                        timestamp=time.time(),
                    )
                    self._last_rate_limit = rl
                    if rl.available <= 3:
                        logger.error(
                            f"Rate limit critical: only {rl.available} requests remaining "
                            f"(window expires epoch={rl.expiry})"
                        )
                    elif rl.available <= 10:
                        logger.warning(
                            f"Rate limit low: {rl.available}/{rl.allowed} remaining "
                            f"(window expires epoch={rl.expiry})"
                        )
                except (ValueError, TypeError):
                    pass  # Headers absent or malformed — not fatal
                return response.json()

            elif response.status_code == 401 or response.status_code == 403:
                error_msg = f"Authentication failed: {response.text}"
                # Log at WARNING rather than ERROR — callers receive the exception
                # and are expected to handle it; ERROR-level floods the GUI system log.
                logger.warning(error_msg)
                raise TradierAuthenticationError(error_msg)

            elif response.status_code == 400 or response.status_code == 422:
                error_msg = f"Validation error: {response.text}"
                logger.error(error_msg)
                raise TradierValidationError(error_msg)

            elif response.status_code == 429:
                error_msg = f"Rate limit exceeded: {response.text}"
                logger.warning(error_msg)
                raise TradierRateLimitError(error_msg)

            elif response.status_code >= 500:
                error_msg = f"Server error ({response.status_code}): {response.text}"
                logger.error(error_msg)
                raise TradierServerError(error_msg)

            else:
                error_msg = f"API error ({response.status_code}): {response.text}"
                logger.error(error_msg)
                raise TradierAPIError(error_msg)

        except requests.exceptions.Timeout:
            error_msg = f"Request timeout after {self.timeout}s: {endpoint}"
            logger.warning(error_msg)  # transient; full traceback is noise
            raise TradierAPIError(error_msg)  # noqa: B904

        except requests.exceptions.ConnectionError as e:
            # Includes ReadTimeoutError wrapped by urllib3 after max retries.
            # Log as warning — these are transient network conditions on sandbox.
            detail = str(e).strip()
            if not detail:
                detail = "request failed"
            else:
                detail = detail.splitlines()[0]
            error_msg = f"Connection error: {detail}"
            logger.warning(error_msg)
            raise TradierAPIError(error_msg)  # noqa: B904

        except (TradierAuthenticationError, TradierValidationError,
                TradierRateLimitError, TradierServerError, TradierAPIError):
            raise  # Re-raise Tradier-specific errors without wrapping

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise TradierAPIError(error_msg)  # noqa: B904

    def get_rate_limit_info(self) -> RateLimitInfo | None:
        """
        Return the most recent rate limit snapshot from Tradier headers.

        Updated automatically after every successful API call.  Callers
        (SpyderU40_RateLimiter, dashboard widgets) can query this to adapt
        request pacing dynamically instead of relying on a static estimate.

        Returns:
            RateLimitInfo snapshot, or None if no successful call has been made yet.

        Example:
            >>> info = client.get_rate_limit_info()
            >>> if info and info.remaining_pct < 20:
            ...     logger.warning(f"Only {info.available} Tradier calls left")
        """
        return self._last_rate_limit

    # ==========================================================================
    # USER & ACCOUNT ENDPOINTS
    # ==========================================================================

    def get_user_profile(self) -> dict[str, Any]:
        """
        Get user profile information.

        Returns:
            User profile data including account details

        Example:
            >>> profile = client.get_user_profile()
            >>> print(profile["profile"]["name"])
        """
        logger.debug("Fetching user profile")
        return self._make_request("GET", "/user/profile")

    def get_account_balances(self) -> dict[str, Any]:
        """
        Get account balances and buying power.

        Returns:
            Account balance data

        Example:
            >>> balances = client.get_account_balances()
            >>> print(balances["balances"]["total_equity"])
        """
        logger.debug("Fetching balances for account %s", self.account_id)
        return self._make_request("GET", f"/accounts/{self.account_id}/balances")

    def get_positions(self) -> dict[str, Any]:
        """
        Get current positions.

        Returns:
            List of current positions

        Example:
            >>> positions = client.get_positions()
            >>> for pos in positions["positions"]["position"]:
            ...     print(f"{pos['symbol']}: {pos['quantity']} shares")
        """
        logger.info("Fetching positions for account %s", self.account_id)
        return self._make_request("GET", f"/accounts/{self.account_id}/positions")

    def get_history(self, limit: int = 100) -> dict[str, Any]:
        """
        Get trade history.

        Args:
            limit: Maximum number of events to return

        Returns:
            Trade history events
        """
        logger.info("Fetching history for account %s", self.account_id)
        return self._make_request(
            "GET",
            f"/accounts/{self.account_id}/history",
            params={"limit": limit}
        )

    def get_gainloss(
        self,
        page: int | None = None,
        limit: int | None = None,
        sort_by: str | None = None,
        sort_direction: str | None = None,
        start: str | None = None,
        end: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """
        Get realized gain/loss for closed positions.

        Useful for tax reporting, performance attribution, and strategy P&L analysis.

        Args:
            page: Page number for pagination (1-based).
            limit: Records per page (max 100).
            sort_by: Sort field: "openDate", "closeDate", "instrument" etc.
            sort_direction: "asc" or "desc".
            start: Filter from date (YYYY-MM-DD).
            end:   Filter to date (YYYY-MM-DD).
            symbol: Filter by symbol.

        Returns:
            Gain/loss data with closed position records.

        Example:
            >>> gl = client.get_gainloss(start="2026-01-01", end="2026-03-16")
            >>> for record in gl.get("gainloss", {}).get("closed_position", []):
            ...     print(f"{record['symbol']}: ${record['gain_loss']:.2f}")
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if limit is not None:
            params["limit"] = limit
        if sort_by:
            params["sortBy"] = sort_by
        if sort_direction:
            params["sort"] = sort_direction
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if symbol:
            params["symbol"] = symbol

        logger.info("Fetching gain/loss for account %s", self.account_id)
        return self._make_request(
            "GET",
            f"/accounts/{self.account_id}/gainloss",
            params=params,
        )

    def get_watchlists(self) -> dict[str, Any]:
        """
        Get all watchlists for the current user.

        Returns:
            Watchlist data with names, IDs, and symbol lists.

        Example:
            >>> wls = client.get_watchlists()
            >>> for wl in wls.get("watchlists", {}).get("watchlist", []):
            ...     print(wl["name"], wl["id"])
        """
        logger.debug("Fetching watchlists")
        return self._make_request("GET", "/watchlists")

    def add_to_watchlist(self, watchlist_id: str, symbols: list[str]) -> dict[str, Any]:
        """
        Add symbols to an existing watchlist.

        Args:
            watchlist_id: Watchlist ID (from get_watchlists()).
            symbols: List of symbols to add.

        Returns:
            Updated watchlist data.

        Raises:
            ValueError: If symbols list is empty.

        Example:
            >>> import client.add_to_watchlist("default", ["SPY", "QQQ"])
        """
        if not symbols:
            raise ValueError("symbols list must not be empty")
        logger.info("Adding %s to watchlist %s", symbols, watchlist_id)
        return self._make_request(
            "POST",
            f"/watchlists/{watchlist_id}/symbols",
            data={"symbols": ",".join(symbols)},
        )

    # ==========================================================================
    # ORDER ENDPOINTS
    # ==========================================================================

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        duration: OrderDuration = OrderDuration.DAY,
        limit_price: float | None = None,
        stop_price: float | None = None,
        order_class: OrderClass = OrderClass.EQUITY,
        tag: str | None = None,  # P0-9: idempotency key (≤24 h dedup by Tradier)
    ) -> dict[str, Any]:
        """
        Place an order.

        Args:
            symbol: Security symbol (e.g., "SPY")
            side: Order side (buy/sell)
            quantity: Number of shares/contracts
            order_type: Order type (market, limit, stop)
            duration: Time-in-force (day, gtc)
            limit_price: Limit price (required for limit orders)
            stop_price: Stop price (required for stop orders)
            order_class: Security class (equity, option)

        Returns:
            Order response with order ID

        Example:
            >>> # Market order
            >>> order = client.place_order(
            ...     symbol="SPY",
            ...     side=OrderSide.BUY,
            ...     quantity=10,
            ...     order_type=OrderType.MARKET
            ... )
            >>> print(order["order"]["id"])
        """
        logger.info("Placing %s order: %s %s %s", order_type.value, side.value, quantity, symbol)

        # Build order payload
        payload = {
            "class": order_class.value,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "type": order_type.value,
            "duration": duration.value
        }

        # Add limit price if specified
        if limit_price is not None:
            payload["price"] = limit_price

        # Add stop price if specified
        if stop_price is not None:
            payload["stop"] = stop_price

        # P0-9: Tradier idempotency tag — prevents duplicate fills on retry.
        if tag is not None:
            payload["tag"] = tag

        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload
        )

    def get_order(self, order_id: int) -> dict[str, Any]:
        """
        Get order details by ID.

        Args:
            order_id: Order ID

        Returns:
            Order details
        """
        logger.info("Fetching order %s", order_id)
        return self._make_request("GET", f"/accounts/{self.account_id}/orders/{order_id}")

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if the cancellation was accepted by the API, False otherwise.

        Note (C7 v18): BrokerProtocol declares ``cancel_order -> bool``.  The
        raw Tradier response is a JSON dict; we coerce it to bool here so the
        return type matches the protocol contract.  Call sites that previously
        relied on the raw dict should use ``_cancel_order_raw()`` instead.
        """
        logger.info("Canceling order %s", order_id)
        raw: dict[str, Any] = self._make_request(
            "DELETE", f"/accounts/{self.account_id}/orders/{order_id}"
        )
        # Tradier returns {"order": {"id": <int>, "status": "ok"}} on success.
        return bool((raw or {}).get("order", {}).get("id"))

    def get_orders(self) -> dict[str, Any]:
        """
        Get all orders (open and recent closed).

        Returns:
            List of orders
        """
        logger.info("Fetching all orders for account %s", self.account_id)
        return self._make_request("GET", f"/accounts/{self.account_id}/orders")

    def close_position(
        self,
        symbol: str,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position",
        force: bool = False,
    ) -> dict[str, Any]:
        """Close an existing position by placing a market closing order.

        Looks up the current position quantity from Tradier, then submits a
        market order on the opposite side to flatten the position.

        Args:
            symbol: Symbol of the position to close (equity or OCC option symbol).
            urgency: Urgency hint for logging ("IMMEDIATE", "EOD", etc.).
            reason: Audit-trail reason string logged with every close attempt.
            force: When True, submit a qty-1 closing order even if no position
                   is found via get_positions() (safety sweep for stale state).

        Returns:
            Order response dict from place_order(), or ``{}`` if no position
            was found and *force* is False.

        Raises:
            TradierAPIError: If the order submission fails.
        """
        logger.warning(
            "close_position: symbol=%s urgency=%s reason=%s force=%s",
            symbol, urgency, reason, force,
        )

        # ── 1. Look up live position quantity ────────────────────────────────
        quantity: int = 0
        try:
            pos_resp = self.get_positions()
            raw = (pos_resp.get("positions") or {}).get("position", [])
            if isinstance(raw, dict):
                raw = [raw]  # Tradier returns a dict when only one position exists
            for p in raw:
                if p.get("symbol") == symbol:
                    quantity = int(p.get("quantity", 0))
                    break
        except Exception as exc:
            logger.error("close_position: get_positions() failed for %s: %s", symbol, exc)
            if not force:
                return {}

        if quantity == 0 and not force:
            logger.info("close_position: no open position found for %s — skipping", symbol)
            return {}

        # ── 2. Determine close side and order class ───────────────────────────
        # OCC option symbols are 21 characters (e.g. SPY260220C00550000);
        # equity tickers are ≤ 5 characters.
        is_option: bool = len(symbol) > 6
        close_qty: int = abs(quantity) if quantity != 0 else 1  # force=True fallback

        if quantity >= 0:
            side = OrderSide.SELL_TO_CLOSE if is_option else OrderSide.SELL
        else:
            side = OrderSide.BUY_TO_CLOSE if is_option else OrderSide.BUY

        order_class = OrderClass.OPTION if is_option else OrderClass.EQUITY

        logger.warning(
            "Closing position: symbol=%s qty=%s side=%s urgency=%s reason=%s",
            symbol, close_qty, side.value, urgency, reason,
        )

        return self.place_order(
            symbol=symbol,
            side=side,
            quantity=close_qty,
            order_type=OrderType.MARKET,
            duration=OrderDuration.DAY,
            order_class=order_class,
        )

    def close_position_verified(
        self,
        symbol: str,
        timeout_s: float = 10.0,
        urgency: str = "IMMEDIATE",
        reason: str = "close_position_verified",
    ) -> dict[str, Any]:
        """A23 (v14): submit close and poll ``get_order`` until filled or timeout.

        Tradier market-close orders usually fill in well under a second, but
        the shutdown path cannot trust a bare ``close_position`` ack — that
        only confirms the broker received the order, not that the position
        is actually flat. Callers are expected to fire ``KILL_SWITCH`` when
        this returns ``status != "verified"``.
        """
        response = self.close_position(symbol, urgency=urgency, reason=reason)
        if not response:
            return {
                "status": "unverified",
                "order": response,
                "reason": "no_position_or_submit_failed",
            }
        oid = (response.get("order") or {}).get("id")
        if oid is None:
            return {
                "status": "unverified",
                "order": response,
                "reason": "no_order_id_returned",
            }

        import time as _time
        deadline = _time.monotonic() + max(0.0, float(timeout_s))
        last_status: str | None = None
        while _time.monotonic() < deadline:
            try:
                order_resp = self.get_order(int(oid))
                last_status = (order_resp.get("order") or {}).get("status")
            except Exception as exc:
                logger.warning(
                    "close_position_verified: get_order failed for %s: %s", oid, exc
                )
                last_status = None

            if last_status == "filled":
                return {
                    "status": "verified",
                    "order": response,
                    "fill": order_resp,
                }
            if last_status in ("canceled", "cancelled", "rejected", "expired"):
                return {
                    "status": "unverified",
                    "order": response,
                    "reason": f"terminal_non_fill:{last_status}",
                }
            _time.sleep(0.25)

        return {
            "status": "unverified",
            "order": response,
            "reason": f"timeout_last_status:{last_status}",
        }

    # ==========================================================================
    # ORDER PREVIEW (DRY-RUN)
    # ==========================================================================

    def preview_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        duration: OrderDuration = OrderDuration.DAY,
        limit_price: float | None = None,
        stop_price: float | None = None,
        order_class: OrderClass = OrderClass.EQUITY,
    ) -> dict[str, Any]:
        """
        Preview a single-leg order without actually placing it.

        Tradier validates the order and returns estimated cost, commission,
        and margin impact.  No order is submitted.  Use this in SpyderE_Risk
        to pre-validate orders before execution.

        Args:
            symbol: Security symbol.
            side: Order side (buy/sell).
            quantity: Number of shares/contracts.
            order_type: Order type.
            duration: Time-in-force.
            limit_price: Limit price (required for limit orders).
            stop_price: Stop price (required for stop orders).
            order_class: Security class.

        Returns:
            Preview response: estimated_cost, commission, margin_change,
            and validation status.

        Example:
            >>> preview = client.preview_order(
            ...     "SPY", OrderSide.BUY, 10, OrderType.LIMIT, limit_price=560.00
            ... )
            >>> print(preview["order"]["status"])  # "ok" or error details
        """
        logger.debug("Previewing order: %s %s %s", side.value, quantity, symbol)
        payload: dict[str, Any] = {
            "class": order_class.value,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "type": order_type.value,
            "duration": duration.value,
            "preview": "true",
        }
        if limit_price is not None:
            payload["price"] = limit_price
        if stop_price is not None:
            payload["stop"] = stop_price

        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    def preview_multileg_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        order_type: str = "credit",
        duration: OrderDuration = OrderDuration.DAY,
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Preview a multileg option order without placing it.

        Args:
            symbol: Underlying symbol.
            legs: Option legs (OptionLeg objects).
            order_type: 'market', 'credit', 'debit', or 'even'.
            duration: Time-in-force.
            price: Net limit price.

        Returns:
            Preview response with estimated cost/commission.

        Raises:
            ValueError: If legs are empty.

        Example:
            >>> preview = client.preview_multileg_order("SPY", legs, "credit", price=2.00)
        """
        if not legs:
            raise ValueError("At least one OptionLeg is required")
        logger.debug("Previewing multileg order: %s %s legs", symbol, len(legs))
        payload: dict[str, Any] = {
            "class": "multileg",
            "symbol": symbol,
            "type": order_type,
            "duration": duration.value,
            "preview": "true",
        }
        if price is not None:
            payload["price"] = str(price)
        for i, leg in enumerate(legs):
            payload[f"option_symbol[{i}]"] = leg.option_symbol
            payload[f"side[{i}]"] = leg.side.value
            payload[f"quantity[{i}]"] = str(leg.quantity)

        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    def preview_iron_condor(
        self,
        symbol: str,
        expiration: str,
        put_buy_strike: float,
        put_sell_strike: float,
        call_sell_strike: float,
        call_buy_strike: float,
        quantity: int = 1,
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Preview an Iron Condor order (convenience wrapper for preview_multileg_order).

        Args:
            symbol: Underlying symbol.
            expiration: Option expiration (YYYY-MM-DD).
            put_buy_strike: Long put strike (protection).
            put_sell_strike: Short put strike.
            call_sell_strike: Short call strike.
            call_buy_strike: Long call strike (protection).
            quantity: Contracts per leg.
            price: Net credit limit price.

        Returns:
            Preview response with estimated commission and cost.
        """
        legs = [
            OptionLeg(build_option_symbol(symbol, expiration, "P", put_buy_strike),
                      OrderSide.BUY_TO_OPEN, quantity),
            OptionLeg(build_option_symbol(symbol, expiration, "P", put_sell_strike),
                      OrderSide.SELL_TO_OPEN, quantity),
            OptionLeg(build_option_symbol(symbol, expiration, "C", call_sell_strike),
                      OrderSide.SELL_TO_OPEN, quantity),
            OptionLeg(build_option_symbol(symbol, expiration, "C", call_buy_strike),
                      OrderSide.BUY_TO_OPEN, quantity),
        ]
        return self.preview_multileg_order(symbol, legs, "credit", price=price)

    def preview_credit_spread(
        self,
        symbol: str,
        expiration: str,
        sell_strike: float,
        buy_strike: float,
        option_type: str = "P",
        quantity: int = 1,
        price: float | None = None,
    ) -> dict[str, Any]:
        """
        Preview a credit spread order.

        Args:
            symbol: Underlying symbol.
            expiration: Option expiration (YYYY-MM-DD).
            sell_strike: Short strike.
            buy_strike: Long strike.
            option_type: "P" for bull put, "C" for bear call.
            quantity: Number of contracts.
            price: Net credit limit price.

        Returns:
            Preview response with estimated commission and cost.
        """
        legs = [
            OptionLeg(build_option_symbol(symbol, expiration, option_type, sell_strike),
                      OrderSide.SELL_TO_OPEN, quantity),
            OptionLeg(build_option_symbol(symbol, expiration, option_type, buy_strike),
                      OrderSide.BUY_TO_OPEN, quantity),
        ]
        return self.preview_multileg_order(symbol, legs, "credit", price=price)

    # ==========================================================================
    # MARKET DATA ENDPOINTS
    # ==========================================================================

    def get_quotes(self, symbols: list[str]) -> dict[str, Any]:
        """
        Get real-time quotes for symbols.

        Note: Tradier provides delayed data to non-account holders.
        Account holders get real-time quotes at no additional cost.

        Args:
            symbols: List of symbols (e.g., ["SPY", "QQQ"])

        Returns:
            Quote data

        Example:
            >>> quotes = client.get_quotes(["SPY"])
            >>> spy_quote = quotes["quotes"]["quote"]
            >>> print(f"SPY: ${spy_quote['last']}")
        """
        symbols_str = ",".join(symbols)
        logger.debug("Fetching quotes for %s", symbols_str)
        return self._make_request("GET", "/markets/quotes", params={"symbols": symbols_str})

    def get_option_chain(self, symbol: str, expiration: str) -> dict[str, Any]:
        """
        Get option chain for a symbol.

        Args:
            symbol: Underlying symbol (e.g., "SPY")
            expiration: Expiration date (YYYY-MM-DD)

        Returns:
            Option chain data
        """
        logger.debug("Fetching option chain for %s expiring %s", symbol, expiration)
        return self._make_request(
            "GET",
            "/markets/options/chains",
            params={"symbol": symbol, "expiration": expiration}
        )

    def get_option_expirations(self, symbol: str) -> dict[str, Any]:
        """
        Get available option expiration dates.

        Args:
            symbol: Underlying symbol (e.g., "SPY")

        Returns:
            List of expiration dates
        """
        logger.debug("Fetching option expirations for %s", symbol)
        return self._make_request("GET", "/markets/options/expirations", params={"symbol": symbol})

    def get_option_strikes(
        self,
        symbol: str,
        expiration: str,
    ) -> dict[str, Any]:
        """
        Get available strikes for an underlying on a specific expiration.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            expiration: Expiration date (YYYY-MM-DD).

        Returns:
            Response with available strikes.

        Example:
            >>> strikes = client.get_option_strikes("SPY", "2026-03-20")
            >>> print(strikes["strikes"]["strike"])
        """
        logger.debug("Fetching option strikes for %s on %s", symbol, expiration)
        return self._make_request(
            "GET",
            "/markets/options/strikes",
            params={"symbol": symbol, "expiration": expiration},
        )

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list[GreekData]:
        """
        Get option chain with parsed Greeks as structured GreekData objects.

        Tradier returns Greeks inline in the option chain response. This method
        parses them into GreekData dataclass instances for easy programmatic access.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            expiration: Expiration date (YYYY-MM-DD).
            option_type: Filter by "call" or "put". None returns both.

        Returns:
            List of GreekData objects with Greeks, pricing, and metadata.

        Example:
            >>> greeks = client.get_option_chain_with_greeks("SPY", "2026-03-20")
            >>> for g in greeks:
            ...     if abs(g.delta) > 0.3:
            ...         print(f"{g.symbol}: Δ={g.delta:.3f} θ={g.theta:.3f}")
        """
        params = {"symbol": symbol, "expiration": expiration, "greeks": "true"}
        if option_type:
            params["option_type"] = option_type.lower()

        logger.debug("Fetching option chain with greeks for %s exp %s", symbol, expiration)
        response = self._make_request("GET", "/markets/options/chains", params=params)

        return self._parse_greeks_from_chain(response, symbol)

    @staticmethod
    def _parse_greeks_from_chain(
        response: dict[str, Any],
        underlying: str,
    ) -> list[GreekData]:
        """
        Parse Greeks from Tradier option chain response.

        Args:
            response: Raw Tradier API response.
            underlying: Underlying symbol for tagging.

        Returns:
            List of GreekData objects.
        """
        result = []
        options = response.get("options", {})
        if not options:
            return result

        option_list = options.get("option", [])
        if isinstance(option_list, dict):
            option_list = [option_list]

        for opt in option_list:
            greeks_data = opt.get("greeks", {}) or {}
            bid = opt.get("bid", 0.0) or 0.0
            ask = opt.get("ask", 0.0) or 0.0
            mid = round((bid + ask) / 2, 4) if (bid + ask) > 0 else 0.0

            gd = GreekData(
                symbol=opt.get("symbol", ""),
                underlying=underlying,
                strike=opt.get("strike", 0.0),
                expiration=opt.get("expiration_date", ""),
                option_type=opt.get("option_type", ""),
                bid=bid,
                ask=ask,
                last=opt.get("last", 0.0) or 0.0,
                mid=mid,
                volume=opt.get("volume", 0) or 0,
                open_interest=opt.get("open_interest", 0) or 0,
                delta=greeks_data.get("delta", 0.0) or 0.0,
                gamma=greeks_data.get("gamma", 0.0) or 0.0,
                theta=greeks_data.get("theta", 0.0) or 0.0,
                vega=greeks_data.get("vega", 0.0) or 0.0,
                rho=greeks_data.get("rho", 0.0) or 0.0,
                iv=greeks_data.get("mid_iv", 0.0) or greeks_data.get("smv_vol", 0.0) or 0.0,
                in_the_money=(opt.get("in_the_money") is True),
            )
            result.append(gd)

        return result

    def find_options_by_delta(
        self,
        symbol: str,
        expiration: str,
        target_delta: float,
        option_type: str = "call",
        tolerance: float = 0.05,
    ) -> list[GreekData]:
        """
        Find option contracts closest to a target delta.

        Useful for delta-based strike selection in strategies like
        Iron Condors (e.g., 0.16 delta short strikes).

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).
            target_delta: Target absolute delta value (e.g., 0.16).
            option_type: "call" or "put".
            tolerance: Acceptable delta deviation (default ±0.05).

        Returns:
            List of GreekData sorted by proximity to target delta.

        Example:
            >>> # Find ~16-delta puts for Iron Condor short put
            >>> puts = client.find_options_by_delta(
            ...     "SPY", "2026-03-20", target_delta=0.16,
            ...     option_type="put"
            ... )
        """
        chain = self.get_option_chain_with_greeks(
            symbol, expiration, option_type=option_type
        )

        # Filter by delta proximity
        matches = []
        for g in chain:
            delta_diff = abs(abs(g.delta) - target_delta)
            if delta_diff <= tolerance:
                matches.append((delta_diff, g))

        # Sort by closest to target
        matches.sort(key=lambda x: x[0])
        return [g for _, g in matches]

    def get_market_calendar(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """
        Get the trading calendar for a given month.

        Returns trading days, market open/close times, and holiday markers.
        Used by SpyderA04_Scheduler and SpyderU10_TradingCalendar.

        Args:
            month: Calendar month (1-12).  Defaults to current month.
            year:  Calendar year (e.g., 2026).  Defaults to current year.

        Returns:
            Calendar data with market open/close flags per day.

        Example:
            >>> cal = client.get_market_calendar(month=3, year=2026)
            >>> for day in cal["calendar"]["days"]["day"]:
            ...     print(day["date"], day["status"])
        """
        params: dict[str, Any] = {}
        if month is not None:
            params["month"] = month
        if year is not None:
            params["year"] = year
        logger.debug("Fetching market calendar %s/%s", year, month)
        return self._make_request("GET", "/markets/calendar", params=params)

    def get_market_clock(self) -> dict[str, Any]:
        """
        Get the current market state (pre-market, open, post-market, closed).

        Returns the current time relative to market hours, next open/close times,
        and whether the market is currently open.

        Returns:
            Market clock data.

        Example:
            >>> clock = client.get_market_clock()
            >>> print(clock["clock"]["state"])  # "open" | "closed" | "premarket" | "postmarket"
        """
        logger.debug("Fetching market clock")
        return self._make_request("GET", "/markets/clock")

    def get_time_sales(
        self,
        symbol: str,
        interval: str = "1min",
        start: str | None = None,
        end: str | None = None,
        session_filter: str = "open",
    ) -> dict[str, Any]:
        """
        Get tick-level time and sales data (OHLCV bars).

        Args:
            symbol: Symbol (e.g., "SPY").
            interval: Bar interval: "tick", "1min", "5min", "15min" etc.
            start: Start datetime (YYYY-MM-DD HH:MM).
            end:   End datetime (YYYY-MM-DD HH:MM).
            session_filter: "all" or "open" (regular session only).

        Returns:
            Time and sales data.

        Example:
            >>> ts = client.get_time_sales("SPY", interval="1min", start="2026-03-16 09:30")
        """
        params: dict[str, Any] = {"symbol": symbol, "interval": interval,
                                   "session_filter": session_filter}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        logger.debug("Fetching time sales for %s (%s)", symbol, interval)
        return self._make_request("GET", "/markets/timesales", params=params)

    def search_symbols(self, query: str, indexes: bool = False) -> dict[str, Any]:
        """
        Search for symbols by company name or ticker prefix.

        Args:
            query: Search string (e.g., "Apple" or "SPY").
            indexes: Include index symbols in results.

        Returns:
            Search results with symbol, exchange, and description.

        Example:
            >>> results = client.search_symbols("SPDR")
            >>> for s in results["securities"]["security"]:
            ...     print(s["symbol"], s["description"])
        """
        params: dict[str, Any] = {"q": query, "indexes": str(indexes).lower()}
        logger.debug("Searching symbols: '%s'", query)
        return self._make_request("GET", "/markets/search", params=params)

    def get_historical_quotes(
        self,
        symbol: str,
        interval: str = "daily",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """
        Get historical OHLCV bars for a symbol.

        Args:
            symbol: Symbol (e.g., "SPY").
            interval: Bar size: "daily", "weekly", or "monthly".
            start: Start date (YYYY-MM-DD).
            end:   End date (YYYY-MM-DD).

        Returns:
            Historical OHLCV data.

        Example:
            >>> history = client.get_historical_quotes("SPY", interval="daily",
            ...     start="2026-01-01", end="2026-03-16")
            >>> for bar in history["history"]["day"]:
            ...     print(bar["date"], bar["close"])
        """
        params: dict[str, Any] = {"symbol": symbol, "interval": interval}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        logger.debug("Fetching historical quotes for %s (%s)", symbol, interval)
        return self._make_request("GET", "/markets/history", params=params)

    # ==========================================================================
    # MULTILEG ORDER ENDPOINTS
    # ==========================================================================

    def place_multileg_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        order_type: str = "market",
        duration: OrderDuration = OrderDuration.DAY,
        price: float | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """
        Place a multileg option order (spreads, Iron Condors, etc.).

        Tradier supports multileg orders with up to 4 legs for complex
        option strategies. The order_type for multileg is typically:
        - 'market': Fill at market
        - 'credit': Net credit (receive premium)
        - 'debit': Net debit (pay premium)
        - 'even': Zero net premium

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            legs: List of OptionLeg objects defining each leg.
            order_type: 'market', 'credit', 'debit', or 'even'.
            duration: Time-in-force.
            price: Net limit price (required for credit/debit orders).
            tag: Optional order tag for tracking.

        Returns:
            Order response with order ID.

        Raises:
            ValueError: If legs are empty or price missing for limit types.
            TradierAPIError: On API errors.

        Example:
            >>> # Bull put spread (credit spread)
            >>> legs = [
            ...     OptionLeg(
            ...         option_symbol=build_option_symbol("SPY", "2026-03-20", "P", 540),
            ...         side=OrderSide.SELL_TO_OPEN,
            ...         quantity=1,
            ...     ),
            ...     OptionLeg(
            ...         option_symbol=build_option_symbol("SPY", "2026-03-20", "P", 535),
            ...         side=OrderSide.BUY_TO_OPEN,
            ...         quantity=1,
            ...     ),
            ... ]
            >>> order = client.place_multileg_order(
            ...     "SPY", legs, order_type="credit", price=1.50
            ... )

            >>> # Iron Condor (4 legs)
            >>> legs = [
            ...     OptionLeg(build_option_symbol("SPY", "2026-03-20", "P", 535),
            ...               OrderSide.BUY_TO_OPEN, 1),
            ...     OptionLeg(build_option_symbol("SPY", "2026-03-20", "P", 540),
            ...               OrderSide.SELL_TO_OPEN, 1),
            ...     OptionLeg(build_option_symbol("SPY", "2026-03-20", "C", 570),
            ...               OrderSide.SELL_TO_OPEN, 1),
            ...     OptionLeg(build_option_symbol("SPY", "2026-03-20", "C", 575),
            ...               OrderSide.BUY_TO_OPEN, 1),
            ... ]
            >>> order = client.place_multileg_order(
            ...     "SPY", legs, order_type="credit", price=2.00
            ... )
        """
        if not legs:
            raise ValueError("At least one OptionLeg is required")

        if order_type in ("credit", "debit") and price is None:
            raise ValueError(f"price is required for '{order_type}' multileg orders")

        logger.info(
            f"Placing multileg order: {symbol} with {len(legs)} legs "
            f"(type={order_type})"
        )

        # Build Tradier multileg payload
        payload = {
            "class": "multileg",
            "symbol": symbol,
            "type": order_type,
            "duration": duration.value,
        }

        if price is not None:
            payload["price"] = str(price)

        if tag:
            payload["tag"] = tag

        # Add legs as indexed arrays
        for i, leg in enumerate(legs):
            payload[f"option_symbol[{i}]"] = leg.option_symbol
            payload[f"side[{i}]"] = leg.side.value
            payload[f"quantity[{i}]"] = str(leg.quantity)

        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    def place_iron_condor(
        self,
        symbol: str,
        expiration: str,
        put_buy_strike: float,
        put_sell_strike: float,
        call_sell_strike: float,
        call_buy_strike: float,
        quantity: int = 1,
        order_type: str = "credit",
        price: float | None = None,
        duration: OrderDuration = OrderDuration.DAY,
    ) -> dict[str, Any]:
        """
        Place an Iron Condor order (convenience wrapper for place_multileg_order).

        An Iron Condor consists of 4 legs:
          - Buy OTM put (protection)
          - Sell put closer to money (short put)
          - Sell call closer to money (short call)
          - Buy OTM call (protection)

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            expiration: Option expiration (YYYY-MM-DD).
            put_buy_strike: Long put strike (lowest, protection).
            put_sell_strike: Short put strike.
            call_sell_strike: Short call strike.
            call_buy_strike: Long call strike (highest, protection).
            quantity: Number of contracts per leg.
            order_type: 'credit', 'debit', 'market', or 'even'.
            price: Net credit/debit limit price.
            duration: Time-in-force.

        Returns:
            Order response.

        Example:
            >>> order = client.place_iron_condor(
            ...     "SPY", "2026-03-20",
            ...     put_buy_strike=535, put_sell_strike=540,
            ...     call_sell_strike=570, call_buy_strike=575,
            ...     quantity=1, order_type="credit", price=2.00
            ... )
        """
        legs = [
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, "P", put_buy_strike),
                side=OrderSide.BUY_TO_OPEN,
                quantity=quantity,
            ),
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, "P", put_sell_strike),
                side=OrderSide.SELL_TO_OPEN,
                quantity=quantity,
            ),
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, "C", call_sell_strike),
                side=OrderSide.SELL_TO_OPEN,
                quantity=quantity,
            ),
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, "C", call_buy_strike),
                side=OrderSide.BUY_TO_OPEN,
                quantity=quantity,
            ),
        ]

        logger.info(
            f"Placing Iron Condor: {symbol} {expiration} "
            f"P{put_buy_strike}/{put_sell_strike} C{call_sell_strike}/{call_buy_strike}"
        )

        return self.place_multileg_order(
            symbol=symbol,
            legs=legs,
            order_type=order_type,
            duration=duration,
            price=price,
            tag="ironcondor",
        )

    def place_credit_spread(
        self,
        symbol: str,
        expiration: str,
        sell_strike: float,
        buy_strike: float,
        option_type: str = "P",
        quantity: int = 1,
        price: float | None = None,
        duration: OrderDuration = OrderDuration.DAY,
    ) -> dict[str, Any]:
        """
        Place a credit spread (bull put or bear call).

        A credit spread sells a closer-to-money option and buys a
        further-out-of-money option for protection.

        Args:
            symbol: Underlying symbol.
            expiration: Option expiration (YYYY-MM-DD).
            sell_strike: Short strike (closer to money).
            buy_strike: Long strike (farther from money, protection).
            option_type: "P" for bull put spread, "C" for bear call spread.
            quantity: Number of contracts.
            price: Net credit limit price.
            duration: Time-in-force.

        Returns:
            Order response.

        Example:
            >>> # Bull put spread for credit
            >>> order = client.place_credit_spread(
            ...     "SPY", "2026-03-20",
            ...     sell_strike=540, buy_strike=535,
            ...     option_type="P", quantity=1, price=1.50
            ... )
        """
        legs = [
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, option_type, sell_strike),
                side=OrderSide.SELL_TO_OPEN,
                quantity=quantity,
            ),
            OptionLeg(
                option_symbol=build_option_symbol(symbol, expiration, option_type, buy_strike),
                side=OrderSide.BUY_TO_OPEN,
                quantity=quantity,
            ),
        ]

        spread_type = "bull_put" if option_type[0].upper() == "P" else "bear_call"
        logger.info(
            f"Placing {spread_type} spread: {symbol} {expiration} "
            f"{option_type}{sell_strike}/{buy_strike}"
        )

        return self.place_multileg_order(
            symbol=symbol,
            legs=legs,
            order_type="credit",
            duration=duration,
            price=price,
            tag=f"credit_spread_{spread_type}",
        )

    def modify_order(
        self,
        order_id: int,
        order_type: str | None = None,
        duration: str | None = None,
        price: float | None = None,
        stop: float | None = None,
    ) -> dict[str, Any]:
        """
        Modify an existing order.

        Args:
            order_id: Order ID to modify.
            order_type: New order type (optional).
            duration: New duration (optional).
            price: New limit price (optional).
            stop: New stop price (optional).

        Returns:
            Modification response.
        """
        payload = {}
        if order_type:
            payload["type"] = order_type
        if duration:
            payload["duration"] = duration
        if price is not None:
            payload["price"] = str(price)
        if stop is not None:
            payload["stop"] = str(stop)

        logger.info("Modifying order %s: %s", order_id, payload)
        return self._make_request(
            "PUT",
            f"/accounts/{self.account_id}/orders/{order_id}",
            data=payload,
        )

    # ==========================================================================
    # CONTINGENT ORDER ENDPOINTS  (ENH-04)
    # ==========================================================================

    def place_oco_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """
        Place an OCO (One-Cancels-Other) order for two option legs.

        When one leg fills the other is automatically cancelled.  Useful for
        bracketing an open position with a profit-target and a stop.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            legs:   Exactly 2 OptionLeg objects (primary and secondary).
            duration: Order duration. Defaults to "day".

        Returns:
            Order response dict with order ID.

        Raises:
            ValueError: If fewer than 2 legs are provided.

        Example:
            >>> legs = [
            ...     OptionLeg("SPY260320C00550000", OrderSide.SELL_TO_CLOSE, 1),
            ...     OptionLeg("SPY260320C00560000", OrderSide.BUY_TO_CLOSE, 1),
            ... ]
            >>> order = client.place_oco_order("SPY", legs)
        """
        if len(legs) < 2:
            raise ValueError("OCO order requires exactly 2 legs")

        payload: dict[str, Any] = {
            "class": "oco",
            "symbol": symbol,
            "duration": duration,
            "type[0]": "market",
            "type[1]": "market",
        }
        for i, leg in enumerate(legs[:2]):
            payload[f"option_symbol[{i}]"] = leg.option_symbol
            payload[f"side[{i}]"] = leg.side.value
            payload[f"quantity[{i}]"] = str(leg.quantity)

        logger.info("Placing OCO order: %s (%s legs)", symbol, len(legs))
        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    def place_oto_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """
        Place an OTO (One-Triggers-Other) order for two option legs.

        The second leg is triggered only when the first leg fills.  Use this
        to enter a position and simultaneously queue a protective stop.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            legs:   Exactly 2 OptionLeg objects (trigger and response).
            duration: Order duration. Defaults to "day".

        Returns:
            Order response dict with order ID.

        Raises:
            ValueError: If fewer than 2 legs are provided.

        Example:
            >>> legs = [
            ...     OptionLeg("SPY260320P00500000", OrderSide.BUY_TO_OPEN, 1),
            ...     OptionLeg("SPY260320P00495000", OrderSide.SELL_TO_CLOSE, 1),
            ... ]
            >>> order = client.place_oto_order("SPY", legs)
        """
        if len(legs) < 2:
            raise ValueError("OTO order requires exactly 2 legs")

        payload: dict[str, Any] = {
            "class": "oto",
            "symbol": symbol,
            "duration": duration,
            "type[0]": "market",
            "type[1]": "market",
        }
        for i, leg in enumerate(legs[:2]):
            payload[f"option_symbol[{i}]"] = leg.option_symbol
            payload[f"side[{i}]"] = leg.side.value
            payload[f"quantity[{i}]"] = str(leg.quantity)

        logger.info("Placing OTO order: %s (%s legs)", symbol, len(legs))
        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    def place_otoco_order(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """
        Place an OTOCO (One-Triggers-OCO) order for three option legs.

        The entry leg triggers an OCO pair of a profit target and a stop loss.
        This is the primary bracket-order mechanism for defined-risk entries.

        Args:
            symbol: Underlying symbol (e.g., "SPY").
            legs:   Exactly 3 OptionLeg objects — entry, profit-target, stop-loss.
            duration: Order duration. Defaults to "day".

        Returns:
            Order response dict with order ID.

        Raises:
            ValueError: If fewer than 3 legs are provided.

        Example:
            >>> legs = [
            ...     OptionLeg("SPY260320C00550000", OrderSide.BUY_TO_OPEN, 1),   # entry
            ...     OptionLeg("SPY260320C00550000", OrderSide.SELL_TO_CLOSE, 1), # profit target
            ...     OptionLeg("SPY260320C00550000", OrderSide.SELL_TO_CLOSE, 1), # stop
            ... ]
            >>> order = client.place_otoco_order("SPY", legs)
        """
        if len(legs) < 3:
            raise ValueError("OTOCO order requires exactly 3 legs")

        payload: dict[str, Any] = {
            "class": "otoco",
            "symbol": symbol,
            "duration": duration,
            "type[0]": "market",
            "type[1]": "market",
            "type[2]": "market",
        }
        for i, leg in enumerate(legs[:3]):
            payload[f"option_symbol[{i}]"] = leg.option_symbol
            payload[f"side[{i}]"] = leg.side.value
            payload[f"quantity[{i}]"] = str(leg.quantity)

        logger.info("Placing OTOCO order: %s (%s legs)", symbol, len(legs))
        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload,
        )

    # ==========================================================================
    # STREAMING SESSION
    # ==========================================================================

    def create_streaming_session(self) -> str | None:
        """
        Create a streaming session for Tradier SSE events.

        Tradier requires creating a session token before connecting
        to the SSE streaming endpoint.

        Returns:
            Session ID string, or None on failure.
        """
        try:
            response = self._make_request("POST", "/markets/events/session")
            session_id = response.get("stream", {}).get("sessionid")
            if session_id:
                logger.info("Tradier streaming session created")
            return session_id
        except TradierAPIError as e:
            logger.error("Failed to create streaming session: %s", e, exc_info=True)
            return None

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def test_connection(self) -> bool:
        """
        Test API connection and authentication.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            profile = self.get_user_profile()
            if "profile" in profile:
                logger.debug("Tradier connection test PASSED")
                return True
            else:
                logger.error("Tradier connection test FAILED: Invalid response")
                return False
        except Exception as e:
            logger.error("Tradier connection test FAILED: %s", str(e), exc_info=True)
            return False

    def __repr__(self) -> str:
        """String representation."""
        return f"TradierClient(account={self.account_id}, env={self.environment.value})"

    # ==========================================================================
    # ASYNC WRAPPERS WITH RATE LIMITING & CIRCUIT BREAKERS
    # ==========================================================================

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def place_order_async(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        duration: OrderDuration = OrderDuration.DAY,
        limit_price: float | None = None,
        stop_price: float | None = None,
        order_class: OrderClass = OrderClass.EQUITY,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """
        Place an order asynchronously with rate limiting and circuit breaker.

        This async version automatically applies:
        - Rate limiting (10 req/sec for Tradier)
        - Circuit breaker protection (opens after 5 failures)
        - Non-blocking execution in async contexts
        - Idempotency tag forwarded to the sync ``place_order`` (P0-9).

        Args:
            symbol: Security symbol (e.g., "SPY")
            side: Order side (buy/sell)
            quantity: Number of shares/contracts
            order_type: Order type (market, limit, stop)
            duration: Time-in-force (day, gtc)
            limit_price: Limit price (required for limit orders)
            stop_price: Stop price (required for stop orders)
            order_class: Security class (equity, option)
            tag: Optional Tradier idempotency tag (e.g. ``"spyder-<order_id>"``).
                 Deduplicated by Tradier for ~24 h; prevents duplicate fills on
                 network-timeout retries.

        Returns:
            Order response with order ID

        Example:
            >>> # In async context
            >>> order = await client.place_order_async(
            ...     symbol="SPY",
            ...     side=OrderSide.BUY,
            ...     quantity=10,
            ...     order_type=OrderType.MARKET,
            ...     tag="spyder-abc123",
            ... )
        """
        loop = asyncio.get_running_loop()

        # Use functools.partial so the tag keyword arg is forwarded correctly
        # without relying on positional order (place_order has 8+ positional args).
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                functools.partial(
                    self.place_order,
                    symbol,
                    side,
                    quantity,
                    order_type,
                    duration,
                    limit_price,
                    stop_price,
                    order_class,
                    tag,
                ),
            )
            return result

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def get_quotes_async(self, symbols: list[str]) -> dict[str, Any]:
        """
        Get real-time quotes asynchronously with rate limiting and circuit breaker.

        This async version provides:
        - Automatic rate limiting to prevent API bans
        - Circuit breaker to handle service outages gracefully
        - Non-blocking operation in async event loops

        Args:
            symbols: List of symbols (e.g., ["SPY", "QQQ"])

        Returns:
            Quote data

        Example:
            >>> quotes = await client.get_quotes_async(["SPY", "QQQ"])
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_quotes,
                symbols
            )
            return result

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def get_account_balances_async(self) -> dict[str, Any]:
        """
        Get account balances asynchronously with protection.

        Returns:
            Account balance data
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_account_balances
            )
            return result

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def get_positions_async(self) -> dict[str, Any]:
        """
        Get current positions asynchronously with protection.

        Returns:
            List of current positions
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_positions
            )
            return result

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def cancel_order_async(self, order_id: int) -> dict[str, Any]:
        """
        Cancel an order asynchronously with protection.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.cancel_order,
                order_id
            )
            return result

    @rate_limit(service="tradier")
    @retry_async(max_attempts=3, base_delay=1.0, max_delay=8.0,
                 exceptions=(TradierServerError, TradierRateLimitError, ConnectionError, TimeoutError))  # noqa: E501
    async def get_option_chain_async(self, symbol: str, expiration: str) -> dict[str, Any]:
        """
        Get option chain asynchronously with protection.

        Args:
            symbol: Underlying symbol (e.g., "SPY")
            expiration: Expiration date (YYYY-MM-DD)

        Returns:
            Option chain data
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_option_chain,
                symbol,
                expiration
            )
            return result

    # ==========================================================================
    # CIRCUIT BREAKER MONITORING
    # ==========================================================================

    @staticmethod
    def get_circuit_breaker_status() -> dict[str, Any]:
        """
        Get current circuit breaker status for monitoring.

        Returns:
            Dictionary with circuit breaker statistics:
                - state: Current state (CLOSED/OPEN/HALF_OPEN)
                - failure_count: Number of consecutive failures
                - is_open: Whether circuit is open (blocking requests)
                - time_until_retry: Seconds until retry attempt (if open)

        Example:
            >>> status = TradierClient.get_circuit_breaker_status()
            >>> if status['is_open']:
            ...     logger.warning(f"Tradier circuit open for {status['time_until_retry']}s")
        """
        return tradier_breaker.get_stats()

    @staticmethod
    def reset_circuit_breaker():
        """
        Manually reset the circuit breaker.

        Use this after manually verifying that the service has recovered.

        Example:
            >>> TradierClient.reset_circuit_breaker()
            >>> logger.info("Tradier circuit breaker manually reset")
        """
        tradier_breaker.reset()
        logger.info("Tradier circuit breaker has been manually reset")

    @rate_limit(service="tradier")
    async def place_multileg_order_async(
        self,
        symbol: str,
        legs: list[OptionLeg],
        order_type: str = "market",
        duration: OrderDuration = OrderDuration.DAY,
        price: float | None = None,
        tag: str | None = None,
    ) -> dict[str, Any]:
        """
        Place a multileg order asynchronously with rate limiting and circuit breaker.

        Args:
            symbol: Underlying symbol.
            legs: List of OptionLeg objects.
            order_type: 'market', 'credit', 'debit', or 'even'.
            duration: Time-in-force.
            price: Net limit price.
            tag: Optional order tag.

        Returns:
            Order response with order ID.
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.place_multileg_order(
                    symbol, legs, order_type, duration, price, tag
                ),
            )
            return result

    @rate_limit(service="tradier")
    async def get_option_chain_with_greeks_async(
        self,
        symbol: str,
        expiration: str,
        option_type: str | None = None,
    ) -> list[GreekData]:
        """
        Get option chain with parsed Greeks asynchronously.

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).
            option_type: Filter by "call" or "put".

        Returns:
            List of GreekData objects.
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.get_option_chain_with_greeks(
                    symbol, expiration, option_type
                ),
            )
            return result

    @rate_limit(service="tradier")
    async def get_option_strikes_async(
        self,
        symbol: str,
        expiration: str,
    ) -> dict[str, Any]:
        """
        Get option strikes asynchronously.

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).

        Returns:
            Response with available strikes.
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_option_strikes,
                symbol,
                expiration,
            )
            return result

    @rate_limit(service="tradier")
    async def modify_order_async(
        self,
        order_id: int,
        order_type: str | None = None,
        duration: str | None = None,
        price: float | None = None,
        stop: float | None = None,
    ) -> dict[str, Any]:
        """
        Modify an order asynchronously.

        Args:
            order_id: Order ID to modify.
            order_type: New order type.
            duration: New duration.
            price: New limit price.
            stop: New stop price.

        Returns:
            Modification response.
        """
        loop = asyncio.get_running_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.modify_order(
                    order_id, order_type, duration, price, stop
                ),
            )
            return result

    # ---- ENH-05: account endpoints ----------------------------------------

    @rate_limit(service="tradier")
    async def get_gainloss_async(
        self,
        page: int | None = None,
        limit: int | None = None,
        sort_by: str = "closeDate",
        sort_direction: str = "desc",
        start: str | None = None,
        end: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`get_gainloss`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.get_gainloss(
                    page, limit, sort_by, sort_direction, start, end, symbol
                ),
            )
            return result

    @rate_limit(service="tradier")
    async def get_watchlists_async(self) -> dict[str, Any]:
        """Async wrapper for :meth:`get_watchlists`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(None, self.get_watchlists)
            return result

    @rate_limit(service="tradier")
    async def add_to_watchlist_async(
        self, watchlist_id: str, symbols: list[str]
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`add_to_watchlist`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.add_to_watchlist(watchlist_id, symbols),
            )
            return result

    # ---- ENH-05: market data endpoints ------------------------------------

    @rate_limit(service="tradier")
    async def get_market_calendar_async(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`get_market_calendar`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.get_market_calendar(month, year),
            )
            return result

    @rate_limit(service="tradier")
    async def get_market_clock_async(self) -> dict[str, Any]:
        """Async wrapper for :meth:`get_market_clock`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(None, self.get_market_clock)
            return result

    @rate_limit(service="tradier")
    async def get_time_sales_async(
        self,
        symbol: str,
        interval: str = "1min",
        start: str | None = None,
        end: str | None = None,
        session_filter: str = "open",
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`get_time_sales`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.get_time_sales(symbol, interval, start, end, session_filter),
            )
            return result

    @rate_limit(service="tradier")
    async def search_symbols_async(
        self, query: str, indexes: bool = False
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`search_symbols`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.search_symbols(query, indexes),
            )
            return result

    @rate_limit(service="tradier")
    async def get_historical_quotes_async(
        self,
        symbol: str,
        interval: str = "daily",
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`get_historical_quotes`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.get_historical_quotes(symbol, interval, start, end),
            )
            return result

    # ---- ENH-04: contingent order endpoints --------------------------------

    @rate_limit(service="tradier")
    async def place_oco_order_async(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`place_oco_order`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.place_oco_order(symbol, legs, duration),
            )
            return result

    @rate_limit(service="tradier")
    async def place_oto_order_async(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`place_oto_order`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.place_oto_order(symbol, legs, duration),
            )
            return result

    @rate_limit(service="tradier")
    async def place_otoco_order_async(
        self,
        symbol: str,
        legs: list[OptionLeg],
        duration: str = "day",
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`place_otoco_order`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.place_otoco_order(symbol, legs, duration),
            )
            return result

    # ---- ENH-06: order preview ---------------------------------------------

    @rate_limit(service="tradier")
    async def preview_order_async(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        duration: str = "day",
        limit_price: float | None = None,
        stop_price: float | None = None,
        order_class: OrderClass = OrderClass.OPTION,
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`preview_order`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.preview_order(
                    symbol, side, quantity, order_type, duration,
                    limit_price, stop_price, order_class,
                ),
            )
            return result

    @rate_limit(service="tradier")
    async def preview_multileg_order_async(
        self,
        symbol: str,
        legs: list[OptionLeg],
        order_type: str = "credit",
        duration: str = "day",
        price: float | None = None,
    ) -> dict[str, Any]:
        """Async wrapper for :meth:`preview_multileg_order`."""
        loop = asyncio.get_running_loop()
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.preview_multileg_order(symbol, legs, order_type, duration, price),
            )
            return result


class TradierAccountStreamSSE:
    """
    Real-time account event stream via Tradier Server-Sent Events (SSE).

    Streams order fills, status changes, and account events in real-time.
    Runs in a background thread and dispatches events via callbacks.

    This is critical for:
    - Confirming order fills without polling
    - Real-time position updates
    - Detecting partial fills and order rejections
    - Enabling event-driven order management

    Example:
        >>> client = create_tradier_client_from_env()
        >>> stream = TradierAccountStreamSSE(client)
        >>> stream.on_event = lambda e: print(f"Event: {e.event_type} {e.symbol}")
        >>> stream.start()
        >>> # ... later
        >>> stream.stop()

    Attributes:
        client: Parent TradierClient instance.
        on_event: Callback for all events.
        on_order: Callback for order-specific events.
        on_trade: Callback for trade/fill events.
    """

    def __init__(self, client: TradierClient):
        """
        Initialize the account event stream.

        Args:
            client: Configured TradierClient instance.
        """
        self.client = client
        self._running = False
        self._thread: threading.Thread | None = None
        self._session_id: str | None = None
        self._reconnect_attempts = 0
        self._max_reconnect = 10
        self._reconnect_delay = 2.0

        # Callbacks
        self.on_event: Callable[[AccountEvent], None] | None = None
        self.on_order: Callable[[AccountEvent], None] | None = None
        self.on_trade: Callable[[AccountEvent], None] | None = None
        self.on_error: Callable[[str], None] | None = None

        logger.info("TradierAccountStream initialized")

    def start(self) -> None:
        """
        Start streaming account events in a background thread.

        Raises:
            ImportError: If sseclient-py is not installed.
            RuntimeError: If already streaming.
        """
        if not HAS_SSE:
            raise ImportError(
                "sseclient-py required for SSE streaming. "
                "Run: pip install sseclient-py"
            )

        if self._running:
            logger.warning("Account stream already running")
            return

        self._running = True
        self._reconnect_attempts = 0

        self._thread = threading.Thread(
            target=self._stream_loop,
            name="TradierAccountStream",
            daemon=True,
        )
        _coord = get_shutdown_coordinator()
        _coord.register_thread(self._thread, name="TradierAccountStream")
        _coord.register_cleanup(self.stop)
        self._thread.start()
        logger.info("Account event stream started")

    def stop(self) -> None:
        """Stop the account event stream."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        logger.info("Account event stream stopped")

    @property
    def is_running(self) -> bool:
        """Check if the stream is active."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def _stream_loop(self) -> None:
        """Main SSE streaming loop with reconnection logic."""
        while self._running and self._reconnect_attempts < self._max_reconnect:
            try:
                # Create streaming session
                self._session_id = self.client.create_streaming_session()
                if not self._session_id:
                    raise TradierAPIError("Failed to create streaming session")

                # Connect to SSE endpoint
                url = f"{TRADIER_STREAM_URL}/accounts/events"
                headers = {
                    "Accept": "text/event-stream",
                }
                payload = {
                    "sessionid": self._session_id,
                    "excludeAccounts": "",
                }

                logger.info("Connecting to Tradier account event stream...")

                response = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    stream=True,
                    timeout=(10, None),  # connect timeout 10s, no read timeout
                )
                response.raise_for_status()

                # Reset reconnect counter on successful connection
                self._reconnect_attempts = 0

                client_sse = sseclient.SSEClient(response)
                for event in client_sse.events():
                    if not self._running:
                        break
                    self._process_sse_event(event)

            except Exception as e:
                self._reconnect_attempts += 1
                delay = min(
                    self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                    120.0,
                )
                error_msg = (
                    f"Account stream error (attempt {self._reconnect_attempts}/"
                    f"{self._max_reconnect}): {e}"
                )
                logger.error(error_msg, exc_info=True)

                if self.on_error:
                    try:
                        self.on_error(error_msg)
                    except Exception as cb_err:
                        logger.debug("on_error callback raised: %s", cb_err)

                if self._running:
                    logger.info(f"Reconnecting account stream in {delay:.1f}s...")
                    time.sleep(delay)  # thread-safe: time.sleep() intentional

        if self._reconnect_attempts >= self._max_reconnect:
            logger.error(
                f"Account stream: max reconnection attempts "
                f"({self._max_reconnect}) reached"
            )

    def _process_sse_event(self, event: Any) -> None:
        """
        Process a single SSE event from Tradier.

        Args:
            event: SSE event object with data attribute.
        """
        try:
            if not event.data or event.data == "":
                return  # heartbeat

            data = json.loads(event.data)
            event_type = data.get("type", event.event or "unknown")

            account_event = AccountEvent(
                event_type=event_type,
                timestamp=data.get("date", ""),
                data=data,
                order_id=data.get("id"),
                symbol=data.get("symbol", ""),
                status=data.get("status", ""),
            )

            logger.debug(
                f"Account event: {event_type} "
                f"symbol={account_event.symbol} "
                f"status={account_event.status}"
            )

            # Dispatch to callbacks
            if self.on_event:
                self.on_event(account_event)

            if event_type in ("order", "pending", "filled", "canceled",
                              "rejected", "partially_filled"):
                if self.on_order:
                    self.on_order(account_event)

            if event_type in ("trade", "filled", "partially_filled"):
                if self.on_trade:
                    self.on_trade(account_event)

        except json.JSONDecodeError:
            logger.debug("Non-JSON SSE data (heartbeat): %s", event.data[:50])
        except Exception as e:
            logger.warning("Error processing SSE event: %s", e, exc_info=True)


# Backward-compatibility alias — existing code using TradierAccountStream continues to work.
TradierAccountStream = TradierAccountStreamSSE


# ==============================================================================
# WEBSOCKET MARKET DATA STREAM  (ENH-01)
# ==============================================================================
class TradierMarketStream:
    """
    Real-time market data stream via Tradier WebSocket API.

    Streams real-time quotes, trades, and summaries for equities and options.
    Runs in a background thread and dispatches events via caller-supplied callbacks.

    WebSocket protocol flow
    -----------------------
    1. ``POST /v1/markets/events/session`` → receive a ``sessionid`` (5-min TTL).
    2. Open ``wss://ws.tradier.com/v1/markets/events``.
    3. Send JSON subscription payload with ``sessionid``, ``symbols``, and ``filter``.
    4. Receive streaming JSON events; re-send payload to update symbol list.

    Key advantage over SSE
    ----------------------
    Symbols can be added or removed by re-sending the subscription payload on the
    *existing* connection — no reconnect required (see :meth:`update_symbols`).

    Example::

        client = create_tradier_client_from_env()
        stream = TradierMarketStream(client, symbols=["SPY", "QQQ"])
        stream.on_quote = lambda msg: print(f"Quote: {msg['symbol']} {msg['bid']}/{msg['ask']}")
        stream.start()
        # … later …
        stream.stop()

    Attributes:
        client: Parent :class:`TradierClient` instance.
        on_quote: Callback invoked for every quote event.
        on_trade: Callback invoked for every trade print.
        on_summary: Callback invoked for per-symbol summary events.
        on_error: Callback invoked on connection errors (receives error string).
        on_connected: Callback invoked on successful WebSocket open.
        on_disconnected: Callback invoked when the stream disconnects.
    """

    def __init__(
        self,
        client: "TradierClient",
        symbols: list[str],
        filters: list[str] | None = None,
        max_reconnect: int = 10,
        reconnect_delay: float = 2.0,
    ) -> None:
        """
        Initialise TradierMarketStream.

        Args:
            client: Configured :class:`TradierClient` instance.
            symbols: Initial list of symbols to subscribe to.
            filters: Event type filters.  Valid values: ``"trade"``, ``"quote"``,
                     ``"summary"``, ``"timesale"``, ``"tradex"``.
                     Defaults to ``["trade", "quote"]``.
            max_reconnect: Maximum reconnection attempts before giving up.
            reconnect_delay: Base backoff delay in seconds (doubles each attempt,
                             capped at 120 s).
        """
        if not HAS_WEBSOCKET:
            raise ImportError(
                "websocket-client is required for WebSocket market streaming. "
                "Install it with: pip install 'websocket-client>=1.7.0'"
            )

        self.client = client
        self._symbols: list[str] = list(symbols)
        self._filters: list[str] = filters if filters is not None else ["trade", "quote"]
        self._max_reconnect = max_reconnect
        self._reconnect_delay = reconnect_delay

        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._ws: Any = None
        self._session_id: str | None = None
        self._session_created_at: float = 0.0
        self._reconnect_attempts: int = 0
        self._ws_lock: threading.Lock = threading.Lock()

        # Public callbacks — assign before calling start()
        self.on_quote: Callable[[dict[str, Any]], None] | None = None
        self.on_trade: Callable[[dict[str, Any]], None] | None = None
        self.on_summary: Callable[[dict[str, Any]], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_connected: Callable[[], None] | None = None
        self.on_disconnected: Callable[[], None] | None = None

        logger.info(
            "TradierMarketStream initialised for %s symbol(s): %s", len(self._symbols), self._symbols  # noqa: E501
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start streaming market data in a background daemon thread.

        Raises:
            RuntimeError: If the stream is already running.

        Example::

            stream.start()
        """
        if self._running:
            logger.warning("TradierMarketStream is already running")
            return

        self._running = True
        self._reconnect_attempts = 0
        self._thread = threading.Thread(
            target=self._stream_loop,
            name="TradierMarketStream",
            daemon=True,
        )
        _coord = get_shutdown_coordinator()
        _coord.register_thread(self._thread, name="TradierMarketStream")
        _coord.register_cleanup(self.stop)
        self._thread.start()
        logger.info("Market stream started — symbols: %s", self._symbols)

    def stop(self) -> None:
        """
        Gracefully stop the market data stream.

        Closes the WebSocket connection and waits up to 10 s for the background
        thread to exit.

        Example::

            stream.stop()
        """
        self._running = False
        with self._ws_lock:
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception as ws_err:
                    logger.debug("WebSocket close error: %s", ws_err)
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        logger.info("Market stream stopped")

    def update_symbols(self, symbols: list[str]) -> None:
        """
        Update the symbol subscription without reconnecting.

        Re-sends the subscription payload on the live connection.  This is a
        key WebSocket advantage — no reconnection or new session needed.

        Args:
            symbols: Replacement symbol list.

        Example::

            stream.update_symbols(["SPY", "QQQ", "IWM"])
        """
        self._symbols = list(symbols)
        with self._ws_lock:
            ws = self._ws
        if ws is not None and self._session_id:
            try:
                payload = {
                    "symbols": self._symbols,
                    "sessionid": self._session_id,
                    "filter": self._filters,
                }
                ws.send(json.dumps(payload))
                logger.info("Market stream subscription updated: %s", self._symbols)
            except Exception as exc:
                logger.warning("Failed to send updated subscription: %s", exc, exc_info=True)

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the stream thread is alive and active."""
        return self._running and self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_ws_url(self) -> str:
        """Return the correct WebSocket URL for the configured environment."""
        env = getattr(self.client, "environment", TradingEnvironment.SANDBOX)
        if env in (TradingEnvironment.SANDBOX,):
            return f"{TRADIER_SANDBOX_WS_URL}/markets/events"
        return f"{TRADIER_WS_URL}/markets/events"

    def _is_session_expired(self) -> bool:
        """Return ``True`` if the session token may have expired.

        Tradier session tokens expire after 5 minutes; we refresh after
        ``SESSION_TTL`` seconds (4.5 min) to avoid edge-case expiry mid-stream.
        """
        return time.time() - self._session_created_at > SESSION_TTL

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _stream_loop(self) -> None:
        """Main WebSocket loop with exponential-backoff reconnection."""
        while self._running and self._reconnect_attempts < self._max_reconnect:
            try:
                # Refresh session token if absent or approaching expiry
                if self._session_id is None or self._is_session_expired():
                    session_id = self.client.create_streaming_session()
                    if not session_id:
                        raise TradierAPIError("create_streaming_session returned empty token")
                    self._session_id = session_id
                    self._session_created_at = time.time()
                    logger.debug("Market stream session token refreshed")

                ws_url = self._get_ws_url()
                logger.info("Connecting market stream WebSocket → %s", ws_url)

                ws_app = websocket.WebSocketApp(
                    ws_url,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                with self._ws_lock:
                    self._ws = ws_app

                ws_app.run_forever(
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                )

                # run_forever() returned — stream disconnected unexpectedly
                if self._running:
                    self._reconnect_attempts += 1
                    delay = min(
                        self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                        120.0,
                    )
                    logger.warning(
                        f"Market stream disconnected unexpectedly. "
                        f"Reconnecting in {delay:.1f}s "
                        f"(attempt {self._reconnect_attempts}/{self._max_reconnect})"
                    )
                    # Force session refresh on next iteration
                    self._session_id = None
                    time.sleep(delay)  # thread-safe: time.sleep() intentional

            except Exception as exc:
                self._reconnect_attempts += 1
                delay = min(
                    self._reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                    120.0,
                )
                error_msg = (
                    f"Market stream error "
                    f"(attempt {self._reconnect_attempts}/{self._max_reconnect}): {exc}"
                )
                logger.error(error_msg, exc_info=True)
                if self.on_error:
                    try:
                        self.on_error(error_msg)
                    except Exception as cb_err:
                        logger.debug("on_error callback raised: %s", cb_err)
                if self._running:
                    logger.info(f"Reconnecting market stream in {delay:.1f}s…")
                    self._session_id = None
                    time.sleep(delay)  # thread-safe: time.sleep() intentional

        with self._ws_lock:
            self._ws = None

        if self._reconnect_attempts >= self._max_reconnect:
            logger.error(
                f"Market stream: max reconnection attempts ({self._max_reconnect}) reached. "
                "Stream is stopped."
            )

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def _on_ws_open(self, ws: Any) -> None:
        """Send subscription payload immediately after the WebSocket opens."""
        payload = {
            "symbols": self._symbols,
            "sessionid": self._session_id,
            "filter": self._filters,
        }
        ws.send(json.dumps(payload))
        self._reconnect_attempts = 0  # Reset on successful connect
        logger.info(
            "Market stream connected — subscribed to %s symbol(s)", len(self._symbols)
        )
        if self.on_connected:
            try:
                self.on_connected()
            except Exception as exc:
                logger.warning("on_connected callback raised: %s", exc, exc_info=True)

    def _on_ws_message(self, ws: Any, message: str) -> None:
        """Parse and dispatch an incoming WebSocket message to the right callback."""
        try:
            if not message or not message.strip():
                return  # Heartbeat / keep-alive

            data: dict[str, Any] = json.loads(message)
            if not isinstance(data, dict):
                return

            event_type: str = data.get("type", "")
            logger.debug("Market event: %s %s", event_type, data.get('symbol', ''))

            if event_type == "quote" and self.on_quote:
                try:
                    self.on_quote(data)
                except Exception as exc:
                    logger.warning("on_quote callback raised: %s", exc, exc_info=True)

            elif event_type in ("trade", "tradex") and self.on_trade:
                try:
                    self.on_trade(data)
                except Exception as exc:
                    logger.warning("on_trade callback raised: %s", exc, exc_info=True)

            elif event_type == "summary" and self.on_summary:
                try:
                    self.on_summary(data)
                except Exception as exc:
                    logger.warning("on_summary callback raised: %s", exc, exc_info=True)

        except json.JSONDecodeError:
            logger.debug("Non-JSON WebSocket message (heartbeat): %s", message[:50])
        except Exception as exc:
            logger.warning("Unhandled error in _on_ws_message: %s", exc, exc_info=True)

    def _on_ws_error(self, ws: Any, error: Any) -> None:
        """Handle WebSocket-level errors."""
        error_msg = str(error)
        logger.error("Market stream WebSocket error: %s", error_msg)
        if self.on_error:
            try:
                self.on_error(error_msg)
            except Exception as cb_err:
                logger.debug("on_error callback raised: %s", cb_err)

    def _on_ws_close(
        self,
        ws: Any,
        close_status_code: Any,
        close_msg: Any,
    ) -> None:
        """Handle WebSocket close and notify the disconnected callback."""
        with self._ws_lock:
            self._ws = None
        logger.info(
            "Market stream disconnected (code=%s, msg=%s)", close_status_code, close_msg
        )
        if self.on_disconnected:
            try:
                self.on_disconnected()
            except Exception as exc:
                logger.warning("on_disconnected callback raised: %s", exc, exc_info=True)


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_tradier_client_from_env(environment: TradingEnvironment | None = None) -> TradierClient:
    """
    Create TradierClient from environment variables.

    Required environment variables:
        - TRADIER_API_KEY: API access token
        - TRADIER_ACCOUNT_ID: Account ID

    Optional environment variables:
        - TRADIER_ENVIRONMENT: ``"live"`` or ``"sandbox"`` (default: ``"sandbox"``).
          When *environment* is not passed explicitly, this variable is read to
          determine which Tradier endpoint to connect to.  This is independent of
          ``TRADING_MODE`` so that paper-trading mode can still consume real
          production quotes (``TRADING_MODE=paper TRADIER_ENVIRONMENT=live``).

    Args:
        environment: Trading environment override.  If ``None`` (the default),
            the value of the ``TRADIER_ENVIRONMENT`` env var is used, falling
            back to ``sandbox`` if that variable is also absent.

    Returns:
        Configured TradierClient instance

    Raises:
        ValueError: If required environment variables are missing

    Example:
        >>> import os
        >>> os.environ["TRADIER_API_KEY"] = "your_token"
        >>> os.environ["TRADIER_ACCOUNT_ID"] = "your_account"
        >>> os.environ["TRADIER_ENVIRONMENT"] = "live"
        >>> client = create_tradier_client_from_env()  # picks up TRADIER_ENVIRONMENT
    """
    api_key = os.getenv("TRADIER_API_KEY")
    account_id = os.getenv("TRADIER_ACCOUNT_ID")

    if not api_key:
        raise ValueError("TRADIER_API_KEY environment variable not set")
    if not account_id:
        raise ValueError("TRADIER_ACCOUNT_ID environment variable not set")

    if environment is None:
        _env_str = os.getenv("TRADIER_ENVIRONMENT", "sandbox").lower()
        environment = TradingEnvironment.LIVE if _env_str == "live" else TradingEnvironment.SANDBOX

    return TradierClient(
        api_key=api_key,
        account_id=account_id,
        environment=environment
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    """Test Tradier client connection."""


    # Load from environment
    try:
        client = create_tradier_client_from_env(TradingEnvironment.SANDBOX)

        # Test connection
        if client.test_connection():

            # Get user profile
            profile = client.get_user_profile()

            # Get account balances
            balances = client.get_account_balances()

            # Get positions
            positions = client.get_positions()

            # Get quotes
            quotes = client.get_quotes(["SPY"])

        else:
            pass

    except Exception as e:
        logger.error("Demo __main__ failed: %s", e, exc_info=True)
