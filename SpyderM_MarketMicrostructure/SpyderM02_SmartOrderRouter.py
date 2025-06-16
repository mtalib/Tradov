#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderM02_SmartOrderRouter.py
Group: M (Market Microstructure)
Purpose: Intelligent order routing across multiple venues

Description:
This module implements smart order routing across 16+ trading
    venues to achieve optimal execution. Features include venue scoring,
    hidden liquidity detection, advanced order types (Iceberg, VWAP),
    and adaptive algorithms targeting 1-2 cent price improvement.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import asyncio
import logging
import pandas as pd
import numpy as np
import uuid

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class OrderType(Enum):
    """Smart order types available."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    MIDPOINT = "MIDPOINT"
    ICEBERG = "ICEBERG"
    VWAP = "VWAP"
    TWAP = "TWAP"
    ADAPTIVE = "ADAPTIVE"
    SWEEP = "SWEEP"
    PEG = "PEG"
class Venue(Enum):
    """Trading venues for options."""
    CBOE = "CBOE"
    ISE = "ISE"
    PHLX = "PHLX"
    BOX = "BOX"
    MIAX = "MIAX"
    NASDAQ = "NASDAQ"
    NYSE_ARCA = "NYSE_ARCA"
    C2 = "C2"
    GEMX = "GEMX"
    MERCURY = "MERCURY"
    PEARL = "PEARL"
    EDGX = "EDGX"
    BZX = "BZX"
    MEMX = "MEMX"
    LTSE = "LTSE"
    IEX = "IEX"
@dataclass
class VenueQuote:
    """Quote from a specific venue."""
    venue: Venue
    bid_price: float
    ask_price: float
    bid_size: int
    ask_size: int
    hidden_liquidity_probability: float
    average_fill_time: float  # milliseconds
    maker_rebate: float
    taker_fee: float
    timestamp: datetime
@dataclass
class RoutingDecision:
    """Smart routing decision for order."""
    primary_venue: Venue
    venue_allocations: Dict[Venue, float]  # Venue -> percentage
    order_type: OrderType
    limit_price: Optional[float]
    time_horizon: int  # seconds
    expected_fill_price: float
    expected_fill_time: float  # milliseconds
    price_improvement: float
    hidden_liquidity_targets: List[Venue]
    special_instructions: List[str]
@dataclass
class ExecutionReport:
    """Execution quality report."""
    order_id: str
    requested_quantity: int
    filled_quantity: int
    average_fill_price: float
    benchmark_price: float  # Arrival price or midpoint
    slippage_bps: float
    price_improvement: float
    fill_rate: float
    execution_time_ms: float
    venues_used: List[Venue]
    hidden_liquidity_captured: int
class SpyderSmartOrderRouter:
    """
    Implements institutional-grade smart order routing.
    Features:
    - Multi-venue quote aggregation
    - Hidden liquidity detection
    - Optimal venue selection
    - Advanced order types (Iceberg, VWAP, etc.)
    - Real-time execution quality monitoring
    """
    def __init__(self, market_data=None, order_manager=None):
        """Initialize smart order router."""
        self.market_data = market_data
        self.order_manager = order_manager
        # Venue characteristics (from market microstructure research)
        self.VENUE_CHARACTERISTICS = {
            Venue.CBOE: {
                'market_share': 0.24,
                'avg_spread': 0.02,
                'hidden_ratio': 0.15,
                'fill_time_ms': 12,
                'maker_rebate': -0.0023,
                'taker_fee': 0.0047
            },
            Venue.ISE: {
                'market_share': 0.18,
                'avg_spread': 0.025,
                'hidden_ratio': 0.12,
                'fill_time_ms': 15,
                'maker_rebate': -0.0020,
                'taker_fee': 0.0045
            },
            Venue.PHLX: {
                'market_share': 0.16,
                'avg_spread': 0.022,
                'hidden_ratio': 0.18,
                'fill_time_ms': 14,
                'maker_rebate': -0.0022,
                'taker_fee': 0.0046
            },
            Venue.BOX: {
                'market_share': 0.08,
                'avg_spread': 0.015,  # Penny pilot advantage
                'hidden_ratio': 0.20,
                'fill_time_ms': 18,
                'maker_rebate': -0.0025,
                'taker_fee': 0.0040
            },
            Venue.MIAX: {
                'market_share': 0.12,
                'avg_spread': 0.020,
                'hidden_ratio': 0.10,
                'fill_time_ms': 10,  # Fast
                'maker_rebate': -0.0018,
                'taker_fee': 0.0048
            }
            # Additional venues with similar characteristics
        }
        # Execution algorithm parameters
        self.ALGO_PARAMS = {
            'iceberg': {
                'display_ratio': 0.2,  # 20% displayed
                'min_display': 10,
                'max_display': 100,
                'randomize': True
            },
            'vwap': {
                'participation_rate': 0.15,  # 15% of volume
                'min_slice': 10,
                'max_slice': 500,
                'urgency_factor': 1.2
            },
            'adaptive': {
                'initial_aggressiveness': 0.5,
                'learning_rate': 0.1,
                'max_aggressiveness': 0.9,
                'min_aggressiveness': 0.1
            }
        }
        # Performance targets
        self.PERFORMANCE_TARGETS = {
            'fill_rate_30s': 0.90,      # 90% within 30 seconds
            'slippage_small': 10,        # 10 bps for <$1M
            'slippage_large': 20,        # 20 bps for >$1M
            'price_improvement': 0.01,   # 1 cent average
            'hidden_capture': 0.25       # 25% of hidden liquidity
        }
        # State tracking
        self.active_orders = {}
        self.execution_history = []
        self.venue_performance = defaultdict(lambda: {
            'fills': 0,
            'volume': 0,
            'improvement': 0,
            'failures': 0
        })
    async def route_order(self, symbol: str, quantity: int, side: str,
                         urgency: str = 'NORMAL') -> RoutingDecision:
        """
        Determine optimal routing for an order.
        Args:
            symbol: Option symbol
            quantity: Order quantity
            side: BUY or SELL
            urgency: IMMEDIATE, HIGH, NORMAL, LOW
        Returns:
            Routing decision with venue allocations
        """
        # Get quotes from all venues
        venue_quotes = await self._aggregate_venue_quotes(symbol)
        # Analyze order characteristics
        order_profile = self._analyze_order_profile(
            symbol, quantity, side, urgency
        )
        # Determine optimal order type
        order_type = self._select_order_type(order_profile, venue_quotes)
        # Calculate venue allocations
        allocations = self._calculate_venue_allocations(
            venue_quotes, order_profile, order_type
        )
        # Detect hidden liquidity opportunities
        hidden_targets = self._detect_hidden_liquidity(
            venue_quotes, order_profile
        )
        # Calculate expected execution metrics
        execution_metrics = self._calculate_execution_metrics(
            venue_quotes, allocations, order_profile
        )
        # Build routing decision
        decision = RoutingDecision(
            primary_venue=allocations[0][0],  # Top venue
            venue_allocations={v: pct for v, pct in allocations},
            order_type=order_type,
            limit_price=execution_metrics['limit_price'],
            time_horizon=self._urgency_to_horizon(urgency),
            expected_fill_price=execution_metrics['expected_price'],
            expected_fill_time=execution_metrics['expected_time'],
            price_improvement=execution_metrics['improvement'],
            hidden_liquidity_targets=hidden_targets,
            special_instructions=self._generate_instructions(order_profile)
        )
        return decision
    async def _aggregate_venue_quotes(self, symbol: str) -> List[VenueQuote]:
        """Aggregate quotes from all available venues."""
        quotes = []
        # In production, this would query real venues
        # For demo, generate realistic quotes based on characteristics
        base_bid = 2.50
        base_ask = 2.52
        for venue, chars in self.VENUE_CHARACTERISTICS.items():
            # Simulate realistic quote variations
            spread_var = np.random.normal(0, 0.002)
            size_var = np.random.uniform(0.8, 1.2)
            quote = VenueQuote(
                venue=venue,
                bid_price=base_bid - chars['avg_spread']/2 + spread_var,
                ask_price=base_ask + chars['avg_spread']/2 + spread_var,
                bid_size=int(1000 * chars['market_share'] * size_var),
                ask_size=int(1000 * chars['market_share'] * size_var),
                hidden_liquidity_probability=chars['hidden_ratio'],
                average_fill_time=chars['fill_time_ms'],
                maker_rebate=chars['maker_rebate'],
                taker_fee=chars['taker_fee'],
                timestamp=datetime.now()
            )
            quotes.append(quote)
        return quotes
    def _analyze_order_profile(self, symbol: str, quantity: int,
                              side: str, urgency: str) -> Dict[str, Any]:
        """Analyze order characteristics for routing optimization."""
        # Calculate order size metrics
        avg_daily_volume = self._get_adv(symbol)
        order_percentage = quantity / avg_daily_volume if avg_daily_volume > 0 else 0
        # Determine order profile
        profile = {
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'urgency': urgency,
            'size_category': self._categorize_size(quantity),
            'adv_percentage': order_percentage,
            'is_large': order_percentage > 0.05,  # >5% of ADV
            'requires_iceberg': quantity > 500,
            'expected_market_impact': self._estimate_market_impact(order_percentage),
            'optimal_slice_size': self._calculate_optimal_slice(quantity, avg_daily_volume)
        }
        return profile
    def _select_order_type(self, profile: Dict[str, Any],
                          quotes: List[VenueQuote]) -> OrderType:
        """Select optimal order type based on profile and market conditions."""
        # Immediate orders
        if profile['urgency'] == 'IMMEDIATE':
            if profile['is_large']:
                return OrderType.SWEEP  # Sweep all venues
            else:
                return OrderType.MARKET
        # Large orders requiring algorithms
        if profile['requires_iceberg']:
            return OrderType.ICEBERG
        # Time-sensitive but not immediate
        if profile['urgency'] == 'HIGH':
            return OrderType.ADAPTIVE
        # Normal orders - optimize for price
        best_spread = min(q.ask_price - q.bid_price for q in quotes)
        if best_spread <= 0.02:  # Tight spread
            return OrderType.MIDPOINT
        else:
            return OrderType.LIMIT
    def _calculate_venue_allocations(self, quotes: List[VenueQuote],
                                   profile: Dict[str, Any],
                                   order_type: OrderType) -> List[Tuple[Venue, float]]:
        """Calculate optimal allocation across venues."""
        allocations = []
        # Score each venue
        venue_scores = {}
        for quote in quotes:
            score = self._score_venue(quote, profile, order_type)
            venue_scores[quote.venue] = score
        # Sort by score
        sorted_venues = sorted(venue_scores.items(), key=lambda x: x[1], reverse=True)
        # Allocate based on order type
        if order_type == OrderType.SWEEP:
            # Use all venues with available liquidity
            total_liquidity = sum(q.ask_size if profile['side'] == 'BUY' 
                                else q.bid_size for q in quotes)
            for quote in quotes:
                size = quote.ask_size if profile['side'] == 'BUY' else quote.bid_size
                if size > 0:
                    allocations.append((quote.venue, size / total_liquidity))
        elif order_type in [OrderType.ICEBERG, OrderType.VWAP]:
            # Multi-venue allocation weighted by score
            total_score = sum(venue_scores.values())
            for venue, score in sorted_venues[:5]:  # Top 5 venues
                if score > 0:
                    allocations.append((venue, score / total_score))
        else:
            # Single venue for simple orders
            if sorted_venues:
                allocations.append((sorted_venues[0][0], 1.0))
        return allocations
    def _score_venue(self, quote: VenueQuote, profile: Dict[str, Any],
                    order_type: OrderType) -> float:
        """Score a venue for order routing."""
        score = 100.0
        # Price score (most important)
        if profile['side'] == 'BUY':
            price_score = (2.55 - quote.ask_price) * 100  # Lower is better
        else:
            price_score = (quote.bid_price - 2.45) * 100  # Higher is better
        score += price_score * 2.0
        # Size score
        available_size = quote.ask_size if profile['side'] == 'BUY' else quote.bid_size
        size_ratio = min(available_size / profile['quantity'], 1.0)
        score += size_ratio * 30
        # Speed score (important for urgent orders)
        if profile['urgency'] in ['IMMEDIATE', 'HIGH']:
            speed_score = (30 - quote.average_fill_time) * 2
            score += speed_score
        # Hidden liquidity score (for large orders)
        if profile['is_large']:
            hidden_score = quote.hidden_liquidity_probability * 50
            score += hidden_score
        # Fee/rebate score
        if order_type in [OrderType.LIMIT, OrderType.MIDPOINT]:
            fee_score = -quote.maker_rebate * 1000  # Rebate is negative
        else:
            fee_score = -quote.taker_fee * 1000
        score += fee_score
        # Venue reliability (from historical performance)
        venue_perf = self.venue_performance[quote.venue]
        if venue_perf['fills'] > 0:
            success_rate = 1 - (venue_perf['failures'] / venue_perf['fills'])
            score += success_rate * 20
        return max(score, 0)
    def _detect_hidden_liquidity(self, quotes: List[VenueQuote],
                               profile: Dict[str, Any]) -> List[Venue]:
        """Detect venues likely to have hidden liquidity."""
        hidden_targets = []
        for quote in quotes:
            # High hidden liquidity probability
            if quote.hidden_liquidity_probability > 0.15:
                # Size imbalance suggesting hidden orders
                size_imbalance = abs(quote.bid_size - quote.ask_size) / max(quote.bid_size, quote.ask_size)
                if size_imbalance > 0.5:
                    hidden_targets.append(quote.venue)
                    continue
                # Tight spread suggesting competition
                spread = quote.ask_price - quote.bid_price
                if spread <= 0.01 and profile['is_large']:
                    hidden_targets.append(quote.venue)
        return hidden_targets[:3]  # Top 3 venues
    def _calculate_execution_metrics(self, quotes: List[VenueQuote],
                                   allocations: List[Tuple[Venue, float]],
                                   profile: Dict[str, Any]) -> Dict[str, float]:
        """Calculate expected execution metrics."""
        # Calculate weighted average fill price
        expected_price = 0
        expected_time = 0
        allocation_dict = dict(allocations)
        for quote in quotes:
            if quote.venue in allocation_dict:
                weight = allocation_dict[quote.venue]
                if profile['side'] == 'BUY':
                    price = quote.ask_price
                else:
                    price = quote.bid_price
                expected_price += price * weight
                expected_time += quote.average_fill_time * weight
        # Calculate midpoint for comparison
        best_bid = max(q.bid_price for q in quotes)
        best_ask = min(q.ask_price for q in quotes)
        midpoint = (best_bid + best_ask) / 2
        # Calculate price improvement
        if profile['side'] == 'BUY':
            improvement = best_ask - expected_price
        else:
            improvement = expected_price - best_bid
        # Determine limit price
        if profile['side'] == 'BUY':
            limit_price = expected_price + 0.02  # 2 cents above expected
        else:
            limit_price = expected_price - 0.02  # 2 cents below expected
        return {
            'expected_price': expected_price,
            'expected_time': expected_time,
            'improvement': max(improvement, 0),
            'limit_price': limit_price,
            'midpoint': midpoint
        }
    def _urgency_to_horizon(self, urgency: str) -> int:
        """Convert urgency to time horizon in seconds."""
        horizons = {
            'IMMEDIATE': 5,
            'HIGH': 30,
            'NORMAL': 300,  # 5 minutes
            'LOW': 900      # 15 minutes
        }
        return horizons.get(urgency, 300)
    def _generate_instructions(self, profile: Dict[str, Any]) -> List[str]:
        """Generate special routing instructions."""
        instructions = []
        # Large order instructions
        if profile['is_large']:
            instructions.append("MINIMIZE_MARKET_IMPACT")
            instructions.append("SEEK_HIDDEN_LIQUIDITY")
        # Urgent order instructions
        if profile['urgency'] == 'IMMEDIATE':
            instructions.append("AGGRESSIVE_PRICING")
            instructions.append("ACCEPT_LIQUIDITY_FEES")
        # Iceberg instructions
        if profile['requires_iceberg']:
            instructions.append(f"DISPLAY_SIZE:{profile['optimal_slice_size']}")
            instructions.append("RANDOMIZE_DISPLAY")
        return instructions
    async def execute_with_algo(self, routing: RoutingDecision,
                              quantity: int, side: str) -> ExecutionReport:
        """Execute order using selected algorithm."""
        order_id = str(uuid.uuid4())
        start_time = datetime.now()
        # Track order
        self.active_orders[order_id] = {
            'routing': routing,
            'quantity': quantity,
            'side': side,
            'filled': 0,
            'fills': []
        }
        try:
            # Execute based on order type
            if routing.order_type == OrderType.ICEBERG:
                result = await self._execute_iceberg(order_id, routing, quantity, side)
            elif routing.order_type == OrderType.SWEEP:
                result = await self._execute_sweep(order_id, routing, quantity, side)
            elif routing.order_type == OrderType.ADAPTIVE:
                result = await self._execute_adaptive(order_id, routing, quantity, side)
            else:
                result = await self._execute_simple(order_id, routing, quantity, side)
            # Calculate execution metrics
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            report = ExecutionReport(
                order_id=order_id,
                requested_quantity=quantity,
                filled_quantity=result['filled'],
                average_fill_price=result['avg_price'],
                benchmark_price=routing.expected_fill_price,
                slippage_bps=self._calculate_slippage(
                    result['avg_price'],
                    routing.expected_fill_price,
                    side
                ),
                price_improvement=result.get('improvement', 0),
                fill_rate=result['filled'] / quantity,
                execution_time_ms=execution_time,
                venues_used=result['venues'],
                hidden_liquidity_captured=result.get('hidden_captured', 0)
            )
            # Update venue performance
            self._update_venue_performance(report)
            # Store execution history
            self.execution_history.append(report)
            return report
        finally:
            # Clean up
            if order_id in self.active_orders:
                del self.active_orders[order_id]
    async def _execute_iceberg(self, order_id: str, routing: RoutingDecision,
                             quantity: int, side: str) -> Dict[str, Any]:
        """Execute iceberg order algorithm."""
        params = self.ALGO_PARAMS['iceberg']
        filled = 0
        fills = []
        venues_used = set()
        hidden_captured = 0
        # Calculate display size
        display_size = max(
            params['min_display'],
            min(params['max_display'], int(quantity * params['display_ratio']))
        )
        # Execute in slices
        while filled < quantity:
            remaining = quantity - filled
            slice_size = min(display_size, remaining)
            # Randomize display size if configured
            if params['randomize']:
                slice_size = int(slice_size * np.random.uniform(0.8, 1.2))
            # Route slice to venues
            for venue, allocation in routing.venue_allocations.items():
                if allocation > 0 and filled < quantity:
                    venue_size = int(slice_size * allocation)
                    if venue_size > 0:
                        # Simulate execution
                        fill = await self._simulate_fill(
                            venue, venue_size, side, routing.limit_price
                        )
                        if fill['filled'] > 0:
                            fills.append(fill)
                            filled += fill['filled']
                            venues_used.add(venue)
                            # Check for hidden liquidity
                            if fill['filled'] > venue_size * 1.1:
                                hidden_captured += fill['filled'] - venue_size
            # Brief pause between slices
            await asyncio.sleep(0.1)
        # Calculate average price
        total_value = sum(f['filled'] * f['price'] for f in fills)
        avg_price = total_value / filled if filled > 0 else 0
        return {
            'filled': filled,
            'avg_price': avg_price,
            'venues': list(venues_used),
            'hidden_captured': hidden_captured,
            'improvement': self._calculate_improvement(fills, side)
        }
    async def _execute_sweep(self, order_id: str, routing: RoutingDecision,
                           quantity: int, side: str) -> Dict[str, Any]:
        """Execute sweep order across all venues."""
        filled = 0
        fills = []
        venues_used = set()
        # Hit all venues simultaneously
        tasks = []
        for venue, allocation in routing.venue_allocations.items():
            if allocation > 0:
                venue_qty = int(quantity * allocation)
                if venue_qty > 0:
                    task = self._simulate_fill(
                        venue, venue_qty, side, None  # Market order
                    )
                    tasks.append((venue, task))
        # Wait for all fills
        for venue, task in tasks:
            fill = await task
            if fill['filled'] > 0:
                fills.append(fill)
                filled += fill['filled']
                venues_used.add(venue)
        # Calculate metrics
        total_value = sum(f['filled'] * f['price'] for f in fills)
        avg_price = total_value / filled if filled > 0 else 0
        return {
            'filled': filled,
            'avg_price': avg_price,
            'venues': list(venues_used),
            'improvement': 0  # No improvement on market orders
        }
    async def _execute_adaptive(self, order_id: str, routing: RoutingDecision,
                              quantity: int, side: str) -> Dict[str, Any]:
        """Execute adaptive algorithm that learns from fills."""
        params = self.ALGO_PARAMS['adaptive']
        filled = 0
        fills = []
        venues_used = set()
        # Initialize aggressiveness
        aggressiveness = params['initial_aggressiveness']
        # Adaptive execution loop
        while filled < quantity:
            remaining = quantity - filled
            # Determine slice size based on aggressiveness
            slice_size = int(remaining * aggressiveness * 0.1)
            slice_size = max(10, min(slice_size, remaining))
            # Adjust limit price based on aggressiveness
            price_adjustment = aggressiveness * 0.02  # Up to 2 cents
            if side == 'BUY':
                limit = routing.limit_price + price_adjustment
            else:
                limit = routing.limit_price - price_adjustment
            # Execute slice
            best_venue = self._select_best_venue(routing.venue_allocations)
            fill = await self._simulate_fill(best_venue, slice_size, side, limit)
            if fill['filled'] > 0:
                fills.append(fill)
                filled += fill['filled']
                venues_used.add(best_venue)
                # Learn from fill rate
                fill_rate = fill['filled'] / slice_size
                if fill_rate < 0.5:
                    # Poor fill - increase aggressiveness
                    aggressiveness = min(
                        params['max_aggressiveness'],
                        aggressiveness + params['learning_rate']
                    )
                elif fill_rate > 0.9:
                    # Great fill - decrease aggressiveness
                    aggressiveness = max(
                        params['min_aggressiveness'],
                        aggressiveness - params['learning_rate']
                    )
            else:
                # No fill - significantly increase aggressiveness
                aggressiveness = min(
                    params['max_aggressiveness'],
                    aggressiveness + params['learning_rate'] * 2
                )
            await asyncio.sleep(0.05)
        # Calculate metrics
        total_value = sum(f['filled'] * f['price'] for f in fills)
        avg_price = total_value / filled if filled > 0 else 0
        return {
            'filled': filled,
            'avg_price': avg_price,
            'venues': list(venues_used),
            'improvement': self._calculate_improvement(fills, side)
        }
    async def _execute_simple(self, order_id: str, routing: RoutingDecision,
                            quantity: int, side: str) -> Dict[str, Any]:
        """Execute simple order (limit/market/midpoint)."""
        venue = routing.primary_venue
        fill = await self._simulate_fill(venue, quantity, side, routing.limit_price)
        return {
            'filled': fill['filled'],
            'avg_price': fill['price'],
            'venues': [venue] if fill['filled'] > 0 else [],
            'improvement': fill.get('improvement', 0)
        }
    async def _simulate_fill(self, venue: Venue, quantity: int,
                           side: str, limit_price: Optional[float]) -> Dict[str, Any]:
        """Simulate order fill (in production, would send to venue)."""
        # Simulate realistic fill behavior
        await asyncio.sleep(0.01)  # Network latency
        # Random fill characteristics
        fill_rate = np.random.uniform(0.8, 1.0) if limit_price else 1.0
        filled_qty = int(quantity * fill_rate)
        # Price simulation
        base_price = 2.51
        if side == 'BUY':
            if limit_price and limit_price < base_price:
                filled_qty = 0  # No fill
                price = 0
            else:
                price = base_price - np.random.uniform(0, 0.01)  # Price improvement
        else:
            if limit_price and limit_price > base_price:
                filled_qty = 0  # No fill
                price = 0
            else:
                price = base_price + np.random.uniform(0, 0.01)  # Price improvement
        improvement = 0.01 if filled_qty > 0 and limit_price else 0
        return {
            'venue': venue,
            'filled': filled_qty,
            'price': price,
            'improvement': improvement
        }
    def _calculate_slippage(self, fill_price: float, benchmark: float,
                          side: str) -> float:
        """Calculate slippage in basis points."""
        if side == 'BUY':
            slippage = (fill_price - benchmark) / benchmark
        else:
            slippage = (benchmark - fill_price) / benchmark
        return slippage * 10000  # Convert to basis points
    def _calculate_improvement(self, fills: List[Dict], side: str) -> float:
        """Calculate price improvement from fills."""
        if not fills:
            return 0
        total_improvement = sum(f.get('improvement', 0) * f['filled'] for f in fills)
        total_filled = sum(f['filled'] for f in fills)
        return total_improvement / total_filled if total_filled > 0 else 0
    def _select_best_venue(self, allocations: Dict[Venue, float]) -> Venue:
        """Select best venue from allocations."""
        if not allocations:
            return Venue.CBOE  # Default
        # Weighted random selection
        venues = list(allocations.keys())
        weights = list(allocations.values())
        return np.random.choice(venues, p=weights/np.sum(weights))
    def _update_venue_performance(self, report: ExecutionReport):
        """Update venue performance statistics."""
        for venue in report.venues_used:
            perf = self.venue_performance[venue]
            perf['fills'] += 1
            perf['volume'] += report.filled_quantity
            perf['improvement'] += report.price_improvement
            if report.fill_rate < 0.5:
                perf['failures'] += 1
    def _get_adv(self, symbol: str) -> float:
        """Get average daily volume for symbol."""
        # Simplified - would query historical data
        if 'SPY' in symbol:
            return 50000  # Typical SPY option ADV
        return 10000
    def _categorize_size(self, quantity: int) -> str:
        """Categorize order size."""
        if quantity < 10:
            return 'SMALL'
        elif quantity < 100:
            return 'MEDIUM'
        elif quantity < 1000:
            return 'LARGE'
        else:
            return 'BLOCK'
    def _estimate_market_impact(self, adv_percentage: float) -> float:
        """Estimate market impact in basis points."""
        # Square root market impact model
        return 10 * np.sqrt(adv_percentage * 100)
    def _calculate_optimal_slice(self, quantity: int, adv: float) -> int:
        """Calculate optimal slice size for large orders."""
        # Target 1-2% of average volume per slice
        target_percentage = 0.015
        optimal = int(adv * target_percentage)
        # Constrain between reasonable bounds
        return max(10, min(optimal, quantity // 10))
    def get_execution_analytics(self, period_hours: int = 24) -> Dict[str, Any]:
        """Get execution quality analytics."""
        if not self.execution_history:
            return {'no_data': True}
        # Filter by period
        cutoff = datetime.now() - timedelta(hours=period_hours)
        recent = [e for e in self.execution_history 
                 if hasattr(e, 'timestamp') and e.timestamp >= cutoff]
        if not recent:
            return {'no_data': True}
        # Calculate statistics
        analytics = {
            'total_orders': len(recent),
            'total_volume': sum(e.filled_quantity for e in recent),
            'avg_fill_rate': np.mean([e.fill_rate for e in recent]),
            'avg_slippage_bps': np.mean([e.slippage_bps for e in recent]),
            'avg_improvement': np.mean([e.price_improvement for e in recent]),
            'avg_execution_ms': np.mean([e.execution_time_ms for e in recent]),
            'venues_used': list(set(v for e in recent for v in e.venues_used)),
            'performance_vs_targets': {
                'fill_rate_30s': np.mean([e.fill_rate for e in recent 
                                         if e.execution_time_ms <= 30000]),
                'target_fill_rate': self.PERFORMANCE_TARGETS['fill_rate_30s'],
                'avg_slippage': np.mean([e.slippage_bps for e in recent]),
                'target_slippage': self.PERFORMANCE_TARGETS['slippage_small']
            }
        }
        return analytics
async def main():
    """Example usage of smart order router."""
    router = SpyderSmartOrderRouter()
    # Route a large order
    print("=== Large Order Routing ===")
    routing = await router.route_order(
        symbol='SPY_250_CALL',
        quantity=1000,
        side='BUY',
        urgency='NORMAL'
    )
    print(f"Order Type: {routing.order_type.value}")
    print(f"Primary Venue: {routing.primary_venue.value}")
    print(f"Expected Fill Price: ${routing.expected_fill_price:.3f}")
    print(f"Expected Improvement: ${routing.price_improvement:.3f}")
    print("\nVenue Allocations:")
    for venue, pct in routing.venue_allocations.items():
        print(f"  {venue.value}: {pct:.1%}")
    # Execute the order
    print("\n=== Executing Order ===")
    report = await router.execute_with_algo(routing, 1000, 'BUY')
    print(f"Filled: {report.filled_quantity}/{report.requested_quantity}")
    print(f"Avg Price: ${report.average_fill_price:.3f}")
    print(f"Slippage: {report.slippage_bps:.1f} bps")
    print(f"Execution Time: {report.execution_time_ms:.0f} ms")
    # Get analytics
    print("\n=== Execution Analytics ===")
    analytics = router.get_execution_analytics()
    if 'no_data' not in analytics:
        print(f"Fill Rate: {analytics['avg_fill_rate']:.1%}")
        print(f"Avg Slippage: {analytics['avg_slippage_bps']:.1f} bps")
        print(f"Avg Improvement: ${analytics['avg_improvement']:.3f}")
if __name__ == "__main__":
    asyncio.run(main())