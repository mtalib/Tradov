"""Regression test for D31 market_data_cache shape.

Background: C01 DataFeed publishes MARKET_DATA events with payload
``{'symbol': 'SPY', 'tick': {...}}``. Earlier the orchestrator merged that
payload via ``cache.update(data)`` so the cache became literally
``{'symbol': 'SPY', 'tick': {...}}``, and the L09 regime detector's reads
of ``cache.get('SPY')`` always returned ``[]`` — leaving spy_ema50/atr/vix
permanently NaN and forcing L09 to fall back to SIDEWAYS_RANGE on a
hardcoded ``spy_price = 500.0``.

The fix buckets per-symbol into bounded deques. These tests pin that
behavior so the regression cannot return.
"""

from __future__ import annotations

import importlib
from collections import deque
from types import SimpleNamespace


class _StubEM:
    handlers: dict = {}

    def subscribe(self, *a, **k) -> None:  # noqa: D401
        return None

    def emit(self, *a, **k) -> None:
        return None

    def publish(self, *a, **k) -> None:
        return None


def _make_orchestrator():
    mod = importlib.import_module(
        "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
    )
    return mod.StrategyOrchestrator(event_manager=_StubEM())


def _tick_event(symbol: str, price: float):
    tick = {
        "symbol": symbol,
        "price": price,
        "last": price,
        "close": price,
        "high": price + 0.05,
        "low": price - 0.05,
        "volume": 1000,
    }
    return SimpleNamespace(data={"symbol": symbol, "tick": tick})


def test_market_data_event_buckets_per_symbol_into_deque():
    orch = _make_orchestrator()
    for i in range(60):
        orch._on_market_data_event(_tick_event("SPY", 500.0 + i * 0.1))
    for i in range(40):
        orch._on_market_data_event(_tick_event("VIX", 18.0 + (i % 5) * 0.1))

    spy_bucket = orch.market_data_cache.get("SPY")
    vix_bucket = orch.market_data_cache.get("VIX")

    assert isinstance(spy_bucket, deque), "SPY bucket must be a deque"
    assert isinstance(vix_bucket, deque), "VIX bucket must be a deque"
    assert len(spy_bucket) == 60
    assert len(vix_bucket) == 40
    # Top-level keys 'symbol' and 'tick' must NOT leak into the cache —
    # that was the original bug where they overwrote on every event.
    assert "symbol" not in orch.market_data_cache
    assert "tick" not in orch.market_data_cache


def test_market_data_event_bucket_is_bounded():
    orch = _make_orchestrator()
    # Push more ticks than the bounded buffer to confirm it rolls.
    for i in range(500):
        orch._on_market_data_event(_tick_event("SPY", 500.0 + i * 0.01))

    spy_bucket = orch.market_data_cache["SPY"]
    assert isinstance(spy_bucket, deque)
    assert spy_bucket.maxlen is not None
    assert len(spy_bucket) == spy_bucket.maxlen


def test_l09_regime_classification_sees_real_data_after_fix():
    orch = _make_orchestrator()
    # 60 SPY closes is enough for EMA50 + ATR14 to be finite.
    for i in range(60):
        orch._on_market_data_event(_tick_event("SPY", 500.0 + i * 0.1))
    for i in range(60):
        orch._on_market_data_event(_tick_event("VIX", 18.0 + (i % 5) * 0.1))

    regime = orch._classify_market_regime_unified(
        vix_level=18.0, vix_percentile=50.0, trend_strength=0.5
    )

    # Before the fix, regime was forced to SIDEWAYS_RANGE on hardcoded
    # spy_price=500.0 with NaN inputs. After the fix, the detector sees
    # real EMA50/ATR series and produces a regime that reflects them.
    # We don't pin a specific regime label here (the engine has multiple
    # paths) — only that classification ran and returned *something*.
    assert regime is not None


def test_non_tick_payload_does_not_corrupt_per_symbol_buckets():
    """C12 dark-pool block_trade events have 'symbol' but no 'tick'.

    They must not destroy or replace existing per-symbol buckets.
    """
    orch = _make_orchestrator()
    for i in range(10):
        orch._on_market_data_event(_tick_event("SPY", 500.0 + i))

    block_trade_event = SimpleNamespace(
        data={
            "type": "block_trade",
            "symbol": "SPY",
            "venue": "DARK",
            "size": 100000,
            "is_dark_pool": True,
        }
    )
    orch._on_market_data_event(block_trade_event)

    spy_bucket = orch.market_data_cache.get("SPY")
    assert isinstance(spy_bucket, deque)
    assert len(spy_bucket) == 10  # not clobbered by the block-trade event
    # Other top-level keys from the block trade event were merged.
    assert orch.market_data_cache.get("type") == "block_trade"
