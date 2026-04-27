#!/usr/bin/env python3
from __future__ import annotations
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD02_IronCondor.py
Purpose: Iron Condor strategy with consolidated multi-leg infrastructure (Updated)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 16:30:00

Module Description:
    Iron Condor strategy implementation focused on strategy-specific entry/exit logic
    and market analysis. Generic multi-leg construction, order management, and Greeks
    calculations have been moved to SpyderD32_MultiLegStrategyCoordinator for
    consolidation and code reuse across all multi-leg strategies.

CONSOLIDATION UPDATE:
    Generic multi-leg infrastructure REMOVED and consolidated into D26_MultiLegStrategyCoordinator.
    This module now focuses exclusively on Iron Condor specific trading logic:
    - Iron Condor entry criteria and market condition analysis
    - Strike selection methodology specific to Iron Condor
    - Profit targets and stop loss rules for Iron Condor
    - Adjustment techniques specific to Iron Condor strategy
    - Exit criteria and position management for Iron Condor

Key Features:
    • Iron Condor specific entry conditions (high IV, range-bound market)
    • Strike selection at 16-20 delta puts/calls for optimal risk/reward
    • Dynamic profit targets (25-50% of credit received)
    • Stop loss at 2x credit received or delta breach
    • Time decay management (close at 21-45 DTE)
    • Iron Condor specific adjustment techniques
    • Integration with D26 for multi-leg execution

Removed Infrastructure:
    • Generic multi-leg order management - Now in D26
    • Combined Greeks calculations - Now in D26
    • Multi-leg position sizing - Now in D26
    • Generic P&L calculations - Now in D26
    • Position group validation - Now in D26
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime
from typing import Any
from dataclasses import dataclass
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile

# Integration with consolidated multi-leg coordinator
try:
    from SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
        MultiLegStrategyCoordinator, MultiLegStrategyType, get_multileg_coordinator  # noqa: F401
    )
    MULTILEG_COORDINATOR_AVAILABLE = True
except ImportError:
    MULTILEG_COORDINATOR_AVAILABLE = False

# Integration with event management
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType  # noqa: F401
    EVENT_MANAGER_AVAILABLE = True
except ImportError:
    EVENT_MANAGER_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Iron Condor specific parameters
IC_MIN_IV_RANK = 40                    # Minimum IV rank for IC entry
IC_OPTIMAL_IV_RANK = 60                # Optimal IV rank for IC
IC_MAX_IV_RANK = 80                    # Maximum IV rank (too high)

IC_DELTA_TARGET_PUT = -0.16            # Target delta for short put (16 delta)
IC_DELTA_TARGET_CALL = 0.16            # Target delta for short call (16 delta)
IC_DELTA_TOLERANCE = 0.04              # Tolerance for delta selection

IC_MIN_DTE = 21                        # Minimum days to expiration
IC_MAX_DTE = 45                        # Maximum days to expiration
IC_OPTIMAL_DTE = 30                    # Optimal days to expiration

IC_PROFIT_TARGET_MIN = 0.25            # 25% profit target
IC_PROFIT_TARGET_MAX = 0.50            # 50% profit target
IC_STOP_LOSS_MULTIPLIER = 2.0          # 2x credit received

IC_MIN_CREDIT = 0.30                   # Minimum credit per contract
IC_MAX_WIDTH = 10.0                    # Maximum spread width

# Market condition thresholds
IC_MIN_EXPECTED_MOVE_RATIO = 0.8       # Minimum expected move vs spread width
IC_MAX_EXPECTED_MOVE_RATIO = 1.2       # Maximum expected move vs spread width
IC_VOLATILITY_SKEW_MAX = 0.05          # Maximum acceptable volatility skew

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class IronCondorState(Enum):
    """Iron Condor position states"""
    ANALYZING = auto()
    READY_TO_ENTER = auto()
    ENTERING = auto()
    ACTIVE = auto()
    MONITORING = auto()
    PROFIT_TARGET_HIT = auto()
    STOP_LOSS_HIT = auto()
    ADJUSTING = auto()
    CLOSING = auto()
    CLOSED = auto()
    ERROR = auto()

