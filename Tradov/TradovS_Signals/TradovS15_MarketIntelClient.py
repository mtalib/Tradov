#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovS_Signals
Module: TradovS15_MarketIntelClient.py
Purpose: Market intelligence via Adanos social sentiment and Alpha Vantage macro
         news-sentiment. All HTTP fetches are TTL-cached so callers can invoke
         ``get_snapshot()`` on every S07 cycle without triggering network I/O.

API key env vars:
  ADANOS_API_KEY       – Adanos social intelligence API key (optional)
  ALPHA_VANTAGE_API_KEY – Alpha Vantage API key (optional; shared with C35)

Both sources degrade gracefully: if a key is absent or the request fails the
corresponding fields are filled with NaN / empty defaults and ``available`` is
set to False so callers can skip downstream processing.
"""

from __future__ import annotations

import os
import time
import threading
import math
from typing import Any

import requests

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger

# ---------------------------------------------------------------------------
# Module-level logger (used only inside this module)
# ---------------------------------------------------------------------------
logger = TradovLogger.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_ADANOS_BASE_URL = "https://api.adanos.org"
_ADANOS_PLATFORMS = ("reddit", "x", "news")   # polymarket excluded — equity-only
_ADANOS_SYMBOLS = ("TRAD", "QQQ")              # symbols to aggregate
_ADANOS_TTL_SECONDS = 600                     # 10-minute cache

_AV_NEWS_URL = "https://www.alphavantage.co/query"
_AV_NEWS_TOPICS = ("financial_markets", "economy_macro")
_AV_NEWS_TTL_SECONDS = 3600                   # 60-minute cache
_AV_NEWS_LIMIT = 12                           # articles per topic

_REQUEST_TIMEOUT = 15  # seconds per HTTP call


# ---------------------------------------------------------------------------
# Public snapshot datatype (plain dict; callers key by the string constants)
# ---------------------------------------------------------------------------

#: Keys returned by :meth:`MarketIntelClient.get_snapshot`
ADANOS_SENTIMENT = "ADANOS_SENTIMENT"         # dict
NEWS_FLOW_EQUITIES = "NEWS_FLOW_EQUITIES"     # float sentiment score
NEWS_FLOW_MACRO = "NEWS_FLOW_MACRO"           # float sentiment score
NEWS_FLOW_VERDICT = "NEWS_FLOW_VERDICT"       # "bullish"|"neutral"|"defensive"
NEWS_FLOW_HEADLINE = "NEWS_FLOW_HEADLINE"     # str – most recent headline


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sentiment_label(score: float) -> str:
    """Map a -1…1 score to a human-readable label."""
    if not math.isfinite(score):
        return "neutral"
    if score > 0.15:
        return "bullish"
    if score < -0.15:
        return "bearish"
    return "neutral"


def _verdict_from_scores(equities_score: float, macro_score: float) -> str:
    """Combine equities-tone and macro-tone into a single NEWS_FLOW_VERDICT."""
    if not math.isfinite(equities_score):
        equities_score = 0.0
    if not math.isfinite(macro_score):
        macro_score = 0.0
    combined = 0.6 * equities_score + 0.4 * macro_score
    if combined > 0.12:
        return "bullish"
    if combined < -0.12:
        return "defensive"
    return "neutral"


# ---------------------------------------------------------------------------
# MarketIntelClient
# ---------------------------------------------------------------------------

class MarketIntelClient:
    """Fetches and caches Adanos + Alpha Vantage macro-news sentiment.

    All network I/O happens inside :meth:`get_snapshot` which is designed to be
    called from a worker thread — never from the Qt main thread.

    Thread-safety: a single :class:`threading.Lock` serialises cache refreshes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

        self._adanos_api_key: str | None = os.getenv("ADANOS_API_KEY") or None
        self._av_api_key: str | None = os.getenv("ALPHA_VANTAGE_API_KEY") or None

        # Adanos cache
        self._adanos_cache: dict[str, Any] = {}
        self._adanos_last_ts: float = 0.0

        # Alpha Vantage news cache per topic
        self._av_cache: dict[str, tuple[float, list[dict]]] = {}  # topic → (ts, articles)

        logger.debug(
            "S15_MarketIntelClient init | adanos=%s av=%s",
            "key-set" if self._adanos_api_key else "no-key",
            "key-set" if self._av_api_key else "no-key",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> dict[str, Any]:
        """Return the latest market-intelligence snapshot.

        Refreshes from the network only when the TTL has expired; otherwise
        returns the in-memory cached result immediately.

        Returns a dict with the following keys (see module-level constants):
          - ``ADANOS_SENTIMENT``  – dict with per-platform aggregated metrics
          - ``NEWS_FLOW_EQUITIES`` – float, equities news sentiment score (-1…1)
          - ``NEWS_FLOW_MACRO``    – float, macro news sentiment score (-1…1)
          - ``NEWS_FLOW_VERDICT``  – "bullish" | "neutral" | "defensive"
          - ``NEWS_FLOW_HEADLINE`` – str, most recent relevant headline
        """
        with self._lock:
            adanos_data = self._get_adanos_data()
            eq_score, macro_score, headline = self._get_av_news_data()

        verdict = _verdict_from_scores(eq_score, macro_score)

        return {
            ADANOS_SENTIMENT: adanos_data,
            NEWS_FLOW_EQUITIES: eq_score,
            NEWS_FLOW_MACRO: macro_score,
            NEWS_FLOW_VERDICT: verdict,
            NEWS_FLOW_HEADLINE: headline,
        }

    # ------------------------------------------------------------------
    # Adanos internals
    # ------------------------------------------------------------------

    def _get_adanos_data(self) -> dict[str, Any]:
        """Return cached or freshly fetched Adanos sentiment aggregate."""
        now = time.monotonic()
        if self._adanos_cache and (now - self._adanos_last_ts) < _ADANOS_TTL_SECONDS:
            return self._adanos_cache

        if not self._adanos_api_key:
            return self._adanos_unavailable()

        try:
            data = self._fetch_adanos_aggregate()
            self._adanos_cache = data
            self._adanos_last_ts = now
            return data
        except Exception as exc:
            logger.warning("Adanos fetch failed: %s", exc)
            if self._adanos_cache:
                return self._adanos_cache
            return self._adanos_unavailable()

    def _fetch_adanos_aggregate(self) -> dict[str, Any]:
        """Fetch Adanos data for all configured symbols and platforms, aggregate."""
        scores: list[float] = []
        buzz_scores: list[float] = []
        bullish_pcts: list[float] = []
        bearish_pcts: list[float] = []

        headers = {"X-API-Key": self._adanos_api_key, "Accept": "application/json"}

        for symbol in _ADANOS_SYMBOLS:
            for platform in _ADANOS_PLATFORMS:
                url = f"{_ADANOS_BASE_URL}/{platform}/stocks/v1/stock/{symbol}"
                try:
                    resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
                    if resp.status_code == 404:
                        # Symbol/platform not supported — skip silently
                        continue
                    if resp.status_code != 200:
                        logger.debug(
                            "Adanos %s/%s HTTP %s", platform, symbol, resp.status_code
                        )
                        continue
                    payload = resp.json()
                    s = payload.get("sentiment_score")
                    b = payload.get("buzz_score")
                    bull = payload.get("bullish_pct")
                    bear = payload.get("bearish_pct")
                    if isinstance(s, (int, float)) and math.isfinite(float(s)):
                        scores.append(float(s))
                    if isinstance(b, (int, float)) and math.isfinite(float(b)):
                        buzz_scores.append(float(b))
                    if isinstance(bull, (int, float)) and math.isfinite(float(bull)):
                        bullish_pcts.append(float(bull))
                    if isinstance(bear, (int, float)) and math.isfinite(float(bear)):
                        bearish_pcts.append(float(bear))
                except Exception as exc:
                    logger.debug("Adanos request error (%s/%s): %s", platform, symbol, exc)

        if not scores:
            return self._adanos_unavailable()

        avg_score = sum(scores) / len(scores)
        avg_buzz = sum(buzz_scores) / len(buzz_scores) if buzz_scores else float("nan")
        avg_bull = sum(bullish_pcts) / len(bullish_pcts) if bullish_pcts else float("nan")
        avg_bear = sum(bearish_pcts) / len(bearish_pcts) if bearish_pcts else float("nan")

        return {
            "score": round(avg_score, 4),
            "trend": _sentiment_label(avg_score),
            "buzz": round(avg_buzz, 4) if math.isfinite(avg_buzz) else float("nan"),
            "bullish_pct": round(avg_bull, 2) if math.isfinite(avg_bull) else float("nan"),
            "bearish_pct": round(avg_bear, 2) if math.isfinite(avg_bear) else float("nan"),
            "available": True,
            "source_count": len(scores),
        }

    @staticmethod
    def _adanos_unavailable() -> dict[str, Any]:
        return {
            "score": float("nan"),
            "trend": "neutral",
            "buzz": float("nan"),
            "bullish_pct": float("nan"),
            "bearish_pct": float("nan"),
            "available": False,
            "source_count": 0,
        }

    # ------------------------------------------------------------------
    # Alpha Vantage news-sentiment internals
    # ------------------------------------------------------------------

    def _get_av_news_data(self) -> tuple[float, float, str]:
        """Return (equities_score, macro_score, top_headline)."""
        if not self._av_api_key:
            return float("nan"), float("nan"), ""

        equities_articles = self._fetch_av_topic("financial_markets")
        macro_articles = self._fetch_av_topic("economy_macro")

        eq_score = self._average_sentiment(equities_articles)
        macro_score = self._average_sentiment(macro_articles)

        # Pick the most recent headline from either batch
        all_articles = equities_articles + macro_articles
        all_articles.sort(key=lambda a: a.get("time_published", ""), reverse=True)
        headline = all_articles[0].get("title", "") if all_articles else ""

        return eq_score, macro_score, headline

    def _fetch_av_topic(self, topic: str) -> list[dict]:
        """Fetch and cache Alpha Vantage NEWS_SENTIMENT articles for *topic*."""
        now = time.monotonic()
        cached = self._av_cache.get(topic)
        if cached is not None:
            cache_ts, articles = cached
            if (now - cache_ts) < _AV_NEWS_TTL_SECONDS:
                return articles

        params = {
            "function": "NEWS_SENTIMENT",
            "topics": topic,
            "sort": "LATEST",
            "limit": _AV_NEWS_LIMIT,
            "apikey": self._av_api_key,
        }
        try:
            resp = requests.get(_AV_NEWS_URL, params=params, timeout=_REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.debug("AV news HTTP %s for topic=%s", resp.status_code, topic)
                return self._av_cache.get(topic, (0, []))[1]
            articles = resp.json().get("feed", [])
            self._av_cache[topic] = (now, articles)
            return articles
        except Exception as exc:
            logger.warning("AV news fetch error (topic=%s): %s", topic, exc)
            return self._av_cache.get(topic, (0, []))[1]

    @staticmethod
    def _average_sentiment(articles: list[dict]) -> float:
        """Average the ``overall_sentiment_score`` field across articles."""
        scores = []
        for art in articles:
            s = art.get("overall_sentiment_score")
            if isinstance(s, (int, float)) and math.isfinite(float(s)):
                scores.append(float(s))
        if not scores:
            return float("nan")
        return round(sum(scores) / len(scores), 4)


# ---------------------------------------------------------------------------
# Singleton factory (matches pattern used by S09, S10, S14 …)
# ---------------------------------------------------------------------------
_instance: MarketIntelClient | None = None
_instance_lock = threading.Lock()


def get_market_intel_client() -> MarketIntelClient:
    """Return the module-level singleton :class:`MarketIntelClient`."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MarketIntelClient()
    return _instance
