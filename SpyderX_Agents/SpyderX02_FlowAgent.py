#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderX02_FlowAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Options Flow Analysis Agent

Description:
    This agent analyzes unusual options activity, volume spikes, and order flow
    to detect smart money movements and institutional positioning. It provides
    AI-powered interpretation of flow data, identifying potential opportunities
    and risks based on large trades, sweep orders, and unusual activity patterns.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 19:30
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import time
import numpy as np

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from functools import lru_cache

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities import SpyderLogger, get_logger

# ==============================================================================
# CONSTANTS
# ==============================================================================
# AI Model Configuration
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.7
MAX_TOKENS = 2048

# Flow Analysis Thresholds
UNUSUAL_VOLUME_MULTIPLIER = 2.5  # 2.5x average volume
LARGE_TRADE_THRESHOLD = 100  # contracts
SWEEP_TIME_WINDOW = 60  # seconds
BLOCK_TRADE_MIN = 500  # contracts

# Sentiment Indicators
BULLISH_INDICATORS = ['sweep', 'aggressive call buying', 'call walls']
BEARISH_INDICATORS = ['put buying', 'protective puts', 'put walls']

# ==============================================================================
# ENUMS
# ==============================================================================
class FlowType(Enum):
    """Types of options flow"""
    SWEEP = "sweep"
    BLOCK = "block"
    SPLIT = "split"
    REGULAR = "regular"
    UNUSUAL = "unusual"

class Sentiment(Enum):
    """Market sentiment from flow"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"

class FlowSignificance(Enum):
    """Significance of flow activity"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionsFlow:
    """Individual options flow data"""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    volume: int
    open_interest: int
    price: float
    bid_ask_spread: float
    trade_size: int
    exchange: str
    is_sweep: bool = False
    is_block: bool = False
    implied_volatility: float = 0.0
    delta: float = 0.0

