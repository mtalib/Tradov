#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD15_StraddleStrangle.py
Group: D (Trading Strategies)
Purpose: Straddle and Strangle strategies for volatility trading

Description:
    Professional implementation of Straddle and Strangle strategies based on 
    LEAN's LongAndShortStraddleStrategiesAlgorithm and LongAndShortStrangleStrategiesAlgorithm.
    Optimized for SPY options volatility trading with advanced Greeks management.

Based on: QuantConnect LEAN Straddle/Strangle algorithms
Author: Spyder Development Team
Created: 2025-06-23
Version: 1.0 (LEAN-Enhanced)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
from datetime import datetime, timedelta
import itertools
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderAction
from SpyderU_Utilities.SpyderU14_OptionStrategies import SpyderOptionStrategies, StrategyType

# ==============================================================================
# CONSTANTS (From LEAN Algorithms)
# ==============================================================================
# Volatility requirements
MIN_IV_FOR_STRADDLE = 0.15        # 15% minimum IV for straddle entry
MIN_IV_FOR_STRANGLE = 0.12        # 12% minimum IV for strangle entry
MAX_IV_FOR_SHORT_STRADDLE = 0.35  # 35% maximum IV for short straddle
MAX_IV_FOR_SHORT_STRANGLE = 0.40  # 40% maximum IV for short strangle

# Strike selection (LEAN patterns)
ATM_TOLERANCE = 1.0               # ATM tolerance for straddles
STRANGLE_STRIKE_DISTANCE = 5.0    # Distance between strangle strikes
OTM_DISTANCE_MIN = 2.0            # Minimum OTM distance
OTM_DISTANCE_MAX = 15.0           # Maximum OTM distance

# Time to expiration
MIN_DTE_LONG = 14                 # Minimum DTE for long strategies
MAX_DTE_LONG = 45                 # Maximum DTE for long strategies
MIN_DTE_SHORT = 7                 # Minimum DTE for short strategies
MAX_DTE_SHORT = 30                # Maximum DTE for short strategies

# Position management
STRADDLE_PROFIT_TARGET = 0.50     # 50% profit target
STRANGLE_PROFIT_TARGET = 0.40     # 40% profit target
STOP_LOSS_THRESHOLD = 2.0         # 200% stop loss
MAX_POSITION_COUNT = 2            # Maximum concurrent positions

# Greeks thresholds
MIN_DELTA_NEUTRAL_THRESHOLD = 0.05  # Delta neutrality tolerance
MAX_GAMMA_EXPOSURE = 10.0          # Maximum gamma exposure
MIN_VEGA_EXPOSURE = 5.0            # Minimum vega for volatility plays

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class VolatilityStrategy(Enum):
    """Volatility strategy types (from LEAN)"""
    LONG_STRADDLE = "long_straddle"
    SHORT_STRADDLE = "short_straddle"
    LONG_STRANGLE = "long_strangle"
    SHORT_STRANGLE = "short_strangle"
    IRON_STRADDLE = "iron_straddle"      # Short straddle with protective wings
    IRON_STRANGLE = "iron_strangle"      # Short strangle with protective wings

class VolatilityDirection(Enum):
    """Expected volatility direction"""
    EXPANSION = "expansion"     # Expecting vol increase
    CONTRACTION = "contraction" # Expecting vol decrease
    NEUTRAL = "neutral"         # No vol direction bias

class PositionState(Enum):
    """Position lifecycle states"""
    SCANNING = "scanning"
    PENDING_ENTRY = "pending_entry"
    ACTIVE = "active"
    PROFIT_TAKING = "profit_taking"
    RISK_MANAGEMENT = "risk_management"
    CLOSING = "closing"
    CLOSED = "closed"
    EXPIRED = "expired"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityAnalysis:
    """Volatility analysis data structure"""
    current_iv: float
    iv_rank: float              # IV rank (0-100)
    iv_percentile: float        # IV percentile (0-100)
    realized_vol: float         # Historical realized volatility
    vol_premium: float          # IV - RV premium
    vol_trend: str              # "rising", "falling", "stable"
    term_structure: Dict[int, float]  # DTE -> IV mapping
    skew: float                 # Put/call skew
    confidence: float           # Analysis confidence (0-1)

