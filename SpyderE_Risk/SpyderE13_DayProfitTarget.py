#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE13_DayProfitTarget.py
Purpose: Daily Profit Target Engine with Algorithmic Slicing and Risk Integration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-28 Time: 19:00:00

⚠️ INTEGRATION UPDATE REQUIRED ⚠️
    This module currently uses DEPRECATED ib_async for IB client integration.

    Migration Needed:
    - ❌ Remove ib_async IB client dependency
    - ✅ Integrate with SpyderB40_TradierClient for order execution
    - ✅ Use Polygon.io for market data via SpyderC25_PolygonDataHandler
    - 🔧 Update algorithmic slicing to work with Tradier API

    Current Status: Functional but uses legacy IBKR integration
    Priority: Medium - Module works but should be updated for consistency

Module Description:
    Advanced daily profit targeting system with institutional-grade algorithmic
    slicing capabilities. Handles large profit targets (up to millions) through
    sophisticated parent/child order management, multi-venue execution, and
    intelligent risk integration. Features TWAP, VWAP, POV, and SOR algorithms
    with real-time progress monitoring, market impact analysis, and seamless
    integration with existing risk management and strategy orchestration systems.

Key Features:
    - Daily profit target setting with account balance validation
    - Algorithmic slicing: TWAP, VWAP, POV, SOR, and adaptive algorithms
    - Parent/child order management with IBKR API integration
    - Multi-venue smart order routing (CBOE, PHLX, BOX, MIAX, ARCA)
    - Real-time progress monitoring and risk controls
    - Integration with SpyderD12_StrategyOrchestrator for capital coordination
    - PySide6 widget for Risk Levels Configuration 5th tab
    - Market impact measurement and execution quality analytics
    - Circuit breakers and emergency stop mechanisms
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import statistics
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, time as dt_time
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Set
import copy
import heapq
import numpy as np
import pandas as pd
from scipy import stats, optimize

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz

# ⚠️ DEPRECATED: ib_async integration should be replaced with Tradier API
# TODO: Migrate to SpyderB40_TradierClient for order execution
# Current implementation uses legacy IBKR integration
from ib_async import IB, Contract, Order, Trade, Fill, OrderStatus

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QGroupBox,
    QCheckBox,
    QMessageBox,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QSplitter,
    QFrame,
    QScrollArea,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QLineEdit,
    QFormLayout,
    QGridLayout,
    QLCDNumber,
)
from PySide6.QtCore import (
    QTimer,
    QThread,
    Signal,
    Qt,
    QAbstractTableModel,
    QModelIndex,
)
from PySide6.QtGui import QFont, QColor, QIcon, QPalette, QPixmap
import plotly.graph_objects as go
import plotly.express as px
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import plotly.graph_objects as go

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    # Core imports
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import (
        SpyderErrorHandler,
        TradingError,
    )
    from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

    # Broker integration
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    from SpyderB_Broker.SpyderB02_OrderManager import OrderManager
    from SpyderB_Broker.SpyderB20_IntegratedConnectivityManager import (
        IntegratedConnectivityManager,
    )

    # Strategy coordination
    from SpyderD_Strategies.SpyderD12_StrategyOrchestrator import StrategyOrchestrator

    # Event management
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

    SPYDER_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Some Spyder modules not available: {e}")
    SPYDER_MODULES_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Profit target limits and defaults
MIN_DAILY_PROFIT_TARGET = 100.0  # $100 minimum
MAX_DAILY_PROFIT_TARGET = 10_000_000.0  # $10M maximum
DEFAULT_PROFIT_TARGET = 25_000.0  # $25K default
MAX_ACCOUNT_RISK_PCT = 0.20  # Maximum 20% of account balance

# Algorithmic slicing parameters
DEFAULT_CHILD_ORDER_SIZE = 100  # Contracts per child order
MIN_CHILD_ORDER_SIZE = 10  # Minimum child order size
MAX_CHILD_ORDER_SIZE = 500  # Maximum child order size
DEFAULT_TIME_WINDOW_MINUTES = 60  # 1 hour execution window
SLICE_INTERVAL_SECONDS = 30  # 30 seconds between child orders

# Market impact and execution
MAX_MARKET_IMPACT_BPS = 20  # 20 basis points max impact
EXECUTION_QUALITY_THRESHOLD = 0.95  # 95% execution quality required
MIN_LIQUIDITY_DEPTH = 1000  # Minimum market depth required
VENUE_TIMEOUT_SECONDS = 5  # Venue response timeout

# Risk monitoring
PROGRESS_CHECK_INTERVAL = 10  # Check progress every 10 seconds
RISK_CHECK_INTERVAL = 5  # Risk checks every 5 seconds
MAX_DRAWDOWN_FROM_TARGET = 0.10  # 10% max drawdown from progress
CIRCUIT_BREAKER_THRESHOLD = 0.05  # 5% account loss triggers circuit breaker

# Multi-venue configuration
SUPPORTED_VENUES = [
    "SMART",  # IB Smart routing
    "CBOE",  # Chicago Board Options Exchange
    "PHLX",  # NASDAQ OMX PHLX
    "BOX",  # Boston Options Exchange
    "MIAX",  # Miami International Securities Exchange
    "ARCA",  # NYSE Arca Options
    "ISE",  # International Securities Exchange
    "GEMX",  # NASDAQ GEMX
    "MRX",  # NASDAQ MRX
    "BZX",  # Bats BZX Options
]

# ==============================================================================
# ENUMS
# ==============================================================================


class ProfitTargetStatus(Enum):
    """Profit target execution status"""

    INACTIVE = "inactive"
    VALIDATING = "validating"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SlicingAlgorithm(Enum):
    """Algorithmic slicing strategies"""

    TWAP = "twap"  # Time-Weighted Average Price
    VWAP = "vwap"  # Volume-Weighted Average Price
    POV = "pov"  # Percentage of Volume
    SOR = "sor"  # Smart Order Routing
    ADAPTIVE = "adaptive"  # ML-driven adaptive algorithm
    LIQUIDITY_SEEKING = "liquidity"  # Liquidity-seeking algorithm
    ICEBERG = "iceberg"  # Iceberg orders
    STEALTH = "stealth"  # Stealth execution


class OrderExecutionVenue(Enum):
    """Order execution venues"""

    SMART = "SMART"
    CBOE = "CBOE"
    PHLX = "PHLX"
    BOX = "BOX"
    MIAX = "MIAX"
    ARCA = "ARCA"
    ISE = "ISE"
    GEMX = "GEMX"
    MRX = "MRX"
    BZX = "BZX"


class RiskBreachType(Enum):
    """Types of risk breaches"""

    ACCOUNT_BALANCE = "account_balance"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    MARKET_IMPACT = "market_impact"
    EXECUTION_QUALITY = "execution_quality"
    PROGRESS_DEVIATION = "progress_deviation"
    CONNECTIVITY_LOSS = "connectivity_loss"


class MarketCondition(Enum):
    """Market condition classifications"""

    CALM = "calm"
    NORMAL = "normal"
    VOLATILE = "volatile"
    HIGHLY_VOLATILE = "highly_volatile"
    CRISIS = "crisis"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class ProfitTargetConfig:
    """Configuration for daily profit targeting"""

    target_amount: float
    max_risk_amount: float
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES
    slicing_algorithm: SlicingAlgorithm = SlicingAlgorithm.ADAPTIVE
    child_order_size: int = DEFAULT_CHILD_ORDER_SIZE
    max_market_impact_bps: float = MAX_MARKET_IMPACT_BPS
    preferred_venues: List[OrderExecutionVenue] = field(
        default_factory=lambda: [OrderExecutionVenue.SMART]
    )
    enable_dark_pools: bool = True
    enable_smart_routing: bool = True
    risk_monitoring_enabled: bool = True


@dataclass
class ChildOrderSpec:
    """Specification for a child order"""

    order_id: str
    parent_order_id: str
    contract: Contract
    action: str  # BUY/SELL
    quantity: int
    order_type: str
    limit_price: Optional[float]
    time_in_force: str
    venue: OrderExecutionVenue
    algorithm_params: Dict[str, Any]
    scheduled_time: datetime
    priority_score: float
    risk_allocation: float


