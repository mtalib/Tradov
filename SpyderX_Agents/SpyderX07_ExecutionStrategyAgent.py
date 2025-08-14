#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX07_ExecutionStrategyAgent.py
Purpose: AI-Enhanced Order Execution and Strategy Management
Group: X (AI Agents)

This module implements an intelligent execution strategy agent that optimizes
order placement, manages slippage, and ensures best execution for SPY options
trades using Ollama AI integration.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-16
Last Updated: 2025-06-19 Time: 13:47
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import statistics
from collections import deque

# Third-party imports
import numpy as np

# Ollama imports (with graceful fallback)
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Order types
class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"

# Execution urgency levels
class ExecutionUrgency(Enum):
    """Execution urgency enumeration."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# Time in force options
class TimeInForce(Enum):
    """Time in force enumeration."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTD = "GTD"  # Good Till Date

# Execution algorithms
EXECUTION_ALGORITHMS = [
    "TWAP",      # Time Weighted Average Price
    "VWAP",      # Volume Weighted Average Price
    "POV",       # Percentage of Volume
    "ICEBERG",   # Iceberg orders
    "SNIPER",    # Sniper execution
    "ADAPTIVE",  # Adaptive algorithm
]

# Default configuration
DEFAULT_CONFIG = {
    'max_order_size': 100,
    'max_slippage_bps': 5,  # basis points
    'urgency_threshold': 0.7,
    'adaptive_threshold': 0.8,
    'retry_attempts': 3,
    'execution_window_minutes': 5,
}

# Model configuration
DEFAULT_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.3  # Lower temperature for execution decisions

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ExecutionRequest:
    """Execution request data structure."""
    symbol: str
    quantity: int
    side: str  # 'BUY' or 'SELL'
    order_type: OrderType
    urgency: ExecutionUrgency
    price_limit: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarketConditions:
    """Market conditions data structure."""
    bid: float
    ask: float
    last: float
    volume: int
    volatility: float
    spread_bps: float
    liquidity_score: float
    trend: str  # 'UP', 'DOWN', 'NEUTRAL'

@dataclass
class ExecutionPlan:
    """Execution plan data structure."""
    algorithm: str
    order_slices: List[Dict[str, Any]]
    estimated_cost: float
    estimated_time: float
    risk_score: float
    confidence: float
    ai_insights: Dict[str, Any]

@dataclass
class ExecutionResult:
    """Execution result data structure."""
    success: bool
    filled_quantity: int
    average_price: float
    slippage_bps: float
    execution_time: float
    algorithm_used: str
    metadata: Dict[str, Any]

# ==============================================================================
# EXECUTION STRATEGY AGENT CLASS
# ==============================================================================

