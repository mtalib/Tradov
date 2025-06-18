#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX02_MarketAnalysisAgent.py
Purpose: AI-Enhanced Market Analysis Agent
         Pattern Recognition, Regime Detection, and Context-Aware Analysis

Key Capabilities:
- Advanced pattern recognition beyond rule-based systems
- Market regime detection (trending, ranging, volatile, calm)
- Context-aware trend analysis
- Integration of technical indicators with AI interpretation
- Multi-timeframe analysis
- Real-time market condition assessment

Created: Tuesday, June 17, 2025
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import logging
from collections import deque
import warnings
warnings.filterwarnings('ignore')

# AI/ML imports
from openai import AsyncOpenAI
import aiohttp
from functools import lru_cache

# Technical analysis imports
import talib
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans


class MarketRegime(Enum):
    """Market regime classifications"""
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    SQUEEZE = "SQUEEZE"
    PARABOLIC = "PARABOLIC"
    CRASH = "CRASH"


class PatternType(Enum):
    """Technical pattern types"""
    # Classic Patterns
    HEAD_SHOULDERS = "HEAD_SHOULDERS"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    TRIANGLE = "TRIANGLE"
    FLAG = "FLAG"
    WEDGE = "WEDGE"
    CUP_HANDLE = "CUP_HANDLE"
    
    # Candlestick Patterns
    DOJI = "DOJI"
    HAMMER = "HAMMER"
    SHOOTING_STAR = "SHOOTING_STAR"
    ENGULFING = "ENGULFING"
    HARAMI = "HARAMI"
    
    # Advanced Patterns
    ELLIOTT_WAVE = "ELLIOTT_WAVE"
    WYCKOFF = "WYCKOFF"
    HARMONIC = "HARMONIC"


class TrendStrength(Enum):
    """Trend strength classifications"""
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"


@dataclass
class MarketAnalysis:
    """Complete market analysis result"""
    timestamp: datetime
    regime: MarketRegime
    trend: Dict[str, Any]
    patterns: List[Dict[str, Any]]
    support_resistance: Dict[str, float]
    volatility_analysis: Dict[str, float]
    momentum_analysis: Dict[str, float]
    volume_analysis: Dict[str, Any]
    ai_insights: Dict[str, Any]
    confidence_score: float
    trade_signals: List[Dict[str, Any]]


@dataclass
class Pattern:
    """Detected pattern information"""
    pattern_type: PatternType
    start_time: datetime
    end_time: datetime
    confidence: float
    price_target: Optional[float]
    stop_loss: Optional[float]
    description: str


@dataclass
class TrendAnalysis:
    """Trend analysis results"""
    direction: str  # UP, DOWN, SIDEWAYS
    strength: TrendStrength
    duration: int  # bars
    angle: float  # degrees
    momentum: float
    health_score: float
    reversal_probability: float


