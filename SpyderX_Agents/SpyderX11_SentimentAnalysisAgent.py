#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX11_SentimentAnalysisAgent.py
Purpose: AI-Enhanced Market Sentiment Analysis
Group: X (AI Agents)

Description:
    Analyzes market sentiment from multiple sources including news, social media,
    and market indicators to provide actionable insights for options trading.
    This agent helps predict market movements and volatility changes based on
    sentiment shifts.

    Key Features:
    - News sentiment analysis (financial news sources)
    - Social media monitoring (Reddit, Twitter/X)
    - Market sentiment indicators (Put/Call ratio, VIX, breadth)
    - Event impact prediction
    - Sentiment-based trade signals

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - requests (for API calls)
    - beautifulsoup4 (for web scraping)
    - textblob (for basic sentiment)
    - vaderSentiment (for social media sentiment)
    - pandas, numpy
    - asyncio, aiohttp
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import re
import hashlib
from urllib.parse import urlparse
import aiohttp
from textblob import TextBlob
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Import Spyder core components
from SpyderU01_DataStructures import MarketData, Event
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Sentiment Types
class SentimentSource(Enum):
    """Sources of sentiment data"""
    NEWS = "news"
    REDDIT = "reddit"
    TWITTER = "twitter"
    STOCKTWITS = "stocktwits"
    MARKET_INDICATORS = "market_indicators"
    ANALYST_RATINGS = "analyst_ratings"
    ECONOMIC_DATA = "economic_data"

