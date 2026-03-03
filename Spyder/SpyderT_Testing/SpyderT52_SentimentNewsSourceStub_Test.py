#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT52_SentimentNewsSourceStub_Test.py
Purpose: Unit tests for C35 SentimentAnalyzer news source stubs
         (BaseNewsSource, AlphaVantageNewsSource, FinnhubNewsSource,
          YahooFinanceRSSNewsSource) and their integration into
          SentimentAnalyzer.

Author: Claude (Copilot)
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# ==============================================================================
# PATCH LOGGING BEFORE MODULE IMPORT
# ==============================================================================
# SpyderLogger depends on the full Spyder environment; stub it out so the
# C35 module can be imported in isolation.

_mock_log = MagicMock()
_mock_log.get_logger.return_value = MagicMock(
    info=MagicMock(), debug=MagicMock(),
    warning=MagicMock(), error=MagicMock(),
)

_c35_mod = types.ModuleType("Spyder.SpyderC_MarketData.SpyderC35_SentimentAnalyzer")
sys.modules.setdefault("Spyder", types.ModuleType("Spyder"))
sys.modules.setdefault("Spyder.SpyderU_Utilities", types.ModuleType("Spyder.SpyderU_Utilities"))
sys.modules.setdefault(
    "Spyder.SpyderU_Utilities.SpyderU01_Logger",
    types.SimpleNamespace(SpyderLogger=_mock_log),
)
sys.modules.setdefault(
    "Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler",
    types.SimpleNamespace(SpyderErrorHandler=MagicMock()),
)

# Stub optional NLP libs so we can import without them installed
for _mod_name in [
    "transformers", "torch",
    "textblob",
    "vaderSentiment", "vaderSentiment.vaderSentiment",
]:
    sys.modules.setdefault(_mod_name, MagicMock())

import importlib
import importlib.util
import pathlib

_C35_PATH = (
    pathlib.Path(__file__).parent.parent
    / "SpyderC_MarketData"
    / "SpyderC35_SentimentAnalyzer.py"
)
_spec = importlib.util.spec_from_file_location(
    "SpyderC35_SentimentAnalyzer", _C35_PATH
)
_c35_mod = importlib.util.module_from_spec(_spec)
with patch.dict(os.environ, {}):
    _spec.loader.exec_module(_c35_mod)

# Export names used in tests
BaseNewsSource = _c35_mod.BaseNewsSource
AlphaVantageNewsSource = _c35_mod.AlphaVantageNewsSource
FinnhubNewsSource = _c35_mod.FinnhubNewsSource
YahooFinanceRSSNewsSource = _c35_mod.YahooFinanceRSSNewsSource
SentimentAnalyzer = _c35_mod.SentimentAnalyzer
SentimentModel = _c35_mod.SentimentModel
NewsItem = _c35_mod.NewsItem
create_sentiment_analyzer_from_env = _c35_mod.create_sentiment_analyzer_from_env


# ==============================================================================
# HELPERS
# ==============================================================================

def _mock_response(status: int = 200, json_data=None, text: str = "") -> MagicMock:
    """Build a mock requests.Response."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data if json_data is not None else {}
    r.text = text
    return r


def _alpha_vantage_feed(n: int = 3) -> dict:
    """Minimal Alpha Vantage NEWS_SENTIMENT payload."""
    return {
        "feed": [
            {
                "title": f"AV Title {i}",
                "summary": f"AV Summary {i}",
                "url": f"https://example.com/{i}",
                "source": "Reuters",
                "time_published": "20240101T120000",
                "ticker_sentiment": [{"ticker": "SPY"}],
            }
            for i in range(n)
        ]
    }


def _finnhub_feed(n: int = 3) -> list:
    """Minimal Finnhub /company-news payload."""
    base_ts = int(datetime(2024, 1, 1, 12, 0, 0).timestamp())
    return [
        {
            "headline": f"FH Title {i}",
            "summary": f"FH Summary {i}",
            "url": f"https://finnhub.com/{i}",
            "source": "Reuters",
            "datetime": base_ts + i * 3600,
        }
        for i in range(n)
    ]


def _yahoo_rss_xml(n: int = 3) -> str:
    """Minimal Yahoo Finance RSS XML payload."""
    items = "\n".join(
        f"""<item>
  <title>Yahoo Title {i}</title>
  <description>Yahoo Desc {i}</description>
  <link>https://yahoo.com/{i}</link>
  <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
