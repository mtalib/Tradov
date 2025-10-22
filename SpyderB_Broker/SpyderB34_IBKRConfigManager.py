#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB34_IBKRConfigManager.py
Purpose: IBKR Client Portal Web API configuration management

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-01-24 Time: 12:00:00

Module Description:
    This module provides configuration management for the IBKR Client Portal Web API wrapper.
    It handles loading, validating, and managing configuration settings from various sources
    including environment variables, configuration files, and runtime settings. The module
    implements a robust configuration system with support for multiple sources, validation,
    and runtime updates.

Module Constants:
    DEFAULT_CONFIG_FILE_NAME (str): Default configuration file name (default: "ibkr_config.yaml")
    DEFAULT_CONFIG_DIR (str): Default configuration directory (default: "config")
    CONFIG_ENV_VAR (str): Environment variable for config file path (default: "IBKR_CONFIG_FILE")
    MAX_CONFIG_FILE_SIZE (int): Maximum configuration file size in bytes (default: 1048576)

Change Log:
    2025-01-24 (v1.0.0):
        - Initial module creation following Spyder template standards
        - Implemented comprehensive configuration management
        - Added support for multiple configuration sources
        - Implemented configuration validation
        - Added runtime configuration updates
        - Implemented configuration persistence
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import yaml
import threading
import asyncio
import uuid
import warnings
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Safe imports with fallbacks
try:
    from SpyderU_Utilities.SpyderU07_Constants import BaseConstants
except ImportError:
    BaseConstants = None


# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG_FILE_NAME = "ibkr_config.yaml"
DEFAULT_CONFIG_DIR = "config"
CONFIG_ENV_VAR = "IBKR_CONFIG_FILE"
MAX_CONFIG_FILE_SIZE = 1048576  # 1MB