class SpyderX07_ExecutionStrategyAgent:
    """
    AI-Enhanced Order Execution Strategy Agent.
    
    This agent optimizes order execution using AI to minimize market impact,
    reduce slippage, and ensure best execution for SPY options trades.
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL, 
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the Execution Strategy Agent.
        
        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()
        
        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
        
        # Performance tracking
        self.execution_history = deque(maxlen=1000)
        self.algorithm_performance = {algo: {'success': 0, 'total': 0} 
                                     for algo in EXECUTION_ALGORITHMS}
    
    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ==========================================================================
    # MAIN EXECUTION METHODS
    # ==========================================================================
    
    async def execute_order(self, request: ExecutionRequest, 
                          market: MarketConditions) -> ExecutionResult:
        """
        Execute an order with AI-optimized strategy.
        
        Args:
            request: Execution request details
            market: Current market conditions
            
        Returns:
            ExecutionResult object
        """
        self.logger.info(f"Executing order: {request.symbol} {request.side} "
                        f"{request.quantity}")
        
        try:
            # Create execution plan
            plan = await self._create_execution_plan(request, market)
            
            # Execute the plan
            result = await self._execute_plan(request, plan, market)
            
            # Track performance
            self._track_performance(plan.algorithm, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                filled_quantity=0,
                average_price=0.0,
                slippage_bps=0.0,
                execution_time=0.0,
                algorithm_used="NONE",
                metadata={'error': str(e)}
            )
    
    async def _create_execution_plan(self, request: ExecutionRequest,
                                   market: MarketConditions) -> ExecutionPlan:
        """Create AI-optimized execution plan."""
        # Get AI recommendation
        ai_recommendation = await self._get_ai_execution_strategy(request, market)
        
        # Select algorithm
        algorithm = self._select_algorithm(request, market, ai_recommendation)
        
        # Create order slices
        slices = self._create_order_slices(request, algorithm, market)
        
        # Estimate costs and risks
        est_cost = self._estimate_execution_cost(request, market, algorithm)
        est_time = self._estimate_execution_time(request, algorithm)
        risk_score = self._calculate_risk_score(request, market, algorithm)
        
        return ExecutionPlan(
            algorithm=algorithm,
            order_slices=slices,
            estimated_cost=est_cost,
            estimated_time=est_time,
            risk_score=risk_score,
            confidence=ai_recommendation.get('confidence', 0.7),
            ai_insights=ai_recommendation
        )
    
    async def _execute_plan(self, request: ExecutionRequest,
                          plan: ExecutionPlan,
                          market: MarketConditions) -> ExecutionResult:
        """Execute the trading plan."""
        start_time = datetime.now()
        filled_quantity = 0
        total_cost = 0.0
        
        # Execute order slices
        for slice_order in plan.order_slices:
            slice_result = await self._execute_slice(slice_order, market)
            filled_quantity += slice_result['filled']
            total_cost += slice_result['cost']
            
            # Check if we should continue
            if filled_quantity >= request.quantity:
                break
        
        # Calculate results
        avg_price = total_cost / filled_quantity if filled_quantity > 0 else 0
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Calculate slippage
        if request.side == 'BUY':
            slippage_bps = ((avg_price - market.ask) / market.ask) * 10000
        else:
            slippage_bps = ((market.bid - avg_price) / market.bid) * 10000
        
        return ExecutionResult(
            success=filled_quantity == request.quantity,
            filled_quantity=filled_quantity,
            average_price=avg_price,
            slippage_bps=slippage_bps,
            execution_time=execution_time,
            algorithm_used=plan.algorithm,
            metadata={
                'plan_confidence': plan.confidence,
                'market_conditions': market.__dict__
            }
        )
    
    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================
    
    async def _get_ai_execution_strategy(self, request: ExecutionRequest,
                                       market: MarketConditions) -> Dict[str, Any]:
        """Get AI recommendation for execution strategy."""
        if not self.ollama_client:
            return self._get_fallback_strategy(request, market)
        
        prompt = f"""Analyze this order execution scenario and recommend the best execution strategy:

Order Details:
- Symbol: {request.symbol}
- Side: {request.side}
- Quantity: {request.quantity}
- Order Type: {request.order_type.value}
- Urgency: {request.urgency.value}

Market Conditions:
- Bid/Ask: ${market.bid:.2f}/${market.ask:.2f}
- Spread: {market.spread_bps:.1f} bps
- Volume: {market.volume:,}
- Volatility: {market.volatility:.2%}
- Liquidity Score: {market.liquidity_score:.2f}
- Trend: {market.trend}

Available Algorithms: {', '.join(EXECUTION_ALGORITHMS)}