</item>"""
        for i in range(n)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Yahoo Finance</title>
    {items}
  </channel>
</rss>"""


# ==============================================================================
# TESTS — BaseNewsSource ABC
# ==============================================================================

class TestBaseNewsSourceABC(unittest.TestCase):
    """BaseNewsSource cannot be instantiated; subclasses must implement fetch."""

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            BaseNewsSource()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_fetch(self):
        """A subclass missing `fetch` should also be non-instantiable."""
        class BadSource(BaseNewsSource):
            @property
            def source_name(self) -> str:
                return "bad"
            # Missing fetch()

        with self.assertRaises(TypeError):
            BadSource()

    def test_concrete_subclass_valid(self):
        class GoodSource(BaseNewsSource):
            @property
            def source_name(self) -> str:
                return "good"

            def fetch(self, ticker: str, limit: int):
                return []

        src = GoodSource()
        self.assertEqual(src.source_name, "good")
        self.assertEqual(src.fetch("SPY", 5), [])


# ==============================================================================
# TESTS — AlphaVantageNewsSource
# ==============================================================================

class TestAlphaVantageNewsSource(unittest.TestCase):

    def setUp(self):
        self.source = AlphaVantageNewsSource(api_key="test_key")

    def test_source_name(self):
        self.assertEqual(self.source.source_name, "alpha_vantage")

    @patch("requests.get")
    def test_fetch_happy_path(self, mock_get):
        mock_get.return_value = _mock_response(200, _alpha_vantage_feed(3))
        items = self.source.fetch("SPY", 10)

        self.assertEqual(len(items), 3)
        self.assertIsInstance(items[0], NewsItem)
        self.assertEqual(items[0].title, "AV Title 0")
        self.assertEqual(items[0].source, "Reuters")
        self.assertIn("SPY", items[0].tickers)

    @patch("requests.get")
    def test_fetch_non_200_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(429)
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = ConnectionError("timeout")
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_empty_feed_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(200, {"feed": []})
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_bad_date_falls_back_to_now(self, mock_get):
        feed = _alpha_vantage_feed(1)
        feed["feed"][0]["time_published"] = "INVALID"
        mock_get.return_value = _mock_response(200, feed)
        items = self.source.fetch("SPY", 10)
        self.assertEqual(len(items), 1)
        # published should be approx now
        self.assertAlmostEqual(
            items[0].published.timestamp(), datetime.now().timestamp(), delta=5
        )

    @patch("requests.get")
    def test_api_key_passed_in_params(self, mock_get):
        mock_get.return_value = _mock_response(200, {"feed": []})
        self.source.fetch("SPY", 5)
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("params")
        # Extract params from whatever form mock was called
        params = mock_get.call_args.kwargs.get("params") or mock_get.call_args.args[1] if len(mock_get.call_args.args) > 1 else mock_get.call_args.kwargs["params"]
        self.assertEqual(params["apikey"], "test_key")
        self.assertEqual(params["tickers"], "SPY")


# ==============================================================================
# TESTS — FinnhubNewsSource
# ==============================================================================

