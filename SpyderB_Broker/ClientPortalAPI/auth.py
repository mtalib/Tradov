#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: SpyderB_Broker/ClientPortalAPI/auth.py
Purpose: Authentication for Client Portal Web API
Author: Mohamed Talib
Last Updated: 2025-11-08

Module Description:
    Handles authentication for IBKR Client Portal Web API using:
    - OAuth 2.0 with private_key_jwt (production/institutional)
    - CP Gateway authentication (development/paper trading)

References:
    - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md
    - https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/
"""

import os
import time
import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

# JWT for OAuth 2.0
try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    HAS_JWT = True
except ImportError:
    HAS_JWT = False
    logging.warning("JWT libraries not available. Install with: pip install pyjwt cryptography")

logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION CLASSES
# ==============================================================================

@dataclass
class OAuthConfig:
    """OAuth 2.0 configuration"""
    consumer_key: str
    private_key_path: str
    token_url: str = "https://api.ibkr.com/v1/oauth2/token"
    algorithm: str = "RS256"
    token_expiry_buffer: int = 60  # Refresh token 60 seconds before expiry

    def __post_init__(self):
        """Validate configuration"""
        if not self.consumer_key:
            raise ValueError("consumer_key is required")
        if not self.private_key_path:
            raise ValueError("private_key_path is required")
        if not Path(self.private_key_path).exists():
            raise FileNotFoundError(f"Private key not found: {self.private_key_path}")


@dataclass
class CPGatewayConfig:
    """CP Gateway configuration"""
    host: str = "localhost"
    port: int = 5000
    ssl: bool = True
    cacert: Optional[str] = None
    timeout: int = 30

    @property
    def base_url(self) -> str:
        """Get base URL for CP Gateway"""
        protocol = "https" if self.ssl else "http"
        return f"{protocol}://{self.host}:{self.port}/v1/api"


# ==============================================================================
# OAUTH 2.0 CLIENT
# ==============================================================================

class OAuthClient:
    """
    OAuth 2.0 authentication client using private_key_jwt

    This is the RECOMMENDED authentication method for production/institutional accounts.
    It's more secure than client_secret as the secret never leaves your server.

    Usage:
        >>> config = OAuthConfig(
        ...     consumer_key='your_key',
        ...     private_key_path='/path/to/private_key.pem'
        ... )
        >>> client = OAuthClient(config)
        >>> token = client.get_access_token()
        >>> # Use token in Authorization header
        >>> headers = {'Authorization': f'Bearer {token}'}

    References:
        - RFC 7521: JWT Profile for OAuth 2.0 Client Authentication
        - RFC 7523: JWT Profile for OAuth 2.0 Authorization Grants
    """

    def __init__(self, config: OAuthConfig):
        """
        Initialize OAuth client

        Args:
            config: OAuth configuration

        Raises:
            ValueError: If JWT libraries not available
            FileNotFoundError: If private key file not found
        """
        if not HAS_JWT:
            raise ValueError(
                "JWT libraries required for OAuth 2.0. "
                "Install with: pip install pyjwt cryptography"
            )

        self.config = config
        self.private_key = self._load_private_key()
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self.session = requests.Session()

        logger.info(f"OAuth client initialized for consumer: {config.consumer_key[:10]}...")

    def _load_private_key(self):
        """
        Load RSA private key from file

        Returns:
            Private key object

        Raises:
            FileNotFoundError: If key file doesn't exist
            ValueError: If key file is invalid
        """
        key_path = Path(self.config.private_key_path)

        if not key_path.exists():
            raise FileNotFoundError(f"Private key not found: {key_path}")

        try:
            with open(key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,  # Assuming unencrypted key
                    backend=default_backend()
                )
            logger.debug(f"Private key loaded from: {key_path}")
            return private_key

        except Exception as e:
            raise ValueError(f"Failed to load private key: {e}")

    def _create_jwt_assertion(self) -> str:
        """
        Create JWT assertion for token request

        The JWT contains:
        - iss (issuer): Your consumer key
        - sub (subject): Your consumer key
        - aud (audience): Token endpoint URL
        - exp (expiration): 5 minutes from now
        - iat (issued at): Current time
        - jti (JWT ID): Unique identifier

        Returns:
            Signed JWT string

        References:
            - https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/#oauth
        """
        now = int(time.time())

        payload = {
            'iss': self.config.consumer_key,  # Issuer
            'sub': self.config.consumer_key,  # Subject
            'aud': self.config.token_url,     # Audience
            'exp': now + 300,                  # Expiration (5 minutes)
            'iat': now,                        # Issued at
            'jti': f"{self.config.consumer_key}-{now}"  # Unique ID
        }

        # Sign JWT with private key
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.algorithm,
            headers={'kid': self.config.consumer_key}
        )

        logger.debug(f"JWT assertion created, expires at: {datetime.fromtimestamp(now + 300)}")
        return token

    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get access token (with automatic refresh)

        Args:
            force_refresh: Force token refresh even if current token is valid

        Returns:
            Valid access token

        Raises:
            requests.HTTPError: If token request fails
        """
        # Check if current token is still valid
        if not force_refresh and self._is_token_valid():
            logger.debug("Using cached access token")
            return self.access_token

        # Request new token
        logger.info("Requesting new access token...")

        jwt_assertion = self._create_jwt_assertion()

        data = {
            'grant_type': 'client_credentials',
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': jwt_assertion
        }

        try:
            response = self.session.post(
                self.config.token_url,
                data=data,
                timeout=30
            )
            response.raise_for_status()

            token_data = response.json()

            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"Access token obtained, expires at: {self.token_expiry}")
            return self.access_token

        except requests.HTTPError as e:
            logger.error(f"Token request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting token: {e}")
            raise

    def _is_token_valid(self) -> bool:
        """
        Check if current access token is valid

        Returns:
            True if token exists and hasn't expired (with buffer)
        """
        if not self.access_token or not self.token_expiry:
            return False

        # Check if token expires soon (within buffer time)
        now = datetime.now()
        expiry_with_buffer = self.token_expiry - timedelta(seconds=self.config.token_expiry_buffer)

        return now < expiry_with_buffer

    def refresh_token(self) -> str:
        """
        Force refresh of access token

        Returns:
            New access token
        """
        logger.info("Forcing token refresh...")
        return self.get_access_token(force_refresh=True)

    def get_authorization_header(self) -> Dict[str, str]:
        """
        Get Authorization header for API requests

        Returns:
            Dict with Authorization header

        Usage:
            >>> headers = client.get_authorization_header()
            >>> response = requests.get(url, headers=headers)
        """
        token = self.get_access_token()
        return {'Authorization': f'Bearer {token}'}


