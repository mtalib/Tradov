#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD32_MultiLegStrategyCoordinator.py
Purpose: Unified multi-leg options strategy coordinator - consolidates complex strategies
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-02 Time: 18:30:00

Module Description:
    Unified multi-leg strategy coordinator that consolidates D02_IronCondor, D10_IronButterfly,
    and other complex multi-leg options strategies. Provides intelligent strategy selection
    based on market volatility, trend conditions, and risk-return optimization. Eliminates
    redundant leg construction, Greeks management, and adjustment logic while providing
    superior multi-leg strategy execution and management capabilities.

Consolidation Benefits:
    • Eliminates multi-leg strategy overlap (D02, D10, and future complex strategies)
    • Unified leg construction and optimization algorithms
    • Intelligent strategy selection based on volatility environment
    • Advanced Greeks management across all multi-leg positions
    • Consolidated adjustment and defense mechanisms
    • Superior risk management with position-level coordination
    • Single source of truth for complex options strategies

Key Features:
    • Iron Condor: Neutral strategy for range-bound, high-IV environments
    • Iron Butterfly: Neutral strategy for low-movement, high-IV scenarios
    • Jade Lizard: Modified strategy for specific market conditions
    • Big Lizard: Extended strategy for wider ranges
    • Broken Wing Butterfly: Directional bias with limited risk
    • Dynamic Strategy Morphing: Convert between strategies as conditions change
    • Advanced Greeks Hedging: Delta, gamma, vega risk management
    • Intelligent Adjustment Logic: Roll, add wings, convert strategies
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import asyncio
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Reinforcement Learning (optional)
try:
    import gym
    from gym import spaces
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv  # noqa: F401
    HAS_SB3 = True
except ImportError:
    HAS_SB3 = False

# Integration imports
try:
    from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import get_unified_regime_engine, MarketRegime  # noqa: F401
    REGIME_ENGINE_AVAILABLE = True
except ImportError:
    REGIME_ENGINE_AVAILABLE = False

try:
    from SpyderE_Risk.SpyderE19_UnifiedRiskCoordinator import get_unified_risk_coordinator
    RISK_COORDINATOR_AVAILABLE = True
except ImportError:
    RISK_COORDINATOR_AVAILABLE = False

try:
    from SpyderD_Strategies.SpyderD25_UnifiedCreditSpreadEngine import UnifiedCreditSpreadEngine  # noqa: F401
    CREDIT_SPREAD_ENGINE_AVAILABLE = True
except ImportError:
    CREDIT_SPREAD_ENGINE_AVAILABLE = False

try:
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import OrderManager  # noqa: F401
    ORDER_MANAGER_AVAILABLE = True
except ImportError:
    ORDER_MANAGER_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Multi-leg strategy parameters
MIN_IMPLIED_VOLATILITY = 0.18       # Minimum IV for multi-leg strategies
OPTIMAL_IV_RANGE = (0.25, 0.40)     # Optimal IV range for maximum premium
MAX_IMPLIED_VOLATILITY = 0.60       # Above this, too risky

# Time parameters
MIN_DTE_MULTILEG = 14                # Minimum days to expiration
MAX_DTE_MULTILEG = 45                # Maximum days to expiration
OPTIMAL_DTE_RANGE = (21, 35)         # Optimal DTE range
THETA_OPTIMIZATION_ZONE = (14, 28)   # When theta is most favorable

# Greeks thresholds
MAX_NET_DELTA = 0.10                 # Maximum net delta for neutral strategies
MAX_GAMMA_RISK = 0.05                # Maximum gamma risk per position
MAX_VEGA_RISK = 15.0                 # Maximum vega risk per position
THETA_ACCELERATION_THRESHOLD = 14    # Days when theta accelerates

# Wing width parameters
MIN_WING_WIDTH = 5.0                 # Minimum wing width
MAX_WING_WIDTH = 25.0                # Maximum wing width
OPTIMAL_WING_WIDTH = 10.0            # Default wing width

# Profit and loss management
PROFIT_TARGET_PERCENT = 0.25         # Take profits at 25% of max profit
STOP_LOSS_PERCENT = 2.0              # Stop loss at 200% of credit received
ADJUSTMENT_DELTA_THRESHOLD = 0.15    # When to consider adjustments

# Market condition thresholds
LOW_VOLATILITY_THRESHOLD = 15        # VIX below 15
HIGH_VOLATILITY_THRESHOLD = 30       # VIX above 30
EXTREME_VOLATILITY_THRESHOLD = 45    # VIX above 45 (too high for most strategies)

# Position limits
MAX_MULTILEG_POSITIONS = 3           # Maximum concurrent multi-leg positions
MAX_PORTFOLIO_ALLOCATION = 0.20      # Maximum 20% of portfolio in multi-leg
MAX_CORRELATED_RISK = 0.30           # Maximum correlated risk exposure

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class MultiLegStrategyType(Enum):
    """Types of multi-leg strategies"""
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    JADE_LIZARD = "jade_lizard"
    BIG_LIZARD = "big_lizard"
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly"
    DOUBLE_DIAGONAL = "double_diagonal"
    AUTO_SELECT = "auto_select"

class VolatilityEnvironment(Enum):
    """Volatility environment classifications"""
    LOW_VOL = "low_vol"              # VIX < 15
    NORMAL_VOL = "normal_vol"        # VIX 15-25
    HIGH_VOL = "high_vol"            # VIX 25-35
    EXTREME_VOL = "extreme_vol"      # VIX > 35

class MarketCondition(Enum):
    """Market condition for strategy selection"""
    RANGE_BOUND = "range_bound"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    VOLATILE_CHOPPY = "volatile_choppy"
    BREAKOUT_PENDING = "breakout_pending"

class AdjustmentAction(Enum):
    """Types of adjustments for multi-leg strategies"""
    ROLL_UNTESTED_SIDE = "roll_untested_side"
    ADD_EXTRA_WINGS = "add_extra_wings"
    CONVERT_TO_BUTTERFLY = "convert_to_butterfly"
    CONVERT_TO_CONDOR = "convert_to_condor"
    CLOSE_THREATENED_SIDE = "close_threatened_side"
    ROLL_ENTIRE_POSITION = "roll_entire_position"
    ADD_DELTA_HEDGE = "add_delta_hedge"

class PositionStatus(Enum):
    """Multi-leg position status"""
    ACTIVE = "active"
    PROFIT_ZONE = "profit_zone"
    ADJUSTMENT_NEEDED = "adjustment_needed"
    STOP_LOSS_ZONE = "stop_loss_zone"
    EXPIRATION_WEEK = "expiration_week"
    CLOSING = "closing"
    CLOSED = "closed"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionLeg:
    """Individual option leg definition"""
    option_type: str        # 'call' or 'put'
    strike: float
    quantity: int           # Positive for long, negative for short
    expiration: datetime
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    price: float = 0.0
    implied_vol: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'option_type': self.option_type,
            'strike': self.strike,
            'quantity': self.quantity,
            'expiration': self.expiration.isoformat(),
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'price': self.price,
            'implied_vol': self.implied_vol
        }

@dataclass
class MultiLegStructure:
    """Complete multi-leg strategy structure"""
    strategy_type: MultiLegStrategyType
    legs: list[OptionLeg]
    net_credit: float
    max_profit: float
    max_loss: float
    breakeven_points: list[float]
    probability_profit: float

    # Net Greeks
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # Risk metrics
    wing_width: float = 0.0
    body_width: float = 0.0
    risk_reward_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'strategy_type': self.strategy_type.value,
            'legs': [leg.to_dict() for leg in self.legs],
            'net_credit': self.net_credit,
            'max_profit': self.max_profit,
            'max_loss': self.max_loss,
            'breakeven_points': self.breakeven_points,
            'probability_profit': self.probability_profit,
            'net_delta': self.net_delta,
            'net_gamma': self.net_gamma,
            'net_theta': self.net_theta,
            'net_vega': self.net_vega,
            'wing_width': self.wing_width,
            'body_width': self.body_width,
            'risk_reward_ratio': self.risk_reward_ratio
        }

@dataclass
class MultiLegPosition:
    """Active multi-leg position"""
    position_id: str
    strategy_structure: MultiLegStructure
    entry_time: datetime
    entry_net_credit: float
    current_value: float
    unrealized_pnl: float
    status: PositionStatus
    days_held: int

    # Market context at entry
    market_condition_at_entry: MarketCondition
    volatility_environment_at_entry: VolatilityEnvironment
    underlying_price_at_entry: float
    vix_at_entry: float

    # Position Greeks
    current_delta: float = 0.0
    current_gamma: float = 0.0
    current_theta: float = 0.0
    current_vega: float = 0.0

    # Management history
    adjustments: list[dict[str, Any]] = field(default_factory=list)
    management_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'position_id': self.position_id,
            'strategy_structure': self.strategy_structure.to_dict(),
            'entry_time': self.entry_time.isoformat(),
            'entry_net_credit': self.entry_net_credit,
            'current_value': self.current_value,
            'unrealized_pnl': self.unrealized_pnl,
            'status': self.status.value,
            'days_held': self.days_held,
            'market_condition_at_entry': self.market_condition_at_entry.value,
            'volatility_environment_at_entry': self.volatility_environment_at_entry.value,
            'underlying_price_at_entry': self.underlying_price_at_entry,
            'vix_at_entry': self.vix_at_entry,
            'current_delta': self.current_delta,
            'current_gamma': self.current_gamma,
            'current_theta': self.current_theta,
            'current_vega': self.current_vega,
            'adjustments': self.adjustments,
            'management_notes': self.management_notes
        }

