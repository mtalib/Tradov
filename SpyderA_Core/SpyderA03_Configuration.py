#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderA03_Configuration.py
Group: A (Core Trading Engine)
Purpose: Complete configuration management system

Description:
    This module provides comprehensive configuration management for the Spyder
    trading system. It handles loading configurations from multiple sources
    (files, environment variables, defaults), validates configuration values,
    manages sensitive data encryption, supports hot-reloading, and provides
    configuration versioning and audit trails.

Spyder Version: 2.0
Author: Mohamed Talib
Created: 2025-01-27
Last Updated: 2025-07-06 - Production Ready
"""

import configparser
import copy
import hashlib
import json
import logging
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re
import sys
import threading
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import toml
import yaml

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import base64

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("Warning: cryptography not installed - sensitive data will not be encrypted")

import watchdog
from jsonschema import Draft7Validator, ValidationError, validate
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_DIR = Path.home() / ".spyder" / "config"
DEFAULT_CONFIG_FILE = "config.yaml"
DEFAULT_ENV_PREFIX = "SPYDER_"
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


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ConfigValue:
    """Configuration value with metadata"""

    key: str
    value: Any
    source: ConfigSource
    timestamp: datetime = field(default_factory=datetime.now)
    encrypted: bool = False
    schema_validated: bool = False
    description: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None


@dataclass
class ConfigChange:
    """Configuration change record"""

    timestamp: datetime
    key: str
    old_value: Any
    new_value: Any
    source: str
    user: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class ConfigSchema:
    """Configuration schema definition"""

    version: str
    properties: Dict[str, Any]
    required: List[str]
    additional_properties: bool = False
    definitions: Optional[Dict[str, Any]] = None


# ==============================================================================
# CONFIGURATION FILE HANDLER
# ==============================================================================


class ConfigFileHandler(FileSystemEventHandler):
    """Handle configuration file changes"""

    def __init__(self, config_manager: "ConfigManager"):
        self.config_manager = config_manager
        self.logger = SpyderLogger.get_logger(__name__)

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).suffix in SUPPORTED_FORMATS:
            self.logger.info(f"Configuration file modified: {event.src_path}")
            self.config_manager._on_config_file_changed(Path(event.src_path))


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class ConfigManager:
    """
    Comprehensive configuration management system for Spyder.

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
        config_path: Optional[Path] = None,
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
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration paths
        self.config_path = config_path or DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
        self.config_dir = (
            self.config_path.parent if self.config_path.is_file() else self.config_path
        )
        self.environment = environment

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Configuration data structures
        self.config_data: Dict[str, Any] = {}
        self.config_sources: Dict[str, ConfigValue] = {}
        self.change_history: List[ConfigChange] = []
        self.schemas: Dict[str, ConfigSchema] = {}
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Thread safety
        self._lock = threading.RLock()

        # Encryption setup
        self.encryption_key = None
        self._init_encryption()

        # File watching
        self.auto_reload = auto_reload
        self.file_observer = None
        self.watched_files: Set[Path] = set()

        # Load initial configuration
        self._load_all_configurations()

        # Start file observer if enabled
        if self.auto_reload:
            self._start_file_observer()

        self.logger.info(f"ConfigManager initialized for environment: {environment}")

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

            self.logger.info("Encryption initialized")

        except Exception as e:
            self.logger.error(f"Encryption initialization failed: {e}")

    def _load_all_configurations(self):
        """Load configurations from all sources"""
        try:
            # 1. Load default configuration
            self._load_defaults()

            # 2. Load configuration files
            self._load_config_files()

            # 3. Load environment variables
            self._load_environment_variables()

            # 4. Validate merged configuration
            self._validate_configuration()

            # 5. Create initial backup
            self._backup_configuration()

            self.logger.info("All configurations loaded successfully")

        except Exception as e:
            self.logger.error(f"Configuration loading failed: {e}")
            self.error_handler.handle_error(e, "load_all_configurations")
            # Use defaults on error
            self._load_defaults()

    def _load_defaults(self):
        """Load default configuration values"""
        defaults = {
            "application": {
                "name": "Spyder Trading System",
                "version": "2.0.0",
                "environment": self.environment,
                "debug": self.environment == "development",
                "timezone": "US/Eastern",
            },
            "logging": {
                "level": "INFO" if self.environment == "production" else "DEBUG",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": str(self.config_dir / "logs" / "spyder.log"),
                "max_size": "10MB",
                "backup_count": 5,
            },
            "database": {
                "type": "sqlite",
                "path": str(self.config_dir / "spyder.db"),
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
                "symbols": ["SPY"],
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
            "api": {
                "enabled": False,
                "host": "0.0.0.0",
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
            self.logger.info(f"Loading configuration from: {file_path}")

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
                self.logger.warning(f"Unsupported configuration format: {suffix}")
                return

            if config_data:
                self._merge_config(config_data, ConfigSource.FILE)

        except Exception as e:
            self.logger.error(f"Failed to load config file {file_path}: {e}")
            self.error_handler.handle_error(e, f"load_config_file:{file_path}")

    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML configuration file"""
        with open(file_path, "r") as f:
            return yaml.safe_load(f) or {}

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file"""
        with open(file_path, "r") as f:
            return json.load(f)

    def _load_toml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load TOML configuration file"""
        with open(file_path, "r") as f:
            return toml.load(f)

    def _load_ini_file(self, file_path: Path) -> Dict[str, Any]:
        """Load INI configuration file"""
        config = configparser.ConfigParser()
        config.read(file_path)

        # Convert to nested dictionary
        result = {}
        for section in config.sections():
            result[section] = dict(config.items(section))

        return result

    def _load_env_file(self, file_path: Path) -> Dict[str, Any]:
        """Load .env configuration file"""
        result = {}

        with open(file_path, "r") as f:
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
                # e.g., SPYDER_BROKER_HOST -> broker.host
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

    def _set_nested_value(self, d: Dict[str, Any], key: str, value: Any):
        """Set value in nested dictionary using dot notation"""
        keys = key.split(".")
        current = d

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _merge_config(self, new_config: Dict[str, Any], source: ConfigSource):
        """Merge new configuration with existing"""
        with self._lock:
            # Deep merge configurations
            self._deep_merge(self.config_data, new_config)

            # Track sources
            self._track_config_sources(new_config, source)

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]):
        """Deep merge two dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def _track_config_sources(self, config: Dict[str, Any], source: ConfigSource, prefix: str = ""):
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
            self.logger.error(f"Encryption failed: {e}")
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
            self.logger.error(f"Decryption failed: {e}")
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
                self.logger.error(f"Error getting config value {key}: {e}")
                return default

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values (with sensitive data masked)"""
        with self._lock:
            # Deep copy configuration
            config_copy = copy.deepcopy(self.config_data)

            # Mask sensitive values
            self._mask_sensitive_values(config_copy)

            return config_copy

    def _mask_sensitive_values(self, config: Dict[str, Any], prefix: str = ""):
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
                    timestamp=datetime.now(),
                    key=key,
                    old_value=old_value if not is_sensitive else "***MASKED***",
                    new_value=value if not is_sensitive else "***MASKED***",
                    source=source,
                )
                self.change_history.append(change)

                # Notify callbacks
                self._notify_callbacks(key, old_value, value)

                self.logger.info(f"Configuration updated: {key}")
                return True

            except Exception as e:
                self.logger.error(f"Error setting config value {key}: {e}")
                return False

    def update(self, updates: Dict[str, Any], source: str = "runtime") -> bool:
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
                        timestamp=datetime.now(),
                        key=key,
                        old_value=old_value,
                        new_value=None,
                        source="runtime",
                    )
                    self.change_history.append(change)

                    return True

                return False

            except Exception as e:
                self.logger.error(f"Error deleting config value {key}: {e}")
                return False

    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    def load_schema(self, schema_path: Path):
        """Load configuration schema from file"""
        try:
            with open(schema_path, "r") as f:
                schema_data = json.load(f)

            schema = ConfigSchema(
                version=schema_data.get("version", "1.0"),
                properties=schema_data.get("properties", {}),
                required=schema_data.get("required", []),
                additional_properties=schema_data.get("additionalProperties", False),
                definitions=schema_data.get("definitions"),
            )

            self.schemas[schema_path.stem] = schema
            self.logger.info(f"Loaded configuration schema: {schema_path.stem}")

        except Exception as e:
            self.logger.error(f"Failed to load schema {schema_path}: {e}")

    def validate(self, schema_name: Optional[str] = None) -> List[str]:
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

    def _validate_basic(self) -> List[str]:
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

    def _validate_against_schema(self, schema_name: str) -> List[str]:
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
        errors = self.validate()

        if errors:
            self.logger.warning(f"Configuration validation found {len(errors)} issues:")
            for error in errors:
                self.logger.warning(f"  - {error}")
        else:
            self.logger.info("Configuration validation passed")

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
            self.logger.info("Configuration file monitoring started")

        except Exception as e:
            self.logger.error(f"Failed to start file observer: {e}")

    def _stop_file_observer(self):
        """Stop watching configuration files"""
        if self.file_observer and self.file_observer.is_alive():
            self.file_observer.stop()
            self.file_observer.join()

    def _on_config_file_changed(self, file_path: Path):
        """Handle configuration file change"""
        try:
            # Reload the specific file
            self.logger.info(f"Reloading configuration file: {file_path}")

            # Create backup before reloading
            self._backup_configuration()

            # Reload file
            self._load_config_file(file_path)

            # Revalidate
            self._validate_configuration()

            # Notify all callbacks
            self._notify_all_callbacks()

        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")

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
            self.logger.error(f"Configuration reload failed: {e}")
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
                        self.logger.error(f"Callback error: {e}")

    def _notify_all_callbacks(self):
        """Notify all callbacks (used for reload)"""
        for pattern, callbacks in self.callbacks.items():
            for callback in callbacks:
                try:
                    callback("*", None, None)  # Special reload notification
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")

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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"config_backup_{timestamp}.json"

            # Save configuration
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "environment": self.environment,
                "config": self.get_all(),  # This masks sensitive data
                "sources": {k: v.source.name for k, v in self.config_sources.items()},
            }

            with open(backup_file, "w") as f:
                json.dump(backup_data, f, indent=2, default=str)

            # Clean old backups
            self._clean_old_backups(backup_dir)

            self.logger.debug(f"Configuration backed up to: {backup_file}")

        except Exception as e:
            self.logger.error(f"Backup failed: {e}")

    def _clean_old_backups(self, backup_dir: Path):
        """Remove old backup files"""
        try:
            backups = sorted(backup_dir.glob("config_backup_*.json"))

            # Keep only the most recent backups
            while len(backups) > CONFIG_BACKUP_COUNT:
                oldest = backups.pop(0)
                oldest.unlink()

        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")

    def restore_backup(self, backup_file: Path) -> bool:
        """
        Restore configuration from backup.

        Args:
            backup_file: Path to backup file

        Returns:
            bool: True if successful
        """
        try:
            self.logger.info(f"Restoring configuration from: {backup_file}")

            with open(backup_file, "r") as f:
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
            self.logger.error(f"Restore failed: {e}")
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
            self.logger.error(f"Checksum calculation failed: {e}")
            return ""

    def get_change_history(self, limit: Optional[int] = None) -> List[ConfigChange]:
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
                self.logger.error(f"Unsupported export format: {format}")
                return False

            self.logger.info(f"Configuration exported to: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False

    def print_config(self, section: Optional[str] = None):
        """Print configuration to console (for debugging)"""
        config = self.get(section) if section else self.get_all()

        print(f"\n{'='*60}")
        print(f"Configuration ({self.environment})")
        print(f"{'='*60}")
        print(yaml.dump(config, default_flow_style=False))
        print(f"{'='*60}\n")

    def __del__(self):
        """Cleanup on deletion"""
        self._stop_file_observer()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_config_manager_instance: Optional[ConfigManager] = None
_config_lock = threading.Lock()


def get_config_manager(config_path: Optional[Path] = None) -> ConfigManager:
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
    print("Testing ConfigManager...")

    # Create config manager
    config = ConfigManager(environment="development")

    # Test basic operations
    print("\n1. Testing basic get/set:")
    print(f"Broker host: {config.get('broker.host')}")
    config.set("broker.host", "localhost")
    print(f"Updated broker host: {config.get('broker.host')}")

    # Test validation
    print("\n2. Testing validation:")
    errors = config.validate()
    if errors:
        print(f"Validation errors: {errors}")
    else:
        print("Validation passed")

    # Test sensitive data
    print("\n3. Testing sensitive data:")
    config.set("broker.api_key", "secret123")
    print(f"API key (should be encrypted): {config.config_sources.get('broker.api_key', {})}")

    # Test export
    print("\n4. Testing export:")
    export_path = Path("test_config_export.yaml")
    if config.export_config(export_path):
        print(f"Configuration exported to: {export_path}")

    # Print configuration
    print("\n5. Current configuration:")
    config.print_config()

    # Test change history
    print("\n6. Change history:")
    for change in config.get_change_history(limit=5):
        print(f"  - {change.timestamp}: {change.key} = {change.new_value}")

    print("\n✅ ConfigManager test completed")