class SpyderX02_MarketAnalysisAgent:
    """
    AI-Enhanced Market Analysis Agent
    
    Combines traditional technical analysis with AI pattern recognition
    and context-aware market interpretation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Market Analysis Agent"""
        self.config = config or self._default_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.get('openai_api_key'))
        self.logger = self._setup_logging()
        
        # Analysis parameters
        self.lookback_periods = {
            'short': 20,
            'medium': 50,
            'long': 200
        }
        
        # Market data cache
        self.market_data_cache = {}
        self.analysis_cache = {}
        self.pattern_history = deque(maxlen=100)
        
        # Initialize components
        self.pattern_detector = PatternDetector()
        self.regime_analyzer = RegimeAnalyzer()
        self.support_resistance_finder = SupportResistanceFinder()
        
        # Performance tracking
        self.prediction_accuracy = deque(maxlen=100)
        
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            'min_pattern_confidence': 0.7,
            'regime_lookback': 50,
            'volume_threshold': 1.5,
            'ai_temperature': 0.7,
            'max_cache_age': 300,  # 5 minutes
            'update_interval': 60   # 1 minute
        }
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    async def analyze_market(self, 
                           symbol: str = 'SPY',
                           timeframe: str = '5min') -> MarketAnalysis:
        """
        Perform comprehensive market analysis
        
        Args:
            symbol: Trading symbol
            timeframe: Analysis timeframe
            
        Returns:
            Complete market analysis
        """
        try:
            # Get market data
            market_data = await self._get_market_data(symbol, timeframe)
            
            # Parallel analysis tasks
            tasks = [
                self._analyze_regime(market_data),
                self._analyze_trend(market_data),
                self._detect_patterns(market_data),
                self._find_support_resistance(market_data),
                self._analyze_volatility(market_data),
                self._analyze_momentum(market_data),
                self._analyze_volume(market_data)
            ]
            
            results = await asyncio.gather(*tasks)
            
            regime, trend, patterns, sr_levels, volatility, momentum, volume = results
            
            # Get AI insights
            ai_insights = await self._get_ai_insights(
                regime, trend, patterns, sr_levels, volatility, momentum, volume
            )
            
            # Generate trade signals
            trade_signals = await self._generate_trade_signals(
                regime, trend, patterns, sr_levels, ai_insights
            )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                regime, trend, patterns, volatility
            )
            
            analysis = MarketAnalysis(
                timestamp=datetime.now(),
                regime=regime,
                trend=trend,
                patterns=patterns,
                support_resistance=sr_levels,
                volatility_analysis=volatility,
                momentum_analysis=momentum,
                volume_analysis=volume,
                ai_insights=ai_insights,
                confidence_score=confidence,
                trade_signals=trade_signals
            )
            
            # Cache the analysis
            self.analysis_cache[symbol] = analysis
            
            self.logger.info(f"Market analysis completed for {symbol}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Market analysis error: {str(e)}")
            raise
    
    async def _get_market_data(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Get market data with caching"""
        cache_key = f"{symbol}_{timeframe}"
        
        # Check cache
        if cache_key in self.market_data_cache:
            cached_data, timestamp = self.market_data_cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.config['max_cache_age']:
                return cached_data
        
        # Fetch new data (placeholder - integrate with data provider)
        # In production, this would connect to your data feed
        data = pd.DataFrame()  # Replace with actual data fetching
        
        # Cache the data
        self.market_data_cache[cache_key] = (data, datetime.now())
        
        return data
    
    async def _analyze_regime(self, data: pd.DataFrame) -> MarketRegime:
        """Analyze current market regime"""
        return await self.regime_analyzer.analyze(data)
    
    async def _analyze_trend(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze market trend"""
        try:
            # Calculate trend indicators
            sma_short = talib.SMA(data['close'], timeperiod=self.lookback_periods['short'])
            sma_medium = talib.SMA(data['close'], timeperiod=self.lookback_periods['medium'])
            sma_long = talib.SMA(data['close'], timeperiod=self.lookback_periods['long'])
            
            # ADX for trend strength
            adx = talib.ADX(data['high'], data['low'], data['close'])
            
            # Determine trend direction
            current_price = data['close'].iloc[-1]
            
            if current_price > sma_short.iloc[-1] > sma_medium.iloc[-1] > sma_long.iloc[-1]:
                direction = "UP"
                strength = TrendStrength.STRONG if adx.iloc[-1] > 25 else TrendStrength.MODERATE
            elif current_price < sma_short.iloc[-1] < sma_medium.iloc[-1] < sma_long.iloc[-1]:
                direction = "DOWN"
                strength = TrendStrength.STRONG if adx.iloc[-1] > 25 else TrendStrength.MODERATE
            else:
                direction = "SIDEWAYS"
                strength = TrendStrength.NEUTRAL
            
            # Calculate trend angle
            trend_slope = np.polyfit(range(20), data['close'].tail(20), 1)[0]
            angle = np.degrees(np.arctan(trend_slope))
            
            # Momentum
            rsi = talib.RSI(data['close'])
            momentum = rsi.iloc[-1]
            
            # Health score (0-100)
            health_score = self._calculate_trend_health(data, sma_short, sma_medium, sma_long)
            
            # Reversal probability
            reversal_prob = self._calculate_reversal_probability(data, momentum, adx)
            
            return {
                'direction': direction,
                'strength': strength,
                'duration': self._calculate_trend_duration(data, direction),
                'angle': angle,
                'momentum': momentum,
                'health_score': health_score,
                'reversal_probability': reversal_prob,
                'key_levels': {
                    'sma_short': sma_short.iloc[-1],
                    'sma_medium': sma_medium.iloc[-1],
                    'sma_long': sma_long.iloc[-1]
                }
            }
            
        except Exception as e:
            self.logger.error(f"Trend analysis error: {str(e)}")
            return {}
    
    async def _detect_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect technical patterns"""
        patterns = await self.pattern_detector.detect_all_patterns(data)
        
        # Filter by confidence
        filtered_patterns = [
            p for p in patterns 
            if p['confidence'] >= self.config['min_pattern_confidence']
        ]
        
        # Add to history
        for pattern in filtered_patterns:
            self.pattern_history.append(pattern)
        
        return filtered_patterns
    
    async def _find_support_resistance(self, data: pd.DataFrame) -> Dict[str, float]:
        """Find support and resistance levels"""
        return await self.support_resistance_finder.find_levels(data)
    
    async def _analyze_volatility(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze market volatility"""
        try:
            # Historical volatility
            returns = data['close'].pct_change()
            hist_vol = returns.std() * np.sqrt(252)  # Annualized
            
            # ATR
            atr = talib.ATR(data['high'], data['low'], data['close'])
            current_atr = atr.iloc[-1]
            
            # Bollinger Bands
            upper, middle, lower = talib.BBANDS(data['close'])
            bb_width = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1]
            
            # Volatility regime
            vol_percentile = stats.percentileofscore(
                returns.rolling(252).std() * np.sqrt(252),
                hist_vol
            )
            
            return {
                'historical_volatility': hist_vol,
                'atr': current_atr,
                'atr_percentage': current_atr / data['close'].iloc[-1],
                'bollinger_width': bb_width,
                'volatility_percentile': vol_percentile,
                'volatility_trend': self._analyze_volatility_trend(atr),
                'is_volatile': vol_percentile > 75
            }
            
        except Exception as e:
            self.logger.error(f"Volatility analysis error: {str(e)}")
            return {}
    
    async def _analyze_momentum(self, data: pd.DataFrame) -> Dict[str, float]:
        """Analyze market momentum"""
        try:
            # RSI
            rsi = talib.RSI(data['close'])
            
            # MACD
            macd, signal, hist = talib.MACD(data['close'])
            
            # Stochastic
            slowk, slowd = talib.STOCH(data['high'], data['low'], data['close'])
            
            # Williams %R
            willr = talib.WILLR(data['high'], data['low'], data['close'])
            
            # Money Flow Index
            mfi = talib.MFI(data['high'], data['low'], data['close'], data['volume'])
            
            return {
                'rsi': rsi.iloc[-1],
                'rsi_trend': 'bullish' if rsi.iloc[-1] > rsi.iloc[-5] else 'bearish',
                'macd': macd.iloc[-1],
                'macd_signal': signal.iloc[-1],
                'macd_histogram': hist.iloc[-1],
                'macd_cross': self._detect_macd_cross(macd, signal),
                'stochastic_k': slowk.iloc[-1],
                'stochastic_d': slowd.iloc[-1],
                'williams_r': willr.iloc[-1],
                'mfi': mfi.iloc[-1],
                'momentum_score': self._calculate_momentum_score(
                    rsi.iloc[-1], macd.iloc[-1], hist.iloc[-1], mfi.iloc[-1]
                )
            }
            
        except Exception as e:
            self.logger.error(f"Momentum analysis error: {str(e)}")
            return {}
    
    async def _analyze_volume(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volume patterns"""
        try:
            volume = data['volume']
            
            # Volume moving averages
            vol_sma = talib.SMA(volume, timeperiod=20)
            
            # Current volume vs average
            vol_ratio = volume.iloc[-1] / vol_sma.iloc[-1]
            
            # On-Balance Volume
            obv = talib.OBV(data['close'], volume)
            
            # Volume trend
            vol_trend = 'increasing' if volume.tail(5).mean() > vol_sma.iloc[-1] else 'decreasing'
            
            # Accumulation/Distribution
            ad = talib.AD(data['high'], data['low'], data['close'], volume)
            
            return {
                'current_volume': volume.iloc[-1],
                'average_volume': vol_sma.iloc[-1],
                'volume_ratio': vol_ratio,
                'volume_trend': vol_trend,
                'obv': obv.iloc[-1],
                'obv_trend': 'bullish' if obv.iloc[-1] > obv.iloc[-5] else 'bearish',
                'accumulation_distribution': ad.iloc[-1],
                'is_high_volume': vol_ratio > self.config['volume_threshold'],
                'volume_profile': self._analyze_volume_profile(data)
            }
            
        except Exception as e:
            self.logger.error(f"Volume analysis error: {str(e)}")
            return {}
    
    async def _get_ai_insights(self, regime: MarketRegime, trend: Dict,
                              patterns: List[Dict], sr_levels: Dict,
                              volatility: Dict, momentum: Dict,
                              volume: Dict) -> Dict[str, Any]:
        """Get AI-powered insights"""
        try:
            # Prepare context for AI
            context = {
                'regime': regime.value,
                'trend': trend,
                'patterns': patterns[:5],  # Top 5 patterns
                'support_resistance': sr_levels,
                'volatility': volatility,
                'momentum': momentum,
                'volume': volume
            }
            
            prompt = f"""
            Analyze the following SPY market data and provide insights:
            
            Market Context:
            {json.dumps(context, indent=2)}
            
            Provide:
            1. Market interpretation
            2. Key observations
            3. Risk factors
            4. Opportunity assessment
            5. Recommended strategy approach
            
            Be specific and actionable.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert market analyst specializing in SPY options trading."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config['ai_temperature']
            )
            
            insights_text = response.choices[0].message.content
            
            # Parse AI response
            insights = self._parse_ai_insights(insights_text)
            
            return {
                'interpretation': insights.get('interpretation', ''),
                'key_observations': insights.get('observations', []),
                'risk_factors': insights.get('risks', []),
                'opportunities': insights.get('opportunities', []),
                'strategy_recommendation': insights.get('strategy', ''),
                'confidence': self._assess_ai_confidence(insights)
            }
            
        except Exception as e:
            self.logger.error(f"AI insights error: {str(e)}")
            return {
                'interpretation': 'Unable to generate AI insights',
                'key_observations': [],
                'risk_factors': [],
                'opportunities': [],
                'strategy_recommendation': 'Use traditional analysis',
                'confidence': 0.5
            }
    
    async def _generate_trade_signals(self, regime: MarketRegime,
                                    trend: Dict, patterns: List[Dict],
                                    sr_levels: Dict, ai_insights: Dict) -> List[Dict[str, Any]]:
        """Generate actionable trade signals"""
        signals = []
        
        try:
            # Trend-following signals
            if trend['direction'] == 'UP' and trend['strength'] in [TrendStrength.STRONG, TrendStrength.MODERATE]:
                signals.append({
                    'type': 'BULLISH',
                    'strategy': 'TREND_FOLLOWING',
                    'action': 'BUY_CALLS',
                    'confidence': trend['health_score'] / 100,
                    'reason': f"Strong uptrend with {trend['strength'].value} strength",
                    'risk_level': 'MODERATE'
                })
            
            # Pattern-based signals
            for pattern in patterns[:3]:  # Top 3 patterns
                if pattern['pattern_type'] in ['DOUBLE_BOTTOM', 'CUP_HANDLE']:
                    signals.append({
                        'type': 'BULLISH',
                        'strategy': 'PATTERN_BREAKOUT',
                        'action': 'BUY_CALLS',
                        'confidence': pattern['confidence'],
                        'reason': f"{pattern['pattern_type']} pattern detected",
                        'target': pattern.get('price_target'),
                        'stop_loss': pattern.get('stop_loss'),
                        'risk_level': 'MODERATE'
                    })
            
            # Support/Resistance signals
            current_price = sr_levels.get('current_price', 0)
            nearest_support = sr_levels.get('nearest_support', 0)
            nearest_resistance = sr_levels.get('nearest_resistance', 0)
            
            if current_price and nearest_support:
                support_distance = (current_price - nearest_support) / current_price
                if support_distance < 0.01:  # Within 1% of support
                    signals.append({
                        'type': 'BULLISH',
                        'strategy': 'SUPPORT_BOUNCE',
                        'action': 'BUY_CALLS',
                        'confidence': 0.7,
                        'reason': 'Price near strong support level',
                        'target': nearest_resistance,
                        'stop_loss': nearest_support * 0.995,
                        'risk_level': 'LOW'
                    })
            
            # Volatility-based signals
            if volatility.get('is_volatile') and regime == MarketRegime.SQUEEZE:
                signals.append({
                    'type': 'NEUTRAL',
                    'strategy': 'VOLATILITY_BREAKOUT',
                    'action': 'STRADDLE',
                    'confidence': 0.65,
                    'reason': 'Volatility squeeze detected - breakout expected',
                    'risk_level': 'HIGH'
                })
            
            # Sort by confidence
            signals.sort(key=lambda x: x['confidence'], reverse=True)
            
            return signals[:5]  # Top 5 signals
            
        except Exception as e:
            self.logger.error(f"Signal generation error: {str(e)}")
            return []
    
    def _calculate_confidence(self, regime: MarketRegime, trend: Dict,
                            patterns: List[Dict], volatility: Dict) -> float:
        """Calculate overall analysis confidence"""
        confidence_scores = []
        
        # Regime confidence
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            confidence_scores.append(0.8)
        elif regime == MarketRegime.RANGING:
            confidence_scores.append(0.7)
        else:
            confidence_scores.append(0.6)
        
        # Trend confidence
        if trend.get('health_score', 0) > 70:
            confidence_scores.append(0.85)
        elif trend.get('health_score', 0) > 50:
            confidence_scores.append(0.7)
        else:
            confidence_scores.append(0.5)
        
        # Pattern confidence
        if patterns:
            avg_pattern_confidence = np.mean([p['confidence'] for p in patterns[:3]])
            confidence_scores.append(avg_pattern_confidence)
        
        # Volatility confidence
        if not volatility.get('is_volatile', False):
            confidence_scores.append(0.8)
        else:
            confidence_scores.append(0.6)
        
        return np.mean(confidence_scores)
    
    def _calculate_trend_health(self, data: pd.DataFrame, sma_short: pd.Series,
                              sma_medium: pd.Series, sma_long: pd.Series) -> float:
        """Calculate trend health score (0-100)"""
        score = 0
        
        # Moving average alignment
        if sma_short.iloc[-1] > sma_medium.iloc[-1] > sma_long.iloc[-1]:
            score += 30
        elif sma_short.iloc[-1] < sma_medium.iloc[-1] < sma_long.iloc[-1]:
            score += 30
        
        # Price above/below MAs
        current_price = data['close'].iloc[-1]
        if current_price > sma_short.iloc[-1]:
            score += 20
        
        # Trend consistency
        price_changes = data['close'].pct_change().tail(20)
        if price_changes.mean() > 0 and price_changes.std() < 0.02:
            score += 30
        
        # Volume confirmation
        volume_trend = data['volume'].tail(5).mean() > data['volume'].tail(20).mean()
        if volume_trend:
            score += 20
        
        return min(score, 100)
    
    def _calculate_reversal_probability(self, data: pd.DataFrame,
                                      momentum: float, adx: pd.Series) -> float:
        """Calculate probability of trend reversal"""
        prob = 0.0
        
        # Extreme RSI
        if momentum > 70 or momentum < 30:
            prob += 0.3
        
        # Weakening trend (ADX declining)
        if adx.iloc[-1] < adx.iloc[-5]:
            prob += 0.2
        
        # Divergence detection would go here
        # Price making new highs but momentum not confirming
        
        # Volume divergence
        price_trend = data['close'].tail(10).pct_change().mean()
        volume_trend = data['volume'].tail(10).pct_change().mean()
        if (price_trend > 0 and volume_trend < 0) or (price_trend < 0 and volume_trend > 0):
            prob += 0.2
        
        return min(prob, 0.9)
    
    def _calculate_trend_duration(self, data: pd.DataFrame, direction: str) -> int:
        """Calculate how long the current trend has been in place"""
        # Simplified - in production would be more sophisticated
        return 20  # placeholder
    
    def _analyze_volatility_trend(self, atr: pd.Series) -> str:
        """Analyze volatility trend"""
        recent_atr = atr.tail(5).mean()
        older_atr = atr.tail(20).mean()
        
        if recent_atr > older_atr * 1.2:
            return "expanding"
        elif recent_atr < older_atr * 0.8:
            return "contracting"
        else:
            return "stable"
    
    def _detect_macd_cross(self, macd: pd.Series, signal: pd.Series) -> Optional[str]:
        """Detect MACD crossovers"""
        if len(macd) < 2 or len(signal) < 2:
            return None
        
        # Check for crossover in last 2 bars
        if macd.iloc[-2] < signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]:
            return "bullish_cross"
        elif macd.iloc[-2] > signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]:
            return "bearish_cross"
        
        return None
    
    def _calculate_momentum_score(self, rsi: float, macd: float,
                                macd_hist: float, mfi: float) -> float:
        """Calculate overall momentum score (0-100)"""
        score = 0
        
        # RSI component
        if 40 < rsi < 60:
            score += 25  # Neutral
        elif rsi > 60:
            score += 25 * ((rsi - 50) / 50)  # Bullish
        else:
            score += 25 * ((50 - rsi) / 50)  # Bearish adjustment
        
        # MACD component
        if macd > 0:
            score += 25
        if macd_hist > 0:
            score += 25
        
        # MFI component
        if mfi > 50:
            score += 25 * ((mfi - 50) / 50)
        
        return min(score, 100)
    
    def _analyze_volume_profile(self, data: pd.DataFrame) -> str:
        """Analyze volume profile"""
        # Simplified volume profile analysis
        recent_volume = data['volume'].tail(20)
        
        if recent_volume.iloc[-1] > recent_volume.mean() * 2:
            return "climactic"
        elif recent_volume.iloc[-1] > recent_volume.mean() * 1.5:
            return "elevated"
        elif recent_volume.iloc[-1] < recent_volume.mean() * 0.5:
            return "low"
        else:
            return "normal"
    
    def _parse_ai_insights(self, insights_text: str) -> Dict[str, Any]:
        """Parse AI insights from text response"""
        # In production, this would use more sophisticated parsing
        # For now, return structured placeholder
        return {
            'interpretation': insights_text[:200],
            'observations': ['Key observation 1', 'Key observation 2'],
            'risks': ['Risk factor 1', 'Risk factor 2'],
            'opportunities': ['Opportunity 1', 'Opportunity 2'],
            'strategy': 'Recommended strategy based on analysis'
        }
    
    def _assess_ai_confidence(self, insights: Dict[str, Any]) -> float:
        """Assess confidence in AI insights"""
        # Simplified confidence assessment
        if insights.get('interpretation') and insights.get('strategy'):
            return 0.85
        return 0.5


