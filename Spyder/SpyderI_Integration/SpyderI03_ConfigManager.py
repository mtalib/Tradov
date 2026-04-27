#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI03_ConfigManager.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
import time
import copy
from datetime import datetime, timedelta, timezone
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import yaml
import hashlib
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from jsonschema import validate, ValidationError
import toml

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU04_Encryption import EncryptionManager
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager

try:
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Configuration file formats
SUPPORTED_FORMATS = {'.json', '.yaml', '.yml', '.toml', '.ini'}
DEFAULT_CONFIG_FORMAT = '.json'

# Environment types
ENVIRONMENTS = {
    'development': 'dev',
    'staging': 'stage',
    'production': 'prod',
    'testing': 'test'
}

# Configuration categories
CONFIG_CATEGORIES = {
    'CORE': ['trading_engine', 'scheduler', 'event_manager'],
    'BROKER': ['ib_config', 'connection', 'authentication'],
    'MARKET_DATA': ['data_feeds', 'historical_data', 'real_time'],
    'STRATEGIES': ['strategy_params', 'execution_rules', 'risk_limits'],
    'RISK': ['position_limits', 'drawdown_controls', 'circuit_breakers'],
    'NOTIFICATIONS': ['alerts', 'email', 'telegram', 'slack'],
    'ML': ['model_configs', 'training_params', 'inference_settings'],
    'INFRASTRUCTURE': ['logging', 'monitoring', 'performance']
}

# Synchronization intervals
CONFIG_SYNC_INTERVAL = 5  # seconds
CONFIG_BACKUP_INTERVAL = 300  # 5 minutes
CONFIG_CLEANUP_INTERVAL = 3600  # 1 hour

# Security settings
ENCRYPTION_KEY_FILE = '.spyder_encryption_key'
SENSITIVE_KEYS = {
    'password', 'secret', 'key', 'token', 'api_key',
    'private_key', 'credential', 'auth', 'pin'
}

# Validation settings
MAX_CONFIG_SIZE = 10 * 1024 * 1024  # 10MB
MAX_NESTING_DEPTH = 10
CONFIG_HISTORY_LIMIT = 100

# ==============================================================================
# ENUMS
# ==============================================================================
class ConfigScope(Enum):
    """Configuration scope levels"""
    GLOBAL = "global"           # System-wide configuration
    MODULE = "module"           # Module-specific configuration
    STRATEGY = "strategy"       # Strategy-specific configuration
    SESSION = "session"         # Session-specific configuration
    USER = "user"              # User-specific configuration

class ConfigFormat(Enum):
    """Supported configuration formats"""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"

class ConfigEvent(Enum):
    """Configuration event types"""
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    RELOADED = "reloaded"
    VALIDATED = "validated"
    SYNCHRONIZED = "synchronized"
    ENCRYPTED = "encrypted"
    DECRYPTED = "decrypted"

class ValidationLevel(Enum):
    """Configuration validation levels"""
    NONE = "none"              # No validation
    BASIC = "basic"            # Basic type checking
    SCHEMA = "schema"          # JSON schema validation
    STRICT = "strict"          # Strict validation with business rules

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ConfigMetadata:
    """Configuration metadata"""
    name: str
    scope: ConfigScope
    format: ConfigFormat
    file_path: Path | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    checksum: str | None = None
    encrypted: bool = False
    schema_version: str | None = None
    environment: str | None = None
    tags: set[str] = field(default_factory=set)

@dataclass
class ConfigChange:
    """Configuration change record"""
    timestamp: datetime
    config_name: str
    event_type: ConfigEvent
    old_value: Any | None = None
    new_value: Any | None = None
    key_path: str | None = None
    user: str | None = None
    source: str | None = None
    description: str | None = None

@dataclass
class ConfigSubscription:
    """Configuration subscription for modules"""
    module_id: str
    config_name: str
    callback: Callable[[dict[str, Any]], None]
    key_patterns: list[str] | None = None
    immediate_notify: bool = True
    subscribed_at: datetime = field(default_factory=datetime.now)

@dataclass
class ConfigValidationRule:
    """Configuration validation rule"""
    name: str
    rule_type: str  # 'type', 'range', 'enum', 'regex', 'custom'
    parameters: dict[str, Any]
    message: str
    severity: str = 'error'  # 'error', 'warning', 'info'

