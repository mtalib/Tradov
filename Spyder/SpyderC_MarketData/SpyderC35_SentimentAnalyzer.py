#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC35_SentimentAnalyzer.py
Purpose: Real-time sentiment analysis from news, social media, and market data

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-12-27

Module Description:
    This module provides comprehensive sentiment analysis capabilities:
    - News sentiment scoring using FinBERT (financial BERT)
    - Social media monitoring (Reddit, Twitter/X)
    - SEC filing sentiment analysis
    - Composite sentiment scoring combining multiple sources

    Research shows NLP sentiment strategies achieve ~62% accuracy and
    combined with technical analysis can generate significant alpha.

References:
    - FinBERT: Financial Sentiment Analysis with BERT
    - Sentiment Analysis Stock Market (AIMultiple Research)
    - NLP in Trading (LuxAlgo)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re
import time
from typing import Any, Callable
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import requests

# NLP Libraries (optional - graceful degradation)
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    HAS_VADER = True
except ImportError:
    HAS_VADER = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
FINBERT_MODEL = "ProsusAI/finbert"
NEWS_CACHE_TTL = 300  # 5 minutes
MAX_NEWS_ITEMS = 100
SOCIAL_CACHE_TTL = 60  # 1 minute
REDDIT_USER_AGENT = "SpyderBot/1.0"

# API Endpoints
ALPHA_VANTAGE_NEWS_URL = "https://www.alphavantage.co/query"
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
REDDIT_API_URL = "https://oauth.reddit.com"

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# ENUMS
# ==============================================================================
class SentimentType(Enum):
    """Sentiment classification."""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class SourceType(Enum):
    """Sentiment data source."""
    NEWS = "news"
    REDDIT = "reddit"
    TWITTER = "twitter"
    SEC_FILING = "sec_filing"
    EARNINGS_CALL = "earnings_call"
    ANALYST_REPORT = "analyst_report"


class SentimentModel(Enum):
    """Sentiment analysis model type."""
    FINBERT = "finbert"
    VADER = "vader"
    TEXTBLOB = "textblob"
    ENSEMBLE = "ensemble"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class SentimentScore:
    """Individual sentiment score."""
    text: str
    source: SourceType
    timestamp: datetime
    score: float  # -1 to 1
    sentiment: SentimentType
    confidence: float
    model_used: SentimentModel
    ticker: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_significant(self) -> bool:
        """Check if sentiment is significant (not neutral with high confidence)."""
        return (
            self.sentiment != SentimentType.NEUTRAL and
            self.confidence >= 0.6
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text[:200],  # Truncate for storage
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "score": self.score,
            "sentiment": self.sentiment.value,
            "confidence": self.confidence,
            "model_used": self.model_used.value,
            "ticker": self.ticker,
            "is_significant": self.is_significant,
        }


@dataclass
class NewsItem:
    """News article data."""
    title: str
    description: str
    url: str
    source: str
    published: datetime
    tickers: list[str]
    sentiment: SentimentScore | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description[:500],
            "url": self.url,
            "source": self.source,
            "published": self.published.isoformat(),
            "tickers": self.tickers,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
        }


@dataclass
class SocialPost:
    """Social media post data."""
    platform: str  # reddit, twitter
    content: str
    author: str
    timestamp: datetime
    upvotes: int = 0
    comments: int = 0
    subreddit: str | None = None
    sentiment: SentimentScore | None = None

    @property
    def engagement_score(self) -> float:
        """Calculate engagement score."""
        return (self.upvotes * 1.0 + self.comments * 2.0) / 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "platform": self.platform,
            "content": self.content[:500],
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "upvotes": self.upvotes,
            "comments": self.comments,
            "engagement_score": self.engagement_score,
            "sentiment": self.sentiment.to_dict() if self.sentiment else None,
        }


@dataclass
class CompositeSentiment:
    """Aggregated sentiment from multiple sources."""
    symbol: str
    timestamp: datetime
    overall_score: float  # -1 to 1
    overall_sentiment: SentimentType
    confidence: float
    source_scores: dict[str, float]
    source_counts: dict[str, int]
    bullish_count: int
    bearish_count: int
    neutral_count: int
    trend: str  # improving, stable, deteriorating
    news_items: list[NewsItem] = field(default_factory=list)
    social_posts: list[SocialPost] = field(default_factory=list)

    @property
    def sentiment_ratio(self) -> float:
        """Calculate bullish to bearish ratio."""
        if self.bearish_count == 0:
            return float('inf') if self.bullish_count > 0 else 1.0
        return self.bullish_count / self.bearish_count

    @property
    def is_actionable(self) -> bool:
        """Check if sentiment is actionable for trading."""
        return (
            self.overall_sentiment != SentimentType.NEUTRAL and
            self.confidence >= 0.6 and
            (self.bullish_count + self.bearish_count) >= 5
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": self.overall_score,
            "overall_sentiment": self.overall_sentiment.value,
            "confidence": self.confidence,
            "source_scores": self.source_scores,
            "source_counts": self.source_counts,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "sentiment_ratio": self.sentiment_ratio if self.sentiment_ratio != float('inf') else 999,
            "trend": self.trend,
            "is_actionable": self.is_actionable,
            "top_news": [n.to_dict() for n in self.news_items[:5]],
        }


