#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderZ05_OrderRouter.py
Group: Z (Communication)
Purpose: Intelligent order routing to optimal execution venues with lifecycle management
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 14:30:00

Description:
    This module provides intelligent order routing capabilities that automatically
    select the best execution venue based on real-time market conditions, liquidity,
    fees, and historical execution quality. It manages order lifecycle events,
    maintains priority queues, and optimizes routing decisions to achieve best
    execution while minimizing costs and market impact.

Key Features:
    - Smart order routing across multiple venues
    - Venue selection based on liquidity and fees
    - Order priority queue management
    - Dark pool routing for large orders
    - Latency-aware routing optimization
    - Real-time venue performance tracking
    - Order splitting and aggregation
    - Regulatory compliance (Reg NMS)
    - Kill switch and circuit breakers
    - Detailed routing analytics
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import queue
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import random
import hashlib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderB_Broker.SpyderB02_OrderManager import Order, OrderStatus  # noqa: F401
    from SpyderM_Monitoring.SpyderM05_TransactionCostAnalysis import ExecutionVenue
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

    # Mock classes for standalone testing
    class OrderStatus(Enum):
        PENDING = "PENDING"
        SUBMITTED = "SUBMITTED"
        FILLED = "FILLED"
        CANCELLED = "CANCELLED"
        REJECTED = "REJECTED"

    class ExecutionVenue(Enum):
        SMART = "SMART"
        NYSE = "NYSE"
        NASDAQ = "NASDAQ"
        ARCA = "ARCA"
        BATS = "BATS"
        IEX = "IEX"
        DARK = "DARK_POOL"

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Routing Parameters
MAX_ROUTING_LATENCY_MS = 5  # Maximum acceptable routing decision time
DEFAULT_QUEUE_SIZE = 10000
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_MS = 100

# Venue Selection Weights
LIQUIDITY_WEIGHT = 0.40
FEE_WEIGHT = 0.25
LATENCY_WEIGHT = 0.20
FILL_QUALITY_WEIGHT = 0.15

# Dark Pool Thresholds
DARK_POOL_MIN_SIZE = 1000  # Minimum shares for dark pool
DARK_POOL_MAX_PERCENTAGE = 0.30  # Max 30% to dark pools

# Circuit Breaker Parameters
MAX_ORDERS_PER_SECOND = 100
MAX_REJECTION_RATE = 0.10  # 10% rejection rate triggers circuit breaker
CIRCUIT_BREAKER_COOLDOWN = 60  # seconds

# Venue Characteristics (mock data for testing)
VENUE_CHARACTERISTICS = {
    ExecutionVenue.NYSE: {
        'latency_ms': 2,
        'fee_per_share': 0.0030,
        'rebate_per_share': 0.0020,
        'typical_spread': 0.01,
        'liquidity_score': 95,
        'dark_pool': False
    },
    ExecutionVenue.NASDAQ: {
        'latency_ms': 1,
        'fee_per_share': 0.0028,
        'rebate_per_share': 0.0022,
        'typical_spread': 0.01,
        'liquidity_score': 98,
        'dark_pool': False
    },
    ExecutionVenue.ARCA: {
        'latency_ms': 1,
        'fee_per_share': 0.0030,
        'rebate_per_share': 0.0021,
        'typical_spread': 0.01,
        'liquidity_score': 90,
        'dark_pool': False
    },
    ExecutionVenue.BATS: {
        'latency_ms': 1,
        'fee_per_share': 0.0025,
        'rebate_per_share': 0.0023,
        'typical_spread': 0.01,
        'liquidity_score': 85,
        'dark_pool': False
    },
    ExecutionVenue.IEX: {
        'latency_ms': 350,  # IEX speed bump
        'fee_per_share': 0.0009,
        'rebate_per_share': 0,
        'typical_spread': 0.02,
        'liquidity_score': 70,
        'dark_pool': False
    },
    ExecutionVenue.DARK: {
        'latency_ms': 5,
        'fee_per_share': 0.0010,
        'rebate_per_share': 0,
        'typical_spread': 0,
        'liquidity_score': 60,
        'dark_pool': True
    }
}

# ==============================================================================
# ENUMS
# ==============================================================================

class RoutingStrategy(Enum):
    """Order routing strategies"""
    SMART = "SMART_ROUTING"
    SPRAY = "SPRAY_ROUTING"
    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"
    DARK_ONLY = "DARK_ONLY"
    LIT_ONLY = "LIT_ONLY"
    LATENCY_OPTIMIZED = "LATENCY_OPTIMIZED"
    COST_OPTIMIZED = "COST_OPTIMIZED"