class SentimentType(Enum):
    """Types of sentiment analysis"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"

class EventImpact(Enum):
    """Expected impact of events"""
    HIGH_POSITIVE = "high_positive"
    MODERATE_POSITIVE = "moderate_positive"
    LOW_POSITIVE = "low_positive"
    NEUTRAL = "neutral"
    LOW_NEGATIVE = "low_negative"
    MODERATE_NEGATIVE = "moderate_negative"
    HIGH_NEGATIVE = "high_negative"

@dataclass
class SentimentScore:
    """Sentiment score from a source"""
    source: SentimentSource
    timestamp: datetime
    score: float  # -1 to 1 (bearish to bullish)
    confidence: float  # 0 to 1
    volume: int  # Number of mentions/articles
    keywords: List[str] = field(default_factory=list)
    raw_text: Optional[str] = None

@dataclass
class MarketSentiment:
    """Aggregated market sentiment"""
    timestamp: datetime
    overall_score: float  # -1 to 1
    sentiment_type: SentimentType
    confidence: float
    source_scores: Dict[SentimentSource, float]
    trending_topics: List[str]
    event_risks: List[Dict[str, Any]]
    trade_signal: Optional[str] = None

@dataclass
class EventAlert:
    """Alert for significant events"""
    event_type: str
    headline: str
    impact: EventImpact
    expected_move: float  # Expected % move in SPY
    volatility_impact: float  # Expected IV change
    confidence: float
    source: str
    timestamp: datetime

@dataclass
class SentimentTrend:
    """Sentiment trend analysis"""
    period: str  # "1H", "4H", "1D", "1W"
    direction: str  # "improving", "deteriorating", "stable"
    rate_of_change: float
    momentum: float
    reversal_probability: float

class SentimentAnalysisAgent(SpyderBaseAgent):
    """
    AI-Enhanced Sentiment Analysis Agent
    
    Monitors and analyzes market sentiment from multiple sources
    to provide trading signals and risk alerts.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Sentiment Analysis Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('sentiment_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.update_frequency = config.get('sentiment_update_minutes', 5)
        self.lookback_hours = config.get('sentiment_lookback_hours', 24)
        
        # API configurations (would be in config file)
        self.news_api_key = config.get('news_api_key', '')
        self.reddit_client_id = config.get('reddit_client_id', '')
        self.twitter_bearer_token = config.get('twitter_bearer_token', '')
        
        # Sentiment analyzers
        self.vader = SentimentIntensityAnalyzer()
        
        # Data storage
        self.sentiment_scores: Dict[SentimentSource, deque] = {
            source: deque(maxlen=1000) for source in SentimentSource
        }
        self.market_sentiment_history: deque = deque(maxlen=1000)
        self.event_alerts: deque = deque(maxlen=100)
        self.trending_topics: Dict[str, int] = defaultdict(int)
        
        # Market indicators
        self.put_call_ratio: float = 1.0
        self.vix_level: float = 15.0
        self.market_breadth: float = 0.5
        self.fear_greed_index: float = 50.0
        
        # Keywords and patterns
        self.bullish_keywords = [
            'rally', 'surge', 'bullish', 'upgrade', 'beat', 'strong',
            'growth', 'record', 'breakthrough', 'positive', 'optimistic',
            'buy', 'upside', 'breakout', 'momentum', 'recovery'
        ]
        
        self.bearish_keywords = [
            'crash', 'plunge', 'bearish', 'downgrade', 'miss', 'weak',
            'recession', 'decline', 'selloff', 'negative', 'pessimistic',
            'sell', 'downside', 'breakdown', 'correction', 'risk'
        ]
        
        self.volatility_keywords = [
            'uncertainty', 'volatile', 'swing', 'turbulent', 'unstable',
            'fear', 'panic', 'spike', 'surge', 'jump', 'collapse'
        ]
        
        # Event patterns
        self.event_patterns = {
            'fed_meeting': r'federal reserve|fed meeting|fomc|interest rate',
            'earnings': r'earnings|eps|revenue|guidance|quarterly results',
            'economic_data': r'jobs report|unemployment|inflation|cpi|gdp|retail sales',
            'geopolitical': r'war|conflict|sanctions|trade war|tariff',
            'market_crash': r'crash|circuit breaker|limit down|black swan'
        }
        
        # Cache for API calls
        self.api_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.cache_duration = timedelta(minutes=5)
        
        self.logger.info("Sentiment Analysis Agent initialized")

    async def initialize(self, event_manager=None, market_data_provider=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.market_data_provider = market_data_provider
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_update)
            self.event_manager.subscribe(EventType.NEWS_UPDATE, self._handle_news_update)
        
        # Start background tasks
        asyncio.create_task(self._monitor_sentiment_loop())
        asyncio.create_task(self._analyze_trends_loop())
        asyncio.create_task(self._detect_events_loop())
        asyncio.create_task(self._update_market_indicators_loop())
        
        self.state = AgentState.RUNNING
        self.logger.info("Sentiment Analysis Agent initialized and running")

    async def get_market_sentiment(self) -> MarketSentiment:
        """
        Get current aggregated market sentiment
        
        Returns:
            Current market sentiment with all sources combined
        """
        try:
            # Collect sentiment from all sources
            source_sentiments = {}
            
            # News sentiment
            news_sentiment = await self._analyze_news_sentiment()
            source_sentiments[SentimentSource.NEWS] = news_sentiment
            
            # Social media sentiment
            reddit_sentiment = await self._analyze_reddit_sentiment()
            source_sentiments[SentimentSource.REDDIT] = reddit_sentiment
            
            # Market indicators sentiment
            market_sentiment = await self._analyze_market_indicators()
            source_sentiments[SentimentSource.MARKET_INDICATORS] = market_sentiment
            
            # Aggregate sentiments
            aggregated = await self._aggregate_sentiments(source_sentiments)
            
            # Detect event risks
            event_risks = await self._detect_event_risks()
            
            # Generate trade signal
            trade_signal = await self._generate_trade_signal(aggregated, event_risks)
            
            # Get trending topics
            trending = self._get_trending_topics()
            
            # Create market sentiment
            sentiment = MarketSentiment(
                timestamp=datetime.now(),
                overall_score=aggregated['score'],
                sentiment_type=aggregated['type'],
                confidence=aggregated['confidence'],
                source_scores={k: v.score for k, v in source_sentiments.items()},
                trending_topics=trending,
                event_risks=event_risks,
                trade_signal=trade_signal
            )
            
            # Store in history
            self.market_sentiment_history.append(sentiment)
            
            # Publish sentiment update
            if self.event_manager:
                await self.event_manager.publish(Event(
                    type=EventType.SENTIMENT_UPDATE,
                    data={'sentiment': sentiment}
                ))
            
            return sentiment
            
        except Exception as e:
            self.logger.error(f"Error getting market sentiment: {str(e)}")
            return self._get_default_sentiment()

    async def analyze_text_sentiment(self, text: str, source: str = 'general') -> Dict[str, Any]:
        """
        Analyze sentiment of specific text
        
        Args:
            text: Text to analyze
            source: Source context (news, social, etc.)
            
        Returns:
            Sentiment analysis results
        """
        try:
            # Basic sentiment with TextBlob
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
            
            # VADER sentiment (better for social media)
            vader_scores = self.vader.polarity_scores(text)
            
            # Keyword analysis
            bullish_count = sum(1 for word in self.bullish_keywords if word in text.lower())
            bearish_count = sum(1 for word in self.bearish_keywords if word in text.lower())
            volatility_count = sum(1 for word in self.volatility_keywords if word in text.lower())
            
            # AI-enhanced analysis
            ai_sentiment = await self._ai_analyze_sentiment(text, source)
            
            # Combine scores
            combined_score = (
                polarity * 0.3 +
                vader_scores['compound'] * 0.3 +
                (bullish_count - bearish_count) / max(bullish_count + bearish_count, 1) * 0.2 +
                ai_sentiment.get('score', 0) * 0.2
            )
            
            return {
                'score': np.clip(combined_score, -1, 1),
                'polarity': polarity,
                'subjectivity': subjectivity,
                'vader': vader_scores,
                'bullish_keywords': bullish_count,
                'bearish_keywords': bearish_count,
                'volatility_keywords': volatility_count,
                'ai_insights': ai_sentiment.get('insights', ''),
                'confidence': ai_sentiment.get('confidence', 0.5)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing text sentiment: {str(e)}")
            return {'score': 0, 'confidence': 0}

    async def detect_market_events(self) -> List[EventAlert]:
        """
        Detect significant market events from sentiment sources
        
        Returns:
            List of event alerts
        """
        try:
            events = []
            
            # Check each event pattern
            for event_type, pattern in self.event_patterns.items():
                matches = await self._search_event_pattern(pattern)
                
                for match in matches:
                    # Analyze event impact
                    impact = await self._analyze_event_impact(event_type, match)
                    
                    # Create event alert
                    alert = EventAlert(
                        event_type=event_type,
                        headline=match['headline'],
                        impact=impact['impact'],
                        expected_move=impact['expected_move'],
                        volatility_impact=impact['volatility_impact'],
                        confidence=impact['confidence'],
                        source=match['source'],
                        timestamp=datetime.now()
                    )
                    
                    events.append(alert)
                    
                    # Store alert
                    self.event_alerts.append(alert)
            
            # Sort by impact
            events.sort(key=lambda x: abs(x.expected_move), reverse=True)
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error detecting market events: {str(e)}")
            return []

    async def get_sentiment_trends(self) -> Dict[str, SentimentTrend]:
        """
        Get sentiment trends across different timeframes
        
        Returns:
            Dictionary of trends by timeframe
        """
        try:
            trends = {}
            
            # Define timeframes
            timeframes = {
                '1H': timedelta(hours=1),
                '4H': timedelta(hours=4),
                '1D': timedelta(days=1),
                '1W': timedelta(days=7)
            }
            
            for period, delta in timeframes.items():
                trend = await self._calculate_sentiment_trend(delta)
                trends[period] = SentimentTrend(
                    period=period,
                    direction=trend['direction'],
                    rate_of_change=trend['rate_of_change'],
                    momentum=trend['momentum'],
                    reversal_probability=trend['reversal_probability']
                )
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error getting sentiment trends: {str(e)}")
            return {}

    async def get_options_sentiment(self) -> Dict[str, Any]:
        """
        Get options-specific sentiment indicators
        
        Returns:
            Options sentiment metrics
        """
        try:
            # Put/Call ratio sentiment
            pc_sentiment = self._interpret_put_call_ratio(self.put_call_ratio)
            
            # VIX sentiment
            vix_sentiment = self._interpret_vix_level(self.vix_level)
            
            # Options flow sentiment
            flow_sentiment = await self._analyze_options_flow()
            
            # Term structure sentiment
            term_sentiment = await self._analyze_term_structure()
            
            return {
                'put_call_ratio': {
                    'value': self.put_call_ratio,
                    'sentiment': pc_sentiment,
                    'signal': self._get_pc_signal(self.put_call_ratio)
                },
                'vix': {
                    'level': self.vix_level,
                    'sentiment': vix_sentiment,
                    'regime': self._get_vix_regime(self.vix_level)
                },
                'options_flow': flow_sentiment,
                'term_structure': term_sentiment,
                'overall': self._combine_options_sentiment(
                    pc_sentiment, vix_sentiment, flow_sentiment
                )
            }
            
        except Exception as e:
            self.logger.error(f"Error getting options sentiment: {str(e)}")
            return {}

    async def _analyze_news_sentiment(self) -> SentimentScore:
        """Analyze sentiment from news sources"""
        try:
            # Check cache
            cache_key = 'news_sentiment'
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Fetch news articles (mock implementation)
            articles = await self._fetch_news_articles()
            
            # Analyze each article
            sentiments = []
            keywords = []
            
            for article in articles:
                sentiment = await self.analyze_text_sentiment(
                    article.get('title', '') + ' ' + article.get('description', ''),
                    source='news'
                )
                sentiments.append(sentiment['score'])
                
                # Extract keywords
                keywords.extend(self._extract_keywords(article.get('title', '')))
            
            # Calculate aggregate score
            if sentiments:
                avg_score = np.mean(sentiments)
                confidence = 1 - np.std(sentiments)  # Higher std = lower confidence
            else:
                avg_score = 0
                confidence = 0
            
            score = SentimentScore(
                source=SentimentSource.NEWS,
                timestamp=datetime.now(),
                score=avg_score,
                confidence=confidence,
                volume=len(articles),
                keywords=list(set(keywords))[:10]  # Top 10 unique keywords
            )
            
            # Cache result
            self._cache_data(cache_key, score)
            
            # Store score
            self.sentiment_scores[SentimentSource.NEWS].append(score)
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error analyzing news sentiment: {str(e)}")
            return SentimentScore(
                source=SentimentSource.NEWS,
                timestamp=datetime.now(),
                score=0,
                confidence=0,
                volume=0
            )

    async def _analyze_reddit_sentiment(self) -> SentimentScore:
        """Analyze sentiment from Reddit"""
        try:
            # Check cache
            cache_key = 'reddit_sentiment'
            cached = self._get_cached_data(cache_key)
            if cached:
                return cached
            
            # Fetch Reddit posts (mock implementation)
            posts = await self._fetch_reddit_posts()
            
            # Analyze each post
            sentiments = []
            keywords = []
            total_score_weight = 0
            
            for post in posts:
                # Weight by upvotes
                weight = np.log1p(post.get('score', 1))
                
                sentiment = await self.analyze_text_sentiment(
                    post.get('title', '') + ' ' + post.get('selftext', ''),
                    source='reddit'
                )
                
                sentiments.append(sentiment['score'] * weight)
                total_score_weight += weight
                
                # Extract keywords
                keywords.extend(self._extract_keywords(post.get('title', '')))
            
            # Calculate weighted average
            if total_score_weight > 0:
                avg_score = sum(sentiments) / total_score_weight
                confidence = min(0.8, total_score_weight / 100)  # Cap at 0.8
            else:
                avg_score = 0
                confidence = 0
            
            score = SentimentScore(
                source=SentimentSource.REDDIT,
                timestamp=datetime.now(),
                score=avg_score,
                confidence=confidence,
                volume=len(posts),
                keywords=list(set(keywords))[:10]
            )
            
            # Cache result
            self._cache_data(cache_key, score)
            
            # Store score
            self.sentiment_scores[SentimentSource.REDDIT].append(score)
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error analyzing Reddit sentiment: {str(e)}")
            return SentimentScore(
                source=SentimentSource.REDDIT,
                timestamp=datetime.now(),
                score=0,
                confidence=0,
                volume=0
            )

    async def _analyze_market_indicators(self) -> SentimentScore:
        """Analyze sentiment from market indicators"""
        try:
            # Put/Call ratio sentiment
            pc_score = (1.2 - self.put_call_ratio) / 0.4  # Normalize around 1.0
            pc_score = np.clip(pc_score, -1, 1)
            
            # VIX sentiment (inverse)
            vix_score = (20 - self.vix_level) / 10  # Normalize around 20
            vix_score = np.clip(vix_score, -1, 1)
            
            # Market breadth sentiment
            breadth_score = (self.market_breadth - 0.5) * 2  # Normalize 0-1 to -1 to 1
            
            # Fear & Greed sentiment
            fg_score = (self.fear_greed_index - 50) / 50  # Normalize 0-100 to -1 to 1
            
            # Combine indicators
            combined_score = (
                pc_score * 0.3 +
                vix_score * 0.3 +
                breadth_score * 0.2 +
                fg_score * 0.2
            )
            
            # Confidence based on indicator agreement
            scores = [pc_score, vix_score, breadth_score, fg_score]
            confidence = 1 - np.std(scores)
            
            score = SentimentScore(
                source=SentimentSource.MARKET_INDICATORS,
                timestamp=datetime.now(),
                score=combined_score,
                confidence=confidence,
                volume=4,  # Number of indicators
                keywords=['put/call', 'vix', 'breadth', 'fear/greed']
            )
            
            # Store score
            self.sentiment_scores[SentimentSource.MARKET_INDICATORS].append(score)
            
            return score
            
        except Exception as e:
            self.logger.error(f"Error analyzing market indicators: {str(e)}")
            return SentimentScore(
                source=SentimentSource.MARKET_INDICATORS,
                timestamp=datetime.now(),
                score=0,
                confidence=0,
                volume=0
            )

    async def _aggregate_sentiments(
        self,
        source_sentiments: Dict[SentimentSource, SentimentScore]
    ) -> Dict[str, Any]:
        """Aggregate sentiments from all sources"""
        try:
            if not source_sentiments:
                return {'score': 0, 'type': SentimentType.NEUTRAL, 'confidence': 0}
            
            # Weight by source importance and confidence
            weights = {
                SentimentSource.NEWS: 0.25,
                SentimentSource.REDDIT: 0.15,
                SentimentSource.TWITTER: 0.15,
                SentimentSource.MARKET_INDICATORS: 0.35,
                SentimentSource.ANALYST_RATINGS: 0.10
            }
            
            total_score = 0
            total_weight = 0
            
            for source, sentiment in source_sentiments.items():
                weight = weights.get(source, 0.1) * sentiment.confidence
                total_score += sentiment.score * weight
                total_weight += weight
            
            if total_weight > 0:
                overall_score = total_score / total_weight
            else:
                overall_score = 0
            
            # Determine sentiment type
            if overall_score > 0.3:
                sentiment_type = SentimentType.BULLISH
            elif overall_score < -0.3:
                sentiment_type = SentimentType.BEARISH
            elif abs(overall_score) < 0.1:
                sentiment_type = SentimentType.NEUTRAL
            else:
                sentiment_type = SentimentType.MIXED
            
            # Calculate confidence
            confidences = [s.confidence for s in source_sentiments.values()]
            avg_confidence = np.mean(confidences) if confidences else 0
            
            return {
                'score': overall_score,
                'type': sentiment_type,
                'confidence': avg_confidence
            }
            
        except Exception as e:
            self.logger.error(f"Error aggregating sentiments: {str(e)}")
            return {'score': 0, 'type': SentimentType.NEUTRAL, 'confidence': 0}

    async def _detect_event_risks(self) -> List[Dict[str, Any]]:
        """Detect potential event risks"""
        try:
            risks = []
            
            # Check recent events
            recent_events = list(self.event_alerts)[-10:]  # Last 10 events
            
            for event in recent_events:
                risk = {
                    'event': event.event_type,
                    'impact': event.impact.value,
                    'probability': event.confidence,
                    'expected_move': event.expected_move,
                    'volatility_impact': event.volatility_impact,
                    'time_to_event': 'immediate'
                }
                risks.append(risk)
            
            # Check upcoming scheduled events
            scheduled_risks = await self._check_scheduled_events()
            risks.extend(scheduled_risks)
            
            return risks
            
        except Exception as e:
            self.logger.error(f"Error detecting event risks: {str(e)}")
            return []

    async def _generate_trade_signal(
        self,
        sentiment: Dict[str, Any],
        event_risks: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate trade signal based on sentiment and risks"""
        try:
            score = sentiment['score']
            confidence = sentiment['confidence']
            
            # Check for high-risk events
            high_risk_events = [e for e in event_risks 
                              if 'high' in e.get('impact', '').lower()]
            
            if high_risk_events:
                return "AVOID - High risk events detected"
            
            # Generate signal based on sentiment
            if confidence < 0.6:
                return "WAIT - Low confidence"
            
            if score > 0.5:
                return "BULLISH - Consider bull strategies"
            elif score > 0.3:
                return "MILD_BULLISH - Consider neutral to bullish strategies"
            elif score < -0.5:
                return "BEARISH - Consider bear strategies"
            elif score < -0.3:
                return "MILD_BEARISH - Consider neutral to bearish strategies"
            else:
                return "NEUTRAL - Consider non-directional strategies"
            
        except Exception as e:
            self.logger.error(f"Error generating trade signal: {str(e)}")
            return None

    async def _ai_analyze_sentiment(self, text: str, source: str) -> Dict[str, Any]:
        """Use AI to analyze sentiment"""
        try:
            prompt = f"""
            Analyze the sentiment of this {source} text for SPY options trading:
            
            "{text}"
            
            Consider:
            1. Bullish or bearish sentiment (-1 to 1)
            2. Impact on SPY price movement
            3. Impact on volatility
            4. Key insights for options trading
            
            Return JSON with: score, confidence, insights
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            
            # Parse response
            try:
                result = json.loads(response)
                return result
            except:
                return {'score': 0, 'confidence': 0.5, 'insights': ''}
                
        except Exception as e:
            self.logger.error(f"Error in AI sentiment analysis: {str(e)}")
            return {'score': 0, 'confidence': 0.5, 'insights': ''}

    async def _search_event_pattern(self, pattern: str) -> List[Dict[str, Any]]:
        """Search for event patterns in recent data"""
        matches = []
        
        # Search in recent news
        for score_data in self.sentiment_scores[SentimentSource.NEWS]:
            if hasattr(score_data, 'raw_text') and score_data.raw_text:
                if re.search(pattern, score_data.raw_text, re.IGNORECASE):
                    matches.append({
                        'headline': score_data.raw_text[:100],
                        'source': 'news',
                        'timestamp': score_data.timestamp
                    })
        
        return matches

    async def _analyze_event_impact(
        self,
        event_type: str,
        match: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze impact of detected event"""
        
        # Default impacts by event type
        default_impacts = {
            'fed_meeting': {
                'impact': EventImpact.HIGH_NEGATIVE,
                'expected_move': 0.02,  # 2% move
                'volatility_impact': 0.20  # 20% IV increase
            },
            'earnings': {
                'impact': EventImpact.MODERATE_POSITIVE,
                'expected_move': 0.015,
                'volatility_impact': 0.10
            },
            'economic_data': {
                'impact': EventImpact.LOW_NEGATIVE,
                'expected_move': 0.01,
                'volatility_impact': 0.05
            },
            'geopolitical': {
                'impact': EventImpact.MODERATE_NEGATIVE,
                'expected_move': -0.015,
                'volatility_impact': 0.15
            },
            'market_crash': {
                'impact': EventImpact.HIGH_NEGATIVE,
                'expected_move': -0.05,
                'volatility_impact': 0.50
            }
        }
        
        base_impact = default_impacts.get(event_type, {
            'impact': EventImpact.NEUTRAL,
            'expected_move': 0,
            'volatility_impact': 0
        })
        
        # AI enhancement
        ai_adjustment = await self._ai_assess_event_impact(event_type, match)
        
        return {
            'impact': base_impact['impact'],
            'expected_move': base_impact['expected_move'] * ai_adjustment.get('multiplier', 1),
            'volatility_impact': base_impact['volatility_impact'] * ai_adjustment.get('multiplier', 1),
            'confidence': ai_adjustment.get('confidence', 0.7)
        }

    async def _ai_assess_event_impact(
        self,
        event_type: str,
        match: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use AI to assess event impact"""
        try:
            prompt = f"""
            Assess the market impact of this {event_type} event:
            "{match.get('headline', '')}"
            
            Consider historical similar events and current market conditions.
            Return JSON with: multiplier (0.5-2.0), confidence (0-1)
            """
            
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=1.5)
            
            try:
                return json.loads(response)
            except:
                return {'multiplier': 1.0, 'confidence': 0.7}
                
        except:
            return {'multiplier': 1.0, 'confidence': 0.7}

    async def _calculate_sentiment_trend(self, timeframe: timedelta) -> Dict[str, Any]:
        """Calculate sentiment trend for timeframe"""
        try:
            cutoff = datetime.now() - timeframe
            
            # Get historical sentiments
            recent_sentiments = []
            for sentiment in self.market_sentiment_history:
                if sentiment.timestamp > cutoff:
                    recent_sentiments.append({
                        'time': sentiment.timestamp,
                        'score': sentiment.overall_score
                    })
            
            if len(recent_sentiments) < 2:
                return {
                    'direction': 'stable',
                    'rate_of_change': 0,
                    'momentum': 0,
                    'reversal_probability': 0
                }
            
            # Sort by time
            recent_sentiments.sort(key=lambda x: x['time'])
            
            # Calculate trend
            scores = [s['score'] for s in recent_sentiments]
            times = [(s['time'] - recent_sentiments[0]['time']).total_seconds() / 3600 
                    for s in recent_sentiments]
            
            # Linear regression for trend
            if len(scores) > 1:
                slope, intercept = np.polyfit(times, scores, 1)
                
                # Determine direction
                if slope > 0.01:
                    direction = 'improving'
                elif slope < -0.01:
                    direction = 'deteriorating'
                else:
                    direction = 'stable'
                
                # Calculate momentum (acceleration)
                if len(scores) > 2:
                    first_half_avg = np.mean(scores[:len(scores)//2])
                    second_half_avg = np.mean(scores[len(scores)//2:])
                    momentum = second_half_avg - first_half_avg
                else:
                    momentum = 0
                
                # Reversal probability (extreme sentiment)
                current_score = scores[-1]
                if abs(current_score) > 0.7:
                    reversal_probability = abs(current_score) - 0.7
                else:
                    reversal_probability = 0
                
                return {
                    'direction': direction,
                    'rate_of_change': slope,
                    'momentum': momentum,
                    'reversal_probability': reversal_probability
                }
            
            return {
                'direction': 'stable',
                'rate_of_change': 0,
                'momentum': 0,
                'reversal_probability': 0
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating sentiment trend: {str(e)}")
            return {
                'direction': 'stable',
                'rate_of_change': 0,
                'momentum': 0,
                'reversal_probability': 0
            }

    def _interpret_put_call_ratio(self, ratio: float) -> float:
        """Interpret put/call ratio as sentiment"""
        # Higher P/C ratio = more bearish
        # Normal range: 0.7 - 1.3
        if ratio > 1.3:
            return -0.8  # Very bearish
        elif ratio > 1.1:
            return -0.4  # Bearish
        elif ratio < 0.7:
            return 0.8   # Very bullish
        elif ratio < 0.9:
            return 0.4   # Bullish
        else:
            return 0     # Neutral

    def _interpret_vix_level(self, vix: float) -> float:
        """Interpret VIX level as sentiment"""
        # Higher VIX = more fear/bearish
        if vix > 30:
            return -0.9  # Extreme fear
        elif vix > 25:
            return -0.6  # High fear
        elif vix > 20:
            return -0.3  # Moderate fear
        elif vix < 12:
            return 0.6   # Complacency (bullish)
        elif vix < 15:
            return 0.3   # Low fear (bullish)
        else:
            return 0     # Normal

    def _get_pc_signal(self, ratio: float) -> str:
        """Get signal from put/call ratio"""
        if ratio > 1.3:
            return "Extreme bearish positioning - potential reversal"
        elif ratio > 1.1:
            return "Bearish positioning"
        elif ratio < 0.7:
            return "Extreme bullish positioning - potential reversal"
        elif ratio < 0.9:
            return "Bullish positioning"
        else:
            return "Neutral positioning"

    def _get_vix_regime(self, vix: float) -> str:
        """Get VIX regime"""
        if vix > 30:
            return "Crisis/Panic"
        elif vix > 25:
            return "High Volatility"
        elif vix > 20:
            return "Elevated Volatility"
        elif vix < 12:
            return "Low Volatility/Complacency"
        else:
            return "Normal Volatility"

    async def _analyze_options_flow(self) -> Dict[str, Any]:
        """Analyze options flow sentiment"""
        # Simplified implementation
        return {
            'large_call_buying': 0.3,  # Bullish
            'large_put_buying': -0.2,  # Bearish
            'call_volume_ratio': 0.55,  # Slightly bullish
            'unusual_activity': False
        }

    async def _analyze_term_structure(self) -> Dict[str, Any]:
        """Analyze options term structure"""
        # Simplified implementation
        return {
            'term_structure_slope': 0.1,  # Normal contango
            'near_term_premium': 'normal',
            'calendar_opportunity': False
        }

    def _combine_options_sentiment(
        self,
        pc_sentiment: float,
        vix_sentiment: float,
        flow_sentiment: Dict[str, Any]
    ) -> float:
        """Combine options-specific sentiments"""
        flow_score = (
            flow_sentiment.get('large_call_buying', 0) +
            flow_sentiment.get('large_put_buying', 0)
        )
        
        return (pc_sentiment * 0.4 + vix_sentiment * 0.4 + flow_score * 0.2)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if w not in common_words and len(w) > 3]
        
        # Count occurrences
        word_count = defaultdict(int)
        for word in keywords:
            word_count[word] += 1
        
        # Return top keywords
        sorted_keywords = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_keywords[:10]]

    def _get_trending_topics(self) -> List[str]:
        """Get current trending topics"""
        # Get recent keywords
        recent_keywords = []
        
        for source_scores in self.sentiment_scores.values():
            for score in list(source_scores)[-10:]:  # Last 10 entries
                recent_keywords.extend(score.keywords)
        
        # Count frequencies
        topic_count = defaultdict(int)
        for keyword in recent_keywords:
            topic_count[keyword] += 1
        
        # Sort by frequency
        sorted_topics = sorted(topic_count.items(), key=lambda x: x[1], reverse=True)
        
        return [topic for topic, count in sorted_topics[:5]]

    async def _fetch_news_articles(self) -> List[Dict[str, Any]]:
        """Fetch news articles (mock implementation)"""
        # In production, would use news API
        return [
            {
                'title': 'SPY Reaches New All-Time High on Strong Economic Data',
                'description': 'Markets rally as inflation shows signs of cooling',
                'source': 'Financial Times',
                'publishedAt': datetime.now().isoformat()
            },
            {
                'title': 'Fed Minutes Suggest Potential Rate Cuts in 2025',
                'description': 'Federal Reserve considering policy shift',
                'source': 'Reuters',
                'publishedAt': datetime.now().isoformat()
            }
        ]

    async def _fetch_reddit_posts(self) -> List[Dict[str, Any]]:
        """Fetch Reddit posts (mock implementation)"""
        # In production, would use Reddit API
        return [
            {
                'title': 'SPY to the moon! 🚀 Technical analysis inside',
                'selftext': 'Breaking through resistance at 450...',
                'score': 150,
                'num_comments': 45
            },
            {
                'title': 'Why I think we\'re due for a correction',
                'selftext': 'Overbought conditions across the board...',
                'score': 89,
                'num_comments': 67
            }
        ]

    async def _check_scheduled_events(self) -> List[Dict[str, Any]]:
        """Check for scheduled market events"""
        # Simplified - would check economic calendar
        return [
            {
                'event': 'fomc_meeting',
                'impact': 'high',
                'probability': 1.0,
                'expected_move': 0.02,
                'volatility_impact': 0.15,
                'time_to_event': '2 days'
            }
        ]

    def _get_cached_data(self, key: str) -> Optional[Any]:
        """Get cached data if still valid"""
        if key in self.api_cache:
            data, timestamp = self.api_cache[key]
            if datetime.now() - timestamp < self.cache_duration:
                return data
        return None

    def _cache_data(self, key: str, data: Any):
        """Cache data with timestamp"""
        self.api_cache[key] = (data, datetime.now())

    def _get_default_sentiment(self) -> MarketSentiment:
        """Get default sentiment when analysis fails"""
        return MarketSentiment(
            timestamp=datetime.now(),
            overall_score=0,
            sentiment_type=SentimentType.NEUTRAL,
            confidence=0,
            source_scores={},
            trending_topics=[],
            event_risks=[],
            trade_signal="WAIT - Unable to analyze sentiment"
        )

    async def _monitor_sentiment_loop(self):
        """Background task to monitor sentiment"""
        while self.state == AgentState.RUNNING:
            try:
                # Update sentiment every N minutes
                await asyncio.sleep(self.update_frequency * 60)
                
                # Get latest sentiment
                await self.get_market_sentiment()
                
            except Exception as e:
                self.logger.error(f"Error in sentiment monitoring loop: {str(e)}")

    async def _analyze_trends_loop(self):
        """Background task to analyze sentiment trends"""
        while self.state == AgentState.RUNNING:
            try:
                # Analyze trends every 30 minutes
                await asyncio.sleep(1800)
                
                trends = await self.get_sentiment_trends()
                
                # Check for significant changes
                for period, trend in trends.items():
                    if abs(trend.rate_of_change) > 0.1:
                        self.logger.info(
                            f"Significant sentiment trend in {period}: "
                            f"{trend.direction} at {trend.rate_of_change:.3f}/hour"
                        )
                
            except Exception as e:
                self.logger.error(f"Error in trends analysis loop: {str(e)}")

    async def _detect_events_loop(self):
        """Background task to detect market events"""
        while self.state == AgentState.RUNNING:
            try:
                # Check for events every 15 minutes
                await asyncio.sleep(900)
                
                events = await self.detect_market_events()
                
                # Alert on high-impact events
                for event in events:
                    if 'high' in event.impact.value:
                        if self.event_manager:
                            await self.event_manager.publish(Event(
                                type=EventType.HIGH_IMPACT_EVENT,
                                data={'event': event}
                            ))
                
            except Exception as e:
                self.logger.error(f"Error in event detection loop: {str(e)}")

    async def _update_market_indicators_loop(self):
        """Background task to update market indicators"""
        while self.state == AgentState.RUNNING:
            try:
                # Update every 5 minutes
                await asyncio.sleep(300)
                
                # In production, would fetch from data provider
                # Mock updates for now
                self.put_call_ratio = np.random.normal(1.0, 0.2)
                self.vix_level = np.random.normal(18, 3)
                self.market_breadth = np.random.uniform(0.3, 0.7)
                self.fear_greed_index = np.random.uniform(30, 70)
                
            except Exception as e:
                self.logger.error(f"Error updating market indicators: {str(e)}")

    async def _handle_market_update(self, event: Event):
        """Handle market data updates"""
        # Could trigger immediate sentiment analysis on big moves
        pass

    async def _handle_news_update(self, event: Event):
        """Handle news updates"""
        try:
            # Analyze new news immediately
            news_data = event.data
            sentiment = await self.analyze_text_sentiment(
                news_data.get('headline', ''),
                source='news'
            )
            
            # Check if significant
            if abs(sentiment['score']) > 0.7:
                self.logger.info(f"Significant news sentiment: {sentiment['score']:.2f}")
                
        except Exception as e:
            self.logger.error(f"Error handling news update: {str(e)}")


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_sentiment_analysis_agent(config: Dict[str, Any]) -> SentimentAnalysisAgent:
    """
    Factory function to create SentimentAnalysisAgent.
    
    Args:
        config: Agent configuration dictionary
        
    Returns:
        Configured SentimentAnalysisAgent instance
    """
    return SentimentAnalysisAgent(config)

