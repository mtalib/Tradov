#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker 
Module: SpyderB15_PrometheusMetrics.py
Purpose: Prometheus metrics collection and HTTP endpoint with TradingMetrics
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-27 Time: 19:00:00  

Module Description:
    Centralized Prometheus metrics collection and HTTP endpoint for the Spyder
    trading system. Includes the missing TradingMetrics class that provides
    real-time trading performance monitoring, portfolio metrics, execution
    quality tracking, and risk management analytics. Integrates with all
    system components through callback registration.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import time
import queue
import json
import sys
import os
from typing import Dict, List, Optional, Callable, Any, Protocol, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from abc import ABC, abstractmethod
from collections import defaultdict, deque
import statistics

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# Prometheus client
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        start_http_server, CollectorRegistry, 
        generate_latest, CONTENT_TYPE_LATEST
    )
    import psutil
    HAS_PROMETHEUS = True
except ImportError:
    print("Warning: prometheus_client not available - metrics disabled")
    HAS_PROMETHEUS = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    HAS_LOCAL_IMPORTS = True
except ImportError:
    HAS_LOCAL_IMPORTS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default configuration
DEFAULT_METRICS_PORT = 9090
DEFAULT_COLLECTION_INTERVAL = 5.0  # seconds
DEFAULT_MAX_QUEUE_SIZE = 10000
DEFAULT_HOST = "0.0.0.0"

# Metric namespaces
NAMESPACE = "spyder"
SUBSYSTEM_GATEWAY = "gateway"
SUBSYSTEM_TRADING = "trading"
SUBSYSTEM_SYSTEM = "system"
SUBSYSTEM_MARKET = "market"

# Update intervals
UPDATE_INTERVAL = 10  # Metrics update interval (seconds)
TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

# Trading metrics constants
MAX_TRADE_HISTORY = 1000
PERFORMANCE_WINDOW_DAYS = 30
METRICS_RETENTION_HOURS = 24

# =============================================================================
# ENUMS FOR TRADING METRICS
# =============================================================================
class MetricPeriod(Enum):
    """Time periods for metrics aggregation"""
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class PerformanceStatus(Enum):
    """Performance status indicators"""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    CRITICAL = "critical"

class TradeStatus(Enum):
    """Trade execution status"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class ComponentHealth(Enum):
    """Component health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class MetricType(Enum):
    """Prometheus metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

# =============================================================================
# TRADING METRICS DATA STRUCTURES
# =============================================================================
@dataclass
class TradeMetrics:
    """Individual trade metrics"""
    trade_id: str
    symbol: str
    strategy: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    commission: float = 0.0
    duration: timedelta = timedelta(0)
    status: TradeStatus = TradeStatus.PENDING
    max_profit: float = 0.0
    max_loss: float = 0.0

@dataclass
class StrategyMetrics:
    """Performance metrics for individual trading strategies"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    average_duration: timedelta = timedelta(0)

@dataclass
class PortfolioMetrics:
    """Overall portfolio performance metrics"""
    timestamp: datetime
    total_value: float
    cash_balance: float
    positions_value: float
    daily_pnl: float
    total_pnl: float
    return_percent: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    beta: float = 0.0
    alpha: float = 0.0
    
@dataclass
class ExecutionMetrics:
    """Trade execution quality metrics"""
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    cancelled_orders: int = 0
    average_fill_time: float = 0.0
    average_slippage: float = 0.0
    total_commission: float = 0.0
    execution_rate: float = 0.0
    
@dataclass
class RiskMetrics:
    """Risk management metrics"""
    value_at_risk: float  # VaR
    conditional_var: float  # CVaR
    position_sizing_accuracy: float
    risk_reward_ratio: float
    kelly_percentage: float
    exposure_percent: float
    correlation_risk: float
    concentration_risk: float
    
@dataclass
class MetricsSnapshot:
    """Complete metrics snapshot at a point in time"""
    timestamp: datetime
    period: MetricPeriod
    portfolio: PortfolioMetrics
    strategies: Dict[str, StrategyMetrics]
    execution: ExecutionMetrics
    risk: RiskMetrics
    trades: List[TradeMetrics]
    performance_status: PerformanceStatus
    alerts: List[str] = field(default_factory=list)

