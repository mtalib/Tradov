#!/usr/bin/env python3
"""Focused regression tests for idempotent C01 shutdown behavior."""

from types import SimpleNamespace


def test_c01_stop_returns_fast_when_already_disconnected():
    from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager, DataFeedStatus

    feed = DataFeedManager.__new__(DataFeedManager)
    feed.is_running = False
    feed.status = DataFeedStatus.DISCONNECTED
    feed.logger = SimpleNamespace(error=lambda *_args, **_kwargs: None)
    feed._stop_event = SimpleNamespace(
        set=lambda: (_ for _ in ()).throw(AssertionError("unexpected stop_event.set"))
    )
    feed._provider = SimpleNamespace(
        disconnect=lambda: (_ for _ in ()).throw(AssertionError("unexpected provider.disconnect"))
    )
    feed.market_cache = SimpleNamespace(
        stop=lambda: (_ for _ in ()).throw(AssertionError("unexpected market_cache.stop"))
    )
    feed._update_thread = SimpleNamespace(
        join=lambda timeout=None: (_ for _ in ()).throw(AssertionError("unexpected update join"))
    )
    feed._monitor_thread = SimpleNamespace(
        join=lambda timeout=None: (_ for _ in ()).throw(AssertionError("unexpected monitor join"))
    )
    feed.executor = SimpleNamespace(
        shutdown=lambda wait=True: (_ for _ in ()).throw(AssertionError("unexpected executor.shutdown"))
    )

    assert feed.stop() is True