# ==============================================================================
# CP GATEWAY AUTHENTICATION
# ==============================================================================

class CPGatewayAuth:
    """
    CP Gateway authentication

    This is the simpler authentication method for:
    - Development and testing
    - Individual/retail accounts
    - Paper trading

    The CP Gateway is a Java application that handles authentication
    and routes API requests. You must:
    1. Download and run CP Gateway
    2. Authenticate via browser (username/password + 2FA)
    3. Use this class to communicate with the Gateway

    Usage:
        >>> config = CPGatewayConfig(host='localhost', port=5000)
        >>> auth = CPGatewayAuth(config)
        >>> if auth.is_authenticated():
        ...     print("Gateway is ready!")

    Important:
        - Session lasts up to 24 hours
        - Times out after 6 minutes without activity
        - Must send /tickle every 4-5 minutes to keep alive

    References:
        - https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/
    """

    def __init__(self, config: CPGatewayConfig):
        """
        Initialize CP Gateway authentication

        Args:
            config: Gateway configuration
        """
        self.config = config
        self.session = requests.Session()

        # SSL configuration
        if config.ssl:
            if config.cacert:
                self.session.verify = config.cacert
            else:
                # For self-signed certificates (development only!)
                self.session.verify = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        logger.info(f"CP Gateway auth initialized: {config.base_url}")

    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated with Gateway

        Returns:
            True if authenticated, False otherwise
        """
        try:
            url = f"{self.config.base_url}/iserver/auth/status"
            response = self.session.post(url, timeout=self.config.timeout)
            response.raise_for_status()

            status = response.json()
            authenticated = status.get('authenticated', False)

            if authenticated:
                logger.debug("Gateway session is authenticated")
            else:
                logger.warning("Gateway session is not authenticated")

            return authenticated

        except Exception as e:
            logger.error(f"Failed to check auth status: {e}")
            return False

    def reauthenticate(self) -> bool:
        """
        Re-authenticate with Gateway

        Note: This triggers a browser-based authentication flow.
        The user must complete 2FA in their browser.

        Returns:
            True if re-authentication initiated successfully
        """
        try:
            url = f"{self.config.base_url}/iserver/reauthenticate"
            response = self.session.post(url, timeout=self.config.timeout)
            response.raise_for_status()

            result = response.json()
            logger.info(f"Re-authentication initiated: {result}")
            return True

        except Exception as e:
            logger.error(f"Re-authentication failed: {e}")
            return False

    def logout(self) -> bool:
        """
        Logout from Gateway

        Returns:
            True if logout successful
        """
        try:
            url = f"{self.config.base_url}/logout"
            response = self.session.post(url, timeout=self.config.timeout)
            response.raise_for_status()

            logger.info("Logged out from Gateway")
            return True

        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False

    def get_session(self) -> requests.Session:
        """
        Get the authenticated session

        Returns:
            Requests session with auth cookies

        Usage:
            >>> session = auth.get_session()
            >>> response = session.get(f'{base_url}/portfolio/accounts')
        """
        return self.session


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_oauth_client_from_env() -> OAuthClient:
    """
    Create OAuth client from environment variables

    Required environment variables:
        - IBKR_CONSUMER_KEY: Your OAuth consumer key
        - IBKR_PRIVATE_KEY_PATH: Path to private key file
        - IBKR_OAUTH_TOKEN_URL: (optional) Token endpoint URL

    Returns:
        Configured OAuth client

    Raises:
        ValueError: If required environment variables not set

    Usage:
        >>> # Set environment variables first
        >>> os.environ['IBKR_CONSUMER_KEY'] = 'your_key'
        >>> os.environ['IBKR_PRIVATE_KEY_PATH'] = '/path/to/key.pem'
        >>> client = create_oauth_client_from_env()
    """
    consumer_key = os.getenv('IBKR_CONSUMER_KEY')
    private_key_path = os.getenv('IBKR_PRIVATE_KEY_PATH')
    token_url = os.getenv(
        'IBKR_OAUTH_TOKEN_URL',
        'https://api.ibkr.com/v1/oauth2/token'
    )

    if not consumer_key:
        raise ValueError("IBKR_CONSUMER_KEY environment variable not set")
    if not private_key_path:
        raise ValueError("IBKR_PRIVATE_KEY_PATH environment variable not set")

    config = OAuthConfig(
        consumer_key=consumer_key,
        private_key_path=private_key_path,
        token_url=token_url
    )

    return OAuthClient(config)


def create_gateway_auth_from_env() -> CPGatewayAuth:
    """
    Create CP Gateway auth from environment variables

    Optional environment variables:
        - CP_GATEWAY_HOST: Gateway host (default: localhost)
        - CP_GATEWAY_PORT: Gateway port (default: 5000)
        - CP_GATEWAY_SSL: Use SSL (default: true)
        - CP_GATEWAY_CACERT: Path to CA certificate

    Returns:
        Configured CP Gateway auth

    Usage:
        >>> auth = create_gateway_auth_from_env()
        >>> if auth.is_authenticated():
        ...     print("Ready to trade!")
    """
    config = CPGatewayConfig(
        host=os.getenv('CP_GATEWAY_HOST', 'localhost'),
        port=int(os.getenv('CP_GATEWAY_PORT', '5000')),
        ssl=os.getenv('CP_GATEWAY_SSL', 'true').lower() == 'true',
        cacert=os.getenv('CP_GATEWAY_CACERT')
    )

    return CPGatewayAuth(config)


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================

if __name__ == '__main__':
    """
    Example usage of authentication clients
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
    )

    print("=" * 60)
    print("IBKR Client Portal API - Authentication Examples")
    print("=" * 60)

    # Example 1: CP Gateway Auth (for development)
    print("\n1. CP Gateway Authentication (Development)")
    print("-" * 60)

    try:
        gateway_config = CPGatewayConfig(host='localhost', port=5000)
        gateway_auth = CPGatewayAuth(gateway_config)

        if gateway_auth.is_authenticated():
            print("✅ Gateway is authenticated and ready!")
        else:
            print("❌ Gateway is not authenticated")
            print("   Please open https://localhost:5000 in your browser")
            print("   and complete the login process.")

    except Exception as e:
        print(f"❌ Gateway auth failed: {e}")

    # Example 2: OAuth 2.0 (for production)
    print("\n2. OAuth 2.0 Authentication (Production)")
    print("-" * 60)

    if HAS_JWT:
        print("✅ JWT libraries available")

        # Check if credentials are in environment
        if os.getenv('IBKR_CONSUMER_KEY') and os.getenv('IBKR_PRIVATE_KEY_PATH'):
            try:
                oauth_client = create_oauth_client_from_env()
                token = oauth_client.get_access_token()
                print(f"✅ Access token obtained: {token[:20]}...")
                print(f"   Token expires at: {oauth_client.token_expiry}")

            except Exception as e:
                print(f"❌ OAuth authentication failed: {e}")
        else:
            print("⚠️  OAuth credentials not found in environment")
            print("   Set IBKR_CONSUMER_KEY and IBKR_PRIVATE_KEY_PATH")
    else:
        print("❌ JWT libraries not installed")
        print("   Install with: pip install pyjwt cryptography")

    print("\n" + "=" * 60)
    print("For more information, see:")
    print("  - CLIENT_PORTAL_WEB_API_BEST_PRACTICES.md")
    print("  - https://www.interactivebrokers.com/campus/ibkr-api-page/cpapi-v1/")
    print("=" * 60)
