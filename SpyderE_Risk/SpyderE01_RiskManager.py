#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE01_RiskManager.py
Group: E (Risk Management)
Purpose: Enhanced comprehensive risk management with real-time monitoring

Description:
    This module provides institutional-grade risk management capabilities including
    pre-trade risk checks, real-time position monitoring, portfolio risk assessment,
    and automated risk mitigation. It implements sophisticated risk models, stress
    testing, and provides comprehensive risk reporting for professional trading
    operations.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 18:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple, NamedTuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# Statistical imports
try:
    from scipy import stats
    from scipy.stats import norm
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: scipy not found. Advanced risk calculations will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OrderAction, OptionType
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# Conditional imports
try:
    from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
    HAS_PERFORMANCE_METRICS = True
except ImportError:
    HAS_PERFORMANCE_METRICS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk Limits Configuration
DEFAULT_MAX_DAILY_LOSS = 5000.0           # USD
DEFAULT_MAX_PORTFOLIO_DELTA = 1000.0      # Delta exposure
DEFAULT_MAX_PORTFOLIO_GAMMA = 100.0       # Gamma exposure  
DEFAULT_MAX_PORTFOLIO_VEGA = 500.0        # Vega exposure
DEFAULT_MAX_SINGLE_POSITION = 50000.0     # USD per position
DEFAULT_MAX_CONCENTRATION = 0.25           # 25% max in single position

# Greeks Limits
DEFAULT_DELTA_LIMIT = 1000
DEFAULT_GAMMA_LIMIT = 100
DEFAULT_THETA_LIMIT = 500
DEFAULT_VEGA_LIMIT = 1000
DEFAULT_RHO_LIMIT = 500

# Risk Monitoring
RISK_CHECK_INTERVAL = 1.0    # seconds
STRESS_TEST_INTERVAL = 300   # 5 minutes
VaR_CALCULATION_INTERVAL = 60 # 1 minute

# Volatility Parameters
DEFAULT_VOLATILITY_WINDOW = 30  # days
VIX_SPIKE_THRESHOLD = 30        # VIX level
VOLATILITY_SHOCK_THRESHOLD = 0.05  # 5% daily move

# Circuit Breaker Thresholds
CIRCUIT_BREAKER_LOSS_PCT = 0.05    # 5% portfolio loss
CIRCUIT_BREAKER_VIX_LEVEL = 40     # VIX level
CIRCUIT_BREAKER_VOLUME_SPIKE = 2.0  # 2x normal volume

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskProfile(Enum):
    """Risk profile enumeration"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    SPECULATIVE = "speculative"

class RiskLevel(Enum):
    """Risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskType(Enum):
    """Risk type enumeration"""
    MARKET_RISK = "market_risk"
    CREDIT_RISK = "credit_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    OPERATIONAL_RISK = "operational_risk"
    MODEL_RISK = "model_risk"
    CONCENTRATION_RISK = "concentration_risk"

class RiskAction(Enum):
    """Risk action enumeration"""
    APPROVE = "approve"
    REJECT = "reject"
    WARN = "warn"
    REDUCE_SIZE = "reduce_size"
    HEDGE = "hedge"
    LIQUIDATE = "liquidate"

class CircuitBreakerState(Enum):
    """Circuit breaker state"""
    NORMAL = "normal"
    WARNING = "warning"
    TRIGGERED = "triggered"
    HALTED = "halted"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskLimits:
    """Risk limits configuration"""
    max_daily_loss: float = DEFAULT_MAX_DAILY_LOSS
    max_portfolio_delta: float = DEFAULT_MAX_PORTFOLIO_DELTA
    max_portfolio_gamma: float = DEFAULT_MAX_PORTFOLIO_GAMMA
    max_portfolio_vega: float = DEFAULT_MAX_PORTFOLIO_VEGA
    max_single_position: float = DEFAULT_MAX_SINGLE_POSITION
    max_concentration: float = DEFAULT_MAX_CONCENTRATION
    max_leverage: float = 2.0
    max_correlation_exposure: float = 0.5
    
    # Greeks limits
    delta_limit: float = DEFAULT_DELTA_LIMIT
    gamma_limit: float = DEFAULT_GAMMA_LIMIT
    theta_limit: float = DEFAULT_THETA_LIMIT
    vega_limit: float = DEFAULT_VEGA_LIMIT
    rho_limit: float = DEFAULT_RHO_LIMIT

@dataclass
class RiskCheckResult:
    """Risk check result"""
    approved: bool
    action: RiskAction
    risk_level: RiskLevel
    risk_score: float
    reason: str
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioRisk:
    """Portfolio risk metrics"""
    total_exposure: float = 0.0
    delta_exposure: float = 0.0
    gamma_exposure: float = 0.0
    vega_exposure: float = 0.0
    theta_exposure: float = 0.0
    var_1d: float = 0.0          # 1-day Value at Risk
    var_10d: float = 0.0         # 10-day Value at Risk
    expected_shortfall: float = 0.0
    concentration_risk: float = 0.0
    correlation_risk: float = 0.0
    liquidity_risk: float = 0.0
    stress_test_loss: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    beta: float = 1.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class StressTestScenario:
    """Stress test scenario"""
    name: str
    description: str
    market_move: float           # % move in underlying
    volatility_change: float     # % change in volatility
    time_decay_days: int = 0     # Days of time decay
    expected_loss: float = 0.0   # Expected loss from scenario

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    enabled: bool = True
    daily_loss_threshold: float = CIRCUIT_BREAKER_LOSS_PCT
    vix_threshold: float = CIRCUIT_BREAKER_VIX_LEVEL
    volume_spike_threshold: float = CIRCUIT_BREAKER_VOLUME_SPIKE
    position_limit_breach_count: int = 3
    consecutive_losses_limit: int = 5

