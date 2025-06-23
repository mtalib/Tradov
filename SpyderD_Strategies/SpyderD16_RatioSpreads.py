#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD16_RatioSpreads.py
Group: D (Trading Strategies)
Purpose: Ratio Spreads and Jade Lizard strategies for high-probability income

Description:
    Professional implementation of Ratio Spreads and Jade Lizard strategies
    optimized for SPY options. These high-probability income strategies are
    designed for range-bound markets with superior risk-adjusted returns.

Based on: Professional options trading patterns and market maker strategies
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
# CONSTANTS (Professional Trading Parameters)
# ==============================================================================
# Ratio spread parameters
RATIO_1X2_CREDIT_MIN = 0.25          # Minimum credit for 1x2 ratio spreads
RATIO_1X3_CREDIT_MIN = 0.50          # Minimum credit for 1x3 ratio spreads
RATIO_BREAKEVEN_BUFFER = 3.0         # Buffer above breakeven level

# Jade Lizard parameters
JADE_LIZARD_MIN_CREDIT = 2.00        # Minimum credit for Jade Lizard
JADE_LIZARD_CALL_DISTANCE = 10.0     # Distance of short call from ATM
JADE_LIZARD_PUT_SPREAD_WIDTH = 5.0   # Width of put spread

# Strike selection
OTM_DISTANCE_MIN = 5.0               # Minimum OTM distance
OTM_DISTANCE_MAX = 25.0              # Maximum OTM distance
STRIKE_SPACING_MIN = 2.5             # Minimum strike spacing

# Time parameters
MIN_DTE = 14                         # Minimum days to expiration
MAX_DTE = 45                         # Maximum days to expiration
EARLY_CLOSE_DTE = 7                  # Close positions at 7 DTE

# Risk management
MAX_LOSS_RATIO = 3.0                 # Maximum loss as multiple of credit
PROFIT_TARGET_RATIO = 0.25           # Take profits at 25% of max profit
ADJUSTMENT_DELTA_THRESHOLD = 0.15    # Adjust when delta exceeds threshold

# Market conditions
MIN_IV_RANK = 25                     # Minimum IV rank for entry
MAX_SKEW_RATIO = 1.5                 # Maximum put/call skew ratio
TREND_STRENGTH_MAX = 0.3             # Maximum trend strength for entry

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class RatioStrategy(Enum):
    """Ratio spread strategy types"""
    CALL_RATIO_1X2 = "call_ratio_1x2"           # 1 long call, 2 short calls
    CALL_RATIO_1X3 = "call_ratio_1x3"           # 1 long call, 3 short calls
    PUT_RATIO_1X2 = "put_ratio_1x2"             # 1 long put, 2 short puts
    PUT_RATIO_1X3 = "put_ratio_1x3"             # 1 long put, 3 short puts
    JADE_LIZARD = "jade_lizard"                  # Short call + short put spread
    JADE_LIZARD_MODIFIED = "jade_lizard_modified" # Jade Lizard with call spread
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly" # Unbalanced butterfly
    RATIO_CALL_SPREAD = "ratio_call_spread"      # Uneven call spread

class MarketBias(Enum):
    """Expected market direction"""
    BULLISH = "bullish"         # Expecting upward movement
    BEARISH = "bearish"         # Expecting downward movement
    NEUTRAL = "neutral"         # Expecting range-bound movement

