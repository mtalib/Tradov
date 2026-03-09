#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderP_PortfolioMgmt
Module: SpyderP07_RenaissancePositionSizer.py
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
from typing import Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

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

DEFAULT_MAX_POSITION_SIZE = 0.05        # 5% of portfolio per position
DEFAULT_MAX_PORTFOLIO_RISK = 0.02       # 2% max portfolio risk per trade
DEFAULT_MIN_CONFIDENCE = 0.50           # Minimum confidence to trade
DEFAULT_HIGH_CONFIDENCE = 0.70          # High confidence threshold
DEFAULT_MIN_CONTRACTS = 1               # Minimum contracts per trade
DEFAULT_MAX_CONTRACTS = 100             # Maximum contracts per trade

# Kelly Criterion parameters
KELLY_FRACTION = 0.25  # Use quarter-Kelly for safety


# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class PositionSizeMethod(Enum):
    """Position sizing method enumeration"""
    FIXED_FRACTION = "fixed_fraction"
    RISK_BASED = "risk_based"
    KELLY = "kelly"
    CONFIDENCE_SCALED = "confidence_scaled"


class TradeOutcome(Enum):
    """Trade outcome classification"""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PositionSizeResult:
    """Result of position size calculation"""
    num_contracts: int
    position_value: float
    risk_per_trade: float
    confidence_used: float
    method_used: PositionSizeMethod
    reasoning: str

    # Risk metrics
    max_loss: float = 0.0
    risk_reward_ratio: float = 0.0
    portfolio_risk_pct: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'num_contracts': self.num_contracts,
            'position_value': self.position_value,
            'risk_per_trade': self.risk_per_trade,
            'confidence_used': self.confidence_used,
            'method_used': self.method_used.value,
            'reasoning': self.reasoning,
            'max_loss': self.max_loss,
            'risk_reward_ratio': self.risk_reward_ratio,
            'portfolio_risk_pct': self.portfolio_risk_pct
        }


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    entry_price: float
    exit_price: float
    position_size: int
    pnl: float
    return_pct: float
    confidence: float
    exit_reason: str


