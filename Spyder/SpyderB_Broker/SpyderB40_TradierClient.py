#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB40_TradierClient.py
Purpose: Tradier Brokerage REST API Client for Order Execution

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-11-18 Time: 19:00:00

Module Description:
    Simplified REST API client for Tradier Brokerage. This module replaces the complex
    IBKR Client Portal Web API with a straightforward Bearer token authentication model.

    Tradier provides commission-free equity and ETF options trading with a developer-friendly
    REST API. No OAuth complexity, no session management, no auto-tickle required.

    KEY FEATURES:
    - Simple Bearer token authentication (stateless)
    - Commission-free equity/ETF options trading
    - RESTful HTTP API with JSON responses
    - No session timeouts or connection management
    - Sandbox and live environment support

    API ENDPOINTS COVERED:
    - User profile and account information
    - Account balances and positions
    - Market quotes (real-time for account holders)
    - Order placement (market, limit, stop orders)
    - Order management (status, cancellation)
    - Trade history

Module Constants:
    TRADIER_LIVE_URL (str): Production API base URL
    TRADIER_SANDBOX_URL (str): Sandbox API base URL
    DEFAULT_TIMEOUT (int): HTTP request timeout in seconds (default: 10)
    MAX_RETRIES (int): Maximum retry attempts for failed requests (default: 3)
    RETRY_BACKOFF (float): Exponential backoff factor for retries (default: 2.0)

Change Log:
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
import time
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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
    import os

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
    import os

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
