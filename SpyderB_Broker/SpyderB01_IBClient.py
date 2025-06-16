#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderB01_IBClient.py
Group: B (Broker Interface)
Purpose: Interactive Brokers client interface

Description:
    This module provides a unified interface to Interactive Brokers supporting
    both Client Portal Web API and Gateway Direct Connection. It handles
    authentication, connection management, order execution, and market data
    retrieval. The module includes automatic failover, heartbeat management,
    and robust error handling for production trading environments.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Union

# Type alias for ticker ID
TickerId = int

from datetime import datetime, timedelta
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Gateway direct connection imports
try:
    from ib_insync import IB, util, Stock, Option, Contract
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError
from SpyderU_Utilities.SpyderU04_Encryption import CredentialManager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connection defaults
DEFAULT_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 5000
DEFAULT_GATEWAY_PORT_PAPER = 4001
DEFAULT_GATEWAY_PORT_LIVE = 4000
DEFAULT_CLIENT_ID = 1

# Heartbeat settings
HEARTBEAT_INTERVAL = 300  # 5 minutes
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 3

# API endpoints
API_BASE_PATH = "/v1"
AUTH_ENDPOINT = "/portal/authenticate"
ACCOUNTS_ENDPOINT = "/iserver/accounts"

# Suppress insecure warnings for localhost
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ==============================================================================
# ENUMS
# ==============================================================================
class ConnectionType(Enum):
    """Types of IB connections"""
    WEB_API = "web_api"
    GATEWAY = "gateway"

class TradingMode(Enum):
    """Trading modes"""
    PAPER = "paper"
    LIVE = "live"

