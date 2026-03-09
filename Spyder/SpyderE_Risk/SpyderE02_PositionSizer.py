#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE02_PositionSizer.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import stats

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.warning(f"Error in {context}: {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Position Sizing Methods
KELLY_REDUCTION_FACTOR = 0.375      # 37.5% of full Kelly (institutional standard)
MIN_KELLY_REDUCTION = 0.25          # Minimum 25% of Kelly
MAX_KELLY_REDUCTION = 0.50          # Maximum 50% of Kelly

# Risk Parameters
DEFAULT_RISK_PER_TRADE = 0.02       # 2% risk per trade
MIN_POSITION_SIZE = 0.001           # 0.1% minimum
MAX_POSITION_SIZE = 0.05            # 5% maximum
DEFAULT_CONFIDENCE_LEVEL = 0.95     # 95% confidence for calculations

# Volatility Parameters
ATR_MULTIPLIER = 2.0               # ATR multiplier for stops
VOLATILITY_LOOKBACK = 14           # Days for volatility calculation
HIGH_VOL_THRESHOLD = 30            # VIX > 30 is high volatility
LOW_VOL_THRESHOLD = 15             # VIX < 15 is low volatility

# Market Regime Adjustments
REGIME_MULTIPLIERS = {
    'bull': 1.2,
    'bear': 0.8,
    'neutral': 1.0,
    'high_volatility': 0.6,
    'low_volatility': 1.1
}

# Day of Week Adjustments (from research)
DAY_OF_WEEK_MULTIPLIERS = {
    0: 1.0,   # Monday - normal
    1: 1.0,   # Tuesday - normal
    2: 0.9,   # Wednesday - slightly reduced
    3: 0.9,   # Thursday - slightly reduced
    4: 0.8    # Friday - reduced
}

# Strategy Performance Requirements
MIN_TRADES_FOR_KELLY = 20          # Minimum trades for Kelly sizing
MIN_WIN_RATE_FOR_KELLY = 0.40      # Minimum 40% win rate
MAX_KELLY_FRACTION = 0.25           # Maximum 25% Kelly

# ==============================================================================
# ENUMS
# ==============================================================================
class SizingMethod(Enum):
    """Position sizing methods."""
    FIXED_FRACTIONAL = "fixed_fractional"
    KELLY_CRITERION = "kelly_criterion"
    VOLATILITY_BASED = "volatility_based"
    RISK_PARITY = "risk_parity"
    HYBRID = "hybrid"
    CUSTOM = "custom"

class MarketRegime(Enum):
    """Market regime classifications."""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"

class VolatilityRegime(Enum):
    """Volatility regime classifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketConditions:
    """Current market conditions."""
    timestamp: datetime
    spy_price: float
    vix_level: float
    spy_atr_14: float
    market_regime: MarketRegime
    volatility_regime: VolatilityRegime
    intraday_range: float
    volume_ratio: float  # Current vs average
    trend_strength: float  # -1 to 1
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategyPerformance:
    """Strategy performance metrics."""
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    current_streak: int  # Positive for wins, negative for losses
    kelly_fraction: float
    last_updated: datetime

@dataclass
class PositionSizeRequest:
    """Position sizing request."""
    strategy_name: str
    symbol: str
    entry_price: float
    stop_loss_price: float
    target_price: float | None
    signal_strength: float  # 0 to 1
    trade_type: str  # 'long', 'short', 'option'
    option_details: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionSizeRecommendation:
    """Position size recommendation."""
    timestamp: datetime
    position_size_pct: float  # Percentage of portfolio
    position_size_units: int  # Number of shares/contracts
    dollar_amount: float
    risk_amount: float
    sizing_method: SizingMethod
    confidence_score: float
    adjustments_applied: list[str]
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# POSITION SIZER CLASS
# ==============================================================================
class PositionSizer:
    """
    Professional position sizing with multiple methods.

    Implements Kelly Criterion, volatility-based sizing, and dynamic adjustments
    based on market conditions and strategy performance. Thread-safe implementation
    with comprehensive risk controls.

    Attributes:
        portfolio_value: Current portfolio value
        strategy_stats: Performance statistics by strategy
        market_conditions: Current market conditions

    Example:
        >>> sizer = PositionSizer(portfolio_value=100000)
        >>> request = PositionSizeRequest(
        ...     strategy_name="momentum",
        ...     symbol="SPY",
        ...     entry_price=400,
        ...     stop_loss_price=395
        ... )
        >>> recommendation = sizer.calculate_position_size(request)
        >>> print(f"Position size: {recommendation.position_size_pct:.1%}")
    """

    def __init__(self, portfolio_value: float, config: dict[str, Any] | None = None):
        """
        Initialize position sizer.

        Args:
            portfolio_value: Initial portfolio value
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.portfolio_value = portfolio_value

        # Risk parameters
        self.risk_per_trade = self.config.get('risk_per_trade', DEFAULT_RISK_PER_TRADE)
        self.min_position_size = self.config.get('min_position_size', MIN_POSITION_SIZE)
        self.max_position_size = self.config.get('max_position_size', MAX_POSITION_SIZE)

        # State management with thread safety
        self._lock = threading.RLock()

        # Strategy performance tracking
        self.strategy_stats: dict[str, StrategyPerformance] = {}
        self.trade_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Market conditions
        self.current_market_conditions: MarketConditions | None = None
        self.market_history: deque = deque(maxlen=252)  # 1 year of daily data

        # Sizing history
        self.sizing_history: deque = deque(maxlen=1000)

        # Load historical data
        self._load_historical_data()

        self.logger.info(f"PositionSizer initialized with portfolio value: ${portfolio_value:,.2f}")

    # ==========================================================================
    # PUBLIC METHODS - POSITION SIZING
    # ==========================================================================
    def calculate_position_size(self, request: PositionSizeRequest) -> PositionSizeRecommendation:
        """
        Calculate optimal position size.

        Args:
            request: Position sizing request with trade details

        Returns:
            Position size recommendation
        """
        try:
            with self._lock:
                # Validate request
                if not self._validate_request(request):
                    return self._create_rejected_recommendation("Invalid request")

                # Get strategy stats
                strategy_stats = self.strategy_stats.get(request.strategy_name)

                # Determine sizing method
                sizing_method = self._determine_sizing_method(request, strategy_stats)

                # Calculate base position size
                base_size = self._calculate_base_size(request, sizing_method, strategy_stats)

                # Apply adjustments
                adjusted_size = self._apply_adjustments(base_size, request, sizing_method)

                # Apply risk limits
                final_size = self._apply_risk_limits(adjusted_size, request)

                # Calculate position details
                recommendation = self._create_recommendation(
                    final_size, request, sizing_method
                )

                # Store in history
                self.sizing_history.append(recommendation)

                # Log recommendation
                self.logger.info(
                    f"Position size calculated: {recommendation.position_size_pct:.1%} "
                    f"for {request.strategy_name} using {sizing_method.value}"
                )

                return recommendation

        except Exception as e:
            self.logger.error(f"Position sizing error: {e}")
            self.error_handler.handle_error(e, {"method": "calculate_position_size"})
            return self._create_rejected_recommendation(str(e))

    def update_portfolio_value(self, new_value: float) -> None:
        """Update portfolio value."""
        with self._lock:
            old_value = self.portfolio_value
            self.portfolio_value = new_value
            self.logger.info(f"Portfolio value updated: ${old_value:,.2f} -> ${new_value:,.2f}")

    def update_market_conditions(self, conditions: MarketConditions) -> None:
        """Update current market conditions."""
        with self._lock:
            self.current_market_conditions = conditions
            self.market_history.append(conditions)
            self.logger.debug(f"Market conditions updated: VIX={conditions.vix_level:.1f}")

    def record_trade_result(self, strategy_name: str, trade_result: dict[str, Any]) -> None:
        """
        Record trade result for Kelly calculations.

        Args:
            strategy_name: Strategy identifier
            trade_result: Trade result with pnl, win/loss, etc.
        """
        with self._lock:
            # Add to trade history
            self.trade_history[strategy_name].append(trade_result)

            # Update strategy statistics
            self._update_strategy_stats(strategy_name)

            self.logger.info(f"Trade result recorded for {strategy_name}")

    # ==========================================================================
    # PRIVATE METHODS - VALIDATION
    # ==========================================================================
    def _validate_request(self, request: PositionSizeRequest) -> bool:
        """Validate position size request."""
        # Check required fields
        if not request.symbol or request.entry_price <= 0:
            return False

        # Check stop loss
        if request.stop_loss_price <= 0:
            return False

        # Validate stop loss logic
        if request.trade_type == 'long' and request.stop_loss_price >= request.entry_price:
            return False
        if request.trade_type == 'short' and request.stop_loss_price <= request.entry_price:
            return False

        # Check signal strength
        return 0 <= request.signal_strength <= 1

    # ==========================================================================
    # PRIVATE METHODS - SIZING CALCULATIONS
    # ==========================================================================
    def _determine_sizing_method(self, request: PositionSizeRequest,
                               stats: StrategyPerformance | None) -> SizingMethod:
        """Determine appropriate sizing method."""
        # Use Kelly if we have enough data and good performance
        if (stats and
            stats.total_trades >= MIN_TRADES_FOR_KELLY and
            stats.win_rate >= MIN_WIN_RATE_FOR_KELLY):
            return SizingMethod.HYBRID  # Hybrid includes Kelly

        # Use volatility-based for high volatility
        if (self.current_market_conditions and
            self.current_market_conditions.volatility_regime in
            [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]):
            return SizingMethod.VOLATILITY_BASED

        # Default to fixed fractional
        return SizingMethod.FIXED_FRACTIONAL

    def _calculate_base_size(self, request: PositionSizeRequest,
                           method: SizingMethod,
                           stats: StrategyPerformance | None) -> float:
        """Calculate base position size."""
        if method == SizingMethod.FIXED_FRACTIONAL:
            return self._calculate_fixed_fractional_size(request)

        elif method == SizingMethod.KELLY_CRITERION:
            return self._calculate_kelly_size(request, stats)

        elif method == SizingMethod.VOLATILITY_BASED:
            return self._calculate_volatility_based_size(request)

        elif method == SizingMethod.RISK_PARITY:
            return self._calculate_risk_parity_size(request)

        elif method == SizingMethod.HYBRID:
            return self._calculate_hybrid_size(request, stats)

        else:
            return self._calculate_fixed_fractional_size(request)

    def _calculate_fixed_fractional_size(self, request: PositionSizeRequest) -> float:
        """Calculate fixed fractional position size."""
        # Risk amount
        risk_amount = self.portfolio_value * self.risk_per_trade

        # Risk per unit
        risk_per_unit = abs(request.entry_price - request.stop_loss_price)

        if risk_per_unit == 0:
            return self.risk_per_trade

        # Position value
        position_value = risk_amount / risk_per_unit * request.entry_price

        # Convert to percentage
        return position_value / self.portfolio_value

    def _calculate_kelly_size(self, request: PositionSizeRequest,
                            stats: StrategyPerformance | None) -> float:
        """Calculate Kelly Criterion position size."""
        if not stats or stats.total_trades < MIN_TRADES_FOR_KELLY:
            return self._calculate_fixed_fractional_size(request)

        # Kelly formula: f = (p*b - q) / b
        # where p = win rate, q = loss rate, b = win/loss ratio
        p = stats.win_rate
        q = 1 - p

        # Avoid division by zero
        if stats.avg_loss == 0:
            b = 2.0  # Default favorable ratio
        else:
            b = stats.avg_win / abs(stats.avg_loss)

        # Calculate Kelly fraction
        if b == 0:
            kelly_fraction = 0
        else:
            kelly_fraction = (p * b - q) / b

        # Apply Kelly reduction
        kelly_fraction *= KELLY_REDUCTION_FACTOR

        # Cap at maximum
        kelly_fraction = min(kelly_fraction, MAX_KELLY_FRACTION)

        # Ensure positive
        kelly_fraction = max(0, kelly_fraction)

        return kelly_fraction

    def _calculate_volatility_based_size(self, request: PositionSizeRequest) -> float:
        """Calculate volatility-based position size."""
        if not self.current_market_conditions:
            return self._calculate_fixed_fractional_size(request)

        # Use ATR for position sizing
        atr = self.current_market_conditions.spy_atr_14

        if atr == 0:
            return self._calculate_fixed_fractional_size(request)

        # Risk amount
        risk_amount = self.portfolio_value * self.risk_per_trade

        # Position size based on ATR
        position_value = risk_amount / (atr * ATR_MULTIPLIER)

        # Convert to percentage
        return position_value / self.portfolio_value

    def _calculate_risk_parity_size(self, request: PositionSizeRequest) -> float:
        """Calculate risk parity position size."""
        # For single strategy, similar to volatility-based
        # Would be more complex with multiple strategies
        return self._calculate_volatility_based_size(request)

    def _calculate_hybrid_size(self, request: PositionSizeRequest,
                             stats: StrategyPerformance | None) -> float:
        """Calculate hybrid position size combining multiple methods."""
        # Get individual sizes
        fixed_size = self._calculate_fixed_fractional_size(request)
        vol_size = self._calculate_volatility_based_size(request)

        # Include Kelly if available
        if stats and stats.total_trades >= MIN_TRADES_FOR_KELLY:
            kelly_size = self._calculate_kelly_size(request, stats)
            # Weight: 50% Kelly, 30% volatility, 20% fixed
            return (kelly_size * 0.5) + (vol_size * 0.3) + (fixed_size * 0.2)
        else:
            # Weight: 60% volatility, 40% fixed
            return (vol_size * 0.6) + (fixed_size * 0.4)

    # ==========================================================================
    # PRIVATE METHODS - ADJUSTMENTS
    # ==========================================================================
    def _apply_adjustments(self, base_size: float, request: PositionSizeRequest,
                         method: SizingMethod) -> float:
        """Apply various adjustments to base position size."""
        adjusted_size = base_size
        adjustments = []

        # Market regime adjustment
        if self.current_market_conditions:
            regime_mult = REGIME_MULTIPLIERS.get(
                self.current_market_conditions.market_regime.value, 1.0
            )
            adjusted_size *= regime_mult
            if regime_mult != 1.0:
                adjustments.append(f"Market regime ({regime_mult:.1f}x)")

        # Volatility adjustment
        if self.current_market_conditions:
            vol_mult = self._get_volatility_multiplier()
            adjusted_size *= vol_mult
            if vol_mult != 1.0:
                adjustments.append(f"Volatility ({vol_mult:.1f}x)")

        # Day of week adjustment
        dow_mult = DAY_OF_WEEK_MULTIPLIERS.get(datetime.now().weekday(), 1.0)
        adjusted_size *= dow_mult
        if dow_mult != 1.0:
            adjustments.append(f"Day of week ({dow_mult:.1f}x)")

        # Signal strength adjustment
        signal_mult = 0.5 + (0.5 * request.signal_strength)  # 0.5x to 1.0x
        adjusted_size *= signal_mult
        if signal_mult != 1.0:
            adjustments.append(f"Signal strength ({signal_mult:.1f}x)")

        # Consecutive loss adjustment
        streak_mult = self._get_streak_multiplier(request.strategy_name)
        adjusted_size *= streak_mult
        if streak_mult != 1.0:
            adjustments.append(f"Win/loss streak ({streak_mult:.1f}x)")

        # Store adjustments in request metadata
        request.metadata['adjustments'] = adjustments

        return adjusted_size

    def _get_volatility_multiplier(self) -> float:
        """Get volatility-based size multiplier."""
        if not self.current_market_conditions:
            return 1.0

        vix = self.current_market_conditions.vix_level

        if vix > HIGH_VOL_THRESHOLD:
            return 0.5  # Reduce size by 50% in high volatility
        elif vix < LOW_VOL_THRESHOLD:
            return 1.2  # Increase size by 20% in low volatility
        else:
            # Linear interpolation
            return 1.2 - (0.7 * (vix - LOW_VOL_THRESHOLD) /
                         (HIGH_VOL_THRESHOLD - LOW_VOL_THRESHOLD))

    def _get_streak_multiplier(self, strategy_name: str) -> float:
        """Get win/loss streak multiplier."""
        stats = self.strategy_stats.get(strategy_name)
        if not stats:
            return 1.0

        streak = stats.current_streak

        # Reduce size after consecutive losses
        if streak < -3:
            return 0.5  # 50% reduction after 3+ losses
        elif streak < -2:
            return 0.7  # 30% reduction after 2 losses
        elif streak < -1:
            return 0.85  # 15% reduction after 1 loss
        # Slightly increase after wins
        elif streak > 3:
            return 1.1  # 10% increase after 3+ wins
        else:
            return 1.0

    def _apply_risk_limits(self, size: float, request: PositionSizeRequest) -> float:
        """Apply risk limits to position size."""
        # Apply minimum
        size = max(size, self.min_position_size)

        # Apply maximum
        size = max(min(size, self.max_position_size), 0)

        # Check portfolio constraints
        size = self._check_portfolio_constraints(size, request)

        return size

    def _check_portfolio_constraints(self, size: float,
                                   request: PositionSizeRequest) -> float:
        """Check portfolio-level constraints."""
        # Would integrate with portfolio manager for:
        # - Total exposure limits
        # - Correlation limits
        # - Sector concentration
        # - Greeks limits (for options)

        # For now, just ensure reasonable size
        return size

    # ==========================================================================
    # PRIVATE METHODS - RECOMMENDATION CREATION
    # ==========================================================================
    def _create_recommendation(self, size_pct: float, request: PositionSizeRequest,
                             method: SizingMethod) -> PositionSizeRecommendation:
        """Create position size recommendation."""
        # Calculate dollar amount
        dollar_amount = self.portfolio_value * size_pct

        # Calculate units
        units = int(dollar_amount / request.entry_price)

        # Adjust for round lots if needed
        if request.trade_type == 'option':
            units = max(1, units)  # At least 1 contract
        else:
            # Round to nearest 10 shares for stocks
            units = max(10, round(units / 10) * 10)

        # Recalculate actual dollar amount
        actual_dollar_amount = units * request.entry_price
        actual_size_pct = actual_dollar_amount / self.portfolio_value

        # Calculate risk amount
        risk_per_unit = abs(request.entry_price - request.stop_loss_price)
        risk_amount = units * risk_per_unit

        # Confidence score
        confidence = self._calculate_confidence_score(request, method)

        # Warnings
        warnings = self._generate_warnings(actual_size_pct, request)

        return PositionSizeRecommendation(
            timestamp=datetime.now(),
            position_size_pct=actual_size_pct,
            position_size_units=units,
            dollar_amount=actual_dollar_amount,
            risk_amount=risk_amount,
            sizing_method=method,
            confidence_score=confidence,
            adjustments_applied=request.metadata.get('adjustments', []),
            warnings=warnings,
            metadata={
                'strategy': request.strategy_name,
                'symbol': request.symbol,
                'signal_strength': request.signal_strength
            }
        )

    def _create_rejected_recommendation(self, reason: str) -> PositionSizeRecommendation:
        """Create rejected recommendation."""
        return PositionSizeRecommendation(
            timestamp=datetime.now(),
            position_size_pct=0,
            position_size_units=0,
            dollar_amount=0,
            risk_amount=0,
            sizing_method=SizingMethod.FIXED_FRACTIONAL,
            confidence_score=0,
            adjustments_applied=[],
            warnings=[f"Position rejected: {reason}"],
            metadata={'rejected': True, 'reason': reason}
        )

    def _calculate_confidence_score(self, request: PositionSizeRequest,
                                  method: SizingMethod) -> float:
        """Calculate confidence score for recommendation."""
        confidence = 0.5  # Base confidence

        # Method confidence
        if method == SizingMethod.HYBRID:
            confidence += 0.2
        elif method == SizingMethod.KELLY_CRITERION:
            confidence += 0.15
        elif method == SizingMethod.VOLATILITY_BASED:
            confidence += 0.1

        # Signal strength impact
        confidence += 0.2 * request.signal_strength

        # Market conditions impact
        if self.current_market_conditions:
            if self.current_market_conditions.volatility_regime == VolatilityRegime.NORMAL:
                confidence += 0.1

        # Cap at 1.0
        return min(confidence, 1.0)

    def _generate_warnings(self, size_pct: float,
                         request: PositionSizeRequest) -> list[str]:
        """Generate warnings for position size."""
        warnings = []

        # Size warnings
        if size_pct >= self.max_position_size * 0.9:
            warnings.append(f"Position size near maximum limit ({size_pct:.1%})")

        if size_pct <= self.min_position_size * 1.1:
            warnings.append(f"Position size near minimum limit ({size_pct:.1%})")

        # Volatility warnings
        if (self.current_market_conditions and
            self.current_market_conditions.vix_level > HIGH_VOL_THRESHOLD):
            warnings.append(f"High volatility environment (VIX={self.current_market_conditions.vix_level:.1f})")

        # Streak warnings
        stats = self.strategy_stats.get(request.strategy_name)
        if stats and stats.current_streak < -2:
            warnings.append(f"Strategy on losing streak ({stats.current_streak} losses)")

        return warnings

    # ==========================================================================
    # PRIVATE METHODS - STATISTICS
    # ==========================================================================
    def _update_strategy_stats(self, strategy_name: str) -> None:
        """Update strategy performance statistics."""
        trades = list(self.trade_history[strategy_name])

        if len(trades) < 5:  # Need minimum trades
            return

        # Calculate statistics
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]

        win_rate = len(winning_trades) / len(trades) if trades else 0

        avg_win = (sum(t['pnl'] for t in winning_trades) / len(winning_trades)
                  if winning_trades else 0)
        avg_loss = (sum(abs(t['pnl']) for t in losing_trades) / len(losing_trades)
                   if losing_trades else 0)

        # Profit factor
        total_wins = sum(t['pnl'] for t in winning_trades)
        total_losses = sum(abs(t['pnl']) for t in losing_trades)
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # Calculate streak
        streak = self._calculate_current_streak(trades)

        # Calculate Sharpe ratio
        returns = [t.get('return_pct', 0) for t in trades]
        sharpe = self._calculate_sharpe_ratio(returns) if returns else 0

        # Calculate max drawdown
        equity_curve = self._build_equity_curve(trades)
        max_dd = self._calculate_max_drawdown(equity_curve)

        # Update or create stats
        self.strategy_stats[strategy_name] = StrategyPerformance(
            strategy_name=strategy_name,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            current_streak=streak,
            kelly_fraction=self._calculate_kelly_fraction(win_rate, avg_win, avg_loss),
            last_updated=datetime.now()
        )

    def _calculate_current_streak(self, trades: list[dict]) -> int:
        """Calculate current win/loss streak."""
        if not trades:
            return 0

        streak = 0
        current_type = None

        # Go through trades in reverse (most recent first)
        for trade in reversed(trades):
            is_win = trade.get('pnl', 0) > 0

            if current_type is None:
                current_type = is_win
                streak = 1 if is_win else -1
            elif is_win == current_type:
                streak += 1 if is_win else -1
            else:
                break

        return streak

    def _calculate_sharpe_ratio(self, returns: list[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 20:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0.0

        # Annualized Sharpe (assuming daily returns)
        return (mean_return / std_return) * np.sqrt(252)

    def _build_equity_curve(self, trades: list[dict]) -> list[float]:
        """Build equity curve from trades."""
        equity = [100000]  # Start with base

        for trade in trades:
            pnl = trade.get('pnl', 0)
            equity.append(equity[-1] + pnl)

        return equity

    def _calculate_max_drawdown(self, equity_curve: list[float]) -> float:
        """Calculate maximum drawdown."""
        if len(equity_curve) < 2:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve[1:]:
            if value > peak:
                peak = value

            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_kelly_fraction(self, win_rate: float, avg_win: float,
                                avg_loss: float) -> float:
        """Calculate Kelly fraction for strategy."""
        if avg_loss == 0 or win_rate == 0:
            return 0.0

        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        kelly = (p * b - q) / b if b > 0 else 0

        # Apply reduction factor
        return max(0, min(kelly * KELLY_REDUCTION_FACTOR, MAX_KELLY_FRACTION))

    # ==========================================================================
    # PRIVATE METHODS - DATA MANAGEMENT
    # ==========================================================================
    def _load_historical_data(self) -> None:
        """Load historical data for calculations."""
        # In production, this would load from database
        self.logger.info("Loading historical sizing data")

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    def get_sizing_statistics(self) -> dict[str, Any]:
        """Get position sizing statistics."""
        with self._lock:
            recent_sizes = list(self.sizing_history)[-100:]

            if not recent_sizes:
                return {}

            sizes_pct = [r.position_size_pct for r in recent_sizes]

            return {
                'avg_position_size': np.mean(sizes_pct),
                'median_position_size': np.median(sizes_pct),
                'max_position_size': max(sizes_pct),
                'min_position_size': min(sizes_pct),
                'std_position_size': np.std(sizes_pct),
                'total_recommendations': len(self.sizing_history),
                'method_distribution': self._get_method_distribution(recent_sizes),
                'avg_confidence': np.mean([r.confidence_score for r in recent_sizes])
            }

    def _get_method_distribution(self, recommendations: list[PositionSizeRecommendation]) -> dict[str, float]:
        """Get distribution of sizing methods used."""
        method_counts = defaultdict(int)

        for rec in recommendations:
            method_counts[rec.sizing_method.value] += 1

        total = len(recommendations)
        return {
            method: count / total
            for method, count in method_counts.items()
        }

    def get_strategy_statistics(self, strategy_name: str) -> StrategyPerformance | None:
        """Get statistics for a specific strategy."""
        with self._lock:
            return self.strategy_stats.get(strategy_name)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Singleton instance
_position_sizer_instance: PositionSizer | None = None
_instance_lock = threading.Lock()

def get_position_sizer(portfolio_value: float, **kwargs) -> PositionSizer:
    """
    Get or create position sizer instance (singleton).

    Args:
        portfolio_value: Portfolio value
        **kwargs: Additional configuration

    Returns:
        PositionSizer instance
    """
    global _position_sizer_instance

    if _position_sizer_instance is None:
        with _instance_lock:
            if _position_sizer_instance is None:
                _position_sizer_instance = PositionSizer(portfolio_value, kwargs)
    else:
        # Update portfolio value if instance exists
        _position_sizer_instance.update_portfolio_value(portfolio_value)

    return _position_sizer_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # Initialize position sizer
    sizer = get_position_sizer(portfolio_value=100000)

    # Create test market conditions
    market_conditions = MarketConditions(
        timestamp=datetime.now(),
        spy_price=400.0,
        vix_level=18.0,
        spy_atr_14=5.0,
        market_regime=MarketRegime.NEUTRAL,
        volatility_regime=VolatilityRegime.NORMAL,
        intraday_range=0.015,
        volume_ratio=1.1,
        trend_strength=0.3
    )

    sizer.update_market_conditions(market_conditions)

    # Test position sizing request
    request = PositionSizeRequest(
        strategy_name="momentum",
        symbol="SPY",
        entry_price=400.0,
        stop_loss_price=395.0,
        target_price=410.0,
        signal_strength=0.8,
        trade_type="long"
    )

    # Calculate position size
    recommendation = sizer.calculate_position_size(request)


    if recommendation.adjustments_applied:
        for _adj in recommendation.adjustments_applied:
            pass

    if recommendation.warnings:
        for _warn in recommendation.warnings:
            pass

    # Test with some trade history
    trades = [
        {'pnl': 500, 'return_pct': 0.005},
        {'pnl': -200, 'return_pct': -0.002},
        {'pnl': 800, 'return_pct': 0.008},
        {'pnl': 300, 'return_pct': 0.003},
        {'pnl': -150, 'return_pct': -0.0015},
        {'pnl': 600, 'return_pct': 0.006},
    ]

    for trade in trades:
        sizer.record_trade_result("momentum", trade)

    # Get strategy statistics
    stats = sizer.get_strategy_statistics("momentum")
    if stats:
        pass

    # Test different market conditions
    high_vol_conditions = MarketConditions(
        timestamp=datetime.now(),
        spy_price=380.0,
        vix_level=35.0,
        spy_atr_14=10.0,
        market_regime=MarketRegime.BEAR,
        volatility_regime=VolatilityRegime.HIGH,
        intraday_range=0.03,
        volume_ratio=1.5,
        trend_strength=-0.5
    )

    sizer.update_market_conditions(high_vol_conditions)
    high_vol_recommendation = sizer.calculate_position_size(request)


    # Get overall statistics
    sizing_stats = sizer.get_sizing_statistics()
    for _key, value in sizing_stats.items():
        if isinstance(value, dict):
            for _k, _v in value.items():
                pass
        else:
            pass

