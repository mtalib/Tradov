#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC09_NewsManager.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

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
from datetime import datetime, timedelta, timezone
import threading
import time
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import numpy as np
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import feedparser

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType, EventBus

NEWS_SOURCES = {
    'bloomberg': 'https://www.bloomberg.com/feeds/news',
    'reuters': 'https://www.reuters.com/feeds/news',
    'cnbc': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
    'marketwatch': 'https://feeds.marketwatch.com/marketwatch/topstories/',
    'wsj': 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
    'fed': 'https://www.federalreserve.gov/feeds/press_all.xml'
}

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
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_bus = EventBus()

        # News storage
        self.news_items: dict[str, NewsItem] = {}
        self.news_sentiments: dict[str, NewsSentiment] = {}
        self.news_impacts: dict[str, NewsImpact] = {}
        self.news_history: deque = deque(maxlen=1000)

        # Analysis tools
        self.vader_analyzer = SentimentIntensityAnalyzer()
        self.processed_urls: set[str] = set()

        # Current state
        self.current_analysis: NewsAnalysis | None = None
        self.sentiment_history: deque = deque(maxlen=100)

        # Statistics
        self.stats = {
            'items_processed': 0,
            'sources_active': 0,
            'errors': 0,
            'last_update': datetime.now(timezone.utc)
        }

        # Control flags
        self.is_running = False
        self.fetch_thread: threading.Thread | None = None
        self.analysis_thread: threading.Thread | None = None
        self.lock = threading.Lock()

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
            self.fetch_thread.join(timeout=5)
        if self.analysis_thread:
            self.analysis_thread.join(timeout=5)
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
            items = list(self.news_items.values())

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
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
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

    # ==========================================================================
    # FETCHING METHODS
    # ==========================================================================
    def _fetch_loop(self) -> None:
        """Main fetch loop for news sources."""
        while self.is_running:
            try:
                # Fetch from each source
                for source_name, source_url in NEWS_SOURCES.items():
                    try:
                        self._fetch_from_source(source_name, source_url)
                        self.stats['sources_active'] += 1
                    except Exception as e:
                        self.logger.error("Error fetching from %s: %s", source_name, e)

                time.sleep(NEWS_FETCH_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Fetch loop error: %s", e)
                self.stats['errors'] += 1
                time.sleep(NEWS_FETCH_INTERVAL)  # thread-safe: time.sleep() intentional

    def _fetch_from_source(self, source_name: str, source_url: str) -> None:
        """Fetch news from a specific source."""
        try:
            # Parse RSS feed
            feed = feedparser.parse(source_url)

            for entry in feed.entries[:20]:  # Limit to recent items
                # Check if already processed
                if entry.link in self.processed_urls:
                    continue

                # Create news item
                news_item = self._create_news_item(source_name, entry)
                if news_item:
                    with self.lock:
                        self.news_items[news_item.id] = news_item
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
            if published:
                timestamp = datetime.fromtimestamp(time.mktime(published))
            else:
                timestamp = datetime.now(timezone.utc)

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

                    # Publish event
                    event = Event(
                        type=EventType.NEWS_ANALYSIS,
                        data={
                            'analysis': analysis,
                            'timestamp': datetime.now(timezone.utc)
                        }
                    )
                    self.event_bus.publish(event)

                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Analysis loop error: %s", e)
                time.sleep(ANALYSIS_INTERVAL)  # thread-safe: time.sleep() intentional

    def _analyze_sentiment(self, news_item: NewsItem) -> NewsSentiment | None:
        """Analyze sentiment of news item."""
        try:
            text = f"{news_item.title} {news_item.summary}"

            # TextBlob analysis
            blob = TextBlob(text)
            textblob_polarity = blob.sentiment.polarity
            textblob_subjectivity = blob.sentiment.subjectivity

            # VADER analysis
            vader_scores = self.vader_analyzer.polarity_scores(text)

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
                timestamp=datetime.now(timezone.utc),
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
                timestamp=datetime.now(timezone.utc),
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

        return affected if affected else ['SPY']

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
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
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
                    timestamp=datetime.now(timezone.utc),
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

            # Publish breaking news event
            event = Event(
                type=EventType.BREAKING_NEWS,
                data={
                    'news_item': news_item,
                    'timestamp': datetime.now(timezone.utc)
                }
            )
            self.event_bus.publish(event)

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
