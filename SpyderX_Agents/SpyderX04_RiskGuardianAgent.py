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
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

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
DEFAULT_TEMPERATURE = 0.2  # Lower temperature for risk decisions
MAX_TOKENS = 2000

# Risk Thresholds
MAX_PORTFOLIO_RISK = 0.02  # 2% max portfolio risk
MAX_POSITION_RISK = 0.01   # 1% max position risk
MAX_DRAWDOWN = 0.10        # 10% max drawdown
VAR_CONFIDENCE = 0.95      # 95% VaR
RISK_FREE_RATE = 0.05      # 5% annual risk-free rate

# Circuit Breaker Thresholds
DAILY_LOSS_LIMIT = 0.03    # 3% daily loss limit
CONSECUTIVE_LOSSES = 3      # Max consecutive losing trades
VOLATILITY_SPIKE = 2.0     # 2x normal volatility

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk level classifications"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"
    CRITICAL = "critical"

class RiskType(Enum):
    """Types of risk to monitor"""
    MARKET = "market"
    POSITION = "position"
    PORTFOLIO = "portfolio"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    LIQUIDITY = "liquidity"
    OPERATIONAL = "operational"

class RiskAction(Enum):
    """Risk management actions"""
    APPROVE = "approve"
    REJECT = "reject"
    REDUCE_SIZE = "reduce_size"
    HEDGE = "hedge"
    CLOSE_POSITION = "close_position"
    HALT_TRADING = "halt_trading"
    ADJUST_LIMITS = "adjust_limits"

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
    position_type: str  # 'long' or 'short'
    market_value: float
    unrealized_pnl: float
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0

@dataclass
class Portfolio:
    """Portfolio state"""
    cash: float
    positions: List[Position]
    total_value: float
    current_risk: float
    max_drawdown: float
    daily_pnl: float
    realized_pnl: float

@dataclass
class RiskMetrics:
    """Comprehensive risk metrics"""
    timestamp: datetime
    portfolio_var: float
    portfolio_cvar: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    position_concentration: float
    correlation_risk: float
    stress_test_results: Dict[str, float]
    risk_score: float  # 0-100

@dataclass
class RiskAssessment:
    """AI-enhanced risk assessment"""
    timestamp: datetime
    risk_level: RiskLevel
    risk_metrics: RiskMetrics
    violations: List[str]
    recommendations: List[str]
    required_actions: List[RiskAction]
    ai_insights: Dict[str, Any]
    confidence_score: float

