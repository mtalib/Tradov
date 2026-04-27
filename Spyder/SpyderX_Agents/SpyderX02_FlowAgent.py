#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX02_FlowAgent.py
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
import asyncio
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import numpy as np

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.info("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import is_spyderx_enabled
from Spyder.SpyderU_Utilities.SpyderU17_LLMUtils import strip_thinking_block
from Spyder.SpyderM_Monitoring.SpyderM07_MigrationMonitor import get_migration_monitor
from Spyder.SpyderN_OptionsAnalytics.SpyderN10_OptionsFlowAnalyzer import AdvancedOptionsFlowAnalyzer as OptionsFlowAnalyzer  # noqa: E501
try:
    from Spyder.SpyderS_Signals.SpyderS08_ShortSqueezeDetector import (
        ShortSqueezeDetector,
        SqueezeStrength,
    )
    _SQUEEZE_DETECTOR_AVAILABLE = True
except ImportError:
    ShortSqueezeDetector = None  # type: ignore[assignment,misc]
    SqueezeStrength = None  # type: ignore[assignment,misc]
    _SQUEEZE_DETECTOR_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model configuration
DEFAULT_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma4:e4b") if OLLAMA_AVAILABLE else None
DEFAULT_TEMPERATURE = 0.4  # Balanced for pattern recognition

# Flow detection thresholds
MIN_PREMIUM_THRESHOLD = 25000  # $25k minimum for significant flow
BLOCK_SIZE_THRESHOLD = 100  # 100 contracts for block trades
SWEEP_TIME_WINDOW = 5  # 5 seconds for sweep detection
UNUSUAL_VOLUME_MULTIPLIER = 3  # 3x average volume
INSTITUTIONAL_SIZE_PERCENTILE = 90  # Top 10% by size

# Pattern detection
MOMENTUM_WINDOW = 20  # Number of flows for momentum calculation
SENTIMENT_DECAY_RATE = 0.95  # Decay rate for flow sentiment
PATTERN_CONFIDENCE_THRESHOLD = 0.7

# AI configuration
AI_BATCH_SIZE = 50  # Process flows in batches
FLOW_CACHE_TTL = 300  # 5 minutes cache

# Flow types
AGGRESSIVE_FLOW_TYPES = ['SWEEP', 'ISO', 'CROSS']
NEUTRAL_FLOW_TYPES = ['BLOCK', 'SPREAD']

# ==============================================================================
# ENUMS
# ==============================================================================
class FlowType(Enum):
    """Options flow types"""
    SWEEP = "sweep"
    BLOCK = "block"
    SPLIT = "split"
    SPREAD = "spread"
    ISO = "intermarket_sweep"
    CROSS = "cross"
    REGULAR = "regular"

class FlowSentiment(Enum):
    """Flow sentiment classification"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"

class InstitutionalType(Enum):
    """Institutional trader types"""
    MARKET_MAKER = "market_maker"
    HEDGE_FUND = "hedge_fund"
    PROPRIETARY = "proprietary"
    RETAIL_AGGREGATOR = "retail_aggregator"
    UNKNOWN = "unknown"

class FlowPatternType(Enum):
    """Detected flow pattern types"""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    SHORT_SQUEEZE = "short_squeeze"
    HEDGING = "hedging"
    ROLLING = "rolling"
    CLOSING = "closing"
    OPENING = "opening"

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
    side: str  # 'buy' or 'sell'
    quantity: int
    price: float
    premium: float
    iv: float
    underlying_price: float
    flow_type: FlowType
    exchange: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class FlowAnalysis:
    """Comprehensive flow analysis result"""
    total_flows: int
    bullish_flows: int
    bearish_flows: int
    net_premium: float
    sentiment: FlowSentiment
    sentiment_score: float  # -1 to 1
    unusual_flows: list[OptionsFlow]
    institutional_flows: list[OptionsFlow]
    detected_patterns: list[dict[str, Any]]
    momentum_score: float
    smart_money_confidence: float
    natural_language_summary: str
    trade_ideas: list[dict[str, Any]]
    confidence: float

@dataclass
class InstitutionalActivity:
    """Institutional activity detection"""
    trader_type: InstitutionalType
    flows: list[OptionsFlow]
    total_premium: float
    avg_size: float
    preferred_strikes: list[float]
    time_pattern: str
    confidence: float

@dataclass
class FlowPattern:
    """Detected flow pattern"""
    pattern_type: str
    flows: list[OptionsFlow]
    start_time: datetime
    end_time: datetime
    strikes_involved: list[float]
    net_premium: float
    direction: str
    confidence: float
    description: str

@dataclass
class TradeIdea:
    """AI-generated trade idea from flow"""
    strategy: str
    symbol: str
    strikes: list[float]
    expiry: datetime
    rationale: str
    entry_conditions: list[str]
    risk_reward: dict[str, float]
    confidence: float
    based_on_flows: list[str]  # Flow IDs

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX02_FlowAgent:
    """
    AI-Enhanced Options Flow Analysis Agent.

    This agent provides sophisticated flow analysis by detecting patterns,
    identifying institutional activity, and generating trade ideas. It uses
    AI to understand complex flow relationships and provide actionable insights.

    Attributes:
        model_name: Ollama model for AI analysis
        temperature: Temperature setting for AI responses
        flow_buffer: Recent flows for pattern detection
        pattern_detector: Pattern detection engine
        performance_metrics: Agent performance tracking
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the Flow Agent"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.model_name = model_name
        self.temperature = temperature

        # Initialize components
        self.traditional_analyzer = OptionsFlowAnalyzer()
        self.migration_monitor = get_migration_monitor()

        # Flow tracking
        self.flow_buffer = deque(maxlen=1000)
        self.pattern_history = defaultdict(list)
        self.institutional_tracker = defaultdict(list)

        # Caching
        self.analysis_cache = {}
        self.cache_timestamps = {}
        self._cache_maxsize = 200

        # Performance metrics
        self.performance_metrics = {
            'flows_analyzed': 0,
            'patterns_detected': 0,
            'institutional_detected': 0,
            'trade_ideas_generated': 0,
            'ai_queries': 0,
            'avg_confidence': 0.0,
            'successful_patterns': 0
        }

        # Volume tracking for unusual detection
        self.volume_history = defaultdict(lambda: deque(maxlen=20))
        self.average_sizes = defaultdict(float)

        # Short-squeeze detector (one instance, reused across calls)
        self._squeeze_detector: ShortSqueezeDetector | None = (
            ShortSqueezeDetector() if _SQUEEZE_DETECTOR_AVAILABLE else None
        )

        self.logger.info("Flow Agent initialized with model: %s", model_name)

    # ==========================================================================
    # PUBLIC METHODS - MAIN FUNCTIONALITY
    # ==========================================================================
    async def analyze_flow_batch(
        self,
        flows: list[OptionsFlow],
        market_conditions: dict[str, Any] | None = None
    ) -> FlowAnalysis:
        """
        Analyze a batch of options flows with AI enhancement.

        Args:
            flows: List of options flows to analyze
            market_conditions: Current market conditions

        Returns:
            FlowAnalysis with comprehensive insights
        """
        try:
            if not flows:
                return self._create_empty_analysis()

            # Update flow buffer
            self.flow_buffer.extend(flows)

            # Basic flow metrics
            flow_metrics = self._calculate_flow_metrics(flows)

            # Detect unusual flows
            unusual_flows = self._detect_unusual_flows(flows)

            # Identify institutional activity
            institutional_flows = await self._identify_institutional_flows(flows)

            # Detect patterns
            patterns = await self._detect_flow_patterns(flows, market_conditions)

            # Calculate momentum
            momentum = self._calculate_flow_momentum(flows)

            # Get AI analysis if enabled
            if is_spyderx_enabled("USE_AI_FLOW") and OLLAMA_AVAILABLE:
                analysis = await self._enhance_with_ai_analysis(
                    flows, flow_metrics, patterns, institutional_flows, market_conditions
                )
            else:
                # Fallback to rule-based analysis
                analysis = self._create_rule_based_analysis(
                    flows, flow_metrics, unusual_flows, institutional_flows, patterns, momentum
                )

            # Update performance metrics
            self._update_performance_metrics(analysis)

            # Log in shadow mode
            if is_spyderx_enabled("ENABLE_SPYDERX_SHADOW"):
                await self._log_shadow_analysis(analysis)

            return analysis

        except Exception as e:
            self.logger.error("Flow analysis failed: %s", e, exc_info=True)
            return self._create_error_analysis(str(e))

    async def detect_smart_money(
        self,
        flows: list[OptionsFlow],
        lookback_periods: int = 5
    ) -> dict[str, Any]:
        """
        Detect smart money movements with AI pattern recognition.

        Args:
            flows: Recent options flows
            lookback_periods: Number of periods to analyze

        Returns:
            Smart money analysis results
        """
        try:
            # Get historical flows for comparison
            historical_flows = list(self.flow_buffer)[-lookback_periods * 100:]

            # Identify characteristics of smart money
            smart_money_indicators = {
                'large_blocks': self._identify_large_blocks(flows),
                'perfect_timing': await self._analyze_timing_precision(flows),
                'complex_strategies': self._detect_complex_strategies(flows),
                'consistent_direction': self._analyze_directional_consistency(flows),
                'unusual_strikes': self._find_unusual_strike_selection(flows)
            }

            # AI enhancement for pattern recognition
            if is_spyderx_enabled("USE_AI_FLOW") and OLLAMA_AVAILABLE:
                smart_money_analysis = await self._ai_smart_money_detection(
                    flows, smart_money_indicators, historical_flows
                )
            else:
                smart_money_analysis = self._rule_based_smart_money(smart_money_indicators)

            return smart_money_analysis

        except Exception as e:
            self.logger.error("Smart money detection failed: %s", e, exc_info=True)
            return {'error': str(e), 'confidence': 0.0}

    async def generate_trade_ideas(
        self,
        flow_analysis: FlowAnalysis,
        portfolio_context: dict[str, Any] | None = None
    ) -> list[TradeIdea]:
        """
        Generate actionable trade ideas from flow analysis.

        Args:
            flow_analysis: Completed flow analysis
            portfolio_context: Current portfolio state

        Returns:
            List of trade ideas with confidence scores
        """
        try:
            trade_ideas = []

            # Generate ideas from unusual flows
            if flow_analysis.unusual_flows:
                unusual_ideas = await self._generate_unusual_flow_ideas(
                    flow_analysis.unusual_flows,
                    flow_analysis.sentiment
                )
                trade_ideas.extend(unusual_ideas)

            # Generate ideas from patterns
            if flow_analysis.detected_patterns:
                pattern_ideas = await self._generate_pattern_ideas(
                    flow_analysis.detected_patterns,
                    portfolio_context
                )
                trade_ideas.extend(pattern_ideas)

            # Generate ideas from institutional activity
            if flow_analysis.institutional_flows:
                institutional_ideas = await self._generate_institutional_ideas(
                    flow_analysis.institutional_flows,
                    flow_analysis.smart_money_confidence
                )
                trade_ideas.extend(institutional_ideas)

            # AI enhancement for idea generation
            if is_spyderx_enabled("USE_AI_FLOW") and OLLAMA_AVAILABLE:
                ai_ideas = await self._generate_ai_trade_ideas(
                    flow_analysis,
                    portfolio_context,
                    trade_ideas
                )
                trade_ideas.extend(ai_ideas)

            # Rank and filter ideas
            ranked_ideas = self._rank_trade_ideas(trade_ideas, portfolio_context)

            self.performance_metrics['trade_ideas_generated'] += len(ranked_ideas)

            return ranked_ideas[:5]  # Return top 5 ideas

        except Exception as e:
            self.logger.error("Trade idea generation failed: %s", e, exc_info=True)
            return []

    async def monitor_real_time_flow(
        self,
        flow_stream: asyncio.Queue,
        alert_callback: callable
    ) -> None:
        """
        Monitor real-time options flow with AI alerts.

        Args:
            flow_stream: Queue of incoming flows
            alert_callback: Callback for flow alerts
        """
        self.logger.info("Starting real-time flow monitoring")

        batch = []
        last_analysis = datetime.now()

        while True:
            try:
                # Collect flows for batch processing
                flow = await asyncio.wait_for(flow_stream.get(), timeout=1.0)
                batch.append(flow)

                # Process batch every 10 flows or 5 seconds
                if len(batch) >= 10 or (datetime.now() - last_analysis).seconds >= 5:
                    if batch:
                        # Analyze batch
                        analysis = await self.analyze_flow_batch(batch)

                        # Generate alerts for significant flows
                        alerts = self._generate_flow_alerts(analysis)
                        for alert in alerts:
                            await alert_callback(alert)

                        # Reset batch
                        batch = []
                        last_analysis = datetime.now()

            except TimeoutError:
                continue
            except Exception as e:
                self.logger.error("Real-time flow monitoring error: %s", e, exc_info=True)

    # ==========================================================================
    # PRIVATE METHODS - FLOW ANALYSIS
    # ==========================================================================
    def _calculate_flow_metrics(self, flows: list[OptionsFlow]) -> dict[str, Any]:
        """Calculate basic flow metrics"""
        if not flows:
            return {}

        call_flows = [f for f in flows if f.option_type == 'call']
        put_flows = [f for f in flows if f.option_type == 'put']

        call_premium = sum(f.premium for f in call_flows if f.side == 'buy') - \
                      sum(f.premium for f in call_flows if f.side == 'sell')
        put_premium = sum(f.premium for f in put_flows if f.side == 'buy') - \
                     sum(f.premium for f in put_flows if f.side == 'sell')

        return {
            'total_flows': len(flows),
            'call_flows': len(call_flows),
            'put_flows': len(put_flows),
            'call_premium': call_premium,
            'put_premium': put_premium,
            'net_premium': call_premium + put_premium,
            'put_call_ratio': len(put_flows) / len(call_flows) if call_flows else 0,
            'avg_size': statistics.mean([f.quantity for f in flows]),
            'total_volume': sum(f.quantity for f in flows)
        }

    def _detect_unusual_flows(self, flows: list[OptionsFlow]) -> list[OptionsFlow]:
        """Detect unusual flow activity"""
        unusual = []

        for flow in flows:
            # Check premium threshold
            if flow.premium < MIN_PREMIUM_THRESHOLD:
                continue

            # Check against historical average
            avg_size = self.average_sizes.get(flow.symbol, 0)
            if avg_size > 0 and flow.quantity > avg_size * UNUSUAL_VOLUME_MULTIPLIER:
                unusual.append(flow)
                continue

            # Check for sweep activity
            if flow.flow_type in [FlowType.SWEEP, FlowType.ISO]:
                unusual.append(flow)
                continue

            # Check for aggressive positioning
            if self._is_aggressive_positioning(flow):
                unusual.append(flow)

        return unusual

    async def _identify_institutional_flows(
        self,
        flows: list[OptionsFlow]
    ) -> list[OptionsFlow]:
        """Identify potential institutional flows"""
        institutional = []

        # Size-based detection
        flow_sizes = [f.quantity for f in flows]
        if flow_sizes:
            size_threshold = np.percentile(flow_sizes, INSTITUTIONAL_SIZE_PERCENTILE)

            for flow in flows:
                if flow.quantity >= size_threshold:
                    # Additional checks for institutional characteristics
                    if self._has_institutional_characteristics(flow):
                        institutional.append(flow)
                        self.institutional_tracker[flow.symbol].append(flow)

        return institutional

    async def _detect_flow_patterns(
        self,
        flows: list[OptionsFlow],
        market_conditions: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Detect patterns in options flow"""
        patterns = []

        # Group flows by symbol and strike
        flow_groups = defaultdict(list)
        for flow in flows:
            key = (flow.symbol, flow.strike, flow.expiry)
            flow_groups[key].append(flow)

        # Detect accumulation/distribution
        for _, group_flows in flow_groups.items():
            if len(group_flows) >= 3:
                pattern = self._analyze_accumulation_pattern(group_flows)
                if pattern:
                    patterns.append(pattern)

        # Detect rolling activity
        rolling_patterns = self._detect_rolling_patterns(flows)
        patterns.extend(rolling_patterns)

        # Detect hedging patterns
        hedging_patterns = self._detect_hedging_patterns(flows)
        patterns.extend(hedging_patterns)

        # Detect short squeeze / short covering
        squeeze_patterns = self._detect_short_squeeze_patterns(flows)
        patterns.extend(squeeze_patterns)

        self.performance_metrics['patterns_detected'] += len(patterns)

        return patterns

    def _detect_short_squeeze_patterns(
        self,
        flows: list,
    ) -> list[dict[str, Any]]:
        """
        Detect short covering and short squeeze conditions from options flow.

        Delegates to SpyderS08_ShortSqueezeDetector and converts any
        WATCH-or-above signal into a standardised pattern dict that can be
        handled by the rest of the agent pipeline.

        Returns:
            List of zero or one pattern dict.  Empty when no squeeze is
            detected or when the detector is unavailable.
        """
        if self._squeeze_detector is None or not flows:
            return []

        try:
            self._squeeze_detector.update_options_flow(flows)
            signal = self._squeeze_detector.detect()

            if signal.strength == SqueezeStrength.NONE:
                return []

            return [{
                'type': FlowPattern.SHORT_SQUEEZE.value
                        if hasattr(FlowPattern, 'SHORT_SQUEEZE')
                        else 'short_squeeze',
                'squeeze_type': signal.squeeze_type.value,
                'strength': signal.strength.value,
                'score': signal.composite_score,
                'symbol': flows[0].symbol if flows else 'SPY',
                'price': signal.price,
                'price_change_pct': round(signal.price_change_pct * 100, 3),
                'action_bias': signal.action_bias,
                'confidence': signal.confidence,
                'description': signal.reasoning,
                'components': [
                    {
                        'name': c.name,
                        'score': round(c.score, 2),
                        'threshold': c.threshold,
                        'description': c.description,
                    }
                    for c in signal.components
                    if c.threshold != 'none'
                ],
                'timestamp': signal.timestamp.isoformat(),
            }]
        except Exception as exc:
            self.logger.error("Short squeeze detection error: %s", exc, exc_info=True)
            return []

    # ==========================================================================
    # PRIVATE METHODS - AI ENHANCEMENT
    # ==========================================================================
    async def _enhance_with_ai_analysis(
        self,
        flows: list[OptionsFlow],
        flow_metrics: dict[str, Any],
        patterns: list[dict[str, Any]],
        institutional_flows: list[OptionsFlow],
        market_conditions: dict[str, Any] | None = None
    ) -> FlowAnalysis:
        """Enhance flow analysis with AI insights"""
        try:
            # Prepare context for AI
            context = self._prepare_ai_context(
                flows, flow_metrics, patterns, institutional_flows, market_conditions
            )

            # Query AI model
            prompt = self._construct_flow_prompt(context)
            response = await self._query_ai_model(prompt)

            # Parse AI response
            ai_insights = self._parse_flow_ai_response(response)

            # Generate trade ideas
            trade_ideas = await self._generate_ai_trade_ideas_from_insights(
                ai_insights, flows, patterns
            )

            # Calculate sentiment
            sentiment, sentiment_score = self._calculate_ai_sentiment(
                ai_insights, flow_metrics
            )

            # Build analysis
            analysis = FlowAnalysis(
                total_flows=len(flows),
                bullish_flows=len([f for f in flows if self._is_bullish_flow(f)]),
                bearish_flows=len([f for f in flows if self._is_bearish_flow(f)]),
                net_premium=flow_metrics.get('net_premium', 0),
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                unusual_flows=self._detect_unusual_flows(flows),
                institutional_flows=institutional_flows,
                detected_patterns=patterns,
                momentum_score=self._calculate_flow_momentum(flows),
                smart_money_confidence=ai_insights.get('smart_money_confidence', 0.5),
                natural_language_summary=ai_insights.get('summary', ''),
                trade_ideas=trade_ideas,
                confidence=ai_insights.get('confidence', 0.7)
            )

            self.performance_metrics['ai_queries'] += 1

            return analysis

        except Exception as e:
            self.logger.error("AI flow analysis failed: %s", e, exc_info=True)
            # Fallback to rule-based
            return self._create_rule_based_analysis(
                flows, flow_metrics, self._detect_unusual_flows(flows),
                institutional_flows, patterns, self._calculate_flow_momentum(flows)
            )

    async def _query_ai_model(self, prompt: str) -> str:
        """Query the AI model for flow analysis"""
        if not OLLAMA_AVAILABLE:
            return ""

        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert options flow analyst.
                        Analyze flow patterns to identify smart money movements and institutional activity.
                        Focus on actionable insights and specific trade setups.
                        Be precise about entry levels, position sizing, and risk management."""  # noqa: E501
                    },
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": self.temperature, "think": False}
            )

            return strip_thinking_block(response['message']['content'])

        except Exception as e:
            self.logger.error("AI model query failed: %s", e, exc_info=True)
            return ""

    def _construct_flow_prompt(self, context: dict[str, Any]) -> str:
        """Construct prompt for AI flow analysis"""
        return f"""Analyze the following options flow data and provide insights:

Flow Summary:
- Total Flows: {context['metrics']['total_flows']}
- Call/Put Ratio: {context['metrics'].get('put_call_ratio', 0):.2f}
- Net Premium: ${context['metrics']['net_premium']:,.0f}
- Average Size: {context['metrics']['avg_size']:.0f} contracts

Unusual Activity:
- Large Blocks: {context['unusual_count']}
- Sweeps Detected: {context['sweep_count']}
- Institutional Flows: {context['institutional_count']}

Detected Patterns:
{json.dumps(context['patterns'], indent=2)}

Recent Notable Flows:
{context['notable_flows']}

Market Context:
- SPY Price: ${context.get('spy_price', 450):.2f}
- VIX: {context.get('vix', 15):.1f}
- Trend: {context.get('trend', 'neutral')}

Provide:
1. Overall flow sentiment (bullish/bearish/neutral)
2. Smart money positioning assessment
3. Key observations about institutional activity
4. Specific actionable trade setups based on flow
5. Risk levels and position sizing recommendations
6. Confidence level (0-1) in your analysis

Format as JSON with keys: sentiment, smart_money_confidence, summary,
key_observations, trade_setups, risk_assessment, confidence"""

    # ==========================================================================
    # PRIVATE METHODS - PATTERN DETECTION
    # ==========================================================================
    def _analyze_accumulation_pattern(self, flows: list[OptionsFlow]) -> dict[str, Any] | None:
        """Analyze flows for accumulation/distribution patterns"""
        if len(flows) < 3:
            return None

        # Calculate net positioning
        buy_volume = sum(f.quantity for f in flows if f.side == 'buy')
        sell_volume = sum(f.quantity for f in flows if f.side == 'sell')
        net_volume = buy_volume - sell_volume

        # Check for consistent direction
        if abs(net_volume) < 0.6 * (buy_volume + sell_volume):
            return None  # Not strong enough

        pattern_type = 'accumulation' if net_volume > 0 else 'distribution'

        return {
            'type': pattern_type,
            'symbol': flows[0].symbol,
            'strike': flows[0].strike,
            'expiry': flows[0].expiry.isoformat(),
            'net_volume': net_volume,
            'flow_count': len(flows),
            'avg_price': statistics.mean([f.price for f in flows]),
            'confidence': min(0.9, abs(net_volume) / (buy_volume + sell_volume))
        }

    def _detect_rolling_patterns(self, flows: list[OptionsFlow]) -> list[dict[str, Any]]:
        """Detect option rolling patterns"""
        patterns = []

        # Group by symbol
        symbol_flows = defaultdict(list)
        for flow in flows:
            symbol_flows[flow.symbol].append(flow)

        for symbol, s_flows in symbol_flows.items():
            # Look for simultaneous buy/sell at different strikes/expiries
            sells = [f for f in s_flows if f.side == 'sell']
            buys = [f for f in s_flows if f.side == 'buy']

            for sell in sells:
                for buy in buys:
                    if self._is_roll_candidate(sell, buy):
                        patterns.append({
                            'type': 'rolling',
                            'symbol': symbol,
                            'from_strike': sell.strike,
                            'to_strike': buy.strike,
                            'from_expiry': sell.expiry.isoformat(),
                            'to_expiry': buy.expiry.isoformat(),
                            'size': min(sell.quantity, buy.quantity),
                            'confidence': 0.8
                        })

        return patterns

    def _detect_hedging_patterns(self, flows: list[OptionsFlow]) -> list[dict[str, Any]]:
        """Detect hedging patterns in flows"""
        patterns = []

        # Look for put buying with call selling (collar)
        # Or large put purchases (protective puts)
        put_buys = [f for f in flows if f.option_type == 'put' and f.side == 'buy']

        for put in put_buys:
            if put.quantity >= BLOCK_SIZE_THRESHOLD:
                # Check if it's likely hedging
                if self._is_hedge_characteristics(put):
                    patterns.append({
                        'type': 'hedging',
                        'symbol': put.symbol,
                        'strike': put.strike,
                        'expiry': put.expiry.isoformat(),
                        'size': put.quantity,
                        'premium': put.premium,
                        'hedge_type': 'protective_put',
                        'confidence': 0.75
                    })

        return patterns

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _is_aggressive_positioning(self, flow: OptionsFlow) -> bool:
        """Check if flow represents aggressive positioning"""
        # Check for aggressive flow types
        if flow.flow_type in [FlowType.SWEEP, FlowType.ISO]:
            return True

        # Check for far OTM options with high premium
        moneyness = flow.strike / flow.underlying_price
        if flow.option_type == 'call' and moneyness > 1.05 or flow.option_type == 'put' and moneyness < 0.95:  # 5% OTM calls  # noqa: E501
            return flow.premium > MIN_PREMIUM_THRESHOLD * 2

        return False

    def _has_institutional_characteristics(self, flow: OptionsFlow) -> bool:
        """Check if flow has institutional characteristics"""
        # Large size
        if flow.quantity < BLOCK_SIZE_THRESHOLD:
            return False

        # Clean execution (round lots)
        if flow.quantity % 100 != 0:
            return False

        # Execution timing (market hours)
        hour = flow.timestamp.hour
        return not (hour < 9 or hour > 16)

    def _is_bullish_flow(self, flow: OptionsFlow) -> bool:
        """Determine if flow is bullish"""
        if flow.option_type == 'call' and flow.side == 'buy':
            return True
        return bool(flow.option_type == 'put' and flow.side == 'sell')

    def _is_bearish_flow(self, flow: OptionsFlow) -> bool:
        """Determine if flow is bearish"""
        if flow.option_type == 'put' and flow.side == 'buy':
            return True
        return bool(flow.option_type == 'call' and flow.side == 'sell')

    def _calculate_flow_momentum(self, flows: list[OptionsFlow]) -> float:
        """Calculate momentum score from recent flows"""
        if len(flows) < 5:
            return 0.0

        # Calculate directional flow over time
        time_buckets = defaultdict(float)
        for flow in flows:
            bucket = flow.timestamp.minute // 5  # 5-minute buckets
            value = flow.premium if self._is_bullish_flow(flow) else -flow.premium
            time_buckets[bucket] += value

        # Calculate momentum as trend in buckets
        if len(time_buckets) < 2:
            return 0.0

        values = list(time_buckets.values())
        momentum = (values[-1] - values[0]) / (abs(values[0]) + 1)
        return max(-1, min(1, momentum))  # Normalize to [-1, 1]

    def _is_roll_candidate(self, sell: OptionsFlow, buy: OptionsFlow) -> bool:
        """Check if two flows represent a roll"""
        # Same type
        if sell.option_type != buy.option_type:
            return False

        # Within reasonable time window
        time_diff = abs((sell.timestamp - buy.timestamp).total_seconds())
        if time_diff > 60:  # More than 1 minute apart
            return False

        # Similar size
        size_ratio = min(sell.quantity, buy.quantity) / max(sell.quantity, buy.quantity)
        if size_ratio < 0.8:
            return False

        # Different strikes or expiries
        return sell.strike != buy.strike or sell.expiry != buy.expiry

    def _is_hedge_characteristics(self, flow: OptionsFlow) -> bool:
        """Check if flow has hedge characteristics"""
        # Usually puts for hedging
        if flow.option_type != 'put':
            return False

        # Near the money or slightly OTM
        moneyness = flow.strike / flow.underlying_price
        if moneyness < 0.90 or moneyness > 1.00:
            return False

        # Reasonable expiry (1-3 months)
        days_to_expiry = (flow.expiry - flow.timestamp).days
        return not (days_to_expiry < 30 or days_to_expiry > 90)

    def _prepare_ai_context(
        self,
        flows: list[OptionsFlow],
        flow_metrics: dict[str, Any],
        patterns: list[dict[str, Any]],
        institutional_flows: list[OptionsFlow],
        market_conditions: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Prepare context for AI analysis"""
        # Get notable flows
        notable_flows = sorted(
            flows,
            key=lambda x: x.premium,
            reverse=True
        )[:10]

        notable_flows_str = "\n".join([
            f"{f.timestamp.strftime('%H:%M')} - {f.symbol} {f.strike} {f.option_type} "
            f"{f.side} {f.quantity} @ ${f.price:.2f} (${f.premium:,.0f})"
            for f in notable_flows
        ])

        # Count flow types
        sweep_count = len([f for f in flows if f.flow_type in [FlowType.SWEEP, FlowType.ISO]])
        unusual_count = len(self._detect_unusual_flows(flows))

        context = {
            'metrics': flow_metrics,
            'patterns': patterns[:5],  # Top 5 patterns
            'unusual_count': unusual_count,
            'sweep_count': sweep_count,
            'institutional_count': len(institutional_flows),
            'notable_flows': notable_flows_str,
            'spy_price': market_conditions.get('spy_price', 450) if market_conditions else 450,
            'vix': market_conditions.get('vix', 15) if market_conditions else 15,
            'trend': market_conditions.get('trend', 'neutral') if market_conditions else 'neutral'
        }

        return context

    def _parse_flow_ai_response(self, response: str) -> dict[str, Any]:
        """Parse AI response for flow analysis"""
        try:
            # Try to parse as JSON
            if '{' in response and '}' in response:
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except Exception as e:
            self.logger.debug("Failed to parse flow AI response as JSON: %s", e)

        # Fallback parsing
        return {
            'sentiment': 'neutral',
            'smart_money_confidence': 0.5,
            'summary': response[:200] if response else 'No analysis available',
            'confidence': 0.5
        }

    def _calculate_ai_sentiment(
        self,
        ai_insights: dict[str, Any],
        flow_metrics: dict[str, Any]
    ) -> tuple[FlowSentiment, float]:
        """Calculate sentiment from AI insights and metrics"""
        # Get AI sentiment
        ai_sentiment = ai_insights.get('sentiment', 'neutral').lower()

        # Calculate metric-based sentiment
        call_premium = flow_metrics.get('call_premium', 0)
        put_premium = flow_metrics.get('put_premium', 0)

        if call_premium > put_premium * 1.5:
            metric_sentiment = 'bullish'
            sentiment_score = min(1.0, (call_premium - put_premium) / (call_premium + put_premium + 1))  # noqa: E501
        elif put_premium > call_premium * 1.5:
            metric_sentiment = 'bearish'
            sentiment_score = max(-1.0, (call_premium - put_premium) / (call_premium + put_premium + 1))  # noqa: E501
        else:
            metric_sentiment = 'neutral'
            sentiment_score = (call_premium - put_premium) / (call_premium + put_premium + 1)

        # Combine AI and metric sentiment
        if ai_sentiment == metric_sentiment:
            final_sentiment = FlowSentiment(ai_sentiment.upper())
        else:
            final_sentiment = FlowSentiment.MIXED

        return final_sentiment, sentiment_score

    async def _generate_ai_trade_ideas_from_insights(
        self,
        ai_insights: dict[str, Any],
        flows: list[OptionsFlow],
        patterns: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate trade ideas from AI insights"""
        trade_setups = ai_insights.get('trade_setups', [])
        ideas = []

        if isinstance(trade_setups, list):
            for setup in trade_setups[:3]:  # Max 3 AI ideas
                if isinstance(setup, dict):
                    ideas.append({
                        'strategy': setup.get('strategy', 'Unknown'),
                        'strikes': setup.get('strikes', []),
                        'rationale': setup.get('rationale', ''),
                        'entry_conditions': setup.get('entry_conditions', []),
                        'risk_reward': setup.get('risk_reward', {}),
                        'confidence': setup.get('confidence', 0.5)
                    })

        return ideas

    def _create_rule_based_analysis(
        self,
        flows: list[OptionsFlow],
        flow_metrics: dict[str, Any],
        unusual_flows: list[OptionsFlow],
        institutional_flows: list[OptionsFlow],
        patterns: list[dict[str, Any]],
        momentum: float
    ) -> FlowAnalysis:
        """Create rule-based flow analysis"""
        # Calculate sentiment
        call_premium = flow_metrics.get('call_premium', 0)
        put_premium = flow_metrics.get('put_premium', 0)

        if call_premium > put_premium * 1.5:
            sentiment = FlowSentiment.BULLISH
            sentiment_score = 0.7
        elif put_premium > call_premium * 1.5:
            sentiment = FlowSentiment.BEARISH
            sentiment_score = -0.7
        else:
            sentiment = FlowSentiment.NEUTRAL
            sentiment_score = 0.0

        # Generate summary
        summary = f"Analyzed {len(flows)} flows with "
        if unusual_flows:
            summary += f"{len(unusual_flows)} unusual flows detected. "
        if institutional_flows:
            summary += f"{len(institutional_flows)} potential institutional trades. "
        summary += f"Net premium flow: ${flow_metrics.get('net_premium', 0):,.0f}"

        return FlowAnalysis(
            total_flows=len(flows),
            bullish_flows=len([f for f in flows if self._is_bullish_flow(f)]),
            bearish_flows=len([f for f in flows if self._is_bearish_flow(f)]),
            net_premium=flow_metrics.get('net_premium', 0),
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            unusual_flows=unusual_flows,
            institutional_flows=institutional_flows,
            detected_patterns=patterns,
            momentum_score=momentum,
            smart_money_confidence=0.5,
            natural_language_summary=summary,
            trade_ideas=[],
            confidence=0.6
        )

    def _rank_trade_ideas(
        self,
        ideas: list[TradeIdea],
        portfolio_context: dict[str, Any] | None = None
    ) -> list[TradeIdea]:
        """Rank trade ideas by quality and fit"""
        if not ideas:
            return []

        # Score each idea
        scored_ideas = []
        for idea in ideas:
            score = idea.confidence

            # Adjust for portfolio context
            if portfolio_context:
                # Reduce score if similar position exists
                existing_positions = portfolio_context.get('positions', [])
                for pos in existing_positions:
                    if pos.get('symbol') == idea.symbol:
                        score *= 0.7  # Reduce score for duplicate exposure

            scored_ideas.append((score, idea))

        # Sort by score
        scored_ideas.sort(key=lambda x: x[0], reverse=True)

        return [idea for score, idea in scored_ideas]

    def _generate_flow_alerts(self, analysis: FlowAnalysis) -> list[dict[str, Any]]:
        """Generate alerts from flow analysis"""
        alerts = []

        # Alert for strong directional flow
        if abs(analysis.sentiment_score) > 0.8:
            direction = "bullish" if analysis.sentiment_score > 0 else "bearish"
            alerts.append({
                'type': 'strong_directional_flow',
                'message': f"Strong {direction} flow detected",
                'severity': 'high',
                'data': {
                    'sentiment_score': analysis.sentiment_score,
                    'net_premium': analysis.net_premium
                }
            })

        # Alert for unusual activity
        if len(analysis.unusual_flows) >= 5:
            alerts.append({
                'type': 'unusual_activity',
                'message': f"{len(analysis.unusual_flows)} unusual flows detected",
                'severity': 'medium',
                'data': {
                    'count': len(analysis.unusual_flows),
                    'total_premium': sum(f.premium for f in analysis.unusual_flows)
                }
            })

        # Alert for institutional activity
        if analysis.smart_money_confidence > 0.8:
            alerts.append({
                'type': 'smart_money',
                'message': "High confidence smart money activity detected",
                'severity': 'high',
                'data': {
                    'confidence': analysis.smart_money_confidence,
                    'institutional_count': len(analysis.institutional_flows)
                }
            })

        return alerts

    def _update_performance_metrics(self, analysis: FlowAnalysis) -> None:
        """Update agent performance metrics"""
        self.performance_metrics['flows_analyzed'] += analysis.total_flows

        # Update average confidence
        total_analyses = self.performance_metrics.get('total_analyses', 0) + 1
        self.performance_metrics['total_analyses'] = total_analyses

        avg_conf = self.performance_metrics['avg_confidence']
        self.performance_metrics['avg_confidence'] = (
            (avg_conf * (total_analyses - 1) + analysis.confidence) / total_analyses
        )

        # Track institutional detection
        if analysis.institutional_flows:
            self.performance_metrics['institutional_detected'] += len(analysis.institutional_flows)

    async def _log_shadow_analysis(self, analysis: FlowAnalysis) -> None:
        """Log analysis for shadow mode comparison"""
        if hasattr(self, 'migration_monitor'):
            try:
                comparison_data = {
                    'total_flows': analysis.total_flows,
                    'sentiment': analysis.sentiment.value,
                    'unusual_count': len(analysis.unusual_flows),
                    'patterns': len(analysis.detected_patterns),
                    'confidence': analysis.confidence
                }

                # Log to migration monitor
                await self.migration_monitor.log_ai_analysis(
                    'FlowAgent',
                    comparison_data
                )
            except Exception as e:
                self.logger.error("Shadow logging failed: %s", e, exc_info=True)

    def _create_empty_analysis(self) -> FlowAnalysis:
        """Create empty analysis result"""
        return FlowAnalysis(
            total_flows=0,
            bullish_flows=0,
            bearish_flows=0,
            net_premium=0.0,
            sentiment=FlowSentiment.NEUTRAL,
            sentiment_score=0.0,
            unusual_flows=[],
            institutional_flows=[],
            detected_patterns=[],
            momentum_score=0.0,
            smart_money_confidence=0.0,
            natural_language_summary="No flows to analyze",
            trade_ideas=[],
            confidence=0.0
        )

    def _create_error_analysis(self, error: str) -> FlowAnalysis:
        """Create error analysis result"""
        return FlowAnalysis(
            total_flows=0,
            bullish_flows=0,
            bearish_flows=0,
            net_premium=0.0,
            sentiment=FlowSentiment.NEUTRAL,
            sentiment_score=0.0,
            unusual_flows=[],
            institutional_flows=[],
            detected_patterns=[],
            momentum_score=0.0,
            smart_money_confidence=0.0,
            natural_language_summary=f"Analysis error: {error}",
            trade_ideas=[],
            confidence=0.0
        )

    def get_performance_metrics(self) -> dict[str, Any]:
        """Get agent performance metrics"""
        return self.performance_metrics.copy()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_flow_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE
) -> SpyderX02_FlowAgent:
    """
    Factory function to create Flow Agent instance.

    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses

    Returns:
        SpyderX02_FlowAgent instance
    """
    return SpyderX02_FlowAgent(model_name, temperature)

# Singleton instance
_module_instance = None
_module_instance_lock = threading.Lock()


def get_module_instance() -> SpyderX02_FlowAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        with _module_instance_lock:
            if _module_instance is None:
                _module_instance = create_flow_agent()
    return _module_instance

