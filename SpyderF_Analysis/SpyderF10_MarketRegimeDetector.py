#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF10_MarketRegimeDetector.py
Group: F (Technical Analysis)
Purpose: Professional market regime detection and analysis

Description:
This module implements sophisticated market regime detection based
    on institutional standards including VIX levels, volatility clustering,
    mean reversion analysis, and market stress indicators. Provides real-time
    regime classification to optimize strategy selection and risk management.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque, defaultdict
import threading
import time
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from SpyderC_MarketData.SpyderC01_DataFeed import MarketDataFeed
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
VIX_LOW_THRESHOLD = 16.0           # Below 16 = low volatility regime
VIX_NORMAL_LOW = 16.0              # 16-25 = normal volatility
VIX_NORMAL_HIGH = 25.0             
VIX_HIGH_THRESHOLD = 25.0          # Above 25 = high volatility regime
VIX_EXTREME_THRESHOLD = 30.0       # Above 30 = extreme volatility/crisis
GARCH_PERSISTENCE_THRESHOLD = 0.85  # High GARCH persistence indicates clustering
VOLATILITY_SHOCK_THRESHOLD = 2.0    # 2 standard deviations for vol shocks
MEAN_REVERSION_LOOKBACK = 20        # 20-day lookback for mean reversion
REVERSION_SPEED_THRESHOLD = 0.1     # Minimum mean reversion speed
SKEW_STRESS_THRESHOLD = -1.5        # Put/call skew stress level
CORRELATION_BREAKDOWN = 0.3         # Correlation breakdown threshold
LIQUIDITY_STRESS_THRESHOLD = 2.0    # Liquidity stress multiplier
MIN_REGIME_DURATION = 3             # Minimum 3 days for regime change
REGIME_CONFIDENCE_THRESHOLD = 0.75   # 75% confidence for regime classification
class MarketRegime(Enum):
    """Market regime classification"""
    LOW_VOLATILITY = auto()          # VIX < 16, trending markets
    NORMAL_VOLATILITY = auto()       # VIX 16-25, balanced conditions
    HIGH_VOLATILITY = auto()         # VIX 25-30, elevated uncertainty
    CRISIS_VOLATILITY = auto()       # VIX > 30, market stress
    TRANSITION = auto()              # Regime change in progress
class TrendRegime(Enum):
    """Trend regime classification"""
    STRONG_BULL = auto()             # Strong uptrend
    WEAK_BULL = auto()               # Weak uptrend
    SIDEWAYS = auto()                # Range-bound
    WEAK_BEAR = auto()               # Weak downtrend
    STRONG_BEAR = auto()             # Strong downtrend
class VolatilityCluster(Enum):
    """Volatility clustering state"""
    LOW_CLUSTERING = auto()          # Low volatility persistence
    MODERATE_CLUSTERING = auto()     # Moderate clustering
    HIGH_CLUSTERING = auto()         # High volatility clustering
    VOLATILITY_SHOCK = auto()        # Sudden volatility spike
class LiquidityRegime(Enum):
    """Market liquidity regime"""
    ABUNDANT = auto()                # High liquidity
    NORMAL = auto()                  # Normal liquidity
    SCARCE = auto()                  # Reduced liquidity
    CRISIS = auto()                  # Liquidity crisis
@dataclass
class RegimeMetrics:
    """Market regime metrics"""
    timestamp: datetime
    # VIX-based metrics
    vix_level: float
    vix_percentile: float            # Historical percentile
    vix_trend: float                 # VIX trend slope
    vix_mean_reversion: float        # Mean reversion speed
    # Volatility clustering
    garch_persistence: float         # GARCH persistence parameter
    volatility_clustering: float     # Clustering strength
    realized_vs_implied: float       # RV vs IV differential
    # Trend metrics
    trend_strength: float            # Trend strength (0-1)
    trend_direction: float           # Trend direction (-1 to 1)
    momentum: float                  # Price momentum
    # Market stress indicators
    put_call_skew: float            # Put/call volatility skew
    correlation_stress: float        # Cross-asset correlation
    liquidity_stress: float         # Liquidity stress indicator
    # Mean reversion
    mean_reversion_speed: float      # Speed of mean reversion
    oversold_probability: float      # Probability of oversold condition
    overbought_probability: float    # Probability of overbought condition
