#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB15_PrometheusMetrics.py
Purpose: Comprehensive Prometheus metrics collection and monitoring
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-11 Time: 16:30:00

Module Description:
    Centralized Prometheus metrics collection and HTTP endpoint for the Spyder
    trading system. Provides real-time monitoring of trading performance, system
    health, client connections, and risk metrics. Essential for production
    monitoring, alerting, and performance optimization of the autonomous
    trading system.

Key Features:
    - Real-time trading metrics (P&L, positions, executions)
    - System performance monitoring (CPU, memory, latency)
    - Multi-client connection tracking (all 10 clients)
    - Risk management metrics and alerts
    - HTTP endpoint for Prometheus scraping
    - Dashboard integration support
    - Performance analytics and trend analysis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import statistics
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from collections.abc import Callable

# ==============================================================================
# THIRD-PARTY IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,  # noqa: F401
        start_http_server, CollectorRegistry,
        generate_latest, CONTENT_TYPE_LATEST,  # noqa: F401
        REGISTRY
    )
    HAS_PROMETHEUS = True
except ImportError:
    logging.info("WARNING: prometheus_client not available - metrics collection disabled")
    HAS_PROMETHEUS = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    logging.info("WARNING: psutil not available - system metrics limited")
    HAS_PSUTIL = False

# ==============================================================================
# LOCAL IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError:
    logging.info("WARNING: SpyderLogger not available - using basic logging")
    import logging
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

try:
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    logging.info("WARNING: SpyderErrorHandler not available - using basic error handling")
    class SpyderErrorHandler:
        def handle_error(self, error, context=""):
            logging.info("ERROR in %s: %s", context, error)

try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    HAS_EVENT_MANAGER = True
except ImportError:
    logging.info("WARNING: EventManager not available - no event notifications")
    HAS_EVENT_MANAGER = False
    class EventManager:
        def emit_event(self, event): pass
    class Event:
        def __init__(self, event_type, data=None): pass
    class EventType:
        METRICS_UPDATED = "metrics_updated"

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Prometheus configuration
DEFAULT_HOST = "0.0.0.0"
DEFAULT_METRICS_PORT = 9090
DEFAULT_COLLECTION_INTERVAL = 10.0  # seconds
DEFAULT_MAX_QUEUE_SIZE = 1000

# Namespace and subsystem labels
NAMESPACE = "spyder"
SUBSYSTEM_GATEWAY = "gateway"
SUBSYSTEM_TRADING = "trading"
SUBSYSTEM_SYSTEM = "system"
SUBSYSTEM_RISK = "risk"
SUBSYSTEM_MARKET = "market"

# Client configuration
CLIENT_COUNT = 10
CLIENT_ID_RANGE = range(1, CLIENT_COUNT + 1)

# Performance thresholds
LATENCY_WARNING_MS = 50
LATENCY_CRITICAL_MS = 100
CPU_WARNING_PERCENT = 70
CPU_CRITICAL_PERCENT = 85
MEMORY_WARNING_PERCENT = 80
MEMORY_CRITICAL_PERCENT = 90

# Trading thresholds
DAILY_PNL_WARNING = -5000.0  # $5K daily loss warning
DAILY_PNL_CRITICAL = -10000.0  # $10K daily loss critical
MAX_POSITION_SIZE = 1000000.0  # $1M max position size

# ==============================================================================
# ENUMS
# ==============================================================================

class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"

class MetricPeriod(Enum):
    """Time periods for metric aggregation."""
    REAL_TIME = "real_time"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

class PerformanceStatus(Enum):
    """Performance status levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    CRITICAL = "critical"

class TradeStatus(Enum):
    """Trade execution status."""
    PENDING = "pending"
    EXECUTED = "executed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    FAILED = "failed"

class ComponentHealth(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"
    UNKNOWN = "unknown"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class TradeMetrics:
    """Individual trade performance metrics."""
    trade_id: str
    symbol: str
    strategy: str
    entry_time: datetime
    exit_time: datetime | None = None

    # Financial metrics
    quantity: float = 0.0
    entry_price: float = 0.0
    exit_price: float | None = None
    realized_pnl: float = 0.0
    commission: float = 0.0

    # Execution metrics
    fill_time_ms: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0

    # Status
    status: TradeStatus = TradeStatus.PENDING

@dataclass
class StrategyMetrics:
    """Strategy performance metrics."""
    strategy_name: str

    # Performance metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0

    # Risk metrics
    max_position_size: float = 0.0
    current_exposure: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%

    # Timing
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics."""
    # Portfolio value
    total_value: float = 0.0
    cash_balance: float = 0.0
    equity_value: float = 0.0
    options_value: float = 0.0

    # P&L metrics
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Risk metrics
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0

    # Position metrics
    long_positions: int = 0
    short_positions: int = 0
    total_positions: int = 0

    # Performance
    return_today: float = 0.0
    return_mtd: float = 0.0
    return_ytd: float = 0.0

    # Timestamps
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class ExecutionMetrics:
    """Order execution quality metrics."""
    # Volume metrics
    total_volume: float = 0.0
    avg_order_size: float = 0.0

    # Timing metrics
    avg_fill_time_ms: float = 0.0
    fastest_fill_ms: float = 0.0
    slowest_fill_ms: float = 0.0

    # Quality metrics
    avg_slippage_bps: float = 0.0
    fill_rate: float = 0.0
    rejection_rate: float = 0.0

    # Market impact
    avg_market_impact_bps: float = 0.0
    large_order_impact_bps: float = 0.0

    # Counts
    total_orders: int = 0
    filled_orders: int = 0
    cancelled_orders: int = 0
    rejected_orders: int = 0

