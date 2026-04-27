#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderM_Monitoring
Module: SpyderM04_TradingMetrics.py
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
import math
import statistics
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date, timezone
from enum import Enum
from typing import Any

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

METRICS_UPDATE_INTERVAL = 5  # seconds
AGGREGATE_INTERVAL = 60  # seconds
REPORT_INTERVAL = 300  # 5 minutes

# Performance thresholds
MIN_SHARPE_RATIO = 1.0
MIN_WIN_RATE = 0.40
MAX_DRAWDOWN = 0.10  # 10%
MAX_CONSECUTIVE_LOSSES = 5

# Risk-free rate for calculations
RISK_FREE_RATE = 0.05  # 5% annual

# ==============================================================================
# ENUMS
# ==============================================================================
class MetricPeriod(Enum):
    """Time periods for metric aggregation"""
    REAL_TIME = "real_time"
    MINUTE_1 = "1_minute"
    MINUTE_5 = "5_minute"
    MINUTE_15 = "15_minute"
    HOUR_1 = "1_hour"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YTD = "year_to_date"
    ALL_TIME = "all_time"

class PerformanceStatus(Enum):
    """Trading performance status"""
    EXCELLENT = "excellent"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    WARNING = "warning"
    POOR = "poor"
    CRITICAL = "critical"

class MetricCategory(Enum):
    """Categories of trading metrics"""
    PNL = "profit_loss"
    WIN_RATE = "win_rate"
    RISK = "risk_metrics"
    EXECUTION = "execution_quality"
    STRATEGY = "strategy_performance"
    PORTFOLIO = "portfolio_metrics"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TradeMetrics:
    """Metrics for a single trade"""
    trade_id: str
    symbol: str
    strategy: str
    entry_time: datetime
    exit_time: datetime | None
    entry_price: float
    exit_price: float | None
    quantity: int
    trade_type: str  # 'long' or 'short'
    pnl: float = 0.0
    pnl_percent: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    is_winner: bool = False
    max_profit: float = 0.0
    max_loss: float = 0.0
    duration: timedelta | None = None

