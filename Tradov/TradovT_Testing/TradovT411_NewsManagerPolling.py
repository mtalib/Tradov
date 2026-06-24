from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace


def test_news_manager_polls_the_configured_provider():
    from Tradov.TradovC_MarketData.TradovC09_NewsManager import NewsManager

    manager = NewsManager()

    calls: list[str] = []

    def record(name: str):
        def _inner(*args, **kwargs):
            calls.append(name)

        return _inner

    manager._fetch_from_finnhub = record("finnhub")  # type: ignore[method-assign]
    manager._fetch_from_newsfilter = record("newsfilter")  # type: ignore[method-assign]
    manager._fetch_from_source = record("rss")  # type: ignore[method-assign]

    manager._finnhub_enabled = True
    manager._newsfilter_enabled = False
    manager._poll_news_sources_once()
    assert calls == ["finnhub"]

    calls.clear()
    manager._finnhub_enabled = False
    manager._newsfilter_enabled = True
    manager._poll_news_sources_once()
    assert calls == ["newsfilter"]

    calls.clear()
    manager._finnhub_enabled = False
    manager._newsfilter_enabled = False
    manager._poll_news_sources_once()
    assert calls == ["rss", "rss", "rss"]


def test_newsfilter_fetch_processes_all_recent_articles(monkeypatch):
    from Tradov.TradovC_MarketData.TradovC09_NewsManager import NewsManager

    manager = NewsManager()
    manager._newsfilter_enabled = True
    manager._finnhub_enabled = False
    manager._newsfilter_sources = ["reuters"]
    manager._newsfilter_last_poll_at = datetime.now(UTC)

    now = datetime.now(UTC)
    articles = [
        {"title": "Headline A", "url": "https://example.com/a", "publishedAt": now.isoformat()},
        {"title": "Headline B", "url": "https://example.com/b", "publishedAt": now.isoformat()},
    ]

    def fake_news_item(article, source_id):
        return SimpleNamespace(
            id=article["url"],
            url=article["url"],
            timestamp=now,
            priority="normal",
        )

    monkeypatch.setattr(manager, "_query_newsfilter_source", lambda *args, **kwargs: articles)
    monkeypatch.setattr(manager, "_create_newsfilter_news_item", fake_news_item)
    monkeypatch.setattr(manager, "_is_recent_news_item", lambda *args, **kwargs: True)
    monkeypatch.setattr(manager, "_analyze_sentiment", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_assess_impact", lambda *args, **kwargs: None)
    monkeypatch.setattr(manager, "_handle_breaking_news", lambda *args, **kwargs: None)

    manager._fetch_from_newsfilter()

    assert set(manager.news_items) == {"https://example.com/a", "https://example.com/b"}
    assert manager.processed_urls == {"https://example.com/a", "https://example.com/b"}
