#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderM01_OrderBookAnalyzer.py
Group: M (Market Microstructure)
Purpose: Level 2 order book analysis for optimal execution

Description:
This module analyzes order book dynamics to optimize execution
    quality. It detects hidden liquidity, estimates market impact, identifies
    optimal execution windows (9:45-10:15 AM), and provides professional
    execution recommendations targeting 90%+ fill rates.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable, Deque
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
import statistics
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import asyncio
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from SpyderB_Broker.SpyderB01_IBClient import IBClient
from SpyderC_MarketData.SpyderC01_DataFeed import MarketDataFeed

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
MIN_BID_ASK_LEVELS = 5              # Minimum levels for analysis
MAX_ORDER_BOOK_DEPTH = 20           # Maximum depth to analyze
HIDDEN_LIQUIDITY_THRESHOLD = 0.3    # 30% hidden liquidity threshold
TARGET_FILL_RATE = 0.90             # 90% fill rate target
TARGET_PRICE_IMPROVEMENT = 0.01     # 1 cent price improvement target
MAX_ACCEPTABLE_SLIPPAGE = 0.10      # 10 basis points maximum slippage
SMALL_ORDER_THRESHOLD = 0.02        # <2% of daily volume
MEDIUM_ORDER_THRESHOLD = 0.05       # 2-5% of daily volume
LARGE_ORDER_THRESHOLD = 0.10        # 5-10% of daily volume
OPTIMAL_ENTRY_START = "09:45:00"    # Optimal entry window start
OPTIMAL_ENTRY_END = "10:15:00"      # Optimal entry window end
LUNCH_PERIOD_START = "12:30:00"     # Reduced liquidity period
LUNCH_PERIOD_END = "13:30:00"       # Reduced liquidity period
LEVEL2_UPDATE_FREQUENCY = 0.1       # 100ms Level 2 updates
MICROSTRUCTURE_ANALYSIS_FREQ = 1.0  # 1 second analysis updates
class OrderSide(Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"
class LiquidityState(Enum):
    """Market liquidity state"""
    EXCELLENT = auto()
    GOOD = auto()
    FAIR = auto()
    POOR = auto()
    CRITICAL = auto()
class ExecutionTiming(Enum):
    """Execution timing recommendation"""
    IMMEDIATE = auto()
    OPTIMAL_WINDOW = auto()
    WAIT_FOR_LIQUIDITY = auto()
    AVOID_PERIOD = auto()
    END_OF_DAY = auto()
class OrderFlowDirection(Enum):
    """Order flow direction"""
    BULLISH = auto()
    BEARISH = auto()
    NEUTRAL = auto()
@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    size: int
    orders: int
    side: OrderSide
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot"""
    symbol: str
    timestamp: datetime
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]
    # Derived metrics
    bid_price: float = 0.0
    ask_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    mid_price: float = 0.0
    # Liquidity metrics
    bid_liquidity: float = 0.0  # Total bid size in top 5 levels
    ask_liquidity: float = 0.0  # Total ask size in top 5 levels
    imbalance_ratio: float = 0.0  # Bid vs ask imbalance
    def __post_init__(self):
        """Calculate derived metrics."""
        if self.bids and self.asks:
            self.bid_price = self.bids[0].price
            self.ask_price = self.asks[0].price
            self.spread = self.ask_price - self.bid_price
            self.mid_price = (self.bid_price + self.ask_price) / 2
            self.spread_bps = (self.spread / self.mid_price) * 10000 if self.mid_price > 0 else 0
            # Liquidity calculations
            self.bid_liquidity = sum(level.size for level in self.bids[:5])
            self.ask_liquidity = sum(level.size for level in self.asks[:5])
            total_liquidity = self.bid_liquidity + self.ask_liquidity
            if total_liquidity > 0:
                self.imbalance_ratio = (self.bid_liquidity - self.ask_liquidity) / total_liquidity
@dataclass
class ExecutionOpportunity:
    """Execution opportunity analysis"""
    symbol: str
    timestamp: datetime
    side: OrderSide
    # Execution metrics
    expected_fill_rate: float
    expected_price_improvement: float
    estimated_slippage_bps: float
    liquidity_state: LiquidityState
    # Timing recommendation
    timing_recommendation: ExecutionTiming
    optimal_execution_time: Optional[datetime]
    urgency_score: float  # 0-1 scale
    # Order flow context
    flow_direction: OrderFlowDirection
    momentum_score: float
    recent_volume_ratio: float
    # Execution strategy
    recommended_order_type: str  # 'MARKET', 'LIMIT', 'MIDPOINT'
    aggressive_side_penalty: float  # Cost of hitting vs. joining
    hidden_liquidity_probability: float
@dataclass
class MicrostructureMetrics:
    """Market microstructure metrics"""
    symbol: str
    timestamp: datetime
    # Spread metrics
    average_spread_bps: float
    spread_volatility: float
    effective_spread: float  # Including market impact
    # Liquidity metrics
    average_depth: float
    liquidity_stability: float
    hidden_liquidity_ratio: float
    # Order flow metrics
    order_flow_toxicity: float  # Probability of informed trading
    flow_imbalance: float
    trade_size_distribution: Dict[str, float]
    # Timing metrics
    optimal_execution_periods: List[Tuple[datetime, datetime]]
    volume_weighted_spread: float
    # Market quality
    price_efficiency: float
    liquidity_provision_rate: float
class OrderBookAnalyzer:
    """
    Professional order book analysis for optimal execution.
    Provides real-time Level 2 order book analysis with:
    - Liquidity state assessment
    - Hidden liquidity detection
    - Optimal execution timing
    - Market impact estimation
    - Professional execution recommendations
    """
    def __init__(
        self,
        ib_client: IBClient,
        market_data_feed: MarketDataFeed,
        symbols: List[str] = None
    ):
        """Initialize order book analyzer."""
        self.ib_client = ib_client
        self.market_data_feed = market_data_feed
        self.symbols = symbols or ['SPY']
        # Logging
        self.logger = SpyderLogger().get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.time_utils = TradingTimeUtils()
        # Order book data
        self.order_books: Dict[str, OrderBookSnapshot] = {}
        self.book_history: Dict[str, Deque[OrderBookSnapshot]] = defaultdict(lambda: deque(maxlen=1000))
        # Analysis state
        self.microstructure_metrics: Dict[str, MicrostructureMetrics] = {}
        self.execution_opportunities: Dict[str, ExecutionOpportunity] = {}
        # Monitoring control
        self.monitoring_active = False
        self.analysis_thread: Optional[threading.Thread] = None
        # Performance tracking
        self.fill_rate_history = deque(maxlen=100)
        self.price_improvement_history = deque(maxlen=100)
        self.slippage_history = deque(maxlen=100)
        # Callbacks
        self.opportunity_callbacks: List[Callable] = []
        self.liquidity_alert_callbacks: List[Callable] = []
        self.logger.info(f"Order Book Analyzer initialized for symbols: {self.symbols}")
    # ==========================================================================
    # PUBLIC METHODS - CORE FUNCTIONALITY
    # ==========================================================================
    def start_analysis(self) -> None:
        """Start real-time order book analysis."""
        if self.monitoring_active:
            self.logger.warning("Order book analysis already active")
            return
        self.monitoring_active = True
        # Subscribe to Level 2 data
        for symbol in self.symbols:
            self.ib_client.subscribe_level2_data(symbol, self._on_level2_update)
        # Start analysis thread
        self.analysis_thread = threading.Thread(
            target=self._analysis_loop,
            name="OrderBookAnalysis",
            daemon=True
        )
        self.analysis_thread.start()
        self.logger.info("Order book analysis started")
    def stop_analysis(self) -> None:
        """Stop order book analysis."""
        self.monitoring_active = False
        # Unsubscribe from data
        for symbol in self.symbols:
            self.ib_client.unsubscribe_level2_data(symbol)
        # Stop analysis thread
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=5.0)
        self.logger.info("Order book analysis stopped")
    def get_execution_recommendation(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        urgency: float = 0.5
    ) -> Optional[ExecutionOpportunity]:
        """Get execution recommendation for a trade."""
        try:
            # Get current order book
            book = self.order_books.get(symbol)
            if not book:
                self.logger.warning(f"No order book data for {symbol}")
                return None
            # Analyze execution opportunity
            opportunity = self._analyze_execution_opportunity(
                symbol, side, quantity, urgency, book
            )
            return opportunity
        except Exception as e:
            self.error_handler.handle_error(e, "get_execution_recommendation")
            return None
    def get_current_liquidity_state(self, symbol: str) -> Optional[LiquidityState]:
        """Get current liquidity state for symbol."""
        book = self.order_books.get(symbol)
        if not book:
            return None
        return self._assess_liquidity_state(book)
    def get_optimal_execution_time(self, symbol: str) -> Optional[datetime]:
        """Get optimal execution time based on historical patterns."""
        try:
            current_time = datetime.now().time()
            # Check if we're in optimal window
            optimal_start = datetime.strptime(OPTIMAL_ENTRY_START, "%H:%M:%S").time()
            optimal_end = datetime.strptime(OPTIMAL_ENTRY_END, "%H:%M:%S").time()
            if optimal_start <= current_time <= optimal_end:
                return datetime.now()  # Execute now
            # Check if we're in poor liquidity period
            lunch_start = datetime.strptime(LUNCH_PERIOD_START, "%H:%M:%S").time()
            lunch_end = datetime.strptime(LUNCH_PERIOD_END, "%H:%M:%S").time()
            if lunch_start <= current_time <= lunch_end:
                # Wait until after lunch
                next_good_time = datetime.now().replace(
                    hour=13, minute=30, second=0, microsecond=0
                )
                return next_good_time
            # Default to next optimal window
            next_optimal = datetime.now().replace(
                hour=9, minute=45, second=0, microsecond=0
            )
            if next_optimal <= datetime.now():
                next_optimal += timedelta(days=1)
            return next_optimal
        except Exception as e:
            self.error_handler.handle_error(e, "get_optimal_execution_time")
            return None
    def estimate_market_impact(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int
    ) -> Dict[str, float]:
        """Estimate market impact for trade size."""
        try:
            book = self.order_books.get(symbol)
            if not book:
                return {'impact_bps': 0.0, 'confidence': 0.0}
            # Get average daily volume
            daily_volume = self._get_average_daily_volume(symbol)
            if daily_volume == 0:
                return {'impact_bps': 0.0, 'confidence': 0.0}
            # Calculate volume percentage
            volume_pct = quantity / daily_volume
            # Estimate impact based on order book depth
            levels_needed = 0
            remaining_quantity = quantity
            total_cost = 0.0
            levels = book.asks if side == OrderSide.BUY else book.bids
            for level in levels:
                if remaining_quantity <= 0:
                    break
                level_quantity = min(remaining_quantity, level.size)
                total_cost += level_quantity * level.price
                remaining_quantity -= level_quantity
                levels_needed += 1
            if remaining_quantity > 0:
                # Not enough liquidity in book
                impact_bps = max(50.0, volume_pct * 1000)  # High impact estimate
                confidence = 0.3
            else:
                # Calculate actual impact
                reference_price = book.mid_price
                average_price = total_cost / quantity if quantity > 0 else reference_price
                impact_bps = abs(average_price - reference_price) / reference_price * 10000
                confidence = 0.8 if levels_needed <= 3 else 0.6
            return {
                'impact_bps': impact_bps,
                'confidence': confidence,
                'levels_needed': levels_needed,
                'volume_percentage': volume_pct * 100
            }
        except Exception as e:
            self.error_handler.handle_error(e, "estimate_market_impact")
            return {'impact_bps': 0.0, 'confidence': 0.0}
    def get_hidden_liquidity_probability(self, symbol: str) -> float:
        """Estimate probability of hidden liquidity."""
        try:
            book = self.order_books.get(symbol)
            if not book:
                return 0.0
            # Analyze recent order book changes for hidden liquidity signals
            recent_books = list(self.book_history[symbol])[-10:]  # Last 10 snapshots
            if len(recent_books) < 5:
                return 0.5  # Default assumption
            # Look for signs of hidden liquidity:
            # 1. Large trades without significant book impact
            # 2. Quick replenishment of depleted levels
            # 3. Tight spreads despite small visible size
            hidden_signals = 0
            total_checks = 0
            for i in range(1, len(recent_books)):
                prev_book = recent_books[i-1]
                curr_book = recent_books[i]
                # Check for level replenishment
                if self._detect_level_replenishment(prev_book, curr_book):
                    hidden_signals += 1
                # Check for spread stability despite small size
                if curr_book.spread_bps < 15 and curr_book.bid_liquidity < 100:
                    hidden_signals += 1
                total_checks += 2
            probability = hidden_signals / total_checks if total_checks > 0 else 0.5
            return min(1.0, max(0.0, probability))
        except Exception as e:
            self.error_handler.handle_error(e, "get_hidden_liquidity_probability")
            return 0.5
    # ==========================================================================
    # PUBLIC METHODS - PERFORMANCE TRACKING
    # ==========================================================================
    def record_execution_result(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        expected_price: float,
        actual_price: float,
        fill_rate: float
    ) -> None:
        """Record execution result for performance tracking."""
        try:
            # Calculate metrics
            price_improvement = (expected_price - actual_price) * (1 if side == OrderSide.BUY else -1)
            slippage_bps = abs(actual_price - expected_price) / expected_price * 10000
            # Store in history
            self.fill_rate_history.append(fill_rate)
            self.price_improvement_history.append(price_improvement)
            self.slippage_history.append(slippage_bps)
            self.logger.info(
                f"Execution recorded: {symbol} {side.value} {quantity} "
                f"Fill: {fill_rate:.1%}, Improvement: ${price_improvement:.3f}, "
                f"Slippage: {slippage_bps:.1f}bps"
            )
        except Exception as e:
            self.error_handler.handle_error(e, "record_execution_result")
    def get_execution_performance(self) -> Dict[str, float]:
        """Get execution performance metrics."""
        if not self.fill_rate_history:
            return {}
        return {
            'average_fill_rate': statistics.mean(self.fill_rate_history),
            'average_price_improvement': statistics.mean(self.price_improvement_history),
            'average_slippage_bps': statistics.mean(self.slippage_history),
            'fill_rate_consistency': 1.0 - statistics.stdev(self.fill_rate_history),
            'execution_count': len(self.fill_rate_history),
            'target_fill_rate_achievement': sum(1 for x in self.fill_rate_history if x >= TARGET_FILL_RATE) / len(self.fill_rate_history)
        }
    # ==========================================================================
    # PRIVATE METHODS - ANALYSIS LOOP
    # ==========================================================================
    def _analysis_loop(self) -> None:
        """Main analysis loop."""
        self.logger.info("Order book analysis loop started")
        while self.monitoring_active:
            try:
                start_time = time.time()
                # Analyze each symbol
                for symbol in self.symbols:
                    if symbol in self.order_books:
                        self._analyze_microstructure(symbol)
                        self._identify_execution_opportunities(symbol)
                # Calculate sleep time
                elapsed = time.time() - start_time
                sleep_time = max(0, MICROSTRUCTURE_ANALYSIS_FREQ - elapsed)
                time.sleep(sleep_time)
            except Exception as e:
                self.error_handler.handle_error(e, "_analysis_loop")
                time.sleep(1.0)
    def _on_level2_update(self, symbol: str, bids: List, asks: List) -> None:
        """Handle Level 2 order book update."""
        try:
            # Convert to our format
            bid_levels = [
                OrderBookLevel(
                    price=float(bid[0]),
                    size=int(bid[1]),
                    orders=int(bid[2]) if len(bid) > 2 else 1,
                    side=OrderSide.BUY
                ) for bid in bids[:MAX_ORDER_BOOK_DEPTH]
            ]
            ask_levels = [
                OrderBookLevel(
                    price=float(ask[0]),
                    size=int(ask[1]),
                    orders=int(ask[2]) if len(ask) > 2 else 1,
                    side=OrderSide.SELL
                ) for ask in asks[:MAX_ORDER_BOOK_DEPTH]
            ]
            # Create snapshot
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                bids=bid_levels,
                asks=ask_levels
            )
            # Store current and historical data
            self.order_books[symbol] = snapshot
            self.book_history[symbol].append(snapshot)
        except Exception as e:
            self.error_handler.handle_error(e, "_on_level2_update")
    def _analyze_microstructure(self, symbol: str) -> None:
        """Analyze microstructure for symbol."""
        try:
            book = self.order_books.get(symbol)
            if not book:
                return
            # Get recent history
            recent_books = list(self.book_history[symbol])[-50:]  # Last 50 snapshots
            if len(recent_books) < 10:
                return
            # Calculate microstructure metrics
            spreads = [b.spread_bps for b in recent_books]
            depths = [b.bid_liquidity + b.ask_liquidity for b in recent_books]
            metrics = MicrostructureMetrics(
                symbol=symbol,
                timestamp=datetime.now(),
                average_spread_bps=statistics.mean(spreads),
                spread_volatility=statistics.stdev(spreads) if len(spreads) > 1 else 0.0,
                effective_spread=book.spread_bps * 1.2,  # Simplified
                average_depth=statistics.mean(depths),
                liquidity_stability=1.0 - (statistics.stdev(depths) / statistics.mean(depths)) if statistics.mean(depths) > 0 else 0.0,
                hidden_liquidity_ratio=self.get_hidden_liquidity_probability(symbol),
                order_flow_toxicity=self._calculate_flow_toxicity(recent_books),
                flow_imbalance=book.imbalance_ratio,
                trade_size_distribution={'small': 0.6, 'medium': 0.3, 'large': 0.1},  # Placeholder
                optimal_execution_periods=[],  # Would be calculated from historical data
                volume_weighted_spread=book.spread_bps,  # Simplified
                price_efficiency=0.85,  # Placeholder
                liquidity_provision_rate=0.75  # Placeholder
            )
            self.microstructure_metrics[symbol] = metrics
        except Exception as e:
            self.error_handler.handle_error(e, "_analyze_microstructure")
    def _identify_execution_opportunities(self, symbol: str) -> None:
        """Identify execution opportunities."""
        try:
            book = self.order_books.get(symbol)
            if not book:
                return
            # Analyze both buy and sell opportunities
            for side in [OrderSide.BUY, OrderSide.SELL]:
                opportunity = self._analyze_execution_opportunity(
                    symbol, side, 100, 0.5, book  # Standard 100 contract analysis
                )
                if opportunity:
                    self.execution_opportunities[f"{symbol}_{side.value}"] = opportunity
                    # Trigger callbacks if high-quality opportunity
                    if opportunity.urgency_score > 0.7:
                        for callback in self.opportunity_callbacks:
                            try:
                                callback(opportunity)
                            except Exception as e:
                                self.logger.error(f"Opportunity callback error: {e}")
        except Exception as e:
            self.error_handler.handle_error(e, "_identify_execution_opportunities")
    # ==========================================================================
    # PRIVATE METHODS - ANALYSIS UTILITIES
    # ==========================================================================
    def _analyze_execution_opportunity(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        urgency: float,
        book: OrderBookSnapshot
    ) -> Optional[ExecutionOpportunity]:
        """Analyze execution opportunity for specific trade."""
        try:
            # Assess liquidity state
            liquidity_state = self._assess_liquidity_state(book)
            # Calculate expected fill rate
            fill_rate = self._estimate_fill_rate(book, side, quantity)
            # Estimate price improvement
            price_improvement = self._estimate_price_improvement(book, side, quantity)
            # Calculate slippage
            slippage_bps = self._estimate_slippage(book, side, quantity)
            # Determine timing recommendation
            timing_rec = self._get_timing_recommendation(liquidity_state, urgency)
            # Assess order flow
            flow_direction = self._assess_order_flow_direction(book)
            opportunity = ExecutionOpportunity(
                symbol=symbol,
                timestamp=datetime.now(),
                side=side,
                expected_fill_rate=fill_rate,
                expected_price_improvement=price_improvement,
                estimated_slippage_bps=slippage_bps,
                liquidity_state=liquidity_state,
                timing_recommendation=timing_rec,
                optimal_execution_time=self.get_optimal_execution_time(symbol),
                urgency_score=urgency,
                flow_direction=flow_direction,
                momentum_score=self._calculate_momentum_score(symbol),
                recent_volume_ratio=self._get_recent_volume_ratio(symbol),
                recommended_order_type=self._recommend_order_type(book, side, urgency),
                aggressive_side_penalty=self._calculate_aggressive_penalty(book),
                hidden_liquidity_probability=self.get_hidden_liquidity_probability(symbol)
            )
            return opportunity
        except Exception as e:
            self.error_handler.handle_error(e, "_analyze_execution_opportunity")
            return None
    def _assess_liquidity_state(self, book: OrderBookSnapshot) -> LiquidityState:
        """Assess current liquidity state."""
        # Multiple factors determine liquidity quality
        spread_score = min(1.0, 20.0 / book.spread_bps) if book.spread_bps > 0 else 0.0
        depth_score = min(1.0, (book.bid_liquidity + book.ask_liquidity) / 500.0)
        balance_score = 1.0 - abs(book.imbalance_ratio)
        overall_score = (spread_score + depth_score + balance_score) / 3.0
        if overall_score >= 0.8:
            return LiquidityState.EXCELLENT
        elif overall_score >= 0.6:
            return LiquidityState.GOOD
        elif overall_score >= 0.4:
            return LiquidityState.FAIR
        elif overall_score >= 0.2:
            return LiquidityState.POOR
        else:
            return LiquidityState.CRITICAL
    def _estimate_fill_rate(self, book: OrderBookSnapshot, side: OrderSide, quantity: int) -> float:
        """Estimate expected fill rate."""
        levels = book.asks if side == OrderSide.BUY else book.bids
        available_liquidity = sum(level.size for level in levels[:5])
        if quantity <= available_liquidity * 0.3:
            return 0.95  # High fill rate for small orders
        elif quantity <= available_liquidity * 0.6:
            return 0.85  # Good fill rate for medium orders
        elif quantity <= available_liquidity:
            return 0.70  # Fair fill rate for large orders
        else:
            return 0.40  # Poor fill rate when exceeding visible liquidity
    def _estimate_price_improvement(self, book: OrderBookSnapshot, side: OrderSide, quantity: int) -> float:
        """Estimate expected price improvement."""
        # Simplified model - real implementation would be more sophisticated
        if book.spread <= 0.02:  # 2 cent spread
            return 0.005  # Half cent improvement
        elif book.spread <= 0.05:  # 5 cent spread
            return 0.010  # 1 cent improvement
        else:
            return 0.015  # 1.5 cent improvement
    def _estimate_slippage(self, book: OrderBookSnapshot, side: OrderSide, quantity: int) -> float:
        """Estimate execution slippage in basis points."""
        impact = self.estimate_market_impact(book.symbol, side, quantity)
        return impact.get('impact_bps', 0.0)
    def _get_timing_recommendation(self, liquidity_state: LiquidityState, urgency: float) -> ExecutionTiming:
        """Get timing recommendation based on liquidity and urgency."""
        current_time = datetime.now().time()
        # Check if in optimal window
        optimal_start = datetime.strptime(OPTIMAL_ENTRY_START, "%H:%M:%S").time()
        optimal_end = datetime.strptime(OPTIMAL_ENTRY_END, "%H:%M:%S").time()
        in_optimal_window = optimal_start <= current_time <= optimal_end
        if urgency > 0.8:
            return ExecutionTiming.IMMEDIATE
        elif in_optimal_window and liquidity_state in [LiquidityState.EXCELLENT, LiquidityState.GOOD]:
            return ExecutionTiming.OPTIMAL_WINDOW
        elif liquidity_state == LiquidityState.POOR:
            return ExecutionTiming.WAIT_FOR_LIQUIDITY
        else:
            return ExecutionTiming.OPTIMAL_WINDOW
    def _assess_order_flow_direction(self, book: OrderBookSnapshot) -> OrderFlowDirection:
        """Assess order flow direction."""
        if book.imbalance_ratio > 0.2:
            return OrderFlowDirection.BULLISH
        elif book.imbalance_ratio < -0.2:
            return OrderFlowDirection.BEARISH
        else:
            return OrderFlowDirection.NEUTRAL
    def _recommend_order_type(self, book: OrderBookSnapshot, side: OrderSide, urgency: float) -> str:
        """Recommend order type based on conditions."""
        if urgency > 0.8:
            return "MARKET"
        elif book.spread_bps < 10:  # Tight spread
            return "MIDPOINT"
        else:
            return "LIMIT"
    def _calculate_flow_toxicity(self, recent_books: List[OrderBookSnapshot]) -> float:
        """Calculate order flow toxicity (probability of informed trading)."""
        # Simplified implementation
        return 0.3  # 30% toxicity assumption
    def _calculate_momentum_score(self, symbol: str) -> float:
        """Calculate momentum score."""
        # Simplified implementation
        return 0.5  # Neutral momentum
    def _get_recent_volume_ratio(self, symbol: str) -> float:
        """Get recent volume ratio vs average."""
        # Simplified implementation
        return 1.0  # Normal volume
    def _calculate_aggressive_penalty(self, book: OrderBookSnapshot) -> float:
        """Calculate penalty for aggressive orders."""
        return book.spread / 2  # Half spread penalty
    def _get_average_daily_volume(self, symbol: str) -> float:
        """Get average daily volume for symbol."""
        # Would integrate with historical data - simplified for now
        if symbol == 'SPY':
            return 50000000  # 50M average daily volume for SPY
        else:
            return 1000000   # 1M default for options
    def _detect_level_replenishment(self, prev_book: OrderBookSnapshot, curr_book: OrderBookSnapshot) -> bool:
        """Detect if order book levels were quickly replenished."""
        # Check if top level was depleted and then replenished
        if not prev_book.bids or not curr_book.bids:
            return False
        # If bid size increased significantly after decrease
        prev_bid_size = prev_book.bids[0].size if prev_book.bids else 0
        curr_bid_size = curr_book.bids[0].size if curr_book.bids else 0
        # Simple replenishment detection
        return curr_bid_size > prev_bid_size * 1.5
    # ==========================================================================
    # PUBLIC METHODS - CALLBACKS
    # ==========================================================================
    def add_opportunity_callback(self, callback: Callable[[ExecutionOpportunity], None]) -> None:
        """Add callback for execution opportunities."""
        self.opportunity_callbacks.append(callback)
    def add_liquidity_alert_callback(self, callback: Callable[[str, LiquidityState], None]) -> None:
        """Add callback for liquidity alerts."""
        self.liquidity_alert_callbacks.append(callback)
    # ==========================================================================
    # PUBLIC METHODS - REPORTING
    # ==========================================================================
    def get_current_market_quality(self) -> Dict[str, Any]:
        """Get current market quality metrics."""
        quality_metrics = {}
        for symbol in self.symbols:
            book = self.order_books.get(symbol)
            if not book:
                continue
            liquidity_state = self._assess_liquidity_state(book)
            quality_metrics[symbol] = {
                'timestamp': book.timestamp,
                'bid_ask_spread_bps': book.spread_bps,
                'liquidity_state': liquidity_state.name,
                'bid_liquidity': book.bid_liquidity,
                'ask_liquidity': book.ask_liquidity,
                'imbalance_ratio': book.imbalance_ratio,
                'hidden_liquidity_prob': self.get_hidden_liquidity_probability(symbol),
                'optimal_execution_window': self.time_utils.is_optimal_trading_time()
            }
        return quality_metrics
    def get_execution_cost_analysis(self, symbol: str, side: OrderSide, quantity: int) -> Dict[str, Any]:
        """Get detailed execution cost analysis."""
        try:
            book = self.order_books.get(symbol)
            if not book:
                return {}
            # Market order cost
            market_impact = self.estimate_market_impact(symbol, side, quantity)
            # Limit order analysis
            limit_price = book.bid_price if side == OrderSide.SELL else book.ask_price
            limit_fill_prob = self._estimate_fill_rate(book, side, quantity)
            # Midpoint order analysis
            mid_price = book.mid_price
            mid_savings = book.spread / 2
            mid_fill_prob = limit_fill_prob * 0.7  # Lower fill probability
            return {
                'symbol': symbol,
                'side': side.value,
                'quantity': quantity,
                'current_spread_bps': book.spread_bps,
                'market_order': {
                    'estimated_impact_bps': market_impact.get('impact_bps', 0),
                    'fill_probability': 0.98,
                    'execution_certainty': 'high'
                },
                'limit_order': {
                    'price': limit_price,
                    'savings_vs_market': 0.0,
                    'fill_probability': limit_fill_prob,
                    'execution_certainty': 'medium'
                },
                'midpoint_order': {
                    'price': mid_price,
                    'savings_vs_market': mid_savings,
                    'fill_probability': mid_fill_prob,
                    'execution_certainty': 'low'
                },
                'recommendation': self._recommend_order_type(book, side, 0.5),
                'optimal_timing': self.get_optimal_execution_time(symbol)
            }
        except Exception as e:
            self.error_handler.handle_error(e, "get_execution_cost_analysis")
            return {}
    def generate_execution_report(self) -> Dict[str, Any]:
        """Generate comprehensive execution analysis report."""
        try:
            performance = self.get_execution_performance()
            market_quality = self.get_current_market_quality()
            # Overall assessment
            overall_liquidity = "GOOD"
            if all(metrics.get('liquidity_state') in ['EXCELLENT', 'GOOD'] 
                  for metrics in market_quality.values()):
                overall_liquidity = "EXCELLENT"
            elif any(metrics.get('liquidity_state') == 'CRITICAL' 
                    for metrics in market_quality.values()):
                overall_liquidity = "POOR"
            return {
                'report_timestamp': datetime.now(),
                'monitoring_status': self.monitoring_active,
                'symbols_tracked': len(self.symbols),
                'overall_market_liquidity': overall_liquidity,
                'performance_metrics': performance,
                'market_quality_by_symbol': market_quality,
                'execution_recommendations': {
                    'current_period': 'optimal' if self.time_utils.is_optimal_trading_time() else 'suboptimal',
                    'next_optimal_window': self.get_optimal_execution_time('SPY'),
                    'general_advice': self._get_general_execution_advice()
                },
                'system_health': {
                    'order_book_updates_per_second': len(self.book_history.get('SPY', [])) / 60.0,
                    'analysis_latency_ms': 10.0,  # Placeholder
                    'data_quality_score': 0.95    # Placeholder
                }
            }
        except Exception as e:
            self.error_handler.handle_error(e, "generate_execution_report")
            return {}
    def _get_general_execution_advice(self) -> str:
        """Get general execution advice based on current conditions."""
        current_time = datetime.now().time()
        optimal_start = datetime.strptime(OPTIMAL_ENTRY_START, "%H:%M:%S").time()
        optimal_end = datetime.strptime(OPTIMAL_ENTRY_END, "%H:%M:%S").time()
        lunch_start = datetime.strptime(LUNCH_PERIOD_START, "%H:%M:%S").time()
        lunch_end = datetime.strptime(LUNCH_PERIOD_END, "%H:%M:%S").time()
        if optimal_start <= current_time <= optimal_end:
            return "Optimal execution window - proceed with normal trading"
        elif lunch_start <= current_time <= lunch_end:
            return "Lunch period - consider waiting for better liquidity"
        elif current_time < optimal_start:
            return "Pre-market - wait for opening rotation to complete"
        else:
            return "Standard trading hours - monitor liquidity carefully"
if __name__ == "__main__":
    print("Order Book Analyzer - Professional Market Microstructure")
    print("=" * 65)
    # Example usage (would need real IB client and market data feed)
    print("This module provides:")
    print("• Real-time Level 2 order book analysis")
    print("• Professional execution recommendations")
    print("• Market impact estimation")
    print("• Hidden liquidity detection")
    print("• Optimal timing analysis")
    print("• Execution quality tracking")
    # Mock example
    print("\nExample analysis output:")
    print("Symbol: SPY")
    print("Bid-Ask Spread: 1.2 bps")
    print("Liquidity State: EXCELLENT")
    print("Hidden Liquidity Probability: 65%")
    print("Recommended Order Type: MIDPOINT")
    print("Expected Fill Rate: 92%")
    print("Estimated Price Improvement: $0.01")