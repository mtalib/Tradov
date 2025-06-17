#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX04_RiskGuardianAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Risk Management and Control Agent

Description:
    This agent replaces traditional risk management modules with intelligent,
    context-aware risk assessment. It consolidates functionality from RiskManager,
    PortfolioRisk, DrawdownControl, StressTest, and RiskControl modules into a
    unified AI-driven risk guardian. The agent provides real-time risk monitoring,
    dynamic position sizing, and intelligent circuit breaker decisions.

Author: Mohamed Talib
Spyder Version: 1.0
Last Updated: 2025-01-28 Time: 10:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from functools import lru_cache

# LangGraph for agent orchestration
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import Graph, StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain_ollama import OllamaLLM
from langchain.tools import Tool

# Risk calculations
from scipy import stats
from scipy.optimize import minimize

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
CACHE_TTL_SECONDS = 300  # 5 minutes for risk assessments

# Risk Limits (Default)
DEFAULT_RISK_LIMITS = {
    'max_portfolio_var': 0.02,  # 2% daily VaR
    'max_position_size': 0.10,  # 10% per position
    'max_sector_exposure': 0.30,  # 30% sector concentration
    'max_drawdown': 0.15,  # 15% maximum drawdown
    'max_leverage': 2.0,  # 2x leverage
    'min_cash_buffer': 0.20  # 20% cash buffer
}

