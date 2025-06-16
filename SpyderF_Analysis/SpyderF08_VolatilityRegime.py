#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF08_VolatilityRegime.py
Group: F (Analysis)
Purpose: Volatility regime classification and analysis

Description:
    This module analyzes and classifies the current volatility regime to help
    determine optimal trading strategies. It tracks VIX levels, implied volatility
    percentiles, and historical volatility patterns to categorize market conditions
    as low, normal, high, or extreme volatility environments.

Author: Mohamed Talib
Date: 2025-06-06
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import threading
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VIX thresholds
VIX_LOW_THRESHOLD = 15
VIX_NORMAL_THRESHOLD = 20
VIX_HIGH_THRESHOLD = 30
VIX_EXTREME_THRESHOLD = 40

# Historical volatility periods
HV_LOOKBACK_PERIODS = [10, 20, 30, 60]  # Days

# IV percentile lookback
IV_PERCENTILE_LOOKBACK = 252  # 1 year

# Regime change thresholds
REGIME_CHANGE_THRESHOLD = 0.8  # 80% confidence required

# Update intervals
REGIME_UPDATE_INTERVAL = 300  # 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    TRANSITIONING = "transitioning"

class RegimeStrength(Enum):
    """Regime strength levels"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RegimeAnalysis:
    """Volatility regime analysis results"""
    timestamp: datetime
    current_regime: VolatilityRegime
    regime_strength: RegimeStrength
    vix_level: float
    vix_percentile: float
    iv_percentile: float
    hv_10d: float
    hv_20d: float
    hv_30d: float
    realized_vs_implied: float  # RV/IV ratio
    regime_confidence: float
    transition_probability: Dict[VolatilityRegime, float]
    recommended_strategies: List[str]
    position_size_adjustment: float
    notes: List[str]

@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics"""
    vix_current: float
    vix_change_1d: float
    vix_change_5d: float
    vix_sma_10: float
    vix_sma_20: float
    term_structure_slope: float  # VIX9D/VIX slope
    put_call_iv_spread: float
    skew_index: float
    correlation_spy_vix: float