@dataclass
class ConfigBackup:
    """Configuration backup information"""
    backup_id: str
    config_name: str
    backup_path: Path
    created_at: datetime
    metadata: ConfigMetadata
    size_bytes: int

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConfigManager:
    """
    Centralized configuration management system for SPYDER modules.

    This class provides comprehensive configuration management including
    real-time synchronization, validation, encryption, versioning, and
    hot reloading capabilities across all SPYDER modules.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event manager for notifications
        encryption_manager: Encryption/decryption handler

    Example:
        >>> config_mgr = ConfigManager()
        >>> config_mgr.register_config('trading_engine', engine_config)
        >>> config_mgr.subscribe('risk_manager', 'risk_limits', callback)
        >>> config_mgr.update_config('trading_engine', 'max_position_size', 1000)
    """

    def __init__(self, config_dir: Path | None = None, environment: str = 'development'):
        """
        Initialize the Configuration Manager.

        Args:
            config_dir: Directory for configuration files
            environment: Current environment (dev/staging/prod)
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()

        # Configuration settings
        self.config_dir = Path(config_dir) if config_dir else Path('./config')
        self.environment = environment
        self.config_dir.mkdir(exist_ok=True)

        # Configuration storage
        self.configs: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, ConfigMetadata] = {}
        self.subscriptions: dict[str, list[ConfigSubscription]] = defaultdict(list)
        self.validation_rules: dict[str, list[ConfigValidationRule]] = defaultdict(list)

        # Change tracking
        self.change_history: deque = deque(maxlen=CONFIG_HISTORY_LIMIT)
        self.pending_changes: dict[str, list[ConfigChange]] = defaultdict(list)

        # File watching
        self.file_observer: Observer | None = None
        self.watched_files: set[Path] = set()

        # Synchronization
        self.sync_lock = threading.RLock()
        self.is_syncing = False
        self.sync_thread: threading.Thread | None = None

        # Encryption
        self.encryption_manager = EncryptionManager()
        self.encrypted_configs: set[str] = set()

        # Backup management
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
        self.backups: dict[str, list[ConfigBackup]] = defaultdict(list)

        # Performance tracking
        self.performance_metrics = {
            'config_loads': 0,
            'config_saves': 0,
            'sync_operations': 0,
            'validation_checks': 0,
            'notifications_sent': 0
        }

        # Initialize components
        self._initialize_schemas()
        self._load_existing_configs()
        self._start_file_watching()
        self._start_sync_thread()

        # Register with integration hub
        if HUB_AVAILABLE:
            hub = get_integration_hub()
            if hub:
                hub.register_module(self, dependencies=['SpyderU04_Encryption'])

        self.logger.info("ConfigManager initialized for environment: %s", environment)

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION REGISTRATION
    # ==========================================================================

    def register_config(self, name: str, config_data: dict[str, Any],
                       scope: ConfigScope = ConfigScope.MODULE,
                       format: ConfigFormat = ConfigFormat.JSON,
                       schema: dict | None = None,
                       encrypt_sensitive: bool = True) -> bool:
        """
        Register a new configuration.

        Args:
            name: Configuration name
            config_data: Configuration data
            scope: Configuration scope
            format: File format
            schema: JSON schema for validation
            encrypt_sensitive: Whether to encrypt sensitive data

        Returns:
            Success status
        """
        try:
            with self.sync_lock:
                # Validate configuration
                if not self._validate_config(name, config_data, schema):
                    return False

                # Create metadata
                metadata = ConfigMetadata(
                    name=name,
                    scope=scope,
                    format=format,
                    environment=self.environment,
                    file_path=self._get_config_file_path(name, format)
                )

                # Encrypt sensitive data if requested
                if encrypt_sensitive:
                    config_data = self._encrypt_sensitive_data(config_data)
                    metadata.encrypted = True
                    self.encrypted_configs.add(name)

                # Calculate checksum
                metadata.checksum = self._calculate_checksum(config_data)

                # Store configuration
                self.configs[name] = copy.deepcopy(config_data)
                self.metadata[name] = metadata

                # Save to file
                self._save_config_to_file(name, config_data, metadata)

                # Create backup
                self._create_backup(name)

                # Record change
                change = ConfigChange(
                    timestamp=datetime.now(timezone.utc),
                    config_name=name,
                    event_type=ConfigEvent.CREATED,
                    new_value=config_data,
                    source=self.__class__.__name__
                )
                self.change_history.append(change)

                # Notify subscribers
                self._notify_subscribers(name, config_data, ConfigEvent.CREATED)

                # Update performance metrics
                self.performance_metrics['config_saves'] += 1

                self.logger.info("Registered configuration: %s", name)
                return True

        except Exception as e:
            self.error_handler.handle_error(e, f"register_config: {name}")
            return False

    def unregister_config(self, name: str, remove_file: bool = False) -> bool:
        """
        Unregister a configuration.

        Args:
            name: Configuration name
            remove_file: Whether to remove the config file

        Returns:
            Success status
        """
        try:
            with self.sync_lock:
                if name not in self.configs:
                    self.logger.warning("Configuration not found: %s", name)
                    return False

                # Get old config for change tracking
                old_config = self.configs[name]

                # Remove from storage
                del self.configs[name]
                metadata = self.metadata.pop(name, None)

                # Remove subscriptions
                if name in self.subscriptions:
                    del self.subscriptions[name]

                # Remove from encrypted set
                self.encrypted_configs.discard(name)

                # Remove file if requested
                if remove_file and metadata and metadata.file_path:
                    try:
                        metadata.file_path.unlink()
                        self.watched_files.discard(metadata.file_path)
                    except FileNotFoundError:
                        pass

                # Record change
                change = ConfigChange(
                    timestamp=datetime.now(timezone.utc),
                    config_name=name,
                    event_type=ConfigEvent.DELETED,
                    old_value=old_config,
                    source=self.__class__.__name__
                )
                self.change_history.append(change)

                # Notify subscribers
                self._notify_subscribers(name, None, ConfigEvent.DELETED)

                self.logger.info("Unregistered configuration: %s", name)
                return True

        except Exception as e:
            self.error_handler.handle_error(e, f"unregister_config: {name}")
            return False

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION ACCESS
    # ==========================================================================

    def get_config(self, name: str, decrypt: bool = True) -> dict[str, Any] | None:
        """
        Get configuration data.

        Args:
            name: Configuration name
            decrypt: Whether to decrypt sensitive data

        Returns:
            Configuration data or None
        """
        try:
            if name not in self.configs:
                self.logger.warning("Configuration not found: %s", name)
                return None

            config_data = copy.deepcopy(self.configs[name])

            # Decrypt if needed
            if decrypt and name in self.encrypted_configs:
                config_data = self._decrypt_sensitive_data(config_data)

            self.performance_metrics['config_loads'] += 1
            return config_data

        except Exception as e:
            self.error_handler.handle_error(e, f"get_config: {name}")
            return None

    def get_config_value(self, name: str, key_path: str, default: Any = None,
                        decrypt: bool = True) -> Any:
        """
        Get a specific configuration value using dot notation.

        Args:
            name: Configuration name
            key_path: Dot-separated path to value (e.g., 'db.connection.host')
            default: Default value if not found
            decrypt: Whether to decrypt sensitive data

        Returns:
            Configuration value or default
        """
        try:
            config = self.get_config(name, decrypt)
            if not config:
                return default

            # Navigate through nested keys
            current = config
            for key in key_path.split('.'):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default

            return current

        except Exception as e:
            self.error_handler.handle_error(e, f"get_config_value: {name}.{key_path}")
            return default

    def set_config_value(self, name: str, key_path: str, value: Any,
                        validate: bool = True, notify: bool = True) -> bool:
        """
        Set a specific configuration value using dot notation.

        Args:
            name: Configuration name
            key_path: Dot-separated path to value
            value: New value to set
            validate: Whether to validate the change
            notify: Whether to notify subscribers

        Returns:
            Success status
        """
        try:
            with self.sync_lock:
                if name not in self.configs:
                    self.logger.error("Configuration not found: %s", name)
                    return False

                # Get current config
                config = copy.deepcopy(self.configs[name])
                old_value = self.get_config_value(name, key_path)

                # Navigate to parent and set value
                keys = key_path.split('.')
                current = config

                # Navigate to parent
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                # Set the value
                current[keys[-1]] = value

                # Validate if requested
                if validate and not self._validate_config(name, config):
                    return False

                # Update configuration
                self.configs[name] = config

                # Update metadata
                if name in self.metadata:
                    self.metadata[name].updated_at = datetime.now(timezone.utc)
                    self.metadata[name].version += 1
                    self.metadata[name].checksum = self._calculate_checksum(config)

                # Save to file
                metadata = self.metadata.get(name)
                if metadata:
                    self._save_config_to_file(name, config, metadata)

                # Record change
                change = ConfigChange(
                    timestamp=datetime.now(timezone.utc),
                    config_name=name,
                    event_type=ConfigEvent.UPDATED,
                    old_value=old_value,
                    new_value=value,
                    key_path=key_path,
                    source=self.__class__.__name__
                )
                self.change_history.append(change)

                # Notify subscribers if requested
                if notify:
                    self._notify_subscribers(name, config, ConfigEvent.UPDATED, key_path)

                self.logger.debug("Updated config %s.%s = %s", name, key_path, value)
                return True

        except Exception as e:
            self.error_handler.handle_error(e, f"set_config_value: {name}.{key_path}")
            return False

    # ==========================================================================
    # PUBLIC METHODS - SUBSCRIPTION MANAGEMENT
    # ==========================================================================

    def subscribe(self, module_id: str, config_name: str,
                 callback: Callable[[dict[str, Any]], None],
                 key_patterns: list[str] | None = None,
                 immediate_notify: bool = True) -> bool:
        """
        Subscribe to configuration changes.

        Args:
            module_id: Subscribing module identifier
            config_name: Configuration name to watch
            callback: Callback function for notifications
            key_patterns: Optional key patterns to filter notifications
            immediate_notify: Whether to notify immediately with current config

        Returns:
            Success status
        """
        try:
            subscription = ConfigSubscription(
                module_id=module_id,
                config_name=config_name,
                callback=callback,
                key_patterns=key_patterns,
                immediate_notify=immediate_notify
            )

            self.subscriptions[config_name].append(subscription)

            # Immediate notification if requested
            if immediate_notify and config_name in self.configs:
                try:
                    callback(self.get_config(config_name))
                except Exception as e:
                    self.error_handler.handle_error(e, f"immediate_notify: {module_id}")

            self.logger.info("Module %s subscribed to %s", module_id, config_name)
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"subscribe: {module_id}")
            return False

    def unsubscribe(self, module_id: str, config_name: str | None = None) -> bool:
        """
        Unsubscribe from configuration changes.

        Args:
            module_id: Module identifier
            config_name: Specific config to unsubscribe from (None for all)

        Returns:
            Success status
        """
        try:
            removed_count = 0

            if config_name:
                # Remove from specific config
                if config_name in self.subscriptions:
                    original_len = len(self.subscriptions[config_name])
                    self.subscriptions[config_name] = [
                        sub for sub in self.subscriptions[config_name]
                        if sub.module_id != module_id
                    ]
                    removed_count = original_len - len(self.subscriptions[config_name])
            else:
                # Remove from all configs
                for config_subs in self.subscriptions.values():
                    original_len = len(config_subs)
                    config_subs[:] = [
                        sub for sub in config_subs
                        if sub.module_id != module_id
                    ]
                    removed_count += original_len - len(config_subs)

            self.logger.info("Removed %s subscriptions for %s", removed_count, module_id)
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"unsubscribe: {module_id}")
            return False

    # ==========================================================================
    # PUBLIC METHODS - UTILITY
    # ==========================================================================

    def reload_config(self, name: str) -> bool:
        """
        Reload configuration from file.

        Args:
            name: Configuration name

        Returns:
            Success status
        """
        try:
            if name not in self.metadata:
                self.logger.error("Configuration metadata not found: %s", name)
                return False

            metadata = self.metadata[name]
            if not metadata.file_path or not metadata.file_path.exists():
                self.logger.error("Configuration file not found: %s", metadata.file_path)
                return False

            # Load from file
            new_config = self._load_config_from_file(metadata.file_path, metadata.format)
            if new_config is None:
                return False

            # Validate
            if not self._validate_config(name, new_config):
                return False

            # Update configuration
            old_config = self.configs.get(name)
            self.configs[name] = new_config

            # Update metadata
            metadata.updated_at = datetime.now(timezone.utc)
            metadata.version += 1
            metadata.checksum = self._calculate_checksum(new_config)

            # Record change
            change = ConfigChange(
                timestamp=datetime.now(timezone.utc),
                config_name=name,
                event_type=ConfigEvent.RELOADED,
                old_value=old_config,
                new_value=new_config,
                source='file_reload'
            )
            self.change_history.append(change)

            # Notify subscribers
            self._notify_subscribers(name, new_config, ConfigEvent.RELOADED)

            self.logger.info("Reloaded configuration: %s", name)
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"reload_config: {name}")
            return False

    def get_config_summary(self) -> dict[str, Any]:
        """
        Get comprehensive configuration summary.

        Returns:
            Configuration summary
        """
        try:
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'environment': self.environment,
                'total_configs': len(self.configs),
                'encrypted_configs': len(self.encrypted_configs),
                'total_subscriptions': sum(len(subs) for subs in self.subscriptions.values()),
                'config_categories': {
                    category: [name for name in configs if any(
                        keyword in name.lower() for keyword in keywords
                    )]
                    for category, keywords in CONFIG_CATEGORIES.items()
                    for configs in [list(self.configs.keys())]
                },
                'recent_changes': len([
                    change for change in self.change_history
                    if change.timestamp > datetime.now(timezone.utc) - timedelta(hours=1)
                ]),
                'performance_metrics': self.performance_metrics.copy(),
                'sync_status': {
                    'is_syncing': self.is_syncing,
                    'watched_files': len(self.watched_files),
                    'pending_changes': sum(len(changes) for changes in self.pending_changes.values())  # noqa: E501
                }
            }

        except Exception as e:
            self.error_handler.handle_error(e, "get_config_summary")
            return {'error': str(e)}

    # ==========================================================================
    # PRIVATE METHODS - FILE OPERATIONS
    # ==========================================================================

    def _get_config_file_path(self, name: str, format: ConfigFormat) -> Path:
        """Get configuration file path"""
        env_suffix = f"_{self.environment}" if self.environment != 'development' else ""
        filename = f"{name}{env_suffix}.{format.value}"
        return self.config_dir / filename

    def _save_config_to_file(self, name: str, config_data: dict[str, Any],
                            metadata: ConfigMetadata) -> None:
        """Save configuration to file"""
        if not metadata.file_path:
            return

        try:
            # Create backup of existing file
            if metadata.file_path.exists():
                backup_path = metadata.file_path.with_suffix(f".backup.{int(time.time())}")
                shutil.copy2(metadata.file_path, backup_path)

            # Save based on format
            if metadata.format == ConfigFormat.JSON:
                with open(metadata.file_path, 'w') as f:
                    json.dump(config_data, f, indent=2, default=str)
            elif metadata.format == ConfigFormat.YAML:
                with open(metadata.file_path, 'w') as f:
                    yaml.dump(config_data, f, default_flow_style=False)
            elif metadata.format == ConfigFormat.TOML:
                with open(metadata.file_path, 'w') as f:
                    toml.dump(config_data, f)

            # Add to watched files
            self.watched_files.add(metadata.file_path)

        except Exception as e:
            self.error_handler.handle_error(e, f"_save_config_to_file: {name}")

    def _load_config_from_file(self, file_path: Path, format: ConfigFormat) -> dict[str, Any] | None:  # noqa: E501
        """Load configuration from file"""
        try:
            if not file_path.exists():
                return None

            with open(file_path) as f:
                if format == ConfigFormat.JSON:
                    return json.load(f)
                elif format == ConfigFormat.YAML:
                    return yaml.safe_load(f)
                elif format == ConfigFormat.TOML:
                    return toml.load(f)

            return None

        except Exception as e:
            self.error_handler.handle_error(e, f"_load_config_from_file: {file_path}")
            return None

    # ==========================================================================
    # PRIVATE METHODS - HELPER FUNCTIONS
    # ==========================================================================

    def _initialize_schemas(self) -> None:
        """Initialize configuration schemas"""
        # Load schemas from files or define defaults
        self.schemas = {}  # Would contain JSON schemas for validation

    def _load_existing_configs(self) -> None:
        """Load existing configuration files"""
        for file_path in self.config_dir.glob('*'):
            if file_path.suffix.lower() in SUPPORTED_FORMATS:
                self._load_config_file(file_path)

    def _load_config_file(self, file_path: Path) -> None:
        """Load a single configuration file"""
        try:
            # Determine format
            format_map = {
                '.json': ConfigFormat.JSON,
                '.yaml': ConfigFormat.YAML,
                '.yml': ConfigFormat.YAML,
                '.toml': ConfigFormat.TOML
            }
            format = format_map.get(file_path.suffix.lower())
            if not format:
                return

            # Extract name
            name = file_path.stem
            if f"_{self.environment}" in name:
                name = name.replace(f"_{self.environment}", "")

            # Load configuration
            config_data = self._load_config_from_file(file_path, format)
            if config_data:
                metadata = ConfigMetadata(
                    name=name,
                    scope=ConfigScope.MODULE,
                    format=format,
                    file_path=file_path,
                    environment=self.environment
                )

                self.configs[name] = config_data
                self.metadata[name] = metadata
                self.watched_files.add(file_path)

        except Exception as e:
            self.error_handler.handle_error(e, f"_load_config_file: {file_path}")

    def _start_file_watching(self) -> None:
        """Start file system watching"""
        try:
            if self.file_observer:
                return

            event_handler = ConfigFileHandler(self)
            self.file_observer = Observer()
            self.file_observer.schedule(event_handler, str(self.config_dir), recursive=True)
            self.file_observer.start()

        except Exception as e:
            self.error_handler.handle_error(e, "_start_file_watching")

    def _start_sync_thread(self) -> None:
        """Start synchronization thread"""
        try:
            if self.sync_thread and self.sync_thread.is_alive():
                return

            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()

        except Exception as e:
            self.error_handler.handle_error(e, "_start_sync_thread")

    def _sync_loop(self) -> None:
        """Main synchronization loop"""
        while True:
            try:
                time.sleep(CONFIG_SYNC_INTERVAL)  # thread-safe: time.sleep() intentional

                if self.pending_changes:
                    self._process_pending_changes()

                # Periodic backup
                if int(time.time()) % CONFIG_BACKUP_INTERVAL == 0:
                    self._create_periodic_backups()

                # Cleanup old backups
                if int(time.time()) % CONFIG_CLEANUP_INTERVAL == 0:
                    self._cleanup_old_backups()

            except Exception as e:
                self.error_handler.handle_error(e, "_sync_loop")
                time.sleep(10)  # thread-safe: time.sleep() intentional

    def _process_pending_changes(self) -> None:
        """Process pending configuration changes"""
        try:
            with self.sync_lock:
                self.is_syncing = True

                for config_name, changes in self.pending_changes.items():
                    if config_name in self.configs:
                        # Apply changes and notify
                        for change in changes:
                            self._notify_subscribers(config_name, self.configs[config_name],
                                                   change.event_type, change.key_path)

                # Clear pending changes
                self.pending_changes.clear()
                self.performance_metrics['sync_operations'] += 1

        except Exception as e:
            self.error_handler.handle_error(e, "_process_pending_changes")
        finally:
            self.is_syncing = False

    def _validate_config(self, name: str, config_data: dict[str, Any],
                        schema: dict | None = None) -> bool:
        """Validate configuration data"""
        try:
            # Basic validation
            if not isinstance(config_data, dict):
                self.logger.error("Configuration must be a dictionary: %s", name)
                return False

            # Size check
            config_str = json.dumps(config_data, default=str)
            if len(config_str.encode()) > MAX_CONFIG_SIZE:
                self.logger.error("Configuration too large: %s", name)
                return False

            # Depth check
            if self._get_nesting_depth(config_data) > MAX_NESTING_DEPTH:
                self.logger.error("Configuration nesting too deep: %s", name)
                return False

            # Schema validation
            if schema:
                try:
                    validate(instance=config_data, schema=schema)
                except ValidationError as e:
                    self.logger.error("Schema validation failed for %s: %s", name, e)
                    return False

            # Custom validation rules
            if name in self.validation_rules:
                for rule in self.validation_rules[name]:
                    if not self._apply_validation_rule(config_data, rule):
                        return False

            self.performance_metrics['validation_checks'] += 1
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"_validate_config: {name}")
            return False

    def _get_nesting_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate nesting depth of configuration"""
        if isinstance(obj, dict):
            if not obj:
                return depth
            return max(self._get_nesting_depth(v, depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return depth
            return max(self._get_nesting_depth(item, depth + 1) for item in obj)
        else:
            return depth

    def _apply_validation_rule(self, config_data: dict[str, Any],
                             rule: ConfigValidationRule) -> bool:
        """Apply a single validation rule"""
        try:
            # Implementation would depend on rule type
            # This is a simplified version
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"_apply_validation_rule: {rule.name}")
            return False

    def _encrypt_sensitive_data(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Encrypt sensitive configuration data"""
        try:
            encrypted_config = copy.deepcopy(config_data)

            def encrypt_recursive(obj: Any, path: str = "") -> Any:
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                            if isinstance(value, str):
                                obj[key] = self.encryption_manager.encrypt(value)
                        else:
                            obj[key] = encrypt_recursive(value, current_path)
                elif isinstance(obj, list):
                    return [encrypt_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
                return obj

            encrypt_recursive(encrypted_config)
            return encrypted_config

        except Exception as e:
            self.error_handler.handle_error(e, "_encrypt_sensitive_data")
            return config_data

    def _decrypt_sensitive_data(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Decrypt sensitive configuration data"""
        try:
            decrypted_config = copy.deepcopy(config_data)

            def decrypt_recursive(obj: Any, path: str = "") -> Any:
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
                            if isinstance(value, str):
                                try:
                                    obj[key] = self.encryption_manager.decrypt(value)
                                except Exception:
                                    pass  # Value might not be encrypted
                        else:
                            obj[key] = decrypt_recursive(value, current_path)
                elif isinstance(obj, list):
                    return [decrypt_recursive(item, f"{path}[{i}]") for i, item in enumerate(obj)]
                return obj

            decrypt_recursive(decrypted_config)
            return decrypted_config

        except Exception as e:
            self.error_handler.handle_error(e, "_decrypt_sensitive_data")
            return config_data

    def _calculate_checksum(self, config_data: dict[str, Any]) -> str:
        """Calculate configuration checksum"""
        try:
            config_str = json.dumps(config_data, sort_keys=True, default=str)
            return hashlib.sha256(config_str.encode()).hexdigest()
        except Exception:
            return ""

    def _notify_subscribers(self, config_name: str, config_data: dict[str, Any] | None,
                          event_type: ConfigEvent, key_path: str | None = None) -> None:
        """Notify subscribers of configuration changes"""
        try:
            if config_name not in self.subscriptions:
                return

            for subscription in self.subscriptions[config_name]:
                try:
                    # Check if subscriber is interested in this key path
                    if (subscription.key_patterns and key_path and
                        not any(self._matches_pattern(key_path, pattern)
                               for pattern in subscription.key_patterns)):
                        continue

                    # Prepare notification data
                    notification_data = {
                        'config_name': config_name,
                        'event_type': event_type.value,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'config_data': config_data,
                        'key_path': key_path
                    }

                    # Call subscriber callback
                    subscription.callback(notification_data)
                    self.performance_metrics['notifications_sent'] += 1

                except Exception as e:
                    self.error_handler.handle_error(e, f"notify_subscriber: {subscription.module_id}")  # noqa: E501

        except Exception as e:
            self.error_handler.handle_error(e, f"_notify_subscribers: {config_name}")

    def _matches_pattern(self, key_path: str, pattern: str) -> bool:
        """Check if key path matches pattern"""
        try:
            import fnmatch
            return fnmatch.fnmatch(key_path, pattern)
        except Exception:
            return False

    def _create_backup(self, config_name: str) -> None:
        """Create configuration backup"""
        try:
            if config_name not in self.configs or config_name not in self.metadata:
                return

            backup_id = f"{config_name}_{int(time.time())}"
            backup_path = self.backup_dir / f"{backup_id}.json"

            # Save backup
            with open(backup_path, 'w') as f:
                backup_data = {
                    'config_data': self.configs[config_name],
                    'metadata': asdict(self.metadata[config_name])
                }
                json.dump(backup_data, f, indent=2, default=str)

            # Create backup record
            backup = ConfigBackup(
                backup_id=backup_id,
                config_name=config_name,
                backup_path=backup_path,
                created_at=datetime.now(timezone.utc),
                metadata=self.metadata[config_name],
                size_bytes=backup_path.stat().st_size
            )

            self.backups[config_name].append(backup)

        except Exception as e:
            self.error_handler.handle_error(e, f"_create_backup: {config_name}")

    def _create_periodic_backups(self) -> None:
        """Create periodic backups of all configurations"""
        for config_name in self.configs:
            self._create_backup(config_name)

    def _cleanup_old_backups(self) -> None:
        """Clean up old configuration backups"""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)  # Keep 30 days

            for _config_name, backup_list in self.backups.items():
                # Remove old backups
                old_backups = [b for b in backup_list if b.created_at < cutoff_time]
                for backup in old_backups:
                    try:
                        backup.backup_path.unlink()
                        backup_list.remove(backup)
                    except FileNotFoundError:
                        pass

        except Exception as e:
            self.error_handler.handle_error(e, "_cleanup_old_backups")

    def shutdown(self) -> None:
        """Shutdown configuration manager"""
        try:
            # Stop file watching
            if self.file_observer:
                self.file_observer.stop()
                self.file_observer.join()

            # Save any pending changes
            if self.pending_changes:
                self._process_pending_changes()

            self.logger.info("ConfigManager shutdown completed")

        except Exception as e:
            self.error_handler.handle_error(e, "shutdown")

# ==============================================================================
# HELPER CLASSES
# ==============================================================================
class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration files"""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory or not self._is_config_file(event.src_path):
            return

        try:
            file_path = Path(event.src_path)
            if file_path in self.config_manager.watched_files:
                # Find config name
                for name, metadata in self.config_manager.metadata.items():
                    if metadata.file_path == file_path:
                        self.config_manager.reload_config(name)
                        break
        except Exception as e:
            self.logger.error("Error handling file modification: %s", e)

    def _is_config_file(self, file_path: str) -> bool:
        """Check if file is a configuration file"""
        return Path(file_path).suffix.lower() in SUPPORTED_FORMATS

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_config_manager(config_dir: Path | None = None,
                         environment: str = 'development') -> ConfigManager:
    """
    Factory function to create configuration manager.

    Args:
        config_dir: Configuration directory
        environment: Environment name

    Returns:
        Configured ConfigManager instance
    """
    return ConfigManager(config_dir, environment)

def get_default_config_schema() -> dict[str, Any]:
    """
    Get default configuration schema.

    Returns:
        Default JSON schema for configurations
    """
    return {
        "type": "object",
        "properties": {
            "module_name": {"type": "string"},
            "version": {"type": "string"},
            "enabled": {"type": "boolean"},
            "parameters": {"type": "object"}
        },
        "required": ["module_name", "version"]
    }

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Global configuration manager instance
_global_config_manager: ConfigManager | None = None

def get_global_config_manager() -> ConfigManager | None:
    """Get global configuration manager instance"""
    return _global_config_manager

def set_global_config_manager(config_manager: ConfigManager) -> None:
    """Set global configuration manager instance"""
    global _global_config_manager
    _global_config_manager = config_manager

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create config manager
    config_mgr = ConfigManager()

    # Test configuration registration
    test_config = {
        "module_name": "test_module",
        "version": "1.0",
        "enabled": True,
        "parameters": {
            "timeout": 30,
            "retries": 3,
            "api_key": "secret_key_123",  # Will be encrypted
            "database": {
                "host": "localhost",
                "port": 5432,
                "password": "db_secret"  # Will be encrypted
            }
        }
    }

    success = config_mgr.register_config("test_module", test_config)

    # Test configuration retrieval
    retrieved_config = config_mgr.get_config("test_module")
    if retrieved_config:
        pass

    # Test configuration update
    update_success = config_mgr.set_config_value("test_module", "parameters.timeout", 60)
    updated_timeout = config_mgr.get_config_value("test_module", "parameters.timeout")

    # Test subscription

    def config_callback(notification_data):
        pass

    sub_success = config_mgr.subscribe("test_subscriber", "test_module", config_callback)

    # Trigger a change to test notification
    config_mgr.set_config_value("test_module", "parameters.retries", 5)

    # Test configuration summary
    summary = config_mgr.get_config_summary()

    # Test environment-specific configuration
    prod_config = test_config.copy()
    prod_config["parameters"]["timeout"] = 120  # Different timeout for production

    prod_config_mgr = ConfigManager(environment='production')
    prod_success = prod_config_mgr.register_config("test_module", prod_config)

    prod_timeout = prod_config_mgr.get_config_value("test_module", "parameters.timeout")

    # Test configuration validation
    invalid_config = {"invalid": "structure", "missing": "required_fields"}
    invalid_success = config_mgr.register_config("invalid_module", invalid_config)

    # Performance metrics
    metrics = config_mgr.performance_metrics

    # Clean up
    config_mgr.unsubscribe("test_subscriber")
    config_mgr.shutdown()


    # Demonstrate integration with other modules

    strategy_config = {
        "strategy_name": "iron_condor",
        "version": "2.1",
        "enabled": True,
        "risk_parameters": {
            "max_position_size": 10,
            "stop_loss_pct": 0.50,
            "profit_target_pct": 0.30,
            "max_dte": 45,
            "min_dte": 7
        },
        "entry_conditions": {
            "iv_rank_min": 30,
            "iv_rank_max": 70,
            "trend_filter": True,
            "vix_max": 25
        },
        "execution": {
            "order_type": "LIMIT",
            "time_in_force": "DAY",
            "retry_attempts": 3
        }
    }

    config_mgr_demo = ConfigManager()
    config_mgr_demo.register_config("iron_condor_strategy", strategy_config)


    def risk_config_updated(notification_data):
        if notification_data['key_path'] and 'risk_parameters' in notification_data['key_path']:
            pass
            # Risk manager would update its limits here

    config_mgr_demo.subscribe("risk_manager", "iron_condor_strategy", risk_config_updated,
                             key_patterns=["risk_parameters.*"])

    # Simulate risk parameter change
    config_mgr_demo.set_config_value("iron_condor_strategy", "risk_parameters.max_position_size", 15)  # noqa: E501

    environments = ['development', 'staging', 'production']
    for env in environments:
        env_config = strategy_config.copy()
        env_config['risk_parameters']['max_position_size'] = {
            'development': 1,
            'staging': 5,
            'production': 10
        }[env]

        env_mgr = ConfigManager(environment=env)
        env_mgr.register_config("iron_condor_strategy", env_config)