@dataclass
class StrategyMetrics:
    """Performance metrics for a trading strategy"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    win_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
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
    strategies: dict[str, StrategyMetrics]
    execution: ExecutionMetrics
    risk: RiskMetrics
    trades: list[TradeMetrics]
    performance_status: PerformanceStatus
    alerts: list[str] = field(default_factory=list)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
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
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Metrics storage
        self.trade_history: list[TradeMetrics] = []
        self.current_trades: dict[str, TradeMetrics] = {}
        self.strategy_metrics: dict[str, StrategyMetrics] = defaultdict(self._create_strategy_metrics)  # noqa: E501
        self.portfolio_history: deque = deque(maxlen=10000)

        # Real-time tracking
        self.last_portfolio_value = 0.0
        self.high_water_mark = 0.0
        self.current_drawdown = 0.0
        self.daily_starting_value = 0.0

        # Performance tracking
        self.daily_returns: deque = deque(maxlen=252)  # 1 year of trading days
        self.equity_curve: list[tuple[datetime, float]] = []

        # Monitoring threads
        self.monitoring_active = False
        self.monitor_thread = None
        self.aggregate_thread = None
        self.stop_event = threading.Event()

        # Cached calculations
        self._cached_metrics: dict[MetricPeriod, MetricsSnapshot] = {}
        self._cache_timestamp: dict[MetricPeriod, datetime] = {}

        self.logger.info("Trading Metrics system initialized")

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start_monitoring(self) -> bool:
        """
        Start real-time metrics monitoring.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.monitoring_active:
                self.logger.warning("Monitoring already active")
                return False

            self.monitoring_active = True
            self.stop_event.clear()

            # Initialize daily values
            self._initialize_daily_values()

            # Start monitoring threads
            self._start_monitoring_threads()

            self.logger.info("Trading metrics monitoring started")
            return True

        except Exception as e:
            self.logger.error("Failed to start monitoring: %s", e)
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop metrics monitoring.

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.monitoring_active:
                return False

            self.monitoring_active = False
            self.stop_event.set()

            # Wait for threads
            for thread in [self.monitor_thread, self.aggregate_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=5)

            self.logger.info("Trading metrics monitoring stopped")
            return True

        except Exception as e:
            self.logger.error("Error stopping monitoring: %s", e)
            return False

    # ==========================================================================
    # PUBLIC METHODS - TRADE TRACKING
    # ==========================================================================
    def open_trade(self, trade: TradeMetrics):
        """
        Record a new trade opening.

        Args:
            trade: Trade metrics object
        """
        self.current_trades[trade.trade_id] = trade
        self.logger.debug("Opened trade: %s", trade.trade_id)

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: datetime | None = None
    ) -> TradeMetrics | None:
        """
        Record a trade closing.

        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            exit_time: Exit timestamp

        Returns:
            Completed trade metrics or None
        """
        if trade_id not in self.current_trades:
            self.logger.error("Trade %s not found", trade_id)
            return None

        trade = self.current_trades.pop(trade_id)
        trade.exit_price = exit_price
        trade.exit_time = exit_time or datetime.now(timezone.utc)

        # Calculate P&L
        if trade.trade_type == 'long':
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # short
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

        trade.pnl -= trade.commission
        trade.pnl_percent = trade.pnl / (trade.entry_price * trade.quantity)
        trade.is_winner = trade.pnl > 0

        # Calculate duration
        trade.duration = trade.exit_time - trade.entry_time

        # Add to history
        self.trade_history.append(trade)

        # Update strategy metrics
        self._update_strategy_metrics(trade)

        self.logger.info(f"Closed trade {trade_id}: P&L=${trade.pnl:.2f}")
        return trade

    def update_portfolio_value(self, total_value: float, cash_balance: float):
        """
        Update current portfolio value.

        Args:
            total_value: Total portfolio value
            cash_balance: Cash balance
        """
        timestamp = datetime.now(timezone.utc)
        positions_value = total_value - cash_balance

        # Calculate daily P&L
        daily_pnl = total_value - self.daily_starting_value

        # Update drawdown
        if total_value > self.high_water_mark:
            self.high_water_mark = total_value
            self.current_drawdown = 0.0
        else:
            self.current_drawdown = (self.high_water_mark - total_value) / self.high_water_mark

        # Create portfolio metrics
        metrics = PortfolioMetrics(
            timestamp=timestamp,
            total_value=total_value,
            cash_balance=cash_balance,
            positions_value=positions_value,
            daily_pnl=daily_pnl,
            total_pnl=total_value - self.daily_starting_value,  # Simplified
            return_percent=(total_value / self.daily_starting_value - 1) * 100,
            volatility=self._calculate_volatility(),
            sharpe_ratio=self._calculate_sharpe_ratio(),
            sortino_ratio=self._calculate_sortino_ratio(),
            calmar_ratio=self._calculate_calmar_ratio(),
            max_drawdown=self._calculate_max_drawdown(),
            current_drawdown=self.current_drawdown
        )

        # Store in history
        self.portfolio_history.append(metrics)
        self.equity_curve.append((timestamp, total_value))

        # Update last value
        self.last_portfolio_value = total_value

    # ==========================================================================
    # PUBLIC METHODS - METRICS RETRIEVAL
    # ==========================================================================
    def get_current_metrics(self, period: MetricPeriod = MetricPeriod.REAL_TIME) -> MetricsSnapshot:
        """
        Get current metrics snapshot.

        Args:
            period: Time period for metrics

        Returns:
            MetricsSnapshot with current data
        """
        # Check cache
        if period in self._cached_metrics:
            cache_age = datetime.now(timezone.utc) - self._cache_timestamp.get(period, datetime.min)
            if cache_age.seconds < 60:  # 1-minute cache
                return self._cached_metrics[period]

        # Generate new snapshot
        snapshot = self._generate_metrics_snapshot(period)

        # Cache it
        self._cached_metrics[period] = snapshot
        self._cache_timestamp[period] = datetime.now(timezone.utc)

        return snapshot

    def get_strategy_performance(self, strategy_name: str) -> StrategyMetrics | None:
        """
        Get performance metrics for a specific strategy.

        Args:
            strategy_name: Name of the strategy

        Returns:
            StrategyMetrics or None
        """
        return self.strategy_metrics.get(strategy_name)

    def get_trade_history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        strategy: str | None = None
    ) -> list[TradeMetrics]:
        """
        Get trade history with optional filters.

        Args:
            start_date: Start date filter
            end_date: End date filter
            strategy: Strategy name filter

        Returns:
            List of trades matching criteria
        """
        trades = self.trade_history

        if start_date:
            trades = [t for t in trades if t.entry_time >= start_date]

        if end_date:
            trades = [t for t in trades if t.entry_time <= end_date]

        if strategy:
            trades = [t for t in trades if t.strategy == strategy]

        return trades

    def get_performance_summary(self) -> dict[str, Any]:
        """
        Get overall performance summary.

        Returns:
            Dict with performance statistics
        """
        if not self.trade_history:
            return self._empty_performance_summary()

        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.is_winner)
        losing_trades = total_trades - winning_trades

        gross_profit = sum(t.pnl for t in self.trade_history if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trade_history if t.pnl < 0))
        net_profit = gross_profit - gross_loss

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'net_profit': net_profit,
            'profit_factor': gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            'average_win': gross_profit / winning_trades if winning_trades > 0 else 0,
            'average_loss': gross_loss / losing_trades if losing_trades > 0 else 0,
            'largest_win': max((t.pnl for t in self.trade_history), default=0),
            'largest_loss': min((t.pnl for t in self.trade_history), default=0),
            'average_trade': net_profit / total_trades if total_trades > 0 else 0,
            'sharpe_ratio': self._calculate_sharpe_ratio(),
            'max_drawdown': self._calculate_max_drawdown(),
            'current_drawdown': self.current_drawdown,
            'trades_today': self._count_trades_today(),
            'pnl_today': self._calculate_pnl_today()
        }

    # ==========================================================================
    # PUBLIC METHODS - ALERTS AND MONITORING
    # ==========================================================================
    def check_performance_alerts(self) -> list[str]:
        """
        Check for performance issues requiring alerts.

        Returns:
            List of alert messages
        """
        alerts = []

        # Check drawdown
        if self.current_drawdown > MAX_DRAWDOWN:
            alerts.append(f"Maximum drawdown exceeded: {self.current_drawdown:.1%}")

        # Check consecutive losses
        consecutive_losses = self._count_consecutive_losses()
        if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            alerts.append(f"Consecutive losses: {consecutive_losses}")

        # Check win rate
        if self.trade_history:
            recent_trades = self.trade_history[-20:]  # Last 20 trades
            recent_win_rate = sum(1 for t in recent_trades if t.is_winner) / len(recent_trades)
            if recent_win_rate < MIN_WIN_RATE:
                alerts.append(f"Low win rate: {recent_win_rate:.1%}")

        # Check Sharpe ratio
        sharpe = self._calculate_sharpe_ratio()
        if sharpe < MIN_SHARPE_RATIO and len(self.daily_returns) > 20:
            alerts.append(f"Low Sharpe ratio: {sharpe:.2f}")

        return alerts

    def get_risk_metrics(self) -> RiskMetrics:
        """
        Calculate current risk metrics.

        Returns:
            RiskMetrics object
        """
        return RiskMetrics(
            value_at_risk=self._calculate_var(),
            conditional_var=self._calculate_cvar(),
            position_sizing_accuracy=self._calculate_position_sizing_accuracy(),
            risk_reward_ratio=self._calculate_risk_reward_ratio(),
            kelly_percentage=self._calculate_kelly_percentage(),
            exposure_percent=self._calculate_exposure_percent(),
            correlation_risk=self._calculate_correlation_risk(),
            concentration_risk=self._calculate_concentration_risk()
        )

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _initialize_daily_values(self):
        """Initialize values at start of trading day."""
        # Get last portfolio value or use initial value
        if self.portfolio_history:
            self.daily_starting_value = self.portfolio_history[-1].total_value
        else:
            self.daily_starting_value = 100000  # Default starting value

        self.last_portfolio_value = self.daily_starting_value
        self.high_water_mark = max(self.high_water_mark, self.daily_starting_value)

    def _start_monitoring_threads(self):
        """Start monitoring threads."""
        # Real-time monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="TradingMetricsMonitor"
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        # Aggregation thread
        self.aggregate_thread = threading.Thread(
            target=self._aggregation_loop,
            name="TradingMetricsAggregator"
        )
        self.aggregate_thread.daemon = True
        self.aggregate_thread.start()

    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOPS
    # ==========================================================================
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while not self.stop_event.is_set():
            try:
                # Update real-time metrics
                self._update_real_time_metrics()

                # Check for alerts
                alerts = self.check_performance_alerts()
                if alerts:
                    for alert in alerts:
                        self.logger.warning("Performance Alert: %s", alert)

                self.stop_event.wait(METRICS_UPDATE_INTERVAL)

            except Exception as e:
                self.logger.error("Monitoring error: %s", e)

    def _aggregation_loop(self):
        """Metrics aggregation loop."""
        while not self.stop_event.is_set():
            try:
                # Aggregate metrics for different periods
                self._aggregate_period_metrics()

                # Clean old data
                self._clean_old_data()

                self.stop_event.wait(AGGREGATE_INTERVAL)

            except Exception as e:
                self.logger.error("Aggregation error: %s", e)

    # ==========================================================================
    # PRIVATE METHODS - METRICS CALCULATION
    # ==========================================================================
    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio."""
        if len(self.daily_returns) < 2:
            return 0.0

        returns = list(self.daily_returns)
        if not returns:
            return 0.0

        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0

        if std_return == 0:
            return 0.0

        # Annualize
        annual_return = mean_return * 252
        annual_std = std_return * math.sqrt(252)

        return (annual_return - RISK_FREE_RATE) / annual_std

    def _calculate_sortino_ratio(self) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(self.daily_returns) < 2:
            return 0.0

        returns = list(self.daily_returns)
        negative_returns = [r for r in returns if r < 0]

        if not negative_returns:
            return float('inf')  # No downside

        mean_return = statistics.mean(returns)
        downside_std = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 0

        if downside_std == 0:
            return float('inf')

        # Annualize
        annual_return = mean_return * 252
        annual_downside = downside_std * math.sqrt(252)

        return (annual_return - RISK_FREE_RATE) / annual_downside

    def _calculate_calmar_ratio(self) -> float:
        """Calculate Calmar ratio (return/max drawdown)."""
        max_dd = self._calculate_max_drawdown()
        if max_dd == 0:
            return float('inf')

        if not self.daily_returns:
            return 0.0

        annual_return = statistics.mean(self.daily_returns) * 252
        return annual_return / max_dd

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if not self.equity_curve:
            return 0.0

        values = [v for _, v in self.equity_curve]
        peak = values[0]
        max_dd = 0.0

        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd

    def _calculate_volatility(self) -> float:
        """Calculate annualized volatility."""
        if len(self.daily_returns) < 2:
            return 0.0

        return statistics.stdev(self.daily_returns) * math.sqrt(252)

    def _calculate_var(self, confidence: float = 0.95) -> float:
        """Calculate Value at Risk."""
        if not self.daily_returns:
            return 0.0

        sorted_returns = sorted(self.daily_returns)
        index = int(len(sorted_returns) * (1 - confidence))
        return sorted_returns[index] if index < len(sorted_returns) else 0.0

    def _calculate_cvar(self, confidence: float = 0.95) -> float:
        """Calculate Conditional Value at Risk."""
        var = self._calculate_var(confidence)
        tail_returns = [r for r in self.daily_returns if r <= var]
        return statistics.mean(tail_returns) if tail_returns else var

    def _calculate_position_sizing_accuracy(self) -> float:
        """Calculate how well position sizing matches targets."""
        # Simplified implementation
        return 0.95  # Placeholder

    def _calculate_risk_reward_ratio(self) -> float:
        """Calculate average risk/reward ratio."""
        if not self.trade_history:
            return 0.0

        ratios = []
        for trade in self.trade_history:
            if trade.max_loss != 0:
                ratio = abs(trade.max_profit / trade.max_loss)
                ratios.append(ratio)

        return statistics.mean(ratios) if ratios else 0.0

    def _calculate_kelly_percentage(self) -> float:
        """Calculate Kelly criterion for position sizing."""
        if not self.trade_history:
            return 0.0

        win_rate = sum(1 for t in self.trade_history if t.is_winner) / len(self.trade_history)

        wins = [t.pnl for t in self.trade_history if t.pnl > 0]
        losses = [abs(t.pnl) for t in self.trade_history if t.pnl < 0]

        if not wins or not losses:
            return 0.0

        avg_win = statistics.mean(wins)
        avg_loss = statistics.mean(losses)

        if avg_loss == 0:
            return 0.0

        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        kelly = (b * p - q) / b
        return max(0, min(kelly, 0.25))  # Cap at 25%

    def _calculate_exposure_percent(self) -> float:
        """Calculate current market exposure."""
        if not self.portfolio_history:
            return 0.0

        latest = self.portfolio_history[-1]
        return latest.positions_value / latest.total_value

    def _calculate_correlation_risk(self) -> float:
        """Calculate portfolio correlation risk."""
        # Simplified - would calculate actual correlations
        return 0.3  # Placeholder

    def _calculate_concentration_risk(self) -> float:
        """Calculate position concentration risk."""
        # Simplified - would check position sizes
        return 0.2  # Placeholder

    # ==========================================================================
    # PRIVATE METHODS - METRICS GENERATION
    # ==========================================================================
    def _generate_metrics_snapshot(self, period: MetricPeriod) -> MetricsSnapshot:
        """Generate complete metrics snapshot."""
        # Get latest portfolio metrics
        if self.portfolio_history:
            portfolio = self.portfolio_history[-1]
        else:
            portfolio = self._create_empty_portfolio_metrics()

        # Get execution metrics
        execution = self._calculate_execution_metrics(period)

        # Get risk metrics
        risk = self.get_risk_metrics()

        # Get trades for period
        trades = self._get_trades_for_period(period)

        # Determine performance status
        status = self._determine_performance_status(portfolio, risk)

        # Get alerts
        alerts = self.check_performance_alerts()

        return MetricsSnapshot(
            timestamp=datetime.now(timezone.utc),
            period=period,
            portfolio=portfolio,
            strategies=dict(self.strategy_metrics),
            execution=execution,
            risk=risk,
            trades=trades,
            performance_status=status,
            alerts=alerts
        )

    def _determine_performance_status(
        self,
        portfolio: PortfolioMetrics,
        risk: RiskMetrics
    ) -> PerformanceStatus:
        """Determine overall performance status."""
        score = 0

        # Check Sharpe ratio
        if portfolio.sharpe_ratio >= 2.0:
            score += 3
        elif portfolio.sharpe_ratio >= 1.0:
            score += 2
        elif portfolio.sharpe_ratio >= 0.5:
            score += 1

        # Check drawdown
        if portfolio.current_drawdown < 0.05:
            score += 2
        elif portfolio.current_drawdown < 0.10:
            score += 1
        else:
            score -= 1

        # Check win rate
        if self.trade_history:
            win_rate = sum(1 for t in self.trade_history[-20:] if t.is_winner) / min(20, len(self.trade_history))  # noqa: E501
            if win_rate >= 0.6:
                score += 2
            elif win_rate >= 0.5:
                score += 1
            elif win_rate < 0.4:
                score -= 1

        # Determine status
        if score >= 6:
            return PerformanceStatus.EXCELLENT
        elif score >= 4:
            return PerformanceStatus.GOOD
        elif score >= 2:
            return PerformanceStatus.SATISFACTORY
        elif score >= 0:
            return PerformanceStatus.WARNING
        elif score >= -2:
            return PerformanceStatus.POOR
        else:
            return PerformanceStatus.CRITICAL

    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    def _create_strategy_metrics(self) -> StrategyMetrics:
        """Create empty strategy metrics."""
        return StrategyMetrics(strategy_name="")

    def _create_empty_portfolio_metrics(self) -> PortfolioMetrics:
        """Create empty portfolio metrics."""
        return PortfolioMetrics(
            timestamp=datetime.now(timezone.utc),
            total_value=0,
            cash_balance=0,
            positions_value=0,
            daily_pnl=0,
            total_pnl=0,
            return_percent=0,
            volatility=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            max_drawdown=0,
            current_drawdown=0
        )

    def _empty_performance_summary(self) -> dict[str, Any]:
        """Return empty performance summary."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'gross_profit': 0,
            'gross_loss': 0,
            'net_profit': 0,
            'profit_factor': 0,
            'average_win': 0,
            'average_loss': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'average_trade': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'current_drawdown': 0,
            'trades_today': 0,
            'pnl_today': 0
        }

    def _update_strategy_metrics(self, trade: TradeMetrics):
        """Update metrics for a strategy."""
        metrics = self.strategy_metrics[trade.strategy]
        metrics.strategy_name = trade.strategy
        metrics.total_trades += 1

        if trade.is_winner:
            metrics.winning_trades += 1
            metrics.gross_profit += trade.pnl
            metrics.consecutive_wins += 1
            metrics.consecutive_losses = 0
        else:
            metrics.losing_trades += 1
            metrics.gross_loss += abs(trade.pnl)
            metrics.consecutive_losses += 1
            metrics.consecutive_wins = 0

        metrics.total_pnl += trade.pnl
        metrics.win_rate = metrics.winning_trades / metrics.total_trades

        if metrics.winning_trades > 0:
            metrics.average_win = metrics.gross_profit / metrics.winning_trades

        if metrics.losing_trades > 0:
            metrics.average_loss = metrics.gross_loss / metrics.losing_trades

        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss

        metrics.best_trade = max(metrics.best_trade, trade.pnl)
        metrics.worst_trade = min(metrics.worst_trade, trade.pnl)

    def _count_consecutive_losses(self) -> int:
        """Count current consecutive losses."""
        if not self.trade_history:
            return 0

        count = 0
        for trade in reversed(self.trade_history):
            if not trade.is_winner:
                count += 1
            else:
                break

        return count

    def _count_trades_today(self) -> int:
        """Count trades executed today."""
        today = date.today()
        return sum(1 for t in self.trade_history if t.entry_time.date() == today)

    def _calculate_pnl_today(self) -> float:
        """Calculate P&L for today."""
        today = date.today()
        return sum(t.pnl for t in self.trade_history if t.entry_time.date() == today)

    def _get_trades_for_period(self, period: MetricPeriod) -> list[TradeMetrics]:
        """Get trades for specified period."""
        now = datetime.now(timezone.utc)

        if period == MetricPeriod.REAL_TIME:
            # Include current trades
            return list(self.current_trades.values())
        elif period == MetricPeriod.MINUTE_1:
            cutoff = now - timedelta(minutes=1)
        elif period == MetricPeriod.MINUTE_5:
            cutoff = now - timedelta(minutes=5)
        elif period == MetricPeriod.MINUTE_15:
            cutoff = now - timedelta(minutes=15)
        elif period == MetricPeriod.HOUR_1:
            cutoff = now - timedelta(hours=1)
        elif period == MetricPeriod.DAILY:
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == MetricPeriod.WEEKLY:
            cutoff = now - timedelta(days=7)
        elif period == MetricPeriod.MONTHLY:
            cutoff = now - timedelta(days=30)
        elif period == MetricPeriod.YTD:
            cutoff = datetime(now.year, 1, 1)
        else:  # ALL_TIME
            return self.trade_history

        return [t for t in self.trade_history if t.entry_time >= cutoff]

    def _calculate_execution_metrics(self, period: MetricPeriod) -> ExecutionMetrics:
        """Calculate execution metrics for period."""
        trades = self._get_trades_for_period(period)

        if not trades:
            return ExecutionMetrics()

        total_orders = len(trades)
        filled_orders = len([t for t in trades if t.exit_time is not None])

        fill_times = []
        slippages = []
        total_commission = 0

        for trade in trades:
            if trade.duration:
                fill_times.append(trade.duration.total_seconds())
            slippages.append(abs(trade.slippage))
            total_commission += trade.commission

        return ExecutionMetrics(
            total_orders=total_orders,
            filled_orders=filled_orders,
            rejected_orders=0,  # Would need order data
            cancelled_orders=0,  # Would need order data
            average_fill_time=statistics.mean(fill_times) if fill_times else 0,
            average_slippage=statistics.mean(slippages) if slippages else 0,
            total_commission=total_commission,
            execution_rate=filled_orders / total_orders if total_orders > 0 else 0
        )

    def _update_real_time_metrics(self):
        """Update real-time metrics."""
        # Calculate daily returns
        if self.last_portfolio_value > 0 and self.daily_starting_value > 0:
            daily_return = (self.last_portfolio_value / self.daily_starting_value) - 1
            self.daily_returns.append(daily_return)

    def _aggregate_period_metrics(self):
        """Aggregate metrics for different time periods."""
        # This would aggregate metrics for different periods
        # For now, just clear cache to force recalculation
        self._cached_metrics.clear()
        self._cache_timestamp.clear()

    def _clean_old_data(self):
        """Clean old data to manage memory."""
        # Keep only last 30 days of trades
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        self.trade_history = [t for t in self.trade_history if t.entry_time > cutoff]

        # Keep only last 365 days of equity curve
        cutoff_equity = datetime.now(timezone.utc) - timedelta(days=365)
        self.equity_curve = [(ts, v) for ts, v in self.equity_curve if ts > cutoff_equity]

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_trading_metrics() -> TradingMetrics:
    """
    Factory function to create trading metrics system.

    Returns:
        Configured TradingMetrics instance
    """
    return TradingMetrics()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    pass
