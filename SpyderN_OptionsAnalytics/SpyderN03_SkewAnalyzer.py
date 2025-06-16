#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN03_SkewAnalyzer.py
Group: N (Options Analytics)
Purpose: Volatility skew analysis

Description:
    This module analyzes volatility skew patterns to assess market sentiment and
    identify potential regime changes. It tracks put-call skew, risk reversal
    indicators, and generates trading signals based on skew anomalies. The module
    is crucial for risk assessment and directional bias detection.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: PRODUCTION - Fully implemented
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum, auto
import numpy as np
import threading
from collections import deque
import time
import bisect
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from scipy import stats, interpolate
from scipy.optimize import minimize_scalar

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Skew calculation parameters
STANDARD_DELTAS = [0.10, 0.25, 0.50, 0.75, 0.90]  # Delta levels for skew curve
SKEW_WINDOW_SIZE = 100  # Historical data points for percentile calculation
MIN_VOLUME_THRESHOLD = 10  # Minimum volume for reliable IV
MIN_OI_THRESHOLD = 50  # Minimum open interest

# Skew thresholds
SKEW_NORMAL_RANGE = (-0.05, 0.05)  # Normal skew range
SKEW_WARNING_THRESHOLD = 0.10  # Warning level
SKEW_EXTREME_THRESHOLD = 0.15  # Extreme skew level

# Risk reversal parameters
RR_25_DELTA = 0.25  # Standard 25-delta risk reversal
BUTTERFLY_25_DELTA = 0.25  # Standard 25-delta butterfly

# ==============================================================================
# ENUMS
# ==============================================================================
class SkewType(Enum):
    """Types of volatility skew."""
    NORMAL = "normal"
    STEEP_PUT = "steep_put"
    STEEP_CALL = "steep_call"
    FLAT = "flat"
    INVERTED = "inverted"

class MarketSentiment(Enum):
    """Market sentiment based on skew."""
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"

class SkewRegime(Enum):
    """Skew regime classification."""
    CRASH_FEAR = "crash_fear"  # High put skew (normal market)
    COMPLACENT = "complacent"  # Low/flat skew
    SQUEEZE_RISK = "squeeze_risk"  # High call skew
    TRANSITIONING = "transitioning"  # Changing regime

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SkewPoint:
    """Single point on the skew curve."""
    strike: float
    delta: float
    implied_vol: float
    moneyness: float  # Strike/Spot
    volume: int
    open_interest: int
    bid_ask_spread: float

@dataclass
class SkewMetrics:
    """Comprehensive volatility skew metrics."""
    timestamp: datetime
    underlying_price: float
    atm_iv: float
    
    # Skew measurements
    put_call_skew: float  # 25 delta put IV - 25 delta call IV
    risk_reversal_25: float  # 25 delta RR
    risk_reversal_10: float  # 10 delta RR (tail risk)
    butterfly_25: float  # 25 delta butterfly
    
    # Skew curve parameters
    skew_slope: float  # Linear regression slope
    skew_curvature: float  # Second derivative at ATM
    skew_type: SkewType
    
    # Market assessment
    sentiment: MarketSentiment
    regime: SkewRegime
    percentile_rank: float  # Historical percentile (0-100)
    z_score: float  # Standard deviations from mean
    
    # Quality metrics
    data_points: int
    r_squared: float  # Fit quality
    
    # Additional analytics
    term_structure: Optional[Dict[int, float]] = None  # DTE -> skew
    strike_profile: Optional[List[SkewPoint]] = None

@dataclass
class SkewSignal:
    """Trading signal based on skew analysis."""
    timestamp: datetime
    signal_type: str  # 'directional', 'volatility', 'spread'
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # 0-1
    confidence: float  # 0-1
    
    # Strategy recommendation
    strategy_suggestion: str
    entry_timing: str  # 'immediate', 'wait_confirmation', 'scale_in'
    
    # Risk parameters
    suggested_size: float  # Position size multiplier
    stop_loss_adjustment: float  # Adjustment factor
    
    # Detailed reasoning
    rationale: str
    supporting_metrics: Dict[str, float]