# ==============================================================================
# ENUMS
# ==============================================================================
class ModuleState(Enum):
    """Module operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()

class ConfigSource(Enum):
    """Configuration source enumeration."""
    DEFAULT = "default"
    FILE = "file"
    ENVIRONMENT = "environment"
    RUNTIME = "runtime"


@dataclass
class GatewayConfig:
    """Gateway configuration settings."""
    base_url: str = "https://localhost:5000"
    api_version: str = "v1"
    timeout: int = 30
    verify_ssl: bool = False
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class SessionConfig:
    """Session management configuration."""
    auth_check_interval: int = 5  # seconds
    tickle_interval: int = 60  # seconds
    max_auth_wait: int = 300  # 5 minutes
    session_refresh_interval: int = 3600  # 1 hour
    auto_refresh: bool = True


@dataclass
class OrderConfig:
    """Order management configuration."""
    default_timeout: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    validate_orders: bool = True
    order_cache_duration: int = 300  # 5 minutes
    max_order_history: int = 1000
    default_tif: str = "DAY"  # Time in force


@dataclass
class MarketDataConfig:
    """Market data configuration."""
    default_timeout: int = 10
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_duration: int = 5  # seconds
    max_cache_size: int = 1000
    rate_limit_delay: float = 0.1  # seconds between requests
    default_fields: List[str] = field(default_factory=lambda: [
        "31",  # Last price
        "84",  # Bid
        "86"   # Ask
    ])


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: Optional[str] = None
    max_size: str = "10MB"
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class IBKRConfig:
    """Complete IBKR configuration."""
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    orders: OrderConfig = field(default_factory=OrderConfig)
    market_data: MarketDataConfig = field(default_factory=MarketDataConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    # Account settings
    default_account: Optional[str] = None
    paper_account: Optional[str] = None

    # Feature flags
    use_ibkr_wrapper: bool = True
    enable_realtime_data: bool = True
    enable_historical_data: bool = True

    # Environment settings
    environment: str = "production"  # production, certification, paper

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IBKRConfig':
        """Create configuration from dictionary."""
        # Handle nested configurations
        if 'gateway' in data:
            data['gateway'] = GatewayConfig(**data['gateway'])

        if 'session' in data:
            data['session'] = SessionConfig(**data['session'])

        if 'orders' in data:
            data['orders'] = OrderConfig(**data['orders'])

        if 'market_data' in data:
            data['market_data'] = MarketDataConfig(**data['market_data'])

        if 'logging' in data:
            data['logging'] = LoggingConfig(**data['logging'])

        return cls(**data)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConfigManager:
    """
    Manages configuration for IBKR Client Portal API wrapper.

    This class handles loading configuration from multiple sources,
    validating settings, and providing access to configuration
    values throughout the application.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        state: Current module state
        config_file: Path to configuration file
        _state_lock: Thread lock for state management
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize Configuration Manager.

        Args:
            config_file: Path to configuration file
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # State management
        self.state = ModuleState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Configuration file path
        self.config_file = config_file or self._find_config_file()

        # Current configuration
        self._config: IBKRConfig = IBKRConfig()

        # Configuration source tracking
        self._config_sources: Dict[str, ConfigSource] = {}

        # Load configuration
        self._load_configuration()

        self.state = ModuleState.READY
        self.logger.info(f"ConfigManager initialized with config file: {self.config_file}")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the configuration manager with all necessary setup.

        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False

                self.logger.info(f"Initializing {self.__class__.__name__}...")

                # Perform initialization tasks
                if not self._validate_configuration():
                    return False

                if not self._setup_resources():
                    return False

                self.state = ModuleState.READY
                self.logger.info(f"{self.__class__.__name__} initialization completed")
                return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "initialize")
            self.state = ModuleState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the configuration manager.

        Returns:
            bool: True if start successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.READY:
                    self.logger.warning(f"Cannot start from state: {self.state}")
                    return False

                self.logger.info(f"Starting {self.__class__.__name__}...")

                # Clear shutdown event
                self._shutdown_event.clear()

                self.state = ModuleState.RUNNING
                self.logger.info(f"{self.__class__.__name__} started successfully")
                return True

        except Exception as e:
            self.logger.error(f"Failed to start {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "start")
            self.state = ModuleState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the configuration manager gracefully.

        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [ModuleState.RUNNING, ModuleState.PAUSED]:
                    self.logger.warning(f"Cannot stop from state: {self.state}")
                    return False

                self.logger.info(f"Stopping {self.__class__.__name__}...")

                # Signal shutdown
                self._shutdown_event.set()

                # Clean up resources
                self._cleanup_resources()

                self.state = ModuleState.STOPPED
                self.logger.info(f"{self.__class__.__name__} stopped successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _validate_configuration(self) -> bool:
        """Validate module configuration."""
        try:
            if not self.config_file and not os.getenv(CONFIG_ENV_VAR):
                self.logger.debug("No configuration file specified, using defaults")

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _setup_resources(self) -> bool:
        """Set up required resources."""
        try:
            # Setup any required resources
            self.logger.debug("Resources setup completed")
            return True

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            return False

    def _cleanup_resources(self):
        """Clean up allocated resources."""
        try:
            # Clean up any resources
            self._config_sources.clear()
            self.logger.debug("Resources cleaned up")

        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")

    # ==========================================================================
    # CORE OPERATIONS
    # ==========================================================================

    def get_config(self) -> IBKRConfig:
        """
        Get current configuration.

        Returns:
            Current IBKR configuration
        """
        return self._config

    def get_gateway_config(self) -> GatewayConfig:
        """Get gateway configuration."""
        return self._config.gateway

    def get_session_config(self) -> SessionConfig:
        """Get session configuration."""
        return self._config.session

    def get_order_config(self) -> OrderConfig:
        """Get order configuration."""
        return self._config.orders

    def get_market_data_config(self) -> MarketDataConfig:
        """Get market data configuration."""
        return self._config.market_data

    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        return self._config.logging

    def update_config(self, updates: Dict[str, Any], source: ConfigSource = ConfigSource.RUNTIME) -> bool:
        """
        Update configuration with new values.

        Args:
            updates: Configuration updates
            source: Source of the updates

        Returns:
            True if update successful
        """
        try:
            # Convert to dict for merging
            current_dict = self._config.to_dict()

            # Merge updates
            self._deep_merge(current_dict, updates)

            # Create new configuration
            new_config = IBKRConfig.from_dict(current_dict)

            # Validate new configuration
            if self._validate_config(new_config):
                self._config = new_config

                # Track source
                for key in updates.keys():
                    self._config_sources[key] = source

                self.logger.info(f"Configuration updated from {source.value}")
                return True
            else:
                self.logger.error("Configuration validation failed")
                return False

        except Exception as e:
            self.logger.error(f"Error updating configuration: {e}")
            return False

    def save_config(self, file_path: Optional[str] = None) -> bool:
        """
        Save current configuration to file.

        Args:
            file_path: Path to save configuration (uses default if None)

        Returns:
            True if save successful
        """
        try:
            save_path = file_path or self.config_file

            if not save_path:
                self.logger.error("No configuration file path specified")
                return False

            # Create directory if it doesn't exist
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)

            # Save configuration
            with open(save_path, 'w') as f:
                if save_path.endswith('.yaml') or save_path.endswith('.yml'):
                    yaml.dump(self._config.to_dict(), f, default_flow_style=False, indent=2)
                else:
                    json.dump(self._config.to_dict(), f, indent=2)

            self.logger.info(f"Configuration saved to {save_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    def get_config_source(self, key: str) -> Optional[ConfigSource]:
        """
        Get the source of a configuration value.

        Args:
            key: Configuration key

        Returns:
            Source of the configuration value
        """
        return self._config_sources.get(key)

    def reload_config(self) -> bool:
        """
        Reload configuration from sources.

        Returns:
            True if reload successful
        """
        try:
            self._config_sources.clear()
            self._load_configuration()
            self.logger.info("Configuration reloaded")
            return True
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")
            return False

    def _find_config_file(self) -> Optional[str]:
        """Find configuration file in standard locations."""
        # Check environment variable first
        config_file = os.getenv('IBKR_CONFIG_FILE')
        if config_file and os.path.exists(config_file):
            return config_file

        # Check standard locations
        locations = [
            os.path.join(os.getcwd(), 'ibkr_config.yaml'),
            os.path.join(os.getcwd(), 'ibkr_config.json'),
            os.path.join(os.path.expanduser('~'), '.ibkr', 'config.yaml'),
            os.path.join(os.path.expanduser('~'), '.ibkr', 'config.json'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'ibkr_config.yaml'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'ibkr_config.json')
        ]

        for location in locations:
            if os.path.exists(location):
                return location

        return None

    def _load_configuration(self):
        """Load configuration from all sources."""
        # Start with default configuration
        self._config = IBKRConfig()

        # Load from file if available
        if self.config_file and os.path.exists(self.config_file):
            self._load_from_file()

        # Load from environment variables
        self._load_from_environment()

        # Validate final configuration
        self._validate_config(self._config)

    def _load_from_file(self):
        """Load configuration from file."""
        try:
            data = None
            if self.config_file:
                with open(self.config_file, 'r') as f:
                    if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                        data = yaml.safe_load(f)
                    else:
                        data = json.load(f)

            if data:
                # Update configuration
                self.update_config(data, ConfigSource.FILE)
                self.logger.info(f"Configuration loaded from {self.config_file}")

        except Exception as e:
            self.logger.error(f"Error loading configuration from file: {e}")

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_mappings = {
            # Gateway settings
            'IBKR_GATEWAY_URL': ('gateway', 'base_url'),
            'IBKR_API_VERSION': ('gateway', 'api_version'),
            'IBKR_TIMEOUT': ('gateway', 'timeout'),
            'IBKR_VERIFY_SSL': ('gateway', 'verify_ssl'),

            # Session settings
            'IBKR_AUTH_CHECK_INTERVAL': ('session', 'auth_check_interval'),
            'IBKR_TICKLE_INTERVAL': ('session', 'tickle_interval'),

            # Order settings
            'IBKR_ORDER_TIMEOUT': ('orders', 'default_timeout'),
            'IBKR_VALIDATE_ORDERS': ('orders', 'validate_orders'),

            # Market data settings
            'IBKR_CACHE_DURATION': ('market_data', 'cache_duration'),
            'IBKR_RATE_LIMIT_DELAY': ('market_data', 'rate_limit_delay'),

            # Account settings
            'IBKR_DEFAULT_ACCOUNT': ('default_account',),
            'IBKR_PAPER_ACCOUNT': ('paper_account',),

            # Feature flags
            'IBKR_USE_WRAPPER': ('use_ibkr_wrapper',),
            'IBKR_ENVIRONMENT': ('environment',),

            # Logging settings
            'IBKR_LOG_LEVEL': ('logging', 'level'),
            'IBKR_LOG_FILE': ('logging', 'file'),
        }

        updates = {}
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert value to appropriate type
                converted_value = self._convert_env_value(value)

                # Build nested dict structure
                current = updates
                for part in config_path[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Set final value
                current[config_path[-1]] = converted_value

        if updates:
            self.update_config(updates, ConfigSource.ENVIRONMENT)
            self.logger.info("Configuration loaded from environment variables")

    def _convert_env_value(self, value: str) -> Any:
        """Convert environment variable value to appropriate type."""
        # Handle boolean values
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False

        # Handle numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass

        # Return as string
        return value

    def _validate_config(self, config: IBKRConfig) -> bool:
        """Validate configuration values."""
        try:
            # Validate gateway URL
            if not config.gateway.base_url:
                self.logger.error("Gateway base URL is required")
                return False

            # Validate timeout values
            if config.gateway.timeout <= 0:
                self.logger.error("Gateway timeout must be positive")
                return False

            # Validate session intervals
            if config.session.auth_check_interval <= 0:
                self.logger.error("Auth check interval must be positive")
                return False

            if config.session.tickle_interval <= 0:
                self.logger.error("Tickle interval must be positive")
                return False

            # Validate order settings
            if config.orders.default_timeout <= 0:
                self.logger.error("Order timeout must be positive")
                return False

            # Validate market data settings
            if config.market_data.cache_duration < 0:
                self.logger.error("Cache duration cannot be negative")
                return False

            if config.market_data.rate_limit_delay < 0:
                self.logger.error("Rate limit delay cannot be negative")
                return False

            # Validate logging level
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if config.logging.level not in valid_log_levels:
                self.logger.error(f"Invalid log level: {config.logging.level}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error validating configuration: {e}")
            return False

    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge source dictionary into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get current module status.

        Returns:
            Dictionary containing status information
        """
        return {
            'name': self.__class__.__name__,
            'state': self.state.name,
            'config_file': self.config_file,
            'config_sources': {k: v.value for k, v in self._config_sources.items()},
            'environment': self._config.environment,
            'default_account': self._config.default_account
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


if __name__ == "__main__":
    # Example usage
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create config manager
    config_manager = ConfigManager()

    # Get configuration
    config = config_manager.get_config()
    print(f"Gateway URL: {config.gateway.base_url}")
    print(f"Environment: {config.environment}")
    print(f"Default Account: {config.default_account}")

    # Update configuration
    updates = {
        'gateway': {
            'timeout': 45
        },
        'environment': 'paper'
    }

    if config_manager.update_config(updates):
        print("Configuration updated successfully")
        updated_config = config_manager.get_config()
        print(f"Updated Gateway Timeout: {updated_config.gateway.timeout}")
        print(f"Updated Environment: {updated_config.environment}")

    # Save configuration
    if config_manager.save_config('test_config.yaml'):
        print("Configuration saved to test_config.yaml")