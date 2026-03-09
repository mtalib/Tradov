#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderM05_TransactionCostAnalysis.py
Group: M (Monitoring)
Purpose: Comprehensive transaction cost analysis and execution quality monitoring
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 13:30:00

Description:
    This module provides detailed transaction cost analysis (TCA) to monitor and
    improve execution quality. It tracks all components of trading costs including
    spreads, commissions, market impact, and opportunity costs. The module generates
    real-time and historical TCA reports, identifies execution issues, and provides
    actionable insights to optimize trading performance and reduce costs.

Key Features:
    - Real-time transaction cost tracking
    - Multi-component cost decomposition
    - Execution quality benchmarking (VWAP, TWAP, arrival price)
    - Slippage analysis and pattern detection
    - Venue analysis and routing optimization
    - Best execution compliance reporting
    - Cost attribution by strategy and trader
    - Anomaly detection for unusual costs
    - Performance improvement recommendations
    - Integration with execution algorithms
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta, date
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import threading
import queue

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderH_Storage.SpyderH02_DatabaseManager import DatabaseManager
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Cost Components Weights
SPREAD_WEIGHT = 0.30
IMPACT_WEIGHT = 0.40
TIMING_WEIGHT = 0.20
OPPORTUNITY_WEIGHT = 0.10

# Benchmarks
VWAP_WINDOW_MINUTES = 30
TWAP_WINDOW_MINUTES = 30
ARRIVAL_PRICE_WINDOW_SECONDS = 5

# Quality Thresholds (in basis points)
EXCELLENT_THRESHOLD = 5  # < 5 bps from benchmark
GOOD_THRESHOLD = 10  # < 10 bps
ACCEPTABLE_THRESHOLD = 20  # < 20 bps
POOR_THRESHOLD = 50  # > 50 bps is poor

# Alerting Thresholds
HIGH_COST_ALERT_BPS = 50
SLIPPAGE_ALERT_BPS = 25
UNUSUAL_PATTERN_THRESHOLD = 3  # Standard deviations

# Reporting Intervals
INTRADAY_REPORT_INTERVAL = 3600  # 1 hour
DAILY_REPORT_TIME = "16:30"  # After market close

# ==============================================================================
# ENUMS
# ==============================================================================

class CostComponent(Enum):
    """Transaction cost components"""
    SPREAD = "SPREAD"
    IMPACT = "IMPACT"
    COMMISSION = "COMMISSION"
    TIMING = "TIMING"
    OPPORTUNITY = "OPPORTUNITY"
    SLIPPAGE = "SLIPPAGE"
    FEES = "FEES"
    REBATES = "REBATES"

class Benchmark(Enum):
    """Execution benchmarks"""
    ARRIVAL = "ARRIVAL_PRICE"
    VWAP = "VWAP"
    TWAP = "TWAP"
    CLOSE = "CLOSE"
    OPEN = "OPEN"
    MIDPOINT = "MIDPOINT"
    CUSTOM = "CUSTOM"

class ExecutionVenue(Enum):
    """Execution venues"""
    SMART = "SMART"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"
    ARCA = "ARCA"
    BATS = "BATS"
    IEX = "IEX"
    DARK = "DARK_POOL"
    DIRECT = "DIRECT"

class QualityRating(Enum):
    """Execution quality rating"""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    ACCEPTABLE = "ACCEPTABLE"
    POOR = "POOR"
    UNACCEPTABLE = "UNACCEPTABLE"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ExecutionRecord:
    """Single execution record"""
    execution_id: str
    order_id: str
    symbol: str
    side: str  # BUY/SELL
    quantity: int
    execution_price: float
    execution_time: datetime
    venue: ExecutionVenue
    liquidity_flag: str  # ADD/REMOVE/NEUTRAL
    commission: float
    fees: float
    rebates: float

@dataclass
class OrderContext:
    """Order context for TCA"""
    order_id: str
    symbol: str
    side: str
    total_quantity: int
    order_type: str
    limit_price: float | None
    arrival_time: datetime
    arrival_price: float
    decision_price: float
    strategy: str
    urgency: str
    trader_id: str | None = None
    algo_id: str | None = None

