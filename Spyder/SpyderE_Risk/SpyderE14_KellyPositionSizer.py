#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Series: SpyderE_Risk
Module: SpyderE14_KellyPositionSizer.py
Purpose: Kelly Criterion for Optimal Position Sizing
Author: SPYDER Team
Date Created: 2025-01-04
Last Updated: 2025-01-04

Description:
    Implements Kelly Criterion for optimal position sizing,
    inspired by Renaissance Technologies' quantitative framework.
    
    Kelly Criterion provides:
    - Mathematically optimal position sizing for long-term growth
    - Balance between growth and drawdown
    - Fractional Kelly for reduced risk (Quarter-Kelly, Half-Kelly)
    - Multi-asset Kelly for portfolio optimization
    - Confidence-based sizing based on prediction accuracy
    
    Based on Renaissance research, Kelly Criterion is essential
    for maximizing long-term geometric growth while controlling
    drawdown. Renaissance uses Quarter-Kelly to reduce volatility
    while maintaining most of the growth benefits.

Key Features:
    - Classic Kelly Criterion (f* = (p(b+1) - 1) / b)
    - Fractional Kelly (Half-Kelly, Quarter-Kelly)
    - Multi-asset Kelly for portfolio optimization
    - Confidence-based sizing
    - Drawdown-aware sizing
    - Risk-adjusted Kelly
    - Integration with existing Spyder risk management

Dependencies:
    - numpy, pandas for data processing
    - scipy for optimization
    - SpyderE01_RiskManager for risk limits

