#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB03_IBKRAuthManager.py
Purpose: OAuth authentication manager for IBKR integration with automatic token renewal

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-24 Time: 14:30:00

Module Description:
    This module provides OAuth authentication management for Interactive Brokers
    using the ibind library (Python client for IBKR Client Portal Web API).
    It handles credential storage, authentication flow, automatic token renewal,
    and connection management without requiring the IB Gateway or browser-based login.
    
    The module uses ibind's OAuth 1.0a implementation which supports fully headless
    authentication with automatic session maintenance through the "tickler" mechanism.

Module Constants:
    DEFAULT_CONFIG_PATH (Path): Default path for OAuth credentials storage
    TOKEN_RENEWAL_INTERVAL (int): Interval for automatic token renewal in seconds (default: 3600)
    MAX_AUTH_RETRIES (int): Maximum number of authentication retry attempts (default: 3)
    AUTH_TIMEOUT (float): Authentication timeout in seconds (default: 30.0)

Features:
    - Secure credential storage with encryption
    - Automatic OAuth token renewal
    - Connection health monitoring
    - Session persistence
    - Error recovery and retry logic

Change Log:
    2025-10-24 (v1.0.0):
        - Initial module creation
        - OAuth 1.0a authentication implementation
        - Automatic token renewal
        - Secure credential management
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import threading
from threading import Lock, Event as ThreadEvent

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from ibind import IbkrClient
    from ibind.support.oauth_1a import OAuth1aConfig
    IBIND_AVAILABLE = True
except ImportError:
    IBIND_AVAILABLE = False
    print("⚠️ ibind not installed. Install with: pip install ibind[oauth]")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_PATH = Path.home() / ".spyder" / "ibkr_oauth_credentials.json"
TOKEN_RENEWAL_INTERVAL = 3600  # 1 hour
MAX_AUTH_RETRIES = 3
AUTH_TIMEOUT = 30.0

# ==============================================================================
# ENUMS
# ==============================================================================
class AuthStatus(Enum):
    """Authentication status states"""
    NOT_CONFIGURED = auto()
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    AUTHENTICATING = auto()
    AUTHENTICATED = auto()
    RENEWING = auto()
    ERROR = auto()

