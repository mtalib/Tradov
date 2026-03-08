#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import os
import time
try:
    import orjson as json  # 3-10x faster JSON; drop-in compatible for loads/dumps
except ImportError:
    import json
import asyncio
import threading
from typing import Optional, Dict, Any, List, Callable
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

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import rate_limit, acquire_tradier
from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import tradier_breaker

# ==============================================================================
# CONSTANTS
# ==============================================================================
TRADIER_LIVE_URL = "https://api.tradier.com/v1"
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"
TRADIER_STREAM_URL = "https://stream.tradier.com/v1"
DEFAULT_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # exponential backoff factor

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
    data: Dict[str, Any] = field(default_factory=dict)
    order_id: Optional[int] = None
    symbol: str = ""
    status: str = ""


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


def parse_option_symbol(symbol: str) -> Dict[str, Any]:
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

        logger.info(f"TradierClient initialized for {environment.value} environment")

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
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
            logger.debug(f"Making {method} request to {endpoint}")

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
                return response.json()

            elif response.status_code == 401 or response.status_code == 403:
                error_msg = f"Authentication failed: {response.text}"
                logger.error(error_msg)
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
            error_msg = f"Request timeout after {self.timeout}s"
            logger.error(error_msg)
            raise TradierAPIError(error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(error_msg)
            raise TradierAPIError(error_msg)

        except (TradierAuthenticationError, TradierValidationError,
                TradierRateLimitError, TradierServerError, TradierAPIError):
            raise  # Re-raise Tradier-specific errors without wrapping

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            raise TradierAPIError(error_msg)

    # ==========================================================================
    # USER & ACCOUNT ENDPOINTS
    # ==========================================================================

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile information.

        Returns:
            User profile data including account details

        Example:
            >>> profile = client.get_user_profile()
            >>> print(profile["profile"]["name"])
        """
        logger.info("Fetching user profile")
        return self._make_request("GET", "/user/profile")

    def get_account_balances(self) -> Dict[str, Any]:
        """
        Get account balances and buying power.

        Returns:
            Account balance data

        Example:
            >>> balances = client.get_account_balances()
            >>> print(balances["balances"]["total_equity"])
        """
        logger.info(f"Fetching balances for account {self.account_id}")
        return self._make_request("GET", f"/accounts/{self.account_id}/balances")

    def get_positions(self) -> Dict[str, Any]:
        """
        Get current positions.

        Returns:
            List of current positions

        Example:
            >>> positions = client.get_positions()
            >>> for pos in positions["positions"]["position"]:
            ...     print(f"{pos['symbol']}: {pos['quantity']} shares")
        """
        logger.info(f"Fetching positions for account {self.account_id}")
        return self._make_request("GET", f"/accounts/{self.account_id}/positions")

    def get_history(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get trade history.

        Args:
            limit: Maximum number of events to return

        Returns:
            Trade history events
        """
        logger.info(f"Fetching history for account {self.account_id}")
        return self._make_request(
            "GET",
            f"/accounts/{self.account_id}/history",
            params={"limit": limit}
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
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        order_class: OrderClass = OrderClass.EQUITY
    ) -> Dict[str, Any]:
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
        logger.info(f"Placing {order_type.value} order: {side.value} {quantity} {symbol}")

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

        return self._make_request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=payload
        )

    def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get order details by ID.

        Args:
            order_id: Order ID

        Returns:
            Order details
        """
        logger.info(f"Fetching order {order_id}")
        return self._make_request("GET", f"/accounts/{self.account_id}/orders/{order_id}")

    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        logger.info(f"Canceling order {order_id}")
        return self._make_request("DELETE", f"/accounts/{self.account_id}/orders/{order_id}")

    def get_orders(self) -> Dict[str, Any]:
        """
        Get all orders (open and recent closed).

        Returns:
            List of orders
        """
        logger.info(f"Fetching all orders for account {self.account_id}")
        return self._make_request("GET", f"/accounts/{self.account_id}/orders")

    # ==========================================================================
    # MARKET DATA ENDPOINTS
    # ==========================================================================

    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
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
        logger.debug(f"Fetching quotes for {symbols_str}")
        return self._make_request("GET", "/markets/quotes", params={"symbols": symbols_str})

    def get_option_chain(self, symbol: str, expiration: str) -> Dict[str, Any]:
        """
        Get option chain for a symbol.

        Args:
            symbol: Underlying symbol (e.g., "SPY")
            expiration: Expiration date (YYYY-MM-DD)

        Returns:
            Option chain data
        """
        logger.debug(f"Fetching option chain for {symbol} expiring {expiration}")
        return self._make_request(
            "GET",
            "/markets/options/chains",
            params={"symbol": symbol, "expiration": expiration}
        )

    def get_option_expirations(self, symbol: str) -> Dict[str, Any]:
        """
        Get available option expiration dates.

        Args:
            symbol: Underlying symbol (e.g., "SPY")

        Returns:
            List of expiration dates
        """
        logger.debug(f"Fetching option expirations for {symbol}")
        return self._make_request("GET", "/markets/options/expirations", params={"symbol": symbol})

    def get_option_strikes(
        self,
        symbol: str,
        expiration: str,
    ) -> Dict[str, Any]:
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
        logger.debug(f"Fetching option strikes for {symbol} on {expiration}")
        return self._make_request(
            "GET",
            "/markets/options/strikes",
            params={"symbol": symbol, "expiration": expiration},
        )

    def get_option_chain_with_greeks(
        self,
        symbol: str,
        expiration: str,
        option_type: Optional[str] = None,
    ) -> List[GreekData]:
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

        logger.debug(f"Fetching option chain with greeks for {symbol} exp {expiration}")
        response = self._make_request("GET", "/markets/options/chains", params=params)

        return self._parse_greeks_from_chain(response, symbol)

    @staticmethod
    def _parse_greeks_from_chain(
        response: Dict[str, Any],
        underlying: str,
    ) -> List[GreekData]:
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
    ) -> List[GreekData]:
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

    # ==========================================================================
    # MULTILEG ORDER ENDPOINTS
    # ==========================================================================

    def place_multileg_order(
        self,
        symbol: str,
        legs: List[OptionLeg],
        order_type: str = "market",
        duration: OrderDuration = OrderDuration.DAY,
        price: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        price: Optional[float] = None,
        duration: OrderDuration = OrderDuration.DAY,
    ) -> Dict[str, Any]:
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
            tag="iron_condor",
        )

    def place_credit_spread(
        self,
        symbol: str,
        expiration: str,
        sell_strike: float,
        buy_strike: float,
        option_type: str = "P",
        quantity: int = 1,
        price: Optional[float] = None,
        duration: OrderDuration = OrderDuration.DAY,
    ) -> Dict[str, Any]:
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
        order_type: Optional[str] = None,
        duration: Optional[str] = None,
        price: Optional[float] = None,
        stop: Optional[float] = None,
    ) -> Dict[str, Any]:
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

        logger.info(f"Modifying order {order_id}: {payload}")
        return self._make_request(
            "PUT",
            f"/accounts/{self.account_id}/orders/{order_id}",
            data=payload,
        )

    # ==========================================================================
    # STREAMING SESSION
    # ==========================================================================

    def create_streaming_session(self) -> Optional[str]:
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
            logger.error(f"Failed to create streaming session: {e}")
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
                logger.info("Tradier connection test PASSED")
                return True
            else:
                logger.error("Tradier connection test FAILED: Invalid response")
                return False
        except Exception as e:
            logger.error(f"Tradier connection test FAILED: {str(e)}")
            return False

    def __repr__(self) -> str:
        """String representation."""
        return f"TradierClient(account={self.account_id}, env={self.environment.value})"

    # ==========================================================================
    # ASYNC WRAPPERS WITH RATE LIMITING & CIRCUIT BREAKERS
    # ==========================================================================

    @rate_limit(service="tradier")
    async def place_order_async(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        duration: OrderDuration = OrderDuration.DAY,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        order_class: OrderClass = OrderClass.EQUITY
    ) -> Dict[str, Any]:
        """
        Place an order asynchronously with rate limiting and circuit breaker.

        This async version automatically applies:
        - Rate limiting (10 req/sec for Tradier)
        - Circuit breaker protection (opens after 5 failures)
        - Non-blocking execution in async contexts

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
            >>> # In async context
            >>> order = await client.place_order_async(
            ...     symbol="SPY",
            ...     side=OrderSide.BUY,
            ...     quantity=10,
            ...     order_type=OrderType.MARKET
            ... )
        """
        loop = asyncio.get_event_loop()

        # Wrap sync method in async executor with circuit breaker protection
        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.place_order,
                symbol,
                side,
                quantity,
                order_type,
                duration,
                limit_price,
                stop_price,
                order_class
            )
            return result

    @rate_limit(service="tradier")
    async def get_quotes_async(self, symbols: List[str]) -> Dict[str, Any]:
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
        loop = asyncio.get_event_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_quotes,
                symbols
            )
            return result

    @rate_limit(service="tradier")
    async def get_account_balances_async(self) -> Dict[str, Any]:
        """
        Get account balances asynchronously with protection.

        Returns:
            Account balance data
        """
        loop = asyncio.get_event_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_account_balances
            )
            return result

    @rate_limit(service="tradier")
    async def get_positions_async(self) -> Dict[str, Any]:
        """
        Get current positions asynchronously with protection.

        Returns:
            List of current positions
        """
        loop = asyncio.get_event_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.get_positions
            )
            return result

    @rate_limit(service="tradier")
    async def cancel_order_async(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order asynchronously with protection.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        loop = asyncio.get_event_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                self.cancel_order,
                order_id
            )
            return result

    @rate_limit(service="tradier")
    async def get_option_chain_async(self, symbol: str, expiration: str) -> Dict[str, Any]:
        """
        Get option chain asynchronously with protection.

        Args:
            symbol: Underlying symbol (e.g., "SPY")
            expiration: Expiration date (YYYY-MM-DD)

        Returns:
            Option chain data
        """
        loop = asyncio.get_event_loop()

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
    def get_circuit_breaker_status() -> Dict[str, Any]:
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
        legs: List[OptionLeg],
        order_type: str = "market",
        duration: OrderDuration = OrderDuration.DAY,
        price: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        loop = asyncio.get_event_loop()

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
        option_type: Optional[str] = None,
    ) -> List[GreekData]:
        """
        Get option chain with parsed Greeks asynchronously.

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).
            option_type: Filter by "call" or "put".

        Returns:
            List of GreekData objects.
        """
        loop = asyncio.get_event_loop()

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
    ) -> Dict[str, Any]:
        """
        Get option strikes asynchronously.

        Args:
            symbol: Underlying symbol.
            expiration: Expiration date (YYYY-MM-DD).

        Returns:
            Response with available strikes.
        """
        loop = asyncio.get_event_loop()

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
        order_type: Optional[str] = None,
        duration: Optional[str] = None,
        price: Optional[float] = None,
        stop: Optional[float] = None,
    ) -> Dict[str, Any]:
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
        loop = asyncio.get_event_loop()

        async with tradier_breaker:
            result = await loop.run_in_executor(
                None,
                lambda: self.modify_order(
                    order_id, order_type, duration, price, stop
                ),
            )
            return result


# ==============================================================================
# SSE ACCOUNT EVENT STREAM
# ==============================================================================
class TradierAccountStream:
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
        >>> stream = TradierAccountStream(client)
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
        self._thread: Optional[threading.Thread] = None
        self._session_id: Optional[str] = None
        self._reconnect_attempts = 0
        self._max_reconnect = 10
        self._reconnect_delay = 2.0

        # Callbacks
        self.on_event: Optional[Callable[[AccountEvent], None]] = None
        self.on_order: Optional[Callable[[AccountEvent], None]] = None
        self.on_trade: Optional[Callable[[AccountEvent], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

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
                logger.error(error_msg)

                if self.on_error:
                    try:
                        self.on_error(error_msg)
                    except Exception:
                        pass

                if self._running:
                    logger.info(f"Reconnecting account stream in {delay:.1f}s...")
                    time.sleep(delay)

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
            logger.debug(f"Non-JSON SSE data (heartbeat): {event.data[:50]}")
        except Exception as e:
            logger.warning(f"Error processing SSE event: {e}")


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_tradier_client_from_env(environment: TradingEnvironment = TradingEnvironment.SANDBOX) -> TradierClient:
    """
    Create TradierClient from environment variables.

    Required environment variables:
        - TRADIER_API_KEY: API access token
        - TRADIER_ACCOUNT_ID: Account ID

    Args:
        environment: Trading environment (live or sandbox)

    Returns:
        Configured TradierClient instance

    Raises:
        ValueError: If required environment variables are missing

    Example:
        >>> import os
        >>> os.environ["TRADIER_API_KEY"] = "your_token"
        >>> os.environ["TRADIER_ACCOUNT_ID"] = "your_account"
        >>> client = create_tradier_client_from_env(TradingEnvironment.SANDBOX)
    """
    api_key = os.getenv("TRADIER_API_KEY")
    account_id = os.getenv("TRADIER_ACCOUNT_ID")

    if not api_key:
        raise ValueError("TRADIER_API_KEY environment variable not set")
    if not account_id:
        raise ValueError("TRADIER_ACCOUNT_ID environment variable not set")

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

    print("Tradier Client Test")
    print("=" * 60)

    # Load from environment
    try:
        client = create_tradier_client_from_env(TradingEnvironment.SANDBOX)
        print(f"✓ Client created: {client}")

        # Test connection
        if client.test_connection():
            print("✓ Connection test passed")

            # Get user profile
            profile = client.get_user_profile()
            print(f"✓ User: {profile.get('profile', {}).get('name', 'Unknown')}")

            # Get account balances
            balances = client.get_account_balances()
            print(f"✓ Balance retrieved")

            # Get positions
            positions = client.get_positions()
            print(f"✓ Positions retrieved")

            # Get quotes
            quotes = client.get_quotes(["SPY"])
            print(f"✓ Quote retrieved for SPY")

            print("\n✓ All tests passed!")
        else:
            print("✗ Connection test failed")

    except Exception as e:
        print(f"✗ Error: {str(e)}")
