#!/usr/bin/env python3
"""Focused regressions for F01 config-manager compatibility."""

from types import SimpleNamespace

from Spyder.SpyderF_Analysis import SpyderF01_Indicators as f01


def test_technical_indicators_defaults_to_a03_singleton(monkeypatch) -> None:
    class _SingletonConfig:
        def get_config(self, key: str, default=None):
            if key != "indicators":
                return default
            return {
                "default_sma_period": 34,
                "cache_ttl_seconds": 45,
            }

        def is_feature_enabled(self, key: str) -> bool:
            return key == "use_talib"

    fake_manager = _SingletonConfig()
    monkeypatch.setattr(f01, "get_config_manager", lambda: fake_manager)

    indicators = f01.TechnicalIndicators(monitor=SimpleNamespace())

    assert indicators.config_manager is fake_manager
    assert indicators.default_sma_period == 34
    assert indicators.cache_ttl_seconds == 45
    assert indicators.use_talib is True
    assert indicators.use_ml_signals is False


def test_technical_indicators_supports_legacy_config_manager_without_flags() -> None:
    class _LegacyConfig:
        def get_config(self, name: str, decrypt: bool = True):
            assert name == "indicators"
            assert decrypt is True
            return {
                "default_rsi_period": 21,
                "performance_threshold_ms": 250,
            }

    indicators = f01.TechnicalIndicators(
        config_manager=_LegacyConfig(),
        monitor=SimpleNamespace(),
    )

    assert indicators.default_rsi_period == 21
    assert indicators.performance_threshold == 250
    assert indicators.use_talib is False
    assert indicators.use_ml_signals is False
