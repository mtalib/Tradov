#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderP04_CapitalAllocator.py
Group: P (Portfolio Management)
Purpose: Dynamic capital allocation across strategies using Kelly Criterion and risk parity
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 14:00:00

Description:
    This module provides intelligent capital allocation across multiple trading
    strategies using advanced portfolio optimization techniques including Kelly
    Criterion, risk parity, and machine learning-based allocation. It dynamically
    adjusts position sizes based on strategy performance, market conditions, and
    risk constraints to maximize long-term growth while controlling drawdowns.

Key Features:
    - Kelly Criterion optimization for position sizing
    - Risk parity allocation across strategies
    - Dynamic allocation based on regime detection
    - Correlation-aware portfolio construction
    - Maximum drawdown constraints
    - Fractional Kelly for conservative sizing
    - Strategy performance tracking and rebalancing
    - Capital preservation in adverse conditions
    - Multi-objective optimization (return, risk, diversification)
    - Real-time allocation adjustments
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import scipy.optimize as optimize
from scipy.stats import norm, t
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from sklearn.covariance import LedoitWolf
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderP_PortfolioMgmt.SpyderP03_CorrelationAnalyzer import CorrelationAnalyzer
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Kelly Criterion Parameters
FULL_KELLY = 1.0
HALF_KELLY = 0.5
QUARTER_KELLY = 0.25
DEFAULT_KELLY_FRACTION = 0.25  # Conservative default

# Risk Parameters
MAX_POSITION_SIZE = 0.20  # 20% max per strategy
MIN_POSITION_SIZE = 0.01  # 1% minimum
MAX_LEVERAGE = 1.0  # No leverage by default
MAX_CORRELATION = 0.8  # Max correlation between strategies
TARGET_VOLATILITY = 0.15  # 15% annual target volatility

# Allocation Constraints
MIN_STRATEGIES = 3  # Minimum active strategies for diversification
MAX_STRATEGIES = 10  # Maximum concurrent strategies
REBALANCE_THRESHOLD = 0.05  # 5% drift triggers rebalance
EMERGENCY_CASH_RESERVE = 0.10  # 10% cash reserve

# Performance Windows
LOOKBACK_DAYS = 60  # Historical data for calculations
CONFIDENCE_LEVEL = 0.95  # 95% confidence for estimates
MIN_SAMPLES = 30  # Minimum samples for statistics

# Regime-Based Adjustments
BULL_MARKET_MULTIPLIER = 1.2
BEAR_MARKET_MULTIPLIER = 0.6
HIGH_VOL_MULTIPLIER = 0.5
CRASH_MODE_ALLOCATION = 0.1  # 10% only in crash

# ==============================================================================
# ENUMS
# ==============================================================================

class AllocationMethod(Enum):
    """Capital allocation methods"""
    KELLY = "KELLY_CRITERION"
    RISK_PARITY = "RISK_PARITY"
    EQUAL_WEIGHT = "EQUAL_WEIGHT"
    MEAN_VARIANCE = "MEAN_VARIANCE"
    MIN_VARIANCE = "MINIMUM_VARIANCE"
    MAX_SHARPE = "MAXIMUM_SHARPE"
    HIERARCHICAL = "HIERARCHICAL_RISK_PARITY"
    DYNAMIC = "DYNAMIC_ADAPTIVE"

class MarketRegime(Enum):
    """Market regime classification"""
    BULL = "BULL_MARKET"
    BEAR = "BEAR_MARKET"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    CRASH = "CRASH"
    RECOVERY = "RECOVERY"

class RiskLevel(Enum):
    """Portfolio risk levels"""
    CONSERVATIVE = 1
    MODERATE = 2
    AGGRESSIVE = 3
    VERY_AGGRESSIVE = 4

class RebalanceType(Enum):
    """Rebalancing types"""
    PERIODIC = "PERIODIC"
    THRESHOLD = "THRESHOLD"
    DYNAMIC = "DYNAMIC"
    TACTICAL = "TACTICAL"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class StrategyPerformance:
    """Strategy performance metrics"""
    strategy_id: str
    returns: List[float]
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    volatility: float
    downside_deviation: float
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    calmar_ratio: float
    recovery_time_days: float
    correlation_to_market: float

@dataclass
class AllocationDecision:
    """Capital allocation decision"""
    timestamp: datetime
    strategy_id: str
    current_allocation: float
    target_allocation: float
    allocation_change: float
    position_size_dollars: float
    position_size_percent: float
    kelly_fraction: float
    confidence_score: float
    risk_contribution: float
    expected_return: float
    expected_volatility: float
    reasoning: str

@dataclass
class PortfolioState:
    """Current portfolio state"""
    timestamp: datetime
    total_capital: float
    allocated_capital: float
    cash_reserves: float
    num_active_strategies: int
    strategy_allocations: Dict[str, float]
    strategy_positions: Dict[str, float]
    portfolio_volatility: float
    portfolio_sharpe: float
    portfolio_var: float
    leverage_used: float
    margin_used: float
    buying_power: float

@dataclass
class AllocationConstraints:
    """Allocation constraints and limits"""
    max_position_size: float = MAX_POSITION_SIZE
    min_position_size: float = MIN_POSITION_SIZE
    max_leverage: float = MAX_LEVERAGE
    max_strategies: int = MAX_STRATEGIES
    min_strategies: int = MIN_STRATEGIES
    max_correlation: float = MAX_CORRELATION
    target_volatility: float = TARGET_VOLATILITY
    cash_reserve: float = EMERGENCY_CASH_RESERVE
    kelly_fraction: float = DEFAULT_KELLY_FRACTION
    allow_short: bool = False
    sector_limits: Dict[str, float] = field(default_factory=dict)