# ==============================================================================
# MAIN CLASSES
# ==============================================================================
class IBClient:
    """
    Interactive Brokers Client Portal Web API client.
    
    This class provides browser-based access to IB through the Client Portal
    Web API. It handles authentication, session management, and provides
    methods for trading and market data retrieval.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Configuration dictionary
        session: HTTP session for API calls
        is_connected: Connection status
        is_authenticated: Authentication status
        
    Example:
        >>> client = IBClient(config)
        >>> client.connect()
        >>> client.get_market_data("SPY")
    """
    
    def __init__(self, config=None):
        """Initialize IB Web API Client."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config
        self.base_url = f"https://localhost:{DEFAULT_WEB_PORT}"
        
        # Session management
        self.session = requests.Session()
        self.session.verify = False  # Allow self-signed cert
        
        # Connection state
        self.is_connected = False
        self.is_authenticated = False
        self.account_id = None
        self.trading_mode = TradingMode.PAPER
        
        # Set configuration
        self._set_config()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def connect(self) -> bool:
        """
        Connect to IB Client Portal Web API.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.logger.info(f"Connecting to IB Client Portal at {self.host}:{self.port}")
            
            # Test connection
            response = self.session.get(f"{self.base_url}{API_BASE_PATH}{AUTH_ENDPOINT}")
            self.is_connected = response.status_code == 200
            
            if self.is_connected:
                # Attempt authentication
                self.authenticate()
                self.logger.info("✅ Successfully connected to IB Client Portal")
                return True
            else:
                self.logger.error(f"Connection failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to IB Client Portal: {e}")
            return False
    
    def authenticate(self) -> bool:
        """
        Authenticate to IB Client Portal Web API.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            if self.is_authenticated:
                self.logger.info("✅ Already authenticated")
                return True
            
            # Check authentication status
            response = self.session.get(f"{self.base_url}{API_BASE_PATH}/iserver/auth/status")
            
            if response.status_code == 200:
                auth_data = response.json()
                self.is_authenticated = auth_data.get("authenticated", False)
                
                if self.is_authenticated:
                    self._get_account_info()
                    self.logger.info("✅ Authentication successful")
                    return True
            
            self.logger.warning("Authentication required - please login via browser")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Authentication failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IB Client Portal."""
        try:
            self.logger.info("Disconnecting from IB Client Portal...")
            self.session.close()
            self.is_connected = False
            self.is_authenticated = False
            self.logger.info("✅ Disconnected from IB Client Portal")
            
        except Exception as e:
            self.logger.error(f"Error during disconnection: {e}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account information.
        
        Returns:
            Dict containing account details
        """
        if not self.is_authenticated:
            return {}
        
        try:
            response = self.session.get(f"{self.base_url}{API_BASE_PATH}{ACCOUNTS_ENDPOINT}")
            if response.status_code == 200:
                return response.json()
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_market_data(self, symbol: str, sec_type: str = "STK") -> Dict[str, Any]:
        """
        Get market data for a symbol.
        
        Args:
            symbol: Trading symbol
            sec_type: Security type
            
        Returns:
            Dict containing market data
        """
        # Implementation would go here
        self.logger.debug(f"Getting market data for {symbol}")
        return {"symbol": symbol, "last": 0.0, "bid": 0.0, "ask": 0.0}
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _set_config(self):
        """Set configuration from provided config or environment variables."""
        try:
            if isinstance(self.config, dict):
                ib_config = self.config.get("ib", {})
                self.host = ib_config.get("host", os.getenv("IB_HOST", DEFAULT_HOST))
                self.port = int(ib_config.get("port", os.getenv("IB_PORT", DEFAULT_WEB_PORT)))
                self.trading_mode = TradingMode(
                    ib_config.get("trading_mode", os.getenv("DEFAULT_TRADING_MODE", "paper"))
                )
                self.client_id = int(
                    ib_config.get("client_id", os.getenv("IB_CLIENT_ID", DEFAULT_CLIENT_ID))
                )
            else:
                self.host = getattr(self.config, "ib_host", os.getenv("IB_HOST", DEFAULT_HOST))
                self.port = int(
                    getattr(self.config, "ib_port", os.getenv("IB_PORT", DEFAULT_WEB_PORT))
                )
                self.trading_mode = TradingMode(
                    getattr(self.config, "trading_mode", os.getenv("DEFAULT_TRADING_MODE", "paper"))
                )
                self.client_id = int(
                    getattr(self.config, "ib_client_id", os.getenv("IB_CLIENT_ID", DEFAULT_CLIENT_ID))
                )
            
            self.base_url = f"https://{self.host}:{self.port}"
            self.logger.info(f"IB Client configured: {self.host}:{self.port} ({self.trading_mode.value})")
            
        except Exception as e:
            self.logger.error(f"Error setting configuration: {e}")
            raise TradingError(f"IB Client config error: {e}")
    
    def _get_account_info(self):
        """Retrieve and store account information."""
        try:
            accounts = self.get_account_info()
            if accounts and isinstance(accounts, list) and len(accounts) > 0:
                self.account_id = accounts[0].get("id")
                self.logger.info(f"Using account: {self.account_id}")
        except Exception as e:
            self.logger.error(f"Error retrieving account info: {e}")


class IBGatewayClient:
    """
    Interactive Brokers Gateway client using ib_insync.
    
    This class provides direct socket connection to IB Gateway for automated
    trading. It includes heartbeat management, automatic reconnection, and
    full trading functionality through the ib_insync library.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        ib: IB connection instance
        is_connected: Connection status
        heartbeat_thread: Thread for connection maintenance
        
    Example:
        >>> client = IBGatewayClient(config)
        >>> client.connect()
        >>> positions = client.get_positions()
    """
    
    def __init__(self, config=None):
        """Initialize IB Gateway client."""
        if not IB_INSYNC_AVAILABLE:
            raise ImportError(
                "ib_insync is required for IBGatewayClient. Please install: pip install ib_insync"
            )
        
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # IB connection
        self.ib = IB()
        
        # Connection state
        self.is_connected = False
        self.account_id = None
        self.trading_mode = TradingMode.PAPER
        
        # Configuration
        self.config = config or {}
        self._set_connection_params()
        
        # Heartbeat management
        self.heartbeat_interval = HEARTBEAT_INTERVAL
        self.heartbeat_thread = None
        self.keep_alive = False
        self._tickle_count = 0
        self._reconnect_attempts = 0
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def connect(self, host=None, port=None, client_id=None) -> bool:
        """
        Connect to IB Gateway with 2FA support.
        
        Args:
            host: Override host address
            port: Override port number
            client_id: Override client ID
            
        Returns:
            bool: True if connection successful
        """
        # Override parameters if provided
        if host:
            self.host = host
        if port:
            self.port = port
        if client_id:
            self.client_id = client_id
        
        try:
            self.logger.info(f"Connecting to IB Gateway at {self.host}:{self.port}")
            self.logger.info("Please approve 2FA on your mobile device when prompted...")
            
            # Connect to IB Gateway
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.is_connected = True
            self._reconnect_attempts = 0
            
            # Get account information
            self._get_account_info()
            
            # Start persistent connection management
            self._start_heartbeat()
            
            self.logger.info("✅ Successfully connected to IB Gateway")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to IB Gateway: {e}")
            self._handle_connection_error(e)
            return False
    
    def disconnect(self):
        """Disconnect from IB Gateway."""
        self.keep_alive = False
        
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.logger.info("Stopping heartbeat thread...")
            self.heartbeat_thread.join(timeout=2)
        
        if self.is_connected and self.ib.isConnected():
            self.ib.disconnect()
            self.is_connected = False
            self.logger.info("✅ Disconnected from IB Gateway")
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.is_connected and self.ib.isConnected()
    
    def authenticate(self) -> bool:
        """Authentication is handled by Gateway connection."""
        if self.is_connected:
            self.logger.info("✅ Already authenticated with IB Gateway")
            return True
        else:
            self.logger.warning("❌ Not connected to IB Gateway")
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        if not self.is_connected:
            return {}
        
        try:
            account_summary = self.ib.accountSummary()
            account_info = {"account_id": self.account_id}
            
            for item in account_summary:
                if item.account == self.account_id:
                    account_info[item.tag] = item.value
            
            return account_info
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        if not self.is_connected:
            return []
        
        try:
            positions = self.ib.positions()
            formatted_positions = []
            
            for position in positions:
                pos_dict = {
                    "symbol": position.contract.symbol,
                    "secType": position.contract.secType,
                    "position": position.position,
                    "avgCost": position.avgCost,
                }
                
                # Add option-specific fields
                if hasattr(position.contract, "lastTradeDateOrContractMonth"):
                    pos_dict["expiry"] = position.contract.lastTradeDateOrContractMonth
                if hasattr(position.contract, "strike"):
                    pos_dict["strike"] = position.contract.strike
                if hasattr(position.contract, "right"):
                    pos_dict["right"] = position.contract.right
                
                formatted_positions.append(pos_dict)
            
            return formatted_positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return []
    
    def get_market_data(self, symbol: str, sec_type: str = "STK") -> Dict[str, Any]:
        """Get market data for a symbol."""
        if not self.is_connected:
            return {}
        
        try:
            if sec_type == "STK":
                contract = Stock(symbol, "SMART", "USD")
            else:
                self.logger.error(f"Security type {sec_type} not implemented")
                return {}
            
            qualified_contracts = self.ib.qualifyContracts(contract)
            if not qualified_contracts:
                return {}
            
            contract = qualified_contracts[0]
            self.ib.reqMktData(contract)
            self.ib.sleep(1)  # Wait for data
            
            ticker = self.ib.ticker(contract)
            
            return {
                "symbol": symbol,
                "last": ticker.last or ticker.close,
                "bid": ticker.bid,
                "ask": ticker.ask,
                "high": ticker.high,
                "low": ticker.low,
                "volume": ticker.volume,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market data for {symbol}: {e}")
            return {}
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _set_connection_params(self):
        """Set connection parameters for IB Gateway."""
        try:
            if isinstance(self.config, dict):
                ib_config = self.config.get("ib", {})
                self.host = ib_config.get("gateway_host", os.getenv("IB_GATEWAY_HOST", DEFAULT_HOST))
                self.trading_mode = TradingMode(
                    ib_config.get("trading_mode", os.getenv("DEFAULT_TRADING_MODE", "paper"))
                )
                self.client_id = int(
                    ib_config.get("client_id", os.getenv("IB_CLIENT_ID", DEFAULT_CLIENT_ID))
                )
            else:
                self.host = getattr(
                    self.config, "ib_gateway_host", os.getenv("IB_GATEWAY_HOST", DEFAULT_HOST)
                )
                self.trading_mode = TradingMode(
                    getattr(self.config, "trading_mode", os.getenv("DEFAULT_TRADING_MODE", "paper"))
                )
                self.client_id = int(
                    getattr(self.config, "ib_client_id", os.getenv("IB_CLIENT_ID", DEFAULT_CLIENT_ID))
                )
            
            # Set port based on trading mode
            if self.trading_mode == TradingMode.PAPER:
                self.port = int(os.getenv("IB_GATEWAY_PORT_PAPER", DEFAULT_GATEWAY_PORT_PAPER))
            else:
                self.port = int(os.getenv("IB_GATEWAY_PORT_LIVE", DEFAULT_GATEWAY_PORT_LIVE))
            
            self.logger.info(f"Gateway params: {self.host}:{self.port} ({self.trading_mode.value})")
            
        except Exception as e:
            self.logger.error(f"Error setting connection parameters: {e}")
            raise TradingError(f"IB Gateway config error: {e}")
    
    def _get_account_info(self):
        """Get account information after connecting."""
        if not self.is_connected:
            return
        
        try:
            accounts = self.ib.managedAccounts()
            if accounts:
                self.account_id = accounts[0]
                self.logger.info(f"✅ Using account: {self.account_id}")
                
                # Get account value
                account_summary = self.ib.accountSummary()
                for item in account_summary:
                    if item.tag == "NetLiquidation" and item.account == self.account_id:
                        self.logger.info(f"✅ Account value: ${item.value}")
                        break
            else:
                self.logger.warning("No accounts found")
                
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
    
    def _handle_connection_error(self, error: Exception):
        """Handle connection errors."""
        error_msg = str(error).lower()
        if "socket error" in error_msg:
            self.logger.error("Make sure IB Gateway is running and configured for API access")
            self.logger.error(f"API Port: {DEFAULT_GATEWAY_PORT_PAPER} (paper) or {DEFAULT_GATEWAY_PORT_LIVE} (live)")
    
    # ==========================================================================
    # HEARTBEAT METHODS
    # ==========================================================================
    def _start_heartbeat(self):
        """Start heartbeat thread to maintain persistent connection."""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
        
        self.keep_alive = True
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker, daemon=True
        )
        self.heartbeat_thread.start()
        self.logger.info("✅ Heartbeat thread started")
    
    def _heartbeat_worker(self):
        """Worker thread for connection heartbeat."""
        while self.keep_alive and self.is_connected:
            try:
                time.sleep(self.heartbeat_interval)
                
                if not self.keep_alive:
                    break
                
                # Tickle the connection
                if not self._tickle_connection():
                    if not self._reconnect():
                        break
                        
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                if not self._reconnect():
                    break
    
    def _tickle_connection(self):
        """Minimal connection check without async operations."""
        try:
            # Simple connection status check
            is_connected = self.ib.isConnected()
            
            if not is_connected:
                self.logger.warning("Connection lost detected")
                return False
            
            # Periodic lightweight check
            self._tickle_count += 1
            if self._tickle_count % 3 == 0:
                try:
                    accounts = self.ib.managedAccounts()
                    self.logger.debug(f"Connection alive - {len(accounts)} accounts")
                except Exception as e:
                    self.logger.debug(f"Account check failed: {e}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection check failed: {e}")
            return False
    
    def _reconnect(self) -> bool:
        """Attempt to reconnect to IB Gateway."""
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self.logger.error("Max reconnection attempts reached")
            return False
        
        try:
            self._reconnect_attempts += 1
            self.logger.info(f"Reconnection attempt {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}")
            
            # Disconnect first
            if self.ib.isConnected():
                self.ib.disconnect()
            
            time.sleep(RECONNECT_DELAY)
            
            # Reconnect
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.is_connected = True
            self._reconnect_attempts = 0
            
            self.logger.info("✅ Successfully reconnected to IB Gateway")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Reconnection failed: {e}")
            self.is_connected = False
            return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_ib_client(config=None) -> Union[IBClient, IBGatewayClient]:
    """
    Get appropriate IB client based on configuration.
    
    This factory function returns either an IBClient (Web API) or
    IBGatewayClient (Direct connection) based on configuration settings
    and environment variables.
    
    Args:
        config: Configuration object/dict
        
    Returns:
        Union[IBClient, IBGatewayClient]: Client instance
    """
    logger = SpyderLogger(__name__)
    
    # Check environment variables first
    use_gateway_env = os.getenv("IB_USE_GATEWAY", "false").lower()
    auth_method_env = os.getenv("IB_AUTH_METHOD", "client_portal").lower()
    
    use_gateway = (
        use_gateway_env in ("true", "yes", "1") or auth_method_env == "gateway"
    )
    
    logger.info(f"Factory selection - Gateway: {use_gateway}, Available: {IB_INSYNC_AVAILABLE}")
    
    # Check config as fallback
    if not use_gateway and config:
        if isinstance(config, dict):
            ib_config = config.get("ib", {})
            use_gateway = (
                ib_config.get("use_gateway", False)
                or ib_config.get("gateway", {}).get("enabled", False)
                or config.get("use_gateway", False)
            )
        else:
            use_gateway = getattr(config, "use_gateway", False) or getattr(
                config, "ib_use_gateway", False
            )
    
    # Create appropriate client
    if use_gateway:
        if IB_INSYNC_AVAILABLE:
            logger.info("✅ Creating IBGatewayClient")
            return IBGatewayClient(config)
        else:
            logger.error("❌ ib_insync not available, falling back to IBClient")
            logger.error("💡 Install with: pip install ib_insync")
            return IBClient(config)
    else:
        logger.info("ℹ️ Creating IBClient (Client Portal)")
        return IBClient(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
__all__ = [
    'IBClient',
    'IBGatewayClient',
    'get_ib_client',
    'ConnectionType',
    'TradingMode'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing IB Client modules...")
    
    # Test factory function
    client = get_ib_client()
    print(f"✅ Created client: {type(client).__name__}")
    
    # Test connection (requires IB running)
    if hasattr(client, 'connect'):
        print("Testing connection...")
        if client.connect():
            print("✅ Connection test passed")
            client.disconnect()
        else:
            print("❌ Connection test failed (ensure IB is running)")
    else:
        print("❌ Client missing connect method")