@dataclass
class RiskAlert:
    """Risk alert data structure"""
    alert_id: str
    alert_type: str
    severity: RiskLevel
    message: str
    affected_positions: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RiskManager:
    """
    Enhanced Risk Management System.
    
    This class provides comprehensive risk management capabilities including
    pre-trade risk checks, real-time portfolio monitoring, stress testing,
    and automated risk mitigation for professional trading operations.
    
    Key Features:
    - Real-time risk monitoring and alerting
    - Pre-trade risk validation with dynamic limits
    - Portfolio VaR and stress testing
    - Greeks exposure monitoring and limits
    - Circuit breaker protection mechanisms
    - Concentration and correlation risk analysis
    - Automated risk mitigation recommendations
    
    Attributes:
        logger: Module logger instance
        config: Risk manager configuration
        risk_limits: Current risk limit settings
        portfolio_risk: Current portfolio risk metrics
        circuit_breaker_state: Circuit breaker status
        
    Example:
        >>> risk_manager = get_risk_manager()
        >>> result = risk_manager.check_pre_trade_risk(signal)
        >>> if result.approved:
        >>>     # Proceed with trade
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Risk Manager.
        
        Args:
            config: Risk manager configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        
        # Risk configuration
        self.risk_limits = self._initialize_risk_limits()
        self.risk_profile = RiskProfile(self.config.get('risk_profile', 'moderate'))
        
        # Portfolio risk tracking
        self.portfolio_risk = PortfolioRisk()
        self.risk_history: deque = deque(maxlen=10000)
        self._risk_lock = RLock()
        
        # Circuit breaker system
        self.circuit_breaker_config = CircuitBreakerConfig()
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        self._circuit_breaker_lock = RLock()
        
        # Risk alerts
        self.active_alerts: Dict[str, RiskAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self._alert_lock = RLock()
        
        # Performance metrics
        if HAS_PERFORMANCE_METRICS:
            self.performance_metrics = PerformanceMetrics()
        else:
            self.performance_metrics = None
        
        # Threading infrastructure
        self.worker_threads: Dict[str, threading.Thread] = {}
        self._shutdown_event = ThreadEvent()
        
        # Market data cache
        self.market_data: Dict[str, Any] = {}
        self.vix_level: float = 20.0
        self.market_volatility: float = 0.15
        self._market_data_lock = RLock()
        
        # Stress test scenarios
        self.stress_scenarios = self._initialize_stress_scenarios()
        
        # Event manager integration
        try:
            from SpyderA_Core.SpyderA05_EventManager import get_event_manager
            self.event_manager = get_event_manager()
            self.has_event_manager = True
        except Exception as e:
            self.logger.warning(f"Event manager not available: {e}")
            self.event_manager = None
            self.has_event_manager = False
        
        # Monitoring state
        self.monitoring_active = False
        self.last_risk_check = datetime.now()
        self.last_stress_test = datetime.now()
        self.last_var_calculation = datetime.now()
        
        # Statistics
        self.risk_checks_performed = 0
        self.trades_approved = 0
        self.trades_rejected = 0
        self.alerts_generated = 0
        
        self.logger.info(f"RiskManager initialized with {self.risk_profile.value} profile")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the risk manager.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing RiskManager...")
            
            # Validate risk limits
            if not self._validate_risk_limits():
                self.logger.error("Risk limits validation failed")
                return False
            
            # Initialize market data subscriptions
            self._initialize_market_data()
            
            # Perform initial risk assessment
            self._perform_initial_risk_assessment()
            
            self.logger.info("RiskManager initialization completed")
            return True
            
        except Exception as e:
            self.logger.error(f"RiskManager initialization failed: {e}")
            self.error_handler.handle_risk_error(e, "RiskManager", "initialize")
            return False
    
    def start_monitoring(self) -> bool:
        """
        Start risk monitoring.
        
        Returns:
            bool: True if monitoring started successfully
        """
        try:
            self.logger.info("Starting risk monitoring...")
            
            # Start worker threads
            self._start_monitoring_threads()
            
            self.monitoring_active = True
            
            # Emit monitoring started event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.RISK_MONITORING_STARTED,
                    {
                        'timestamp': datetime.now(),
                        'risk_profile': self.risk_profile.value,
                        'circuit_breaker_enabled': self.circuit_breaker_config.enabled
                    }
                )
            
            self.logger.info("Risk monitoring started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Risk monitoring start failed: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """
        Stop risk monitoring.
        
        Returns:
            bool: True if monitoring stopped successfully
        """
        try:
            self.logger.info("Stopping risk monitoring...")
            
            # Signal shutdown
            self._shutdown_event.set()
            self.monitoring_active = False
            
            # Stop worker threads
            self._stop_monitoring_threads()
            
            self.logger.info("Risk monitoring stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Risk monitoring stop failed: {e}")
            return False
    
    # ==========================================================================
    # PRE-TRADE RISK CHECKS
    # ==========================================================================
    
    def check_pre_trade_risk(self, signal) -> RiskCheckResult:
        """
        Perform comprehensive pre-trade risk check.
        
        Args:
            signal: Trading signal to validate
            
        Returns:
            RiskCheckResult with approval status and recommendations
        """
        try:
            self.risk_checks_performed += 1
            check_start = time.time()
            
            # Initialize result
            result = RiskCheckResult(
                approved=False,
                action=RiskAction.REJECT,
                risk_level=RiskLevel.HIGH,
                risk_score=100.0,
                reason="Risk check failed"
            )
            
            # Check if risk monitoring is active
            if not self.monitoring_active:
                result.reason = "Risk monitoring not active"
                return result
            
            # Check circuit breaker state
            if self.circuit_breaker_state == CircuitBreakerState.HALTED:
                result.reason = "Circuit breaker halted - no new trades allowed"
                result.action = RiskAction.REJECT
                return result
            
            # Perform individual risk checks
            checks = [
                self._check_position_size_risk(signal),
                self._check_portfolio_concentration_risk(signal),
                self._check_greeks_exposure_risk(signal),
                self._check_correlation_risk(signal),
                self._check_liquidity_risk(signal),
                self._check_market_conditions_risk(signal),
                self._check_daily_loss_limit(signal)
            ]
            
            # Analyze check results
            approved_checks = sum(1 for check in checks if check.approved)
            total_checks = len(checks)
            approval_rate = approved_checks / total_checks
            
            # Calculate composite risk score
            risk_scores = [check.risk_score for check in checks]
            composite_risk_score = np.mean(risk_scores) if risk_scores else 100.0
            
            # Determine overall approval
            if approval_rate >= 0.8 and composite_risk_score <= 70.0:
                result.approved = True
                result.action = RiskAction.APPROVE
                result.risk_level = self._determine_risk_level(composite_risk_score)
                result.reason = "All risk checks passed"
                self.trades_approved += 1
            elif approval_rate >= 0.6 and composite_risk_score <= 85.0:
                result.approved = True
                result.action = RiskAction.WARN
                result.risk_level = RiskLevel.MEDIUM
                result.reason = "Trade approved with warnings"
                result.recommendations.append("Monitor position closely")
                self.trades_approved += 1
            else:
                result.approved = False
                result.action = RiskAction.REJECT
                result.risk_level = RiskLevel.HIGH
                result.reason = "Risk checks failed - trade rejected"
                self.trades_rejected += 1
            
            # Compile failed checks reasons
            failed_checks = [check for check in checks if not check.approved]
            if failed_checks:
                failed_reasons = [check.reason for check in failed_checks]
                result.reason += f" - Failed: {', '.join(failed_reasons)}"
            
            # Add recommendations from all checks
            for check in checks:
                result.recommendations.extend(check.recommendations)
            
            # Set final metrics
            result.risk_score = composite_risk_score
            result.metrics = {
                'approval_rate': approval_rate,
                'checks_passed': approved_checks,
                'total_checks': total_checks,
                'check_time_ms': (time.time() - check_start) * 1000
            }
            
            # Log result
            self.logger.info(f"Pre-trade risk check: {result.action.value} "
                           f"(Score: {result.risk_score:.1f}, Checks: {approved_checks}/{total_checks})")
            
            # Emit risk check event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.RISK_CHECK_COMPLETED,
                    {
                        'signal_id': getattr(signal, 'signal_id', 'unknown'),
                        'approved': result.approved,
                        'action': result.action.value,
                        'risk_score': result.risk_score,
                        'risk_level': result.risk_level.value,
                        'timestamp': datetime.now()
                    }
                )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Pre-trade risk check failed: {e}")
            self.error_handler.handle_risk_error(e, "RiskManager", "check_pre_trade_risk")
            
            return RiskCheckResult(
                approved=False,
                action=RiskAction.REJECT,
                risk_level=RiskLevel.CRITICAL,
                risk_score=100.0,
                reason=f"Risk check error: {str(e)}"
            )
    
    # ==========================================================================
    # INDIVIDUAL RISK CHECKS
    # ==========================================================================
    
    def _check_position_size_risk(self, signal) -> RiskCheckResult:
        """Check position size risk."""
        try:
            # Estimate position value
            estimated_value = self._estimate_position_value(signal)
            max_position = self.risk_limits.max_single_position
            
            if estimated_value <= max_position:
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.APPROVE,
                    risk_level=RiskLevel.LOW,
                    risk_score=min(50.0, (estimated_value / max_position) * 50),
                    reason="Position size within limits"
                )
            else:
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.HIGH,
                    risk_score=min(100.0, (estimated_value / max_position) * 100),
                    reason=f"Position size ${estimated_value:,.0f} exceeds limit ${max_position:,.0f}",
                    recommendations=[f"Reduce position size to ${max_position:,.0f} or less"]
                )
                
        except Exception as e:
            self.logger.error(f"Position size risk check failed: {e}")
            return RiskCheckResult(
                approved=False,
                action=RiskAction.REJECT,
                risk_level=RiskLevel.HIGH,
                risk_score=100.0,
                reason="Position size check error"
            )
    
    def _check_portfolio_concentration_risk(self, signal) -> RiskCheckResult:
        """Check portfolio concentration risk."""
        try:
            # This would integrate with position tracker to get current portfolio
            # For now, simulate concentration check
            symbol = getattr(signal, 'symbol', 'UNKNOWN')
            estimated_value = self._estimate_position_value(signal)
            
            # Simulate current portfolio value
            current_portfolio_value = 100000.0  # Would get from position tracker
            
            concentration = estimated_value / current_portfolio_value if current_portfolio_value > 0 else 0
            max_concentration = self.risk_limits.max_concentration
            
            if concentration <= max_concentration:
                risk_score = (concentration / max_concentration) * 50
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.APPROVE,
                    risk_level=RiskLevel.LOW if concentration < 0.15 else RiskLevel.MEDIUM,
                    risk_score=risk_score,
                    reason="Concentration within limits"
                )
            else:
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.HIGH,
                    risk_score=min(100.0, (concentration / max_concentration) * 100),
                    reason=f"Concentration {concentration:.1%} exceeds limit {max_concentration:.1%}",
                    recommendations=["Diversify holdings", "Reduce position size"]
                )
                
        except Exception as e:
            self.logger.error(f"Concentration risk check failed: {e}")
            return RiskCheckResult(
                approved=False,
                action=RiskAction.REJECT,
                risk_level=RiskLevel.HIGH,
                risk_score=100.0,
                reason="Concentration check error"
            )
    
    def _check_greeks_exposure_risk(self, signal) -> RiskCheckResult:
        """Check Greeks exposure risk."""
        try:
            # Estimate Greeks impact of new position
            estimated_delta = self._estimate_delta_impact(signal)
            estimated_gamma = self._estimate_gamma_impact(signal)
            estimated_vega = self._estimate_vega_impact(signal)
            
            # Get current portfolio Greeks (would integrate with position tracker)
            current_delta = self.portfolio_risk.delta_exposure
            current_gamma = self.portfolio_risk.gamma_exposure
            current_vega = self.portfolio_risk.vega_exposure
            
            # Calculate new exposures
            new_delta = current_delta + estimated_delta
            new_gamma = current_gamma + estimated_gamma
            new_vega = current_vega + estimated_vega
            
            # Check limits
            violations = []
            risk_score = 0.0
            
            if abs(new_delta) > self.risk_limits.delta_limit:
                violations.append(f"Delta: {new_delta:.0f} > {self.risk_limits.delta_limit:.0f}")
                risk_score = max(risk_score, abs(new_delta) / self.risk_limits.delta_limit * 100)
            
            if abs(new_gamma) > self.risk_limits.gamma_limit:
                violations.append(f"Gamma: {new_gamma:.0f} > {self.risk_limits.gamma_limit:.0f}")
                risk_score = max(risk_score, abs(new_gamma) / self.risk_limits.gamma_limit * 100)
            
            if abs(new_vega) > self.risk_limits.vega_limit:
                violations.append(f"Vega: {new_vega:.0f} > {self.risk_limits.vega_limit:.0f}")
                risk_score = max(risk_score, abs(new_vega) / self.risk_limits.vega_limit * 100)
            
            if violations:
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.HIGH,
                    risk_score=min(100.0, risk_score),
                    reason=f"Greeks limits exceeded: {', '.join(violations)}",
                    recommendations=["Hedge existing positions", "Reduce trade size"]
                )
            else:
                # Calculate risk score based on utilization
                delta_util = abs(new_delta) / self.risk_limits.delta_limit
                gamma_util = abs(new_gamma) / self.risk_limits.gamma_limit
                vega_util = abs(new_vega) / self.risk_limits.vega_limit
                
                max_utilization = max(delta_util, gamma_util, vega_util)
                risk_score = max_utilization * 70  # Max 70 if at limit
                
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.APPROVE,
                    risk_level=self._determine_risk_level(risk_score),
                    risk_score=risk_score,
                    reason="Greeks exposure within limits"
                )
                
        except Exception as e:
            self.logger.error(f"Greeks exposure risk check failed: {e}")
            return RiskCheckResult(
                approved=False,
                action=RiskAction.REJECT,
                risk_level=RiskLevel.HIGH,
                risk_score=100.0,
                reason="Greeks exposure check error"
            )
    
    def _check_correlation_risk(self, signal) -> RiskCheckResult:
        """Check correlation risk."""
        try:
            # Simplified correlation check
            symbol = getattr(signal, 'symbol', 'UNKNOWN')
            
            # For SPY options, correlation risk is lower
            if 'SPY' in symbol.upper():
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.APPROVE,
                    risk_level=RiskLevel.LOW,
                    risk_score=20.0,
                    reason="SPY correlation risk acceptable"
                )
            else:
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.APPROVE,
                    risk_level=RiskLevel.MEDIUM,
                    risk_score=40.0,
                    reason="Correlation risk within acceptable range"
                )
                
        except Exception as e:
            self.logger.error(f"Correlation risk check failed: {e}")
            return RiskCheckResult(
                approved=True,
                action=RiskAction.APPROVE,
                risk_level=RiskLevel.MEDIUM,
                risk_score=50.0,
                reason="Correlation check completed with warnings"
            )
    
    def _check_liquidity_risk(self, signal) -> RiskCheckResult:
        """Check liquidity risk."""
        try:
            symbol = getattr(signal, 'symbol', 'UNKNOWN')
            quantity = getattr(signal, 'quantity', 0)
            
            # SPY options typically have good liquidity
            if 'SPY' in symbol.upper():
                if quantity <= 100:  # Standard size
                    return RiskCheckResult(
                        approved=True,
                        action=RiskAction.APPROVE,
                        risk_level=RiskLevel.LOW,
                        risk_score=10.0,
                        reason="SPY liquidity excellent"
                    )
                else:
                    return RiskCheckResult(
                        approved=True,
                        action=RiskAction.WARN,
                        risk_level=RiskLevel.MEDIUM,
                        risk_score=30.0,
                        reason="Large SPY position - monitor execution",
                        recommendations=["Consider splitting large orders"]
                    )
            else:
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.WARN,
                    risk_level=RiskLevel.MEDIUM,
                    risk_score=50.0,
                    reason="Non-SPY symbol - verify liquidity",
                    recommendations=["Check bid-ask spreads", "Verify daily volume"]
                )
                
        except Exception as e:
            self.logger.error(f"Liquidity risk check failed: {e}")
            return RiskCheckResult(
                approved=True,
                action=RiskAction.WARN,
                risk_level=RiskLevel.MEDIUM,
                risk_score=60.0,
                reason="Liquidity check completed with warnings"
            )
    
    def _check_market_conditions_risk(self, signal) -> RiskCheckResult:
        """Check market conditions risk."""
        try:
            # Check VIX level
            if self.vix_level > VIX_SPIKE_THRESHOLD:
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.HIGH,
                    risk_score=90.0,
                    reason=f"High volatility environment (VIX: {self.vix_level:.1f})",
                    recommendations=["Wait for volatility to decrease", "Consider defensive strategies"]
                )
            
            # Check market hours
            if not self._is_market_hours():
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.MEDIUM,
                    risk_score=70.0,
                    reason="Outside market hours",
                    recommendations=["Wait for market open", "Use extended hours if necessary"]
                )
            
            return RiskCheckResult(
                approved=True,
                action=RiskAction.APPROVE,
                risk_level=RiskLevel.LOW,
                risk_score=20.0,
                reason="Market conditions favorable"
            )
            
        except Exception as e:
            self.logger.error(f"Market conditions risk check failed: {e}")
            return RiskCheckResult(
                approved=True,
                action=RiskAction.WARN,
                risk_level=RiskLevel.MEDIUM,
                risk_score=50.0,
                reason="Market conditions check completed with warnings"
            )
    
    def _check_daily_loss_limit(self, signal) -> RiskCheckResult:
        """Check daily loss limit."""
        try:
            # Get current daily P&L (would integrate with performance tracker)
            current_daily_pnl = self.portfolio_risk.var_1d  # Simplified
            
            if current_daily_pnl < -self.risk_limits.max_daily_loss:
                return RiskCheckResult(
                    approved=False,
                    action=RiskAction.REJECT,
                    risk_level=RiskLevel.CRITICAL,
                    risk_score=100.0,
                    reason=f"Daily loss limit exceeded: ${current_daily_pnl:,.0f}",
                    recommendations=["Stop trading for today", "Review risk management"]
                )
            
            # Check if close to limit
            loss_utilization = abs(current_daily_pnl) / self.risk_limits.max_daily_loss
            if loss_utilization > 0.8:
                return RiskCheckResult(
                    approved=True,
                    action=RiskAction.WARN,
                    risk_level=RiskLevel.HIGH,
                    risk_score=80.0,
                    reason=f"Approaching daily loss limit: {loss_utilization:.1%}",
                    recommendations=["Consider reducing position sizes", "Avoid high-risk trades"]
                )
            
            return RiskCheckResult(
                approved=True,
                action=RiskAction.APPROVE,
                risk_level=RiskLevel.LOW,
                risk_score=loss_utilization * 50,
                reason="Daily loss within acceptable range"
            )
            
        except Exception as e:
            self.logger.error(f"Daily loss limit check failed: {e}")
            return RiskCheckResult(
                approved=True,
                action=RiskAction.APPROVE,
                risk_level=RiskLevel.MEDIUM,
                risk_score=50.0,
                reason="Daily loss check completed"
            )
    
    # ==========================================================================
    # PORTFOLIO RISK MONITORING
    # ==========================================================================
    
    def update_portfolio_risk(self, portfolio_data: Dict[str, Any]) -> bool:
        """
        Update portfolio risk metrics.
        
        Args:
            portfolio_data: Current portfolio data
            
        Returns:
            bool: True if update successful
        """
        try:
            with self._risk_lock:
                # Update portfolio exposure
                self.portfolio_risk.total_exposure = portfolio_data.get('total_market_value', 0.0)
                self.portfolio_risk.delta_exposure = portfolio_data.get('total_delta', 0.0)
                self.portfolio_risk.gamma_exposure = portfolio_data.get('total_gamma', 0.0)
                self.portfolio_risk.vega_exposure = portfolio_data.get('total_vega', 0.0)
                self.portfolio_risk.theta_exposure = portfolio_data.get('total_theta', 0.0)
                
                # Calculate concentration risk
                max_position = portfolio_data.get('max_position_size', 0.0)
                total_value = self.portfolio_risk.total_exposure
                if total_value > 0:
                    self.portfolio_risk.concentration_risk = max_position / total_value
                
                # Update timestamp
                self.portfolio_risk.last_update = datetime.now()
                
                # Add to history
                self.risk_history.append(copy.deepcopy(self.portfolio_risk))
                
                # Check for risk limit violations
                self._check_portfolio_risk_limits()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Portfolio risk update failed: {e}")
            return False
    
    def check_greek_limits(self, greeks: Dict[str, float]) -> bool:
        """
        Check if portfolio Greeks are within limits.
        
        Args:
            greeks: Portfolio Greeks dictionary
            
        Returns:
            bool: True if within limits
        """
        try:
            violations = []
            
            delta = greeks.get('delta', 0.0)
            gamma = greeks.get('gamma', 0.0)
            vega = greeks.get('vega', 0.0)
            theta = greeks.get('theta', 0.0)
            
            if abs(delta) > self.risk_limits.delta_limit:
                violations.append(f"Delta limit exceeded: {delta:.0f}")
            
            if abs(gamma) > self.risk_limits.gamma_limit:
                violations.append(f"Gamma limit exceeded: {gamma:.0f}")
            
            if abs(vega) > self.risk_limits.vega_limit:
                violations.append(f"Vega limit exceeded: {vega:.0f}")
            
            if violations:
                self._generate_risk_alert(
                    "GREEKS_LIMIT_VIOLATION",
                    RiskLevel.HIGH,
                    f"Greeks limits violated: {', '.join(violations)}",
                    recommended_actions=["Hedge positions", "Reduce exposure"]
                )
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Greeks limit check failed: {e}")
            return False
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _initialize_risk_limits(self) -> RiskLimits:
        """Initialize risk limits based on configuration."""
        try:
            limits = RiskLimits()
            
            # Apply configuration overrides
            if 'risk_limits' in self.config:
                limit_config = self.config['risk_limits']
                for key, value in limit_config.items():
                    if hasattr(limits, key):
                        setattr(limits, key, value)
            
            # Apply risk profile adjustments
            if self.config.get('risk_profile') == 'conservative':
                limits.max_daily_loss *= 0.5
                limits.max_single_position *= 0.7
                limits.max_portfolio_delta *= 0.6
            elif self.config.get('risk_profile') == 'aggressive':
                limits.max_daily_loss *= 1.5
                limits.max_single_position *= 1.3
                limits.max_portfolio_delta *= 1.4
            
            return limits
            
        except Exception as e:
            self.logger.error(f"Risk limits initialization failed: {e}")
            return RiskLimits()
    
    def _initialize_stress_scenarios(self) -> List[StressTestScenario]:
        """Initialize stress test scenarios."""
        return [
            StressTestScenario(
                name="Market Crash",
                description="5% market decline with volatility spike",
                market_move=-0.05,
                volatility_change=0.5
            ),
            StressTestScenario(
                name="Flash Crash",
                description="10% market decline in single day",
                market_move=-0.10,
                volatility_change=1.0
            ),
            StressTestScenario(
                name="Volatility Spike",
                description="50% increase in volatility",
                market_move=0.0,
                volatility_change=0.5
            ),
            StressTestScenario(
                name="Time Decay",
                description="5 days of time decay",
                market_move=0.0,
                volatility_change=0.0,
                time_decay_days=5
            )
        ]
    
    def _estimate_position_value(self, signal) -> float:
        """Estimate position value from signal."""
        try:
            quantity = getattr(signal, 'quantity', 0)
            symbol = getattr(signal, 'symbol', '')
            
            # Simplified estimation
            if 'SPY' in symbol.upper():
                if any(c in symbol for c in ['C', 'P']):  # Option
                    return quantity * 500.0  # Assume $5 option price
                else:  # Stock
                    return quantity * 450.0  # SPY price
            else:
                return quantity * 100.0  # Default estimation
                
        except Exception as e:
            self.logger.error(f"Position value estimation failed: {e}")
            return 0.0
    
    def _estimate_delta_impact(self, signal) -> float:
        """Estimate delta impact of signal."""
        try:
            quantity = getattr(signal, 'quantity', 0)
            symbol = getattr(signal, 'symbol', '')
            
            # Simplified delta estimation
            if 'SPY' in symbol.upper():
                if 'C' in symbol:  # Call option
                    return quantity * 50  # Assume 0.5 delta
                elif 'P' in symbol:  # Put option
                    return quantity * -50  # Assume -0.5 delta
                else:  # Stock
                    return quantity * 100  # Stock delta = 100
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Delta impact estimation failed: {e}")
            return 0.0
    
    def _estimate_gamma_impact(self, signal) -> float:
        """Estimate gamma impact of signal."""
        try:
            quantity = getattr(signal, 'quantity', 0)
            symbol = getattr(signal, 'symbol', '')
            
            # Simplified gamma estimation for options
            if any(c in symbol for c in ['C', 'P']):
                return quantity * 5  # Assume 0.05 gamma
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Gamma impact estimation failed: {e}")
            return 0.0
    
    def _estimate_vega_impact(self, signal) -> float:
        """Estimate vega impact of signal."""
        try:
            quantity = getattr(signal, 'quantity', 0)
            symbol = getattr(signal, 'symbol', '')
            
            # Simplified vega estimation for options
            if any(c in symbol for c in ['C', 'P']):
                return quantity * 20  # Assume 0.2 vega
            
            return 0.0
            
        except Exception as e:
            self.logger.error(f"Vega impact estimation failed: {e}")
            return 0.0
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from risk score."""
        if risk_score <= 30:
            return RiskLevel.LOW
        elif risk_score <= 60:
            return RiskLevel.MEDIUM
        elif risk_score <= 85:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def _is_market_hours(self) -> bool:
        """Check if currently in market hours."""
        try:
            # Simplified market hours check
            from datetime import time
            import pytz
            
            et = pytz.timezone('US/Eastern')
            now_et = datetime.now(et)
            
            # Check if weekday
            if now_et.weekday() >= 5:  # Weekend
                return False
            
            # Check time (9:30 AM - 4:00 PM ET)
            market_open = time(9, 30)
            market_close = time(16, 0)
            current_time = now_et.time()
            
            return market_open <= current_time <= market_close
            
        except Exception as e:
            self.logger.warning(f"Market hours check failed: {e}")
            return True  # Default to open
    
    def _validate_risk_limits(self) -> bool:
        """Validate risk limits configuration."""
        try:
            # Check that limits are reasonable
    def _validate_risk_limits(self) -> bool:
        """Validate risk limits configuration."""
        try:
            # Check that limits are reasonable
            if self.risk_limits.max_daily_loss <= 0:
                self.logger.error("Invalid max_daily_loss limit")
                return False
            
            if self.risk_limits.max_single_position <= 0:
                self.logger.error("Invalid max_single_position limit")
                return False
            
            if not (0 < self.risk_limits.max_concentration <= 1):
                self.logger.error("Invalid max_concentration limit")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Risk limits validation failed: {e}")
            return False
    
    def _initialize_market_data(self):
        """Initialize market data subscriptions."""
        try:
            # This would integrate with market data feed
            # For now, set default values
            self.vix_level = 20.0
            self.market_volatility = 0.15
            
        except Exception as e:
            self.logger.error(f"Market data initialization failed: {e}")
    
    def _perform_initial_risk_assessment(self):
        """Perform initial risk assessment."""
        try:
            # Initial portfolio risk calculation
            self.portfolio_risk = PortfolioRisk()
            
            # Check circuit breaker status
            self.circuit_breaker_state = CircuitBreakerState.NORMAL
            
            self.logger.info("Initial risk assessment completed")
            
        except Exception as e:
            self.logger.error(f"Initial risk assessment failed: {e}")
    
    def _start_monitoring_threads(self):
        """Start risk monitoring threads."""
        try:
            # Risk monitoring thread
            risk_thread = threading.Thread(
                target=self._risk_monitoring_worker,
                name="RiskMonitor",
                daemon=True
            )
            risk_thread.start()
            self.worker_threads['risk_monitor'] = risk_thread
            
            # Circuit breaker monitoring thread
            circuit_thread = threading.Thread(
                target=self._circuit_breaker_worker,
                name="CircuitBreakerMonitor",
                daemon=True
            )
            circuit_thread.start()
            self.worker_threads['circuit_breaker'] = circuit_thread
            
            # VaR calculation thread
            var_thread = threading.Thread(
                target=self._var_calculation_worker,
                name="VaRCalculator",
                daemon=True
            )
            var_thread.start()
            self.worker_threads['var_calculator'] = var_thread
            
            self.logger.info("Risk monitoring threads started")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring threads: {e}")
    
    def _stop_monitoring_threads(self):
        """Stop monitoring threads."""
        try:
            # Wait for threads to finish
            for name, thread in self.worker_threads.items():
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    if thread.is_alive():
                        self.logger.warning(f"Thread {name} did not stop gracefully")
            
            self.worker_threads.clear()
            self.logger.info("Risk monitoring threads stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring threads: {e}")
    
    def _risk_monitoring_worker(self):
        """Risk monitoring worker thread."""
        while not self._shutdown_event.is_set():
            try:
                # Check portfolio risk limits
                self._check_portfolio_risk_limits()
                
                # Update market data
                self._update_market_data()
                
                # Check for risk alerts
                self._process_risk_alerts()
                
                self.last_risk_check = datetime.now()
                self._shutdown_event.wait(RISK_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Risk monitoring worker error: {e}")
                self._shutdown_event.wait(5.0)
    
    def _circuit_breaker_worker(self):
        """Circuit breaker monitoring worker thread."""
        while not self._shutdown_event.is_set():
            try:
                # Check circuit breaker conditions
                self._check_circuit_breaker_conditions()
                
                self._shutdown_event.wait(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Circuit breaker worker error: {e}")
                self._shutdown_event.wait(10.0)
    
    def _var_calculation_worker(self):
        """VaR calculation worker thread."""
        while not self._shutdown_event.is_set():
            try:
                # Calculate portfolio VaR
                self._calculate_portfolio_var()
                
                # Perform stress tests
                self._perform_stress_tests()
                
                self.last_var_calculation = datetime.now()
                self._shutdown_event.wait(VaR_CALCULATION_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"VaR calculation worker error: {e}")
                self._shutdown_event.wait(60.0)
    
    def _check_portfolio_risk_limits(self):
        """Check portfolio-level risk limits."""
        try:
            with self._risk_lock:
                violations = []
                
                # Check delta exposure
                if abs(self.portfolio_risk.delta_exposure) > self.risk_limits.max_portfolio_delta:
                    violations.append(f"Portfolio delta: {self.portfolio_risk.delta_exposure:.0f}")
                
                # Check concentration
                if self.portfolio_risk.concentration_risk > self.risk_limits.max_concentration:
                    violations.append(f"Concentration: {self.portfolio_risk.concentration_risk:.1%}")
                
                # Check VaR
                if abs(self.portfolio_risk.var_1d) > self.risk_limits.max_daily_loss:
                    violations.append(f"Daily VaR: ${self.portfolio_risk.var_1d:,.0f}")
                
                if violations:
                    self._generate_risk_alert(
                        "PORTFOLIO_RISK_LIMIT",
                        RiskLevel.HIGH,
                        f"Portfolio risk limits violated: {', '.join(violations)}",
                        recommended_actions=["Reduce positions", "Implement hedges"]
                    )
                    
        except Exception as e:
            self.logger.error(f"Portfolio risk limit check failed: {e}")
    
    def _check_circuit_breaker_conditions(self):
        """Check circuit breaker trigger conditions."""
        try:
            if not self.circuit_breaker_config.enabled:
                return
            
            with self._circuit_breaker_lock:
                should_trigger = False
                trigger_reason = ""
                
                # Check daily loss threshold
                daily_loss_pct = abs(self.portfolio_risk.var_1d) / max(self.portfolio_risk.total_exposure, 1)
                if daily_loss_pct > self.circuit_breaker_config.daily_loss_threshold:
                    should_trigger = True
                    trigger_reason = f"Daily loss {daily_loss_pct:.1%} exceeds threshold"
                
                # Check VIX level
                if self.vix_level > self.circuit_breaker_config.vix_threshold:
                    should_trigger = True
                    trigger_reason = f"VIX {self.vix_level:.1f} exceeds threshold"
                
                # Trigger circuit breaker if conditions met
                if should_trigger and self.circuit_breaker_state == CircuitBreakerState.NORMAL:
                    self._trigger_circuit_breaker(trigger_reason)
                elif not should_trigger and self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                    self._reset_circuit_breaker("Conditions normalized")
                    
        except Exception as e:
            self.logger.error(f"Circuit breaker check failed: {e}")
    
    def _trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker."""
        try:
            self.circuit_breaker_state = CircuitBreakerState.TRIGGERED
            
            self.logger.critical(f"CIRCUIT BREAKER TRIGGERED: {reason}")
            
            # Generate critical alert
            self._generate_risk_alert(
                "CIRCUIT_BREAKER_TRIGGERED",
                RiskLevel.CRITICAL,
                f"Circuit breaker triggered: {reason}",
                recommended_actions=[
                    "Stop all new trading",
                    "Review positions",
                    "Consider emergency liquidation"
                ]
            )
            
            # Emit circuit breaker event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.CIRCUIT_BREAKER_TRIGGERED,
                    {
                        'reason': reason,
                        'timestamp': datetime.now(),
                        'portfolio_value': self.portfolio_risk.total_exposure,
                        'daily_pnl': self.portfolio_risk.var_1d
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Circuit breaker trigger failed: {e}")
    
    def _reset_circuit_breaker(self, reason: str):
        """Reset circuit breaker."""
        try:
            self.circuit_breaker_state = CircuitBreakerState.NORMAL
            
            self.logger.info(f"Circuit breaker reset: {reason}")
            
            # Emit reset event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.CIRCUIT_BREAKER_RESET,
                    {
                        'reason': reason,
                        'timestamp': datetime.now()
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Circuit breaker reset failed: {e}")
    
    def _calculate_portfolio_var(self):
        """Calculate portfolio Value at Risk."""
        try:
            if not HAS_SCIPY:
                # Simplified VaR calculation
                portfolio_value = self.portfolio_risk.total_exposure
                daily_volatility = self.market_volatility / math.sqrt(252)  # Annualized to daily
                
                # 95% confidence level VaR
                var_95 = portfolio_value * daily_volatility * 1.645
                var_99 = portfolio_value * daily_volatility * 2.33
                
                with self._risk_lock:
                    self.portfolio_risk.var_1d = -var_95  # Negative for loss
                    self.portfolio_risk.var_10d = -var_95 * math.sqrt(10)
                    self.portfolio_risk.expected_shortfall = -var_99
            else:
                # More sophisticated VaR calculation with scipy
                # Would use historical returns and Monte Carlo simulation
                self._calculate_sophisticated_var()
                
        except Exception as e:
            self.logger.error(f"VaR calculation failed: {e}")
    
    def _calculate_sophisticated_var(self):
        """Calculate sophisticated VaR using statistical methods."""
        try:
            # This would implement Monte Carlo or historical VaR
            # For now, use simplified calculation
            portfolio_value = self.portfolio_risk.total_exposure
            
            # Simulate returns using normal distribution
            daily_vol = self.market_volatility / math.sqrt(252)
            returns = np.random.normal(0, daily_vol, 10000)
            portfolio_returns = returns * portfolio_value
            
            # Calculate VaR at different confidence levels
            var_95 = np.percentile(portfolio_returns, 5)  # 5th percentile
            var_99 = np.percentile(portfolio_returns, 1)  # 1st percentile
            
            # Expected Shortfall (CVaR)
            es_95 = np.mean(portfolio_returns[portfolio_returns <= var_95])
            
            with self._risk_lock:
                self.portfolio_risk.var_1d = var_95
                self.portfolio_risk.var_10d = var_95 * math.sqrt(10)
                self.portfolio_risk.expected_shortfall = es_95
                
        except Exception as e:
            self.logger.error(f"Sophisticated VaR calculation failed: {e}")
    
    def _perform_stress_tests(self):
        """Perform portfolio stress tests."""
        try:
            worst_case_loss = 0.0
            
            for scenario in self.stress_scenarios:
                # Simulate scenario impact
                scenario_loss = self._simulate_stress_scenario(scenario)
                scenario.expected_loss = scenario_loss
                
                if scenario_loss < worst_case_loss:
                    worst_case_loss = scenario_loss
            
            with self._risk_lock:
                self.portfolio_risk.stress_test_loss = worst_case_loss
            
            # Check if stress test results require action
            if abs(worst_case_loss) > self.risk_limits.max_daily_loss * 2:
                self._generate_risk_alert(
                    "STRESS_TEST_FAILURE",
                    RiskLevel.HIGH,
                    f"Stress test shows potential loss of ${worst_case_loss:,.0f}",
                    recommended_actions=["Review portfolio construction", "Add hedges"]
                )
                
        except Exception as e:
            self.logger.error(f"Stress testing failed: {e}")
    
    def _simulate_stress_scenario(self, scenario: StressTestScenario) -> float:
        """Simulate impact of stress scenario on portfolio."""
        try:
            # Simplified stress test calculation
            portfolio_value = self.portfolio_risk.total_exposure
            delta_exposure = self.portfolio_risk.delta_exposure
            vega_exposure = self.portfolio_risk.vega_exposure
            theta_exposure = self.portfolio_risk.theta_exposure
            
            # Calculate scenario impact
            delta_pnl = delta_exposure * scenario.market_move * 100  # Delta per $1 move
            vega_pnl = vega_exposure * scenario.volatility_change * 100  # Vega per 1% vol change
            theta_pnl = theta_exposure * scenario.time_decay_days  # Theta per day
            
            total_pnl = delta_pnl + vega_pnl + theta_pnl
            
            return total_pnl
            
        except Exception as e:
            self.logger.error(f"Stress scenario simulation failed: {e}")
            return 0.0
    
    def _update_market_data(self):
        """Update market data for risk calculations."""
        try:
            # This would integrate with market data feed
            # For now, simulate updates
            import random
            
            # Simulate VIX updates
            vix_change = random.uniform(-0.5, 0.5)
            self.vix_level = max(10.0, min(50.0, self.vix_level + vix_change))
            
            # Simulate volatility updates
            vol_change = random.uniform(-0.001, 0.001)
            self.market_volatility = max(0.05, min(0.50, self.market_volatility + vol_change))
            
        except Exception as e:
            self.logger.error(f"Market data update failed: {e}")
    
    def _generate_risk_alert(
        self, 
        alert_type: str, 
        severity: RiskLevel, 
        message: str,
        affected_positions: List[str] = None,
        recommended_actions: List[str] = None
    ):
        """Generate a risk alert."""
        try:
            alert = RiskAlert(
                alert_id=str(uuid.uuid4()),
                alert_type=alert_type,
                severity=severity,
                message=message,
                affected_positions=affected_positions or [],
                recommended_actions=recommended_actions or []
            )
            
            with self._alert_lock:
                self.active_alerts[alert.alert_id] = alert
                self.alert_history.append(alert)
                self.alerts_generated += 1
            
            self.logger.warning(f"Risk Alert [{severity.value.upper()}]: {message}")
            
            # Emit alert event
            if self.has_event_manager:
                self.event_manager.emit_event(
                    EventType.RISK_ALERT_GENERATED,
                    {
                        'alert_id': alert.alert_id,
                        'alert_type': alert_type,
                        'severity': severity.value,
                        'message': message,
                        'timestamp': alert.timestamp
                    }
                )
                
        except Exception as e:
            self.logger.error(f"Risk alert generation failed: {e}")
    
    def _process_risk_alerts(self):
        """Process and manage active risk alerts."""
        try:
            with self._alert_lock:
                # Check for alerts that should be auto-acknowledged
                current_time = datetime.now()
                alerts_to_acknowledge = []
                
                for alert_id, alert in self.active_alerts.items():
                    # Auto-acknowledge old alerts (older than 1 hour)
                    if (current_time - alert.timestamp).total_seconds() > 3600:
                        alerts_to_acknowledge.append(alert_id)
                
                # Acknowledge old alerts
                for alert_id in alerts_to_acknowledge:
                    if alert_id in self.active_alerts:
                        self.active_alerts[alert_id].acknowledged = True
                        self.logger.info(f"Auto-acknowledged alert: {alert_id}")
                
        except Exception as e:
            self.logger.error(f"Risk alert processing failed: {e}")
    
    # ==========================================================================
    # PUBLIC QUERY METHODS
    # ==========================================================================
    
    def get_portfolio_risk_summary(self) -> Dict[str, Any]:
        """
        Get portfolio risk summary.
        
        Returns:
            Portfolio risk summary dictionary
        """
        try:
            with self._risk_lock:
                return {
                    'total_exposure': self.portfolio_risk.total_exposure,
                    'delta_exposure': self.portfolio_risk.delta_exposure,
                    'gamma_exposure': self.portfolio_risk.gamma_exposure,
                    'vega_exposure': self.portfolio_risk.vega_exposure,
                    'theta_exposure': self.portfolio_risk.theta_exposure,
                    'var_1d': self.portfolio_risk.var_1d,
                    'var_10d': self.portfolio_risk.var_10d,
                    'expected_shortfall': self.portfolio_risk.expected_shortfall,
                    'concentration_risk': self.portfolio_risk.concentration_risk,
                    'stress_test_loss': self.portfolio_risk.stress_test_loss,
                    'last_update': self.portfolio_risk.last_update.isoformat(),
                    'circuit_breaker_state': self.circuit_breaker_state.value,
                    'vix_level': self.vix_level,
                    'market_volatility': self.market_volatility
                }
                
        except Exception as e:
            self.logger.error(f"Error getting portfolio risk summary: {e}")
            return {}
    
    def get_risk_limits(self) -> Dict[str, Any]:
        """
        Get current risk limits.
        
        Returns:
            Risk limits dictionary
        """
        try:
            return asdict(self.risk_limits)
        except Exception as e:
            self.logger.error(f"Error getting risk limits: {e}")
            return {}
    
    def get_active_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get active risk alerts.
        
        Args:
            hours: Hours to look back for alerts
            
        Returns:
            List of active alert dictionaries
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            alerts = []
            
            with self._alert_lock:
                for alert in self.active_alerts.values():
                    if alert.timestamp >= cutoff_time and not alert.acknowledged:
                        alerts.append({
                            'alert_id': alert.alert_id,
                            'alert_type': alert.alert_type,
                            'severity': alert.severity.value,
                            'message': alert.message,
                            'affected_positions': alert.affected_positions,
                            'recommended_actions': alert.recommended_actions,
                            'timestamp': alert.timestamp.isoformat(),
                            'acknowledged': alert.acknowledged
                        })
            
            # Sort by severity and timestamp
            alerts.sort(key=lambda x: (x['severity'], x['timestamp']), reverse=True)
            return alerts
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {e}")
            return []
    
    def get_risk_statistics(self) -> Dict[str, Any]:
        """
        Get risk management statistics.
        
        Returns:
            Risk statistics dictionary
        """
        try:
            approval_rate = (self.trades_approved / max(self.risk_checks_performed, 1)) * 100
            
            return {
                'risk_checks_performed': self.risk_checks_performed,
                'trades_approved': self.trades_approved,
                'trades_rejected': self.trades_rejected,
                'approval_rate': approval_rate,
                'alerts_generated': self.alerts_generated,
                'active_alerts_count': len([a for a in self.active_alerts.values() if not a.acknowledged]),
                'monitoring_active': self.monitoring_active,
                'circuit_breaker_state': self.circuit_breaker_state.value,
                'last_risk_check': self.last_risk_check.isoformat(),
                'last_var_calculation': self.last_var_calculation.isoformat(),
                'risk_profile': self.risk_profile.value
            }
            
        except Exception as e:
            self.logger.error(f"Error getting risk statistics: {e}")
            return {}

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_manager(config: Dict[str, Any] = None) -> RiskManager:
    """
    Factory function to create a RiskManager instance.
    
    Args:
        config: Risk manager configuration
        
    Returns:
        RiskManager instance
    """
    return RiskManager(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance
_risk_manager_instance: Optional[RiskManager] = None
_risk_manager_lock = Lock()

def get_risk_manager(config: Dict[str, Any] = None) -> RiskManager:
    """
    Get singleton RiskManager instance.
    
    Args:
        config: Configuration (only used for first call)
        
    Returns:
        RiskManager instance
    """
    global _risk_manager_instance
    
    with _risk_manager_lock:
        if _risk_manager_instance is None:
            _risk_manager_instance = RiskManager(config)
        
        return _risk_manager_instance

def reset_risk_manager():
    """Reset the singleton risk manager instance (for testing)."""
    global _risk_manager_instance
    with _risk_manager_lock:
        if _risk_manager_instance and _risk_manager_instance.monitoring_active:
            _risk_manager_instance.stop_monitoring()
        _risk_manager_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing RiskManager...")
    
    # Mock configuration
    test_config = {
        'risk_profile': 'moderate',
        'risk_limits': {
            'max_daily_loss': 1000.0,
            'max_single_position': 10000.0
        }
    }
    
    # Create risk manager
    risk_manager = RiskManager(test_config)
    
    if risk_manager.initialize():
        print("✅ RiskManager initialized successfully")
        
        if risk_manager.start_monitoring():
            print("✅ Risk monitoring started successfully")
            
            # Test risk check with mock signal
            class MockSignal:
                def __init__(self):
                    self.signal_id = "test_signal"
                    self.symbol = "SPY"
                    self.quantity = 100
                    self.action = "BUY"
            
            mock_signal = MockSignal()
            result = risk_manager.check_pre_trade_risk(mock_signal)
            print(f"🔍 Risk check result: {result.action.value} (Score: {result.risk_score:.1f})")
            
            # Get risk summary
            summary = risk_manager.get_portfolio_risk_summary()
            print(f"📊 Portfolio risk summary: {len(summary)} metrics")
            
            # Get statistics
            stats = risk_manager.get_risk_statistics()
            print(f"📈 Risk statistics: {stats.get('risk_checks_performed', 0)} checks performed")
            
            # Brief operation
            time.sleep(2)
            
            if risk_manager.stop_monitoring():
                print("✅ Risk monitoring stopped successfully")
            else:
                print("❌ Risk monitoring stop failed")
        else:
            print("❌ Risk monitoring start failed")
    else:
        print("❌ RiskManager initialization failed")
    
    print("RiskManager testing completed.")#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE01_RiskManager.py
Group: E (Risk Management)
Purpose: Enhanced comprehensive risk management with real-time monitoring

Description:
    This module provides institutional-grade risk management capabilities including
    pre-trade risk checks, real-time position monitoring, portfolio risk assessment,
    and automated risk mitigation. It implements sophisticated risk models, stress
    testing, and provides comprehensive risk reporting for professional trading
    operations.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 18:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple, NamedTuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# Statistical imports
try:
    from scipy import stats
    from scipy.stats import norm
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: scipy not found. Advanced risk calculations will be limited.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OrderAction, OptionType
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# Conditional imports
try:
    from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
    HAS_PERFORMANCE_METRICS = True
except ImportError:
    HAS_PERFORMANCE_METRICS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk Limits Configuration
DEFAULT_MAX_DAILY_LOSS = 5000.0           # USD
DEFAULT_MAX_PORTFOLIO_DELTA = 1000.0      # Delta exposure
DEFAULT_MAX_PORTFOLIO_GAMMA = 100.0       # Gamma exposure  
DEFAULT_MAX_PORTFOLIO_VEGA = 500.0        # Vega exposure
DEFAULT_MAX_SINGLE_POSITION = 50000.0     # USD per position
DEFAULT_MAX_CONCENTRATION = 0.25           # 25% max in single position

# Greeks Limits
DEFAULT_DELTA_LIMIT = 1000
DEFAULT_GAMMA_LIMIT = 100
DEFAULT_THETA_LIMIT = 500
DEFAULT_VEGA_LIMIT = 1000
DEFAULT_RHO_LIMIT = 500

# Risk Monitoring
RISK_CHECK_INTERVAL = 1.0    # seconds
STRESS_TEST_INTERVAL = 300   # 5 minutes
VaR_CALCULATION_INTERVAL = 60 # 1 minute

# Volatility Parameters
DEFAULT_VOLATILITY_WINDOW = 30  # days
VIX_SPIKE_THRESHOLD = 30        # VIX level
VOLATILITY_SHOCK_THRESHOLD = 0.05  # 5% daily move

# Circuit Breaker Thresholds
CIRCUIT_BREAKER_LOSS_PCT = 0.05    # 5% portfolio loss
CIRCUIT_BREAKER_VIX_LEVEL = 40     # VIX level
CIRCUIT_BREAKER_VOLUME_SPIKE = 2.0  # 2x normal volume

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskProfile(Enum):
    """Risk profile enumeration"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    SPECULATIVE = "speculative"

class RiskLevel(Enum):
    """Risk level enumeration"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskType(Enum):
    """Risk type enumeration"""
    MARKET_RISK = "market_risk"
    CREDIT_RISK = "credit_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    OPERATIONAL_RISK = "operational_risk"
    MODEL_RISK = "model_risk"
    CONCENTRATION_RISK = "concentration_risk"

class RiskAction(Enum):
    """Risk action enumeration"""
    APPROVE = "approve"
    REJECT = "reject"
    WARN = "warn"
    REDUCE_SIZE = "reduce_size"
    HEDGE = "hedge"
    LIQUIDATE = "liquidate"

class CircuitBreakerState(Enum):
    """Circuit breaker state"""
    NORMAL = "normal"
    WARNING = "warning"
    TRIGGERED = "triggered"
    HALTED = "halted"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskLimits:
    """Risk limits configuration"""
    max_daily_loss: float = DEFAULT_MAX_DAILY_LOSS
    max_portfolio_delta: float = DEFAULT_MAX_PORTFOLIO_DELTA
    max_portfolio_gamma: float = DEFAULT_MAX_PORTFOLIO_GAMMA
    max_portfolio_vega: float = DEFAULT_MAX_PORTFOLIO_VEGA
    max_single_position: float = DEFAULT_MAX_SINGLE_POSITION
    max_concentration: float = DEFAULT_MAX_CONCENTRATION
    max_leverage: float = 2.0
    max_correlation_exposure: float = 0.5
    
    # Greeks limits
    delta_limit: float = DEFAULT_DELTA_LIMIT
    gamma_limit: float = DEFAULT_GAMMA_LIMIT
    theta_limit: float = DEFAULT_THETA_LIMIT
    vega_limit: float = DEFAULT_VEGA_LIMIT
    rho_limit: float = DEFAULT_RHO_LIMIT

@dataclass
class RiskCheckResult:
    """Risk check result"""
    approved: bool
    action: RiskAction
    risk_level: RiskLevel
    risk_score: float
    reason: str
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioRisk:
    """Portfolio risk metrics"""
    total_exposure: float = 0.0
    delta_exposure: float = 0.0
    gamma_exposure: float = 0.0
    vega_exposure: float = 0.0
    theta_exposure: float = 0.0
    var_1d: float = 0.0          # 1-day Value at Risk
    var_10d: float = 0.0         # 10-day Value at Risk
    expected_shortfall: float = 0.0
    concentration_risk: float = 0.0
    correlation_risk: float = 0.0
    liquidity_risk: float = 0.0
    stress_test_loss: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    beta: float = 1.0
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class StressTestScenario:
    """Stress test scenario"""
    name: str
    description: str
    market_move: float           # % move in underlying
    volatility_change: float     # % change in volatility
    time_decay_days: int = 0     # Days of time decay
    expected_loss: float = 0.0   # Expected loss from scenario

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    enabled: bool = True
    daily_loss_threshold: float = CIRCUIT_BREAKER_LOSS_PCT
    vix_threshold: float = CIRCUIT_BREAKER_VIX_LEVEL
    volume_spike_threshold: float = CIRCUIT_BREAKER_VOLUME_SPIKE
    position_limit_breach_count: int = 3
    consecutive_losses_limit: int = 5

@dataclass
class RiskAlert:
    """Risk alert data structure"""
    alert_id: str
    alert_type: str
    severity: RiskLevel
    message: str
    affected_positions: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RiskManager:
    """
    Enhanced Risk Management System.
    
    This class provides comprehensive risk management capabilities including
    pre-trade risk checks, real-time portfolio monitoring, stress testing,
    and automated risk mitigation for professional trading operations.
    
    Key Features:
    - Real-time risk monitoring and alerting
    - Pre-trade risk validation with dynamic limits
    - Portfolio VaR and stress testing
    - Greeks exposure monitoring and limits
    - Circuit breaker protection mechanisms
    - Concentration and correlation risk analysis
    - Automated risk mitigation recommendations
    
    Attributes:
        logger: Module logger instance
        config: Risk manager configuration
        risk_limits: Current risk limit settings
        portfolio_risk: Current portfolio risk metrics
        circuit_breaker_state: Circuit breaker status
        
    Example:
        >>> risk_manager = get_risk_manager()
        >>> result = risk_manager.check_pre_trade_risk(signal)
        >>> if result.approved:
        >>>     # Proceed with trade
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Risk Manager.
        
        Args:
            config: Risk manager configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        
        # Risk configuration
        self.risk_limits = self._initialize_risk_limits()
        self.risk_profile = RiskProfile(self.config.get('risk_profile', 'moderate'))
        
        # Portfolio risk tracking
        self.portfolio_risk = PortfolioRisk()
        self.risk_history: deque = deque(maxlen=10000)
        self._risk_lock = RLock()
        
        # Circuit breaker system
        self.circuit_breaker_config = CircuitBreakerConfig()
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        self._circuit_breaker_lock = RLock()
        
        # Risk alerts
        self.active_alerts: Dict[str, RiskAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self._alert_lock = RLock()
        
        # Performance metrics
        if HAS_PERFORMANCE_METRICS:
            self.performance_metrics = PerformanceMetrics()
        else:
            self.performance_metrics = None
        
        # Threading infrastructure
        self.worker_threads: Dict[str, threading.Thread] = {}
        self._shutdown_event = ThreadEvent()
        
        # Market data cache
        self.market_data: Dict[str, Any] = {}
        self.vix_level: float = 20.0
        self.market_volatility: float = 0.15
        self._market_data_lock = RLock()
        
        # Stress test scenarios
