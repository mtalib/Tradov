#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: Tradov.TradovU_Utilities
Module: TradovU46_SecretsManager.py
Purpose: Unified secrets management — env vars, encrypted YAML, optional Vault

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-01

Module Description:
    Resolves the inconsistent secrets-handling across the codebase (some
    modules read from env vars, others from config files, others from
    encrypted YAML) by providing a single SecretManager that merges all
    sources under a consistent API.

    Resolution priority (highest to lowest):
        1. HashiCorp Vault (if VAULT_ADDR + VAULT_TOKEN are set)
        2. Environment variables  (TRADOV_SECRET_<KEY> or plain <KEY>)
        3. Encrypted YAML file    (~/.tradov/secrets.yaml, Fernet-encrypted)
        4. Plain YAML file        (~/.tradov/secrets.yaml, plaintext fallback)

    A secret key is normalised to UPPER_SNAKE_CASE before resolution so
    callers can use any casing they prefer.

Key Features:
    • Transparent priority merging across 4 sources
    • Fernet-encrypted YAML file via TradovU04_Encryption
    • Optional HashiCorp Vault KV-v2 path (no extra library needed — uses
      the Vault HTTP API via urllib)
    • set() / delete() write-through to the YAML file (not Vault)
    • Thread-safe via RLock
    • Module-level singleton via get_secrets()

Dependencies:
    • Python standard library only (os, pathlib, urllib, json, threading)
    • PyYAML (standard Tradov dep) — for YAML persistence
    • TradovU04_Encryption — Fernet encryption (graceful degradation to
      plaintext if unavailable)
    • TradovU01_Logger (graceful fallback to stdlib logging)

