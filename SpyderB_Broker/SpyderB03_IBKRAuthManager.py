#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB03_IBKRAuthManager.py
Purpose: OAuth authentication manager for IBKR integration with automatic token renewal

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-24 Time: 16:00:00

Module Description:
    This module provides OAuth authentication management for Interactive Brokers
    using the ibind[oauth] library. It handles credential storage, authentication
    flow, automatic token renewal, and connection management without requiring
    the IB Gateway or browser-based login.

Module Constants:
    DEFAULT_CONFIG_PATH (str): Default path for credential storage
    TOKEN_RENEWAL_INTERVAL (int): Seconds before expiry to renew token (default: 300)
    CONNECTION_TIMEOUT (int): Connection timeout in seconds (default: 30)
    MAX_RETRY_ATTEMPTS (int): Maximum authentication retry attempts (default: 3)

Dependencies:
    - ibind[oauth]: IBKR OAuth authentication library
    - cryptography: Certificate and key management
    - json: Credential storage
    - threading: Token renewal background thread

Change Log:
    2025-10-24 (v1.0.0):
        - Initial module creation
        - OAuth 1.0a authentication implementation
        - Automatic token renewal mechanism
        - Secure credential storage
        - Connection health monitoring
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ibind import IbkrClient
    from ibind.support.py_utils import get_secret
    IBIND_AVAILABLE = True
except ImportError:
    IBIND_AVAILABLE = False
    print("⚠️ ibind library not available. Install with: pip install 'ibind[oauth]'")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    # Fallback logger if SpyderLogger not available
    SpyderLogger = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.spyder/ibkr_oauth_credentials.json")
TOKEN_RENEWAL_INTERVAL = 300  # Renew 5 minutes before expiry
CONNECTION_TIMEOUT = 30
MAX_RETRY_ATTEMPTS = 3

# IBKR API Endpoints
PAPER_TRADING_URL = "https://api.ibkr.com/v1/api"
LIVE_TRADING_URL = "https://api.ibkr.com/v1/api"

# ==============================================================================
# ENUMS
# ==============================================================================
class AuthStatus(Enum):
    """OAuth authentication status"""
    NOT_CONFIGURED = auto()
    CONFIGURED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED = auto()
    AUTHENTICATION_FAILED = auto()
    TOKEN_EXPIRED = auto()
    DISCONNECTED = auto()

