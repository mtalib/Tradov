#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderE07_StrategyHealthMonitor.py
Group: E (Risk Management)
Purpose: Monitor strategy performance and auto-disable failing strategies

Description:
    This module monitors the health and performance of trading strategies,
    automatically disabling strategies that fall below configurable thresholds.
    It tracks metrics like win rate, consecutive losses, drawdown, and Sharpe ratio
    to ensure only profitable strategies remain active.

Author: Mohamed Talib
Date: 2025-01-10
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderH_Storage.SpyderH01_DatabaseManager import get_database_manager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default performance thresholds
DEFAULT_MIN_WIN_RATE = 0.30  # 30%
DEFAULT_MAX_CONSECUTIVE_LOSSES = 7
DEFAULT_MAX_DRAWDOWN_PERCENT = 0.10  # 10%
DEFAULT_MIN_SHARPE_RATIO = -0.5
DEFAULT_EVALUATION_PERIOD_TRADES = 20
DEFAULT_GRACE_PERIOD_TRADES = 10
DEFAULT_COOLDOWN_DAYS = 3

# ==============================================================================
# ENUMS
# ==============================================================================
class DisableReason(Enum):
    """Reasons for strategy disabling"""
    LOW_WIN_RATE = auto()
    CONSECUTIVE_LOSSES = auto()
    MAX_DRAWDOWN = auto()
    LOW_SHARPE_RATIO = auto()
    MANUAL_DISABLE = auto()
    SYSTEM_ERROR = auto()

class StrategyStatus(Enum):
    """Strategy operational status"""
    ENABLED = auto()
    DISABLED = auto()
    COOLDOWN = auto()
    GRACE_PERIOD = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_equity: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    last_trade_time: Optional[datetime] = None
    last_evaluation: Optional[datetime] = None

@dataclass
class StrategyHealth:
    """Strategy health status"""
    strategy_name: str
    status: StrategyStatus
    metrics: StrategyMetrics
    is_enabled: bool = True
    disabled_at: Optional[datetime] = None
    disabled_reason: Optional[DisableReason] = None
    cooldown_until: Optional[datetime] = None
    manual_override: bool = False
    grace_trades_remaining: int = 0

