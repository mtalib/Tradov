#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX13_MarketAnalysisAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Market Analysis and Regime Detection

Description:
    This agent provides sophisticated market analysis by combining traditional
    technical analysis with AI-powered pattern recognition and regime detection.
    It identifies market conditions, trends, and potential turning points while
    providing natural language insights about market dynamics. The agent learns
    from historical patterns to improve prediction accuracy.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-17
Last Updated: 2025-01-28 Time: 18:30
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import hashlib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats, signal
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU11_FeatureFlags import is_spyderx_enabled, SPYDERX_FEATURE_FLAGS
from SpyderF_Analysis.SpyderF10_MarketRegimeDetector import MarketRegimeDetector
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF02_PriceAction import PriceActionAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model configuration
DEFAULT_MODEL = "llama3" if OLLAMA_AVAILABLE else None
DEFAULT_TEMPERATURE = 0.4  # Balanced for market analysis

# Market regime thresholds
TREND_STRENGTH_THRESHOLD = 0.7
VOLATILITY_PERCENTILES = [25, 50, 75, 90]
VOLUME_ANOMALY_THRESHOLD = 2.0  # Standard deviations
CORRELATION_WINDOW = 20  # Days

# Pattern detection
MIN_PATTERN_LENGTH = 5  # Bars
PATTERN_SIMILARITY_THRESHOLD = 0.85
MAX_PATTERNS_TO_TRACK = 100

# AI configuration
ANALYSIS_CACHE_TTL = 300  # 5 minutes
CONFIDENCE_THRESHOLD = 0.75

