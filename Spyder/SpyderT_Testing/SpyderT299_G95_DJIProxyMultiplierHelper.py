#!/usr/bin/env python3
"""Focused tests for G95 DJI proxy multiplier normalization helper."""

from __future__ import annotations

from Spyder.SpyderG_GUI.SpyderG95_DJIProxyMultiplierHelper import (
    normalize_dji_proxy_multiplier,
)


def test_normalize_dji_proxy_multiplier_returns_positive_float() -> None:
    assert normalize_dji_proxy_multiplier("105.5", 101.2) == 105.5


def test_normalize_dji_proxy_multiplier_rejects_non_positive_values() -> None:
    assert normalize_dji_proxy_multiplier(0, 101.2) == 101.2
    assert normalize_dji_proxy_multiplier(-5, 101.2) == 101.2


def test_normalize_dji_proxy_multiplier_rejects_invalid_values() -> None:
    assert normalize_dji_proxy_multiplier("abc", 101.2) == 101.2
    assert normalize_dji_proxy_multiplier(None, 101.2) == 101.2