@dataclass
class RiskMetrics:
    """Risk management metrics."""
    # Exposure metrics
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0

    # Concentration risk
    max_single_position_pct: float = 0.0
    top_5_positions_pct: float = 0.0

    # Drawdown tracking
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    drawdown_duration_days: int = 0

    # Risk limits
    var_95_1day: float = 0.0
    var_99_1day: float = 0.0
    expected_shortfall: float = 0.0

    # Stress test results
    stress_test_pnl: dict[str, float] = field(default_factory=dict)

    # Alert counts
    risk_alerts_24h: int = 0
    limit_breaches_24h: int = 0

@dataclass
class ClientMetrics:
    """Individual client connection metrics."""
    client_id: int

    # Connection metrics
    is_connected: bool = False
    connection_uptime_seconds: float = 0.0
    reconnection_count: int = 0

    # Performance metrics
    latency_ms: float = 0.0
    throughput_ops_per_sec: float = 0.0
    error_rate_percent: float = 0.0

    # Activity metrics
    api_calls_per_minute: float = 0.0
    data_requests_per_minute: float = 0.0
    order_requests_per_minute: float = 0.0

    # Status
    health_status: ComponentHealth = ComponentHealth.UNKNOWN
    last_error: str | None = None
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class MetricsSnapshot:
    """Complete metrics snapshot for a point in time."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Core metrics
    portfolio: PortfolioMetrics = field(default_factory=PortfolioMetrics)
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    risk: RiskMetrics = field(default_factory=RiskMetrics)

    # Strategy metrics
    strategy_metrics: dict[str, StrategyMetrics] = field(default_factory=dict)

    # Client metrics
    client_metrics: dict[int, ClientMetrics] = field(default_factory=dict)

    # System metrics
    system_cpu_percent: float = 0.0
    system_memory_percent: float = 0.0
    system_disk_percent: float = 0.0
    system_load_avg: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Overall health
    overall_health: ComponentHealth = ComponentHealth.UNKNOWN
    performance_status: PerformanceStatus = PerformanceStatus.AVERAGE

@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    # Server settings
    host: str = DEFAULT_HOST
    port: int = DEFAULT_METRICS_PORT

    # Collection settings
    collection_interval: float = DEFAULT_COLLECTION_INTERVAL
    max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE

    # Feature flags
    enable_system_metrics: bool = True
    enable_trading_metrics: bool = True
    enable_market_metrics: bool = True
    enable_gateway_metrics: bool = True
    enable_risk_metrics: bool = True

    # Storage settings
    retention_days: int = 30
    enable_persistent_storage: bool = False
    storage_path: str | None = None

    # Debug settings
    enable_debug_logging: bool = False
    log_level: str = "INFO"

# ==============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ==============================================================================

if HAS_PROMETHEUS:
    class SpyderMetrics:
        """Centralized Prometheus metrics definitions."""

        def __init__(self, registry: CollectorRegistry | None = None):
            """Initialize metrics with optional custom registry."""
            self.registry = registry or REGISTRY
            self._initialize_metrics()

        def _initialize_metrics(self):
            """Initialize all Prometheus metrics."""

            # =================================================================
            # SYSTEM INFORMATION
            # =================================================================
            self.system_info = Info(
                "system_info",
                "System information",
                namespace=NAMESPACE,
                registry=self.registry
            )

            # =================================================================
            # GATEWAY CONNECTION METRICS
            # =================================================================
            self.gateway_connected = Gauge(
                "gateway_connected",
                "Gateway connection status (1=connected, 0=disconnected)",
                ["client_id", "purpose"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_GATEWAY,
                registry=self.registry
            )

            self.gateway_latency = Histogram(
                "gateway_latency_ms",
                "Gateway response latency in milliseconds",
                ["client_id"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_GATEWAY,
                registry=self.registry
            )

            self.gateway_errors = Counter(
                "gateway_errors_total",
                "Total gateway errors",
                ["client_id", "error_type"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_GATEWAY,
                registry=self.registry
            )

            self.gateway_reconnections = Counter(
                "gateway_reconnections_total",
                "Total gateway reconnections",
                ["client_id"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_GATEWAY,
                registry=self.registry
            )

            # =================================================================
            # TRADING METRICS
            # =================================================================
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

            self.unrealized_pnl = Gauge(
                "unrealized_pnl_usd",
                "Unrealized profit and loss in USD",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.position_count = Gauge(
                "position_count",
                "Number of open positions",
                ["symbol", "strategy"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.trades_executed = Counter(
                "trades_executed_total",
                "Total trades executed",
                ["symbol", "strategy", "side"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.order_fill_time = Histogram(
                "order_fill_time_ms",
                "Order fill time in milliseconds",
                ["symbol", "order_type"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.slippage = Histogram(
                "slippage_bps",
                "Order slippage in basis points",
                ["symbol", "order_type"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            # =================================================================
            # RISK METRICS
            # =================================================================
            self.portfolio_delta = Gauge(
                "portfolio_delta",
                "Total portfolio delta",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.portfolio_gamma = Gauge(
                "portfolio_gamma",
                "Total portfolio gamma",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.portfolio_theta = Gauge(
                "portfolio_theta",
                "Total portfolio theta",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.portfolio_vega = Gauge(
                "portfolio_vega",
                "Total portfolio vega",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.var_95 = Gauge(
                "var_95_usd",
                "Value at Risk 95% in USD",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.max_drawdown = Gauge(
                "max_drawdown_percent",
                "Maximum drawdown percentage",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            self.leverage = Gauge(
                "leverage_ratio",
                "Portfolio leverage ratio",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            # =================================================================
            # SYSTEM METRICS
            # =================================================================
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

            self.system_disk_usage = Gauge(
                "system_disk_usage_percent",
                "System disk usage percentage",
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_SYSTEM,
                registry=self.registry
            )

            self.system_load_avg = Gauge(
                "system_load_avg",
                "System load average",
                ["period"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_SYSTEM,
                registry=self.registry
            )

            # =================================================================
            # STRATEGY METRICS
            # =================================================================
            self.strategy_pnl = Gauge(
                "strategy_pnl_usd",
                "Strategy profit and loss in USD",
                ["strategy"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.strategy_trades = Counter(
                "strategy_trades_total",
                "Total trades per strategy",
                ["strategy", "outcome"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            self.strategy_win_rate = Gauge(
                "strategy_win_rate_percent",
                "Strategy win rate percentage",
                ["strategy"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            # =================================================================
            # STRATEGY P&L BY REGIME
            # =================================================================
            self.strategy_pnl_by_regime = Histogram(
                "strategy_pnl_by_regime_dollars",
                "Strategy P&L in dollars, labeled by strategy and market regime",
                ["strategy_id", "regime"],
                buckets=[-500, -200, -100, -50, -20, 0, 20, 50, 100, 200, 500, 1000],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            # =================================================================
            # ORDER FILL LATENCY
            # =================================================================
            self.order_fill_latency_ms = Histogram(
                "order_fill_latency_milliseconds",
                "Time from order submission to fill confirmation in milliseconds",
                ["order_type", "symbol"],
                buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_TRADING,
                registry=self.registry
            )

            # =================================================================
            # RISK BREACH COUNTER
            # =================================================================
            self.risk_breach_total = Counter(
                "risk_breach_total",
                "Total number of risk limit breaches by type",
                ["breach_type", "severity"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            # =================================================================
            # RISK SIGNAL REJECTION COUNTER
            # =================================================================
            self.risk_rejections_total = Counter(
                "risk_rejections_total",
                "Total strategy signals rejected by the E-Series risk gate",
                ["strategy", "rejection_reason"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_RISK,
                registry=self.registry
            )

            # =================================================================
            # REGIME CLASSIFICATION CONFIDENCE
            # =================================================================
            self.regime_classification_confidence = Gauge(
                "regime_classification_confidence",
                "Current confidence score of market regime classification (0.0-1.0)",
                ["regime_type", "detector"],
                namespace=NAMESPACE,
                subsystem=SUBSYSTEM_MARKET,
                registry=self.registry
            )

# ==============================================================================
# TRADING METRICS CLASS
# ==============================================================================

class TradingMetrics:
    """
    Comprehensive trading metrics collection and analysis.

    Tracks all trading activity, performance metrics, and provides
    real-time analytics for the autonomous trading system.
    """

    def __init__(self):
        """Initialize trading metrics."""
        self.logger = SpyderLogger.get_logger(__name__)

        # Current snapshot
        self.current_snapshot = MetricsSnapshot()

        # Historical data
        self.trade_history: list[TradeMetrics] = []
        self.snapshot_history: deque = deque(maxlen=1440)  # 24 hours at 1-minute intervals
        self.daily_snapshots: deque = deque(maxlen=365)    # 1 year of daily snapshots

        # Performance tracking
        self.drawdown_history: deque = deque(maxlen=1000)
        self.pnl_history: deque = deque(maxlen=1000)

        # Event callbacks
        self._update_callbacks: list[Callable] = []
        self._alert_callbacks: list[Callable] = []

        # State
        self._is_running = False
        self._last_update = datetime.now(timezone.utc)

        self.logger.info("TradingMetrics initialized")

    def start_monitoring(self):
        """Start metrics monitoring."""
        self._is_running = True
        self.logger.info("Trading metrics monitoring started")

    def stop_monitoring(self):
        """Stop metrics monitoring."""
        self._is_running = False
        self.logger.info("Trading metrics monitoring stopped")

    def record_trade(self, trade: TradeMetrics):
        """Record a trade execution."""
        self.trade_history.append(trade)

        # Update current metrics
        if trade.status == TradeStatus.EXECUTED:
            self._update_from_trade(trade)

        self.logger.debug("Recorded trade: %s", trade.trade_id)

    def update_portfolio_value(self, total_value: float, cash_balance: float):
        """Update portfolio value metrics."""
        self.current_snapshot.portfolio.total_value = total_value
        self.current_snapshot.portfolio.cash_balance = cash_balance
        self.current_snapshot.portfolio.equity_value = total_value - cash_balance
        self.current_snapshot.portfolio.last_updated = datetime.now(timezone.utc)

    def update_positions(self, positions: list[dict[str, Any]]):
        """Update position metrics from position data."""
        portfolio = self.current_snapshot.portfolio

        portfolio.long_positions = sum(1 for p in positions if p.get('quantity', 0) > 0)
        portfolio.short_positions = sum(1 for p in positions if p.get('quantity', 0) < 0)
        portfolio.total_positions = len(positions)

        # Calculate Greeks
        portfolio.total_delta = sum(p.get('delta', 0) for p in positions)
        portfolio.total_gamma = sum(p.get('gamma', 0) for p in positions)
        portfolio.total_theta = sum(p.get('theta', 0) for p in positions)
        portfolio.total_vega = sum(p.get('vega', 0) for p in positions)

        # Calculate unrealized P&L
        portfolio.unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)

    def update_daily_pnl(self, daily_pnl: float):
        """Update daily P&L."""
        self.current_snapshot.portfolio.daily_pnl = daily_pnl
        self.current_snapshot.portfolio.return_today = (
            daily_pnl / max(1.0, self.current_snapshot.portfolio.total_value) * 100
        )

        # Track P&L history
        self.pnl_history.append(daily_pnl)

        # Calculate drawdown
        self._update_drawdown()

    def update_execution_metrics(self, fill_time_ms: float, slippage_bps: float,
                               order_type: str = "market"):
        """Update execution quality metrics."""
        execution = self.current_snapshot.execution

        # Update timing metrics
        if execution.total_orders == 0:
            execution.avg_fill_time_ms = fill_time_ms
            execution.fastest_fill_ms = fill_time_ms
            execution.slowest_fill_ms = fill_time_ms
        else:
            execution.avg_fill_time_ms = (
                (execution.avg_fill_time_ms * execution.total_orders + fill_time_ms) /
                (execution.total_orders + 1)
            )
            execution.fastest_fill_ms = min(execution.fastest_fill_ms, fill_time_ms)
            execution.slowest_fill_ms = max(execution.slowest_fill_ms, fill_time_ms)

        # Update slippage
        if execution.total_orders == 0:
            execution.avg_slippage_bps = slippage_bps
        else:
            execution.avg_slippage_bps = (
                (execution.avg_slippage_bps * execution.total_orders + slippage_bps) /
                (execution.total_orders + 1)
            )

        execution.total_orders += 1
        execution.filled_orders += 1
        execution.fill_rate = execution.filled_orders / execution.total_orders * 100

    def register_update_callback(self, callback: Callable):
        """Register callback for metrics updates."""
        self._update_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable):
        """Register callback for alert notifications."""
        self._alert_callbacks.append(callback)

    def get_current_snapshot(self) -> MetricsSnapshot:
        """Get current metrics snapshot."""
        return self.current_snapshot

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        portfolio = self.current_snapshot.portfolio

        return {
            'total_value': portfolio.total_value,
            'daily_pnl': portfolio.daily_pnl,
            'daily_return_pct': portfolio.return_today,
            'total_positions': portfolio.total_positions,
            'unrealized_pnl': portfolio.unrealized_pnl,
            'max_drawdown': max(self.drawdown_history) if self.drawdown_history else 0.0,
            'total_trades': len(self.trade_history),
            'win_rate': self._calculate_win_rate(),
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'performance_status': self._assess_performance_status().value
        }

    def _update_from_trade(self, trade: TradeMetrics):
        """Update metrics from a completed trade."""
        # Update portfolio realized P&L
        self.current_snapshot.portfolio.realized_pnl += trade.realized_pnl

        # Update strategy metrics
        strategy_name = trade.strategy
        if strategy_name not in self.current_snapshot.strategy_metrics:
            self.current_snapshot.strategy_metrics[strategy_name] = StrategyMetrics(strategy_name)

        strategy = self.current_snapshot.strategy_metrics[strategy_name]
        strategy.total_trades += 1
        strategy.total_pnl += trade.realized_pnl

        if trade.realized_pnl > 0:
            strategy.winning_trades += 1
        else:
            strategy.losing_trades += 1

        strategy.win_rate = strategy.winning_trades / strategy.total_trades * 100
        strategy.last_updated = datetime.now(timezone.utc)

    def _update_drawdown(self):
        """Update drawdown calculations."""
        if not self.pnl_history:
            return

        # Calculate running maximum
        running_max = self.pnl_history[0]
        current_drawdown = 0.0

        for pnl in self.pnl_history:
            running_max = max(running_max, pnl)
            drawdown = (pnl - running_max) / max(1.0, abs(running_max)) * 100
            current_drawdown = min(current_drawdown, drawdown)

        self.current_snapshot.risk.current_drawdown = current_drawdown
        self.drawdown_history.append(abs(current_drawdown))

        if self.drawdown_history:
            self.current_snapshot.risk.max_drawdown = max(self.drawdown_history)

    def _calculate_win_rate(self) -> float:
        """Calculate overall win rate."""
        if not self.trade_history:
            return 0.0

        winning_trades = sum(1 for trade in self.trade_history if trade.realized_pnl > 0)
        return winning_trades / len(self.trade_history) * 100

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(self.pnl_history) < 2:
            return 0.0

        returns = list(self.pnl_history)
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        if std_return == 0:
            return 0.0

        return (mean_return - risk_free_rate) / std_return

    def _assess_performance_status(self) -> PerformanceStatus:
        """Assess current performance status."""
        daily_pnl = self.current_snapshot.portfolio.daily_pnl
        max_dd = max(self.drawdown_history) if self.drawdown_history else 0.0

        if daily_pnl > 5000 and max_dd < 2:
            return PerformanceStatus.EXCELLENT
        elif daily_pnl > 1000 and max_dd < 5:
            return PerformanceStatus.GOOD
        elif daily_pnl > 0 and max_dd < 10:
            return PerformanceStatus.AVERAGE
        elif daily_pnl > -5000 and max_dd < 15:
            return PerformanceStatus.POOR
        else:
            return PerformanceStatus.CRITICAL

# ==============================================================================
# PROMETHEUS METRICS COLLECTOR
# ==============================================================================

class PrometheusMetricsCollector:
    """
    Centralized Prometheus metrics collector for the Spyder system.

    Collects metrics from all system components and exposes them via HTTP endpoint.
    """

    def __init__(self, config: MetricsConfig | None = None):
        """Initialize the metrics collector."""
        self.config = config or MetricsConfig()
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Core components
        self.trading_metrics = TradingMetrics()
        self.registry = CollectorRegistry() if HAS_PROMETHEUS else None
        self.metrics = SpyderMetrics(self.registry) if HAS_PROMETHEUS else None

        # HTTP server
        self.http_server = None

        # State management
        self.running = False
        self.collection_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # System metrics tracking
        self._last_system_update = datetime.now(timezone.utc)
        self._system_metrics_interval = 30.0  # seconds

        self.logger.info("PrometheusMetricsCollector initialized on port %s", self.config.port)

    def start(self) -> bool:
        """Start the metrics collection and HTTP server."""
        try:
            if self.running:
                self.logger.warning("Metrics collector is already running")
                return True

            if not HAS_PROMETHEUS:
                self.logger.warning("Prometheus client not available - metrics disabled")
                return False

            self.logger.info("Starting Prometheus metrics collector...")

            # Start HTTP server
            try:
                self.http_server = start_http_server(
                    self.config.port,
                    addr=self.config.host,
                    registry=self.registry
                )
                self.logger.info("Metrics HTTP server started on %s:%s", self.config.host, self.config.port)  # noqa: E501
            except Exception as e:
                self.logger.error("Failed to start HTTP server: %s", e)
                return False

            # Start trading metrics
            self.trading_metrics.start_monitoring()

            # Start collection thread
            self.running = True
            self._shutdown_event.clear()

            self.collection_thread = threading.Thread(
                target=self._collection_loop,
                name="MetricsCollector",
                daemon=True
            )
            self.collection_thread.start()

            # Set system info
            self._update_system_info()

            self.logger.info("Metrics collector started successfully")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "start_metrics_collector")
            return False

    def stop(self):
        """Stop the metrics collector."""
        if not self.running:
            return

        self.logger.info("Stopping metrics collector...")
        self.running = False
        self._shutdown_event.set()

        # Stop trading metrics
        self.trading_metrics.stop_monitoring()

        # Wait for collection thread
        if self.collection_thread and self.collection_thread.is_alive():
            self.collection_thread.join(timeout=10)

        self.logger.info("Metrics collector stopped")

    def _collection_loop(self):
        """Main metrics collection loop."""
        while self.running and not self._shutdown_event.is_set():
            try:
                start_time = time.time()

                # Update system metrics
                if self._should_update_system_metrics():
                    self._update_system_metrics()

                # Update trading metrics
                self._update_trading_metrics()

                # Update gateway metrics
                self._update_gateway_metrics()

                # Performance tracking
                collection_time = time.time() - start_time
                if collection_time > 5.0:  # Log slow collections
                    self.logger.warning(f"Slow metrics collection: {collection_time:.2f}s")

                # Wait for next collection
                self._shutdown_event.wait(self.config.collection_interval)

            except Exception as e:
                self.error_handler.handle_error(e, "_collection_loop")
                self._shutdown_event.wait(60)  # Wait longer on error

    def _should_update_system_metrics(self) -> bool:
        """Check if system metrics should be updated."""
        return (datetime.now(timezone.utc) - self._last_system_update).total_seconds() >= self._system_metrics_interval  # noqa: E501

    def _update_system_info(self):
        """Update system information."""
        if not HAS_PROMETHEUS:
            return

        try:
            import platform
            self.metrics.system_info.info({
                'version': '1.0.0',
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'hostname': platform.node(),
                'architecture': platform.architecture()[0]
            })
        except Exception as e:
            self.logger.debug("Failed to update system info: %s", e)

    def _update_system_metrics(self):
        """Update system performance metrics."""
        if not HAS_PROMETHEUS or not HAS_PSUTIL:
            return

        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.system_cpu_usage.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics.system_memory_usage.set(memory.percent)

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.metrics.system_disk_usage.set(disk_percent)

            # Load average
            load_avg = psutil.getloadavg()
            self.metrics.system_load_avg.labels(period="1m").set(load_avg[0])
            self.metrics.system_load_avg.labels(period="5m").set(load_avg[1])
            self.metrics.system_load_avg.labels(period="15m").set(load_avg[2])

            self._last_system_update = datetime.now(timezone.utc)

        except Exception as e:
            self.logger.debug("Failed to update system metrics: %s", e)

    def _update_trading_metrics(self):
        """Update trading-related metrics."""
        if not HAS_PROMETHEUS:
            return

        try:
            snapshot = self.trading_metrics.get_current_snapshot()
            portfolio = snapshot.portfolio

            # Portfolio metrics
            self.metrics.portfolio_value.set(portfolio.total_value)
            self.metrics.daily_pnl.set(portfolio.daily_pnl)
            self.metrics.unrealized_pnl.set(portfolio.unrealized_pnl)

            # Risk metrics
            self.metrics.portfolio_delta.set(portfolio.total_delta)
            self.metrics.portfolio_gamma.set(portfolio.total_gamma)
            self.metrics.portfolio_theta.set(portfolio.total_theta)
            self.metrics.portfolio_vega.set(portfolio.total_vega)

            # Position count
            self.metrics.position_count.labels(symbol="SPY", strategy="ALL").set(portfolio.total_positions)  # noqa: E501

            # Strategy metrics
            for strategy_name, strategy in snapshot.strategy_metrics.items():
                self.metrics.strategy_pnl.labels(strategy=strategy_name).set(strategy.total_pnl)
                self.metrics.strategy_win_rate.labels(strategy=strategy_name).set(strategy.win_rate)

        except Exception as e:
            self.logger.debug("Failed to update trading metrics: %s", e)

    def _update_gateway_metrics(self):
        """Update gateway connection metrics."""
        if not HAS_PROMETHEUS:
            return

        try:
            # Update client connection status
            for client_id in CLIENT_ID_RANGE:
                # This would be updated from actual client health data
                # For now, simulate connection status
                is_connected = self._check_client_connection(client_id)
                purpose = self._get_client_purpose(client_id)

                self.metrics.gateway_connected.labels(
                    client_id=str(client_id),
                    purpose=purpose
                ).set(1 if is_connected else 0)

        except Exception as e:
            self.logger.debug("Failed to update gateway metrics: %s", e)

    def _check_client_connection(self, client_id: int) -> bool:
        """Check if a client is connected (placeholder)."""
        # This would integrate with SpyderB14_MultiClientWatchdog
        return True  # Placeholder

    def _get_client_purpose(self, client_id: int) -> str:
        """Get client purpose for metrics labeling."""
        purpose_map = {
            1: "trading", 2: "orders", 3: "market_data", 4: "account_data",
            5: "positions", 6: "risk", 7: "backup", 8: "general",
            9: "general", 10: "general"
        }
        return purpose_map.get(client_id, "general")

    def get_trading_metrics(self) -> TradingMetrics:
        """Get the TradingMetrics instance."""
        return self.trading_metrics

    def record_trade_execution(self, trade: TradeMetrics):
        """Record a trade execution."""
        self.trading_metrics.record_trade(trade)

        # Update Prometheus metrics
        if HAS_PROMETHEUS:
            self.metrics.trades_executed.labels(
                symbol=trade.symbol,
                strategy=trade.strategy,
                side="buy" if trade.quantity > 0 else "sell"
            ).inc()

            if trade.fill_time_ms > 0:
                self.metrics.order_fill_time.labels(
                    symbol=trade.symbol,
                    order_type="market"
                ).observe(trade.fill_time_ms)

            if trade.slippage_bps != 0:
                self.metrics.slippage.labels(
                    symbol=trade.symbol,
                    order_type="market"
                ).observe(abs(trade.slippage_bps))

    def record_strategy_pnl(self, strategy_id: str, regime: str, pnl: float):
        """
        Record strategy P&L observation bucketed by market regime.

        Args:
            strategy_id: Identifier for the strategy (e.g. 'iron_condor').
            regime: Current market regime label (e.g. 'trending', 'mean_reverting').
            pnl: Realized or unrealized P&L in dollars for this observation.
        """
        if HAS_PROMETHEUS and self.metrics:
            self.metrics.strategy_pnl_by_regime.labels(
                strategy_id=strategy_id,
                regime=regime
            ).observe(pnl)

    def record_fill_latency(self, order_type: str, symbol: str, latency_ms: float):
        """
        Record the latency from order submission to fill confirmation.

        Args:
            order_type: Type of order (e.g. 'market', 'limit').
            symbol: Instrument symbol (e.g. 'SPY').
            latency_ms: Fill latency in milliseconds.
        """
        if HAS_PROMETHEUS and self.metrics:
            self.metrics.order_fill_latency_ms.labels(
                order_type=order_type,
                symbol=symbol
            ).observe(latency_ms)

    def record_risk_breach(self, breach_type: str, severity: str):
        """
        Increment the risk breach counter for a given breach type and severity.

        Args:
            breach_type: Category of breach (e.g. 'position_limit', 'var_limit', 'drawdown').
            severity: Severity level (e.g. 'warning', 'critical').
        """
        if HAS_PROMETHEUS and self.metrics:
            self.metrics.risk_breach_total.labels(
                breach_type=breach_type,
                severity=severity
            ).inc()

    def record_risk_rejection(self, strategy: str, rejection_reason: str) -> None:
        """
        Increment the signal-rejection counter for the Prometheus scrape endpoint.

        Args:
            strategy: Identifier of the originating strategy (e.g. 'iron_condor').
            rejection_reason: Short rule-code or reason string (e.g.
                'DELTA_LIMIT_EXCEEDED', 'MAX_DAILY_LOSS').
        """
        if HAS_PROMETHEUS and self.metrics:
            self.metrics.risk_rejections_total.labels(
                strategy=strategy,
                rejection_reason=rejection_reason,
            ).inc()

    def update_regime_confidence(self, regime_type: str, detector: str, confidence: float):
        """
        Update the gauge reflecting current regime classification confidence.

        Args:
            regime_type: The classified regime (e.g. 'trending', 'volatile', 'neutral').
            detector: Identifier for the detector model (e.g. 'hmm', 'ml_ensemble').
            confidence: Confidence score in the range [0.0, 1.0].
        """
        if HAS_PROMETHEUS and self.metrics:
            self.metrics.regime_classification_confidence.labels(
                regime_type=regime_type,
                detector=detector
            ).set(confidence)

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_metrics_collector(config: dict[str, Any] | None = None) -> PrometheusMetricsCollector:
    """
    Factory function to create PrometheusMetricsCollector instance.

    Args:
        config: Configuration dictionary

    Returns:
        PrometheusMetricsCollector instance
    """
    if config:
        metrics_config = MetricsConfig(**config)
    else:
        metrics_config = MetricsConfig()

    return PrometheusMetricsCollector(metrics_config)

def get_default_metrics_collector() -> PrometheusMetricsCollector:
    """Get default metrics collector instance (singleton pattern)."""
    if not hasattr(get_default_metrics_collector, '_instance'):
        get_default_metrics_collector._instance = create_metrics_collector()

    return get_default_metrics_collector._instance


# ==============================================================================
# MODULE-LEVEL HELPER FUNCTIONS
# ==============================================================================

def record_strategy_pnl(strategy_id: str, regime: str, pnl: float):
    """
    Module-level helper: record strategy P&L by regime on the default collector.

    Args:
        strategy_id: Identifier for the strategy (e.g. 'iron_condor').
        regime: Current market regime label (e.g. 'trending', 'mean_reverting').
        pnl: Realized or unrealized P&L in dollars for this observation.
    """
    get_default_metrics_collector().record_strategy_pnl(strategy_id, regime, pnl)


def record_fill_latency(order_type: str, symbol: str, latency_ms: float):
    """
    Module-level helper: record order fill latency on the default collector.

    Args:
        order_type: Type of order (e.g. 'market', 'limit').
        symbol: Instrument symbol (e.g. 'SPY').
        latency_ms: Fill latency in milliseconds.
    """
    get_default_metrics_collector().record_fill_latency(order_type, symbol, latency_ms)


def record_risk_breach(breach_type: str, severity: str):
    """
    Module-level helper: increment the risk breach counter on the default collector.

    Args:
        breach_type: Category of breach (e.g. 'position_limit', 'var_limit').
        severity: Severity level (e.g. 'warning', 'critical').
    """
    get_default_metrics_collector().record_risk_breach(breach_type, severity)


def record_risk_rejection(strategy: str, rejection_reason: str) -> None:
    """
    Module-level helper: increment the risk signal rejection counter.

    Call this from D31 (or any risk gate) whenever ``validate_signal`` rejects
    a strategy signal so the rejection rate is visible on Prometheus dashboards.

    Args:
        strategy: Originating strategy identifier.
        rejection_reason: Short rule-code / reason string.
    """
    get_default_metrics_collector().record_risk_rejection(strategy, rejection_reason)


def update_regime_confidence(regime_type: str, detector: str, confidence: float):
    """
    Module-level helper: update regime classification confidence on the default collector.

    Args:
        regime_type: The classified regime (e.g. 'trending', 'volatile', 'neutral').
        detector: Identifier for the detector model (e.g. 'hmm', 'ml_ensemble').
        confidence: Confidence score in the range [0.0, 1.0].
    """
    get_default_metrics_collector().update_regime_confidence(regime_type, detector, confidence)


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    'MetricType', 'MetricPeriod', 'PerformanceStatus', 'TradeStatus', 'ComponentHealth',

    # Data structures
    'TradeMetrics', 'StrategyMetrics', 'PortfolioMetrics', 'ExecutionMetrics',
    'RiskMetrics', 'ClientMetrics', 'MetricsSnapshot', 'MetricsConfig',

    # Main classes
    'TradingMetrics', 'PrometheusMetricsCollector',

    # Factory functions
    'create_metrics_collector', 'get_default_metrics_collector',

    # New metric helper functions
    'record_strategy_pnl', 'record_fill_latency',
    'record_risk_breach', 'update_regime_confidence',
    'record_risk_rejection',
]

# ==============================================================================
# MODULE TEST
# ==============================================================================

if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


    # Create metrics collector
    collector = create_metrics_collector()


    # Test trading metrics
    trading_metrics = collector.get_trading_metrics()

    # Example trade
    sample_trade = TradeMetrics(
        trade_id="TEST_001",
        symbol="SPY",
        strategy="iron_condor",
        entry_time=datetime.now(timezone.utc),
        quantity=10,
        entry_price=580.0,
        realized_pnl=250.0,
        fill_time_ms=45.0,
        slippage_bps=2.5,
        status=TradeStatus.EXECUTED
    )

    trading_metrics.record_trade(sample_trade)

    # Performance summary
    summary = trading_metrics.get_performance_summary()


# Export alias for missing PrometheusMetrics
try:
    if "SpyderLogger" in globals():
        PrometheusMetrics = SpyderLogger
    else:
        class PrometheusMetrics:
            def __init__(self): pass
except Exception:
    pass

