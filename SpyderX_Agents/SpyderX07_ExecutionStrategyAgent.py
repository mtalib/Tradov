#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX07_ExecutionStrategyAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Order Execution and Smart Routing

Description:
    This agent replaces traditional market microstructure modules with an
    intelligent AI system that optimizes order execution, predicts liquidity,
    minimizes market impact, and adapts execution algorithms in real-time.
    It ensures best execution through intelligent decision-making about when,
    where, and how to execute orders in the options market.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-16
Last Updated: 2025-06-19 Time: 11:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from enum import Enum, auto
from collections import defaultdict, deque
import hashlib

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats

# Ollama integration
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    print("Warning: ollama package not installed. Install with: pip install ollama")
    OLLAMA_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Note: In standalone mode, we're not importing from other Spyder modules
# In production, these would be imported from the Spyder ecosystem

# ==============================================================================
# CONSTANTS
# ==============================================================================
# LLM Configuration
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_TEMPERATURE = 0.2  # Lower for execution decisions
MAX_TOKENS = 2000

# Execution Configuration
MAX_ORDER_SLICE = 1000
MIN_ORDER_SIZE = 1
DEFAULT_PARTICIPATION_RATE = 0.1
MAX_SPREAD_CROSS = 0.02  # 2% max spread to cross
URGENCY_THRESHOLD = 0.8

# Market Hours
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
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
    ADAPTIVE = "adaptive"

class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class VenueType(Enum):
    """Execution venue types"""
    EXCHANGE = "exchange"
    DARK_POOL = "dark_pool"
    MARKET_MAKER = "market_maker"
    ECN = "ecn"

