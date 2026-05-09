#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU11_FeatureFlags.py
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
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

DEFAULT_CONFIG_FILE = "config/feature_flags.json"
CACHE_REFRESH_INTERVAL = 300  # 5 minutes
MAX_CACHE_AGE = 3600  # 1 hour

# Default feature flags
DEFAULT_FEATURES = {
    "advanced_risk_management": True,
    "ml_strategy_selection": False,
    "real_time_greek_monitoring": True,
    "automated_position_sizing": True,
    "dark_pool_detection": False,
    "sentiment_analysis": False,
    "news_impact_analysis": False,
    "zero_dte_strategies": True,
    "iron_condor_automation": True,
    "volatility_surface_analysis": False,
    "gamma_hedging": False,
    "portfolio_optimization": True,
    "alert_notifications": True,
    "performance_analytics": True,
}

# Environment-based overrides
ENVIRONMENT_OVERRIDES = {
    "development": {
        "ml_strategy_selection": True,
        "sentiment_analysis": True,
        "volatility_surface_analysis": True,
    },
    "testing": {"all_features": True},
    "production": {"experimental_features": False},
}


def _matching_now(reference: datetime | None = None) -> datetime:
    """Return now() with tz-awareness matching the reference timestamp."""
    if reference is not None and reference.tzinfo is None:
        return datetime.now()  # spyder: naive-ok
    return datetime.now(timezone.utc)

# ==============================================================================
# ENUMS
# ==============================================================================


class FeatureStatus(Enum):
    """Feature flag status"""

    ENABLED = "enabled"
    DISABLED = "disabled"
    TESTING = "testing"
    ROLLOUT = "rollout"
    DEPRECATED = "deprecated"


class RolloutStrategy(Enum):
    """Feature rollout strategy"""

    ALL = "all"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    CANARY = "canary"
    GRADUAL = "gradual"