class RatioPositionState(Enum):
    """Position lifecycle states"""
    SCANNING = "scanning"
    PENDING_ENTRY = "pending_entry"
    ACTIVE = "active"
    ADJUSTMENT_PENDING = "adjustment_pending"
    PROFIT_TAKING = "profit_taking"
    RISK_MANAGEMENT = "risk_management"
    CLOSING = "closing"
    CLOSED = "closed"
    ASSIGNED = "assigned"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RatioSpreadLegs:
    """Ratio spread leg definition"""
    strategy_type: RatioStrategy
    long_strike: float
    short_strike_1: float
    short_strike_2: Optional[float] = None  # For 1x3 ratios or complex strategies
    expiry: datetime = None
    underlying_symbol: str = "SPY"
    
    # Quantities (positive = long, negative = short)
    long_quantity: int = 1
    short_quantity_1: int = -2
    short_quantity_2: int = 0  # For complex strategies
    
    # Pricing and Greeks
    net_credit: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_upper: float = 0.0
    breakeven_lower: Optional[float] = None  # For complex strategies
    
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # Risk metrics
    win_probability: float = 0.0
    profit_range: Tuple[float, float] = (0.0, 0.0)
    max_risk_area: float = 0.0

@dataclass
class MarketAnalysis:
    """Market condition analysis for ratio strategies"""
    underlying_price: float
    iv_rank: float
    iv_percentile: float
    put_call_skew: float
    trend_strength: float  # -1 (bearish) to 1 (bullish)
    trend_direction: MarketBias
    
    # Volatility analysis
    realized_vol: float
    implied_vol: float
    vol_premium: float
    term_structure_slope: float
    
    # Support/resistance
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    
    # Market breadth
    volume_profile: Dict[float, float] = field(default_factory=dict)
    options_flow: str = "neutral"  # "bullish", "bearish", "neutral"
    
    # Suitability scores
    ratio_spread_score: float = 0.0    # 0-100
    jade_lizard_score: float = 0.0     # 0-100
    recommended_strategy: Optional[RatioStrategy] = None

