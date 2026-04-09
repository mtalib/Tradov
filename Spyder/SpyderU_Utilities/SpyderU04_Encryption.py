#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU04_Encryption.py
Purpose: Encryption utilities and credential management using Fernet (AES-128-CBC)
         and Argon2id password hashing.

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-27 Time: 00:00:00

Module Description:
    Provides real symmetric encryption via cryptography.fernet.Fernet and
    secure password hashing via argon2-cffi.  Replaces the former base64
    stubs with production-grade cryptographic primitives.

Change Log:
    2026-03-27:
        - Replaced base64 stubs with Fernet symmetric encryption
        - Replaced SHA-256 password hashing with Argon2id
        - Key is derived from SPYDER_ENCRYPTION_KEY env var or auto-generated
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import secrets
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from cryptography.fernet import Fernet, InvalidToken
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

logger = logging.getLogger(__name__)

# ==============================================================================
# KEY MANAGEMENT
# ==============================================================================

def _get_or_create_key() -> bytes:
    """Return the Fernet key from the environment, or generate one.

    If SPYDER_ENCRYPTION_KEY is set it must be a valid url-safe base64
    encoded 32-byte key (as produced by ``Fernet.generate_key()``).
    When the variable is absent a fresh key is generated and a warning
    is logged — encrypted data will NOT survive process restarts unless
    the key is persisted.
    """
    env_key = os.environ.get("SPYDER_ENCRYPTION_KEY")
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key
    logger.warning(
        "SPYDER_ENCRYPTION_KEY not set — generating ephemeral key. "
        "Encrypted data will not survive restarts. Set the env var to a "
        "value produced by cryptography.fernet.Fernet.generate_key()."
    )
    return Fernet.generate_key()


# Module-level singleton key (loaded once)
_FERNET_KEY: bytes = _get_or_create_key()
_FERNET: Fernet = Fernet(_FERNET_KEY)
_HASHER: PasswordHasher = PasswordHasher()


class EncryptionManager:
    """Fernet-based encryption manager.

    Each instance can optionally use its own key; by default the
    module-level key derived from ``SPYDER_ENCRYPTION_KEY`` is used.
    """

    def __init__(self, key: bytes | None = None):
        self._key = key or _FERNET_KEY
        self._fernet = Fernet(self._key) if key else _FERNET
        self.is_initialized = True

    def encrypt(self, data: str) -> str:
        """Encrypt *data* and return a url-safe base64 token string."""
        return self._fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a Fernet token string back to plaintext.

        Returns the original *encrypted_data* unchanged when decryption
        fails (e.g. data was produced by the old base64 stub).
        """
        try:
            return self._fernet.decrypt(encrypted_data.encode()).decode()
        except (InvalidToken, Exception):
            return encrypted_data

    def generate_key(self) -> bytes:
        """Generate a new Fernet key."""
        return Fernet.generate_key()


class CredentialManager:
    """In-memory credential store backed by Fernet encryption."""

    def __init__(self):
        self.credentials: dict[str, str] = {}
        self.encryption_manager = EncryptionManager()

    def initialize(self) -> bool:
        """Initialize credential manager."""
        return True

    def set_credential(self, key: str, value: str) -> bool:
        """Store a credential (encrypted in memory)."""
        self.credentials[key] = self.encryption_manager.encrypt(value)
        return True

    def get_credential(self, key: str, default: str | None = None) -> str | None:
        """Retrieve and decrypt a credential."""
        enc = self.credentials.get(key)
        if enc is None:
            return default
        return self.encryption_manager.decrypt(enc)

    def list_credentials(self) -> list:
        """List all credential keys."""
        return list(self.credentials.keys())

    def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        if key in self.credentials:
            del self.credentials[key]
            return True
        return False


# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================


def encrypt_data(data: str) -> str:
    """Encrypt *data* using the module-level Fernet instance."""
    return _FERNET.encrypt(data.encode()).decode()


def decrypt_data(encrypted_data: str) -> str:
    """Decrypt a Fernet token; returns input unchanged on failure."""
    try:
        return _FERNET.decrypt(encrypted_data.encode()).decode()
    except (InvalidToken, Exception):
        return encrypted_data


def encrypt(data: str) -> str:
    """Alias for encrypt_data."""
    return encrypt_data(data)


def decrypt(encrypted_data: str) -> str:
    """Alias for decrypt_data."""
    return decrypt_data(encrypted_data)


def generate_secure_password(length: int = 32) -> str:
    """Generate a cryptographically secure random password."""
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Returns an encoded Argon2 hash string that embeds the salt,
    parameters, and digest — safe to store directly in a database.
    """
    return _HASHER.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify *password* against an Argon2id *hashed* value.

    Returns True if the password matches, False otherwise.
    """
    try:
        return _HASHER.verify(hashed, password)
    except (VerifyMismatchError, VerificationError):
        return False


# ==============================================================================
# BACKWARDS COMPATIBILITY
# ==============================================================================
# Alias for modules expecting different names
Encryption = EncryptionManager

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
__all__ = [
    "EncryptionManager",
    "CredentialManager",
    "Encryption",
    "encrypt_data",
    "decrypt_data",
    "encrypt",
    "decrypt",
    "generate_secure_password",
    "hash_password",
    "verify_password",
]

if __name__ == "__main__":
    # Test encryption
    em = EncryptionManager()
    test_data = "Hello, World!"
    encrypted = em.encrypt(test_data)
    decrypted = em.decrypt(encrypted)
    assert decrypted == test_data, "Encryption round-trip failed"

    # Test password hashing
    pw = "test_password_123"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed), "Password verification failed"
    assert not verify_password("wrong", hashed), "Wrong password should not verify"
    print("All encryption tests passed.")  # noqa: T201