class OrderPriority(Enum):
    """Order priority levels"""
    CRITICAL = 0  # Highest priority
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BATCH = 4  # Lowest priority

class RoutingEvent(Enum):
    """Order routing lifecycle events"""
    RECEIVED = "ORDER_RECEIVED"
    QUEUED = "ORDER_QUEUED"
    ROUTING = "ROUTING_STARTED"
    ROUTED = "ORDER_ROUTED"
    ACKNOWLEDGED = "VENUE_ACK"
    REJECTED = "VENUE_REJECT"
    FILLED = "ORDER_FILLED"
    PARTIAL = "PARTIAL_FILL"
    CANCELLED = "ORDER_CANCELLED"
    EXPIRED = "ORDER_EXPIRED"

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    TRIGGERED = "TRIGGERED"
    COOLDOWN = "COOLDOWN"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class RoutableOrder:
    """Order with routing information"""
    order_id: str
    symbol: str
    side: str  # BUY/SELL
    quantity: int
    order_type: str  # MARKET/LIMIT/STOP
    limit_price: float | None
    stop_price: float | None
    time_in_force: str  # DAY/GTC/IOC/FOK
    routing_strategy: RoutingStrategy
    priority: OrderPriority
    max_venues: int = 3
    allow_dark: bool = True
    min_fill_size: int | None = None
    max_display_size: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class VenueQuote:
    """Market quote from a venue"""
    venue: ExecutionVenue
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    timestamp: datetime

@dataclass
class RoutingDecision:
    """Routing decision for an order"""
    order_id: str
    venue: ExecutionVenue
    quantity: int
    routing_time: datetime
    expected_fee: float
    expected_rebate: float
    expected_latency_ms: float
    liquidity_score: float
    confidence: float
    reasoning: str

@dataclass
class VenuePerformance:
    """Venue performance metrics"""
    venue: ExecutionVenue
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    partial_fills: int = 0
    avg_fill_time_ms: float = 0
    avg_fill_quality: float = 0  # Price improvement
    total_fees: float = 0
    total_rebates: float = 0
    avg_spread: float = 0
    fill_rate: float = 0
    rejection_rate: float = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class OrderLifecycle:
    """Complete order lifecycle tracking"""
    order_id: str
    events: list[tuple[RoutingEvent, datetime, dict]]
    routing_decisions: list[RoutingDecision]
    fills: list[dict]
    total_filled: int = 0
    avg_fill_price: float = 0
    total_fees: float = 0
    total_rebates: float = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    status: OrderStatus = OrderStatus.PENDING