# ==============================================================================
# STRATEGY HEALTH MONITOR CLASS
# ==============================================================================
class StrategyHealthMonitor:
    """
    Monitor strategy performance and auto-disable failing strategies.
    
    Features:
    - Real-time performance tracking
    - Configurable thresholds per strategy
    - Grace period for new strategies
    - Cooldown period after disabling
    - Manual override capabilities
    - Performance reset functionality
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize strategy health monitor"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.db_manager = get_database_manager()
        self.event_manager = get_event_manager()
        
        # Configuration
        self.config = config or {}
        self.thresholds = self._load_thresholds()
        
        # Strategy tracking
        self.strategies: Dict[str, StrategyHealth] = {}
        self._lock = threading.Lock()
        
        # Initialize database
        self._initialize_database()
        
        # Load existing strategy states
        self._load_strategy_states()
        
        self.logger.info("StrategyHealthMonitor initialized")
    
    def _load_thresholds(self) -> Dict[str, Any]:
        """Load performance thresholds from config"""
        return {
            'min_win_rate': self.config.get('min_win_rate', DEFAULT_MIN_WIN_RATE),
            'max_consecutive_losses': self.config.get('max_consecutive_losses', DEFAULT_MAX_CONSECUTIVE_LOSSES),
            'max_drawdown_percent': self.config.get('max_drawdown_percent', DEFAULT_MAX_DRAWDOWN_PERCENT),
            'min_sharpe_ratio': self.config.get('min_sharpe_ratio', DEFAULT_MIN_SHARPE_RATIO),
            'evaluation_period_trades': self.config.get('evaluation_period_trades', DEFAULT_EVALUATION_PERIOD_TRADES),
            'grace_period_trades': self.config.get('grace_period_trades', DEFAULT_GRACE_PERIOD_TRADES),
            'cooldown_days': self.config.get('cooldown_days', DEFAULT_COOLDOWN_DAYS)
        }
    
    def _initialize_database(self) -> None:
        """Initialize database table for strategy status"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS strategy_status (
            strategy_name TEXT PRIMARY KEY,
            is_enabled BOOLEAN DEFAULT TRUE,
            status TEXT DEFAULT 'ENABLED',
            disabled_reason TEXT,
            disabled_at TIMESTAMP,
            cooldown_until TIMESTAMP,
            manual_override BOOLEAN DEFAULT FALSE,
            performance_metrics TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        
        try:
            with self.db_manager.get_connection() as conn:
                conn.execute(create_table_sql)
                conn.commit()
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
    
    def _load_strategy_states(self) -> None:
        """Load existing strategy states from database"""
        try:
            query = "SELECT * FROM strategy_status"
            rows = self.db_manager.fetch_all(query)
            
            for row in rows:
                strategy_name = row['strategy_name']
                metrics_json = row['performance_metrics']
                
                # Parse metrics
                metrics_data = json.loads(metrics_json) if metrics_json else {}
                metrics = StrategyMetrics(**metrics_data)
                
                # Parse status
                status = StrategyStatus[row['status']]
                
                # Create health object
                health = StrategyHealth(
                    strategy_name=strategy_name,
                    status=status,
                    metrics=metrics,
                    is_enabled=row['is_enabled'],
                    disabled_at=datetime.fromisoformat(row['disabled_at']) if row['disabled_at'] else None,
                    disabled_reason=DisableReason[row['disabled_reason']] if row['disabled_reason'] else None,
                    cooldown_until=datetime.fromisoformat(row['cooldown_until']) if row['cooldown_until'] else None,
                    manual_override=row['manual_override']
                )
                
                self.strategies[strategy_name] = health
                
        except Exception as e:
            self.logger.error(f"Error loading strategy states: {e}")
    
    def register_strategy(self, strategy_name: str) -> None:
        """Register a new strategy for monitoring"""
        with self._lock:
            if strategy_name not in self.strategies:
                health = StrategyHealth(
                    strategy_name=strategy_name,
                    status=StrategyStatus.GRACE_PERIOD,
                    metrics=StrategyMetrics(),
                    grace_trades_remaining=self.thresholds['grace_period_trades']
                )
                
                self.strategies[strategy_name] = health
                self._save_strategy_state(strategy_name)
                
                self.logger.info(f"Registered strategy: {strategy_name}")
    
    def update_trade_result(self, strategy_name: str, pnl: float, 
                          timestamp: Optional[datetime] = None) -> None:
        """Update strategy metrics with trade result"""
        with self._lock:
            if strategy_name not in self.strategies:
                self.register_strategy(strategy_name)
            
            health = self.strategies[strategy_name]
            metrics = health.metrics
            
            # Update basic metrics
            metrics.total_trades += 1
            metrics.total_pnl += pnl
            metrics.last_trade_time = timestamp or datetime.now()
            
            # Update win/loss tracking
            if pnl > 0:
                metrics.winning_trades += 1
                metrics.consecutive_wins += 1
                metrics.consecutive_losses = 0
                metrics.avg_win = ((metrics.avg_win * (metrics.winning_trades - 1) + pnl) / 
                                  metrics.winning_trades)
            else:
                metrics.losing_trades += 1
                metrics.consecutive_losses += 1
                metrics.consecutive_wins = 0
                metrics.avg_loss = ((metrics.avg_loss * (metrics.losing_trades - 1) + abs(pnl)) / 
                                   metrics.losing_trades)
            
            # Update win rate
            if metrics.total_trades > 0:
                metrics.win_rate = metrics.winning_trades / metrics.total_trades
            
            # Update drawdown
            equity = metrics.peak_equity + pnl
            if equity > metrics.peak_equity:
                metrics.peak_equity = equity
            else:
                drawdown = (metrics.peak_equity - equity) / metrics.peak_equity
                metrics.max_drawdown = max(metrics.max_drawdown, drawdown)
            
            # Handle grace period
            if health.status == StrategyStatus.GRACE_PERIOD:
                health.grace_trades_remaining -= 1
                if health.grace_trades_remaining <= 0:
                    health.status = StrategyStatus.ENABLED
            
            # Check if should disable
            if health.status == StrategyStatus.ENABLED and not health.manual_override:
                should_disable, reason = self._should_disable_strategy(health)
                if should_disable:
                    self._disable_strategy(strategy_name, reason)
            
            # Save state
            self._save_strategy_state(strategy_name)
    
    def _should_disable_strategy(self, health: StrategyHealth) -> Tuple[bool, Optional[DisableReason]]:
        """Check if strategy should be disabled based on performance"""
        metrics = health.metrics
        
        # Only evaluate after minimum trades
        if metrics.total_trades < self.thresholds['evaluation_period_trades']:
            return False, None
        
        # Check win rate
        if metrics.win_rate < self.thresholds['min_win_rate']:
            return True, DisableReason.LOW_WIN_RATE
        
        # Check consecutive losses
        if metrics.consecutive_losses >= self.thresholds['max_consecutive_losses']:
            return True, DisableReason.CONSECUTIVE_LOSSES
        
        # Check drawdown
        if metrics.max_drawdown > self.thresholds['max_drawdown_percent']:
            return True, DisableReason.MAX_DRAWDOWN
        
        # Check Sharpe ratio (if we have enough data)
        if metrics.total_trades >= 50 and metrics.sharpe_ratio < self.thresholds['min_sharpe_ratio']:
            return True, DisableReason.LOW_SHARPE_RATIO
        
        return False, None
    
    def _disable_strategy(self, strategy_name: str, reason: DisableReason) -> None:
        """Disable a strategy"""
        health = self.strategies[strategy_name]
        
        health.status = StrategyStatus.DISABLED
        health.is_enabled = False
        health.disabled_at = datetime.now()
        health.disabled_reason = reason
        health.cooldown_until = datetime.now() + timedelta(days=self.thresholds['cooldown_days'])
        
        # Emit disable event
        if self.event_manager:
            event = self.event_manager.create_event(
                EventType.STRATEGY,
                {
                    'action': 'strategy_disabled',
                    'strategy': strategy_name,
                    'reason': reason.name,
                    'metrics': {
                        'win_rate': health.metrics.win_rate,
                        'consecutive_losses': health.metrics.consecutive_losses,
                        'max_drawdown': health.metrics.max_drawdown,
                        'total_trades': health.metrics.total_trades
                    }
                },
                source='strategy_health_monitor'
            )
            self.event_manager.publish(event)
        
        self.logger.warning(f"Strategy {strategy_name} disabled due to {reason.name}")
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if strategy is enabled"""
        with self._lock:
            if strategy_name not in self.strategies:
                return True  # Default to enabled for new strategies
            
            health = self.strategies[strategy_name]
            
            # Check cooldown
            if health.status == StrategyStatus.COOLDOWN:
                if health.cooldown_until and datetime.now() >= health.cooldown_until:
                    health.status = StrategyStatus.ENABLED
                    health.is_enabled = True
                    health.cooldown_until = None
                    self._save_strategy_state(strategy_name)
            
            return health.is_enabled
    
    def enable_strategy(self, strategy_name: str, manual: bool = True) -> bool:
        """Enable a strategy"""
        with self._lock:
            if strategy_name not in self.strategies:
                self.register_strategy(strategy_name)
                return True
            
            health = self.strategies[strategy_name]
            
            # Check if in cooldown
            if health.status == StrategyStatus.COOLDOWN and not manual:
                self.logger.warning(f"Strategy {strategy_name} is in cooldown until {health.cooldown_until}")
                return False
            
            health.status = StrategyStatus.ENABLED
            health.is_enabled = True
            health.manual_override = manual
            health.disabled_at = None
            health.disabled_reason = None
            health.cooldown_until = None
            
            self._save_strategy_state(strategy_name)
            self.logger.info(f"Strategy {strategy_name} enabled (manual={manual})")
            
            return True
    
    def disable_strategy(self, strategy_name: str, reason: str = "manual") -> bool:
        """Manually disable a strategy"""
        with self._lock:
            if strategy_name not in self.strategies:
                self.register_strategy(strategy_name)
            
            self._disable_strategy(strategy_name, DisableReason.MANUAL_DISABLE)
            return True
    
    def reset_strategy_metrics(self, strategy_name: str) -> bool:
        """Reset performance metrics for a strategy"""
        with self._lock:
            if strategy_name not in self.strategies:
                return False
            
            health = self.strategies[strategy_name]
            health.metrics = StrategyMetrics()
            health.grace_trades_remaining = self.thresholds['grace_period_trades']
            health.status = StrategyStatus.GRACE_PERIOD
            
            self._save_strategy_state(strategy_name)
            self.logger.info(f"Reset metrics for strategy {strategy_name}")
            
            return True
    
    def get_strategy_health(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get health status for a strategy"""
        with self._lock:
            if strategy_name not in self.strategies:
                return None
            
            health = self.strategies[strategy_name]
            
            return {
                'strategy_name': strategy_name,
                'status': health.status.name,
                'is_enabled': health.is_enabled,
                'metrics': {
                    'total_trades': health.metrics.total_trades,
                    'win_rate': health.metrics.win_rate,
                    'consecutive_losses': health.metrics.consecutive_losses,
                    'max_drawdown': health.metrics.max_drawdown,
                    'sharpe_ratio': health.metrics.sharpe_ratio,
                    'total_pnl': health.metrics.total_pnl
                },
                'disabled_reason': health.disabled_reason.name if health.disabled_reason else None,
                'cooldown_until': health.cooldown_until.isoformat() if health.cooldown_until else None,
                'grace_trades_remaining': health.grace_trades_remaining
            }
    
    def get_all_strategies_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all strategies"""
        with self._lock:
            return {
                name: self.get_strategy_health(name)
                for name in self.strategies.keys()
            }
    
    def _save_strategy_state(self, strategy_name: str) -> None:
        """Save strategy state to database"""
        try:
            health = self.strategies[strategy_name]
            
            # Serialize metrics
            metrics_dict = {
                'total_trades': health.metrics.total_trades,
                'winning_trades': health.metrics.winning_trades,
                'losing_trades': health.metrics.losing_trades,
                'consecutive_losses': health.metrics.consecutive_losses,
                'consecutive_wins': health.metrics.consecutive_wins,
                'total_pnl': health.metrics.total_pnl,
                'max_drawdown': health.metrics.max_drawdown,
                'peak_equity': health.metrics.peak_equity,
                'sharpe_ratio': health.metrics.sharpe_ratio,
                'win_rate': health.metrics.win_rate,
                'avg_win': health.metrics.avg_win,
                'avg_loss': health.metrics.avg_loss,
                'last_trade_time': health.metrics.last_trade_time.isoformat() if health.metrics.last_trade_time else None
            }
            
            # Upsert to database
            query = """
            INSERT OR REPLACE INTO strategy_status (
                strategy_name, is_enabled, status, disabled_reason, 
                disabled_at, cooldown_until, manual_override, 
                performance_metrics, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = (
                strategy_name,
                health.is_enabled,
                health.status.name,
                health.disabled_reason.name if health.disabled_reason else None,
                health.disabled_at.isoformat() if health.disabled_at else None,
                health.cooldown_until.isoformat() if health.cooldown_until else None,
                health.manual_override,
                json.dumps(metrics_dict),
                datetime.now()
            )
            
            self.db_manager.execute(query, params)
            
        except Exception as e:
            self.logger.error(f"Error saving strategy state: {e}")
    
    def calculate_sharpe_ratio(self, strategy_name: str, returns: List[float]) -> float:
        """Calculate Sharpe ratio for strategy"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return 0.0
        
        # Annualized Sharpe ratio (assuming daily returns)
        sharpe = (avg_return / std_return) * np.sqrt(252)
        
        # Update strategy metrics
        with self._lock:
            if strategy_name in self.strategies:
                self.strategies[strategy_name].metrics.sharpe_ratio = sharpe
        
        return sharpe

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_health_monitor_instance: Optional[StrategyHealthMonitor] = None

def get_strategy_health_monitor(config: Optional[Dict[str, Any]] = None) -> StrategyHealthMonitor:
    """Get singleton instance of strategy health monitor"""
    global _health_monitor_instance
    if _health_monitor_instance is None:
        _health_monitor_instance = StrategyHealthMonitor(config)
    return _health_monitor_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the health monitor
    monitor = get_strategy_health_monitor({
        'min_win_rate': 0.35,
        'max_consecutive_losses': 5,
        'grace_period_trades': 10
    })
    
    # Register strategies
    monitor.register_strategy("IronCondor")
    monitor.register_strategy("ZeroDTE")
    
    # Simulate trades
    print("Simulating trades...")
    
    # Good performance for IronCondor
    for i in range(15):
        pnl = 100 if i % 3 != 0 else -50  # 66% win rate
        monitor.update_trade_result("IronCondor", pnl)
    
    # Poor performance for ZeroDTE
    for i in range(15):
        pnl = -100 if i < 8 else 50  # Many consecutive losses
        monitor.update_trade_result("ZeroDTE", pnl)
    
    # Check health
    print("\nStrategy Health Status:")
    for strategy, health in monitor.get_all_strategies_health().items():
        print(f"\n{strategy}:")
        print(f"  Status: {health['status']}")
        print(f"  Enabled: {health['is_enabled']}")
        print(f"  Win Rate: {health['metrics']['win_rate']:.2%}")
        print(f"  Consecutive Losses: {health['metrics']['consecutive_losses']}")
        print(f"  Total P&L: ${health['metrics']['total_pnl']:.2f}")
        if health['disabled_reason']:
            print(f"  Disabled Reason: {health['disabled_reason']}")
