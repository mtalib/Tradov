#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX07_ExecutionStrategyAgent.py
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
import asyncio
import json
import logging
import threading
import os
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import random
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.info("Warning: Ollama not installed. AI features will be limited.")

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
DEFAULT_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma4:e4b")
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
    price_limit: float | None = None
    stop_price: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    metadata: dict[str, Any] = field(default_factory=dict)

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
    order_slices: list[dict[str, Any]]
    estimated_cost: float
    estimated_time: float
    risk_score: float
    confidence: float
    ai_insights: dict[str, Any]

@dataclass
class ExecutionResult:
    """Execution result data structure."""
    success: bool
    filled_quantity: int
    average_price: float
    slippage_bps: float
    execution_time: float
    algorithm_used: str
    metadata: dict[str, Any]

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
                self.logger.error("Failed to connect to Ollama: %s", e)

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
            self.logger.error("Execution failed: %s", e)
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
                                       market: MarketConditions) -> dict[str, Any]:
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
            self.logger.error("AI execution strategy failed: %s", e)
            return self._get_fallback_strategy(request, market)

    def _get_fallback_strategy(self, request: ExecutionRequest,
                              market: MarketConditions) -> dict[str, Any]:
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
                         ai_rec: dict[str, Any]) -> str:
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
                           market: MarketConditions) -> list[dict[str, Any]]:
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

    async def _execute_slice(self, slice_order: dict[str, Any],
                           market: MarketConditions) -> dict[str, Any]:
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

    def get_performance_stats(self) -> dict[str, Any]:
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
                self.logger.info("Updated config: %s = %s", key, value)

    # --------------------------------------------------------------------------
    # STABLE-BASELINES3: RL EXECUTION STRATEGY
    # --------------------------------------------------------------------------

    def create_execution_rl_env(self):
        """
        Create an RL environment for TWAP/VWAP execution scheduling.

        The agent learns optimal order slicing and timing to minimize
        market impact and improve execution quality.

        Returns:
            gym.Env instance for SB3 training.
        """
        try:
            import gymnasium as gym
            from gymnasium import spaces
        except ImportError:
            try:
                import gym
                from gym import spaces
            except ImportError:
                self.logger.warning("gym/gymnasium not installed")
                return None

        import numpy as _np

        class ExecutionEnvironment(gym.Env):
            """
            RL environment for order execution optimization.

            Observation: [remaining_qty_pct, time_remaining_pct, spread,
                         volume_ratio, volatility, vwap_deviation,
                         momentum, inventory_risk]
            Action: 0=wait, 1=small_slice, 2=medium_slice, 3=large_slice, 4=aggressive
            Reward: -market_impact - timing_risk + execution_improvement
            """
            metadata = {'render_modes': []}

            def __init__(self):
                super().__init__()
                self.observation_space = spaces.Box(
                    low=-5.0, high=5.0, shape=(8,), dtype=_np.float32)
                self.action_space = spaces.Discrete(5)
                self.step_count = 0
                self.max_steps = 78  # ~6.5 hours in 5-min bars

            def reset(self, seed=None, options=None):
                super().reset(seed=seed)
                self.step_count = 0
                self.remaining_qty = 1.0
                self._state = _np.array([
                    1.0,                           # remaining_qty_pct
                    1.0,                           # time_remaining_pct
                    _np.random.uniform(0.01, 0.05), # spread
                    _np.random.uniform(0.5, 2.0),  # volume_ratio
                    _np.random.uniform(0.1, 0.4),  # volatility
                    0.0,                           # vwap_deviation
                    _np.random.uniform(-0.5, 0.5), # momentum
                    0.0,                           # inventory_risk
                ], dtype=_np.float32)
                return self._state, {}

            def step(self, action):
                self.step_count += 1
                slice_sizes = [0, 0.05, 0.15, 0.30, 0.50]
                slice_pct = slice_sizes[action]
                executed = min(slice_pct, self.remaining_qty)
                self.remaining_qty -= executed

                # Market impact model
                impact = executed * self._state[2] * (1 + executed * 5)
                timing_risk = self.remaining_qty * self._state[4] * 0.01

                reward = -impact * 100 - timing_risk * 50
                if self.remaining_qty <= 0.01:
                    reward += 10  # completion bonus

                # Evolve state
                self._state[0] = self.remaining_qty
                self._state[1] = max(0, 1 - self.step_count / self.max_steps)
                self._state[3] = _np.clip(
                    self._state[3] + _np.random.normal(0, 0.1), 0.1, 5.0)
                self._state[5] += _np.random.normal(0, 0.01)
                self._state[7] = self.remaining_qty * self._state[4]

                done = self.step_count >= self.max_steps or self.remaining_qty <= 0.01
                return self._state.copy(), float(reward), done, False, {}

        return ExecutionEnvironment()

    def train_execution_policy(self, total_timesteps: int = 50000) -> Any | None:
        """
        Train a PPO policy for TWAP/VWAP execution optimization.

        Args:
            total_timesteps: Training steps.

        Returns:
            Trained SB3 model or None.
        """
        env = self.create_execution_rl_env()
        if env is None:
            return None

        try:
            from stable_baselines3 import PPO
            model = PPO('MlpPolicy', env, verbose=0,
                       learning_rate=3e-4, n_steps=2048)
            model.learn(total_timesteps=total_timesteps)
            self.logger.info("Execution RL policy trained: %s steps", total_timesteps)
            return model
        except ImportError:
            self.logger.warning("stable-baselines3 not installed")
            return None

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
_module_instance_lock = threading.Lock()