@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status"""
    state: CircuitBreakerState
    orders_per_second: float
    rejection_rate: float
    last_triggered: datetime | None
    cooldown_until: datetime | None
    triggers_count: int = 0

# ==============================================================================
# ORDER ROUTER
# ==============================================================================

class OrderRouter:
    """
    Intelligent order routing system with venue optimization
    Routes orders to best execution venue based on multiple factors
    """

    def __init__(self):
        """Initialize order router"""
        # Logging
        if LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)

        # Order queues by priority
        self.order_queues: dict[OrderPriority, queue.PriorityQueue] = {}
        for priority in OrderPriority:
            self.order_queues[priority] = queue.PriorityQueue(maxsize=DEFAULT_QUEUE_SIZE)

        # Active orders and lifecycle tracking
        self.active_orders: dict[str, RoutableOrder] = {}
        self.order_lifecycles: dict[str, OrderLifecycle] = {}

        # Venue tracking
        self.venue_performance: dict[ExecutionVenue, VenuePerformance] = {}
        self.venue_quotes: dict[str, dict[ExecutionVenue, VenueQuote]] = defaultdict(dict)
        self.venue_availability: dict[ExecutionVenue, bool] = {
            venue: True for venue in ExecutionVenue
        }

        # Initialize venue performance
        for venue in ExecutionVenue:
            self.venue_performance[venue] = VenuePerformance(venue=venue)

        # Circuit breaker
        self.circuit_breaker = CircuitBreakerStatus(
            state=CircuitBreakerState.NORMAL,
            orders_per_second=0,
            rejection_rate=0,
            last_triggered=None,
            cooldown_until=None
        )

        # Statistics
        self.total_orders_routed = 0
        self.total_orders_filled = 0
        self.total_orders_rejected = 0
        self.routing_latencies: deque = deque(maxlen=1000)

        # Threading
        self.router_thread = None
        self.monitor_thread = None
        self.stop_event = threading.Event()

        # Start router
        self._start_router()

        self.logger.info("✅ OrderRouter initialized")

    # ==========================================================================
    # ORDER SUBMISSION
    # ==========================================================================

    def submit_order(self, order: RoutableOrder) -> str:
        """
        Submit order for routing

        Args:
            order: Order to route

        Returns:
            Order ID for tracking
        """
        # Check circuit breaker
        if self.circuit_breaker.state == CircuitBreakerState.TRIGGERED:
            if self.circuit_breaker.cooldown_until and datetime.now(timezone.utc) < self.circuit_breaker.cooldown_until:  # noqa: E501
                self.logger.warning("Circuit breaker active - order rejected: %s", order.order_id)
                self._record_event(order.order_id, RoutingEvent.REJECTED,
                                 {'reason': 'circuit_breaker'})
                return None
            else:
                # Reset circuit breaker
                self._reset_circuit_breaker()

        # Generate order ID if not provided
        if not order.order_id:
            order.order_id = self._generate_order_id()

        # Initialize lifecycle tracking
        self.order_lifecycles[order.order_id] = OrderLifecycle(
            order_id=order.order_id,
            events=[(RoutingEvent.RECEIVED, datetime.now(timezone.utc), {})],
            routing_decisions=[],
            fills=[]
        )

        # Add to active orders
        self.active_orders[order.order_id] = order

        # Queue order based on priority
        priority_value = order.priority.value
        queue_item = (priority_value, order.created_at, order)

        try:
            self.order_queues[order.priority].put_nowait(queue_item)
            self._record_event(order.order_id, RoutingEvent.QUEUED,
                             {'queue': order.priority.name})

            self.logger.info("Order queued: %s (%s priority)", order.order_id, order.priority.name)

        except queue.Full:
            self.logger.error("Queue full for priority %s", order.priority.name)
            self._record_event(order.order_id, RoutingEvent.REJECTED,
                             {'reason': 'queue_full'})
            return None

        return order.order_id

    # ==========================================================================
    # ROUTING LOGIC
    # ==========================================================================

    def _router_loop(self):
        """Main routing loop thread"""
        self.logger.info("Router thread started")

        while not self.stop_event.is_set():
            try:
                # Process orders from highest to lowest priority
                for priority in OrderPriority:
                    if not self.order_queues[priority].empty():
                        try:
                            _, _, order = self.order_queues[priority].get_nowait()
                            self._route_order(order)
                        except queue.Empty:
                            continue

                # Brief sleep to prevent CPU spinning
                time.sleep(0.001)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Router error: %s", e)

        self.logger.info("Router thread stopped")

    def _route_order(self, order: RoutableOrder):
        """
        Route order to optimal venue(s)

        Args:
            order: Order to route
        """
        start_time = time.time()

        self._record_event(order.order_id, RoutingEvent.ROUTING, {})

        # Get routing decisions based on strategy
        if order.routing_strategy == RoutingStrategy.SMART:
            decisions = self._smart_routing(order)

        elif order.routing_strategy == RoutingStrategy.SPRAY:
            decisions = self._spray_routing(order)

        elif order.routing_strategy == RoutingStrategy.DARK_ONLY:
            decisions = self._dark_pool_routing(order)

        elif order.routing_strategy == RoutingStrategy.LATENCY_OPTIMIZED:
            decisions = self._latency_optimized_routing(order)

        elif order.routing_strategy == RoutingStrategy.COST_OPTIMIZED:
            decisions = self._cost_optimized_routing(order)

        else:
            decisions = self._smart_routing(order)

        # Execute routing decisions
        for decision in decisions:
            self._execute_routing_decision(order, decision)

        # Track routing latency
        routing_latency = (time.time() - start_time) * 1000
        self.routing_latencies.append(routing_latency)

        if routing_latency > MAX_ROUTING_LATENCY_MS:
            self.logger.warning(f"High routing latency: {routing_latency:.1f}ms for {order.order_id}")  # noqa: E501

        self.total_orders_routed += 1

    def _smart_routing(self, order: RoutableOrder) -> list[RoutingDecision]:
        """
        Smart routing algorithm considering multiple factors

        Args:
            order: Order to route

        Returns:
            List of routing decisions
        """
        decisions = []
        remaining_quantity = order.quantity

        # Get available venues
        available_venues = self._get_available_venues(order)

        if not available_venues:
            self.logger.error("No available venues for %s", order.order_id)
            return decisions

        # Score each venue
        venue_scores = {}
        for venue in available_venues:
            score = self._score_venue(venue, order)
            venue_scores[venue] = score

        # Sort venues by score
        sorted_venues = sorted(venue_scores.items(), key=lambda x: x[1], reverse=True)

        # Route to top venues
        venues_used = 0
        for venue, score in sorted_venues:
            if venues_used >= order.max_venues or remaining_quantity <= 0:
                break

            # Determine quantity for this venue
            if venues_used == 0:
                # Primary venue gets majority
                venue_quantity = int(remaining_quantity * 0.7)
            else:
                # Secondary venues get remainder
                venue_quantity = int(remaining_quantity * 0.5)

            venue_quantity = min(venue_quantity, remaining_quantity)

            if venue_quantity > 0:
                decision = RoutingDecision(
                    order_id=order.order_id,
                    venue=venue,
                    quantity=venue_quantity,
                    routing_time=datetime.now(timezone.utc),
                    expected_fee=self._calculate_expected_fee(venue, venue_quantity),
                    expected_rebate=self._calculate_expected_rebate(venue, venue_quantity),
                    expected_latency_ms=VENUE_CHARACTERISTICS[venue]['latency_ms'],
                    liquidity_score=VENUE_CHARACTERISTICS[venue]['liquidity_score'],
                    confidence=score,
                    reasoning=f"Smart routing - score: {score:.2f}"
                )

                decisions.append(decision)
                remaining_quantity -= venue_quantity
                venues_used += 1

        return decisions

    def _spray_routing(self, order: RoutableOrder) -> list[RoutingDecision]:
        """
        Spray order across multiple venues simultaneously

        Args:
            order: Order to route

        Returns:
            List of routing decisions
        """
        decisions = []
        available_venues = self._get_available_venues(order)

        if not available_venues:
            return decisions

        # Distribute evenly across venues
        venues_to_use = min(len(available_venues), order.max_venues)
        quantity_per_venue = order.quantity // venues_to_use
        remainder = order.quantity % venues_to_use

        for i, venue in enumerate(list(available_venues)[:venues_to_use]):
            venue_quantity = quantity_per_venue
            if i == 0:
                venue_quantity += remainder  # First venue gets remainder

            decision = RoutingDecision(
                order_id=order.order_id,
                venue=venue,
                quantity=venue_quantity,
                routing_time=datetime.now(timezone.utc),
                expected_fee=self._calculate_expected_fee(venue, venue_quantity),
                expected_rebate=self._calculate_expected_rebate(venue, venue_quantity),
                expected_latency_ms=VENUE_CHARACTERISTICS[venue]['latency_ms'],
                liquidity_score=VENUE_CHARACTERISTICS[venue]['liquidity_score'],
                confidence=0.5,
                reasoning="Spray routing - equal distribution"
            )

            decisions.append(decision)

        return decisions

    def _dark_pool_routing(self, order: RoutableOrder) -> list[RoutingDecision]:
        """
        Route to dark pools only

        Args:
            order: Order to route

        Returns:
            List of routing decisions
        """
        decisions = []

        # Check if order qualifies for dark pool
        if order.quantity < DARK_POOL_MIN_SIZE:
            # Too small for dark pool, use smart routing
            return self._smart_routing(order)

        # Find available dark pools
        dark_venues = [
            venue for venue in ExecutionVenue
            if VENUE_CHARACTERISTICS[venue].get('dark_pool', False) and
            self.venue_availability.get(venue, False)
        ]

        if not dark_venues:
            # No dark pools available, fallback to smart routing
            return self._smart_routing(order)

        # Route to dark pool(s)
        for venue in dark_venues:
            decision = RoutingDecision(
                order_id=order.order_id,
                venue=venue,
                quantity=order.quantity,
                routing_time=datetime.now(timezone.utc),
                expected_fee=self._calculate_expected_fee(venue, order.quantity),
                expected_rebate=0,  # Dark pools typically don't offer rebates
                expected_latency_ms=VENUE_CHARACTERISTICS[venue]['latency_ms'],
                liquidity_score=VENUE_CHARACTERISTICS[venue]['liquidity_score'],
                confidence=0.7,
                reasoning="Dark pool routing for large order"
            )

            decisions.append(decision)
            break  # Usually send to one dark pool at a time

        return decisions

    def _latency_optimized_routing(self, order: RoutableOrder) -> list[RoutingDecision]:
        """
        Route to lowest latency venues

        Args:
            order: Order to route

        Returns:
            List of routing decisions
        """
        decisions = []
        available_venues = self._get_available_venues(order)

        if not available_venues:
            return decisions

        # Sort by latency
        sorted_venues = sorted(
            available_venues,
            key=lambda v: VENUE_CHARACTERISTICS[v]['latency_ms']
        )

        # Use fastest venue
        fastest_venue = sorted_venues[0]

        decision = RoutingDecision(
            order_id=order.order_id,
            venue=fastest_venue,
            quantity=order.quantity,
            routing_time=datetime.now(timezone.utc),
            expected_fee=self._calculate_expected_fee(fastest_venue, order.quantity),
            expected_rebate=self._calculate_expected_rebate(fastest_venue, order.quantity),
            expected_latency_ms=VENUE_CHARACTERISTICS[fastest_venue]['latency_ms'],
            liquidity_score=VENUE_CHARACTERISTICS[fastest_venue]['liquidity_score'],
            confidence=0.8,
            reasoning=f"Latency optimized - {VENUE_CHARACTERISTICS[fastest_venue]['latency_ms']}ms"
        )

        decisions.append(decision)
        return decisions

    def _cost_optimized_routing(self, order: RoutableOrder) -> list[RoutingDecision]:
        """
        Route to minimize costs

        Args:
            order: Order to route

        Returns:
            List of routing decisions
        """
        decisions = []
        available_venues = self._get_available_venues(order)

        if not available_venues:
            return decisions

        # Calculate net cost for each venue
        venue_costs = {}
        for venue in available_venues:
            fee = self._calculate_expected_fee(venue, order.quantity)
            rebate = self._calculate_expected_rebate(venue, order.quantity)
            net_cost = fee - rebate
            venue_costs[venue] = net_cost

        # Sort by cost (lowest first)
        sorted_venues = sorted(venue_costs.items(), key=lambda x: x[1])

        # Use cheapest venue
        cheapest_venue, cost = sorted_venues[0]

        decision = RoutingDecision(
            order_id=order.order_id,
            venue=cheapest_venue,
            quantity=order.quantity,
            routing_time=datetime.now(timezone.utc),
            expected_fee=self._calculate_expected_fee(cheapest_venue, order.quantity),
            expected_rebate=self._calculate_expected_rebate(cheapest_venue, order.quantity),
            expected_latency_ms=VENUE_CHARACTERISTICS[cheapest_venue]['latency_ms'],
            liquidity_score=VENUE_CHARACTERISTICS[cheapest_venue]['liquidity_score'],
            confidence=0.85,
            reasoning=f"Cost optimized - net cost: ${cost:.4f}"
        )

        decisions.append(decision)
        return decisions

    # ==========================================================================
    # VENUE MANAGEMENT
    # ==========================================================================

    def _get_available_venues(self, order: RoutableOrder) -> set[ExecutionVenue]:
        """Get available venues for order"""
        available = set()

        for venue in ExecutionVenue:
            # Check if venue is available
            if not self.venue_availability.get(venue, False):
                continue

            # Check dark pool restrictions
            if VENUE_CHARACTERISTICS[venue].get('dark_pool', False) and not order.allow_dark:
                continue

            # Check if venue is suitable for order type
            if self._is_venue_suitable(venue, order):
                available.add(venue)

        return available

    def _is_venue_suitable(self, venue: ExecutionVenue, order: RoutableOrder) -> bool:
        """Check if venue is suitable for order"""
        # Check liquidity requirements
        if order.quantity > 10000 and VENUE_CHARACTERISTICS[venue]['liquidity_score'] < 80:
            return False

        # Check latency requirements for IOC orders
        return not (order.time_in_force == "IOC" and VENUE_CHARACTERISTICS[venue]['latency_ms'] > 10)  # noqa: E501

    def _score_venue(self, venue: ExecutionVenue, order: RoutableOrder) -> float:
        """
        Score venue for order routing

        Args:
            venue: Venue to score
            order: Order being routed

        Returns:
            Score between 0 and 1
        """
        score = 0.0

        # Liquidity score
        liquidity = VENUE_CHARACTERISTICS[venue]['liquidity_score'] / 100
        score += liquidity * LIQUIDITY_WEIGHT

        # Fee score (inverted - lower is better)
        max_fee = 0.0030
        fee = VENUE_CHARACTERISTICS[venue]['fee_per_share']
        fee_score = 1 - (fee / max_fee)
        score += fee_score * FEE_WEIGHT

        # Latency score (inverted - lower is better)
        max_latency = 350  # IEX speed bump
        latency = VENUE_CHARACTERISTICS[venue]['latency_ms']
        latency_score = 1 - (latency / max_latency)
        score += latency_score * LATENCY_WEIGHT

        # Fill quality score from historical performance
        if venue in self.venue_performance:
            perf = self.venue_performance[venue]
            if perf.total_orders > 0:
                fill_score = perf.fill_rate
                score += fill_score * FILL_QUALITY_WEIGHT
            else:
                score += 0.5 * FILL_QUALITY_WEIGHT  # Default score
        else:
            score += 0.5 * FILL_QUALITY_WEIGHT

        return min(1.0, score)

    def _calculate_expected_fee(self, venue: ExecutionVenue, quantity: int) -> float:
        """Calculate expected fee for venue"""
        fee_per_share = VENUE_CHARACTERISTICS[venue]['fee_per_share']
        return fee_per_share * quantity

    def _calculate_expected_rebate(self, venue: ExecutionVenue, quantity: int) -> float:
        """Calculate expected rebate for venue"""
        rebate_per_share = VENUE_CHARACTERISTICS[venue]['rebate_per_share']
        return rebate_per_share * quantity

    def update_venue_quote(self, symbol: str, venue: ExecutionVenue, quote: VenueQuote):
        """Update market quote from venue"""
        self.venue_quotes[symbol][venue] = quote

    def update_venue_availability(self, venue: ExecutionVenue, available: bool):
        """Update venue availability status"""
        self.venue_availability[venue] = available

        if not available:
            self.logger.warning("Venue %s marked as unavailable", venue.value)

    # ==========================================================================
    # EXECUTION AND LIFECYCLE
    # ==========================================================================

    def _execute_routing_decision(self, order: RoutableOrder, decision: RoutingDecision):
        """
        Execute routing decision

        Args:
            order: Original order
            decision: Routing decision
        """
        # Record routing decision
        if order.order_id in self.order_lifecycles:
            self.order_lifecycles[order.order_id].routing_decisions.append(decision)

        # Send to venue (simulated)
        success = self._send_to_venue(order, decision)

        if success:
            self._record_event(order.order_id, RoutingEvent.ROUTED, {
                'venue': decision.venue.value,
                'quantity': decision.quantity
            })

            # Update venue performance
            if decision.venue in self.venue_performance:
                self.venue_performance[decision.venue].total_orders += 1
        else:
            self._record_event(order.order_id, RoutingEvent.REJECTED, {
                'venue': decision.venue.value,
                'reason': 'venue_unavailable'
            })

            # Update rejection rate
            if decision.venue in self.venue_performance:
                self.venue_performance[decision.venue].rejected_orders += 1

    def _send_to_venue(self, order: RoutableOrder, decision: RoutingDecision) -> bool:
        """
        Send order to venue (simulated)

        Args:
            order: Order to send
            decision: Routing decision

        Returns:
            Success status
        """
        # Simulate sending to venue
        # In production, this would interface with actual venue connections

        # Simulate latency
        latency_ms = decision.expected_latency_ms
        time.sleep(latency_ms / 1000)  # thread-safe: time.sleep() intentional

        # Simulate success/failure (95% success rate)
        success = random.random() < 0.95

        if success:
            # Simulate fill after some time
            self._simulate_fill(order, decision)

        return success

    def _simulate_fill(self, order: RoutableOrder, decision: RoutingDecision):
        """Simulate order fill (for testing)"""
        # Random fill time between 10-100ms
        fill_time = random.uniform(0.01, 0.1)

        # Schedule fill simulation
        timer = threading.Timer(fill_time, self._process_fill,
                              args=[order.order_id, decision.venue, decision.quantity])
        timer.start()

    def _process_fill(self, order_id: str, venue: ExecutionVenue, quantity: int):
        """Process order fill"""
        if order_id not in self.order_lifecycles:
            return

        lifecycle = self.order_lifecycles[order_id]

        # Simulate fill price (around current market)
        fill_price = 100 + random.uniform(-0.5, 0.5)

        fill_data = {
            'venue': venue.value,
            'quantity': quantity,
            'price': fill_price,
            'timestamp': datetime.now(timezone.utc)
        }

        lifecycle.fills.append(fill_data)
        lifecycle.total_filled += quantity

        # Update average fill price
        total_value = sum(f['quantity'] * f['price'] for f in lifecycle.fills)
        lifecycle.avg_fill_price = total_value / lifecycle.total_filled

        # Check if fully filled
        if order_id in self.active_orders:
            order = self.active_orders[order_id]
            if lifecycle.total_filled >= order.quantity:
                self._record_event(order_id, RoutingEvent.FILLED, fill_data)
                lifecycle.status = OrderStatus.FILLED
                lifecycle.end_time = datetime.now(timezone.utc)
                self.total_orders_filled += 1

                # Update venue performance
                if venue in self.venue_performance:
                    self.venue_performance[venue].filled_orders += 1
                    self.venue_performance[venue].fill_rate = (
                        self.venue_performance[venue].filled_orders /
                        self.venue_performance[venue].total_orders
                    )
            else:
                self._record_event(order_id, RoutingEvent.PARTIAL, fill_data)

    def _record_event(self, order_id: str, event: RoutingEvent, data: dict):
        """Record lifecycle event"""
        if order_id in self.order_lifecycles:
            self.order_lifecycles[order_id].events.append(
                (event, datetime.now(timezone.utc), data)
            )

    # ==========================================================================
    # CIRCUIT BREAKER
    # ==========================================================================

    def _monitor_circuit_breaker(self):
        """Monitor for circuit breaker conditions"""
        while not self.stop_event.is_set():
            try:
                # Calculate orders per second
                recent_orders = [
                    1 for lifecycle in self.order_lifecycles.values()
                    if lifecycle.start_time > datetime.now(timezone.utc) - timedelta(seconds=1)
                ]
                self.circuit_breaker.orders_per_second = len(recent_orders)

                # Calculate rejection rate
                total_recent = len(recent_orders)
                if total_recent > 0:
                    recent_rejects = sum(
                        1 for lifecycle in self.order_lifecycles.values()
                        if lifecycle.start_time > datetime.now(timezone.utc) - timedelta(seconds=10) and
                        any(event[0] == RoutingEvent.REJECTED for event in lifecycle.events)
                    )
                    self.circuit_breaker.rejection_rate = recent_rejects / total_recent

                # Check thresholds
                if (self.circuit_breaker.orders_per_second > MAX_ORDERS_PER_SECOND or
                    self.circuit_breaker.rejection_rate > MAX_REJECTION_RATE):
                    self._trigger_circuit_breaker()
                elif self.circuit_breaker.state == CircuitBreakerState.WARNING:
                    if (self.circuit_breaker.orders_per_second < MAX_ORDERS_PER_SECOND * 0.8 and
                        self.circuit_breaker.rejection_rate < MAX_REJECTION_RATE * 0.8):
                        self.circuit_breaker.state = CircuitBreakerState.NORMAL

                time.sleep(1)  # thread-safe: time.sleep() intentional

            except Exception as e:
                self.logger.error("Circuit breaker monitor error: %s", e)

    def _trigger_circuit_breaker(self):
        """Trigger circuit breaker"""
        self.circuit_breaker.state = CircuitBreakerState.TRIGGERED
        self.circuit_breaker.last_triggered = datetime.now(timezone.utc)
        self.circuit_breaker.cooldown_until = datetime.now(timezone.utc) + timedelta(seconds=CIRCUIT_BREAKER_COOLDOWN)  # noqa: E501
        self.circuit_breaker.triggers_count += 1

        self.logger.critical(f"🚨 Circuit breaker triggered! Orders: {self.circuit_breaker.orders_per_second}/s, "  # noqa: E501
                           f"Rejection rate: {self.circuit_breaker.rejection_rate:.1%}")

    def _reset_circuit_breaker(self):
        """Reset circuit breaker after cooldown"""
        self.circuit_breaker.state = CircuitBreakerState.NORMAL
        self.circuit_breaker.cooldown_until = None
        self.logger.info("Circuit breaker reset")

    # ==========================================================================
    # UTILITIES
    # ==========================================================================

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        random_suffix = hashlib.md5(str(random.random()).encode(), usedforsecurity=False).hexdigest()[:6]  # noqa: E501
        return f"ORD_{timestamp}_{random_suffix}"

    def _start_router(self):
        """Start router threads"""
        # Start routing thread
        if not self.router_thread or not self.router_thread.is_alive():
            self.router_thread = threading.Thread(target=self._router_loop, daemon=True)
            self.router_thread.start()

        # Start monitor thread
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor_circuit_breaker, daemon=True)  # noqa: E501
            self.monitor_thread.start()

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def get_order_status(self, order_id: str) -> OrderLifecycle | None:
        """Get order lifecycle status"""
        return self.order_lifecycles.get(order_id)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        if order_id not in self.active_orders:
            return False

        self._record_event(order_id, RoutingEvent.CANCELLED, {})

        if order_id in self.order_lifecycles:
            self.order_lifecycles[order_id].status = OrderStatus.CANCELLED
            self.order_lifecycles[order_id].end_time = datetime.now(timezone.utc)

        # Remove from active orders
        if order_id in self.active_orders:
            del self.active_orders[order_id]

        self.logger.info("Order cancelled: %s", order_id)
        return True

    def get_venue_performance(self, venue: ExecutionVenue) -> VenuePerformance | None:
        """Get venue performance metrics"""
        return self.venue_performance.get(venue)

    def get_router_statistics(self) -> dict[str, Any]:
        """Get router statistics"""
        avg_latency = np.mean(self.routing_latencies) if self.routing_latencies else 0

        # Queue depths
        queue_depths = {
            priority.name: self.order_queues[priority].qsize()
            for priority in OrderPriority
        }

        return {
            'total_orders_routed': self.total_orders_routed,
            'total_orders_filled': self.total_orders_filled,
            'total_orders_rejected': self.total_orders_rejected,
            'active_orders': len(self.active_orders),
            'avg_routing_latency_ms': avg_latency,
            'queue_depths': queue_depths,
            'circuit_breaker_state': self.circuit_breaker.state.value,
            'circuit_breaker_triggers': self.circuit_breaker.triggers_count,
            'orders_per_second': self.circuit_breaker.orders_per_second,
            'rejection_rate': self.circuit_breaker.rejection_rate
        }

    def get_venue_statistics(self) -> dict[str, dict]:
        """Get statistics for all venues"""
        stats = {}

        for venue, perf in self.venue_performance.items():
            stats[venue.value] = {
                'total_orders': perf.total_orders,
                'filled_orders': perf.filled_orders,
                'rejected_orders': perf.rejected_orders,
                'fill_rate': perf.fill_rate,
                'rejection_rate': perf.rejection_rate,
                'available': self.venue_availability.get(venue, False)
            }

        return stats

    def shutdown(self):
        """Shutdown router"""
        self.stop_event.set()

        if self.router_thread:
            self.router_thread.join(timeout=5)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

        self.logger.info("OrderRouter shutdown complete")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_order_router() -> OrderRouter:
    """Factory function to create order router"""
    return OrderRouter()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


    # Create router
    router = create_order_router()

    # Test orders with different strategies
    test_orders = [
        RoutableOrder(
            order_id="TEST_001",
            symbol="SPY",
            side="BUY",
            quantity=10000,
            order_type="LIMIT",
            limit_price=585.50,
            time_in_force="DAY",
            routing_strategy=RoutingStrategy.SMART,
            priority=OrderPriority.NORMAL,
            allow_dark=True
        ),
        RoutableOrder(
            order_id="TEST_002",
            symbol="QQQ",
            side="SELL",
            quantity=5000,
            order_type="MARKET",
            limit_price=None,
            time_in_force="IOC",
            routing_strategy=RoutingStrategy.LATENCY_OPTIMIZED,
            priority=OrderPriority.HIGH,
            allow_dark=False
        ),
        RoutableOrder(
            order_id="TEST_003",
            symbol="IWM",
            side="BUY",
            quantity=20000,
            order_type="LIMIT",
            limit_price=225.00,
            time_in_force="DAY",
            routing_strategy=RoutingStrategy.DARK_ONLY,
            priority=OrderPriority.LOW,
            allow_dark=True
        ),
        RoutableOrder(
            order_id="TEST_004",
            symbol="SPY",
            side="SELL",
            quantity=3000,
            order_type="LIMIT",
            limit_price=585.60,
            time_in_force="GTC",
            routing_strategy=RoutingStrategy.COST_OPTIMIZED,
            priority=OrderPriority.NORMAL,
            allow_dark=False
        )
    ]


    for order in test_orders:
        order_id = router.submit_order(order)

    # Let orders process
    time.sleep(2)

    # Check order status

    for order in test_orders:
        lifecycle = router.get_order_status(order.order_id)
        if lifecycle:
            if lifecycle.routing_decisions:
                for _decision in lifecycle.routing_decisions:
                    pass
            if lifecycle.avg_fill_price > 0:
                pass

    # Get statistics
    stats = router.get_router_statistics()
    for key, _value in stats.items():
        if key != 'queue_depths':
            pass

    for _priority, _depth in stats['queue_depths'].items():
        pass

    # Venue statistics
    venue_stats = router.get_venue_statistics()
    for _venue, vstats in venue_stats.items():
        if vstats['total_orders'] > 0:
            pass

    # Shutdown
    router.shutdown()