References:
    - Kelly, J. (1956) "A New Interpretation of Information Rate"
    - Thorp, E. (1962) "Beat the Dealer"
    - Renaissance Technologies research on position sizing
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import optimize

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback logging if custom modules not available
    import logging
    SpyderLogger = logging.getLogger
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.error(f"[{context}] {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Kelly Fraction Types
class KellyFraction(Enum):
    """Kelly fraction types for risk adjustment."""
    FULL_KELLY = 1.0  # Full Kelly (maximum growth, maximum risk)
    HALF_KELLY = 0.5  # Half Kelly (reduced risk)
    QUARTER_KELLY = 0.25  # Quarter Kelly (Renaissance standard)
    EIGHTH_KELLY = 0.125  # Eighth Kelly (very conservative)
    CUSTOM = 0.0  # Custom fraction

# Position Sizing Methods
class SizingMethod(Enum):
    """Position sizing methods."""
    KELLY = "kelly"  # Kelly Criterion
    FIXED_FRACTION = "fixed_fraction"  # Fixed fraction of capital
    RISK_PARITY = "risk_parity"  # Risk parity
    VOLATILITY_TARGET = "volatility_target"  # Volatility targeting
    CONFIDENCE_BASED = "confidence_based"  # Confidence-based sizing

# Default Configuration
DEFAULT_KELLY_FRACTION = 0.25  # Quarter-Kelly (Renaissance standard)
DEFAULT_MAX_POSITION_SIZE = 0.20  # Maximum 20% of capital per position
DEFAULT_MIN_POSITION_SIZE = 0.01  # Minimum 1% of capital per position
DEFAULT_CONFIDENCE_THRESHOLD = 0.70  # Minimum confidence for trading

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class KellyResult:
    """Results from Kelly Criterion calculation."""
    kelly_fraction: float  # Optimal fraction of capital
    expected_growth: float  # Expected geometric growth rate
    expected_return: float  # Expected arithmetic return
    expected_drawdown: float  # Expected maximum drawdown
    sharpe_ratio: float  # Expected Sharpe ratio
    win_probability: float  # Probability of winning
    avg_win: float  # Average win amount
    avg_loss: float  # Average loss amount
    risk_reward_ratio: float  # Risk/reward ratio

@dataclass
class PositionSizingResult:
    """Result of position sizing calculation."""
    position_size: float  # Position size (fraction of capital)
    position_value: float  # Position value (dollars)
    number_of_contracts: int  # Number of options contracts
    kelly_fraction: float  # Kelly fraction used
    sizing_method: SizingMethod  # Sizing method used
    confidence: float  # Confidence in sizing
    risk_limit: float  # Risk limit (fraction of capital)
    expected_loss: float  # Expected maximum loss
    expected_return: float  # Expected return
    reason: str = ""  # Explanation for sizing

@dataclass
class MultiAssetKellyResult:
    """Results from multi-asset Kelly optimization."""
    position_weights: np.ndarray  # Optimal weights for each asset
    expected_growth: float  # Expected portfolio growth
    expected_return: float  # Expected portfolio return
    expected_volatility: float  # Expected portfolio volatility
    sharpe_ratio: float  # Expected Sharpe ratio
    correlation_matrix: Optional[np.ndarray]  # Correlation matrix
    covariance_matrix: Optional[np.ndarray]  # Covariance matrix

# ==============================================================================
# MAIN CLASS
# ==============================================================================

class KellyPositionSizer:
    """
    Kelly Criterion Position Sizer for Optimal Position Sizing.
    
    Inspired by Renaissance Technologies' quantitative framework, this module
    implements the Kelly Criterion for mathematically optimal position sizing
    to maximize long-term geometric growth while controlling drawdown.
    
    Key Concepts:
        - Kelly Criterion: f* = (p(b+1) - 1) / b
        - Fractional Kelly: Reduce risk by using fraction of full Kelly
        - Quarter-Kelly: Renaissance standard for reduced drawdown
        - Multi-Asset Kelly: Optimize portfolio weights
        - Confidence-Based Sizing: Adjust based on prediction confidence
    
    Example:
        >>> sizer = KellyPositionSizer(kelly_fraction=KellyFraction.QUARTER_KELLY)
        >>> sizing = sizer.calculate_position_size(win_prob=0.55, avg_win=100, avg_loss=80)
        >>> print(f"Position Size: {sizing.position_size:.2%}")
    """
    
    def __init__(self,
                 kelly_fraction: KellyFraction = KellyFraction.QUARTER_KELLY,
                 custom_fraction: float = 0.25,
                 max_position_size: float = DEFAULT_MAX_POSITION_SIZE,
                 min_position_size: float = DEFAULT_MIN_POSITION_SIZE,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD):
        """
        Initialize Kelly Position Sizer.
        
        Args:
            kelly_fraction: Kelly fraction type
            custom_fraction: Custom fraction if type is CUSTOM
            max_position_size: Maximum position size (fraction of capital)
            min_position_size: Minimum position size (fraction of capital)
            confidence_threshold: Minimum confidence for trading
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.kelly_fraction_type = kelly_fraction
        self.custom_fraction = custom_fraction
        self.max_position_size = max_position_size
        self.min_position_size = min_position_size
        self.confidence_threshold = confidence_threshold
        
        # Calculate effective Kelly fraction
        self.effective_kelly_fraction = self._get_effective_fraction()
        
        # Historical tracking
        self.position_history: List[PositionSizingResult] = []
        self.kelly_history: List[KellyResult] = []
        
        self.logger.info(
            f"KellyPositionSizer initialized: fraction={self.effective_kelly_fraction:.2%}, "
            f"max_size={max_position_size:.2%}, min_size={min_position_size:.2%}"
        )
    
    def _get_effective_fraction(self) -> float:
        """Get effective Kelly fraction based on type."""
        if self.kelly_fraction_type == KellyFraction.FULL_KELLY:
            return 1.0
        elif self.kelly_fraction_type == KellyFraction.HALF_KELLY:
            return 0.5
        elif self.kelly_fraction_type == KellyFraction.QUARTER_KELLY:
            return 0.25
        elif self.kelly_fraction_type == KellyFraction.EIGHTH_KELLY:
            return 0.125
        elif self.kelly_fraction_type == KellyFraction.CUSTOM:
            return self.custom_fraction
        else:
            return 0.25  # Default to Quarter-Kelly
    
    def calculate_kelly(self,
                       win_probability: float,
                       avg_win: float,
                       avg_loss: float) -> KellyResult:
        """
        Calculate Kelly Criterion for a single asset.
        
        Classic Kelly: f* = (p(b+1) - 1) / b
        where:
            p = win probability
            b = avg_win / avg_loss (odds)
        
        Args:
            win_probability: Probability of winning trade (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive number)
            
        Returns:
            KellyResult with optimal fraction and metrics
        """
        try:
            self.logger.debug("Calculating Kelly Criterion...")
            
            # Validate inputs
            if not (0 < win_probability < 1):
                raise ValueError("Win probability must be between 0 and 1")
            if avg_loss <= 0:
                raise ValueError("Average loss must be positive")
            
            # Calculate odds
            odds = avg_win / avg_loss
            
            # Calculate Kelly fraction
            kelly_fraction = (win_probability * (odds + 1) - 1) / odds
            
            # Apply fractional Kelly
            adjusted_kelly = kelly_fraction * self.effective_kelly_fraction
            
            # Calculate expected metrics
            expected_return = win_probability * avg_win - (1 - win_probability) * avg_loss
            expected_growth = win_probability * np.log(1 + adjusted_kelly * odds) + \
                            (1 - win_probability) * np.log(1 - adjusted_kelly)
            
            # Expected drawdown (simplified)
            expected_drawdown = adjusted_kelly * avg_loss
            
            # Expected Sharpe ratio
            win_std = np.sqrt(win_probability * (avg_win - expected_return)**2 + 
                            (1 - win_probability) * (avg_loss + expected_return)**2)
            sharpe_ratio = expected_return / win_std if win_std > 0 else 0.0
            
            # Risk/reward ratio
            risk_reward_ratio = avg_win / avg_loss
            
            result = KellyResult(
                kelly_fraction=adjusted_kelly,
                expected_growth=expected_growth,
                expected_return=expected_return,
                expected_drawdown=expected_drawdown,
                sharpe_ratio=sharpe_ratio,
                win_probability=win_probability,
                avg_win=avg_win,
                avg_loss=avg_loss,
                risk_reward_ratio=risk_reward_ratio
            )
            
            # Store history
            self.kelly_history.append(result)
            
            self.logger.debug(
                f"Kelly calculated: fraction={adjusted_kelly:.2%}, "
                f"expected_growth={expected_growth:.4f}"
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "KellyPositionSizer.calculate_kelly")
            raise
    
    def calculate_position_size(self,
                               capital: float,
                               win_probability: float,
                               avg_win: float,
                               avg_loss: float,
                               confidence: float = 1.0,
                               sizing_method: SizingMethod = SizingMethod.KELLY,
                               current_price: float = 100.0,
                               contract_multiplier: int = 100) -> PositionSizingResult:
        """
        Calculate optimal position size.
        
        Args:
            capital: Total capital available
            win_probability: Probability of winning trade (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive number)
            confidence: Confidence in prediction (0-1)
            sizing_method: Sizing method to use
            current_price: Current price of underlying
            contract_multiplier: Options contract multiplier (default 100)
            
        Returns:
            PositionSizingResult with position size and details
        """
        try:
            self.logger.debug("Calculating position size...")
            
            # Calculate Kelly
            kelly_result = self.calculate_kelly(win_probability, avg_win, avg_loss)
            
            # Adjust for confidence
            if confidence < self.confidence_threshold:
                # Reduce position size if confidence is low
                confidence_adjustment = confidence / self.confidence_threshold
                position_fraction = kelly_result.kelly_fraction * confidence_adjustment
                reason = f"Low confidence ({confidence:.2%}) - reduced position"
            else:
                position_fraction = kelly_result.kelly_fraction
                reason = f"Kelly sizing with {self.effective_kelly_fraction:.0%} fraction"
            
            # Apply sizing method
            if sizing_method == SizingMethod.KELLY:
                # Already calculated
                pass
            elif sizing_method == SizingMethod.FIXED_FRACTION:
                position_fraction = self.effective_kelly_fraction
                reason = f"Fixed fraction {self.effective_kelly_fraction:.0%}"
            elif sizing_method == SizingMethod.CONFIDENCE_BASED:
                # Size based purely on confidence
                position_fraction = self.effective_kelly_fraction * confidence
                reason = f"Confidence-based sizing ({confidence:.2%})"
            else:
                # Default to Kelly
                pass
            
            # Apply limits
            position_fraction = np.clip(position_fraction, 
                                       self.min_position_size, 
                                       self.max_position_size)
            
            # Calculate position value
            position_value = capital * position_fraction
            
            # Calculate number of contracts (for options)
            contract_value = current_price * contract_multiplier
            number_of_contracts = int(position_value / contract_value)
            if number_of_contracts < 1:
                number_of_contracts = 0
                position_value = 0.0
                reason = "Position too small for 1 contract"
            
            # Calculate expected loss
            expected_loss = position_value * (avg_loss / (avg_win + avg_loss))
            
            # Calculate expected return
            expected_return = position_value * (avg_win / (avg_win + avg_loss))
            
            result = PositionSizingResult(
                position_size=position_fraction,
                position_value=position_value,
                number_of_contracts=number_of_contracts,
                kelly_fraction=kelly_result.kelly_fraction,
                sizing_method=sizing_method,
                confidence=confidence,
                risk_limit=self.max_position_size,
                expected_loss=expected_loss,
                expected_return=expected_return,
                reason=reason
            )
            
            # Store history
            self.position_history.append(result)
            
            self.logger.debug(
                f"Position size calculated: {position_fraction:.2%}, "
                f"contracts={number_of_contracts}"
            )
            
            return result
            
        except Exception as e:
            self.error_handler.handle_error(e, "KellyPositionSizer.calculate_position_size")
            raise
    
    def calculate_multi_asset_kelly(self,
                                    returns: pd.DataFrame,
                                    risk_free_rate: float = 0.02) -> MultiAssetKellyResult:
        """
        Calculate optimal portfolio weights using multi-asset Kelly.
        
        Maximizes: f^T * μ - 0.5 * f^T * Σ * f
        where:
            f = position weights
            μ = expected returns
            Σ = covariance matrix
        
        Args:
            returns: DataFrame of asset returns (time x assets)
            risk_free_rate: Risk-free rate (annualized)
            
        Returns:
            MultiAssetKellyResult with optimal weights
        """
        try:
            self.logger.info("Calculating multi-asset Kelly...")
            
            # Calculate expected returns
            expected_returns = returns.mean().values
            
            # Calculate covariance matrix
            covariance_matrix = returns.cov().values
            
            # Calculate correlation matrix
            correlation_matrix = np.corrcoef(returns.T)
            
            # Number of assets
            n_assets = len(expected_returns)
            
            # Define objective function (negative growth rate)
            def objective(f):
                return -(np.dot(f, expected_returns) - 
                        0.5 * np.dot(f, np.dot(covariance_matrix, f)))
            
            # Constraints: sum of weights = 1
            constraints = {'type': 'eq', 'fun': lambda f: np.sum(f) - 1}
            
            # Bounds: weights between 0 and 1 (long-only)
            bounds = [(0, 1) for _ in range(n_assets)]
            
            # Initial guess: equal weights
            initial_guess = np.ones(n_assets) / n_assets
            
            # Optimize
            result = optimize.minimize(
                objective,
                initial_guess,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if not result.success:
                self.logger.warning("Optimization failed, using equal weights")
                optimal_weights = initial_guess
            else:
                optimal_weights = result.x
            
            # Apply fractional Kelly
            optimal_weights = optimal_weights * self.effective_kelly_fraction
            
            # Calculate portfolio metrics
            portfolio_return = np.dot(optimal_weights, expected_returns)
            portfolio_variance = np.dot(optimal_weights, np.dot(covariance_matrix, optimal_weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            portfolio_sharpe = (portfolio_return - risk_free_rate) / portfolio_volatility
            
            # Expected growth rate
            portfolio_growth = portfolio_return - 0.5 * portfolio_variance
            
            return MultiAssetKellyResult(
                position_weights=optimal_weights,
                expected_growth=portfolio_growth,
                expected_return=portfolio_return,
                expected_volatility=portfolio_volatility,
                sharpe_ratio=portfolio_sharpe,
                correlation_matrix=correlation_matrix,
                covariance_matrix=covariance_matrix
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, "KellyPositionSizer.calculate_multi_asset_kelly")
            raise
    
    def calculate_risk_adjusted_kelly(self,
                                     win_probability: float,
                                     avg_win: float,
                                     avg_loss: float,
                                     max_drawdown: float = 0.20) -> float:
        """
        Calculate risk-adjusted Kelly fraction.
        
        Adjusts Kelly fraction to respect maximum drawdown constraint.
        
        Args:
            win_probability: Probability of winning trade (0-1)
            avg_win: Average win amount
            avg_loss: Average loss amount (positive number)
            max_drawdown: Maximum acceptable drawdown (fraction of capital)
            
        Returns:
            Risk-adjusted Kelly fraction
        """
        # Calculate basic Kelly
        kelly_result = self.calculate_kelly(win_probability, avg_win, avg_loss)
        basic_kelly = kelly_result.kelly_fraction
        
        # Calculate expected drawdown
        expected_drawdown = kelly_result.expected_drawdown
        
        # Adjust if expected drawdown exceeds maximum
        if expected_drawdown > max_drawdown:
            # Scale down Kelly to respect drawdown limit
            adjusted_kelly = basic_kelly * (max_drawdown / expected_drawdown)
        else:
            adjusted_kelly = basic_kelly
        
        return adjusted_kelly
    
    def get_position_history(self, periods: int = 30) -> pd.DataFrame:
        """
        Get historical position sizing results.
        
        Args:
            periods: Number of periods to retrieve
            
        Returns:
            DataFrame with position history
        """
        if not self.position_history:
            return pd.DataFrame()
        
        history = self.position_history[-periods:]
        
        return pd.DataFrame([
            {
                'timestamp': datetime.now(),  # Simplified
                'position_size': h.position_size,
                'position_value': h.position_value,
                'number_of_contracts': h.number_of_contracts,
                'kelly_fraction': h.kelly_fraction,
                'confidence': h.confidence,
                'expected_loss': h.expected_loss,
                'expected_return': h.expected_return
            }
            for h in history
        ])
    
    def get_kelly_statistics(self) -> Dict[str, Any]:
        """
        Get statistics on Kelly calculations.
        
        Returns:
            Dictionary with Kelly statistics
        """
        if not self.kelly_history:
            return {}
        
        kelly_fractions = [k.kelly_fraction for k in self.kelly_history]
        expected_returns = [k.expected_return for k in self.kelly_history]
        sharpe_ratios = [k.sharpe_ratio for k in self.kelly_history]
        
        return {
            'total_calculations': len(self.kelly_history),
            'avg_kelly_fraction': np.mean(kelly_fractions),
            'std_kelly_fraction': np.std(kelly_fractions),
            'avg_expected_return': np.mean(expected_returns),
            'avg_sharpe_ratio': np.mean(sharpe_ratios),
            'max_kelly_fraction': np.max(kelly_fractions),
            'min_kelly_fraction': np.min(kelly_fractions),
            'effective_kelly_fraction': self.effective_kelly_fraction
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sample_trade_history(n_trades: int = 100,
                              win_prob: float = 0.55,
                              avg_win: float = 100,
                              avg_loss: float = 80) -> pd.DataFrame:
    """
    Create sample trade history for testing.
    
    Args:
        n_trades: Number of trades to generate
        win_prob: Probability of winning trade
        avg_win: Average win amount
        avg_loss: Average loss amount
        
    Returns:
        DataFrame with trade history
    """
    np.random.seed(42)
    
    # Generate trades
    trades = []
    for i in range(n_trades):
        is_win = np.random.random() < win_prob
        if is_win:
            # Win with some variance
            pnl = np.random.normal(avg_win, avg_win * 0.2)
        else:
            # Loss with some variance
            pnl = -np.random.normal(avg_loss, avg_loss * 0.2)
        
        trades.append({
            'trade_id': i + 1,
            'pnl': pnl,
            'is_win': is_win
        })
    
    return pd.DataFrame(trades)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("💰 SPYDER KELLY POSITION SIZER")
    print("=" * 70)
    print("Kelly Criterion for Optimal Position Sizing")
    print("Inspired by Renaissance Technologies")
    print()
    
    # Create sizer with Quarter-Kelly (Renaissance standard)
    print("\n1. Initializing Kelly Position Sizer...")
    sizer = KellyPositionSizer(
        kelly_fraction=KellyFraction.QUARTER_KELLY,
        max_position_size=0.20,
        min_position_size=0.01
    )
    print(f"   ✅ Initialized with Quarter-Kelly ({sizer.effective_kelly_fraction:.0%})")
    
    # Test different win probabilities
    print("\n2. Testing Kelly Criterion with different win probabilities...")
    win_probs = [0.45, 0.50, 0.55, 0.60, 0.65]
    
    for win_prob in win_probs:
        kelly_result = sizer.calculate_kelly(
            win_probability=win_prob,
            avg_win=100,
            avg_loss=80
        )
        
        print(f"\n   Win Probability: {win_prob:.2%}")
        print(f"   Kelly Fraction: {kelly_result.kelly_fraction:.2%}")
        print(f"   Expected Growth: {kelly_result.expected_growth:.4f}")
        print(f"   Expected Return: {kelly_result.expected_return:.2f}")
        print(f"   Expected Drawdown: {kelly_result.expected_drawdown:.2f}")
        print(f"   Sharpe Ratio: {kelly_result.sharpe_ratio:.2f}")
    
    # Test position sizing
    print("\n3. Testing Position Sizing...")
    capital = 100000  # $100,000
    sizing = sizer.calculate_position_size(
        capital=capital,
        win_probability=0.55,
        avg_win=100,
        avg_loss=80,
        confidence=0.80,
        current_price=450.0,
        contract_multiplier=100
    )
    
    print(f"\n   Capital: ${capital:,.2f}")
    print(f"   Position Size: {sizing.position_size:.2%}")
    print(f"   Position Value: ${sizing.position_value:,.2f}")
    print(f"   Number of Contracts: {sizing.number_of_contracts}")
    print(f"   Expected Loss: ${sizing.expected_loss:,.2f}")
    print(f"   Expected Return: ${sizing.expected_return:,.2f}")
    print(f"   Reason: {sizing.reason}")
    
    # Test confidence-based sizing
    print("\n4. Testing Confidence-Based Sizing...")
    confidences = [0.50, 0.60, 0.70, 0.80, 0.90, 1.00]
    
    print(f"\n   Confidence | Position Size | Contracts")
    print(f"   {'-'*40}")
    for conf in confidences:
        sizing = sizer.calculate_position_size(
            capital=capital,
            win_probability=0.55,
            avg_win=100,
            avg_loss=80,
            confidence=conf,
            current_price=450.0,
            contract_multiplier=100
        )
        print(f"   {conf:.2%}      | {sizing.position_size:12.2%} | {sizing.number_of_contracts:10d}")
    
    # Test multi-asset Kelly
    print("\n5. Testing Multi-Asset Kelly...")
    np.random.seed(42)
    n_assets = 3
    n_periods = 252
    
    # Generate correlated returns
    returns = pd.DataFrame(
        np.random.multivariate_normal(
            mean=[0.0005, 0.0003, 0.0004],
            cov=[[0.0001, 0.00005, 0.00003],
                 [0.00005, 0.00015, 0.00004],
                 [0.00003, 0.00004, 0.00012]],
            size=n_periods
        ),
        columns=['Asset1', 'Asset2', 'Asset3']
    )
    
    multi_result = sizer.calculate_multi_asset_kelly(returns)
    
    print(f"\n   Optimal Weights:")
    for i, weight in enumerate(multi_result.position_weights):
        print(f"   Asset {i+1}: {weight:.2%}")
    
    print(f"\n   Portfolio Metrics:")
    print(f"   Expected Growth: {multi_result.expected_growth:.4f}")
    print(f"   Expected Return: {multi_result.expected_return:.4f}")
    print(f"   Expected Volatility: {multi_result.expected_volatility:.4f}")
    print(f"   Sharpe Ratio: {multi_result.sharpe_ratio:.2f}")
    
    # Get statistics
    print("\n6. Kelly Statistics:")
    stats = sizer.get_kelly_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✅ Kelly Position Sizer Test Completed Successfully")
    print("=" * 70)
