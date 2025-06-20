#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderA03_Configuration.py
Group: A (Core Trading Engine)
Purpose: Configuration management and settings

Description:
    This module manages all configuration settings for the Spyder trading system.
    It provides a centralized configuration management system with validation,
    hot-reloading, environment-specific settings, and secure credential handling.
    Configurations can be loaded from JSON, YAML, or environment variables.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import copy
import hashlib
import threading
import re
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, time
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import yaml
from cryptography.fernet import Fernet
from jsonschema import validate, ValidationError
import toml

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU04_Encryption import CredentialManager

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_DIR = Path.home() / ".spyder"
DEFAULT_CONFIG_FILE = "config.json"
CONFIG_SCHEMA_FILE = "config_schema.json"
SECRETS_FILE = "secrets.enc"

# Validation patterns
SYMBOL_PATTERN = re.compile(r"^[A-Z]{1,5}$")
TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
EMAIL_PATTERN = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


# ==============================================================================
# ENUMS
# ==============================================================================
class ConfigFormat(Enum):
    """Configuration file formats"""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


class Environment(Enum):
    """Deployment environments"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PAPER = "paper"
    PRODUCTION = "production"


class ConnectionType(Enum):
    """Broker connection types"""

    TWS_PAPER = "tws_paper"
    TWS_LIVE = "tws_live"
    GATEWAY_PAPER = "gateway_paper"
    GATEWAY_LIVE = "gateway_live"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class BrokerConfig:
    """Broker configuration"""

    host: str = "127.0.0.1"
    port: int = 7497  # TWS Paper Trading
    client_id: int = 1
    connection_type: ConnectionType = ConnectionType.TWS_PAPER
    account: str = ""
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: int = 5  # seconds

    def validate(self) -> None:
        """Validate broker configuration"""
        if not self.host:
            raise ValueError("Broker host cannot be empty")
        if self.port <= 0 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")
        if self.client_id < 0:
            raise ValueError(f"Invalid client ID: {self.client_id}")
        if self.max_reconnect_attempts < 0:
            raise ValueError(
                f"Invalid max reconnect attempts: {self.max_reconnect_attempts}"
            )


@dataclass
class MarketDataConfig:
    """Market data configuration"""

    symbols: List[str] = field(default_factory=lambda: ["SPY"])
    data_types: List[str] = field(
        default_factory=lambda: ["TRADES", "QUOTES", "BARS", "OPTIONS"]
    )
    bar_size: str = "1 min"
    historical_days: int = 5
    option_chain_strikes: int = 20
    option_chain_expiry_days: int = 45
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300

    def validate(self) -> None:
        """Validate market data configuration"""
        for symbol in self.symbols:
            if not SYMBOL_PATTERN.match(symbol):
                raise ValueError(f"Invalid symbol: {symbol}")
        if self.historical_days < 0:
            raise ValueError(f"Invalid historical days: {self.historical_days}")
        if self.option_chain_strikes < 0:
            raise ValueError(
                f"Invalid option chain strikes: {self.option_chain_strikes}"
            )


@dataclass
class RiskConfig:
    """Risk management configuration"""

    max_position_size: float = 10000.0
    max_daily_loss: float = 500.0
    max_positions: int = 5
    max_portfolio_heat: float = 0.06  # 6% of account
    position_size_method: str = "fixed"  # fixed, kelly, volatility_based
    stop_loss_percent: float = 0.02  # 2%
    take_profit_percent: float = 0.05  # 5%
    max_correlation: float = 0.7
    use_trailing_stop: bool = True
    trailing_stop_percent: float = 0.015  # 1.5%

    def validate(self) -> None:
        """Validate risk configuration"""
        if self.max_position_size <= 0:
            raise ValueError("Max position size must be positive")
        if self.max_daily_loss <= 0:
            raise ValueError("Max daily loss must be positive")
        if self.max_positions <= 0:
            raise ValueError("Max positions must be positive")
        if self.max_portfolio_heat <= 0 or self.max_portfolio_heat > 1:
            raise ValueError("Max portfolio heat must be between 0 and 1")


@dataclass
class StrategyConfig:
    """Strategy configuration"""

    enabled_strategies: List[str] = field(
        default_factory=lambda: ["iron_condor", "credit_spread"]
    )

    # Iron Condor settings
    iron_condor_enabled: bool = True
    iron_condor_delta: float = 0.15
    iron_condor_dte_min: int = 30
    iron_condor_dte_max: int = 45
    iron_condor_min_credit: float = 1.0
    iron_condor_profit_target: float = 0.5  # 50% of credit

    # Credit Spread settings
    credit_spread_enabled: bool = True
    credit_spread_delta: float = 0.20
    credit_spread_dte_min: int = 15
    credit_spread_dte_max: int = 45
    credit_spread_min_credit: float = 0.5

    # 0DTE settings
    zero_dte_enabled: bool = False
    zero_dte_start_time: str = "09:45"
    zero_dte_end_time: str = "15:30"
    zero_dte_max_contracts: int = 2

    def validate(self) -> None:
        """Validate strategy configuration"""
        if self.iron_condor_delta <= 0 or self.iron_condor_delta >= 1:
            raise ValueError(f"Invalid iron condor delta: {self.iron_condor_delta}")
        if self.credit_spread_delta <= 0 or self.credit_spread_delta >= 1:
            raise ValueError(f"Invalid credit spread delta: {self.credit_spread_delta}")
        if not TIME_PATTERN.match(self.zero_dte_start_time):
            raise ValueError(f"Invalid time format: {self.zero_dte_start_time}")
        if not TIME_PATTERN.match(self.zero_dte_end_time):
            raise ValueError(f"Invalid time format: {self.zero_dte_end_time}")


@dataclass
class TradingHoursConfig:
    """Trading hours configuration"""

    market_open: str = "09:30"
    market_close: str = "16:00"
    pre_market_start: str = "04:00"
    after_hours_end: str = "20:00"

    # Trading windows
    enable_pre_market: bool = False
    enable_after_hours: bool = False

    # Strategy-specific windows
    stop_new_trades_before_close: int = 30  # minutes
    close_all_positions_before_close: int = 15  # minutes

    # Days to trade
    trade_monday: bool = True
    trade_tuesday: bool = True
    trade_wednesday: bool = True
    trade_thursday: bool = True
    trade_friday: bool = True

    def validate(self) -> None:
        """Validate trading hours configuration"""
        times = [
            self.market_open,
            self.market_close,
            self.pre_market_start,
            self.after_hours_end,
        ]
        for t in times:
            if not TIME_PATTERN.match(t):
                raise ValueError(f"Invalid time format: {t}")


@dataclass
class NotificationConfig:
    """Notification configuration"""

    email_enabled: bool = True
    email_smtp_host: str = "smtp.gmail.com"
    email_smtp_port: int = 587
    email_from: str = ""
    email_to: List[str] = field(default_factory=list)

    sms_enabled: bool = False
    sms_provider: str = "twilio"
    sms_from: str = ""
    sms_to: List[str] = field(default_factory=list)

    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_chat_ids: List[str] = field(default_factory=list)

    # Alert levels
    alert_on_fill: bool = True
    alert_on_risk_limit: bool = True
    alert_on_daily_summary: bool = True
    alert_on_error: bool = True

    def validate(self) -> None:
        """Validate notification configuration"""
        if self.email_enabled:
            for email in self.email_to:
                if not EMAIL_PATTERN.match(email):
                    raise ValueError(f"Invalid email: {email}")


@dataclass
class DatabaseConfig:
    """Database configuration"""

    type: str = "sqlite"  # sqlite, postgresql
    host: str = "localhost"
    port: int = 5432
    name: str = "spyder"
    user: str = ""
    password: str = ""

    # SQLite specific
    sqlite_path: str = str(DEFAULT_CONFIG_DIR / "spyder.db")

    # Connection pool
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30

    def validate(self) -> None:
        """Validate database configuration"""
        if self.type not in ["sqlite", "postgresql"]:
            raise ValueError(f"Invalid database type: {self.type}")
        if self.type == "postgresql":
            if not self.host or not self.name:
                raise ValueError("PostgreSQL requires host and database name")


@dataclass
class PerformanceConfig:
    """Performance monitoring configuration"""

    enable_profiling: bool = False
    profile_interval: int = 300  # seconds

    enable_metrics: bool = True
    metrics_interval: int = 60  # seconds

    # Resource limits
    max_memory_mb: int = 2048
    max_cpu_percent: float = 80.0

    # Data retention
    trade_history_days: int = 365
    performance_history_days: int = 90
    log_retention_days: int = 30

    def validate(self) -> None:
        """Validate performance configuration"""
        if self.max_memory_mb <= 0:
            raise ValueError("Max memory must be positive")
        if self.max_cpu_percent <= 0 or self.max_cpu_percent > 100:
            raise ValueError("Max CPU percent must be between 0 and 100")


@dataclass
class TradingConfig:
    """Main trading configuration"""

    environment: Environment = Environment.PAPER
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategies: StrategyConfig = field(default_factory=StrategyConfig)
    trading_hours: TradingHoursConfig = field(default_factory=TradingHoursConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    # System settings
    log_level: str = "INFO"
    debug_mode: bool = False
    dry_run: bool = False

    def validate(self) -> None:
        """Validate all configuration sections"""
        self.broker.validate()
        self.market_data.validate()
        self.risk.validate()
        self.strategies.validate()
        self.trading_hours.validate()
        self.notifications.validate()
        self.database.validate()
        self.performance.validate()

    # ADD THESE METHODS for compatibility:
    def get(self, key: str, default=None):
        """Get configuration value by key with dot notation support."""
        try:
            # First try to get from the parent ConfigManager's raw config
            if hasattr(self, "_config_manager"):
                raw_config = getattr(self._config_manager, "_raw_config", {})
                keys = key.split(".")
                value = raw_config

                for k in keys:
                    if isinstance(value, dict) and k in value:
                        value = value[k]
                    else:
                        break
                else:
                    return value

            # Fallback to dataclass dict conversion
            keys = key.split(".")
            value = asdict(self)  # Convert dataclass to dict

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value
        except Exception:
            return default

    def get_all(self) -> dict:
        """
        Get all configuration values.
        
        Returns:
            dict: Complete configuration dictionary
        """
        with self._config_lock:
            return self._raw_config.copy() if hasattr(self, '_raw_config') else {}

    def get_config(self) -> dict:
        """Get configuration as dictionary."""
        return asdict(self)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


# ==============================================================================
# CONFIGURATION MANAGER CLASS
# ==============================================================================
class ConfigManager:
    """
    Centralized configuration management system.

    Features:
    - Multiple format support (JSON, YAML, TOML)
    - Environment-specific configurations
    - Hot-reloading with file watching
    - Secure credential management
    - Configuration validation
    - Default values and overrides
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to configuration file
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration paths
        self.config_dir = DEFAULT_CONFIG_DIR
        self.config_dir.mkdir(exist_ok=True)

        # Handle different config_path formats
        if config_path:
            if isinstance(config_path, str):
                self.config_path = Path(config_path)
            else:
                self.config_path = config_path
        else:
            self.config_path = self.config_dir / DEFAULT_CONFIG_FILE

        # Alias for compatibility
        self.config_file = self.config_path

        # Initialize configuration
        self.config = None
        self.credentials = None
        self._raw_config = {}  # ADD THIS
        self._config_lock = threading.Lock()  # ADD THIS
        self._watching = False  # ADD THIS
        self._watch_thread = None  # ADD THIS

        # Initialize credential manager
        try:
            self.credential_manager = CredentialManager()
        except Exception as e:
            self.logger.warning(f"Failed to initialize credential manager: {e}")
            self.credential_manager = None

        # Load configuration
        self.load_config()

        self.logger.info(f"ConfigManager initialized with {self.config_path}")

    # ==========================================================================
    # CONFIGURATION LOADING
    # ==========================================================================
    def load_config(self) -> None:
        """Load configuration with fallback to defaults."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_file}")
            else:
                self.logger.warning(f"Config file not found: {self.config_file}")
                config_data = self._create_default_config()

                # Create the config file with defaults
                self.config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.config_file, "w") as f:
                    json.dump(config_data, f, indent=4)
                self.logger.info(f"Created default config file: {self.config_file}")

            # Store raw config for compatibility
            self._raw_config = config_data

            # Convert JSON structure to TradingConfig structure
            trading_config_data = self._convert_json_to_dataclass_format(config_data)

            # Convert to TradingConfig object
            self.config = TradingConfig(**trading_config_data)

        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Use defaults if loading fails
            default_config_data = self._get_default_dataclass_config()
            self.config = TradingConfig(**default_config_data)
            self._raw_config = self._create_default_config()

    def _load_file(self, format_type: ConfigFormat) -> Dict[str, Any]:
        """
        Load configuration file.

        Args:
            format_type: File format

        Returns:
            Configuration dictionary
        """
        with open(self.config_path, "r") as f:
            if format_type == ConfigFormat.JSON:
                return json.load(f)
            elif format_type == ConfigFormat.YAML:
                return yaml.safe_load(f)
            elif format_type == ConfigFormat.TOML:
                return toml.load(f)
            else:
                raise ValueError(f"Unsupported format: {format_type}")

    def _get_config_format(self) -> ConfigFormat:
        """
        Determine configuration file format.

        Returns:
            Config format
        """
        suffix = self.config_path.suffix.lower()
        if suffix == ".json":
            return ConfigFormat.JSON
        elif suffix in [".yaml", ".yml"]:
            return ConfigFormat.YAML
        elif suffix == ".toml":
            return ConfigFormat.TOML
        else:
            # Try to detect from content
            return ConfigFormat.JSON

    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides"""
        # Environment-specific config file
        env = os.getenv("SPYDER_ENV", "paper").lower()
        env_config_path = self.config_path.parent / f"config.{env}.json"

        if env_config_path.exists():
            try:
                with open(env_config_path, "r") as f:
                    env_config = json.load(f)
                self._raw_config = self._deep_merge(self._raw_config, env_config)
                self.logger.info(f"Applied {env} environment configuration")
            except Exception as e:
                self.logger.error(f"Failed to load environment config: {e}")

        # Individual environment variables
        env_mappings = {
            "SPYDER_BROKER_HOST": "broker.host",
            "SPYDER_BROKER_PORT": "broker.port",
            "SPYDER_BROKER_CLIENT_ID": "broker.client_id",
            "SPYDER_LOG_LEVEL": "log_level",
            "SPYDER_DEBUG": "debug_mode",
            "SPYDER_DRY_RUN": "dry_run",
        }

        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(self._raw_config, config_path, value)

    def _load_credentials(self) -> None:
        """Load encrypted credentials"""
        try:
            # Email credentials
            email_user = self.credential_manager.get_credential("email_user")
            email_pass = self.credential_manager.get_credential("email_password")
            if email_user:
                self._set_nested_value(
                    self._raw_config, "notifications.email_user", email_user
                )
            if email_pass:
                self._set_nested_value(
                    self._raw_config, "notifications.email_password", email_pass
                )

            # Twilio credentials
            twilio_sid = self.credential_manager.get_credential("twilio_account_sid")
            twilio_token = self.credential_manager.get_credential("twilio_auth_token")
            if twilio_sid:
                self._set_nested_value(
                    self._raw_config, "notifications.twilio_account_sid", twilio_sid
                )
            if twilio_token:
                self._set_nested_value(
                    self._raw_config, "notifications.twilio_auth_token", twilio_token
                )

            # Telegram token
            telegram_token = self.credential_manager.get_credential(
                "telegram_bot_token"
            )
            if telegram_token:
                self._set_nested_value(
                    self._raw_config, "notifications.telegram_bot_token", telegram_token
                )

            # Database password
            db_password = self.credential_manager.get_credential("database_password")
            if db_password:
                self._set_nested_value(
                    self._raw_config, "database.password", db_password
                )

        except Exception as e:
            self.logger.warning(f"Failed to load some credentials: {e}")

    def _build_config(self) -> None:
        """Build configuration object from raw config"""
        # Environment
        env_str = self._raw_config.get("environment", "paper")
        self.config.environment = Environment(env_str.lower())

        # Broker
        broker_config = self._raw_config.get("broker", {})
        if "connection_type" in broker_config:
            broker_config["connection_type"] = ConnectionType(
                broker_config["connection_type"]
            )
        self.config.broker = BrokerConfig(**broker_config)

        # Market Data
        market_data_config = self._raw_config.get("market_data", {})
        self.config.market_data = MarketDataConfig(**market_data_config)

        # Risk
        risk_config = self._raw_config.get("risk", {})
        self.config.risk = RiskConfig(**risk_config)

        # Strategies
        strategy_config = self._raw_config.get("strategies", {})
        self.config.strategies = StrategyConfig(**strategy_config)

        # Trading Hours
        trading_hours_config = self._raw_config.get("trading_hours", {})
        self.config.trading_hours = TradingHoursConfig(**trading_hours_config)

        # Notifications
        notification_config = self._raw_config.get("notifications", {})
        self.config.notifications = NotificationConfig(**notification_config)

        # Database
        database_config = self._raw_config.get("database", {})
        self.config.database = DatabaseConfig(**database_config)

        # Performance
        performance_config = self._raw_config.get("performance", {})
        self.config.performance = PerformanceConfig(**performance_config)

        # System settings
        self.config.log_level = self._raw_config.get("log_level", "INFO")
        self.config.debug_mode = self._raw_config.get("debug_mode", False)
        self.config.dry_run = self._raw_config.get("dry_run", False)

    # ==========================================================================
    # CONFIGURATION SAVING
    # ==========================================================================
    def save_config(self, path: Optional[str] = None) -> None:
        """
        Save configuration to file.

        Args:
            path: Optional path to save to
        """
        save_path = Path(path) if path else self.config_path

        with self._config_lock:
            try:
                # Convert to dictionary
                config_dict = self._config_to_dict()

                # Remove sensitive data
                config_dict = self._remove_sensitive_data(config_dict)

                # Determine format
                format_type = self._get_config_format()

                # Save file
                with open(save_path, "w") as f:
                    if format_type == ConfigFormat.JSON:
                        json.dump(config_dict, f, indent=2)
                    elif format_type == ConfigFormat.YAML:
                        yaml.dump(config_dict, f, default_flow_style=False)
                    elif format_type == ConfigFormat.TOML:
                        toml.dump(config_dict, f)

                self.logger.info(f"Configuration saved to {save_path}")

            except Exception as e:
                self.logger.error(f"Failed to save configuration: {e}")
                raise

    def _config_to_dict(self) -> Dict[str, Any]:
        """Convert configuration object to dictionary"""
        config_dict = {
            "environment": self.config.environment.value,
            "broker": asdict(self.config.broker),
            "market_data": asdict(self.config.market_data),
            "risk": asdict(self.config.risk),
            "strategies": asdict(self.config.strategies),
            "trading_hours": asdict(self.config.trading_hours),
            "notifications": asdict(self.config.notifications),
            "database": asdict(self.config.database),
            "performance": asdict(self.config.performance),
            "log_level": self.config.log_level,
            "debug_mode": self.config.debug_mode,
            "dry_run": self.config.dry_run,
        }

        # Convert enums to values
        if "connection_type" in config_dict["broker"]:
            config_dict["broker"]["connection_type"] = config_dict["broker"][
                "connection_type"
            ].value

        return config_dict

    def _remove_sensitive_data(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from configuration"""
        result = copy.deepcopy(config_dict)

        # Remove passwords and tokens
        sensitive_paths = [
            "database.password",
            "notifications.email_password",
            "notifications.twilio_auth_token",
            "notifications.telegram_bot_token",
        ]

        for path in sensitive_paths:
            self._remove_nested_value(result, path)

        return result

    # ==========================================================================
    # HOT RELOADING
    # ==========================================================================
    def enable_hot_reload(self) -> None:
        """Enable configuration hot reloading"""
        if self._watching:
            return

        self._watching = True
        self._watch_thread = threading.Thread(
            target=self._watch_config_file, daemon=True, name="ConfigWatcher"
        )
        self._watch_thread.start()

        self.logger.info("Configuration hot reload enabled")

    def disable_hot_reload(self) -> None:
        """Disable configuration hot reloading"""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=5.0)

        self.logger.info("Configuration hot reload disabled")

    def _watch_config_file(self) -> None:
        """Watch configuration file for changes"""
        import time

        while self._watching:
            try:
                # Check if file has changed
                current_hash = self._calculate_file_hash()
                if current_hash != self._config_hash:
                    self.logger.info("Configuration file changed, reloading...")
                    self.reload_config()

                time.sleep(5.0)  # Check every 5 seconds

            except Exception as e:
                self.logger.error(f"Error watching config file: {e}")

    def reload_config(self) -> None:
        """Reload configuration from file"""
        try:
            old_config = copy.deepcopy(self.config)
            self.load_config()

            # Notify about changes
            changes = self._get_config_changes(old_config, self.config)
            if changes:
                self.logger.info(f"Configuration reloaded with {len(changes)} changes")
                for change in changes:
                    self.logger.info(f"  {change}")

        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def get_config(self) -> TradingConfig:
        """
        Get current configuration.

        Returns:
            Trading configuration
        """
        with self._config_lock:
            return copy.deepcopy(self.config)

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration values.

        Args:
            updates: Dictionary of updates
        """
        with self._config_lock:
            # Apply updates to raw config
            self._raw_config = self._deep_merge(self._raw_config, updates)

            # Rebuild config
            self._build_config()

            # Validate
            self.config.validate()

            # Save if auto-save enabled
            if hasattr(self, "auto_save") and self.auto_save:
                self.save_config()

    def get_value(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value by path.

        Args:
            path: Dot-separated path (e.g., "broker.host")
            default: Default value if not found

        Returns:
            Configuration value
        """
        with self._config_lock:
            return self._get_nested_value(self._raw_config, path, default)

    def set_value(self, path: str, value: Any) -> None:
        """
        Set configuration value by path.

        Args:
            path: Dot-separated path
            value: Value to set
        """
        with self._config_lock:
            self._set_nested_value(self._raw_config, path, value)
            self._build_config()
            self.config.validate()

    def validate_config(self) -> List[str]:
        """
        Validate configuration and return errors.

        Returns:
            List of validation errors
        """
        errors = []

        try:
            self.config.validate()
        except Exception as e:
            errors.append(str(e))

        # Additional validation
        if self.config.environment == Environment.PRODUCTION:
            if self.config.dry_run:
                errors.append("Dry run mode should not be enabled in production")
            if self.config.debug_mode:
                errors.append("Debug mode should not be enabled in production")

        return errors

    def export_config(
        self, format_type: ConfigFormat, include_sensitive: bool = False
    ) -> str:
        """
        Export configuration as string.

        Args:
            format_type: Export format
            include_sensitive: Include sensitive data

        Returns:
            Configuration string
        """
        config_dict = self._config_to_dict()

        if not include_sensitive:
            config_dict = self._remove_sensitive_data(config_dict)

        if format_type == ConfigFormat.JSON:
            return json.dumps(config_dict, indent=2)
        elif format_type == ConfigFormat.YAML:
            return yaml.dump(config_dict, default_flow_style=False)
        elif format_type == ConfigFormat.TOML:
            return toml.dumps(config_dict)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _deep_merge(
        self, base: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = copy.deepcopy(base)

        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _get_nested_value(
        self, data: Dict[str, Any], path: str, default: Any = None
    ) -> Any:
        """Get nested value from dictionary"""
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value in dictionary"""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Convert string values to appropriate types
        if isinstance(value, str):
            if value.lower() in ["true", "false"]:
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "").isdigit():
                value = float(value)

        current[keys[-1]] = value

    def _remove_nested_value(self, data: Dict[str, Any], path: str) -> None:
        """Remove nested value from dictionary"""
        keys = path.split(".")
        current = data

        for key in keys[:-1]:
            if key not in current:
                return
            current = current[key]

        if keys[-1] in current:
            del current[keys[-1]]

    def _calculate_hash(self) -> str:
        """Calculate configuration hash"""
        config_str = json.dumps(self._raw_config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def _calculate_file_hash(self) -> str:
        """Calculate file hash"""
        if not self.config_path.exists():
            return ""

        with open(self.config_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _get_config_changes(self, old: TradingConfig, new: TradingConfig) -> List[str]:
        """Get list of configuration changes"""
        changes = []

        # Compare each section
        old_dict = self._config_to_dict()
        new_dict = self._config_to_dict()

        def compare_dicts(d1: Dict, d2: Dict, prefix: str = "") -> None:
            for key in set(list(d1.keys()) + list(d2.keys())):
                path = f"{prefix}.{key}" if prefix else key

                if key not in d1:
                    changes.append(f"Added: {path} = {d2[key]}")
                elif key not in d2:
                    changes.append(f"Removed: {path}")
                elif d1[key] != d2[key]:
                    if isinstance(d1[key], dict) and isinstance(d2[key], dict):
                        compare_dicts(d1[key], d2[key], path)
                    else:
                        changes.append(f"Changed: {path} from {d1[key]} to {d2[key]}")

        compare_dicts(old_dict, new_dict)
        return changes

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key with optional default."""
        try:
            # Navigate nested keys using dot notation (e.g., 'broker.host')
            keys = key.split(".")
            value = self.config

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value
        except Exception as e:
            self.logger.warning(f"Error getting config key '{key}': {e}")
            return default

    def get_broker_config(self) -> Dict[str, Any]:
        """Get broker configuration section."""
        return self.get(
            "broker",
            {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 1,
                "connection_timeout": 30,
            },
        )

    def get_ib_host(self) -> str:
        """Get IB host."""
        return self.get("broker.host", "127.0.0.1")

    def get_ib_port(self) -> int:
        """Get IB port."""
        return self.get("broker.port", 7497)

    def get_spyder_client_id(self) -> int:
        """Get IB client ID."""
        return self.get("broker.client_id", 1)

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration if none exists."""
        default_config = {
            "ib": {
                "client_portal": {
                    "enabled": True,
                    "base_url": "https://localhost:5000",
                    "gateway_url": "https://localhost:5000",
                },
                "auth": {"method": "client_portal", "trading_mode": "paper"},
                "connection": {
                    "timeout": 30,
                    "retry_attempts": 3,
                    "retry_delay": 5,
                    "ssl_verify": False,
                },
            },
            "trading": {
                "symbol": "SPY",
                "strategy": "iron_condor",
                "position_size": {"max_contracts": 10, "max_daily_contracts": 50},
                "risk_management": {
                    "max_daily_loss": 500,
                    "max_position_loss": 100,
                    "profit_target": 0.5,
                    "stop_loss": 2.0,
                },
                "trading_hours": {
                    "market_open": "09:30",
                    "market_close": "16:00",
                    "timezone": "US/Eastern",
                    "trading_days": [
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                    ],
                },
                "options": {
                    "days_to_expiry": 45,
                    "delta_target": 0.15,
                    "strike_selection": "otm",
                    "spread_width": 5,
                },
            },
            "gui": {
                "enabled": True,
                "theme": "dark",
                "window_size": {"width": 1200, "height": 800},
                "auto_save_layout": True,
            },
            "logging": {
                "level": "INFO",
                "file_enabled": True,
                "console_enabled": True,
                "max_file_size": "10MB",
                "backup_count": 5,
            },
        }

        return default_config

    def _convert_json_to_dataclass_format(
        self, config_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert JSON config format to TradingConfig dataclass format."""
        try:
            # Map JSON structure to dataclass structure
            trading_config = {}

            # Environment (default to PAPER)
            trading_config["environment"] = Environment.PAPER

            # Broker config from IB section
            ib_config = config_data.get("ib", {})
            client_portal_config = ib_config.get("client_portal", {})

            # Map IB config to BrokerConfig
            broker_config = {
                "host": client_portal_config.get("base_url", "https://localhost:5000")
                .replace("https://", "")
                .replace("http://", "")
                .split(":")[0],
                "port": 4001,  # Default for Client Portal
                "client_id": 1,
                "connection_type": ConnectionType.TWS_PAPER,
                "account": "",
                "auto_reconnect": True,
                "max_reconnect_attempts": ib_config.get("connection", {}).get(
                    "retry_attempts", 10
                ),
                "reconnect_delay": ib_config.get("connection", {}).get(
                    "retry_delay", 5
                ),
            }
            trading_config["broker"] = broker_config

            # Market data config
            trading_section = config_data.get("trading", {})
            market_data_config = {
                "symbols": [trading_section.get("symbol", "SPY")],
                "data_types": ["TRADES", "QUOTES", "BARS", "OPTIONS"],
                "bar_size": "1 min",
                "historical_days": 5,
                "option_chain_strikes": 20,
                "option_chain_expiry_days": trading_section.get("options", {}).get(
                    "days_to_expiry", 45
                ),
                "cache_enabled": True,
                "cache_ttl_seconds": 300,
            }
            trading_config["market_data"] = market_data_config

            # Risk config
            risk_mgmt = trading_section.get("risk_management", {})
            risk_config = {
                "max_position_size": float(risk_mgmt.get("max_position_loss", 100.0)),
                "max_daily_loss": float(risk_mgmt.get("max_daily_loss", 500.0)),
                "max_positions": trading_section.get("position_size", {}).get(
                    "max_contracts", 5
                ),
                "max_portfolio_heat": 0.06,
                "position_size_method": "fixed",
                "stop_loss_percent": float(risk_mgmt.get("stop_loss", 0.02)),
                "take_profit_percent": float(risk_mgmt.get("profit_target", 0.05)),
                "max_correlation": 0.7,
                "use_trailing_stop": True,
                "trailing_stop_percent": 0.015,
            }
            trading_config["risk"] = risk_config

            # Strategy config
            options_config = trading_section.get("options", {})
            strategy_config = {
                "enabled_strategies": [trading_section.get("strategy", "iron_condor")],
                "iron_condor_enabled": True,
                "iron_condor_delta": float(options_config.get("delta_target", 0.15)),
                "iron_condor_dte_min": 30,
                "iron_condor_dte_max": options_config.get("days_to_expiry", 45),
                "iron_condor_min_credit": 1.0,
                "iron_condor_profit_target": float(risk_mgmt.get("profit_target", 0.5)),
                "credit_spread_enabled": True,
                "credit_spread_delta": 0.20,
                "credit_spread_dte_min": 15,
                "credit_spread_dte_max": 45,
                "credit_spread_min_credit": 0.5,
                "zero_dte_enabled": False,
                "zero_dte_start_time": "09:45",
                "zero_dte_end_time": "15:30",
                "zero_dte_max_contracts": 2,
            }
            trading_config["strategies"] = strategy_config

            # Trading hours config
            hours_config = trading_section.get("trading_hours", {})
            trading_hours_config = {
                "market_open": hours_config.get("market_open", "09:30"),
                "market_close": hours_config.get("market_close", "16:00"),
                "pre_market_start": "04:00",
                "after_hours_end": "20:00",
                "enable_pre_market": False,
                "enable_after_hours": False,
                "stop_new_trades_before_close": 30,
                "close_all_positions_before_close": 15,
                "trade_monday": True,
                "trade_tuesday": True,
                "trade_wednesday": True,
                "trade_thursday": True,
                "trade_friday": True,
            }
            trading_config["trading_hours"] = trading_hours_config

            # Notifications config
            notifications_section = config_data.get("notifications", {})
            notification_config = {
                "email_enabled": notifications_section.get("email_enabled", False),
                "email_smtp_host": "smtp.gmail.com",
                "email_smtp_port": 587,
                "email_from": "",
                "email_to": [],
                "sms_enabled": False,
                "sms_provider": "twilio",
                "sms_from": "",
                "sms_to": [],
                "telegram_enabled": False,
                "telegram_bot_token": "",
                "telegram_chat_ids": [],
                "alert_on_fill": notifications_section.get("trade_notifications", True),
                "alert_on_risk_limit": True,
                "alert_on_daily_summary": True,
                "alert_on_error": notifications_section.get(
                    "error_notifications", True
                ),
            }
            trading_config["notifications"] = notification_config

            # Database config
            database_config = {
                "type": "sqlite",
                "host": "localhost",
                "port": 5432,
                "name": "spyder",
                "user": "",
                "password": "",
                "sqlite_path": str(DEFAULT_CONFIG_DIR / "spyder.db"),
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
            }
            trading_config["database"] = database_config

            # Performance config
            performance_config = {
                "enable_profiling": False,
                "profile_interval": 300,
                "enable_metrics": True,
                "metrics_interval": 60,
                "max_memory_mb": 2048,
                "max_cpu_percent": 80.0,
                "trade_history_days": 365,
                "performance_history_days": 90,
                "log_retention_days": 30,
            }
            trading_config["performance"] = performance_config

            # System settings
            logging_config = config_data.get("logging", {})
            trading_config["log_level"] = logging_config.get("level", "INFO")
            trading_config["debug_mode"] = False
            trading_config["dry_run"] = False

            return trading_config

        except Exception as e:
            self.logger.error(f"Error converting config format: {e}")
            return self._get_default_dataclass_config()

    def _get_default_dataclass_config(self) -> Dict[str, Any]:
        """Get default configuration in dataclass format."""
        return {
            "environment": Environment.PAPER,
            "broker": {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 1,
                "connection_type": ConnectionType.TWS_PAPER,
                "account": "",
                "auto_reconnect": True,
                "max_reconnect_attempts": 10,
                "reconnect_delay": 5,
            },
            "market_data": {
                "symbols": ["SPY"],
                "data_types": ["TRADES", "QUOTES", "BARS", "OPTIONS"],
                "bar_size": "1 min",
                "historical_days": 5,
                "option_chain_strikes": 20,
                "option_chain_expiry_days": 45,
                "cache_enabled": True,
                "cache_ttl_seconds": 300,
            },
            "risk": {
                "max_position_size": 10000.0,
                "max_daily_loss": 500.0,
                "max_positions": 5,
                "max_portfolio_heat": 0.06,
                "position_size_method": "fixed",
                "stop_loss_percent": 0.02,
                "take_profit_percent": 0.05,
                "max_correlation": 0.7,
                "use_trailing_stop": True,
                "trailing_stop_percent": 0.015,
            },
            "strategies": {
                "enabled_strategies": ["iron_condor"],
                "iron_condor_enabled": True,
                "iron_condor_delta": 0.15,
                "iron_condor_dte_min": 30,
                "iron_condor_dte_max": 45,
                "iron_condor_min_credit": 1.0,
                "iron_condor_profit_target": 0.5,
                "credit_spread_enabled": True,
                "credit_spread_delta": 0.20,
                "credit_spread_dte_min": 15,
                "credit_spread_dte_max": 45,
                "credit_spread_min_credit": 0.5,
                "zero_dte_enabled": False,
                "zero_dte_start_time": "09:45",
                "zero_dte_end_time": "15:30",
                "zero_dte_max_contracts": 2,
            },
            "trading_hours": {
                "market_open": "09:30",
                "market_close": "16:00",
                "pre_market_start": "04:00",
                "after_hours_end": "20:00",
                "enable_pre_market": False,
                "enable_after_hours": False,
                "stop_new_trades_before_close": 30,
                "close_all_positions_before_close": 15,
                "trade_monday": True,
                "trade_tuesday": True,
                "trade_wednesday": True,
                "trade_thursday": True,
                "trade_friday": True,
            },
            "notifications": {
                "email_enabled": False,
                "email_smtp_host": "smtp.gmail.com",
                "email_smtp_port": 587,
                "email_from": "",
                "email_to": [],
                "sms_enabled": False,
                "sms_provider": "twilio",
                "sms_from": "",
                "sms_to": [],
                "telegram_enabled": False,
                "telegram_bot_token": "",
                "telegram_chat_ids": [],
                "alert_on_fill": True,
                "alert_on_risk_limit": True,
                "alert_on_daily_summary": True,
                "alert_on_error": True,
            },
            "database": {
                "type": "sqlite",
                "host": "localhost",
                "port": 5432,
                "name": "spyder",
                "user": "",
                "password": "",
                "sqlite_path": str(DEFAULT_CONFIG_DIR / "spyder.db"),
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
            },
            "performance": {
                "enable_profiling": False,
                "profile_interval": 300,
                "enable_metrics": True,
                "metrics_interval": 60,
                "max_memory_mb": 2048,
                "max_cpu_percent": 80.0,
                "trade_history_days": 365,
                "performance_history_days": 90,
                "log_retention_days": 30,
            },
            "log_level": "INFO",
            "debug_mode": False,
            "dry_run": False,
        }


# =============================================================================
# Global Configuration Manager Instance
# =============================================================================
_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager(config_path: Optional[str] = None) -> ConfigManager:
    """
    Get the global configuration manager instance (singleton pattern).

    Args:
        config_path: Path to configuration file (optional)

    Returns:
        ConfigManager: The global configuration manager instance
    """
    global _config_manager_instance

    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_path)

    return _config_manager_instance


def reset_config_manager() -> None:
    """Reset the global configuration manager instance."""
    global _config_manager_instance
    _config_manager_instance = None


# =============================================================================
# Module Test Function
# =============================================================================
if __name__ == "__main__":
    # Test the function
    try:
        config_mgr = get_config_manager()
        print("get_config_manager() works!")
        print(f"Config path: {config_mgr.config_path}")
        print(f"Config loaded: {config_mgr.config is not None}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()

# Global configuration manager instance
_config_manager_instance = None

def get_config_manager(config_path=None):
    """Get configuration manager instance."""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager(config_path)
    return _config_manager_instance

def reset_config_manager():
    """Reset configuration manager instance."""
    global _config_manager_instance
    _config_manager_instance = None
