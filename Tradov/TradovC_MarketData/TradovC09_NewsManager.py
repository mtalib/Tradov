#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovC_MarketData
Module: TradovC09_NewsManager.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, UTC
from email.utils import parsedate_to_datetime
import re
import os
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import numpy as np
import requests

try:
    import feedparser
except ImportError:  # pragma: no cover - optional RSS dependency
    feedparser = None  # type: ignore[assignment]

try:
    from textblob import TextBlob
except ImportError:  # pragma: no cover - optional sentiment dependency
    TextBlob = None  # type: ignore[assignment]

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
except ImportError:  # pragma: no cover - optional sentiment dependency
    SentimentIntensityAnalyzer = None  # type: ignore[assignment]

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovA_Core.TradovA05_EventManager import EventType, EventBus

NEWS_SOURCE_URLS: dict[str, list[str]] = {
    "reuters": [
        "https://www.reuters.com/feeds/news",
        "https://news.google.com/rss/search?q=site%3Areuters.com&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "cnbc": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://news.google.com/rss/search?q=site%3Acnbc.com&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "marketwatch": [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://news.google.com/rss/search?q=site%3Amarketwatch.com&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    # Fed feed intentionally excluded: keep enterprise news focused on
    # broad market content rather than policy press releases.
}

NEWSFILTER_QUERY_ENDPOINTS = (
    "https://api.newsfilter.io/search",
    "https://api.newsfilter.io/public/actions",
)
NEWSFILTER_DEFAULT_SOURCES = ("reuters", "cnbc")
NEWSFILTER_LOOKBACK_MINUTES = 5
NEWSFILTER_PAGE_SIZE = 50
FINNHUB_NEWS_ENDPOINT = "https://finnhub.io/api/v1/news"
FINNHUB_NEWS_CATEGORY = "general"
FINNHUB_POLL_INTERVAL_SECONDS = 300
FINNHUB_HEADLINES_PER_POLL = 3


class _FallbackFeedEntry(dict):
    """Minimal feedparser-compatible entry for RSS/Atom fallback parsing."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _read_env_value(key: str, default: str = "") -> str:
    """Read a value from the process env, then fall back to the project .env file."""
    value = os.environ.get(key, "").strip()
    if value:
        return value

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return default

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, raw_value = line.split("=", 1)
            if name.strip() != key:
                continue
            parsed = raw_value.split("#", 1)[0].strip()
            if parsed and ((parsed.startswith('"') and parsed.endswith('"')) or (parsed.startswith("'") and parsed.endswith("'"))):
                parsed = parsed[1:-1].strip()
            return parsed or default
    except Exception:
        return default

    return default


FINNHUB_NEWS_CATEGORY = (_read_env_value("FINNHUB_NEWS_CATEGORY", "general").lower() or "general")

# Keywords for different categories
FED_KEYWORDS = ['federal reserve', 'fomc', 'powell', 'interest rate', 'monetary policy',
                'inflation', 'employment', 'gdp', 'economic data']
MARKET_KEYWORDS = ['spy', 's&p 500', 'stock market', 'wall street', 'nasdaq', 'dow jones']
CRISIS_KEYWORDS = ['crash', 'plunge', 'collapse', 'emergency', 'halt', 'circuit breaker']
EARNINGS_KEYWORDS = ['earnings', 'revenue', 'guidance', 'profit', 'loss', 'beat', 'miss']

# Sentiment thresholds
SENTIMENT_VERY_POSITIVE = 0.5
SENTIMENT_POSITIVE = 0.1
SENTIMENT_NEGATIVE = -0.1
SENTIMENT_VERY_NEGATIVE = -0.5

# Impact levels
IMPACT_CRITICAL = 0.9
IMPACT_HIGH = 0.7
IMPACT_MEDIUM = 0.5
IMPACT_LOW = 0.3

# Update intervals
NEWS_FETCH_INTERVAL = 60  # seconds
ANALYSIS_INTERVAL = 10  # seconds
NEWS_HEADLINES_PER_POLL = 3
NEWS_MAX_ITEM_AGE_SECONDS = 24 * 60 * 60

# ==============================================================================
# ENUMS
# ==============================================================================
class NewsCategory(Enum):
    """News category classification"""
    FED_POLICY = "fed_policy"
    ECONOMIC_DATA = "economic_data"
    MARKET_MOVING = "market_moving"
    EARNINGS = "earnings"
    GEOPOLITICAL = "geopolitical"
    SECTOR_SPECIFIC = "sector_specific"
    GENERAL = "general"

class NewsPriority(Enum):
    """News priority levels"""
    BREAKING = "breaking"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class SentimentLevel(Enum):
    """Sentiment classification"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"

class MarketImpact(Enum):
    """Expected market impact"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class NewsItem:
    """Individual news item"""
    id: str
    timestamp: datetime
    source: str
    title: str
    summary: str
    url: str
    category: NewsCategory
    priority: NewsPriority
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    timestamp_has_time: bool = True
    raw_text: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)

@dataclass
class NewsSentiment:
    """News sentiment analysis"""
    item_id: str
    timestamp: datetime
    sentiment_score: float  # -1 to 1
    sentiment_level: SentimentLevel
    textblob_polarity: float
    textblob_subjectivity: float
    vader_scores: dict[str, float]
    keywords_found: list[str]
    confidence: float

@dataclass
class NewsImpact:
    """News market impact assessment"""
    item_id: str
    timestamp: datetime
    impact_level: MarketImpact
    impact_score: float  # 0 to 1
    affected_sectors: list[str]
    expected_duration: str  # "minutes", "hours", "days"
    trading_implications: list[str]

@dataclass
class NewsAnalysis:
    """Comprehensive news analysis"""
    timestamp: datetime
    total_items: int
    items_by_category: dict[NewsCategory, int]
    overall_sentiment: float
    sentiment_trend: str  # "improving", "deteriorating", "stable"
    high_impact_items: list[NewsItem]
    fed_news_count: int
    breaking_news: list[NewsItem]
    market_implications: dict[str, Any]
    trading_signals: list[dict[str, Any]]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class NewsManager:
    """
    Real-time news aggregation and sentiment analysis system.

    This class aggregates news from multiple sources, performs sentiment analysis,
    assesses market impact, and generates trading signals based on news flow.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_bus: Event management system
        news_items: Collection of news items
        sentiment_analyzer: VADER sentiment analyzer

    Example:
        >>> manager = NewsManager()
        >>> manager.initialize()
        >>> analysis = manager.get_current_analysis()
    """

    def __init__(self):
        """Initialize the news manager."""
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()
        self.event_bus = EventBus()

        # News storage
        self.news_items: dict[str, NewsItem] = {}
        self.news_sentiments: dict[str, NewsSentiment] = {}
        self.news_impacts: dict[str, NewsImpact] = {}
        self.news_history: deque = deque(maxlen=1000)

        # Analysis tools
        self.vader_analyzer = SentimentIntensityAnalyzer() if SentimentIntensityAnalyzer is not None else None
        self.processed_urls: set[str] = set()
        self._newsfilter_api_key = _read_env_value("NEWSFILTER_API_KEY")
        self._newsfilter_sources = self._resolve_newsfilter_sources()
        self._newsfilter_session = requests.Session()
        self._newsfilter_last_poll_at = datetime.now(UTC) - timedelta(minutes=NEWSFILTER_LOOKBACK_MINUTES)
        self._newsfilter_enabled = bool(self._newsfilter_api_key)
        self._finnhub_api_key = _read_env_value("FINNHUB_API_KEY")
        self._finnhub_enabled = bool(self._finnhub_api_key)
        self._finnhub_session = requests.Session()
        self._news_feed_provider = (
            "finnhub" if self._finnhub_enabled else
            "newsfilter" if self._newsfilter_enabled else
            "rss"
        )
        self._news_item_retention_seconds = NEWS_MAX_ITEM_AGE_SECONDS

        # Current state
        self.current_analysis: NewsAnalysis | None = None
        self.sentiment_history: deque = deque(maxlen=100)

        # Statistics
        self.stats = {
            'items_processed': 0,
            'sources_active': 0,
            'errors': 0,
            'last_update': datetime.now(UTC)
        }

        # Control flags
        self.is_running = False
        self.fetch_thread: threading.Thread | None = None
        self.analysis_thread: threading.Thread | None = None
        self.lock = threading.RLock()

        # Callbacks
        self.news_callbacks: list[callable] = []
        self.alert_callbacks: list[callable] = []

        self.logger.info("NewsManager initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize news monitoring.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing news monitoring")

            # Start monitoring
            self.start()

            self.logger.info("News monitoring initialized successfully")
            return True

        except Exception as e:
            self.logger.error("Initialization failed: %s", e)
            return False

    def start(self) -> None:
        """Start news monitoring."""
        if not self.is_running:
            self.is_running = True

            # Prime the feed immediately so the dashboard has data before the
            # background poll thread finishes its first cycle.
            try:
                self._poll_news_sources_once()
            except Exception as exc:
                self.logger.warning("Initial news prime failed: %s", exc)

            # Start fetch thread
            self.fetch_thread = threading.Thread(
                target=self._fetch_loop,
                daemon=True
            )
            self.fetch_thread.start()

            # Start analysis thread
            self.analysis_thread = threading.Thread(
                target=self._analysis_loop,
                daemon=True
            )
            self.analysis_thread.start()

            self.logger.info("News monitoring started")

    def stop(self) -> None:
        """Stop news monitoring."""
        self.is_running = False
        if self.fetch_thread:
            self.fetch_thread.join(timeout=0.5)
        if self.analysis_thread:
            self.analysis_thread.join(timeout=0.5)
        for session_name in ("_newsfilter_session", "_finnhub_session"):
            session = getattr(self, session_name, None)
            close_session = getattr(session, "close", None)
            if callable(close_session):
                try:
                    close_session()
                except Exception:
                    self.logger.debug(
                        "Failed to close %s during NewsManager shutdown",
                        session_name,
                        exc_info=True,
                    )
        self.logger.info("News monitoring stopped")

    def get_current_analysis(self) -> NewsAnalysis | None:
        """
        Get current news analysis.

        Returns:
            Current analysis or None
        """
        return self.current_analysis

    def get_recent_news(self, category: NewsCategory | None = None,
                       limit: int = 10) -> list[NewsItem]:
        """
        Get recent news items.

        Args:
            category: Filter by category (optional)
            limit: Maximum items to return

        Returns:
            List of news items
        """
        with self.lock:
            self._prune_stale_news_items_locked()
            items_by_id: dict[str, NewsItem] = {}
            for item in self.news_history:
                if not self._is_recent_news_item(item):
                    continue
                items_by_id[self._news_item_history_key(item)] = item
            for item_id, item in self.news_items.items():
                if not self._is_recent_news_item(item):
                    continue
                items_by_id[item_id] = item
            items = list(items_by_id.values())

            # Filter by category if specified
            if category:
                items = [item for item in items if item.category == category]

            # Sort by timestamp
            items.sort(key=lambda x: x.timestamp, reverse=True)

            return items[:limit]

    def search_news(self, query: str, limit: int = 20) -> list[NewsItem]:
        """
        Search news by keyword.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching news items
        """
        query_lower = query.lower()
        results = []

        with self.lock:
            self._prune_stale_news_items_locked()
            for item in self.news_items.values():
                # Search in title and summary
                if (query_lower in item.title.lower() or
                    query_lower in item.summary.lower()):
                    results.append(item)

                if len(results) >= limit:
                    break

        return results

    def get_sentiment_trend(self, window_minutes: int = 60) -> dict[str, Any]:
        """
        Get sentiment trend over time window.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Sentiment trend analysis
        """
        cutoff_time = datetime.now(UTC) - timedelta(minutes=window_minutes)
        recent_sentiments = []

        with self.lock:
            for sentiment in self.news_sentiments.values():
                if sentiment.timestamp > cutoff_time:
                    recent_sentiments.append(sentiment)

        if not recent_sentiments:
            return {'trend': 'neutral', 'change': 0.0}

        # Sort by time
        recent_sentiments.sort(key=lambda x: x.timestamp)

        # Calculate trend
        early_sentiment = np.mean([s.sentiment_score for s in recent_sentiments[:len(recent_sentiments)//2]])  # noqa: E501
        late_sentiment = np.mean([s.sentiment_score for s in recent_sentiments[len(recent_sentiments)//2:]])  # noqa: E501

        change = late_sentiment - early_sentiment

        if change > 0.1:
            trend = 'improving'
        elif change < -0.1:
            trend = 'deteriorating'
        else:
            trend = 'stable'

        return {
            'trend': trend,
            'change': change,
            'current_sentiment': late_sentiment,
            'sentiment_count': len(recent_sentiments)
        }

    def register_news_callback(self, callback: callable) -> None:
        """Register callback for news updates."""
        self.news_callbacks.append(callback)

    def register_alert_callback(self, callback: callable) -> None:
        """Register callback for breaking news alerts."""
        self.alert_callbacks.append(callback)

    def refresh_now(self, *, force: bool = True) -> bool:
        """Fetch the latest news immediately using the configured provider.

        When *force* is True, the visible cache and duplicate-suppression set
        are cleared first so the caller gets a true manual refresh instead of
        a replay of the prior cached slice.
        """
        if force:
            with self.lock:
                self.news_items.clear()
                self.news_history.clear()
                self.news_sentiments.clear()
                self.news_impacts.clear()
                self.processed_urls.clear()
        self._poll_news_sources_once()
        self._prune_stale_news_items()
        return True

    # ==========================================================================
    # FETCHING METHODS
    # ==========================================================================
    def _fetch_loop(self) -> None:
        """Main fetch loop for news sources."""
        while self.is_running:
            try:
                self._poll_news_sources_once()

                self._prune_stale_news_items()
                time.sleep(FINNHUB_POLL_INTERVAL_SECONDS)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Fetch loop error: %s", e)
                self.stats['errors'] += 1
                time.sleep(FINNHUB_POLL_INTERVAL_SECONDS)  # thread-safe: time.sleep() intentional

    def _poll_news_sources_once(self) -> None:
        """Poll the configured news provider once.

        The manager supports three modes:
        - Finnhub when an API key is present.
        - Newsfilter when only NEWSFILTER_API_KEY is present.
        - RSS fallback when no API key is configured.
        """
        if self._finnhub_enabled:
            self._fetch_from_finnhub()
            return
        if self._newsfilter_enabled:
            self._fetch_from_newsfilter()
            return

        for source_name, source_urls in NEWS_SOURCE_URLS.items():
            self._fetch_from_source(source_name, source_urls)

    def _fetch_from_finnhub(self) -> None:
        """Fetch market news from Finnhub as the primary feed."""
        articles = self._query_finnhub_news()
        if not articles:
            return

        self.stats['sources_active'] += 1
        for article in articles[:FINNHUB_HEADLINES_PER_POLL]:
            news_item = self._create_finnhub_news_item(article)
            if news_item is None:
                continue
            if not self._is_recent_news_item(news_item):
                continue
            if news_item.url in self.processed_urls:
                continue

            with self.lock:
                self.news_items[news_item.id] = news_item
                self.news_history.appendleft(news_item)
                self.processed_urls.add(news_item.url)
                self.stats['items_processed'] += 1

            sentiment = self._analyze_sentiment(news_item)
            if sentiment:
                self.news_sentiments[news_item.id] = sentiment

            impact = self._assess_impact(news_item, sentiment)
            if impact:
                self.news_impacts[news_item.id] = impact

            if news_item.priority == NewsPriority.BREAKING:
                self._handle_breaking_news(news_item)
        self._prune_stale_news_items()

    def _query_finnhub_news(self) -> list[dict[str, Any]]:
        """Query Finnhub market news using the authenticated REST API."""
        params = {
            "category": FINNHUB_NEWS_CATEGORY,
            "minId": 0,
            "token": self._finnhub_api_key,
        }
        try:
            response = self._finnhub_session.get(
                FINNHUB_NEWS_ENDPOINT,
                params=params,
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
            return []
        except Exception as exc:
            self.logger.warning("Finnhub fetch failed: %s", exc)
            return []

    def _create_finnhub_news_item(self, article: dict[str, Any]) -> NewsItem | None:
        """Normalize a Finnhub news item into a NewsItem."""
        try:
            title = str(article.get("headline") or "").strip()
            summary = str(article.get("summary") or "").strip()
            url = str(article.get("url") or "").strip()
            if not title or not url:
                return None

            timestamp = datetime.now(UTC)
            article_time = article.get("datetime")
            if article_time not in (None, ""):
                try:
                    timestamp = datetime.fromtimestamp(int(article_time), tz=UTC)
                except (TypeError, ValueError, OSError):
                    timestamp = datetime.now(UTC)

            source_raw = str(article.get("source") or "").strip()
            source_tag = re.sub(r"\s+", "-", source_raw.upper()) if source_raw else ""
            source_name = f"FIN-{source_tag}" if source_tag else "FIN"
            item_id = str(article.get("id") or hashlib.md5(url.encode(), usedforsecurity=False).hexdigest())
            category = self._categorize_news(title, summary)
            priority = self._determine_priority(title, summary, category)
            tags = []
            category_tag = str(article.get("category") or "").strip()
            if category_tag:
                tags.append(category_tag)

            return NewsItem(
                id=item_id,
                timestamp=timestamp,
                received_at=datetime.now(UTC),
                timestamp_has_time=True,
                source=source_name,
                title=title,
                summary=summary,
                url=url,
                category=category,
                priority=priority,
                author=str(article.get("source") or ""),
                tags=tags,
                raw_text=f"{title}\n{summary}".strip(),
            )
        except Exception as exc:
            self.logger.error("Error creating Finnhub news item: %s", exc)
            return None

    def _resolve_newsfilter_sources(self) -> list[str]:
        """Resolve enabled Newsfilter source IDs."""
        raw = os.environ.get("NEWSFILTER_SOURCES", "").strip().lower()
        if not raw:
            return list(NEWSFILTER_DEFAULT_SOURCES)
        sources = [part.strip() for part in raw.split(",") if part.strip()]
        return sources or list(NEWSFILTER_DEFAULT_SOURCES)

    def _newsfilter_query_window(self) -> tuple[str, str]:
        """Return an ISO-8601 window for the next Newsfilter poll."""
        start = self._newsfilter_last_poll_at - timedelta(seconds=15)
        end = datetime.now(UTC) + timedelta(seconds=5)
        return start.isoformat(), end.isoformat()

    def _fetch_from_newsfilter(self) -> None:
        """Fetch Reuters/CNBC market news from the Newsfilter API."""
        start_iso, end_iso = self._newsfilter_query_window()
        newest_seen = self._newsfilter_last_poll_at

        for source_id in self._newsfilter_sources:
            try:
                articles = self._query_newsfilter_source(source_id, start_iso, end_iso)
            except Exception as exc:
                self.logger.warning("Newsfilter fetch failed for %s: %s", source_id, exc)
                continue

            if not articles:
                continue

            self.stats['sources_active'] += 1
            for article in articles[:NEWSFILTER_PAGE_SIZE]:
                news_item = self._create_newsfilter_news_item(article, source_id)
                if news_item is None:
                    continue
                if not self._is_recent_news_item(news_item):
                    continue
                if news_item.url in self.processed_urls:
                    continue

                with self.lock:
                    self.news_items[news_item.id] = news_item
                    self.news_history.appendleft(news_item)
                    self.processed_urls.add(news_item.url)
                    self.stats['items_processed'] += 1

                    sentiment = self._analyze_sentiment(news_item)
                    if sentiment:
                        self.news_sentiments[news_item.id] = sentiment

                    impact = self._assess_impact(news_item, sentiment)
                    if impact:
                        self.news_impacts[news_item.id] = impact

                    if news_item.priority == NewsPriority.BREAKING:
                        self._handle_breaking_news(news_item)

                    if news_item.timestamp > newest_seen:
                        newest_seen = news_item.timestamp

        self._newsfilter_last_poll_at = max(newest_seen, datetime.now(UTC) - timedelta(seconds=5))
        self._prune_stale_news_items()

    def _query_newsfilter_source(self, source_id: str, start_iso: str, end_iso: str) -> list[dict[str, Any]]:
        """Query one Newsfilter source ID for a bounded time window."""
        query = {
            "queryString": f"source.id:{source_id} AND publishedAt:[{start_iso} TO {end_iso}]",
            "from": 0,
            "size": NEWSFILTER_PAGE_SIZE,
        }
        headers = {
            "Authorization": self._newsfilter_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for endpoint in NEWSFILTER_QUERY_ENDPOINTS:
            try:
                response = self._newsfilter_session.post(
                    endpoint,
                    headers=headers,
                    json=query,
                    timeout=20,
                )
                if response.status_code in (401, 403, 404):
                    last_error = RuntimeError(f"{endpoint} returned {response.status_code}")
                    continue
                response.raise_for_status()
                payload = response.json()
                articles = payload.get("articles", [])
                if isinstance(articles, list):
                    return [article for article in articles if isinstance(article, dict)]
                return []
            except Exception as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []

    def _create_newsfilter_news_item(self, article: dict[str, Any], source_id: str) -> NewsItem | None:
        """Normalize a Newsfilter article into a NewsItem."""
        try:
            title = str(article.get("title") or "").strip()
            summary = str(article.get("description") or "").strip()
            url = str(article.get("url") or article.get("sourceUrl") or "").strip()
            if not title or not url:
                return None

            timestamp_text = str(article.get("publishedAt") or "").strip()
            timestamp = datetime.now(UTC)
            if timestamp_text:
                try:
                    timestamp = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = datetime.now(UTC)

            source_data = article.get("source")
            if isinstance(source_data, dict):
                source_name = str(source_data.get("name") or source_data.get("id") or source_id).strip()
            else:
                source_name = source_id

            item_id = str(article.get("id") or hashlib.md5(url.encode(), usedforsecurity=False).hexdigest())
            category = self._categorize_news(title, summary)
            priority = self._determine_priority(title, summary, category)
            symbols = article.get("symbols") or []
            tags = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]

            return NewsItem(
                id=item_id,
                timestamp=timestamp,
                received_at=datetime.now(UTC),
                timestamp_has_time=True,
                source=source_name,
                title=title,
                summary=summary,
                url=url,
                category=category,
                priority=priority,
                author=str(article.get("author") or ""),
                tags=tags,
                raw_text=f"{title}\n{summary}".strip(),
            )
        except Exception as e:
            self.logger.error("Error creating Newsfilter news item: %s", e)
            return None

    def _fetch_from_source(self, source_name: str, source_urls: list[str], limit: int = 20) -> None:
        """Fetch news from a specific source."""
        try:
            if not source_urls:
                return

            last_error: Exception | None = None
            entries: list[Any] = []
            for source_url in source_urls:
                try:
                    # Parse RSS feed. Use feedparser when installed, otherwise a small
                    # stdlib parser so the dashboard can still show news headlines.
                    entries = self._parse_feed_entries(source_url)
                    if entries:
                        break
                except Exception as exc:
                    last_error = exc
                    continue

            if not entries:
                if last_error is not None:
                    raise last_error
                return

            for entry in entries[:max(1, limit)]:  # Limit to recent items
                # Check if already processed
                if entry.link in self.processed_urls:
                    continue

                # Create news item
                news_item = self._create_news_item(source_name, entry)
                if news_item:
                    if not self._is_recent_news_item(news_item):
                        continue
                    with self.lock:
                        self.news_items[news_item.id] = news_item
                        self.news_history.appendleft(news_item)
                        self.processed_urls.add(entry.link)
                        self.stats['items_processed'] += 1

                    # Analyze sentiment
                    sentiment = self._analyze_sentiment(news_item)
                    if sentiment:
                        self.news_sentiments[news_item.id] = sentiment

                    # Assess impact
                    impact = self._assess_impact(news_item, sentiment)
                    if impact:
                        self.news_impacts[news_item.id] = impact

                    # Check for breaking news
                    if news_item.priority == NewsPriority.BREAKING:
                        self._handle_breaking_news(news_item)

        except Exception as e:
            self.logger.error("Error fetching from %s: %s", source_name, e)
        finally:
            self._prune_stale_news_items()

    def _parse_feed_entries(self, source_url: str) -> list[Any]:
        if feedparser is not None:
            feed = feedparser.parse(source_url)
            return list(getattr(feed, "entries", []) or [])

        request = Request(
            source_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux x86_64) Tradov/1.0 RSS Reader",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 - configured trusted feed URLs
            payload = response.read()

        root = ET.fromstring(payload)
        entries: list[Any] = []
        for node in root.findall(".//item"):
            entry = self._fallback_entry_from_rss_item(node)
            if entry:
                entries.append(entry)
        if entries:
            return entries

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for node in root.findall(".//atom:entry", ns):
            entry = self._fallback_entry_from_atom_entry(node, ns)
            if entry:
                entries.append(entry)
        return entries

    @staticmethod
    def _parsed_time_tuple(raw_text: str) -> Any | None:
        if not raw_text:
            return None
        try:
            parsed = parsedate_to_datetime(raw_text)
            return parsed.timetuple()
        except Exception:
            return None

    def _fallback_entry_from_rss_item(self, item: ET.Element) -> _FallbackFeedEntry | None:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            return None
        published = (item.findtext("pubDate") or item.findtext("published") or item.findtext("updated") or "").strip()
        return _FallbackFeedEntry(
            title=title,
            summary=(item.findtext("description") or "").strip(),
            link=link,
            published=published,
            updated=published,
            published_parsed=self._parsed_time_tuple(published),
            tags=[],
            author=(item.findtext("author") or "").strip(),
        )

    def _fallback_entry_from_atom_entry(self, entry: ET.Element, ns: dict[str, str]) -> _FallbackFeedEntry | None:
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link = ""
        for link_node in entry.findall("atom:link", ns):
            href = (link_node.attrib.get("href") or "").strip()
            if href:
                link = href
                break
        if not title or not link:
            return None
        published = (
            entry.findtext("atom:published", default="", namespaces=ns)
            or entry.findtext("atom:updated", default="", namespaces=ns)
            or ""
        ).strip()
        return _FallbackFeedEntry(
            title=title,
            summary=(entry.findtext("atom:summary", default="", namespaces=ns) or "").strip(),
            link=link,
            published=published,
            updated=published,
            published_parsed=self._parsed_time_tuple(published),
            tags=[],
            author=(entry.findtext("atom:author/atom:name", default="", namespaces=ns) or "").strip(),
        )

    def _create_news_item(self, source: str, entry: Any) -> NewsItem | None:
        """Create news item from feed entry."""
        try:
            # Extract basic info
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            url = entry.get('link', '')

            # Skip if missing required fields
            if not title or not url:
                return None

            # Parse timestamp
            published = entry.get('published_parsed')
            raw_timestamp_text = str(entry.get('published', '') or entry.get('updated', '') or "")
            if published:
                try:
                    timestamp = parsedate_to_datetime(raw_timestamp_text) if raw_timestamp_text else None
                except Exception:
                    timestamp = None
                if timestamp is None:
                    timestamp = datetime.fromtimestamp(time.mktime(published), tz=UTC)
                elif timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                else:
                    timestamp = timestamp.astimezone(UTC)
            else:
                timestamp = datetime.now(UTC)
            timestamp_has_time = bool(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", raw_timestamp_text))
            received_at = datetime.now(UTC)

            # Generate ID
            item_id = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()

            # Categorize
            category = self._categorize_news(title, summary)
            priority = self._determine_priority(title, summary, category)

            # Extract tags
            tags = [tag['term'] for tag in entry.get('tags', [])]

            return NewsItem(
                id=item_id,
                timestamp=timestamp,
                received_at=received_at,
                timestamp_has_time=timestamp_has_time,
                source=source,
                title=title,
                summary=summary,
                url=url,
                category=category,
                priority=priority,
                author=entry.get('author', ''),
                tags=tags
            )

        except Exception as e:
            self.logger.error("Error creating news item: %s", e)
            return None

    def _news_item_history_key(self, news_item: NewsItem) -> str:
        """Return a stable key for de-duplicating items in recent-news queries."""
        news_id = str(getattr(news_item, "id", "") or "").strip()
        if news_id:
            return news_id
        source = str(getattr(news_item, "source", "") or "").strip()
        title = str(getattr(news_item, "title", "") or "").strip()
        timestamp = getattr(news_item, "timestamp", None)
        ts_text = ""
        if hasattr(timestamp, "isoformat"):
            try:
                ts_text = timestamp.isoformat()
            except Exception:
                ts_text = ""
        return "|".join(part for part in (ts_text, source, title) if part)

    def _item_timestamp_utc(self, news_item: NewsItem) -> datetime | None:
        """Return a timezone-aware UTC timestamp for a news item."""
        timestamp = getattr(news_item, "timestamp", None)
        if not isinstance(timestamp, datetime):
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def _is_recent_news_item(self, news_item: NewsItem, now: datetime | None = None) -> bool:
        """Return True if the item is within the configured retention window."""
        now = now or datetime.now(UTC)
        timestamp = self._item_timestamp_utc(news_item)
        if timestamp is None:
            return False
        age_seconds = (now - timestamp).total_seconds()
        return 0.0 <= age_seconds <= self._news_item_retention_seconds

    def _prune_stale_news_items_locked(self) -> None:
        """Remove news items older than the retention window."""
        now = datetime.now(UTC)
        stale_items = [
            (item_id, item)
            for item_id, item in self.news_items.items()
            if not self._is_recent_news_item(item, now)
        ]
        stale_ids = [item_id for item_id, _item in stale_items]
        if not stale_ids:
            return

        for item_id in stale_ids:
            self.news_items.pop(item_id, None)
            self.news_sentiments.pop(item_id, None)
            self.news_impacts.pop(item_id, None)

        stale_urls = {
            item.url
            for _item_id, item in stale_items
            if getattr(item, "url", "")
        }
        if stale_urls:
            self.processed_urls.difference_update(stale_urls)

    def _prune_stale_news_items(self) -> None:
        """Thread-safe stale-item pruning helper."""
        with self.lock:
            self._prune_stale_news_items_locked()

    def _categorize_news(self, title: str, summary: str) -> NewsCategory:
        """Categorize news based on content."""
        text = f"{title} {summary}".lower()

        # Check categories in priority order
        if any(keyword in text for keyword in FED_KEYWORDS):
            return NewsCategory.FED_POLICY
        elif any(keyword in text for keyword in ['gdp', 'employment', 'inflation', 'retail sales']):
            return NewsCategory.ECONOMIC_DATA
        elif any(keyword in text for keyword in EARNINGS_KEYWORDS):
            return NewsCategory.EARNINGS
        elif any(keyword in text for keyword in MARKET_KEYWORDS):
            return NewsCategory.MARKET_MOVING
        elif any(keyword in text for keyword in ['china', 'russia', 'war', 'sanctions']):
            return NewsCategory.GEOPOLITICAL
        else:
            return NewsCategory.GENERAL

    def _determine_priority(self, title: str, summary: str,
                          category: NewsCategory) -> NewsPriority:
        """Determine news priority."""
        text = f"{title} {summary}".lower()

        # Check for breaking indicators
        if any(word in text for word in ['breaking', 'alert', 'urgent']):
            return NewsPriority.BREAKING

        # Check for crisis keywords
        if any(keyword in text for keyword in CRISIS_KEYWORDS):
            return NewsPriority.BREAKING

        # Category-based priority
        if category in [NewsCategory.FED_POLICY, NewsCategory.ECONOMIC_DATA]:
            return NewsPriority.HIGH
        elif category == NewsCategory.MARKET_MOVING:
            return NewsPriority.MEDIUM
        else:
            return NewsPriority.LOW

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _analysis_loop(self) -> None:
        """Main analysis loop."""
        while self.is_running:
            try:
                # Perform analysis
                analysis = self._perform_analysis()
                if analysis:
                    self.current_analysis = analysis

                    # Notify callbacks
                    for callback in self.news_callbacks:
                        try:
                            callback(analysis)
                        except Exception as e:
                            self.logger.error("News callback error: %s", e)

                    # Publish event on the lightweight in-process bus.
                    self.event_bus.publish(
                        EventType.NEWS_ANALYSIS,
                        {
                            'analysis': analysis,
                            'timestamp': datetime.now(UTC)
                        },
                    )

                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Analysis loop error: %s", e)
                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

    def _analyze_sentiment(self, news_item: NewsItem) -> NewsSentiment | None:
        """Analyze sentiment of news item."""
        try:
            text = f"{news_item.title} {news_item.summary}"

            # Sentiment libraries are optional; news ingestion must keep working
            # even when the NLP extras are not installed in the trading runtime.
            if TextBlob is not None:
                blob = TextBlob(text)
                textblob_polarity = blob.sentiment.polarity
                textblob_subjectivity = blob.sentiment.subjectivity
            else:
                textblob_polarity = 0.0
                textblob_subjectivity = 0.0

            # VADER analysis
            if self.vader_analyzer is not None:
                vader_scores = self.vader_analyzer.polarity_scores(text)
            else:
                vader_scores = {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0}

            # Combined sentiment score
            sentiment_score = (
                textblob_polarity * 0.4 +
                vader_scores['compound'] * 0.6
            )

            # Determine sentiment level
            if sentiment_score >= SENTIMENT_VERY_POSITIVE:
                sentiment_level = SentimentLevel.VERY_BULLISH
            elif sentiment_score >= SENTIMENT_POSITIVE:
                sentiment_level = SentimentLevel.BULLISH
            elif sentiment_score <= SENTIMENT_VERY_NEGATIVE:
                sentiment_level = SentimentLevel.VERY_BEARISH
            elif sentiment_score <= SENTIMENT_NEGATIVE:
                sentiment_level = SentimentLevel.BEARISH
            else:
                sentiment_level = SentimentLevel.NEUTRAL

            # Find keywords
            keywords_found = []
            all_keywords = FED_KEYWORDS + MARKET_KEYWORDS + CRISIS_KEYWORDS
            for keyword in all_keywords:
                if keyword in text.lower():
                    keywords_found.append(keyword)

            # Calculate confidence
            confidence = min(abs(sentiment_score) * 2, 1.0)
            if textblob_subjectivity > 0.8:
                confidence *= 0.7  # Lower confidence for highly subjective

            return NewsSentiment(
                item_id=news_item.id,
                timestamp=datetime.now(UTC),
                sentiment_score=sentiment_score,
                sentiment_level=sentiment_level,
                textblob_polarity=textblob_polarity,
                textblob_subjectivity=textblob_subjectivity,
                vader_scores=vader_scores,
                keywords_found=keywords_found,
                confidence=confidence
            )

        except Exception as e:
            self.logger.error("Error analyzing sentiment: %s", e)
            return None

    def _assess_impact(self, news_item: NewsItem,
                      sentiment: NewsSentiment | None) -> NewsImpact | None:
        """Assess market impact of news."""
        try:
            # Base impact on category and priority
            if news_item.priority == NewsPriority.BREAKING:
                impact_score = 0.9
            elif news_item.category == NewsCategory.FED_POLICY:
                impact_score = 0.8
            elif news_item.category == NewsCategory.ECONOMIC_DATA:
                impact_score = 0.7
            elif news_item.category == NewsCategory.MARKET_MOVING:
                impact_score = 0.6
            else:
                impact_score = 0.3

            # Adjust for sentiment extremity
            if sentiment and abs(sentiment.sentiment_score) > 0.5:
                impact_score = min(impact_score * 1.2, 1.0)

            # Determine impact level
            if impact_score >= IMPACT_CRITICAL:
                impact_level = MarketImpact.CRITICAL
            elif impact_score >= IMPACT_HIGH:
                impact_level = MarketImpact.HIGH
            elif impact_score >= IMPACT_MEDIUM:
                impact_level = MarketImpact.MEDIUM
            elif impact_score >= IMPACT_LOW:
                impact_level = MarketImpact.LOW
            else:
                impact_level = MarketImpact.MINIMAL

            # Determine affected sectors
            affected_sectors = self._identify_affected_sectors(news_item)

            # Expected duration
            if impact_level == MarketImpact.CRITICAL:
                duration = "days"
            elif impact_level == MarketImpact.HIGH:
                duration = "hours"
            else:
                duration = "minutes"

            # Trading implications
            implications = self._generate_implications(
                news_item, sentiment, impact_level
            )

            return NewsImpact(
                item_id=news_item.id,
                timestamp=datetime.now(UTC),
                impact_level=impact_level,
                impact_score=impact_score,
                affected_sectors=affected_sectors,
                expected_duration=duration,
                trading_implications=implications
            )

        except Exception as e:
            self.logger.error("Error assessing impact: %s", e)
            return None

    def _identify_affected_sectors(self, news_item: NewsItem) -> list[str]:
        """Identify sectors affected by news."""
        text = f"{news_item.title} {news_item.summary}".lower()
        affected = []

        sector_keywords = {
            'XLK': ['tech', 'technology', 'software', 'semiconductor'],
            'XLF': ['bank', 'financial', 'jpmorgan', 'goldman'],
            'XLE': ['energy', 'oil', 'gas', 'exxon', 'chevron'],
            'XLV': ['health', 'pharma', 'biotech', 'pfizer'],
            'XLI': ['industrial', 'manufacturing', 'boeing', 'caterpillar'],
            'XLY': ['consumer', 'retail', 'amazon', 'tesla'],
            'XLP': ['staples', 'procter', 'coca-cola', 'walmart'],
            'XLU': ['utilities', 'electric', 'power', 'nextera']
        }

        for sector, keywords in sector_keywords.items():
            if any(keyword in text for keyword in keywords):
                affected.append(sector)

        # If Fed news, all sectors affected
        if news_item.category == NewsCategory.FED_POLICY:
            return ['ALL']

        return affected if affected else ['TRAD']

    def _generate_implications(self, news_item: NewsItem,
                             sentiment: NewsSentiment | None,
                             impact_level: MarketImpact) -> list[str]:
        """Generate trading implications."""
        implications = []

        # High impact implications
        if impact_level in [MarketImpact.CRITICAL, MarketImpact.HIGH]:
            implications.append("Expect increased volatility")
            implications.append("Consider reducing position sizes")

            if sentiment:
                if sentiment.sentiment_level in [SentimentLevel.VERY_BEARISH, SentimentLevel.BEARISH]:  # noqa: E501
                    implications.append("Consider protective puts")
                    implications.append("Avoid bullish strategies")
                elif sentiment.sentiment_level in [SentimentLevel.VERY_BULLISH, SentimentLevel.BULLISH]:  # noqa: E501
                    implications.append("Consider bull spreads")
                    implications.append("Avoid bearish positions")

        # Category-specific implications
        if news_item.category == NewsCategory.FED_POLICY:
            implications.append("Monitor bond yields")
            implications.append("Watch for sector rotation")
        elif news_item.category == NewsCategory.EARNINGS:
            implications.append("Check options implied volatility")
            implications.append("Consider earnings plays")

        return implications

    def _perform_analysis(self) -> NewsAnalysis | None:
        """Perform comprehensive news analysis."""
        try:
            with self.lock:
                # Count items by category
                items_by_category = defaultdict(int)
                for item in self.news_items.values():
                    items_by_category[item.category] += 1

                # Calculate overall sentiment
                recent_sentiments = []
                cutoff_time = datetime.now(UTC) - timedelta(hours=1)
                for sentiment in self.news_sentiments.values():
                    if sentiment.timestamp > cutoff_time:
                        recent_sentiments.append(sentiment.sentiment_score)

                overall_sentiment = np.mean(recent_sentiments) if recent_sentiments else 0.0

                # Get sentiment trend
                trend_data = self.get_sentiment_trend(60)
                sentiment_trend = trend_data['trend']

                # Find high impact items
                high_impact_items = []
                for item_id, impact in self.news_impacts.items():
                    if impact.impact_level in [MarketImpact.CRITICAL, MarketImpact.HIGH]:
                        if item_id in self.news_items:
                            high_impact_items.append(self.news_items[item_id])

                # Count Fed news
                fed_news_count = sum(1 for item in self.news_items.values()
                                   if item.category == NewsCategory.FED_POLICY)

                # Find breaking news
                breaking_news = [item for item in self.news_items.values()
                               if item.priority == NewsPriority.BREAKING]

                # Generate market implications
                implications = self._generate_market_implications(
                    overall_sentiment, high_impact_items
                )

                # Generate trading signals
                signals = self._generate_trading_signals(
                    overall_sentiment, sentiment_trend, high_impact_items
                )

                return NewsAnalysis(
                    timestamp=datetime.now(UTC),
                    total_items=len(self.news_items),
                    items_by_category=dict(items_by_category),
                    overall_sentiment=overall_sentiment,
                    sentiment_trend=sentiment_trend,
                    high_impact_items=high_impact_items[:5],  # Top 5
                    fed_news_count=fed_news_count,
                    breaking_news=breaking_news[:3],  # Top 3
                    market_implications=implications,
                    trading_signals=signals
                )

        except Exception as e:
            self.logger.error("Error performing analysis: %s", e)
            return None

    def _generate_market_implications(self, sentiment: float,
                                    high_impact_items: list[NewsItem]) -> dict[str, Any]:
        """Generate market implications from news."""
        implications = {
            'volatility_expectation': 'normal',
            'trend_bias': 'neutral',
            'risk_level': 'medium',
            'key_themes': [],
            'sectors_to_watch': []
        }

        # Volatility expectation
        if len(high_impact_items) > 2:
            implications['volatility_expectation'] = 'high'
        elif any(item.category == NewsCategory.FED_POLICY for item in high_impact_items):
            implications['volatility_expectation'] = 'elevated'

        # Trend bias
        if sentiment > 0.3:
            implications['trend_bias'] = 'bullish'
        elif sentiment < -0.3:
            implications['trend_bias'] = 'bearish'

        # Risk level
        if any(item.priority == NewsPriority.BREAKING for item in high_impact_items):
            implications['risk_level'] = 'high'
        elif sentiment < -0.5 or sentiment > 0.5:
            implications['risk_level'] = 'elevated'

        # Extract themes
        themes = set()
        for item in high_impact_items[:5]:
            if item.category == NewsCategory.FED_POLICY:
                themes.add('Monetary Policy')
            elif item.category == NewsCategory.ECONOMIC_DATA:
                themes.add('Economic Data')
            elif item.category == NewsCategory.EARNINGS:
                themes.add('Corporate Earnings')

        implications['key_themes'] = list(themes)

        # Sectors to watch
        sectors = set()
        for item in high_impact_items:
            if item.id in self.news_impacts:
                impact = self.news_impacts[item.id]
                sectors.update(impact.affected_sectors)

        implications['sectors_to_watch'] = list(sectors)[:5]

        return implications

    def _generate_trading_signals(self, sentiment: float, trend: str,
                                high_impact_items: list[NewsItem]) -> list[dict[str, Any]]:
        """Generate trading signals from news analysis."""
        signals = []

        # Sentiment-based signals
        if sentiment > 0.5:
            signals.append({
                'type': 'sentiment',
                'direction': 'bullish',
                'strength': min(sentiment, 1.0),
                'message': 'Strong positive news sentiment',
                'strategy': 'Consider bull put spreads'
            })
        elif sentiment < -0.5:
            signals.append({
                'type': 'sentiment',
                'direction': 'bearish',
                'strength': min(abs(sentiment), 1.0),
                'message': 'Strong negative news sentiment',
                'strategy': 'Consider bear call spreads'
            })

        # Trend-based signals
        if trend == 'improving':
            signals.append({
                'type': 'trend',
                'direction': 'bullish',
                'strength': 0.6,
                'message': 'News sentiment improving',
                'strategy': 'Look for bullish entries'
            })
        elif trend == 'deteriorating':
            signals.append({
                'type': 'trend',
                'direction': 'bearish',
                'strength': 0.6,
                'message': 'News sentiment deteriorating',
                'strategy': 'Consider defensive positions'
            })

        # High impact signals
        for item in high_impact_items[:2]:
            if item.id in self.news_sentiments:
                sentiment_data = self.news_sentiments[item.id]
                if abs(sentiment_data.sentiment_score) > 0.5:
                    signals.append({
                        'type': 'high_impact',
                        'direction': 'caution',
                        'strength': 0.8,
                        'message': f'High impact: {item.title[:50]}...',
                        'strategy': 'Adjust position sizes'
                    })

        # Fed news signal
        fed_items = [item for item in high_impact_items
                    if item.category == NewsCategory.FED_POLICY]
        if fed_items:
            signals.append({
                'type': 'fed_news',
                'direction': 'caution',
                'strength': 0.9,
                'message': 'Fed policy news detected',
                'strategy': 'Expect volatility, consider hedges'
            })

        return signals

    def _handle_breaking_news(self, news_item: NewsItem) -> None:
        """Handle breaking news alerts."""
        try:
            # Notify alert callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(news_item)
                except Exception as e:
                    self.logger.error("Alert callback error: %s", e)

            # Publish breaking news event on the lightweight in-process bus.
            self.event_bus.publish(
                EventType.BREAKING_NEWS,
                {
                    'news_item': news_item,
                    'timestamp': datetime.now(UTC)
                },
            )

            self.logger.warning("BREAKING NEWS: %s", news_item.title)

        except Exception as e:
            self.logger.error("Error handling breaking news: %s", e)

# ==============================================================================
# TEST SECTION
# ==============================================================================
if __name__ == "__main__":
    # Test the news manager
    manager = NewsManager()

    if manager.initialize():

        # Create some test news items
        test_items = [
            {
                'title': 'Federal Reserve Raises Interest Rates by 0.25%',
                'summary': 'The FOMC announced a quarter-point rate hike...',
                'source': 'test',
                'url': 'http://example.com/1'
            },
            {
                'title': 'S&P 500 Hits New All-Time High',
                'summary': 'Stock market rallies on strong earnings...',
                'source': 'test',
                'url': 'http://example.com/2'
            },
            {
                'title': 'Breaking: Major Bank Reports Surprise Loss',
                'summary': 'XYZ Bank shocked investors with quarterly loss...',
                'source': 'test',
                'url': 'http://example.com/3'
            }
        ]

        # Process test items
        for _i, item_data in enumerate(test_items):
            entry = type('Entry', (), item_data)()
            entry.link = item_data['url']
            entry.published_parsed = time.gmtime()
            entry.tags = []
            entry.author = 'Test Author'

            news_item = manager._create_news_item('test', entry)
            if news_item:
                manager.news_items[news_item.id] = news_item

                # Analyze
                sentiment = manager._analyze_sentiment(news_item)
                if sentiment:
                    manager.news_sentiments[news_item.id] = sentiment

                impact = manager._assess_impact(news_item, sentiment)
                if impact:
                    manager.news_impacts[news_item.id] = impact

        # Wait for analysis
        time.sleep(2)  # thread-safe: time.sleep() intentional

        # Get analysis
        analysis = manager.get_current_analysis()
        if analysis:

            if analysis.high_impact_items:
                for _item in analysis.high_impact_items:
                    pass

            if analysis.trading_signals:
                for _signal in analysis.trading_signals:
                    pass

        # Search test
        results = manager.search_news("Federal Reserve")

        # Stop manager
        manager.stop()
