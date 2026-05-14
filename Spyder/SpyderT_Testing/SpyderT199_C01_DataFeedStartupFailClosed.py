#!/usr/bin/env python3
"""Focused tests for C01 startup fail-closed behavior."""

from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import (
    DataFeedManager,
    DataFeedStatus,
    NullProvider,
)


class _StubEventManager:
    def subscribe(self, *args, **kwargs):
        return None

    def publish(self, *args, **kwargs):
        return True

    def emit(self, *args, **kwargs):
        return True


class _StubShutdownCoordinator:
    def register_thread(self, *args, **kwargs):
        return None

    def register_cleanup(self, *args, **kwargs):
        return None


def test_c01_start_fails_when_null_provider_has_no_quote_fallback(monkeypatch):
    feed = DataFeedManager(provider=NullProvider(), event_manager=_StubEventManager())
    monkeypatch.setattr(feed, "_ensure_quote_client", lambda: None)

    started = feed.start()

    assert started is False
    assert feed.status == DataFeedStatus.ERROR
    assert feed.is_running is False


def test_c01_null_provider_quote_fallback_defaults_to_one_second(monkeypatch):
    monkeypatch.delenv("SPYDER_FEED_QUOTE_POLL_INTERVAL_S", raising=False)

    feed = DataFeedManager(provider=NullProvider(), event_manager=_StubEventManager())

    assert feed._quote_poll_interval_s == 1.0


def test_c01_start_skips_settle_delay_when_running_degraded_quote_fallback(monkeypatch):
    feed = DataFeedManager(provider=NullProvider(), event_manager=_StubEventManager())
    feed.market_cache = None

    sleep_calls: list[float] = []

    monkeypatch.setattr(
        "Spyder.SpyderC_MarketData.SpyderC01_DataFeed.get_shutdown_coordinator",
        lambda: _StubShutdownCoordinator(),
    )
    monkeypatch.setattr(feed, "_ensure_quote_client", lambda: object())
    monkeypatch.setattr(feed, "_update_loop", lambda: None)
    monkeypatch.setattr(feed, "_monitor_loop", lambda: None)
    monkeypatch.setattr(
        "Spyder.SpyderC_MarketData.SpyderC01_DataFeed.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    try:
        started = feed.start()
        status_during_start = feed.status
    finally:
        feed.stop()

    assert started is True
    assert status_during_start == DataFeedStatus.DEGRADED
    assert sleep_calls == []


def test_c_series_package_lazy_exports_keep_c01_public_api():
    from Spyder.SpyderC_MarketData import DataFeedManager as PackageDataFeedManager
    from Spyder.SpyderC_MarketData import DataFeedStatus as PackageDataFeedStatus
    from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import (
        DataFeedManager as ModuleDataFeedManager,
    )
    from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import (
        DataFeedStatus as ModuleDataFeedStatus,
    )

    assert PackageDataFeedManager is ModuleDataFeedManager
    assert PackageDataFeedStatus is ModuleDataFeedStatus
