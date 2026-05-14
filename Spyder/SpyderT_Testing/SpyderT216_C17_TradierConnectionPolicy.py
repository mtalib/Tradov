#!/usr/bin/env python3
"""Focused policy regression for C17 Tradier connection defaults."""

from __future__ import annotations

from Spyder.SpyderC_MarketData.SpyderC17_MarketConfigManager import MarketConfigManager


def test_c17_tradier_defaults_omit_sandbox_url():
    manager = MarketConfigManager()

    tradier_defaults = manager.defaults["connections"]["tradier"]

    assert tradier_defaults["base_url"] == "https://api.tradier.com/v1"
    assert "sandbox_url" not in tradier_defaults
