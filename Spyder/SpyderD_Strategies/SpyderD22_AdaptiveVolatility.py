#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderD22_AdaptiveVolatility.py
Group: D (Strategies)
Purpose: Adaptive volatility trading strategy leveraging N-modules
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 16:30:00

Description:
    This module implements an adaptive volatility trading strategy that leverages
    the N-group numerical modules for sophisticated volatility analysis. It trades
    the volatility risk premium, IV/HV divergences, term structure anomalies, and
    volatility regime changes. The strategy dynamically adjusts positions based on
    volatility forecasts, skew analysis, and market microstructure.

Key Features:
    - IV vs HV arbitrage trading
    - Volatility risk premium harvesting
    - Term structure trading (contango/backwardation)
    - Volatility regime detection and adaptation
    - Skew trading opportunities
    - Integration with N04_OptionsGreeks and N05_VolatilityModeling
    - Dynamic position sizing based on volatility forecast
    - Multiple timeframe volatility analysis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from scipy import stats, optimize

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, Signal, StrategyState
from Spyder.SpyderN_Numerical.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator
from Spyder.SpyderN_Numerical.SpyderN05_VolatilityModeling import VolatilityModeling
from Spyder.SpyderN_Numerical.SpyderN06_StatisticalAnalysis import StatisticalAnalysis
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Volatility thresholds
IV_HV_DIVERGENCE_THRESHOLD = 0.20  # 20% divergence triggers signal
VOLATILITY_RISK_PREMIUM_TARGET = 0.15  # Target 15% premium
SKEW_EXTREME_THRESHOLD = 2.0  # 2 standard deviations
TERM_STRUCTURE_SLOPE_THRESHOLD = 0.10  # 10% slope difference

# Position limits
MAX_VEGA_EXPOSURE = 1000  # Maximum vega per position
MAX_VOLATILITY_POSITIONS = 5
MIN_DAYS_TO_EXPIRY = 15
MAX_DAYS_TO_EXPIRY = 60

# Regime thresholds
REGIME_CHANGE_CONFIDENCE = 0.70  # 70% confidence for regime change
VOLATILITY_SPIKE_THRESHOLD = 1.5  # 50% increase = spike
VOLATILITY_CRUSH_THRESHOLD = 0.7  # 30% decrease = crush

# Risk parameters
MAX_POSITION_SIZE = 0.05  # 5% of portfolio per position
STOP_LOSS_MULTIPLIER = 2.0  # Stop at 2x expected move
TARGET_PROFIT_MULTIPLIER = 1.5  # Target 1.5x risk

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classifications"""
    LOW_STABLE = "low_stable"
    LOW_RISING = "low_rising"
    NORMAL = "normal"
    HIGH_STABLE = "high_stable"
    HIGH_FALLING = "high_falling"
    SPIKE = "spike"
    CRUSH = "crush"
    TRANSITIONING = "transitioning"

class VolatilityTrade(Enum):
    """Types of volatility trades"""
    LONG_VOLATILITY = "long_volatility"
    SHORT_VOLATILITY = "short_volatility"
    VOLATILITY_ARBITRAGE = "volatility_arbitrage"
    TERM_STRUCTURE = "term_structure"
    SKEW_TRADE = "skew_trade"
    DISPERSION = "dispersion"
    CORRELATION = "correlation"

class SignalStrength(Enum):
    """Signal strength levels"""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4
    EXTREME = 5

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics"""
    spot_price: float
    implied_volatility: float
    historical_volatility: float
    iv_rank: float
    iv_percentile: float
    volatility_risk_premium: float
    realized_volatility: float
    garch_forecast: float
    ewma_volatility: float
    parkinson_volatility: float
    term_structure: Dict[int, float]
    volatility_smile: Dict[float, float]
    skew: float
    kurtosis: float
    regime: VolatilityRegime
    regime_confidence: float

