#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: SpyderB_Broker/ClientPortalAPI/rest_client.py
Purpose: REST API client for Client Portal Web API
Author: Mohamed Talib
Last Updated: 2025-11-08

Module Description:
    Complete REST API client for IBKR Client Portal Web API with:
    - Automatic rate limiting
    - Retry logic with exponential backoff
    - Connection pooling
    - Error handling and recovery
    - Session management integration

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://interactivebrokers.github.io/cpwebapi/
"""

import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .session import SessionManager
from .rate_limiter import AdaptiveRateLimiter
from .auth import OAuthClient, CPGatewayAuth

logger = logging.getLogger(__name__)


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class APIError(Exception):
    """Base API error"""
    pass


class AuthenticationError(APIError):
    """Authentication failure"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded"""
    pass


class ValidationError(APIError):
    """Request validation failed"""
    pass


class ConnectionError(APIError):
    """Connection failed"""
    pass


# ==============================================================================
# CLIENT CONFIGURATION
# ==============================================================================

@dataclass
class ClientConfig:
    """REST client configuration"""
    # Retry configuration
    max_retries: int = 3
    backoff_factor: float = 2.0  # 2^0, 2^1, 2^2 = 1s, 2s, 4s
    retry_on_status: List[int] = None  # Retry on these status codes

    # Connection pooling
    pool_connections: int = 10
    pool_maxsize: int = 20
    pool_block: bool = False

    # Timeouts
    connect_timeout: int = 10
    read_timeout: int = 30

    # Rate limiting
    use_rate_limiter: bool = True
    rate_limit: int = 10  # Will be overridden based on auth method

    def __post_init__(self):
        if self.retry_on_status is None:
            self.retry_on_status = [429, 500, 502, 503, 504]


# ==============================================================================
# REST CLIENT
# ==============================================================================