@dataclass
class StraddleStrangleLegs:
    """Straddle/Strangle leg definition (LEAN-style)"""
    strategy_type: VolatilityStrategy
    call_strike: float
    put_strike: float
    expiry: datetime
    underlying_symbol: str = "SPY"
    
    # Greeks and pricing
    total_premium: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # Risk metrics
    max_profit: float = float('inf')  # Unlimited for long strategies
    max_loss: float = 0.0
    breakeven_upper: float = 0.0
    breakeven_lower: float = 0.0

@dataclass
class VolatilityPosition:
    """Active volatility position tracking"""
    position_id: str
    strategy_type: VolatilityStrategy
    legs: StraddleStrangleLegs
    entry_time: datetime
    entry_price: float
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Greeks tracking
    current_delta: float = 0.0
    current_gamma: float = 0.0
    current_theta: float = 0.0
    current_vega: float = 0.0
    
    # Position management
    state: PositionState = PositionState.ACTIVE
    profit_target: float = 0.0
    stop_loss: float = 0.0
    dte_remaining: int = 0
    
    # Volatility tracking
    entry_iv: float = 0.0
    current_iv: float = 0.0
    vol_change: float = 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderD15_StraddleStrangle:
    """
    LEAN-Enhanced Straddle and Strangle Trading Strategy.
    
    Implements professional volatility trading strategies based on QuantConnect
    LEAN's straddle and strangle algorithms with advanced Greeks management.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Straddle/Strangle strategy."""
        self.config = config or {}
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Strategy state
        self.active_positions: Dict[str, VolatilityPosition] = {}
        self.strategy_statistics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_winner': 0.0,
            'avg_loser': 0.0,
            'max_drawdown': 0.0,
            'vol_prediction_accuracy': 0.0
        }
        
        # LEAN-style configuration
        self.max_positions = self.config.get('max_positions', MAX_POSITION_COUNT)
        self.profit_target = self.config.get('profit_target', STRADDLE_PROFIT_TARGET)
        self.stop_loss = self.config.get('stop_loss', STOP_LOSS_THRESHOLD)
        
        self.logger.info("SpyderD15_StraddleStrangle initialized with LEAN enhancements")
    
    # ==========================================================================
    # VOLATILITY ANALYSIS (LEAN-Enhanced)
    # ==========================================================================
    
    def analyze_volatility_environment(self, market_data: Dict[str, Any]) -> VolatilityAnalysis:
        """
        Analyze volatility environment using LEAN patterns.
        
        Based on LEAN's volatility analysis algorithms with professional
        IV rank, percentile, and term structure analysis.
        """
        try:
            option_chain = market_data.get('option_chain', [])
            underlying_price = market_data.get('underlying_price', 0.0)
            historical_data = market_data.get('historical_data', [])
            
            if not option_chain:
                return self._create_neutral_vol_analysis()
            
            # Calculate current IV (ATM options)
            current_iv = self._calculate_atm_iv(option_chain, underlying_price)
            
            # Calculate IV rank and percentile
            iv_rank = self._calculate_iv_rank(current_iv, historical_data)
            iv_percentile = self._calculate_iv_percentile(current_iv, historical_data)
            
            # Calculate realized volatility
            realized_vol = self._calculate_realized_volatility(historical_data)
            
            # Calculate volatility premium
            vol_premium = current_iv - realized_vol
            
            # Analyze volatility trend
            vol_trend = self._analyze_vol_trend(historical_data)
            
            # Build term structure
            term_structure = self._build_vol_term_structure(option_chain)
            
            # Calculate skew
            skew = self._calculate_volatility_skew(option_chain, underlying_price)
            
            # Calculate confidence
            confidence = self._calculate_analysis_confidence(
                len(option_chain), len(historical_data), iv_rank
            )
            
            return VolatilityAnalysis(
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                realized_vol=realized_vol,
                vol_premium=vol_premium,
                vol_trend=vol_trend,
                term_structure=term_structure,
                skew=skew,
                confidence=confidence
            )
            
        except Exception as e:
            self.logger.error(f"Volatility analysis failed: {e}")
            return self._create_neutral_vol_analysis()
    
    def _calculate_atm_iv(self, option_chain: List[Any], underlying_price: float) -> float:
        """Calculate ATM implied volatility using LEAN patterns."""
        try:
            atm_options = []
            
            for option in option_chain:
                if abs(option.strike - underlying_price) <= ATM_TOLERANCE:
                    if hasattr(option, 'implied_volatility') and option.implied_volatility > 0:
                        atm_options.append(option.implied_volatility)
            
            return np.mean(atm_options) if atm_options else 0.2  # Default 20%
            
        except Exception as e:
            self.logger.error(f"ATM IV calculation failed: {e}")
            return 0.2
    
    def _calculate_iv_rank(self, current_iv: float, historical_data: List[Any]) -> float:
        """Calculate IV rank (LEAN pattern)."""
        try:
            if len(historical_data) < 252:  # Need at least 1 year
                return 50.0  # Neutral rank
            
            iv_history = [data.get('iv', 0.2) for data in historical_data[-252:]]
            rank = stats.percentileofscore(iv_history, current_iv)
            return max(0.0, min(100.0, rank))
            
        except Exception:
            return 50.0
    
    def _calculate_iv_percentile(self, current_iv: float, historical_data: List[Any]) -> float:
        """Calculate IV percentile using LEAN patterns."""
        try:
            if len(historical_data) < 30:
                return 50.0
            
            iv_history = [data.get('iv', 0.2) for data in historical_data[-30:]]
            percentile = stats.percentileofscore(iv_history, current_iv)
            return max(0.0, min(100.0, percentile))
            
        except Exception:
            return 50.0
    
    # ==========================================================================
    # STRATEGY SELECTION (LEAN-Enhanced)
    # ==========================================================================
    
    def select_optimal_strategy(self, 
                              vol_analysis: VolatilityAnalysis,
                              market_data: Dict[str, Any]) -> Optional[VolatilityStrategy]:
        """
        Select optimal volatility strategy based on LEAN decision logic.
        
        Uses sophisticated volatility environment analysis to choose between
        long/short straddles/strangles based on IV levels and market conditions.
        """
        try:
            # LEAN Pattern: Check volatility regime first
            if vol_analysis.confidence < 0.5:
                self.logger.info("Low confidence in volatility analysis, skipping")
                return None
            
            iv_rank = vol_analysis.iv_rank
            vol_premium = vol_analysis.vol_premium
            trend = vol_analysis.vol_trend
            
            # LEAN Pattern: Strategy selection based on IV environment
            if iv_rank < 20:  # Low IV environment
                if vol_premium > 0.03:  # High vol premium
                    return VolatilityStrategy.LONG_STRANGLE  # Cheaper than straddle
                elif trend == "rising":
                    return VolatilityStrategy.LONG_STRADDLE  # Max volatility exposure
                    
            elif iv_rank > 80:  # High IV environment
                if vol_premium > 0.05:  # Very high vol premium
                    return VolatilityStrategy.SHORT_STRANGLE  # Collect premium
                elif trend == "falling":
                    return VolatilityStrategy.SHORT_STRADDLE  # Max premium collection
                    
            elif 30 <= iv_rank <= 70:  # Normal IV environment
                if trend == "rising" and vol_premium < 0.02:
                    return VolatilityStrategy.LONG_STRADDLE
                elif trend == "falling" and vol_premium > 0.03:
                    return VolatilityStrategy.SHORT_STRANGLE
            
            # Check current position count
            if len(self.active_positions) >= self.max_positions:
                self.logger.info("Maximum positions reached, skipping new entries")
                return None
            
            # Default: No strategy if conditions not met
            return None
            
        except Exception as e:
            self.logger.error(f"Strategy selection failed: {e}")
            return None
    
    # ==========================================================================
    # STRIKE SELECTION (LEAN Algorithms)
    # ==========================================================================
    
    def select_strategy_strikes(self,
                              strategy_type: VolatilityStrategy,
                              option_chain: List[Any],
                              underlying_price: float) -> Optional[StraddleStrangleLegs]:
        """
        Select optimal strikes using LEAN algorithm patterns.
        
        Based on LEAN's LongAndShortStraddleStrategiesAlgorithm and 
        LongAndShortStrangleStrategiesAlgorithm strike selection logic.
        """
        try:
            # LEAN Pattern: Group by expiry and select appropriate one
            for expiry, group in itertools.groupby(option_chain, lambda x: x.expiry):
                contracts = sorted(group, key=lambda x: x.strike)
                
                # LEAN Pattern: Check DTE requirements
                dte = (expiry - datetime.now()).days
                if not self._validate_dte_for_strategy(strategy_type, dte):
                    continue
                
                # LEAN Pattern: Separate puts and calls
                puts = [x for x in contracts if x.option_right == "PUT"]
                calls = [x for x in contracts if x.option_right == "CALL"]
                
                if len(puts) < 2 or len(calls) < 2:
                    continue
                
                # Select strikes based on strategy type
                if strategy_type in [VolatilityStrategy.LONG_STRADDLE, 
                                   VolatilityStrategy.SHORT_STRADDLE]:
                    return self._select_straddle_strikes(
                        strategy_type, puts, calls, underlying_price, expiry
                    )
                else:  # Strangle strategies
                    return self._select_strangle_strikes(
                        strategy_type, puts, calls, underlying_price, expiry
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Strike selection failed: {e}")
            return None
    
    def _select_straddle_strikes(self,
                               strategy_type: VolatilityStrategy,
                               puts: List[Any],
                               calls: List[Any],
                               underlying_price: float,
                               expiry: datetime) -> Optional[StraddleStrangleLegs]:
        """Select straddle strikes (ATM for both legs)."""
        try:
            # Find ATM strike
            all_strikes = [opt.strike for opt in puts + calls]
            atm_strike = min(all_strikes, key=lambda x: abs(x - underlying_price))
            
            # Verify we have both put and call at ATM strike
            atm_put = next((p for p in puts if p.strike == atm_strike), None)
            atm_call = next((c for c in calls if c.strike == atm_strike), None)
            
            if not atm_put or not atm_call:
                return None
            
            # Calculate Greeks and pricing
            total_premium = self._estimate_total_premium(atm_put, atm_call, strategy_type)
            delta = self._calculate_straddle_delta(atm_put, atm_call)
            gamma = self._calculate_straddle_gamma(atm_put, atm_call)
            theta = self._calculate_straddle_theta(atm_put, atm_call)
            vega = self._calculate_straddle_vega(atm_put, atm_call)
            
            # Calculate profit/loss parameters
            max_profit, max_loss, be_upper, be_lower = self._calculate_straddle_pnl_params(
                strategy_type, atm_strike, total_premium
            )
            
            return StraddleStrangleLegs(
                strategy_type=strategy_type,
                call_strike=atm_strike,
                put_strike=atm_strike,
                expiry=expiry,
                total_premium=total_premium,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_upper=be_upper,
                breakeven_lower=be_lower
            )
            
        except Exception as e:
            self.logger.error(f"Straddle strike selection failed: {e}")
            return None
    
    def _select_strangle_strikes(self,
                               strategy_type: VolatilityStrategy,
                               puts: List[Any],
                               calls: List[Any],
                               underlying_price: float,
                               expiry: datetime) -> Optional[StraddleStrangleLegs]:
        """Select strangle strikes (OTM puts and calls)."""
        try:
            # Find OTM put (below underlying)
            otm_puts = [p for p in puts if p.strike < underlying_price]
            if not otm_puts:
                return None
            
            # Select put strike based on distance
            target_put_distance = STRANGLE_STRIKE_DISTANCE
            otm_put = min(otm_puts, key=lambda p: abs(underlying_price - p.strike - target_put_distance))
            
            # Find OTM call (above underlying)  
            otm_calls = [c for c in calls if c.strike > underlying_price]
            if not otm_calls:
                return None
            
            # Select call strike based on distance
            target_call_distance = STRANGLE_STRIKE_DISTANCE
            otm_call = min(otm_calls, key=lambda c: abs(c.strike - underlying_price - target_call_distance))
            
            # Calculate Greeks and pricing
            total_premium = self._estimate_total_premium(otm_put, otm_call, strategy_type)
            delta = self._calculate_strangle_delta(otm_put, otm_call)
            gamma = self._calculate_strangle_gamma(otm_put, otm_call)
            theta = self._calculate_strangle_theta(otm_put, otm_call)
            vega = self._calculate_strangle_vega(otm_put, otm_call)
            
            # Calculate profit/loss parameters
            max_profit, max_loss, be_upper, be_lower = self._calculate_strangle_pnl_params(
                strategy_type, otm_put.strike, otm_call.strike, total_premium
            )
            
            return StraddleStrangleLegs(
                strategy_type=strategy_type,
                call_strike=otm_call.strike,
                put_strike=otm_put.strike,
                expiry=expiry,
                total_premium=total_premium,
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_upper=be_upper,
                breakeven_lower=be_lower
            )
            
        except Exception as e:
            self.logger.error(f"Strangle strike selection failed: {e}")
            return None
    
    # ==========================================================================
    # POSITION MANAGEMENT (LEAN-Enhanced)
    # ==========================================================================
    
    async def execute_volatility_strategy(self,
                                        strategy_type: VolatilityStrategy,
                                        legs: StraddleStrangleLegs) -> bool:
        """
        Execute volatility strategy using LEAN position management patterns.
        
        Creates atomic multi-leg orders with professional validation and
        position group management like LEAN's OptionStrategies.
        """
        try:
            # LEAN Pattern: Create strategy using OptionStrategies helper
            if strategy_type == VolatilityStrategy.LONG_STRADDLE:
                strategy = SpyderOptionStrategies.long_straddle(
                    "SPY", legs.call_strike, legs.expiry
                )
            elif strategy_type == VolatilityStrategy.SHORT_STRADDLE:
                strategy = SpyderOptionStrategies.short_straddle(
                    "SPY", legs.call_strike, legs.expiry
                )
            elif strategy_type == VolatilityStrategy.LONG_STRANGLE:
                strategy = SpyderOptionStrategies.long_strangle(
                    "SPY", legs.put_strike, legs.call_strike, legs.expiry
                )
            elif strategy_type == VolatilityStrategy.SHORT_STRANGLE:
                strategy = SpyderOptionStrategies.short_strangle(
                    "SPY", legs.put_strike, legs.call_strike, legs.expiry
                )
            else:
                raise ValueError(f"Unsupported strategy type: {strategy_type}")
            
            # LEAN Pattern: Validate strategy before execution
            SpyderOptionStrategies.validate_strategy_legs(strategy)
            
            # Create position tracking
            position = VolatilityPosition(
                position_id=f"VOL_{uuid.uuid4().hex[:8]}",
                strategy_type=strategy_type,
                legs=legs,
                entry_time=datetime.now(),
                entry_price=legs.total_premium,
                profit_target=legs.total_premium * self.profit_target,
                stop_loss=legs.total_premium * self.stop_loss,
                dte_remaining=(legs.expiry - datetime.now()).days,
                entry_iv=0.0  # Will be updated with current IV
            )
            
            # Add to active positions
            self.active_positions[position.position_id] = position
            
            # Update statistics
            self.strategy_statistics['total_trades'] += 1
            
            self.logger.info(f"Executed {strategy_type.value} strategy: {position.position_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {e}")
            self.error_handler.handle_error(e, {"strategy_type": strategy_type.value})
            return False
    
    # ==========================================================================
    # GREEKS CALCULATIONS (LEAN-Enhanced)
    # ==========================================================================
    
    def _calculate_straddle_delta(self, put_option: Any, call_option: Any) -> float:
        """Calculate total straddle delta (should be near zero for ATM)."""
        try:
            put_delta = getattr(put_option, 'delta', -0.5)  # Default put delta
            call_delta = getattr(call_option, 'delta', 0.5)  # Default call delta
            return abs(put_delta + call_delta)  # Should be near zero for ATM straddle
        except Exception:
            return 0.05  # Default small delta
    
    def _calculate_straddle_gamma(self, put_option: Any, call_option: Any) -> float:
        """Calculate total straddle gamma (positive for long, negative for short)."""
        try:
            put_gamma = getattr(put_option, 'gamma', 0.1)
            call_gamma = getattr(call_option, 'gamma', 0.1)
            return put_gamma + call_gamma
        except Exception:
            return 0.2  # Default gamma
    
    def _calculate_straddle_theta(self, put_option: Any, call_option: Any) -> float:
        """Calculate total straddle theta (time decay)."""
        try:
            put_theta = getattr(put_option, 'theta', -0.05)
            call_theta = getattr(call_option, 'theta', -0.05)
            return put_theta + call_theta
        except Exception:
            return -0.1  # Default theta
    
    def _calculate_straddle_vega(self, put_option: Any, call_option: Any) -> float:
        """Calculate total straddle vega (volatility sensitivity)."""
        try:
            put_vega = getattr(put_option, 'vega', 0.15)
            call_vega = getattr(call_option, 'vega', 0.15)
            return put_vega + call_vega
        except Exception:
            return 0.3  # Default vega
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _create_neutral_vol_analysis(self) -> VolatilityAnalysis:
        """Create neutral volatility analysis for error cases."""
        return VolatilityAnalysis(
            current_iv=0.2,
            iv_rank=50.0,
            iv_percentile=50.0,
            realized_vol=0.18,
            vol_premium=0.02,
            vol_trend="stable",
            term_structure={},
            skew=0.0,
            confidence=0.0
        )
    
    def _validate_dte_for_strategy(self, strategy_type: VolatilityStrategy, dte: int) -> bool:
        """Validate DTE requirements for strategy type."""
        if strategy_type in [VolatilityStrategy.LONG_STRADDLE, VolatilityStrategy.LONG_STRANGLE]:
            return MIN_DTE_LONG <= dte <= MAX_DTE_LONG
        else:  # Short strategies
            return MIN_DTE_SHORT <= dte <= MAX_DTE_SHORT
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get comprehensive strategy summary."""
        return {
            'module_name': 'SpyderD15_StraddleStrangle',
            'strategy_type': 'Volatility Trading (LEAN-Enhanced)',
            'active_positions': len(self.active_positions),
            'statistics': self.strategy_statistics.copy(),
            'available_strategies': [s.value for s in VolatilityStrategy],
            'last_updated': datetime.now().isoformat()
        }

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_straddle_strangle_strategy(config: Dict[str, Any] = None) -> SpyderD15_StraddleStrangle:
    """Factory function to create StraddleStrangle strategy instance."""
    return SpyderD15_StraddleStrangle(config)

if __name__ == "__main__":
    # Example usage
    strategy = create_straddle_strangle_strategy()
    print("SpyderD15_StraddleStrangle strategy initialized successfully!")
    print(f"Available strategies: {[s.value for s in VolatilityStrategy]}")
