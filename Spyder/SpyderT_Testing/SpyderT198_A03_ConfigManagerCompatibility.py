#!/usr/bin/env python3
"""Regression tests for A03 ConfigManager compatibility APIs."""

from Spyder.SpyderA_Core.SpyderA03_Configuration import ConfigManager
from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters


def test_a03_config_manager_supports_legacy_f_series_api(tmp_path):
    config_manager = ConfigManager(
        config_path=tmp_path,
        environment="development",
        auto_reload=False,
    )

    assert config_manager.get_config("entry_filters", {}) == {}
    assert config_manager.is_feature_enabled("adaptive_entry_filters") is False
    assert EntryFilters(config_manager=config_manager) is not None


def test_a03_feature_flag_compatibility_checks_common_locations(tmp_path):
    config_manager = ConfigManager(
        config_path=tmp_path,
        environment="development",
        auto_reload=False,
    )

    config_manager.config_data.setdefault("features", {})["use_talib"] = True
    config_manager.config_data.setdefault("feature_flags", {})["gap_news_correlation"] = "yes"

    assert config_manager.is_feature_enabled("use_talib") is True
    assert config_manager.is_feature_enabled("gap_news_correlation") is True
    assert config_manager.is_feature_enabled("nonexistent_feature") is False
