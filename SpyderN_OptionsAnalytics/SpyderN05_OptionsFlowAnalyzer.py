#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN05_OptionsFlowAnalyzer.py
Group: N (Options Analytics)
Purpose: Options flow analysis for institutional activity and sentiment

Description:
This module analyzes options flow for institutional activity,
    dark pool detection, and sentiment integration. It tracks large trades,
    unusual activity patterns, and integrates multiple sentiment sources
    to provide real-time flow analysis for trading decisions.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict, deque
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import asyncio
import logging
import re
    import asyncio

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class FlowType(Enum):
    """Types of options flow."""
    SWEEP = "SWEEP"              # Multi-exchange sweep
    BLOCK = "BLOCK"              # Large block trade
    SPLIT = "SPLIT"              # Split across exchanges
    UNUSUAL = "UNUSUAL"          # Unusual size/price
    REPEAT = "REPEAT"            # Repeated similar trades
    INSTITUTIONAL = "INSTITUTIONAL"  # Likely institutional
class SentimentSource(Enum):
    """Sources of sentiment data."""
    NEWS = "NEWS"
    TWITTER = "TWITTER"
    REDDIT = "REDDIT"
    STOCKTWITS = "STOCKTWITS"
    BENZINGA = "BENZINGA"
    BLOOMBERG = "BLOOMBERG"
@dataclass
class OptionsFlow:
    """Individual options flow trade."""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    side: str  # 'BUY' or 'SELL'
    quantity: int
    price: float
    underlying_price: float
    implied_volatility: float
    delta: float
    flow_type: FlowType
    exchanges: List[str]
    is_sweep: bool
    is_unusual: bool
    sentiment_score: float
@dataclass
class FlowCluster:
    """Cluster of related options flows."""
    cluster_id: str
    flows: List[OptionsFlow]
    total_volume: int
    total_premium: float
    dominant_side: str
    dominant_sentiment: float
    time_span: timedelta
    strategy_type: Optional[str]  # Detected strategy
    confidence: float
@dataclass
class InstitutionalFootprint:
    """Institutional trading pattern."""
    institution_id: str
    detection_confidence: float
    historical_patterns: List[str]
    position_changes: Dict[str, float]
    filing_correlation: float  # Correlation with 13F filings
    typical_strategies: List[str]