def get_module_instance() -> SpyderX07_ExecutionStrategyAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        with _module_instance_lock:
            if _module_instance is None:
                _module_instance = create_execution_strategy_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_execution_agent():
    """Test the Execution Strategy Agent functionality."""
    logging.info("="*80)
    logging.info("Testing SpyderX07_ExecutionStrategyAgent")
    logging.info("="*80)

    agent = create_execution_strategy_agent()

    # Test case 1: Market order execution
    logging.info("\nTest 1: Market Order Execution")
    logging.info("-"*40)

    request = ExecutionRequest(
        symbol="SPY",
        quantity=50,
        side="BUY",
        order_type=OrderType.MARKET,
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
    logging.info("Execution Result:")
    logging.info("  Success: %s", result.success)
    logging.info("  Filled: %s/%s", result.filled_quantity, request.quantity)
    logging.info(f"  Avg Price: ${result.average_price:.2f}")
    logging.info(f"  Slippage: {result.slippage_bps:.1f} bps")
    logging.info("  Algorithm: %s", result.algorithm_used)
    logging.info(f"  Time: {result.execution_time:.1f}s")

    # Test case 2: Large order in illiquid market
    logging.info("\nTest 2: Large Order in Illiquid Market")
    logging.info("-"*40)

    request2 = ExecutionRequest(
        symbol="SPY",
        quantity=200,
        side="SELL",
        order_type=OrderType.LIMIT,
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
    logging.info("Execution Result:")
    logging.info("  Success: %s", result2.success)
    logging.info("  Filled: %s/%s", result2.filled_quantity, request2.quantity)
    logging.info(f"  Avg Price: ${result2.average_price:.2f}")
    logging.info(f"  Slippage: {result2.slippage_bps:.1f} bps")
    logging.info("  Algorithm: %s", result2.algorithm_used)
    logging.info(f"  Time: {result2.execution_time:.1f}s")

    # Test case 3: Critical urgency order
    logging.info("\nTest 3: Critical Urgency Order")
    logging.info("-"*40)

    request3 = ExecutionRequest(
        symbol="SPY",
        quantity=30,
        side="BUY",
        order_type=OrderType.MARKET,
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
    logging.info("Execution Result:")
    logging.info("  Success: %s", result3.success)
    logging.info("  Filled: %s/%s", result3.filled_quantity, request3.quantity)
    logging.info(f"  Avg Price: ${result3.average_price:.2f}")
    logging.info(f"  Slippage: {result3.slippage_bps:.1f} bps")
    logging.info("  Algorithm: %s", result3.algorithm_used)
    logging.info(f"  Time: {result3.execution_time:.1f}s")

    # Show performance statistics
    logging.info("\nPerformance Statistics")
    logging.info("-"*40)
    stats = agent.get_performance_stats()
    logging.info(f"Overall Success Rate: {stats['overall_success_rate']:.1%}")
    logging.info(f"Average Slippage: {stats['average_slippage_bps']:.1f} bps")
    logging.info(f"Average Execution Time: {stats['average_execution_time']:.1f}s")
    logging.info("\nAlgorithm Performance:")
    for algo, perf in stats['algorithm_performance'].items():
        logging.info(f"  {algo}: {perf['success_rate']:.1%} "
              f"({perf['total_executions']} executions)")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":

    # Run async tests
    asyncio.run(test_execution_agent())

