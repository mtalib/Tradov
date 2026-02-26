#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK07_StrategyComparison.py
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
import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
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
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    LOCAL_IMPORTS = True
except ImportError:
    import logging
    SpyderLogger = type('SpyderLogger', (), {
        'get_logger': staticmethod(lambda name: logging.getLogger(name))
    })()
    LOCAL_IMPORTS = False

try:
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    SpyderErrorHandler = type('SpyderErrorHandler', (), {
        'handle_error': lambda self, e, context: print(f"Error in {context}: {e}")
    })

# ==============================================================================
# CONSTANTS
# ==============================================================================
REPORT_OUTPUT_DIR = Path("reports/strategy_comparison")
TRADING_DAYS_PER_YEAR = 252
MIN_PERIODS_FOR_COMPARISON = 30
RISK_FREE_RATE = 0.05  # 5% annual risk-free rate

# Benchmark thresholds
GOOD_SHARPE_RATIO = 1.0
EXCELLENT_SHARPE_RATIO = 2.0
GOOD_WIN_RATE = 0.55
EXCELLENT_WIN_RATE = 0.65


# ==============================================================================
# ENUMS
# ==============================================================================
class ComparisonMetric(Enum):
    """Metrics available for strategy comparison."""
    TOTAL_RETURN = "total_return"
    ANNUALIZED_RETURN = "annualized_return"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    VOLATILITY = "volatility"
    CALMAR_RATIO = "calmar_ratio"
    TRADE_COUNT = "trade_count"


class RankingCriteria(Enum):
    """Criteria for ranking strategies."""
    RISK_ADJUSTED = "risk_adjusted"
    ABSOLUTE_RETURN = "absolute_return"
    CONSISTENCY = "consistency"
    COMPOSITE = "composite"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyMetrics:
    """Performance metrics for a single strategy."""
    strategy_name: str
    start_date: date
    end_date: date
    trading_days: int

    # Return metrics
    total_return: float
    annualized_return: float
    avg_daily_return: float
    best_day: float
    worst_day: float

    # Risk metrics
    volatility: float
    downside_deviation: float
    max_drawdown: float
    max_drawdown_duration: int  # days
    var_95: float

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: Optional[float] = None

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration: float = 0.0  # in hours

    # Consistency metrics
    positive_months: int = 0
    total_months: int = 0
    monthly_win_rate: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


@dataclass
class StrategyComparison:
    """Comparison results between two or more strategies."""
    comparison_date: datetime
    strategies: List[str]
    period_start: date
    period_end: date

    # Individual metrics
    strategy_metrics: Dict[str, StrategyMetrics] = field(default_factory=dict)

    # Correlation matrix
    correlation_matrix: Optional[pd.DataFrame] = None

    # Rankings
    rankings_by_sharpe: List[str] = field(default_factory=list)
    rankings_by_return: List[str] = field(default_factory=list)
    rankings_by_consistency: List[str] = field(default_factory=list)
    composite_ranking: List[str] = field(default_factory=list)

    # Statistical tests
    statistical_significance: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Summary
    best_strategy: str = ""
    best_strategy_reason: str = ""
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ComparisonConfig:
    """Configuration for strategy comparison."""
    benchmark: Optional[str] = None
    risk_free_rate: float = RISK_FREE_RATE
    include_correlation: bool = True
    include_statistical_tests: bool = True
    min_periods: int = MIN_PERIODS_FOR_COMPARISON
    ranking_weights: Dict[str, float] = field(default_factory=lambda: {
        'sharpe_ratio': 0.3,
        'total_return': 0.2,
        'max_drawdown': 0.2,
        'win_rate': 0.15,
        'consistency': 0.15
    })