@dataclass
class VolatilitySignal:
    """Volatility trading signal"""
    trade_type: VolatilityTrade
    direction: str  # LONG, SHORT, NEUTRAL
    strength: SignalStrength
    entry_iv: float
    target_iv: float
    stop_iv: float
    expected_edge: float
    confidence: float
    time_horizon: int  # Days
    recommended_structure: str
    size_recommendation: float

@dataclass
class VolatilityPosition:
    """Active volatility position"""
    position_id: str
    trade_type: VolatilityTrade
    entry_date: datetime
    expiration: datetime
    structure: str  # straddle, strangle, etc.
    entry_iv: float
    current_iv: float
    target_iv: float
    stop_iv: float
    vega: float
    theta: float
    gamma: float
    pnl: float
    days_held: int

# ==============================================================================
# MAIN STRATEGY CLASS
# ==============================================================================
class AdaptiveVolatilityStrategy(BaseStrategy):
    """
    Adaptive volatility trading strategy.
    
    Leverages numerical modules to identify and trade volatility opportunities
    across multiple timeframes and structures.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Adaptive Volatility Strategy"""
        super().__init__(config)
        
        self.strategy_name = "AdaptiveVolatility"
        self.version = "1.0.0"
        
        # Initialize numerical components
        self.greeks_calculator = OptionsGreeksCalculator()
        self.volatility_model = VolatilityModeling()
        self.statistical_analyzer = StatisticalAnalysis()
        
        # Strategy parameters
        self.iv_hv_threshold = config.get('iv_hv_threshold', IV_HV_DIVERGENCE_THRESHOLD)
        self.vrp_target = config.get('vrp_target', VOLATILITY_RISK_PREMIUM_TARGET)
        self.max_vega = config.get('max_vega', MAX_VEGA_EXPOSURE)
        
        # Position tracking
        self.active_positions: Dict[str, VolatilityPosition] = {}
        self.position_history: List[VolatilityPosition] = []
        
        # Volatility tracking
        self.current_metrics: Optional[VolatilityMetrics] = None
        self.volatility_history = []
        self.regime_history = []
        
        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.sharpe_ratio = 0.0
        
        # Calibration data
        self.iv_history = pd.DataFrame()
        self.hv_history = pd.DataFrame()
        self.regime_model = None
        
        self.logger.info(f"{self.strategy_name} initialized")
    
    def analyze_market_conditions(self, market_data: Dict[str, Any]) -> Signal:
        """
        Analyze volatility conditions and generate trading signals.
        
        Args:
            market_data: Current market data including options
            
        Returns:
            Trading signal with volatility positions
        """
        try:
            # Calculate comprehensive volatility metrics
            metrics = self._calculate_volatility_metrics(market_data)
            self.current_metrics = metrics
            
            # Detect regime and transitions
            regime_signal = self._detect_regime_change(metrics)
            
            # Analyze trading opportunities
            opportunities = []
            
            # Check IV/HV divergence
            iv_hv_signal = self._analyze_iv_hv_divergence(metrics)
            if iv_hv_signal:
                opportunities.append(iv_hv_signal)
            
            # Check volatility risk premium
            vrp_signal = self._analyze_vrp(metrics)
            if vrp_signal:
                opportunities.append(vrp_signal)
            
            # Check term structure
            term_signal = self._analyze_term_structure(metrics)
            if term_signal:
                opportunities.append(term_signal)
            
            # Check skew opportunities
            skew_signal = self._analyze_skew(metrics)
            if skew_signal:
                opportunities.append(skew_signal)
            
            # Combine signals and select best opportunity
            if opportunities:
                best_signal = self._select_best_opportunity(opportunities, metrics)
                return self._create_trade_signal(best_signal, metrics, market_data)
            
            # Check existing positions for management
            management_signal = self._manage_positions(metrics, market_data)
            if management_signal:
                return management_signal
            
            return Signal(action="HOLD")
            
        except Exception as e:
            self.logger.error(f"Error analyzing volatility: {e}")
            self.error_handler.handle_error(e, {"method": "analyze_market_conditions"})
            return Signal(action="HOLD")
    
    def _calculate_volatility_metrics(self, market_data: Dict[str, Any]) -> VolatilityMetrics:
        """Calculate comprehensive volatility metrics"""
        try:
            spot = market_data['SPY']['last']
            
            # Get IV from options data
            options_data = market_data.get('options_data', {})
            current_iv = options_data.get('implied_volatility', 0.20)
            
            # Calculate historical volatilities using N-modules
            price_history = market_data.get('price_history', [])
            
            # Use VolatilityModeling module for sophisticated calculations
            hv_20 = self.volatility_model.calculate_historical_volatility(price_history, 20)
            realized_vol = self.volatility_model.calculate_realized_volatility(price_history)
            garch_forecast = self.volatility_model.garch_forecast(price_history)
            ewma_vol = self.volatility_model.calculate_ewma_volatility(price_history)
            parkinson_vol = self.volatility_model.calculate_parkinson_volatility(
                market_data.get('high_low_data', [])
            )
            
            # Calculate IV rank and percentile
            iv_rank = self._calculate_iv_rank(current_iv)
            iv_percentile = self._calculate_iv_percentile(current_iv)
            
            # Calculate volatility risk premium
            vrp = current_iv - realized_vol
            
            # Get term structure
            term_structure = self._extract_term_structure(options_data)
            
            # Get volatility smile/skew
            smile = self._extract_volatility_smile(options_data)
            
            # Calculate skew and kurtosis
            skew = self.statistical_analyzer.calculate_skew(price_history)
            kurtosis = self.statistical_analyzer.calculate_kurtosis(price_history)
            
            # Determine regime
            regime, confidence = self._determine_volatility_regime(
                current_iv, hv_20, iv_rank, vrp
            )
            
            return VolatilityMetrics(
                spot_price=spot,
                implied_volatility=current_iv,
                historical_volatility=hv_20,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                volatility_risk_premium=vrp,
                realized_volatility=realized_vol,
                garch_forecast=garch_forecast,
                ewma_volatility=ewma_vol,
                parkinson_volatility=parkinson_vol,
                term_structure=term_structure,
                volatility_smile=smile,
                skew=skew,
                kurtosis=kurtosis,
                regime=regime,
                regime_confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility metrics: {e}")
            # Return default metrics
            return VolatilityMetrics(
                spot_price=market_data.get('SPY', {}).get('last', 450),
                implied_volatility=0.20,
                historical_volatility=0.18,
                iv_rank=50,
                iv_percentile=50,
                volatility_risk_premium=0.02,
                realized_volatility=0.18,
                garch_forecast=0.19,
                ewma_volatility=0.19,
                parkinson_volatility=0.17,
                term_structure={},
                volatility_smile={},
                skew=0,
                kurtosis=3,
                regime=VolatilityRegime.NORMAL,
                regime_confidence=0.5
            )
    
    def _calculate_iv_rank(self, current_iv: float) -> float:
        """Calculate IV rank over past year"""
        if len(self.iv_history) < 20:
            return 50.0  # Default to middle
        
        yearly_ivs = self.iv_history.tail(252)['iv'].values
        min_iv = yearly_ivs.min()
        max_iv = yearly_ivs.max()
        
        if max_iv == min_iv:
            return 50.0
        
        return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
    
    def _calculate_iv_percentile(self, current_iv: float) -> float:
        """Calculate IV percentile over past year"""
        if len(self.iv_history) < 20:
            return 50.0
        
        yearly_ivs = self.iv_history.tail(252)['iv'].values
        return stats.percentileofscore(yearly_ivs, current_iv)
    
    def _extract_term_structure(self, options_data: Dict) -> Dict[int, float]:
        """Extract volatility term structure"""
        term_structure = {}
        
        expirations = options_data.get('expirations', {})
        for days, data in expirations.items():
            if isinstance(days, int) and 'implied_volatility' in data:
                term_structure[days] = data['implied_volatility']
        
        return term_structure
    
    def _extract_volatility_smile(self, options_data: Dict) -> Dict[float, float]:
        """Extract volatility smile/skew"""
        smile = {}
        
        chain = options_data.get('chain', {})
        for strike, data in chain.items():
            if isinstance(data, dict) and 'implied_volatility' in data:
                smile[strike] = data['implied_volatility']
        
        return smile
    
    def _determine_volatility_regime(
        self,
        iv: float,
        hv: float,
        iv_rank: float,
        vrp: float
    ) -> Tuple[VolatilityRegime, float]:
        """Determine current volatility regime"""
        confidence = 0.5
        
        # Low volatility regimes
        if iv < 0.12:  # IV below 12%
            if iv > hv * 1.1:  # IV rising relative to HV
                return VolatilityRegime.LOW_RISING, 0.7
            else:
                return VolatilityRegime.LOW_STABLE, 0.8
        
        # High volatility regimes
        elif iv > 0.25:  # IV above 25%
            if iv < hv * 0.9:  # IV falling relative to HV
                return VolatilityRegime.HIGH_FALLING, 0.7
            else:
                return VolatilityRegime.HIGH_STABLE, 0.8
        
        # Spike detection
        if len(self.iv_history) > 5:
            recent_avg = self.iv_history.tail(5)['iv'].mean()
            if iv > recent_avg * VOLATILITY_SPIKE_THRESHOLD:
                return VolatilityRegime.SPIKE, 0.9
            elif iv < recent_avg * VOLATILITY_CRUSH_THRESHOLD:
                return VolatilityRegime.CRUSH, 0.9
        
        # Check for regime transition
        if abs(vrp) > 0.05 and iv_rank > 70:
            return VolatilityRegime.TRANSITIONING, 0.6
        
        return VolatilityRegime.NORMAL, 0.5
    
    def _detect_regime_change(self, metrics: VolatilityMetrics) -> Optional[VolatilitySignal]:
        """Detect volatility regime changes"""
        if not self.regime_history:
            self.regime_history.append(metrics.regime)
            return None
        
        previous_regime = self.regime_history[-1]
        current_regime = metrics.regime
        
        # Check for significant regime change
        if previous_regime != current_regime and metrics.regime_confidence > REGIME_CHANGE_CONFIDENCE:
            self.regime_history.append(current_regime)
            
            # Generate signal based on regime transition
            if current_regime == VolatilityRegime.SPIKE:
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SHORT_VOLATILITY,
                    direction="SHORT",
                    strength=SignalStrength.STRONG,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 0.8,
                    stop_iv=metrics.implied_volatility * 1.2,
                    expected_edge=0.10,
                    confidence=metrics.regime_confidence,
                    time_horizon=10,
                    recommended_structure="short_straddle",
                    size_recommendation=0.5
                )
            
            elif current_regime == VolatilityRegime.CRUSH:
                return VolatilitySignal(
                    trade_type=VolatilityTrade.LONG_VOLATILITY,
                    direction="LONG",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 1.3,
                    stop_iv=metrics.implied_volatility * 0.7,
                    expected_edge=0.08,
                    confidence=metrics.regime_confidence,
                    time_horizon=15,
                    recommended_structure="long_strangle",
                    size_recommendation=0.7
                )
        
        self.regime_history.append(current_regime)
        return None
    
    def _analyze_iv_hv_divergence(self, metrics: VolatilityMetrics) -> Optional[VolatilitySignal]:
        """Analyze IV/HV divergence for trading opportunities"""
        divergence = metrics.implied_volatility - metrics.historical_volatility
        divergence_ratio = divergence / metrics.historical_volatility
        
        if abs(divergence_ratio) > self.iv_hv_threshold:
            if divergence_ratio > self.iv_hv_threshold:
                # IV too high relative to HV - sell volatility
                return VolatilitySignal(
                    trade_type=VolatilityTrade.VOLATILITY_ARBITRAGE,
                    direction="SHORT",
                    strength=self._calculate_signal_strength(abs(divergence_ratio)),
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.historical_volatility * 1.1,
                    stop_iv=metrics.implied_volatility * 1.15,
                    expected_edge=divergence * 0.5,
                    confidence=min(0.8, abs(divergence_ratio)),
                    time_horizon=20,
                    recommended_structure="iron_condor",
                    size_recommendation=self._calculate_position_size(divergence_ratio)
                )
            else:
                # IV too low relative to HV - buy volatility
                return VolatilitySignal(
                    trade_type=VolatilityTrade.VOLATILITY_ARBITRAGE,
                    direction="LONG",
                    strength=self._calculate_signal_strength(abs(divergence_ratio)),
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.historical_volatility * 0.9,
                    stop_iv=metrics.implied_volatility * 0.85,
                    expected_edge=abs(divergence) * 0.5,
                    confidence=min(0.8, abs(divergence_ratio)),
                    time_horizon=20,
                    recommended_structure="calendar_spread",
                    size_recommendation=self._calculate_position_size(abs(divergence_ratio))
                )
        
        return None
    
    def _analyze_vrp(self, metrics: VolatilityMetrics) -> Optional[VolatilitySignal]:
        """Analyze volatility risk premium"""
        if metrics.volatility_risk_premium > self.vrp_target:
            # Significant VRP - sell volatility
            return VolatilitySignal(
                trade_type=VolatilityTrade.SHORT_VOLATILITY,
                direction="SHORT",
                strength=SignalStrength.MODERATE,
                entry_iv=metrics.implied_volatility,
                target_iv=metrics.realized_volatility,
                stop_iv=metrics.implied_volatility * 1.20,
                expected_edge=metrics.volatility_risk_premium * 0.7,
                confidence=0.65,
                time_horizon=30,
                recommended_structure="put_spread",
                size_recommendation=0.8
            )
        
        elif metrics.volatility_risk_premium < -self.vrp_target * 0.5:
            # Negative VRP - potential volatility expansion
            return VolatilitySignal(
                trade_type=VolatilityTrade.LONG_VOLATILITY,
                direction="LONG",
                strength=SignalStrength.WEAK,
                entry_iv=metrics.implied_volatility,
                target_iv=metrics.implied_volatility * 1.25,
                stop_iv=metrics.implied_volatility * 0.80,
                expected_edge=abs(metrics.volatility_risk_premium) * 0.5,
                confidence=0.55,
                time_horizon=20,
                recommended_structure="long_butterfly",
                size_recommendation=0.5
            )
        
        return None
    
    def _analyze_term_structure(self, metrics: VolatilityMetrics) -> Optional[VolatilitySignal]:
        """Analyze volatility term structure"""
        if len(metrics.term_structure) < 2:
            return None
        
        # Calculate term structure slope
        terms = sorted(metrics.term_structure.keys())
        if len(terms) >= 2:
            front_month = metrics.term_structure[terms[0]]
            back_month = metrics.term_structure[terms[-1]]
            slope = (back_month - front_month) / front_month
            
            if abs(slope) > TERM_STRUCTURE_SLOPE_THRESHOLD:
                if slope > TERM_STRUCTURE_SLOPE_THRESHOLD:
                    # Contango - sell front, buy back
                    return VolatilitySignal(
                        trade_type=VolatilityTrade.TERM_STRUCTURE,
                        direction="NEUTRAL",
                        strength=SignalStrength.MODERATE,
                        entry_iv=front_month,
                        target_iv=(front_month + back_month) / 2,
                        stop_iv=front_month * 1.3,
                        expected_edge=abs(slope) * 0.3,
                        confidence=0.60,
                        time_horizon=terms[0],
                        recommended_structure="calendar_spread",
                        size_recommendation=0.6
                    )
                else:
                    # Backwardation - buy front, sell back
                    return VolatilitySignal(
                        trade_type=VolatilityTrade.TERM_STRUCTURE,
                        direction="NEUTRAL",
                        strength=SignalStrength.MODERATE,
                        entry_iv=front_month,
                        target_iv=(front_month + back_month) / 2,
                        stop_iv=front_month * 0.7,
                        expected_edge=abs(slope) * 0.3,
                        confidence=0.60,
                        time_horizon=terms[0],
                        recommended_structure="reverse_calendar",
                        size_recommendation=0.6
                    )
        
        return None
    
    def _analyze_skew(self, metrics: VolatilityMetrics) -> Optional[VolatilitySignal]:
        """Analyze volatility skew for opportunities"""
        if abs(metrics.skew) > SKEW_EXTREME_THRESHOLD:
            if metrics.skew > SKEW_EXTREME_THRESHOLD:
                # Extreme positive skew - potential mean reversion
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SKEW_TRADE,
                    direction="SHORT",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 0.9,
                    stop_iv=metrics.implied_volatility * 1.15,
                    expected_edge=0.06,
                    confidence=0.55,
                    time_horizon=15,
                    recommended_structure="put_ratio_spread",
                    size_recommendation=0.5
                )
            else:
                # Extreme negative skew - potential volatility expansion
                return VolatilitySignal(
                    trade_type=VolatilityTrade.SKEW_TRADE,
                    direction="LONG",
                    strength=SignalStrength.MODERATE,
                    entry_iv=metrics.implied_volatility,
                    target_iv=metrics.implied_volatility * 1.1,
                    stop_iv=metrics.implied_volatility * 0.85,
                    expected_edge=0.06,
                    confidence=0.55,
                    time_horizon=15,
                    recommended_structure="call_ratio_spread",
                    size_recommendation=0.5
                )
        
        return None
    
    def _calculate_signal_strength(self, divergence: float) -> SignalStrength:
        """Calculate signal strength based on divergence magnitude"""
        abs_div = abs(divergence)
        if abs_div < 0.3:
            return SignalStrength.WEAK
        elif abs_div < 0.5:
            return SignalStrength.MODERATE
        elif abs_div < 0.7:
            return SignalStrength.STRONG
        elif abs_div < 1.0:
            return SignalStrength.VERY_STRONG
        else:
            return SignalStrength.EXTREME
    
    def _calculate_position_size(self, signal_strength: float) -> float:
        """Calculate position size based on signal strength"""
        return min(1.0, max(0.2, signal_strength))
    
    def _select_best_opportunity(
        self,
        opportunities: List[VolatilitySignal],
        metrics: VolatilityMetrics
    ) -> VolatilitySignal:
        """Select best trading opportunity from multiple signals"""
        # Score each opportunity
        scored_opportunities = []
        
        for opp in opportunities:
            score = 0.0
            
            # Weight by signal strength
            score += opp.strength.value * 20
            
            # Weight by confidence
            score += opp.confidence * 100
            
            # Weight by expected edge
            score += opp.expected_edge * 200
            
            # Adjust for regime alignment
            if self._is_regime_aligned(opp, metrics.regime):
                score *= 1.2
            
            # Adjust for IV rank
            if metrics.iv_rank > 70 and opp.direction == "SHORT":
                score *= 1.1
            elif metrics.iv_rank < 30 and opp.direction == "LONG":
                score *= 1.1
            
            scored_opportunities.append((opp, score))
        
        # Return highest scoring opportunity
        return max(scored_opportunities, key=lambda x: x[1])[0]
    
    def _is_regime_aligned(self, signal: VolatilitySignal, regime: VolatilityRegime) -> bool:
        """Check if signal aligns with current regime"""
        alignments = {
            VolatilityRegime.HIGH_FALLING: ["SHORT"],
            VolatilityRegime.LOW_RISING: ["LONG"],
            VolatilityRegime.SPIKE: ["SHORT"],
            VolatilityRegime.CRUSH: ["LONG"]
        }
        
        return signal.direction in alignments.get(regime, [])
    
    def _create_trade_signal(
        self,
        vol_signal: VolatilitySignal,
        metrics: VolatilityMetrics,
        market_data: Dict
    ) -> Signal:
        """Create trading signal from volatility signal"""
        # Map structure to specific strategy
        structure_map = {
            "iron_condor": "IRON_CONDOR",
            "short_straddle": "SHORT_STRADDLE",
            "long_strangle": "LONG_STRANGLE",
            "calendar_spread": "CALENDAR",
            "put_spread": "PUT_SPREAD",
            "long_butterfly": "BUTTERFLY",
            "put_ratio_spread": "RATIO_SPREAD",
            "call_ratio_spread": "RATIO_SPREAD"
        }
        
        strategy = structure_map.get(vol_signal.recommended_structure, "CUSTOM")
        
        # Calculate contracts based on vega limit
        target_vega = self.max_vega * vol_signal.size_recommendation
        contracts = self._calculate_contracts_for_vega(target_vega, market_data)
        
        return Signal(
            action="ENTER",
            strategy=strategy,
            direction=vol_signal.direction,
            contracts=contracts,
            confidence=vol_signal.confidence,
            metadata={
                'trade_type': vol_signal.trade_type.value,
                'entry_iv': vol_signal.entry_iv,
                'target_iv': vol_signal.target_iv,
                'stop_iv': vol_signal.stop_iv,
                'expected_edge': vol_signal.expected_edge,
                'time_horizon': vol_signal.time_horizon,
                'structure': vol_signal.recommended_structure,
                'current_regime': metrics.regime.value,
                'iv_rank': metrics.iv_rank,
                'vrp': metrics.volatility_risk_premium
            }
        )
    
    def _calculate_contracts_for_vega(self, target_vega: float, market_data: Dict) -> int:
        """Calculate number of contracts for target vega exposure"""
        # Get ATM vega from options chain
        chain = market_data.get('options_chain', {})
        atm_strike = market_data['SPY']['last']
        
        # Find closest ATM option
        atm_vega = 0.50  # Default estimate
        
        for strike, data in chain.get('calls', {}).items():
            if abs(strike - atm_strike) < 1.0:
                atm_vega = data.get('vega', 0.50)
                break
        
        # Calculate contracts
        contracts = int(target_vega / (atm_vega * 100))
        return max(1, min(contracts, 20))  # Limit between 1 and 20
    
    def _manage_positions(
        self,
        metrics: VolatilityMetrics,
        market_data: Dict
    ) -> Optional[Signal]:
        """Manage existing volatility positions"""
        for pos_id, position in self.active_positions.items():
            # Update position metrics
            position.current_iv = metrics.implied_volatility
            position.days_held = (datetime.now() - position.entry_date).days
            
            # Check exit conditions
            if position.current_iv <= position.target_iv:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Target reached",
                    metadata={'final_iv': position.current_iv}
                )
            
            elif position.current_iv >= position.stop_iv:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Stop loss",
                    metadata={'final_iv': position.current_iv}
                )
            
            elif position.days_held >= position.trade_type.time_horizon:
                return Signal(
                    action="CLOSE",
                    position_id=pos_id,
                    reason="Time exit",
                    metadata={'final_iv': position.current_iv}
                )
        
        return None
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics"""
        return {
            'strategy': self.strategy_name,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / max(1, self.total_trades),
            'total_pnl': self.total_pnl,
            'sharpe_ratio': self.sharpe_ratio,
            'active_positions': len(self.active_positions),
            'current_regime': self.current_metrics.regime.value if self.current_metrics else "UNKNOWN",
            'current_iv': self.current_metrics.implied_volatility if self.current_metrics else 0,
            'iv_rank': self.current_metrics.iv_rank if self.current_metrics else 50
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_adaptive_volatility_strategy(config: Optional[Dict[str, Any]] = None) -> AdaptiveVolatilityStrategy:
    """Factory function to create AdaptiveVolatilityStrategy instance"""
    return AdaptiveVolatilityStrategy(config)
