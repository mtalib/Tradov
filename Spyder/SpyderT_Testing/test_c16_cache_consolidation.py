#!/usr/bin/env python3
"""Tests for C16/H03 cache consolidation behavior."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from Spyder.SpyderC_MarketData import SpyderC16_MarketDataCache as c16_module
from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import MarketDataCache


def _build_config(db_path: str, redis_enabled: bool = False) -> dict:
    return {
        "memory": {
            "max_size": 128,
            "ttl_seconds": 5,
            "cleanup_interval": 1,
        },
        "persistence": {
            "enabled": False,
            "db_path": db_path,
            "retention_days": 1,
            "compression": False,
        },
        "redis": {
            "enabled": redis_enabled,
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "ttl_seconds": 10,
        },
        "preload": {
            "enabled": False,
            "symbols": [],
            "lookback_minutes": 1,
        },
    }


def test_c16_uses_h03_for_l1_put_get(tmp_path):
    cache = MarketDataCache(config=_build_config(str(tmp_path / "cache.db")))

    payload = {"last": 500.12, "bid": 500.10, "ask": 500.14, "tier": "HIGH"}
    assert cache.put("SPY", payload) is True

    out = cache.get("SPY")
    assert out is not None
    assert out["last"] == payload["last"]

    stats = cache.get_stats()
    assert stats["mode"] == "local_only"
    assert stats["tier_hits"]["l1"] >= 1

    cache.stop()


def test_c16_reports_degraded_when_redis_requested_but_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(c16_module, "REDIS_AVAILABLE", False)

    cache = MarketDataCache(config=_build_config(str(tmp_path / "cache.db"), redis_enabled=True))
    assert cache.put("SPY", {"last": 501.0, "tier": "HIGH"}) is True

    stats = cache.get_stats()
    assert stats["mode"] == "degraded"
    assert stats["redis_available"] is False
    assert stats["redis_fallbacks"] >= 1

    cache.stop()


def test_c16_range_without_persistence_returns_empty_dataframe(tmp_path):
    cache = MarketDataCache(config=_build_config(str(tmp_path / "cache.db")))
    df = cache.get_range(
        "SPY",
        datetime.now() - timedelta(minutes=1),
        datetime.now(),
    )
    assert isinstance(df, pd.DataFrame)
    assert df.empty
    cache.stop()


def test_c16_invalidate_removes_l1_entry(tmp_path):
    cache = MarketDataCache(config=_build_config(str(tmp_path / "cache.db")))

    cache.put("SPY", {"last": 499.0, "tier": "MEDIUM"})
    assert cache.get("SPY") is not None

    cache.invalidate("SPY")
    assert cache.get("SPY") is None

    cache.stop()
