#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE01_RiskManager.py
Group: E (Risk Management)
Purpose: Risk management and position monitoring

Description:
    This module provides comprehensive risk management for the Spyder trading
    system. It monitors portfolio exposure, enforces position limits, tracks
    risk metrics in real-time, and provides circuit breaker functionality.
    The system implements institutional-grade risk controls including Greeks
    limits, VaR calculations, and stress testing capabilities.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.5
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import TRADING_DAYS_PER_YEAR


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Risk limits - Portfolio level
MAX_PORTFOLIO_RISK_PERCENT = 2.0    # 2% max portfolio risk
MAX_POSITION_SIZE_PERCENT = 5.0     # 5% max single position
MAX_SECTOR_EXPOSURE_PERCENT = 20.0  # 20% max sector exposure
MAX_CORRELATION_RISK = 0.7          # Maximum correlation threshold

# Risk limits - Greeks
MAX_PORTFOLIO_DELTA = 100.0         # Maximum portfolio delta
MAX_PORTFOLIO_GAMMA = 50.0          # Maximum portfolio gamma
MAX_PORTFOLIO_VEGA = 200.0          # Maximum portfolio vega
MAX_PORTFOLIO_THETA = -500.0        # Maximum negative theta

# Trading limits
MAX_DAILY_TRADES = 50               # Maximum trades per day
MAX_HOURLY_TRADES = 10              # Maximum trades per hour
MAX_POSITION_COUNT = 20             # Maximum open positions
MAX_DAILY_LOSS_PERCENT = 1.0        # Daily loss limit (1%)

# Circuit breaker thresholds
CIRCUIT_BREAKER_1_PERCENT = 0.5     # Warning level
CIRCUIT_BREAKER_2_PERCENT = 0.75    # Reduce position level
CIRCUIT_BREAKER_3_PERCENT = 1.0     # Stop trading level

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk level classifications."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    EXTREME = "extreme"

class RiskCheckResult(Enum):
    """Risk check results."""
    APPROVED = "approved"
    WARNING = "warning"
    REJECTED = "rejected"
    BLOCKED = "blocked"

class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    NORMAL = "normal"
    WARNING = "warning"
    RESTRICTED = "restricted"
    HALTED = "halted"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskMetrics:
    """Current risk metrics."""
    portfolio_value: float = 0.0
    open_positions: int = 0
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_vega: float = 0.0
    portfolio_theta: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_percent: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    correlation_risk: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PositionRisk:
    """Individual position risk metrics."""
    symbol: str
    position_size: float
    position_value: float
    position_percent: float
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    unrealized_pnl: float = 0.0
    risk_score: float = 0.0