@dataclass
class MarketEnvironmentAnalysis:
    """Comprehensive market environment analysis for multi-leg strategies"""
    timestamp: datetime
    underlying_price: float
    volatility_environment: VolatilityEnvironment
    market_condition: MarketCondition
    implied_volatility: float
    vix_level: float

    # Volatility metrics
    iv_rank: float              # IV rank over lookback period
    iv_percentile: float        # IV percentile
    volatility_skew: float      # Put/call skew
    term_structure_slope: float # IV term structure slope

    # Market structure
    support_resistance_range: float
    expected_move: float
    trend_strength: float
    momentum_score: float

    # Options flow
    put_call_ratio: float = 1.0
    options_volume_ratio: float = 1.0
    unusual_activity: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'underlying_price': self.underlying_price,
            'volatility_environment': self.volatility_environment.value,
            'market_condition': self.market_condition.value,
            'implied_volatility': self.implied_volatility,
            'vix_level': self.vix_level,
            'iv_rank': self.iv_rank,
            'iv_percentile': self.iv_percentile,
            'volatility_skew': self.volatility_skew,
            'term_structure_slope': self.term_structure_slope,
            'support_resistance_range': self.support_resistance_range,
            'expected_move': self.expected_move,
            'trend_strength': self.trend_strength,
            'momentum_score': self.momentum_score,
            'put_call_ratio': self.put_call_ratio,
            'options_volume_ratio': self.options_volume_ratio,
            'unusual_activity': self.unusual_activity
        }

