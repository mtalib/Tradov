#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE02_PositionSizer.py
Group: E (Risk Management)
Purpose: Professional position sizing with Kelly Criterion

Description:
Enhanced position sizing module implementing institutional-grade
    methodologies including Kelly Criterion (25-50% of optimal), volatility-based
    sizing, VIX regime adjustments, and day-of-week research integration.
    Provides real-time position sizing with professional risk controls.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import calendar
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderC_MarketData.SpyderC01_DataFeed import MarketDataFeed

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
KELLY_REDUCTION_FACTOR = 0.375      # 37.5% of full Kelly (institutional standard)
MIN_KELLY_REDUCTION = 0.25          # Minimum 25% of Kelly
MAX_KELLY_REDUCTION = 0.50          # Maximum 50% of Kelly
DEFAULT_RISK_PER_TRADE = 0.02       # 2% default risk per trade
MAX_POSITION_SIZE = 0.10            # 10% maximum position size
MIN_POSITION_SIZE = 0.005           # 0.5% minimum position size
MAX_DAILY_RISK = 0.05               # 5% maximum daily risk exposure
MONDAY_MIN_POSITION_PCT = 0.01      # 1% minimum Monday position
MONDAY_MAX_POSITION_PCT = 0.05      # 5% maximum Monday position
OTHER_DAYS_MIN_PCT = 0.005          # 0.5% minimum other days
OTHER_DAYS_MAX_PCT = 0.025          # 2.5% maximum other days
VIX_LOW_THRESHOLD = 16.0            # Below 16 = low volatility regime
VIX_NORMAL_THRESHOLD = 25.0         # Above 25 = high volatility regime
VIX_HIGH_REDUCTION_FACTOR = 0.5     # 50% size reduction when VIX > 25
VIX_EXTREME_THRESHOLD = 30.0        # Above 30 = extreme volatility
VIX_EXTREME_REDUCTION = 0.25        # 75% size reduction when VIX > 30
ATR_MULTIPLIER = 2.0                # ATR multiplier for volatility sizing
ATR_PERIOD = 14                     # 14-day ATR calculation
MAX_CONSECUTIVE_LOSSES = 3          # Reduce size after 3 consecutive losses
LOSS_STREAK_REDUCTION = 0.5         # 50% size reduction during loss streaks
class SizingMethod(Enum):
    """Position sizing methodologies"""
    KELLY_CRITERION = "kelly_criterion"
    FIXED_FRACTIONAL = "fixed_fractional"
    VOLATILITY_BASED = "volatility_based"
    RISK_PARITY = "risk_parity"
    PROFESSIONAL_HYBRID = "professional_hybrid"
class MarketRegime(Enum):
    """Market volatility regimes"""
    LOW_VOLATILITY = auto()      # VIX < 16
    NORMAL_VOLATILITY = auto()   # VIX 16-25
    HIGH_VOLATILITY = auto()     # VIX 25-30
    EXTREME_VOLATILITY = auto()  # VIX > 30
class DayOfWeekEffect(Enum):
    """Day of week trading effects"""
    MONDAY = auto()              # Higher volatility, larger positions allowed
    TUESDAY = auto()             # Normal trading
    WEDNESDAY = auto()           # Normal trading
    THURSDAY = auto()            # Normal trading
    FRIDAY = auto()              # End of week effects
@dataclass
class StrategyStats:
    """Strategy performance statistics for Kelly Criterion"""
    win_rate: float              # Probability of winning trade
    avg_win: float              # Average winning trade return
    avg_loss: float             # Average losing trade return (negative)
    trade_count: int            # Number of trades
    consecutive_losses: int     # Current consecutive losses
    max_drawdown: float         # Maximum historical drawdown
    sharpe_ratio: float         # Risk-adjusted returns
    def kelly_percentage(self) -> float:
        """Calculate Kelly Criterion percentage"""
        if self.avg_loss >= 0:  # Prevent division by zero
            return 0.0
        # Kelly formula: f* = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
        b = abs(self.avg_win / self.avg_loss) if self.avg_loss != 0 else 0
        p = self.win_rate
        q = 1 - self.win_rate
        kelly_pct = (b * p - q) / b if b > 0 else 0
        return max(0, kelly_pct)  # Kelly can't be negative