class ClientPortalRESTClient:
    """
    Complete REST API client for IBKR Client Portal

    Features:
    - Automatic rate limiting (10 req/s Gateway, 50 req/s OAuth)
    - Retry logic with exponential backoff
    - Connection pooling for performance
    - Session management integration
    - Comprehensive error handling

    Usage with OAuth:
        >>> from SpyderB_Broker.ClientPortalAPI import (
        ...     OAuthClient, SessionManager, ClientPortalRESTClient
        ... )
        >>> oauth = OAuthClient(oauth_config)
        >>> session_mgr = SessionManager(oauth, base_url)
        >>> session_mgr.start()
        >>>
        >>> client = ClientPortalRESTClient(session_mgr)
        >>> accounts = client.get('/portfolio/accounts')

    Usage with CP Gateway:
        >>> from SpyderB_Broker.ClientPortalAPI import (
        ...     CPGatewayAuth, SessionManager, ClientPortalRESTClient
        ... )
        >>> auth = CPGatewayAuth(gateway_config)
        >>> session_mgr = SessionManager(auth, auth.config.base_url)
        >>> session_mgr.start()
        >>>
        >>> client = ClientPortalRESTClient(session_mgr)
        >>> positions = client.get('/portfolio/DU123456/positions')

    Important:
        - Always use SessionManager, don't pass raw session
        - Rate limiting is automatic
        - Retries handle transient errors
        - Session tickle is automatic via SessionManager
    """

    def __init__(
        self,
        session_manager: SessionManager,
        config: Optional[ClientConfig] = None,
        rate_limiter: Optional[AdaptiveRateLimiter] = None
    ):
        """
        Initialize REST client

        Args:
            session_manager: SessionManager instance
            config: Client configuration (optional)
            rate_limiter: Rate limiter instance (optional, will create if needed)
        """
        self.session_mgr = session_manager
        self.config = config or ClientConfig()

        # Determine rate limit based on auth method
        if isinstance(session_manager.auth_client, OAuthClient):
            self.config.rate_limit = 50  # OAuth: 50 req/sec
            logger.info("Using OAuth rate limit: 50 req/sec")
        else:
            self.config.rate_limit = 10  # Gateway: 10 req/sec
            logger.info("Using CP Gateway rate limit: 10 req/sec")

        # Rate limiter
        if rate_limiter:
            self.rate_limiter = rate_limiter
        elif self.config.use_rate_limiter:
            self.rate_limiter = AdaptiveRateLimiter(
                initial_rate=self.config.rate_limit,
                per_seconds=1
            )
        else:
            self.rate_limiter = None

        # Get session from manager
        self.session = session_manager.get_session()

        # Setup connection pooling and retries
        self._setup_session()

        # Statistics
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.retry_count = 0

        logger.info(f"REST client initialized: {session_manager.base_url}")

    def _setup_session(self):
        """Setup session with connection pooling and retry logic"""
        # Retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=self.config.retry_on_status,
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
            raise_on_status=False  # We'll handle status codes manually
        )

        # HTTP adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.pool_connections,
            pool_maxsize=self.config.pool_maxsize,
            pool_block=self.config.pool_block
        )

        # Mount adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.debug("Session configured with connection pooling and retry logic")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with rate limiting and error handling

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/portfolio/accounts')
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit exceeded (after retries)
            ValidationError: If request validation fails
            APIError: For other API errors
        """
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        url = f"{self.session_mgr.base_url}{endpoint}"

        # Apply rate limiting
        if self.rate_limiter:
            self.rate_limiter.acquire()

        # Set timeout if not specified
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (self.config.connect_timeout, self.config.read_timeout)

        # Track request
        self.request_count += 1

        try:
            # Make request
            response = self.session.request(method, url, **kwargs)

            # Handle status codes
            if response.status_code == 401:
                # Authentication error
                self.error_count += 1
                raise AuthenticationError(
                    f"Authentication failed: {response.status_code} - {response.text}"
                )

            elif response.status_code == 429:
                # Rate limit exceeded
                self.error_count += 1

                # Tell rate limiter to back off
                if self.rate_limiter:
                    self.rate_limiter.handle_rate_limit_error()

                raise RateLimitError(
                    f"Rate limit exceeded: {response.status_code} - {response.text}"
                )

            elif response.status_code == 400:
                # Bad request - validation error
                self.error_count += 1
                raise ValidationError(
                    f"Invalid request: {response.status_code} - {response.text}"
                )

            elif response.status_code >= 500:
                # Server error
                self.error_count += 1
                raise APIError(
                    f"Server error: {response.status_code} - {response.text}"
                )

            elif response.status_code >= 400:
                # Other client error
                self.error_count += 1
                raise APIError(
                    f"API error: {response.status_code} - {response.text}"
                )

            # Success
            self.success_count += 1

            # Tell rate limiter about success
            if self.rate_limiter:
                self.rate_limiter.handle_success()

            return response

        except requests.exceptions.Timeout as e:
            self.error_count += 1
            raise ConnectionError(f"Request timeout: {e}")

        except requests.exceptions.ConnectionError as e:
            self.error_count += 1
            raise ConnectionError(f"Connection failed: {e}")

        except (AuthenticationError, RateLimitError, ValidationError, APIError):
            # Re-raise our custom exceptions
            raise

        except Exception as e:
            self.error_count += 1
            raise APIError(f"Unexpected error: {e}")

    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs) -> Any:
        """
        GET request

        Args:
            endpoint: API endpoint
            params: Query parameters
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response

        Example:
            >>> accounts = client.get('/portfolio/accounts')
            >>> positions = client.get('/portfolio/DU123456/positions')
        """
        response = self._make_request('GET', endpoint, params=params, **kwargs)
        return response.json() if response.content else None

    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        **kwargs
    ) -> Any:
        """
        POST request

        Args:
            endpoint: API endpoint
            data: Form data
            json: JSON data
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response

        Example:
            >>> order = {'symbol': 'SPY', 'action': 'BUY', 'quantity': 100}
            >>> result = client.post('/iserver/account/DU123456/orders', json={'orders': [order]})
        """
        response = self._make_request('POST', endpoint, data=data, json=json, **kwargs)
        return response.json() if response.content else None

    def delete(self, endpoint: str, **kwargs) -> Any:
        """
        DELETE request

        Args:
            endpoint: API endpoint
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response

        Example:
            >>> client.delete('/iserver/account/DU123456/order/123456')
        """
        response = self._make_request('DELETE', endpoint, **kwargs)
        return response.json() if response.content else None

    def put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        **kwargs
    ) -> Any:
        """
        PUT request

        Args:
            endpoint: API endpoint
            data: Form data
            json: JSON data
            **kwargs: Additional arguments

        Returns:
            Parsed JSON response
        """
        response = self._make_request('PUT', endpoint, data=data, json=json, **kwargs)
        return response.json() if response.content else None

    # ==========================================================================
    # CONVENIENCE METHODS - Common API operations
    # ==========================================================================

    def get_accounts(self) -> List[Dict]:
        """
        Get portfolio accounts

        Returns:
            List of account information

        Example:
            >>> accounts = client.get_accounts()
            >>> for account in accounts:
            ...     print(f"Account: {account['id']}")
        """
        return self.get('/portfolio/accounts')

    def get_positions(self, account_id: str) -> List[Dict]:
        """
        Get positions for an account

        Args:
            account_id: Account ID

        Returns:
            List of positions
        """
        return self.get(f'/portfolio/{account_id}/positions')

    def get_account_summary(self, account_id: str) -> Dict:
        """
        Get account summary

        Args:
            account_id: Account ID

        Returns:
            Account summary data
        """
        return self.get(f'/portfolio/{account_id}/summary')

    def get_market_data_snapshot(
        self,
        conids: List[int],
        fields: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        Get market data snapshot

        Args:
            conids: List of contract IDs
            fields: List of field IDs (optional)

        Returns:
            Market data for requested contracts

        Example:
            >>> # SPY contract ID: 756733
            >>> data = client.get_market_data_snapshot([756733], fields=[31, 84, 86])
            >>> # Field 31=last, 84=bid, 86=ask
        """
        params = {
            'conids': ','.join(map(str, conids))
        }
        if fields:
            params['fields'] = ','.join(map(str, fields))

        return self.get('/iserver/marketdata/snapshot', params=params)

    def place_order(
        self,
        account_id: str,
        orders: List[Dict]
    ) -> Dict:
        """
        Place one or more orders

        Args:
            account_id: Account ID
            orders: List of order definitions

        Returns:
            Order placement response

        Example:
            >>> orders = [{
            ...     'conid': 756733,  # SPY
            ...     'orderType': 'LMT',
            ...     'side': 'BUY',
            ...     'quantity': 100,
            ...     'price': 585.00,
            ...     'tif': 'DAY'
            ... }]
            >>> result = client.place_order('DU123456', orders)
        """
        return self.post(
            f'/iserver/account/{account_id}/orders',
            json={'orders': orders}
        )

    def cancel_order(self, account_id: str, order_id: str) -> Dict:
        """
        Cancel an order

        Args:
            account_id: Account ID
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        return self.delete(f'/iserver/account/{account_id}/order/{order_id}')

    def get_live_orders(self, account_id: Optional[str] = None) -> Dict:
        """
        Get live orders

        Args:
            account_id: Account ID (optional)

        Returns:
            Live orders
        """
        params = {'accountId': account_id} if account_id else {}
        return self.get('/iserver/account/orders', params=params)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get client statistics

        Returns:
            Dict with request statistics
        """
        stats = {
            'total_requests': self.request_count,
            'successful_requests': self.success_count,
            'failed_requests': self.error_count,
            'retry_count': self.retry_count,
            'success_rate': (
                self.success_count / self.request_count * 100
                if self.request_count > 0 else 0
            )
        }

        # Add rate limiter stats if available
        if self.rate_limiter:
            limiter_stats = self.rate_limiter.get_stats()
            stats['rate_limiter'] = limiter_stats

        return stats

    def __repr__(self) -> str:
        return (
            f"ClientPortalRESTClient("
            f"requests={self.request_count}, "
            f"success_rate={self.success_count/max(self.request_count,1)*100:.1f}%)"
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """Example usage of REST client"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
    )

    print("=" * 60)
    print("IBKR Client Portal API - REST Client Example")
    print("=" * 60)

    try:
        from .auth import CPGatewayAuth, CPGatewayConfig
        from .session import SessionManager

        # Setup authentication
        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        auth = CPGatewayAuth(gateway_config)

        # Create session manager
        session_mgr = SessionManager(auth, gateway_config.base_url)
        session_mgr.start()

        # Create REST client
        client = ClientPortalRESTClient(session_mgr)

        print("\n✅ REST client initialized")
        print(f"Rate limit: {client.config.rate_limit} req/sec")

        # Example: Get accounts
        print("\nFetching accounts...")
        try:
            accounts = client.get_accounts()
            print(f"Found {len(accounts)} accounts:")
            for account in accounts:
                print(f"  - {account.get('id')}: {account.get('type')}")
        except Exception as e:
            print(f"❌ Error fetching accounts: {e}")

        # Example: Get market data
        print("\nFetching market data for SPY...")
        try:
            spy_data = client.get_market_data_snapshot(
                conids=[756733],  # SPY
                fields=[31, 84, 86]  # last, bid, ask
            )
            print(f"SPY data: {spy_data}")
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")

        # Show statistics
        print("\nClient statistics:")
        stats = client.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Cleanup
        session_mgr.stop()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("=" * 60)