Provide a JSON response with:
{{
    "recommended_algorithm": "algorithm_name",
    "reasoning": "explanation",
    "slice_strategy": "how to slice the order",
    "timing": "optimal timing approach",
    "risk_factors": ["key risks"],
    "confidence": 0.0-1.0
}}"""
        
        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )
            
            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1
            
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return self._get_fallback_strategy(request, market)
                
        except Exception as e:
            self.logger.error(f"AI execution strategy failed: {e}")
            return self._get_fallback_strategy(request, market)
    
    def _get_fallback_strategy(self, request: ExecutionRequest,
                              market: MarketConditions) -> Dict[str, Any]:
        """Fallback strategy when AI is unavailable."""
        # Rule-based algorithm selection
        if request.urgency == ExecutionUrgency.CRITICAL:
            algorithm = "SNIPER"
        elif market.liquidity_score < 0.3:
            algorithm = "ICEBERG"
        elif market.volatility > 0.02:
            algorithm = "ADAPTIVE"
        elif request.quantity > 50:
            algorithm = "VWAP"
        else:
            algorithm = "TWAP"
        
        return {
            'recommended_algorithm': algorithm,
            'reasoning': 'Rule-based selection',
            'slice_strategy': 'Equal slices over time',
            'timing': 'Distribute evenly',
            'risk_factors': ['Market impact', 'Slippage'],
            'confidence': 0.6
        }
    
    # ==========================================================================
    # EXECUTION ALGORITHM METHODS
    # ==========================================================================
    
    def _select_algorithm(self, request: ExecutionRequest,
                         market: MarketConditions,
                         ai_rec: Dict[str, Any]) -> str:
        """Select execution algorithm based on conditions and AI recommendation."""
        recommended = ai_rec.get('recommended_algorithm', 'TWAP')
        
        # Validate recommendation
        if recommended in EXECUTION_ALGORITHMS:
            # Check if conditions support the recommendation
            if self._validate_algorithm_choice(recommended, request, market):
                return recommended
        
        # Fallback to best performing algorithm
        return self._get_best_performing_algorithm()
    
    def _create_order_slices(self, request: ExecutionRequest,
                           algorithm: str,
                           market: MarketConditions) -> List[Dict[str, Any]]:
        """Create order slices based on algorithm."""
        slices = []
        
        if algorithm == "TWAP":
            # Time-weighted slices
            num_slices = min(10, request.quantity // 10)
            slice_size = request.quantity // num_slices
            interval = self.config['execution_window_minutes'] / num_slices
            
            for i in range(num_slices):
                slices.append({
                    'size': slice_size,
                    'delay_minutes': i * interval,
                    'type': request.order_type.value
                })
                
        elif algorithm == "VWAP":
            # Volume-weighted slices
            # Simplified: heavier during high volume periods
            volume_profile = [0.1, 0.15, 0.25, 0.25, 0.15, 0.1]
            for i, weight in enumerate(volume_profile):
                slices.append({
                    'size': int(request.quantity * weight),
                    'delay_minutes': i * 0.5,
                    'type': request.order_type.value
                })
                
        elif algorithm == "ICEBERG":
            # Show only small portions
            visible_size = min(10, request.quantity // 10)
            num_slices = request.quantity // visible_size
            
            for i in range(num_slices):
                slices.append({
                    'size': visible_size,
                    'delay_minutes': i * 0.1,
                    'type': request.order_type.value,
                    'hidden': True
                })
                
        elif algorithm == "SNIPER":
            # Single aggressive order
            slices.append({
                'size': request.quantity,
                'delay_minutes': 0,
                'type': 'MARKET' if request.urgency == ExecutionUrgency.CRITICAL
                        else request.order_type.value
            })
            
        else:  # ADAPTIVE or POV
            # Adaptive slicing based on conditions
            if market.volatility > 0.02:
                # More slices in volatile markets
                num_slices = min(20, request.quantity // 5)
            else:
                num_slices = min(10, request.quantity // 10)
                
            slice_size = request.quantity // num_slices
            for i in range(num_slices):
                slices.append({
                    'size': slice_size,
                    'delay_minutes': i * 0.25,
                    'type': request.order_type.value,
                    'adaptive': True
                })
        
        return slices
    
    async def _execute_slice(self, slice_order: Dict[str, Any],
                           market: MarketConditions) -> Dict[str, Any]:
        """Execute a single order slice."""
        # Simulate execution (in real implementation, this would call broker API)
        await asyncio.sleep(0.1)  # Simulate network delay
        
        # Calculate fill price with slippage
        if slice_order.get('type') == 'MARKET':
            fill_price = market.ask if slice_order.get('side', 'BUY') == 'BUY' else market.bid
            # Add random slippage
            slippage = random.uniform(0, market.spread_bps / 10000)
            fill_price *= (1 + slippage) if slice_order.get('side', 'BUY') == 'BUY' else (1 - slippage)
        else:
            # Limit order - might get better price
            fill_price = market.last
        
        return {
            'filled': slice_order['size'],
            'cost': slice_order['size'] * fill_price,
            'price': fill_price
        }
    
    # ==========================================================================
    # ANALYSIS AND OPTIMIZATION METHODS
    # ==========================================================================
    
    def _estimate_execution_cost(self, request: ExecutionRequest,
                               market: MarketConditions,
                               algorithm: str) -> float:
        """Estimate execution cost including slippage and fees."""
        base_cost = request.quantity * market.last
        
        # Estimate slippage based on algorithm and conditions
        slippage_factor = {
            'SNIPER': market.spread_bps * 1.5,
            'TWAP': market.spread_bps * 0.7,
            'VWAP': market.spread_bps * 0.6,
            'ICEBERG': market.spread_bps * 0.8,
            'ADAPTIVE': market.spread_bps * 0.5,
            'POV': market.spread_bps * 0.7
        }.get(algorithm, market.spread_bps)
        
        # Adjust for market conditions
        if market.volatility > 0.02:
            slippage_factor *= 1.5
        if market.liquidity_score < 0.5:
            slippage_factor *= 1.3
            
        slippage_cost = base_cost * (slippage_factor / 10000)
        
        # Add estimated fees (simplified)
        fees = base_cost * 0.0001  # 1 bps
        
        return base_cost + slippage_cost + fees
    
    def _estimate_execution_time(self, request: ExecutionRequest,
                               algorithm: str) -> float:
        """Estimate execution time in seconds."""
        base_time = {
            'SNIPER': 1.0,
            'TWAP': self.config['execution_window_minutes'] * 60,
            'VWAP': self.config['execution_window_minutes'] * 60,
            'ICEBERG': request.quantity * 0.5,
            'ADAPTIVE': self.config['execution_window_minutes'] * 30,
            'POV': self.config['execution_window_minutes'] * 45
        }.get(algorithm, 60.0)
        
        return base_time
    
    def _calculate_risk_score(self, request: ExecutionRequest,
                            market: MarketConditions,
                            algorithm: str) -> float:
        """Calculate execution risk score (0-1, higher is riskier)."""
        risk_factors = []
        
        # Size risk
        size_risk = min(1.0, request.quantity / 100)
        risk_factors.append(size_risk * 0.3)
        
        # Market risk
        market_risk = market.volatility * 10  # Scale volatility
        risk_factors.append(market_risk * 0.3)
        
        # Liquidity risk
        liquidity_risk = 1.0 - market.liquidity_score
        risk_factors.append(liquidity_risk * 0.2)
        
        # Algorithm risk
        algo_risk = {
            'SNIPER': 0.8,  # High impact risk
            'TWAP': 0.3,
            'VWAP': 0.3,
            'ICEBERG': 0.5,
            'ADAPTIVE': 0.4,
            'POV': 0.4
        }.get(algorithm, 0.5)
        risk_factors.append(algo_risk * 0.2)
        
        return min(1.0, sum(risk_factors))
    
    def _validate_algorithm_choice(self, algorithm: str,
                                 request: ExecutionRequest,
                                 market: MarketConditions) -> bool:
        """Validate if algorithm is appropriate for conditions."""
        if algorithm == "SNIPER":
            # Only for urgent small orders
            return (request.urgency in [ExecutionUrgency.HIGH, ExecutionUrgency.CRITICAL] and
                   request.quantity <= 50)
        
        elif algorithm == "ICEBERG":
            # For large orders in thin markets
            return (request.quantity > 50 and market.liquidity_score < 0.5)
        
        elif algorithm in ["TWAP", "VWAP"]:
            # For medium to large orders with time flexibility
            return (request.urgency not in [ExecutionUrgency.CRITICAL] and
                   request.quantity > 20)
        
        return True  # Default: allow
    
    def _get_best_performing_algorithm(self) -> str:
        """Get the best performing algorithm based on history."""
        best_algo = "TWAP"  # Default
        best_rate = 0.0
        
        for algo, stats in self.algorithm_performance.items():
            if stats['total'] > 10:  # Minimum sample size
                success_rate = stats['success'] / stats['total']
                if success_rate > best_rate:
                    best_rate = success_rate
                    best_algo = algo
        
        return best_algo
    
    def _track_performance(self, algorithm: str, result: ExecutionResult):
        """Track algorithm performance."""
        self.algorithm_performance[algorithm]['total'] += 1
        if result.success:
            self.algorithm_performance[algorithm]['success'] += 1
        
        self.execution_history.append({
            'timestamp': datetime.now(),
            'algorithm': algorithm,
            'success': result.success,
            'slippage_bps': result.slippage_bps,
            'execution_time': result.execution_time
        })
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get execution performance statistics."""
        if not self.execution_history:
            return {'message': 'No execution history available'}
        
        recent_executions = list(self.execution_history)[-100:]
        
        success_rate = sum(1 for e in recent_executions if e['success']) / len(recent_executions)
        avg_slippage = statistics.mean(e['slippage_bps'] for e in recent_executions)
        avg_time = statistics.mean(e['execution_time'] for e in recent_executions)
        
        algo_stats = {}
        for algo, stats in self.algorithm_performance.items():
            if stats['total'] > 0:
                algo_stats[algo] = {
                    'success_rate': stats['success'] / stats['total'],
                    'total_executions': stats['total']
                }
        
        return {
            'overall_success_rate': success_rate,
            'average_slippage_bps': avg_slippage,
            'average_execution_time': avg_time,
            'algorithm_performance': algo_stats,
            'total_executions': len(self.execution_history)
        }
    
    def update_config(self, **kwargs):
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
                self.logger.info(f"Updated config: {key} = {value}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_execution_strategy_agent(model_name: str = DEFAULT_MODEL,
                                  temperature: float = DEFAULT_TEMPERATURE) -> SpyderX07_ExecutionStrategyAgent:
    """
    Factory function to create Execution Strategy Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX07_ExecutionStrategyAgent instance
    """
    return SpyderX07_ExecutionStrategyAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX07_ExecutionStrategyAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_execution_strategy_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_execution_agent():
    """Test the Execution Strategy Agent functionality."""
    print("="*80)
    print("Testing SpyderX07_ExecutionStrategyAgent")
    print("="*80)
    
    agent = create_execution_strategy_agent()
    
    # Test case 1: Market order execution
    print("\nTest 1: Market Order Execution")
    print("-"*40)
    
    request = ExecutionRequest(
        symbol="SPY",
        quantity=50,
        side="BUY",
        order_type=MARKET,
        urgency=ExecutionUrgency.HIGH
    )
    
    market = MarketConditions(
        bid=450.00,
        ask=450.05,
        last=450.02,
        volume=1000000,
        volatility=0.015,
        spread_bps=1.1,
        liquidity_score=0.8,
        trend="UP"
    )
    
    result = await agent.execute_order(request, market)
    print(f"Execution Result:")
    print(f"  Success: {result.success}")
    print(f"  Filled: {result.filled_quantity}/{request.quantity}")
    print(f"  Avg Price: ${result.average_price:.2f}")
    print(f"  Slippage: {result.slippage_bps:.1f} bps")
    print(f"  Algorithm: {result.algorithm_used}")
    print(f"  Time: {result.execution_time:.1f}s")
    
    # Test case 2: Large order in illiquid market
    print("\nTest 2: Large Order in Illiquid Market")
    print("-"*40)
    
    request2 = ExecutionRequest(
        symbol="SPY",
        quantity=200,
        side="SELL",
        order_type=LIMIT,
        urgency=ExecutionUrgency.LOW,
        price_limit=449.90
    )
    
    market2 = MarketConditions(
        bid=449.95,
        ask=450.10,
        last=450.00,
        volume=500000,
        volatility=0.025,
        spread_bps=3.3,
        liquidity_score=0.4,
        trend="DOWN"
    )
    
    result2 = await agent.execute_order(request2, market2)
    print(f"Execution Result:")
    print(f"  Success: {result2.success}")
    print(f"  Filled: {result2.filled_quantity}/{request2.quantity}")
    print(f"  Avg Price: ${result2.average_price:.2f}")
    print(f"  Slippage: {result2.slippage_bps:.1f} bps")
    print(f"  Algorithm: {result2.algorithm_used}")
    print(f"  Time: {result2.execution_time:.1f}s")
    
    # Test case 3: Critical urgency order
    print("\nTest 3: Critical Urgency Order")
    print("-"*40)
    
    request3 = ExecutionRequest(
        symbol="SPY",
        quantity=30,
        side="BUY",
        order_type=MARKET,
        urgency=ExecutionUrgency.CRITICAL
    )
    
    market3 = MarketConditions(
        bid=451.00,
        ask=451.15,
        last=451.10,
        volume=2000000,
        volatility=0.035,
        spread_bps=3.3,
        liquidity_score=0.9,
        trend="UP"
    )
    
    result3 = await agent.execute_order(request3, market3)
    print(f"Execution Result:")
    print(f"  Success: {result3.success}")
    print(f"  Filled: {result3.filled_quantity}/{request3.quantity}")
    print(f"  Avg Price: ${result3.average_price:.2f}")
    print(f"  Slippage: {result3.slippage_bps:.1f} bps")
    print(f"  Algorithm: {result3.algorithm_used}")
    print(f"  Time: {result3.execution_time:.1f}s")
    
    # Show performance statistics
    print("\nPerformance Statistics")
    print("-"*40)
    stats = agent.get_performance_stats()
    print(f"Overall Success Rate: {stats['overall_success_rate']:.1%}")
    print(f"Average Slippage: {stats['average_slippage_bps']:.1f} bps")
    print(f"Average Execution Time: {stats['average_execution_time']:.1f}s")
    print("\nAlgorithm Performance:")
    for algo, perf in stats['algorithm_performance'].items():
        print(f"  {algo}: {perf['success_rate']:.1%} "
              f"({perf['total_executions']} executions)")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print(f"Initializing {__name__}")
    print(f"Ollama Available: {OLLAMA_AVAILABLE}")
    
    # Run async tests
    asyncio.run(test_execution_agent())
    
    print("\n" + "="*80)
    print("SpyderX07_ExecutionStrategyAgent module loaded successfully!")
    print("="*80)