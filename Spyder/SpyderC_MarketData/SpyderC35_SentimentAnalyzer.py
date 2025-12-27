#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import json
import time
import asyncio
import threading
from typing import Dict, List, Optional, Any, Tuple, Callable
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque, defaultdict
from abc import ABC, abstractmethod
import hashlib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
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
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
FINBERT_MODEL = "ProsusAI/finbert"
NEWS_CACHE_TTL = 300  # 5 minutes
MAX_NEWS_ITEMS = 100
SOCIAL_CACHE_TTL = 60  # 1 minute
REDDIT_USER_AGENT = "SpyderBot/1.0"

# API Endpoints
POLYGON_NEWS_URL = "https://api.polygon.io/v2/reference/news"
ALPHA_VANTAGE_NEWS_URL = "https://www.alphavantage.co/query"
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
    ticker: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_significant(self) -> bool:
        """Check if sentiment is significant (not neutral with high confidence)."""
        return (
            self.sentiment != SentimentType.NEUTRAL and
            self.confidence >= 0.6
        )

    def to_dict(self) -> Dict[str, Any]:
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
    tickers: List[str]
    sentiment: Optional[SentimentScore] = None

    def to_dict(self) -> Dict[str, Any]:
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
    subreddit: Optional[str] = None
    sentiment: Optional[SentimentScore] = None

    @property
    def engagement_score(self) -> float:
        """Calculate engagement score."""
        return (self.upvotes * 1.0 + self.comments * 2.0) / 100

    def to_dict(self) -> Dict[str, Any]:
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
    source_scores: Dict[str, float]
    source_counts: Dict[str, int]
    bullish_count: int
    bearish_count: int
    neutral_count: int
    trend: str  # improving, stable, deteriorating
    news_items: List[NewsItem] = field(default_factory=list)
    social_posts: List[SocialPost] = field(default_factory=list)

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

    def to_dict(self) -> Dict[str, Any]:
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
    def analyze(self, text: str) -> Tuple[float, float]:
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

    def analyze(self, text: str) -> Tuple[float, float]:
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

    def analyze(self, text: str) -> Tuple[float, float]:
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

    def analyze(self, text: str) -> Tuple[float, float]:
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
        self.models: List[Tuple[BaseSentimentModel, float]] = []

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

    def analyze(self, text: str) -> Tuple[float, float]:
        """Analyze using weighted ensemble."""
        weighted_score = 0.0
        weighted_confidence = 0.0

        for model, weight in self.models:
            score, confidence = model.analyze(text)
            weighted_score += score * weight
            weighted_confidence += confidence * weight

        return weighted_score, weighted_confidence


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
        >>> analyzer = SentimentAnalyzer(polygon_api_key="your_key")
        >>> sentiment = analyzer.get_composite_sentiment("SPY")
        >>> print(f"Overall: {sentiment.overall_sentiment.value}")
        >>> print(f"Score: {sentiment.overall_score:.2f}")
        >>> print(f"Confidence: {sentiment.confidence:.2%}")
    """

    def __init__(
        self,
        polygon_api_key: Optional[str] = None,
        alpha_vantage_key: Optional[str] = None,
        reddit_credentials: Optional[Dict[str, str]] = None,
        model_type: SentimentModel = SentimentModel.ENSEMBLE,
        use_finbert: bool = True
    ):
        """
        Initialize Sentiment Analyzer.

        Args:
            polygon_api_key: Polygon.io API key for news
            alpha_vantage_key: Alpha Vantage API key for news
            reddit_credentials: Reddit API credentials
            model_type: Sentiment model to use
            use_finbert: Use FinBERT in ensemble (requires transformers)
        """
        self.polygon_api_key = polygon_api_key
        self.alpha_vantage_key = alpha_vantage_key
        self.reddit_credentials = reddit_credentials

        # Initialize sentiment model
        self.model_type = model_type
        self._init_sentiment_model(model_type, use_finbert)

        # Caches
        self._news_cache: Dict[str, Tuple[List[NewsItem], datetime]] = {}
        self._social_cache: Dict[str, Tuple[List[SocialPost], datetime]] = {}
        self._sentiment_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

        # Callbacks
        self._sentiment_callbacks: List[Callable[[SentimentScore], None]] = []

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
    ) -> List[NewsItem]:
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

        # Fetch news from available sources
        news_items = []

        if self.polygon_api_key:
            news_items.extend(self._fetch_polygon_news(ticker, limit))

        if self.alpha_vantage_key and len(news_items) < limit:
            news_items.extend(self._fetch_alpha_vantage_news(ticker, limit - len(news_items)))

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

    def _fetch_polygon_news(self, ticker: str, limit: int) -> List[NewsItem]:
        """Fetch news from Polygon.io."""
        try:
            params = {
                "ticker": ticker,
                "limit": limit,
                "apiKey": self.polygon_api_key
            }

            response = requests.get(POLYGON_NEWS_URL, params=params, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Polygon news fetch failed: {response.status_code}")
                return []

            data = response.json()
            results = data.get("results", [])

            news_items = []
            for item in results:
                try:
                    published = datetime.fromisoformat(
                        item.get("published_utc", "").replace("Z", "+00:00")
                    )
                except:
                    published = datetime.now()

                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    url=item.get("article_url", ""),
                    source=item.get("publisher", {}).get("name", "Unknown"),
                    published=published,
                    tickers=item.get("tickers", [])
                ))

            return news_items

        except Exception as e:
            logger.error(f"Polygon news fetch error: {e}")
            return []

    def _fetch_alpha_vantage_news(self, ticker: str, limit: int) -> List[NewsItem]:
        """Fetch news from Alpha Vantage."""
        try:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "limit": limit,
                "apikey": self.alpha_vantage_key
            }

            response = requests.get(ALPHA_VANTAGE_NEWS_URL, params=params, timeout=30)

            if response.status_code != 200:
                return []

            data = response.json()
            feed = data.get("feed", [])

            news_items = []
            for item in feed:
                try:
                    published = datetime.strptime(
                        item.get("time_published", "")[:15],
                        "%Y%m%dT%H%M%S"
                    )
                except:
                    published = datetime.now()

                news_items.append(NewsItem(
                    title=item.get("title", ""),
                    description=item.get("summary", ""),
                    url=item.get("url", ""),
                    source=item.get("source", "Unknown"),
                    published=published,
                    tickers=[t.get("ticker", "") for t in item.get("ticker_sentiment", [])]
                ))

            return news_items

        except Exception as e:
            logger.error(f"Alpha Vantage news fetch error: {e}")
            return []

    # ==========================================================================
    # SOCIAL MEDIA ANALYSIS
    # ==========================================================================

    def monitor_social_media(
        self,
        tickers: List[str],
        subreddits: Optional[List[str]] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> Dict[str, List[SocialPost]]:
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

        results: Dict[str, List[SocialPost]] = {}

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
        subreddits: List[str],
        limit: int
    ) -> List[SocialPost]:
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
        subreddits: List[str],
        limit: int
    ) -> List[SocialPost]:
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
                    except:
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
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Reddit fetch error for r/{subreddit}: {e}")

        return posts

    def _fetch_reddit_api(
        self,
        ticker: str,
        subreddits: List[str],
        limit: int
    ) -> List[SocialPost]:
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
        ticker: Optional[str] = None
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
        all_sentiments: List[SentimentScore] = []
        news_items: List[NewsItem] = []
        social_posts: List[SocialPost] = []

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
        source_scores: Dict[str, float] = {}
        source_counts: Dict[str, int] = defaultdict(int)

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
        filing_types: Optional[List[str]] = None
    ) -> List[SentimentScore]:
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

    def get_sentiment_summary(self, ticker: str) -> Dict[str, Any]:
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
def create_sentiment_analyzer_from_env() -> SentimentAnalyzer:
    """Create SentimentAnalyzer from environment variables."""
    polygon_key = os.getenv("POLYGON_API_KEY")
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")

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
        polygon_api_key=polygon_key,
        alpha_vantage_key=alpha_vantage_key,
        reddit_credentials=reddit_creds,
        model_type=model_map.get(model_type, SentimentModel.ENSEMBLE),
        use_finbert=os.getenv("USE_FINBERT", "true").lower() == "true"
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    print("Sentiment Analyzer Test")
    print("=" * 60)

    # Test available models
    print("\n=== Available Models ===")
    print(f"Transformers (FinBERT): {HAS_TRANSFORMERS}")
    print(f"VADER: {HAS_VADER}")
    print(f"TextBlob: {HAS_TEXTBLOB}")

    # Initialize analyzer
    polygon_key = os.getenv("POLYGON_API_KEY")

    try:
        analyzer = SentimentAnalyzer(
            polygon_api_key=polygon_key,
            model_type=SentimentModel.ENSEMBLE,
            use_finbert=False  # Skip FinBERT for faster testing
        )

        # Test individual analysis
        print("\n=== Text Analysis ===")
        test_texts = [
            "SPY is showing strong bullish momentum, expecting new all-time highs!",
            "Market crash incoming, sell everything before it's too late.",
            "The market opened flat today with mixed signals.",
            "BREAKING: Fed announces surprise rate cut, stocks surge!",
        ]

        for text in test_texts:
            sentiment = analyzer._analyze_text(text, SourceType.NEWS, "SPY")
            print(f"\nText: {text[:50]}...")
            print(f"  Score: {sentiment.score:.3f}")
            print(f"  Sentiment: {sentiment.sentiment.value}")
            print(f"  Confidence: {sentiment.confidence:.2%}")

        # Test news analysis (if API key available)
        if polygon_key:
            print("\n=== News Analysis ===")
            news = analyzer.analyze_news("SPY", limit=5)
            for item in news[:3]:
                print(f"\n{item.title}")
                if item.sentiment:
                    print(f"  Sentiment: {item.sentiment.sentiment.value}")
                    print(f"  Score: {item.sentiment.score:.3f}")

        # Test composite sentiment
        print("\n=== Composite Sentiment ===")
        composite = analyzer.get_composite_sentiment("SPY")
        print(f"Overall: {composite.overall_sentiment.value}")
        print(f"Score: {composite.overall_score:.3f}")
        print(f"Confidence: {composite.confidence:.2%}")
        print(f"Trend: {composite.trend}")
        print(f"Bullish/Bearish: {composite.bullish_count}/{composite.bearish_count}")
        print(f"Actionable: {composite.is_actionable}")

    except ImportError as e:
        print(f"\nNote: Some features unavailable: {e}")
        print("Install required libraries: pip install textblob vaderSentiment transformers torch")