# ==============================================================================
# ADVANCED MARKET ENVIRONMENT ANALYZER
# ==============================================================================
class MultiLegMarketAnalyzer:
    """Advanced market analysis specifically for multi-leg strategies"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize multi-leg market analyzer"""
        self.config = config or {}
        self.logger = SpyderLogger.get_logger(f"{__name__}.MultiLegAnalyzer")

        # Analysis parameters
        self.iv_lookback_days = self.config.get('iv_lookback_days', 252)
        self.trend_lookback_days = self.config.get('trend_lookback_days', 20)
        self.support_resistance_lookback = self.config.get('sr_lookback', 60)

    def analyze_environment(self, market_data: pd.DataFrame) -> MarketEnvironmentAnalysis:
        """Comprehensive market environment analysis for multi-leg strategies"""
        try:
            if len(market_data) < 20:
                raise ValueError("Insufficient market data for analysis")

            current_price = market_data['close'].iloc[-1]
            timestamp = datetime.now(timezone.utc)

            # Volatility analysis
            vix_level = market_data.get('vix', pd.Series([20.0])).iloc[-1] if 'vix' in market_data else 20.0  # noqa: E501
            volatility_env = self._classify_volatility_environment(vix_level)
            implied_vol = self._estimate_implied_volatility(market_data)

            # IV metrics
            iv_rank = self._calculate_iv_rank(market_data, implied_vol)
            iv_percentile = self._calculate_iv_percentile(market_data, implied_vol)
            volatility_skew = self._calculate_volatility_skew()
            term_structure_slope = self._calculate_term_structure_slope()

            # Market condition analysis
            market_condition = self._analyze_market_condition(market_data)
            trend_strength = self._calculate_trend_strength(market_data)
            momentum_score = self._calculate_momentum_score(market_data)

            # Support/Resistance and range analysis
            sr_range = self._calculate_support_resistance_range(market_data)
            expected_move = self._calculate_expected_move(implied_vol, current_price)

            # Options flow analysis
            put_call_ratio = self._calculate_put_call_ratio(market_data)
            options_volume_ratio = self._calculate_options_volume_ratio(market_data)
            unusual_activity = self._detect_unusual_activity(market_data)

            return MarketEnvironmentAnalysis(
                timestamp=timestamp,
                underlying_price=current_price,
                volatility_environment=volatility_env,
                market_condition=market_condition,
                implied_volatility=implied_vol,
                vix_level=vix_level,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                volatility_skew=volatility_skew,
                term_structure_slope=term_structure_slope,
                support_resistance_range=sr_range,
                expected_move=expected_move,
                trend_strength=trend_strength,
                momentum_score=momentum_score,
                put_call_ratio=put_call_ratio,
                options_volume_ratio=options_volume_ratio,
                unusual_activity=unusual_activity
            )

        except Exception as e:
            self.logger.error("Market environment analysis failed: %s", e, exc_info=True)
            neutral = MarketEnvironmentAnalysis(
                timestamp=datetime.now(timezone.utc),
                underlying_price=market_data['close'].iloc[-1],
                volatility_environment=VolatilityEnvironment.NORMAL_VOL,
                market_condition=MarketCondition.RANGE_BOUND,
                implied_volatility=0.20,
                vix_level=20.0,
                iv_rank=0.5,
                iv_percentile=0.5,
                volatility_skew=0.0,
                term_structure_slope=0.0,
                support_resistance_range=10.0,
                expected_move=5.0,
                trend_strength=0.0,
                momentum_score=0.0
            )
            self.logger.warning(
                "Returning neutral market environment due to analysis failure. "
                "Strategy selection may be unreliable."
            )
            return neutral

    def _classify_volatility_environment(self, vix_level: float) -> VolatilityEnvironment:
        """Classify volatility environment based on VIX"""
        if vix_level < LOW_VOLATILITY_THRESHOLD:
            return VolatilityEnvironment.LOW_VOL
        elif vix_level < HIGH_VOLATILITY_THRESHOLD:
            return VolatilityEnvironment.NORMAL_VOL
        elif vix_level < EXTREME_VOLATILITY_THRESHOLD:
            return VolatilityEnvironment.HIGH_VOL
        else:
            return VolatilityEnvironment.EXTREME_VOL

    def _estimate_implied_volatility(self, market_data: pd.DataFrame) -> float:
        """Estimate current implied volatility"""
        try:
            returns = market_data['close'].pct_change().dropna()
            if len(returns) < 20:
                return 0.20

            # Calculate realized volatility
            realized_vol = returns.tail(20).std() * np.sqrt(252)

            # IV typically trades at premium to realized
            iv_premium = 1.3 if len(returns) > 60 else 1.2
            estimated_iv = realized_vol * iv_premium

            return min(max(estimated_iv, 0.10), 0.80)

        except Exception:
            return 0.20

    def _calculate_iv_rank(self, market_data: pd.DataFrame, current_iv: float) -> float:
        """Calculate IV rank over lookback period"""
        try:
            self.logger.warning(
                "IV rank is estimated from realized volatility proxy — not live implied "
                "volatility. This lags true IV rank by days/weeks. Consider integrating "
                "live IV data."
            )
            # Estimate IV history (in reality would use actual IV data)
            returns = market_data['close'].pct_change().dropna()
            if len(returns) < 100:
                return 0.5  # Default to middle rank

            # Attempt to fetch live ATM IV history from TradierClient option chain.
            # Falls back to rolling realized-volatility proxy when the client is
            # unavailable or returns insufficient data.
            live_iv_series = None
            try:
                from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
                    create_tradier_client_from_env,
                )
                _tradier = create_tradier_client_from_env()
                # Retrieve the nearest-expiry ATM option to sample current IV
                _chain = _tradier.get_option_chain("SPY", expiration_date=None, greeks=True)
                if _chain and "options" in _chain:
                    iv_samples = [
                        opt.get("greeks", {}).get("smv_vol") or opt.get("implied_volatility", 0)
                        for opt in _chain.get("options", {}).get("option", [])
                        if opt.get("greeks", {}).get("smv_vol") or opt.get("implied_volatility")
                    ]
                    if len(iv_samples) >= 5:
                        # Use the median ATM IV as a single-point estimate;
                        # a full IV time-series would require historical option snapshots.
                        live_iv_series = pd.Series([float(v) for v in iv_samples if v])
                        self.logger.debug(
                            f"Live IV samples retrieved from Tradier: n={len(live_iv_series)}, "
                            f"median={live_iv_series.median():.4f}"
                        )
            except Exception as _tradier_exc:
                self.logger.debug(
                    f"Live IV history unavailable from Tradier ({_tradier_exc}); "
                    "using realized-volatility proxy."
                )

            if live_iv_series is not None and len(live_iv_series) >= 5:
                iv_history = live_iv_series.tail(min(len(live_iv_series), self.iv_lookback_days))
                rank = (current_iv > iv_history).sum() / len(iv_history)
                return rank

            # Fallback: calculate rolling realized volatility as proxy for IV
            rolling_vol = returns.rolling(20).std() * np.sqrt(252) * 1.2  # IV premium

            if len(rolling_vol.dropna()) < 50:
                return 0.5

            # Calculate rank
            iv_history = rolling_vol.dropna().tail(min(len(rolling_vol), self.iv_lookback_days))
            rank = (current_iv > iv_history).sum() / len(iv_history)

            return rank

        except Exception:
            return 0.5

    def _calculate_iv_percentile(self, market_data: pd.DataFrame, current_iv: float) -> float:
        """Calculate IV percentile"""
        # For simplicity, percentile tracks closely with rank
        return self._calculate_iv_rank(market_data, current_iv)

    def _calculate_volatility_skew(self, option_chain=None) -> float:
        """
        Calculate put/call volatility skew.

        NOTE: Currently returns a conservative estimate. For accurate skew,
        integrate live option chain IV data from broker.

        Returns:
            float: Estimated skew as decimal (e.g., 0.02 = 2%)
        """
        # Attempt to compute live put/call IV skew from TradierClient option chain.
        # Skew = (25-delta put IV - 25-delta call IV) / ATM IV
        # Typical range: 0.01 (low stress) to 0.05 (high stress)
        if option_chain is not None:
            try:
                puts = [
                    c for c in option_chain
                    if c.get("option_type", "").upper() == "PUT"
                    and c.get("greeks", {}).get("delta") is not None
                ]
                calls = [
                    c for c in option_chain
                    if c.get("option_type", "").upper() == "CALL"
                    and c.get("greeks", {}).get("delta") is not None
                ]

                def _nearest_delta(contracts, target_delta: float) -> float | None:
                    """Return IV of the contract whose |delta| is closest to target."""
                    best, best_iv = None, None
                    for c in contracts:
                        delta = abs(float(c["greeks"]["delta"]))
                        if best is None or abs(delta - target_delta) < abs(best - target_delta):
                            best = delta
                            best_iv = (
                                c.get("greeks", {}).get("smv_vol")
                                or c.get("implied_volatility")
                            )
                    return float(best_iv) if best_iv else None

                atm_calls = [
                    c for c in calls
                    if abs(abs(float(c["greeks"]["delta"])) - 0.50) < 0.10
                ]
                atm_iv = (
                    float(atm_calls[0].get("greeks", {}).get("smv_vol")
                          or atm_calls[0].get("implied_volatility", 0))
                    if atm_calls else None
                )

                put_25d_iv = _nearest_delta(puts, 0.25)
                call_25d_iv = _nearest_delta(calls, 0.25)

                if put_25d_iv and call_25d_iv and atm_iv and atm_iv > 0:
                    skew = (put_25d_iv - call_25d_iv) / atm_iv
                    self.logger.debug(
                        f"Live IV skew computed: put_25d={put_25d_iv:.4f}, "
                        f"call_25d={call_25d_iv:.4f}, atm={atm_iv:.4f}, skew={skew:.4f}"
                    )
                    return max(0.0, skew)
            except Exception as _skew_exc:
                self.logger.debug("Live skew calculation failed (%s); using estimate.", _skew_exc)

        # Fallback: conservative middle estimate
        self.logger.debug("Using estimated volatility skew (live option_chain not provided)")
        return 0.025  # Conservative estimate; replace with live calculation

    def _calculate_term_structure_slope(self) -> float:
        """Calculate IV term structure slope"""
        # Simplified - normally would use multiple expirations
        # Positive slope = contango, negative = backwardation
        return 0.01  # Slight contango assumption

    def _analyze_market_condition(self, market_data: pd.DataFrame) -> MarketCondition:
        """Analyze overall market condition"""
        try:
            trend_strength = self._calculate_trend_strength(market_data)
            self._analyze_price_action(market_data)
            volatility = self._calculate_realized_volatility(market_data)

            # Decision matrix
            if abs(trend_strength) < 0.3:
                if volatility < 0.15:
                    return MarketCondition.RANGE_BOUND
                else:
                    return MarketCondition.VOLATILE_CHOPPY
            elif trend_strength > 0.3:
                return MarketCondition.TRENDING_UP
            elif trend_strength < -0.3:
                return MarketCondition.TRENDING_DOWN
            else:
                return MarketCondition.BREAKOUT_PENDING

        except Exception:
            return MarketCondition.RANGE_BOUND

    def _calculate_trend_strength(self, market_data: pd.DataFrame) -> float:
        """Calculate trend strength (-1 to +1)"""
        try:
            prices = market_data['close'].tail(self.trend_lookback_days)
            if len(prices) < 10:
                return 0.0

            # Multiple moving averages
            ma_fast = prices.rolling(5).mean()
            ma_medium = prices.rolling(10).mean()
            ma_slow = prices.rolling(20).mean()

            current_price = prices.iloc[-1]

            # Trend alignment score
            alignment_score = 0
            if current_price > ma_fast.iloc[-1] > ma_medium.iloc[-1] > ma_slow.iloc[-1]:
                alignment_score = 1  # Strong uptrend
            elif current_price < ma_fast.iloc[-1] < ma_medium.iloc[-1] < ma_slow.iloc[-1]:
                alignment_score = -1  # Strong downtrend
            elif current_price > ma_fast.iloc[-1]:
                alignment_score = 0.5  # Weak uptrend
            elif current_price < ma_fast.iloc[-1]:
                alignment_score = -0.5  # Weak downtrend

            # Price momentum
            momentum = (current_price - ma_slow.iloc[-1]) / ma_slow.iloc[-1] * 10
            momentum = max(-1, min(1, momentum))  # Normalize

            # Combined score
            return (alignment_score * 0.6 + momentum * 0.4)

        except Exception:
            return 0.0

    def _analyze_price_action(self, market_data: pd.DataFrame) -> float:
        """Analyze recent price action patterns"""
        try:
            prices = market_data['close'].tail(10)
            if len(prices) < 5:
                return 0.0

            # Calculate price action score
            returns = prices.pct_change().dropna()
            consistency = returns.std()  # Lower std = more consistent direction

            return 1.0 / (1.0 + consistency * 100)  # Convert to 0-1 score

        except Exception:
            return 0.0

    def _calculate_realized_volatility(self, market_data: pd.DataFrame) -> float:
        """Calculate recent realized volatility"""
        try:
            returns = market_data['close'].pct_change().tail(20).dropna()
            if len(returns) < 10:
                return 0.15

            return returns.std() * np.sqrt(252)

        except Exception:
            return 0.15

    def _calculate_momentum_score(self, market_data: pd.DataFrame) -> float:
        """Calculate momentum score"""
        try:
            prices = market_data['close']
            if len(prices) < 20:
                return 0.0

            # RSI-like momentum
            gains = prices.diff().where(prices.diff() > 0, 0).rolling(14).sum()
            losses = -prices.diff().where(prices.diff() < 0, 0).rolling(14).sum()

            rs = gains / losses
            rsi = 100 - (100 / (1 + rs))

            # Convert RSI to momentum score (-1 to +1)
            current_rsi = rsi.iloc[-1]
            return (current_rsi - 50) / 50

        except Exception:
            return 0.0

    def _calculate_support_resistance_range(self, market_data: pd.DataFrame) -> float:
        """Calculate current support/resistance range"""
        try:
            lookback_data = market_data.tail(self.support_resistance_lookback)
            high_low_range = lookback_data['high'].max() - lookback_data['low'].min()

            return high_low_range

        except Exception:
            return 10.0  # Default range

    def _calculate_expected_move(self, implied_vol: float, current_price: float,
                               days_to_expiration: int = 21) -> float:
        """Calculate expected move based on IV"""
        try:
            # Standard expected move formula
            time_factor = np.sqrt(days_to_expiration / 365)
            expected_move = current_price * implied_vol * time_factor

            return expected_move

        except Exception:
            return current_price * 0.05  # 5% default move

    def _calculate_put_call_ratio(self, market_data: pd.DataFrame) -> float:
        """Calculate put/call ratio if available"""
        try:
            if 'put_volume' in market_data and 'call_volume' in market_data:
                put_vol = market_data['put_volume'].iloc[-1]
                call_vol = market_data['call_volume'].iloc[-1]
                return put_vol / call_vol if call_vol > 0 else 1.0

            # Estimate from price action if not available
            recent_returns = market_data['close'].pct_change().tail(5)
            negative_days = (recent_returns < 0).sum()
            return (negative_days + 2) / 7  # Crude estimation

        except Exception:
            return 1.0

    def _calculate_options_volume_ratio(self, market_data: pd.DataFrame) -> float:
        """Calculate options volume ratio"""
        try:
            if 'options_volume' in market_data:
                current_vol = market_data['options_volume'].iloc[-1]
                avg_vol = market_data['options_volume'].tail(20).mean()
                return current_vol / avg_vol if avg_vol > 0 else 1.0
            return 1.0
        except Exception:
            return 1.0

    def _detect_unusual_activity(self, market_data: pd.DataFrame) -> bool:
        """Detect unusual options activity"""
        try:
            # Simple volume spike detection
            if 'volume' in market_data:
                current_vol = market_data['volume'].iloc[-1]
                avg_vol = market_data['volume'].tail(20).mean()
                return current_vol > avg_vol * 2  # 2x average volume
            return False
        except Exception:
            return False