class FeatureType(Enum):
    """Feature type classification"""

    CORE = "core"
    STRATEGY = "strategy"
    ANALYTICS = "analytics"
    UI = "ui"
    EXPERIMENTAL = "experimental"
    INTEGRATION = "integration"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class FeatureFlag:
    """Feature flag definition."""

    name: str
    enabled: bool
    status: FeatureStatus
    type: FeatureType
    description: str = ""
    rollout_percentage: float = 100.0
    rollout_strategy: RolloutStrategy = RolloutStrategy.ALL
    enabled_users: list[str] = field(default_factory=list)
    environments: list[str] = field(default_factory=lambda: ["all"])
    created_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_date: datetime | None = None
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation."""
        if not self.name:
            raise ValueError("Feature name cannot be empty")
        if not 0 <= self.rollout_percentage <= 100:
            raise ValueError("Rollout percentage must be between 0 and 100")

    def is_expired(self) -> bool:
        """Check if feature flag has expired."""
        if self.expires_date:
            return _matching_now(self.expires_date) > self.expires_date
        return False

    def is_enabled_for_user(self, user_id: str) -> bool:
        """Check if feature is enabled for specific user."""
        if not self.enabled:
            return False

        if self.is_expired():
            return False

        if self.rollout_strategy == RolloutStrategy.ALL:
            return True
        elif self.rollout_strategy == RolloutStrategy.USER_LIST:
            return user_id in self.enabled_users
        elif self.rollout_strategy == RolloutStrategy.PERCENTAGE:
            # Use hash of user_id + feature name for consistent rollout
            hash_input = f"{user_id}:{self.name}"
            hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)  # noqa: E501
            percentage = (hash_value % 100) + 1
            return percentage <= self.rollout_percentage

        return self.enabled

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status.value,
            "type": self.type.value,
            "description": self.description,
            "rollout_percentage": self.rollout_percentage,
            "rollout_strategy": self.rollout_strategy.value,
            "enabled_users": self.enabled_users,
            "environments": self.environments,
            "created_date": self.created_date.isoformat(),
            "modified_date": self.modified_date.isoformat(),
            "expires_date": self.expires_date.isoformat() if self.expires_date else None,
            "dependencies": self.dependencies,
            "metadata": self.metadata,
        }


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class FeatureFlags:
    """
    Feature flag management system.

    dynamic enabling/disabling, A/B testing, gradual rollouts, and
    configuration management. Features can be controlled globally,
    per environment, or per user with real-time updates.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        features: Dictionary of feature flags
        config_file: Path to configuration file
        cache_timestamp: Last cache update timestamp

    Example:
        >>> flags = FeatureFlags()
        >>> if flags.is_enabled("ml_strategy_selection"):
        ...     print("ML strategies enabled")
        >>> flags.enable_feature("sentiment_analysis")
        >>> flags.set_rollout_percentage("new_feature", 25.0)
    """

    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE):
        """Initialize the feature flags manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_file = config_file
        self.features: dict[str, FeatureFlag] = {}
        self.cache_timestamp = 0.0
        self.lock = threading.RLock()
        self.environment = os.getenv("SPYDER_ENV", "development")
        self.user_id = os.getenv("SPYDER_USER_ID", "default")

        # Load initial configuration
        self._load_configuration()

        self.logger.info(
            "%s initialized with %s features", self.__class__.__name__, len(self.features)
        )

    # ==========================================================================
    # PUBLIC METHODS - FEATURE CHECKING
    # ==========================================================================
    def is_enabled(self, feature_name: str, user_id: str | None = None) -> bool:
        """
        Check if a feature is enabled.

        Args:
            feature_name: Name of the feature to check
            user_id: Optional user ID for user-specific checks

        Returns:
            bool: True if feature is enabled

        Example:
            >>> flags = FeatureFlags()
            >>> enabled = flags.is_enabled("ml_strategy_selection")
            >>> user_enabled = flags.is_enabled("beta_feature", "user123")
        """
        try:
            self._refresh_cache_if_needed()

            if feature_name not in self.features:
                self.logger.warning("Unknown feature flag: %s", feature_name)
                return False

            feature = self.features[feature_name]
            current_user = user_id or self.user_id

            # Check environment restrictions
            if feature.environments and "all" not in feature.environments:
                if self.environment not in feature.environments:
                    return False

            # Check dependencies
            if feature.dependencies:
                for dep in feature.dependencies:
                    if not self.is_enabled(dep, current_user):
                        return False

            return feature.is_enabled_for_user(current_user)

        except Exception as e:
            self.logger.error("Error checking feature %s: %s", feature_name, e)
            return False

    def check_feature_enabled(self, feature_name: str, user_id: str | None = None) -> bool:
        """
        Alias for is_enabled method for backward compatibility.

        Args:
            feature_name: Name of the feature to check
            user_id: Optional user ID for user-specific checks

        Returns:
            bool: True if feature is enabled
        """
        return self.is_enabled(feature_name, user_id)

    def get_enabled_features(self, user_id: str | None = None) -> list[str]:
        """
        Get list of all enabled features for a user.

        Args:
            user_id: Optional user ID

        Returns:
            List of enabled feature names
        """
        enabled = []
        current_user = user_id or self.user_id

        for feature_name in self.features:
            if self.is_enabled(feature_name, current_user):
                enabled.append(feature_name)

        return enabled

    # ==========================================================================
    # PUBLIC METHODS - FEATURE MANAGEMENT
    # ==========================================================================
    def enable_feature(self, feature_name: str, save: bool = True) -> bool:
        """
        Enable a feature flag.

        Args:
            feature_name: Name of the feature to enable
            save: Whether to save changes to file

        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                if feature_name in self.features:
                    self.features[feature_name].enabled = True
                    feature = self.features[feature_name]
                    feature.modified_date = _matching_now(feature.modified_date)
                else:
                    # Create new feature
                    self.features[feature_name] = FeatureFlag(
                        name=feature_name,
                        enabled=True,
                        status=FeatureStatus.ENABLED,
                        type=FeatureType.EXPERIMENTAL,
                    )

                if save:
                    self._save_configuration()

                self.logger.info("Feature %s enabled", feature_name)
                return True

        except Exception as e:
            self.logger.error("Failed to enable feature %s: %s", feature_name, e)
            return False

    def disable_feature(self, feature_name: str, save: bool = True) -> bool:
        """
        Disable a feature flag.

        Args:
            feature_name: Name of the feature to disable
            save: Whether to save changes to file

        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                if feature_name in self.features:
                    self.features[feature_name].enabled = False
                    feature = self.features[feature_name]
                    feature.modified_date = _matching_now(feature.modified_date)

                    if save:
                        self._save_configuration()

                    self.logger.info("Feature %s disabled", feature_name)
                    return True
                else:
                    self.logger.warning("Feature %s not found", feature_name)
                    return False

        except Exception as e:
            self.logger.error("Failed to disable feature %s: %s", feature_name, e)
            return False

    def set_rollout_percentage(
        self, feature_name: str, percentage: float, save: bool = True
    ) -> bool:
        """
        Set rollout percentage for a feature.

        Args:
            feature_name: Name of the feature
            percentage: Rollout percentage (0-100)
            save: Whether to save changes to file

        Returns:
            bool: True if successful
        """
        try:
            if not 0 <= percentage <= 100:
                raise ValueError("Percentage must be between 0 and 100")

            with self.lock:
                if feature_name in self.features:
                    self.features[feature_name].rollout_percentage = percentage
                    self.features[feature_name].rollout_strategy = RolloutStrategy.PERCENTAGE
                    feature = self.features[feature_name]
                    feature.modified_date = _matching_now(feature.modified_date)

                    if save:
                        self._save_configuration()

                    self.logger.info("Feature %s rollout set to %s%%", feature_name, percentage)
                    return True
                else:
                    self.logger.warning("Feature %s not found", feature_name)
                    return False

        except Exception as e:
            self.logger.error("Failed to set rollout for %s: %s", feature_name, e)
            return False

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def create_feature(
        self,
        name: str,
        enabled: bool = False,
        feature_type: FeatureType = FeatureType.EXPERIMENTAL,
        description: str = "",
    ) -> bool:
        """
        Create a new feature flag.

        Args:
            name: Feature name
            enabled: Initial enabled state
            feature_type: Type of feature
            description: Feature description

        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                if name in self.features:
                    self.logger.warning("Feature %s already exists", name)
                    return False

                self.features[name] = FeatureFlag(
                    name=name,
                    enabled=enabled,
                    status=FeatureStatus.ENABLED if enabled else FeatureStatus.DISABLED,
                    type=feature_type,
                    description=description,
                )

                self._save_configuration()
                self.logger.info("Created feature flag: %s", name)
                return True

        except Exception as e:
            self.logger.error("Failed to create feature %s: %s", name, e)
            return False

    def get_feature_info(self, feature_name: str) -> dict[str, Any] | None:
        """
        Get detailed information about a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Dictionary with feature information or None
        """
        if feature_name in self.features:
            return self.features[feature_name].to_dict()
        return None

    def list_features(self, feature_type: FeatureType | None = None) -> list[dict[str, Any]]:
        """
        List all features with optional filtering.

        Args:
            feature_type: Optional filter by feature type

        Returns:
            List of feature dictionaries
        """
        features = []
        for feature in self.features.values():
            if feature_type is None or feature.type == feature_type:
                features.append(feature.to_dict())

        return sorted(features, key=lambda x: x["name"])

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _load_configuration(self) -> None:
        """Load feature flags from configuration file."""
        try:
            # Load from file if exists
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    config_data = json.load(f)

                for name, data in config_data.items():
                    try:
                        self.features[name] = FeatureFlag(
                            name=name,
                            enabled=data.get("enabled", False),
                            status=FeatureStatus(data.get("status", "disabled")),
                            type=FeatureType(data.get("type", "experimental")),
                            description=data.get("description", ""),
                            rollout_percentage=data.get("rollout_percentage", 100.0),
                            rollout_strategy=RolloutStrategy(data.get("rollout_strategy", "all")),
                            enabled_users=data.get("enabled_users", []),
                            environments=data.get("environments", ["all"]),
                            dependencies=data.get("dependencies", []),
                            metadata=data.get("metadata", {}),
                        )
                    except Exception as e:
                        self.logger.warning("Failed to load feature %s: %s", name, e)
            else:
                # Create default configuration
                self._create_default_configuration()

            # Apply environment overrides
            self._apply_environment_overrides()

            self.cache_timestamp = time.time()

        except Exception as e:
            self.logger.error("Failed to load configuration: %s", e)
            self._create_default_configuration()

    def _create_default_configuration(self) -> None:
        """Create default feature flag configuration."""
        try:
            for name, enabled in DEFAULT_FEATURES.items():
                self.features[name] = FeatureFlag(
                    name=name,
                    enabled=enabled,
                    status=FeatureStatus.ENABLED if enabled else FeatureStatus.DISABLED,
                    type=FeatureType.CORE,
                    description=f"Default feature: {name}",
                )

            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            self._save_configuration()

        except Exception as e:
            self.logger.error("Failed to create default configuration: %s", e)

    def _apply_environment_overrides(self) -> None:
        """Apply environment-specific overrides."""
        try:
            if self.environment in ENVIRONMENT_OVERRIDES:
                overrides = ENVIRONMENT_OVERRIDES[self.environment]

                for feature_name, enabled in overrides.items():
                    if feature_name == "all_features":
                        # Enable/disable all features
                        for feature in self.features.values():
                            feature.enabled = enabled
                    elif feature_name == "experimental_features":
                        # Enable/disable experimental features
                        for feature in self.features.values():
                            if feature.type == FeatureType.EXPERIMENTAL:
                                feature.enabled = enabled
                    elif feature_name in self.features:
                        self.features[feature_name].enabled = enabled

        except Exception as e:
            self.logger.error("Failed to apply environment overrides: %s", e)

    def _save_configuration(self) -> None:
        """Save feature flags to configuration file."""
        try:
            config_data = {}
            for name, feature in self.features.items():
                config_data[name] = feature.to_dict()

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2, default=str)

        except Exception as e:
            self.logger.error("Failed to save configuration: %s", e)

    def _refresh_cache_if_needed(self) -> None:
        """Refresh cache if needed based on age."""
        current_time = time.time()
        if current_time - self.cache_timestamp > CACHE_REFRESH_INTERVAL:
            self._load_configuration()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def check_feature_enabled(feature_name: str, user_id: str | None = None) -> bool:
    """
    Quick check for feature enablement.

    Args:
        feature_name: Name of the feature to check
        user_id: Optional user ID

    Returns:
        bool: True if feature is enabled
    """
    flags = get_feature_flags()
    return flags.check_feature_enabled(feature_name, user_id)


def is_feature_enabled(feature_name: str, user_id: str | None = None) -> bool:
    """
    Alias for check_feature_enabled.

    Args:
        feature_name: Name of the feature to check
        user_id: Optional user ID

    Returns:
        bool: True if feature is enabled
    """
    return check_feature_enabled(feature_name, user_id)


def enable_feature(feature_name: str) -> bool:
    """
    Enable a feature flag.

    Args:
        feature_name: Name of the feature to enable

    Returns:
        bool: True if successful
    """
    flags = get_feature_flags()
    return flags.enable_feature(feature_name)


def disable_feature(feature_name: str) -> bool:
    """
    Disable a feature flag.

    Args:
        feature_name: Name of the feature to disable

    Returns:
        bool: True if successful
    """
    flags = get_feature_flags()
    return flags.disable_feature(feature_name)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_feature_flags_instance: FeatureFlags | None = None


def get_feature_flags() -> FeatureFlags:
    """
    Get singleton instance of feature flags manager.

    Returns:
        FeatureFlags instance
    """
    global _feature_flags_instance
    if _feature_flags_instance is None:
        _feature_flags_instance = FeatureFlags()
    return _feature_flags_instance


# Aliases for backward compatibility
def is_spyderx_enabled(feature_name: str, user_id: str | None = None) -> bool:
    """Check if a SpyderX feature is enabled (alias for is_feature_enabled)."""
    return is_feature_enabled(feature_name, user_id)


# Default SpyderX feature flags dictionary
SPYDERX_FEATURE_FLAGS: dict[str, bool] = {
    "USE_AI_RISK": False,
    "USE_AI_FLOW": False,
    "ENABLE_SPYDERX_SHADOW": False,
    "USE_AI_GREEKS": False,
    "USE_AI_STRATEGY": False,
}


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code

    flags = FeatureFlags()

    # Test basic functionality

    # Test feature management
    flags.create_feature("test_feature", enabled=False, description="Test feature")

    flags.enable_feature("test_feature", save=False)

    # Test rollout percentage
    flags.set_rollout_percentage("test_feature", 50.0, save=False)
    enabled_count = 0
    for i in range(100):
        if flags.is_enabled("test_feature", f"user_{i}"):
            enabled_count += 1

    # Test enabled features list
    enabled_features = flags.get_enabled_features()