class MetricsCollector:
    """Trading metrics collector for aggregating and managing trading metrics"""

    def __init__(self):
        self.trade_metrics: list[TradeMetrics] = []
        self.strategy_metrics: dict[str, StrategyMetrics] = {}
        self.portfolio_metrics: PortfolioMetrics | None = None

    def add_trade_metric(self, metric: TradeMetrics) -> None:
        """Add a trade metric"""
        self.trade_metrics.append(metric)

    def add_strategy_metric(self, strategy_name: str, metric: StrategyMetrics) -> None:
        """Add a strategy metric"""
        self.strategy_metrics[strategy_name] = metric

    def set_portfolio_metric(self, metric: PortfolioMetrics) -> None:
        """Set portfolio metric"""
        self.portfolio_metrics = metric

    def get_trade_metrics(self) -> list[TradeMetrics]:
        """Get all trade metrics"""
        return self.trade_metrics

    def get_strategy_metrics(self) -> dict[str, StrategyMetrics]:
        """Get all strategy metrics"""
        return self.strategy_metrics

    def get_portfolio_metrics(self) -> PortfolioMetrics | None:
        """Get portfolio metrics"""
        return self.portfolio_metrics

    def clear_metrics(self) -> None:
        """Clear all metrics"""
        self.trade_metrics.clear()
        self.strategy_metrics.clear()
        self.portfolio_metrics = None

def get_metrics_collector() -> MetricsCollector:
    """Factory function to get MetricsCollector instance"""
    return MetricsCollector()