# ==============================================================================
# SENTIMENT MODELS
# ==============================================================================
class BaseSentimentModel(ABC):
    """Base class for sentiment models."""

    @abstractmethod
    def analyze(self, text: str) -> tuple[float, float]:
        """
        Analyze text sentiment.

        Returns:
            Tuple of (score, confidence) where score is -1 to 1
        """
        pass


class FinBERTModel(BaseSentimentModel):
    """FinBERT sentiment model for financial text."""

    def __init__(self):
        if not HAS_TRANSFORMERS:
            raise ImportError("transformers library required for FinBERT")

        logger.info("Loading FinBERT model...")
        self.tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL)
        self.model.eval()

        # Move to GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        logger.info(f"FinBERT loaded on {self.device}")

    def analyze(self, text: str) -> tuple[float, float]:
        """Analyze text using FinBERT."""
        try:
            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)

            # Get prediction
            with torch.no_grad():
                outputs = self.model(**inputs)
                probabilities = torch.softmax(outputs.logits, dim=1)

            # FinBERT outputs: [negative, neutral, positive]
            probs = probabilities.cpu().numpy()[0]

            # Calculate score (-1 to 1)
            score = probs[2] - probs[0]  # positive - negative

            # Confidence is max probability
            confidence = float(max(probs))

            return score, confidence

        except Exception as e:
            logger.error(f"FinBERT analysis error: {e}")
            return 0.0, 0.0


class VADERModel(BaseSentimentModel):
    """VADER sentiment model (rule-based, good for social media)."""

    def __init__(self):
        if not HAS_VADER:
            raise ImportError("vaderSentiment library required")

        self.analyzer = SentimentIntensityAnalyzer()
        logger.info("VADER model initialized")

    def analyze(self, text: str) -> tuple[float, float]:
        """Analyze text using VADER."""
        try:
            scores = self.analyzer.polarity_scores(text)

            # Compound score is already -1 to 1
            score = scores['compound']

            # Confidence based on how extreme the score is
            confidence = abs(score)

            return score, confidence

        except Exception as e:
            logger.error(f"VADER analysis error: {e}")
            return 0.0, 0.0


class TextBlobModel(BaseSentimentModel):
    """TextBlob sentiment model (simple, good for general text)."""

    def __init__(self):
        if not HAS_TEXTBLOB:
            raise ImportError("textblob library required")
        logger.info("TextBlob model initialized")

    def analyze(self, text: str) -> tuple[float, float]:
        """Analyze text using TextBlob."""
        try:
            blob = TextBlob(text)

            # Polarity is -1 to 1
            score = blob.sentiment.polarity

            # Subjectivity as proxy for confidence (0 = objective, 1 = subjective)
            # More subjective = more opinionated = higher confidence
            confidence = blob.sentiment.subjectivity

            return score, confidence

        except Exception as e:
            logger.error(f"TextBlob analysis error: {e}")
            return 0.0, 0.0


class EnsembleSentimentModel(BaseSentimentModel):
    """Ensemble of multiple sentiment models."""

    def __init__(self, use_finbert: bool = True):
        self.models: list[tuple[BaseSentimentModel, float]] = []

        # Add available models with weights
        if HAS_VADER:
            self.models.append((VADERModel(), 0.3))

        if HAS_TEXTBLOB:
            self.models.append((TextBlobModel(), 0.2))

        if use_finbert and HAS_TRANSFORMERS:
            try:
                self.models.append((FinBERTModel(), 0.5))
            except Exception as e:
                logger.warning(f"Could not load FinBERT: {e}")

        if not self.models:
            raise ImportError("No sentiment models available")

        # Normalize weights
        total_weight = sum(w for _, w in self.models)
        self.models = [(m, w / total_weight) for m, w in self.models]

        logger.info(f"Ensemble model initialized with {len(self.models)} models")

    def analyze(self, text: str) -> tuple[float, float]:
        """Analyze using weighted ensemble."""
        weighted_score = 0.0
        weighted_confidence = 0.0

        for model, weight in self.models:
            score, confidence = model.analyze(text)
            weighted_score += score * weight
            weighted_confidence += confidence * weight

        return weighted_score, weighted_confidence


