#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC17_MarketConfigManager.py
Group: C (Market Data)
Purpose: Centralized configuration management for market data systems

Description:
    This module provides a comprehensive configuration management system for all
    market data components. It supports dynamic configuration updates, environment-
    specific settings, validation, versioning, and hot-reloading of configurations
    without system restart. The module ensures all market data components operate
    with consistent and validated settings.:

Author: Assistant
Date Created: 2025-01-23
Last Updated: 2025-01-23
"""

import copy
import hashlib
import json
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import yaml

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import toml

    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False

from jsonschema import Draft7Validator, ValidationError, validate

from SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Configuration paths
DEFAULT_CONFIG_DIR = "config"
CONFIG_FILE_PATTERNS = {"json": "*.json", "yaml": ["*.yaml", "*.yml"], "toml": "*.toml"}

# Environment settings
ENVIRONMENTS = ["development", "testing", "production"]
DEFAULT_ENVIRONMENT = "development"

# Configuration categories
CONFIG_CATEGORIES = {
    "symbols": "Market symbols and groupings",
    "market_data": "Market data hub settings",
    "cache": "Cache configuration",
    "connections": "Broker connections",
    "strategies": "Strategy parameters",
    "risk": "Risk management settings",
    "monitoring": "System monitoring",
    "custom_metrics": "Custom metric calculators",
}

# Default configurations
DEFAULT_SYMBOL_CONFIG = {
    "visible_symbols": {
        "S&P_CORE": {
            "symbols": ["SPY", "SPX", "/ES"],
            "update_frequency": 1,
            "priority": "CRITICAL",
        },
        "VOLATILITY": {
            "symbols": ["VIX", "VIX9D", "VXV", "VXMT", "VVIX", "UVXY"],
            "update_frequency": 5,
            "priority": "HIGH",
        },
        "MARKET_INTERNALS": {
            "symbols": ["TICK-NYSE", "TRIN-NYSE", "ADD-NYSE", "CPC", "PCALL", "SKEW"],
            "update_frequency": 5,
            "priority": "HIGH",
        },
        "MAJOR_INDICES": {
            "symbols": ["DIA", "QQQ", "IWM"],
            "update_frequency": 5,
            "priority": "MEDIUM",
        },
        "BONDS_CREDIT": {"symbols": ["TLT", "LQD"], "update_frequency": 15, "priority": "LOW"},
        "CORRELATIONS": {"symbols": ["DXY", "GLD"], "update_frequency": 15, "priority": "LOW"},
    },
    "hidden_symbols": {
        "VIX_FUTURES": {"symbols": ["VX"], "update_frequency": 5, "priority": "MEDIUM"},
        "ADDITIONAL_INTERNALS": {
            "symbols": [
                "ADVN-NYSE",
                "DECN-NYSE",
                "UVOL-NYSE",
                "DVOL-NYSE",
                "VOLD-NYSE",
                "NYHL-NYSE",
            ],
            "update_frequency": 5,
            "priority": "MEDIUM",
        },
        "SECTOR_ETFS": {
            "symbols": [
                "XLF",
                "XLK",
                "XLE",
                "XLV",
                "XLI",
                "XLY",
                "XLP",
                "XLU",
                "XLRE",
                "XLC",
                "XLB",
            ],
            "update_frequency": 30,
            "priority": "LOW",
        },
    },
    "custom_metrics": {
        "GEX": {"update_frequency": 60, "priority": "HIGH"},
        "DEX": {"update_frequency": 60, "priority": "HIGH"},
        "OGL": {"update_frequency": 60, "priority": "HIGH"},
        "DIX": {"update_frequency": 300, "priority": "MEDIUM"},
        "SWAN": {"update_frequency": 60, "priority": "CRITICAL"},
    },
}

DEFAULT_MARKET_DATA_CONFIG = {
    "hub": {
        "max_concurrent_subscriptions": 100,
        "snapshot_request_limit": 1,
        "connection_timeout": 30,
        "heartbeat_interval": 30,
        "reconnect_attempts": 5,
        "reconnect_delay_base": 5,
    },
    "cache": {
        "memory_max_size": 10000,
        "memory_ttl_seconds": 5,
        "redis_enabled": False,
        "redis_host": "localhost",
        "redis_port": 6379,
        "persistence_enabled": True,
        "retention_days": 30,
    },
    "validation": {
        "enabled": True,
        "price_change_threshold": 0.20,  # 20% max change
        "volume_outlier_threshold": 10,  # 10x average
        "stale_data_seconds": 30,
    },
}

# Configuration schemas for validation
SYMBOL_SCHEMA = {
    "type": "object",
    "properties": {
        "symbols": {"type": "array", "items": {"type": "string"}},
        "update_frequency": {"type": "number", "minimum": 1},
        "priority": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
    },
    "required": ["symbols", "update_frequency", "priority"],
}

# ==============================================================================
# ENUMS
# ==============================================================================


class ConfigFormat(Enum):
    """Configuration file formats"""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


class ConfigChangeType(Enum):
    """Types of configuration changes"""

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    RELOAD = "reload"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ConfigVersion:
    """Configuration version tracking"""

    version: str
    timestamp: datetime
    checksum: str
    changes: List[str] = field(default_factory=list)
    author: str = "system"


@dataclass
class ConfigChange:
    """Represents a configuration change"""

    category: str
    key: str
    old_value: Any
    new_value: Any
    change_type: ConfigChangeType
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ValidationResult:
    """Configuration validation result"""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class MarketConfigManager:
    """
    Centralized configuration management for market data systems.

    Features:
    - Multi-format support (JSON, YAML, TOML)
    - Environment-specific configurations
    - Dynamic hot-reloading
    - Change tracking and versioning
    - Validation with schemas
    - Event-driven updates
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        environment: Optional[str] = None,
        event_manager: Optional[EventManager] = None,
    ):
        """Initialize configuration manager"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager

        # Configuration settings
        self.config_dir = Path(config_dir or DEFAULT_CONFIG_DIR)
        self.environment = environment or os.getenv("SPYDER_ENV", DEFAULT_ENVIRONMENT)

        # Storage
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.defaults: Dict[str, Dict[str, Any]] = {}
        self.overrides: Dict[str, Dict[str, Any]] = {}

        # Versioning
        self.versions: Dict[str, List[ConfigVersion]] = defaultdict(list)
        self.current_version = self._generate_version()

        # Change tracking
        self.change_history: List[ConfigChange] = []
        self.change_callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # File watching
        self.file_watchers: Dict[str, float] = {}  # file -> last_modified
        self.watch_thread: Optional[threading.Thread] = None
        self.watching = False

        # Thread safety
        self._lock = threading.RLock()

        # Initialize
        self._initialize_defaults()
        self._load_schemas()
        self.logger.info(f"MarketConfigManager initialized for environment: {self.environment}")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize_defaults(self):
        """Initialize default configurations"""
        self.defaults["symbols"] = DEFAULT_SYMBOL_CONFIG
        self.defaults["market_data"] = DEFAULT_MARKET_DATA_CONFIG

        # Load additional defaults
        self.defaults["connections"] = {
            "ibkr": {
                "host": "127.0.0.1",
                "port": 7497,  # Paper trading
                "client_id": 1,
                "timeout": 30,
            }
        }

        self.defaults["risk"] = {
            "max_positions": 10,
            "max_position_size": 100000,
            "max_daily_loss": 5000,
            "max_delta_exposure": 1000,
            "max_gamma_exposure": 100,
        }

    def _load_schemas(self):
        """Load validation schemas"""
        self.schemas["symbols"] = {
            "type": "object",
            "properties": {
                "visible_symbols": {"type": "object", "additionalProperties": SYMBOL_SCHEMA},
                "hidden_symbols": {"type": "object", "additionalProperties": SYMBOL_SCHEMA},
                "custom_metrics": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "update_frequency": {"type": "number"},
                            "priority": {"type": "string"},
                        },
                    },
                },
            },
        }

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def start(self):
        """Start the configuration manager"""
        try:
            # Create config directory if needed
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Load all configurations
            self.load_all_configs()

            # Start file watching
            if not self.watching:
                self.watching = True
                self.watch_thread = threading.Thread(target=self._watch_files, daemon=True)
                self.watch_thread.start()

            self.logger.info("Configuration manager started")

        except Exception as e:
            self.logger.error(f"Failed to start config manager: {e}")
            raise

    def stop(self):
        """Stop the configuration manager"""
        self.watching = False
        if self.watch_thread:
            self.watch_thread.join(timeout=5)

        self.logger.info("Configuration manager stopped")

    def get(self, category: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            category: Configuration category
            key: Specific key within category (dot notation supported)
            default: Default value if not found

        Returns:
            Configuration value
        """
        with self._lock:
            # Check overrides first
            if category in self.overrides:
                if key:
                    value = self._get_nested(self.overrides[category], key)
                    if value is not None:
                        return value
                else:
                    return self.overrides[category]

            # Check loaded configs
            if category in self.configs:
                if key:
                    value = self._get_nested(self.configs[category], key)
                    if value is not None:
                        return value
                else:
                    return self.configs[category]

            # Check defaults
            if category in self.defaults:
                if key:
                    return self._get_nested(self.defaults[category], key, default)
                else:
                    return self.defaults[category]

            return default

    def set(self, category: str, key: str, value: Any, persist: bool = False) -> bool:
        """
        Set configuration value.

        Args:
            category: Configuration category
            key: Key to set (dot notation supported)
            value: Value to set
            persist: Whether to persist to file

        Returns:
            Success status
        """
        try:
            with self._lock:
                # Get old value for change tracking
                old_value = self.get(category, key)

                # Ensure category exists
                if category not in self.configs:
                    self.configs[category] = {}

                # Set value
                self._set_nested(self.configs[category], key, value)

                # Track change
                change = ConfigChange(
                    category=category,
                    key=key,
                    old_value=old_value,
                    new_value=value,
                    change_type=ConfigChangeType.UPDATE if old_value else ConfigChangeType.ADD,
                )
                self._track_change(change)

                # Persist if requested
                if persist:
                    self._save_config(category)

                # Notify callbacks
                self._notify_change(category, key, old_value, value)

                return True

        except Exception as e:
            self.logger.error(f"Failed to set config {category}.{key}: {e}")
            return False

    def override(self, category: str, key: str, value: Any) -> bool:
        """
        Set a temporary override (not persisted).

        Args:
            category: Configuration category
            key: Key to override
            value: Override value

        Returns:
            Success status
        """
        try:
            with self._lock:
                if category not in self.overrides:
                    self.overrides[category] = {}

                self._set_nested(self.overrides[category], key, value)

                # Notify without persisting
                old_value = self.get(category, key)
                self._notify_change(category, key, old_value, value)

                return True

        except Exception as e:
            self.logger.error(f"Failed to override {category}.{key}: {e}")
            return False

    def clear_overrides(self, category: Optional[str] = None):
        """Clear configuration overrides"""
        with self._lock:
            if category:
                if category in self.overrides:
                    del self.overrides[category]
            else:
                self.overrides.clear()

    def load_all_configs(self):
        """Load all configuration files"""
        try:
            # Load base configurations
            for category in CONFIG_CATEGORIES:
                self._load_category(category)

            # Load environment-specific configs
            self._load_environment_configs()

            # Validate all configs
            validation = self.validate_all()
            if not validation.is_valid:
                self.logger.warning(f"Configuration validation errors: {validation.errors}")

            self.logger.info(f"Loaded {len(self.configs)} configuration categories")

        except Exception as e:
            self.logger.error(f"Failed to load configurations: {e}")
            raise

    def reload_config(self, category: str) -> bool:
        """
        Reload a specific configuration category.

        Args:
            category: Category to reload

        Returns:
            Success status
        """
        try:
            old_config = self.configs.get(category, {}).copy()

            # Reload
            self._load_category(category)

            # Track reload
            change = ConfigChange(
                category=category,
                key="*",
                old_value=old_config,
                new_value=self.configs.get(category, {}),
                change_type=ConfigChangeType.RELOAD,
            )
            self._track_change(change)

            # Notify
            self._notify_reload(category)

            return True

        except Exception as e:
            self.logger.error(f"Failed to reload {category}: {e}")
            return False

    def validate(self, category: str, config: Optional[Dict] = None) -> ValidationResult:
        """
        Validate configuration against schema.

        Args:
            category: Configuration category
            config: Config to validate (uses loaded if None)

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        # Get config to validate
        if config is None:
            config = self.configs.get(category, {})

        # Check if schema exists
        if category not in self.schemas:
            result.warnings.append(f"No schema defined for {category}")
            return result

        try:
            # Validate against schema
            validate(config, self.schemas[category])

        except ValidationError as e:
            result.is_valid = False
            result.errors.append(str(e))

        # Custom validation
        custom_result = self._custom_validate(category, config)
        if not custom_result.is_valid:
            result.is_valid = False
            result.errors.extend(custom_result.errors)
            result.warnings.extend(custom_result.warnings)

        return result

    def validate_all(self) -> ValidationResult:
        """Validate all loaded configurations"""
        result = ValidationResult(is_valid=True)

        for category in self.configs:
            cat_result = self.validate(category)
            if not cat_result.is_valid:
                result.is_valid = False
                result.errors.extend([f"{category}: {e}" for e in cat_result.errors])
                result.warnings.extend([f"{category}: {w}" for w in cat_result.warnings])

        return result

    def register_callback(self, category: str, callback: Callable[[str, Any, Any], None]):
        """
        Register callback for configuration changes.

        Args:
            category: Category to monitor (* for all)
            callback: Function(key, old_value, new_value)
        """
        self.change_callbacks[category].append(callback)

    def get_all_symbols(self) -> Dict[str, List[str]]:
        """Get all configured symbols organized by category"""
        symbols = {}

        # Visible symbols
        visible = self.get("symbols", "visible_symbols", {})
        for group, config in visible.items():
            symbols[f"visible_{group}"] = config.get("symbols", [])

        # Hidden symbols
        hidden = self.get("symbols", "hidden_symbols", {})
        for group, config in hidden.items():
            symbols[f"hidden_{group}"] = config.get("symbols", [])

        # Custom metrics
        custom = self.get("symbols", "custom_metrics", {})
        symbols["custom_metrics"] = list(custom.keys())

        return symbols

    def get_symbol_config(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific symbol"""
        # Check visible symbols
        visible = self.get("symbols", "visible_symbols", {})
        for group, config in visible.items():
            if symbol in config.get("symbols", []):
                return {
                    "group": group,
                    "type": "visible",
                    "update_frequency": config.get("update_frequency"),
                    "priority": config.get("priority"),
                }

        # Check hidden symbols
        hidden = self.get("symbols", "hidden_symbols", {})
        for group, config in hidden.items():
            if symbol in config.get("symbols", []):
                return {
                    "group": group,
                    "type": "hidden",
                    "update_frequency": config.get("update_frequency"),
                    "priority": config.get("priority"),
                }

        # Check custom metrics
        custom = self.get("symbols", "custom_metrics", {})
        if symbol in custom:
            return {
                "group": "custom",
                "type": "custom",
                "update_frequency": custom[symbol].get("update_frequency"),
                "priority": custom[symbol].get("priority"),
            }

        return None

    def export_config(self, category: str, format: ConfigFormat = ConfigFormat.JSON) -> str:
        """Export configuration to string"""
        config = self.get(category)
        if not config:
            return ""

        if format == ConfigFormat.JSON:
            return json.dumps(config, indent=2, default=str)
        elif format == ConfigFormat.YAML:
            return yaml.dump(config, default_flow_style=False)
        elif format == ConfigFormat.TOML and TOML_AVAILABLE:
            return toml.dumps(config)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_version_history(self, category: str) -> List[ConfigVersion]:
        """Get version history for a category"""
        return self.versions.get(category, [])

    def get_change_history(
        self, category: Optional[str] = None, limit: int = 100
    ) -> List[ConfigChange]:
        """Get configuration change history"""
        if category:
            changes = [c for c in self.change_history if c.category == category]
        else:
            changes = self.change_history

        return changes[-limit:]

    # ==========================================================================
    # FILE OPERATIONS
    # ==========================================================================
    def _load_category(self, category: str):
        """Load configuration for a category"""
        # Try different file formats
        for format in ConfigFormat:
            file_path = self._get_config_path(category, format)
            if file_path.exists():
                config = self._load_file(file_path, format)
                if config:
                    self.configs[category] = config
                    self._track_file(file_path)
                    self.logger.debug(f"Loaded {category} from {file_path}")
                    return

        # Use defaults if no file found
        if category in self.defaults:
            self.configs[category] = copy.deepcopy(self.defaults[category])
            self.logger.debug(f"Using defaults for {category}")

    def _load_environment_configs(self):
        """Load environment-specific configurations"""
        env_dir = self.config_dir / self.environment
        if not env_dir.exists():
            return

        for format in ConfigFormat:
            pattern = CONFIG_FILE_PATTERNS.get(format.value, f"*.{format.value}")
            if isinstance(pattern, list):
                patterns = pattern
            else:
                patterns = [pattern]

            for pattern in patterns:
                for file_path in env_dir.glob(pattern):
                    category = file_path.stem
                    config = self._load_file(file_path, format)
                    if config:
                        # Merge with base config
                        if category in self.configs:
                            self.configs[category] = self._deep_merge(
                                self.configs[category], config
                            )
                        else:
                            self.configs[category] = config

                        self._track_file(file_path)
                        self.logger.debug(f"Loaded env override for {category}")

    def _load_file(self, file_path: Path, format: ConfigFormat) -> Optional[Dict]:
        """Load configuration from file"""
        try:
            with open(file_path, "r") as f:
                if format == ConfigFormat.JSON:
                    return json.load(f)
                elif format == ConfigFormat.YAML:
                    return yaml.safe_load(f)
                elif format == ConfigFormat.TOML and TOML_AVAILABLE:
                    return toml.load(f)

        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {e}")

        return None

    def _save_config(self, category: str):
        """Save configuration to file"""
        if category not in self.configs:
            return

        # Determine format from existing file or default to JSON
        format = ConfigFormat.JSON
        for fmt in ConfigFormat:
            if self._get_config_path(category, fmt).exists():
                format = fmt
                break

        file_path = self._get_config_path(category, format)

        try:
            # Create backup
            if file_path.exists():
                backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
                file_path.rename(backup_path)

            # Save new config
            with open(file_path, "w") as f:
                if format == ConfigFormat.JSON:
                    json.dump(self.configs[category], f, indent=2, default=str)
                elif format == ConfigFormat.YAML:
                    yaml.dump(self.configs[category], f, default_flow_style=False)
                elif format == ConfigFormat.TOML and TOML_AVAILABLE:
                    toml.dump(self.configs[category], f)

            # Update version
            self._create_version(category)

            self.logger.info(f"Saved {category} configuration to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to save {category}: {e}")
            # Restore backup if exists
            backup_path = file_path.with_suffix(f"{file_path.suffix}.bak")
            if backup_path.exists():
                backup_path.rename(file_path)

    def _get_config_path(self, category: str, format: ConfigFormat) -> Path:
        """Get configuration file path"""
        return self.config_dir / f"{category}.{format.value}"

    # ==========================================================================
    # FILE WATCHING
    # ==========================================================================
    def _track_file(self, file_path: Path):
        """Track file for changes"""
        self.file_watchers[str(file_path)] = file_path.stat().st_mtime

    def _watch_files(self):
        """Watch configuration files for changes"""
        while self.watching:
            try:
                for file_path, last_modified in list(self.file_watchers.items()):
                    path = Path(file_path)
                    if path.exists():
                        current_modified = path.stat().st_mtime
                        if current_modified > last_modified:
                            self.file_watchers[file_path] = current_modified

                            # Determine category from filename
                            category = path.stem

                            # Check if it's an environment override
                            if self.environment in path.parts:
                                self.logger.info(
                                    f"Detected change in environment config: {category}"
                                )
                            else:
                                self.logger.info(f"Detected change in config file: {category}")

                            # Reload configuration
                            self.reload_config(category)

            except Exception as e:
                self.logger.error(f"Error in file watcher: {e}")

            time.sleep(1)  # Check every second

    # ==========================================================================
    # CHANGE TRACKING
    # ==========================================================================
    def _track_change(self, change: ConfigChange):
        """Track a configuration change"""
        self.change_history.append(change)

        # Limit history size
        if len(self.change_history) > 1000:
            self.change_history = self.change_history[-500:]

        # Publish event if event manager available
        if self.event_manager:
            event = Event(
                EventType.CONFIG_CHANGE,
                {
                    "category": change.category,
                    "key": change.key,
                    "old_value": change.old_value,
                    "new_value": change.new_value,
                    "change_type": change.change_type.value,
                },
            )
            self.event_manager.publish(event)

    def _notify_change(self, category: str, key: str, old_value: Any, new_value: Any):
        """Notify registered callbacks of change"""
        # Category-specific callbacks
        for callback in self.change_callbacks.get(category, []):
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                self.logger.error(f"Error in change callback: {e}")

        # Global callbacks
        for callback in self.change_callbacks.get("*", []):
            try:
                callback(f"{category}.{key}", old_value, new_value)
            except Exception as e:
                self.logger.error(f"Error in global callback: {e}")

    def _notify_reload(self, category: str):
        """Notify callbacks of configuration reload"""
        self._notify_change(category, "*", None, self.configs.get(category))

    # ==========================================================================
    # VERSIONING
    # ==========================================================================
    def _generate_version(self) -> str:
        """Generate version string"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _create_version(self, category: str):
        """Create new version entry"""
        config_str = json.dumps(self.configs.get(category, {}), sort_keys=True)
        checksum = hashlib.md5(config_str.encode()).hexdigest()

        version = ConfigVersion(
            version=self._generate_version(),
            timestamp=datetime.now(),
            checksum=checksum,
            changes=[f"Updated {category} configuration"],
        )

        self.versions[category].append(version)

        # Limit version history
        if len(self.versions[category]) > 50:
            self.versions[category] = self.versions[category][-25:]

    # ==========================================================================
    # VALIDATION
    # ==========================================================================
    def _custom_validate(self, category: str, config: Dict) -> ValidationResult:
        """Perform custom validation for specific categories"""
        result = ValidationResult(is_valid=True)

        if category == "symbols":
            # Validate symbol formats
            all_symbols = []
            for group_type in ["visible_symbols", "hidden_symbols"]:
                if group_type in config:
                    for group, group_config in config[group_type].items():
                        symbols = group_config.get("symbols", [])
                        all_symbols.extend(symbols)

                        # Check for valid symbol format
                        for symbol in symbols:
                            if not self._is_valid_symbol(symbol):
                                result.errors.append(f"Invalid symbol format: {symbol}")

            # Check for duplicates
            duplicates = [s for s in all_symbols if all_symbols.count(s) > 1]
            if duplicates:
                result.warnings.append(f"Duplicate symbols: {set(duplicates)}")

        elif category == "risk":
            # Validate risk limits
            if "max_daily_loss" in config and "max_position_size" in config:
                if config["max_daily_loss"] < config["max_position_size"] * 0.05:
                    result.warnings.append(
                        "Max daily loss may be too low relative to position size"
                    )

        return result

    def _is_valid_symbol(self, symbol: str) -> bool:
        """Check if symbol format is valid"""
        # Basic validation - can be enhanced
        if not symbol:
            return False

        # Special handling for futures
        if symbol.startswith("/"):
            return len(symbol) >= 2

        # Special handling for indices/internals
        if "-" in symbol:
            return all(part.isalnum() for part in symbol.split("-"))

        # Standard symbols
        return symbol.replace("$", "").isalnum()

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _get_nested(self, data: Dict, key: str, default: Any = None) -> Any:
        """Get nested value using dot notation"""
        keys = key.split(".")
        value = data

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def _set_nested(self, data: Dict, key: str, value: Any):
        """Set nested value using dot notation"""
        keys = key.split(".")
        current = data

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the configuration manager

    # Initialize
    config_manager = MarketConfigManager(config_dir="config", environment="development")

    # Start manager
    config_manager.start()

    print("📋 Configuration Manager Test")
    print("=" * 50)

    # Get all symbols
    print("\n📊 All Configured Symbols:")
    symbols = config_manager.get_all_symbols()
    for category, symbol_list in symbols.items():
        print(f"\n{category}:")
        print(f"  {symbol_list}")

    # Get specific configuration
    print("\n⚙️  Market Data Hub Config:")
    hub_config = config_manager.get("market_data", "hub")
    print(json.dumps(hub_config, indent=2))

    # Test symbol lookup
    print("\n🔍 Symbol Configuration Lookup:")
    test_symbols = ["SPY", "VIX", "GEX", "XLF"]
    for symbol in test_symbols:
        config = config_manager.get_symbol_config(symbol)
        print(f"{symbol}: {config}")

    # Test configuration update
    print("\n✏️  Testing Configuration Update:")
    old_value = config_manager.get("risk", "max_positions")
    print(f"Old max_positions: {old_value}")

    config_manager.set("risk", "max_positions", 15)
    new_value = config_manager.get("risk", "max_positions")
    print(f"New max_positions: {new_value}")

    # Test validation
    print("\n✅ Configuration Validation:")
    validation = config_manager.validate_all()
    print(f"Valid: {validation.is_valid}")
    if validation.errors:
        print(f"Errors: {validation.errors}")
    if validation.warnings:
        print(f"Warnings: {validation.warnings}")

    # Test change history
    print("\n📜 Recent Changes:")
    changes = config_manager.get_change_history(limit=5)
    for change in changes:
        print(
            f"  {change.timestamp}: {change.category}.{change.key} " f"({change.change_type.value})"
        )

    # Test export
    print("\n📤 Export Configuration:")
    symbols_json = config_manager.export_config("symbols", ConfigFormat.JSON)
    print(f"Symbols config (first 200 chars):\n{symbols_json[:200]}...")

    # Test callback
    def on_config_change(key: str, old_value: Any, new_value: Any):
        print(f"\n🔔 Config changed: {key}")
        print(f"   Old: {old_value}")
        print(f"   New: {new_value}")

    config_manager.register_callback("risk", on_config_change)

    # Trigger a change
    config_manager.set("risk", "max_daily_loss", 6000)

    # Stop manager
    config_manager.stop()
    print("\n✅ Configuration Manager test completed")
