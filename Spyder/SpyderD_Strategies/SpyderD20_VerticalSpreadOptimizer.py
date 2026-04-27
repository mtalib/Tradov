#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderD20_VerticalSpreadOptimizer.py
Group: D (Strategies)
Purpose: Optimized vertical spread strategy with dynamic strike selection
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 16:00:00

Description:
    This module implements an advanced vertical spread optimizer that dynamically
    selects optimal strikes based on probability of profit, expected value, and
    market conditions. It handles both bull put spreads and bear call spreads with
    intelligent width adjustment, early exit optimization, and risk-aware position
    sizing. The strategy adapts to volatility regimes and market structure.

Key Features:
    - Dynamic strike selection using probability analysis
    - Optimal spread width calculation
    - Expected value maximization
    - Early exit optimization
    - Volatility regime adaptation
    - Risk/reward optimization
    - Integration with Greeks analysis
    - Support for both credit and debit spreads
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from scipy import stats

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy

# Local Signal dataclass — D20 uses its own richer Signal type, not TradingSignal
from dataclasses import dataclass, field  # noqa: F811
from typing import Any as _Any  # noqa: F401


@dataclass
class Signal:
    """Lightweight signal container for VerticalSpreadOptimizer."""
    action: str = "HOLD"
    spread_type: str = ""
    contracts: int = 0
    confidence: float = 0.0
    metadata: dict = field(default_factory=dict)

try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator  # noqa: E501
    HAS_GREEKS_CALC = True
except ImportError:
    OptionsGreeksCalculator = None
    HAS_GREEKS_CALC = False

try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN06_VolatilitySurfaceBuilder import VolatilitySurfaceBuilder as VolatilityModeling  # noqa: E501
    HAS_VOL_MODELING = True
except ImportError:
    VolatilityModeling = None
    HAS_VOL_MODELING = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MIN_CREDIT = 0.30  # Minimum credit to receive
MAX_SPREAD_WIDTH = 10  # Maximum spread width in points
MIN_DAYS_TO_EXPIRY = 7  # Minimum DTE
MAX_DAYS_TO_EXPIRY = 45  # Maximum DTE

# Probability thresholds
MIN_PROBABILITY_OF_PROFIT = 0.65  # 65% minimum PoP
TARGET_PROBABILITY = 0.70  # Target 70% win rate
MAX_PROBABILITY_ITM = 0.30  # Maximum 30% chance of ITM

# Risk parameters
MAX_RISK_PER_TRADE = 0.02  # 2% max risk per trade
TARGET_PROFIT_PCT = 0.50  # Take profit at 50% of max profit
STOP_LOSS_PCT = 2.0  # Stop loss at 200% of credit received

# Greeks limits
MAX_DELTA_PER_CONTRACT = 0.20  # Max 20 delta per contract
MAX_THETA_DECAY = -50  # Maximum theta per position
MIN_THETA_REQUIREMENT = -10  # Minimum theta to enter

# Volatility adjustments
HIGH_VOL_THRESHOLD = 25  # VIX > 25 is high vol
LOW_VOL_THRESHOLD = 15  # VIX < 15 is low vol
VOL_ADJUSTMENT_FACTOR = 0.1  # 10% adjustment per 5 VIX points

# ==============================================================================
# ENUMS
# ==============================================================================
class SpreadType(Enum):
    """Types of vertical spreads"""
    BULL_PUT = "bull_put"
    BEAR_CALL = "bear_call"
    BULL_CALL_DEBIT = "bull_call_debit"
    BEAR_PUT_DEBIT = "bear_put_debit"

class MarketBias(Enum):
    """Market directional bias"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    RANGEBOUND = "rangebound"

class OptimizationMode(Enum):
    """Optimization objectives"""
    MAX_PROFIT = "max_profit"
    MAX_PROBABILITY = "max_probability"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"
    AGGRESSIVE = "aggressive"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SpreadAnalysis:
    """Analysis results for a potential spread"""
    spread_type: SpreadType
    short_strike: float
    long_strike: float
    spread_width: float
    credit: float
    max_loss: float
    probability_of_profit: float
    expected_value: float
    breakeven: float
    delta: float
    theta: float
    score: float = 0.0

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk/reward ratio"""
        if self.max_loss == 0:
            return 0
        return self.credit / self.max_loss