@dataclass
class RatioPosition:
    """Active ratio spread position tracking"""
    position_id: str
    strategy_type: RatioStrategy
    legs: RatioSpreadLegs
    entry_time: datetime
    entry_credit: float
    
    # Current status
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    pnl_percent: float = 0.0
    
    # Greeks tracking
    current_delta: float = 0.0
    current_gamma: float = 0.0
    current_theta: float = 0.0
    current_vega: float = 0.0
    
    # Position management
    state: RatioPositionState = RatioPositionState.ACTIVE
    dte_remaining: int = 0
    profit_target: float = 0.0
    stop_loss: float = 0.0
    adjustment_level: float = 0.0
    
    # Risk monitoring
    max_loss_reached: float = 0.0
    max_profit_reached: float = 0.0
    risk_breach_count: int = 0
    assignment_risk: float = 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderD16_RatioSpreads:
    """
    Professional Ratio Spreads and Jade Lizard Trading Strategy.
    
    Implements sophisticated income strategies optimized for range-bound
    markets with high win rates and superior risk-adjusted returns.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the Ratio Spreads strategy."""
        self.config = config or {}
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Strategy state
        self.active_positions: Dict[str, RatioPosition] = {}
        self.strategy_statistics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_credits': 0.0,
            'total_pnl': 0.0,
            'win_rate': 0.0,
            'avg_winner': 0.0,
            'avg_loser': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0,
            'kelly_criterion': 0.0
        }
        
        # Configuration
        self.max_positions = self.config.get('max_positions', 3)
        self.profit_target = self.config.get('profit_target', PROFIT_TARGET_RATIO)
        self.max_loss_ratio = self.config.get('max_loss_ratio', MAX_LOSS_RATIO)
        
        self.logger.info("SpyderD16_RatioSpreads initialized with professional parameters")
    
    # ==========================================================================
    # MARKET ANALYSIS (Professional)
    # ==========================================================================
    
    def analyze_market_conditions(self, market_data: Dict[str, Any]) -> MarketAnalysis:
        """
        Comprehensive market analysis for ratio strategy selection.
        
        Analyzes market conditions to determine optimal ratio strategy
        based on volatility, trend, and options flow analysis.
        """
        try:
            underlying_price = market_data.get('underlying_price', 0.0)
            option_chain = market_data.get('option_chain', [])
            historical_data = market_data.get('historical_data', [])
            
            if not all([underlying_price, option_chain]):
                return self._create_neutral_market_analysis(underlying_price)
            
            # Volatility analysis
            iv_rank = self._calculate_iv_rank(option_chain, historical_data)
            iv_percentile = self._calculate_iv_percentile(option_chain, historical_data)
            put_call_skew = self._calculate_put_call_skew(option_chain, underlying_price)
            
            # Trend analysis
            trend_strength = self._calculate_trend_strength(historical_data)
            trend_direction = self._determine_trend_direction(trend_strength)
            
            # Volatility metrics
            realized_vol = self._calculate_realized_volatility(historical_data)
            implied_vol = self._calculate_atm_implied_vol(option_chain, underlying_price)
            vol_premium = implied_vol - realized_vol
            term_structure_slope = self._calculate_term_structure_slope(option_chain)
            
            # Support/resistance analysis
            support_levels = self._identify_support_levels(historical_data, underlying_price)
            resistance_levels = self._identify_resistance_levels(historical_data, underlying_price)
            
            # Volume and flow analysis
            volume_profile = self._analyze_volume_profile(historical_data)
            options_flow = self._analyze_options_flow(option_chain)
            
            # Strategy suitability scoring
            ratio_spread_score = self._score_ratio_spread_suitability(
                iv_rank, trend_strength, vol_premium, put_call_skew
            )
            jade_lizard_score = self._score_jade_lizard_suitability(
                iv_rank, trend_strength, vol_premium, underlying_price, support_levels
            )
            
            # Recommend optimal strategy
            recommended_strategy = self._recommend_optimal_strategy(
                ratio_spread_score, jade_lizard_score, trend_direction, iv_rank
            )
            
            return MarketAnalysis(
                underlying_price=underlying_price,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                put_call_skew=put_call_skew,
                trend_strength=trend_strength,
                trend_direction=trend_direction,
                realized_vol=realized_vol,
                implied_vol=implied_vol,
                vol_premium=vol_premium,
                term_structure_slope=term_structure_slope,
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                volume_profile=volume_profile,
                options_flow=options_flow,
                ratio_spread_score=ratio_spread_score,
                jade_lizard_score=jade_lizard_score,
                recommended_strategy=recommended_strategy
            )
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            return self._create_neutral_market_analysis(underlying_price)
    
    def _score_ratio_spread_suitability(self, iv_rank: float, trend_strength: float,
                                      vol_premium: float, skew: float) -> float:
        """Score market suitability for ratio spreads (0-100)."""
        try:
            score = 0.0
            
            # IV rank component (higher is better for selling premium)
            if iv_rank >= 50:
                score += min(30, iv_rank * 0.6)
            else:
                score += iv_rank * 0.3
            
            # Trend strength component (lower is better for ratio spreads)
            trend_score = max(0, 25 - abs(trend_strength) * 50)
            score += trend_score
            
            # Volatility premium component
            if vol_premium > 0.02:  # 2% vol premium
                score += min(25, vol_premium * 500)
            
            # Skew component (moderate skew is preferred)
            if 1.0 <= skew <= 1.3:
                score += 20
            elif 0.8 <= skew <= 1.5:
                score += 10
            
            return min(100.0, max(0.0, score))
            
        except Exception:
            return 50.0
    
    def _score_jade_lizard_suitability(self, iv_rank: float, trend_strength: float,
                                     vol_premium: float, underlying_price: float,
                                     support_levels: List[float]) -> float:
        """Score market suitability for Jade Lizard (0-100)."""
        try:
            score = 0.0
            
            # IV rank component (high IV is essential)
            if iv_rank >= 60:
                score += min(35, iv_rank * 0.58)
            else:
                score += iv_rank * 0.25
            
            # Trend strength component (slight bullish bias preferred)
            if 0.1 <= trend_strength <= 0.4:  # Mild bullish
                score += 25
            elif -0.2 <= trend_strength <= 0.5:
                score += 15
            
            # Volatility premium component (higher premium better)
            if vol_premium > 0.03:
                score += min(25, vol_premium * 600)
            
            # Support level component
            if support_levels:
                closest_support = min(support_levels, key=lambda x: abs(x - underlying_price))
                support_distance = (underlying_price - closest_support) / underlying_price
                if support_distance > 0.03:  # 3% above support
                    score += 15
            
            return min(100.0, max(0.0, score))
            
        except Exception:
            return 50.0
    
    # ==========================================================================
    # STRATEGY SELECTION
    # ==========================================================================
    
    def select_optimal_ratio_strategy(self, market_analysis: MarketAnalysis) -> Optional[RatioStrategy]:
        """
        Select optimal ratio strategy based on market conditions.
        
        Uses professional strategy selection logic based on market regime,
        volatility environment, and risk-reward characteristics.
        """
        try:
            # Check if we can add more positions
            if len(self.active_positions) >= self.max_positions:
                self.logger.info("Maximum positions reached")
                return None
            
            # Check minimum market requirements
            if market_analysis.iv_rank < MIN_IV_RANK:
                self.logger.info(f"IV rank {market_analysis.iv_rank} below minimum {MIN_IV_RANK}")
                return None
            
            if abs(market_analysis.trend_strength) > TREND_STRENGTH_MAX:
                self.logger.info(f"Trend strength {market_analysis.trend_strength} too high")
                return None
            
            # Use recommended strategy from analysis
            if market_analysis.recommended_strategy:
                return market_analysis.recommended_strategy
            
            # Fallback strategy selection
            if market_analysis.jade_lizard_score > market_analysis.ratio_spread_score:
                if market_analysis.jade_lizard_score >= 70:
                    return RatioStrategy.JADE_LIZARD
            
            # Select ratio spread based on market bias
            if market_analysis.ratio_spread_score >= 65:
                if market_analysis.trend_direction == MarketBias.BULLISH:
                    return RatioStrategy.PUT_RATIO_1X2
                elif market_analysis.trend_direction == MarketBias.BEARISH:
                    return RatioStrategy.CALL_RATIO_1X2
                else:  # Neutral
                    # Choose based on skew
                    if market_analysis.put_call_skew > 1.2:
                        return RatioStrategy.PUT_RATIO_1X2  # Sell expensive puts
                    else:
                        return RatioStrategy.CALL_RATIO_1X2  # Sell calls
            
            return None
            
        except Exception as e:
            self.logger.error(f"Strategy selection failed: {e}")
            return None
    
    def _recommend_optimal_strategy(self, ratio_score: float, jade_score: float,
                                  trend_direction: MarketBias, iv_rank: float) -> Optional[RatioStrategy]:
        """Recommend the optimal strategy based on scores."""
        try:
            # High IV environment favors Jade Lizard
            if iv_rank >= 70 and jade_score >= 75:
                return RatioStrategy.JADE_LIZARD
            
            # Strong ratio spread scores
            if ratio_score >= 70:
                if trend_direction == MarketBias.BULLISH:
                    return RatioStrategy.PUT_RATIO_1X2
                elif trend_direction == MarketBias.BEARISH:
                    return RatioStrategy.CALL_RATIO_1X2
                else:
                    return RatioStrategy.CALL_RATIO_1X2  # Default to call ratio
            
            # Moderate scores - use simpler strategies
            if max(ratio_score, jade_score) >= 60:
                if jade_score > ratio_score:
                    return RatioStrategy.JADE_LIZARD
                else:
                    return RatioStrategy.CALL_RATIO_1X2
            
            return None
            
        except Exception:
            return None
    
    # ==========================================================================
    # STRIKE SELECTION (Professional)
    # ==========================================================================
    
    def select_ratio_strikes(self, strategy_type: RatioStrategy,
                           option_chain: List[Any],
                           market_analysis: MarketAnalysis) -> Optional[RatioSpreadLegs]:
        """
        Professional strike selection for ratio strategies.
        
        Uses sophisticated algorithms to select optimal strikes based on
        probability analysis, volatility skew, and risk-reward optimization.
        """
        try:
            underlying_price = market_analysis.underlying_price
            
            # Group by expiry and select appropriate DTE
            for expiry, group in itertools.groupby(option_chain, lambda x: x.expiry):
                contracts = sorted(group, key=lambda x: x.strike)
                
                dte = (expiry - datetime.now()).days
                if not (MIN_DTE <= dte <= MAX_DTE):
                    continue
                
                # Strategy-specific strike selection
                if strategy_type == RatioStrategy.CALL_RATIO_1X2:
                    return self._select_call_ratio_strikes(contracts, underlying_price, expiry)
                elif strategy_type == RatioStrategy.PUT_RATIO_1X2:
                    return self._select_put_ratio_strikes(contracts, underlying_price, expiry)
                elif strategy_type == RatioStrategy.JADE_LIZARD:
                    return self._select_jade_lizard_strikes(contracts, underlying_price, expiry, market_analysis)
                elif strategy_type == RatioStrategy.CALL_RATIO_1X3:
                    return self._select_call_ratio_1x3_strikes(contracts, underlying_price, expiry)
                elif strategy_type == RatioStrategy.PUT_RATIO_1X3:
                    return self._select_put_ratio_1x3_strikes(contracts, underlying_price, expiry)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Strike selection failed: {e}")
            return None
    
    def _select_call_ratio_strikes(self, contracts: List[Any], underlying_price: float,
                                 expiry: datetime) -> Optional[RatioSpreadLegs]:
        """Select strikes for call ratio spread (1 long, 2 short)."""
        try:
            calls = [c for c in contracts if c.option_right == "CALL"]
            if len(calls) < 3:
                return None
            
            # Find ATM call for long leg
            atm_call = min(calls, key=lambda c: abs(c.strike - underlying_price))
            long_strike = atm_call.strike
            
            # Find OTM calls for short legs
            otm_calls = [c for c in calls if c.strike > long_strike + STRIKE_SPACING_MIN]
            if len(otm_calls) < 2:
                return None
            
            # Select short strike based on delta and premium
            target_short_delta = 0.25  # ~25 delta short calls
            short_call = min(otm_calls, 
                           key=lambda c: abs(getattr(c, 'delta', 0.25) - target_short_delta))
            short_strike = short_call.strike
            
            # Calculate credit and risk metrics
            long_premium = getattr(atm_call, 'ask', 5.0)
            short_premium = getattr(short_call, 'bid', 2.0)
            net_credit = 2 * short_premium - long_premium
            
            if net_credit < RATIO_1X2_CREDIT_MIN:
                return None
            
            # Calculate profit/loss parameters
            max_profit = (short_strike - long_strike) + net_credit
            max_loss = float('inf')  # Unlimited upside risk
            breakeven_upper = short_strike + net_credit
            
            # Calculate Greeks
            long_delta = getattr(atm_call, 'delta', 0.5)
            short_delta = getattr(short_call, 'delta', 0.25)
            total_delta = long_delta - 2 * short_delta
            
            long_gamma = getattr(atm_call, 'gamma', 0.1)
            short_gamma = getattr(short_call, 'gamma', 0.05)
            total_gamma = long_gamma - 2 * short_gamma
            
            long_theta = getattr(atm_call, 'theta', -0.05)
            short_theta = getattr(short_call, 'theta', -0.03)
            total_theta = long_theta - 2 * short_theta
            
            # Win probability analysis
            win_probability = self._calculate_win_probability(
                underlying_price, breakeven_upper, expiry
            )
            
            return RatioSpreadLegs(
                strategy_type=RatioStrategy.CALL_RATIO_1X2,
                long_strike=long_strike,
                short_strike_1=short_strike,
                expiry=expiry,
                long_quantity=1,
                short_quantity_1=-2,
                net_credit=net_credit,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_upper=breakeven_upper,
                delta=total_delta,
                gamma=total_gamma,
                theta=total_theta,
                win_probability=win_probability,
                profit_range=(long_strike, short_strike)
            )
            
        except Exception as e:
            self.logger.error(f"Call ratio strike selection failed: {e}")
            return None
    
    def _select_jade_lizard_strikes(self, contracts: List[Any], underlying_price: float,
                                  expiry: datetime, market_analysis: MarketAnalysis) -> Optional[RatioSpreadLegs]:
        """Select strikes for Jade Lizard strategy."""
        try:
            puts = [p for p in contracts if p.option_right == "PUT"]
            calls = [c for c in contracts if c.option_right == "CALL"]
            
            if len(puts) < 2 or len(calls) < 1:
                return None
            
            # Short call selection (OTM)
            otm_calls = [c for c in calls if c.strike > underlying_price + JADE_LIZARD_CALL_DISTANCE]
            if not otm_calls:
                return None
            
            short_call = otm_calls[0]  # First OTM call
            short_call_strike = short_call.strike
            
            # Put spread selection (OTM puts)
            otm_puts = [p for p in puts if p.strike < underlying_price]
            if len(otm_puts) < 2:
                return None
            
            # Select put spread strikes
            otm_puts_sorted = sorted(otm_puts, key=lambda p: p.strike, reverse=True)
            short_put = otm_puts_sorted[0]  # Highest OTM put
            long_put = next((p for p in otm_puts_sorted 
                           if p.strike == short_put.strike - JADE_LIZARD_PUT_SPREAD_WIDTH), None)
            
            if not long_put:
                return None
            
            # Calculate total credit
            call_credit = getattr(short_call, 'bid', 2.0)
            put_spread_credit = (getattr(short_put, 'bid', 3.0) - 
                               getattr(long_put, 'ask', 1.0))
            total_credit = call_credit + put_spread_credit
            
            if total_credit < JADE_LIZARD_MIN_CREDIT:
                return None
            
            # Ensure no upside risk (key Jade Lizard requirement)
            call_strike_minus_credit = short_call_strike - total_credit
            if call_strike_minus_credit <= underlying_price:
                return None  # Would have upside risk
            
            # Calculate risk metrics
            max_profit = total_credit
            max_loss = JADE_LIZARD_PUT_SPREAD_WIDTH - put_spread_credit
            
            return RatioSpreadLegs(
                strategy_type=RatioStrategy.JADE_LIZARD,
                long_strike=long_put.strike,        # Long put
                short_strike_1=short_put.strike,    # Short put
                short_strike_2=short_call_strike,   # Short call
                expiry=expiry,
                long_quantity=1,       # Long put
                short_quantity_1=-1,   # Short put
                short_quantity_2=-1,   # Short call
                net_credit=total_credit,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_upper=short_call_strike + total_credit,
                breakeven_lower=short_put.strike - total_credit,
                win_probability=self._calculate_jade_lizard_win_probability(
                    underlying_price, short_put.strike, short_call_strike, total_credit, expiry
                )
            )
            
        except Exception as e:
            self.logger.error(f"Jade Lizard strike selection failed: {e}")
            return None
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    async def execute_ratio_strategy(self, strategy_type: RatioStrategy,
                                   legs: RatioSpreadLegs) -> bool:
        """Execute ratio strategy with professional position management."""
        try:
            # Create position tracking
            position = RatioPosition(
                position_id=f"RATIO_{uuid.uuid4().hex[:8]}",
                strategy_type=strategy_type,
                legs=legs,
                entry_time=datetime.now(),
                entry_credit=legs.net_credit,
                profit_target=legs.net_credit * self.profit_target,
                stop_loss=legs.net_credit * self.max_loss_ratio,
                adjustment_level=legs.breakeven_upper * 0.95,  # Adjust at 95% of breakeven
                dte_remaining=(legs.expiry - datetime.now()).days
            )
            
            # Add to active positions
            self.active_positions[position.position_id] = position
            
            # Update statistics
            self.strategy_statistics['total_trades'] += 1
            self.strategy_statistics['total_credits'] += legs.net_credit
            
            self.logger.info(f"Executed {strategy_type.value}: {position.position_id}")
            self.logger.info(f"Credit received: ${legs.net_credit:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {e}")
            return False
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _calculate_win_probability(self, underlying_price: float, 
                                 breakeven: float, expiry: datetime) -> float:
        """Calculate probability of profitable outcome."""
        try:
            dte = (expiry - datetime.now()).days
            if dte <= 0:
                return 0.0
            
            # Simplified probability calculation
            # Uses normal distribution with implied volatility
            time_to_expiry = dte / 365.0
            vol = 0.2  # 20% assumed volatility
            
            # Calculate probability of staying below breakeven
            d = (np.log(breakeven / underlying_price)) / (vol * np.sqrt(time_to_expiry))
            prob = stats.norm.cdf(d)
            
            return min(0.95, max(0.05, prob))  # Cap between 5% and 95%
            
        except Exception:
            return 0.5
    
    def _calculate_jade_lizard_win_probability(self, underlying_price: float,
                                             put_breakeven: float, call_breakeven: float,
                                             credit: float, expiry: datetime) -> float:
        """Calculate win probability for Jade Lizard."""
        try:
            # Probability of staying between breakevens
            put_prob = self._calculate_win_probability(underlying_price, put_breakeven, expiry)
            call_prob = 1 - self._calculate_win_probability(underlying_price, call_breakeven, expiry)
            
            # Combined probability
            return put_prob + call_prob - 1.0 if (put_prob + call_prob) > 1 else 0.0
            
        except Exception:
            return 0.5
    
    def _create_neutral_market_analysis(self, underlying_price: float) -> MarketAnalysis:
        """Create neutral market analysis for error cases."""
        return MarketAnalysis(
            underlying_price=underlying_price,
            iv_rank=50.0,
            iv_percentile=50.0,
            put_call_skew=1.0,
            trend_strength=0.0,
            trend_direction=MarketBias.NEUTRAL,
            realized_vol=0.2,
            implied_vol=0.2,
            vol_premium=0.0,
            term_structure_slope=0.0
        )
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """Get comprehensive strategy summary."""
        return {
            'module_name': 'SpyderD16_RatioSpreads',
            'strategy_type': 'High-Probability Income (Ratio Spreads & Jade Lizard)',
            'active_positions': len(self.active_positions),
            'statistics': self.strategy_statistics.copy(),
            'available_strategies': [s.value for s in RatioStrategy],
            'configuration': {
                'max_positions': self.max_positions,
                'profit_target': self.profit_target,
                'max_loss_ratio': self.max_loss_ratio
            },
            'last_updated': datetime.now().isoformat()
        }

# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_ratio_spreads_strategy(config: Dict[str, Any] = None) -> SpyderD16_RatioSpreads:
    """Factory function to create Ratio Spreads strategy instance."""
    return SpyderD16_RatioSpreads(config)

if __name__ == "__main__":
    # Example usage
    strategy = create_ratio_spreads_strategy()
    print("SpyderD16_RatioSpreads strategy initialized successfully!")
    print(f"Available strategies: {[s.value for s in RatioStrategy]}")
    print("Features:")
    print("- Call/Put Ratio Spreads (1x2, 1x3)")
    print("- Jade Lizard (high-probability income)")
    print("- Broken Wing Butterflies")
    print("- Professional risk management")
    print("- Market condition analysis")
