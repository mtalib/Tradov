#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT93_U11FeatureFlags_U09DataTypes.py
Purpose: Test suite for SpyderU11_FeatureFlags and SpyderU09_DataTypes

Author: Test Suite
Year Created: 2025
Last Updated: 2026-01-20 Time: 10:00:00
"""

# ==============================================================================
# BOOTSTRAP — must come before any local imports
# ==============================================================================
import os
import sys
import types
from unittest.mock import MagicMock, patch, mock_open
import pytest

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

# Stub SpyderLogger
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Stub SpyderErrorHandler
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORTS UNDER TEST
# ==============================================================================
import json
import tempfile
from datetime import datetime, date, timedelta

import SpyderU_Utilities.SpyderU11_FeatureFlags as u11_mod
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import (
    FeatureFlag,
    FeatureFlags,
    FeatureStatus,
    FeatureType,
    RolloutStrategy,
    DEFAULT_FEATURES,
    ENVIRONMENT_OVERRIDES,
    DEFAULT_CONFIG_FILE,
    CACHE_REFRESH_INTERVAL,
    MAX_CACHE_AGE,
    SPYDERX_FEATURE_FLAGS,
    get_feature_flags,
    check_feature_enabled,
    is_feature_enabled,
    enable_feature,
    disable_feature,
    is_spyderx_enabled,
)

import SpyderU_Utilities.SpyderU09_DataTypes as u09_mod
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import (
    MarketData,
    OptionContract,
    OrderData,
    Position,
    GreeksData,
    TradeExecution,
    OptionData,
    PositionData,
    SpyderDataTypes,
    OptionRight,
    OptionStyle,
    OrderType,
    OrderAction,
    OrderStatus,
    PositionSide,
    DataQuality,
    MarketDataType,
    MARKET_DATA_FIELDS,
    OPTION_RIGHTS,
    OPTION_STYLES,
    ORDER_TYPES,
    ORDER_ACTIONS,
    ORDER_STATUS,
    create_market_data,
    create_option_contract,
    get_data_types,
)


# ==============================================================================
# HELPERS
# ==============================================================================

def make_flags(tmp_path, env="development"):
    """Create a FeatureFlags instance backed by a temp file."""
    config_file = str(tmp_path / "flags.json")
    with patch.dict(os.environ, {"SPYDER_ENV": env}):
        return FeatureFlags(config_file=config_file)


def make_flags_from_json(tmp_path, data: dict, env="development"):
    """Create a FeatureFlags instance by writing initial JSON first."""
    config_file = tmp_path / "flags.json"
    config_file.write_text(json.dumps(data))
    with patch.dict(os.environ, {"SPYDER_ENV": env}):
        return FeatureFlags(config_file=str(config_file))


def future_date():
    return datetime.now() + timedelta(days=30)


def past_date():
    return datetime.now() - timedelta(days=1)


# ==============================================================================
# U11 — MODULE-LEVEL CONSTANTS
# ==============================================================================

class TestU11Constants:
    def test_default_config_file_value(self):
        assert DEFAULT_CONFIG_FILE == "config/feature_flags.json"

    def test_cache_refresh_interval(self):
        assert CACHE_REFRESH_INTERVAL == 300

    def test_max_cache_age(self):
        assert MAX_CACHE_AGE == 3600

    def test_default_features_is_dict(self):
        assert isinstance(DEFAULT_FEATURES, dict)
        assert len(DEFAULT_FEATURES) > 0

    def test_default_features_has_known_keys(self):
        assert "advanced_risk_management" in DEFAULT_FEATURES
        assert "ml_strategy_selection" in DEFAULT_FEATURES
        assert "zero_dte_strategies" in DEFAULT_FEATURES

    def test_default_features_boolean_values(self):
        for v in DEFAULT_FEATURES.values():
            assert isinstance(v, bool)

    def test_environment_overrides_is_dict(self):
        assert isinstance(ENVIRONMENT_OVERRIDES, dict)
        assert "development" in ENVIRONMENT_OVERRIDES
        assert "testing" in ENVIRONMENT_OVERRIDES
        assert "production" in ENVIRONMENT_OVERRIDES

    def test_spyderx_feature_flags_dict(self):
        assert isinstance(SPYDERX_FEATURE_FLAGS, dict)
        assert "USE_AI_RISK" in SPYDERX_FEATURE_FLAGS
        assert SPYDERX_FEATURE_FLAGS["USE_AI_RISK"] is False


# ==============================================================================
# U11 — ENUMS
# ==============================================================================

class TestFeatureStatus:
    def test_enabled_value(self):
        assert FeatureStatus.ENABLED.value == "enabled"

    def test_disabled_value(self):
        assert FeatureStatus.DISABLED.value == "disabled"

    def test_testing_value(self):
        assert FeatureStatus.TESTING.value == "testing"

    def test_rollout_value(self):
        assert FeatureStatus.ROLLOUT.value == "rollout"

    def test_deprecated_value(self):
        assert FeatureStatus.DEPRECATED.value == "deprecated"

    def test_five_members(self):
        assert len(FeatureStatus) == 5


class TestRolloutStrategy:
    def test_all_value(self):
        assert RolloutStrategy.ALL.value == "all"

    def test_percentage_value(self):
        assert RolloutStrategy.PERCENTAGE.value == "percentage"

    def test_user_list_value(self):
        assert RolloutStrategy.USER_LIST.value == "user_list"

    def test_canary_value(self):
        assert RolloutStrategy.CANARY.value == "canary"

    def test_gradual_value(self):
        assert RolloutStrategy.GRADUAL.value == "gradual"

    def test_five_members(self):
        assert len(RolloutStrategy) == 5


class TestFeatureType:
    def test_core_value(self):
        assert FeatureType.CORE.value == "core"

    def test_strategy_value(self):
        assert FeatureType.STRATEGY.value == "strategy"

    def test_analytics_value(self):
        assert FeatureType.ANALYTICS.value == "analytics"

    def test_ui_value(self):
        assert FeatureType.UI.value == "ui"

    def test_experimental_value(self):
        assert FeatureType.EXPERIMENTAL.value == "experimental"

    def test_integration_value(self):
        assert FeatureType.INTEGRATION.value == "integration"


# ==============================================================================
# U11 — FeatureFlag DATACLASS
# ==============================================================================

class TestFeatureFlagInit:
    def test_basic_creation(self):
        ff = FeatureFlag(
            name="test", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE
        )
        assert ff.name == "test"
        assert ff.enabled is True

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            FeatureFlag(name="", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)

    def test_invalid_rollout_percentage_raises(self):
        with pytest.raises(ValueError, match="Rollout percentage"):
            FeatureFlag(
                name="f", enabled=True, status=FeatureStatus.ENABLED,
                type=FeatureType.CORE, rollout_percentage=101.0
            )

    def test_negative_rollout_percentage_raises(self):
        with pytest.raises(ValueError, match="Rollout percentage"):
            FeatureFlag(
                name="f", enabled=True, status=FeatureStatus.ENABLED,
                type=FeatureType.CORE, rollout_percentage=-1.0
            )

    def test_zero_rollout_allowed(self):
        ff = FeatureFlag(
            name="f", enabled=True, status=FeatureStatus.ENABLED,
            type=FeatureType.CORE, rollout_percentage=0.0
        )
        assert ff.rollout_percentage == 0.0

    def test_100_rollout_allowed(self):
        ff = FeatureFlag(
            name="f", enabled=True, status=FeatureStatus.ENABLED,
            type=FeatureType.CORE, rollout_percentage=100.0
        )
        assert ff.rollout_percentage == 100.0

    def test_default_rollout_percentage(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.rollout_percentage == 100.0

    def test_default_rollout_strategy(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.rollout_strategy == RolloutStrategy.ALL

    def test_expires_date_defaults_none(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.expires_date is None

    def test_dependencies_defaults_empty(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.dependencies == []

    def test_enabled_users_defaults_empty(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.enabled_users == []


class TestFeatureFlagIsExpired:
    def _flag(self, expires=None):
        return FeatureFlag(
            name="f", enabled=True, status=FeatureStatus.ENABLED,
            type=FeatureType.CORE, expires_date=expires
        )

    def test_no_expiry_not_expired(self):
        assert self._flag().is_expired() is False

    def test_future_expiry_not_expired(self):
        assert self._flag(expires=future_date()).is_expired() is False

    def test_past_expiry_is_expired(self):
        assert self._flag(expires=past_date()).is_expired() is True


class TestFeatureFlagIsEnabledForUser:
    def _flag(self, **kwargs):
        defaults = {
            "name": "f", "enabled": True,
            "status": FeatureStatus.ENABLED, "type": FeatureType.CORE
        }
        defaults.update(kwargs)
        return FeatureFlag(**defaults)

    def test_disabled_flag_returns_false(self):
        ff = self._flag(enabled=False)
        assert ff.is_enabled_for_user("user1") is False

    def test_expired_flag_returns_false(self):
        ff = self._flag(expires_date=past_date())
        assert ff.is_enabled_for_user("user1") is False

    def test_all_strategy_returns_true(self):
        ff = self._flag(rollout_strategy=RolloutStrategy.ALL)
        assert ff.is_enabled_for_user("user1") is True

    def test_user_list_strategy_in_list(self):
        ff = self._flag(
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["user1", "user2"]
        )
        assert ff.is_enabled_for_user("user1") is True

    def test_user_list_strategy_not_in_list(self):
        ff = self._flag(
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["user2"]
        )
        assert ff.is_enabled_for_user("user1") is False

    def test_percentage_strategy_0_returns_false(self):
        ff = self._flag(
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=0.0
        )
        # No user should be in 0%
        results = [ff.is_enabled_for_user(f"user_{i}") for i in range(20)]
        assert all(r is False for r in results)

    def test_percentage_strategy_100_returns_true(self):
        ff = self._flag(
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=100.0
        )
        results = [ff.is_enabled_for_user(f"user_{i}") for i in range(20)]
        assert all(r is True for r in results)

    def test_percentage_strategy_deterministic(self):
        ff = self._flag(
            rollout_strategy=RolloutStrategy.PERCENTAGE,
            rollout_percentage=50.0
        )
        # Same user should always get same result
        result1 = ff.is_enabled_for_user("stable_user")
        result2 = ff.is_enabled_for_user("stable_user")
        assert result1 == result2

    def test_canary_strategy_falls_through_to_enabled(self):
        ff = self._flag(rollout_strategy=RolloutStrategy.CANARY)
        # Falls through to `return self.enabled`
        assert ff.is_enabled_for_user("user1") is True

    def test_gradual_strategy_falls_through_to_enabled(self):
        ff = self._flag(rollout_strategy=RolloutStrategy.GRADUAL)
        assert ff.is_enabled_for_user("user1") is True


class TestFeatureFlagToDict:
    def test_to_dict_returns_dict(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        d = ff.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_name(self):
        ff = FeatureFlag(name="myfeature", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.to_dict()["name"] == "myfeature"

    def test_to_dict_status_is_string(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.to_dict()["status"] == "enabled"

    def test_to_dict_type_is_string(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.STRATEGY)
        assert ff.to_dict()["type"] == "strategy"

    def test_to_dict_rollout_strategy_is_string(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.to_dict()["rollout_strategy"] == "all"

    def test_to_dict_expires_none_when_not_set(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        assert ff.to_dict()["expires_date"] is None

    def test_to_dict_expires_isoformat_when_set(self):
        exp = future_date()
        ff = FeatureFlag(
            name="f", enabled=True, status=FeatureStatus.ENABLED,
            type=FeatureType.CORE, expires_date=exp
        )
        assert ff.to_dict()["expires_date"] == exp.isoformat()

    def test_to_dict_has_all_keys(self):
        ff = FeatureFlag(name="f", enabled=True, status=FeatureStatus.ENABLED, type=FeatureType.CORE)
        d = ff.to_dict()
        for key in ["name", "enabled", "status", "type", "description",
                    "rollout_percentage", "rollout_strategy", "enabled_users",
                    "environments", "created_date", "modified_date", "expires_date",
                    "dependencies", "metadata"]:
            assert key in d


# ==============================================================================
# U11 — FeatureFlags CLASS
# ==============================================================================

class TestFeatureFlagsInit:
    def test_init_creates_instance(self, tmp_path):
        ff = make_flags(tmp_path)
        assert ff is not None

    def test_init_loads_default_features(self, tmp_path):
        ff = make_flags(tmp_path)
        assert len(ff.features) > 0

    def test_init_creates_config_file(self, tmp_path):
        config_file = str(tmp_path / "new_flags.json")
        FeatureFlags(config_file=config_file)
        assert os.path.exists(config_file)

    def test_init_loads_from_existing_file(self, tmp_path):
        data = {
            "custom_feature": {
                "enabled": True,
                "status": "enabled",
                "type": "core",
                "description": "Custom",
                "rollout_percentage": 100.0,
                "rollout_strategy": "all",
                "enabled_users": [],
                "environments": ["all"],
                "dependencies": [],
                "metadata": {}
            }
        }
        ff = make_flags_from_json(tmp_path, data)
        assert "custom_feature" in ff.features

    def test_environment_attribute_set(self, tmp_path):
        with patch.dict(os.environ, {"SPYDER_ENV": "production"}):
            ff = FeatureFlags(config_file=str(tmp_path / "f.json"))
            assert ff.environment == "production"

    def test_user_id_attribute_set(self, tmp_path):
        with patch.dict(os.environ, {"SPYDER_USER_ID": "alice"}):
            ff = FeatureFlags(config_file=str(tmp_path / "f.json"))
            assert ff.user_id == "alice"

    def test_default_user_id(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SPYDER_USER_ID", None)
            ff = FeatureFlags(config_file=str(tmp_path / "f.json"))
            assert ff.user_id == "default"


class TestFeatureFlagsIsEnabled:
    def test_unknown_feature_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        assert ff.is_enabled("nonexistent_feature") is False

    def test_known_enabled_feature_returns_true(self, tmp_path):
        ff = make_flags(tmp_path)
        # advanced_risk_management is True in DEFAULT_FEATURES, but dev env may override
        ff.features["advanced_risk_management"].enabled = True
        assert ff.is_enabled("advanced_risk_management") is True

    def test_disabled_feature_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("test_disabled", enabled=False, description="x")
        assert ff.is_enabled("test_disabled") is False

    def test_exception_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        # Force an exception by breaking features dict
        with patch.object(ff, "_refresh_cache_if_needed", side_effect=RuntimeError("boom")):
            # Should catch and return False
            result = ff.is_enabled("advanced_risk_management")
            assert result is False

    def test_check_feature_enabled_alias(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.enable_feature("portfolio_optimization", save=False)
        assert ff.check_feature_enabled("portfolio_optimization") == ff.is_enabled("portfolio_optimization")

    def test_environment_restriction(self, tmp_path):
        config_file = str(tmp_path / "f.json")
        with patch.dict(os.environ, {"SPYDER_ENV": "production"}):
            ff = FeatureFlags(config_file=config_file)
        # Create feature only for development environment
        ff.features["dev_only"] = FeatureFlag(
            name="dev_only", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.EXPERIMENTAL,
            environments=["development"]
        )
        ff.environment = "production"
        assert ff.is_enabled("dev_only") is False

    def test_environment_all_allows_any(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["universal"] = FeatureFlag(
            name="universal", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE,
            environments=["all"]
        )
        assert ff.is_enabled("universal") is True

    def test_dependency_disabled_prevents_enable(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["base"] = FeatureFlag(
            name="base", enabled=False,
            status=FeatureStatus.DISABLED, type=FeatureType.CORE
        )
        ff.features["derived"] = FeatureFlag(
            name="derived", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE,
            dependencies=["base"]
        )
        assert ff.is_enabled("derived") is False

    def test_dependency_enabled_allows_enable(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["base"] = FeatureFlag(
            name="base", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE
        )
        ff.features["derived"] = FeatureFlag(
            name="derived", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE,
            dependencies=["base"]
        )
        assert ff.is_enabled("derived") is True

    def test_with_user_id(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["user_feat"] = FeatureFlag(
            name="user_feat", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE,
            rollout_strategy=RolloutStrategy.USER_LIST,
            enabled_users=["alice"]
        )
        assert ff.is_enabled("user_feat", "alice") is True
        assert ff.is_enabled("user_feat", "bob") is False


class TestFeatureFlagsGetEnabledFeatures:
    def test_returns_list(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.get_enabled_features()
        assert isinstance(result, list)

    def test_enabled_features_subset_of_all(self, tmp_path):
        ff = make_flags(tmp_path)
        enabled = ff.get_enabled_features()
        for name in enabled:
            assert name in ff.features

    def test_with_user_id(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.get_enabled_features(user_id="alice")
        assert isinstance(result, list)


class TestFeatureFlagsEnableDisable:
    def test_enable_existing_feature(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.disable_feature("iron_condor_automation", save=False)
        ff.enable_feature("iron_condor_automation", save=False)
        assert ff.is_enabled("iron_condor_automation") is True

    def test_disable_existing_feature(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.enable_feature("iron_condor_automation", save=False)
        result = ff.disable_feature("iron_condor_automation", save=False)
        assert result is True
        assert ff.features["iron_condor_automation"].enabled is False

    def test_enable_nonexistent_creates_feature(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.enable_feature("brand_new_feature", save=False)
        assert "brand_new_feature" in ff.features
        assert ff.features["brand_new_feature"].enabled is True

    def test_disable_nonexistent_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.disable_feature("nonexistent_xyz", save=False)
        assert result is False

    def test_enable_returns_true(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.enable_feature("test_en", save=False)
        assert result is True

    def test_enable_updates_modified_date(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["test_dt"] = FeatureFlag(
            name="test_dt", enabled=False,
            status=FeatureStatus.DISABLED, type=FeatureType.CORE,
            modified_date=datetime(2020, 1, 1)
        )
        old_date = ff.features["test_dt"].modified_date
        ff.enable_feature("test_dt", save=False)
        assert ff.features["test_dt"].modified_date > old_date

    def test_disable_updates_modified_date(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.features["test_dt2"] = FeatureFlag(
            name="test_dt2", enabled=True,
            status=FeatureStatus.ENABLED, type=FeatureType.CORE,
            modified_date=datetime(2020, 1, 1)
        )
        old_date = ff.features["test_dt2"].modified_date
        ff.disable_feature("test_dt2", save=False)
        assert ff.features["test_dt2"].modified_date > old_date


class TestFeatureFlagsSetRollout:
    def test_set_valid_rollout(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("iron_condor_automation", 50.0, save=False)
        assert result is True
        assert ff.features["iron_condor_automation"].rollout_percentage == 50.0

    def test_set_rollout_sets_strategy(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.set_rollout_percentage("iron_condor_automation", 25.0, save=False)
        assert ff.features["iron_condor_automation"].rollout_strategy == RolloutStrategy.PERCENTAGE

    def test_set_rollout_invalid_percentage(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("iron_condor_automation", 150.0, save=False)
        assert result is False

    def test_set_rollout_negative_percentage(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("iron_condor_automation", -5.0, save=False)
        assert result is False

    def test_set_rollout_nonexistent_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("nonexistent", 50.0, save=False)
        assert result is False

    def test_set_rollout_zero(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("iron_condor_automation", 0.0, save=False)
        assert result is True

    def test_set_rollout_100(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.set_rollout_percentage("iron_condor_automation", 100.0, save=False)
        assert result is True


class TestFeatureFlagsCreateFeature:
    def test_create_new_feature(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.create_feature("new_feature", enabled=False)
        assert result is True
        assert "new_feature" in ff.features

    def test_create_already_exists_returns_false(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("dup_feature", enabled=False)
        result = ff.create_feature("dup_feature", enabled=False)
        assert result is False

    def test_create_with_enabled_true(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("enabled_feat", enabled=True)
        assert ff.features["enabled_feat"].enabled is True

    def test_create_with_description(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("desc_feat", description="My description")
        assert ff.features["desc_feat"].description == "My description"

    def test_create_with_custom_type(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("strategy_feat", feature_type=FeatureType.STRATEGY)
        assert ff.features["strategy_feat"].type == FeatureType.STRATEGY

    def test_create_default_type_experimental(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("exp_feat")
        assert ff.features["exp_feat"].type == FeatureType.EXPERIMENTAL


class TestFeatureFlagsGetInfo:
    def test_get_info_known_feature(self, tmp_path):
        ff = make_flags(tmp_path)
        info = ff.get_feature_info("advanced_risk_management")
        assert info is not None
        assert isinstance(info, dict)

    def test_get_info_unknown_returns_none(self, tmp_path):
        ff = make_flags(tmp_path)
        assert ff.get_feature_info("bogus") is None

    def test_get_info_has_name_key(self, tmp_path):
        ff = make_flags(tmp_path)
        info = ff.get_feature_info("advanced_risk_management")
        assert info["name"] == "advanced_risk_management"


class TestFeatureFlagsListFeatures:
    def test_list_returns_list(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.list_features()
        assert isinstance(result, list)

    def test_list_sorted_by_name(self, tmp_path):
        ff = make_flags(tmp_path)
        result = ff.list_features()
        names = [f["name"] for f in result]
        assert names == sorted(names)

    def test_list_filter_by_type(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.create_feature("ui_feat", feature_type=FeatureType.UI)
        result = ff.list_features(feature_type=FeatureType.UI)
        for f in result:
            assert f["type"] == "ui"

    def test_list_no_filter_includes_all(self, tmp_path):
        ff = make_flags(tmp_path)
        all_feats = ff.list_features()
        assert len(all_feats) == len(ff.features)


class TestFeatureFlagsRefreshCache:
    def test_refresh_not_triggered_when_fresh(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.cache_timestamp = float('inf')  # Far future
        with patch.object(ff, "_load_configuration") as mock_load:
            ff._refresh_cache_if_needed()
            mock_load.assert_not_called()

    def test_refresh_triggered_when_stale(self, tmp_path):
        ff = make_flags(tmp_path)
        ff.cache_timestamp = 0.0  # Very old
        with patch.object(ff, "_load_configuration") as mock_load:
            ff._refresh_cache_if_needed()
            mock_load.assert_called_once()


class TestFeatureFlagsLoadBadJson:
    def test_bad_json_uses_defaults(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{invalid json}")
        ff = FeatureFlags(config_file=str(config_file))
        # Should fall back to defaults without crashing
        assert isinstance(ff.features, dict)


class TestFeatureFlagsApplyEnvironmentOverrides:
    def test_testing_env_all_features_enabled(self, tmp_path):
        config_file = str(tmp_path / "f.json")
        with patch.dict(os.environ, {"SPYDER_ENV": "testing"}):
            ff = FeatureFlags(config_file=config_file)
        # all_features override → everything should be enabled
        for feature in ff.features.values():
            assert feature.enabled is True

    def test_development_env_applies_overrides(self, tmp_path):
        ff = make_flags(tmp_path, env="development")
        # development should have ml_strategy_selection overridden to True
        if "ml_strategy_selection" in ff.features:
            assert ff.features["ml_strategy_selection"].enabled is True

    def test_production_env_disables_experimental(self, tmp_path):
        config_file = str(tmp_path / "f.json")
        with patch.dict(os.environ, {"SPYDER_ENV": "production"}):
            ff = FeatureFlags(config_file=config_file)
        # experimental_features key → all EXPERIMENTAL type disabled
        for feature in ff.features.values():
            if feature.type == FeatureType.EXPERIMENTAL:
                assert feature.enabled is False


# ==============================================================================
# U11 — MODULE FUNCTIONS
# ==============================================================================

class TestU11ModuleFunctions:
    _U11_MOD_KEY = "Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags"

    def setup_method(self):
        """Reset singleton before each test."""
        sys.modules[self._U11_MOD_KEY]._feature_flags_instance = None

    def teardown_method(self):
        sys.modules[self._U11_MOD_KEY]._feature_flags_instance = None

    def test_get_feature_flags_returns_instance(self, tmp_path):
        with patch("Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags.FeatureFlags") as MockFF:
            MockFF.return_value = MagicMock()
            instance = get_feature_flags()
            assert instance is not None

    def test_get_feature_flags_singleton(self):
        instance1 = get_feature_flags()
        instance2 = get_feature_flags()
        assert instance1 is instance2

    def test_check_feature_enabled_calls_singleton(self):
        result = check_feature_enabled("nonexistent_xyz")
        assert isinstance(result, bool)

    def test_is_feature_enabled_alias(self):
        r1 = is_feature_enabled("nonexistent_xyz")
        r2 = check_feature_enabled("nonexistent_xyz")
        assert r1 == r2

    def test_is_spyderx_enabled_alias(self):
        result = is_spyderx_enabled("nonexistent_xyz")
        assert isinstance(result, bool)

    def test_enable_feature_module_function(self):
        instance = get_feature_flags()
        with patch.object(instance, "enable_feature", return_value=True) as mock_enable:
            enable_feature("some_feature")
            mock_enable.assert_called_once_with("some_feature")

    def test_disable_feature_module_function(self):
        instance = get_feature_flags()
        with patch.object(instance, "disable_feature", return_value=True) as mock_disable:
            disable_feature("some_feature")
            mock_disable.assert_called_once_with("some_feature")


# ==============================================================================
# U09 — MODULE-LEVEL CONSTANTS
# ==============================================================================

class TestU09Constants:
    def test_market_data_fields_list(self):
        assert isinstance(MARKET_DATA_FIELDS, list)
        assert "bid" in MARKET_DATA_FIELDS
        assert "ask" in MARKET_DATA_FIELDS
        assert "last" in MARKET_DATA_FIELDS

    def test_option_rights(self):
        assert "CALL" in OPTION_RIGHTS
        assert "PUT" in OPTION_RIGHTS

    def test_option_styles(self):
        assert "AMERICAN" in OPTION_STYLES
        assert "EUROPEAN" in OPTION_STYLES

    def test_order_types(self):
        assert "MKT" in ORDER_TYPES
        assert "LMT" in ORDER_TYPES

    def test_order_actions(self):
        assert "BUY" in ORDER_ACTIONS
        assert "SELL" in ORDER_ACTIONS

    def test_order_status(self):
        assert "Filled" in ORDER_STATUS
        assert "Submitted" in ORDER_STATUS


# ==============================================================================
# U09 — ENUMS
# ==============================================================================

class TestU09Enums:
    def test_option_right_call(self):
        assert OptionRight.CALL.value == "CALL"

    def test_option_right_put(self):
        assert OptionRight.PUT.value == "PUT"

    def test_option_style_american(self):
        assert OptionStyle.AMERICAN.value == "AMERICAN"

    def test_option_style_european(self):
        assert OptionStyle.EUROPEAN.value == "EUROPEAN"

    def test_order_type_market(self):
        assert OrderType.MARKET.value == "MKT"

    def test_order_type_limit(self):
        assert OrderType.LIMIT.value == "LMT"

    def test_order_type_stop(self):
        assert OrderType.STOP.value == "STP"

    def test_order_type_stop_limit(self):
        assert OrderType.STOP_LIMIT.value == "STP_LMT"

    def test_order_type_trailing_stop(self):
        assert OrderType.TRAILING_STOP.value == "TRAIL"

    def test_order_type_trailing_limit(self):
        assert OrderType.TRAILING_LIMIT.value == "TRAIL_LIMIT"

    def test_order_action_buy(self):
        assert OrderAction.BUY.value == "BUY"

    def test_order_action_sell(self):
        assert OrderAction.SELL.value == "SELL"

    def test_order_status_submitted(self):
        assert OrderStatus.SUBMITTED.value == "Submitted"

    def test_order_status_filled(self):
        assert OrderStatus.FILLED.value == "Filled"

    def test_order_status_cancelled(self):
        assert OrderStatus.CANCELLED.value == "Cancelled"

    def test_order_status_pending_submit(self):
        assert OrderStatus.PENDING_SUBMIT.value == "PendingSubmit"

    def test_order_status_pending_cancel(self):
        assert OrderStatus.PENDING_CANCEL.value == "PendingCancel"

    def test_order_status_inactive(self):
        assert OrderStatus.INACTIVE.value == "Inactive"

    def test_order_status_pending_modify(self):
        assert OrderStatus.PENDING_MODIFY.value == "PendingModify"

    def test_position_side_long(self):
        assert PositionSide.LONG.value == "LONG"

    def test_position_side_short(self):
        assert PositionSide.SHORT.value == "SHORT"

    def test_position_side_flat(self):
        assert PositionSide.FLAT.value == "FLAT"

    def test_data_quality_real_time(self):
        assert DataQuality.REAL_TIME.value == "real_time"

    def test_data_quality_delayed(self):
        assert DataQuality.DELAYED.value == "delayed"

    def test_data_quality_frozen(self):
        assert DataQuality.FROZEN.value == "frozen"

    def test_data_quality_halted(self):
        assert DataQuality.HALTED.value == "halted"

    def test_data_quality_unknown(self):
        assert DataQuality.UNKNOWN.value == "unknown"

    def test_market_data_type_quote(self):
        assert MarketDataType.QUOTE.value == "quote"

    def test_market_data_type_trade(self):
        assert MarketDataType.TRADE.value == "trade"

    def test_market_data_type_bar(self):
        assert MarketDataType.BAR.value == "bar"

    def test_market_data_type_options_chain(self):
        assert MarketDataType.OPTIONS_CHAIN.value == "options_chain"

    def test_market_data_type_greeks(self):
        assert MarketDataType.GREEKS.value == "greeks"

    def test_market_data_type_unknown(self):
        assert MarketDataType.UNKNOWN.value == "unknown"


# ==============================================================================
# U09 — MarketData
# ==============================================================================

class TestMarketData:
    def test_basic_creation(self):
        md = MarketData(symbol="SPY")
        assert md.symbol == "SPY"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError):
            MarketData(symbol="")

    def test_default_bid_ask_zero(self):
        md = MarketData(symbol="SPY")
        assert md.bid == 0.0
        assert md.ask == 0.0

    def test_default_quality(self):
        md = MarketData(symbol="SPY")
        assert md.quality == DataQuality.UNKNOWN

    def test_mid_price_with_bid_ask(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.2)
        assert md.mid_price == pytest.approx(450.1)

    def test_mid_price_falls_back_to_last(self):
        md = MarketData(symbol="SPY", last=449.5)
        assert md.mid_price == 449.5

    def test_mid_price_zero_bid_falls_back(self):
        md = MarketData(symbol="SPY", bid=0.0, ask=451.0, last=450.0)
        assert md.mid_price == 450.0

    def test_spread_with_bid_ask(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.2)
        assert md.spread == pytest.approx(0.2)

    def test_spread_zero_when_no_bid_ask(self):
        md = MarketData(symbol="SPY")
        assert md.spread == 0.0

    def test_spread_percent_positive(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.2)
        expected = (0.2 / 450.1) * 100.0
        assert md.spread_percent == pytest.approx(expected, rel=1e-4)

    def test_spread_percent_zero_when_no_spread(self):
        md = MarketData(symbol="SPY")
        assert md.spread_percent == 0.0

    def test_spread_percent_zero_when_mid_zero(self):
        md = MarketData(symbol="SPY", bid=0.0, ask=0.0, last=0.0)
        assert md.spread_percent == 0.0

    def test_to_dict_contains_symbol(self):
        md = MarketData(symbol="SPY")
        assert md.to_dict()["symbol"] == "SPY"

    def test_to_dict_contains_mid_price(self):
        md = MarketData(symbol="SPY", bid=450.0, ask=450.2)
        assert "mid_price" in md.to_dict()

    def test_to_dict_quality_is_string(self):
        md = MarketData(symbol="SPY", quality=DataQuality.REAL_TIME)
        assert md.to_dict()["quality"] == "real_time"

    def test_to_dict_timestamp_isoformat(self):
        md = MarketData(symbol="SPY")
        ts = md.to_dict()["timestamp"]
        # Should be a valid ISO format string
        datetime.fromisoformat(ts)

    def test_full_construction(self):
        md = MarketData(
            symbol="SPY", bid=449.9, ask=450.1, last=450.0,
            volume=10000, bid_size=100, ask_size=200, last_size=50,
            open=448.0, high=451.0, low=447.0, close=450.0,
            quality=DataQuality.REAL_TIME
        )
        assert md.volume == 10000
        assert md.high == 451.0


# ==============================================================================
# U09 — OptionContract
# ==============================================================================

class TestOptionContract:
    def _contract(self, **kwargs):
        defaults = {
            "symbol": "SPY_OPT",
            "underlying": "SPY",
            "expiry": date.today() + timedelta(days=30),
            "strike": 450.0,
            "right": OptionRight.CALL
        }
        defaults.update(kwargs)
        return OptionContract(**defaults)

    def test_basic_creation(self):
        c = self._contract()
        assert c.underlying == "SPY"
        assert c.strike == 450.0

    def test_negative_strike_raises(self):
        with pytest.raises(ValueError):
            self._contract(strike=-1.0)

    def test_zero_strike_raises(self):
        with pytest.raises(ValueError):
            self._contract(strike=0.0)

    def test_zero_multiplier_raises(self):
        with pytest.raises(ValueError):
            self._contract(multiplier=0)

    def test_negative_multiplier_raises(self):
        with pytest.raises(ValueError):
            self._contract(multiplier=-1)

    def test_default_style_american(self):
        c = self._contract()
        assert c.style == OptionStyle.AMERICAN

    def test_default_multiplier(self):
        c = self._contract()
        assert c.multiplier == 100

    def test_default_currency(self):
        c = self._contract()
        assert c.currency == "USD"

    def test_option_symbol_call(self):
        expiry = date(2025, 12, 20)
        c = self._contract(underlying="SPY", expiry=expiry, strike=450.0, right=OptionRight.CALL)
        sym = c.option_symbol
        assert "SPY" in sym
        assert "C" in sym

    def test_option_symbol_put(self):
        expiry = date(2025, 12, 20)
        c = self._contract(underlying="SPY", expiry=expiry, strike=450.0, right=OptionRight.PUT)
        sym = c.option_symbol
        assert "P" in sym

    def test_days_to_expiry_positive(self):
        c = self._contract(expiry=date.today() + timedelta(days=10))
        assert c.days_to_expiry == 10

    def test_days_to_expiry_past(self):
        c = self._contract(expiry=date.today() - timedelta(days=5))
        assert c.days_to_expiry == -5

    def test_to_dict_has_keys(self):
        c = self._contract()
        d = c.to_dict()
        for key in ["symbol", "underlying", "expiry", "strike", "right", "style",
                    "multiplier", "exchange", "currency", "option_symbol", "days_to_expiry"]:
            assert key in d

    def test_to_dict_right_is_string(self):
        c = self._contract(right=OptionRight.PUT)
        assert c.to_dict()["right"] == "PUT"

    def test_to_dict_expiry_is_isoformat(self):
        c = self._contract()
        d = c.to_dict()
        date.fromisoformat(d["expiry"])


# ==============================================================================
# U09 — OrderData
# ==============================================================================

class TestOrderData:
    def _order(self, **kwargs):
        defaults = {
            "order_id": 1, "symbol": "SPY",
            "action": OrderAction.BUY, "order_type": OrderType.LIMIT,
            "quantity": 10, "price": 450.0
        }
        defaults.update(kwargs)
        return OrderData(**defaults)

    def test_basic_creation(self):
        o = self._order()
        assert o.symbol == "SPY"
        assert o.quantity == 10

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError):
            self._order(quantity=0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            self._order(quantity=-5)

    def test_is_filled_false_initially(self):
        o = self._order()
        assert o.is_filled is False

    def test_is_filled_true_when_all_filled(self):
        o = self._order(quantity=10, filled_quantity=10)
        assert o.is_filled is True

    def test_is_active_submitted(self):
        o = self._order(status=OrderStatus.SUBMITTED)
        assert o.is_active is True

    def test_is_active_filled_false(self):
        o = self._order(status=OrderStatus.FILLED)
        assert o.is_active is False

    def test_is_active_cancelled_false(self):
        o = self._order(status=OrderStatus.CANCELLED)
        assert o.is_active is False

    def test_is_active_pending_submit(self):
        o = self._order(status=OrderStatus.PENDING_SUBMIT)
        assert o.is_active is True

    def test_fill_percentage_zero(self):
        o = self._order(quantity=10, filled_quantity=0)
        assert o.fill_percentage == 0.0

    def test_fill_percentage_50(self):
        o = self._order(quantity=10, filled_quantity=5)
        assert o.fill_percentage == 50.0

    def test_fill_percentage_100(self):
        o = self._order(quantity=10, filled_quantity=10)
        assert o.fill_percentage == 100.0

    def test_remaining_quantity_calculated(self):
        o = self._order(quantity=10, filled_quantity=3)
        assert o.remaining_quantity == 7

    def test_to_dict_has_keys(self):
        o = self._order()
        d = o.to_dict()
        for key in ["order_id", "symbol", "action", "order_type", "quantity",
                    "price", "status", "filled_quantity", "remaining_quantity",
                    "avg_fill_price", "commission", "timestamp", "is_filled",
                    "is_active", "fill_percentage"]:
            assert key in d

    def test_to_dict_action_is_string(self):
        o = self._order(action=OrderAction.SELL)
        assert o.to_dict()["action"] == "SELL"

    def test_to_dict_order_type_is_string(self):
        o = self._order(order_type=OrderType.MARKET)
        assert o.to_dict()["order_type"] == "MKT"


# ==============================================================================
# U09 — Position
# ==============================================================================

class TestPosition:
    def test_basic_creation(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0)
        assert p.symbol == "SPY"
        assert p.quantity == 100

    def test_long_side(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0)
        assert p.side == PositionSide.LONG

    def test_short_side(self):
        p = Position(symbol="SPY", quantity=-100, avg_cost=445.0)
        assert p.side == PositionSide.SHORT

    def test_flat_side(self):
        p = Position(symbol="SPY", quantity=0, avg_cost=445.0)
        assert p.side == PositionSide.FLAT

    def test_total_pnl(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0)
        p.realized_pnl = 100.0
        p.unrealized_pnl = 50.0
        assert p.total_pnl == 150.0

    def test_update_market_values_sets_market_value(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=450.0)
        assert p.market_value == pytest.approx(45000.0)

    def test_update_market_values_sets_unrealized_pnl(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=450.0)
        assert p.unrealized_pnl == pytest.approx(500.0)

    def test_update_market_values_no_price(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0, market_price=0.0)
        assert p.market_value == 0.0

    def test_update_market_values_short(self):
        p = Position(symbol="SPY", quantity=-100, avg_cost=445.0, market_price=440.0)
        assert p.unrealized_pnl == pytest.approx(500.0)  # (440-445)*(-100)=500

    def test_to_dict_has_keys(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0)
        d = p.to_dict()
        for key in ["symbol", "quantity", "avg_cost", "market_price", "market_value",
                    "unrealized_pnl", "realized_pnl", "total_pnl", "side", "timestamp"]:
            assert key in d

    def test_to_dict_side_is_string(self):
        p = Position(symbol="SPY", quantity=100, avg_cost=445.0)
        assert p.to_dict()["side"] == "LONG"


# ==============================================================================
# U09 — GreeksData
# ==============================================================================

class TestGreeksData:
    def test_basic_creation(self):
        g = GreeksData(symbol="SPY_C450")
        assert g.symbol == "SPY_C450"

    def test_default_values_zero(self):
        g = GreeksData(symbol="SPY_C450")
        assert g.delta == 0.0
        assert g.gamma == 0.0
        assert g.theta == 0.0
        assert g.vega == 0.0
        assert g.rho == 0.0

    def test_to_dict_keys(self):
        g = GreeksData(symbol="SPY_C450", delta=0.5, gamma=0.02, theta=-0.1, vega=0.3)
        d = g.to_dict()
        for key in ["symbol", "delta", "gamma", "theta", "vega", "rho",
                    "implied_volatility", "underlying_price", "timestamp"]:
            assert key in d

    def test_to_dict_values(self):
        g = GreeksData(symbol="SPY_C450", delta=0.5)
        assert g.to_dict()["delta"] == 0.5


# ==============================================================================
# U09 — TradeExecution
# ==============================================================================

class TestTradeExecution:
    def _exec(self, **kwargs):
        defaults = {
            "execution_id": "exec_001",
            "order_id": 1,
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 100,
            "price": 450.0,
            "commission": 1.5,
            "timestamp": datetime.now()
        }
        defaults.update(kwargs)
        return TradeExecution(**defaults)

    def test_basic_creation(self):
        e = self._exec()
        assert e.execution_id == "exec_001"
        assert e.price == 450.0

    def test_notional_value_buy(self):
        e = self._exec(quantity=100, price=450.0)
        assert e.notional_value == pytest.approx(45000.0)

    def test_notional_value_absolute(self):
        e = self._exec(quantity=-100, price=450.0)
        assert e.notional_value == pytest.approx(45000.0)

    def test_to_dict_has_keys(self):
        e = self._exec()
        d = e.to_dict()
        for key in ["execution_id", "order_id", "symbol", "side", "quantity",
                    "price", "commission", "timestamp", "exchange", "notional_value"]:
            assert key in d

    def test_default_exchange_empty(self):
        e = self._exec()
        assert e.exchange == ""


# ==============================================================================
# U09 — OptionData
# ==============================================================================

class TestOptionData:
    def test_basic_creation(self):
        od = OptionData(
            symbol="SPY_C450",
            expiration=datetime(2025, 12, 20),
            strike=450.0,
            option_type="call"
        )
        assert od.symbol == "SPY_C450"
        assert od.option_type == "call"

    def test_default_bid_zero(self):
        od = OptionData(
            symbol="SPY_C450",
            expiration=datetime(2025, 12, 20),
            strike=450.0,
            option_type="call"
        )
        assert od.bid == 0.0

    def test_full_construction(self):
        od = OptionData(
            symbol="SPY_P440",
            expiration=datetime(2025, 12, 20),
            strike=440.0,
            option_type="put",
            bid=2.0, ask=2.1, last=2.05,
            volume=5000, open_interest=10000,
            implied_volatility=0.20,
            delta=-0.3, gamma=0.05, theta=-0.05, vega=0.15
        )
        assert od.implied_volatility == 0.20
        assert od.delta == -0.3


# ==============================================================================
# U09 — PositionData
# ==============================================================================

class TestPositionData:
    def test_basic_creation(self):
        pd_obj = PositionData()
        assert pd_obj.symbol == ""
        assert pd_obj.quantity == 0
        assert pd_obj.entry_price == 0.0
        assert pd_obj.current_price == 0.0
        assert pd_obj.pnl == 0.0

    def test_set_attributes(self):
        pd_obj = PositionData()
        pd_obj.symbol = "SPY"
        pd_obj.quantity = 100
        pd_obj.entry_price = 445.0
        assert pd_obj.symbol == "SPY"
        assert pd_obj.quantity == 100


# ==============================================================================
# U09 — SpyderDataTypes class
# ==============================================================================

class TestSpyderDataTypes:
    def setup_method(self):
        self.dt = SpyderDataTypes()

    def test_create_market_data_basic(self):
        md = self.dt.create_market_data("SPY")
        assert md.symbol == "SPY"
        assert isinstance(md, MarketData)

    def test_create_market_data_with_prices(self):
        md = self.dt.create_market_data("SPY", bid=449.9, ask=450.1, last=450.0, volume=5000)
        assert md.bid == 449.9
        assert md.volume == 5000

    def test_create_option_contract_call(self):
        future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        oc = self.dt.create_option_contract("SPY", future, 450.0, "CALL")
        assert isinstance(oc, OptionContract)
        assert oc.right == OptionRight.CALL

    def test_create_option_contract_put(self):
        future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        oc = self.dt.create_option_contract("SPY", future, 450.0, "PUT")
        assert oc.right == OptionRight.PUT

    def test_create_option_contract_case_insensitive(self):
        future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        oc = self.dt.create_option_contract("SPY", future, 450.0, "call")
        assert oc.right == OptionRight.CALL

    def test_create_order_buy_limit(self):
        od = self.dt.create_order("SPY", "BUY", "LMT", 10, 450.0)
        assert isinstance(od, OrderData)
        assert od.action == OrderAction.BUY
        assert od.order_type == OrderType.LIMIT

    def test_create_order_sell_market(self):
        od = self.dt.create_order("SPY", "SELL", "MKT", 5)
        assert od.action == OrderAction.SELL
        assert od.order_type == OrderType.MARKET

    def test_create_order_case_insensitive(self):
        od = self.dt.create_order("SPY", "buy", "lmt", 10)
        assert od.action == OrderAction.BUY

    def test_validate_market_data_valid(self):
        md = MarketData(symbol="SPY", bid=449.9, ask=450.1, last=450.0)
        assert self.dt.validate_market_data(md) is True

    def test_validate_market_data_no_bid_ask(self):
        md = MarketData(symbol="SPY")
        assert self.dt.validate_market_data(md) is True

    def test_validate_market_data_negative_bid(self):
        md = MarketData(symbol="SPY", bid=-1.0, ask=450.1)
        assert self.dt.validate_market_data(md) is False

    def test_validate_market_data_bid_gte_ask(self):
        md = MarketData(symbol="SPY", bid=451.0, ask=450.0)
        assert self.dt.validate_market_data(md) is False

    def test_validate_option_contract_valid(self):
        future_date_val = date.today() + timedelta(days=30)
        oc = OptionContract(
            symbol="SPY_OPT", underlying="SPY",
            expiry=future_date_val, strike=450.0, right=OptionRight.CALL
        )
        assert self.dt.validate_option_contract(oc) is True

    def test_validate_option_contract_past_expiry(self):
        past = date.today() - timedelta(days=1)
        oc = OptionContract(
            symbol="SPY_OPT", underlying="SPY",
            expiry=past, strike=450.0, right=OptionRight.CALL
        )
        assert self.dt.validate_option_contract(oc) is False

    def test_validate_option_contract_today_expiry(self):
        today = date.today()
        oc = OptionContract(
            symbol="SPY_OPT", underlying="SPY",
            expiry=today, strike=450.0, right=OptionRight.CALL
        )
        assert self.dt.validate_option_contract(oc) is False

    def test_create_option_invalid_date_raises(self):
        with pytest.raises(Exception):
            self.dt.create_option_contract("SPY", "invalid-date", 450.0, "CALL")

    def test_create_order_invalid_action_raises(self):
        with pytest.raises(Exception):
            self.dt.create_order("SPY", "HOLD", "MKT", 10)


# ==============================================================================
# U09 — MODULE FUNCTIONS
# ==============================================================================

class TestU09ModuleFunctions:
    _U09_MOD_KEY = "Spyder.SpyderU_Utilities.SpyderU09_DataTypes"

    def setup_method(self):
        sys.modules[self._U09_MOD_KEY]._data_types_instance = None

    def teardown_method(self):
        sys.modules[self._U09_MOD_KEY]._data_types_instance = None

    def test_create_market_data_function(self):
        md = create_market_data("SPY", bid=450.0, ask=450.1)
        assert isinstance(md, MarketData)
        assert md.symbol == "SPY"

    def test_create_option_contract_function(self):
        future = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")
        oc = create_option_contract("SPY", future, 450.0, "CALL")
        assert isinstance(oc, OptionContract)

    def test_get_data_types_returns_instance(self):
        instance = get_data_types()
        assert isinstance(instance, SpyderDataTypes)

    def test_get_data_types_singleton(self):
        i1 = get_data_types()
        i2 = get_data_types()
        assert i1 is i2