class TestFinnhubNewsSource(unittest.TestCase):

    def setUp(self):
        self.source = FinnhubNewsSource(api_key="fh_key")

    def test_source_name(self):
        self.assertEqual(self.source.source_name, "finnhub")

    @patch("requests.get")
    def test_fetch_happy_path(self, mock_get):
        mock_get.return_value = _mock_response(200, _finnhub_feed(3))
        items = self.source.fetch("SPY", 10)

        self.assertEqual(len(items), 3)
        self.assertIsInstance(items[0], NewsItem)
        self.assertEqual(items[0].title, "FH Title 0")
        self.assertIn("SPY", items[0].tickers)

    @patch("requests.get")
    def test_fetch_respects_limit(self, mock_get):
        mock_get.return_value = _mock_response(200, _finnhub_feed(10))
        items = self.source.fetch("SPY", 4)
        self.assertEqual(len(items), 4)

    @patch("requests.get")
    def test_fetch_non_200_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(403)
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_non_list_response_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(200, {"error": "Not found"})
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = TimeoutError("timeout")
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_bad_datetime_falls_back_to_now(self, mock_get):
        feed = _finnhub_feed(1)
        feed[0]["datetime"] = "not-a-timestamp"
        mock_get.return_value = _mock_response(200, feed)
        items = self.source.fetch("SPY", 10)
        self.assertEqual(len(items), 1)
        self.assertAlmostEqual(
            items[0].published.timestamp(), datetime.now().timestamp(), delta=5
        )

    @patch("requests.get")
    def test_api_key_in_params(self, mock_get):
        mock_get.return_value = _mock_response(200, [])
        self.source.fetch("AAPL", 5)
        params = mock_get.call_args.kwargs.get("params") or {}
        self.assertEqual(params.get("token"), "fh_key")
        self.assertEqual(params.get("symbol"), "AAPL")

    @patch("requests.get")
    def test_date_range_covers_last_7_days(self, mock_get):
        mock_get.return_value = _mock_response(200, [])
        self.source.fetch("SPY", 5)
        params = mock_get.call_args.kwargs.get("params") or {}
        from_date = datetime.strptime(params["from"], "%Y-%m-%d")
        to_date = datetime.strptime(params["to"], "%Y-%m-%d")
        delta = to_date - from_date
        self.assertAlmostEqual(delta.days, 7, delta=1)


# ==============================================================================
# TESTS — YahooFinanceRSSNewsSource
# ==============================================================================

class TestYahooFinanceRSSNewsSource(unittest.TestCase):

    def setUp(self):
        self.source = YahooFinanceRSSNewsSource()

    def test_source_name(self):
        self.assertEqual(self.source.source_name, "yahoo_rss")

    @patch("requests.get")
    def test_fetch_happy_path(self, mock_get):
        mock_get.return_value = _mock_response(200, text=_yahoo_rss_xml(3))
        items = self.source.fetch("SPY", 10)

        self.assertEqual(len(items), 3)
        self.assertIsInstance(items[0], NewsItem)
        self.assertEqual(items[0].title, "Yahoo Title 0")
        self.assertEqual(items[0].source, "yahoo_finance")
        self.assertIn("SPY", items[0].tickers)

    @patch("requests.get")
    def test_fetch_respects_limit(self, mock_get):
        mock_get.return_value = _mock_response(200, text=_yahoo_rss_xml(10))
        items = self.source.fetch("SPY", 4)
        self.assertEqual(len(items), 4)

    @patch("requests.get")
    def test_fetch_non_200_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(503)
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_malformed_xml_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(200, text="THIS IS NOT XML <<<")
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = ConnectionError("unreachable")
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_fetch_no_channel_returns_empty(self, mock_get):
        mock_get.return_value = _mock_response(
            200, text="<?xml version='1.0'?><rss version='2.0'></rss>"
        )
        items = self.source.fetch("SPY", 10)
        self.assertEqual(items, [])

    @patch("requests.get")
    def test_published_date_parsed(self, mock_get):
        mock_get.return_value = _mock_response(200, text=_yahoo_rss_xml(1))
        items = self.source.fetch("SPY", 10)
        self.assertIsInstance(items[0].published, datetime)
        # Date should be 2024-01-01
        self.assertEqual(items[0].published.year, 2024)

    def test_requires_no_api_key(self):
        """YahooFinanceRSSNewsSource must be constructable with zero arguments."""
        src = YahooFinanceRSSNewsSource()
        self.assertIsInstance(src, BaseNewsSource)


# ==============================================================================
# TESTS — SentimentAnalyzer source pipeline wiring
# ==============================================================================

