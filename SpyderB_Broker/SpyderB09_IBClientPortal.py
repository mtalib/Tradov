#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB09_IBClientPortal.py
Group: B (Broker Interface)
Purpose: Interactive Brokers Client Portal Web API interface

Description:
    This module provides a specialized interface to Interactive Brokers Client
    Portal Web API. It handles OAuth-style authentication, session management,
    and provides methods for trading operations, market data retrieval, and
    account management through the web-based Client Portal interface. Designed
    for scenarios where direct Gateway connection is not available.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
import urllib3

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# API endpoints
API_VERSION = "v1"
AUTH_STATUS_ENDPOINT = "/iserver/auth/status"
ACCOUNTS_ENDPOINT = "/iserver/accounts"
POSITIONS_ENDPOINT = "/iserver/account/positions"
MARKET_DATA_ENDPOINT = "/iserver/marketdata/snapshot"
CONTRACT_SEARCH_ENDPOINT = "/iserver/secdef/search"
ORDER_ENDPOINT = "/iserver/account/{account_id}/orders"
LOGOUT_ENDPOINT = "/logout"

# Connection settings
DEFAULT_BASE_URL = "https://localhost:5000"
AUTH_CHECK_INTERVAL = 5  # seconds
MAX_AUTH_WAIT = 300  # 5 minutes
AUTH_LOG_INTERVAL = 30  # Log every 30 seconds

# Market data fields
FIELD_LAST_PRICE = "31"
FIELD_BID = "84"
FIELD_ASK = "86"
DEFAULT_FIELDS = [FIELD_LAST_PRICE, FIELD_BID, FIELD_ASK]

# Disable SSL warnings for local Client Portal
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# ENUMS
# ==============================================================================
class AuthStatus(Enum):
    """Authentication status states"""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATED = "authenticated"
    AUTHENTICATING = "authenticating"
    FAILED = "failed"