class SpyderOptionsFlowAnalyzer:
    """
    Analyzes options flow for institutional activity and sentiment.
    Features:
    - Real-time flow analysis and clustering
    - Dark pool detection algorithms
    - Institutional footprint tracking
    - Multi-source sentiment integration
    - Unusual activity alerts
    """
    def __init__(self, market_data=None, sentiment_api=None):
        """Initialize options flow analyzer."""
        self.market_data = market_data
        self.sentiment_api = sentiment_api
        # Flow detection parameters
        self.FLOW_THRESHOLDS = {
            'unusual_size': 500,          # Contracts
            'unusual_premium': 50000,     # Dollars
            'sweep_time_window': 5,       # Seconds
            'sweep_min_exchanges': 3,     # Minimum exchanges
            'block_size': 1000,           # Contracts
            'institution_size': 100000,   # Dollar premium
            'repeat_window': 300,         # 5 minutes
            'cluster_time_window': 600    # 10 minutes
        }
        # Dark pool indicators
        self.DARK_POOL_INDICATORS = {
            'off_exchange_ratio': 0.4,    # >40% off-exchange
            'price_improvement': 0.001,   # Better than NBBO
            'odd_lot_ratio': 0.3,         # High odd lots
            'time_clustering': 60,        # Trades within 60 seconds
            'size_consistency': 0.8       # Similar sizes
        }
        # Sentiment weights
        self.SENTIMENT_WEIGHTS = {
            SentimentSource.NEWS: 0.35,
            SentimentSource.BLOOMBERG: 0.25,
            SentimentSource.TWITTER: 0.15,
            SentimentSource.REDDIT: 0.10,
            SentimentSource.STOCKTWITS: 0.10,
            SentimentSource.BENZINGA: 0.05
        }
        # Pattern detection
        self.STRATEGY_PATTERNS = {
            'call_sweep': {
                'min_trades': 5,
                'side': 'BUY',
                'type': 'call',
                'time_window': 300
            },
            'put_wall': {
                'min_volume': 5000,
                'side': 'SELL',
                'type': 'put',
                'strike_range': 5
            },
            'collar': {
                'components': ['buy_put', 'sell_call'],
                'time_window': 60,
                'delta_range': 0.2
            },
            'risk_reversal': {
                'components': ['sell_put', 'buy_call'],
                'strike_relationship': 'symmetric',
                'time_window': 120
            }
        }
        # State tracking
        self.flow_buffer = deque(maxlen=10000)  # Recent flows
        self.flow_clusters = {}
        self.institutional_footprints = {}
        self.sentiment_cache = {}
        self.alert_history = []
        # Performance metrics
        self.analysis_times = deque(maxlen=1000)
        self.detection_accuracy = {'correct': 0, 'total': 0}
    async def analyze_flow(self, trade_data: Dict[str, Any]) -> OptionsFlow:
        """
        Analyze individual options trade for flow characteristics.
        Args:
            trade_data: Raw trade data
        Returns:
            Analyzed options flow
        """
        start_time = datetime.now()
        # Extract basic information
        flow = OptionsFlow(
            timestamp=trade_data['timestamp'],
            symbol=trade_data['symbol'],
            strike=trade_data['strike'],
            expiry=trade_data['expiry'],
            option_type=trade_data['option_type'],
            side=self._determine_trade_side(trade_data),
            quantity=trade_data['quantity'],
            price=trade_data['price'],
            underlying_price=trade_data['underlying_price'],
            implied_volatility=trade_data.get('iv', 0),
            delta=trade_data.get('delta', 0),
            flow_type=FlowType.BLOCK,  # Default, will update
            exchanges=trade_data.get('exchanges', []),
            is_sweep=False,
            is_unusual=False,
            sentiment_score=0
        )
        # Detect flow type
        flow.flow_type = await self._detect_flow_type(flow, trade_data)
        # Check for sweep
        flow.is_sweep = await self._is_sweep_order(flow)
        # Check for unusual activity
        flow.is_unusual = self._is_unusual_activity(flow)
        # Get sentiment score
        flow.sentiment_score = await self._calculate_sentiment_score(
            flow.symbol, flow.timestamp
        )
        # Add to buffer
        self.flow_buffer.append(flow)
        # Track analysis time
        analysis_time = (datetime.now() - start_time).total_seconds() * 1000
        self.analysis_times.append(analysis_time)
        # Generate alerts if needed
        if flow.is_unusual or flow.is_sweep:
            await self._generate_alert(flow)
        return flow
    async def detect_clusters(self, 
                            time_window: Optional[int] = None) -> List[FlowCluster]:
        """
        Detect clusters of related options activity.
        Args:
            time_window: Analysis window in seconds
        Returns:
            List of detected flow clusters
        """
        if time_window is None:
            time_window = self.FLOW_THRESHOLDS['cluster_time_window']
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=time_window)
        # Get recent flows
        recent_flows = [f for f in self.flow_buffer 
                       if f.timestamp >= cutoff_time]
        # Group by symbol and strategy indicators
        clusters = defaultdict(list)
        for flow in recent_flows:
            # Create cluster key
            key = self._create_cluster_key(flow)
            clusters[key].append(flow)
        # Analyze each cluster
        flow_clusters = []
        for key, flows in clusters.items():
            if len(flows) >= 3:  # Minimum cluster size
                cluster = self._analyze_cluster(flows)
                if cluster.confidence > 0.7:
                    flow_clusters.append(cluster)
        # Detect multi-leg strategies
        strategy_clusters = await self._detect_strategy_clusters(recent_flows)
        flow_clusters.extend(strategy_clusters)
        # Sort by significance
        flow_clusters.sort(key=lambda x: x.total_premium, reverse=True)
        return flow_clusters
    async def detect_institutional_activity(self, 
                                          flows: List[OptionsFlow]) -> List[InstitutionalFootprint]:
        """
        Detect potential institutional trading patterns.
        Args:
            flows: Recent options flows
        Returns:
            List of institutional footprints
        """
        footprints = []
        # Group flows by potential institution patterns
        pattern_groups = defaultdict(list)
        for flow in flows:
            # Check size thresholds
            premium = flow.quantity * flow.price * 100
            if premium < self.FLOW_THRESHOLDS['institution_size']:
                continue
            # Extract pattern features
            features = self._extract_institutional_features(flow)
            pattern_key = self._create_pattern_key(features)
            pattern_groups[pattern_key].append(flow)
        # Analyze each pattern group
        for pattern_key, group_flows in pattern_groups.items():
            if len(group_flows) >= 5:  # Minimum pattern size
                footprint = await self._analyze_institutional_pattern(
                    pattern_key, group_flows
                )
                if footprint.detection_confidence > 0.8:
                    footprints.append(footprint)
        # Correlate with known institutional patterns
        for footprint in footprints:
            footprint.filing_correlation = await self._correlate_with_filings(
                footprint
            )
        return footprints
    async def analyze_dark_pool_activity(self, 
                                       trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze potential dark pool activity.
        Args:
            trades: Recent trade data
        Returns:
            Dark pool analysis results
        """
        dark_pool_indicators = {
            'detected_trades': [],
            'total_volume': 0,
            'average_size': 0,
            'price_improvement': 0,
            'confidence_scores': []
        }
        for trade in trades:
            confidence = self._calculate_dark_pool_confidence(trade)
            if confidence > 0.7:
                dark_pool_indicators['detected_trades'].append({
                    'timestamp': trade['timestamp'],
                    'size': trade['quantity'],
                    'price': trade['price'],
                    'confidence': confidence
                })
                dark_pool_indicators['total_volume'] += trade['quantity']
                dark_pool_indicators['confidence_scores'].append(confidence)
        # Calculate aggregates
        if dark_pool_indicators['detected_trades']:
            dark_pool_indicators['average_size'] = (
                dark_pool_indicators['total_volume'] / 
                len(dark_pool_indicators['detected_trades'])
            )
        return dark_pool_indicators
    def _determine_trade_side(self, trade_data: Dict[str, Any]) -> str:
        """Determine if trade is buy or sell."""
        # Multiple methods to determine side
        # Method 1: Explicit side
        if 'side' in trade_data:
            return trade_data['side']
        # Method 2: Trade price vs bid/ask
        if 'bid' in trade_data and 'ask' in trade_data:
            price = trade_data['price']
            mid = (trade_data['bid'] + trade_data['ask']) / 2
            if price > mid:
                return 'BUY'
            else:
                return 'SELL'
        # Method 3: Trade condition codes
        if 'condition' in trade_data:
            buy_codes = ['B', 'E', 'F']  # Buy-side indicators
            if any(code in trade_data['condition'] for code in buy_codes):
                return 'BUY'
        # Default
        return 'BUY' if trade_data.get('delta', 0) > 0 else 'SELL'
    async def _detect_flow_type(self, flow: OptionsFlow, 
                              raw_data: Dict[str, Any]) -> FlowType:
        """Detect the type of options flow."""
        # Check for sweep characteristics
        if len(flow.exchanges) >= self.FLOW_THRESHOLDS['sweep_min_exchanges']:
            # Multi-exchange execution
            time_spread = raw_data.get('execution_time_spread', 0)
            if time_spread < self.FLOW_THRESHOLDS['sweep_time_window']:
                return FlowType.SWEEP
        # Check for block trade
        if flow.quantity >= self.FLOW_THRESHOLDS['block_size']:
            return FlowType.BLOCK
        # Check for split execution
        if self._is_split_execution(raw_data):
            return FlowType.SPLIT
        # Check for repeated pattern
        if await self._is_repeat_pattern(flow):
            return FlowType.REPEAT
        # Check for institutional size
        premium = flow.quantity * flow.price * 100
        if premium >= self.FLOW_THRESHOLDS['institution_size']:
            return FlowType.INSTITUTIONAL
        # Check for unusual characteristics
        if self._is_unusual_activity(flow):
            return FlowType.UNUSUAL
        return FlowType.BLOCK  # Default
    async def _is_sweep_order(self, flow: OptionsFlow) -> bool:
        """Determine if order is a sweep."""
        if flow.flow_type == FlowType.SWEEP:
            return True
        # Additional sweep detection
        recent_similar = [
            f for f in self.flow_buffer
            if (f.symbol == flow.symbol and
                f.strike == flow.strike and
                f.expiry == flow.expiry and
                f.option_type == flow.option_type and
                abs((f.timestamp - flow.timestamp).total_seconds()) < 
                self.FLOW_THRESHOLDS['sweep_time_window'])
        ]
        # Multiple fills across exchanges
        if len(recent_similar) >= 3:
            exchanges = set()
            for f in recent_similar:
                exchanges.update(f.exchanges)
            if len(exchanges) >= self.FLOW_THRESHOLDS['sweep_min_exchanges']:
                return True
        return False
    def _is_unusual_activity(self, flow: OptionsFlow) -> bool:
        """Check if flow represents unusual activity."""
        # Size-based unusual
        if flow.quantity >= self.FLOW_THRESHOLDS['unusual_size']:
            return True
        # Premium-based unusual
        premium = flow.quantity * flow.price * 100
        if premium >= self.FLOW_THRESHOLDS['unusual_premium']:
            return True
        # Out-of-money unusual activity
        moneyness = flow.underlying_price / flow.strike
        if flow.option_type == 'call':
            if moneyness < 0.95 and flow.quantity > 100:  # OTM calls
                return True
        else:
            if moneyness > 1.05 and flow.quantity > 100:  # OTM puts
                return True
        # High IV unusual activity
        if flow.implied_volatility > 0.5 and flow.quantity > 50:
            return True
        return False
    async def _calculate_sentiment_score(self, symbol: str, 
                                       timestamp: datetime) -> float:
        """Calculate sentiment score from multiple sources."""
        # Check cache
        cache_key = f"{symbol}_{timestamp.strftime('%Y%m%d%H')}"
        if cache_key in self.sentiment_cache:
            return self.sentiment_cache[cache_key]
        sentiment_scores = {}
        # Get sentiment from each source
        for source in SentimentSource:
            try:
                score = await self._get_sentiment_from_source(
                    symbol, timestamp, source
                )
                sentiment_scores[source] = score
            except Exception as e:
                logger.warning(f"Failed to get sentiment from {source}: {e}")
                sentiment_scores[source] = 0  # Neutral
        # Weighted average
        total_score = 0
        total_weight = 0
        for source, score in sentiment_scores.items():
            weight = self.SENTIMENT_WEIGHTS.get(source, 0.1)
            total_score += score * weight
            total_weight += weight
        final_score = total_score / total_weight if total_weight > 0 else 0
        # Cache result
        self.sentiment_cache[cache_key] = final_score
        return final_score
    async def _get_sentiment_from_source(self, symbol: str,
                                       timestamp: datetime,
                                       source: SentimentSource) -> float:
        """Get sentiment from specific source."""
        if not self.sentiment_api:
            # Simulate sentiment for demo
            if source == SentimentSource.NEWS:
                return np.random.uniform(-0.5, 0.5)
            elif source == SentimentSource.TWITTER:
                return np.random.uniform(-0.7, 0.7)
            else:
                return np.random.uniform(-0.3, 0.3)
        # Real API call would go here
        # sentiment = await self.sentiment_api.get_sentiment(symbol, source)
        # return sentiment
    def _create_cluster_key(self, flow: OptionsFlow) -> str:
        """Create key for clustering similar flows."""
        # Round strike to nearest 5
        strike_bucket = round(flow.strike / 5) * 5
        # Create key
        key_parts = [
            flow.symbol,
            flow.option_type,
            str(strike_bucket),
            flow.expiry.strftime('%Y%m%d'),
            flow.side
        ]
        return '_'.join(key_parts)
    def _analyze_cluster(self, flows: List[OptionsFlow]) -> FlowCluster:
        """Analyze a cluster of flows."""
        # Calculate aggregates
        total_volume = sum(f.quantity for f in flows)
        total_premium = sum(f.quantity * f.price * 100 for f in flows)
        # Determine dominant side
        buy_volume = sum(f.quantity for f in flows if f.side == 'BUY')
        sell_volume = sum(f.quantity for f in flows if f.side == 'SELL')
        dominant_side = 'BUY' if buy_volume > sell_volume else 'SELL'
        # Average sentiment
        avg_sentiment = np.mean([f.sentiment_score for f in flows])
        # Time span
        time_span = max(f.timestamp for f in flows) - min(f.timestamp for f in flows)
        # Detect strategy type
        strategy = self._detect_strategy_type(flows)
        # Calculate confidence
        confidence = self._calculate_cluster_confidence(flows)
        return FlowCluster(
            cluster_id=f"CLUSTER_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            flows=flows,
            total_volume=total_volume,
            total_premium=total_premium,
            dominant_side=dominant_side,
            dominant_sentiment=avg_sentiment,
            time_span=time_span,
            strategy_type=strategy,
            confidence=confidence
        )
    async def _detect_strategy_clusters(self, 
                                      flows: List[OptionsFlow]) -> List[FlowCluster]:
        """Detect multi-leg strategy clusters."""
        strategy_clusters = []
        # Look for common strategies
        for strategy_name, pattern in self.STRATEGY_PATTERNS.items():
            clusters = self._find_strategy_pattern(flows, pattern)
            strategy_clusters.extend(clusters)
        return strategy_clusters
    def _find_strategy_pattern(self, flows: List[OptionsFlow],
                             pattern: Dict[str, Any]) -> List[FlowCluster]:
        """Find specific strategy pattern in flows."""
        clusters = []
        # Implementation would depend on pattern type
        # Simplified for demo
        if 'components' in pattern:
            # Multi-leg strategy
            # Would implement sophisticated matching logic
            pass
        return clusters
    def _extract_institutional_features(self, flow: OptionsFlow) -> Dict[str, Any]:
        """Extract features indicating institutional trading."""
        features = {
            'size_bucket': self._get_size_bucket(flow.quantity),
            'time_bucket': flow.timestamp.hour,
            'strike_selection': 'round' if flow.strike % 5 == 0 else 'odd',
            'expiry_selection': self._get_expiry_pattern(flow.expiry),
            'execution_quality': self._assess_execution_quality(flow)
        }
        return features
    def _get_size_bucket(self, quantity: int) -> str:
        """Categorize trade size."""
        if quantity >= 5000:
            return 'mega'
        elif quantity >= 1000:
            return 'large'
        elif quantity >= 500:
            return 'medium'
        else:
            return 'small'
    def _get_expiry_pattern(self, expiry: datetime) -> str:
        """Identify expiry selection pattern."""
        days_to_expiry = (expiry - datetime.now()).days
        if days_to_expiry <= 1:
            return '0dte'
        elif days_to_expiry <= 7:
            return 'weekly'
        elif days_to_expiry <= 45:
            return 'monthly'
        else:
            return 'leap'
    def _assess_execution_quality(self, flow: OptionsFlow) -> str:
        """Assess execution quality."""
        # Simplified assessment
        if flow.flow_type == FlowType.SWEEP:
            return 'aggressive'
        elif flow.flow_type == FlowType.BLOCK:
            return 'patient'
        else:
            return 'normal'
    def _create_pattern_key(self, features: Dict[str, Any]) -> str:
        """Create key for pattern matching."""
        key_parts = [
            features['size_bucket'],
            str(features['time_bucket']),
            features['strike_selection'],
            features['execution_quality']
        ]
        return '_'.join(key_parts)
    async def _analyze_institutional_pattern(self, pattern_key: str,
                                           flows: List[OptionsFlow]) -> InstitutionalFootprint:
        """Analyze potential institutional pattern."""
        # Calculate position changes
        position_changes = defaultdict(float)
        for flow in flows:
            key = f"{flow.symbol}_{flow.strike}_{flow.expiry.strftime('%Y%m%d')}"
            if flow.side == 'BUY':
                position_changes[key] += flow.quantity
            else:
                position_changes[key] -= flow.quantity
        # Identify typical strategies
        strategies = self._identify_institutional_strategies(flows)
        # Calculate confidence
        confidence = self._calculate_institutional_confidence(flows)
        return InstitutionalFootprint(
            institution_id=f"INST_{pattern_key}",
            detection_confidence=confidence,
            historical_patterns=[pattern_key],
            position_changes=dict(position_changes),
            filing_correlation=0,  # Will be updated
            typical_strategies=strategies
        )
    def _identify_institutional_strategies(self, 
                                         flows: List[OptionsFlow]) -> List[str]:
        """Identify strategies used by institution."""
        strategies = set()
        # Look for common institutional strategies
        # Simplified detection
        # Check for hedging
        puts = [f for f in flows if f.option_type == 'put' and f.side == 'BUY']
        if len(puts) > len(flows) * 0.3:
            strategies.add('hedging')
        # Check for income generation
        calls = [f for f in flows if f.option_type == 'call' and f.side == 'SELL']
        if len(calls) > len(flows) * 0.3:
            strategies.add('covered_calls')
        # Check for volatility trading
        if any(abs(f.delta) < 0.3 for f in flows):
            strategies.add('volatility_trading')
        return list(strategies)
    def _calculate_institutional_confidence(self, flows: List[OptionsFlow]) -> float:
        """Calculate confidence in institutional detection."""
        confidence_factors = []
        # Size consistency
        sizes = [f.quantity for f in flows]
        size_cv = np.std(sizes) / np.mean(sizes) if np.mean(sizes) > 0 else 1
        confidence_factors.append(1 - min(size_cv, 1))
        # Timing consistency
        timestamps = [f.timestamp for f in flows]
        time_diffs = [(timestamps[i+1] - timestamps[i]).seconds 
                     for i in range(len(timestamps)-1)]
        if time_diffs:
            time_consistency = 1 - min(np.std(time_diffs) / np.mean(time_diffs), 1)
            confidence_factors.append(time_consistency)
        # Execution quality
        sweep_ratio = sum(1 for f in flows if f.is_sweep) / len(flows)
        confidence_factors.append(sweep_ratio)
        return np.mean(confidence_factors)
    async def _correlate_with_filings(self, 
                                    footprint: InstitutionalFootprint) -> float:
        """Correlate pattern with 13F filings."""
        # In production, would query 13F database
        # Simplified correlation score
        # Check if position changes align with known institutional holdings
        correlation_score = 0.5  # Placeholder
        # Boost score for known patterns
        if 'hedging' in footprint.typical_strategies:
            correlation_score += 0.2
        return min(correlation_score, 1.0)
    def _calculate_dark_pool_confidence(self, trade: Dict[str, Any]) -> float:
        """Calculate confidence that trade is from dark pool."""
        confidence_scores = []
        # Check off-exchange indicator
        if trade.get('off_exchange', False):
            confidence_scores.append(0.9)
        elif trade.get('exchange') in ['NONE', 'TRF', 'ADF']:
            confidence_scores.append(0.7)
        # Check for price improvement
        if 'nbbo_mid' in trade:
            improvement = abs(trade['price'] - trade['nbbo_mid']) / trade['nbbo_mid']
            if improvement > self.DARK_POOL_INDICATORS['price_improvement']:
                confidence_scores.append(0.8)
        # Check odd lot
        if trade['quantity'] % 100 != 0:
            confidence_scores.append(0.6)
        # Check timing (often clustered)
        if self._is_time_clustered(trade):
            confidence_scores.append(0.7)
        return np.mean(confidence_scores) if confidence_scores else 0
    def _is_time_clustered(self, trade: Dict[str, Any]) -> bool:
        """Check if trade is time-clustered with similar trades."""
        trade_time = trade['timestamp']
        similar_trades = [
            t for t in self.flow_buffer
            if (t.symbol == trade['symbol'] and
                abs((t.timestamp - trade_time).total_seconds()) < 
                self.DARK_POOL_INDICATORS['time_clustering'])
        ]
        return len(similar_trades) >= 3
    def _is_split_execution(self, raw_data: Dict[str, Any]) -> bool:
        """Check if trade appears to be split execution."""
        # Look for indicators of split execution
        if 'execution_id' in raw_data:
            # Same execution ID across multiple fills
            return True
        # Check for rapid sequential fills
        if 'fill_sequence' in raw_data and raw_data['fill_sequence'] > 1:
            return True
        return False
    async def _is_repeat_pattern(self, flow: OptionsFlow) -> bool:
        """Check if flow is part of repeat pattern."""
        lookback_window = datetime.now() - timedelta(
            seconds=self.FLOW_THRESHOLDS['repeat_window']
        )
        similar_flows = [
            f for f in self.flow_buffer
            if (f.symbol == flow.symbol and
                f.strike == flow.strike and
                f.option_type == flow.option_type and
                f.side == flow.side and
                f.timestamp >= lookback_window)
        ]
        return len(similar_flows) >= 3
    async def _generate_alert(self, flow: OptionsFlow):
        """Generate alert for unusual activity."""
        alert = {
            'timestamp': datetime.now(),
            'flow_id': id(flow),
            'type': 'unusual_options_activity',
            'symbol': flow.symbol,
            'description': self._create_alert_description(flow),
            'urgency': self._calculate_alert_urgency(flow),
            'flow_details': {
                'strike': flow.strike,
                'expiry': flow.expiry,
                'type': flow.option_type,
                'side': flow.side,
                'quantity': flow.quantity,
                'premium': flow.quantity * flow.price * 100
            }
        }
        self.alert_history.append(alert)
        # In production, would send to alert system
        logger.info(f"ALERT: {alert['description']}")
    def _create_alert_description(self, flow: OptionsFlow) -> str:
        """Create human-readable alert description."""
        premium = flow.quantity * flow.price * 100
        parts = []
        if flow.is_sweep:
            parts.append("SWEEP DETECTED")
        parts.extend([
            f"{flow.side}",
            f"{flow.quantity:,}",
            f"{flow.symbol}",
            f"${flow.strike}",
            flow.option_type.upper(),
            f"exp {flow.expiry.strftime('%m/%d')}",
            f"for ${premium:,.0f}"
        ])
        if flow.sentiment_score > 0.5:
            parts.append("(BULLISH SENTIMENT)")
        elif flow.sentiment_score < -0.5:
            parts.append("(BEARISH SENTIMENT)")
        return " ".join(parts)
    def _calculate_alert_urgency(self, flow: OptionsFlow) -> str:
        """Calculate urgency level of alert."""
        premium = flow.quantity * flow.price * 100
        if premium > 1000000 or flow.quantity > 5000:
            return 'CRITICAL'
        elif premium > 500000 or flow.quantity > 2000:
            return 'HIGH'
        elif flow.is_sweep or flow.is_unusual:
            return 'MEDIUM'
        else:
            return 'LOW'
    def _detect_strategy_type(self, flows: List[OptionsFlow]) -> Optional[str]:
        """Detect the type of options strategy from flows."""
        if len(flows) < 2:
            return None
        # Simple strategy detection
        strikes = set(f.strike for f in flows)
        types = set(f.option_type for f in flows)
        sides = set(f.side for f in flows)
        # Straddle/Strangle
        if len(types) == 2 and len(sides) == 1:
            if len(strikes) == 1:
                return 'straddle'
            elif len(strikes) == 2:
                return 'strangle'
        # Spread
        if len(types) == 1 and len(sides) == 2:
            if len(strikes) == 2:
                return 'vertical_spread'
        # Butterfly/Condor
        if len(strikes) >= 3:
            if len(strikes) == 3:
                return 'butterfly'
            elif len(strikes) == 4:
                return 'condor'
        return 'complex'
    def _calculate_cluster_confidence(self, flows: List[OptionsFlow]) -> float:
        """Calculate confidence in cluster detection."""
        factors = []
        # Size factor
        total_volume = sum(f.quantity for f in flows)
        size_score = min(total_volume / 1000, 1.0)
        factors.append(size_score)
        # Consistency factor
        sides = set(f.side for f in flows)
        consistency_score = 1.0 if len(sides) == 1 else 0.5
        factors.append(consistency_score)
        # Time clustering
        timestamps = [f.timestamp for f in flows]
        time_range = (max(timestamps) - min(timestamps)).seconds
        time_score = 1.0 - min(time_range / 600, 1.0)  # Tighter = better
        factors.append(time_score)
        return np.mean(factors)
    def get_flow_summary(self, time_window: int = 3600) -> Dict[str, Any]:
        """Get summary of recent flow activity."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(seconds=time_window)
        recent_flows = [f for f in self.flow_buffer if f.timestamp >= cutoff_time]
        if not recent_flows:
            return {'no_data': True}
        # Calculate aggregates
        total_volume = sum(f.quantity for f in recent_flows)
        total_premium = sum(f.quantity * f.price * 100 for f in recent_flows)
        # Sentiment analysis
        bullish_flows = [f for f in recent_flows 
                        if f.side == 'BUY' and f.option_type == 'call']
        bearish_flows = [f for f in recent_flows 
                        if f.side == 'BUY' and f.option_type == 'put']
        # Unusual activity
        unusual_flows = [f for f in recent_flows if f.is_unusual]
        sweep_flows = [f for f in recent_flows if f.is_sweep]
        summary = {
            'time_window': time_window,
            'total_flows': len(recent_flows),
            'total_volume': total_volume,
            'total_premium': total_premium,
            'average_size': total_volume / len(recent_flows),
            'bullish_volume': sum(f.quantity for f in bullish_flows),
            'bearish_volume': sum(f.quantity for f in bearish_flows),
            'put_call_ratio': len(bearish_flows) / len(bullish_flows) if bullish_flows else 0,
            'unusual_count': len(unusual_flows),
            'sweep_count': len(sweep_flows),
            'avg_sentiment': np.mean([f.sentiment_score for f in recent_flows]),
            'top_symbols': self._get_top_symbols(recent_flows, 5),
            'institutional_confidence': self._calculate_institutional_presence(recent_flows)
        }
        return summary
    def _get_top_symbols(self, flows: List[OptionsFlow], n: int = 5) -> List[Dict]:
        """Get top symbols by activity."""
        symbol_stats = defaultdict(lambda: {'volume': 0, 'premium': 0, 'count': 0})
        for flow in flows:
            stats = symbol_stats[flow.symbol]
            stats['volume'] += flow.quantity
            stats['premium'] += flow.quantity * flow.price * 100
            stats['count'] += 1
        # Sort by premium
        sorted_symbols = sorted(
            symbol_stats.items(),
            key=lambda x: x[1]['premium'],
            reverse=True
        )
        return [
            {
                'symbol': symbol,
                'volume': stats['volume'],
                'premium': stats['premium'],
                'trades': stats['count']
            }
            for symbol, stats in sorted_symbols[:n]
        ]
    def _calculate_institutional_presence(self, flows: List[OptionsFlow]) -> float:
        """Calculate likelihood of institutional presence."""
        if not flows:
            return 0
        institutional_indicators = []
        # Large trades ratio
        large_trades = [f for f in flows 
                       if f.quantity * f.price * 100 > self.FLOW_THRESHOLDS['institution_size']]
        institutional_indicators.append(len(large_trades) / len(flows))
        # Sweep ratio
        sweep_ratio = sum(1 for f in flows if f.is_sweep) / len(flows)
        institutional_indicators.append(sweep_ratio)
        # Execution quality
        block_ratio = sum(1 for f in flows if f.flow_type == FlowType.BLOCK) / len(flows)
        institutional_indicators.append(block_ratio)
        return np.mean(institutional_indicators)
async def main():
    """Example usage of options flow analyzer."""
    analyzer = SpyderOptionsFlowAnalyzer()
    # Simulate options flow data
    print("=== Options Flow Analysis ===")
    # Generate sample flows
    sample_flows = []
    # Unusual large call sweep
    for i in range(5):
        trade = {
            'timestamp': datetime.now() - timedelta(seconds=i),
            'symbol': 'SPY',
            'strike': 455,
            'expiry': datetime.now() + timedelta(days=7),
            'option_type': 'call',
            'quantity': 2000,
            'price': 2.50,
            'underlying_price': 450,
            'iv': 0.25,
            'delta': 0.45,
            'exchanges': ['CBOE', 'ISE', 'PHLX'],
            'bid': 2.48,
            'ask': 2.52
        }
        flow = await analyzer.analyze_flow(trade)
        sample_flows.append(flow)
        print(f"\nFlow {i+1}:")
        print(f"  Type: {flow.flow_type.value}")
        print(f"  Side: {flow.side}")
        print(f"  Size: {flow.quantity:,} contracts")
        print(f"  Premium: ${flow.quantity * flow.price * 100:,.0f}")
        print(f"  Is Sweep: {flow.is_sweep}")
        print(f"  Is Unusual: {flow.is_unusual}")
        print(f"  Sentiment: {flow.sentiment_score:.2f}")
    # Add some put activity
    for i in range(3):
        trade = {
            'timestamp': datetime.now() - timedelta(seconds=10+i),
            'symbol': 'SPY',
            'strike': 445,
            'expiry': datetime.now() + timedelta(days=7),
            'option_type': 'put',
            'quantity': 500,
            'price': 1.80,
            'underlying_price': 450,
            'iv': 0.22,
            'delta': -0.30,
            'exchanges': ['NASDAQ'],
            'bid': 1.78,
            'ask': 1.82
        }
        flow = await analyzer.analyze_flow(trade)
        sample_flows.append(flow)
    # Detect clusters
    print("\n=== Cluster Detection ===")
    clusters = await analyzer.detect_clusters()
    for cluster in clusters:
        print(f"\nCluster {cluster.cluster_id}:")
        print(f"  Total Volume: {cluster.total_volume:,}")
        print(f"  Total Premium: ${cluster.total_premium:,.0f}")
        print(f"  Dominant Side: {cluster.dominant_side}")
        print(f"  Strategy Type: {cluster.strategy_type}")
        print(f"  Confidence: {cluster.confidence:.2f}")
    # Detect institutional activity
    print("\n=== Institutional Detection ===")
    footprints = await analyzer.detect_institutional_activity(sample_flows)
    for footprint in footprints:
        print(f"\nInstitutional Pattern {footprint.institution_id}:")
        print(f"  Confidence: {footprint.detection_confidence:.2f}")
        print(f"  Strategies: {', '.join(footprint.typical_strategies)}")
        print(f"  13F Correlation: {footprint.filing_correlation:.2f}")
    # Analyze dark pool activity
    print("\n=== Dark Pool Analysis ===")
    # Simulate some dark pool trades
    dark_trades = [
        {
            'timestamp': datetime.now(),
            'symbol': 'SPY',
            'quantity': 50000,
            'price': 450.05,
            'off_exchange': True,
            'exchange': 'TRF',
            'nbbo_mid': 450.00
        }
    ]
    dark_analysis = await analyzer.analyze_dark_pool_activity(dark_trades)
    print(f"Detected Dark Pool Trades: {len(dark_analysis['detected_trades'])}")
    print(f"Total Dark Volume: {dark_analysis['total_volume']:,}")
    print(f"Average Size: {dark_analysis['average_size']:,.0f}")
    # Get flow summary
    print("\n=== Flow Summary (Last Hour) ===")
    summary = analyzer.get_flow_summary(3600)
    if 'no_data' not in summary:
        print(f"Total Flows: {summary['total_flows']}")
        print(f"Total Volume: {summary['total_volume']:,}")
        print(f"Total Premium: ${summary['total_premium']:,.0f}")
        print(f"Put/Call Ratio: {summary['put_call_ratio']:.2f}")
        print(f"Unusual Count: {summary['unusual_count']}")
        print(f"Sweep Count: {summary['sweep_count']}")
        print(f"Average Sentiment: {summary['avg_sentiment']:.2f}")
        print(f"Institutional Presence: {summary['institutional_confidence']:.2%}")
        print("\nTop Symbols:")
        for symbol_data in summary['top_symbols']:
            print(f"  {symbol_data['symbol']}: "
                  f"${symbol_data['premium']:,.0f} ({symbol_data['trades']} trades)")
    # Performance metrics
    print("\n=== Performance Metrics ===")
    if analyzer.analysis_times:
        avg_time = np.mean(list(analyzer.analysis_times))
        print(f"Average Analysis Time: {avg_time:.1f} ms")
if __name__ == "__main__":
    asyncio.run(main())