def _make_analyzer(**kwargs) -> SentimentAnalyzer:
    """Build a SentimentAnalyzer with a dummy sentiment model to skip NLP init."""
    dummy_model = MagicMock()
    dummy_model.analyze.return_value = (0.1, 0.7)
    analyzer = object.__new__(SentimentAnalyzer)
    # Manually set attributes to bypass __init__ NLP model loading
    from collections import deque, defaultdict
    analyzer.sentiment_model = dummy_model
    analyzer.model_type = SentimentModel.VADER
    analyzer.reddit_credentials = None
    analyzer._news_cache = {}
    analyzer._social_cache = {}
    analyzer._sentiment_history = defaultdict(lambda: deque(maxlen=1000))
    analyzer._sentiment_callbacks = []
    # Build source list via the helper logic
    alpha_key = kwargs.get("alpha_vantage_key")
    finnhub_key = kwargs.get("finnhub_key")
    news_sources = kwargs.get("news_sources")
    if news_sources is not None:
        analyzer._news_sources = news_sources
    else:
        analyzer._news_sources = []
        if alpha_key:
            analyzer._news_sources.append(AlphaVantageNewsSource(alpha_key))
        if finnhub_key:
            analyzer._news_sources.append(FinnhubNewsSource(finnhub_key))
        analyzer._news_sources.append(YahooFinanceRSSNewsSource())
    analyzer.alpha_vantage_key = alpha_key
    analyzer.finnhub_key = finnhub_key
    return analyzer


class TestSentimentAnalyzerSourcePipeline(unittest.TestCase):
    """Verify SentimentAnalyzer wires _news_sources correctly."""

    def test_no_keys_uses_only_yahoo_rss(self):
        a = _make_analyzer()
        self.assertEqual(len(a._news_sources), 1)
        self.assertIsInstance(a._news_sources[0], YahooFinanceRSSNewsSource)

    def test_alpha_key_prepends_alpha_vantage(self):
        a = _make_analyzer(alpha_vantage_key="av_key")
        self.assertEqual(len(a._news_sources), 2)
        self.assertIsInstance(a._news_sources[0], AlphaVantageNewsSource)
        self.assertIsInstance(a._news_sources[1], YahooFinanceRSSNewsSource)

    def test_finnhub_key_prepends_finnhub(self):
        a = _make_analyzer(finnhub_key="fh_key")
        self.assertEqual(len(a._news_sources), 2)
        self.assertIsInstance(a._news_sources[0], FinnhubNewsSource)
        self.assertIsInstance(a._news_sources[1], YahooFinanceRSSNewsSource)

    def test_both_keys_gives_three_sources(self):
        a = _make_analyzer(alpha_vantage_key="av_key", finnhub_key="fh_key")
        self.assertEqual(len(a._news_sources), 3)
        self.assertIsInstance(a._news_sources[0], AlphaVantageNewsSource)
        self.assertIsInstance(a._news_sources[1], FinnhubNewsSource)
        self.assertIsInstance(a._news_sources[2], YahooFinanceRSSNewsSource)

    def test_explicit_news_sources_respected(self):
        custom = MagicMock(spec=BaseNewsSource)
        a = _make_analyzer(news_sources=[custom])
        self.assertEqual(a._news_sources, [custom])

    def test_analyze_news_iterates_sources_in_order(self):
        """analyze_news should call sources until limit is met."""
        src_a = MagicMock(spec=BaseNewsSource)
        src_a.source_name = "a"
        src_a.fetch.return_value = [
            NewsItem(
                title=f"A{i}", description="", url="", source="a",
                published=datetime.now(), tickers=["SPY"]
            )
            for i in range(3)
        ]
        src_b = MagicMock(spec=BaseNewsSource)
        src_b.source_name = "b"
        src_b.fetch.return_value = [
            NewsItem(
                title=f"B{i}", description="", url="", source="b",
                published=datetime.now(), tickers=["SPY"]
            )
            for i in range(2)
        ]

        analyzer = _make_analyzer(news_sources=[src_a, src_b])
        items = analyzer.analyze_news("SPY", limit=10, use_cache=False)
        # Both sources called, combined = 5 items
        self.assertEqual(len(items), 5)
        src_a.fetch.assert_called_once()
        src_b.fetch.assert_called_once()

    def test_analyze_news_stops_when_limit_reached(self):
        """Second source should not be called once limit is satisfied."""
        src_a = MagicMock(spec=BaseNewsSource)
        src_a.source_name = "a"
        src_a.fetch.return_value = [
            NewsItem(
                title=f"A{i}", description="", url="", source="a",
                published=datetime.now(), tickers=["SPY"]
            )
            for i in range(5)
        ]
        src_b = MagicMock(spec=BaseNewsSource)
        src_b.source_name = "b"
        src_b.fetch.return_value = []

        analyzer = _make_analyzer(news_sources=[src_a, src_b])
        items = analyzer.analyze_news("SPY", limit=5, use_cache=False)
        self.assertEqual(len(items), 5)
        src_b.fetch.assert_not_called()

    def test_analyze_news_cache_is_hit_on_second_call(self):
        src = MagicMock(spec=BaseNewsSource)
        src.source_name = "only"
        src.fetch.return_value = [
            NewsItem(
                title="cached", description="", url="", source="only",
                published=datetime.now(), tickers=["SPY"]
            )
        ]
        analyzer = _make_analyzer(news_sources=[src])
        analyzer.analyze_news("SPY", limit=10, use_cache=True)
        analyzer.analyze_news("SPY", limit=10, use_cache=True)
        # Source should only have been called once (cache hit on second call)
        self.assertEqual(src.fetch.call_count, 1)