@dataclass
class PerformanceMetrics:
    """Portfolio performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0


# ==============================================================================
# RENAISSANCE-STYLE POSITION SIZER
# ==============================================================================
class RenaissancePositionSizer:
    """
    Renaissance-style position sizer with confidence-based scaling.

    Core Principles:
    1. Position size scales with signal confidence
    2. Risk is limited per trade and for the portfolio
    3. Smaller, more frequent trades vs. large concentrated bets
    4. Performance tracking for continuous improvement
    """

    def __init__(
        self,
        initial_capital: float = 100000,
        max_position_size: float = DEFAULT_MAX_POSITION_SIZE,
        max_portfolio_risk: float = DEFAULT_MAX_PORTFOLIO_RISK,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE
    ):
        """
        Initialize the position sizer.

        Args:
            initial_capital: Starting capital
            max_position_size: Maximum position as fraction of capital (0.05 = 5%)
            max_portfolio_risk: Maximum risk per trade as fraction (0.02 = 2%)
            min_confidence: Minimum confidence to trade (0.5 = 50%)
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_position_size = max_position_size
        self.max_portfolio_risk = max_portfolio_risk
        self.min_confidence = min_confidence

        # Logging and error handling
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Trade tracking
        self.trade_history: list[TradeRecord] = []
        self.open_positions: dict[str, dict] = {}
        self.metrics = PerformanceMetrics()

        self.logger.info(
            f"RenaissancePositionSizer initialized: "
            f"capital=${initial_capital:,.2f}, "
            f"max_position={max_position_size:.1%}, "
            f"max_risk={max_portfolio_risk:.1%}"
        )

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        confidence: float,
        method: PositionSizeMethod = PositionSizeMethod.CONFIDENCE_SCALED
    ) -> PositionSizeResult:
        """
        Calculate optimal position size using Renaissance-style risk management.

        Position size is determined by:
        1. Statistical confidence in the signal
        2. Risk per contract (entry - stop loss)
        3. Maximum portfolio risk limit
        4. Available capital

        Args:
            entry_price: Entry price per contract
            stop_loss: Stop loss price
            confidence: Signal confidence (0-1)
            method: Position sizing method

        Returns:
            PositionSizeResult with position details
        """
        try:
            # Validate inputs
            if confidence < self.min_confidence:
                return PositionSizeResult(
                    num_contracts=0,
                    position_value=0,
                    risk_per_trade=0,
                    confidence_used=confidence,
                    method_used=method,
                    reasoning=f"Confidence {confidence:.2%} below minimum {self.min_confidence:.2%}"
                )

            if entry_price <= 0 or stop_loss <= 0:
                return PositionSizeResult(
                    num_contracts=0,
                    position_value=0,
                    risk_per_trade=0,
                    confidence_used=confidence,
                    method_used=method,
                    reasoning="Invalid entry or stop loss price"
                )

            # Calculate risk per contract (for options: price * 100 shares)
            risk_per_contract = abs(entry_price - stop_loss) * 100

            if risk_per_contract <= 0:
                return PositionSizeResult(
                    num_contracts=0,
                    position_value=0,
                    risk_per_trade=0,
                    confidence_used=confidence,
                    method_used=method,
                    reasoning="No risk per contract (stop loss equals entry)"
                )

            # Calculate position size based on method
            if method == PositionSizeMethod.CONFIDENCE_SCALED:
                num_contracts = self._confidence_scaled_sizing(
                    entry_price, stop_loss, confidence, risk_per_contract
                )
                reasoning = f"Confidence-scaled: {confidence:.2%} confidence applied"

            elif method == PositionSizeMethod.RISK_BASED:
                num_contracts = self._risk_based_sizing(risk_per_contract)
                reasoning = "Risk-based: fixed portfolio risk per trade"

            elif method == PositionSizeMethod.KELLY:
                num_contracts = self._kelly_criterion_sizing(
                    entry_price, stop_loss, confidence, risk_per_contract
                )
                reasoning = "Kelly Criterion: optimal growth sizing"

            else:  # FIXED_FRACTION
                num_contracts = self._fixed_fraction_sizing(entry_price)
                reasoning = "Fixed fraction: percentage of capital"

            # Ensure minimum and maximum constraints
            num_contracts = max(DEFAULT_MIN_CONTRACTS if confidence > self.min_confidence else 0,
                               min(num_contracts, DEFAULT_MAX_CONTRACTS))

            # Calculate result values
            position_value = num_contracts * entry_price * 100
            risk_per_trade = num_contracts * risk_per_contract
            max_loss = risk_per_trade
            portfolio_risk_pct = risk_per_trade / self.current_capital if self.current_capital > 0 else 0

            # Check if position exceeds available capital
            if position_value > self.current_capital:
                # Scale down to available capital
                max_affordable = int(self.current_capital / (entry_price * 100))
                num_contracts = min(num_contracts, max_affordable)
                position_value = num_contracts * entry_price * 100
                risk_per_trade = num_contracts * risk_per_contract
                reasoning += " (scaled down to available capital)"

            return PositionSizeResult(
                num_contracts=num_contracts,
                position_value=position_value,
                risk_per_trade=risk_per_trade,
                confidence_used=confidence,
                method_used=method,
                reasoning=reasoning,
                max_loss=max_loss,
                risk_reward_ratio=0,  # Calculated by caller with target
                portfolio_risk_pct=portfolio_risk_pct
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'calculate_position_size'})
            return PositionSizeResult(
                num_contracts=0,
                position_value=0,
                risk_per_trade=0,
                confidence_used=confidence,
                method_used=method,
                reasoning=f"Error in calculation: {str(e)}"
            )

    def _confidence_scaled_sizing(
        self,
        entry_price: float,
        stop_loss: float,
        confidence: float,
        risk_per_contract: float
    ) -> int:
        """
        Calculate position size scaled by confidence.

        Higher confidence = larger position (within limits).
        This is the core Renaissance approach.
        """
        # Maximum capital to risk on this trade
        max_risk_capital = self.current_capital * self.max_portfolio_risk

        # Scale risk by confidence (higher confidence = more risk taken)
        # Confidence scaling: 50% confidence = 0.5x, 100% confidence = 1.5x
        confidence_multiplier = 0.5 + confidence
        adjusted_risk_capital = max_risk_capital * confidence_multiplier

        # Calculate number of contracts based on risk
        num_contracts = int(adjusted_risk_capital / risk_per_contract)

        # Also check max position size constraint
        max_contracts_by_size = int(
            (self.current_capital * self.max_position_size) / (entry_price * 100)
        )

        return min(num_contracts, max_contracts_by_size)

    def _risk_based_sizing(self, risk_per_contract: float) -> int:
        """Calculate position size based on fixed portfolio risk."""
        max_risk_capital = self.current_capital * self.max_portfolio_risk
        return int(max_risk_capital / risk_per_contract)

    def _kelly_criterion_sizing(
        self,
        entry_price: float,
        stop_loss: float,
        confidence: float,
        risk_per_contract: float
    ) -> int:
        """
        Calculate position size using Kelly Criterion.

        Kelly formula: f* = p - (1-p)/b
        Where:
            p = probability of winning (confidence)
            b = win/loss ratio (assumed 1:1 for simplicity)

        We use quarter-Kelly for safety.
        """
        # Win probability from confidence
        p = confidence
        q = 1 - p

        # Assume 1:1 win/loss ratio (conservative)
        b = 1.0

        # Kelly fraction
        kelly = p - (q / b)

        # Use quarter-Kelly for safety
        safe_kelly = kelly * KELLY_FRACTION

        if safe_kelly <= 0:
            return 0

        # Calculate position
        position_value = self.current_capital * safe_kelly
        num_contracts = int(position_value / (entry_price * 100))

        return num_contracts

    def _fixed_fraction_sizing(self, entry_price: float) -> int:
        """Calculate position size as fixed fraction of capital."""
        position_value = self.current_capital * self.max_position_size
        return int(position_value / (entry_price * 100))

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        position_size: int,
        confidence: float,
        entry_time: datetime,
        exit_reason: str
    ) -> TradeRecord:
        """
        Record a completed trade and update metrics.

        Args:
            symbol: Option symbol
            entry_price: Entry price per contract
            exit_price: Exit price per contract
            position_size: Number of contracts
            confidence: Original signal confidence
            entry_time: Time of entry
            exit_reason: Reason for exit

        Returns:
            TradeRecord with trade details
        """
        try:
            # Calculate P&L
            pnl = (exit_price - entry_price) * position_size * 100
            cost_basis = entry_price * position_size * 100
            return_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

            # Create record
            record = TradeRecord(
                entry_time=entry_time,
                exit_time=datetime.now(),
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                position_size=position_size,
                pnl=pnl,
                return_pct=return_pct,
                confidence=confidence,
                exit_reason=exit_reason
            )

            # Add to history
            self.trade_history.append(record)

            # Update capital
            exit_price * position_size * 100
            self.current_capital += pnl

            # Update metrics
            self._update_metrics(record)

            self.logger.info(
                f"Trade recorded: {symbol} | "
                f"P&L: ${pnl:,.2f} ({return_pct:.2f}%) | "
                f"Reason: {exit_reason}"
            )

            return record

        except Exception as e:
            self.error_handler.handle_error(e, {'method': 'record_trade'})
            raise

    def _update_metrics(self, trade: TradeRecord) -> None:
        """Update performance metrics with new trade."""
        self.metrics.total_trades += 1
        self.metrics.total_pnl += trade.pnl

        if trade.pnl > 0:
            self.metrics.winning_trades += 1
            # Running average of wins
            self.metrics.avg_win = (
                (self.metrics.avg_win * (self.metrics.winning_trades - 1) + trade.pnl)
                / self.metrics.winning_trades
            )
        elif trade.pnl < 0:
            self.metrics.losing_trades += 1
            # Running average of losses
            self.metrics.avg_loss = (
                (self.metrics.avg_loss * (self.metrics.losing_trades - 1) + abs(trade.pnl))
                / self.metrics.losing_trades
            )

        # Update win rate
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = self.metrics.winning_trades / self.metrics.total_trades

        # Update profit factor
        total_wins = self.metrics.avg_win * self.metrics.winning_trades
        total_losses = self.metrics.avg_loss * self.metrics.losing_trades
        if total_losses > 0:
            self.metrics.profit_factor = total_wins / total_losses

        # Calculate Sharpe ratio (simplified)
        if len(self.trade_history) > 1:
            returns = [t.return_pct for t in self.trade_history]
            if np.std(returns) > 0:
                self.metrics.sharpe_ratio = np.mean(returns) / np.std(returns)

    def get_metrics(self) -> dict[str, Any]:
        """Get current performance metrics."""
        return {
            'total_trades': self.metrics.total_trades,
            'winning_trades': self.metrics.winning_trades,
            'losing_trades': self.metrics.losing_trades,
            'win_rate': f"{self.metrics.win_rate:.2%}",
            'avg_win': f"${self.metrics.avg_win:,.2f}",
            'avg_loss': f"${self.metrics.avg_loss:,.2f}",
            'profit_factor': f"{self.metrics.profit_factor:.2f}",
            'total_pnl': f"${self.metrics.total_pnl:,.2f}",
            'sharpe_ratio': f"{self.metrics.sharpe_ratio:.2f}",
            'current_capital': f"${self.current_capital:,.2f}",
            'total_return': f"{((self.current_capital - self.initial_capital) / self.initial_capital * 100):.2f}%"
        }

    def get_trade_history_df(self) -> pd.DataFrame:
        """Get trade history as DataFrame."""
        if not self.trade_history:
            return pd.DataFrame()

        data = [
            {
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'symbol': t.symbol,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'position_size': t.position_size,
                'pnl': t.pnl,
                'return_pct': t.return_pct,
                'confidence': t.confidence,
                'exit_reason': t.exit_reason
            }
            for t in self.trade_history
        ]

        return pd.DataFrame(data)

    # --------------------------------------------------------------------------
    # EMPYRICAL-VALIDATED SHARPE
    # --------------------------------------------------------------------------

    def compute_empyrical_sharpe(self, returns: pd.Series,
                                  risk_free_rate: float = 0.05) -> dict[str, float]:
        """
        Compute Sharpe ratio using empyrical instead of manual mean/std.

        Replaces the hand-rolled calculation for institutional accuracy.

        Args:
            returns: Daily return series.
            risk_free_rate: Annual risk-free rate.

        Returns:
            Dictionary with validated Sharpe, Sortino, and related metrics.
        """
        try:
            import empyrical
        except ImportError:
            sharpe = float(returns.mean() / (returns.std() + 1e-8) * np.sqrt(252))
            return {'sharpe_ratio': sharpe, '_backend': 'fallback'}

        rf_daily = risk_free_rate / 252
        return {
            'sharpe_ratio': float(empyrical.sharpe_ratio(returns, risk_free=rf_daily)),
            'sortino_ratio': float(empyrical.sortino_ratio(returns)),
            'annual_return': float(empyrical.annual_return(returns)),
            'annual_volatility': float(empyrical.annual_volatility(returns)),
            'max_drawdown': float(empyrical.max_drawdown(returns)),
            'calmar_ratio': float(empyrical.calmar_ratio(returns)),
            '_backend': 'empyrical',
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_position_sizer(
    initial_capital: float = 100000,
    max_position_size: float = 0.05,
    max_portfolio_risk: float = 0.02
) -> RenaissancePositionSizer:
    """
    Factory function to create a Renaissance-style position sizer.

    Args:
        initial_capital: Starting capital
        max_position_size: Maximum position as fraction of capital
        max_portfolio_risk: Maximum risk per trade as fraction

    Returns:
        Configured RenaissancePositionSizer instance
    """
    return RenaissancePositionSizer(
        initial_capital=initial_capital,
        max_position_size=max_position_size,
        max_portfolio_risk=max_portfolio_risk
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create position sizer
    sizer = create_position_sizer(
        initial_capital=100000,
        max_position_size=0.05,
        max_portfolio_risk=0.02
    )


    # Test position sizing with different confidence levels

    test_cases = [
        {"confidence": 0.40, "entry": 5.00, "stop": 3.50},  # Below minimum
        {"confidence": 0.55, "entry": 5.00, "stop": 3.50},  # Low confidence
        {"confidence": 0.70, "entry": 5.00, "stop": 3.50},  # Medium confidence
        {"confidence": 0.85, "entry": 5.00, "stop": 3.50},  # High confidence
        {"confidence": 0.95, "entry": 5.00, "stop": 3.50},  # Very high confidence
    ]

    for case in test_cases:
        result = sizer.calculate_position_size(
            entry_price=case["entry"],
            stop_loss=case["stop"],
            confidence=case["confidence"]
        )


    # Test different sizing methods

    methods = [
        PositionSizeMethod.CONFIDENCE_SCALED,
        PositionSizeMethod.RISK_BASED,
        PositionSizeMethod.KELLY,
        PositionSizeMethod.FIXED_FRACTION
    ]

    for method in methods:
        result = sizer.calculate_position_size(
            entry_price=5.00,
            stop_loss=3.50,
            confidence=0.70,
            method=method
        )


    # Simulate some trades

    # Simulate wins and losses
    np.random.seed(42)
    for i in range(10):
        confidence = np.random.uniform(0.55, 0.85)
        entry = np.random.uniform(4, 8)
        is_win = np.random.random() < 0.55  # 55% win rate

        if is_win:
            exit_price = entry * np.random.uniform(1.2, 1.8)
            exit_reason = "Take profit"
        else:
            exit_price = entry * np.random.uniform(0.5, 0.85)
            exit_reason = "Stop loss"

        result = sizer.calculate_position_size(
            entry_price=entry,
            stop_loss=entry * 0.7,
            confidence=confidence
        )

        if result.num_contracts > 0:
            sizer.record_trade(
                symbol=f"SPY250117C{450+i}",
                entry_price=entry,
                exit_price=exit_price,
                position_size=result.num_contracts,
                confidence=confidence,
                entry_time=datetime.now(),
                exit_reason=exit_reason
            )

    # Display final metrics

    metrics = sizer.get_metrics()
    for _key, _value in metrics.items():
        pass

    # Display trade history

    history_df = sizer.get_trade_history_df()
    if not history_df.empty:
        pass

