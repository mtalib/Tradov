#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX11_SentimentAnalysisAgent.py
Purpose: AI-Enhanced Market Sentiment Analysis and Social Media Monitoring
Group: X (AI Agents)

This module implements an intelligent sentiment analysis agent that monitors
market sentiment from various sources, analyzes social media trends, and
provides AI-driven insights using Ollama integration.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-16
Last Updated: 2025-06-19 Time: 13:59
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import re
import statistics

# Third-party imports
import numpy as np

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Sentiment sources
class SentimentSource(Enum):
    """Sentiment data sources."""
    REDDIT = "REDDIT"
    TWITTER = "TWITTER"
    NEWS = "NEWS"
    FORUMS = "FORUMS"
    ANALYST = "ANALYST"
    OPTIONS_FLOW = "OPTIONS_FLOW"
    INSIDER = "INSIDER"
    INSTITUTIONAL = "INSTITUTIONAL"

# Sentiment categories
class SentimentCategory(Enum):
    """Sentiment categories."""
    VERY_BULLISH = "VERY_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    VERY_BEARISH = "VERY_BEARISH"

# Entity types for tracking
class EntityType(Enum):
    """Entity types to track."""
    TICKER = "TICKER"
    SECTOR = "SECTOR"
    TOPIC = "TOPIC"
    PERSON = "PERSON"
    EVENT = "EVENT"

# Sentiment indicators
SENTIMENT_INDICATORS = {
    'bullish': ['buy', 'long', 'calls', 'moon', 'bullish', 'up', 'green', 'pump', 'squeeze'],
    'bearish': ['sell', 'short', 'puts', 'crash', 'bearish', 'down', 'red', 'dump', 'drill'],
    'fear': ['fear', 'panic', 'scared', 'worried', 'concern', 'risk', 'volatile'],
    'greed': ['greed', 'fomo', 'yolo', 'diamond hands', 'to the moon', 'rocket'],
    'uncertainty': ['maybe', 'unsure', 'confused', 'volatile', 'unpredictable']
}

# Trending thresholds
TRENDING_THRESHOLDS = {
    'volume_spike': 2.0,      # 2x normal volume
    'mention_spike': 3.0,     # 3x normal mentions
    'sentiment_shift': 0.2,   # 20% sentiment change
    'velocity_threshold': 5   # Mentions per minute
}