# Circuit Breaker Thresholds
CIRCUIT_BREAKER_LEVELS = {
    'warning': 0.03,  # 3% daily loss
    'reduce': 0.05,   # 5% daily loss - reduce positions
    'halt': 0.08,     # 8% daily loss - halt trading
    'emergency': 0.10  # 10% daily loss - close all positions
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk level classification"""
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    NORMAL = "normal"
    WARNING = "warning"
    REDUCE = "reduce"
    HALT = "halt"
    EMERGENCY = "emergency"


class RiskAction(Enum):
    """Risk management actions"""
    APPROVE = "approve"
    APPROVE_WITH_ADJUSTMENT = "approve_with_adjustment"
    REJECT = "reject"
    REDUCE_SIZE = "reduce_size"
    HEDGE_REQUIRED = "hedge_required"
    CLOSE_POSITION = "close_position"


class AgentState(Enum):
    """Agent state enumeration"""
    INITIALIZED = "initialized"
    RUNNING = "running"
    ANALYZING = "analyzing"
    ERROR = "error"
    STOPPED = "stopped"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class Position:
    """Position information"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    position_type: str  # 'option' or 'stock'
    option_type: Optional[str] = None  # 'call' or 'put'
    strike: Optional[float] = None
    expiry: Optional[datetime] = None
    delta: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        """Calculate current market value"""
        return abs(self.quantity) * self.current_price * (100 if self.position_type == 'option' else 1)
    
    @property
    def pnl(self) -> float:
        """Calculate P&L"""
        multiplier = 100 if self.position_type == 'option' else 1
        return self.quantity * (self.current_price - self.entry_price) * multiplier
    
    @property
    def pnl_percent(self) -> float:
        """Calculate P&L percentage"""
        if self.entry_price == 0:
            return 0
        return (self.current_price - self.entry_price) / self.entry_price


@dataclass
class Portfolio:
    """Portfolio state"""
    positions: List[Position]
    cash: float
    buying_power: float
    total_value: float
    daily_pnl: float
    daily_pnl_percent: float
    timestamp: datetime
    
    @property
    def position_count(self) -> int:
        """Number of open positions"""
        return len(self.positions)
    
    @property
    def total_market_value(self) -> float:
        """Total market value of positions"""
        return sum(p.market_value for p in self.positions)
    
    @property
    def cash_percentage(self) -> float:
        """Cash as percentage of total value"""
        if self.total_value == 0:
            return 1.0
        return self.cash / self.total_value


@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    portfolio_var: float  # Value at Risk
    portfolio_cvar: float  # Conditional VaR
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    correlation_risk: float
    concentration_risk: float
    leverage_ratio: float
    margin_usage: float
    stress_test_results: Dict[str, float]


@dataclass
class RiskAssessment:
    """AI risk assessment result"""
    risk_level: RiskLevel
    risk_score: float  # 0-100
    risk_factors: List[str]
    recommendations: List[str]
    position_adjustments: Dict[str, Any]
    hedge_suggestions: List[Dict[str, Any]]
    circuit_breaker_state: CircuitBreakerState
    confidence_score: float


@dataclass
class TradeRequest:
    """Trade request for risk evaluation"""
    symbol: str
    quantity: int
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', etc.
    price: Optional[float] = None
    option_details: Optional[Dict[str, Any]] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX04_RiskGuardianAgent:
    """
    AI-Enhanced Risk Management Agent.
    
    This agent provides intelligent risk assessment, position sizing,
    and circuit breaker functionality. It replaces traditional rule-based
    risk management with context-aware AI decisions.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        state: Current agent state
        risk_calculator: Risk metrics calculation engine
        risk_interpreter: LLM-based risk interpretation
        circuit_breaker: Intelligent circuit breaker
        
    Example:
        >>> agent = SpyderX04_RiskGuardianAgent(config)
        >>> agent.initialize()
        >>> assessment = await agent.assess_portfolio_risk(portfolio)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Risk Guardian Agent."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.state = AgentState.INITIALIZED
        
        # Configuration
        self.config = config or {}
        self.risk_limits = self.config.get('risk_limits', DEFAULT_RISK_LIMITS)
        self.circuit_breaker_levels = self.config.get('circuit_breaker_levels', CIRCUIT_BREAKER_LEVELS)
        self.llm_model = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        
        # Components
        self.risk_calculator = None
        self.risk_interpreter = None
        self.circuit_breaker = None
        self.position_sizer = None
        self.event_manager = None
        
        # State tracking
        self.current_risk_level = RiskLevel.LOW
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        self.last_assessment_time = None
        self.assessment_count = 0
        
        # Risk history for trend analysis
        self.risk_history = []
        self.max_history_size = 1000
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self, event_manager: Optional[EventManager] = None) -> bool:
        """
        Initialize agent components.
        
        Args:
            event_manager: Optional Spyder event manager
            
        Returns:
            bool: True if initialization successful
        """
        try:
            # Set event manager
            self.event_manager = event_manager
            
            # Initialize components
            self.risk_calculator = RiskCalculator(self.risk_limits)
            self.risk_interpreter = RiskInterpreter(self.llm_model)
            self.circuit_breaker = CircuitBreaker(self.circuit_breaker_levels)
            self.position_sizer = PositionSizer(self.risk_limits)
            
            # Setup LangGraph workflow
            self._setup_graph()
            
            # Subscribe to events if event manager provided
            if self.event_manager:
                self._setup_event_subscriptions()
            
            self.state = AgentState.RUNNING
            self.logger.info("Risk Guardian Agent initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.state = AgentState.ERROR
            return False
            
    async def assess_portfolio_risk(
        self, 
        portfolio: Portfolio,
        market_context: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        Comprehensive portfolio risk assessment.
        
        Args:
            portfolio: Current portfolio state
            market_context: Market conditions and context
            
        Returns:
            RiskAssessment with AI analysis
        """
        if self.state != AgentState.RUNNING:
            self.logger.warning("Agent not running, cannot assess risk")
            return self._get_error_assessment("Agent not in running state")
            
        try:
            self.state = AgentState.ANALYZING
            start_time = datetime.now()
            self.assessment_count += 1
            
            # Prepare initial state
            initial_state = {
                "portfolio": portfolio,
                "market_context": market_context or {},
                "timestamp": datetime.now().isoformat(),
                "risk_limits": self.risk_limits
            }
            
            # Run the graph
            result = await self.app.ainvoke(initial_state)
            
            # Track performance
            processing_time = (datetime.now() - start_time).total_seconds()
            self.last_assessment_time = processing_time
            
            # Update state
            assessment = result['risk_assessment']
            self.current_risk_level = assessment.risk_level
            self.circuit_breaker_state = assessment.circuit_breaker_state
            
            # Store in history
            self._update_risk_history(assessment)
            
            # Emit event if event manager is available
            if self.event_manager:
                self.event_manager.emit(Event(
                    type="risk_assessment_complete",
                    data={
                        'assessment': assessment,
                        'processing_time_ms': processing_time * 1000
                    }
                ))
                
            self.state = AgentState.RUNNING
            return assessment
            
        except Exception as e:
            self.logger.error(f"Risk assessment failed: {e}")
            self.state = AgentState.ERROR
            return self._get_error_assessment(str(e))
            
    async def evaluate_trade(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio,
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a proposed trade for risk.
        
        Args:
            trade_request: Proposed trade details
            portfolio: Current portfolio state
            market_context: Market conditions
            
        Returns:
            Risk evaluation with action recommendation
        """
        try:
            # Quick pre-checks
            if self.circuit_breaker_state == CircuitBreakerState.HALT:
                return {
                    'action': RiskAction.REJECT,
                    'reason': 'Trading halted by circuit breaker',
                    'risk_score': 100
                }
            
            # Calculate position size impact
            position_impact = self.position_sizer.calculate_impact(
                trade_request, portfolio
            )
            
            # Get risk assessment
            risk_metrics = self.risk_calculator.calculate_trade_risk(
                trade_request, portfolio
            )
            
            # AI interpretation
            evaluation = await self.risk_interpreter.evaluate_trade(
                trade_request, portfolio, risk_metrics, market_context
            )
            
            # Apply risk limits
            action = self._apply_risk_limits(evaluation, position_impact)
            
            return {
                'action': action,
                'risk_score': evaluation['risk_score'],
                'adjusted_size': evaluation.get('adjusted_size'),
                'reasons': evaluation['reasons'],
                'hedge_suggestions': evaluation.get('hedge_suggestions', [])
            }
            
        except Exception as e:
            self.logger.error(f"Trade evaluation failed: {e}")
            return {
                'action': RiskAction.REJECT,
                'reason': f'Risk evaluation error: {str(e)}',
                'risk_score': 100
            }
            
    def get_position_size(
        self,
        symbol: str,
        portfolio: Portfolio,
        risk_per_trade: Optional[float] = None
    ) -> int:
        """
        Calculate optimal position size.
        
        Args:
            symbol: Trading symbol
            portfolio: Current portfolio
            risk_per_trade: Risk amount per trade
            
        Returns:
            Recommended position size
        """
        if risk_per_trade is None:
            risk_per_trade = portfolio.total_value * 0.02  # 2% default
            
        return self.position_sizer.calculate_size(
            symbol, portfolio, risk_per_trade
        )
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Returns:
            Performance statistics
        """
        return {
            'state': self.state.value,
            'assessment_count': self.assessment_count,
            'last_assessment_time_ms': self.last_assessment_time * 1000 if self.last_assessment_time else 0,
            'current_risk_level': self.current_risk_level.value,
            'circuit_breaker_state': self.circuit_breaker_state.value,
            'risk_history_size': len(self.risk_history)
        }
        
    # ==========================================================================
    # PRIVATE METHODS - GRAPH SETUP
    # ==========================================================================
    def _setup_graph(self):
        """Set up LangGraph workflow."""
        # Define the graph
        workflow = StateGraph(dict)
        
        # Add nodes
        workflow.add_node("calculate_metrics", self._calculate_metrics_node)
        workflow.add_node("analyze_risk", self._analyze_risk_node)
        workflow.add_node("check_limits", self._check_limits_node)
        workflow.add_node("generate_recommendations", self._generate_recommendations_node)
        workflow.add_node("circuit_breaker_check", self._circuit_breaker_node)
        
        # Add edges
        workflow.add_edge("calculate_metrics", "analyze_risk")
        workflow.add_edge("analyze_risk", "check_limits")
        workflow.add_edge("check_limits", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "circuit_breaker_check")
        workflow.add_edge("circuit_breaker_check", END)
        
        # Set entry point
        workflow.set_entry_point("calculate_metrics")
        
        # Compile
        self.app = workflow.compile()
        
    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        # Portfolio updates
        self.event_manager.subscribe('portfolio_update', self._handle_portfolio_update)
        
        # Trade requests
        self.event_manager.subscribe('trade_request', self._handle_trade_request)
        
        # Risk alerts
        self.event_manager.subscribe('risk_check_required', self._handle_risk_check)
        
        self.logger.debug("Risk event subscriptions completed")
        
    # ==========================================================================
    # PRIVATE METHODS - GRAPH NODES
    # ==========================================================================
    def _calculate_metrics_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate risk metrics."""
        portfolio = state["portfolio"]
        
        # Calculate comprehensive risk metrics
        risk_metrics = self.risk_calculator.calculate_portfolio_metrics(portfolio)
        
        # Add stress test results
        stress_results = self.risk_calculator.run_stress_tests(portfolio)
        risk_metrics.stress_test_results = stress_results
        
        state["risk_metrics"] = risk_metrics
        state["calculation_timestamp"] = datetime.now().isoformat()
        
        return state
        
    def _analyze_risk_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """AI risk analysis."""
        risk_metrics = state["risk_metrics"]
        portfolio = state["portfolio"]
        market_context = state["market_context"]
        
        # Get AI interpretation
        analysis = self.risk_interpreter.analyze_risk(
            risk_metrics, portfolio, market_context
        )
        
        state["risk_analysis"] = analysis
        return state
        
    def _check_limits_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Check risk limits."""
        risk_metrics = state["risk_metrics"]
        risk_limits = state["risk_limits"]
        
        # Check each limit
        limit_breaches = []
        
        if risk_metrics.portfolio_var > risk_limits['max_portfolio_var']:
            limit_breaches.append({
                'type': 'portfolio_var',
                'current': risk_metrics.portfolio_var,
                'limit': risk_limits['max_portfolio_var'],
                'severity': 'high'
            })
            
        if risk_metrics.leverage_ratio > risk_limits['max_leverage']:
            limit_breaches.append({
                'type': 'leverage',
                'current': risk_metrics.leverage_ratio,
                'limit': risk_limits['max_leverage'],
                'severity': 'critical'
            })
            
        if risk_metrics.current_drawdown > risk_limits['max_drawdown']:
            limit_breaches.append({
                'type': 'drawdown',
                'current': risk_metrics.current_drawdown,
                'limit': risk_limits['max_drawdown'],
                'severity': 'critical'
            })
            
        state["limit_breaches"] = limit_breaches
        return state
        
    def _generate_recommendations_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate risk recommendations."""
        risk_analysis = state["risk_analysis"]
        limit_breaches = state["limit_breaches"]
        portfolio = state["portfolio"]
        
        recommendations = []
        position_adjustments = {}
        hedge_suggestions = []
        
        # Handle limit breaches
        for breach in limit_breaches:
            if breach['severity'] == 'critical':
                recommendations.append(f"URGENT: {breach['type']} limit exceeded")
                
                if breach['type'] == 'leverage':
                    recommendations.append("Reduce leverage immediately")
                    # Calculate deleveraging needs
                    position_adjustments['reduce_all'] = 0.3  # Reduce all by 30%
                    
                elif breach['type'] == 'drawdown':
                    recommendations.append("Maximum drawdown reached - reduce risk")
                    position_adjustments['stop_new_trades'] = True
                    
        # Add AI recommendations
        recommendations.extend(risk_analysis['recommendations'])
        
        # Generate hedge suggestions if needed
        if risk_analysis['risk_level'] in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            hedge_suggestions = self._generate_hedge_suggestions(
                portfolio, state["risk_metrics"]
            )
            
        state["recommendations"] = recommendations
        state["position_adjustments"] = position_adjustments
        state["hedge_suggestions"] = hedge_suggestions
        
        return state
        
    def _circuit_breaker_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Circuit breaker evaluation."""
        portfolio = state["portfolio"]
        risk_analysis = state["risk_analysis"]
        
        # Check circuit breaker
        cb_state = self.circuit_breaker.evaluate(
            portfolio.daily_pnl_percent,
            risk_analysis['risk_score']
        )
        
        # Create final assessment
        risk_assessment = RiskAssessment(
            risk_level=risk_analysis['risk_level'],
            risk_score=risk_analysis['risk_score'],
            risk_factors=risk_analysis['risk_factors'],
            recommendations=state["recommendations"],
            position_adjustments=state["position_adjustments"],
            hedge_suggestions=state["hedge_suggestions"],
            circuit_breaker_state=cb_state,
            confidence_score=risk_analysis['confidence_score']
        )
        
        state["risk_assessment"] = risk_assessment
        
        # Trigger circuit breaker actions if needed
        if cb_state != CircuitBreakerState.NORMAL:
            self._trigger_circuit_breaker_actions(cb_state)
            
        return state
        
    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    def _apply_risk_limits(
        self, 
        evaluation: Dict[str, Any], 
        position_impact: Dict[str, Any]
    ) -> RiskAction:
        """Apply risk limits to determine action."""
        risk_score = evaluation['risk_score']
        
        if risk_score > 80:
            return RiskAction.REJECT
        elif risk_score > 60:
            if evaluation.get('adjusted_size'):
                return RiskAction.APPROVE_WITH_ADJUSTMENT
            else:
                return RiskAction.REDUCE_SIZE
        elif risk_score > 40:
            if evaluation.get('hedge_suggestions'):
                return RiskAction.HEDGE_REQUIRED
            else:
                return RiskAction.APPROVE
        else:
            return RiskAction.APPROVE
            
    def _generate_hedge_suggestions(
        self, 
        portfolio: Portfolio, 
        risk_metrics: RiskMetrics
    ) -> List[Dict[str, Any]]:
        """Generate hedging suggestions."""
        suggestions = []
        
        # Delta hedging
        total_delta = sum(p.delta * p.quantity for p in portfolio.positions if p.delta)
        if abs(total_delta) > 100:
            suggestions.append({
                'type': 'delta_hedge',
                'action': f"Hedge {-int(total_delta)} shares of SPY",
                'urgency': 'high'
            })
            
        # VIX hedging for high volatility
        if risk_metrics.portfolio_var > 0.015:  # 1.5% VaR
            suggestions.append({
                'type': 'volatility_hedge',
                'action': 'Buy VIX calls for tail risk protection',
                'urgency': 'medium'
            })
            
        return suggestions
        
    def _trigger_circuit_breaker_actions(self, cb_state: CircuitBreakerState):
        """Trigger circuit breaker actions."""
        if self.event_manager:
            self.event_manager.emit(Event(
                type='circuit_breaker_triggered',
                data={
                    'state': cb_state.value,
                    'timestamp': datetime.now().isoformat(),
                    'required_actions': self._get_cb_actions(cb_state)
                }
            ))
            
    def _get_cb_actions(self, cb_state: CircuitBreakerState) -> List[str]:
        """Get required actions for circuit breaker state."""
        actions = {
            CircuitBreakerState.WARNING: ["Monitor closely", "Prepare hedges"],
            CircuitBreakerState.REDUCE: ["Reduce all positions by 30%", "No new trades"],
            CircuitBreakerState.HALT: ["Halt all trading", "Close risky positions"],
            CircuitBreakerState.EMERGENCY: ["Close all positions", "Move to cash"]
        }
        return actions.get(cb_state, [])
        
    def _update_risk_history(self, assessment: RiskAssessment):
        """Update risk history for trend analysis."""
        self.risk_history.append({
            'timestamp': datetime.now(),
            'risk_score': assessment.risk_score,
            'risk_level': assessment.risk_level,
            'circuit_breaker': assessment.circuit_breaker_state
        })
        
        # Maintain size limit
        if len(self.risk_history) > self.max_history_size:
            self.risk_history = self.risk_history[-self.max_history_size:]
            
    def _get_error_assessment(self, error_msg: str) -> RiskAssessment:
        """Generate error assessment."""
        return RiskAssessment(
            risk_level=RiskLevel.CRITICAL,
            risk_score=100,
            risk_factors=[f"Error: {error_msg}"],
            recommendations=["Risk assessment failed - halt trading"],
            position_adjustments={},
            hedge_suggestions=[],
            circuit_breaker_state=CircuitBreakerState.HALT,
            confidence_score=0.0
        )
        
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _handle_portfolio_update(self, event: Event):
        """Handle portfolio update events."""
        asyncio.create_task(self._async_portfolio_check(event))
        
    def _handle_trade_request(self, event: Event):
        """Handle trade request events."""
        asyncio.create_task(self._async_trade_evaluation(event))
        
    def _handle_risk_check(self, event: Event):
        """Handle risk check request."""
        asyncio.create_task(self._async_risk_check(event))
        
    async def _async_portfolio_check(self, event: Event):
        """Async portfolio risk check."""
        portfolio = event.data['portfolio']
        assessment = await self.assess_portfolio_risk(portfolio)
        
        if assessment.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            self.event_manager.emit(Event(
                type='high_risk_alert',
                data={'assessment': assessment}
            ))
            
    async def _async_trade_evaluation(self, event: Event):
        """Async trade evaluation."""
        trade_request = event.data['trade_request']
        portfolio = event.data['portfolio']
        
        evaluation = await self.evaluate_trade(trade_request, portfolio)
        
        self.event_manager.emit(Event(
            type='trade_risk_evaluated',
            data={
                'request_id': event.data.get('request_id'),
                'evaluation': evaluation
            }
        ))
        
    async def _async_risk_check(self, event: Event):
        """Async risk check."""
        portfolio = event.data.get('portfolio')
        if portfolio:
            assessment = await self.assess_portfolio_risk(portfolio)
            self.event_manager.emit(Event(
                type='risk_check_complete',
                data={'assessment': assessment}
            ))
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the agent."""
        if self.state == AgentState.INITIALIZED:
            self.state = AgentState.RUNNING
            self.logger.info("Risk Guardian Agent started")
        else:
            self.logger.warning(f"Cannot start from state: {self.state}")
            
    def stop(self) -> None:
        """Stop the agent."""
        if self.state == AgentState.RUNNING:
            self.state = AgentState.STOPPED
            self.logger.info("Risk Guardian Agent stopped")
        else:
            self.logger.warning(f"Cannot stop from state: {self.state}")
            
    def cleanup(self) -> None:
        """Clean up agent resources."""
        # Clear caches
        if self.risk_calculator:
            self.risk_calculator.clear_cache()
        
        # Clear history
        self.risk_history.clear()
        
        self.logger.info("Risk Guardian Agent cleanup completed")

# ==============================================================================
# RISK CALCULATOR CLASS
# ==============================================================================
class RiskCalculator:
    """
    High-performance risk metrics calculator.
    
    Provides fast calculation of VaR, CVaR, stress tests, and other
    risk metrics using optimized numerical methods.
    """
    
    def __init__(self, risk_limits: Dict[str, float]):
        """Initialize risk calculator."""
        self.logger = SpyderLogger(__name__)
        self.risk_limits = risk_limits
        self.calculation_count = 0
        
    def calculate_portfolio_metrics(self, portfolio: Portfolio) -> RiskMetrics:
        """Calculate comprehensive portfolio risk metrics."""
        self.calculation_count += 1
        
        # Get position returns
        returns = self._calculate_returns(portfolio)
        
        # Calculate VaR and CVaR
        var_95 = self._calculate_var(returns, 0.95)
        cvar_95 = self._calculate_cvar(returns, 0.95)
        
        # Calculate ratios
        sharpe = self._calculate_sharpe_ratio(returns)
        sortino = self._calculate_sortino_ratio(returns)
        
        # Calculate drawdown
        max_dd, current_dd = self._calculate_drawdown(portfolio)
        
        # Calculate concentration and correlation
        concentration = self._calculate_concentration_risk(portfolio)
        correlation = self._calculate_correlation_risk(portfolio)
        
        # Calculate leverage
        leverage = self._calculate_leverage(portfolio)
        margin_usage = self._calculate_margin_usage(portfolio)
        
        return RiskMetrics(
            portfolio_var=var_95,
            portfolio_cvar=cvar_95,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            current_drawdown=current_dd,
            correlation_risk=correlation,
            concentration_risk=concentration,
            leverage_ratio=leverage,
            margin_usage=margin_usage,
            stress_test_results={}
        )
        
    def calculate_trade_risk(
        self, 
        trade: TradeRequest, 
        portfolio: Portfolio
    ) -> Dict[str, float]:
        """Calculate risk metrics for a proposed trade."""
        # Simulate portfolio with new trade
        simulated_portfolio = self._simulate_trade(trade, portfolio)
        
        # Calculate risk change
        current_metrics = self.calculate_portfolio_metrics(portfolio)
        new_metrics = self.calculate_portfolio_metrics(simulated_portfolio)
        
        return {
            'var_change': new_metrics.portfolio_var - current_metrics.portfolio_var,
            'leverage_change': new_metrics.leverage_ratio - current_metrics.leverage_ratio,
            'concentration_change': new_metrics.concentration_risk - current_metrics.concentration_risk,
            'margin_impact': new_metrics.margin_usage - current_metrics.margin_usage
        }
        
    def run_stress_tests(self, portfolio: Portfolio) -> Dict[str, float]:
        """Run stress test scenarios."""
        scenarios = {
            'market_crash': -0.10,  # 10% market drop
            'volatility_spike': 2.0,  # VIX doubles
            'interest_rate_shock': 0.01,  # 100bp rate increase
            'flash_crash': -0.05  # 5% instant drop
        }
        
        results = {}
        for scenario, shock in scenarios.items():
            stressed_value = self._apply_stress_scenario(portfolio, scenario, shock)
            results[scenario] = (stressed_value - portfolio.total_value) / portfolio.total_value
            
        return results
        
    @lru_cache(maxsize=1000)
    def _calculate_var(self, returns: tuple, confidence: float) -> float:
        """Calculate Value at Risk."""
        if not returns:
            return 0.0
        return np.percentile(returns, (1 - confidence) * 100)
        
    def _calculate_cvar(self, returns: tuple, confidence: float) -> float:
        """Calculate Conditional Value at Risk."""
        var = self._calculate_var(returns, confidence)
        return np.mean([r for r in returns if r <= var])
        
    def _calculate_sharpe_ratio(self, returns: tuple) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        return np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        
    def _calculate_sortino_ratio(self, returns: tuple) -> float:
        """Calculate Sortino ratio."""
        if not returns:
            return 0.0
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return float('inf')
        downside_std = np.std(downside_returns)
        return np.mean(returns) / (downside_std + 1e-8) * np.sqrt(252)
        
    def _calculate_returns(self, portfolio: Portfolio) -> tuple:
        """Calculate historical returns (mock for now)."""
        # In production, this would fetch historical data
        # For now, generate synthetic returns based on positions
        np.random.seed(42)  # For consistency
        base_return = 0.0005  # 5bps daily
        volatility = 0.02  # 2% daily vol
        
        returns = np.random.normal(base_return, volatility, 252)
        return tuple(returns)
        
    def _calculate_drawdown(self, portfolio: Portfolio) -> Tuple[float, float]:
        """Calculate maximum and current drawdown."""
        # Mock calculation - in production, use historical peaks
        current_dd = min(0, portfolio.daily_pnl_percent)
        max_dd = -0.08  # Mock 8% max drawdown
        return max_dd, current_dd
        
    def _calculate_concentration_risk(self, portfolio: Portfolio) -> float:
        """Calculate position concentration risk."""
        if not portfolio.positions:
            return 0.0
            
        position_values = [p.market_value for p in portfolio.positions]
        total_value = sum(position_values)
        
        if total_value == 0:
            return 0.0
            
        # Herfindahl index
        concentration = sum((v/total_value)**2 for v in position_values)
        return concentration
        
    def _calculate_correlation_risk(self, portfolio: Portfolio) -> float:
        """Calculate correlation risk."""
        # Simplified - in production, calculate actual correlations
        return 0.3 if len(portfolio.positions) > 5 else 0.1
        
    def _calculate_leverage(self, portfolio: Portfolio) -> float:
        """Calculate portfolio leverage."""
        if portfolio.total_value == 0:
            return 0.0
        return portfolio.total_market_value / portfolio.total_value
        
    def _calculate_margin_usage(self, portfolio: Portfolio) -> float:
        """Calculate margin usage percentage."""
        if portfolio.buying_power == 0:
            return 1.0
        used_margin = portfolio.total_value - portfolio.cash
        return used_margin / portfolio.buying_power
        
    def _simulate_trade(self, trade: TradeRequest, portfolio: Portfolio) -> Portfolio:
        """Simulate portfolio after trade."""
        # Create copy of portfolio
        new_positions = portfolio.positions.copy()
        
        # Add simulated position
        sim_position = Position(
            symbol=trade.symbol,
            quantity=trade.quantity,
            entry_price=trade.price or 100,  # Mock price
            current_price=trade.price or 100,
            position_type='option' if trade.option_details else 'stock'
        )
        new_positions.append(sim_position)
        
        # Return simulated portfolio
        return Portfolio(
            positions=new_positions,
            cash=portfolio.cash - (trade.quantity * trade.price if trade.price else 0),
            buying_power=portfolio.buying_power,
            total_value=portfolio.total_value,
            daily_pnl=portfolio.daily_pnl,
            daily_pnl_percent=portfolio.daily_pnl_percent,
            timestamp=portfolio.timestamp
        )
        
    def _apply_stress_scenario(
        self, 
        portfolio: Portfolio, 
        scenario: str, 
        shock: float
    ) -> float:
        """Apply stress scenario to portfolio."""
        stressed_value = portfolio.total_value
        
        if scenario == 'market_crash':
            # Apply shock to all positions
            position_value = sum(p.market_value * (1 + shock) for p in portfolio.positions)
            stressed_value = portfolio.cash + position_value
            
        return stressed_value
        
    def clear_cache(self):
        """Clear calculation cache."""
        self._calculate_var.cache_clear()

# ==============================================================================
# RISK INTERPRETER CLASS
# ==============================================================================
class RiskInterpreter:
    """
    AI agent that interprets risk metrics and provides insights.
    
    Uses LLM to analyze risk in context and generate actionable
    recommendations.
    """
    
    def __init__(self, llm_model: str = DEFAULT_LLM_MODEL):
        """Initialize risk interpreter."""
        self.logger = SpyderLogger(__name__)
        self.llm = OllamaLLM(model=llm_model, temperature=0.1)
        
    def analyze_risk(
        self,
        risk_metrics: RiskMetrics,
        portfolio: Portfolio,
        market_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze risk metrics with AI."""
        # Build prompt
        prompt = self._build_risk_prompt(risk_metrics, portfolio, market_context)
        
        # Get LLM analysis
        response = self.llm.invoke(prompt)
        
        # Parse response
        return self._parse_risk_analysis(response, risk_metrics)
        
    async def evaluate_trade(
        self,
        trade: TradeRequest,
        portfolio: Portfolio,
        risk_metrics: Dict[str, float],
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate trade risk with AI."""
        prompt = self._build_trade_prompt(trade, portfolio, risk_metrics, market_context)
        response = self.llm.invoke(prompt)
        return self._parse_trade_evaluation(response)
        
    def _build_risk_prompt(
        self,
        risk_metrics: RiskMetrics,
        portfolio: Portfolio,
        market_context: Dict[str, Any]
    ) -> str:
        """Build risk analysis prompt."""
        return f"""You are an expert risk manager analyzing portfolio risk.

Portfolio Overview:
- Total Value: ${portfolio.total_value:,.2f}
- Positions: {portfolio.position_count}
- Cash: {portfolio.cash_percentage:.1%}
- Daily P&L: {portfolio.daily_pnl_percent:.2%}

Risk Metrics:
- VaR (95%): {risk_metrics.portfolio_var:.2%}
- CVaR (95%): {risk_metrics.portfolio_cvar:.2%}
- Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}
- Max Drawdown: {risk_metrics.max_drawdown:.2%}
- Current Drawdown: {risk_metrics.current_drawdown:.2%}
- Leverage: {risk_metrics.leverage_ratio:.1f}x
- Concentration Risk: {risk_metrics.concentration_risk:.2f}

Market Context:
- VIX: {market_context.get('vix', 'N/A')}
- Trend: {market_context.get('trend', 'N/A')}

Provide risk assessment in JSON format:
{{
    "risk_level": "low|moderate|elevated|high|critical",
    "risk_score": 0-100,
    "risk_factors": ["factor1", "factor2"],
    "recommendations": ["action1", "action2"],
    "confidence_score": 0.0-1.0
}}"""
        
    def _build_trade_prompt(
        self,
        trade: TradeRequest,
        portfolio: Portfolio,
        risk_metrics: Dict[str, float],
        market_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build trade evaluation prompt."""
        return f"""Evaluate this trade from a risk perspective:

Trade Details:
- Symbol: {trade.symbol}
- Side: {trade.side}
- Quantity: {trade.quantity}
- Type: {trade.order_type}

Risk Impact:
- VaR Change: {risk_metrics['var_change']:.2%}
- Leverage Change: {risk_metrics['leverage_change']:.2f}x
- Concentration Change: {risk_metrics['concentration_change']:.2f}

Current Portfolio:
- Positions: {portfolio.position_count}
- Leverage: {portfolio.total_market_value / portfolio.total_value:.1f}x

Provide evaluation in JSON:
{{
    "risk_score": 0-100,
    "approve": true/false,
    "adjusted_size": null or number,
    "reasons": ["reason1", "reason2"],
    "hedge_suggestions": []
}}"""
        
    def _parse_risk_analysis(
        self, 
        response: str, 
        risk_metrics: RiskMetrics
    ) -> Dict[str, Any]:
        """Parse risk analysis from LLM."""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                # Convert string risk level to enum
                risk_level_str = data.get('risk_level', 'moderate')
                risk_level = RiskLevel[risk_level_str.upper()]
                
                return {
                    'risk_level': risk_level,
                    'risk_score': data.get('risk_score', 50),
                    'risk_factors': data.get('risk_factors', []),
                    'recommendations': data.get('recommendations', []),
                    'confidence_score': data.get('confidence_score', 0.7)
                }
        except Exception as e:
            self.logger.error(f"Failed to parse risk analysis: {e}")
            
        # Fallback to rule-based
        return self._get_rule_based_analysis(risk_metrics)
        
    def _parse_trade_evaluation(self, response: str) -> Dict[str, Any]:
        """Parse trade evaluation from LLM."""
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
            
        # Fallback
        return {
            'risk_score': 50,
            'approve': True,
            'adjusted_size': None,
            'reasons': ['Unable to parse AI response'],
            'hedge_suggestions': []
        }
        
    def _get_rule_based_analysis(self, risk_metrics: RiskMetrics) -> Dict[str, Any]:
        """Rule-based risk analysis as fallback."""
        risk_score = 0
        risk_factors = []
        recommendations = []
        
        # VaR check
        if risk_metrics.portfolio_var < -0.02:
            risk_score += 30
            risk_factors.append("High Value at Risk")
            recommendations.append("Reduce position sizes")
            
        # Leverage check
        if risk_metrics.leverage_ratio > 1.5:
            risk_score += 20
            risk_factors.append("Elevated leverage")
            recommendations.append("Deleverage portfolio")
            
        # Drawdown check
        if risk_metrics.current_drawdown < -0.05:
            risk_score += 25
            risk_factors.append("Significant drawdown")
            recommendations.append("Review stop losses")
            
        # Determine risk level
        if risk_score >= 80:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= 60:
            risk_level = RiskLevel.HIGH
        elif risk_score >= 40:
            risk_level = RiskLevel.ELEVATED
        elif risk_score >= 20:
            risk_level = RiskLevel.MODERATE
        else:
            risk_level = RiskLevel.LOW
            
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'recommendations': recommendations,
            'confidence_score': 0.7
        }

# ==============================================================================
# CIRCUIT BREAKER CLASS
# ==============================================================================
class CircuitBreaker:
    """
    Intelligent circuit breaker for risk control.
    """
    
    def __init__(self, levels: Dict[str, float]):
        """Initialize circuit breaker."""
        self.levels = levels
        self.state = CircuitBreakerState.NORMAL
        self.triggers = []
        
    def evaluate(self, daily_loss: float, risk_score: float) -> CircuitBreakerState:
        """Evaluate circuit breaker state."""
        # Check loss-based triggers
        if daily_loss <= -self.levels['emergency']:
            return CircuitBreakerState.EMERGENCY
        elif daily_loss <= -self.levels['halt']:
            return CircuitBreakerState.HALT
        elif daily_loss <= -self.levels['reduce']:
            return CircuitBreakerState.REDUCE
        elif daily_loss <= -self.levels['warning']:
            return CircuitBreakerState.WARNING
            
        # Check risk score triggers
        if risk_score >= 90:
            return CircuitBreakerState.HALT
        elif risk_score >= 70:
            return CircuitBreakerState.REDUCE
        elif risk_score >= 50:
            return CircuitBreakerState.WARNING
            
        return CircuitBreakerState.NORMAL

# ==============================================================================
# POSITION SIZER CLASS
# ==============================================================================
class PositionSizer:
    """
    Intelligent position sizing based on risk.
    """
    
    def __init__(self, risk_limits: Dict[str, float]):
        """Initialize position sizer."""
        self.risk_limits = risk_limits
        
    def calculate_size(
        self,
        symbol: str,
        portfolio: Portfolio,
        risk_amount: float
    ) -> int:
        """Calculate optimal position size."""
        # Kelly criterion simplified
        max_position_value = portfolio.total_value * self.risk_limits['max_position_size']
        
        # Adjust for current exposure
        current_exposure = sum(p.market_value for p in portfolio.positions if p.symbol == symbol)
        available_exposure = max_position_value - current_exposure
        
        # Calculate shares (simplified)
        price_estimate = 100  # Would get from market data
        max_shares = int(available_exposure / price_estimate)
        
        return max(0, max_shares)
        
    def calculate_impact(
        self,
        trade: TradeRequest,
        portfolio: Portfolio
    ) -> Dict[str, float]:
        """Calculate position size impact."""
        trade_value = trade.quantity * (trade.price or 100)
        
        return {
            'position_percentage': trade_value / portfolio.total_value,
            'concentration_impact': self._calc_concentration_impact(trade, portfolio),
            'leverage_impact': trade_value / portfolio.buying_power
        }
        
    def _calc_concentration_impact(
        self,
        trade: TradeRequest,
        portfolio: Portfolio
    ) -> float:
        """Calculate concentration impact."""
        # Simplified calculation
        symbol_exposure = sum(p.market_value for p in portfolio.positions if p.symbol == trade.symbol)
        trade_value = trade.quantity * (trade.price or 100)
        
        new_concentration = (symbol_exposure + trade_value) / portfolio.total_value
        return new_concentration

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_guardian_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX04_RiskGuardianAgent:
    """
    Factory function to create Risk Guardian Agent.
    
    Args:
        config: Agent configuration
        
    Returns:
        Configured SpyderX04_RiskGuardianAgent instance
    """
    return SpyderX04_RiskGuardianAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: Optional[SpyderX04_RiskGuardianAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX04_RiskGuardianAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None and config is not None:
        _module_instance = SpyderX04_RiskGuardianAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing SpyderX04_RiskGuardianAgent module...")
    print("=" * 60)
    
    # Configuration
    test_config = {
        'risk_limits': DEFAULT_RISK_LIMITS,
        'circuit_breaker_levels': CIRCUIT_BREAKER_LEVELS,
        'llm_model': DEFAULT_LLM_MODEL
    }
    
    # Create agent
    agent = SpyderX04_RiskGuardianAgent(test_config)
    
    if agent.initialize():
        print("✅ Risk Guardian Agent initialized successfully")
        
        # Create test portfolio
        test_positions = [
            Position(
                symbol="SPY",
                quantity=100,
                entry_price=545.00,
                current_price=548.50,
                position_type="stock"
            ),
            Position(
                symbol="SPY_240201C550",
                quantity=10,
                entry_price=4.50,
                current_price=5.25,
                position_type="option",
                option_type="call",
                strike=550.0,
                expiry=datetime.now() + timedelta(days=10),
                delta=0.45
            )
        ]
        
        test_portfolio = Portfolio(
            positions=test_positions,
            cash=50000.0,
            buying_power=100000.0,
            total_value=105000.0,
            daily_pnl=1250.0,
            daily_pnl_percent=0.012,
            timestamp=datetime.now()
        )
        
        # Market context
        market_context = {
            'vix': 16.5,
            'trend': 'Bullish',
            'volume': 'Average'
        }
        
        # Run risk assessment
        import asyncio
        
        async def test_assessment():
            print("\n📊 Running Portfolio Risk Assessment...")
            assessment = await agent.assess_portfolio_risk(test_portfolio, market_context)
            
            print(f"\nRisk Level: {assessment.risk_level.value.upper()}")
            print(f"Risk Score: {assessment.risk_score}/100")
            print(f"Circuit Breaker: {assessment.circuit_breaker_state.value}")
            print(f"Confidence: {assessment.confidence_score:.1%}")
            
            print("\nRisk Factors:")
            for factor in assessment.risk_factors:
                print(f"  • {factor}")
                
            print("\nRecommendations:")
            for rec in assessment.recommendations:
                print(f"  → {rec}")
                
            # Test trade evaluation
            print("\n📈 Testing Trade Evaluation...")
            test_trade = TradeRequest(
                symbol="SPY_240201P540",
                quantity=5,
                side="buy",
                order_type="limit",
                price=3.50
            )
            
            evaluation = await agent.evaluate_trade(test_trade, test_portfolio, market_context)
            print(f"\nTrade Action: {evaluation['action'].value}")
            print(f"Risk Score: {evaluation['risk_score']}/100")
            
            if 'reasons' in evaluation:
                print("\nReasons:")
                for reason in evaluation['reasons']:
                    print(f"  • {reason}")
                    
        asyncio.run(test_assessment())
        
        # Performance metrics
        print(f"\n⚡ Performance Metrics:")
        metrics = agent.get_performance_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value}")
        
        # Cleanup
        agent.stop()
        agent.cleanup()
    else:
        print("❌ Risk Guardian Agent initialization failed")
