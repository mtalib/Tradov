#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderP_PortfolioMgmt
Module: SpyderP01_PortfolioManager.py
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
import time
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import optimize

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceCalculator as PerformanceMetrics  # noqa: E501
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from Spyder.SpyderE_Risk.SpyderE02_PositionSizer import get_position_sizer
from Spyder.SpyderE_Risk.SpyderE04_DrawdownControl import DrawdownController
from Spyder.SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderS_Signals.SpyderS05_GEXDEXCalculator import GammaExposureCalculator

try:
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub
    from SpyderI_Integration.SpyderI03_ConfigManager import get_global_config_manager  # noqa: F401
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

_module_logger = SpyderLogger.get_logger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Portfolio management settings
DEFAULT_PORTFOLIO_SIZE = 100000  # $100k default portfolio
MAX_PORTFOLIO_STRATEGIES = 20    # Maximum concurrent strategies
DEFAULT_REBALANCE_FREQUENCY = 24 * 60 * 60  # 24 hours in seconds

# Risk limits (portfolio-level)
MAX_PORTFOLIO_DELTA = 500        # Maximum net delta exposure
MAX_PORTFOLIO_GAMMA = 100        # Maximum net gamma exposure
MAX_PORTFOLIO_VEGA = 1000        # Maximum net vega exposure
MAX_PORTFOLIO_THETA = -200       # Maximum theta decay per day
MAX_CORRELATION_EXPOSURE = 0.6   # Maximum correlation between strategies

# Allocation constraints
MIN_STRATEGY_ALLOCATION = 0.05   # 5% minimum allocation
MAX_STRATEGY_ALLOCATION = 0.40   # 40% maximum allocation
MIN_CASH_RESERVE = 0.10          # 10% minimum cash reserve
DIVERSIFICATION_TARGET = 0.85    # Target diversification ratio

# Performance thresholds
STRATEGY_UNDERPERFORMANCE_THRESHOLD = -0.10  # -10% underperformance
STRATEGY_REALLOCATION_THRESHOLD = 0.05       # 5% allocation drift
PORTFOLIO_DRAWDOWN_THRESHOLD = 0.08          # 8% portfolio drawdown