@dataclass
class VerticalSpreadPosition:
    """Active vertical spread position"""
    position_id: str
    spread_type: SpreadType
    entry_date: datetime
    expiration: datetime
    short_strike: float
    long_strike: float
    contracts: int
    entry_credit: float
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    target_profit: float = 0.0
    stop_loss: float = 0.0
    days_in_trade: int = 0
    management_points: list[tuple[int, float]] = field(default_factory=list)

# ==============================================================================
# MAIN STRATEGY CLASS
# ==============================================================================
class VerticalSpreadOptimizer(BaseStrategy):
    """
    Advanced vertical spread strategy with dynamic optimization.

    This strategy finds optimal vertical spreads by analyzing probability
    distributions, expected values, and market conditions.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize Vertical Spread Optimizer"""
        super().__init__(config)

        self.strategy_name = "VerticalSpreadOptimizer"
        self.version = "1.0.0"

        # Components
        self.greeks_calculator = OptionsGreeksCalculator() if HAS_GREEKS_CALC else None
        self.volatility_model = VolatilityModeling() if HAS_VOL_MODELING else None

        # Strategy settings
        self.optimization_mode = OptimizationMode(
            config.get('optimization_mode', 'balanced')
        )
        self.min_credit = config.get('min_credit', MIN_CREDIT)
        self.max_spread_width = config.get('max_spread_width', MAX_SPREAD_WIDTH)
        self.target_probability = config.get('target_probability', TARGET_PROBABILITY)

        # Position tracking
        self.active_positions: dict[str, VerticalSpreadPosition] = {}
        self.closed_positions: list[VerticalSpreadPosition] = []

        # Performance metrics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0

        # Market analysis
        self.market_bias = MarketBias.NEUTRAL
        self.current_iv_rank = 50
        self.current_iv_percentile = 50

        self.logger.info("%s initialized with mode: %s", self.strategy_name, self.optimization_mode)

    def analyze_market_conditions(self, market_data: dict[str, Any]) -> Signal:
        """
        Analyze market and generate trading signals.

        Args:
            market_data: Current market data

        Returns:
            Trading signal with spread recommendations
        """
        try:
            # Update market analysis
            self._update_market_bias(market_data)
            self._update_volatility_metrics(market_data)

            # Check if we should enter new positions
            if not self._should_enter_position(market_data):
                return Signal(action="HOLD")

            # Find optimal spreads based on market bias
            optimal_spread = self._find_optimal_spread(market_data)

            if optimal_spread and optimal_spread.score >= self._get_min_score():
                # Generate entry signal
                return self._create_entry_signal(optimal_spread, market_data)

            # Check existing positions for management
            management_signal = self._check_position_management(market_data)
            if management_signal:
                return management_signal

            return Signal(action="HOLD")

        except Exception as e:
            self.logger.error("Error analyzing market: %s", e)
            self.error_handler.handle_error(e, {"method": "analyze_market_conditions"})
            return Signal(action="HOLD")

    def _update_market_bias(self, market_data: dict[str, Any]):
        """Update market directional bias"""
        try:
            price = market_data['SPY']['last']

            # Simple trend analysis (can be enhanced)
            sma_20 = market_data.get('sma_20', price)
            sma_50 = market_data.get('sma_50', price)
            rsi = market_data.get('rsi', 50)

            # Determine bias
            if price > sma_20 and sma_20 > sma_50 and rsi > 50:
                self.market_bias = MarketBias.BULLISH
            elif price < sma_20 and sma_20 < sma_50 and rsi < 50:
                self.market_bias = MarketBias.BEARISH
            elif 45 <= rsi <= 55 and abs(price - sma_20) / price < 0.01:
                self.market_bias = MarketBias.RANGEBOUND
            else:
                self.market_bias = MarketBias.NEUTRAL

        except Exception as e:
            self.logger.warning("Could not update market bias: %s", e)
            self.market_bias = MarketBias.NEUTRAL

    def _update_volatility_metrics(self, market_data: dict[str, Any]):
        """Update IV rank and percentile"""
        try:
            if 'options_data' in market_data:
                iv_data = market_data['options_data'].get('iv_metrics', {})
                self.current_iv_rank = iv_data.get('iv_rank', 50)
                self.current_iv_percentile = iv_data.get('iv_percentile', 50)
            else:
                # Estimate from VIX if available
                vix = market_data.get('VIX', {}).get('last', 18)
                self.current_iv_rank = min(100, (vix - 10) * 3)
                self.current_iv_percentile = self.current_iv_rank

        except Exception as e:
            self.logger.warning("Could not update volatility metrics: %s", e)

    def _should_enter_position(self, market_data: dict[str, Any]) -> bool:
        """Check if conditions are suitable for new position"""
        # Check maximum positions
        if len(self.active_positions) >= self.config.get('max_positions', 5):
            return False

        # Check market hours
        current_time = datetime.now().time()
        if current_time < time(9, 45) or current_time > time(15, 30):
            return False  # Only trade during regular hours

        # Check IV conditions
        if self.current_iv_rank < 30 and self.optimization_mode != OptimizationMode.AGGRESSIVE:
            self.logger.debug("IV rank too low for credit spreads")
            return False

        # Check for high volatility events
        return not market_data.get('upcoming_events', {}).get('earnings_today', False)

    def _find_optimal_spread(self, market_data: dict[str, Any]) -> SpreadAnalysis | None:
        """
        Find the optimal vertical spread based on current conditions.

        Args:
            market_data: Current market data

        Returns:
            Optimal spread analysis or None
        """
        try:
            spot_price = market_data['SPY']['last']
            options_chain = market_data.get('options_chain', {})

            if not options_chain:
                return None

            # Determine spread type based on market bias
            spread_type = self._select_spread_type()

            # Get candidate strikes
            candidate_strikes = self._get_candidate_strikes(
                spot_price, options_chain, spread_type
            )

            # Analyze each potential spread
            spreads = []
            for short_strike, long_strike in candidate_strikes:
                analysis = self._analyze_spread(
                    short_strike, long_strike, spread_type,
                    spot_price, options_chain, market_data
                )

                if analysis and self._validate_spread(analysis):
                    spreads.append(analysis)

            # Score and rank spreads
            if spreads:
                self._score_spreads(spreads)
                return max(spreads, key=lambda x: x.score)

            return None

        except Exception as e:
            self.logger.error("Error finding optimal spread: %s", e)
            return None

    def _select_spread_type(self) -> SpreadType:
        """Select spread type based on market bias and optimization mode"""
        if self.market_bias == MarketBias.BULLISH:
            if self.optimization_mode == OptimizationMode.AGGRESSIVE:
                return SpreadType.BULL_CALL_DEBIT
            return SpreadType.BULL_PUT

        elif self.market_bias == MarketBias.BEARISH:
            if self.optimization_mode == OptimizationMode.AGGRESSIVE:
                return SpreadType.BEAR_PUT_DEBIT
            return SpreadType.BEAR_CALL

        else:  # Neutral or Rangebound
            # Sell premium in high IV
            if self.current_iv_rank > 50:
                # Choose based on slight directional bias
                return SpreadType.BULL_PUT if np.random.random() > 0.5 else SpreadType.BEAR_CALL
            else:
                # Buy spreads in low IV
                return SpreadType.BULL_CALL_DEBIT if np.random.random() > 0.5 else SpreadType.BEAR_PUT_DEBIT  # noqa: E501

    def _get_candidate_strikes(
        self,
        spot: float,
        chain: dict,
        spread_type: SpreadType
    ) -> list[tuple[float, float]]:
        """Get candidate strike pairs for analysis"""
        candidates = []

        # Get strikes from chain
        strikes = sorted(chain.get('strikes', []))
        if not strikes:
            return candidates

        # Filter strikes based on spread type
        if spread_type == SpreadType.BULL_PUT:
            # Short strike below spot, long strike below short
            short_strikes = [s for s in strikes if s < spot * 0.98]
            for short in short_strikes:
                long_strikes = [s for s in strikes if s < short]
                for long in long_strikes:
                    if 1 <= short - long <= self.max_spread_width:
                        candidates.append((short, long))

        elif spread_type == SpreadType.BEAR_CALL:
            # Short strike above spot, long strike above short
            short_strikes = [s for s in strikes if s > spot * 1.02]
            for short in short_strikes:
                long_strikes = [s for s in strikes if s > short]
                for long in long_strikes:
                    if 1 <= long - short <= self.max_spread_width:
                        candidates.append((short, long))

        # Limit candidates to top prospects
        return candidates[:20]

    def _analyze_spread(
        self,
        short_strike: float,
        long_strike: float,
        spread_type: SpreadType,
        spot: float,
        chain: dict,
        market_data: dict
    ) -> SpreadAnalysis | None:
        """Analyze a specific spread combination"""
        try:
            # Get option prices
            if spread_type in [SpreadType.BULL_PUT, SpreadType.BEAR_PUT_DEBIT]:
                short_price = chain['puts'].get(short_strike, {}).get('mid', 0)
                long_price = chain['puts'].get(long_strike, {}).get('mid', 0)
            else:
                short_price = chain['calls'].get(short_strike, {}).get('mid', 0)
                long_price = chain['calls'].get(long_strike, {}).get('mid', 0)

            if not short_price or not long_price:
                return None

            # Calculate spread metrics
            if spread_type in [SpreadType.BULL_PUT, SpreadType.BEAR_CALL]:
                # Credit spread
                credit = short_price - long_price
                max_loss = abs(short_strike - long_strike) - credit

                if credit < self.min_credit:
                    return None
            else:
                # Debit spread
                debit = long_price - short_price
                credit = -debit  # Negative for debit
                max_loss = debit

            # Calculate probability of profit
            days_to_expiry = chain.get('days_to_expiry', 30)
            volatility = market_data.get('implied_volatility', 0.20)

            pop = self._calculate_probability_of_profit(
                spot, short_strike, long_strike, spread_type,
                volatility, days_to_expiry
            )

            # Calculate expected value
            ev = self._calculate_expected_value(
                credit, max_loss, pop, spread_type
            )

            # Calculate breakeven
            if spread_type == SpreadType.BULL_PUT:
                breakeven = short_strike - credit
            elif spread_type == SpreadType.BEAR_CALL:
                breakeven = short_strike + credit
            else:
                breakeven = short_strike  # Simplified for debit spreads

            # Get Greeks
            delta = chain['puts' if 'PUT' in spread_type.value.upper() else 'calls'].get(
                short_strike, {}
            ).get('delta', 0)

            theta = chain['puts' if 'PUT' in spread_type.value.upper() else 'calls'].get(
                short_strike, {}
            ).get('theta', 0)

            return SpreadAnalysis(
                spread_type=spread_type,
                short_strike=short_strike,
                long_strike=long_strike,
                spread_width=abs(short_strike - long_strike),
                credit=credit,
                max_loss=max_loss,
                probability_of_profit=pop,
                expected_value=ev,
                breakeven=breakeven,
                delta=delta,
                theta=theta
            )

        except Exception as e:
            self.logger.error("Error analyzing spread: %s", e)
            return None

    def _calculate_probability_of_profit(
        self,
        spot: float,
        short_strike: float,
        long_strike: float,
        spread_type: SpreadType,
        volatility: float,
        days: int
    ) -> float:
        """Calculate probability of profit for the spread"""
        try:
            # Convert days to years
            time_to_expiry = days / 365.0

            # Calculate standard deviation
            std_dev = spot * volatility * np.sqrt(time_to_expiry)

            # Calculate probability based on spread type
            if spread_type == SpreadType.BULL_PUT:
                # Profitable if price stays above short strike
                z_score = (short_strike - spot) / std_dev
                pop = 1 - stats.norm.cdf(z_score)

            elif spread_type == SpreadType.BEAR_CALL:
                # Profitable if price stays below short strike
                z_score = (short_strike - spot) / std_dev
                pop = stats.norm.cdf(z_score)

            else:
                # Simplified for debit spreads
                pop = 0.5  # Can be enhanced with more sophisticated models

            return min(0.99, max(0.01, pop))

        except Exception as e:
            self.logger.error("Error calculating PoP: %s", e)
            return 0.5

    def _calculate_expected_value(
        self,
        credit: float,
        max_loss: float,
        pop: float,
        spread_type: SpreadType
    ) -> float:
        """Calculate expected value of the spread"""
        if spread_type in [SpreadType.BULL_PUT, SpreadType.BEAR_CALL]:
            # Credit spread EV
            win_amount = credit
            loss_amount = -max_loss
            ev = (pop * win_amount) + ((1 - pop) * loss_amount)
        else:
            # Debit spread EV (simplified)
            max_profit = max_loss * 2  # Assumption: 2:1 profit potential
            ev = (pop * max_profit) + ((1 - pop) * (-max_loss))

        return ev

    def _validate_spread(self, analysis: SpreadAnalysis) -> bool:
        """Validate spread meets minimum requirements"""
        # Check probability threshold
        if analysis.probability_of_profit < MIN_PROBABILITY_OF_PROFIT:
            return False

        # Check risk/reward
        if analysis.risk_reward_ratio < 0.25:  # At least 1:4 risk/reward
            return False

        # Check expected value
        if analysis.expected_value < 0:
            return False

        # Check delta limits
        if abs(analysis.delta) > MAX_DELTA_PER_CONTRACT:
            return False

        # Check theta requirement
        return analysis.theta <= MIN_THETA_REQUIREMENT  # Theta is negative

    def _score_spreads(self, spreads: list[SpreadAnalysis]):
        """Score and rank spreads based on optimization mode"""
        for spread in spreads:
            score = 0.0

            # Base scoring components
            pop_score = spread.probability_of_profit * 100
            ev_score = spread.expected_value * 10
            rr_score = spread.risk_reward_ratio * 50
            theta_score = abs(spread.theta) * 2

            # Weight based on optimization mode
            if self.optimization_mode == OptimizationMode.MAX_PROFIT:
                score = ev_score * 0.5 + rr_score * 0.3 + pop_score * 0.2

            elif self.optimization_mode == OptimizationMode.MAX_PROBABILITY:
                score = pop_score * 0.5 + ev_score * 0.3 + theta_score * 0.2

            elif self.optimization_mode == OptimizationMode.CONSERVATIVE:
                score = pop_score * 0.4 + rr_score * 0.4 + ev_score * 0.2

            elif self.optimization_mode == OptimizationMode.AGGRESSIVE:
                score = ev_score * 0.4 + rr_score * 0.4 + theta_score * 0.2

            else:  # BALANCED
                score = pop_score * 0.33 + ev_score * 0.33 + rr_score * 0.34

            # Adjust for market conditions
            if self.current_iv_rank > 70:
                score *= 1.2  # Boost in high IV
            elif self.current_iv_rank < 30:
                score *= 0.8  # Reduce in low IV

            spread.score = score

    def _get_min_score(self) -> float:
        """Get minimum score threshold based on mode"""
        thresholds = {
            OptimizationMode.CONSERVATIVE: 70,
            OptimizationMode.BALANCED: 60,
            OptimizationMode.AGGRESSIVE: 50,
            OptimizationMode.MAX_PROFIT: 55,
            OptimizationMode.MAX_PROBABILITY: 65
        }
        return thresholds.get(self.optimization_mode, 60)

    def _create_entry_signal(
        self,
        spread: SpreadAnalysis,
        market_data: dict[str, Any]
    ) -> Signal:
        """Create entry signal for optimal spread"""
        # Calculate position size
        account_value = market_data.get('account_value', 100000)
        max_risk = account_value * MAX_RISK_PER_TRADE
        contracts = int(max_risk / (spread.max_loss * 100))
        contracts = min(contracts, self.config.get('max_contracts', 10))

        # Create signal
        signal = Signal(
            action="ENTER",
            spread_type=spread.spread_type.value,
            contracts=contracts,
            confidence=spread.probability_of_profit,
            metadata={
                'short_strike': spread.short_strike,
                'long_strike': spread.long_strike,
                'credit': spread.credit,
                'max_loss': spread.max_loss,
                'probability_of_profit': spread.probability_of_profit,
                'expected_value': spread.expected_value,
                'breakeven': spread.breakeven,
                'score': spread.score,
                'target_profit': spread.credit * TARGET_PROFIT_PCT,
                'stop_loss': spread.credit * STOP_LOSS_PCT
            }
        )

        self.logger.info(
            f"Entry signal: {spread.spread_type.value} "
            f"{spread.short_strike}/{spread.long_strike} "
            f"Credit: ${spread.credit:.2f} PoP: {spread.probability_of_profit:.1%}"
        )

        return signal

    def _check_position_management(self, market_data: dict[str, Any]) -> Signal | None:
        """Check existing positions for management actions"""
        for position_id, position in self.active_positions.items():
            # Update position metrics
            self._update_position_metrics(position, market_data)

            # Check profit target
            if position.unrealized_pnl >= position.target_profit:
                return Signal(
                    action="CLOSE",
                    position_id=position_id,
                    reason="Target profit reached",
                    metadata={'pnl': position.unrealized_pnl}
                )

            # Check stop loss
            if position.unrealized_pnl <= -position.stop_loss:
                return Signal(
                    action="CLOSE",
                    position_id=position_id,
                    reason="Stop loss triggered",
                    metadata={'pnl': position.unrealized_pnl}
                )

            # Check time-based exit
            if position.days_in_trade >= 21:  # 21 days
                if position.unrealized_pnl > 0:
                    return Signal(
                        action="CLOSE",
                        position_id=position_id,
                        reason="Time-based exit",
                        metadata={'pnl': position.unrealized_pnl}
                    )

            # Check for adjustments
            adjustment = self._check_for_adjustment(position, market_data)
            if adjustment:
                return adjustment

        return None

    def _update_position_metrics(self, position: VerticalSpreadPosition, market_data: dict):
        """Update position P&L and metrics"""
        try:
            # Get current option prices
            chain = market_data.get('options_chain', {})

            if position.spread_type in [SpreadType.BULL_PUT, SpreadType.BEAR_PUT_DEBIT]:
                options = chain.get('puts', {})
            else:
                options = chain.get('calls', {})

            short_price = options.get(position.short_strike, {}).get('mid', 0)
            long_price = options.get(position.long_strike, {}).get('mid', 0)

            # Calculate current value
            current_credit = short_price - long_price

            # Calculate P&L
            if position.spread_type in [SpreadType.BULL_PUT, SpreadType.BEAR_CALL]:
                # Credit spread: profit when spread value decreases
                position.unrealized_pnl = (position.entry_credit - current_credit) * 100 * position.contracts  # noqa: E501
            else:
                # Debit spread: profit when spread value increases
                position.unrealized_pnl = (current_credit + position.entry_credit) * 100 * position.contracts  # noqa: E501

            position.current_value = current_credit
            position.days_in_trade = (datetime.now() - position.entry_date).days

        except Exception as e:
            self.logger.error("Error updating position metrics: %s", e)

    def _check_for_adjustment(
        self,
        position: VerticalSpreadPosition,
        market_data: dict
    ) -> Signal | None:
        """Check if position needs adjustment"""
        spot = market_data['SPY']['last']

        # Check if short strike is threatened
        if position.spread_type == SpreadType.BULL_PUT:
            if spot < position.short_strike * 1.02:  # Within 2% of short strike
                return Signal(
                    action="ADJUST",
                    position_id=position.position_id,
                    adjustment_type="roll_down",
                    metadata={'current_spot': spot, 'short_strike': position.short_strike}
                )

        elif position.spread_type == SpreadType.BEAR_CALL:
            if spot > position.short_strike * 0.98:  # Within 2% of short strike
                return Signal(
                    action="ADJUST",
                    position_id=position.position_id,
                    adjustment_type="roll_up",
                    metadata={'current_spot': spot, 'short_strike': position.short_strike}
                )

        return None

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get strategy performance statistics"""
        win_rate = self.winning_trades / max(1, self.total_trades)

        return {
            'strategy': self.strategy_name,
            'optimization_mode': self.optimization_mode.value,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_pnl,
            'max_drawdown': self.max_drawdown,
            'active_positions': len(self.active_positions),
            'market_bias': self.market_bias.value,
            'current_iv_rank': self.current_iv_rank
        }

    # ------------------------------------------------------------------
    # BaseStrategy abstract contract
    # ------------------------------------------------------------------
    def generate_signals(self, market_data) -> list:
        """Bridge BaseStrategy.generate_signals to analyze_market_conditions."""
        import pandas as pd
        from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import TradingSignal
        from uuid import uuid4
        if isinstance(market_data, pd.DataFrame):
            data_dict = market_data.to_dict('list') if not market_data.empty else {}
        else:
            data_dict = market_data if isinstance(market_data, dict) else {}
        sig = self.analyze_market_conditions(data_dict)
        if sig and getattr(sig, 'action', 'HOLD') != 'HOLD':
            ts = TradingSignal(
                signal_id=str(uuid4()),
                symbol=self.config.get('symbol', 'SPY'),
                action=sig.action,
                quantity=sig.contracts or 1,
                entry_price=0.0,
                strategy_id='VerticalSpreadOptimizer',
            )
            return [ts]
        return []

    def validate_signal(self, signal, account_value: float = 0) -> bool:
        """Validate a generated signal meets minimum requirements."""
        return bool(signal and getattr(signal, 'symbol', None) and getattr(signal, 'quantity', 0) > 0)  # noqa: E501

    def calculate_position_size(self, signal, account_value: float) -> int:
        """Return contract count scaled by account value and per-trade risk budget."""
        risk_budget = account_value * self.config.get('max_risk_per_trade', 0.02)
        premium_per_contract = getattr(signal, 'entry_price', 1.0) * 100 or 100
        return max(1, int(risk_budget / premium_per_contract))

    def should_exit_position(self, position: dict, current_data: dict) -> bool:
        """Return True when the position should be closed based on P&L thresholds."""
        pnl_pct = current_data.get('pnl_pct', 0.0)
        stop_loss = self.config.get('stop_loss_pct', -1.0)
        profit_target = self.config.get('profit_target_pct', 0.50)
        return pnl_pct <= stop_loss or pnl_pct >= profit_target


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_vertical_spread_optimizer(config: dict[str, Any] | None = None) -> VerticalSpreadOptimizer:  # noqa: E501
    """Factory function to create VerticalSpreadOptimizer instance"""
    return VerticalSpreadOptimizer(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'optimization_mode': 'balanced',
        'min_credit': 0.30,
        'max_spread_width': 5,
        'target_probability': 0.70,
        'max_positions': 3,
        'max_contracts': 10
    }

    # Create strategy
    strategy = create_vertical_spread_optimizer(test_config)

    # Test market data
    test_market_data = {
        'SPY': {'last': 450.00},
        'VIX': {'last': 18.5},
        'sma_20': 448.50,
        'sma_50': 445.00,
        'rsi': 55,
        'options_chain': {
            'days_to_expiry': 30,
            'strikes': [440, 441, 442, 443, 444, 445, 446, 447, 448, 449, 450, 451, 452],
            'puts': {
                445: {'mid': 2.50, 'delta': -0.20, 'theta': -0.15},
                440: {'mid': 1.50, 'delta': -0.12, 'theta': -0.10}
            },
            'calls': {
                455: {'mid': 2.00, 'delta': 0.18, 'theta': -0.12},
                460: {'mid': 1.00, 'delta': 0.10, 'theta': -0.08}
            }
        },
        'implied_volatility': 0.18,
        'account_value': 100000
    }

    # Test signal generation

    signal = strategy.analyze_market_conditions(test_market_data)

    if signal.metadata:
        for key, value in signal.metadata.items():
            if isinstance(value, float):
                if 'probability' in key or 'pop' in key.lower() or key in ['credit', 'max_loss', 'expected_value', 'target_profit']:  # noqa: E501
                    pass
                else:
                    pass
            else:
                pass

    # Get stats
    stats = strategy.get_strategy_stats()
    for _, _ in stats.items():
        pass
