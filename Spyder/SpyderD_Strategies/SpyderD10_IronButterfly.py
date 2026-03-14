#!/usr/bin/env python3
from __future__ import annotations
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD10_IronButterfly.py
Purpose: Iron Butterfly strategy with consolidated multi-leg infrastructure (Updated)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 17:00:00

Module Description:
    Iron Butterfly strategy implementation focused on strategy-specific entry/exit logic
    and ATM-centered market analysis. Generic multi-leg construction, order management,
    and Greeks calculations have been moved to SpyderD32_MultiLegStrategyCoordinator for
    consolidation and code reuse across all multi-leg strategies.

CONSOLIDATION UPDATE:
    Generic multi-leg infrastructure REMOVED and consolidated into D26_MultiLegStrategyCoordinator.
    This module now focuses exclusively on Iron Butterfly specific trading logic:
    - Iron Butterfly entry criteria and neutral market outlook analysis
    - ATM strike selection methodology specific to Iron Butterfly
    - Profit targets and stop loss rules for Iron Butterfly
    - Adjustment techniques specific to Iron Butterfly strategy
    - Exit criteria and time decay management for Iron Butterfly

Key Features:
    • Iron Butterfly specific entry conditions (neutral outlook, high IV near ATM)
    • ATM strike selection with equidistant wing placement
    • Profit targets at 25% of maximum profit potential
    • Stop loss at delta breach or 75% of max profit
    • Time decay optimization (close at 10-15 DTE)
    • Iron Butterfly specific adjustment techniques
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
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

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
# Iron Butterfly specific parameters
IB_MIN_IV_RANK = 30                    # Minimum IV rank for IB entry
IB_OPTIMAL_IV_RANK = 50                # Optimal IV rank for IB
IB_MAX_IV_RANK = 75                    # Maximum IV rank

IB_ATM_TOLERANCE = 0.50                # ATM strike tolerance ($0.50)
IB_WING_WIDTH_MIN = 5.0                # Minimum wing width
IB_WING_WIDTH_MAX = 15.0               # Maximum wing width
IB_OPTIMAL_WING_WIDTH = 10.0           # Optimal wing width

IB_MIN_DTE = 10                        # Minimum days to expiration
IB_MAX_DTE = 35                        # Maximum days to expiration
IB_OPTIMAL_DTE = 25                    # Optimal days to expiration

IB_PROFIT_TARGET = 0.25                # 25% of max profit
IB_STOP_LOSS = 0.75                    # 75% of max profit (or delta breach)
IB_EARLY_CLOSE_PROFIT = 0.15           # Close early at 15%

IB_MIN_CREDIT = 0.50                   # Minimum credit per contract
IB_MAX_DELTA_THRESHOLD = 0.05          # Maximum delta at entry

# Market condition thresholds for Iron Butterfly
IB_MAX_EXPECTED_MOVE_RATIO = 0.8       # Max expected move vs wing width
IB_NEUTRAL_OUTLOOK_THRESHOLD = 0.02    # Maximum trend strength for neutral
IB_MIN_TIME_DECAY_RATE = 0.02          # Minimum theta decay rate

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class IronButterflyState(Enum):
    """Iron Butterfly position states"""
    ANALYZING = auto()
    READY_TO_ENTER = auto()
    ENTERING = auto()
    ACTIVE = auto()
    MONITORING = auto()
    PROFIT_TARGET_HIT = auto()
    STOP_LOSS_HIT = auto()
    DELTA_BREACH = auto()
    ADJUSTING = auto()
    CLOSING = auto()
    CLOSED = auto()
    ERROR = auto()

class IronButterflyAdjustmentType(Enum):
    """Types of Iron Butterfly adjustments"""
    CONVERT_TO_CONDOR = "convert_to_condor"
    ROLL_ATM_STRIKES = "roll_atm_strikes"
    ADJUST_WINGS = "adjust_wings"
    CLOSE_PROFITABLE_SIDE = "close_profitable_side"
    DELTA_HEDGE = "delta_hedge"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class IronButterflySetup:
    """Iron Butterfly strategy setup parameters"""
    underlying_price: float
    atm_strike: float  # Center strike for both put and call
    long_put_strike: float
    long_call_strike: float
    expiration_date: datetime
    days_to_expiry: int
    wing_width: float
    expected_credit: float
    max_profit: float
    max_loss: float
    breakeven_lower: float
    breakeven_upper: float
    probability_of_profit: float
    iv_rank: float
    time_decay_rate: float
    setup_quality_score: float