# ==============================================================================
# STRATEGY COMPARISON ANALYZER
# ==============================================================================
class StrategyComparisonAnalyzer:
    """
    Comprehensive strategy comparison and analysis tool.

    Provides detailed comparative analysis of trading strategies including
    performance metrics, risk analysis, correlation studies, and statistical
    significance testing.
    """

    def __init__(self, config: Optional[ComparisonConfig] = None):
        """
        Initialize strategy comparison analyzer.

        Args:
            config: Optional comparison configuration
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.config = config or ComparisonConfig()

        # Output configuration
        self.output_dir = Path(REPORT_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Thread safety
        self._lock = threading.Lock()

        self.logger.info("StrategyComparisonAnalyzer initialized")

    def compare_strategies(
        self,
        strategy_returns: Dict[str, pd.Series],
        strategy_trades: Optional[Dict[str, pd.DataFrame]] = None
    ) -> StrategyComparison:
        """
        Compare multiple strategies.

        Args:
            strategy_returns: Dictionary mapping strategy names to return series
            strategy_trades: Optional dictionary mapping strategy names to trade DataFrames

        Returns:
            StrategyComparison with detailed comparison results
        """
        with self._lock:
            try:
                if len(strategy_returns) < 2:
                    raise ValueError("At least 2 strategies required for comparison")

                strategies = list(strategy_returns.keys())

                # Align all return series to common date range
                aligned_returns = self._align_returns(strategy_returns)

                # Determine comparison period
                all_dates = pd.concat([s for s in aligned_returns.values()]).index
                period_start = all_dates.min().date()
                period_end = all_dates.max().date()

                comparison = StrategyComparison(
                    comparison_date=datetime.now(),
                    strategies=strategies,
                    period_start=period_start,
                    period_end=period_end
                )

                # Calculate metrics for each strategy
                for name, returns in aligned_returns.items():
                    trades = strategy_trades.get(name) if strategy_trades else None
                    comparison.strategy_metrics[name] = self._calculate_strategy_metrics(
                        name, returns, trades
                    )

                # Calculate correlation matrix
                if self.config.include_correlation and len(strategies) > 1:
                    comparison.correlation_matrix = self._calculate_correlations(aligned_returns)

                # Perform statistical tests
                if self.config.include_statistical_tests and len(strategies) == 2:
                    comparison.statistical_significance = self._run_statistical_tests(
                        aligned_returns
                    )

                # Generate rankings
                comparison.rankings_by_sharpe = self._rank_by_metric(
                    comparison.strategy_metrics, 'sharpe_ratio', reverse=True
                )
                comparison.rankings_by_return = self._rank_by_metric(
                    comparison.strategy_metrics, 'total_return', reverse=True
                )
                comparison.rankings_by_consistency = self._rank_by_metric(
                    comparison.strategy_metrics, 'monthly_win_rate', reverse=True
                )
                comparison.composite_ranking = self._calculate_composite_ranking(
                    comparison.strategy_metrics
                )

                # Determine best strategy and generate recommendations
                comparison.best_strategy = comparison.composite_ranking[0]
                comparison.best_strategy_reason = self._explain_best_strategy(
                    comparison.best_strategy,
                    comparison.strategy_metrics[comparison.best_strategy]
                )
                comparison.recommendations = self._generate_recommendations(comparison)

                self.logger.info(
                    f"Strategy comparison complete: {len(strategies)} strategies analyzed"
                )

                return comparison

            except Exception as e:
                self.logger.error(f"Error comparing strategies: {e}")
                raise

    def _align_returns(
        self,
        strategy_returns: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """Align all return series to common date range."""
        # Find common date range
        all_indices = [set(returns.index) for returns in strategy_returns.values()]
        common_dates = set.intersection(*all_indices) if all_indices else set()

        if len(common_dates) < self.config.min_periods:
            self.logger.warning(
                f"Only {len(common_dates)} common periods found, "
                f"minimum is {self.config.min_periods}"
            )

        aligned = {}
        for name, returns in strategy_returns.items():
            common_series = returns[returns.index.isin(common_dates)].sort_index()
            aligned[name] = common_series

        return aligned

    def _calculate_strategy_metrics(
        self,
        name: str,
        returns: pd.Series,
        trades: Optional[pd.DataFrame] = None
    ) -> StrategyMetrics:
        """Calculate comprehensive metrics for a strategy."""
        trading_days = len(returns)

        # Basic return metrics
        total_return = (1 + returns).prod() - 1
        annualized_return = (1 + total_return) ** (TRADING_DAYS_PER_YEAR / trading_days) - 1
        avg_daily_return = returns.mean()
        best_day = returns.max()
        worst_day = returns.min()

        # Risk metrics
        volatility = returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        downside_returns = returns[returns < 0]
        downside_deviation = downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR) if len(downside_returns) > 0 else 0

        # Drawdown calculation
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdowns.min())

        # Drawdown duration
        in_drawdown = drawdowns < 0
        dd_duration = 0
        current_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                dd_duration = max(dd_duration, current_duration)
            else:
                current_duration = 0

        # VaR 95%
        var_95 = abs(np.percentile(returns, 5))

        # Risk-adjusted metrics
        excess_return = annualized_return - self.config.risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility > 0 else 0
        sortino_ratio = excess_return / downside_deviation if downside_deviation > 0 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # Monthly statistics
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        positive_months = (monthly_returns > 0).sum()
        total_months = len(monthly_returns)
        monthly_win_rate = positive_months / total_months if total_months > 0 else 0

        metrics = StrategyMetrics(
            strategy_name=name,
            start_date=returns.index.min().date(),
            end_date=returns.index.max().date(),
            trading_days=trading_days,
            total_return=total_return,
            annualized_return=annualized_return,
            avg_daily_return=avg_daily_return,
            best_day=best_day,
            worst_day=worst_day,
            volatility=volatility,
            downside_deviation=downside_deviation,
            max_drawdown=max_drawdown,
            max_drawdown_duration=dd_duration,
            var_95=var_95,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            positive_months=positive_months,
            total_months=total_months,
            monthly_win_rate=monthly_win_rate
        )

        # Trade statistics if available
        if trades is not None and len(trades) > 0:
            metrics = self._add_trade_statistics(metrics, trades)

        return metrics

    def _add_trade_statistics(
        self,
        metrics: StrategyMetrics,
        trades: pd.DataFrame
    ) -> StrategyMetrics:
        """Add trade-level statistics to metrics."""
        # Expect trades DataFrame to have 'pnl' column
        if 'pnl' not in trades.columns:
            return metrics

        pnl = trades['pnl']
        metrics.total_trades = len(trades)
        metrics.winning_trades = (pnl > 0).sum()
        metrics.losing_trades = (pnl < 0).sum()
        metrics.win_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0

        winning_pnl = pnl[pnl > 0]
        losing_pnl = pnl[pnl < 0]

        metrics.avg_win = winning_pnl.mean() if len(winning_pnl) > 0 else 0
        metrics.avg_loss = abs(losing_pnl.mean()) if len(losing_pnl) > 0 else 0

        total_wins = winning_pnl.sum() if len(winning_pnl) > 0 else 0
        total_losses = abs(losing_pnl.sum()) if len(losing_pnl) > 0 else 0
        metrics.profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Consecutive wins/losses
        is_win = (pnl > 0).astype(int)
        metrics.max_consecutive_wins = self._max_consecutive(is_win, 1)
        metrics.max_consecutive_losses = self._max_consecutive(is_win, 0)

        # Trade duration if available
        if 'duration_hours' in trades.columns:
            metrics.avg_trade_duration = trades['duration_hours'].mean()

        return metrics

    def _max_consecutive(self, series: pd.Series, value: int) -> int:
        """Calculate maximum consecutive occurrences of a value."""
        max_count = 0
        current_count = 0
        for v in series:
            if v == value:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        return max_count

    def _calculate_correlations(
        self,
        aligned_returns: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """Calculate correlation matrix between strategies."""
        returns_df = pd.DataFrame(aligned_returns)
        return returns_df.corr()

    def _run_statistical_tests(
        self,
        aligned_returns: Dict[str, pd.Series]
    ) -> Dict[str, Dict[str, float]]:
        """Run statistical significance tests between strategies."""
        results = {}
        strategies = list(aligned_returns.keys())

        if len(strategies) != 2:
            return results

        s1, s2 = strategies
        r1 = aligned_returns[s1]
        r2 = aligned_returns[s2]

        # Paired t-test for mean returns
        try:
            from scipy import stats
            t_stat, p_value = stats.ttest_rel(r1, r2)
            results[f"{s1}_vs_{s2}"] = {
                't_statistic': t_stat,
                'p_value': p_value,
                'significant_at_05': p_value < 0.05,
                'significant_at_01': p_value < 0.01
            }
        except ImportError:
            self.logger.warning("scipy not available for statistical tests")
        except Exception as e:
            self.logger.warning(f"Statistical test failed: {e}")

        return results

    def _rank_by_metric(
        self,
        metrics: Dict[str, StrategyMetrics],
        metric_name: str,
        reverse: bool = True
    ) -> List[str]:
        """Rank strategies by a specific metric."""
        ranked = sorted(
            metrics.items(),
            key=lambda x: getattr(x[1], metric_name),
            reverse=reverse
        )
        return [name for name, _ in ranked]

    def _calculate_composite_ranking(
        self,
        metrics: Dict[str, StrategyMetrics]
    ) -> List[str]:
        """Calculate composite ranking based on weighted metrics."""
        weights = self.config.ranking_weights
        scores = {}

        for name, m in metrics.items():
            score = 0
            # Normalize and weight each metric
            score += weights.get('sharpe_ratio', 0) * min(m.sharpe_ratio / EXCELLENT_SHARPE_RATIO, 1)
            score += weights.get('total_return', 0) * min(m.total_return, 1)
            score += weights.get('max_drawdown', 0) * (1 - min(m.max_drawdown, 0.5) / 0.5)
            score += weights.get('win_rate', 0) * m.win_rate
            score += weights.get('consistency', 0) * m.monthly_win_rate
            scores[name] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [name for name, _ in ranked]

    def _explain_best_strategy(
        self,
        strategy_name: str,
        metrics: StrategyMetrics
    ) -> str:
        """Generate explanation for why a strategy is ranked best."""
        reasons = []

        if metrics.sharpe_ratio >= EXCELLENT_SHARPE_RATIO:
            reasons.append(f"excellent risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")
        elif metrics.sharpe_ratio >= GOOD_SHARPE_RATIO:
            reasons.append(f"good risk-adjusted returns (Sharpe: {metrics.sharpe_ratio:.2f})")

        if metrics.max_drawdown < 0.10:
            reasons.append(f"low maximum drawdown ({metrics.max_drawdown*100:.1f}%)")

        if metrics.win_rate >= EXCELLENT_WIN_RATE:
            reasons.append(f"excellent win rate ({metrics.win_rate*100:.1f}%)")
        elif metrics.win_rate >= GOOD_WIN_RATE:
            reasons.append(f"good win rate ({metrics.win_rate*100:.1f}%)")

        if metrics.monthly_win_rate >= 0.70:
            reasons.append(f"consistent monthly performance ({metrics.monthly_win_rate*100:.1f}% profitable months)")

        if not reasons:
            reasons.append("best overall composite score across all metrics")

        return f"{strategy_name} ranks highest due to: {', '.join(reasons)}"

    def _generate_recommendations(
        self,
        comparison: StrategyComparison
    ) -> List[str]:
        """Generate actionable recommendations from comparison."""
        recommendations = []
        best = comparison.strategy_metrics[comparison.best_strategy]

        # Recommendation based on correlation
        if comparison.correlation_matrix is not None:
            corr_values = comparison.correlation_matrix.values
            off_diagonal = corr_values[np.triu_indices(len(corr_values), k=1)]
            if len(off_diagonal) > 0:
                avg_corr = np.mean(off_diagonal)
                if avg_corr < 0.3:
                    recommendations.append(
                        "Strategies show low correlation - consider running them in parallel for diversification"
                    )
                elif avg_corr > 0.7:
                    recommendations.append(
                        "Strategies are highly correlated - limited diversification benefit from running both"
                    )

        # Recommendations based on best strategy characteristics
        if best.max_drawdown > 0.15:
            recommendations.append(
                f"Consider adding stop-loss rules to {comparison.best_strategy} "
                f"to reduce {best.max_drawdown*100:.1f}% max drawdown"
            )

        if best.sharpe_ratio < GOOD_SHARPE_RATIO:
            recommendations.append(
                "All strategies have below-average risk-adjusted returns - consider parameter optimization"
            )

        # Compare to identify specific improvements
        for name, metrics in comparison.strategy_metrics.items():
            if name == comparison.best_strategy:
                continue
            if metrics.win_rate > best.win_rate * 1.1:
                recommendations.append(
                    f"{name} has better win rate - consider analyzing its entry signals"
                )
            if metrics.max_drawdown < best.max_drawdown * 0.8:
                recommendations.append(
                    f"{name} has lower drawdown - consider adopting its risk management approach"
                )

        return recommendations

    def generate_comparison_report(
        self,
        comparison: StrategyComparison,
        format: str = 'text'
    ) -> str:
        """
        Generate formatted comparison report.

        Args:
            comparison: Comparison results
            format: Output format ('text', 'json', 'html')

        Returns:
            Formatted report string
        """
        if format == 'json':
            return self._generate_json_report(comparison)
        elif format == 'html':
            return self._generate_html_report(comparison)
        else:
            return self._generate_text_report(comparison)

    def _generate_text_report(self, comparison: StrategyComparison) -> str:
        """Generate text format report."""
        lines = [
            "=" * 80,
            "SPYDER STRATEGY COMPARISON REPORT",
            "=" * 80,
            f"Generated: {comparison.comparison_date}",
            f"Period: {comparison.period_start} to {comparison.period_end}",
            f"Strategies Compared: {', '.join(comparison.strategies)}",
            "",
            "-" * 80,
            "PERFORMANCE SUMMARY",
            "-" * 80,
            ""
        ]

        # Performance table header
        headers = ["Strategy", "Return", "Sharpe", "Sortino", "Max DD", "Win Rate", "Trades"]
        lines.append(f"{headers[0]:<20} {headers[1]:>10} {headers[2]:>8} {headers[3]:>8} {headers[4]:>8} {headers[5]:>10} {headers[6]:>8}")
        lines.append("-" * 80)

        # Performance data rows
        for name in comparison.composite_ranking:
            m = comparison.strategy_metrics[name]
            lines.append(
                f"{name:<20} {m.total_return*100:>9.2f}% {m.sharpe_ratio:>8.2f} "
                f"{m.sortino_ratio:>8.2f} {m.max_drawdown*100:>7.2f}% "
                f"{m.win_rate*100:>9.1f}% {m.total_trades:>8}"
            )

        lines.extend([
            "",
            "-" * 80,
            "RANKINGS",
            "-" * 80,
            f"By Sharpe Ratio: {' > '.join(comparison.rankings_by_sharpe)}",
            f"By Total Return: {' > '.join(comparison.rankings_by_return)}",
            f"By Consistency:  {' > '.join(comparison.rankings_by_consistency)}",
            f"Composite:       {' > '.join(comparison.composite_ranking)}",
            "",
            "-" * 80,
            "BEST STRATEGY",
            "-" * 80,
            comparison.best_strategy_reason,
        ])

        if comparison.correlation_matrix is not None:
            lines.extend([
                "",
                "-" * 80,
                "CORRELATION MATRIX",
                "-" * 80,
            ])
            lines.append(comparison.correlation_matrix.to_string())

        if comparison.recommendations:
            lines.extend([
                "",
                "-" * 80,
                "RECOMMENDATIONS",
                "-" * 80,
            ])
            for i, rec in enumerate(comparison.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)

    def _generate_json_report(self, comparison: StrategyComparison) -> str:
        """Generate JSON format report."""
        data = {
            'comparison_date': comparison.comparison_date.isoformat(),
            'period_start': comparison.period_start.isoformat(),
            'period_end': comparison.period_end.isoformat(),
            'strategies': comparison.strategies,
            'strategy_metrics': {
                name: asdict(metrics)
                for name, metrics in comparison.strategy_metrics.items()
            },
            'rankings': {
                'by_sharpe': comparison.rankings_by_sharpe,
                'by_return': comparison.rankings_by_return,
                'by_consistency': comparison.rankings_by_consistency,
                'composite': comparison.composite_ranking
            },
            'best_strategy': comparison.best_strategy,
            'best_strategy_reason': comparison.best_strategy_reason,
            'recommendations': comparison.recommendations
        }

        # Convert dates in metrics
        for name, metrics in data['strategy_metrics'].items():
            metrics['start_date'] = metrics['start_date'].isoformat()
            metrics['end_date'] = metrics['end_date'].isoformat()

        if comparison.correlation_matrix is not None:
            data['correlation_matrix'] = comparison.correlation_matrix.to_dict()

        return json.dumps(data, indent=2)

    def _generate_html_report(self, comparison: StrategyComparison) -> str:
        """Generate HTML format report."""
        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>Strategy Comparison Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; margin: 20px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }",
            "th { background-color: #4CAF50; color: white; }",
            "tr:nth-child(even) { background-color: #f2f2f2; }",
            ".best { background-color: #90EE90; font-weight: bold; }",
            "h1, h2, h3 { color: #333; }",
            "</style>",
            "</head><body>",
            "<h1>Strategy Comparison Report</h1>",
            f"<p>Generated: {comparison.comparison_date}</p>",
            f"<p>Period: {comparison.period_start} to {comparison.period_end}</p>",
            "",
            "<h2>Performance Summary</h2>",
            "<table>",
            "<tr><th>Strategy</th><th>Return</th><th>Sharpe</th><th>Sortino</th>",
            "<th>Max DD</th><th>Win Rate</th><th>Trades</th></tr>"
        ]

        for name in comparison.composite_ranking:
            m = comparison.strategy_metrics[name]
            css_class = 'best' if name == comparison.best_strategy else ''
            html.append(
                f"<tr class='{css_class}'><td>{name}</td>"
                f"<td>{m.total_return*100:.2f}%</td>"
                f"<td>{m.sharpe_ratio:.2f}</td>"
                f"<td>{m.sortino_ratio:.2f}</td>"
                f"<td>{m.max_drawdown*100:.2f}%</td>"
                f"<td>{m.win_rate*100:.1f}%</td>"
                f"<td>{m.total_trades}</td></tr>"
            )

        html.extend([
            "</table>",
            f"<h2>Best Strategy: {comparison.best_strategy}</h2>",
            f"<p>{comparison.best_strategy_reason}</p>",
            "<h2>Recommendations</h2>",
            "<ul>"
        ])

        for rec in comparison.recommendations:
            html.append(f"<li>{rec}</li>")

        html.extend([
            "</ul>",
            "</body></html>"
        ])

        return "\n".join(html)

    def export_comparison(
        self,
        comparison: StrategyComparison,
        filename: Optional[str] = None,
        format: str = 'text'
    ) -> Path:
        """
        Export comparison report to file.

        Args:
            comparison: Comparison results
            filename: Optional custom filename
            format: Output format ('text', 'json', 'html')

        Returns:
            Path to exported file
        """
        if filename is None:
            filename = f"strategy_comparison_{comparison.comparison_date.strftime('%Y%m%d_%H%M%S')}"

        extension = {'text': 'txt', 'json': 'json', 'html': 'html'}.get(format, 'txt')
        output_path = self.output_dir / f"{filename}.{extension}"

        report_content = self.generate_comparison_report(comparison, format)

        with open(output_path, 'w') as f:
            f.write(report_content)

        self.logger.info(f"Comparison report exported to {output_path}")
        return output_path

    # --------------------------------------------------------------------------
    # PYFOLIO / EMPYRICAL INTEGRATION
    # --------------------------------------------------------------------------

    def generate_round_trip_analysis(self, strategy_returns: Dict[str, pd.Series],
                                     benchmark_returns: Optional[pd.Series] = None,
                                     ) -> Dict[str, Dict[str, Any]]:
        """
        Generate round-trip tear sheet analysis per strategy using empyrical.

        Args:
            strategy_returns: {strategy_name: returns_series} mapping.
            benchmark_returns: Optional benchmark series for alpha/beta.

        Returns:
            Dictionary of strategy metrics for head-to-head comparison.
        """
        try:
            import empyrical
        except ImportError:
            self.logger.warning("empyrical not installed — skipping round-trip analysis")
            return {}

        rf_daily = 0.05 / 252
        result: Dict[str, Dict[str, Any]] = {}

        for name, returns in strategy_returns.items():
            if len(returns) < 20:
                continue

            metrics = {
                'sharpe_ratio': float(empyrical.sharpe_ratio(returns, risk_free=rf_daily)),
                'sortino_ratio': float(empyrical.sortino_ratio(returns)),
                'calmar_ratio': float(empyrical.calmar_ratio(returns)),
                'max_drawdown': float(empyrical.max_drawdown(returns)),
                'annual_return': float(empyrical.annual_return(returns)),
                'annual_volatility': float(empyrical.annual_volatility(returns)),
                'omega_ratio': float(empyrical.omega_ratio(returns)),
                'tail_ratio': float(empyrical.tail_ratio(returns)),
                'stability': float(empyrical.stability_of_timeseries(returns)),
                'var_95': float(np.percentile(returns, 5)),
                'win_rate': float((returns > 0).sum() / len(returns)),
            }

            if benchmark_returns is not None:
                idx = returns.index.intersection(benchmark_returns.index)
                if len(idx) > 10:
                    r, b = returns.loc[idx], benchmark_returns.loc[idx]
                    metrics['alpha'] = float(empyrical.alpha(r, b, rf_daily))
                    metrics['beta'] = float(empyrical.beta(r, b))

            result[name] = metrics

        # Rank by Sharpe
        ranked = sorted(result.items(), key=lambda x: x[1].get('sharpe_ratio', 0), reverse=True)
        self.logger.info(f"Round-trip analysis: {len(result)} strategies, "
                         f"best={ranked[0][0] if ranked else 'N/A'}")
        return result


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    "StrategyComparisonAnalyzer",
    "StrategyComparison",
    "StrategyMetrics",
    "ComparisonConfig",
    "ComparisonMetric",
    "RankingCriteria",
]