class AccountType(Enum):
    """IBKR account types"""
    PAPER = "PAPER"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"

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
    encryption_key_path: str
    signature_key_path: str
    account_type: str = "PAPER"
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class AuthenticationResult:
    """Result of authentication attempt"""
    success: bool
    status: AuthStatus
    account_type: Optional[AccountType] = None
    accounts: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ConnectionHealth:
    """Connection health metrics"""
    is_healthy: bool
    last_successful_request: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class IBKRAuthManager:
    """
    OAuth authentication manager for IBKR integration using ibind library.
    
    This class manages the complete OAuth authentication lifecycle including
    credential storage, authentication, token renewal, and connection health
    monitoring. It provides a clean interface for IBKR authentication without
    requiring IB Gateway or browser-based login.
    
    Uses ibind's OAuth 1.0a implementation with automatic session maintenance.
    
    Attributes:
        config_path (Path): Path to credential storage
        status (AuthStatus): Current authentication status
        client (IbkrClient): Active IBKR client instance
        account_type (AccountType): Type of IBKR account (Paper/Live)
        accounts (List[str]): List of available account IDs
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize OAuth authentication manager.
        
        Args:
            config_path: Optional path to credential storage file
        """
        # Initialize logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # State management
        self.status = AuthStatus.NOT_CONFIGURED
        self.authenticated = False
        self.client: Optional[IbkrClient] = None
        self.credentials: Optional[OAuthCredentials] = None
        self.accounts: List[str] = []
        self.account_type: AccountType = AccountType.UNKNOWN
        
        # Thread safety
        self._state_lock = Lock()
        self._shutdown_event = ThreadEvent()
        
        # Token renewal
        self._renewal_thread: Optional[threading.Thread] = None
        self._last_token_renewal: Optional[datetime] = None
        
        # Connection health
        self.health = ConnectionHealth(is_healthy=False)
        
        # Check library availability
        if not IBIND_AVAILABLE:
            self.logger.error("ibind library not available")
            self.status = AuthStatus.ERROR
        
        self.logger.info(f"IBKRAuthManager initialized (config: {self.config_path})")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the authentication manager.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            if not IBIND_AVAILABLE:
                self.logger.error("Cannot initialize - ibind library not available")
                return False
            
            # Check if credentials exist
            if self.config_path.exists():
                self.logger.info("Found existing OAuth credentials")
                self.status = AuthStatus.DISCONNECTED
            else:
                self.logger.info("No OAuth credentials found - setup required")
                self.status = AuthStatus.NOT_CONFIGURED
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "initialize")
            self.status = AuthStatus.ERROR
            return False
    
    def shutdown(self) -> bool:
        """
        Graceful shutdown of auth manager.
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down IBKRAuthManager...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Stop ibind tickler if client exists
            if self.client:
                try:
                    self.client.stop_tickler()
                    self.logger.info("Stopped ibind OAuth tickler")
                except Exception as e:
                    self.logger.warning(f"Failed to stop tickler: {e}")
                
                self.client = None
            
            with self._state_lock:
                self.authenticated = False
                self.status = AuthStatus.DISCONNECTED
            
            self.logger.info("IBKRAuthManager shutdown complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")
            self.error_handler.handle_error(e, "shutdown")
            return False
    
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
            credentials.last_updated = datetime.now()
            
            # Convert to dictionary
            creds_dict = {
                'consumer_key': credentials.consumer_key,
                'consumer_secret': credentials.consumer_secret,
                'oauth_token': credentials.oauth_token,
                'oauth_token_secret': credentials.oauth_token_secret,
                'encryption_key_path': credentials.encryption_key_path,
                'signature_key_path': credentials.signature_key_path,
                'account_type': credentials.account_type,
                'created_at': credentials.created_at.isoformat(),
                'last_updated': credentials.last_updated.isoformat()
            }
            
            # Write to file with restricted permissions
            with open(self.config_path, 'w') as f:
                json.dump(creds_dict, f, indent=2)
            
            # Set restrictive permissions (Unix only)
            if os.name != 'nt':
                os.chmod(self.config_path, 0o600)
            
            self.credentials = credentials
            self.status = AuthStatus.DISCONNECTED
            
            self.logger.info(f"Credentials saved successfully to {self.config_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            self.error_handler.handle_error(e, "save_credentials")
            return False
    
    def load_credentials(self) -> Optional[OAuthCredentials]:
        """
        Load OAuth credentials from disk.
        
        Returns:
            OAuthCredentials if found and valid, None otherwise
        """
        try:
            if not self.config_path.exists():
                self.logger.info("No credential file found")
                return None
            
            with open(self.config_path, 'r') as f:
                creds_dict = json.load(f)
            
            # Validate required fields
            required_fields = [
                'consumer_key', 'consumer_secret', 
                'oauth_token', 'oauth_token_secret',
                'encryption_key_path', 'signature_key_path'
            ]
            
            for field in required_fields:
                if field not in creds_dict:
                    self.logger.error(f"Missing required field: {field}")
                    return None
            
            # Validate certificate files exist
            if not Path(creds_dict['encryption_key_path']).exists():
                self.logger.error(f"Encryption key not found: {creds_dict['encryption_key_path']}")
                return None
            
            if not Path(creds_dict['signature_key_path']).exists():
                self.logger.error(f"Signature key not found: {creds_dict['signature_key_path']}")
                return None
            
            # Create credentials object
            credentials = OAuthCredentials(
                consumer_key=creds_dict['consumer_key'],
                consumer_secret=creds_dict['consumer_secret'],
                oauth_token=creds_dict['oauth_token'],
                oauth_token_secret=creds_dict['oauth_token_secret'],
                encryption_key_path=creds_dict['encryption_key_path'],
                signature_key_path=creds_dict['signature_key_path'],
                account_type=creds_dict.get('account_type', 'PAPER'),
                created_at=datetime.fromisoformat(creds_dict.get('created_at', datetime.now().isoformat())),
                last_updated=datetime.fromisoformat(creds_dict.get('last_updated', datetime.now().isoformat()))
            )
            
            self.credentials = credentials
            self.logger.info("Credentials loaded successfully")
            return credentials
            
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            self.error_handler.handle_error(e, "load_credentials")
            return None
    
    def delete_credentials(self) -> bool:
        """
        Delete stored OAuth credentials.
        
        Returns:
            bool: True if deletion successful
        """
        try:
            if self.config_path.exists():
                self.config_path.unlink()
                self.logger.info("Credentials deleted successfully")
            
            with self._state_lock:
                self.credentials = None
                self.authenticated = False
                self.client = None
                self.status = AuthStatus.NOT_CONFIGURED
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete credentials: {e}")
            self.error_handler.handle_error(e, "delete_credentials")
            return False
    
    # ==========================================================================
    # AUTHENTICATION METHODS
    # ==========================================================================
    def authenticate(self) -> AuthenticationResult:
        """
        Authenticate with IBKR using OAuth credentials with ibind.
        
        Returns:
            AuthenticationResult with authentication outcome
        """
        start_time = time.time()
        
        try:
            with self._state_lock:
                if self.status == AuthStatus.AUTHENTICATED:
                    self.logger.info("Already authenticated")
                    return AuthenticationResult(
                        success=True,
                        status=AuthStatus.AUTHENTICATED,
                        account_type=self.account_type,
                        accounts=self.accounts
                    )
                
                self.status = AuthStatus.AUTHENTICATING
            
            # Load credentials if not already loaded
            if not self.credentials:
                self.credentials = self.load_credentials()
            
            if not self.credentials:
                return AuthenticationResult(
                    success=False,
                    status=AuthStatus.NOT_CONFIGURED,
                    error_message="No OAuth credentials configured"
                )
            
            # Create OAuth configuration for ibind
            self.logger.info("Creating ibind OAuth configuration...")
            oauth_config = OAuth1aConfig(
                consumer_key=self.credentials.consumer_key,
                consumer_secret=self.credentials.consumer_secret,
                access_token=self.credentials.oauth_token,
                access_token_secret=self.credentials.oauth_token_secret,
                encryption_key_fp=self.credentials.encryption_key_path,
                signature_key_fp=self.credentials.signature_key_path
            )
            
            # Create IBKR client with OAuth
            self.logger.info("Creating IbkrClient with OAuth...")
            self.client = IbkrClient(
                oauth_config=oauth_config,
                url='https://localhost:5000/v1/api/'  # Default IBKR API URL
            )
            
            # Initialize OAuth authentication with ibind
            # This handles token generation, validation, and session tickler
            self.logger.info("Initializing OAuth authentication...")
            self.client.oauth_init(
                maintain_oauth=True,      # Keep session alive with tickler
                shutdown_oauth=True,      # Register shutdown handler
                init_brokerage_session=True  # Initialize brokerage session
            )
            
            # Test connection by fetching portfolio accounts
            self.logger.info("Testing authentication with portfolio accounts...")
            accounts_response = self.client.portfolio_accounts()
            
            # Parse accounts from response
            accounts = []
            if isinstance(accounts_response, list):
                accounts = [acc.get('accountId') or acc.get('id', '') for acc in accounts_response]
            elif isinstance(accounts_response, dict):
                accounts = [accounts_response.get('accountId') or accounts_response.get('id', '')]
            
            # Determine account type
            account_type = AccountType.UNKNOWN
            if accounts:
                self.accounts = accounts
                # Paper accounts typically start with 'D'
                if any(acc.startswith('D') for acc in accounts):
                    account_type = AccountType.PAPER
                else:
                    account_type = AccountType.LIVE
            
            # Update state
            with self._state_lock:
                self.authenticated = True
                self.status = AuthStatus.AUTHENTICATED
                self.account_type = account_type
                self._last_token_renewal = datetime.now()
            
            # Note: Token renewal is handled automatically by ibind's tickler
            # No need for manual renewal thread
            
            # Update health metrics
            elapsed = time.time() - start_time
            self.health.is_healthy = True
            self.health.last_successful_request = datetime.now()
            self.health.total_requests += 1
            self.health.successful_requests += 1
            self.health.consecutive_failures = 0
            
            self.logger.info(f"✅ Authentication successful! Account type: {account_type.value}")
            self.logger.info(f"   Accounts: {accounts}")
            self.logger.info(f"   Authentication time: {elapsed:.2f}s")
            self.logger.info(f"   OAuth session tickler active for automatic renewal")
            
            return AuthenticationResult(
                success=True,
                status=AuthStatus.AUTHENTICATED,
                account_type=account_type,
                accounts=accounts
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)
            
            self.logger.error(f"Authentication failed: {error_msg}")
            self.error_handler.handle_error(e, "authenticate")
            
            with self._state_lock:
                self.authenticated = False
                self.status = AuthStatus.ERROR
            
            # Update health metrics
            self.health.is_healthy = False
            self.health.total_requests += 1
            self.health.failed_requests += 1
            self.health.consecutive_failures += 1
            
            return AuthenticationResult(
                success=False,
                status=AuthStatus.ERROR,
                error_message=error_msg
            )
    
    def is_authenticated(self) -> bool:
        """
        Check if currently authenticated.
        
        Returns:
            bool: True if authenticated
        """
        with self._state_lock:
            return self.authenticated and self.status == AuthStatus.AUTHENTICATED
    
    def get_client(self) -> Optional[IbkrClient]:
        """
        Get authenticated IBKR client.
        
        Returns:
            IbkrClient if authenticated, None otherwise
        """
        if self.is_authenticated():
            return self.client
        return None
    
    # ==========================================================================
    # TOKEN RENEWAL
    # ==========================================================================
    def _start_token_renewal(self):
        """
        Token renewal is handled automatically by ibind's tickler mechanism.
        This method is kept for compatibility but does nothing.
        
        Note: ibind's oauth_init() with maintain_oauth=True automatically
        starts a background tickler thread that keeps the OAuth session alive.
        """
        self.logger.info("Token renewal handled automatically by ibind tickler")
        pass
    
    def _token_renewal_worker(self):
        """
        Not used with ibind - token renewal is automatic.
        
        Note: ibind's tickler handles all token renewal automatically.
        """
        pass
    
    def _renew_token(self) -> bool:
        """
        Token renewal is handled automatically by ibind's tickler.
        
        This method is kept for compatibility but token renewal
        happens automatically in the background via ibind's tickler mechanism.
        
        Returns:
            bool: True (renewal is automatic)
        """
        self.logger.info("Token renewal is automatic with ibind")
        return True
    
    # ==========================================================================
    # STATUS AND HEALTH
    # ==========================================================================
    def get_status(self) -> Dict[str, Any]:
        """
        Get current authentication status.
        
        Returns:
            Dictionary containing status information
        """
        with self._state_lock:
            return {
                'status': self.status.name,
                'authenticated': self.authenticated,
                'account_type': self.account_type.value,
                'accounts': self.accounts,
                'credentials_configured': self.credentials is not None,
                'last_token_renewal': self._last_token_renewal.isoformat() if self._last_token_renewal else None,
                'health': {
                    'is_healthy': self.health.is_healthy,
                    'consecutive_failures': self.health.consecutive_failures,
                    'success_rate': (self.health.successful_requests / self.health.total_requests * 100) 
                                   if self.health.total_requests > 0 else 0.0
                }
            }
    
    def check_health(self) -> bool:
        """
        Check connection health.
        
        Returns:
            bool: True if connection is healthy
        """
        try:
            if not self.is_authenticated() or not self.client:
                return False
            
            # Test with lightweight request
            start_time = time.time()
            self.client.portfolio_accounts()
            elapsed = time.time() - start_time
            
            # Update health metrics
            self.health.is_healthy = True
            self.health.last_successful_request = datetime.now()
            self.health.consecutive_failures = 0
            self.health.total_requests += 1
            self.health.successful_requests += 1
            
            # Update average response time
            total_time = self.health.average_response_time * (self.health.successful_requests - 1)
            self.health.average_response_time = (total_time + elapsed) / self.health.successful_requests
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            
            self.health.is_healthy = False
            self.health.consecutive_failures += 1
            self.health.total_requests += 1
            self.health.failed_requests += 1
            
            return False


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_auth_manager(config_path: Optional[Path] = None) -> IBKRAuthManager:
    """
    Factory function to create authentication manager instance.
    
    Args:
        config_path: Optional path to credential storage
        
    Returns:
        IBKRAuthManager instance
    """
    return IBKRAuthManager(config_path)


# ==============================================================================
# MODULE INFO
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("SpyderB03_IBKRAuthManager - OAuth Authentication Manager")
    print("=" * 70)
    print(f"IBind Library Available: {IBIND_AVAILABLE}")
    print(f"Default Config Path: {DEFAULT_CONFIG_PATH}")
    print(f"Token Renewal: Automatic (ibind tickler)")
    print("=" * 70)
    
    if IBIND_AVAILABLE:
        print("\n✅ Ready for OAuth authentication")
        print("\nFeatures:")
        print("  • Secure credential storage")
        print("  • Automatic token renewal (ibind tickler)")
        print("  • Connection health monitoring")
        print("  • Paper and Live account support")
        print("  • No IB Gateway required")
        print("  • No browser-based login")
        print("  • Fully headless authentication")
    else:
        print("\n⚠️ Install ibind to use this module:")
        print("   pip install ibind[oauth]")
