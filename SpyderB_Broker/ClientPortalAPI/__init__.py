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
    - auth: Authentication and session management (OAuth 2.0, CP Gateway)
    - session: Session lifecycle and tickle keepalive
    - rate_limiter: Request rate limiting and throttling
    - rest_client: Synchronous REST API client
    - websocket_client: Asynchronous WebSocket client for real-time data
    - market_data: Market data subscription manager
    - order_manager: Order placement, modification, cancellation
    - position_tracker: Position and portfolio tracking
    - account_manager: Account information and management

API Documentation:
    https://interactivebrokers.github.io/cpwebapi/
"""

__version__ = "1.0.0"
__author__ = "Mohamed Talib"

# Import available components
from .rate_limiter import RateLimiter, AdaptiveRateLimiter, create_cp_gateway_limiter, create_oauth_limiter
from .auth import OAuthClient, CPGatewayAuth, OAuthConfig, CPGatewayConfig, create_oauth_client_from_env, create_gateway_auth_from_env

# These will be imported as they're implemented
# from .session import SessionManager
# from .rest_client import ClientPortalRESTClient
# from .websocket_client import ClientPortalWebSocket
# from .market_data import MarketDataManager
# from .order_manager import OrderManager, Order, OrderSide, OrderType
# from .position_tracker import PositionTracker
# from .account_manager import AccountManager

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
    # To be added as implemented:
    # 'SessionManager',
    # 'ClientPortalRESTClient',
    # 'ClientPortalWebSocket',
    # 'MarketDataManager',
    # 'OrderManager',
    # 'Order',
    # 'OrderSide',
    # 'OrderType',
    # 'PositionTracker',
    # 'AccountManager',
]
