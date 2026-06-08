#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovA_Core
Module: TradovA03_Configuration.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import copy
import json
import logging
import os
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum, auto
from pathlib import Path
from typing import Any
from collections.abc import Callable

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import configparser
import hashlib
import toml
import yaml

try:
    import base64  # noqa: F401

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes  # noqa: F401
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # noqa: F401

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logging.info("Warning: cryptography not installed - sensitive data will not be encrypted")

from jsonschema import Draft7Validator
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_DIR = Path.home() / ".tradov" / "config"
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_ENV_PREFIX = "TRADOV_"
SENSITIVE_KEY_PATTERNS = [
    r".*password.*",
    r".*secret.*",
    r".*key.*",
    r".*token.*",
    r".*credential.*",
    r".*auth.*",
    r".*api.*key.*",
]
CONFIG_BACKUP_COUNT = 5
CONFIG_SCHEMA_VERSION = "2.0"

# Supported configuration file formats
SUPPORTED_FORMATS = {".json", ".yaml", ".yml", ".toml", ".ini", ".env"}

# ==============================================================================
# ENUMS
# ==============================================================================


class ConfigSource(Enum):
    """Configuration source types"""

    DEFAULT = auto()
    FILE = auto()
    ENVIRONMENT = auto()
    RUNTIME = auto()
    REMOTE = auto()


class ConfigFormat(Enum):
    """Configuration file formats"""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"
    ENV = "env"


class ValidationLevel(Enum):
    """Configuration validation levels"""

    NONE = auto()
    BASIC = auto()
    STRICT = auto()
    CUSTOM = auto()


class StartupValidationError(RuntimeError):
    """Raised when blocking startup validation fails."""


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ConfigValue:
    """Configuration value with metadata"""

    key: str
    value: Any
    source: ConfigSource
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    encrypted: bool = False
    schema_validated: bool = False
    description: str | None = None
    constraints: dict[str, Any] | None = None


@dataclass
class ConfigChange:
    """Configuration change record"""

    timestamp: datetime
    key: str
    old_value: Any
    new_value: Any
    source: str
    user: str | None = None
    reason: str | None = None


@dataclass
class ConfigSchema:
    """Configuration schema definition"""

    version: str
    properties: dict[str, Any]
    required: list[str]
    additional_properties: bool = False
    definitions: dict[str, Any] | None = None