@dataclass
class FlowAnalysis:
    """AI-enhanced flow analysis result"""
    flows: List[OptionsFlow]
    sentiment: Sentiment
    significance: FlowSignificance
    smart_money_detected: bool
    key_levels: List[float]  # Important strikes
    interpretation: str
    trade_ideas: List[str]
    risk_factors: List[str]
    confidence_score: float
    analysis_timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class AggregatedFlow:
    """Aggregated flow metrics"""
    total_volume: int
    call_volume: int
    put_volume: int
    put_call_ratio: float
    avg_trade_size: float
    large_trades_count: int
    sweep_count: int
    net_premium: float
    bullish_flow_score: float
    bearish_flow_score: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX02_FlowAgent:
    """
    AI-Enhanced Options Flow Analysis Agent.
    
    This agent provides intelligent analysis of options order flow to detect
    institutional activity and smart money movements.
    
    Attributes:
        logger: Module logger instance
        config: Agent configuration
        analysis_history: History of flow analyses
        
    Example:
        >>> agent = SpyderX02_FlowAgent()
        >>> analysis = await agent.analyze_flow(flow_data)
        >>> print(analysis.interpretation)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Flow Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = get_logger(__name__)
        self.config = config or self._get_default_config()
        
        # Initialize components
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        
        # Analysis tracking
        self.analysis_history: List[FlowAnalysis] = []
        self.performance_metrics = {
            'total_analyses': 0,
            'avg_response_time': 0,
            'smart_money_detected': 0
        }
        
        # Cache for repeated analyses
        self._analysis_cache = {}
        
        # Historical data for comparison
        self.historical_averages = {
            'daily_volume': 50000,
            'avg_trade_size': 25,
            'typical_spread': 0.05
        }
        
        self.logger.info(f"{self.__class__.__name__} initialized with model: {self.model_name}")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    
    async def analyze_flow(
        self,
        flows: List[OptionsFlow],
        market_context: Optional[Dict[str, Any]] = None
    ) -> FlowAnalysis:
        """
        Analyze options flow with AI enhancement.
        
        Args:
            flows: List of options flow data
            market_context: Optional market context
            
        Returns:
            AI-enhanced flow analysis
        """
        start_time = time.time()
        
        try:
            # Aggregate flow metrics
            aggregated = self._aggregate_flow(flows)
            
            # Detect unusual activity
            unusual_flows = self._detect_unusual_activity(flows)
            
            # Identify smart money
            smart_money_detected = self._detect_smart_money(flows, aggregated)
            
            # Find key levels
            key_levels = self._identify_key_levels(flows)
            
            # Determine sentiment
            sentiment = self._calculate_sentiment(aggregated, unusual_flows)
            
            # Calculate significance
            significance = self._calculate_significance(aggregated, unusual_flows)
            
            # Generate AI interpretation
            interpretation = await self._generate_interpretation(
                flows, aggregated, unusual_flows, smart_money_detected, market_context
            )
            
            # Generate trade ideas
            trade_ideas = await self._generate_trade_ideas(
                sentiment, key_levels, unusual_flows, market_context
            )
            
            # Identify risk factors
            risk_factors = await self._identify_risk_factors(
                flows, aggregated, market_context
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                aggregated, unusual_flows, smart_money_detected
            )
            
            # Create analysis result
            analysis = FlowAnalysis(
                flows=flows,
                sentiment=sentiment,
                significance=significance,
                smart_money_detected=smart_money_detected,
                key_levels=key_levels,
                interpretation=interpretation,
                trade_ideas=trade_ideas,
                risk_factors=risk_factors,
                confidence_score=confidence_score
            )
            
            # Update history and metrics
            self.analysis_history.append(analysis)
            self._update_metrics(time.time() - start_time, smart_money_detected)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing flow: {str(e)}")
            raise
    
    async def analyze_sweep_activity(
        self,
        flows: List[OptionsFlow],
        time_window: int = SWEEP_TIME_WINDOW
    ) -> Dict[str, Any]:
        """
        Analyze sweep order activity.
        
        Args:
            flows: Flow data
            time_window: Time window for sweep detection
            
        Returns:
            Sweep analysis results
        """
        sweeps = [f for f in flows if f.is_sweep]
        
        if not sweeps:
            return {
                'sweep_count': 0,
                'interpretation': 'No sweep activity detected',
                'urgency': 'low'
            }
        
        # Group sweeps by strike and time
        sweep_clusters = self._cluster_sweeps(sweeps, time_window)
        
        # AI interpretation of sweep activity
        interpretation = await self._interpret_sweeps(sweep_clusters)
        
        return {
            'sweep_count': len(sweeps),
            'clusters': len(sweep_clusters),
            'total_volume': sum(s.volume for s in sweeps),
            'interpretation': interpretation,
            'urgency': 'high' if len(sweep_clusters) > 2 else 'medium'
        }
    
    async def detect_institutional_activity(
        self,
        flows: List[OptionsFlow]
    ) -> Dict[str, Any]:
        """
        Detect potential institutional activity.
        
        Args:
            flows: Flow data
            
        Returns:
            Institutional activity analysis
        """
        # Identify block trades
        block_trades = [f for f in flows if f.is_block or f.trade_size >= BLOCK_TRADE_MIN]
        
        # Look for patterns
        patterns = self._identify_institutional_patterns(flows)
        
        # AI interpretation
        interpretation = await self._interpret_institutional_activity(
            block_trades, patterns
        )
        
        return {
            'block_trades': len(block_trades),
            'total_block_volume': sum(b.volume for b in block_trades),
            'patterns_detected': patterns,
            'interpretation': interpretation,
            'confidence': 'high' if len(block_trades) > 3 else 'medium'
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Returns:
            Performance metrics dictionary
        """
        return self.performance_metrics.copy()
    
    # ==========================================================================
    # PRIVATE METHODS - FLOW ANALYSIS
    # ==========================================================================
    
    def _aggregate_flow(self, flows: List[OptionsFlow]) -> AggregatedFlow:
        """Aggregate flow metrics."""
        if not flows:
            return AggregatedFlow(
                total_volume=0, call_volume=0, put_volume=0,
                put_call_ratio=0, avg_trade_size=0, large_trades_count=0,
                sweep_count=0, net_premium=0, bullish_flow_score=0,
                bearish_flow_score=0
            )
        
        call_volume = sum(f.volume for f in flows if f.option_type == 'call')
        put_volume = sum(f.volume for f in flows if f.option_type == 'put')
        
        return AggregatedFlow(
            total_volume=sum(f.volume for f in flows),
            call_volume=call_volume,
            put_volume=put_volume,
            put_call_ratio=put_volume / max(call_volume, 1),
            avg_trade_size=np.mean([f.trade_size for f in flows]),
            large_trades_count=sum(1 for f in flows if f.trade_size >= LARGE_TRADE_THRESHOLD),
            sweep_count=sum(1 for f in flows if f.is_sweep),
            net_premium=sum(f.volume * f.price * 100 for f in flows),
            bullish_flow_score=self._calculate_bullish_score(flows),
            bearish_flow_score=self._calculate_bearish_score(flows)
        )
    
    def _detect_unusual_activity(self, flows: List[OptionsFlow]) -> List[OptionsFlow]:
        """Detect unusual flow activity."""
        unusual = []
        
        for flow in flows:
            # Check various unusual criteria
            if any([
                flow.volume > self.historical_averages['daily_volume'] * UNUSUAL_VOLUME_MULTIPLIER,
                flow.trade_size > self.historical_averages['avg_trade_size'] * 10,
                flow.is_sweep and flow.trade_size > LARGE_TRADE_THRESHOLD,
                flow.bid_ask_spread > self.historical_averages['typical_spread'] * 3
            ]):
                unusual.append(flow)
        
        return unusual
    
    def _detect_smart_money(self, flows: List[OptionsFlow], aggregated: AggregatedFlow) -> bool:
        """Detect potential smart money activity."""
        indicators = 0
        
        # Multiple sweep orders
        if aggregated.sweep_count >= 3:
            indicators += 1
        
        # Large block trades
        if aggregated.large_trades_count >= 2:
            indicators += 1
        
        # Unusual put/call ratio
        if aggregated.put_call_ratio > 2 or aggregated.put_call_ratio < 0.3:
            indicators += 1
        
        # High average trade size
        if aggregated.avg_trade_size > self.historical_averages['avg_trade_size'] * 5:
            indicators += 1
        
        return indicators >= 2
    
    def _identify_key_levels(self, flows: List[OptionsFlow]) -> List[float]:
        """Identify key strike levels from flow."""
        # Group by strike and sum volume
        strike_volume = {}
        for flow in flows:
            strike_volume[flow.strike] = strike_volume.get(flow.strike, 0) + flow.volume
        
        # Sort by volume and get top strikes
        sorted_strikes = sorted(strike_volume.items(), key=lambda x: x[1], reverse=True)
        
        # Return top 5 strikes
        return [strike for strike, _ in sorted_strikes[:5]]
    
    def _calculate_sentiment(self, aggregated: AggregatedFlow, unusual_flows: List[OptionsFlow]) -> Sentiment:
        """Calculate market sentiment from flow."""
        # Base sentiment on put/call ratio
        if aggregated.put_call_ratio < 0.5:
            base_sentiment = 2  # Bullish
        elif aggregated.put_call_ratio > 1.5:
            base_sentiment = -2  # Bearish
        else:
            base_sentiment = 0  # Neutral
        
        # Adjust for flow scores
        sentiment_score = base_sentiment + (aggregated.bullish_flow_score - aggregated.bearish_flow_score)
        
        # Map to sentiment enum
        if sentiment_score >= 3:
            return Sentiment.VERY_BULLISH
        elif sentiment_score >= 1:
            return Sentiment.BULLISH
        elif sentiment_score <= -3:
            return Sentiment.VERY_BEARISH
        elif sentiment_score <= -1:
            return Sentiment.BEARISH
        else:
            return Sentiment.NEUTRAL
    
    def _calculate_significance(self, aggregated: AggregatedFlow, unusual_flows: List[OptionsFlow]) -> FlowSignificance:
        """Calculate significance of flow activity."""
        if aggregated.sweep_count >= 5 or len(unusual_flows) >= 10:
            return FlowSignificance.HIGH
        elif aggregated.sweep_count >= 2 or len(unusual_flows) >= 5:
            return FlowSignificance.MEDIUM
        else:
            return FlowSignificance.LOW
    
    def _calculate_bullish_score(self, flows: List[OptionsFlow]) -> float:
        """Calculate bullish flow score."""
        score = 0.0
        
        for flow in flows:
            if flow.option_type == 'call':
                # Weight by size and aggressiveness
                weight = min(flow.trade_size / LARGE_TRADE_THRESHOLD, 2.0)
                if flow.is_sweep:
                    weight *= 1.5
                score += weight
        
        return score
    
    def _calculate_bearish_score(self, flows: List[OptionsFlow]) -> float:
        """Calculate bearish flow score."""
        score = 0.0
        
        for flow in flows:
            if flow.option_type == 'put':
                # Weight by size and aggressiveness
                weight = min(flow.trade_size / LARGE_TRADE_THRESHOLD, 2.0)
                if flow.is_sweep:
                    weight *= 1.5
                score += weight
        
        return score
    
    def _calculate_confidence_score(self, aggregated: AggregatedFlow, unusual_flows: List[OptionsFlow], smart_money: bool) -> float:
        """Calculate confidence score for analysis."""
        confidence = 0.7  # Base confidence
        
        # Increase for smart money detection
        if smart_money:
            confidence += 0.15
        
        # Increase for significant activity
        if aggregated.sweep_count >= 3:
            confidence += 0.1
        
        # Decrease for low volume
        if aggregated.total_volume < 1000:
            confidence -= 0.2
        
        return max(0.3, min(0.95, confidence))
    
    def _cluster_sweeps(self, sweeps: List[OptionsFlow], time_window: int) -> List[List[OptionsFlow]]:
        """Cluster sweep orders by time and strike."""
        if not sweeps:
            return []
        
        # Sort by timestamp
        sorted_sweeps = sorted(sweeps, key=lambda x: x.timestamp)
        
        clusters = []
        current_cluster = [sorted_sweeps[0]]
        
        for sweep in sorted_sweeps[1:]:
            # Check if within time window of last sweep in cluster
            time_diff = (sweep.timestamp - current_cluster[-1].timestamp).seconds
            
            if time_diff <= time_window and sweep.strike == current_cluster[0].strike:
                current_cluster.append(sweep)
            else:
                clusters.append(current_cluster)
                current_cluster = [sweep]
        
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def _identify_institutional_patterns(self, flows: List[OptionsFlow]) -> List[str]:
        """Identify institutional trading patterns."""
        patterns = []
        
        # Check for accumulation pattern
        strike_accumulation = {}
        for flow in flows:
            key = (flow.strike, flow.option_type)
            strike_accumulation[key] = strike_accumulation.get(key, 0) + flow.volume
        
        # Find strikes with heavy accumulation
        for (strike, opt_type), volume in strike_accumulation.items():
            if volume > self.historical_averages['daily_volume']:
                patterns.append(f"Heavy {opt_type} accumulation at ${strike}")
        
        # Check for spread trades
        # Simplified - would need more sophisticated logic in production
        if len(set(f.strike for f in flows)) >= 3:
            patterns.append("Possible spread positioning detected")
        
        return patterns
    
    # ==========================================================================
    # PRIVATE METHODS - AI GENERATION
    # ==========================================================================
    
    async def _generate_interpretation(
        self,
        flows: List[OptionsFlow],
        aggregated: AggregatedFlow,
        unusual_flows: List[OptionsFlow],
        smart_money_detected: bool,
        market_context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate AI interpretation of flow activity."""
        try:
            import ollama
            
            # Prepare flow summary
            flow_summary = f"""
Total Volume: {aggregated.total_volume:,}
Call Volume: {aggregated.call_volume:,} | Put Volume: {aggregated.put_volume:,}
Put/Call Ratio: {aggregated.put_call_ratio:.2f}
Large Trades: {aggregated.large_trades_count} | Sweeps: {aggregated.sweep_count}
Average Trade Size: {aggregated.avg_trade_size:.0f} contracts
Smart Money Detected: {'Yes' if smart_money_detected else 'No'}

Top 3 Unusual Flows:
"""
            for i, flow in enumerate(unusual_flows[:3], 1):
                flow_summary += f"{i}. {flow.option_type.upper()} ${flow.strike} - {flow.volume:,} volume, {flow.trade_size} size\n"
            
            if market_context:
                flow_summary += f"\nMarket Context: {market_context}"
            
            prompt = f"""You are an expert options flow analyst. Analyze this flow data and provide insights.

{flow_summary}

Provide a concise interpretation focusing on:
1. What the flow is telling us about market sentiment
2. Whether this represents institutional/smart money activity
3. Key levels to watch based on the flow
4. Potential near-term market direction

Keep it to 4-5 sentences with actionable insights."""

            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': 250,
                    'num_thread': 16
                }
            )
            
            return response['response']
            
        except Exception as e:
            self.logger.warning(f"Ollama not available, using fallback: {e}")
            # Fallback interpretation
            sentiment = "bullish" if aggregated.put_call_ratio < 0.7 else "bearish" if aggregated.put_call_ratio > 1.3 else "neutral"
            
            interpretation = f"Flow analysis shows {sentiment} sentiment with "
            interpretation += f"{aggregated.total_volume:,} total volume. "
            
            if smart_money_detected:
                interpretation += "Smart money activity detected through multiple sweeps and large trades. "
            
            if unusual_flows:
                interpretation += f"Unusual activity concentrated at strikes: {', '.join([f'${f.strike}' for f in unusual_flows[:3]])}. "
            
            interpretation += f"Put/Call ratio of {aggregated.put_call_ratio:.2f} suggests "
            interpretation += "call buying dominance." if aggregated.put_call_ratio < 1 else "put buying pressure."
            
            return interpretation
    
    async def _generate_trade_ideas(
        self,
        sentiment: Sentiment,
        key_levels: List[float],
        unusual_flows: List[OptionsFlow],
        market_context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate trade ideas based on flow analysis."""
        try:
            import ollama
            
            prompt = f"""Based on options flow analysis, suggest 2-3 specific trade ideas.

Sentiment: {sentiment.value}
Key Strike Levels: {', '.join([f'${level}' for level in key_levels[:3]])}
Unusual Activity: {len(unusual_flows)} unusual flows detected
{f"Market Context: {market_context}" if market_context else ""}

Provide specific, actionable trade ideas with strikes and strategies.
Format each on a new line starting with a number."""

            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.8,
                    'num_predict': 200
                }
            )
            
            # Parse trade ideas
            ideas = []
            for line in response['response'].split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    idea = line.lstrip('0123456789.- ').strip()
                    if len(idea) > 10:
                        ideas.append(idea)
            
            return ideas[:3]
            
        except Exception as e:
            self.logger.warning(f"Ollama not available for trade ideas: {e}")
            # Fallback trade ideas
            ideas = []
            
            if sentiment in [Sentiment.BULLISH, Sentiment.VERY_BULLISH]:
                if key_levels:
                    ideas.append(f"Consider call spreads targeting ${key_levels[0]} strike")
                ideas.append("Look for call calendar spreads on pullbacks")
            elif sentiment in [Sentiment.BEARISH, Sentiment.VERY_BEARISH]:
                if key_levels:
                    ideas.append(f"Consider put spreads with protection at ${key_levels[0]}")
                ideas.append("Put butterflies for ranged downside")
            else:
                ideas.append("Iron condors outside the key strike levels")
                ideas.append("Straddle sales if IV elevated")
            
            return ideas
    
    async def _identify_risk_factors(
        self,
        flows: List[OptionsFlow],
        aggregated: AggregatedFlow,
        market_context: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Identify risk factors from flow analysis."""
        risks = []
        
        # Check for one-sided flow
        if aggregated.put_call_ratio > 3 or aggregated.put_call_ratio < 0.3:
            risks.append("Extremely one-sided flow may indicate crowded positioning")
        
        # Check for expiry concentration
        expiry_dates = set(f.expiry.date() for f in flows)
        if len(expiry_dates) == 1:
            risks.append("Flow concentrated in single expiry - event risk possible")
        
        # Check spread widths
        high_spreads = [f for f in flows if f.bid_ask_spread > 0.10]
        if len(high_spreads) > len(flows) * 0.3:
            risks.append("Wide bid-ask spreads indicate low liquidity")
        
        # Check for hedge flow
        if aggregated.put_volume > aggregated.call_volume * 1.5:
            risks.append("Heavy put buying may be hedging - underlying could still rise")
        
        return risks
    
    async def _interpret_sweeps(self, sweep_clusters: List[List[OptionsFlow]]) -> str:
        """Interpret sweep order activity."""
        if not sweep_clusters:
            return "No significant sweep activity"
        
        # Analyze the clusters
        cluster_summary = f"Detected {len(sweep_clusters)} sweep clusters. "
        
        for cluster in sweep_clusters[:2]:  # Top 2 clusters
            strike = cluster[0].strike
            opt_type = cluster[0].option_type
            total_vol = sum(s.volume for s in cluster)
            cluster_summary += f"{opt_type.upper()} ${strike}: {total_vol:,} contracts swept. "
        
        cluster_summary += "This aggressive buying suggests urgent positioning for expected move."
        
        return cluster_summary
    
    async def _interpret_institutional_activity(
        self,
        block_trades: List[OptionsFlow],
        patterns: List[str]
    ) -> str:
        """Interpret institutional activity."""
        if not block_trades and not patterns:
            return "No clear institutional footprints detected"
        
        interpretation = f"Detected {len(block_trades)} block trades"
        
        if block_trades:
            total_block_vol = sum(b.volume for b in block_trades)
            interpretation += f" totaling {total_block_vol:,} contracts. "
        
        if patterns:
            interpretation += f"Patterns observed: {'; '.join(patterns[:2])}. "
        
        interpretation += "This suggests institutional positioning or hedging activity."
        
        return interpretation
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _update_metrics(self, response_time: float, smart_money: bool) -> None:
        """Update performance metrics."""
        self.performance_metrics['total_analyses'] += 1
        
        # Update average response time
        total = self.performance_metrics['total_analyses']
        current_avg = self.performance_metrics['avg_response_time']
        new_avg = ((current_avg * (total - 1)) + response_time) / total
        self.performance_metrics['avg_response_time'] = new_avg
        
        # Track smart money detection
        if smart_money:
            self.performance_metrics['smart_money_detected'] += 1
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'llm_model': DEFAULT_LLM_MODEL,
            'temperature': DEFAULT_TEMPERATURE,
            'max_tokens': MAX_TOKENS,
            'thresholds': {
                'unusual_volume': UNUSUAL_VOLUME_MULTIPLIER,
                'large_trade': LARGE_TRADE_THRESHOLD,
                'sweep_window': SWEEP_TIME_WINDOW,
                'block_min': BLOCK_TRADE_MIN
            }
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_flow_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX02_FlowAgent:
    """
    Factory function to create Flow Agent.
    
    Args:
        config: Agent configuration
        
    Returns:
        Configured SpyderX02_FlowAgent instance
    """
    return SpyderX02_FlowAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization code
_module_instance: Optional[SpyderX02_FlowAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX02_FlowAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX02_FlowAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    import asyncio
    
    async def test_agent():
        """Test the Flow Agent functionality."""
        print("Testing SpyderX02_FlowAgent...")
        print("=" * 60)
        
        # Create agent
        agent = create_flow_agent()
        
        # Create test flow data
        test_flows = [
            OptionsFlow(
                timestamp=datetime.now(),
                symbol="SPY_240201C550",
                strike=550.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='call',
                volume=5000,
                open_interest=10000,
                price=2.50,
                bid_ask_spread=0.05,
                trade_size=500,  # Large trade
                exchange="CBOE",
                is_sweep=True,
                implied_volatility=0.25,
                delta=0.45
            ),
            OptionsFlow(
                timestamp=datetime.now() - timedelta(seconds=30),
                symbol="SPY_240201C550",
                strike=550.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='call',
                volume=3000,
                open_interest=10000,
                price=2.48,
                bid_ask_spread=0.05,
                trade_size=300,
                exchange="ISE",
                is_sweep=True,
                implied_volatility=0.25,
                delta=0.45
            ),
            OptionsFlow(
                timestamp=datetime.now(),
                symbol="SPY_240201P540",
                strike=540.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='put',
                volume=2000,
                open_interest=8000,
                price=1.80,
                bid_ask_spread=0.04,
                trade_size=100,
                exchange="PHLX",
                is_sweep=False,
                implied_volatility=0.22,
                delta=-0.30
            )
        ]
        
        # Test flow analysis
        print("\n1. Testing flow analysis...")
        analysis = await agent.analyze_flow(test_flows, {'vix': 15, 'trend': 'bullish'})
        
        print(f"\nSentiment: {analysis.sentiment.value}")
        print(f"Significance: {analysis.significance.value}")
        print(f"Smart Money: {'Detected' if analysis.smart_money_detected else 'Not detected'}")
        print(f"Key Levels: {analysis.key_levels}")
        print(f"\nInterpretation:\n{analysis.interpretation}")
        
        print(f"\nTrade Ideas:")
        for i, idea in enumerate(analysis.trade_ideas, 1):
            print(f"  {i}. {idea}")
        
        # Test sweep analysis
        print("\n2. Testing sweep analysis...")
        sweep_analysis = await agent.analyze_sweep_activity(test_flows)
        print(f"Sweep Activity: {sweep_analysis}")
        
        # Test institutional detection
        print("\n3. Testing institutional detection...")
        inst_analysis = await agent.detect_institutional_activity(test_flows)
        print(f"Institutional Activity: {inst_analysis}")
        
        # Show performance metrics
        print("\n4. Performance Metrics:")
        metrics = agent.get_performance_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
    
    # Run the test
    asyncio.run(test_agent())