class IronCondorAdjustmentType(Enum):
    """Types of Iron Condor adjustments"""
    ROLL_PUT_SIDE = "roll_put_side"
    ROLL_CALL_SIDE = "roll_call_side"
    CONVERT_TO_BUTTERFLY = "convert_to_butterfly"
    CLOSE_UNTESTED_SIDE = "close_untested_side"
    ROLL_ENTIRE_STRUCTURE = "roll_entire_structure"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class IronCondorSetup:
    """Iron Condor strategy setup parameters"""
    underlying_price: float
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    expiration_date: datetime
    days_to_expiry: int
    expected_credit: float
    max_profit: float
    max_loss: float
    probability_of_profit: float
    iv_rank: float
    expected_move: float
    setup_quality_score: float

@dataclass
class IronCondorAnalysis:
    """Iron Condor market analysis results"""
    market_suitable: bool
    iv_analysis: dict[str, float]
    volatility_skew: float
    expected_move_analysis: dict[str, float]
    trend_analysis: dict[str, Any]
    optimal_strikes: dict[str, float] | None
    setup_recommendation: str
    confidence_score: float
    risk_warnings: list[str]

# ==============================================================================
# MAIN IRON CONDOR STRATEGY CLASS
# ==============================================================================
class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy with consolidated multi-leg infrastructure.

    Focuses exclusively on Iron Condor specific trading logic while leveraging
    the consolidated multi-leg coordinator (D26) for infrastructure operations.

    This implementation handles:
    - Iron Condor specific entry criteria
    - Strike selection methodology
    - Profit targets and risk management
    - Strategy-specific adjustments
    - Exit criteria and timing
    """

    def __init__(self, event_manager: EventManager = None,
                 risk_profile: RiskProfile = None, config: dict[str, Any] = None):
        """Initialize Iron Condor strategy"""

        # Initialize base strategy
        super().__init__(
            name="Iron Condor Strategy",
            strategy_type="iron_condor",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {}
        )

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize multi-leg coordinator integration
        self.multileg_coordinator = None
        if MULTILEG_COORDINATOR_AVAILABLE:
            try:
                self.multileg_coordinator = get_multileg_coordinator()
                self.logger.info("✅ Connected to MultiLegStrategyCoordinator")
            except Exception as e:
                self.logger.error("Failed to connect to coordinator: %s", e)
        else:
            self.logger.warning("❌ MultiLegStrategyCoordinator not available")

        # Iron Condor specific configuration
        self.min_iv_rank = self.config.get('min_iv_rank', IC_MIN_IV_RANK)
        self.profit_target = self.config.get('profit_target', IC_PROFIT_TARGET_MIN)
        self.stop_loss_multiplier = self.config.get('stop_loss_multiplier', IC_STOP_LOSS_MULTIPLIER)
        self.min_dte = self.config.get('min_dte', IC_MIN_DTE)
        self.max_dte = self.config.get('max_dte', IC_MAX_DTE)
        self.min_credit = self.config.get('min_credit', IC_MIN_CREDIT)

        # Strategy state
        self.current_analysis: IronCondorAnalysis | None = None
        self.active_setups: list[IronCondorSetup] = []
        self.strategy_state = IronCondorState.ANALYZING

        # Performance tracking
        self.performance_metrics = {
            'total_ic_trades': 0,
            'winning_ic_trades': 0,
            'total_ic_profit': 0.0,
            'avg_ic_hold_days': 0.0,
            'ic_win_rate': 0.0,
            'avg_credit_captured': 0.0,
            'max_consecutive_losses': 0,
            'best_ic_trade': 0.0,
            'worst_ic_trade': 0.0
        }

        self.logger.info("🎯 IronCondorStrategy initialized with D26 integration")

    def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
        """Legacy adapter for BaseStrategy contract.

        Iron Condor evaluation currently runs through dedicated async analysis and
        coordinator pathways; this sync hook returns no direct entry signals.
        """
        return []

    def validate_signal(self, signal: Any) -> bool:
        """Basic safety gate for external signals."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: Any) -> int:
        """Use provided size when available, otherwise default to one contract."""
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else 1

    def should_exit_position(self, position: Any,
                             market_data: pd.DataFrame) -> tuple[bool, str]:
        """Generic stop/take-profit exit adapter for BaseStrategy contract."""
        if market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        stop_loss = getattr(position, "stop_loss", None)
        take_profit = getattr(position, "take_profit", None)
        position_type = str(getattr(getattr(position, "position_type", ""), "value", "")).lower()

        if stop_loss is not None:
            if position_type == "short":
                if current_price >= stop_loss:
                    return True, "stop_loss"
            elif current_price <= stop_loss:
                return True, "stop_loss"

        if take_profit is not None:
            if position_type == "short":
                if current_price <= take_profit:
                    return True, "take_profit"
            elif current_price >= take_profit:
                return True, "take_profit"

        return False, ""

    # ==========================================================================
    # IRON CONDOR SPECIFIC MARKET ANALYSIS
    # ==========================================================================

    async def analyze_iron_condor_opportunity(self, market_data: pd.DataFrame,
                                            option_chain: pd.DataFrame = None) -> IronCondorAnalysis:
        """
        Analyze market conditions for Iron Condor entry.

        This is Iron Condor specific analysis - generic analysis is in D26.
        """
        try:
            current_price = market_data['close'].iloc[-1]

            # IV Analysis (Iron Condor specific)
            iv_analysis = self._analyze_iv_for_iron_condor(market_data)

            # Volatility skew analysis
            volatility_skew = self._calculate_volatility_skew(option_chain) if option_chain is not None else 0.0

            # Expected move analysis
            expected_move_analysis = self._analyze_expected_move_for_ic(market_data, current_price)

            # Trend analysis (Iron Condor prefers range-bound)
            trend_analysis = self._analyze_trend_for_iron_condor(market_data)

            # Overall suitability
            market_suitable = self._assess_market_suitability_for_ic(
                iv_analysis, expected_move_analysis, trend_analysis
            )

            # Find optimal strikes if suitable
            optimal_strikes = None
            setup_recommendation = ""
            confidence_score = 0.0
            risk_warnings = []

            if market_suitable and option_chain is not None:
                optimal_strikes = self._find_optimal_iron_condor_strikes(
                    current_price, option_chain, iv_analysis
                )
                setup_recommendation, confidence_score = self._generate_ic_recommendation(
                    iv_analysis, expected_move_analysis, trend_analysis
                )
                risk_warnings = self._identify_ic_risk_warnings(
                    iv_analysis, expected_move_analysis, volatility_skew
                )

            analysis = IronCondorAnalysis(
                market_suitable=market_suitable,
                iv_analysis=iv_analysis,
                volatility_skew=volatility_skew,
                expected_move_analysis=expected_move_analysis,
                trend_analysis=trend_analysis,
                optimal_strikes=optimal_strikes,
                setup_recommendation=setup_recommendation,
                confidence_score=confidence_score,
                risk_warnings=risk_warnings
            )

            self.current_analysis = analysis
            return analysis

        except Exception as e:
            self.logger.error("Iron Condor analysis failed: %s", e)
            self.error_handler.handle_error(e, {"method": "analyze_iron_condor_opportunity"})

            return IronCondorAnalysis(
                market_suitable=False,
                iv_analysis={},
                volatility_skew=0.0,
                expected_move_analysis={},
                trend_analysis={},
                optimal_strikes=None,
                setup_recommendation="Analysis failed",
                confidence_score=0.0,
                risk_warnings=["Analysis error occurred"]
            )

    def _analyze_iv_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze implied volatility specifically for Iron Condor strategy"""
        try:
            # Get IV data (assuming it's in the market data)
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]

            # Calculate IV rank (simplified - would need historical IV data)
            iv_history = market_data.get('iv', pd.Series([0.20] * 100)).tail(252)  # 1 year
            iv_rank = (current_iv > iv_history).sum() / len(iv_history) * 100

            # Iron Condor IV analysis
            iv_analysis = {
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_suitable_for_ic': IC_MIN_IV_RANK <= iv_rank <= IC_MAX_IV_RANK,
                'iv_quality_score': self._calculate_iv_quality_score(current_iv, iv_rank),
                'iv_trend': 'rising' if current_iv > iv_history.mean() else 'falling'
            }

            return iv_analysis

        except Exception as e:
            self.logger.error("IV analysis failed: %s", e)
            return {
                'current_iv': 0.20,
                'iv_rank': 50.0,
                'iv_suitable_for_ic': False,
                'iv_quality_score': 0.0,
                'iv_trend': 'unknown'
            }

    def _calculate_iv_quality_score(self, current_iv: float, iv_rank: float) -> float:
        """Calculate IV quality score for Iron Condor (0.0 to 1.0)"""
        try:
            # Optimal IV rank for Iron Condor is around 60
            iv_rank_score = 1.0 - abs(iv_rank - IC_OPTIMAL_IV_RANK) / IC_OPTIMAL_IV_RANK

            # Prefer moderate to high IV for premium selling
            iv_level_score = min(1.0, current_iv / 0.25) if current_iv > 0.15 else 0.0

            # Combined score
            return (iv_rank_score * 0.6 + iv_level_score * 0.4)

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IV analysis failed: %s", e)
            return 0.0

    def _analyze_expected_move_for_ic(self, market_data: pd.DataFrame,
                                    current_price: float) -> dict[str, float]:
        """Analyze expected move for Iron Condor positioning"""
        try:
            # Calculate volatility-based expected move
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]
            days_to_expiry = 30  # Default assumption

            # Expected move calculation
            expected_move = current_price * current_iv * np.sqrt(days_to_expiry / 365)
            expected_move_pct = expected_move / current_price

            # Iron Condor specific analysis
            analysis = {
                'expected_move_dollars': expected_move,
                'expected_move_percent': expected_move_pct,
                'expected_move_suitable_for_ic': 0.02 <= expected_move_pct <= 0.06,  # 2-6%
                'move_quality_score': self._calculate_move_quality_score(expected_move_pct)
            }

            return analysis

        except Exception as e:
            self.logger.error("Expected move analysis failed: %s", e)
            return {
                'expected_move_dollars': 10.0,
                'expected_move_percent': 0.03,
                'expected_move_suitable_for_ic': True,
                'move_quality_score': 0.5
            }

    def _calculate_move_quality_score(self, expected_move_pct: float) -> float:
        """Calculate expected move quality for Iron Condor"""
        try:
            # Optimal expected move for IC is 3-4%
            optimal_move = 0.035

            if 0.02 <= expected_move_pct <= 0.06:
                # Within acceptable range
                deviation = abs(expected_move_pct - optimal_move)
                return max(0.0, 1.0 - deviation / 0.02)
            else:
                # Outside acceptable range
                return 0.0

        except (ValueError, ZeroDivisionError, TypeError) as e:
            self.logger.warning("Move quality calculation failed: %s", e)
            return 0.0

    def _analyze_trend_for_iron_condor(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze trend conditions for Iron Condor (prefers range-bound)"""
        try:
            # Calculate trend indicators
            closes = market_data['close'].tail(20)
            sma_20 = closes.mean()
            current_price = closes.iloc[-1]

            # Price vs moving average
            price_vs_sma = (current_price - sma_20) / sma_20

            # Volatility of recent returns
            returns = closes.pct_change().dropna()
            return_volatility = returns.std()

            # Range-bound detection
            high_20 = market_data['high'].tail(20).max()
            low_20 = market_data['low'].tail(20).min()
            range_size = (high_20 - low_20) / current_price

            # Range-bound is ideal for Iron Condor
            is_range_bound = range_size < 0.08 and abs(price_vs_sma) < 0.02

            return {
                'trend_strength': abs(price_vs_sma),
                'is_range_bound': is_range_bound,
                'range_size_percent': range_size,
                'return_volatility': return_volatility,
                'trend_suitable_for_ic': is_range_bound,
                'trend_quality_score': 1.0 if is_range_bound else 0.5
            }

        except Exception as e:
            self.logger.error("Trend analysis failed: %s", e)
            return {
                'trend_strength': 0.01,
                'is_range_bound': True,
                'range_size_percent': 0.05,
                'return_volatility': 0.01,
                'trend_suitable_for_ic': True,
                'trend_quality_score': 0.8
            }

    def _assess_market_suitability_for_ic(self, iv_analysis: dict,
                                        expected_move_analysis: dict,
                                        trend_analysis: dict) -> bool:
        """Assess overall market suitability for Iron Condor"""
        try:
            # All conditions must be met for Iron Condor
            iv_suitable = iv_analysis.get('iv_suitable_for_ic', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ic', False)
            trend_suitable = trend_analysis.get('trend_suitable_for_ic', False)

            return iv_suitable and move_suitable and trend_suitable

        except (KeyError, TypeError, AttributeError) as e:
            self.logger.warning("Market condition check failed: %s", e)
            return False

    # ==========================================================================
    # IRON CONDOR SPECIFIC STRIKE SELECTION
    # ==========================================================================

    def _find_optimal_iron_condor_strikes(self, current_price: float,
                                        option_chain: pd.DataFrame,
                                        iv_analysis: dict) -> dict[str, float] | None:
        """Find optimal strike selection for Iron Condor"""
        try:
            if option_chain is None or option_chain.empty:
                return None

            # Target deltas for Iron Condor
            target_put_delta = IC_DELTA_TARGET_PUT
            target_call_delta = IC_DELTA_TARGET_CALL

            # Find strikes closest to target deltas
            puts = option_chain[option_chain['option_type'] == 'put'].copy()
            calls = option_chain[option_chain['option_type'] == 'call'].copy()

            # Short put strike (around 16 delta)
            short_put_candidates = puts[
                (puts['delta'] >= target_put_delta - IC_DELTA_TOLERANCE) &
                (puts['delta'] <= target_put_delta + IC_DELTA_TOLERANCE)
            ]

            # Short call strike (around 16 delta)
            short_call_candidates = calls[
                (calls['delta'] >= target_call_delta - IC_DELTA_TOLERANCE) &
                (calls['delta'] <= target_call_delta + IC_DELTA_TOLERANCE)
            ]

            if short_put_candidates.empty or short_call_candidates.empty:
                return None

            # Select best strikes based on premium and liquidity
            short_put_strike = self._select_best_short_strike(short_put_candidates, 'put')
            short_call_strike = self._select_best_short_strike(short_call_candidates, 'call')

            # Find long strikes (protection)
            long_put_strike = self._find_long_protection_strike(
                puts, short_put_strike, 'put', current_price
            )
            long_call_strike = self._find_long_protection_strike(
                calls, short_call_strike, 'call', current_price
            )

            if not all([short_put_strike, long_put_strike, short_call_strike, long_call_strike]):
                return None

            # Validate strike selection
            if not self._validate_iron_condor_strikes(
                long_put_strike, short_put_strike, short_call_strike, long_call_strike
            ):
                return None

            return {
                'long_put_strike': long_put_strike,
                'short_put_strike': short_put_strike,
                'short_call_strike': short_call_strike,
                'long_call_strike': long_call_strike
            }

        except Exception as e:
            self.logger.error("Strike selection failed: %s", e)
            return None

    def _select_best_short_strike(self, candidates: pd.DataFrame, option_type: str) -> float | None:
        """Select best short strike from candidates"""
        try:
            if candidates.empty:
                return None

            # Score each candidate based on premium and liquidity
            candidates = candidates.copy()
            candidates['score'] = (
                candidates.get('bid', 0) * 0.4 +  # Premium weight
                candidates.get('volume', 0) * 0.0001 * 0.3 +  # Volume weight
                candidates.get('open_interest', 0) * 0.0001 * 0.3  # OI weight
            )

            # Select highest scoring strike
            best_candidate = candidates.loc[candidates['score'].idxmax()]
            return best_candidate['strike']

        except Exception as e:
            self.logger.error("Best strike selection failed: %s", e)
            return None

    def _find_long_protection_strike(self, options: pd.DataFrame, short_strike: float,
                                   option_type: str, current_price: float) -> float | None:
        """Find appropriate long protection strike"""
        try:
            if option_type == 'put':
                # Long put should be below short put
                candidates = options[options['strike'] < short_strike]
                target_width = min(IC_MAX_WIDTH, short_strike * 0.05)  # 5% of strike or max width
                target_strike = short_strike - target_width

                if candidates.empty:
                    return None

                # Find closest to target
                candidates['distance'] = abs(candidates['strike'] - target_strike)
                best_candidate = candidates.loc[candidates['distance'].idxmin()]

            else:  # call
                # Long call should be above short call
                candidates = options[options['strike'] > short_strike]
                target_width = min(IC_MAX_WIDTH, short_strike * 0.05)
                target_strike = short_strike + target_width

                if candidates.empty:
                    return None

                candidates['distance'] = abs(candidates['strike'] - target_strike)
                best_candidate = candidates.loc[candidates['distance'].idxmin()]

            return best_candidate['strike']

        except Exception as e:
            self.logger.error("Long protection strike selection failed: %s", e)
            return None

    def _validate_iron_condor_strikes(self, long_put: float, short_put: float,
                                    short_call: float, long_call: float) -> bool:
        """Validate Iron Condor strike selection"""
        try:
            # Basic structure validation
            if not (long_put < short_put < short_call < long_call):
                return False

            # Check spread widths
            put_width = short_put - long_put
            call_width = long_call - short_call

            if put_width <= 0 or call_width <= 0:
                return False

            if max(put_width, call_width) > IC_MAX_WIDTH:
                return False

            # Check spread width balance (shouldn't be too imbalanced)
            width_ratio = max(put_width, call_width) / min(put_width, call_width)
            return width_ratio <= 2.0  # Maximum 2:1 ratio


        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("Strike validation failed: %s", e)
            return False

    # ==========================================================================
    # IRON CONDOR SPECIFIC EXECUTION INTERFACE
    # ==========================================================================

    async def create_iron_condor_position(self, setup: IronCondorSetup) -> str | None:
        """Create Iron Condor position using D26 coordinator"""
        try:
            if not self.multileg_coordinator:
                self.logger.error("MultiLegStrategyCoordinator not available")
                return None

            # Create the Iron Condor structure using D26
            structure = await self.multileg_coordinator.analyze_multileg_opportunity(
                market_data=None,  # Would need market data
                strategy_type=MultiLegStrategyType.IRON_CONDOR
            )

            if not structure:
                self.logger.warning("Could not create Iron Condor structure")
                return None

            # Execute the position through D26
            position_id = await self.multileg_coordinator.execute_multileg_strategy(structure)

            if position_id:
                self.active_setups.append(setup)
                self.strategy_state = IronCondorState.ACTIVE
                self.logger.info("✅ Iron Condor position created: %s", position_id)

            return position_id

        except Exception as e:
            self.logger.error("Iron Condor position creation failed: %s", e)
            return None

    # ==========================================================================
    # IRON CONDOR SPECIFIC MANAGEMENT
    # ==========================================================================

    def should_close_iron_condor(self, position_data: dict) -> tuple[bool, str]:
        """Iron Condor specific exit criteria"""
        try:
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            days_held = position_data.get('days_held', 0)
            dte = position_data.get('days_to_expiry', 30)

            # Profit target hit
            if current_pnl_pct >= self.profit_target:
                return True, "Profit target achieved"

            # Stop loss hit
            if current_pnl_pct <= -self.stop_loss_multiplier:
                return True, "Stop loss triggered"

            # Time-based exit (close with 7-10 DTE)
            if dte <= 7:
                return True, "Time decay exit - approaching expiration"

            # Early profit taking if very profitable
            if current_pnl_pct >= 0.75 and days_held >= 7:
                return True, "Early profit taking - 75% profit achieved"

            return False, "Hold position"

        except Exception as e:
            self.logger.error("Exit criteria analysis failed: %s", e)
            return True, "Exit due to analysis error"

    def suggest_iron_condor_adjustment(self, position_data: dict) -> IronCondorAdjustmentType | None:
        """Suggest Iron Condor specific adjustments"""
        try:
            underlying_price = position_data.get('underlying_price', 0)
            short_put_strike = position_data.get('short_put_strike', 0)
            short_call_strike = position_data.get('short_call_strike', 0)
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            dte = position_data.get('days_to_expiry', 30)

            # Only consider adjustments if losing money and have time
            if current_pnl_pct >= -0.25 or dte <= 14:
                return None

            # Determine which side is being challenged
            put_side_challenged = underlying_price < short_put_strike * 1.02
            call_side_challenged = underlying_price > short_call_strike * 0.98

            if put_side_challenged:
                return IronCondorAdjustmentType.ROLL_PUT_SIDE
            elif call_side_challenged:
                return IronCondorAdjustmentType.ROLL_CALL_SIDE
            else:
                # Both sides safe - maybe convert to butterfly for more credit
                return IronCondorAdjustmentType.CONVERT_TO_BUTTERFLY

        except Exception as e:
            self.logger.error("Adjustment analysis failed: %s", e)
            return None

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _calculate_volatility_skew(self, option_chain: pd.DataFrame) -> float:
        """Calculate volatility skew for Iron Condor analysis"""
        try:
            if option_chain is None or option_chain.empty:
                return 0.0

            puts = option_chain[option_chain['option_type'] == 'put']
            calls = option_chain[option_chain['option_type'] == 'call']

            if puts.empty or calls.empty:
                return 0.0

            # Compare IV between puts and calls at similar deltas
            put_iv = puts[abs(puts['delta'] + 0.16) < 0.02]['iv'].mean()
            call_iv = calls[abs(calls['delta'] - 0.16) < 0.02]['iv'].mean()

            if pd.isna(put_iv) or pd.isna(call_iv):
                return 0.0

            return abs(put_iv - call_iv)

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IV skew calculation failed: %s", e)
            return 0.0

    def _generate_ic_recommendation(self, iv_analysis: dict, expected_move_analysis: dict,
                                  trend_analysis: dict) -> tuple[str, float]:
        """Generate Iron Condor setup recommendation"""
        try:
            iv_score = iv_analysis.get('iv_quality_score', 0.0)
            move_score = expected_move_analysis.get('move_quality_score', 0.0)
            trend_score = trend_analysis.get('trend_quality_score', 0.0)

            overall_score = (iv_score * 0.4 + move_score * 0.3 + trend_score * 0.3)

            if overall_score >= 0.8:
                recommendation = "Excellent Iron Condor opportunity - high probability setup"
            elif overall_score >= 0.6:
                recommendation = "Good Iron Condor opportunity - favorable conditions"
            elif overall_score >= 0.4:
                recommendation = "Marginal Iron Condor opportunity - proceed with caution"
            else:
                recommendation = "Poor Iron Condor opportunity - consider other strategies"

            return recommendation, overall_score

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IC recommendation generation failed: %s", e)
            return "Analysis incomplete", 0.0

    def _identify_ic_risk_warnings(self, iv_analysis: dict, expected_move_analysis: dict,
                                 volatility_skew: float) -> list[str]:
        """Identify risk warnings for Iron Condor"""
        warnings = []

        try:
            # IV warnings
            iv_rank = iv_analysis.get('iv_rank', 50)
            if iv_rank < 30:
                warnings.append("Low IV rank - limited premium available")
            elif iv_rank > 80:
                warnings.append("Very high IV rank - potential volatility contraction")

            # Expected move warnings
            expected_move_pct = expected_move_analysis.get('expected_move_percent', 0.03)
            if expected_move_pct > 0.06:
                warnings.append("Large expected move - increased risk of strikes being breached")

            # Volatility skew warnings
            if volatility_skew > IC_VOLATILITY_SKEW_MAX:
                warnings.append("High volatility skew - uneven risk between puts and calls")

            return warnings

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning("IC risk warning identification failed: %s", e)
            return ["Risk analysis incomplete"]

    def get_strategy_performance(self) -> dict[str, Any]:
        """Get Iron Condor strategy performance metrics"""
        return {
            'strategy_name': 'Iron Condor',
            'consolidation_status': 'Infrastructure moved to D26',
            'performance_metrics': self.performance_metrics.copy(),
            'current_state': self.strategy_state.name,
            'active_setups': len(self.active_setups),
            'multileg_coordinator_connected': self.multileg_coordinator is not None,
            'last_analysis': {
                'timestamp': datetime.now().isoformat(),
                'market_suitable': self.current_analysis.market_suitable if self.current_analysis else False,
                'confidence_score': self.current_analysis.confidence_score if self.current_analysis else 0.0
            }
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_iron_condor_strategy(event_manager: EventManager = None,
                               risk_profile: RiskProfile = None,
                               config: dict[str, Any] = None) -> IronCondorStrategy:
    """Factory function to create Iron Condor strategy"""
    return IronCondorStrategy(event_manager, risk_profile, config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Test configuration
    test_config = {
        'min_iv_rank': 40,
        'profit_target': 0.25,
        'stop_loss_multiplier': 2.0,
        'min_dte': 21,
        'max_dte': 45
    }

    # Create strategy
    strategy = create_iron_condor_strategy(config=test_config)



    # Show strategy configuration


    # Show performance metrics
    performance = strategy.get_strategy_performance()


