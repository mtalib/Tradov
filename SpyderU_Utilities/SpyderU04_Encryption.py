#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU04_Encryption.py
Group: U (Utilities)
Purpose: Credential encryption and secure storage

Description:
    This module provides secure credential management for the Spyder trading system.
    It implements encryption for sensitive data like API keys, passwords, and tokens
    using Fernet symmetric encryption. Credentials are stored in an encrypted file
    with key derivation from a master password.

Author: Mohamed Talib
Date: 2024-01-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import base64
import getpass
import secrets
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
CREDENTIALS_FILE = "credentials.enc"
SALT_LENGTH = 32
ITERATIONS = 100000

# ==============================================================================
# CREDENTIAL MANAGER CLASS
# ==============================================================================
class CredentialManager:
    """
    Manages encrypted storage of credentials.
    
    Features:
    - Secure credential storage using Fernet encryption
    - Master password protection
    - Key derivation using PBKDF2
    - Import/export functionality
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize credential manager.
        
        Args:
            storage_path: Path to store encrypted credentials
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Storage paths
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".spyder" / CREDENTIALS_FILE
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Encryption key
        self._fernet: Optional[Fernet] = None
        self._master_key: Optional[bytes] = None
        
        # Credentials cache
        self._credentials: Dict[str, str] = {}
        self._loaded = False
        
        self.logger.info(f"CredentialManager initialized with storage: {self.storage_path}")
    
    # ==========================================================================
    # KEY MANAGEMENT
    # ==========================================================================
    def initialize(self, master_password: Optional[str] = None) -> None:
        """
        Initialize encryption with master password.
        
        Args:
            master_password: Master password (will prompt if not provided)
        """
        try:
            if not master_password:
                master_password = self._get_master_password()
            
            # Derive key from password
            self._master_key = self._derive_key(master_password)
            self._fernet = Fernet(self._master_key)
            
            # Load existing credentials
            if self.storage_path.exists():
                self._load_credentials()
            else:
                self._credentials = {}
                self._save_credentials()
            
            self._loaded = True
            self.logger.info("Credential manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize credential manager: {e}")
            raise
    
    def _derive_key(self, password: str) -> bytes:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            password: Master password
            
        Returns:
            Derived key
        """
        # Get or create salt
        salt_path = self.storage_path.parent / ".salt"
        if salt_path.exists():
            with open(salt_path, 'rb') as f:
                salt = f.read()
        else:
            salt = secrets.token_bytes(SALT_LENGTH)
            with open(salt_path, 'wb') as f:
                f.write(salt)
            os.chmod(salt_path, 0o600)  # Restrict permissions
        
        # Derive key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=ITERATIONS
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_master_password(self) -> str:
        """
        Get master password from user.
        
        Returns:
            Master password
        """
        # Check environment variable first
        password = os.getenv('SPYDER_MASTER_PASSWORD')
        if password:
            return password
        
        # Prompt user
        return getpass.getpass("Enter master password: ")
    
    # ==========================================================================
    # CREDENTIAL OPERATIONS
    # ==========================================================================
    def set_credential(self, key: str, value: str) -> None:
        """
        Set a credential.
        
        Args:
            key: Credential key
            value: Credential value
        """
        if not self._loaded:
            raise RuntimeError("Credential manager not initialized")
        
        self._credentials[key] = value
        self._save_credentials()
        self.logger.info(f"Credential '{key}' updated")
    
    def get_credential(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a credential.
        
        Args:
            key: Credential key
            default: Default value if not found
            
        Returns:
            Credential value or default
        """
        if not self._loaded:
            raise RuntimeError("Credential manager not initialized")
        
        return self._credentials.get(key, default)
    
    def delete_credential(self, key: str) -> bool:
        """
        Delete a credential.
        
        Args:
            key: Credential key
            
        Returns:
            True if deleted
        """
        if not self._loaded:
            raise RuntimeError("Credential manager not initialized")
        
        if key in self._credentials:
            del self._credentials[key]
            self._save_credentials()
            self.logger.info(f"Credential '{key}' deleted")
            return True
        
        return False
    
    def list_credentials(self) -> List[str]:
        """
        List all credential keys.
        
        Returns:
            List of credential keys
        """
        if not self._loaded:
            raise RuntimeError("Credential manager not initialized")
        
        return list(self._credentials.keys())
    
    # ==========================================================================
    # STORAGE OPERATIONS
    # ==========================================================================
    def _save_credentials(self) -> None:
        """Save credentials to encrypted file"""
        try:
            # Convert to JSON
            data = json.dumps(self._credentials)
            
            # Encrypt
            encrypted_data = self._fernet.encrypt(data.encode())
            
            # Save to file
            with open(self.storage_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Restrict permissions
            os.chmod(self.storage_path, 0o600)
            
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            raise
    
    def _load_credentials(self) -> None:
        """Load credentials from encrypted file"""
        try:
            # Read encrypted data
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt
            decrypted_data = self._fernet.decrypt(encrypted_data)
            
            # Parse JSON
            self._credentials = json.loads(decrypted_data.decode())
            
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            raise
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def change_master_password(self, old_password: str, new_password: str) -> None:
        """
        Change master password.
        
        Args:
            old_password: Current master password
            new_password: New master password
        """
        # Verify old password
        old_key = self._derive_key(old_password)
        if old_key != self._master_key:
            raise ValueError("Invalid old password")
        
        # Derive new key
        self._master_key = self._derive_key(new_password)
        self._fernet = Fernet(self._master_key)
        
        # Re-encrypt credentials
        self._save_credentials()
        
        self.logger.info("Master password changed successfully")
    
    def export_credentials(self, path: Path, password: Optional[str] = None) -> None:
        """
        Export credentials to encrypted file.
        
        Args:
            path: Export path
            password: Password for export file (uses master if not provided)
        """
        if not self._loaded:
            raise RuntimeError("Credential manager not initialized")
        
        # Use provided password or master
        if not password:
            password = self._get_master_password()
        
        # Create new Fernet with export password
        export_key = self._derive_key(password)
        export_fernet = Fernet(export_key)
        
        # Encrypt credentials
        data = json.dumps(self._credentials)
        encrypted_data = export_fernet.encrypt(data.encode())
        
        # Save to file
        with open(path, 'wb') as f:
            f.write(encrypted_data)
        
        self.logger.info(f"Credentials exported to {path}")
    
    def import_credentials(self, path: Path, password: Optional[str] = None) -> None:
        """
        Import credentials from encrypted file.
        
        Args:
            path: Import path
            password: Password for import file
        """
        if not password:
            password = getpass.getpass("Enter import file password: ")
        
        # Create Fernet with import password
        import_key = self._derive_key(password)
        import_fernet = Fernet(import_key)
        
        # Read and decrypt
        with open(path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted_data = import_fernet.decrypt(encrypted_data)
        imported_creds = json.loads(decrypted_data.decode())
        
        # Merge with existing
        self._credentials.update(imported_creds)
        self._save_credentials()
        
        self.logger.info(f"Imported {len(imported_creds)} credentials")

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def generate_secure_password(length: int = 32) -> str:
    """
    Generate a secure random password.
    
    Args:
        length: Password length
        
    Returns:
        Secure password
    """
    return secrets.token_urlsafe(length)

def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256.
    
    Args:
        password: Password to hash
        
    Returns:
        Hashed password
    """
    return hashlib.sha256(password.encode()).hexdigest()

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test credential manager
    manager = CredentialManager()
    
    print("Initializing credential manager...")
    manager.initialize()
    
    # Test operations
    print("\nSetting test credentials...")
    manager.set_credential("api_key", "test_api_key_12345")
    manager.set_credential("api_secret", "test_api_secret_67890")
    
    print("\nRetrieving credentials...")
    print(f"API Key: {manager.get_credential('api_key')}")
    print(f"API Secret: {manager.get_credential('api_secret')}")
    
    print("\nListing all credentials...")
    for key in manager.list_credentials():
        print(f"  - {key}")
    
    # Test password generation
    print("\nGenerating secure password...")
    password = generate_secure_password()
    print(f"Generated: {password}")
    print(f"Hash: {hash_password(password)}")