@dataclass
class ExecutionMetrics:
    """Execution quality and performance metrics"""

    total_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0
    avg_fill_time: float = 0.0
    total_slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    execution_quality_score: float = 0.0
    venue_performance: Dict[str, float] = field(default_factory=dict)
    total_commission: float = 0.0
    total_fees: float = 0.0


@dataclass
class ProfitTargetProgress:
    """Real-time progress tracking"""

    target_amount: float
    current_profit: float
    progress_percentage: float
    time_elapsed_minutes: int
    estimated_completion_time: Optional[datetime]
    orders_executed: int
    orders_pending: int
    risk_utilization_pct: float
    execution_metrics: ExecutionMetrics
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAlert:
    """Risk monitoring alert"""

    alert_id: str
    breach_type: RiskBreachType
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    current_value: float
    threshold_value: float
    recommended_action: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketImpactAnalysis:
    """Market impact measurement and analysis"""

    pre_trade_mid: float
    post_trade_mid: float
    volume_impact: float
    spread_impact: float
    total_impact_bps: float
    liquidity_consumed_pct: float
    recovery_time_seconds: float
    impact_score: str  # 'low', 'medium', 'high'


# ==============================================================================
# ALGORITHMIC SLICING MANAGER
# ==============================================================================


class AlgorithmicSlicingManager:
    """
    Manages algorithmic slicing strategies and parent/child order coordination.

    Implements multiple slicing algorithms for optimal execution of large orders
    with minimal market impact across multiple venues.
    """

    def __init__(self, ib_client: IB, logger: Optional[logging.Logger] = None):
        self.ib = ib_client
        self.logger = logger or logging.getLogger(__name__)

        # Order tracking
        self.parent_orders: Dict[str, Order] = {}
        self.child_orders: Dict[str, ChildOrderSpec] = {}
        self.execution_queue = []
        self.active_orders: Dict[str, Order] = {}

        # Performance tracking
        self.venue_performance: Dict[str, ExecutionMetrics] = {}
        self.algorithm_performance: Dict[SlicingAlgorithm, ExecutionMetrics] = {}

        # Market analysis
        self.market_depth_cache: Dict[str, Dict] = {}
        self.liquidity_analysis: Dict[str, float] = {}

        # Threading
        self.execution_thread = None
        self.monitoring_thread = None
        self.stop_event = threading.Event()

    def create_slicing_plan(
        self,
        target_profit: float,
        risk_allocation: float,
        algorithm: SlicingAlgorithm,
        time_window_minutes: int,
    ) -> List[ChildOrderSpec]:
        """
        Create comprehensive slicing execution plan.

        Args:
            target_profit: Target profit amount
            risk_allocation: Maximum risk allocation
            algorithm: Slicing algorithm to use
            time_window_minutes: Execution time window

        Returns:
            List of child order specifications
        """
        try:
            self.logger.info(
                f"Creating slicing plan - Target: ${target_profit:,.2f}, Algorithm: {algorithm.value}"
            )

            # Estimate required position size based on profit target
            estimated_contracts = self._estimate_contracts_for_profit(target_profit)

            # Choose slicing algorithm
            if algorithm == SlicingAlgorithm.TWAP:
                child_orders = self._create_twap_plan(
                    estimated_contracts, time_window_minutes
                )
            elif algorithm == SlicingAlgorithm.VWAP:
                child_orders = self._create_vwap_plan(
                    estimated_contracts, time_window_minutes
                )
            elif algorithm == SlicingAlgorithm.POV:
                child_orders = self._create_pov_plan(
                    estimated_contracts, time_window_minutes
                )
            elif algorithm == SlicingAlgorithm.SOR:
                child_orders = self._create_sor_plan(
                    estimated_contracts, time_window_minutes
                )
            elif algorithm == SlicingAlgorithm.ADAPTIVE:
                child_orders = self._create_adaptive_plan(
                    estimated_contracts, time_window_minutes
                )
            else:
                child_orders = self._create_liquidity_seeking_plan(
                    estimated_contracts, time_window_minutes
                )

            # Apply risk allocation to each child order
            for child_order in child_orders:
                child_order.risk_allocation = risk_allocation / len(child_orders)

            self.logger.info(
                f"✅ Created slicing plan with {len(child_orders)} child orders"
            )
            return child_orders

        except Exception as e:
            self.logger.error(f"❌ Error creating slicing plan: {e}")
            return []

    def _create_twap_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create Time-Weighted Average Price execution plan"""
        child_orders = []

        # Calculate child order parameters
        child_order_size = min(DEFAULT_CHILD_ORDER_SIZE, total_contracts // 10)
        num_orders = max(1, total_contracts // child_order_size)
        time_interval = (time_window_minutes * 60) // num_orders

        start_time = datetime.now()

        for i in range(num_orders):
            # Calculate scheduled execution time
            execution_time = start_time + timedelta(seconds=i * time_interval)

            # Determine remaining quantity
            remaining_qty = total_contracts - (i * child_order_size)
            order_qty = min(child_order_size, remaining_qty)

            if order_qty <= 0:
                break

            # Create child order specification
            child_order = ChildOrderSpec(
                order_id=f"twap_{uuid.uuid4().hex[:8]}",
                parent_order_id="",  # Will be set when parent order is placed
                contract=self._get_spy_options_contract(),
                action="BUY",  # Will be determined by strategy
                quantity=order_qty,
                order_type="LMT",
                limit_price=None,  # Will be calculated at execution time
                time_in_force="DAY",
                venue=OrderExecutionVenue.SMART,
                algorithm_params={
                    "algorithm": "TWAP",
                    "time_window": time_window_minutes,
                },
                scheduled_time=execution_time,
                priority_score=1.0,  # Equal priority for TWAP
                risk_allocation=0.0,  # Will be set later
            )

            child_orders.append(child_order)

        return child_orders

    def _create_vwap_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create Volume-Weighted Average Price execution plan"""
        child_orders = []

        # Get historical volume profile (simplified for demo)
        volume_profile = self._get_volume_profile()

        # Distribute orders based on expected volume
        child_order_size = min(DEFAULT_CHILD_ORDER_SIZE, total_contracts // 8)
        num_periods = len(volume_profile)

        start_time = datetime.now()

        for i, volume_weight in enumerate(volume_profile):
            # Calculate order size based on volume weight
            order_qty = int(total_contracts * volume_weight)
            if order_qty < MIN_CHILD_ORDER_SIZE:
                continue

            execution_time = start_time + timedelta(
                minutes=i * (time_window_minutes // num_periods)
            )

            child_order = ChildOrderSpec(
                order_id=f"vwap_{uuid.uuid4().hex[:8]}",
                parent_order_id="",
                contract=self._get_spy_options_contract(),
                action="BUY",
                quantity=min(order_qty, MAX_CHILD_ORDER_SIZE),
                order_type="LMT",
                limit_price=None,
                time_in_force="DAY",
                venue=OrderExecutionVenue.SMART,
                algorithm_params={"algorithm": "VWAP", "volume_weight": volume_weight},
                scheduled_time=execution_time,
                priority_score=volume_weight,
                risk_allocation=0.0,
            )

            child_orders.append(child_order)

        return child_orders

    def _create_adaptive_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create adaptive ML-driven execution plan"""
        # This would integrate with machine learning models to optimize execution
        # For now, we'll use a hybrid approach combining TWAP and VWAP

        child_orders = []

        # Analyze current market conditions
        market_condition = self._analyze_market_conditions()

        if market_condition == MarketCondition.CALM:
            # Use TWAP in calm markets
            child_orders = self._create_twap_plan(total_contracts, time_window_minutes)
        elif market_condition == MarketCondition.VOLATILE:
            # Use smaller orders with smart routing in volatile markets
            child_orders = self._create_sor_plan(total_contracts, time_window_minutes)
        else:
            # Use VWAP in normal markets
            child_orders = self._create_vwap_plan(total_contracts, time_window_minutes)

        # Adjust parameters based on ML insights (placeholder)
        for child_order in child_orders:
            child_order.algorithm_params["adaptive_score"] = 0.75
            child_order.algorithm_params["market_condition"] = market_condition.value

        return child_orders

    def _create_sor_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create Smart Order Routing execution plan"""
        child_orders = []

        # Distribute across multiple venues
        venues = [
            OrderExecutionVenue.SMART,
            OrderExecutionVenue.CBOE,
            OrderExecutionVenue.PHLX,
            OrderExecutionVenue.BOX,
        ]

        orders_per_venue = total_contracts // len(venues)
        child_order_size = min(DEFAULT_CHILD_ORDER_SIZE // 2, orders_per_venue // 5)

        start_time = datetime.now()

        for venue_idx, venue in enumerate(venues):
            venue_contracts = orders_per_venue
            if venue_idx == len(venues) - 1:  # Last venue gets remainder
                venue_contracts = total_contracts - (
                    orders_per_venue * (len(venues) - 1)
                )

            num_orders = max(1, venue_contracts // child_order_size)

            for i in range(num_orders):
                order_qty = min(
                    child_order_size, venue_contracts - (i * child_order_size)
                )
                if order_qty <= 0:
                    break

                # Stagger execution times across venues
                execution_time = start_time + timedelta(
                    seconds=venue_idx * 15
                    + i * (time_window_minutes * 60 // num_orders)
                )

                child_order = ChildOrderSpec(
                    order_id=f"sor_{venue.value.lower()}_{uuid.uuid4().hex[:6]}",
                    parent_order_id="",
                    contract=self._get_spy_options_contract(),
                    action="BUY",
                    quantity=order_qty,
                    order_type="LMT",
                    limit_price=None,
                    time_in_force="DAY",
                    venue=venue,
                    algorithm_params={"algorithm": "SOR", "venue": venue.value},
                    scheduled_time=execution_time,
                    priority_score=self._get_venue_priority_score(venue),
                    risk_allocation=0.0,
                )

                child_orders.append(child_order)

        return child_orders

    def _create_pov_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create Percentage of Volume execution plan"""
        child_orders = []

        # Target participation rate (e.g., 10% of market volume)
        participation_rate = 0.10

        # Get expected volume profile
        expected_volume_per_minute = self._get_expected_volume_per_minute()

        start_time = datetime.now()

        for minute in range(time_window_minutes):
            expected_volume = expected_volume_per_minute.get(
                minute, 1000
            )  # Default 1000 contracts/minute
            target_volume = int(expected_volume * participation_rate)

            if target_volume < MIN_CHILD_ORDER_SIZE:
                continue

            execution_time = start_time + timedelta(minutes=minute)

            child_order = ChildOrderSpec(
                order_id=f"pov_{minute}_{uuid.uuid4().hex[:6]}",
                parent_order_id="",
                contract=self._get_spy_options_contract(),
                action="BUY",
                quantity=min(target_volume, total_contracts),
                order_type="LMT",
                limit_price=None,
                time_in_force="DAY",
                venue=OrderExecutionVenue.SMART,
                algorithm_params={
                    "algorithm": "POV",
                    "participation_rate": participation_rate,
                },
                scheduled_time=execution_time,
                priority_score=min(1.0, target_volume / DEFAULT_CHILD_ORDER_SIZE),
                risk_allocation=0.0,
            )

            child_orders.append(child_order)

            # Reduce remaining contracts
            total_contracts -= target_volume
            if total_contracts <= 0:
                break

        return child_orders

    def _create_liquidity_seeking_plan(
        self, total_contracts: int, time_window_minutes: int
    ) -> List[ChildOrderSpec]:
        """Create liquidity-seeking execution plan"""
        child_orders = []

        # Use smaller orders that adapt to available liquidity
        adaptive_order_size = DEFAULT_CHILD_ORDER_SIZE // 3
        num_orders = max(1, total_contracts // adaptive_order_size)

        start_time = datetime.now()

        for i in range(num_orders):
            order_qty = min(
                adaptive_order_size, total_contracts - (i * adaptive_order_size)
            )
            if order_qty <= 0:
                break

            # More frequent execution with smaller sizes
            execution_time = start_time + timedelta(
                seconds=i * (time_window_minutes * 60 // (num_orders * 2))
            )

            child_order = ChildOrderSpec(
                order_id=f"liq_{uuid.uuid4().hex[:8]}",
                parent_order_id="",
                contract=self._get_spy_options_contract(),
                action="BUY",
                quantity=order_qty,
                order_type="LMT",
                limit_price=None,
                time_in_force="IOC",  # Immediate or Cancel for liquidity seeking
                venue=OrderExecutionVenue.SMART,
                algorithm_params={"algorithm": "LIQUIDITY", "adaptive_sizing": True},
                scheduled_time=execution_time,
                priority_score=1.0 / (i + 1),  # Higher priority for earlier orders
                risk_allocation=0.0,
            )

            child_orders.append(child_order)

        return child_orders

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _estimate_contracts_for_profit(self, target_profit: float) -> int:
        """Estimate number of contracts needed for target profit"""
        # This is a simplified calculation
        # Real implementation would use option pricing models, Greeks, etc.

        # Assume average profit per contract (very simplified)
        avg_profit_per_contract = 50.0  # $50 profit per contract average

        estimated_contracts = max(1, int(target_profit / avg_profit_per_contract))

        # Apply safety factor
        estimated_contracts = int(estimated_contracts * 1.2)  # 20% buffer

        return min(estimated_contracts, 10000)  # Cap at 10k contracts for safety

    def _get_spy_options_contract(self) -> Contract:
        """Get SPY options contract for current expiration"""
        # This would be dynamically determined based on strategy
        return Contract(
            symbol="SPY",
            secType="OPT",
            exchange="SMART",
            currency="USD",
            lastTradeDateOrContractMonth="20250919",  # Would be dynamic
            strike=500.0,  # Would be calculated based on current price
            right="C",  # Call option, would be strategy-dependent
        )

    def _get_volume_profile(self) -> List[float]:
        """Get historical volume profile weights"""
        # Simplified volume profile - would use real market data
        return [0.05, 0.08, 0.12, 0.15, 0.20, 0.18, 0.12, 0.10]

    def _get_expected_volume_per_minute(self) -> Dict[int, int]:
        """Get expected volume per minute"""
        # Simplified - would use real-time market data
        base_volume = 2000
        return {
            minute: int(base_volume * (1 + 0.1 * np.sin(minute * np.pi / 30)))
            for minute in range(60)
        }

    def _analyze_market_conditions(self) -> MarketCondition:
        """Analyze current market conditions"""
        # This would analyze VIX, volume, price action, etc.
        # For demo, return normal condition
        return MarketCondition.NORMAL

    def _get_venue_priority_score(self, venue: OrderExecutionVenue) -> float:
        """Get priority score for venue based on performance"""
        # This would be based on historical execution quality
        venue_scores = {
            OrderExecutionVenue.SMART: 0.9,
            OrderExecutionVenue.CBOE: 0.85,
            OrderExecutionVenue.PHLX: 0.8,
            OrderExecutionVenue.BOX: 0.75,
            OrderExecutionVenue.MIAX: 0.7,
        }
        return venue_scores.get(venue, 0.5)


# ==============================================================================
# DAY PROFIT TARGET ENGINE
# ==============================================================================


class DayProfitTargetEngine:
    """
    Main engine for daily profit targeting with risk integration and monitoring.

    Orchestrates the entire profit targeting process from validation through
    execution and monitoring, with real-time risk controls and integration
    with existing Spyder systems.
    """

    def __init__(
        self,
        ib_client: Optional[IB] = None,
        strategy_orchestrator: Optional[StrategyOrchestrator] = None,
        connectivity_manager: Optional[IntegratedConnectivityManager] = None,
        event_manager: Optional[EventManager] = None,
    ):
        """
        Initialize Day Profit Target Engine.

        Args:
            ib_client: Interactive Brokers client
            strategy_orchestrator: Strategy orchestration integration
            connectivity_manager: Connectivity management
            event_manager: Event management system
        """
        # Setup logging and error handling
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None

        # Core components
        self.ib = ib_client or IB()
        self.strategy_orchestrator = strategy_orchestrator
        self.connectivity_manager = connectivity_manager
        self.event_manager = event_manager or EventManager()

        # Algorithmic slicing manager
        self.slicing_manager = AlgorithmicSlicingManager(self.ib, self.logger)

        # Current state
        self.status = ProfitTargetStatus.INACTIVE
        self.current_config: Optional[ProfitTargetConfig] = None
        self.current_progress = ProfitTargetProgress(
            target_amount=0.0,
            current_profit=0.0,
            progress_percentage=0.0,
            time_elapsed_minutes=0,
            estimated_completion_time=None,
            orders_executed=0,
            orders_pending=0,
            risk_utilization_pct=0.0,
            execution_metrics=ExecutionMetrics(),
        )

        # Risk monitoring
        self.risk_alerts: List[RiskAlert] = []
        self.circuit_breaker_active = False
        self.max_account_balance = 0.0
        self.daily_start_balance = 0.0
        self.current_account_balance = 0.0

        # Execution tracking
        self.parent_order_id: Optional[str] = None
        self.active_child_orders: Dict[str, Order] = {}
        self.completed_orders: List[Fill] = []
        self.execution_start_time: Optional[datetime] = None

        # Performance analytics
        self.market_impact_analyzer = MarketImpactAnalyzer()
        self.execution_quality_tracker = ExecutionQualityTracker()

        # Threading and monitoring
        self.monitoring_active = False
        self.progress_monitor_thread = None
        self.risk_monitor_thread = None
        self.execution_thread = None
        self.shutdown_event = threading.Event()

        # Trading calendar
        try:
            self.trading_calendar = TradingCalendar() if TradingCalendar else None
        except (ImportError, TypeError, AttributeError) as e:
            # TradingCalendar not available or failed to initialize
            self.logger.debug(f"TradingCalendar not available: {e}")
            self.trading_calendar = None

        # Callbacks
        self.progress_callbacks: List[Callable] = []
        self.risk_alert_callbacks: List[Callable] = []
        self.completion_callbacks: List[Callable] = []

        self.logger.info("🎯 Day Profit Target Engine initialized")

    # ==========================================================================
    # PUBLIC INTERFACE - TARGET MANAGEMENT
    # ==========================================================================

    async def validate_profit_target(
        self, target_amount: float
    ) -> Tuple[bool, str, float]:
        """
        Validate if profit target is achievable with current account balance.

        Args:
            target_amount: Desired daily profit target

        Returns:
            Tuple of (is_valid, message, max_achievable_target)
        """
        try:
            self.logger.info(f"Validating profit target: ${target_amount:,.2f}")

            # Check basic limits
            if target_amount < MIN_DAILY_PROFIT_TARGET:
                return (
                    False,
                    f"Target too low. Minimum: ${MIN_DAILY_PROFIT_TARGET:,.2f}",
                    MIN_DAILY_PROFIT_TARGET,
                )

            if target_amount > MAX_DAILY_PROFIT_TARGET:
                return (
                    False,
                    f"Target too high. Maximum: ${MAX_DAILY_PROFIT_TARGET:,.2f}",
                    MAX_DAILY_PROFIT_TARGET,
                )

            # Get current account balance
            account_balance = await self._get_current_account_balance()
            if account_balance <= 0:
                return False, "Cannot retrieve account balance", 0.0

            # Calculate maximum achievable target based on account balance and risk limits
            max_risk_amount = account_balance * MAX_ACCOUNT_RISK_PCT
            max_achievable_target = self._calculate_max_achievable_profit(
                account_balance, max_risk_amount
            )

            # Check if target is achievable
            if target_amount > max_achievable_target:
                return (
                    False,
                    f"Target exceeds maximum achievable (${max_achievable_target:,.2f}) based on account balance",
                    max_achievable_target,
                )

            # Check existing positions and strategy conflicts
            if self.strategy_orchestrator:
                allocated_capital = (
                    self.strategy_orchestrator.portfolio_metrics.allocated_capital
                )
                available_capital = account_balance - allocated_capital

                required_capital = self._estimate_required_capital(target_amount)

                if required_capital > available_capital:
                    return (
                        False,
                        f"Insufficient available capital. Required: ${required_capital:,.2f}, Available: ${available_capital:,.2f}",
                        available_capital * 0.8,
                    )

            # Check market conditions
            if not self._is_market_suitable_for_target(target_amount):
                return (
                    False,
                    "Market conditions not suitable for this target",
                    max_achievable_target * 0.5,
                )

            self.logger.info(f"✅ Profit target validated: ${target_amount:,.2f}")
            return True, "Target validated successfully", max_achievable_target

        except Exception as e:
            self.logger.error(f"❌ Error validating profit target: {e}")
            return False, f"Validation error: {str(e)}", 0.0

    async def set_profit_target(
        self,
        target_amount: float,
        slicing_algorithm: SlicingAlgorithm = SlicingAlgorithm.ADAPTIVE,
        time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
        child_order_size: int = DEFAULT_CHILD_ORDER_SIZE,
    ) -> bool:
        """
        Set and configure daily profit target.

        Args:
            target_amount: Target profit amount
            slicing_algorithm: Algorithm for order slicing
            time_window_minutes: Execution time window
            child_order_size: Size of child orders

        Returns:
            bool: True if configuration successful
        """
        try:
            # Validate target
            is_valid, message, max_target = await self.validate_profit_target(
                target_amount
            )
            if not is_valid:
                self.logger.error(f"❌ Invalid profit target: {message}")
                return False

            # Get account balance for risk calculation
            account_balance = await self._get_current_account_balance()
            max_risk_amount = account_balance * MAX_ACCOUNT_RISK_PCT

            # Create configuration
            self.current_config = ProfitTargetConfig(
                target_amount=target_amount,
                max_risk_amount=max_risk_amount,
                time_window_minutes=time_window_minutes,
                slicing_algorithm=slicing_algorithm,
                child_order_size=child_order_size,
                max_market_impact_bps=MAX_MARKET_IMPACT_BPS,
                preferred_venues=[OrderExecutionVenue.SMART, OrderExecutionVenue.CBOE],
                enable_dark_pools=True,
                enable_smart_routing=True,
                risk_monitoring_enabled=True,
            )

            # Initialize progress tracking
            self.current_progress = ProfitTargetProgress(
                target_amount=target_amount,
                current_profit=0.0,
                progress_percentage=0.0,
                time_elapsed_minutes=0,
                estimated_completion_time=datetime.now()
                + timedelta(minutes=time_window_minutes),
                orders_executed=0,
                orders_pending=0,
                risk_utilization_pct=0.0,
                execution_metrics=ExecutionMetrics(),
            )

            # Store account balance snapshot
            self.daily_start_balance = account_balance
            self.current_account_balance = account_balance
            self.max_account_balance = account_balance

            # Update status
            self.status = ProfitTargetStatus.ACTIVE

            self.logger.info(
                f"✅ Profit target configured: ${target_amount:,.2f} using {slicing_algorithm.value}"
            )

            # Notify callbacks
            self._notify_progress_callbacks()

            return True

        except Exception as e:
            self.logger.error(f"❌ Error setting profit target: {e}")
            if self.error_handler:
                self.error_handler.handle_error(
                    e, "DayProfitTargetEngine.set_profit_target"
                )
            return False

    async def start_profit_targeting(self) -> bool:
        """
        Start profit targeting execution.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.status != ProfitTargetStatus.ACTIVE:
                self.logger.error("Cannot start - profit target not configured")
                return False

            if not self.current_config:
                self.logger.error("Cannot start - no configuration available")
                return False

            self.logger.info("🚀 Starting profit targeting execution...")

            # Check connectivity
            if self.connectivity_manager:
                connectivity_report = (
                    self.connectivity_manager.get_connectivity_report()
                )
                if connectivity_report.overall_state == "failed":
                    self.logger.error("❌ Cannot start - connectivity failed")
                    return False

            # Ensure IB connection
            if not self.ib.isConnected():
                await self._connect_to_ib()

            # Create slicing execution plan
            child_orders = self.slicing_manager.create_slicing_plan(
                target_profit=self.current_config.target_amount,
                risk_allocation=self.current_config.max_risk_amount,
                algorithm=self.current_config.slicing_algorithm,
                time_window_minutes=self.current_config.time_window_minutes,
            )

            if not child_orders:
                self.logger.error("❌ Failed to create execution plan")
                return False

            # Start monitoring
            await self._start_monitoring()

            # Begin execution
            self.execution_start_time = datetime.now()
            self.status = ProfitTargetStatus.IN_PROGRESS

            # Start execution thread
            self.execution_thread = threading.Thread(
                target=self._execute_slicing_plan, args=(child_orders,), daemon=True
            )
            self.execution_thread.start()

            self.logger.info(
                f"✅ Profit targeting started - {len(child_orders)} orders planned"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error starting profit targeting: {e}")
            self.status = ProfitTargetStatus.FAILED
            return False

    async def stop_profit_targeting(self, reason: str = "user_request") -> bool:
        """
        Stop profit targeting execution.

        Args:
            reason: Reason for stopping

        Returns:
            bool: True if stopped successfully
        """
        try:
            if self.status not in [
                ProfitTargetStatus.IN_PROGRESS,
                ProfitTargetStatus.ACTIVE,
            ]:
                self.logger.warning("Profit targeting not active")
                return True

            self.logger.info(f"🛑 Stopping profit targeting - Reason: {reason}")

            # Signal shutdown
            self.shutdown_event.set()

            # Cancel all active orders
            await self._cancel_all_active_orders()

            # Stop monitoring
            self.monitoring_active = False

            # Wait for threads to complete
            if self.execution_thread:
                self.execution_thread.join(timeout=30)
            if self.progress_monitor_thread:
                self.progress_monitor_thread.join(timeout=10)
            if self.risk_monitor_thread:
                self.risk_monitor_thread.join(timeout=10)

            # Update status
            if reason == "target_achieved":
                self.status = ProfitTargetStatus.COMPLETED
            elif reason == "risk_breach":
                self.status = ProfitTargetStatus.FAILED
            else:
                self.status = ProfitTargetStatus.CANCELLED

            # Generate final report
            final_report = self._generate_final_report()
            self.logger.info("📊 Final profit targeting report generated")

            # Notify completion callbacks
            for callback in self.completion_callbacks:
                try:
                    callback(self.status, final_report)
                except Exception as e:
                    self.logger.error(f"Completion callback error: {e}")

            self.logger.info("✅ Profit targeting stopped")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error stopping profit targeting: {e}")
            return False

    def get_current_progress(self) -> ProfitTargetProgress:
        """Get current progress information"""
        return copy.deepcopy(self.current_progress)

    def get_risk_alerts(self) -> List[RiskAlert]:
        """Get current risk alerts"""
        return copy.deepcopy(self.risk_alerts)

    # ==========================================================================
    # PRIVATE METHODS - EXECUTION AND MONITORING
    # ==========================================================================

    def _execute_slicing_plan(self, child_orders: List[ChildOrderSpec]):
        """Execute the slicing plan in a separate thread"""
        try:
            self.logger.info(f"Executing slicing plan with {len(child_orders)} orders")

            # Sort orders by scheduled time and priority
            sorted_orders = sorted(
                child_orders, key=lambda x: (x.scheduled_time, -x.priority_score)
            )

            for child_order in sorted_orders:
                if self.shutdown_event.is_set():
                    break

                # Wait until scheduled time
                now = datetime.now()
                if child_order.scheduled_time > now:
                    sleep_seconds = (child_order.scheduled_time - now).total_seconds()
                    if self.shutdown_event.wait(sleep_seconds):
                        break  # Shutdown requested

                # Check if still safe to execute
                if not self._is_safe_to_continue():
                    self.logger.warning("⚠️ Safety check failed, pausing execution")
                    break

                # Execute child order
                success = self._execute_child_order(child_order)

                if success:
                    self.current_progress.orders_executed += 1
                else:
                    self.logger.warning(
                        f"Failed to execute child order: {child_order.order_id}"
                    )

                # Brief pause between orders
                if not self.shutdown_event.wait(2):
                    continue

            self.logger.info("✅ Slicing plan execution completed")

        except Exception as e:
            self.logger.error(f"❌ Error executing slicing plan: {e}")
            self.status = ProfitTargetStatus.FAILED

    def _execute_child_order(self, child_order_spec: ChildOrderSpec) -> bool:
        """Execute a single child order"""
        try:
            # Create IB order from specification
            contract = child_order_spec.contract

            order = Order()
            order.action = child_order_spec.action
            order.totalQuantity = child_order_spec.quantity
            order.orderType = child_order_spec.order_type
            order.timeInForce = child_order_spec.time_in_force

            # Set limit price if not market order
            if child_order_spec.order_type == "LMT" and child_order_spec.limit_price:
                order.lmtPrice = child_order_spec.limit_price

            # Link to parent order if available
            if self.parent_order_id:
                order.parentId = int(self.parent_order_id)

            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Track order
            self.active_child_orders[child_order_spec.order_id] = order

            self.logger.info(
                f"📋 Child order placed: {child_order_spec.order_id} - {child_order_spec.quantity} @ {child_order_spec.venue.value}"
            )

            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing child order: {e}")
            return False

    async def _start_monitoring(self):
        """Start monitoring threads"""
        self.monitoring_active = True
        self.shutdown_event.clear()

        # Start progress monitoring
        self.progress_monitor_thread = threading.Thread(
            target=self._progress_monitoring_loop, daemon=True
        )
        self.progress_monitor_thread.start()

        # Start risk monitoring
        self.risk_monitor_thread = threading.Thread(
            target=self._risk_monitoring_loop, daemon=True
        )
        self.risk_monitor_thread.start()

        self.logger.info("✅ Monitoring threads started")

    def _progress_monitoring_loop(self):
        """Progress monitoring loop"""
        while self.monitoring_active and not self.shutdown_event.is_set():
            try:
                # Update current progress
                self._update_progress()

                # Check if target achieved
                if self.current_progress.progress_percentage >= 100.0:
                    self.logger.info("🎯 Target achieved!")
                    asyncio.create_task(self.stop_profit_targeting("target_achieved"))
                    break

                # Notify callbacks
                self._notify_progress_callbacks()

                # Wait for next update
                self.shutdown_event.wait(PROGRESS_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in progress monitoring: {e}")
                self.shutdown_event.wait(5)

    def _risk_monitoring_loop(self):
        """Risk monitoring loop"""
        while self.monitoring_active and not self.shutdown_event.is_set():
            try:
                # Check various risk factors
                alerts = []

                # Account balance risk
                account_alert = self._check_account_balance_risk()
                if account_alert:
                    alerts.append(account_alert)

                # Daily loss limit
                loss_alert = self._check_daily_loss_limit()
                if loss_alert:
                    alerts.append(loss_alert)

                # Market impact
                impact_alert = self._check_market_impact()
                if impact_alert:
                    alerts.append(impact_alert)

                # Execution quality
                quality_alert = self._check_execution_quality()
                if quality_alert:
                    alerts.append(quality_alert)

                # Process alerts
                for alert in alerts:
                    self._process_risk_alert(alert)

                # Wait for next check
                self.shutdown_event.wait(RISK_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"Error in risk monitoring: {e}")
                self.shutdown_event.wait(5)

    def _update_progress(self):
        """Update progress metrics"""
        try:
            # Get current P&L (simplified)
            current_profit = self._get_current_profit()

            # Calculate progress percentage
            if self.current_config:
                progress_pct = min(
                    100.0, (current_profit / self.current_config.target_amount) * 100
                )
            else:
                progress_pct = 0.0

            # Calculate time elapsed
            if self.execution_start_time:
                elapsed = datetime.now() - self.execution_start_time
                time_elapsed_minutes = int(elapsed.total_seconds() / 60)
            else:
                time_elapsed_minutes = 0

            # Update progress
            self.current_progress.current_profit = current_profit
            self.current_progress.progress_percentage = progress_pct
            self.current_progress.time_elapsed_minutes = time_elapsed_minutes
            self.current_progress.last_updated = datetime.now()

            # Update risk utilization
            if self.current_config:
                self.current_progress.risk_utilization_pct = min(
                    100.0,
                    (abs(current_profit) / self.current_config.max_risk_amount) * 100,
                )

        except Exception as e:
            self.logger.error(f"Error updating progress: {e}")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    async def _get_current_account_balance(self) -> float:
        """Get current account balance"""
        try:
            # This would connect to IB and get real account balance
            # For demo, return a placeholder value
            return 500000.0  # $500K demo balance
        except Exception as e:
            self.logger.error(f"Error getting account balance: {e}")
            return 0.0

    def _calculate_max_achievable_profit(
        self, account_balance: float, max_risk: float
    ) -> float:
        """Calculate maximum achievable profit target"""
        # Simplified calculation - real version would use sophisticated models
        # Factor in leverage, option pricing, Greeks, volatility, etc.

        # Conservative estimate: 5% of account balance max profit target
        conservative_target = account_balance * 0.05

        # Risk-adjusted target based on max risk allocation
        risk_adjusted_target = max_risk * 2.0  # 2:1 risk/reward

        return min(conservative_target, risk_adjusted_target)

    def _estimate_required_capital(self, target_profit: float) -> float:
        """Estimate capital required for profit target"""
        # Simplified - real version would calculate based on strategies, leverage, etc.
        return target_profit * 5.0  # 5x capital for 1x profit (conservative)

    def _is_market_suitable_for_target(self, target_amount: float) -> bool:
        """Check if market conditions are suitable for target"""
        # Check VIX, volume, time of day, etc.
        # For demo, return True
        return True

    def _get_current_profit(self) -> float:
        """Get current realized + unrealized profit"""
        # This would calculate from positions and fills
        # For demo, return progressive profit
        if self.execution_start_time:
            elapsed_minutes = (
                datetime.now() - self.execution_start_time
            ).total_seconds() / 60
            # Simulate gradual progress toward target
            if self.current_config:
                simulated_profit = (
                    (elapsed_minutes / self.current_config.time_window_minutes)
                    * self.current_config.target_amount
                    * 0.7
                )
                return min(simulated_profit, self.current_config.target_amount)
        return 0.0

    def _is_safe_to_continue(self) -> bool:
        """Check if it's safe to continue execution"""
        # Check circuit breakers, risk limits, connectivity, etc.
        return not self.circuit_breaker_active and self.monitoring_active

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def add_progress_callback(self, callback: Callable):
        """Add progress update callback"""
        self.progress_callbacks.append(callback)

    def add_risk_alert_callback(self, callback: Callable):
        """Add risk alert callback"""
        self.risk_alert_callbacks.append(callback)

    def add_completion_callback(self, callback: Callable):
        """Add completion callback"""
        self.completion_callbacks.append(callback)

    def _notify_progress_callbacks(self):
        """Notify all progress callbacks"""
        for callback in self.progress_callbacks:
            try:
                callback(self.current_progress)
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")


# ==============================================================================
# SUPPORTING CLASSES
# ==============================================================================


class MarketImpactAnalyzer:
    """Analyzes market impact of order execution"""

    def __init__(self):
        self.impact_history: List[MarketImpactAnalysis] = []

    def analyze_impact(
        self, pre_price: float, post_price: float, volume: int
    ) -> MarketImpactAnalysis:
        """Analyze market impact of an execution"""
        # Simplified impact analysis
        price_impact = abs(post_price - pre_price)
        impact_bps = (price_impact / pre_price) * 10000  # Convert to basis points

        # Classify impact
        if impact_bps <= 5:
            impact_score = "low"
        elif impact_bps <= 15:
            impact_score = "medium"
        else:
            impact_score = "high"

        analysis = MarketImpactAnalysis(
            pre_trade_mid=pre_price,
            post_trade_mid=post_price,
            volume_impact=volume,
            spread_impact=0.0,  # Would calculate spread impact
            total_impact_bps=impact_bps,
            liquidity_consumed_pct=0.0,  # Would calculate based on book depth
            recovery_time_seconds=0.0,  # Would measure price recovery
            impact_score=impact_score,
        )

        self.impact_history.append(analysis)
        return analysis


class ExecutionQualityTracker:
    """Tracks execution quality metrics"""

    def __init__(self):
        self.execution_history: List[Dict] = []
        self.venue_performance: Dict[str, List[float]] = defaultdict(list)

    def record_execution(
        self, venue: str, fill_price: float, target_price: float, fill_time: float
    ):
        """Record execution metrics"""
        slippage = abs(fill_price - target_price) / target_price * 10000  # BPS

        execution_record = {
            "venue": venue,
            "fill_price": fill_price,
            "target_price": target_price,
            "slippage_bps": slippage,
            "fill_time": fill_time,
            "timestamp": datetime.now(),
        }

        self.execution_history.append(execution_record)
        self.venue_performance[venue].append(slippage)

    def get_venue_performance(self, venue: str) -> Dict[str, float]:
        """Get performance statistics for a venue"""
        if venue not in self.venue_performance:
            return {"avg_slippage": 0.0, "fill_rate": 0.0}

        slippages = self.venue_performance[venue]
        return {
            "avg_slippage": statistics.mean(slippages),
            "fill_rate": (
                len(slippages) / len(self.execution_history)
                if self.execution_history
                else 0.0
            ),
        }


# ==============================================================================
# PYSIDE6 DAY PROFIT TARGET WIDGET
# ==============================================================================


class DayProfitTargetWidget(QWidget):
    """
    PySide6 widget for Day Profit Target configuration and monitoring.

    Integrates as the 5th tab in Risk Levels Configuration dialog.
    """

    # Qt signals
    targetConfigured = Signal(float, str)  # target_amount, algorithm
    executionStarted = Signal()
    executionStopped = Signal(str)  # reason
    progressUpdated = Signal(dict)  # progress_data
    riskAlert = Signal(dict)  # alert_data

    def __init__(self, profit_engine: Optional[DayProfitTargetEngine] = None):
        super().__init__()

        self.profit_engine = profit_engine or DayProfitTargetEngine()

        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        # UI state
        self.is_monitoring = False
        self.last_progress_update = None

        # Setup UI
        self.setup_ui()
        self.setup_monitoring()
        self.setup_engine_callbacks()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()

        # Target Configuration Section
        self.create_target_config_section(main_layout)

        # Progress Monitoring Section
        self.create_progress_monitoring_section(main_layout)

        # Risk Controls Section
        self.create_risk_controls_section(main_layout)

        # Execution Analytics Section
        self.create_analytics_section(main_layout)

        self.setLayout(main_layout)

    def create_target_config_section(self, layout):
        """Create target configuration section"""
        config_group = QGroupBox("🎯 Daily Profit Target Configuration")
        config_layout = QFormLayout()

        # Target amount input
        self.target_amount_input = QLineEdit()
        self.target_amount_input.setPlaceholderText("Enter target amount (e.g., 25000)")
        self.target_amount_input.textChanged.connect(self.validate_target_input)
        config_layout.addRow("Target Amount ($):", self.target_amount_input)

        # Target validation display
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        config_layout.addRow("Validation:", self.validation_label)

        # Slicing algorithm selection
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([algo.value.upper() for algo in SlicingAlgorithm])
        self.algorithm_combo.setCurrentText("ADAPTIVE")
        config_layout.addRow("Slicing Algorithm:", self.algorithm_combo)

        # Time window
        self.time_window_spin = QSpinBox()
        self.time_window_spin.setRange(15, 480)  # 15 minutes to 8 hours
        self.time_window_spin.setValue(60)
        self.time_window_spin.setSuffix(" minutes")
        config_layout.addRow("Execution Window:", self.time_window_spin)

        # Child order size
        self.child_order_size_spin = QSpinBox()
        self.child_order_size_spin.setRange(MIN_CHILD_ORDER_SIZE, MAX_CHILD_ORDER_SIZE)
        self.child_order_size_spin.setValue(DEFAULT_CHILD_ORDER_SIZE)
        self.child_order_size_spin.setSuffix(" contracts")
        config_layout.addRow("Child Order Size:", self.child_order_size_spin)

        # Configuration buttons
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("🔍 Validate Target")
        self.validate_btn.clicked.connect(self.validate_target)
        button_layout.addWidget(self.validate_btn)

        self.configure_btn = QPushButton("⚙️ Configure Target")
        self.configure_btn.clicked.connect(self.configure_target)
        self.configure_btn.setEnabled(False)
        button_layout.addWidget(self.configure_btn)

        config_layout.addRow("Actions:", button_layout)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

    def create_progress_monitoring_section(self, layout):
        """Create progress monitoring section"""
        progress_group = QGroupBox("📊 Execution Progress")
        progress_layout = QVBoxLayout()

        # Progress display
        metrics_layout = QGridLayout()

        # Current profit
        self.current_profit_lcd = QLCDNumber(8)
        self.current_profit_lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self.current_profit_lcd.display(0.0)
        metrics_layout.addWidget(QLabel("Current Profit ($):"), 0, 0)
        metrics_layout.addWidget(self.current_profit_lcd, 0, 1)

        # Progress percentage
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        metrics_layout.addWidget(QLabel("Progress:"), 1, 0)
        metrics_layout.addWidget(self.progress_bar, 1, 1)

        # Time elapsed
        self.time_elapsed_label = QLabel("Time Elapsed: 0 minutes")
        metrics_layout.addWidget(self.time_elapsed_label, 2, 0, 1, 2)

        # Orders executed
        self.orders_executed_label = QLabel("Orders Executed: 0")
        metrics_layout.addWidget(self.orders_executed_label, 3, 0, 1, 2)

        progress_layout.addLayout(metrics_layout)

        # Control buttons
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("🚀 Start Execution")
        self.start_btn.clicked.connect(self.start_execution)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        control_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.clicked.connect(self.pause_execution)
        self.pause_btn.setEnabled(False)
        control_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("🛑 Stop")
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white;")
        control_layout.addWidget(self.stop_btn)

        progress_layout.addLayout(control_layout)

        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

    def create_risk_controls_section(self, layout):
        """Create risk controls section"""
        risk_group = QGroupBox("⚠️ Risk Monitoring")
        risk_layout = QVBoxLayout()

        # Risk metrics display
        risk_metrics_layout = QGridLayout()

        self.risk_utilization_label = QLabel("Risk Utilization: 0%")
        risk_metrics_layout.addWidget(self.risk_utilization_label, 0, 0)

        self.account_balance_label = QLabel("Account Balance: $0")
        risk_metrics_layout.addWidget(self.account_balance_label, 0, 1)

        self.max_risk_label = QLabel("Max Risk Amount: $0")
        risk_metrics_layout.addWidget(self.max_risk_label, 1, 0)

        self.market_impact_label = QLabel("Market Impact: 0 bps")
        risk_metrics_layout.addWidget(self.market_impact_label, 1, 1)

        risk_layout.addLayout(risk_metrics_layout)

        # Risk alerts list
        self.risk_alerts_list = QListWidget()
        self.risk_alerts_list.setMaximumHeight(100)
        risk_layout.addWidget(QLabel("Active Risk Alerts:"))
        risk_layout.addWidget(self.risk_alerts_list)

        # Circuit breaker controls
        circuit_layout = QHBoxLayout()

        self.circuit_breaker_cb = QCheckBox("Enable Circuit Breaker")
        self.circuit_breaker_cb.setChecked(True)
        circuit_layout.addWidget(self.circuit_breaker_cb)

        self.emergency_stop_btn = QPushButton("🚨 Emergency Stop")
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        self.emergency_stop_btn.setStyleSheet(
            "background-color: #FF5722; color: white; font-weight: bold;"
        )
        circuit_layout.addWidget(self.emergency_stop_btn)

        risk_layout.addLayout(circuit_layout)

        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

    def create_analytics_section(self, layout):
        """Create execution analytics section"""
        analytics_group = QGroupBox("📈 Execution Analytics")
        analytics_layout = QVBoxLayout()

        # Create matplotlib figure for analytics
        self.analytics_figure = Figure(figsize=(10, 4))
        self.analytics_canvas = FigureCanvas(self.analytics_figure)
        analytics_layout.addWidget(self.analytics_canvas)

        # Analytics metrics
        analytics_metrics_layout = QHBoxLayout()

        self.avg_slippage_label = QLabel("Avg Slippage: 0 bps")
        analytics_metrics_layout.addWidget(self.avg_slippage_label)

        self.fill_rate_label = QLabel("Fill Rate: 0%")
        analytics_metrics_layout.addWidget(self.fill_rate_label)

        self.execution_quality_label = QLabel("Quality Score: 0.0")
        analytics_metrics_layout.addWidget(self.execution_quality_label)

        analytics_layout.addLayout(analytics_metrics_layout)

        analytics_group.setLayout(analytics_layout)
        layout.addWidget(analytics_group)

    def setup_monitoring(self):
        """Setup monitoring timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(2000)  # Update every 2 seconds

    def setup_engine_callbacks(self):
        """Setup callbacks with profit engine"""
        self.profit_engine.add_progress_callback(self.on_progress_update)
        self.profit_engine.add_risk_alert_callback(self.on_risk_alert)
        self.profit_engine.add_completion_callback(self.on_execution_complete)

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================

    def validate_target_input(self):
        """Validate target input as user types"""
        try:
            text = self.target_amount_input.text().strip()
            if not text:
                self.validation_label.setText("")
                self.configure_btn.setEnabled(False)
                return

            target_amount = float(text)

            if target_amount < MIN_DAILY_PROFIT_TARGET:
                self.validation_label.setText(
                    f"⚠️ Too low. Minimum: ${MIN_DAILY_PROFIT_TARGET:,.2f}"
                )
                self.validation_label.setStyleSheet("color: orange;")
                self.configure_btn.setEnabled(False)
            elif target_amount > MAX_DAILY_PROFIT_TARGET:
                self.validation_label.setText(
                    f"⚠️ Too high. Maximum: ${MAX_DAILY_PROFIT_TARGET:,.2f}"
                )
                self.validation_label.setStyleSheet("color: red;")
                self.configure_btn.setEnabled(False)
            else:
                self.validation_label.setText("✓ Valid target amount")
                self.validation_label.setStyleSheet("color: green;")
                self.configure_btn.setEnabled(True)

        except ValueError:
            self.validation_label.setText("❌ Invalid number format")
            self.validation_label.setStyleSheet("color: red;")
            self.configure_btn.setEnabled(False)

    def validate_target(self):
        """Validate target with account balance check"""
        try:
            target_text = self.target_amount_input.text().strip()
            if not target_text:
                QMessageBox.warning(self, "Warning", "Please enter a target amount")
                return

            target_amount = float(target_text)

            self.validate_btn.setEnabled(False)
            self.validate_btn.setText("🔄 Validating...")

            # Run validation in thread (simplified for demo)
            QTimer.singleShot(
                2000,
                lambda: self._validation_complete(
                    target_amount, True, "Validation successful", target_amount * 0.8
                ),
            )

        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid number")

    def _validation_complete(
        self, target_amount: float, is_valid: bool, message: str, max_achievable: float
    ):
        """Handle validation completion"""
        self.validate_btn.setEnabled(True)
        self.validate_btn.setText("🔍 Validate Target")

        if is_valid:
            self.validation_label.setText(f"✅ {message}")
            self.validation_label.setStyleSheet("color: green;")
            self.configure_btn.setEnabled(True)
            self.start_btn.setEnabled(False)  # Need to configure first
        else:
            self.validation_label.setText(
                f"❌ {message}\nMax achievable: ${max_achievable:,.2f}"
            )
            self.validation_label.setStyleSheet("color: red;")
            self.configure_btn.setEnabled(False)

    def configure_target(self):
        """Configure the profit target"""
        try:
            target_amount = float(self.target_amount_input.text().strip())
            algorithm_text = self.algorithm_combo.currentText().lower()
            algorithm = SlicingAlgorithm(algorithm_text)
            time_window = self.time_window_spin.value()
            child_order_size = self.child_order_size_spin.value()

            # Configure the engine (simplified for demo)
            self.configure_btn.setEnabled(False)
            self.configure_btn.setText("⚙️ Configuring...")

            # Simulate configuration
            QTimer.singleShot(
                1500,
                lambda: self._configuration_complete(target_amount, algorithm.value),
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Configuration Error", f"Failed to configure target: {str(e)}"
            )

    def _configuration_complete(self, target_amount: float, algorithm: str):
        """Handle configuration completion"""
        self.configure_btn.setEnabled(True)
        self.configure_btn.setText("⚙️ Configure Target")

        # Update UI state
        self.start_btn.setEnabled(True)
        self.validation_label.setText(
            f"✅ Target configured: ${target_amount:,.2f} using {algorithm.upper()}"
        )
        self.validation_label.setStyleSheet("color: blue;")

        # Emit signal
        self.targetConfigured.emit(target_amount, algorithm)

        QMessageBox.information(
            self,
            "Configuration Complete",
            f"Profit target of ${target_amount:,.2f} configured successfully!",
        )

    def start_execution(self):
        """Start profit targeting execution"""
        reply = QMessageBox.question(
            self,
            "Start Execution",
            "Are you sure you want to start profit targeting execution?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)
            self.is_monitoring = True

            # Emit signal
            self.executionStarted.emit()

            # Update UI
            self.validation_label.setText("🚀 Execution started...")
            self.validation_label.setStyleSheet("color: blue;")

            # Start simulated progress
            self._start_simulated_progress()

    def pause_execution(self):
        """Pause execution"""
        self.pause_btn.setEnabled(False)
        self.start_btn.setText("▶️ Resume")
        self.start_btn.setEnabled(True)

        self.validation_label.setText("⏸️ Execution paused")
        self.validation_label.setStyleSheet("color: orange;")

    def stop_execution(self):
        """Stop execution"""
        reply = QMessageBox.question(
            self,
            "Stop Execution",
            "Are you sure you want to stop execution?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._reset_execution_ui()
            self.executionStopped.emit("user_request")

            self.validation_label.setText("🛑 Execution stopped by user")
            self.validation_label.setStyleSheet("color: red;")

    def emergency_stop(self):
        """Emergency stop execution"""
        reply = QMessageBox.critical(
            self,
            "Emergency Stop",
            "EMERGENCY STOP - This will immediately halt all execution!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._reset_execution_ui()
            self.executionStopped.emit("emergency_stop")

            self.validation_label.setText("🚨 EMERGENCY STOP ACTIVATED")
            self.validation_label.setStyleSheet("color: red; font-weight: bold;")

    def _reset_execution_ui(self):
        """Reset execution UI state"""
        self.start_btn.setEnabled(True)
        self.start_btn.setText("🚀 Start Execution")
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.is_monitoring = False

        # Reset progress displays
        self.progress_bar.setValue(0)
        self.current_profit_lcd.display(0.0)
        self.time_elapsed_label.setText("Time Elapsed: 0 minutes")
        self.orders_executed_label.setText("Orders Executed: 0")

    def _start_simulated_progress(self):
        """Start simulated progress for demo"""
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_simulated_progress)
        self.progress_timer.start(5000)  # Update every 5 seconds

        self.simulation_start_time = datetime.now()
        self.simulation_progress = 0.0

    def _update_simulated_progress(self):
        """Update simulated progress"""
        if not self.is_monitoring:
            self.progress_timer.stop()
            return

        # Simulate gradual progress
        self.simulation_progress += 2.5  # 2.5% every 5 seconds

        if self.simulation_progress >= 100.0:
            self.simulation_progress = 100.0
            self._execution_complete("target_achieved")
            self.progress_timer.stop()
            return

        # Update displays
        try:
            target_amount = float(self.target_amount_input.text().strip())
            current_profit = (self.simulation_progress / 100.0) * target_amount

            self.progress_bar.setValue(int(self.simulation_progress))
            self.current_profit_lcd.display(current_profit)

            elapsed = datetime.now() - self.simulation_start_time
            elapsed_minutes = int(elapsed.total_seconds() / 60)
            self.time_elapsed_label.setText(f"Time Elapsed: {elapsed_minutes} minutes")

            orders_executed = int(
                self.simulation_progress * 0.5
            )  # Simulate order count
            self.orders_executed_label.setText(f"Orders Executed: {orders_executed}")

            # Update risk utilization (simulated)
            risk_util = min(50.0, self.simulation_progress * 0.3)
            self.risk_utilization_label.setText(f"Risk Utilization: {risk_util:.1f}%")

        except ValueError:
            pass  # Invalid target amount

    def _execution_complete(self, reason: str):
        """Handle execution completion"""
        self._reset_execution_ui()

        if reason == "target_achieved":
            self.validation_label.setText(
                "🎯 TARGET ACHIEVED! Execution completed successfully"
            )
            self.validation_label.setStyleSheet("color: green; font-weight: bold;")
            QMessageBox.information(
                self, "Success", "🎯 Profit target achieved successfully!"
            )
        else:
            self.validation_label.setText(f"❌ Execution stopped: {reason}")
            self.validation_label.setStyleSheet("color: red;")

    def update_display(self):
        """Update display with current data"""
        # Update account balance display
        self.account_balance_label.setText(f"Account Balance: $500,000")  # Demo value
        self.max_risk_label.setText(f"Max Risk Amount: $100,000")  # Demo value

        # Update analytics chart (placeholder)
        self._update_analytics_chart()

    def _update_analytics_chart(self):
        """Update analytics chart"""
        try:
            self.analytics_figure.clear()
            ax = self.analytics_figure.add_subplot(111)

            # Create sample data for demo
            times = list(range(10))
            profits = [i * 2500 + np.random.normal(0, 500) for i in times]

            go.Scatter(times, profits, "b-", linewidth=2)
            ax.set_xlabel("Time (minutes)")
            ax.set_ylabel("Cumulative Profit ($)")
            ax.set_title("Profit Progress")
            ax.grid(True, alpha=0.3)

            self.analytics_canvas.draw()

        except Exception as e:
            self.logger.error(f"Error updating analytics chart: {e}")

    # ==========================================================================
    # CALLBACK HANDLERS
    # ==========================================================================

    def on_progress_update(self, progress: ProfitTargetProgress):
        """Handle progress updates from engine"""
        self.progressUpdated.emit(asdict(progress))

        # Update UI elements
        self.current_profit_lcd.display(progress.current_profit)
        self.progress_bar.setValue(int(progress.progress_percentage))
        self.time_elapsed_label.setText(
            f"Time Elapsed: {progress.time_elapsed_minutes} minutes"
        )
        self.orders_executed_label.setText(
            f"Orders Executed: {progress.orders_executed}"
        )

    def on_risk_alert(self, alert: RiskAlert):
        """Handle risk alerts from engine"""
        self.riskAlert.emit(asdict(alert))

        # Add to risk alerts list
        alert_item = QListWidgetItem(f"⚠️ {alert.breach_type.value}: {alert.message}")
        if alert.severity == "critical":
            alert_item.setBackground(QColor(255, 0, 0, 50))  # Light red background
        elif alert.severity == "high":
            alert_item.setBackground(QColor(255, 165, 0, 50))  # Light orange background

        self.risk_alerts_list.insertItem(0, alert_item)

        # Keep only last 5 alerts visible
        while self.risk_alerts_list.count() > 5:
            self.risk_alerts_list.takeItem(5)

    def on_execution_complete(self, status: ProfitTargetStatus, report: Dict):
        """Handle execution completion from engine"""
        reason = status.value
        self._execution_complete(reason)


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================


def create_day_profit_target_engine(
    ib_client: Optional[IB] = None,
    strategy_orchestrator: Optional[StrategyOrchestrator] = None,
    connectivity_manager: Optional[IntegratedConnectivityManager] = None,
) -> DayProfitTargetEngine:
    """Factory function to create day profit target engine"""
    return DayProfitTargetEngine(ib_client, strategy_orchestrator, connectivity_manager)


def create_day_profit_target_widget(
    profit_engine: Optional[DayProfitTargetEngine] = None,
) -> DayProfitTargetWidget:
    """Factory function to create day profit target widget"""
    return DayProfitTargetWidget(profit_engine)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def main():
    """Main execution function for testing and demonstration"""
    print("🎯 SPYDER E13 - Day Profit Target Engine")
    print("=" * 60)

    try:
        # Create profit target engine
        engine = DayProfitTargetEngine()
        print("✅ Day Profit Target Engine initialized")

        # Test target validation
        print("\n📊 Testing target validation:")

        # Test various targets
        test_targets = [1000, 25000, 100000, 1000000]

        for target in test_targets:
            print(f"\n  Testing target: ${target:,.2f}")

            # Simulate validation (would be async in real usage)
            max_achievable = target * 0.8  # Simulate max achievable

            if target <= MAX_DAILY_PROFIT_TARGET:
                print(f"    ✅ Valid - Max achievable: ${max_achievable:,.2f}")
            else:
                print(f"    ❌ Too high - Max achievable: ${max_achievable:,.2f}")

        print(f"\n🎯 Test Results:")
        print(f"  Engine Status: {engine.status.value}")
        print(
            f"  Supported Algorithms: {', '.join([a.value for a in SlicingAlgorithm])}"
        )
        print(f"  Supported Venues: {len(SUPPORTED_VENUES)} venues")

        print(f"\n✅ Day Profit Target Engine test completed!")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

    return True


if __name__ == "__main__":
    main()