Environment Variables:
    TRADOV_SECRETS_FILE    — override default ~/.tradov/secrets.yaml
    VAULT_ADDR             — HashiCorp Vault address (e.g. http://127.0.0.1:8200)
    VAULT_TOKEN            — Vault token
    VAULT_SECRET_PATH      — Vault KV-v2 path (default: tradov/data)
    VAULT_MOUNT            — Vault KV-v2 mount (default: secret)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    _log = TradovLogger.get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

try:
    from Tradov.TradovU_Utilities.TradovU04_Encryption import EncryptionManager
    _enc = EncryptionManager()
    HAS_ENCRYPTION = True
except Exception:
    HAS_ENCRYPTION = False
    _log.warning(
        "TradovU04_Encryption unavailable — secrets YAML will be stored as plaintext"
    )

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_SECRETS_FILE = Path.home() / ".tradov" / "secrets.yaml"
_ENV_PREFIX = "TRADOV_SECRET_"
_VAULT_ADDR = os.getenv("VAULT_ADDR", "")
_VAULT_TOKEN = os.getenv("VAULT_TOKEN", "")
_VAULT_PATH = os.getenv("VAULT_SECRET_PATH", "tradov/data")
_VAULT_MOUNT = os.getenv("VAULT_MOUNT", "secret")


# ==============================================================================
# HELPERS
# ==============================================================================

def _normalise(key: str) -> str:
    """Normalise a secret key to UPPER_SNAKE_CASE."""
    return key.strip().upper().replace("-", "_").replace(" ", "_")


def _vault_get(key: str) -> str | None:
    """Fetch a single key from HashiCorp Vault KV-v2.  Returns None on failure."""
    if not (_VAULT_ADDR and _VAULT_TOKEN):
        return None
    url = f"{_VAULT_ADDR}/v1/{_VAULT_MOUNT}/data/{_VAULT_PATH}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "X-Vault-Token": _VAULT_TOKEN,
                "Content-Type": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            data = body.get("data", {}).get("data", {})
            return data.get(key)
    except Exception as exc:
        _log.debug("Vault lookup failed for key %r: %s", key, exc)
        return None


# ==============================================================================
# SECRETS MANAGER
# ==============================================================================

class SecretsManager:
    """
    Unified secrets manager with priority-ordered resolution.

    Usage::

        from Tradov.TradovU_Utilities.TradovU46_SecretsManager import get_secrets

        sm = get_secrets()
        token     = sm.get("TRADIER_API_TOKEN")
        api_key   = sm.get("TRADIER_API_KEY", required=True)

        # Persist a new secret to the encrypted YAML file:
        sm.set("MY_SECRET", "s3cr3t_v4lue")

        # Delete a secret from the YAML file:
        sm.delete("MY_SECRET")
    """

    def __init__(self, secrets_file: Path | None = None) -> None:
        self._file   = Path(os.getenv("TRADOV_SECRETS_FILE", "")) or secrets_file or _DEFAULT_SECRETS_FILE  # noqa: E501
        self._lock   = threading.RLock()
        self._cache: dict[str, str] = {}
        self._yaml_data: dict[str, str] = {}
        self._loaded = False
        self._log    = _log

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: str | None = None, required: bool = False) -> str | None:
        """
        Resolve secret *key* using the priority chain.

        Args:
            key:      Secret name (case-insensitive, snake_case or UPPER_CASE).
            default:  Value to return if not found anywhere.
            required: If True, raises KeyError when the secret is missing.

        Returns:
            Secret value string, or *default* / None.

        Raises:
            KeyError: when required=True and the secret is not found.
        """
        norm = _normalise(key)
        with self._lock:
            # 1. In-memory cache
            if norm in self._cache:
                return self._cache[norm]

            # 2. Vault (if configured)
            value = _vault_get(norm)
            if value is not None:
                self._cache[norm] = value
                return value

            # 3. Environment variable
            value = os.getenv(f"{_ENV_PREFIX}{norm}") or os.getenv(norm)
            if value:
                self._cache[norm] = value
                return value

            # 4. Encrypted / plain YAML file
            self._ensure_loaded()
            value = self._yaml_data.get(norm)
            if value:
                self._cache[norm] = value
                return value

        if required:
            raise KeyError(
                f"Required secret {key!r} not found in Vault, environment, or secrets file"
            )
        return default

    def get_all(self) -> dict[str, str]:
        """
        Return a merged snapshot of all secrets from the YAML file and
        matching environment variables.  Vault keys are NOT enumerated.
        """
        self._ensure_loaded()
        merged: dict[str, str] = dict(self._yaml_data)
        # Add any TRADOV_SECRET_* env vars
        for env_key, env_val in os.environ.items():
            if env_key.startswith(_ENV_PREFIX):
                norm = env_key[len(_ENV_PREFIX):]
                merged[norm] = env_val
        return merged

    def set(self, key: str, value: str) -> None:
        """
        Store *key*=*value* in the encrypted YAML file and in-memory cache.
        Does NOT write to Vault or environment.
        """
        norm = _normalise(key)
        with self._lock:
            self._ensure_loaded()
            self._yaml_data[norm] = value
            self._cache[norm] = value
            self._save_yaml()
        self._log.info("Secret set: %s (source: yaml)", norm)

    def delete(self, key: str) -> bool:
        """
        Remove *key* from the YAML file and in-memory cache.
        Returns True if the key existed.
        """
        norm = _normalise(key)
        with self._lock:
            self._ensure_loaded()
            existed = norm in self._yaml_data
            self._yaml_data.pop(norm, None)
            self._cache.pop(norm, None)
            if existed:
                self._save_yaml()
        if existed:
            self._log.info("Secret deleted: %s", norm)
        return existed

    def reload(self) -> None:
        """Force a fresh read from the YAML file and clear the in-memory cache."""
        with self._lock:
            self._cache.clear()
            self._loaded = False
            self._ensure_loaded()

    def has(self, key: str) -> bool:
        """Return True if the secret exists in any source."""
        return self.get(key) is not None

    # ------------------------------------------------------------------
    # YAML persistence
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load YAML file into _yaml_data (once per instance lifetime)."""
        if self._loaded:
            return
        self._yaml_data = {}
        if not HAS_YAML:
            self._log.warning("PyYAML not available — YAML secrets file will be skipped")
            self._loaded = True
            return
        if not self._file.exists():
            self._loaded = True
            return
        try:
            raw = self._file.read_text(encoding="utf-8").strip()
            if not raw:
                self._loaded = True
                return
            # Attempt Fernet decryption first
            if HAS_ENCRYPTION:
                try:
                    raw = _enc.decrypt(raw)
                except Exception:
                    pass   # treat as plaintext
            data = yaml.safe_load(raw) or {}
            # Normalise all keys on load
            self._yaml_data = {_normalise(k): str(v) for k, v in data.items()}
            self._log.debug("Loaded %d secrets from %s", len(self._yaml_data), self._file)
        except Exception as exc:
            self._log.error("Failed to load secrets file %s: %s", self._file, exc)
        finally:
            self._loaded = True

    def _save_yaml(self) -> None:
        """Persist _yaml_data to the YAML file (Fernet-encrypted if available)."""
        if not HAS_YAML:
            self._log.warning("PyYAML unavailable — cannot persist secrets to file")
            return
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            plaintext = yaml.dump(self._yaml_data, default_flow_style=False)
            if HAS_ENCRYPTION:
                content = _enc.encrypt(plaintext)
            else:
                content = plaintext
            self._file.write_text(content, encoding="utf-8")
            # Restrict permissions to owner-only on POSIX
            try:
                self._file.chmod(0o600)
            except Exception:
                pass
        except Exception as exc:
            self._log.error("Failed to save secrets file %s: %s", self._file, exc)

    # ------------------------------------------------------------------
    # Convenience helpers for common Tradov secrets
    # ------------------------------------------------------------------

    @property
    def tradier_api_token(self) -> str | None:
        return self.get("TRADIER_API_TOKEN")

    @property
    def telegram_bot_token(self) -> str | None:
        return self.get("TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str | None:
        return self.get("TELEGRAM_CHAT_ID")

    @property
    def slack_webhook_url(self) -> str | None:
        return self.get("TRADOV_SLACK_WEBHOOK_URL")

    @property
    def teams_webhook_url(self) -> str | None:
        return self.get("TRADOV_TEAMS_WEBHOOK_URL")

    @property
    def discord_webhook_url(self) -> str | None:
        return self.get("TRADOV_DISCORD_WEBHOOK_URL")


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_manager: SecretsManager | None = None
_manager_lock = threading.Lock()


def get_secrets(secrets_file: Path | None = None) -> SecretsManager:
    """Return the module-level SecretsManager singleton."""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = SecretsManager(secrets_file=secrets_file)
    return _manager