# Market indicators
INDICATORS_TO_TRACK = [
    'RSI', 'MACD', 'BB', 'ATR', 'OBV', 'ADX',
    'StochRSI', 'Williams%R', 'CCI', 'MFI'
]

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classifications"""
    BULL_QUIET = "bull_quiet"
    BULL_VOLATILE = "bull_volatile"
    BEAR_QUIET = "bear_quiet"
    BEAR_VOLATILE = "bear_volatile"
    RANGING = "ranging"
    TRANSITION = "transition"

class TrendStrength(Enum):
    """Trend strength levels"""
    STRONG_UP = "strong_up"
    MODERATE_UP = "moderate_up"
    WEAK_UP = "weak_up"
    NEUTRAL = "neutral"
    WEAK_DOWN = "weak_down"
    MODERATE_DOWN = "moderate_down"
    STRONG_DOWN = "strong_down"

class MarketPhase(Enum):
    """Market cycle phases"""
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"

class PatternType(Enum):
    """Chart pattern types"""
    HEAD_SHOULDERS = "head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIANGLE = "triangle"
    FLAG = "flag"
    WEDGE = "wedge"
    CHANNEL = "channel"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """Container for market data"""
    symbol: str
    ohlcv: pd.DataFrame
    volume_profile: Optional[pd.Series] = None
    options_data: Optional[pd.DataFrame] = None
    correlated_assets: Optional[Dict[str, pd.Series]] = None
    economic_data: Optional[Dict[str, Any]] = None

@dataclass
class MarketAnalysis:
    """Comprehensive market analysis result"""
    regime: MarketRegime
    trend: TrendStrength
    phase: MarketPhase
    support_levels: List[float]
    resistance_levels: List[float]
    key_levels: Dict[str, float]
    patterns: List[Dict[str, Any]]
    indicators: Dict[str, float]
    correlations: Dict[str, float]
    volatility_analysis: Dict[str, float]
    volume_analysis: Dict[str, Any]
    market_breadth: Dict[str, float]
    natural_language_summary: str
    predictions: Dict[str, Any]
    confidence_scores: Dict[str, float]

@dataclass
class RegimeAnalysis:
    """Detailed regime analysis"""
    current_regime: MarketRegime
    regime_duration: int  # Days
    regime_strength: float
    transition_probability: float
    historical_performance: Dict[str, float]
    expected_duration: int
    key_characteristics: List[str]

@dataclass
class PatternDetection:
    """Detected chart pattern"""
    pattern_type: PatternType
    start_date: datetime
    end_date: Optional[datetime]
    key_points: List[Tuple[datetime, float]]
    target_price: float
    stop_loss: float
    confidence: float
    completion_status: float  # 0-1

@dataclass
class MarketPrediction:
    """AI-generated market prediction"""
    timeframe: str
    direction: str
    target_levels: List[float]
    probability: float
    key_drivers: List[str]
    risk_factors: List[str]
    alternative_scenarios: List[Dict[str, Any]]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX13_MarketAnalysisAgent:
    """
    AI-Enhanced Market Analysis Agent.
    
    This agent provides comprehensive market analysis by combining traditional
    technical analysis with AI-powered insights. It detects market regimes,
    identifies patterns, and generates predictions with natural language
    explanations.
    
    Attributes:
        model_name: Ollama model for AI analysis
        temperature: Temperature setting for AI responses
        regime_detector: Traditional regime detection
        pattern_buffer: Historical patterns for comparison
        analysis_cache: Cache for analysis results
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the Market Analysis Agent"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.model_name = model_name
        self.temperature = temperature
        
        # Initialize components
        self.regime_detector = MarketRegimeDetector()
        self.trend_detector = TrendDetector()
        self.price_action = PriceActionAnalyzer()
        
        # Pattern tracking
        self.pattern_buffer = deque(maxlen=MAX_PATTERNS_TO_TRACK)
        self.regime_history = deque(maxlen=252)  # 1 year
        
        # Analysis cache
        self.analysis_cache = {}
        self.cache_timestamps = {}
        
        # Performance tracking
        self.agent_metrics = {
            'analyses_performed': 0,
            'patterns_detected': 0,
            'regime_changes_detected': 0,
            'predictions_made': 0,
            'ai_queries': 0,
            'avg_confidence': 0.0,
            'prediction_accuracy': 0.0
        }
        
        # Market indicators
        self.indicator_history = defaultdict(lambda: deque(maxlen=100))
        
        self.logger.info(f"Market Analysis Agent initialized with model: {model_name}")
    
    # ==========================================================================
    # PUBLIC METHODS - MAIN FUNCTIONALITY
    # ==========================================================================
    async def analyze_market(
        self,
        market_data: MarketData,
        analysis_depth: str = 'comprehensive'
    ) -> MarketAnalysis:
        """
        Perform comprehensive AI-enhanced market analysis.
        
        Args:
            market_data: Market data to analyze
            analysis_depth: 'quick', 'standard', or 'comprehensive'
            
        Returns:
            MarketAnalysis with AI insights
        """
        try:
            # Check cache
            cache_key = self._generate_cache_key(market_data)
            if self._is_cache_valid(cache_key) and analysis_depth != 'comprehensive':
                return self.analysis_cache[cache_key]
            
            # Detect market regime
            regime_analysis = await self._analyze_market_regime(market_data)
            
            # Analyze trend
            trend_analysis = await self._analyze_trend(market_data)
            
            # Detect support/resistance
            sr_levels = self._detect_support_resistance(market_data.ohlcv)
            
            # Detect patterns
            patterns = await self._detect_patterns(market_data)
            
            # Calculate indicators
            indicators = self._calculate_indicators(market_data.ohlcv)
            
            # Analyze correlations
            correlations = self._analyze_correlations(market_data)
            
            # Analyze volatility
            volatility_analysis = self._analyze_volatility(market_data.ohlcv)
            
            # Analyze volume
            volume_analysis = await self._analyze_volume(market_data)
            
            # Market breadth (if available)
            breadth = self._analyze_market_breadth(market_data)
            
            # Get AI-enhanced analysis
            if is_spyderx_enabled("USE_AI_MARKET_ANALYSIS") and OLLAMA_AVAILABLE:
                analysis = await self._enhance_with_ai_analysis(
                    regime_analysis, trend_analysis, sr_levels,
                    patterns, indicators, correlations,
                    volatility_analysis, volume_analysis,
                    breadth, market_data
                )
            else:
                # Fallback to rule-based analysis
                analysis = self._create_rule_based_analysis(
                    regime_analysis, trend_analysis, sr_levels,
                    patterns, indicators, correlations,
                    volatility_analysis, volume_analysis, breadth
                )
            
            # Cache result
            self.analysis_cache[cache_key] = analysis
            self.cache_timestamps[cache_key] = datetime.now()
            
            # Update metrics
            self._update_agent_metrics(analysis)
            
            # Store in history
            self.regime_history.append({
                'timestamp': datetime.now(),
                'regime': analysis.regime,
                'indicators': indicators
            })
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            return self._create_error_analysis(str(e))
    
    async def predict_market_movement(
        self,
        market_analysis: MarketAnalysis,
        timeframes: List[str] = ['1D', '1W', '1M']
    ) -> Dict[str, MarketPrediction]:
        """
        Generate AI-powered market predictions.
        
        Args:
            market_analysis: Completed market analysis
            timeframes: Prediction timeframes
            
        Returns:
            Dictionary of predictions by timeframe
        """
        try:
            predictions = {}
            
            for timeframe in timeframes:
                # Generate prediction for timeframe
                prediction = await self._generate_prediction(
                    market_analysis, timeframe
                )
                predictions[timeframe] = prediction
            
            self.agent_metrics['predictions_made'] += len(predictions)
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Market prediction failed: {e}")
            return {}
    
    async def detect_regime_change(
        self,
        current_analysis: MarketAnalysis,
        lookback_periods: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Detect potential regime changes using AI.
        
        Args:
            current_analysis: Current market analysis
            lookback_periods: Periods to look back
            
        Returns:
            Regime change detection result or None
        """
        try:
            # Get historical regimes
            historical_regimes = list(self.regime_history)[-lookback_periods:]
            
            if len(historical_regimes) < 5:
                return None
            
            # Check for regime stability
            recent_regimes = [r['regime'] for r in historical_regimes[-5:]]
            regime_counts = defaultdict(int)
            for regime in recent_regimes:
                regime_counts[regime] += 1
            
            # Detect transition
            if len(regime_counts) > 1:
                # Mixed regimes indicate potential transition
                transition_analysis = await self._analyze_regime_transition(
                    current_analysis, historical_regimes
                )
                
                if transition_analysis['probability'] > 0.7:
                    self.agent_metrics['regime_changes_detected'] += 1
                    return transition_analysis
            
            return None
            
        except Exception as e:
            self.logger.error(f"Regime change detection failed: {e}")
            return None
    
    async def identify_trading_opportunities(
        self,
        market_analysis: MarketAnalysis,
        risk_tolerance: str = 'moderate'
    ) -> List[Dict[str, Any]]:
        """
        Identify trading opportunities based on market analysis.
        
        Args:
            market_analysis: Completed market analysis
            risk_tolerance: 'conservative', 'moderate', or 'aggressive'
            
        Returns:
            List of trading opportunities
        """
        try:
            opportunities = []
            
            # Pattern-based opportunities
            for pattern in market_analysis.patterns:
                if pattern['confidence'] > CONFIDENCE_THRESHOLD:
                    opp = self._create_pattern_opportunity(pattern, risk_tolerance)
                    if opp:
                        opportunities.append(opp)
            
            # Support/resistance opportunities
            sr_opportunities = self._identify_sr_opportunities(
                market_analysis, risk_tolerance
            )
            opportunities.extend(sr_opportunities)
            
            # Regime-based opportunities
            regime_opportunities = await self._identify_regime_opportunities(
                market_analysis, risk_tolerance
            )
            opportunities.extend(regime_opportunities)
            
            # AI-enhanced opportunity detection
            if is_spyderx_enabled("USE_AI_MARKET_ANALYSIS") and OLLAMA_AVAILABLE:
                ai_opportunities = await self._ai_identify_opportunities(
                    market_analysis, risk_tolerance
                )
                opportunities.extend(ai_opportunities)
            
            # Rank opportunities
            ranked = self._rank_opportunities(opportunities, market_analysis)
            
            return ranked[:10]  # Top 10 opportunities
            
        except Exception as e:
            self.logger.error(f"Opportunity identification failed: {e}")
            return []
    
    # ==========================================================================
    # PRIVATE METHODS - REGIME ANALYSIS
    # ==========================================================================
    async def _analyze_market_regime(
        self,
        market_data: MarketData
    ) -> RegimeAnalysis:
        """Analyze current market regime"""
        ohlcv = market_data.ohlcv
        
        # Calculate returns
        returns = ohlcv['close'].pct_change().dropna()
        
        # Trend analysis
        trend = self._calculate_trend_strength(ohlcv)
        
        # Volatility analysis
        volatility = returns.rolling(20).std().iloc[-1]
        volatility_percentile = self._calculate_volatility_percentile(volatility)
        
        # Determine regime
        if trend > TREND_STRENGTH_THRESHOLD:
            if volatility_percentile < 50:
                regime = MarketRegime.BULL_QUIET
            else:
                regime = MarketRegime.BULL_VOLATILE
        elif trend < -TREND_STRENGTH_THRESHOLD:
            if volatility_percentile < 50:
                regime = MarketRegime.BEAR_QUIET
            else:
                regime = MarketRegime.BEAR_VOLATILE
        else:
            regime = MarketRegime.RANGING
        
        # Calculate regime duration
        regime_duration = self._calculate_regime_duration(regime)
        
        # Historical performance in regime
        historical_perf = self._get_regime_historical_performance(regime)
        
        return RegimeAnalysis(
            current_regime=regime,
            regime_duration=regime_duration,
            regime_strength=abs(trend),
            transition_probability=self._calculate_transition_probability(regime, trend),
            historical_performance=historical_perf,
            expected_duration=historical_perf.get('avg_duration', 20),
            key_characteristics=self._get_regime_characteristics(regime)
        )
    
    # ==========================================================================
    # PRIVATE METHODS - PATTERN DETECTION
    # ==========================================================================
    async def _detect_patterns(
        self,
        market_data: MarketData
    ) -> List[Dict[str, Any]]:
        """Detect chart patterns using AI and traditional methods"""
        patterns = []
        ohlcv = market_data.ohlcv
        
        # Traditional pattern detection
        traditional_patterns = self._detect_traditional_patterns(ohlcv)
        patterns.extend(traditional_patterns)
        
        # AI pattern detection if enabled
        if is_spyderx_enabled("USE_AI_MARKET_ANALYSIS") and OLLAMA_AVAILABLE:
            ai_patterns = await self._ai_detect_patterns(ohlcv)
            patterns.extend(ai_patterns)
        
        # Store detected patterns
        for pattern in patterns:
            self.pattern_buffer.append({
                'timestamp': datetime.now(),
                'pattern': pattern
            })
        
        self.agent_metrics['patterns_detected'] += len(patterns)
        
        return patterns
    
    def _detect_traditional_patterns(self, ohlcv: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect patterns using traditional methods"""
        patterns = []
        
        # Head and Shoulders
        hs_pattern = self._detect_head_shoulders(ohlcv)
        if hs_pattern:
            patterns.append(hs_pattern)
        
        # Double Top/Bottom
        double_patterns = self._detect_double_patterns(ohlcv)
        patterns.extend(double_patterns)
        
        # Triangles
        triangle_patterns = self._detect_triangles(ohlcv)
        patterns.extend(triangle_patterns)
        
        return patterns
    
    # ==========================================================================
    # PRIVATE METHODS - AI ENHANCEMENT
    # ==========================================================================
    async def _enhance_with_ai_analysis(
        self,
        regime_analysis: RegimeAnalysis,
        trend_analysis: TrendStrength,
        sr_levels: Dict[str, List[float]],
        patterns: List[Dict[str, Any]],
        indicators: Dict[str, float],
        correlations: Dict[str, float],
        volatility_analysis: Dict[str, float],
        volume_analysis: Dict[str, Any],
        breadth: Dict[str, float],
        market_data: MarketData
    ) -> MarketAnalysis:
        """Enhance analysis with AI insights"""
        try:
            # Prepare context
            context = {
                'regime': regime_analysis.current_regime.value,
                'trend': trend_analysis.value,
                'support_levels': sr_levels.get('support', []),
                'resistance_levels': sr_levels.get('resistance', []),
                'patterns': [p['type'] for p in patterns[:5]],
                'indicators': indicators,
                'volatility': volatility_analysis,
                'volume': volume_analysis,
                'current_price': market_data.ohlcv['close'].iloc[-1],
                'price_change_1d': market_data.ohlcv['close'].pct_change().iloc[-1],
                'price_change_5d': market_data.ohlcv['close'].pct_change(5).iloc[-1]
            }
            
            # Query AI
            prompt = self._construct_market_prompt(context)
            response = await self._query_ai_model(prompt)
            
            # Parse response
            ai_insights = self._parse_market_ai_response(response)
            
            # Generate predictions
            predictions = await self._generate_ai_predictions(
                context, ai_insights
            )
            
            # Calculate confidence scores
            confidence_scores = self._calculate_market_confidence(
                ai_insights, patterns, indicators
            )
            
            analysis = MarketAnalysis(
                regime=regime_analysis.current_regime,
                trend=trend_analysis,
                phase=self._determine_market_phase(regime_analysis, trend_analysis),
                support_levels=sr_levels.get('support', []),
                resistance_levels=sr_levels.get('resistance', []),
                key_levels=self._identify_key_levels(sr_levels, market_data),
                patterns=patterns,
                indicators=indicators,
                correlations=correlations,
                volatility_analysis=volatility_analysis,
                volume_analysis=volume_analysis,
                market_breadth=breadth,
                natural_language_summary=ai_insights.get('summary', ''),
                predictions=predictions,
                confidence_scores=confidence_scores
            )
            
            self.agent_metrics['ai_queries'] += 1
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"AI market analysis failed: {e}")
            return self._create_rule_based_analysis(
                regime_analysis, trend_analysis, sr_levels,
                patterns, indicators, correlations,
                volatility_analysis, volume_analysis, breadth
            )
    
    async def _query_ai_model(self, prompt: str) -> str:
        """Query the AI model for market analysis"""
        if not OLLAMA_AVAILABLE:
            return ""
            
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert market analyst and trader.
                        Analyze market conditions to identify opportunities and risks.
                        Provide specific, actionable insights with price levels.
                        Consider technical indicators, patterns, and market structure."""
                    },
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": self.temperature}
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"AI model query failed: {e}")
            return ""
    
    def _construct_market_prompt(self, context: Dict[str, Any]) -> str:
        """Construct prompt for AI market analysis"""
        return f"""Analyze the following market conditions:

