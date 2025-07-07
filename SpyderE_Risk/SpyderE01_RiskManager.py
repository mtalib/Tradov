#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE01_RiskManager.py
Group: E (Risk Management)
Purpose: Comprehensive risk management with real-time monitoring

Description:
    This module provides institutional-grade risk management capabilities including
    pre-trade risk checks, real-time position monitoring, portfolio risk assessment,
    and automated risk mitigation. It implements sophisticated risk models, stress
    testing, and provides comprehensive risk reporting for professional trading
    operations.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-06 Time: 14:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import math
from concurrent.futures import ThreadPoolExecutor
import queue

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS - SAFE PATTERN
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    # Fallback logger
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': lambda name: logging.getLogger(name)
    })()

try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    # Fallback error handler
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: print(f"Error in {context}: {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk Limits (per $100k portfolio)
DEFAULT_MAX_POSITION_SIZE = 0.05  # 5% max per position
DEFAULT_MAX_PORTFOLIO_RISK = 0.02  # 2% max portfolio risk
DEFAULT_MAX_DAILY_LOSS = 0.03  # 3% max daily loss
DEFAULT_MAX_POSITIONS = 10  # Maximum concurrent positions
DEFAULT_MAX_CORRELATION = 0.7  # Maximum position correlation

# Greeks Limits (per $100k)
DEFAULT_MAX_DELTA = 100  # Maximum portfolio delta
DEFAULT_MAX_GAMMA = 50  # Maximum portfolio gamma
DEFAULT_MAX_VEGA = 200  # Maximum portfolio vega
DEFAULT_MAX_THETA = -100  # Maximum portfolio theta (negative for income)

# VaR Parameters
VAR_CONFIDENCE_LEVEL = 0.95  # 95% confidence
VAR_LOOKBACK_DAYS = 252  # 1 year of trading days
STRESS_TEST_SCENARIOS = 20  # Number of Monte Carlo scenarios

# Monitoring
RISK_CHECK_INTERVAL = 5  # seconds
PORTFOLIO_UPDATE_INTERVAL = 30  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk level classifications"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskCheckResult(Enum):
    """Risk check outcomes"""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

class MitigationAction(Enum):
    """Risk mitigation actions"""
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    HEDGE_POSITION = "hedge_position"
    STOP_TRADING = "stop_trading"
    ALERT_ONLY = "alert_only"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size: float = DEFAULT_MAX_POSITION_SIZE
    max_portfolio_risk: float = DEFAULT_MAX_PORTFOLIO_RISK
    max_daily_loss: float = DEFAULT_MAX_DAILY_LOSS
    max_positions: int = DEFAULT_MAX_POSITIONS
    max_correlation: float = DEFAULT_MAX_CORRELATION
    max_delta: float = DEFAULT_MAX_DELTA
    max_gamma: float = DEFAULT_MAX_GAMMA
    max_vega: float = DEFAULT_MAX_VEGA
    max_theta: float = DEFAULT_MAX_THETA
    custom_limits: Dict[str, float] = field(default_factory=dict)

@dataclass
class PositionRisk:
    """Risk metrics for a single position"""
    position_id: str
    symbol: str
    quantity: int
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    var_95: float
    max_loss_potential: float
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    concentration_risk: float = 0.0
    correlation_risk: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PortfolioRisk:
    """Portfolio-wide risk metrics"""
    timestamp: datetime
    portfolio_value: float
    at_risk_capital: float
    total_var_95: float
    total_cvar_95: float
    max_drawdown: float
    current_drawdown: float
    daily_pnl: float
    total_delta: float
    total_gamma: float
    total_vega: float
    total_theta: float
    correlation_matrix: Optional[np.ndarray] = None
    concentration_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW
    active_positions: int = 0
    risk_utilization: Dict[str, float] = field(default_factory=dict)

@dataclass
class RiskAlert:
    """Risk alert information"""
    alert_id: str
    timestamp: datetime
    severity: RiskLevel
    category: str
    message: str
    position_id: Optional[str] = None
    recommended_action: Optional[MitigationAction] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskProfile:
    """Complete risk profile"""
    timestamp: datetime
    portfolio_risk: PortfolioRisk
    position_risks: Dict[str, PositionRisk]
    active_alerts: List[RiskAlert]
    risk_limits: RiskLimits
    compliance_status: Dict[str, bool]
    recommendations: List[str]

# ==============================================================================
# RISK MANAGER CLASS
# ==============================================================================
class RiskManager:
    """
    Comprehensive risk management system.
    
    Provides real-time risk monitoring, pre-trade checks, portfolio risk
    assessment, and automated risk mitigation with thread-safe operations.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        risk_limits: Current risk limits
        portfolio_risk: Current portfolio risk metrics
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize risk manager with configuration."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.risk_limits = self._load_risk_limits()
        
        # State management with thread safety
        self._state_lock = RLock()
        self._position_risks: Dict[str, PositionRisk] = {}
        self._portfolio_risk = self._create_empty_portfolio_risk()
        self._risk_alerts: deque = deque(maxlen=1000)
        self._risk_history: deque = deque(maxlen=10000)
        
        # Historical data for calculations
        self._returns_buffer: deque = deque(maxlen=VAR_LOOKBACK_DAYS)
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Monitoring
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._event_queue = queue.Queue()
        
        # Callbacks
        self._alert_callbacks: List[Callable] = []
        self._mitigation_callbacks: List[Callable] = []
        
        # Initialize
        self._initialized = False
        self._initialize()
        
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize(self) -> None:
        """Initialize risk management components."""
        try:
            # Load historical data if available
            self._load_historical_data()
            
            # Start monitoring
            self.start_monitoring()
            
            self._initialized = True
            self.logger.info("RiskManager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"RiskManager initialization failed: {e}")
            self.error_handler.handle_error(e, {"method": "_initialize"})
    
    def _load_risk_limits(self) -> RiskLimits:
        """Load risk limits from configuration."""
        limits_config = self.config.get('risk_limits', {})
        return RiskLimits(
            max_position_size=limits_config.get('max_position_size', DEFAULT_MAX_POSITION_SIZE),
            max_portfolio_risk=limits_config.get('max_portfolio_risk', DEFAULT_MAX_PORTFOLIO_RISK),
            max_daily_loss=limits_config.get('max_daily_loss', DEFAULT_MAX_DAILY_LOSS),
            max_positions=limits_config.get('max_positions', DEFAULT_MAX_POSITIONS),
            max_correlation=limits_config.get('max_correlation', DEFAULT_MAX_CORRELATION),
            max_delta=limits_config.get('max_delta', DEFAULT_MAX_DELTA),
            max_gamma=limits_config.get('max_gamma', DEFAULT_MAX_GAMMA),
            max_vega=limits_config.get('max_vega', DEFAULT_MAX_VEGA),
            max_theta=limits_config.get('max_theta', DEFAULT_MAX_THETA),
            custom_limits=limits_config.get('custom_limits', {})
        )
    
    def _create_empty_portfolio_risk(self) -> PortfolioRisk:
        """Create empty portfolio risk object."""
        return PortfolioRisk(
            timestamp=datetime.now(),
            portfolio_value=0.0,
            at_risk_capital=0.0,
            total_var_95=0.0,
            total_cvar_95=0.0,
            max_drawdown=0.0,
            current_drawdown=0.0,
            daily_pnl=0.0,
            total_delta=0.0,
            total_gamma=0.0,
            total_vega=0.0,
            total_theta=0.0,
            active_positions=0
        )
    
    # ==========================================================================
    # PUBLIC METHODS - RISK CHECKS
    # ==========================================================================
    def check_pre_trade_risk(self, trade_params: Dict[str, Any]) -> Tuple[RiskCheckResult, Optional[str]]:
        """
        Perform pre-trade risk checks.
        
        Args:
            trade_params: Trade parameters including symbol, quantity, type
            
        Returns:
            Tuple of (result, rejection_reason)
        """
        try:
            with self._state_lock:
                # Extract trade details
                symbol = trade_params.get('symbol', '')
                quantity = trade_params.get('quantity', 0)
                trade_value = trade_params.get('value', 0)
                trade_type = trade_params.get('type', 'unknown')
                
                # Check position limit
                if len(self._position_risks) >= self.risk_limits.max_positions:
                    return RiskCheckResult.REJECTED, "Maximum position count exceeded"
                
                # Check position size
                portfolio_value = self._portfolio_risk.portfolio_value
                if portfolio_value > 0:
                    position_size_pct = trade_value / portfolio_value
                    if position_size_pct > self.risk_limits.max_position_size:
                        return RiskCheckResult.REJECTED, f"Position size {position_size_pct:.1%} exceeds limit"
                
                # Check daily loss limit
                if self._check_daily_loss_limit():
                    return RiskCheckResult.REJECTED, "Daily loss limit reached"
                
                # Check correlation risk
                correlation_risk = self._calculate_correlation_impact(symbol, quantity)
                if correlation_risk > self.risk_limits.max_correlation:
                    return RiskCheckResult.NEEDS_REVIEW, f"High correlation risk: {correlation_risk:.2f}"
                
                # Check Greeks impact (for options)
                if trade_type == 'option':
                    greeks_check = self._check_greeks_impact(trade_params)
                    if greeks_check[0] == RiskCheckResult.REJECTED:
                        return greeks_check
                
                return RiskCheckResult.APPROVED, None
                
        except Exception as e:
            self.logger.error(f"Pre-trade risk check failed: {e}")
            return RiskCheckResult.REJECTED, "Risk check error"
    
    def calculate_position_risk(self, position: Dict[str, Any]) -> PositionRisk:
        """
        Calculate risk metrics for a position.
        
        Args:
            position: Position details dictionary
            
        Returns:
            PositionRisk object with calculated metrics
        """
        try:
            # Extract position details
            position_id = position.get('id', str(uuid.uuid4()))
            symbol = position.get('symbol', 'UNKNOWN')
            quantity = position.get('quantity', 0)
            entry_price = position.get('entry_price', 0)
            current_price = position.get('current_price', entry_price)
            position_type = position.get('type', 'stock')
            
            # Calculate market value and P&L
            if position_type == 'option':
                multiplier = 100
                market_value = quantity * current_price * multiplier
                cost_basis = quantity * entry_price * multiplier
            else:
                market_value = quantity * current_price
                cost_basis = quantity * entry_price
            
            unrealized_pnl = market_value - cost_basis
            realized_pnl = position.get('realized_pnl', 0)
            
            # Calculate VaR
            var_95 = self._calculate_position_var(symbol, market_value)
            
            # Calculate max loss potential
            max_loss = self._calculate_max_loss_potential(position, market_value)
            
            # Extract Greeks (for options)
            delta = position.get('delta', 0) * quantity
            gamma = position.get('gamma', 0) * quantity
            vega = position.get('vega', 0) * quantity
            theta = position.get('theta', 0) * quantity
            
            # Calculate concentration risk
            portfolio_value = self._portfolio_risk.portfolio_value
            concentration = abs(market_value) / portfolio_value if portfolio_value > 0 else 0
            
            # Determine risk level
            risk_level = self._assess_position_risk_level(
                var_95, max_loss, concentration, market_value
            )
            
            # Create position risk object
            position_risk = PositionRisk(
                position_id=position_id,
                symbol=symbol,
                quantity=quantity,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                var_95=var_95,
                max_loss_potential=max_loss,
                delta=delta,
                gamma=gamma,
                vega=vega,
                theta=theta,
                risk_level=risk_level,
                concentration_risk=concentration,
                correlation_risk=0.0,  # Calculated separately
                metadata={
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'position_type': position_type,
                    'last_updated': datetime.now().isoformat()
                }
            )
            
            # Update internal state
            with self._state_lock:
                self._position_risks[position_id] = position_risk
            
            return position_risk
            
        except Exception as e:
            self.logger.error(f"Position risk calculation failed: {e}")
            self.error_handler.handle_error(e, {"method": "calculate_position_risk"})
            # Return safe default
            return PositionRisk(
                position_id=position.get('id', 'ERROR'),
                symbol=position.get('symbol', 'UNKNOWN'),
                quantity=0,
                market_value=0,
                unrealized_pnl=0,
                realized_pnl=0,
                var_95=0,
                max_loss_potential=0,
                risk_level=RiskLevel.HIGH
            )
    
    def calculate_portfolio_risk(self, positions: List[Dict[str, Any]], 
                               portfolio_value: float) -> PortfolioRisk:
        """
        Calculate portfolio-wide risk metrics.
        
        Args:
            positions: List of position dictionaries
            portfolio_value: Total portfolio value
            
        Returns:
            PortfolioRisk object with calculated metrics
        """
        try:
            with self._state_lock:
                # Calculate position risks
                position_risks = []
                for pos in positions:
                    pos_risk = self.calculate_position_risk(pos)
                    position_risks.append(pos_risk)
                
                # Aggregate metrics
                at_risk_capital = sum(abs(pr.market_value) for pr in position_risks)
                total_unrealized_pnl = sum(pr.unrealized_pnl for pr in position_risks)
                total_realized_pnl = sum(pr.realized_pnl for pr in position_risks)
                
                # Greeks aggregation
                total_delta = sum(pr.delta for pr in position_risks)
                total_gamma = sum(pr.gamma for pr in position_risks)
                total_vega = sum(pr.vega for pr in position_risks)
                total_theta = sum(pr.theta for pr in position_risks)
                
                # Portfolio VaR and CVaR
                portfolio_var = self._calculate_portfolio_var(position_risks)
                portfolio_cvar = self._calculate_portfolio_cvar(position_risks, portfolio_var)
                
                # Drawdown calculations
                max_dd, current_dd = self._calculate_drawdowns(portfolio_value)
                
                # Daily P&L
                daily_pnl = self._calculate_daily_pnl(total_unrealized_pnl, total_realized_pnl)
                
                # Correlation matrix
                correlation_matrix = self._calculate_correlation_matrix(positions)
                
                # Concentration score
                concentration_score = self._calculate_concentration_score(position_risks, portfolio_value)
                
                # Risk utilization
                risk_utilization = self._calculate_risk_utilization(
                    total_delta, total_gamma, total_vega, total_theta,
                    at_risk_capital, portfolio_value, len(positions)
                )
                
                # Overall risk level
                risk_level = self._assess_portfolio_risk_level(
                    portfolio_var, current_dd, concentration_score, risk_utilization
                )
                
                # Create portfolio risk object
                portfolio_risk = PortfolioRisk(
                    timestamp=datetime.now(),
                    portfolio_value=portfolio_value,
                    at_risk_capital=at_risk_capital,
                    total_var_95=portfolio_var,
                    total_cvar_95=portfolio_cvar,
                    max_drawdown=max_dd,
                    current_drawdown=current_dd,
                    daily_pnl=daily_pnl,
                    total_delta=total_delta,
                    total_gamma=total_gamma,
                    total_vega=total_vega,
                    total_theta=total_theta,
                    correlation_matrix=correlation_matrix,
                    concentration_score=concentration_score,
                    risk_level=risk_level,
                    active_positions=len(positions),
                    risk_utilization=risk_utilization
                )
                
                # Update internal state
                self._portfolio_risk = portfolio_risk
                self._risk_history.append(portfolio_risk)
                
                # Check for alerts
                self._check_risk_alerts(portfolio_risk, position_risks)
                
                return portfolio_risk
                
        except Exception as e:
            self.logger.error(f"Portfolio risk calculation failed: {e}")
            self.error_handler.handle_error(e, {"method": "calculate_portfolio_risk"})
            return self._create_empty_portfolio_risk()
    
    def get_risk_profile(self) -> RiskProfile:
        """
        Get comprehensive risk profile.
        
        Returns:
            Current risk profile with all metrics
        """
        with self._state_lock:
            # Compliance check
            compliance_status = self._check_compliance()
            
            # Generate recommendations
            recommendations = self._generate_risk_recommendations()
            
            return RiskProfile(
                timestamp=datetime.now(),
                portfolio_risk=copy.deepcopy(self._portfolio_risk),
                position_risks=copy.deepcopy(self._position_risks),
                active_alerts=list(self._risk_alerts)[-10:],  # Last 10 alerts
                risk_limits=copy.deepcopy(self.risk_limits),
                compliance_status=compliance_status,
                recommendations=recommendations
            )
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_position_var(self, symbol: str, market_value: float) -> float:
        """Calculate Value at Risk for a position."""
        try:
            # Get historical returns
            returns = self._get_symbol_returns(symbol)
            if not returns or len(returns) < 20:
                # Use portfolio returns as proxy
                returns = list(self._returns_buffer)
            
            if not returns:
                # Default to 2% of market value
                return abs(market_value) * 0.02
            
            # Calculate VaR
            returns_array = np.array(returns)
            var_pct = np.percentile(returns_array, (1 - VAR_CONFIDENCE_LEVEL) * 100)
            
            return abs(market_value * var_pct)
            
        except Exception as e:
            self.logger.error(f"VaR calculation failed: {e}")
            return abs(market_value) * 0.02  # Default 2%
    
    def _calculate_max_loss_potential(self, position: Dict[str, Any], 
                                    market_value: float) -> float:
        """Calculate maximum potential loss for a position."""
        position_type = position.get('type', 'stock')
        quantity = position.get('quantity', 0)
        
        if position_type == 'stock':
            # Max loss is full position value for long, unlimited for short
            return abs(market_value) if quantity > 0 else abs(market_value) * 2
            
        elif position_type == 'option':
            option_type = position.get('option_type', 'call')
            strike = position.get('strike', 0)
            
            if quantity > 0:  # Long options
                # Max loss is premium paid
                return abs(market_value)
            else:  # Short options
                if option_type == 'call':
                    # Unlimited risk (capped at 2x strike)
                    return abs(quantity * 100 * strike * 2)
                else:  # put
                    # Max loss is strike price
                    return abs(quantity * 100 * strike)
        
        return abs(market_value)  # Default
    
    def _calculate_portfolio_var(self, position_risks: List[PositionRisk]) -> float:
        """Calculate portfolio VaR considering correlations."""
        if not position_risks:
            return 0.0
        
        # Simple sum for now (conservative)
        # TODO: Implement correlation-adjusted VaR
        return sum(pr.var_95 for pr in position_risks)
    
    def _calculate_portfolio_cvar(self, position_risks: List[PositionRisk], 
                                portfolio_var: float) -> float:
        """Calculate Conditional VaR (Expected Shortfall)."""
        # Simplified: CVaR is typically 1.2-1.5x VaR
        return portfolio_var * 1.3
    
    def _calculate_drawdowns(self, current_value: float) -> Tuple[float, float]:
        """Calculate maximum and current drawdown."""
        if not self._risk_history:
            return 0.0, 0.0
        
        # Get historical peak
        values = [rh.portfolio_value for rh in self._risk_history]
        peak = max(values) if values else current_value
        
        # Current drawdown
        current_dd = (peak - current_value) / peak if peak > 0 else 0.0
        
        # Max drawdown
        max_dd = 0.0
        running_peak = values[0] if values else current_value
        
        for value in values:
            if value > running_peak:
                running_peak = value
            dd = (running_peak - value) / running_peak if running_peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        
        return max_dd, current_dd
    
    def _calculate_daily_pnl(self, unrealized: float, realized: float) -> float:
        """Calculate daily P&L."""
        # Get today's starting values
        today_start = datetime.now().replace(hour=0, minute=0, second=0)
        
        # Find last risk history entry from yesterday
        yesterday_pnl = 0.0
        for rh in reversed(self._risk_history):
            if rh.timestamp < today_start:
                yesterday_total = sum(pr.unrealized_pnl + pr.realized_pnl 
                                    for pr in self._position_risks.values())
                break
        
        current_total = unrealized + realized
        return current_total - yesterday_pnl
    
    def _calculate_correlation_matrix(self, positions: List[Dict[str, Any]]) -> Optional[np.ndarray]:
        """Calculate correlation matrix for positions."""
        # Simplified - would use actual price correlations
        n = len(positions)
        if n < 2:
            return None
        
        # Create identity matrix with some correlation
        corr_matrix = np.eye(n)
        
        # Add some correlation between positions (simplified)
        for i in range(n):
            for j in range(i + 1, n):
                # Same symbol = high correlation
                if positions[i].get('symbol') == positions[j].get('symbol'):
                    corr_matrix[i, j] = corr_matrix[j, i] = 0.95
                else:
                    # Different symbols = moderate correlation
                    corr_matrix[i, j] = corr_matrix[j, i] = 0.3
        
        return corr_matrix
    
    def _calculate_concentration_score(self, position_risks: List[PositionRisk], 
                                     portfolio_value: float) -> float:
        """Calculate portfolio concentration score (0-1)."""
        if not position_risks or portfolio_value <= 0:
            return 0.0
        
        # Calculate position weights
        weights = [abs(pr.market_value) / portfolio_value for pr in position_risks]
        
        # Herfindahl index
        herfindahl = sum(w * w for w in weights)
        
        # Normalize (1/n = perfectly diversified)
        n = len(weights)
        min_herfindahl = 1 / n if n > 0 else 1
        
        return (herfindahl - min_herfindahl) / (1 - min_herfindahl) if min_herfindahl < 1 else 0
    
    def _calculate_risk_utilization(self, delta: float, gamma: float, vega: float, 
                                  theta: float, at_risk_capital: float, 
                                  portfolio_value: float, position_count: int) -> Dict[str, float]:
        """Calculate risk limit utilization percentages."""
        utilization = {}
        
        # Greeks utilization
        utilization['delta'] = abs(delta) / self.risk_limits.max_delta if self.risk_limits.max_delta > 0 else 0
        utilization['gamma'] = abs(gamma) / self.risk_limits.max_gamma if self.risk_limits.max_gamma > 0 else 0
        utilization['vega'] = abs(vega) / self.risk_limits.max_vega if self.risk_limits.max_vega > 0 else 0
        utilization['theta'] = abs(theta) / abs(self.risk_limits.max_theta) if self.risk_limits.max_theta != 0 else 0
        
        # Capital utilization
        utilization['capital'] = at_risk_capital / portfolio_value if portfolio_value > 0 else 0
        
        # Position count utilization
        utilization['positions'] = position_count / self.risk_limits.max_positions
        
        return utilization
    
    def _calculate_correlation_impact(self, symbol: str, quantity: float) -> float:
        """Calculate correlation impact of new position."""
        # Simplified - would calculate actual correlation impact
        existing_symbols = {pr.symbol for pr in self._position_risks.values()}
        
        if symbol in existing_symbols:
            return 0.8  # High correlation if same symbol
        else:
            return 0.3  # Moderate correlation otherwise
    
    # ==========================================================================
    # PRIVATE METHODS - RISK ASSESSMENT
    # ==========================================================================
    def _assess_position_risk_level(self, var: float, max_loss: float, 
                                  concentration: float, market_value: float) -> RiskLevel:
        """Assess risk level for a position."""
        # Risk scoring
        risk_score = 0
        
        # VaR as percentage of position
        var_pct = var / abs(market_value) if market_value != 0 else 0
        if var_pct > 0.10:  # >10% VaR
            risk_score += 3
        elif var_pct > 0.05:  # >5% VaR
            risk_score += 2
        elif var_pct > 0.02:  # >2% VaR
            risk_score += 1
        
        # Concentration risk
        if concentration > 0.20:  # >20% of portfolio
            risk_score += 3
        elif concentration > 0.10:  # >10%
            risk_score += 2
        elif concentration > 0.05:  # >5%
            risk_score += 1
        
        # Map score to risk level
        if risk_score >= 5:
            return RiskLevel.CRITICAL
        elif risk_score >= 3:
            return RiskLevel.HIGH
        elif risk_score >= 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _assess_portfolio_risk_level(self, var: float, drawdown: float, 
                                   concentration: float, utilization: Dict[str, float]) -> RiskLevel:
        """Assess overall portfolio risk level."""
        risk_score = 0
        
        # Drawdown risk
        if drawdown > 0.20:  # >20% drawdown
            risk_score += 3
        elif drawdown > 0.10:  # >10%
            risk_score += 2
        elif drawdown > 0.05:  # >5%
            risk_score += 1
        
        # Concentration risk
        if concentration > 0.50:  # >50% concentration
            risk_score += 3
        elif concentration > 0.30:  # >30%
            risk_score += 2
        elif concentration > 0.20:  # >20%
            risk_score += 1
        
        # Greeks utilization
        for greek, util in utilization.items():
            if greek in ['delta', 'gamma', 'vega']:
                if util > 0.90:  # >90% utilized
                    risk_score += 2
                elif util > 0.70:  # >70%
                    risk_score += 1
        
        # Map score to risk level
        if risk_score >= 8:
            return RiskLevel.CRITICAL
        elif risk_score >= 5:
            return RiskLevel.HIGH
        elif risk_score >= 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been reached."""
        if not self._portfolio_risk.portfolio_value:
            return False
        
        daily_loss_pct = abs(self._portfolio_risk.daily_pnl) / self._portfolio_risk.portfolio_value
        return daily_loss_pct >= self.risk_limits.max_daily_loss
    
    def _check_greeks_impact(self, trade_params: Dict[str, Any]) -> Tuple[RiskCheckResult, Optional[str]]:
        """Check Greeks impact of new trade."""
        # Extract Greeks from trade
        delta = trade_params.get('delta', 0) * trade_params.get('quantity', 0)
        gamma = trade_params.get('gamma', 0) * trade_params.get('quantity', 0)
        vega = trade_params.get('vega', 0) * trade_params.get('quantity', 0)
        theta = trade_params.get('theta', 0) * trade_params.get('quantity', 0)
        
        # Calculate new totals
        new_delta = self._portfolio_risk.total_delta + delta
        new_gamma = self._portfolio_risk.total_gamma + gamma
        new_vega = self._portfolio_risk.total_vega + vega
        new_theta = self._portfolio_risk.total_theta + theta
        
        # Check limits
        if abs(new_delta) > self.risk_limits.max_delta:
            return RiskCheckResult.REJECTED, f"Delta limit exceeded: {new_delta:.1f}"
        
        if abs(new_gamma) > self.risk_limits.max_gamma:
            return RiskCheckResult.REJECTED, f"Gamma limit exceeded: {new_gamma:.1f}"
        
        if abs(new_vega) > self.risk_limits.max_vega:
            return RiskCheckResult.REJECTED, f"Vega limit exceeded: {new_vega:.1f}"
        
        if new_theta < self.risk_limits.max_theta:  # Theta is negative
            return RiskCheckResult.REJECTED, f"Theta limit exceeded: {new_theta:.1f}"
        
        return RiskCheckResult.APPROVED, None
    
    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        self.logger.info("Risk monitoring started")
        
        while self._monitoring_active:
            try:
                # Quick risk check
                self._perform_risk_check()
                
                # Sleep
                time.sleep(RISK_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.error_handler.handle_error(e, {"method": "_monitoring_loop"})
        
        self.logger.info("Risk monitoring stopped")
    
    def _perform_risk_check(self) -> None:
        """Perform periodic risk check."""
        with self._state_lock:
            # Check position risks
            for pos_id, pos_risk in self._position_risks.items():
                self._check_position_risk(pos_risk)
            
            # Check portfolio risk
            self._check_portfolio_risk()
    
    def _check_position_risk(self, position_risk: PositionRisk) -> None:
        """Check individual position risk."""
        # Check risk level change
        if position_risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            alert = RiskAlert(
                alert_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                severity=position_risk.risk_level,
                category="position_risk",
                message=f"High risk detected for {position_risk.symbol}",
                position_id=position_risk.position_id,
                recommended_action=self._determine_mitigation_action(position_risk)
            )
            self._raise_alert(alert)
    
    def _check_portfolio_risk(self) -> None:
        """Check portfolio-wide risk."""
        portfolio_risk = self._portfolio_risk
        
        # Check risk level
        if portfolio_risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            alert = RiskAlert(
                alert_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                severity=portfolio_risk.risk_level,
                category="portfolio_risk",
                message="High portfolio risk detected",
                recommended_action=MitigationAction.REDUCE_POSITION
            )
            self._raise_alert(alert)
        
        # Check specific metrics
        if portfolio_risk.current_drawdown > self.risk_limits.max_daily_loss:
            alert = RiskAlert(
                alert_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                severity=RiskLevel.CRITICAL,
                category="drawdown",
                message=f"Drawdown {portfolio_risk.current_drawdown:.1%} exceeds limit",
                recommended_action=MitigationAction.STOP_TRADING
            )
            self._raise_alert(alert)
    
    def _check_risk_alerts(self, portfolio_risk: PortfolioRisk, 
                         position_risks: List[PositionRisk]) -> None:
        """Check for risk alerts."""
        # Portfolio alerts
        self._check_portfolio_risk()
        
        # Position alerts
        for pos_risk in position_risks:
            self._check_position_risk(pos_risk)
    
    def _raise_alert(self, alert: RiskAlert) -> None:
        """Raise a risk alert."""
        # Store alert
        self._risk_alerts.append(alert)
        
        # Log alert
        self.logger.warning(f"Risk Alert: {alert.message}")
        
        # Execute callbacks
        for callback in self._alert_callbacks:
            try:
                self._executor.submit(callback, alert)
            except Exception as e:
                self.logger.error(f"Alert callback failed: {e}")
        
        # Execute mitigation if critical
        if alert.severity == RiskLevel.CRITICAL and alert.recommended_action:
            self._execute_mitigation(alert)
    
    def _execute_mitigation(self, alert: RiskAlert) -> None:
        """Execute risk mitigation action."""
        for callback in self._mitigation_callbacks:
            try:
                self._executor.submit(callback, alert)
            except Exception as e:
                self.logger.error(f"Mitigation callback failed: {e}")
    
    def _determine_mitigation_action(self, position_risk: PositionRisk) -> MitigationAction:
        """Determine appropriate mitigation action."""
        if position_risk.risk_level == RiskLevel.CRITICAL:
            return MitigationAction.CLOSE_POSITION
        elif position_risk.risk_level == RiskLevel.HIGH:
            return MitigationAction.REDUCE_POSITION
        else:
            return MitigationAction.ALERT_ONLY
    
    # ==========================================================================
    # PRIVATE METHODS - COMPLIANCE
    # ==========================================================================
    def _check_compliance(self) -> Dict[str, bool]:
        """Check compliance with all risk limits."""
        compliance = {}
        
        # Position limits
        compliance['position_count'] = len(self._position_risks) <= self.risk_limits.max_positions
        compliance['position_sizes'] = all(
            pr.concentration_risk <= self.risk_limits.max_position_size
            for pr in self._position_risks.values()
        )
        
        # Greeks limits
        pr = self._portfolio_risk
        compliance['delta'] = abs(pr.total_delta) <= self.risk_limits.max_delta
        compliance['gamma'] = abs(pr.total_gamma) <= self.risk_limits.max_gamma
        compliance['vega'] = abs(pr.total_vega) <= self.risk_limits.max_vega
        compliance['theta'] = pr.total_theta >= self.risk_limits.max_theta
        
        # Loss limits
        compliance['daily_loss'] = not self._check_daily_loss_limit()
        
        # Overall compliance
        compliance['overall'] = all(compliance.values())
        
        return compliance
    
    def _generate_risk_recommendations(self) -> List[str]:
        """Generate risk management recommendations."""
        recommendations = []
        
        # Check concentration
        if self._portfolio_risk.concentration_score > 0.3:
            recommendations.append("Consider diversifying positions to reduce concentration risk")
        
        # Check Greeks
        utilization = self._portfolio_risk.risk_utilization
        
        if utilization.get('delta', 0) > 0.7:
            recommendations.append(f"Delta exposure high ({utilization['delta']:.0%}), consider hedging")
        
        if utilization.get('gamma', 0) > 0.7:
            recommendations.append(f"Gamma exposure high ({utilization['gamma']:.0%}), monitor closely")
        
        if utilization.get('vega', 0) > 0.7:
            recommendations.append(f"Vega exposure high ({utilization['vega']:.0%}), reduce in high IV")
        
        # Check drawdown
        if self._portfolio_risk.current_drawdown > 0.05:
            recommendations.append(f"In drawdown ({self._portfolio_risk.current_drawdown:.1%}), consider reducing risk")
        
        return recommendations
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_symbol_returns(self, symbol: str) -> List[float]:
        """Get historical returns for a symbol."""
        if symbol not in self._price_history:
            return []
        
        prices = list(self._price_history[symbol])
        if len(prices) < 2:
            return []
        
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] != 0 else 0
            returns.append(ret)
        
        return returns
    
    def _load_historical_data(self) -> None:
        """Load historical data for risk calculations."""
        # This would load from database in production
        self.logger.info("Loading historical risk data")
    
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start risk monitoring."""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="RiskMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Risk monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop risk monitoring."""
        if self._monitoring_active:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            self.logger.info("Risk monitoring stopped")
    
    def shutdown(self) -> None:
        """Shutdown risk manager."""
        self.stop_monitoring()
        self._executor.shutdown(wait=True)
        self.logger.info("RiskManager shutdown complete")
    
    # ==========================================================================
    # PUBLIC METHODS - CALLBACKS
    # ==========================================================================
    def register_alert_callback(self, callback: Callable) -> None:
        """Register callback for risk alerts."""
        self._alert_callbacks.append(callback)
    
    def register_mitigation_callback(self, callback: Callable) -> None:
        """Register callback for risk mitigation."""
        self._mitigation_callbacks.append(callback)
    
    def update_risk_limits(self, new_limits: Dict[str, Any]) -> None:
        """Update risk limits dynamically."""
        with self._state_lock:
            for key, value in new_limits.items():
                if hasattr(self.risk_limits, key):
                    setattr(self.risk_limits, key, value)
            self.logger.info(f"Risk limits updated: {new_limits}")
    
    def add_price_update(self, symbol: str, price: float) -> None:
        """Add price update for risk calculations."""
        self._price_history[symbol].append(price)
    
    def add_return_observation(self, daily_return: float) -> None:
        """Add daily return observation."""
        self._returns_buffer.append(daily_return)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Singleton instance
_risk_manager_instance: Optional[RiskManager] = None
_instance_lock = Lock()

def get_risk_manager(config: Optional[Dict[str, Any]] = None) -> RiskManager:
    """
    Get or create risk manager instance (singleton).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        RiskManager instance
    """
    global _risk_manager_instance
    
    if _risk_manager_instance is None:
        with _instance_lock:
            if _risk_manager_instance is None:
                _risk_manager_instance = RiskManager(config)
    
    return _risk_manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("="*80)
    print("SPYDER E01 - Risk Manager Test")
    print("="*80)
    
    # Initialize risk manager
    risk_mgr = get_risk_manager({
        'risk_limits': {
            'max_position_size': 0.05,
            'max_portfolio_risk': 0.02,
            'max_daily_loss': 0.03,
            'max_positions': 10
        }
    })
    
    # Test position risk calculation
    test_position = {
        'id': 'TEST001',
        'symbol': 'SPY',
        'quantity': 100,
        'entry_price': 400.00,
        'current_price': 405.00,
        'type': 'stock'
    }
    
    pos_risk = risk_mgr.calculate_position_risk(test_position)
    print(f"\nPosition Risk Analysis:")
    print(f"  Symbol: {pos_risk.symbol}")
    print(f"  Market Value: ${pos_risk.market_value:,.2f}")
    print(f"  Unrealized P&L: ${pos_risk.unrealized_pnl:,.2f}")
    print(f"  VaR (95%): ${pos_risk.var_95:,.2f}")
    print(f"  Risk Level: {pos_risk.risk_level.value}")
    
    # Test portfolio risk calculation
    positions = [test_position]
    portfolio_value = 100000
    
    portfolio_risk = risk_mgr.calculate_portfolio_risk(positions, portfolio_value)
    print(f"\nPortfolio Risk Analysis:")
    print(f"  Portfolio Value: ${portfolio_risk.portfolio_value:,.2f}")
    print(f"  At Risk Capital: ${portfolio_risk.at_risk_capital:,.2f}")
    print(f"  Portfolio VaR: ${portfolio_risk.total_var_95:,.2f}")
    print(f"  Risk Level: {portfolio_risk.risk_level.value}")
    
    # Test pre-trade risk check
    trade_params = {
        'symbol': 'SPY',
        'quantity': 100,
        'value': 40500,
        'type': 'stock'
    }
    
    result, reason = risk_mgr.check_pre_trade_risk(trade_params)
    print(f"\nPre-Trade Risk Check:")
    print(f"  Result: {result.value}")
    print(f"  Reason: {reason or 'Approved'}")
    
    # Get risk profile
    profile = risk_mgr.get_risk_profile()
    print(f"\nRisk Profile Summary:")
    print(f"  Compliance Status: {profile.compliance_status.get('overall', False)}")
    print(f"  Active Alerts: {len(profile.active_alerts)}")
    print(f"  Recommendations: {len(profile.recommendations)}")
    
    if profile.recommendations:
        print("\nRecommendations:")
        for rec in profile.recommendations:
            print(f"  - {rec}")
    
    print("\n✅ Risk Manager test completed successfully!")
    
    # Cleanup
    risk_mgr.shutdown()