@dataclass
class TradeRequest:
    """Trade request for risk evaluation"""
    symbol: str
    quantity: int
    side: str  # 'buy' or 'sell'
    order_type: str
    price: Optional[float]
    strategy_type: str
    expected_risk: float
    expected_return: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX04_RiskGuardianAgent:
    """
    AI-Enhanced Risk Guardian Agent.
    
    This agent provides intelligent risk management by monitoring portfolio risk,
    evaluating trades, managing drawdowns, and implementing circuit breakers.
    It uses Ollama for context-aware risk assessment and recommendations.
    
    Attributes:
        logger: Module logger instance
        config: Agent configuration
        ollama_client: Ollama LLM client
        risk_limits: Current risk limits
        risk_history: Historical risk assessments
        
    Example:
        >>> agent = SpyderX04_RiskGuardianAgent()
        >>> assessment = await agent.assess_portfolio_risk(portfolio)
        >>> approval = await agent.evaluate_trade(trade_request, portfolio)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Risk Guardian Agent.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger
        
        # LLM configuration
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        
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
        
        # Risk limits and thresholds
        self.risk_limits = {
            'max_portfolio_risk': self.config.get('max_portfolio_risk', MAX_PORTFOLIO_RISK),
            'max_position_risk': self.config.get('max_position_risk', MAX_POSITION_RISK),
            'max_drawdown': self.config.get('max_drawdown', MAX_DRAWDOWN),
            'daily_loss_limit': self.config.get('daily_loss_limit', DAILY_LOSS_LIMIT),
            'var_confidence': self.config.get('var_confidence', VAR_CONFIDENCE)
        }
        
        # Risk tracking
        self.risk_history: List[RiskAssessment] = []
        self.daily_losses: deque = deque(maxlen=CONSECUTIVE_LOSSES)
        self.circuit_breaker_active = False
        self.last_circuit_breaker_time: Optional[datetime] = None
        
        # Performance tracking
        self.historical_returns: deque = deque(maxlen=252)  # 1 year of daily returns
        self.volatility_history: deque = deque(maxlen=30)   # 30 days of volatility
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    async def assess_portfolio_risk(
        self,
        portfolio: Portfolio,
        market_data: Optional[Dict[str, Any]] = None
    ) -> RiskAssessment:
        """
        Perform comprehensive portfolio risk assessment.
        
        Args:
            portfolio: Current portfolio state
            market_data: Optional market data for context
            
        Returns:
            Comprehensive risk assessment with AI insights
        """
        start_time = datetime.now()
        
        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics(portfolio, market_data)
        
        # Check for violations
        violations = self._check_risk_violations(risk_metrics, portfolio)
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_metrics, violations)
        
        # Get recommendations
        recommendations = self._generate_recommendations(
            risk_metrics,
            violations,
            portfolio
        )
        
        # Determine required actions
        required_actions = self._determine_required_actions(
            risk_level,
            violations,
            portfolio
        )
        
        # Get AI insights if available
        if self.ollama_client:
            ai_insights = await self._get_ai_risk_insights(
                risk_metrics,
                portfolio,
                violations,
                market_data
            )
            additional_recommendations = ai_insights.get('recommendations', [])
            recommendations.extend(additional_recommendations)
            confidence = ai_insights.get('confidence', 0.7)
        else:
            ai_insights = {}
            confidence = 0.6
        
        # Create assessment
        assessment = RiskAssessment(
            timestamp=datetime.now(),
            risk_level=risk_level,
            risk_metrics=risk_metrics,
            violations=violations,
            recommendations=recommendations,
            required_actions=required_actions,
            ai_insights=ai_insights,
            confidence_score=confidence
        )
        
        # Store in history
        self.risk_history.append(assessment)
        
        # Check circuit breakers
        self._check_circuit_breakers(assessment, portfolio)
        
        # Log performance
        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"Risk assessment completed: {risk_level.value} risk "
            f"with {len(violations)} violations in {elapsed:.2f} seconds"
        )
        
        return assessment
    
    async def evaluate_trade(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a trade request for risk approval.
        
        Args:
            trade_request: Proposed trade
            portfolio: Current portfolio state
            market_data: Optional market data
            
        Returns:
            Evaluation result with approval status and recommendations
        """
        # Check if circuit breaker is active
        if self.circuit_breaker_active:
            return {
                'approved': False,
                'reason': 'Circuit breaker active - trading halted',
                'action': RiskAction.HALT_TRADING,
                'recommendations': []
            }
        
        # Calculate trade impact
        trade_impact = self._calculate_trade_impact(trade_request, portfolio)
        
        # Check position limits
        position_check = self._check_position_limits(trade_request, portfolio)
        
        # Project portfolio risk with new trade
        projected_risk = self._project_portfolio_risk(
            trade_request,
            portfolio,
            trade_impact
        )
        
        # Get AI evaluation if available
        if self.ollama_client:
            ai_evaluation = await self._get_ai_trade_evaluation(
                trade_request,
                portfolio,
                trade_impact,
                projected_risk,
                market_data
            )
            approved = ai_evaluation.get('approved', False)
            reason = ai_evaluation.get('reason', '')
            recommendations = ai_evaluation.get('recommendations', [])
        else:
            # Rule-based evaluation
            approved = (
                position_check['passed'] and
                projected_risk < self.risk_limits['max_portfolio_risk'] and
                trade_impact['risk_contribution'] < self.risk_limits['max_position_risk']
            )
            reason = self._get_evaluation_reason(
                approved,
                position_check,
                projected_risk,
                trade_impact
            )
            recommendations = []
        
        # Determine action
        if approved:
            action = RiskAction.APPROVE
        elif projected_risk > self.risk_limits['max_portfolio_risk'] * 0.8:
            action = RiskAction.REDUCE_SIZE
            recommendations.append(
                f"Reduce position size to {int(trade_request.quantity * 0.5)} contracts"
            )
        else:
            action = RiskAction.REJECT
        
        return {
            'approved': approved,
            'reason': reason,
            'action': action,
            'recommendations': recommendations,
            'trade_impact': trade_impact,
            'projected_risk': projected_risk
        }
    
    async def stress_test_portfolio(
        self,
        portfolio: Portfolio,
        scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Run stress tests on portfolio.
        
        Args:
            portfolio: Current portfolio
            scenarios: Optional custom stress scenarios
            
        Returns:
            Stress test results and recommendations
        """
        if not scenarios:
            scenarios = self._get_default_stress_scenarios()
        
        results = {}
        worst_case_loss = 0
        
        for scenario in scenarios:
            scenario_result = self._run_stress_scenario(portfolio, scenario)
            results[scenario['name']] = scenario_result
            worst_case_loss = min(worst_case_loss, scenario_result['portfolio_change'])
        
        # Get AI interpretation if available
        if self.ollama_client:
            ai_analysis = await self._get_ai_stress_test_analysis(
                results,
                portfolio,
                worst_case_loss
            )
            interpretation = ai_analysis.get('interpretation', '')
            recommendations = ai_analysis.get('recommendations', [])
        else:
            interpretation = f"Worst case loss: {worst_case_loss:.1%}"
            recommendations = []
            if worst_case_loss < -0.10:
                recommendations.append("Consider hedging strategies")
        
        return {
            'scenarios': results,
            'worst_case_loss': worst_case_loss,
            'interpretation': interpretation,
            'recommendations': recommendations,
            'timestamp': datetime.now()
        }
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Get current risk summary.
        
        Returns:
            Summary of current risk status
        """
        if not self.risk_history:
            return {"message": "No risk assessments available"}
        
        latest_assessment = self.risk_history[-1]
        
        return {
            'current_risk_level': latest_assessment.risk_level.value,
            'risk_score': latest_assessment.risk_metrics.risk_score,
            'violations': len(latest_assessment.violations),
            'circuit_breaker_active': self.circuit_breaker_active,
            'last_assessment': latest_assessment.timestamp,
            'confidence': latest_assessment.confidence_score
        }
    
    # ==========================================================================
    # PRIVATE METHODS - RISK CALCULATIONS
    # ==========================================================================
    def _calculate_risk_metrics(
        self,
        portfolio: Portfolio,
        market_data: Optional[Dict[str, Any]] = None
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics."""
        # Portfolio VaR and CVaR
        portfolio_var = self._calculate_var(portfolio, self.risk_limits['var_confidence'])
        portfolio_cvar = self._calculate_cvar(portfolio, self.risk_limits['var_confidence'])
        
        # Risk ratios
        sharpe_ratio = self._calculate_sharpe_ratio()
        sortino_ratio = self._calculate_sortino_ratio()
        
        # Drawdown
        max_drawdown = portfolio.max_drawdown
        current_drawdown = self._calculate_current_drawdown(portfolio)
        
        # Position concentration
        position_concentration = self._calculate_concentration_risk(portfolio)
        
        # Correlation risk
        correlation_risk = self._calculate_correlation_risk(portfolio)
        
        # Stress tests
        stress_results = self._quick_stress_test(portfolio)
        
        # Overall risk score (0-100)
        risk_score = self._calculate_risk_score(
            portfolio_var,
            current_drawdown,
            position_concentration,
            correlation_risk
        )
        
        return RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=portfolio_var,
            portfolio_cvar=portfolio_cvar,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            position_concentration=position_concentration,
            correlation_risk=correlation_risk,
            stress_test_results=stress_results,
            risk_score=risk_score
        )
    
    def _calculate_var(self, portfolio: Portfolio, confidence: float) -> float:
        """Calculate Value at Risk."""
        if not self.historical_returns:
            # Use position-based estimate
            total_risk = sum(abs(p.market_value * 0.02) for p in portfolio.positions)
            return total_risk / portfolio.total_value if portfolio.total_value > 0 else 0
        
        # Historical VaR
        returns = np.array(self.historical_returns)
        var_percentile = (1 - confidence) * 100
        var = np.percentile(returns, var_percentile)
        
        return abs(var)
    
    def _calculate_cvar(self, portfolio: Portfolio, confidence: float) -> float:
        """Calculate Conditional Value at Risk."""
        if not self.historical_returns:
            # Use VaR * 1.25 as estimate
            return self._calculate_var(portfolio, confidence) * 1.25
        
        # Historical CVaR
        returns = np.array(self.historical_returns)
        var_percentile = (1 - confidence) * 100
        var = np.percentile(returns, var_percentile)
        
        # Average of returns worse than VaR
        worse_returns = returns[returns <= var]
        cvar = np.mean(worse_returns) if len(worse_returns) > 0 else var
        
        return abs(cvar)
    
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio."""
        if len(self.historical_returns) < 20:
            return 0.0
        
        returns = np.array(self.historical_returns)
        excess_returns = returns - (RISK_FREE_RATE / 252)  # Daily risk-free rate
        
        if returns.std() == 0:
            return 0.0
        
        return (excess_returns.mean() / returns.std()) * np.sqrt(252)
    
    def _calculate_sortino_ratio(self) -> float:
        """Calculate Sortino ratio."""
        if len(self.historical_returns) < 20:
            return 0.0
        
        returns = np.array(self.historical_returns)
        excess_returns = returns - (RISK_FREE_RATE / 252)
        
        # Downside deviation
        negative_returns = returns[returns < 0]
        if len(negative_returns) == 0:
            return self._calculate_sharpe_ratio()  # No downside
        
        downside_std = np.std(negative_returns)
        if downside_std == 0:
            return 0.0
        
        return (excess_returns.mean() / downside_std) * np.sqrt(252)
    
    def _calculate_current_drawdown(self, portfolio: Portfolio) -> float:
        """Calculate current drawdown from peak."""
        # In production, this would track actual peak
        # For now, use simple calculation
        if portfolio.daily_pnl < 0:
            return abs(portfolio.daily_pnl / portfolio.total_value)
        return 0.0
    
    def _calculate_concentration_risk(self, portfolio: Portfolio) -> float:
        """Calculate position concentration risk."""
        if not portfolio.positions:
            return 0.0
        
        # Herfindahl index
        total_value = sum(abs(p.market_value) for p in portfolio.positions)
        if total_value == 0:
            return 0.0
        
        concentration = sum(
            (abs(p.market_value) / total_value) ** 2
            for p in portfolio.positions
        )
        
        return concentration
    
    def _calculate_correlation_risk(self, portfolio: Portfolio) -> float:
        """Calculate correlation risk."""
        # Simplified: assume higher correlation with more positions
        # In production, would calculate actual correlations
        num_positions = len(portfolio.positions)
        if num_positions <= 1:
            return 0.0
        
        # Estimate correlation impact
        return min(0.5, num_positions * 0.05)
    
    def _quick_stress_test(self, portfolio: Portfolio) -> Dict[str, float]:
        """Run quick stress test scenarios."""
        scenarios = {
            'market_down_5%': -0.05,
            'market_down_10%': -0.10,
            'volatility_spike': -0.03,
            'black_swan': -0.20
        }
        
        results = {}
        for scenario, shock in scenarios.items():
            # Simple calculation - in production would be more sophisticated
            portfolio_impact = sum(
                p.market_value * shock * (p.delta if p.delta else 1.0)
                for p in portfolio.positions
            )
            results[scenario] = portfolio_impact / portfolio.total_value if portfolio.total_value > 0 else 0
        
        return results
    
    def _calculate_risk_score(
        self,
        var: float,
        drawdown: float,
        concentration: float,
        correlation: float
    ) -> float:
        """Calculate overall risk score (0-100)."""
        # Weight different risk factors
        var_score = min(100, var / self.risk_limits['max_portfolio_risk'] * 100)
        dd_score = min(100, drawdown / self.risk_limits['max_drawdown'] * 100)
        conc_score = min(100, concentration * 200)  # 0.5 concentration = 100
        corr_score = min(100, correlation * 200)
        
        # Weighted average
        weights = [0.3, 0.3, 0.2, 0.2]
        scores = [var_score, dd_score, conc_score, corr_score]
        
        risk_score = sum(w * s for w, s in zip(weights, scores))
        
        return min(100, max(0, risk_score))
    
    # ==========================================================================
    # PRIVATE METHODS - RISK CHECKS
    # ==========================================================================
    def _check_risk_violations(
        self,
        risk_metrics: RiskMetrics,
        portfolio: Portfolio
    ) -> List[str]:
        """Check for risk limit violations."""
        violations = []
        
        # Portfolio risk violations
        if risk_metrics.portfolio_var > self.risk_limits['max_portfolio_risk']:
            violations.append(
                f"Portfolio VaR ({risk_metrics.portfolio_var:.1%}) exceeds limit "
                f"({self.risk_limits['max_portfolio_risk']:.1%})"
            )
        
        # Drawdown violations
        if risk_metrics.current_drawdown > self.risk_limits['max_drawdown']:
            violations.append(
                f"Current drawdown ({risk_metrics.current_drawdown:.1%}) exceeds limit "
                f"({self.risk_limits['max_drawdown']:.1%})"
            )
        
        # Daily loss violations
        if portfolio.daily_pnl / portfolio.total_value < -self.risk_limits['daily_loss_limit']:
            violations.append(
                f"Daily loss exceeds limit ({self.risk_limits['daily_loss_limit']:.1%})"
            )
        
        # Concentration violations
        if risk_metrics.position_concentration > 0.4:
            violations.append("Excessive position concentration risk")
        
        # Risk score violations
        if risk_metrics.risk_score > 80:
            violations.append(f"Overall risk score too high ({risk_metrics.risk_score:.0f}/100)")
        
        return violations
    
    def _determine_risk_level(
        self,
        risk_metrics: RiskMetrics,
        violations: List[str]
    ) -> RiskLevel:
        """Determine overall risk level."""
        if len(violations) >= 3 or risk_metrics.risk_score > 90:
            return RiskLevel.CRITICAL
        elif len(violations) >= 2 or risk_metrics.risk_score > 80:
            return RiskLevel.EXTREME
        elif len(violations) >= 1 or risk_metrics.risk_score > 60:
            return RiskLevel.HIGH
        elif risk_metrics.risk_score > 40:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def _generate_recommendations(
        self,
        risk_metrics: RiskMetrics,
        violations: List[str],
        portfolio: Portfolio
    ) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # VaR recommendations
        if risk_metrics.portfolio_var > self.risk_limits['max_portfolio_risk'] * 0.8:
            recommendations.append("Consider reducing overall portfolio exposure")
        
        # Drawdown recommendations
        if risk_metrics.current_drawdown > self.risk_limits['max_drawdown'] * 0.5:
            recommendations.append("Implement defensive strategies to protect capital")
        
        # Concentration recommendations
        if risk_metrics.position_concentration > 0.3:
            recommendations.append("Diversify positions to reduce concentration risk")
        
        # Sharpe ratio recommendations
        if risk_metrics.sharpe_ratio < 0.5:
            recommendations.append("Review strategy performance - low risk-adjusted returns")
        
        # Stress test recommendations
        worst_scenario = min(risk_metrics.stress_test_results.values())
        if worst_scenario < -0.15:
            recommendations.append("Consider tail risk hedging strategies")
        
        return recommendations
    
    def _determine_required_actions(
        self,
        risk_level: RiskLevel,
        violations: List[str],
        portfolio: Portfolio
    ) -> List[RiskAction]:
        """Determine required risk management actions."""
        actions = []
        
        if risk_level == RiskLevel.CRITICAL:
            actions.append(RiskAction.HALT_TRADING)
            actions.append(RiskAction.CLOSE_POSITION)
        elif risk_level == RiskLevel.EXTREME:
            actions.append(RiskAction.REDUCE_SIZE)
            actions.append(RiskAction.HEDGE)
        elif risk_level == RiskLevel.HIGH:
            actions.append(RiskAction.ADJUST_LIMITS)
        
        # Check for specific violations
        for violation in violations:
            if "Daily loss" in violation:
                actions.append(RiskAction.HALT_TRADING)
            elif "drawdown" in violation:
                actions.append(RiskAction.REDUCE_SIZE)
        
        return list(set(actions))  # Remove duplicates
    
    # ==========================================================================
    # PRIVATE METHODS - TRADE EVALUATION
    # ==========================================================================
    def _calculate_trade_impact(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio
    ) -> Dict[str, Any]:
        """Calculate the impact of a proposed trade."""
        # Estimate position value
        position_value = trade_request.quantity * (trade_request.price or 100) * 100
        
        # Risk contribution
        risk_contribution = abs(position_value * trade_request.expected_risk)
        risk_contribution_pct = risk_contribution / portfolio.total_value if portfolio.total_value > 0 else 0
        
        # Portfolio impact
        new_total_value = portfolio.total_value + position_value
        concentration_impact = position_value / new_total_value if new_total_value > 0 else 0
        
        return {
            'position_value': position_value,
            'risk_contribution': risk_contribution_pct,
            'concentration_impact': concentration_impact,
            'expected_return': trade_request.expected_return,
            'risk_reward_ratio': (
                trade_request.expected_return / trade_request.expected_risk
                if trade_request.expected_risk > 0 else 0
            )
        }
    
    def _check_position_limits(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio
    ) -> Dict[str, Any]:
        """Check if trade violates position limits."""
        # Check number of positions
        max_positions = self.config.get('max_positions', 10)
        current_positions = len(portfolio.positions)
        
        # Check if adding new position
        is_new_position = not any(
            p.symbol == trade_request.symbol for p in portfolio.positions
        )
        
        if is_new_position and current_positions >= max_positions:
            return {
                'passed': False,
                'reason': f'Maximum positions ({max_positions}) reached'
            }
        
        # Check position size limits
        position_value = trade_request.quantity * (trade_request.price or 100) * 100
        max_position_value = portfolio.total_value * 0.2  # 20% max per position
        
        if position_value > max_position_value:
            return {
                'passed': False,
                'reason': f'Position size exceeds 20% of portfolio'
            }
        
        return {'passed': True, 'reason': 'Position limits OK'}
    
    def _project_portfolio_risk(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio,
        trade_impact: Dict[str, Any]
    ) -> float:
        """Project portfolio risk with new trade."""
        # Current portfolio risk
        current_risk = portfolio.current_risk
        
        # Add trade risk contribution
        projected_risk = current_risk + trade_impact['risk_contribution']
        
        # Adjust for correlation (simplified)
        correlation_adjustment = 0.8  # Assume 80% correlation benefit
        projected_risk *= correlation_adjustment
        
        return projected_risk
    
    def _get_evaluation_reason(
        self,
        approved: bool,
        position_check: Dict[str, Any],
        projected_risk: float,
        trade_impact: Dict[str, Any]
    ) -> str:
        """Generate evaluation reason."""
        if not approved:
            if not position_check['passed']:
                return position_check['reason']
            elif projected_risk > self.risk_limits['max_portfolio_risk']:
                return f"Projected portfolio risk ({projected_risk:.1%}) exceeds limit"
            elif trade_impact['risk_contribution'] > self.risk_limits['max_position_risk']:
                return f"Position risk contribution too high"
            else:
                return "Trade rejected due to risk constraints"
        else:
            return f"Trade approved - Risk within limits ({projected_risk:.1%})"
    
    # ==========================================================================
    # PRIVATE METHODS - CIRCUIT BREAKERS
    # ==========================================================================
    def _check_circuit_breakers(
        self,
        assessment: RiskAssessment,
        portfolio: Portfolio
    ):
        """Check and activate circuit breakers if needed."""
        # Daily loss circuit breaker
        daily_loss_pct = portfolio.daily_pnl / portfolio.total_value if portfolio.total_value > 0 else 0
        if daily_loss_pct < -self.risk_limits['daily_loss_limit']:
            self._activate_circuit_breaker("Daily loss limit exceeded")
            
        # Consecutive losses circuit breaker
        if portfolio.daily_pnl < 0:
            self.daily_losses.append(portfolio.daily_pnl)
            if len(self.daily_losses) == CONSECUTIVE_LOSSES and all(loss < 0 for loss in self.daily_losses):
                self._activate_circuit_breaker("Consecutive losses limit reached")
        
        # Risk level circuit breaker
        if assessment.risk_level == RiskLevel.CRITICAL:
            self._activate_circuit_breaker("Critical risk level reached")
    
    def _activate_circuit_breaker(self, reason: str):
        """Activate circuit breaker."""
        self.circuit_breaker_active = True
        self.last_circuit_breaker_time = datetime.now()
        self.logger.warning(f"CIRCUIT BREAKER ACTIVATED: {reason}")
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker (manual override)."""
        self.circuit_breaker_active = False
        self.daily_losses.clear()
        self.logger.info("Circuit breaker reset")
    
    # ==========================================================================
    # PRIVATE METHODS - AI INTEGRATION
    # ==========================================================================
    async def _get_ai_risk_insights(
        self,
        risk_metrics: RiskMetrics,
        portfolio: Portfolio,
        violations: List[str],
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get AI insights on risk using Ollama."""
        try:
            prompt = self._build_risk_prompt(risk_metrics, portfolio, violations, market_data)
            
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            return self._parse_ai_risk_response(response['response'])
            
        except Exception as e:
            self.logger.error(f"Error getting AI risk insights: {e}")
            return {}
    
    async def _get_ai_trade_evaluation(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio,
        trade_impact: Dict[str, Any],
        projected_risk: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get AI evaluation of trade using Ollama."""
        try:
            prompt = self._build_trade_evaluation_prompt(
                trade_request,
                portfolio,
                trade_impact,
                projected_risk,
                market_data
            )
            
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            return self._parse_ai_trade_response(response['response'])
            
        except Exception as e:
            self.logger.error(f"Error getting AI trade evaluation: {e}")
            return {
                'approved': projected_risk < self.risk_limits['max_portfolio_risk'],
                'reason': 'AI evaluation unavailable - using rule-based decision',
                'recommendations': []
            }
    
    async def _get_ai_stress_test_analysis(
        self,
        results: Dict[str, Any],
        portfolio: Portfolio,
        worst_case_loss: float
    ) -> Dict[str, Any]:
        """Get AI analysis of stress test results."""
        try:
            prompt = self._build_stress_test_prompt(results, portfolio, worst_case_loss)
            
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )
            
            return self._parse_ai_stress_response(response['response'])
            
        except Exception as e:
            self.logger.error(f"Error getting AI stress test analysis: {e}")
            return {
                'interpretation': f"Stress test shows worst case loss of {worst_case_loss:.1%}",
                'recommendations': []
            }
    
    def _build_risk_prompt(
        self,
        risk_metrics: RiskMetrics,
        portfolio: Portfolio,
        violations: List[str],
        market_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build risk assessment prompt for Ollama."""
        violations_str = "\n".join(f"- {v}" for v in violations) if violations else "None"
        
        market_str = ""
        if market_data:
            market_str = f"\nMarket Context:\n- VIX: {market_data.get('vix', 'N/A')}\n- Trend: {market_data.get('trend', 'N/A')}"
        
        prompt = f"""You are an expert risk manager analyzing portfolio risk.

Portfolio Metrics:
- Total Value: ${portfolio.total_value:,.2f}
- Current Risk: {portfolio.current_risk:.1%}
- Daily P&L: ${portfolio.daily_pnl:,.2f}
- Number of Positions: {len(portfolio.positions)}

Risk Metrics:
- Portfolio VaR (95%): {risk_metrics.portfolio_var:.1%}
- Portfolio CVaR: {risk_metrics.portfolio_cvar:.1%}
- Sharpe Ratio: {risk_metrics.sharpe_ratio:.2f}
- Sortino Ratio: {risk_metrics.sortino_ratio:.2f}
- Current Drawdown: {risk_metrics.current_drawdown:.1%}
- Risk Score: {risk_metrics.risk_score:.0f}/100

Violations:
{violations_str}
{market_str}

Provide risk analysis as JSON with:
1. Key risk factors to monitor
2. Specific recommendations for risk reduction
3. Hidden risks not captured in metrics
4. Overall confidence in risk assessment (0-1)

Format: {{"risk_factors": [], "recommendations": [], "hidden_risks": [], "confidence": 0.8}}"""

        return prompt
    
    def _build_trade_evaluation_prompt(
        self,
        trade_request: TradeRequest,
        portfolio: Portfolio,
        trade_impact: Dict[str, Any],
        projected_risk: float,
        market_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build trade evaluation prompt for Ollama."""
        market_str = ""
        if market_data:
            market_str = f"\nMarket: VIX={market_data.get('vix', 'N/A')}"
        
        prompt = f"""You are a risk manager evaluating a trade request.

Trade Request:
- Symbol: {trade_request.symbol}
- Side: {trade_request.side}
- Quantity: {trade_request.quantity}
- Strategy: {trade_request.strategy_type}
- Expected Risk: {trade_request.expected_risk:.1%}
- Expected Return: {trade_request.expected_return:.1%}

Portfolio:
- Total Value: ${portfolio.total_value:,.2f}
- Current Risk: {portfolio.current_risk:.1%}
- Available Cash: ${portfolio.cash:,.2f}

Trade Impact:
- Risk Contribution: {trade_impact['risk_contribution']:.1%}
- Projected Portfolio Risk: {projected_risk:.1%}
- Risk/Reward Ratio: {trade_impact['risk_reward_ratio']:.2f}
{market_str}

Should this trade be approved? Provide decision as JSON:
{{"approved": true/false, "reason": "explanation", "recommendations": ["list of recommendations if any"]}}"""

        return prompt
    
    def _build_stress_test_prompt(
        self,
        results: Dict[str, Any],
        portfolio: Portfolio,
        worst_case_loss: float
    ) -> str:
        """Build stress test analysis prompt."""
        scenarios_str = "\n".join(
            f"- {name}: {result['portfolio_change']:.1%}"
            for name, result in results.items()
        )
        
        prompt = f"""You are a risk expert analyzing stress test results.

Portfolio Value: ${portfolio.total_value:,.2f}

Stress Test Results:
{scenarios_str}

Worst Case Loss: {worst_case_loss:.1%}

Provide analysis as JSON with:
1. Interpretation of results
2. Specific hedging recommendations
3. Risk mitigation strategies

Format: {{"interpretation": "text", "recommendations": ["list"]}}"""

        return prompt
    
    def _parse_ai_risk_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama risk assessment response."""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
        except:
            pass
        
        return {
            'risk_factors': [],
            'recommendations': [],
            'hidden_risks': [],
            'confidence': 0.7
        }
    
    def _parse_ai_trade_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama trade evaluation response."""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                data = json.loads(json_str)
                return {
                    'approved': bool(data.get('approved', False)),
                    'reason': data.get('reason', ''),
                    'recommendations': data.get('recommendations', [])
                }
        except:
            pass
        
        return {
            'approved': False,
            'reason': 'Failed to parse AI response',
            'recommendations': []
        }
    
    def _parse_ai_stress_response(self, response: str) -> Dict[str, Any]:
        """Parse Ollama stress test response."""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
        except:
            pass
        
        return {
            'interpretation': 'Stress test analysis unavailable',
            'recommendations': []
        }
    
    # ==========================================================================
    # PRIVATE METHODS - STRESS TESTING
    # ==========================================================================
    def _get_default_stress_scenarios(self) -> List[Dict[str, Any]]:
        """Get default stress test scenarios."""
        return [
            {
                'name': 'Market Crash',
                'market_shock': -0.20,
                'volatility_shock': 2.0,
                'correlation': 0.9
            },
            {
                'name': 'Flash Crash',
                'market_shock': -0.10,
                'volatility_shock': 3.0,
                'correlation': 0.95
            },
            {
                'name': 'Volatility Spike',
                'market_shock': -0.05,
                'volatility_shock': 2.5,
                'correlation': 0.7
            },
            {
                'name': 'Liquidity Crisis',
                'market_shock': -0.15,
                'volatility_shock': 1.5,
                'correlation': 0.8
            }
        ]
    
    def _run_stress_scenario(
        self,
        portfolio: Portfolio,
        scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run a single stress scenario."""
        total_impact = 0
        
        for position in portfolio.positions:
            # Market impact
            market_impact = position.market_value * scenario['market_shock']
            
            # Adjust for position delta
            if position.delta:
                market_impact *= abs(position.delta)
            
            # Volatility impact
            if position.vega:
                vol_impact = position.vega * scenario['volatility_shock'] * 100
                market_impact += vol_impact
            
            total_impact += market_impact
        
        portfolio_change = total_impact / portfolio.total_value if portfolio.total_value > 0 else 0
        
        return {
            'portfolio_change': portfolio_change,
            'dollar_impact': total_impact,
            'margin_call_risk': portfolio_change < -0.15
        }
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def update_returns(self, daily_return: float):
        """Update historical returns for risk calculations."""
        self.historical_returns.append(daily_return)
    
    def update_volatility(self, volatility: float):
        """Update volatility history."""
        self.volatility_history.append(volatility)
    
    def clear_history(self):
        """Clear risk assessment history."""
        self.risk_history.clear()
        self.historical_returns.clear()
        self.volatility_history.clear()
        self.daily_losses.clear()
        self.logger.info("Risk history cleared")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_guardian_agent(config: Optional[Dict[str, Any]] = None) -> SpyderX04_RiskGuardianAgent:
    """
    Factory function to create Risk Guardian Agent.
    
    Args:
        config: Optional configuration dictionary
        
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
    if _module_instance is None:
        _module_instance = SpyderX04_RiskGuardianAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    async def test_agent():
        """Test the Risk Guardian Agent."""
        # Create agent
        config = {
            'llm_model': 'llama3.2:3b-instruct-q4_K_M',
            'temperature': 0.2,
            'max_portfolio_risk': 0.02,
            'max_drawdown': 0.10
        }
        
        agent = create_risk_guardian_agent(config)
        
        # Create sample portfolio
        positions = [
            Position(
                symbol="SPY_CALL_550",
                quantity=10,
                entry_price=5.00,
                current_price=5.50,
                position_type='long',
                market_value=5500,
                unrealized_pnl=500,
                delta=0.45,
                gamma=0.02,
                vega=0.15,
                theta=-0.25
            ),
            Position(
                symbol="SPY_PUT_540",
                quantity=5,
                entry_price=4.00,
                current_price=3.50,
                position_type='long',
                market_value=1750,
                unrealized_pnl=-250,
                delta=-0.35,
                gamma=0.02,
                vega=0.12,
                theta=-0.20
            )
        ]
        
        portfolio = Portfolio(
            cash=20000,
            positions=positions,
            total_value=27250,
            current_risk=0.015,
            max_drawdown=0.05,
            daily_pnl=250,
            realized_pnl=1500
        )
        
        # Test portfolio risk assessment
        print("="*80)
        print("TESTING RISK GUARDIAN AGENT")
        print("="*80)
        print(f"Portfolio Value: ${portfolio.total_value:,.2f}")
        print(f"Positions: {len(portfolio.positions)}")
        print("\nAssessing portfolio risk...")
        
        assessment = await agent.assess_portfolio_risk(
            portfolio,
            {'vix': 16.5, 'trend': 'bullish'}
        )
        
        print("\n" + "="*60)
        print("RISK ASSESSMENT RESULTS")
        print("="*60)
        print(f"Risk Level: {assessment.risk_level.value.upper()}")
        print(f"Risk Score: {assessment.risk_metrics.risk_score:.0f}/100")
        print(f"Portfolio VaR (95%): {assessment.risk_metrics.portfolio_var:.1%}")
        print(f"Sharpe Ratio: {assessment.risk_metrics.sharpe_ratio:.2f}")
        print(f"Confidence: {assessment.confidence_score:.1%}")
        
        if assessment.violations:
            print("\nViolations:")
            for violation in assessment.violations:
                print(f"  ⚠️  {violation}")
        
        if assessment.recommendations:
            print("\nRecommendations:")
            for rec in assessment.recommendations:
                print(f"  • {rec}")
        
        # Test trade evaluation
        trade_request = TradeRequest(
            symbol="SPY_CALL_560",
            quantity=20,
            side='buy',
            order_type='limit',
            price=3.00,
            strategy_type='bull_call_spread',
            expected_risk=0.005,
            expected_return=0.015
        )
        
        print("\n" + "="*60)
        print("TRADE EVALUATION")
        print("="*60)
        print(f"Trade: BUY {trade_request.quantity} {trade_request.symbol}")
        
        evaluation = await agent.evaluate_trade(trade_request, portfolio)
        
        print(f"Decision: {'APPROVED ✅' if evaluation['approved'] else 'REJECTED ❌'}")
        print(f"Reason: {evaluation['reason']}")
        print(f"Action: {evaluation['action'].value}")
        
        if evaluation.get('recommendations'):
            print("Recommendations:")
            for rec in evaluation['recommendations']:
                print(f"  • {rec}")
        
        # Test stress testing
        print("\n" + "="*60)
        print("STRESS TEST RESULTS")
        print("="*60)
        
        stress_results = await agent.stress_test_portfolio(portfolio)
        
        print(f"Worst Case Loss: {stress_results['worst_case_loss']:.1%}")
        print("\nScenario Results:")
        for scenario, result in stress_results['scenarios'].items():
            print(f"  {scenario}: {result['portfolio_change']:.1%}")
        
        if stress_results.get('recommendations'):
            print("\nStress Test Recommendations:")
            for rec in stress_results['recommendations']:
                print(f"  • {rec}")
        
        # Show risk summary
        print("\n" + "="*60)
        print("RISK SUMMARY")
        print("="*60)
        summary = agent.get_risk_summary()
        for key, value in summary.items():
            print(f"{key}: {value}")
    
    # Run test
    asyncio.run(test_agent())