Market State:
- Current Regime: {context['regime']}
- Trend: {context['trend']}
- Current Price: ${context['current_price']:.2f}
- 1-Day Change: {context['price_change_1d']:.2%}
- 5-Day Change: {context['price_change_5d']:.2%}

Technical Levels:
- Support: {context['support_levels'][:3]}
- Resistance: {context['resistance_levels'][:3]}

Patterns Detected: {context['patterns']}

Key Indicators:
{json.dumps({k: v for k, v in context['indicators'].items() if k in ['RSI', 'MACD', 'ADX']}, indent=2)}

Volatility: {context['volatility'].get('current', 0):.2%} (Percentile: {context['volatility'].get('percentile', 50)})

Provide:
1. Market assessment summary (100 words)
2. Key opportunities with specific entry/exit levels
3. Major risks to watch
4. Expected market direction next 1-5 days
5. Confidence level in assessment (0-1)

Format as JSON with keys: summary, opportunities, risks, prediction, confidence"""
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _calculate_trend_strength(self, ohlcv: pd.DataFrame) -> float:
        """Calculate trend strength (-1 to 1)"""
        close = ohlcv['close']
        
        # Multiple timeframe analysis
        ma_short = close.rolling(10).mean()
        ma_medium = close.rolling(20).mean()
        ma_long = close.rolling(50).mean()
        
        # Current position relative to MAs
        current = close.iloc[-1]
        
        score = 0
        if current > ma_short.iloc[-1]:
            score += 0.33
        if current > ma_medium.iloc[-1]:
            score += 0.33
        if current > ma_long.iloc[-1]:
            score += 0.34
        
        # Adjust for MA alignment
        if ma_short.iloc[-1] > ma_medium.iloc[-1] > ma_long.iloc[-1]:
            score *= 1.2
        elif ma_short.iloc[-1] < ma_medium.iloc[-1] < ma_long.iloc[-1]:
            score *= -1.2
        
        return max(-1, min(1, score))
    
    def _detect_support_resistance(self, ohlcv: pd.DataFrame) -> Dict[str, List[float]]:
        """Detect support and resistance levels"""
        high = ohlcv['high']
        low = ohlcv['low']
        close = ohlcv['close']
        
        # Find local extrema
        highs = signal.argrelextrema(high.values, np.greater, order=5)[0]
        lows = signal.argrelextrema(low.values, np.less, order=5)[0]
        
        # Extract price levels
        resistance_levels = sorted(high.iloc[highs].tolist(), reverse=True)[:5]
        support_levels = sorted(low.iloc[lows].tolist())[:5]
        
        # Add psychological levels
        current = close.iloc[-1]
        psychological_levels = [
            round(current / 10) * 10,  # Nearest 10
            round(current / 50) * 50,  # Nearest 50
            round(current / 100) * 100  # Nearest 100
        ]
        
        return {
            'support': support_levels,
            'resistance': resistance_levels,
            'psychological': psychological_levels
        }
    
    def _calculate_indicators(self, ohlcv: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators"""
        close = ohlcv['close']
        high = ohlcv['high']
        low = ohlcv['low']
        volume = ohlcv['volume']
        
        indicators = {}
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        indicators['RSI'] = 100 - (100 / (1 + rs)).iloc[-1]
        
        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        indicators['MACD'] = (ema12 - ema26).iloc[-1]
        indicators['MACD_signal'] = (ema12 - ema26).ewm(span=9, adjust=False).mean().iloc[-1]
        
        # ATR
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        indicators['ATR'] = tr.rolling(14).mean().iloc[-1]
        
        # ADX
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr14 = tr.rolling(14).sum()
        plus_di = 100 * (plus_dm.rolling(14).sum() / tr14)
        minus_di = 100 * (minus_dm.rolling(14).sum() / tr14)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        indicators['ADX'] = dx.rolling(14).mean().iloc[-1]
        
        # Store in history
        for key, value in indicators.items():
            self.indicator_history[key].append(value)
        
        return indicators
    
    def _generate_cache_key(self, market_data: MarketData) -> str:
        """Generate cache key for market data"""
        key_data = {
            'symbol': market_data.symbol,
            'last_close': market_data.ohlcv['close'].iloc[-1],
            'last_volume': market_data.ohlcv['volume'].iloc[-1],
            'data_points': len(market_data.ohlcv)
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
        
        age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
        return age < ANALYSIS_CACHE_TTL
    
    def _update_agent_metrics(self, analysis: MarketAnalysis) -> None:
        """Update agent performance metrics"""
        self.agent_metrics['analyses_performed'] += 1
        
        # Update average confidence
        n = self.agent_metrics['analyses_performed']
        avg_conf = self.agent_metrics['avg_confidence']
        new_conf = analysis.confidence_scores.get('overall', 0.7)
        
        self.agent_metrics['avg_confidence'] = (
            (avg_conf * (n - 1) + new_conf) / n
        )
    
    def get_agent_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return self.agent_metrics.copy()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_market_analysis_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE
) -> SpyderX13_MarketAnalysisAgent:
    """
    Factory function to create Market Analysis Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX13_MarketAnalysisAgent instance
    """
    return SpyderX13_MarketAnalysisAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX13_MarketAnalysisAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_market_analysis_agent()
    return _module_instance