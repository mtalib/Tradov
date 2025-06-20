#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderF09_EntryFilters.py
Group: F (Analysis)
Purpose: Consolidated entry criteria checking

Description:
    This module consolidates all entry filters and criteria from the research
    into a single, easy-to-use interface. It checks market conditions, technical
    indicators, volatility levels, and timing constraints to determine if
    conditions are favorable for entering trades.

Author: Mohamed Talib
Date: 2025-06-06
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderF_Analysis.SpyderF08_VolatilityRegime import (
    VolatilityRegimeAnalyzer, VolatilityRegime
)
from SpyderF_Analysis.SpyderF07_GapAnalyzer import GapAnalyzer, GapType
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Time windows (ET)
OPTIMAL_ENTRY_START = time(10, 15)
OPTIMAL_ENTRY_END = time(11, 40)
TIME_BASED_EXIT = time(12, 0)
EARLY_CLOSE_TIME = time(15, 30)  # 30 minutes before close

# Research-based thresholds
IV_PERCENTILE_MIN = 50          # Minimum IV percentile at 9:35 AM
OVERNIGHT_GAP_MAX = 0.003       # 0.3% maximum gap
RSI_MIN = 30
RSI_MAX = 70
PRICE_TO_MA_MAX = 0.005         # 0.5% from 10-day MA
VIX_MIN = 15
VIX_MAX = 30

# Day quality scores (from research)
DAY_QUALITY_SCORES = {
    0: 1.0,   # Monday - highest
    1: 0.4,   # Tuesday
    2: 0.5,   # Wednesday
    3: 0.4,   # Thursday
    4: 0.3    # Friday - lowest
}

# ==============================================================================
# ENUMS
# ==============================================================================
class FilterResult(Enum):
    """Filter check results"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"

class EntryQuality(Enum):
    """Overall entry quality assessment"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    REJECT = "reject"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FilterCheck:
    """Individual filter check result"""
    name: str
    result: FilterResult
    value: Any
    threshold: Any
    reason: str
    weight: float = 1.0

@dataclass
class EntryAssessment:
    """Complete entry assessment results"""
    timestamp: datetime
    symbol: str
    strategy: str
    overall_quality: EntryQuality
    overall_score: float
    can_enter: bool
    filter_results: List[FilterCheck]
    passed_filters: int
    total_filters: int
    warnings: List[str]
    recommendations: List[str]
    position_size_adjustment: float
    
    def get_failed_filters(self) -> List[FilterCheck]:
        """Get list of failed filters"""
        return [f for f in self.filter_results if f.result == FilterResult.FAIL]
    
    def get_warning_filters(self) -> List[FilterCheck]:
        """Get list of warning filters"""
        return [f for f in self.filter_results if f.result == FilterResult.WARNING]

@dataclass
class MarketConditions:
    """Current market conditions snapshot"""
    timestamp: datetime
    spy_price: float
    vix_level: float
    spy_rsi: float
    spy_ma_10: float
    overnight_gap: float
    iv_percentile: float
    market_internals_score: float
    volatility_regime: VolatilityRegime
    is_trending: bool
    trend_strength: float