@dataclass
class MarketConditions:
    """Current market conditions for sizing adjustments"""
    vix_level: float
    spy_atr_14: float            # 14-day ATR of SPY
    realized_volatility: float   # Recent realized volatility
    market_regime: MarketRegime
    day_of_week: DayOfWeekEffect
    time_to_expiry: Optional[int] = None  # Days to expiration for options
    def get_vix_adjustment_factor(self) -> float:
        """Get position size adjustment based on VIX"""
        if self.vix_level > VIX_EXTREME_THRESHOLD:
            return VIX_EXTREME_REDUCTION  # 75% reduction
        elif self.vix_level > VIX_NORMAL_THRESHOLD:
            return VIX_HIGH_REDUCTION_FACTOR  # 50% reduction
        else:
            return 1.0  # No adjustment
@dataclass
class PositionSizeRecommendation:
    """Position sizing recommendation"""
    strategy_name: str
    symbol: str
    recommended_size: float      # As percentage of portfolio
    sizing_method: SizingMethod
    # Risk metrics
    expected_risk: float         # Expected risk as % of portfolio
    risk_reward_ratio: float
    win_probability: float
    # Adjustments applied
    base_size: float            # Before adjustments
    kelly_adjustment: float     # Kelly-based adjustment
    vix_adjustment: float       # VIX-based adjustment
    day_adjustment: float       # Day-of-week adjustment
    volatility_adjustment: float # ATR-based adjustment
    streak_adjustment: float    # Consecutive loss adjustment
    # Limits and warnings
    max_allowed_size: float
    size_limited_by: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    # Context
    market_conditions: Optional[MarketConditions] = None
    calculation_timestamp: datetime = field(default_factory=datetime.now)