# ==============================================================================
# MULTI-LEG STRATEGY CONSTRUCTOR
# ==============================================================================
class MultiLegStrategyConstructor:
    """Intelligent construction of multi-leg option strategies"""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize multi-leg strategy constructor"""
        self.config = config or {}
        self.logger = SpyderLogger.get_logger(f"{__name__}.StrategyConstructor")

    def construct_strategy(self, strategy_type: MultiLegStrategyType,
                          market_analysis: MarketEnvironmentAnalysis,
                          days_to_expiration: int = 21) -> MultiLegStructure | None:
        """Construct optimal multi-leg strategy based on market conditions"""
        try:
            if strategy_type == MultiLegStrategyType.AUTO_SELECT:
                strategy_type = self._select_optimal_strategy(market_analysis)

            if strategy_type == MultiLegStrategyType.IRON_CONDOR:
                return self._construct_iron_condor(market_analysis, days_to_expiration)
            elif strategy_type == MultiLegStrategyType.IRON_BUTTERFLY:
                return self._construct_iron_butterfly(market_analysis, days_to_expiration)
            elif strategy_type == MultiLegStrategyType.JADE_LIZARD:
                return self._construct_jade_lizard(market_analysis, days_to_expiration)
            else:
                self.logger.warning("Strategy type %s not implemented yet", strategy_type)
                return None

        except Exception as e:
            self.logger.error("Strategy construction failed: %s", e, exc_info=True)
            return None

    def _select_optimal_strategy(self, market_analysis: MarketEnvironmentAnalysis) -> MultiLegStrategyType:  # noqa: E501
        """Intelligently select optimal strategy based on market conditions"""
        try:
            vol_env = market_analysis.volatility_environment
            market_condition = market_analysis.market_condition
            expected_move = market_analysis.expected_move
            underlying_price = market_analysis.underlying_price

            # High IV strategies
            if vol_env in [VolatilityEnvironment.HIGH_VOL, VolatilityEnvironment.EXTREME_VOL]:
                if market_condition == MarketCondition.RANGE_BOUND:
                    # High IV + Range bound = Iron Condor
                    return MultiLegStrategyType.IRON_CONDOR
                elif abs(market_analysis.trend_strength) < 0.2:
                    # High IV + Low movement = Iron Butterfly
                    return MultiLegStrategyType.IRON_BUTTERFLY
                else:
                    # High IV + Trending = Jade Lizard (undefined risk on one side)
                    return MultiLegStrategyType.JADE_LIZARD

            # Normal to low IV strategies
            elif vol_env == VolatilityEnvironment.NORMAL_VOL:
                if market_condition == MarketCondition.RANGE_BOUND:
                    # Normal IV + Range bound = Iron Condor (wider)
                    return MultiLegStrategyType.IRON_CONDOR
                elif expected_move < underlying_price * 0.03:  # < 3% expected move
                    # Small expected move = Iron Butterfly
                    return MultiLegStrategyType.IRON_BUTTERFLY
                else:
                    return MultiLegStrategyType.IRON_CONDOR

            else:  # Low volatility
                # Low IV generally not ideal for multi-leg, but if forced:
                if market_condition == MarketCondition.RANGE_BOUND:
                    return MultiLegStrategyType.IRON_BUTTERFLY  # Tighter range
                else:
                    return MultiLegStrategyType.IRON_CONDOR

        except Exception as e:
            self.logger.error("Strategy selection failed: %s", e, exc_info=True)
            return MultiLegStrategyType.IRON_CONDOR  # Default fallback

    def _construct_iron_condor(self, market_analysis: MarketEnvironmentAnalysis,
                             dte: int) -> MultiLegStructure:
        """Construct Iron Condor strategy"""
        try:
            underlying_price = market_analysis.underlying_price
            expected_move = market_analysis.expected_move
            iv = market_analysis.implied_volatility

            # Calculate strikes based on expected move and IV
            # Iron Condor: Sell put spread + sell call spread

            # Wing width based on volatility environment
            wing_width = self._calculate_optimal_wing_width(market_analysis)

            # Short strikes positioned outside expected move
            move_multiplier = 1.2 if market_analysis.volatility_environment == VolatilityEnvironment.HIGH_VOL else 1.0  # noqa: E501

            short_put_strike = underlying_price - (expected_move * move_multiplier)
            short_call_strike = underlying_price + (expected_move * move_multiplier)

            # Round strikes to nearest 0.50 (SPY)
            short_put_strike = round(short_put_strike * 2) / 2
            short_call_strike = round(short_call_strike * 2) / 2

            # Long strikes
            long_put_strike = short_put_strike - wing_width
            long_call_strike = short_call_strike + wing_width

            # Create legs
            expiration = datetime.now(timezone.utc) + timedelta(days=dte)

            legs = [
                # Put spread (bull put spread)
                OptionLeg('put', long_put_strike, 1, expiration),      # Long put
                OptionLeg('put', short_put_strike, -1, expiration),    # Short put
                # Call spread (bear call spread)
                OptionLeg('call', short_call_strike, -1, expiration),  # Short call
                OptionLeg('call', long_call_strike, 1, expiration),    # Long call
            ]

            # Estimate pricing and Greeks (simplified)
            self._estimate_legs_pricing_and_greeks(legs, underlying_price, iv, dte)

            # Calculate strategy metrics
            net_credit = self._calculate_net_credit(legs)
            max_profit = net_credit
            max_loss = wing_width - net_credit

            # Breakeven points
            breakeven_lower = short_put_strike - net_credit
            breakeven_upper = short_call_strike + net_credit

            # Probability of profit (simplified)
            prob_profit = self._estimate_probability_profit(underlying_price,
                                                          [breakeven_lower, breakeven_upper],
                                                          expected_move)

            # Net Greeks
            net_delta = sum(leg.delta * leg.quantity for leg in legs)
            net_gamma = sum(leg.gamma * leg.quantity for leg in legs)
            net_theta = sum(leg.theta * leg.quantity for leg in legs)
            net_vega = sum(leg.vega * leg.quantity for leg in legs)

            return MultiLegStructure(
                strategy_type=MultiLegStrategyType.IRON_CONDOR,
                legs=legs,
                net_credit=net_credit,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_points=[breakeven_lower, breakeven_upper],
                probability_profit=prob_profit,
                net_delta=net_delta,
                net_gamma=net_gamma,
                net_theta=net_theta,
                net_vega=net_vega,
                wing_width=wing_width,
                body_width=short_call_strike - short_put_strike,
                risk_reward_ratio=max_loss / max_profit if max_profit > 0 else 0
            )

        except Exception as e:
            self.logger.error("Iron Condor construction failed: %s", e, exc_info=True)
            raise

    def _construct_iron_butterfly(self, market_analysis: MarketEnvironmentAnalysis,
                                dte: int) -> MultiLegStructure:
        """Construct Iron Butterfly strategy"""
        try:
            underlying_price = market_analysis.underlying_price
            iv = market_analysis.implied_volatility

            # Iron Butterfly: ATM short straddle + protective wings
            atm_strike = round(underlying_price * 2) / 2  # Round to nearest 0.50

            # Wing width based on volatility (tighter for butterfly)
            wing_width = self._calculate_optimal_wing_width(market_analysis) * 0.8

            # Strikes
            long_put_strike = atm_strike - wing_width
            short_put_strike = atm_strike
            short_call_strike = atm_strike
            long_call_strike = atm_strike + wing_width

            # Create legs
            expiration = datetime.now(timezone.utc) + timedelta(days=dte)

            legs = [
                OptionLeg('put', long_put_strike, 1, expiration),      # Long put
                OptionLeg('put', short_put_strike, -1, expiration),    # Short put
                OptionLeg('call', short_call_strike, -1, expiration),  # Short call
                OptionLeg('call', long_call_strike, 1, expiration),    # Long call
            ]

            # Estimate pricing and Greeks
            self._estimate_legs_pricing_and_greeks(legs, underlying_price, iv, dte)

            # Calculate strategy metrics
            net_credit = self._calculate_net_credit(legs)
            max_profit = net_credit
            max_loss = wing_width - net_credit

            # Single breakeven range (butterfly has narrow profit zone)
            breakeven_lower = atm_strike - net_credit
            breakeven_upper = atm_strike + net_credit

            prob_profit = self._estimate_probability_profit(underlying_price,
                                                          [breakeven_lower, breakeven_upper],
                                                          market_analysis.expected_move)

            # Net Greeks
            net_delta = sum(leg.delta * leg.quantity for leg in legs)
            net_gamma = sum(leg.gamma * leg.quantity for leg in legs)
            net_theta = sum(leg.theta * leg.quantity for leg in legs)
            net_vega = sum(leg.vega * leg.quantity for leg in legs)

            return MultiLegStructure(
                strategy_type=MultiLegStrategyType.IRON_BUTTERFLY,
                legs=legs,
                net_credit=net_credit,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_points=[breakeven_lower, breakeven_upper],
                probability_profit=prob_profit,
                net_delta=net_delta,
                net_gamma=net_gamma,
                net_theta=net_theta,
                net_vega=net_vega,
                wing_width=wing_width,
                body_width=0.0,  # No body width in butterfly
                risk_reward_ratio=max_loss / max_profit if max_profit > 0 else 0
            )

        except Exception as e:
            self.logger.error("Iron Butterfly construction failed: %s", e, exc_info=True)
            raise

    def _construct_jade_lizard(self, market_analysis: MarketEnvironmentAnalysis,
                             dte: int) -> MultiLegStructure:
        """Construct Jade Lizard strategy (call spread + short put)"""
        try:
            underlying_price = market_analysis.underlying_price
            expected_move = market_analysis.expected_move
            iv = market_analysis.implied_volatility

            # Jade Lizard: Short call spread + short put
            # Undefined risk on upside, but collect more premium

            wing_width = self._calculate_optimal_wing_width(market_analysis)

            # Position short put below support, call spread above resistance
            short_put_strike = underlying_price - (expected_move * 0.8)
            short_call_strike = underlying_price + (expected_move * 0.6)
            long_call_strike = short_call_strike + wing_width

            # Round strikes
            short_put_strike = round(short_put_strike * 2) / 2
            short_call_strike = round(short_call_strike * 2) / 2
            long_call_strike = round(long_call_strike * 2) / 2

            # Create legs
            expiration = datetime.now(timezone.utc) + timedelta(days=dte)

            legs = [
                OptionLeg('put', short_put_strike, -1, expiration),    # Short put (naked)
                OptionLeg('call', short_call_strike, -1, expiration),  # Short call
                OptionLeg('call', long_call_strike, 1, expiration),    # Long call
            ]

            # Estimate pricing and Greeks
            self._estimate_legs_pricing_and_greeks(legs, underlying_price, iv, dte)

            # Calculate metrics
            net_credit = self._calculate_net_credit(legs)
            max_profit = net_credit
            float('inf')  # Undefined risk on put side

            # Breakeven points
            breakeven_lower = short_put_strike - net_credit
            breakeven_upper = short_call_strike + net_credit

            prob_profit = self._estimate_probability_profit(underlying_price,
                                                          [breakeven_lower, breakeven_upper],
                                                          expected_move)

            # Net Greeks
            net_delta = sum(leg.delta * leg.quantity for leg in legs)
            net_gamma = sum(leg.gamma * leg.quantity for leg in legs)
            net_theta = sum(leg.theta * leg.quantity for leg in legs)
            net_vega = sum(leg.vega * leg.quantity for leg in legs)

            return MultiLegStructure(
                strategy_type=MultiLegStrategyType.JADE_LIZARD,
                legs=legs,
                net_credit=net_credit,
                max_profit=max_profit,
                max_loss=wing_width * 100,  # Practical max loss from call spread
                breakeven_points=[breakeven_lower, breakeven_upper],
                probability_profit=prob_profit,
                net_delta=net_delta,
                net_gamma=net_gamma,
                net_theta=net_theta,
                net_vega=net_vega,
                wing_width=wing_width,
                body_width=short_call_strike - short_put_strike,
                risk_reward_ratio=(wing_width * 100) / max_profit if max_profit > 0 else 0
            )

        except Exception as e:
            self.logger.error("Jade Lizard construction failed: %s", e, exc_info=True)
            raise

    def _calculate_optimal_wing_width(self, market_analysis: MarketEnvironmentAnalysis) -> float:
        """Calculate optimal wing width based on market conditions"""
        try:
            base_width = OPTIMAL_WING_WIDTH

            # Adjust based on volatility environment
            if market_analysis.volatility_environment == VolatilityEnvironment.HIGH_VOL:
                multiplier = 1.3
            elif market_analysis.volatility_environment == VolatilityEnvironment.LOW_VOL:
                multiplier = 0.7
            else:
                multiplier = 1.0

            # Adjust based on expected move
            expected_move = market_analysis.expected_move
            if expected_move > market_analysis.underlying_price * 0.05:  # > 5% move expected
                multiplier *= 1.2
            elif expected_move < market_analysis.underlying_price * 0.02:  # < 2% move expected
                multiplier *= 0.8

            adjusted_width = base_width * multiplier

            return max(MIN_WING_WIDTH, min(MAX_WING_WIDTH, adjusted_width))

        except Exception:
            return OPTIMAL_WING_WIDTH

    def _estimate_legs_pricing_and_greeks(self, legs: list[OptionLeg],
                                        underlying_price: float,
                                        implied_vol: float, dte: int):
        """Estimate option pricing and Greeks for all legs (simplified Black-Scholes)"""
        try:
            time_to_expiry = dte / 365.0

            for leg in legs:
                # Calculate moneyness
                moneyness = leg.strike / underlying_price

                # Estimate price based on moneyness and option type
                if leg.option_type == 'call':
                    if moneyness < 0.95:  # Deep ITM
                        leg.price = underlying_price - leg.strike + 0.5  # Intrinsic + time value
                        leg.delta = 0.90
                    elif moneyness < 0.98:  # ITM
                        leg.price = underlying_price - leg.strike + 2.0
                        leg.delta = 0.70
                    elif moneyness < 1.02:  # ATM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.4
                        leg.delta = 0.50
                    elif moneyness < 1.05:  # OTM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.2
                        leg.delta = 0.25
                    else:  # Deep OTM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.1
                        leg.delta = 0.10
                else:  # Put
                    if moneyness > 1.05:  # Deep ITM
                        leg.price = leg.strike - underlying_price + 0.5
                        leg.delta = -0.90
                    elif moneyness > 1.02:  # ITM
                        leg.price = leg.strike - underlying_price + 2.0
                        leg.delta = -0.70
                    elif moneyness > 0.98:  # ATM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.4
                        leg.delta = -0.50
                    elif moneyness > 0.95:  # OTM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.2
                        leg.delta = -0.25
                    else:  # Deep OTM
                        leg.price = underlying_price * implied_vol * np.sqrt(time_to_expiry) * 0.1
                        leg.delta = -0.10

                # Estimate other Greeks (simplified)
                leg.gamma = 0.05 if abs(moneyness - 1.0) < 0.05 else 0.02  # Higher gamma ATM
                leg.theta = -leg.price / (dte / 7) if dte > 0 else 0  # Weekly decay approximation
                leg.vega = underlying_price * 0.01 * np.sqrt(time_to_expiry)  # Vega approximation
                leg.implied_vol = implied_vol

        except Exception as e:
            self.logger.error("Legs pricing estimation failed: %s", e, exc_info=True)

    def _calculate_net_credit(self, legs: list[OptionLeg]) -> float:
        """Calculate net credit/debit for the strategy"""
        try:
            net_credit = 0.0
            for leg in legs:
                if leg.quantity > 0:  # Long position
                    net_credit -= leg.price * abs(leg.quantity)
                else:  # Short position
                    net_credit += leg.price * abs(leg.quantity)

            return net_credit

        except Exception:
            return 0.0

    def _estimate_probability_profit(self, underlying_price: float,
                                   breakeven_points: list[float],
                                   expected_move: float) -> float:
        """Estimate probability of profit based on breakeven points"""
        try:
            if len(breakeven_points) == 2:
                # Two breakevens (like iron condor)
                lower_be, upper_be = breakeven_points
                profit_range = upper_be - lower_be

                # Assume normal distribution centered on current price
                # Probability = range within breakevens / total likely range
                total_range = expected_move * 4  # ±2 standard deviations

                # Adjust for where current price sits relative to breakevens
                center_offset = abs((upper_be + lower_be) / 2 - underlying_price)
                prob = (profit_range - center_offset) / total_range

                return max(0.3, min(0.9, prob))  # Cap between 30% and 90%
            else:
                return 0.65  # Default probability

        except Exception:
            return 0.65

# ==============================================================================
# RL ENVIRONMENT — STRATEGY MORPHING / ADJUSTMENT
# ==============================================================================
if HAS_SB3:
    class StrategyMorphEnvironment(gym.Env):
        """
        RL environment for multi-leg strategy adjustment decisions.

        The agent observes an active multi-leg position's P&L, Greeks,
        time-to-expiration, and volatility context, then decides whether
        to hold, close, roll, or convert to a different spread structure.

        Observation (12-dim):
            [pnl_pct, days_held_norm, dte_norm, net_delta, net_gamma,
             net_theta, net_vega, iv_rank, vix_change, underlying_move,
             strategy_encoding, pop_estimate]

        Actions (7 discrete, matching AdjustmentAction enum):
            0=hold, 1=roll_untested_side, 2=add_extra_wings,
            3=convert_to_butterfly, 4=convert_to_condor,
            5=close_threatened_side, 6=roll_entire_position
        """

        ACTION_NAMES = [
            'hold', 'roll_untested_side', 'add_extra_wings',
            'convert_to_butterfly', 'convert_to_condor',
            'close_threatened_side', 'roll_entire_position',
        ]

        STRATEGY_ENCODINGS = {
            'iron_condor': 0.0,
            'iron_butterfly': 0.2,
            'jade_lizard': 0.4,
            'big_lizard': 0.6,
            'broken_wing_butterfly': 0.8,
            'double_diagonal': 1.0,
        }

        def __init__(self, episode_length: int = 30):
            super().__init__()
            self.observation_space = spaces.Box(
                low=-np.inf, high=np.inf, shape=(12,), dtype=np.float32
            )
            self.action_space = spaces.Discrete(7)
            self.episode_length = episode_length

            self.current_step = 0
            self.position_pnl = 0.0
            self.max_credit = 1.0
            self.total_dte = 30
            self.strategy_type = 'iron_condor'
            self.cumulative_reward = 0.0

        def reset(self) -> np.ndarray:
            self.current_step = 0
            self.position_pnl = 0.0
            self.max_credit = np.random.uniform(1.0, 5.0)
            self.total_dte = np.random.randint(14, 45)
            strategies = list(self.STRATEGY_ENCODINGS.keys())
            self.strategy_type = strategies[np.random.randint(0, len(strategies))]
            self.cumulative_reward = 0.0
            self._iv_rank = np.random.uniform(0.3, 0.9)
            self._vix = np.random.uniform(12, 40)
            self._underlying = np.random.uniform(400, 600)
            self._delta = np.random.uniform(-0.1, 0.1)
            self._gamma = np.random.uniform(-0.05, 0.05)
            self._theta = np.random.uniform(0.0, 0.5)
            self._vega = np.random.uniform(-15, 15)
            return self._get_obs()

        def step(self, action: int):
            # Simulate market dynamics
            underlying_move = np.random.normal(0, 0.01)
            vix_change = np.random.normal(0, 0.02)
            self._iv_rank = np.clip(self._iv_rank + np.random.normal(0, 0.02), 0, 1)
            self._vix = max(8, self._vix + vix_change * self._vix)
            self._underlying *= (1 + underlying_move)

            # Greeks evolve
            self._delta += underlying_move * self._gamma * 100
            self._theta *= max(0.9, 1.0 - 1.0 / max(1, self.total_dte - self.current_step))

            # Compute P&L change from theta + delta exposure
            pnl_change = self._theta * 0.05 - abs(self._delta) * abs(underlying_move) * self._underlying  # noqa: E501
            self.position_pnl += pnl_change

            # Reward based on action quality
            if action == 0:  # Hold
                reward = float(pnl_change / max(0.1, self.max_credit))
            elif action in [1, 2, 3, 4]:  # Adjust
                adjustment_cost = np.random.uniform(0.05, 0.15) * self.max_credit
                adjustment_benefit = abs(self._delta) * 0.5  # Reduce delta
                self._delta *= 0.5  # Adjustments reduce delta
                reward = float((adjustment_benefit - adjustment_cost) / max(0.1, self.max_credit))
            elif action == 5:  # Close threatened side
                close_benefit = max(0, self.position_pnl * 0.3)
                reward = float(close_benefit / max(0.1, self.max_credit) - 0.1)
            else:  # Roll entire
                roll_cost = np.random.uniform(0.1, 0.3) * self.max_credit
                roll_benefit = self._theta * 0.3 + self.max_credit * 0.1
                reward = float((roll_benefit - roll_cost) / max(0.1, self.max_credit))

            self.cumulative_reward += reward
            self.current_step += 1
            done = self.current_step >= self.episode_length

            info = {
                'action': self.ACTION_NAMES[action],
                'pnl': self.position_pnl,
                'cumulative_reward': self.cumulative_reward,
            }
            return self._get_obs(), float(reward), done, info

        def _get_obs(self) -> np.ndarray:
            remaining_dte = max(0, self.total_dte - self.current_step)
            return np.array([
                self.position_pnl / max(0.1, self.max_credit),  # pnl_pct
                self.current_step / max(1, self.episode_length),  # days_held_norm
                remaining_dte / 45.0,  # dte_norm
                self._delta,
                self._gamma,
                self._theta,
                self._vega / 15.0,
                self._iv_rank,
                0.0,  # vix_change (latest)
                0.0,  # underlying_move (latest)
                self.STRATEGY_ENCODINGS.get(self.strategy_type, 0.0),
                0.65,  # pop_estimate placeholder
            ], dtype=np.float32)


# ==============================================================================
# MAIN MULTI-LEG STRATEGY COORDINATOR
# ==============================================================================
class MultiLegStrategyCoordinator:
    """
    Multi-Leg Strategy Coordinator.

    Consolidates D02 Iron Condor, D10 Iron Butterfly, and other complex
    multi-leg strategies into intelligent unified coordination system.
    """

    def __init__(self, config: dict[str, Any] = None, order_manager=None):
        """Initialize multi-leg strategy coordinator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # Optional OrderManager for real/paper broker routing.
        # When provided, execute_multileg_strategy will submit combo orders
        # to Tradier rather than only updating in-memory position state.
        self.order_manager = order_manager

        # Initialize analysis and construction engines
        self.market_analyzer = MultiLegMarketAnalyzer(self.config.get('analyzer_config', {}))
        self.strategy_constructor = MultiLegStrategyConstructor(self.config.get('constructor_config', {}))  # noqa: E501

        # Integration with unified systems
        self.regime_engine = None
        self.risk_coordinator = None

        if REGIME_ENGINE_AVAILABLE:
            try:
                self.regime_engine = get_unified_regime_engine()
                self.logger.info("Connected to unified regime engine")
            except Exception as e:
                self.logger.warning("Could not connect to regime engine: %s", e, exc_info=True)

        if RISK_COORDINATOR_AVAILABLE:
            try:
                self.risk_coordinator = get_unified_risk_coordinator()
                self.logger.info("Connected to unified risk coordinator")
            except Exception as e:
                self.logger.warning("Could not connect to risk coordinator: %s", e, exc_info=True)

        # Position management
        self.active_positions: dict[str, MultiLegPosition] = {}
        self.position_history: list[MultiLegPosition] = []

        # Performance tracking
        self.performance_metrics = {
            'total_positions': 0,
            'winning_positions': 0,
            'losing_positions': 0,
            'win_rate': 0.0,
            'total_profit': 0.0,
            'max_loss': 0.0,
            'avg_credit': 0.0,
            'avg_hold_days': 0.0,
            'avg_max_profit_achieved': 0.0,
            'strategy_breakdown': {
                'iron_condor': {'count': 0, 'profit': 0.0},
                'iron_butterfly': {'count': 0, 'profit': 0.0},
                'jade_lizard': {'count': 0, 'profit': 0.0}
            }
        }

        # Configuration
        self.max_positions = self.config.get('max_positions', MAX_MULTILEG_POSITIONS)
        self.profit_target = self.config.get('profit_target', PROFIT_TARGET_PERCENT)
        self.stop_loss = self.config.get('stop_loss', STOP_LOSS_PERCENT)

        # Threading
        self._lock = threading.RLock()

        # Greeks freshness tracking
        self._greeks_last_updated: datetime | None = None

        # RL strategy morph model (optional)
        self._rl_morph_model = None
        self._rl_morph_enabled = HAS_SB3
        self._load_rl_morph_model()

        self.logger.info("MultiLegStrategyCoordinator initialized successfully")

    def _load_rl_morph_model(self, model_path: str | None = None) -> None:
        """Load pre-trained RL strategy morphing model if available."""
        if not HAS_SB3:
            self._rl_morph_enabled = False
            return
        try:
            if model_path:
                self._rl_morph_model = PPO.load(model_path)
                self.logger.info("RL morph model loaded from %s", model_path)
            else:
                default_path = "models/rl/strategy_morph/strategy_morph_PPO_final"
                if os.path.exists(default_path + ".zip"):
                    self._rl_morph_model = PPO.load(default_path)
                    self.logger.info("RL morph model loaded from default path")
                else:
                    self._rl_morph_enabled = False
        except Exception as e:
            self._rl_morph_enabled = False
            self.logger.warning("Failed to load RL morph model: %s", e, exc_info=True)

    def _get_rl_adjustment_recommendation(
        self,
        position: 'MultiLegPosition',
        market_analysis: 'MarketEnvironmentAnalysis',
    ) -> AdjustmentAction | None:
        """
        Query RL model for position adjustment recommendation.

        Args:
            position: Active multi-leg position.
            market_analysis: Current market environment analysis.

        Returns:
            AdjustmentAction if RL recommends one, None if hold or disabled.
        """
        if not self._rl_morph_enabled or self._rl_morph_model is None:
            return None

        # Greeks staleness check — warn if position Greeks are stale
        GREEKS_STALENESS_SECONDS = 300  # 5 minutes
        if self._greeks_last_updated:
            age = (datetime.now(timezone.utc) - self._greeks_last_updated).total_seconds()
            if age > GREEKS_STALENESS_SECONDS:
                self.logger.warning(
                    f"Greeks are {age:.0f}s old (>{GREEKS_STALENESS_SECONDS}s threshold). "
                    "Position management may be inaccurate. Refresh from broker."
                )

        try:
            remaining_dte = max(0, MAX_DTE_MULTILEG - position.days_held)
            strategy_enc = {
                MultiLegStrategyType.IRON_CONDOR: 0.0,
                MultiLegStrategyType.IRON_BUTTERFLY: 0.2,
                MultiLegStrategyType.JADE_LIZARD: 0.4,
                MultiLegStrategyType.BIG_LIZARD: 0.6,
                MultiLegStrategyType.BROKEN_WING_BUTTERFLY: 0.8,
                MultiLegStrategyType.DOUBLE_DIAGONAL: 1.0,
            }.get(position.strategy_structure.strategy_type, 0.0)

            obs = np.array([
                position.unrealized_pnl / max(0.1, position.entry_net_credit),
                position.days_held / 45.0,
                remaining_dte / 45.0,
                position.current_delta,
                position.current_gamma,
                position.current_theta,
                position.current_vega / 15.0,
                market_analysis.iv_rank,
                (market_analysis.vix_level - position.vix_at_entry) / max(1.0, position.vix_at_entry),  # noqa: E501
                (market_analysis.underlying_price - position.underlying_price_at_entry)
                    / position.underlying_price_at_entry,
                strategy_enc,
                market_analysis.iv_percentile,
            ], dtype=np.float32)

            action, _ = self._rl_morph_model.predict(obs, deterministic=True)
            action = int(action)

            if action == 0:
                return None  # Hold

            action_map = {
                1: AdjustmentAction.ROLL_UNTESTED_SIDE,
                2: AdjustmentAction.ADD_EXTRA_WINGS,
                3: AdjustmentAction.CONVERT_TO_BUTTERFLY,
                4: AdjustmentAction.CONVERT_TO_CONDOR,
                5: AdjustmentAction.CLOSE_THREATENED_SIDE,
                6: AdjustmentAction.ROLL_ENTIRE_POSITION,
            }
            recommended = action_map.get(action)
            if recommended:
                self.logger.info(
                    "RL recommends %s for position %s", recommended.value, position.position_id
                )
            return recommended

        except Exception as e:
            self.logger.warning("RL adjustment recommendation failed: %s", e, exc_info=True)
            return None

    # ==========================================================================
    # PUBLIC METHODS - MAIN INTERFACE
    # ==========================================================================
    async def analyze_multileg_opportunity(self, market_data: pd.DataFrame,
                                         strategy_type: MultiLegStrategyType = MultiLegStrategyType.AUTO_SELECT) -> MultiLegStructure | None:  # noqa: E501
        """
        Analyze market for multi-leg strategy opportunities.

        Args:
            market_data: Recent market data
            strategy_type: Specific strategy type or AUTO_SELECT

        Returns:
            MultiLegStructure if opportunity found, None otherwise
        """
        try:
            # Enforce position count limit
            active_count = len(self.active_positions)
            if active_count >= MAX_MULTILEG_POSITIONS:
                self.logger.warning(
                    f"Position limit reached ({active_count}/{MAX_MULTILEG_POSITIONS}). "
                    "Skipping entry."
                )
                return None

            # Enforce portfolio allocation limit
            if hasattr(self, 'portfolio_value') and self.portfolio_value > 0:
                allocated = getattr(self, 'total_allocated', 0)
                if allocated / self.portfolio_value >= MAX_PORTFOLIO_ALLOCATION:
                    self.logger.warning(
                        f"Portfolio allocation limit reached "
                        f"({allocated/self.portfolio_value:.1%} >= "
                        f"{MAX_PORTFOLIO_ALLOCATION:.1%}). Skipping entry."
                    )
                    return None

            # Analyze market environment
            market_analysis = self.market_analyzer.analyze_environment(market_data)

            # Check if conditions favor multi-leg strategies
            if not self._are_conditions_favorable(market_analysis):
                return None

            # Construct optimal strategy
            strategy_structure = self.strategy_constructor.construct_strategy(
                strategy_type, market_analysis
            )

            if strategy_structure and self._validate_strategy_structure(strategy_structure, market_analysis):  # noqa: E501
                self.logger.info(f"Multi-leg opportunity identified: "
                               f"{strategy_structure.strategy_type.value} with "
                               f"${strategy_structure.net_credit:.2f} credit")
                return strategy_structure

            return None

        except Exception as e:
            self.logger.error("Multi-leg opportunity analysis failed: %s", e, exc_info=True)
            return None

    def _are_conditions_favorable(self, market_analysis: MarketEnvironmentAnalysis) -> bool:
        """Check if market conditions favor multi-leg strategies"""
        try:
            # Need sufficient implied volatility
            if market_analysis.implied_volatility < MIN_IMPLIED_VOLATILITY:
                self.logger.debug(f"IV too low: {market_analysis.implied_volatility:.1%}")
                return False

            # Avoid extreme volatility unless specifically targeting it
            if (market_analysis.volatility_environment == VolatilityEnvironment.EXTREME_VOL and
                market_analysis.vix_level > 50):
                self.logger.debug("VIX too extreme: %s", market_analysis.vix_level)
                return False

            # Need reasonable IV rank for good premium collection
            if market_analysis.iv_rank < 0.3:
                self.logger.debug(f"IV rank too low: {market_analysis.iv_rank:.1%}")
                return False

            # Check for unusual market conditions
            if market_analysis.unusual_activity and market_analysis.volatility_environment == VolatilityEnvironment.EXTREME_VOL:  # noqa: E501
                self.logger.debug("Unusual activity with extreme volatility")
                return False

            return True

        except Exception:
            return False

    def _validate_strategy_structure(self, structure: MultiLegStructure,
                                   market_analysis: MarketEnvironmentAnalysis) -> bool:
        """Validate strategy structure meets requirements"""
        try:
            # Check net credit is reasonable
            if structure.net_credit < 0.5:  # Minimum $0.50 credit
                self.logger.debug(f"Net credit too low: ${structure.net_credit:.2f}")
                return False

            # Check probability of profit
            if structure.probability_profit < 0.4:  # Minimum 40% PoP
                self.logger.debug(f"PoP too low: {structure.probability_profit:.1%}")
                return False

            # Check risk/reward ratio
            if structure.risk_reward_ratio > 4.0:  # Max 4:1 risk/reward
                self.logger.debug(f"Risk/reward too high: {structure.risk_reward_ratio:.1f}")
                return False

            # Validate bid/ask spread width per leg
            MAX_SPREAD_PCT = 0.10  # 10% of mark price max spread
            for leg in getattr(structure, 'legs', []):
                if hasattr(leg, 'bid') and hasattr(leg, 'ask') and leg.bid and leg.ask:
                    mark = (leg.bid + leg.ask) / 2
                    spread_pct = (leg.ask - leg.bid) / mark if mark > 0 else 1.0
                    if spread_pct > MAX_SPREAD_PCT:
                        self.logger.warning(
                            f"Leg spread too wide: {spread_pct:.1%} > {MAX_SPREAD_PCT:.1%} max. "
                            f"Bid: {leg.bid}, Ask: {leg.ask}. Skipping entry."
                        )
                        return False

            # Check net delta for neutral strategies
            if structure.strategy_type in [MultiLegStrategyType.IRON_CONDOR, MultiLegStrategyType.IRON_BUTTERFLY]:  # noqa: E501
                if abs(structure.net_delta) > MAX_NET_DELTA:
                    self.logger.debug(f"Net delta too high: {structure.net_delta:.3f}")
                    return False

            # Check Greeks limits
            if abs(structure.net_vega) > MAX_VEGA_RISK:
                self.logger.debug(f"Vega risk too high: {structure.net_vega:.1f}")
                return False

            return True

        except Exception:
            return False

    async def execute_multileg_strategy(self, strategy_structure: MultiLegStructure) -> str | None:
        """
        Execute multi-leg strategy.

        When an ``OrderManager`` instance has been injected, the legs are
        submitted as a **single combo order** (Iron Condor or credit spread)
        to eliminate inter-leg slippage.  Without an ``OrderManager`` the
        method operates in simulation mode and only updates in-memory state.

        Args:
            strategy_structure: Strategy structure to execute

        Returns:
            Position ID if successful, None if failed
        """
        try:
            position_id = str(uuid.uuid4())

            # Get current market analysis for context
            market_analysis = self.market_analyzer.analyze_environment(pd.DataFrame())  # Would use real data  # noqa: E501

            # ------------------------------------------------------------------
            # BROKER ROUTING: submit as a single combo order when possible.
            # This eliminates inter-leg slippage that occurs when legs are
            # sent sequentially as individual single-leg orders.
            # ------------------------------------------------------------------
            broker_order_id: int | None = None
            if self.order_manager is not None:
                try:
                    broker_order_id = self._submit_combo_order(
                        strategy_structure, position_id
                    )
                    if broker_order_id is None:
                        self.logger.warning(
                            f"Combo order submission failed for "
                            f"{strategy_structure.strategy_type.value} — "
                            f"aborting execution"
                        )
                        return None
                    self.logger.info(
                        "Combo order submitted: Tradier ID=%s", broker_order_id
                    )
                except Exception as broker_exc:
                    self.logger.error(
                        f"Broker routing error for {strategy_structure.strategy_type.value}: "
                        f"{broker_exc} — aborting"
                    )
                    return None
            else:
                self.logger.debug(
                    "No OrderManager — running in simulation mode (no broker order sent)"
                )
            # ------------------------------------------------------------------

            # Create position
            position = MultiLegPosition(
                position_id=position_id,
                strategy_structure=strategy_structure,
                entry_time=datetime.now(timezone.utc),
                entry_net_credit=strategy_structure.net_credit,
                current_value=strategy_structure.net_credit,
                unrealized_pnl=0.0,
                status=PositionStatus.ACTIVE,
                days_held=0,
                market_condition_at_entry=market_analysis.market_condition,
                volatility_environment_at_entry=market_analysis.volatility_environment,
                underlying_price_at_entry=market_analysis.underlying_price,
                vix_at_entry=market_analysis.vix_level,
                current_delta=strategy_structure.net_delta,
                current_gamma=strategy_structure.net_gamma,
                current_theta=strategy_structure.net_theta,
                current_vega=strategy_structure.net_vega
            )
            if broker_order_id is not None:
                position.broker_order_id = broker_order_id  # type: ignore[attr-defined]

            # Store position
            with self._lock:
                self.active_positions[position_id] = position

                # Update performance metrics
                self.performance_metrics['total_positions'] += 1
                strategy_key = strategy_structure.strategy_type.value
                if strategy_key in self.performance_metrics['strategy_breakdown']:
                    self.performance_metrics['strategy_breakdown'][strategy_key]['count'] += 1

                # Update average credit
                total_positions = self.performance_metrics['total_positions']
                self.performance_metrics['avg_credit'] = (
                    (self.performance_metrics['avg_credit'] * (total_positions - 1) +
                     strategy_structure.net_credit) / total_positions
                )

            self.logger.info(f"Executed {strategy_structure.strategy_type.value}: "
                           f"Position {position_id}, Credit ${strategy_structure.net_credit:.2f}, "
                           f"Max Profit ${strategy_structure.max_profit:.2f}")

            return position_id

        except Exception as e:
            self.logger.error("Multi-leg strategy execution failed: %s", e, exc_info=True)
            return None

    def _submit_combo_order(
        self,
        strategy_structure: MultiLegStructure,
        position_id: str,
    ) -> int | None:
        """
        Route the strategy to the OrderManager as a single all-or-nothing
        combo order, preventing inter-leg slippage.

        Supported strategy types:
        - ``IRON_CONDOR`` → ``submit_iron_condor``
        - ``IRON_BUTTERFLY`` → ``submit_iron_condor`` (ATM variant)
        - All others with defined legs → ``submit_multileg_order``

        Args:
            strategy_structure: Constructed strategy with strike/leg details.
            position_id: Local UUID for the position (used as a tag).

        Returns:
            Tradier order ID on success, ``None`` on failure.
        """
        from Spyder.SpyderB_Broker.SpyderB40_TradierClient import OptionLeg

        s = strategy_structure
        strategy_type = s.strategy_type

        try:
            # ----- Iron Condor (and Iron Butterfly treated identically) -----
            if strategy_type in (
                MultiLegStrategyType.IRON_CONDOR,
                MultiLegStrategyType.IRON_BUTTERFLY,
            ):
                # Expect legs list: [put_long, put_short, call_short, call_long]
                if len(s.legs) >= 4:
                    result = self.order_manager.submit_iron_condor(
                        symbol=s.underlying_symbol,
                        expiration=s.expiration_date,
                        put_buy_strike=min(leg.strike for leg in s.legs if leg.option_type == 'put'),  # noqa: E501
                        put_sell_strike=max(
                            leg.strike for leg in s.legs
                            if leg.option_type == 'put' and leg.action in ('sell_to_open', 'sell')
                        ),
                        call_sell_strike=min(
                            leg.strike for leg in s.legs
                            if leg.option_type == 'call' and leg.action in ('sell_to_open', 'sell')
                        ),
                        call_buy_strike=max(leg.strike for leg in s.legs if leg.option_type == 'call'),  # noqa: E501
                        quantity=s.contracts,
                        price=s.net_credit,  # target net credit
                        strategy_name=f"{strategy_type.value}:{position_id[:8]}",
                    )
                    if result.success:
                        return result.tradier_order_id
                    self.logger.error("Iron condor order rejected: %s", result.message)
                    return None

            # ----- Jade Lizard and other multi-leg structures ---------------
            if s.legs:
                tradier_legs = [
                    OptionLeg(
                        option_symbol=leg.option_symbol,
                        side=leg.action,  # sell_to_open / buy_to_open
                        quantity=s.contracts,
                    )
                    for leg in s.legs
                ]
                result = self.order_manager.submit_multileg_order(
                    symbol=s.underlying_symbol,
                    legs=tradier_legs,
                    order_type="credit" if s.net_credit > 0 else "debit",
                    price=abs(s.net_credit),
                    strategy_name=f"{strategy_type.value}:{position_id[:8]}",
                )
                if result.success:
                    return result.tradier_order_id
                self.logger.error("Multileg order rejected: %s", result.message)
                return None

            self.logger.warning(
                "No legs defined for %s — cannot route combo order", strategy_type.value
            )
            return None

        except Exception as exc:
            self.logger.error("_submit_combo_order error: %s", exc, exc_info=True)
            return None

    def get_coordinator_status(self) -> dict[str, Any]:
        """Get comprehensive coordinator status"""
        with self._lock:
            # Count strategies
            strategy_counts = defaultdict(int)
            total_risk = 0.0
            total_credit = 0.0
            total_unrealized_pnl = 0.0

            for position in self.active_positions.values():
                strategy_counts[position.strategy_structure.strategy_type.value] += 1
                total_risk += position.strategy_structure.max_loss
                total_credit += position.entry_net_credit
                total_unrealized_pnl += position.unrealized_pnl

            return {
                'coordinator_name': 'MultiLegStrategyCoordinator',
                'active_positions': len(self.active_positions),
                'max_positions': self.max_positions,
                'strategy_breakdown': dict(strategy_counts),
                'exposure': {
                    'total_credit_collected': total_credit,
                    'total_risk_capital': total_risk,
                    'unrealized_pnl': total_unrealized_pnl,
                    'portfolio_utilization': total_risk / 100000  # Placeholder
                },
                'performance_metrics': self.performance_metrics,
                'integration_status': {
                    'regime_engine': REGIME_ENGINE_AVAILABLE,
                    'risk_coordinator': RISK_COORDINATOR_AVAILABLE,
                    'credit_spread_engine': CREDIT_SPREAD_ENGINE_AVAILABLE
                }
            }

    def get_consolidation_report(self) -> dict[str, Any]:
        """Get D-Series multi-leg consolidation report"""
        return {
            'consolidation_name': 'D-Series Multi-Leg Strategy Consolidation',
            'consolidated_modules': [
                'D02_IronCondor',
                'D10_IronButterfly',
                'Future complex multi-leg strategies (Jade Lizard, etc.)'
            ],
            'consolidation_benefits': [
                'Unified strategy selection and construction logic',
                'Intelligent market analysis for optimal multi-leg strategies',
                'Consolidated Greeks management and risk monitoring',
                'Advanced adjustment and defense mechanisms',
                'Single position management system for all multi-leg strategies',
                'Enhanced volatility environment analysis and adaptation'
            ],
            'feature_improvements': {
                'strategy_selection': 'Auto-selection based on volatility environment and market conditions',  # noqa: E501
                'construction_logic': 'Advanced algorithms for optimal strike selection and wing sizing',  # noqa: E501
                'greeks_management': 'Unified Greeks monitoring and delta-hedging capabilities',
                'adjustment_logic': 'Sophisticated adjustment and defense strategies',
                'performance_tracking': 'Comprehensive metrics across all multi-leg strategy types'
            },
            'eliminated_redundancies': [
                'Duplicate strategy construction algorithms',
                'Overlapping Greeks calculation methods',
                'Redundant market analysis for multi-leg suitability',
                'Multiple position management systems'
            ],
            'performance_gains': {
                'code_reduction': '~50% less duplicate multi-leg code',
                'decision_consistency': 'Unified logic prevents conflicting strategy selection',
                'maintenance_efficiency': 'Single coordinator vs multiple separate strategies',
                'enhanced_intelligence': 'Advanced market analysis drives better strategy selection'
            }
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_multileg_strategy_coordinator(config: dict[str, Any] = None) -> MultiLegStrategyCoordinator:  # noqa: E501
    """
    Create multi-leg strategy coordinator instance.

    Args:
        config: Optional configuration dictionary

    Returns:
        MultiLegStrategyCoordinator instance
    """
    return MultiLegStrategyCoordinator(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing and demonstration

    # Create multi-leg strategy coordinator
    config = {
        'max_positions': 2,
        'profit_target': 0.25,
        'stop_loss': 2.0
    }

    coordinator = create_multileg_strategy_coordinator(config)

    status = coordinator.get_coordinator_status()
    for _integration, available in status['integration_status'].items():
        status_symbol = '✅' if available else '❌'

    # Create test market data for high volatility environment
    dates = pd.date_range(start='2024-01-01', periods=60, freq='D')

    # High volatility market scenario
    base_price = 450
    volatility_factor = 0.03  # 3% daily volatility
    noise = np.random.randn(60) * base_price * volatility_factor
    trend = np.linspace(0, 10, 60)  # Slight uptrend
    prices = base_price + trend + noise

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(60) * 1,
        'high': prices + abs(np.random.randn(60) * 3),
        'low': prices - abs(np.random.randn(60) * 3),
        'close': prices,
        'volume': np.random.lognormal(17, 0.4, 60),
        'vix': 30 + 10 * np.random.beta(2, 2, 60),  # High VIX environment
        'put_volume': np.random.lognormal(15, 0.3, 60),
        'call_volume': np.random.lognormal(15, 0.2, 60)
    })

    current_price = prices[-1]
    current_vix = market_data['vix'].iloc[-1]


    # Test market environment analysis
    market_analysis = coordinator.market_analyzer.analyze_environment(market_data)


    # Test multi-leg opportunity analysis

    import asyncio

    async def run_multileg_analysis():
        # Test auto-selection
        auto_opportunity = await coordinator.analyze_multileg_opportunity(market_data)
        return auto_opportunity

    opportunity = asyncio.run(run_multileg_analysis())

    if opportunity:

        for _i, leg in enumerate(opportunity.legs):
            action = "BUY" if leg.quantity > 0 else "SELL"


        if len(opportunity.breakeven_points) == 2:
            lower, upper = opportunity.breakeven_points
            current_distance_lower = abs(current_price - lower)
            current_distance_upper = abs(current_price - upper)

        # Test strategy execution

        async def run_execution():
            position_id = await coordinator.execute_multileg_strategy(opportunity)
            return position_id

        position_id = asyncio.run(run_execution())

        if position_id:

            # Show position details
            position = coordinator.active_positions[position_id]

        else:
            pass

    else:
        pass

    # Test different strategy types

    strategy_types = [
        MultiLegStrategyType.IRON_CONDOR,
        MultiLegStrategyType.IRON_BUTTERFLY,
        MultiLegStrategyType.JADE_LIZARD
    ]

    for strategy_type in strategy_types:

        # Construct specific strategy
        specific_structure = coordinator.strategy_constructor.construct_strategy(
            strategy_type, market_analysis
        )

        if specific_structure:
            pass
        else:
            pass

    # Show final coordinator status
    final_status = coordinator.get_coordinator_status()

    if final_status['strategy_breakdown']:
        for _strategy, _count in final_status['strategy_breakdown'].items():
            pass


    # Performance metrics
    pm = final_status['performance_metrics']

    # Show consolidation benefits
    consolidation = coordinator.get_consolidation_report()
    for _benefit in consolidation['consolidation_benefits']:
        pass

    for _redundancy in consolidation['eliminated_redundancies']:
        pass

    for _metric, _value in consolidation['performance_gains'].items():
        pass