@dataclass
class RebalanceSignal:
    """Rebalancing signal"""
    timestamp: datetime
    trigger_type: str  # drift, periodic, tactical, risk
    current_allocations: Dict[str, float]
    target_allocations: Dict[str, float]
    drift_amount: float
    urgency: str  # immediate, normal, optional
    estimated_cost: float
    estimated_impact: float

# ==============================================================================
# CAPITAL ALLOCATOR
# ==============================================================================

class CapitalAllocator:
    """
    Dynamic capital allocation system using Kelly Criterion and advanced optimization
    Maximizes long-term growth while controlling risk
    """
    
    def __init__(self, 
                 initial_capital: float,
                 risk_level: RiskLevel = RiskLevel.MODERATE,
                 constraints: Optional[AllocationConstraints] = None):
        """
        Initialize capital allocator
        
        Args:
            initial_capital: Starting capital amount
            risk_level: Risk tolerance level
            constraints: Allocation constraints
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_level = risk_level
        self.constraints = constraints or AllocationConstraints()
        
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            
        # Strategy tracking
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.strategy_allocations: Dict[str, float] = {}
        self.strategy_positions: Dict[str, float] = {}
        
        # Historical data
        self.returns_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=LOOKBACK_DAYS))
        self.allocation_history: List[AllocationDecision] = []
        self.portfolio_history: List[PortfolioState] = []
        
        # Market regime
        self.current_regime = MarketRegime.SIDEWAYS
        self.regime_confidence = 0.5
        
        # Correlation tracking
        self.correlation_matrix = None
        self.covariance_matrix = None
        
        # Statistics
        self.total_rebalances = 0
        self.total_allocations = 0
        self.allocation_accuracy = 0.0
        
        # Initialize risk parameters based on level
        self._initialize_risk_parameters()
        
        self.logger.info(f"✅ CapitalAllocator initialized with ${initial_capital:,.0f}")
        
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    
    def _initialize_risk_parameters(self):
        """Initialize risk parameters based on risk level"""
        if self.risk_level == RiskLevel.CONSERVATIVE:
            self.constraints.kelly_fraction = 0.15
            self.constraints.max_position_size = 0.10
            self.constraints.target_volatility = 0.08
            self.constraints.cash_reserve = 0.20
            
        elif self.risk_level == RiskLevel.MODERATE:
            self.constraints.kelly_fraction = 0.25
            self.constraints.max_position_size = 0.20
            self.constraints.target_volatility = 0.12
            self.constraints.cash_reserve = 0.10
            
        elif self.risk_level == RiskLevel.AGGRESSIVE:
            self.constraints.kelly_fraction = 0.40
            self.constraints.max_position_size = 0.30
            self.constraints.target_volatility = 0.18
            self.constraints.cash_reserve = 0.05
            
        else:  # VERY_AGGRESSIVE
            self.constraints.kelly_fraction = 0.50
            self.constraints.max_position_size = 0.40
            self.constraints.target_volatility = 0.25
            self.constraints.cash_reserve = 0.02
            
    # ==========================================================================
    # KELLY CRITERION CALCULATION
    # ==========================================================================
    
    def calculate_kelly_fraction(self, 
                                strategy_id: str,
                                confidence_adjustment: bool = True) -> float:
        """
        Calculate Kelly fraction for a strategy
        
        Args:
            strategy_id: Strategy identifier
            confidence_adjustment: Apply confidence-based adjustment
            
        Returns:
            Optimal betting fraction
        """
        if strategy_id not in self.strategy_performance:
            return 0.0
            
        perf = self.strategy_performance[strategy_id]
        
        # Basic Kelly: f = (p*b - q) / b
        # where p = win probability, q = loss probability, b = win/loss ratio
        
        if perf.win_rate == 0 or perf.avg_loss == 0:
            return 0.0
            
        p = perf.win_rate
        q = 1 - p
        b = abs(perf.avg_win / perf.avg_loss) if perf.avg_loss != 0 else 0
        
        if b == 0:
            return 0.0
            
        # Basic Kelly fraction
        kelly = (p * b - q) / b
        
        # Ensure positive
        kelly = max(0, kelly)
        
        # Apply confidence adjustment based on sample size
        if confidence_adjustment:
            samples = len(self.returns_history[strategy_id])
            confidence = min(1.0, samples / MIN_SAMPLES)
            kelly *= confidence
            
        # Apply strategy-specific adjustments
        kelly = self._adjust_kelly_for_strategy(strategy_id, kelly)
        
        # Apply fractional Kelly
        kelly *= self.constraints.kelly_fraction
        
        # Apply constraints
        kelly = min(kelly, self.constraints.max_position_size)
        kelly = max(kelly, 0)  # No negative allocations unless shorting allowed
        
        return kelly
        
    def _adjust_kelly_for_strategy(self, strategy_id: str, base_kelly: float) -> float:
        """Adjust Kelly fraction based on strategy characteristics"""
        if strategy_id not in self.strategy_performance:
            return base_kelly
            
        perf = self.strategy_performance[strategy_id]
        adjusted_kelly = base_kelly
        
        # Adjust for volatility
        if perf.volatility > 0:
            vol_adjustment = min(1.0, self.constraints.target_volatility / perf.volatility)
            adjusted_kelly *= vol_adjustment
            
        # Adjust for drawdown
        if perf.max_drawdown > 0.20:  # More than 20% drawdown
            dd_adjustment = 1 - (perf.max_drawdown - 0.20)
            adjusted_kelly *= max(0.5, dd_adjustment)
            
        # Adjust for Sharpe ratio
        if perf.sharpe_ratio < 0.5:
            sharpe_adjustment = max(0.3, perf.sharpe_ratio)
            adjusted_kelly *= sharpe_adjustment
            
        # Adjust for market regime
        adjusted_kelly = self._adjust_for_regime(adjusted_kelly)
        
        return adjusted_kelly
        
    def calculate_multi_kelly(self, 
                            strategy_ids: List[str],
                            correlation_matrix: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Calculate Kelly fractions for multiple correlated strategies
        
        Args:
            strategy_ids: List of strategy identifiers
            correlation_matrix: Correlation matrix between strategies
            
        Returns:
            Optimal allocations for each strategy
        """
        n = len(strategy_ids)
        if n == 0:
            return {}
            
        # Get individual Kelly fractions
        individual_kellys = {
            sid: self.calculate_kelly_fraction(sid) 
            for sid in strategy_ids
        }
        
        # If no correlation provided or single strategy, return individual
        if correlation_matrix is None or n == 1:
            return individual_kellys
            
        # Prepare returns and covariance
        returns = []
        for sid in strategy_ids:
            if sid in self.returns_history:
                returns.append(list(self.returns_history[sid]))
            else:
                returns.append([0] * LOOKBACK_DAYS)
                
        returns_df = pd.DataFrame(returns).T
        returns_df.columns = strategy_ids
        
        # Calculate covariance matrix
        if ML_AVAILABLE:
            # Use Ledoit-Wolf shrinkage for better covariance estimation
            lw = LedoitWolf()
            cov_matrix = lw.fit(returns_df).covariance_
        else:
            cov_matrix = returns_df.cov().values
            
        # Solve for optimal allocations considering correlation
        # This is a quadratic programming problem
        allocations = self._solve_correlated_kelly(
            strategy_ids,
            individual_kellys,
            cov_matrix
        )
        
        return allocations
        
    def _solve_correlated_kelly(self,
                               strategy_ids: List[str],
                               individual_kellys: Dict[str, float],
                               cov_matrix: np.ndarray) -> Dict[str, float]:
        """Solve for optimal Kelly allocations with correlation"""
        n = len(strategy_ids)
        
        # Expected returns (use Kelly fractions as proxy)
        expected_returns = np.array([individual_kellys[sid] for sid in strategy_ids])
        
        # Objective function: maximize expected growth - 0.5 * risk
        def objective(weights):
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_variance = np.dot(weights, np.dot(cov_matrix, weights))
            return -(portfolio_return - 0.5 * portfolio_variance)
            
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},  # Sum to 1
            {'type': 'ineq', 'fun': lambda x: x}  # All positive
        ]
        
        # Bounds
        bounds = [(0, self.constraints.max_position_size) for _ in range(n)]
        
        # Initial guess (equal weight)
        x0 = np.array([1/n] * n)
        
        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            allocations = {
                strategy_ids[i]: result.x[i] 
                for i in range(n)
            }
        else:
            # Fallback to individual Kelly
            allocations = individual_kellys
            
        return allocations
        
    # ==========================================================================
    # RISK PARITY ALLOCATION
    # ==========================================================================
    
    def calculate_risk_parity(self, strategy_ids: List[str]) -> Dict[str, float]:
        """
        Calculate risk parity allocation
        Equal risk contribution from each strategy
        
        Args:
            strategy_ids: List of strategy identifiers
            
        Returns:
            Risk parity allocations
        """
        n = len(strategy_ids)
        if n == 0:
            return {}
            
        # Get volatilities
        volatilities = []
        for sid in strategy_ids:
            if sid in self.strategy_performance:
                volatilities.append(self.strategy_performance[sid].volatility)
            else:
                volatilities.append(0.15)  # Default 15% volatility
                
        volatilities = np.array(volatilities)
        
        # Simple risk parity: weight inversely proportional to volatility
        if np.sum(volatilities) > 0:
            inv_vols = 1 / volatilities
            weights = inv_vols / np.sum(inv_vols)
        else:
            weights = np.array([1/n] * n)
            
        # Apply constraints
        weights = np.clip(weights, 
                         self.constraints.min_position_size,
                         self.constraints.max_position_size)
        
        # Renormalize
        weights = weights / np.sum(weights)
        
        allocations = {
            strategy_ids[i]: weights[i]
            for i in range(n)
        }
        
        return allocations
        
    def calculate_hierarchical_risk_parity(self, 
                                          strategy_ids: List[str]) -> Dict[str, float]:
        """
        Calculate Hierarchical Risk Parity (HRP) allocation
        Combines diversification with clustering
        
        Args:
            strategy_ids: List of strategy identifiers
            
        Returns:
            HRP allocations
        """
        n = len(strategy_ids)
        if n < 2:
            return {sid: 1.0 for sid in strategy_ids}
            
        # Get returns matrix
        returns_matrix = self._get_returns_matrix(strategy_ids)
        
        if returns_matrix is None:
            # Fallback to equal weight
            return {sid: 1/n for sid in strategy_ids}
            
        # Calculate correlation and distance matrices
        corr_matrix = np.corrcoef(returns_matrix.T)
        dist_matrix = np.sqrt(0.5 * (1 - corr_matrix))
        
        # Perform hierarchical clustering
        # (Simplified version - full HRP would use linkage clustering)
        
        # For now, use risk parity within correlation clusters
        allocations = self.calculate_risk_parity(strategy_ids)
        
        return allocations
        
    # ==========================================================================
    # MEAN-VARIANCE OPTIMIZATION
    # ==========================================================================
    
    def calculate_mean_variance(self,
                               strategy_ids: List[str],
                               target_return: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate mean-variance optimal allocation
        
        Args:
            strategy_ids: List of strategy identifiers
            target_return: Target portfolio return
            
        Returns:
            Mean-variance optimal allocations
        """
        n = len(strategy_ids)
        if n == 0:
            return {}
            
        # Get expected returns and covariance
        returns_matrix = self._get_returns_matrix(strategy_ids)
        
        if returns_matrix is None:
            return {sid: 1/n for sid in strategy_ids}
            
        expected_returns = returns_matrix.mean(axis=0)
        cov_matrix = np.cov(returns_matrix.T)
        
        # Objective: minimize variance
        def objective(weights):
            return np.dot(weights, np.dot(cov_matrix, weights))
            
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        # Add return constraint if specified
        if target_return is not None:
            constraints.append({
                'type': 'eq',
                'fun': lambda x: np.dot(x, expected_returns) - target_return
            })
            
        # Bounds
        bounds = [(0, self.constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.array([1/n] * n)
        
        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            allocations = {
                strategy_ids[i]: result.x[i]
                for i in range(n)
            }
        else:
            # Fallback to equal weight
            allocations = {sid: 1/n for sid in strategy_ids}
            
        return allocations
        
    def calculate_max_sharpe(self, strategy_ids: List[str]) -> Dict[str, float]:
        """
        Calculate maximum Sharpe ratio allocation
        
        Args:
            strategy_ids: List of strategy identifiers
            
        Returns:
            Maximum Sharpe allocations
        """
        n = len(strategy_ids)
        if n == 0:
            return {}
            
        # Get expected returns and covariance
        returns_matrix = self._get_returns_matrix(strategy_ids)
        
        if returns_matrix is None:
            return {sid: 1/n for sid in strategy_ids}
            
        expected_returns = returns_matrix.mean(axis=0)
        cov_matrix = np.cov(returns_matrix.T)
        risk_free_rate = 0.02 / 252  # Daily risk-free rate
        
        # Objective: maximize Sharpe ratio (negative for minimization)
        def objective(weights):
            portfolio_return = np.dot(weights, expected_returns)
            portfolio_std = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
            
            if portfolio_std == 0:
                return 0
                
            sharpe = (portfolio_return - risk_free_rate) / portfolio_std
            return -sharpe  # Negative for minimization
            
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # Sum to 1
        ]
        
        # Bounds
        bounds = [(0, self.constraints.max_position_size) for _ in range(n)]
        
        # Initial guess
        x0 = np.array([1/n] * n)
        
        # Optimize
        result = optimize.minimize(
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )
        
        if result.success:
            allocations = {
                strategy_ids[i]: result.x[i]
                for i in range(n)
            }
        else:
            # Fallback to equal weight
            allocations = {sid: 1/n for sid in strategy_ids}
            
        return allocations
        
    # ==========================================================================
    # DYNAMIC ALLOCATION
    # ==========================================================================
    
    def allocate_capital(self,
                        strategy_ids: List[str],
                        method: AllocationMethod = AllocationMethod.DYNAMIC) -> List[AllocationDecision]:
        """
        Main capital allocation method
        
        Args:
            strategy_ids: Strategies to allocate to
            method: Allocation method to use
            
        Returns:
            List of allocation decisions
        """
        self.total_allocations += 1
        decisions = []
        
        # Update market regime
        self._update_market_regime()
        
        # Filter strategies based on performance
        active_strategies = self._filter_strategies(strategy_ids)
        
        if not active_strategies:
            self.logger.warning("No strategies meet allocation criteria")
            return decisions
            
        # Calculate allocations based on method
        if method == AllocationMethod.KELLY:
            allocations = self.calculate_multi_kelly(active_strategies)
            
        elif method == AllocationMethod.RISK_PARITY:
            allocations = self.calculate_risk_parity(active_strategies)
            
        elif method == AllocationMethod.EQUAL_WEIGHT:
            n = len(active_strategies)
            allocations = {sid: 1/n for sid in active_strategies}
            
        elif method == AllocationMethod.MEAN_VARIANCE:
            allocations = self.calculate_mean_variance(active_strategies)
            
        elif method == AllocationMethod.MIN_VARIANCE:
            allocations = self.calculate_mean_variance(active_strategies, target_return=0)
            
        elif method == AllocationMethod.MAX_SHARPE:
            allocations = self.calculate_max_sharpe(active_strategies)
            
        elif method == AllocationMethod.HIERARCHICAL:
            allocations = self.calculate_hierarchical_risk_parity(active_strategies)
            
        else:  # DYNAMIC
            allocations = self._dynamic_allocation(active_strategies)
            
        # Apply regime adjustments
        allocations = self._apply_regime_adjustments(allocations)
        
        # Apply constraints
        allocations = self._apply_constraints(allocations)
        
        # Create allocation decisions
        for strategy_id, target_allocation in allocations.items():
            current_allocation = self.strategy_allocations.get(strategy_id, 0)
            
            decision = AllocationDecision(
                timestamp=datetime.now(),
                strategy_id=strategy_id,
                current_allocation=current_allocation,
                target_allocation=target_allocation,
                allocation_change=target_allocation - current_allocation,
                position_size_dollars=target_allocation * self.current_capital,
                position_size_percent=target_allocation,
                kelly_fraction=self.calculate_kelly_fraction(strategy_id),
                confidence_score=self._calculate_confidence(strategy_id),
                risk_contribution=self._calculate_risk_contribution(strategy_id, target_allocation),
                expected_return=self._get_expected_return(strategy_id),
                expected_volatility=self._get_expected_volatility(strategy_id),
                reasoning=self._generate_reasoning(strategy_id, method)
            )
            
            decisions.append(decision)
            self.allocation_history.append(decision)
            
        # Update allocations
        self.strategy_allocations = allocations
        
        # Update portfolio state
        self._update_portfolio_state()
        
        self.logger.info(f"Allocated capital to {len(decisions)} strategies using {method.value}")
        
        return decisions
        
    def _dynamic_allocation(self, strategy_ids: List[str]) -> Dict[str, float]:
        """
        Dynamic allocation combining multiple methods
        """
        # Get allocations from different methods
        kelly_alloc = self.calculate_multi_kelly(strategy_ids)
        risk_parity_alloc = self.calculate_risk_parity(strategy_ids)
        sharpe_alloc = self.calculate_max_sharpe(strategy_ids)
        
        # Combine based on market regime and confidence
        allocations = {}
        
        for sid in strategy_ids:
            kelly_w = kelly_alloc.get(sid, 0)
            rp_w = risk_parity_alloc.get(sid, 0)
            sharpe_w = sharpe_alloc.get(sid, 0)
            
            # Weight methods based on regime
            if self.current_regime == MarketRegime.BULL:
                # More aggressive in bull market
                combined = 0.5 * kelly_w + 0.2 * rp_w + 0.3 * sharpe_w
                
            elif self.current_regime == MarketRegime.BEAR:
                # More conservative in bear market
                combined = 0.2 * kelly_w + 0.6 * rp_w + 0.2 * sharpe_w
                
            elif self.current_regime == MarketRegime.HIGH_VOLATILITY:
                # Focus on risk parity in high vol
                combined = 0.1 * kelly_w + 0.7 * rp_w + 0.2 * sharpe_w
                
            elif self.current_regime == MarketRegime.CRASH:
                # Minimal allocation in crash
                combined = min(0.02, 0.1 * rp_w)
                
            else:  # SIDEWAYS or RECOVERY
                # Balanced approach
                combined = 0.33 * kelly_w + 0.34 * rp_w + 0.33 * sharpe_w
                
            allocations[sid] = combined
            
        # Normalize
        total = sum(allocations.values())
        if total > 0:
            allocations = {k: v/total for k, v in allocations.items()}
            
        return allocations
        
    # ==========================================================================
    # REBALANCING
    # ==========================================================================
    
    def check_rebalance_needed(self) -> Optional[RebalanceSignal]:
        """
        Check if portfolio rebalancing is needed
        
        Returns:
            Rebalance signal if needed, None otherwise
        """
        if not self.strategy_allocations:
            return None
            
        # Calculate current vs target drift
        max_drift = 0
        total_drift = 0
        
        for strategy_id, current_alloc in self.strategy_allocations.items():
            # Recalculate target
            target_alloc = self.calculate_kelly_fraction(strategy_id)
            drift = abs(target_alloc - current_alloc)
            
            max_drift = max(max_drift, drift)
            total_drift += drift
            
        # Check if drift exceeds threshold
        if max_drift > self.constraints.rebalance_threshold:
            # Calculate new target allocations
            active_strategies = list(self.strategy_allocations.keys())
            target_allocations = self._dynamic_allocation(active_strategies)
            
            signal = RebalanceSignal(
                timestamp=datetime.now(),
                trigger_type="drift",
                current_allocations=self.strategy_allocations.copy(),
                target_allocations=target_allocations,
                drift_amount=max_drift,
                urgency="normal" if max_drift < 0.10 else "immediate",
                estimated_cost=self._estimate_rebalance_cost(target_allocations),
                estimated_impact=self._estimate_rebalance_impact(target_allocations)
            )
            
            return signal
            
        # Check for tactical rebalancing opportunities
        if self._check_tactical_rebalance():
            active_strategies = list(self.strategy_allocations.keys())
            target_allocations = self._dynamic_allocation(active_strategies)
            
            signal = RebalanceSignal(
                timestamp=datetime.now(),
                trigger_type="tactical",
                current_allocations=self.strategy_allocations.copy(),
                target_allocations=target_allocations,
                drift_amount=0,
                urgency="optional",
                estimated_cost=self._estimate_rebalance_cost(target_allocations),
                estimated_impact=self._estimate_rebalance_impact(target_allocations)
            )
            
            return signal
            
        return None
        
    def execute_rebalance(self, signal: RebalanceSignal) -> bool:
        """
        Execute portfolio rebalancing
        
        Args:
            signal: Rebalance signal
            
        Returns:
            Success status
        """
        try:
            self.total_rebalances += 1
            
            # Update allocations
            self.strategy_allocations = signal.target_allocations
            
            # Update positions
            for strategy_id, allocation in signal.target_allocations.items():
                self.strategy_positions[strategy_id] = allocation * self.current_capital
                
            # Update portfolio state
            self._update_portfolio_state()
            
            self.logger.info(f"Rebalanced portfolio: {signal.trigger_type} trigger")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rebalancing failed: {e}")
            return False
            
    # ==========================================================================
    # RISK MANAGEMENT
    # ==========================================================================
    
    def _apply_regime_adjustments(self, 
                                 allocations: Dict[str, float]) -> Dict[str, float]:
        """Apply market regime adjustments to allocations"""
        adjusted = {}
        
        for strategy_id, allocation in allocations.items():
            if self.current_regime == MarketRegime.BULL:
                adjusted[strategy_id] = allocation * BULL_MARKET_MULTIPLIER
                
            elif self.current_regime == MarketRegime.BEAR:
                adjusted[strategy_id] = allocation * BEAR_MARKET_MULTIPLIER
                
            elif self.current_regime == MarketRegime.HIGH_VOLATILITY:
                adjusted[strategy_id] = allocation * HIGH_VOL_MULTIPLIER
                
            elif self.current_regime == MarketRegime.CRASH:
                adjusted[strategy_id] = allocation * CRASH_MODE_ALLOCATION
                
            else:
                adjusted[strategy_id] = allocation
                
        # Renormalize
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v/total for k, v in adjusted.items()}
            
        return adjusted
        
    def _apply_constraints(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Apply allocation constraints"""
        constrained = {}
        
        # Apply position size limits
        for strategy_id, allocation in allocations.items():
            constrained[strategy_id] = np.clip(
                allocation,
                self.constraints.min_position_size,
                self.constraints.max_position_size
            )
            
        # Reserve cash
        total_allocation = sum(constrained.values())
        max_allocation = 1 - self.constraints.cash_reserve
        
        if total_allocation > max_allocation:
            # Scale down proportionally
            scale = max_allocation / total_allocation
            constrained = {k: v * scale for k, v in constrained.items()}
            
        # Check correlation constraints
        constrained = self._apply_correlation_constraints(constrained)
        
        return constrained
        
    def _apply_correlation_constraints(self, 
                                      allocations: Dict[str, float]) -> Dict[str, float]:
        """Reduce allocation to highly correlated strategies"""
        if len(allocations) < 2:
            return allocations
            
        # Get correlation matrix
        strategy_ids = list(allocations.keys())
        corr_matrix = self._calculate_correlation_matrix(strategy_ids)
        
        if corr_matrix is None:
            return allocations
            
        # Identify highly correlated pairs
        adjusted = allocations.copy()
        n = len(strategy_ids)
        
        for i in range(n):
            for j in range(i+1, n):
                correlation = corr_matrix[i, j]
                
                if abs(correlation) > self.constraints.max_correlation:
                    # Reduce allocation to smaller position
                    sid1, sid2 = strategy_ids[i], strategy_ids[j]
                    
                    if adjusted[sid1] < adjusted[sid2]:
                        # Reduce sid1
                        adjusted[sid1] *= (1 - abs(correlation - self.constraints.max_correlation))
                    else:
                        # Reduce sid2
                        adjusted[sid2] *= (1 - abs(correlation - self.constraints.max_correlation))
                        
        return adjusted
        
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _filter_strategies(self, strategy_ids: List[str]) -> List[str]:
        """Filter strategies based on performance criteria"""
        filtered = []
        
        for sid in strategy_ids:
            if sid not in self.strategy_performance:
                continue
                
            perf = self.strategy_performance[sid]
            
            # Filter criteria
            if perf.sharpe_ratio < 0:  # Negative Sharpe
                continue
            if perf.max_drawdown > 0.50:  # More than 50% drawdown
                continue
            if perf.win_rate < 0.30:  # Less than 30% win rate
                continue
                
            filtered.append(sid)
            
        return filtered
        
    def _update_market_regime(self):
        """Update current market regime detection"""
        # This would use actual market data
        # For now, simulate
        regimes = list(MarketRegime)
        probabilities = [0.3, 0.2, 0.3, 0.15, 0.02, 0.03]  # Bull, Bear, Sideways, HighVol, Crash, Recovery
        
        self.current_regime = np.random.choice(regimes, p=probabilities)
        self.regime_confidence = np.random.uniform(0.6, 0.9)
        
    def _get_returns_matrix(self, strategy_ids: List[str]) -> Optional[np.ndarray]:
        """Get returns matrix for strategies"""
        if not strategy_ids:
            return None
            
        returns = []
        for sid in strategy_ids:
            if sid in self.returns_history:
                strategy_returns = list(self.returns_history[sid])
                if len(strategy_returns) >= MIN_SAMPLES:
                    returns.append(strategy_returns[-MIN_SAMPLES:])
                else:
                    return None
            else:
                return None
                
        return np.array(returns) if returns else None
        
    def _calculate_correlation_matrix(self, strategy_ids: List[str]) -> Optional[np.ndarray]:
        """Calculate correlation matrix for strategies"""
        returns_matrix = self._get_returns_matrix(strategy_ids)
        
        if returns_matrix is None:
            return None
            
        return np.corrcoef(returns_matrix)
        
    def _calculate_confidence(self, strategy_id: str) -> float:
        """Calculate confidence score for strategy allocation"""
        if strategy_id not in self.strategy_performance:
            return 0.0
            
        perf = self.strategy_performance[strategy_id]
        
        # Base confidence on multiple factors
        confidence = 0.0
        
        # Sharpe ratio component (0-40%)
        if perf.sharpe_ratio > 0:
            confidence += min(0.4, perf.sharpe_ratio / 3)
            
        # Win rate component (0-30%)
        confidence += perf.win_rate * 0.3
        
        # Sample size component (0-20%)
        samples = len(self.returns_history[strategy_id])
        confidence += min(0.2, samples / (MIN_SAMPLES * 2))
        
        # Drawdown component (0-10%)
        if perf.max_drawdown < 0.20:
            confidence += 0.1
            
        return min(1.0, confidence)
        
    def _calculate_risk_contribution(self, strategy_id: str, allocation: float) -> float:
        """Calculate risk contribution of strategy to portfolio"""
        if strategy_id not in self.strategy_performance:
            return 0.0
            
        strategy_vol = self.strategy_performance[strategy_id].volatility
        
        # Simplified risk contribution
        risk_contribution = allocation * strategy_vol
        
        return risk_contribution
        
    def _get_expected_return(self, strategy_id: str) -> float:
        """Get expected return for strategy"""
        if strategy_id not in self.returns_history:
            return 0.0
            
        returns = list(self.returns_history[strategy_id])
        
        if not returns:
            return 0.0
            
        return np.mean(returns)
        
    def _get_expected_volatility(self, strategy_id: str) -> float:
        """Get expected volatility for strategy"""
        if strategy_id not in self.strategy_performance:
            return 0.15  # Default 15%
            
        return self.strategy_performance[strategy_id].volatility
        
    def _generate_reasoning(self, strategy_id: str, method: AllocationMethod) -> str:
        """Generate reasoning for allocation decision"""
        perf = self.strategy_performance.get(strategy_id)
        
        if not perf:
            return f"New strategy allocation using {method.value}"
            
        reasons = []
        
        if perf.sharpe_ratio > 1.0:
            reasons.append(f"Strong Sharpe ratio ({perf.sharpe_ratio:.2f})")
        if perf.win_rate > 0.60:
            reasons.append(f"High win rate ({perf.win_rate:.1%})")
        if perf.max_drawdown < 0.10:
            reasons.append(f"Low drawdown ({perf.max_drawdown:.1%})")
            
        reasoning = f"{method.value} allocation. " + ", ".join(reasons) if reasons else ""
        
        return reasoning
        
    def _update_portfolio_state(self):
        """Update current portfolio state"""
        state = PortfolioState(
            timestamp=datetime.now(),
            total_capital=self.current_capital,
            allocated_capital=sum(self.strategy_positions.values()),
            cash_reserves=self.current_capital * self.constraints.cash_reserve,
            num_active_strategies=len([a for a in self.strategy_allocations.values() if a > 0]),
            strategy_allocations=self.strategy_allocations.copy(),
            strategy_positions=self.strategy_positions.copy(),
            portfolio_volatility=self._calculate_portfolio_volatility(),
            portfolio_sharpe=self._calculate_portfolio_sharpe(),
            portfolio_var=self._calculate_portfolio_var(),
            leverage_used=0,  # Would calculate actual leverage
            margin_used=0,  # Would calculate actual margin
            buying_power=self.current_capital - sum(self.strategy_positions.values())
        )
        
        self.portfolio_history.append(state)
        
    def _calculate_portfolio_volatility(self) -> float:
        """Calculate portfolio volatility"""
        if not self.strategy_allocations:
            return 0.0
            
        # Weighted volatility (simplified)
        weighted_vol = 0
        
        for sid, allocation in self.strategy_allocations.items():
            if sid in self.strategy_performance:
                weighted_vol += allocation * self.strategy_performance[sid].volatility
                
        return weighted_vol
        
    def _calculate_portfolio_sharpe(self) -> float:
        """Calculate portfolio Sharpe ratio"""
        if not self.returns_history:
            return 0.0
            
        # Calculate portfolio returns
        portfolio_returns = []
        
        for i in range(MIN_SAMPLES):
            period_return = 0
            for sid, allocation in self.strategy_allocations.items():
                if sid in self.returns_history and len(self.returns_history[sid]) > i:
                    period_return += allocation * self.returns_history[sid][-MIN_SAMPLES+i]
            portfolio_returns.append(period_return)
            
        if not portfolio_returns:
            return 0.0
            
        mean_return = np.mean(portfolio_returns)
        std_return = np.std(portfolio_returns)
        
        if std_return == 0:
            return 0.0
            
        risk_free_rate = 0.02 / 252  # Daily risk-free rate
        sharpe = (mean_return - risk_free_rate) / std_return * np.sqrt(252)
        
        return sharpe
        
    def _calculate_portfolio_var(self) -> float:
        """Calculate portfolio Value at Risk"""
        # Simplified VaR calculation
        portfolio_vol = self._calculate_portfolio_volatility()
        var_95 = -1.645 * portfolio_vol * self.current_capital
        
        return var_95
        
    def _estimate_rebalance_cost(self, target_allocations: Dict[str, float]) -> float:
        """Estimate rebalancing transaction costs"""
        total_cost = 0
        
        for sid, target in target_allocations.items():
            current = self.strategy_allocations.get(sid, 0)
            turnover = abs(target - current) * self.current_capital
            
            # Assume 10 bps transaction cost
            total_cost += turnover * 0.001
            
        return total_cost
        
    def _estimate_rebalance_impact(self, target_allocations: Dict[str, float]) -> float:
        """Estimate market impact of rebalancing"""
        total_impact = 0
        
        for sid, target in target_allocations.items():
            current = self.strategy_allocations.get(sid, 0)
            turnover = abs(target - current) * self.current_capital
            
            # Simple square-root impact model
            impact = 0.001 * np.sqrt(turnover / 1000000)  # Impact per $1M
            total_impact += impact
            
        return total_impact
        
    def _check_tactical_rebalance(self) -> bool:
        """Check for tactical rebalancing opportunities"""
        # Check if regime changed significantly
        # Check if correlations changed
        # Check if new opportunities emerged
        
        # For now, simple random check
        return np.random.random() < 0.05  # 5% chance
        
    def _adjust_for_regime(self, kelly: float) -> float:
        """Adjust Kelly fraction for market regime"""
        if self.current_regime == MarketRegime.BULL:
            return kelly * 1.2
        elif self.current_regime == MarketRegime.BEAR:
            return kelly * 0.7
        elif self.current_regime == MarketRegime.HIGH_VOLATILITY:
            return kelly * 0.5
        elif self.current_regime == MarketRegime.CRASH:
            return kelly * 0.2
        else:
            return kelly
            
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def update_strategy_performance(self, 
                                  strategy_id: str,
                                  performance: StrategyPerformance):
        """Update strategy performance metrics"""
        self.strategy_performance[strategy_id] = performance
        
    def add_returns(self, strategy_id: str, returns: List[float]):
        """Add returns history for strategy"""
        for ret in returns:
            self.returns_history[strategy_id].append(ret)
            
    def get_allocation_summary(self) -> Dict[str, Any]:
        """Get current allocation summary"""
        return {
            'total_capital': self.current_capital,
            'allocated_capital': sum(self.strategy_positions.values()),
            'cash_reserves': self.current_capital * self.constraints.cash_reserve,
            'num_strategies': len([a for a in self.strategy_allocations.values() if a > 0]),
            'allocations': self.strategy_allocations,
            'portfolio_volatility': self._calculate_portfolio_volatility(),
            'portfolio_sharpe': self._calculate_portfolio_sharpe(),
            'current_regime': self.current_regime.value,
            'regime_confidence': self.regime_confidence
        }
        
    def get_strategy_allocation(self, strategy_id: str) -> float:
        """Get current allocation for strategy"""
        return self.strategy_allocations.get(strategy_id, 0.0)
        
    def set_risk_level(self, risk_level: RiskLevel):
        """Update risk level and adjust parameters"""
        self.risk_level = risk_level
        self._initialize_risk_parameters()
        
    def update_capital(self, new_capital: float):
        """Update available capital"""
        self.current_capital = new_capital
        
        # Update position sizes
        for sid, allocation in self.strategy_allocations.items():
            self.strategy_positions[sid] = allocation * new_capital

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_capital_allocator(initial_capital: float,
                           risk_level: RiskLevel = RiskLevel.MODERATE) -> CapitalAllocator:
    """Factory function to create capital allocator"""
    return CapitalAllocator(initial_capital, risk_level)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import logging
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("CAPITAL ALLOCATOR TEST")
    print("=" * 80)
    
    # Create allocator
    allocator = create_capital_allocator(
        initial_capital=1_000_000,
        risk_level=RiskLevel.MODERATE
    )
    
    # Create test strategies
    test_strategies = ["STRAT_A", "STRAT_B", "STRAT_C", "STRAT_D"]
    
    # Add performance data
    for i, sid in enumerate(test_strategies):
        perf = StrategyPerformance(
            strategy_id=sid,
            returns=[np.random.normal(0.001, 0.02) for _ in range(60)],
            sharpe_ratio=1.5 - i*0.3,
            sortino_ratio=2.0 - i*0.4,
            max_drawdown=0.10 + i*0.05,
            win_rate=0.60 - i*0.05,
            profit_factor=1.8 - i*0.2,
            avg_win=100 + i*10,
            avg_loss=50 + i*5,
            volatility=0.10 + i*0.02,
            downside_deviation=0.08 + i*0.01,
            var_95=-0.02 - i*0.005,
            cvar_95=-0.03 - i*0.007,
            calmar_ratio=2.0 - i*0.3,
            recovery_time_days=10 + i*5,
            correlation_to_market=0.5 + i*0.1
        )
        
        allocator.update_strategy_performance(sid, perf)
        allocator.add_returns(sid, perf.returns)
    
    print("\n📊 Testing Different Allocation Methods:\n")
    
    # Test different allocation methods
    methods = [
        AllocationMethod.KELLY,
        AllocationMethod.RISK_PARITY,
        AllocationMethod.MAX_SHARPE,
        AllocationMethod.DYNAMIC
    ]
    
    for method in methods:
        decisions = allocator.allocate_capital(test_strategies, method)
        
        print(f"\n{method.value}:")
        print("-" * 40)
        
        for decision in decisions:
            print(f"  {decision.strategy_id}: {decision.target_allocation:.1%} "
                  f"(${decision.position_size_dollars:,.0f})")
            print(f"    Kelly: {decision.kelly_fraction:.3f}, "
                  f"Confidence: {decision.confidence_score:.1%}")
    
    # Check rebalancing
    print("\n🔄 Rebalancing Check:")
    signal = allocator.check_rebalance_needed()
    
    if signal:
        print(f"  Rebalance needed: {signal.trigger_type}")
        print(f"  Drift: {signal.drift_amount:.1%}")
        print(f"  Estimated cost: ${signal.estimated_cost:,.2f}")
    else:
        print("  No rebalancing needed")
    
    # Get summary
    summary = allocator.get_allocation_summary()
    
    print("\n📈 Portfolio Summary:")
    print(f"  Total Capital: ${summary['total_capital']:,.0f}")
    print(f"  Allocated: ${summary['allocated_capital']:,.0f}")
    print(f"  Cash Reserve: ${summary['cash_reserves']:,.0f}")
    print(f"  Active Strategies: {summary['num_strategies']}")
    print(f"  Portfolio Volatility: {summary['portfolio_volatility']:.1%}")
    print(f"  Portfolio Sharpe: {summary['portfolio_sharpe']:.2f}")
    print(f"  Market Regime: {summary['current_regime']}")
    
    print("\n✅ Capital allocator test completed")
