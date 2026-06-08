#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovH_Storage
Module: TradovH07_PerformanceAnalytics.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, date, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    TradovLogger = type('TradovLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    LOCAL_IMPORTS = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21
RISK_FREE_RATE = 0.045  # 4.5% annual risk-free rate (current T-bill rate, standardized)
DEFAULT_INITIAL_CAPITAL = 100000.0


# ==============================================================================
# ENUMS
# ==============================================================================
class TimeFrame(Enum):
    """Time frames for analytics."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ALL_TIME = "all_time"


class MetricCategory(Enum):
    """Categories of performance metrics."""
    RETURNS = "returns"
    RISK = "risk"
    RISK_ADJUSTED = "risk_adjusted"
    TRADE_STATISTICS = "trade_statistics"
    TIMING = "timing"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    # Period information
    start_date: date
    end_date: date
    trading_days: int
    calendar_days: int

    # Capital metrics
    initial_capital: float
    ending_capital: float
    net_profit: float
    gross_profit: float
    gross_loss: float

    # Return metrics
    total_return: float
    total_return_pct: float
    annualized_return: float
    avg_daily_return: float
    avg_monthly_return: float

    # Risk metrics
    volatility: float
    downside_deviation: float
    max_drawdown: float
    max_drawdown_duration: int
    var_95: float
    cvar_95: float

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_trade: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_holding_period: float
    max_consecutive_wins: int
    max_consecutive_losses: int

    # Consistency
    positive_days: int
    positive_months: int
    total_months: int
    monthly_consistency: float

    # Benchmark comparison (if available)
    benchmark_return: float | None = None
    alpha: float | None = None
    beta: float | None = None
    information_ratio: float | None = None


@dataclass
class EquityCurve:
    """Equity curve data."""
    dates: list[date]
    equity: list[float]
    returns: list[float]
    drawdowns: list[float]
    high_water_mark: list[float]


@dataclass
class TradeDistribution:
    """Trade distribution analysis."""
    pnl_histogram: dict[str, int]  # PnL buckets -> count
    holding_time_distribution: dict[str, int]  # Time buckets -> count
    hourly_distribution: dict[int, int]  # Hour -> trade count
    weekday_distribution: dict[str, int]  # Weekday -> trade count
    monthly_distribution: dict[str, float]  # Month -> total PnL


@dataclass
class PerformanceReport:
    """Complete performance report."""
    report_date: datetime
    account_id: str
    strategy_name: str | None
    time_frame: TimeFrame

    # Core data
    metrics: PerformanceMetrics
    equity_curve: EquityCurve | None = None
    trade_distribution: TradeDistribution | None = None

    # Monthly breakdown
    monthly_returns: dict[str, float] | None = None

    # Insights
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ==============================================================================
# PERFORMANCE ANALYTICS ENGINE
# ==============================================================================
class PerformanceAnalytics:
    """
    Performance analytics engine for trading analysis.

    Calculates comprehensive performance metrics, generates equity curves,
    and provides insights for strategy optimization.
    """

    def __init__(
        self,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        risk_free_rate: float = RISK_FREE_RATE,
        config: dict[str, Any] | None = None
    ):
        """
        Initialize performance analytics.

        Args:
            initial_capital: Starting capital for calculations
            risk_free_rate: Annual risk-free rate for Sharpe/Sortino
            config: Optional configuration dictionary
        """
        self.logger = TradovLogger.get_logger(__name__)
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.config = config or {}

        # Thread safety
        self._lock = threading.Lock()

        self.logger.info(
            f"PerformanceAnalytics initialized: capital=${initial_capital:,.2f}"
        )

    def calculate(self, *args, **kwargs) -> dict[str, Any]:
        """Legacy calculate method for backward compatibility."""
        return {}

    def get_summary_stats(self) -> dict[str, Any]:
        """Return an empty summary; populated when trade data is available."""
        return {}

    def analyze_trades(
        self,
        trades: list[dict[str, Any]],
        time_frame: TimeFrame = TimeFrame.ALL_TIME,
        strategy_name: str | None = None,
        account_id: str = "default"
    ) -> PerformanceReport:
        """
        Analyze a list of trades and generate performance report.

        Args:
            trades: List of trade dictionaries with at least 'pnl' and 'executed_at'
            time_frame: Time frame for analysis
            strategy_name: Optional strategy name
            account_id: Account identifier

        Returns:
            Complete PerformanceReport
        """
        with self._lock:
            if not trades:
                raise ValueError("No trades provided for analysis")

            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(trades)

            # Ensure datetime column
            if 'executed_at' in df.columns:
                df['executed_at'] = pd.to_datetime(df['executed_at'])
                df = df.sort_values('executed_at')

            # Filter by time frame
            df = self._filter_by_timeframe(df, time_frame)

            if df.empty:
                raise ValueError("No trades in specified time frame")

            # Calculate metrics
            metrics = self._calculate_metrics(df)

            # Generate equity curve
            equity_curve = self._generate_equity_curve(df)

            # Analyze trade distribution
            trade_dist = self._analyze_trade_distribution(df)

            # Calculate monthly returns
            monthly_returns = self._calculate_monthly_returns(df)

            # Generate insights
            strengths, weaknesses, recommendations = self._generate_insights(metrics)

            return PerformanceReport(
                report_date=datetime.now(UTC),
                account_id=account_id,
                strategy_name=strategy_name,
                time_frame=time_frame,
                metrics=metrics,
                equity_curve=equity_curve,
                trade_distribution=trade_dist,
                monthly_returns=monthly_returns,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations
            )

    def analyze_returns(
        self,
        returns: pd.Series | list[float],
        initial_capital: float | None = None
    ) -> PerformanceMetrics:
        """
        Analyze a return series.

        Args:
            returns: Daily returns series
            initial_capital: Starting capital

        Returns:
            PerformanceMetrics
        """
        if isinstance(returns, list):
            returns = pd.Series(returns)

        capital = initial_capital or self.initial_capital

        # Create synthetic trade data
        trades_df = pd.DataFrame({
            'pnl': returns * capital,
            'executed_at': returns.index if hasattr(returns, 'index') else range(len(returns))
        })

        return self._calculate_metrics(trades_df, returns_series=returns)

    def _filter_by_timeframe(
        self,
        df: pd.DataFrame,
        time_frame: TimeFrame
    ) -> pd.DataFrame:
        """Filter DataFrame by time frame."""
        if 'executed_at' not in df.columns:
            return df

        now = datetime.now(UTC)

        if time_frame == TimeFrame.DAILY:
            start = now - timedelta(days=1)
        elif time_frame == TimeFrame.WEEKLY:
            start = now - timedelta(weeks=1)
        elif time_frame == TimeFrame.MONTHLY:
            start = now - timedelta(days=30)
        elif time_frame == TimeFrame.QUARTERLY:
            start = now - timedelta(days=90)
        elif time_frame == TimeFrame.YEARLY:
            start = now - timedelta(days=365)
        else:  # ALL_TIME
            return df

        return df[df['executed_at'] >= start]

    def _calculate_metrics(
        self,
        df: pd.DataFrame,
        returns_series: pd.Series | None = None
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics from trade data."""
        # Extract PnL
        pnl = df['pnl'].values if 'pnl' in df.columns else np.array([0])

        # Date range
        if 'executed_at' in df.columns and len(df) > 0:
            start_date = df['executed_at'].min().date() if hasattr(df['executed_at'].min(), 'date') else date.today()  # noqa: E501
            end_date = df['executed_at'].max().date() if hasattr(df['executed_at'].max(), 'date') else date.today()  # noqa: E501
            trading_days = len(df['executed_at'].dt.date.unique()) if hasattr(df['executed_at'].dt, 'date') else len(df)  # noqa: E501
        else:
            start_date = date.today()
            end_date = date.today()
            trading_days = len(df)

        calendar_days = (end_date - start_date).days + 1

        # Capital metrics
        gross_profit = pnl[pnl > 0].sum() if len(pnl[pnl > 0]) > 0 else 0
        gross_loss = abs(pnl[pnl < 0].sum()) if len(pnl[pnl < 0]) > 0 else 0
        net_profit = pnl.sum()
        ending_capital = self.initial_capital + net_profit

        # Return metrics
        total_return = net_profit
        total_return_pct = (net_profit / self.initial_capital) * 100

        # Calculate daily returns if not provided
        if returns_series is None:
            if 'executed_at' in df.columns:
                daily_pnl = df.groupby(df['executed_at'].dt.date)['pnl'].sum()
                returns_series = daily_pnl / self.initial_capital
            else:
                returns_series = pd.Series(pnl) / self.initial_capital

        # Annualized return
        years = trading_days / TRADING_DAYS_PER_YEAR if trading_days > 0 else 1
        annualized_return = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0  # noqa: E501

        avg_daily_return = returns_series.mean() * 100 if len(returns_series) > 0 else 0

        # Monthly returns
        if len(returns_series) >= 21:
            monthly_returns = returns_series.rolling(21).sum()
            avg_monthly_return = monthly_returns.mean() * 100
        else:
            avg_monthly_return = avg_daily_return * 21

        # Risk metrics
        volatility = returns_series.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100 if len(returns_series) > 1 else 0  # noqa: E501
        downside_returns = returns_series[returns_series < 0]
        downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) * 100 if len(downside_returns) > 1 else 0  # noqa: E501

        # Drawdown
        cum_returns = (1 + returns_series).cumprod()
        rolling_max = cum_returns.cummax()
        drawdowns = (cum_returns - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min()) * 100 if len(drawdowns) > 0 else 0

        # Max drawdown duration
        in_drawdown = drawdowns < 0
        dd_duration = 0
        current_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                dd_duration = max(dd_duration, current_duration)
            else:
                current_duration = 0

        # VaR and CVaR
        var_95 = abs(np.percentile(returns_series, 5)) * 100 if len(returns_series) > 0 else 0
        tail_returns = returns_series[returns_series <= np.percentile(returns_series, 5)]
        cvar_95 = abs(tail_returns.mean()) * 100 if len(tail_returns) > 0 else var_95

        # Risk-adjusted metrics
        excess_return = annualized_return - (self.risk_free_rate * 100)
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Omega ratio
        threshold = 0
        gains = returns_series[returns_series > threshold].sum()
        losses = abs(returns_series[returns_series < threshold].sum())
        omega_ratio = gains / losses if losses > 0 else float('inf')

        # Trade statistics
        total_trades = len(pnl)
        winning_trades = len(pnl[pnl > 0])
        losing_trades = len(pnl[pnl < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        avg_trade = pnl.mean() if len(pnl) > 0 else 0
        avg_winner = pnl[pnl > 0].mean() if len(pnl[pnl > 0]) > 0 else 0
        avg_loser = abs(pnl[pnl < 0].mean()) if len(pnl[pnl < 0]) > 0 else 0
        largest_winner = pnl.max() if len(pnl) > 0 else 0
        largest_loser = pnl.min() if len(pnl) > 0 else 0

        # Holding period
        if 'duration_hours' in df.columns:
            avg_holding_period = df['duration_hours'].mean()
        else:
            avg_holding_period = 0

        # Consecutive wins/losses
        max_consecutive_wins = self._max_consecutive(pnl > 0)
        max_consecutive_losses = self._max_consecutive(pnl < 0)

        # Consistency
        positive_days = (returns_series > 0).sum() if len(returns_series) > 0 else 0

        # Monthly consistency
        if 'executed_at' in df.columns and len(df) > 0:
            monthly_pnl = df.groupby(df['executed_at'].dt.to_period('M'))['pnl'].sum()
            positive_months = (monthly_pnl > 0).sum()
            total_months = len(monthly_pnl)
        else:
            positive_months = 0
            total_months = 0

        monthly_consistency = (positive_months / total_months) * 100 if total_months > 0 else 0

        return PerformanceMetrics(
            start_date=start_date,
            end_date=end_date,
            trading_days=trading_days,
            calendar_days=calendar_days,
            initial_capital=self.initial_capital,
            ending_capital=ending_capital,
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return,
            avg_daily_return=avg_daily_return,
            avg_monthly_return=avg_monthly_return,
            volatility=volatility,
            downside_deviation=downside_deviation,
            max_drawdown=max_drawdown,
            max_drawdown_duration=dd_duration,
            var_95=var_95,
            cvar_95=cvar_95,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            omega_ratio=omega_ratio,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade=avg_trade,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            avg_holding_period=avg_holding_period,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            positive_days=positive_days,
            positive_months=positive_months,
            total_months=total_months,
            monthly_consistency=monthly_consistency
        )

    def _max_consecutive(self, condition: np.ndarray) -> int:
        """Calculate maximum consecutive True values."""
        max_count = 0
        current_count = 0
        for val in condition:
            if val:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        return max_count

    def _generate_equity_curve(self, df: pd.DataFrame) -> EquityCurve:
        """Generate equity curve from trade data."""
        if 'pnl' not in df.columns:
            return EquityCurve(dates=[], equity=[], returns=[], drawdowns=[], high_water_mark=[])

        # Sort by date
        if 'executed_at' in df.columns:
            df = df.sort_values('executed_at')
            dates = df['executed_at'].dt.date.tolist()
        else:
            dates = list(range(len(df)))

        # Calculate cumulative equity
        cumulative_pnl = df['pnl'].cumsum()
        equity = (self.initial_capital + cumulative_pnl).tolist()

        # Calculate returns
        equity_series = pd.Series(equity)
        returns = equity_series.pct_change().fillna(0).tolist()

        # Calculate drawdowns
        equity_array = np.array(equity)
        high_water = np.maximum.accumulate(equity_array)
        drawdowns = ((equity_array - high_water) / high_water).tolist()

        return EquityCurve(
            dates=dates,
            equity=equity,
            returns=returns,
            drawdowns=drawdowns,
            high_water_mark=high_water.tolist()
        )

    def _analyze_trade_distribution(self, df: pd.DataFrame) -> TradeDistribution:
        """Analyze trade distribution patterns."""
        pnl = df['pnl'].values if 'pnl' in df.columns else []

        # PnL histogram
        if len(pnl) > 0:
            bins = [float('-inf'), -1000, -500, -100, 0, 100, 500, 1000, float('inf')]
            labels = ['< -$1000', '-$1000 to -$500', '-$500 to -$100', '-$100 to $0',
                     '$0 to $100', '$100 to $500', '$500 to $1000', '> $1000']
            pnl_hist = pd.cut(pnl, bins=bins, labels=labels).value_counts().to_dict()
            pnl_histogram = {str(k): v for k, v in pnl_hist.items()}
        else:
            pnl_histogram = {}

        # Holding time distribution
        holding_time_distribution = {}
        if 'duration_hours' in df.columns:
            bins = [0, 1, 4, 8, 24, float('inf')]
            labels = ['< 1 hour', '1-4 hours', '4-8 hours', '8-24 hours', '> 24 hours']
            time_hist = pd.cut(df['duration_hours'], bins=bins, labels=labels).value_counts().to_dict()  # noqa: E501
            holding_time_distribution = {str(k): v for k, v in time_hist.items()}

        # Hourly distribution
        hourly_distribution = {}
        if 'executed_at' in df.columns:
            hourly_distribution = df['executed_at'].dt.hour.value_counts().to_dict()

        # Weekday distribution
        weekday_distribution = {}
        if 'executed_at' in df.columns:
            weekday_distribution = df['executed_at'].dt.day_name().value_counts().to_dict()

        # Monthly distribution
        monthly_distribution = {}
        if 'executed_at' in df.columns and 'pnl' in df.columns:
            monthly_pnl = df.groupby(df['executed_at'].dt.strftime('%Y-%m'))['pnl'].sum()
            monthly_distribution = monthly_pnl.to_dict()

        return TradeDistribution(
            pnl_histogram=pnl_histogram,
            holding_time_distribution=holding_time_distribution,
            hourly_distribution=hourly_distribution,
            weekday_distribution=weekday_distribution,
            monthly_distribution=monthly_distribution
        )

    def _calculate_monthly_returns(self, df: pd.DataFrame) -> dict[str, float]:
        """Calculate monthly returns."""
        if 'executed_at' not in df.columns or 'pnl' not in df.columns:
            return {}

        monthly_pnl = df.groupby(df['executed_at'].dt.strftime('%Y-%m'))['pnl'].sum()
        monthly_returns = (monthly_pnl / self.initial_capital * 100).to_dict()

        return monthly_returns

    def _generate_insights(
        self,
        metrics: PerformanceMetrics
    ) -> tuple[list[str], list[str], list[str]]:
        """Generate insights based on performance metrics."""
        strengths = []
        weaknesses = []
        recommendations = []

        # Analyze Sharpe ratio
        if metrics.sharpe_ratio >= 2.0:
            strengths.append(f"Excellent risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")  # noqa: E501
        elif metrics.sharpe_ratio >= 1.0:
            strengths.append(f"Good risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")
        elif metrics.sharpe_ratio < 0.5:
            weaknesses.append(f"Poor risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")
            recommendations.append("Consider reducing position sizes or improving entry timing")

        # Analyze win rate
        if metrics.win_rate >= 60:
            strengths.append(f"Strong win rate ({metrics.win_rate:.1f}%)")
        elif metrics.win_rate < 40:
            weaknesses.append(f"Low win rate ({metrics.win_rate:.1f}%)")
            recommendations.append("Review entry criteria and consider tighter filters")

        # Analyze profit factor
        if metrics.profit_factor >= 2.0:
            strengths.append(f"Excellent profit factor ({metrics.profit_factor:.2f})")
        elif metrics.profit_factor < 1.0:
            weaknesses.append(f"Negative expectancy (PF: {metrics.profit_factor:.2f})")
            recommendations.append("Strategy needs significant improvement - consider pausing live trading")  # noqa: E501

        # Analyze drawdown
        if metrics.max_drawdown < 10:
            strengths.append(f"Low maximum drawdown ({metrics.max_drawdown:.1f}%)")
        elif metrics.max_drawdown > 20:
            weaknesses.append(f"High maximum drawdown ({metrics.max_drawdown:.1f}%)")
            recommendations.append("Implement stricter risk limits or reduce position sizing")

        # Analyze consistency
        if metrics.monthly_consistency >= 70:
            strengths.append(f"Consistent monthly performance ({metrics.monthly_consistency:.0f}% profitable)")  # noqa: E501
        elif metrics.monthly_consistency < 50:
            weaknesses.append(f"Inconsistent monthly results ({metrics.monthly_consistency:.0f}% profitable)")  # noqa: E501
            recommendations.append("Focus on reducing variance in trade outcomes")

        # Analyze avg winner vs loser
        if metrics.avg_winner > 0 and metrics.avg_loser > 0:
            win_loss_ratio = metrics.avg_winner / metrics.avg_loser
            if win_loss_ratio >= 2.0:
                strengths.append(f"Strong reward/risk ratio ({win_loss_ratio:.2f})")
            elif win_loss_ratio < 1.0:
                weaknesses.append(f"Poor reward/risk ratio ({win_loss_ratio:.2f})")
                recommendations.append("Improve profit targets or tighten stop losses")

        return strengths, weaknesses, recommendations

    def export_report(
        self,
        report: PerformanceReport,
        format: str = 'json',
        output_path: Path | None = None
    ) -> str:
        """
        Export performance report to file or string.

        Args:
            report: Performance report to export
            format: Output format ('json', 'text', 'html')
            output_path: Optional file path to save

        Returns:
            Formatted report string
        """
        if format == 'json':
            content = self._to_json(report)
        elif format == 'html':
            content = self._to_html(report)
        else:
            content = self._to_text(report)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(content)
            self.logger.info("Report exported to %s", output_path)

        return content

    def _to_json(self, report: PerformanceReport) -> str:
        """Convert report to JSON."""
        data = {
            'report_date': report.report_date.isoformat(),
            'account_id': report.account_id,
            'strategy_name': report.strategy_name,
            'time_frame': report.time_frame.value,
            'metrics': asdict(report.metrics),
            'monthly_returns': report.monthly_returns,
            'strengths': report.strengths,
            'weaknesses': report.weaknesses,
            'recommendations': report.recommendations
        }

        # Convert dates
        data['metrics']['start_date'] = data['metrics']['start_date'].isoformat()
        data['metrics']['end_date'] = data['metrics']['end_date'].isoformat()

        return json.dumps(data, indent=2)

    def _to_text(self, report: PerformanceReport) -> str:
        """Convert report to text format."""
        m = report.metrics
        lines = [
            "=" * 70,
            "TRADOV PERFORMANCE ANALYTICS REPORT",
            "=" * 70,
            f"Generated: {report.report_date}",
            f"Account: {report.account_id}",
            f"Strategy: {report.strategy_name or 'All'}",
            f"Period: {m.start_date} to {m.end_date}",
            "",
            "-" * 70,
            "SUMMARY",
            "-" * 70,
            f"  Initial Capital:    ${m.initial_capital:,.2f}",
            f"  Ending Capital:     ${m.ending_capital:,.2f}",
            f"  Net Profit:         ${m.net_profit:,.2f}",
            f"  Total Return:       {m.total_return_pct:.2f}%",
            f"  Annualized Return:  {m.annualized_return:.2f}%",
            "",
            "-" * 70,
            "RISK METRICS",
            "-" * 70,
            f"  Volatility:         {m.volatility:.2f}%",
            f"  Max Drawdown:       {m.max_drawdown:.2f}%",
            f"  Sharpe Ratio:       {m.sharpe_ratio:.2f}",
            f"  Sortino Ratio:      {m.sortino_ratio:.2f}",
            f"  Calmar Ratio:       {m.calmar_ratio:.2f}",
            "",
            "-" * 70,
            "TRADE STATISTICS",
            "-" * 70,
            f"  Total Trades:       {m.total_trades}",
            f"  Win Rate:           {m.win_rate:.1f}%",
            f"  Profit Factor:      {m.profit_factor:.2f}",
            f"  Avg Trade:          ${m.avg_trade:.2f}",
            f"  Avg Winner:         ${m.avg_winner:.2f}",
            f"  Avg Loser:          ${m.avg_loser:.2f}",
            f"  Largest Winner:     ${m.largest_winner:.2f}",
            f"  Largest Loser:      ${m.largest_loser:.2f}",
        ]

        if report.strengths:
            lines.extend([
                "",
                "-" * 70,
                "STRENGTHS",
                "-" * 70,
            ])
            for s in report.strengths:
                lines.append(f"  + {s}")

        if report.weaknesses:
            lines.extend([
                "",
                "-" * 70,
                "WEAKNESSES",
                "-" * 70,
            ])
            for w in report.weaknesses:
                lines.append(f"  - {w}")

        if report.recommendations:
            lines.extend([
                "",
                "-" * 70,
                "RECOMMENDATIONS",
                "-" * 70,
            ])
            for i, r in enumerate(report.recommendations, 1):
                lines.append(f"  {i}. {r}")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)

    def _to_html(self, report: PerformanceReport) -> str:
        """Convert report to HTML format."""
        m = report.metrics
        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>Performance Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; }",
            "th { background-color: #4CAF50; color: white; }",
            ".positive { color: green; }",
            ".negative { color: red; }",
            "</style>",
            "</head><body>",
            "<h1>Performance Analytics Report</h1>",
            f"<p>Generated: {report.report_date}</p>",
            "<h2>Summary</h2>",
            "<table>",
            f"<tr><td>Net Profit</td><td class='{'positive' if m.net_profit >= 0 else 'negative'}'>${m.net_profit:,.2f}</td></tr>",  # noqa: E501
            f"<tr><td>Total Return</td><td>{m.total_return_pct:.2f}%</td></tr>",
            f"<tr><td>Sharpe Ratio</td><td>{m.sharpe_ratio:.2f}</td></tr>",
            f"<tr><td>Win Rate</td><td>{m.win_rate:.1f}%</td></tr>",
            f"<tr><td>Max Drawdown</td><td>{m.max_drawdown:.2f}%</td></tr>",
            "</table>",
            "</body></html>"
        ]

        return "\n".join(html)


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "PerformanceAnalytics",
    "PerformanceMetrics",
    "PerformanceReport",
    "EquityCurve",
    "TradeDistribution",
    "TimeFrame",
    "MetricCategory",
]