# ==============================================================================
# VOLATILITY REGIME ANALYZER CLASS
# ==============================================================================
class VolatilityRegimeAnalyzer:
    """
    Analyzes and classifies volatility regimes for strategy selection.
    
    Features:
    - Real-time VIX monitoring
    - IV percentile calculation
    - Historical volatility analysis
    - Regime transition detection
    - Strategy recommendations
    - Position sizing adjustments
    """
    
    def __init__(self, event_manager: EventManager, data_feed=None):
        """
        Initialize volatility regime analyzer.
        
        Args:
            event_manager: Event manager instance
            data_feed: Market data feed for real-time updates
        """
        self.event_manager = event_manager
        self.data_feed = data_feed
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Current state
        self.current_regime = VolatilityRegime.NORMAL
        self.current_analysis: Optional[RegimeAnalysis] = None
        self.volatility_metrics: Optional[VolatilityMetrics] = None
        
        # Historical data storage
        self.vix_history: List[Tuple[datetime, float]] = []
        self.iv_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.regime_history: List[Tuple[datetime, VolatilityRegime]] = []
        
        # VIX thresholds
        self.vix_thresholds = {
            'low': VIX_LOW_THRESHOLD,
            'normal': VIX_NORMAL_THRESHOLD,
            'high': VIX_HIGH_THRESHOLD,
            'extreme': VIX_EXTREME_THRESHOLD
        }
        
        # Strategy recommendations by regime
        self.regime_strategies = {
            VolatilityRegime.LOW: [
                "iron_butterfly",  # Benefit from low vol
                "calendar_spread",  # Vol expansion play
                "diagonal_spread"
            ],
            VolatilityRegime.NORMAL: [
                "iron_condor",     # Standard premium collection
                "credit_spread",   # Directional with protection
                "butterfly"
            ],
            VolatilityRegime.HIGH: [
                "credit_spread",   # Wider strikes
                "iron_condor",     # Adjusted for high IV
                "ratio_spread"     # Skew plays
            ],
            VolatilityRegime.EXTREME: [
                "debit_spread",    # Limited risk
                "butterfly",       # Defined risk
                "defensive_puts"   # Portfolio protection
            ]
        }
        
        # Threading
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        self._data_lock = threading.RLock()
        
        self.logger.info("VolatilityRegimeAnalyzer initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start volatility regime monitoring"""
        if self._running:
            return
        
        self._running = True
        
        # Load historical data
        self._load_historical_data()
        
        # Start update thread
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="VolRegimeUpdater"
        )
        self._update_thread.start()
        
        # Initial analysis
        self.analyze_current_regime()
        
        self.logger.info("Volatility regime analyzer started")
    
    def stop(self) -> None:
        """Stop volatility regime monitoring"""
        self._running = False
        
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
        
        self.logger.info("Volatility regime analyzer stopped")
    
    # ==========================================================================
    # REGIME ANALYSIS
    # ==========================================================================
    def analyze_current_regime(self) -> RegimeAnalysis:
        """
        Perform comprehensive volatility regime analysis.
        
        Returns:
            RegimeAnalysis object with current assessment
        """
        try:
            # Get current metrics
            metrics = self._calculate_volatility_metrics()
            
            # Classify regime
            regime = self._classify_regime(metrics)
            
            # Calculate regime strength
            strength = self._calculate_regime_strength(metrics, regime)
            
            # Calculate confidence
            confidence = self._calculate_confidence(metrics, regime)
            
            # Get transition probabilities
            transitions = self._calculate_transition_probabilities(metrics)
            
            # Get recommendations
            strategies = self._get_strategy_recommendations(regime, metrics)
            position_adjustment = self._calculate_position_adjustment(regime, strength)
            
            # Generate notes
            notes = self._generate_analysis_notes(metrics, regime)
            
            # Create analysis
            analysis = RegimeAnalysis(
                timestamp=datetime.now(),
                current_regime=regime,
                regime_strength=strength,
                vix_level=metrics.vix_current,
                vix_percentile=self._calculate_vix_percentile(metrics.vix_current),
                iv_percentile=self._calculate_iv_percentile('SPY'),
                hv_10d=self._calculate_historical_volatility(10),
                hv_20d=self._calculate_historical_volatility(20),
                hv_30d=self._calculate_historical_volatility(30),
                realized_vs_implied=self._calculate_rv_iv_ratio(),
                regime_confidence=confidence,
                transition_probability=transitions,
                recommended_strategies=strategies,
                position_size_adjustment=position_adjustment,
                notes=notes
            )
            
            # Update state
            with self._data_lock:
                self.current_regime = regime
                self.current_analysis = analysis
                self._add_to_history(regime)
            
            # Emit event
            self._emit_regime_event(analysis)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing regime: {e}")
            self.error_handler.handle_error(e, "analyze_regime")
            return self._get_default_analysis()
    
    def _classify_regime(self, metrics: VolatilityMetrics) -> VolatilityRegime:
        """Classify current volatility regime"""
        vix = metrics.vix_current
        
        # Check for regime transitions
        if self._is_transitioning(metrics):
            return VolatilityRegime.TRANSITIONING
        
        # Classify based on VIX levels
        if vix >= self.vix_thresholds['extreme']:
            return VolatilityRegime.EXTREME
        elif vix >= self.vix_thresholds['high']:
            return VolatilityRegime.HIGH
        elif vix >= self.vix_thresholds['normal']:
            return VolatilityRegime.NORMAL
        else:
            return VolatilityRegime.LOW
    
    def _calculate_regime_strength(self, metrics: VolatilityMetrics, 
                                   regime: VolatilityRegime) -> RegimeStrength:
        """Calculate strength of current regime"""
        # Factors to consider
        factors = []
        
        # VIX level relative to regime boundaries
        vix_strength = self._calculate_vix_strength(metrics.vix_current, regime)
        factors.append(vix_strength)
        
        # Trend consistency
        trend_strength = self._calculate_trend_strength(metrics)
        factors.append(trend_strength)
        
        # Term structure
        term_strength = self._calculate_term_structure_strength(metrics)
        factors.append(term_strength)
        
        # Average strength
        avg_strength = np.mean(factors)
        
        if avg_strength >= 0.75:
            return RegimeStrength.VERY_STRONG
        elif avg_strength >= 0.5:
            return RegimeStrength.STRONG
        elif avg_strength >= 0.25:
            return RegimeStrength.MODERATE
        else:
            return RegimeStrength.WEAK
    
    def _calculate_confidence(self, metrics: VolatilityMetrics, 
                             regime: VolatilityRegime) -> float:
        """Calculate confidence in regime classification"""
        confidence_factors = []
        
        # Clear VIX level
        if regime == VolatilityRegime.EXTREME and metrics.vix_current > 40:
            confidence_factors.append(0.9)
        elif regime == VolatilityRegime.LOW and metrics.vix_current < 12:
            confidence_factors.append(0.9)
        else:
            # Distance from boundaries
            boundary_confidence = self._calculate_boundary_confidence(
                metrics.vix_current, regime
            )
            confidence_factors.append(boundary_confidence)
        
        # Trend agreement
        if metrics.vix_sma_10 > metrics.vix_sma_20:  # Uptrend
            if regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.4)
        else:  # Downtrend
            if regime in [VolatilityRegime.LOW, VolatilityRegime.NORMAL]:
                confidence_factors.append(0.8)
            else:
                confidence_factors.append(0.4)
        
        # Historical consistency
        hist_consistency = self._calculate_historical_consistency(regime)
        confidence_factors.append(hist_consistency)
        
        return np.mean(confidence_factors)
    
    # ==========================================================================
    # METRICS CALCULATION
    # ==========================================================================
    def _calculate_volatility_metrics(self) -> VolatilityMetrics:
        """Calculate comprehensive volatility metrics"""
        # Get current VIX
        vix_current = self._get_current_vix()
        
        # Calculate changes
        vix_change_1d = self._calculate_vix_change(1)
        vix_change_5d = self._calculate_vix_change(5)
        
        # Moving averages
        vix_sma_10 = self._calculate_vix_sma(10)
        vix_sma_20 = self._calculate_vix_sma(20)
        
        # Term structure
        term_slope = self._calculate_term_structure_slope()
        
        # IV spreads
        pc_spread = self._calculate_put_call_iv_spread()
        
        # Skew
        skew = self._calculate_skew_index()
        
        # Correlation
        correlation = self._calculate_spy_vix_correlation()
        
        return VolatilityMetrics(
            vix_current=vix_current,
            vix_change_1d=vix_change_1d,
            vix_change_5d=vix_change_5d,
            vix_sma_10=vix_sma_10,
            vix_sma_20=vix_sma_20,
            term_structure_slope=term_slope,
            put_call_iv_spread=pc_spread,
            skew_index=skew,
            correlation_spy_vix=correlation
        )
    
    def _calculate_vix_percentile(self, current_vix: float) -> float:
        """Calculate VIX percentile over historical period"""
        if not self.vix_history:
            return 50.0
        
        # Get last year of VIX values
        one_year_ago = datetime.now() - timedelta(days=365)
        historical_vix = [v for d, v in self.vix_history if d >= one_year_ago]
        
        if not historical_vix:
            return 50.0
        
        # Calculate percentile
        return stats.percentileofscore(historical_vix, current_vix)
    
    def get_iv_percentile(self, symbol: str, lookback_days: int = 252) -> float:
        """
        Calculate IV percentile for entry criteria.
        
        Args:
            symbol: Symbol to check (e.g., 'SPY')
            lookback_days: Days to look back for percentile
            
        Returns:
            IV percentile (0-100)
        """
        if symbol not in self.iv_history:
            return 50.0
        
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        historical_iv = [iv for d, iv in self.iv_history[symbol] if d >= cutoff_date]
        
        if not historical_iv or len(historical_iv) < 20:
            return 50.0
        
        current_iv = self._get_current_iv(symbol)
        if current_iv is None:
            return 50.0
        
        return stats.percentileofscore(historical_iv, current_iv)
    
    def _calculate_historical_volatility(self, days: int) -> float:
        """Calculate historical volatility over specified days"""
        if not self.data_feed:
            # Return placeholder
            return 0.15  # 15% annualized
        
        try:
            # Get price data
            prices = self.data_feed.get_historical_prices('SPY', days)
            if len(prices) < days:
                return 0.15
            
            # Calculate daily returns
            returns = np.diff(np.log(prices))
            
            # Calculate annualized volatility
            daily_vol = np.std(returns)
            annual_vol = daily_vol * np.sqrt(252)
            
            return annual_vol
            
        except Exception as e:
            self.logger.error(f"Error calculating HV: {e}")
            return 0.15
    
    def _calculate_rv_iv_ratio(self) -> float:
        """Calculate realized volatility to implied volatility ratio"""
        try:
            # Get 20-day realized vol
            rv_20 = self._calculate_historical_volatility(20)
            
            # Get current IV
            current_iv = self._get_current_iv('SPY')
            if current_iv is None or current_iv == 0:
                return 1.0
            
            return rv_20 / current_iv
            
        except Exception:
            return 1.0
    
    # ==========================================================================
    # TRANSITION DETECTION
    # ==========================================================================
    def _calculate_transition_probabilities(self, 
                                          metrics: VolatilityMetrics) -> Dict[VolatilityRegime, float]:
        """Calculate probability of transitioning to each regime"""
        probabilities = {}
        
        # Current VIX momentum
        momentum = (metrics.vix_current - metrics.vix_sma_20) / metrics.vix_sma_20
        
        # Term structure indication
        term_signal = metrics.term_structure_slope
        
        # Calculate probabilities for each regime
        for regime in VolatilityRegime:
            if regime == VolatilityRegime.TRANSITIONING:
                continue
            
            prob = self._calculate_regime_probability(
                metrics.vix_current, momentum, term_signal, regime
            )
            probabilities[regime] = prob
        
        # Normalize probabilities
        total = sum(probabilities.values())
        if total > 0:
            probabilities = {k: v/total for k, v in probabilities.items()}
        
        return probabilities
    
    def _is_transitioning(self, metrics: VolatilityMetrics) -> bool:
        """Check if regime is transitioning"""
        # Large VIX moves
        if abs(metrics.vix_change_1d) > 0.15:  # 15% daily change
            return True
        
        # Near boundaries
        for threshold in self.vix_thresholds.values():
            if abs(metrics.vix_current - threshold) < 1.0:  # Within 1 point
                return True
        
        # Diverging signals
        if self._has_diverging_signals(metrics):
            return True
        
        return False
    
    # ==========================================================================
    # STRATEGY RECOMMENDATIONS
    # ==========================================================================
    def _get_strategy_recommendations(self, regime: VolatilityRegime,
                                    metrics: VolatilityMetrics) -> List[str]:
        """Get recommended strategies for current regime"""
        base_strategies = self.regime_strategies.get(regime, [])
        
        # Adjust based on specific conditions
        adjusted_strategies = []
        
        for strategy in base_strategies:
            if self._is_strategy_suitable(strategy, regime, metrics):
                adjusted_strategies.append(strategy)
        
        # Add regime-specific adjustments
        if regime == VolatilityRegime.HIGH:
            # Add calendar spreads if term structure favorable
            if metrics.term_structure_slope > 0.1:
                adjusted_strategies.append("calendar_spread")
        
        elif regime == VolatilityRegime.LOW:
            # Consider naked puts in very low vol
            if metrics.vix_current < 12 and self._check_market_conditions():
                adjusted_strategies.append("cash_secured_put")
        
        return adjusted_strategies[:3]  # Top 3 recommendations
    
    def _calculate_position_adjustment(self, regime: VolatilityRegime,
                                     strength: RegimeStrength) -> float:
        """Calculate position size adjustment factor"""
        # Base adjustments by regime
        regime_factors = {
            VolatilityRegime.LOW: 1.2,      # Can be more aggressive
            VolatilityRegime.NORMAL: 1.0,   # Standard sizing
            VolatilityRegime.HIGH: 0.8,     # Reduce size
            VolatilityRegime.EXTREME: 0.5,  # Significant reduction
            VolatilityRegime.TRANSITIONING: 0.7  # Cautious
        }
        
        # Strength adjustments
        strength_factors = {
            RegimeStrength.VERY_STRONG: 1.1,
            RegimeStrength.STRONG: 1.0,
            RegimeStrength.MODERATE: 0.9,
            RegimeStrength.WEAK: 0.8
        }
        
        base_factor = regime_factors.get(regime, 1.0)
        strength_factor = strength_factors.get(strength, 1.0)
        
        return base_factor * strength_factor
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _get_current_vix(self) -> float:
        """Get current VIX level"""
        if self.data_feed:
            vix = self.data_feed.get_last_price('VIX')
            if vix:
                return vix
        
        # Fallback to last known or default
        if self.vix_history:
            return self.vix_history[-1][1]
        
        return 16.0  # Default normal VIX
    
    def _get_current_iv(self, symbol: str) -> Optional[float]:
        """Get current implied volatility for symbol"""
        if self.data_feed:
            return self.data_feed.get_atm_iv(symbol)
        return None
    
    def _calculate_vix_change(self, days: int) -> float:
        """Calculate VIX change over specified days"""
        if len(self.vix_history) < days + 1:
            return 0.0
        
        current = self.vix_history[-1][1]
        previous = self.vix_history[-(days+1)][1]
        
        if previous == 0:
            return 0.0
        
        return (current - previous) / previous
    
    def _calculate_vix_sma(self, period: int) -> float:
        """Calculate VIX simple moving average"""
        if len(self.vix_history) < period:
            return self._get_current_vix()
        
        values = [v for _, v in self.vix_history[-period:]]
        return np.mean(values)
    
    def _calculate_term_structure_slope(self) -> float:
        """Calculate VIX term structure slope"""
        if self.data_feed:
            vix9d = self.data_feed.get_last_price('VIX9D')
            vix = self.data_feed.get_last_price('VIX')
            
            if vix9d and vix and vix != 0:
                return (vix - vix9d) / vix
        
        return 0.0
    
    def _calculate_put_call_iv_spread(self) -> float:
        """Calculate put-call IV spread"""
        if self.data_feed:
            put_iv = self.data_feed.get_atm_iv('SPY', 'PUT')
            call_iv = self.data_feed.get_atm_iv('SPY', 'CALL')
            
            if put_iv and call_iv:
                return put_iv - call_iv
        
        return 0.0
    
    def _calculate_skew_index(self) -> float:
        """Calculate options skew index"""
        # Simplified skew calculation
        # In production, would use 25-delta put IV / ATM IV
        return 1.0
    
    def _calculate_spy_vix_correlation(self) -> float:
        """Calculate SPY-VIX correlation"""
        # Typically negative correlation
        # Simplified for now
        return -0.7
    
    def _calculate_vix_strength(self, vix: float, regime: VolatilityRegime) -> float:
        """Calculate VIX strength within regime"""
        if regime == VolatilityRegime.LOW:
            # Closer to 0 is stronger
            return max(0, (15 - vix) / 15)
        elif regime == VolatilityRegime.NORMAL:
            # Middle of range is strongest
            distance = abs(vix - 17.5) / 2.5
            return max(0, 1 - distance)
        elif regime == VolatilityRegime.HIGH:
            # Middle of range
            distance = abs(vix - 25) / 5
            return max(0, 1 - distance)
        else:  # EXTREME
            # Higher is stronger
            return min(1, (vix - 30) / 20)
    
    def _calculate_trend_strength(self, metrics: VolatilityMetrics) -> float:
        """Calculate trend consistency strength"""
        # Compare short and long MA
        if metrics.vix_sma_10 > metrics.vix_sma_20:
            # Uptrend
            return min(1, (metrics.vix_sma_10 - metrics.vix_sma_20) / metrics.vix_sma_20)
        else:
            # Downtrend
            return min(1, (metrics.vix_sma_20 - metrics.vix_sma_10) / metrics.vix_sma_20)
    
    def _calculate_term_structure_strength(self, metrics: VolatilityMetrics) -> float:
        """Calculate term structure signal strength"""
        return min(1, abs(metrics.term_structure_slope) * 5)
    
    def _calculate_boundary_confidence(self, vix: float, regime: VolatilityRegime) -> float:
        """Calculate confidence based on distance from regime boundaries"""
        distances = []
        
        for threshold in self.vix_thresholds.values():
            distance = abs(vix - threshold)
            distances.append(distance)
        
        min_distance = min(distances)
        
        # Further from boundaries = higher confidence
        return min(1, min_distance / 5)
    
    def _calculate_historical_consistency(self, regime: VolatilityRegime) -> float:
        """Calculate how consistent regime has been historically"""
        if len(self.regime_history) < 10:
            return 0.5
        
        # Check last 10 observations
        recent_regimes = [r for _, r in self.regime_history[-10:]]
        consistency = recent_regimes.count(regime) / len(recent_regimes)
        
        return consistency
    
    def _calculate_regime_probability(self, vix: float, momentum: float,
                                    term_signal: float, regime: VolatilityRegime) -> float:
        """Calculate probability of specific regime"""
        # Base probability from VIX level
        if regime == VolatilityRegime.LOW:
            base_prob = max(0, (15 - vix) / 15)
        elif regime == VolatilityRegime.NORMAL:
            base_prob = 1 - abs(vix - 17.5) / 10
        elif regime == VolatilityRegime.HIGH:
            base_prob = 1 - abs(vix - 25) / 10
        else:  # EXTREME
            base_prob = max(0, (vix - 30) / 20)
        
        base_prob = max(0, min(1, base_prob))
        
        # Adjust for momentum
        if momentum > 0:  # Rising VIX
            if regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
                base_prob *= 1.2
            else:
                base_prob *= 0.8
        else:  # Falling VIX
            if regime in [VolatilityRegime.LOW, VolatilityRegime.NORMAL]:
                base_prob *= 1.2
            else:
                base_prob *= 0.8
        
        return max(0, min(1, base_prob))
    
    def _has_diverging_signals(self, metrics: VolatilityMetrics) -> bool:
        """Check if signals are diverging"""
        divergences = 0
        
        # VIX vs moving average
        if (metrics.vix_current > metrics.vix_sma_20 and 
            metrics.vix_change_1d < 0):
            divergences += 1
        
        # Term structure vs spot
        if (metrics.term_structure_slope > 0.1 and 
            metrics.vix_current < 20):
            divergences += 1
        
        return divergences >= 2
    
    def _is_strategy_suitable(self, strategy: str, regime: VolatilityRegime,
                            metrics: VolatilityMetrics) -> bool:
        """Check if strategy is suitable for current conditions"""
        # Strategy-specific checks
        if strategy == "iron_condor":
            # Need reasonable IV
            return 15 <= metrics.vix_current <= 35
        
        elif strategy == "iron_butterfly":
            # Best in low vol
            return metrics.vix_current < 20
        
        elif strategy == "credit_spread":
            # Works in most regimes
            return True
        
        elif strategy == "calendar_spread":
            # Need positive term structure
            return metrics.term_structure_slope > 0
        
        return True
    
    def _check_market_conditions(self) -> bool:
        """Check overall market conditions"""
        # Simplified check - in production would be more comprehensive
        return True
    
    def _generate_analysis_notes(self, metrics: VolatilityMetrics,
                               regime: VolatilityRegime) -> List[str]:
        """Generate analysis notes"""
        notes = []
        
        # VIX level notes
        if metrics.vix_current > 35:
            notes.append("VIX above 35 - extreme caution advised")
        elif metrics.vix_current < 12:
            notes.append("VIX below 12 - potential complacency")
        
        # Trend notes
        if metrics.vix_change_5d > 0.25:
            notes.append("VIX up 25%+ in 5 days - volatility spike")
        elif metrics.vix_change_5d < -0.25:
            notes.append("VIX down 25%+ in 5 days - volatility crush")
        
        # Term structure
        if metrics.term_structure_slope > 0.2:
            notes.append("Steep contango - expect volatility to rise")
        elif metrics.term_structure_slope < -0.1:
            notes.append("Backwardation - near-term stress")
        
        # Regime-specific notes
        if regime == VolatilityRegime.TRANSITIONING:
            notes.append("Regime transitioning - reduce position sizes")
        
        return notes
    
    def _add_to_history(self, regime: VolatilityRegime) -> None:
        """Add regime to history"""
        self.regime_history.append((datetime.now(), regime))
        
        # Limit history size
        if len(self.regime_history) > 1000:
            self.regime_history = self.regime_history[-1000:]
    
    def _emit_regime_event(self, analysis: RegimeAnalysis) -> None:
        """Emit volatility regime event"""
        self.event_manager.emit(Event(
            EventType.ANALYSIS,
            {
                'type': 'volatility_regime',
                'regime': analysis.current_regime.value,
                'strength': analysis.regime_strength.value,
                'vix': analysis.vix_level,
                'iv_percentile': analysis.iv_percentile,
                'confidence': analysis.regime_confidence,
                'strategies': analysis.recommended_strategies,
                'position_adjustment': analysis.position_size_adjustment
            }
        ))
    
    def _get_default_analysis(self) -> RegimeAnalysis:
        """Get default analysis when error occurs"""
        return RegimeAnalysis(
            timestamp=datetime.now(),
            current_regime=VolatilityRegime.NORMAL,
            regime_strength=RegimeStrength.MODERATE,
            vix_level=16.0,
            vix_percentile=50.0,
            iv_percentile=50.0,
            hv_10d=0.15,
            hv_20d=0.15,
            hv_30d=0.15,
            realized_vs_implied=1.0,
            regime_confidence=0.5,
            transition_probability={
                VolatilityRegime.LOW: 0.25,
                VolatilityRegime.NORMAL: 0.5,
                VolatilityRegime.HIGH: 0.2,
                VolatilityRegime.EXTREME: 0.05
            },
            recommended_strategies=["iron_condor"],
            position_size_adjustment=1.0,
            notes=["Default analysis due to error"]
        )
    
    def _load_historical_data(self) -> None:
        """Load historical volatility data"""
        # In production, would load from database
        # For now, initialize with some recent data
        base_vix = 16.0
        for i in range(252):  # One year
            date = datetime.now() - timedelta(days=252-i)
            # Simulate some variation
            vix = base_vix + np.random.normal(0, 2)
            vix = max(10, min(50, vix))  # Bound between 10-50
            self.vix_history.append((date, vix))
    
    def _update_loop(self) -> None:
        """Background update loop"""
        while self._running:
            try:
                # Update current data
                current_vix = self._get_current_vix()
                self.vix_history.append((datetime.now(), current_vix))
                
                # Periodic full analysis
                self.analyze_current_regime()
                
                # Sleep
                time.sleep(REGIME_UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
                time.sleep(60)  # Wait a minute on error
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_current_regime(self) -> VolatilityRegime:
        """Get current volatility regime"""
        return self.current_regime
    
    def get_position_size_factor(self) -> float:
        """Get position sizing factor for current regime"""
        if self.current_analysis:
            return self.current_analysis.position_size_adjustment
        return 1.0
    
    def get_recommended_strategies(self) -> List[str]:
        """Get recommended strategies for current regime"""
        if self.current_analysis:
            return self.current_analysis.recommended_strategies
        return ["iron_condor"]  # Default
    
    def is_high_volatility(self) -> bool:
        """Check if currently in high volatility regime"""
        return self.current_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]
    
    def get_regime_analysis(self) -> Optional[RegimeAnalysis]:
        """Get latest regime analysis"""
        return self.current_analysis
    
    def update_vix_data(self, vix_value: float) -> None:
        """Update VIX data (for real-time feeds)"""
        with self._data_lock:
            self.vix_history.append((datetime.now(), vix_value))
            # Trim old data
            cutoff = datetime.now() - timedelta(days=365)
            self.vix_history = [(d, v) for d, v in self.vix_history if d > cutoff]
    
    def update_iv_data(self, symbol: str, iv_value: float) -> None:
        """Update IV data for a symbol"""
        with self._data_lock:
            if symbol not in self.iv_history:
                self.iv_history[symbol] = []
            
            self.iv_history[symbol].append((datetime.now(), iv_value))
            
            # Trim old data
            cutoff = datetime.now() - timedelta(days=365)
            self.iv_history[symbol] = [(d, v) for d, v in self.iv_history[symbol] 
                                       if d > cutoff]

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the volatility regime analyzer
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Create event manager
    event_manager = EventManager()
    
    # Create analyzer
    analyzer = VolatilityRegimeAnalyzer(event_manager)
    
    # Start analyzer
    analyzer.start()
    
    # Perform analysis
    print("Performing volatility regime analysis...")
    analysis = analyzer.analyze_current_regime()
    
    print(f"\nCurrent Regime: {analysis.current_regime.value}")
    print(f"Regime Strength: {analysis.regime_strength.value}")
    print(f"VIX Level: {analysis.vix_level:.2f}")
    print(f"VIX Percentile: {analysis.vix_percentile:.1f}%")
    print(f"IV Percentile: {analysis.iv_percentile:.1f}%")
    print(f"Confidence: {analysis.regime_confidence:.1%}")
    print(f"Position Size Adjustment: {analysis.position_size_adjustment:.2f}x")
    
    print("\nRecommended Strategies:")
    for strategy in analysis.recommended_strategies:
        print(f"  - {strategy}")
    
    print("\nTransition Probabilities:")
    for regime, prob in analysis.transition_probability.items():
        print(f"  {regime.value}: {prob:.1%}")
    
    print("\nNotes:")
    for note in analysis.notes:
        print(f"  - {note}")
    
    # Test IV percentile calculation
    print(f"\nSPY IV Percentile: {analyzer.get_iv_percentile('SPY'):.1f}%")
    
    # Stop analyzer
    analyzer.stop()