@dataclass
class RiskCheck:
    """Risk check result details."""
    result: RiskCheckResult
    risk_level: RiskLevel
    messages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    metrics: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RiskProfile:
    """
    Risk profile configuration for trading strategies.
    
    Defines risk parameters and limits for different trading profiles
    from conservative to aggressive risk tolerance levels.
    """
    
    name: str = "moderate"
    max_daily_loss: float = 0.02        # 2% max daily loss
    max_position_size: float = 0.05     # 5% max position size
    max_portfolio_heat: float = 0.10    # 10% max portfolio risk
    max_leverage: float = 2.0           # 2x max leverage
    
    # Strategy-specific limits
    max_strategies: int = 5             # Max concurrent strategies
    max_positions_per_strategy: int = 3 # Max positions per strategy
    
    # Risk thresholds
    stop_loss_threshold: float = 0.15   # 15% stop loss
    profit_target: float = 0.10         # 10% profit target
    
    # Volatility limits
    max_vix_level: float = 30.0         # Max VIX for new positions
    min_iv_rank: float = 20.0           # Min IV rank for entries
    
    def __post_init__(self):
        """Validate risk profile parameters."""
        if self.max_daily_loss <= 0 or self.max_daily_loss > 0.10:
            raise ValueError("Daily loss limit must be between 0 and 10%")
        
        if self.max_position_size <= 0 or self.max_position_size > 0.20:
            raise ValueError("Position size must be between 0 and 20%")
    
    @classmethod
    def conservative(cls) -> 'RiskProfile':
        """Create conservative risk profile."""
        return cls(
            name="conservative",
            max_daily_loss=0.01,
            max_position_size=0.02,
            max_portfolio_heat=0.05,
            max_leverage=1.5
        )
    
    @classmethod
    def moderate(cls) -> 'RiskProfile':
        """Create moderate risk profile."""
        return cls(
            name="moderate",
            max_daily_loss=0.02,
            max_position_size=0.05,
            max_portfolio_heat=0.10,
            max_leverage=2.0
        )
    
    @classmethod
    def aggressive(cls) -> 'RiskProfile':
        """Create aggressive risk profile.""" 
        return cls(
            name="aggressive",
            max_daily_loss=0.03,
            max_position_size=0.08,
            max_portfolio_heat=0.15,
            max_leverage=3.0
        )

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RiskManager:
    """
    Risk management system for portfolio and position monitoring.
    
    This class provides comprehensive risk management including position
    sizing, Greeks monitoring, circuit breakers, and real-time risk
    metrics calculation. It enforces institutional-grade risk controls
    and provides detailed risk analytics.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        config: Risk management configuration
        risk_metrics: Current portfolio risk metrics
        circuit_breaker_state: Current circuit breaker state
        
    Example:
        >>> risk_mgr = RiskManager(config)
        >>> risk_mgr.start()
        >>> check = risk_mgr.check_trade_risk(trade_params)
    """
    
    def __init__(self, config=None):
        """Initialize risk manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self._load_risk_limits()
        
        # State management
        self.is_running = False
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        
        # Risk tracking
        self.risk_metrics = RiskMetrics()
        self.positions: Dict[str, PositionRisk] = {}
        self.daily_trades = 0
        self.hourly_trades = 0
        self.daily_pnl = 0.0
        
        # Historical data
        self.trade_history: List[Dict] = []
        self.risk_history: List[RiskMetrics] = []
        self.pnl_history: List[float] = []
        
        # Threading
        self._lock = threading.Lock()
        self._monitor_thread = None
        self._stop_event = threading.Event()
        
        # Timestamps
        self.last_trade_time = None
        self.last_risk_update = None
        self.trading_start_time = None
        
        # Risk profiles
        self.risk_profile = RiskProfile.moderate()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the risk manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Risk manager already running")
                return True
            
            self.is_running = True
            self._stop_event.clear()
            self.trading_start_time = datetime.now()
            
            # Start monitoring thread
            self._start_monitor()
            
            self.logger.info("Risk manager started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start risk manager: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the risk manager.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            self.is_running = False
            self._stop_event.set()
            
            # Wait for monitor thread
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            
            self.logger.info("Risk manager stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop risk manager: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - RISK CHECKS
    # ==========================================================================
    def check_trade_risk(
        self,
        symbol: str,
        trade_type: str,
        quantity: int,
        price: float,
        **kwargs
    ) -> RiskCheck:
        """
        Check if a trade meets risk requirements.
        
        Args:
            symbol: Trading symbol
            trade_type: BUY or SELL
            quantity: Number of contracts/shares
            price: Trade price
            **kwargs: Additional parameters (Greeks, etc.)
            
        Returns:
            RiskCheck object with approval status
        """
        risk_check = RiskCheck(
            result=RiskCheckResult.APPROVED,
            risk_level=RiskLevel.LOW
        )
        
        try:
            with self._lock:
                # Check circuit breaker
                if self.circuit_breaker_state == CircuitBreakerState.HALTED:
                    risk_check.result = RiskCheckResult.BLOCKED
                    risk_check.violations.append("Trading halted by circuit breaker")
                    return risk_check
                
                # Calculate position value
                position_value = quantity * price * kwargs.get('multiplier', 100)
                position_percent = (position_value / self.risk_metrics.portfolio_value * 100
                                  if self.risk_metrics.portfolio_value > 0 else 0)
                
                # Position size check
                if position_percent > self.max_position_size:
                    risk_check.result = RiskCheckResult.REJECTED
                    risk_check.violations.append(
                        f"Position size {position_percent:.2f}% exceeds limit {self.max_position_size:.2f}%"
                    )
                
                # Daily trade limit check
                if self.daily_trades >= self.max_daily_trades:
                    risk_check.result = RiskCheckResult.REJECTED
                    risk_check.violations.append(
                        f"Daily trade limit reached ({self.max_daily_trades})"
                    )
                
                # Hourly trade limit check
                if self.hourly_trades >= self.max_hourly_trades:
                    risk_check.result = RiskCheckResult.WARNING
                    risk_check.warnings.append(
                        f"Approaching hourly trade limit ({self.hourly_trades}/{self.max_hourly_trades})"
                    )
                
                # Greeks limits check
                self._check_greeks_limits(risk_check, kwargs)
                
                # Correlation risk check
                self._check_correlation_risk(risk_check, symbol)
                
                # Daily loss check
                if self.daily_pnl < 0 and abs(self.daily_pnl) >= self.max_daily_loss:
                    risk_check.result = RiskCheckResult.BLOCKED
                    risk_check.violations.append(
                        f"Daily loss limit reached (${self.daily_pnl:.2f})"
                    )
                
                # Set risk level
                risk_check.risk_level = self._calculate_risk_level(risk_check)
                
                # Add metrics
                risk_check.metrics = {
                    'position_value': position_value,
                    'position_percent': position_percent,
                    'portfolio_risk': self.risk_metrics.portfolio_delta,
                    'daily_trades': self.daily_trades,
                    'daily_pnl': self.daily_pnl
                }
            
        except Exception as e:
            self.logger.error(f"Error checking trade risk: {e}")
            risk_check.result = RiskCheckResult.REJECTED
            risk_check.violations.append(f"Risk check error: {str(e)}")
        
        return risk_check
    
    def check_risk_limits(self) -> Dict[str, Any]:
        """
        Check current risk limits status.
        
        Returns:
            Dict with risk limit information
        """
        with self._lock:
            portfolio_risk = self.check_portfolio_risk()
            
            return {
                'approved': portfolio_risk.result == RiskCheckResult.APPROVED,
                'risk_level': portfolio_risk.risk_level.value,
                'circuit_breaker': self.circuit_breaker_state.value,
                'warnings': portfolio_risk.warnings,
                'violations': portfolio_risk.violations,
                'risk_metrics': {
                    'portfolio_value': self.risk_metrics.portfolio_value,
                    'open_positions': self.risk_metrics.open_positions,
                    'daily_pnl': self.risk_metrics.daily_pnl,
                    'daily_pnl_percent': self.risk_metrics.daily_pnl_percent,
                    'portfolio_delta': self.risk_metrics.portfolio_delta,
                    'var_95': self.risk_metrics.var_95,
                    'max_drawdown': self.risk_metrics.max_drawdown
                }
            }
    
    def check_portfolio_risk(self) -> RiskCheck:
        """
        Check overall portfolio risk.
        
        Returns:
            RiskCheck object with portfolio risk assessment
        """
        risk_check = RiskCheck(
            result=RiskCheckResult.APPROVED,
            risk_level=RiskLevel.LOW
        )
        
        try:
            with self._lock:
                metrics = self.risk_metrics
                
                # Portfolio exposure check
                total_exposure = sum(pos.position_value for pos in self.positions.values())
                exposure_percent = (total_exposure / metrics.portfolio_value * 100
                                  if metrics.portfolio_value > 0 else 0)
                
                if exposure_percent > 100:
                    risk_check.warnings.append(
                        f"Portfolio leverage {exposure_percent:.1f}%"
                    )
                
                # Greeks checks
                if abs(metrics.portfolio_delta) > self.max_portfolio_delta:
                    risk_check.violations.append(
                        f"Portfolio delta {metrics.portfolio_delta:.1f} exceeds limit"
                    )
                    risk_check.result = RiskCheckResult.WARNING
                
                if abs(metrics.portfolio_gamma) > self.max_portfolio_gamma:
                    risk_check.violations.append(
                        f"Portfolio gamma {metrics.portfolio_gamma:.1f} exceeds limit"
                    )
                    risk_check.result = RiskCheckResult.WARNING
                
                # VaR check
                if metrics.var_95 > metrics.portfolio_value * 0.05:
                    risk_check.warnings.append(
                        f"High VaR: ${metrics.var_95:.2f} ({metrics.var_95/metrics.portfolio_value*100:.1f}%)"
                    )
                
                # Drawdown check
                if metrics.max_drawdown > 0.10:
                    risk_check.warnings.append(
                        f"Significant drawdown: {metrics.max_drawdown*100:.1f}%"
                    )
                
                # Set risk level
                risk_check.risk_level = self._assess_portfolio_risk_level(metrics)
                
                # Add metrics
                risk_check.metrics = {
                    'total_exposure': total_exposure,
                    'exposure_percent': exposure_percent,
                    'portfolio_delta': metrics.portfolio_delta,
                    'portfolio_gamma': metrics.portfolio_gamma,
                    'var_95': metrics.var_95,
                    'max_drawdown': metrics.max_drawdown
                }
            
        except Exception as e:
            self.logger.error(f"Error checking portfolio risk: {e}")
            risk_check.result = RiskCheckResult.REJECTED
            risk_check.violations.append(f"Portfolio risk check error: {str(e)}")
        
        return risk_check
    
    # ==========================================================================
    # PUBLIC METHODS - RISK UPDATES
    # ==========================================================================
    def update_position_risk(self, position_data: Dict[str, Any]) -> bool:
        """
        Update risk metrics for a position.
        
        Args:
            position_data: Position information including Greeks
            
        Returns:
            bool: True if updated successfully
        """
        try:
            symbol = position_data.get('symbol')
            if not symbol:
                return False
            
            with self._lock:
                # Create or update position risk
                pos_risk = PositionRisk(
                    symbol=symbol,
                    position_size=position_data.get('quantity', 0),
                    position_value=position_data.get('market_value', 0),
                    position_percent=0.0,  # Will be calculated
                    delta=position_data.get('delta', 0),
                    gamma=position_data.get('gamma', 0),
                    vega=position_data.get('vega', 0),
                    theta=position_data.get('theta', 0),
                    unrealized_pnl=position_data.get('unrealized_pnl', 0)
                )
                
                # Calculate position percent
                if self.risk_metrics.portfolio_value > 0:
                    pos_risk.position_percent = (
                        pos_risk.position_value / self.risk_metrics.portfolio_value * 100
                    )
                
                # Calculate risk score
                pos_risk.risk_score = self._calculate_position_risk_score(pos_risk)
                
                # Update positions
                self.positions[symbol] = pos_risk
                
                # Recalculate portfolio metrics
                self._update_portfolio_metrics()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating position risk: {e}")
            return False
    
    def update_portfolio_value(self, portfolio_value: float) -> bool:
        """
        Update portfolio value.
        
        Args:
            portfolio_value: Total portfolio value
            
        Returns:
            bool: True if updated successfully
        """
        try:
            with self._lock:
                self.risk_metrics.portfolio_value = portfolio_value
                self.last_risk_update = datetime.now()
                
                # Recalculate position percentages
                for pos in self.positions.values():
                    if portfolio_value > 0:
                        pos.position_percent = pos.position_value / portfolio_value * 100
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio value: {e}")
            return False
    
    def record_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Record a trade for risk tracking.
        
        Args:
            trade_data: Trade information
            
        Returns:
            bool: True if recorded successfully
        """
        try:
            with self._lock:
                # Update trade counts
                self.daily_trades += 1
                self.hourly_trades += 1
                self.last_trade_time = datetime.now()
                
                # Add to history
                trade_data['timestamp'] = self.last_trade_time
                self.trade_history.append(trade_data)
                
                # Trim history
                if len(self.trade_history) > 1000:
                    self.trade_history = self.trade_history[-1000:]
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error recording trade: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - CIRCUIT BREAKERS
    # ==========================================================================
    def check_circuit_breakers(self) -> CircuitBreakerState:
        """
        Check and update circuit breaker state.
        
        Returns:
            Current circuit breaker state
        """
        try:
            with self._lock:
                daily_loss_percent = abs(self.daily_pnl / self.risk_metrics.portfolio_value * 100
                                        if self.risk_metrics.portfolio_value > 0 else 0)
                
                previous_state = self.circuit_breaker_state
                
                # Determine new state
                if daily_loss_percent >= CIRCUIT_BREAKER_3_PERCENT:
                    self.circuit_breaker_state = CircuitBreakerState.HALTED
                elif daily_loss_percent >= CIRCUIT_BREAKER_2_PERCENT:
                    self.circuit_breaker_state = CircuitBreakerState.RESTRICTED
                elif daily_loss_percent >= CIRCUIT_BREAKER_1_PERCENT:
                    self.circuit_breaker_state = CircuitBreakerState.WARNING
                else:
                    self.circuit_breaker_state = CircuitBreakerState.NORMAL
                
                # Log state changes
                if self.circuit_breaker_state != previous_state:
                    self.logger.warning(
                        f"Circuit breaker state changed: {previous_state.value} -> {self.circuit_breaker_state.value}"
                    )
                    self.logger.warning(f"Daily loss: {daily_loss_percent:.2f}%")
            
            return self.circuit_breaker_state
            
        except Exception as e:
            self.logger.error(f"Error checking circuit breakers: {e}")
            return self.circuit_breaker_state
    
    def reset_circuit_breaker(self) -> bool:
        """
        Reset circuit breaker (manual override).
        
        Returns:
            bool: True if reset successfully
        """
        try:
            with self._lock:
                self.circuit_breaker_state = CircuitBreakerState.NORMAL
                self.logger.info("Circuit breaker manually reset")
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting circuit breaker: {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - RISK METRICS
    # ==========================================================================
    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Get current risk metrics.
        
        Returns:
            Dict containing risk metrics
        """
        try:
            with self._lock:
                return {
                    'portfolio_value': self.risk_metrics.portfolio_value,
                    'open_positions': self.risk_metrics.open_positions,
                    'portfolio_greeks': {
                        'delta': self.risk_metrics.portfolio_delta,
                        'gamma': self.risk_metrics.portfolio_gamma,
                        'vega': self.risk_metrics.portfolio_vega,
                        'theta': self.risk_metrics.portfolio_theta
                    },
                    'daily_pnl': self.risk_metrics.daily_pnl,
                    'daily_pnl_percent': self.risk_metrics.daily_pnl_percent,
                    'var_95': self.risk_metrics.var_95,
                    'max_drawdown': self.risk_metrics.max_drawdown,
                    'circuit_breaker': self.circuit_breaker_state.value,
                    'daily_trades': self.daily_trades,
                    'last_update': self.risk_metrics.timestamp.isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting risk metrics: {e}")
            return {}
    
    def get_position_risks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get risk metrics for all positions.
        
        Returns:
            Dict of position risks by symbol
        """
        try:
            with self._lock:
                return {
                    symbol: {
                        'position_value': pos.position_value,
                        'position_percent': pos.position_percent,
                        'greeks': {
                            'delta': pos.delta,
                            'gamma': pos.gamma,
                            'vega': pos.vega,
                            'theta': pos.theta
                        },
                        'unrealized_pnl': pos.unrealized_pnl,
                        'risk_score': pos.risk_score
                    }
                    for symbol, pos in self.positions.items()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting position risks: {e}")
            return {}
    
    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk.
        
        Args:
            confidence_level: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            VaR amount
        """
        try:
            if len(self.pnl_history) < 20:
                return 0.0
            
            # Calculate returns
            returns = pd.Series(self.pnl_history).pct_change().dropna()
            
            if len(returns) < 20:
                return 0.0
            
            # Parametric VaR
            mean_return = returns.mean()
            std_return = returns.std()
            
            # Calculate VaR
            z_score = stats.norm.ppf(1 - confidence_level)
            var = self.risk_metrics.portfolio_value * (mean_return + z_score * std_return)
            
            return abs(var)
            
        except Exception as e:
            self.logger.error(f"Error calculating VaR: {e}")
            return 0.0
    
    def is_healthy(self) -> bool:
        """
        Check if risk manager is healthy.
        
        Returns:
            bool: True if healthy
        """
        return self.is_running and self.circuit_breaker_state != CircuitBreakerState.HALTED
    
    def get_strategy_status(self) -> Dict[str, Any]:
        """
        Get strategy-related risk status.
        
        Returns:
            Dict with strategy risk information
        """
        return {
            'total_strategies': len(self.positions),
            'active_strategies': sum(1 for p in self.positions.values() if p.position_size > 0),
            'risk_profile': self.risk_profile.name,
            'max_strategies': self.risk_profile.max_strategies,
            'max_positions_per_strategy': self.risk_profile.max_positions_per_strategy
        }
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _load_risk_limits(self):
        """Load risk limits from configuration."""
        risk_config = self.config.get('risk_limits', {})
        
        # Portfolio limits
        self.max_portfolio_risk = risk_config.get(
            'max_portfolio_risk_percent', MAX_PORTFOLIO_RISK_PERCENT
        )
        self.max_position_size = risk_config.get(
            'max_position_size_percent', MAX_POSITION_SIZE_PERCENT
        )
        
        # Greeks limits
        self.max_portfolio_delta = risk_config.get(
            'max_portfolio_delta', MAX_PORTFOLIO_DELTA
        )
        self.max_portfolio_gamma = risk_config.get(
            'max_portfolio_gamma', MAX_PORTFOLIO_GAMMA
        )
        self.max_portfolio_vega = risk_config.get(
            'max_portfolio_vega', MAX_PORTFOLIO_VEGA
        )
        self.max_portfolio_theta = risk_config.get(
            'max_portfolio_theta', MAX_PORTFOLIO_THETA
        )
        
        # Trading limits
        self.max_daily_trades = risk_config.get(
            'max_daily_trades', MAX_DAILY_TRADES
        )
        self.max_hourly_trades = risk_config.get(
            'max_hourly_trades', MAX_HOURLY_TRADES
        )
        self.max_daily_loss = risk_config.get(
            'max_daily_loss_percent', MAX_DAILY_LOSS_PERCENT
        )
    
    def _start_monitor(self):
        """Start risk monitoring thread."""
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        self.logger.info("Risk monitor started")
        
        while not self._stop_event.is_set():
            try:
                # Update risk metrics
                self._update_portfolio_metrics()
                
                # Check circuit breakers
                self.check_circuit_breakers()
                
                # Reset hourly counter
                if self.last_trade_time:
                    if datetime.now() - self.last_trade_time > timedelta(hours=1):
                        self.hourly_trades = 0
                
                # Calculate VaR
                self.risk_metrics.var_95 = self.calculate_var(0.95)
                
                # Add to history
                self.risk_history.append(self.risk_metrics)
                if len(self.risk_history) > 1440:  # Keep 24 hours at 1-min intervals
                    self.risk_history = self.risk_history[-1440:]
                
                # Wait for next update
                self._stop_event.wait(60)  # Update every minute
                
            except Exception as e:
                self.logger.error(f"Error in risk monitor: {e}")
                time.sleep(5)
    
    def _update_portfolio_metrics(self):
        """Update portfolio-level risk metrics."""
        try:
            # Calculate portfolio Greeks
            portfolio_delta = sum(pos.delta for pos in self.positions.values())
            portfolio_gamma = sum(pos.gamma for pos in self.positions.values())
            portfolio_vega = sum(pos.vega for pos in self.positions.values())
            portfolio_theta = sum(pos.theta for pos in self.positions.values())
            
            # Calculate P&L
            daily_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            daily_pnl_percent = (daily_pnl / self.risk_metrics.portfolio_value * 100
                               if self.risk_metrics.portfolio_value > 0 else 0)
            
            # Update metrics
            self.risk_metrics.portfolio_delta = portfolio_delta
            self.risk_metrics.portfolio_gamma = portfolio_gamma
            self.risk_metrics.portfolio_vega = portfolio_vega
            self.risk_metrics.portfolio_theta = portfolio_theta
            self.risk_metrics.daily_pnl = daily_pnl
            self.risk_metrics.daily_pnl_percent = daily_pnl_percent
            self.risk_metrics.open_positions = len(self.positions)
            self.risk_metrics.timestamp = datetime.now()
            
            # Update P&L history
            self.pnl_history.append(daily_pnl)
            if len(self.pnl_history) > 252:  # Keep 1 year of daily data
                self.pnl_history = self.pnl_history[-252:]
            
            # Calculate drawdown
            if self.pnl_history:
                peak = max(self.pnl_history)
                current = self.pnl_history[-1]
                self.risk_metrics.max_drawdown = (peak - current) / peak if peak > 0 else 0
            
            # Calculate Sharpe ratio
            if len(self.pnl_history) >= 20:
                returns = pd.Series(self.pnl_history).pct_change().dropna()
                if len(returns) > 0 and returns.std() > 0:
                    self.risk_metrics.sharpe_ratio = (
                        returns.mean() / returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
                    )
            
        except Exception as e:
            self.logger.error(f"Error updating portfolio metrics: {e}")
    
    def _check_greeks_limits(self, risk_check: RiskCheck, trade_params: Dict):
        """Check Greeks limits for a trade."""
        delta = trade_params.get('delta', 0)
        gamma = trade_params.get('gamma', 0)
        vega = trade_params.get('vega', 0)
        theta = trade_params.get('theta', 0)
        
        # Project new portfolio Greeks
        new_delta = self.risk_metrics.portfolio_delta + delta
        new_gamma = self.risk_metrics.portfolio_gamma + gamma
        new_vega = self.risk_metrics.portfolio_vega + vega
        new_theta = self.risk_metrics.portfolio_theta + theta
        
        # Check limits
        if abs(new_delta) > self.max_portfolio_delta:
            risk_check.violations.append(
                f"Portfolio delta would exceed limit: {new_delta:.1f}"
            )
            risk_check.result = RiskCheckResult.REJECTED
        
        if abs(new_gamma) > self.max_portfolio_gamma:
            risk_check.violations.append(
                f"Portfolio gamma would exceed limit: {new_gamma:.1f}"
            )
            risk_check.result = RiskCheckResult.REJECTED
        
        if abs(new_vega) > self.max_portfolio_vega:
            risk_check.warnings.append(
                f"High portfolio vega: {new_vega:.1f}"
            )
        
        if new_theta < self.max_portfolio_theta:
            risk_check.warnings.append(
                f"High negative theta: {new_theta:.1f}"
            )
    
    def _check_correlation_risk(self, risk_check: RiskCheck, symbol: str):
        """Check correlation risk for concentration."""
        # Count similar positions
        similar_positions = sum(1 for s in self.positions.keys() if s.startswith(symbol[:3]))
        
        if similar_positions >= 3:
            risk_check.warnings.append(
                f"High concentration in {symbol[:3]} positions: {similar_positions}"
            )
        
        # Would implement full correlation matrix in production
    
    def _calculate_risk_level(self, risk_check: RiskCheck) -> RiskLevel:
        """Calculate overall risk level from check results."""
        if risk_check.result == RiskCheckResult.BLOCKED:
            return RiskLevel.EXTREME
        elif risk_check.result == RiskCheckResult.REJECTED:
            return RiskLevel.CRITICAL
        elif len(risk_check.violations) > 0:
            return RiskLevel.HIGH
        elif len(risk_check.warnings) > 2:
            return RiskLevel.MODERATE
        elif len(risk_check.warnings) > 0:
            return RiskLevel.LOW
        else:
            return RiskLevel.LOW
    
    def _assess_portfolio_risk_level(self, metrics: RiskMetrics) -> RiskLevel:
        """Assess overall portfolio risk level."""
        risk_score = 0
        
        # Delta risk
        delta_util = abs(metrics.portfolio_delta) / self.max_portfolio_delta
        risk_score += delta_util * 20
        
        # Gamma risk
        gamma_util = abs(metrics.portfolio_gamma) / self.max_portfolio_gamma
        risk_score += gamma_util * 20
        
        # P&L risk
        if metrics.daily_pnl_percent < -0.5:
            risk_score += 30
        elif metrics.daily_pnl_percent < -0.25:
            risk_score += 15
        
        # Drawdown risk
        if metrics.max_drawdown > 0.10:
            risk_score += 20
        elif metrics.max_drawdown > 0.05:
            risk_score += 10
        
        # Convert score to level
        if risk_score >= 80:
            return RiskLevel.EXTREME
        elif risk_score >= 60:
            return RiskLevel.CRITICAL
        elif risk_score >= 40:
            return RiskLevel.HIGH
        elif risk_score >= 20:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW
    
    def _calculate_position_risk_score(self, position: PositionRisk) -> float:
        """Calculate risk score for a position."""
        score = 0.0
        
        # Size risk
        score += position.position_percent * 10
        
        # Greeks risk
        score += abs(position.delta) * 0.5
        score += abs(position.gamma) * 1.0
        score += abs(position.vega) * 0.2
        
        # P&L risk
        if position.unrealized_pnl < 0:
            loss_percent = abs(position.unrealized_pnl) / position.position_value
            score += loss_percent * 50
        
        return min(score, 100.0)
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def shutdown(self) -> None:
        """Shutdown the risk manager gracefully."""
        try:
            self.stop()
            
            # Clear data
            with self._lock:
                self.positions.clear()
                self.trade_history.clear()
                self.risk_history.clear()
                self.pnl_history.clear()
            
            self.logger.info("Risk manager shut down")
            
        except Exception as e:
            self.logger.error(f"Error during risk manager shutdown: {e}")
    
    def cleanup(self) -> None:
        """Clean up risk manager resources."""
        self.shutdown()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_risk_manager_instance: Optional[RiskManager] = None

def get_risk_manager(config=None) -> RiskManager:
    """
    Get singleton risk manager instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        RiskManager instance
    """
    global _risk_manager_instance
    if _risk_manager_instance is None:
        _risk_manager_instance = RiskManager(config)
    return _risk_manager_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
__all__ = [
    'RiskManager',
    'get_risk_manager',
    'RiskLevel',
    'RiskCheckResult',
    'CircuitBreakerState',
    'RiskMetrics',
    'PositionRisk',
    'RiskCheck',
    'RiskProfile'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing RiskManager module...")
    
    # Create manager
    manager = RiskManager()
    
    # Test startup
    if manager.start():
        print("✅ RiskManager started successfully")
        
        # Set portfolio value
        manager.update_portfolio_value(100000.0)
        print("✅ Portfolio value set: $100,000")
        
        # Test trade risk check
        trade_params = {
            'symbol': 'SPY',
            'trade_type': 'BUY',
            'quantity': 10,
            'price': 450.0,
            'delta': 5.0,
            'gamma': 0.5,
            'vega': 2.0,
            'theta': -1.0
        }
        
        risk_check = manager.check_trade_risk(**trade_params)
        print(f"✅ Trade risk check: {risk_check.result.value}")
        print(f"   Risk level: {risk_check.risk_level.value}")
        if risk_check.warnings:
            print(f"   Warnings: {risk_check.warnings}")
        if risk_check.violations:
            print(f"   Violations: {risk_check.violations}")
        
        # Test position update
        position_data = {
            'symbol': 'SPY',
            'quantity': 10,
            'market_value': 45000.0,
            'delta': 5.0,
            'gamma': 0.5,
            'vega': 2.0,
            'theta': -1.0,
            'unrealized_pnl': 100.0
        }
        
        if manager.update_position_risk(position_data):
            print("✅ Position risk updated")
        
        # Test portfolio risk
        portfolio_risk = manager.check_portfolio_risk()
        print(f"✅ Portfolio risk check: {portfolio_risk.risk_level.value}")
        
        # Get risk metrics
        metrics = manager.get_risk_metrics()
        print("✅ Risk metrics retrieved:")
        print(f"   Portfolio value: ${metrics['portfolio_value']:,.2f}")
        print(f"   Open positions: {metrics['open_positions']}")
        print(f"   Portfolio delta: {metrics['portfolio_greeks']['delta']:.2f}")
        print(f"   Circuit breaker: {metrics['circuit_breaker']}")
        
        # Test circuit breaker
        circuit_state = manager.check_circuit_breakers()
        print(f"✅ Circuit breaker state: {circuit_state.value}")
        
        # Test VaR calculation
        var_95 = manager.calculate_var(0.95)
        print(f"✅ Value at Risk (95%): ${var_95:,.2f}")
        
        # Test health check
        is_healthy = manager.is_healthy()
        print(f"✅ Risk manager health: {'Good' if is_healthy else 'Bad'}")
        
        # Test risk profiles
        print("\n✅ Risk profiles available:")
        conservative = RiskProfile.conservative()
        print(f"   Conservative: max daily loss {conservative.max_daily_loss*100:.1f}%")
        
        moderate = RiskProfile.moderate()
        print(f"   Moderate: max daily loss {moderate.max_daily_loss*100:.1f}%")
        
        aggressive = RiskProfile.aggressive()
        print(f"   Aggressive: max daily loss {aggressive.max_daily_loss*100:.1f}%")
        
        # Test strategy status
        strategy_status = manager.get_strategy_status()
        print(f"\n✅ Strategy status: {strategy_status}")
        
        # Test position risks
        position_risks = manager.get_position_risks()
        print(f"✅ Position risks: {len(position_risks)} positions tracked")
        
        # Cleanup
        manager.stop()
        manager.cleanup()
        print("\n✅ RiskManager test completed successfully!")
        
    else:
        print("❌ RiskManager failed to start")