# ==============================================================================
# NEWS SOURCE PROVIDERS
# ==============================================================================
class BaseNewsSource(ABC):
    """
    Abstract base class for news data sources.

    All concrete news sources must implement :meth:`fetch` so that
    :class:`SentimentAnalyzer` can iterate over a pluggable list of sources
    without knowing their implementation details.

    Example (custom source)::

        class MySource(BaseNewsSource):
            @property
            def source_name(self) -> str:
                return "my_source"

            def fetch(self, ticker: str, limit: int) -> List[NewsItem]:
                ...
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source identifier used in logs."""

    @abstractmethod
    def fetch(self, ticker: str, limit: int) -> list[NewsItem]:
        """
        Fetch recent news items for *ticker*.

        Args:
            ticker: Stock ticker symbol (e.g. ``"SPY"``)
            limit:  Maximum number of :class:`NewsItem` objects to return.

        Returns:
            List of :class:`NewsItem`.  Must never raise — return an empty
            list on any error so the caller can try the next source.
        """


class AlphaVantageNewsSource(BaseNewsSource):
    """
    News source backed by the Alpha Vantage ``NEWS_SENTIMENT`` endpoint.

    Requires a free/premium Alpha Vantage API key.
    Env var: ``ALPHA_VANTAGE_API_KEY``
    """

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: Alpha Vantage API key.
        """
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "alpha_vantage"

    def fetch(self, ticker: str, limit: int) -> list[NewsItem]:
        """Fetch from Alpha Vantage NEWS_SENTIMENT endpoint."""
        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "limit": limit,
                "apikey": self._api_key,
            }
            response = requests.get(
                ALPHA_VANTAGE_NEWS_URL, params=params, timeout=30
            )
            if response.status_code != 200:
                logger.warning(
                    f"AlphaVantage news HTTP {response.status_code} for {ticker}"
                )
                return []

            feed = response.json().get("feed", [])
            items: list[NewsItem] = []
            for entry in feed:
                try:
                    published = datetime.strptime(
                        entry.get("time_published", "")[:15], "%Y%m%dT%H%M%S"
                    )
                except Exception:
                    published = datetime.now()

                items.append(NewsItem(
                    title=entry.get("title", ""),
                    description=entry.get("summary", ""),
                    url=entry.get("url", ""),
                    source=entry.get("source", "alpha_vantage"),
                    published=published,
                    tickers=[
                        t.get("ticker", "")
                        for t in entry.get("ticker_sentiment", [])
                    ],
                ))
            return items

        except Exception as exc:
            logger.error(f"AlphaVantageNewsSource.fetch error: {exc}")
            return []


class FinnhubNewsSource(BaseNewsSource):
    """
    News source backed by the Finnhub ``/company-news`` endpoint.

    Finnhub offers a generous free tier (60 req/min).  Register at
    https://finnhub.io/ to obtain an API key.
    Env var: ``FINNHUB_API_KEY``

    .. note::
        This is a **stub implementation**.  The HTTP call is functional but
        error‑handling and field normalisation may need tuning once live data
        is observed.
    """

    def __init__(self, api_key: str) -> None:
        """
        Args:
            api_key: Finnhub API key.
        """
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "finnhub"

    def fetch(self, ticker: str, limit: int) -> list[NewsItem]:
        """Fetch from Finnhub /company-news endpoint."""
        try:
            today = datetime.utcnow()
            week_ago = today - timedelta(days=7)
            params = {
                "symbol": ticker,
                "from": week_ago.strftime("%Y-%m-%d"),
                "to": today.strftime("%Y-%m-%d"),
                "token": self._api_key,
            }
            response = requests.get(
                FINNHUB_NEWS_URL, params=params, timeout=30
            )
            if response.status_code != 200:
                logger.warning(
                    f"Finnhub news HTTP {response.status_code} for {ticker}"
                )
                return []

            entries = response.json()
            if not isinstance(entries, list):
                return []

            items: list[NewsItem] = []
            for entry in entries[:limit]:
                try:
                    published = datetime.utcfromtimestamp(entry.get("datetime", 0))
                except Exception:
                    published = datetime.now()

                items.append(NewsItem(
                    title=entry.get("headline", ""),
                    description=entry.get("summary", ""),
                    url=entry.get("url", ""),
                    source=entry.get("source", "finnhub"),
                    published=published,
                    tickers=[ticker],
                ))
            return items

        except Exception as exc:
            logger.error(f"FinnhubNewsSource.fetch error: {exc}")
            return []


class YahooFinanceRSSNewsSource(BaseNewsSource):
    """
    Key‑free news source backed by the Yahoo Finance RSS feed.

    No API key required.  RSS is a lightweight fallback suitable for use when
    paid API keys are absent.  Results are limited to ~20 headlines.

    .. note::
        This is a **stub implementation**.  Yahoo may throttle or block
        automated requests; add appropriate rate‑limiting if deployed at high
        frequency.
    """

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (compatible; SpyderBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    @property
    def source_name(self) -> str:
        return "yahoo_rss"

    def fetch(self, ticker: str, limit: int) -> list[NewsItem]:
        """Fetch headlines from the Yahoo Finance RSS feed for *ticker*."""
        try:
            params = {"s": ticker, "region": "US", "lang": "en-US"}
            response = requests.get(
                YAHOO_RSS_URL,
                params=params,
                headers=self._HEADERS,
                timeout=15,
            )
            if response.status_code != 200:
                logger.warning(
                    f"YahooRSS HTTP {response.status_code} for {ticker}"
                )
                return []

            root = ET.fromstring(response.text)
            channel = root.find("channel")
            if channel is None:
                return []

            items: list[NewsItem] = []
            for item_el in list(channel.findall("item"))[:limit]:
                title = (item_el.findtext("title") or "").strip()
                description = (item_el.findtext("description") or "").strip()
                url = (item_el.findtext("link") or "").strip()
                pub_str = (item_el.findtext("pubDate") or "").strip()

                try:
                    # RFC 2822 date: "Mon, 01 Jan 2024 12:00:00 +0000"
                    from email.utils import parsedate_to_datetime
                    published = parsedate_to_datetime(pub_str).replace(tzinfo=None)
                except Exception:
                    published = datetime.now()

                items.append(NewsItem(
                    title=title,
                    description=description,
                    url=url,
                    source="yahoo_finance",
                    published=published,
                    tickers=[ticker],
                ))
            return items

        except Exception as exc:
            logger.error(f"YahooFinanceRSSNewsSource.fetch error: {exc}")
            return []


# ==============================================================================
# MAIN SENTIMENT ANALYZER
# ==============================================================================
class SentimentAnalyzer:
    """
    Comprehensive sentiment analyzer for options trading.

    Provides:
    - News sentiment analysis
    - Social media monitoring (Reddit)
    - Composite sentiment scoring
    - Historical sentiment tracking

    Example:
        >>> analyzer = SentimentAnalyzer()
        >>> sentiment = analyzer.get_composite_sentiment("SPY")
        >>> print(f"Overall: {sentiment.overall_sentiment.value}")
        >>> print(f"Score: {sentiment.overall_score:.2f}")
        >>> print(f"Confidence: {sentiment.confidence:.2%}")
    """

    def __init__(
        self,
        alpha_vantage_key: str | None = None,
        finnhub_key: str | None = None,
        reddit_credentials: dict[str, str] | None = None,
        model_type: SentimentModel = SentimentModel.ENSEMBLE,
        use_finbert: bool = True,
        news_sources: list[BaseNewsSource] | None = None,
    ):
        """
        Initialize Sentiment Analyzer.

        Args:
            alpha_vantage_key: Alpha Vantage API key for news.
            finnhub_key: Finnhub API key for news (free tier available).
            reddit_credentials: Reddit API credentials.
            model_type: Sentiment model to use.
            use_finbert: Use FinBERT in ensemble (requires transformers).
            news_sources: Explicit list of :class:`BaseNewsSource` instances to
                use in priority order.  When *None* (default), sources are
                auto-built from the supplied API keys: AlphaVantage (if key
                present), Finnhub (if key present), and YahooFinanceRSS as a
                zero-key fallback.
        """
        self.alpha_vantage_key = alpha_vantage_key
        self.finnhub_key = finnhub_key
        self.reddit_credentials = reddit_credentials

        # Build news source pipeline ------------------------------------------
        if news_sources is not None:
            self._news_sources: list[BaseNewsSource] = news_sources
        else:
            self._news_sources = []
            if alpha_vantage_key:
                self._news_sources.append(AlphaVantageNewsSource(alpha_vantage_key))
            if finnhub_key:
                self._news_sources.append(FinnhubNewsSource(finnhub_key))
            # Always include the key-free RSS fallback last.
            self._news_sources.append(YahooFinanceRSSNewsSource())

        source_names = [s.source_name for s in self._news_sources]
        logger.info(f"SentimentAnalyzer news sources: {source_names}")

        # Initialize sentiment model
        self.model_type = model_type
        self._init_sentiment_model(model_type, use_finbert)

        # Caches
        self._news_cache: dict[str, tuple[list[NewsItem], datetime]] = {}
        self._social_cache: dict[str, tuple[list[SocialPost], datetime]] = {}
        self._sentiment_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

        # Callbacks
        self._sentiment_callbacks: list[Callable[[SentimentScore], None]] = []

        logger.info(f"SentimentAnalyzer initialized with {model_type.value} model")

    def _init_sentiment_model(self, model_type: SentimentModel, use_finbert: bool):
        """Initialize the sentiment model."""
        try:
            if model_type == SentimentModel.FINBERT:
                if not HAS_TRANSFORMERS:
                    raise ImportError("transformers required for FinBERT")
                self.sentiment_model = FinBERTModel()
            elif model_type == SentimentModel.VADER:
                if not HAS_VADER:
                    raise ImportError("vaderSentiment required")
                self.sentiment_model = VADERModel()
            elif model_type == SentimentModel.TEXTBLOB:
                if not HAS_TEXTBLOB:
                    raise ImportError("textblob required")
                self.sentiment_model = TextBlobModel()
            else:  # ENSEMBLE
                self.sentiment_model = EnsembleSentimentModel(use_finbert)

        except ImportError as e:
            logger.warning(f"Could not load {model_type.value}: {e}")
            # Fallback to simplest available
            if HAS_VADER:
                self.sentiment_model = VADERModel()
                self.model_type = SentimentModel.VADER
            elif HAS_TEXTBLOB:
                self.sentiment_model = TextBlobModel()
                self.model_type = SentimentModel.TEXTBLOB
            else:
                raise ImportError("No sentiment analysis libraries available")

    # ==========================================================================
    # NEWS ANALYSIS
    # ==========================================================================

    def analyze_news(
        self,
        ticker: str,
        limit: int = 50,
        use_cache: bool = True
    ) -> list[NewsItem]:
        """
        Fetch and analyze news for a ticker.

        Args:
            ticker: Stock ticker symbol
            limit: Maximum news items to fetch
            use_cache: Use cached news if available

        Returns:
            List of NewsItem with sentiment scores

        Example:
            >>> news = analyzer.analyze_news("SPY")
            >>> for item in news[:5]:
            ...     print(f"{item.title}")
            ...     print(f"  Sentiment: {item.sentiment.sentiment.value}")
        """
        # Check cache
        if use_cache and ticker in self._news_cache:
            cached_news, cache_time = self._news_cache[ticker]
            if (datetime.now() - cache_time).seconds < NEWS_CACHE_TTL:
                return cached_news

        # Fetch news from the configured source pipeline
        news_items: list[NewsItem] = []

        for source in self._news_sources:
            if len(news_items) >= limit:
                break
            remaining = limit - len(news_items)
            try:
                fetched = source.fetch(ticker, remaining)
                news_items.extend(fetched)
                logger.debug(
                    f"News: {len(fetched)} items from {source.source_name} for {ticker}"
                )
            except Exception as exc:  # pragma: no cover  — source.fetch should not raise
                logger.error(f"News source {source.source_name} raised unexpectedly: {exc}")

        # Analyze sentiment for each item
        for item in news_items:
            text = f"{item.title}. {item.description}"
            item.sentiment = self._analyze_text(text, SourceType.NEWS, ticker)

        # Sort by recency
        news_items.sort(key=lambda x: x.published, reverse=True)

        # Cache results
        self._news_cache[ticker] = (news_items[:limit], datetime.now())

        logger.info(f"Analyzed {len(news_items)} news items for {ticker}")
        return news_items[:limit]

    def _fetch_alpha_vantage_news(self, ticker: str, limit: int) -> list[NewsItem]:
        """
        Fetch news from Alpha Vantage (legacy helper kept for backward compat).

        .. deprecated::
            Use :class:`AlphaVantageNewsSource` via the ``news_sources``
            constructor parameter instead.
        """
        if not self.alpha_vantage_key:
            return []
        return AlphaVantageNewsSource(self.alpha_vantage_key).fetch(ticker, limit)

    # ==========================================================================
    # SOCIAL MEDIA ANALYSIS
    # ==========================================================================

    def monitor_social_media(
        self,
        tickers: list[str],
        subreddits: list[str] | None = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> dict[str, list[SocialPost]]:
        """
        Monitor social media for ticker mentions.

        Args:
            tickers: List of tickers to monitor
            subreddits: Reddit subreddits to monitor
            limit: Maximum posts per ticker
            use_cache: Use cached results if available

        Returns:
            Dictionary mapping ticker to list of SocialPost

        Example:
            >>> posts = analyzer.monitor_social_media(["SPY", "QQQ"])
            >>> for ticker, ticker_posts in posts.items():
            ...     print(f"{ticker}: {len(ticker_posts)} posts")
        """
        subreddits = subreddits or ["wallstreetbets", "options", "stocks", "investing"]

        results: dict[str, list[SocialPost]] = {}

        for ticker in tickers:
            # Check cache
            cache_key = f"{ticker}_reddit"
            if use_cache and cache_key in self._social_cache:
                cached_posts, cache_time = self._social_cache[cache_key]
                if (datetime.now() - cache_time).seconds < SOCIAL_CACHE_TTL:
                    results[ticker] = cached_posts
                    continue

            # Fetch Reddit posts
            posts = self._fetch_reddit_posts(ticker, subreddits, limit)

            # Analyze sentiment
            for post in posts:
                post.sentiment = self._analyze_text(post.content, SourceType.REDDIT, ticker)

            # Cache results
            self._social_cache[cache_key] = (posts, datetime.now())
            results[ticker] = posts

        return results

    def _fetch_reddit_posts(
        self,
        ticker: str,
        subreddits: list[str],
        limit: int
    ) -> list[SocialPost]:
        """Fetch Reddit posts mentioning ticker."""
        posts = []

        # Use Reddit API if credentials available
        if self.reddit_credentials:
            posts = self._fetch_reddit_api(ticker, subreddits, limit)
        else:
            # Fallback to public JSON endpoints
            posts = self._fetch_reddit_public(ticker, subreddits, limit)

        return posts

    def _fetch_reddit_public(
        self,
        ticker: str,
        subreddits: list[str],
        limit: int
    ) -> list[SocialPost]:
        """Fetch Reddit posts via public JSON endpoints."""
        posts = []

        for subreddit in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                params = {
                    "q": f"${ticker} OR {ticker}",
                    "sort": "new",
                    "limit": limit // len(subreddits),
                    "restrict_sr": "on",
                    "t": "day"
                }
                headers = {"User-Agent": REDDIT_USER_AGENT}

                response = requests.get(url, params=params, headers=headers, timeout=30)

                if response.status_code != 200:
                    continue

                data = response.json()
                children = data.get("data", {}).get("children", [])

                for child in children:
                    post_data = child.get("data", {})

                    # Check if ticker is actually mentioned
                    title = post_data.get("title", "")
                    selftext = post_data.get("selftext", "")
                    content = f"{title} {selftext}"

                    if ticker.upper() not in content.upper():
                        continue

                    try:
                        created = datetime.fromtimestamp(post_data.get("created_utc", 0))
                    except Exception:
                        created = datetime.now()

                    posts.append(SocialPost(
                        platform="reddit",
                        content=content[:1000],
                        author=post_data.get("author", "unknown"),
                        timestamp=created,
                        upvotes=post_data.get("ups", 0),
                        comments=post_data.get("num_comments", 0),
                        subreddit=subreddit
                    ))

                # Rate limiting
                time.sleep(0.5)  # thread-safe: time.sleep() intentional

            except Exception as e:
                logger.error(f"Reddit fetch error for r/{subreddit}: {e}")

        return posts

    def _fetch_reddit_api(
        self,
        ticker: str,
        subreddits: list[str],
        limit: int
    ) -> list[SocialPost]:
        """Fetch Reddit posts via OAuth API."""
        # This would use proper Reddit OAuth authentication
        # For now, fallback to public endpoint
        return self._fetch_reddit_public(ticker, subreddits, limit)

    # ==========================================================================
    # CORE ANALYSIS
    # ==========================================================================

    def _analyze_text(
        self,
        text: str,
        source: SourceType,
        ticker: str | None = None
    ) -> SentimentScore:
        """
        Analyze text sentiment.

        Args:
            text: Text to analyze
            source: Source type
            ticker: Associated ticker

        Returns:
            SentimentScore with analysis results
        """
        # Clean text
        text = self._clean_text(text)

        if not text:
            return SentimentScore(
                text="",
                source=source,
                timestamp=datetime.now(),
                score=0.0,
                sentiment=SentimentType.NEUTRAL,
                confidence=0.0,
                model_used=self.model_type,
                ticker=ticker
            )

        # Get sentiment score
        score, confidence = self.sentiment_model.analyze(text)

        # Classify sentiment
        sentiment = self._classify_sentiment(score, confidence)

        result = SentimentScore(
            text=text[:500],
            source=source,
            timestamp=datetime.now(),
            score=score,
            sentiment=sentiment,
            confidence=confidence,
            model_used=self.model_type,
            ticker=ticker
        )

        # Store in history
        if ticker:
            self._sentiment_history[ticker].append(result)

        # Trigger callbacks
        for callback in self._sentiment_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Sentiment callback error: {e}")

        return result

    def _clean_text(self, text: str) -> str:
        """Clean and preprocess text."""
        if not text:
            return ""

        # Remove URLs
        text = re.sub(r'http\S+|www\S+', '', text)

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove special characters but keep $TICKER format
        text = re.sub(r'[^\w\s$@#]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    def _classify_sentiment(self, score: float, confidence: float) -> SentimentType:
        """Classify sentiment from score."""
        if confidence < 0.3:
            return SentimentType.NEUTRAL

        if score > 0.5:
            return SentimentType.VERY_BULLISH
        elif score > 0.2:
            return SentimentType.BULLISH
        elif score > -0.2:
            return SentimentType.NEUTRAL
        elif score > -0.5:
            return SentimentType.BEARISH
        else:
            return SentimentType.VERY_BEARISH

    # ==========================================================================
    # COMPOSITE SENTIMENT
    # ==========================================================================

    def get_composite_sentiment(
        self,
        ticker: str,
        include_news: bool = True,
        include_social: bool = True,
        lookback_hours: int = 24
    ) -> CompositeSentiment:
        """
        Get composite sentiment from all sources.

        Args:
            ticker: Stock ticker
            include_news: Include news sentiment
            include_social: Include social media sentiment
            lookback_hours: Time window for analysis

        Returns:
            CompositeSentiment with aggregated analysis

        Example:
            >>> sentiment = analyzer.get_composite_sentiment("SPY")
            >>> print(f"Overall: {sentiment.overall_sentiment.value}")
            >>> print(f"News score: {sentiment.source_scores.get('news', 0):.2f}")
            >>> print(f"Trend: {sentiment.trend}")
        """
        all_sentiments: list[SentimentScore] = []
        news_items: list[NewsItem] = []
        social_posts: list[SocialPost] = []

        # Collect news sentiment
        if include_news:
            news_items = self.analyze_news(ticker)
            for item in news_items:
                if item.sentiment:
                    all_sentiments.append(item.sentiment)

        # Collect social sentiment
        if include_social:
            social_data = self.monitor_social_media([ticker])
            social_posts = social_data.get(ticker, [])
            for post in social_posts:
                if post.sentiment:
                    all_sentiments.append(post.sentiment)

        # Filter by lookback window
        cutoff = datetime.now() - timedelta(hours=lookback_hours)
        recent_sentiments = [s for s in all_sentiments if s.timestamp >= cutoff]

        if not recent_sentiments:
            return CompositeSentiment(
                symbol=ticker,
                timestamp=datetime.now(),
                overall_score=0.0,
                overall_sentiment=SentimentType.NEUTRAL,
                confidence=0.0,
                source_scores={},
                source_counts={},
                bullish_count=0,
                bearish_count=0,
                neutral_count=0,
                trend="stable",
                news_items=news_items,
                social_posts=social_posts
            )

        # Calculate source-specific scores
        source_scores: dict[str, float] = {}
        source_counts: dict[str, int] = defaultdict(int)

        for sentiment in recent_sentiments:
            source = sentiment.source.value
            source_counts[source] += 1

            if source not in source_scores:
                source_scores[source] = []
            source_scores[source].append(sentiment.score)

        # Average scores per source
        for source in source_scores:
            scores = source_scores[source]
            source_scores[source] = sum(scores) / len(scores)

        # Calculate overall score (weighted by source)
        source_weights = {
            SourceType.NEWS.value: 1.5,
            SourceType.REDDIT.value: 1.0,
            SourceType.TWITTER.value: 1.0,
            SourceType.SEC_FILING.value: 2.0,
            SourceType.ANALYST_REPORT.value: 2.0,
        }

        weighted_sum = 0
        weight_sum = 0
        for source, score in source_scores.items():
            weight = source_weights.get(source, 1.0)
            weighted_sum += score * weight
            weight_sum += weight

        overall_score = weighted_sum / weight_sum if weight_sum > 0 else 0

        # Count sentiments
        bullish = sum(1 for s in recent_sentiments
                     if s.sentiment in [SentimentType.BULLISH, SentimentType.VERY_BULLISH])
        bearish = sum(1 for s in recent_sentiments
                     if s.sentiment in [SentimentType.BEARISH, SentimentType.VERY_BEARISH])
        neutral = len(recent_sentiments) - bullish - bearish

        # Calculate confidence
        confidence = sum(s.confidence for s in recent_sentiments) / len(recent_sentiments)

        # Determine trend
        trend = self._calculate_trend(ticker, overall_score)

        return CompositeSentiment(
            symbol=ticker,
            timestamp=datetime.now(),
            overall_score=overall_score,
            overall_sentiment=self._classify_sentiment(overall_score, confidence),
            confidence=confidence,
            source_scores=source_scores,
            source_counts=dict(source_counts),
            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,
            trend=trend,
            news_items=news_items,
            social_posts=social_posts
        )

    def _calculate_trend(self, ticker: str, current_score: float) -> str:
        """Calculate sentiment trend over time."""
        history = list(self._sentiment_history.get(ticker, []))

        if len(history) < 10:
            return "stable"

        # Compare recent vs older average
        recent = [s.score for s in history[-10:]]
        older = [s.score for s in history[-30:-10]] if len(history) >= 30 else []

        if not older:
            return "stable"

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        diff = recent_avg - older_avg

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "deteriorating"
        else:
            return "stable"

    # ==========================================================================
    # SEC FILING ANALYSIS
    # ==========================================================================

    def analyze_sec_filings(
        self,
        ticker: str,
        filing_types: list[str] | None = None
    ) -> list[SentimentScore]:
        """
        Analyze SEC filings for sentiment.

        Args:
            ticker: Stock ticker
            filing_types: Types of filings to analyze (8-K, 10-K, 10-Q)

        Returns:
            List of SentimentScore for each filing
        """
        filing_types = filing_types or ["8-K", "10-K", "10-Q"]

        # This would integrate with SEC EDGAR API
        # For now, return placeholder
        logger.info(f"SEC filing analysis for {ticker} (not yet implemented)")
        return []

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================

    def register_callback(self, callback: Callable[[SentimentScore], None]):
        """Register callback for new sentiment scores."""
        self._sentiment_callbacks.append(callback)

    # ==========================================================================
    # HISTORY & ANALYTICS
    # ==========================================================================

    def get_sentiment_history(
        self,
        ticker: str,
        hours: int = 24
    ) -> pd.DataFrame:
        """
        Get historical sentiment data.

        Args:
            ticker: Stock ticker
            hours: Hours of history to return

        Returns:
            DataFrame with sentiment history
        """
        history = list(self._sentiment_history.get(ticker, []))

        if not history:
            return pd.DataFrame()

        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [s for s in history if s.timestamp >= cutoff]

        df = pd.DataFrame([s.to_dict() for s in recent])

        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp').sort_index()

        return df

    def get_sentiment_summary(self, ticker: str) -> dict[str, Any]:
        """Get quick sentiment summary for a ticker."""
        composite = self.get_composite_sentiment(ticker)

        return {
            "ticker": ticker,
            "sentiment": composite.overall_sentiment.value,
            "score": composite.overall_score,
            "confidence": composite.confidence,
            "trend": composite.trend,
            "news_count": len(composite.news_items),
            "social_count": len(composite.social_posts),
            "bullish_ratio": composite.bullish_count / max(
                composite.bullish_count + composite.bearish_count, 1
            ),
            "is_actionable": composite.is_actionable,
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_sentiment_analyzer_from_env() -> 'SentimentAnalyzer':
    """
    Create :class:`SentimentAnalyzer` from environment variables.

    Reads the following env vars (all optional):

    * ``ALPHA_VANTAGE_API_KEY`` — Alpha Vantage news key
    * ``FINNHUB_API_KEY``       — Finnhub news key (free tier)
    * ``REDDIT_CLIENT_ID``      — Reddit OAuth app client ID
    * ``REDDIT_CLIENT_SECRET``  — Reddit OAuth app secret
    * ``REDDIT_USERNAME``       — Reddit username
    * ``REDDIT_PASSWORD``       — Reddit password
    * ``SENTIMENT_MODEL``       — ``ensemble`` (default), ``finbert``, ``vader``, ``textblob``
    * ``USE_FINBERT``           — ``true`` / ``false`` (default ``true``)

    The YahooFinance RSS source is always appended as a key-free fallback.
    """
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    finnhub_key = os.getenv("FINNHUB_API_KEY")

    # Reddit credentials
    reddit_creds = None
    if os.getenv("REDDIT_CLIENT_ID"):
        reddit_creds = {
            "client_id": os.getenv("REDDIT_CLIENT_ID"),
            "client_secret": os.getenv("REDDIT_CLIENT_SECRET"),
            "username": os.getenv("REDDIT_USERNAME"),
            "password": os.getenv("REDDIT_PASSWORD"),
        }

    # Model selection
    model_type = os.getenv("SENTIMENT_MODEL", "ensemble")
    model_map = {
        "finbert": SentimentModel.FINBERT,
        "vader": SentimentModel.VADER,
        "textblob": SentimentModel.TEXTBLOB,
        "ensemble": SentimentModel.ENSEMBLE,
    }

    return SentimentAnalyzer(
        alpha_vantage_key=alpha_vantage_key,
        finnhub_key=finnhub_key,
        reddit_credentials=reddit_creds,
        model_type=model_map.get(model_type, SentimentModel.ENSEMBLE),
        use_finbert=os.getenv("USE_FINBERT", "true").lower() == "true",
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Test available models

    # Initialize analyzer
    try:
        analyzer = SentimentAnalyzer(
            model_type=SentimentModel.ENSEMBLE,
            use_finbert=False  # Skip FinBERT for faster testing
        )

        # Test individual analysis
        test_texts = [
            "SPY is showing strong bullish momentum, expecting new all-time highs!",
            "Market crash incoming, sell everything before it's too late.",
            "The market opened flat today with mixed signals.",
            "BREAKING: Fed announces surprise rate cut, stocks surge!",
        ]

        for text in test_texts:
            sentiment = analyzer._analyze_text(text, SourceType.NEWS, "SPY")

        # Test composite sentiment
        composite = analyzer.get_composite_sentiment("SPY")

    except ImportError:
        pass