# ==============================================================================
# ENTRY FILTERS CLASS
# ==============================================================================
class EntryFilters:
    """
    Consolidated entry criteria checking system.
    
    Implements all research-based entry filters including:
    - Day of week quality
    - Optimal entry time windows
    - IV percentile requirements
    - Overnight gap limits
    - RSI boundaries
    - Price relative to moving average
    - VIX range requirements
    - Market internals confirmation
    """
    
    def __init__(self, 
                 volatility_analyzer: Optional[VolatilityRegimeAnalyzer] = None,
                 gap_analyzer: Optional[GapAnalyzer] = None,
                 market_internals: Optional[MarketInternals] = None,
                 indicators: Optional[TechnicalIndicators] = None):
        """
        Initialize entry filters.
        
        Args:
            volatility_analyzer: Volatility regime analyzer
            gap_analyzer: Gap analyzer
            market_internals: Market internals tracker
            indicators: Technical indicators calculator
        """
        self.volatility_analyzer = volatility_analyzer
        self.gap_analyzer = gap_analyzer
        self.market_internals = market_internals
        self.indicators = indicators
        
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Filter weights for scoring
        self.filter_weights = {
            'day_of_week': 2.0,      # Double weight for day
            'entry_time': 1.5,       # Important timing
            'iv_percentile': 1.5,    # Critical filter
            'overnight_gap': 1.0,
            'rsi_range': 1.0,
            'price_ma_distance': 0.8,
            'vix_range': 1.0,
            'market_internals': 0.8,
            'volatility_regime': 1.2,
            'trend_alignment': 0.6
        }
        
        self.logger.info("EntryFilters initialized")
    
    # ==========================================================================
    # MAIN ASSESSMENT METHOD
    # ==========================================================================
    def assess_entry(self, symbol: str = 'SPY', strategy: str = 'iron_condor',
                    custom_filters: Optional[Dict[str, Any]] = None) -> EntryAssessment:
        """
        Perform complete entry assessment.
        
        Args:
            symbol: Symbol to assess (default SPY)
            strategy: Strategy being considered
            custom_filters: Optional custom filter overrides
            
        Returns:
            EntryAssessment with complete results
        """
        try:
            # Get current market conditions
            conditions = self._get_market_conditions(symbol)
            
            # Run all filters
            filter_results = []
            
            # 1. Day of week filter
            filter_results.append(self._check_day_of_week())
            
            # 2. Entry time window
            filter_results.append(self._check_entry_time())
            
            # 3. IV percentile
            filter_results.append(self._check_iv_percentile(symbol, conditions))
            
            # 4. Overnight gap
            filter_results.append(self._check_overnight_gap(symbol, conditions))
            
            # 5. RSI range
            filter_results.append(self._check_rsi_range(symbol, conditions))
            
            # 6. Price to MA distance
            filter_results.append(self._check_price_ma_distance(symbol, conditions))
            
            # 7. VIX range
            filter_results.append(self._check_vix_range(conditions))
            
            # 8. Market internals (if available)
            if self.market_internals:
                filter_results.append(self._check_market_internals())
            
            # 9. Volatility regime
            if self.volatility_analyzer:
                filter_results.append(self._check_volatility_regime(strategy))
            
            # 10. Trend alignment
            filter_results.append(self._check_trend_alignment(symbol, conditions))
            
            # Apply custom filters if provided
            if custom_filters:
                for name, config in custom_filters.items():
                    filter_results.append(self._apply_custom_filter(name, config))
            
            # Calculate overall assessment
            assessment = self._calculate_overall_assessment(
                symbol, strategy, conditions, filter_results
            )
            
            return assessment
            
        except Exception as e:
            self.logger.error(f"Error in entry assessment: {e}")
            self.error_handler.handle_error(e, "assess_entry")
            return self._get_error_assessment(symbol, strategy, str(e))
    
    # ==========================================================================
    # INDIVIDUAL FILTER CHECKS
    # ==========================================================================
    def _check_day_of_week(self) -> FilterCheck:
        """Check day of week quality"""
        current_day = datetime.now().weekday()
        quality_score = DAY_QUALITY_SCORES.get(current_day, 0.5)
        
        if current_day == 0:  # Monday
            result = FilterResult.PASS
            reason = "Monday - optimal trading day"
        elif quality_score >= 0.4:
            result = FilterResult.WARNING
            reason = f"{self._get_day_name(current_day)} - reduced opportunity"
        else:
            result = FilterResult.WARNING
            reason = f"{self._get_day_name(current_day)} - lowest quality day"
        
        return FilterCheck(
            name="day_of_week",
            result=result,
            value=self._get_day_name(current_day),
            threshold="Monday preferred",
            reason=reason,
            weight=self.filter_weights['day_of_week']
        )
    
    def _check_entry_time(self) -> FilterCheck:
        """Check if within optimal entry time window"""
        current_time = datetime.now().time()
        
        if OPTIMAL_ENTRY_START <= current_time <= OPTIMAL_ENTRY_END:
            result = FilterResult.PASS
            reason = "Within optimal entry window"
        elif current_time < OPTIMAL_ENTRY_START:
            result = FilterResult.WARNING
            reason = "Before optimal window - consider waiting"
        elif current_time > TIME_BASED_EXIT:
            result = FilterResult.FAIL
            reason = "Past recommended entry time"
        else:
            result = FilterResult.WARNING
            reason = "Outside optimal window but acceptable"
        
        return FilterCheck(
            name="entry_time",
            result=result,
            value=current_time.strftime("%H:%M"),
            threshold=f"{OPTIMAL_ENTRY_START.strftime('%H:%M')}-{OPTIMAL_ENTRY_END.strftime('%H:%M')}",
            reason=reason,
            weight=self.filter_weights['entry_time']
        )
    
    def _check_iv_percentile(self, symbol: str, conditions: MarketConditions) -> FilterCheck:
        """Check IV percentile requirement"""
        iv_percentile = conditions.iv_percentile
        
        # Special check for 9:35 AM
        current_time = datetime.now().time()
        if time(9, 30) <= current_time <= time(9, 40):
            threshold = IV_PERCENTILE_MIN
        else:
            threshold = 40  # More lenient later
        
        if iv_percentile >= threshold:
            result = FilterResult.PASS
            reason = f"IV percentile {iv_percentile:.1f}% above threshold"
        elif iv_percentile >= threshold - 10:
            result = FilterResult.WARNING
            reason = f"IV percentile {iv_percentile:.1f}% slightly below threshold"
        else:
            result = FilterResult.FAIL
            reason = f"IV percentile {iv_percentile:.1f}% too low"
        
        return FilterCheck(
            name="iv_percentile",
            result=result,
            value=f"{iv_percentile:.1f}%",
            threshold=f"{threshold}%",
            reason=reason,
            weight=self.filter_weights['iv_percentile']
        )
    
    def _check_overnight_gap(self, symbol: str, conditions: MarketConditions) -> FilterCheck:
        """Check overnight gap size"""
        gap = abs(conditions.overnight_gap)
        
        if gap <= OVERNIGHT_GAP_MAX:
            result = FilterResult.PASS
            reason = f"Gap {gap:.2%} within limits"
        elif gap <= OVERNIGHT_GAP_MAX * 1.5:
            result = FilterResult.WARNING
            reason = f"Gap {gap:.2%} elevated"
        else:
            result = FilterResult.FAIL
            reason = f"Gap {gap:.2%} too large"
        
        return FilterCheck(
            name="overnight_gap",
            result=result,
            value=f"{conditions.overnight_gap:+.2%}",
            threshold=f"±{OVERNIGHT_GAP_MAX:.1%}",
            reason=reason,
            weight=self.filter_weights['overnight_gap']
        )
    
    def _check_rsi_range(self, symbol: str, conditions: MarketConditions) -> FilterCheck:
        """Check RSI boundaries"""
        rsi = conditions.spy_rsi
        
        if RSI_MIN <= rsi <= RSI_MAX:
            result = FilterResult.PASS
            reason = f"RSI {rsi:.1f} in neutral range"
        elif rsi < RSI_MIN - 5 or rsi > RSI_MAX + 5:
            result = FilterResult.FAIL
            reason = f"RSI {rsi:.1f} in extreme zone"
        else:
            result = FilterResult.WARNING
            reason = f"RSI {rsi:.1f} approaching extreme"
        
        return FilterCheck(
            name="rsi_range",
            result=result,
            value=f"{rsi:.1f}",
            threshold=f"{RSI_MIN}-{RSI_MAX}",
            reason=reason,
            weight=self.filter_weights['rsi_range']
        )
    
    def _check_price_ma_distance(self, symbol: str, conditions: MarketConditions) -> FilterCheck:
        """Check price distance from 10-day MA"""
        price = conditions.spy_price
        ma_10 = conditions.spy_ma_10
        
        if ma_10 > 0:
            distance = abs(price - ma_10) / ma_10
        else:
            distance = 0
        
        if distance <= PRICE_TO_MA_MAX:
            result = FilterResult.PASS
            reason = f"Price {distance:.2%} from MA"
        elif distance <= PRICE_TO_MA_MAX * 2:
            result = FilterResult.WARNING
            reason = f"Price {distance:.2%} extended from MA"
        else:
            result = FilterResult.FAIL
            reason = f"Price {distance:.2%} too far from MA"
        
        return FilterCheck(
            name="price_ma_distance",
            result=result,
            value=f"{distance:.2%}",
            threshold=f"{PRICE_TO_MA_MAX:.1%}",
            reason=reason,
            weight=self.filter_weights['price_ma_distance']
        )
    
    def _check_vix_range(self, conditions: MarketConditions) -> FilterCheck:
        """Check VIX level requirements"""
        vix = conditions.vix_level
        
        if VIX_MIN <= vix <= VIX_MAX:
            result = FilterResult.PASS
            reason = f"VIX {vix:.1f} in optimal range"
        elif vix < VIX_MIN:
            result = FilterResult.WARNING
            reason = f"VIX {vix:.1f} low - reduced premiums"
        elif vix > VIX_MAX:
            result = FilterResult.WARNING
            reason = f"VIX {vix:.1f} elevated - higher risk"
        else:
            result = FilterResult.FAIL
            reason = f"VIX {vix:.1f} extreme"
        
        return FilterCheck(
            name="vix_range",
            result=result,
            value=f"{vix:.1f}",
            threshold=f"{VIX_MIN}-{VIX_MAX}",
            reason=reason,
            weight=self.filter_weights['vix_range']
        )
    
    def _check_market_internals(self) -> FilterCheck:
        """Check market internals confirmation"""
        if not self.market_internals:
            return FilterCheck(
                name="market_internals",
                result=FilterResult.SKIP,
                value="N/A",
                threshold="Positive",
                reason="Market internals not available",
                weight=self.filter_weights['market_internals']
            )
        
        strength = self.market_internals.get_strength_score()
        
        if -20 <= strength <= 20:
            result = FilterResult.PASS
            reason = "Market internals neutral"
        elif abs(strength) <= 40:
            result = FilterResult.WARNING
            reason = f"Market internals {strength:.0f} - moderate bias"
        else:
            result = FilterResult.FAIL
            reason = f"Market internals {strength:.0f} - extreme"
        
        return FilterCheck(
            name="market_internals",
            result=result,
            value=f"{strength:.0f}",
            threshold="±20",
            reason=reason,
            weight=self.filter_weights['market_internals']
        )
    
    def _check_volatility_regime(self, strategy: str) -> FilterCheck:
        """Check volatility regime suitability"""
        if not self.volatility_analyzer:
            return FilterCheck(
                name="volatility_regime",
                result=FilterResult.SKIP,
                value="N/A",
                threshold="Suitable",
                reason="Volatility analyzer not available",
                weight=self.filter_weights['volatility_regime']
            )
        
        regime = self.volatility_analyzer.get_current_regime()
        recommended = self.volatility_analyzer.get_recommended_strategies()
        
        if strategy.lower() in [s.lower() for s in recommended]:
            result = FilterResult.PASS
            reason = f"{regime.value} regime suitable for {strategy}"
        elif regime == VolatilityRegime.TRANSITIONING:
            result = FilterResult.WARNING
            reason = "Regime transitioning - use caution"
        else:
            result = FilterResult.WARNING
            reason = f"{regime.value} regime - consider alternatives"
        
        return FilterCheck(
            name="volatility_regime",
            result=result,
            value=regime.value,
            threshold="Suitable for strategy",
            reason=reason,
            weight=self.filter_weights['volatility_regime']
        )
    
    def _check_trend_alignment(self, symbol: str, conditions: MarketConditions) -> FilterCheck:
        """Check trend alignment"""
        if conditions.is_trending and conditions.trend_strength > 0.7:
            result = FilterResult.WARNING
            reason = f"Strong trend ({conditions.trend_strength:.1%}) - adjust strikes"
        else:
            result = FilterResult.PASS
            reason = "No strong trend - suitable for neutral strategies"
        
        return FilterCheck(
            name="trend_alignment",
            result=result,
            value=f"{conditions.trend_strength:.1%}",
            threshold="< 70%",
            reason=reason,
            weight=self.filter_weights['trend_alignment']
        )
    
    def _apply_custom_filter(self, name: str, config: Dict[str, Any]) -> FilterCheck:
        """Apply custom filter"""
        try:
            value = config.get('value')
            threshold = config.get('threshold')
            operator = config.get('operator', '>=')
            
            # Evaluate condition
            if operator == '>=':
                passed = value >= threshold
            elif operator == '<=':
                passed = value <= threshold
            elif operator == '==':
                passed = value == threshold
            elif operator == '!=':
                passed = value != threshold
            else:
                passed = False
            
            result = FilterResult.PASS if passed else FilterResult.FAIL
            reason = f"Custom: {name} {operator} {threshold}"
            
            return FilterCheck(
                name=f"custom_{name}",
                result=result,
                value=value,
                threshold=threshold,
                reason=reason,
                weight=config.get('weight', 1.0)
            )
            
        except Exception as e:
            return FilterCheck(
                name=f"custom_{name}",
                result=FilterResult.FAIL,
                value="Error",
                threshold="N/A",
                reason=f"Custom filter error: {e}",
                weight=1.0
            )
    
    # ==========================================================================
    # MARKET CONDITIONS
    # ==========================================================================
    def _get_market_conditions(self, symbol: str) -> MarketConditions:
        """Get current market conditions"""
        try:
            # Get SPY price
            spy_price = self._get_current_price(symbol)
            
            # Get VIX
            vix_level = self._get_vix_level()
            
            # Get RSI
            spy_rsi = self._get_rsi(symbol)
            
            # Get MA
            spy_ma_10 = self._get_ma(symbol, 10)
            
            # Get overnight gap
            overnight_gap = self._get_overnight_gap(symbol)
            
            # Get IV percentile
            iv_percentile = self._get_iv_percentile(symbol)
            
            # Get market internals score
            internals_score = self._get_internals_score()
            
            # Get volatility regime
            vol_regime = self._get_volatility_regime()
            
            # Check trend
            is_trending, trend_strength = self._check_trend(symbol)
            
            return MarketConditions(
                timestamp=datetime.now(),
                spy_price=spy_price,
                vix_level=vix_level,
                spy_rsi=spy_rsi,
                spy_ma_10=spy_ma_10,
                overnight_gap=overnight_gap,
                iv_percentile=iv_percentile,
                market_internals_score=internals_score,
                volatility_regime=vol_regime,
                is_trending=is_trending,
                trend_strength=trend_strength
            )
            
        except Exception as e:
            self.logger.error(f"Error getting market conditions: {e}")
            # Return default conditions
            return self._get_default_conditions()
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price"""
        # In production, would get from data feed
        # Placeholder for now
        return 450.0
    
    def _get_vix_level(self) -> float:
        """Get current VIX level"""
        if self.volatility_analyzer and self.volatility_analyzer.current_analysis:
            return self.volatility_analyzer.current_analysis.vix_level
        return 16.0  # Default
    
    def _get_rsi(self, symbol: str) -> float:
        """Get current RSI"""
        if self.indicators:
            return self.indicators.get_rsi(symbol)
        return 50.0  # Default neutral
   
    
    def _get_ma(self, symbol: str, period: int) -> float:
        """Get moving average"""
        if self.indicators:
            return self.indicators.get_sma(symbol, period)
        return self._get_current_price(symbol)  # Default to current price
    
    def _get_overnight_gap(self, symbol: str) -> float:
        """Get overnight gap percentage"""
        if self.gap_analyzer:
            gap_data = self.gap_analyzer.get_latest_gap(symbol)
            if gap_data:
                return gap_data.gap_percent
        return 0.0  # Default no gap
    
    def _get_iv_percentile(self, symbol: str) -> float:
        """Get IV percentile"""
        if self.volatility_analyzer:
            return self.volatility_analyzer.get_iv_percentile(symbol)
        return 50.0  # Default middle
    
    def _get_internals_score(self) -> float:
        """Get market internals strength score"""
        if self.market_internals:
            return self.market_internals.get_strength_score()
        return 0.0  # Default neutral
    
    def _get_volatility_regime(self) -> VolatilityRegime:
        """Get current volatility regime"""
        if self.volatility_analyzer:
            return self.volatility_analyzer.get_current_regime()
        return VolatilityRegime.NORMAL  # Default
    
    def _check_trend(self, symbol: str) -> Tuple[bool, float]:
        """Check if trending and trend strength"""
        if self.indicators:
            # Simple trend check using MAs
            ma_20 = self.indicators.get_sma(symbol, 20)
            ma_50 = self.indicators.get_sma(symbol, 50)
            price = self._get_current_price(symbol)
            
            if ma_20 > 0 and ma_50 > 0:
                # Calculate trend strength
                ma_diff = abs(ma_20 - ma_50) / ma_50
                price_diff = abs(price - ma_20) / ma_20
                
                trend_strength = (ma_diff + price_diff) / 2
                is_trending = trend_strength > 0.02  # 2% threshold
                
                return is_trending, trend_strength
        
        return False, 0.0
    
    def _get_default_conditions(self) -> MarketConditions:
        """Get default market conditions for error cases"""
        return MarketConditions(
            timestamp=datetime.now(),
            spy_price=450.0,
            vix_level=16.0,
            spy_rsi=50.0,
            spy_ma_10=450.0,
            overnight_gap=0.0,
            iv_percentile=50.0,
            market_internals_score=0.0,
            volatility_regime=VolatilityRegime.NORMAL,
            is_trending=False,
            trend_strength=0.0
        )
    
    # ==========================================================================
    # ASSESSMENT CALCULATION
    # ==========================================================================
    def _calculate_overall_assessment(self, symbol: str, strategy: str,
                                    conditions: MarketConditions,
                                    filter_results: List[FilterCheck]) -> EntryAssessment:
        """Calculate overall entry assessment"""
        # Count results
        passed = sum(1 for f in filter_results if f.result == FilterResult.PASS)
        failed = sum(1 for f in filter_results if f.result == FilterResult.FAIL)
        warnings = sum(1 for f in filter_results if f.result == FilterResult.WARNING)
        total = len([f for f in filter_results if f.result != FilterResult.SKIP])
        
        # Calculate weighted score
        total_score = 0.0
        total_weight = 0.0
        
        for filter_check in filter_results:
            if filter_check.result == FilterResult.SKIP:
                continue
            
            # Score based on result
            if filter_check.result == FilterResult.PASS:
                score = 1.0
            elif filter_check.result == FilterResult.WARNING:
                score = 0.5
            else:  # FAIL
                score = 0.0
            
            weighted_score = score * filter_check.weight
            total_score += weighted_score
            total_weight += filter_check.weight
        
        # Normalize score
        overall_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Determine quality
        if failed > 0:
            overall_quality = EntryQuality.REJECT
            can_enter = False
        elif overall_score >= 0.85:
            overall_quality = EntryQuality.EXCELLENT
            can_enter = True
        elif overall_score >= 0.70:
            overall_quality = EntryQuality.GOOD
            can_enter = True
        elif overall_score >= 0.55:
            overall_quality = EntryQuality.ACCEPTABLE
            can_enter = True
        else:
            overall_quality = EntryQuality.POOR
            can_enter = False
        
        # Generate warnings
        warning_messages = self._generate_warnings(filter_results, conditions)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            filter_results, conditions, strategy
        )
        
        # Calculate position size adjustment
        position_adjustment = self._calculate_position_adjustment(
            overall_score, filter_results, conditions
        )
        
        return EntryAssessment(
            timestamp=datetime.now(),
            symbol=symbol,
            strategy=strategy,
            overall_quality=overall_quality,
            overall_score=overall_score,
            can_enter=can_enter,
            filter_results=filter_results,
            passed_filters=passed,
            total_filters=total,
            warnings=warning_messages,
            recommendations=recommendations,
            position_size_adjustment=position_adjustment
        )
    
    def _generate_warnings(self, filter_results: List[FilterCheck],
                          conditions: MarketConditions) -> List[str]:
        """Generate warning messages"""
        warnings = []
        
        # Check specific warning conditions
        for filter_check in filter_results:
            if filter_check.result == FilterResult.WARNING:
                if filter_check.name == "day_of_week":
                    warnings.append(f"Non-Monday trade - consider reduced position size")
                elif filter_check.name == "entry_time":
                    warnings.append(f"Outside optimal entry window - monitor closely")
                elif filter_check.name == "iv_percentile":
                    warnings.append(f"IV percentile below ideal - premiums may be low")
                elif filter_check.name == "vix_range":
                    if conditions.vix_level > VIX_MAX:
                        warnings.append(f"Elevated VIX - consider wider strikes")
                    else:
                        warnings.append(f"Low VIX - expect smaller premiums")
        
        # Add volatility regime warnings
        if conditions.volatility_regime == VolatilityRegime.TRANSITIONING:
            warnings.append("Volatility regime transitioning - use extra caution")
        
        # Market internals warning
        if abs(conditions.market_internals_score) > 40:
            direction = "bullish" if conditions.market_internals_score > 0 else "bearish"
            warnings.append(f"Strong {direction} internals - market bias present")
        
        return warnings
    
    def _generate_recommendations(self, filter_results: List[FilterCheck],
                                 conditions: MarketConditions,
                                 strategy: str) -> List[str]:
        """Generate trading recommendations"""
        recommendations = []
        
        # Day-based recommendations
        day_filter = next((f for f in filter_results if f.name == "day_of_week"), None)
        if day_filter and day_filter.result != FilterResult.PASS:
            recommendations.append("Consider waiting for Monday for better opportunities")
            recommendations.append("If entering today, use 50% reduced position size")
        
        # Time-based recommendations
        time_filter = next((f for f in filter_results if f.name == "entry_time"), None)
        if time_filter:
            current_time = datetime.now().time()
            if current_time < OPTIMAL_ENTRY_START:
                wait_minutes = (
                    datetime.combine(date.today(), OPTIMAL_ENTRY_START) -
                    datetime.combine(date.today(), current_time)
                ).seconds // 60
                recommendations.append(f"Consider waiting {wait_minutes} minutes for optimal window")
            elif current_time > OPTIMAL_ENTRY_END:
                recommendations.append("Set exit target for 12:00 PM ET")
        
        # Volatility-based recommendations
        if conditions.volatility_regime == VolatilityRegime.HIGH:
            recommendations.append("Widen strikes due to high volatility")
            recommendations.append("Consider reducing position size by 20%")
        elif conditions.volatility_regime == VolatilityRegime.LOW:
            recommendations.append("Consider Iron Butterfly for low volatility")
            recommendations.append("May need to go closer to the money for premium")
        
        # RSI-based recommendations
        if conditions.spy_rsi > 65:
            recommendations.append("RSI elevated - favor call credit spreads")
        elif conditions.spy_rsi < 35:
            recommendations.append("RSI oversold - favor put credit spreads")
        
        # Gap-based recommendations
        if abs(conditions.overnight_gap) > 0.002:
            recommendations.append("Gap present - wait for first hour to settle")
        
        # Strategy-specific recommendations
        if strategy.lower() == "iron_condor":
            if conditions.vix_level < 15:
                recommendations.append("Low VIX - consider Iron Butterfly instead")
            recommendations.append("Target 50% of credit received (research-based)")
        elif strategy.lower() == "iron_butterfly":
            recommendations.append("Target 15% of max profit for quick exit")
        
        return recommendations[:5]  # Limit to top 5
    
    def _calculate_position_adjustment(self, overall_score: float,
                                     filter_results: List[FilterCheck],
                                     conditions: MarketConditions) -> float:
        """Calculate position size adjustment factor"""
        base_adjustment = 1.0
        
        # Day of week adjustment (most important)
        day_filter = next((f for f in filter_results if f.name == "day_of_week"), None)
        if day_filter:
            current_day = datetime.now().weekday()
            if current_day != 0:  # Not Monday
                base_adjustment *= 0.5  # 50% reduction
        
        # Score-based adjustment
        if overall_score < 0.6:
            base_adjustment *= 0.7
        elif overall_score < 0.7:
            base_adjustment *= 0.85
        elif overall_score > 0.85:
            base_adjustment *= 1.1
        
        # Volatility regime adjustment
        if self.volatility_analyzer:
            vol_adjustment = self.volatility_analyzer.get_position_size_factor()
            base_adjustment *= vol_adjustment
        
        # Time-based adjustment
        current_time = datetime.now().time()
        if current_time > TIME_BASED_EXIT:
            base_adjustment *= 0.5  # Late entry penalty
        
        # Cap adjustments
        return max(0.3, min(1.5, base_adjustment))
    
    def _get_error_assessment(self, symbol: str, strategy: str, error: str) -> EntryAssessment:
        """Get error assessment when something fails"""
        return EntryAssessment(
            timestamp=datetime.now(),
            symbol=symbol,
            strategy=strategy,
            overall_quality=EntryQuality.REJECT,
            overall_score=0.0,
            can_enter=False,
            filter_results=[
                FilterCheck(
                    name="error",
                    result=FilterResult.FAIL,
                    value=error,
                    threshold="N/A",
                    reason=f"Assessment error: {error}",
                    weight=1.0
                )
            ],
            passed_filters=0,
            total_filters=1,
            warnings=[f"Entry assessment failed: {error}"],
            recommendations=["Fix errors before attempting entry"],
            position_size_adjustment=0.0
        )
    
    def _get_day_name(self, weekday: int) -> str:
        """Get day name from weekday number"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[weekday] if 0 <= weekday < 7 else 'Unknown'
    
    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================
    def get_quick_check(self, symbol: str = 'SPY') -> Dict[str, bool]:
        """
        Perform quick entry check for key filters.
        
        Returns:
            Dict with pass/fail for critical filters
        """
        current_time = datetime.now().time()
        current_day = datetime.now().weekday()
        
        return {
            'is_monday': current_day == 0,
            'in_time_window': OPTIMAL_ENTRY_START <= current_time <= OPTIMAL_ENTRY_END,
            'before_exit_time': current_time < TIME_BASED_EXIT,
            'market_hours': time(9, 30) <= current_time <= time(16, 0)
        }
    
    def should_exit_by_time(self) -> bool:
        """Check if position should be exited based on time"""
        return datetime.now().time() >= TIME_BASED_EXIT
    
    def get_time_until_optimal_window(self) -> Optional[int]:
        """Get minutes until optimal entry window opens"""
        current_time = datetime.now().time()
        
        if current_time < OPTIMAL_ENTRY_START:
            current_dt = datetime.combine(date.today(), current_time)
            optimal_dt = datetime.combine(date.today(), OPTIMAL_ENTRY_START)
            return int((optimal_dt - current_dt).total_seconds() / 60)
        
        return None
    
    def get_position_size_for_day(self) -> float:
        """Get position size multiplier for current day"""
        current_day = datetime.now().weekday()
        
        if current_day == 0:  # Monday
            return 1.0
        else:
            return 0.5  # 50% for other days
    
    def format_assessment_summary(self, assessment: EntryAssessment) -> str:
        """Format assessment results as readable summary"""
        lines = [
            f"Entry Assessment for {assessment.symbol} - {assessment.strategy}",
            f"{'=' * 50}",
            f"Overall Quality: {assessment.overall_quality.value.upper()}",
            f"Score: {assessment.overall_score:.1%}",
            f"Can Enter: {'YES' if assessment.can_enter else 'NO'}",
            f"Filters Passed: {assessment.passed_filters}/{assessment.total_filters}",
            f"Position Size Adjustment: {assessment.position_size_adjustment:.1%}",
            ""
        ]
        
        # Add failed filters
        failed = assessment.get_failed_filters()
        if failed:
            lines.append("Failed Filters:")
            for f in failed:
                lines.append(f"  ❌ {f.name}: {f.reason}")
            lines.append("")
        
        # Add warnings
        if assessment.warnings:
            lines.append("Warnings:")
            for warning in assessment.warnings:
                lines.append(f"  ⚠️  {warning}")
            lines.append("")
        
        # Add recommendations
        if assessment.recommendations:
            lines.append("Recommendations:")
            for i, rec in enumerate(assessment.recommendations, 1):
                lines.append(f"  {i}. {rec}")
        
        return "\n".join(lines)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the entry filters
    from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
    from SpyderF_Analysis.SpyderF07_GapAnalyzer import GapAnalyzer
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    
    # Create components
    event_manager = EventManager()
    volatility_analyzer = VolatilityRegimeAnalyzer(event_manager)
    gap_analyzer = GapAnalyzer(event_manager)
    
    # Start analyzers
    volatility_analyzer.start()
    gap_analyzer.start()
    
    # Create entry filters
    filters = EntryFilters(
        volatility_analyzer=volatility_analyzer,
        gap_analyzer=gap_analyzer
    )
    
    # Perform assessment
    print("Performing entry assessment for SPY Iron Condor...")
    print("=" * 60)
    
    assessment = filters.assess_entry('SPY', 'iron_condor')
    
    # Print formatted summary
    print(filters.format_assessment_summary(assessment))
    
    # Quick checks
    print("\nQuick Checks:")
    quick = filters.get_quick_check()
    for check, passed in quick.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check}: {passed}")
    
    # Time checks
    minutes_to_window = filters.get_time_until_optimal_window()
    if minutes_to_window:
        print(f"\n⏰ {minutes_to_window} minutes until optimal entry window")
    
    # Position sizing
    day_size = filters.get_position_size_for_day()
    print(f"\n💰 Position size for today: {day_size:.0%}")
    
    # Test custom filters
    print("\nTesting with custom filters...")
    custom = {
        'min_volume': {
            'value': 1000000,
            'threshold': 500000,
            'operator': '>=',
            'weight': 1.0
        }
    }
    
    assessment2 = filters.assess_entry('SPY', 'iron_condor', custom)
    print(f"With custom filter - Score: {assessment2.overall_score:.1%}")
    
    # Stop analyzers
    volatility_analyzer.stop()
    gap_analyzer.stop()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