class PositionSizer:
    """
    Professional position sizing with institutional standards.
    Implements advanced position sizing methodologies including:
    - Kelly Criterion with institutional reduction factors (25-50%)
    - Volatility-based sizing using ATR
    - VIX regime adjustments (50% reduction when VIX > 25)
    - Day-of-week research integration
    - Consecutive loss streak management
    - Professional risk controls
    """
    def __init__(
        self,
        portfolio_value: float,
        volatility_analyzer: VolatilityAnalyzer,
        market_data_feed: MarketDataFeed,
        default_method: SizingMethod = SizingMethod.PROFESSIONAL_HYBRID
    ):
        """Initialize enhanced position sizer."""
        self.portfolio_value = portfolio_value
        self.volatility_analyzer = volatility_analyzer
        self.market_data_feed = market_data_feed
        self.default_method = default_method
        # Logging
        self.logger = SpyderLogger().get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.time_utils = TradingTimeUtils()
        # Strategy performance tracking
        self.strategy_stats: Dict[str, StrategyStats] = {}
        # Current market conditions
        self.current_market_conditions: Optional[MarketConditions] = None
        # Risk limits
        self.max_daily_risk = MAX_DAILY_RISK
        self.current_daily_risk = 0.0
        # Configuration
        self.kelly_reduction_factor = KELLY_REDUCTION_FACTOR
        self.use_day_of_week_adjustments = True
        self.use_vix_adjustments = True
        self.use_volatility_adjustments = True
        self.logger.info(f"Enhanced Position Sizer initialized with ${portfolio_value:,.0f} portfolio")
    # ==========================================================================
    # PUBLIC METHODS - CORE FUNCTIONALITY
    # ==========================================================================
    def calculate_position_size(
        self,
        strategy_name: str,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_profit: Optional[float] = None,
        method: Optional[SizingMethod] = None
    ) -> PositionSizeRecommendation:
        """
        Calculate professional position size with all adjustments.
        Args:
            strategy_name: Strategy identifier for stats tracking
            symbol: Trading symbol (e.g., 'SPY')
            entry_price: Expected entry price
            stop_loss: Stop loss price
            target_profit: Target profit price (optional)
            method: Sizing method override
        Returns:
            Complete position sizing recommendation
        """
        try:
            # Update market conditions
            self._update_market_conditions(symbol)
            # Use specified method or default
            sizing_method = method or self.default_method
            # Calculate base position size
            base_size = self._calculate_base_size(
                strategy_name, symbol, entry_price, stop_loss, 
                target_profit, sizing_method
            )
            # Apply professional adjustments
            recommendation = self._apply_professional_adjustments(
                strategy_name, symbol, base_size, sizing_method,
                entry_price, stop_loss, target_profit
            )
            # Validate and apply limits
            recommendation = self._apply_risk_limits(recommendation)
            return recommendation
        except Exception as e:
            self.error_handler.handle_error(e, "calculate_position_size")
            return self._get_fallback_recommendation(strategy_name, symbol)
    def update_strategy_performance(
        self,
        strategy_name: str,
        trade_result: float,
        was_winner: bool
    ) -> None:
        """Update strategy performance statistics."""
        try:
            if strategy_name not in self.strategy_stats:
                self.strategy_stats[strategy_name] = StrategyStats(
                    win_rate=0.5, avg_win=0.0, avg_loss=0.0, trade_count=0,
                    consecutive_losses=0, max_drawdown=0.0, sharpe_ratio=0.0
                )
            stats = self.strategy_stats[strategy_name]
            # Update trade count
            stats.trade_count += 1
            # Update win/loss tracking
            if was_winner:
                # Update winning stats
                if stats.avg_win == 0:
                    stats.avg_win = trade_result
                else:
                    stats.avg_win = (stats.avg_win * 0.9) + (trade_result * 0.1)  # Exponential smoothing
                # Reset consecutive losses
                stats.consecutive_losses = 0
            else:
                # Update losing stats
                if stats.avg_loss == 0:
                    stats.avg_loss = trade_result
                else:
                    stats.avg_loss = (stats.avg_loss * 0.9) + (trade_result * 0.1)
                # Increment consecutive losses
                stats.consecutive_losses += 1
            # Update win rate with exponential smoothing
            if stats.trade_count == 1:
                stats.win_rate = 1.0 if was_winner else 0.0
            else:
                alpha = 2.0 / (stats.trade_count + 1)  # Exponential smoothing factor
                stats.win_rate = (1 - alpha) * stats.win_rate + alpha * (1.0 if was_winner else 0.0)
            self.logger.info(
                f"Strategy {strategy_name} updated: WR={stats.win_rate:.1%}, "
                f"Trades={stats.trade_count}, Streak={stats.consecutive_losses}"
            )
        except Exception as e:
            self.error_handler.handle_error(e, "update_strategy_performance")
    def get_daily_risk_usage(self) -> Dict[str, float]:
        """Get current daily risk usage."""
        return {
            'current_daily_risk_pct': self.current_daily_risk,
            'max_daily_risk_pct': self.max_daily_risk,
            'remaining_risk_pct': self.max_daily_risk - self.current_daily_risk,
            'risk_utilization': self.current_daily_risk / self.max_daily_risk
        }
    def reset_daily_risk(self) -> None:
        """Reset daily risk tracking (call at start of new trading day)."""
        self.current_daily_risk = 0.0
        self.logger.info("Daily risk tracking reset")
    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def set_kelly_reduction_factor(self, factor: float) -> None:
        """Set Kelly Criterion reduction factor."""
        if MIN_KELLY_REDUCTION <= factor <= MAX_KELLY_REDUCTION:
            self.kelly_reduction_factor = factor
            self.logger.info(f"Kelly reduction factor set to {factor:.1%}")
        else:
            self.logger.warning(f"Invalid Kelly factor {factor:.1%}, must be between {MIN_KELLY_REDUCTION:.1%} and {MAX_KELLY_REDUCTION:.1%}")
    def update_portfolio_value(self, new_value: float) -> None:
        """Update portfolio value."""
        old_value = self.portfolio_value
        self.portfolio_value = new_value
        self.logger.info(f"Portfolio value updated: ${old_value:,.0f} -> ${new_value:,.0f}")
    def enable_day_of_week_adjustments(self, enabled: bool = True) -> None:
        """Enable/disable day-of-week position adjustments."""
        self.use_day_of_week_adjustments = enabled
        self.logger.info(f"Day-of-week adjustments {'enabled' if enabled else 'disabled'}")
    def enable_vix_adjustments(self, enabled: bool = True) -> None:
        """Enable/disable VIX-based position adjustments."""
        self.use_vix_adjustments = enabled
        self.logger.info(f"VIX adjustments {'enabled' if enabled else 'disabled'}")
    # ==========================================================================
    # PRIVATE METHODS - BASE SIZE CALCULATION
    # ==========================================================================
    def _calculate_base_size(
        self,
        strategy_name: str,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_profit: Optional[float],
        method: SizingMethod
    ) -> float:
        """Calculate base position size before adjustments."""
        if method == SizingMethod.KELLY_CRITERION:
            return self._calculate_kelly_size(strategy_name, entry_price, stop_loss, target_profit)
        elif method == SizingMethod.FIXED_FRACTIONAL:
            return self._calculate_fixed_fractional_size(entry_price, stop_loss)
        elif method == SizingMethod.VOLATILITY_BASED:
            return self._calculate_volatility_based_size(symbol, entry_price, stop_loss)
        elif method == SizingMethod.RISK_PARITY:
            return self._calculate_risk_parity_size(symbol, entry_price, stop_loss)
        elif method == SizingMethod.PROFESSIONAL_HYBRID:
            return self._calculate_professional_hybrid_size(
                strategy_name, symbol, entry_price, stop_loss, target_profit
            )
        else:
            return DEFAULT_RISK_PER_TRADE
    def _calculate_kelly_size(
        self,
        strategy_name: str,
        entry_price: float,
        stop_loss: float,
        target_profit: Optional[float]
    ) -> float:
        """Calculate Kelly Criterion position size."""
        if strategy_name not in self.strategy_stats:
            return DEFAULT_RISK_PER_TRADE
        stats = self.strategy_stats[strategy_name]
        # Need minimum trades for Kelly calculation
        if stats.trade_count < 10:
            return DEFAULT_RISK_PER_TRADE
        # Calculate Kelly percentage
        kelly_pct = stats.kelly_percentage()
        if kelly_pct <= 0:
            return MIN_POSITION_SIZE
        # Apply institutional reduction factor (25-50% of full Kelly)
        adjusted_kelly = kelly_pct * self.kelly_reduction_factor
        # Limit to reasonable range
        return max(MIN_POSITION_SIZE, min(MAX_POSITION_SIZE, adjusted_kelly))
    def _calculate_fixed_fractional_size(self, entry_price: float, stop_loss: float) -> float:
        """Calculate fixed fractional position size."""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return DEFAULT_RISK_PER_TRADE
        # Risk 2% of portfolio
        risk_amount = self.portfolio_value * DEFAULT_RISK_PER_TRADE
        position_size_dollars = risk_amount / risk_per_share
        return position_size_dollars / self.portfolio_value
    def _calculate_volatility_based_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """Calculate volatility-based position size using ATR."""
        if not self.current_market_conditions:
            return DEFAULT_RISK_PER_TRADE
        atr = self.current_market_conditions.spy_atr_14
        if atr == 0:
            return DEFAULT_RISK_PER_TRADE
        # Professional formula: Position Size = (Account Risk × Risk %) / (ATR × 2.0)
        account_risk = self.portfolio_value * DEFAULT_RISK_PER_TRADE
        position_size_dollars = account_risk / (atr * ATR_MULTIPLIER)
        return position_size_dollars / self.portfolio_value
    def _calculate_risk_parity_size(self, symbol: str, entry_price: float, stop_loss: float) -> float:
        """Calculate risk parity position size."""
        # Risk parity aims for equal risk contribution
        # Simplified implementation - would be more complex in practice
        return DEFAULT_RISK_PER_TRADE
    def _calculate_professional_hybrid_size(
        self,
        strategy_name: str,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        target_profit: Optional[float]
    ) -> float:
        """Calculate professional hybrid size combining multiple methods."""
        # Combine Kelly (if available), volatility-based, and fixed fractional
        kelly_size = self._calculate_kelly_size(strategy_name, entry_price, stop_loss, target_profit)
        vol_size = self._calculate_volatility_based_size(symbol, entry_price, stop_loss)
        fixed_size = self._calculate_fixed_fractional_size(entry_price, stop_loss)
        # Weight the methods
        if strategy_name in self.strategy_stats and self.strategy_stats[strategy_name].trade_count >= 20:
            # Use Kelly if we have enough data
            return (kelly_size * 0.5) + (vol_size * 0.3) + (fixed_size * 0.2)
        else:
            # Use volatility and fixed fractional
            return (vol_size * 0.6) + (fixed_size * 0.4)
    # ==========================================================================
    # PRIVATE METHODS - PROFESSIONAL ADJUSTMENTS
    # ==========================================================================
    def _apply_professional_adjustments(
        self,
        strategy_name: str,
        symbol: str,
        base_size: float,
        method: SizingMethod,
        entry_price: float,
        stop_loss: float,
        target_profit: Optional[float]
    ) -> PositionSizeRecommendation:
        """Apply professional adjustments to base size."""
        # Calculate risk metrics
        risk_per_share = abs(entry_price - stop_loss)
        risk_reward_ratio = (abs(target_profit - entry_price) / risk_per_share) if target_profit else 1.0
        # Get strategy stats for win probability
        win_prob = 0.5  # Default
        if strategy_name in self.strategy_stats:
            win_prob = self.strategy_stats[strategy_name].win_rate
        # Start with base size
        adjusted_size = base_size
        # Apply VIX adjustment
        vix_adjustment = 1.0
        if self.use_vix_adjustments and self.current_market_conditions:
            vix_adjustment = self.current_market_conditions.get_vix_adjustment_factor()
            adjusted_size *= vix_adjustment
        # Apply day-of-week adjustment
        day_adjustment = self._get_day_of_week_adjustment()
        if self.use_day_of_week_adjustments:
            adjusted_size *= day_adjustment
        # Apply volatility adjustment
        volatility_adjustment = self._get_volatility_adjustment()
        adjusted_size *= volatility_adjustment
        # Apply consecutive loss streak adjustment
        streak_adjustment = self._get_streak_adjustment(strategy_name)
        adjusted_size *= streak_adjustment
        # Create recommendation
        recommendation = PositionSizeRecommendation(
            strategy_name=strategy_name,
            symbol=symbol,
            recommended_size=adjusted_size,
            sizing_method=method,
            expected_risk=adjusted_size * risk_per_share / entry_price,
            risk_reward_ratio=risk_reward_ratio,
            win_probability=win_prob,
            base_size=base_size,
            kelly_adjustment=1.0,  # Would be calculated if using Kelly
            vix_adjustment=vix_adjustment,
            day_adjustment=day_adjustment,
            volatility_adjustment=volatility_adjustment,
            streak_adjustment=streak_adjustment,
            max_allowed_size=MAX_POSITION_SIZE,
            market_conditions=self.current_market_conditions
        )
        return recommendation
    def _get_day_of_week_adjustment(self) -> float:
        """Get day-of-week position size adjustment."""
        if not self.current_market_conditions:
            return 1.0
        day_effect = self.current_market_conditions.day_of_week
        if day_effect == DayOfWeekEffect.MONDAY:
            # Monday allows larger positions (1-5% vs 0.5-2.5%)
            return 2.0  # Can use 2x normal size
        else:
            # Other days use normal sizing
            return 1.0
    def _get_volatility_adjustment(self) -> float:
        """Get volatility-based adjustment."""
        if not self.current_market_conditions:
            return 1.0
        regime = self.current_market_conditions.market_regime
        if regime == MarketRegime.LOW_VOLATILITY:
            return 1.2  # Increase size in low vol
        elif regime == MarketRegime.HIGH_VOLATILITY:
            return 0.7  # Reduce size in high vol
        elif regime == MarketRegime.EXTREME_VOLATILITY:
            return 0.5  # Significantly reduce in extreme vol
        else:
            return 1.0  # Normal vol
    def _get_streak_adjustment(self, strategy_name: str) -> float:
        """Get consecutive loss streak adjustment."""
        if strategy_name not in self.strategy_stats:
            return 1.0
        consecutive_losses = self.strategy_stats[strategy_name].consecutive_losses
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            return LOSS_STREAK_REDUCTION  # 50% reduction
        else:
            return 1.0
    # ==========================================================================
    # PRIVATE METHODS - RISK LIMITS AND VALIDATION
    # ==========================================================================
    def _apply_risk_limits(self, recommendation: PositionSizeRecommendation) -> PositionSizeRecommendation:
        """Apply risk limits and validation."""
        original_size = recommendation.recommended_size
        # Apply absolute limits
        if recommendation.recommended_size > MAX_POSITION_SIZE:
            recommendation.recommended_size = MAX_POSITION_SIZE
            recommendation.size_limited_by = "max_position_limit"
            recommendation.warnings.append(f"Size reduced from {original_size:.1%} to {MAX_POSITION_SIZE:.1%} due to max position limit")
        if recommendation.recommended_size < MIN_POSITION_SIZE:
            recommendation.recommended_size = MIN_POSITION_SIZE
            recommendation.size_limited_by = "min_position_limit"
            recommendation.warnings.append(f"Size increased from {original_size:.1%} to {MIN_POSITION_SIZE:.1%} due to min position limit")
        # Check daily risk limit
        potential_daily_risk = self.current_daily_risk + recommendation.expected_risk
        if potential_daily_risk > self.max_daily_risk:
            # Scale down to fit within daily limit
            remaining_risk = self.max_daily_risk - self.current_daily_risk
            if remaining_risk > 0:
                scale_factor = remaining_risk / recommendation.expected_risk
                recommendation.recommended_size *= scale_factor
                recommendation.size_limited_by = "daily_risk_limit"
                recommendation.warnings.append(f"Size scaled down by {scale_factor:.1%} due to daily risk limit")
            else:
                recommendation.recommended_size = 0.0
                recommendation.size_limited_by = "daily_risk_exhausted"
                recommendation.warnings.append("No position allowed - daily risk limit exhausted")
        # Apply day-of-week specific limits
        if self.current_market_conditions:
            day_limits = self._get_day_of_week_limits()
            min_limit, max_limit = day_limits
            if recommendation.recommended_size > max_limit:
                recommendation.recommended_size = max_limit
                recommendation.size_limited_by = "day_of_week_limit"
                recommendation.warnings.append(f"Size limited to {max_limit:.1%} by day-of-week limits")
            if recommendation.recommended_size < min_limit and recommendation.recommended_size > 0:
                recommendation.recommended_size = min_limit
                recommendation.warnings.append(f"Size increased to minimum day-of-week limit of {min_limit:.1%}")
        return recommendation
    def _get_day_of_week_limits(self) -> Tuple[float, float]:
        """Get day-of-week specific position limits."""
        if not self.current_market_conditions:
            return OTHER_DAYS_MIN_PCT, OTHER_DAYS_MAX_PCT
        day_effect = self.current_market_conditions.day_of_week
        if day_effect == DayOfWeekEffect.MONDAY:
            return MONDAY_MIN_POSITION_PCT, MONDAY_MAX_POSITION_PCT
        else:
            return OTHER_DAYS_MIN_PCT, OTHER_DAYS_MAX_PCT
    # ==========================================================================
    # PRIVATE METHODS - MARKET CONDITIONS
    # ==========================================================================
    def _update_market_conditions(self, symbol: str) -> None:
        """Update current market conditions."""
        try:
            # Get VIX level
            vix_level = self.market_data_feed.get_current_price('VIX') or 20.0
            # Get SPY ATR
            spy_atr = self.volatility_analyzer.get_atr(symbol, ATR_PERIOD) or 5.0
            # Get realized volatility
            realized_vol = self.volatility_analyzer.get_realized_volatility(symbol, 20) or 0.20
            # Determine market regime
            if vix_level < VIX_LOW_THRESHOLD:
                regime = MarketRegime.LOW_VOLATILITY
            elif vix_level < VIX_NORMAL_THRESHOLD:
                regime = MarketRegime.NORMAL_VOLATILITY
            elif vix_level < VIX_EXTREME_THRESHOLD:
                regime = MarketRegime.HIGH_VOLATILITY
            else:
                regime = MarketRegime.EXTREME_VOLATILITY
            # Get day of week
            weekday = datetime.now().weekday()
            if weekday == 0:  # Monday
                day_effect = DayOfWeekEffect.MONDAY
            elif weekday == 1:
                day_effect = DayOfWeekEffect.TUESDAY
            elif weekday == 2:
                day_effect = DayOfWeekEffect.WEDNESDAY
            elif weekday == 3:
                day_effect = DayOfWeekEffect.THURSDAY
            else:  # Friday
                day_effect = DayOfWeekEffect.FRIDAY
            self.current_market_conditions = MarketConditions(
                vix_level=vix_level,
                spy_atr_14=spy_atr,
                realized_volatility=realized_vol,
                market_regime=regime,
                day_of_week=day_effect
            )
        except Exception as e:
            self.error_handler.handle_error(e, "_update_market_conditions")
    def _get_fallback_recommendation(self, strategy_name: str, symbol: str) -> PositionSizeRecommendation:
        """Get fallback recommendation in case of errors."""
        return PositionSizeRecommendation(
            strategy_name=strategy_name,
            symbol=symbol,
            recommended_size=DEFAULT_RISK_PER_TRADE,
            sizing_method=SizingMethod.FIXED_FRACTIONAL,
            expected_risk=DEFAULT_RISK_PER_TRADE,
            risk_reward_ratio=1.0,
            win_probability=0.5,
            base_size=DEFAULT_RISK_PER_TRADE,
            kelly_adjustment=1.0,
            vix_adjustment=1.0,
            day_adjustment=1.0,
            volatility_adjustment=1.0,
            streak_adjustment=1.0,
            max_allowed_size=MAX_POSITION_SIZE,
            warnings=["Fallback recommendation due to calculation error"]
        )
    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================
    def get_sizing_performance_report(self) -> Dict[str, Any]:
        """Generate position sizing performance report."""
        return {
            'portfolio_value': self.portfolio_value,
            'daily_risk_usage': self.get_daily_risk_usage(),
            'current_market_conditions': {
                'vix_level': self.current_market_conditions.vix_level if self.current_market_conditions else None,
                'market_regime': self.current_market_conditions.market_regime.name if self.current_market_conditions else None,
                'day_of_week': self.current_market_conditions.day_of_week.name if self.current_market_conditions else None
            },
            'strategy_performance': {
                name: {
                    'win_rate': stats.win_rate,
                    'trade_count': stats.trade_count,
                    'consecutive_losses': stats.consecutive_losses,
                    'kelly_percentage': stats.kelly_percentage(),
                    'avg_win': stats.avg_win,
                    'avg_loss': stats.avg_loss
                } for name, stats in self.strategy_stats.items()
            },
            'configuration': {
                'kelly_reduction_factor': self.kelly_reduction_factor,
                'use_day_of_week_adjustments': self.use_day_of_week_adjustments,
                'use_vix_adjustments': self.use_vix_adjustments,
                'use_volatility_adjustments': self.use_volatility_adjustments,
                'max_daily_risk': self.max_daily_risk
            }
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_position_sizer_instance: Optional[PositionSizer] = None

def get_position_sizer(portfolio_value: float = 100000.0, **kwargs) -> PositionSizer:
    """
    Get singleton position sizer instance.
    
    Args:
        portfolio_value: Portfolio value
        **kwargs: Additional arguments for PositionSizer
        
    Returns:
        PositionSizer instance
    """
    global _position_sizer_instance
    if _position_sizer_instance is None:
        _position_sizer_instance = PositionSizer(portfolio_value, **kwargs)
    return _position_sizer_instance


if __name__ == "__main__":
    print("Enhanced Position Sizer - Professional Risk Management")
    print("=" * 60)
    # Example of enhanced features
    print("Professional Features:")
    print("• Kelly Criterion with 25-50% institutional reduction")
    print("• VIX-based position adjustments (50% reduction when VIX > 25)")
    print("• Day-of-week research integration (Monday 1-5%, others 0.5-2.5%)")
    print("• Volatility-based sizing using 14-day ATR")
    print("• Consecutive loss streak management")
    print("• Professional risk controls and limits")
    print("• Real-time market regime detection")
    print("• Hybrid sizing methodology combining multiple approaches")