class AccountType(Enum):
    """IBKR account types"""
    PAPER = "paper"
    LIVE = "live"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OAuthCredentials:
    """OAuth credentials for IBKR authentication"""
    consumer_key: str
    consumer_secret: str
    oauth_token: str
    oauth_token_secret: str
    encryption_cert_path: str
    signature_cert_path: str
    account_type: AccountType
    account_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'consumer_key': self.consumer_key,
            'consumer_secret': self.consumer_secret,
            'oauth_token': self.oauth_token,
            'oauth_token_secret': self.oauth_token_secret,
            'encryption_cert_path': self.encryption_cert_path,
            'signature_cert_path': self.signature_cert_path,
            'account_type': self.account_type.value,
            'account_id': self.account_id,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OAuthCredentials':
        """Create from dictionary"""
        return cls(
            consumer_key=data['consumer_key'],
            consumer_secret=data['consumer_secret'],
            oauth_token=data['oauth_token'],
            oauth_token_secret=data['oauth_token_secret'],
            encryption_cert_path=data['encryption_cert_path'],
            signature_cert_path=data['signature_cert_path'],
            account_type=AccountType(data['account_type']),
            account_id=data.get('account_id'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        )

@dataclass
class ConnectionStatus:
    """OAuth connection status information"""
    status: AuthStatus
    authenticated: bool = False
    account_type: Optional[AccountType] = None
    account_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_auth_time: Optional[datetime] = None
    error_message: Optional[str] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBKRAuthManager:
    """
    OAuth authentication manager for Interactive Brokers API.
    
    This class handles OAuth 1.0a authentication with IBKR using the ibind library.
    It provides secure credential storage, automatic token renewal, and connection
    health monitoring without requiring IB Gateway or browser-based authentication.
    
    Attributes:
        logger: Module logger instance
        config_path: Path to credential storage file
        credentials: Current OAuth credentials
        client: IBKR client instance from ibind
        status: Current connection status
        _renewal_thread: Background thread for token renewal
        _shutdown_event: Event for coordinated shutdown
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the OAuth authentication manager.
        
        Args:
            config_path: Optional custom path for credential storage
        """
        # Setup logger
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        
        # Configuration
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._ensure_config_directory()
        
        # State
        self.credentials: Optional[OAuthCredentials] = None
        self.client: Optional[IbkrClient] = None
        self.status = ConnectionStatus(status=AuthStatus.NOT_CONFIGURED)
        
        # Token renewal thread
        self._renewal_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        self.logger.info(f"IBKRAuthManager initialized - Config: {self.config_path}")
    
    # ==========================================================================
    # INITIALIZATION & CONFIGURATION
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the authentication manager and load saved credentials.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            if not IBIND_AVAILABLE:
                self.logger.error("ibind library not available")
                return False
            
            # Load saved credentials if they exist
            if os.path.exists(self.config_path):
                if self.load_credentials():
                    self.status.status = AuthStatus.CONFIGURED
                    self.logger.info("Credentials loaded successfully")
                else:
                    self.logger.warning("Failed to load saved credentials")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False
    
    def _ensure_config_directory(self):
        """Ensure configuration directory exists"""
        config_dir = os.path.dirname(self.config_path)
        if config_dir:
            os.makedirs(config_dir, mode=0o700, exist_ok=True)
    
    # ==========================================================================
    # CREDENTIAL MANAGEMENT
    # ==========================================================================
    
    def save_credentials(self, credentials: OAuthCredentials) -> bool:
        """
        Save OAuth credentials securely to disk.
        
        Args:
            credentials: OAuth credentials to save
            
        Returns:
            bool: True if save successful
        """
        try:
            # Store credentials
            self.credentials = credentials
            
            # Save to disk (with restricted permissions)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(credentials.to_dict(), f, indent=2)
            
            # Set restrictive permissions (owner read/write only)
            os.chmod(self.config_path, 0o600)
            
            self.status.status = AuthStatus.CONFIGURED
            self.logger.info(f"Credentials saved for {credentials.account_type.value} account")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            return False
    
    def load_credentials(self) -> bool:
        """
        Load OAuth credentials from disk.
        
        Returns:
            bool: True if load successful
        """
        try:
            if not os.path.exists(self.config_path):
                self.logger.info("No saved credentials found")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.credentials = OAuthCredentials.from_dict(data)
            self.status.status = AuthStatus.CONFIGURED
            self.logger.info(f"Credentials loaded for {self.credentials.account_type.value} account")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            return False
    
    def clear_credentials(self) -> bool:
        """
        Clear stored credentials.
        
        Returns:
            bool: True if clear successful
        """
        try:
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
            
            self.credentials = None
            self.status = ConnectionStatus(status=AuthStatus.NOT_CONFIGURED)
            self.logger.info("Credentials cleared")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear credentials: {e}")
            return False
    
    def has_credentials(self) -> bool:
        """Check if credentials are configured"""
        return self.credentials is not None
    
    # ==========================================================================
    # AUTHENTICATION
    # ==========================================================================
    
    def authenticate(self) -> bool:
        """
        Authenticate with IBKR using stored OAuth credentials.
        
        Returns:
            bool: True if authentication successful
        """
        if not self.credentials:
            self.logger.error("No credentials configured")
            self.status.status = AuthStatus.NOT_CONFIGURED
            return False
        
        try:
            self.status.status = AuthStatus.AUTHENTICATING
            self.logger.info(f"Authenticating with IBKR ({self.credentials.account_type.value})...")
            
            # Create IBKR client with OAuth credentials
            self.client = IbkrClient(
                account_id=self.credentials.account_id,
                url=(PAPER_TRADING_URL if self.credentials.account_type == AccountType.PAPER 
                     else LIVE_TRADING_URL)
            )
            
            # Authenticate using OAuth
            success = self.client.oauth(
                consumer_key=self.credentials.consumer_key,
                access_token=self.credentials.oauth_token,
                access_token_secret=self.credentials.oauth_token_secret,
                encryption_key=self.credentials.encryption_cert_path,
                signature_key=self.credentials.signature_cert_path
            )
            
            if success:
                self.status = ConnectionStatus(
                    status=AuthStatus.AUTHENTICATED,
                    authenticated=True,
                    account_type=self.credentials.account_type,
                    account_id=self.credentials.account_id,
                    last_auth_time=datetime.now(),
                    token_expires_at=datetime.now() + timedelta(hours=24)  # IBKR tokens typically last 24 hours
                )
                
                self.logger.info("✅ Authentication successful")
                
                # Start token renewal thread
                self._start_renewal_thread()
                
                return True
            else:
                raise Exception("OAuth authentication failed")
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            self.status = ConnectionStatus(
                status=AuthStatus.AUTHENTICATION_FAILED,
                error_message=str(e)
            )
            return False
    
    def disconnect(self):
        """Disconnect from IBKR"""
        try:
            # Stop renewal thread
            if self._renewal_thread and self._renewal_thread.is_alive():
                self._shutdown_event.set()
                self._renewal_thread.join(timeout=5)
            
            # Close client connection
            if self.client:
                self.client = None
            
            self.status = ConnectionStatus(status=AuthStatus.DISCONNECTED)
            self.logger.info("Disconnected from IBKR")
            
        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")
    
    # ==========================================================================
    # TOKEN RENEWAL
    # ==========================================================================
    
    def _start_renewal_thread(self):
        """Start background thread for automatic token renewal"""
        if self._renewal_thread and self._renewal_thread.is_alive():
            return
        
        self._shutdown_event.clear()
        self._renewal_thread = threading.Thread(
            target=self._token_renewal_worker,
            daemon=True,
            name="OAuthTokenRenewal"
        )
        self._renewal_thread.start()
        self.logger.info("Token renewal thread started")
    
    def _token_renewal_worker(self):
        """Background worker for automatic token renewal"""
        while not self._shutdown_event.is_set():
            try:
                # Check if token needs renewal
                if self.status.authenticated and self.status.token_expires_at:
                    time_until_expiry = (self.status.token_expires_at - datetime.now()).total_seconds()
                    
                    # Renew if within TOKEN_RENEWAL_INTERVAL seconds of expiry
                    if time_until_expiry <= TOKEN_RENEWAL_INTERVAL:
                        self.logger.info("Token expiring soon, renewing...")
                        if self.authenticate():
                            self.logger.info("✅ Token renewed successfully")
                        else:
                            self.logger.error("❌ Token renewal failed")
                
                # Sleep for 1 minute before next check
                self._shutdown_event.wait(60)
                
            except Exception as e:
                self.logger.error(f"Token renewal error: {e}")
                self._shutdown_event.wait(60)
    
    # ==========================================================================
    # CONNECTION HEALTH
    # ==========================================================================
    
    def is_authenticated(self) -> bool:
        """Check if currently authenticated"""
        return self.status.authenticated and self.client is not None
    
    def get_connection_status(self) -> ConnectionStatus:
        """Get current connection status"""
        return self.status
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the OAuth connection with IBKR.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not self.client:
            return False, "Not authenticated"
        
        try:
            # Try to get account summary as a connection test
            accounts = self.client.get_accounts()
            if accounts:
                return True, f"Connection OK - {len(accounts)} account(s) accessible"
            else:
                return False, "No accounts accessible"
                
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    # ==========================================================================
    # CLEANUP
    # ==========================================================================
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.disconnect()
            self.logger.info("OAuth manager cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    def __del__(self):
        """Destructor"""
        self.cleanup()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_auth_manager(config_path: Optional[str] = None) -> IBKRAuthManager:
    """
    Factory function to create an OAuth authentication manager.
    
    Args:
        config_path: Optional path to credential storage
        
    Returns:
        IBKRAuthManager instance
    """
    return IBKRAuthManager(config_path)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("SpyderB03_IBKRAuthManager - OAuth Authentication Manager")
    print("=" * 70)
    print(f"ibind Library Available: {IBIND_AVAILABLE}")
    print(f"Default Config Path: {DEFAULT_CONFIG_PATH}")
    print(f"Token Renewal Interval: {TOKEN_RENEWAL_INTERVAL}s")
    print("=" * 70)
    
    if IBIND_AVAILABLE:
        print("\n✅ Ready for OAuth authentication")
        print("\nFeatures:")
        print("  • Secure credential storage")
        print("  • Automatic token renewal")
        print("  • Connection health monitoring")
        print("  • Paper and Live account support")
        print("  • No IB Gateway required")
        print("  • No browser-based login")
    else:
        print("\n⚠️ Install ibind to use this module:")
        print("   pip install 'ibind[oauth]'")
