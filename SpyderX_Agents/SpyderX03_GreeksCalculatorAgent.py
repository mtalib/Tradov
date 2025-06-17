#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX01_GreeksAgent.py
Group: X (AI Agents)
Purpose: AI-Enhanced Greeks Calculation and Analysis Agent

Description:
    This agent combines high-performance Greeks calculations using py_vollib with
    LLM-powered intelligent interpretation. It augments the traditional Greeks
    modules by adding AI-driven risk assessment, portfolio analysis, and
    actionable trading recommendations. The agent integrates seamlessly with
    Spyder's event system for real-time options analysis.

Author: Mohamed Talib
Spyder Version: 1.0
Last Updated: 2025-01-27 Time: 14:30
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

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from functools import lru_cache

# Greeks calculation libraries
import py_vollib.black_scholes as bs
import py_vollib.black_scholes.greeks.analytical as greeks
from py_vollib.black_scholes.implied_volatility import implied_volatility

# LangGraph for agent orchestration
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import Graph, StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain_ollama import OllamaLLM
from langchain.tools import Tool

# Caching
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_VOLATILITY = 0.20
CACHE_TTL_SECONDS = 900  # 15 minutes
MAX_CACHE_SIZE = 10000
DEFAULT_LLM_MODEL = "llama3.2:3b-instruct-q4_K_M"
DEFAULT_RISK_FREE_RATE = 0.05

# Greek Limits (per $1M notional)
GREEK_LIMITS = {
    'delta': 100,
    'gamma': 50,
    'vega': 200,
    'theta': -300
}

