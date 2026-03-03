#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX04_RiskGuardianAgent.py
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
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import statistics
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.info("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU11_FeatureFlags import is_spyderx_enabled, SPYDERX_FEATURE_FLAGS
from Spyder.SpyderM_Monitoring.SpyderM07_MigrationMonitor import get_migration_monitor
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskManager
from Spyder.SpyderE_Risk.SpyderE02_PositionSizer import PositionSizer
from Spyder.SpyderE_Risk.SpyderE03_DrawdownControl import DrawdownController

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model configuration
DEFAULT_MODEL = "llama3" if OLLAMA_AVAILABLE else None
DEFAULT_TEMPERATURE = 0.2  # Lower temperature for conservative risk decisions

# Risk thresholds
MAX_PORTFOLIO_RISK = 0.02  # 2% max portfolio risk
MAX_POSITION_RISK = 0.005  # 0.5% max position risk
MAX_DRAWDOWN = 0.10  # 10% max drawdown
CORRELATION_THRESHOLD = 0.7  # High correlation threshold
VAR_CONFIDENCE = 0.95  # 95% VaR confidence level
STRESS_TEST_SCENARIOS = 20  # Number of stress test scenarios

# Circuit breaker levels
CIRCUIT_BREAKER_LEVELS = {
    'WARNING': 0.6,    # 60% of limit
    'CRITICAL': 0.8,   # 80% of limit
    'EMERGENCY': 0.95  # 95% of limit
}

# AI confidence thresholds
MIN_CONFIDENCE_RISK = 0.75  # Higher threshold for risk decisions
HIGH_CONFIDENCE_RISK = 0.90

# Cache configuration
RISK_CACHE_TTL = 60  # 1 minute for risk calculations

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk level classification"""
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class RiskMetric(Enum):
    """Risk metrics enumeration"""
    VAR = "value_at_risk"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    BETA = "beta"
    CORRELATION = "correlation"

class RiskAction(Enum):
    """Risk management actions"""
    CONTINUE = "continue"
    REDUCE_POSITION = "reduce_position"
    HEDGE_REQUIRED = "hedge_required"
    STOP_TRADING = "stop_trading"
    EMERGENCY_LIQUIDATION = "emergency_liquidation"

class StressScenario(Enum):
    """Stress test scenarios"""
    MARKET_CRASH = "market_crash"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    BLACK_SWAN = "black_swan"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskMetrics:
    """Comprehensive risk metrics container"""
    portfolio_var: float
    portfolio_es: float  # Expected Shortfall
    position_risks: Dict[str, float]
    correlation_matrix: np.ndarray
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    beta: float
    risk_contribution: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RiskAssessment:
    """AI-enhanced risk assessment"""
    risk_level: RiskLevel
    risk_metrics: RiskMetrics
    risk_factors: Dict[str, float]
    stress_test_results: Dict[str, float]
    recommended_actions: List[Dict[str, Any]]
    natural_language_assessment: str
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionLimit:
    """Dynamic position limits"""
    max_position_size: int
    max_portfolio_allocation: float
    max_sector_exposure: float
    max_correlation_exposure: float
    adjustment_reason: str
    confidence: float

@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status"""
    active: bool
    level: Optional[str] = None
    triggered_metrics: List[str] = field(default_factory=list)
    activation_time: Optional[datetime] = None
    estimated_reset_time: Optional[datetime] = None
    override_allowed: bool = False

@dataclass
class AIRiskInsight:
    """AI-generated risk insight"""
    summary: str
    key_risks: List[str]
    opportunities: List[str]
    recommended_hedges: List[Dict[str, Any]]
    market_context: str
    confidence: float
    reasoning: Optional[str] = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX04_RiskGuardianAgent:
    """
    AI-Enhanced Risk Guardian Agent for intelligent portfolio protection.
    
    This agent provides sophisticated risk management by combining traditional
    risk metrics with AI-powered analysis. It monitors portfolio risk in real-time,
    adjusts position limits dynamically, and can trigger circuit breakers when
    necessary to protect capital.
    
    Attributes:
        model_name: Ollama model for AI analysis
        temperature: Temperature setting for AI responses
        risk_cache: Cache for risk calculations
        circuit_breaker: Circuit breaker status
        risk_history: Historical risk metrics
    """
    
    def __init__(self, model_name: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the Risk Guardian Agent"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.model_name = model_name
        self.temperature = temperature
        
        # Initialize components
        self.traditional_risk_manager = RiskManager()
        self.position_sizer = PositionSizer()
        self.drawdown_controller = DrawdownController()
        self.migration_monitor = get_migration_monitor()
        
        # Risk tracking
        self.risk_cache = {}
        self.cache_timestamps = {}
        self.risk_history = deque(maxlen=1000)
        self.circuit_breaker = CircuitBreakerStatus(active=False)
        
        # Performance tracking
        self.performance_metrics = {
            'assessments': 0,
            'ai_queries': 0,
            'circuit_breaker_triggers': 0,
            'risk_overrides': 0,
            'avg_confidence': 0.0,
            'prevented_losses': 0.0
        }
        
        # Risk limits (can be adjusted dynamically)
        self.risk_limits = {
            'max_portfolio_risk': MAX_PORTFOLIO_RISK,
            'max_position_risk': MAX_POSITION_RISK,
            'max_drawdown': MAX_DRAWDOWN,
            'max_correlation': CORRELATION_THRESHOLD
        }
        
        self.logger.info(f"Risk Guardian Agent initialized with model: {model_name}")
    
    # ==========================================================================
    # PUBLIC METHODS - MAIN FUNCTIONALITY
    # ==========================================================================
    async def assess_portfolio_risk(
        self,
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> RiskAssessment:
        """
        Perform comprehensive AI-enhanced risk assessment.
        
        Args:
            portfolio: Current portfolio state
            market_conditions: Current market conditions
            
        Returns:
            RiskAssessment with AI insights and recommendations
        """
        try:
            # Calculate traditional risk metrics
            risk_metrics = await self._calculate_risk_metrics(portfolio, market_conditions)
            
            # Store in history
            self.risk_history.append({
                'timestamp': datetime.now(),
                'metrics': risk_metrics,
                'portfolio_value': portfolio.get('total_value', 0)
            })
            
            # Run stress tests
            stress_results = await self._run_stress_tests(portfolio, market_conditions)
            
            # Get AI-enhanced assessment if enabled
            if is_spyderx_enabled("USE_AI_RISK") and OLLAMA_AVAILABLE:
                assessment = await self._enhance_with_ai_risk_analysis(
                    risk_metrics, stress_results, portfolio, market_conditions
                )
            else:
                # Fallback to rule-based assessment
                assessment = self._create_rule_based_assessment(
                    risk_metrics, stress_results
                )
            
            # Check circuit breakers
            await self._check_circuit_breakers(assessment)
            
            # Update performance metrics
            self.performance_metrics['assessments'] += 1
            self.performance_metrics['avg_confidence'] = (
                (self.performance_metrics['avg_confidence'] * 
                 (self.performance_metrics['assessments'] - 1) +
                 assessment.confidence_score) / 
                self.performance_metrics['assessments']
            )
            
            # Log assessment if in shadow mode
            if is_spyderx_enabled("ENABLE_SPYDERX_SHADOW"):
                await self._log_shadow_assessment(assessment)
            
            return assessment
            
        except Exception as e:
            self.logger.error(f"Risk assessment failed: {e}")
            return self._create_emergency_assessment(str(e))
    
    async def calculate_position_limits(
        self,
        symbol: str,
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> PositionLimit:
        """
        Calculate dynamic position limits with AI optimization.
        
        Args:
            symbol: Trading symbol
            portfolio: Current portfolio state
            market_conditions: Current market conditions
            
        Returns:
            PositionLimit with AI-adjusted limits
        """
        try:
            # Base position sizing
            base_size = self.position_sizer.calculate_position_size(
                portfolio['total_value'],
                self.risk_limits['max_position_risk']
            )
            
            # Get current risk assessment
            risk_assessment = await self.assess_portfolio_risk(portfolio, market_conditions)
            
            # Adjust for risk level
            risk_multiplier = self._get_risk_multiplier(risk_assessment.risk_level)
            
            # AI-enhanced adjustment if enabled
            if is_spyderx_enabled("USE_AI_RISK") and OLLAMA_AVAILABLE:
                limits = await self._calculate_ai_position_limits(
                    symbol, base_size, risk_assessment, market_conditions
                )
            else:
                limits = self._calculate_rule_based_limits(
                    symbol, base_size, risk_multiplier, portfolio
                )
            
            return limits
            
        except Exception as e:
            self.logger.error(f"Position limit calculation failed: {e}")
            return self._create_conservative_limits(str(e))
    
    async def monitor_real_time_risk(
        self,
        portfolio_updates: asyncio.Queue,
        alert_callback: callable
    ) -> None:
        """
        Monitor portfolio risk in real-time with AI alerts.
        
        Args:
            portfolio_updates: Queue of portfolio updates
            alert_callback: Callback function for risk alerts
        """
        self.logger.info("Starting real-time risk monitoring")
        
        while True:
            try:
                # Get portfolio update
                update = await asyncio.wait_for(
                    portfolio_updates.get(),
                    timeout=1.0
                )
                
                # Quick risk check
                risk_level = await self._quick_risk_assessment(update)
                
                # Detailed assessment if risk elevated
                if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EMERGENCY]:
                    assessment = await self.assess_portfolio_risk(
                        update['portfolio'],
                        update['market_conditions']
                    )
                    
                    # Generate alerts
                    alerts = self._generate_risk_alerts(assessment)
                    for alert in alerts:
                        await alert_callback(alert)
                
                # Check circuit breaker status
                if self.circuit_breaker.active:
                    await self._check_circuit_breaker_reset(update)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Real-time monitoring error: {e}")
    
    async def execute_risk_action(
        self,
        action: RiskAction,
        portfolio: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute risk management action with AI validation.
        
        Args:
            action: Risk action to execute
            portfolio: Current portfolio
            params: Additional parameters
            
        Returns:
            Execution result
        """
        try:
            # Validate action with AI if enabled
            if is_spyderx_enabled("USE_AI_RISK") and OLLAMA_AVAILABLE:
                validation = await self._validate_risk_action_ai(action, portfolio, params)
                if not validation['approved']:
                    self.logger.warning(f"AI rejected risk action: {validation['reason']}")
                    return {'success': False, 'reason': validation['reason']}
            
            # Execute action
            result = await self._execute_action(action, portfolio, params)
            
            # Track performance
            if result['success']:
                self._track_risk_action_performance(action, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Risk action execution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    # ==========================================================================
    # PRIVATE METHODS - RISK CALCULATIONS
    # ==========================================================================
    async def _calculate_risk_metrics(
        self,
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> RiskMetrics:
        """Calculate comprehensive risk metrics"""
        positions = portfolio.get('positions', [])
        returns = self._calculate_portfolio_returns(positions, market_conditions)
        
        # VaR and Expected Shortfall
        var = self._calculate_var(returns, VAR_CONFIDENCE)
        es = self._calculate_expected_shortfall(returns, VAR_CONFIDENCE)
        
        # Position-level risks
        position_risks = {}
        risk_contributions = {}
        for position in positions:
            position_var = self._calculate_position_var(position, market_conditions)
            position_risks[position['symbol']] = position_var
            risk_contributions[position['symbol']] = position_var / var if var > 0 else 0
        
        # Correlation matrix
        correlation_matrix = self._calculate_correlation_matrix(positions, market_conditions)
        
        # Drawdown metrics
        max_dd, current_dd = self._calculate_drawdown_metrics(portfolio)
        
        # Risk-adjusted returns
        sharpe = self._calculate_sharpe_ratio(returns)
        sortino = self._calculate_sortino_ratio(returns)
        
        # Beta
        beta = self._calculate_portfolio_beta(returns, market_conditions)
        
        return RiskMetrics(
            portfolio_var=var,
            portfolio_es=es,
            position_risks=position_risks,
            correlation_matrix=correlation_matrix,
            max_drawdown=max_dd,
            current_drawdown=current_dd,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            beta=beta,
            risk_contribution=risk_contributions
        )
    
    def _calculate_portfolio_returns(
        self,
        positions: List[Dict[str, Any]],
        market_conditions: Dict[str, Any]
    ) -> np.ndarray:
        """Calculate portfolio returns series"""
        # Simplified return calculation - in production, use actual price history
        returns = []
        for i in range(252):  # One year of daily returns
            daily_return = np.random.normal(
                market_conditions.get('expected_return', 0.0002),
                market_conditions.get('volatility', 0.015)
            )
            returns.append(daily_return)
        return np.array(returns)
    
    def _calculate_var(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Value at Risk"""
        return -np.percentile(returns, (1 - confidence) * 100)
    
    def _calculate_expected_shortfall(self, returns: np.ndarray, confidence: float) -> float:
        """Calculate Expected Shortfall (CVaR)"""
        var = self._calculate_var(returns, confidence)
        return -returns[returns <= -var].mean()
    
    async def _run_stress_tests(
        self,
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> Dict[str, float]:
        """Run comprehensive stress tests"""
        stress_results = {}
        
        scenarios = {
            StressScenario.MARKET_CRASH: {
                'market_move': -0.20,  # 20% crash
                'vol_multiplier': 3.0,
                'correlation': 0.95
            },
            StressScenario.VOLATILITY_SPIKE: {
                'market_move': -0.05,
                'vol_multiplier': 5.0,
                'correlation': 0.8
            },
            StressScenario.LIQUIDITY_CRISIS: {
                'market_move': -0.10,
                'vol_multiplier': 2.0,
                'correlation': 0.9,
                'liquidity_discount': 0.15
            },
            StressScenario.BLACK_SWAN: {
                'market_move': -0.35,
                'vol_multiplier': 10.0,
                'correlation': 1.0
            }
        }
        
        for scenario, params in scenarios.items():
            loss = await self._simulate_scenario(portfolio, params)
            stress_results[scenario.value] = loss
        
        return stress_results
    
    # ==========================================================================
    # PRIVATE METHODS - AI ENHANCEMENT
    # ==========================================================================
    async def _enhance_with_ai_risk_analysis(
        self,
        risk_metrics: RiskMetrics,
        stress_results: Dict[str, float],
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> RiskAssessment:
        """Enhance risk analysis with AI insights"""
        try:
            # Check cache
            cache_key = self._generate_risk_cache_key(portfolio, market_conditions)
            if self._is_risk_cache_valid(cache_key):
                return self.risk_cache[cache_key]
            
            # Prepare context for AI
            context = {
                'risk_metrics': {
                    'var': risk_metrics.portfolio_var,
                    'expected_shortfall': risk_metrics.portfolio_es,
                    'max_drawdown': risk_metrics.max_drawdown,
                    'current_drawdown': risk_metrics.current_drawdown,
                    'sharpe_ratio': risk_metrics.sharpe_ratio
                },
                'stress_tests': stress_results,
                'portfolio': {
                    'total_value': portfolio.get('total_value', 0),
                    'position_count': len(portfolio.get('positions', [])),
                    'concentration': self._calculate_concentration(portfolio)
                },
                'market': market_conditions,
                'risk_limits': self.risk_limits
            }
            
            # Query AI model
            prompt = self._construct_risk_prompt(context)
            response = await self._query_ai_model(prompt)
            
            # Parse AI response
            ai_insights = self._parse_risk_ai_response(response)
            
            # Determine risk level
            risk_level = self._determine_risk_level(risk_metrics, stress_results, ai_insights)
            
            # Generate recommendations
            recommendations = await self._generate_ai_recommendations(
                risk_level, risk_metrics, ai_insights
            )
            
            assessment = RiskAssessment(
                risk_level=risk_level,
                risk_metrics=risk_metrics,
                risk_factors=self._identify_risk_factors(risk_metrics, market_conditions),
                stress_test_results=stress_results,
                recommended_actions=recommendations,
                natural_language_assessment=ai_insights.summary,
                confidence_score=ai_insights.confidence,
                metadata={
                    'ai_model': self.model_name,
                    'reasoning': ai_insights.reasoning
                }
            )
            
            # Cache result
            self.risk_cache[cache_key] = assessment
            self.cache_timestamps[cache_key] = datetime.now()
            
            self.performance_metrics['ai_queries'] += 1
            
            return assessment
            
        except Exception as e:
            self.logger.error(f"AI risk analysis failed: {e}")
            # Fallback to rule-based
            return self._create_rule_based_assessment(risk_metrics, stress_results)
    
    async def _query_ai_model(self, prompt: str) -> str:
        """Query the AI model for risk analysis"""
        if not OLLAMA_AVAILABLE:
            return ""
            
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert risk management AI for options trading.
                        Analyze risk metrics and provide actionable insights.
                        Be conservative in risk assessment and prioritize capital preservation.
                        Always provide specific, quantified recommendations."""
                    },
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": self.temperature}
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"AI model query failed: {e}")
            return ""
    
    def _construct_risk_prompt(self, context: Dict[str, Any]) -> str:
        """Construct prompt for AI risk analysis"""
        return f"""Analyze the following portfolio risk metrics and provide assessment:

Portfolio Risk Metrics:
- Value at Risk (95%): {context['risk_metrics']['var']:.2%}
- Expected Shortfall: {context['risk_metrics']['expected_shortfall']:.2%}
- Max Drawdown: {context['risk_metrics']['max_drawdown']:.2%}
- Current Drawdown: {context['risk_metrics']['current_drawdown']:.2%}
- Sharpe Ratio: {context['risk_metrics']['sharpe_ratio']:.2f}

Stress Test Results:
{json.dumps(context['stress_tests'], indent=2)}

Portfolio Details:
- Total Value: ${context['portfolio']['total_value']:,.2f}
- Position Count: {context['portfolio']['position_count']}
- Concentration: {context['portfolio']['concentration']:.2%}

Market Conditions:
- Volatility: {context['market'].get('volatility', 0.15):.2%}
- Trend: {context['market'].get('trend', 'neutral')}

Risk Limits:
- Max Portfolio Risk: {context['risk_limits']['max_portfolio_risk']:.2%}
- Max Drawdown: {context['risk_limits']['max_drawdown']:.2%}

Provide:
1. Overall risk assessment (low/moderate/high/critical)
2. Key risk factors and concerns
3. Specific actionable recommendations
4. Suggested position adjustments or hedges
5. Confidence level in your assessment (0-1)

Format as JSON with keys: risk_level, summary, key_risks, recommendations, hedges, confidence"""
    
    # ==========================================================================
    # PRIVATE METHODS - CIRCUIT BREAKERS
    # ==========================================================================
    async def _check_circuit_breakers(self, assessment: RiskAssessment) -> None:
        """Check and potentially trigger circuit breakers"""
        triggers = []
        
        # Check VaR limit
        if assessment.risk_metrics.portfolio_var > self.risk_limits['max_portfolio_risk']:
            triggers.append('portfolio_var_exceeded')
        
        # Check drawdown limit
        if assessment.risk_metrics.current_drawdown > self.risk_limits['max_drawdown']:
            triggers.append('max_drawdown_exceeded')
        
        # Check stress test results
        for scenario, loss in assessment.stress_test_results.items():
            if loss > 0.25:  # 25% loss in stress scenario
                triggers.append(f'stress_test_{scenario}_failed')
        
        # Determine circuit breaker level
        if triggers:
            level = self._determine_circuit_breaker_level(triggers, assessment)
            
            if level and not self.circuit_breaker.active:
                await self._activate_circuit_breaker(level, triggers)
    
    async def _activate_circuit_breaker(self, level: str, triggers: List[str]) -> None:
        """Activate circuit breaker"""
        self.circuit_breaker = CircuitBreakerStatus(
            active=True,
            level=level,
            triggered_metrics=triggers,
            activation_time=datetime.now(),
            estimated_reset_time=datetime.now() + timedelta(minutes=30),
            override_allowed=(level != 'EMERGENCY')
        )
        
        self.performance_metrics['circuit_breaker_triggers'] += 1
        
        self.logger.warning(
            f"Circuit breaker activated: Level={level}, Triggers={triggers}"
        )
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _get_risk_multiplier(self, risk_level: RiskLevel) -> float:
        """Get position size multiplier based on risk level"""
        multipliers = {
            RiskLevel.MINIMAL: 1.2,
            RiskLevel.LOW: 1.0,
            RiskLevel.MODERATE: 0.8,
            RiskLevel.HIGH: 0.5,
            RiskLevel.CRITICAL: 0.2,
            RiskLevel.EMERGENCY: 0.0
        }
        return multipliers.get(risk_level, 0.5)
    
    def _calculate_concentration(self, portfolio: Dict[str, Any]) -> float:
        """Calculate portfolio concentration (Herfindahl index)"""
        positions = portfolio.get('positions', [])
        if not positions:
            return 0.0
            
        total_value = sum(p.get('value', 0) for p in positions)
        if total_value == 0:
            return 0.0
            
        concentration = sum(
            (p.get('value', 0) / total_value) ** 2
            for p in positions
        )
        return concentration
    
    def _is_risk_cache_valid(self, cache_key: str) -> bool:
        """Check if cached risk assessment is still valid"""
        if cache_key not in self.cache_timestamps:
            return False
            
        age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
        return age < RISK_CACHE_TTL
    
    def _generate_risk_cache_key(
        self,
        portfolio: Dict[str, Any],
        market_conditions: Dict[str, Any]
    ) -> str:
        """Generate cache key for risk assessment"""
        key_data = {
            'positions': len(portfolio.get('positions', [])),
            'value': portfolio.get('total_value', 0),
            'volatility': market_conditions.get('volatility', 0)
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics"""
        return self.performance_metrics.copy()
    
    def get_risk_history(self, periods: int = 100) -> List[Dict[str, Any]]:
        """Get recent risk history"""
        return list(self.risk_history)[-periods:]

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_guardian_agent(
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE
) -> SpyderX04_RiskGuardianAgent:
    """
    Factory function to create Risk Guardian Agent instance.
    
    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses
        
    Returns:
        SpyderX04_RiskGuardianAgent instance
    """
    return SpyderX04_RiskGuardianAgent(model_name, temperature)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderX04_RiskGuardianAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_risk_guardian_agent()
    return _module_instance