class OrderStatus(Enum):
    """Order status states"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
# No additional data structures needed for this module

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBClientPortal:
    """
    Interactive Brokers Client Portal Web API Client.
    
    This class provides a complete interface to IB's Client Portal Web API,
    handling authentication, market data, order management, and account
    operations through HTTP REST endpoints.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        base_url: Base URL for API endpoints
        session: HTTP session for API calls
        authenticated: Authentication status
        account_id: Current account ID
        
    Example:
        >>> client = IBClientPortal()
        >>> client.authenticate()
        >>> positions = client.get_positions()
    """
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, config: Dict = None):
        """Initialize IB Client Portal client."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/{API_VERSION}/api"
        self.config = config or {}
        
        # Session management
        self.session = requests.Session()
        self.session.verify = False  # For local self-signed cert
        
        # Authentication state
        self.authenticated = False
        self.auth_status = AuthStatus.NOT_AUTHENTICATED
        self.auth_expires_at = None
        self.account_id = None
        
        # Event manager (optional)
        self.event_manager = None
        
        self.logger.info(f"{self.__class__.__name__} initialized for {base_url}")
    
    # ==========================================================================
    # PUBLIC METHODS - AUTHENTICATION
    # ==========================================================================
    def authenticate(self, username: str = None, password: str = None) -> bool:
        """
        Authenticate with Client Portal.
        
        Note: Client Portal uses OAuth-style authentication requiring
        manual browser login. Username/password parameters are reserved
        for future use.
        
        Args:
            username: Reserved for future use
            password: Reserved for future use
            
        Returns:
            bool: True if authentication successful
        """
        try:
            # Check if already authenticated
            if self._check_existing_auth():
                return True
            
            # Get current authentication status
            auth_status = self.get_auth_status()
            if auth_status and auth_status.get("authenticated", False):
                self._handle_auth_success(auth_status)
                return True
            
            # Need manual authentication
            self.logger.info("Authentication required - please login via Client Portal web interface")
            self.logger.info(f"Open browser to: {self.base_url}")
            
            # Wait for authentication
            return self._wait_for_authentication()
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            self.auth_status = AuthStatus.FAILED
            return False
    
    def get_auth_status(self) -> Optional[Dict]:
        """
        Get current authentication status.
        
        Returns:
            Dict with authentication details or None
        """
        try:
            response = self.session.get(f"{self.api_base}{AUTH_STATUS_ENDPOINT}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.debug(f"Auth status check failed: {e}")
            return None
    
    def logout(self) -> bool:
        """
        Logout from Client Portal.
        
        Returns:
            bool: True if logout successful
        """
        try:
            response = self.session.post(f"{self.api_base}{LOGOUT_ENDPOINT}")
            response.raise_for_status()
            
            # Reset authentication state
            self.authenticated = False
            self.auth_status = AuthStatus.NOT_AUTHENTICATED
            self.auth_expires_at = None
            self.account_id = None
            
            self.logger.info("Successfully logged out")
            return True
            
        except Exception as e:
            self.logger.error(f"Logout failed: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - ACCOUNT OPERATIONS
    # ==========================================================================
    def get_accounts(self) -> List[Dict]:
        """
        Get account information.
        
        Returns:
            List of account dictionaries
        """
        try:
            if not self._ensure_authenticated():
                return []
            
            response = self.session.get(f"{self.api_base}{ACCOUNTS_ENDPOINT}")
            response.raise_for_status()
            
            accounts = response.json()
            self.logger.debug(f"Retrieved {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            self.logger.error(f"Failed to get accounts: {e}")
            return []
    
    def get_positions(self) -> List[Dict]:
        """
        Get current positions.
        
        Returns:
            List of position dictionaries
        """
        try:
            if not self._ensure_authenticated():
                return []
            
            if not self.account_id:
                self._update_account_id()
            
            if not self.account_id:
                self.logger.error("No account ID available")
                return []
            
            endpoint = POSITIONS_ENDPOINT.format(account_id=self.account_id)
            response = self.session.get(f"{self.api_base}{endpoint}")
            response.raise_for_status()
            
            positions = response.json()
            self.logger.debug(f"Retrieved {len(positions)} positions")
            return positions
            
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            return []
    
    # ==========================================================================
    # PUBLIC METHODS - MARKET DATA
    # ==========================================================================
    def get_market_data(self, symbol: str, fields: List[str] = None) -> Optional[Dict]:
        """
        Get market data for symbol.
        
        Args:
            symbol: Trading symbol
            fields: List of field IDs (default: last, bid, ask)
            
        Returns:
            Dict with market data or None
        """
        try:
            if not self._ensure_authenticated():
                return None
            
            # Default fields for options trading
            if fields is None:
                fields = DEFAULT_FIELDS
            
            # Get contract ID
            contract_id = self._get_contract_id(symbol)
            if not contract_id:
                return None
            
            # Request market data
            params = {
                "conids": contract_id,
                "fields": ",".join(fields)
            }
            
            response = self.session.get(
                f"{self.api_base}{MARKET_DATA_ENDPOINT}",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            self.logger.debug(f"Market data retrieved for {symbol}")
            return self._format_market_data(symbol, data)
            
        except Exception as e:
            self.logger.error(f"Failed to get market data for {symbol}: {e}")
            return None
    
    def search_contracts(self, symbol: str) -> List[Dict]:
        """
        Search for contracts by symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of matching contracts
        """
        try:
            params = {"symbol": symbol}
            response = self.session.get(
                f"{self.api_base}{CONTRACT_SEARCH_ENDPOINT}",
                params=params
            )
            response.raise_for_status()
            
            contracts = response.json()
            self.logger.debug(f"Found {len(contracts)} contracts for {symbol}")
            return contracts
            
        except Exception as e:
            self.logger.error(f"Contract search failed for {symbol}: {e}")
            return []
    
    # ==========================================================================
    # PUBLIC METHODS - ORDER MANAGEMENT
    # ==========================================================================
    def place_order(self, order_data: Dict) -> Optional[Dict]:
        """
        Place an order.
        
        Args:
            order_data: Order details dictionary
            
        Returns:
            Dict with order result or None
        """
        try:
            if not self._ensure_authenticated():
                return None
            
            if not self.account_id:
                self._update_account_id()
            
            if not self.account_id:
                self.logger.error("No account ID available")
                return None
            
            # Place order
            endpoint = ORDER_ENDPOINT.format(account_id=self.account_id)
            response = self.session.post(
                f"{self.api_base}{endpoint}",
                json=order_data
            )
            response.raise_for_status()
            
            result = response.json()
            self.logger.info(f"Order placed: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            return None
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _check_existing_auth(self) -> bool:
        """Check if already authenticated and session valid."""
        if self.authenticated and self.auth_expires_at:
            if datetime.now() < self.auth_expires_at - timedelta(minutes=1):
                self.logger.debug("Already authenticated and session valid")
                return True
        return False
    
    def _wait_for_authentication(self) -> bool:
        """Wait for user to complete authentication."""
        waited = 0
        self.auth_status = AuthStatus.AUTHENTICATING
        
        while waited < MAX_AUTH_WAIT:
            auth_status = self.get_auth_status()
            if auth_status and auth_status.get("authenticated", False):
                self._handle_auth_success(auth_status)
                return True
            
            time.sleep(AUTH_CHECK_INTERVAL)
            waited += AUTH_CHECK_INTERVAL
            
            # Periodic logging
            if waited % AUTH_LOG_INTERVAL == 0:
                self.logger.info(f"Waiting for authentication... ({waited}s)")
        
        self.logger.error("Authentication timeout")
        self.auth_status = AuthStatus.FAILED
        return False
    
    def _handle_auth_success(self, auth_status: Dict):
        """Handle successful authentication."""
        self.authenticated = True
        self.auth_status = AuthStatus.AUTHENTICATED
        self.auth_expires_at = datetime.now() + timedelta(hours=1)  # Estimate
        
        # Get account ID from auth status
        accounts = auth_status.get("accounts", [])
        if accounts:
            self.account_id = accounts[0].get("id")
        
        self.logger.info("Successfully authenticated with Client Portal")
        self.logger.info(f"Account ID: {self.account_id}")
    
    def _ensure_authenticated(self) -> bool:
        """Ensure client is authenticated before API calls."""
        if not self.authenticated:
            self.logger.warning("Not authenticated - attempting authentication")
            return self.authenticate()
        return True
    
    def _update_account_id(self):
        """Update account ID from accounts list."""
        accounts = self.get_accounts()
        if accounts and isinstance(accounts, list) and len(accounts) > 0:
            self.account_id = accounts[0].get("id")
            self.logger.debug(f"Updated account ID: {self.account_id}")
    
    def _get_contract_id(self, symbol: str) -> Optional[int]:
        """Get contract ID for symbol."""
        contracts = self.search_contracts(symbol)
        if not contracts:
            self.logger.error(f"No contracts found for {symbol}")
            return None
        
        contract_id = contracts[0].get("conid")
        if not contract_id:
            self.logger.error(f"No contract ID for {symbol}")
            return None
        
        return contract_id
    
    def _format_market_data(self, symbol: str, raw_data: Dict) -> Dict:
        """Format raw market data response."""
        if not raw_data:
            return {"symbol": symbol}
        
        # Extract first item if list
        if isinstance(raw_data, list) and len(raw_data) > 0:
            raw_data = raw_data[0]
        
        formatted = {
            "symbol": symbol,
            "last": raw_data.get(FIELD_LAST_PRICE),
            "bid": raw_data.get(FIELD_BID),
            "ask": raw_data.get(FIELD_ASK),
            "timestamp": datetime.now().isoformat()
        }
        
        return formatted
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the client portal interface."""
        self.logger.info("Client Portal interface started")
    
    def stop(self) -> None:
        """Stop the client portal interface."""
        if self.authenticated:
            self.logout()
        self.session.close()
        self.logger.info("Client Portal interface stopped")
    
    def cleanup(self) -> None:
        """Clean up client resources."""
        self.stop()
        self.logger.info("Client Portal cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_client_portal_client(config: Dict = None) -> IBClientPortal:
    """
    Get IBClientPortal instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        IBClientPortal instance
    """
    if config is None:
        from SpyderA_Core.SpyderA03_Configuration import get_config_manager
        config_manager = get_config_manager()
        config = config_manager.get_config()
    
    base_url = config.get("ib", {}).get("client_portal", {}).get("base_url", DEFAULT_BASE_URL)
    return IBClientPortal(base_url, config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
__all__ = [
    'IBClientPortal',
    'get_client_portal_client',
    'AuthStatus',
    'OrderStatus'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    client = IBClientPortal()
    
    print("✅ IBClientPortal created successfully")
    
    # Test authentication status
    auth_status = client.get_auth_status()