@dataclass
class MarketContext:
    """Market context at execution"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    mid: float
    spread: float
    vwap: float
    twap: float
    volume: int
    volatility: float
    liquidity_score: float

@dataclass
class CostBreakdown:
    """Detailed cost breakdown"""
    order_id: str
    symbol: str
    total_cost_bps: float
    total_cost_dollars: float
    spread_cost: float
    impact_cost: float
    timing_cost: float
    opportunity_cost: float
    commission_cost: float
    fee_cost: float
    rebate_credit: float
    slippage: float

@dataclass
class TCAReport:
    """Transaction Cost Analysis report"""
    report_id: str
    period_start: datetime
    period_end: datetime
    total_orders: int
    total_executions: int
    total_volume: int
    total_value: float
    avg_cost_bps: float
    total_cost_dollars: float
    cost_by_component: dict[str, float]
    cost_by_symbol: dict[str, float]
    cost_by_strategy: dict[str, float]
    cost_by_venue: dict[str, float]
    quality_distribution: dict[str, int]
    outliers: list[str]  # Order IDs with unusual costs
    recommendations: list[str]

@dataclass
class BenchmarkComparison:
    """Benchmark comparison results"""
    order_id: str
    symbol: str
    execution_price: float
    arrival_price: float
    vwap: float
    twap: float
    arrival_shortfall_bps: float
    vwap_shortfall_bps: float
    twap_shortfall_bps: float
    best_benchmark: str
    quality_rating: QualityRating

@dataclass
class VenueStatistics:
    """Venue execution statistics"""
    venue: ExecutionVenue
    total_executions: int
    total_volume: int
    avg_spread_capture: float
    avg_price_improvement: float
    fill_rate: float
    avg_latency_ms: float
    rebate_rate: float
    cost_per_share: float

# ==============================================================================
# TRANSACTION COST ANALYZER
# ==============================================================================

class TransactionCostAnalyzer:
    """
    Comprehensive transaction cost analysis system
    Monitors, analyzes, and reports on all trading costs
    """

    def __init__(self, database_manager: Optional['DatabaseManager'] = None):
        """Initialize TCA system"""
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)

        # Database
        self.db_manager = database_manager

        # Storage
        self.executions: dict[str, list[ExecutionRecord]] = defaultdict(list)
        self.order_contexts: dict[str, OrderContext] = {}
        self.market_contexts: deque = deque(maxlen=10000)
        self.cost_breakdowns: dict[str, CostBreakdown] = {}

        # Benchmarks cache
        self.vwap_cache: dict[str, pd.DataFrame] = {}
        self.twap_cache: dict[str, pd.DataFrame] = {}

        # Statistics
        self.daily_stats: dict[date, dict] = defaultdict(dict)
        self.venue_stats: dict[ExecutionVenue, VenueStatistics] = {}

        # Real-time monitoring
        self.alert_queue = queue.Queue()
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()

        # Configuration
        self.alert_thresholds = {
            'high_cost': HIGH_COST_ALERT_BPS,
            'slippage': SLIPPAGE_ALERT_BPS,
            'unusual_pattern': UNUSUAL_PATTERN_THRESHOLD
        }

        # Start monitoring
        self._start_monitoring()

        self.logger.info("✅ TransactionCostAnalyzer initialized")

    # ==========================================================================
    # EXECUTION PROCESSING
    # ==========================================================================

    def process_execution(self,
                         execution: ExecutionRecord,
                         order_context: OrderContext,
                         market_context: MarketContext):
        """
        Process new execution for TCA

        Args:
            execution: Execution details
            order_context: Order context
            market_context: Market conditions at execution
        """
        # Store execution
        self.executions[execution.order_id].append(execution)

        # Store contexts if new
        if execution.order_id not in self.order_contexts:
            self.order_contexts[execution.order_id] = order_context

        self.market_contexts.append(market_context)

        # Calculate immediate costs
        immediate_costs = self._calculate_immediate_costs(
            execution, order_context, market_context
        )

        # Check for alerts
        self._check_cost_alerts(execution, immediate_costs)

        # Update running statistics
        self._update_statistics(execution, immediate_costs)

        self.logger.debug(f"Processed execution {execution.execution_id}: "
                         f"{immediate_costs['total_bps']:.1f} bps cost")

    def _calculate_immediate_costs(self,
                                  execution: ExecutionRecord,
                                  order_context: OrderContext,
                                  market_context: MarketContext) -> dict[str, float]:
        """Calculate immediate execution costs"""
        costs = {}

        # Spread cost (half-spread if crossing)
        if execution.liquidity_flag == "REMOVE":
            spread_cost = market_context.spread / 2
        else:
            spread_cost = 0

        costs['spread_bps'] = (spread_cost / market_context.mid) * 10000

        # Slippage from arrival price
        if order_context.side == "BUY":
            slippage = execution.execution_price - order_context.arrival_price
        else:
            slippage = order_context.arrival_price - execution.execution_price

        costs['slippage_bps'] = (slippage / order_context.arrival_price) * 10000

        # Commission and fees
        trade_value = execution.quantity * execution.execution_price
        costs['commission_bps'] = (execution.commission / trade_value) * 10000
        costs['fee_bps'] = (execution.fees / trade_value) * 10000
        costs['rebate_bps'] = (execution.rebates / trade_value) * 10000

        # Total immediate cost
        costs['total_bps'] = (
            costs['spread_bps'] +
            costs['slippage_bps'] +
            costs['commission_bps'] +
            costs['fee_bps'] -
            costs['rebate_bps']
        )

        return costs

    # ==========================================================================
    # COMPREHENSIVE TCA
    # ==========================================================================

    def calculate_tca(self, order_id: str) -> CostBreakdown:
        """
        Calculate comprehensive TCA for completed order

        Args:
            order_id: Order identifier

        Returns:
            Detailed cost breakdown
        """
        if order_id not in self.order_contexts:
            self.logger.warning(f"No context for order {order_id}")
            return None

        order_context = self.order_contexts[order_id]
        executions = self.executions[order_id]

        if not executions:
            self.logger.warning(f"No executions for order {order_id}")
            return None

        # Calculate weighted average execution price
        total_value = sum(e.quantity * e.execution_price for e in executions)
        total_quantity = sum(e.quantity for e in executions)
        avg_price = total_value / total_quantity if total_quantity > 0 else 0

        # Get benchmarks
        benchmarks = self._calculate_benchmarks(order_id, executions)

        # Calculate cost components
        spread_cost = self._calculate_spread_cost(executions, order_context)
        impact_cost = self._calculate_impact_cost(executions, order_context, benchmarks)
        timing_cost = self._calculate_timing_cost(executions, order_context, benchmarks)
        opportunity_cost = self._calculate_opportunity_cost(order_context, executions)

        # Direct costs
        commission_cost = sum(e.commission for e in executions)
        fee_cost = sum(e.fees for e in executions)
        rebate_credit = sum(e.rebates for e in executions)

        # Slippage
        if order_context.side == "BUY":
            slippage = avg_price - order_context.arrival_price
        else:
            slippage = order_context.arrival_price - avg_price

        slippage_bps = (slippage / order_context.arrival_price) * 10000

        # Total costs
        total_cost_dollars = (
            spread_cost + impact_cost + timing_cost + opportunity_cost +
            commission_cost + fee_cost - rebate_credit
        )

        total_cost_bps = (total_cost_dollars / total_value) * 10000 if total_value > 0 else 0

        # Create breakdown
        breakdown = CostBreakdown(
            order_id=order_id,
            symbol=order_context.symbol,
            total_cost_bps=total_cost_bps,
            total_cost_dollars=total_cost_dollars,
            spread_cost=spread_cost,
            impact_cost=impact_cost,
            timing_cost=timing_cost,
            opportunity_cost=opportunity_cost,
            commission_cost=commission_cost,
            fee_cost=fee_cost,
            rebate_credit=rebate_credit,
            slippage=slippage_bps
        )

        # Cache breakdown
        self.cost_breakdowns[order_id] = breakdown

        return breakdown

    def _calculate_spread_cost(self,
                              executions: list[ExecutionRecord],
                              order_context: OrderContext) -> float:
        """Calculate spread crossing costs"""
        total_spread_cost = 0

        for execution in executions:
            # Get market context at execution time
            market = self._get_market_context(
                execution.symbol,
                execution.execution_time
            )

            if market and execution.liquidity_flag == "REMOVE":
                # Crossed spread
                spread_cost = (market.spread / 2) * execution.quantity
                total_spread_cost += spread_cost

        return total_spread_cost

    def _calculate_impact_cost(self,
                              executions: list[ExecutionRecord],
                              order_context: OrderContext,
                              benchmarks: dict[str, float]) -> float:
        """Calculate market impact cost"""
        if 'vwap' not in benchmarks:
            return 0

        total_impact = 0
        cumulative_qty = 0

        for execution in executions:
            cumulative_qty += execution.quantity

            # Estimate impact based on participation
            participation = cumulative_qty / order_context.total_quantity

            # Simple square-root model
            impact_pct = 0.001 * np.sqrt(participation)
            impact_cost = impact_pct * execution.execution_price * execution.quantity

            total_impact += impact_cost

        return total_impact

    def _calculate_timing_cost(self,
                              executions: list[ExecutionRecord],
                              order_context: OrderContext,
                              benchmarks: dict[str, float]) -> float:
        """Calculate timing cost (delay cost)"""
        if not executions:
            return 0

        # Time from arrival to first execution
        first_exec_time = min(e.execution_time for e in executions)
        delay_seconds = (first_exec_time - order_context.arrival_time).total_seconds()

        # Estimate drift cost (simplified)
        drift_per_second = 0.00001  # 0.001% per second
        timing_cost_pct = drift_per_second * delay_seconds

        total_value = sum(e.quantity * e.execution_price for e in executions)
        timing_cost = timing_cost_pct * total_value

        return timing_cost

    def _calculate_opportunity_cost(self,
                                   order_context: OrderContext,
                                   executions: list[ExecutionRecord]) -> float:
        """Calculate opportunity cost of unfilled portion"""
        filled_quantity = sum(e.quantity for e in executions)
        unfilled_quantity = order_context.total_quantity - filled_quantity

        if unfilled_quantity <= 0:
            return 0

        # Estimate opportunity cost (simplified)
        # Assume unfilled portion would have captured some alpha
        expected_alpha = 0.0005  # 5 bps expected alpha
        opportunity_cost = unfilled_quantity * order_context.arrival_price * expected_alpha

        return opportunity_cost

    # ==========================================================================
    # BENCHMARKING
    # ==========================================================================

    def _calculate_benchmarks(self,
                            order_id: str,
                            executions: list[ExecutionRecord]) -> dict[str, float]:
        """Calculate execution benchmarks"""
        if not executions:
            return {}

        order_context = self.order_contexts[order_id]
        symbol = order_context.symbol

        benchmarks = {}

        # Arrival price
        benchmarks['arrival'] = order_context.arrival_price

        # VWAP
        vwap = self._calculate_vwap(
            symbol,
            min(e.execution_time for e in executions),
            max(e.execution_time for e in executions)
        )
        if vwap:
            benchmarks['vwap'] = vwap

        # TWAP
        twap = self._calculate_twap(
            symbol,
            min(e.execution_time for e in executions),
            max(e.execution_time for e in executions)
        )
        if twap:
            benchmarks['twap'] = twap

        return benchmarks

    def _calculate_vwap(self,
                       symbol: str,
                       start_time: datetime,
                       end_time: datetime) -> float | None:
        """Calculate VWAP for period"""
        # Check cache
        cache_key = f"{symbol}_{start_time}_{end_time}"
        if cache_key in self.vwap_cache:
            return self.vwap_cache[cache_key]['vwap'].iloc[-1]

        # Get market data for period
        market_data = self._get_market_data_range(symbol, start_time, end_time)

        if market_data.empty:
            return None

        # Calculate VWAP
        market_data['value'] = market_data['price'] * market_data['volume']
        cumulative_value = market_data['value'].cumsum()
        cumulative_volume = market_data['volume'].cumsum()

        vwap = cumulative_value / cumulative_volume

        # Cache result
        self.vwap_cache[cache_key] = pd.DataFrame({'vwap': vwap})

        return vwap.iloc[-1] if not vwap.empty else None

    def _calculate_twap(self,
                       symbol: str,
                       start_time: datetime,
                       end_time: datetime) -> float | None:
        """Calculate TWAP for period"""
        # Check cache
        cache_key = f"{symbol}_{start_time}_{end_time}"
        if cache_key in self.twap_cache:
            return self.twap_cache[cache_key]['twap'].iloc[-1]

        # Get market data for period
        market_data = self._get_market_data_range(symbol, start_time, end_time)

        if market_data.empty:
            return None

        # Calculate TWAP
        twap = market_data['price'].mean()

        # Cache result
        self.twap_cache[cache_key] = pd.DataFrame({'twap': [twap]})

        return twap

    def compare_to_benchmarks(self, order_id: str) -> BenchmarkComparison:
        """
        Compare execution to various benchmarks

        Args:
            order_id: Order identifier

        Returns:
            Benchmark comparison results
        """
        if order_id not in self.order_contexts:
            return None

        order_context = self.order_contexts[order_id]
        executions = self.executions[order_id]

        if not executions:
            return None

        # Calculate average execution price
        total_value = sum(e.quantity * e.execution_price for e in executions)
        total_quantity = sum(e.quantity for e in executions)
        avg_price = total_value / total_quantity

        # Get benchmarks
        benchmarks = self._calculate_benchmarks(order_id, executions)

        # Calculate shortfalls
        arrival_shortfall = self._calculate_shortfall(
            avg_price,
            benchmarks.get('arrival', avg_price),
            order_context.side
        )

        vwap_shortfall = self._calculate_shortfall(
            avg_price,
            benchmarks.get('vwap', avg_price),
            order_context.side
        )

        twap_shortfall = self._calculate_shortfall(
            avg_price,
            benchmarks.get('twap', avg_price),
            order_context.side
        )

        # Determine best benchmark
        shortfalls = {
            'arrival': abs(arrival_shortfall),
            'vwap': abs(vwap_shortfall),
            'twap': abs(twap_shortfall)
        }
        best_benchmark = min(shortfalls, key=shortfalls.get)

        # Rate quality
        min_shortfall = shortfalls[best_benchmark]
        quality_rating = self._rate_execution_quality(min_shortfall)

        return BenchmarkComparison(
            order_id=order_id,
            symbol=order_context.symbol,
            execution_price=avg_price,
            arrival_price=benchmarks.get('arrival', 0),
            vwap=benchmarks.get('vwap', 0),
            twap=benchmarks.get('twap', 0),
            arrival_shortfall_bps=arrival_shortfall,
            vwap_shortfall_bps=vwap_shortfall,
            twap_shortfall_bps=twap_shortfall,
            best_benchmark=best_benchmark,
            quality_rating=quality_rating
        )

    def _calculate_shortfall(self,
                           exec_price: float,
                           benchmark_price: float,
                           side: str) -> float:
        """Calculate implementation shortfall in bps"""
        if benchmark_price == 0:
            return 0

        if side == "BUY":
            shortfall = (exec_price - benchmark_price) / benchmark_price
        else:
            shortfall = (benchmark_price - exec_price) / benchmark_price

        return shortfall * 10000  # Convert to bps

    def _rate_execution_quality(self, shortfall_bps: float) -> QualityRating:
        """Rate execution quality based on shortfall"""
        shortfall_abs = abs(shortfall_bps)

        if shortfall_abs < EXCELLENT_THRESHOLD:
            return QualityRating.EXCELLENT
        elif shortfall_abs < GOOD_THRESHOLD:
            return QualityRating.GOOD
        elif shortfall_abs < ACCEPTABLE_THRESHOLD:
            return QualityRating.ACCEPTABLE
        elif shortfall_abs < POOR_THRESHOLD:
            return QualityRating.POOR
        else:
            return QualityRating.UNACCEPTABLE

    # ==========================================================================
    # VENUE ANALYSIS
    # ==========================================================================

    def analyze_venue_performance(self,
                                 start_date: datetime,
                                 end_date: datetime) -> dict[ExecutionVenue, VenueStatistics]:
        """
        Analyze execution quality by venue

        Args:
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Venue performance statistics
        """
        venue_data = defaultdict(lambda: {
            'executions': [],
            'spread_captures': [],
            'price_improvements': [],
            'latencies': [],
            'fills': 0,
            'attempts': 0
        })

        # Aggregate data by venue
        for _order_id, execs in self.executions.items():
            for execution in execs:
                if start_date <= execution.execution_time <= end_date:
                    venue = execution.venue
                    venue_data[venue]['executions'].append(execution)

                    # Calculate metrics
                    market = self._get_market_context(
                        execution.symbol,
                        execution.execution_time
                    )

                    if market:
                        # Spread capture
                        if execution.liquidity_flag == "ADD":
                            spread_capture = market.spread / 2
                            venue_data[venue]['spread_captures'].append(spread_capture)

                        # Price improvement
                        if execution.side == "BUY":
                            improvement = market.ask - execution.execution_price
                        else:
                            improvement = execution.execution_price - market.bid

                        if improvement > 0:
                            venue_data[venue]['price_improvements'].append(improvement)

        # Calculate statistics
        venue_stats = {}

        for venue, data in venue_data.items():
            if not data['executions']:
                continue

            total_volume = sum(e.quantity for e in data['executions'])
            total_value = sum(e.quantity * e.execution_price for e in data['executions'])

            stats = VenueStatistics(
                venue=venue,
                total_executions=len(data['executions']),
                total_volume=total_volume,
                avg_spread_capture=np.mean(data['spread_captures']) if data['spread_captures'] else 0,
                avg_price_improvement=np.mean(data['price_improvements']) if data['price_improvements'] else 0,
                fill_rate=data['fills'] / data['attempts'] if data['attempts'] > 0 else 0,
                avg_latency_ms=np.mean(data['latencies']) if data['latencies'] else 0,
                rebate_rate=sum(e.rebates for e in data['executions']) / total_value if total_value > 0 else 0,
                cost_per_share=sum(e.commission + e.fees for e in data['executions']) / total_volume if total_volume > 0 else 0
            )

            venue_stats[venue] = stats

        self.venue_stats = venue_stats
        return venue_stats

    # ==========================================================================
    # REPORTING
    # ==========================================================================

    def generate_tca_report(self,
                           start_time: datetime,
                           end_time: datetime,
                           group_by: str | None = None) -> TCAReport:
        """
        Generate comprehensive TCA report

        Args:
            start_time: Report start time
            end_time: Report end time
            group_by: Optional grouping (symbol, strategy, venue)

        Returns:
            TCA report
        """
        report_id = f"TCA_{start_time.strftime('%Y%m%d_%H%M%S')}"

        # Filter relevant orders
        relevant_orders = []
        for order_id, context in self.order_contexts.items():
            if start_time <= context.arrival_time <= end_time:
                relevant_orders.append(order_id)

        if not relevant_orders:
            self.logger.warning(f"No orders found for period {start_time} to {end_time}")
            return None

        # Calculate TCA for each order
        cost_breakdowns = []
        for order_id in relevant_orders:
            breakdown = self.calculate_tca(order_id)
            if breakdown:
                cost_breakdowns.append(breakdown)

        if not cost_breakdowns:
            return None

        # Aggregate statistics
        total_orders = len(relevant_orders)
        total_executions = sum(len(self.executions[oid]) for oid in relevant_orders)
        total_volume = sum(
            sum(e.quantity for e in self.executions[oid])
            for oid in relevant_orders
        )
        total_value = sum(
            sum(e.quantity * e.execution_price for e in self.executions[oid])
            for oid in relevant_orders
        )

        # Cost aggregation
        total_cost_dollars = sum(b.total_cost_dollars for b in cost_breakdowns)
        avg_cost_bps = (total_cost_dollars / total_value * 10000) if total_value > 0 else 0

        # Component breakdown
        cost_by_component = {
            CostComponent.SPREAD.value: sum(b.spread_cost for b in cost_breakdowns),
            CostComponent.IMPACT.value: sum(b.impact_cost for b in cost_breakdowns),
            CostComponent.TIMING.value: sum(b.timing_cost for b in cost_breakdowns),
            CostComponent.OPPORTUNITY.value: sum(b.opportunity_cost for b in cost_breakdowns),
            CostComponent.COMMISSION.value: sum(b.commission_cost for b in cost_breakdowns),
            CostComponent.FEES.value: sum(b.fee_cost for b in cost_breakdowns),
            CostComponent.REBATES.value: sum(b.rebate_credit for b in cost_breakdowns)
        }

        # Group analysis
        cost_by_symbol = defaultdict(float)
        cost_by_strategy = defaultdict(float)
        cost_by_venue = defaultdict(float)

        for order_id in relevant_orders:
            context = self.order_contexts[order_id]
            breakdown = self.cost_breakdowns.get(order_id)

            if breakdown:
                cost_by_symbol[context.symbol] += breakdown.total_cost_dollars
                cost_by_strategy[context.strategy] += breakdown.total_cost_dollars

                for execution in self.executions[order_id]:
                    venue_cost = (execution.commission + execution.fees - execution.rebates)
                    cost_by_venue[execution.venue.value] += venue_cost

        # Quality distribution
        quality_distribution = defaultdict(int)
        for order_id in relevant_orders:
            comparison = self.compare_to_benchmarks(order_id)
            if comparison:
                quality_distribution[comparison.quality_rating.value] += 1

        # Identify outliers
        outliers = self._identify_cost_outliers(cost_breakdowns)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            cost_breakdowns,
            quality_distribution,
            cost_by_venue
        )

        # Create report
        report = TCAReport(
            report_id=report_id,
            period_start=start_time,
            period_end=end_time,
            total_orders=total_orders,
            total_executions=total_executions,
            total_volume=total_volume,
            total_value=total_value,
            avg_cost_bps=avg_cost_bps,
            total_cost_dollars=total_cost_dollars,
            cost_by_component=cost_by_component,
            cost_by_symbol=dict(cost_by_symbol),
            cost_by_strategy=dict(cost_by_strategy),
            cost_by_venue=dict(cost_by_venue),
            quality_distribution=dict(quality_distribution),
            outliers=outliers,
            recommendations=recommendations
        )

        # Store report
        if self.db_manager:
            self._store_report(report)

        return report

    def _identify_cost_outliers(self,
                               cost_breakdowns: list[CostBreakdown],
                               threshold_std: float = 3) -> list[str]:
        """Identify orders with unusual costs"""
        if not cost_breakdowns:
            return []

        costs_bps = [b.total_cost_bps for b in cost_breakdowns]
        mean_cost = np.mean(costs_bps)
        std_cost = np.std(costs_bps)

        outliers = []
        for breakdown in cost_breakdowns:
            z_score = abs((breakdown.total_cost_bps - mean_cost) / std_cost) if std_cost > 0 else 0

            if z_score > threshold_std:
                outliers.append(breakdown.order_id)

        return outliers

    def _generate_recommendations(self,
                                 cost_breakdowns: list[CostBreakdown],
                                 quality_distribution: dict[str, int],
                                 cost_by_venue: dict[str, float]) -> list[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Check overall quality
        total_orders = sum(quality_distribution.values())
        if total_orders > 0:
            poor_pct = (quality_distribution.get(QualityRating.POOR.value, 0) +
                       quality_distribution.get(QualityRating.UNACCEPTABLE.value, 0)) / total_orders

            if poor_pct > 0.2:  # More than 20% poor executions
                recommendations.append(
                    "High percentage of poor executions - review execution algorithms"
                )

        # Check cost components
        if cost_breakdowns:
            avg_impact = np.mean([b.impact_cost for b in cost_breakdowns])
            avg_spread = np.mean([b.spread_cost for b in cost_breakdowns])

            if avg_impact > avg_spread * 2:
                recommendations.append(
                    "High market impact costs - consider more passive execution"
                )

        # Check venue costs
        if cost_by_venue:
            best_venue = min(cost_by_venue, key=cost_by_venue.get)
            worst_venue = max(cost_by_venue, key=cost_by_venue.get)

            if cost_by_venue[worst_venue] > cost_by_venue[best_venue] * 2:
                recommendations.append(
                    f"Consider routing more flow to {best_venue} instead of {worst_venue}"
                )

        # Check for patterns
        if len(cost_breakdowns) > 10:
            recent_costs = [b.total_cost_bps for b in cost_breakdowns[-10:]]
            older_costs = [b.total_cost_bps for b in cost_breakdowns[:-10]]

            if np.mean(recent_costs) > np.mean(older_costs) * 1.5:
                recommendations.append(
                    "Recent execution costs trending higher - investigate market conditions"
                )

        return recommendations

    # ==========================================================================
    # MONITORING AND ALERTS
    # ==========================================================================

    def _start_monitoring(self):
        """Start real-time monitoring thread"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True
            )
            self.monitor_thread.start()

    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("TCA monitoring started")

        while not self.stop_monitoring.is_set():
            try:
                # Check for alerts
                self._process_alerts()

                # Generate periodic reports
                current_time = datetime.now()
                if current_time.minute == 0:  # Top of hour
                    self._generate_intraday_report()

                # Sleep
                self.stop_monitoring.wait(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")

        self.logger.info("TCA monitoring stopped")

    def _check_cost_alerts(self,
                          execution: ExecutionRecord,
                          costs: dict[str, float]):
        """Check for cost-related alerts"""
        # High cost alert
        if costs['total_bps'] > self.alert_thresholds['high_cost']:
            alert = {
                'type': 'HIGH_COST',
                'execution_id': execution.execution_id,
                'symbol': execution.symbol,
                'cost_bps': costs['total_bps'],
                'timestamp': datetime.now()
            }
            self.alert_queue.put(alert)
            self.logger.warning(f"⚠️ High cost alert: {costs['total_bps']:.1f} bps for {execution.symbol}")

        # Slippage alert
        if costs['slippage_bps'] > self.alert_thresholds['slippage']:
            alert = {
                'type': 'HIGH_SLIPPAGE',
                'execution_id': execution.execution_id,
                'symbol': execution.symbol,
                'slippage_bps': costs['slippage_bps'],
                'timestamp': datetime.now()
            }
            self.alert_queue.put(alert)

    def _process_alerts(self):
        """Process queued alerts"""
        alerts_processed = 0
        max_alerts = 10

        while not self.alert_queue.empty() and alerts_processed < max_alerts:
            try:
                alert = self.alert_queue.get_nowait()

                # Log alert
                self.logger.warning(f"Alert: {alert['type']} - {alert}")

                # Could send to monitoring system, email, etc.

                alerts_processed += 1

            except queue.Empty:
                break

    def _generate_intraday_report(self):
        """Generate intraday TCA report"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)

        report = self.generate_tca_report(start_time, end_time)

        if report:
            self.logger.info(f"Intraday TCA: {report.total_orders} orders, "
                           f"avg cost {report.avg_cost_bps:.1f} bps")

    # ==========================================================================
    # DATA ACCESS HELPERS
    # ==========================================================================

    def _get_market_context(self,
                          symbol: str,
                          timestamp: datetime) -> MarketContext | None:
        """Get market context at specific time"""
        # Find closest market context
        for context in reversed(self.market_contexts):
            if context.symbol == symbol and abs((context.timestamp - timestamp).total_seconds()) < 5:
                return context
        return None

    def _get_market_data_range(self,
                              symbol: str,
                              start_time: datetime,
                              end_time: datetime) -> pd.DataFrame:
        """Get market data for time range"""
        # This would fetch from database or market data provider
        # For now, return simulated data
        time_range = pd.date_range(start=start_time, end=end_time, freq='1min')

        data = pd.DataFrame({
            'timestamp': time_range,
            'symbol': symbol,
            'price': np.random.normal(585.50, 0.5, len(time_range)),
            'volume': np.random.poisson(100000, len(time_range))
        })

        return data

    def _update_statistics(self,
                          execution: ExecutionRecord,
                          costs: dict[str, float]):
        """Update running statistics"""
        today = date.today()

        if today not in self.daily_stats:
            self.daily_stats[today] = {
                'total_executions': 0,
                'total_volume': 0,
                'total_cost_bps': 0,
                'costs': []
            }

        self.daily_stats[today]['total_executions'] += 1
        self.daily_stats[today]['total_volume'] += execution.quantity
        self.daily_stats[today]['costs'].append(costs['total_bps'])

    def _store_report(self, report: TCAReport):
        """Store TCA report in database"""
        if not self.db_manager:
            return

        # Convert report to dict for storage
        asdict(report)

        # Store in database
        # self.db_manager.insert_tca_report(report_dict)

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def get_execution_summary(self, order_id: str) -> dict[str, Any]:
        """Get execution summary for order"""
        if order_id not in self.order_contexts:
            return None

        executions = self.executions[order_id]
        if not executions:
            return None

        breakdown = self.cost_breakdowns.get(order_id)
        comparison = self.compare_to_benchmarks(order_id)

        return {
            'order_id': order_id,
            'symbol': self.order_contexts[order_id].symbol,
            'total_executions': len(executions),
            'total_quantity': sum(e.quantity for e in executions),
            'avg_price': sum(e.quantity * e.execution_price for e in executions) /
                        sum(e.quantity for e in executions),
            'total_cost_bps': breakdown.total_cost_bps if breakdown else 0,
            'quality_rating': comparison.quality_rating.value if comparison else None,
            'best_benchmark': comparison.best_benchmark if comparison else None
        }

    def get_daily_statistics(self, target_date: date) -> dict[str, Any]:
        """Get daily TCA statistics"""
        if target_date not in self.daily_stats:
            return None

        stats = self.daily_stats[target_date]

        return {
            'date': target_date,
            'total_executions': stats['total_executions'],
            'total_volume': stats['total_volume'],
            'avg_cost_bps': np.mean(stats['costs']) if stats['costs'] else 0,
            'median_cost_bps': np.median(stats['costs']) if stats['costs'] else 0,
            'std_cost_bps': np.std(stats['costs']) if stats['costs'] else 0
        }

    def shutdown(self):
        """Shutdown TCA system"""
        self.stop_monitoring.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("TransactionCostAnalyzer shutdown complete")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_tca_analyzer(database_manager: Optional['DatabaseManager'] = None) -> TransactionCostAnalyzer:
    """Factory function to create TCA analyzer"""
    return TransactionCostAnalyzer(database_manager)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


    # Create analyzer
    tca = create_tca_analyzer()

    # Simulate some executions
    test_order = OrderContext(
        order_id="TEST_001",
        symbol="SPY",
        side="BUY",
        total_quantity=10000,
        order_type="LIMIT",
        limit_price=585.50,
        arrival_time=datetime.now() - timedelta(minutes=10),
        arrival_price=585.45,
        decision_price=585.40,
        strategy="VWAP",
        urgency="NORMAL"
    )

    # Add to contexts
    tca.order_contexts[test_order.order_id] = test_order

    # Simulate executions
    executions = [
        ExecutionRecord(
            execution_id="EXEC_001",
            order_id=test_order.order_id,
            symbol="SPY",
            side="BUY",
            quantity=3000,
            execution_price=585.48,
            execution_time=datetime.now() - timedelta(minutes=8),
            venue=ExecutionVenue.SMART,
            liquidity_flag="REMOVE",
            commission=3.00,
            fees=0.30,
            rebates=0.00
        ),
        ExecutionRecord(
            execution_id="EXEC_002",
            order_id=test_order.order_id,
            symbol="SPY",
            side="BUY",
            quantity=4000,
            execution_price=585.52,
            execution_time=datetime.now() - timedelta(minutes=5),
            venue=ExecutionVenue.ARCA,
            liquidity_flag="ADD",
            commission=4.00,
            fees=0.40,
            rebates=0.20
        ),
        ExecutionRecord(
            execution_id="EXEC_003",
            order_id=test_order.order_id,
            symbol="SPY",
            side="BUY",
            quantity=3000,
            execution_price=585.55,
            execution_time=datetime.now() - timedelta(minutes=2),
            venue=ExecutionVenue.NASDAQ,
            liquidity_flag="REMOVE",
            commission=3.00,
            fees=0.30,
            rebates=0.00
        )
    ]

    # Process executions
    for execution in executions:
        market_context = MarketContext(
            symbol="SPY",
            timestamp=execution.execution_time,
            bid=585.45,
            ask=585.55,
            mid=585.50,
            spread=0.10,
            vwap=585.48,
            twap=585.50,
            volume=1000000,
            volatility=0.012,
            liquidity_score=85
        )

        tca.process_execution(execution, test_order, market_context)


    # Calculate TCA
    breakdown = tca.calculate_tca(test_order.order_id)


    # Benchmark comparison
    comparison = tca.compare_to_benchmarks(test_order.order_id)


    # Generate report
    report = tca.generate_tca_report(
        datetime.now() - timedelta(hours=1),
        datetime.now()
    )

    if report:
        pass

    # Shutdown
    tca.shutdown()
