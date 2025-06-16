#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE05_PortfolioAllocator.py
Group: E (Risk Management)
Purpose: Portfolio allocation across strategies

Description:
    This module manages capital allocation across multiple trading strategies
    using various optimization techniques including mean-variance optimization,
    risk parity, and dynamic allocation based on performance and market conditions.

Author: Mohamed Talib
Date: 2025-05-29
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
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
from SpyderE_Risk.SpyderE06_RiskMetrics import RiskMetricsCalculator

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Allocation constraints
MIN_ALLOCATION = 0.05      # 5% minimum allocation per strategy
MAX_ALLOCATION = 0.40      # 40% maximum allocation per strategy
CASH_RESERVE = 0.10        # 10% cash reserve

# Rebalancing parameters
REBALANCE_THRESHOLD = 0.05  # 5% deviation triggers rebalance
MIN_REBALANCE_INTERVAL = 7  # Minimum days between rebalances
TRANSACTION_COST = 0.001    # 0.1% transaction cost

# Performance windows
SHORT_WINDOW = 20          # 20 days for short-term performance
MEDIUM_WINDOW = 60         # 60 days for medium-term
LONG_WINDOW = 252          # 252 days for long-term

# Risk parameters
TARGET_PORTFOLIO_VOL = 0.15  # 15% target volatility
MAX_CORRELATION = 0.80       # Maximum correlation between strategies
MIN_SHARPE_RATIO = 0.5      # Minimum acceptable Sharpe ratio

# ==============================================================================
# ENUMS
# ==============================================================================
class AllocationMethod(Enum):
    """Portfolio allocation methods"""
    EQUAL_WEIGHT = auto()
    RISK_PARITY = auto()
    MEAN_VARIANCE = auto()
    MAXIMUM_SHARPE = auto()
    MINIMUM_VARIANCE = auto()
    KELLY_OPTIMAL = auto()
    DYNAMIC_ADAPTIVE = auto()

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    SCHEDULED = auto()
    THRESHOLD_BREACH = auto()
    RISK_LIMIT = auto()
    STRATEGY_CHANGE = auto()
    MANUAL = auto()
    DRAWDOWN = auto()

class StrategyStatus(Enum):
    """Strategy operational status"""
    ACTIVE = auto()
    PAUSED = auto()
    RAMPING_UP = auto()
    RAMPING_DOWN = auto()
    STOPPED = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyPerformance:
    """Strategy performance metrics"""
    strategy_name: str
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    trades_count: int
    current_positions: int
    last_updated: datetime

@dataclass
class AllocationTarget:
    """Target allocation for a strategy"""
    strategy_name: str
    target_weight: float
    current_weight: float
    deviation: float
    rebalance_amount: float
    priority: int
    constraints: Dict[str, float]

@dataclass
class PortfolioAllocation:
    """Complete portfolio allocation"""
    timestamp: datetime
    method: AllocationMethod
    allocations: Dict[str, float]  # strategy -> weight
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    risk_contribution: Dict[str, float]
    confidence_score: float
    notes: List[str] = field(default_factory=list)

@dataclass
class RebalanceAction:
    """Rebalancing action"""
    action_id: str
    timestamp: datetime
    reason: RebalanceReason
    old_allocation: Dict[str, float]
    new_allocation: Dict[str, float]
    trades_required: List[Dict[str, Any]]
    estimated_cost: float
    executed: bool = False