# ==============================================================================
# SKEW ANALYZER CLASS
# ==============================================================================
class SkewAnalyzer:
    """
    Analyzes volatility skew for market sentiment and trading signals.
    
    This class provides comprehensive skew analysis including real-time
    calculation, historical comparison, regime detection, and signal generation.
    It integrates directly with market data feeds for live analysis.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the skew analyzer.
        
        Args:
            symbol: Underlying symbol to analyze
        """
        self.symbol = symbol
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data sources
        self.option_chain_mgr = OptionChainManager()
        self.data_feed_mgr = DataFeedManager.get_instance()
        self.event_manager = get_event_manager()
        
        # Historical data storage
        self.skew_history: deque = deque(maxlen=SKEW_WINDOW_SIZE * 10)
        self.metrics_cache: deque = deque(maxlen=SKEW_WINDOW_SIZE)
        self.signal_history: List[SkewSignal] = []
        
        # Current state
        self.current_metrics: Optional[SkewMetrics] = None
        self.current_regime: SkewRegime = SkewRegime.CRASH_FEAR
        
        # Threading for continuous monitoring
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()
        
        # Calibration parameters
        self.calibration_params = {
            'skew_smoothing': 0.1,
            'regime_threshold': 0.7,
            'signal_threshold': 0.8
        }
        
        self.logger.info(f"SkewAnalyzer initialized for {symbol}")
        
    # ==========================================================================
    # MAIN ANALYSIS METHODS
    # ==========================================================================
    def calculate_skew(self, option_chain: pd.DataFrame) -> SkewMetrics:
        """
        Calculate current skew metrics from option chain.
        
        Args:
            option_chain: DataFrame with option data
            
        Returns:
            SkewMetrics object with comprehensive analysis
        """
        try:
            # Filter for liquid options
            chain = self._filter_liquid_options(option_chain)
            
            if chain.empty:
                raise ValueError("No liquid options available for skew calculation")
            
            # Get underlying price
            underlying_price = chain['underlying_price'].iloc[0]
            
            # Calculate implied volatilities by delta
            iv_by_delta = self._calculate_iv_by_delta(chain, underlying_price)
            
            # Calculate skew metrics
            atm_iv = self._get_atm_iv(chain, underlying_price)
            put_call_skew = self._calculate_put_call_skew(iv_by_delta)
            risk_reversal_25 = self._calculate_risk_reversal(iv_by_delta, 0.25)
            risk_reversal_10 = self._calculate_risk_reversal(iv_by_delta, 0.10)
            butterfly_25 = self._calculate_butterfly(iv_by_delta, 0.25)
            
            # Fit skew curve and get parameters
            skew_params = self._fit_skew_curve(chain, underlying_price)
            
            # Classify skew type and sentiment
            skew_type = self._classify_skew_type(put_call_skew, skew_params['slope'])
            sentiment = self._assess_market_sentiment(put_call_skew, risk_reversal_25)
            regime = self._detect_skew_regime(put_call_skew, butterfly_25, atm_iv)
            
            # Calculate historical metrics
            percentile_rank = self._calculate_percentile_rank(put_call_skew)
            z_score = self._calculate_z_score(put_call_skew)
            
            # Create strike profile
            strike_profile = self._create_strike_profile(chain, underlying_price)
            
            # Build metrics object
            metrics = SkewMetrics(
                timestamp=datetime.now(),
                underlying_price=underlying_price,
                atm_iv=atm_iv,
                put_call_skew=put_call_skew,
                risk_reversal_25=risk_reversal_25,
                risk_reversal_10=risk_reversal_10,
                butterfly_25=butterfly_25,
                skew_slope=skew_params['slope'],
                skew_curvature=skew_params['curvature'],
                skew_type=skew_type,
                sentiment=sentiment,
                regime=regime,
                percentile_rank=percentile_rank,
                z_score=z_score,
                data_points=len(chain),
                r_squared=skew_params['r_squared'],
                strike_profile=strike_profile
            )
            
            # Update cache
            with self._lock:
                self.current_metrics = metrics
                self.metrics_cache.append(metrics)
                
            # Emit event
            self._emit_skew_update(metrics)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating skew: {e}")
            self.error_handler.handle_error(e, {"method": "calculate_skew"})
            raise
            
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_skew_signals(self, 
                            skew_metrics: Optional[SkewMetrics] = None,
                            market_data: Optional[Dict[str, Any]] = None) -> List[SkewSignal]:
        """
        Generate trading signals based on skew analysis.
        
        Args:
            skew_metrics: Current skew metrics (uses cached if None)
            market_data: Additional market data for context
            
        Returns:
            List of trading signals
        """
        if skew_metrics is None:
            skew_metrics = self.current_metrics
            
        if skew_metrics is None:
            self.logger.warning("No skew metrics available for signal generation")
            return []
            
        signals = []
        
        # Check for extreme skew conditions
        if abs(skew_metrics.put_call_skew) > SKEW_EXTREME_THRESHOLD:
            signal = self._generate_extreme_skew_signal(skew_metrics)
            if signal:
                signals.append(signal)
                
        # Check for regime transitions
        if skew_metrics.regime == SkewRegime.TRANSITIONING:
            signal = self._generate_regime_change_signal(skew_metrics)
            if signal:
                signals.append(signal)
                
        # Check for divergences
        divergence = self._detect_skew_divergence()
        if divergence:
            signal = self._generate_divergence_signal(divergence, skew_metrics)
            if signal:
                signals.append(signal)
                
        # Check for mean reversion opportunities
        if abs(skew_metrics.z_score) > 2.0:
            signal = self._generate_mean_reversion_signal(skew_metrics)
            if signal:
                signals.append(signal)
                
        # Store signals
        self.signal_history.extend(signals)
        
        return signals
        
    # ==========================================================================
    # PRIVATE CALCULATION METHODS
    # ==========================================================================
    def _filter_liquid_options(self, option_chain: pd.DataFrame) -> pd.DataFrame:
        """Filter options for sufficient liquidity."""
        return option_chain[
            (option_chain['volume'] >= MIN_VOLUME_THRESHOLD) |
            (option_chain['open_interest'] >= MIN_OI_THRESHOLD)
        ].copy()
        
    def _calculate_iv_by_delta(self, 
                              chain: pd.DataFrame, 
                              spot: float) -> Dict[float, Dict[str, float]]:
        """Calculate IV for standard delta levels."""
        iv_by_delta = {}
        
        for delta in STANDARD_DELTAS:
            # Find puts and calls near target delta
            put_iv = self._find_iv_for_delta(chain, spot, delta, 'PUT')
            call_iv = self._find_iv_for_delta(chain, spot, 1 - delta, 'CALL')
            
            iv_by_delta[delta] = {
                'put': put_iv,
                'call': call_iv
            }
            
        return iv_by_delta
        
    def _find_iv_for_delta(self, 
                          chain: pd.DataFrame, 
                          spot: float,
                          target_delta: float,
                          option_type: str) -> float:
        """Find IV for specific delta using interpolation."""
        # Filter for option type
        options = chain[chain['type'] == option_type].copy()
        
        if options.empty:
            return np.nan
            
        # Calculate deltas if not provided
        if 'delta' not in options.columns:
            options['delta'] = options.apply(
                lambda x: self._calculate_delta(spot, x['strike'], x['tte'], 
                                              x['implied_volatility'], option_type),
                axis=1
            )
            
        # Sort by delta
        options = options.sort_values('delta')
        
        # Interpolate to find IV at target delta
        if len(options) < 2:
            return options.iloc[0]['implied_volatility']
            
        return np.interp(target_delta, 
                        options['delta'].values, 
                        options['implied_volatility'].values)
                        
    def _calculate_delta(self, S: float, K: float, T: float, 
                        sigma: float, option_type: str) -> float:
        """Calculate option delta using Black-Scholes."""
        r = 0.05  # Risk-free rate assumption
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        
        if option_type == 'CALL':
            return stats.norm.cdf(d1)
        else:
            return stats.norm.cdf(d1) - 1
            
    def _get_atm_iv(self, chain: pd.DataFrame, spot: float) -> float:
        """Get at-the-money implied volatility."""
        # Find closest strike to spot
        chain['distance'] = abs(chain['strike'] - spot)
        atm_options = chain.nsmallest(2, 'distance')
        
        return atm_options['implied_volatility'].mean()
        
    def _calculate_put_call_skew(self, iv_by_delta: Dict[float, Dict[str, float]]) -> float:
        """Calculate 25-delta put-call skew."""
        if 0.25 not in iv_by_delta:
            return 0.0
            
        put_iv = iv_by_delta[0.25]['put']
        call_iv = iv_by_delta[0.25]['call']
        
        if np.isnan(put_iv) or np.isnan(call_iv):
            return 0.0
            
        return put_iv - call_iv
        
    def _calculate_risk_reversal(self, 
                                iv_by_delta: Dict[float, Dict[str, float]], 
                                delta: float) -> float:
        """Calculate risk reversal for given delta."""
        if delta not in iv_by_delta:
            return 0.0
            
        put_iv = iv_by_delta[delta]['put']
        call_iv = iv_by_delta[delta]['call']
        
        if np.isnan(put_iv) or np.isnan(call_iv):
            return 0.0
            
        return (put_iv - call_iv) / 2
        
    def _calculate_butterfly(self, 
                           iv_by_delta: Dict[float, Dict[str, float]], 
                           delta: float) -> float:
        """Calculate butterfly spread for given delta."""
        if delta not in iv_by_delta or 0.50 not in iv_by_delta:
            return 0.0
            
        put_iv = iv_by_delta[delta]['put']
        call_iv = iv_by_delta[delta]['call']
        atm_iv = (iv_by_delta[0.50]['put'] + iv_by_delta[0.50]['call']) / 2
        
        if np.isnan(put_iv) or np.isnan(call_iv) or np.isnan(atm_iv):
            return 0.0
            
        return ((put_iv + call_iv) / 2) - atm_iv
        
    def _fit_skew_curve(self, chain: pd.DataFrame, spot: float) -> Dict[str, float]:
        """Fit polynomial to skew curve and extract parameters."""
        # Calculate moneyness and filter
        chain['moneyness'] = chain['strike'] / spot
        chain = chain[(chain['moneyness'] > 0.8) & (chain['moneyness'] < 1.2)]
        
        if len(chain) < 5:
            return {'slope': 0.0, 'curvature': 0.0, 'r_squared': 0.0}
            
        # Fit second-order polynomial
        x = chain['moneyness'].values
        y = chain['implied_volatility'].values
        
        coeffs = np.polyfit(x, y, 2)
        poly = np.poly1d(coeffs)
        
        # Calculate R-squared
        y_fit = poly(x)
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Extract parameters
        slope = coeffs[1]  # First derivative at x=1 (ATM)
        curvature = 2 * coeffs[0]  # Second derivative
        
        return {
            'slope': slope,
            'curvature': curvature,
            'r_squared': r_squared
        }
        
    def _classify_skew_type(self, put_call_skew: float, slope: float) -> SkewType:
        """Classify the type of skew."""
        if abs(put_call_skew) < 0.02:
            return SkewType.FLAT
        elif put_call_skew > SKEW_WARNING_THRESHOLD:
            return SkewType.STEEP_PUT
        elif put_call_skew < -SKEW_WARNING_THRESHOLD:
            return SkewType.STEEP_CALL
        elif slope < 0:
            return SkewType.NORMAL
        else:
            return SkewType.INVERTED
            
    def _assess_market_sentiment(self, put_call_skew: float, rr_25: float) -> MarketSentiment:
        """Assess market sentiment from skew metrics."""
        # Combined score from multiple metrics
        score = put_call_skew * 0.7 + rr_25 * 0.3
        
        if score > 0.10:
            return MarketSentiment.VERY_BEARISH
        elif score > 0.05:
            return MarketSentiment.BEARISH
        elif score < -0.10:
            return MarketSentiment.VERY_BULLISH
        elif score < -0.05:
            return MarketSentiment.BULLISH
        else:
            return MarketSentiment.NEUTRAL
            
    def _detect_skew_regime(self, 
                          put_call_skew: float, 
                          butterfly: float,
                          atm_iv: float) -> SkewRegime:
        """Detect current skew regime."""
        # Check for regime characteristics
        if put_call_skew > 0.08 and butterfly > 0.02:
            return SkewRegime.CRASH_FEAR
        elif abs(put_call_skew) < 0.03 and butterfly < 0.01:
            return SkewRegime.COMPLACENT
        elif put_call_skew < -0.05:
            return SkewRegime.SQUEEZE_RISK
        else:
            # Check if transitioning
            if len(self.metrics_cache) > 10:
                recent_skews = [m.put_call_skew for m in list(self.metrics_cache)[-10:]]
                if np.std(recent_skews) > 0.03:
                    return SkewRegime.TRANSITIONING
                    
        return SkewRegime.CRASH_FEAR  # Default
        
    def _calculate_percentile_rank(self, put_call_skew: float) -> float:
        """Calculate historical percentile rank of current skew."""
        if len(self.metrics_cache) < 20:
            return 50.0
            
        historical_skews = [m.put_call_skew for m in self.metrics_cache]
        return stats.percentileofscore(historical_skews, put_call_skew)
        
    def _calculate_z_score(self, put_call_skew: float) -> float:
        """Calculate z-score of current skew."""
        if len(self.metrics_cache) < 20:
            return 0.0
            
        historical_skews = [m.put_call_skew for m in self.metrics_cache]
        mean = np.mean(historical_skews)
        std = np.std(historical_skews)
        
        if std == 0:
            return 0.0
            
        return (put_call_skew - mean) / std
        
    def _create_strike_profile(self, chain: pd.DataFrame, spot: float) -> List[SkewPoint]:
        """Create detailed strike profile."""
        profile = []
        
        for _, row in chain.iterrows():
            profile.append(SkewPoint(
                strike=row['strike'],
                delta=row.get('delta', 0.0),
                implied_vol=row['implied_volatility'],
                moneyness=row['strike'] / spot,
                volume=row['volume'],
                open_interest=row['open_interest'],
                bid_ask_spread=row.get('ask', 0) - row.get('bid', 0)
            ))
            
        return sorted(profile, key=lambda x: x.strike)
        
    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    def _generate_extreme_skew_signal(self, metrics: SkewMetrics) -> Optional[SkewSignal]:
        """Generate signal for extreme skew conditions."""
        if abs(metrics.put_call_skew) < SKEW_EXTREME_THRESHOLD:
            return None
            
        # Determine direction and strategy
        if metrics.put_call_skew > SKEW_EXTREME_THRESHOLD:
            # Extreme put skew - potential bounce
            direction = "bullish"
            strategy = "Bull Put Spread or Long Call Spread"
            rationale = f"Extreme put skew ({metrics.put_call_skew:.3f}) suggests oversold conditions"
        else:
            # Extreme call skew - potential pullback
            direction = "bearish"
            strategy = "Bear Call Spread or Long Put Spread"
            rationale = f"Extreme call skew ({metrics.put_call_skew:.3f}) suggests overbought conditions"
            
        return SkewSignal(
            timestamp=datetime.now(),
            signal_type="directional",
            direction=direction,
            strength=min(abs(metrics.put_call_skew) / 0.20, 1.0),
            confidence=0.7 + (0.3 * metrics.r_squared),
            strategy_suggestion=strategy,
            entry_timing="wait_confirmation",
            suggested_size=0.5,  # Half size due to extreme conditions
            stop_loss_adjustment=1.5,  # Wider stops
            rationale=rationale,
            supporting_metrics={
                'skew': metrics.put_call_skew,
                'percentile': metrics.percentile_rank,
                'z_score': metrics.z_score
            }
        )
        
    def _generate_regime_change_signal(self, metrics: SkewMetrics) -> Optional[SkewSignal]:
        """Generate signal for regime transitions."""
        if metrics.regime != SkewRegime.TRANSITIONING:
            return None
            
        # Analyze transition direction
        recent_metrics = list(self.metrics_cache)[-20:]
        if len(recent_metrics) < 20:
            return None
            
        # Check trend in skew
        skew_trend = np.polyfit(range(len(recent_metrics)), 
                               [m.put_call_skew for m in recent_metrics], 1)[0]
                               
        if skew_trend > 0.002:
            # Increasing skew - becoming more bearish
            direction = "bearish"
            strategy = "Long Volatility - Straddle or Iron Condor"
            rationale = "Skew regime transitioning to higher fear levels"
        else:
            # Decreasing skew - becoming more bullish
            direction = "bullish"
            strategy = "Short Volatility - Iron Condor or Calendar Spread"
            rationale = "Skew regime transitioning to complacency"
            
        return SkewSignal(
            timestamp=datetime.now(),
            signal_type="volatility",
            direction=direction,
            strength=0.6,
            confidence=0.65,
            strategy_suggestion=strategy,
            entry_timing="scale_in",
            suggested_size=0.7,
            stop_loss_adjustment=1.2,
            rationale=rationale,
            supporting_metrics={
                'skew_trend': skew_trend,
                'regime': metrics.regime.value,
                'butterfly': metrics.butterfly_25
            }
        )
        
    def _detect_skew_divergence(self) -> Optional[Dict[str, Any]]:
        """Detect divergence between price and skew."""
        if len(self.metrics_cache) < 20:
            return None
            
        # Get recent data
        recent_metrics = list(self.metrics_cache)[-20:]
        prices = [m.underlying_price for m in recent_metrics]
        skews = [m.put_call_skew for m in recent_metrics]
        
        # Calculate trends
        price_trend = np.polyfit(range(len(prices)), prices, 1)[0]
        skew_trend = np.polyfit(range(len(skews)), skews, 1)[0]
        
        # Normalize trends
        price_trend_norm = price_trend / np.mean(prices)
        
        # Check for divergence
        if price_trend_norm > 0.001 and skew_trend < -0.001:
            # Price up, skew down - bullish divergence
            return {
                'type': 'bullish_divergence',
                'strength': abs(price_trend_norm - skew_trend),
                'price_trend': 'up',
                'skew_trend': 'down'
            }
        elif price_trend_norm < -0.001 and skew_trend > 0.001:
            # Price down, skew up - bearish divergence
            return {
                'type': 'bearish_divergence',
                'strength': abs(price_trend_norm - skew_trend),
                'price_trend': 'down',
                'skew_trend': 'up'
            }
            
        return None
        
    def _generate_divergence_signal(self, 
                                  divergence: Dict[str, Any],
                                  metrics: SkewMetrics) -> Optional[SkewSignal]:
        """Generate signal from divergence."""
        if divergence['type'] == 'bullish_divergence':
            direction = "bullish"
            strategy = "Long Delta - Call Spreads or Put Sales"
            rationale = "Price rising while skew declining suggests strength"
        else:
            direction = "bearish"
            strategy = "Short Delta - Put Spreads or Call Sales"
            rationale = "Price falling while skew rising suggests weakness"
            
        return SkewSignal(
            timestamp=datetime.now(),
            signal_type="directional",
            direction=direction,
            strength=min(divergence['strength'] * 10, 1.0),
            confidence=0.75,
            strategy_suggestion=strategy,
            entry_timing="immediate",
            suggested_size=0.8,
            stop_loss_adjustment=1.0,
            rationale=rationale,
            supporting_metrics={
                'divergence_type': divergence['type'],
                'divergence_strength': divergence['strength'],
                'current_skew': metrics.put_call_skew
            }
        )
        
    def _generate_mean_reversion_signal(self, metrics: SkewMetrics) -> Optional[SkewSignal]:
        """Generate mean reversion signal for extreme z-scores."""
        if abs(metrics.z_score) < 2.0:
            return None
            
        if metrics.z_score > 2.0:
            # Skew too high - expect reversion down
            direction = "neutral"
            strategy = "Sell Put Spreads or Risk Reversals"
            rationale = f"Skew z-score of {metrics.z_score:.2f} suggests mean reversion"
        else:
            # Skew too low - expect reversion up
            direction = "neutral"
            strategy = "Buy Put Spreads or Risk Reversals"
            rationale = f"Skew z-score of {metrics.z_score:.2f} suggests mean reversion"
            
        return SkewSignal(
            timestamp=datetime.now(),
            signal_type="spread",
            direction=direction,
            strength=min(abs(metrics.z_score) / 3.0, 1.0),
            confidence=0.8,
            strategy_suggestion=strategy,
            entry_timing="scale_in",
            suggested_size=0.6,
            stop_loss_adjustment=1.3,
            rationale=rationale,
            supporting_metrics={
                'z_score': metrics.z_score,
                'percentile': metrics.percentile_rank,
                'mean_skew': np.mean([m.put_call_skew for m in self.metrics_cache])
            }
        )
        
    # ==========================================================================
    # EVENT AND MONITORING
    # ==========================================================================
    def _emit_skew_update(self, metrics: SkewMetrics) -> None:
        """Emit skew update event."""
        event = Event(
            type=EventType.ANALYTICS,
            data={
                'type': 'skew_update',
                'symbol': self.symbol,
                'skew': metrics.put_call_skew,
                'sentiment': metrics.sentiment.value,
                'regime': metrics.regime.value,
                'percentile': metrics.percentile_rank
            }
        )
        self.event_manager.emit(event)
        
    def start_monitoring(self, update_interval: int = 60) -> None:
        """Start continuous skew monitoring."""
        if self._running:
            self.logger.warning("Skew monitoring already running")
            return
            
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(update_interval,),
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info(f"Started skew monitoring with {update_interval}s interval")
        
    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("Stopped skew monitoring")
        
    def _monitor_loop(self, interval: int) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Get latest option chain
                chain = self.option_chain_mgr.get_option_chain(self.symbol)
                
                if chain is not None and not chain.empty:
                    # Calculate skew
                    metrics = self.calculate_skew(chain)
                    
                    # Generate signals
                    signals = self.generate_skew_signals(metrics)
                    
                    # Emit signals
                    for signal in signals:
                        self._emit_signal(signal)
                        
            except Exception as e:
                self.logger.error(f"Error in skew monitor loop: {e}")
                
            time.sleep(interval)
            
    def _emit_signal(self, signal: SkewSignal) -> None:
        """Emit trading signal event."""
        event = Event(
            type=EventType.SIGNAL,
            data={
                'source': 'skew_analyzer',
                'signal': signal.__dict__
            }
        )
        self.event_manager.emit(event)
        
    # ==========================================================================
    # PUBLIC INTERFACE METHODS
    # ==========================================================================
    def get_current_metrics(self) -> Optional[SkewMetrics]:
        """Get current skew metrics."""
        with self._lock:
            return self.current_metrics
            
    def get_skew_history(self, lookback_periods: int = 100) -> List[SkewMetrics]:
        """Get historical skew metrics."""
        with self._lock:
            return list(self.metrics_cache)[-lookback_periods:]
            
    def get_signal_history(self, lookback_periods: int = 50) -> List[SkewSignal]:
        """Get historical signals."""
        return self.signal_history[-lookback_periods:]
        
    def get_skew_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive skew dashboard data."""
        metrics = self.current_metrics
        
        if metrics is None:
            return {
                'status': 'no_data',
                'message': 'No skew data available'
            }
            
        return {
            'status': 'active',
            'timestamp': metrics.timestamp.isoformat(),
            'underlying_price': metrics.underlying_price,
            'current_skew': {
                'value': metrics.put_call_skew,
                'percentile': metrics.percentile_rank,
                'z_score': metrics.z_score,
                'type': metrics.skew_type.value
            },
            'risk_metrics': {
                'risk_reversal_25': metrics.risk_reversal_25,
                'risk_reversal_10': metrics.risk_reversal_10,
                'butterfly_25': metrics.butterfly_25
            },
            'market_assessment': {
                'sentiment': metrics.sentiment.value,
                'regime': metrics.regime.value,
                'confidence': metrics.r_squared
            },
            'signals': [
                {
                    'time': s.timestamp.isoformat(),
                    'type': s.signal_type,
                    'direction': s.direction,
                    'strength': s.strength,
                    'strategy': s.strategy_suggestion
                }
                for s in self.signal_history[-5:]
            ]
        }

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'SkewAnalyzer',
    'SkewMetrics',
    'SkewSignal',
    'SkewType',
    'MarketSentiment',
    'SkewRegime'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the skew analyzer
    analyzer = SkewAnalyzer("SPY")
    
    print("="*60)
    print("SPYDER - Skew Analyzer Test")
    print("="*60)
    
    # Start monitoring
    analyzer.start_monitoring(update_interval=30)
    
    print("\nSkew Analyzer started successfully!")
    print("Monitoring SPY options skew...")
    print("\nPress Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(10)
            
            # Print current status
            dashboard = analyzer.get_skew_dashboard()
            if dashboard['status'] == 'active':
                print(f"\nSkew Update: {dashboard['current_skew']['value']:.3f} "
                      f"(Percentile: {dashboard['current_skew']['percentile']:.1f}%)")
                print(f"Sentiment: {dashboard['market_assessment']['sentiment']}")
                
    except KeyboardInterrupt:
        print("\n\nStopping skew analyzer...")
        analyzer.stop_monitoring()
        print("Done!")