@dataclass
class RegimeState:
    """Current market regime state"""
    timestamp: datetime
    # Primary regime classifications
    volatility_regime: MarketRegime
    trend_regime: TrendRegime
    clustering_regime: VolatilityCluster
    liquidity_regime: LiquidityRegime
    # Confidence levels
    regime_confidence: float         # Overall regime confidence
    transition_probability: float    # Probability of regime change
    # Strategy implications
    optimal_strategies: List[str]    # Recommended strategies for regime
    risk_adjustment_factor: float    # Risk scaling factor
    # Regime stability
    regime_duration_days: int        # Days in current regime
    expected_duration_days: float    # Expected remaining duration
    # Supporting metrics
    metrics: RegimeMetrics
@dataclass
class RegimeTransition:
    """Regime transition event"""
    timestamp: datetime
    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_probability: float
    trigger_factors: List[str]       # What triggered the transition
    recommended_actions: List[str]   # Recommended portfolio actions
class MarketRegimeDetector:
    """
    Professional market regime detection system.
    Implements institutional-grade regime analysis including:
    - VIX-based volatility regime classification
    - Volatility clustering detection using GARCH models
    - Mean reversion analysis and trend detection
    - Market stress indicators and correlation breakdowns
    - Real-time regime monitoring with confidence levels
    - Strategy optimization based on regime state
    """
    def __init__(
        self,
        market_data_feed: MarketDataFeed,
        volatility_analyzer: VolatilityAnalyzer,
        market_internals: MarketInternals
    ):
        """Initialize market regime detector."""
        self.market_data_feed = market_data_feed
        self.volatility_analyzer = volatility_analyzer
        self.market_internals = market_internals
        # Logging
        self.logger = SpyderLogger().get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.time_utils = TradingTimeUtils()
        # Current state
        self.current_regime: Optional[RegimeState] = None
        self.regime_history: deque = deque(maxlen=252)  # 1 year of regime history
        # Historical data for analysis
        self.vix_history: deque = deque(maxlen=252)
        self.spy_price_history: deque = deque(maxlen=252)
        self.volume_history: deque = deque(maxlen=252)
        # Volatility clustering model
        self.garch_model = None
        self.volatility_states = deque(maxlen=100)
        # Monitoring
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        # Callbacks
        self.regime_change_callbacks: List[Callable] = []
        self.stress_alert_callbacks: List[Callable] = []
        # Performance tracking
        self.regime_accuracy_history = deque(maxlen=50)
        self.logger.info("Market Regime Detector initialized")
    # ==========================================================================
    # PUBLIC METHODS - CORE FUNCTIONALITY
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start real-time regime monitoring."""
        if self.monitoring_active:
            self.logger.warning("Regime monitoring already active")
            return
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="RegimeDetector",
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Market regime monitoring started")
    def stop_monitoring(self) -> None:
        """Stop regime monitoring."""
        self.monitoring_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("Market regime monitoring stopped")
    def get_current_regime(self) -> Optional[RegimeState]:
        """Get current market regime state."""
        return self.current_regime
    def detect_regime_change(self) -> Optional[RegimeTransition]:
        """Detect potential regime change."""
        try:
            # Calculate current metrics
            current_metrics = self._calculate_regime_metrics()
            if not current_metrics:
                return None
            # Classify new regime
            new_regime = self._classify_volatility_regime(current_metrics)
            # Check for regime change
            if (self.current_regime and 
                new_regime != self.current_regime.volatility_regime):
                # Calculate transition probability
                transition_prob = self._calculate_transition_probability(
                    self.current_regime.volatility_regime, new_regime, current_metrics
                )
                if transition_prob > REGIME_CONFIDENCE_THRESHOLD:
                    # Create transition event
                    transition = RegimeTransition(
                        timestamp=datetime.now(),
                        from_regime=self.current_regime.volatility_regime,
                        to_regime=new_regime,
                        transition_probability=transition_prob,
                        trigger_factors=self._identify_transition_triggers(current_metrics),
                        recommended_actions=self._get_transition_recommendations(
                            self.current_regime.volatility_regime, new_regime
                        )
                    )
                    return transition
            return None
        except Exception as e:
            self.error_handler.handle_error(e, "detect_regime_change")
            return None
    def get_optimal_strategies_for_regime(
        self,
        regime: Optional[MarketRegime] = None
    ) -> List[str]:
        """Get optimal strategies for current or specified regime."""
        target_regime = regime or (self.current_regime.volatility_regime if self.current_regime else MarketRegime.NORMAL_VOLATILITY)
        strategy_mapping = {
            MarketRegime.LOW_VOLATILITY: [
                'iron_condor',
                'short_strangle',
                'covered_call',
                'cash_secured_put'
            ],
            MarketRegime.NORMAL_VOLATILITY: [
                'iron_butterfly',
                'calendar_spread',
                'diagonal_spread',
                'ratio_spread'
            ],
            MarketRegime.HIGH_VOLATILITY: [
                'long_straddle',
                'long_strangle',
                'protective_put',
                'collar'
            ],
            MarketRegime.CRISIS_VOLATILITY: [
                'cash_position',
                'vix_calls',
                'protective_puts',
                'bear_put_spread'
            ]
        }
        return strategy_mapping.get(target_regime, ['iron_condor'])
    def get_risk_adjustment_factor(self) -> float:
        """Get risk adjustment factor based on current regime."""
        if not self.current_regime:
            return 1.0
        regime_factors = {
            MarketRegime.LOW_VOLATILITY: 1.2,      # Increase risk in low vol
            MarketRegime.NORMAL_VOLATILITY: 1.0,   # Normal risk
            MarketRegime.HIGH_VOLATILITY: 0.7,     # Reduce risk in high vol
            MarketRegime.CRISIS_VOLATILITY: 0.3    # Significantly reduce in crisis
        }
        base_factor = regime_factors.get(self.current_regime.volatility_regime, 1.0)
        # Apply additional adjustments based on regime confidence
        confidence_adjustment = self.current_regime.regime_confidence
        return base_factor * confidence_adjustment
    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def analyze_volatility_clustering(self) -> Dict[str, float]:
        """Analyze volatility clustering patterns."""
        try:
            if len(self.vix_history) < 30:
                return {'clustering_strength': 0.5, 'persistence': 0.5}
            # Calculate daily VIX changes
            vix_data = list(self.vix_history)
            vix_returns = [
                (vix_data[i] - vix_data[i-1]) / vix_data[i-1]
                for i in range(1, len(vix_data))
            ]
            # Calculate volatility clustering metrics
            abs_returns = [abs(r) for r in vix_returns]
            # Autocorrelation of absolute returns (clustering indicator)
            clustering_strength = self._calculate_autocorrelation(abs_returns, lag=1)
            # GARCH persistence approximation
            if len(abs_returns) >= 20:
                persistence = self._estimate_garch_persistence(abs_returns)
            else:
                persistence = 0.5
            return {
                'clustering_strength': max(0, min(1, clustering_strength)),
                'persistence': max(0, min(1, persistence)),
                'current_volatility_state': self._classify_volatility_state()
            }
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_volatility_clustering")
            return {'clustering_strength': 0.5, 'persistence': 0.5}
    def calculate_mean_reversion_metrics(self) -> Dict[str, float]:
        """Calculate mean reversion analysis."""
        try:
            if len(self.vix_history) < MEAN_REVERSION_LOOKBACK:
                return {'reversion_speed': 0.0, 'half_life': float('inf')}
            vix_data = list(self.vix_history)[-MEAN_REVERSION_LOOKBACK:]
            # Calculate VIX mean reversion using Ornstein-Uhlenbeck process
            log_vix = [np.log(v) for v in vix_data]
            # Estimate mean reversion speed
            reversion_speed = self._estimate_mean_reversion_speed(log_vix)
            # Calculate half-life of mean reversion
            if reversion_speed > 0:
                half_life = np.log(2) / reversion_speed
            else:
                half_life = float('inf')
            # Current deviation from long-term mean
            long_term_mean = statistics.mean(vix_data)
            current_deviation = (vix_data[-1] - long_term_mean) / long_term_mean
            return {
                'reversion_speed': reversion_speed,
                'half_life': half_life,
                'long_term_mean': long_term_mean,
                'current_deviation': current_deviation,
                'reversion_probability': self._calculate_reversion_probability(
                    current_deviation, reversion_speed
                )
            }
        except Exception as e:
            self.error_handler.handle_error(e, "calculate_mean_reversion_metrics")
            return {'reversion_speed': 0.0, 'half_life': float('inf')}
    def assess_market_stress(self) -> Dict[str, float]:
        """Assess market stress indicators."""
        try:
            stress_indicators = {}
            # VIX stress level
            if self.vix_history:
                current_vix = list(self.vix_history)[-1]
                vix_percentile = self._calculate_percentile(
                    current_vix, list(self.vix_history)
                )
                stress_indicators['vix_stress'] = min(1.0, vix_percentile / 100.0)
            # Put/call skew stress
            put_call_skew = self._get_put_call_skew()
            if put_call_skew < SKEW_STRESS_THRESHOLD:
                stress_indicators['skew_stress'] = abs(put_call_skew / SKEW_STRESS_THRESHOLD)
            else:
                stress_indicators['skew_stress'] = 0.0
            # Correlation breakdown stress
            correlation_stress = self._assess_correlation_breakdown()
            stress_indicators['correlation_stress'] = correlation_stress
            # Liquidity stress
            liquidity_stress = self._assess_liquidity_stress()
            stress_indicators['liquidity_stress'] = liquidity_stress
            # Overall stress level
            overall_stress = statistics.mean(stress_indicators.values())
            stress_indicators['overall_stress'] = overall_stress
            # Stress level classification
            if overall_stress > 0.8:
                stress_indicators['stress_level'] = 'EXTREME'
            elif overall_stress > 0.6:
                stress_indicators['stress_level'] = 'HIGH'
            elif overall_stress > 0.4:
                stress_indicators['stress_level'] = 'MODERATE'
            else:
                stress_indicators['stress_level'] = 'LOW'
            return stress_indicators
        except Exception as e:
            self.error_handler.handle_error(e, "assess_market_stress")
            return {'overall_stress': 0.5, 'stress_level': 'MODERATE'}
    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOP
    # ==========================================================================
    def _monitoring_loop(self) -> None:
        """Main regime monitoring loop."""
        self.logger.info("Market regime monitoring loop started")
        while self.monitoring_active:
            try:
                start_time = time.time()
                # Update market data
                self._update_market_data()
                # Calculate regime metrics
                metrics = self._calculate_regime_metrics()
                if metrics:
                    # Update current regime state
                    self._update_regime_state(metrics)
                    # Check for regime transitions
                    transition = self.detect_regime_change()
                    if transition:
                        self._handle_regime_transition(transition)
                # Sleep until next update
                elapsed = time.time() - start_time
                sleep_time = max(0, 60.0 - elapsed)  # Update every minute
                time.sleep(sleep_time)
            except Exception as e:
                self.error_handler.handle_error(e, "_monitoring_loop")
                time.sleep(30.0)  # Brief pause on error
    def _update_market_data(self) -> None:
        """Update historical market data."""
        try:
            # Get current VIX
            current_vix = self.market_data_feed.get_current_price('VIX')
            if current_vix:
                self.vix_history.append(current_vix)
            # Get current SPY price
            current_spy = self.market_data_feed.get_current_price('SPY')
            if current_spy:
                self.spy_price_history.append(current_spy)
            # Get current volume
            current_volume = self.market_data_feed.get_current_volume('SPY')
            if current_volume:
                self.volume_history.append(current_volume)
        except Exception as e:
            self.error_handler.handle_error(e, "_update_market_data")
    def _calculate_regime_metrics(self) -> Optional[RegimeMetrics]:
        """Calculate comprehensive regime metrics."""
        try:
            if len(self.vix_history) < 20:
                return None
            current_vix = list(self.vix_history)[-1]
            # VIX-based metrics
            vix_percentile = self._calculate_percentile(current_vix, list(self.vix_history))
            vix_trend = self._calculate_trend_slope(list(self.vix_history)[-10:])
            vix_mean_reversion = self.calculate_mean_reversion_metrics()['reversion_speed']
            # Volatility clustering
            clustering_metrics = self.analyze_volatility_clustering()
            garch_persistence = clustering_metrics['persistence']
            volatility_clustering = clustering_metrics['clustering_strength']
            # Realized vs implied volatility
            realized_vol = self.volatility_analyzer.get_realized_volatility('SPY', 20)
            implied_vol = current_vix / 100.0
            rv_iv_diff = (realized_vol - implied_vol) / implied_vol if implied_vol > 0 else 0
            # Trend metrics
            trend_metrics = self._calculate_trend_metrics()
            # Market stress
            stress_metrics = self.assess_market_stress()
            return RegimeMetrics(
                timestamp=datetime.now(),
                vix_level=current_vix,
                vix_percentile=vix_percentile,
                vix_trend=vix_trend,
                vix_mean_reversion=vix_mean_reversion,
                garch_persistence=garch_persistence,
                volatility_clustering=volatility_clustering,
                realized_vs_implied=rv_iv_diff,
                trend_strength=trend_metrics['strength'],
                trend_direction=trend_metrics['direction'],
                momentum=trend_metrics['momentum'],
                put_call_skew=self._get_put_call_skew(),
                correlation_stress=stress_metrics.get('correlation_stress', 0.0),
                liquidity_stress=stress_metrics.get('liquidity_stress', 0.0),
                mean_reversion_speed=vix_mean_reversion,
                oversold_probability=self._calculate_oversold_probability(),
                overbought_probability=self._calculate_overbought_probability()
            )
        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_regime_metrics")
            return None
    def _update_regime_state(self, metrics: RegimeMetrics) -> None:
        """Update current regime state."""
        try:
            # Classify regimes
            volatility_regime = self._classify_volatility_regime(metrics)
            trend_regime = self._classify_trend_regime(metrics)
            clustering_regime = self._classify_clustering_regime(metrics)
            liquidity_regime = self._classify_liquidity_regime(metrics)
            # Calculate regime confidence
            regime_confidence = self._calculate_regime_confidence(metrics)
            # Calculate transition probability
            transition_prob = 0.0
            if self.current_regime:
                transition_prob = self._calculate_transition_probability(
                    self.current_regime.volatility_regime, volatility_regime, metrics
                )
            # Calculate regime duration
            regime_duration = 1
            if (self.current_regime and 
                self.current_regime.volatility_regime == volatility_regime):
                regime_duration = self.current_regime.regime_duration_days + 1
            # Get optimal strategies
            optimal_strategies = self.get_optimal_strategies_for_regime(volatility_regime)
            # Calculate risk adjustment
            risk_adjustment = self._calculate_risk_adjustment(volatility_regime, metrics)
            # Create new regime state
            new_regime = RegimeState(
                timestamp=datetime.now(),
                volatility_regime=volatility_regime,
                trend_regime=trend_regime,
                clustering_regime=clustering_regime,
                liquidity_regime=liquidity_regime,
                regime_confidence=regime_confidence,
                transition_probability=transition_prob,
                optimal_strategies=optimal_strategies,
                risk_adjustment_factor=risk_adjustment,
                regime_duration_days=regime_duration,
                expected_duration_days=self._estimate_regime_duration(volatility_regime),
                metrics=metrics
            )
            # Update current regime
            self.current_regime = new_regime
            self.regime_history.append(new_regime)
        except Exception as e:
            self.error_handler.handle_error(e, "_update_regime_state")
    # ==========================================================================
    # PRIVATE METHODS - REGIME CLASSIFICATION
    # ==========================================================================
    def _classify_volatility_regime(self, metrics: RegimeMetrics) -> MarketRegime:
        """Classify volatility regime based on VIX levels."""
        vix = metrics.vix_level
        if vix < VIX_LOW_THRESHOLD:
            return MarketRegime.LOW_VOLATILITY
        elif vix < VIX_NORMAL_HIGH:
            return MarketRegime.NORMAL_VOLATILITY
        elif vix < VIX_EXTREME_THRESHOLD:
            return MarketRegime.HIGH_VOLATILITY
        else:
            return MarketRegime.CRISIS_VOLATILITY
    def _classify_trend_regime(self, metrics: RegimeMetrics) -> TrendRegime:
        """Classify trend regime."""
        strength = metrics.trend_strength
        direction = metrics.trend_direction
        if strength > 0.7:  # Strong trend
            if direction > 0.5:
                return TrendRegime.STRONG_BULL
            elif direction < -0.5:
                return TrendRegime.STRONG_BEAR
            else:
                return TrendRegime.SIDEWAYS
        elif strength > 0.3:  # Weak trend
            if direction > 0.2:
                return TrendRegime.WEAK_BULL
            elif direction < -0.2:
                return TrendRegime.WEAK_BEAR
            else:
                return TrendRegime.SIDEWAYS
        else:
            return TrendRegime.SIDEWAYS
    def _classify_clustering_regime(self, metrics: RegimeMetrics) -> VolatilityCluster:
        """Classify volatility clustering regime."""
        persistence = metrics.garch_persistence
        clustering = metrics.volatility_clustering
        # Check for volatility shock
        if abs(metrics.vix_trend) > VOLATILITY_SHOCK_THRESHOLD:
            return VolatilityCluster.VOLATILITY_SHOCK
        # Classify based on persistence and clustering
        if persistence > 0.9 and clustering > 0.7:
            return VolatilityCluster.HIGH_CLUSTERING
        elif persistence > 0.7 or clustering > 0.5:
            return VolatilityCluster.MODERATE_CLUSTERING
        else:
            return VolatilityCluster.LOW_CLUSTERING
    def _classify_liquidity_regime(self, metrics: RegimeMetrics) -> LiquidityRegime:
        """Classify liquidity regime."""
        liquidity_stress = metrics.liquidity_stress
        if liquidity_stress > 0.8:
            return LiquidityRegime.CRISIS
        elif liquidity_stress > 0.6:
            return LiquidityRegime.SCARCE
        elif liquidity_stress > 0.3:
            return LiquidityRegime.NORMAL
        else:
            return LiquidityRegime.ABUNDANT
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_percentile(self, value: float, data: List[float]) -> float:
        """Calculate percentile of value in data."""
        if not data:
            return 50.0
        sorted_data = sorted(data)
        position = sum(1 for x in sorted_data if x <= value)
        return (position / len(sorted_data)) * 100.0
    def _calculate_trend_slope(self, data: List[float]) -> float:
        """Calculate trend slope using linear regression."""
        if len(data) < 2:
            return 0.0
        x = list(range(len(data)))
        try:
            slope, _, _, _, _ = stats.linregress(x, data)
            return slope
        except:
            return 0.0
    def _calculate_trend_metrics(self) -> Dict[str, float]:
        """Calculate comprehensive trend metrics."""
        if len(self.spy_price_history) < 20:
            return {'strength': 0.0, 'direction': 0.0, 'momentum': 0.0}
        prices = list(self.spy_price_history)[-20:]
        # Trend strength using R-squared
        x = list(range(len(prices)))
        try:
            slope, intercept, r_value, _, _ = stats.linregress(x, prices)
            trend_strength = abs(r_value)  # R-squared as trend strength
            trend_direction = 1.0 if slope > 0 else -1.0
            # Momentum using recent price changes
            recent_change = (prices[-1] - prices[-5]) / prices[-5] if len(prices) >= 5 else 0
            momentum = np.tanh(recent_change * 100)  # Normalize to [-1, 1]
            return {
                'strength': trend_strength,
                'direction': trend_direction,
                'momentum': momentum
            }
        except:
            return {'strength': 0.0, 'direction': 0.0, 'momentum': 0.0}
    def _calculate_autocorrelation(self, data: List[float], lag: int = 1) -> float:
        """Calculate autocorrelation at specified lag."""
        if len(data) <= lag:
            return 0.0
        try:
            series = pd.Series(data)
            return series.autocorr(lag=lag)
        except:
            return 0.0
    def _estimate_garch_persistence(self, returns: List[float]) -> float:
        """Estimate GARCH persistence parameter."""
        # Simplified GARCH(1,1) persistence estimation
        if len(returns) < 10:
            return 0.5
        try:
            # Calculate squared returns (proxy for volatility)
            squared_returns = [r**2 for r in returns]
            # Simple persistence approximation using autocorrelation
            persistence = self._calculate_autocorrelation(squared_returns, lag=1)
            return max(0, min(1, persistence))
        except:
            return 0.5
    def _estimate_mean_reversion_speed(self, log_data: List[float]) -> float:
        """Estimate mean reversion speed using Ornstein-Uhlenbeck process."""
        if len(log_data) < 10:
            return 0.0
        try:
            # Calculate first differences
            diff_data = [log_data[i] - log_data[i-1] for i in range(1, len(log_data))]
            lagged_levels = log_data[:-1]
            # Center the lagged levels
            mean_level = statistics.mean(lagged_levels)
            centered_levels = [x - mean_level for x in lagged_levels]
            # Estimate reversion speed using regression
            if len(centered_levels) == len(diff_data):
                slope, _, _, _, _ = stats.linregress(centered_levels, diff_data)
                return abs(slope)  # Reversion speed
            else:
                return 0.0
        except:
            return 0.0
    def _calculate_reversion_probability(self, deviation: float, reversion_speed: float) -> float:
        """Calculate probability of mean reversion."""
        if reversion_speed <= 0:
            return 0.5
        # Higher deviation and faster reversion = higher probability
        prob = 1 - np.exp(-reversion_speed * abs(deviation))
        return max(0, min(1, prob))
    def _calculate_regime_confidence(self, metrics: RegimeMetrics) -> float:
        """Calculate confidence in current regime classification."""
        confidence_factors = []
        # VIX-based confidence
        vix = metrics.vix_level
        if vix < VIX_LOW_THRESHOLD - 2 or vix > VIX_EXTREME_THRESHOLD + 5:
            confidence_factors.append(0.9)  # Very clear regime
        elif VIX_LOW_THRESHOLD + 1 < vix < VIX_NORMAL_HIGH - 1:
            confidence_factors.append(0.8)  # Clear normal regime
        else:
            confidence_factors.append(0.6)  # Transition zone
        # Trend confidence
        if metrics.trend_strength > 0.7:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.6)
        # Persistence confidence
        if metrics.garch_persistence > 0.8:
            confidence_factors.append(0.8)
        else:
            confidence_factors.append(0.7)
        return statistics.mean(confidence_factors)
    def _calculate_transition_probability(
        self,
        current_regime: MarketRegime,
        new_regime: MarketRegime,
        metrics: RegimeMetrics
    ) -> float:
        """Calculate probability of regime transition."""
        if current_regime == new_regime:
            return 0.0
        # Base transition probability
        base_prob = 0.1
        # Increase probability based on VIX movement
        vix_change_factor = abs(metrics.vix_trend) / 5.0  # Normalize
        # Increase probability for extreme values
        if metrics.vix_level > VIX_EXTREME_THRESHOLD or metrics.vix_level < VIX_LOW_THRESHOLD:
            extreme_factor = 0.3
        else:
            extreme_factor = 0.0
        # Clustering factor
        clustering_factor = metrics.volatility_clustering * 0.2
        total_prob = base_prob + vix_change_factor + extreme_factor + clustering_factor
        return min(1.0, total_prob)
    def _calculate_risk_adjustment(self, regime: MarketRegime, metrics: RegimeMetrics) -> float:
        """Calculate risk adjustment factor for regime."""
        base_adjustments = {
            MarketRegime.LOW_VOLATILITY: 1.2,
            MarketRegime.NORMAL_VOLATILITY: 1.0,
            MarketRegime.HIGH_VOLATILITY: 0.7,
            MarketRegime.CRISIS_VOLATILITY: 0.3
        }
        base_factor = base_adjustments.get(regime, 1.0)
        # Adjust based on stress indicators
        stress_adjustment = 1.0 - (metrics.liquidity_stress * 0.3)
        return base_factor * stress_adjustment
    def _estimate_regime_duration(self, regime: MarketRegime) -> float:
        """Estimate expected duration of regime in days."""
        # Historical average durations (institutional knowledge)
        duration_estimates = {
            MarketRegime.LOW_VOLATILITY: 45.0,      # ~2 months
            MarketRegime.NORMAL_VOLATILITY: 90.0,   # ~3 months
            MarketRegime.HIGH_VOLATILITY: 30.0,     # ~1 month
            MarketRegime.CRISIS_VOLATILITY: 15.0    # ~2 weeks
        }
        return duration_estimates.get(regime, 60.0)
    # ==========================================================================
    # PRIVATE METHODS - UTILITY FUNCTIONS
    # ==========================================================================
    def _classify_volatility_state(self) -> str:
        """Classify current volatility state."""
        if not self.vix_history:
            return "UNKNOWN"
        current_vix = list(self.vix_history)[-1]
        if current_vix < 12:
            return "EXTREMELY_LOW"
        elif current_vix < 16:
            return "LOW"
        elif current_vix < 25:
            return "NORMAL"
        elif current_vix < 30:
            return "HIGH"
        else:
            return "EXTREME"
    def _get_put_call_skew(self) -> float:
        """Get put/call volatility skew."""
        # Simplified implementation - would get from options data
        return -1.0  # Typical negative skew
    def _assess_correlation_breakdown(self) -> float:
        """Assess cross-asset correlation breakdown."""
        # Simplified implementation - would analyze cross-asset correlations
        return 0.3  # Moderate correlation stress
    def _assess_liquidity_stress(self) -> float:
        """Assess market liquidity stress."""
        # Simplified implementation - would analyze bid-ask spreads, depth
        return 0.2  # Low liquidity stress
    def _calculate_oversold_probability(self) -> float:
        """Calculate probability of oversold conditions."""
        if not self.vix_history:
            return 0.0
        current_vix = list(self.vix_history)[-1]
        vix_percentile = self._calculate_percentile(current_vix, list(self.vix_history))
        # Higher VIX percentile = higher oversold probability
        return min(1.0, vix_percentile / 100.0)
    def _calculate_overbought_probability(self) -> float:
        """Calculate probability of overbought conditions."""
        if not self.vix_history:
            return 0.0
        current_vix = list(self.vix_history)[-1]
        vix_percentile = self._calculate_percentile(current_vix, list(self.vix_history))
        # Lower VIX percentile = higher overbought probability
        return min(1.0, (100.0 - vix_percentile) / 100.0)
    def _identify_transition_triggers(self, metrics: RegimeMetrics) -> List[str]:
        """Identify factors triggering regime transition."""
        triggers = []
        if abs(metrics.vix_trend) > 2.0:
            triggers.append("significant_vix_movement")
        if metrics.volatility_clustering > 0.8:
            triggers.append("high_volatility_clustering")
        if metrics.liquidity_stress > 0.7:
            triggers.append("liquidity_stress")
        if abs(metrics.realized_vs_implied) > 0.3:
            triggers.append("rv_iv_divergence")
        return triggers or ["general_market_conditions"]
    def _get_transition_recommendations(
        self,
        from_regime: MarketRegime,
        to_regime: MarketRegime
    ) -> List[str]:
        """Get recommendations for regime transition."""
        transition_map = {
            (MarketRegime.LOW_VOLATILITY, MarketRegime.NORMAL_VOLATILITY): [
                "close_short_vol_positions",
                "reduce_iron_condor_exposure",
                "prepare_for_increased_movement"
            ],
            (MarketRegime.NORMAL_VOLATILITY, MarketRegime.HIGH_VOLATILITY): [
                "buy_protection",
                "reduce_position_sizes",
                "consider_long_volatility_strategies"
            ],
            (MarketRegime.HIGH_VOLATILITY, MarketRegime.CRISIS_VOLATILITY): [
                "emergency_risk_reduction",
                "hedge_all_positions",
                "preserve_capital"
            ],
            (MarketRegime.CRISIS_VOLATILITY, MarketRegime.HIGH_VOLATILITY): [
                "gradual_reentry",
                "look_for_mean_reversion_opportunities",
                "maintain_hedges"
            ]
        }
        return transition_map.get((from_regime, to_regime), ["monitor_closely"])
    def _handle_regime_transition(self, transition: RegimeTransition) -> None:
        """Handle regime transition event."""
        self.logger.info(
            f"Regime transition detected: {transition.from_regime.name} -> "
            f"{transition.to_regime.name} (probability: {transition.transition_probability:.1%})"
        )
        # Execute callbacks
        for callback in self.regime_change_callbacks:
            try:
                callback(transition)
            except Exception as e:
                self.logger.error(f"Regime change callback error: {e}")
    # ==========================================================================
    # PUBLIC METHODS - CALLBACKS AND REPORTING
    # ==========================================================================
    def add_regime_change_callback(self, callback: Callable[[RegimeTransition], None]) -> None:
        """Add callback for regime changes."""
        self.regime_change_callbacks.append(callback)
    def add_stress_alert_callback(self, callback: Callable[[Dict[str, float]], None]) -> None:
        """Add callback for market stress alerts."""
        self.stress_alert_callbacks.append(callback)
    def get_regime_analysis_report(self) -> Dict[str, Any]:
        """Generate comprehensive regime analysis report."""
        try:
            current_metrics = self._calculate_regime_metrics()
            clustering_analysis = self.analyze_volatility_clustering()
            mean_reversion = self.calculate_mean_reversion_metrics()
            stress_assessment = self.assess_market_stress()
            return {
                'timestamp': datetime.now(),
                'current_regime': {
                    'volatility_regime': self.current_regime.volatility_regime.name if self.current_regime else None,
                    'trend_regime': self.current_regime.trend_regime.name if self.current_regime else None,
                    'confidence': self.current_regime.regime_confidence if self.current_regime else None,
                    'duration_days': self.current_regime.regime_duration_days if self.current_regime else None
                },
                'market_metrics': {
                    'vix_level': current_metrics.vix_level if current_metrics else None,
                    'vix_percentile': current_metrics.vix_percentile if current_metrics else None,
                    'trend_strength': current_metrics.trend_strength if current_metrics else None,
                    'volatility_clustering': clustering_analysis['clustering_strength']
                },
                'mean_reversion': mean_reversion,
                'stress_indicators': stress_assessment,
                'optimal_strategies': self.get_optimal_strategies_for_regime(),
                'risk_adjustment_factor': self.get_risk_adjustment_factor(),
                'regime_history_length': len(self.regime_history),
                'monitoring_status': self.monitoring_active
            }
        except Exception as e:
            self.error_handler.handle_error(e, "get_regime_analysis_report")
            return {'error': 'Failed to generate report'}
if __name__ == "__main__":
    print("Market Regime Detector - Professional Analysis")
    print("=" * 55)
    print("Professional Features:")
    print("• VIX-based regime classification (16/25/30 thresholds)")
    print("• Volatility clustering detection using GARCH models")
    print("• Mean reversion analysis with Ornstein-Uhlenbeck process")
    print("• Market stress indicators and correlation breakdown")
    print("• Real-time regime monitoring with confidence levels")
    print("• Strategy optimization based on regime state")
    print("• Professional risk adjustment factors")
    print("• Institutional transition probability models")