# ==============================================================================
# PORTFOLIO ALLOCATOR CLASS
# ==============================================================================
class PortfolioAllocator:
    """
    Manages portfolio allocation across trading strategies.
    
    Implements multiple allocation methods and dynamic rebalancing
    based on performance, risk metrics, and market conditions.
    """
    
    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile
    ):
        """
        Initialize portfolio allocator.
        
        Args:
            event_manager: Event manager for notifications
            risk_profile: Risk profile configuration
        """
        self.event_manager = event_manager
        self.risk_profile = risk_profile
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Components
        self.risk_calculator = RiskMetricsCalculator()
        
        # Strategy tracking
        self.strategies: Dict[str, StrategyStatus] = {}
        self.performance: Dict[str, StrategyPerformance] = {}
        self.returns_history: Dict[str, pd.Series] = {}
        
        # Allocation state
        self.current_allocation: Optional[PortfolioAllocation] = None
        self.target_allocation: Optional[PortfolioAllocation] = None
        self.last_rebalance: Optional[datetime] = None
        
        # Configuration
        self.default_method = AllocationMethod.RISK_PARITY
        self.enable_dynamic_allocation = True
        self.use_regime_adjustment = True
        
        # History tracking
        self.allocation_history: List[PortfolioAllocation] = []
        self.rebalance_history: List[RebalanceAction] = []
        
        # Register event handlers
        self._register_event_handlers()
        
        self.logger.info("PortfolioAllocator initialized")
    
    # ==========================================================================
    # STRATEGY MANAGEMENT
    # ==========================================================================
    def add_strategy(
        self,
        strategy_name: str,
        initial_allocation: float = 0.0,
        status: StrategyStatus = StrategyStatus.ACTIVE
    ) -> None:
        """
        Add a strategy to the portfolio.
        
        Args:
            strategy_name: Strategy identifier
            initial_allocation: Initial allocation weight
            status: Strategy status
        """
        self.strategies[strategy_name] = status
        self.returns_history[strategy_name] = pd.Series(dtype=float)
        
        # Initialize performance
        self.performance[strategy_name] = StrategyPerformance(
            strategy_name=strategy_name,
            total_return=0.0,
            annualized_return=0.0,
            volatility=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            trades_count=0,
            current_positions=0,
            last_updated=datetime.now()
        )
        
        self.logger.info(f"Added strategy {strategy_name} with status {status.name}")
    
    def update_strategy_performance(
        self,
        strategy_name: str,
        daily_return: float,
        metrics: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Update strategy performance metrics.
        
        Args:
            strategy_name: Strategy identifier
            daily_return: Daily return value
            metrics: Additional performance metrics
        """
        if strategy_name not in self.strategies:
            return
        
        # Update returns history
        self.returns_history[strategy_name] = pd.concat([
            self.returns_history[strategy_name],
            pd.Series([daily_return], index=[datetime.now().date()])
        ])
        
        # Limit history
        if len(self.returns_history[strategy_name]) > LONG_WINDOW:
            self.returns_history[strategy_name] = self.returns_history[strategy_name].iloc[-LONG_WINDOW:]
        
        # Update performance metrics
        self._update_performance_metrics(strategy_name, metrics)
    
    # ==========================================================================
    # ALLOCATION CALCULATION
    # ==========================================================================
    def calculate_allocation(
        self,
        method: Optional[AllocationMethod] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> PortfolioAllocation:
        """
        Calculate optimal portfolio allocation.
        
        Args:
            method: Allocation method to use
            constraints: Additional constraints
            
        Returns:
            Portfolio allocation
        """
        method = method or self.default_method
        
        try:
            # Get active strategies
            active_strategies = [
                s for s, status in self.strategies.items()
                if status == StrategyStatus.ACTIVE
            ]
            
            if not active_strategies:
                return self._get_cash_allocation()
            
            # Calculate allocation based on method
            if method == AllocationMethod.EQUAL_WEIGHT:
                allocation = self._equal_weight_allocation(active_strategies)
                
            elif method == AllocationMethod.RISK_PARITY:
                allocation = self._risk_parity_allocation(active_strategies)
                
            elif method == AllocationMethod.MEAN_VARIANCE:
                allocation = self._mean_variance_allocation(active_strategies)
                
            elif method == AllocationMethod.MAXIMUM_SHARPE:
                allocation = self._maximum_sharpe_allocation(active_strategies)
                
            elif method == AllocationMethod.MINIMUM_VARIANCE:
                allocation = self._minimum_variance_allocation(active_strategies)
                
            elif method == AllocationMethod.KELLY_OPTIMAL:
                allocation = self._kelly_optimal_allocation(active_strategies)
                
            elif method == AllocationMethod.DYNAMIC_ADAPTIVE:
                allocation = self._dynamic_adaptive_allocation(active_strategies)
                
            else:
                allocation = self._equal_weight_allocation(active_strategies)
            
            # Apply constraints
            if constraints:
                allocation = self._apply_constraints(allocation, constraints)
            
            # Apply regime adjustments
            if self.use_regime_adjustment:
                allocation = self._apply_regime_adjustment(allocation)
            
            # Store allocation
            self.target_allocation = allocation
            self.allocation_history.append(allocation)
            
            # Emit allocation event
            self._emit_allocation_event(allocation)
            
            return allocation
            
        except Exception as e:
            self.logger.error(f"Error calculating allocation: {e}")
            self.error_handler.handle_error(e, "calculate_allocation")
            return self._get_safe_allocation(active_strategies)
    
    # ==========================================================================
    # ALLOCATION METHODS
    # ==========================================================================
    def _equal_weight_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Equal weight allocation"""
        n = len(strategies)
        weight = (1 - CASH_RESERVE) / n
        
        allocations = {s: weight for s in strategies}
        allocations['cash'] = CASH_RESERVE
        
        # Calculate expected metrics
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.EQUAL_WEIGHT,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.7,
            notes=["Simple equal weight allocation"]
        )
    
    def _risk_parity_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Risk parity allocation"""
        if len(strategies) == 1:
            return self._equal_weight_allocation(strategies)
        
        # Get returns and covariance
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty or len(returns_df) < 30:
            return self._equal_weight_allocation(strategies)
        
        cov_matrix = returns_df.cov() * 252  # Annualized
        
        # Risk parity optimization
        n = len(strategies)
        x0 = np.array([1/n] * n)
        
        def risk_parity_objective(weights):
            """Minimize difference in risk contributions"""
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            marginal_contrib = cov_matrix @ weights
            contrib = weights * marginal_contrib / portfolio_vol
            
            # Equal risk contribution target
            target_contrib = portfolio_vol / n
            
            return np.sum((contrib - target_contrib) ** 2)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - (1 - CASH_RESERVE)}
        ]
        
        # Optimize
        result = minimize(
            risk_parity_objective,
            x0,
            method='SLSQP',
            constraints=constraints,
            bounds=[(MIN_ALLOCATION, MAX_ALLOCATION)] * n
        )
        
        if result.success:
            weights = result.x
        else:
            self.logger.warning("Risk parity optimization failed, using equal weight")
            weights = x0 * (1 - CASH_RESERVE)
        
        # Create allocation
        allocations = {s: w for s, w in zip(strategies, weights)}
        allocations['cash'] = CASH_RESERVE
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.RISK_PARITY,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.8,
            notes=["Risk parity - equal risk contribution"]
        )
    
    def _mean_variance_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Mean-variance optimization"""
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty or len(returns_df) < 60:
            return self._equal_weight_allocation(strategies)
        
        # Calculate expected returns and covariance
        expected_returns = returns_df.mean() * 252
        cov_matrix = returns_df.cov() * 252
        
        # Target return (use average of strategy returns)
        target_return = expected_returns.mean()
        
        n = len(strategies)
        x0 = np.array([1/n] * n)
        
        def portfolio_variance(weights):
            return weights @ cov_matrix @ weights
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - (1 - CASH_RESERVE)},
            {'type': 'ineq', 'fun': lambda x: x @ expected_returns - target_return}
        ]
        
        # Optimize
        result = minimize(
            portfolio_variance,
            x0,
            method='SLSQP',
            constraints=constraints,
            bounds=[(MIN_ALLOCATION, MAX_ALLOCATION)] * n
        )
        
        if result.success:
            weights = result.x
        else:
            self.logger.warning("Mean-variance optimization failed")
            return self._risk_parity_allocation(strategies)
        
        # Create allocation
        allocations = {s: w for s, w in zip(strategies, weights)}
        allocations['cash'] = CASH_RESERVE
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.MEAN_VARIANCE,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.85,
            notes=[f"Target return: {target_return:.1%}"]
        )
    
    def _maximum_sharpe_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Maximum Sharpe ratio optimization"""
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty or len(returns_df) < 60:
            return self._equal_weight_allocation(strategies)
        
        # Calculate expected returns and covariance
        expected_returns = returns_df.mean() * 252
        cov_matrix = returns_df.cov() * 252
        risk_free_rate = 0.02  # 2% risk-free rate
        
        n = len(strategies)
        x0 = np.array([1/n] * n)
        
        def negative_sharpe(weights):
            """Negative Sharpe ratio for minimization"""
            portfolio_return = weights @ expected_returns
            portfolio_vol = np.sqrt(weights @ cov_matrix @ weights)
            if portfolio_vol == 0:
                return 0
            return -(portfolio_return - risk_free_rate) / portfolio_vol
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - (1 - CASH_RESERVE)}
        ]
        
        # Optimize
        result = minimize(
            negative_sharpe,
            x0,
            method='SLSQP',
            constraints=constraints,
            bounds=[(MIN_ALLOCATION, MAX_ALLOCATION)] * n
        )
        
        if result.success:
            weights = result.x
        else:
            return self._mean_variance_allocation(strategies)
        
        # Create allocation
        allocations = {s: w for s, w in zip(strategies, weights)}
        allocations['cash'] = CASH_RESERVE
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.MAXIMUM_SHARPE,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.9,
            notes=["Maximized Sharpe ratio"]
        )
    
    def _minimum_variance_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Minimum variance portfolio"""
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty or len(returns_df) < 30:
            return self._equal_weight_allocation(strategies)
        
        cov_matrix = returns_df.cov() * 252
        n = len(strategies)
        x0 = np.array([1/n] * n)
        
        def portfolio_variance(weights):
            return weights @ cov_matrix @ weights
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - (1 - CASH_RESERVE)}
        ]
        
        # Optimize
        result = minimize(
            portfolio_variance,
            x0,
            method='SLSQP',
            constraints=constraints,
            bounds=[(MIN_ALLOCATION, MAX_ALLOCATION)] * n
        )
        
        if result.success:
            weights = result.x
        else:
            return self._equal_weight_allocation(strategies)
        
        # Create allocation
        allocations = {s: w for s, w in zip(strategies, weights)}
        allocations['cash'] = CASH_RESERVE
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.MINIMUM_VARIANCE,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.85,
            notes=["Minimum variance portfolio"]
        )
    
    def _kelly_optimal_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Kelly criterion based allocation"""
        allocations = {}
        
        for strategy in strategies:
            perf = self.performance.get(strategy)
            if not perf or perf.trades_count < 20:
                # Not enough data, use minimum allocation
                allocations[strategy] = MIN_ALLOCATION
                continue
            
            # Kelly formula: f = (p*b - q) / b
            p = perf.win_rate
            q = 1 - p
            b = perf.profit_factor  # Win/loss ratio
            
            if b > 0:
                kelly_fraction = (p * b - q) / b
                # Use fractional Kelly (25%)
                kelly_fraction *= 0.25
                
                # Apply bounds
                kelly_fraction = max(MIN_ALLOCATION, min(kelly_fraction, MAX_ALLOCATION))
            else:
                kelly_fraction = MIN_ALLOCATION
            
            allocations[strategy] = kelly_fraction
        
        # Normalize to sum to 1 - cash reserve
        total = sum(allocations.values())
        if total > 0:
            scale = (1 - CASH_RESERVE) / total
            allocations = {s: w * scale for s, w in allocations.items()}
        
        allocations['cash'] = CASH_RESERVE
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.KELLY_OPTIMAL,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.75,
            notes=["Kelly criterion with 25% fraction"]
        )
    
    def _dynamic_adaptive_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Dynamic allocation based on recent performance and regime"""
        # Start with risk parity base
        base_allocation = self._risk_parity_allocation(strategies)
        allocations = base_allocation.allocations.copy()
        
        # Adjust based on recent performance
        for strategy in strategies:
            if strategy not in self.returns_history:
                continue
                
            returns = self.returns_history[strategy]
            if len(returns) < SHORT_WINDOW:
                continue
            
            # Calculate momentum
            short_return = returns.iloc[-SHORT_WINDOW:].mean() * 252
            medium_return = returns.iloc[-MEDIUM_WINDOW:].mean() * 252 if len(returns) >= MEDIUM_WINDOW else short_return
            
            # Momentum adjustment
            if short_return > medium_return * 1.2:  # Positive momentum
                allocations[strategy] *= 1.2
            elif short_return < medium_return * 0.8:  # Negative momentum
                allocations[strategy] *= 0.8
            
            # Drawdown adjustment
            perf = self.performance.get(strategy)
            if perf and perf.max_drawdown > 0.10:  # 10% drawdown
                allocations[strategy] *= (1 - perf.max_drawdown)
        
        # Re-normalize
        total = sum(v for k, v in allocations.items() if k != 'cash')
        if total > 0:
            scale = (1 - CASH_RESERVE) / total
            for strategy in strategies:
                if strategy in allocations:
                    allocations[strategy] *= scale
        
        # Apply bounds
        for strategy in strategies:
            if strategy in allocations:
                allocations[strategy] = max(MIN_ALLOCATION, min(allocations[strategy], MAX_ALLOCATION))
        
        expected_return, expected_vol, expected_sharpe = self._calculate_portfolio_metrics(allocations)
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.DYNAMIC_ADAPTIVE,
            allocations=allocations,
            expected_return=expected_return,
            expected_volatility=expected_vol,
            expected_sharpe=expected_sharpe,
            risk_contribution=self._calculate_risk_contribution(allocations),
            confidence_score=0.8,
            notes=["Dynamic adjustment based on momentum and drawdown"]
        )
    
    # ==========================================================================
    # REBALANCING
    # ==========================================================================
    def check_rebalance_needed(self) -> Tuple[bool, List[AllocationTarget]]:
        """
        Check if portfolio rebalancing is needed.
        
        Returns:
            Tuple of (needs_rebalance, list of targets)
        """
        if not self.current_allocation or not self.target_allocation:
            return False, []
        
        # Check time since last rebalance
        if self.last_rebalance:
            days_since = (datetime.now() - self.last_rebalance).days
            if days_since < MIN_REBALANCE_INTERVAL:
                return False, []
        
        targets = []
        needs_rebalance = False
        
        for strategy, target_weight in self.target_allocation.allocations.items():
            current_weight = self.current_allocation.allocations.get(strategy, 0)
            deviation = abs(target_weight - current_weight)
            
            if deviation > REBALANCE_THRESHOLD:
                needs_rebalance = True
                
            target = AllocationTarget(
                strategy_name=strategy,
                target_weight=target_weight,
                current_weight=current_weight,
                deviation=deviation,
                rebalance_amount=target_weight - current_weight,
                priority=1 if deviation > REBALANCE_THRESHOLD * 2 else 2,
                constraints={'min': MIN_ALLOCATION, 'max': MAX_ALLOCATION}
            )
            targets.append(target)
        
        return needs_rebalance, targets
    
    def execute_rebalance(
        self,
        targets: List[AllocationTarget],
        reason: RebalanceReason = RebalanceReason.THRESHOLD_BREACH
    ) -> RebalanceAction:
        """
        Execute portfolio rebalancing.
        
        Args:
            targets: List of allocation targets
            reason: Reason for rebalancing
            
        Returns:
            Rebalance action
        """
        # Create rebalance action
        action = RebalanceAction(
            action_id=f"RB_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            reason=reason,
            old_allocation=self.current_allocation.allocations if self.current_allocation else {},
            new_allocation={t.strategy_name: t.target_weight for t in targets},
            trades_required=self._calculate_rebalance_trades(targets),
            estimated_cost=self._estimate_rebalance_cost(targets)
        )
        
        # Update current allocation
        self.current_allocation = self.target_allocation
        self.last_rebalance = datetime.now()
        
        # Record action
        self.rebalance_history.append(action)
        action.executed = True
        
        # Emit rebalance event
        self._emit_rebalance_event(action)
        
        self.logger.info(f"Executed rebalance: {action.action_id}")
        
        return action
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _get_returns_dataframe(self, strategies: List[str]) -> pd.DataFrame:
        """Get returns DataFrame for strategies"""
        returns_dict = {}
        
        for strategy in strategies:
            if strategy in self.returns_history and len(self.returns_history[strategy]) > 0:
                returns_dict[strategy] = self.returns_history[strategy]
        
        if not returns_dict:
            return pd.DataFrame()
        
        # Align all series to common dates
        df = pd.DataFrame(returns_dict)
        return df.dropna()
    
    def _calculate_portfolio_metrics(
        self,
        allocations: Dict[str, float]
    ) -> Tuple[float, float, float]:
        """Calculate expected portfolio metrics"""
        strategies = [s for s in allocations.keys() if s != 'cash']
        
        if not strategies:
            return 0.0, 0.0, 0.0
        
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty:
            # Use historical performance data
            expected_return = sum(
                allocations.get(s, 0) * self.performance.get(s, StrategyPerformance(
                    strategy_name=s, total_return=0, annualized_return=0,
                    volatility=0.15, sharpe_ratio=0, max_drawdown=0,
                    win_rate=0, profit_factor=0, trades_count=0,
                    current_positions=0, last_updated=datetime.now()
                )).annualized_return
                for s in strategies
            )
            expected_vol = 0.15  # Default
            expected_sharpe = expected_return / expected_vol if expected_vol > 0 else 0
            
            return expected_return, expected_vol, expected_sharpe
        
        # Calculate from returns data
        weights = np.array([allocations.get(s, 0) for s in returns_df.columns])
        
        # Expected return
        expected_returns = returns_df.mean() * 252
        expected_return = weights @ expected_returns
        
        # Expected volatility
        cov_matrix = returns_df.cov() * 252
        expected_vol = np.sqrt(weights @ cov_matrix @ weights)
        
        # Expected Sharpe
        risk_free_rate = 0.02
        expected_sharpe = (expected_return - risk_free_rate) / expected_vol if expected_vol > 0 else 0
        
        return float(expected_return), float(expected_vol), float(expected_sharpe)
    
    def _calculate_risk_contribution(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Calculate risk contribution by strategy"""
        strategies = [s for s in allocations.keys() if s != 'cash']
        
        if not strategies:
            return {}
        
        returns_df = self._get_returns_dataframe(strategies)
        if returns_df.empty or len(strategies) == 1:
            # Equal risk contribution assumption
            return {s: allocations[s] for s in strategies}
        
        weights = np.array([allocations.get(s, 0) for s in returns_df.columns])
        cov_matrix = returns_df.cov().values * 252
        
        # Portfolio variance
        portfolio_var = weights @ cov_matrix @ weights
        
        if portfolio_var == 0:
            return {s: 0 for s in strategies}
        
        # Marginal contributions
        marginal_contrib = cov_matrix @ weights
        
        # Risk contributions
        risk_contrib = weights * marginal_contrib / portfolio_var
        
        return {s: float(rc) for s, rc in zip(returns_df.columns, risk_contrib)}
    
    def _apply_constraints(
        self,
        allocation: PortfolioAllocation,
        constraints: Dict[str, Any]
    ) -> PortfolioAllocation:
        """Apply additional constraints to allocation"""
        allocations = allocation.allocations.copy()
        
        # Apply strategy-specific constraints
        for strategy, weight in allocations.items():
            if strategy == 'cash':
                continue
                
            # Min/max constraints
            min_weight = constraints.get(f'{strategy}_min', MIN_ALLOCATION)
            max_weight = constraints.get(f'{strategy}_max', MAX_ALLOCATION)
            
            allocations[strategy] = max(min_weight, min(weight, max_weight))
        
        # Re-normalize
        total = sum(v for k, v in allocations.items() if k != 'cash')
        if total > (1 - CASH_RESERVE):
            scale = (1 - CASH_RESERVE) / total
            for strategy in allocations:
                if strategy != 'cash':
                    allocations[strategy] *= scale
        
        allocation.allocations = allocations
        return allocation
    
    def _apply_regime_adjustment(self, allocation: PortfolioAllocation) -> PortfolioAllocation:
        """Apply market regime adjustments"""
        # Would implement regime detection and adjustment
        # For now, return unchanged
        return allocation
    
    def _calculate_rebalance_trades(self, targets: List[AllocationTarget]) -> List[Dict[str, Any]]:
        """Calculate trades required for rebalancing"""
        trades = []
        
        for target in targets:
            if abs(target.rebalance_amount) > 0.001:  # 0.1% threshold
                trades.append({
                    'strategy': target.strategy_name,
                    'action': 'increase' if target.rebalance_amount > 0 else 'decrease',
                    'amount': abs(target.rebalance_amount),
                    'priority': target.priority
                })
        
        return sorted(trades, key=lambda x: x['priority'])
    
    def _estimate_rebalance_cost(self, targets: List[AllocationTarget]) -> float:
        """Estimate cost of rebalancing"""
        total_turnover = sum(abs(t.rebalance_amount) for t in targets)
        return total_turnover * TRANSACTION_COST
    
    def _update_performance_metrics(self, strategy: str, metrics: Optional[Dict[str, float]]) -> None:
        """Update strategy performance metrics"""
        perf = self.performance[strategy]
        returns = self.returns_history.get(strategy, pd.Series())
        
        if len(returns) > 0:
            perf.total_return = (1 + returns).prod() - 1
            perf.annualized_return = returns.mean() * 252
            perf.volatility = returns.std() * np.sqrt(252)
            
            if perf.volatility > 0:
                perf.sharpe_ratio = (perf.annualized_return - 0.02) / perf.volatility
            
            # Calculate max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            perf.max_drawdown = abs(drawdown.min())
        
        # Update from provided metrics
        if metrics:
            perf.win_rate = metrics.get('win_rate', perf.win_rate)
            perf.profit_factor = metrics.get('profit_factor', perf.profit_factor)
            perf.trades_count = metrics.get('trades_count', perf.trades_count)
            perf.current_positions = metrics.get('positions', perf.current_positions)
        
        perf.last_updated = datetime.now()
    
    def _get_cash_allocation(self) -> PortfolioAllocation:
        """Get all-cash allocation"""
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.EQUAL_WEIGHT,
            allocations={'cash': 1.0},
            expected_return=0.0,
            expected_volatility=0.0,
            expected_sharpe=0.0,
            risk_contribution={},
            confidence_score=1.0,
            notes=["No active strategies - 100% cash"]
        )
    
    def _get_safe_allocation(self, strategies: List[str]) -> PortfolioAllocation:
        """Get safe fallback allocation"""
        # Use equal weight with larger cash reserve
        n = len(strategies)
        if n == 0:
            return self._get_cash_allocation()
        
        safe_cash_reserve = 0.3  # 30% cash
        weight = (1 - safe_cash_reserve) / n
        
        allocations = {s: weight for s in strategies}
        allocations['cash'] = safe_cash_reserve
        
        return PortfolioAllocation(
            timestamp=datetime.now(),
            method=AllocationMethod.EQUAL_WEIGHT,
            allocations=allocations,
            expected_return=0.0,
            expected_volatility=0.15,
            expected_sharpe=0.0,
            risk_contribution={s: weight for s in strategies},
            confidence_score=0.5,
            notes=["Safe allocation due to optimization error"]
        )
    
    # ==========================================================================
    # EVENT HANDLING
    # ==========================================================================
    def _register_event_handlers(self) -> None:
        """Register event handlers"""
        self.event_manager.subscribe(
            self._handle_strategy_event,
            event_filter=lambda e: e.type == EventType.STRATEGY,
            subscriber_id="portfolio_allocator"
        )
        
        self.event_manager.subscribe(
            self._handle_performance_event,
            event_filter=lambda e: e.type == EventType.PERFORMANCE,
            subscriber_id="portfolio_allocator_perf"
        )
    
    def _handle_strategy_event(self, event: Event) -> None:
        """Handle strategy events"""
        action = event.data.get('action')
        strategy = event.data.get('strategy')
        
        if action == 'started' and strategy not in self.strategies:
            self.add_strategy(strategy)
        elif action == 'stopped' and strategy in self.strategies:
            self.strategies[strategy] = StrategyStatus.STOPPED
    
    def _handle_performance_event(self, event: Event) -> None:
        """Handle performance update events"""
        strategy = event.data.get('strategy')
        daily_return = event.data.get('daily_return')
        metrics = event.data.get('metrics')
        
        if strategy and daily_return is not None:
            self.update_strategy_performance(strategy, daily_return, metrics)
    
    def _emit_allocation_event(self, allocation: PortfolioAllocation) -> None:
        """Emit allocation event"""
        self.event_manager.emit(Event(
            EventType.PORTFOLIO,
            {
                'action': 'allocation_calculated',
                'method': allocation.method.name,
                'allocations': allocation.allocations,
                'expected_return': allocation.expected_return,
                'expected_volatility': allocation.expected_volatility,
                'expected_sharpe': allocation.expected_sharpe
            }
        ))
    
    def _emit_rebalance_event(self, action: RebalanceAction) -> None:
        """Emit rebalance event"""
        self.event_manager.emit(Event(
            EventType.PORTFOLIO,
            {
                'action': 'rebalance_executed',
                'rebalance_id': action.action_id,
                'reason': action.reason.name,
                'trades': action.trades_required,
                'cost': action.estimated_cost
            }
        ))
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_current_allocation(self) -> Optional[PortfolioAllocation]:
        """Get current portfolio allocation"""
        return self.current_allocation
    
    def get_strategy_performance(self, strategy: str) -> Optional[StrategyPerformance]:
        """Get performance metrics for a strategy"""
        return self.performance.get(strategy)
    
    def get_allocation_history(self, limit: int = 100) -> List[PortfolioAllocation]:
        """Get allocation history"""
        return self.allocation_history[-limit:]
    
    def get_rebalance_history(self, limit: int = 50) -> List[RebalanceAction]:
        """Get rebalance history"""
        return self.rebalance_history[-limit:]


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test portfolio allocator
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    # Initialize
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.10,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.02
    )
    
    allocator = PortfolioAllocator(event_manager, risk_profile)
    
    # Add strategies
    strategies = ['momentum', 'mean_reversion', 'volatility', 'pairs']
    for strategy in strategies:
        allocator.add_strategy(strategy)
    
    # Simulate returns history
    np.random.seed(42)
    for i in range(100):
        for strategy in strategies:
            # Different return profiles
            if strategy == 'momentum':
                daily_return = np.random.normal(0.0005, 0.015)
            elif strategy == 'mean_reversion':
                daily_return = np.random.normal(0.0003, 0.010)
            elif strategy == 'volatility':
                daily_return = np.random.normal(0.0004, 0.020)
            else:  # pairs
                daily_return = np.random.normal(0.0002, 0.008)
            
            allocator.update_strategy_performance(strategy, daily_return)
    
    # Test different allocation methods
    print("PORTFOLIO ALLOCATION TESTS")
    print("=" * 60)
    
    methods = [
        AllocationMethod.EQUAL_WEIGHT,
        AllocationMethod.RISK_PARITY,
        AllocationMethod.MEAN_VARIANCE,
        AllocationMethod.MAXIMUM_SHARPE,
        AllocationMethod.MINIMUM_VARIANCE,
        AllocationMethod.KELLY_OPTIMAL,
        AllocationMethod.DYNAMIC_ADAPTIVE
    ]
    
    for method in methods:
        print(f"\n{method.name}:")
        allocation = allocator.calculate_allocation(method)
        
        print(f"  Expected Return: {allocation.expected_return:.1%}")
        print(f"  Expected Volatility: {allocation.expected_volatility:.1%}")
        print(f"  Expected Sharpe: {allocation.expected_sharpe:.2f}")
        print(f"  Confidence: {allocation.confidence_score:.1%}")
        
        print("\n  Allocations:")
        for strategy, weight in sorted(allocation.allocations.items()):
            if weight > 0:
                print(f"    {strategy}: {weight:.1%}")
        
        if allocation.risk_contribution:
            print("\n  Risk Contribution:")
            for strategy, contrib in sorted(allocation.risk_contribution.items()):
                print(f"    {strategy}: {contrib:.1%}")
    
    # Test rebalancing
    print("\n" + "=" * 60)
    print("REBALANCING TEST")
    
    # Set current allocation
    allocator.current_allocation = allocator.calculate_allocation(AllocationMethod.EQUAL_WEIGHT)
    
    # Calculate new target
    allocator.target_allocation = allocator.calculate_allocation(AllocationMethod.RISK_PARITY)
    
    # Check if rebalance needed
    needs_rebalance, targets = allocator.check_rebalance_needed()
    
    print(f"\nRebalance needed: {needs_rebalance}")
    if needs_rebalance:
        print("\nRebalance targets:")
        for target in targets:
            print(f"  {target.strategy_name}:")
            print(f"    Current: {target.current_weight:.1%}")
            print(f"    Target: {target.target_weight:.1%}")
            print(f"    Change: {target.rebalance_amount:+.1%}")
        
        # Execute rebalance
        action = allocator.execute_rebalance(targets)
        print(f"\nRebalance executed: {action.action_id}")
        print(f"Estimated cost: ${action.estimated_cost * 100000:.2f}")
    
    print("\n✅ Portfolio allocator test completed successfully")