@dataclass
class ClientMetrics:
    """Metrics for a specific IB client connection"""
    client_id: int
    purpose: str
    connected: bool = False
    uptime_seconds: float = 0.0
    latency_ms: float = 0.0
    error_count: int = 0
    reconnection_count: int = 0
    messages_processed: int = 0
    rate_limit_usage: float = 0.0

# =============================================================================
# MAIN TRADING METRICS CLASS
# =============================================================================
class TradingMetrics:
    """
    Real-time trading metrics system.
    
    This class collects, calculates, and monitors all trading metrics
    providing real-time insights into system performance.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        metrics_history: Historical metrics data
        current_trades: Active trades being tracked
        strategy_metrics: Metrics by strategy
        
    Example:
        >>> metrics = TradingMetrics()
        >>> metrics.start_monitoring()
        >>> snapshot = metrics.get_current_metrics()
    """
    
    def __init__(self):
        """Initialize the trading metrics system."""
        # Setup logging
        if HAS_LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
            
        # Core data structures
        self.current_trades: Dict[str, TradeMetrics] = {}
        self.completed_trades: deque = deque(maxlen=MAX_TRADE_HISTORY)
        self.strategy_metrics: Dict[str, StrategyMetrics] = {}
        self.metrics_history: deque = deque(maxlen=METRICS_RETENTION_HOURS * 12)  # 5min intervals
        
        # Portfolio state
        self.portfolio_value = 100000.0  # Starting value
        self.cash_balance = 100000.0
        self.positions_value = 0.0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        
        # Performance tracking
        self.performance_window: deque = deque(maxlen=PERFORMANCE_WINDOW_DAYS)
        self.drawdown_history: List[float] = []
        self.peak_portfolio_value = self.portfolio_value
        
        # Execution tracking
        self.execution_stats = {
            'total_orders': 0,
            'filled_orders': 0,
            'rejected_orders': 0,
            'cancelled_orders': 0,
            'fill_times': deque(maxlen=1000),
            'slippage_values': deque(maxlen=1000),
            'total_commission': 0.0
        }
        
        # Threading
        self.lock = threading.RLock()
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.logger.info("TradingMetrics initialized successfully")
    
    def start_monitoring(self) -> bool:
        """Start the metrics monitoring thread."""
        if self.running:
            self.logger.warning("TradingMetrics already running")
            return True
            
        try:
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="TradingMetrics-Monitor"
            )
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            self.logger.info("TradingMetrics monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start TradingMetrics monitoring: {e}")
            self.running = False
            return False
    
    def stop_monitoring(self):
        """Stop the metrics monitoring thread."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("TradingMetrics monitoring stopped")
    
    def add_trade(self, trade: TradeMetrics):
        """Add a new trade for monitoring."""
        with self.lock:
            self.current_trades[trade.trade_id] = trade
            self.logger.debug(f"Added trade {trade.trade_id} for monitoring")
    
    def update_trade(self, trade_id: str, **updates):
        """Update an existing trade's metrics."""
        with self.lock:
            if trade_id in self.current_trades:
                trade = self.current_trades[trade_id]
                for key, value in updates.items():
                    if hasattr(trade, key):
                        setattr(trade, key, value)
                
                # If trade is completed, move to completed trades
                if trade.status in [TradeStatus.FILLED, TradeStatus.CANCELLED, TradeStatus.REJECTED]:
                    self.completed_trades.append(trade)
                    del self.current_trades[trade_id]
                    self._update_strategy_metrics(trade)
                    
                self.logger.debug(f"Updated trade {trade_id}")
    
    def record_order_execution(self, filled: bool = True, fill_time_ms: float = 0, 
                             slippage: float = 0, commission: float = 0):
        """Record order execution statistics."""
        with self.lock:
            self.execution_stats['total_orders'] += 1
            
            if filled:
                self.execution_stats['filled_orders'] += 1
                if fill_time_ms > 0:
                    self.execution_stats['fill_times'].append(fill_time_ms)
                if slippage != 0:
                    self.execution_stats['slippage_values'].append(abs(slippage))
                self.execution_stats['total_commission'] += commission
            else:
                self.execution_stats['rejected_orders'] += 1
    
    def update_portfolio(self, total_value: float, cash: float, positions_value: float):
        """Update portfolio values."""
        with self.lock:
            old_value = self.portfolio_value
            self.portfolio_value = total_value
            self.cash_balance = cash
            self.positions_value = positions_value
            
            # Update daily P&L
            if old_value > 0:
                self.daily_pnl = total_value - old_value
                self.total_pnl += self.daily_pnl
            
            # Track drawdown
            if total_value > self.peak_portfolio_value:
                self.peak_portfolio_value = total_value
            
            current_drawdown = (self.peak_portfolio_value - total_value) / self.peak_portfolio_value
            self.drawdown_history.append(current_drawdown)
            
            self.logger.debug(f"Portfolio updated: ${total_value:,.2f}")
    
    def get_current_metrics(self, period: MetricPeriod = MetricPeriod.REALTIME) -> MetricsSnapshot:
        """Get current metrics snapshot."""
        with self.lock:
            # Calculate portfolio metrics
            portfolio_metrics = self._calculate_portfolio_metrics()
            
            # Calculate strategy metrics
            strategy_metrics = dict(self.strategy_metrics)
            
            # Calculate execution metrics
            execution_metrics = self._calculate_execution_metrics()
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics()
            
            # Determine performance status
            performance_status = self._assess_performance_status()
            
            # Get recent trades
            recent_trades = list(self.completed_trades)[-50:]  # Last 50 trades
            
            snapshot = MetricsSnapshot(
                timestamp=datetime.now(),
                period=period,
                portfolio=portfolio_metrics,
                strategies=strategy_metrics,
                execution=execution_metrics,
                risk=risk_metrics,
                trades=recent_trades,
                performance_status=performance_status
            )
            
            # Store in history
            self.metrics_history.append(snapshot)
            
            return snapshot
    
    def get_strategy_performance(self, strategy_name: str) -> Optional[StrategyMetrics]:
        """Get performance metrics for a specific strategy."""
        with self.lock:
            return self.strategy_metrics.get(strategy_name)
    
    def get_portfolio_summary(self) -> Dict[str, float]:
        """Get portfolio summary statistics."""
        with self.lock:
            return {
                'total_value': self.portfolio_value,
                'cash_balance': self.cash_balance,
                'positions_value': self.positions_value,
                'daily_pnl': self.daily_pnl,
                'total_pnl': self.total_pnl,
                'return_percent': (self.total_pnl / 100000.0) * 100 if self.total_pnl else 0.0,
                'max_drawdown': max(self.drawdown_history) * 100 if self.drawdown_history else 0.0,
                'current_drawdown': self.drawdown_history[-1] * 100 if self.drawdown_history else 0.0
            }
    
    def _monitoring_loop(self):
        """Main monitoring loop running in separate thread."""
        while self.running:
            try:
                # Update metrics every 5 minutes
                self.get_current_metrics()
                
                # Sleep with ability to wake up for shutdown
                for _ in range(300):  # 5 minutes = 300 seconds
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in metrics monitoring loop: {e}")
                if self.error_handler:
                    self.error_handler.handle_exception(e)
                time.sleep(60)  # Wait 1 minute on error
    
    def _update_strategy_metrics(self, trade: TradeMetrics):
        """Update strategy-specific metrics when trade completes."""
        strategy_name = trade.strategy
        
        if strategy_name not in self.strategy_metrics:
            self.strategy_metrics[strategy_name] = StrategyMetrics(strategy_name=strategy_name)
        
        metrics = self.strategy_metrics[strategy_name]
        metrics.total_trades += 1
        
        if trade.pnl > 0:
            metrics.winning_trades += 1
            metrics.consecutive_wins += 1
            metrics.consecutive_losses = 0
            if trade.pnl > metrics.best_trade:
                metrics.best_trade = trade.pnl
        else:
            metrics.losing_trades += 1
            metrics.consecutive_losses += 1
            metrics.consecutive_wins = 0
            if trade.pnl < metrics.worst_trade:
                metrics.worst_trade = trade.pnl
        
        metrics.total_pnl += trade.pnl
        metrics.win_rate = metrics.winning_trades / metrics.total_trades
        
        # Calculate averages
        if metrics.winning_trades > 0:
            winning_pnls = [t.pnl for t in self.completed_trades 
                          if t.strategy == strategy_name and t.pnl > 0]
            metrics.average_win = statistics.mean(winning_pnls) if winning_pnls else 0
        
        if metrics.losing_trades > 0:
            losing_pnls = [abs(t.pnl) for t in self.completed_trades 
                         if t.strategy == strategy_name and t.pnl < 0]
            metrics.average_loss = statistics.mean(losing_pnls) if losing_pnls else 0
        
        # Calculate profit factor
        if metrics.average_loss > 0:
            metrics.profit_factor = (metrics.average_win * metrics.winning_trades) / (metrics.average_loss * metrics.losing_trades)
    
    def _calculate_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate current portfolio metrics."""
        return_pct = (self.total_pnl / 100000.0) * 100 if self.total_pnl else 0.0
        max_dd = max(self.drawdown_history) * 100 if self.drawdown_history else 0.0
        current_dd = self.drawdown_history[-1] * 100 if self.drawdown_history else 0.0
        
        return PortfolioMetrics(
            timestamp=datetime.now(),
            total_value=self.portfolio_value,
            cash_balance=self.cash_balance,
            positions_value=self.positions_value,
            daily_pnl=self.daily_pnl,
            total_pnl=self.total_pnl,
            return_percent=return_pct,
            volatility=0.0,  # Would need price history to calculate
            sharpe_ratio=0.0,  # Would need risk-free rate and return history
            sortino_ratio=0.0,  # Would need downside deviation
            calmar_ratio=0.0,  # Would need annual return / max drawdown
            max_drawdown=max_dd,
            current_drawdown=current_dd
        )
    
    def _calculate_execution_metrics(self) -> ExecutionMetrics:
        """Calculate execution quality metrics."""
        stats = self.execution_stats
        total_orders = stats['total_orders']
        filled_orders = stats['filled_orders']
        
        avg_fill_time = statistics.mean(stats['fill_times']) if stats['fill_times'] else 0.0
        avg_slippage = statistics.mean(stats['slippage_values']) if stats['slippage_values'] else 0.0
        execution_rate = (filled_orders / total_orders) * 100 if total_orders > 0 else 0.0
        
        return ExecutionMetrics(
            total_orders=total_orders,
            filled_orders=filled_orders,
            rejected_orders=stats['rejected_orders'],
            cancelled_orders=stats['cancelled_orders'],
            average_fill_time=avg_fill_time,
            average_slippage=avg_slippage,
            total_commission=stats['total_commission'],
            execution_rate=execution_rate
        )
    
    def _calculate_risk_metrics(self) -> RiskMetrics:
        """Calculate risk management metrics."""
        # Simplified risk metrics - would need more data for full calculation
        exposure_pct = (self.positions_value / self.portfolio_value) * 100 if self.portfolio_value > 0 else 0.0
        
        return RiskMetrics(
            value_at_risk=0.0,  # Would need historical returns
            conditional_var=0.0,  # Would need tail risk calculation
            position_sizing_accuracy=0.0,  # Would need target vs actual position sizes
            risk_reward_ratio=0.0,  # Would need risk/reward analysis
            kelly_percentage=0.0,  # Would need win rate and avg win/loss
            exposure_percent=exposure_pct,
            correlation_risk=0.0,  # Would need correlation matrix
            concentration_risk=0.0  # Would need position concentration analysis
        )
    
    def _assess_performance_status(self) -> PerformanceStatus:
        """Assess overall performance status."""
        if not self.strategy_metrics:
            return PerformanceStatus.AVERAGE
        
        # Simple assessment based on total P&L and drawdown
        return_pct = (self.total_pnl / 100000.0) * 100
        max_dd = max(self.drawdown_history) * 100 if self.drawdown_history else 0.0
        
        if return_pct > 10 and max_dd < 5:
            return PerformanceStatus.EXCELLENT
        elif return_pct > 5 and max_dd < 10:
            return PerformanceStatus.GOOD
        elif return_pct > 0 and max_dd < 15:
            return PerformanceStatus.AVERAGE
        elif return_pct > -5 and max_dd < 20:
            return PerformanceStatus.POOR
        else:
            return PerformanceStatus.CRITICAL

# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================
@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_METRICS_PORT
    collection_interval: float = DEFAULT_COLLECTION_INTERVAL
    max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE
    enable_system_metrics: bool = True
    enable_trading_metrics: bool = True
    enable_market_metrics: bool = True
    enable_gateway_metrics: bool = True
    enable_debug_logging: bool = False

if HAS_PROMETHEUS:
    class SpyderMetrics:
        """Centralized Prometheus metrics definitions"""
        
        def __init__(self, registry: Optional[CollectorRegistry] = None):
            """Initialize metrics with optional custom registry"""
            self.registry = registry or CollectorRegistry()
            self._initialize_metrics()
        
        def _initialize_metrics(self):
            """Initialize all Prometheus metrics"""
            
            # System Information
            self.system_info = Info(
                "spyder_system_info", 
                "System information", 
                registry=self.registry
            )
            
            # Gateway Connection Metrics
            self.gateway_connected = Gauge(
                "gateway_connected",
                "Gateway connection status (1=connected, 0=disconnected)",
                ["client_id", "purpose"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_GATEWAY,
                registry=self.registry
            )
            
            # Trading Metrics
            self.portfolio_value = Gauge(
                "portfolio_value_usd",
                "Total portfolio value in USD",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )
            
            self.daily_pnl = Gauge(
                "daily_pnl_usd",
                "Daily profit and loss in USD",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )
            
            self.position_count = Gauge(
                "position_count",
                "Number of open positions",
                ["symbol"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )
            
            # System Metrics
            self.system_cpu_usage = Gauge(
                "system_cpu_usage_percent",
                "System CPU usage percentage",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_SYSTEM,
                registry=self.registry
            )
            
            self.system_memory_usage = Gauge(
                "system_memory_usage_percent",
                "System memory usage percentage",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_SYSTEM,
                registry=self.registry
            )

# =============================================================================
# PROMETHEUS METRICS COLLECTOR
# =============================================================================
class PrometheusMetricsCollector:
    """
    Centralized Prometheus metrics collector for the Spyder system.
    
    Collects metrics from all system components and exposes them via HTTP endpoint.
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        """Initialize the metrics collector."""
        self.config = config or MetricsConfig()
        
        # Setup logging
        if HAS_LOCAL_IMPORTS:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
        # Core components
        self.trading_metrics = TradingMetrics()
        self.registry = CollectorRegistry() if HAS_PROMETHEUS else None
        self.metrics = SpyderMetrics(self.registry) if HAS_PROMETHEUS else None
        self.http_server = None
        
        # State management
        self.running = False
        self.collection_thread: Optional[threading.Thread] = None
        
        self.logger.info(f"PrometheusMetricsCollector initialized on port {self.config.port}")
    
    def start(self) -> bool:
        """Start the metrics collection and HTTP server."""
        if not HAS_PROMETHEUS:
            self.logger.error("Prometheus client not available - cannot start metrics")
            return False
            
        try:
            # Start TradingMetrics monitoring
            if not self.trading_metrics.start_monitoring():
                self.logger.error("Failed to start TradingMetrics monitoring")
                return False
            
            # Start HTTP server
            self.http_server = start_http_server(
                self.config.port, 
                addr=self.config.host,
                registry=self.registry
            )
            
            self.running = True
            self.logger.info(f"Metrics HTTP server started on {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start metrics collector: {e}")
            return False
    
    def stop(self):
        """Stop the metrics collector."""
        self.running = False
        
        # Stop TradingMetrics
        self.trading_metrics.stop_monitoring()
        
        # Note: prometheus_client doesn't provide a clean way to stop the HTTP server
        self.logger.info("Metrics collector stopped")
    
    def get_trading_metrics(self) -> TradingMetrics:
        """Get the TradingMetrics instance."""
        return self.trading_metrics

# =============================================================================
# MODULE EXPORTS
# =============================================================================
__all__ = [
    # Main classes - CRITICAL FOR IMPORTS
    "TradingMetrics",
    "PrometheusMetricsCollector",
    
    # Data classes
    "TradeMetrics",
    "StrategyMetrics", 
    "PortfolioMetrics",
    "ExecutionMetrics",
    "RiskMetrics",
    "MetricsSnapshot",
    "ClientMetrics",
    "MetricsConfig",
    
    # Enums
    "MetricPeriod",
    "PerformanceStatus",
    "TradeStatus",
    "ComponentHealth",
    "MetricType",
]

# =============================================================================
# STANDALONE EXECUTION
# =============================================================================
if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting Spyder Prometheus Metrics Collector")
    
    try:
        # Create and start metrics collector
        collector = PrometheusMetricsCollector()
        
        if collector.start():
            logger.info("Metrics collector started successfully")
            logger.info(f"Metrics available at: http://localhost:{collector.config.port}/metrics")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
        else:
            logger.error("Failed to start metrics collector")
            
    except Exception as e:
        logger.error(f"Critical error: {e}")
        
    finally:
        logger.info("Shutting down metrics collector")
        if 'collector' in locals():
            collector.stop()
