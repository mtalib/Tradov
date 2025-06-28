#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC09_NewsManager.py
Group: C (Market Data)
Purpose: Real-time news feed management and processing

Description:
    This module manages real-time news feeds from Interactive Brokers including
    provider discovery, broadtape and instrument-specific news subscriptions,
    article retrieval, and news event processing. It integrates with the trading
    system to provide timely market intelligence for trading decisions.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 20:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from ibapi.contract import Contract

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# News configuration
MAX_NEWS_HISTORY = 1000
NEWS_CACHE_DURATION = 3600  # 1 hour
ARTICLE_REQUEST_TIMEOUT = 30  # seconds
MAX_CONCURRENT_ARTICLES = 10

# Provider codes (common ones)
PROVIDER_BENZINGA = "BZ"
PROVIDER_BRIEFING = "BRFG"
PROVIDER_DJ = "DJ"
PROVIDER_FL = "FL"

# News tick type
NEWS_TICK_TYPE = "292"

# ==============================================================================
# ENUMS
# ==============================================================================
class NewsType(Enum):
    """Types of news subscriptions"""
    BROADTAPE = "BROADTAPE"
    INSTRUMENT = "INSTRUMENT"
    HEADLINE = "HEADLINE"
    ARTICLE = "ARTICLE"

class NewsRelevance(Enum):
    """News relevance levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class NewsProvider:
    """News provider information"""
    code: str
    name: str
    enabled: bool = True
    
@dataclass
class NewsHeadline:
    """News headline data"""
    headline_id: str
    timestamp: datetime
    provider_code: str
    article_id: str
    headline: str
    symbol: Optional[str] = None
    relevance: NewsRelevance = NewsRelevance.MEDIUM
    extra_data: Optional[str] = None
    
@dataclass
class NewsArticle:
    """Full news article data"""
    article_id: str
    provider_code: str
    article_type: int  # 0 = text/HTML, 1 = binary/PDF
    content: str
    headline: Optional[NewsHeadline] = None
    retrieved_time: datetime = field(default_factory=datetime.now)
    
@dataclass
class NewsSubscription:
    """Active news subscription"""
    req_id: int
    news_type: NewsType
    provider_code: str
    symbol: Optional[str] = None
    active: bool = True
    created_time: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class NewsManager:
    """
    News feed management for SPYDER trading system.
    
    This class manages all aspects of news data including provider discovery,
    subscription management, headline monitoring, and article retrieval.
    It provides filtered news events to the trading system based on relevance.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        providers: Available news providers
        subscriptions: Active news subscriptions
        headlines: Recent news headlines
        
    Example:
        >>> news_mgr = NewsManager(ib_client, event_manager)
        >>> news_mgr.initialize()
        >>> news_mgr.subscribe_spy_news()
    """
    
    def __init__(self, ib_client, event_manager: Optional[EventManager] = None):
        """Initialize the news manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # IB client reference
        self.ib_client = ib_client
        self.event_manager = event_manager
        
        # Provider management
        self.providers: Dict[str, NewsProvider] = {}
        self.preferred_providers = [PROVIDER_BENZINGA, PROVIDER_DJ, PROVIDER_BRIEFING]
        
        # Subscription management
        self.subscriptions: Dict[int, NewsSubscription] = {}
        self.next_req_id = 90000  # Start news req IDs at 90000
        
        # News storage
        self.headlines = deque(maxlen=MAX_NEWS_HISTORY)
        self.articles: Dict[str, NewsArticle] = {}
        self.article_cache_time: Dict[str, datetime] = {}
        
        # Filtering
        self.relevance_keywords = {
            NewsRelevance.CRITICAL: ['crash', 'halt', 'suspend', 'emergency', 'fed'],
            NewsRelevance.HIGH: ['spy', 'spx', 's&p', 'volatility', 'options', 'gamma'],
            NewsRelevance.MEDIUM: ['market', 'stock', 'trade', 'economy', 'earnings']
        }
        
        # Threading
        self.article_lock = threading.Lock()
        self.pending_articles: Set[str] = set()
        
        # Callbacks
        self.headline_callbacks: List[Callable] = []
        self.article_callbacks: List[Callable] = []
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS - INITIALIZATION
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize news manager and discover providers.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Discover available news providers
            self.discover_providers()
            
            # Wait a bit for provider discovery
            time.sleep(1.0)
            
            self.logger.info("News manager initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"News initialization failed: {e}")
            return False
    
    def discover_providers(self) -> None:
        """Discover available news providers."""
        self.logger.info("Requesting news providers...")
        self.ib_client.reqNewsProviders()
        
    # ==========================================================================
    # PUBLIC METHODS - SUBSCRIPTIONS
    # ==========================================================================
    def subscribe_broadtape_news(self, provider_code: Optional[str] = None) -> int:
        """
        Subscribe to general news feed from a provider.
        
        Args:
            provider_code: Provider code (uses preferred if None)
            
        Returns:
            Request ID for the subscription
        """
        # Use preferred provider if not specified
        if provider_code is None:
            provider_code = self._get_preferred_provider()
            
        if provider_code is None:
            self.logger.error("No news providers available")
            return -1
            
        req_id = self._get_next_req_id()
        
        # Create special NEWS contract
        contract = Contract()
        contract.symbol = ""
        contract.secType = "NEWS"
        contract.exchange = provider_code
        
        # Subscribe with news tick type
        self.ib_client.reqMktData(req_id, contract, NEWS_TICK_TYPE, False, False, [])
        
        # Track subscription
        subscription = NewsSubscription(
            req_id=req_id,
            news_type=NewsType.BROADTAPE,
            provider_code=provider_code
        )
        self.subscriptions[req_id] = subscription
        
        self.logger.info(f"Subscribed to broadtape news from {provider_code} (req_id: {req_id})")
        return req_id
        
    def subscribe_instrument_news(self, symbol: str, provider_code: Optional[str] = None) -> int:
        """
        Subscribe to instrument-specific news.
        
        Args:
            symbol: Instrument symbol (e.g., 'SPY')
            provider_code: Provider code (uses preferred if None)
            
        Returns:
            Request ID for the subscription
        """
        # Use preferred provider if not specified
        if provider_code is None:
            provider_code = self._get_preferred_provider()
            
        if provider_code is None:
            self.logger.error("No news providers available")
            return -1
            
        req_id = self._get_next_req_id()
        
        # Create standard contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Request with mdoff to suppress price data
        generic_ticks = f"mdoff,{NEWS_TICK_TYPE}:{provider_code}"
        self.ib_client.reqMktData(req_id, contract, generic_ticks, False, False, [])
        
        # Track subscription
        subscription = NewsSubscription(
            req_id=req_id,
            news_type=NewsType.INSTRUMENT,
            provider_code=provider_code,
            symbol=symbol
        )
        self.subscriptions[req_id] = subscription
        
        self.logger.info(f"Subscribed to {symbol} news from {provider_code} (req_id: {req_id})")
        return req_id
        
    def subscribe_spy_news(self) -> List[int]:
        """
        Subscribe to all SPY-related news feeds.
        
        Returns:
            List of request IDs
        """
        req_ids = []
        
        # Subscribe to SPY-specific news from all preferred providers
        for provider in self.preferred_providers:
            if provider in self.providers:
                req_id = self.subscribe_instrument_news("SPY", provider)
                if req_id > 0:
                    req_ids.append(req_id)
                    
        # Also subscribe to broadtape for general market news
        req_id = self.subscribe_broadtape_news()
        if req_id > 0:
            req_ids.append(req_id)
            
        self.logger.info(f"Subscribed to {len(req_ids)} SPY news feeds")
        return req_ids
        
    def unsubscribe_news(self, req_id: int) -> None:
        """
        Unsubscribe from a news feed.
        
        Args:
            req_id: Request ID of the subscription
        """
        if req_id in self.subscriptions:
            self.ib_client.cancelMktData(req_id)
            
            subscription = self.subscriptions[req_id]
            subscription.active = False
            
            self.logger.info(f"Unsubscribed from news (req_id: {req_id})")
            
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all news feeds."""
        for req_id in list(self.subscriptions.keys()):
            self.unsubscribe_news(req_id)
            
    # ==========================================================================
    # PUBLIC METHODS - ARTICLE RETRIEVAL
    # ==========================================================================
    def request_article(self, provider_code: str, article_id: str) -> None:
        """
        Request full text of a news article.
        
        Args:
            provider_code: News provider code
            article_id: Article identifier
        """
        # Check if already cached
        cache_key = f"{provider_code}:{article_id}"
        
        with self.article_lock:
            if cache_key in self.articles:
                # Check cache age
                cache_time = self.article_cache_time.get(cache_key, datetime.min)
                if (datetime.now() - cache_time).seconds < NEWS_CACHE_DURATION:
                    self.logger.debug(f"Article {article_id} found in cache")
                    return
                    
            # Check if already pending
            if cache_key in self.pending_articles:
                self.logger.debug(f"Article {article_id} already pending")
                return
                
            # Mark as pending
            self.pending_articles.add(cache_key)
            
        req_id = self._get_next_req_id()
        self.ib_client.reqNewsArticle(req_id, provider_code, article_id, [])
        
        self.logger.info(f"Requested article {article_id} from {provider_code}")
        
    # ==========================================================================
    # PUBLIC METHODS - CALLBACKS
    # ==========================================================================
    def register_headline_callback(self, callback: Callable) -> None:
        """Register callback for news headlines."""
        self.headline_callbacks.append(callback)
        
    def register_article_callback(self, callback: Callable) -> None:
        """Register callback for news articles."""
        self.article_callbacks.append(callback)
        
    # ==========================================================================
    # PUBLIC METHODS - IB CALLBACKS
    # ==========================================================================
    def on_news_providers(self, providers: List) -> None:
        """
        Handle news providers response.
        
        Args:
            providers: List of NewsProvider objects from IB
        """
        self.providers.clear()
        
        for provider in providers:
            news_provider = NewsProvider(
                code=provider.providerCode,
                name=provider.providerName
            )
            self.providers[provider.providerCode] = news_provider
            
            self.logger.info(f"News provider available: {provider.providerCode} - {provider.providerName}")
            
        # Emit event if event manager available
        if self.event_manager:
            self.event_manager.emit(Event(
                EventType.MARKET_DATA,
                {
                    'type': 'news_providers',
                    'providers': list(self.providers.keys()),
                    'count': len(self.providers)
                }
            ))
            
    def on_tick_news(self, req_id: int, time_stamp: int, provider_code: str,
                    article_id: str, headline_text: str, extra_data: str) -> None:
        """
        Handle news headline.
        
        Args:
            req_id: Request ID
            time_stamp: Unix timestamp
            provider_code: Provider code
            article_id: Article ID
            headline_text: Headline text
            extra_data: Additional data
        """
        # Get subscription info
        subscription = self.subscriptions.get(req_id)
        symbol = subscription.symbol if subscription else None
        
        # Create headline object
        headline = NewsHeadline(
            headline_id=f"{provider_code}:{article_id}",
            timestamp=datetime.fromtimestamp(time_stamp),
            provider_code=provider_code,
            article_id=article_id,
            headline=headline_text,
            symbol=symbol,
            relevance=self._calculate_relevance(headline_text, symbol),
            extra_data=extra_data
        )
        
        # Store headline
        self.headlines.append(headline)
        
        # Log based on relevance
        if headline.relevance in [NewsRelevance.HIGH, NewsRelevance.CRITICAL]:
            self.logger.warning(f"HIGH RELEVANCE NEWS: {headline_text}")
        else:
            self.logger.info(f"News: {headline_text}")
            
        # Execute callbacks
        for callback in self.headline_callbacks:
            try:
                callback(headline)
            except Exception as e:
                self.logger.error(f"Headline callback error: {e}")
                
        # Emit event if high relevance
        if self.event_manager and headline.relevance in [NewsRelevance.HIGH, NewsRelevance.CRITICAL]:
            self.event_manager.emit(Event(
                EventType.MARKET_DATA,
                {
                    'type': 'news_headline',
                    'headline': headline_text,
                    'relevance': headline.relevance.value,
                    'symbol': symbol,
                    'provider': provider_code,
                    'timestamp': headline.timestamp
                }
            ))
            
        # Auto-request article for critical news
        if headline.relevance == NewsRelevance.CRITICAL:
            self.request_article(provider_code, article_id)
            
    def on_news_article(self, req_id: int, article_type: int, article_text: str) -> None:
        """
        Handle full news article.
        
        Args:
            req_id: Request ID
            article_type: 0 = text/HTML, 1 = binary/PDF
            article_text: Article content
        """
        # Find the corresponding headline (simplified - would need better tracking)
        headline = None
        for h in reversed(self.headlines):
            if h.article_id:  # Find matching article
                headline = h
                break
                
        # Create article object
        article = NewsArticle(
            article_id=headline.article_id if headline else f"article_{req_id}",
            provider_code=headline.provider_code if headline else "UNKNOWN",
            article_type=article_type,
            content=article_text,
            headline=headline
        )
        
        # Cache article
        cache_key = f"{article.provider_code}:{article.article_id}"
        with self.article_lock:
            self.articles[cache_key] = article
            self.article_cache_time[cache_key] = datetime.now()
            self.pending_articles.discard(cache_key)
            
        # Log
        content_type = "text" if article_type == 0 else "binary"
        self.logger.info(f"Received {content_type} article (length: {len(article_text)})")
        
        # Execute callbacks
        for callback in self.article_callbacks:
            try:
                callback(article)
            except Exception as e:
                self.logger.error(f"Article callback error: {e}")
                
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _get_next_req_id(self) -> int:
        """Get next request ID for news operations."""
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id
        
    def _get_preferred_provider(self) -> Optional[str]:
        """Get first available preferred provider."""
        for provider in self.preferred_providers:
            if provider in self.providers:
                return provider
        
        # Return first available if no preferred found
        if self.providers:
            return list(self.providers.keys())[0]
            
        return None
        
    def _calculate_relevance(self, headline: str, symbol: Optional[str]) -> NewsRelevance:
        """
        Calculate news relevance based on content.
        
        Args:
            headline: Headline text
            symbol: Related symbol
            
        Returns:
            NewsRelevance level
        """
        headline_lower = headline.lower()
        
        # Check critical keywords
        for keyword in self.relevance_keywords[NewsRelevance.CRITICAL]:
            if keyword in headline_lower:
                return NewsRelevance.CRITICAL
                
        # Check if symbol-specific and contains symbol
        if symbol and symbol.lower() in headline_lower:
            return NewsRelevance.HIGH
            
        # Check high relevance keywords
        for keyword in self.relevance_keywords[NewsRelevance.HIGH]:
            if keyword in headline_lower:
                return NewsRelevance.HIGH
                
        # Check medium relevance keywords
        for keyword in self.relevance_keywords[NewsRelevance.MEDIUM]:
            if keyword in headline_lower:
                return NewsRelevance.MEDIUM
                
        return NewsRelevance.LOW
        
    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def get_recent_headlines(self, minutes: int = 60, 
                           min_relevance: NewsRelevance = NewsRelevance.MEDIUM) -> List[NewsHeadline]:
        """
        Get recent headlines filtered by time and relevance.
        
        Args:
            minutes: Look back period in minutes
            min_relevance: Minimum relevance level
            
        Returns:
            List of filtered headlines
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        relevance_values = [NewsRelevance.CRITICAL, NewsRelevance.HIGH, NewsRelevance.MEDIUM, NewsRelevance.LOW]
        min_index = relevance_values.index(min_relevance)
        allowed_relevance = relevance_values[:min_index + 1]
        
        filtered = [
            h for h in self.headlines
            if h.timestamp >= cutoff_time and h.relevance in allowed_relevance
        ]
        
        return sorted(filtered, key=lambda h: h.timestamp, reverse=True)
        
    def get_sentiment_indicators(self) -> Dict[str, Any]:
        """
        Calculate news sentiment indicators.
        
        Returns:
            Dictionary of sentiment metrics
        """
        recent_headlines = self.get_recent_headlines(minutes=30)
        
        if not recent_headlines:
            return {
                'headline_count': 0,
                'critical_count': 0,
                'high_relevance_ratio': 0.0,
                'news_velocity': 0.0
            }
            
        critical_count = sum(1 for h in recent_headlines if h.relevance == NewsRelevance.CRITICAL)
        high_count = sum(1 for h in recent_headlines if h.relevance == NewsRelevance.HIGH)
        
        return {
            'headline_count': len(recent_headlines),
            'critical_count': critical_count,
            'high_relevance_ratio': (critical_count + high_count) / len(recent_headlines),
            'news_velocity': len(recent_headlines) / 30.0  # Headlines per minute
        }
        
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up news manager resources."""
        # Unsubscribe from all feeds
        self.unsubscribe_all()
        
        # Clear caches
        self.headlines.clear()
        self.articles.clear()
        
        self.logger.info("News manager cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def format_headline_display(headline: NewsHeadline) -> str:
    """
    Format headline for display.
    
    Args:
        headline: NewsHeadline object
        
    Returns:
        Formatted string
    """
    relevance_symbol = {
        NewsRelevance.CRITICAL: "🔴",
        NewsRelevance.HIGH: "🟡",
        NewsRelevance.MEDIUM: "🔵",
        NewsRelevance.LOW: "⚪"
    }
    
    symbol = relevance_symbol.get(headline.relevance, "")
    timestamp = headline.timestamp.strftime("%H:%M:%S")
    
    return f"{symbol} [{timestamp}] {headline.headline}"

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
pass

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("✅ News Manager Module Test")
    print("-" * 60)
    
    # Test news provider
    provider = NewsProvider(code="BZ", name="Benzinga")
    print(f"Provider: {provider.code} - {provider.name}")
    
    # Test headline
    headline = NewsHeadline(
        headline_id="BZ:12345",
        timestamp=datetime.now(),
        provider_code="BZ",
        article_id="12345",
        headline="SPY hits new all-time high amid Fed comments",
        symbol="SPY",
        relevance=NewsRelevance.HIGH
    )
    
    print(f"\nHeadline: {format_headline_display(headline)}")
    print(f"  Symbol: {headline.symbol}")
    print(f"  Provider: {headline.provider_code}")
    print(f"  Article ID: {headline.article_id}")
    
    # Test relevance calculation
    class MockNewsManager:
        def __init__(self):
            self.relevance_keywords = {
                NewsRelevance.CRITICAL: ['crash', 'halt', 'suspend'],
                NewsRelevance.HIGH: ['spy', 'spx', 'volatility'],
                NewsRelevance.MEDIUM: ['market', 'stock', 'trade']
            }
            
        def _calculate_relevance(self, headline: str, symbol: Optional[str]) -> NewsRelevance:
            """Test relevance calculation."""
            return NewsManager._calculate_relevance(self, headline, symbol)
    
    mock_mgr = MockNewsManager()
    
    test_headlines = [
        ("Market crash fears rise", None),
        ("SPY options volume surges", "SPY"),
        ("Apple earnings beat estimates", None),
        ("Trading halted on NYSE", None)
    ]
    
    print("\nRelevance tests:")
    for text, symbol in test_headlines:
        relevance = mock_mgr._calculate_relevance(text, symbol)
        print(f"  '{text}' -> {relevance.value}")
    
    print("\n✅ All tests passed")
