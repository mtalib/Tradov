#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker/ClientPortalAPI
Purpose: Client Portal Web API implementation for IBKR connectivity
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-08

Module Description:
    This package provides a complete Client Portal Web API implementation for
    Interactive Brokers, replacing the legacy TWS API (ib_async) with a modern
    REST + WebSocket architecture.

Components:
    - SpyderB09_ClientPortal_Auth: Authentication (OAuth 2.0, CP Gateway)
    - SpyderB09_ClientPortal_Session: Session lifecycle and tickle keepalive
    - SpyderB09_ClientPortal_RateLimiter: Request rate limiting and throttling
    - SpyderB09_ClientPortal_RESTClient: Synchronous REST API client
    - SpyderB09_ClientPortal_WebSocket: WebSocket client for real-time streaming
    - SpyderB09_ClientPortal_MarketData: Unified market data manager
    - SpyderB09_ClientPortal_Examples: Usage examples and demonstrations

API Documentation:
    https://interactivebrokers.github.io/cpwebapi/
"""

__version__ = "1.0.0"
__author__ = "Mohamed Talib"

# Import available components
from .SpyderB09_ClientPortal_RateLimiter import (
    RateLimiter,
    AdaptiveRateLimiter,
    create_cp_gateway_limiter,
    create_oauth_limiter
)

from .SpyderB09_ClientPortal_Auth import (
    OAuthClient,
    CPGatewayAuth,
    OAuthConfig,
    CPGatewayConfig,
    create_oauth_client_from_env,
    create_gateway_auth_from_env
)

from .SpyderB09_ClientPortal_Session import (
    SessionManager,
    SessionConfig
)

from .SpyderB09_ClientPortal_RESTClient import (
    ClientPortalRESTClient,
    ClientConfig,
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError
)

from .SpyderB09_ClientPortal_WebSocket import (
    ClientPortalWebSocket,
    WebSocketConfig,
    SubscriptionType,
    ConnectionState,
    WS_PROD_URL,
    WS_PAPER_URL
)

from .SpyderB09_ClientPortal_MarketData import (
    MarketDataManager,
    MarketDataConfig,
    Quote,
    Bar
)

__all__ = [
    # Rate limiting
    'RateLimiter',
    'AdaptiveRateLimiter',
    'create_cp_gateway_limiter',
    'create_oauth_limiter',
    # Authentication
    'OAuthClient',
    'CPGatewayAuth',
    'OAuthConfig',
    'CPGatewayConfig',
    'create_oauth_client_from_env',
    'create_gateway_auth_from_env',
    # Session Management
    'SessionManager',
    'SessionConfig',
    # REST Client
    'ClientPortalRESTClient',
    'ClientConfig',
    'APIError',
    'AuthenticationError',
    'RateLimitError',
    'ValidationError',
    # WebSocket
    'ClientPortalWebSocket',
    'WebSocketConfig',
    'SubscriptionType',
    'ConnectionState',
    'WS_PROD_URL',
    'WS_PAPER_URL',
    # Market Data
    'MarketDataManager',
    'MarketDataConfig',
    'Quote',
    'Bar',
]
