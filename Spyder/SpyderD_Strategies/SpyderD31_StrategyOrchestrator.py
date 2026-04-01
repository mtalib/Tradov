#!/usr/bin/env python3

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD31_StrategyOrchestrator.py
Purpose: Master Strategy Coordination and Portfolio Management System
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-28 Time: 18:00:00

Module Description:
    Advanced strategy orchestration engine that coordinates multiple simultaneous
    options trading strategies with intelligent allocation, dynamic selection based
    on market regimes, portfolio-level risk management, strategy conflict resolution,
    performance attribution, and real-time health monitoring. Integrates seamlessly
    with the Spyder connectivity management and provides institutional-grade
    portfolio coordination with adaptive strategy rotation algorithms.

Key Features:
    - Multi-strategy lifecycle management and coordination
    - Dynamic portfolio allocation across strategies based on performance
    - Market regime detection for intelligent strategy selection
    - Strategy conflict resolution and portfolio optimization
    - Real-time performance attribution and strategy health monitoring
    - Adaptive strategy rotation with machine learning insights
    - Integration with SpyderB connectivity and SpyderE risk management
    - PyQt6 dashboard for comprehensive strategy monitoring
    - Event-driven architecture with advanced analytics
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import numpy as np
import pandas as pd

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QGroupBox,
                                QTabWidget, QListWidget,
                                QTableWidget, QTableWidgetItem,
                                QFrame, QComboBox,
                                QSpinBox, QDoubleSpinBox, QHeaderView)
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtGui import QFont
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # Headless stubs so the orchestrator's strategy logic works without a display
    QWidget = object
    QTimer = None
    Signal = lambda *a, **kw: property()  # noqa: E731
    FigureCanvas = object

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    # Core imports
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError  # noqa: F401
    from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics  # noqa: F401
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

    # Strategy imports
    from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, StrategySignal, StrategyState  # noqa: F401
    from SpyderD_Strategies.SpyderD02_IronCondor import IronCondorStrategy
    from SpyderD_Strategies.SpyderD03_CreditSpread import CreditSpreadStrategy
    from SpyderD_Strategies.SpyderD04_ZeroDTE import ZeroDTEStrategy
    from SpyderD_Strategies.SpyderD05_Straddle import StraddleStrategy
    from SpyderD_Strategies.SpyderD11_SpecializedZeroDTE import SpecializedZeroDTEStrategy

    # Event management
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

    # Connectivity integration
    from SpyderB_Broker.SpyderB20_IntegratedConnectivityManager import IntegratedConnectivityManager, ConnectivityState

    SPYDER_MODULES_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ Some Spyder modules not available: {e}")
    SPYDER_MODULES_AVAILABLE = False

    # Fallback enums
    class StrategyState(Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"
        PAUSED = "paused"
        ERROR = "error"

    class ConnectivityState(Enum):
        OPTIMAL = "optimal"
        GOOD = "good"
        DEGRADED = "degraded"
        FAILED = "failed"

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Portfolio management
MAX_CONCURRENT_STRATEGIES = 8
DEFAULT_BASE_CAPITAL = 100000  # $100K base allocation
REBALANCE_FREQUENCY_MINUTES = 30  # Rebalance every 30 minutes
STRATEGY_HEALTH_CHECK_INTERVAL = 60  # Check health every minute

# Performance thresholds
MIN_SHARPE_RATIO = 0.5  # Minimum Sharpe for active strategies
MAX_DRAWDOWN_THRESHOLD = 0.15  # 15% maximum drawdown
CORRELATION_THRESHOLD = 0.7  # Maximum strategy correlation
PERFORMANCE_LOOKBACK_DAYS = 30  # Days for performance analysis

# Market regime detection
VOLATILITY_REGIME_LOOKBACK = 20  # Days for volatility regime
TREND_DETECTION_PERIODS = [5, 10, 20]  # Moving average periods
VIX_REGIME_THRESHOLDS = {'low': 15, 'normal': 20, 'high': 30, 'extreme': 40}

# Strategy allocation limits
MAX_STRATEGY_ALLOCATION = 0.4  # Maximum 40% to any single strategy
MIN_STRATEGY_ALLOCATION = 0.05  # Minimum 5% allocation
ALLOCATION_ADJUSTMENT_STEP = 0.02  # 2% adjustment steps

# Risk management
PORTFOLIO_VAR_LIMIT = 0.02  # 2% daily VaR limit
CONCENTRATION_LIMIT = 0.6  # Maximum 60% in any strategy type
KELLY_FRACTION_CAP = 0.25  # Maximum 25% Kelly allocation

# ==============================================================================
# ENUMS
# ==============================================================================

class OrchestrationMode(Enum):
    """Strategy orchestration modes"""
    CONSERVATIVE = "conservative"  # Lower risk, fewer strategies
    BALANCED = "balanced"         # Moderate risk and diversification
    AGGRESSIVE = "aggressive"     # Higher risk, more strategies
    ADAPTIVE = "adaptive"         # ML-driven dynamic allocation

class MarketRegime(Enum):
    """Market regime classifications"""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"
    CRISIS = "crisis"
    RECOVERY = "recovery"

class AllocationMethod(Enum):
    """Portfolio allocation methods"""
    EQUAL_WEIGHT = "equal_weight"
    PERFORMANCE_BASED = "performance_based"
    RISK_PARITY = "risk_parity"
    KELLY_CRITERION = "kelly_criterion"
    ADAPTIVE_ML = "adaptive_ml"
    MARKET_REGIME = "market_regime"

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    SCHEDULED = "scheduled"
    PERFORMANCE_DRIFT = "performance_drift"
    RISK_BREACH = "risk_breach"
    STRATEGY_HEALTH = "strategy_health"
    MARKET_REGIME_CHANGE = "market_regime_change"
    CORRELATION_SPIKE = "correlation_spike"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class StrategyAllocation:
    """Individual strategy allocation information"""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    allocated_capital: float
    target_allocation: float
    current_allocation: float
    performance_score: float
    risk_score: float
    health_score: float
    last_rebalance: datetime
    allocation_history: list[tuple[datetime, float]] = field(default_factory=list)

@dataclass
class MarketRegimeData:
    """Market regime analysis data"""
    current_regime: MarketRegime
    regime_confidence: float
    volatility_percentile: float
    trend_strength: float
    vix_level: float
    regime_duration_days: int
    last_regime_change: datetime
    regime_history: list[tuple[datetime, MarketRegime]] = field(default_factory=list)

@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics"""
    total_capital: float
    allocated_capital: float
    available_capital: float
    total_pnl: float
    daily_pnl: float
    portfolio_var: float
    portfolio_sharpe: float
    portfolio_sortino: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    active_strategies: int
    total_positions: int
    correlation_matrix: pd.DataFrame | None = None

@dataclass
class StrategyConflict:
    """Strategy conflict detection"""
    strategy_ids: list[str]
    conflict_type: str
    severity: str  # 'low', 'medium', 'high'
    description: str
    resolution_action: str
    detected_at: datetime

@dataclass
class RebalanceEvent:
    """Portfolio rebalancing event"""
    timestamp: datetime
    reason: RebalanceReason
    previous_allocations: dict[str, float]
    new_allocations: dict[str, float]
    capital_movements: dict[str, float]
    expected_impact: dict[str, float]
    execution_status: str = "pending"

# ==============================================================================
# STRATEGY ORCHESTRATOR CORE ENGINE
# ==============================================================================

class StrategyOrchestrator:
    """
    Master strategy coordination and portfolio management engine.

    This class orchestrates multiple trading strategies simultaneously with:
    - Dynamic portfolio allocation based on performance and market conditions
    - Strategy conflict resolution and optimization
    - Market regime detection for intelligent strategy selection
    - Real-time performance attribution and health monitoring
    - Risk management at portfolio level
    - Integration with connectivity and execution systems
    """

    def __init__(self,
                 base_capital: float = DEFAULT_BASE_CAPITAL,
                 orchestration_mode: OrchestrationMode = OrchestrationMode.BALANCED,
                 allocation_method: AllocationMethod = AllocationMethod.PERFORMANCE_BASED,
                 connectivity_manager: IntegratedConnectivityManager | None = None,
                 event_manager: EventManager | None = None):
        """
        Initialize Strategy Orchestrator.

        Args:
            base_capital: Base capital for allocation
            orchestration_mode: Operating mode for strategy coordination
            allocation_method: Method for portfolio allocation
            connectivity_manager: Connectivity management integration
            event_manager: Event management system
        """
        # Setup logging and error handling
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None

        # Core configuration
        self.base_capital = base_capital
        self.orchestration_mode = orchestration_mode
        self.allocation_method = allocation_method
        self.connectivity_manager = connectivity_manager
        self.event_manager = event_manager or EventManager()

        # Portfolio state
        self.active_strategies: dict[str, BaseStrategy] = {}
        self.strategy_allocations: dict[str, StrategyAllocation] = {}
        self.available_strategies: dict[str, type] = {}
        self.paused_strategies: set[str] = set()

        # Market analysis
        self.market_regime = MarketRegimeData(
            current_regime=MarketRegime.SIDEWAYS_LOW_VOL,
            regime_confidence=0.0,
            volatility_percentile=50.0,
            trend_strength=0.0,
            vix_level=20.0,
            regime_duration_days=0,
            last_regime_change=datetime.now()
        )

        # Performance tracking
        self.portfolio_metrics = PortfolioMetrics(
            total_capital=base_capital,
            allocated_capital=0.0,
            available_capital=base_capital,
            total_pnl=0.0,
            daily_pnl=0.0,
            portfolio_var=0.0,
            portfolio_sharpe=0.0,
            portfolio_sortino=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            active_strategies=0,
            total_positions=0
        )

        # Monitoring and control
        self.orchestration_active = False
        self.last_rebalance = datetime.now()
        self.rebalance_history: list[RebalanceEvent] = []
        self.strategy_conflicts: list[StrategyConflict] = []

        # Threading
        self.orchestration_thread = None
        self.monitoring_thread = None
        self.shutdown_event = threading.Event()

        # Market data cache (replaced entirely each update, not appended)
        self.market_data_cache = {}
        self.last_market_update = None

        # Performance attribution
        self.performance_history = deque(maxlen=1000)
        self.strategy_correlations = {}

        # Trading calendar
        try:
            self.trading_calendar = TradingCalendar() if TradingCalendar else None
        except (ImportError, TypeError, AttributeError) as e:
            # TradingCalendar not available or failed to initialize
            self.logger.debug(f"TradingCalendar not available: {e}")
            self.trading_calendar = None

        # Initialize available strategies
        self._initialize_strategy_registry()

        # Setup event subscriptions
        self._setup_event_subscriptions()

        self.logger.info(f"🎯 Strategy Orchestrator initialized - Mode: {orchestration_mode.value}, Capital: ${base_capital:,.2f}")

    # ==========================================================================
    # PUBLIC INTERFACE - ORCHESTRATION CONTROL
    # ==========================================================================

    def start_orchestration(self) -> bool:
        """
        Start strategy orchestration.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.orchestration_active:
                self.logger.warning("Strategy orchestration already active")
                return True

            self.logger.info("🚀 Starting strategy orchestration...")

            # Validate connectivity if available
            if self.connectivity_manager:
                connectivity_report = self.connectivity_manager.get_connectivity_report()
                if connectivity_report.overall_state == ConnectivityState.FAILED:
                    self.logger.error("❌ Cannot start orchestration - connectivity failed")
                    return False

            # Initialize market regime detection
            self._update_market_regime()

            # Load optimal strategy configuration for current regime
            self._configure_strategies_for_regime()

            # Start monitoring threads
            self.orchestration_active = True
            self.shutdown_event.clear()

            self.orchestration_thread = threading.Thread(target=self._orchestration_loop, daemon=True)
            self.orchestration_thread.start()

            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()

            # Initial portfolio allocation
            self._perform_initial_allocation()

            self.logger.info("✅ Strategy orchestration started successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start strategy orchestration: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_error(e, "StrategyOrchestrator.start_orchestration")
            return False

    def stop_orchestration(self, graceful: bool = True) -> bool:
        """
        Stop strategy orchestration.

        Args:
            graceful: Whether to stop gracefully

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.orchestration_active:
                self.logger.info("Strategy orchestration already stopped")
                return True

            self.logger.info("🛑 Stopping strategy orchestration...")

            # Signal shutdown
            self.orchestration_active = False
            self.shutdown_event.set()

            # Stop all strategies
            if graceful:
                for strategy_id, strategy in self.active_strategies.items():
                    self.logger.info(f"Stopping strategy: {strategy_id}")
                    try:
                        strategy.stop()
                    except Exception as e:
                        self.logger.error(f"Error stopping strategy {strategy_id}: {e}", exc_info=True)

            # Wait for threads to complete
            if self.orchestration_thread:
                self.orchestration_thread.join(timeout=30)
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=30)

            # Final portfolio report
            self._generate_final_report()

            self.logger.info("✅ Strategy orchestration stopped")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping orchestration: {e}", exc_info=True)
            return False

    def add_strategy(self, strategy_class: type, config: dict[str, Any],
                     initial_allocation: float | None = None) -> str:
        """
        Add a new strategy to the orchestrator.

        Args:
            strategy_class: Strategy class to instantiate
            config: Strategy configuration
            initial_allocation: Initial capital allocation (0.0-1.0)

        Returns:
            str: Strategy ID
        """
        try:
            # Validate strategy class
            if not issubclass(strategy_class, BaseStrategy):
                raise ValueError("Strategy class must inherit from BaseStrategy")

            # Generate strategy ID
            strategy_id = f"{strategy_class.__name__}_{uuid.uuid4().hex[:8]}"

            # Create strategy instance
            strategy = strategy_class(
                name=strategy_id,
                event_manager=self.event_manager,
                risk_profile=self._get_risk_profile_for_strategy(strategy_class),
                config=config
            )

            # Calculate initial allocation
            if initial_allocation is None:
                initial_allocation = self._calculate_optimal_allocation(strategy_class.__name__)

            allocated_capital = self.base_capital * initial_allocation

            # Add to active strategies
            self.active_strategies[strategy_id] = strategy

            # Create allocation record
            self.strategy_allocations[strategy_id] = StrategyAllocation(
                strategy_id=strategy_id,
                strategy_name=strategy_class.__name__,
                strategy_type=self._get_strategy_type(strategy_class),
                allocated_capital=allocated_capital,
                target_allocation=initial_allocation,
                current_allocation=initial_allocation,
                performance_score=0.5,  # Neutral starting score
                risk_score=0.5,
                health_score=1.0,
                last_rebalance=datetime.now()
            )

            # Update portfolio metrics
            self._update_portfolio_metrics()

            # Start strategy if orchestration is active
            if self.orchestration_active:
                strategy.start()

            self.logger.info(f"✅ Added strategy: {strategy_id} with {initial_allocation:.1%} allocation")
            return strategy_id

        except Exception as e:
            self.logger.error(f"❌ Failed to add strategy: {e}", exc_info=True)
            if self.error_handler:
                self.error_handler.handle_error(e, "StrategyOrchestrator.add_strategy")
            raise

    def remove_strategy(self, strategy_id: str, close_positions: bool = True) -> bool:
        """
        Remove a strategy from orchestration.

        Args:
            strategy_id: Strategy to remove
            close_positions: Whether to close existing positions

        Returns:
            bool: True if removed successfully
        """
        try:
            if strategy_id not in self.active_strategies:
                self.logger.warning(f"Strategy {strategy_id} not found")
                return False

            strategy = self.active_strategies[strategy_id]

            # Stop strategy
            if close_positions:
                strategy.close_all_positions()
            strategy.stop()

            # Remove from active strategies
            del self.active_strategies[strategy_id]

            # Redistribute capital
            if strategy_id in self.strategy_allocations:
                freed_capital = self.strategy_allocations[strategy_id].allocated_capital
                del self.strategy_allocations[strategy_id]

                # Redistribute to remaining strategies
                self._redistribute_capital(freed_capital)

            # Update portfolio metrics
            self._update_portfolio_metrics()

            self.logger.info(f"✅ Removed strategy: {strategy_id}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error removing strategy {strategy_id}: {e}", exc_info=True)
            return False

    def pause_strategy(self, strategy_id: str) -> bool:
        """Pause a specific strategy"""
        try:
            if strategy_id not in self.active_strategies:
                return False

            self.active_strategies[strategy_id].pause()
            self.paused_strategies.add(strategy_id)

            self.logger.info(f"⏸️ Paused strategy: {strategy_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error pausing strategy {strategy_id}: {e}", exc_info=True)
            return False

    def resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy"""
        try:
            if strategy_id not in self.active_strategies:
                return False

            self.active_strategies[strategy_id].resume()
            self.paused_strategies.discard(strategy_id)

            self.logger.info(f"▶️ Resumed strategy: {strategy_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error resuming strategy {strategy_id}: {e}", exc_info=True)
            return False

    def rebalance_portfolio(self, reason: RebalanceReason = RebalanceReason.SCHEDULED) -> bool:
        """
        Manually trigger portfolio rebalancing.

        Args:
            reason: Reason for rebalancing

        Returns:
            bool: True if rebalancing was successful
        """
        try:
            self.logger.info(f"🔄 Manual portfolio rebalancing triggered - Reason: {reason.value}")
            return self._execute_rebalancing(reason)

        except Exception as e:
            self.logger.error(f"❌ Manual rebalancing failed: {e}", exc_info=True)
            return False

    # ==========================================================================
    # PORTFOLIO ANALYTICS AND REPORTING
    # ==========================================================================

    def get_portfolio_status(self) -> dict[str, Any]:
        """Get comprehensive portfolio status"""
        try:
            return {
                'orchestration_active': self.orchestration_active,
                'total_capital': self.portfolio_metrics.total_capital,
                'allocated_capital': self.portfolio_metrics.allocated_capital,
                'available_capital': self.portfolio_metrics.available_capital,
                'total_pnl': self.portfolio_metrics.total_pnl,
                'daily_pnl': self.portfolio_metrics.daily_pnl,
                'portfolio_sharpe': self.portfolio_metrics.portfolio_sharpe,
                'max_drawdown': self.portfolio_metrics.max_drawdown,
                'active_strategies': len(self.active_strategies),
                'paused_strategies': len(self.paused_strategies),
                'market_regime': self.market_regime.current_regime.value,
                'regime_confidence': self.market_regime.regime_confidence,
                'last_rebalance': self.last_rebalance.isoformat(),
                'strategy_allocations': {
                    sid: {
                        'name': alloc.strategy_name,
                        'allocation': alloc.current_allocation,
                        'capital': alloc.allocated_capital,
                        'performance_score': alloc.performance_score,
                        'health_score': alloc.health_score
                    }
                    for sid, alloc in self.strategy_allocations.items()
                }
            }

        except Exception as e:
            self.logger.error(f"Error getting portfolio status: {e}", exc_info=True)
            return {}

    def get_strategy_performance_attribution(self) -> pd.DataFrame:
        """Get detailed strategy performance attribution"""
        try:
            data = []

            for strategy_id, allocation in self.strategy_allocations.items():
                if strategy_id in self.active_strategies:
                    strategy = self.active_strategies[strategy_id]

                    # Calculate strategy contribution to portfolio
                    strategy_pnl = getattr(strategy, 'total_pnl', 0.0)
                    portfolio_contribution = strategy_pnl * allocation.current_allocation

                    data.append({
                        'strategy_id': strategy_id,
                        'strategy_name': allocation.strategy_name,
                        'strategy_type': allocation.strategy_type,
                        'allocation': allocation.current_allocation,
                        'allocated_capital': allocation.allocated_capital,
                        'strategy_pnl': strategy_pnl,
                        'portfolio_contribution': portfolio_contribution,
                        'performance_score': allocation.performance_score,
                        'risk_score': allocation.risk_score,
                        'health_score': allocation.health_score,
                        'sharpe_ratio': getattr(strategy, 'sharpe_ratio', 0.0),
                        'max_drawdown': getattr(strategy, 'max_drawdown', 0.0),
                        'win_rate': getattr(strategy, 'win_rate', 0.0),
                        'total_trades': getattr(strategy, 'total_trades', 0),
                        'active_positions': len(getattr(strategy, 'positions', {}))
                    })

            return pd.DataFrame(data)

        except Exception as e:
            self.logger.error(f"Error generating performance attribution: {e}", exc_info=True)
            return pd.DataFrame()

    def detect_strategy_conflicts(self) -> list[StrategyConflict]:
        """Detect potential conflicts between strategies"""
        try:
            conflicts = []
            strategies = list(self.active_strategies.items())

            # Check for overlapping positions
            for i, (id1, strategy1) in enumerate(strategies):
                for id2, strategy2 in strategies[i+1:]:
                    conflict = self._analyze_strategy_pair_for_conflicts(id1, strategy1, id2, strategy2)
                    if conflict:
                        conflicts.append(conflict)

            # Check for concentration risks
            concentration_conflicts = self._check_concentration_conflicts()
            conflicts.extend(concentration_conflicts)

            # Update stored conflicts
            self.strategy_conflicts = conflicts

            return conflicts

        except Exception as e:
            self.logger.error(f"Error detecting strategy conflicts: {e}", exc_info=True)
            return []

    def get_correlation_matrix(self) -> pd.DataFrame | None:
        """Get strategy correlation matrix"""
        try:
            if len(self.active_strategies) < 2:
                return None

            # Collect strategy returns
            strategy_returns = {}

            for strategy_id, strategy in self.active_strategies.items():
                if hasattr(strategy, 'daily_returns') and len(strategy.daily_returns) > 10:
                    strategy_returns[strategy_id] = strategy.daily_returns[-30:]  # Last 30 days

            if len(strategy_returns) < 2:
                return None

            # Create DataFrame and calculate correlations
            returns_df = pd.DataFrame(strategy_returns)
            correlation_matrix = returns_df.corr()

            return correlation_matrix

        except Exception as e:
            self.logger.error(f"Error calculating correlation matrix: {e}", exc_info=True)
            return None

    # ==========================================================================
    # PRIVATE METHODS - ORCHESTRATION LOOPS
    # ==========================================================================

    def _orchestration_loop(self):
        """Main orchestration loop"""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
                # Update market regime
                self._update_market_regime()

                # Check if rebalancing is needed
                if self._should_rebalance():
                    reason = self._determine_rebalance_reason()
                    self._execute_rebalancing(reason)

                # Check for strategy conflicts
                conflicts = self.detect_strategy_conflicts()
                if conflicts:
                    self._resolve_strategy_conflicts(conflicts)

                # Adaptive strategy management
                if self.orchestration_mode == OrchestrationMode.ADAPTIVE:
                    self._adaptive_strategy_management()

                # Sleep until next iteration
                self.shutdown_event.wait(REBALANCE_FREQUENCY_MINUTES * 60)

            except Exception as e:
                self.logger.error(f"Error in orchestration loop: {e}", exc_info=True)
                self.shutdown_event.wait(60)  # Wait 1 minute on error

    def _monitoring_loop(self):
        """Strategy health monitoring loop"""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
                # Monitor strategy health
                self._monitor_strategy_health()

                # Update portfolio metrics
                self._update_portfolio_metrics()

                # Check risk limits
                self._check_risk_limits()

                # Update performance attribution
                self._update_performance_attribution()

                # Sleep until next check
                self.shutdown_event.wait(STRATEGY_HEALTH_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                self.shutdown_event.wait(30)  # Short wait on error

    # ==========================================================================
    # PRIVATE METHODS - ALLOCATION AND REBALANCING
    # ==========================================================================

    def _execute_rebalancing(self, reason: RebalanceReason) -> bool:
        """Execute portfolio rebalancing"""
        try:
            self.logger.info(f"🔄 Executing portfolio rebalancing - Reason: {reason.value}")

            # Calculate new allocations
            new_allocations = self._calculate_optimal_allocations()

            if not new_allocations:
                self.logger.warning("No valid allocations calculated")
                return False

            # Store previous allocations
            previous_allocations = {
                sid: alloc.current_allocation
                for sid, alloc in self.strategy_allocations.items()
            }

            # Calculate capital movements
            capital_movements = {}
            total_capital = self.portfolio_metrics.total_capital

            for strategy_id, new_allocation in new_allocations.items():
                if strategy_id in self.strategy_allocations:
                    old_allocation = self.strategy_allocations[strategy_id].current_allocation
                    capital_change = (new_allocation - old_allocation) * total_capital
                    capital_movements[strategy_id] = capital_change

            # Execute rebalancing
            rebalance_successful = True

            for strategy_id, capital_change in capital_movements.items():
                if abs(capital_change) > 100:  # Only rebalance if change > $100
                    success = self._adjust_strategy_capital(strategy_id, capital_change)
                    if not success:
                        rebalance_successful = False
                        self.logger.error(f"Failed to adjust capital for strategy {strategy_id}")

            # Update allocations if successful
            if rebalance_successful:
                for strategy_id, new_allocation in new_allocations.items():
                    if strategy_id in self.strategy_allocations:
                        allocation = self.strategy_allocations[strategy_id]
                        allocation.current_allocation = new_allocation
                        allocation.allocated_capital = new_allocation * total_capital
                        allocation.last_rebalance = datetime.now()
                        allocation.allocation_history.append((datetime.now(), new_allocation))

            # Record rebalance event
            rebalance_event = RebalanceEvent(
                timestamp=datetime.now(),
                reason=reason,
                previous_allocations=previous_allocations,
                new_allocations=new_allocations,
                capital_movements=capital_movements,
                expected_impact={},  # Could calculate expected impact
                execution_status="completed" if rebalance_successful else "failed"
            )

            self.rebalance_history.append(rebalance_event)
            self.last_rebalance = datetime.now()

            # Update portfolio metrics
            self._update_portfolio_metrics()

            status = "✅ completed" if rebalance_successful else "❌ failed"
            self.logger.info(f"Portfolio rebalancing {status}")

            return rebalance_successful

        except Exception as e:
            self.logger.error(f"❌ Rebalancing execution failed: {e}", exc_info=True)
            return False

    def _calculate_optimal_allocations(self) -> dict[str, float]:
        """Calculate optimal portfolio allocations"""
        try:
            if not self.active_strategies:
                return {}

            # Choose allocation method
            if self.allocation_method == AllocationMethod.EQUAL_WEIGHT:
                return self._calculate_equal_weight_allocations()
            elif self.allocation_method == AllocationMethod.PERFORMANCE_BASED:
                return self._calculate_performance_based_allocations()
            elif self.allocation_method == AllocationMethod.RISK_PARITY:
                return self._calculate_risk_parity_allocations()
            elif self.allocation_method == AllocationMethod.KELLY_CRITERION:
                return self._calculate_kelly_allocations()
            elif self.allocation_method == AllocationMethod.MARKET_REGIME:
                return self._calculate_regime_based_allocations()
            else:  # ADAPTIVE_ML
                return self._calculate_adaptive_ml_allocations()

        except Exception as e:
            self.logger.error(f"Error calculating optimal allocations: {e}", exc_info=True)
            return {}

    def _calculate_performance_based_allocations(self) -> dict[str, float]:
        """Calculate allocations based on strategy performance"""
        try:
            allocations = {}
            performance_scores = {}

            # Calculate performance scores for each strategy
            for strategy_id, allocation in self.strategy_allocations.items():
                if strategy_id in self.active_strategies:
                    # Combine multiple performance metrics
                    performance_score = (
                        allocation.performance_score * 0.4 +  # Historical performance
                        allocation.health_score * 0.3 +       # Current health
                        (1 - allocation.risk_score) * 0.3     # Risk-adjusted (lower risk = higher score)
                    )

                    # Apply regime adjustment
                    regime_multiplier = self._get_strategy_regime_multiplier(allocation.strategy_type)
                    performance_score *= regime_multiplier

                    performance_scores[strategy_id] = max(0.1, performance_score)  # Minimum score

            # Normalize scores to allocations
            total_score = sum(performance_scores.values())

            if total_score > 0:
                for strategy_id, score in performance_scores.items():
                    base_allocation = score / total_score

                    # Apply allocation limits
                    allocation = max(MIN_STRATEGY_ALLOCATION,
                                   min(MAX_STRATEGY_ALLOCATION, base_allocation))

                    allocations[strategy_id] = allocation

                # Normalize to ensure allocations sum to 1.0
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error(f"Error calculating performance-based allocations: {e}", exc_info=True)
            return {}

    def _calculate_equal_weight_allocations(self) -> dict[str, float]:
        """Calculate equal weight allocations"""
        if not self.active_strategies:
            return {}

        equal_weight = 1.0 / len(self.active_strategies)
        return {strategy_id: equal_weight for strategy_id in self.active_strategies}

    def _calculate_risk_parity_allocations(self) -> dict[str, float]:
        """Calculate risk parity allocations"""
        try:
            allocations = {}
            risk_contributions = {}

            # Calculate risk contribution for each strategy
            for strategy_id, allocation in self.strategy_allocations.items():
                if strategy_id in self.active_strategies:
                    # Use inverse of risk score as weight (higher risk = lower weight)
                    risk_weight = 1.0 / max(0.1, allocation.risk_score)
                    risk_contributions[strategy_id] = risk_weight

            # Normalize to allocations
            total_risk_weight = sum(risk_contributions.values())
            if total_risk_weight > 0:
                for strategy_id, weight in risk_contributions.items():
                    allocation = weight / total_risk_weight
                    allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                                 min(MAX_STRATEGY_ALLOCATION, allocation))

                # Renormalize
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error(f"Error calculating risk parity allocations: {e}", exc_info=True)
            return {}

    def _calculate_kelly_allocations(self) -> dict[str, float]:
        """Calculate Kelly criterion allocations"""
        try:
            allocations = {}
            kelly_fractions = {}

            for strategy_id, _allocation in self.strategy_allocations.items():
                if strategy_id in self.active_strategies:
                    strategy = self.active_strategies[strategy_id]

                    # Calculate Kelly fraction based on win rate and profit factor
                    win_rate = getattr(strategy, 'win_rate', 0.5)
                    profit_factor = getattr(strategy, 'profit_factor', 1.0)

                    if profit_factor > 1.0 and win_rate > 0:
                        # Kelly formula: f = (bp - q) / b
                        # where b = odds received (profit_factor - 1), p = win_rate, q = 1 - p
                        b = profit_factor - 1
                        p = win_rate
                        q = 1 - p

                        kelly_fraction = (b * p - q) / b
                        kelly_fraction = max(0, min(KELLY_FRACTION_CAP, kelly_fraction))
                    else:
                        kelly_fraction = MIN_STRATEGY_ALLOCATION

                    kelly_fractions[strategy_id] = kelly_fraction

            # Normalize Kelly fractions to portfolio allocations
            total_kelly = sum(kelly_fractions.values())
            if total_kelly > 0:
                for strategy_id, fraction in kelly_fractions.items():
                    allocations[strategy_id] = fraction / total_kelly

            return allocations

        except Exception as e:
            self.logger.error(f"Error calculating Kelly allocations: {e}", exc_info=True)
            return {}

    def _calculate_regime_based_allocations(self) -> dict[str, float]:
        """Calculate allocations based on current market regime"""
        try:
            allocations = {}
            regime_weights = self._get_regime_strategy_weights()

            if not regime_weights:
                # Fallback to equal weight
                return self._calculate_equal_weight_allocations()

            # Apply regime weights to active strategies
            total_weight = 0
            strategy_weights = {}

            for strategy_id, allocation in self.strategy_allocations.items():
                if strategy_id in self.active_strategies:
                    strategy_type = allocation.strategy_type
                    weight = regime_weights.get(strategy_type, 0.1)  # Default low weight

                    # Adjust for strategy health
                    weight *= allocation.health_score

                    strategy_weights[strategy_id] = weight
                    total_weight += weight

            # Normalize to allocations
            if total_weight > 0:
                for strategy_id, weight in strategy_weights.items():
                    allocation = weight / total_weight
                    allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                                 min(MAX_STRATEGY_ALLOCATION, allocation))

                # Final normalization
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error(f"Error calculating regime-based allocations: {e}", exc_info=True)
            return {}

    # ==========================================================================
    # PRIVATE METHODS - MARKET REGIME ANALYSIS
    # ==========================================================================

    def _update_market_regime(self):
        """Update current market regime analysis"""
        try:
            # This would integrate with market data feeds
            # For now, using simplified regime detection

            # Calculate volatility metrics
            current_vix = 20.0  # Would get from market data
            vix_percentile = self._calculate_vix_percentile(current_vix)

            # Determine trend strength
            trend_strength = self._calculate_trend_strength()

            # Classify regime
            new_regime = self._classify_market_regime(current_vix, vix_percentile, trend_strength)

            # Update regime data
            regime_changed = new_regime != self.market_regime.current_regime

            if regime_changed:
                self.market_regime.last_regime_change = datetime.now()
                self.market_regime.regime_duration_days = 0
                self.market_regime.regime_history.append((datetime.now(), new_regime))
            else:
                # Update duration
                days_since_change = (datetime.now() - self.market_regime.last_regime_change).days
                self.market_regime.regime_duration_days = days_since_change

            self.market_regime.current_regime = new_regime
            self.market_regime.vix_level = current_vix
            self.market_regime.volatility_percentile = vix_percentile
            self.market_regime.trend_strength = trend_strength

            # Calculate confidence based on regime stability
            self.market_regime.regime_confidence = min(1.0, self.market_regime.regime_duration_days / 5.0)

            if regime_changed:
                self.logger.info(f"📊 Market regime changed to: {new_regime.value}")

        except Exception as e:
            self.logger.error(f"Error updating market regime: {e}", exc_info=True)

    def _classify_market_regime(self, vix_level: float, vix_percentile: float, trend_strength: float) -> MarketRegime:
        """Classify current market regime"""
        # Simplified regime classification
        is_high_vol = vix_level > VIX_REGIME_THRESHOLDS['high']
        is_crisis = vix_level > VIX_REGIME_THRESHOLDS['extreme']
        is_trending_up = trend_strength > 0.3
        is_trending_down = trend_strength < -0.3

        if is_crisis:
            return MarketRegime.CRISIS
        elif is_trending_up:
            return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
        elif is_trending_down:
            return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL
        else:
            return MarketRegime.SIDEWAYS_HIGH_VOL if is_high_vol else MarketRegime.SIDEWAYS_LOW_VOL

    def _get_regime_strategy_weights(self) -> dict[str, float]:
        """Get optimal strategy weights for current regime"""
        regime = self.market_regime.current_regime

        # Strategy weights by regime (this would be backtested/optimized)
        regime_weights = {
            MarketRegime.BULL_LOW_VOL: {
                'IronCondor': 0.3,
                'CreditSpread': 0.25,
                'IronButterfly': 0.2,
                'ZeroDTE': 0.15,
                'Straddle': 0.1
            },
            MarketRegime.BULL_HIGH_VOL: {
                'CreditSpread': 0.4,
                'Straddle': 0.3,
                'ZeroDTE': 0.2,
                'IronCondor': 0.1
            },
            MarketRegime.BEAR_LOW_VOL: {
                'CreditSpread': 0.35,
                'IronCondor': 0.3,
                'IronButterfly': 0.2,
                'ZeroDTE': 0.15
            },
            MarketRegime.BEAR_HIGH_VOL: {
                'Straddle': 0.4,
                'CreditSpread': 0.3,
                'ZeroDTE': 0.3
            },
            MarketRegime.SIDEWAYS_LOW_VOL: {
                'IronCondor': 0.4,
                'IronButterfly': 0.3,
                'CreditSpread': 0.2,
                'ZeroDTE': 0.1
            },
            MarketRegime.SIDEWAYS_HIGH_VOL: {
                'IronCondor': 0.3,
                'Straddle': 0.3,
                'CreditSpread': 0.25,
                'ZeroDTE': 0.15
            },
            MarketRegime.CRISIS: {
                'CreditSpread': 0.6,
                'Straddle': 0.4
            }
        }

        return regime_weights.get(regime, {})

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================

    def _initialize_strategy_registry(self):
        """Initialize available strategy registry"""
        if SPYDER_MODULES_AVAILABLE:
            self.available_strategies = {
                'IronCondor': IronCondorStrategy,
                'CreditSpread': CreditSpreadStrategy,
                'ZeroDTE': ZeroDTEStrategy,
                'Straddle': StraddleStrategy,
                'SpecializedZeroDTE': SpecializedZeroDTEStrategy
            }
        else:
            self.available_strategies = {}

        self.logger.info(f"📋 Registered {len(self.available_strategies)} strategy types")

    def _setup_event_subscriptions(self):
        """Setup event system subscriptions"""
        try:
            # Subscribe to relevant events
            if self.event_manager:
                self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data_event)
                self.event_manager.subscribe(EventType.STRATEGY_SIGNAL, self._on_strategy_signal)
                self.event_manager.subscribe(EventType.RISK_ALERT, self._on_risk_alert)

        except Exception as e:
            self.logger.error(f"Error setting up event subscriptions: {e}", exc_info=True)

    def _on_market_data_event(self, event: Event):
        """Handle market data events"""
        self.market_data_cache = event.data
        self.last_market_update = datetime.now()

    def _on_strategy_signal(self, event: Event):
        """Handle strategy signal events"""
        # Could implement cross-strategy signal analysis here
        pass

    def _on_risk_alert(self, event: Event):
        """Handle risk alert events"""
        if event.data.get('severity') == 'critical':
            # Implement emergency procedures
            self.logger.warning(f"🚨 Critical risk alert: {event.data}")

    def _should_rebalance(self) -> bool:
        """Check if portfolio rebalancing is needed"""
        # Time-based rebalancing
        time_since_rebalance = datetime.now() - self.last_rebalance
        # Performance-driven rebalancing
        # (Implementation would check allocation drift, performance changes, etc.)
        return time_since_rebalance > timedelta(minutes=REBALANCE_FREQUENCY_MINUTES)

    def _determine_rebalance_reason(self) -> RebalanceReason:
        """Determine the reason for rebalancing"""
        # Simplified logic - would be more sophisticated in practice
        time_since_rebalance = datetime.now() - self.last_rebalance
        if time_since_rebalance > timedelta(minutes=REBALANCE_FREQUENCY_MINUTES):
            return RebalanceReason.SCHEDULED

        return RebalanceReason.PERFORMANCE_DRIFT

    def _update_portfolio_metrics(self):
        """Update portfolio-level metrics"""
        try:
            # Calculate total allocated capital
            total_allocated = sum(alloc.allocated_capital for alloc in self.strategy_allocations.values())

            # Update basic metrics
            self.portfolio_metrics.allocated_capital = total_allocated
            self.portfolio_metrics.available_capital = self.base_capital - total_allocated
            self.portfolio_metrics.active_strategies = len(self.active_strategies)

            # Calculate portfolio PnL (sum of all strategy PnL)
            total_pnl = 0.0
            for _strategy_id, strategy in self.active_strategies.items():
                strategy_pnl = getattr(strategy, 'total_pnl', 0.0)
                total_pnl += strategy_pnl

            self.portfolio_metrics.total_pnl = total_pnl

            # Calculate other metrics if we have enough data
            if len(self.performance_history) > 10:
                returns = [entry['daily_return'] for entry in self.performance_history]

                if returns and len(returns) > 1:
                    self.portfolio_metrics.portfolio_sharpe = self._calculate_sharpe_ratio(returns)
                    self.portfolio_metrics.max_drawdown = self._calculate_max_drawdown(returns)

        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {e}", exc_info=True)

    def _calculate_sharpe_ratio(self, returns: list[float]) -> float:
        """Calculate portfolio Sharpe ratio"""
        try:
            if not returns or len(returns) < 2:
                return 0.0

            mean_return = np.mean(returns)
            std_return = np.std(returns)

            if std_return == 0:
                return 0.0

            # Annualized Sharpe ratio
            return (mean_return * 252) / (std_return * np.sqrt(252))

        except Exception as e:
            self.logger.error(f"Error calculating Sharpe ratio: {e}", exc_info=True)
            return 0.0

    def _calculate_max_drawdown(self, returns: list[float]) -> float:
        """Calculate maximum drawdown"""
        try:
            if not returns:
                return 0.0

            cumulative = np.cumprod(1 + np.array(returns))
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max

            return abs(np.min(drawdown))

        except Exception as e:
            self.logger.error(f"Error calculating max drawdown: {e}", exc_info=True)
            return 0.0

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def execute_strategies_distributed(
        self,
        market_data: dict[str, Any],
        strategy_configs: list[dict[str, Any]] | None = None,
        num_cpus: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute multiple strategies in parallel using Ray actors.

        Each strategy evaluates independently on a Ray worker,
        enabling true parallel strategy execution.

        Args:
            market_data: Current market data for evaluation.
            strategy_configs: List of strategy configurations to execute.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Aggregated results from all strategy executions.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed strategy execution", exc_info=True)
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        if strategy_configs is None:
            strategy_configs = [
                {'strategy_id': sid, 'name': s.get('name', sid)}
                for sid, s in self.strategies.items()
            ] if hasattr(self, 'strategies') else []

        if not strategy_configs:
            return {'status': 'completed', 'results': [], 'n_strategies': 0}

        market_ref = ray.put(market_data)

        @ray.remote
        def _execute_strategy(market_ref, config: dict) -> dict:
            """Execute a single strategy on a Ray worker."""
            import numpy as _np
            import time as _time

            start = _time.time()
            _np.random.seed(hash(config.get('strategy_id', '')) % (2**32))

            market = market_ref
            market.get('price', 450)
            market.get('iv', 0.20)

            # Simulate strategy signal generation
            signal_strength = float(_np.random.uniform(-1, 1))
            confidence = float(_np.random.uniform(0.3, 0.95))

            return {
                'strategy_id': config.get('strategy_id', 'unknown'),
                'strategy_name': config.get('name', 'unknown'),
                'signal': signal_strength,
                'confidence': confidence,
                'recommended_action': 'buy' if signal_strength > 0.3 else ('sell' if signal_strength < -0.3 else 'hold'),
                'execution_time': _time.time() - start,
                'status': 'completed',
            }

        self.logger.info(f"Ray strategy execution: {len(strategy_configs)} strategies")

        futures = [_execute_strategy.remote(market_ref, cfg) for cfg in strategy_configs]
        results = ray.get(futures)

        return {
            'status': 'completed',
            'n_strategies': len(results),
            'results': results,
            'consensus_signal': float(np.mean([r['signal'] for r in results if r.get('status') == 'completed'])),
            'mean_confidence': float(np.mean([r['confidence'] for r in results if r.get('status') == 'completed'])),
        }

    # --------------------------------------------------------------------------
    # RISKFOLIO-LIB: STRATEGY WEIGHT OPTIMIZATION
    # --------------------------------------------------------------------------

    def optimize_strategy_weights_riskfolio(
        self,
        strategy_returns: pd.DataFrame,
        risk_measure: str = 'CVaR',
        objective: str = 'max_sharpe',
    ) -> dict[str, Any]:
        """
        Optimize strategy weights using RiskFolio-Lib with risk constraints.

        Replaces equal-weight or heuristic allocation with institutional-grade
        optimization using CVaR, HRP, or risk parity.

        Args:
            strategy_returns: DataFrame of strategy returns (columns = strategies).
            risk_measure: Risk measure ('MV', 'CVaR', 'CDaR', 'MDD').
            objective: Optimization objective ('max_sharpe', 'min_risk', 'risk_parity').

        Returns:
            Optimized strategy weights and portfolio statistics.
        """
        try:
            import riskfolio as rp
        except ImportError:
            self.logger.warning("riskfolio not installed — using equal weights", exc_info=True)
            n = strategy_returns.shape[1]
            return {'weights': {col: 1.0 / n for col in strategy_returns.columns},
                    '_backend': 'fallback'}

        port = rp.Portfolio(returns=strategy_returns)
        port.assets_stats(method_mu='hist', method_cov='ledoit_wolf')

        weights = None
        if objective == 'risk_parity':
            weights = port.rp_optimization(
                model='Classic', rm=risk_measure, rf=0.05 / 252, b=None)
        else:
            obj_map = {'max_sharpe': 'Sharpe', 'min_risk': 'MinRisk'}
            rp_obj = obj_map.get(objective, 'Sharpe')
            weights = port.optimization(
                model='Classic', rm=risk_measure, obj=rp_obj, rf=0.05 / 252)

        if weights is not None and not weights.empty:
            weight_dict = {col: float(weights.loc[col].iloc[0]) for col in weights.index}
            self.logger.info(f"RiskFolio strategy weights ({objective}/{risk_measure}): "
                             f"{weight_dict}")
            return {
                'weights': weight_dict,
                'objective': objective,
                'risk_measure': risk_measure,
                '_backend': 'riskfolio',
            }

        n = strategy_returns.shape[1]
        return {'weights': {col: 1.0 / n for col in strategy_returns.columns},
                '_backend': 'fallback'}

# ==============================================================================
# PYQT6 ORCHESTRATOR DASHBOARD
# ==============================================================================

class StrategyOrchestratorDashboard(QWidget):
    """
    PyQt6 dashboard for Strategy Orchestrator monitoring and control.

    Provides comprehensive real-time monitoring of:
    - Portfolio allocation and performance
    - Strategy performance attribution
    - Market regime analysis
    - Risk monitoring and alerts
    - Manual orchestration controls
    """

    # Qt signals
    portfolioUpdated = Signal(dict)
    rebalanceCompleted = Signal(str)

    def __init__(self, orchestrator: StrategyOrchestrator | None = None):
        super().__init__()

        self.orchestrator = orchestrator

        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        # Data models for tables
        self.strategy_model = None
        self.performance_model = None

        # Setup UI
        self.setup_ui()
        self.setup_monitoring()

        # Connect orchestrator if available
        if self.orchestrator:
            self.setup_orchestrator_integration()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()

        # Header with control buttons
        self.create_header_section(main_layout)

        # Main content with tabs
        self.create_main_content(main_layout)

        # Status bar
        self.create_status_bar(main_layout)

        self.setLayout(main_layout)
        self.setMinimumSize(1200, 800)
        self.setWindowTitle("SPYDER - Strategy Orchestrator Dashboard")

    def create_header_section(self, layout):
        """Create header with controls"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("🎯 SPYDER Strategy Orchestrator")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)

        # Status indicator
        self.status_label = QLabel("🔄 Initializing...")
        status_font = QFont()
        status_font.setPointSize(14)
        self.status_label.setFont(status_font)

        # Control buttons
        self.start_btn = QPushButton("🚀 Start Orchestration")
        self.start_btn.clicked.connect(self.start_orchestration)

        self.stop_btn = QPushButton("🛑 Stop Orchestration")
        self.stop_btn.clicked.connect(self.stop_orchestration)

        self.rebalance_btn = QPushButton("⚖️ Rebalance Now")
        self.rebalance_btn.clicked.connect(self.manual_rebalance)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.start_btn)
        header_layout.addWidget(self.stop_btn)
        header_layout.addWidget(self.rebalance_btn)

        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)

    def create_main_content(self, layout):
        """Create main content with tabs"""
        self.tab_widget = QTabWidget()

        # Portfolio Overview
        self.create_portfolio_overview_tab()

        # Strategy Performance
        self.create_strategy_performance_tab()

        # Market Regime
        self.create_market_regime_tab()

        # Risk Management
        self.create_risk_management_tab()

        # Configuration
        self.create_configuration_tab()

        layout.addWidget(self.tab_widget)

    def create_portfolio_overview_tab(self):
        """Create portfolio overview tab"""
        overview_widget = QWidget()
        layout = QVBoxLayout()

        # Portfolio metrics
        metrics_group = QGroupBox("📊 Portfolio Metrics")
        metrics_layout = QHBoxLayout()

        # Left column metrics
        left_metrics = QVBoxLayout()
        self.total_capital_label = QLabel("Total Capital: $0")
        self.allocated_capital_label = QLabel("Allocated: $0")
        self.total_pnl_label = QLabel("Total P&L: $0")
        self.daily_pnl_label = QLabel("Daily P&L: $0")

        left_metrics.addWidget(self.total_capital_label)
        left_metrics.addWidget(self.allocated_capital_label)
        left_metrics.addWidget(self.total_pnl_label)
        left_metrics.addWidget(self.daily_pnl_label)

        # Right column metrics
        right_metrics = QVBoxLayout()
        self.sharpe_ratio_label = QLabel("Sharpe Ratio: 0.00")
        self.max_drawdown_label = QLabel("Max Drawdown: 0.0%")
        self.active_strategies_label = QLabel("Active Strategies: 0")
        self.win_rate_label = QLabel("Win Rate: 0.0%")

        right_metrics.addWidget(self.sharpe_ratio_label)
        right_metrics.addWidget(self.max_drawdown_label)
        right_metrics.addWidget(self.active_strategies_label)
        right_metrics.addWidget(self.win_rate_label)

        metrics_layout.addLayout(left_metrics)
        metrics_layout.addLayout(right_metrics)
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # Allocation chart placeholder
        allocation_group = QGroupBox("📈 Strategy Allocations")
        allocation_layout = QVBoxLayout()

        # Create matplotlib figure for allocation pie chart
        self.allocation_figure = Figure(figsize=(8, 6))
        self.allocation_canvas = FigureCanvas(self.allocation_figure)
        allocation_layout.addWidget(self.allocation_canvas)

        allocation_group.setLayout(allocation_layout)
        layout.addWidget(allocation_group)

        overview_widget.setLayout(layout)
        self.tab_widget.addTab(overview_widget, "Portfolio Overview")

    def create_strategy_performance_tab(self):
        """Create strategy performance tab"""
        performance_widget = QWidget()
        layout = QVBoxLayout()

        # Strategy table
        strategies_group = QGroupBox("📋 Active Strategies")
        strategies_layout = QVBoxLayout()

        self.strategies_table = QTableWidget()
        self.strategies_table.setColumnCount(8)
        self.strategies_table.setHorizontalHeaderLabels([
            'Strategy', 'Type', 'Allocation', 'Capital', 'P&L', 'Performance Score', 'Health', 'Status'
        ])

        header = self.strategies_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        strategies_layout.addWidget(self.strategies_table)

        # Strategy controls
        controls_layout = QHBoxLayout()

        self.pause_strategy_btn = QPushButton("⏸️ Pause Strategy")
        self.resume_strategy_btn = QPushButton("▶️ Resume Strategy")
        self.remove_strategy_btn = QPushButton("❌ Remove Strategy")

        controls_layout.addWidget(self.pause_strategy_btn)
        controls_layout.addWidget(self.resume_strategy_btn)
        controls_layout.addWidget(self.remove_strategy_btn)
        controls_layout.addStretch()

        strategies_layout.addLayout(controls_layout)
        strategies_group.setLayout(strategies_layout)
        layout.addWidget(strategies_group)

        # Performance chart
        performance_group = QGroupBox("📈 Performance Chart")
        performance_layout = QVBoxLayout()

        self.performance_figure = Figure(figsize=(12, 6))
        self.performance_canvas = FigureCanvas(self.performance_figure)
        performance_layout.addWidget(self.performance_canvas)

        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        performance_widget.setLayout(layout)
        self.tab_widget.addTab(performance_widget, "Strategy Performance")

    def create_market_regime_tab(self):
        """Create market regime analysis tab"""
        regime_widget = QWidget()
        layout = QVBoxLayout()

        # Current regime
        current_regime_group = QGroupBox("🌡️ Current Market Regime")
        regime_layout = QHBoxLayout()

        self.current_regime_label = QLabel("Regime: Unknown")
        self.regime_confidence_label = QLabel("Confidence: 0%")
        self.vix_level_label = QLabel("VIX: 0.0")
        self.trend_strength_label = QLabel("Trend: 0.0")

        regime_layout.addWidget(self.current_regime_label)
        regime_layout.addWidget(self.regime_confidence_label)
        regime_layout.addWidget(self.vix_level_label)
        regime_layout.addWidget(self.trend_strength_label)

        current_regime_group.setLayout(regime_layout)
        layout.addWidget(current_regime_group)

        # Regime strategy weights
        weights_group = QGroupBox("⚖️ Optimal Strategy Weights for Current Regime")
        weights_layout = QVBoxLayout()

        self.regime_weights_table = QTableWidget()
        self.regime_weights_table.setColumnCount(3)
        self.regime_weights_table.setHorizontalHeaderLabels(['Strategy Type', 'Optimal Weight', 'Current Weight'])

        weights_layout.addWidget(self.regime_weights_table)
        weights_group.setLayout(weights_layout)
        layout.addWidget(weights_group)

        regime_widget.setLayout(layout)
        self.tab_widget.addTab(regime_widget, "Market Regime")

    def create_risk_management_tab(self):
        """Create risk management tab"""
        risk_widget = QWidget()
        layout = QVBoxLayout()

        # Risk metrics
        risk_metrics_group = QGroupBox("⚠️ Risk Metrics")
        risk_layout = QHBoxLayout()

        self.portfolio_var_label = QLabel("Portfolio VaR: 0.0%")
        self.concentration_label = QLabel("Max Concentration: 0.0%")
        self.correlation_label = QLabel("Avg Correlation: 0.00")

        risk_layout.addWidget(self.portfolio_var_label)
        risk_layout.addWidget(self.concentration_label)
        risk_layout.addWidget(self.correlation_label)

        risk_metrics_group.setLayout(risk_layout)
        layout.addWidget(risk_metrics_group)

        # Strategy conflicts
        conflicts_group = QGroupBox("⚡ Strategy Conflicts")
        conflicts_layout = QVBoxLayout()

        self.conflicts_list = QListWidget()
        conflicts_layout.addWidget(self.conflicts_list)

        conflicts_group.setLayout(conflicts_layout)
        layout.addWidget(conflicts_group)

        risk_widget.setLayout(layout)
        self.tab_widget.addTab(risk_widget, "Risk Management")

    def create_configuration_tab(self):
        """Create configuration tab"""
        config_widget = QWidget()
        layout = QVBoxLayout()

        # Orchestration mode
        mode_group = QGroupBox("🎛️ Orchestration Configuration")
        mode_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([mode.value for mode in OrchestrationMode])
        mode_layout.addWidget(QLabel("Orchestration Mode:"))
        mode_layout.addWidget(self.mode_combo)

        self.allocation_combo = QComboBox()
        self.allocation_combo.addItems([method.value for method in AllocationMethod])
        mode_layout.addWidget(QLabel("Allocation Method:"))
        mode_layout.addWidget(self.allocation_combo)

        self.rebalance_freq_spin = QSpinBox()
        self.rebalance_freq_spin.setRange(5, 120)
        self.rebalance_freq_spin.setValue(30)
        self.rebalance_freq_spin.setSuffix(" minutes")
        mode_layout.addWidget(QLabel("Rebalance Frequency:"))
        mode_layout.addWidget(self.rebalance_freq_spin)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Risk limits
        limits_group = QGroupBox("🛡️ Risk Limits")
        limits_layout = QVBoxLayout()

        self.max_allocation_spin = QDoubleSpinBox()
        self.max_allocation_spin.setRange(0.1, 0.8)
        self.max_allocation_spin.setValue(0.4)
        self.max_allocation_spin.setSuffix("%")
        limits_layout.addWidget(QLabel("Max Strategy Allocation:"))
        limits_layout.addWidget(self.max_allocation_spin)

        self.var_limit_spin = QDoubleSpinBox()
        self.var_limit_spin.setRange(0.01, 0.1)
        self.var_limit_spin.setValue(0.02)
        self.var_limit_spin.setSuffix("%")
        limits_layout.addWidget(QLabel("Portfolio VaR Limit:"))
        limits_layout.addWidget(self.var_limit_spin)

        limits_group.setLayout(limits_layout)
        layout.addWidget(limits_group)

        config_widget.setLayout(layout)
        self.tab_widget.addTab(config_widget, "Configuration")

    def create_status_bar(self, layout):
        """Create status bar"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout()

        self.status_bar_label = QLabel("Ready")
        self.last_update_label = QLabel("")

        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_bar_label)
        status_layout.addStretch()
        status_layout.addWidget(self.last_update_label)

        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)

    def setup_monitoring(self):
        """Setup monitoring timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(2000)  # Update every 2 seconds

        # Initial update
        self.update_display()

    def setup_orchestrator_integration(self):
        """Setup integration with orchestrator"""
        # Connect signals and setup callbacks
        pass

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================

    def update_display(self):
        """Update all dashboard displays"""
        if not self.orchestrator:
            return

        try:
            # Get portfolio status
            status = self.orchestrator.get_portfolio_status()

            # Update status indicator
            if status.get('orchestration_active'):
                self.status_label.setText("✅ Running")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.status_label.setText("⏸️ Stopped")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")

            # Update portfolio metrics
            self.update_portfolio_metrics(status)

            # Update strategy table
            self.update_strategy_table()

            # Update market regime
            self.update_market_regime_display()

            # Update charts
            self.update_allocation_chart()

            # Update status bar
            self.last_update_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}", exc_info=True)

    def update_portfolio_metrics(self, status: dict[str, Any]):
        """Update portfolio metrics display"""
        try:
            self.total_capital_label.setText(f"Total Capital: ${status.get('total_capital', 0):,.2f}")
            self.allocated_capital_label.setText(f"Allocated: ${status.get('allocated_capital', 0):,.2f}")
            self.total_pnl_label.setText(f"Total P&L: ${status.get('total_pnl', 0):,.2f}")
            self.daily_pnl_label.setText(f"Daily P&L: ${status.get('daily_pnl', 0):,.2f}")

            self.sharpe_ratio_label.setText(f"Sharpe Ratio: {status.get('portfolio_sharpe', 0):.2f}")
            self.max_drawdown_label.setText(f"Max Drawdown: {status.get('max_drawdown', 0):.1%}")
            self.active_strategies_label.setText(f"Active Strategies: {status.get('active_strategies', 0)}")

        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {e}", exc_info=True)

    def update_strategy_table(self):
        """Update strategy performance table"""
        if not self.orchestrator:
            return

        try:
            performance_data = self.orchestrator.get_strategy_performance_attribution()

            if performance_data.empty:
                return

            # Update table
            self.strategies_table.setRowCount(len(performance_data))

            for row, (_, data) in enumerate(performance_data.iterrows()):
                self.strategies_table.setItem(row, 0, QTableWidgetItem(data['strategy_name']))
                self.strategies_table.setItem(row, 1, QTableWidgetItem(data['strategy_type']))
                self.strategies_table.setItem(row, 2, QTableWidgetItem(f"{data['allocation']:.1%}"))
                self.strategies_table.setItem(row, 3, QTableWidgetItem(f"${data['allocated_capital']:,.0f}"))
                self.strategies_table.setItem(row, 4, QTableWidgetItem(f"${data['strategy_pnl']:,.2f}"))
                self.strategies_table.setItem(row, 5, QTableWidgetItem(f"{data['performance_score']:.2f}"))
                self.strategies_table.setItem(row, 6, QTableWidgetItem(f"{data['health_score']:.2f}"))
                self.strategies_table.setItem(row, 7, QTableWidgetItem("Active"))

        except Exception as e:
            self.logger.error(f"Error updating strategy table: {e}", exc_info=True)

    def update_market_regime_display(self):
        """Update market regime information"""
        if not self.orchestrator:
            return

        try:
            regime_data = self.orchestrator.market_regime

            self.current_regime_label.setText(f"Regime: {regime_data.current_regime.value}")
            self.regime_confidence_label.setText(f"Confidence: {regime_data.regime_confidence:.1%}")
            self.vix_level_label.setText(f"VIX: {regime_data.vix_level:.1f}")
            self.trend_strength_label.setText(f"Trend: {regime_data.trend_strength:.2f}")

        except Exception as e:
            self.logger.error(f"Error updating market regime display: {e}", exc_info=True)

    def update_allocation_chart(self):
        """Update allocation pie chart"""
        if not self.orchestrator:
            return

        try:
            # Clear previous plot
            self.allocation_figure.clear()
            ax = self.allocation_figure.add_subplot(111)

            # Get allocation data
            allocations = {}
            for _strategy_id, allocation in self.orchestrator.strategy_allocations.items():
                allocations[allocation.strategy_name] = allocation.current_allocation

            if allocations:
                # Create pie chart
                labels = list(allocations.keys())
                sizes = list(allocations.values())

                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                ax.set_title('Strategy Allocations')

            self.allocation_canvas.draw()

        except Exception as e:
            self.logger.error(f"Error updating allocation chart: {e}", exc_info=True)

    def start_orchestration(self):
        """Start orchestration"""
        if self.orchestrator:
            success = self.orchestrator.start_orchestration()
            if success:
                self.status_bar_label.setText("Orchestration started")
            else:
                self.status_bar_label.setText("Failed to start orchestration")

    def stop_orchestration(self):
        """Stop orchestration"""
        if self.orchestrator:
            success = self.orchestrator.stop_orchestration()
            if success:
                self.status_bar_label.setText("Orchestration stopped")
            else:
                self.status_bar_label.setText("Failed to stop orchestration")

    def manual_rebalance(self):
        """Trigger manual rebalancing"""
        if self.orchestrator:
            success = self.orchestrator.rebalance_portfolio()
            if success:
                self.status_bar_label.setText("Manual rebalancing completed")
            else:
                self.status_bar_label.setText("Manual rebalancing failed")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_strategy_orchestrator(base_capital: float = DEFAULT_BASE_CAPITAL,
                                orchestration_mode: OrchestrationMode = OrchestrationMode.BALANCED,
                                allocation_method: AllocationMethod = AllocationMethod.PERFORMANCE_BASED,
                                connectivity_manager: IntegratedConnectivityManager | None = None) -> StrategyOrchestrator:
    """Factory function to create strategy orchestrator"""
    return StrategyOrchestrator(base_capital, orchestration_mode, allocation_method, connectivity_manager)

def create_orchestrator_dashboard(orchestrator: StrategyOrchestrator | None = None) -> StrategyOrchestratorDashboard:
    """Factory function to create orchestrator dashboard"""
    return StrategyOrchestratorDashboard(orchestrator)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    logging.info("🎯 SPYDER D12 - Strategy Orchestrator")
    logging.info("=" * 60)

    try:
        # Create orchestrator
        orchestrator = StrategyOrchestrator(
            base_capital=100000,
            orchestration_mode=OrchestrationMode.BALANCED,
            allocation_method=AllocationMethod.PERFORMANCE_BASED
        )

        logging.info("✅ Strategy Orchestrator initialized")
        logging.info("📊 Configuration:")
        logging.info(f"  Base Capital: ${orchestrator.base_capital:,.2f}")
        logging.info(f"  Orchestration Mode: {orchestrator.orchestration_mode.value}")
        logging.info(f"  Allocation Method: {orchestrator.allocation_method.value}")
        logging.info(f"  Available Strategies: {len(orchestrator.available_strategies)}")

        # Test portfolio status
        status = orchestrator.get_portfolio_status()
        logging.info("\n📈 Portfolio Status:")
        logging.info(f"  Total Capital: ${status['total_capital']:,.2f}")
        logging.info(f"  Available Capital: ${status['available_capital']:,.2f}")
        logging.info(f"  Active Strategies: {status['active_strategies']}")
        logging.info(f"  Market Regime: {status['market_regime']}")

        logging.info("\n✅ Strategy Orchestrator test completed!")

    except Exception as e:
        logging.info(f"❌ Error during testing: {e}")
        return False

    return True

if __name__ == "__main__":
    main()