@dataclass
class IronButterflyAnalysis:
    """Iron Butterfly market analysis results"""
    market_suitable: bool
    neutral_outlook_confirmed: bool
    atm_analysis: dict[str, float]
    iv_analysis: dict[str, float]
    time_decay_analysis: dict[str, float]
    expected_move_analysis: dict[str, float]
    optimal_wing_width: float | None
    atm_strike_recommendation: float | None
    setup_recommendation: str
    confidence_score: float
    risk_warnings: list[str]

# ==============================================================================
# MAIN IRON BUTTERFLY STRATEGY CLASS
# ==============================================================================
class IronButterflyStrategy(BaseStrategy):
    """
    Iron Butterfly Strategy with consolidated multi-leg infrastructure.

    Focuses exclusively on Iron Butterfly specific trading logic while leveraging
    the consolidated multi-leg coordinator (D26) for infrastructure operations.

    This implementation handles:
    - Iron Butterfly specific entry criteria (neutral outlook)
    - ATM strike selection and wing placement
    - Profit targets and risk management
    - Strategy-specific adjustments
    - Exit criteria and time decay optimization
    """

    def __init__(self, event_manager: EventManager = None,
                 risk_profile: RiskProfile = None, config: dict[str, Any] = None):
        """Initialize Iron Butterfly strategy"""

        # Initialize base strategy
        super().__init__(
            name="Iron Butterfly Strategy",
            strategy_type="iron_butterfly",
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
                self.logger.info("Connected to MultiLegStrategyCoordinator")
            except Exception as e:
                self.logger.error(f"Failed to connect to coordinator: {e}")
        else:
            self.logger.warning("MultiLegStrategyCoordinator not available")

        # Iron Butterfly specific configuration
        self.min_iv_rank = self.config.get('min_iv_rank', IB_MIN_IV_RANK)
        self.profit_target = self.config.get('profit_target', IB_PROFIT_TARGET)
        self.stop_loss = self.config.get('stop_loss', IB_STOP_LOSS)
        self.min_dte = self.config.get('min_dte', IB_MIN_DTE)
        self.max_dte = self.config.get('max_dte', IB_MAX_DTE)
        self.wing_width = self.config.get('wing_width', IB_OPTIMAL_WING_WIDTH)
        self.atm_tolerance = self.config.get('atm_tolerance', IB_ATM_TOLERANCE)

        # Strategy state
        self.current_analysis: IronButterflyAnalysis | None = None
        self.active_setups: list[IronButterflySetup] = []
        self.strategy_state = IronButterflyState.ANALYZING

        # Performance tracking
        self.performance_metrics = {
            'total_ib_trades': 0,
            'winning_ib_trades': 0,
            'total_ib_profit': 0.0,
            'avg_ib_hold_days': 0.0,
            'ib_win_rate': 0.0,
            'avg_credit_captured': 0.0,
            'max_consecutive_losses': 0,
            'best_ib_trade': 0.0,
            'worst_ib_trade': 0.0,
            'avg_time_to_profit': 0.0
        }

        self.logger.info("Iron Butterfly Strategy initialized with D26 integration")

    # ==========================================================================
    # IRON BUTTERFLY SPECIFIC MARKET ANALYSIS
    # ==========================================================================

    async def analyze_iron_butterfly_opportunity(self, market_data: pd.DataFrame,
                                               option_chain: pd.DataFrame = None) -> IronButterflyAnalysis:
        """
        Analyze market conditions for Iron Butterfly entry.

        This is Iron Butterfly specific analysis - generic analysis is in D26.
        """
        try:
            current_price = market_data['close'].iloc[-1]

            # Neutral outlook analysis (critical for Iron Butterfly)
            neutral_outlook_confirmed = self._confirm_neutral_market_outlook(market_data)

            # ATM analysis (Iron Butterfly centers on ATM)
            atm_analysis = self._analyze_atm_conditions(market_data, current_price)

            # IV Analysis (Iron Butterfly specific requirements)
            iv_analysis = self._analyze_iv_for_iron_butterfly(market_data)

            # Time decay analysis (critical for Iron Butterfly profitability)
            time_decay_analysis = self._analyze_time_decay_potential(market_data)

            # Expected move analysis (must be smaller than wing width)
            expected_move_analysis = self._analyze_expected_move_for_ib(market_data, current_price)

            # Overall suitability
            market_suitable = self._assess_market_suitability_for_ib(
                neutral_outlook_confirmed, iv_analysis, expected_move_analysis, time_decay_analysis
            )

            # Find optimal setup if suitable
            optimal_wing_width = None
            atm_strike_recommendation = None
            setup_recommendation = ""
            confidence_score = 0.0
            risk_warnings = []

            if market_suitable and option_chain is not None:
                optimal_wing_width = self._find_optimal_wing_width(
                    current_price, option_chain, expected_move_analysis
                )
                atm_strike_recommendation = self._find_optimal_atm_strike(
                    current_price, option_chain
                )
                setup_recommendation, confidence_score = self._generate_ib_recommendation(
                    iv_analysis, expected_move_analysis, time_decay_analysis
                )
                risk_warnings = self._identify_ib_risk_warnings(
                    neutral_outlook_confirmed, iv_analysis, expected_move_analysis
                )

            analysis = IronButterflyAnalysis(
                market_suitable=market_suitable,
                neutral_outlook_confirmed=neutral_outlook_confirmed,
                atm_analysis=atm_analysis,
                iv_analysis=iv_analysis,
                time_decay_analysis=time_decay_analysis,
                expected_move_analysis=expected_move_analysis,
                optimal_wing_width=optimal_wing_width,
                atm_strike_recommendation=atm_strike_recommendation,
                setup_recommendation=setup_recommendation,
                confidence_score=confidence_score,
                risk_warnings=risk_warnings
            )

            self.current_analysis = analysis
            return analysis

        except Exception as e:
            self.logger.error(f"Iron Butterfly analysis failed: {e}")
            self.error_handler.handle_error(e, {"method": "analyze_iron_butterfly_opportunity"})

            return IronButterflyAnalysis(
                market_suitable=False,
                neutral_outlook_confirmed=False,
                atm_analysis={},
                iv_analysis={},
                time_decay_analysis={},
                expected_move_analysis={},
                optimal_wing_width=None,
                atm_strike_recommendation=None,
                setup_recommendation="Analysis failed",
                confidence_score=0.0,
                risk_warnings=["Analysis error occurred"]
            )

    def _confirm_neutral_market_outlook(self, market_data: pd.DataFrame) -> bool:
        """Confirm neutral market outlook (essential for Iron Butterfly)"""
        try:
            # Analyze trend strength over multiple timeframes
            closes = market_data['close']

            # Short-term trend (5 days)
            short_term_change = (closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6]

            # Medium-term trend (10 days)
            medium_term_change = (closes.iloc[-1] - closes.iloc[-11]) / closes.iloc[-11]

            # Range analysis (20 days)
            high_20 = market_data['high'].tail(20).max()
            low_20 = market_data['low'].tail(20).min()
            current_position = (closes.iloc[-1] - low_20) / (high_20 - low_20)

            # Volatility of returns
            returns = closes.pct_change().dropna().tail(10)
            return_volatility = returns.std()

            # Neutral outlook criteria
            trend_neutral = (
                abs(short_term_change) < IB_NEUTRAL_OUTLOOK_THRESHOLD and
                abs(medium_term_change) < IB_NEUTRAL_OUTLOOK_THRESHOLD * 1.5
            )

            position_centered = 0.3 <= current_position <= 0.7  # Not at extremes
            volatility_stable = return_volatility < 0.02  # Low return volatility

            return trend_neutral and position_centered and volatility_stable

        except Exception as e:
            self.logger.error(f"Neutral outlook analysis failed: {e}")
            return False

    def _analyze_atm_conditions(self, market_data: pd.DataFrame, current_price: float) -> dict[str, float]:
        """Analyze ATM conditions for Iron Butterfly"""
        try:
            # Price stability around current level
            closes = market_data['close'].tail(10)
            price_stability = closes.std() / closes.mean()

            # ATM attractiveness score
            atm_score = max(0.0, 1.0 - price_stability * 10)  # Penalize instability

            return {
                'current_price': current_price,
                'price_stability': price_stability,
                'atm_attractiveness_score': atm_score,
                'suitable_for_atm_strategy': price_stability < 0.01  # Less than 1% daily std
            }

        except Exception as e:
            self.logger.error(f"ATM analysis failed: {e}")
            return {
                'current_price': current_price,
                'price_stability': 0.02,
                'atm_attractiveness_score': 0.5,
                'suitable_for_atm_strategy': False
            }

    def _analyze_iv_for_iron_butterfly(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze implied volatility specifically for Iron Butterfly strategy"""
        try:
            # Get IV data
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]

            # Calculate IV rank
            iv_history = market_data.get('iv', pd.Series([0.20] * 100)).tail(252)
            iv_rank = (current_iv > iv_history).sum() / len(iv_history) * 100

            # Iron Butterfly IV analysis (different from Iron Condor)
            iv_analysis = {
                'current_iv': current_iv,
                'iv_rank': iv_rank,
                'iv_suitable_for_ib': IB_MIN_IV_RANK <= iv_rank <= IB_MAX_IV_RANK,
                'iv_quality_score': self._calculate_ib_iv_quality_score(current_iv, iv_rank),
                'iv_trend': 'rising' if current_iv > iv_history.mean() else 'falling',
                'time_decay_potential': current_iv * 0.1  # Simplified theta estimate
            }

            return iv_analysis

        except Exception as e:
            self.logger.error(f"IB IV analysis failed: {e}")
            return {
                'current_iv': 0.20,
                'iv_rank': 40.0,
                'iv_suitable_for_ib': False,
                'iv_quality_score': 0.0,
                'iv_trend': 'unknown',
                'time_decay_potential': 0.02
            }

    def _calculate_ib_iv_quality_score(self, current_iv: float, iv_rank: float) -> float:
        """Calculate IV quality score for Iron Butterfly (0.0 to 1.0)"""
        try:
            # Optimal IV rank for Iron Butterfly is around 40-60 (lower than IC)
            if iv_rank < IB_MIN_IV_RANK:
                iv_rank_score = 0.0
            elif iv_rank > IB_MAX_IV_RANK:
                iv_rank_score = 0.3  # Still possible but not ideal
            else:
                # Score peaks around 50
                iv_rank_score = 1.0 - abs(iv_rank - IB_OPTIMAL_IV_RANK) / IB_OPTIMAL_IV_RANK

            # Prefer moderate IV levels for Iron Butterfly
            if current_iv < 0.15:
                iv_level_score = 0.0
            elif current_iv > 0.35:
                iv_level_score = 0.5
            else:
                iv_level_score = min(1.0, current_iv / 0.25)

            return (iv_rank_score * 0.7 + iv_level_score * 0.3)

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Iron Butterfly calculation failed: {e}")
            return 0.0

    def _analyze_time_decay_potential(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Analyze time decay potential for Iron Butterfly"""
        try:
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]

            # Estimate theta decay rate
            estimated_theta = current_iv * 0.1  # Simplified calculation

            # Days to optimal close
            optimal_close_days = 15  # Iron Butterfly typically closed around 15 DTE

            # Total expected time decay
            expected_time_decay = estimated_theta * optimal_close_days

            analysis = {
                'estimated_daily_theta': estimated_theta,
                'optimal_close_dte': optimal_close_days,
                'expected_total_decay': expected_time_decay,
                'decay_rate_suitable': estimated_theta >= IB_MIN_TIME_DECAY_RATE,
                'time_decay_quality_score': min(1.0, estimated_theta / 0.05)
            }

            return analysis

        except Exception as e:
            self.logger.error(f"Time decay analysis failed: {e}")
            return {
                'estimated_daily_theta': 0.02,
                'optimal_close_dte': 15,
                'expected_total_decay': 0.30,
                'decay_rate_suitable': True,
                'time_decay_quality_score': 0.4
            }

    def _analyze_expected_move_for_ib(self, market_data: pd.DataFrame,
                                    current_price: float) -> dict[str, float]:
        """Analyze expected move for Iron Butterfly (must be smaller than wings)"""
        try:
            current_iv = market_data.get('iv', pd.Series([0.20])).iloc[-1]
            days_to_expiry = 25  # Default assumption

            # Expected move calculation
            expected_move = current_price * current_iv * np.sqrt(days_to_expiry / 365)
            expected_move_pct = expected_move / current_price

            # Iron Butterfly specific analysis - move should be small
            wing_width = self.wing_width
            expected_move_vs_wings = expected_move / wing_width

            analysis = {
                'expected_move_dollars': expected_move,
                'expected_move_percent': expected_move_pct,
                'expected_move_vs_wing_width': expected_move_vs_wings,
                'expected_move_suitable_for_ib': expected_move_vs_wings <= IB_MAX_EXPECTED_MOVE_RATIO,
                'move_quality_score': self._calculate_ib_move_quality_score(expected_move_vs_wings)
            }

            return analysis

        except Exception as e:
            self.logger.error(f"Expected move analysis failed: {e}")
            return {
                'expected_move_dollars': 8.0,
                'expected_move_percent': 0.02,
                'expected_move_vs_wing_width': 0.8,
                'expected_move_suitable_for_ib': True,
                'move_quality_score': 0.6
            }

    def _calculate_ib_move_quality_score(self, move_vs_wings: float) -> float:
        """Calculate expected move quality for Iron Butterfly"""
        try:
            # Optimal move is about 60% of wing width
            optimal_ratio = 0.6

            if move_vs_wings <= IB_MAX_EXPECTED_MOVE_RATIO:
                deviation = abs(move_vs_wings - optimal_ratio)
                return max(0.0, 1.0 - deviation / 0.3)
            else:
                # Move too large for Iron Butterfly
                return 0.0

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Iron Butterfly calculation failed: {e}")
            return 0.0

    def _assess_market_suitability_for_ib(self, neutral_outlook: bool, iv_analysis: dict,
                                        expected_move_analysis: dict, time_decay_analysis: dict) -> bool:
        """Assess overall market suitability for Iron Butterfly"""
        try:
            # All conditions must be met for Iron Butterfly
            outlook_suitable = neutral_outlook
            iv_suitable = iv_analysis.get('iv_suitable_for_ib', False)
            move_suitable = expected_move_analysis.get('expected_move_suitable_for_ib', False)
            decay_suitable = time_decay_analysis.get('decay_rate_suitable', False)

            return outlook_suitable and iv_suitable and move_suitable and decay_suitable

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Iron Butterfly validation failed: {e}")
            return False

    # ==========================================================================
    # IRON BUTTERFLY SPECIFIC STRIKE SELECTION
    # ==========================================================================

    def _find_optimal_atm_strike(self, current_price: float,
                               option_chain: pd.DataFrame) -> float | None:
        """Find optimal ATM strike for Iron Butterfly center"""
        try:
            if option_chain is None or option_chain.empty:
                return None

            # Get available strikes
            available_strikes = sorted(option_chain['strike'].unique())

            # Find closest strike to current price
            closest_strike = min(available_strikes, key=lambda x: abs(x - current_price))

            # Ensure it's within ATM tolerance
            if abs(closest_strike - current_price) <= self.atm_tolerance:
                return closest_strike
            else:
                return None

        except Exception as e:
            self.logger.error(f"ATM strike selection failed: {e}")
            return None

    def _find_optimal_wing_width(self, current_price: float, option_chain: pd.DataFrame,
                               expected_move_analysis: dict) -> float | None:
        """Find optimal wing width for Iron Butterfly"""
        try:
            expected_move = expected_move_analysis.get('expected_move_dollars', 10.0)

            # Wing width should be wider than expected move
            min_width = max(IB_WING_WIDTH_MIN, expected_move * 1.2)
            max_width = min(IB_WING_WIDTH_MAX, current_price * 0.05)  # 5% of underlying

            # Choose optimal width
            optimal_width = min(max_width, max(min_width, IB_OPTIMAL_WING_WIDTH))

            # Validate against available strikes
            atm_strike = self._find_optimal_atm_strike(current_price, option_chain)
            if not atm_strike:
                return None

            # Check if wing strikes exist
            available_strikes = sorted(option_chain['strike'].unique())
            upper_wing = atm_strike + optimal_width
            lower_wing = atm_strike - optimal_width

            # Find closest available strikes
            upper_available = min(available_strikes, key=lambda x: abs(x - upper_wing))
            lower_available = min(available_strikes, key=lambda x: abs(x - lower_wing))

            # Calculate actual wing width
            actual_upper_width = abs(upper_available - atm_strike)
            actual_lower_width = abs(atm_strike - lower_available)

            # Use symmetric width (average of both sides)
            actual_wing_width = (actual_upper_width + actual_lower_width) / 2

            return actual_wing_width if IB_WING_WIDTH_MIN <= actual_wing_width <= IB_WING_WIDTH_MAX else None

        except Exception as e:
            self.logger.error(f"Wing width selection failed: {e}")
            return None

    # ==========================================================================
    # IRON BUTTERFLY SPECIFIC EXECUTION INTERFACE
    # ==========================================================================

    async def create_iron_butterfly_position(self, setup: IronButterflySetup) -> str | None:
        """Create Iron Butterfly position using D26 coordinator"""
        try:
            if not self.multileg_coordinator:
                self.logger.error("MultiLegStrategyCoordinator not available")
                return None

            # Create the Iron Butterfly structure using D26
            structure = await self.multileg_coordinator.analyze_multileg_opportunity(
                market_data=None,  # Would need market data
                strategy_type=MultiLegStrategyType.IRON_BUTTERFLY
            )

            if not structure:
                self.logger.warning("Could not create Iron Butterfly structure")
                return None

            # Execute the position through D26
            position_id = await self.multileg_coordinator.execute_multileg_strategy(structure)

            if position_id:
                self.active_setups.append(setup)
                self.strategy_state = IronButterflyState.ACTIVE
                self.logger.info(f"Iron Butterfly position created: {position_id}")

            return position_id

        except Exception as e:
            self.logger.error(f"Iron Butterfly position creation failed: {e}")
            return None

    # ==========================================================================
    # IRON BUTTERFLY SPECIFIC MANAGEMENT
    # ==========================================================================

    def should_close_iron_butterfly(self, position_data: dict) -> tuple[bool, str]:
        """Iron Butterfly specific exit criteria"""
        try:
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            days_held = position_data.get('days_held', 0)
            dte = position_data.get('days_to_expiry', 25)
            position_delta = position_data.get('position_delta', 0.0)

            # Profit target hit (25% of max profit)
            if current_pnl_pct >= self.profit_target:
                return True, "Profit target achieved"

            # Stop loss hit (75% of max profit loss)
            if current_pnl_pct <= -self.stop_loss:
                return True, "Stop loss triggered"

            # Delta breach (position no longer neutral)
            if abs(position_delta) > IB_MAX_DELTA_THRESHOLD:
                return True, "Delta breach - position no longer neutral"

            # Time-based exit (close with 10-15 DTE for Iron Butterfly)
            if dte <= 10:
                return True, "Time decay exit - approaching expiration"

            # Early profit taking if very profitable quickly
            if current_pnl_pct >= IB_EARLY_CLOSE_PROFIT and days_held >= 3:
                return True, "Early profit taking - 15% profit achieved"

            return False, "Hold position"

        except Exception as e:
            self.logger.error(f"Exit criteria analysis failed: {e}")
            return True, "Exit due to analysis error"

    def suggest_iron_butterfly_adjustment(self, position_data: dict) -> IronButterflyAdjustmentType | None:
        """Suggest Iron Butterfly specific adjustments"""
        try:
            underlying_price = position_data.get('underlying_price', 0)
            atm_strike = position_data.get('atm_strike', 0)
            current_pnl_pct = position_data.get('pnl_percent', 0.0)
            dte = position_data.get('days_to_expiry', 25)
            position_delta = position_data.get('position_delta', 0.0)

            # Only consider adjustments if losing money and have time
            if current_pnl_pct >= -0.20 or dte <= 14:
                return None

            # Price moved away from ATM significantly
            price_move_pct = abs(underlying_price - atm_strike) / atm_strike

            if price_move_pct > 0.03:  # 3% move from ATM
                # Convert to Iron Condor for better risk management
                return IronButterflyAdjustmentType.CONVERT_TO_CONDOR

            # Delta imbalance
            if abs(position_delta) > IB_MAX_DELTA_THRESHOLD:
                return IronButterflyAdjustmentType.DELTA_HEDGE

            # If still near ATM but losing, consider rolling strikes
            if price_move_pct < 0.02:
                return IronButterflyAdjustmentType.ROLL_ATM_STRIKES

            return None

        except Exception as e:
            self.logger.error(f"Adjustment analysis failed: {e}")
            return None

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _generate_ib_recommendation(self, iv_analysis: dict, expected_move_analysis: dict,
                                  time_decay_analysis: dict) -> tuple[str, float]:
        """Generate Iron Butterfly setup recommendation"""
        try:
            iv_score = iv_analysis.get('iv_quality_score', 0.0)
            move_score = expected_move_analysis.get('move_quality_score', 0.0)
            decay_score = time_decay_analysis.get('time_decay_quality_score', 0.0)

            # Weight time decay heavily for Iron Butterfly
            overall_score = (iv_score * 0.3 + move_score * 0.3 + decay_score * 0.4)

            if overall_score >= 0.8:
                recommendation = "Excellent Iron Butterfly opportunity - optimal neutral conditions"
            elif overall_score >= 0.6:
                recommendation = "Good Iron Butterfly opportunity - favorable time decay environment"
            elif overall_score >= 0.4:
                recommendation = "Marginal Iron Butterfly opportunity - monitor closely"
            else:
                recommendation = "Poor Iron Butterfly opportunity - consider Iron Condor instead"

            return recommendation, overall_score

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Iron Butterfly recommendation failed: {e}")
            return "Analysis incomplete", 0.0

    def _identify_ib_risk_warnings(self, neutral_outlook: bool, iv_analysis: dict,
                                 expected_move_analysis: dict) -> list[str]:
        """Identify risk warnings for Iron Butterfly"""
        warnings = []

        try:
            # Neutral outlook warnings
            if not neutral_outlook:
                warnings.append("Market showing directional bias - Iron Butterfly may not be optimal")

            # IV warnings
            iv_rank = iv_analysis.get('iv_rank', 50)
            if iv_rank < 25:
                warnings.append("Low IV rank - limited time decay potential")
            elif iv_rank > 70:
                warnings.append("High IV rank - consider Iron Condor for better risk management")

            # Expected move warnings
            move_vs_wings = expected_move_analysis.get('expected_move_vs_wing_width', 0.5)
            if move_vs_wings > 0.8:
                warnings.append("Expected move approaching wing width - higher risk of loss")

            return warnings

        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            self.logger.warning(f"Iron Butterfly risk analysis failed: {e}")
            return ["Risk analysis incomplete"]

    def get_strategy_performance(self) -> dict[str, Any]:
        """Get Iron Butterfly strategy performance metrics"""
        return {
            'strategy_name': 'Iron Butterfly',
            'consolidation_status': 'Infrastructure moved to D26',
            'performance_metrics': self.performance_metrics.copy(),
            'current_state': self.strategy_state.name,
            'active_setups': len(self.active_setups),
            'multileg_coordinator_connected': self.multileg_coordinator is not None,
            'last_analysis': {
                'timestamp': datetime.now().isoformat(),
                'market_suitable': self.current_analysis.market_suitable if self.current_analysis else False,
                'neutral_outlook': self.current_analysis.neutral_outlook_confirmed if self.current_analysis else False,
                'confidence_score': self.current_analysis.confidence_score if self.current_analysis else 0.0
            }
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_iron_butterfly_strategy(event_manager: EventManager = None,
                                  risk_profile: RiskProfile = None,
                                  config: dict[str, Any] = None) -> IronButterflyStrategy:
    """Factory function to create Iron Butterfly strategy"""
    return IronButterflyStrategy(event_manager, risk_profile, config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Test configuration
    test_config = {
        'min_iv_rank': 30,
        'profit_target': 0.25,
        'stop_loss': 0.75,
        'min_dte': 10,
        'max_dte': 35,
        'wing_width': 10.0,
        'atm_tolerance': 0.50
    }

    # Create strategy
    strategy = create_iron_butterfly_strategy(config=test_config)



    # Show strategy configuration


    # Show performance metrics
    performance = strategy.get_strategy_performance()