# Update frequencies
PORTFOLIO_UPDATE_FREQUENCY = 60   # seconds
REBALANCE_CHECK_FREQUENCY = 3600  # 1 hour
PERFORMANCE_CALC_FREQUENCY = 300  # 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class PortfolioState(Enum):
    """Portfolio operational states"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    REBALANCING = "rebalancing"
    DEFENSIVE = "defensive"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"

class AllocationMethod(Enum):
    """Capital allocation methods"""
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    PERFORMANCE_BASED = "performance_based"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    KELLY_CRITERION = "kelly_criterion"
    MAX_DIVERSIFICATION = "max_diversification"
    RISKFOLIO_OPTIMIZED = "riskfolio_optimized"

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    SCHEDULED = "scheduled"
    DRIFT_THRESHOLD = "drift_threshold"
    RISK_BREACH = "risk_breach"
    PERFORMANCE_TRIGGER = "performance_trigger"
    MARKET_REGIME_CHANGE = "market_regime_change"
    STRATEGY_CHANGE = "strategy_change"
    EMERGENCY = "emergency"

class HedgeType(Enum):
    """Types of portfolio hedges"""
    DELTA_HEDGE = "delta_hedge"
    VOLATILITY_HEDGE = "volatility_hedge"
    CORRELATION_HEDGE = "correlation_hedge"
    TAIL_RISK_HEDGE = "tail_risk_hedge"
    SECTOR_HEDGE = "sector_hedge"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyAllocation:
    """Strategy allocation information"""
    strategy_id: str
    strategy_name: str
    target_allocation: float    # Target percentage (0-1)
    current_allocation: float   # Current percentage (0-1)
    allocated_capital: float    # Dollar amount allocated
    available_capital: float    # Available for new positions
    used_capital: float        # Currently in positions
    performance_mtd: float     # Month-to-date performance
    performance_ytd: float     # Year-to-date performance
    sharpe_ratio: float        # Risk-adjusted return
    max_drawdown: float        # Maximum historical drawdown
    volatility: float          # Strategy volatility
    correlation_to_portfolio: float  # Correlation to rest of portfolio
    last_rebalance: datetime   # Last rebalancing timestamp
    status: str = "active"     # active, paused, closing

@dataclass
class PortfolioPosition:
    """Consolidated portfolio position"""
    symbol: str
    strategy_positions: dict[str, Any]  # Positions by strategy
    net_quantity: int          # Net position size
    net_delta: float          # Net delta exposure
    net_gamma: float          # Net gamma exposure
    net_vega: float           # Net vega exposure
    net_theta: float          # Net theta exposure
    total_cost_basis: float   # Total cost basis
    total_market_value: float # Current market value
    unrealized_pnl: float     # Unrealized P&L
    days_in_trade: int        # Days since first position
    risk_contribution: float  # Contribution to portfolio risk

@dataclass
class PortfolioMetrics:
    """Portfolio performance and risk metrics"""
    timestamp: datetime
    total_value: float
    cash_balance: float
    invested_capital: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    mtd_return: float
    ytd_return: float
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    volatility: float
    beta: float
    value_at_risk: float       # 95% VaR
    expected_shortfall: float  # Expected loss beyond VaR
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_vega: float
    portfolio_theta: float
    correlation_score: float   # Portfolio diversification
    strategy_count: int
    active_positions: int

@dataclass
class RebalanceEvent:
    """Portfolio rebalancing event"""
    rebalance_id: str
    timestamp: datetime
    reason: RebalanceReason
    old_allocations: dict[str, float]
    new_allocations: dict[str, float]
    capital_movements: dict[str, float]  # Net capital change by strategy
    expected_impact: dict[str, Any]      # Expected impact metrics
    execution_time: float | None = None
    success: bool = False
    notes: str = ""

@dataclass
class HedgePosition:
    """Portfolio hedge position"""
    hedge_id: str
    hedge_type: HedgeType
    hedge_ratio: float         # Hedge ratio (0-1)
    target_exposure: float     # Target exposure to hedge
    hedge_instruments: list[dict[str, Any]]  # Hedge instruments
    cost_basis: float          # Cost of hedge
    effectiveness: float       # Hedge effectiveness ratio
    created_at: datetime
    expires_at: datetime | None = None
    is_active: bool = True

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PortfolioManager:
    """
    Comprehensive portfolio management system for SPYDER strategies.

    This manager coordinates multiple trading strategies, manages capital
    allocation, monitors portfolio-level risk, handles rebalancing, and
    implements cross-strategy hedging for institutional-grade portfolio
    management.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event manager for notifications
        performance_metrics: Performance tracking system

    Example:
        >>> portfolio = PortfolioManager(initial_capital=100000)
        >>> portfolio.add_strategy('iron_condor', target_allocation=0.30)
        >>> portfolio.start_management()
        >>> metrics = portfolio.get_portfolio_metrics()
    """

    def __init__(self, initial_capital: float = DEFAULT_PORTFOLIO_SIZE,
                 config: dict[str, Any] | None = None,
                 tradier_client: Any = None):
        """
        Initialize the Portfolio Manager.

        Args:
            initial_capital: Initial portfolio capital
            config: Configuration dictionary
            tradier_client: Optional TradierClient for live market data feeds
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.performance_metrics = PerformanceMetrics()
        self.datetime_utils = DateTimeUtils()

        # Configuration
        self.config = config or {}
        self.initial_capital = initial_capital
        self.current_capital = initial_capital

        # Portfolio state
        self.portfolio_state = PortfolioState.INITIALIZING
        self.portfolio_id = str(uuid.uuid4())
        self.created_at = datetime.now(timezone.utc)

        # Strategy management
        self.strategy_allocations: dict[str, StrategyAllocation] = {}
        self.strategy_instances: dict[str, BaseStrategy] = {}
        self.strategy_performance: dict[str, deque] = defaultdict(lambda: deque(maxlen=252))  # 1 year  # noqa: E501

        # Position management
        self.portfolio_positions: dict[str, PortfolioPosition] = {}
        self.position_history: deque = deque(maxlen=10000)

        # Performance tracking
        self.portfolio_metrics_history: deque = deque(maxlen=1000)
        self.daily_returns: deque = deque(maxlen=252)  # 1 year of daily returns
        self.benchmark_returns: deque = deque(maxlen=252)  # SPY benchmark

        # Risk management
        self.risk_manager = get_risk_manager()
        self.position_sizer = get_position_sizer(initial_capital)
        self.drawdown_controller = DrawdownController()

        # Market analysis
        self.vix_analyzer = VIXAnalyzer(tradier_client=tradier_client)
        self.greeks_calculator = GreeksCalculator()
        self.gamma_calculator = GammaExposureCalculator()

        # Rebalancing
        self.last_rebalance = datetime.now(timezone.utc)
        self.rebalance_history: deque = deque(maxlen=100)
        self.pending_rebalances: list[RebalanceEvent] = []

        # Hedging
        self.hedge_positions: dict[str, HedgePosition] = {}
        self.hedge_effectiveness_history: deque = deque(maxlen=100)

        # Threading
        self.is_managing = False
        self._stop_event = threading.Event()
        self.management_thread: threading.Thread | None = None
        self.rebalance_thread: threading.Thread | None = None

        # Allocation method
        self.allocation_method = AllocationMethod(
            self.config.get('allocation_method', 'risk_parity')
        )

        # Initialize components
        self._initialize_portfolio()

        # Register with integration hub
        if HUB_AVAILABLE:
            hub = get_integration_hub()
            if hub:
                hub.register_module(self, dependencies=['SpyderE01_RiskManager'])

        self.logger.info(f"PortfolioManager initialized with ${initial_capital:,.0f} capital")

    # ==========================================================================
    # PUBLIC METHODS - STRATEGY MANAGEMENT
    # ==========================================================================

    def add_strategy(self, strategy_id: str, strategy_instance: BaseStrategy | None = None,
                    target_allocation: float = 0.10, strategy_config: dict | None = None) -> bool:
        """
        Add a new strategy to the portfolio.

        Args:
            strategy_id: Unique strategy identifier
            strategy_instance: Strategy instance (optional)
            target_allocation: Target allocation percentage (0-1)
            strategy_config: Strategy configuration

        Returns:
            Success status
        """
        try:
            if strategy_id in self.strategy_allocations:
                self.logger.warning("Strategy %s already exists", strategy_id)
                return False

            # Validate allocation
            if not (MIN_STRATEGY_ALLOCATION <= target_allocation <= MAX_STRATEGY_ALLOCATION):
                raise ValueError(f"Invalid allocation: {target_allocation}")

            # Check total allocation doesn't exceed limits
            total_allocation = sum(alloc.target_allocation for alloc in self.strategy_allocations.values())  # noqa: E501
            if total_allocation + target_allocation > (1.0 - MIN_CASH_RESERVE):
                raise ValueError("Total allocation would exceed maximum allowed")

            # Calculate allocated capital
            allocated_capital = self.current_capital * target_allocation

            # Create strategy allocation
            allocation = StrategyAllocation(
                strategy_id=strategy_id,
                strategy_name=strategy_config.get('name', strategy_id) if strategy_config else strategy_id,  # noqa: E501
                target_allocation=target_allocation,
                current_allocation=target_allocation,
                allocated_capital=allocated_capital,
                available_capital=allocated_capital,
                used_capital=0.0,
                performance_mtd=0.0,
                performance_ytd=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                correlation_to_portfolio=0.0,
                last_rebalance=datetime.now(timezone.utc)
            )

            # Store allocation
            self.strategy_allocations[strategy_id] = allocation

            # Store strategy instance if provided
            if strategy_instance:
                self.strategy_instances[strategy_id] = strategy_instance

                # Subscribe to strategy events
                self._subscribe_to_strategy_events(strategy_id, strategy_instance)

            # Update portfolio state
            self._update_portfolio_metrics()

            # Emit event
            self.event_manager.emit_event(Event(
                type=EventType.STRATEGY_ADDED,
                source=self.__class__.__name__,
                data={
                    'strategy_id': strategy_id,
                    'target_allocation': target_allocation,
                    'allocated_capital': allocated_capital
                }
            ))

            self.logger.info(f"Added strategy {strategy_id} with {target_allocation:.1%} allocation")  # noqa: E501
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"add_strategy: {strategy_id}")
            return False

    def remove_strategy(self, strategy_id: str, close_positions: bool = True) -> bool:
        """
        Remove a strategy from the portfolio.

        Args:
            strategy_id: Strategy to remove
            close_positions: Whether to close existing positions

        Returns:
            Success status
        """
        try:
            if strategy_id not in self.strategy_allocations:
                self.logger.warning("Strategy %s not found", strategy_id)
                return False

            allocation = self.strategy_allocations[strategy_id]

            # Close positions if requested
            if close_positions:
                self._close_strategy_positions(strategy_id)

            # Return capital to portfolio
            self.current_capital += allocation.available_capital

            # Remove from tracking
            del self.strategy_allocations[strategy_id]
            if strategy_id in self.strategy_instances:
                del self.strategy_instances[strategy_id]
            if strategy_id in self.strategy_performance:
                del self.strategy_performance[strategy_id]

            # Update metrics
            self._update_portfolio_metrics()

            # Emit event
            self.event_manager.emit_event(Event(
                type=EventType.STRATEGY_REMOVED,
                source=self.__class__.__name__,
                data={'strategy_id': strategy_id}
            ))

            self.logger.info("Removed strategy %s", strategy_id)
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"remove_strategy: {strategy_id}")
            return False

    def update_allocation(self, strategy_id: str, new_allocation: float) -> bool:
        """
        Update strategy allocation.

        Args:
            strategy_id: Strategy to update
            new_allocation: New allocation percentage

        Returns:
            Success status
        """
        try:
            if strategy_id not in self.strategy_allocations:
                self.logger.error("Strategy %s not found", strategy_id)
                return False

            if not (MIN_STRATEGY_ALLOCATION <= new_allocation <= MAX_STRATEGY_ALLOCATION):
                raise ValueError(f"Invalid allocation: {new_allocation}")

            old_allocation = self.strategy_allocations[strategy_id].target_allocation

            # Check if rebalancing is needed
            if abs(new_allocation - old_allocation) > STRATEGY_REALLOCATION_THRESHOLD:
                self._schedule_rebalance(RebalanceReason.STRATEGY_CHANGE, {
                    strategy_id: new_allocation
                })
            else:
                # Direct update for small changes
                self.strategy_allocations[strategy_id].target_allocation = new_allocation
                self._update_portfolio_metrics()

            self.logger.info(f"Updated {strategy_id} allocation: {old_allocation:.1%} → {new_allocation:.1%}")  # noqa: E501
            return True

        except Exception as e:
            self.error_handler.handle_error(e, f"update_allocation: {strategy_id}")
            return False

    # ==========================================================================
    # PUBLIC METHODS - PORTFOLIO OPERATIONS
    # ==========================================================================

    def start_management(self) -> bool:
        """
        Start portfolio management operations.

        Returns:
            Success status
        """
        try:
            if self.is_managing:
                self.logger.warning("Portfolio management already active")
                return True

            self.is_managing = True
            self._stop_event.clear()
            self.portfolio_state = PortfolioState.ACTIVE

            # Start management thread
            self.management_thread = threading.Thread(
                target=self._portfolio_management_loop,
                daemon=True,
                name="PortfolioManager"
            )
            self.management_thread.start()

            # Start rebalancing thread
            self.rebalance_thread = threading.Thread(
                target=self._rebalance_monitoring_loop,
                daemon=True,
                name="PortfolioRebalancer"
            )
            self.rebalance_thread.start()

            self.logger.info("Started portfolio management")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "start_management")
            return False

    def stop_management(self) -> bool:
        """
        Stop portfolio management operations.

        Returns:
            Success status
        """
        try:
            self.is_managing = False
            self._stop_event.set()
            self.portfolio_state = PortfolioState.SHUTDOWN

            # Wait for threads to complete
            if self.management_thread and self.management_thread.is_alive():
                self.management_thread.join(timeout=10.0)

            if self.rebalance_thread and self.rebalance_thread.is_alive():
                self.rebalance_thread.join(timeout=10.0)

            self.logger.info("Stopped portfolio management")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "stop_management")
            return False

    def rebalance_portfolio(self, reason: RebalanceReason = RebalanceReason.SCHEDULED,
                          target_allocations: dict[str, float] | None = None) -> bool:
        """
        Rebalance the portfolio.

        Args:
            reason: Reason for rebalancing
            target_allocations: Optional new target allocations

        Returns:
            Success status
        """
        try:
            self.portfolio_state = PortfolioState.REBALANCING

            # Calculate new allocations if not provided
            if target_allocations is None:
                target_allocations = self._calculate_optimal_allocations()

            # Create rebalance event
            rebalance_event = RebalanceEvent(
                rebalance_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                reason=reason,
                old_allocations={sid: alloc.current_allocation
                               for sid, alloc in self.strategy_allocations.items()},
                new_allocations=target_allocations,
                capital_movements={}
            )

            # Execute rebalancing
            start_time = time.time()
            success = self._execute_rebalance(rebalance_event)
            execution_time = time.time() - start_time

            # Update event
            rebalance_event.execution_time = execution_time
            rebalance_event.success = success

            # Store in history
            self.rebalance_history.append(rebalance_event)
            self.last_rebalance = datetime.now(timezone.utc)

            # Update state
            self.portfolio_state = PortfolioState.ACTIVE if success else PortfolioState.EMERGENCY

            # Emit event
            self.event_manager.emit_event(Event(
                type=EventType.PORTFOLIO_REBALANCED,
                source=self.__class__.__name__,
                data=asdict(rebalance_event)
            ))

            self.logger.info(f"Portfolio rebalancing {'successful' if success else 'failed'} in {execution_time:.2f}s")  # noqa: E501
            return success

        except Exception as e:
            self.error_handler.handle_error(e, "rebalance_portfolio")
            self.portfolio_state = PortfolioState.EMERGENCY
            return False

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """
        Get current portfolio metrics.

        Returns:
            Current portfolio metrics
        """
        try:
            # Calculate current positions and P&L
            total_positions_value = sum(pos.total_market_value for pos in self.portfolio_positions.values())  # noqa: E501
            unrealized_pnl = sum(pos.unrealized_pnl for pos in self.portfolio_positions.values())

            # Calculate Greeks
            portfolio_delta = sum(pos.net_delta for pos in self.portfolio_positions.values())
            portfolio_gamma = sum(pos.net_gamma for pos in self.portfolio_positions.values())
            portfolio_vega = sum(pos.net_vega for pos in self.portfolio_positions.values())
            portfolio_theta = sum(pos.net_theta for pos in self.portfolio_positions.values())

            # Calculate performance metrics
            total_value = self.current_capital + total_positions_value
            cash_balance = self.current_capital - sum(
                alloc.used_capital for alloc in self.strategy_allocations.values()
            )

            # Calculate returns
            total_return = (total_value - self.initial_capital) / self.initial_capital

            # Calculate risk metrics
            returns_array = np.array(list(self.daily_returns)) if self.daily_returns else np.array([0])  # noqa: E501
            volatility = np.std(returns_array) * np.sqrt(252) if len(returns_array) > 1 else 0.0
            sharpe_ratio = self._calculate_sharpe_ratio(returns_array)
            max_drawdown = self._calculate_max_drawdown()

            # Calculate VaR and ES
            var_95 = np.percentile(returns_array, 5) * total_value if len(returns_array) > 0 else 0.0  # noqa: E501
            es_95 = returns_array[returns_array <= np.percentile(returns_array, 5)].mean() * total_value if len(returns_array) > 10 else 0.0  # noqa: E501

            metrics = PortfolioMetrics(
                timestamp=datetime.now(timezone.utc),
                total_value=total_value,
                cash_balance=cash_balance,
                invested_capital=total_positions_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=self._calculate_realized_pnl(),
                daily_pnl=self._calculate_daily_pnl(),
                mtd_return=self._calculate_mtd_return(),
                ytd_return=self._calculate_ytd_return(),
                total_return=total_return,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=self._calculate_sortino_ratio(returns_array),
                max_drawdown=max_drawdown,
                current_drawdown=self._calculate_current_drawdown(),
                volatility=volatility,
                beta=self._calculate_beta(),
                value_at_risk=var_95,
                expected_shortfall=es_95,
                portfolio_delta=portfolio_delta,
                portfolio_gamma=portfolio_gamma,
                portfolio_vega=portfolio_vega,
                portfolio_theta=portfolio_theta,
                correlation_score=self._calculate_diversification_score(),
                strategy_count=len(self.strategy_allocations),
                active_positions=len(self.portfolio_positions)
            )

            # Store in history
            self.portfolio_metrics_history.append(metrics)

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, "get_portfolio_metrics")
            # Return default metrics on error
            return PortfolioMetrics(
                timestamp=datetime.now(timezone.utc),
                total_value=self.current_capital,
                cash_balance=self.current_capital,
                invested_capital=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                daily_pnl=0.0,
                mtd_return=0.0,
                ytd_return=0.0,
                total_return=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                current_drawdown=0.0,
                volatility=0.0,
                beta=0.0,
                value_at_risk=0.0,
                expected_shortfall=0.0,
                portfolio_delta=0.0,
                portfolio_gamma=0.0,
                portfolio_vega=0.0,
                portfolio_theta=0.0,
                correlation_score=0.0,
                strategy_count=0,
                active_positions=0
            )

    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================

    @property
    def state(self) -> "PortfolioState":
        """Alias for portfolio_state for backward compatibility."""
        return self.portfolio_state

    def get_portfolio_summary(self) -> dict[str, Any]:
        """
        Get comprehensive portfolio summary.

        Returns:
            Portfolio summary dictionary
        """
        try:
            metrics = self.get_portfolio_metrics()

            # Strategy performance summary
            strategy_summary = {}
            for strategy_id, allocation in self.strategy_allocations.items():
                strategy_summary[strategy_id] = {
                    'allocation': f"{allocation.current_allocation:.1%}",
                    'capital': f"${allocation.allocated_capital:,.0f}",
                    'performance_mtd': f"{allocation.performance_mtd:.2%}",
                    'performance_ytd': f"{allocation.performance_ytd:.2%}",
                    'sharpe_ratio': f"{allocation.sharpe_ratio:.2f}",
                    'max_drawdown': f"{allocation.max_drawdown:.2%}",
                    'status': allocation.status
                }

            # Risk summary
            risk_summary = {
                'portfolio_delta': f"{metrics.portfolio_delta:.0f}",
                'portfolio_gamma': f"{metrics.portfolio_gamma:.0f}",
                'portfolio_vega': f"{metrics.portfolio_vega:.0f}",
                'portfolio_theta': f"{metrics.portfolio_theta:.0f}",
                'max_delta_utilization': f"{abs(metrics.portfolio_delta)/MAX_PORTFOLIO_DELTA:.1%}",
                'max_gamma_utilization': f"{abs(metrics.portfolio_gamma)/MAX_PORTFOLIO_GAMMA:.1%}",
                'max_vega_utilization': f"{abs(metrics.portfolio_vega)/MAX_PORTFOLIO_VEGA:.1%}",
                'value_at_risk': f"${metrics.value_at_risk:,.0f}",
                'current_drawdown': f"{metrics.current_drawdown:.2%}"
            }


           # Performance summary
            performance_summary = {
                'total_return': f"{metrics.total_return:.2%}",
                'ytd_return': f"{metrics.ytd_return:.2%}",
                'mtd_return': f"{metrics.mtd_return:.2%}",
                'daily_pnl': f"${metrics.daily_pnl:,.0f}",
                'sharpe_ratio': f"{metrics.sharpe_ratio:.2f}",
                'sortino_ratio': f"{metrics.sortino_ratio:.2f}",
                'volatility': f"{metrics.volatility:.2%}",
                'max_drawdown': f"{metrics.max_drawdown:.2%}",
                'correlation_score': f"{metrics.correlation_score:.2f}"
            }

            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'portfolio_id': self.portfolio_id,
                'state': self.portfolio_state.value,
                'total_value': f"${metrics.total_value:,.0f}",
                'cash_balance': f"${metrics.cash_balance:,.0f}",
                'invested_capital': f"${metrics.invested_capital:,.0f}",
                'unrealized_pnl': f"${metrics.unrealized_pnl:,.0f}",
                'strategy_count': metrics.strategy_count,
                'active_positions': metrics.active_positions,
                'last_rebalance': self.last_rebalance.isoformat(),
                'strategies': strategy_summary,
                'risk_metrics': risk_summary,
                'performance_metrics': performance_summary,
                'allocation_method': self.allocation_method.value,
                'diversification_target': f"{DIVERSIFICATION_TARGET:.1%}",
                'cash_reserve': f"{MIN_CASH_RESERVE:.1%}"
            }

        except Exception as e:
            self.error_handler.handle_error(e, "get_portfolio_summary")
            return {'error': str(e)}

    # ==========================================================================
    # PRIVATE METHODS - PORTFOLIO OPERATIONS
    # ==========================================================================

    def _initialize_portfolio(self) -> None:
        """Initialize portfolio components.

        State stays INITIALIZING until ``start_management()`` flips it to ACTIVE
        once the management/rebalancing threads are actually running.  Avoids
        false-positive ACTIVE state before the portfolio is wired to the
        broker.
        """
        try:
            self.portfolio_metrics_history.clear()
            self._refresh_vix_snapshot()
            self.logger.info("Portfolio components initialized")

        except Exception as e:
            self.error_handler.handle_error(e, "_initialize_portfolio")

    def _refresh_vix_snapshot(self) -> float | None:
        """Refresh VIX data and return the current spot level when available."""
        try:
            analyzer = getattr(self, 'vix_analyzer', None)
            if analyzer is None:
                return None

            snapshot = None
            if hasattr(analyzer, 'update_vix_data'):
                snapshot = analyzer.update_vix_data()
            else:
                # Compatibility path for analyzers exposing only granular update methods.
                if hasattr(analyzer, '_update_realtime_data'):
                    analyzer._update_realtime_data()
                if hasattr(analyzer, '_update_volatility_metrics'):
                    analyzer._update_volatility_metrics()
                if hasattr(analyzer, 'get_current_metrics'):
                    snapshot = analyzer.get_current_metrics()

            if snapshot is None:
                return None

            for attr_name in ('vix_spot', 'vix', 'value'):
                value = getattr(snapshot, attr_name, None)
                if isinstance(value, int | float):
                    return float(value)

            if isinstance(snapshot, dict):
                for key in ('vix_spot', 'vix', 'value'):
                    value = snapshot.get(key)
                    if isinstance(value, int | float):
                        return float(value)

            return None

        except Exception as e:
            self.error_handler.handle_error(e, "_refresh_vix_snapshot")
            return None

    def _portfolio_management_loop(self) -> None:
        """Main portfolio management loop"""
        while self.is_managing:
            try:
                # Update portfolio metrics
                self._update_portfolio_metrics()

                # Check risk limits
                self._check_portfolio_risk_limits()

                # Update strategy performance
                self._update_strategy_performance()

                # Check for rebalancing needs
                self._check_rebalance_triggers()

                # Update hedge positions
                self._update_hedge_positions()

                # Sleep until next update
                self._stop_event.wait(PORTFOLIO_UPDATE_FREQUENCY)

            except Exception as e:
                self.error_handler.handle_error(e, "_portfolio_management_loop")
                self._stop_event.wait(10)  # Wait longer on error

    def _rebalance_monitoring_loop(self) -> None:
        """Rebalancing monitoring loop"""
        while self.is_managing:
            try:
                # Check if scheduled rebalance is due
                time_since_rebalance = datetime.now(timezone.utc) - self.last_rebalance
                if time_since_rebalance.total_seconds() >= DEFAULT_REBALANCE_FREQUENCY:
                    self.rebalance_portfolio(RebalanceReason.SCHEDULED)

                # Process pending rebalances
                if self.pending_rebalances:
                    self._process_pending_rebalances()

                self._stop_event.wait(REBALANCE_CHECK_FREQUENCY)

            except Exception as e:
                self.error_handler.handle_error(e, "_rebalance_monitoring_loop")
                self._stop_event.wait(60)

    def _update_portfolio_metrics(self) -> None:
        """Update portfolio metrics"""
        try:
            # Update positions from strategies
            self._consolidate_positions()

            # Calculate current metrics
            metrics = self.get_portfolio_metrics()

            # Update daily returns
            if len(self.portfolio_metrics_history) > 0:
                previous_value = self.portfolio_metrics_history[-1].total_value
                daily_return = (metrics.total_value - previous_value) / previous_value
                self.daily_returns.append(daily_return)

        except Exception as e:
            self.error_handler.handle_error(e, "_update_portfolio_metrics")

    def _consolidate_positions(self) -> None:
        """Consolidate positions across all strategies"""
        try:
            consolidated_positions = {}

            # Collect positions from all strategies
            for strategy_id, strategy in self.strategy_instances.items():
                if hasattr(strategy, 'get_current_positions'):
                    positions = strategy.get_current_positions()

                    for symbol, position in positions.items():
                        if symbol not in consolidated_positions:
                            consolidated_positions[symbol] = PortfolioPosition(
                                symbol=symbol,
                                strategy_positions={},
                                net_quantity=0,
                                net_delta=0.0,
                                net_gamma=0.0,
                                net_vega=0.0,
                                net_theta=0.0,
                                total_cost_basis=0.0,
                                total_market_value=0.0,
                                unrealized_pnl=0.0,
                                days_in_trade=0,
                                risk_contribution=0.0
                            )

                        # Add strategy position
                        cons_pos = consolidated_positions[symbol]
                        cons_pos.strategy_positions[strategy_id] = position

                        # Aggregate metrics
                        cons_pos.net_quantity += position.get('quantity', 0)
                        cons_pos.net_delta += position.get('delta', 0)
                        cons_pos.net_gamma += position.get('gamma', 0)
                        cons_pos.net_vega += position.get('vega', 0)
                        cons_pos.net_theta += position.get('theta', 0)
                        cons_pos.total_cost_basis += position.get('cost_basis', 0)
                        cons_pos.total_market_value += position.get('market_value', 0)
                        cons_pos.unrealized_pnl += position.get('unrealized_pnl', 0)

            # Update portfolio positions
            self.portfolio_positions = consolidated_positions

        except Exception as e:
            self.error_handler.handle_error(e, "_consolidate_positions")

    def _check_portfolio_risk_limits(self) -> None:
        """Check portfolio-level risk limits"""
        try:
            metrics = self.get_portfolio_metrics()
            violations = []

            # Check Greek limits
            if abs(metrics.portfolio_delta) > MAX_PORTFOLIO_DELTA:
                violations.append(f"Delta limit exceeded: {metrics.portfolio_delta:.0f}")

            if abs(metrics.portfolio_gamma) > MAX_PORTFOLIO_GAMMA:
                violations.append(f"Gamma limit exceeded: {metrics.portfolio_gamma:.0f}")

            if abs(metrics.portfolio_vega) > MAX_PORTFOLIO_VEGA:
                violations.append(f"Vega limit exceeded: {metrics.portfolio_vega:.0f}")

            if metrics.portfolio_theta < MAX_PORTFOLIO_THETA:
                violations.append(f"Theta limit exceeded: {metrics.portfolio_theta:.0f}")

            # Check drawdown
            if metrics.current_drawdown > PORTFOLIO_DRAWDOWN_THRESHOLD:
                violations.append(f"Drawdown threshold exceeded: {metrics.current_drawdown:.2%}")
                self._trigger_defensive_mode()

            # Emit violations
            if violations:
                self.event_manager.emit_event(Event(
                    type=EventType.RISK_LIMIT_BREACH,
                    source=self.__class__.__name__,
                    data={'violations': violations}
                ))

                self.logger.warning("Portfolio risk violations: %s", violations)

        except Exception as e:
            self.error_handler.handle_error(e, "_check_portfolio_risk_limits")

    def _update_strategy_performance(self) -> None:
        """Update individual strategy performance metrics"""
        try:
            for strategy_id, allocation in self.strategy_allocations.items():
                if strategy_id in self.strategy_instances:
                    strategy = self.strategy_instances[strategy_id]

                    # Get strategy performance
                    if hasattr(strategy, 'get_performance_metrics'):
                        perf = strategy.get_performance_metrics()

                        # Update allocation metrics
                        allocation.performance_mtd = perf.get('mtd_return', 0.0)
                        allocation.performance_ytd = perf.get('ytd_return', 0.0)
                        allocation.sharpe_ratio = perf.get('sharpe_ratio', 0.0)
                        allocation.max_drawdown = perf.get('max_drawdown', 0.0)
                        allocation.volatility = perf.get('volatility', 0.0)

                        # Store in history
                        self.strategy_performance[strategy_id].append({
                            'timestamp': datetime.now(timezone.utc),
                            'return': perf.get('daily_return', 0.0),
                            'value': perf.get('total_value', allocation.allocated_capital)
                        })

                        # Calculate correlation to portfolio
                        allocation.correlation_to_portfolio = self._calculate_strategy_correlation(strategy_id)  # noqa: E501

        except Exception as e:
            self.error_handler.handle_error(e, "_update_strategy_performance")

    def _check_rebalance_triggers(self) -> None:
        """Check if rebalancing is needed"""
        try:
            rebalance_needed = False
            reason = None

            # Check allocation drift
            max_drift = 0.0
            for _strategy_id, allocation in self.strategy_allocations.items():
                drift = abs(allocation.current_allocation - allocation.target_allocation)
                max_drift = max(max_drift, drift)

                if drift > STRATEGY_REALLOCATION_THRESHOLD:
                    rebalance_needed = True
                    reason = RebalanceReason.DRIFT_THRESHOLD
                    break

            # Check strategy performance triggers
            for _strategy_id, allocation in self.strategy_allocations.items():
                if allocation.performance_mtd < STRATEGY_UNDERPERFORMANCE_THRESHOLD:
                    rebalance_needed = True
                    reason = RebalanceReason.PERFORMANCE_TRIGGER
                    break

            # Check market regime changes
            if hasattr(self, 'vix_analyzer'):
                vix_regime = self.vix_analyzer.analyze_regime()
                if hasattr(self, '_last_vix_regime'):
                    if vix_regime.current_regime != self._last_vix_regime:
                        rebalance_needed = True
                        reason = RebalanceReason.MARKET_REGIME_CHANGE
                self._last_vix_regime = vix_regime.current_regime

            # Schedule rebalancing if needed
            if rebalance_needed and reason:
                self._schedule_rebalance(reason)

        except Exception as e:
            self.error_handler.handle_error(e, "_check_rebalance_triggers")

    def _schedule_rebalance(self, reason: RebalanceReason,
                          target_allocations: dict[str, float] | None = None) -> None:
        """Schedule a portfolio rebalance"""
        try:
            rebalance_event = RebalanceEvent(
                rebalance_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc),
                reason=reason,
                old_allocations={sid: alloc.current_allocation
                               for sid, alloc in self.strategy_allocations.items()},
                new_allocations=target_allocations or {},
                capital_movements={}
            )

            self.pending_rebalances.append(rebalance_event)

            self.logger.info("Scheduled rebalance due to: %s", reason.value)

        except Exception as e:
            self.error_handler.handle_error(e, "_schedule_rebalance")

    def _process_pending_rebalances(self) -> None:
        """Process pending rebalance events"""
        try:
            while self.pending_rebalances:
                rebalance_event = self.pending_rebalances.pop(0)

                # Calculate optimal allocations if not provided
                if not rebalance_event.new_allocations:
                    rebalance_event.new_allocations = self._calculate_optimal_allocations()

                # Execute rebalance
                success = self._execute_rebalance(rebalance_event)

                if success:
                    self.rebalance_history.append(rebalance_event)
                    self.last_rebalance = datetime.now(timezone.utc)
                else:
                    self.logger.error("Rebalance failed: %s", rebalance_event.rebalance_id)

        except Exception as e:
            self.error_handler.handle_error(e, "_process_pending_rebalances")

    def _execute_rebalance(self, rebalance_event: RebalanceEvent) -> bool:
        """Execute a rebalance event"""
        try:
            # Calculate capital movements needed
            for strategy_id, new_allocation in rebalance_event.new_allocations.items():
                if strategy_id in self.strategy_allocations:
                    old_allocation = self.strategy_allocations[strategy_id].current_allocation
                    capital_change = (new_allocation - old_allocation) * self.current_capital
                    rebalance_event.capital_movements[strategy_id] = capital_change

            # Execute capital movements
            for strategy_id, capital_change in rebalance_event.capital_movements.items():
                if strategy_id in self.strategy_allocations:
                    allocation = self.strategy_allocations[strategy_id]

                    # Update allocation
                    allocation.current_allocation = rebalance_event.new_allocations[strategy_id]
                    allocation.target_allocation = rebalance_event.new_allocations[strategy_id]
                    allocation.allocated_capital += capital_change
                    allocation.available_capital += capital_change
                    allocation.last_rebalance = datetime.now(timezone.utc)

                    # Notify strategy of capital change
                    if strategy_id in self.strategy_instances:
                        strategy = self.strategy_instances[strategy_id]
                        if hasattr(strategy, 'update_capital'):
                            strategy.update_capital(allocation.allocated_capital)

            rebalance_event.success = True
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "_execute_rebalance")
            rebalance_event.success = False
            return False

    def _calculate_optimal_allocations(self) -> dict[str, float]:
        """Calculate optimal portfolio allocations"""
        try:
            if self.allocation_method == AllocationMethod.EQUAL_WEIGHT:
                return self._calculate_equal_weight_allocations()
            elif self.allocation_method == AllocationMethod.RISK_PARITY:
                return self._calculate_risk_parity_allocations()
            elif self.allocation_method == AllocationMethod.PERFORMANCE_BASED:
                return self._calculate_performance_based_allocations()
            elif self.allocation_method == AllocationMethod.VOLATILITY_ADJUSTED:
                return self._calculate_volatility_adjusted_allocations()
            elif self.allocation_method == AllocationMethod.KELLY_CRITERION:
                return self._calculate_kelly_allocations()
            elif self.allocation_method == AllocationMethod.RISKFOLIO_OPTIMIZED:
                return self._calculate_riskfolio_allocations()
            else:
                return self._calculate_risk_parity_allocations()  # Default

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_optimal_allocations")
            # Return current allocations on error
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_risk_parity_allocations(self) -> dict[str, float]:
        """Calculate risk parity allocations"""
        try:
            allocations = {}
            total_inverse_vol = 0.0

            # Calculate inverse volatility weights
            for strategy_id, allocation in self.strategy_allocations.items():
                if allocation.volatility > 0:
                    inverse_vol = 1.0 / allocation.volatility
                    total_inverse_vol += inverse_vol
                    allocations[strategy_id] = inverse_vol
                else:
                    allocations[strategy_id] = 1.0
                    total_inverse_vol += 1.0

            # Normalize to sum to (1 - cash_reserve)
            target_sum = 1.0 - MIN_CASH_RESERVE
            for strategy_id in allocations:
                allocations[strategy_id] = (allocations[strategy_id] / total_inverse_vol) * target_sum  # noqa: E501

                # Apply min/max constraints
                allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                             min(MAX_STRATEGY_ALLOCATION, allocations[strategy_id]))

            return allocations

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_risk_parity_allocations")
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_equal_weight_allocations(self) -> dict[str, float]:
        """Calculate equal weight allocations"""
        try:
            num_strategies = len(self.strategy_allocations)
            if num_strategies == 0:
                return {}

            target_sum = 1.0 - MIN_CASH_RESERVE
            equal_weight = target_sum / num_strategies

            # Apply constraints
            equal_weight = max(MIN_STRATEGY_ALLOCATION,
                             min(MAX_STRATEGY_ALLOCATION, equal_weight))

            return {strategy_id: equal_weight for strategy_id in self.strategy_allocations}

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_equal_weight_allocations")
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_performance_based_allocations(self) -> dict[str, float]:
        """Calculate performance-based allocations"""
        try:
            allocations = {}
            total_score = 0.0

            # Calculate performance scores (Sharpe ratio weighted)
            for strategy_id, allocation in self.strategy_allocations.items():
                score = max(0.1, allocation.sharpe_ratio + 1.0)  # Ensure positive scores
                total_score += score
                allocations[strategy_id] = score

            # Normalize
            target_sum = 1.0 - MIN_CASH_RESERVE
            for strategy_id in allocations:
                allocations[strategy_id] = (allocations[strategy_id] / total_score) * target_sum

                # Apply constraints
                allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                             min(MAX_STRATEGY_ALLOCATION, allocations[strategy_id]))

            return allocations

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_performance_based_allocations")
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_volatility_adjusted_allocations(self) -> dict[str, float]:
        """Calculate volatility-adjusted allocations"""
        try:
            # Target portfolio volatility
            target_vol = 0.15  # 15% annualized

            allocations = {}
            for strategy_id, allocation in self.strategy_allocations.items():
                if allocation.volatility > 0:
                    vol_adjusted = target_vol / allocation.volatility
                    allocations[strategy_id] = vol_adjusted
                else:
                    allocations[strategy_id] = 1.0

            # Normalize
            total_weight = sum(allocations.values())
            target_sum = 1.0 - MIN_CASH_RESERVE

            for strategy_id in allocations:
                allocations[strategy_id] = (allocations[strategy_id] / total_weight) * target_sum

                # Apply constraints
                allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                             min(MAX_STRATEGY_ALLOCATION, allocations[strategy_id]))

            return allocations

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_volatility_adjusted_allocations")
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_kelly_allocations(self) -> dict[str, float]:
        """Calculate Kelly criterion allocations"""
        try:
            allocations = {}

            for strategy_id, allocation in self.strategy_allocations.items():
                if allocation.volatility > 0 and allocation.performance_ytd != 0:
                    # Simplified Kelly: (expected_return - risk_free_rate) / variance
                    excess_return = allocation.performance_ytd - 0.02  # Assume 2% risk-free rate
                    variance = allocation.volatility ** 2
                    kelly_fraction = excess_return / variance if variance > 0 else 0.0

                    # Apply Kelly reduction factor (typically 25-50% of full Kelly)
                    kelly_fraction *= 0.25

                    allocations[strategy_id] = max(0.0, kelly_fraction)
                else:
                    allocations[strategy_id] = MIN_STRATEGY_ALLOCATION

            # Normalize and apply constraints
            total_kelly = sum(allocations.values())
            target_sum = 1.0 - MIN_CASH_RESERVE

            if total_kelly > 0:
                for strategy_id in allocations:
                    allocations[strategy_id] = (allocations[strategy_id] / total_kelly) * target_sum
                    allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                                 min(MAX_STRATEGY_ALLOCATION, allocations[strategy_id]))  # noqa: E501
            else:
                # Fall back to equal weight
                return self._calculate_equal_weight_allocations()

            return allocations

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_kelly_allocations")
            return {sid: alloc.current_allocation for sid, alloc in self.strategy_allocations.items()}  # noqa: E501

    def _calculate_riskfolio_allocations(self) -> dict[str, float]:
        """
        Calculate allocations using RiskFolio-Lib optimization.

        Builds a returns matrix from strategy allocation history and
        delegates to ``optimize_portfolio_riskfolio``.  Falls back to
        risk parity if insufficient data is available.

        Returns:
            Dictionary of strategy allocations.
        """
        try:
            # Build returns data from strategy allocations
            frames = {}
            for sid, alloc in self.strategy_allocations.items():
                if hasattr(alloc, 'return_history') and len(getattr(alloc, 'return_history', [])) > 5:  # noqa: E501
                    frames[sid] = pd.Series(alloc.return_history)
                elif hasattr(alloc, 'daily_returns') and isinstance(alloc.daily_returns, pd.Series):
                    if len(alloc.daily_returns) > 5:
                        frames[sid] = alloc.daily_returns

            if len(frames) < 2:
                self.logger.info("Insufficient data for RiskFolio — falling back to risk parity")
                return self._calculate_risk_parity_allocations()

            returns_data = pd.DataFrame(frames).dropna()
            if len(returns_data) < 10:
                return self._calculate_risk_parity_allocations()

            result = self.optimize_portfolio_riskfolio(
                returns_data=returns_data,
                objective='max_sharpe',
                risk_measure='CVaR'
            )

            weights = result.get('weights', {})
            if not weights:
                return self._calculate_risk_parity_allocations()

            # Apply constraints
            target_sum = 1.0 - MIN_CASH_RESERVE
            total = sum(weights.values())
            if total > 0:
                for sid in weights:
                    weights[sid] = (weights[sid] / total) * target_sum
                    weights[sid] = max(MIN_STRATEGY_ALLOCATION,
                                      min(MAX_STRATEGY_ALLOCATION, weights[sid]))

            return weights

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_riskfolio_allocations")
            return self._calculate_risk_parity_allocations()

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================

    def _calculate_sharpe_ratio(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio"""
        try:
            if len(returns) < 2:
                return 0.0

            excess_returns = returns - 0.02/252  # Daily risk-free rate
            return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0.0  # noqa: E501

        except Exception as e:
            self.logger.debug("_calculate_sharpe_ratio calculation error: %s", e)
            return 0.0

    def _calculate_sortino_ratio(self, returns: np.ndarray) -> float:
        """Calculate Sortino ratio"""
        try:
            if len(returns) < 2:
                return 0.0

            excess_returns = returns - 0.02/252
            downside_returns = excess_returns[excess_returns < 0]

            if len(downside_returns) == 0:
                return np.inf if np.mean(excess_returns) > 0 else 0.0

            downside_std = np.std(downside_returns)
            return np.mean(excess_returns) / downside_std * np.sqrt(252) if downside_std > 0 else 0.0  # noqa: E501

        except Exception as e:
            self.logger.debug("_calculate_sortino_ratio calculation error: %s", e)
            return 0.0

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        try:
            if len(self.portfolio_metrics_history) < 2:
                return 0.0

            values = [m.total_value for m in self.portfolio_metrics_history]
            peak = values[0]
            max_dd = 0.0

            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak
                max_dd = max(max_dd, drawdown)

            return max_dd

        except Exception as e:
            self.logger.debug("_calculate_max_drawdown calculation error: %s", e)
            return 0.0

    def _calculate_current_drawdown(self) -> float:
        """Calculate current drawdown"""
        try:
            if len(self.portfolio_metrics_history) < 2:
                return 0.0

            values = [m.total_value for m in self.portfolio_metrics_history]
            current_value = values[-1]
            peak_value = max(values)

            return (peak_value - current_value) / peak_value if peak_value > 0 else 0.0

        except Exception as e:
            self.logger.debug("_calculate_current_drawdown calculation error: %s", e)
            return 0.0

    def _calculate_beta(self) -> float:
        """Calculate portfolio beta relative to SPY"""
        try:
            if len(self.daily_returns) < 30 or len(self.benchmark_returns) < 30:
                return 1.0

            portfolio_returns = np.array(list(self.daily_returns)[-30:])
            benchmark_returns = np.array(list(self.benchmark_returns)[-30:])

            covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
            benchmark_variance = np.var(benchmark_returns)

            return covariance / benchmark_variance if benchmark_variance > 0 else 1.0

        except Exception as e:
            self.logger.debug("_calculate_beta calculation error: %s", e)
            return 1.0

    def _calculate_diversification_score(self) -> float:
        """Calculate portfolio diversification score"""
        try:
            if len(self.strategy_allocations) < 2:
                return 0.0

            # Calculate weighted average correlation
            total_correlation = 0.0
            total_weight = 0.0

            strategies = list(self.strategy_allocations.keys())
            for i, strategy1 in enumerate(strategies):
                for _j, strategy2 in enumerate(strategies[i+1:], i+1):
                    corr = self._calculate_strategy_pair_correlation(strategy1, strategy2)
                    weight1 = self.strategy_allocations[strategy1].current_allocation
                    weight2 = self.strategy_allocations[strategy2].current_allocation

                    total_correlation += abs(corr) * weight1 * weight2
                    total_weight += weight1 * weight2

            avg_correlation = total_correlation / total_weight if total_weight > 0 else 0.0
            return 1.0 - avg_correlation  # Higher score = better diversification

        except Exception as e:
            self.logger.debug("_calculate_diversification_score calculation error: %s", e)
            return 0.5

    def _calculate_strategy_correlation(self, strategy_id: str) -> float:
        """Calculate strategy correlation to rest of portfolio"""
        try:
            if strategy_id not in self.strategy_performance:
                return 0.0

            strategy_returns = [p['return'] for p in self.strategy_performance[strategy_id]]

            if len(strategy_returns) < 10:
                return 0.0

            # Calculate portfolio returns excluding this strategy
            other_returns = []
            for other_id, other_performance in self.strategy_performance.items():
                if other_id != strategy_id:
                    other_returns.extend([p['return'] for p in other_performance])

            if len(other_returns) < 10:
                return 0.0

            # Calculate correlation
            min_len = min(len(strategy_returns), len(other_returns))
            if min_len < 2:
                return 0.0

            corr_matrix = np.corrcoef(
                strategy_returns[-min_len:],
                other_returns[-min_len:]
            )

            return corr_matrix[0, 1] if not np.isnan(corr_matrix[0, 1]) else 0.0

        except Exception as e:
            self.logger.debug("_calculate_strategy_correlation calculation error: %s", e)
            return 0.0

    def _calculate_strategy_pair_correlation(self, strategy1: str, strategy2: str) -> float:
        """Calculate correlation between two strategies"""
        try:
            if (strategy1 not in self.strategy_performance or
                strategy2 not in self.strategy_performance):
                return 0.0

            returns1 = [p['return'] for p in self.strategy_performance[strategy1]]
            returns2 = [p['return'] for p in self.strategy_performance[strategy2]]

            min_len = min(len(returns1), len(returns2))
            if min_len < 2:
                return 0.0

            corr_matrix = np.corrcoef(returns1[-min_len:], returns2[-min_len:])
            return corr_matrix[0, 1] if not np.isnan(corr_matrix[0, 1]) else 0.0

        except Exception as e:
            self.logger.debug("_calculate_strategy_pair_correlation calculation error: %s", e)
            return 0.0

    def _calculate_realized_pnl(self) -> float:
        """Calculate realized P&L"""
        # Placeholder - would integrate with actual trade tracking
        return 0.0

    def _calculate_daily_pnl(self) -> float:
        """Calculate daily P&L"""
        try:
            if len(self.portfolio_metrics_history) < 2:
                return 0.0

            current_value = self.portfolio_metrics_history[-1].total_value
            previous_value = self.portfolio_metrics_history[-2].total_value

            return current_value - previous_value

        except Exception as e:
            self.logger.debug("_calculate_daily_pnl calculation error: %s", e)
            return 0.0

    def _calculate_mtd_return(self) -> float:
        """Calculate month-to-date return"""
        try:
            if not self.portfolio_metrics_history:
                return 0.0

            current_value = self.portfolio_metrics_history[-1].total_value

            # Find start of current month
            current_date = datetime.now(timezone.utc)
            month_start = current_date.replace(day=1)

            # Find closest metric to month start
            month_start_value = self.initial_capital
            for metric in self.portfolio_metrics_history:
                if metric.timestamp >= month_start:
                    month_start_value = metric.total_value
                    break

            return (current_value - month_start_value) / month_start_value if month_start_value > 0 else 0.0  # noqa: E501

        except Exception as e:
            self.logger.debug("_calculate_mtd_return calculation error: %s", e)
            return 0.0

    def _calculate_ytd_return(self) -> float:
        """Calculate year-to-date return"""
        try:
            if not self.portfolio_metrics_history:
                return 0.0

            current_value = self.portfolio_metrics_history[-1].total_value

            # Find start of current year
            current_date = datetime.now(timezone.utc)
            year_start = current_date.replace(month=1, day=1)

            # Find closest metric to year start
            year_start_value = self.initial_capital
            for metric in self.portfolio_metrics_history:
                if metric.timestamp >= year_start:
                    year_start_value = metric.total_value
                    break

            return (current_value - year_start_value) / year_start_value if year_start_value > 0 else 0.0  # noqa: E501

        except Exception as e:
            self.logger.debug("_calculate_ytd_return calculation error: %s", e)
            return 0.0

    # ==========================================================================
    # PRIVATE METHODS - HELPER FUNCTIONS
    # ==========================================================================

    def _subscribe_to_strategy_events(self, strategy_id: str, strategy: BaseStrategy) -> None:
        """Subscribe to strategy events"""
        try:
            # Subscribe to strategy signals and position updates
            if hasattr(strategy, 'subscribe_to_events'):
                strategy.subscribe_to_events(self._handle_strategy_event)

        except Exception as e:
            self.error_handler.handle_error(e, f"_subscribe_to_strategy_events: {strategy_id}")

    def _handle_strategy_event(self, event: Event) -> None:
        """Handle events from strategies"""
        try:
            if event.type == EventType.POSITION_OPENED:
                self._handle_position_opened(event)
            elif event.type == EventType.POSITION_CLOSED:
                self._handle_position_closed(event)
            elif event.type == EventType.SIGNAL_GENERATED:
                self._handle_strategy_signal(event)

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_strategy_event")

    def _handle_position_opened(self, event: Event) -> None:
        """Handle position opened event"""
        try:
            strategy_id = event.data.get('strategy_id')
            position_info = event.data.get('position')

            if strategy_id in self.strategy_allocations:
                allocation = self.strategy_allocations[strategy_id]
                position_cost = position_info.get('cost', 0)

                # Update used capital
                allocation.used_capital += position_cost
                allocation.available_capital -= position_cost

                # Update portfolio positions
                self._consolidate_positions()

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_position_opened")

    def _handle_position_closed(self, event: Event) -> None:
        """Handle position closed event"""
        try:
            strategy_id = event.data.get('strategy_id')
            position_info = event.data.get('position')

            if strategy_id in self.strategy_allocations:
                allocation = self.strategy_allocations[strategy_id]
                position_cost = position_info.get('cost', 0)
                realized_pnl = position_info.get('realized_pnl', 0)

                # Update capital
                allocation.used_capital -= position_cost
                allocation.available_capital += position_cost + realized_pnl

                # Update portfolio positions
                self._consolidate_positions()

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_position_closed")

    def _handle_strategy_signal(self, event: Event) -> None:
        """Handle strategy signal"""
        try:
            strategy_id = event.data.get('strategy_id')
            signal = event.data.get('signal')

            # Log signal for analysis
            self.logger.info("Strategy signal from %s: %s", strategy_id, signal)

            # Could implement signal aggregation logic here

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_strategy_signal")

    def _close_strategy_positions(self, strategy_id: str) -> None:
        """Close all positions for a strategy"""
        try:
            if strategy_id in self.strategy_instances:
                strategy = self.strategy_instances[strategy_id]
                if hasattr(strategy, 'close_all_positions'):
                    strategy.close_all_positions()

        except Exception as e:
            self.error_handler.handle_error(e, f"_close_strategy_positions: {strategy_id}")

    def _trigger_defensive_mode(self) -> None:
        """Trigger defensive portfolio mode"""
        try:
            self.portfolio_state = PortfolioState.DEFENSIVE

            # Reduce position sizes across all strategies
            for strategy_id, _allocation in self.strategy_allocations.items():
                if strategy_id in self.strategy_instances:
                    strategy = self.strategy_instances[strategy_id]
                    if hasattr(strategy, 'reduce_position_size'):
                        strategy.reduce_position_size(0.5)  # 50% reduction

            # Emit defensive mode event
            self.event_manager.emit_event(Event(
                type=EventType.PORTFOLIO_DEFENSIVE_MODE,
                source=self.__class__.__name__,
                data={'reason': 'drawdown_threshold_exceeded'}
            ))

            self.logger.warning("Activated defensive portfolio mode")

        except Exception as e:
            self.error_handler.handle_error(e, "_trigger_defensive_mode")

    def _update_hedge_positions(self) -> None:
        """Update portfolio hedge positions"""
        try:
            # Check if hedging is needed
            metrics = self.get_portfolio_metrics()

            # Delta hedging
            if abs(metrics.portfolio_delta) > MAX_PORTFOLIO_DELTA * 0.8:
                self._consider_delta_hedge(metrics.portfolio_delta)

            # Volatility hedging
            vix_spot = self._refresh_vix_snapshot()
            if vix_spot is not None and vix_spot > 25:  # High VIX
                self._consider_volatility_hedge()

        except Exception as e:
            self.error_handler.handle_error(e, "_update_hedge_positions")

    def _consider_delta_hedge(self, portfolio_delta: float) -> None:
        """Consider delta hedging"""
        try:
            # Simplified delta hedging logic
            if abs(portfolio_delta) > MAX_PORTFOLIO_DELTA * 0.9:
                hedge_delta = -portfolio_delta * 0.5  # Hedge 50% of exposure

                # Create hedge position (simplified)
                hedge = HedgePosition(
                    hedge_id=str(uuid.uuid4()),
                    hedge_type=HedgeType.DELTA_HEDGE,
                    hedge_ratio=0.5,
                    target_exposure=hedge_delta,
                    hedge_instruments=[{'type': 'SPY_shares', 'quantity': int(hedge_delta)}],
                    cost_basis=abs(hedge_delta) * 450,  # Assume SPY at $450
                    effectiveness=0.95,
                    created_at=datetime.now(timezone.utc)
                )

                self.hedge_positions[hedge.hedge_id] = hedge

                self.logger.info(f"Created delta hedge: {hedge_delta:.0f} delta")

        except Exception as e:
            self.error_handler.handle_error(e, "_consider_delta_hedge")

    def _consider_volatility_hedge(self) -> None:
        """Consider volatility hedging"""
        try:
            # Check if volatility hedge already exists
            vol_hedges = [h for h in self.hedge_positions.values()
                         if h.hedge_type == HedgeType.VOLATILITY_HEDGE and h.is_active]

            if not vol_hedges:
                # Create VIX hedge (simplified)
                hedge = HedgePosition(
                    hedge_id=str(uuid.uuid4()),
                    hedge_type=HedgeType.VOLATILITY_HEDGE,
                    hedge_ratio=0.2,
                    target_exposure=self.current_capital * 0.02,  # 2% of portfolio
                    hedge_instruments=[{'type': 'VIX_calls', 'quantity': 10}],
                    cost_basis=self.current_capital * 0.01,  # 1% cost
                    effectiveness=0.8,
                    created_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=30)
                )

                self.hedge_positions[hedge.hedge_id] = hedge

                self.logger.info("Created volatility hedge")

        except Exception as e:
            self.error_handler.handle_error(e, "_consider_volatility_hedge")

    # --------------------------------------------------------------------------
    # RISKFOLIO-LIB: DEFAULT OPTIMIZATION BACKEND
    # --------------------------------------------------------------------------

    def optimize_portfolio_riskfolio(
        self,
        returns_data: pd.DataFrame,
        objective: str = 'max_sharpe',
        risk_measure: str = 'CVaR',
        max_weight: float = 0.30,
    ) -> dict[str, Any]:
        """
        Wire RiskFolio-Lib as the default portfolio optimization backend.

        Provides CVaR, HRP, risk parity, and Black-Litterman optimization
        modes that complement the existing scipy-based approach.

        Args:
            returns_data: DataFrame of asset returns (columns = assets).
            objective: 'max_sharpe', 'min_risk', 'max_return', 'risk_parity', 'hrp'.
            risk_measure: Risk measure for optimization ('MV', 'CVaR', 'CDaR', 'MDD').
            max_weight: Maximum weight per asset.

        Returns:
            Optimized weights and portfolio statistics.
        """
        try:
            import riskfolio as rp
        except ImportError:
            self.logger.warning("riskfolio not installed", exc_info=True)
            n = returns_data.shape[1]
            return {'weights': {col: 1.0 / n for col in returns_data.columns},
                    '_backend': 'fallback'}

        port = rp.Portfolio(returns=returns_data)
        port.assets_stats(method_mu='hist', method_cov='ledoit_wolf')

        weights = None
        if objective == 'hrp':
            weights = port.optimization(
                model='HRP', codependence='pearson', rm=risk_measure,
                rf=0.05 / 252, linkage='single', leaf_order=True)
        elif objective == 'risk_parity':
            weights = port.rp_optimization(
                model='Classic', rm=risk_measure, rf=0.05 / 252, b=None)
        else:
            obj_map = {'max_sharpe': 'Sharpe', 'min_risk': 'MinRisk',
                       'max_return': 'MaxRet'}
            rp_obj = obj_map.get(objective, 'Sharpe')
            weights = port.optimization(
                model='Classic', rm=risk_measure, obj=rp_obj, rf=0.05 / 252)

        if weights is not None and not weights.empty:
            weight_dict = {col: float(weights.loc[col].iloc[0]) for col in weights.index}
            # Compute portfolio stats
            port_ret = sum(weight_dict.get(c, 0) * returns_data[c].mean()
                          for c in returns_data.columns) * 252
            port_vol = float(np.sqrt(
                np.array([weight_dict.get(c, 0) for c in returns_data.columns]).T @
                returns_data.cov().values * 252 @
                np.array([weight_dict.get(c, 0) for c in returns_data.columns])))

            result = {
                'weights': weight_dict,
                'expected_return': float(port_ret),
                'expected_volatility': port_vol,
                'sharpe_ratio': float(port_ret / (port_vol + 1e-8)),
                'objective': objective,
                'risk_measure': risk_measure,
                '_backend': 'riskfolio',
            }
            self.logger.info(f"RiskFolio optimization ({objective}/{risk_measure}): "
                             f"Sharpe={result['sharpe_ratio']:.4f}")
            return result

        n = returns_data.shape[1]
        return {'weights': {col: 1.0 / n for col in returns_data.columns},
                '_backend': 'fallback'}

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_portfolio_manager(initial_capital: float = DEFAULT_PORTFOLIO_SIZE,
                           config: dict[str, Any] | None = None) -> PortfolioManager:
    """
    Factory function to create portfolio manager.

    Args:
        initial_capital: Initial portfolio capital
        config: Configuration dictionary

    Returns:
        Configured PortfolioManager instance
    """
    return PortfolioManager(initial_capital, config)

def calculate_portfolio_correlation(strategy_returns: dict[str, list[float]]) -> np.ndarray:
    """
    Calculate correlation matrix for strategies.

    Args:
        strategy_returns: Dictionary of strategy returns

    Returns:
        Correlation matrix
    """
    try:
        # Convert to DataFrame
        df = pd.DataFrame(strategy_returns)

        # Calculate correlation matrix
        return df.corr().values

    except Exception as e:
        _module_logger.debug("calculate_portfolio_correlation error: %s", e)
        # Return identity matrix on error
        n = len(strategy_returns)
        return np.eye(n)

def optimize_portfolio_allocation(expected_returns: np.ndarray,
                                cov_matrix: np.ndarray,
                                method: str = 'max_sharpe') -> np.ndarray:
    """
    Optimize portfolio allocation using modern portfolio theory.

    Args:
        expected_returns: Expected returns for each strategy
        cov_matrix: Covariance matrix
        method: Optimization method ('max_sharpe', 'min_variance', 'risk_parity')

    Returns:
        Optimal allocation weights
    """
    try:
        n_assets = len(expected_returns)

        if method == 'max_sharpe':
            # Maximize Sharpe ratio
            def negative_sharpe(weights):
                portfolio_return = np.sum(expected_returns * weights)
                portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                return -(portfolio_return - 0.02) / portfolio_std  # Assume 2% risk-free rate

            constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
            bounds = tuple((MIN_STRATEGY_ALLOCATION, MAX_STRATEGY_ALLOCATION) for _ in range(n_assets))  # noqa: E501

            result = optimize.minimize(negative_sharpe,
                                     np.array([1/n_assets] * n_assets),
                                     method='SLSQP',
                                     bounds=bounds,
                                     constraints=constraints)

            return result.x if result.success else np.array([1/n_assets] * n_assets)

        elif method == 'min_variance':
            # Minimize variance
            def portfolio_variance(weights):
                return np.dot(weights.T, np.dot(cov_matrix, weights))

            constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
            bounds = tuple((MIN_STRATEGY_ALLOCATION, MAX_STRATEGY_ALLOCATION) for _ in range(n_assets))  # noqa: E501

            result = optimize.minimize(portfolio_variance,
                                     np.array([1/n_assets] * n_assets),
                                     method='SLSQP',
                                     bounds=bounds,
                                     constraints=constraints)

            return result.x if result.success else np.array([1/n_assets] * n_assets)

        elif method == 'risk_parity':
            # Risk parity allocation
            portfolio_vol = np.sqrt(np.diag(cov_matrix))
            weights = 1 / portfolio_vol
            return weights / np.sum(weights)

        else:
            # Equal weight fallback
            return np.array([1/n_assets] * n_assets)

    except Exception as e:
        _module_logger.debug("optimize_portfolio_allocation error: %s", e)
        # Equal weight fallback on error
        n_assets = len(expected_returns)
        return np.array([1/n_assets] * n_assets)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

import threading as _threading  # noqa: E402

# Global portfolio manager instance guarded by a lock so concurrent
# init/reset/get calls from different threads cannot race.
_global_portfolio_manager: PortfolioManager | None = None
_global_portfolio_manager_lock = _threading.RLock()

def get_global_portfolio_manager() -> PortfolioManager | None:
    """Get global portfolio manager instance"""
    with _global_portfolio_manager_lock:
        return _global_portfolio_manager

def get_portfolio_manager() -> PortfolioManager | None:
    """Backward-compatible accessor for the global portfolio manager."""
    return get_global_portfolio_manager()

def set_global_portfolio_manager(portfolio_manager: PortfolioManager) -> None:
    """Set global portfolio manager instance"""
    global _global_portfolio_manager
    with _global_portfolio_manager_lock:
        _global_portfolio_manager = portfolio_manager

def reset_global_portfolio_manager() -> None:
    """Clear global portfolio manager instance (for shutdown/testing)."""
    global _global_portfolio_manager
    with _global_portfolio_manager_lock:
        _global_portfolio_manager = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create portfolio manager
    portfolio = PortfolioManager(initial_capital=100000)

    # Test strategy addition
    strategies = [
        {'id': 'iron_condor', 'allocation': 0.25, 'name': 'Iron Condor'},
        {'id': 'credit_spreads', 'allocation': 0.20, 'name': 'Credit Spreads'},
        {'id': 'straddles', 'allocation': 0.15, 'name': 'Straddles'},
        {'id': 'calendar_spreads', 'allocation': 0.15, 'name': 'Calendar Spreads'},
        {'id': 'butterflies', 'allocation': 0.10, 'name': 'Iron Butterflies'}
    ]

    for strategy in strategies:
        success = portfolio.add_strategy(
            strategy['id'],
            target_allocation=strategy['allocation'],
            strategy_config={'name': strategy['name']}
        )

    # Start portfolio management
    start_success = portfolio.start_management()

    # Wait for initial data collection
    time.sleep(2)  # thread-safe: time.sleep() intentional

    # Get portfolio metrics
    metrics = portfolio.get_portfolio_metrics()

    # Get portfolio summary
    summary = portfolio.get_portfolio_summary()
    if 'error' not in summary:

        for _strategy_id, _strategy_info in summary['strategies'].items():
            pass

    # Test allocation update
    update_success = portfolio.update_allocation('iron_condor', 0.30)

    # Test rebalancing
    rebalance_success = portfolio.rebalance_portfolio(RebalanceReason.SCHEDULED)

    # Show rebalance history
    if portfolio.rebalance_history:
        last_rebalance = portfolio.rebalance_history[-1]

    # Test different allocation methods
    allocation_methods = [
        AllocationMethod.EQUAL_WEIGHT,
        AllocationMethod.RISK_PARITY,
        AllocationMethod.PERFORMANCE_BASED,
        AllocationMethod.VOLATILITY_ADJUSTED
    ]

    for method in allocation_methods:
        portfolio.allocation_method = method
        allocations = portfolio._calculate_optimal_allocations()
        for _strategy_id, _allocation in allocations.items():
            pass

    # Test risk monitoring
    portfolio._check_portfolio_risk_limits()

    # Test correlation calculation
    div_score = portfolio._calculate_diversification_score()

    # Test performance calculations

    # Simulate some returns
    for _i in range(10):
        portfolio.daily_returns.append(np.random.normal(0.001, 0.02))  # 0.1% daily return, 2% volatility  # noqa: E501
        portfolio.benchmark_returns.append(np.random.normal(0.0008, 0.015))  # SPY benchmark

    returns_array = np.array(list(portfolio.daily_returns))
    sharpe = portfolio._calculate_sharpe_ratio(returns_array)
    sortino = portfolio._calculate_sortino_ratio(returns_array)
    beta = portfolio._calculate_beta()


    # Test hedge consideration
    portfolio._consider_delta_hedge(600)  # Simulate high delta
    portfolio._consider_volatility_hedge()

    for _hedge_id, _hedge in portfolio.hedge_positions.items():
        pass

    # Test utility functions

    # Test correlation calculation
    sample_returns = {
        'strategy1': [0.01, 0.02, -0.01, 0.015, 0.005],
        'strategy2': [0.008, 0.018, -0.008, 0.012, 0.003],
        'strategy3': [-0.005, 0.025, -0.015, 0.020, 0.010]
    }

    corr_matrix = calculate_portfolio_correlation(sample_returns)

    # Test optimization
    expected_returns = np.array([0.12, 0.10, 0.08])  # 12%, 10%, 8% expected returns
    cov_matrix = np.array([[0.04, 0.02, 0.01],
                          [0.02, 0.03, 0.015],
                          [0.01, 0.015, 0.02]])

    optimal_weights = optimize_portfolio_allocation(expected_returns, cov_matrix, 'max_sharpe')

    # Test emergency scenarios

    # Simulate large drawdown
    original_state = portfolio.portfolio_state
    portfolio._trigger_defensive_mode()

    # Restore normal state
    portfolio.portfolio_state = PortfolioState.ACTIVE

    # Stop management
    stop_success = portfolio.stop_management()


    # Demonstrate integration examples


    # Example of how strategies would integrate
    strategy_configs = {
        'conservative': {'iron_condor': 0.40, 'credit_spreads': 0.30, 'butterflies': 0.20},
        'aggressive': {'straddles': 0.30, 'calendar_spreads': 0.25, 'ratio_spreads': 0.25},
        'balanced': {'iron_condor': 0.25, 'credit_spreads': 0.20, 'straddles': 0.15, 'calendars': 0.15}  # noqa: E501
    }

    for _config_name, allocations in strategy_configs.items():
        total_allocation = sum(allocations.values())
        cash_reserve = 1.0 - total_allocation
        for _, _allocation in allocations.items():
            pass


    # Example risk scenarios
    risk_scenarios = [
        {'name': 'VIX Spike', 'vix': 35, 'action': 'Reduce position sizes, add volatility hedge'},
        {'name': 'Market Crash', 'spy_drop': -5, 'action': 'Close risky positions, activate emergency protocols'},  # noqa: E501
        {'name': 'High Correlation', 'correlation': 0.8, 'action': 'Rebalance for diversification'},
        {'name': 'Drawdown Alert', 'drawdown': -8, 'action': 'Defensive mode, reduce leverage'}
    ]

    for _scenario in risk_scenarios:
        pass


    # Example performance attribution
    sample_performance = {
        'iron_condor': {'return': 0.15, 'contribution': 0.0375, 'weight': 0.25},
        'credit_spreads': {'return': 0.12, 'contribution': 0.024, 'weight': 0.20},
        'straddles': {'return': 0.08, 'contribution': 0.012, 'weight': 0.15},
        'calendars': {'return': 0.10, 'contribution': 0.015, 'weight': 0.15}
    }

    total_return = sum(s['contribution'] for s in sample_performance.values())
    for _, perf in sample_performance.items():
        contribution_pct = perf['contribution'] / total_return * 100


    # Example rebalancing triggers
    rebalancing_triggers = [
        "Allocation drift > 5%: Rebalance to target weights",
        "Strategy underperformance > -10%: Reduce allocation",
        "VIX regime change: Adjust volatility exposure",
        "Correlation spike > 80%: Enhance diversification",
        "Daily loss > 2%: Risk reduction protocols"
    ]

    for _trigger in rebalancing_triggers:
        pass