# ==============================================================================
# CONFIGURATION FILE HANDLER
# ==============================================================================


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes"""

    def __init__(self, config_manager: "ConfigManager"):
        self.config_manager = config_manager
        self.logger = TradovLogger.get_logger(__name__)

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).suffix in SUPPORTED_FORMATS:
            self.logger.info("Configuration file modified: %s", event.src_path)
            self.config_manager._on_config_file_changed(Path(event.src_path))


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class ConfigManager:
    """
    Comprehensive configuration management system for Tradov.

    This class provides:
    - Multi-source configuration loading (files, env vars, defaults)
    - Configuration validation with JSON schemas
    - Sensitive data encryption
    - Hot-reloading of configuration files
    - Configuration versioning and backups
    - Audit trail of configuration changes
    - Thread-safe operations
    - Type conversion and validation

    Attributes:
        config_dir: Configuration directory path
        logger: Module logger instance
        error_handler: Error handling system
        config_data: Merged configuration data
        config_sources: Configuration values by source
        change_history: History of configuration changes
        schemas: Configuration schemas for validation
        encryption_key: Key for encrypting sensitive data
        file_observer: File system observer for hot-reload
    """

    def __init__(
        self,
        config_path: Path | None = None,
        environment: str = "production",
        auto_reload: bool = True,
    ):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to main configuration file
            environment: Environment name (development, staging, production)
            auto_reload: Enable automatic configuration reloading
        """
        # Initialize logging
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()

        # Configuration paths
        self.config_path = config_path or DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
        self.config_dir = (
            self.config_path.parent if self.config_path.is_file() else self.config_path
        )
        self.environment = environment

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Configuration data structures
        self.config_data: dict[str, Any] = {}
        self.config_sources: dict[str, ConfigValue] = {}
        self.change_history: list[ConfigChange] = []
        self.schemas: dict[str, ConfigSchema] = {}
        self.callbacks: dict[str, list[Callable]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

        # Encryption setup
        self.encryption_key = None
        self._init_encryption()

        # File watching
        self.auto_reload = auto_reload
        self.file_observer = None
        self.watched_files: set[Path] = set()

        # Load initial configuration
        self._load_all_configurations()

        # Start file observer if enabled
        if self.auto_reload:
            self._start_file_observer()

        self.logger.debug("ConfigManager initialized for environment: %s", environment)

    def _init_encryption(self):
        """Initialize encryption for sensitive data"""
        if not HAS_CRYPTO:
            self.logger.warning("Encryption not available - install cryptography package")
            return

        try:
            # Try to load existing key
            key_file = self.config_dir / ".encryption.key"

            if key_file.exists():
                with open(key_file, "rb") as f:
                    self.encryption_key = f.read()
            else:
                # Generate new key
                self.encryption_key = Fernet.generate_key()

                # Save key with restricted permissions
                with open(key_file, "wb") as f:
                    f.write(self.encryption_key)

                # Set file permissions (Unix-like systems)
                try:
                    os.chmod(key_file, 0o600)
                except Exception:
                    pass

            self.logger.debug("Encryption initialized")

        except Exception as e:
            self.logger.error("Encryption initialization failed: %s", e)

    def _load_all_configurations(self):
        """Load configurations from all sources"""
        try:
            # 1. Load default configuration
            self._load_defaults()

            # 2. Load configuration files
            self._load_config_files()

            # 2.5 Load repo-level regime policy if present.
            self._load_repo_regime_policy()

            # 2.6 Load repo-level agent handoff policy if present.
            self._load_repo_agent_handoff_policy()

            # 3. Load environment variables
            self._load_environment_variables()

            # 4. Validate merged configuration
            self._validate_configuration()

            # 5. Create initial backup
            self._backup_configuration()

            self.logger.debug("All configurations loaded successfully")

        except Exception as e:
            self.logger.error("Configuration loading failed: %s", e)
            self.error_handler.handle_error(e, "load_all_configurations")
            if isinstance(e, StartupValidationError) or e.__class__.__name__ == "ConfigurationError":  # noqa: E501
                raise
            # Use defaults on error
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration values"""
        defaults = {
            "application": {
                "name": "Tradov Trading System",
                "version": "2.0.0",
                "environment": self.environment,
                "debug": self.environment == "development",
                "timezone": "US/Eastern",
            },
            "logging": {
                "level": "INFO" if self.environment == "production" else "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": str(self.config_dir / "logs" / "tradov.log"),
                "max_size": "10MB",
                "backup_count": 5,
            },
            "database": {
                "type": "sqlite",
                "path": str(self.config_dir / "tradov.db"),
                "pool_size": 5,
                "echo": False,
            },
            "broker": {
                "provider": "interactive_brokers",
                "host": "127.0.0.1",
                "port": 4002,
                "client_id": 1,
                "account": "",
                "timeout": 30,
                "retry_count": 3,
                "connection_retry_delay": 5,
            },
            "trading": {
                "mode": "paper" if self.environment != "production" else "live",
                "market_data_type": 1,  # 1=Live, 2=Frozen, 3=Delayed, 4=Delayed Frozen
                "symbols": ["SPX"],
                "max_position_size": 10000,
                "max_daily_trades": 100,
                "enable_short_selling": True,
                "enable_options": True,
            },
            "risk": {
                "max_position_size": 10000,
                "max_portfolio_risk": 0.02,  # 2% max risk
                "max_daily_loss": 500,
                "max_drawdown": 0.10,  # 10% max drawdown
                "position_sizing_method": "fixed",
                "stop_loss_percent": 0.02,  # 2% stop loss
                "take_profit_percent": 0.04,  # 4% take profit
                "max_correlation": 0.7,
                "enable_circuit_breaker": True,
            },
            "strategies": {
                "enabled": [],
                "max_concurrent": 5,
                "default_allocation": 0.2,  # 20% per strategy
                "rebalance_frequency": "daily",
            },
            "notifications": {
                "email_enabled": False,
                "email_smtp_host": "",
                "email_smtp_port": 587,
                "email_from": "",
                "email_to": [],
                "telegram_enabled": False,
                "telegram_bot_token": "",
                "telegram_chat_id": "",
                "desktop_enabled": True,
            },
            "monitoring": {
                "health_check_interval": 60,  # seconds
                "metrics_collection_interval": 30,
                "performance_window_size": 1000,
                "alert_cooldown_minutes": 15,
            },
            "automation": {
                "enabled": True,
            },
            "autonomous_readiness": {
                "lean_mode": True,
                "observe_only_agents": True,
                "session_window": {
                    "primary_start_et": "09:30",
                    "primary_end_et": "16:15",
                    "first_entry_not_before_et": "09:45",
                    "zero_dte_no_new_risk_cutoff_et": "14:30",
                    "broker_cutoff_et": "16:00",
                    "broker_cutoff_buffer_minutes": 10,
                    "pin_risk_monitor_end_et": "17:30",
                    "fail_closed_if_cutoff_unknown_live": True,
                },
                "liquidity": {
                    "enabled": True,
                    "max_spread_pct": 0.12,
                    "max_spread_abs": 0.20,
                    "max_quote_age_ms": 1500,
                    "min_top_of_book_size": 10,
                    "min_open_interest": 500,
                    "min_volume": 50,
                    "min_oi_change_pct": -0.20,
                },
                "execution": {
                    "enabled": True,
                    "max_slippage_bps": 25,
                    "max_fill_latency_ms": 2500,
                    "max_partial_fill_ratio": 0.40,
                    "max_reject_rate_5m": 0.08,
                    "degrade_size_multiplier": 0.50,
                    "halt_on_quality_breach": True,
                },
                "event_clock": {
                    "enabled": True,
                    "sources": "calendar+manual",
                    "high_impact_only": True,
                    "blackout_pre_minutes": 30,
                    "blackout_post_minutes": 30,
                    "max_size_multiplier_during_event": 0.25,
                    "allowlist_strategies": [],
                },
                "macro_regime": {
                    # VIX9D / VIX short-end stress profile.
                    "vix9d_vix_warn_ratio": 1.05,
                    "vix9d_vix_fail_ratio": 1.12,
                    "vix9d_warn_abs": 23.0,
                    "vix9d_fail_abs": 28.0,

                    # VVIX vol-of-vol stress profile.
                    "vvix_warn": 100.0,
                    "vvix_fail": 115.0,

                    # CPC put/call crowding extremes.
                    "cpc_warn_high": 1.20,
                    "cpc_fail_high": 1.35,
                    "cpc_warn_low": 0.70,
                    "cpc_fail_low": 0.60,

                    # RVOL participation profile.
                    "rvol_warn": 0.80,
                    "rvol_fail": 0.55,

                    # QQQ / IWM relative confirmation vs TRAD (percentage points).
                    "qqq_rel_warn_pct": 0.35,
                    "qqq_rel_fail_pct": 0.75,
                    "iwm_rel_warn_pct": 0.40,
                    "iwm_rel_fail_pct": 0.90,

                    # XLK / XLF sector confirmation vs TRAD (percentage points).
                    "xlk_rel_warn_pct": 0.45,
                    "xlk_rel_fail_pct": 1.00,
                    "xlf_rel_warn_pct": 0.35,
                    "xlf_rel_fail_pct": 0.80,
                },
                "escalation": {
                    "warn_on_single_breach": True,
                    "degrade_on_two_breaches": True,
                    "halt_on_three_breaches": True,
                    "sustained_breach_minutes": 10,
                },
            },
            "api": {
                "enabled": False,
                "host": "127.0.0.1",
                "port": 8080,
                "auth_required": True,
                "ssl_enabled": False,
                "rate_limit": 100,  # requests per minute
            },
        }

        # Store defaults with metadata
        self._merge_config(defaults, ConfigSource.DEFAULT)

    def _load_config_files(self):
        """Load configuration from files"""
        # Main configuration file
        if self.config_path.exists() and self.config_path.is_file():
            self._load_config_file(self.config_path)
            self.watched_files.add(self.config_path)

        # Environment-specific configuration
        env_config_path = self.config_dir / f"config.{self.environment}.yaml"
        if env_config_path.exists():
            self._load_config_file(env_config_path)
            self.watched_files.add(env_config_path)

        # Local overrides (not in version control)
        local_config_path = self.config_dir / "config.local.yaml"
        if local_config_path.exists():
            self._load_config_file(local_config_path)
            self.watched_files.add(local_config_path)

        # Load additional config files in config directory
        for config_file in self.config_dir.glob("*.yaml"):
            if config_file not in self.watched_files and not config_file.name.startswith("."):
                self._load_config_file(config_file)
                self.watched_files.add(config_file)

    def _load_config_file(self, file_path: Path):
        """Load a single configuration file"""
        try:
            self.logger.info("Loading configuration from: %s", file_path)

            # Determine file format
            suffix = file_path.suffix.lower()

            if suffix in [".yaml", ".yml"]:
                config_data = self._load_yaml_file(file_path)
            elif suffix == ".json":
                config_data = self._load_json_file(file_path)
            elif suffix == ".toml":
                config_data = self._load_toml_file(file_path)
            elif suffix == ".ini":
                config_data = self._load_ini_file(file_path)
            elif suffix == ".env":
                config_data = self._load_env_file(file_path)
            else:
                self.logger.warning("Unsupported configuration format: %s", suffix)
                return

            if config_data:
                self._merge_config(config_data, ConfigSource.FILE)

        except Exception as e:
            self.logger.error("Failed to load config file %s: %s", file_path, e)
            self.error_handler.handle_error(e, f"load_config_file:{file_path}")

    def _load_repo_regime_policy(self):
        """Load repository regime policy JSON into autonomous_readiness namespace."""
        try:
            # Avoid overriding explicit values already loaded from config files/env.
            existing = self.get("autonomous_readiness.regime_policy")
            if isinstance(existing, dict) and existing:
                return

            repo_policy_path = Path(__file__).resolve().parents[2] / "config" / "regime_policy.json"
            if not repo_policy_path.exists():
                return

            policy = self._load_json_file(repo_policy_path)
            if not isinstance(policy, dict) or not policy:
                return

            self._merge_config(
                {"autonomous_readiness": {"regime_policy": policy}},
                ConfigSource.FILE,
            )
            self.watched_files.add(repo_policy_path)
            self.logger.debug("Loaded regime policy from: %s", repo_policy_path)
        except Exception as e:
            self.logger.warning("Failed to load repo regime policy: %s", e)

    def _load_repo_agent_handoff_policy(self):
        """Load repository agent handoff policy JSON into autonomous_readiness namespace."""
        try:
            existing = self.get("autonomous_readiness.agent_handoff_policy")
            if isinstance(existing, dict) and existing:
                return

            repo_policy_path = Path(__file__).resolve().parents[2] / "config" / "agent_handoff_policy.json"
            if not repo_policy_path.exists():
                return

            policy = self._load_json_file(repo_policy_path)
            if not isinstance(policy, dict) or not policy:
                return

            self._merge_config(
                {"autonomous_readiness": {"agent_handoff_policy": policy}},
                ConfigSource.FILE,
            )
            self.watched_files.add(repo_policy_path)
            self.logger.debug("Loaded agent handoff policy from: %s", repo_policy_path)
        except Exception as e:
            self.logger.warning("Failed to load repo agent handoff policy: %s", e)

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any]:
        """Load YAML configuration file"""
        with open(file_path) as f:
            return yaml.safe_load(f) or {}

    def _load_json_file(self, file_path: Path) -> dict[str, Any]:
        """Load JSON configuration file"""
        with open(file_path) as f:
            return json.load(f)

    def _load_toml_file(self, file_path: Path) -> dict[str, Any]:
        """Load TOML configuration file"""
        with open(file_path) as f:
            return toml.load(f)

    def _load_ini_file(self, file_path: Path) -> dict[str, Any]:
        """Load INI configuration file"""
        config = configparser.ConfigParser()
        config.read(file_path)

        # Convert to nested dictionary
        result = {}
        for section in config.sections():
            result[section] = dict(config.items(section))

        return result

    def _load_env_file(self, file_path: Path) -> dict[str, Any]:
        """Load .env configuration file"""
        result = {}

        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    result[key.strip()] = value.strip()

        return result

    def _load_environment_variables(self):
        """Load configuration from environment variables"""
        env_config = {}

        for key, value in os.environ.items():
            if key.startswith(DEFAULT_ENV_PREFIX):
                # Remove prefix and convert to lowercase
                config_key = key[len(DEFAULT_ENV_PREFIX) :].lower()

                # Convert underscores to dots for nested keys
                # e.g., TRADOV_BROKER_HOST -> broker.host
                config_key = config_key.replace("_", ".")

                # Parse value
                parsed_value = self._parse_env_value(value)

                # Build nested dictionary
                self._set_nested_value(env_config, config_key, parsed_value)

        if env_config:
            self._merge_config(env_config, ConfigSource.ENVIRONMENT)

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type"""
        # Try to parse as JSON first (for complex types)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

        # Boolean values
        if value.lower() in ["true", "yes", "1", "on"]:
            return True
        elif value.lower() in ["false", "no", "0", "off"]:
            return False

        # Numeric values
        try:
            if "." in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # List values (comma-separated)
        if "," in value:
            return [v.strip() for v in value.split(",")]

        # Default to string
        return value

    def _set_nested_value(self, d: dict[str, Any], key: str, value: Any):
        """Set value in nested dictionary using dot notation"""
        keys = key.split(".")
        current = d

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _merge_config(self, new_config: dict[str, Any], source: ConfigSource):
        """Merge new configuration with existing"""
        with self._lock:
            # Deep merge configurations
            self._deep_merge(self.config_data, new_config)

            # Track sources
            self._track_config_sources(new_config, source)

    def _deep_merge(self, base: dict[str, Any], update: dict[str, Any]):
        """Deep merge two dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _track_config_sources(self, config: dict[str, Any], source: ConfigSource, prefix: str = ""):
        """Track the source of each configuration value"""
        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._track_config_sources(value, source, full_key)
            else:
                # Check if value is sensitive
                is_sensitive = self._is_sensitive_key(full_key)

                # Encrypt sensitive values
                if is_sensitive and self.encryption_key and source != ConfigSource.DEFAULT:
                    encrypted_value = self._encrypt_value(value)
                    self.config_sources[full_key] = ConfigValue(
                        key=full_key, value=encrypted_value, source=source, encrypted=True
                    )
                else:
                    self.config_sources[full_key] = ConfigValue(
                        key=full_key, value=value, source=source, encrypted=False
                    )

    def _is_sensitive_key(self, key: str) -> bool:
        """Check if a configuration key contains sensitive data"""
        key_lower = key.lower()
        return any(re.match(pattern, key_lower) for pattern in SENSITIVE_KEY_PATTERNS)

    def _encrypt_value(self, value: Any) -> str:
        """Encrypt a configuration value"""
        if not self.encryption_key or not HAS_CRYPTO:
            return value

        try:
            f = Fernet(self.encryption_key)

            # Convert value to string
            value_str = json.dumps(value) if not isinstance(value, str) else value

            # Encrypt
            encrypted = f.encrypt(value_str.encode())

            return encrypted.decode()

        except Exception as e:
            self.logger.error("Encryption failed: %s", e)
            return value

    def _decrypt_value(self, encrypted_value: str) -> Any:
        """Decrypt a configuration value"""
        if not self.encryption_key or not HAS_CRYPTO:
            return encrypted_value

        try:
            f = Fernet(self.encryption_key)

            # Decrypt
            decrypted = f.decrypt(encrypted_value.encode())
            value_str = decrypted.decode()

            # Try to parse as JSON
            try:
                return json.loads(value_str)
            except json.JSONDecodeError:
                return value_str

        except Exception as e:
            self.logger.error("Decryption failed: %s", e)
            return encrypted_value

    # ==========================================================================
    # CONFIGURATION ACCESS
    # ==========================================================================
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            try:
                # Navigate nested dictionary
                value = self.config_data
                for k in key.split("."):
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        return default

                # Check if value needs decryption
                if key in self.config_sources and self.config_sources[key].encrypted:
                    return self._decrypt_value(value)

                return value

            except Exception as e:
                self.logger.error("Error getting config value %s: %s", key, e)
                return default

    def get_config(self, key: str, default: Any = None) -> Any:
        """Compatibility wrapper for callers that still expect get_config()."""
        return self.get(key, default)

    def is_feature_enabled(self, key: str) -> bool:
        """Compatibility wrapper for F-series feature-flag checks."""
        candidates = (
            f"features.{key}",
            f"feature_flags.{key}",
            key,
        )

        for candidate in candidates:
            value = self.get(candidate, None)
            if value is None:
                continue
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}

        return False

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values (with sensitive data masked)"""
        with self._lock:
            # Deep copy configuration
            config_copy = copy.deepcopy(self.config_data)

            # Mask sensitive values
            self._mask_sensitive_values(config_copy)

            return config_copy

    def _mask_sensitive_values(self, config: dict[str, Any], prefix: str = ""):
        """Mask sensitive values in configuration"""
        for key, value in list(config.items()):
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                self._mask_sensitive_values(value, full_key)
            elif self._is_sensitive_key(full_key):
                config[key] = "***MASKED***"

    def set(self, key: str, value: Any, source: str = "runtime") -> bool:
        """
        Set configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: New value
            source: Source of the change

        Returns:
            bool: True if successful
        """
        with self._lock:
            try:
                # Get old value for change tracking
                old_value = self.get(key)

                # Set new value
                self._set_nested_value(self.config_data, key, value)

                # Track source
                is_sensitive = self._is_sensitive_key(key)
                encrypted_value = (
                    self._encrypt_value(value) if is_sensitive and self.encryption_key else value
                )

                self.config_sources[key] = ConfigValue(
                    key=key,
                    value=encrypted_value,
                    source=ConfigSource.RUNTIME,
                    encrypted=is_sensitive,
                )

                # Record change
                change = ConfigChange(
                    timestamp=datetime.now(UTC),
                    key=key,
                    old_value=old_value if not is_sensitive else "***MASKED***",
                    new_value=value if not is_sensitive else "***MASKED***",
                    source=source,
                )
                self.change_history.append(change)

                # Notify callbacks
                self._notify_callbacks(key, old_value, value)

                self.logger.info("Configuration updated: %s", key)
                return True

            except Exception as e:
                self.logger.error("Error setting config value %s: %s", key, e)
                return False

    def update(self, updates: dict[str, Any], source: str = "runtime") -> bool:
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of updates
            source: Source of the changes

        Returns:
            bool: True if all updates successful
        """
        success = True

        for key, value in updates.items():
            if not self.set(key, value, source):
                success = False

        return success

    def delete(self, key: str) -> bool:
        """
        Delete configuration value.

        Args:
            key: Configuration key

        Returns:
            bool: True if successful
        """
        with self._lock:
            try:
                # Navigate to parent and delete key
                keys = key.split(".")
                parent = self.config_data

                for k in keys[:-1]:
                    if k in parent:
                        parent = parent[k]
                    else:
                        return False

                if keys[-1] in parent:
                    old_value = parent[keys[-1]]
                    del parent[keys[-1]]

                    # Remove from sources
                    if key in self.config_sources:
                        del self.config_sources[key]

                    # Record change
                    change = ConfigChange(
                        timestamp=datetime.now(UTC),
                        key=key,
                        old_value=old_value,
                        new_value=None,
                        source="runtime",
                    )
                    self.change_history.append(change)

                    return True

                return False

            except Exception as e:
                self.logger.error("Error deleting config value %s: %s", key, e)
                return False

    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    def load_schema(self, schema_path: Path):
        """Load configuration schema from file"""
        try:
            with open(schema_path) as f:
                schema_data = json.load(f)

            schema = ConfigSchema(
                version=schema_data.get("version", "1.0"),
                properties=schema_data.get("properties", {}),
                required=schema_data.get("required", []),
                additional_properties=schema_data.get("additionalProperties", False),
                definitions=schema_data.get("definitions"),
            )

            self.schemas[schema_path.stem] = schema
            self.logger.info("Loaded configuration schema: %s", schema_path.stem)

        except Exception as e:
            self.logger.error("Failed to load schema %s: %s", schema_path, e)

    def validate(self, schema_name: str | None = None) -> list[str]:
        """
        Validate configuration against schema.

        Args:
            schema_name: Schema to validate against (None for basic validation)

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Basic validation
        errors.extend(self._validate_basic())

        # Schema validation if available
        if schema_name and schema_name in self.schemas:
            errors.extend(self._validate_against_schema(schema_name))

        return errors

    def _validate_basic(self) -> list[str]:
        """Perform basic configuration validation"""
        errors = []

        # Check required top-level sections
        required_sections = ["application", "logging", "broker", "trading", "risk"]
        for section in required_sections:
            if section not in self.config_data:
                errors.append(f"Missing required section: {section}")

        # Validate data types
        validations = [
            ("broker.port", int, lambda x: 1 <= x <= 65535),
            ("broker.timeout", (int, float), lambda x: x > 0),
            ("risk.max_position_size", (int, float), lambda x: x > 0),
            ("risk.max_daily_loss", (int, float), lambda x: x > 0),
            ("trading.max_daily_trades", int, lambda x: x > 0),
        ]

        for key, expected_type, validator in validations:
            value = self.get(key)
            if value is not None:
                if not isinstance(value, expected_type):
                    errors.append(f"{key} must be {expected_type.__name__}")
                elif validator and not validator(value):
                    errors.append(f"{key} value {value} is invalid")

        return errors

    def _validate_against_schema(self, schema_name: str) -> list[str]:
        """Validate configuration against JSON schema"""
        errors = []
        schema = self.schemas[schema_name]

        try:
            # Create JSON schema
            json_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": schema.properties,
                "required": schema.required,
                "additionalProperties": schema.additional_properties,
            }

            if schema.definitions:
                json_schema["definitions"] = schema.definitions

            # Validate
            validator = Draft7Validator(json_schema)

            for error in validator.iter_errors(self.config_data):
                errors.append(f"{'.'.join(str(p) for p in error.path)}: {error.message}")

        except Exception as e:
            errors.append(f"Schema validation error: {e}")

        return errors

    def _validate_configuration(self):
        """Validate loaded configuration"""
        # --- Fail-fast env-var check (item #8 hardening) --------------------
        # Import lazily to avoid triggering load_dotenv() at module-import time
        # (which can change os.environ and affect unrelated test skip conditions).
        try:
            from config.config import (
                ConfigurationError as _ConfigurationError,
                validate_startup_config as _validate_startup_config,
            )

            HAS_STARTUP_VALIDATOR = True
        except Exception:
            HAS_STARTUP_VALIDATOR = False
            _ConfigurationError = RuntimeError  # type: ignore[misc,assignment]
            _validate_startup_config = None  # type: ignore[assignment]

        if HAS_STARTUP_VALIDATOR and _validate_startup_config is not None:
            try:
                _validate_startup_config()
            except _ConfigurationError as exc:
                self.logger.critical(
                    "STARTUP BLOCKED — configuration errors detected:\n%s", exc
                )
                raise  # Propagate so the application does not silently start

        mode = "paper"
        if hasattr(self, "get"):
            try:
                mode = str(self.get("trading.mode", "paper")).strip().lower()
            except Exception:
                mode = "paper"

        config_for_validation = getattr(self, "config_data", {})
        readiness_result = ConfigManager.validate_autonomous_readiness_config(
            self,
            config_for_validation,
            mode,
        )

        if hasattr(self, "config_data"):
            self.config_data = readiness_result["effective"]

        if readiness_result["warnings"]:
            self.logger.warning(
                "Autonomous readiness validation warnings: %s",
                len(readiness_result["warnings"]),
            )
            for warning in readiness_result["warnings"]:
                self.logger.warning("  - %s", warning)

        if readiness_result["errors"]:
            self.logger.error(
                "Autonomous readiness validation errors: %s",
                len(readiness_result["errors"]),
            )
            for error in readiness_result["errors"]:
                self.logger.error("  - %s", error)

        if not readiness_result["ok"] and mode == "live":
            raise StartupValidationError(
                "autonomous readiness validation failed in live mode: "
                + "; ".join(readiness_result["errors"])
            )

        self.logger.debug(
            "Autonomous readiness startup report | mode=%s ok=%s warnings=%s errors=%s",
            mode,
            readiness_result["ok"],
            len(readiness_result["warnings"]),
            len(readiness_result["errors"]),
        )

        # --- Schema / value validation via ConfigManager.validate() ----------
        errors = self.validate()

        if errors:
            self.logger.warning("Configuration validation found %s issues:", len(errors))
            for error in errors:
                self.logger.warning("  - %s", error)
        else:
            self.logger.debug("Configuration validation passed")

    def validate_autonomous_readiness_config(
        self,
        config: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        """Validate autonomous readiness config and return effective startup settings."""
        effective = copy.deepcopy(config)
        warnings: list[str] = []
        errors: list[str] = []

        effective = self._apply_autonomous_readiness_env_overrides(effective)

        def require_bool(path: str):
            value = self._get_nested_path_value(effective, path)
            if not isinstance(value, bool):
                errors.append(f"{path} must be bool")

        def require_int_range(
            path: str,
            lo: int,
            hi: int,
            severity: str = "ERROR",
            fallback: int | None = None,
        ):
            value = self._get_nested_path_value(effective, path)
            is_valid = isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi
            if not is_valid:
                message = f"{path} out of range [{lo}, {hi}]"
                if severity == "WARN" and fallback is not None:
                    warnings.append(f"{message}; fallback={fallback}")
                    self._set_nested_value(effective, path, fallback)
                elif severity == "WARN":
                    warnings.append(message)
                else:
                    errors.append(message)

        def require_float_range(
            path: str,
            lo: float,
            hi: float,
            severity: str = "ERROR",
            fallback: float | None = None,
        ):
            value = self._get_nested_path_value(effective, path)
            valid_numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if not valid_numeric or float(value) < lo or float(value) > hi:
                message = f"{path} out of range [{lo}, {hi}]"
                if severity == "WARN" and fallback is not None:
                    warnings.append(f"{message}; fallback={fallback}")
                    self._set_nested_value(effective, path, fallback)
                elif severity == "WARN":
                    warnings.append(message)
                else:
                    errors.append(message)

        def require_time_string(path: str):
            value = self._get_nested_path_value(effective, path)
            if not isinstance(value, str) or re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value.strip()) is None:
                errors.append(f"{path} must be HH:MM (24h)")

        require_time_string("autonomous_readiness.session_window.primary_start_et")
        require_time_string("autonomous_readiness.session_window.primary_end_et")
        require_time_string("autonomous_readiness.session_window.first_entry_not_before_et")
        require_time_string("autonomous_readiness.session_window.zero_dte_no_new_risk_cutoff_et")
        require_time_string("autonomous_readiness.session_window.broker_cutoff_et")
        require_time_string("autonomous_readiness.session_window.pin_risk_monitor_end_et")
        require_int_range("autonomous_readiness.session_window.broker_cutoff_buffer_minutes", 0, 120)
        require_bool("autonomous_readiness.session_window.fail_closed_if_cutoff_unknown_live")

        try:
            session_cfg = self._get_nested_path_value(effective, "autonomous_readiness.session_window", {})
            if isinstance(session_cfg, dict):
                start_et = datetime.strptime(str(session_cfg.get("primary_start_et", "09:30")), "%H:%M").time()
                end_et = datetime.strptime(str(session_cfg.get("primary_end_et", "16:15")), "%H:%M").time()
                first_entry_et = datetime.strptime(
                    str(session_cfg.get("first_entry_not_before_et", "09:45")),
                    "%H:%M",
                ).time()
                no_new_risk_et = datetime.strptime(
                    str(session_cfg.get("zero_dte_no_new_risk_cutoff_et", "14:30")),
                    "%H:%M",
                ).time()
                broker_cutoff_et = datetime.strptime(
                    str(session_cfg.get("broker_cutoff_et", "16:00")),
                    "%H:%M",
                ).time()

                if start_et >= end_et:
                    errors.append("autonomous_readiness.session_window.primary_start_et must be before primary_end_et")
                if first_entry_et < start_et:
                    errors.append("autonomous_readiness.session_window.first_entry_not_before_et must be >= primary_start_et")
                if first_entry_et > end_et:
                    errors.append("autonomous_readiness.session_window.first_entry_not_before_et must be <= primary_end_et")
                if no_new_risk_et > end_et:
                    errors.append("autonomous_readiness.session_window.zero_dte_no_new_risk_cutoff_et must be <= primary_end_et")
                if broker_cutoff_et > end_et:
                    warnings.append("autonomous_readiness.session_window.broker_cutoff_et is after primary_end_et")
        except Exception:
            errors.append("autonomous_readiness.session_window contains invalid time ordering")

        require_float_range("autonomous_readiness.liquidity.max_spread_pct", 0.01, 0.50)
        require_float_range("autonomous_readiness.liquidity.max_spread_abs", 0.01, 2.00)
        require_int_range("autonomous_readiness.liquidity.max_quote_age_ms", 100, 10000)
        require_int_range(
            "autonomous_readiness.liquidity.min_top_of_book_size",
            1,
            1000,
            severity="WARN",
            fallback=10,
        )
        require_int_range("autonomous_readiness.liquidity.min_open_interest", 0, 1_000_000)
        require_int_range("autonomous_readiness.liquidity.min_volume", 0, 1_000_000)
        require_float_range(
            "autonomous_readiness.liquidity.min_oi_change_pct",
            -1.00,
            1.00,
            severity="WARN",
            fallback=-0.20,
        )

        require_bool("autonomous_readiness.observe_only_agents")

        require_float_range("autonomous_readiness.execution.max_slippage_bps", 1, 200)
        require_int_range("autonomous_readiness.execution.max_fill_latency_ms", 100, 20000)
        require_float_range("autonomous_readiness.execution.max_partial_fill_ratio", 0.00, 1.00)
        require_float_range("autonomous_readiness.execution.max_reject_rate_5m", 0.00, 1.00)
        require_float_range("autonomous_readiness.execution.degrade_size_multiplier", 0.10, 1.00)
        require_bool("autonomous_readiness.execution.halt_on_quality_breach")

        require_bool("autonomous_readiness.event_clock.enabled")
        sources = self._get_nested_path_value(effective, "autonomous_readiness.event_clock.sources")
        if sources not in {"calendar", "manual", "calendar+manual"}:
            warnings.append("autonomous_readiness.event_clock.sources invalid; fallback=manual")
            self._set_nested_value(effective, "autonomous_readiness.event_clock.sources", "manual")

        require_bool("autonomous_readiness.event_clock.high_impact_only")
        require_int_range("autonomous_readiness.event_clock.blackout_pre_minutes", 0, 240)
        require_int_range("autonomous_readiness.event_clock.blackout_post_minutes", 0, 240)
        require_float_range(
            "autonomous_readiness.event_clock.max_size_multiplier_during_event",
            0.00,
            1.00,
        )

        # Macro regime thresholds for F09 trust gates (VIX9D/VVIX/CPC/RVOL).
        require_float_range("autonomous_readiness.macro_regime.vix9d_vix_warn_ratio", 0.80, 1.80)
        require_float_range("autonomous_readiness.macro_regime.vix9d_vix_fail_ratio", 0.85, 2.00)
        require_float_range("autonomous_readiness.macro_regime.vix9d_warn_abs", 10.0, 80.0)
        require_float_range("autonomous_readiness.macro_regime.vix9d_fail_abs", 10.0, 100.0)
        require_float_range("autonomous_readiness.macro_regime.vvix_warn", 50.0, 250.0)
        require_float_range("autonomous_readiness.macro_regime.vvix_fail", 50.0, 300.0)
        require_float_range("autonomous_readiness.macro_regime.cpc_warn_high", 0.80, 2.50)
        require_float_range("autonomous_readiness.macro_regime.cpc_fail_high", 0.80, 3.00)
        require_float_range("autonomous_readiness.macro_regime.cpc_warn_low", 0.20, 1.20)
        require_float_range("autonomous_readiness.macro_regime.cpc_fail_low", 0.20, 1.20)
        require_float_range("autonomous_readiness.macro_regime.rvol_warn", 0.20, 3.00)
        require_float_range("autonomous_readiness.macro_regime.rvol_fail", 0.10, 2.50)
        require_float_range("autonomous_readiness.macro_regime.qqq_rel_warn_pct", 0.05, 5.00)
        require_float_range("autonomous_readiness.macro_regime.qqq_rel_fail_pct", 0.05, 6.00)
        require_float_range("autonomous_readiness.macro_regime.iwm_rel_warn_pct", 0.05, 5.00)
        require_float_range("autonomous_readiness.macro_regime.iwm_rel_fail_pct", 0.05, 6.00)
        require_float_range("autonomous_readiness.macro_regime.xlk_rel_warn_pct", 0.05, 5.00)
        require_float_range("autonomous_readiness.macro_regime.xlk_rel_fail_pct", 0.05, 6.00)
        require_float_range("autonomous_readiness.macro_regime.xlf_rel_warn_pct", 0.05, 5.00)
        require_float_range("autonomous_readiness.macro_regime.xlf_rel_fail_pct", 0.05, 6.00)

        allowlist_path = "autonomous_readiness.event_clock.allowlist_strategies"
        allowlist = self._get_nested_path_value(effective, allowlist_path)
        if allowlist is not None:
            if isinstance(allowlist, list):
                filtered = [item for item in allowlist if isinstance(item, str) and item.strip()]
                if len(filtered) != len(allowlist):
                    warnings.append(
                        "autonomous_readiness.event_clock.allowlist_strategies contains invalid items; dropping invalid values"  # noqa: E501
                    )
                self._set_nested_value(effective, allowlist_path, filtered)
            else:
                warnings.append(
                    "autonomous_readiness.event_clock.allowlist_strategies must be list[str]; fallback=[]"  # noqa: E501
                )
                self._set_nested_value(effective, allowlist_path, [])

        degrade = self._get_nested_path_value(
            effective,
            "autonomous_readiness.execution.degrade_size_multiplier",
        )
        event_mult = self._get_nested_path_value(
            effective,
            "autonomous_readiness.event_clock.max_size_multiplier_during_event",
        )

        # Macro-regime ordering checks (warn/fail pairs should be monotonic).
        vix_warn_ratio = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.vix9d_vix_warn_ratio",
        )
        vix_fail_ratio = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.vix9d_vix_fail_ratio",
        )
        if isinstance(vix_warn_ratio, (int, float)) and isinstance(vix_fail_ratio, (int, float)):
            if float(vix_fail_ratio) < float(vix_warn_ratio):
                warnings.append(
                    "autonomous_readiness.macro_regime.vix9d_vix_fail_ratio < warn_ratio; fallback to warn_ratio"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.vix9d_vix_fail_ratio",
                    float(vix_warn_ratio),
                )

        vvix_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.vvix_warn",
        )
        vvix_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.vvix_fail",
        )
        if isinstance(vvix_warn, (int, float)) and isinstance(vvix_fail, (int, float)):
            if float(vvix_fail) < float(vvix_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.vvix_fail < vvix_warn; fallback to vvix_warn"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.vvix_fail",
                    float(vvix_warn),
                )

        cpc_warn_high = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.cpc_warn_high",
        )
        cpc_fail_high = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.cpc_fail_high",
        )
        if isinstance(cpc_warn_high, (int, float)) and isinstance(cpc_fail_high, (int, float)):
            if float(cpc_fail_high) < float(cpc_warn_high):
                warnings.append(
                    "autonomous_readiness.macro_regime.cpc_fail_high < cpc_warn_high; fallback to cpc_warn_high"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.cpc_fail_high",
                    float(cpc_warn_high),
                )

        cpc_warn_low = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.cpc_warn_low",
        )
        cpc_fail_low = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.cpc_fail_low",
        )
        if isinstance(cpc_warn_low, (int, float)) and isinstance(cpc_fail_low, (int, float)):
            if float(cpc_fail_low) > float(cpc_warn_low):
                warnings.append(
                    "autonomous_readiness.macro_regime.cpc_fail_low > cpc_warn_low; fallback to cpc_warn_low"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.cpc_fail_low",
                    float(cpc_warn_low),
                )

        rvol_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.rvol_warn",
        )
        rvol_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.rvol_fail",
        )
        if isinstance(rvol_warn, (int, float)) and isinstance(rvol_fail, (int, float)):
            if float(rvol_fail) > float(rvol_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.rvol_fail > rvol_warn; fallback to rvol_warn"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.rvol_fail",
                    float(rvol_warn),
                )

        qqq_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.qqq_rel_warn_pct",
        )
        qqq_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.qqq_rel_fail_pct",
        )
        if isinstance(qqq_warn, (int, float)) and isinstance(qqq_fail, (int, float)):
            if float(qqq_fail) < float(qqq_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.qqq_rel_fail_pct < qqq_rel_warn_pct; fallback to qqq_rel_warn_pct"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.qqq_rel_fail_pct",
                    float(qqq_warn),
                )

        iwm_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.iwm_rel_warn_pct",
        )
        iwm_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.iwm_rel_fail_pct",
        )
        if isinstance(iwm_warn, (int, float)) and isinstance(iwm_fail, (int, float)):
            if float(iwm_fail) < float(iwm_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.iwm_rel_fail_pct < iwm_rel_warn_pct; fallback to iwm_rel_warn_pct"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.iwm_rel_fail_pct",
                    float(iwm_warn),
                )

        xlk_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.xlk_rel_warn_pct",
        )
        xlk_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.xlk_rel_fail_pct",
        )
        if isinstance(xlk_warn, (int, float)) and isinstance(xlk_fail, (int, float)):
            if float(xlk_fail) < float(xlk_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.xlk_rel_fail_pct < xlk_rel_warn_pct; fallback to xlk_rel_warn_pct"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.xlk_rel_fail_pct",
                    float(xlk_warn),
                )

        xlf_warn = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.xlf_rel_warn_pct",
        )
        xlf_fail = self._get_nested_path_value(
            effective,
            "autonomous_readiness.macro_regime.xlf_rel_fail_pct",
        )
        if isinstance(xlf_warn, (int, float)) and isinstance(xlf_fail, (int, float)):
            if float(xlf_fail) < float(xlf_warn):
                warnings.append(
                    "autonomous_readiness.macro_regime.xlf_rel_fail_pct < xlf_rel_warn_pct; fallback to xlf_rel_warn_pct"  # noqa: E501
                )
                self._set_nested_value(
                    effective,
                    "autonomous_readiness.macro_regime.xlf_rel_fail_pct",
                    float(xlf_warn),
                )
        if isinstance(degrade, (int, float)) and isinstance(event_mult, (int, float)):
            if float(degrade) < float(event_mult):
                errors.append(
                    "autonomous_readiness.execution.degrade_size_multiplier should be >= autonomous_readiness.event_clock.max_size_multiplier_during_event"  # noqa: E501
                )

        pre = self._get_nested_path_value(
            effective,
            "autonomous_readiness.event_clock.blackout_pre_minutes",
        )
        post = self._get_nested_path_value(
            effective,
            "autonomous_readiness.event_clock.blackout_post_minutes",
        )
        event_enabled = self._get_nested_path_value(effective, "autonomous_readiness.event_clock.enabled")  # noqa: E501
        if event_enabled is True and pre == 0 and post == 0:
            errors.append(
                "autonomous_readiness.event_clock.enabled=true requires non-zero pre or post blackout window"  # noqa: E501
            )

        halt_on_quality_breach = self._get_nested_path_value(
            effective,
            "autonomous_readiness.execution.halt_on_quality_breach",
        )
        execution_cfg = self._get_nested_path_value(effective, "autonomous_readiness.execution")
        if halt_on_quality_breach is True and isinstance(execution_cfg, dict):
            required_keys = {
                "max_slippage_bps",
                "max_fill_latency_ms",
                "max_reject_rate_5m",
            }
            if not required_keys.issubset(set(execution_cfg.keys())):
                errors.append(
                    "autonomous_readiness.execution.halt_on_quality_breach=true requires max_slippage_bps, max_fill_latency_ms, and max_reject_rate_5m"  # noqa: E501
                )

        normalized_mode = mode.strip().lower() if isinstance(mode, str) else "paper"
        ok = len(errors) == 0

        if not ok and normalized_mode != "live":
            self._set_nested_value(effective, "automation.enabled", False)
            warnings.append("paper mode: blocking errors present, automation disabled")
            ok = True

        return {
            "ok": ok,
            "effective": effective,
            "warnings": warnings,
            "errors": errors,
        }

    def _apply_autonomous_readiness_env_overrides(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply documented env overrides for autonomous readiness settings."""
        effective = copy.deepcopy(config)
        env_key_to_path = {
            "TRADOV_LEAN_MODE": "autonomous_readiness.lean_mode",
            "TRADOV_OBSERVE_ONLY_AGENTS": "autonomous_readiness.observe_only_agents",
            "TRADOV_SESSION_PRIMARY_START_ET": "autonomous_readiness.session_window.primary_start_et",
            "TRADOV_SESSION_PRIMARY_END_ET": "autonomous_readiness.session_window.primary_end_et",
            "TRADOV_FIRST_ENTRY_NOT_BEFORE_ET": "autonomous_readiness.session_window.first_entry_not_before_et",
            "TRADOV_ZERO_DTE_NO_NEW_RISK_CUTOFF_ET": "autonomous_readiness.session_window.zero_dte_no_new_risk_cutoff_et",  # noqa: E501
            "TRADOV_BROKER_CUTOFF_ET": "autonomous_readiness.session_window.broker_cutoff_et",
            "TRADOV_BROKER_CUTOFF_BUFFER_MINUTES": "autonomous_readiness.session_window.broker_cutoff_buffer_minutes",  # noqa: E501
            "TRADOV_PIN_RISK_MONITOR_END_ET": "autonomous_readiness.session_window.pin_risk_monitor_end_et",  # noqa: E501
            "TRADOV_FAIL_CLOSED_IF_CUTOFF_UNKNOWN_LIVE": "autonomous_readiness.session_window.fail_closed_if_cutoff_unknown_live",  # noqa: E501
            "TRADOV_LIQUIDITY_ENABLED": "autonomous_readiness.liquidity.enabled",
            "TRADOV_LIQUIDITY_MAX_SPREAD_PCT": "autonomous_readiness.liquidity.max_spread_pct",
            "TRADOV_LIQUIDITY_MAX_SPREAD_ABS": "autonomous_readiness.liquidity.max_spread_abs",
            "TRADOV_LIQUIDITY_MAX_QUOTE_AGE_MS": "autonomous_readiness.liquidity.max_quote_age_ms",
            "TRADOV_LIQUIDITY_MIN_TOP_OF_BOOK_SIZE": "autonomous_readiness.liquidity.min_top_of_book_size",  # noqa: E501
            "TRADOV_LIQUIDITY_MIN_OPEN_INTEREST": "autonomous_readiness.liquidity.min_open_interest",  # noqa: E501
            "TRADOV_LIQUIDITY_MIN_VOLUME": "autonomous_readiness.liquidity.min_volume",
            "TRADOV_LIQUIDITY_MIN_OI_CHANGE_PCT": "autonomous_readiness.liquidity.min_oi_change_pct",  # noqa: E501
            "TRADOV_EXECUTION_ENABLED": "autonomous_readiness.execution.enabled",
            "TRADOV_EXECUTION_MAX_SLIPPAGE_BPS": "autonomous_readiness.execution.max_slippage_bps",
            "TRADOV_EXECUTION_MAX_FILL_LATENCY_MS": "autonomous_readiness.execution.max_fill_latency_ms",  # noqa: E501
            "TRADOV_EXECUTION_MAX_PARTIAL_FILL_RATIO": "autonomous_readiness.execution.max_partial_fill_ratio",  # noqa: E501
            "TRADOV_EXECUTION_MAX_REJECT_RATE_5M": "autonomous_readiness.execution.max_reject_rate_5m",  # noqa: E501
            "TRADOV_EXECUTION_DEGRADE_SIZE_MULTIPLIER": "autonomous_readiness.execution.degrade_size_multiplier",  # noqa: E501
            "TRADOV_EXECUTION_HALT_ON_QUALITY_BREACH": "autonomous_readiness.execution.halt_on_quality_breach",  # noqa: E501
            "TRADOV_EVENT_CLOCK_ENABLED": "autonomous_readiness.event_clock.enabled",
            "TRADOV_EVENT_CLOCK_SOURCES": "autonomous_readiness.event_clock.sources",
            "TRADOV_EVENT_CLOCK_HIGH_IMPACT_ONLY": "autonomous_readiness.event_clock.high_impact_only",  # noqa: E501
            "TRADOV_EVENT_CLOCK_BLACKOUT_PRE_MINUTES": "autonomous_readiness.event_clock.blackout_pre_minutes",  # noqa: E501
            "TRADOV_EVENT_CLOCK_BLACKOUT_POST_MINUTES": "autonomous_readiness.event_clock.blackout_post_minutes",  # noqa: E501
            "TRADOV_EVENT_CLOCK_MAX_SIZE_MULTIPLIER_DURING_EVENT": "autonomous_readiness.event_clock.max_size_multiplier_during_event",  # noqa: E501
            "TRADOV_EVENT_CLOCK_ALLOWLIST_STRATEGIES": "autonomous_readiness.event_clock.allowlist_strategies",  # noqa: E501
            "TRADOV_ESCALATION_WARN_ON_SINGLE_BREACH": "autonomous_readiness.escalation.warn_on_single_breach",  # noqa: E501
            "TRADOV_ESCALATION_DEGRADE_ON_TWO_BREACHES": "autonomous_readiness.escalation.degrade_on_two_breaches",  # noqa: E501
            "TRADOV_ESCALATION_HALT_ON_THREE_BREACHES": "autonomous_readiness.escalation.halt_on_three_breaches",  # noqa: E501
            "TRADOV_ESCALATION_SUSTAINED_BREACH_MINUTES": "autonomous_readiness.escalation.sustained_breach_minutes",  # noqa: E501
        }

        for env_key, path in env_key_to_path.items():
            if env_key in os.environ:
                self._set_nested_value(effective, path, self._parse_env_value(os.environ[env_key]))

        return effective

    def _get_nested_path_value(self, config: dict[str, Any], path: str, default: Any = None) -> Any:
        """Get a nested configuration value from an arbitrary config dictionary."""
        current: Any = config
        for key in path.split("."):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    # ==========================================================================
    # HOT RELOAD
    # ==========================================================================
    def _start_file_observer(self):
        """Start watching configuration files for changes"""
        try:
            self.file_observer = Observer()
            handler = ConfigFileHandler(self)

            # Watch config directory
            self.file_observer.schedule(handler, str(self.config_dir), recursive=False)

            self.file_observer.start()
            self.logger.debug("Configuration file monitoring started")

        except Exception as e:
            self.logger.error("Failed to start file observer: %s", e)

    def _stop_file_observer(self):
        """Stop watching configuration files"""
        if self.file_observer and self.file_observer.is_alive():
            self.file_observer.stop()
            self.file_observer.join()

    def _on_config_file_changed(self, file_path: Path):
        """Handle configuration file change"""
        try:
            # Reload the specific file
            self.logger.info("Reloading configuration file: %s", file_path)

            # Create backup before reloading
            self._backup_configuration()

            # Reload file
            self._load_config_file(file_path)

            # Revalidate
            self._validate_configuration()

            # Notify all callbacks
            self._notify_all_callbacks()

        except Exception as e:
            self.logger.error("Error reloading configuration: %s", e)

    def reload(self) -> bool:
        """
        Manually reload all configurations.

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info("Manual configuration reload requested")

            # Clear current configuration
            with self._lock:
                self.config_data.clear()
                self.config_sources.clear()

            # Reload everything
            self._load_all_configurations()

            # Notify callbacks
            self._notify_all_callbacks()

            return True

        except Exception as e:
            self.logger.error("Configuration reload failed: %s", e)
            return False

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================
    def register_callback(self, key_pattern: str, callback: Callable[[str, Any, Any], None]):
        """
        Register callback for configuration changes.

        Args:
            key_pattern: Key pattern to watch (supports wildcards)
            callback: Function to call on change (key, old_value, new_value)
        """
        self.callbacks[key_pattern].append(callback)

    def unregister_callback(self, key_pattern: str, callback: Callable):
        """Unregister callback"""
        if key_pattern in self.callbacks and callback in self.callbacks[key_pattern]:
            self.callbacks[key_pattern].remove(callback)

    def _notify_callbacks(self, key: str, old_value: Any, new_value: Any):
        """Notify callbacks about configuration change"""
        for pattern, callbacks in self.callbacks.items():
            if self._match_pattern(key, pattern):
                for callback in callbacks:
                    try:
                        callback(key, old_value, new_value)
                    except Exception as e:
                        self.logger.error("Callback error: %s", e)

    def _notify_all_callbacks(self):
        """Notify all callbacks (used for reload)"""
        for _pattern, callbacks in self.callbacks.items():
            for callback in callbacks:
                try:
                    callback("*", None, None)  # Special reload notification
                except Exception as e:
                    self.logger.error("Callback error: %s", e)

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Check if key matches pattern (supports * wildcard)"""
        import fnmatch

        return fnmatch.fnmatch(key, pattern)

    # ==========================================================================
    # BACKUP AND RESTORE
    # ==========================================================================
    def _backup_configuration(self):
        """Create configuration backup"""
        try:
            backup_dir = self.config_dir / "backups"
            backup_dir.mkdir(exist_ok=True)

            # Create backup filename with timestamp
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"config_backup_{timestamp}.json"

            # Save configuration
            backup_data = {
                "timestamp": datetime.now(UTC).isoformat(),
                "environment": self.environment,
                "config": self.get_all(),  # This masks sensitive data
                "sources": {k: v.source.name for k, v in self.config_sources.items()},
            }

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            # Clean old backups
            self._clean_old_backups(backup_dir)

            self.logger.debug("Configuration backed up to: %s", backup_file)

        except Exception as e:
            self.logger.error("Backup failed: %s", e)

    def _clean_old_backups(self, backup_dir: Path):
        """Remove old backup files"""
        try:
            backups = sorted(backup_dir.glob("config_backup_*.json"))

            # Keep only the most recent backups
            while len(backups) > CONFIG_BACKUP_COUNT:
                oldest = backups.pop(0)
                oldest.unlink()

        except Exception as e:
            self.logger.error("Backup cleanup failed: %s", e)

    def restore_backup(self, backup_file: Path) -> bool:
        """
        Restore configuration from backup.

        Args:
            backup_file: Path to backup file

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info("Restoring configuration from: %s", backup_file)

            with open(backup_file) as f:
                backup_data = json.load(f)

            # Clear current configuration
            with self._lock:
                self.config_data.clear()
                self.config_sources.clear()

            # Restore configuration
            self._merge_config(backup_data["config"], ConfigSource.FILE)

            # Validate
            self._validate_configuration()

            # Notify callbacks
            self._notify_all_callbacks()

            self.logger.info("Configuration restored successfully")
            return True

        except Exception as e:
            self.logger.error("Restore failed: %s", e)
            return False

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def get_checksum(self) -> str:
        """Get configuration checksum for change detection"""
        try:
            # Create stable string representation
            config_str = json.dumps(self.config_data, sort_keys=True, default=str)

            # Calculate SHA256 hash
            return hashlib.sha256(config_str.encode()).hexdigest()

        except Exception as e:
            self.logger.error("Checksum calculation failed: %s", e)
            return ""

    def get_change_history(self, limit: int | None = None) -> list[ConfigChange]:
        """
        Get configuration change history.

        Args:
            limit: Maximum number of changes to return

        Returns:
            List of configuration changes
        """
        if limit:
            return self.change_history[-limit:]
        return self.change_history.copy()

    def export_config(
        self,
        output_path: Path,
        format: ConfigFormat = ConfigFormat.YAML,
        include_sensitive: bool = False,
    ) -> bool:
        """
        Export configuration to file.

        Args:
            output_path: Output file path
            format: Export format
            include_sensitive: Include sensitive values (decrypted)

        Returns:
            bool: True if successful
        """
        try:
            # Get configuration
            if include_sensitive:
                # Get raw configuration with decrypted values
                export_data = copy.deepcopy(self.config_data)
                # Decrypt sensitive values
                for key, source in self.config_sources.items():
                    if source.encrypted:
                        decrypted_value = self._decrypt_value(self.get(key))
                        self._set_nested_value(export_data, key, decrypted_value)
            else:
                export_data = self.get_all()  # Masked sensitive data

            # Export based on format
            if format == ConfigFormat.YAML:
                with open(output_path, "w") as f:
                    yaml.dump(export_data, f, default_flow_style=False)
            elif format == ConfigFormat.JSON:
                with open(output_path, "w") as f:
                    json.dump(export_data, f, indent=2, default=str)
            elif format == ConfigFormat.TOML:
                with open(output_path, "w") as f:
                    toml.dump(export_data, f)
            else:
                self.logger.error("Unsupported export format: %s", format)
                return False

            self.logger.info("Configuration exported to: %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Export failed: %s", e)
            return False

    def print_config(self, section: str | None = None):
        """Print configuration to console (for debugging)"""
        config = self.get(section) if section else self.get_all()

        logging.info("\n%s", '='*60)
        logging.info("Configuration (%s)", self.environment)
        logging.info("%s", '='*60)
        logging.info(yaml.dump(config, default_flow_style=False))
        logging.info("%s\n", '='*60)

    def __del__(self):
        """Cleanup on deletion"""
        try:
            if hasattr(self, "file_observer"):
                self._stop_file_observer()
        except Exception:
            # Destructors should never raise during interpreter shutdown or tests.
            pass


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_config_manager_instance: ConfigManager | None = None
_config_lock = threading.Lock()


def get_config_manager(config_path: Path | None = None) -> ConfigManager:
    """
    Get singleton ConfigManager instance.

    Args:
        config_path: Configuration file path (for first call)

    Returns:
        ConfigManager instance
    """
    global _config_manager_instance

    with _config_lock:
        if _config_manager_instance is None:
            _config_manager_instance = ConfigManager(config_path)

        return _config_manager_instance


def reset_config_manager():
    """Reset the singleton instance (for testing)"""
    global _config_manager_instance
    with _config_lock:
        if _config_manager_instance:
            _config_manager_instance._stop_file_observer()
        _config_manager_instance = None


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing

    # Create config manager
    config = ConfigManager(environment="development")

    # Test basic operations
    config.set("broker.host", "localhost")

    # Test validation
    errors = config.validate()
    if errors:
        pass
    else:
        pass

    # Test sensitive data
    config.set("broker.api_key", "secret123")

    # Test export
    export_path = Path("test_config_export.yaml")
    if config.export_config(export_path):
        pass

    # Print configuration
    config.print_config()

    # Test change history
    for _change in config.get_change_history(limit=5):
        pass