# Default configuration
DEFAULT_CONFIG = {
    'sentiment_window': 60,          # Minutes
    'trend_detection_window': 30,    # Minutes
    'min_mentions_threshold': 10,    # Minimum mentions to consider
    'sentiment_decay_rate': 0.95,    # Exponential decay for old sentiment
    'anomaly_detection_std': 2.5     # Standard deviations for anomaly
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.4

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SentimentData:
    """Individual sentiment data point."""
    source: SentimentSource
    timestamp: datetime
    content: str
    author: Optional[str]
    sentiment_score: float  # -1 to 1
    confidence: float      # 0 to 1
    entities: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SentimentSummary:
    """Sentiment summary for an entity."""
    entity: str
    entity_type: EntityType
    overall_sentiment: SentimentCategory
    sentiment_score: float
    volume: int
    trend: str  # 'increasing', 'stable', 'decreasing'
    momentum: float
    sources: Dict[str, int]
    key_themes: List[str]
    ai_insights: Dict[str, Any]

@dataclass
class MarketSentiment:
    """Overall market sentiment analysis."""
    timestamp: datetime
    overall_category: SentimentCategory
    composite_score: float  # -1 to 1
    fear_greed_index: float  # 0 to 100
    put_call_ratio: Optional[float]
    vix_correlation: Optional[float]
    top_bullish: List[Tuple[str, float]]
    top_bearish: List[Tuple[str, float]]
    trending_topics: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    ai_analysis: Dict[str, Any]

@dataclass
class SentimentAlert:
    """Sentiment-based alert."""
    timestamp: datetime
    alert_type: str  # 'spike', 'reversal', 'anomaly', 'trend'
    entity: str
    description: str
    severity: str  # 'high', 'medium', 'low'
    data: Dict[str, Any]
    recommended_action: Optional[str]

# ==============================================================================
# SENTIMENT ANALYSIS AGENT CLASS
# ==============================================================================

class SpyderX11_SentimentAnalysisAgent:
    """
    AI-Enhanced Sentiment Analysis Agent.
    
    This agent analyzes market sentiment from multiple sources using AI to
    identify trends, anomalies, and trading opportunities.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Sentiment Analysis Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Data storage
        self.sentiment_buffer = deque(maxlen=10000)
        self.entity_sentiments = defaultdict(list)
        self.trending_entities = set()
        
        # Tracking
        self.sentiment_history = defaultdict(lambda: deque(maxlen=1000))
        self.anomaly_history = deque(maxlen=100)
        
        # Baseline metrics
        self.baseline_volumes = defaultdict(lambda: 50)  # Default baseline
        self.baseline_sentiments = defaultdict(lambda: 0.0)
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # MAIN ANALYSIS METHODS
    # ==========================================================================
    
    async def analyze_sentiment(self, data_points: List[SentimentData]) -> MarketSentiment:
        """
        Analyze sentiment from multiple data points.
        
        Args:
            data_points: List of sentiment data points
            
        Returns:
            MarketSentiment analysis
        """
        self.logger.info(f"Analyzing sentiment from {len(data_points)} data points")
        
        try:
            # Add to buffer
            self.sentiment_buffer.extend(data_points)
            
            # Update entity sentiments
            self._update_entity_sentiments(data_points)
            
            # Calculate overall sentiment
            overall_sentiment = self._calculate_overall_sentiment()
            
            # Calculate fear/greed index
            fear_greed = self._calculate_fear_greed_index()
            
            # Identify top movers
            top_bullish, top_bearish = self._identify_top_movers()
            
            # Detect trending topics
            trending = await self._detect_trending_topics()
            
            # Detect anomalies
            anomalies = self._detect_sentiment_anomalies()
            
            # Get AI analysis
            ai_analysis = await self._get_ai_market_sentiment_analysis(
                overall_sentiment, trending, anomalies
            )
            
            # Determine category
            category = self._score_to_category(overall_sentiment)
            
            return MarketSentiment(
                timestamp=datetime.now(),
                overall_category=category,
                composite_score=overall_sentiment,
                fear_greed_index=fear_greed,
                put_call_ratio=None,  # Would come from options data
                vix_correlation=None,  # Would come from market data
                top_bullish=top_bullish,
                top_bearish=top_bearish,
                trending_topics=trending,
                anomalies=anomalies,
                ai_analysis=ai_analysis
            )
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {e}")
            return self._create_default_market_sentiment()
    
    async def analyze_entity_sentiment(self, entity: str,
                                     entity_type: EntityType = EntityType.TICKER) -> SentimentSummary:
        """
        Analyze sentiment for a specific entity.
        
        Args:
            entity: Entity to analyze (e.g., 'SPY')
            entity_type: Type of entity
            
        Returns:
            SentimentSummary for the entity
        """
        self.logger.info(f"Analyzing sentiment for {entity}")
        
        try:
            # Get recent mentions
            mentions = self._get_entity_mentions(entity)
            
            if not mentions:
                return self._create_empty_sentiment_summary(entity, entity_type)
            
            # Calculate metrics
            sentiment_score = self._calculate_entity_sentiment(mentions)
            volume = len(mentions)
            trend = self._calculate_sentiment_trend(entity)
            momentum = self._calculate_sentiment_momentum(entity)
            
            # Source breakdown
            sources = self._analyze_sources(mentions)
            
            # Extract themes
            themes = await self._extract_key_themes(mentions)
            
            # Get AI insights
            ai_insights = await self._get_ai_entity_insights(entity, mentions, themes)
            
            # Determine category
            category = self._score_to_category(sentiment_score)
            
            return SentimentSummary(
                entity=entity,
                entity_type=entity_type,
                overall_sentiment=category,
                sentiment_score=sentiment_score,
                volume=volume,
                trend=trend,
                momentum=momentum,
                sources=sources,
                key_themes=themes,
                ai_insights=ai_insights
            )
            
        except Exception as e:
            self.logger.error(f"Entity sentiment analysis failed: {e}")
            return self._create_empty_sentiment_summary(entity, entity_type)
    
    async def detect_sentiment_shifts(self, 
                                    lookback_minutes: int = 60) -> List[SentimentAlert]:
        """
        Detect significant sentiment shifts.
        
        Args:
            lookback_minutes: Minutes to look back
            
        Returns:
            List of sentiment alerts
        """
        self.logger.info("Detecting sentiment shifts")
        
        alerts = []
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        # Check each tracked entity
        for entity, history in self.sentiment_history.items():
            recent_data = [d for d in history if d['timestamp'] > cutoff_time]
            
            if len(recent_data) < 10:  # Need minimum data
                continue
            
            # Detect various patterns
            spike_alert = self._detect_sentiment_spike(entity, recent_data)
            if spike_alert:
                alerts.append(spike_alert)
            
            reversal_alert = self._detect_sentiment_reversal(entity, recent_data)
            if reversal_alert:
                alerts.append(reversal_alert)
            
            trend_alert = self._detect_new_trend(entity, recent_data)
            if trend_alert:
                alerts.append(trend_alert)
        
        # Get AI recommendations for alerts
        if alerts and self.ollama_client:
            alerts = await self._enhance_alerts_with_ai(alerts)
        
        return alerts
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _get_ai_market_sentiment_analysis(self, overall_score: float,
                                              trending: List[Dict[str, Any]],
                                              anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get AI analysis of market sentiment."""
        if not self.ollama_client:
            return {'analysis': 'No AI available'}
        
        prompt = f"""Analyze this market sentiment data:

Overall Sentiment Score: {overall_score:.2f} (-1 to 1)
Sentiment Category: {self._score_to_category(overall_score).value}

Top Trending Topics:
{json.dumps(trending[:5], indent=2)}

Detected Anomalies:
{json.dumps(anomalies[:3], indent=2)}

Recent Market Context:
- SPY options flow sentiment
- Social media buzz around Fed decisions
- Retail vs institutional sentiment divergence

Provide a JSON response:
{{
    "market_interpretation": "overall market mood and why",
    "key_drivers": ["driver1", "driver2", ...],
    "contrarian_signals": ["signal1", "signal2", ...],
    "risk_factors": ["risk1", "risk2", ...],
    "trading_implications": "how to trade this sentiment",
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'analysis': 'Failed to parse AI response'}
                
        except Exception as e:
            self.logger.error(f"AI market sentiment analysis failed: {e}")
            return {'error': str(e)}
    
    async def _get_ai_entity_insights(self, entity: str,
                                    mentions: List[SentimentData],
                                    themes: List[str]) -> Dict[str, Any]:
        """Get AI insights for entity sentiment."""
        if not self.ollama_client:
            return {'insights': 'No AI available'}
        
        # Prepare mention summary
        mention_summary = self._summarize_mentions(mentions[:10])
        
        prompt = f"""Analyze sentiment for {entity}:

Recent Mentions: {len(mentions)}
Average Sentiment: {np.mean([m.sentiment_score for m in mentions]):.2f}
Key Themes: {', '.join(themes)}

Sample Mentions:
{mention_summary}

Provide a JSON response:
{{
    "sentiment_driver": "what's driving the sentiment",
    "authenticity_score": 0.0-1.0,
    "manipulation_risk": "low/medium/high",
    "smart_money_view": "likely institutional sentiment",
    "retail_view": "likely retail sentiment",
    "actionable_insight": "specific trading insight",
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'insights': 'Failed to parse'}
                
        except Exception as e:
            self.logger.error(f"AI entity insights failed: {e}")
            return {'error': str(e)}
    
    async def _extract_key_themes(self, mentions: List[SentimentData]) -> List[str]:
        """Extract key themes from mentions using AI."""
        if not self.ollama_client or not mentions:
            return self._extract_themes_rule_based(mentions)
        
        # Combine recent mention content
        combined_text = ' '.join([m.content for m in mentions[:20]])
        
        prompt = f"""Extract key themes from these market mentions:

{combined_text[:1000]}...

Identify 3-5 main themes being discussed.

Provide a JSON response:
{{
    "themes": ["theme1", "theme2", "theme3", ...]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return data.get('themes', [])[:5]
            else:
                return self._extract_themes_rule_based(mentions)
                
        except Exception as e:
            self.logger.error(f"AI theme extraction failed: {e}")
            return self._extract_themes_rule_based(mentions)
    
    async def _detect_trending_topics(self) -> List[Dict[str, Any]]:
        """Detect trending topics using AI and statistics."""
        trending = []
        
        # Get volume spikes
        volume_spikes = self._detect_volume_spikes()
        
        # Get sentiment shifts
        sentiment_shifts = self._detect_sentiment_shifts_internal()
        
        # Combine and rank
        all_topics = set(volume_spikes.keys()) | set(sentiment_shifts.keys())
        
        for topic in all_topics:
            volume_change = volume_spikes.get(topic, 1.0)
            sentiment_change = sentiment_shifts.get(topic, 0.0)
            
            # Calculate trend score
            trend_score = (volume_change * 0.6 + abs(sentiment_change) * 0.4)
            
            if trend_score > 1.5:  # Threshold for trending
                trending.append({
                    'topic': topic,
                    'trend_score': trend_score,
                    'volume_change': volume_change,
                    'sentiment_change': sentiment_change,
                    'category': 'bullish' if sentiment_change > 0 else 'bearish'
                })
        
        # Sort by trend score
        trending.sort(key=lambda x: x['trend_score'], reverse=True)
        
        # Enhance with AI if available
        if trending and self.ollama_client:
            trending = await self._enhance_trending_with_ai(trending[:10])
        
        return trending[:10]  # Top 10
    
    async def _enhance_trending_with_ai(self, 
                                      trending: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance trending topics with AI insights."""
        if not self.ollama_client:
            return trending
        
        prompt = f"""Analyze these trending market topics:

{json.dumps(trending, indent=2)}

For each topic, assess its market impact and trading relevance.

Provide a JSON response:
{{
    "enhanced_topics": [
        {{
            "topic": "original topic",
            "market_impact": "high/medium/low",
            "duration_estimate": "hours/days/weeks",
            "trading_opportunity": "description",
            "risk_level": "high/medium/low"
        }}
    ]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                enhanced = data.get('enhanced_topics', [])
                
                # Merge enhancements
                for i, topic in enumerate(trending):
                    if i < len(enhanced):
                        topic.update(enhanced[i])
                
            return trending
                
        except Exception as e:
            self.logger.error(f"AI trending enhancement failed: {e}")
            return trending
    
    async def _enhance_alerts_with_ai(self, 
                                    alerts: List[SentimentAlert]) -> List[SentimentAlert]:
        """Enhance sentiment alerts with AI recommendations."""
        if not self.ollama_client or not alerts:
            return alerts
        
        # Prepare alert summary
        alert_summary = [{
            'type': a.alert_type,
            'entity': a.entity,
            'description': a.description
        } for a in alerts[:5]]
        
        prompt = f"""Analyze these sentiment alerts and provide trading recommendations:

{json.dumps(alert_summary, indent=2)}

For each alert, suggest specific trading actions.

Provide a JSON response:
{{
    "recommendations": [
        {{
            "alert_index": 0,
            "action": "specific trading action",
            "reasoning": "why this action",
            "risk_management": "stop loss or hedge",
            "confidence": 0.0-1.0
        }}
    ]
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                recommendations = data.get('recommendations', [])
                
                # Apply recommendations to alerts
                for rec in recommendations:
                    idx = rec.get('alert_index', 0)
                    if 0 <= idx < len(alerts):
                        alerts[idx].recommended_action = rec.get('action', '')
                        alerts[idx].data['ai_reasoning'] = rec.get('reasoning', '')
                        alerts[idx].data['risk_management'] = rec.get('risk_management', '')
            
            return alerts
                
        except Exception as e:
            self.logger.error(f"AI alert enhancement failed: {e}")
            return alerts
    
    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    
    def _calculate_overall_sentiment(self) -> float:
        """Calculate overall market sentiment score."""
        recent_window = datetime.now() - timedelta(minutes=self.config['sentiment_window'])
        recent_data = [d for d in self.sentiment_buffer if d.timestamp > recent_window]
        
        if not recent_data:
            return 0.0
        
        # Weight by confidence and recency
        weighted_sum = 0.0
        total_weight = 0.0
        
        for data in recent_data:
            # Time decay
            age_minutes = (datetime.now() - data.timestamp).total_seconds() / 60
            time_weight = self.config['sentiment_decay_rate'] ** (age_minutes / 60)
            
            # Combined weight
            weight = data.confidence * time_weight
            weighted_sum += data.sentiment_score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _calculate_fear_greed_index(self) -> float:
        """Calculate fear/greed index (0-100)."""
        # Get sentiment indicators
        fear_count = 0
        greed_count = 0
        
        recent_window = datetime.now() - timedelta(minutes=30)
        recent_data = [d for d in self.sentiment_buffer if d.timestamp > recent_window]
        
        for data in recent_data:
            content_lower = data.content.lower()
            
            # Count fear indicators
            for indicator in SENTIMENT_INDICATORS['fear']:
                if indicator in content_lower:
                    fear_count += 1
            
            # Count greed indicators
            for indicator in SENTIMENT_INDICATORS['greed']:
                if indicator in content_lower:
                    greed_count += 1
        
        # Calculate index
        total_indicators = fear_count + greed_count
        if total_indicators == 0:
            return 50.0  # Neutral
        
        greed_ratio = greed_count / total_indicators
        return greed_ratio * 100
    
    def _identify_top_movers(self) -> Tuple[List[Tuple[str, float]], 
                                          List[Tuple[str, float]]]:
        """Identify top bullish and bearish entities."""
        entity_scores = defaultdict(list)
        
        # Aggregate scores by entity
        for entity, sentiments in self.entity_sentiments.items():
            if sentiments:
                avg_score = np.mean([s.sentiment_score for s in sentiments[-20:]])
                volume = len(sentiments)
                
                if volume >= self.config['min_mentions_threshold']:
                    entity_scores[entity] = avg_score
        
        # Sort and separate
        sorted_entities = sorted(entity_scores.items(), key=lambda x: x[1])
        
        top_bearish = [(e, s) for e, s in sorted_entities[:5] if s < 0]
        top_bullish = [(e, s) for e, s in sorted_entities[-5:] if s > 0]
        top_bullish.reverse()  # Highest first
        
        return top_bullish, top_bearish
    
    def _detect_sentiment_anomalies(self) -> List[Dict[str, Any]]:
        """Detect sentiment anomalies."""
        anomalies = []
        
        for entity, history in self.sentiment_history.items():
            if len(history) < 20:
                continue
            
            # Calculate baseline statistics
            scores = [h['score'] for h in history]
            mean_score = np.mean(scores)
            std_score = np.std(scores)
            
            # Check latest score
            if history:
                latest = history[-1]
                z_score = abs((latest['score'] - mean_score) / std_score) if std_score > 0 else 0
                
                if z_score > self.config['anomaly_detection_std']:
                    anomalies.append({
                        'entity': entity,
                        'type': 'sentiment_anomaly',
                        'z_score': z_score,
                        'current_score': latest['score'],
                        'baseline_score': mean_score,
                        'timestamp': latest['timestamp']
                    })
        
        # Sort by z-score
        anomalies.sort(key=lambda x: x['z_score'], reverse=True)
        
        return anomalies[:10]  # Top 10 anomalies
    
    def _detect_sentiment_spike(self, entity: str,
                              recent_data: List[Dict[str, Any]]) -> Optional[SentimentAlert]:
        """Detect sentiment spike for entity."""
        if len(recent_data) < 5:
            return None
        
        # Compare recent vs historical
        recent_scores = [d['score'] for d in recent_data[-5:]]
        historical_scores = [d['score'] for d in recent_data[:-5]]
        
        if not historical_scores:
            return None
        
        recent_avg = np.mean(recent_scores)
        historical_avg = np.mean(historical_scores)
        
        change = abs(recent_avg - historical_avg)
        
        if change > TRENDING_THRESHOLDS['sentiment_shift']:
            direction = 'bullish' if recent_avg > historical_avg else 'bearish'
            
            return SentimentAlert(
                timestamp=datetime.now(),
                alert_type='spike',
                entity=entity,
                description=f"Sentiment spike detected: {direction} move of {change:.1%}",
                severity='high' if change > 0.3 else 'medium',
                data={
                    'recent_sentiment': recent_avg,
                    'historical_sentiment': historical_avg,
                    'change': change,
                    'direction': direction
                },
                recommended_action=None
            )
        
        return None
    
    def _detect_sentiment_reversal(self, entity: str,
                                 recent_data: List[Dict[str, Any]]) -> Optional[SentimentAlert]:
        """Detect sentiment reversal."""
        if len(recent_data) < 10:
            return None
        
        # Check for reversal pattern
        first_half = [d['score'] for d in recent_data[:len(recent_data)//2]]
        second_half = [d['score'] for d in recent_data[len(recent_data)//2:]]
        
        first_avg = np.mean(first_half)
        second_avg = np.mean(second_half)
        
        # Check if sentiment reversed sign
        if first_avg * second_avg < 0 and abs(first_avg - second_avg) > 0.3:
            direction = 'bullish' if second_avg > 0 else 'bearish'
            
            return SentimentAlert(
                timestamp=datetime.now(),
                alert_type='reversal',
                entity=entity,
                description=f"Sentiment reversal: turned {direction}",
                severity='high',
                data={
                    'previous_sentiment': first_avg,
                    'current_sentiment': second_avg,
                    'reversal_strength': abs(first_avg - second_avg)
                },
                recommended_action=None
            )
        
        return None
    
    def _detect_new_trend(self, entity: str,
                        recent_data: List[Dict[str, Any]]) -> Optional[SentimentAlert]:
        """Detect new sentiment trend."""
        if len(recent_data) < 15:
            return None
        
        # Calculate trend using linear regression (simplified)
        x = list(range(len(recent_data)))
        y = [d['score'] for d in recent_data]
        
        # Simple slope calculation
        n = len(x)
        slope = (n * sum(i*y[i] for i in x) - sum(x) * sum(y)) / (n * sum(i**2 for i in x) - sum(x)**2)
        
        # Significant trend threshold
        if abs(slope) > 0.01:  # Adjust threshold as needed
            direction = 'bullish' if slope > 0 else 'bearish'
            
            return SentimentAlert(
                timestamp=datetime.now(),
                alert_type='trend',
                entity=entity,
                description=f"New {direction} trend detected",
                severity='medium',
                data={
                    'trend_slope': slope,
                    'direction': direction,
                    'strength': abs(slope)
                },
                recommended_action=None
            )
        
        return None
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _update_entity_sentiments(self, data_points: List[SentimentData]):
        """Update entity sentiment tracking."""
        for data in data_points:
            for entity in data.entities:
                self.entity_sentiments[entity].append(data)
                
                # Update history
                self.sentiment_history[entity].append({
                    'timestamp': data.timestamp,
                    'score': data.sentiment_score,
                    'volume': 1
                })
        
        # Clean old data
        cutoff = datetime.now() - timedelta(hours=24)
        for entity in list(self.entity_sentiments.keys()):
            self.entity_sentiments[entity] = [
                d for d in self.entity_sentiments[entity] if d.timestamp > cutoff
            ]
    
    def _get_entity_mentions(self, entity: str) -> List[SentimentData]:
        """Get recent mentions of an entity."""
        mentions = self.entity_sentiments.get(entity, [])
        recent_window = datetime.now() - timedelta(minutes=self.config['sentiment_window'])
        return [m for m in mentions if m.timestamp > recent_window]
    
    def _calculate_entity_sentiment(self, mentions: List[SentimentData]) -> float:
        """Calculate weighted sentiment for entity."""
        if not mentions:
            return 0.0
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for mention in mentions:
            # Weight by confidence and source reliability
            source_weight = self._get_source_weight(mention.source)
            weight = mention.confidence * source_weight
            
            weighted_sum += mention.sentiment_score * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _get_source_weight(self, source: SentimentSource) -> float:
        """Get reliability weight for source."""
        weights = {
            SentimentSource.ANALYST: 1.0,
            SentimentSource.INSTITUTIONAL: 0.9,
            SentimentSource.OPTIONS_FLOW: 0.85,
            SentimentSource.NEWS: 0.8,
            SentimentSource.INSIDER: 0.9,
            SentimentSource.TWITTER: 0.6,
            SentimentSource.REDDIT: 0.5,
            SentimentSource.FORUMS: 0.4
        }
        return weights.get(source, 0.5)
    
    def _calculate_sentiment_trend(self, entity: str) -> str:
        """Calculate sentiment trend for entity."""
        history = self.sentiment_history.get(entity, [])
        
        if len(history) < 10:
            return 'stable'
        
        # Compare recent vs older
        recent = [h['score'] for h in history[-10:]]
        older = [h['score'] for h in history[-20:-10]]
        
        recent_avg = np.mean(recent)
        older_avg = np.mean(older)
        
        change = recent_avg - older_avg
        
        if change > 0.1:
            return 'increasing'
        elif change < -0.1:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_sentiment_momentum(self, entity: str) -> float:
        """Calculate sentiment momentum."""
        history = self.sentiment_history.get(entity, [])
        
        if len(history) < 5:
            return 0.0
        
        # Rate of change
        recent_scores = [h['score'] for h in history[-5:]]
        momentum = recent_scores[-1] - recent_scores[0]
        
        return momentum
    
    def _analyze_sources(self, mentions: List[SentimentData]) -> Dict[str, int]:
        """Analyze mention sources."""
        source_counts = defaultdict(int)
        
        for mention in mentions:
            source_counts[mention.source.value] += 1
        
        return dict(source_counts)
    
    def _score_to_category(self, score: float) -> SentimentCategory:
        """Convert sentiment score to category."""
        if score >= 0.5:
            return SentimentCategory.VERY_BULLISH
        elif score >= 0.2:
            return SentimentCategory.BULLISH
        elif score >= -0.2:
            return SentimentCategory.NEUTRAL
        elif score >= -0.5:
            return SentimentCategory.BEARISH
        else:
            return SentimentCategory.VERY_BEARISH
    
    def _extract_themes_rule_based(self, mentions: List[SentimentData]) -> List[str]:
        """Extract themes using rule-based approach."""
        theme_counts = defaultdict(int)
        
        # Count sentiment indicators
        for mention in mentions:
            content_lower = mention.content.lower()
            
            for category, indicators in SENTIMENT_INDICATORS.items():
                for indicator in indicators:
                    if indicator in content_lower:
                        theme_counts[category] += 1
        
        # Sort by frequency
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [theme for theme, _ in sorted_themes[:5]]
    
    def _summarize_mentions(self, mentions: List[SentimentData]) -> str:
        """Summarize mentions for AI prompt."""
        summaries = []
        
        for mention in mentions[:5]:
            summary = f"- [{mention.source.value}] ({mention.sentiment_score:+.2f}): "
            summary += mention.content[:100] + "..."
            summaries.append(summary)
        
        return "\n".join(summaries)
    
    def _detect_volume_spikes(self) -> Dict[str, float]:
        """Detect volume spikes by entity."""
        volume_changes = {}
        
        for entity, history in self.sentiment_history.items():
            if len(history) < 20:
                continue
            
            # Recent vs baseline volume
            recent_count = len([h for h in history[-10:]])
            baseline_count = len([h for h in history[-30:-10]]) / 2  # Normalize
            
            if baseline_count > 0:
                change_ratio = recent_count / baseline_count
                if change_ratio > TRENDING_THRESHOLDS['volume_spike']:
                    volume_changes[entity] = change_ratio
        
        return volume_changes
    
    def _detect_sentiment_shifts_internal(self) -> Dict[str, float]:
        """Detect sentiment shifts by entity."""
        sentiment_changes = {}
        
        for entity, history in self.sentiment_history.items():
            if len(history) < 20:
                continue
            
            # Recent vs baseline sentiment
            recent_scores = [h['score'] for h in history[-10:]]
            baseline_scores = [h['score'] for h in history[-30:-10]]
            
            if recent_scores and baseline_scores:
                recent_avg = np.mean(recent_scores)
                baseline_avg = np.mean(baseline_scores)
                
                change = recent_avg - baseline_avg
                if abs(change) > TRENDING_THRESHOLDS['sentiment_shift']:
                    sentiment_changes[entity] = change
        
        return sentiment_changes
    
    def _create_default_market_sentiment(self) -> MarketSentiment:
        """Create default market sentiment when analysis fails."""
        return MarketSentiment(
            timestamp=datetime.now(),
            overall_category=SentimentCategory.NEUTRAL,
            composite_score=0.0,
            fear_greed_index=50.0,
            put_call_ratio=None,
            vix_correlation=None,
            top_bullish=[],
            top_bearish=[],
            trending_topics=[],
            anomalies=[],
            ai_analysis={'error': 'Analysis failed'}
        )
    
    def _create_empty_sentiment_summary(self, entity: str,
                                      entity_type: EntityType) -> SentimentSummary:
        """Create empty sentiment summary."""
        return SentimentSummary(
            entity=entity,
            entity_type=entity_type,
            overall_sentiment=SentimentCategory.NEUTRAL,
            sentiment_score=0.0,
            volume=0,
            trend='stable',
            momentum=0.0,
            sources={},
            key_themes=[],
            ai_insights={'message': 'No data available'}
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sentiment_analysis_agent(model_name: str = DEFAULT_MODEL,
                                  temperature: float = DEFAULT_TEMPERATURE) -> SpyderX11_SentimentAnalysisAgent:
    """
    Factory function to create Sentiment Analysis Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX11_SentimentAnalysisAgent instance
    """
    return SpyderX11_SentimentAnalysisAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX11_SentimentAnalysisAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_sentiment_analysis_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_sentiment_agent():
    """Test the Sentiment Analysis Agent functionality."""
    print("="*80)
    print("Testing SpyderX11_SentimentAnalysisAgent")
    print("="*80)
    
    agent = create_sentiment_analysis_agent()
    
    # Create sample sentiment data
    sample_data = [
        SentimentData(
            source=SentimentSource.REDDIT,
            timestamp=datetime.now() - timedelta(minutes=30),
            content="SPY calls looking good! Bullish on the market rally",
            author="user123",
            sentiment_score=0.8,
            confidence=0.9,
            entities=["SPY"]
        ),
        SentimentData(
            source=SentimentSource.TWITTER,
            timestamp=datetime.now() - timedelta(minutes=25),
            content="Market crash incoming! Loading up on SPY puts",
            author="trader456",
            sentiment_score=-0.7,
            confidence=0.8,
            entities=["SPY"]
        ),
        SentimentData(
            source=SentimentSource.NEWS,
            timestamp=datetime.now() - timedelta(minutes=20),
            content="Fed signals potential rate cuts, markets respond positively",
            author="FinanceNews",
            sentiment_score=0.5,
            confidence=0.95,
            entities=["SPY", "FED"]
        ),
        SentimentData(
            source=SentimentSource.OPTIONS_FLOW,
            timestamp=datetime.now() - timedelta(minutes=15),
            content="Unusual call volume detected on SPY 460 strikes",
            author="FlowTracker",
            sentiment_score=0.6,
            confidence=0.85,
            entities=["SPY"]
        ),
        SentimentData(
            source=SentimentSource.ANALYST,
            timestamp=datetime.now() - timedelta(minutes=10),
            content="Upgrade SPY target to 470, maintain bullish outlook",
            author="GoldmanAnalyst",
            sentiment_score=0.9,
            confidence=0.95,
            entities=["SPY"]
        )
    ]
    
    # Add more sample data for variety
    for i in range(20):
        sentiment = 0.3 * np.sin(i/5) + np.random.normal(0, 0.2)
        sample_data.append(SentimentData(
            source=np.random.choice(list(SentimentSource)),
            timestamp=datetime.now() - timedelta(minutes=60-i*2),
            content=f"Sample mention {i} about SPY and market conditions",
            author=f"user{i}",
            sentiment_score=max(-1, min(1, sentiment)),
            confidence=0.7 + np.random.random() * 0.3,
            entities=["SPY"] + (["AAPL"] if i % 3 == 0 else [])
        ))
    
    # Test 1: Overall Market Sentiment
    print("\nTest 1: Market Sentiment Analysis")
    print("-"*40)
    
    market_sentiment = await agent.analyze_sentiment(sample_data)
    
    print(f"Overall Sentiment: {market_sentiment.overall_category.value}")
    print(f"Composite Score: {market_sentiment.composite_score:+.2f}")
    print(f"Fear/Greed Index: {market_sentiment.fear_greed_index:.0f}/100")
    
    print(f"\nTop Bullish Entities:")
    for entity, score in market_sentiment.top_bullish[:3]:
        print(f"  {entity}: {score:+.2f}")
    
    print(f"\nTop Bearish Entities:")
    for entity, score in market_sentiment.top_bearish[:3]:
        print(f"  {entity}: {score:+.2f}")
    
    print(f"\nTrending Topics:")
    for topic in market_sentiment.trending_topics[:3]:
        print(f"  - {topic['topic']}: Score {topic['trend_score']:.2f}")
    
    # Test 2: Entity Sentiment Analysis
    print("\n\nTest 2: Entity Sentiment Analysis (SPY)")
    print("-"*40)
    
    spy_sentiment = await agent.analyze_entity_sentiment("SPY")
    
    print(f"Entity: {spy_sentiment.entity}")
    print(f"Sentiment: {spy_sentiment.overall_sentiment.value}")
    print(f"Score: {spy_sentiment.sentiment_score:+.2f}")
    print(f"Volume: {spy_sentiment.volume} mentions")
    print(f"Trend: {spy_sentiment.trend}")
    print(f"Momentum: {spy_sentiment.momentum:+.2f}")
    
    print(f"\nSource Distribution:")
    for source, count in list(spy_sentiment.sources.items())[:3]:
        print(f"  {source}: {count}")
    
    print(f"\nKey Themes:")
    for theme in spy_sentiment.key_themes[:3]:
        print(f"  - {theme}")
    
    # Test 3: Sentiment Shift Detection
    print("\n\nTest 3: Sentiment Shift Detection")
    print("-"*40)
    
    # Add some dramatic shifts
    shift_data = []
    for i in range(10):
        # Create a sentiment reversal pattern
        if i < 5:
            sentiment = -0.6 + np.random.normal(0, 0.1)
        else:
            sentiment = 0.7 + np.random.normal(0, 0.1)
            
        shift_data.append(SentimentData(
            source=SentimentSource.TWITTER,
            timestamp=datetime.now() - timedelta(minutes=30-i*3),
            content=f"SPY sentiment shift test {i}",
            author=f"shifter{i}",
            sentiment_score=sentiment,
            confidence=0.8,
            entities=["TEST_ENTITY"]
        ))
    
    # Process shift data
    await agent.analyze_sentiment(shift_data)
    
    # Detect shifts
    alerts = await agent.detect_sentiment_shifts(lookback_minutes=60)
    
    print(f"Detected {len(alerts)} sentiment alerts:")
    for alert in alerts[:3]:
        print(f"\n[{alert.severity.upper()}] {alert.alert_type}: {alert.entity}")
        print(f"  {alert.description}")
        if alert.recommended_action:
            print(f"  Recommendation: {alert.recommended_action}")
    
    # Test 4: AI Analysis Quality
    print("\n\nTest 4: AI Analysis Quality")
    print("-"*40)
    
    if market_sentiment.ai_analysis:
        print("AI Market Analysis:")
        for key, value in list(market_sentiment.ai_analysis.items())[:3]:
            print(f"  {key}: {value}")
    
    if spy_sentiment.ai_insights:
        print("\nAI Entity Insights:")
        for key, value in list(spy_sentiment.ai_insights.items())[:3]:
            print(f"  {key}: {value}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_sentiment_agent())
    
    print("\n" + "="*80)
    print("SpyderX11_SentimentAnalysisAgent module loaded successfully!")
    print("="*80)