class PatternDetector:
    """Advanced pattern detection using AI and traditional methods"""
    
    async def detect_all_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect all types of patterns"""
        patterns = []
        
        # Classic chart patterns
        patterns.extend(await self._detect_chart_patterns(data))
        
        # Candlestick patterns
        patterns.extend(await self._detect_candlestick_patterns(data))
        
        # Advanced patterns
        patterns.extend(await self._detect_advanced_patterns(data))
        
        return patterns
    
    async def _detect_chart_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect classic chart patterns"""
        patterns = []
        
        # Head and Shoulders
        if self._is_head_shoulders(data):
            patterns.append({
                'pattern_type': 'HEAD_SHOULDERS',
                'confidence': 0.75,
                'start_time': data.index[-30],
                'end_time': data.index[-1],
                'description': 'Bearish reversal pattern detected'
            })
        
        # Double Top/Bottom
        double_pattern = self._detect_double_patterns(data)
        if double_pattern:
            patterns.append(double_pattern)
        
        return patterns
    
    async def _detect_candlestick_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect candlestick patterns using TA-Lib"""
        patterns = []
        
        # Doji
        doji = talib.CDLDOJI(data['open'], data['high'], data['low'], data['close'])
        if doji.iloc[-1] != 0:
            patterns.append({
                'pattern_type': 'DOJI',
                'confidence': 0.8,
                'time': data.index[-1],
                'description': 'Indecision pattern - potential reversal'
            })
        
        # Hammer
        hammer = talib.CDLHAMMER(data['open'], data['high'], data['low'], data['close'])
        if hammer.iloc[-1] != 0:
            patterns.append({
                'pattern_type': 'HAMMER',
                'confidence': 0.75,
                'time': data.index[-1],
                'description': 'Bullish reversal pattern'
            })
        
        return patterns
    
    async def _detect_advanced_patterns(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect advanced patterns like Elliott Waves, Harmonics"""
        patterns = []
        
        # Simplified Elliott Wave detection
        # In production, this would be much more sophisticated
        
        return patterns
    
    def _is_head_shoulders(self, data: pd.DataFrame) -> bool:
        """Detect head and shoulders pattern"""
        # Simplified detection logic
        if len(data) < 30:
            return False
        
        prices = data['close'].tail(30)
        
        # Find peaks
        peaks = []
        for i in range(1, len(prices) - 1):
            if prices.iloc[i] > prices.iloc[i-1] and prices.iloc[i] > prices.iloc[i+1]:
                peaks.append((i, prices.iloc[i]))
        
        # Check for head and shoulders structure
        if len(peaks) >= 3:
            # Middle peak should be highest (head)
            middle_peak = peaks[len(peaks)//2]
            if all(middle_peak[1] > p[1] for i, p in enumerate(peaks) if i != len(peaks)//2):
                return True
        
        return False
    
    def _detect_double_patterns(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Detect double top/bottom patterns"""
        # Simplified detection
        return None


class RegimeAnalyzer:
    """Market regime detection and analysis"""
    
    async def analyze(self, data: pd.DataFrame) -> MarketRegime:
        """Analyze and classify market regime"""
        
        # Calculate indicators for regime detection
        returns = data['close'].pct_change()
        volatility = returns.std()
        trend_strength = self._calculate_trend_strength(data)
        
        # Price action analysis
        recent_high = data['high'].tail(20).max()
        recent_low = data['low'].tail(20).min()
        current_price = data['close'].iloc[-1]
        
        price_position = (current_price - recent_low) / (recent_high - recent_low)
        
        # Classify regime
        if trend_strength > 0.7 and price_position > 0.8:
            return MarketRegime.TRENDING_UP
        elif trend_strength > 0.7 and price_position < 0.2:
            return MarketRegime.TRENDING_DOWN
        elif volatility > data['close'].pct_change().rolling(50).std().mean() * 2:
            return MarketRegime.VOLATILE
        elif (recent_high - recent_low) / current_price < 0.02:
            return MarketRegime.SQUEEZE
        elif price_position > 0.95 and returns.tail(5).mean() > returns.std() * 2:
            return MarketRegime.PARABOLIC
        elif price_position < 0.05 and returns.tail(5).mean() < -returns.std() * 2:
            return MarketRegime.CRASH
        else:
            return MarketRegime.RANGING
    
    def _calculate_trend_strength(self, data: pd.DataFrame) -> float:
        """Calculate trend strength (0-1)"""
        adx = talib.ADX(data['high'], data['low'], data['close'])
        return min(adx.iloc[-1] / 50, 1.0) if not adx.empty else 0.5


class SupportResistanceFinder:
    """Find key support and resistance levels"""
    
    async def find_levels(self, data: pd.DataFrame) -> Dict[str, float]:
        """Find support and resistance levels"""
        levels = {}
        
        # Current price
        current_price = data['close'].iloc[-1]
        levels['current_price'] = current_price
        
        # Find pivot points
        pivots = self._calculate_pivot_points(data)
        levels.update(pivots)
        
        # Find historical levels
        historical_levels = self._find_historical_levels(data)
        levels.update(historical_levels)
        
        # Find nearest levels
        all_levels = [v for k, v in levels.items() if k != 'current_price']
        support_levels = [l for l in all_levels if l < current_price]
        resistance_levels = [l for l in all_levels if l > current_price]
        
        if support_levels:
            levels['nearest_support'] = max(support_levels)
        if resistance_levels:
            levels['nearest_resistance'] = min(resistance_levels)
        
        return levels
    
    def _calculate_pivot_points(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate pivot points"""
        high = data['high'].iloc[-1]
        low = data['low'].iloc[-1]
        close = data['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        
        return {
            'pivot': pivot,
            'r1': 2 * pivot - low,
            'r2': pivot + (high - low),
            's1': 2 * pivot - high,
            's2': pivot - (high - low)
        }
    
    def _find_historical_levels(self, data: pd.DataFrame) -> Dict[str, float]:
        """Find historical support/resistance levels"""
        levels = {}
        
        # Find recent highs and lows
        lookback = min(len(data), 100)
        recent_data = data.tail(lookback)
        
        # Cluster analysis for key levels
        prices = recent_data[['high', 'low']].values.flatten()
        
        # Simple clustering (in production, use more sophisticated methods)
        kmeans = KMeans(n_clusters=min(5, len(prices)//10))
        kmeans.fit(prices.reshape(-1, 1))
        
        key_levels = sorted(kmeans.cluster_centers_.flatten())
        
        for i, level in enumerate(key_levels):
            levels[f'historical_{i+1}'] = level
        
        return levels


# Main execution
async def main():
    """Example usage of Market Analysis Agent"""
    
    # Initialize agent
    agent = SpyderX02_MarketAnalysisAgent()
    
    # Perform analysis
    analysis = await agent.analyze_market('SPY', '5min')
    
    # Print results
    print(f"Market Regime: {analysis.regime.value}")
    print(f"Trend: {analysis.trend['direction']} - {analysis.trend['strength'].value}")
    print(f"Confidence: {analysis.confidence_score:.2%}")
    
    print("\nTop Trade Signals:")
    for signal in analysis.trade_signals[:3]:
        print(f"- {signal['action']}: {signal['reason']} (Confidence: {signal['confidence']:.2%})")
    
    print("\nAI Insights:")
    print(f"Interpretation: {analysis.ai_insights['interpretation']}")
    print(f"Strategy: {analysis.ai_insights['strategy_recommendation']}")


if __name__ == "__main__":
    asyncio.run(main())