class UrgencyLevel(Enum):
    """Order urgency levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Order:
    """Order details"""
    order_id: str
    symbol: str
    quantity: int
    side: str  # 'buy' or 'sell'
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    strategy_tag: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    status: OrderStatus = OrderStatus.PENDING

@dataclass
class MarketMicrostructure:
    """Market microstructure data"""
    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last_price: float
    last_size: int
    total_volume: int
    quote_count: int
    trade_count: int
    volatility: float
    spread: float
    depth_imbalance: float

@dataclass
class LiquidityProfile:
    """Liquidity analysis for a symbol"""
    symbol: str
    avg_spread: float
    avg_size: float
    liquidity_score: float
    best_execution_times: List[time]
    venue_distribution: Dict[VenueType, float]
    impact_estimate: float
    urgency_cost: Dict[UrgencyLevel, float]

@dataclass
class ExecutionPlan:
    """Execution plan for an order"""
    order: Order
    algorithm: ExecutionAlgo
    slices: List[Dict[str, Any]]
    venues: List[VenueType]
    timing_strategy: str
    expected_cost: float
    expected_duration: timedelta
    risk_parameters: Dict[str, float]

@dataclass
class ExecutionAnalytics:
    """Post-execution analytics"""
    order_id: str
    algorithm_used: ExecutionAlgo
    execution_time: timedelta
    avg_price: float
    slippage: float
    market_impact: float
    total_cost: float
    venue_breakdown: Dict[VenueType, float]
    performance_vs_benchmark: float

@dataclass
class MarketImpactModel:
    """Market impact prediction model"""
    symbol: str
    temporary_impact: float
    permanent_impact: float
    decay_rate: float
    confidence: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX07_ExecutionStrategyAgent:
    """
    AI-Enhanced Execution Strategy Agent.
    
    This agent provides intelligent order execution by predicting liquidity,
    optimizing routing, minimizing market impact, and adapting execution
    algorithms in real-time using Ollama for decision support.
    
    Attributes:
        logger: Module logger instance
        config: Agent configuration
        ollama_client: Ollama LLM client
        active_orders: Currently active orders
        execution_analytics: Historical execution performance
        
    Example:
        >>> agent = SpyderX07_ExecutionStrategyAgent()
        >>> plan = await agent.create_execution_plan(order, market_data)
        >>> result = await agent.execute_order(plan)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Execution Strategy Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # LLM configuration
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        self.max_order_slice = self.config.get('max_order_slice', MAX_ORDER_SLICE)
        
        # Initialize Ollama client
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                # Test if Ollama is running
                ollama.list()
                self.ollama_client = ollama
                self.logger.info(f"Ollama initialized with model: {self.model_name}")
            except Exception as e:
                self.logger.error(f"Failed to connect to Ollama: {e}")
                self.logger.info("Agent will work with reduced AI capabilities")
        
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
        self.impact_models: Dict[str, MarketImpactModel] = {}
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
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    async def create_execution_plan(
        self,
        order: Order,
        market_data: Optional[MarketMicrostructure] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> ExecutionPlan:
        """
        Create optimal execution plan for an order.
        
        Args:
            order: Order to execute
            market_data: Current market microstructure
            constraints: Execution constraints
            
        Returns:
            Detailed execution plan
        """
        start_time = datetime.now()
        
        # Analyze order characteristics
        order_analysis = self._analyze_order(order)
        
        # Get or update liquidity profile
        liquidity = await self._analyze_liquidity(order.symbol, market_data)
        
        # Predict market impact
        impact_model = await self._predict_market_impact(order, liquidity)
        
        # Select optimal algorithm
        if self.ollama_client:
            algorithm = await self._get_ai_algo_recommendation(
                order,
                liquidity,
                impact_model,
                constraints
            )
        else:
            algorithm = self._select_algorithm_rules(order, liquidity)
        
        # Create execution slices
        slices = self._create_execution_slices(order, algorithm, liquidity)
        
        # Determine venue routing
        venues = self._determine_venues(order, liquidity)
        
        # Calculate expected costs
        expected_cost = self._calculate_expected_cost(
            order,
            algorithm,
            impact_model,
            liquidity
        )
        
        # Estimate execution duration
        expected_duration = self._estimate_duration(order, algorithm, liquidity)
        
        # Create plan
        plan = ExecutionPlan(
            order=order,
            algorithm=algorithm,
            slices=slices,
            venues=venues,
            timing_strategy=self._get_timing_strategy(order, market_data),
            expected_cost=expected_cost,
            expected_duration=expected_duration,
            risk_parameters={
                'max_slippage': constraints.get('max_slippage', 0.02) if constraints else 0.02,
                'max_impact': constraints.get('max_impact', 0.01) if constraints else 0.01,
                'urgency_premium': self._calculate_urgency_premium(order.urgency)
            }
        )
        
        # Store plan
        self.execution_plans[order.order_id] = plan
        
        # Log planning time
        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"Execution plan created for {order.order_id} using {algorithm.value} "
            f"in {elapsed:.2f} seconds"
        )
        
        return plan
    
    async def execute_order(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool = True
    ) -> ExecutionAnalytics:
        """
        Execute order according to plan.
        
        Args:
            plan: Execution plan
            real_time_updates: Whether to adapt in real-time
            
        Returns:
            Execution analytics
        """
        self.logger.info(f"Starting execution of order {plan.order.order_id}")
        
        # Mark order as active
        self.active_orders[plan.order.order_id] = plan.order
        plan.order.status = OrderStatus.SUBMITTED
        
        # Execute using selected algorithm
        if plan.algorithm in self.algo_implementations:
            execution_result = await self.algo_implementations[plan.algorithm](
                plan,
                real_time_updates
            )
        else:
            # Default to simple execution
            execution_result = await self._execute_simple(plan)
        
        # Calculate analytics
        analytics = self._calculate_execution_analytics(
            plan,
            execution_result
        )
        
        # Store analytics
        self.execution_analytics.append(analytics)
        self._update_performance_tracking(analytics)
        
        # Clean up
        if plan.order.order_id in self.active_orders:
            del self.active_orders[plan.order.order_id]
        
        self.logger.info(
            f"Execution completed for {plan.order.order_id}. "
            f"Avg price: {analytics.avg_price:.2f}, "
            f"Slippage: {analytics.slippage:.2%}"
        )
        
        return analytics
    
    async def analyze_market_microstructure(
        self,
        symbol: str,
        lookback_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze market microstructure for a symbol.
        
        Args:
            symbol: Symbol to analyze
            lookback_minutes: Historical data to consider
            
        Returns:
            Microstructure analysis
        """
        # Get recent data
        recent_data = self._get_recent_microstructure(symbol, lookback_minutes)
        
        if not recent_data:
            return {"error": "No microstructure data available"}
        
        # Calculate metrics
        analysis = {
            'avg_spread': np.mean([d.spread for d in recent_data]),
            'spread_volatility': np.std([d.spread for d in recent_data]),
            'avg_depth_imbalance': np.mean([d.depth_imbalance for d in recent_data]),
            'liquidity_score': self._calculate_liquidity_score(recent_data),
            'best_execution_times': self._identify_best_execution_times(recent_data),
            'volatility_regime': self._classify_volatility_regime(recent_data)
        }
        
        # Get AI insights if available
        if self.ollama_client:
            ai_insights = await self._get_ai_microstructure_insights(
                symbol,
                analysis,
                recent_data
            )
            analysis['ai_insights'] = ai_insights
        
        return analysis
    
    async def optimize_execution_parameters(
        self,
        order: Order,
        historical_executions: Optional[List[ExecutionAnalytics]] = None
    ) -> Dict[str, Any]:
        """
        Optimize execution parameters based on historical performance.
        
        Args:
            order: Order to optimize for
            historical_executions: Historical execution data
            
        Returns:
            Optimized parameters
        """
        # Use own history if not provided
        if not historical_executions:
            historical_executions = self._get_relevant_executions(order)
        
        # Analyze historical performance
        performance_analysis = self._analyze_execution_performance(
            historical_executions,
            order
        )
        
        # Get AI recommendations if available
        if self.ollama_client:
            recommendations = await self._get_ai_parameter_optimization(
                order,
                performance_analysis
            )
        else:
            recommendations = self._get_rule_based_optimization(
                order,
                performance_analysis
            )
        
        return {
            'recommended_algo': recommendations.get('algorithm', ExecutionAlgo.ADAPTIVE),
            'optimal_slice_size': recommendations.get('slice_size', 100),
            'participation_rate': recommendations.get('participation_rate', 0.1),
            'urgency_adjustment': recommendations.get('urgency_adjustment', 1.0),
            'venue_preferences': recommendations.get('venues', [VenueType.EXCHANGE])
        }
    
    def get_execution_performance(
        self,
        filter_by: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get execution performance summary.
        
        Args:
            filter_by: Optional filters (symbol, algo, date range)
            
        Returns:
            Performance metrics
        """
        analytics = self.execution_analytics
        
        # Apply filters
        if filter_by:
            if 'symbol' in filter_by:
                analytics = [a for a in analytics if self._get_order_by_id(a.order_id).symbol == filter_by['symbol']]
            if 'algorithm' in filter_by:
                analytics = [a for a in analytics if a.algorithm_used == filter_by['algorithm']]
        
        if not analytics:
            return {"message": "No execution data available"}
        
        # Calculate aggregate metrics
        return {
            'total_executions': len(analytics),
            'avg_slippage': np.mean([a.slippage for a in analytics]),
            'avg_market_impact': np.mean([a.market_impact for a in analytics]),
            'avg_execution_time': np.mean([a.execution_time.total_seconds() for a in analytics]),
            'total_cost': sum(a.total_cost for a in analytics),
            'algo_breakdown': self._get_algo_performance_breakdown(analytics),
            'venue_breakdown': self._get_venue_performance_breakdown(analytics)
        }
    
    # ==========================================================================
    # PRIVATE METHODS - ORDER ANALYSIS
    # ==========================================================================
    def _analyze_order(self, order: Order) -> Dict[str, Any]:
        """Analyze order characteristics."""
        return {
            'size_category': self._categorize_order_size(order.quantity),
            'urgency_score': self._score_urgency(order.urgency),
            'market_hours_remaining': self._get_market_hours_remaining(),
            'is_opening': self._is_opening_order(order),
            'is_closing': self._is_closing_order(order)
        }
    
    def _categorize_order_size(self, quantity: int) -> str:
        """Categorize order size."""
        if quantity < 10:
            return 'small'
        elif quantity < 100:
            return 'medium'
        elif quantity < 1000:
            return 'large'
        else:
            return 'block'
    
    def _score_urgency(self, urgency: UrgencyLevel) -> float:
        """Convert urgency level to numeric score."""
        scores = {
            UrgencyLevel.LOW: 0.2,
            UrgencyLevel.MEDIUM: 0.5,
            UrgencyLevel.HIGH: 0.8,
            UrgencyLevel.CRITICAL: 1.0
        }
        return scores.get(urgency, 0.5)
    
    def _get_market_hours_remaining(self) -> float:
        """Get hours remaining until market close."""
        now = datetime.now().time()
        
        if now < MARKET_OPEN:
            # Before market open
            return 6.5  # Full trading day
        elif now > MARKET_CLOSE:
            # After market close
            return 0.0
        else:
            # During market hours
            close_time = datetime.combine(datetime.now().date(), MARKET_CLOSE)
            now_time = datetime.now()
            return (close_time - now_time).total_seconds() / 3600
    
    def _is_opening_order(self, order: Order) -> bool:
        """Check if order is opening a position."""
        # Simplified check
        return order.strategy_tag and 'open' in order.strategy_tag.lower()
    
    def _is_closing_order(self, order: Order) -> bool:
        """Check if order is closing a position."""
        # Simplified check
        return order.strategy_tag and 'close' in order.strategy_tag.lower()
    
    # ==========================================================================
    # PRIVATE METHODS - LIQUIDITY ANALYSIS
    # ==========================================================================
    async def _analyze_liquidity(
        self,
        symbol: str,
        market_data: Optional[MarketMicrostructure] = None
    ) -> LiquidityProfile:
        """Analyze liquidity for a symbol."""
        # Check cache
        if symbol in self.liquidity_profiles:
            profile = self.liquidity_profiles[symbol]
            # Update if we have new market data
            if market_data:
                profile = self._update_liquidity_profile(profile, market_data)
        else:
            # Create new profile
            profile = await self._create_liquidity_profile(symbol, market_data)
        
        # Store in cache
        self.liquidity_profiles[symbol] = profile
        
        return profile
    
    async def _create_liquidity_profile(
        self,
        symbol: str,
        market_data: Optional[MarketMicrostructure] = None
    ) -> LiquidityProfile:
        """Create new liquidity profile."""
        # Use current market data or defaults
        if market_data:
            avg_spread = market_data.spread
            avg_size = (market_data.bid_size + market_data.ask_size) / 2
        else:
            avg_spread = 0.01  # 1 cent default
            avg_size = 100     # 100 contracts default
        
        # Calculate liquidity score
        liquidity_score = self._calculate_single_liquidity_score(avg_spread, avg_size)
        
        # Identify best execution times (simplified)
        best_times = [
            time(9, 45),   # After opening volatility
            time(11, 0),   # Mid-morning
            time(14, 30),  # Mid-afternoon
            time(15, 45)   # Before close
        ]
        
        # Venue distribution (simplified)
        venue_distribution = {
            VenueType.EXCHANGE: 0.7,
            VenueType.DARK_POOL: 0.2,
            VenueType.ECN: 0.1
        }
        
        # Impact estimate
        impact_estimate = avg_spread * 0.5  # Half spread as base impact
        
        # Urgency costs
        urgency_cost = {
            UrgencyLevel.LOW: impact_estimate * 0.5,
            UrgencyLevel.MEDIUM: impact_estimate * 1.0,
            UrgencyLevel.HIGH: impact_estimate * 2.0,
            UrgencyLevel.CRITICAL: impact_estimate * 3.0
        }
        
        return LiquidityProfile(
            symbol=symbol,
            avg_spread=avg_spread,
            avg_size=avg_size,
            liquidity_score=liquidity_score,
            best_execution_times=best_times,
            venue_distribution=venue_distribution,
            impact_estimate=impact_estimate,
            urgency_cost=urgency_cost
        )
    
    def _update_liquidity_profile(
        self,
        profile: LiquidityProfile,
        market_data: MarketMicrostructure
    ) -> LiquidityProfile:
        """Update existing liquidity profile with new data."""
        # Exponential moving average update
        alpha = 0.1
        
        profile.avg_spread = (1 - alpha) * profile.avg_spread + alpha * market_data.spread
        profile.avg_size = (1 - alpha) * profile.avg_size + alpha * (market_data.bid_size + market_data.ask_size) / 2
        profile.liquidity_score = self._calculate_single_liquidity_score(
            profile.avg_spread,
            profile.avg_size
        )
        
        return profile
    
    def _calculate_single_liquidity_score(self, spread: float, size: float) -> float:
        """Calculate liquidity score from spread and size."""
        # Lower spread and higher size = better liquidity
        spread_score = max(0, 1 - spread / 0.05)  # Normalize to 5 cent max
        size_score = min(1, size / 1000)          # Normalize to 1000 contracts
        
        return (spread_score + size_score) / 2
    
    # ==========================================================================
    # PRIVATE METHODS - MARKET IMPACT
    # ==========================================================================
    async def _predict_market_impact(
        self,
        order: Order,
        liquidity: LiquidityProfile
    ) -> MarketImpactModel:
        """Predict market impact for order."""
        # Check cache
        cache_key = f"{order.symbol}_{order.quantity}_{order.side}"
        if cache_key in self.impact_models:
            return self.impact_models[cache_key]
        
        # Calculate base impact
        participation_rate = order.quantity / (liquidity.avg_size * 100)  # Rough estimate
        
        # Temporary impact (simplified square-root model)
        temporary_impact = liquidity.avg_spread * np.sqrt(participation_rate) * 2
        
        # Permanent impact (simplified linear model)
        permanent_impact = liquidity.avg_spread * participation_rate * 0.5
        
        # Decay rate (how fast temporary impact dissipates)
        decay_rate = 0.7  # 70% decay per time unit
        
        # Confidence based on liquidity
        confidence = min(0.9, liquidity.liquidity_score + 0.3)
        
        model = MarketImpactModel(
            symbol=order.symbol,
            temporary_impact=temporary_impact,
            permanent_impact=permanent_impact,
            decay_rate=decay_rate,
            confidence=confidence
        )
        
        # Cache model
        self.impact_models[cache_key] = model
        
        return model
    
    # ==========================================================================
    # PRIVATE METHODS - ALGORITHM SELECTION
    # ==========================================================================
    def _select_algorithm_rules(
        self,
        order: Order,
        liquidity: LiquidityProfile
    ) -> ExecutionAlgo:
        """Select execution algorithm using rules."""
        # Simple rule-based selection
        size_category = self._categorize_order_size(order.quantity)
        urgency_score = self._score_urgency(order.urgency)
        
        if urgency_score > URGENCY_THRESHOLD:
            return ExecutionAlgo.MARKET
        elif size_category == 'block':
            return ExecutionAlgo.ICEBERG
        elif order.order_type == OrderType.MARKET:
            if size_category == 'small':
                return ExecutionAlgo.MARKET
            else:
                return ExecutionAlgo.TWAP
        elif liquidity.liquidity_score < 0.3:
            return ExecutionAlgo.SNIPER
        else:
            return ExecutionAlgo.ADAPTIVE
    
    # ==========================================================================
    # PRIVATE METHODS - EXECUTION SLICING
    # ==========================================================================
    def _create_execution_slices(
        self,
        order: Order,
        algorithm: ExecutionAlgo,
        liquidity: LiquidityProfile
    ) -> List[Dict[str, Any]]:
        """Create execution slices based on algorithm."""
        slices = []
        remaining_quantity = order.quantity
        
        if algorithm == ExecutionAlgo.ICEBERG:
            # Hide large order by showing small slices
            slice_size = min(self.max_order_slice, int(liquidity.avg_size * 0.2))
            
            while remaining_quantity > 0:
                current_slice = min(slice_size, remaining_quantity)
                slices.append({
                    'quantity': current_slice,
                    'timing': 'immediate',
                    'show_quantity': min(10, current_slice)  # Show only small portion
                })
                remaining_quantity -= current_slice
                
        elif algorithm == ExecutionAlgo.TWAP:
            # Time-weighted slices
            num_slices = min(10, max(3, order.quantity // 100))
            slice_size = order.quantity // num_slices
            
            for i in range(num_slices):
                slices.append({
                    'quantity': slice_size,
                    'timing': f'slice_{i}',
                    'delay_minutes': i * 5  # 5 minutes between slices
                })
            
            # Handle remainder
            if order.quantity % num_slices > 0:
                slices[-1]['quantity'] += order.quantity % num_slices
                
        else:
            # Single slice for simple algorithms
            slices.append({
                'quantity': order.quantity,
                'timing': 'immediate',
                'show_quantity': order.quantity
            })
        
        return slices
    
    # ==========================================================================
    # PRIVATE METHODS - VENUE ROUTING
    # ==========================================================================
    def _determine_venues(
        self,
        order: Order,
        liquidity: LiquidityProfile
    ) -> List[VenueType]:
        """Determine optimal venues for execution."""
        venues = []
        
        # Always include primary exchange
        venues.append(VenueType.EXCHANGE)
        
        # Add dark pools for large orders
        if self._categorize_order_size(order.quantity) in ['large', 'block']:
            venues.append(VenueType.DARK_POOL)
        
        # Add ECN for better prices
        if liquidity.liquidity_score > 0.5:
            venues.append(VenueType.ECN)
        
        return venues
    
    # ==========================================================================
    # PRIVATE METHODS - COST ESTIMATION
    # ==========================================================================
    def _calculate_expected_cost(
        self,
        order: Order,
        algorithm: ExecutionAlgo,
        impact_model: MarketImpactModel,
        liquidity: LiquidityProfile
    ) -> float:
        """Calculate expected execution cost."""
        # Base costs
        spread_cost = liquidity.avg_spread * order.quantity * 0.5  # Half spread
        
        # Impact costs
        impact_cost = (impact_model.temporary_impact + impact_model.permanent_impact) * order.quantity
        
        # Urgency premium
        urgency_premium = liquidity.urgency_cost.get(order.urgency, 0) * order.quantity
        
        # Algorithm efficiency factor
        algo_efficiency = {
            ExecutionAlgo.MARKET: 1.2,      # Higher cost for immediacy
            ExecutionAlgo.LIMIT: 0.8,       # Lower cost but risk of non-fill
            ExecutionAlgo.TWAP: 0.9,
            ExecutionAlgo.VWAP: 0.85,
            ExecutionAlgo.ICEBERG: 0.9,
            ExecutionAlgo.SNIPER: 0.95,
            ExecutionAlgo.ADAPTIVE: 0.85
        }.get(algorithm, 1.0)
        
        total_cost = (spread_cost + impact_cost + urgency_premium) * algo_efficiency
        
        return total_cost
    
    def _estimate_duration(
        self,
        order: Order,
        algorithm: ExecutionAlgo,
        liquidity: LiquidityProfile
    ) -> timedelta:
        """Estimate execution duration."""
        if algorithm == ExecutionAlgo.MARKET:
            return timedelta(seconds=1)
        elif algorithm == ExecutionAlgo.TWAP:
            # Based on number of slices
            num_slices = min(10, max(3, order.quantity // 100))
            return timedelta(minutes=num_slices * 5)
        elif algorithm == ExecutionAlgo.VWAP:
            # Typically 30-60 minutes
            return timedelta(minutes=45)
        elif algorithm == ExecutionAlgo.ICEBERG:
            # Based on liquidity
            slices_needed = order.quantity / (liquidity.avg_size * 0.2)
            return timedelta(minutes=slices_needed * 2)
        else:
            # Default estimate
            return timedelta(minutes=15)
    
    def _get_timing_strategy(
        self,
        order: Order,
        market_data: Optional[MarketMicrostructure]
    ) -> str:
        """Determine timing strategy."""
        urgency_score = self._score_urgency(order.urgency)
        
        if urgency_score > 0.8:
            return "immediate"
        elif self._get_market_hours_remaining() < 0.5:
            return "accelerated"  # Speed up near close
        elif market_data and market_data.volatility > 0.02:
            return "patient"  # Wait during high volatility
        else:
            return "opportunistic"
    
    def _calculate_urgency_premium(self, urgency: UrgencyLevel) -> float:
        """Calculate urgency premium multiplier."""
        premiums = {
            UrgencyLevel.LOW: 0.0,
            UrgencyLevel.MEDIUM: 0.01,
            UrgencyLevel.HIGH: 0.02,
            UrgencyLevel.CRITICAL: 0.05
        }
        return premiums.get(urgency, 0.01)
    
    # ==========================================================================
    # PRIVATE METHODS - EXECUTION ALGORITHMS
    # ==========================================================================
    async def _execute_simple(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Simple execution implementation."""
        # Simulated execution
        fills = []
        total_quantity = 0
        total_cost = 0
        
        for slice_config in plan.slices:
            quantity = slice_config['quantity']
            
            # Simulate fill (in production, would send to broker)
            fill_price = await self._simulate_fill_price(
                plan.order.symbol,
                quantity,
                plan.order.side
            )
            
            fills.append({
                'quantity': quantity,
                'price': fill_price,
                'timestamp': datetime.now(),
                'venue': plan.venues[0]
            })
            
            total_quantity += quantity
            total_cost += quantity * fill_price
            
            # Update order status
            if total_quantity >= plan.order.quantity:
                plan.order.status = OrderStatus.FILLED
            else:
                plan.order.status = OrderStatus.PARTIAL
        
        return {
            'fills': fills,
            'total_quantity': total_quantity,
            'total_cost': total_cost,
            'avg_price': total_cost / total_quantity if total_quantity > 0 else 0
        }
    
    async def _execute_twap(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Time-Weighted Average Price algorithm."""
        fills = []
        total_quantity = 0
        total_cost = 0
        
        for i, slice_config in enumerate(plan.slices):
            # Wait for scheduled time
            if 'delay_minutes' in slice_config and slice_config['delay_minutes'] > 0:
                await asyncio.sleep(slice_config['delay_minutes'] * 60)  # In production, use scheduler
            
            # Check if we should continue
            if real_time_updates and not self._should_continue_execution(plan):
                break
            
            # Execute slice
            quantity = slice_config['quantity']
            fill_price = await self._simulate_fill_price(
                plan.order.symbol,
                quantity,
                plan.order.side
            )
            
            fills.append({
                'quantity': quantity,
                'price': fill_price,
                'timestamp': datetime.now(),
                'venue': plan.venues[i % len(plan.venues)]
            })
            
            total_quantity += quantity
            total_cost += quantity * fill_price
            
            self.logger.info(f"TWAP slice {i+1}/{len(plan.slices)} executed")
        
        return {
            'fills': fills,
            'total_quantity': total_quantity,
            'total_cost': total_cost,
            'avg_price': total_cost / total_quantity if total_quantity > 0 else 0
        }
    
    async def _execute_vwap(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Volume-Weighted Average Price algorithm."""
        # Simplified VWAP - in production would track actual volume
        return await self._execute_twap(plan, real_time_updates)
    
    async def _execute_pov(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Percentage of Volume algorithm."""
        # Simplified POV - in production would track market volume
        return await self._execute_twap(plan, real_time_updates)
    
    async def _execute_iceberg(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Iceberg algorithm."""
        fills = []
        total_quantity = 0
        total_cost = 0
        
        for slice_config in plan.slices:
            # Show only small portion
            show_quantity = slice_config.get('show_quantity', 10)
            hidden_quantity = slice_config['quantity'] - show_quantity
            
            # Execute visible portion
            fill_price = await self._simulate_fill_price(
                plan.order.symbol,
                show_quantity,
                plan.order.side
            )
            
            fills.append({
                'quantity': show_quantity,
                'price': fill_price,
                'timestamp': datetime.now(),
                'venue': VenueType.EXCHANGE,
                'type': 'visible'
            })
            
            # Execute hidden portion
            if hidden_quantity > 0:
                hidden_price = await self._simulate_fill_price(
                    plan.order.symbol,
                    hidden_quantity,
                    plan.order.side,
                    impact_reduction=0.5  # Less impact for hidden orders
                )
                
                fills.append({
                    'quantity': hidden_quantity,
                    'price': hidden_price,
                    'timestamp': datetime.now(),
                    'venue': VenueType.DARK_POOL,
                    'type': 'hidden'
                })
            
            total_quantity += slice_config['quantity']
            total_cost += show_quantity * fill_price + hidden_quantity * hidden_price
        
        return {
            'fills': fills,
            'total_quantity': total_quantity,
            'total_cost': total_cost,
            'avg_price': total_cost / total_quantity if total_quantity > 0 else 0
        }
    
    async def _execute_sniper(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Sniper algorithm for low liquidity."""
        # Wait for optimal conditions
        await self._wait_for_liquidity(plan.order.symbol)
        
        # Execute quickly when liquidity appears
        return await self._execute_simple(plan)
    
    async def _execute_adaptive(
        self,
        plan: ExecutionPlan,
        real_time_updates: bool
    ) -> Dict[str, Any]:
        """Execute using Adaptive algorithm."""
        # Start with TWAP approach
        initial_result = await self._execute_twap(plan, real_time_updates)
        
        # In production, would adapt based on real-time conditions
        return initial_result
    
    # ==========================================================================
    # PRIVATE METHODS - SIMULATION
    # ==========================================================================
    async def _simulate_fill_price(
        self,
        symbol: str,
        quantity: int,
        side: str,
        impact_reduction: float = 1.0
    ) -> float:
        """Simulate fill price with market impact."""
        # Get base price (in production, from market data)
        base_price = 100.0  # Placeholder
        
        # Get liquidity profile
        if symbol in self.liquidity_profiles:
            liquidity = self.liquidity_profiles[symbol]
            spread = liquidity.avg_spread
            
            # Apply spread
            if side == 'buy':
                price = base_price + spread / 2
            else:
                price = base_price - spread / 2
            
            # Add market impact
            impact = spread * np.sqrt(quantity / liquidity.avg_size) * impact_reduction
            if side == 'buy':
                price += impact
            else:
                price -= impact
        else:
            # Default spread and impact
            if side == 'buy':
                price = base_price * 1.001
            else:
                price = base_price * 0.999
        
        # Add some noise
        price *= (1 + np.random.normal(0, 0.0001))
        
        return round(price, 2)
    
    def _should_continue_execution(self, plan: ExecutionPlan) -> bool:
        """Check if execution should continue."""
        # Check market hours
        if self._get_market_hours_remaining() <= 0:
            return False
        
        # Check if order cancelled
        if plan.order.status == OrderStatus.CANCELLED:
            return False
        
        # In production, would check more conditions
        return True
    
    async def _wait_for_liquidity(self, symbol: str):
        """Wait for liquidity to improve."""
        # Simplified wait
        await asyncio.sleep(5)  # Wait 5 seconds
    
    # ==========================================================================
    # PRIVATE METHODS - ANALYTICS
    # ==========================================================================
    def _calculate_execution_analytics(
        self,
        plan: ExecutionPlan,
        execution_result: Dict[str, Any]
    ) -> ExecutionAnalytics:
        """Calculate execution analytics."""
        fills = execution_result.get('fills', [])
        
        # Calculate average price
        avg_price = execution_result.get('avg_price', 0)
        
        # Calculate slippage (simplified)
        if plan.order.limit_price:
            slippage = (avg_price - plan.order.limit_price) / plan.order.limit_price
            if plan.order.side == 'sell':
                slippage = -slippage
        else:
            slippage = 0.0
        
        # Calculate market impact (simplified)
        if fills:
            first_price = fills[0]['price']
            last_price = fills[-1]['price']
            market_impact = abs(last_price - first_price) / first_price
        else:
            market_impact = 0.0
        
        # Calculate execution time
        if fills:
            execution_time = fills[-1]['timestamp'] - fills[0]['timestamp']
        else:
            execution_time = timedelta(seconds=0)
        
        # Venue breakdown
        venue_breakdown = defaultdict(float)
        for fill in fills:
            venue = fill.get('venue', VenueType.EXCHANGE)
            venue_breakdown[venue] += fill['quantity']
        
        # Normalize venue breakdown
        total_quantity = execution_result.get('total_quantity', 1)
        for venue in venue_breakdown:
            venue_breakdown[venue] /= total_quantity
        
        return ExecutionAnalytics(
            order_id=plan.order.order_id,
            algorithm_used=plan.algorithm,
            execution_time=execution_time,
            avg_price=avg_price,
            slippage=slippage,
            market_impact=market_impact,
            total_cost=execution_result.get('total_cost', 0),
            venue_breakdown=dict(venue_breakdown),
            performance_vs_benchmark=0.0  # Would calculate vs VWAP/TWAP benchmark
        )
    
    def _update_performance_tracking(self, analytics: ExecutionAnalytics):
        """Update performance tracking with new execution."""
        # Track by algorithm
        self.algo_performance[analytics.algorithm_used].append(analytics.slippage)
        
        # Track by venue
        for venue, percentage in analytics.venue_breakdown.items():
            if venue.value not in self.venue_performance:
                self.venue_performance[venue.value] = {
                    'executions': 0,
                    'avg_slippage': 0.0
                }
            
            stats = self.venue_performance[venue.value]
            stats['executions'] += 1
            stats['avg_slippage'] = (
                (stats['avg_slippage'] * (stats['executions'] - 1) + analytics.slippage) /
                stats['executions']
            )
    
    # ==========================================================================
    # PRIVATE METHODS - MICROSTRUCTURE ANALYSIS
    # ==========================================================================
    def _get_recent_microstructure(
        self,
        symbol: str,
        lookback_minutes: int
    ) -> List[MarketMicrostructure]:
        """Get recent microstructure data."""
        # In production, would retrieve from data feed
        # For now, return empty list
        return []
    
    def _calculate_liquidity_score(
        self,
        data: List[MarketMicrostructure]
    ) -> float:
        """Calculate liquidity score from microstructure data."""
        if not data:
            return 0.5
        
        avg_spread = np.mean([d.spread for d in data])
        avg_size = np.mean([(d.bid_size + d.ask_size) / 2 for d in data])
        
        return self._calculate_single_liquidity_score(avg_spread, avg_size)
    
    def _identify_best_execution_times(
        self,
        data: List[MarketMicrostructure]
    ) -> List[str]:
        """Identify best times for execution."""
        # Simplified - return standard times
        return ["09:45", "11:00", "14:30", "15:45"]
    
    def _classify_volatility_regime(
        self,
        data: List[MarketMicrostructure]
    ) -> str:
        """Classify volatility regime."""
        if not data:
            return "normal"
        
        avg_volatility = np.mean([d.volatility for d in data])
        
        if avg_volatility < 0.01:
            return "low"
        elif avg_volatility < 0.02:
            return "normal"
        else:
            return "high"
    
    # ==========================================================================
    # PRIVATE METHODS - OPTIMIZATION
    # ==========================================================================
    def _get_relevant_executions(
        self,
        order: Order
    ) -> List[ExecutionAnalytics]:
        """Get relevant historical executions for analysis."""
        relevant = []
        
        for analytics in self.execution_analytics:
            # Get order details
            historical_order = self._get_order_by_id(analytics.order_id)
            if not historical_order:
                continue
            
            # Check relevance
            if (historical_order.symbol == order.symbol and
                abs(historical_order.quantity - order.quantity) / order.quantity < 0.5):
                relevant.append(analytics)
        
        return relevant[-100:]  # Last 100 relevant executions
    
    def _analyze_execution_performance(
        self,
        executions: List[ExecutionAnalytics],
        order: Order
    ) -> Dict[str, Any]:
        """Analyze historical execution performance."""
        if not executions:
            return {}
        
        # Group by algorithm
        algo_performance = defaultdict(list)
        for execution in executions:
            algo_performance[execution.algorithm_used].append({
                'slippage': execution.slippage,
                'impact': execution.market_impact,
                'time': execution.execution_time.total_seconds()
            })
        
        # Calculate statistics by algorithm
        algo_stats = {}
        for algo, perfs in algo_performance.items():
            algo_stats[algo.value] = {
                'avg_slippage': np.mean([p['slippage'] for p in perfs]),
                'avg_impact': np.mean([p['impact'] for p in perfs]),
                'avg_time': np.mean([p['time'] for p in perfs]),
                'count': len(perfs)
            }
        
        return {
            'algo_stats': algo_stats,
            'best_algo': min(algo_stats.items(), key=lambda x: x[1]['avg_slippage'])[0] if algo_stats else None
        }
    
    def _get_rule_based_optimization(
        self,
        order: Order,
        performance_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get rule-based optimization recommendations."""
        recommendations = {
            'algorithm': ExecutionAlgo.ADAPTIVE,
            'slice_size': 100,
            'participation_rate': 0.1,
            'urgency_adjustment': 1.0,
            'venues': [VenueType.EXCHANGE]
        }
        
        # Use best performing algorithm if available
        if performance_analysis.get('best_algo'):
            for algo in ExecutionAlgo:
                if algo.value == performance_analysis['best_algo']:
                    recommendations['algorithm'] = algo
                    break
        
        # Adjust slice size based on order size
        if order.quantity > 1000:
            recommendations['slice_size'] = 200
        elif order.quantity < 100:
            recommendations['slice_size'] = order.quantity
        
        # Add venues for large orders
        if order.quantity > 500:
            recommendations['venues'].append(VenueType.DARK_POOL)
        
        return recommendations
    
    # ==========================================================================
    # PRIVATE METHODS - PERFORMANCE ANALYSIS
    # ==========================================================================
    def _get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID from history."""
        # Check active orders
        if order_id in self.active_orders:
            return self.active_orders[order_id]
        
        # Check execution plans
        if order_id in self.execution_plans:
            return self.execution_plans[order_id].order
        
        return None
    
    def _get_algo_performance_breakdown(
        self,
        analytics: List[ExecutionAnalytics]
    ) -> Dict[str, Dict[str, float]]:
        """Get performance breakdown by algorithm."""
        breakdown = defaultdict(lambda: {'count': 0, 'avg_slippage': 0.0})
        
        for a in analytics:
            algo = a.algorithm_used.value
            current = breakdown[algo]
            current['count'] += 1
            current['avg_slippage'] = (
                (current['avg_slippage'] * (current['count'] - 1) + a.slippage) /
                current['count']
            )
        
        return dict(breakdown)
    
    def _get_venue_performance_breakdown(
        self,
        analytics: List[ExecutionAnalytics]
    ) -> Dict[str, Dict[str, float]]:
        """Get performance breakdown by venue."""
        breakdown = defaultdict(lambda: {'volume': 0.0, 'avg_slippage': 0.0})
        
        for a in analytics:
            for venue, percentage in a.venue_breakdown.items():
                venue_name = venue.value if hasattr(venue, 'value') else str(venue)
                current = breakdown[venue_name]
                current['volume'] += percentage
                current['avg_slippage'] = (
                    (current['avg_slippage'] * (current['volume'] - percentage) + a.slippage * percentage) /
                    current['volume']
                )
        
        return dict(breakdown)
    
    # ==========================================================================
    # PRIVATE METHODS - AI INTEGRATION
    # ==========================================================================
    async def _get_ai_algo_recommendation(
        self,
        order: Order,
        liquidity: LiquidityProfile,
        impact_model: MarketImpactModel,
        constraints: Optional[Dict[str, Any]] = None
    ) -> ExecutionAlgo:
        """Get AI recommendation for execution algorithm."""
        try:
            constraints_str = ""
            if constraints:
                constraints_str = "\nConstraints:\n" + "\n".join([f"- {k}: {v}" for k, v in constraints.items()])
            
            prompt = f"""Select the optimal execution algorithm for this options order:

Order Details:
- Symbol: {order.symbol}
- Quantity: {order.quantity} contracts
- Side: {order.side}
- Urgency: {order.urgency.value}
- Order Type: {order.order_type.value}

Market Conditions:
- Liquidity Score: {liquidity.liquidity_score:.2f}
- Average Spread: ${liquidity.avg_spread:.3f}
- Average Size: {liquidity.avg_size} contracts
- Impact Estimate: {impact_model.temporary_impact:.3f}
{constraints_str}

Available algorithms: market, limit, twap, vwap, pov, iceberg, sniper, adaptive

Consider urgency, liquidity, and market impact. Respond with just the algorithm name."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': 50
                }
            )
            
            # Parse response
            algo_name = response['response'].strip().lower()
            
            # Map to ExecutionAlgo
            for algo in ExecutionAlgo:
                if algo.value == algo_name:
                    return algo
            
            # Default if not found
            return ExecutionAlgo.ADAPTIVE
            
        except Exception as e:
            self.logger.error(f"Error getting AI algo recommendation: {e}")
            return self._select_algorithm_rules(order, liquidity)
    
    async def _get_ai_microstructure_insights(
        self,
        symbol: str,
        analysis: Dict[str, Any],
        recent_data: List[MarketMicrostructure]
    ) -> Dict[str, Any]:
        """Get AI insights on market microstructure."""
        try:
            prompt = f"""Analyze the market microstructure for {symbol}:

Metrics:
- Average Spread: ${analysis['avg_spread']:.3f}
- Spread Volatility: {analysis['spread_volatility']:.3f}
- Liquidity Score: {analysis['liquidity_score']:.2f}
- Volatility Regime: {analysis['volatility_regime']}

Provide insights on:
1. Optimal execution timing
2. Expected market impact
3. Venue selection strategy
4. Risk factors

Be specific and actionable."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            return {
                'insights': response['response'],
                'confidence': 0.8
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI microstructure insights: {e}")
            return {}
    
    async def _get_ai_parameter_optimization(
        self,
        order: Order,
        performance_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get AI recommendations for execution parameters."""
        try:
            perf_str = ""
            if performance_analysis.get('algo_stats'):
                perf_str = "\nHistorical Performance:\n"
                for algo, stats in performance_analysis['algo_stats'].items():
                    perf_str += f"- {algo}: slippage={stats['avg_slippage']:.3f}, count={stats['count']}\n"
            
            prompt = f"""Optimize execution parameters for this options order:

Order:
- Symbol: {order.symbol}
- Quantity: {order.quantity}
- Urgency: {order.urgency.value}
{perf_str}

Recommend:
1. Best algorithm (from: market, limit, twap, vwap, pov, iceberg, sniper, adaptive)
2. Optimal slice size
3. Participation rate (0.0-1.0)
4. Urgency adjustment factor
5. Preferred venues

Consider historical performance and current market conditions."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            # Parse response (simplified)
            text = response['response'].lower()
            
            # Extract algorithm
            algorithm = ExecutionAlgo.ADAPTIVE
            for algo in ExecutionAlgo:
                if algo.value in text:
                    algorithm = algo
                    break
            
            # Extract numbers (simplified)
            import re
            numbers = re.findall(r'\d+\.?\d*', text)
            
            slice_size = int(numbers[0]) if numbers else 100
            participation_rate = float(numbers[1]) if len(numbers) > 1 else 0.1
            
            return {
                'algorithm': algorithm,
                'slice_size': min(slice_size, order.quantity),
                'participation_rate': min(participation_rate, 1.0),
                'urgency_adjustment': 1.0,
                'venues': [VenueType.EXCHANGE, VenueType.DARK_POOL]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting AI parameter optimization: {e}")
            return self._get_rule_based_optimization(order, performance_analysis)
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def clear_cache(self):
        """Clear cached data."""
        self.liquidity_profiles.clear()
        self.impact_models.clear()
        self.microstructure.clear()
        self.logger.info("Execution cache cleared")
    
    def get_active_orders(self) -> List[Order]:
        """Get list of active orders."""
        return list(self.active_orders.values())
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an active order."""
        if order_id in self.active_orders:
            self.active_orders[order_id].status = OrderStatus.CANCELLED
            self.logger.info(f"Order {order_id} cancelled")
            return True
        return False

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_execution_strategy_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX07_ExecutionStrategyAgent:
    """
    Factory function to create Execution Strategy Agent.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Configured SpyderX07_ExecutionStrategyAgent instance
    """
    return SpyderX07_ExecutionStrategyAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: Optional[SpyderX07_ExecutionStrategyAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX07_ExecutionStrategyAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX07_ExecutionStrategyAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    async def test_agent():
        """Test the Execution Strategy Agent."""
        # Create agent
        config = {
            'llm_model': 'llama3.2:3b-instruct-q4_K_M',
            'temperature': 0.2,
            'max_order_slice': 1000
        }
        
        agent = create_execution_strategy_agent(config)
        
        # Create sample order
        order = Order(
            order_id="TEST001",
            symbol="SPY_240201C550",
            quantity=500,
            side="buy",
            order_type=OrderType.LIMIT,
            limit_price=5.50,
            urgency=UrgencyLevel.MEDIUM,
            strategy_tag="open_position"
        )
        
        # Create sample market data
        market_data = MarketMicrostructure(
            timestamp=datetime.now(),
            bid=5.45,
            ask=5.50,
            bid_size=100,
            ask_size=150,
            last_price=5.48,
            last_size=50,
            total_volume=10000,
            quote_count=500,
            trade_count=200,
            volatility=0.015,
            spread=0.05,
            depth_imbalance=0.2
        )
        
        print("="*80)
        print("TESTING EXECUTION STRATEGY AGENT")
        print("="*80)
        
        # 1. Create execution plan
        print("\n1. Creating Execution Plan...")
        plan = await agent.create_execution_plan(
            order,
            market_data,
            {'max_slippage': 0.02, 'max_impact': 0.01}
        )
        
        print(f"Algorithm: {plan.algorithm.value}")
        print(f"Number of slices: {len(plan.slices)}")
        print(f"Venues: {[v.value for v in plan.venues]}")
        print(f"Expected cost: ${plan.expected_cost:.2f}")
        print(f"Expected duration: {plan.expected_duration}")
        
        # 2. Analyze microstructure
        print("\n2. Analyzing Market Microstructure...")
        microstructure_analysis = await agent.analyze_market_microstructure(
            order.symbol,
            lookback_minutes=30
        )
        
        for key, value in microstructure_analysis.items():
            if key != 'ai_insights':
                print(f"{key}: {value}")
        
        # 3. Optimize parameters