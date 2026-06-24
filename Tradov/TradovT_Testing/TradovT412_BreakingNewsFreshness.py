from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace


def test_news_freshness_formats_seconds_minutes_and_hours():
    import pytest

    pytest.importorskip("PySide6")

    from Tradov.TradovG_GUI.TradovG60_PairTradingWidgets import _format_news_freshness

    now = datetime.now(UTC)

    assert _format_news_freshness(SimpleNamespace(timestamp=now), now=now) == "age: 0s"
    assert _format_news_freshness(SimpleNamespace(timestamp=now - timedelta(seconds=75)), now=now) == "age: 1m 15s"
    assert _format_news_freshness(SimpleNamespace(timestamp=now - timedelta(hours=2, minutes=7)), now=now) == "age: 2h 07m"