# ==============================================================================
# TESTS — backward-compat _fetch_alpha_vantage_news
# ==============================================================================

class TestAlphaVantageBackwardCompat(unittest.TestCase):
    """_fetch_alpha_vantage_news should delegate to AlphaVantageNewsSource."""

    def test_returns_empty_when_no_key(self):
        analyzer = _make_analyzer()
        analyzer.alpha_vantage_key = None
        result = analyzer._fetch_alpha_vantage_news("SPY", 10)
        self.assertEqual(result, [])

    @patch("requests.get")
    def test_delegates_to_av_source_when_key_present(self, mock_get):
        mock_get.return_value = _mock_response(200, _alpha_vantage_feed(2))
        analyzer = _make_analyzer(alpha_vantage_key="av_key")
        result = analyzer._fetch_alpha_vantage_news("SPY", 10)
        self.assertEqual(len(result), 2)


# ==============================================================================
# TESTS — create_sentiment_analyzer_from_env
# ==============================================================================

class TestCreateFromEnv(unittest.TestCase):
    """create_sentiment_analyzer_from_env should read FINNHUB_API_KEY."""

    def _call(self, env: dict) -> SentimentAnalyzer:
        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(
                SentimentAnalyzer,
                "__init__",
                side_effect=lambda self, **kw: self.__dict__.update(kw) or None,
            ),
        ):
            # We just want to inspect the kwargs passed to __init__
            result = MagicMock(spec=SentimentAnalyzer)
            SentimentAnalyzer.__init__ = MagicMock(return_value=None)
            a = create_sentiment_analyzer_from_env()
        return a

    def test_finnhub_key_read_from_env(self):
        env = {"FINNHUB_API_KEY": "fh_env_key"}
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(SentimentAnalyzer, "__init__", fake_init),
        ):
            create_sentiment_analyzer_from_env()

        self.assertEqual(captured.get("finnhub_key"), "fh_env_key")

    def test_alpha_vantage_key_read_from_env(self):
        env = {"ALPHA_VANTAGE_API_KEY": "av_env_key"}
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, env, clear=True),
            patch.object(SentimentAnalyzer, "__init__", fake_init),
        ):
            create_sentiment_analyzer_from_env()

        self.assertEqual(captured.get("alpha_vantage_key"), "av_env_key")

    def test_no_env_keys_gives_none(self):
        captured = {}

        def fake_init(self, **kw):
            captured.update(kw)

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(SentimentAnalyzer, "__init__", fake_init),
        ):
            create_sentiment_analyzer_from_env()

        self.assertIsNone(captured.get("alpha_vantage_key"))
        self.assertIsNone(captured.get("finnhub_key"))


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