# ==============================================================================
# ENUMS
# ==============================================================================
class GreekLimitStatus(Enum):
    """Greek limit status levels"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    BREACH = "breach"


class MarketRegime(Enum):
    """Market regime classification"""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"


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
class OptionContract:
    """Enhanced option contract details"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    underlying_price: float
    market_price: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    
    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiration"""
        return max(0, (self.expiry - datetime.now()).days)
    
    @property
    def time_to_expiry_years(self) -> float:
        """Calculate time to expiration in years"""
        return max(0.0, (self.expiry - datetime.now()).days / 365.25)
    

@dataclass
class GreeksResult:
    """Enhanced Greeks calculation results"""
    contract: OptionContract
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_vol: Optional[float] = None
    theoretical_price: Optional[float] = None
    price_diff: Optional[float] = None  # Market - Theoretical
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'symbol': self.contract.symbol,
            'strike': self.contract.strike,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'implied_vol': self.implied_vol,
            'theoretical_price': self.theoretical_price,
            'price_diff': self.price_diff
        }
    

@dataclass
class GreeksInterpretation:
    """Enhanced AI interpretation of Greeks"""
    risk_assessment: str
    trading_recommendation: str
    key_insights: List[str]
    warning_flags: List[str]
    confidence_score: float
    hedge_suggestions: Optional[List[str]] = None
    adjustment_triggers: Optional[Dict[str, float]] = None


@dataclass
class PortfolioGreeks:
    """Portfolio-level Greeks aggregation"""
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    weighted_iv: float
    position_count: int
    notional_value: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX01_GreeksAgent:
    """
    AI-Enhanced Greeks Analysis Agent.
    
    This agent combines traditional Greeks calculations with LLM-powered
    interpretation to provide intelligent risk assessment and trading
    recommendations. It integrates with Spyder's event system and enhances
    the existing Greeks calculation modules.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        state: Current agent state
        calculator: Greeks calculation engine
        interpreter: LLM-based interpretation engine
        event_manager: Spyder event manager integration
        
    Example:
        >>> agent = SpyderX01_GreeksAgent(config)
        >>> agent.initialize()
        >>> results = await agent.analyze_position(contracts)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Greeks Agent."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.state = AgentState.INITIALIZED
        
        # Configuration
        self.config = config or {}
        self.risk_free_rate = self.config.get('risk_free_rate', DEFAULT_RISK_FREE_RATE)
        self.llm_model = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.greek_limits = self.config.get('greek_limits', GREEK_LIMITS)
        
        # Components
        self.calculator = None
        self.interpreter = None
        self.event_manager = None
        
        # Performance tracking
        self.analysis_count = 0
        self.last_analysis_time = None
        self.cache_hits = 0
        
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
            
            # Initialize calculator
            self.calculator = GreeksCalculator(self.risk_free_rate)
            
            # Initialize interpreter
            self.interpreter = GreeksInterpreter(self.llm_model)
            
            # Setup LangGraph workflow
            self._setup_graph()
            
            # Subscribe to events if event manager provided
            if self.event_manager:
                self._setup_event_subscriptions()
            
            self.state = AgentState.RUNNING
            self.logger.info("Greeks Agent initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.state = AgentState.ERROR
            return False
            
    async def analyze_position(
        self, 
        contracts: List[OptionContract],
        market_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for Greeks analysis.
        
        Args:
            contracts: List of option contracts to analyze
            market_context: Current market conditions
            
        Returns:
            Comprehensive analysis with calculations and AI interpretation
        """
        if self.state != AgentState.RUNNING:
            self.logger.warning("Agent not running, cannot analyze position")
            return self._get_error_response("Agent not in running state")
            
        try:
            self.state = AgentState.ANALYZING
            start_time = datetime.now()
            self.analysis_count += 1
            
            # Prepare initial state
            initial_state = {
                "contracts": contracts,
                "market_context": market_context or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Run the graph
            result = await self.app.ainvoke(initial_state)
            
            # Track performance
            self.last_analysis_time = (datetime.now() - start_time).total_seconds()
            
            # Emit event if event manager is available
            if self.event_manager:
                self.event_manager.emit(Event(
                    type="greeks_analysis_complete",
                    data=result
                ))
                
            self.state = AgentState.RUNNING
            return result
            
        except Exception as e:
            self.logger.error(f"Greeks analysis failed: {e}")
            self.state = AgentState.ERROR
            return self._get_error_response(str(e))
            
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get agent performance metrics.
        
        Returns:
            Performance statistics
        """
        return {
            'state': self.state.value,
            'analysis_count': self.analysis_count,
            'last_analysis_time_ms': self.last_analysis_time * 1000 if self.last_analysis_time else 0,
            'cache_hits': self.cache_hits,
            'calculator_stats': self.calculator.get_performance_stats() if self.calculator else {},
            'cache_enabled': self.interpreter.use_redis if self.interpreter else False
        }
        
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _setup_graph(self):
        """Set up LangGraph workflow."""
        # Define the graph
        workflow = StateGraph(dict)
        
        # Add nodes
        workflow.add_node("calculate", self._calculate_node)
        workflow.add_node("interpret", self._interpret_node)
        workflow.add_node("analyze_portfolio", self._analyze_portfolio_node)
        workflow.add_node("generate_alerts", self._generate_alerts_node)
        
        # Add edges
        workflow.add_edge("calculate", "interpret")
        workflow.add_edge("interpret", "analyze_portfolio")
        workflow.add_edge("analyze_portfolio", "generate_alerts")
        workflow.add_edge("generate_alerts", END)
        
        # Set entry point
        workflow.set_entry_point("calculate")
        
        # Compile
        self.app = workflow.compile()
        
    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        # Subscribe to Greeks calculation requests
        self.event_manager.subscribe('calculate_greeks', self._handle_greeks_request)
        
        # Subscribe to position analysis requests
        self.event_manager.subscribe('analyze_position', self._handle_position_analysis)
        
        self.logger.debug("Event subscriptions completed")
        
    def _handle_greeks_request(self, event: Event):
        """Handle Greeks calculation request from event system."""
        asyncio.create_task(self._async_handle_event(event))
        
    def _handle_position_analysis(self, event: Event):
        """Handle position analysis request from event system."""
        asyncio.create_task(self._async_handle_event(event))
        
    async def _async_handle_event(self, event: Event):
        """Async event handler."""
        contracts_data = event.data.get('contracts', [])
        contracts = [self._convert_to_option_contract(c) for c in contracts_data]
        market_context = event.data.get('market_context', {})
        
        result = await self.analyze_position(contracts, market_context)
        
        # Emit result event
        self.event_manager.emit(Event(
            type='greeks_analysis_result',
            data=result
        ))
        
    def _convert_to_option_contract(self, data: Dict) -> OptionContract:
        """Convert dictionary to OptionContract."""
        return OptionContract(
            symbol=data['symbol'],
            strike=data['strike'],
            expiry=datetime.fromisoformat(data['expiry']),
            option_type=data['option_type'],
            underlying_price=data['underlying_price'],
            market_price=data.get('market_price'),
            bid=data.get('bid'),
            ask=data.get('ask'),
            volume=data.get('volume'),
            open_interest=data.get('open_interest')
        )
        
    def _calculate_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate Greeks for all contracts."""
        contracts = state["contracts"]
        
        # Calculate Greeks
        greeks_results = self.calculator.batch_calculate(contracts)
        
        # Update state
        state["greeks_results"] = greeks_results
        state["calculation_stats"] = self.calculator.get_performance_stats()
        
        return state
        
    def _interpret_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Get AI interpretation for each result."""
        greeks_results = state["greeks_results"]
        market_context = state["market_context"]
        
        interpretations = []
        for result in greeks_results:
            interpretation = self.interpreter.interpret_greeks(
                result, 
                market_context
            )
            interpretations.append({
                'contract': result.contract.symbol,
                'greeks': result.to_dict(),
                'interpretation': interpretation
            })
            
        state["interpretations"] = interpretations
        return state
        
    def _analyze_portfolio_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze portfolio-level Greeks."""
        greeks_results = state["greeks_results"]
        
        # Calculate portfolio Greeks
        portfolio_greeks = self._calculate_portfolio_greeks(greeks_results)
        
        # Generate portfolio analysis
        portfolio_analysis = self._analyze_portfolio_greeks(
            portfolio_greeks,
            greeks_results
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            portfolio_analysis,
            state["market_context"]
        )
        
        state["portfolio_greeks"] = portfolio_greeks
        state["portfolio_analysis"] = portfolio_analysis
        state["recommendations"] = recommendations
        
        return state
        
    def _generate_alerts_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate alerts based on analysis."""
        portfolio_analysis = state["portfolio_analysis"]
        alerts = []
        
        # Check Greek limits
        total_greeks = portfolio_analysis['total_greeks']
        
        # Delta limit check
        delta_limit = self.greek_limits.get('delta', 100)
        if abs(total_greeks['delta']) > delta_limit:
            alerts.append({
                'type': 'greek_limit_breach',
                'severity': 'high',
                'message': f"Delta limit breached: {total_greeks['delta']:.2f} (limit: ±{delta_limit})",
                'action': 'Immediate hedging required'
            })
            
        # Gamma limit check
        gamma_limit = self.greek_limits.get('gamma', 50)
        if abs(total_greeks['gamma']) > gamma_limit:
            alerts.append({
                'type': 'greek_limit_warning',
                'severity': 'medium',
                'message': f"High gamma exposure: {total_greeks['gamma']:.2f}",
                'action': 'Consider reducing position size'
            })
            
        state["alerts"] = alerts
        
        # Prepare final response
        state["analysis_complete"] = True
        state["summary"] = self._generate_summary(state)
        
        return state
        
    def _calculate_portfolio_greeks(self, results: List[GreeksResult]) -> PortfolioGreeks:
        """Calculate portfolio-level Greeks."""
        if not results:
            return PortfolioGreeks(
                total_delta=0, total_gamma=0, total_theta=0,
                total_vega=0, total_rho=0, weighted_iv=0,
                position_count=0, notional_value=0
            )
            
        # Aggregate Greeks
        total_delta = sum(r.delta for r in results)
        total_gamma = sum(r.gamma for r in results)
        total_theta = sum(r.theta for r in results)
        total_vega = sum(r.vega for r in results)
        total_rho = sum(r.rho for r in results)
        
        # Calculate weighted IV
        total_vega_dollars = sum(r.vega * (r.contract.market_price or r.theoretical_price)
                                for r in results)
        weighted_iv = sum(r.implied_vol * r.vega * 
                         (r.contract.market_price or r.theoretical_price)
                         for r in results) / max(total_vega_dollars, 1)
        
        # Calculate notional value
        notional_value = sum(
            r.contract.strike * 100 * abs(r.delta)
            for r in results
        )
        
        return PortfolioGreeks(
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_theta=total_theta,
            total_vega=total_vega,
            total_rho=total_rho,
            weighted_iv=weighted_iv,
            position_count=len(results),
            notional_value=notional_value
        )
        
    def _analyze_portfolio_greeks(
        self,
        portfolio_greeks: PortfolioGreeks,
        results: List[GreeksResult]
    ) -> Dict[str, Any]:
        """Analyze portfolio-level Greeks."""
        # Calculate risk metrics
        max_gamma = max(abs(r.gamma) for r in results) if results else 0
        
        # Risk scoring
        directional_risk = self._calculate_risk_score(abs(portfolio_greeks.total_delta), [50, 100, 200])
        gamma_risk = self._calculate_risk_score(max_gamma, [0.05, 0.10, 0.20])
        theta_risk = self._calculate_risk_score(-portfolio_greeks.total_theta, [50, 100, 200])
        vega_risk = self._calculate_risk_score(abs(portfolio_greeks.total_vega), [100, 200, 500])
        
        overall_risk = max(directional_risk, gamma_risk, theta_risk, vega_risk)
        
        return {
            'total_greeks': {
                'delta': portfolio_greeks.total_delta,
                'gamma': portfolio_greeks.total_gamma,
                'theta': portfolio_greeks.total_theta,
                'vega': portfolio_greeks.total_vega,
                'rho': portfolio_greeks.total_rho
            },
            'risk_metrics': {
                'directional_risk': self._risk_score_to_text(directional_risk),
                'gamma_risk': self._risk_score_to_text(gamma_risk),
                'theta_risk': self._risk_score_to_text(theta_risk),
                'vega_risk': self._risk_score_to_text(vega_risk),
                'overall_risk': self._risk_score_to_text(overall_risk)
            },
            'portfolio_stats': {
                'position_count': portfolio_greeks.position_count,
                'notional_value': portfolio_greeks.notional_value,
                'weighted_iv': portfolio_greeks.weighted_iv
            }
        }
        
    def _generate_recommendations(
        self, 
        portfolio_analysis: Dict[str, Any],
        market_context: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        greeks = portfolio_analysis['total_greeks']
        risk_metrics = portfolio_analysis['risk_metrics']
        
        # Delta hedging recommendations
        if abs(greeks['delta']) > 100:
            hedge_shares = -int(greeks['delta'])
            recommendations.append(
                f"URGENT: Delta hedge with {hedge_shares} shares of SPY"
            )
            
        # Gamma risk management
        if risk_metrics['gamma_risk'] in ['High', 'Critical']:
            recommendations.append(
                "Reduce position size or add gamma hedges at different strikes"
            )
            
        # Theta management
        if greeks['theta'] < -100:
            recommendations.append(
                "Monitor theta decay - consider reducing time-sensitive positions"
            )
            
        return recommendations
        
    def _calculate_risk_score(self, value: float, thresholds: List[float]) -> int:
        """Calculate risk score (0-3) based on thresholds."""
        for i, threshold in enumerate(thresholds):
            if value <= threshold:
                return i
        return len(thresholds)
        
    def _risk_score_to_text(self, score: int) -> str:
        """Convert risk score to text."""
        mapping = {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Critical'}
        return mapping.get(score, 'Unknown')
        
    def _generate_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary of analysis."""
        portfolio = state["portfolio_analysis"]
        
        return {
            'timestamp': state['timestamp'],
            'positions_analyzed': len(state['contracts']),
            'total_delta': portfolio['total_greeks']['delta'],
            'daily_theta': portfolio['total_greeks']['theta'],
            'overall_risk': portfolio['risk_metrics']['overall_risk'],
            'alerts_count': len(state['alerts']),
            'top_recommendation': state['recommendations'][0] if state['recommendations'] else 'No action required',
            'analysis_time_ms': self.last_analysis_time * 1000 if self.last_analysis_time else 0
        }
        
    def _get_error_response(self, error_msg: str) -> Dict[str, Any]:
        """Generate error response."""
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': error_msg,
            'positions': [],
            'portfolio': {},
            'recommendations': ["Error in analysis - please check logs"]
        }
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the agent."""
        if self.state == AgentState.INITIALIZED:
            self.state = AgentState.RUNNING
            self.logger.info("Greeks Agent started")
        else:
            self.logger.warning(f"Cannot start from state: {self.state}")
            
    def stop(self) -> None:
        """Stop the agent."""
        if self.state == AgentState.RUNNING:
            self.state = AgentState.STOPPED
            self.logger.info("Greeks Agent stopped")
        else:
            self.logger.warning(f"Cannot stop from state: {self.state}")
            
    def cleanup(self) -> None:
        """Clean up agent resources."""
        # Cleanup any resources
        if self.calculator:
            self.calculator.calculate_greeks.cache_clear()
        
        self.logger.info("Greeks Agent cleanup completed")

# ==============================================================================
# GREEKS CALCULATOR CLASS
# ==============================================================================
class GreeksCalculator:
    """
    High-performance Greeks calculator using py_vollib.
    
    This class provides fast, cached calculations of option Greeks
    with support for batch processing and implied volatility calculations.
    """
    
    def __init__(self, risk_free_rate: float = DEFAULT_RISK_FREE_RATE):
        """Initialize the Greeks calculator."""
        self.logger = SpyderLogger(__name__)
        self.risk_free_rate = risk_free_rate
        self.calculation_count = 0
        self.cache_hits = 0
        
        self.logger.info(f"GreeksCalculator initialized with r={risk_free_rate}")
        
    @lru_cache(maxsize=MAX_CACHE_SIZE)
    def calculate_greeks(
        self, 
        S: float,      # Underlying price
        K: float,      # Strike price
        T: float,      # Time to expiration (years)
        r: float,      # Risk-free rate
        sigma: float,  # Implied volatility
        flag: str      # 'c' for call, 'p' for put
    ) -> Dict[str, float]:
        """
        Calculate all Greeks using py_vollib (cached for performance).
        
        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiration in years
            r: Risk-free rate
            sigma: Implied volatility
            flag: 'c' for call, 'p' for put
            
        Returns:
            Dict containing delta, gamma, theta, vega, rho
        """
        self.calculation_count += 1
        
        try:
            # Validate inputs
            if T <= 0:
                return self._get_expired_greeks(S, K, flag)
                
            if sigma <= 0:
                self.logger.warning(f"Invalid volatility {sigma}, using default")
                sigma = DEFAULT_VOLATILITY
                
            return {
                'delta': greeks.delta(flag, S, K, T, r, sigma),
                'gamma': greeks.gamma(flag, S, K, T, r, sigma),
                'theta': greeks.theta(flag, S, K, T, r, sigma),
                'vega': greeks.vega(flag, S, K, T, r, sigma),
                'rho': greeks.rho(flag, S, K, T, r, sigma)
            }
        except Exception as e:
            self.logger.error(f"Greeks calculation failed: {e}")
            return self._get_default_greeks()
    
    def calculate_implied_volatility(
        self,
        price: float,   # Option market price
        S: float,       # Underlying price
        K: float,       # Strike price
        T: float,       # Time to expiration
        r: float,       # Risk-free rate
        flag: str       # 'c' or 'p'
    ) -> float:
        """Calculate implied volatility from market price."""
        try:
            if T <= 0:
                return 0.0
                
            # Check for valid price bounds
            intrinsic = max(0, S - K) if flag == 'c' else max(0, K - S)
            if price < intrinsic:
                self.logger.warning(f"Price {price} below intrinsic {intrinsic}")
                return DEFAULT_VOLATILITY
                
            return implied_volatility(price, S, K, T, r, flag)
        except Exception as e:
            self.logger.warning(f"IV calculation failed: {e}")
            return DEFAULT_VOLATILITY
            
    def calculate_theoretical_price(
        self,
        S: float, K: float, T: float, 
        r: float, sigma: float, flag: str
    ) -> float:
        """Calculate theoretical option price."""
        try:
            if T <= 0:
                # Expired option value
                if flag == 'c':
                    return max(0, S - K)
                else:
                    return max(0, K - S)
                    
            return bs.black_scholes(flag, S, K, T, r, sigma)
        except Exception as e:
            self.logger.error(f"Price calculation failed: {e}")
            return 0.0
            
    def batch_calculate(
        self, 
        contracts: List[OptionContract],
        volatility: float = DEFAULT_VOLATILITY,
        use_market_iv: bool = True
    ) -> List[GreeksResult]:
        """Calculate Greeks for multiple contracts efficiently."""
        results = []
        
        for contract in contracts:
            # Calculate time to expiration in years
            T = contract.time_to_expiry_years
            
            # Skip expired options
            if T <= 0:
                self.logger.debug(f"Skipping expired contract: {contract.symbol}")
                continue
                
            # Use market price to calculate IV if available
            if use_market_iv and contract.market_price:
                sigma = self.calculate_implied_volatility(
                    contract.market_price,
                    contract.underlying_price,
                    contract.strike,
                    T,
                    self.risk_free_rate,
                    contract.option_type[0]  # 'c' or 'p'
                )
            else:
                sigma = volatility
                
            # Calculate Greeks
            greeks_dict = self.calculate_greeks(
                contract.underlying_price,
                contract.strike,
                T,
                self.risk_free_rate,
                sigma,
                contract.option_type[0]
            )
            
            # Calculate theoretical price
            theo_price = self.calculate_theoretical_price(
                contract.underlying_price,
                contract.strike,
                T,
                self.risk_free_rate,
                sigma,
                contract.option_type[0]
            )
            
            # Calculate price difference if market price available
            price_diff = None
            if contract.market_price:
                price_diff = contract.market_price - theo_price
            
            results.append(GreeksResult(
                contract=contract,
                delta=greeks_dict['delta'],
                gamma=greeks_dict['gamma'],
                theta=greeks_dict['theta'],
                vega=greeks_dict['vega'],
                rho=greeks_dict['rho'],
                implied_vol=sigma,
                theoretical_price=theo_price,
                price_diff=price_diff
            ))
            
        return results
    
    def _get_expired_greeks(self, S: float, K: float, flag: str) -> Dict[str, float]:
        """Return Greeks for expired options."""
        if flag == 'c':
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
            
        return {
            'delta': delta,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
    
    def _get_default_greeks(self) -> Dict[str, float]:
        """Return default Greeks for error cases."""
        return {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get calculator performance statistics."""
        cache_hit_rate = self.cache_hits / max(1, self.calculation_count)
        return {
            'calculations': self.calculation_count,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': cache_hit_rate,
            'cache_info': self.calculate_greeks.cache_info()._asdict()
        }

# ==============================================================================
# AI GREEKS INTERPRETER CLASS
# ==============================================================================
class GreeksInterpreter:
    """
    AI agent that interprets Greeks and provides trading insights.
    
    Uses LLM to analyze Greeks values in context and generate
    actionable recommendations with risk assessments.
    """
    
    def __init__(self, llm_model: str = DEFAULT_LLM_MODEL):
        """Initialize the Greeks interpreter."""
        self.logger = SpyderLogger(__name__)
        self.llm = OllamaLLM(model=llm_model, temperature=0.1)
        
        # Cache setup
        self.redis_client = None
        self.use_redis = False
        self.memory_cache = {}
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
                self.redis_client.ping()
                self.use_redis = True
                self.logger.info("Redis cache enabled for Greeks interpretations")
            except:
                self.logger.warning("Redis not available, using memory cache")
        
        self.logger.info(f"GreeksInterpreter initialized with model: {llm_model}")
        
    def interpret_greeks(
        self, 
        greeks_result: GreeksResult,
        market_context: Optional[Dict] = None,
        portfolio_greeks: Optional[PortfolioGreeks] = None
    ) -> GreeksInterpretation:
        """
        Use LLM to interpret Greeks and provide trading recommendations.
        
        Args:
            greeks_result: Calculated Greeks for the option
            market_context: Current market conditions
            portfolio_greeks: Portfolio-level Greeks aggregation
            
        Returns:
            GreeksInterpretation with AI analysis
        """
        # Check cache first
        cache_key = self._generate_cache_key(greeks_result, market_context)
        cached_result = self._get_cached_interpretation(cache_key)
        if cached_result:
            return cached_result
            
        # Prepare context for LLM
        prompt = self._build_interpretation_prompt(
            greeks_result, 
            market_context,
            portfolio_greeks
        )
        
        # Get LLM interpretation
        response = self.llm.invoke(prompt)
        
        # Parse response into structured format
        interpretation = self._parse_interpretation(response, greeks_result)
        
        # Cache the result
        self._cache_interpretation(cache_key, interpretation)
        
        return interpretation
        
    def _build_interpretation_prompt(
        self, 
        greeks_result: GreeksResult,
        market_context: Optional[Dict] = None,
        portfolio_greeks: Optional[PortfolioGreeks] = None
    ) -> str:
        """Build prompt for LLM interpretation."""
        contract = greeks_result.contract
        
        prompt = f"""You are an expert options trader analyzing Greeks for risk assessment.

Option Contract:
- Type: {contract.option_type}
- Strike: ${contract.strike}
- Underlying Price: ${contract.underlying_price}
- Days to Expiry: {contract.days_to_expiry}

Greeks Values:
- Delta: {greeks_result.delta:.4f}
- Gamma: {greeks_result.gamma:.4f}
- Theta: ${greeks_result.theta:.2f}/day
- Vega: ${greeks_result.vega:.2f}/1% vol
- Rho: ${greeks_result.rho:.2f}/1% rate

Provide a comprehensive risk assessment and trading recommendation in JSON format:
{{
    "risk_assessment": "overall risk level and explanation",
    "trading_recommendation": "specific action to take",
    "key_insights": ["insight1", "insight2"],
    "warning_flags": ["warning1", "warning2"],
    "confidence_score": 0.85,
    "hedge_suggestions": ["hedge1", "hedge2"],
    "adjustment_triggers": {{"delta_threshold": 0.70}}
}}"""
        return prompt
        
    def _parse_interpretation(
        self, 
        llm_response: str, 
        greeks_result: GreeksResult
    ) -> GreeksInterpretation:
        """Parse LLM response into structured interpretation."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return GreeksInterpretation(
                    risk_assessment=data.get('risk_assessment', ''),
                    trading_recommendation=data.get('trading_recommendation', ''),
                    key_insights=data.get('key_insights', []),
                    warning_flags=data.get('warning_flags', []),
                    confidence_score=data.get('confidence_score', 0.5),
                    hedge_suggestions=data.get('hedge_suggestions', []),
                    adjustment_triggers=data.get('adjustment_triggers', {})
                )
        except Exception as e:
            self.logger.error(f"Failed to parse LLM response: {e}")
            
        # Fallback interpretation
        return self._get_rule_based_interpretation(greeks_result)
        
    def _get_rule_based_interpretation(
        self, 
        greeks_result: GreeksResult
    ) -> GreeksInterpretation:
        """Rule-based interpretation as fallback."""
        insights = []
        warnings = []
        hedge_suggestions = []
        
        # Delta analysis
        abs_delta = abs(greeks_result.delta)
        if abs_delta > 0.8:
            insights.append("Very high delta - option behaves like stock")
            hedge_suggestions.append(f"Consider delta hedge with {-int(greeks_result.delta * 100)} shares")
            
        # Gamma analysis
        if greeks_result.gamma > 0.10:
            warnings.append("Very high gamma - delta extremely unstable")
            
        # Theta analysis
        if greeks_result.theta < -1.0:
            warnings.append("Severe theta decay - losing >$1/day")
            
        # Risk assessment
        risk_level = "High" if len(warnings) > 2 else "Medium" if warnings else "Low"
        
        # Trading recommendation
        if len(warnings) > 3:
            recommendation = "Close or reduce position - multiple risk factors"
        else:
            recommendation = "Hold position - monitor Greeks daily"
            
        return GreeksInterpretation(
            risk_assessment=f"{risk_level} risk based on Greeks analysis",
            trading_recommendation=recommendation,
            key_insights=insights,
            warning_flags=warnings,
            confidence_score=0.7,
            hedge_suggestions=hedge_suggestions,
            adjustment_triggers={'delta_threshold': 0.70}
        )
        
    def _generate_cache_key(
        self, 
        greeks_result: GreeksResult,
        market_context: Optional[Dict]
    ) -> str:
        """Generate cache key for interpretation."""
        key_parts = [
            greeks_result.contract.symbol,
            f"{greeks_result.delta:.3f}",
            f"{greeks_result.gamma:.3f}"
        ]
        
        if market_context:
            key_parts.append(str(market_context.get('vix', 0)))
            
        return ":".join(key_parts)
        
    def _get_cached_interpretation(self, cache_key: str) -> Optional[GreeksInterpretation]:
        """Get cached interpretation if available."""
        try:
            if self.use_redis and self.redis_client:
                cached = self.redis_client.get(f"greeks_interp:{cache_key}")
                if cached:
                    data = json.loads(cached)
                    return GreeksInterpretation(**data)
            else:
                return self.memory_cache.get(cache_key)
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {e}")
        return None
        
    def _cache_interpretation(self, cache_key: str, interpretation: GreeksInterpretation):
        """Cache interpretation for reuse."""
        try:
            data = {
                'risk_assessment': interpretation.risk_assessment,
                'trading_recommendation': interpretation.trading_recommendation,
                'key_insights': interpretation.key_insights,
                'warning_flags': interpretation.warning_flags,
                'confidence_score': interpretation.confidence_score,
                'hedge_suggestions': interpretation.hedge_suggestions,
                'adjustment_triggers': interpretation.adjustment_triggers
            }
            
            if self.use_redis and self.redis_client:
                self.redis_client.setex(
                    f"greeks_interp:{cache_key}",
                    CACHE_TTL_SECONDS,
                    json.dumps(data)
                )
            else:
                self.memory_cache[cache_key] = interpretation
        except Exception as e:
            self.logger.error(f"Cache storage error: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_greeks_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX01_GreeksAgent:
    """
    Factory function to create Greeks Agent.
    
    Args:
        config: Agent configuration
        
    Returns:
        Configured SpyderX01_GreeksAgent instance
    """
    return SpyderX01_GreeksAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: Optional[SpyderX01_GreeksAgent] = None

def get_module_instance(config: Optional[Dict[str, Any]] = None) -> SpyderX01_GreeksAgent:
    """
    Get singleton instance of the module.
    
    Args:
        config: Configuration if creating new instance
        
    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None and config is not None:
        _module_instance = SpyderX01_GreeksAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing SpyderX01_GreeksAgent module...")
    print("=" * 60)
    
    # Configuration
    test_config = {
        'risk_free_rate': 0.05,
        'llm_model': DEFAULT_LLM_MODEL,
        'greek_limits': GREEK_LIMITS
    }
    
    # Create agent
    agent = SpyderX01_GreeksAgent(test_config)
    
    if agent.initialize():
        print("✅ Greeks Agent initialized successfully")
        
        # Example contracts for testing
        test_contracts = [
            OptionContract(
                symbol="SPY_240201C550",
                strike=550.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='call',
                underlying_price=548.50,
                market_price=5.25
            ),
            OptionContract(
                symbol="SPY_240201P540",
                strike=540.0,
                expiry=datetime.now() + timedelta(days=10),
                option_type='put',
                underlying_price=548.50,
                market_price=3.75
            )
        ]
        
        # Market context
        market_context = {
            'vix': 15.2,
            'trend': 'Bullish',
            'volume': 'Above Average'
        }
        
        # Run analysis
        import asyncio
        
        async def test_analysis():
            results = await agent.analyze_position(test_contracts, market_context)
            print(f"\nAnalysis Summary: {results.get('summary', {})}")
            
        asyncio.run(test_analysis())
        
        # Performance metrics
        print(f"\nPerformance Metrics: {agent.get_performance_metrics()}")
        
        # Cleanup
        agent.stop()
        agent.cleanup()
    else:
        print("❌ Greeks Agent initialization failed")
