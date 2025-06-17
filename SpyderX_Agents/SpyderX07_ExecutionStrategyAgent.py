#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX07_ExecutionStrategyAgent.py
Purpose: AI-Enhanced Order Execution and Smart Routing
Group: X (AI Agents)

Description:
    Replaces traditional market microstructure modules (SpyderM) with an
    intelligent AI agent that optimizes order execution, predicts liquidity,
    minimizes market impact, and adapts execution algorithms in real-time.

    Replaced Modules:
    - SpyderM01_OrderRouting
    - SpyderM02_ExecutionAlgos
    
    This agent ensures best execution through intelligent decision-making
    about when, where, and how to execute orders.

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - numpy, pandas
    - asyncio
    - scipy
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
from scipy import stats

# Import Spyder core components
from SpyderU01_DataStructures import (
    Order, OrderType, OrderStatus, TimeInForce,
    OptionContract, ExecutionReport, MarketDepth
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# Execution Algorithm Types
class ExecutionAlgo(Enum):
    """Available execution algorithms"""
    MARKET = "market"
    LIMIT = "limit"
    TWAP = "twap"  # Time-Weighted Average Price
    VWAP = "vwap"  # Volume-Weighted Average Price
    POV = "pov"    # Percentage of Volume
    MOC = "moc"    # Market on Close
    ICEBERG = "iceberg"
    SNIPER = "sniper"
    IMPLEMENTATION_SHORTFALL = "implementation_shortfall"
    ARRIVAL_PRICE = "arrival_price"
    ADAPTIVE = "adaptive"

# Urgency Levels
class Urgency(Enum):
    """Order urgency levels"""
    LOW = "low"          # Can wait for better prices
    MEDIUM = "medium"    # Balance price and speed
    HIGH = "high"        # Execute quickly
    CRITICAL = "critical" # Execute immediately

# Market Conditions
class MarketCondition(Enum):
    """Current market conditions"""
    LIQUID = "liquid"
    ILLIQUID = "illiquid"
    VOLATILE = "volatile"
    STABLE = "stable"
    TRENDING = "trending"
    CHOPPY = "choppy"

@dataclass
class ExecutionPlan:
    """Execution plan for an order"""
    order_id: str
    algo: ExecutionAlgo
    parameters: Dict[str, Any]
    venue_preferences: List[str]
    time_constraints: Dict[str, Any]
    price_limits: Dict[str, float]
    slicing_strategy: Optional[Dict[str, Any]] = None
    adaptations: List[Dict[str, Any]] = field(default_factory=list)
    estimated_cost: float = 0.0
    confidence: float = 0.0

@dataclass
class LiquidityProfile:
    """Market liquidity analysis"""
    timestamp: datetime
    bid_depth: List[Tuple[float, int]]  # [(price, size), ...]
    ask_depth: List[Tuple[float, int]]
    spread: float
    depth_imbalance: float
    average_trade_size: float
    liquidity_score: float  # 0-100
    predicted_impact: Dict[str, float]  # size -> impact
    hidden_liquidity_estimate: float

@dataclass
class ExecutionAnalytics:
    """Post-execution analytics"""
    order_id: str
    algo_used: ExecutionAlgo
    arrival_price: float
    average_price: float
    vwap: float
    slippage: float
    market_impact: float
    timing_cost: float
    total_cost: float
    fill_rate: float
    execution_time: timedelta

@dataclass
class MarketMicrostructure:
    """Market microstructure state"""
    tick_size: float
    lot_size: int
    typical_spread: float
    average_volume: float
    volatility: float
    participation_rate: float
    trade_frequency: float
    order_arrival_rate: float

class ExecutionStrategyAgent(SpyderBaseAgent):
    """
    AI-Enhanced Execution Strategy Agent
    
    Provides intelligent order execution with adaptive algorithms,
    liquidity prediction, and smart routing decisions.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Execution Strategy Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('execution_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.max_order_slice = config.get('max_order_slice', 1000)
        self.min_order_size = config.get('min_order_size', 1)
        self.default_participation_rate = config.get('participation_rate', 0.1)
        
        # Execution state
        self.active_orders: Dict[str, Order] = {}
        self.execution_plans: Dict[str, ExecutionPlan] = {}
        self.order_slices: Dict[str, List[Order]] = defaultdict(list)
        
        # Market analysis
        self.liquidity_profiles: Dict[str, LiquidityProfile] = {}
        self.microstructure: Dict[str, MarketMicrostructure] = {}
        self.recent_executions: deque = deque(maxlen=1000)
        
        # Performance tracking
        self.execution_analytics: List[ExecutionAnalytics] = []
        self.algo_performance: Dict[ExecutionAlgo, List[float]] = defaultdict(list)
        self.venue_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Real-time state
        self.market_data_buffer: deque = deque(maxlen=1000)
        self.order_book_snapshots: deque = deque(maxlen=100)
        self.trade_tape: deque = deque(maxlen=10000)
        
        # Prediction models
        self.impact_models: Dict[str, Any] = {}
        self.liquidity_predictors: Dict[str, Any] = {}
        
        # Execution algorithms
        self.algo_implementations = {
            ExecutionAlgo.TWAP: self._execute_twap,
            ExecutionAlgo.VWAP: self._execute_vwap,
            ExecutionAlgo.POV: self._execute_pov,
            ExecutionAlgo.ICEBERG: self._execute_iceberg,
            ExecutionAlgo.SNIPER: self._execute_sniper,
            ExecutionAlgo.ADAPTIVE: self._execute_adaptive
        }
        
        self.logger.info("Execution Strategy Agent initialized")

    async def initialize(self, event_manager=None, broker_interface=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        self.broker = broker_interface
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_data)
            self.event_manager.subscribe(EventType.ORDER_BOOK_UPDATE, self._handle_order_book)
            self.event_manager.subscribe(EventType.TRADE_PRINT, self._handle_trade_print)
            self.event_manager.subscribe(EventType.EXECUTION_REPORT, self._handle_execution_report)
        
        # Start monitoring loops
        asyncio.create_task(self._monitor_executions())
        asyncio.create_task(self._adapt_algorithms())
        
        self.state = AgentState.RUNNING
        self.logger.info("Execution Strategy Agent initialized and running")

    async def create_execution_plan(
        self,
        order: Order,
        urgency: Urgency = Urgency.MEDIUM,
        constraints: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Create intelligent execution plan for an order
        
        Args:
            order: Order to execute
            urgency: Execution urgency level
            constraints: Additional constraints
            
        Returns:
            Optimized execution plan
        """
        try:
            # Analyze current market conditions
            market_condition = await self._analyze_market_conditions(order.symbol)
            
            # Get liquidity profile
            liquidity = await self._analyze_liquidity(order.symbol, order.quantity)
            
            # Predict market impact
            impact_prediction = await self._predict_market_impact(
                order, liquidity, market_condition
            )
            
            # Select optimal algorithm
            algo_selection = await self._select_execution_algorithm(
                order, urgency, market_condition, liquidity, impact_prediction
            )
            
            # Design execution parameters
            execution_params = await self._design_execution_parameters(
                order, algo_selection, urgency, constraints
            )
            
            # Create slicing strategy if needed
            slicing_strategy = None
            if order.quantity > self.max_order_slice:
                slicing_strategy = await self._create_slicing_strategy(
                    order, algo_selection, liquidity
                )
            
            # Estimate execution cost
            estimated_cost = await self._estimate_execution_cost(
                order, algo_selection, execution_params, impact_prediction
            )
            
            # Build execution plan
            plan = ExecutionPlan(
                order_id=order.order_id,
                algo=algo_selection['algo'],
                parameters=execution_params,
                venue_preferences=algo_selection.get('venues', ['SMART']),
                time_constraints=self._get_time_constraints(urgency, constraints),
                price_limits=self._get_price_limits(order, market_condition),
                slicing_strategy=slicing_strategy,
                estimated_cost=estimated_cost,
                confidence=algo_selection['confidence']
            )
            
            # Store plan
            self.execution_plans[order.order_id] = plan
            
            self.logger.info(
                f"Created execution plan for {order.order_id}: "
                f"{plan.algo.value} with confidence {plan.confidence:.2f}"
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Error creating execution plan: {str(e)}")
            # Return default plan
            return self._get_default_execution_plan(order, urgency)

    async def execute_order(
        self,
        order: Order,
        plan: Optional[ExecutionPlan] = None
    ) -> List[ExecutionReport]:
        """
        Execute order according to plan
        
        Args:
            order: Order to execute
            plan: Execution plan (will create if not provided)
            
        Returns:
            List of execution reports
        """
        try:
            # Create plan if not provided
            if not plan:
                plan = await self.create_execution_plan(order)
            
            # Store active order
            self.active_orders[order.order_id] = order
            
            # Execute based on algorithm
            if plan.algo in self.algo_implementations:
                execution_task = asyncio.create_task(
                    self.algo_implementations[plan.algo](order, plan)
                )
                
                # Monitor execution
                reports = await self._monitor_execution(order, execution_task)
            else:
                # Direct execution for simple orders
                reports = await self._execute_direct(order)
            
            # Analyze execution quality
            analytics = await self._analyze_execution_quality(order, reports, plan)
            self.execution_analytics.append(analytics)
            
            # Update performance tracking
            self._update_performance_metrics(plan.algo, analytics)
            
            return reports
            
        except Exception as e:
            self.logger.error(f"Error executing order {order.order_id}: {str(e)}")
            return []

    async def _analyze_market_conditions(self, symbol: str) -> MarketCondition:
        """Analyze current market conditions"""
        # Get recent market data
        recent_data = [d for d in self.market_data_buffer if d.get('symbol') == symbol]
        
        if not recent_data:
            return MarketCondition.STABLE
        
        # Calculate volatility
        prices = [d['price'] for d in recent_data[-50:]]
        if len(prices) > 2:
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns) * np.sqrt(252 * 390)  # Annualized intraday
        else:
            volatility = 0.02
        
        # Check liquidity
        spreads = [d.get('spread', 0.01) for d in recent_data[-20:]]
        avg_spread = np.mean(spreads) if spreads else 0.01
        
        # Determine trend
        if len(prices) > 20:
            trend = (prices[-1] - prices[-20]) / prices[-20]
        else:
            trend = 0
        
        # Classify conditions
        if volatility > 0.3:
            return MarketCondition.VOLATILE
        elif avg_spread > 0.02:
            return MarketCondition.ILLIQUID
        elif abs(trend) > 0.02:
            return MarketCondition.TRENDING
        elif volatility < 0.1:
            return MarketCondition.STABLE
        else:
            return MarketCondition.CHOPPY

    async def _analyze_liquidity(
        self,
        symbol: str,
        order_size: int
    ) -> LiquidityProfile:
        """Analyze market liquidity"""
        # Check cached profile
        if symbol in self.liquidity_profiles:
            profile = self.liquidity_profiles[symbol]
            if (datetime.now() - profile.timestamp).seconds < 60:
                return profile
        
        # Get order book data
        order_book = await self._get_order_book(symbol)
        
        # Analyze depth
        bid_depth = order_book.get('bids', [])[:10]
        ask_depth = order_book.get('asks', [])[:10]
        
        # Calculate metrics
        if bid_depth and ask_depth:
            spread = ask_depth[0][0] - bid_depth[0][0]
            
            # Depth imbalance
            bid_volume = sum(level[1] for level in bid_depth)
            ask_volume = sum(level[1] for level in ask_depth)
            depth_imbalance = (bid_volume - ask_volume) / (bid_volume + ask_volume) if (bid_volume + ask_volume) > 0 else 0
        else:
            spread = 0.01
            depth_imbalance = 0
        
        # Estimate market impact
        impact_curve = await self._estimate_impact_curve(symbol, bid_depth, ask_depth)
        predicted_impact = impact_curve.get(order_size, order_size * 0.0001)
        
        # Calculate liquidity score
        liquidity_score = self._calculate_liquidity_score(
            spread, bid_depth, ask_depth, order_size
        )
        
        # Estimate hidden liquidity
        hidden_liquidity = await self._estimate_hidden_liquidity(symbol, order_book)
        
        profile = LiquidityProfile(
            timestamp=datetime.now(),
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            spread=spread,
            depth_imbalance=depth_imbalance,
            average_trade_size=self._get_average_trade_size(symbol),
            liquidity_score=liquidity_score,
            predicted_impact={order_size: predicted_impact},
            hidden_liquidity_estimate=hidden_liquidity
        )
        
        # Cache profile
        self.liquidity_profiles[symbol] = profile
        
        return profile

    async def _predict_market_impact(
        self,
        order: Order,
        liquidity: LiquidityProfile,
        market_condition: MarketCondition
    ) -> Dict[str, float]:
        """Predict market impact of order"""
        # Get microstructure data
        if order.symbol not in self.microstructure:
            self.microstructure[order.symbol] = await self._get_microstructure(order.symbol)
        
        micro = self.microstructure[order.symbol]
        
        # Base impact model
        order_ratio = order.quantity / micro.average_volume if micro.average_volume > 0 else 0.1
        
        # Linear impact component
        linear_impact = order_ratio * micro.typical_spread * 10
        
        # Square-root impact (empirically observed)
        sqrt_impact = 0.1 * micro.typical_spread * np.sqrt(order_ratio * 10000)
        
        # Adjust for market conditions
        condition_multipliers = {
            MarketCondition.VOLATILE: 2.0,
            MarketCondition.ILLIQUID: 1.5,
            MarketCondition.CHOPPY: 1.3,
            MarketCondition.TRENDING: 1.2,
            MarketCondition.STABLE: 1.0,
            MarketCondition.LIQUID: 0.8
        }
        
        multiplier = condition_multipliers.get(market_condition, 1.0)
        
        # Combine impacts
        temporary_impact = (linear_impact + sqrt_impact) * multiplier
        permanent_impact = temporary_impact * 0.3  # Empirical ratio
        
        # Adjust for liquidity score
        liquidity_adjustment = (100 - liquidity.liquidity_score) / 100
        temporary_impact *= (1 + liquidity_adjustment)
        
        return {
            'temporary_impact': temporary_impact,
            'permanent_impact': permanent_impact,
            'total_impact': temporary_impact + permanent_impact,
            'spread_cost': liquidity.spread / 2,
            'timing_risk': micro.volatility * np.sqrt(order.quantity / micro.average_volume)
        }

    async def _select_execution_algorithm(
        self,
        order: Order,
        urgency: Urgency,
        market_condition: MarketCondition,
        liquidity: LiquidityProfile,
        impact_prediction: Dict[str, float]
    ) -> Dict[str, Any]:
        """Select optimal execution algorithm using AI"""
        
        # Prepare context for AI
        context = {
            'order_size': order.quantity,
            'order_value': order.quantity * order.limit_price if order.limit_price else 0,
            'urgency': urgency.value,
            'market_condition': market_condition.value,
            'liquidity_score': liquidity.liquidity_score,
            'spread': liquidity.spread,
            'predicted_impact': impact_prediction['total_impact'],
            'volatility': self.microstructure.get(order.symbol, {}).get('volatility', 0.02)
        }
        
        # Get AI recommendation
        ai_recommendation = await self._get_ai_algo_recommendation(context)
        
        # Apply rule-based validation
        validated_algo = self._validate_algo_selection(
            ai_recommendation, order, urgency, market_condition
        )
        
        return validated_algo

    async def _get_ai_algo_recommendation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI recommendation for execution algorithm"""
        prompt = f"""
        Select the optimal execution algorithm for this order:
        
        Order Context:
        - Size: {context['order_size']} shares
        - Urgency: {context['urgency']}
        - Market Condition: {context['market_condition']}
        - Liquidity Score: {context['liquidity_score']:.1f}/100
        - Spread: ${context['spread']:.3f}
        - Predicted Impact: {context['predicted_impact']:.2%}
        - Volatility: {context['volatility']:.2%}
        
        Available algorithms:
        - TWAP: Time-weighted execution
        - VWAP: Volume-weighted execution
        - POV: Percentage of volume
        - ICEBERG: Hidden quantity execution
        - SNIPER: Aggressive liquidity taking
        - ADAPTIVE: Dynamic algorithm switching
        
        Recommend the best algorithm with reasoning.
        
        Format response as JSON:
        {{
            "algorithm": "algo_name",
            "confidence": 0.0-1.0,
            "reasoning": "explanation",
            "parameters": {{}},
            "venues": ["venue1", "venue2"]
        }}
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            recommendation = json.loads(response)
            
            return {
                'algo': ExecutionAlgo(recommendation['algorithm'].lower()),
                'confidence': recommendation['confidence'],
                'reasoning': recommendation['reasoning'],
                'parameters': recommendation.get('parameters', {}),
                'venues': recommendation.get('venues', ['SMART'])
            }
        except:
            # Fallback logic
            if context['urgency'] == 'critical':
                return {
                    'algo': ExecutionAlgo.SNIPER,
                    'confidence': 0.8,
                    'reasoning': 'Critical urgency requires aggressive execution',
                    'parameters': {'aggression': 0.9},
                    'venues': ['SMART']
                }
            elif context['liquidity_score'] < 50:
                return {
                    'algo': ExecutionAlgo.ICEBERG,
                    'confidence': 0.7,
                    'reasoning': 'Low liquidity requires hidden execution',
                    'parameters': {'display_size': 100},
                    'venues': ['SMART']
                }
            else:
                return {
                    'algo': ExecutionAlgo.TWAP,
                    'confidence': 0.6,
                    'reasoning': 'Default to time-weighted execution',
                    'parameters': {'duration': 300},
                    'venues': ['SMART']
                }

    def _validate_algo_selection(
        self,
        ai_recommendation: Dict[str, Any],
        order: Order,
        urgency: Urgency,
        market_condition: MarketCondition
    ) -> Dict[str, Any]:
        """Validate and adjust AI algorithm selection"""
        algo = ai_recommendation['algo']
        
        # Override for specific conditions
        if urgency == Urgency.CRITICAL and algo not in [ExecutionAlgo.MARKET, ExecutionAlgo.SNIPER]:
            ai_recommendation['algo'] = ExecutionAlgo.SNIPER
            ai_recommendation['reasoning'] += " (Overridden due to critical urgency)"
            
        elif order.quantity > self.max_order_slice * 10 and algo != ExecutionAlgo.ADAPTIVE:
            ai_recommendation['algo'] = ExecutionAlgo.ADAPTIVE
            ai_recommendation['reasoning'] += " (Large order requires adaptive execution)"
            
        elif market_condition == MarketCondition.ILLIQUID and algo in [ExecutionAlgo.MARKET, ExecutionAlgo.SNIPER]:
            ai_recommendation['algo'] = ExecutionAlgo.ICEBERG
            ai_recommendation['reasoning'] += " (Illiquid market requires careful execution)"
        
        return ai_recommendation

    async def _design_execution_parameters(
        self,
        order: Order,
        algo_selection: Dict[str, Any],
        urgency: Urgency,
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Design detailed execution parameters"""
        algo = algo_selection['algo']
        base_params = algo_selection.get('parameters', {})
        
        # Add algorithm-specific parameters
        if algo == ExecutionAlgo.TWAP:
            base_params.update({
                'start_time': datetime.now(),
                'end_time': datetime.now() + timedelta(minutes=base_params.get('duration', 30)),
                'slice_interval': 60,  # seconds
                'min_slice_size': max(1, order.quantity // 100)
            })
            
        elif algo == ExecutionAlgo.VWAP:
            volume_curve = await self._get_volume_curve(order.symbol)
            base_params.update({
                'volume_curve': volume_curve,
                'participation_rate': self.default_participation_rate,
                'max_participation': 0.2
            })
            
        elif algo == ExecutionAlgo.ICEBERG:
            base_params.update({
                'display_size': min(base_params.get('display_size', 100), order.quantity // 10),
                'refresh_type': 'random',
                'randomization': 0.2
            })
            
        elif algo == ExecutionAlgo.POV:
            base_params.update({
                'target_percentage': base_params.get('target_percentage', 0.1),
                'max_percentage': 0.2,
                'min_fill_size': 1
            })
            
        elif algo == ExecutionAlgo.SNIPER:
            base_params.update({
                'aggression_level': base_params.get('aggression', 0.8),
                'price_improvement': -0.01 if order.side == 'BUY' else 0.01,
                'max_sweep_levels': 3
            })
            
        elif algo == ExecutionAlgo.ADAPTIVE:
            base_params.update({
                'initial_algo': ExecutionAlgo.TWAP,
                'adaptation_frequency': 60,  # seconds
                'performance_threshold': 0.001,  # 10 bps
                'allowed_algos': [ExecutionAlgo.TWAP, ExecutionAlgo.VWAP, ExecutionAlgo.SNIPER]
            })
        
        # Apply constraints
        if constraints:
            base_params.update(constraints)
        
        return base_params

    async def _create_slicing_strategy(
        self,
        order: Order,
        algo_selection: Dict[str, Any],
        liquidity: LiquidityProfile
    ) -> Dict[str, Any]:
        """Create order slicing strategy"""
        total_quantity = order.quantity
        
        # Calculate optimal slice size
        market_capacity = sum(level[1] for level in liquidity.ask_depth[:3])
        optimal_slice = min(
            self.max_order_slice,
            int(market_capacity * 0.2),  # 20% of visible liquidity
            total_quantity // 10  # At least 10 slices
        )
        
        # Adjust for algorithm type
        if algo_selection['algo'] == ExecutionAlgo.ICEBERG:
            optimal_slice = min(optimal_slice, 100)  # Smaller for iceberg
        elif algo_selection['algo'] == ExecutionAlgo.SNIPER:
            optimal_slice = min(optimal_slice, market_capacity)  # Can take full depth
        
        # Create slice schedule
        n_slices = max(1, total_quantity // optimal_slice)
        base_slice_size = total_quantity // n_slices
        remainder = total_quantity % n_slices
        
        slices = []
        for i in range(n_slices):
            slice_size = base_slice_size
            if i < remainder:
                slice_size += 1
                
            # Add randomization
            if algo_selection['algo'] != ExecutionAlgo.TWAP:
                randomization = np.random.uniform(0.8, 1.2)
                slice_size = int(slice_size * randomization)
                slice_size = max(1, min(slice_size, total_quantity - sum(s['size'] for s in slices)))
            
            slices.append({
                'size': slice_size,
                'timing': 'immediate' if i == 0 else 'scheduled',
                'delay': i * 60 if algo_selection['algo'] == ExecutionAlgo.TWAP else 0
            })
        
        return {
            'total_slices': n_slices,
            'slices': slices,
            'adaptive': True,
            'min_slice_size': 1,
            'max_slice_size': self.max_order_slice
        }

    async def _estimate_execution_cost(
        self,
        order: Order,
        algo_selection: Dict[str, Any],
        params: Dict[str, Any],
        impact: Dict[str, float]
    ) -> float:
        """Estimate total execution cost"""
        # Base costs
        spread_cost = impact['spread_cost'] * order.quantity
        impact_cost = impact['total_impact'] * order.quantity * (order.limit_price or 100)
        
        # Algorithm-specific adjustments
        algo_multipliers = {
            ExecutionAlgo.MARKET: 1.5,     # Higher impact
            ExecutionAlgo.SNIPER: 1.3,      # Aggressive
            ExecutionAlgo.TWAP: 1.0,        # Baseline
            ExecutionAlgo.VWAP: 0.9,        # Efficient
            ExecutionAlgo.ICEBERG: 0.8,     # Hidden
            ExecutionAlgo.ADAPTIVE: 0.85    # Optimized
        }
        
        multiplier = algo_multipliers.get(algo_selection['algo'], 1.0)
        
        # Timing risk
        if algo_selection['algo'] in [ExecutionAlgo.TWAP, ExecutionAlgo.VWAP]:
            duration = params.get('duration', 300) / 60  # minutes
            timing_risk = impact['timing_risk'] * np.sqrt(duration / 30)  # 30 min baseline
        else:
            timing_risk = impact['timing_risk'] * 0.5
        
        # Total estimated cost (bps)
        total_cost_bps = (spread_cost + impact_cost * multiplier + timing_risk) * 10000
        
        return total_cost_bps

    def _get_time_constraints(
        self,
        urgency: Urgency,
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Get time constraints for execution"""
        now = datetime.now()
        
        # Default constraints by urgency
        urgency_constraints = {
            Urgency.LOW: {'max_duration': 3600, 'start_delay': 300},      # 1 hour, 5 min delay OK
            Urgency.MEDIUM: {'max_duration': 1800, 'start_delay': 60},    # 30 min, 1 min delay OK
            Urgency.HIGH: {'max_duration': 300, 'start_delay': 0},        # 5 min, immediate
            Urgency.CRITICAL: {'max_duration': 60, 'start_delay': 0}      # 1 min, immediate
        }
        
        time_constraints = urgency_constraints.get(urgency, urgency_constraints[Urgency.MEDIUM])
        
        # Apply custom constraints
        if constraints and 'time_constraints' in constraints:
            time_constraints.update(constraints['time_constraints'])
        
        # Add market hours constraints
        market_close = now.replace(hour=16, minute=0, second=0)
        time_to_close = (market_close - now).seconds
        
        if time_to_close < time_constraints['max_duration']:
            time_constraints['max_duration'] = time_to_close - 60  # Leave 1 minute buffer
            time_constraints['must_complete_by'] = market_close - timedelta(minutes=1)
        
        return time_constraints

    def _get_price_limits(
        self,
        order: Order,
        market_condition: MarketCondition
    ) -> Dict[str, float]:
        """Get price limits for execution"""
        if order.order_type == OrderType.MARKET:
            # Market orders need price protection
            if order.side == 'BUY':
                return {
                    'max_price': order.limit_price * 1.02 if order.limit_price else float('inf'),
                    'reference_price': order.limit_price or 0
                }
            else:
                return {
                    'min_price': order.limit_price * 0.98 if order.limit_price else 0,
                    'reference_price': order.limit_price or 0
                }
        else:
            # Limit orders
            return {
                'limit_price': order.limit_price,
                'discretion': 0.01 if market_condition == MarketCondition.LIQUID else 0
            }

    def _get_default_execution_plan(self, order: Order, urgency: Urgency) -> ExecutionPlan:
        """Get default execution plan as fallback"""
        if urgency == Urgency.CRITICAL:
            algo = ExecutionAlgo.MARKET
        elif order.quantity > self.max_order_slice:
            algo = ExecutionAlgo.TWAP
        else:
            algo = ExecutionAlgo.LIMIT
        
        return ExecutionPlan(
            order_id=order.order_id,
            algo=algo,
            parameters={'duration': 300},
            venue_preferences=['SMART'],
            time_constraints=self._get_time_constraints(urgency, None),
            price_limits=self._get_price_limits(order, MarketCondition.STABLE),
            estimated_cost=50,  # 50 bps default
            confidence=0.5
        )

    # Execution Algorithm Implementations
    
    async def _execute_twap(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order using TWAP algorithm"""
        reports = []
        params = plan.parameters
        
        start_time = params['start_time']
        end_time = params['end_time']
        slice_interval = params['slice_interval']
        
        # Calculate slice schedule
        duration = (end_time - start_time).seconds
        n_slices = max(1, duration // slice_interval)
        slice_size = order.quantity // n_slices
        remainder = order.quantity % n_slices
        
        executed_quantity = 0
        
        for i in range(n_slices):
            # Calculate this slice size
            current_slice = slice_size
            if i < remainder:
                current_slice += 1
            
            # Check if we're done
            if executed_quantity >= order.quantity:
                break
            
            # Create slice order
            slice_order = self._create_slice_order(order, current_slice, i)
            
            # Execute slice
            try:
                slice_report = await self._execute_slice(slice_order, plan)
                reports.append(slice_report)
                executed_quantity += slice_report.filled_quantity
                
                # Check for completion
                if executed_quantity >= order.quantity:
                    break
                
                # Wait for next slice
                if i < n_slices - 1:
                    await asyncio.sleep(slice_interval)
                    
            except Exception as e:
                self.logger.error(f"Error executing TWAP slice {i}: {str(e)}")
                
                # Adapt on failure
                if params.get('adaptive', True):
                    # Switch to more aggressive execution
                    remaining = order.quantity - executed_quantity
                    aggressive_order = self._create_slice_order(order, remaining, -1)
                    aggressive_order.order_type = OrderType.MARKET
                    
                    final_report = await self._execute_slice(aggressive_order, plan)
                    reports.append(final_report)
                    break
        
        return reports

    async def _execute_vwap(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order using VWAP algorithm"""
        reports = []
        params = plan.parameters
        
        volume_curve = params.get('volume_curve', {})
        participation_rate = params.get('participation_rate', 0.1)
        
        executed_quantity = 0
        start_time = datetime.now()
        
        while executed_quantity < order.quantity:
            # Get current market volume
            current_volume = await self._get_current_volume(order.symbol)
            
            # Calculate target slice based on volume
            target_slice = int(current_volume * participation_rate)
            target_slice = min(target_slice, order.quantity - executed_quantity)
            target_slice = max(target_slice, 1)
            
            # Create and execute slice
            slice_order = self._create_slice_order(order, target_slice, -1)
            
            try:
                slice_report = await self._execute_slice(slice_order, plan)
                reports.append(slice_report)
                executed_quantity += slice_report.filled_quantity
                
                # Adaptive waiting based on market activity
                if current_volume > 0:
                    wait_time = min(60, max(5, 100 / current_volume))
                else:
                    wait_time = 30
                    
                await asyncio.sleep(wait_time)
                
                # Check time constraints
                if (datetime.now() - start_time).seconds > params.get('max_duration', 3600):
                    self.logger.warning(f"VWAP execution timeout for {order.order_id}")
                    break
                    
            except Exception as e:
                self.logger.error(f"Error in VWAP execution: {str(e)}")
                break
        
        return reports

    async def _execute_iceberg(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order using Iceberg algorithm"""
        reports = []
        params = plan.parameters
        
        display_size = params['display_size']
        randomization = params.get('randomization', 0.2)
        
        executed_quantity = 0
        
        while executed_quantity < order.quantity:
            # Randomize display size
            current_display = int(display_size * (1 + np.random.uniform(-randomization, randomization)))
            current_display = max(1, min(current_display, order.quantity - executed_quantity))
            
            # Create visible order
            visible_order = self._create_slice_order(order, current_display, -1)
            visible_order.order_type = OrderType.LIMIT
            
            try:
                # Place and monitor visible order
                report = await self._execute_slice(visible_order, plan)
                reports.append(report)
                executed_quantity += report.filled_quantity
                
                # Random delay between refreshes
                if executed_quantity < order.quantity:
                    delay = np.random.uniform(5, 30)
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                self.logger.error(f"Error in Iceberg execution: {str(e)}")
                break
        
        return reports

    async def _execute_sniper(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order using Sniper algorithm (aggressive)"""
        reports = []
        params = plan.parameters
        
        aggression = params.get('aggression_level', 0.8)
        max_sweep = params.get('max_sweep_levels', 3)
        
        # Get current order book
        book = await self._get_order_book(order.symbol)
        
        if order.side == 'BUY':
            available_liquidity = book.get('asks', [])[:max_sweep]
        else:
            available_liquidity = book.get('bids', [])[:max_sweep]
        
        executed_quantity = 0
        
        for level_price, level_size in available_liquidity:
            if executed_quantity >= order.quantity:
                break
            
            # Calculate size to take at this level
            take_size = min(
                int(level_size * aggression),
                order.quantity - executed_quantity
            )
            
            if take_size > 0:
                # Create aggressive order at this level
                sweep_order = self._create_slice_order(order, take_size, -1)
                sweep_order.limit_price = level_price
                sweep_order.order_type = OrderType.LIMIT
                sweep_order.time_in_force = TimeInForce.IOC  # Immediate or Cancel
                
                try:
                    report = await self._execute_slice(sweep_order, plan)
                    reports.append(report)
                    executed_quantity += report.filled_quantity
                except Exception as e:
                    self.logger.error(f"Error in Sniper sweep: {str(e)}")
        
        # If not fully filled, place remaining as limit order
        if executed_quantity < order.quantity:
            remaining_order = self._create_slice_order(
                order, 
                order.quantity - executed_quantity, 
                -1
            )
            remaining_order.order_type = OrderType.LIMIT
            
            final_report = await self._execute_slice(remaining_order, plan)
            reports.append(final_report)
        
        return reports

    async def _execute_pov(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order as Percentage of Volume"""
        reports = []
        params = plan.parameters
        
        target_pct = params.get('target_percentage', 0.1)
        max_pct = params.get('max_percentage', 0.2)
        
        executed_quantity = 0
        market_volume = 0
        
        while executed_quantity < order.quantity:
            # Get recent market volume
            recent_volume = await self._get_recent_volume(order.symbol, 60)  # Last minute
            
            # Calculate our target based on POV
            our_target = int((market_volume + recent_volume) * target_pct)
            our_current = executed_quantity
            
            # Calculate next slice
            slice_size = min(
                our_target - our_current,
                int(recent_volume * max_pct),
                order.quantity - executed_quantity
            )
            
            if slice_size > 0:
                slice_order = self._create_slice_order(order, slice_size, -1)
                
                try:
                    report = await self._execute_slice(slice_order, plan)
                    reports.append(report)
                    executed_quantity += report.filled_quantity
                except Exception as e:
                    self.logger.error(f"Error in POV execution: {str(e)}")
            
            market_volume += recent_volume
            await asyncio.sleep(10)  # Check every 10 seconds
            
            # Safety check
            if len(reports) > 1000:  # Prevent infinite loops
                break
        
        return reports

    async def _execute_adaptive(self, order: Order, plan: ExecutionPlan) -> List[ExecutionReport]:
        """Execute order using adaptive algorithm switching"""
        reports = []
        params = plan.parameters
        
        current_algo = params.get('initial_algo', ExecutionAlgo.TWAP)
        allowed_algos = params.get('allowed_algos', [ExecutionAlgo.TWAP, ExecutionAlgo.VWAP])
        adaptation_frequency = params.get('adaptation_frequency', 60)
        
        executed_quantity = 0
        last_adaptation = datetime.now()
        performance_history = []
        
        while executed_quantity < order.quantity:
            # Check if we should adapt
            if (datetime.now() - last_adaptation).seconds > adaptation_frequency:
                # Analyze recent performance
                recent_performance = self._analyze_recent_performance(
                    reports[-10:] if len(reports) > 10 else reports
                )
                performance_history.append(recent_performance)
                
                # Decide if we should switch algorithms
                new_algo = await self._select_adaptive_algorithm(
                    current_algo,
                    allowed_algos,
                    recent_performance,
                    order,
                    executed_quantity
                )
                
                if new_algo != current_algo:
                    self.logger.info(
                        f"Adaptive execution switching from {current_algo.value} "
                        f"to {new_algo.value} for {order.order_id}"
                    )
                    current_algo = new_algo
                
                last_adaptation = datetime.now()
            
            # Execute using current algorithm
            remaining_qty = order.quantity - executed_quantity
            temp_order = self._create_slice_order(order, remaining_qty, -1)
            
            # Create temporary plan for current algorithm
            temp_plan = ExecutionPlan(
                order_id=temp_order.order_id,
                algo=current_algo,
                parameters=self._get_adaptive_params(current_algo, params),
                venue_preferences=plan.venue_preferences,
                time_constraints={'max_duration': adaptation_frequency},
                price_limits=plan.price_limits,
                estimated_cost=0,
                confidence=0.8
            )
            
            # Execute for one adaptation period
            if current_algo in self.algo_implementations:
                period_reports = await self.algo_implementations[current_algo](
                    temp_order, temp_plan
                )
                reports.extend(period_reports)
                
                # Update executed quantity
                for report in period_reports:
                    executed_quantity += report.filled_quantity
            
            # Safety check
            if len(reports) > 1000:
                break
        
        return reports

    async def _execute_direct(self, order: Order) -> List[ExecutionReport]:
        """Execute order directly without complex algorithm"""
        if self.broker:
            report = await self.broker.place_order(order)
            return [report]
        else:
            # Mock execution
            return [ExecutionReport(
                order_id=order.order_id,
                timestamp=datetime.now(),
                status=OrderStatus.FILLED,
                filled_quantity=order.quantity,
                average_price=order.limit_price or 100.0,
                commission=order.quantity * 0.001,
                venue='MOCK'
            )]

    def _create_slice_order(self, parent_order: Order, slice_size: int, slice_index: int) -> Order:
        """Create a slice order from parent order"""
        slice_order = Order(
            order_id=f"{parent_order.order_id}_slice_{slice_index}",
            parent_id=parent_order.order_id,
            symbol=parent_order.symbol,
            side=parent_order.side,
            quantity=slice_size,
            order_type=parent_order.order_type,
            limit_price=parent_order.limit_price,
            stop_price=parent_order.stop_price,
            time_in_force=parent_order.time_in_force
        )
        
        return slice_order

    async def _execute_slice(self, slice_order: Order, plan: ExecutionPlan) -> ExecutionReport:
        """Execute a single order slice"""
        # Add to active orders
        self.active_orders[slice_order.order_id] = slice_order
        
        try:
            if self.broker:
                # Real execution through broker
                report = await self.broker.place_order(slice_order)
            else:
                # Simulated execution
                await asyncio.sleep(0.1)  # Simulate execution delay
                
                # Mock fill
                fill_price = slice_order.limit_price or 100.0
                if slice_order.side == 'BUY':
                    fill_price *= (1 + np.random.uniform(0, 0.001))
                else:
                    fill_price *= (1 - np.random.uniform(0, 0.001))
                
                report = ExecutionReport(
                    order_id=slice_order.order_id,
                    timestamp=datetime.now(),
                    status=OrderStatus.FILLED,
                    filled_quantity=slice_order.quantity,
                    average_price=fill_price,
                    commission=slice_order.quantity * 0.001,
                    venue='SIM'
                )
            
            # Record execution
            self.recent_executions.append({
                'timestamp': report.timestamp,
                'order_id': report.order_id,
                'symbol': slice_order.symbol,
                'side': slice_order.side,
                'quantity': report.filled_quantity,
                'price': report.average_price,
                'algo': plan.algo.value
            })
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error executing slice {slice_order.order_id}: {str(e)}")
            
            # Return partial fill or failure
            return ExecutionReport(
                order_id=slice_order.order_id,
                timestamp=datetime.now(),
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                average_price=0,
                commission=0,
                venue='ERROR',
                message=str(e)
            )
        finally:
            # Remove from active orders
            if slice_order.order_id in self.active_orders:
                del self.active_orders[slice_order.order_id]

    async def _monitor_execution(
        self,
        order: Order,
        execution_task: asyncio.Task
    ) -> List[ExecutionReport]:
        """Monitor ongoing execution"""
        try:
            # Wait for execution to complete
            reports = await execution_task
            
            # Verify execution quality
            total_filled = sum(r.filled_quantity for r in reports)
            if total_filled < order.quantity:
                self.logger.warning(
                    f"Partial fill for {order.order_id}: "
                    f"{total_filled}/{order.quantity} shares"
                )
            
            return reports
            
        except asyncio.CancelledError:
            self.logger.warning(f"Execution cancelled for {order.order_id}")
            return []
        except Exception as e:
            self.logger.error(f"Error monitoring execution: {str(e)}")
            return []

    async def _monitor_executions(self):
        """Background task to monitor all executions"""
        while self.state == AgentState.RUNNING:
            try:
                # Check active orders
                for order_id, order in list(self.active_orders.items()):
                    # Check for stale orders
                    if order_id in self.execution_plans:
                        plan = self.execution_plans[order_id]
                        max_duration = plan.time_constraints.get('max_duration', 3600)
                        
                        # Cancel if exceeded max duration
                        # (Implementation depends on broker interface)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in execution monitor: {str(e)}")

    async def _adapt_algorithms(self):
        """Background task to adapt algorithm selection"""
        while self.state == AgentState.RUNNING:
            try:
                # Analyze recent performance by algorithm
                for algo in ExecutionAlgo:
                    if algo in self.algo_performance and len(self.algo_performance[algo]) > 10:
                        recent_performance = self.algo_performance[algo][-50:]
                        avg_performance = np.mean(recent_performance)
                        
                        # Adjust algorithm preferences based on performance
                        # (Store in internal state for algorithm selection)
                
                await asyncio.sleep(300)  # Adapt every 5 minutes
                
            except Exception as e:
                self.logger.error(f"Error in algorithm adaptation: {str(e)}")

    async def _analyze_execution_quality(
        self,
        order: Order,
        reports: List[ExecutionReport],
        plan: ExecutionPlan
    ) -> ExecutionAnalytics:
        """Analyze execution quality"""
        if not reports:
            return ExecutionAnalytics(
                order_id=order.order_id,
                algo_used=plan.algo,
                arrival_price=0,
                average_price=0,
                vwap=0,
                slippage=0,
                market_impact=0,
                timing_cost=0,
                total_cost=0,
                fill_rate=0,
                execution_time=timedelta(0)
            )
        
        # Calculate metrics
        total_quantity = sum(r.filled_quantity for r in reports)
        total_value = sum(r.filled_quantity * r.average_price for r in reports)
        average_price = total_value / total_quantity if total_quantity > 0 else 0
        
        # Get market prices during execution
        start_time = reports[0].timestamp
        end_time = reports[-1].timestamp
        execution_time = end_time - start_time
        
        # Calculate VWAP during execution period
        vwap = await self._calculate_market_vwap(
            order.symbol, start_time, end_time
        )
        
        # Arrival price (price at order submission)
        arrival_price = order.limit_price or average_price
        
        # Calculate costs
        if order.side == 'BUY':
            slippage = (average_price - arrival_price) / arrival_price
            vwap_slippage = (average_price - vwap) / vwap if vwap > 0 else 0
        else:
            slippage = (arrival_price - average_price) / arrival_price
            vwap_slippage = (vwap - average_price) / vwap if vwap > 0 else 0
        
        # Implementation shortfall components
        market_impact = abs(slippage) * 0.6  # Empirical split
        timing_cost = abs(slippage) * 0.4
        
        # Total cost in basis points
        total_cost = abs(slippage) * 10000
        
        # Fill rate
        fill_rate = total_quantity / order.quantity
        
        return ExecutionAnalytics(
            order_id=order.order_id,
            algo_used=plan.algo,
            arrival_price=arrival_price,
            average_price=average_price,
            vwap=vwap,
            slippage=slippage,
            market_impact=market_impact,
            timing_cost=timing_cost,
            total_cost=total_cost,
            fill_rate=fill_rate,
            execution_time=execution_time
        )

    def _update_performance_metrics(self, algo: ExecutionAlgo, analytics: ExecutionAnalytics):
        """Update algorithm performance metrics"""
        # Track performance by algorithm
        self.algo_performance[algo].append(analytics.total_cost)
        
        # Update venue performance if available
        # (Would track by execution venue)

    async def _get_order_book(self, symbol: str) -> Dict[str, Any]:
        """Get current order book"""
        if self.broker:
            return await self.broker.get_order_book(symbol)
        else:
            # Mock order book
            mid_price = 100.0
            spread = 0.01
            
            return {
                'bids': [
                    (mid_price - spread/2 - i*0.01, np.random.randint(100, 1000))
                    for i in range(10)
                ],
                'asks': [
                    (mid_price + spread/2 + i*0.01, np.random.randint(100, 1000))
                    for i in range(10)
                ]
            }

    async def _get_microstructure(self, symbol: str) -> MarketMicrostructure:
        """Get market microstructure data"""
        # Would fetch from market data provider
        # Mock implementation
        return MarketMicrostructure(
            tick_size=0.01,
            lot_size=1,
            typical_spread=0.01,
            average_volume=1000000,
            volatility=0.02,
            participation_rate=0.1,
            trade_frequency=100,  # trades per minute
            order_arrival_rate=200  # orders per minute
        )

    async def _estimate_impact_curve(
        self,
        symbol: str,
        bid_depth: List[Tuple[float, int]],
        ask_depth: List[Tuple[float, int]]
    ) -> Dict[int, float]:
        """Estimate market impact for different order sizes"""
        impact_curve = {}
        
        # Calculate cumulative depth
        cumulative_size = 0
        weighted_price = 0
        
        for price, size in ask_depth:  # For buy orders
            cumulative_size += size
            weighted_price += price * size
            
            # Estimate impact at this cumulative size
            if cumulative_size > 0:
                avg_price = weighted_price / cumulative_size
                mid_price = (bid_depth[0][0] + ask_depth[0][0]) / 2 if bid_depth and ask_depth else price
                impact = (avg_price - mid_price) / mid_price
                impact_curve[cumulative_size] = impact
        
        return impact_curve

    def _calculate_liquidity_score(
        self,
        spread: float,
        bid_depth: List[Tuple[float, int]],
        ask_depth: List[Tuple[float, int]],
        order_size: int
    ) -> float:
        """Calculate liquidity score (0-100)"""
        score = 100.0
        
        # Spread component (40%)
        if spread > 0.02:
            score -= 20
        elif spread > 0.01:
            score -= 10
        
        # Depth component (40%)
        total_depth = sum(level[1] for level in (bid_depth + ask_depth))
        if total_depth < order_size * 5:
            score -= 30
        elif total_depth < order_size * 10:
            score -= 15
        
        # Balance component (20%)
        if bid_depth and ask_depth:
            bid_size = sum(level[1] for level in bid_depth)
            ask_size = sum(level[1] for level in ask_depth)
            imbalance = abs(bid_size - ask_size) / (bid_size + ask_size)
            if imbalance > 0.3:
                score -= 10
        
        return max(0, score)

    async def _estimate_hidden_liquidity(
        self,
        symbol: str,
        visible_book: Dict[str, Any]
    ) -> float:
        """Estimate hidden liquidity using AI"""
        # Analyze recent trade sizes vs visible liquidity
        recent_trades = [t for t in self.trade_tape if t.get('symbol') == symbol][-100:]
        
        if not recent_trades:
            return 0.5  # Default 50% hidden
        
        # Calculate ratio of large trades to visible liquidity
        visible_size = sum(level[1] for level in visible_book.get('bids', [])[:3])
        visible_size += sum(level[1] for level in visible_book.get('asks', [])[:3])
        
        large_trades = [t for t in recent_trades if t.get('size', 0) > visible_size * 0.2]
        hidden_ratio = len(large_trades) / len(recent_trades) if recent_trades else 0
        
        # Adjust estimate based on market conditions
        # Higher hidden liquidity in liquid markets
        return min(0.8, hidden_ratio * 2)

    def _get_average_trade_size(self, symbol: str) -> float:
        """Get average trade size for symbol"""
        recent_trades = [t for t in self.trade_tape if t.get('symbol') == symbol][-100:]
        
        if recent_trades:
            sizes = [t.get('size', 0) for t in recent_trades]
            return np.mean(sizes)
        else:
            return 100  # Default

    async def _get_volume_curve(self, symbol: str) -> Dict[str, float]:
        """Get intraday volume curve"""
        # Would fetch historical intraday volume pattern
        # Mock implementation - U-shaped curve
        curve = {}
        for hour in range(9, 17):  # 9:30 AM to 4:00 PM
            for minute in range(0, 60, 5):
                time_key = f"{hour:02d}:{minute:02d}"
                # U-shaped: high at open/close
                if hour == 9 and minute < 30:
                    continue
                elif hour == 9:
                    curve[time_key] = 0.15  # High opening volume
                elif hour == 15 and minute > 30:
                    curve[time_key] = 0.12  # High closing volume
                else:
                    # Lower midday volume
                    curve[time_key] = 0.05 + 0.02 * np.sin((hour - 9) * np.pi / 7)
        
        return curve

    async def _get_current_volume(self, symbol: str) -> float:
        """Get current trading volume"""
        # Count recent trades
        cutoff = datetime.now() - timedelta(seconds=60)
        recent_volume = sum(
            t.get('size', 0) for t in self.trade_tape
            if t.get('symbol') == symbol and t.get('timestamp', datetime.min) > cutoff
        )
        
        return recent_volume

    async def _get_recent_volume(self, symbol: str, seconds: int) -> float:
        """Get volume over recent period"""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        volume = sum(
            t.get('size', 0) for t in self.trade_tape
            if t.get('symbol') == symbol and t.get('timestamp', datetime.min) > cutoff
        )
        
        return volume

    def _analyze_recent_performance(self, reports: List[ExecutionReport]) -> Dict[str, float]:
        """Analyze recent execution performance"""
        if not reports:
            return {'slippage': 0, 'fill_rate': 0, 'speed': 0}
        
        # Calculate average slippage
        slippages = []
        for report in reports:
            if hasattr(report, 'order') and report.order.limit_price:
                slippage = abs(report.average_price - report.order.limit_price) / report.order.limit_price
                slippages.append(slippage)
        
        # Fill rate
        fill_rates = [r.filled_quantity / r.order.quantity if hasattr(r, 'order') else 1 for r in reports]
        
        # Execution speed (simplified)
        speeds = [1.0 for r in reports]  # Would calculate based on timestamps
        
        return {
            'slippage': np.mean(slippages) if slippages else 0,
            'fill_rate': np.mean(fill_rates),
            'speed': np.mean(speeds)
        }

    async def _select_adaptive_algorithm(
        self,
        current_algo: ExecutionAlgo,
        allowed_algos: List[ExecutionAlgo],
        performance: Dict[str, float],
        order: Order,
        executed_quantity: int
    ) -> ExecutionAlgo:
        """Select best algorithm based on recent performance"""
        
        # Check if current algorithm is underperforming
        if performance['slippage'] > 0.002:  # 20 bps
            # High slippage - switch to less aggressive
            if current_algo == ExecutionAlgo.SNIPER:
                return ExecutionAlgo.ICEBERG
            elif current_algo == ExecutionAlgo.TWAP:
                return ExecutionAlgo.VWAP
        
        # Check fill rate
        if performance['fill_rate'] < 0.8:
            # Poor fills - switch to more aggressive
            if current_algo == ExecutionAlgo.ICEBERG:
                return ExecutionAlgo.SNIPER
            elif current_algo == ExecutionAlgo.VWAP:
                return ExecutionAlgo.TWAP
        
        # Check remaining quantity
        remaining_pct = (order.quantity - executed_quantity) / order.quantity
        if remaining_pct < 0.2 and current_algo != ExecutionAlgo.SNIPER:
            # Final push - use aggressive algo
            return ExecutionAlgo.SNIPER if ExecutionAlgo.SNIPER in allowed_algos else current_algo
        
        return current_algo

    def _get_adaptive_params(
        self,
        algo: ExecutionAlgo,
        base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get parameters for adaptive algorithm switching"""
        if algo == ExecutionAlgo.TWAP:
            return {
                'duration': base_params.get('adaptation_frequency', 60),
                'slice_interval': 10
            }
        elif algo == ExecutionAlgo.VWAP:
            return {
                'participation_rate': 0.15,
                'max_duration': base_params.get('adaptation_frequency', 60)
            }
        elif algo == ExecutionAlgo.SNIPER:
            return {
                'aggression_level': 0.9,
                'max_sweep_levels': 5
            }
        else:
            return {}

    async def _calculate_market_vwap(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> float:
        """Calculate market VWAP during execution period"""
        # Get trades during period
        period_trades = [
            t for t in self.trade_tape
            if (t.get('symbol') == symbol and
                t.get('timestamp', datetime.min) >= start_time and
                t.get('timestamp', datetime.max) <= end_time)
        ]
        
        if not period_trades:
            return 0
        
        # Calculate VWAP
        total_value = sum(t.get('price', 0) * t.get('size', 0) for t in period_trades)
        total_volume = sum(t.get('size', 0) for t in period_trades)
        
        return total_value / total_volume if total_volume > 0 else 0

    async def _handle_market_data(self, event: Event):
        """Handle market data updates"""
        if hasattr(event, 'data'):
            self.market_data_buffer.append({
                'timestamp': datetime.now(),
                'symbol': event.data.get('symbol'),
                'price': event.data.get('price'),
                'size': event.data.get('size'),
                'spread': event.data.get('spread', 0.01)
            })

    async def _handle_order_book(self, event: Event):
        """Handle order book updates"""
        if hasattr(event, 'data'):
            self.order_book_snapshots.append({
                'timestamp': datetime.now(),
                'symbol': event.data.get('symbol'),
                'bids': event.data.get('bids', []),
                'asks': event.data.get('asks', [])
            })

    async def _handle_trade_print(self, event: Event):
        """Handle trade print events"""
        if hasattr(event, 'data'):
            self.trade_tape.append({
                'timestamp': datetime.now(),
                'symbol': event.data.get('symbol'),
                'price': event.data.get('price'),
                'size': event.data.get('size'),
                'side': event.data.get('side')
            })

    async def _handle_execution_report(self, event: Event):
        """Handle execution reports"""
        if hasattr(event, 'data'):
            report = event.data.get('report')
            if report and report.order_id in self.active_orders:
                # Update order status
                order = self.active_orders[report.order_id]
                
                # Check if order is complete
                if report.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    del self.active_orders[report.order_id]

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for execution insights"""
        # Mock implementation
        if "execution algorithm" in prompt:
            return json.dumps({
                "algorithm": "adaptive",
                "confidence": 0.85,
                "reasoning": "High order size with moderate urgency suggests adaptive execution",
                "parameters": {
                    "initial_algo": "twap",
                    "adaptation_frequency": 60
                },
                "venues": ["SMART", "IEX"]
            })
        else:
            return "{}"

    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        stats = {
            'active_orders': len(self.active_orders),
            'recent_executions': len(self.recent_executions),
            'algo_performance': {},
            'average_slippage': 0,
            'average_fill_rate': 0,
            'best_performing_algo': None,
            'worst_performing_algo': None
        }
        
        # Analyze algorithm performance
        algo_stats = {}
        for algo, costs in self.algo_performance.items():
            if costs:
                algo_stats[algo.value] = {
                    'avg_cost_bps': np.mean(costs),
                    'std_cost_bps': np.std(costs),
                    'n_executions': len(costs),
                    'recent_trend': 'improving' if len(costs) > 10 and np.mean(costs[-5:]) < np.mean(costs[-10:-5]) else 'stable'
                }
        
        stats['algo_performance'] = algo_stats
        
        # Find best/worst algorithms
        if algo_stats:
            best_algo = min(algo_stats.items(), key=lambda x: x[1]['avg_cost_bps'])
            worst_algo = max(algo_stats.items(), key=lambda x: x[1]['avg_cost_bps'])
            stats['best_performing_algo'] = best_algo[0]
            stats['worst_performing_algo'] = worst_algo[0]
        
        # Calculate average metrics from recent executions
        if self.execution_analytics:
            recent_analytics = self.execution_analytics[-100:]
            stats['average_slippage'] = np.mean([a.slippage for a in recent_analytics])
            stats['average_fill_rate'] = np.mean([a.fill_rate for a in recent_analytics])
        
        return stats

    async def optimize_execution_parameters(
        self,
        symbol: str,
        typical_order_size: int,
        historical_executions: List[ExecutionAnalytics]
    ) -> Dict[str, Any]:
        """Optimize execution parameters based on historical data"""
        
        # Group by algorithm
        algo_groups = defaultdict(list)
        for execution in historical_executions:
            algo_groups[execution.algo_used].append(execution)
        
        # Analyze each algorithm's performance
        recommendations = {}
        
        for algo, executions in algo_groups.items():
            if len(executions) < 10:
                continue
            
            # Calculate performance metrics
            avg_cost = np.mean([e.total_cost for e in executions])
            cost_std = np.std([e.total_cost for e in executions])
            avg_time = np.mean([e.execution_time.total_seconds() for e in executions])
            
            # Generate recommendations
            if algo == ExecutionAlgo.TWAP:
                optimal_duration = avg_time * (1 + cost_std / 100)  # Adjust based on cost variance
                recommendations[algo] = {
                    'optimal_duration': optimal_duration,
                    'slice_interval': max(10, optimal_duration / 50),
                    'confidence': min(0.9, 1 - cost_std / 100)
                }
            
            elif algo == ExecutionAlgo.VWAP:
                # Analyze participation rate impact
                recommendations[algo] = {
                    'optimal_participation': 0.1,  # Would calculate from data
                    'max_participation': 0.2,
                    'avoid_times': []  # Would identify high-impact periods
                }
            
            elif algo == ExecutionAlgo.ICEBERG:
                # Optimize display size
                recommendations[algo] = {
                    'optimal_display_pct': 0.1,  # 10% of order
                    'randomization': 0.2,
                    'refresh_delay': 15  # seconds
                }
        
        # Overall recommendations
        best_algo_by_size = {}
        
        # Small orders
        if typical_order_size < 1000:
            best_algo_by_size['small'] = ExecutionAlgo.LIMIT
        # Medium orders
        elif typical_order_size < 10000:
            best_algo_by_size['medium'] = ExecutionAlgo.TWAP
        # Large orders
        else:
            best_algo_by_size['large'] = ExecutionAlgo.ADAPTIVE
        
        return {
            'algo_specific': recommendations,
            'size_based_recommendation': best_algo_by_size,
            'market_impact_threshold': np.percentile([e.market_impact for e in historical_executions], 75),
            'typical_spread': np.mean([e.arrival_price * 0.0001 for e in historical_executions])  # Simplified
        }

    async def export_execution_report(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = 'json'
    ) -> Union[str, pd.DataFrame]:
        """Export execution report for period"""
        
        # Filter executions by date
        period_executions = [
            e for e in self.execution_analytics
            if start_date <= e.timestamp <= end_date
        ]
        
        if not period_executions:
            return "No executions found in period"
        
        # Create report data
        report_data = []
        
        for execution in period_executions:
            report_data.append({
                'order_id': execution.order_id,
                'timestamp': execution.timestamp,
                'algorithm': execution.algo_used.value,
                'arrival_price': execution.arrival_price,
                'average_price': execution.average_price,
                'vwap': execution.vwap,
                'slippage_bps': execution.slippage * 10000,
                'market_impact_bps': execution.market_impact * 10000,
                'total_cost_bps': execution.total_cost,
                'fill_rate': execution.fill_rate,
                'execution_time_seconds': execution.execution_time.total_seconds()
            })
        
        # Create DataFrame
        df = pd.DataFrame(report_data)
        
        if format == 'json':
            # Add summary statistics
            summary = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'total_executions': len(report_data),
                'average_slippage_bps': df['slippage_bps'].mean(),
                'average_cost_bps': df['total_cost_bps'].mean(),
                'best_execution': df.loc[df['total_cost_bps'].idxmin()].to_dict(),
                'worst_execution': df.loc[df['total_cost_bps'].idxmax()].to_dict(),
                'by_algorithm': df.groupby('algorithm').agg({
                    'total_cost_bps': ['mean', 'std', 'count']
                }).to_dict()
            }
            
            return json.dumps({
                'executions': report_data,
                'summary': summary
            }, indent=2, default=str)
        else:
            return df

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Cancel any active orders
        for order_id in list(self.active_orders.keys()):
            self.logger.info(f"Cancelling active order {order_id}")
            # Would send cancel to broker
        
        self.logger.info("Execution Strategy Agent shutdown complete")

# Factory function
def create_execution_strategy_agent(config: Dict[str, Any]) -> ExecutionStrategyAgent:
    """Create and return an Execution Strategy Agent instance"""
    return ExecutionStrategyAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'execution_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'max_order_slice': 1000,
        'min_order_size': 1,
        'participation_rate': 0.1
    }
    
    # Create agent
    execution_agent = create_execution_strategy_agent(test_config)
    
    # Example usage
    async def example_usage():
        await execution_agent.initialize()
        
        # Create test order
        test_order = Order(
            order_id='TEST_001',
            symbol='SPY',
            side='BUY',
            quantity=5000,
            order_type=OrderType.LIMIT,
            limit_price=400.00,
            time_in_force=TimeInForce.DAY
        )
        
        # Create execution plan
        plan = await execution_agent.create_execution_plan(
            test_order,
            urgency=Urgency.MEDIUM
        )
        
        print(f"Execution Plan:")
        print(f"Algorithm: {plan.algo.value}")
        print(f"Confidence: {plan.confidence:.2%}")
        print(f"Estimated Cost: {plan.estimated_cost:.1f} bps")
        print(f"Parameters: {plan.parameters}")
        
        # Execute order
        reports = await execution_agent.execute_order(test_order, plan)
        
        print(f"\nExecution Results:")
        print(f"Total Filled: {sum(r.filled_quantity for r in reports)} shares")
        print(f"Average Price: ${np.mean([r.average_price for r in reports]):.2f}")
        
        # Get statistics
        stats = await execution_agent.get_execution_stats()
        print(f"\nExecution Statistics:")
        print(f"Active Orders: {stats['active_orders']}")
        print(f"Best Algorithm: {stats['best_performing_algo']}")
    
    # Run example
    # asyncio.run(example_usage())